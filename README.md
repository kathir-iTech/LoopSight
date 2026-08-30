# LoopSight

Uncertainty-triggered active-perception inspection agent — OpenCV AI Competition 2026.

## What's actually implemented and tested here (as of this commit)

- `services/inference/cv/first_pass.py` — deterministic first-pass measurement + evidence-gap scoring, domain-agnostic via `InspectionProfile`
- `services/inference/cv/tools.py` — the 4 whitelisted reinspection tools
- `services/inference/cv/policy.py` — the deterministic final-decision policy
- `services/inference/agent/tool_selector.py` — bounded agent tool selection, whitelist-enforced, with a mock mode and a fallback for both malformed *and* failed (network/429/timeout) agent calls
- `services/inference/tests/` — 19 tests, all passing, run with `python3 tests/test_*.py`. Synthetic images stand in for real print photos until the self-captured dataset exists.

## Honest caveats — read before trusting this against a deadline

1. **Tested against OpenCV 4.13, not OpenCV 5** — this sandbox has no network access to install OpenCV 5. The operations used (Canny, findContours, absdiff) are source-compatible per the spec's verified research, but re-run the full test suite against real OpenCV 5 before submission.
2. **Thresholds in `PROFILES["fdm_print_surface_v1"]` are uncalibrated placeholders.** Real test runs show measured `edge_continuity` values in the 0.01–0.24 range on synthetic images — well below the 0.35/0.85 guessed thresholds. The relative signal (broken < clean) is proven; the absolute cutoffs need recalibrating against real labeled photos.
3. **`call_gemini()` in `tool_selector.py` has never actually been called** — no API key/network in this environment. It's written against the documented API shape; verify it directly against a real key before the demo.
4. **Reference-image comparison is naive (raw pixel `absdiff`)** — flagged by an external adversarial review as fragile to lighting/exposure differences between the reference photo and a live capture, and that critique is correct. This needs a lighting-normalization step (histogram equalization at minimum) before it's demo-ready. Not yet fixed here — next thing to build.
5. **No AWS/Docker/COOL deployment exists yet.** Everything above runs locally. Per the spec's own phase plan, that's deliberate — Phase 6, not Phase 1.

## Quick start

```bash
cd services/inference
python3 tests/test_first_pass.py
python3 tests/test_tools.py
python3 tests/test_tool_selector.py
python3 tests/test_integration.py
```

See `LoopSight_Project_Spec.md` (repo root) for the full architecture, evaluation plan, and build phases.
