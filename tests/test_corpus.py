"""Source inventory, evidence freshness and independent subject libraries."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from conftest import PLUGIN_DIR

SCRIPT = PLUGIN_DIR / "skills" / "natural-writing" / "scripts" / "corpus.py"
spec = importlib.util.spec_from_file_location("corpus", SCRIPT)
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


def setup_library(tmp_path):
    source = tmp_path / "original.md"
    source.write_text("We tried the slow way first.\nIt worked, eventually.\n", encoding="utf-8")
    library = corpus.Library(tmp_path / "library", "alex-rivera")
    library.inventory([source], author="Alex Rivera", authorship="confirmed", name="Alex Rivera")
    return library, source, next(iter(library.entries()))


def test_full_inventory_deduplicates_without_claiming_every_file_was_read(tmp_path):
    folder = tmp_path / "writing"
    folder.mkdir()
    (folder / "a.md").write_text("We sent the report on Friday.")
    (folder / "copy.txt").write_text("We sent the report on Friday.")
    (folder / "old.docx").write_bytes(b"not a text export")
    (folder / ".git").mkdir()
    (folder / ".git" / "secret.txt").write_text("ignored")
    (folder / "linked.md").symlink_to(folder / "a.md")
    library = corpus.Library(tmp_path / "library", "alex")
    result = library.inventory([folder], authorship="confirmed")
    assert result["sources"] == 4 and result["duplicates"] == 1
    assert result["access"] == {"available": 2, "needs_export": 2}
    assert result["reading"] == {"indexed": 4}
    sample = library.sample()
    assert len(sample) == 1 and sample[0]["authorship"] == "confirmed"


def test_incremental_updates_invalidate_coverage_and_profiles(tmp_path):
    library, source, sid = setup_library(tmp_path)
    assert "1: We tried" in library.read(sid)
    library.mark_read(sid, "full", "Read the whole two-line sample")
    draft = tmp_path / "profile.md"
    draft.write_text(f"# Alex Rivera\nTentative: uses plain sentences. Evidence source:{sid}:L1-L2.\n")
    saved = library.save_profile(draft)
    assert Path(saved).is_file() and not library.status()["profile_stale"]
    library.inventory([])
    assert library.entries()[sid]["read_status"] == "full"
    assert not library.status()["profile_stale"]
    source.write_text("We changed the whole argument.\n")
    with pytest.raises(ValueError, match="source changed"):
        library.read(sid)
    with pytest.raises(ValueError, match="source changed"):
        library.save_profile(draft)
    library.inventory([])
    assert library.status()["profile_stale"] and library.entries()[sid]["read_status"] == "indexed"
    source.unlink()
    library.inventory([])
    assert library.entries()[sid]["access"] == "unavailable"


def test_remote_exports_roles_unknown_authorship_and_access_are_explicit(tmp_path):
    exported = tmp_path / "post.txt"
    exported.write_text("We tried this in April.\nWe kept the awkward sentence.")
    manifest = tmp_path / "manifest.jsonl"
    rows = [
        {"locator": "https://example.org/post", "text_path": "post.txt", "role": "voice", "author": "Alex", "authorship": "confirmed", "published_at": "2025-04-02", "medium": "newsletter"},
        {"locator": "drive://reference", "text_path": "post.txt", "role": "reference", "authorship": "confirmed"},
        {"locator": "drive://missing", "access_note": "Permission unavailable", "role": "reference"},
        {"locator": "https://example.org/uncertain", "text_path": "post.txt", "role": "voice"},
    ]
    manifest.write_text("\n".join(json.dumps(row) for row in rows))
    library = corpus.Library(tmp_path / "library", "alex")
    status = library.inventory([], [manifest])
    assert status["sources"] == 4 and status["access"]["unavailable"] == 1
    assert all(row.get("published_at") is None for row in library.entries().values() if row["locator"] != "https://example.org/post")
    # Duplicate identity must not let uncertain authorship erase a confirmed sample.
    sample = library.sample()
    assert len(sample) == 1 and sample[0]["locator"] == "https://example.org/post"


def test_sampling_spreads_over_media_periods_and_lengths(tmp_path):
    manifest = tmp_path / "sources.jsonl"
    rows = []
    for medium in ("email", "newsletter", "social"):
        for year in (2024, 2026):
            for n in (5, 15, 30):
                p = tmp_path / f"{medium}-{year}-{n}.txt"
                p.write_text(f"{medium} {year} " + "words " * n)
                rows.append({"locator": str(p), "text_path": str(p), "medium": medium,
                             "published_at": f"{year}-01-01", "authorship": "confirmed"})
    manifest.write_text("\n".join(json.dumps(row) for row in rows))
    library = corpus.Library(tmp_path / "library", "alex")
    library.inventory([], [manifest])
    sample = library.sample(12)
    assert len(sample) == 12
    assert {r["medium"] for r in sample} == {"email", "newsletter", "social"}
    assert {r["published_at"][:4] for r in sample} == {"2024", "2026"}


def test_profile_cannot_cite_unread_research_unconfirmed_or_other_subject(tmp_path):
    library, source, sid = setup_library(tmp_path)
    draft = tmp_path / "profile.md"
    draft.write_text(f"Evidence source:{sid}:L1-L2")
    with pytest.raises(ValueError, match="must be read"):
        library.save_profile(draft)
    library.mark_read(sid, "excerpt")
    other = corpus.Library(library.root, "other-subject")
    with pytest.raises(ValueError, match="must be read"):
        other.save_profile(draft)
    library.inventory([source], role="reference", authorship="confirmed")
    ref = next(r["id"] for r in library.entries().values() if r["role"] == "reference")
    library.mark_read(ref, "full")
    draft.write_text(f"Evidence source:{ref}:L1-L2")
    with pytest.raises(ValueError, match="must be read"):
        library.save_profile(draft)
    with pytest.raises(ValueError, match="different name"):
        library.inventory([], name="Another Alex")
    with pytest.raises(ValueError):
        corpus.Library(library.root, "../other-subject")


def test_standalone_copy_runs_without_plugin_or_hermes(tmp_path):
    standalone = tmp_path / "portable"
    shutil.copytree(SCRIPT.parent.parent, standalone)
    source = tmp_path / "sample.md"
    source.write_text("We prefer a short opening.\n")
    command = [sys.executable, str(standalone / "scripts" / "corpus.py"), "--library", str(tmp_path / "voices"), "--subject", "alex"]
    result = subprocess.run(command + ["inventory", str(source), "--authorship", "confirmed"], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["sources"] == 1
    failure = subprocess.run(command + ["read", "missing"], text=True, capture_output=True)
    assert failure.returncode == 2 and "unavailable" in failure.stderr


def test_html_normalization_and_malformed_manifests_do_not_corrupt_index(tmp_path):
    source = tmp_path / "post.html"
    source.write_text('<article><p>We said &quot;hello&quot;.</p><script>fake voice</script></article>')
    assert "fake voice" not in corpus.source_text(source)
    assert 'We said "hello".' in corpus.source_text(source)
    library = corpus.Library(tmp_path / "library", "alex")
    library.inventory([source])
    before = library.index_path.read_text()
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"role":"invalid"}')
    with pytest.raises(ValueError):
        library.inventory([], [bad])
    assert library.index_path.read_text() == before
    bad.write_text('[]')
    with pytest.raises(ValueError, match="must be objects"):
        library.inventory([], [bad])
    bad.write_text('{"locator":"test","medium":3}')
    with pytest.raises(ValueError, match="must be text"):
        library.inventory([], [bad])
    assert library.index_path.read_text() == before


def test_subject_symlinks_cannot_merge_two_libraries(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    (root / "alex").mkdir()
    (root / "other").symlink_to(root / "alex", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        corpus.Library(root, "other")
