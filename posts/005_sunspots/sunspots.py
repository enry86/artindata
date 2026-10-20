"""The restless Sun: every year of sunspots since 1749, one disc per year.

Each disc is the Sun in that year, with one dark spot for every 10 units of
that year's mean sunspot number (SILSO). The big disc is 1957, the busiest
year on record; the two small ones are the quietest year (1810) and the most
recent full year (2025). The grid below is all 278 years in calendar order.

    python fetch_data.py    # once, to refresh data/
    python sunspots.py      # writes output/*.png
"""
import csv
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from matplotlib.colors import to_rgb
from matplotlib.patches import Circle

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
from dataviz_style import Canvas, THEMES, TYPE_SCALE, font, pt, DPI  # noqa: E402
from dataviz_style import effects as fx  # noqa: E402

THEME = THEMES["solar"]
SOURCE = "Data: SILSO, Royal Observatory of Belgium · CC BY-NC 4.0"
TITLE = "The restless Sun"
SUBTITLE = "One disc per year since 1749, one spot per 10 on the sunspot number.\nBusy years are pitted and bright, quiet ones clean and dim."
UNIT = 10.0                    # sunspot-number units per drawn spot
COLS = 20                      # discs per row: two decades
HERO, QUIET, LATEST = 1957, 1810, 2025
BRIGHTNESS_SWING = 0.30        # how much dimmer a spotless disc is than the busiest year's
HALO_MIN = 0.0                 # glow of a spotless year, as a share of the busiest year's

# ---------------------------------------------------------------- data
def load_years():
    """{year: (annual mean of the monthly sunspot number, months available)}"""
    by = {}
    for r in csv.reader(open(HERE / "data" / "SN_m_tot_V2.0.csv"), delimiter=";"):
        by.setdefault(int(r[0]), []).append(float(r[3]))
    return {y: (sum(v) / len(v), len(v)) for y, v in sorted(by.items())}


def spot_count(mean):
    return int(mean / UNIT + 0.5)


# ---------------------------------------------------------------- a disc
RAMP_I = [0.30, 0.55, 0.78, 0.92, 1.00]
RAMP_C = np.array([to_rgb(c) for c in ("#8A2E0B", "#D9701F", "#F6A02F", "#FFC966", "#FFF1C9")])
UMBRA = np.array(to_rgb("#140603"))
PEN_TINT = np.array([0.55, 1.0, 1.40])      # the penumbra darkens green/blue more: warm brown, not grey
LIMB_DARKENING = 0.70
R_UMBRA, R_PENUMBRA = 0.065, 0.150      # in units of the disc radius
BAND = (4.0, 34.0)                      # latitude band where spots appear, degrees
MAX_LON = 78.0


def place_spots(year, count):
    """Latitude/longitude (radians) of `count` spots. The COUNT is the data;
    positions are random (fixed seed per year) inside the real latitude bands,
    kept apart so they stay countable (loose enough to clump a little, as real groups do). Never drops a spot."""
    rng = np.random.default_rng(np.random.SeedSequence([year, 5]))
    pts, sep, tries = [], 0.22, 0
    while len(pts) < count:
        tries += 1
        if tries % 300 == 0:
            sep *= 0.9
        lat = np.radians(rng.choice([-1, 1]) * rng.uniform(*BAND))
        lon = np.radians(rng.uniform(-MAX_LON, MAX_LON))
        xy = (np.cos(lat) * np.sin(lon), np.sin(lat))
        if all((xy[0] - a) ** 2 + (xy[1] - b) ** 2 > sep ** 2 for a, b, _, _ in pts):
            pts.append((xy[0], xy[1], lat, lon))
    assert len(pts) == count
    return pts


def ramp(I):
    return np.stack([np.interp(I, RAMP_I, RAMP_C[:, k]) for k in range(3)], axis=-1)


def render_disc(R, spots, cx, cy, seed=0, ss=3, heat=1.0):
    """RGBA patch of one solar disc of radius R px centred at (cx, cy) px.
    Returns (patch, x0, y0): the top-left pixel of the patch on the page."""
    pad = 2
    x0, y0 = int(np.floor(cx - R)) - pad, int(np.floor(cy - R)) - pad
    n = int(np.ceil(2 * R)) + 2 * pad + 2
    g = (np.arange(n * ss) + 0.5) / ss
    X = (x0 + g[None, :] - cx) / R
    Y = -(y0 + g[:, None] - cy) / R
    r2 = X ** 2 + Y ** 2
    inside = r2 < 1
    mu = np.sqrt(np.clip(1 - r2, 0, 1))
    I = 1 - LIMB_DARKENING * (1 - mu)
    # faint granulation: decoration, same texture on every disc
    noise = gaussian_filter(np.random.default_rng(seed).normal(size=I.shape), 0.035 * R * ss)
    I = I * (1 + 0.03 * noise / max(noise.std(), 1e-9))
    I = I * (1 - BRIGHTNESS_SWING * (1 - heat))          # quiet years burn dimmer
    rgb = ramp(np.clip(I, 0.30, 1.0))
    for sx, sy, lat, lon in spots:
        mus = np.cos(lat) * np.cos(lon)                  # foreshortening towards the limb
        dx, dy = X - sx, Y - sy
        rr = max(np.hypot(sx, sy), 1e-6)
        er = (sx / rr, sy / rr) if rr > 1e-3 else (1.0, 0.0)
        d_rad = dx * er[0] + dy * er[1]
        d_tan = -dx * er[1] + dy * er[0]
        d = np.sqrt((d_rad / max(mus, 0.25)) ** 2 + d_tan ** 2)
        pen = np.clip((R_PENUMBRA - d) / (0.15 * R_PENUMBRA), 0, 1)
        umb = np.clip((R_UMBRA - d) / (0.15 * R_UMBRA), 0, 1)
        depth = 0.38 + 0.30 * (1 - np.clip(d / R_PENUMBRA, 0, 1))      # darker towards the umbra
        rgb = rgb * (1 - (pen * depth)[..., None] * PEN_TINT)
        rgb = rgb * (1 - umb[..., None]) + UMBRA * umb[..., None]
    alpha = np.clip((1 - np.sqrt(r2)) * R * ss, 0, 1)     # antialiased edge
    rgba = np.concatenate([rgb, alpha[..., None]], axis=2)
    rgba[..., :3] *= alpha[..., None]                      # premultiply for the block mean
    rgba = rgba.reshape(n, ss, n, ss, 4).mean(axis=(1, 3))
    a = rgba[..., 3:4]
    rgba[..., :3] = np.where(a > 1e-6, rgba[..., :3] / np.maximum(a, 1e-6), 0)
    return rgba, x0, y0


def stamp(layer, patch, x0, y0):
    """Paste an RGBA patch onto a full-page RGBA layer (no overlap expected)."""
    H, W = layer.shape[:2]
    h, w = patch.shape[:2]
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    p = patch[ya - y0:yb - y0, xa - x0:xb - x0]
    reg = layer[ya:yb, xa:xb]
    pa, la = p[..., 3:4], reg[..., 3:4]
    na = pa + la * (1 - pa)
    reg[..., :3] = (p[..., :3] * pa + reg[..., :3] * la * (1 - pa)) / np.maximum(na, 1e-9)
    reg[..., 3:4] = na


# ---------------------------------------------------------------- page
def render(fmt, out):
    years = load_years()
    c = Canvas(fmt, THEME)
    W, H = c.W, c.H

    # geometry
    gx0, gx1 = 130, c.right                           # the left strip carries the row labels
    cell = (gx1 - gx0) / COLS
    rows = -(-len(years) // COLS)
    gy0 = 598
    R_grid = cell * 0.46
    hero_c, R_hero = (W / 2, 376), 130
    side_R = 52
    left_c, right_c = (190, 376), (W - 190, 376)

    cells = {}
    for i, y in enumerate(years):
        cells[y] = (gx0 + (i % COLS + 0.5) * cell, gy0 + (i // COLS + 0.5) * cell)

    def disc_for(year, R, centre):
        mean, months = years[year]
        n = spot_count(mean)
        return render_disc(R, place_spots(year, n), centre[0], centre[1], seed=year, heat=heat_of(n)), n

    # The halo scales with the spot count (the same quantity the spots show), so
    # busy years glow and quiet years are dim. Glow layers carry that scaling.
    peak = max(spot_count(m) for m, _ in years.values())

    def heat_of(n):
        return (n / peak) ** 0.7

    def halo(n):
        return HALO_MIN + (1 - HALO_MIN) * (n / peak) ** 1.2

    grid_layer = np.zeros((H, W, 4)); grid_glow = np.zeros((H, W, 4))
    for y in years:
        (patch, x0, y0), n = disc_for(y, R_grid, cells[y])
        stamp(grid_layer, patch, x0, y0)
        g = patch.copy(); g[..., 3] *= halo(n)
        stamp(grid_glow, g, x0, y0)
    hero_layer = np.zeros((H, W, 4)); hero_glow = np.zeros((H, W, 4))
    counts = {}
    for year, R, centre in ((HERO, R_hero, hero_c), (QUIET, side_R, right_c),
                            (LATEST, side_R, left_c)):
        (patch, x0, y0), counts[year] = disc_for(year, R, centre)
        stamp(hero_layer, patch, x0, y0)
        g = patch.copy(); g[..., 3] *= halo(counts[year])
        stamp(hero_glow, g, x0, y0)

    key_y = c.footer_top - 20
    msg = f"1 spot = {int(UNIT)} on the sunspot number  ·  a row is 20 years, 1749 to 2026"
    t = c.text(0, 0, msg, role="label", color=THEME.muted)
    w = t.get_window_extent(c.fig.canvas.get_renderer()).width
    t.remove()
    x_start = (W - (w + 30)) / 2
    sample, sx0, sy0 = render_disc(10, [(0.0, 0.0, 0.0, 0.0)], x_start + 10, key_y - 5, seed=1)
    stamp(grid_layer, sample, sx0, sy0)

    img = c.gradient()
    # corona behind the big disc, and a lower warmth behind the grid
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot(xx - hero_c[0], yy - hero_c[1])
    corona = (0.50 * np.exp(-(r / (R_hero * 1.55)) ** 2) + 0.25 * np.exp(-(r / (R_hero * 3.2)) ** 2))[..., None]
    img = fx.screen(img, corona * np.array(to_rgb("#B24A12")))
    img = fx.glow(img, grid_glow, 7, 0.55)
    img = fx.glow(img, grid_glow, 16, 0.75)
    img = fx.glow(img, hero_glow, 46, 0.85)
    img = fx.glow(img, hero_glow, 14, 0.55)
    img = fx.over(img, grid_layer)
    img = fx.over(img, hero_layer)

    ax = c.backdrop(img)
    # rings in the grid: the three discs shown above
    for year in (HERO, QUIET, LATEST):
        cx, cy = cells[year]
        ax.add_patch(Circle((cx, cy), R_grid * 1.32, fill=False, ec=THEME.accent, lw=1.2, zorder=5))

    c.header(TITLE, SUBTITLE, align="center")

    # labels under the three big discs
    for year, (cx, cy), R, cap in ((LATEST, left_c, side_R, "last full year"),
                                   (HERO, hero_c, R_hero, "the busiest year"),
                                   (QUIET, right_c, side_R, "the quietest year")):
        base = hero_c[1] + R_hero + 38
        c.text(cx, base, str(year), role="note", ha="center")
        c.text(cx, base + 24, f"{cap}: {counts[year]} spot{'s' if counts[year] != 1 else ''}",
               role="label", color=THEME.muted, ha="center")

    # row labels: first year of every second row
    for i in range(0, rows, 2):
        y = list(years)[i * COLS]
        c.text(c.left, gy0 + (i + 0.5) * cell + 6, str(y), role="small", color=THEME.muted)
    # the last disc is a part-year
    last = list(years)[-1]
    cx, cy = cells[last]
    c.text(cx + cell * 0.75, cy - 3, "2026, to", role="small", color=THEME.muted)
    c.text(cx + cell * 0.75, cy + 14, "September", role="small", color=THEME.muted)

    c.text(x_start + 30, key_y, msg, role="label", color=THEME.muted)

    c.footer(SOURCE)
    return c.save(HERE / "output" / out)


if __name__ == "__main__":
    for fmt, name in (("instagram", "sunspots_instagram.png"), ("x_portrait", "sunspots_x_portrait.png")):
        print(render(fmt, name))
