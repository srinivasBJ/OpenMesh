# OpenMesh Pull Request Audit

Date: 2026-06-04

Repository: `srinivasBJ/OpenMesh`

Command used:

```bash
gh pr list --state open --limit 100 \
  --json number,title,state,isDraft,mergeable,headRefName,baseRefName,author,updatedAt,url,reviewDecision,statusCheckRollup
```

## Summary

- Open PRs reviewed: 10.
- Already merged PRs among open PRs: 0.
- Obsolete PRs identified: 0.
- PRs closed: 0.
- PRs merged: 0.
- PRs left open: 10.

Decision: keep all Dependabot PRs open until after `v1.0.0-alpha` ships. They
are useful dependency-hardening backlog items, but merging dependency churn into
the release freeze is not safer than shipping the already validated release
candidate.

## Audit Table

| PR | Title | Status | Action taken | Justification |
| --- | --- | --- | --- | --- |
| #1 | chore(deps): bump actions/setup-python from 5 to 6 | Open, mergeable, CI passed | Left open | Valid CI-maintenance PR, but not required for v1 alpha because current CI is already green. Keep for post-alpha hardening. |
| #2 | chore(deps): bump actions/checkout from 4 to 6 | Open, mergeable, CI passed | Left open | Valid CI-maintenance PR, but not required for v1 alpha because current CI is already green. Keep for post-alpha hardening. |
| #3 | Bump actions/setup-node from 4 to 6 | Open, mergeable, prior CI failed | Left open | Not obsolete, but not safe to merge during release freeze without revalidation. Keep for post-alpha CI dependency review. |
| #4 | Bump psycopg2-binary from 2.9.9 to 2.9.12 in /backend | Open, mergeable, prior CI failed | Left open | Runtime dependency update. Not obsolete, but not safe to merge during release freeze because backend checks previously failed. |
| #5 | Bump pydantic from 2.11.7 to 2.13.4 in /backend | Open, mergeable, prior CI failed | Left open | Runtime dependency update touching validation behavior. Not safe for release freeze without focused compatibility testing. |
| #6 | chore(deps): bump axios from 1.13.6 to 1.16.1 in /frontend | Open, mergeable, CI passed | Left open | Frontend dependency update with green CI, but still dependency churn. Keep for post-alpha dependency-hardening batch. |
| #7 | Bump redis from 5.0.1 to 8.0.0 in /backend | Open, mergeable, prior CI failed | Left open | Major runtime dependency update. Not obsolete, but unsafe for v1 alpha freeze. |
| #8 | Bump apscheduler from 3.10.4 to 3.11.2 in /backend | Open, mergeable, prior CI failed | Left open | Scheduler dependency update. Not obsolete, but prior backend failure makes it post-alpha work. |
| #9 | chore(deps): bump zustand from 4.5.7 to 5.0.14 in /frontend | Open, mergeable, CI passed | Left open | Frontend state dependency update with green CI. Keep open for post-alpha hardening rather than changing release candidate behavior. |
| #10 | Bump anthropic from 0.84.0 to 0.105.2 in /backend | Open, mergeable, prior CI failed | Left open | Provider dependency update. Not obsolete, but unsafe for v1 alpha freeze without provider regression testing. |

## Release Decision

No open PR was merged for the v1 alpha release.

No open PR was closed as obsolete.

Recommended post-alpha action:

1. Re-run CI on PRs #1, #2, #6, and #9 and merge if still green.
2. Rebase and revalidate #3, #4, #5, #7, #8, and #10.
3. Batch dependency updates behind one release-hardening milestone instead of
   mixing them into launch tagging.
