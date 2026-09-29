"""Raster effects for background art: offscreen layers, blur, glow, light.

Images are H x W x 3 float arrays in 0..1 (layers are H x W x 4 RGBA),
in the same pixel space as Canvas (origin top-left).
"""
import numpy as np
from scipy.ndimage import gaussian_filter
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure


def layer(W, H, dpi, draw):
    """Render `draw(ax)` (px coords, y down) into a transparent RGBA array."""
    fig = Figure(figsize=(W / dpi, H / dpi), dpi=dpi)
    FigureCanvasAgg(fig)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.set_axis_off(); ax.patch.set_alpha(0)
    draw(ax)
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba(), dtype=float) / 255


def _blur(arr, sigma):
    # blur across rows and columns only, never across channels
    return gaussian_filter(arr, sigma=(sigma, sigma, 0), mode="nearest")


def blur(img, radius):
    """Gaussian blur (sigma = `radius` px) of an RGB or RGBA float array.

    RGBA is blurred premultiplied: transparent pixels carry arbitrary colour
    (Agg stores them as white), which would otherwise bleed into the edges
    as a pale fringe.
    """
    if img.shape[2] == 3:
        return np.clip(_blur(img, radius), 0, 1)
    a = img[..., 3:4]
    rgb_p = _blur(img[..., :3] * a, radius)
    a_b = _blur(a, radius)
    rgb = np.where(a_b > 1e-6, rgb_p / np.maximum(a_b, 1e-6), 0)
    return np.concatenate([np.clip(rgb, 0, 1), np.clip(a_b, 0, 1)], axis=2)


def over(base, rgba):
    """Alpha-composite an RGBA layer onto an RGB image."""
    a = rgba[..., 3:4]
    return base * (1 - a) + rgba[..., :3] * a


def screen(base, light):
    """Screen blend: brightens, never darkens -- how light adds up."""
    return 1 - (1 - base) * (1 - np.clip(light, 0, 1))


def glow(base, rgba, radius, strength):
    """Add a blurred, premultiplied copy of `rgba` as light."""
    lit = rgba[..., :3] * rgba[..., 3:4]
    return screen(base, blur(lit, radius) * strength)


def radial_light(base, cx, cy, sx, sy, color, strength):
    """A soft elliptical pool of light centred at (cx, cy) px."""
    H, W, _ = base.shape
    y, x = np.mgrid[0:H, 0:W]
    fall = np.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))
    return screen(base, fall[..., None] * np.array(to_rgb(color)) * strength)
