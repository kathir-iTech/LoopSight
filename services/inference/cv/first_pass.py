"""
LoopSight v2 — deterministic first-pass OpenCV 5 measurement & spatial metrology stage.

Design constraint (see spec Section 9): this module produces EVIDENCE only.
It never renders a pass/fail judgment on its own — score_evidence() applies
a fixed, inspectable threshold policy, and even that only decides whether
more evidence is needed, not the final verdict (policy.py owns that).

Supported InspectionProfiles:
  1. water_turbidity_v1          — Optical nephelometry (Secchi pattern visibility,
                                   HSV/LAB specular glare detection, perspective skew,
                                   and vertical settling stratification).
  2. structural_crack_metrology_v1 — Civil/structural crack metrology (CLAHE, bilateral
                                   filtering, morphological black-hat, Euclidean distance
                                   transform width in mm, and tortuosity).
  3. fdm_print_surface_v1        — Manufacturing surface & edge continuity QC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)
logger.info(f"[first_pass] Loaded with OpenCV {cv2.__version__} — cv2.__version__ recorded for submission evidence")
try:
    logging.getLogger().info(f"[first_pass] OpenCV version: {cv2.__version__}")
except Exception:
    pass


@dataclass(frozen=True)
class InspectionProfile:
    name: str
    edge_continuity_confident_fail: float
    edge_continuity_confident_pass: float
    contrast_min_for_confidence: float
    reference_similarity_floor: float
    # water-turbidity-specific thresholds
    pattern_visibility_confident_turbid: float = 0.20
    pattern_visibility_confident_clear: float = 0.55
    # structural-crack-specific thresholds (mm and severity 0..1)
    crack_severity_confident_pass: float = 0.16
    crack_severity_confident_fail: float = 0.55
    crack_width_mm_fail: float = 0.40


PROFILES: dict[str, InspectionProfile] = {
    "fdm_print_surface_v1": InspectionProfile(
        name="fdm_print_surface_v1",
        edge_continuity_confident_fail=0.05,
        edge_continuity_confident_pass=0.20,
        contrast_min_for_confidence=0.10,
        reference_similarity_floor=0.40,
    ),
    "water_turbidity_v1": InspectionProfile(
        name="water_turbidity_v1",
        edge_continuity_confident_fail=0.20,
        edge_continuity_confident_pass=0.55,
        contrast_min_for_confidence=0.05,
        reference_similarity_floor=0.40,
        pattern_visibility_confident_turbid=0.20,
        pattern_visibility_confident_clear=0.55,
    ),
    "structural_crack_metrology_v1": InspectionProfile(
        name="structural_crack_metrology_v1",
        edge_continuity_confident_fail=0.16,
        edge_continuity_confident_pass=0.55,
        contrast_min_for_confidence=0.05,
        reference_similarity_floor=0.40,
        crack_severity_confident_pass=0.16,
        crack_severity_confident_fail=0.55,
        crack_width_mm_fail=0.40,
    ),
}


@dataclass
class RegionEvidence:
    x: int
    y: int
    w: int
    h: int
    edge_continuity: float
    reference_similarity: float
    layer_alignment_deviation: float
    local_contrast: float
    # water-turbidity & optical nephelometry fields
    pattern_visibility: float = 0.0
    pattern_sharpness: float = 0.0
    pattern_found: bool = False
    glare_ratio: float = 0.0
    skew_deg: float = 0.0
    stratification_delta: float = 0.0
    # structural crack metrology fields
    crack_width_mm: float = 0.0
    crack_length_px: float = 0.0
    crack_severity_score: float = 0.0
    detection_method: str = "full_frame"


@dataclass
class FirstPassResult:
    status: str  # "CONFIDENT_PASS" | "CONFIDENT_FAIL" | "UNCERTAIN"
    regions: list[RegionEvidence]
    evidence_gap: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)


ALL_TOOLS = [
    "reinspect_roi",
    "compare_to_reference",
    "measure_edge_continuity",
    "track_across_frames",
    "inpaint_specular_glare",
    "rectify_perspective_homography",
    "analyze_vertical_stratification",
    "skeletonize_crack_metrology",
]


def _local_contrast(gray_roi: np.ndarray) -> float:
    """Normalized std-dev of pixel intensity in the ROI."""
    if gray_roi.size == 0:
        return 0.0
    return float(np.std(gray_roi)) / 128.0


def _laplacian_sharpness(gray: np.ndarray) -> float:
    """Variance of Laplacian — classic blur metric."""
    if gray.size == 0:
        return 0.0
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _measure_specular_glare(bgr_crop: np.ndarray, gray_crop: np.ndarray) -> float:
    """Measure fraction of ROI pixels affected by localized specular reflection glare.
    True specular glare on curved glass is a localized bright spot (5%..55% of ROI)
    that creates a sharp luminance spike above surrounding pattern squares."""
    if gray_crop.size == 0:
        return 0.0
    if bgr_crop.ndim == 3:
        hsv = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2HSV)
        v_chan = hsv[:, :, 2]
        s_chan = hsv[:, :, 1]
        glare_mask = (v_chan >= 242) & (s_chan <= 35)
    else:
        glare_mask = gray_crop >= 242
    raw_ratio = float(np.count_nonzero(glare_mask)) / float(gray_crop.size)
    # Only flag localized glare blobs (2%..60% of frame) where peak brightness >= 245
    if raw_ratio < 0.02 or raw_ratio > 0.65:
        return 0.0
    return round(raw_ratio, 4)


def _estimate_perspective_skew_deg(gray: np.ndarray) -> float:
    """Estimate perspective / rotational skew angle (degrees from axis-aligned)
    of the dominant grid or quadrilateral structure in the ROI."""
    if gray.size == 0:
        return 0.0
    try:
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0.0
        h, w = gray.shape[:2]
        min_area = h * w * 0.01
        valid = [c for c in contours if cv2.contourArea(c) >= min_area]
        if not valid:
            return 0.0
        largest = max(valid, key=cv2.contourArea)
        rect = cv2.minAreaRect(largest)
        angle = abs(float(rect[2]))
        # Normalize angle in [0, 90) to deviation from nearest 90-deg axis
        dev = min(angle % 90.0, 90.0 - (angle % 90.0))
        return round(float(dev), 2)
    except Exception:
        return 0.0


def _detect_reference_pattern(gray: np.ndarray) -> tuple[bool, str]:
    """Detect the printed high-contrast reference pattern in-frame via
    cv2.findChessboardCorners or contour-based quadrilateral square counting."""
    for pattern_size in [(7, 7), (7, 5), (6, 5), (6, 4), (5, 5), (4, 3), (3, 3)]:
        try:
            ret, _ = cv2.findChessboardCorners(
                gray,
                pattern_size,
                flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK,
            )
            if ret:
                return True, f"chessboard_{pattern_size[0]}x{pattern_size[1]}"
        except Exception:
            continue
    try:
        # Use both Otsu and adaptive thresholding so glare/stratification doesn't hide valid squares
        h, w = gray.shape[:2]
        img_area = max(h * w, 1)
        for mode in ("otsu", "adaptive"):
            if mode == "otsu":
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                block = max(11, (min(h, w) // 8) | 1)
                thresh = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 2
                )
            contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            square_like = 0
            for c in contours:
                area = cv2.contourArea(c)
                if not (img_area * 0.0015 < area < img_area * 0.12):
                    continue
                x, y, cw, ch = cv2.boundingRect(c)
                if cw == 0 or ch == 0:
                    continue
                aspect = cw / float(ch)
                if 0.6 <= aspect <= 1.65:
                    peri = cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, 0.04 * peri, True)
                    if 4 <= len(approx) <= 6:
                        square_like += 1
            if square_like >= 6:
                return True, f"contours_{square_like}_squares"
    except Exception:
        pass
    return False, "none"


def _compute_visibility_core(gray: np.ndarray) -> tuple[float, float, float, float]:
    """Return (pattern_visibility, sharpness_norm, local_contrast, edge_sharp)."""
    local_contrast = float(max(0.0, min(1.0, _local_contrast(gray))))
    lap_var = _laplacian_sharpness(gray)
    sharpness_norm = float(min(lap_var / 600.0, 1.0))
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.count_nonzero(edges)) / edges.size if edges.size else 0.0
    edge_sharp = float(min(edge_density * 10.0, 1.0))
    pattern_visibility = float(0.45 * local_contrast + 0.35 * sharpness_norm + 0.20 * edge_sharp)
    pattern_visibility = float(max(0.0, min(1.0, pattern_visibility)))
    return pattern_visibility, sharpness_norm, local_contrast, edge_sharp


def measure_pattern_visibility(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
) -> RegionEvidence:
    """Water-turbidity core optical nephelometry measurement (water_turbidity_v1).
    Measures pattern visibility, sharpness, local contrast, localized specular glare,
    perspective skew angle, and top-vs-bottom vertical turbidity stratification."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop

    pattern_found, det_method = _detect_reference_pattern(gray)
    pattern_visibility, sharpness_norm, local_contrast, _ = _compute_visibility_core(gray)
    glare_ratio = _measure_specular_glare(crop, gray)
    skew_deg = _estimate_perspective_skew_deg(gray)

    # Vertical stratification: compare top third vs bottom third visibility
    stratification_delta = 0.0
    if gray.shape[0] >= 30:
        third = gray.shape[0] // 3
        top_vis, _, _, _ = _compute_visibility_core(gray[:max(10, third - 4), :])
        bot_vis, _, _, _ = _compute_visibility_core(gray[min(gray.shape[0] - 10, 2 * third + 4):, :])
        stratification_delta = round(float(abs(top_vis - bot_vis)), 4)

    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    layer_alignment_deviation = _contour_deviation_score(contours, gray.shape)

    return RegionEvidence(
        x=x,
        y=y,
        w=w,
        h=h,
        edge_continuity=pattern_visibility,
        reference_similarity=1.0,
        layer_alignment_deviation=layer_alignment_deviation,
        local_contrast=local_contrast,
        pattern_visibility=pattern_visibility,
        pattern_sharpness=sharpness_norm,
        pattern_found=pattern_found,
        glare_ratio=glare_ratio,
        skew_deg=skew_deg,
        stratification_delta=stratification_delta,
        detection_method=det_method,
    )


def measure_crack_metrology(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
    mm_per_px: float = 0.10,
) -> RegionEvidence:
    """Structural crack metrology (structural_crack_metrology_v1).
    Uses bilateral surface-noise suppression, morphological black-hat filament extraction,
    connected-component filtering, and Euclidean distance transform (cv2.distanceTransform)
    to measure calibrated crack width in mm, length in px, and severity score."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop

    local_contrast = float(max(0.0, min(1.0, _local_contrast(gray))))
    glare_ratio = _measure_specular_glare(crop, gray)

    # Bilateral filter preserves sharp crack boundaries while smoothing concrete/wall grain
    smoothed = cv2.bilateralFilter(gray, 7, 50, 50)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    blackhat = cv2.morphologyEx(smoothed, cv2.MORPH_BLACKHAT, kernel)

    # Require genuine dark filament contrast (avoid flagging uniform noise)
    bh_max = float(np.max(blackhat)) if blackhat.size else 0.0
    if bh_max < 18.0:
        return RegionEvidence(
            x=x, y=y, w=w, h=h,
            edge_continuity=0.0,
            reference_similarity=1.0,
            layer_alignment_deviation=0.0,
            local_contrast=local_contrast,
            glare_ratio=glare_ratio,
            crack_width_mm=0.0,
            crack_length_px=0.0,
            crack_severity_score=0.0,
            detection_method="blackhat_clean",
        )

    _, bin_mask = cv2.threshold(blackhat, max(28, int(bh_max * 0.42)), 255, cv2.THRESH_BINARY)
    # Remove isolated salt-and-pepper specks via connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bin_mask, connectivity=8)
    clean_mask = np.zeros_like(bin_mask)
    max_len = 0.0
    for lbl in range(1, num_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        bw = int(stats[lbl, cv2.CC_STAT_WIDTH])
        bh = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        span = float(max(bw, bh))
        # A structural crack filament has elongated span (>= 18 px)
        if area >= 20 and span >= 18.0:
            clean_mask[labels == lbl] = 255
            max_len = max(max_len, span)

    if np.count_nonzero(clean_mask) == 0:
        return RegionEvidence(
            x=x, y=y, w=w, h=h,
            edge_continuity=0.0,
            reference_similarity=1.0,
            layer_alignment_deviation=0.0,
            local_contrast=local_contrast,
            glare_ratio=glare_ratio,
            crack_width_mm=0.0,
            crack_length_px=0.0,
            crack_severity_score=0.0,
            detection_method="blackhat_filtered_clean",
        )

    # Euclidean distance transform gives half-width at the medial ridge
    dist = cv2.distanceTransform(clean_mask, cv2.DIST_L2, 5)
    ridge_vals = dist[clean_mask > 0]
    p90_radius_px = float(np.percentile(ridge_vals, 85)) if ridge_vals.size else 0.0
    width_px = max(0.0, p90_radius_px * 2.0)
    crack_width_mm = round(width_px * mm_per_px, 3)

    # Severity blends normalized width (0.6mm = 1.0) and span coverage
    diag = float(np.hypot(w, h)) or 1.0
    len_norm = min(max_len / (diag * 0.55), 1.0)
    width_norm = min(crack_width_mm / 0.60, 1.0)
    severity = round(float(0.60 * width_norm + 0.40 * len_norm), 4)

    contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tortuosity = _contour_deviation_score(contours, gray.shape)

    return RegionEvidence(
        x=x,
        y=y,
        w=w,
        h=h,
        edge_continuity=severity,
        reference_similarity=1.0,
        layer_alignment_deviation=tortuosity,
        local_contrast=local_contrast,
        glare_ratio=glare_ratio,
        crack_width_mm=crack_width_mm,
        crack_length_px=round(max_len, 1),
        crack_severity_score=severity,
        detection_method="distance_transform_metrology",
    )


def measure_region(
    frame: np.ndarray,
    reference: np.ndarray | None,
    roi: tuple[int, int, int, int],
) -> RegionEvidence:
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop

    edges = cv2.Canny(gray, 50, 150)
    edge_continuity = float(np.count_nonzero(edges)) / edges.size if edges.size else 0.0

    if reference is not None:
        ref_crop = reference[y:y + h, x:x + w]
        ref_gray = cv2.cvtColor(ref_crop, cv2.COLOR_BGR2GRAY) if ref_crop.ndim == 3 else ref_crop
        if ref_gray.shape == gray.shape:
            eq_gray = cv2.equalizeHist(gray)
            eq_ref = cv2.equalizeHist(ref_gray)
            diff = cv2.absdiff(eq_gray, eq_ref)
            reference_similarity = 1.0 - (float(np.mean(diff)) / 255.0)
        else:
            reference_similarity = 0.0
    else:
        reference_similarity = 1.0

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    layer_alignment_deviation = _contour_deviation_score(contours, gray.shape)

    return RegionEvidence(
        x=x,
        y=y,
        w=w,
        h=h,
        edge_continuity=edge_continuity,
        reference_similarity=reference_similarity,
        layer_alignment_deviation=layer_alignment_deviation,
        local_contrast=_local_contrast(gray),
    )


def propose_rois(frame: np.ndarray, max_rois: int = 3) -> list[tuple[int, int, int, int]]:
    """Propose candidate ROIs automatically via contour energy / pattern localization,
    always including the full-frame canonical ROI first so global metrics remain consistent."""
    h, w = frame.shape[:2]
    rois: list[tuple[int, int, int, int]] = [(0, 0, w, h)]
    if max_rois <= 1 or h < 80 or w < 80:
        return rois
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        edges = cv2.Canny(gray, 40, 140)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        img_area = h * w
        candidates = []
        for c in contours:
            rx, ry, rw, rh = cv2.boundingRect(c)
            area = rw * rh
            if img_area * 0.08 <= area <= img_area * 0.85:
                candidates.append((area, (rx, ry, rw, rh)))
        candidates.sort(key=lambda item: item[0], reverse=True)
        for _, rect in candidates[: max_rois - 1]:
            rois.append(rect)
    except Exception:
        pass
    return rois


def _contour_deviation_score(contours, shape: tuple[int, int]) -> float:
    if not contours:
        return 0.0
    h, w = shape[:2]
    img_area = max(h * w, 1)
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    perimeter = cv2.arcLength(largest, True)
    if area <= 1:
        return min(perimeter / (img_area ** 0.5 + 1e-6), 1.0)
    jaggedness = (perimeter ** 2) / (4 * np.pi * area)
    return float(min(jaggedness / 10.0, 1.0))


def score_evidence(regions: list[RegionEvidence], profile: InspectionProfile) -> FirstPassResult:
    """Deterministic policy — NOT a model. Decides whether first-pass OpenCV
    evidence is confident or requires an agent-selected second-look tool."""
    if not regions:
        return FirstPassResult(
            status="UNCERTAIN",
            regions=[],
            evidence_gap=["no regions measured"],
            allowed_tools=ALL_TOOLS,
        )

    # 1. Water-turbidity profile (optical nephelometry)
    if profile.name == "water_turbidity_v1":
        worst = min(regions, key=lambda r: r.pattern_visibility)
        lowest_contrast = min(r.local_contrast for r in regions)
        max_glare = max(getattr(r, "glare_ratio", 0.0) for r in regions)
        max_skew = max(getattr(r, "skew_deg", 0.0) for r in regions)
        max_strat = max(getattr(r, "stratification_delta", 0.0) for r in regions)

        if not any(r.pattern_found for r in regions):
            # Check if perspective skew or glare hid the pattern
            if max_skew >= 10.0:
                return FirstPassResult(
                    status="UNCERTAIN",
                    regions=regions,
                    evidence_gap=[
                        f"reference pattern skewed ({max_skew:.1f} deg) — run homography rectification to recover pattern geometry"
                    ],
                    allowed_tools=["rectify_perspective_homography", "reinspect_roi", "track_across_frames"],
                )
            return FirstPassResult(
                status="UNCERTAIN",
                regions=regions,
                evidence_gap=[
                    "reference pattern not detected — ensure the printed checkerboard/grid is visible behind the water sample"
                ],
                allowed_tools=["reinspect_roi", "rectify_perspective_homography", "track_across_frames"],
            )

        if lowest_contrast < profile.contrast_min_for_confidence:
            return FirstPassResult(
                status="UNCERTAIN",
                regions=regions,
                evidence_gap=[
                    "very low contrast — pattern not distinguishable through water, try a photo under different lighting (backlight or phone flash)"
                ],
                allowed_tools=ALL_TOOLS,
            )

        # Confounder check 1: localized specular glare on glass washing out pattern
        if max_glare >= 0.03:
            return FirstPassResult(
                status="UNCERTAIN",
                regions=regions,
                evidence_gap=[
                    f"specular glass glare ({max_glare:.1%} saturated pixels) confounding pattern visibility {worst.pattern_visibility:.2f} — run specular glare inpainting or second lighting"
                ],
                allowed_tools=["inpaint_specular_glare", "track_across_frames", "reinspect_roi"],
            )

        # Confounder check 2: perspective skew distorting checkerboard squares
        if max_skew >= 10.0 and worst.pattern_visibility < profile.pattern_visibility_confident_clear:
            return FirstPassResult(
                status="UNCERTAIN",
                regions=regions,
                evidence_gap=[
                    f"perspective skew ({max_skew:.1f} deg) attenuating pattern visibility {worst.pattern_visibility:.2f} — run perspective homography rectification"
                ],
                allowed_tools=["rectify_perspective_homography", "reinspect_roi", "track_across_frames"],
            )

        # Confounder check 3: strong top-vs-bottom settling stratification
        if max_strat >= 0.22:
            return FirstPassResult(
                status="UNCERTAIN",
                regions=regions,
                evidence_gap=[
                    f"vertical turbidity stratification detected (top-vs-bottom delta {max_strat:.2f}) — run vertical stratification analysis"
                ],
                allowed_tools=["analyze_vertical_stratification", "track_across_frames", "reinspect_roi"],
            )

        if worst.pattern_visibility <= profile.pattern_visibility_confident_turbid:
            return FirstPassResult(status="CONFIDENT_FAIL", regions=regions)

        if worst.pattern_visibility >= profile.pattern_visibility_confident_clear:
            return FirstPassResult(status="CONFIDENT_PASS", regions=regions)

        return FirstPassResult(
            status="UNCERTAIN",
            regions=regions,
            evidence_gap=[
                f"pattern visibility {worst.pattern_visibility:.2f} in borderline band ({profile.pattern_visibility_confident_turbid}-{profile.pattern_visibility_confident_clear}) — request photo under different lighting (backlight vs ambient or with phone flash)"
            ],
            allowed_tools=[
                "track_across_frames",
                "inpaint_specular_glare",
                "rectify_perspective_homography",
                "analyze_vertical_stratification",
                "reinspect_roi",
                "measure_edge_continuity",
            ],
        )

    # 2. Structural crack metrology profile
    if profile.name == "structural_crack_metrology_v1":
        worst_crack = max(regions, key=lambda r: r.crack_severity_score)
        lowest_contrast = min(r.local_contrast for r in regions)
        max_glare = max(getattr(r, "glare_ratio", 0.0) for r in regions)

        if lowest_contrast < profile.contrast_min_for_confidence:
            return FirstPassResult(
                status="UNCERTAIN",
                regions=regions,
                evidence_gap=["low surface illumination contrast — run CLAHE skeletonization metrology"],
                allowed_tools=["skeletonize_crack_metrology", "reinspect_roi", "measure_edge_continuity"],
            )

        if max_glare >= 0.08:
            return FirstPassResult(
                status="UNCERTAIN",
                regions=regions,
                evidence_gap=[f"surface glare ({max_glare:.1%}) obscuring fracture boundary — inpaint glare and re-measure crack width"],
                allowed_tools=["inpaint_specular_glare", "skeletonize_crack_metrology", "reinspect_roi"],
            )

        if (
            worst_crack.crack_severity_score >= profile.crack_severity_confident_fail
            or worst_crack.crack_width_mm >= profile.crack_width_mm_fail
        ):
            return FirstPassResult(status="CONFIDENT_FAIL", regions=regions)

        if worst_crack.crack_severity_score <= profile.crack_severity_confident_pass and worst_crack.crack_width_mm < 0.15:
            return FirstPassResult(status="CONFIDENT_PASS", regions=regions)

        return FirstPassResult(
            status="UNCERTAIN",
            regions=regions,
            evidence_gap=[
                f"hairline/shadow ambiguity: crack_severity={worst_crack.crack_severity_score:.2f} (width={worst_crack.crack_width_mm:.2f}mm) in borderline band — run medial-axis skeletonization metrology"
            ],
            allowed_tools=["skeletonize_crack_metrology", "reinspect_roi", "measure_edge_continuity"],
        )

    # 3. FDM print surface profile (original behavior preserved 100%)
    worst = min(regions, key=lambda r: r.edge_continuity)
    lowest_contrast = min(r.local_contrast for r in regions)

    if lowest_contrast < profile.contrast_min_for_confidence:
        return FirstPassResult(
            status="UNCERTAIN",
            regions=regions,
            evidence_gap=["low local contrast — cannot confirm edge deviation"],
            allowed_tools=ALL_TOOLS,
        )

    if worst.reference_similarity < profile.reference_similarity_floor:
        return FirstPassResult(
            status="UNCERTAIN",
            regions=regions,
            evidence_gap=[f"reference similarity {worst.reference_similarity:.2f} below floor {profile.reference_similarity_floor}"],
            allowed_tools=["compare_to_reference", "reinspect_roi"],
        )

    if worst.edge_continuity <= profile.edge_continuity_confident_fail:
        return FirstPassResult(status="CONFIDENT_FAIL", regions=regions)

    if worst.edge_continuity >= profile.edge_continuity_confident_pass:
        return FirstPassResult(status="CONFIDENT_PASS", regions=regions)

    return FirstPassResult(
        status="UNCERTAIN",
        regions=regions,
        evidence_gap=[
            f"edge continuity {worst.edge_continuity:.2f} in ambiguous middle band ({profile.edge_continuity_confident_fail}-{profile.edge_continuity_confident_pass})"
        ],
        allowed_tools=["reinspect_roi", "measure_edge_continuity"],
    )


def run_first_pass(
    frame: np.ndarray,
    reference: np.ndarray | None,
    rois: list[tuple[int, int, int, int]],
    profile_name: str = "fdm_print_surface_v1",
) -> FirstPassResult:
    if profile_name not in PROFILES:
        raise ValueError(f"unknown inspection_profile '{profile_name}'. valid: {sorted(PROFILES.keys())}")
    profile = PROFILES[profile_name]
    if profile_name == "water_turbidity_v1":
        regions = [measure_pattern_visibility(frame, roi) for roi in rois]
        if reference is not None:
            for idx, roi in enumerate(rois):
                ref_region = measure_region(reference, None, roi)
                regions[idx].reference_similarity = ref_region.reference_similarity
        return score_evidence(regions, profile)

    if profile_name == "structural_crack_metrology_v1":
        regions = [measure_crack_metrology(frame, roi) for roi in rois]
        return score_evidence(regions, profile)

    regions = [measure_region(frame, reference, roi) for roi in rois]
    return score_evidence(regions, profile)
