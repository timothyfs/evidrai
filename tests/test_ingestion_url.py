import pytest

from evidrai.ingestion.url import SourceExtractionError, candidate_claims_from_text, extract_source_from_html, html_to_text


HTML = """
<html>
<head>
  <title>Example story title</title>
  <meta name="description" content="The council says the bridge will reopen in June after safety repairs." />
</head>
<body>
  <nav>Navigation should disappear</nav>
  <article>
    <h1>Bridge repairs delayed</h1>
    <p>The council says the bridge will reopen in June after safety repairs.</p>
    <p>Engineers found corrosion in two supports and reported that extra work is required.</p>
    <script>bad()</script>
  </article>
</body>
</html>
"""


def test_html_to_text_removes_script_and_navigation():
    text = html_to_text(HTML)

    assert "bad()" not in text
    assert "Navigation should disappear" not in text
    assert "The council says" in text


def test_extract_source_from_html_returns_article_packet():
    result = extract_source_from_html("https://example.com/story", HTML)

    assert result.schema_version == "source_extract.v1"
    assert result.ok is True
    assert result.domain == "example.com"
    assert result.title == "Example story title"
    assert result.description == "The council says the bridge will reopen in June after safety repairs."
    assert result.word_count > 10
    assert result.candidate_claims[0] == "The council says the bridge will reopen in June after safety repairs."


def test_extract_source_rejects_invalid_url():
    with pytest.raises(SourceExtractionError):
        extract_source_from_html("example.com/story", HTML)


def test_candidate_claims_are_deduped_and_limited():
    claims = candidate_claims_from_text(
        "Short",
        "The agency says the policy will start next month.",
        "The agency says the policy will start next month. Officials reported that the pilot has ended. This is short.",
        max_claims=2,
    )

    assert claims == [
        "The agency says the policy will start next month.",
        "Officials reported that the pilot has ended.",
    ]
