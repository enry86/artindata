"""Download every earthquake of magnitude 4.5+ in 2025 and save the columns this post uses.

Source: USGS Earthquake Hazards Program, ComCat catalog, via the FDSN event
web service. Public domain (US Government work). Magnitude 4.5 is the
catalog's global completeness threshold: below it, what is recorded depends
on how close the nearest seismometers are.

Also downloads the Natural Earth 110m land polygons (public domain), used for
the faint continents on the globe.
"""
import urllib.request
from pathlib import Path

import pandas as pd

API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
DATA = Path(__file__).parent / "data"
START, END = "2025-01-01", "2026-01-01"      # end is exclusive
LAND = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson"
KEEP = ["time", "latitude", "longitude", "depth", "mag", "magType", "place", "id", "status"]


def main():
    DATA.mkdir(exist_ok=True)
    url = (f"{API}?format=csv&starttime={START}&endtime={END}"
           f"&minmagnitude=4.5&orderby=time-asc&eventtype=earthquake")
    raw = pd.read_csv(url)
    assert len(raw) < 20000, "the API caps one request at 20,000 events"
    raw[KEEP].to_csv(DATA / "quakes_2025.csv", index=False)
    print(f"{len(raw)} earthquakes, {raw.time.min()} .. {raw.time.max()}")
    urllib.request.urlretrieve(LAND, DATA / "ne_110m_land.geojson")


if __name__ == "__main__":
    main()
