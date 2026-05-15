from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import requests


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


def extract_youtube_transcript(url: str, preferred_langs: Tuple[str, ...] = ("en", "en-US", "en-GB")) -> Dict[str, Any]:
    """Try to extract YouTube captions without downloading the video.

    Returns a stable payload with ok/error rather than raising so the UI can fall
    back cleanly to manual transcript paste.
    """
    try:
        from yt_dlp import YoutubeDL
    except Exception:
        return {"ok": False, "error": "yt-dlp is not installed, so automatic transcript extraction is unavailable."}

    try:
        with YoutubeDL({"skip_download": True, "quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        return {"ok": False, "error": f"Could not inspect this YouTube URL: {exc}"}

    subtitles = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    tracks = subtitles or automatic
    if not tracks:
        return {
            "ok": False,
            "title": info.get("title", ""),
            "error": "No accessible YouTube captions were found for this video. Paste a transcript manually, or use audio transcription outside the app.",
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
            response = requests.get(caption_url, timeout=20)
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
