"""Download the sunspot data this post uses.

Source: SILSO, World Data Center for the production, preservation and
dissemination of the international sunspot number, Royal Observatory of
Belgium, Brussels (sidc.be/SILSO). Monthly mean total sunspot number, V2.0.
"""
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
URL = "https://www.sidc.be/SILSO/DATA/SN_m_tot_V2.0.csv"


def main():
    DATA.mkdir(exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "artindata/0.1 (github.com/enry86/artindata)"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    (DATA / "SN_m_tot_V2.0.csv").write_bytes(raw)
    print(f"{len(raw.splitlines())} monthly values saved")


if __name__ == "__main__":
    main()
