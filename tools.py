"""JSON tool handler and readable slash-command reports."""
from __future__ import annotations
import json
from .detector import check
from .surfaces import SURFACE_LABELS, get_surface


def writing_check(args: dict, **kwargs) -> str:
    try:
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        text = args.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a nonempty string")
        cap = max(1, min(200, int(args.get("max_findings", 30))))
        return json.dumps(check(text, args.get("surface")).to_dict(cap), ensure_ascii=False)
    except (ValueError, TypeError) as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        return json.dumps({"error": f"check failed: {type(exc).__name__}"})


def format_report(data: dict, limit: int = 10) -> str:
    lines = [data.get("summary", "")]
    for f in data.get("findings", [])[:limit]:
        mark = "" if f.get("counted", True) else " (advisory)"
        lines += [f"- {f['line']}:{f['col']} {f['label']}{mark}: {f['excerpt']}", f"  Suggestion: {f['hint']}"]
    more = data.get("findings_total", 0) - min(limit, len(data.get("findings", [])))
    if more > 0:
        lines.append(f"({more} more findings)")
    return "\n".join(lines)


USAGE = "Usage: /writing-check [surface] <text>\nSurfaces: " + ", ".join(f"{k} ({v})" for k, v in SURFACE_LABELS.items()) + ".\nOmit the text to show the last local answer's report. Aliases include email, social and docs."


def make_command(guard):
    def handler(raw_args: str = "") -> str:
        raw = (raw_args or "").strip()
        if raw in ("help", "-h", "--help"):
            return USAGE
        if not raw:
            last = guard.recall()
            if not last:
                return "No checked answer on this screen yet. Reports are not retained on shared gateways.\n" + USAGE
            out = [f"Last answer (mode: {last['mode']})", format_report(last["report"])]
            rw = last.get("rewrite")
            if rw:
                out.append(f"Rewrite: {rw['reason']} ({rw['score_before']} -> {rw['score_after']})")
                if rw.get("diff"):
                    out += ["Changed lines:", *rw["diff"]]
            return "\n".join(out)
        surface = None
        pieces = raw.split(maxsplit=1)
        if len(pieces) == 2:
            try:
                surface = get_surface(pieces[0]).name
                raw = pieces[1]
            except ValueError:
                pass
        return format_report(check(raw, surface).to_dict())
    return handler
