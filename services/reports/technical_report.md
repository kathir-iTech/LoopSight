# LoopSight — Technical Report (Skeleton)

> **Status: skeleton.** All sections marked `[PENDING — real dataset]` or `[PENDING — real numbers]`
> must be backfilled from real test results before submission (spec Section 14: *"this should be
> written from real test results, not drafted generically and backfilled"*). Every other section
> below is written from code that exists and runs.
>
> Environment used to produce this skeleton: `cv2.__version__ = [PENDING]` (record as required
> competition evidence), Python 3.13 target, `google-genai 2.20.0`.

---

## 1. Problem

Desktop 3D-printing (FDM) users and small print-farm operators lack an inspection tool that acts on
visual *uncertainty* rather than reporting a one-shot confidence score. Existing options fall into
two camps (spec Section 8):

- **Single-shot "AI failure" plugins** (e.g. OctoPrint/Obico-style) that flag catastrophic
  spaghetti failure but do not reason about ambiguous, partial, or early-stage defects.
- **Fixed-budget frameworks** (academic and hobbyist: Holzmond & Li 2017, Jin et al. 2019,
  Petsiuk & Pearce 2022) that observe once per checkpoint and commit to a verdict.

Both treat a single observation as final. LoopSight's thesis is narrower and falsifiable
(spec Sections 4, 9): **an inspection controller that decides, from the evidence it already has,
which materially-different OpenCV observation to obtain next, can beat a fixed observation budget
at matched cost.** It is not a claim to have invented visual defect inspection; it is a test of one
specific active-perception policy.

Honest risk, stated up front (spec Section 1): the adaptive-reinspection mechanic may turn out not
to beat a simpler fixed two-pass heuristic. That is the specific thing Experiments A/B/B2/C
(§4) are built to measure, and a documented fallback policy exists regardless of the outcome.

## 2. Architecture

Pipeline, one image in → one verdict out (spec Section 9/12):

```
image ─► first-pass (OpenCV 5 classical: edges/contours/SSIM)
          │
          ├─ CONFIRM ─► deterministic verdict (PASS/REVIEW/FAIL)
          │
          └─ UNCERTAIN ─► evidence-gap score
                            │
                            ▼
               bounded agent (selects 1 of a small whitelist of OpenCV tools)
                            │
                            ▼
                       second observation ─► deterministic final policy
```

Key design constraint (spec Section 9, enforced in `main.py` and the tools module): **OpenCV 5
produces evidence; the final PASS/REVIEW/FAIL decision is deterministic and policy/evidence-driven;
the model's only job is choosing which OpenCV tool to run next.** The LLM never renders the visual
judgment itself — this is what keeps the system "AI-core, not a wrapper" and keeps a false
confidence signal from reaching the user unchecked.

### Components (implemented)

- `services/inference/main.py` — FastAPI `/inspect` endpoint; upload validation
  (`MAX_UPLOAD_BYTES = 10 MiB`), `inspection_profile` dispatch, golden-result demo fallback,
  deterministic final policy, `human_approval_required` gate.
- `services/inference/first_pass.py` — OpenCV 5 first-pass measurement and evidence-gap scoring
  (CONFIRM vs. UNCERTAIN, evidence-gap reasons).
- `services/inference/agent/tool_selector.py` — bounded agent; `call_gemini` selects `{tool,
  arguments, reason_code}` from a whitelisted tool set; `max_agent_steps` cap; network timeout
  bound (`GEMINI_TIMEOUT_SECONDS`).
- `services/inference/tools/` — whitelisted OpenCV second-look operations (tighter crop,
  lighting-normalized measurement, reference comparison).
- `apps/web/` — Next.js evidence-trace UI: first look → uncertainty → chosen next action → new
  evidence → final decision.

Security/human-control properties that ship in v1, not documented-only (spec Section 26):
least-privilege IAM, `max_agent_steps` rate-limit defense, whitelisted (not free-form) tool set,
and a real `human_approval_required` enforcement gate.

## 3. Evaluation

The central question (spec Section 14): **does adaptive reinspection beat a fixed second-pass
heuristic at matched cost?**

| Experiment | Question | Status / result |
|-----------|----------|-----------------|
| A | Fixed single-pass baseline | Implemented; `trigger_rate = 0` by design |
| B | Fixed second-pass at matched cost | Implemented; `conditional_benefit` metric |
| B2 | Fixed second-pass matched to the agent's cost distribution | Implemented; deterministic per-case matched budget |
| C | Adaptive (agent) second-look | Implemented; the claim under test |
| D | COOL (AWS Graviton) baseline-vs-optimized delta | `[PENDING — AWS deployment]` |
| E | Robustness / adversarial & ambiguous cases | `[PENDING — real cases]` |

Metric: `accuracy`, `trigger_rate`, `conditional_benefit` (bounded), CPU/latency.

Implementation status:
- Harness `scripts/run_experiments.py` runs A/B/B2/C on synthetic fixtures end-to-end and prints a
  report (`run_all` + `print_report`).
- Experiment B2 uses a deterministic per-case hash to match the agent's budget, so it is stable and
  per-case rather than all-or-nothing (spec: "beats fixed observation at matched cost" — B2 is the
  matched-cost control, and is the number to lead with in front of a judge who has seen
  OctoPrint/PrintGuard, spec Section 20).

Real numbers: `[PENDING — real dataset]`. Placeholder contract tests assert that B2 is
cost-matched and `conditional_benefit` is bounded, but the headline accuracy table must be filled
from `data/self_captured/` measurements recorded via `scripts/run_experiments.py`.

## 4. Results

`[PENDING — real dataset; replace this section with the A/B/B2/C table from `scripts/run_experiments.py`]`

## 5. Limitations

Honest, from real test results (spec Section 14 Experiment E, Section 20). To be completed with at
least one genuinely ambiguous/adversarial failure case handled gracefully, ending in `REVIEW`.

- `[PENDING — real dataset]` Dark-filament contrast bias (spec Section 20: bias/fairness).
- `[PENDING]` Stale-buffered-frame risk in live/video mode (spec Section 20 Revision 2 note).
- `[PENDING]` Real failure cases from Experiment E.

## 6. Responsible Use

- Stakes are **moderate, not safety-critical** (spec Section 20): a wrong verdict wastes filament
  and print time — a real but recoverable cost, and one worth stating because it keeps the
  product's liability/disclaimer burden lower than a safety-monitoring pitch would carry.
- Product-shown disclaimer: *"LoopSight is a decision-support tool for print-quality inspection. It
  does not guarantee defect-free output and should not be the sole basis for high-stakes or
  safety-critical part decisions."*
- Data licensing: self-captured data ships in the public repo. Any MVTec-family reference is
  internal-validation-only and **never redistributed** (CC BY-NC-SA 4.0, spec Section 13). Any added
  detector library gets its license checked individually (YOLO is AGPL-3.0-only; Apache-2.0
  alternatives exist).
- IP: only the report/video/architecture package is included in the competition's submission
  license grant; the private code/dataset stays outside it (spec Section 3).
- Transparency: the evidence-trace UI is the system's transparency story — a judge sees exactly
  what was measured and why.

## 7. Setup & Reproduction

`[PENDING — pinned dependency versions + fresh-clone setup instructions; verify in Phase 4/5 on a
clean machine per spec Section 18.]`

## 8. Appendix: Build Progress Evidence

Cross-referenced artifacts already produced in this repo:

- Phase B real-stack end-to-end evidence: `services/reports/_phase_b_verification.json`.
- Evaluation harness + tests: `services/inference/scripts/run_experiments.py`,
  `services/inference/tests/test_run_experiments.py`.
- CI workflow: `.github/workflows/test.yml` (inference pytest suite + Next.js build; the live
  Gemini test skip()s in CI via `GEMINI_API_KEY=disabled`).