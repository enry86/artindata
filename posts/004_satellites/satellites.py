"""Above us, right now: every active satellite at one instant.

Positions come from CelesTrak's orbital elements (SGP4), all propagated to
the same moment. The big picture is the low-orbit shell, hugging the planet at
true scale; the circle on the right shows the whole picture to scale, where
the geostationary ring floats 36,000 km up and the Earth is a dot.

    python fetch_data.py    # once, to refresh data/
    python satellites.py    # writes output/*.png
"""
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.colors
import numpy as np
import pandas as pd
import matplotlib.patheffects as pe
from scipy.ndimage import gaussian_filter1d
from matplotlib.patches import Circle
from sgp4 import omm
from sgp4.api import Satrec, jday
from sgp4.propagation import gstime

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
from dataviz_style import Canvas, THEMES, font, pt, DPI  # noqa: E402
from dataviz_style import effects as fx  # noqa: E402
from dataviz_style import globe  # noqa: E402

THEME = THEMES["orbit"]
SWARM, OTHER = THEME.highlights            # Starlink: ivory. Every other satellite: coral red
LIMB = "#6FE3C0"                           # the Earth's atmospheric glow
EARTH = dict(dark="#031210", light="#0B3A33", land="#1F6D5D", rim="#2F9C84", rim_strength=0.8,
             land_strength=0.55, sun=(-0.35, 0.40, 0.85))
SOURCE = "Data: CelesTrak (orbits), SGP4 · public domain"

EARTH_KM = 6371.0
LEO_KM = 2500.0                            # below this altitude: the big picture
FOV_KM = 46000.0                           # half-width of the to-scale circle
CAM_LON, CAM_ELEV = 205.0, 22.0            # the point on Earth facing us, degrees (the Pacific, so the ISS is in view)

TRAIL_BIG, TRAIL_SMALL = 30.0, 240.0     # seconds of travel the streaks show (low orbit; to-scale view)

# ---------------------------------------------------------------- data
DATA = HERE / "data"


def read_snapshot():
    """UTC moment at which every satellite is placed: when the elements were downloaded."""
    f = DATA / "snapshot.txt"
    t = datetime.fromisoformat(f.read_text().strip()) if f.exists() else datetime(2026, 10, 15, 20, 0)
    return t


SNAP = read_snapshot()
SNAPSHOT = (SNAP.year, SNAP.month, SNAP.day, SNAP.hour, SNAP.minute, 0.0)


def load_elements():
    """Orbital elements of the active satellites. Falls back to the union of
    CelesTrak's group files if the single 'active' file was not downloadable."""
    f = DATA / "gp_active.json"
    if f.exists():
        try:
            return list(json.load(open(f))), "active"
        except json.JSONDecodeError:
            pass
    recs = {}
    for g in glob.glob(str(DATA / "groups" / "*.json")):
        for r in json.load(open(g)):
            recs[r["NORAD_CAT_ID"]] = r
    return list(recs.values()), "groups"


def propagate(recs):
    jd, fr = jday(*SNAPSHOT)
    rows = []
    for r in recs:
        s = Satrec()
        omm.initialize(s, r)
        err, pos, vel = s.sgp4(jd, fr)
        if err == 0 and np.all(np.isfinite(pos)):
            rows.append((r["NORAD_CAT_ID"], r["OBJECT_NAME"], *pos, *vel))
    sats = pd.DataFrame(rows, columns=["id", "name", "x", "y", "z", "vx", "vy", "vz"])
    sats["alt"] = np.linalg.norm(sats[["x", "y", "z"]].values, axis=1) - EARTH_KM
    sats["starlink"] = sats.name.str.startswith("STARLINK")
    cat = pd.read_csv(DATA / "satcat.csv", usecols=["NORAD_CAT_ID", "LAUNCH_DATE"], low_memory=False)
    sats = sats.merge(cat.rename(columns={"NORAD_CAT_ID": "id"}), on="id", how="left")
    sats["launch_year"] = pd.to_datetime(sats.LAUNCH_DATE).dt.year
    return sats, gstime(sum(jday(*SNAPSHOT)))


ELEMENTS, SOURCE_KIND = load_elements()
sats, GMST = propagate(ELEMENTS)
P = sats[["x", "y", "z"]].values
N = len(sats)
N_STARLINK = int(sats.starlink.sum())
PCT_STARLINK = round(100 * N_STARLINK / N)
PCT_NEW = round(100 * (sats.launch_year >= 2025).mean())
N_LEO = int((sats.alt < LEO_KM).sum())


# ---------------------------------------------------------------- the camera
def camera():
    """Orthographic camera above (CAM_ELEV, CAM_LON) on the rotating Earth,
    expressed in the inertial frame the satellites are in. North is up."""
    a = np.radians(CAM_LON) + GMST
    e = np.radians(CAM_ELEV)
    d = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    x = np.cross([0, 0, 1.0], d)
    x /= np.linalg.norm(x)
    return x, np.cross(d, x), d


CX, CY, CD = camera()
V = sats[["vx", "vy", "vz"]].values         # km/s, same inertial frame
VX, VY = V @ CX, V @ CY                     # velocity on the screen, km/s
X, Y, Z = P @ CX, P @ CY, P @ CD            # km: right, up, towards the viewer


class View:
    """Satellites at `scale` px per km around (cx, cy) px."""

    def __init__(self, cx, cy, scale, sel, trail_s=0.0):
        self.cx, self.cy, self.scale, self.trail_s = cx, cy, scale, trail_s
        self.px = cx + scale * X
        self.py = cy - scale * Y
        self.sel = sel
        self.near = sel & (Z >= 0)
        self.far = sel & (Z < 0)

    def draw(self, ax, which, size, alpha=1.0):
        for kind, color in ((True, SWARM), (False, OTHER)):
            k = which & (sats.starlink.values == kind)
            if self.trail_s:
                self.streaks(ax, k, color, size, alpha)
            ax.scatter(self.px[k], self.py[k], s=pt(2 * size, DPI) ** 2, color=color, alpha=alpha, lw=0, zorder=5)


def _streaks(self, ax, k, color, size, alpha, steps=6):
    """Where each satellite has just been: a tail along its velocity, fading away from it.
    Length = speed x trail_s, so a faster satellite leaves a longer streak."""
    from matplotlib.collections import LineCollection
    idx = np.flatnonzero(k)
    t = np.linspace(0, self.trail_s, steps + 1)
    xs = self.px[idx, None] - self.scale * VX[idx, None] * t
    ys = self.py[idx, None] + self.scale * VY[idx, None] * t
    pts = np.stack([xs, ys], -1)
    segs = np.concatenate([pts[:, :-1, None], pts[:, 1:, None]], 2).reshape(-1, 2, 2)
    fade = np.tile(np.linspace(0.5, 0.0, steps), len(idx)) * alpha
    rgba = np.zeros((len(fade), 4)); rgba[:, :3] = matplotlib.colors.to_rgb(color); rgba[:, 3] = fade
    ax.add_collection(LineCollection(segs, colors=rgba, linewidths=pt(1.1 * size, DPI), capstyle="round", zorder=4))


View.streaks = _streaks


def halo(px, color=THEME.bg, alpha=0.85):
    return [pe.Stroke(linewidth=pt(px, DPI), foreground=color, alpha=alpha), pe.Normal()]


def lit(c, img, view, which, size, levels=((14, 0.5, 3.0), (5, 0.8, 1.8), (1.6, 0.9, 1.2))):
    for radius, strength, scale in levels:
        lay = fx.layer(c.W, c.H, DPI, lambda a, s=scale: view.draw(a, which, size * s, 0.85))
        img = fx.glow(img, lay, radius, strength)
    return img


def disc(img, cx, cy, r, color, alpha=1.0):
    H, W, _ = img.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    a = np.clip((r - np.hypot(xx - cx, yy - cy)), 0, 1)[..., None] * alpha
    from matplotlib.colors import to_rgb
    return img * (1 - a) + np.array(to_rgb(color)) * a


# ---------------------------------------------------------------- scene
def scene(c, main, inset, mask):
    """main: the Earth (cx, cy, R px). inset: the to-scale view (cx, cy, R px = FOV_KM)."""
    img = globe.paint_stars(c, c.gradient())
    big = View(main["cx"], main["cy"], main["R"] / EARTH_KM, sats.alt.values < LEO_KM, TRAIL_BIG)
    # The to-scale view shows everything above low orbit (a skin 7% of the Earth's radius thick,
    # invisible at this scale; a ring of light round the little Earth stands for it), inside an
    # invisible ellipse that keeps the far outliers away from the text.
    scale = inset["R"] / FOV_KM
    inside = (X * scale / inset["a"]) ** 2 + (Y * scale / inset["b"]) ** 2 < 1
    small = View(inset["cx"], inset["cy"], scale, inside & (sats.alt.values >= LEO_KM), TRAIL_SMALL)

    e_r = EARTH_KM * scale
    img = globe.paint_sphere(img, inset["cx"], inset["cy"], e_r, CAM_ELEV, CAM_LON, mask, **EARTH)
    skin = fx.layer(c.W, c.H, DPI, lambda a: a.add_patch(Circle((inset["cx"], inset["cy"]), e_r * 1.07, fc="none",
                                                                  ec=SWARM, lw=pt(1.6, DPI), alpha=0.9)))
    img = fx.glow(fx.over(img, skin), skin, 3, 0.9)
    img = lit(c, img, small, small.sel, 1.0, levels=((10, 0.55, 2.4), (3.5, 0.85, 1.6), (1.2, 0.9, 1.1)))

    # the low-orbit shell round the big Earth: far side first, then the ball, then the near side
    img = lit(c, img, big, big.far & big.sel, 1.0)
    img = globe.paint_sphere(img, main["cx"], main["cy"], main["R"], CAM_ELEV, CAM_LON, mask, **EARTH)
    limb = fx.layer(c.W, c.H, DPI, lambda a: a.add_patch(Circle((main["cx"], main["cy"]), main["R"] + 0.5, fc="none",
                                                                  ec=LIMB, lw=pt(1.4, DPI), alpha=0.7)))
    img = fx.glow(img, limb, 4, 0.9)
    img = fx.glow(img, limb, 14, 0.5)
    img = lit(c, img, big, big.near & big.sel, 1.0)

    ax = c.backdrop(image=img)
    big.draw(ax, big.near & big.sel, 1.0, 0.9)
    small.draw(ax, small.sel, 1.0, 1.0)
    iss_mark(ax, big)
    # the zoom: two faint lines from the little Earth to the big one
    th = np.arctan2(inset["cy"] - main["cy"], inset["cx"] - main["cx"])
    for s in (-0.5, 0.5):
        ax.plot([inset["cx"], main["cx"] + main["R"] * np.cos(th + s)],
                [inset["cy"], main["cy"] + main["R"] * np.sin(th + s)],
                color=THEME.muted, lw=0.8, alpha=0.28, zorder=2)
    return ax, big, small


def iss_mark(ax, view):
    """Bright dot and label on the International Space Station (NORAD 25544)."""
    i = int(np.flatnonzero(sats.id.values == 25544)[0])
    x, y, far = view.px[i], view.py[i], Z[i] < 0
    ax.scatter([x], [y], s=pt(9, DPI) ** 2, color=THEME.ink, lw=0, zorder=9)
    lab = "ISS" + (" · behind the Earth" if far else "")
    ax.text(x + 14, y - 4, lab, fontproperties=font("sans"), fontsize=pt(17, DPI), color=THEME.ink,
            ha="left", va="center", path_effects=halo(5), zorder=9)
    print(f"ISS at {sats.alt.values[i]:.0f} km, {'far' if far else 'near'} side, px {x:.0f},{y:.0f}")


# ---------------------------------------------------------------- altitude plot
ALT_LO, ALT_HI = 250.0, 45000.0


def altitude_curves(bins=150):
    """Satellites per slice of altitude (log scale), Starlink and the rest, lightly smoothed."""
    edges = np.linspace(np.log10(ALT_LO), np.log10(ALT_HI), bins + 1)
    out = {}
    for name, sel in (("starlink", sats.starlink.values), ("other", ~sats.starlink.values)):
        h, _ = np.histogram(np.log10(sats.alt.values[sel].clip(ALT_LO, ALT_HI - 1)), edges)
        out[name] = gaussian_filter1d(h.astype(float), 1.2)
    return (edges[:-1] + edges[1:]) / 2, out


def peaks():
    """Named clusters read off the data: (label, altitude km, count)."""
    nav = sats.name.str.contains("GPS|NAVSTAR|GALILEO|GLONASS|BEIDOU", regex=True) & sats.alt.between(18000, 25000)
    geo = sats.alt.between(35000, 36600)
    groups = (("Starlink", sats.starlink), ("OneWeb", sats.name.str.startswith("ONEWEB")),
              ("GPS, Galileo, ...", nav), ("Geostationary", geo))
    return [(label, float(sats.alt[m].median()), int(m.sum())) for label, m in groups if m.sum() > 20]


def altitude_plot(c, ax, x0, x1, y_base, h):
    """Line plot: how many satellites orbit at each altitude. Height is the square
    root of the count per slice, so small groups stay visible next to Starlink."""
    pos = lambda km: x0 + (np.log10(km) - np.log10(ALT_LO)) / (np.log10(ALT_HI) - np.log10(ALT_LO)) * (x1 - x0)
    mid, curves = altitude_curves()
    top = np.sqrt(max(v.max() for v in curves.values()))
    xs = pos(10 ** mid)

    def draw(a, width, alpha):
        for name, col in (("other", OTHER), ("starlink", SWARM)):
            ys = y_base - h * np.sqrt(curves[name]) / top
            a.fill_between(xs, y_base, ys, color=col, alpha=alpha * 0.18, lw=0)
            a.plot(xs, ys, color=col, lw=pt(width, DPI), alpha=alpha, solid_capstyle="round")
    ax.fill_between([x0, x1], y_base, y_base, color="none")
    draw(ax, 1.8, 1.0)
    ax.plot([x0, x1], [y_base, y_base], color=THEME.guide, lw=1, zorder=1)
    for km, lab in ((300, "300 km"), (1000, "1,000"), (3000, "3,000"), (10000, "10,000"), (30000, "30,000 km")):
        ax.plot([pos(km)] * 2, [y_base, y_base + 6], color=THEME.muted, lw=1, alpha=0.7)
        c.text(pos(km), y_base + 26, lab, role="small", color=THEME.muted, ha="center")
    # the ISS: one object, drawn as a ring on the curve at its altitude
    iss = float(sats.alt[sats.id == 25544].iloc[0])
    i = int(np.argmin(abs(mid - np.log10(iss))))
    yy = y_base - h * np.sqrt(curves["starlink"][i]) / top
    ax.scatter([pos(iss)], [yy], s=pt(8, DPI) ** 2, color=THEME.ink, lw=0, zorder=9)
    ax.text(pos(iss) - 12, yy - 2, f"ISS · {iss:,.0f} km", fontproperties=font("sans"), fontsize=pt(15, DPI),
            color=THEME.ink, ha="right", va="center", path_effects=halo(4), zorder=9)
    for label, km, n in peaks():
        i = int(np.argmin(abs(mid - np.log10(km))))
        yy = y_base - h * np.sqrt(max(curves["starlink"][i], curves["other"][i])) / top
        ax.plot([pos(km)] * 2, [yy - 4, yy - 16], color=THEME.muted, lw=0.8, alpha=0.7)
        ax.text(pos(km), yy - 22, f"{label} · {n:,}", fontproperties=font("sans"), fontsize=pt(15, DPI),
                color=THEME.ink, ha="left" if km < 2000 else "center", va="bottom", path_effects=halo(4), zorder=7)


def notes(c, ax, main, inset):
    # caption of the to-scale view, right-aligned under its ring
    x = c.right
    c.text(x, inset["cy"] + inset["b"] + 12, "To scale", role="note", ha="right")
    c.text(x, inset["cy"] + inset["b"] + 38, "the geostationary ring floats 36,000 km up",
           role="small", color=THEME.muted, ha="right")
    # key
    x0, y0 = main["cx"] + main["R"] + 52, main["cy"] + 90
    n_other = N - N_STARLINK
    for i, (color, label, n) in enumerate(((SWARM, "Starlink", N_STARLINK), (OTHER, "every other satellite", n_other))):
        ax.scatter([x0], [y0 + i * 40], s=pt(11, DPI) ** 2, color=color, lw=0, zorder=6)
        c.text(x0 + 22, y0 + 6 + i * 40, f"{label}  ·  {n:,}", role="label", color=THEME.ink)
    y = y0 + 2 * 40 + 6
    c.text(x0 - 6, y, "Tails show the way each one came from,", role="small", color=THEME.muted)
    c.text(x0 - 6, y + 26, f"its last {TRAIL_BIG:.0f} s ({TRAIL_SMALL / 60:.0f} min in the to-scale view)", role="small",
           color=THEME.muted)


def share_words(pct):
    return "Two in three" if 63 <= pct <= 70 else f"{pct}%"


TITLE = "Above us, right now"
WHEN = f"{SNAP:%H:%M} UTC on {SNAP.day} {SNAP:%B %Y}"
SUBTITLE = (f"All {N:,} active satellites, placed where they were at {SNAP:%H:%M} UTC\n"
            f"on {SNAP.day} {SNAP:%B %Y}. {share_words(PCT_STARLINK)} are Starlink; {PCT_NEW}% launched since 2025.")


def export(fmt, out):
    c = Canvas(fmt, THEME)
    main = dict(cx=410, cy=785, R=245)
    inset = dict(cx=700, cy=385, R=300, a=300, b=150)
    ax, big, small = scene(c, main, inset, globe.land_mask(DATA / "ne_110m_land.geojson"))
    c.header(TITLE, SUBTITLE, align="left")
    notes(c, ax, main, inset)
    c.text(c.right, c.footer_top - 170, "SATELLITES BY ALTITUDE", role="small", color=THEME.muted, ha="right")
    altitude_plot(c, ax, c.left, c.right, c.footer_top - 52, 100)
    c.footer(SOURCE)
    return c.save(HERE / "output" / out)


if __name__ == "__main__":
    print(f"{N:,} satellites ({SOURCE_KIND} elements), {N_STARLINK:,} Starlink ({PCT_STARLINK}%), "
          f"{N_LEO:,} in low orbit, {PCT_NEW}% launched since 2025")
    for fmt, name in (("instagram", "instagram"), ("x_portrait", "x")):
        print("wrote", export(fmt, f"satellites_{name}.png").relative_to(HERE))
