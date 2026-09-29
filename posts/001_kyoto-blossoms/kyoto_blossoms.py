"""1,200 springs in Kyoto: peak cherry blossom date, 812-2026.

One petal per recorded year, placed by the day of peak bloom, drifting
beneath a glowing canopy at dusk. A smoothed ~50-year average runs through them in
lantern gold. Years without a record are left empty.

    python fetch_data.py       # once, to refresh data/
    python kyoto_blossoms.py   # writes output/*.png
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.patheffects as pe
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.path import Path as MPath
from matplotlib.transforms import Affine2D

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
from dataviz_style import Canvas, THEMES, font, pt, DPI  # noqa: E402
from dataviz_style import effects as fx  # noqa: E402
from canopy import canopy  # noqa: E402

THEME = THEMES["sakura_night"]
SOURCE = "Data: Yasuyuki Aono, Osaka Metropolitan University · via Our World in Data"
SIGMA = 15           # years: Gaussian weighting of the average (~50-year span)
MIN_RECORDS = 10     # records needed within +/-25 years to draw the average
SPAN = 6             # days from the mean at which the line colour saturates
CASING = "#0B0E24"   # dark outline under the average line, lifts it off the petals

# ---------------------------------------------------------------- data
df = pd.read_csv(HERE / "data" / "kyoto_bloom.csv")
record = df.loc[df.doy.idxmin()]                    # earliest peak bloom
full = df.set_index("year").doy.reindex(range(df.year.min(), df.year.max() + 1))
# Gaussian-weighted average over the recorded years only. Unlike a hard-edged
# window it doesn't jump each time a record enters or leaves the window.
_yrs, _vals = df.year.values, df.doy.values
_w = np.exp(-0.5 * ((full.index.values[:, None] - _yrs[None, :]) / SIGMA) ** 2)
_n = (np.abs(full.index.values[:, None] - _yrs[None, :]) <= 25).sum(axis=1)
trend = pd.Series(np.where(_n >= MIN_RECORDS, (_w * _vals).sum(1) / _w.sum(1), np.nan),
                  index=full.index)
MEAN = df.doy.mean()                                # the 1,200-year average bloom day


def doy_label(d):
    """Day-of-year -> 'Apr 15' (non-leap calendar, so +/-1 day in leap years)."""
    day = date(2001, 1, 1) + timedelta(days=int(d) - 1)
    return f"{day:%b} {day.day}"


DATE_TICKS = [91, 121]        # Apr 1, May 1 (mid-April is marked by the mean line)
YEAR_TICKS = [812, 1000, 1200, 1400, 1600, 1800, 2026]

# ---------------------------------------------------------------- the petal
# A cherry petal: narrow at the base, notched at the tip. Unit box, tip up.
_V = [(0, -1), (0.45, -0.6), (0.68, 0.4), (0.36, 0.95),
      (0.22, 1.06), (0.08, 0.96), (0, 0.78),
      (-0.08, 0.96), (-0.22, 1.06), (-0.36, 0.95),
      (-0.68, 0.4), (-0.45, -0.6), (0, -1), (0, -1)]
_C = [MPath.MOVETO] + [MPath.CURVE4] * 12 + [MPath.CLOSEPOLY]
PETAL = MPath(_V, _C)
ANGLES = np.arange(0, 360, 30)          # 12 orientations, purely decorative


def petal(angle):
    return Affine2D().rotate_deg(angle).transform_path(PETAL)


def petal_colors(n, rng):
    """Random tones between the theme's pale and deep pink -- texture, not data.

    A triangular draw keeps most petals near the middle tone, with a few
    paler and deeper ones, like a real drift of blossom.
    """
    light, dark = (np.array(to_rgb(h)) for h in THEME.mark_range)
    t = rng.triangular(0, 0.5, 1, size=n)[:, None]
    rgb = light + (dark - light) * t
    alpha = rng.uniform(0.75, 0.95, size=(n, 1))
    return np.hstack([rgb, alpha])


def petal_style(n):
    """Stable pseudo-random rotation and tone for each of n petals."""
    rng = np.random.default_rng(812)
    return rng.choice(ANGLES, size=n), petal_colors(n, rng)


def draw_petals(ax, x, y, size_px, scale=1.0):
    """Scatter the data petals (also used, scaled up, for their glow)."""
    rot, colors = petal_style(len(x))
    s = pt(size_px * scale, DPI) ** 2
    for a in ANGLES:
        m = rot == a
        ax.scatter(x[m], y[m], s=s, marker=petal(a), lw=0, c=colors[m])


# ---------------------------------------------------------------- effects
def halo(px, color, alpha=1.0):
    return [pe.Stroke(linewidth=pt(px, DPI), foreground=color, alpha=alpha), pe.Normal()]


def glow(color, widths=(20, 11, 5), alphas=(0.06, 0.13, 0.3)):
    """Soft light around a line: wide faint strokes under the real one."""
    return [pe.Stroke(linewidth=pt(w, DPI), foreground=color, alpha=a)
            for w, a in zip(widths, alphas)] + [pe.Normal()]


def note(c, ax, x, y, s, ha="left", color=None, size=None):
    """Italic annotation, haloed in the page colour behind it."""
    x_px, y_px = ax.transData.transform((x, y))
    return ax.text(x, y, s, fontproperties=font("note"), fontsize=pt(size or 21, DPI),
                   color=color or THEME.ink, ha=ha, va="center", linespacing=1.2,
                   path_effects=halo(5, c.page_color(c.H - y_px, x_px), alpha=0.6))


def deviation_colors(days):
    """Signed days from the mean -> diverging colour: ember (earlier),
    neutral (on the mean), ice (later). Saturates at +/-SPAN days."""
    early, mid, late = (np.array(to_rgb(h)) for h in THEME.diverging)
    t = np.clip(np.asarray(days) / SPAN, -1, 1)[:, None]
    return np.where(t < 0, mid + (early - mid) * -t, mid + (late - mid) * t)


def gradient_swatch(c, x, y, width, lw_px=3):
    """A short line running through the diverging scale, for the key."""
    t = np.linspace(-SPAN, SPAN, 40)
    xs = np.linspace(x, x + width, 41)
    segs = [[(c.fx(a), c.fy(y)), (c.fx(b), c.fy(y))] for a, b in zip(xs[:-1], xs[1:])]
    if CASING:
        c.fig.add_artist(LineCollection(segs, colors=CASING, linewidths=pt(lw_px + 4, DPI),
                                        capstyle="round", transform=c.fig.transFigure))
    c.fig.add_artist(LineCollection(segs, colors=deviation_colors(t), linewidths=pt(lw_px, DPI),
                                    capstyle="round", transform=c.fig.transFigure))


def key(c, y, x=None):
    """Key: petal = a recorded year; line = long-run average, coloured
    from earlier to later than the mean. Centred on the page if x is None."""
    muted = dict(role="label", color=THEME.muted)
    r = c.fig.canvas.get_renderer()
    width = lambda s: c.text(0, -100, s, **muted).get_window_extent(r).width
    parts = ["one recorded year", "long-run average,", "earlier", "later"]
    w = {p: width(p) for p in parts}
    for t in c.fig.texts[-len(parts):]:
        t.remove()
    total = 30 + 8 + w[parts[0]] + 44 + w[parts[1]] + 10 + w["earlier"] + 8 + 50 + 8 + w["later"]
    x = c.W / 2 - total / 2 if x is None else x

    ax = c.axes(x, y - 14, x + 30, y + 14)
    ax.set_xlim(-1, 1); ax.set_ylim(-1, 1); ax.set_axis_off()
    ax.scatter([0], [0], s=pt(15, DPI) ** 2, marker=petal(20), color=THEME.mark, lw=0)
    x += 38
    c.text(x, y + 6, parts[0], **muted); x += w[parts[0]] + 44
    c.text(x, y + 6, parts[1], **muted); x += w[parts[1]] + 10
    c.text(x, y + 6, "earlier", **muted); x += w["earlier"] + 8
    gradient_swatch(c, x, y, 50); x += 58
    c.text(x, y + 6, "later", **muted)


def guides(ax, orient):
    for d in DATE_TICKS:
        (ax.axvline if orient == "v" else ax.axhline)(d, color=THEME.guide, lw=1, zorder=0)


def outside(*boxes):
    """f(x, y) -> True when (x, y) px lies outside every (x0, y0, x1, y1) box."""
    return lambda x, y: not any(x0 < x < x1 and y0 < y < y1 for x0, y0, x1, y1 in boxes)


def scene(c, limbs, allowed, seed, keep_out=(), far_limbs=None, far_allowed=None):
    """Dusk sky + glowing canopy (decoration), with an optional far layer of
    trees behind it for depth. Returns the page image."""
    # blossom thins towards the centre so the sky opens up, as under real trees
    thin = lambda x, y: 0.3 + 0.7 * min(1, abs(x - c.W / 2) / (c.W / 2)) ** 0.8
    # the far trees thin less, so distant blossom shows through the sky gap
    far_thin = lambda x, y: 0.65 + 0.35 * min(1, abs(x - c.W / 2) / (c.W / 2))
    return canopy(c.gradient(), limbs, allowed, PETAL, THEME.mark_range,
                  lambda px: pt(px, DPI), DPI, seed=seed, keep_out=keep_out,
                  density=1.5, thin=thin, far_limbs=far_limbs, far_allowed=far_allowed,
                  far_thin=far_thin)


def light_the_scene(c, img, ax, x, y, size_px, orient, light):
    """Distant light + a soft glow around every data petal and the average
    line, then set the page.

    The glow is a blurred copy of the real marks, so it only brightens
    around marks that exist: it adds no marks of its own.
    """
    img = fx.radial_light(img, *light, color="#7B6BB0", strength=0.22)

    def to_px(xy):
        p = ax.transData.transform(xy)
        p[:, 1] = c.H - p[:, 1]
        return p

    px = to_px(np.column_stack([x, y]))
    petals = fx.layer(c.W, c.H, DPI, lambda a: draw_petals(a, px[:, 0], px[:, 1], size_px, 1.3))
    img = fx.glow(img, petals, 6, 0.8)
    img = fx.glow(img, petals, 16, 0.35)
    line = fx.layer(c.W, c.H, DPI, lambda a: trend_line(a, trend, orient, 7, transform=to_px))
    img = fx.glow(img, line, 6, 1.0)
    img = fx.glow(img, line, 22, 0.7)
    c.backdrop(image=img)


def trend_segments(trend, orient):
    """Segments of the long-run average and their colours (by distance from
    the mean). A gap in the average breaks the line instead of bridging it."""
    t = trend.dropna()
    pts = (np.column_stack([t.values, t.index]) if orient == "v"
           else np.column_stack([t.index, t.values]))
    joined = np.diff(t.index.values) == 1
    segs = np.stack([pts[:-1], pts[1:]], axis=1)[joined]
    rgb = deviation_colors(((t.values[:-1] + t.values[1:]) / 2 - MEAN)[joined])
    return segs, rgb


def trend_line(ax, trend, orient, lw_px=4, transform=None):
    """The long-run average, each segment coloured by its distance from the mean.
    `transform` maps data to px, for drawing the same line into the glow layer."""
    segs, rgb = trend_segments(trend, orient)
    if transform is not None:
        segs = transform(segs.reshape(-1, 2)).reshape(segs.shape)
    elif CASING:
        # a dark casing under the line lifts it off the petals, as on a map
        ax.add_collection(LineCollection(segs, colors=CASING, linewidths=pt(lw_px + 4, DPI),
                                         capstyle="round", zorder=4, alpha=0.9))
    ax.add_collection(LineCollection(segs, colors=rgb, linewidths=pt(lw_px, DPI),
                                     capstyle="round", zorder=4))


def mean_line(c, ax, orient, label_at):
    """Faint dashed line at the 1,200-year mean: the zero for the colours."""
    kw = dict(color=THEME.muted, lw=1, ls=(0, (3, 4)), alpha=0.6, zorder=1)
    (ax.axvline if orient == "v" else ax.axhline)(MEAN, **kw)
    label = f"1,200-year average · {doy_label(round(MEAN))}"
    note(c, ax, *label_at, label, color=THEME.muted, size=17,
         ha="center" if orient == "v" else "left")


def data_layer(ax, x, y, trend_series, orient, size_px, record_xy):
    draw_petals(ax, x, y, size_px)
    trend_line(ax, trend_series, orient)
    # the record year, re-drawn on top in the "earlier" colour
    early = THEME.diverging[0]
    ax.scatter(*record_xy, s=pt(size_px + 6, DPI) ** 2, marker=petal(0),
               color=early, lw=0, zorder=5, path_effects=glow(early, (14, 8), (0.1, 0.2)))


TITLE = "1,200 springs in Kyoto"
SUBTITLE = ("The day Kyoto's cherry trees reach full bloom, recorded\n"
            "in court diaries since 812 and observed to this day")
REC_NOTE = (f"{doy_label(record.doy).replace('Mar', 'March')}, {record.year}\n"
            "the earliest peak bloom\nin 1,200 years")


def mirrored(W, right, steep_below):
    """Right-side limbs (x measured in from the right edge) plus their mirror
    image. Low left limbs climb steeply first, so they don't run straight into
    the clear zone kept beside the date/year labels."""
    right = [(W + dx, y, a, l, w, d) for dx, y, a, l, w, d in right]
    left = [(W - x, y, -86 if y > steep_below else 180 - a, l, w, d)
            for x, y, a, l, w, d in right]
    return right + left


# ---------------------------------------------------------------- Instagram 4:5
def instagram():
    c = Canvas("instagram", THEME)
    W, mid = c.W, c.W / 2

    # a symmetric U: blossom curtains down both edges, a shallow arch between,
    # and the centred title in the window of sky
    def canopy_bottom(x):
        b = 100 + 595 * (abs(x - mid) / mid) ** 1.8
        return min(b, 470) if 66 <= x < 150 else b      # stay off the year labels

    limbs = mirrored(W, [(30, 660, -112, 280, 26, 6), (30, 490, -138, 270, 20, 6),
                         (30, 330, -158, 280, 20, 6), (30, 170, -170, 300, 14, 7),
                         (30, 40, 176, 240, 16, 6)], steep_below=470)
    limbs += [(-15, 640, -92, 300, 7, 5), (-15, 450, -88, 230, 6, 5)]   # twigs in the left strip
    y0 = c.header(TITLE, SUBTITLE, top=250, align="center")
    top, bottom = y0 + 95, c.footer_top - 70
    title_box = (200, 215, W - 200, 400)

    # the far trees reach ~50 px deeper, peeking out below the front canopy,
    # but never behind the title, the key or the plot (incl. its labels)
    near_ok = lambda x, y: -80 < y < canopy_bottom(x) and -80 < x < W + 80
    clear = outside(title_box, (220, y0 + 5, W - 220, y0 + 50),
                    (80, top - 14, c.right + 14, bottom + 40))
    far = mirrored(W, [(20, 580, -122, 260, 15, 6), (20, 410, -148, 280, 12, 6),
                       (20, 250, -164, 300, 10, 7), (20, 100, -176, 320, 9, 7),
                       (20, 150, -178, 460, 8, 7)],
                   steep_below=470)
    img = scene(c, seed=7, keep_out=[title_box], limbs=limbs, allowed=near_ok,
                far_limbs=far, far_allowed=lambda x, y: near_ok(x, y - 90) and clear(x, y))

    key(c, y0 + 30)
    ax = c.axes(c.left + 60, top, c.right, bottom)
    ax.set_xlim(80, 128)
    ax.set_ylim(2032, 805)                           # time runs down the page
    light_the_scene(c, img, ax, df.doy.values, df.year.values, 15, "v",
                    light=(W * 0.52, 700, 380, 280))
    guides(ax, "v")

    data_layer(ax, df.doy.values, df.year.values, trend, "v", 15,
               ([record.doy], [record.year]))
    mean_line(c, ax, "v", label_at=(MEAN, 820))

    # notes sit in the empty corners: early dates before 1900, late dates after
    ax.annotate("", xy=(record.doy, record.year - 12), xytext=(84, 1905),
                arrowprops=dict(arrowstyle="-", color=THEME.ink, lw=0.8))
    note(c, ax, 81.2, 1862, REC_NOTE)
    note(c, ax, 111, 1968, "From the 1850s, spring\ncomes earlier as the\ncity and climate warm",
         color=THEME.muted)
    note(c, ax, 81.2, 1075, "Before 1400,\nmany springs\nwent unrecorded", color=THEME.muted)

    ax.set_xticks(DATE_TICKS, [doy_label(d) for d in DATE_TICKS])
    ax.set_yticks(YEAR_TICKS, [str(y) for y in YEAR_TICKS])
    c.style_ticks(ax)
    c.footer(SOURCE)
    return c.save(HERE / "output" / "kyoto_blossoms_instagram.png")


# ---------------------------------------------------------------- X 16:9
def x_post():
    c = Canvas("x", THEME)
    W, mid = c.W, c.W / 2

    # the same U, flattened: curtains outside the plot, a thin arch above the title
    def canopy_bottom(x):
        if x < 66 or x > c.right + 6:
            return 540                                   # curtains beside the plot
        return 38 + 190 * (abs(x - mid) / mid) ** 1.8

    limbs = mirrored(W, [(30, 560, -98, 320, 22, 6), (30, 330, -130, 260, 20, 6),
                         (30, 150, -165, 320, 18, 6), (30, 30, 178, 380, 14, 6)],
                     steep_below=200)
    limbs += [(-15, 520, -92, 280, 7, 5), (-15, 330, -88, 200, 6, 5)]   # twigs in the left strip
    y0 = c.header(TITLE, SUBTITLE, align="center")
    top, bottom = y0 + 30, c.footer_top - 60
    title_box = (440, 45, W - 440, 200)

    near_ok = lambda x, y: -80 < y < canopy_bottom(x) and -80 < x < W + 80
    clear = outside(title_box, (80, top - 40, c.right + 14, bottom + 40))
    far = mirrored(W, [(20, 450, -110, 280, 14, 6), (20, 240, -145, 280, 11, 6),
                       (20, 80, -172, 360, 9, 6)], steep_below=200)
    img = scene(c, seed=11, keep_out=[title_box], limbs=limbs, allowed=near_ok,
                far_limbs=far, far_allowed=lambda x, y: near_ok(x, y - 50) and clear(x, y))

    key(c, bottom - 26, x=c.left + 110)
    ax = c.axes(c.left + 70, top, c.right, bottom)
    ax.set_xlim(800, 2034)
    ax.set_ylim(80, 128)                              # later dates higher up
    light_the_scene(c, img, ax, df.year.values, df.doy.values, 13, "h",
                    light=(W * 0.6, 460, 560, 220))
    guides(ax, "h")

    data_layer(ax, df.year.values, df.doy.values, trend, "h", 13,
               ([record.year], [record.doy]))
    mean_line(c, ax, "h", label_at=(1560, MEAN - 1.8))

    ax.annotate("", xy=(record.year - 6, record.doy + 0.3), xytext=(1905, 84.5),
                arrowprops=dict(arrowstyle="-", color=THEME.ink, lw=0.8,
                                connectionstyle="arc3,rad=-0.2"))
    note(c, ax, 1898, 84.5, REC_NOTE.replace("\n", " ", 1), ha="right")
    note(c, ax, 820, 126.5, "Before 1400, many springs went unrecorded", color=THEME.muted)

    ax.set_yticks(DATE_TICKS, [doy_label(d) for d in DATE_TICKS])
    ax.set_xticks(YEAR_TICKS, [str(y) for y in YEAR_TICKS])
    c.style_ticks(ax)
    c.footer(SOURCE)
    return c.save(HERE / "output" / "kyoto_blossoms_x.png")


if __name__ == "__main__":
    for p in (instagram(), x_post()):
        print("wrote", p.relative_to(HERE))
