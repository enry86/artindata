"""Brand assets for @artindata: profile pictures and vector masters.

Everything is drawn from dataviz_style/mark.py, so the avatar and the
footer signature never drift apart.

    python brand/make_brand.py    # writes brand/output/*
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from dataviz_style import THEMES, DPI, pt              # noqa: E402
from dataviz_style import effects as fx                # noqa: E402
from dataviz_style.mark import draw_mark               # noqa: E402

OUT = HERE / "output"
SIZE = 1080                 # square; both platforms crop it to a circle
MARK = 0.52                 # frame side as a share of the canvas (a square fits the circle up to ~0.6)


def px_axes(fig, W, H):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.set_axis_off()
    return ax


def mark_layer(theme, W, H, S):
    """The mark alone, as an RGBA layer (for glow and compositing)."""
    return fx.layer(W, H, DPI, lambda ax: draw_mark(ax, W / 2, H / 2, S, theme.ink,
                                                   theme.accent, lambda p: pt(p, DPI)))


def avatar(theme, name, glow=True):
    W = H = SIZE
    S = SIZE * MARK
    # background: the theme's sky, or its flat bg, as a smooth vertical ramp
    stops = theme.sky[1:3] if theme.sky else (theme.bg, theme.bg)
    cols = np.array([matplotlib.colors.to_rgb(c) for c in stops])
    t = np.linspace(0, 1, H)[:, None]
    img = np.broadcast_to((cols[0] + (cols[1] - cols[0]) * t)[:, None, :], (H, W, 3)).copy()

    layer = mark_layer(theme, W, H, S)
    if glow:
        # light only from the dab, not the frame: rebuild a dab-only layer
        dab = fx.layer(W, H, DPI, lambda ax: draw_mark(ax, W / 2, H / 2, S, (0, 0, 0, 0),
                                                      theme.accent, lambda p: pt(p, DPI)))
        img = fx.glow(img, dab, 40, 0.55)
        img = fx.glow(img, dab, 110, 0.35)
    img = fx.over(img, layer)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"avatar_{name}.png"
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)
    return path


def vector(theme, name):
    """Transparent SVG + PNG master of the mark alone."""
    S, pad = 400, 40
    W = H = S + 2 * pad
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
    fig.patch.set_alpha(0)
    draw_mark(px_axes(fig, W, H), W / 2, H / 2, S, theme.ink, theme.accent, lambda p: pt(p, DPI))
    for ext in ("svg", "png"):
        fig.savefig(OUT / f"mark_{name}.{ext}", dpi=DPI, transparent=True)
    plt.close(fig)


def preview(paths):
    """How the avatars look once cropped to a circle, at real display sizes."""
    sizes = (320, 110, 40)
    tile_w = sum(sizes) + 40 * len(sizes)
    sheet = Image.new("RGB", (tile_w, 360 * len(paths)), (230, 225, 216))
    for row, p in enumerate(paths):
        src = Image.open(p)
        x = 20
        for s in sizes:
            im = src.resize((s, s), Image.LANCZOS)
            mask = Image.new("L", (s, s), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, s - 1, s - 1), fill=255)
            sheet.paste(im, (x, row * 360 + (360 - s) // 2), mask)
            x += s + 40
    sheet.save(OUT / "preview_circle_crop.png")
    return OUT / "preview_circle_crop.png"


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    night = avatar(THEMES["sakura_night"], "night")
    cream = avatar(THEMES["botany"], "cream", glow=False)
    vector(THEMES["sakura_night"], "night")
    vector(THEMES["botany"], "cream")
    print("wrote", *(p.name for p in (night, cream, preview([night, cream]))))
