# LoopSight — Check your water before you drink it

Uncertainty-triggered active-perception water-turbidity screener — OpenCV AI Competition 2026. Photograph a printed checkerboard through a clear glass of water; LoopSight measures how much the pattern fades — the same Secchi-disk / turbidity-tube principle, now with agentic second look under different lighting.

> **Safety: turbidity is NOT potability.** Clear-looking water can still carry arsenic, fluoride, or nitrate — invisible to any camera. LoopSight flags *visibly cloudy water* for follow-up; it never says "safe to drink." See Honest caveats §7 and the UI's first-screen banner.

## What's actually implemented and tested here (as of this commit)

- `services/inference/cv/first_pass.py` — deterministic first-pass measurement + evidence-gap scoring, domain-agnostic via `InspectionProfile` (`water_turbidity_v1` primary, `fdm_print_surface_v1` kept as fallback). Water path uses `measure_pattern_visibility(frame, roi)` — checkerboard/grid detection via `cv2.findChessboardCorners` or contour square count, then contrast attenuation + Laplacian sharpness + edge-density blend into a `pattern_visibility` score in 0..1.
- `services/inference/cv/tools.py` — the 4 whitelisted reinspection tools; for water `track_across_frames` is reframed as the primary "different lighting" tool (backlight vs ambient / phone flash), `reinspect_roi` re-measures the pattern region at higher effective resolution, `measure_edge_continuity` re-processes at different Canny thresholds
- `services/inference/cv/policy.py` — the deterministic final-decision policy (water branch checks `pattern_visibility` against 0.20 turbid / 0.55 clear; fdm branch unchanged)
- `services/inference/agent/tool_selector.py` — bounded agent tool selection, whitelist-enforced, with a mock mode and a fallback for both malformed *and* failed (network/429/timeout) agent calls; `call_gemini` is network-timeout-bounded (`GEMINI_TIMEOUT_SECONDS`, default 15) so a dead key can never hang the suite
- `services/inference/main.py` — FastAPI `/inspect` endpoint with upload validation (`MAX_UPLOAD_BYTES` = 10 MiB, 413 on oversized), `inspection_profile` dispatch (default `water_turbidity_v1`, both profiles listed at `GET /version`), a golden-result demo fallback, and the deterministic final policy
- `services/inference/scripts/run_experiments.py` — evaluation harness (Experiments A/B/B2/C, `run_all`, `print_report`), dry-runnable on synthetic fixtures (now includes water checkerboard fixtures: clear / turbid / borderline)
- `services/inference/tests/` — 44 tests (43 passing + 1 live-Gemini integration test that skip()s unless a key is provisioned), run with `python -m pytest tests/`. Synthetic images stand in for real water photos until self-captured dataset exists. CI (`.github/workflows/test.yml`) runs this suite plus a Next.js build.
- `apps/web` — water-themed UI: deep `#0a1628` → clear `#38bdf8` gradient, animated ripple/wave background, radically simplified landing (one primary upload zone; reference & demo behind "Advanced options"), Framer Motion droplet/ripple loader, water-clarity gauge (circular + gradient bar) in evidence trace

## Domain pivot — why water turbidity

Desktop 3D-print QC is a crowded demo space and a weak "won't work for India" story. Household drinking-water turbidity screening is a large, named, India-grounded problem (arsenic/fluoride/nitrate groundwater contamination affecting a serious number of habitations) where LoopSight's actual mechanism — *uncertain → agent picks a second, differently-lit look → resolve* — is not already answered by another method and provides genuinely strong visual material (water/clarity identity instead of defect-inspector aesthetic). The printable checkerboard behind a glass is the Secchi-disk principle; the agent's second look asking for a different lighting condition is the real-world technique that resolves borderline visibility. `fdm_print_surface_v1` is retained as a legacy/secondary profile, documented but not primary.

## Honest caveats — read before trusting this against a deadline

1. **Verified against OpenCV 5.0.0** — `cv2.__version__ 5.0.0` logged at import and via `GET /version`. Prior note about 4.13-only is now resolved (re-run at 43 passed / 1 skipped against 5.0.0).
2. **Thresholds are interim and synthetic-calibrated.** `PROFILES["water_turbidity_v1"]` uses `pattern_visibility_confident_turbid=0.20, clear=0.55, contrast_min=0.05` calibrated on synthetic checkerboard fixtures (clear ~0.81, turbid ~0.12, borderline ~0.32). `fdm_print_surface_v1` retains its interim `0.05/0.20` from synthetic edge_continuity. Both need recalibration against real photos.
3. **`call_gemini()` in `tool_selector.py` has never succeeded live** — the shipped key is placeholder; must regenerate at aistudio.google.com. The call path is verified against the documented API shape and is network-timeout-bounded so it fails fast; verify against a real key before the demo.
4. **Reference-image comparison is lighting-normalized (equalizeHist)** — prior fragility is fixed for fdm; water profile does not rely on reference similarity as primary signal (pattern visibility owns the decision).
5. **No AWS/Docker/COOL deployment exists yet beyond local Lambda packaging.** Deploy via `services/inference/Dockerfile.lambda` + ECR to `AWS Lambda arm64`; the harness is local-first per spec phase plan.
6. **Turbidity ≠ potability — safety limitation.** A clear visibility score does NOT mean safe to drink. See Responsible Use in `services/reports/technical_report.md`. UI never says "safe"; it says "No visible turbidity detected — this does not confirm the water is safe."
7. **Statistical claims are blocked on real photos.** `scripts/run_experiments.py` proves the harness runs on synthetic fixtures, but the A/B/B2/C headline numbers must be regenerated against the labeled self-captured dataset (`data/self_captured/`) — see `services/reports/technical_report.md`, sections marked `[PENDING — real dataset]`.

## Quick start

```bash
cd services/inference
python -m pytest tests -q        # full suite; 43 pass + 1 gemini test skips without a key (verify current count with your own terminal, not this README)

# Default profile is now water_turbidity_v1. To test fdm:
# curl -F "image=@print.jpg" -F "inspection_profile=fdm_print_surface_v1" http://localhost:8000/inspect
```

The suite (first-pass, tools, tool-selector, policy, integration, e2e, demo golden-path,
input-hardening, experiments) runs on synthetic fixtures and needs no network, no AWS, and no
Gemini key. `scripts/_verify_end_to_end.py` and `tests/test_e2e_local.py` exercise the real stack
end-to-end; `scripts/run_experiments.py` runs the Experiment A/B/B2/C harness.

## Water checklist — printable pattern

Print a high-contrast checkerboard or grid on any A4 sheet (black/white). Place it behind or under a clear glass/cup, photograph it with and without water. The web UI's instructions show this; the same pattern is what `measure_pattern_visibility` detects via `cv2.findChessboardCorners` or contour square counting, then measures contrast attenuation and edge sharpness through the water.

See `LoopSight_Project_Spec.md` (repo root) for the full architecture, evaluation plan, and build phases. `services/reports/technical_report.md` §7 has the responsible-use / safety framing and real-world-impact section for water.
