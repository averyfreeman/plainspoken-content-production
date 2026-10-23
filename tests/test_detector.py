"""Behavioral coverage for English eligibility, positions and conservative rules."""
import json
import pytest
from conftest import load_module

det = load_module("detector")
rules = load_module("rules")
surfaces = load_module("surfaces")
FLAGGED = "Great question! It's important to note that we could send the report on Friday. I hope this helps."
GOOD = "We could send the report on Friday."


def ids(report):
    return {f.rule for f in report.findings}


def test_positioned_report_is_deterministic_and_bounded():
    text = "Hi Maya,\n\n" + FLAGGED
    a = det.check(text)
    assert a.verdict == "rewrite" and 40 <= a.score <= 100
    assert a.to_dict() == det.check(text).to_dict()
    assert {"sycophancy.great_question", "stock.note", "stock.hope_helpful"} <= ids(a)
    for f in a.findings:
        assert 0 <= f.start < f.end <= len(text)
        assert f.line == text.count("\n", 0, f.start) + 1
        assert f.col == f.start - text.rfind("\n", 0, f.start)
    report = a.to_dict(1)
    assert len(report["findings"]) == 1 and report["findings_total"] == len(a.findings)
    assert report["words"] > 0 and report["chars"] == len(text)


@pytest.mark.parametrize("text", [
    GOOD, "Thanks, Maya. I'll send the draft tomorrow. Does Friday work for you?",
    "The estimator is robust to outliers; use the median—it's less sensitive to noise.",
    "We need to underscore the same field twice in this example.",
    "This isn't a cache; it's a queue. The distinction changes how retries work.",
    "The tapestry was made in 1910. Its colors have faded.",
    "I like the awkward pause here. I like the second pause too. I like how it reads aloud.",
])
def test_real_voice_and_precise_terms_do_not_trigger_rewriting(text):
    r = det.check(text)
    assert r.english and r.verdict == "ok"


def test_punctuation_vocabulary_and_rhythm_are_advisory_only():
    text = "The robust estimator works—use it here. The robust estimator handles noise; keep it. The robust estimator is stable. The robust estimator takes time."
    r = det.check(text)
    assert {"format.dash", "format.semicolon", "rhythm.openers", "rhythm.uniform"} <= ids(r)
    assert r.score == 0 and not any(f.counted for f in r.findings)


@pytest.mark.parametrize("text", [
    "これは日本語の文章です。明日の会議についてお知らせします。資料を確認してください。",
    "Voici les informations concernant votre demande. Nous vous répondrons demain.",
    "```python\nmessage = 'Great question! I hope this helps.'\n```",
    "```text\nGreat question! This is an unclosed fence.",
    json.dumps({"text": FLAGGED}), '"Great question! I hope this helps."',
    "> Great question! I hope this helps.", "", "12345",
])
def test_nonprose_and_unsupported_languages_are_skipped(text):
    r = det.check(text)
    assert r.verdict == "unsupported_language" and not r.findings


def test_protected_spans_and_apostrophes():
    text = '''We don't change quotes such as "Great question!" or ‘I hope this helps.’.
`Great question!` is an example.
````text
Great question!
```
I hope this helps.
````
> It's important to note that this is a quote.
| Great question! | I hope this helps. |
See https://example.org/Great-question! for the original.
'''
    r = det.check(text)
    assert not any(f.counted for f in r.findings)
    assert det.is_english("It's important to note that we can't send it until Friday.")


def test_sentence_boundaries_handle_abbreviations_initials_and_decimals():
    text = "Dr. Maya spoke to J. Rivera at 10.30 a.m. on Friday. The cost is $12.50. We don't need a new estimate."
    sentences = det.split_sentences(text)
    assert len(sentences) == 3
    assert sentences[0].text.endswith("Friday.")
    for s in sentences:
        assert text[s.start:s.end] == s.text


def test_quotations_with_contractions_and_multiline_double_quotes_are_data():
    text = '''We keep 'It's important to note that we don't ship early.' unchanged.
We also keep “Great question!
I hope this helps.” as quoted text. It stays as written.'''
    r = det.check(text)
    assert not any(f.counted for f in r.findings)


def test_repetition_caps_contributions_but_keeps_findings():
    r = det.check("\n".join(["I hope this helps."] * 8))
    hits = [f for f in r.findings if f.rule == "stock.hope_helpful"]
    assert len(hits) == 8 and sum(f.counted for f in hits) == 2
    once = det.check("Furthermore, the report is ready for review.")
    assert "stock.transitions" not in ids(once)


def test_context_thresholds_and_aliases():
    text = "This is a game-changing release with unparalleled support."
    assert det.check(text, "external").score > det.check(text, "chat").score
    assert surfaces.get_surface("social").name == "sns"
    assert surfaces.get_surface("EMAIL").name == "business_email"
    assert det.check(FLAGGED, threshold=99).verdict == "ok"
    with pytest.raises(ValueError):
        det.check(FLAGGED, "fax")
    with pytest.raises(ValueError):
        det.check(FLAGGED, threshold=-1)


def test_catalog_integrity():
    assert len({r.id for r in rules.RULES}) == len(rules.RULES)
    for r in rules.RULES:
        assert r.category in rules.CATEGORIES and r.label and r.hint and r.weight > 0
