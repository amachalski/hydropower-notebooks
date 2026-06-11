"""Extract thick solid curves (eta contours) from a hill-chart scan.

Method: EDT line-width segmentation â€” markers (EDT >= t_marker) propagated
within mask (EDT >= t_mask); thick lines (eta contours) survive, thin
families (grid, sigma, dashed phi/a0) drop out.
Usage: python _extract_eta.py <image.png> [thr] [t_marker] [t_mask]
"""
import sys
import json
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
from scipy import ndimage

src = Path(sys.argv[1])
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.72
t_marker = float(sys.argv[3]) if len(sys.argv) > 3 else 2.2
t_mask = float(sys.argv[4]) if len(sys.argv) > 4 else 1.45
outdir = Path(__file__).parent.parent / "other"

gray = np.asarray(Image.open(src).convert("L"), dtype=float) / 255.0
ink = gray < thr
H, W = ink.shape

edt = ndimage.distance_transform_edt(ink)
st8 = ndimage.generate_binary_structure(2, 2)
core = ndimage.binary_propagation(edt >= t_marker, structure=st8, mask=edt >= t_mask)
thick = ndimage.binary_dilation(core, st8, iterations=2) & ink

lab, n = ndimage.label(thick, structure=st8)
sizes = ndimage.sum_labels(np.ones_like(lab), lab, index=np.arange(1, n + 1))

keep = []
for i in np.argsort(sizes)[::-1]:
    cid = i + 1
    if sizes[i] < 250:
        break
    ys, xs = np.where(lab == cid)
    diag = float(np.hypot(xs.max() - xs.min(), ys.max() - ys.min()))
    if diag < 120:
        continue
    bbox_area = (xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
    if sizes[i] / bbox_area > 0.35:   # compact blob = text
        continue
    keep.append(dict(cid=int(cid), size=int(sizes[i]),
                     bbox=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]))

print(f"thr={thr} marker={t_marker} mask={t_mask}: {n} raw, {len(keep)} kept")
for k in keep:
    b = k["bbox"]
    print(f"  c{k['cid']}: {k['size']} px, bbox x[{b[0]}..{b[2]}] y[{b[1]}..{b[3]}]")

palette = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48),
           (145, 30, 180), (70, 240, 240), (240, 50, 230), (60, 100, 30),
           (0, 128, 128), (130, 60, 240), (170, 110, 40), (128, 0, 0),
           (0, 0, 128), (128, 128, 0), (255, 105, 180), (100, 100, 100)]
base = np.asarray(Image.open(src).convert("L"), dtype=np.uint8)
rgb = np.stack([255 - (255 - base) // 4] * 3, axis=-1)
st4 = ndimage.generate_binary_structure(2, 1)
for j, k in enumerate(keep):
    m = ndimage.binary_dilation(lab == k["cid"], st4, iterations=2)
    rgb[m] = palette[j % len(palette)]
img = Image.fromarray(rgb)
d = ImageDraw.Draw(img)
for j, k in enumerate(keep):
    b = k["bbox"]
    cx, cy = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
    d.rectangle([cx - 2, cy - 13, cx + 52, cy + 13], fill=(255, 255, 255),
                outline=palette[j % len(palette)])
    d.text((cx + 2, cy - 12), f"c{k['cid']}", fill=palette[j % len(palette)])
img.save(outdir / "_eta_overlay_full.png")
img2 = img.copy()
img2.thumbnail((1450, 1450), Image.LANCZOS)
img2.save(outdir / "_eta_overlay.png")
np.save(outdir / "_eta_labels.npy", lab)
(outdir / "_eta_keep.json").write_text(json.dumps(keep))
print("overlay: _eta_overlay.png (+full), labels: _eta_labels.npy, keep: _eta_keep.json")
