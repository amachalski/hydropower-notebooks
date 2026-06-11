"""
Hill Chart Digitization Module
==============================
Tools for digitizing universal hill charts (charakterystyki uniwersalne)
of model turbines from scanned images.

Pipeline:
    1. Gridline detection (skew-tolerant, banded line fitting)
    2. Axis calibration: pixel -> (Q11 [l/s], n11 [rpm]) via per-gridline
       anchors (piecewise linear, handles uneven scan distortion)
    3. Curve point extraction (semi-automated + vision-assisted)
    4. Surface fitting: poly3(Q11, n11) in the WPE_2.xlsm form + validation

Chart conventions (Soviet turbine atlases):
    PL (ПЛ)  = Kaplan (adjustable blade), number = design head [m]
    PO (РО)  = Francis (radial-axial),    number = design head [m]
    Suffix   = runner model number (e.g. PL10_592 -> runner ПЛ-592)

Curve families on a chart:
    eta   - efficiency contours [%] (thick solid closed curves)
    sigma - cavitation coefficient lines
    phi   - runner blade angle lines [deg] (Kaplan only)
    a0    - guide vane opening lines [mm]
"""

import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field


# ============================================================
# GRIDLINE DETECTION
# ============================================================

def load_ink(path, threshold: float = 0.55) -> np.ndarray:
    """Load scan as boolean ink mask (True = dark pixel)."""
    from PIL import Image
    img = np.asarray(Image.open(path).convert("L"), dtype=float) / 255.0
    return img < threshold


def _find_peaks(frac: np.ndarray, min_frac: float, min_gap: int) -> list[float]:
    """Groups of above-threshold positions merged within min_gap -> centroids."""
    idx = np.where(frac > min_frac)[0]
    if len(idx) == 0:
        return []
    groups = [[idx[0]]]
    for i in idx[1:]:
        if i - groups[-1][-1] <= min_gap:
            groups[-1].append(i)
        else:
            groups.append([i])
    return [float(np.average(g, weights=frac[g])) for g in groups]


def find_lines_banded(
    ink: np.ndarray,
    axis: int,
    n_bands: int = 8,
    min_frac: float = 0.45,
    min_gap: int = 5,
) -> list[tuple[float, float]]:
    """Skew-tolerant straight-line detection.

    Splits the image into n_bands along the line direction, finds ink-fraction
    peaks per band, chains peaks across bands, fits pos = a + b*t per line.

    Args:
        ink: boolean ink mask
        axis: 0 -> vertical lines, 1 -> horizontal lines
        n_bands: number of bands along the line
        min_frac: min ink fraction within a band to count as line candidate
        min_gap: merge peaks closer than this [px]

    Returns:
        List of (a, b): line position = a + b * t, where t is the coordinate
        along the line (x for horizontal, y for vertical). Sorted by a.
    """
    H, W = ink.shape
    length = W if axis == 1 else H
    bands = np.array_split(np.arange(length), n_bands)
    hits = []
    for band in bands:
        sub = ink[:, band] if axis == 1 else ink[band, :]
        frac = sub.mean(axis=1) if axis == 1 else sub.mean(axis=0)
        for p in _find_peaks(frac, min_frac, min_gap):
            hits.append((float(band.mean()), p))
    hits.sort(key=lambda h: (h[1], h[0]))
    lines: list[list[tuple[float, float]]] = []
    for t, p in hits:
        for ln in lines:
            t0, p0 = ln[-1]
            if abs(p - p0) < 8 and t != t0:
                ln.append((t, p))
                break
        else:
            lines.append([(t, p)])
    out = []
    for ln in lines:
        if len(ln) < max(3, n_bands // 2):
            continue
        ts = np.array([h[0] for h in ln])
        ps = np.array([h[1] for h in ln])
        b, a = np.polyfit(ts, ps, 1)
        out.append((float(a), float(b)))
    out.sort(key=lambda ab: ab[0])
    return out


def fill_gaps(lines: list[tuple[float, float]], extent: float) -> list[tuple[float, float]]:
    """Insert interpolated lines where spacing is a multiple of the median
    (gridlines hidden under dense ink are often missed by detection)."""
    if len(lines) < 3:
        return list(lines)
    pos = [a + b * extent / 2 for a, b in lines]
    sp = np.diff(pos)
    med = float(np.median(sp))
    out = list(lines)
    for i, s in enumerate(sp):
        n_missing = int(round(s / med)) - 1
        for k in range(1, n_missing + 1):
            f = k / (n_missing + 1)
            a = lines[i][0] + f * (lines[i + 1][0] - lines[i][0])
            b = lines[i][1] + f * (lines[i + 1][1] - lines[i][1])
            out.append((a, b))
    out.sort(key=lambda ab: ab[0])
    return out


# ============================================================
# CALIBRATION
# ============================================================

@dataclass
class ChartCalibration:
    """Pixel <-> data mapping for one scanned hill chart.

    Built from detected gridlines + user-assigned tick values. Uses
    piecewise-linear interpolation over gridline anchors, evaluated at the
    point's own pixel position, so uneven spacing AND skew are handled.

    Attributes:
        vlines: (a, b) per vertical gridline: x_px = a + b * y_px
        hlines: (a, b) per horizontal gridline: y_px = a + b * x_px
        v_values: Q11 value [l/s] per vertical gridline (same order)
        h_values: n11 value [rpm] per horizontal gridline (same order)
    """
    vlines: list[tuple[float, float]]
    hlines: list[tuple[float, float]]
    v_values: list[float]
    h_values: list[float]
    meta: dict = field(default_factory=dict)

    def px_to_data(self, x_px, y_px):
        """Convert pixel coordinates to (Q11 [l/s], n11 [rpm])."""
        x_px = np.asarray(x_px, dtype=float)
        y_px = np.asarray(y_px, dtype=float)
        # gridline positions evaluated at this point's row/column (skew-aware)
        vx = np.array([[a + b * y for (a, b) in self.vlines] for y in np.atleast_1d(y_px)])
        hy = np.array([[a + b * x for (a, b) in self.hlines] for x in np.atleast_1d(x_px)])
        Q = np.array([np.interp(x, vxr, self.v_values) for x, vxr in zip(np.atleast_1d(x_px), vx)])
        n = np.array([np.interp(y, hyr, self.h_values) for y, hyr in zip(np.atleast_1d(y_px), hy)])
        if np.isscalar(x_px) or x_px.ndim == 0:
            return float(Q[0]), float(n[0])
        return Q, n

    def data_to_px(self, Q, n):
        """Convert (Q11, n11) to approximate pixel coordinates (for overlays)."""
        Q = np.atleast_1d(np.asarray(Q, dtype=float))
        n = np.atleast_1d(np.asarray(n, dtype=float))
        # first pass: ignore skew (b=0), then refine once
        vx0 = np.array([a for a, _ in self.vlines])
        hy0 = np.array([a for a, _ in self.hlines])
        x = np.interp(Q, self.v_values, vx0)
        y = np.interp(n, self.h_values[::-1], hy0[::-1]) if self.h_values[0] > self.h_values[-1] \
            else np.interp(n, self.h_values, hy0)
        for _ in range(2):
            vx = np.array([[a + b * yi for (a, b) in self.vlines] for yi in y])
            hy = np.array([[a + b * xi for (a, b) in self.hlines] for xi in x])
            x = np.array([np.interp(q, self.v_values, vxr) for q, vxr in zip(Q, vx)])
            hv = np.array(self.h_values)
            if hv[0] > hv[-1]:
                y = np.array([np.interp(ni, hv[::-1], hyr[::-1]) for ni, hyr in zip(n, hy)])
            else:
                y = np.array([np.interp(ni, hv, hyr) for ni, hyr in zip(n, hy)])
        if len(x) == 1:
            return float(x[0]), float(y[0])
        return x, y

    def save(self, path):
        data = dict(vlines=self.vlines, hlines=self.hlines,
                    v_values=self.v_values, h_values=self.h_values, meta=self.meta)
        Path(path).write_text(json.dumps(data, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(vlines=[tuple(v) for v in d["vlines"]],
                   hlines=[tuple(v) for v in d["hlines"]],
                   v_values=d["v_values"], h_values=d["h_values"],
                   meta=d.get("meta", {}))


# ============================================================
# REFERENCE DATA (TurbineSelection.pdf, digitization ~2021)
# ============================================================
# Ground truth for validating scan digitization: poly3 surfaces fitted to the
# original manual (WebPlotDigitizer-era) digitization. eta in %, Q11 in l/s,
# n11 in rpm. Term order matches POLY3_TERMS below.

REFERENCE_POLY3 = {
    "PL10_592": [-124.481705538762, 0.154204842002, 2.888381751801,
                 -0.000061659707, -0.012579893826, -0.001559640356,
                 0.000000002398, 0.000014043245, 0.000000530328,
                 0.000004926336, -0.000000001599],
    "PL50_642": [11.294548545229, 0.047052854852, 1.550867828954,
                 -0.000037633657, -0.010583730750, -0.000408638896,
                 0.000000004608, 0.000015075668, 0.000000207366,
                 0.000003388652, -0.000000001381],
}

REFERENCE_INFO = {
    "PL10_592": dict(Q_opt=1113, n_opt=156, eta_opt=0.89, nsN=591,
                     Q_range=(575, 2592), n_range=(120, 237)),
    "PL50_642": dict(Q_opt=827, n_opt=107, eta_opt=0.91, nsN=642,
                     Q_range=(292, 1988), n_range=(74, 156)),
}


# ============================================================
# SURFACE FIT (poly3, WPE_2.xlsm form)
# ============================================================

POLY3_TERMS = [
    "1", "Q", "n", "Q^2", "n^2", "Q*n", "Q^3", "n^3", "Q^2*n", "Q*n^2", "Q^2*n^2",
]


def poly3_design_matrix(Q, n):
    """Design matrix with the 11 terms of the WPE_2.xlsm poly3 surface."""
    Q = np.asarray(Q, dtype=float)
    n = np.asarray(n, dtype=float)
    return np.column_stack([
        np.ones_like(Q), Q, n, Q**2, n**2, Q*n, Q**3, n**3, Q**2*n, Q*n**2, Q**2*n**2,
    ])


def fit_poly3(Q, n, eta):
    """Least-squares fit of the poly3 surface. Returns coefficient vector (11,)."""
    A = poly3_design_matrix(Q, n)
    coef, *_ = np.linalg.lstsq(A, np.asarray(eta, dtype=float), rcond=None)
    return coef


def eval_poly3(coef, Q, n):
    """Evaluate poly3 surface at (Q, n)."""
    return poly3_design_matrix(Q, n) @ np.asarray(coef, dtype=float)


def poly3_optimum(coef, Q_range, n_range, n_grid: int = 600):
    """Locate surface maximum on a dense grid within the data range."""
    Qd = np.linspace(*Q_range, n_grid)
    nd = np.linspace(*n_range, n_grid)
    QQ, NN = np.meshgrid(Qd, nd)
    EE = eval_poly3(coef, QQ.ravel(), NN.ravel()).reshape(QQ.shape)
    j = np.unravel_index(np.argmax(EE), EE.shape)
    return float(QQ[j]), float(NN[j]), float(EE[j])
