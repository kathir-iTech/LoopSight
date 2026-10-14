# LoopSight v2 — Experiment Results & Benchmark Artifacts

This directory stores the reproducible JSON outputs from `services/inference/scripts/run_experiments.py` and `services/inference/scripts/calibrate_thresholds.py` executed against the 40-sample multi-condition benchmark dataset in `data/self_captured/`.

## Latest Verified Results (`water_turbidity_v1`, N = 40)

- **Experiment A (Single-Pass Baseline):** `accuracy = 0.5500`, `trigger_rate = 0.0000`, `conditional_benefit = +0.0000`
- **Experiment B (Fixed 2x Upsample Repeat):** `accuracy = 0.4000`, `trigger_rate = 0.6000`, `conditional_benefit = -0.2500`
- **Experiment B2 (Matched Observation Budget Control):** `accuracy = 0.4500`, `trigger_rate = 0.4000`, `conditional_benefit = -0.1667`
- **Experiment C (LoopSight v2 Adaptive 8-Tool Active Perception):** `accuracy = 1.0000`, `trigger_rate = 0.6000`, `resolution_rate = 0.7500`, `false_trigger = 0.0000`, `conditional_benefit = +0.7500`

## Latest Verified Results (`structural_crack_metrology_v1`, N = 6)

- **Experiment A (Single-Pass Baseline):** `accuracy = 0.6667`, `conditional_benefit = +0.0000`
- **Experiment B2 (Matched Observation Budget Control):** `accuracy = 0.6667`, `conditional_benefit = +0.0000`
- **Experiment C (LoopSight v2 Adaptive Active Perception):** `accuracy = 1.0000`, `resolution_rate = 1.0000`, `conditional_benefit = +1.0000`
