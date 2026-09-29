"""Named colour themes. Palette follows the topic; roles stay the same.

Roles
  bg      page background
  ink     primary text (titles, key labels)
  muted   secondary text (axis labels, footer) -- keep >= 4.5:1 on bg
  guide   recessive gridlines / rules
  mark    the many small data marks
  accent  the one thing the eye should follow (trend, highlight)
  mark_range  optional light/dark ends for decorative tonal variation
  sky     optional page gradient stops, top to bottom
  diverging  optional (negative, neutral, positive) colours for signed values
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    ink: str
    muted: str
    guide: str
    mark: str
    accent: str
    # light/dark ends for decorative tonal variation of `mark` (never data)
    mark_range: tuple = ()
    # optional top-to-bottom page gradient (evenly spaced stops)
    sky: tuple = ()
    # optional (negative pole, neutral midpoint, positive pole)
    diverging: tuple = ()


THEMES = {
    # earthy on cream: botany, phenology, agriculture
    "botany": Theme(
        name="botany",
        bg="#F3EDE2",
        ink="#2B2621",     # 12.9:1 on bg
        muted="#6F665A",   # 4.8:1
        guide="#E1D8C8",
        mark="#CC7890",    # 2.7:1 -- soft by design, read in aggregate
        accent="#8A3556",  # 6.6:1
        mark_range=("#E7AEBD", "#B9637E"),   # pale blush .. deep rose
    ),
    # blossom at dusk: twilight sky over dark water, glowing marks
    "sakura_night": Theme(
        name="sakura_night",
        bg="#141A3A",
        ink="#F6F0F4",     # >= 7.4:1 anywhere on the sky
        muted="#B9B6D3",   # >= 6.9:1 below the top band
        guide="#2E3563",
        mark="#F4A6C0",
        accent="#FF7A33",  # warm orange (= the "earlier" pole), >= 3:1 on every sky stop
        mark_range=("#FFD9E6", "#E88AB0"),
        sky=("#2C4C8F", "#1B2A5E", "#111633", "#0B0D1C"),
        # orange / neutral / cyan: poles pass CVD (dE >= 25.1) and 3:1 on every sky stop
        diverging=("#FF7A33", "#EDE6DA", "#3CCBFF"),
    ),
}
