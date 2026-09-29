"""The @artindata signature mark: a painted point, hung in a frame.

The exact square frame is the data (rigour); the free brush dab inside is
the art. The frame takes the theme's ink, the dab its accent, so the mark
keeps its shape across posts while its colour follows the topic.

All geometry is in px (y down) in a box of side S centred at (cx, cy).
"""
import numpy as np
from matplotlib.patches import Polygon, Rectangle


def _bezier(p0, c, p1, n=24):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * np.asarray(p0) + 2 * (1 - t) * t * np.asarray(c) + t ** 2 * np.asarray(p1)


def dab(cx, cy, r, length, angle, bend=0.35):
    """Outline of a brush dab: a round head of radius r whose tail tapers to a
    point `length` px away at `angle` degrees (y down), sweeping by `bend` * r."""
    u = np.array([np.cos(np.radians(angle)), np.sin(np.radians(angle))])
    n = np.array([-u[1], u[0]])
    head = np.array([cx, cy])
    tip = head + u * length + n * bend * r
    side1 = _bezier(head + n * r, head + u * length * 0.45 + n * r * 0.75, tip)
    side2 = _bezier(tip, head + u * length * 0.4 - n * r * 0.55, head - n * r)
    back = [head + r * (np.cos(t) * -n + np.sin(t) * -u) for t in np.linspace(0, np.pi, 24)]
    return np.vstack([side1, side2, back])


def draw_mark(ax, cx, cy, S, ink, accent, lw_to_pt):
    """Draw the mark on a px-space axes. `lw_to_pt` converts px to points."""
    ax.add_patch(Rectangle((cx - S / 2, cy - S / 2), S, S, fill=False, ec=ink,
                           lw=lw_to_pt(S * 0.07), joinstyle="miter"))
    ax.add_patch(Polygon(dab(cx + S * 0.14, cy - S * 0.12, S * 0.16, S * 0.42, 135),
                         closed=True, color=accent, lw=0))
