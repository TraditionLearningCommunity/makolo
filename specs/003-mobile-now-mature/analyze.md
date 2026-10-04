# Spec Analysis: Mobile Mature Now

## Findings

1. **No material Clarify required.** Server authority, runtime shape, lane scope and G01/G02 are explicit.
2. **Current generic screen is insufficient.** It renders every row as an identical Material Card and cannot express Now's dominant consequence or N2.
3. **Shared Presentation foundation is sufficient for geometry and state rendering.** No common primitive change is required for the basic Mature Now composition.
4. **Runtime source-state gap is transversal.** `watchNow()` supplies `StoredProjection` but not sync-source reachability/last refresh failure. This lane must not modify sync/ProfileStore to obtain it.
5. **Safe lane strategy:** make state cues injectable into the selector/screen boundary, default production to facts available from the snapshot, and cover offline/error compositions in dedicated component tests. Integrator can later connect the shared source-state signal without redesign.
6. **N3 must be conservative.** A source kind/id is not itself permission. Only navigate to an already-existing owner route; never synthesize a mutation/capability.
7. **Golden references are structural contracts, not license to edit common fixtures.** This lane can render its own test inputs through the shared harness.

## Risk controls

- Malformed item → skip rather than invent “Élément Makolo”.
- Empty valid `items` → calm success.
- Missing projection → not acquired, never calm.
- Unknown capability → no CTA.
- Server ordering → retained exactly.
- Compact/Wide → same selected truth; only geometry changes.
