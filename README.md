# pyfit

PRINT YOUR FIT AI pattern studio.

## Run locally

From `/home/runner/work/pyfit/pyfit`:

```bash
python3 backend.py
```

Then open `http://localhost:8000`.

## Auth + persistence

- User accounts, auth tokens, generated patterns, and payment sessions are persisted in:
  - `/home/runner/work/pyfit/pyfit/data/pyfit.db`
- Auth endpoints:
  - `POST /api/auth/signup`
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
  - `GET /api/auth/me`
- Saved patterns endpoint:
  - `GET /api/patterns` (requires authenticated request header)

## Backend endpoints

- `POST /api/mesh/refine` updates mesh params from refinement text.
- `POST /api/pattern/generate` returns generated pattern geometry + sewing instructions and persists it.
- `POST /api/pipeline/run` runs the backend photo-to-pattern pipeline:
  - accepts `imageDataUrl` (base64 data URL), `designPrompt`, and `measurements`
  - writes source upload, mannequin-free SVG render, and tiled multi-page PDF to `/home/runner/work/pyfit/pyfit/data/generated`
  - returns `mannequinFreeRenderUrl` and `patternPdfUrl` for frontend rendering/download
- `GET /api/health` returns service status.

## Payment wiring (Stripe Checkout)

- Set `STRIPE_SECRET_KEY` in the backend environment to enable checkout.
- Checkout endpoint:
  - `POST /api/payments/checkout` (requires auth, returns Stripe checkout URL)
- Confirmation endpoint:
  - `POST /api/payments/confirm` (requires auth, verifies Stripe session and credits account)
