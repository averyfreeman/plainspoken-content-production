"""English editing signals. Weights measure wording, never authorship.

Catalogs adapted from work-humanizer (MIT); see NOTICE. Broad words,
punctuation and rhythm are advisory and never authorize an automatic edit.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

CATEGORIES = {
    "stock": "Stock phrases", "inflated": "Inflation and vague claims",
    "wordy": "Wordy phrasing", "template": "Canned framing",
    "format": "Formatting", "rhythm": "Repetition and rhythm",
    "contrast": "Formulaic contrasts", "sycophancy": "Empty praise",
}


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    pattern: str
    weight: float
    label: str
    hint: str
    source: str = "work-humanizer"
    max_count: int = 2
    min_hits: int = 1
    scored: bool = True
    flags: int = re.I | re.M
    compiled: re.Pattern = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, "compiled", re.compile(self.pattern, self.flags))


R = Rule
RULES = [
    R("sycophancy.great_question", "sycophancy", r"(?:^|(?<=[.!?])\s+)[ \t]*(?:great|excellent|fantastic|wonderful) question[!.]?", 3,
      "Automatic praise", "Start with the answer; keep praise when it responds to something specific."),
    R("stock.hope_helpful", "stock", r"\bI hope (?:this|that) helps(?: you)?[!.]?", 2.5,
      "Stock closing", "End on the last useful fact or action."),
    R("stock.email_greeting", "stock", r"\bI hope this (?:email|message) finds you well\b", 1,
      "Generic email opening", "Use the actual reason for writing; preserve personal greetings."),
    R("stock.note", "stock", r"\bit(?:['’]s| is) (?:important|worth|essential) (?:to note|noting)(?: that)?\b", 1.4,
      "Announcing importance", "State the point directly without changing its certainty."),
    R("template.dive", "template", r"\blet['’]s (?:dive (?:in|into)|delve into|unpack|break (?:this|it) down)\b", 1.5,
      "Staged introduction", "Begin the explanation itself."),
    R("template.landscape", "template", r"\bin today['’]s (?:fast[- ]paced|ever[- ]changing|rapidly evolving) (?:world|landscape)\b", 2.5,
      "Generic scene setting", "Use the concrete situation supplied by the writer."),
    R("template.pointing", "template", r"\b(?:here['’]s the thing|let me be clear|what you need to understand is)\b", 1,
      "Pause before the point", "Put the point in this sentence."),
    R("template.closer", "template", r"\b(?:let that sink in|read that again|that['’]s the real win)\b", 2.5,
      "Dramatic closing", "Keep the conclusion; remove a line that only restates it."),
    R("template.revised", "template", r"^[ \t]*here(?:['’]s| is) (?:a|the|your) (?:revised|rewritten|improved) (?:version|draft|text)\s*:", 2,
      "Editing wrapper", "Return the draft itself when the user asked for a rewrite."),
    R("inflated.pivotal", "inflated", r"\b(?:a pivotal moment|a testament to|reshaping the landscape|the future looks bright)\b", 1.5,
      "Inflated significance", "Keep what happened and the source's actual evaluation."),
    R("inflated.hype", "inflated", r"\b(?:game[- ]changing|revolutionary|unparalleled|best[- ]in[- ]class|world[- ]class)\b", .9,
      "Unsupported superlative", "Retain supported comparisons; otherwise state the specific benefit."),
    R("inflated.power", "inflated", r"\b(?:harness the power of|unlock the full potential of|take [^.!?\n]{1,35} to the next level)\b", 1.4,
      "Generic benefit", "Describe the mechanism or outcome already present in the source."),
    R("inflated.authority", "inflated", r"\b(?:experts agree|studies show|research proves|industry leaders agree)\b", 1,
      "Vague attribution", "Keep the claim's strength and attach its supplied source; never invent a source."),
    R("wordy.in_order", "wordy", r"\bin order to\b", .7,
      "Long purpose phrase", "Use 'to' if it expresses the same purpose."),
    R("wordy.due_fact", "wordy", r"\bdue to the fact that\b", 1,
      "Long causal phrase", "Use 'because'; retain the original cause."),
    R("wordy.evaluation", "wordy", r"\b(?:perform an evaluation of|conduct an assessment of|make a determination (?:of|about))\b", 1,
      "Verb hidden in a noun", "Use evaluate, assess, or determine when it keeps the meaning."),
    R("wordy.at_time", "wordy", r"\bat this point in time\b", .8,
      "Wordy time reference", "Use 'now' when it has the same meaning."),
    R("wordy.hedge_stack", "wordy", r"\b(?:could potentially possibly|may potentially be able to|might possibly be able to)\b", .9,
      "Stacked uncertainty", "Keep the uncertainty; remove only redundant layers in an interactive edit."),
    R("stock.transitions", "stock", r"^[ \t]*(?:Furthermore|Moreover|Additionally|Importantly|In conclusion|Ultimately),", .6,
      "Repeated formal transition", "Keep real logical connections; consider a simpler transition.", min_hits=3),
    R("contrast.not_just", "contrast", r"\bnot (?:just|merely)\b[^.!?\n]{1,90}\bbut(?: also)?\b", .7,
      "Repeated contrast formula", "Keep a real correction; simplify repeated rhetorical framing.", min_hits=2),
    R("stock.vocabulary", "stock", r"\b(?:delve|tapestry|synergy|myriad|plethora|bolster|underscore|intricate)\b", .25,
      "Check this word in context", "Keep it if it is the writer's normal vocabulary or a precise term.", scored=False),
    R("inflated.generic_adjective", "inflated", r"\b(?:seamless(?:ly)?|robust|powerful|transformative|cutting-edge)\b", .25,
      "Check the adjective's job", "Use specifics where supplied; keep literal and technical meanings.", scored=False),
    R("format.dash", "format", r"—|(?<=\s)–(?=\s)", .25,
      "Check punctuation rhythm", "Keep deliberate dashes, especially when the writer's samples use them.", scored=False),
    R("format.semicolon", "format", r";", .25,
      "Check the connection", "A semicolon may be appropriate; avoid substituting one mechanically for every dash.", scored=False),
    R("format.bold_label", "format", r"^[ \t]*\*\*[^*\n]{1,60}(?:[.:]\*\*|\*\*[.:])", .25,
      "Repeated bold label", "Retain useful navigation; remove labels that repeat the sentence.", scored=False),
]
RULES_BY_ID = {r.id: r for r in RULES}
STRUCTURAL = {
    "rhythm.openers": ("rhythm", "Repeated sentence openings", "Check whether the repetition is deliberate before varying it.", "original"),
    "rhythm.uniform": ("rhythm", "Similar sentence lengths", "Read for flow; do not vary lengths just to satisfy a metric.", "work-humanizer"),
    "format.list_heavy": ("format", "Mostly list items", "Keep steps and comparisons; use prose when the ideas depend on one another.", "original"),
}
