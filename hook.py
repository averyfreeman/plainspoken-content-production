"""Check final English replies; enforce by default, preserve originals on failure.

The hook never researches a corpus, interviews a writer, or writes profiles.
Only an explicitly configured voice profile is read. Report excerpts remain
in memory on local interfaces; gateway replies are not retained. Existing media
handling and deadlines preserve the original plugin's delivery protections.
"""

from __future__ import annotations

import difflib
import logging
import math
import re
import threading
import time

from .detector import check, is_english
from .rewrite import load_voice_profile, rewrite
from .surfaces import get_surface

logger = logging.getLogger(__name__)

MODES = ("off", "report", "enforce")

DEFAULTS = {
    "mode": "enforce",
    "voice_profile": "",
    "surface": "chat",
    "platform_surfaces": {},
    "threshold": 0,
    "max_attempts": 2,
    "rewrite_timeout": 20,
    "time_budget": 25,
    "accept_partial": False,
    "min_chars": 40,
}

# Surfaces with one user per profile, where keeping the last report is not a leak.
LOCAL_PLATFORMS = {"", "cli", "tui", "desktop", "local", "acp"}
MIN_CALL_SECONDS = 3.0
MEDIA_TTL_SECONDS = 15 * 60
MEDIA_LINE = re.compile(r"^[ \t]*MEDIA:\S.*$", re.M)


def host_hook_timeout() -> float | None:
    """Hermes' plugins.hook_callback_timeout (read only); None when unknown or disabled."""
    try:
        # Reads one key of Hermes' config, read-only. load_config_readonly is not a
        # documented plugin API; if it moves, the configured budget is used as is.
        from hermes_cli.config import load_config_readonly
        value = ((load_config_readonly() or {}).get("plugins") or {}).get("hook_callback_timeout", 30)
        value = float(30 if value is None else value)
        return value if math.isfinite(value) and value > 0 else None
    except Exception:
        return None


def effective_budget(configured: float) -> float:
    """The configured budget, shrunk to stay 3 s under the host's hook timeout."""
    budget = max(5.0, configured) if math.isfinite(configured) else 25.0
    host = host_hook_timeout()
    if host is not None:
        budget = min(budget, max(1.0, host - 3.0))
    return budget


def split_media_lines(text: str) -> tuple[str, list[str]]:
    """Take MEDIA: attachment lines out of an answer; they are put back verbatim."""
    kept = [m.group(0) for m in MEDIA_LINE.finditer(text)]
    body = MEDIA_LINE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", body).strip(), kept


class Guard:
    """Holds the plugin context; one instance per loaded plugin."""

    def __init__(self, ctx=None, llm_call=None):
        self.ctx = ctx
        self._llm_call = llm_call  # tests inject a fake; Hermes uses ctx.llm
        self.last: dict | None = None
        self._media_turns: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------- tool observer
    def on_tool_result(self, tool_name: str = "", result=None, session_id: str = "", turn_id: str = "", **kwargs):
        """post_tool_call observer: remember turns in which a tool returned a MEDIA: line."""
        try:
            text = result if isinstance(result, str) else ("" if result is None else str(result))
            if "MEDIA:" not in text:
                return None
            now = time.time()
            with self._lock:
                self._media_turns[(session_id or "", str(turn_id or ""))] = now
                for key in [k for k, t in self._media_turns.items() if now - t > MEDIA_TTL_SECONDS]:
                    del self._media_turns[key]
        except Exception:
            logger.debug("plainspoken: tool observer failed", exc_info=True)
        return None

    def media_this_turn(self, session_id: str, turn_id) -> bool:
        now = time.time()
        sid, tid = session_id or "", str(turn_id or "")
        with self._lock:
            if tid:
                t = self._media_turns.get((sid, tid))
                return t is not None and now - t <= MEDIA_TTL_SECONDS
            return any(k[0] == sid and now - t <= MEDIA_TTL_SECONDS for k, t in self._media_turns.items())

    # ------------------------------------------------------------ settings
    def setting(self, key: str):
        default = DEFAULTS[key]
        if self.ctx is None:
            return default
        try:
            value = self.ctx.get_config(key, default)
        except Exception:
            return default
        return default if value is None else value

    def settings(self) -> dict:
        mode = str(self.setting("mode")).strip().lower()
        if mode not in MODES:
            logger.warning("plainspoken: unknown mode %r, using 'report'", mode)
            mode = "report"
        return {
            "mode": mode,
            "surface": str(self.setting("surface") or "chat"),
            "voice_profile": str(self.setting("voice_profile") or ""),
            "platform_surfaces": dict(self.setting("platform_surfaces") or {}),
            "threshold": int(self.setting("threshold") or 0),
            "max_attempts": max(1, min(3, int(self.setting("max_attempts") or 2))),
            "rewrite_timeout": max(1.0, min(float(self.setting("rewrite_timeout") or 20), 120.0)),
            "time_budget": effective_budget(float(self.setting("time_budget") or 25)),
            "accept_partial": self.setting("accept_partial") is True,
            "min_chars": max(0, int(self.setting("min_chars"))),
        }

    def surface_for(self, platform: str, conf: dict) -> str:
        surface = conf["platform_surfaces"].get(platform or "") or conf["surface"]
        try:
            return get_surface(surface).name
        except (ValueError, AttributeError):
            return "chat"

    # ----------------------------------------------------------------- llm
    def llm(self, messages: list[dict], max_tokens: int, timeout: float) -> str:
        if self._llm_call is not None:
            return self._llm_call(messages)
        result = self.ctx.llm.complete(
            messages=messages, max_tokens=max_tokens, temperature=0.2, timeout=timeout,
            purpose="plainspoken.rewrite",
        )
        return result.text or ""

    # ---------------------------------------------------------------- hook
    def on_output(self, response_text: str = "", session_id: str = "", model: str = "",
                  platform: str = "", **kwargs):
        """Return a replacement string, or None to leave the answer unchanged."""
        try:
            return self._on_output(response_text, platform, session_id, kwargs.get("turn_id"))
        except Exception:  # never break the turn
            logger.warning("plainspoken: check failed; answer left unchanged", exc_info=True)
            return None

    def _on_output(self, text: str, platform: str, session_id: str = "", turn_id=None):
        started = time.monotonic()
        if (platform or "") not in LOCAL_PLATFORMS:
            self.last = None
        conf = self.settings()
        if conf["mode"] == "off" or not text or len(text) < conf["min_chars"] or not is_english(text):
            return None
        surface = self.surface_for(platform, conf)
        report = check(text, surface, conf["threshold"] or None)
        record = {
            "at": int(time.time()), "platform": platform or "", "mode": conf["mode"],
            "report": report.to_dict(max_findings=30),
        }
        logger.info("plainspoken: %s score=%d threshold=%d findings=%d mode=%s",
                    surface, report.score, report.threshold, len(report.findings), conf["mode"])
        replacement = None
        if conf["mode"] == "enforce" and report.needs_rewrite and self.media_this_turn(session_id, turn_id):
            record["rewrite"] = {"changed": False, "attempts": 0, "score_before": report.score, "score_after": None,
                                 "threshold": report.threshold, "rejected": [],
                                 "reason": "skipped: a tool returned media this turn (attachments come first)"}
            logger.info("plainspoken: rewrite skipped, a tool returned media this turn")
        elif conf["mode"] == "enforce" and report.needs_rewrite:
            body, media = split_media_lines(text)
            max_tokens = min(8000, 2 * len(text) + 600)
            deadline = started + conf["time_budget"]

            def call(msgs):
                left = deadline - time.monotonic()
                if left < MIN_CALL_SECONDS:
                    raise TimeoutError("plainspoken time budget spent")
                return self.llm(msgs, max_tokens, min(conf["rewrite_timeout"], left - 1.0))

            body_report = check(body, surface, conf["threshold"] or None) if media else report
            try:
                voice_profile = load_voice_profile(conf["voice_profile"])
            except (OSError, UnicodeError, ValueError):
                record["rewrite"] = {"changed": False, "attempts": 0,
                                     "score_before": report.score, "score_after": None,
                                     "threshold": report.threshold, "rejected": [],
                                     "reason": "kept original: selected voice profile unavailable, empty or oversized"}
                if (platform or "") in LOCAL_PLATFORMS:
                    self.remember(record)
                logger.warning("plainspoken: selected voice profile could not be used")
                return None
            outcome = rewrite(body, llm=call, surface=surface, threshold=conf["threshold"] or None,
                              max_attempts=conf["max_attempts"], report=body_report,
                              voice_profile=voice_profile)
            record["rewrite"] = outcome.to_dict()
            if outcome.changed and time.monotonic() > deadline:
                record["rewrite"].update(changed=False, reason="abandoned: finished after the time budget")
            elif outcome.changed and outcome.after.needs_rewrite and not conf["accept_partial"]:
                record["rewrite"].update(changed=False, reason="kept original: the rewrite is still over the threshold "
                                                               "(set accept_partial: true to deliver it)")
            elif outcome.changed:
                replacement = outcome.text.rstrip() + ("\n\n" + "\n".join(media) if media else "")
            if replacement is not None and (platform or "") in LOCAL_PLATFORMS:
                record["rewrite"]["diff"] = list(difflib.unified_diff(
                    body.splitlines(), outcome.text.splitlines(), "before", "after", lineterm="", n=0))[:60]
            record["rewrite"]["seconds"] = round(time.monotonic() - started, 2)
            logger.info("plainspoken: rewrite %s (%s -> %s) in %.1fs", record["rewrite"]["reason"],
                        outcome.before.score, outcome.after.score if outcome.after else "-",
                        record["rewrite"]["seconds"])
        if (platform or "") in LOCAL_PLATFORMS:
            self.remember(record)
        return replacement

    def remember(self, record: dict) -> None:
        """Keep the latest local report in this process only (never on disk, never shared)."""
        self.last = record

    def recall(self) -> dict | None:
        return self.last
