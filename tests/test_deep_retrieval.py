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


def test_acquisition_claim_builds_bounded_rumor_discovery_queries():
    queries = verification.build_rumor_discovery_queries("Cisco is buying Nutanix")

    assert len(queries) == 4
    assert any("thelayoff.com" in query for query in queries)
    assert any("glassdoor.com" in query for query in queries)
    assert all("rumor" in query for query in queries)


def test_acquisition_claim_queries_include_authoritative_discovery_targets():
    queries = verification.build_search_queries([
        SubClaim(
            id="sc_1",
            text="Cisco is buying Nutanix",
            claim_type="business",
        )
    ])

    assert any("Reuters" in query for query in queries)
    assert any("SEC filing" in query for query in queries)
    assert any("investor relations press release" in query for query in queries)


def test_non_acquisition_claim_does_not_search_rumor_forums():
    queries = verification.build_rumor_discovery_queries("Nutanix announced a new product")

    assert queries == []


def test_rumor_discovery_results_are_kept_as_context_not_evidence(monkeypatch):
    monkeypatch.setattr(verification, "SCORING_CONFIG", replace(verification.SCORING_CONFIG, max_deep_search_queries=1, max_source_summaries=10))
    fake = FakeSearch()

    sources = verification.retrieve_sources(fake, ["Cisco is buying Nutanix"], "Cisco is buying Nutanix")

    rumor_sources = [source for source in sources if source.source_role == "rumor_driver"]
    assert rumor_sources
    assert all(source.evidence_category == "rumor_amplification" for source in rumor_sources)
    assert all(source.claim_support == "mixed" for source in rumor_sources)
    assert all(source.weighted_score <= 1.8 for source in rumor_sources)
    assert any("thelayoff.com" in query for query, _max_results in fake.queries)


def test_dynamic_source_strength_promotes_sec_filings_for_acquisition_claims():
    source = verification.score_source(
        {
            "title": "Cisco Form 8-K",
            "url": "https://www.sec.gov/Archives/edgar/data/858877/0001193125-26-000001.htm",
            "snippet": "Cisco announced an acquisition agreement for Nutanix.",
            "content": "Cisco announced an acquisition agreement to buy Nutanix and filed the transaction details.",
        },
        "Cisco is buying Nutanix",
    )

    assert source.source_type == "legal"
    assert source.authority_score == 5.0
    assert source.independence_score >= 4.7
    assert source.bias_risk_score <= 1.2
    assert source.weighted_score >= 4.0


def test_dynamic_source_strength_promotes_claim_company_investor_pages():
    source = verification.score_source(
        {
            "title": "Cisco newsroom update",
            "url": "https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2026/m08/cisco-investor-relations.html",
            "snippet": "Cisco and Nutanix announced a partnership update.",
            "content": "Cisco and Nutanix announced a partnership update, not an acquisition agreement.",
        },
        "Cisco is buying Nutanix",
    )

    assert source.source_type == "primary"
    assert source.authority_score >= 4.7
    assert source.directness_score >= 4.4
    assert source.bias_risk_score <= 2.2


def test_dynamic_source_strength_keeps_workplace_forums_weak():
    source = verification.score_source(
        {
            "title": "Cisco buying Nutanix rumours",
            "url": "https://www.thelayoff.com/t/rumor-cisco-nutanix",
            "snippet": "Employees discuss a rumour that Cisco may buy Nutanix.",
            "content": "Anonymous employee discussion about a possible acquisition rumour.",
        },
        "Cisco is buying Nutanix",
    )

    assert source.source_type == "forum"
    assert source.authority_score <= 1.4
    assert source.independence_score <= 1.6
    assert source.bias_risk_score >= 4.3
