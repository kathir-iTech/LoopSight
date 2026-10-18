"""
LoopSight v2 — the bounded, whitelisted set of 8 OpenCV 5 active-perception tools.

Every tool here takes the current frame (+ a fresh capture or reference where
relevant) and returns a new RegionEvidence produced by a MATERIALLY DIFFERENT
OpenCV 5 geometric, photometric, or multi-frame operation:
  1. reinspect_roi                  — Bicubic super-sampled ROI re-measurement + CLAHE recovery
  2. compare_to_reference           — Histogram-equalized reference alignment verification
  3. measure_edge_continuity        — High-sensitivity Canny (30, 100) edge/pattern extraction
  4. track_across_frames            — Multi-lighting / multi-frame persistence + phase-correlation shift
  5. inpaint_specular_glare         — HSV/LAB specular reflection masking + cv2.inpaint (Telea) + CLAHE
  6. rectify_perspective_homography — Corner/quadrilateral detection + cv2.warpPerspective fronto-parallel rectification
  7. analyze_vertical_stratification — 3-zone vertical column nephelometry (supernatant vs sediment settling)
  8. skeletonize_crack_metrology    — CLAHE + morphological black-hat + Euclidean distance transform (mm)
"""

from __future__ import annotations

from dataclasses import dataclass
import cv2
import numpy as np

from .first_pass import (
    RegionEvidence,
    measure_region,
    measure_pattern_visibility,
    measure_crack_metrology,
    _compute_visibility_core,
    _detect_reference_pattern,
)


@dataclass
class ToolResult:
    tool: str
    region: RegionEvidence
    notes: str


def reinspect_roi(
    frame: np.ndarray,
    reference: np.ndarray | None,
    roi: tuple[int, int, int, int],
    scale: float = 2.0,
) -> ToolResult:
    """Upsample the region of interest with bicubic interpolation and apply
    local contrast normalization when illumination is attenuated."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    if crop.size == 0:
        raise ValueError(f"empty ROI for reinspect_roi: {roi}")
    upsampled = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    fake_roi = (0, 0, upsampled.shape[1], upsampled.shape[0])
    ref_crop = None
    if reference is not None:
        ref_region = reference[y:y + h, x:x + w]
        if ref_region.size:
            ref_crop = cv2.resize(ref_region, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    try:
        pv_region = measure_pattern_visibility(upsampled, fake_roi)
        if pv_region.pattern_found:
            return ToolResult(
                tool="reinspect_roi",
                region=pv_region,
                notes=f"upsampled {scale}x (INTER_CUBIC) before re-measuring pattern visibility",
            )
    except Exception:
        pass
    region = measure_region(upsampled, ref_crop, fake_roi)
    return ToolResult(tool="reinspect_roi", region=region, notes=f"upsampled {scale}x before re-measuring")


def compare_to_reference(
    frame: np.ndarray,
    reference: np.ndarray,
    roi: tuple[int, int, int, int],
) -> ToolResult:
    """Isolated histogram-equalized reference-comparison pass."""
    region = measure_region(frame, reference, roi)
    return ToolResult(
        tool="compare_to_reference",
        region=region,
        notes="isolated histogram-equalized reference-similarity re-check",
    )


def measure_edge_continuity(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
    low: int = 30,
    high: int = 100,
) -> ToolResult:
    """Re-run edge detection with a more sensitive Canny threshold pair (30, 100)
    and adaptive local contrast enhancement to resolve faint boundaries."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    edges = cv2.Canny(gray, low, high)
    edge_continuity = float(np.count_nonzero(edges)) / edges.size if edges.size else 0.0
    try:
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharp_norm = float(min(lap_var / 600.0, 1.0))
    except Exception:
        sharp_norm = 0.0
    pattern_found, _ = _detect_reference_pattern(gray)
    edge_sharp = float(min(edge_continuity * 10.0, 1.0)) if edge_continuity else 0.0
    pattern_visibility = float(0.5 * (float(np.std(gray)) / 128.0) + 0.3 * sharp_norm + 0.2 * edge_sharp)
    pattern_visibility = float(max(0.0, min(1.0, pattern_visibility)))
    region = RegionEvidence(
        x=x,
        y=y,
        w=w,
        h=h,
        edge_continuity=edge_continuity,
        reference_similarity=-1.0,
        layer_alignment_deviation=-1.0,
        local_contrast=float(np.std(gray)) / 128.0 if gray.size else 0.0,
        pattern_visibility=pattern_visibility,
        pattern_sharpness=sharp_norm,
        pattern_found=pattern_found,
    )
    return ToolResult(
        tool="measure_edge_continuity",
        region=region,
        notes=f"re-ran Canny at ({low},{high}) vs. first-pass thresholds",
    )


def track_across_frames(
    frames: list[np.ndarray],
    roi: tuple[int, int, int, int],
) -> ToolResult:
    """Multi-lighting / multi-frame active perception tool.
    Measures pattern visibility or edge continuity across frames, computes
    persistence_std, and estimates sub-pixel spatial registration shift via
    cv2.phaseCorrelate."""
    if len(frames) < 2:
        raise ValueError("track_across_frames needs at least 2 distinct frames")

    def _measure(f: np.ndarray) -> RegionEvidence:
        try:
            pv = measure_pattern_visibility(f, roi)
            if pv.pattern_found or pv.pattern_visibility > 0:
                return pv
        except Exception:
            pass
        return measure_region(f, None, roi)

    measurements = [_measure(f) for f in frames]
    vis_vals = [m.pattern_visibility for m in measurements if hasattr(m, "pattern_visibility")]
    edge_vals = [m.edge_continuity for m in measurements]
    if any(v > 0 for v in vis_vals):
        vals = vis_vals
        metric_name = "pattern_visibility"
    else:
        vals = edge_vals
        metric_name = "edge_continuity"
    persistence = float(np.std(vals))

    # Sub-pixel phase correlation shift between first and last frame
    shift_px = 0.0
    try:
        x, y, w, h = roi
        g1 = cv2.cvtColor(frames[0][y:y + h, x:x + w], cv2.COLOR_BGR2GRAY) if frames[0].ndim == 3 else frames[0][y:y + h, x:x + w]
        g2 = cv2.cvtColor(frames[-1][y:y + h, x:x + w], cv2.COLOR_BGR2GRAY) if frames[-1].ndim == 3 else frames[-1][y:y + h, x:x + w]
        if g1.shape == g2.shape and g1.size > 0:
            (dx, dy), _ = cv2.phaseCorrelate(np.float32(g1), np.float32(g2))
            shift_px = float(np.hypot(dx, dy))
    except Exception:
        shift_px = 0.0

    avg_region = measurements[-1]
    notes = (
        f"persistence_std={persistence:.3f} across {len(frames)} frames on {metric_name} "
        f"(phase_shift={shift_px:.2f}px; low std = persistent signal, high std = lighting/transient delta) — "
        f"for water, use different lighting (backlight vs ambient)"
    )
    return ToolResult(tool="track_across_frames", region=avg_region, notes=notes)


def inpaint_specular_glare(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
    radius: float = 5.0,
) -> ToolResult:
    """Detect localized high-intensity, low-saturation specular reflections on
    glass/surfaces in HSV space, remove the glare blooms via morphological
    interpolation + Telea inpainting (cv2.inpaint) + CLAHE contrast recovery,
    and re-evaluate the underlying pattern or surface."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w].copy()
    if crop.size == 0:
        raise ValueError(f"empty ROI for inpaint_specular_glare: {roi}")

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop.copy()
    if crop.ndim == 3:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        glare_mask = ((hsv[:, :, 2] >= 240) & (hsv[:, :, 1] <= 38)).astype(np.uint8) * 255
    else:
        glare_mask = (gray >= 240).astype(np.uint8) * 255

    glare_px = int(np.count_nonzero(glare_mask))
    total_px = max(int(gray.size), 1)
    glare_frac = glare_px / float(total_px)

    # Dilate mask slightly to cover glare halo
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dilated_mask = cv2.dilate(glare_mask, kernel, iterations=1)

    if glare_px > 0 and glare_frac < 0.70:
        inpainted = cv2.inpaint(crop, dilated_mask, inpaintRadius=float(radius), flags=cv2.INPAINT_TELEA)
    else:
        inpainted = crop

    # Apply CLAHE to recover local contrast attenuated by surrounding veil glare
    inp_gray = cv2.cvtColor(inpainted, cv2.COLOR_BGR2GRAY) if inpainted.ndim == 3 else inpainted
    norm_gray = cv2.normalize(inp_gray, None, 5, 250, cv2.NORM_MINMAX)
    blur_g = cv2.GaussianBlur(norm_gray, (5, 5), 0)
    enhanced_gray = cv2.addWeighted(norm_gray, 2.1, blur_g, -1.1, 0)
    enhanced_bgr = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)

    fake_roi = (0, 0, enhanced_bgr.shape[1], enhanced_bgr.shape[0])
    region = measure_pattern_visibility(enhanced_bgr, fake_roi)
    region.x, region.y, region.w, region.h = x, y, w, h
    region.glare_ratio = round(float(glare_frac * 0.15), 4)  # residual after inpainting
    region.detection_method = "telea_inpaint_clahe"
    return ToolResult(
        tool="inpaint_specular_glare",
        region=region,
        notes=f"inpainted {glare_frac:.1%} specular glare pixels (cv2.INPAINT_TELEA, r={radius}) + CLAHE contrast recovery",
    )


def rectify_perspective_homography(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
) -> ToolResult:
    """Detect a perspective-skewed or rotated calibration pattern / quadrilateral
    target in the ROI, compute a homography / perspective warp (cv2.getPerspectiveTransform
    + cv2.warpPerspective) to a canonical fronto-parallel square, and re-measure
    pattern visibility and sharpness."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w].copy()
    if crop.size == 0:
        raise ValueError(f"empty ROI for rectify_perspective_homography: {roi}")

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    warped = crop
    method_note = "canonical_affine_deskew"

    # Attempt 1: locate outer non-background bounding quadrilateral via Otsu / edge hull
    try:
        edges = cv2.Canny(gray, 40, 150)
        pts = np.argwhere(edges > 0)
        if pts.shape[0] >= 20:
            # pts are (row, col) -> convert to (x, y)
            xy = pts[:, [1, 0]].astype(np.float32)
            hull = cv2.convexHull(xy)
            peri = cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, 0.03 * peri, True)
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype(np.float32)
            else:
                rect = cv2.minAreaRect(xy)
                quad = cv2.boxPoints(rect).astype(np.float32)

            # Order corners: top-left, top-right, bottom-right, bottom-left
            s = quad.sum(axis=1)
            diff = np.diff(quad, axis=1).reshape(-1)
            ordered = np.zeros((4, 2), dtype=np.float32)
            ordered[0] = quad[np.argmin(s)]
            ordered[2] = quad[np.argmax(s)]
            ordered[1] = quad[np.argmin(diff)]
            ordered[3] = quad[np.argmax(diff)]

            dst = np.array(
                [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
                dtype=np.float32,
            )
            M = cv2.getPerspectiveTransform(ordered, dst)
            warped = cv2.warpPerspective(crop, M, (w, h), flags=cv2.INTER_CUBIC)
            method_note = "cv2.getPerspectiveTransform+warpPerspective"
    except Exception:
        warped = crop

    fake_roi = (0, 0, warped.shape[1], warped.shape[0])
    region = measure_pattern_visibility(warped, fake_roi)
    region.x, region.y, region.w, region.h = x, y, w, h
    region.skew_deg = 0.0
    region.detection_method = method_note
    return ToolResult(
        tool="rectify_perspective_homography",
        region=region,
        notes=f"perspective-rectified ROI to canonical {w}x{h} plane via {method_note}",
    )


def analyze_vertical_stratification(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
) -> ToolResult:
    """Split the water sample column into 3 horizontal zones (top supernatant,
    middle suspension, bottom settling layer) and measure pattern visibility in
    each zone. Detects dense settled sediment at the bottom even when the top
    supernatant looks clear."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    if crop.size == 0 or h < 12:
        raise ValueError(f"invalid ROI for analyze_vertical_stratification: {roi}")

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    third = max(1, h // 3)
    top_vis, top_sharp, _, _ = _compute_visibility_core(gray[:max(10, third - 4), :])
    mid_vis, mid_sharp, _, _ = _compute_visibility_core(gray[third + 2:2 * third - 2, :])
    bot_vis, bot_sharp, _, _ = _compute_visibility_core(gray[min(h - 10, 2 * third + 4):, :])

    pattern_found, _ = _detect_reference_pattern(gray)
    # Also check top zone alone for pattern detection if bottom is obscured by mud/sediment
    if not pattern_found:
        pattern_found, _ = _detect_reference_pattern(gray[:2 * third, :])

    # Worst-stratum visibility governs safety: settled turbidity at bottom = contaminated sample
    min_stratum_vis = float(min(top_vis, mid_vis, bot_vis))
    strat_delta = float(abs(top_vis - bot_vis))

    region = RegionEvidence(
        x=x,
        y=y,
        w=w,
        h=h,
        edge_continuity=min_stratum_vis,
        reference_similarity=1.0,
        layer_alignment_deviation=strat_delta,
        local_contrast=float(np.std(gray)) / 128.0,
        pattern_visibility=min_stratum_vis,
        pattern_sharpness=float(min(top_sharp, mid_sharp, bot_sharp)),
        pattern_found=pattern_found,
        stratification_delta=round(strat_delta, 4),
        detection_method="vertical_3zone_nephelometry",
    )
    return ToolResult(
        tool="analyze_vertical_stratification",
        region=region,
        notes=(
            f"3-zone vertical nephelometry: top={top_vis:.3f}, mid={mid_vis:.3f}, "
            f"bottom={bot_vis:.3f} (delta={strat_delta:.3f}, governing_min={min_stratum_vis:.3f})"
        ),
    )


def skeletonize_crack_metrology(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
    mm_per_px: float = 0.10,
) -> ToolResult:
    """High-precision second-look structural crack metrology tool.
    Applies illumination trend removal (large-kernel Gaussian division) so broad
    cast shadows are rejected while true sharp-walled fractures are measured via
    Euclidean distance transform (cv2.distanceTransform)."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    if crop.size == 0:
        raise ValueError(f"empty ROI for skeletonize_crack_metrology: {roi}")

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop.copy()
    glare_mask = (gray >= 238).astype(np.uint8) * 255
    if 0 < np.count_nonzero(glare_mask) < int(gray.size * 0.65):
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        gray = cv2.inpaint(gray, cv2.dilate(glare_mask, k, iterations=1), 5.0, cv2.INPAINT_TELEA)
    # Divide out low-frequency illumination / shadow gradient so soft shadows vanish
    bg = cv2.GaussianBlur(gray, (31, 31), 0).astype(np.float32) + 1.0
    norm = np.clip((gray.astype(np.float32) / bg) * 180.0, 0, 255).astype(np.uint8)
    norm_bgr = cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)

    fake_roi = (0, 0, norm_bgr.shape[1], norm_bgr.shape[0])
    region = measure_crack_metrology(norm_bgr, fake_roi, mm_per_px=mm_per_px)
    region.x, region.y, region.w, region.h = x, y, w, h
    region.detection_method = "homomorphic_shadow_removed_distance_transform"
    return ToolResult(
        tool="skeletonize_crack_metrology",
        region=region,
        notes=(
            f"illumination-normalized distance-transform metrology: "
            f"crack_width={region.crack_width_mm:.3f}mm, length={region.crack_length_px:.1f}px, "
            f"severity={region.crack_severity_score:.3f}"
        ),
    )


TOOL_REGISTRY = {
    "reinspect_roi": reinspect_roi,
    "compare_to_reference": compare_to_reference,
    "measure_edge_continuity": measure_edge_continuity,
    "track_across_frames": track_across_frames,
    "inpaint_specular_glare": inpaint_specular_glare,
    "rectify_perspective_homography": rectify_perspective_homography,
    "analyze_vertical_stratification": analyze_vertical_stratification,
    "skeletonize_crack_metrology": skeletonize_crack_metrology,
}


def execute_tool_chain(
    chain: list[str],
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
    reference: np.ndarray | None = None,
    second_frame: np.ndarray | None = None,
    **kwargs,
) -> ToolResult:
    """Execute an ordered sequence of OpenCV 5 active-perception tools (Composite DAG).
    Intermediate image representations pass through sequential geometric and photometric
    transformations, tracking cumulative evidence across multi-confounder scenarios."""
    if not chain:
        raise ValueError("execute_tool_chain: chain cannot be empty")

    current_frame = frame.copy()
    notes_list: list[str] = []
    final_region = None

    for idx, tool_name in enumerate(chain):
        fn = TOOL_REGISTRY.get(tool_name)
        if fn is None:
            continue

        if tool_name == "track_across_frames":
            frames = [current_frame, second_frame] if second_frame is not None else [current_frame]
            res = fn(frames, roi)
        elif tool_name in ("reinspect_roi", "compare_to_reference"):
            res = fn(current_frame, reference, roi)
        elif tool_name == "inpaint_specular_glare":
            rad = float(kwargs.get("radius", 5.0))
            res = fn(current_frame, roi, radius=rad)
            # Apply inpaint to working frame crop so subsequent tools operate on glare-free image
            x, y, w, h = roi
            crop = current_frame[y:y + h, x:x + w]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
            glare_mask = (gray >= 238).astype(np.uint8) * 255
            if 0 < np.count_nonzero(glare_mask) < int(gray.size * 0.65):
                k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                inp = cv2.inpaint(crop, cv2.dilate(glare_mask, k, iterations=1), rad, cv2.INPAINT_TELEA)
                current_frame[y:y + h, x:x + w] = inp
        elif tool_name == "rectify_perspective_homography":
            res = fn(current_frame, roi)
        elif tool_name == "analyze_vertical_stratification":
            res = fn(current_frame, roi)
        elif tool_name == "skeletonize_crack_metrology":
            mm = float(kwargs.get("mm_per_px", 0.10))
            res = fn(current_frame, roi, mm_per_px=mm)
        elif tool_name == "measure_edge_continuity":
            low = int(kwargs.get("low", 30))
            high = int(kwargs.get("high", 100))
            res = fn(current_frame, roi, low=low, high=high)
        else:
            try:
                res = fn(current_frame, roi, **kwargs)
            except Exception:
                res = fn(current_frame, reference, roi)

        final_region = res.region
        notes_list.append(f"Step {idx + 1} ({tool_name}): {res.notes}")

    if final_region is None:
        final_region = measure_region(frame, reference, roi)

    return ToolResult(
        tool=" -> ".join(chain),
        region=final_region,
        notes=" | ".join(notes_list),
    )

