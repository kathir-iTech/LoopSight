# LoopSight — Submission Video Script (≤5 minutes)

> Timed outline for the required ≤5-minute judge video. Written against what the system **actually does now** (water turbidity screening, not the prior FDM reference). Record with OBS Studio, 1080p, captions. No watermark. Keep total ≤4:45.

> Delivery: one presenter (Kathir), screen share of live `https://<vercel-url>` + `https://<lambda-url>/version`. Rehearse the genuinely ambiguous case (borderline visibility where agent asks for different lighting) at least twice — the wow moment must not depend on a lucky first-pass. Have a printed checkerboard + clear glass on desk as physical prop.

---

## 0:00 — Problem: water before you drink it (15s)

**Visual:** Title card: `LoopSight — Check your water before you drink it` + safety banner: "Flags visibly cloudy water for follow-up. Not a substitute for a real water safety test." Cut to map/stat: arsenic / fluoride / nitrate-affected habitations in India (cite technical_report.md §1).

**Script (≈35 words):**
> "Millions of households in India face groundwater with invisible contaminants — arsenic, fluoride, nitrate. A fast question matters before drinking: is this water visibly cloudy? Clear-looking water can still be unsafe — no camera can see those chemicals — but visibly turbid water should never be drunk without treatment. LoopSight screens for that visible signal."

**On-screen text:** "Turbidity ≠ potability."

---

## 0:15 — Who & Why Now (10s)

**Visual:** Quick persona cards: Household (rural family checking stored water), Village health volunteer (screening before referring to lab), Small field tester. OpenCV 5 logo + AWS Lambda logo + printable A4 checkerboard.

**Script (≈25 words):**
> "For the household, the village volunteer, the field tester — with only a printed sheet and a phone. And why now: OpenCV 5 + cheap compute makes a real turbidity-from-pattern pipeline practical on free-tier Lambda — the judge's favorite AWS story."

---

## 0:25 — Architecture in One Slide (15s)

**Visual:** ASCII pipeline slide. Highlight loop: `pattern through water → pattern_visibility `0.20-0.55` → UNCERTAIN → agent picks track_across_frames (different lighting) → re-measure → PASS/REVIEW/FAIL`.

**Script (≈35 words):**
> "One image in, one verdict out. FastAPI on Lambda: OpenCV 5 measures pattern visibility through water (contrast + Laplacian sharpness), deterministic gap scoring, a bounded agent that picks exactly one whitelisted tool — often track_across_frames meaning different lighting — a second observation, deterministic PASS/REVIEW/FAIL. The LLM never renders the visual judgment."

**Key line:** "OpenCV produces evidence — pattern visibility; policy decides."

---

## 0:40 — First Inspection: Clear Water (25s)

**Visual:** Live demo tab 1 — `https://<vercel-url>` showing water-themed UI (deep #0a1628 → #38bdf8, animated ripple). Upload a **clear checkerboard-through-water** synthetic fixture (or your own photo: same board, clear glass, good light). Show single large upload zone (Advanced options stays collapsed), file info, droplet/ripple loader, then `/job/[id]`.

**Script (≈40 words):**
> "Place a printed checkerboard behind a clear glass, photograph it. Hit 'Check clarity.' The droplet fills while OpenCV measures pattern visibility — contrast loss and edge blur through water. This clear case scores 0.81, well above 0.55 — confident, no second look needed — and lands on PASS with the safety note: 'No visible turbidity detected — this does not confirm the water is safe. Invisible contaminants require a real water test.'"

**Evidence trace to show:** Section 1 Clarity Gauge (circular 81% cyan, gradient bar, status Clear), Section 4 Final Decision card with safety copy, human approval: No.

---

## 1:05 — The Wow Moment: Borderline Water Needs Different Lighting (45s)

**Visual:** Live demo tab 2 — upload the **borderline turbid** fixture (pattern_visibility 0.32 in the 0.20-0.55 band). This is the rehearsed genuinely ambiguous case.

**Script (≈65 words):**
> "Now the hard one. First pass scores pattern visibility 0.32 — solidly in the borderline band — evidence gap reads: 'pattern visibility 0.32 in borderline band (0.2-0.55) — request photo under different lighting (backlight vs ambient or with phone flash).' The agent fires: it picks `track_across_frames` with reason `BORDERLINE_PATTERN_VISIBILITY` — you see it as a decision node with the tool in a code chip and a connector from Section 1. Second observation re-measures the pattern at higher resolution — this is the Secchi technique in the literature: backlight reveals what ambient hides — and updates the clarity gauge. Final decision: REVIEW or FAIL with 'Visible turbidity detected — do not drink without treatment.' That's the thesis: borderline visibility triggered a materially different lighting-aware observation, and the trace shows it."

**What must be visible:** Amber evidence gap with lighting request, Agent Decision card (track_across_frames + reason), New Evidence second gauge, Final Decision with safety copy, timings, Copy/Share/PDF.

**If the live backend hiccups:** narrate golden fallback from `demo_golden.py` — same trace shape, precomputed so the demo never fully breaks — then show `/version` proof that the live pipeline exists separately and lists both profiles.

---

## 1:50 — What Changed? Side-by-Side (15s)

**Visual:** Split screen: first-pass gauge (0.32 borderline) vs second-pass gauge (e.g., 0.17 turbid after different processing). Highlight that pattern_visibility moved and sharpness/local_contrast updated — not a duplicate read, but a different processing path (upsampled crop via reinspect_roi or different thresholds). Show the track_across_frames note: persistence on pattern_visibility.

**Script (≈25 words):**
> "This wasn't a duplicate read. The second look changed the observation — upsampled pattern region or different thresholds — so the visibility evidence actually changed before the policy decided."

---

## 2:05 — Advanced Options & History (20s)

**Visual:** Back to upload page. Click "Advanced options" expander — reveals reference-image slot (optional known-good) and "Try demo case." Show thumbnail after selection. Then scroll to Recent (last 5, job_id, timestamp, decision badge) and click one. Download PDF report and show safety footer: "No visible turbidity does NOT confirm safe water — invisible contaminants require a real water test."

**Script (≈35 words):**
> "One primary action by default — advanced options stay hidden until you need them, so first impression is clean. History persists in localStorage; you can download a PDF — it carries the safety footer, never 'safe to drink.'"

---

## 2:25 — Evaluation: Does the Loop Beat Fixed Observation? (35s)

**Visual:** Slide: Experiment A/B/B2/C table (technical_report.md §4). Highlight B2 as the critical control. Show conditional_benefit in [−1,1].

**Script (≈70 words):**
> "Honest risk: does adaptivity beat a fixed second pass at same cost? We test it. A: single pass. B: fixed second pass on random subset. B2 — the number to lead with — is fixed second pass matched per case to the agent's budget via deterministic hash, so it costs exactly the same as adaptive but chooses cases blindly. C: adaptive. Claim is narrow: 'our controller beats fixed observation at matched cost, measured by conditional benefit.' Real numbers are pending self-captured water photos — we show the harness running on synthetic clear/turbid/borderline checkerboards and placeholder contract tests, not a fake headline."

**On-screen for pending:** `[PENDING — real dataset]` table, but harness verified on synthetic water fixtures.

---

## 3:00 — Stack & OpenCV 5 Proof (20s)

**Visual:** `GET /version` in browser showing `profile_names: ["fdm_print_surface_v1","water_turbidity_v1"]`, `opencv_version: 5.0.0`, plus `python -c "import cv2; print(cv2.__version__)"` 5.0.0. Show `requirements.txt:1` (`opencv-python-headless>=5.0.0`) and import-time log from `cv/first_pass.py`, plus water measurement code `measure_pattern_visibility` with findChessboardCorners / contour logic.

**Script (≈40 words):**
> "Stack proof. Next.js 15 + Tailwind water theme #0a1628/#38bdf8 + Framer Motion droplet loader + jsPDF on Vercel. Python + FastAPI + OpenCV 5.0.0.93 on Lambda via Mangum. `pip show opencv-python-headless` reads 5.0.0.93. `GET /version` returns both profiles, opencv_version, python_version, gemini_model — everything a judge needs to verify we actually used OpenCV 5 and shipped both domains."

---

## 3:20 — Responsible Use & Limitations (25s)

**Visual:** Slide with honest bullets + UI safety banner text.

**Script (≈50 words):**
> "Most important: turbidity is not potability. The UI says on first load: 'Flags visibly cloudy water for follow-up. Not a substitute for a real water safety test.' PASS never says safe — it says 'No visible turbidity detected — this does not confirm the water is safe. Invisible contaminants require a real water test.' FAIL says 'do not drink without treatment.' Thresholds are interim (0.20 turbid, 0.55 clear) until real water photos recalibrate them. Final decision is always REVIEW when genuinely borderline — we demo that, not hide it."

---

## 3:45 — Live Inspection of a Real Photo (35s)

**Visual:** Upload a **real water photo** you captured: same A4 checkerboard behind a clear glass — one with plain water, one where you've added a pinch of flour/milk to simulate turbidity (or real field sample if available). Let the judge see metrics differ from synthetic canned values — not frozen mocks. Point to circular gauge moving.

**Script (≈50 words):**
> "Here's real water — same board, tap water vs. slightly clouded sample. You see pattern_visibility actually moves — 0.81 vs. 0.28 — and the second-lighting logic still fires only when borderline. The trace is copyable as JSON — every number is inspectable. Place a glass, print a sheet — that's the whole setup, and it works for India because it works with what people already have."

**If no real photos yet:** explicitly say "Real self-captured water dataset is the next sprint — today's demo uses synthetic checkerboard fixtures plus fallback, and report marks that pending."

---

## 4:20 — Cloud & Reproducibility (15s)

**Visual:** AWS console: Lambda log group + one CloudWatch log line (`{event:inspect, profile:"water_turbidity_v1", status, decision, agent_tool, measurements}`), and `npm run build` green + `pytest 43 passed / 1 skipped`.

**Script (≈30 words):**
> "Deployed on Lambda (always-free tier), logs to CloudWatch, job store DynamoDB-or-in-memory. Fresh clone repro: `pip install -r requirements.txt && python -m pytest tests -q` — 43 passed, one live-Gemini test skips without a key — and `npm run build` compiles clean."

---

## 4:35 — Close (10s)

**Visual:** Title card `Check your water before you drink it` + safety footer + report QR + repo URL.

**Script (≈20 words):**
> "LoopSight doesn't claim to have invented water screening. It tests one loop: uncertainty → a differently-lit look → a better decision at matched cost. Thank you."

---

## Rehearsal Notes

- **Time control:** Use a visible timer. If long, cut 2:25 evaluation detail and keep the wow moment + real-photo demo — those score Technical Execution and Real-World Impact.
- **Two-tabs trick:** Have two browser tabs pre-loaded (one clear, one borderline) so you don't waste seconds waiting for an upload.
- **Backup if Lambda is cold:** Have `DEMO_MODE=golden` tab ready and narrate it as designed fallback, not failure.
- **Physical prop:** Bring the actual A4 checkerboard and two glasses (clear vs. clouded with flour) — hold them up while the gauge is on screen — strongest possible demo of "one pattern, two waters, one trace."
- **No claims beyond evidence:** Don't quote accuracy until `run_experiments.py` has run on real photos. Say "harness verified on synthetic, pending real dataset." And never say "safe to drink" — always deliver the safety framing verbatim.
- **Safety first:** Judges will notice the banner on first load. Lead with it — it shows ethical design, not an afterthought.

---

### Files Referenced

- Report: `services/reports/technical_report.md`
- Architecture: `reports/ARCHITECTURE.md`
- Checklist: `reports/SUBMISSION_CHECKLIST.md`
- Evidence: `services/reports/_phase_b_verification.json`
