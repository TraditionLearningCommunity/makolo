# Makolo — CI trigger policy

This document records the intended GitHub Actions trigger policy. It is operational guidance, not a product/domain contract.

## Goal

Run the strongest relevant gate without starting unrelated Django, PostgreSQL, E2E, seed or mobile work.

The policy is conservative:

- runtime code changes keep the existing broad Django and PostgreSQL protection;
- mixed PRs (docs + runtime) are treated as runtime PRs;
- docs-only changes do not start runtime suites;
- mobile-only changes stay on the mobile workflows;
- specialized PostgreSQL workflows run only for their declared surfaces and are deferred while a PR is draft when a fast/general gate already exists;
- obsolete runs are cancelled when a newer commit supersedes them;
- supply-chain scans are event-driven for relevant changes and also run weekly so path filtering does not hide newly published dependency advisories.

## Docs-only

Changes confined to `docs/**` and root Markdown files such as `AGENTS.md` or `README.md` must not start:

- full Django;
- E2E;
- generic PostgreSQL matrices;
- Beta seed validation;
- Funding PostgreSQL;
- Conversation PostgreSQL;
- supply-chain audits.

A PR that also changes runtime/config/dependency/workflow files is not docs-only and keeps the relevant gates.

## Mobile-only

The backend/general CI ignores `mobile/**` and mobile workflow files already owned by the mobile lane. Mobile workflows remain responsible for Flutter analysis/tests/builds.

Do not extend this exclusion to backend/API contract changes merely because their consumer is mobile.

## Draft PRs

Draft PRs may use lightweight checks, but expensive specialized PostgreSQL gates should wait until the PR is ready for review unless the workflow has a deliberate draft-specific fast lane.

Moving a PR back to draft must not restart expensive runtime suites merely because of the state transition.

## Beta seed

Beta seed validates runtime/data compatibility, not documentation, frontend assets or test files themselves. It therefore ignores docs-only, mobile-only, frontend/static-only and test-only changes. Any accompanying runtime change still triggers the workflow.

## Supply chain

The supply-chain workflow protects:

- Python runtime dependencies;
- agent/runtime dependency profiles;
- npm runtime dependencies;
- first-party Python runtime code through Bandit;
- pinned GitHub Actions references.

It skips changes that its checks do not inspect (docs, mobile, frontend/static/template-only and test-only changes), while a weekly scheduled run continues to catch advisories that appear without a repository change.

## Specialized PostgreSQL gates

Actor/domain workflows use narrow path filters. Documentation changes to an actor contract do not run PostgreSQL because the test command does not validate Markdown.

Specialized gates should target PRs into `main`, use concurrency cancellation, and avoid doing full PostgreSQL work on draft updates when the generic fast checks already cover basic Django/migration validity.

## Safety rules

When changing CI:

1. never skip a gate solely to make a failing PR green;
2. do not exclude a path if the workflow actually validates artifacts or behavior owned by that path;
3. prefer a conservative extra run over an unproven exclusion;
4. workflow-file changes must still trigger the workflow that owns them;
5. dependency/config/migration/runtime changes keep their relevant gates;
6. after changing trigger policy, verify the workflow files themselves and observe the PR checks before merge.

Path filtering is an optimization, not a weakening of product contracts.

## Funding full-diff impact gate (November 2026)

The Funding PostgreSQL workflow uses a lightweight `scope` job before provisioning
PostgreSQL. This evaluates the **complete change set** (`base...head` for PRs,
`before..head` for pushes), not only the latest commit. The check uses a full
checkout rather than relying solely on GitHub's first-300-file PR path filter.

The heavy Funding suite still runs for changes in Funding itself or in the
upstream surfaces its tests exercise: Activity, Payments, identity/authority,
Commerce/Subscriptions, Discovery, social/topic context, geography, shared
core/configuration/templates, tooling and dependencies. On missing history,
unavailable diff or ambiguous revision, the scope defaults to **run**.

A manual `workflow_dispatch` runs the complete suite regardless of changed
paths. Changes to the workflow file itself also run the suite. This is an
optimization of runner allocation, not a removal of Funding tests or a
substitute for the broader required CI. Do not make a failing Funding check
green by removing the affected path from its scope.

For an unusually large cumulative PR such as #522, any relevant Funding
change anywhere in the PR still selects the complete Funding suite even if
the latest commit is mobile-only. Optimizing a single-commit feedback loop
further would require a separately enforced cumulative pre-merge gate;
do not silently switch the required tests to only the latest commit.
