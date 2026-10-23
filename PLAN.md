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

## Next work

1. Publish the v0.2.0 release.
2. Review the generated voice sample and calibrate the initial profile.
3. Confirm authorship and select appropriate professional writing samples.
4. Add a professional register and decide whether to configure the profile for automatic edits.
5. After the writing framework is complete, design a study of acceptable writing behavior across Japanese and English cultural norms.

The profile and source archive stay local. Public repository issues and release notes should describe capabilities and progress without copying personal documents or private source text.

## Existing verification

The current English implementation previously passed 65 tests, the portable skill validator, and 14 Hermes plugin validation checks. The Japanese corpus and original implementation remain on the research branch for later comparative work.
