# LoopSight — Capture Sheet (10–15 borderline pairs)

**Goal:** 10–15 samples where *you* hesitate. Two lightings each. This settles `conditional_benefit`.

| ID | Hesitation — why unsure (one line) | Self-guess BEFORE app | A: ambient ✓ | B: backlight/flash ✓ | App UNCERTAIN? | App vis. | Match? | Notes |
|---|---|---|---|---|---|---|---|---|
| 01 |  |  | ☐ | ☐ |  |  |  |  |
| 02 |  |  | ☐ | ☐ |  |  |  |  |
| 03 |  |  | ☐ | ☐ |  |  |  |  |
| 04 |  |  | ☐ | ☐ |  |  |  |  |
| 05 |  |  | ☐ | ☐ |  |  |  |  |
| 06 |  |  | ☐ | ☐ |  |  |  |  |
| 07 |  |  | ☐ | ☐ |  |  |  |  |
| 08 |  |  | ☐ | ☐ |  |  |  |  |
| 09 |  |  | ☐ | ☐ |  |  |  |  |
| 10 |  |  | ☐ | ☐ |  |  |  |  |
| 11 |  |  | ☐ | ☐ |  |  |  |  |
| 12 |  |  | ☐ | ☐ |  |  |  |  |
| 13 |  |  | ☐ | ☐ |  |  |  |  |
| 14 |  |  | ☐ | ☐ |  |  |  |  |
| 15 |  |  | ☐ | ☐ |  |  |  |  |

**After shooting:**
```bash
python services/inference/scripts/calibrate_thresholds.py data/self_captured
python services/inference/scripts/run_experiments.py data/self_captured --profile water_turbidity_v1
```
Read `conditional_benefit` on *real* borderline. >0 = second look helped; ~0/negative = honest negative result (also defensible).
