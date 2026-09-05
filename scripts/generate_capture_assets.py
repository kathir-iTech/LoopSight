#!/usr/bin/env python
"""Generate printable checkerboard (A4) and one-page capture sheet PDFs for LoopSight water data capture."""
import cv2
import numpy as np
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
(ROOT / "data" / "self_captured").mkdir(exist_ok=True)
for sub in ["clear", "turbid", "borderline"]:
    (ROOT / "data" / "self_captured" / sub).mkdir(exist_ok=True)

# Colors
DEEP = HexColor("#0a1628")
ACCENT = HexColor("#38bdf8")
MUTED = HexColor("#8aa0c0")
WARN = HexColor("#f59e0b")

def make_checkerboard_image(size_px=2200, squares=8):
    """High-contrast checkerboard for printing."""
    img = np.full((size_px, size_px, 3), 255, dtype=np.uint8)
    sq = size_px // squares
    for r in range(squares):
        for c in range(squares):
            if (r + c) % 2 == 0:
                x0, y0 = c*sq, r*sq
                x1, y1 = (c+1)*sq, (r+1)*sq
                cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 0), -1)
    # Add thin outer border for cutting
    cv2.rectangle(img, (0,0), (size_px-1,size_px-1), (0,0,0), thickness=8)
    return img

def generate_checkerboard_pdf():
    out = DATA_DIR / "checkerboard_A4.pdf"
    # Also save PNG for quick preview
    png_out = DATA_DIR / "checkerboard_A4.png"
    board = make_checkerboard_image(size_px=2200, squares=8)
    cv2.imwrite(str(png_out), board)
    print(f"Saved checkerboard PNG: {png_out} ({board.shape})")

    # Create PDF A4
    c = canvas.Canvas(str(out), pagesize=A4)
    w, h = A4
    # Background
    c.setFillColor(HexColor("#ffffff"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    # Title
    c.setFillColor(DEEP)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w/2, h - 18*mm, "LoopSight — Checkerboard for Water Turbidity Screening")
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawCentredString(w/2, h - 22*mm, "Print at 100% — Do NOT use Fit to page / Shrink to fit — A4, 300 dpi recommended — Black should be solid, white clean")
    # Instructions box
    box_y = h - 31*mm
    c.setStrokeColor(ACCENT)
    c.setFillColor(HexColor("#f0f9ff"))
    c.roundRect(12*mm, box_y - 6*mm, w - 24*mm, 9*mm, 2*mm, fill=1, stroke=1)
    c.setFillColor(DEEP)
    c.setFont("Helvetica", 6.5)
    c.drawString(14*mm, box_y + 1*mm, "HOW TO USE:  1) Print this page.  2) Place behind/under a clear glass.  3) Photograph the pattern THROUGH water — see capture sheet for two lightings per sample.")
    c.setFont("Helvetica-Oblique", 6)
    c.setFillColor(HexColor("#64748b"))
    c.drawString(14*mm, box_y - 3*mm, "Tip: Tape to cardboard for stiffness. Keep glass ~2–3 cm in front of paper. Frame tightly on glass + pattern, no faces needed.")
    # Checkerboard image centered
    # Convert cv2 BGR to RGB for reportlab
    board_rgb = cv2.cvtColor(board, cv2.COLOR_BGR2RGB)
    # Save to buffer
    _, buf = cv2.imencode('.png', cv2.cvtColor(board_rgb, cv2.COLOR_RGB2BGR))
    # Actually board is already BGR-> we need RGB buffer for reportlab; use PIL
    from PIL import Image
    pil_img = Image.fromarray(board_rgb)
    img_buffer = io.BytesIO()
    pil_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    img_reader = ImageReader(img_buffer)
    # Place image: 170mm square centered
    img_size = 170*mm
    img_x = (w - img_size)/2
    img_y = (h - img_size)/2 - 6*mm
    c.drawImage(img_reader, img_x, img_y, width=img_size, height=img_size, preserveAspectRatio=True)
    # Footer details
    c.setFont("Helvetica", 6)
    c.setFillColor(MUTED)
    c.drawCentredString(w/2, 12*mm, "Inner corners: 7×7 (8×8 squares) — detectable via cv2.findChessboardCorners 7×7 / 7×5 / 6×4. Outer border for cutting. If printer lightens blacks, increase contrast in print dialog.")
    c.setFont("Helvetica", 5.5)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawCentredString(w/2, 9*mm, "LoopSight  |  water_turbidity_v1  |  Secchi-disk principle: pattern visibility through water is the signal  |  Generated 2026-09-04")
    # Cut marks
    c.setStrokeColor(HexColor("#cbd5e1"))
    c.setLineWidth(0.3)
    for (x, y) in [(img_x, img_y + img_size), (img_x + img_size, img_y + img_size), (img_x, img_y), (img_x + img_size, img_y)]:
        c.line(x - 3*mm, y, x - 0.5*mm, y)
        c.line(x, y - 3*mm, x, y - 0.5*mm)
    c.showPage()
    c.save()
    print(f"Saved checkerboard PDF: {out}")

def generate_capture_sheet_pdf():
    out = DATA_DIR / "capture_sheet.pdf"
    md_out = DATA_DIR / "capture_sheet.md"
    c = canvas.Canvas(str(out), pagesize=A4)
    w, h = A4
    # Background
    c.setFillColor(HexColor("#ffffff"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    # Header
    c.setFillColor(DEEP)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(w/2, h - 14*mm, "LoopSight — Water Capture Sheet  (10–15 borderline pairs)")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(WARN)
    c.drawCentredString(w/2, h - 17.5*mm, "Goal: settle conditional_benefit with REAL photos — only borderline samples where YOU hesitate. Two lightings per sample. Stop after 10–15 good pairs.")
    # Safety banner copy (as in UI)
    banner_y = h - 25*mm
    c.setFillColor(HexColor("#fff7ed"))
    c.setStrokeColor(WARN)
    c.roundRect(10*mm, banner_y - 5*mm, w - 20*mm, 8*mm, 2*mm, fill=1, stroke=1)
    c.setFillColor(HexColor("#9a3412"))
    c.setFont("Helvetica-Bold", 6)
    c.drawString(13*mm, banner_y + 1*mm, "Safety: Turbidity is NOT potability. Clear-looking water can still carry arsenic/fluoride/nitrate. This sheet is for screening research only.")
    c.setFont("Helvetica", 6)
    c.drawString(13*mm, banner_y - 2.5*mm, "Flag visibly cloudy water for follow-up. Do NOT label any sample as safe to drink — visible turbidity: do not drink without treatment.")
    # Instructions
    inst_y = h - 34*mm
    c.setFillColor(DEEP)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(10*mm, inst_y, "How to shoot (same for every sample):")
    c.setFont("Helvetica", 6)
    instructions = [
        "1. Place checkerboard behind clear glass, 2–3 cm gap. Glass on white paper, no faces in frame. Frame tightly on glass+pattern.",
        "2. Pour sample. For borderline: water where YOU hesitate at a glance (hazy? settling? could be glass?). Skip obvious clear/muddy — they prove nothing.",
        "3. Photo A — ambient light (room light, no flash). Photo B — backlight (hold phone flash/torch behind glass) OR phone flash from front. Keep distance/angle identical.",
        "4. BEFORE running app: write hesitation note + self-guess (clear / probably-fine / concerning). After app, compare — did its uncertainty match your reason?",
        "5. Save as: sample03_ambient.jpg + sample03_backlight.jpg (or _flash). Keep pairs together. No editing/cropping after.",
    ]
    for i, line in enumerate(instructions):
        c.drawString(12*mm, inst_y - 4 - i*3.2*mm, line)
    # Table header
    table_top = inst_y - 23*mm
    c.setFillColor(DEEP)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(10*mm, table_top, "Log — fill as you shoot (pen, one line each):")
    # Column definitions (x positions)
    # ID | Hesitation note (why unsure) | Self-guess BEFORE app | Ambient ✓ | Backlight/Flash ✓ | App UNCERTAIN? | App vis.
    cols = [
        ("ID", 10*mm, 12*mm),
        ("Hesitation — why you hesitated (one line)", 22*mm, 58*mm),
        ("Self-guess BEFORE app", 80*mm, 22*mm),
        ("A: amb", 102*mm, 12*mm),
        ("B: back/flash", 114*mm, 16*mm),
        ("App UNCERTAIN?", 130*mm, 18*mm),
        ("App vis.", 148*mm, 12*mm),
        ("Match?", 160*mm, 12*mm),
        ("Notes", 172*mm, 28*mm),
    ]
    # Header background
    header_y = table_top - 6*mm
    c.setFillColor(DEEP)
    c.roundRect(10*mm, header_y - 1*mm, w - 20*mm, 5*mm, 1*mm, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 5)
    for name, x, wid in cols:
        c.drawString(x + 1*mm, header_y + 1*mm, name)
    # Rows
    row_h = 7.2*mm
    start_y = header_y - row_h
    c.setFont("Helvetica", 5.5)
    for row in range(15):
        y = start_y - row*row_h
        # Alternating row bg
        if row % 2 == 0:
            c.setFillColor(HexColor("#f8fafc"))
            c.rect(10*mm, y - 0.5*mm, w - 20*mm, row_h, fill=1, stroke=0)
        c.setStrokeColor(HexColor("#e2e8f0"))
        c.setLineWidth(0.25)
        c.rect(10*mm, y - 0.5*mm, w - 20*mm, row_h, fill=0, stroke=1)
        # Vertical lines
        for _, x, _ in cols[1:]:
            c.line(x, y - 0.5*mm, x, y + row_h - 0.5*mm)
        # Row number
        c.setFillColor(HexColor("#334155"))
        c.drawCentredString(16*mm, y + 2.5*mm, f"{row+1:02d}")
        # Self-guess hint
        if row == 0:
            c.setFont("Helvetica-Oblique", 4)
            c.setFillColor(HexColor("#94a3b8"))
            c.drawString(80.5*mm, y + 2.5*mm, "clear / prob-fine / concerning")
            c.setFont("Helvetica", 5.5)
            c.setFillColor(HexColor("#334155"))
        # Checkbox hint for A/B
        # leave empty for pen check
    # Footer legend
    legend_y = start_y - 15*row_h - 4*mm
    c.setFillColor(HexColor("#f1f5f9"))
    c.setStrokeColor(HexColor("#e2e8f0"))
    c.roundRect(10*mm, legend_y - 8*mm, w - 20*mm, 10*mm, 1.5*mm, fill=1, stroke=1)
    c.setFillColor(DEEP)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(12*mm, legend_y - 1*mm, "After shooting — run (from repo root):")
    c.setFont("Helvetica", 5)
    c.setFillColor(HexColor("#334155"))
    c.drawString(12*mm, legend_y - 4*mm, "python services/inference/scripts/calibrate_thresholds.py data/self_captured   →  copy suggested thresholds if needed")
    c.drawString(12*mm, legend_y - 7*mm, "python services/inference/scripts/run_experiments.py data/self_captured --profile water_turbidity_v1   →  read conditional_benefit (on REAL borderline pairs)")
    # Interpretation
    interp_y = legend_y - 13*mm
    c.setFillColor(WARN)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(10*mm, interp_y, "How to read the answer:")
    c.setFillColor(HexColor("#334155"))
    c.setFont("Helvetica", 5)
    c.drawString(10*mm, interp_y - 3*mm, "• conditional_benefit > 0 means second look (backlight/flash) genuinely resolved cases where ambient alone was borderline — claim holds.")
    c.drawString(10*mm, interp_y - 6*mm, "• ~0 or negative on REAL borderline means mechanism didn't help — keep domain, pitch honest negative result + execution (also strong).")
    c.drawString(10*mm, interp_y - 9*mm, "• App UNCERTAIN? should line up with your hesitation note — if not, thresholds need recalibration, not a pivot.")
    c.setFont("Helvetica-Oblique", 5)
    c.setFillColor(HexColor("#64748b"))
    c.drawString(10*mm, interp_y - 12*mm, "Keep this sheet with the dataset — it's the audit trail that your \"borderline\" was a real human hesitation, not a vibe.")
    # Footer
    c.setFont("Helvetica", 5)
    c.setFillColor(MUTED)
    c.drawCentredString(w/2, 8*mm, "LoopSight  |  water_turbidity_v1  |  10–15 pairs is enough — quality over quantity  |  No faces, no addresses, MIT  |  Print this sheet, fill by hand")
    c.showPage()
    c.save()
    print(f"Saved capture sheet PDF: {out}")

    # Also save markdown version for quick viewing/editing
    md = f"""# LoopSight — Capture Sheet (10–15 borderline pairs)

**Goal:** 10–15 samples where *you* hesitate. Two lightings each. This settles `conditional_benefit`.

| ID | Hesitation — why unsure (one line) | Self-guess BEFORE app | A: ambient ✓ | B: backlight/flash ✓ | App UNCERTAIN? | App vis. | Match? | Notes |
|---|---|---|---|---|---|---|---|---|
"""
    for i in range(1, 16):
        md += f"| {i:02d} |  |  | ☐ | ☐ |  |  |  |  |\n"
    md += """
**After shooting:**
```bash
python services/inference/scripts/calibrate_thresholds.py data/self_captured
python services/inference/scripts/run_experiments.py data/self_captured --profile water_turbidity_v1
```
Read `conditional_benefit` on *real* borderline. >0 = second look helped; ~0/negative = honest negative result (also defensible).
"""
    md_out.write_text(md, encoding="utf-8")
    print(f"Saved capture sheet MD: {md_out}")

if __name__ == "__main__":
    generate_checkerboard_pdf()
    generate_capture_sheet_pdf()
