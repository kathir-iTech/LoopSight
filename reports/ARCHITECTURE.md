# LoopSight — System Architecture

> **Purpose:** Judge-verifiable map of the complete system, per `LoopSight_Project_Spec.md` Section 10 and `reports/SUBMISSION_CHECKLIST.md` §3.
> All file paths are repo-relative and verifiable via `git ls-files` or direct read. This document must match `services/reports/technical_report.md` §2 exactly — any drift is a review flag.

---

## 1. Full ASCII Diagram

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                        BROWSER (phone / desktop)                        │
 │   • 320px mobile-first, Inter font, drag-and-drop, camera capture       │
 │   • glassmorphism cards, Framer Motion page transitions + 200ms stagger │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │  https://<vercel-url>
                                │  FormData { image: File, reference_image?: File }
                                │  or { demo_case: "uncertain" | "confident_pass" | "confident_fail" }
                                ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                     VERCEL — Next.js 15 (App Router)                     │
 │                                                                         │
 │  apps/web/src/app/page.tsx         apps/web/src/app/job/[id]/page.tsx  │
 │  ┌──────────────────────────┐       ┌──────────────────────────────┐    │
 │  │  Upload card              │       │  Evidence-trace viewer        │    │
 │  │  • drag-over highlight    │       │  • polling GET /api/jobs/[id] │    │
 │  │  • preview thumbnail      │       │    every 1.5s until not       │    │
 │  │  • file info (name/size)  │       │    "processing" (30s timeout) │    │
 │  │  • reference slot (opt)   │       │  • staggered reveal (200ms)   │    │
 │  │  • Inspect (indigo)       │       │  • 4 sections + connectors    │    │
 │  │  • Try demo case (ghost)  │       │  • Copy JSON / Share / PDF    │    │
 │  │  • history (localStorage) │       │  • timings + raw JSON         │    │
 │  └──────────────┬───────────┘       └──────────────┬───────────────┘    │
 │                 │                                   │                    │
 │  apps/web/src/app/api/inspect/route.ts             │                    │
 │  apps/web/src/app/api/jobs/[id]/route.ts           │                    │
 │  ┌──────────────────────────────────────────────────┴─────────────┐    │
 │  │  /api routes                                                     │    │
 │  │  • inject inspection_profile (default fdm_print_surface_v1)      │    │
 │  │  • forward DEMO_MODE / FORCE_AMBIGUOUS / demo_case               │    │
 │  │  • fetch(INFERENCE_API_URL + "/inspect")                         │    │
 │  │  • fallback: fixtureForFileBytes (FNV-1a hash) when backend down │    │
 │  └──────────────────────────────┬───────────────────────────────────┘    │
 └───────────────────────────────┬─────────────────────────────────────────┘
                                 │  https://<lambda-url>/inspect  (HTTP, multipart)
                                 │  INFERENCE_API_URL env var
                                 ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                AWS LAMBDA — FastAPI (Mangum adapter)                     │
 │                services/inference/main.py  (FastAPI app, handler)       │
 │                                                                         │
 │  GET  /              health {status, service, jobs, store}              │
 │  GET  /health        health {status: ok}                                │
 │  GET  /version       {opencv_version, python_version, profile_names,    │
 │                       gemini_model, build_timestamp}  ← Phase 6         │
 │  POST /inspect       multipart {image,file}, reference_image?,          │
 │                       inspection_profile, demo_case?                    │
 │   └─► _decode_image(data: bytes) → np.ndarray BGR (cv2.imdecode)        │
 │   └─► (optional) _decode_image(reference_image) → np.ndarray | None     │
 │   └─► demo_golden.resolve_golden_from_request() if DEMO_MODE=golden     │
 │   └─► run_first_pass(frame, reference, [roi], profile_name)             │
 │        │                                                                 │
 │        ├─ CONFIDENT_* ─► decide(first_pass, None)                        │
 │        └─ UNCERTAIN ─► select_tool(first_pass, api_key|mock_fixture)    │
 │                         │  call_gemini() timeout 15s, whitelist guard    │
 │                         ▼                                                │
 │                      _run_tool(tool_call, frame, reference, roi)        │
 │                         │  TOOL_REGISTRY dispatch                       │
 │                         ▼                                                │
 │                      decide(first_pass, second_pass_region)              │
 │                         ↓                                                │
 │                      {status, regions, evidence_gap, agent_call?,       │
 │                       second_pass?, final_decision, measurements}        │
 │   └─► store.save(job_id, result)  ─►  DynamoDB or InMemory (see below) │
 │   └─► return {job_id}                                                   │
 │  GET  /jobs/{job_id}  ─► store.get(job_id) → InspectionResult JSON      │
 │                                                                         │
 └───────────────┬───────────────────────────────────┬─────────────────────┘
                 │                                   │
                 ▼                                   ▼
 ┌──────────────────────────┐        ┌──────────────────────────────┐
 │  cv/first_pass.py         │        │  cv/tools.py                  │
 │  • InspectionProfile     │        │  • reinspect_roi(frame,ref,  │
 │    (fail=0.05 pass=0.20 │        │    roi, scale=2.0) → upsamp  │
 │     contrast=0.10 floor │        │  • compare_to_reference       │
 │     =0.40 interim)       │        │  • measure_edge_continuity  │
 │  • measure_region()     │        │  • track_across_frames      │
 │  • score_evidence()     │        │  • TOOL_REGISTRY             │
 │  • run_first_pass()     │        │                               │
 └──────────────┬──────────┘        └──────────┬───────────────────┘
                │                               │
                ▼                               │
 ┌──────────────────────────┐                  │
 │  agent/tool_selector.py   │◄─────────────────┘
 │  • validate_tool_call()  │   (tool choice feeds back into tools)
 │  • _build_prompt()       │
 │  • call_gemini()          │
 │  • select_tool()          │
 └──────────────┬──────────┘
                │
                ▼
 ┌──────────────────────────┐
 │  cv/policy.py             │
 │  • decide()               │
 │    CONFIDENT_PASS → PASS  │
 │    CONFIDENT_FAIL → FAIL  │
 │    UNCERTAIN+None → REVIEW│
 │    UNCERTAIN+evidence →   │
 │      ec≥pass→PASS         │
 │      ec≤fail→FAIL         │
 │      else → REVIEW        │
 └──────────────┬──────────┘
                │
                ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                           STORAGE & OBSERVABILITY                       │
 │                                                                         │
 │  services/inference/storage.py                                          │
 │  ┌────────────────────────────────┐  ┌──────────────────────────────┐  │
 │  │  InMemoryJobStore (default)    │  │  DynamoJobStore (boto3)       │  │
 │  │  wraps JOBS: Dict[str, dict]   │  │  when AWS creds resolvable    │  │
 │  │  len() cheap, jobs=count       │  │  Scan avoided, jobs=0 (cheap) │  │
 │  └──────────────┬─────────────────┘  └──────────┬───────────────────┘  │
 │                 │                               │                       │
 │                 ▼                               ▼                       │
 │         ┌───────────────┐               ┌───────────────┐              │
 │         │   DynamoDB    │               │   S3 (future) │              │
 │         │  job_id →     │               │ evidence imgs │              │
 │         │  InspectionResult │           │ + artifacts   │              │
 │         └───────┬───────┘               └───────┬───────┘              │
 │                 │                               │                       │
 │                 └───────────────┬───────────────┘                       │
 │                                 ▼                                       │
 │                     CloudWatch (structured JSON)                        │
 │  logger.info(json.dumps({event:"inspect", profile, status, decision,   │
 │                         agent_tool, measurements:{decode_ms,            │
 │                         first_pass_ms, agent_ms, second_pass_ms,        │
 │                         total_ms}}))                                    │
 └─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                   Browser renders Evidence Trace
                   (Perception → Agent → New Evidence → Decision)
```

---

## 2. Data Flow Table (what goes in each hop, what comes out)

| Hop | In | Out | File / Function |
|-----|----|----|-----------------|
| **Browser → Next.js** | `FormData {image: File, reference_image?: File}` plus `inspection_profile` default `fdm_print_surface_v1` | `POST /api/inspect` multipart | `apps/web/src/app/page.tsx:handleSubmit()` |
| **Next.js API → Inference** | Same `FormData` (plus `demo_case` if Try demo case or `DEMO_MODE=golden`) | `fetch(INFERENCE_API_URL + "/inspect", {method:"POST", body:formData})` | `apps/web/src/app/api/inspect/route.ts:4` |
| **FastAPI `POST /inspect`** | Multipart bytes, `inspection_profile`, optional `reference_image` | Decoded `frame: np.ndarray` BGR + `reference: np.ndarray | None` via `_decode_image` | `services/inference/main.py:245,117` |
| **First pass** | `frame`, `reference`, `[roi=(0,0,w,h)]`, `profile_name` | `FirstPassResult {status, regions: [RegionEvidence], evidence_gap, allowed_tools}` | `cv/first_pass.py:198 run_first_pass` |
| **Evidence-gap gate** | `FirstPassResult.status` | Branch CONFIDENT→policy, UNCERTAIN→agent | `main.py:362 if first_pass.status == "UNCERTAIN"` |
| **Agent tool selection** | `FirstPassResult {evidence_gap, regions}` | `ToolCall {tool, arguments, reason_code}` (whitelist-validated, fallback on invalid/429/timeout) | `agent/tool_selector.py:138 select_tool` |
| **Tool execution** | `frame`, `reference`, `roi`, `tool_call` | `ToolResult {tool, region: RegionEvidence, notes}` — materially different observation | `cv/tools.py:30,51,60,80` + `main.py:185 _run_tool` |
| **Final policy** | `FirstPassResult` + `second_pass_region: RegionEvidence | None` | `FinalDecision {decision (PASS/REVIEW/FAIL), confidence_band, human_approval_required, reasoning}` | `cv/policy.py:26 decide` |
| **Storage** | `InspectionResult {status, regions, evidence_gap, agent_call?, second_pass?, final_decision, measurements}` | `store.save(job_id, result)` → `JOBS dict` or DynamoDB; return `{job_id}` | `main.py:451 store.save` + `storage.py: create_job_store` |
| **Polling** | `GET /jobs/{job_id}` every 1.5s until `status != "processing"` (30s timeout) | `InspectionResult` JSON or `{error:"Job not found" , status:404}` | `apps/web/src/app/job/[id]/page.tsx:58` + `main.py:466 get_job` |
| **UI render** | `InspectionResult` JSON | Staggered cards (Perception → Agent → New Evidence → Decision), timings, copy/share/PDF | `apps/web/src/app/job/[id]/page.tsx:200` |
| **Version / health** | `GET /version` | `{opencv_version, python_version, profile_names, gemini_model, build_timestamp}` | `main.py:248 version` |
| **Logs** | Every `POST /inspect` | Structured JSON to stdout → CloudWatch | `main.py:435 logger.info` |

---

## 3. Component Responsibility Table (what each file owns, what it deliberately does NOT do)

| Component | File | Owns | Deliberately NOT |
|-----------|------|------|-------------------|
| **Inference entry** | `services/inference/main.py` | FastAPI routes, `MAX_UPLOAD_BYTES=10MiB` validation (413), `inspection_profile` dispatch, `reference_image` decode, golden fallback, timing (`decode_ms`…`total_ms`), `Mangum` Lambda adapter, CORS, `JOBS` backing dict | Measurement (delegates to `cv/`); tool choice (to `agent/`); verdict (to `cv/policy.py`) |
| **First pass** | `services/inference/cv/first_pass.py` | `InspectionProfile` (interim fail=0.05/pass=0.20/contrast=0.10/floor=0.40), `measure_region` (Canny 50/150, equalizeHist+absdiff, findContours, local_contrast), `score_evidence`, `run_first_pass`, logs `cv2.__version__` | Final verdict; agent |
| **Tools** | `services/inference/cv/tools.py` | `reinspect_roi` (upsample 2× INTER_CUBIC), `compare_to_reference`, `measure_edge_continuity` (low=30 high=100), `track_across_frames` (persistence std), `TOOL_REGISTRY` | Freshness enforcement (capture layer); policy |
| **Policy** | `services/inference/cv/policy.py` | `FinalDecision` + `decide()` 30-line deterministic policy | Any model call |
| **Agent** | `services/inference/agent/tool_selector.py` | `validate_tool_call` (second whitelist), `_build_prompt`, `call_gemini` (gemini-3.6-flash + fallbacks, 15s timeout), `select_tool` with fallback `FALLBACK_AFTER_*` | Measurement |
| **Storage** | `services/inference/storage.py` | `JobStore`, `InMemoryJobStore`, `DynamoJobStore` (boto3 only if creds resolvable) | Business logic |
| **Golden fallback** | `services/inference/demo_golden.py` | `GOLDEN_RESULTS` (3 fixtures), `load_golden`, `resolve_golden_from_request` when `DEMO_MODE=golden` | Real CV |
| **Calibration** | `services/inference/scripts/calibrate_thresholds.py` | `calibrate`, `compute_table`, `suggest_thresholds`, `print_report` — data-driven thresholds from `data/self_captured/` | Runtime |
| **Experiments** | `services/inference/scripts/run_experiments.py` | `run_all`, `print_report`, A/B/B2/C, `conditional_benefit`, B2 per-case hash | Real dataset |
| **Upload UI** | `apps/web/src/app/page.tsx` | Drag-and-drop, camera, file info, reference slot, Inspect/Try demo, pulsing indicator, feature cards, localStorage history (last 5), glassmorphism, Framer Motion | Inference |
| **Trace UI** | `apps/web/src/app/job/[id]/page.tsx` | Staggered reveal, metric grids, amber evidence-gap, agent decision node + connector, second-pass grid, PASS/REVIEW/FAIL card, Copy/Share/PDF (jsPDF), timings, polling 1.5s/30s, history counter, conditional ref-similarity | Measurement |
| **API proxy (inspect)** | `apps/web/src/app/api/inspect/route.ts` | Forwards FormData to `INFERENCE_API_URL`, injects `inspection_profile`, demo-case pass-through, FNV-1a `fixtureForFileBytes` fallback when backend down | CV |
| **API proxy (jobs)** | `apps/web/src/app/api/jobs/[id]/route.ts` | Proxies `GET /jobs/{id}` with `cache:no-store`, falls back to `getJob` in-memory | Storage |
| **Types** | `apps/web/src/lib/types.ts` | `InspectionResult`, `RegionEvidence`, `Measurements` exact shape of API | — |
| **History** | `apps/web/src/lib/history.ts` | `loadHistory`, `saveToHistory`, `clearHistory` (key `loopsight_history`, max 20, show 5) | Backend |
| **404** | `apps/web/src/app/not-found.tsx` | Dark on-brand 404 (SearchX, Back to inspection) | — |

---

## 4. What's Live Now vs. What Needs AWS to Be Real

| Layer | Live Now (verified locally 2026-09-04) | Needs AWS to be judge-accessible |
|-------|----------------------------------------|-----------------------------------|
| **CV pipeline** | ✅ `cv/first_pass.py`, `cv/tools.py`, `cv/policy.py` — `pytest 43 passed / 1 skipped` + `services/reports/_phase_b_verification.json` (clean vs. broken differ, not frozen mocks) | No |
| **Agent (mock path)** | ✅ `select_tool` with `mock_fixture` + whitelist + fallback; `call_gemini` timeout-bounded; live path skip()s in CI | Needs valid `GEMINI_API_KEY` for live demo |
| **FastAPI service** | ✅ `uvicorn main:app --port 8000` serves `/inspect`, `/jobs/{id}`, `/version`, `/health`; `MAX_UPLOAD_BYTES` 413, `reference_image` decode | Needs Lambda deployment (`Dockerfile.lambda` + `Mangum` + ECR + Lambda URL) |
| **Next.js UI** | ✅ `npm run build` compiles clean (294kB /job/[id] incl. jsPDF), `npm run dev` works, drag-and-drop + reference + polling + history + PDF/Share/Toasts verified | Needs `vercel deploy` + `INFERENCE_API_URL` env |
| **Storage** | ✅ `InMemoryJobStore` wraps `JOBS` dict; `store.save/get` works; 413/400/404 paths | Needs DynamoDB table + least-privilege IAM for persistence across deploys |
| **Logs** | ✅ Structured JSON per `/inspect` to stdout (profile, status, decision, agent_tool, measurements) | Needs CloudWatch log group + retention + shareable link |
| **Image artifacts** | 🟡 Job JSON stored; raw upload bytes not persisted to S3 in v1 | Optional S3 bucket + lifecycle-delete |
| **Evaluation harness** | ✅ `scripts/run_experiments.py` runs A/B/B2/C on synthetic fixtures; `scripts/calibrate_thresholds.py` suggests thresholds | Needs `data/self_captured/` (30–100 real photos) + `python scripts/run_experiments.py data/self_captured/` for headline numbers |
| **Experiment D (COOL)** | Not pursuing (always-free tier) | Would need COOL AMI `m8g.4xlarge` + `source /opt/cool/venvs/python_3.12/bin/activate` |
| **Video** | 🟡 Script only (`reports/VIDEO_SCRIPT.md`) ≤5 min outline | Needs recording (OBS) |
| **Version proof** | ✅ `python -c "import cv2; print(cv2.__version__)" → 5.0.0`, `GET /version` returns live versions, `requirements.txt` pins `opencv-python-headless>=5.0.0` → `5.0.0.93` | No — already judge-verifiable locally |

---

## 5. Security & Human-Control Notes (v1, not doc-only)

- Least-privilege IAM (Lambda execution role only needs logs + DynamoDB + S3 write, not admin).
- `max_agent_steps` bounded to 1; `ALL_TOOLS` whitelist enforced twice (prompt + `validate_tool_call`).
- `human_approval_required` enforced for REVIEW/FAIL in `cv/policy.py`, surfaced as large PASS/REVIEW/FAIL card.
- `GEMINI_TIMEOUT_SECONDS=15` prevents slow model from hanging request; failures fall back to deterministic `FALLBACK_AFTER_*`.
- `MAX_UPLOAD_BYTES=10MiB` + empty/corrupt 400s + 413 logging; `track_across_frames` requires caller to supply distinct timestamped frames.

---

## 6. Verification Commands (for judges)

```bash
# Versions (must match report §3)
python -c "import cv2; print(cv2.__version__)"   # 5.0.0
python -c "import platform; print(platform.python_version())"
pip show opencv-python-headless | grep Version   # 5.0.0.93
curl http://localhost:8000/version
curl http://localhost:8000/health

# Full suite (must be 43 passed / 1 skipped)
python -m pytest services/inference/tests -q

# End-to-end on synthetic (must differ, not frozen)
python services/inference/scripts/_verify_end_to_end.py

# Web build (must compile clean)
npm run build --prefix apps/web
```

---

*This ASCII diagram satisfies both `reports/architecture.md` (Phase 8) and `reports/ARCHITECTURE.md` (Phase 9) — they are the same file on case-insensitive filesystems. On case-sensitive systems, `architecture.md` is a symlink/copy of this file.*
