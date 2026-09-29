# 001 · 1,200 springs in Kyoto

![Instagram version](output/kyoto_blossoms_instagram.png)

## What it shows
The date Kyoto's cherry trees reach full bloom each year, from 812 to 2026.
Each petal is one year with a record, drifting beneath a cherry canopy at dusk.
The line is a smoothed long-run average. Its colour shows how far it sits from
the 1,200-year mean (April 14, dashed): orange where blooms come earlier than usual,
cyan where they come later, pale grey on the mean.
For a thousand years the average wanders around mid-April. From the mid-1800s
it moves steadily earlier. In 2023 the trees peaked on **March 25**, the earliest
date in the whole record.

## Data
- **Source:** Yasuyuki Aono (Osaka Metropolitan University), who compiled
  bloom dates from imperial court diaries, chronicles and poetry anthologies,
  plus modern observations by the Japan Meteorological Agency.
  See Aono & Kazui (2008), *Int. J. Climatology* 28:905–914, and Aono & Saito (2010),
  *Int. J. Biometeorology* 54:211–219.
- **Distributed by:** [Our World in Data](https://ourworldindata.org/grapher/date-of-the-peak-cherry-tree-blossom-in-kyoto),
  CC BY 4.0. The original spreadsheet on Aono's university page is no longer online.
- **Coverage:** 838 recorded years between 812 and 2026. Before 1400, many
  years have no surviving record. Those years are left empty, not filled in.

## Caveats
- Dates are stored as day-of-year and shown on a non-leap calendar, so a
  label can be off by one day in leap years.
- Pre-modern dates come from historical documents and carry more
  uncertainty than modern observations.
- The average is Gaussian-weighted (σ = 15 years, so it spans roughly 50 years)
  and uses recorded years only. A plain moving window jumps each time a record
  enters or leaves it. That creates spikes that aren't in the data, which is
  most visible in the sparse early centuries.
- The average is only drawn where at least 10 records fall within ±25 years.
  That's why the line starts in the late 800s.
- The recent shift to earlier blooms reflects both climate warming and
  Kyoto's urban heat island (Aono's own attribution).

## How it's built
- `fetch_data.py` downloads the series and writes `data/kyoto_bloom.csv`,
  keeping only years with a record.
- `kyoto_blossoms.py` draws both exports with the shared `dataviz_style`
  module (`sakura_night` theme: twilight sky, dark "water", lantern-gold accent):
  - Petals are a custom Bézier `Path` used as a scatter marker. Their rotation
    and tone (pale to deep pink, from the theme's `mark_range`) are decorative
    only. **Colour does not encode anything.** Only a petal's position carries data.
    Both come from a seeded random generator, so renders repeat exactly.
  - `canopy.py` paints the background: branch skeletons grown by `branches.py`
    (limbs wander, taper and split), then soft rose masses (blurred), five-petal
    flowers and highlights. A blurred copy of the blossom is screen-blended on
    top so the canopy glows. The result goes in as the page image via
    `Canvas.backdrop(image=...)`.
  - A second, far canopy is rendered first, for depth, using atmospheric
    perspective. It has smaller flowers and thinner wood, and is then defocused
    (3.5 px blur), hazed 45% toward the sky behind it and faded to 75%. It can
    reach a little lower than the front canopy, so it peeks out beneath it,
    but it's kept out of explicit boxes around the plot, title and key. Blurs
    are done premultiplied (`effects.blur`), so transparent edges don't leave
    a pale fringe.
  - The canopy is **decoration only**. It is kept out of the plot area and
    away from the title, and its flowers are whole blossoms, a different shape
    from the single data petals. There are no decorative petals in the plot.
    Every petal there is a real year.
  - The data petals glow. A blurred copy of the real petals is screen-blended
    into the page, so light appears only around marks that exist. A soft
    lavender pool of light deep in the scene adds depth. The raster helpers
    (layers, blur, screen blend, radial light) live in `dataviz_style/effects.py`.
  - The average line is a `LineCollection`, each segment coloured on a
    diverging scale (theme `diverging`: orange / neutral / cyan) by its distance
    from the mean. The scale saturates at ±6 days. The two poles pass a
    colour-blindness check (ΔE ≥ 25.1) with ≥ 3:1 contrast on every sky tone.
    A dark casing under the line separates it from the petals, as roads are cased on maps.
    Colour only repeats what the line's position already shows: its distance
    from the dashed mean line.
  - The line's glow is a blurred copy of the line itself. Text halos sample
    the page image (`Canvas.page_color`), so they blend into the gradient.
  - The 4:5 version runs time down the page. The 16:9 version runs it left to right.

```
python fetch_data.py
python kyoto_blossoms.py   # -> output/kyoto_blossoms_instagram.png, output/kyoto_blossoms_x.png
```
