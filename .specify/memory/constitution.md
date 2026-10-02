# Makolo Constitution

## Core Principles

### I. Runtime Authority and Brownfield Evidence

Before meaningful work, the implementer MUST refresh the current `main` HEAD and inspect
recent commits, active PRs/branches relevant to the scope, current CI evidence, and the code,
migrations and tests that actually implement the touched behavior.

The current runtime wins over historical notes, old SHAs, old PR descriptions and old plans.
A Spec Kit artifact MUST NOT claim that a capability is absent, broken or pending without
checking the current repository state.

For domain work, the implementer MUST read
`docs/architecture/makolo-domain-blueprint.md`, the current canonical documents for the
domain, and `docs/operations-runbook.md` when operations can be affected.

**Rationale**: Makolo is a mature brownfield product in active development. Planning from stale
context creates duplicate work and architectural regressions.

### II. Canonical Domain Ownership and Contextual Product Language

Makolo MUST preserve the rule **backend generic, business contextual**. Canonical abstractions
such as Profile, Activity, Occurrence, Journey, Access, Requirement and Proof remain owned by
their established domains; Presentation uses the natural vocabulary of the human context.

A change MUST NOT create a second source of truth for an existing domain fact. Before adding a
model, column, lifecycle or other persistent state, the plan MUST test whether the need belongs
to an existing domain, relation, orchestration service, selector/read model, Readiness,
Domain Events, Analytics, Presentation or another existing projection mechanism.

**Rationale**: Local convenience is not sufficient reason to fragment Makolo's domain model.

### III. Identity, Responsibility and Authority

A Profile MUST remain a global person and MUST NOT become a global participant, organizer or
other contextual role. Assignment expresses responsibility. Mandate and Permission express
authority. Membership, Group, Team or responsibility MUST NOT grant authority implicitly.

Authorization-sensitive actions MUST be enforced server-side. A client may hide or disable an
action for usability, but client state is never the security boundary.

**Rationale**: Identity, collaboration and authority are deliberately separate Makolo concerns.

### IV. Composition, Security and Minimum Disclosure

Composition MUST NOT implicitly transfer Permission, Mandate, Access, Payment state or access
to private data. Public and collective projections MUST apply minimum disclosure.

Secrets, passwords, tokens, private keys, sensitive environment variables, full credentials or
QRs, and unnecessary PII MUST NOT appear in specs, plans, tasks, commits, issues, logs or
documentation. Demo data MUST remain distinguishable from real data.

**Rationale**: Combining facts may improve understanding; it never creates new authority or
visibility.

### V. Projection and State Discipline

Readiness MUST remain derived rather than copied into a generic persistent status. Presentation
represents facts; it does not own them. UX state such as loading, selected, expanded, dismissed,
seen or draft-restored MUST NOT become business state unless domain ownership is demonstrated.

The established distinctions MUST be preserved, including:

- Requirement, Form, Resource, JourneyArtifact, Proof, Trust Credential and AccessCredential;
- Access as a right, AccessCredential as its representation/secret, and AccessUse as observed use;
- Capacity as "how many?" and Placement as "where?";
- Waitlist and Live Queue;
- JourneyStep and operational checkpoint;
- Dossier and Project versus a generic task manager;
- owning a document, finding it, and satisfying a Requirement.

**Rationale**: A convenient aggregate status is not a replacement for independent business
dimensions.

### VI. Production-First Completeness

Unless a task is explicitly a prototype, spike, exploration or proof of concept, work MUST be
treated as production-bound. The delivered slice MUST be the smallest vertically complete slice,
not scaffolding that another developer must finish.

Required behavior MUST NOT be hidden behind product mocks, placeholders, fake success states,
silent catches, speculative abstractions, missing error handling, missing authorization or
untracked TODOs. Failures MUST be corrected at their root cause.

The change MUST preserve valid existing data and supported behavior unless an explicitly approved
migration or compatibility change says otherwise.

**Rationale**: Incremental delivery means small complete increments, not provisional product debt.

### VII. Tests, Migrations and Operational Safety

For business changes, targeted tests MUST cover the changed contract first, followed by the
relevant wider suite. The change MUST include migration consistency checks and `manage.py check`
where applicable. PostgreSQL validation is required when behavior depends on locking,
constraints, concurrency or database-specific semantics.

Authorization/IDOR, concurrency/idempotence, offline/sync truth and backward-data compatibility
MUST be tested when relevant. Tests MUST NOT be removed, weakened or bypassed to obtain green CI.
Destructive migrations require an explicit safeguard and rollback/recovery strategy.

Operational changes MUST be reconciled with `docs/operations-runbook.md`. PythonAnywhere remains
beta/test infrastructure unless current canonical configuration says otherwise.

**Rationale**: A green narrow test is evidence, not permission to ignore the surrounding contract.

### VIII. Git Integration and Safe Parallelism

Important work MUST use a dedicated branch and PR. `main` is the sole integration branch and
MUST NOT be modified directly for ordinary feature work. Each work item/branch has one owner.

Before parallel work, an explicit collision audit MUST cover shared models/migrations,
authorization resolution, shared selectors/serializers, global navigation, `/me/` surfaces,
fixtures/factories, CI files and deployment/runbook surfaces as applicable. Parallel lanes are
allowed only when their write surfaces and responsibilities are genuinely independent.

A branch MUST be reconciled with the current `main` before final integration. A PR MUST NOT merge
with red required CI, and the relevant `main` gates MUST be checked after merge.

**Rationale**: Parallel execution is valuable only when integration ownership stays unambiguous.

### IX. Product Experience Doctrine

The product promise is **"Makolo marche pour vous."** The experience principle is
**"Pas le plaisir de rester. Le plaisir d'avancer."**

Now answers **"Qu'est-ce qui compte maintenant ?"** and may legitimately conclude
**"Tout est en ordre. ✓"**. Discover remains an exploratory field of real possibilities rather
than a retention feed.

Makolo MUST NOT optimize for artificial watch time, infinite scroll, likes, streaks, generic
popularity or re-engagement without real utility. Content and media MUST have context and purpose;
Presentation MUST NOT invent facts to make a surface look complete.

**Rationale**: Product quality is measured by real-world progress, not time spent in the interface.

### X. Agent and Spec Kit Governance

Spec Kit is a process layer for bounded change. It MUST NOT become a new architecture, a new
business ontology or a higher source of truth than Makolo's current runtime and canonical
documents.

ChatGPT remains the primary remote orchestration surface. Codex/ECC MAY execute bounded lanes, but
no agent framework may override Makolo architecture, invariants, security boundaries, canonical
documents or Git workflow.

Every non-trivial Spec Kit plan MUST identify the user problem, owner, base SHA, branch, in-scope
surfaces, forbidden areas, acceptance criteria, test/evidence requirements and merge gate.
`implement → converge` MAY repeat until Spec Kit reports convergence, but convergence never
replaces human/diff review, required tests or CI.

**Rationale**: Agent tooling accelerates execution; it does not receive product or architectural
authority.

## Sources of Truth and Spec Persistence

When sources conflict, use this precedence for the substance of a Makolo change:

1. current code, migrations and tests;
2. `docs/architecture/makolo-domain-blueprint.md`;
3. the current canonical documents for the affected domains and experience;
4. `docs/operations-runbook.md`;
5. current GitHub state;
6. historical handoffs, plans and conversation context.

`AGENTS.md`, `docs/operations/agent-orchestration.md` and
`docs/operations/ai-development-guardrails.md` define the working discipline around those
sources and MUST be followed.

Spec Kit feature artifacts describe a bounded intended change. They do not retroactively specify
all existing Makolo behavior. During a feature, the spec/plan/tasks MUST be reconciled when current
repository evidence changes. After merge, the feature directory is retained as a historical
delivery record; current runtime and canonical documents remain authoritative for future work.

The first brownfield adoption MUST NOT attempt to rewrite the whole Makolo system as specifications.

## Development Workflow and Review Gates

The default Makolo Spec Kit workflow is:

1. create a Makolo-owned branch from verified current `main`;
2. run `$speckit-specify` for one bounded change and explicit compatibility boundaries;
3. use `$speckit-clarify` when material behavior is ambiguous;
4. run `$speckit-plan` only after repository, collision and canonical-owner review;
5. use `$speckit-checklist` when an additional quality checklist is useful;
6. generate `$speckit-tasks`, marking parallel tasks only when write surfaces do not collide;
7. run `$speckit-analyze` before implementation for non-trivial work;
8. run `$speckit-implement`;
9. run `$speckit-converge` and repeat implementation/convergence while justified gaps remain;
10. review the diff, targeted/wider test evidence, migrations, security/privacy implications and CI;
11. reconcile with current `main`, merge only when green, then verify relevant post-merge gates.

Makolo does not install Spec Kit's Git extension in the initial adoption. Branch creation,
ownership, reconciliation and merge discipline remain controlled by the existing Makolo
orchestration contract.

The core `taskstoissues` skill is installed because it is part of the pinned Spec Kit core, but
it is optional and MUST NOT create GitHub issues unless the work item actually benefits from that
representation.

## Governance

This constitution governs Spec Kit-assisted planning and execution in Makolo. It does not
supersede higher-priority runtime/domain sources listed above. If this constitution conflicts with
a current canonical Makolo truth, the canonical truth wins and this constitution MUST be amended.

Amendments require a dedicated reviewed change that states the rationale and checks whether
`AGENTS.md`, agent orchestration, AI guardrails or Spec Kit adoption guidance must also change.

Constitution versioning follows semantic versioning:

- **MAJOR**: a principle is removed or redefined incompatibly;
- **MINOR**: a principle/section is added or materially expanded;
- **PATCH**: wording or clarification changes without changing meaning.

Every Spec Kit plan and analysis MUST perform a constitution compliance check. Any deliberate
deviation must be explicit, justified, bounded and reviewed; it MUST NOT be hidden as an
implementation convenience.

**Version**: 1.0.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-02
