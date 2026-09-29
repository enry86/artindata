"""Typography: bundled fonts (SIL OFL) and the type scale.

Fonts are loaded from files, not system names, so every machine renders
identically. Sizes are in pixels of the exported image; `pt()` converts.
"""
from pathlib import Path

from matplotlib.font_manager import FontProperties

FONT_DIR = Path(__file__).parent / "fonts"

_FILES = {
    "display": "Fraunces-Display.ttf",
    "display_semi": "Fraunces-DisplaySemi.ttf",
    "note": "Fraunces-TextItalic.ttf",
    "sans": "Inter-Regular.ttf",
    "sans_medium": "Inter-Medium.ttf",
    "sans_semi": "Inter-SemiBold.ttf",
}

# role -> (font, size in px)
TYPE_SCALE = {
    "title":    ("display", 64),
    "subtitle": ("sans", 24),
    "note":     ("note", 22),     # annotations inside the plot
    "label":    ("sans", 17),     # axis labels, key
    "small":    ("sans", 15),     # footer
    "handle":   ("sans_semi", 16),
}


def font(name):
    return FontProperties(fname=FONT_DIR / _FILES[name])


def pt(px, dpi):
    return px * 72 / dpi
