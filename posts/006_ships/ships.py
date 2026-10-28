"""Under sail: every logged position of 1,736 ship logbooks, 1750-1855.

Each thread is one ship's track, drawn from one logged position to the next.
No land is drawn: the continents are where no ship went. The chart around
the tracks (graticule, tropics, degree border, compass rose and its rhumb
lines) is drawn in ink in the manner of an 18th-century sea chart.

    python fetch_data.py    # once, to refresh data/
    python ships.py         # writes output/*.png
"""
import csv
import sys
from datetime import date
from pathlib import Path

import numpy as np
from matplotlib import patheffects
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Polygon, Rectangle

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
from dataviz_style import Canvas, THEMES, DPI, font, pt  # noqa: E402
from dataviz_style import effects as fx  # noqa: E402

TITLE = "Under sail"
SUBTITLE = ("Every position in 1,736 ships' logbooks, 1750–1855.\n"
            "No land is drawn: the continents are where no ship went.")
SOURCE = "Data: CLIWOC 2.1 (PANGAEA) · CC BY 3.0"
NATIONS = ["DUTCH", "BRITISH", "SPANISH", "FRENCH"]
FIRST_YEAR = 1750        # 926 scattered earlier positions (1662-1749) are left out
MAX_GAP_DAYS = 3          # longer silences in a logbook break the thread
MAX_STEP_DEG = 8          # so does an implausible jump between two fixes
LON = (-98, 115)          # Gulf of Mexico to Java; most of the Pacific is cut
LAT_SOUTH = -68           # the northern edge follows from the page height
INSET = 34                # page edge to the chart's neatline, px
ROSE = (93, 73)           # compass rose centre (lon, lat): the empty Arctic corner

THEME = THEMES["logbook"]   # nation inks in NATIONS order

# Logbook remarks as transcribed by CLIWOC (Dutch ones translated), each pinned
# to the position logged that day:
# (date, ship, who, lat, lon, text, text position (lon, lat))
NOTES = [
    ("30 Jun 1768", "Prince Rupert", "British", 57.2, -21.4,
     "“At 1 am it cleared, saw the moon\neclipsed […] and 3 minutes past 2\n"
     "she was total eclipse.”", (-66, 73.5)),
    ("18 Apr 1820", "Delphina", "Dutch", 35.0, -18.6,
     "“Mutiny among the soldiers narrowly\nprevented. They wanted to seize\n"
     "the ship, murder their opponents\nand sail to America.”", (-6, 36.0)),
    ("11 May 1817", "Tromp", "Dutch", 0.3, -21.6,
     "“The black land bird is worn out from flying\nand lets itself be caught easily. "
     "It is put\nin a little basket in the gallery.”", (9, 11.0)),
    ("16 Sep 1816", "Maria Reigersbergen", "Dutch", -36.1, 34.9,
     "“Cartridges in the powder room\ngnawed by rats.”", (48, -8.5)),
    ("27 Dec 1794", "Centurion", "British", 18.2, 72.7,
     "“Pirates”", (66, 50.0)),
    ("17 Jan 1773", "Resolution", "British", -66.6, 39.6,
     "Sea ice. James Cook's ship is the first\nknown to cross the Antarctic Circle.", (46, -61.0)),
]
NOTE_PX = 18              # quote size; 1.15 line spacing


# ---------------------------------------------------------------- data
def load_positions():
    with open(HERE / "data" / "positions.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f) if int(r["year"]) >= FIRST_YEAR]
    lon = np.array([float(r["lon"]) for r in rows])
    lat = np.array([float(r["lat"]) for r in rows])
    nation = np.array([r["nation"] for r in rows])
    book = np.array([r["logbook"] for r in rows])
    day = np.array([date(int(r["year"]), int(r["month"]), int(r["day"])).toordinal()
                    if valid_date(r) else -10**6 for r in rows])
    return lon, lat, nation, book, day


def valid_date(r):
    try:
        date(int(r["year"]), int(r["month"]), int(r["day"]))
        return True
    except ValueError:
        return False


def links(lon, lat, book, day):
    """True for i where position i-1 -> i is drawn as one leg of a track."""
    return ((book[1:] == book[:-1])
            & (np.abs(np.diff(day)) <= MAX_GAP_DAYS)
            & (np.abs(np.diff(lon)) <= MAX_STEP_DEG)
            & (np.abs(np.diff(lat)) <= MAX_STEP_DEG))


# ---------------------------------------------------------------- projection
def mercator_y(lat):
    return np.degrees(np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)))


def mercator_lat(y):
    return np.degrees(2 * np.arctan(np.exp(np.radians(y))) - np.pi / 2)


class Chart:
    """Mercator over LON, from LAT_SOUTH up to whatever fits the box (px)."""

    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom
        self.s = (right - left) / (LON[1] - LON[0])
        self.y_south = mercator_y(LAT_SOUTH)
        self.lat_north = float(mercator_lat(self.y_south + (bottom - top) / self.s))

    def px(self, lon):
        return self.left + (np.asarray(lon) - LON[0]) * self.s

    def py(self, lat):
        # same scale both ways: shapes stay true to the projection
        return self.bottom - (mercator_y(np.asarray(lat)) - self.y_south) * self.s

    def xy(self, lat, lon):
        return float(self.px(lon)), float(self.py(lat))


# ---------------------------------------------------------------- drawing
def clip_to(ax, ch, artist):
    artist.set_clip_path(Rectangle((ch.left, ch.top), ch.right - ch.left, ch.bottom - ch.top,
                                   transform=ax.transData))
    return artist


def runs(link):
    """(start, stop) index ranges of the unbroken stretches of each track."""
    breaks = np.flatnonzero(~link) + 1
    starts = np.r_[0, breaks]
    stops = np.r_[breaks, len(link) + 1]
    return [(a, b) for a, b in zip(starts, stops) if b - a >= 2]


def catmull_rom(p, k=4):
    """Smooth curve through every point of `p` (n x 2), k samples per leg."""
    q = np.vstack([p[:1], p, p[-1:]])
    p0, p1, p2, p3 = q[:-3], q[1:-2], q[2:-1], q[3:]
    t = np.linspace(0, 1, k, endpoint=False)[None, :, None]
    c = 0.5 * ((2 * p1)[:, None] + (p2 - p0)[:, None] * t
               + (2 * p0 - 5 * p1 + 4 * p2 - p3)[:, None] * t ** 2
               + (3 * p1 - p0 - 3 * p2 + p3)[:, None] * t ** 3)
    return np.vstack([c.reshape(-1, 2), p[-1:]])


def wobble(curve, rng, amp=0.35):
    """A pen's sub-pixel tremor across the stroke; far below the data's precision."""
    d = np.gradient(curve, axis=0)
    n = np.c_[-d[:, 1], d[:, 0]] / (np.hypot(d[:, 0], d[:, 1])[:, None] + 1e-9)
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(curve, axis=0).T))]
    off = amp * np.sin(s / rng.uniform(25, 70) + rng.uniform(0, 2 * np.pi))
    return curve + n * off[:, None]


def track_layer(c, ch, lon, lat, nation, link, lw=(0.35, 0.65), alpha=0.16, seed=17):
    """RGBA layer with every nation's tracks as pen strokes, clipped to the chart.

    Each unbroken stretch of a logbook is one smooth stroke through its logged
    positions. Light ink, so routes build up where many ships overlap and a
    lone track stays faint. Stroke width varies a little per stroke (decoration).
    """
    rng = np.random.default_rng(seed)
    pts = np.c_[ch.px(lon), ch.py(lat)]
    cols = dict(zip(NATIONS, c.theme.highlights))
    strokes = {k: [] for k in NATIONS + [""]}
    for a, b in runs(link):
        k = nation[a] if nation[a] in cols else ""
        strokes[k].append(wobble(catmull_rom(pts[a:b]), rng))

    def draw(ax):
        # biggest fleets first, so the small ones stay visible on top
        for k in NATIONS + [""]:
            clip_to(ax, ch, ax.add_collection(LineCollection(
                strokes[k], colors=cols.get(k, c.theme.mark), alpha=alpha,
                linewidths=rng.uniform(*lw, len(strokes[k])), capstyle="round",
                joinstyle="round")))
    sharp = fx.layer(c.W, c.H, DPI, draw)
    # a little ink bleeds into the paper around each stroke
    bleed = fx.blur(sharp, 1.2)
    bleed[..., 3] *= 0.6
    return sharp, bleed


def paper(c, seed=6):
    """Aged-paper page: soft stains and darker edges. Decoration only."""
    rng = np.random.default_rng(seed)
    img = c.gradient((c.theme.bg,))
    blot = fx.blur(rng.random((c.H, c.W, 1)).repeat(3, 2), 90)
    blot = (blot - blot.mean()) / (blot.std() + 1e-9)
    img = img * (1 - 0.012 * np.abs(blot))      # stains only darken
    fine = rng.normal(0, 0.012, (c.H, c.W, 1))
    y, x = np.mgrid[0:c.H, 0:c.W]
    edge = np.hypot((x - c.W / 2) / (c.W * 0.62), (y - c.H / 2) / (c.H * 0.62)) ** 4
    img = img * (1 + fine) * (1 - 0.10 * edge[..., None]) * np.array([1, 0.985, 0.95]) ** edge[..., None]
    return np.clip(img, 0, 1)


def chart_layer(c, ch):
    """Old-chart furniture in ink: graticule, tropics, rhumb lines, neatline, rose."""
    ink = c.theme.ink
    lats = [a for a in range(-60, 90, 10) if LAT_SOUTH < a < ch.lat_north]

    def draw(ax):
        for lon in range(-90, LON[1] + 1, 10):
            ax.plot([ch.px(lon)] * 2, [ch.top, ch.bottom], color=ink, lw=0.35, alpha=0.22)
        for lat in lats:
            ax.plot([ch.left, ch.right], [ch.py(lat)] * 2, color=ink, lw=0.35, alpha=0.22)
        # labels sit where no track crosses them
        for lat, name, side in ((23.44, "Tropic of Cancer", 1), (0, "Equator", 1),
                                (-23.44, "Tropic of Capricorn", 0), (-66.56, "Antarctic Circle", 1)):
            y = ch.py(lat)
            ax.plot([ch.left, ch.right], [y, y], color=ink, lw=0.8 if lat == 0 else 0.6,
                    alpha=0.45, ls="-" if lat == 0 else (0, (6, 4)))
            ax.text(ch.right - 14 if side else ch.left + 14, y - 6, name, fontproperties=font("note"),
                    fontsize=pt(15, DPI), color=ink, alpha=0.65, ha="right" if side else "left")
        cx, cy = ch.xy(ROSE[1], ROSE[0])
        for k in range(32):
            a = np.radians(k * 360 / 32)
            clip_to(ax, ch, ax.plot([cx, cx + 3000 * np.sin(a)], [cy, cy - 3000 * np.cos(a)],
                                    color=ink, lw=0.4, alpha=0.18)[0])
        neatline(ax, ch, ink, lats)
        rose(ax, cx, cy, 92, ink, c.theme.accent, c.theme.bg)
    return fx.layer(c.W, c.H, DPI, draw)


def neatline(ax, ch, ink, lats, w=9):
    """Double border with alternating black/white degree bars, every 10 degrees."""
    l, t, r, b = ch.left, ch.top, ch.right, ch.bottom
    for d in (0, w):
        ax.add_patch(Rectangle((l - d, t - d), r - l + 2 * d, b - t + 2 * d, fill=False,
                               ec=ink, lw=0.8))
    lons = list(range(-90, LON[1] + 1, 10))
    for i, (a0, a1) in enumerate(zip([LON[0]] + lons, lons + [LON[1]])):
        if i % 2 == 0:
            for y in (t - w, b):
                ax.add_patch(Rectangle((ch.px(a0), y), ch.px(a1) - ch.px(a0), w, color=ink, lw=0))
    for i, (a0, a1) in enumerate(zip([LAT_SOUTH] + lats, lats + [ch.lat_north])):
        if i % 2 == 0:
            for x in (l - w, r):
                ax.add_patch(Rectangle((x, ch.py(a1)), w, ch.py(a0) - ch.py(a1), color=ink, lw=0))


def rose(ax, cx, cy, R, ink, accent, paper_col):
    """A 16-point compass rose; north is the top of the chart."""
    ax.add_patch(Circle((cx, cy), R * 1.08, fc=paper_col, ec=ink, lw=0.8))
    ax.add_patch(Circle((cx, cy), R * 1.0, fill=False, ec=ink, lw=0.4))
    for n, (length, width) in ((16, (0.55, 0.06)), (8, (0.75, 0.10)), (4, (1.0, 0.14))):
        for k in range(n):
            a = np.radians(k * 360 / n)
            tip = (cx + R * length * np.sin(a), cy - R * length * np.cos(a))
            for side, shade in ((-1, ink), (1, paper_col)):
                b = a + side * np.pi / 2
                base = (cx + R * width * np.sin(b), cy - R * width * np.cos(b))
                ax.add_patch(Polygon([(cx, cy), base, tip], closed=True, fc=shade, ec=ink, lw=0.5))
    ax.add_patch(Circle((cx, cy), R * 0.05, fc=accent, ec=ink, lw=0.5))
    ax.text(cx, cy - R * 1.2, "N", fontproperties=font("display"), fontsize=pt(26, DPI),
            color=ink, ha="center", va="baseline")


def halo(c, w=4):
    return [patheffects.withStroke(linewidth=w, foreground=c.theme.bg)]


def note_layer(c, ch):
    """A ring on each quote's logged position and a hairline to its text."""
    ink = c.theme.ink

    def draw(ax):
        for *_, lat, lon, text, (tlon, tlat) in NOTES:
            x, y = ch.xy(lat, lon)
            tx, ty = ch.xy(tlat, tlon)
            # meet the text block's left edge at the height nearest the ring
            top, bottom = ty - NOTE_PX, ty + NOTE_PX * 1.15 * text.count("\n") + 25
            ax.add_patch(Circle((x, y), 5, fc="none", ec=c.theme.bg, lw=3.2))
            ax.add_patch(Circle((x, y), 5, fc="none", ec=ink, lw=1.1))
            ax.plot([x, tx - 8], [y, np.clip(y, top, bottom)], color=ink, lw=0.6, alpha=0.7)
    return fx.layer(c.W, c.H, DPI, draw)


def say(c, x, y, s, face, px, color=None, **kw):
    """Canvas text at a size off the type scale."""
    return c.fig.text(c.fx(x), c.fy(y), s, fontproperties=font(face), fontsize=pt(px, DPI),
                      color=color or c.theme.ink, **kw)


def note_text(c, ch):
    for when, ship, who, _lat, _lon, text, (tlon, tlat) in NOTES:
        tx, ty = ch.xy(tlat, tlon)              # first line's baseline
        last = ty + NOTE_PX * 1.15 * text.count("\n")
        # matplotlib puts a multi-line block's last line on the baseline
        say(c, tx, last, text, "note", NOTE_PX, linespacing=1.15, va="baseline",
            path_effects=halo(c))
        below = last + 21
        say(c, tx, below, f"{ship} · {who} · {when}", "sans", 13, c.theme.muted,
            path_effects=halo(c, 3))


def key(c, ch):
    """Nation key in the empty far south-west corner of the chart."""
    x0, y0 = ch.left + 26, ch.bottom - 70
    for i, (k, col) in enumerate(zip(NATIONS, c.theme.highlights)):
        x, y = x0 + (i % 2) * 120, y0 + (i // 2) * 30
        c.rule(x, x + 26, y - 6, color=col, lw=3)
        c.text(x + 36, y, k.title(), role="label", path_effects=halo(c))


def render(fmt, data, path, quotes=True):
    c = Canvas(fmt, THEME)
    lon, lat, nation, book, day = data
    link = links(lon, lat, book, day)
    ch = Chart(INSET, INSET, c.W - INSET, c.footer_top - 20)
    page = paper(c)
    page = fx.over(page, chart_layer(c, ch))
    sharp, bleed = track_layer(c, ch, lon, lat, nation, link)
    page = fx.over(fx.over(page, bleed), sharp)
    if quotes:
        page = fx.over(page, note_layer(c, ch))
    c.backdrop(page)
    c.header(TITLE, SUBTITLE, halo=halo(c, 5))
    if quotes:
        note_text(c, ch)
    key(c, ch)
    c.footer(SOURCE)
    return c.save(path)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "output"
    data = load_positions()
    # slide 1: the chart alone; slide 2: the same chart with logbook notes
    for fmt in ("instagram", "x_portrait"):
        print(render(fmt, data, out / f"ships_{fmt}.png", quotes=False))
        print(render(fmt, data, out / f"ships_{fmt}_notes.png"))


if __name__ == "__main__":
    main()
