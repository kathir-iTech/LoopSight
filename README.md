# LoopSight v2 — Active-Perception Optical Nephelometry & Spatial Metrology Engine

> Current status: [strict technical review and ten-day build plan](reports/STRICT_TECHNICAL_REVIEW.md). The committed benchmark images are generated synthetic fixtures. Physical NTU/mm calibration, real-world accuracy and the live AWS deployment remain unverified. This project does not certify drinking-water potability or structural safety.

**LoopSight v2** is an uncertainty-triggered **OpenCV 5 Active-Perception & Model Context Protocol (MCP) Vision Engine** built for the **OpenCV AI Competition 2026 (powered by AWS)**.

Instead of treating a single camera frame as final—or letting an LLM hallucinate visual verdicts—LoopSight v2 uses **deterministic OpenCV 5 metrology** on Pass 1 to quantify both the primary signal and physical confounders (specular glass glare, perspective skew, vertical sediment stratification, dim ambient lighting, and surface shadows). When Pass 1 is `UNCERTAIN`, a bounded agent selects from **8 whitelisted OpenCV 5 tools** to acquire a materially different second observation before a deterministic policy (`cv/policy.py`) renders the final verdict.

## Key Highlights

- **3 Calibrated OpenCV 5 Inspection Profiles:**
  1. `water_turbidity_v1` — Household drinking-water optical nephelometry (Secchi checkerboard visibility, HSV specular glare masking, perspective skew detection, and 3-zone vertical sediment stratification).
  2. `structural_crack_metrology_v1` — Civil/structural crack inspection using bilateral noise suppression, morphological black-hat filament extraction, and Euclidean distance transform (`cv2.distanceTransform`) to measure calibrated **fracture width in millimeters (`mm`)**.
  3. `fdm_print_surface_v1` — Manufacturing surface edge continuity and lighting-normalized (`cv2.equalizeHist`) reference comparison.
- **8 Whitelisted OpenCV 5 Active-Perception Tools (Exposed via `/mcp/tools`):**
  - `inpaint_specular_glare` (`cv2.inpaint` Telea + dynamic range contrast recovery)
  - `rectify_perspective_homography` (`cv2.getPerspectiveTransform` + `cv2.warpPerspective`)
  - `analyze_vertical_stratification` (3-stratum supernatant vs. settled bottom sediment analysis)
  - `skeletonize_crack_metrology` (homomorphic Gaussian shadow removal + `cv2.distanceTransform` width in mm)
  - `track_across_frames` (multi-lighting ambient → backlight fusion + `cv2.phaseCorrelate` sub-pixel shift)
  - `reinspect_roi` (2x `cv2.INTER_CUBIC` super-sampling)
  - `measure_edge_continuity` (high-sensitivity Canny 30/100 re-evaluation)
  - `compare_to_reference` (histogram-equalized reference check)
- **Reproducible Synthetic Benchmark:**
  The 40 generated primary water fixtures reproduce A=55%, B=40%, B2=45%, C=100%. B2 does not currently match C's realized observation budget. On six generated crack fixtures, both the fixed two-pass baseline and adaptive policy reach 100%. These results do not establish physical measurement accuracy or an adaptive advantage on independent real samples.
- **Responsible-AI Safety Guards:**
  - Enforces **"Turbidity ≠ Potability"** across all UI screens and PDF exports: clear water can still contain invisible arsenic, fluoride, or nitrates.
  - Returns `NO_PATTERN_DETECTED` when no reference checkerboard is present on water uploads rather than guessing on invalid input.

## Quickstart (Local Development)

### 1. Backend (FastAPI + OpenCV 5 + MCP Server)

```bash
pip install -r requirements.txt
uvicorn services.inference.main:app --reload --port 8000
```

Verify endpoints:
- `GET http://localhost:8000/version` — OpenCV version, profiles, and 8 MCP tools
- `GET http://localhost:8000/mcp/tools` — Model Context Protocol tool schemas
- `GET http://localhost:8000/samples` — Built-in 6-scenario benchmark catalog

### 2. Frontend (Next.js 15 Interactive Workbench)

```bash
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:3000` to upload images, use live camera capture with pre-flight telemetry, or run any of the **6 built-in benchmark scenarios in 1 click**.

### 3. Run Tests & Evaluation Harness

```bash
# Backend regression tests; live Gemini requires separate configuration
python -m pytest services/inference/tests -v

# Synthetic generation overwrites data/self_captured; preserve genuine captures elsewhere.
python services/inference/scripts/generate_benchmark_dataset.py
python services/inference/scripts/calibrate_thresholds.py data/self_captured
python services/inference/scripts/run_experiments.py data/self_captured --profile water_turbidity_v1
python services/inference/scripts/run_experiments.py --profile structural_crack_metrology_v1
```

Frontend API regression checks and production build, from `apps/web`:

```bash
npm test
npm run build
```

Configure `INFERENCE_API_URL` on Vercel to use the real backend. Missing or failed inference returns an error; it never selects a canned verdict. Set `DEMO_MODE=golden` only for explicitly labeled fixture demonstrations. Result JSON, the result page and PDF report retain execution-source labels. Fonts are bundled locally.
