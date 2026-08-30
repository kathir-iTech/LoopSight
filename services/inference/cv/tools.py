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
    of the first pass."""
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
    thresholds may have been too conservative to resolve a subtle edge."""
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    edges = cv2.Canny(gray, low, high)
    edge_continuity = float(np.count_nonzero(edges)) / edges.size if edges.size else 0.0
    region = RegionEvidence(
        x=x, y=y, w=w, h=h,
        edge_continuity=edge_continuity,
        reference_similarity=-1.0,  # not measured by this tool — caller should not treat -1 as a real value
        layer_alignment_deviation=-1.0,
        local_contrast=float(np.std(gray)) / 128.0 if gray.size else 0.0,
    )
    return ToolResult(tool="measure_edge_continuity", region=region, notes=f"re-ran Canny at ({low},{high}) vs. first-pass thresholds")


def track_across_frames(frames: list[np.ndarray], roi: tuple[int, int, int, int]) -> ToolResult:
    """Video-mode only (Section 9's 'additive scope', not required for the
    v1 core loop). Checks whether the anomaly persists across multiple
    genuinely distinct frames, guarding specifically against the stale-
    buffered-frame failure mode flagged in Revision 2: callers MUST supply
    frames with distinct, increasing timestamps upstream of this function —
    it does not verify freshness itself, that's the capture layer's job."""
    if len(frames) < 2:
        raise ValueError("track_across_frames needs at least 2 distinct frames")
    measurements = [measure_region(f, None, roi) for f in frames]
    continuities = [m.edge_continuity for m in measurements]
    persistence = float(np.std(continuities))  # low std = anomaly persists (real); high std = likely transient artifact
    avg_region = measurements[-1]  # most recent measurement carries the verdict
    notes = f"persistence_std={persistence:.3f} across {len(frames)} frames (low = persistent, likely real; high = likely transient)"
    return ToolResult(tool="track_across_frames", region=avg_region, notes=notes)


TOOL_REGISTRY = {
    "reinspect_roi": reinspect_roi,
    "compare_to_reference": compare_to_reference,
    "measure_edge_continuity": measure_edge_continuity,
    "track_across_frames": track_across_frames,
}
