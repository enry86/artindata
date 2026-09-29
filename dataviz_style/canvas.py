"""Canvas: a figure at an exact export size with the fixed layout grid.

All positions are in pixels measured from the top-left corner of the
exported image, so layout code reads like a design spec.
"""
import os
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D

from .fonts import TYPE_SCALE, font, pt
from .mark import draw_mark
from .themes import Theme

HANDLE = "@artindata"
DPI = 100


@dataclass(frozen=True)
class Format:
    name: str
    width: int
    height: int
    margin: int     # left/right
    top: int        # to the title's cap line
    footer: int     # height of the footer band


FORMATS = {
    "instagram": Format("instagram", 1080, 1350, margin=80, top=84, footer=76),
    "x":         Format("x",         1600, 900,  margin=80, top=64, footer=64),
}


class Canvas:
    def __init__(self, fmt, theme: Theme):
        self.fmt = FORMATS[fmt] if isinstance(fmt, str) else fmt
        self.theme = theme
        self.W, self.H = self.fmt.width, self.fmt.height
        self.fig = plt.figure(figsize=(self.W / DPI, self.H / DPI), dpi=DPI,
                              facecolor=theme.bg)

    # -- geometry ---------------------------------------------------------
    @property
    def left(self):
        return self.fmt.margin

    @property
    def right(self):
        return self.W - self.fmt.margin

    @property
    def footer_top(self):
        return self.H - self.fmt.footer

    def fx(self, x):
        return x / self.W

    def fy(self, y):
        return 1 - y / self.H

    # -- drawing ----------------------------------------------------------
    def text(self, x, y, s, role="label", color=None, ha="left", va="baseline", **kw):
        face, size = TYPE_SCALE[role]
        return self.fig.text(self.fx(x), self.fy(y), s, fontproperties=font(face),
                             fontsize=pt(size, DPI), color=color or self.theme.ink,
                             ha=ha, va=va, **kw)

    def rule(self, x0, x1, y, color=None, lw=1):
        self.fig.add_artist(Line2D([self.fx(x0), self.fx(x1)], [self.fy(y)] * 2,
                                   color=color or self.theme.guide, lw=lw))

    def axes(self, left, top, right, bottom):
        """Plot area in px. No chrome: spines off, ticks recessive."""
        ax = self.fig.add_axes([self.fx(left), self.fy(bottom),
                                (right - left) / self.W, (bottom - top) / self.H])
        ax.set_facecolor("none")
        for s in ax.spines.values():
            s.set_visible(False)
        _, size = TYPE_SCALE["label"]
        ax.tick_params(length=0, labelsize=pt(size, DPI), labelcolor=self.theme.muted,
                       pad=pt(10, DPI))
        for lab in ax.get_xticklabels() + ax.get_yticklabels():
            lab.set_fontproperties(font("sans"))
        return ax

    def gradient(self, stops=None):
        """H x W x 3 page gradient through `stops` (default: theme.sky)."""
        stops = stops or self.theme.sky or (self.theme.bg,)
        cols = np.array([to_rgb(s) for s in stops])
        t = np.linspace(0, 1, self.H)
        pos = np.linspace(0, 1, len(cols))
        column = np.stack([np.interp(t, pos, cols[:, i]) for i in range(3)], axis=1)
        return np.broadcast_to(column[:, None, :], (self.H, self.W, 3)).copy()

    def backdrop(self, image=None):
        """Full-page axes behind everything, in px (origin top-left).

        `image` is an H x W x 3 array painted as the page (e.g. `gradient()`
        with art composited on it). Returns the axes for further drawing.
        """
        ax = self.fig.add_axes([0, 0, 1, 1], zorder=-10)
        ax.set_xlim(0, self.W)
        ax.set_ylim(self.H, 0)
        ax.set_axis_off()
        if image is not None:
            self._page = np.clip(image, 0, 1)
            ax.imshow(self._page, extent=(0, self.W, self.H, 0), aspect="auto",
                      interpolation="nearest", zorder=-1)
        return ax

    def page_color(self, y, x=None):
        """Page colour under (x, y) px -- use it for halos so they blend in."""
        page = getattr(self, "_page", None)
        if page is None:
            return np.array(to_rgb(self.theme.bg))
        yi = int(np.clip(y, 0, self.H - 1))
        xi = int(np.clip(self.W / 2 if x is None else x, 0, self.W - 1))
        return page[yi, xi]

    def style_ticks(self, ax):
        """Re-apply the label font after tick labels have been set."""
        _, size = TYPE_SCALE["label"]
        for lab in ax.get_xticklabels() + ax.get_yticklabels():
            lab.set_fontproperties(font("sans"))
            lab.set_fontsize(pt(size, DPI))

    def header(self, title, subtitle=None, top=None, halo=None, align="left"):
        """Title + subtitle. Returns the y (px) below them.

        `top` overrides the grid's default (e.g. to sit below background art);
        `halo` is an optional list of path effects for legibility over art;
        `align` is "left" (at the margin) or "center" (on the page axis).
        """
        _, t = TYPE_SCALE["title"]
        _, s = TYPE_SCALE["subtitle"]
        kw = {"path_effects": halo} if halo else {}
        x, ha = (self.W / 2, "center") if align == "center" else (self.left, "left")
        y = (self.fmt.top if top is None else top) + t * 0.72
        self.text(x, y, title, role="title", ha=ha, **kw)
        if subtitle:
            for i, line in enumerate(subtitle.split("\n")):
                y += (s * 1.9 if i == 0 else s * 1.4)
                self.text(x, y, line, role="subtitle", color=self.theme.muted, ha=ha, **kw)
        return y + s

    def signature(self, x, y, size=22):
        """The signature mark (see mark.py), sitting on the text baseline `y`.
        Returns the x where the handle text should start."""
        pad = 3                                   # room for the frame's stroke
        x0, y0 = x - pad, y - size - pad + 3      # box top-left; mark centred on caps
        side = size + 2 * pad
        ax = self.fig.add_axes([self.fx(x0), self.fy(y0 + side), side / self.W, side / self.H])
        ax.set_xlim(x0, x0 + side); ax.set_ylim(y0 + side, y0); ax.set_axis_off()
        draw_mark(ax, x + size / 2, y0 + pad + size / 2, size, self.theme.ink,
                  self.theme.accent, lambda px: pt(px, DPI))
        return x + size + 12

    def footer(self, source):
        y_rule = self.footer_top
        self.rule(self.left, self.right, y_rule)
        y = y_rule + self.fmt.footer * 0.55
        x = self.signature(self.left, y)
        self.text(x, y, HANDLE, role="handle")
        self.text(self.right, y, source, role="small", color=self.theme.muted, ha="right")

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # render to a temp file, then swap it in: an image viewer holding the
        # old file open (common on Windows) only delays the swap briefly
        tmp = path.with_name(path.stem + ".tmp" + path.suffix)
        self.fig.savefig(tmp, dpi=DPI, facecolor=self.theme.bg)
        plt.close(self.fig)
        for attempt in range(20):
            try:
                os.replace(tmp, path)
                break
            except OSError:
                if attempt == 19:
                    raise
                time.sleep(0.25)
        return path
