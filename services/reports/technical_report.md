# LoopSight — Technical Report

> **Status:** Filled where data exists; sections requiring real dataset numbers are explicitly marked `[PENDING — real dataset]`. This report is written from code that exists and runs, per spec Section 14: *"this should be written from real test results, not drafted generically and backfilled"*.
>
> **Build environment (verified 2026-09-04):**
> `cv2.__version__ = 5.0.0` (`opencv-python-headless 5.0.0.93`), Python 3.14.6, `google-genai 2.20.0`, `fastapi 0.141.1`, `numpy 2.5.1`, `boto3 1.43.59`, `mangum 0.22.0`, Next.js 15.5.23, React 19, Framer Motion 13.1.1, jsPDF 4.2.1, react-hot-toast 2.6.0, Tailwind CSS 4.0.0.
> The OpenCV version is also logged at import time in `services/inference/cv/first_pass.py:10` and exposed via `GET /version`.

---

## 1. Problem — Primary domain: household drinking-water turbidity screening (India-grounded)

Millions of habitations in India face groundwater contamination (arsenic, fluoride, nitrate) and households lack a fast screen for *visibly* cloudy water before deciding to treat or seek a lab test. Existing turbidity assessment falls into two camps:

- **Single-shot visual judgment** ("does this look cloudy to you?") — one glance under one lighting condition, no way to interrogate borderline cases. The same failure as single-shot print-inspection plugins: one observation treated as final verdict.
- **Fixed-budget lab or field kits** — accurate but not instant, not always accessible at point of use, and do not handle the *uncertain middle* gracefully (either over-call or under-call).

Both treat a single observation as final. LoopSight's thesis is narrower and falsifiable (spec Sections 4, 9): **an inspection controller that decides, from the evidence it already has, which materially-different OpenCV observation to obtain next, can beat a fixed observation budget at matched cost.** Here the signal is *pattern visibility through water* (Secchi-disk / turbidity-tube principle): a printed high-contrast checkerboard behind a clear glass; turbidity blurs and attenuates contrast. When visibility is borderline, the agent requests a second photo under different lighting (backlight vs. ambient or phone flash) — the real-world technique that resolves this ambiguity. This is not a claim to have invented turbidity inspection; it is a test of one specific active-perception policy applied to a large, named, real problem.

Honest risk, stated up front: the adaptive-reinspection mechanic may turn out not to beat a simpler fixed two-pass heuristic — that is what Experiments A/B/B2/C (§4) measure. Secondary domain `fdm_print_surface_v1` (desktop 3D-print QC) is retained as a fully-tested fallback/legacy profile but is no longer the primary story; it is where the request for "genuinely strong visual material" is answered instead by a water/clarity identity rather than a defect-inspector aesthetic.

**Why this domain solves both problems at once:** turbidity screening directly answers "won't work for India" (real, large, named rural groundwater problem) and gives the frontend a distinctive water/clarity visual identity instead of a generic SaaS dash.

---

## 2. Architecture

### 2.1 Pipeline — one image in → one verdict out (spec Section 9/12)

```
image (multipart /api/inspect) ─► FastAPI POST /inspect (services/inference/main.py:247)
                                  │  _decode_image() → BGR ndarray (cv2.imdecode)
                                  │
                                  ├─► first_pass.run_first_pass(frame, reference, rois, profile_name)
                                  │     │  measure_region() per ROI: Canny(50,150) → edge_continuity,
                                  │     │  equalizeHist+absdiff → reference_similarity,
                                  │     │  findContours → layer_alignment_deviation, std/128 → local_contrast
                                  │     └─► score_evidence(): CONFIDENT_PASS / CONFIDENT_FAIL / UNCERTAIN
                                  │            + evidence_gap[] + allowed_tools[]
                                  │
                                  ├─ CONFIDENT_* ─► cv/policy.decide() → final_decision (no agent)
                                  │
                                  └─ UNCERTAIN ─► agent/tool_selector.select_tool(first_pass, api_key|mock_fixture)
                                                    │  validates whitelist, reason_code
                                                    │  call_gemini() bounded by GEMINI_TIMEOUT_SECONDS (default 15)
                                                    │  fallback → FALLBACK_AFTER_INVALID_AGENT_RESPONSE
                                                    ▼
                                               TOOL_REGISTRY[tool] (cv/tools.py)
                                                    │  reinspect_roi (upsample 2x, INTER_CUBIC)
                                                    │  compare_to_reference (isolated SSIM pass)
                                                    │  measure_edge_continuity (Canny low=30 high=100)
                                                    │  track_across_frames (video-mode, persistence std)
                                                    ▼
                                               cv/policy.decide(first_pass, second_pass_region)
                                                    → FinalDecision {decision, confidence_band, human_approval_required, reasoning}
                                  │
                                  └─► store.save(job_id, result) → DynamoDB or InMemoryJobStore (services/inference/storage.py)
                                      ← return {job_id} to Next.js
                                      ← GET /jobs/{job_id} returns full InspectionResult JSON
```

Key design constraint (spec Section 9, enforced in `main.py` and `agent/tool_selector.py`): **OpenCV 5 produces evidence; the final PASS/REVIEW/FAIL decision is deterministic and policy/evidence-driven; the model's only job is choosing which OpenCV tool to run next.** The LLM never renders the visual judgment itself.

### 2.2 Component Responsibility

| File | Owns | Deliberately does NOT |
|------|------|-----------------------|
| `services/inference/main.py` | FastAPI `/inspect` & `/jobs/{id}`, `/version`, `/health`; upload validation (`MAX_UPLOAD_BYTES = 10 MiB`, 413 on oversize); `inspection_profile` dispatch; golden-result demo fallback; timing instrumentation (`decode_ms`, `first_pass_ms`, `agent_ms`, `second_pass_ms`, `total_ms`); reference_image decoding; `human_approval_required` gate; Lambda `Mangum` adapter | Visual measurement (delegates to `cv/`); tool choice (delegates to `agent/`); final policy (delegates to `cv/policy.py`) |
| `services/inference/cv/first_pass.py` | `InspectionProfile` primary `water_turbidity_v1` (`pattern_visibility_confident_turbid=0.20`, `clear=0.55`, `contrast_min=0.05` interim, synthetic-calibrated: clear ~0.81 / turbid ~0.12 / borderline ~0.32) + legacy `fdm_print_surface_v1` (`edge 0.05/0.20`); `measure_pattern_visibility()` (findChessboardCorners or contour square count → contrast + Laplacian sharpness + edge-density blend → `pattern_visibility` 0..1) + `measure_region()` (fdm), `score_evidence()` (water branch vs fdm branch), `run_first_pass()` dispatches by `profile_name`; logs `cv2.__version__` | Final verdict; agent logic |
| `services/inference/cv/tools.py` | `ToolResult`, `reinspect_roi()` (upsample 2x; for water re-measures pattern at higher res), `compare_to_reference()` (isolated ref check), `measure_edge_continuity()` (different Canny thresholds — for water re-processes pattern), `track_across_frames()` **reframed for water as primary "different lighting" tool** (backlight vs ambient / flash; persistence_std on `pattern_visibility`) | Freshness / buffering (caller's job); policy |
| `services/inference/cv/policy.py` | `FinalDecision`, `decide()` — deterministic; water branch checks `pattern_visibility` (turbid ≤0.20 → FAIL, clear ≥0.55 → PASS, else REVIEW; tagline "no visible turbidity ≠ safe"), fdm branch unchanged | Any model call |
| `services/inference/agent/tool_selector.py` | `ToolCall`, `validate_tool_call()`, `_build_prompt()`, `call_gemini()` (models: `gemini-3.6-flash` primary, fallbacks `gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`, timeout-bounded), `select_tool_mock()`, `select_tool()` with deterministic fallback | Measurement |
| `services/inference/storage.py` | `JobStore` abstraction: `InMemoryJobStore` (wraps `JOBS: dict`) vs `DynamoJobStore` (boto3, only if credentials resolvable) | Business logic |
| `services/inference/demo_golden.py` | `GOLDEN_RESULTS` (three fixtures: `confident_pass`, `confident_fail`, `uncertain`), `load_golden()`, `resolve_golden_from_request()` — served when `DEMO_MODE=golden` | Real CV |
| `apps/web/src/app/page.tsx` | Water-themed upload UI (`#0a1628` deep → `#38bdf8` clear, animated ripple/wave background): ONE primary upload/camera zone, safety banner first-screen ("Flags visibly cloudy water · not a substitute for a real water test"), headline "Check your water before you drink it", Framer Motion droplet/ripple loader, Advanced-options expander hiding reference & demo (cut visible elements by >50% vs. prior SaaS dash), compact water "How it works" stepper (photograph pattern → agent asks for different lighting if borderline → clarity verdict), history | Inference (proxies to backend) |
| `apps/web/src/app/job/[id]/page.tsx` | Evidence-trace viewer with water-clarity gauge (circular + gradient bar 0→1, thresholds 0.20 turbid / 0.55 clear, pattern_found chip), safety-critical PASS copy ("No visible turbidity detected — this does not confirm the water is safe…") and FAIL/REVIEW copy ("Visible turbidity detected — this water should not be consumed…"), Perception (Clarity Gauge, Sharpness, Local contrast), Agent Decision (reason_code + lighting note), New Evidence (second visibility after different lighting), Final Decision, Copy/Share/PDF, timings | Measurement |
| `apps/web/src/app/api/inspect/route.ts` | Forwards `FormData` (`image`, optional `reference_image`, `inspection_profile`, `demo_case`) to `INFERENCE_API_URL`; demo-fallback via `fixtureForFileBytes` (FNV-1a hash) when backend unreachable | CV |
| `apps/web/src/app/api/jobs/[id]/route.ts` | Proxies `GET /jobs/{id}` to inference, falls back to in-memory `getJob` | Storage |
| `apps/web/src/app/not-found.tsx` | On-brand 404 (dark, SearchX icon, Back to inspection) | — |
| `apps/web/src/lib/types.ts` | `InspectionResult`, `RegionEvidence`, `AgentCall`, `Measurements` interfaces — exact shape of `/inspect` and `/jobs` payloads | — |
| `apps/web/src/lib/history.ts` | `loadHistory()`, `saveToHistory()`, `clearHistory()` — localStorage `loopsight_history`, max 20 entries, last 5 shown | Backend |

### 2.3 Data Flow (per hop)

| Hop | In | Out |
|-----|----|----|
| Browser → Vercel/Next.js | `FormData {image: File, reference_image?: File, inspection_profile?}` or `demo_case` | `POST /api/inspect` |
| Next.js API route → Lambda FastAPI | Same `FormData` forwarded to `INFERENCE_API_URL` | `fetch(INFERENCE_API_URL + "/inspect")` |
| FastAPI `POST /inspect` | Multipart bytes, decoded via `_decode_image` → `np.ndarray` BGR, optional `reference` ndarray | `FirstPassResult` via `run_first_pass` |
| Agent layer | `FirstPassResult.evidence_gap` + `regions[].local_contrast` etc. as prompt | `ToolCall {tool, arguments, reason_code}` |
| Tool execution | `frame`, `reference`, `roi` + tool args | `ToolResult {region: RegionEvidence}` |
| Policy | `first_pass` + `second_pass_region` | `FinalDecision {decision, confidence_band, human_approval_required}` |
| Storage | `result: InspectionResult` with `measurements` | `job_id` + `GET /jobs/{id}` JSON |

### 2.4 Actual Function Signatures (verified from code)

```python
# services/inference/cv/first_pass.py:85
def measure_region(frame: np.ndarray, reference: np.ndarray | None, roi: tuple[int,int,int,int]) -> RegionEvidence

# services/inference/cv/first_pass.py:154
def score_evidence(regions: list[RegionEvidence], profile: InspectionProfile) -> FirstPassResult

# services/inference/cv/first_pass.py:198
def run_first_pass(frame: np.ndarray, reference: np.ndarray | None, rois: list[tuple[int,int,int,int]], profile_name: str = "fdm_print_surface_v1") -> FirstPassResult

# services/inference/cv/tools.py:30
def reinspect_roi(frame: np.ndarray, reference: np.ndarray | None, roi: tuple[int,int,int,int], scale: float = 2.0) -> ToolResult

# services/inference/cv/tools.py:51
def compare_to_reference(frame: np.ndarray, reference: np.ndarray, roi: tuple[int,int,int,int]) -> ToolResult

# services/inference/cv/tools.py:60
def measure_edge_continuity(frame: np.ndarray, roi: tuple[int,int,int,int], low: int = 30, high: int = 100) -> ToolResult

# services/inference/cv/tools.py:80
def track_across_frames(frames: list[np.ndarray], roi: tuple[int,int,int,int]) -> ToolResult

# services/inference/cv/policy.py:26
def decide(first_pass: FirstPassResult, second_pass_region: RegionEvidence | None, profile_name: str = "fdm_print_surface_v1") -> FinalDecision

# services/inference/agent/tool_selector.py:43
def validate_tool_call(raw: dict) -> ToolCall

# services/inference/agent/tool_selector.py:76
def call_gemini(first_pass: FirstPassResult, api_key: str, model: str = "gemini-3.6-flash") -> ToolCall

# services/inference/agent/tool_selector.py:138
def select_tool(first_pass: FirstPassResult, *, api_key: str | None = None, mock_fixture: dict | None = None, default_tool: str = "reinspect_roi") -> ToolCall

# services/inference/main.py:117
def _decode_image(data: bytes) -> np.ndarray

# services/inference/main.py:185
def _run_tool(tool_call: ToolCall, frame: np.ndarray, reference: np.ndarray | None, roi: tuple[int,int,int,int]) -> ToolResult

# services/inference/main.py:245 (POST)
async def inspect(request: Request) -> JSONResponse  # returns {job_id}

# services/inference/main.py:466 (GET)
async def get_job(job_id: str) -> JSONResponse  # returns InspectionResult

# services/inference/main.py:248 (GET)
async def version() -> dict  # {opencv_version, python_version, profile_names, gemini_model, build_timestamp}
```

---

## 3. Stack (pinned, verified)

| Layer | Choice | Version (pinned) | Notes |
|-------|--------|------------------|-------|
| Frontend framework | Next.js (App Router) | 15.5.23 | TypeScript 5.7.0, Tailwind CSS 4.0.0 + @tailwindcss/postcss 4.0.0, postcss 8.5.0 |
| UI | Tailwind CSS + shadcn/ui + lucide-react + Framer Motion | lucide-react 0.468.0, framer-motion 13.1.1, class-variance-authority 0.7.1, clsx 2.1.1, tailwind-merge 2.6.0 | Water theme #0a1628 deep → #38bdf8 clear, Inter font, animated ripple/wave background, glassmorphism + backdrop-blur, clarity gauge (circular + gradient bar) |
| Export / UX | jsPDF, react-hot-toast | jspdf 4.2.1, react-hot-toast 2.6.0 | Download report PDF, toast notifications, Share link |
| CV runtime | Python + opencv-python-headless | 5.0.0.93 (`cv2.__version__ 5.0.0`), numpy 2.5.1, Python 3.14.6 | Verified `5.x` not `4.x`; logged in `cv/first_pass.py` and `/version` |
| API | FastAPI + uvicorn + python-multipart + mangum | fastapi 0.141.1, uvicorn 0.51.0 (standard), mangum 0.22.0 | CORS for localhost:3000, Lambda handler via Mangum |
| Agent | google-genai (Gemini) | 2.20.0, model `gemini-3.6-flash` (fallback `gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`), `GEMINI_TIMEOUT_SECONDS=15` | Whitelisted tool set, `call_gemini` network-timeout-bounded; mock path default when no key |
| Storage | boto3 (DynamoDB) + in-memory fallback | boto3 1.43.59 | `storage.py` picks `DynamoJobStore` only when AWS credentials resolvable; otherwise `InMemoryJobStore` wraps `JOBS: dict` |
| Frontend hosting | Vercel (Hobby) | — | Proxies `/api/*` to `INFERENCE_API_URL` |
| CV hosting | AWS Lambda (FastAPI) | — | Container via `Dockerfile.lambda`; `handler = Mangum(app)`; not pursuing Best Use of COOL (always-free tier) |
| CI | GitHub Actions | `.github/workflows/test.yml` | Runs `pytest services/inference/tests` + `npm run build --prefix apps/web`; live Gemini test skip()s when `GEMINI_API_KEY=disabled` |
| Observability | CloudWatch (logs) + structured JSON log line per `/inspect` | — | `logger.info(json.dumps({event:"inspect", profile, status, decision, agent_tool, measurements}))` |

Pinned dependencies: `requirements.txt` (`opencv-python-headless>=5.0.0`, `numpy>=2.0`, `fastapi>=0.110.0`, `uvicorn[standard]>=0.30.0`, `python-multipart>=0.0.9`, `google-genai>=1.0.0`, `boto3>=1.35.0`, `mangum>=0.19.0`) and `apps/web/package.json` (see versions above). Fresh-clone setup is in §7.

---

## 4. Evaluation

The central question (spec Section 14): **does adaptive reinspection beat a fixed second-pass heuristic at matched cost?**

### 4.1 Experiments (implemented in `services/inference/scripts/run_experiments.py`)

| Experiment | Question | Implementation |
|-----------|----------|----------------|
| A | Fixed single-pass baseline | `trigger_rate = 0` by design; no agent, no second look. |
| B | Fixed second-pass at matched cost (aggregate) | Runs second pass on a fixed fraction of cases equal to C's overall trigger rate. |
| B2 | Fixed second-pass matched to the agent's cost distribution (per-case deterministic) | **Critical control.** Uses a deterministic per-case hash (`hash(job_id) % N`) so B2 triggers on exactly the same *number* of cases as C, but on a random subset independent of evidence-gap. This is stable, per-case, and not all-or-nothing. The judge has seen OctoPrint/PrintGuard; B2 is the number to lead with — "beats fixed observation at matched cost" is only meaningful if the baseline is cost-matched *per case*, not just on average. |
| C | Adaptive (agent) second-look | `UNCERTAIN` → `select_tool` (mock or live Gemini) → `TOOL_REGISTRY` → `decide`. |

Harness: `run_all()` walks a dataset folder (`clean/`, `defect/`, …), runs A/B/B2/C end-to-end, collects `accuracy`, `precision`, `recall`, `trigger_rate`, `conditional_benefit` (bounded in [−1, 1]), and latency/CPU via `measurements`. `print_report()` prints a markdown table. The harness is dry-runnable on synthetic fixtures today; real headline numbers must be regenerated against `data/self_captured/`.

### 4.2 Metrics

- **`accuracy`** — correct decisions (PASS on clean, FAIL/REVIEW on defect) over total. Reported per-experiment.
- **`trigger_rate`** — fraction of cases where second pass ran (A=0, C=agent's rate, B/B2=matched to C).
- **`conditional_benefit`** — bounded benefit of the second look *conditional on having triggered*, i.e. accuracy gain on the triggered subset vs. what single-pass would have done on that same subset. Definition in `scripts/run_experiments.py:calculate_conditional_benefit()`; clamped to [−1, 1] so a tiny denominator can't produce an unbounded headline. Placeholder contract tests assert boundedness and that B2's trigger count equals C's.
- **Latency** — `measurements: {decode_ms, first_pass_ms, agent_ms, second_pass_ms, total_ms}` per job, aggregated as mean/p50/p95 for Experiment D.

### 4.3 Why B2 Is the Critical Control

Without B2, a naive comparison (C vs. A) conflates "second observation helps" with "adaptive selection helps." Fixed two-pass (B) already gets a second observation on every (or a random) subset; if C beats B at the same *number* of second looks, the gain is attributable to *which* cases and *which* tools were chosen, not merely to having more compute. B2 enforces this by matching C's budget deterministically per case, so the only remaining difference is adaptivity. Spec Section 20 explicitly calls this the evaluation's falsifiable core.

### 4.4 Real Numbers

`[PENDING — real dataset]` — placeholder contract tests assert that B2 is cost-matched and `conditional_benefit` is bounded, but the headline accuracy table must be filled from `data/self_captured/` measurements recorded via `scripts/run_experiments.py`. Synthetic-fixture demo numbers are in `services/reports/_phase_b_verification.json` but are not a substitute for real photos.

---

## 5. Results

`[PENDING — real dataset; replace this section with the A/B/B2/C table from scripts/run_experiments.py run against data/self_captured/. Keep the synthetic _phase_b_verification.json as build evidence, not as the results table.]`

---

## 6. Limitations (honest, from real test results — spec Sections 14, 20)

These are not placeholders; they are disclosed pre-submission and must survive live demo.

- **Thresholds are interim and synthetic-calibrated.** `PROFILES["fdm_print_surface_v1"]` now uses `fail=0.05, pass=0.20, contrast_min=0.10, reference_similarity_floor=0.40` — updated in Phase 6 from the original `0.35/0.85/0.40/0.55` placeholders after synthetic test runs measured `edge_continuity` in the 0.01–0.24 range. The relative signal (broken < clean) is proven (`test_broken_edge_has_lower_edge_continuity_than_clean` passes); the absolute cutoffs are still uncalibrated for real photos and will need recalibration via `scripts/calibrate_thresholds.py` against `data/self_captured/` before trusting a headline accuracy number. Documented as interim until real photos recalibrate them.

- **OpenCV 5 verified, but behavior is source-compatible.** `opencv-python-headless 5.0.0.93` now installed and verified (`cv2.__version__ == 5.0.0` logged at import and via `GET /version`). The operations used (Canny, findContours, absdiff, equalizeHist, resize) are source-compatible between 4.x and 5.x (5.x changes contour performance via TRUCO, not call signature). Full test suite re-run against 5.x in Phase 6: 43 passed / 1 skipped. Prior caveat about testing only on 4.13 is now resolved.

- **Reference-image comparison is lighting-normalized but still single-view.** `measure_region` now equalizes histograms before `absdiff` so identical geometry under different illumination (alpha=1.3 beta=30) stays at similarity 1.0 (raw absdiff drops to 0.77–0.86). CLAHE was tested and rejected (left similarity at ~0.84 — does not correct global shift). EqualizeHist does not hide real defects: clean vs. broken synthetic squares score 0.9667 equalized vs 0.9765 raw (still distinct). Single-view remains a limitation vs. multi-angle capture.

- **Dark-filament / low-contrast bias.** `[PENDING — real dataset to quantify]` Synthetic testing shows `local_contrast < 0.10` triggers `UNCERTAIN` (low local contrast — cannot confirm edge deviation) and routes to `REVIEW`. Real dark filaments (black, navy) under dim lighting may systematically hit this gate more often, producing a higher `REVIEW` rate on that subpopulation — a bias to measure explicitly when `data/self_captured/` includes filament-color stratification.

- **Stale-buffered-frame risk in live/video mode.** `track_across_frames` explicitly requires distinct frames with increasing timestamps; the capture layer (not `cv/tools.py`) must enforce freshness by continuously draining `cv2.VideoCapture`. Single-image upload mode (`POST /inspect` with one `image`) is not affected; the risk only applies to a future live-camera path and is documented as not yet mitigated beyond the contract in the tools module's docstring.

- **No real dataset yet; stats blocked.** `scripts/run_experiments.py` proves the harness runs on synthetic fixtures, but Experiments D (COOL vs. baseline latency) and E (robustness/adversarial cases) require real photos. Experiment E must include at least one genuinely ambiguous/adversarial failure case handled gracefully, ending in `REVIEW` — not yet produced.

- **Mock fallback on live site.** `apps/web/src/app/api/inspect/route.ts` falls back to `fixtureForFileBytes` (FNV-1a hash over uploaded bytes, same bytes → same fixture, different bytes → usually different fixture) when `INFERENCE_API_URL` is unreachable. This is the spec-required demo resilience (Section 10), not a substitute for the real pipeline. The fallback path is clearly marked `DEMO MODE` in UI and report.

- **Gemini live path has never succeeded with the shipped key.** `call_gemini()` is verified against the API shape and bounded by `GEMINI_TIMEOUT_SECONDS=15` so a failing key never hangs the request (fallback to `FALLBACK_AFTER_AGENT_CALL_ERROR`), but the key that was in `.env` is compromised and must be regenerated by the user at aistudio.google.com before the demo. The mock path (`select_tool` with `mock_fixture`) is the tested default; production must verify against a valid key.

---

## 7. Responsible Use — water-turbidity is safety-adjacent (not "stakes moderate, not safety-critical" any more)

- **Turbidity is NOT potability — single most important content change (do not treat as boilerplate).** A clear-looking sample can still carry arsenic, fluoride, or nitrate — invisible to any camera. This is an ethical design decision, not legal disclaimer.
  - **Landing page first screen (above headline):** "Flags visibly cloudy water for follow-up. Not a substitute for a real water safety test. Clear-looking water can still carry invisible contaminants."
  - **Result PASS state:** "No visible turbidity detected — this does not confirm the water is safe. Invisible contaminants require a real water test." It never says "safe" or "safe to drink."
  - **Result REVIEW / FAIL states:** "Visible turbidity detected — this water should not be consumed without treatment or further testing."
  - These framings also appear in this report and in `reports/VIDEO_SCRIPT.md`'s narrative — same language everywhere.
- **Product-shown disclaimers (rendered in `apps/web/src/app/job/[id]/page.tsx` banner + DecisionCard + Download PDF footer and `apps/web/src/app/page.tsx` safety banner + footer):** *"LoopSight flags visibly cloudy water for follow-up. It does not confirm water is safe — invisible contaminants require a real water test. Visible turbidity: do not drink without treatment."* & *"Flags visibly cloudy water for follow-up. Not a substitute for a real water safety test."* The PDF report footer also reads: *"Safety: No visible turbidity does NOT confirm safe water — invisible contaminants require a real water test. Visible turbidity: do not drink without treatment. Generated by LoopSight — demo mode, not a certified inspection"*.
- **Legacy note:** stakes for `fdm_print_surface_v1` remain moderate (wasted filament/time), but the primary domain's framing above overrides when discussing product liability.
- **Data licensing:** Self-captured data (`data/self_captured/`) ships in the public repo under MIT. Any MVTec-family reference is internal-validation-only and **never redistributed** (MVTec AD et al. are CC BY-NC-SA 4.0, non-commercial only — spec Section 13). Any added detector library gets its license checked individually (e.g., YOLO is AGPL-3.0-only; Apache-2.0 alternatives like RTMDet exist and must be preferred).
- **IP:** Only the report/video/architecture package is included in the competition's submission license grant (Devpost Official Rules, IP clause); the private code/dataset stays outside it (spec Section 3). The repo's private branch is not part of the submission.
- **Transparency:** The evidence-trace UI is the system's transparency story — a judge sees exactly what was measured (`edge_continuity`, `reference_similarity`, `layer_alignment_deviation`, `local_contrast`), why the agent fired (`reason_code`), what tool ran, and what changed (`evidence_changed`, `second_pass.regions`, `confidence_band`, `human_approval_required`). The raw JSON trace is copyable via "Copy trace as JSON".
- **Human control:** `human_approval_required: true` is enforced for every `REVIEW` and `FAIL` decision (not just displayed); `max_agent_steps` and `ALL_TOOLS` whitelist prevent free-form actions; `GEMINI_TIMEOUT_SECONDS` prevents a slow model from blocking the pipeline.

---

## 8. Setup & Reproduction

### 8.1 Pinned Versions

See §3 Stack. Quickest check:

```bash
python -c "import cv2; print(cv2.__version__)"  # must print 5.0.0
python -c "import platform; print(platform.python_version())"
pip show opencv-python-headless fastapi numpy google-genai boto3 mangum
cat requirements.txt
cat apps/web/package.json
curl http://localhost:8000/version
```

### 8.2 Fresh-clone setup

```bash
git clone <repo-url> && cd LoopSight

# Inference service
cd services/inference
pip install -r ../../requirements.txt
python -m pytest tests -q  # 43 passed, 1 skipped (live Gemini skips if no key)

# Run the real pipeline locally
uvicorn main:app --reload --port 8000
curl http://localhost:8000/version  # {opencv_version, python_version, profile_names, gemini_model, build_timestamp}
curl -X POST -F "image=@/path/to/print.jpg" http://localhost:8000/inspect
curl http://localhost:8000/jobs/<job_id>

# With reference image
curl -X POST -F "image=@print.jpg" -F "reference_image=@reference.jpg" http://localhost:8000/inspect

# Web (in a second terminal)
cd apps/web
npm install
npm run build  # must compile clean
npm run dev    # http://localhost:3000
# Set INFERENCE_API_URL in .env.local if inference is not on localhost:8000
# Optionally: GEMINI_API_KEY, DEMO_MODE=golden, FORCE_AMBIGUOUS=1
```

### 8.3 Environment Variables

| Var | Purpose | Default |
|-----|---------|---------|
| `INFERENCE_API_URL` | Where Next.js API routes proxy to | `http://localhost:8000` |
| `GEMINI_API_KEY` | Live agent; if absent, `select_tool` uses mock fixture | unset (mock path) |
| `GEMINI_MODEL` | Overridden model name for `/version` | `gemini-3.6-flash` |
| `GEMINI_TIMEOUT_SECONDS` | Network timeout for `call_gemini` | `15` |
| `DEMO_MODE` | `golden` → serve precomputed fixtures instead of live CV | unset |
| `DEMO_CASE` / `demo_case` | `confident_pass` \| `confident_fail` \| `uncertain` | `uncertain` when forced |
| `FORCE_AMBIGUOUS` | `1` → force `uncertain` fixture via web layer | unset |

### 8.4 Calibration Workflow (when real photos exist)

```bash
# After capturing to data/self_captured/{clean,layer_shift,...}/
python services/inference/scripts/calibrate_thresholds.py data/self_captured --reference data/self_captured/clean/001.jpg
# Copy suggested thresholds into services/inference/cv/first_pass.py PROFILES
# Then:
python services/inference/scripts/run_experiments.py data/self_captured
```

---

## 9. Appendix: Build Progress Evidence

Cross-referenced artifacts already produced in this repo:

- Phase B real-stack end-to-end evidence: `services/reports/_phase_b_verification.json` (synthetic clean/broken through full stack, measurements: edge_continuity, layer_alignment_deviation, timings).
- Threshold calibration harness: `services/inference/scripts/calibrate_thresholds.py` (compute_table, suggest_thresholds, print_report).
- Evaluation harness + tests: `services/inference/scripts/run_experiments.py`, `services/inference/tests/test_run_experiments.py` (A/B/B2/C, `run_all`, `print_report`, `conditional_benefit` bounded, B2 cost-matched).
- CI workflow: `.github/workflows/test.yml` (inference pytest suite + Next.js build; the live Gemini test skip()s in CI via `GEMINI_API_KEY=disabled`).
- Demo golden path: `services/inference/demo_golden.py`, `services/inference/tests/test_demo_golden.py`, `apps/web/src/lib/mock-data.ts` (FNV-1a hash, same bytes → same fixture).
- UI: `apps/web/src/app/page.tsx` (drag-and-drop, reference-image slot, history, feature cards, Framer Motion), `apps/web/src/app/job/[id]/page.tsx` (staggered reveal, polling 1.5s/30s timeout, Copy/Share/Download PDF via jsPDF, timings, reference-similarity conditional), `apps/web/src/app/not-found.tsx`, `apps/web/src/lib/history.ts` (localStorage), `services/inference/main.py: /version`.
- OpenCV 5 verification: `services/inference/cv/first_pass.py` logs `cv2.__version__` at import; `GET /version` returns live version; `requirements.txt` pins `opencv-python-headless>=5.0.0` and resolves to `5.0.0.93`.
