# Evidrai Web

Thin customer-facing frontend for the independent Evidrai API.

Status: first slice. Streamlit remains the lab/admin UI.

## Local development

```bash
cd web
npm install
NEXT_PUBLIC_API_BASE_URL=https://evidrai.onrender.com npm run dev
```

Open:

```text
http://localhost:3000
```

## Configuration

```text
NEXT_PUBLIC_API_BASE_URL=https://evidrai.onrender.com
```

The variable is public because it is used by the browser frontend. Do not put secrets in `NEXT_PUBLIC_*` variables.

## Current features

- runtime status from `/runtime`
- Fast/Deep single-claim assessment
- optional source URL
- verdict/confidence display
- evidence source list
- current-browser report history using localStorage
- load report by ID
- assessment feedback controls linked to the backend feedback API

## Deployment

Recommended first deployment target: Vercel.

See `../docs/frontend-deployment.md`.

## Next frontend slices

- shareable report route `/reports/[id]`
- speech/video audit UI
- better loading/error states
- deploy to Vercel or Render static web service
