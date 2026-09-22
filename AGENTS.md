# Makolo — Agent & Human Working Contract

This repository is a mature product in active development. Humans, ChatGPT, Codex and optional agent harnesses may all contribute, but GitHub `main` remains the shared source of integration truth.

## Before meaningful work

1. Refresh the current `main` HEAD.
2. Inspect recent commits and active PRs/branches relevant to the scope.
3. Read the current code, migrations and tests before trusting an older plan or handoff.
4. Read `docs/architecture/makolo-domain-blueprint.md` and the canonical docs for the domain being changed.
5. Check `docs/operations-runbook.md` for operational consequences.
6. Perform a collision audit before parallel work.

Runtime wins over historical notes. A roadmap describes a target or sequence, not proof that something is still missing.

## Architectural invariants

- A Profile is a global person; never a global “participant” or “organizer”.
- Assignment = responsibility. Mandate/Permission = authority.
- Membership/Group/Team never grants authority implicitly.
- Readiness is derived; do not duplicate it as a generic persistent state.
- Requirement, Form, Resource, JourneyArtifact, Proof, Trust Credential and AccessCredential are distinct.
- Access = right; AccessCredential = representation/secret; AccessUse = observed use.
- Capacity = “how many?”; Placement = “where?”.
- Waitlist != Live Queue.
- JourneyStep != operational checkpoint.
- Dossier != generic task manager; Project != generic task manager.
- Owning a document != finding it != satisfying a Requirement.
- Composition never implicitly transfers Permission, Mandate, Access, Payment or private data.
- Public/collective projections apply minimum disclosure.

Before adding a model or persistent state, verify whether the need belongs in an existing domain, relation, orchestration service, selector/read model, Readiness, Domain Events, Analytics or Presentation.

## Git and ownership

- Important work uses a dedicated branch and PR.
- One owner per work item/branch.
- Do not let two workers write the same files/surfaces concurrently without an explicit integrator.
- Parallelize only independent write surfaces.
- Do not merge with red CI.
- Never weaken/remove tests to obtain green CI.
- Fix root causes.
- Reconcile long-lived branches with current `main` before final integration.
- After merge, verify `main` and the relevant gates.

Manual local work, ChatGPT+GitHub work and Codex/ECC work may coexist. Push local changes before expecting remote agents to review them.

## Change contract

Every meaningful work item should state:

- user problem / objective;
- owner;
- base SHA;
- branch;
- in-scope files/surfaces;
- forbidden areas;
- acceptance criteria;
- tests/evidence;
- merge gate.

For domain changes, include targeted tests first, then the relevant wider suite, migration checks, PostgreSQL where needed, server-side authorization/IDOR checks, concurrency/idempotence where relevant and backward-data compatibility.

## Product boundaries

Makolo’s promise is **“Makolo marche pour vous.”**

- Home asks: **“Qu’est-ce qui compte maintenant ?”**
- Discover asks: **“Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?”**
- Principle: **“Pas le plaisir de rester. Le plaisir d’avancer.”**

Do not optimize for artificial watch time, infinite scroll, likes or generic popularity. Content/media must have context and purpose. Presentation represents facts; it does not own them.

## Operational and security discipline

- Never invent production URLs, providers, accounts, environment variables, secrets or deployment targets.
- PythonAnywhere remains a temporary beta/test environment until official docs/configs say otherwise.
- Never expose passwords, tokens, private keys, sensitive env vars, full credentials/QRs or unnecessary PII.
- New APIs, caches, logs, media and analytics must respect privacy and minimum disclosure.

## Preferred collaboration model

ChatGPT is the primary remote orchestration surface for this project. Codex/ECC may be used for bounded local/parallel execution, but no external agent framework overrides Makolo’s architecture, invariants, docs or Git workflow.

The detailed coordination procedure lives in:

`docs/operations/agent-orchestration.md`
