# Email identity and bot protection gate

Evidrai now requires a signed-in user before assessments, reports, feedback, speech extraction, or speech verification can run. This captures an email-backed identity through Supabase Auth instead of relying on anonymous browser IDs.

## Backend enforcement

The API rejects anonymous users for:

- `/claims/check`
- `/assessments/fast`
- `/assessments/deep`
- `/assessment-jobs/{mode}`
- `/speech/extract`
- `/speech/verify`
- `/speech/audit`
- `/reports`
- `/reports/{report_id}`
- assessment feedback writes

Public share links remain public through `/public/reports/{token}`.

## Turnstile configuration

Bot protection is enabled when the backend has:

```text
TURNSTILE_SECRET_KEY=<Cloudflare Turnstile secret key>
```

The frontend should also have:

```text
NEXT_PUBLIC_TURNSTILE_SITE_KEY=<Cloudflare Turnstile site key>
```

When configured, assessment and speech requests include a Turnstile token and the API verifies it with Cloudflare before running expensive checks.

## Notes

- Google sign-in still relies on the provider's own bot/abuse controls.
- Email/password sign-up is gated in the UI by Turnstile when the site key is configured.
- The real backend protection happens on assessment/speech endpoints, so bypassing the UI does not bypass the bot check once `TURNSTILE_SECRET_KEY` is configured.
