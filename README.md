# Plainspoken

English writing tools for Hermes and other agents. Clean up formulaic phrasing,
keep the writer's voice, and build reusable voice profiles from their actual work.

The Hermes plugin checks final replies and automatically edits flagged text.
The portable skill handles deeper writing: research the subject's previous
work, interview them, then draft in their voice. Both prioritize meaning over polish.

## Install in Hermes

Requires Hermes 0.21.4+ and Python 3.11+. From this checkout:

```sh
mkdir -p "$HOME/.hermes/plugins"
ln -s "$PWD" "$HOME/.hermes/plugins/plainspoken"
hermes plugins enable plainspoken
```

Run this from the checkout root. The symlink loads the current working files,
including uncommitted changes. If that destination already exists, inspect it
before replacing it. Restart the gateway with `hermes gateway restart` if you
use it; CLI users pick up the plugin on their next launch.

For a snapshot of committed code, use `hermes plugins install "file://$PWD" --enable`.
That command clones Git history and excludes uncommitted changes. A development
symlink does not need a commit and reads new source edits after a restart.

The portable skill remains `natural-writing`, and the checker remains
`writing_check` with the `/writing-check` command. The repository's origin and
homepage identify the Plainspoken project:
<https://github.com/averyfreeman/plainspoken-content-production>. The complete
Japanese plugin snapshot, including its evaluation corpus and source records,
is preserved on the [`research/japanese-cultural-contrast` branch](https://github.com/averyfreeman/plainspoken-content-production/tree/research/japanese-cultural-contrast).

Automatic editing is enabled by default and uses Hermes's configured model.
To check and log without changing replies:

```sh
hermes config set plugins.entries.plainspoken.settings.mode report
```

The checker and corpus helper use Python's standard library. There are no
additional API keys, model SDKs or mandatory MCP servers.

## Check or edit writing

Ask the agent to use `natural-writing` for drafting, rewriting or voice research.
Use `writing_check` when you want positioned suggestions:

```text
/writing-check chat Great question! It's important to note that we could send the report on Friday. I hope this helps.
/writing-check
```

The second command displays the last local report, including delivered changes.
Reports are not retained on shared gateways.

Before:

> Great question! It's important to note that we could send the report on Friday. I hope this helps.

After:

> We could send the report on Friday.

"Could" and "Friday" survive. The editor removes the wrappers. The complete
synthetic examples in [examples/rewrite](examples/rewrite) cover all five contexts.

`writing_check` accepts `text`, optional `surface`, and optional `max_findings`
(default 30, maximum 200). Reports include `score`, `threshold`, `verdict`,
`summary`, `words`, `chars`, category totals, and findings with offsets, line,
column, excerpt, suggestion, source and `counted` status. Verdicts are `ok`,
`rewrite`, and `unsupported_language`.

Scores describe weighted editing signals. They are not probabilities of who
wrote a passage. Broad vocabulary, dashes, semicolons and rhythm are advisory;
they do not trigger automatic edits. Keep terms such as "robust estimator" and
the punctuation a subject actually uses.

| Surface | Context | Default threshold |
| --- | --- | --- |
| `chat` | Replies and conversations | 40 |
| `business_email` | Work email | 35 |
| `external` | Public announcements | 40 |
| `sns` | Social posts | 35 |
| `tech_doc` | Documentation | 45 |

Command aliases include `email`, `social`, and `docs`. Context changes emphasis;
it does not require a formal or casual personality. English language eligibility
is heuristic: short, unusual, or mixed-language passages may be skipped. Code,
quoted material, URLs, tables, markup and complete JSON documents are excluded
from prose checking.

## Learn a subject's voice

Supply previous writing, folders, URLs, transcripts or scoped connected sources.
The skill inventories accessible items, distinguishes authored samples from
research, and starts with twelve representative pieces across dates, formats
and lengths. It searches the wider collection to verify voice observations.
Interviews are the default for substantive work: one short round of focused
questions fills gaps in the subject's reasoning and examples. You can skip
questions or request an immediate draft.

Each subject has a separate global library entry:

```text
~/.natural-writing/profiles/alex-rivera/
  profile.md       Voice observations, examples, caveats and evidence anchors
  sources.jsonl    Inventory, source fingerprints and reading coverage
  subject.json     Identity and profile freshness
```

The portable [skill](skills/natural-writing/SKILL.md) includes the complete
[research workflow](skills/natural-writing/references/voice-research.md).
The helper inventories UTF-8 text and HTML. Use the host's tools to export PDFs,
Word documents, transcripts and connected content. It never fetches URLs or
infers a voice on its own.

```sh
python skills/natural-writing/scripts/corpus.py --subject alex-rivera inventory /path/to/writing --name "Alex Rivera" --author "Alex Rivera" --authorship confirmed
python skills/natural-writing/scripts/corpus.py --subject alex-rivera sample
python skills/natural-writing/scripts/corpus.py --subject alex-rivera status
```

Only mark authorship confirmed when the user or source establishes it. Source
pointers, fingerprints and short evidence excerpts are saved; full source texts
are not copied into the library. Changed exports reset reading status and mark
profiles stale. Each new remote export must be fetched through the host's tools.

To guide automatic Hermes edits with a particular saved profile:

```sh
hermes config set plugins.entries.plainspoken.settings.voice_profile '~/.natural-writing/profiles/alex-rivera/profile.md'
```

The hook reads only that file. It never interviews, researches, discovers other
profiles or writes to the library. A missing, empty or oversized configured
profile leaves the original reply unchanged. Clear this setting to preserve
the current reply's voice without a saved profile.

## Use the skill in another agent

Copy the entire `skills/natural-writing` folder into the agent's skills folder.
For Codex, that is `~/.codex/skills/natural-writing`. References and the corpus
helper travel with it. Invoke `natural-writing` explicitly or ask the agent to
write in a subject's voice. The skill works without Hermes or `writing_check`.

## Automatic editing and safeguards

Only eligible English answers at least `min_chars` long are considered. A reply
over its editing threshold receives at most two model calls by default. The
editor retains unflagged sentences and surrounding content, and can shorten
detected phrases. A broader paraphrase belongs in the interactive skill.

Acceptance checks protect code, quotes, links, tables, names, numbers, dates,
email addresses, handles, signatures, actors, conditions, negation and modal
strength. Contractions are normalized for comparison. These heuristic checks
catch specific forms of drift; they cannot prove that meaning is unchanged.
The interactive skill also audits claims and commitments against the source.

Timeouts, errors, rejected candidates and insufficient improvement keep the
original answer. Existing `MEDIA:` lines are preserved. When a tool returned
media during a turn, rewriting is skipped to leave room for attachment plugins.
Local diffs describe only delivered changes. Logs contain scores and status,
not source excerpts or profile text.

Hermes's CLI may stream the original reply before displaying a transformed
version. Set `display.streaming false` in Hermes when you need the transformed
version to be the first one displayed. Enforcement may add up to the configured
time budget and consumes model tokens on flagged answers.

| Setting | Default | Behavior |
| --- | --- | --- |
| `mode` | `enforce` | `enforce`, `report`, or `off` |
| `surface` | `chat` | Default delivery context |
| `platform_surfaces` | `{}` | Platform-to-context overrides, e.g. `{"email":"business_email"}` |
| `threshold` | `0` | 0 uses the context default; otherwise 1–100 |
| `max_attempts` | `2` | Between 1 and 3 model calls |
| `rewrite_timeout` | `20` | Maximum seconds per call |
| `time_budget` | `25` | Whole rewrite budget, capped below the host hook timeout |
| `accept_partial` | `false` | Opt in to delivering a safe improvement still above threshold |
| `min_chars` | `40` | Shorter replies are skipped |
| `voice_profile` | empty | Optional selected profile file, at most 16,000 characters |

## Migrating from 0.1.0

Version 0.2.0 is an English conversion. Install this working copy as
`plainspoken`, disable the old `ja-writing-guard` installation, and
copy desired settings into `plugins.entries.plainspoken.settings`.
The tool is now `writing_check`, the command `/writing-check`, and the skill
`natural-writing`. The default mode changes from `report` to `enforce`.
Settings and profiles are not silently migrated. If you installed the earlier
working name `natural-writing-guard`, disable that entry and migrate its desired
settings to `plugins.entries.plainspoken.settings`. The global voice library
remains `~/.natural-writing/profiles`; existing subject profiles keep their paths.

The English release uses English fixtures and provisional thresholds. The
Japanese implementation, corpus, comparison baselines and their source records
remain available on the research branch. Neither set of results establishes
acceptable writing behavior across cultures. The English examples check editing
behavior; there has been no independent reader study or live-provider quality
benchmark.

## Development and sources

```sh
python -m pytest -q
python eval/run_eval.py --json eval/results.json
hermes plugins validate .
```

Use a working Python 3.11+ interpreter. Tests replay model responses offline and
exercise the portable helper in temporary libraries. See [evaluation](eval/README.md)
and [design sources](docs/comparison.md) for the evidence and its limits.

MIT licensed. The English editing guidance adapts
[phuryn/work-humanizer](https://github.com/phuryn/work-humanizer), with upstream
copyright preserved. The original Hermes implementation is by TakeshiTGAL.
See [NOTICE](NOTICE), [original notices](NOTICE.upstream), and [LICENSE](LICENSE).
