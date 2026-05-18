from evidrai.transcripts import _caption_candidates, _requests_proxy_dict, _yt_dlp_proxy_url, clean_pasted_youtube_transcript, clean_vtt_transcript, transcript_backend_status


def test_clean_vtt_transcript_removes_timestamps_tags_and_duplicates():
    raw = """WEBVTT

00:00:01.000 --> 00:00:02.000
<v Speaker>We created 10 million jobs</v>

00:00:02.000 --> 00:00:03.000
We created 10 million jobs

00:00:03.000 --> 00:00:04.000
&ldquo;Actually &amp; importantly&rdquo;
"""

    cleaned = clean_vtt_transcript(raw)

    assert "WEBVTT" not in cleaned
    assert "-->" not in cleaned
    assert cleaned.splitlines()[0] == "We created 10 million jobs"
    assert cleaned.count("We created 10 million jobs") == 1
    assert "&" in cleaned


def test_caption_candidates_excludes_live_chat_json():
    candidates = _caption_candidates(
        {
            "live_chat": [{"ext": "json", "url": "https://youtube.com/live_chat_replay"}],
            "en": [{"ext": "vtt", "url": "https://example.com/captions.vtt"}],
        },
        ("en",),
    )

    assert candidates == [{"ext": "vtt", "url": "https://example.com/captions.vtt"}]


def test_clean_pasted_youtube_transcript_preserves_timestamps_and_removes_noise():
    raw = """Transcript
0:04
thank you everybody
0:06 thank you everybody
0:08
[Applause]
0:12
we created 10 million jobs
"""

    cleaned = clean_pasted_youtube_transcript(raw)

    assert "Transcript" not in cleaned
    assert "[0:04] thank you everybody" in cleaned
    assert cleaned.count("thank you everybody") == 1
    assert "Applause" not in cleaned
    assert "[0:12] we created 10 million jobs" in cleaned


def test_youtube_proxy_env_is_explicit(monkeypatch):
    monkeypatch.delenv("YOUTUBE_TRANSCRIPT_PROXY_URL", raising=False)
    monkeypatch.delenv("YOUTUBE_TRANSCRIPT_HTTP_PROXY", raising=False)
    monkeypatch.delenv("YOUTUBE_TRANSCRIPT_HTTPS_PROXY", raising=False)
    monkeypatch.delenv("YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME", raising=False)
    monkeypatch.delenv("YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://global-proxy.example:8080")

    assert _requests_proxy_dict() == {}
    assert _yt_dlp_proxy_url() == ""

    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_PROXY_URL", "http://youtube-proxy.example:8080")

    assert _requests_proxy_dict() == {
        "http": "http://youtube-proxy.example:8080",
        "https": "http://youtube-proxy.example:8080",
    }
    assert _yt_dlp_proxy_url() == "http://youtube-proxy.example:8080"
    assert transcript_backend_status()["generic_proxy_configured"] is True
