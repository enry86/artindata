"""Space-scene helpers: a lit sphere with faint continents, and a star field.

All images are H x W x 3 float arrays in 0..1, in the same pixel space as
Canvas (origin top-left). Decoration only: nothing here encodes data.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from matplotlib.colors import to_rgb
from scipy.ndimage import gaussian_filter, map_coordinates

from . import effects as fx
from .fonts import pt

_LAND = {}


def land_mask(geojson_path, size=(3600, 1800)):
    """Land as an equirectangular raster (1 = land) from Natural Earth polygons."""
    key = str(geojson_path)
    if key not in _LAND:
        W, H = size
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        for f in json.load(open(geojson_path))["features"]:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for poly in polys:
                for k, ring in enumerate(poly):
                    pts = [((lo + 180) / 360 * W, (90 - la) / 180 * H) for lo, la in ring]
                    d.polygon(pts, fill=255 if k == 0 else 0)
        _LAND[key] = gaussian_filter(np.asarray(im, float) / 255, 1.2)
    return _LAND[key]


def paint_sphere(img, cx, cy, R, lat0, lon0, mask=None, dark="#06050B", light="#100D1F",
                 land="#241C42", rim="#2A2144", rim_strength=0.55, land_strength=0.55,
                 sun=(-0.30, 0.40, 0.85)):
    """An opaque shaded ball centred at (cx, cy) px, seen from (lat0, lon0) degrees.

    With `mask` (see `land_mask`) the continents are lifted a touch above the sea.
    `sun` is the light direction (right, up, towards the viewer)."""
    H, W, _ = img.shape
    x0, x1 = max(int(cx - R) - 2, 0), min(int(cx + R) + 3, W)
    y0, y1 = max(int(cy - R) - 2, 0), min(int(cy + R) + 3, H)
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(float)
    dx, dy = (xx - cx) / R, -(yy - cy) / R
    rho2 = dx ** 2 + dy ** 2
    z = np.sqrt(np.clip(1 - rho2, 0, 1))
    lam = np.clip(sun[0] * dx + sun[1] * dy + sun[2] * z, 0, 1)
    body = np.array(to_rgb(dark)) + np.array(to_rgb(light)) * (lam ** 1.8)[..., None]
    if mask is not None:
        p0, l0 = np.radians(lat0), np.radians(lon0)
        lat = np.arcsin(np.clip(dy * np.cos(p0) + z * np.sin(p0), -1, 1))
        lon = l0 + np.arctan2(dx, z * np.cos(p0) - dy * np.sin(p0))
        col = (np.degrees(lon) + 180) % 360 / 360 * (mask.shape[1] - 1)
        row = (90 - np.degrees(lat)) / 180 * (mask.shape[0] - 1)
        m = map_coordinates(mask, [row, col], order=1, mode="wrap") * (rho2 < 1)
        body = body + np.array(to_rgb(land)) * ((0.35 + 0.65 * lam ** 1.4) * m * land_strength)[..., None]
    body = body + (np.clip((rho2 - 0.86) / 0.14, 0, 1) ** 2)[..., None] * np.array(to_rgb(rim)) * rim_strength
    a = np.clip((1 - np.sqrt(rho2)) * R, 0, 1)[..., None]            # 1px antialias
    out = img.copy()
    out[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - a) + np.clip(body, 0, 1) * a
    return out


def paint_stars(c, img, seed=11, n=420, dpi=100):
    """A faint field of stars behind everything."""
    rng = np.random.default_rng(seed)
    x, y = rng.uniform(0, c.W, n), rng.uniform(0, c.H, n)
    b = np.clip(rng.lognormal(-1.4, 0.7, n), 0.05, 1.0)
    tint = np.array(to_rgb("#BFC8F0")) * (1 - rng.uniform(0, 1, n))[:, None] \
        + np.array(to_rgb("#FFE6C8")) * rng.uniform(0, 1, n)[:, None]
    tint = np.clip(tint / np.maximum(tint.max(axis=1, keepdims=True), 1e-6), 0, 1)

    def draw(ax):
        ax.scatter(x, y, s=pt(1.1 + 1.6 * b, dpi) ** 2, c=np.column_stack([tint, 0.15 + 0.6 * b]), lw=0)
    lay = fx.layer(c.W, c.H, dpi, draw)
    img = fx.over(img, lay)
    return fx.glow(img, lay * np.array([1, 1, 1, 0.8]), 2.5, 0.8)
