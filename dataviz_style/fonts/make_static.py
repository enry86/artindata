"""Build the static Fraunces instances used by dataviz_style.

matplotlib can't select variable-font axes, so we freeze the Google Fonts
variable file into a few static TTFs. Run once (needs fonttools):

    python dataviz_style/fonts/make_static.py path/to/Fraunces[...].ttf path/to/Fraunces-Italic[...].ttf

Source: https://github.com/google/fonts/tree/main/ofl/fraunces (SIL OFL 1.1)
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).parent

# name -> (source index, axis location)
INSTANCES = {
    "Fraunces-Display.ttf":       (0, {"opsz": 72, "wght": 380, "SOFT": 50, "WONK": 0}),
    "Fraunces-DisplaySemi.ttf":   (0, {"opsz": 72, "wght": 560, "SOFT": 50, "WONK": 0}),
    "Fraunces-TextItalic.ttf":    (1, {"opsz": 14, "wght": 400, "SOFT": 50, "WONK": 0}),
}


def main(roman, italic):
    sources = [roman, italic]
    for name, (src, loc) in INSTANCES.items():
        font = instantiateVariableFont(TTFont(sources[src]), loc)
        font.save(HERE / name)
        print("wrote", name)


if __name__ == "__main__":
    main(*sys.argv[1:3])
