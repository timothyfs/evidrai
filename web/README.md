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

Optional public Supabase Auth variables for Google OAuth and email magic links:

```text
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<public anon key>
```

These browser variables are public. Do not put private service-role keys, database passwords, or JWT secrets in `NEXT_PUBLIC_*` variables.

For server-side token verification on modern Supabase projects using ECC/RSA JWT signing keys, configure the Render API with:

```text
SUPABASE_URL=https://<project-ref>.supabase.co
```

Legacy HS256 projects may instead use private `SUPABASE_JWT_SECRET`, but do not use a JWT Key ID, `sb_secret_*`, service-role key, or database password.

The UI displays two build labels:

- `Frontend build`: Vercel commit short SHA, via `VERCEL_GIT_COMMIT_SHA` at build time
- `API build`: backend build reported by `/runtime`

## Current features

- runtime status from `/runtime`
- Fast/Deep single-claim assessment
- optional source URL
- verdict/confidence display
- evidence source list
- current-browser report history using localStorage
- load report by ID
- assessment feedback controls linked to the backend feedback API
- two-stage speech/video audit UI: extract claims, select claims, verify selected claims
- auth-ready account shell with browser profile ID and owner-scoped report history

## Deployment

Recommended first deployment target: Vercel.

See `../docs/frontend-deployment.md`.

## Next frontend slices

- shareable report route `/reports/[id]`
- auth-gated Free/Pro/Journalist tiers
- speech/video audit UI
- better loading/error states
- deploy to Vercel or Render static web service
