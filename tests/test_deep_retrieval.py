from dataclasses import replace

from evidrai.models import EvidenceSource
from evidrai.pipeline import verification


class FakeSearch:
    def __init__(self):
        self.queries = []

    def search(self, query, max_results=5):
        self.queries.append((query, max_results))
        return [
            {
                "title": f"Source for {query}",
                "url": f"https://example.com/{query}",
                "snippet": query,
                "content": query,
            }
        ]


def test_retrieve_sources_bounds_deep_search_query_count(monkeypatch):
    monkeypatch.setattr(verification, "SCORING_CONFIG", replace(verification.SCORING_CONFIG, max_deep_search_queries=2))
    fake = FakeSearch()

    sources = verification.retrieve_sources(fake, ["one", "two", "three", "four"], "one two")

    assert len(fake.queries) == 2
    assert all(max_results == 4 for _query, max_results in fake.queries)
    assert len(sources) == 2
    assert all(isinstance(source, EvidenceSource) for source in sources)
