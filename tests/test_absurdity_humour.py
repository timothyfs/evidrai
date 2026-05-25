from evidrai.pipeline.verification import run_quick_pass


class FakeSearch:
    configured = False


class FakeLLM:
    configured = True

    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, *_args, **_kwargs):
        return self.payload


def test_absurdity_humour_gets_fallback_when_model_omits_it():
    result = run_quick_pass(
        "A harmless but overconfident claim",
        "general",
        FakeLLM({"verdict": "Unverified", "confidence": "Low", "tldr": "Evidence is thin.", "why_convincing": "It is not."}),
        FakeSearch(),
        output_style="absurdity_humour",
    )

    assert result["output_style"] == "absurdity_humour"
    assert result["humour_summary"].startswith("Absurdity check:")
    assert "model omitted" in result["humour_safety_note"]


def test_standard_style_never_leaks_model_humour():
    result = run_quick_pass(
        "A harmless claim",
        "general",
        FakeLLM({
            "verdict": "Unverified",
            "confidence": "Low",
            "tldr": "Evidence is thin.",
            "why_convincing": "It is not.",
            "humour_summary": "This should not appear.",
            "humour_safety_note": "Nope.",
        }),
        FakeSearch(),
        output_style="standard",
    )

    assert result["humour_summary"] == ""
    assert result["humour_safety_note"] == ""


def test_absurdity_humour_is_withheld_for_serious_harm():
    result = run_quick_pass(
        "A claim about murder statistics",
        "general",
        FakeLLM({"verdict": "Unverified", "confidence": "Low", "tldr": "Evidence is thin.", "why_convincing": "It is not."}),
        FakeSearch(),
        output_style="absurdity_humour",
    )

    assert result["humour_summary"] == ""
    assert "withheld" in result["humour_safety_note"].lower()
