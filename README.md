# Songs take-home

Two messy song exports are normalized into one clean dataset, served by a FastAPI backend, and shown in a React dashboard. The pipeline (backend/pipeline) merges the files by id and never invents values: anything untrustworthy becomes null with a reason, and the three durations stored in seconds are fixed only because their segment counts confirm it. The API (backend/app) sorts and pages across the whole dataset, has a title search that always returns a list because titles aren't unique, and stores 1-5 star ratings in SQLite. The dashboard (frontend) shows the table, search, ratings, CSV export and a chart of the evidence for the duration fix. Each part was built spec-first (requirements, design, tasks, then test-first code), and the reasoning is in DECISIONS.md.

| Part | Code | Spec | How to run |
|---|---|---|---|
| Data pipeline | `backend/pipeline/` | [specs/data](specs/data/) | [backend/README.md](backend/README.md#data-pipeline) |
| API | `backend/app/` | [specs/api](specs/api/) | [backend/README.md](backend/README.md#api) |
| Dashboard | `frontend/` | [specs/frontend](specs/frontend/) | [frontend/README.md](frontend/README.md) |

The decisions and the reasons behind them are in [DECISIONS.md](DECISIONS.md).

## Quick start

You need Python 3.11+ and Node 18+. On macOS the default `python3` may be older, so check with `python3 --version` (Homebrew's `python3.12` works).

Backend, from `backend/`:

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -e ".[dev]"
```

```bash
uvicorn app.main:create_app --factory --reload
```

The API runs on http://localhost:8000 (docs at /docs). The cleaned data is already committed in `data/normalized/`; to regenerate it, run `python -m pipeline` with the venv active.

Frontend, from `frontend/` in a second terminal:

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173.

## Tests

From `backend/`, with the venv active:

```bash
python -m pytest
```

From `frontend/`:

```bash
npm test
```
