# pyfit

PRINT YOUR FIT AI pattern studio.

## Run locally

From `/home/runner/work/pyfit/pyfit`:

```bash
python3 backend.py
```

Then open `http://localhost:8000`.

## Backend endpoints

- `POST /api/mesh/refine` updates mesh params from refinement text.
- `POST /api/pattern/generate` returns generated pattern geometry + sewing instructions.
- `GET /api/health` returns service status.
