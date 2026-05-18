from __future__ import annotations

import re
import os
from typing import Any, Dict, List, Tuple

import requests


def _youtube_proxy_settings() -> Dict[str, Any]:
    """Read non-secret proxy configuration for YouTube transcript extraction.

    Render/serverless IPs are commonly blocked by YouTube even when the same
    extraction path works from Streamlit or a local machine. Keep this explicit:
    do not silently use global HTTPS_PROXY, and do not require user cookies.
    """
    generic = (os.getenv("YOUTUBE_TRANSCRIPT_PROXY_URL") or "").strip()
    http_url = (os.getenv("YOUTUBE_TRANSCRIPT_HTTP_PROXY") or generic).strip()
    https_url = (os.getenv("YOUTUBE_TRANSCRIPT_HTTPS_PROXY") or generic).strip()
    webshare_username = (os.getenv("YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME") or "").strip()
    webshare_password = (os.getenv("YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD") or "").strip()
    webshare_locations = [
        item.strip().upper()
        for item in (os.getenv("YOUTUBE_TRANSCRIPT_WEBSHARE_LOCATIONS") or "").split(",")
        if item.strip()
    ]
    return {
        "http_url": http_url,
        "https_url": https_url,
        "webshare_username": webshare_username,
        "webshare_password": webshare_password,
        "webshare_locations": webshare_locations,
    }


def _requests_proxy_dict() -> Dict[str, str]:
    settings = _youtube_proxy_settings()
    proxies: Dict[str, str] = {}
    if settings["http_url"]:
        proxies["http"] = settings["http_url"]
    if settings["https_url"]:
        proxies["https"] = settings["https_url"]
    return proxies


def _yt_dlp_proxy_url() -> str:
    settings = _youtube_proxy_settings()
    return settings["https_url"] or settings["http_url"] or ""


def _youtube_transcript_proxy_config():
    settings = _youtube_proxy_settings()
    try:
        from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig
    except Exception:
        return None

    if settings["webshare_username"] and settings["webshare_password"]:
        return WebshareProxyConfig(
            proxy_username=settings["webshare_username"],
            proxy_password=settings["webshare_password"],
            filter_ip_locations=settings["webshare_locations"] or None,
        )
    if settings["http_url"] or settings["https_url"]:
        return GenericProxyConfig(http_url=settings["http_url"] or None, https_url=settings["https_url"] or None)
    return None


def clean_vtt_transcript(text: str) -> str:
    """Convert VTT/SRT-ish captions into readable plain transcript text."""
    lines: List[str] = []
    previous = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith(("WEBVTT", "NOTE", "KIND:", "LANGUAGE:")):
            continue
        if re.match(r"^\d+$", line):
            continue
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&amp;", "&", line)
        line = re.sub(r"&lt;", "<", line)
        line = re.sub(r"&gt;", ">", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines).strip()


def clean_pasted_youtube_transcript(text: str) -> str:
    """Clean transcript text copied from YouTube's transcript side panel.

    YouTube copy/paste commonly alternates timestamp lines and caption lines,
    e.g. "0:04" then "thank you everybody", or puts timestamp and text on the
    same line. This keeps useful timestamps while making the text suitable for
    claim extraction.
    """
    cleaned_blocks: List[str] = []
    pending_time = ""
    previous_text = ""
    timestamp_re = re.compile(r"^(?:(\d{1,2}:)?\d{1,2}:\d{2})$")
    inline_timestamp_re = re.compile(r"^(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})\s+(?P<text>.+)$")

    for raw in (text or "").splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        if not line:
            continue
        if line.lower() in {"transcript", "show transcript", "chapters", "key moments"}:
            continue

        inline = inline_timestamp_re.match(line)
        if inline:
            pending_time = inline.group("ts")
            line = inline.group("text").strip()
        elif timestamp_re.match(line):
            pending_time = line
            continue

        line = re.sub(r"\[music\]|\[applause\]|\(applause\)", "", line, flags=re.I).strip()
        if not line or line == previous_text:
            continue

        if pending_time:
            cleaned_blocks.append(f"[{pending_time}] {line}")
            pending_time = ""
        else:
            cleaned_blocks.append(line)
        previous_text = line

    return "\n".join(cleaned_blocks).strip()


def _caption_candidates(tracks: Dict[str, List[Dict[str, Any]]], preferred_langs: Tuple[str, ...]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    usable_tracks = {key: value for key, value in tracks.items() if key.lower() not in {"live_chat", "comments"}}
    for lang in preferred_langs:
        for key, formats in usable_tracks.items():
            if key == lang or key.startswith(lang + "-") or key.startswith(lang + "."):
                candidates.extend(formats or [])
    if not candidates:
        for _, formats in usable_tracks.items():
            candidates.extend(formats or [])
    candidates = [
        item for item in candidates
        if (item.get("ext") or "").lower() in {"vtt", "srv3", "ttml", "srt"}
        and "live_chat" not in (item.get("url") or "").lower()
    ]
    candidates.sort(key=lambda item: 0 if item.get("ext") in {"vtt", "srt"} else 1)
    return candidates




def transcript_backend_status() -> Dict[str, Any]:
    status: Dict[str, Any] = {}
    proxy_settings = _youtube_proxy_settings()
    status["proxy_configured"] = bool(proxy_settings["http_url"] or proxy_settings["https_url"] or (proxy_settings["webshare_username"] and proxy_settings["webshare_password"]))
    status["generic_proxy_configured"] = bool(proxy_settings["http_url"] or proxy_settings["https_url"])
    status["webshare_proxy_configured"] = bool(proxy_settings["webshare_username"] and proxy_settings["webshare_password"])
    status["webshare_location_filter_configured"] = bool(proxy_settings["webshare_locations"])
    try:
        import youtube_transcript_api  # type: ignore
        status["youtube_transcript_api"] = True
        status["youtube_transcript_api_version"] = getattr(youtube_transcript_api, "__version__", "unknown")
    except Exception as exc:
        status["youtube_transcript_api"] = False
        status["youtube_transcript_api_error"] = str(exc)
    try:
        import yt_dlp  # type: ignore
        status["yt_dlp"] = True
        status["yt_dlp_version"] = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
    except Exception as exc:
        status["yt_dlp"] = False
        status["yt_dlp_error"] = str(exc)
    return status

def youtube_video_id(url: str) -> str:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([A-Za-z0-9_-]{6,})",
        r"[?&]v=([A-Za-z0-9_-]{6,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url or "")
        if match:
            return match.group(1)
    return ""


def _extract_with_youtube_transcript_api(url: str, preferred_langs: Tuple[str, ...]) -> Dict[str, Any]:
    video_id = youtube_video_id(url)
    if not video_id:
        return {"ok": False, "code": "youtube_video_id_missing", "error": "Could not identify the YouTube video ID."}
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return {"ok": False, "code": "youtube_transcript_api_missing", "error": "youtube-transcript-api is not installed."}

    try:
        fetched = YouTubeTranscriptApi(proxy_config=_youtube_transcript_proxy_config()).fetch(video_id, languages=list(preferred_langs))
    except Exception as exc:
        return {"ok": False, "code": "youtube_transcript_api_failed", "error": str(exc)}

    lines: List[str] = []
    for item in fetched:
        text = getattr(item, "text", "") or ""
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
    transcript = "\n".join(lines).strip()
    if not transcript:
        return {"ok": False, "code": "youtube_transcript_empty", "error": "YouTube transcript API returned an empty transcript."}
    return {"ok": True, "language": "YouTube transcript", "transcript": transcript}


def diagnose_youtube_transcript(url: str, preferred_langs: Tuple[str, ...] = ("en", "en-US", "en-GB")) -> Dict[str, Any]:
    """Return non-secret transcript extraction diagnostics without full transcript text."""
    api_result = _extract_with_youtube_transcript_api(url, preferred_langs)
    combined = extract_youtube_transcript(url, preferred_langs)

    def safe_result(result: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ok": bool(result.get("ok")),
            "code": result.get("code") or "",
            "title": result.get("title") or "",
            "language": result.get("language") or "",
            "transcript_chars": len(result.get("transcript") or ""),
        }
        if result.get("error"):
            payload["error"] = str(result.get("error"))[:1000]
        if result.get("developer_detail"):
            payload["developer_detail"] = str(result.get("developer_detail"))[:1500]
        return payload

    return {
        "ok": bool(combined.get("ok")),
        "video_id": youtube_video_id(url),
        "backends": transcript_backend_status(),
        "youtube_transcript_api": safe_result(api_result),
        "combined_extraction": safe_result(combined),
    }

def extract_youtube_transcript(url: str, preferred_langs: Tuple[str, ...] = ("en", "en-US", "en-GB")) -> Dict[str, Any]:
    """Try to extract YouTube captions without downloading the video.

    Returns a stable payload with ok/error rather than raising so the UI can fall
    back cleanly to manual transcript paste.
    """
    transcript_api_result = _extract_with_youtube_transcript_api(url, preferred_langs)
    if transcript_api_result.get("ok"):
        return transcript_api_result

    try:
        from yt_dlp import YoutubeDL
    except Exception:
        return {"ok": False, "error": "Automatic transcript extraction is unavailable. Paste the transcript manually and run the speech/video audit again.", "developer_detail": transcript_api_result.get("error", "yt-dlp is not installed")}

    try:
        ydl_options = {"skip_download": True, "quiet": True, "no_warnings": True}
        proxy_url = _yt_dlp_proxy_url()
        if proxy_url:
            ydl_options["proxy"] = proxy_url
        with YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raw_error = str(exc)
        if "Sign in to confirm" in raw_error or "not a bot" in raw_error or "cookies" in raw_error:
            return {
                "ok": False,
                "code": "youtube_bot_check",
                "error": "YouTube blocked automatic transcript access for this video. Paste the transcript into the Transcript box and run the speech/video audit again.",
                "developer_detail": f"youtube-transcript-api: {transcript_api_result.get('error', '')}; yt-dlp: {raw_error}",
            }
        return {
            "ok": False,
            "code": "youtube_inspection_failed",
            "error": "Evidrai could not inspect this YouTube URL automatically. Paste the transcript manually, or try another video with accessible captions.",
            "developer_detail": f"youtube-transcript-api: {transcript_api_result.get('error', '')}; yt-dlp: {raw_error}",
        }

    subtitles = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    tracks = subtitles or automatic
    if not tracks:
        return {
            "ok": False,
            "title": info.get("title", ""),
            "code": transcript_api_result.get("code") or "youtube_no_accessible_captions",
            "error": "No accessible YouTube captions were found for this video. Paste a transcript manually, or use audio transcription outside the app.",
            "developer_detail": transcript_api_result.get("error", ""),
        }

    candidates = _caption_candidates(tracks, preferred_langs)
    if not candidates:
        return {
            "ok": False,
            "title": info.get("title", ""),
            "error": "No usable caption transcript was found. YouTube only exposed non-transcript data such as live chat, or the captions are unavailable to automated tools.",
        }

    for candidate in candidates:
        caption_url = candidate.get("url")
        if not caption_url:
            continue
        try:
            response = requests.get(caption_url, timeout=20, proxies=_requests_proxy_dict() or None)
            response.raise_for_status()
        except Exception:
            continue
        transcript = clean_vtt_transcript(response.text)
        if transcript:
            return {
                "ok": True,
                "title": info.get("title", ""),
                "language": candidate.get("name") or candidate.get("ext") or "caption",
                "transcript": transcript,
            }

    return {
        "ok": False,
        "title": info.get("title", ""),
        "error": "Caption tracks were listed, but Evidrai could not download a usable transcript from them.",
    }
