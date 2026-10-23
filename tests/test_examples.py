"""Replay synthetic English examples; validate reported metrics against fixtures."""
import json
from pathlib import Path
import pytest
from conftest import PLUGIN_DIR, load_module

det = load_module("detector")
rw = load_module("rewrite")
EXAMPLES = sorted((PLUGIN_DIR / "examples" / "rewrite").glob("*.before.txt"))


def test_examples_cover_each_context():
    assert {p.name.split("_", 1)[1].split(".")[0] for p in EXAMPLES} == {"chat", "business_email", "external", "sns", "tech_doc"}


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_recorded_example_passes_the_real_rewrite_gates(path):
    surface = path.name.split("_", 1)[1].split(".")[0]
    before = path.read_text()
    reply = path.with_name(path.name.replace(".before.txt", ".model_reply.txt")).read_text()
    out = rw.rewrite(before, lambda _: reply, surface=surface)
    assert out.changed, out.rejected
    assert out.after.score < out.before.score and not out.after.needs_rewrite


def test_english_eval_labels_are_behavioral_and_results_reproduce():
    path = PLUGIN_DIR / "eval" / "data" / "english.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert {r["label"] for r in rows} == {"needs_edit", "acceptable"}
    for row in rows:
        actual = det.check(row["text"], row["surface"]).needs_rewrite
        assert actual == (row["label"] == "needs_edit"), row["id"]


def test_portable_skill_has_no_required_hermes_imports_and_all_links_resolve():
    import re
    skill = PLUGIN_DIR / "skills" / "natural-writing"
    for p in skill.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            if "://" not in link:
                assert (p.parent / link).is_file(), link
    script = (skill / "scripts" / "corpus.py").read_text()
    assert "from hermes" not in script and "from ." not in script
