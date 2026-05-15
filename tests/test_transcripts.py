from evidrai.transcripts import _caption_candidates, clean_vtt_transcript


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
