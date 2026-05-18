
## Production proxy support

Render and other cloud-provider hosts can be blocked by YouTube even when the same video works from Streamlit or a local machine. Evidrai therefore supports an explicit transcript-only proxy configuration for YouTube caption lookup.

Do **not** use user browser cookies or personal YouTube account cookies on the server. That is brittle, privacy-sensitive, and risks account enforcement. Prefer either:

1. a transcript/caption provider API, or
2. a controlled rotating residential proxy used only by the transcript extractor.

### Render environment variables

Generic proxy:

```bash
YOUTUBE_TRANSCRIPT_PROXY_URL=http://user:password@host:port
```

Or split HTTP/HTTPS values:

```bash
YOUTUBE_TRANSCRIPT_HTTP_PROXY=http://user:password@host:port
YOUTUBE_TRANSCRIPT_HTTPS_PROXY=http://user:password@host:port
```

Webshare rotating residential proxy support:

```bash
YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME=...
YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD=...
YOUTUBE_TRANSCRIPT_WEBSHARE_LOCATIONS=FR,GB,US
```

`/runtime` and `/transcripts/diagnose` expose only safe booleans such as `proxy_configured`, never proxy URLs or passwords.

### Fallback behaviour

The extraction order remains:

1. `youtube-transcript-api`, now with optional proxy config.
2. `yt-dlp` caption inspection, now with optional proxy config.
3. Caption URL download through the same explicit proxy.
4. User-pasted transcript fallback.

Manual paste remains the safe fallback when a video has no captions, captions are restricted, or YouTube blocks automated access.
