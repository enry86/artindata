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
  highlights optional categorical colours for a few named groups of marks
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
    # optional categorical colours for highlighted groups (validated as a set)
    highlights: tuple = ()


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
    # deep space: starlight dust on near-black, warm highlights
    "deep_space": Theme(
        name="deep_space",
        bg="#05060D",
        ink="#F3F5FB",
        muted="#A8B0CA",
        guide="#2A3354",
        mark="#AFC3F0",
        accent="#FFC857",
        mark_range=("#E4EBFF", "#7F93D6"),   # pale starlight .. deep blue
        sky=("#0C1233", "#080B20", "#05060D", "#05060D"),
        # gold / rose: CVD dE 23.5 (deutan), normal 30.1, both >= 3:1 on bg
        highlights=("#FFC857", "#FF6FD8"),
    ),
    # a planet's restless crust: embers glowing on near-black
    "ember": Theme(
        name="ember",
        bg="#030306",
        ink="#F6F0E8",
        muted="#ABA6B8",   # >= 7:1 on bg
        guide="#2A2836",
        mark="#FF9A5A",
        accent="#FF7A33",
        mark_range=("#FFE2B8", "#7A3FD0"),   # shallow, pale gold .. deep, violet (depth)
        sky=("#09070F", "#050509", "#030306", "#030306"),
    ),
    # the sky above us: ivory swarm and coral rings over a jade planet
    "orbit": Theme(
        name="orbit",
        bg="#030A08",
        ink="#F1F7F2",
        muted="#A1BDB3",   # >= 7:1 on bg
        guide="#1B3731",
        mark="#F4EBC6",
        accent="#FF5E5B",
        mark_range=("#FBF6E0", "#D8CC96"),
        sky=("#0A1D19", "#06110E", "#030A08", "#030A08"),
        highlights=("#F4EBC6", "#FF5E5B"),   # ivory / coral: differ in hue and in lightness (CVD dE >= 35)
    ),
    # the Sun: gold and ember on a scorched near-black
    "solar": Theme(
        name="solar",
        bg="#0A0604",
        ink="#F8F0E4",
        muted="#BFAE95",   # >= 7:1 on bg
        guide="#2C1B12",
        mark="#FFAE3D",
        accent="#FFE3A3",  # pale gold: rings that single out a few discs
        mark_range=("#FFF1C9", "#8A2E0B"),   # white-hot centre .. dark red limb
        sky=("#1A0A05", "#0F0705", "#0A0604", "#0A0604"),
    ),
    # an 18th-century sea chart: ink on parchment, one bright ink per nation
    "logbook": Theme(
        name="logbook",
        bg="#EFE5CF",
        ink="#2E2116",
        muted="#6E5B45",   # >= 4.5:1 on bg
        guide="#DCCDAE",
        mark="#6B5A45",
        accent="#8E1F2A",
        # Dutch orange, British crimson, Spanish teal, French blue: CVD dE >= 10.4 (all pairs)
        highlights=("#F07A10", "#C8102E", "#0E8C7A", "#2456C8"),
    ),
}
