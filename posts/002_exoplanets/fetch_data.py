"""Download every confirmed exoplanet and save the columns this post uses.

Source: NASA Exoplanet Archive, Planetary Systems Composite Parameters table
(`pscomppars`): one row per confirmed planet, with the archive's pick of the
best value for each field. Some of those values are the archive's own
calculations rather than published measurements (the `*_reflink` column then
says "Calculated Value"); we keep a flag for each of them.
"""
from pathlib import Path

import pandas as pd

TAP = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
DATA = Path(__file__).parent / "data"

COLUMNS = [
    "pl_name", "hostname", "disc_year", "discoverymethod", "disc_facility",
    "pl_controv_flag",
    "pl_orbper", "pl_orbsmax", "pl_insol", "pl_eqt",
    "pl_rade", "pl_bmasse", "pl_bmassprov",
    "st_teff", "st_mass", "st_rad", "st_lum", "st_spectype",
    "sy_dist", "ra", "dec", "sy_snum", "sy_pnum",
]
CALCULATED = ["pl_rade", "pl_bmasse", "pl_insol"]


def main():
    DATA.mkdir(exist_ok=True)
    reflinks = [f"{c}_reflink" for c in CALCULATED]
    query = f"select {','.join(COLUMNS + reflinks)} from pscomppars"
    raw = pd.read_csv(f"{TAP}?query={query.replace(' ', '+')}&format=csv")

    for c in CALCULATED:
        raw[f"{c}_calc"] = raw.pop(f"{c}_reflink").fillna("").str.contains("Calculated Value")

    raw.to_csv(DATA / "planets.csv", index=False)
    print(f"{len(raw)} planets, discovered {raw.disc_year.min()}-{raw.disc_year.max()}")


if __name__ == "__main__":
    main()
