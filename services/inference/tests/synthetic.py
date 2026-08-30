"""
Synthetic test-image generators.

Per spec Section 27's testing strategy: pure-geometry CV functions should
be tested against synthetic fixtures with an obvious correct answer, not
only against real photos (which don't exist yet — the self-captured
dataset is Kathir's Phase 2/3 task, not something this sandbox can
produce). These functions stand in for "a clean edge" and "a broken edge"
until real print photos replace them.
"""

import numpy as np
import cv2


def make_clean_square(size: int = 200, margin: int = 40) -> np.ndarray:
    """A crisp, complete, high-contrast square boundary — stands in for a
    clean print surface with a continuous, well-defined edge."""
    img = np.full((size, size, 3), 40, dtype=np.uint8)  # dark background
    cv2.rectangle(img, (margin, margin), (size - margin, size - margin), (220, 220, 220), thickness=3)
    return img


def make_broken_square(size: int = 200, margin: int = 40, gap: int = 25) -> np.ndarray:
    """The same square with deliberate gaps in the boundary — stands in for
    a defect that breaks edge continuity (e.g. under-extrusion gaps)."""
    img = np.full((size, size, 3), 40, dtype=np.uint8)
    x0, y0, x1, y1 = margin, margin, size - margin, size - margin
    # Draw each side as a dashed line with real gaps, not a full rectangle.
    for (p0, p1) in [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]:
        _dashed_line(img, p0, p1, gap=gap)
    return img


def make_low_contrast_frame(size: int = 200) -> np.ndarray:
    """Near-uniform gray — stands in for a genuinely ambiguous, poorly-lit
    frame where the system should say UNCERTAIN rather than guess."""
    base = 128
    img = np.full((size, size, 3), base, dtype=np.uint8)
    noise = np.random.default_rng(42).integers(-3, 4, size=img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return img


def _dashed_line(img: np.ndarray, p0: tuple, p1: tuple, gap: int, dash: int = 15, thickness: int = 3, color=(220, 220, 220)):
    x0, y0 = p0
    x1, y1 = p1
    length = int(np.hypot(x1 - x0, y1 - y0))
    if length == 0:
        return
    dx, dy = (x1 - x0) / length, (y1 - y0) / length
    pos = 0
    draw = True
    while pos < length:
        seg_len = dash if draw else gap
        end_pos = min(pos + seg_len, length)
        if draw:
            sx, sy = int(x0 + dx * pos), int(y0 + dy * pos)
            ex, ey = int(x0 + dx * end_pos), int(y0 + dy * end_pos)
            cv2.line(img, (sx, sy), (ex, ey), color, thickness)
        pos = end_pos
        draw = not draw
