# Makolo — Orchestration ChatGPT-first

## Purpose

Makolo is already an advanced product. Agent tooling is used to accelerate delivery, not to rediscover or redesign the product.

The default collaboration model is:

```text
Human / local PC
        |
        v
     GitHub
        ^
        |
ChatGPT + GitHub   <- primary remote orchestration
        ^
        |
Codex / ECC        <- optional bounded execution
```

GitHub is the rendezvous point. There is one official repository: `TraditionLearningCommunity/makolo`, with `main` as the integration branch.

## Entry protocol for every important task

Before proposing or changing code:

1. Read current `main` HEAD.
2. Inspect recent commits.
3. Inspect open PRs and relevant branches.
4. Check CI state for the branch/PR being continued.
5. Inspect migrations and tests in the touched domain.
6. Read the current implementation before relying on a roadmap or handoff.
7. Read the canonical domain blueprint and relevant canonical docs.
8. Run a collision audit.

Do not treat old SHAs, old PR descriptions or historical discussions as current state.

## Collision audit

Parallel work is allowed only when write surfaces and responsibilities are genuinely independent.

Check for collisions in at least:

- `/me/` and personal projections;
- global navigation and shared templates;
- central URL composition;
- models and migrations;
- permission/mandate resolution;
- shared fixtures/factories;
- common API serializers/selectors;
- CI/workflow files;
- deployment/runbook files.

If two tasks collide, choose one of:

- serialize the work;
- narrow one scope;
- use a single integration branch with explicit checkpoints;
- nominate one integrator to own the overlapping files.

## Work item contract

Every non-trivial lane should have:

```text
ID:
Objective:
Owner:
Base:
Branch:

Scope:
- ...

Forbidden:
- ...

Acceptance:
- ...

Evidence:
- targeted tests
- relevant suite
- migration check
- CI

Merge gate:
- diff reviewed
- architecture boundaries preserved
- security/privacy checks passed
- branch reconciled with current main
- CI green
```

The contract is a coordination tool, not a new business model.

## Roles

### Architect / integrator

Owns boundaries, collision audit, integration strategy and cross-domain consistency.

Must prevent accidental duplication of business truth and unnecessary persistent state.

### Backend Django

Owns services, selectors/read models, APIs/views, authorization and data integrity inside the assigned scope.

Must treat Permission/Mandate/Access rules as server-side responsibilities.

### UX / web

Owns contextual presentation and interaction in the assigned surface.

Must not duplicate canonical business truth in templates or Presentation.

### QA / security

Owns failure modes, regression coverage, IDOR/privacy, concurrency/idempotence where relevant and compatibility with existing data.

### Reviewer / release

Owns independent diff review, test evidence, CI verification, reconciliation with current `main` and post-merge readback.

### Mobile

Activated only for mobile-specific lanes. Flutter consumes canonical backend contracts and must not duplicate Readiness, authorization or business state.

## ChatGPT-first workflow

ChatGPT + GitHub is the primary remote workflow.

Typical sequence:

```text
1. User states objective.
2. ChatGPT refreshes main + PR/branch/CI state.
3. ChatGPT identifies existing implementation and canonical owner domains.
4. ChatGPT defines a bounded lane.
5. Dedicated branch is created.
6. Implementation + focused tests.
7. Relevant wider tests / migration checks.
8. PR opened or updated.
9. CI inspected.
10. Root cause fixed if red.
11. Merge only when green.
12. main verified after merge.
```

No extra agent framework is required for this path.

## Manual local workflow

Local PC work remains first-class.

Before local work:

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c <branch>
```

Push the branch before asking a remote agent to review or continue it:

```bash
git add .
git commit -m "..."
git push -u origin <branch>
```

Remote agents cannot reliably review unpushed local changes.

## Codex / ECC workflow

Codex and ECC are optional accelerators.

Use them for:

- bounded implementation;
- independent tests;
- isolated worktrees;
- focused code review;
- build repair;
- repetitive verification;
- parallel lanes that do not overlap.

Do not give them an open-ended instruction such as “improve Makolo” or “finish the architecture”.

Every Codex/ECC lane must receive the same work-item contract and Makolo invariants.

ECC must not become a repository dependency merely to coordinate work. Install/use it at the developer tool level unless a future explicit product decision requires otherwise.

## Parallel execution rules

Good parallelism:

```text
Lane A: backend projection in isolated files
Lane B: mobile client consuming an already stable API
Lane C: security review, read-only
Lane D: documentation for a closed contract
```

Bad parallelism:

```text
Lane A: rewrite /me/ URLs
Lane B: rewrite /me/ templates
Lane C: change the same selectors
Lane D: change the same fixtures
```

The second case needs sequencing or one integration owner.

## Tests and migrations

For business changes:

1. focused tests for the modified contract;
2. relevant domain/integration suite;
3. `manage.py check`;
4. migration consistency check;
5. PostgreSQL gate when behavior depends on locking, constraints or database semantics;
6. authorization/IDOR checks;
7. concurrency/idempotence checks when applicable;
8. compatibility with valid existing data.

Never create a migration solely because an agent assumes one is needed.

Never delete, weaken or bypass a test to make CI green.

## Deployment / beta

A test deployment is not considered validated until the touched scope is exercised with the relevant personas and authority contexts.

Minimum cross-cutting smoke expectations when relevant:

- visitor;
- authenticated Profile;
- personal action;
- action on behalf of a Space;
- Permission/Mandate boundary;
- Activity/Occurrence;
- Journey;
- Access;
- Capacity;
- no unexpected 500.

PythonAnywhere remains beta/test infrastructure unless the canonical repository configuration changes that status.

## Handoff standard

At the end of a lane, leave enough evidence for another human or agent to continue without reconstructing the work from chat history:

```text
Base:
Head:
Branch/PR:
What changed:
Why:
Tests run:
Migration status:
Known risks:
What remains:
Files/surfaces intentionally not touched:
```

Do not include secrets or unnecessary personal data.

## Current-project rule

Makolo's runtime and canonical docs are the authority. Agent frameworks provide execution patterns only. They do not own Makolo's product model, roadmap, architectural vocabulary or release decisions.
