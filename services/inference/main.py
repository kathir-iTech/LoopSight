"""
LoopSight — FastAPI inference service.

Exposes:
  POST /inspect  — multipart form data with image file + inspection_profile
  GET  /jobs/{job_id} — returns stored InspectionResult

Wiring (per spec Section 9 & prompt):
  1. decode uploaded image
  2. run cv.first_pass.run_first_pass
  3. if UNCERTAIN -> agent.tool_selector.select_tool with a mock_fixture (no Gemini key)
     -> run selected tool from cv.tools.TOOL_REGISTRY
     -> cv.policy.decide for final verdict
  4. otherwise decide without second pass
  5. store full result keyed by job_id, return {job_id}

The result JSON shape matches apps/web/src/lib/types.ts exactly.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import platform
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

# Load .env if present so GEMINI_API_KEY pasted by the user is picked up
# without requiring manual `export` (works both locally and in Docker).
def _load_dotenv():
    candidates = [
        Path(__file__).resolve().parents[3] / ".env",  # repo root when running from services/inference/
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if cand.is_file():
            try:
                with cand.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
                break
            except Exception:
                continue

_load_dotenv()

# Ensure local imports work whether uvicorn is launched from
# services/inference/ or from the repo root.
sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger(__name__)

import cv2
import numpy as np
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Local CV / agent modules (these are the real pipeline, not mocks)
from cv.first_pass import run_first_pass, PROFILES  # type: ignore
from cv.tools import TOOL_REGISTRY  # type: ignore
from cv.policy import decide  # type: ignore
from agent.tool_selector import select_tool  # type: ignore
from storage import create_job_store, InMemoryJobStore  # type: ignore
import demo_golden  # type: ignore

app = FastAPI(title="LoopSight Inference", version="0.1.0")

# Lambda adapter — wraps the same FastAPI app for AWS Lambda's handler interface.
# Leave every existing route/logic untouched; locally uvicorn still runs the app directly.
# Added for Phase 4 Lambda deployment (always-free tier); not pursuing Best Use of COOL.
try:
    from mangum import Mangum  # type: ignore

    handler = Mangum(app)
except Exception:  # mangum not installed in some local envs — still allow `uvicorn main:app`
    handler = None  # type: ignore

# Enable CORS for the Next.js dev server (http://localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (default) — wrapped by the JobStore abstraction.
# This dict is the backing store for InMemoryJobStore and the default when no AWS credentials are present.
JOBS: Dict[str, dict] = {}

# Upload hardening: reject files above this size up-front (10 MiB) so a huge
# or malicious multipart body can never be buffered/decoded into memory or
# forwarded to the CV pipeline. Returns a structured 413, never a 500.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# JobStore abstraction — picks InMemory vs Dynamo at startup based on env/credentials.
# See storage.py: InMemoryJobStore wraps JOBS; DynamoJobStore uses boto3 only if credentials resolvable.
store = create_job_store(JOBS)


def _decode_image(data: bytes) -> np.ndarray:
    """Decode raw image bytes (jpeg/png/webp) into a BGR numpy array via OpenCV."""
    if not data:
        raise ValueError("empty image file")
    nparr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image — unsupported format or corrupt data")
    return img


def _fixture_for_first_pass(first_pass) -> dict:
    """
    Pick a sensible mock_fixture based on the evidence_gap.

    This is the placeholder for the real Gemini call — per the prompt:
    'no real Gemini key yet — pick a sensible fixture based on the evidence_gap'.
    The fixture still flows through the real whitelist validation & fallback
    logic in agent.tool_selector, so the integration is genuine.
    """
    gap_str = " ".join(first_pass.evidence_gap).lower() if first_pass.evidence_gap else ""
    allowed = first_pass.allowed_tools or []

    # Low reference similarity -> re-check against reference if possible
    if "reference similarity" in gap_str:
        if "compare_to_reference" in allowed:
            return {"tool": "compare_to_reference", "arguments": {}, "reason_code": "LOW_REFERENCE_SIMILARITY"}
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "LOW_REFERENCE_SIMILARITY"}

    # Low contrast -> upsampled re-inspection (materially different observation)
    if "low local contrast" in gap_str:
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "INSUFFICIENT_LOCAL_CONTRAST"}
        if "measure_edge_continuity" in allowed:
            return {"tool": "measure_edge_continuity", "arguments": {"low": 30, "high": 100}, "reason_code": "INSUFFICIENT_LOCAL_CONTRAST"}

    # Ambiguous edge band -> more sensitive edge thresholds
    if "ambiguous" in gap_str or "edge continuity" in gap_str:
        if "measure_edge_continuity" in allowed:
            return {"tool": "measure_edge_continuity", "arguments": {"low": 30, "high": 100}, "reason_code": "AMBIGUOUS_EDGE_BAND"}
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "AMBIGUOUS_EDGE_BAND"}

    # No regions measured or generic UNCERTAIN
    if "no regions" in gap_str:
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "NO_REGIONS_FALLBACK"}
        if "measure_edge_continuity" in allowed:
            return {"tool": "measure_edge_continuity", "arguments": {"low": 30, "high": 100}, "reason_code": "NO_REGIONS_FALLBACK"}

    # Default fallback — prefer a non-video tool for single-image uploads
    if "reinspect_roi" in allowed:
        return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "DEFAULT_REINSPECT"}
    if "measure_edge_continuity" in allowed:
        return {"tool": "measure_edge_continuity", "arguments": {"low": 30, "high": 100}, "reason_code": "DEFAULT_EDGE_CHECK"}
    if "compare_to_reference" in allowed:
        return {"tool": "compare_to_reference", "arguments": {}, "reason_code": "DEFAULT_REFERENCE_CHECK"}
    # As a last resort, pick first allowed that is not video-mode (avoid track_across_frames for single image)
    for t in allowed:
        if t != "track_across_frames":
            return {"tool": t, "arguments": {}, "reason_code": "FALLBACK_DEFAULT"}
    if allowed:
        return {"tool": allowed[0], "arguments": {}, "reason_code": "FALLBACK_DEFAULT"}
    # No allowed tools at all (should not happen) — force reinspect_roi and let select_tool fallback handle it
    return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "FALLBACK_NO_ALLOWED_TOOLS"}


def _run_tool(tool_call, frame: np.ndarray, reference: np.ndarray | None, roi: tuple[int, int, int, int]):
    """
    Dispatch to the real TOOL_REGISTRY entry for the agent-selected tool.
    Handles the special-case that some tools need different signatures or are
    video-only (track_across_frames) and must be redirected for single-image mode.
    """
    tool_name = tool_call.tool
    args = tool_call.arguments or {}

    # Video-mode tool can't run on a single uploaded image — redirect to reinspect_roi
    # (still preserves the original agent_call for the evidence trace)
    if tool_name == "track_across_frames":
        fn = TOOL_REGISTRY["reinspect_roi"]
        return fn(frame, reference, roi, scale=2.0)

    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        raise ValueError(f"tool '{tool_name}' not in registry")

    if tool_name == "reinspect_roi":
        scale = float(args.get("scale", 2.0))
        return fn(frame, reference, roi, scale=scale)
    elif tool_name == "compare_to_reference":
        # compare_to_reference requires a reference image; if none supplied,
        # gracefully fall back to reinspect_roi rather than crashing the request
        if reference is None:
            fallback = TOOL_REGISTRY["reinspect_roi"]
            return fallback(frame, reference, roi, scale=2.0)
        return fn(frame, reference, roi)
    elif tool_name == "measure_edge_continuity":
        low = int(args.get("low", 30))
        high = int(args.get("high", 100))
        return fn(frame, roi, low=low, high=high)
    else:
        # Generic fallback for any future tool — try (frame, reference, roi, **args) then (frame, roi, **args)
        try:
            return fn(frame, reference, roi, **args)
        except TypeError:
            return fn(frame, roi, **args)


@app.get("/")
async def health():
    # Report job count from the active store; for InMemory it's len(JOBS), for Dynamo it's not cheap to count
    try:
        if isinstance(store, InMemoryJobStore):
            count = len(store.store)
        else:
            # Dynamo — avoid expensive Scan; report backing dict size (0) and store type
            count = 0
    except Exception:
        count = 0
    return {"status": "ok", "service": "loopsight-inference", "jobs": count, "store": type(store).__name__}


@app.get("/health")
async def health_alt():
    return {"status": "ok"}


# Phase 6: /version endpoint for technical report and judge verification
BUILD_TIMESTAMP = datetime.datetime.now(datetime.timezone.utc).isoformat()

@app.get("/version")
async def version():
    """Returns stack version evidence — used in technical report and by judges to verify OpenCV 5."""
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    return {
        "opencv_version": cv2.__version__,
        "python_version": platform.python_version(),
        "profile_names": sorted(PROFILES.keys()),
        "gemini_model": gemini_model,
        "build_timestamp": BUILD_TIMESTAMP,
    }


@app.post("/inspect")
async def inspect(request: Request):
    """
    Multipart form endpoint:
      - image: file (field names accepted: 'image' or 'file')
      - inspection_profile: string, default 'fdm_print_surface_v1'

    Runs the real CV pipeline, returns { job_id } and stores the full
    InspectionResult for later retrieval via GET /jobs/{job_id}.

    Timing instrumentation (Phase 5): wall-clock for decode, first_pass,
    agent call (if fired), second_pass, and total — logged as a structured
    JSON line and stored in result["measurements"] for Experiment D (COOL baseline comparison).
    """
    t_total_start = time.perf_counter()
    decode_ms: Optional[float] = None
    first_pass_ms: Optional[float] = None
    agent_ms: Optional[float] = None
    second_pass_ms: Optional[float] = None

    form = await request.form()

    # --- Demo-mode short-circuit (DEMO_MODE=golden) ---
    # Serve a pre-computed golden result INSTEAD of running the live pipeline,
    # so a demo in front of judges never depends on a live API (Gemini or the
    # CV runtime) working. See spec Section 10: this is a required fallback,
    # not optional polish. The result is stored so GET /jobs/{id} still works.
    golden = demo_golden.resolve_golden_from_request(form)
    if golden is not None:
        golden_job_id = uuid.uuid4().hex[:8]
        try:
            store.save(golden_job_id, golden)
        except Exception:
            JOBS[golden_job_id] = golden
        return JSONResponse({"job_id": golden_job_id})

    # Accept both 'image' (frontend) and 'file' (generic clients/curl) field names
    upload = form.get("image")
    if upload is None:
        upload = form.get("file")

    if upload is None:
        raise HTTPException(status_code=400, detail="missing image file: expected multipart field 'image'")

    # inspection_profile is optional, default per prompt
    profile_name = form.get("inspection_profile") or "fdm_print_surface_v1"
    # form values can be UploadFile-like or plain strings; normalize to str
    if hasattr(profile_name, "read"):
        # unlikely, but handle file-like profile
        profile_name = (await profile_name.read()).decode("utf-8")  # type: ignore
    profile_name = str(profile_name).strip() or "fdm_print_surface_v1"

    if profile_name not in PROFILES:
        raise HTTPException(status_code=400, detail=f"unknown inspection_profile '{profile_name}'. valid: {sorted(PROFILES.keys())}")

    # Read raw bytes from the uploaded file
    try:
        # UploadFile object (starlette)
        if hasattr(upload, "read"):
            data = await upload.read()  # type: ignore
        else:
            # Already bytes/str
            data = bytes(upload)  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"failed to read image file: {e}")

    if not data:
        raise HTTPException(status_code=400, detail="image file is empty")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"image file too large: {len(data)} bytes exceeds limit of {MAX_UPLOAD_BYTES} bytes",
        )

    # Decode image via OpenCV — timed for Experiment D
    t0 = time.perf_counter()
    try:
        frame = _decode_image(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    decode_ms = (time.perf_counter() - t0) * 1000

    h, w = frame.shape[:2]
    # Single ROI covering the full image — simple, matches synthetic test harness.
    # Future: part-detection to propose tighter ROIs; not needed for v1 wiring.
    roi = (0, 0, w, h)
    # Phase 3: optional reference image for comparison (known-good print)
    reference = None
    ref_upload = form.get("reference_image") or form.get("reference") or form.get("referenceImage")
    if ref_upload is not None and hasattr(ref_upload, "read"):
        try:
            ref_data = await ref_upload.read()  # type: ignore
            if ref_data and len(ref_data) <= MAX_UPLOAD_BYTES:
                try:
                    reference = _decode_image(ref_data)
                    # If decoded reference shape mismatches frame, still pass it — measure_region handles shape mismatch
                    logger.info(f"[inspect] reference image decoded: shape={reference.shape}")
                except ValueError as e:
                    logger.warning(f"[inspect] reference image decode failed, ignoring: {e}")
                    reference = None
            elif ref_data and len(ref_data) > MAX_UPLOAD_BYTES:
                logger.warning(f"[inspect] reference image too large ({len(ref_data)} bytes), ignoring")
        except Exception as e:
            logger.warning(f"[inspect] failed to read reference_image: {e}")
            reference = None

    # --- First pass (deterministic OpenCV) — timed ---
    t0 = time.perf_counter()
    first_pass = run_first_pass(frame, reference, [roi], profile_name=profile_name)
    first_pass_ms = (time.perf_counter() - t0) * 1000

    agent_call_dict = None
    second_pass = None
    tool_result = None
    tool_call = None

    # --- Agent + second pass (only if UNCERTAIN) ---
    if first_pass.status == "UNCERTAIN":
        t_agent = time.perf_counter()
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            # Real Gemini integration — gated behind env var so local dev without a key keeps mock behavior.
            tool_call = select_tool(first_pass, api_key=gemini_key)
        else:
            fixture = _fixture_for_first_pass(first_pass)
            # Mock path: flows through the same whitelist + fallback logic that the live Gemini path uses.
            tool_call = select_tool(first_pass, mock_fixture=fixture)
        agent_ms = (time.perf_counter() - t_agent) * 1000
        agent_call_dict = {"tool": tool_call.tool, "reason_code": tool_call.reason_code}

        t_sp = time.perf_counter()
        try:
            tool_result = _run_tool(tool_call, frame, reference, roi)
        except Exception as e:
            # Tool failure should not crash the whole request — degrade to
            # a REVIEW decision (policy's fallback when second_pass_region is None)
            # but preserve the agent_call for observability.
            logger.warning(f"[inspect] tool {tool_call.tool} failed: {e}")
            tool_result = None
        second_pass_ms = (time.perf_counter() - t_sp) * 1000

        # Second-pass regions for the API response (exact shape from types.ts)
        if tool_result is not None:
            reg = tool_result.region
            sec_entry: dict = {"edge_continuity": float(reg.edge_continuity)}
            # Only include optional metrics when they were actually measured (>=0)
            # measure_edge_continuity intentionally sets -1.0 for non-measured fields
            if getattr(reg, "reference_similarity", -1) >= 0:
                sec_entry["reference_similarity"] = float(reg.reference_similarity)
            if getattr(reg, "layer_alignment_deviation", -1) >= 0:
                sec_entry["layer_alignment_deviation"] = float(reg.layer_alignment_deviation)
            if getattr(reg, "local_contrast", -1) >= 0:
                sec_entry["local_contrast"] = float(reg.local_contrast)
            second_pass = {"regions": [sec_entry]}
        else:
            second_pass = None
        # Final policy — with or without second-pass evidence
        second_region = tool_result.region if tool_result is not None else None
        final = decide(first_pass, second_region, profile_name=profile_name)
    else:
        # Confident path — no agent, no second pass
        agent_ms = None
        second_pass_ms = None
        final = decide(first_pass, None, profile_name=profile_name)

    # --- Build result in exact shape from apps/web/src/lib/types.ts ---
    regions_json = []
    for r in first_pass.regions:
        regions_json.append({
            "x": int(r.x),
            "y": int(r.y),
            "w": int(r.w),
            "h": int(r.h),
            "evidence": {
                "edge_continuity": float(r.edge_continuity),
                "reference_similarity": float(r.reference_similarity),
                "layer_alignment_deviation": float(r.layer_alignment_deviation),
            }
        })

    result: dict = {
        "status": first_pass.status,
        "regions": regions_json,
        "evidence_gap": list(first_pass.evidence_gap),
        "final_decision": {
            "decision": final.decision,
            "confidence_band": final.confidence_band,
            "human_approval_required": bool(final.human_approval_required),
        }
    }
    if agent_call_dict is not None:
        result["agent_call"] = agent_call_dict
    if second_pass is not None:
        result["second_pass"] = second_pass

    # --- Timing instrumentation for Experiment D (COOL baseline comparison) ---
    total_ms = (time.perf_counter() - t_total_start) * 1000
    measurements = {
        "decode_ms": round(decode_ms, 2) if decode_ms is not None else None,
        "first_pass_ms": round(first_pass_ms, 2) if first_pass_ms is not None else None,
        "agent_ms": round(agent_ms, 2) if agent_ms is not None else None,
        "second_pass_ms": round(second_pass_ms, 2) if second_pass_ms is not None else None,
        "total_ms": round(total_ms, 2),
    }
    result["measurements"] = measurements
    # Structured log line (not print) — consumed by CloudWatch to compare COOL vs baseline runs
    try:
        logger.info(
            json.dumps(
                {
                    "event": "inspect",
                    "profile": profile_name,
                    "status": first_pass.status,
                    "decision": final.decision,
                    "agent_tool": agent_call_dict["tool"] if agent_call_dict else None,
                    "measurements": measurements,
                }
            )
        )
    except Exception:
        # Logging must never break the request
        pass

    job_id = uuid.uuid4().hex[:8]
    # Use JobStore abstraction — InMemory wraps JOBS dict, Dynamo writes to table. Never crash on store errors.
    try:
        store.save(job_id, result)
    except Exception as e:
        # Storage layer already logs, but ensure the request still succeeds (store is best-effort).
        import logging

        logging.getLogger(__name__).error(f"[inspect] store.save failed job_id={job_id}: {e}")
        # As a last resort, ensure the in-memory dict still has it so the immediate GET can succeed
        JOBS[job_id] = result

    return JSONResponse({"job_id": job_id})


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """
    Returns the stored InspectionResult for the given job_id.
    The JSON shape matches apps/web/src/lib/types.ts exactly — no wrapper.
    """
    try:
        result = store.get(job_id)
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"[get_job] store.get failed job_id={job_id}: {e}")
        result = None
    # Fallback to in-memory dict if store missed (e.g., Dynamo temporarily unavailable but JOBS has it)
    if result is None:
        result = JOBS.get(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(result)
