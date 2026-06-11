"""Crop a region of a scan for close inspection. Usage:
python _crop.py <image> <x0> <y0> <x1> <y1> [scale] [out]
"""
import sys
from pathlib import Path
from PIL import Image

src = Path(sys.argv[1])
x0, y0, x1, y1 = map(int, sys.argv[2:6])
scale = float(sys.argv[6]) if len(sys.argv) > 6 else 1.0
out = Path(sys.argv[7]) if len(sys.argv) > 7 else Path(r"D:\dydaktyka\2025_2026\EW\other\_crop_out.png")

img = Image.open(src)
img = img.convert("RGB") if img.mode not in ("L", "RGB") else img
crop = img.crop((x0, y0, x1, y1))
if scale != 1.0:
    crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
crop.save(out)
print(out, crop.size)
