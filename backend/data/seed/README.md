# Freight-index seed data (FBX / WCI)

The FBX (Freightos Baltic Index) and WCI (Drewry World Container Index) have **no
free public API** — both are gated behind enterprise/registration. The
`fbx`/`wci` collectors are therefore generic: they fetch whatever CSV/JSON URL
you point them at and upsert `(date, value[, route])` rows into `FreightIndex`.

`fbx.csv` / `wci.csv` here are **sample weekly values** (USD/FEU, approximate)
so the Macro Indices chart and `fbx_pct_7d` have something to render in a demo.
Replace them with real numbers (e.g. manually transcribed weekly figures) when
you have a source.

## Wiring it up

Host these files at a URL the backend can GET (e.g. GitHub raw of this repo),
then set on Render:

```
FBX_SOURCE_URL=https://raw.githubusercontent.com/<owner>/<repo>/main/backend/data/seed/fbx.csv
WCI_SOURCE_URL=https://raw.githubusercontent.com/<owner>/<repo>/main/backend/data/seed/wci.csv
```

Next `POST /api/v1/cron/run?jobs=collect` (or `?jobs=collect,score`) ingests them.

## Format

- `fbx.csv`: `date,value,route` — `route` is optional (defaults `GLOBAL`);
  collector stores `index_name = FBX_<route>`.
- `wci.csv`: `date,value` — collector stores `index_name = WCI`.
- `date` must be ISO (`YYYY-MM-DD`); `value` numeric.
