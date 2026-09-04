# LoopSight — Project Status (canonical)

> **Single source of truth** — a stranger, judge, or future session with no memory should understand the entire project from this file alone. Updated every work session before finishing (see Changelog).

**Last updated:** 2026-09-04 (fix pass 58→ post-fix, pre-real-data)
**Current commit:** `92125ec` + fix-pass uncommitted (Phases 1–7 done, awaiting verification commit)
**Primary domain:** household drinking-water turbidity screening (`water_turbidity_v1`) — checkerboard-behind-glass, Secchi-disk logic, backlight vs ambient second look. Legacy `fdm_print_surface_v1` (3D-print QC) kept fully functional as fallback/reference.
**Stack:** OpenCV 5.0.0 + Python 3.14 + FastAPI + Mangum → Lambda arm64 (always-free) + Next.js 15.5 + Tailwind water `#0a1628→#38bdf8` + Framer Motion + jsPDF; Agent `gemini-3.6-flash` (whitelist + 15s timeout, mock fallback); Store `InMemoryJobStore` → `DynamoJobStore` when `DYNAMO_TABLE_NAME` + creds resolvable.
**Build verified:** `python -m pytest tests -q` → `43 passed, 1 skipped, 1 warning` (synthetic fixtures, no key, no AWS); `npm run build` → `✓ Compiled successfully` + static pages 5/5.

---

## 1. Why this domain (pivot reasoning)

- **Started as** desktop 3D-print QC — mechanism (first look → uncertain → agent picks second observation → resolve) is known active perception (competition itself suggests it), not novel alone. Domain would have been differentiator.
- **Problem with fdm:** no real printer access for student, heavy prior art (3DPrintSaviour, Jin et al. 2019 closed-loop adaptive, etc.), weak India story.
- **Research pick #1 vs #2:** water turbidity screening won over water accessibility auditing — turbidity is where mechanism (second differently-lit look) is *not* answered by another method, gives strong visual identity (water/clarity vs defect-inspector), and directly answers "won't work for India" (arsenic/fluoride/nitrate habitation story, large named problem). One printable A4 checkerboard + clear glass + phone = zero-budget buildable, per spec single-SPOT principle.

---

## 2. Architecture (one image → verdict)

```
image (/api/inspect) → FastAPI POST /inspect main.py:304
  _decode_image → BGR ndarray
  → first_pass.run_first_pass(frame, reference, rois, profile) first_pass.py:403
      water: measure_pattern_visibility → _detect_reference_pattern(findChessboardCorners 5 sizes + contour squares) → contrast std/128 + Laplacian var/600 + Canny density blend → pattern_visibility 0..1 (0.20 turbid / 0.55 clear)
      fdm:   measure_region → Canny 50/150 edge_continuity + equalizeHist absdiff reference_similarity + contour deviation + local_contrast
      → score_evidence → CONFIDENT_PASS/FAIL/UNCERTAIN + evidence_gap + allowed_tools
  → CONFIDENT_* → policy.decide → final_decision (no agent)
  → UNCERTAIN → agent/tool_selector.select_tool (mock fixture or live gemini-3.6-flash, whitelist, FALLBACK_AFTER_*) → TOOL_REGISTRY[tool]
        reinspect_roi (2x upsample) | compare_to_reference | measure_edge_continuity (30/100) | track_across_frames (persistence_std on pattern_visibility — water: different lighting)
      → policy.decide(first, second_region) → PASS/REVIEW/FAIL + human_approval_required
  → store.save(job_id, result) {status, regions[].evidence, evidence_gap, agent_call, second_pass, final_decision, measurements, frames/frame_info} → InMemory/Dynamo
  ← {job_id} → GET /jobs/{id}
```

Key constraint enforced: OpenCV produces evidence; LLM only picks *which* OpenCV tool; final decision deterministic (`policy.py:26` <60 lines).

**Profiles:** `PROFILES` `first_pass.py:58` both listed at `GET /version` `main.py:291` (`opencv_version`, `python_version`, `profile_names`, `gemini_model`, `build_timestamp`).

---

## 3. What's working vs demo-mode vs pending

### Fully working (local, verified)
- **CV:** both profiles, water `pattern_visibility` synthetic clear 0.81 / turbid 0.12 / borderline 0.32 separates; fdm edge `broken < clean` proven `test_first_pass.py:29`; `equalizeHist` lighting normalization `first_pass.py:283`.
- **Agent:** whitelist double-enforced `first_pass.py:110` + `tool_selector.py:26/43`, deterministic fallback, timeout 15s `92`, mock default keeps suite offline.
- **Tools:** 4 whitelisted, materially different observation (upsample, different thresholds, persistence) `tools.py:30`.
- **API:** `/inspect` hardening 10 MiB 413 `main.py:112`, `inspection_profile` dispatch default `water_turbidity_v1`, `reference_image` optional, `image2` + `original_job_id` two-lighting path real (`track_across_frames([frame, frame2])` `main.py:562` with `frame_info` timestamps `seq` `lighting`), `measurements` + CloudWatch log `528`, `FRAME_CACHE` 100 entries `107`.
- **Web:** landing water theme `#0a1628→#38bdf8` `globals.css:3` ripple `46`, one primary zone + `Advanced options` collapsed (22→10 visible, 54% cut), droplet/ripple loader `page.tsx:62`, safety banner first-screen `250`, headline `Check your water…` `260`, history localStorage `history.ts`, evidence trace now water-unified (`job/[id]/page.tsx:40` `ClarityGauge` circular + `ClarityBar` 0.20/0.55, `DecisionCard` safety copies, `isWaterResult` conditional, header `Droplets` `Waves` `379`, loading `Checking water clarity…` `324`, second lighting prompt `Sun` selector + upload/camera + `handleSecondSubmit` → `original_job_id` `343`, `frame_info` LOOK 1→LOOK 2 display `frameInfo` `frame_info`).
- **Docs:** `README.md:1` water pivot + safety, `technical_report.md:1` water §1 + §7 responsible-use + stack water, `VIDEO_SCRIPT.md:1` water ≤4:45 with second lighting demo, `LICENSE` MIT `LICENSE:1`, `data/README.md` consent template.
- **Tests:** 11 test files, synthetic generators `make_checkerboard/make_turbid_water` `synthetic.py:45`, harness `run_experiments.py:86` + `calibrate_thresholds.py:45` both water-aware, CI `test.yml`.

### Demo-mode (spec-required resilience, not real pipeline)
- `demo_golden.py:36` 3 fixtures `confident_pass/fail/uncertain` served when `DEMO_MODE=golden` `main.py:331`; web `mock-data.ts:111` `FNV-1a` `fixtureForFileBytes` fallback when `INFERENCE_API_URL` unreachable `api/inspect/route.ts:42` → `console.warn` + canned `MOCK_RESULT` (same shape, precomputed). Clearly marked demo, not certified (`job/[id]/page.tsx:316` footer).

### Pending (priority order — the 58→82 gap)
1. **Real dataset** `data/self_captured/{clear,turbid,borderline}` empty — all `technical_report.md:197` `[PENDING]` (`§4.4/§5/§6`), `SUBMISSION_CHECKLIST.md:33` unchecked. Synthetic 0.81/0.12/0.32 thresholds interim until real photos recalibrate via `scripts/calibrate_thresholds.py` + `suggest_thresholds` (`pattern_visibility_confident_turbid/clear` now water-aware).
2. **Live deployment** — code ready (`Dockerfile.lambda:5` arm64, `README_DEPLOY_LAMBDA.md:1` 5 steps + billing tripwire, `scripts/deploy_lambda.sh:1` one-pass scripted), but no ECR/Lambda/Function URL/Vercel `INFERENCE_API_URL` live yet (`SUBMISSION_CHECKLIST:12` 🟡). `DynamoJobStore` untested live, CloudWatch log group not created. Independent of data collection — either can finish first.
3. **Video** `reports/VIDEO_SCRIPT.md` exists, `SUBMISSION_CHECKLIST:37` script ✅ `38` record ⏳ — needs OBS 1080p with checkerboard + two glasses + second lighting demo (LOOK timestamps) and safety lines verbatim.
4. **Clean-machine + secret history scrub** — `SUBMISSION_CHECKLIST:22` second machine ⏳; `.env` now redacted to empty `GEMINI_API_KEY=` ` .env:1` and `git log --all --full-history -- .env` empty (never tracked, `git check-ignore` confirms `.env*` ignored), but `git log -p` shows `AQ.Ab8…` only in `tool_selector.py:7` comment placeholder diff, not real key — prior history does **not** contain real secret (verified `git log -p | grep AQ\.Ab8` only docstring). Still, must run `git rm --cached .env` if ever tracked (not needed now) and owner must paste new key from `aistudio.google.com` before any live Gemini test.
5. **Statistical claims** — `run_experiments.py` now water-aware (borderline requires `REVIEW` not any, `C` wires `track_across_frames` with exposure-perturbed `frame2` `220`, `calibrate_thresholds.py` measures `pattern_visibility` `153`), but headline `A/B/B2/C` table cannot be trusted until real photos (currently synthetic `C 0.875, B2 1.0` etc. from `scripts/run_experiments.py` dry-run).

---

## 4. Last self-audit score (strict, 2026-09-04 pre-fix)

**58/100** — `92125ec` water pivot landed on landing page only. Breakdown (Devpost Overall rubric):
- Technical Execution 30% → 16/30 (substantive OpenCV5 + tests, but thresholds synthetic, second look stubbed)
- Innovation 20% → 12/20 (narrow Secchi claim honest, but experiment wiring incomplete)
- Real-World Impact 20% → 12/20 (India water story strong + safety banner, no field pilot)
- UX 10% → 6/10 (landing distinctive, trace still purple/print fields)
- Docs 10% → 7/10 (report filled but `[PENDING]`, video script only, secret in `.env`)
- Cloud/Repro 10% → 5/10 (pinned deps + offline tests + Mangum, but no live URL, no second-machine)

**After this fix pass (expected, not yet re-scored):** trace unified, second look real (`track_across_frames` reachable with two lightings, `frame_info` audit trail), calibration/eval water-aware, deploy scripted, secret redacted, LICENSE + consent added. Re-audit needed on live deployment + real photos to move 58→~78.

---

## 5. Known gaps — priority order (this session’s fix list is 1–7 done)

1. **[DONE] Security:** `.env` rotated to empty (was `AQ.Ab8…` flagged twice, now `GEMINI_API_KEY=` ` .env:6`), confirmed `git ls-files` not tracked and `.gitignore:2` `.env*`; `LICENSE` MIT + `data/README.md` consent added. Owner to paste new key — do **not** test live Gemini until then (fix pass instruction).
2. **[DONE] Trace unified:** `job/[id]/page.tsx` now renders `pattern_visibility/sharpness/pattern_found` + `ClarityGauge/Bar` `0.20/0.55` when `isWaterResult` else fdm fields, theme `#0a1628/#38bdf8` `379`, copy `Checking water clarity…` `324`, header `Droplets/Waves` `379`, second lighting prompt `343` conditionally on `UNCERTAIN`.
3. **[DONE] Second look real:** `main.py:419` `image2` + `lighting`/`lighting2` + `original_job_id` → `FRAME_CACHE` `107` → `track_across_frames([frame, frame2])` `562` with `frame_info` `LOOK 1…→ LOOK 2` `640` + `frame_info` persistence note `568`; frontend prompt `job/[id]/page.tsx:343` `handleSecondSubmit` → `POST /api/inspect` with `original_job_id` → new job. Single-request `image+image2` and follow-up `original_job_id+image` both verified via `TestClient` (see `main.py` verification below).
4. **[DONE] Tooling water-aware:** `calibrate_thresholds.py:45` imports `measure_pattern_visibility`, collects `pattern_visibility/sharpness` per label, `suggest_thresholds` `374` gap-based for water (`clear` vs `turbid/borderline`), `print_report` `381` shows water metrics; `run_experiments.py:73` `CLEAR/TURBID` verdicts, `borderline` tightened to `REVIEW` only, `C` wires `track_across_frames` with exposure-perturbed `frame2` `213`, dry-run dataset `profile-aware` `86`.
5. **[READY] Deploy:** `scripts/deploy_lambda.sh:1` follows `README_DEPLOY_LAMBDA.md:1` (ECR→buildx arm64→Lambda 1024 MB/30s→Function URL NONE + public permission→Vercel `INFERENCE_API_URL`), plus Dynamo `PAY_PER_REQUEST` + billing `$1` tripwire reminder. Owner does IAM/billing steps when prompted, then script runs one-pass.
6. **[UPDATED] Video script:** `VIDEO_SCRIPT.md:51` wow moment now includes second lighting prompt `lighting selector` + `LOOK 1→LOOK 2` timestamps + `persistence_std`, `1:50` side-by-side persistence, `Rehearsal Notes` backlight demo. Drift flagged: before fix, second look was simulated crop — script updated, app now matches.
7. **[VERIFY NEXT] Real data + live deploy independent:** capture `data/self_captured` (A4 checkerboard behind glass, two lightings per sample) → `calibrate` → `run_experiments --profile water_turbidity_v1` → fill `technical_report.md §5` table; run `deploy_lambda.sh` with creds → `curl /version` shows both profiles.

---

## 6. How to verify (one-liners)

```bash
# Synthetic still passes without key/AWS
python -m pytest tests -q            # 43 passed, 1 skipped (services/inference)
npm run build                         # apps/web → ✓ Compiled + 5/5 static

# Water two-lighting real (after this fix)
python -c "import cv2; from fastapi.testclient import TestClient; from main import app; ... # see main.py verification: single borderline → track_across_frames, same-request image+image2 → frames 2 with lighting ambient/backlight, follow-up original_job_id+image → frames 1→2"

# Calibration now water-aware
python scripts/calibrate_thresholds.py data/self_captured --json /tmp/cal.json  # suggests pattern_visibility_confident_turbid/clear

# Experiments now water-aware and borderline strict
python scripts/run_experiments.py --profile water_turbidity_v1  # C now wires track_across_frames, conditional_benefit not artificially zero
```

---

## 7. Changelog (every session appends dated entry, honest state)

- **2026-09-04 — Strict self-audit 58/100** (`92125ec`): landing water-themed, trace still purple/print fields, second look stubbed to `reinspect_roi`, calibration/eval fdm-only, `.env` leaked `AQ.Ab8…`, no live URL/video/real data. Audit filed as `technical_report.md` + checklist truth.
- **2026-09-04 — Fix pass (this session, Phases 1–7):** security `.env` redacted + `LICENSE` + `data/README`, trace unified to water (ClarityGauge, water theme, dual-profile rendering), second look real two-lighting via `image2`/`original_job_id` + `FRAME_CACHE` + `frame_info` LOOK timestamps + frontend prompt, tooling extended to water (`pattern_visibility` calibration + `track_across_frames` in `C` + `REVIEW`-only borderline), deploy scripted `scripts/deploy_lambda.sh`, video script updated for second lighting. Verified: `43 passed` + `build ✓` + `track_across_frames` reachable (same-request and follow-up) with `frames` audit trail. Pending: real water photos + live deploy + recording (independent, either order).
- **Next:** owner pastes new `GEMINI_API_KEY`, runs `deploy_lambda.sh`, captures `data/self_captured` two-lighting set, re-runs calibration/experiments, records video per `VIDEO_SCRIPT.md`, then final re-audit.

---

## 8. Links

- `README.md` quickstart + water caveats
- `services/reports/technical_report.md` §1 water problem, §2 pipeline, §7 responsible-use, §8 setup
- `reports/VIDEO_SCRIPT.md` timed outline (second lighting demo)
- `reports/ARCHITECTURE.md` + `reports/SUBMISSION_CHECKLIST.md` (submission package)
- `services/reports/_phase_b_verification.json` synthetic Phase B evidence (not results table)
- `scripts/deploy_lambda.sh` + `services/inference/README_DEPLOY_LAMBDA.md`

