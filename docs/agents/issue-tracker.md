# Issue tracker: GitHub

Specs and implementation tickets for Plainspoken live in GitHub Issues. Use the `gh` CLI from this checkout; its `origin` remote identifies `averyfreeman/plainspoken-content-production`.

## Conventions

- Create specs and tickets as GitHub issues. Use a heredoc for multi-line bodies.
- Use `ready-for-agent` when acceptance criteria are specific enough for implementation. Use `needs-info` when a decision or source material is missing. Use `needs-triage` for future work whose scope is not defined yet.
- Link implementation tickets to their spec as native sub-issues when supported.
- Express blockers with GitHub's native issue dependencies. Add an edge with `gh api --method POST repos/averyfreeman/plainspoken-content-production/issues/<blocked>/dependencies/blocked_by -F issue_id=<blocker-database-id>`. The blocker ID is the numeric issue database ID, not its issue number. If native dependencies are unavailable, put a `Blocked by: #...` line in the issue body.
- Assign tickets to the milestone that represents their delivery. Close completed tickets and verify changes by reading the issue back.
- PRs are not a triage surface by default.

## Common commands

- Create: `gh issue create --title "..." --body-file ... --label ready-for-agent --milestone "..."`
- Read: `gh issue view <number> --json number,title,body,labels,milestone,state`
- List: `gh issue list --state open`
- Close: `gh issue close <number> --comment "Completed"`
