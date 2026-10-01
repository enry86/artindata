"""Near, or like home: every known exoplanet, placed twice.

Two spiral arms leave Earth. Along one, each planet sits at how far it is
from Earth-like (see similarity.py); along the other, at how far away it is
(light-years, log scale). The 12 most Earth-like worlds (gold) and the 12
nearest (rose) are joined across the arms by threads of light.

    python fetch_data.py    # once, to refresh data/
    python exoplanets.py    # writes output/*.png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.patheffects as pe
from matplotlib.colors import to_rgb
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
from dataviz_style import Canvas, THEMES, font, pt, DPI  # noqa: E402
from dataviz_style import effects as fx  # noqa: E402
from similarity import score  # noqa: E402

THEME = THEMES["deep_space"]
LIKE, NEAR = THEME.highlights           # gold: most Earth-like, rose: nearest
EARTH = "#4FA3FF"
EARTH_R = 24            # px, drawn size of the Earth disc
SOURCE = "Data: NASA Exoplanet Archive, Sept 2026 · Earth-likeness score: see README"
N = 12
LABELS = 5              # worlds named on the picture, per list

# ---------------------------------------------------------------- data
LY_PER_PC = 3.26156
planets = pd.read_csv(HERE / "data" / "planets.csv")
planets = planets[planets.pl_controv_flag == 0]
df = score(planets).dropna(subset=["d_earth", "sy_dist"]).sort_values("d_earth")
df["rank"] = np.arange(1, len(df) + 1)
df["ly"] = df.sy_dist * LY_PER_PC
like = df.head(N)
near = df.nsmallest(N, "ly")
assert not set(like.pl_name) & set(near.pl_name)   # the headline: no world in both

# ---------------------------------------------------------------- the rulers
# both rulers are logarithmic: each equal stretch of arm multiplies the value
STEPS_MIN, STEPS_MAX = 0.3, 20      # Earth-likeness arm (every planet fits: 0.55..19)
LY_MIN, LY_MAX = 1, 20_000          # distance arm (4.2..14,000 ly)
TWIST = 0.6             # turns each arm makes over its length
R0 = 0.06               # the arms leave Earth at this fraction of the radius


def u_like(steps):
    return np.log10(np.asarray(steps, float) / STEPS_MIN) / np.log10(STEPS_MAX / STEPS_MIN)


def u_far(ly):
    return np.log10(np.asarray(ly, float) / LY_MIN) / np.log10(LY_MAX / LY_MIN)


class Spiral:
    """Two arms around (cx, cy) px. Position along the arm (u in 0..1) is
    the value; the radius grows linearly with u, so distance from Earth
    reads the same way on both arms."""

    def __init__(self, cx, cy, R, rotation=90):
        self.cx, self.cy, self.R = cx, cy, R
        self.phase = {"like": np.radians(rotation), "far": np.radians(rotation + 180)}

    def theta(self, u, arm):
        return self.phase[arm] - 2 * np.pi * TWIST * np.asarray(u)

    def xy(self, u, arm):
        u = np.asarray(u, float)
        rad = self.R * (R0 + (1 - R0) * u)
        th = self.theta(u, arm)
        return self.cx + rad * np.cos(th), self.cy - rad * np.sin(th)

    def normal(self, u, arm, eps=1e-3):
        """Unit normal to the arm (for its thickness, which carries no data)."""
        x0, y0 = self.xy(u - eps, arm)
        x1, y1 = self.xy(u + eps, arm)
        tx, ty = x1 - x0, y1 - y0
        n = np.hypot(tx, ty)
        return -ty / n, tx / n


# ---------------------------------------------------------------- effects
def halo(px, color=THEME.bg, alpha=0.8):
    return [pe.Stroke(linewidth=pt(px, DPI), foreground=color, alpha=alpha), pe.Normal()]


ARM_TINT = {"like": ("#E2ECFF", "#6F90E6"),    # starlight blue
            "far": ("#F6E8FF", "#B283E6")}     # violet: tells the two arms apart


def dust(sp, arm, u, size_px, alpha, seed):
    """Every planet as a speck on the arm. The spread across the arm is
    random, like a galaxy's thickness: it moves specks sideways only, so
    each one still lies at its value along the arm."""
    rng = np.random.default_rng(seed)
    x, y = sp.xy(u, arm)
    nx, ny = sp.normal(u, arm)
    spread = sp.R * (0.007 + 0.03 * u) * rng.normal(size=len(u))
    light, dark = (np.array(to_rgb(h)) for h in ARM_TINT[arm])
    t = rng.triangular(0, 0.4, 1, size=len(u))[:, None]
    rgba = np.hstack([light + (dark - light) * t, np.full((len(u), 1), alpha)])
    return x + nx * spread, y + ny * spread, pt(size_px, DPI) ** 2, rgba


def thread(sp, a, b):
    """A curve from a planet's place on one arm to its place on the other,
    bowing towards Earth."""
    a, b = np.asarray(a), np.asarray(b)
    ctrl = np.array([sp.cx, sp.cy]) + ((a + b) / 2 - [sp.cx, sp.cy]) * 0.2
    return MPath([a, ctrl, b], [MPath.MOVETO, MPath.CURVE3, MPath.CURVE3])


def places(sp, group):
    return (np.column_stack(sp.xy(u_like(group.d_earth), "like")),
            np.column_stack(sp.xy(u_far(group.ly), "far")))


def draw_threads(ax, sp, group, color, lw_px, alpha):
    a, b = places(sp, group)
    for p, q in zip(a, b):
        ax.add_patch(PathPatch(thread(sp, p, q), fc="none", ec=color,
                               lw=pt(lw_px, DPI), alpha=alpha, capstyle="round"))


def draw_planets(ax, sp, group, color, size_px, zorder=5, glow_copy=False):
    """A planet on both arms. Hollow when only a minimum mass is known."""
    a, b = places(sp, group)
    hollow = (group.size_from == "min_mass").values
    s = pt(size_px, DPI) ** 2
    for xy in (a, b):
        ax.scatter(xy[~hollow, 0], xy[~hollow, 1], s=s, color=color, lw=0, zorder=zorder)
        fill = (*to_rgb(color), 0.25) if not glow_copy else "none"
        ax.scatter(xy[hollow, 0], xy[hollow, 1], s=s, facecolor=THEME.bg if not glow_copy else "none",
                   lw=0, zorder=zorder)
        ax.scatter(xy[hollow, 0], xy[hollow, 1], s=s, facecolor=fill,
                   edgecolor=color, lw=pt(2.6, DPI), zorder=zorder)


def arm_ticks(c, ax, sp, arm, values, labels, gap=34):
    """Ruler ticks: a short stroke across the arm, its value on the outer side."""
    u = u_like(values) if arm == "like" else u_far(values)
    x, y = sp.xy(u, arm)
    nx, ny = sp.normal(u, arm)
    for xi, yi, nxi, nyi, lab in zip(x, y, nx, ny, labels):
        ax.plot([xi - nxi * 7, xi + nxi * 7], [yi - nyi * 7, yi + nyi * 7],
                color=THEME.muted, lw=1, alpha=0.8, zorder=3)
        d = gap * np.sign(nxi * (xi - sp.cx) + nyi * (yi - sp.cy))
        ax.text(xi + nxi * d, yi + nyi * d, lab, fontproperties=font("sans"),
                fontsize=pt(14, DPI), color=THEME.muted, ha="center", va="center",
                path_effects=halo(4), zorder=6)


# ---------------------------------------------------------------- labels
def spread_labels(ys, gap, lo, hi):
    """Push sorted label y's apart to at least `gap`, within [lo, hi]."""
    order = np.argsort(ys)
    out = np.array(ys, float)[order]
    out[0] = max(out[0], lo)
    for i in range(1, len(out)):
        out[i] = max(out[i], out[i - 1] + gap)
    over = out[-1] - hi
    if over > 0:
        out -= over
        for i in range(len(out) - 2, -1, -1):
            out[i] = min(out[i], out[i + 1] - gap)
    res = np.empty_like(out)
    res[order] = out
    return np.maximum(res, lo)


def label_column(ax, points, texts, x_text, ha, color, lo, hi, gap=24):
    """Labels stacked in a column at x_text, each with a leader to its point."""
    if not len(points):
        return
    ys = spread_labels(points[:, 1], gap, lo, hi)
    for (px, py), ty, s in zip(points, ys, texts):
        end = x_text - 8 if ha == "left" else x_text + 8
        ax.plot([px, (px + end) / 2, end], [py, ty, ty], color=color, lw=0.8,
                alpha=0.55, zorder=4, solid_capstyle="round")
        ax.text(x_text, ty, s, fontproperties=font("sans"), fontsize=pt(15, DPI),
                color=THEME.ink, ha=ha, va="center", path_effects=halo(4), zorder=6)


def fmt_ly(ly):
    return f"{ly:,.0f} ly" if ly >= 10 else f"{ly:.1f} ly"


# ---------------------------------------------------------------- scene
def scene(c, sp):
    """Sky, the two dust arms and their glow, the threads' glow, and Earth's
    light. Every glow is a blurred copy of real marks: it adds none."""
    img = c.gradient()
    img = fx.radial_light(img, sp.cx, sp.cy, sp.R * 0.55, sp.R * 0.55, "#3A4C9A", 0.35)

    specks = [dust(sp, "like", u_like(df.d_earth), 2.4, 0.55, 1),
              dust(sp, "far", u_far(df.ly), 2.4, 0.55, 2)]

    def draw_dust(ax, scale=1.0):
        for x, y, s, rgba in specks:
            ax.scatter(x, y, s=s * scale, c=rgba, lw=0)

    layer = fx.layer(c.W, c.H, DPI, lambda a: (draw_dust(a, 2.5), spines(a, sp, 5, 0.6)))
    img = fx.glow(img, layer, 14, 0.9)
    img = fx.glow(img, layer, 40, 0.6)

    def lit(ax):
        draw_threads(ax, sp, near, NEAR, 4, 0.9)
        draw_threads(ax, sp, like, LIKE, 4, 0.9)
        draw_planets(ax, sp, near, NEAR, 16, glow_copy=True)
        draw_planets(ax, sp, like, LIKE, 16, glow_copy=True)
    layer = fx.layer(c.W, c.H, DPI, lit)
    img = fx.glow(img, layer, 5, 0.9)
    img = fx.glow(img, layer, 18, 0.6)

    # Earth: a small lit world at the core
    img = fx.radial_light(img, sp.cx, sp.cy, 46, 46, EARTH, 0.9)
    img = fx.radial_light(img, sp.cx, sp.cy, 120, 120, EARTH, 0.4)
    img = fx.over(img, earth_disc(c.W, c.H, sp.cx, sp.cy, EARTH_R))
    ax = c.backdrop(image=img)
    draw_dust(ax)
    return ax


def spines(ax, sp, lw_px=1.6, alpha=0.45):
    """The two rulers themselves, from Earth to the arms' ends. They start
    bright at Earth, so the planets are visibly tied to it, and fade outwards."""
    from matplotlib.collections import LineCollection
    u = np.linspace(0, 1, 500)
    for arm in ("like", "far"):
        x, y = sp.xy(u, arm)
        segs = np.stack([np.column_stack([x[:-1], y[:-1]]), np.column_stack([x[1:], y[1:]])], axis=1)
        fade = 1 - u[:-1]
        rgba = np.tile(to_rgb(ARM_TINT[arm][1]), (len(segs), 1))
        rgba = np.hstack([rgba, (alpha * (1 + 1.6 * fade ** 1.5)).clip(0, 1)[:, None]])
        ax.add_collection(LineCollection(segs, colors=rgba, linewidths=pt(lw_px, DPI) * (1 + 1.2 * fade),
                                         capstyle="round", zorder=2))


def earth_disc(W, H, cx, cy, r):
    """A small shaded sphere: ocean blue, lit from the upper left, with a thin
    atmosphere rim. Decoration only -- Earth is the origin, not a data point."""
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    dx, dy = (xx - cx) / r, (yy - cy) / r
    rho2 = dx ** 2 + dy ** 2
    inside = rho2 <= 1
    nz = np.sqrt(np.clip(1 - rho2, 0, 1))
    lam = np.clip(-0.55 * dx - 0.55 * dy + 0.63 * nz, 0, 1)          # light from upper left
    ocean, deep = np.array(to_rgb("#6CB8FF")), np.array(to_rgb("#0B2F7A"))
    rgb = deep + (ocean - deep) * lam[..., None] ** 0.8
    rgb += np.array([0.9, 0.95, 1.0]) * (np.clip(lam - 0.8, 0, 1) ** 2 * 1.5)[..., None]   # sun glint
    rim = np.clip((rho2 - 0.7) / 0.3, 0, 1) ** 2 * inside             # atmosphere
    rgb = rgb + (np.array(to_rgb("#BFE0FF")) - rgb) * (0.55 * rim)[..., None]
    edge = np.clip((1 - np.sqrt(rho2)) * r, 0, 1)                      # 1px antialias
    return np.dstack([rgb.clip(0, 1), edge])


def data_layer(ax, sp):
    spines(ax, sp)
    draw_threads(ax, sp, near, NEAR, 1.4, 0.75)
    draw_threads(ax, sp, like, LIKE, 1.4, 0.75)
    draw_planets(ax, sp, near, NEAR, 13)
    draw_planets(ax, sp, like, LIKE, 13)
    ax.text(sp.cx, sp.cy + EARTH_R + 22, "Earth", fontproperties=font("note"), fontsize=pt(19, DPI),
            color=THEME.ink, ha="center", va="center", path_effects=halo(5), zorder=7)


def key(c, ax, y, vertical=False):
    """Gold = most Earth-like, rose = nearest, hollow = minimum mass only."""
    items = [(LIKE, False, f"the {N} most Earth-like worlds"),
             (NEAR, False, f"the {N} nearest"),
             (THEME.muted, True, "hollow: only a minimum mass is known")]
    r = c.fig.canvas.get_renderer()
    widths = [c.text(0, -100, s, role="label").get_window_extent(r).width for *_, s in items]
    for t in c.fig.texts[-len(items):]:
        t.remove()
    if vertical:
        for i, ((col, hollow, s), w) in enumerate(zip(items, widths)):
            yy = y + i * 34
            ax.scatter([c.left + 7], [yy], s=pt(12, DPI) ** 2, lw=pt(2, DPI) if hollow else 0,
                       facecolor="none" if hollow else col, edgecolor=col)
            c.text(c.left + 22, yy + 6, s, role="label", color=THEME.muted)
        return
    total = sum(widths) + len(items) * 26 + (len(items) - 1) * 34
    x = c.W / 2 - total / 2
    for (col, hollow, s), w in zip(items, widths):
        ax.scatter([x + 7], [y], s=pt(12, DPI) ** 2, lw=pt(2, DPI) if hollow else 0,
                   facecolor="none" if hollow else col, edgecolor=col)
        c.text(x + 22, y + 6, s, role="label", color=THEME.muted)
        x += 26 + w + 34


TITLE = "Near, or like home"
SUBTITLE = ("Every known exoplanet, placed twice: by how Earth-like it is\n"
            "and by how far away it is. The two top-12 lists share no world.")


def arm_titles(ax, sp, u=0.97, off=46):
    """Name each arm at its outer end, just beyond the tip."""
    for arm, s in (("like", "similarity"), ("far", "distance")):
        x, y = sp.xy(u, arm)
        nx, ny = sp.normal(u, arm)
        d = off * np.sign(nx * (x - sp.cx) + ny * (y - sp.cy))
        ax.text(x + nx * d, y + ny * d, s, fontproperties=font("note"), fontsize=pt(24, DPI),
                color=ARM_TINT[arm][0], ha="center", va="center", path_effects=halo(5), zorder=7)


def name_labels(ax, c, sp, y0, left_x, right_x):
    """Name the LABELS best-ranked and LABELS nearest worlds, in columns."""
    lo, hi = y0, c.footer_top - 20
    lab_like, lab_near = like.head(LABELS), near.head(LABELS)
    for group, col, which, fmt in (
            (lab_like, LIKE, 1, lambda r, n, l: f"#{r}  {n} · {fmt_ly(l)}"),
            (lab_near, NEAR, 0, lambda r, n, l: f"{n} · {fmt_ly(l)} · #{r}")):
        pts = places(sp, group)[which]          # like: on the distance arm; near: on its likeness arm
        names = np.array([fmt(r, n, l) for r, n, l in zip(group["rank"], group.pl_name, group.ly)])
        right = pts[:, 0] >= sp.cx
        label_column(ax, pts[right], names[right], right_x, "left", col, lo, hi)
        label_column(ax, pts[~right], names[~right], left_x, "right", col, lo, hi)


# ---------------------------------------------------------------- Instagram 4:5
def instagram(out="exoplanets_instagram.png"):
    c = Canvas("instagram", THEME)
    sp = Spiral(c.W / 2 + 10, 770, 450)
    ax = scene(c, sp)
    y0 = c.header(TITLE, SUBTITLE, align="center")
    key(c, ax, y0 + 36)
    data_layer(ax, sp)
    arm_ticks(c, ax, sp, "like", [1, 2, 5], ["1", "2", "5"])
    arm_ticks(c, ax, sp, "far", [10, 100, 1000], ["10", "100", "1,000"])
    name_labels(ax, c, sp, y0 + 80, c.left + 150, c.right - 150)
    arm_titles(ax, sp)
    c.footer(SOURCE)
    return c.save(HERE / "output" / out)


# ---------------------------------------------------------------- X 16:9
def x(out="exoplanets_x.png"):
    c = Canvas("x", THEME)
    sp = Spiral(1010, 458, 345)
    ax = scene(c, sp)
    y0 = c.header(TITLE, SUBTITLE, align="left")
    key(c, ax, y0 + 40, vertical=True)
    data_layer(ax, sp)
    arm_ticks(c, ax, sp, "like", [1, 2, 5], ["1", "2", "5"])
    arm_ticks(c, ax, sp, "far", [10, 100, 1000], ["10", "100", "1,000"])
    name_labels(ax, c, sp, y0 + 40, 700, 1355)
    arm_titles(ax, sp)
    c.footer(SOURCE)
    return c.save(HERE / "output" / out)


if __name__ == "__main__":
    for p in (instagram(), x()):
        print("wrote", p.relative_to(HERE))
