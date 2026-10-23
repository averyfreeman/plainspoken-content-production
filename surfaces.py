"""Context changes emphasis, without imposing a personality or formality."""
from __future__ import annotations
from dataclasses import dataclass, field

SURFACE_LABELS = {
    "chat": "Chat", "business_email": "Business email", "external": "Public announcement",
    "sns": "Social post", "tech_doc": "Technical documentation",
}
DEFAULT_SURFACE = "chat"


@dataclass(frozen=True)
class Surface:
    name: str
    threshold: int
    category_scale: dict = field(default_factory=dict)
    rule_scale: dict = field(default_factory=dict)

    def weight(self, rule_id, category, base):
        return base * self.rule_scale.get(rule_id, self.category_scale.get(category, 1.0))


SURFACES = {
    "chat": Surface("chat", 40, rule_scale={"sycophancy.great_question": 1.2}),
    "business_email": Surface("business_email", 35, rule_scale={"stock.email_greeting": 1.2}),
    "external": Surface("external", 40, category_scale={"inflated": 1.3}),
    "sns": Surface("sns", 35, category_scale={"template": 1.2}),
    "tech_doc": Surface("tech_doc", 45, category_scale={"format": 0}),
}


def get_surface(name: str | None) -> Surface:
    key = (name or DEFAULT_SURFACE).strip().lower().replace("-", "_")
    key = {"email": "business_email", "mail": "business_email", "press": "external",
           "public": "external", "social": "sns", "social_post": "sns", "x": "sns",
           "twitter": "sns", "tech": "tech_doc", "docs": "tech_doc", "doc": "tech_doc"}.get(key, key)
    if key not in SURFACES:
        raise ValueError(f"unknown surface {name!r}; choose one of {', '.join(SURFACES)}")
    return SURFACES[key]
