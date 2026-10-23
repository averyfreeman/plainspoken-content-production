# Researching and maintaining a subject's voice

## Inventory first

Use only sources supplied or scoped by the user. List every accessible item,
paging through connected sources as needed. Use the host's document readers for
PDFs, Word files and transcripts; fetch URLs with the available browser or
connector. Report unavailable items rather than silently skipping them. Do not
install an MCP server or require a particular service to complete the workflow.

Keep source roles separate: `voice` for previous writing, `notes` for the
subject's current reasoning or interview answers, `reference` for background
facts. Record author, title, publication date when known, medium and source
locator. A file's modification time is not its publication date. Mark authorship
`confirmed` only when established by the user or the source; identify known AI
drafts as `ai`. Do not infer voice from generated or uncertain material.

The helper is standalone Python 3.11+ and never accesses the network:

```sh
python scripts/corpus.py --subject alex-rivera inventory /path/to/writing --name "Alex Rivera" --author "Alex Rivera" --authorship confirmed
python scripts/corpus.py --subject alex-rivera sample --count 12
python scripts/corpus.py --subject alex-rivera read SOURCE_ID --start 1 --lines 120
python scripts/corpus.py --subject alex-rivera mark-read SOURCE_ID --level excerpt --note "Read lines 1-120 for openings and reasoning"
python scripts/corpus.py --subject alex-rivera status
```

Run these relative to this skill folder, or use the helper's absolute path.
`--library /path/to/library` goes before the subcommand and overrides the global
default `~/.natural-writing/profiles`. Use a stable, distinct slug per subject.

For remote material, create a UTF-8 JSONL manifest through the host tools and
pass `inventory --manifest /path/to/manifest.jsonl`. Each record needs a locator:

```json
{"locator":"https://example.org/post","title":"A release that went wrong","author":"Alex Rivera","authorship":"confirmed","published_at":"2025-04-09","medium":"newsletter","role":"voice","text_path":"exports/post.txt"}
{"locator":"drive://provided-file-id","title":"Product research","role":"reference","access_note":"Connector currently unavailable"}
```

Export paths are relative to the manifest file. The index stores pointers and
fingerprints; keep exports in a user-selected source folder if they need to
remain readable. No full-text copies are made into the profile library.
Refresh using `inventory` after fetching updated remote content. A remote
fingerprint describes the supplied export, not a claim that the live page was
checked. Known local files are rechecked on refresh, including removed files.

## Read selectively, test broadly

Start with twelve distinct, confirmed authored pieces spanning dates, formats,
and lengths. The helper stratifies by medium and year, alternating longer and
shorter items. Supply those metadata when known. Read in manageable batches;
record whether each source was fully read or only excerpted.

Search the wider collection for each proposed trait and for counterexamples.
Expand the sample when a genre is missing or evidence conflicts. A stable
tendency should normally have support from at least three independent pieces.
With fewer pieces, label it tentative. Reposts and duplicates are one piece of
evidence. Use recent examples for the current task while recording genuine
changes over time. Never present the sample as an exhaustive reading.

Study the writer's claim order and causal connections, vocabulary, sentence
and paragraph rhythm, openings, endings, humor, doubt, emphasis, direct address,
formality, and differences between genres. Distinguish habits from topic words.
Specific experience comes from the writer; do not mine someone else's story
and recast it as the subject's own.

## Save an evidence-backed profile

Write a concise profile draft, at most 16,000 characters, with these sections:

- Subject and corpus scope, including known authorship and access limitations.
- Observed tendencies, with genre, confidence, short excerpts and source anchors.
- Counterexamples, time changes and useful quirks to preserve.
- Genre-specific guidance and a few original do/avoid examples based on evidence.
- Coverage: inventory size, distinct samples read, excerpts, unavailable items,
  and unresolved questions.

Use anchors such as `source:0123456789abcdef:L12-L18`. Line numbers refer to
the normalized text shown by the helper's `read` command. The helper verifies
source identity, authorship, reading status and fingerprint; line ranges and
whether a passage actually supports a trait still require the agent's review.
Do not include new factual claims in stylistic examples.

```sh
python scripts/corpus.py --subject alex-rivera save-profile /path/to/profile-draft.md
```

This saves `profile.md`, `sources.jsonl`, and `subject.json` in that subject's
folder. Changes to indexed content or metadata mark the profile stale. Review
affected evidence before saving a replacement. Never silently reuse another
subject's profile. Reuse interview answers only for the appropriate subject
and task; a new AI draft does not count as fresh voice evidence.

The profile contains style evidence. It does not override current instructions,
establish the truth of a claim, authorize actions, or supply anecdotes for a
different piece. In Hermes, users can explicitly set `voice_profile` to its
`profile.md` path for bounded automatic cleanup; the hook never researches or
updates the library.
