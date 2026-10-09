"""The cracking Earth: every earthquake of magnitude 4.5+ in 2025, as a ray of light.

The globe is seen from 10 degrees south, 100 degrees east (chosen by eye among
six candidates; 79% of the quakes face us and the M8.8 stands out on the
rim). Each quake is a ray leaving the surface along its normal, from its
epicentre outwards: ray length is magnitude, colour is depth. Rays on the far
side rise past the rim, so the whole year is visible around the orb. Where
quakes lie close together on the near side, thin glowing lines join them.

    python fetch_data.py    # once, to refresh data/
    python quakes.py        # writes output/*.png
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.patheffects as pe
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.spatial import cKDTree
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.patches import Rectangle

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
from dataviz_style import Canvas, THEMES, font, pt, DPI  # noqa: E402
from dataviz_style import effects as fx  # noqa: E402

THEME = THEMES["ember"]
SOURCE = "Data: USGS Earthquake Catalog, M4.5+, 2025 · public domain"
VIEW = (-10.0, 100.0)          # (latitude, longitude) of the point facing us, in degrees
MAG0 = 4.4                     # ray length is zero here (below every quake)
DEPTH_MAX = 700.0

# depth: pale gold at the surface, through orange, to deep red at 700 km
CMAP = LinearSegmentedColormap.from_list(
    "depth", ["#FFE9C4", "#FFB45E", "#FF7A33", "#F2402B", "#D4142C", "#B00A30"])

CRACK = "#FF4326"      # the light leaking out of the surface (decoration: depth stays on the rays)
LINK_KM = 400          # near-side epicentres closer than this are joined by a crack
EARTH_KM = 6371.0

# ---------------------------------------------------------------- data
q = pd.read_csv(HERE / "data" / "quakes_2025.csv")
LAT, LON = np.radians(q.latitude.values), np.radians(q.longitude.values)
MAG = q.mag.values
assert MAG.max() == 8.8 and "Kamchatka" in q.place[int(np.argmax(MAG))]


def depth_color(depth):
    """Depth to colour on a square-root scale: most quakes are shallow, so the
    first 100 km get as much of the scale as the rest of the way down."""
    return CMAP(np.sqrt(np.clip(depth, 0, DEPTH_MAX) / DEPTH_MAX))


def halo(px, color=THEME.bg, alpha=0.85):
    return [pe.Stroke(linewidth=pt(px, DPI), foreground=color, alpha=alpha), pe.Normal()]


def view_z(lat0, lon0):
    """How squarely each quake faces a viewer above (lat0, lon0): >0 is the near side."""
    p0, l0 = np.radians(lat0), np.radians(lon0)
    return np.sin(p0) * np.sin(LAT) + np.cos(p0) * np.cos(LAT) * np.cos(LON - l0)


class Orb:
    """Sphere of radius R px at (cx, cy); a ray of `tall` px per magnitude unit."""

    def __init__(self, cx, cy, R, tall, lat0=VIEW[0], lon0=VIEW[1]):
        self.cx, self.cy, self.R, self.tall = cx, cy, R, tall
        self.lat0, self.lon0 = lat0, lon0
        p0, l0 = np.radians(lat0), np.radians(lon0)
        self.x = np.cos(LAT) * np.sin(LON - l0)
        self.y = np.cos(p0) * np.sin(LAT) - np.sin(p0) * np.cos(LAT) * np.cos(LON - l0)
        self.z = np.sin(p0) * np.sin(LAT) + np.cos(p0) * np.cos(LAT) * np.cos(LON - l0)
        self.length = tall * (MAG - MAG0)
        s = 1 + self.length / R
        self.bx, self.by = cx + R * self.x, cy - R * self.y            # foot, on the surface
        self.tx, self.ty = cx + R * s * self.x, cy - R * s * self.y    # tip
        self.rgba = depth_color(q.depth.values)
        # a back-side ray shows only if its tip clears the rim
        clears = np.hypot(self.tx - cx, self.ty - cy) > R
        self.front = self.z > 0
        self.show = self.front | clears
        self.order = np.argsort(self.z)                                # far to near

    def pick(self, front):
        idx = self.order[self.show[self.order] & (self.front[self.order] == front)]
        return idx

    def rays(self, ax, idx, lw_px, boost=1.0, steps=5, fade=(0.10, 1.0)):
        t = np.linspace(0, 1, steps + 1)
        for a, b in zip(t[:-1], t[1:]):
            x0 = self.bx[idx] + (self.tx[idx] - self.bx[idx]) * a
            y0 = self.by[idx] + (self.ty[idx] - self.by[idx]) * a
            x1 = self.bx[idx] + (self.tx[idx] - self.bx[idx]) * b
            y1 = self.by[idx] + (self.ty[idx] - self.by[idx]) * b
            segs = np.stack([np.column_stack([x0, y0]), np.column_stack([x1, y1])], 1)
            col = self.rgba[idx].copy()
            col[:, 3] = np.clip((fade[0] + (fade[1] - fade[0]) * ((a + b) / 2) ** 1.4) * boost, 0, 1)
            ax.add_collection(LineCollection(segs, colors=col, linewidths=pt(lw_px, DPI),
                                             capstyle="round", zorder=4))

    def tips(self, ax, idx, scale=1.0):
        r = (1.0 + 0.55 * (MAG[idx] - 4.5) ** 1.5) * scale
        ax.scatter(self.tx[idx], self.ty[idx], s=pt(2 * r, DPI) ** 2, c=self.rgba[idx], lw=0, zorder=5)

    def feet(self, ax, idx, scale=1.0, alpha=0.5):
        col = self.rgba[idx].copy()
        col[:, 3] = alpha
        ax.scatter(self.bx[idx], self.by[idx], s=pt(2 * 1.3 * scale, DPI) ** 2, c=col, lw=0, zorder=3)

    def sphere(self, img):
        """An opaque dark ball with a faint lit rim, painted over the far rays."""
        H, W, _ = img.shape
        yy, xx = np.mgrid[0:H, 0:W].astype(float)
        dx, dy = (xx - self.cx) / self.R, (yy - self.cy) / self.R
        rho2 = dx ** 2 + dy ** 2
        nz = np.sqrt(np.clip(1 - rho2, 0, 1))
        lam = np.clip(-0.30 * dx - 0.40 * dy + 0.85 * nz, 0, 1)
        body = np.array(to_rgb("#06050B")) + np.array(to_rgb("#100D1F")) * (lam ** 1.8)[..., None]
        rim = (np.clip((rho2 - 0.86) / 0.14, 0, 1) ** 2)[..., None] * np.array(to_rgb("#2A2144")) * 0.55
        a = np.clip((1 - np.sqrt(rho2)) * self.R, 0, 1)[..., None]
        return img * (1 - a) + np.clip(body + rim, 0, 1) * a


_LAND = None


def land_mask():
    """Land as an equirectangular raster (1 = land), from Natural Earth 110m."""
    global _LAND
    if _LAND is None:
        W, H = 3600, 1800
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        gj = json.load(open(HERE / "data" / "ne_110m_land.geojson"))
        for f in gj["features"]:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for poly in polys:
                for k, ring in enumerate(poly):
                    pts = [((lo + 180) / 360 * W, (90 - la) / 180 * H) for lo, la in ring]
                    d.polygon(pts, fill=255 if k == 0 else 0)
        _LAND = gaussian_filter(np.asarray(im, float) / 255, 1.2)
    return _LAND


def paint_land(o, img, strength=1.0):
    """Continents as a faint filled tone on the ball, shaded like the ball."""
    H, W, _ = img.shape
    x0, x1 = int(o.cx - o.R) - 1, int(o.cx + o.R) + 2
    y0, y1 = int(o.cy - o.R) - 1, int(o.cy + o.R) + 2
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(float)
    dx, dy = (xx - o.cx) / o.R, -(yy - o.cy) / o.R
    rho2 = dx ** 2 + dy ** 2
    inside = rho2 < 1
    z = np.sqrt(np.clip(1 - rho2, 0, 1))
    p0, l0 = np.radians(o.lat0), np.radians(o.lon0)
    lat = np.arcsin(np.clip(dy * np.cos(p0) + z * np.sin(p0), -1, 1))
    lon = l0 + np.arctan2(dx, z * np.cos(p0) - dy * np.sin(p0))
    mask = land_mask()
    col = (np.degrees(lon) + 180) % 360 / 360 * (mask.shape[1] - 1)
    row = (90 - np.degrees(lat)) / 180 * (mask.shape[0] - 1)
    m = map_coordinates(mask, [row, col], order=1, mode="wrap") * inside
    lam = np.clip(-0.30 * dx + 0.40 * dy + 0.85 * z, 0, 1)
    ocean = np.array(to_rgb("#06050B")) + np.array(to_rgb("#100D1F")) * (lam ** 1.8)[..., None]
    tone = ocean + np.array(to_rgb("#241C42")) * (0.35 + 0.65 * lam ** 1.4)[..., None] * 0.55   # a touch lighter than the sea
    a = (m * strength)[..., None]
    out = img.copy()
    out[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - a) + tone * a
    return out


def paint_stars(c, img, seed=11, n=420):
    """A faint field of stars behind everything. Decoration, nothing more."""
    rng = np.random.default_rng(seed)
    x, y = rng.uniform(0, c.W, n), rng.uniform(0, c.H, n)
    b = np.clip(rng.lognormal(-1.4, 0.7, n), 0.05, 1.0)
    tint = np.array(to_rgb("#BFC8F0")) * (1 - rng.uniform(0, 1, n))[:, None] \
        + np.array(to_rgb("#FFE6C8")) * rng.uniform(0, 1, n)[:, None]
    tint = np.clip(tint / np.maximum(tint.max(axis=1, keepdims=True), 1e-6), 0, 1)

    def draw(ax):
        ax.scatter(x, y, s=pt(1.1 + 1.6 * b, DPI) ** 2, c=np.column_stack([tint, 0.15 + 0.6 * b]), lw=0)
    lay = fx.layer(c.W, c.H, DPI, draw)
    img = fx.over(img, lay)
    return fx.glow(img, lay * np.array([1, 1, 1, 0.8]), 2.5, 0.8)


def foot_halos(o, img, idx, c):
    """Light leaking where a ray leaves the surface: the 'crack'."""
    def draw(ax):
        r = 1.5 + 1.7 * (MAG[idx] - 4.5)
        col = np.tile(to_rgb(CRACK), (len(idx), 1))
        ax.scatter(o.bx[idx], o.by[idx], s=pt(2 * r, DPI) ** 2, c=np.column_stack([col, np.full(len(idx), 0.95)]), lw=0)
    lay = fx.layer(c.W, c.H, DPI, draw)
    img = fx.glow(img, lay, 2.6, 1.0)
    return fx.glow(img, lay, 8, 1.0)


def link_segments(o, idx, km=LINK_KM, k=5, z_min=0.06):
    """Pairs of near-side epicentres closer than `km` (each to its k nearest),
    as px segments plus how close they are (0 = touching, 1 = at the limit)."""
    idx = idx[o.z[idx] > z_min]
    pts = np.column_stack([np.cos(LAT[idx]) * np.cos(LON[idx]), np.cos(LAT[idx]) * np.sin(LON[idx]), np.sin(LAT[idx])])
    r = km / EARTH_KM
    d, nb = cKDTree(pts).query(pts, k=k + 1, distance_upper_bound=r)
    pairs = {}
    for i in range(len(idx)):
        for dist, j in zip(d[i, 1:], nb[i, 1:]):
            if np.isfinite(dist):
                pairs[(min(i, j), max(i, j))] = dist / r
    ij = np.array(list(pairs))
    t = np.array(list(pairs.values()))
    a, b = idx[ij[:, 0]], idx[ij[:, 1]]
    segs = np.stack([np.column_stack([o.bx[a], o.by[a]]), np.column_stack([o.bx[b], o.by[b]])], 1)
    return segs, t


def crack_lines(o, img, idx, c):
    segs, t = link_segments(o, idx)
    col = np.tile(to_rgb(CRACK), (len(t), 1))

    def draw(ax, lw, boost):
        rgba = np.column_stack([col, np.clip(boost * (1 - t) ** 0.6, 0, 1)])
        ax.add_collection(LineCollection(segs, colors=rgba, linewidths=pt(lw, DPI), capstyle="round"))
    for radius, strength, lw, boost in ((16, 1.0, 4.0, 1.0), (5, 1.0, 2.8, 1.0)):
        img = fx.glow(img, fx.layer(c.W, c.H, DPI, lambda a, l=lw, b=boost: draw(a, l, b)), radius, strength)
    return fx.over(img, fx.layer(c.W, c.H, DPI, lambda a: draw(a, 1.5, 1.0)))


def scene(c, o):
    far, near = o.pick(False), o.pick(True)

    def lit(ax, idx, thick, tip, foot=0.35, boost=0.9):
        o.rays(ax, idx, 1.1 * thick, boost=boost)
        o.tips(ax, idx, tip)
        o.feet(ax, idx, thick, foot)

    near_boost = 0.55              # dim the near rays so the cracks carry the surface
    far_levels = ((36, 0.55, 3.0, 3.0), (11, 0.8, 2.0, 1.9), (3, 0.9, 1.3, 1.2))
    # near rays point at us and are foreshortened: keep their glow tight so
    # they stay crisp cracks of light instead of smudges
    near_levels = ((20, 0.2, 2.4, 2.0), (6, 0.45, 1.6, 1.4), (2, 0.8, 1.1, 1.0))
    img = paint_stars(c, c.gradient())
    for radius, strength, thick, tip in far_levels:             # the far rays first,
        lay = fx.layer(c.W, c.H, DPI, lambda a, t=thick, p=tip: lit(a, far, t, p))
        img = fx.glow(img, lay, radius, strength)
    img = fx.over(img, fx.layer(c.W, c.H, DPI, lambda a: lit(a, far, 1.0, 1.0)))   # crisp far rays
    img = paint_land(o, o.sphere(img))                          # hidden behind the ball,
    img = crack_lines(o, img, near, c)
    img = foot_halos(o, img, near, c)
    for radius, strength, thick, tip in near_levels:            # then the near rays
        lay = fx.layer(c.W, c.H, DPI, lambda a, t=thick, p=tip: lit(a, near, t, p, 0.8, near_boost))
        img = fx.glow(img, lay, radius, strength)
    ax = c.backdrop(image=img)
    lit(ax, near, 0.9, 0.9, 0.8, near_boost)
    return ax


# ---------------------------------------------------------------- notes
def big_note(ax, o, dx=None, dy=-62, ha=None):
    """Label the biggest quake, on the outward side of its tip."""
    i = int(np.argmax(MAG))
    x, y = o.tx[i], o.ty[i]
    if dx is None:
        dx, ha = (130, "left") if x < o.cx else (-130, "right")
    ex, ey = x + dx, y + dy
    ax.plot([x + (12 if dx > 0 else -12), ex], [y, ey + 8], color=THEME.ink, lw=0.9, alpha=0.6, zorder=7)
    ax.text(ex + (6 if dx > 0 else -6), ey, "Kamchatka, 29 July", fontproperties=font("note"),
            fontsize=pt(22, DPI), color=THEME.ink, ha=ha, va="bottom", path_effects=halo(4), zorder=8)
    ax.text(ex + (6 if dx > 0 else -6), ey + 8, "M8.8, the year's largest", fontproperties=font("sans"),
            fontsize=pt(15, DPI), color=THEME.muted, ha=ha, va="top", path_effects=halo(4), zorder=8)


def key(c, ax, o, x, y_base, width=280):
    c.text(x, y_base - o.tall * 4.4 - 36, "LENGTH · MAGNITUDE", role="small", color=THEME.muted)
    for i, mag in enumerate((5, 6, 7, 8)):
        xx = x + 10 + i * 56
        h = o.tall * (mag - MAG0)
        for a in np.linspace(0, 1, 6)[:-1]:
            ax.plot([xx, xx], [y_base - h * a, y_base - h * (a + .2)], color=CMAP(0.0),
                    lw=pt(1.4, DPI), alpha=0.1 + 0.9 * (a + .1) ** 1.4, zorder=6, solid_capstyle="round")
        ax.scatter([xx], [y_base - h], s=pt(2 * (1 + .55 * (mag - 4.5) ** 1.5), DPI) ** 2,
                   color=CMAP(0.0), lw=0, zorder=6)
        c.text(xx, y_base + 24, str(mag), role="small", color=THEME.muted, ha="center")
    y2 = y_base + 64
    c.text(x, y2, "COLOUR · DEPTH", role="small", color=THEME.muted)
    n = 160
    for i in range(n):
        ax.add_patch(Rectangle((x + width * i / n, y2 + 14), width / n + 0.6, 10,
                               fc=CMAP(i / (n - 1)), lw=0, zorder=6))
    for d in (0, 50, 150, 300, 700):
        tx = x + width * np.sqrt(d / DEPTH_MAX)
        c.text(tx, y2 + 48, f"{d}" + (" km" if d in (0, 700) else ""), role="small",
               color=THEME.muted, ha="left" if d == 0 else "center")


TITLE = "The cracking Earth"
SUBTITLE = ("Every magnitude 4.5+ earthquake of 2025, as a ray\n"
            "from its epicentre: length is magnitude, colour is depth.")


def export(fmt, out):
    """Both platforms use the 4:5 layout; only the footer's handle differs."""
    c = Canvas(fmt, THEME)
    o = Orb(c.W / 2 + 30, 770, 290, tall=36)
    ax = scene(c, o)
    c.header(TITLE, SUBTITLE, align="left")
    big_note(ax, o)
    key(c, ax, o, c.left, 1140)
    c.footer(SOURCE)
    return c.save(HERE / "output" / out)


if __name__ == "__main__":
    n = int((view_z(*VIEW) > 0).sum())
    print(f"{n} of {len(q)} quakes ({round(100 * n / len(q))}%) face us")
    for fmt, out in (("instagram", "quakes_instagram.png"), ("x_portrait", "quakes_x.png")):
        print("wrote", export(fmt, out).relative_to(HERE))
