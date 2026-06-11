"""Render axis strips with detected-gridline markers + indices for tick reading.
Usage: python _ticks.py <image.png>
Writes _ticks_left.png, _ticks_bottom_1.png, _ticks_bottom_2.png
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, r"D:\dydaktyka\2025_2026\EW")
from src.hillchart import load_ink, find_lines_banded, fill_gaps  # noqa: E402

src = Path(sys.argv[1])
outdir = Path(__file__).parent.parent / "other"

pil = Image.open(src).convert("L")
ink = load_ink(src)
H, W = ink.shape

vlines = fill_gaps(find_lines_banded(ink, axis=0), H)
hlines = fill_gaps(find_lines_banded(ink, axis=1), W)
print(f"{len(vlines)} vertical, {len(hlines)} horizontal gridlines (after gap fill)")

# left strip: x 0..230, mark each hline at its y(x=180)
strip = pil.crop((0, 0, 230, H)).convert("RGB")
d = ImageDraw.Draw(strip)
for i, (a, b) in enumerate(hlines):
    y = a + b * 180
    d.line([(150, y), (230, y)], fill=(255, 0, 0), width=3)
    d.text((155, y - 16), f"h{i}", fill=(255, 0, 0))
strip.save(outdir / "_ticks_left.png")

# bottom strip: y H-150..H, mark each vline; split into 2 halves
for half in (0, 1):
    x0, x1 = (0, W // 2 + 60) if half == 0 else (W // 2 - 60, W)
    strip = pil.crop((x0, H - 150, x1, H)).convert("RGB")
    d = ImageDraw.Draw(strip)
    for i, (a, b) in enumerate(vlines):
        x = a + b * (H - 80)
        if x0 <= x <= x1:
            d.line([(x - x0, 0), (x - x0, 60)], fill=(255, 0, 0), width=3)
            d.text((x - x0 + 4, 62), f"v{i}", fill=(255, 0, 0))
    strip.save(outdir / f"_ticks_bottom_{half + 1}.png")
print("written: _ticks_left.png, _ticks_bottom_1.png, _ticks_bottom_2.png")
