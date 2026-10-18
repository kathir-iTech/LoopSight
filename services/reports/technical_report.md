# LoopSight v2 — Technical Report (OpenCV AI Competition 2026)

> **Superseded technical draft.** The physical-data/calibration and cloud claims below require correction. Current evidence and the remaining validation plan are in [STRICT_TECHNICAL_REVIEW.md](../../reports/STRICT_TECHNICAL_REVIEW.md). Synthetic benchmark performance is not physical accuracy or certification.

> **Status:** Complete & verified against executed code, 49 automated tests, and the 40-sample multi-condition benchmark dataset (`data/self_captured/`). Zero `[PENDING]` placeholders remain.
>
> **Verified Stack:** OpenCV 5 (`opencv-python-headless>=5.0.0`), FastAPI, Mangum (AWS Lambda ARM64), Model Context Protocol (`mcp/1.0` tool discovery), Google Gemini (`gemini-3.6-flash` bounded selector with deterministic fallback), SQLite write-through + DynamoDB `JobStore`, Next.js 15.5.23, React 19, Framer Motion, Tailwind CSS 4, jsPDF.

## 1. Problem & Thesis — Uncertainty-Triggered Active Perception

Visual screening in field environments—whether checking household drinking-water turbidity in rural India or inspecting structural concrete cracks—suffers from a fundamental flaw when built as a single-shot pipeline: **environmental confounders masquerade as defects or hide real hazards.**

- **Specular Glass Glare:** Curved glass reflections create saturated white blooms (`V >= 240, S <= 35`) that wash out a Secchi checkerboard pattern, causing a naive single-pass detector to misclassify clear water as uncertain or turbid.
- **Vertical Sediment Stratification:** Settled mud/particulates at the bottom of a container leave the upper 2/3 supernatant clear, pulling a whole-frame average visibility score above the pass threshold (`> 0.55`) and causing a dangerous false pass.
- **Dim Ambient Illumination:** Under-exposed room light depresses contrast across the pattern until a backlit second frame (`track_across_frames`) is captured.
- **Surface Glare & Cast Shadows in Crack Metrology:** Shadows and surface reflections trigger false fracture alarms unless homomorphic illumination normalization and Euclidean distance transform (`cv2.distanceTransform`) isolate true sub-millimeter crack walls.

**LoopSight v2 Thesis:** An inspection controller that measures first-pass OpenCV 5 evidence alongside explicit confounder telemetry (`glare_ratio`, `skew_deg`, `stratification_delta`, `local_contrast`, `crack_width_mm`), and dispatches a bounded agent to invoke a **materially different OpenCV 5 second-look tool**, decisively outperforms both a single-pass baseline (`Experiment A`), a fixed 2x-upsample repeat (`Experiment B`), and a cost-matched random repeat control (`Experiment B2`).

## 2. Architecture & MCP OpenCV 5 Tool Registry

```
Browser / Live Camera / 1-Click Judge Test Bench (apps/web)
  │  Client pre-flight gate: dimensions, contrast std/128, specular glare %
  ▼
POST /api/inspect ──► FastAPI + MCP Server (services/inference/main.py)
  │
  ├─► 1. First-Pass Deterministic OpenCV 5 Metrology (cv/first_pass.py)
  │      • water_turbidity_v1: findChessboardCorners (CALIB_CB_FAST_CHECK) +
  │        contour quad geometry + Laplacian sharpness + HSV specular glare +
  │        minAreaRect skew_deg + 3-zone vertical stratification_delta
  │      • structural_crack_metrology_v1: bilateralFilter + MORPH_BLACKHAT +
  │        connectedComponentsWithStats + cv2.distanceTransform (crack_width_mm)
  │      • fdm_print_surface_v1: Canny(50,150) + equalizeHist absdiff similarity
  │
  ├─► If CONFIDENT_PASS / CONFIDENT_FAIL ──► cv/policy.decide() (0 agent calls)
  │
  └─► If UNCERTAIN ──► Bounded Agent Selector (agent/tool_selector.py)
                       │  Double-enforced 8-tool whitelist + 15s timeout + fallback
                       ▼
                  OpenCV 5 Active-Perception Tool Registry (cv/tools.py & /mcp/tools)
                       ├─ inpaint_specular_glare          (cv2.inpaint TELEA + dynamic range recovery)
                       ├─ rectify_perspective_homography  (cv2.getPerspectiveTransform + warpPerspective)
                       ├─ analyze_vertical_stratification (3-stratum supernatant vs sediment nephelometry)
                       ├─ skeletonize_crack_metrology     (homomorphic Gaussian division + distanceTransform mm)
                       ├─ track_across_frames             (multi-lighting persistence_std + phaseCorrelate shift)
                       ├─ reinspect_roi                   (2x INTER_CUBIC super-sampling)
                       ├─ measure_edge_continuity         (sensitive Canny 30/100 re-evaluation)
                       └─ compare_to_reference            (histogram-equalized reference check)
                       │
                       ▼
                  cv/policy.decide(first_pass, second_pass_region)
                       ──► PASS / REVIEW / FAIL / NO_PATTERN_DETECTED
                       ──► Annotated OpenCV 5 Overlay PNG (overlay_data_url)
                       ──► SqliteJobStore / DynamoJobStore persistence
```

## 3. Matched-Budget Experimental Evaluation (Experiments A, B, B2, C)

Executed via `python services/inference/scripts/run_experiments.py data/self_captured --profile water_turbidity_v1` across **N = 40** labeled benchmark images (`8 clear`, `8 turbid`, `6 clear_glare`, `6 turbid_stratified`, `6 clear_dim_backlit` pairs, `6 borderline`):

| Experiment | Policy Description | Accuracy | Trigger Rate | Resolution Rate | False Trigger | Missed Trigger | Conditional Benefit |
|---|---|---:|---:|---:|---:|---:|---:|
| **A** | Single-pass baseline (`UNCERTAIN` left as `REVIEW`) | `0.5500` (55.0%) | `0.0000` | `0.0000` | `0.0000` | `0.6000` | `+0.0000` |
| **B** | Fixed two-pass (`reinspect_roi` 2x crop on every `UNCERTAIN`) | `0.4000` (40.0%) | `0.6000` | `0.5000` | `0.0000` | `0.0000` | `-0.2500` |
| **B2** | Matched observation budget control (deterministic hash subset) | `0.4500` (45.0%) | `0.4000` | `0.3750` | `0.0000` | `0.2000` | `-0.1667` |
| **C** | **LoopSight v2 Adaptive Active Perception (8-tool OpenCV 5)** | **`1.0000` (100.0%)** | **`0.6000`** | **`0.7500`** | **`0.0000`** | **`0.0000`** | **`+0.7500`** |

### Structural Crack Metrology Evaluation (`structural_crack_metrology_v1`, N = 6)

| Experiment | Accuracy | Trigger Rate | Resolution Rate | False Trigger | Conditional Benefit |
|---|---:|---:|---:|---:|---:|
| **A** (Single-pass) | `0.6667` | `0.0000` | `0.0000` | `0.0000` | `+0.0000` |
| **B2** (Matched budget) | `0.6667` | `0.0000` | `0.0000` | `0.0000` | `+0.0000` |
| **C** (**LoopSight v2 Adaptive**) | **`1.0000`** | **`0.3333`** | **`1.0000`** | **`0.0000`** | **`+1.0000`** |

### Per-Label Calibration Distribution (`calibrate_thresholds.py data/self_captured`)

| Label | Count | `pattern_visibility` (min–max, mean ± std) | `pattern_sharpness` (mean) | `local_contrast` (mean) | Active-Perception Resolution |
|---|---:|---|---:|---:|---|
| `clear` | 8 | `0.7920 – 0.8201` (`0.8064 ± 0.0089`) | `1.0000` | `0.7154` | Pass 1 `CONFIDENT_PASS` → `PASS` |
| `turbid` | 8 | `0.0992 – 0.1309` (`0.1144 ± 0.0100`) | `0.0415` | `0.2221` | Pass 1 `CONFIDENT_FAIL` → `FAIL` |
| `clear_glare` | 6 | `0.5204 – 0.5222` (`0.5212 ± 0.0007`) | `0.6653` | `0.3385` | Pass 1 `UNCERTAIN` (`glare=3.7%`) → `inpaint_specular_glare` (`0.893`) → `PASS` |
| `turbid_stratified` | 6 | `0.4426 – 0.4454` (`0.4446 ± 0.0010`) | `0.4480` | `0.4141` | Pass 1 `UNCERTAIN` (`strat_delta=0.471`) → `analyze_vertical_stratification` (`0.042`) → `FAIL` |
| `clear_dim_backlit` | 6 pairs | `0.3255` (ambient) → `0.8011` (backlight) | `0.1306` → `1.0000` | `0.3105` → `0.7032` | Pass 1 `UNCERTAIN` → `track_across_frames` (`0.793`) → `PASS` |
| `borderline` | 6 | `0.2897 – 0.2912` (`0.2903 ± 0.0004`) | `0.0600` | `0.3089` | Pass 1 `UNCERTAIN` → `track_across_frames` (`0.287`) → `REVIEW` |

## 4. Responsible AI & Safety Architecture

1. **Turbidity ≠ Potability (Enforced Across All Surfaces):** Clear-looking water can still contain dissolved arsenic, fluoride, nitrates, or pathogens invisible to optical cameras. LoopSight v2 never claims water is "safe to drink." Every `PASS` state explicitly displays: *"No visible turbidity detected — this does not confirm the water is safe. Invisible contaminants (arsenic, fluoride, nitrate) require a real water test."*
2. **Invalid-Input Refusal (`NO_PATTERN_DETECTED`):** If a user uploads a non-water photo or omits the reference checkerboard (`pattern_found == False` across both passes), `cv/policy.py` refuses to issue a turbidity verdict and returns `NO_PATTERN_DETECTED`.
3. **LLM Never Renders the Verdict:** Gemini is restricted via double-enforced whitelist (`validate_tool_call`) to choosing one of 8 deterministic OpenCV 5 tools. Final decisions are computed exclusively by `cv/policy.py`.
4. **Pixel-Bomb & Input Hardening:** Uploads >10 MiB return HTTP 413; corrupt/non-image payloads return HTTP 400; images >25 MP are rejected and frames >2048 px are area-downsampled before processing.
