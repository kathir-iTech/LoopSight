"""
LoopSight — threshold calibration tool.

Takes a folder path via CLI arg, expects subfolders named after labels
(clean/, layer_shift/, stringing/, warping/, under_extrusion/, blob/,
elephants_foot/) each containing images.

For every image, runs measure_region() over the full frame, collects
edge_continuity / reference_similarity / layer_alignment_deviation per label.

Prints a table: per label, min/max/mean/std for each metric.

Suggests concrete threshold values for InspectionProfile(...) based on where
clean vs defect distributions actually separate — not a guess, the real gap
between measured distributions.

Usage:
    python scripts/calibrate_thresholds.py /path/to/dataset
    python scripts/calibrate_thresholds.py /path/to/dataset --reference /path/to/clean_ref.jpg
    python -m scripts.calibrate_thresholds /path/to/dataset

The same module is importable for tests:
    from scripts.calibrate_thresholds import calibrate, suggest_thresholds

When real photos land in data/self_captured/, this becomes:
    python services/inference/scripts/calibrate_thresholds.py data/self_captured
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional

import cv2
import numpy as np

# Ensure local imports work when run as `python scripts/calibrate_thresholds.py`
# or `python -m scripts.calibrate_thresholds` or via pytest.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv.first_pass import measure_region  # type: ignore

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# Expected label names per spec, but any subfolder is accepted.
EXPECTED_LABELS = ["clean", "layer_shift", "stringing", "warping", "under_extrusion", "blob", "elephants_foot"]


@dataclass
class MetricStats:
    min: float
    max: float
    mean: float
    std: float
    count: int


def _stats(values: List[float]) -> MetricStats:
    if not values:
        return MetricStats(min=0.0, max=0.0, mean=0.0, std=0.0, count=0)
    arr = np.array(values, dtype=float)
    return MetricStats(
        min=float(np.min(arr)),
        max=float(np.max(arr)),
        mean=float(np.mean(arr)),
        std=float(np.std(arr)),
        count=len(values),
    )


def _load_image(path: Path) -> Optional[np.ndarray]:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        print(f"[warn] could not decode image: {path}", file=sys.stderr)
    return img


def _get_reference_for_frame(ref_img: Optional[np.ndarray], frame: np.ndarray) -> Optional[np.ndarray]:
    if ref_img is None:
        return None
    if ref_img.shape == frame.shape:
        return ref_img
    # Resize reference to match frame dimensions so histogram-normalized
    # comparison is meaningful. Without this, measure_region would return
    # 0.0 for shape mismatch, which is useful as a runtime signal but not
    # as a calibration statistic. For calibration we want the *content*
    # distance, not the size mismatch.
    h, w = frame.shape[:2]
    try:
        resized = cv2.resize(ref_img, (w, h), interpolation=cv2.INTER_LINEAR)
        return resized
    except Exception:
        return None


def calibrate(dataset_root: Path, reference_path: Optional[Path] = None) -> Dict[str, Dict[str, List[float]]]:
    """
    Walk dataset_root, expecting subfolders per label each containing images.
    Returns: {label: {"edge_continuity": [...], "reference_similarity": [...],
                      "layer_alignment_deviation": [...], "local_contrast": [...]} }
    """
    dataset_root = Path(dataset_root)
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"dataset root not found or not a directory: {dataset_root}")

    # Resolve reference image: explicit --reference path wins, otherwise first
    # image in clean/ if it exists.
    ref_img: Optional[np.ndarray] = None
    ref_source: Optional[str] = None
    if reference_path is not None:
        ref_img = _load_image(Path(reference_path))
        ref_source = str(reference_path)
        if ref_img is None:
            raise ValueError(f"could not load reference image: {reference_path}")
    else:
        clean_dir = dataset_root / "clean"
        if clean_dir.is_dir():
            for ext in SUPPORTED_EXTS:
                # prefer first image found sorted
                candidates = sorted(clean_dir.glob(f"*{ext}")) + sorted(clean_dir.glob(f"*{ext.upper()}"))
                if candidates:
                    ref_img = _load_image(candidates[0])
                    if ref_img is not None:
                        ref_source = str(candidates[0])
                        break
                # also check case-insensitive via rglob
            if ref_img is None:
                # fallback: any file in clean/
                for p in sorted(clean_dir.iterdir()):
                    if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                        ref_img = _load_image(p)
                        if ref_img is not None:
                            ref_source = str(p)
                            break
    if ref_source:
        print(f"[info] reference image for similarity: {ref_source}")
    else:
        print("[info] no reference image found (no clean/ exemplar, no --reference) — reference_similarity will be 1.0 for all images (less informative).")

    raw: Dict[str, Dict[str, List[float]]] = {}

    # Discover labels = immediate subdirectories that contain at least one image-like file
    subdirs = [p for p in dataset_root.iterdir() if p.is_dir()]
    if not subdirs:
        raise ValueError(f"no subfolders found in {dataset_root} — expected e.g. clean/, layer_shift/, ...")

    for label_dir in sorted(subdirs):
        label = label_dir.name
        metrics = {"edge_continuity": [], "reference_similarity": [], "layer_alignment_deviation": [], "local_contrast": []}
        # Collect image paths
        image_paths: List[Path] = []
        for ext in SUPPORTED_EXTS:
            image_paths.extend(label_dir.glob(f"*{ext}"))
            image_paths.extend(label_dir.glob(f"*{ext.upper()}"))
        # Also handle files with mixed case and ensure dedup
        image_paths = sorted(set(image_paths))
        # Fallback: iterate all files and filter by suffix lower
        if not image_paths:
            for p in label_dir.iterdir():
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                    image_paths.append(p)
            image_paths = sorted(set(image_paths))

        if not image_paths:
            print(f"[warn] no images found in {label_dir} — skipping label '{label}'")
            continue

        for img_path in image_paths:
            frame = _load_image(img_path)
            if frame is None:
                continue
            h, w = frame.shape[:2]
            if h == 0 or w == 0:
                print(f"[warn] empty image {img_path} — skipping")
                continue
            roi = (0, 0, w, h)
            ref_for_this = _get_reference_for_frame(ref_img, frame)
            # If this image IS the reference source itself, ref_for_this == frame
            # That yields similarity 1.0 which is correct for clean self-comparison.
            region = measure_region(frame, ref_for_this, roi)
            metrics["edge_continuity"].append(float(region.edge_continuity))
            metrics["reference_similarity"].append(float(region.reference_similarity))
            metrics["layer_alignment_deviation"].append(float(region.layer_alignment_deviation))
            metrics["local_contrast"].append(float(region.local_contrast))

        if any(metrics[k] for k in metrics):
            raw[label] = metrics
            print(f"[info] label '{label}': {len(metrics['edge_continuity'])} images measured")

    if not raw:
        raise ValueError(f"no images successfully measured under {dataset_root}")

    return raw


def compute_table(raw: Dict[str, Dict[str, List[float]]]) -> Dict[str, Dict[str, MetricStats]]:
    """Convert raw lists to per-label, per-metric stats."""
    table: Dict[str, Dict[str, MetricStats]] = {}
    for label, metrics in raw.items():
        table[label] = {}
        for metric, values in metrics.items():
            table[label][metric] = _stats(values)
    return table


def suggest_thresholds(raw: Dict[str, Dict[str, List[float]]]) -> Dict[str, float]:
    """
    Suggest concrete InspectionProfile thresholds based on where clean vs.
    defect distributions separate.

    Logic:
    - clean = raw["clean"] if present; defects = aggregate of all other labels.
      If no clean label, fall back to using global percentiles (not ideal, but
      never crashes — prints a warning and uses overall distribution).
    - For edge_continuity (defect = low, clean = high):
        If defect_max < clean_min (separable): gap = clean_min - defect_max
          confident_fail = defect_max + gap*0.3 (just above worst defect)
          confident_pass = clean_min - gap*0.3 (just below best clean)
        Else overlapping: fail = percentile(defect, 75) clipped, pass = percentile(clean, 25)
        Ensure fail < pass, with fallback to means if needed.
    - For reference_similarity_floor (clean high, defect lower):
        If defect_max < clean_min: floor = (defect_max + clean_min)/2
        Else floor = (defect_mean + clean_mean)/2
    - For contrast_min_for_confidence (low contrast = ambiguous):
        Use contrast distribution. If clean vs low/aggregate separable, put
        threshold in the gap. Otherwise use a fraction of clean min.
    Returns dict with keys: edge_continuity_confident_fail,
                            edge_continuity_confident_pass,
                            contrast_min_for_confidence,
                            reference_similarity_floor
    """
    has_clean = "clean" in raw and any(raw["clean"].values())
    # Aggregate defects
    defect_edge: List[float] = []
    defect_ref: List[float] = []
    defect_contrast: List[float] = []
    for label, metrics in raw.items():
        if label == "clean":
            continue
        defect_edge.extend(metrics.get("edge_continuity", []))
        defect_ref.extend(metrics.get("reference_similarity", []))
        defect_contrast.extend(metrics.get("local_contrast", []))

    clean_edge = raw.get("clean", {}).get("edge_continuity", []) if has_clean else []
    clean_ref = raw.get("clean", {}).get("reference_similarity", []) if has_clean else []
    clean_contrast = raw.get("clean", {}).get("local_contrast", []) if has_clean else []

    suggestions: Dict[str, float] = {}

    # --- edge_continuity ---
    if has_clean and defect_edge and clean_edge:
        d_min, d_max = float(np.min(defect_edge)), float(np.max(defect_edge))
        c_min, c_max = float(np.min(clean_edge)), float(np.max(clean_edge))
        d_mean, c_mean = float(np.mean(defect_edge)), float(np.mean(clean_edge))
        if d_max < c_min:
            gap = c_min - d_max
            fail = d_max + gap * 0.3
            pas = c_min - gap * 0.3
            # Clamp to valid [0,1] and ensure ordering
            fail = max(0.0, min(1.0, fail))
            pas = max(0.0, min(1.0, pas))
            if fail >= pas:
                # fallback to means midpoint
                mid = (d_mean + c_mean) / 2.0
                fail = max(0.0, min(mid - 0.02, 1.0))
                pas = max(0.0, min(mid + 0.02, 1.0))
        else:
            # Overlapping distributions — use percentiles for robustness
            # Guard against tiny samples where percentile == same
            try:
                d_p75 = float(np.percentile(defect_edge, 75))
                c_p25 = float(np.percentile(clean_edge, 25))
            except Exception:
                d_p75 = d_mean
                c_p25 = c_mean
            if d_p75 < c_p25:
                fail = d_p75
                pas = c_p25
            else:
                mid = (d_mean + c_mean) / 2.0
                fail = max(0.0, mid - 0.02)
                pas = min(1.0, mid + 0.02)
            # If still overlapping inversion, force midpoint widening
            if fail >= pas:
                fail = max(0.0, min(d_mean + float(np.std(defect_edge)) * 0.5, 1.0))
                pas = max(fail + 0.02, min(c_mean - float(np.std(clean_edge)) * 0.5, 1.0))
                if fail >= pas:
                    fail, pas = 0.35, 0.85  # ultimate fallback to profile defaults
        suggestions["edge_continuity_confident_fail"] = round(float(fail), 4)
        suggestions["edge_continuity_confident_pass"] = round(float(pas), 4)
    else:
        # No clean/defect split — use global percentiles as a weak guess
        all_edge = defect_edge + clean_edge
        if all_edge:
            lo = float(np.percentile(all_edge, 25))
            hi = float(np.percentile(all_edge, 75))
            if lo >= hi:
                lo, hi = 0.01, 0.05
            suggestions["edge_continuity_confident_fail"] = round(lo, 4)
            suggestions["edge_continuity_confident_pass"] = round(hi, 4)
        else:
            suggestions["edge_continuity_confident_fail"] = 0.35
            suggestions["edge_continuity_confident_pass"] = 0.85

    # --- reference_similarity_floor ---
    if has_clean and defect_ref and clean_ref:
        d_max = float(np.max(defect_ref))
        c_min = float(np.min(clean_ref))
        d_mean = float(np.mean(defect_ref))
        c_mean = float(np.mean(clean_ref))
        if d_max < c_min:
            floor = (d_max + c_min) / 2.0
        else:
            # overlapping — use means midpoint, but bias toward clean side
            floor = (d_mean + c_mean) / 2.0
            # If reference was missing (all 1.0), this collapses to 1.0 — fallback
            if floor >= 0.999:
                # All similarities are 1.0 because no reference was used — fall back to default
                floor = 0.55
        suggestions["reference_similarity_floor"] = round(float(max(0.0, min(1.0, floor))), 4)
    else:
        all_ref = defect_ref + clean_ref
        if all_ref and not (len(all_ref) > 0 and all(v == 1.0 for v in all_ref)):
            # If all 1.0, no signal
            floor = float(np.percentile(all_ref, 50)) - 0.05
            suggestions["reference_similarity_floor"] = round(float(max(0.0, min(1.0, floor))), 4)
        else:
            suggestions["reference_similarity_floor"] = 0.55

    # --- contrast_min_for_confidence ---
    if has_clean and defect_contrast and clean_contrast:
        d_max = float(np.max(defect_contrast))
        c_min = float(np.min(clean_contrast))
        d_mean = float(np.mean(defect_contrast))
        c_mean = float(np.mean(clean_contrast))
        # Low contrast is ambiguous, so threshold should be in the gap between
        # the most low-contrast defect and the least low-contrast clean.
        # For synthetic, defects have lower contrast than clean, but not as low as true uniform frames.
        # If separable, put in gap; else use a fraction of clean.
        # Also consider if there is a "low" or ambiguous label that is genuinely low.
        # Look for any label with very low contrast (<0.05) to inform threshold
        all_labels_contrast_min = min((float(np.min(v)) for v in [clean_contrast] + [defect_contrast] if v), default=0.0)
        # Check per-label minima to detect a genuinely low-contrast group
        per_label_mins = {}
        for label, metrics in raw.items():
            vals = metrics.get("local_contrast", [])
            if vals:
                per_label_mins[label] = float(np.min(vals))
        # If there is a label with contrast <0.05 and another >0.15, threshold is gap between them
        low_group_max = max((v for k, v in per_label_mins.items() if v < 0.08), default=None)  # type: ignore
        high_group_min = min((v for k, v in per_label_mins.items() if v > 0.15), default=None)  # type: ignore
        if low_group_max is not None and high_group_min is not None and low_group_max < high_group_min:
            thr = (low_group_max + high_group_min) / 2.0
        elif d_max < c_min:
            thr = (d_max + c_min) / 2.0
        else:
            # overlapping — threshold just below clean distribution
            thr = c_min * 0.8 if c_min > 0 else 0.1
            # Ensure not too high
            thr = max(0.02, min(thr, c_mean * 0.7 if c_mean else 0.4))
        suggestions["contrast_min_for_confidence"] = round(float(max(0.0, min(1.0, thr))), 4)
    else:
        all_contrast = defect_contrast + clean_contrast
        if all_contrast:
            c_min = float(np.min(all_contrast))
            thr = c_min * 0.8 if c_min > 0 else 0.05
            suggestions["contrast_min_for_confidence"] = round(float(max(0.01, min(1.0, thr))), 4)
        else:
            suggestions["contrast_min_for_confidence"] = 0.40

    return suggestions


def print_report(raw: Dict[str, Dict[str, List[float]]], table: Dict[str, Dict[str, MetricStats]], suggestions: Dict[str, float]):
    # Header
    print("\n" + "=" * 88)
    print("LoopSight calibration report")
    print("=" * 88)
    print(f"Labels found: {sorted(raw.keys())}")
    total_images = sum(len(v["edge_continuity"]) for v in raw.values())
    print(f"Total images measured: {total_images}")
    print("-" * 88)

    # Table per label
    metrics_order = ["edge_continuity", "reference_similarity", "layer_alignment_deviation", "local_contrast"]
    # Print column header
    header = f"{'label':<18} {'metric':<28} {'count':>5} {'min':>9} {'max':>9} {'mean':>9} {'std':>9}"
    print(header)
    print("-" * 88)
    for label in sorted(raw.keys()):
        for metric in metrics_order:
            st = table[label].get(metric)
            if st is None or st.count == 0:
                continue
            print(f"{label:<18} {metric:<28} {st.count:>5} {st.min:>9.4f} {st.max:>9.4f} {st.mean:>9.4f} {st.std:>9.4f}")
        print("-" * 88)

    # Suggestions
    print("\nSuggested InspectionProfile thresholds (data-driven, not guesses):")
    print("  These are the gaps where clean vs defect distributions separate.")
    print("  Copy into cv/first_pass.py PROFILES or pass as a new profile.")
    print("-" * 88)
    for k in ["edge_continuity_confident_fail", "edge_continuity_confident_pass", "contrast_min_for_confidence", "reference_similarity_floor"]:
        v = suggestions.get(k)
        if v is not None:
            print(f"  {k:<35} = {v}")

    print("\nPython snippet for PROFILES:")
    print("  PROFILES[\"calibrated_v1\"] = InspectionProfile(")
    for k in ["edge_continuity_confident_fail", "edge_continuity_confident_pass", "contrast_min_for_confidence", "reference_similarity_floor"]:
        v = suggestions.get(k)
        print(f"      {k}={v},")
    print("      name=\"calibrated_v1\",")
    print("  )")

    # Interpretation helper
    print("\nInterpretation:")
    has_clean = "clean" in raw
    if has_clean:
        print("  - edge_continuity: FAIL threshold just above worst defect, PASS just below best clean.")
        print("    If a new image scores <= fail -> confident FAIL, >= pass -> confident PASS, else UNCERTAIN (triggers agent).")
        print("  - reference_similarity_floor: below this -> low similarity triggers UNCERTAIN to re-check reference.")
        print("  - contrast_min_for_confidence: below this -> low-contrast UNCERTAIN (cannot trust edge).")
        # Warn if overlap
        clean_edge_vals = raw["clean"]["edge_continuity"]
        defect_edge_vals = []
        for lbl, m in raw.items():
            if lbl != "clean":
                defect_edge_vals.extend(m["edge_continuity"])
        if clean_edge_vals and defect_edge_vals:
            if max(defect_edge_vals) >= min(clean_edge_vals):
                print("  [WARN] edge_continuity distributions OVERLAP - clean and defect ranges intermix.")
                print("         Suggested thresholds are a midpoint compromise; collect more images or check lighting.")
            else:
                print(f"  [OK] edge_continuity distributions are SEPARABLE (gap {min(clean_edge_vals)-max(defect_edge_vals):.4f}).")
    else:
        print("  [WARN] No 'clean' label found - suggestions use global percentiles, weaker than clean-vs-defect gap method.")
        print("         Add a clean/ folder with known-good images for a proper calibration.")

    print("=" * 88 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="LoopSight threshold calibration: measure synthetic or real images per label and suggest InspectionProfile thresholds.",
        epilog="Example: python scripts/calibrate_thresholds.py data/self_captured\n         python scripts/calibrate_thresholds.py /tmp/synthetic_test --reference clean/reference.jpg",
    )
    parser.add_argument("dataset", type=str, help="path to folder containing subfolders per label (clean/, layer_shift/, ...)")
    parser.add_argument("--reference", type=str, default=None, help="optional explicit reference image for similarity (default: first image in clean/)")
    parser.add_argument("--json", type=str, default=None, help="optional path to write raw measurements as JSON")
    args = parser.parse_args()

    dataset_root = Path(args.dataset)
    reference_path = Path(args.reference) if args.reference else None

    try:
        raw = calibrate(dataset_root, reference_path)
    except Exception as e:
        print(f"[error] calibration failed: {e}", file=sys.stderr)
        sys.exit(1)

    table = compute_table(raw)
    suggestions = suggest_thresholds(raw)
    print_report(raw, table, suggestions)

    if args.json:
        import json as _json
        # Serialize raw lists and suggestions
        out = {
            "dataset": str(dataset_root),
            "reference": str(reference_path) if reference_path else None,
            "raw_counts": {lbl: {k: len(v) for k, v in metrics.items()} for lbl, metrics in raw.items()},
            "table": {
                lbl: {metric: {"min": st.min, "max": st.max, "mean": st.mean, "std": st.std, "count": st.count}
                      for metric, st in metrics.items()}
                for lbl, metrics in table.items()
            },
            "suggestions": suggestions,
        }
        # Also include sample values for debugging
        out["sample_values"] = {lbl: {k: v[:5] for k, v in metrics.items()} for lbl, metrics in raw.items()}
        with open(args.json, "w") as f:
            _json.dump(out, f, indent=2)
        print(f"[info] wrote JSON report to {args.json}")


if __name__ == "__main__":
    main()
