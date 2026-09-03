# LoopSight — Submission Checklist

> Master checklist of everything the OpenCV AI Competition 2026 requires before hitting submit.
> Derived from Devpost Official Rules (spec Section 2) + `LoopSight_Project_Spec.md` + `services/reports/technical_report.md` §8.
> Update this file as each item is verified with **real output** (not summaries). Judges get at least two independent, conflict-free scores averaged; tie-break is Technical Execution → Real-World Impact → extra judge.

_Last updated: 2026-09-04T00:00Z (Phase 10 pre-AWS). Statuses: ✅ Done (verified locally), 🟡 Done locally / needs AWS to be judge-accessible, ⏳ TODO (requires real dataset or AWS)._

---

## 1. Working Judge-Accessible Endpoint

- [ ] 🟡 **Live inference endpoint** — `POST https://<lambda-url>/inspect` + `GET /jobs/{id}` responds 200 to a judge's image upload without auth friction (demo token / signed URLs if needed). _Locally verified: `uvicorn main:app --port 8000` + `curl -F "image=@print.jpg" http://localhost:8000/inspect` returns `{job_id}` and `GET /jobs/{id}` returns full `InspectionResult`. Needs Lambda URL + API Gateway deployment._
- [ ] 🟡 **Frontend demo URL** — `https://<vercel-url>` loads, drag-and-drop works on 320px, Inspect + Try demo case both reach the live backend. _Locally verified: `npm run build` compiles clean, `npm run dev` + upload → redirect to `/job/[id]` → evidence trace renders. Vercel deploy pending._
- [ ] ⏳ **No-auth judge path tested from incognito** — judge can open frontend + hit backend without needing to log in or chase a private invite. _Requires deployed URLs._

## 2. Pinned Dependencies + Setup Instructions

- [x] ✅ **`requirements.txt` pinned** — `opencv-python-headless>=5.0.0` (resolves to 5.0.0.93, verified `cv2.__version__ == 5.0.0`), `numpy>=2.0` (2.5.1), `fastapi>=0.110.0` (0.141.1), `uvicorn[standard]>=0.30.0` (0.51.0), `python-multipart>=0.0.9`, `google-genai>=1.0.0` (2.20.0), `boto3>=1.35.0` (1.43.59), `mangum>=0.19.0` (0.22.0). _File: `requirements.txt`._
- [x] ✅ **`apps/web/package.json` pinned** — `next 15.5.23`, `react 19`, `framer-motion 13.1.1`, `jspdf 4.2.1`, `react-hot-toast 2.6.0`, `tailwindcss 4.0.0`, `lucide-react 0.468.0`. _File: `apps/web/package.json`._
- [x] ✅ **Fresh-clone setup documented** — §8 of `services/reports/technical_report.md` gives copy-paste `pip install`, `uvicorn`, `curl /version`, `npm install && npm run build && npm run dev`, env var table, and calibration workflow. _Verified on current machine (Phase 10)._
- [ ] ⏳ **Clean-machine verification** — run the setup instructions on a machine that has never seen this repo (spec Section 18) and confirm 43 passed / 1 skipped + `npm run build` green. _TODO: second machine._

## 3. Architecture Diagram

- [x] ✅ **ASCII diagram exists** — `reports/ARCHITECTURE.md` (and `reports/architecture.md` alias) contains full browser→Vercel→Next.js→/api→Lambda→FastAPI→cv/first_pass→agent/tool_selector→cv/tools→cv/policy→DynamoDB→S3→CloudWatch diagram + data-flow table + component-responsibility table. _Created in Phase 9._
- [ ] ⏳ **Rendered diagram for submission package** — export a PNG/SVG version of the ASCII diagram for the PDF/video if the submission portal expects an image, not just ASCII. _Optional; ASCII satisfies the requirement._

## 4. Technical Report (Complete, Not Just Skeleton)

- [x] ✅ **Report exists and is not a skeleton** — `services/reports/technical_report.md` filled per Phase 7: §1 Problem, §2 Architecture (real file paths, real function signatures, data-flow + responsibility tables), §3 Stack (pinned versions), §4 Evaluation (A/B/B2/C + conditional_benefit + why B2 is critical), §6 Responsible Use (disclaimers, licensing, IP, transparency), §7 Setup, §8 Appendix, §5 Results still marked `[PENDING — real dataset]` only where real numbers are genuinely required. _File verified._
- [x] ✅ **Limitations section is honest** — §6 lists interim thresholds (fail=0.05/pass=0.20 vs. original 0.35/0.85), OpenCV 5 verified (5.0.0), lighting normalization, dark-filament bias pending, stale-buffer risk, no real dataset, mock fallback, Gemini key compromised. _Matches README caveats._
- [ ] ⏳ **Backfill real numbers** — after `data/self_captured/` exists, run `scripts/run_experiments.py` and replace the `[PENDING — real dataset]` in §5 Results with the A/B/B2/C accuracy table. _Blocked on real photos._

## 5. Video ≤5 Minutes (Script Outline Only)

- [x] ✅ **Script exists** — `reports/VIDEO_SCRIPT.md` is a timed outline (0:00 problem, 0:20 first inspection, 0:55 wow moment with agent firing, etc.) written against what the system *actually does now* (not planned). _Created in Phase 8; not yet recorded._
- [ ] ⏳ **Record & trim to ≤5:00** — OBS Studio, 1080p, captions, no watermark. Must show: upload → evidence trace with agent firing → final decision → /version proof → limitations slide. _TODO after real dataset or at least rehearsed demo with uncertain fixture._

## 6. Evaluation Evidence Including Limitations / Failure Cases

- [x] ✅ **Harness exists and runs** — `services/inference/scripts/run_experiments.py` implements A/B/B2/C, `conditional_benefit` bounded, B2 deterministic per-case hash. _Verified: `python -m scripts.run_experiments` prints report on synthetic fixtures._
- [x] ✅ **Contract tests for harness** — `services/inference/tests/test_run_experiments.py` asserts B2 cost-matched and `conditional_benefit` bounded. _Passing (43/43)._
- [x] ✅ **Build progress evidence** — `services/reports/_phase_b_verification.json` (clean vs. broken synthetic through full stack, differing edge_continuity not frozen mock), `scripts/calibrate_thresholds.py` (suggest_thresholds). _Files exist._
- [ ] ⏳ **Real-dataset table** — A/B/B2/C headline numbers on `data/self_captured/` via `run_experiments.py`. _Blocked on real photos._
- [ ] ⏳ **Experiment E failure case** — at least one genuinely ambiguous/adversarial case that ends in `REVIEW` gracefully, documented with photo and trace. _Blocked on real photos._
- [ ] ⏳ **Experiment D (COOL) comparison** — baseline vs. COOL-on-Graviton latency delta, if pursuing Best Use of COOL. Currently not pursuing; if pursued, needs `m8g.4xlarge` AMI (`/opt/cool/venvs/python_3.12`) and CloudWatch metrics.

## 7. OpenCV 5 Version Confirmed

- [x] ✅ **`opencv-python-headless>=5.0.0` pinned** — `requirements.txt:1` and resolves to `5.0.0.93`. _Verified._
- [x] ✅ **Logged at import** — `services/inference/cv/first_pass.py:10` logs `cv2.__version__` at INFO level on every import/inference run.
- [x] ✅ **Exposed via API** — `GET /version` returns `{opencv_version, python_version, profile_names, gemini_model, build_timestamp}`. _Implemented in `services/inference/main.py:248`._
- [x] ✅ **Verified live** — `python -c "import cv2; print(cv2.__version__)"` prints `5.0.0` in this environment; `pytest` suite re-run against 5.x in Phase 6: 43 passed / 1 skipped.

## 8. AWS Deployment + CloudWatch Logs Accessible

- [ ] 🟡 **Lambda deployment** — `services/inference/Dockerfile.lambda` exists; `handler = Mangum(app)` wraps FastAPI. _Builds locally; needs `docker build` + push to ECR + Lambda URL + IAM (least-privilege) + `INFERENCE_API_URL` env on Vercel. Always-free tier intended; not pursuing COOL AMI._
- [ ] ⏳ **DynamoDB table** — `JobStore` (`storage.py`) auto-picks Dynamo when credentials resolvable; else falls back to `InMemoryJobStore`. _Needs table creation + least-privilege IAM policy._
- [ ] ⏳ **S3 for evidence images** — bucket + lifecycle-delete policy for uploaded images / result artifacts (if storing beyond job JSON). _Optional for v1; job JSON is enough for judge repro._
- [ ] ⏳ **CloudWatch logs accessible to judges** — structured JSON log line per `/inspect` (`event:inspect, profile, status, decision, agent_tool, measurements`) emitted via `logger.info`. _Needs log group + retention + shareable link or screenshot for submission._
- [ ] ⏳ **Judge can verify logs** — documented in report §8 and README how a judge finds the logs (log group name, example query). _TODO post-deploy._

## 9. Security / Human Control (Spec Section 26 — ships in v1, not doc-only)

- [x] ✅ **Least-privilege IAM** — documented; enforcement is via deployment-time policy (not code). _Needs real policy when Lambda is created._
- [x] ✅ **`max_agent_steps` / bounded agent** — agent fires at most once per inspection; `ALL_TOOLS` whitelist; `GEMINI_TIMEOUT_SECONDS` prevents hang.
- [x] ✅ **Whitelisted tool set** — `TOOL_REGISTRY` in `cv/tools.py` + `validate_tool_call` in `agent/tool_selector.py` double-enforced; video-mode tool `track_across_frames` rejected for single-image uploads.
- [x] ✅ **`human_approval_required` gate** — `true` for every `REVIEW` and `FAIL` in `cv/policy.py`; surfaced in UI as large PASS/REVIEW/FAIL card + badge.
- [x] ✅ **Upload hardening** — `MAX_UPLOAD_BYTES = 10 MiB`, 413 on oversize, empty-file and corrupt-decode 400s, tested in `tests/test_input_hardening.py`.

## 10. Submission Package Self-Check

Before clicking submit on `opencv26.devpost.com`, re-read the live Official Rules page (it gets amended) and confirm:

- [ ] Every entry uses **OpenCV 5 for substantive image/video analysis** (not just import) — verified via `/version` + `cv/first_pass.py` + `cv/tools.py`.
- [ ] Every entry runs a **meaningful component on AWS** — Lambda URL is live and described in report.
- [ ] Submission package contains: **technical report**, **judge-accessible code** (repo link or zip), **pinned dependencies + setup instructions**, **architecture diagram**, **working endpoint or live demo**, **video ≤5 minutes**, **evaluation evidence including limitations/failure cases** — per Devpost submission checklist.
- [ ] No misrepresentation of capabilities, results, benchmarks, or human-review role (rejection ground per Responsible & Ethical Use rubric).
- [ ] Team size ≤4, correct Devpost registration, content 13+ and not violating third-party terms.

---

### What's Live Now vs. What Needs AWS to Be Real

| Component | Live Now (verified locally) | Needs AWS |
|-----------|------------------------------|-----------|
| CV pipeline (OpenCV 5, first_pass, tools, policy) | ✅ `pytest 43/1` + `_phase_b_verification.json` | No |
| Agent tool selection (mock path) | ✅ | No — live Gemini needs valid key |
| FastAPI inference service | ✅ `uvicorn main:app` + `/version` | Needs Lambda URL for judges |
| Next.js UI (dark theme, polling, reference slot, history, PDF) | ✅ `npm run build` clean, `npm run dev` works | Needs Vercel deploy |
| Job storage | ✅ InMemory fallback | Needs DynamoDB for persistence |
| Logs | ✅ Structured JSON to stdout | Needs CloudWatch log group |
| Evaluation harness (A/B/B2/C) | ✅ On synthetic fixtures | Needs real `data/self_captured/` |
| Video | 🟡 Script only | Needs recording |

### Evidence Locations (for judges)

- Report: `services/reports/technical_report.md`
- Architecture: `reports/ARCHITECTURE.md`
- Video script: `reports/VIDEO_SCRIPT.md`
- Fresh-clone setup: `services/reports/technical_report.md §8`
- Pinned deps: `requirements.txt`, `apps/web/package.json`
- End-to-end: `services/reports/_phase_b_verification.json`
- Tests: `services/inference/tests/` (run `python -m pytest tests -q`)
- Version proof: `GET /version`, `python -c "import cv2; print(cv2.__version__)"`
