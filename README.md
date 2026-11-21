# Songs take-home

Two messy song exports are normalized into one clean dataset, served by a FastAPI backend, and shown in a React dashboard. Each part was built spec-first: requirements → design → tasks → test-first implementation.

| Part | Code | Spec | How to run |
|---|---|---|---|
| Data pipeline | `backend/pipeline/` | [specs/data](specs/data/) | [backend/README.md](backend/README.md#data-pipeline) |
| API | `backend/app/` | [specs/api](specs/api/) | [backend/README.md](backend/README.md#api) |
| Dashboard | `frontend/` | [specs/frontend](specs/frontend/) | [frontend/README.md](frontend/README.md) |

The decisions and the reasons behind them are in [DECISIONS.md](DECISIONS.md).

## Quick start

From `backend/`, regenerate the clean data (the output is already committed in `data/normalized/`):

```bash
python -m pipeline
```

From `backend/`, start the API on :8000:

```bash
uvicorn app.main:create_app --factory --reload
```

From `frontend/`, start the dashboard on :5173:

```bash
npm install && npm run dev
```

## Tests

From `backend/`:

```bash
python -m pytest
```

From `frontend/`:

```bash
npm test
```
