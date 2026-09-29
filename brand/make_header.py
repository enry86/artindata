"""X header banner for @artindata (1500 x 500): luminous contour lines of a
smooth, seeded mathematical field -- abstract, drawn from no dataset, so no
data is implied. Colours are the night theme's diverging palette.

    python brand/make_header.py    # writes brand/output/header_x.png + preview
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from dataviz_style import THEMES, DPI, pt              # noqa: E402
from dataviz_style import effects as fx                # noqa: E402

TH = THEMES["sakura_night"]
W, H = 1500, 500
OUT = HERE / "output"
AVATAR = (120, 470, 115)          # (cx, cy, r) of the profile picture overlap, px
CMAP = LinearSegmentedColormap.from_list("div", [TH.diverging[2], TH.diverging[1], TH.diverging[0]])


def field(x, y, seed=4):
    """A smooth, seeded 'terrain': a few sine waves summed. Values ~ -1..1."""
    rng = np.random.default_rng(seed)
    f = np.zeros_like(x, dtype=float)
    for _ in range(6):
        k = rng.uniform(0.004, 0.012, 2) * rng.choice([-1, 1], 2)
        f += rng.uniform(0.4, 1) * np.sin(k[0] * x + k[1] * y + rng.uniform(0, 6.3))
    return f / np.abs(f).max()


def quiet(x, y):
    """0 inside the avatar zone, fading to 1 around it."""
    cx, cy, r = AVATAR
    d = np.hypot(x - cx, y - cy)
    return np.clip((d - r) / 140, 0, 1)


def sky():
    cols = np.array([to_rgb(c) for c in (TH.sky[1], TH.sky[3])])
    t = np.linspace(0, 1, H)[:, None]
    img = np.broadcast_to((cols[0] + (cols[1] - cols[0]) * t)[:, None, :], (H, W, 3)).copy()
    return fx.radial_light(img, W * 0.62, H * 0.45, 520, 220, "#5A4E96", 0.25)


def contours(ax):
    """Contour lines of the terrain, like a topographic map at night."""
    xs, ys = np.meshgrid(np.linspace(0, W, 600), np.linspace(0, H, 200))
    f = field(xs, ys)
    levels = np.linspace(-0.95, 0.95, 20)
    ax.contour(xs, ys, f, levels=levels, cmap=CMAP, linewidths=pt(1.6, DPI))


def render(draw, name):
    img = sky()
    art = fx.layer(W, H, DPI, draw)
    yy, xx = np.mgrid[0:H, 0:W]
    art[..., 3] *= quiet(xx, yy)                    # keep the avatar corner quiet
    img = fx.glow(img, art, 5, 0.6)
    img = fx.glow(img, art, 24, 0.45)
    img = fx.over(img, art)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)
    return path


def preview(path):
    """Overlay the real avatar and mobile crop guides, to check the layout."""
    im = Image.open(path).convert("RGB")
    av = Image.open(OUT / "avatar_night.png").resize((2 * AVATAR[2],) * 2, Image.LANCZOS)
    mask = Image.new("L", av.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, av.size[0] - 1, av.size[1] - 1), fill=255)
    im.paste(av, (AVATAR[0] - AVATAR[2], AVATAR[1] - AVATAR[2]), mask)
    d = ImageDraw.Draw(im)
    for y in (60, H - 60):                           # rough mobile crop band
        d.line([(0, y), (W, y)], fill=(255, 255, 255), width=1)
    return im


if __name__ == "__main__":
    path = render(contours, "header_x")
    preview(path).save(OUT / "preview_header.png")
    print("wrote", path.name, "preview_header.png")
