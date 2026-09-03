# LoopSight — Submission Video Script (≤5 minutes)

> Timed outline for the required ≤5-minute judge video. Written against what the system **actually does now** (not what was planned). Record with OBS Studio, 1080p, captions. No watermark. Keep total ≤4:45 to allow for intro/outro buffer.

> Delivery: one presenter (Kathir), screen share of live `https://<vercel-url>` + `https://<lambda-url>/version`. Rehearse the genuinely ambiguous case (the `uncertain` fixture) at least twice — the wow moment must not depend on a lucky first-pass. Have 2–3 physical printed samples on desk as backup.

---

## 0:00 — Problem (15s)

**Visual:** Title card: `LoopSight — Uncertainty-triggered visual inspection` + tagline. Cut to r/3Dprinting screenshot ("Is this normal or should I stop the print?").

**Script (≈35 words):**
> "Desktop 3D-printing users stare at a single photo and guess: is this a real defect or just light and filament color? Single-shot detectors flag spaghetti failure but don't reason about ambiguity. LoopSight treats uncertainty as something to act on, not something to report."

**On-screen text:** "One look is not a verdict."

---

## 0:15 — Who & Why Now (10s)

**Visual:** Quick persona cards: Weekend Maker (1–2 printers, checks periodically), Small Print-Farm Operator (bank of printers, wants a review queue). OpenCV 5 logo + AWS Lambda logo.

**Script (≈25 words):**
> "For the Weekend Maker and the small print-farm operator. And why now: OpenCV 5's rewritten DNN + CPU inference makes a real classical pipeline practical on free-tier compute — the judge's favorite kind of AWS story."

---

## 0:25 — Architecture in One Slide (15s)

**Visual:** ASCII diagram from `reports/ARCHITECTURE.md` rendered as a clean slide (or screen-share the markdown). Highlight the loop: `first-pass → UNCERTAIN → agent → second observation → deterministic policy`.

**Script (≈35 words):**
> "One image in, one verdict out. FastAPI on Lambda: OpenCV 5 first pass, deterministic evidence-gap scoring, a bounded agent that picks exactly one whitelisted OpenCV tool, a second observation, and a deterministic PASS/REVIEW/FAIL. The LLM never renders the visual judgment."

**Key line:** "OpenCV produces evidence; policy decides."

---

## 0:40 — First Inspection: Clean Case (25s)

**Visual:** Live demo tab 1 — `https://<vercel-url>`. Click "Try demo case" or upload a **clean synthetic square** (`confident_pass` fixture). Show drag-and-drop, file info (name/size/type), pulsing "Inspecting…" indicator (not just text), then redirect to `/job/[id]`.

**Script (≈40 words):**
> "Upload a print photo. Optionally add a reference — a known-good print for comparison. Hit Inspect. The progress bar pulses while OpenCV measures edge continuity, layer alignment, and reference similarity. This clean case is confident — no agent needed — and lands on PASS with no second look."

**Evidence trace to show:** Section 1 Perception (metric grid, status PASS), Section 4 Final Decision (green PASS, high confidence, human approval: No).

---

## 1:05 — The Wow Moment: Genuinely Ambiguous Case (45s)

**Visual:** Live demo tab 2 — upload the **ambiguous fixture** (`uncertain` — or your own photo that you have rehearsed to land in the middle band). This is the "rehearse the genuinely ambiguous case, not just the clean ones" object.

**Script (≈65 words):**
> "Now the hard one. First pass says UNCERTAIN — edge continuity 0.52 in the ambiguous middle band, evidence gap shown in the amber callout. The agent fires: it picks `measure_edge_continuity` with reason code `AMBIGUOUS_EDGE_BAND` — you see it as a decision node, with the tool name in a code chip and a connector arrow from Section 1. Second observation runs — same region, different Canny thresholds — and the metric grid updates labeled 'After second look.' Final decision: REVIEW, low confidence, human approval required. That's the whole thesis: uncertainty triggered a materially different observation, and the trace shows it."

**What must be visible:** Evidence gap in amber, Agent Decision card with connector, New Evidence grid, Final Decision REVIEW/amber, measurements timing (`decode_ms`, `first_pass_ms`, `agent_ms`, `second_pass_ms`, `total_ms`), "Copy trace as JSON" and "Download report" buttons.

**If the live backend hiccups:** narrate "This is the golden-result fallback path from `demo_golden.py` — same trace shape, precomputed so the demo never fully breaks," then show the `/version` proof that the live pipeline exists separately.

---

## 1:50 — What Changed? Side-by-Side (15s)

**Visual:** Split screen: first-pass metric grid vs. second-pass metric grid. Highlight that `edge_continuity` moved from 0.52 → 0.58 and `local_contrast` appeared (0.42) — the second observation was not a re-read, it was a different processing path (tighter crop upsampled 2× via `reinspect_roi` or re-thresholded via `measure_edge_continuity`).

**Script (≈25 words):**
> "This wasn't a duplicate read. The second look changed a real parameter — threshold pair, or upsampled crop — so the evidence actually changed before the policy decided."

---

## 2:05 — Reference Image & History (20s)

**Visual:** Back to upload page. Show the reference-image slot ("Upload reference image (optional) — a known-good print") with a thumbnail after selection. Then scroll to Recent inspections (last 5, job_id, timestamp, decision badge) and click one. Download a PDF report via "Download report" (jsPDF) and show the footer disclaimer.

**Script (≈35 words):**
> "Add a known-good reference and similarity actually means something — without it, the metric is hidden, not faked as 1.0. Recent inspections persist in localStorage, and you can download a PDF report — it even carries the disclaimer: 'not a certified inspection.'"

---

## 2:25 — Evaluation: Does the Loop Beat Fixed Observation? (35s)

**Visual:** Slide: Experiment table A/B/B2/C (from `services/reports/technical_report.md` §4). Highlight B2 as the critical control. Show `conditional_benefit` definition and that it is bounded in [−1, 1].

**Script (≈70 words):**
> "Honest risk up front: does adaptivity beat a fixed second pass at the same cost? We test it. A: single pass. B: fixed second pass on a random subset. B2 — the number to lead with — is fixed second pass matched *per case* to the agent's budget via a deterministic hash, so it costs exactly the same as the adaptive path but chooses cases blindly. C: adaptive. The claim is narrower than 'we invented defect detection' — it's 'our controller beats fixed observation at matched cost, measured by conditional benefit.' Real numbers are pending the self-captured dataset — we show the harness running on synthetic fixtures and placeholder contract tests today, not a fake headline."

**On-screen for pending:** `[PENDING — real dataset]` table, but harness verified.

---

## 3:00 — Stack & OpenCV 5 Proof (20s)

**Visual:** `GET /version` in browser or `curl http://localhost:8000/version` in terminal. Then `python -c "import cv2; print(cv2.__version__)"` showing `5.0.0`. Show `requirements.txt:1` (`opencv-python-headless>=5.0.0`) and the import-time log line from `cv/first_pass.py`.

**Script (≈40 words):**
> "Stack proof. Next.js 15 + Tailwind + Framer Motion + jsPDF on Vercel. Python 3.14 + FastAPI + OpenCV 5.0.0.93 on Lambda via Mangum. `pip show opencv-python-headless` reads 5.0.0.93. `GET /version` returns opencv_version, python_version, profile_names, gemini_model, build_timestamp — everything a judge needs to verify we actually used OpenCV 5."

---

## 3:20 — Responsible Use & Limitations (25s)

**Visual:** Slide with 3 honest bullets + disclaimer text as rendered in the UI footer.

**Script (≈50 words):**
> "Stakes are moderate — a wrong verdict wastes filament, not lives — and we show that. The footer reads: 'decision-support, not certified.' MVTec, if used, is internal-validation-only and never redistributed (CC BY-NC-SA). Thresholds are interim (fail 0.05 pass 0.20) until real photos recalibrate them. The final decision is always REVIEW when genuinely ambiguous — we demo that, not hide it."

---

## 3:45 — Live Inspection of a Real Photo (35s)

**Visual:** Upload a **real self-captured print photo** (clean + one with deliberate layer shift / under-extrusion) via camera or file picker. Let the judge see that the measurement values now differ from the synthetic canned values — not frozen mocks.

**Script (≈50 words):**
> "Here's a real print from our makerspace — a calibration cube, one clean, one with a deliberate layer shift from bad belt tension. You see the metrics actually differ, and the second-pass logic still fires only when the first pass says it must. The trace is copyable as JSON — every number is inspectable."

**If no real photos yet:** explicitly say "Real self-captured dataset is the next sprint — today's demo uses synthetic fixtures plus the fallback path, and the report marks that as pending."

---

## 4:20 — Cloud & Reproducibility (15s)

**Visual:** AWS console snippet: Lambda log group + one CloudWatch log line (`{event:inspect, profile, status, decision, agent_tool, measurements}`), and `npm run build` green + `pytest 43 passed / 1 skipped`.

**Script (≈30 words):**
> "Deployed on Lambda (always-free tier), logs to CloudWatch, job store is DynamoDB-or-in-memory. Fresh clone repro: `pip install -r requirements.txt && python -m pytest tests -q` — 43 passed, one live-Gemini test skips without a key — and `npm run build` compiles clean."

---

## 4:35 — Close (10s)

**Visual:** Title card + report QR code + repo URL.

**Script (≈20 words):**
> "LoopSight doesn't claim to have invented inspection. It tests one falsifiable loop: uncertainty → a materially different observation → a better decision at matched cost. Thank you."

---

## Rehearsal Notes

- **Time control:** Use a visible timer. If you run long, cut the 2:25 evaluation detail and keep the wow moment + real-photo demo — those score Technical Execution.
- **Two-tabs trick:** Have two browser tabs pre-loaded (one clean, one ambiguous) so you don't waste seconds waiting for an upload to process live.
- **Backup if Lambda is cold:** Have the `DEMO_MODE=golden` tab ready and narrate it as the designed fallback, not a failure.
- **Physical prints:** If presenting in person, hold up the real defective print while the evidence trace is on screen — strongest possible demo of "one defect, two observations, one trace."
- **No claims beyond evidence:** Don't quote an accuracy number until `scripts/run_experiments.py` has run on real photos. Say "harness verified on synthetic, pending real dataset."

---

### Files Referenced

- Report: `services/reports/technical_report.md`
- Architecture: `reports/ARCHITECTURE.md`
- Checklist: `reports/SUBMISSION_CHECKLIST.md`
- Evidence: `services/reports/_phase_b_verification.json`
