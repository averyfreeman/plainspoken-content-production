"""Tool schema exposed to the agent."""
from .surfaces import SURFACES

WRITING_CHECK = {
    "name": "writing_check",
    "description": "Check English prose for canned phrasing, filler, hype and repetition. Deterministic and offline. Returns an editing score, positioned findings and context-specific suggestions. Advisory findings do not trigger automatic rewrites. Preserve the writer's voice, factual claims and certainty when editing; check again afterwards.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "English prose to check."},
            "surface": {"type": "string", "enum": sorted(SURFACES), "description": "Delivery context; defaults to chat. sns means social posts."},
            "max_findings": {"type": "integer", "minimum": 1, "maximum": 200, "description": "Maximum findings returned; defaults to 30."},
        },
        "required": ["text"],
    },
}
