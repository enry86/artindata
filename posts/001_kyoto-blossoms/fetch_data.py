"""Download the Kyoto peak-bloom series and save a tidy copy.

Primary source: Yasuyuki Aono (Osaka Metropolitan University), compiled from
court diaries, chronicles and modern observations. The original spreadsheet
is no longer online, so we use the Our World in Data mirror (updated yearly).
"""
from pathlib import Path

import pandas as pd

URL = ("https://ourworldindata.org/grapher/date-of-the-peak-cherry-tree-blossom-in-kyoto.csv"
       "?v=1&csvType=full&useColumnShortNames=true")
DATA = Path(__file__).parent / "data"


def main():
    DATA.mkdir(exist_ok=True)
    raw = pd.read_csv(URL, storage_options={"User-Agent": "dataviz-weekly/1.0"})
    raw.to_csv(DATA / "owid_raw.csv", index=False)

    # keep only years with an actual record; missing years stay missing
    df = (raw.rename(columns={"full_flowering_date": "doy"})
             .dropna(subset=["doy"])[["year", "doy"]]
             .astype(int))
    df.to_csv(DATA / "kyoto_bloom.csv", index=False)
    print(f"{len(df)} recorded years, {df.year.min()}-{df.year.max()}, "
          f"day {df.doy.min()}-{df.doy.max()}")


if __name__ == "__main__":
    main()
