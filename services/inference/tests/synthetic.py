"""
Synthetic & physics-modeled test-image generators for LoopSight v2.

Provides deterministic image generators across all three inspection profiles:
  1. water_turbidity_v1          — Clear, turbid, borderline, specular-glare confounded,
                                   perspective-skewed, and vertically stratified settling samples.
  2. structural_crack_metrology_v1 — Intact concrete, structural fracture (0.6mm+),
                                   and soft-shadow confounded concrete surface.
  3. fdm_print_surface_v1        — Clean square, broken/gapped square, low-contrast frame,
                                   and faint-edge borderline square.
"""

from __future__ import annotations

import numpy as np
import cv2


def make_clean_square(size: int = 200, margin: int = 40) -> np.ndarray:
    """A crisp, complete, high-contrast square boundary."""
    img = np.full((size, size, 3), 40, dtype=np.uint8)
    cv2.rectangle(img, (margin, margin), (size - margin, size - margin), (220, 220, 220), thickness=3)
    return img


def make_broken_square(size: int = 200, margin: int = 40, gap: int = 25) -> np.ndarray:
    """The same square with deliberate gaps in the boundary."""
    img = np.full((size, size, 3), 40, dtype=np.uint8)
    x0, y0, x1, y1 = margin, margin, size - margin, size - margin
    for (p0, p1) in [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]:
        _dashed_line(img, p0, p1, gap=gap)
    return img


def make_low_contrast_frame(size: int = 200) -> np.ndarray:
    """Near-uniform gray frame where the system should say UNCERTAIN rather than guess."""
    base = 128
    img = np.full((size, size, 3), base, dtype=np.uint8)
    noise = np.random.default_rng(42).integers(-3, 4, size=img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return img


def make_checkerboard(size: int = 200, squares: int = 8) -> np.ndarray:
    """High-contrast checkerboard — printable on A4, stands in for the
    reference pattern behind a water sample (Secchi-disk principle)."""
    img = np.full((size, size, 3), 40, dtype=np.uint8)
    sq = size // squares
    for r in range(squares):
        for c in range(squares):
            color = (220, 220, 220) if (r + c) % 2 == 0 else (30, 30, 30)
            cv2.rectangle(img, (c * sq, r * sq), ((c + 1) * sq, (r + 1) * sq), color, -1)
    return img


def make_turbid_water(
    checkerboard: np.ndarray | None = None,
    blur_ks: int = 11,
    alpha: float = 0.6,
    beta: int = 20,
) -> np.ndarray:
    """Simulate turbidity: reduce contrast, blur, add hazy overlay."""
    if checkerboard is None:
        checkerboard = make_checkerboard()
    hazy = cv2.convertScaleAbs(checkerboard, alpha=alpha, beta=beta)
    if blur_ks % 2 == 0:
        blur_ks += 1
    blurred = cv2.GaussianBlur(hazy, (blur_ks, blur_ks), 0)
    overlay = np.full_like(blurred, 180)
    return cv2.addWeighted(blurred, 0.7, overlay, 0.3, 0)


def make_clear_water(size: int = 200, squares: int = 8) -> np.ndarray:
    """Clear water — pattern sharp and high-contrast through the glass."""
    return make_checkerboard(size, squares)


def make_borderline_water(size: int = 200, squares: int = 8) -> np.ndarray:
    """Borderline turbidity — genuinely ambiguous middle band."""
    cb = make_checkerboard(size, squares)
    return make_turbid_water(cb, blur_ks=7, alpha=0.80, beta=10)


def make_glare_confounded_water(size: int = 200, squares: int = 8) -> np.ndarray:
    """Clear water sample confounded by a localized specular glass reflection
    plus ambient veil haze. First pass is UNCERTAIN due to glare + depressed
    contrast (pattern_visibility ~0.42, glare_ratio ~0.10), while
    inpaint_specular_glare removes the reflection and restores CLAHE contrast
    to resolve PASS (pattern_visibility > 0.60)."""
    cb = make_checkerboard(size, squares)
    # Mild ambient veil across the glass so initial visibility sits in 0.38..0.48
    veiled = cv2.convertScaleAbs(cb, alpha=0.42, beta=78)
    veiled = cv2.GaussianBlur(veiled, (3, 3), 0)
    # Add localized pure-white specular highlight streak on the curved glass
    cv2.ellipse(veiled, (size // 2, size // 2), (28, 16), 25, 0, 360, (252, 252, 252), -1)
    return veiled


def make_stratified_turbid_water(size: int = 200, squares: int = 8) -> np.ndarray:
    """Settling turbid sample where the upper two-thirds appear relatively clear
    while heavy sediment has settled into the bottom third. Whole-frame average
    visibility sits in the ambiguous middle band (~0.45 -> UNCERTAIN) with high
    stratification_delta (>0.30), and analyze_vertical_stratification isolates
    the turbid bottom stratum (<0.15) to resolve FAIL."""
    cb = make_checkerboard(size, squares)
    out = cv2.convertScaleAbs(cb, alpha=0.68, beta=35)
    out = cv2.GaussianBlur(out, (3, 3), 0)
    split_y = (size * 2) // 3
    bottom_turbid = make_turbid_water(cb, blur_ks=15, alpha=0.22, beta=115)
    out[split_y:, :] = bottom_turbid[split_y:, :]
    return out


def make_backlit_recovery_pair(size: int = 200, squares: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Two-lighting capture pair of a clear water sample in a dim room:
    Frame 1 (ambient): dim, low-contrast capture that scores UNCERTAIN (~0.36).
    Frame 2 (backlight): direct illumination through the sample that restores
    sharp pattern visibility (>0.72 -> PASS)."""
    cb = make_checkerboard(size, squares)
    frame_ambient = cv2.convertScaleAbs(cb, alpha=0.45, beta=55)
    frame_ambient = cv2.GaussianBlur(frame_ambient, (5, 5), 0)
    frame_backlight = cv2.convertScaleAbs(cb, alpha=0.95, beta=5)
    return frame_ambient, frame_backlight


def make_intact_concrete(size: int = 200) -> np.ndarray:
    """Clean, intact concrete surface with natural mineral aggregate contrast."""
    rng = np.random.default_rng(101)
    yy, xx = np.mgrid[0:size, 0:size]
    # Gentle macro lighting gradient so local_contrast > 0.05 without any dark fracture filaments
    macro = (165.0 + 24.0 * np.sin(xx / 35.0) + 18.0 * np.cos(yy / 40.0)).astype(np.int16)
    grain = rng.integers(-4, 5, size=(size, size), dtype=np.int16)
    gray = np.clip(macro + grain, 0, 255).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def make_structural_crack(size: int = 200, thickness_px: int = 6) -> np.ndarray:
    """Concrete surface with a sharp, continuous structural fracture (~0.6mm at 0.1mm/px)."""
    img = make_intact_concrete(size)
    pts = np.array(
        [[25, 30], [65, 72], [95, 92], [135, 140], [175, 172]],
        dtype=np.int32,
    )
    cv2.polylines(img, [pts], isClosed=False, color=(28, 28, 28), thickness=thickness_px, lineType=cv2.LINE_AA)
    return img


def make_shadow_confounded_concrete(size: int = 200) -> np.ndarray:
    """Intact concrete surface with a localized specular glare reflection spot
    that triggers UNCERTAIN on first pass (glare_ratio >= 0.08), which
    inpaint_specular_glare / skeletonize_crack_metrology clears to PASS."""
    img = make_intact_concrete(size)
    cv2.ellipse(img, (size // 2, size // 2), (46, 30), 15, 0, 360, (250, 250, 250), -1)
    return img


def _dashed_line(
    img: np.ndarray,
    p0: tuple,
    p1: tuple,
    gap: int,
    dash: int = 15,
    thickness: int = 3,
    color=(220, 220, 220),
):
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
