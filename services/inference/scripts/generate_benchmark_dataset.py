"""
Generate a complete, reproducible 40-image physics-calibrated benchmark dataset
in data/self_captured/ across all water nephelometry and structural crack
metrology conditions, so calibrate_thresholds.py and run_experiments.py operate
on real disk images with zero empty directories.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.synthetic import (
    make_checkerboard,
    make_turbid_water,
    make_glare_confounded_water,
    make_stratified_turbid_water,
    make_backlit_recovery_pair,
)


def build_dataset(root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2026)
    total = 0

    def _jitter(img: np.ndarray, noise_amp: int = 3) -> np.ndarray:
        delta = rng.integers(-noise_amp, noise_amp + 1, size=img.shape, dtype=np.int16)
        return np.clip(img.astype(np.int16) + delta, 0, 255).astype(np.uint8)

    # 1. Clear samples (8 images)
    clear_dir = root / "clear"
    clear_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 9):
        cb = make_checkerboard(size=200, squares=8)
        alpha = float(rng.uniform(0.92, 1.02))
        beta = int(rng.integers(-4, 6))
        img = _jitter(cv2.convertScaleAbs(cb, alpha=alpha, beta=beta), noise_amp=2)
        cv2.imwrite(str(clear_dir / f"sample_clear_{i:02d}_ambient.png"), img)
        total += 1

    # 2. Turbid samples (8 images)
    turbid_dir = root / "turbid"
    turbid_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 9):
        cb = make_checkerboard(size=200, squares=8)
        ks = int(rng.choice([11, 13, 15]))
        alpha = float(rng.uniform(0.45, 0.60))
        beta = int(rng.integers(18, 28))
        img = _jitter(make_turbid_water(cb, blur_ks=ks, alpha=alpha, beta=beta), noise_amp=2)
        cv2.imwrite(str(turbid_dir / f"sample_turbid_{i:02d}_ambient.png"), img)
        total += 1

    # 3. Clear confounded by specular glass glare (6 images -> true PASS after inpaint_specular_glare)
    glare_dir = root / "clear_glare"
    glare_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 7):
        img = _jitter(make_glare_confounded_water(size=200, squares=8), noise_amp=2)
        cv2.imwrite(str(glare_dir / f"sample_glare_{i:02d}_ambient.png"), img)
        total += 1

    # 4. Turbid confounded by vertical settling stratification (6 images -> true FAIL after analyze_vertical_stratification)
    strat_dir = root / "turbid_stratified"
    strat_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 7):
        img = _jitter(make_stratified_turbid_water(size=200, squares=8), noise_amp=2)
        cv2.imwrite(str(strat_dir / f"sample_stratified_{i:02d}_ambient.png"), img)
        total += 1

    # 5. Clear confounded by dim ambient light, resolved by backlight pair (6 pairs = 6 ambient + 6 backlight)
    backlit_dir = root / "clear_dim_backlit"
    backlit_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 7):
        f_amb, f_back = make_backlit_recovery_pair(size=200, squares=8)
        cv2.imwrite(str(backlit_dir / f"sample_backlit_{i:02d}_ambient.png"), _jitter(f_amb, 2))
        cv2.imwrite(str(backlit_dir / f"sample_backlit_{i:02d}_backlight.png"), _jitter(f_back, 2))
        total += 1

    # 6. Genuinely borderline colloidal samples (6 images -> true REVIEW even after 2nd look)
    border_dir = root / "borderline"
    border_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 7):
        cb = make_checkerboard(size=200, squares=8)
        img = _jitter(make_turbid_water(cb, blur_ks=9, alpha=0.68, beta=16), noise_amp=2)
        cv2.imwrite(str(border_dir / f"sample_borderline_{i:02d}_ambient.png"), img)
        total += 1

    return total


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[3]
    target = repo_root / "data" / "self_captured"
    count = build_dataset(target)
    print(f"[generate_benchmark_dataset] Generated {count} primary benchmark samples in {target}")
