from dataclasses import replace

from evidrai.models import EvidenceSource
from evidrai.models import SubClaim
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


def test_uk_claim_queries_prioritize_uk_official_sources():
    queries = verification.build_search_queries([
        SubClaim(
            id="sc_1",
            text="The UK spends more on debt interest than on defence.",
            claim_type="economic",
            jurisdiction="United Kingdom",
        )
    ])

    assert any(query.startswith("site:gov.uk") for query in queries)
    assert any("commonslibrary.parliament.uk" in query for query in queries)
    assert any("obr.uk" in query for query in queries)
    assert "gov.uk" in queries[1]


def test_wrong_country_source_is_downgraded_for_uk_claim():
    source = verification.score_source(
        {
            "title": "Interest Costs Surpass National Defense and Medicare Spending",
            "url": "https://budget.house.gov/press-release/interest-costs-surpass-national-defense-and-medicare-spending",
            "snippet": "The United States spent more on interest payments than national defense in Fiscal Year 2024.",
            "content": "The U.S. federal budget shows interest costs surpassing defense spending.",
        },
        "The UK spends more on debt interest than on defence.",
    )

    assert source.claim_support == "irrelevant"
    assert source.evidence_category == "irrelevant"
    assert source.source_role == "context"
    assert source.relevance_score <= 1.5
    assert source.weighted_score <= 2.0
    assert "Jurisdiction mismatch" in source.snippet


def test_country_guard_downgrades_other_mismatched_official_sources():
    source = verification.score_source(
        {
            "title": "Canadian defence spending update",
            "url": "https://www.canada.ca/en/department-national-defence/news/defence-spending.html",
            "snippet": "The Canadian government announced defence spending commitments.",
            "content": "Canada's federal budget includes new defence spending.",
        },
        "Australia spends more on debt interest than defence.",
    )

    assert source.claim_support == "irrelevant"
    assert source.evidence_category == "irrelevant"
    assert source.weighted_score <= 2.0


def test_non_uk_country_queries_include_country_official_sources_early():
    queries = verification.build_search_queries([
        SubClaim(
            id="sc_1",
            text="Canada spends more on debt interest than defence.",
            claim_type="economic",
            jurisdiction="Canada",
        )
    ])

    assert "canada.ca" in queries[1]
    assert any("statcan.gc.ca" in query for query in queries[:4])
