"""Download the satellite data this post uses.

Source: CelesTrak (celestrak.org), Dr T.S. Kelso.
  - GP "active" orbital elements: every satellite CelesTrak considers active.
    CelesTrak serves one download of a group per 2 hours; a second request
    returns a short message instead of data, in which case the old file is kept.
  - SATCAT: the catalog of everything launched (owner, launch date, status).
Also the Natural Earth 110m land polygons (public domain) for the continents.
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).parent / "data"
GP = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json"
SATCAT = "https://celestrak.org/pub/satcat.csv"
LAND = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "artindata/0.1 (github.com/enry86/artindata)"})
    return urllib.request.urlopen(req, timeout=120).read()


def main():
    DATA.mkdir(exist_ok=True)
    raw = get(GP)
    try:
        sats = json.loads(raw)
        (DATA / "gp_active.json").write_bytes(raw)
        # the moment satellites.py places every satellite: the download, to the minute (UTC)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        (DATA / "snapshot.txt").write_text(now.strftime("%Y-%m-%dT%H:%M") + "\n")
        print(f"{len(sats)} active satellites, newest element set {max(s['EPOCH'] for s in sats)}")
    except json.JSONDecodeError:
        print("CelesTrak did not return data (one download per 2 hours):", raw[:120].decode(errors="replace"))
    (DATA / "satcat.csv").write_bytes(get(SATCAT))
    (DATA / "ne_110m_land.geojson").write_bytes(get(LAND))


if __name__ == "__main__":
    main()
