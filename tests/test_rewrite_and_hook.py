"""English preservation gates, bounded rewriting and the Hermes contract."""
import json
import pytest
from conftest import load_module, load_plugin, PLUGIN_DIR
from test_detector import FLAGGED, GOOD

det = load_module("detector")
rw = load_module("rewrite")
hook = load_module("hook")
tools = load_module("tools")


class FakeLlm:
    def __init__(self, text=f"<rewritten>{GOOD}</rewritten>"):
        self.text, self.calls = text, []

    def complete(self, **kw):
        self.calls.append(kw)
        return type("Result", (), {"text": self.text})()


class FakeCtx:
    def __init__(self, settings=None, reply=f"<rewritten>{GOOD}</rewritten>"):
        self.config = settings or {}
        self.llm = FakeLlm(reply)
        self.tools, self.hooks, self.commands, self.skills = {}, {}, {}, {}

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def register_tool(self, name, **kw):
        self.tools[name] = kw

    def register_hook(self, name, handler):
        self.hooks[name] = handler

    def register_command(self, name, handler, **kw):
        self.commands[name] = handler

    def register_skill(self, name, path):
        self.skills[name] = path


def test_minimal_edit_is_accepted_without_freezing_ordinary_english_words():
    before = "It's important to note that we will perform an evaluation of the new design. I hope this helps."
    after = "We will evaluate the new design."
    out = rw.rewrite(before, lambda _: f"<rewritten>{after}</rewritten>")
    assert out.changed and out.text == after and out.after.score == 0


@pytest.mark.parametrize("old,new", [
    ("Friday", "Thursday"), ("could", "will"), ("We could", "You could"),
    ("could send", "could not send"), ("report", "report with a guaranteed discount"),
])
def test_changed_claim_controls_are_rejected(old, new):
    assert rw.guard_problems(FLAGGED, GOOD.replace(old, new), det.check(FLAGGED))


def test_factual_anchors_and_unflagged_sentences_are_preserved():
    before = 'Hi Maya,\n\nIt is important to note that we could send OpenDesk 2.1 for $1,200 on Friday at 10 AM if you approve the draft.\nPlease reply to @maya at maya@example.org.\nThe label is "Preview".\nRun `npm test`.\nSee https://example.org/docs.\n\nThanks,\nAlex Rivera\nI hope this helps.'
    good = before.replace("It is important to note that we", "We").replace("\nI hope this helps.", "")
    report = det.check(before)
    assert rw.guard_problems(before, good, report) == []
    for old, new in [("Maya", "Maria"), ("OpenDesk", "OpenDesks"), ("2.1", "2.2"),
                     ("1,200", "1,300"), ("AM", "PM"), ("if you approve the draft", "if you are eligible"),
                     ("Please reply", "You can reply"), ("@maya", "@maria"), ("Preview", "Final"),
                     ("`npm test`", "`npm run test`"), ("https://example.org/docs", "https://example.org"),
                     ("Alex Rivera", "Alex Riveras")]:
        assert rw.guard_problems(before, good.replace(old, new), report), (old, new)


def test_scoped_negation_and_modality_cannot_swap_between_sentences():
    before = "It's important to note that we can ship the report. It's worth noting that we cannot publish the draft. I hope this helps."
    good = "We can ship the report. We cannot publish the draft."
    assert not rw.guard_problems(before, good, det.check(before))
    swapped = "We cannot ship the report. We can publish the draft."
    assert rw.guard_problems(before, swapped, det.check(before))


def test_equivalent_contractions_and_genuine_requests_survive():
    before = "It's important to note that we will not ship before Friday. Please reply by Thursday. I hope this helps."
    good = "We won't ship before Friday. Please reply by Thursday."
    assert not rw.guard_problems(before, good, det.check(before))
    assert rw.guard_problems(before, good.replace("Please reply by Thursday.", ""), det.check(before))


def test_version_digits_attached_to_product_names_are_protected():
    before = "It's important to note that we use OpenDesk2.1. I hope this helps."
    good = "We use OpenDesk2.1."
    assert not rw.guard_problems(before, good, det.check(before))
    assert rw.guard_problems(before, good.replace("2.1", "3.1"), det.check(before))


def test_retries_get_rejection_feedback_and_cannot_invent_sentences():
    replies = iter([f"<rewritten>{GOOD.replace('Friday','Tuesday')}</rewritten>", f"<rewritten>{GOOD}</rewritten>"])
    calls = []
    def model(messages):
        calls.append(messages)
        return next(replies)
    result = rw.rewrite(FLAGGED, model)
    assert result.changed and result.attempts == 2 and result.rejected
    assert "previous attempt was rejected" in calls[1][1]["content"]
    assert rw.guard_problems(FLAGGED, GOOD + " We added a free upgrade.", det.check(FLAGGED))


@pytest.mark.parametrize("candidate", [
    "We could send the contract on Friday.",
    "We could send the report for free on Friday.",
    "We could send the report on Friday because approval is complete.",
])
def test_added_or_substituted_content_inside_a_flagged_sentence_is_rejected(candidate):
    assert rw.guard_problems(FLAGGED, candidate, det.check(FLAGGED))


def test_empty_malformed_failed_and_unsupported_replies_keep_the_original():
    for reply in ["", "Here you go", "<rewritten>```\ncode\n```</rewritten>", f"Extra explanation <rewritten>{GOOD}</rewritten>"]:
        out = rw.rewrite(FLAGGED, lambda _: reply)
        assert not out.changed and out.text == FLAGGED
    def boom(_):
        raise TimeoutError("slow")
    assert not rw.rewrite(FLAGGED, boom).changed
    assert not rw.rewrite(GOOD, lambda _: pytest.fail("unnecessary model call")).changed


def test_default_enforcement_and_opt_out_modes():
    ctx = FakeCtx()
    g = hook.Guard(ctx)
    assert g.on_output(response_text=FLAGGED, platform="cli") == GOOD
    assert ctx.llm.calls[0]["purpose"] == "plainspoken.rewrite"
    assert 0 < ctx.llm.calls[0]["timeout"] <= 20
    assert g.recall()["rewrite"]["changed"]
    assert "Changed lines:" in tools.make_command(g)("")
    for mode in ("report", "off"):
        ctx = FakeCtx({"mode": mode})
        guard = hook.Guard(ctx)
        assert guard.on_output(response_text=FLAGGED) is None
        assert not ctx.llm.calls


def test_short_clean_nonenglish_and_structured_outputs_skip_model():
    ctx = FakeCtx()
    g = hook.Guard(ctx)
    for text in ["Great question!", GOOD, "これは日本語の長い文章です。会議の日程は明日です。資料を確認してください。", json.dumps({"answer": FLAGGED}), "```\n" + FLAGGED + "\n```"]:
        assert g.on_output(response_text=text) is None
    assert not ctx.llm.calls


def test_gateway_reports_do_not_survive_in_shared_processes():
    g = hook.Guard(FakeCtx({"mode": "report"}))
    g.on_output(response_text=FLAGGED, platform="cli")
    assert g.recall()
    g.on_output(response_text=FLAGGED, platform="telegram")
    assert g.recall() is None
    assert hook.Guard().recall() is None


def test_media_observer_and_existing_attachment_lines():
    ctx = FakeCtx()
    g = hook.Guard(ctx)
    g.on_tool_result(result='{"media":"MEDIA:/tmp/chart.png"}', session_id="s", turn_id="a")
    assert g.on_output(response_text=FLAGGED, platform="telegram", session_id="s", turn_id="a") is None
    assert not ctx.llm.calls
    assert g.on_output(response_text=FLAGGED, platform="cli", session_id="other", turn_id="a") == GOOD
    assert g.on_output(response_text=FLAGGED + "\n\nMEDIA:/tmp/report.png", platform="cli", session_id="s", turn_id="b") == GOOD + "\n\nMEDIA:/tmp/report.png"
    assert "MEDIA:" not in ctx.llm.calls[-1]["messages"][1]["content"]


def test_timeout_abandons_late_result_without_claiming_a_delivered_diff(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(hook.time, "monotonic", lambda: clock[0])
    ctx = FakeCtx()
    def late(**kw):
        clock[0] += 60
        return type("Reply", (), {"text": f"<rewritten>{GOOD}</rewritten>"})()
    ctx.llm.complete = late
    g = hook.Guard(ctx)
    assert g.on_output(response_text=FLAGGED, platform="cli") is None
    result = g.recall()["rewrite"]
    assert not result["changed"] and result["reason"].startswith("abandoned")
    assert "diff" not in result
    monkeypatch.setattr(hook, "host_hook_timeout", lambda: 12)
    assert hook.effective_budget(25) == 9


def test_partial_rewrite_requires_explicit_setting():
    partial = "It's important to note that we could send the report on Friday."
    for accept, expected in [(False, None), (True, partial)]:
        ctx = FakeCtx({"threshold": 10, "max_attempts": 1, "accept_partial": accept}, f"<rewritten>{partial}</rewritten>")
        assert hook.Guard(ctx).on_output(response_text=FLAGGED) == expected


def test_only_selected_profile_is_loaded_and_missing_profile_falls_back(tmp_path):
    profile = tmp_path / "profile.md"
    profile.write_text("Keep my deliberate dashes and dry humor.")
    unrelated = tmp_path / "other.md"
    unrelated.write_text("PRIVATE OTHER SUBJECT")
    ctx = FakeCtx({"voice_profile": str(profile)})
    assert hook.Guard(ctx).on_output(response_text=FLAGGED) == GOOD
    prompt = str(ctx.llm.calls[0]["messages"])
    assert "deliberate dashes" in prompt and "PRIVATE OTHER SUBJECT" not in prompt
    for bad in (tmp_path / "missing.md", unrelated):
        if bad == unrelated:
            bad.write_text("x" * 16001)
        ctx = FakeCtx({"voice_profile": str(bad)})
        guard = hook.Guard(ctx)
        assert guard.on_output(response_text=FLAGGED) is None
        assert "voice profile" in guard.recall()["rewrite"]["reason"]
        assert not ctx.llm.calls


def test_settings_mapping_and_errors_never_break_a_turn():
    ctx = FakeCtx({"mode": "report", "platform_surfaces": {"mail": "email"}})
    g = hook.Guard(ctx)
    g.on_output(response_text=FLAGGED, platform="mail")
    assert g.surface_for("mail", g.settings()) == "business_email"
    for settings in [{"threshold": "bad"}, {"platform_surfaces": "bad"}, {"surface": "fax"}, {"mode": "bad"}]:
        hook.Guard(FakeCtx(settings)).on_output(response_text=FLAGGED)


def test_nonfinite_budgets_and_text_booleans_do_not_disable_limits(monkeypatch):
    monkeypatch.setattr(hook, "host_hook_timeout", lambda: None)
    assert hook.effective_budget(float("inf")) == 25
    assert hook.effective_budget(float("nan")) == 25
    g = hook.Guard(FakeCtx({"accept_partial": "false", "rewrite_timeout": -5}))
    assert g.settings()["accept_partial"] is False
    assert g.settings()["rewrite_timeout"] > 0


def test_tool_command_and_registration_match_english_manifest():
    ctx = FakeCtx({"mode": "report"})
    load_plugin().register(ctx)
    assert set(ctx.tools) == {"writing_check"}
    assert set(ctx.hooks) == {"transform_llm_output", "post_tool_call"}
    assert set(ctx.commands) == {"writing-check"} and set(ctx.skills) == {"natural-writing"}
    assert ctx.skills["natural-writing"].is_file()
    manifest = (PLUGIN_DIR / "plugin.yaml").read_text()
    assert "name: plainspoken" in manifest and "  - writing_check" in manifest
    assert "default: enforce" in manifest
    result = json.loads(tools.writing_check({"text": FLAGGED, "max_findings": 1}))
    assert result["verdict"] == "rewrite" and len(result["findings"]) == 1
    for args in (None, {}, {"text": 123}, {"text": FLAGGED, "surface": "fax"}, {"text": FLAGGED, "max_findings": []}):
        assert "error" in json.loads(tools.writing_check(args))
    cmd = ctx.commands["writing-check"]
    assert cmd("help").startswith("Usage: /writing-check")
    assert "sns threshold" in cmd("social " + FLAGGED)
    assert cmd("").startswith("No checked answer")
