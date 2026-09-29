# Race Weekend Companion: website

Static Next.js site (deployed on Vercel) that replays each 2026 weekend session by session. It shows
only data the Python pipeline already computed; nothing runs on a server.

## Update the data after a session or race

From the repo root:

```bash
python scripts/backfill.py --years 2026 [--in-progress]   # new sessions from FastF1
python scripts/backtest.py                                # predictions + scores
python scripts/export_site.py                             # JSON for this site
```

`export_site.py` writes `web/data/` (read at build time) and `web/public/data/race/` (race results,
fetched only when a viewer reveals the race). Commit and push; Vercel rebuilds automatically.

## Develop

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run build      # static export in out/
```

## Deploy on Vercel (one-time)

Import the GitHub repo in Vercel and set **Root Directory** to `web`. The framework preset
(Next.js) and build command are detected automatically. Security headers live in `vercel.json`.

## Design

See [DESIGN.md](DESIGN.md) for the colour, type and layout decisions.
