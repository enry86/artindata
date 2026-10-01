"""An Earth-likeness distance for every planet, inspired by the Earth
Similarity Index (Schulze-Makuch et al. 2011), but built from three terms:

  size   how far the planet's size is from Earth's
  climate how far its sunlight falls outside the habitable zone
  star   how far its star's temperature is from the Sun's

Each term is a log ratio divided by a "one step away" factor, so a planet
twice as big as Earth is as far away as one half as big, and each term
reads as "number of steps from Earth". The three are combined as a
weighted root-mean-square: 0 is Earth, 1 is one step away on average.

Size uses the measured radius when there is one. Otherwise it uses mass
and converts it with the rocky-planet relation R ~ M^0.279 (Chen &
Kipping 2017), so both give the same number of steps. Each planet is
flagged by how its size is known: measured radius, measured mass, or a
minimum mass (radial velocity gives M sin i; the true mass can be higher).

The habitable zone is the conservative one from Kopparapu et al. (2014):
from the runaway-greenhouse edge (inner) to the maximum-greenhouse edge
(outer), both in units of Earth's insolation and depending on the star's
temperature. Inside the zone, the climate term is 0.
"""
import numpy as np
import pandas as pd

SUN_TEFF = 5772.0          # K, IAU nominal

# "one step away" for each term, as a ratio
STEP = {
    "size": 1.5,           # 1.5 R_earth: the radius valley, super-Earth edge
    "climate": 2.0,        # twice the sunlight of the inner edge (or half the outer)
    "star": 1.5,           # 1.5x hotter or cooler than the Sun (~3850 K: an M0 dwarf)
}
WEIGHT = {"size": 1.0, "climate": 1.0, "star": 0.5}
MASS_RADIUS_EXP = 0.279    # Chen & Kipping 2017, terran worlds

# Kopparapu et al. 2014, Table 1: S_eff = S + a T + b T^2 + c T^3 + d T^4, T = Teff - 5780
HZ_INNER = (1.107, 1.332e-4, 1.580e-8, -8.308e-12, -1.931e-15)   # runaway greenhouse, 1 M_earth
HZ_OUTER = (0.356, 6.171e-5, 1.698e-9, -3.198e-12, -5.575e-16)   # maximum greenhouse


def hz_edges(teff):
    """Inner and outer habitable-zone insolation (Earth = 1) for a star.
    The fit is valid for 2600-7200 K; outside that we clip the temperature."""
    t = np.clip(teff, 2600, 7200) - 5780
    poly = lambda c: c[0] + c[1] * t + c[2] * t**2 + c[3] * t**3 + c[4] * t**4
    return poly(HZ_INNER), poly(HZ_OUTER)


def insolation(df):
    """Archive insolation, or L / a^2 when only luminosity and orbit are given.
    A handful of distant, directly imaged planets are listed as exactly 0
    (rounded); we treat those as unknown."""
    from_lum = 10.0 ** df.st_lum / df.pl_orbsmax**2
    return df.pl_insol.where(df.pl_insol > 0).fillna(from_lum)


def size_steps(df, step=STEP["size"]):
    """Size term (signed steps; positive = bigger than Earth) and its provenance."""
    radius_measured = df.pl_rade.notna() & ~df.pl_rade_calc
    mass_known = df.pl_bmasse.notna() & df.pl_bmassprov.isin(["Mass", "Msini"])
    log_r = np.where(radius_measured, np.log(df.pl_rade),
                     MASS_RADIUS_EXP * np.log(df.pl_bmasse))
    how = np.select([radius_measured, mass_known & (df.pl_bmassprov == "Mass"), mass_known],
                    ["radius", "mass", "min_mass"], default="none")
    steps = pd.Series(log_r / np.log(step), index=df.index)
    return steps.where(how != "none"), pd.Series(how, index=df.index)


def climate_steps(s, teff, step=STEP["climate"]):
    """Steps outside the habitable zone (signed; positive = too hot)."""
    inner, outer = hz_edges(teff)
    hot = np.log(s / inner).clip(lower=0)
    cold = np.log(s / outer).clip(upper=0)
    return (hot + cold) / np.log(step)


def star_steps(teff, step=STEP["star"]):
    return np.log(teff / SUN_TEFF) / np.log(step)


def score(df, weight=WEIGHT, step=STEP):
    """Adds the terms and the combined distance `d_earth` to a copy of df."""
    out = df.copy()
    s = insolation(df)
    size, how = size_steps(df, step["size"])
    terms = {
        "size": size,
        "climate": climate_steps(s, df.st_teff, step["climate"]),
        "star": star_steps(df.st_teff, step["star"]),
    }
    for k, v in terms.items():
        out[f"t_{k}"] = v
    out["size_from"] = how
    out["insol"] = s
    total = sum(weight.values())
    out["d_earth"] = np.sqrt(sum(weight[k] * terms[k] ** 2 for k in terms) / total)
    return out


def esi(df):
    """The widely quoted two-term ESI (radius and insolation, equal weights),
    for comparison. 1 = Earth. Uses radius from mass where needed, like ours."""
    r = np.exp(size_steps(df, np.e)[0])
    s = insolation(df)
    return 1 - np.sqrt(0.5 * (((r - 1) / (r + 1)) ** 2 + ((s - 1) / (s + 1)) ** 2))
