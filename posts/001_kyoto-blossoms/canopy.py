"""A glowing cherry canopy over a dusk sky. Decoration only.

Pipeline (all seeded, so every render is identical):
  1. grow branch skeletons with `branches.Branch`
  2. render transparent layers offscreen: dark wood, soft rose masses
     (blurred into clouds), then five-petal flowers and bright highlights
  3. composite over the sky and add blurred copies of the blossom as light
     ("bloom"), so it glows like lit sakura at night

An optional far layer is rendered first, the same way but with smaller
flowers, then blurred and hazed into the sky (atmospheric perspective),
so the canopy has depth.

Returns an H x W x 3 float image for `Canvas.backdrop(image=...)`.
"""
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgb
from matplotlib.transforms import Affine2D

from branches import Branch, flower_marker
from dataviz_style import effects as fx

WOOD = "#1C1628"
MASS = "#A8457A"          # the deep rose "body" of the blossom clouds
HIGHLIGHT = "#FFF4F8"


def _render(W, H, dpi, limbs, allowed, petal, blossom_range, px_to_pt, seed,
            flower_px, density, keep_out, spill, thin):
    """Grow one canopy and render it as (wood, mass, bloom) RGBA layers."""
    rng = np.random.default_rng(seed)
    b = Branch(seed, allowed, bend=10, split=0.9)
    for x, y, angle, length, width, depth in limbs:
        b.grow(x, y, angle, length, width, depth)

    # where blossom grows: every twig end, and all along the thinner wood
    spots = []
    for (x0, y0), (x1, y1) in (s for s, w in zip(b.segments, b.widths) if w < 8):
        for _ in range(rng.poisson(6 * density)):
            t = rng.random()
            spots.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 24))
    for x, y in b.tips:
        spots += [(x, y, 34)] * int(rng.integers(28, 44) * density)
    spots = np.array(spots)
    xy = spots[:, :2] + rng.normal(0, 1, (len(spots), 2)) * spots[:, 2:3]
    ok = np.array([allowed(x, y - spill) for x, y in xy])
    for x0, y0, x1, y1 in keep_out:
        ok &= ~((xy[:, 0] > x0) & (xy[:, 0] < x1) & (xy[:, 1] > y0) & (xy[:, 1] < y1))
    if thin is not None:
        ok &= rng.random(len(xy)) < np.array([thin(x, y) for x, y in xy])
    xy = xy[ok]
    n = len(xy)

    def wood(ax):
        ax.add_collection(LineCollection(
            b.segments, colors=WOOD, linewidths=[px_to_pt(w) for w in b.widths],
            capstyle="round", joinstyle="round"))

    def mass(ax):
        # soft rose volume behind the flowers; blurred below into a cloud
        m = rng.random(n) < 0.25
        ax.scatter(xy[m, 0], xy[m, 1], s=px_to_pt(rng.uniform(40, 90, m.sum())) ** 2,
                   c=MASS, alpha=0.35, lw=0)

    def blossom(ax):
        # flowers, pale to rose, in random orientations
        light, dark = (np.array(to_rgb(h)) for h in blossom_range)
        t = rng.beta(2, 2.5, (n, 1))
        cols = np.hstack([light + (dark - light) * t, rng.uniform(0.55, 0.95, (n, 1))])
        size = px_to_pt(flower_px * rng.uniform(0.6, 1.25, n)) ** 2
        base = flower_marker(petal)
        rot = rng.integers(0, 6, n)
        for k in range(6):
            sel = rot == k
            ax.scatter(xy[sel, 0], xy[sel, 1], s=size[sel], c=cols[sel], lw=0,
                       marker=Affine2D().rotate_deg(k * 12).transform_path(base))
        # a scatter of near-white highlights where the light catches
        h = rng.random(n) < 0.07
        ax.scatter(xy[h, 0], xy[h, 1], s=px_to_pt(flower_px * 0.5) ** 2,
                   c=HIGHLIGHT, alpha=0.85, lw=0, marker=base)

    return (fx.layer(W, H, dpi, wood),
            fx.blur(fx.layer(W, H, dpi, mass), 22),
            fx.layer(W, H, dpi, blossom))


def _recede(layer, sky, blur, haze, opacity):
    """Push a layer back: defocus it, tint it towards the sky behind, fade it."""
    L = fx.blur(layer, blur) if blur else layer.copy()
    L[..., :3] = L[..., :3] * (1 - haze) + sky * haze
    L[..., 3] *= opacity
    return L


def canopy(sky, limbs, allowed, petal, blossom_range, px_to_pt, dpi, seed=7,
           flower_px=15, density=1.0, keep_out=(), spill=20, thin=None,
           far_limbs=None, far_allowed=None, far_thin=None, far_seed=None, far_blur=3.5,
           far_haze=0.45, far_opacity=0.75):
    """`allowed(x, y)` bounds the tree; flowers may spill `spill` px past it.
    `keep_out` is a list of (x0, y0, x1, y1) px boxes (e.g. the title) kept clear.
    `thin(x, y)` -> 0..1 is the chance a flower survives there (sparser areas).
    `far_limbs` adds a second, receding canopy behind the first, bounded by
    `far_allowed` and thinned by `far_thin` (defaults: `allowed`, `thin`).
    """
    H, W, _ = sky.shape
    common = dict(allowed=allowed, petal=petal, blossom_range=blossom_range,
                  px_to_pt=px_to_pt, keep_out=keep_out, spill=spill, thin=thin)
    img = sky

    if far_limbs:
        far_common = dict(common, allowed=far_allowed or allowed, thin=far_thin or thin)
        layers = _render(W, H, dpi, far_limbs, seed=far_seed or seed + 100,
                         flower_px=flower_px * 0.7, density=density * 0.9, **far_common)
        far = [_recede(L, sky, far_blur, far_haze, far_opacity) for L in layers]
        for L in far:
            img = fx.over(img, L)
        img = fx.glow(img, far[2], 20, 0.3)     # a faint haze of light, no sharp bloom

    wood_l, mass_l, bloom_l = _render(W, H, dpi, limbs, seed=seed, flower_px=flower_px,
                                      density=density, **common)
    img = fx.over(img, wood_l)
    img = fx.over(img, mass_l)
    img = fx.over(img, bloom_l)
    img = fx.glow(img, bloom_l, 10, 0.55)       # tight glow
    img = fx.glow(img, bloom_l, 45, 0.45)       # wide haze
    return img
