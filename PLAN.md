# Plainspoken project plan

## Goal

Publish and maintain Plainspoken as an English writing plugin and portable voice-writing skill. Track completed work, release work, and follow-up research in GitHub Issues and milestones.

## Repository and branches

- Public repository: https://github.com/averyfreeman/plainspoken-content-production
- `main`: English Plainspoken project, with a clean root commit.
- `research/japanese-cultural-contrast`: complete pre-conversion Japanese project snapshot, including its corpus, licensing and source records, comparison baselines, skill, and matching tests.
- `upstream`: original `TakeshiTGAL/hermes-plugin-ja-writing-guard` source remote.

The research branch is preserved as an independent history. Bring over framework changes only when the later cross-cultural study is ready to begin.

## Completed markers

- Converted the checker, rules, examples, and Hermes integration for English.
- Added guarded model rewriting and preserved-content checks.
- Added the portable `natural-writing` skill and its evidence-backed corpus helper.
- Indexed 71 author-provided blog posts and saved a provisional, cited profile outside the repository.
- Validated and enabled Plainspoken in Hermes.
- Created the public repository, clean English history, and Japanese research branch.
- Published the public [v0.2.0 release](https://github.com/averyfreeman/plainspoken-content-production/releases/tag/v0.2.0).
- Published the parent spec in [issue #1](https://github.com/averyfreeman/plainspoken-content-production/issues/1) and linked its child tickets.

## Milestones and next work

- **v0.2.0 — Initial public release:** completed; issues #2–#7 are closed.
- **Voice calibration and professional register:** issues [#8](https://github.com/averyfreeman/plainspoken-content-production/issues/8) and [#9](https://github.com/averyfreeman/plainspoken-content-production/issues/9) await author input. Issue [#10](https://github.com/averyfreeman/plainspoken-content-production/issues/10) is blocked by them.
- **Future research — Japanese/English writing norms:** issue [#11](https://github.com/averyfreeman/plainspoken-content-production/issues/11) is deferred until the framework tickets are complete.

The profile and source archive stay local. Public repository issues and release notes should describe capabilities and progress without copying personal documents or private source text.

## Existing verification

The current English implementation previously passed 65 tests, the portable skill validator, and 14 Hermes plugin validation checks. The Japanese corpus and original implementation remain on the research branch for later comparative work.
