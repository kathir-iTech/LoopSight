"""
LoopSight v2 — FastAPI & MCP Active-Perception Inference Service.

Exposes:
  POST /inspect                  — Multipart inspection (water_turbidity_v1,
                                   structural_crack_metrology_v1, fdm_print_surface_v1)
  GET  /jobs/{job_id}            — Retrieve full InspectionResult with visual overlay
  GET  /version                  — Stack & OpenCV version telemetry
  GET  /health                   — Liveness probe
  GET  /mcp/tools                — Model Context Protocol (MCP) OpenCV tool discovery
  POST /mcp/call                 — Direct MCP tool execution over base64 or sample image
  GET  /samples                  — Catalog of generated synthetic benchmark samples
  POST /inspect/sample/{case_id} — Run the real OpenCV 5 + Agent pipeline on a benchmark sample
"""

from __future__ import annotations

import base64
import datetime
import json
import logging
import os
import platform
import hmac
import io
import threading
import hashlib
from dataclasses import asdict
from functools import wraps
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

def _load_dotenv():
    parents = Path(__file__).resolve().parents
    candidates = [
        *([parents[3] / ".env"] if len(parents) > 3 else []),
        Path.cwd() / ".env",
        *([parents[2] / ".env"] if len(parents) > 2 else []),
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

sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger(__name__)

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from cv.first_pass import run_first_pass, PROFILES  # type: ignore
from cv.tools import TOOL_REGISTRY  # type: ignore
from cv.policy import decide  # type: ignore
from agent.tool_selector import select_tool, ToolCall, MCP_TOOL_DESCRIPTORS, ALLOWED_TOOLS  # type: ignore
from storage import create_job_store, InMemoryJobStore  # type: ignore
import demo_golden  # type: ignore
from evidence import MEASUREMENT_CONTRACT
from capture_sessions import SqliteCaptureSessionStore, CaptureSessionError, frame_digest, validate_capture_pair
from cloud_storage import create_capture_store, StorageUnavailable
from request_limits import BodyLimitMiddleware
from evidence_bundle import build_evidence_bundle

app = FastAPI(title="LoopSight v2 Active-Perception Inference & MCP Server", version="0.2.0")
_request_slots = threading.BoundedSemaphore(4)

try:
    from mangum import Mangum  # type: ignore

    handler = Mangum(app)
except Exception:
    handler = None  # type: ignore

# Production-ready CORS: honors CORS_ORIGINS env var (comma-separated) while defaulting to * for public judge access
_cors_env = os.environ.get("CORS_ORIGINS", "*").strip()
_allow_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BodyLimitMiddleware)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    token = os.environ.get("LOOPSIGHT_API_TOKEN", "")
    if token and request.url.path not in {"/health", "/version"}:
        if not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            return JSONResponse({"detail": "backend authentication required"}, status_code=401)
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    limited = request.method == "POST"
    if limited and not _request_slots.acquire(blocking=False):
        return JSONResponse({"detail": "Inspection capacity is busy. Retry shortly."}, status_code=429,
                            headers={"Retry-After": "2"})
    try:
        response = await call_next(request)
    finally:
        if limited:
            _request_slots.release()
    response.headers["X-Request-ID"] = req_id
    return response


JOBS: Dict[str, dict] = {}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000  # 25 MP pixel-bomb guard
_work_slots = threading.BoundedSemaphore(int(os.environ.get("LOOPSIGHT_MAX_CONCURRENT_INSPECTIONS", "2")))
POLICY_SOURCES = {name: hashlib.sha256((Path(__file__).parent / "cv" / name).read_bytes()).hexdigest()
                  for name in ["first_pass.py", "policy.py", "tools.py"]}
POLICY_FINGERPRINT = hashlib.sha256(json.dumps({"source": POLICY_SOURCES, "upload_analysis_side_limit": 1024}, sort_keys=True).encode()).hexdigest()


def bounded_work(fn):
    @wraps(fn)
    def execute(*args, **kwargs):
        if not _work_slots.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="Inspection capacity is busy. Retry shortly.", headers={"Retry-After": "2"})
        try:
            return fn(*args, **kwargs)
        finally:
            _work_slots.release()
    return execute

store = create_job_store(JOBS)
capture_store = create_capture_store()


@app.exception_handler(StorageUnavailable)
async def storage_error(_request: Request, _error: StorageUnavailable):
    logger.error("durable evidence storage unavailable")
    return JSONResponse({"detail": "Evidence storage is unavailable. Retry the inspection."}, status_code=503)


@app.exception_handler(CaptureSessionError)
async def capture_session_error(_request: Request, error: CaptureSessionError):
    return JSONResponse({"detail": str(error)}, status_code=error.status_code)


def _decode_image(data: bytes) -> np.ndarray:
    """Decode raw image bytes (jpeg/png/webp) into a BGR numpy array via OpenCV
    with pixel-dimension cap protection."""
    if not data:
        raise ValueError("empty image file")
    try:
        with Image.open(io.BytesIO(data)) as header:
            if header.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("unsupported image format; use PNG, JPEG or WebP")
            w, h = header.size
            if w <= 0 or h <= 0 or w * h > MAX_IMAGE_PIXELS:
                raise ValueError("image dimensions exceed the maximum pixel budget")
            if min(w, h) < 64 or max(w, h) / min(w, h) > 8:
                raise ValueError("use an image at least 64 pixels per side with a practical target framing")
            header.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("could not decode image — unsupported format or corrupt data") from error
    nparr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image — unsupported format or corrupt data")
    h, w = img.shape[:2]
    if h * w > MAX_IMAGE_PIXELS:
        raise ValueError(f"image dimensions {w}x{h} exceed maximum pixel budget ({MAX_IMAGE_PIXELS} px)")
    if max(h, w) > 1024:
        scale = 1024.0 / float(max(h, w))
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def _render_diagnostic_overlay_data_url(
    frame: np.ndarray,
    profile_name: str,
    first_pass,
    tool_name: Optional[str],
    final_decision: str,
) -> Optional[str]:
    """Render an annotated OpenCV visual telemetry overlay (ROI bounding box,
    detected specular glare contours, vertical stratification lines, or
    crack skeleton overlay) as a compact base64 PNG data URL."""
    try:
        vis = frame.copy()
        if vis.ndim == 2:
            vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
        if max(vis.shape[:2]) > 768:
            scale = 768 / max(vis.shape[:2])
            vis = cv2.resize(vis, (max(1, round(vis.shape[1] * scale)), max(1, round(vis.shape[0] * scale))))
        h, w = vis.shape[:2]
        color_map = {
            "PASS": (248, 189, 56),   # cyan-blue BGR
            "REVIEW": (11, 158, 245), # amber BGR
            "FAIL": (68, 68, 239),    # red BGR
            "NO_PATTERN_DETECTED": (160, 140, 120),
        }
        box_color = color_map.get(final_decision, (248, 189, 56))

        # Highlight specular glare regions in magenta if present
        gray = cv2.cvtColor(vis, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(vis, cv2.COLOR_BGR2HSV)
        glare_mask = ((hsv[:, :, 2] >= 240) & (hsv[:, :, 1] <= 38)).astype(np.uint8) * 255
        if 0.01 * (h * w) <= np.count_nonzero(glare_mask) <= 0.65 * (h * w):
            contours, _ = cv2.findContours(glare_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(vis, contours, -1, (255, 80, 255), 2)

        # For structural crack profile, highlight detected fracture ridge in red
        if profile_name == "structural_crack_metrology_v1":
            smoothed = cv2.bilateralFilter(gray, 7, 50, 50)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            bh = cv2.morphologyEx(smoothed, cv2.MORPH_BLACKHAT, kernel)
            bh_max = float(np.max(bh)) if bh.size else 0.0
            if bh_max >= 18.0:
                _, mask = cv2.threshold(bh, max(28, int(bh_max * 0.42)), 255, cv2.THRESH_BINARY)
                vis[mask > 0] = (40, 40, 255)

        # For vertical stratification tool, draw 3-stratum dashed dividers
        if tool_name == "analyze_vertical_stratification":
            for y_div in (h // 3, (2 * h) // 3):
                cv2.line(vis, (4, y_div), (w - 4, y_div), (11, 158, 245), 1, cv2.LINE_AA)

        # Draw ROI frame & status tag
        cv2.rectangle(vis, (2, 2), (w - 3, h - 3), box_color, 2)
        label = f"{final_decision}" + (f" [{tool_name}]" if tool_name else " [PASS-1]")
        cv2.rectangle(vis, (4, 4), (min(w - 4, 12 + len(label) * 7), 22), (25, 18, 10), -1)
        cv2.putText(vis, label, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.40, box_color, 1, cv2.LINE_AA)

        ok, buf = cv2.imencode(".png", vis)
        if not ok:
            return None
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def _fixture_for_first_pass(first_pass) -> dict:
    """Deterministic active-perception policy mapping specific first-pass
    evidence gaps to the optimal OpenCV 5 second-look tool."""
    gap_str = " ".join(first_pass.evidence_gap).lower() if first_pass.evidence_gap else ""
    allowed = first_pass.allowed_tools or []

    # 0. Composite Confounders (both glare AND skew) -> Multi-Tool Active Perception DAG
    if ("composite" in gap_str or ("glare" in gap_str and "skew" in gap_str)) and "inpaint_specular_glare" in allowed and "rectify_perspective_homography" in allowed:
        return {
            "tool": "inpaint_specular_glare -> rectify_perspective_homography",
            "tool_chain": ["inpaint_specular_glare", "rectify_perspective_homography"],
            "arguments": {"radius": 5.0},
            "reason_code": "COMPOSITE_MULTI_CONFOUNDER_ACTIVE_PERCEPTION_DAG",
        }

    # 1. Specular glare confounder -> inpaint_specular_glare
    if "glare" in gap_str and "inpaint_specular_glare" in allowed:
        return {
            "tool": "inpaint_specular_glare",
            "arguments": {"radius": 5.0},
            "reason_code": "SPECULAR_GLASS_GLARE_CONFOUNDER",
        }

    # 2. Perspective skew confounder -> rectify_perspective_homography
    if ("skew" in gap_str or "homography" in gap_str) and "rectify_perspective_homography" in allowed:
        return {
            "tool": "rectify_perspective_homography",
            "arguments": {},
            "reason_code": "PERSPECTIVE_SKEW_RECTIFICATION",
        }

    # 3. Vertical turbidity stratification -> analyze_vertical_stratification
    if "stratification" in gap_str and "analyze_vertical_stratification" in allowed:
        return {
            "tool": "analyze_vertical_stratification",
            "arguments": {},
            "reason_code": "VERTICAL_SETTLING_STRATIFICATION",
        }

    # 4. Structural crack / shadow ambiguity -> skeletonize_crack_metrology
    if ("crack" in gap_str or "hairline" in gap_str or "skeleton" in gap_str) and "skeletonize_crack_metrology" in allowed:
        return {
            "tool": "skeletonize_crack_metrology",
            "arguments": {},
            "reason_code": "SHADOW_VS_FRACTURE_METROLOGY",
        }

    # 5. Water-turbidity: borderline pattern visibility -> different lighting (track_across_frames)
    if "pattern visibility" in gap_str or "borderline band" in gap_str:
        if "track_across_frames" in allowed:
            return {"tool": "track_across_frames", "arguments": {}, "reason_code": "BORDERLINE_PATTERN_VISIBILITY"}
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "BORDERLINE_PATTERN_VISIBILITY"}
        if "measure_edge_continuity" in allowed:
            return {"tool": "measure_edge_continuity", "arguments": {"low": 30, "high": 100}, "reason_code": "BORDERLINE_PATTERN_VISIBILITY"}

    # 6. Water: pattern not detected -> re-inspect
    if "pattern not detected" in gap_str or "reference pattern" in gap_str:
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "PATTERN_NOT_DETECTED"}
        if "track_across_frames" in allowed:
            return {"tool": "track_across_frames", "arguments": {}, "reason_code": "PATTERN_NOT_DETECTED"}

    # 7. Water: very low contrast -> try different lighting
    if "very low contrast" in gap_str:
        if "track_across_frames" in allowed:
            return {"tool": "track_across_frames", "arguments": {}, "reason_code": "LOW_CONTRAST_WATER"}
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "LOW_CONTRAST_WATER"}

    # 8. Low reference similarity (fdm)
    if "reference similarity" in gap_str:
        if "compare_to_reference" in allowed:
            return {"tool": "compare_to_reference", "arguments": {}, "reason_code": "LOW_REFERENCE_SIMILARITY"}
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "LOW_REFERENCE_SIMILARITY"}

    # 9. Low local contrast
    if "low local contrast" in gap_str or "illumination contrast" in gap_str:
        if "skeletonize_crack_metrology" in allowed and "illumination contrast" in gap_str:
            return {"tool": "skeletonize_crack_metrology", "arguments": {}, "reason_code": "LOW_SURFACE_CONTRAST"}
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "INSUFFICIENT_LOCAL_CONTRAST"}
        if "measure_edge_continuity" in allowed:
            return {"tool": "measure_edge_continuity", "arguments": {"low": 30, "high": 100}, "reason_code": "INSUFFICIENT_LOCAL_CONTRAST"}

    # 10. Ambiguous edge band (fdm)
    if "ambiguous" in gap_str or "edge continuity" in gap_str:
        if "measure_edge_continuity" in allowed:
            return {"tool": "measure_edge_continuity", "arguments": {"low": 30, "high": 100}, "reason_code": "AMBIGUOUS_EDGE_BAND"}
        if "reinspect_roi" in allowed:
            return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "AMBIGUOUS_EDGE_BAND"}

    if "reinspect_roi" in allowed:
        return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "DEFAULT_REINSPECT"}
    if "measure_edge_continuity" in allowed:
        return {"tool": "measure_edge_continuity", "arguments": {"low": 30, "high": 100}, "reason_code": "DEFAULT_EDGE_CHECK"}
    if "compare_to_reference" in allowed:
        return {"tool": "compare_to_reference", "arguments": {}, "reason_code": "DEFAULT_REFERENCE_CHECK"}
    for t in allowed:
        if t != "track_across_frames":
            return {"tool": t, "arguments": {}, "reason_code": "FALLBACK_DEFAULT"}
    if allowed:
        return {"tool": allowed[0], "arguments": {}, "reason_code": "FALLBACK_DEFAULT"}
    return {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "FALLBACK_NO_ALLOWED_TOOLS"}


def _run_tool(
    tool_call,
    frame: np.ndarray,
    reference: np.ndarray | None,
    roi: tuple[int, int, int, int],
    profile_name: str = "water_turbidity_v1",
):
    """Dispatch to the real TOOL_REGISTRY entry for the agent-selected tool."""
    tool_name = tool_call.tool
    args = tool_call.arguments or {}

    chain = getattr(tool_call, "tool_chain", [])
    if chain and len(chain) > 1:
        from cv.tools import execute_tool_chain
        return execute_tool_chain(chain, frame, roi, reference=reference, **args)

    if tool_name == "track_across_frames":
        raise ValueError("track_across_frames requires a second captured image")

    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        raise ValueError(f"tool '{tool_name}' not in registry")

    if tool_name == "reinspect_roi":
        scale = float(args.get("scale", 2.0))
        return fn(frame, reference, roi, scale=scale)
    elif tool_name == "compare_to_reference":
        if reference is None:
            fallback = TOOL_REGISTRY["reinspect_roi"]
            return fallback(frame, reference, roi, scale=2.0)
        return fn(frame, reference, roi)
    elif tool_name == "measure_edge_continuity":
        low = int(args.get("low", 30))
        high = int(args.get("high", 100))
        return fn(frame, roi, low=low, high=high)
    elif tool_name == "inpaint_specular_glare":
        radius = float(args.get("radius", 5.0))
        return fn(frame, roi, radius=radius)
    elif tool_name == "rectify_perspective_homography":
        return fn(frame, roi)
    elif tool_name == "analyze_vertical_stratification":
        return fn(frame, roi)
    elif tool_name == "skeletonize_crack_metrology":
        return fn(frame, roi)
    else:
        try:
            return fn(frame, reference, roi, **args)
        except TypeError:
            return fn(frame, roi, **args)


@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "loopsight-inference",
        "version": "0.2.0",
        "store": type(store).__name__,
        "mcp_enabled": True,
    }


@app.get("/health")
async def health_alt():
    return {"status": "ok"}


@app.get("/ready")
def readiness():
    # Probe actual read permissions without mutating evidence. A real upload smoke
    # is still required to verify writes and cross-instance behavior.
    store.get("0" * 32)
    try:
        capture_store.load("0" * 32)
    except CaptureSessionError as error:
        if error.status_code != 404:
            raise
    return {"status": "ready", "jobs": type(store).__name__, "captures": type(capture_store).__name__,
            "storage_write_verified": False}


BUILD_TIMESTAMP = datetime.datetime.now(datetime.timezone.utc).isoformat()
RUNTIME_INSTANCE_ID = uuid.uuid4().hex


@app.get("/version")
async def version():
    """Returns stack version evidence — used in technical report and by judges."""
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    return {
        "opencv_version": cv2.__version__,
        "measurement_contract": MEASUREMENT_CONTRACT,
        "policy_fingerprint": POLICY_FINGERPRINT,
        "python_version": platform.python_version(),
        "runtime_architecture": platform.machine(),
        "runtime_instance_id": RUNTIME_INSTANCE_ID,
        "instance_started_at": BUILD_TIMESTAMP,
        "profile_names": sorted(PROFILES.keys()),
        "allowed_tools": sorted(ALLOWED_TOOLS),
        "mcp_tools_count": len(MCP_TOOL_DESCRIPTORS),
        "gemini_model": gemini_model,
        "build_timestamp": BUILD_TIMESTAMP,
        "build_revision": os.environ.get("LOOPSIGHT_BUILD_REVISION", "unversioned-local"),
        "storage": {"jobs": type(store).__name__, "captures": type(capture_store).__name__,
                    "shared_across_instances": type(store).__name__ == "S3JobStore" and type(capture_store).__name__ == "S3CaptureSessionStore"},
    }


@app.get("/mcp/tools")
async def mcp_list_tools():
    """Model Context Protocol (MCP) tool discovery endpoint for agentic vision."""
    return {
        "protocol": "mcp/1.0",
        "server": "loopsight-opencv5-mcp",
        "opencv_version": cv2.__version__,
        "tools": MCP_TOOL_DESCRIPTORS,
    }


@app.post("/mcp/rpc")
async def mcp_json_rpc(request: Request):
    """Official Model Context Protocol (MCP) JSON-RPC 2.0 Server Endpoint.
    Allows external AI agent frameworks (Claude Desktop, Gemini agents, LangChain/LlamaIndex)
    to connect directly to LoopSight as an active-perception OpenCV 5 MCP Vision Server.

    Supported JSON-RPC 2.0 Methods:
      - 'initialize': Handshake returning server metadata and tool capabilities
      - 'ping': Liveness verification
      - 'tools/list': Returns all 8 OpenCV 5 active-perception tool descriptors
      - 'tools/call': Executes an OpenCV 5 tool on a sample or base64 image and returns telemetry
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON-RPC body")

    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": body.get("id") if isinstance(body, dict) else None,
                "error": {"code": -32600, "message": "Invalid Request: expected jsonrpc 2.0"},
            },
        )

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})
    if not isinstance(params, dict):
        return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                             "error": {"code": -32602, "message": "params must be an object"}})
    if "id" not in body:
        return Response(status_code=202)

    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "loopsight-opencv5-mcp",
                    "version": "0.2.0",
                    "description": "LoopSight OpenCV 5 Active-Perception & Metrology Engine",
                },
                "capabilities": {
                    "tools": {"listChanged": False},
                },
            },
        })

    elif method == "ping":
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {}})

    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOL_DESCRIPTORS},
        })

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(args, dict):
            return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                                 "error": {"code": -32602, "message": "arguments must be an object"}})
        if not isinstance(tool_name, str) or tool_name not in ALLOWED_TOOLS:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method/Tool not found: '{tool_name}'"},
                },
            )

        from agent.tool_selector import validate_tool_call, InvalidToolCallError
        tool_args = {key: value for key, value in args.items()
                     if key not in {"sample_id", "image_base64", "second_image_base64"}}
        try:
            validate_tool_call({"tool": tool_name, "arguments": tool_args, "reason_code": "MCP_CALL"})
        except InvalidToolCallError as e:
            return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                                 "error": {"code": -32602, "message": str(e)}})

        sample_id = args.get("sample_id", "water_glare_confounded")
        image_b64 = args.get("image_base64")
        if image_b64 is not None:
            try:
                if not isinstance(image_b64, str) or len(image_b64) > 4 * ((MAX_UPLOAD_BYTES + 2) // 3):
                    raise ValueError("encoded image exceeds upload limit")
                img_bytes = base64.b64decode(image_b64, validate=True)
                frame = await run_in_threadpool(_decode_image, img_bytes)
            except Exception as e:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"Error decoding image_base64: {e}"}], "isError": True},
                })
        else:
            try:
                frame, _, _ = _generate_sample_frames(sample_id)
            except (KeyError, TypeError):
                return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                                     "error": {"code": -32602, "message": "unknown sample_id"}})

        roi = (0, 0, frame.shape[1], frame.shape[0])
        fn = TOOL_REGISTRY[tool_name]
        try:
            if tool_name == "track_across_frames":
                second_b64 = args.get("second_image_base64")
                if not isinstance(second_b64, str) or not second_b64:
                    raise ValueError("track_across_frames requires second_image_base64")
                if len(second_b64) > 4 * ((MAX_UPLOAD_BYTES + 2) // 3):
                    raise ValueError("second image exceeds upload limit")
                second_bytes = base64.b64decode(second_b64, validate=True)
                second_frame = await run_in_threadpool(_decode_image, second_bytes)
                aligned_second, pair_report = validate_capture_pair(frame, second_frame)
                x, y, width, height = pair_report["crop"]
                tool_res = await run_in_threadpool(bounded_work(fn), [frame[y:y + height, x:x + width], aligned_second], (0, 0, width, height))
            elif tool_name in ("reinspect_roi", "compare_to_reference"):
                tool_res = await run_in_threadpool(bounded_work(fn), frame, None, roi)
            elif tool_name == "inpaint_specular_glare":
                tool_res = await run_in_threadpool(bounded_work(fn), frame, roi, radius=float(args.get("radius", 5.0)))
            elif tool_name == "skeletonize_crack_metrology":
                tool_res = await run_in_threadpool(bounded_work(fn), frame, roi)
            elif tool_name == "measure_edge_continuity":
                tool_res = await run_in_threadpool(bounded_work(fn), frame, roi, low=int(args.get("low", 30)), high=int(args.get("high", 100)))
            else:
                tool_res = await run_in_threadpool(bounded_work(fn), frame, roi)

            reg = tool_res.region
            telemetry = {
                "measurement_contract": MEASUREMENT_CONTRACT,
                "execution_mode": "live_opencv" if image_b64 is not None else "synthetic_benchmark",
                "measurement_basis": "uncalibrated_image_heuristics",
                "tool": tool_res.tool,
                "notes": tool_res.notes,
                "pattern_visibility": round(float(getattr(reg, "pattern_visibility", 0.0)), 4),
                "crack_width_px": round(float(getattr(reg, "crack_width_px", 0.0)), 3),
                "glare_ratio": round(float(getattr(reg, "glare_ratio", 0.0)), 4),
            }
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(telemetry, indent=2)}
                    ],
                    "isError": False,
                },
            })
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": f"Tool execution failed: {e}"}], "isError": True},
            })

    return JSONResponse(
        status_code=200,
        content={"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: '{method}'"}},
    )


# ---------------------------------------------------------------------------
# Generated synthetic regression scenarios (not physical validation)
# ---------------------------------------------------------------------------
SAMPLE_CATALOG = [
    {
        "id": "water_glare_confounded",
        "title": "Clear Water + Specular Glass Glare",
        "profile": "water_turbidity_v1",
        "description": "Generated glare over a checkerboard. Processing can improve image scores but does not supply a new observation; the result remains REVIEW.",
        "expected_flow": "UNCERTAIN -> same-image diagnosis -> REVIEW (new capture required)",
    },
    {
        "id": "water_stratified_sediment",
        "title": "Settled Sediment Stratification",
        "profile": "water_turbidity_v1",
        "description": "Upper water column appears clear while dense sediment settles in the bottom third (stratification_delta > 0.35). Agent invokes analyze_vertical_stratification to flag FAIL.",
        "expected_flow": "UNCERTAIN -> analyze_vertical_stratification -> FAIL",
    },
    {
        "id": "water_dual_lighting",
        "title": "Borderline Sample (Ambient -> Backlight Pair)",
        "profile": "water_turbidity_v1",
        "description": "Two-frame capture (ambient + backlight) where dim ambient lighting is UNCERTAIN and backlight transmission confirms clear pattern visibility via track_across_frames.",
        "expected_flow": "UNCERTAIN -> track_across_frames (2 frames) -> PASS",
    },
    {
        "id": "water_turbid_fail",
        "title": "High-Turbidity Colloidal Sample",
        "profile": "water_turbidity_v1",
        "description": "Heavily clouded water sample that strongly attenuates checkerboard contrast and sharpness (pattern_visibility <= 0.15). Immediate CONFIDENT_FAIL on Pass 1 without wasting agent compute.",
        "expected_flow": "CONFIDENT_FAIL -> FAIL (0 agent calls)",
    },
    {
        "id": "crack_shadow_confounded",
        "title": "Intact Concrete Wall + Cast Shadow",
        "profile": "structural_crack_metrology_v1",
        "description": "Generated shadow-like gradient. Illumination normalization reduces the crack-like line score; widths are in image pixels without physical scale.",
        "expected_flow": "UNCERTAIN -> skeletonize_crack_metrology -> PASS",
    },
    {
        "id": "crack_structural_fail",
        "title": "Synthetic Crack-Like Line",
        "profile": "structural_crack_metrology_v1",
        "description": "Generated line texture measured with a distance transform in analysis-image pixels. This is not a physical crack-width measurement.",
        "expected_flow": "CONFIDENT_FAIL -> FAIL (image-space screening)",
    },
]


def _generate_sample_frames(sample_id: str) -> tuple[np.ndarray, Optional[np.ndarray], str]:
    """Generate real BGR image arrays for the requested benchmark sample ID."""
    from sample_frames import (
        make_glare_confounded_water,
        make_stratified_turbid_water,
        make_backlit_recovery_pair,
        make_turbid_water,
        make_checkerboard,
        make_shadow_confounded_concrete,
        make_structural_crack,
    )

    if sample_id == "water_glare_confounded":
        return make_glare_confounded_water(), None, "water_turbidity_v1"
    if sample_id == "water_stratified_sediment":
        return make_stratified_turbid_water(), None, "water_turbidity_v1"
    if sample_id == "water_dual_lighting":
        f1, f2 = make_backlit_recovery_pair()
        return f1, f2, "water_turbidity_v1"
    if sample_id == "water_turbid_fail":
        return make_turbid_water(make_checkerboard(), blur_ks=15, alpha=0.45, beta=30), None, "water_turbidity_v1"
    if sample_id == "crack_shadow_confounded":
        return make_shadow_confounded_concrete(), None, "structural_crack_metrology_v1"
    if sample_id == "crack_structural_fail":
        return make_structural_crack(thickness_px=6), None, "structural_crack_metrology_v1"
    raise KeyError(f"Unknown sample_id: {sample_id}")


@app.get("/samples")
async def list_samples():
    """Return the generated synthetic benchmark samples for the 1-click Judge Test Bench."""
    return {"samples": SAMPLE_CATALOG}


@bounded_work
def _execute_inspection_pipeline(
    frame: np.ndarray,
    profile_name: str,
    reference: Optional[np.ndarray] = None,
    second_frame: Optional[np.ndarray] = None,
    first_lighting: str = "ambient",
    second_frame_lighting: str = "backlight",
    original_job_id: Optional[str] = None,
    decode_ms: float = 0.5,
    execution_mode: str = "live_opencv",
    first_capture_metadata: Optional[dict] = None,
) -> tuple[str, dict]:
    """Shared real OpenCV 5 + Agent + Policy execution pipeline used by both
    POST /inspect and POST /inspect/sample/{sample_id}."""
    t_total_start = time.perf_counter()
    first_pass_ms: Optional[float] = None
    agent_ms: Optional[float] = None
    second_pass_ms: Optional[float] = None

    h, w = frame.shape[:2]
    roi = (0, 0, w, h)

    first_capture_metadata = first_capture_metadata or {}
    first_frame_timestamp = first_capture_metadata.get("timestamp") or datetime.datetime.now(datetime.timezone.utc).isoformat()
    second_frame_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat() if second_frame is not None else None
    first_seq, second_seq = 1, 2
    pair_validation = None
    independent_capture_used = False

    t0 = time.perf_counter()
    first_pass = run_first_pass(frame, reference, [roi], profile_name=profile_name)
    first_pass_ms = (time.perf_counter() - t0) * 1000

    agent_call_dict = None
    second_pass = None
    tool_result = None
    tool_call = None
    frame_info_for_result = None

    if first_pass.status == "UNCERTAIN":
        t_agent = time.perf_counter()
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if second_frame is not None and profile_name == "water_turbidity_v1":
            tool_call = ToolCall("track_across_frames", {}, "NEW_CAPTURE_AVAILABLE", ["track_across_frames"])
            gemini_key = None
        elif gemini_key:
            tool_call = select_tool(first_pass, api_key=gemini_key)
        else:
            fixture = _fixture_for_first_pass(first_pass)
            tool_call = select_tool(first_pass, mock_fixture=fixture)
        agent_ms = (time.perf_counter() - t_agent) * 1000
        agent_call_dict = {
            "tool": tool_call.tool,
            "selector": ("deterministic_fallback" if tool_call.reason_code.startswith("FALLBACK_")
                         else "gemini" if gemini_key else "deterministic_policy"),
            "tool_chain": getattr(tool_call, "tool_chain", [tool_call.tool]),
            "reason_code": tool_call.reason_code,
        }

        t_sp = time.perf_counter()
        if second_frame is not None and profile_name == "water_turbidity_v1":
            aligned_second, pair_validation = validate_capture_pair(frame, second_frame)
            x, y, cw, ch = pair_validation["crop"]
            first_crop = frame[y:y + ch, x:x + cw]
            tool_result = TOOL_REGISTRY["track_across_frames"]([first_crop, aligned_second], (0, 0, cw, ch))
            independent_capture_used = True
            frame_info_for_result = [
                {"seq": 1, "timestamp": first_frame_timestamp, "lighting": first_lighting,
                 "sha256": frame_digest(frame), "sha256_basis": "decoded_analysis_pixels", "timestamp_source": "server_received"},
                {"seq": 2, "timestamp": second_frame_timestamp, "lighting": second_frame_lighting,
                 "sha256": frame_digest(second_frame), "sha256_basis": "decoded_analysis_pixels", "timestamp_source": "server_received"},
            ]
            second_quality = run_first_pass(aligned_second, None, [(0, 0, cw, ch)], profile_name=profile_name)
        elif tool_call.tool == "track_across_frames":
            # A requested recapture is a normal pending action, not a failed tool.
            tool_result = None
        else:
            try:
                tool_result = _run_tool(tool_call, frame, reference, roi, profile_name=profile_name)
            except Exception as error:
                logger.warning("inspection tool %s failed: %s", tool_call.tool, error)
                tool_result = None
        second_pass_ms = (time.perf_counter() - t_sp) * 1000

        if tool_result is not None:
            reg = tool_result.region
            sec_entry: dict = {"edge_continuity": float(reg.edge_continuity)}
            if getattr(reg, "reference_similarity", -1) >= 0:
                sec_entry["reference_similarity"] = float(reg.reference_similarity)
            if getattr(reg, "layer_alignment_deviation", -1) >= 0:
                sec_entry["layer_alignment_deviation"] = float(reg.layer_alignment_deviation)
            if getattr(reg, "local_contrast", -1) >= 0:
                sec_entry["local_contrast"] = float(reg.local_contrast)
            if getattr(reg, "pattern_visibility", 0) > 0 or getattr(reg, "pattern_sharpness", 0) > 0 or profile_name == "water_turbidity_v1":
                sec_entry["pattern_visibility"] = float(getattr(reg, "pattern_visibility", 0.0))
                sec_entry["pattern_sharpness"] = float(getattr(reg, "pattern_sharpness", 0.0))
                sec_entry["pattern_found"] = bool(getattr(reg, "pattern_found", False))
                sec_entry["glare_ratio"] = float(getattr(reg, "glare_ratio", 0.0))
                sec_entry["stratification_delta"] = float(getattr(reg, "stratification_delta", 0.0))
            if profile_name == "structural_crack_metrology_v1" or getattr(reg, "crack_width_px", 0.0) > 0:
                sec_entry["crack_width_px"] = float(getattr(reg, "crack_width_px", 0.0))
                sec_entry["crack_length_px"] = float(getattr(reg, "crack_length_px", 0.0))
                sec_entry["crack_severity_score"] = float(getattr(reg, "crack_severity_score", 0.0))
            second_pass = {"regions": [sec_entry], "notes": tool_result.notes,
                           "evidence_source": "new_capture" if independent_capture_used else "same_image_processing"}
            if pair_validation:
                second_pass["crop_in_first_frame"] = pair_validation["crop"]
        else:
            second_pass = None

        second_region = tool_result.region if tool_result is not None else None
        final = decide(first_pass, second_region, profile_name=profile_name,
                       independent_capture=independent_capture_used)
        if independent_capture_used and second_quality.status == "UNCERTAIN":
            final = decide(first_pass, None, profile_name=profile_name)
            final.reasoning = ["new capture remains ambiguous: " + "; ".join(second_quality.evidence_gap)]
    else:
        agent_ms = None
        second_pass_ms = None
        final = decide(first_pass, None, profile_name=profile_name)

    regions_json = []
    for r in first_pass.regions:
        ev: dict = {
            "edge_continuity": float(r.edge_continuity),
            "reference_similarity": float(r.reference_similarity),
            "layer_alignment_deviation": float(r.layer_alignment_deviation),
            "local_contrast": float(getattr(r, "local_contrast", 0.0)),
            "glare_ratio": float(getattr(r, "glare_ratio", 0.0)),
            "skew_deg": float(getattr(r, "skew_deg", 0.0)),
            "stratification_delta": float(getattr(r, "stratification_delta", 0.0)),
            "detection_method": str(getattr(r, "detection_method", "full_frame")),
        }
        pv = getattr(r, "pattern_visibility", 0.0) or 0.0
        if profile_name == "water_turbidity_v1" or pv > 0 or getattr(r, "pattern_found", False):
            ev["pattern_visibility"] = float(pv)
            ev["pattern_sharpness"] = float(getattr(r, "pattern_sharpness", 0.0))
            ev["pattern_found"] = bool(getattr(r, "pattern_found", False))
        if profile_name == "structural_crack_metrology_v1" or getattr(r, "crack_severity_score", 0.0) > 0:
            ev["crack_width_px"] = float(getattr(r, "crack_width_px", 0.0))
            ev["crack_length_px"] = float(getattr(r, "crack_length_px", 0.0))
            ev["crack_severity_score"] = float(getattr(r, "crack_severity_score", 0.0))
        regions_json.append({
            "x": int(r.x),
            "y": int(r.y),
            "w": int(r.w),
            "h": int(r.h),
            "evidence": ev,
        })

    overlay_url = _render_diagnostic_overlay_data_url(
        frame,
        profile_name,
        first_pass,
        agent_call_dict["tool"] if agent_call_dict else None,
        final.decision,
    )

    result: dict = {
        "measurement_contract": MEASUREMENT_CONTRACT,
        "policy_snapshot": {"fingerprint": POLICY_FINGERPRINT, "source_sha256": POLICY_SOURCES,
                            "thresholds": asdict(PROFILES[profile_name]), "upload_analysis_side_limit": 1024},
        "provenance": {
            "execution_mode": execution_mode,
            "runtime_instance_id": RUNTIME_INSTANCE_ID,
            "opencv_version": cv2.__version__,
            "measurement_basis": "uncalibrated_image_heuristics",
        },
        "status": first_pass.status,
        "inspection_profile": profile_name,
        "regions": regions_json,
        "evidence_gap": list(first_pass.evidence_gap),
        "final_decision": {
            "decision": final.decision,
            "confidence_band": final.confidence_band,
            "human_approval_required": bool(final.human_approval_required),
            "reasoning": list(final.reasoning),
        },
    }
    if overlay_url:
        result["overlay_data_url"] = overlay_url
    if agent_call_dict is not None:
        result["agent_call"] = agent_call_dict
    if second_pass is not None:
        result["second_pass"] = second_pass

    if frame_info_for_result is not None:
        result["frames"] = frame_info_for_result
        result["frame_info"] = (
            f"LOOK 1: {frame_info_for_result[0]['timestamp']} frame #{frame_info_for_result[0]['seq']} "
            f"({frame_info_for_result[0]['lighting']}) -> LOOK 2: {frame_info_for_result[1]['timestamp']} "
            f"frame #{frame_info_for_result[1]['seq']} ({frame_info_for_result[1]['lighting']})"
        )
    else:
        result["frames"] = [{"seq": first_seq, "timestamp": first_frame_timestamp, "lighting": first_lighting,
                             "sha256": frame_digest(frame), "sha256_basis": "decoded_analysis_pixels", "timestamp_source": "server_received"}]
        result["frame_info"] = f"LOOK 1: {first_frame_timestamp} frame #{first_seq} ({first_lighting})"

    total_ms = (time.perf_counter() - t_total_start) * 1000
    measurements = {
        "decode_ms": round(decode_ms, 2) if decode_ms is not None else None,
        "first_pass_ms": round(first_pass_ms, 2) if first_pass_ms is not None else None,
        "agent_ms": round(agent_ms, 2) if agent_ms is not None else None,
        "second_pass_ms": round(second_pass_ms, 2) if second_pass_ms is not None else None,
        "total_ms": round(total_ms, 2),
    }
    result["measurements"] = measurements

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
        pass

    job_id = uuid.uuid4().hex
    can_recapture = (execution_mode == "live_opencv" and profile_name == "water_turbidity_v1"
                     and first_pass.status == "UNCERTAIN" and final.decision == "REVIEW"
                     and any(r.pattern_found for r in first_pass.regions) and not independent_capture_used)
    instructions = ["Keep the same sample, checkerboard and camera framing.",
                    "Change the lighting: add backlight or move the light away from glare.",
                    "Take a new photo without filtering or reusing the first image."]
    result["capture_session"] = {
        "state": "awaiting_capture" if can_recapture else "needs_review" if final.decision == "REVIEW" else "complete",
        "can_recapture": can_recapture,
        "instructions": instructions if can_recapture else [],
        "parent_job_id": original_job_id,
    }
    if execution_mode != "demo_fixture":
        try:
            expires_at = capture_store.save(job_id, frame, reference, {
                "profile": profile_name, "timestamp": first_frame_timestamp, "lighting": first_lighting,
                "execution_mode": execution_mode,
                "can_recapture": can_recapture,
                "policy_fingerprint": POLICY_FINGERPRINT,
            }, second_frame=second_frame if independent_capture_used else None)
        except (sqlite3.Error, OSError) as error:
            logger.error("capture persistence failed: %s", type(error).__name__)
            raise CaptureSessionError("capture storage is unavailable; retry the inspection", 503) from error
        result["capture_session"]["expires_at"] = datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc).isoformat()
        result["capture_session"]["evidence_available"] = True
    result["acquisition"] = {
        "observations_received": 2 if second_frame is not None else 1,
        "observations_used": 2 if independent_capture_used else 1,
        "new_capture_used": independent_capture_used,
        "parent_job_id": original_job_id,
        "pair_validation": pair_validation,
    }

    try:
        store.save(job_id, result)
    except (StorageUnavailable, CaptureSessionError):
        raise
    except Exception as error:
        raise StorageUnavailable("inspection result could not be saved") from error

    return job_id, result


@app.post("/inspect/sample/{sample_id}")
def inspect_sample(sample_id: str):
    """Run the real OpenCV 5 + Agent pipeline on one of the generated synthetic
    benchmark samples and return {job_id, sample_id, profile}."""
    try:
        frame1, frame2, profile_name = _generate_sample_frames(sample_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown benchmark sample_id '{sample_id}'")

    job_id, _ = _execute_inspection_pipeline(
        frame=frame1,
        profile_name=profile_name,
        second_frame=frame2,
        first_lighting="ambient",
        second_frame_lighting="backlight",
        decode_ms=0.4,
        execution_mode="synthetic_benchmark",
    )
    return JSONResponse({"job_id": job_id, "sample_id": sample_id, "inspection_profile": profile_name})


@app.post("/inspect")
async def inspect(request: Request):
    """Multipart form endpoint for image inspection across all profiles."""
    form = await request.form(max_files=3, max_fields=20)
    file_fields = {"image", "file", "reference_image", "reference", "referenceImage",
                   "image2", "second_image", "lighting_image2", "secondImage"}
    for name, value in form.multi_items():
        if isinstance(value, UploadFile) and name not in file_fields:
            raise HTTPException(status_code=400, detail=f"field '{name}' must be text")
        if name in file_fields and not isinstance(value, UploadFile):
            raise HTTPException(status_code=400, detail=f"field '{name}' must be an image file")

    golden = demo_golden.resolve_golden_from_request(form)
    if golden is not None:
        golden = {**golden, "provenance": {"execution_mode": "demo_fixture"},
                  "measurement_contract": MEASUREMENT_CONTRACT}
        golden_job_id = uuid.uuid4().hex
        store.save(golden_job_id, golden)
        return JSONResponse({"job_id": golden_job_id})

    # Also allow running a named benchmark sample via form field sample_id
    sample_id_field = form.get("sample_id")
    if sample_id_field and not hasattr(sample_id_field, "read"):
        sid = str(sample_id_field).strip()
        if sid:
            try:
                frame1, frame2, prof = _generate_sample_frames(sid)
                job_id, _ = await run_in_threadpool(_execute_inspection_pipeline,
                    frame=frame1,
                    profile_name=prof,
                    second_frame=frame2,
                    decode_ms=0.4,
                    execution_mode="synthetic_benchmark",
                )
                return JSONResponse({"job_id": job_id})
            except KeyError:
                raise HTTPException(status_code=400, detail=f"unknown sample_id '{sid}'")

    upload = form.get("image")
    if upload is None:
        upload = form.get("file")

    if upload is None:
        raise HTTPException(status_code=400, detail="missing image file: expected multipart field 'image'")

    profile_name = form.get("inspection_profile") or "water_turbidity_v1"
    if hasattr(profile_name, "read"):
        profile_name = (await profile_name.read()).decode("utf-8")  # type: ignore
    profile_name = str(profile_name).strip() or "water_turbidity_v1"

    if profile_name not in PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"unknown inspection_profile '{profile_name}'. valid: {sorted(PROFILES.keys())}",
        )

    try:
        if hasattr(upload, "read"):
            data = await upload.read()  # type: ignore
        else:
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

    t0 = time.perf_counter()
    try:
        frame = await run_in_threadpool(_decode_image, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    decode_ms = (time.perf_counter() - t0) * 1000

    reference = None
    ref_upload = form.get("reference_image") or form.get("reference") or form.get("referenceImage")
    if ref_upload is not None:
        try:
            ref_data = await ref_upload.read()  # type: ignore
            if len(ref_data) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="reference image exceeds the upload limit")
            reference = await run_in_threadpool(_decode_image, ref_data)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"invalid reference image: {error}") from error

    second_frame: Optional[np.ndarray] = None
    second_upload = form.get("image2") or form.get("second_image") or form.get("lighting_image2") or form.get("secondImage")
    lighting_field = form.get("lighting") or form.get("lighting1") or form.get("image_lighting")
    second_lighting_field = form.get("lighting2") or form.get("image2_lighting") or form.get("second_lighting") or form.get("secondImageLighting")
    first_lighting = str(lighting_field).strip() if lighting_field and not hasattr(lighting_field, "read") else "ambient"
    if not first_lighting or hasattr(first_lighting, "read"):
        first_lighting = "ambient"
    requested_second_lighting = (
        str(second_lighting_field).strip()
        if second_lighting_field and not hasattr(second_lighting_field, "read")
        else "backlight"
    )
    if not requested_second_lighting or hasattr(requested_second_lighting, "read"):
        requested_second_lighting = "backlight"

    if second_upload is not None and hasattr(second_upload, "read"):
        sec_data = await second_upload.read()
        if len(sec_data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="second image exceeds the upload limit")
        try:
            second_frame = await run_in_threadpool(_decode_image, sec_data)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"invalid second image: {error}") from error

    original_job_id = form.get("original_job_id") or form.get("previous_job_id") or form.get("job_id")
    if original_job_id and hasattr(original_job_id, "read"):
        try:
            original_job_id = (await original_job_id.read()).decode("utf-8")  # type: ignore
        except Exception:
            original_job_id = None
    if original_job_id:
        original_job_id = str(original_job_id).strip()

    first_capture_metadata = None
    if original_job_id:
        if second_upload is not None:
            raise HTTPException(status_code=400, detail="follow-up requests accept one new image")
        try:
            session = await run_in_threadpool(capture_store.load, original_job_id)
        except (sqlite3.Error, OSError) as error:
            raise CaptureSessionError("capture storage is unavailable", 503) from error
        if profile_name != session.metadata["profile"]:
            raise CaptureSessionError("the inspection profile cannot change during recapture", 409)
        if session.metadata.get("policy_fingerprint") != POLICY_FINGERPRINT:
            raise CaptureSessionError("the inspection policy changed; start a new inspection", 409)
        if not session.metadata.get("can_recapture"):
            raise CaptureSessionError("this inspection already used its follow-up capture; start a new inspection", 409)
        if session.metadata["lighting"] == requested_second_lighting:
            raise CaptureSessionError("use different lighting for the new capture")
        second_frame = frame
        frame = session.frame
        reference = session.reference
        first_lighting = session.metadata["lighting"]
        first_capture_metadata = {"timestamp": session.metadata["timestamp"]}

    if second_frame is not None and (first_lighting == requested_second_lighting):
        raise CaptureSessionError("declare a different lighting condition for the second capture")
    allowed_lighting = {"ambient", "backlight", "flash", "side_light"}
    if first_lighting not in allowed_lighting or requested_second_lighting not in allowed_lighting:
        raise CaptureSessionError("unsupported lighting condition")

    job_id, _ = await run_in_threadpool(_execute_inspection_pipeline,
        frame=frame,
        profile_name=profile_name,
        reference=reference,
        second_frame=second_frame,
        first_lighting=first_lighting,
        second_frame_lighting=requested_second_lighting,
        original_job_id=original_job_id,
        decode_ms=decode_ms,
        first_capture_metadata=first_capture_metadata,
    )
    return JSONResponse({"job_id": job_id})


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Returns the stored InspectionResult for the given job_id."""
    try:
        result = store.get(job_id)
    except (StorageUnavailable, CaptureSessionError):
        raise
    except Exception as error:
        raise StorageUnavailable("inspection result could not be retrieved") from error
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(result)


@app.get("/jobs/{job_id}/captures/{index}")
def get_capture(job_id: str, index: int):
    """Return a retained analysis-space capture; expired evidence is never substituted."""
    if index not in (0, 1):
        raise HTTPException(status_code=404, detail="capture not found")
    try:
        session = capture_store.load(job_id)
    except (sqlite3.Error, OSError) as error:
        raise CaptureSessionError("capture storage is unavailable", 503) from error
    frame = session.frame if index == 0 else session.second_frame
    if frame is None:
        raise HTTPException(status_code=404, detail="capture not found")
    ok, encoded = cv2.imencode(".png", frame)
    if not ok:
        raise CaptureSessionError("could not render the retained capture", 503)
    return Response(encoded.tobytes(), media_type="image/png", headers={"Cache-Control": "private, no-store"})


@app.get("/jobs/{job_id}/evidence")
def export_evidence(job_id: str):
    result = get_job(job_id)
    session = capture_store.load(job_id)
    data = build_evidence_bundle({**json.loads(result.body), "job_id": job_id}, session)
    if len(data) > 4_000_000:
        raise HTTPException(status_code=413, detail="This bundle exceeds the web download budget. Download JSON and individual capture images instead.")
    return Response(data, media_type="application/zip", headers={"Cache-Control": "private, no-store",
                    "Content-Disposition": 'attachment; filename="loopsight-evidence.zip"'})
