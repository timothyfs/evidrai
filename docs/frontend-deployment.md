# Frontend deployment

Status: deployment prep for the thin Next.js customer frontend.

## Recommended target

Use Vercel for the first frontend deployment.

Why:

- native Next.js support
- simple GitHub integration
- good preview deployments
- no need to run a custom Node server for this first slice

## Project settings

Create a new Vercel project from the GitHub repo:

```text
timothyfs/evidrai
```

Set:

```text
Framework Preset: Next.js
Root Directory: web
Build Command: npm run build
Install Command: npm install
Output Directory: .next
```

## Environment variables

Add:

```text
NEXT_PUBLIC_API_BASE_URL=https://evidrai.onrender.com
```

This is safe to expose because it is the public browser-facing API URL. Do not add private secrets to `NEXT_PUBLIC_*` variables.

## API CORS follow-up

After Vercel gives the frontend URL, update the Render API env var:

```text
API_ALLOWED_ORIGINS=https://<vercel-app-url>,https://evidrai-i74sha2rjrzchntsofrmmc.streamlit.app,http://localhost:3000,http://127.0.0.1:3000
```

Then redeploy/restart the Render API.

Without this CORS update, browser calls from the deployed frontend may be blocked even if the API itself is healthy.

## Local validation

```bash
cd web
npm install
NEXT_PUBLIC_API_BASE_URL=https://evidrai.onrender.com npm run build
```

## Post-deploy validation

Open the Vercel URL and confirm:

- API status panel loads
- Storage shows `postgres`
- recent reports load
- a Fast claim assessment completes
- the new report appears in recent reports

## Current limitation

The frontend is intentionally thin. It currently supports single-claim assessment and report viewing. Feedback controls, shareable report routes, and speech/video audit UI come next.
