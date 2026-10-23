"""Deterministic, offline English editing signals with exact source positions."""
from __future__ import annotations
import json
import math
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from .rules import RULES, STRUCTURAL
from .surfaces import Surface, get_surface

WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*(?:-[^\W\d_]+)*", re.UNICODE)
_INLINE = re.compile(r"(?<![`])(`+)(?![`])[^\n]*?\1(?![`])")
_URL = re.compile(r"https?://[^\s<>\"']+")
_QUOTES = re.compile(r'"(?:[^"\\]|\\.){1,10000}"|“[^”]{1,10000}”|(?<!\w)\x27(?:[^\x27\n]|(?<=\w)\x27(?=\w)){1,1500}\x27(?!\w)|‘(?:[^’\n]|(?<=\w)’(?=\w)){1,1500}’')
_ABBREV = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "etc", "e.g", "i.e", "a.m", "p.m", "u.s", "u.k"}
_ENGLISH = set("a an the this that these those it its is are was were be been being i i'm we we're you you're he she they them our your their my me us and or but so because if unless until with without of to for from in on at by as not no yes can could may might must will would should have has had do does did please thanks thank use using used need needs send sent change changed new now help helps question great important note hope available only all about also here there then when which what how why who more most some any each every both between after before run click install open save file read write check error version request update reply work works working first next last let make made time into don't won't can't".split())


def protected_spans(text: str) -> list[tuple[int, int, str]]:
    """Code, URLs, quotations, tables and markup are data, not editable prose."""
    spans = []
    opened = None
    offset = 0
    for line in text.splitlines(keepends=True):
        fence = re.match(r"^[ \t]*(`{3,}|~{3,})", line)
        if opened:
            marker, start = opened
            if fence and fence[1][0] == marker[0] and len(fence[1]) >= len(marker) and not line[fence.end():].strip():
                spans.append((start, offset + len(line), "code block"))
                opened = None
        elif fence:
            opened = (fence[1], offset)
        offset += len(line)
    if opened:
        spans.append((opened[1], len(text), "code block"))
    patterns = (
        (_INLINE, "inline code"), (_URL, "URL"), (_QUOTES, "quotation"),
        (re.compile(r"^[ \t]*>.*$", re.M), "quoted line"),
        (re.compile(r"^[ \t]*\|.*$", re.M), "table row"),
        (re.compile(r"<[^>\n]{1,300}>"), "HTML tag"),
    )
    for pattern, kind in patterns:
        for m in pattern.finditer(text):
            if any(s <= m.start() < e for s, e, _ in spans):
                continue
            end = m.end()
            if kind == "URL":
                while end > m.start() and text[end - 1] in ".,;!?":
                    end -= 1
                while end > m.start() and text[end - 1] in ")]":
                    close = text[end - 1]
                    if text[m.start():end].count(close) <= text[m.start():end].count({")": "(", "]": "["}[close]):
                        break
                    end -= 1
            spans.append((m.start(), end, kind))
    return sorted(spans)


def _mask(text: str) -> str:
    chars = list(text)
    for start, end, _ in protected_spans(text):
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def is_english(text: str) -> bool:
    """Conservative eligibility heuristic; not a general language classifier."""
    scan = _mask(text)
    try:
        if isinstance(json.loads(text), (dict, list, str, int, float, bool)):
            return False
    except (ValueError, TypeError):
        pass
    words = WORD.findall(scan)
    letters = [c for c in scan if c.isalpha()]
    if len(words) < 2 or not letters:
        return False
    latin = sum(c.isascii() for c in letters) / len(letters)
    signals = sum(w.lower().replace("’", "'") in _ENGLISH for w in words)
    return latin >= .75 and signals >= max(1, min(4, len(words) // 10))


@dataclass
class Sentence:
    text: str
    start: int
    end: int
    kind: str = "prose"


def split_sentences(text: str) -> list[Sentence]:
    """Keep offsets and don't split decimals, common abbreviations or initials."""
    result = []
    start = 0
    for m in re.finditer(r"[.!?]+(?:[\"”’])?(?=\s|$)|\n+", text):
        if m[0].startswith("."):
            token = re.search(r"([A-Za-z.]+)$", text[start:m.start()])
            if token and (token[1].lower() in _ABBREV or len(token[1]) == 1 or re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]", token[1])):
                continue
        end = m.end()
        chunk = text[start:end].strip()
        if chunk:
            left = start + len(text[start:end]) - len(text[start:end].lstrip())
            kind = "heading" if re.match(r"#{1,6}\s", chunk) else "list" if re.match(r"(?:[-*+] |\d+[.)] )", chunk) else "prose"
            result.append(Sentence(chunk, left, left + len(chunk), kind))
        start = end
    if text[start:].strip():
        left = start + len(text[start:]) - len(text[start:].lstrip())
        chunk = text[left:].rstrip()
        kind = "heading" if re.match(r"#{1,6}\s", chunk) else "list" if re.match(r"(?:[-*+] |\d+[.)] )", chunk) else "prose"
        result.append(Sentence(chunk, left, left + len(chunk), kind))
    return result


@dataclass
class Finding:
    rule: str
    category: str
    label: str
    hint: str
    start: int
    end: int
    line: int
    col: int
    excerpt: str
    weight: float
    counted: bool
    source: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Report:
    surface: str
    score: int
    threshold: int
    over_threshold: bool
    english: bool
    chars: int
    words: int = 0
    findings: list[Finding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    register_issues: int = 0

    @property
    def register_violation(self):
        return self.register_issues > 0

    @property
    def needs_rewrite(self):
        return self.english and self.over_threshold

    @property
    def verdict(self):
        return "unsupported_language" if not self.english else "rewrite" if self.needs_rewrite else "ok"

    @property
    def reasons(self):
        return ["style"] if self.needs_rewrite else []

    def by_category(self):
        counts = Counter()
        for f in self.findings:
            if f.counted:
                counts[f.category] += f.weight
        return {k: round(v, 2) for k, v in counts.most_common()}

    def summary(self):
        if not self.english:
            return "Skipped: no eligible English prose found (language detection is heuristic)."
        status = "Worth editing." if self.needs_rewrite else "Within the editing threshold."
        return f"Editing signals {self.score}/100 ({self.surface} threshold {self.threshold}); {len(self.findings)} findings. {status}"

    def to_dict(self, max_findings=None):
        items = self.findings if max_findings is None else self.findings[:max_findings]
        return {"surface": self.surface, "score": self.score, "threshold": self.threshold,
                "verdict": self.verdict, "reasons": self.reasons, "register_violation": self.register_violation,
                "summary": self.summary(), "chars": self.chars, "words": self.words,
                "by_category": self.by_category(), "findings": [f.to_dict() for f in items],
                "findings_total": len(self.findings), "stats": self.stats}


def check(text: str, surface: str | Surface | None = None, threshold: int | None = None) -> Report:
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    prof = surface if isinstance(surface, Surface) else get_surface(surface)
    thr = prof.threshold if threshold is None or threshold == 0 else int(threshold)
    if not 1 <= thr <= 100:
        raise ValueError("threshold must be between 1 and 100, or 0 for the default")
    scan = _mask(text)
    words = len(WORD.findall(scan))
    report = Report(prof.name, 0, thr, False, is_english(text), len(text), words)
    if not report.english:
        return report

    def add(rule_id, category, label, hint, start, end, base, counted, source):
        w = prof.weight(rule_id, category, base)
        line = text.count("\n", 0, start) + 1
        col = start - text.rfind("\n", 0, start)
        excerpt = text[max(0, start - 20):min(len(text), end + 30)].replace("\n", "⏎")
        report.findings.append(Finding(rule_id, category, label, hint, start, end, line, col, excerpt,
                                       round(w, 3), bool(counted and w > 0), source))

    for rule in RULES:
        hits = list(rule.compiled.finditer(scan))
        if len(hits) < rule.min_hits:
            continue
        for i, m in enumerate(hits):
            start = m.start() + len(m[0]) - len(m[0].lstrip())
            add(rule.id, rule.category, rule.label, rule.hint, start, m.end(), rule.weight,
                rule.scored and i < rule.max_count, rule.source)
    sents = [s for s in split_sentences(scan) if s.kind == "prose" and len(WORD.findall(s.text)) >= 3]
    lengths = [len(WORD.findall(s.text)) for s in sents]

    def advice(key, sentence):
        cat, label, hint, source = STRUCTURAL[key]
        add(key, cat, label, hint, sentence.start, sentence.end, .25, False, source)

    if len(sents) >= 4:
        openers = [WORD.findall(s.text)[0].lower() for s in sents]
        if Counter(openers).most_common(1)[0][1] >= 3:
            advice("rhythm.openers", sents[0])
        band = sum(abs(n - statistics.median(lengths)) <= 5 for n in lengths) / len(lengths)
        if band >= .7:
            advice("rhythm.uniform", sents[0])
    lines = [ln for ln in scan.splitlines() if ln.strip()]
    lists = [ln for ln in lines if re.match(r"\s*(?:[-*+] |\d+[.)] )", ln)]
    if len(lists) >= 4 and len(lists) / len(lines) >= .5:
        start = scan.index(lists[0])
        advice("format.list_heavy", Sentence(lists[0], start, start + len(lists[0])))
    report.findings.sort(key=lambda f: (f.start, f.rule))
    points = sum(f.weight for f in report.findings if f.counted)
    norm = math.sqrt(max(1, words / 100))
    report.score = round(100 * (1 - math.exp(-points / (4 * norm))))
    report.over_threshold = report.score >= thr
    report.stats = {"points": round(points, 3), "sentences": len(sents),
                    "sentence_words": lengths, "list_ratio": round(len(lists) / max(1, len(lines)), 3)}
    return report
