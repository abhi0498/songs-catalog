# Songs Dashboard

React + Vite single page over the [Songs API](../backend/README.md). Spec: [`specs/frontend/`](../specs/frontend/).

## Run

Start the API first (from `backend/`):

```bash
uvicorn app.main:create_app --factory --reload
```

Then, from this folder:

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173. The API URL defaults to `http://localhost:8000`. To change it, set `VITE_API_URL`, e.g. `VITE_API_URL=http://localhost:9000 npm run dev`. The API only allows the `http://localhost:5173` origin by default (`CORS_ORIGINS` on the backend).

## What it does

- **Songs table:** 10 per page. Click any header to sort by it, and click again to flip asc/desc. The API does the sorting, across all songs.
- **Missing values** are shown as "—". Hover or focus one to see why it's missing (out of range, files disagree, missing in the source, …).
- **Download CSV** saves exactly the rows on screen: a UTF-8 BOM, CRLF line endings, and spreadsheet formula characters escaped.
- **Find a song:** title search that ignores case, accents, spacing and punctuation. It says whether the matches are exact or partial, and shows every song when titles repeat ("Perfect").
- **Stars:** clicking writes the rating to the API. If saving fails, the old rating stays and an error shows next to the stars.
- **Chart:** duration vs segment count. The 3 songs whose durations were stored in seconds are highlighted, and they sit on the same trend as the rest, which is the evidence for the fix.

## Test

```bash
npm test
```

Vitest unit tests cover the logic in `src/lib` (CSV, sort toggle, search messages, reason texts, chart data, API errors). Component tests run against a fake API (`src/test/fakeApi.js`).
