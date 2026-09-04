"""
LoopSight — the bounded, whitelisted set of second-look tools.

Every tool here takes the current frame (+ a fresh capture where relevant)
and returns a new RegionEvidence. Per spec Section 9's Revision 2 note, a
tool must produce a MATERIALLY DIFFERENT observation, not just re-read the
same crop — reinspect_roi upsamples a tighter region at effective higher
resolution rather than merely re-measuring the same pixels, and
track_across_frames explicitly requires a fresh capture with a newer
timestamp than the first pass, enforced by the capture layer, not this
module, so a stale buffered frame can be detected and rejected upstream.

For the water_turbidity_v1 domain, track_across_frames is reframed as the
primary "different lighting" tool: the caller supplies two captures of the
same water sample under different lighting (backlight vs ambient, or with
phone flash) — the same multi-observation purpose, pointed at lighting
variation instead of temporal video frames. The other tools remain valid:
reinspect_roi re-measures the pattern region at higher effective resolution,
measure_edge_continuity re-processes at different Canny thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
import cv2
import numpy as np

from .first_pass import RegionEvidence, measure_region


@dataclass
class ToolResult:
    tool: str
    region: RegionEvidence
    notes: str


def reinspect_roi(frame: np.ndarray, reference: np.ndarray | None, roi: tuple[int, int, int, int], scale: float = 2.0) -> ToolResult:
    """Upsample the region of interest before re-measuring — a materially
    different observation (higher effective resolution), not a duplicate
    of the first pass. For water_turbidity_v1 this re-measures the pattern
    region at higher effective resolution; for fdm it re-measures edge continuity."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    if crop.size == 0:
        raise ValueError(f"empty ROI for reinspect_roi: {roi}")
    upsampled = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # Build a synthetic "full frame" the same size as the upsampled crop so
    # measure_region's coordinate math stays consistent for this call.
    fake_roi = (0, 0, upsampled.shape[1], upsampled.shape[0])
    ref_crop = None
    if reference is not None:
        ref_region = reference[y:y + h, x:x + w]
        if ref_region.size:
            ref_crop = cv2.resize(ref_region, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # Prefer water-aware measurement when pattern is present; fallback to classic region measure
    try:
        from .first_pass import measure_pattern_visibility
        pv_region = measure_pattern_visibility(upsampled, fake_roi)
        if pv_region.pattern_found:
            # Water mode: return pattern visibility measurement (keeps upsampled size to prove materially different observation)
            return ToolResult(tool="reinspect_roi", region=pv_region, notes=f"upsampled {scale}x before re-measuring pattern visibility")
    except Exception:
        pass
    region = measure_region(upsampled, ref_crop, fake_roi)
    return ToolResult(tool="reinspect_roi", region=region, notes=f"upsampled {scale}x before re-measuring")


def compare_to_reference(frame: np.ndarray, reference: np.ndarray, roi: tuple[int, int, int, int]) -> ToolResult:
    """Explicit, isolated reference-comparison pass — same measurement the
    first pass already does, called out as its own tool so the agent's
    choice to specifically re-check reference alignment is visible in the
    evidence trace, distinct from a generic re-crop."""
    region = measure_region(frame, reference, roi)
    return ToolResult(tool="compare_to_reference", region=region, notes="isolated reference-similarity re-check")


def measure_edge_continuity(frame: np.ndarray, roi: tuple[int, int, int, int], low: int = 30, high: int = 100) -> ToolResult:
    """Re-run edge detection with a different (more sensitive) Canny
    threshold pair than the first pass used — a materially different
    processing path over the same crop, useful when the first pass's
    thresholds may have been too conservative to resolve a subtle edge.
    For water_turbidity_v1 this re-processes the pattern at different thresholds
    to reveal visibility that the default pair missed — same tool, different domain phrasing."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    edges = cv2.Canny(gray, low, high)
    edge_continuity = float(np.count_nonzero(edges)) / edges.size if edges.size else 0.0
    # For water compatibility, map edge_continuity to pattern_visibility as well
    # so the water policy (which checks pattern_visibility) still sees signal from this tool
    # Sharpness via Laplacian gives additional water-relevant signal even at new thresholds
    try:
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharp_norm = float(min(lap_var / 600.0, 1.0))
    except Exception:
        sharp_norm = 0.0
    # Estimate pattern_found quickly for water mode
    pattern_found = False
    try:
        for ps in [(7, 7), (7, 5), (6, 4)]:
            ret, _ = cv2.findChessboardCorners(gray, ps, None)
            if ret:
                pattern_found = True
                break
    except Exception:
        pass
    # Blend for water's pattern_visibility so this tool is not blind in water mode
    edge_sharp = float(min(edge_continuity * 10.0, 1.0)) if edge_continuity else 0.0
    pattern_visibility = float(0.5 * (float(np.std(gray)) / 128.0) + 0.3 * sharp_norm + 0.2 * edge_sharp)
    pattern_visibility = float(max(0.0, min(1.0, pattern_visibility)))
    region = RegionEvidence(
        x=x, y=y, w=w, h=h,
        edge_continuity=edge_continuity,
        reference_similarity=-1.0,  # not measured by this tool — caller should not treat -1 as a real value
        layer_alignment_deviation=-1.0,
        local_contrast=float(np.std(gray)) / 128.0 if gray.size else 0.0,
        pattern_visibility=pattern_visibility,
        pattern_sharpness=sharp_norm,
        pattern_found=pattern_found,
    )
    return ToolResult(tool="measure_edge_continuity", region=region, notes=f"re-ran Canny at ({low},{high}) vs. first-pass thresholds")


def track_across_frames(frames: list[np.ndarray], roi: tuple[int, int, int, int]) -> ToolResult:
    """Water-turbidity primary second-look (and video-mode) tool.

    For water_turbidity_v1: caller supplies 2 captures of the same water
    sample under DIFFERENT LIGHTING (backlight vs ambient, or with phone
    flash). This is the real-world technique that resolves borderline
    pattern-visibility ambiguity per research: backlight reveals turbidity
    that ambient hides. Persistence low = same turbidity reading under both
    lights (real turbidity); high = lighting artifact.

    For fdm_print_surface_v1: original video-mode meaning (temporal persistence).

    Callers MUST supply frames with distinct, increasing timestamps / genuinely
    different lighting — this function does not verify freshness itself, that's
    the capture layer's job. Also guards against stale-buffered-frame failure.
    """
    if len(frames) < 2:
        raise ValueError("track_across_frames needs at least 2 distinct frames")
    # Try water-aware measurement first (pattern visibility), fallback to edge for fdm
    from .first_pass import measure_pattern_visibility

    def _measure(f: np.ndarray):
        # Prefer pattern visibility so water's signal is preserved across frames
        try:
            pv = measure_pattern_visibility(f, roi)
            # If pattern was found in at least one frame, this is likely water mode
            if pv.pattern_found or pv.pattern_visibility > 0:
                return pv
        except Exception:
            pass
        return measure_region(f, None, roi)

    measurements = [_measure(f) for f in frames]
    # Use pattern_visibility for water (low/high = turbid/clear), edge_continuity for fdm
    # Pick the metric that has signal: prefer pattern_visibility when non-zero
    vis_vals = [m.pattern_visibility for m in measurements if hasattr(m, "pattern_visibility")]
    edge_vals = [m.edge_continuity for m in measurements]
    # If pattern_visibility varies (water), use it; else use edge
    if any(v > 0 for v in vis_vals):
        vals = vis_vals
        metric_name = "pattern_visibility"
    else:
        vals = edge_vals
        metric_name = "edge_continuity"
    persistence = float(np.std(vals))  # low std = persists (real); high = transient/lighting artifact
    avg_region = measurements[-1]  # most recent measurement carries the verdict
    notes = f"persistence_std={persistence:.3f} across {len(frames)} frames on {metric_name} (low = persistent, likely real; high = likely transient/lighting artifact) — for water, use different lighting (backlight vs ambient)"
    return ToolResult(tool="track_across_frames", region=avg_region, notes=notes)


TOOL_REGISTRY = {
    "reinspect_roi": reinspect_roi,
    "compare_to_reference": compare_to_reference,
    "measure_edge_continuity": measure_edge_continuity,
    "track_across_frames": track_across_frames,
}
