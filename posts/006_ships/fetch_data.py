"""Download the ship logbook data this post uses.

Source: CLIWOC, Climatological Database for the World's Oceans 1750-1850,
release 2.1 (García-Herrera et al. 2005; Koek, Können et al. 2007), archived on
PANGAEA, doi:10.1594/PANGAEA.611088, CC BY 3.0. The GeoPackage export used
here is the one hosted by historicalclimatology.com.

The 93 MB bundle is read in a temporary folder; only two small CSVs are kept:
  data/positions.csv  every logged position (logbook, ship, nation, date, lat, lon)
  data/notes.csv      the logbooks' free-text remarks on wildlife, fights and ice
"""
import csv
import sqlite3
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DATA = Path(__file__).parent / "data"
URL = "https://www.historicalclimatology.com/downloads/cliwoc21-data.zip"
POSITIONS = ["LogbookIdent", "ShipName", "Nationality", "YR", "MO", "DY", "HR",
             "latitude", "longitude", "VoyageFrom", "VoyageTo"]
NOTES = ["BiologyMemo", "WarsAndFightsMemo", "SeaIce"]


def main():
    DATA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zpath = Path(tmp) / "cliwoc21.zip"
        req = urllib.request.Request(URL, headers={"User-Agent": "artindata/0.1 (github.com/enry86/artindata)"})
        zpath.write_bytes(urllib.request.urlopen(req, timeout=600).read())
        with zipfile.ZipFile(zpath) as z:
            z.extract("cliwoc21.gpkg", tmp)
        db = sqlite3.connect(Path(tmp) / "cliwoc21.gpkg")
        where = "latitude IS NOT NULL AND longitude IS NOT NULL"
        order = "ORDER BY LogbookIdent, YR, MO, DY, HR"

        rows = db.execute(f'SELECT {", ".join(POSITIONS)} FROM "CLIWOC21" WHERE {where} {order}').fetchall()
        with open(DATA / "positions.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["logbook", "ship", "nation", "year", "month", "day", "hour",
                        "lat", "lon", "voyage_from", "voyage_to"])
            w.writerows(rows)

        cols = POSITIONS[:9] + NOTES
        any_note = " OR ".join(f"(TRIM(IFNULL({n}, '')) NOT IN ('', '0'))" for n in NOTES)
        notes = db.execute(f'SELECT {", ".join(cols)} FROM "CLIWOC21" WHERE {where} AND ({any_note}) {order}').fetchall()
        with open(DATA / "notes.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["logbook", "ship", "nation", "year", "month", "day", "hour",
                        "lat", "lon", "biology", "fights", "sea_ice"])
            w.writerows(notes)
        db.close()
    print(f"{len(rows)} positions, {len(notes)} notes saved")


if __name__ == "__main__":
    main()
