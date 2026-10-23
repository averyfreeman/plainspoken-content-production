# Sources and design choices

| Resource | How this project uses it |
| --- | --- |
| [work-humanizer](https://github.com/phuryn/work-humanizer) | Primary source for fact and commitment preservation, interview-based drafting, source reasoning, and English editing patterns. MIT; pinned attribution in NOTICE. |
| [Google developer writing guide](https://developers.google.com/style/tone) | Secondary reading on clear, conversational documentation and context-appropriate tone. |
| Available voice fidelity and conversational writing skills | Informed the choice to preserve useful roughness and learn a subject's voice from evidence. Their predefined personas and domain-specific structures are not bundled. |
| [Original Japanese plugin](https://github.com/TakeshiTGAL/hermes-plugin-ja-writing-guard) | Foundation for offline checking, positioned reports, Hermes hooks, bounded model calls, media protection and local report handling. MIT; original notices retained. |

The English version adds a global subject library with traceable source
observations. It inventories supplied material before selecting a representative
sample, distinguishes reference material from voice evidence, and keeps the
interview outside the automatic reply hook.

The checker provides editing signals. Broad vocabulary and punctuation checks
are advisory. The automatic editor is deliberately narrower than interactive
writing: it preserves unflagged sentences and surrounding content, allowing
changes to detected phrasing and a small set of direct replacements. The
portable skill can restructure a piece using the writer's notes and a fact audit.

No external humanizer, commercial detector, embedding service or MCP server is
required at runtime. Connected tools help retrieve sources when available;
exported text works when they are not. This project has not reproduced the
reader judgments or detector results reported by other projects.
