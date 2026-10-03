# Feature Specification: Mobile Mature — Maintenant / Now

**Feature Branch**: `feat/mobile-now-mature`  
**Created**: 2026-10-03  
**Status**: Implementing  
**Base**: `main@297a4c635dafc49d78a95fd463a30a13ffa5ef54`

## User problem

La surface Flutter personnelle `Maintenant` reste aujourd'hui une liste générique rendue par `ProjectionScreen`. Elle doit devenir la projection d'attention Mature répondant uniquement à :

> **Qu'est-ce qui compte maintenant ?**

Le serveur reste propriétaire de l'admission dans `personal.now`. Flutter présente le dernier réel acquis, conserve le contenu local utile et n'invente ni urgence, ni ranking, ni confirmation.

## Parallel contract

Cette lane respecte `specs/002-mobile-personal-batch1-contract/spec.md` depuis la branche `spec/mobile-personal-batch1-contract`. Elle ne modifie pas ce contrat.

**Lane owner**: Now  
**In scope**:
- `mobile/lib/features/now/**`
- tests Now dédiés
- artefacts Spec Kit de cette feature

**Protected / forbidden**:
- `mobile/lib/design/**`
- `mobile/lib/presentation/contracts/**`
- `mobile/lib/dev/gallery/**`
- `mobile/lib/dev/scenarios/**`
- router, shell, actor context, sync engine
- ProfileStore / Drift schema
- migrations Django / Drift
- domaines métier

## User stories

### US1 — Lire immédiatement la conséquence actuelle (P1)

Étant donné une projection `personal.now` connue contenant une ou plusieurs situations, la personne voit d'abord la conséquence la plus forte fournie par l'ordre serveur, son contexte humain, puis une action seulement lorsqu'une capability réellement exploitable l'autorise.

Acceptance:
1. Le premier item serveur devient le dominant perceptif sans score ni re-ranking local.
2. Les situations suivantes restent moins fortes.
3. Aucun CTA n'est inventé depuis un texte ou un état.
4. `items=[]` connu rend `Tout est en ordre. ✓`.

### US2 — Rester utile hors ligne et honnête sur la certitude (P1)

Étant donné un snapshot connu, la perte réseau, une fraîcheur dégradée, une opération pending ou une erreur de refresh ne remplacent pas le contenu par un écran générique.

Acceptance:
1. `content + offline` conserve les situations.
2. `content + refresh error` conserve les situations et signale l'échec.
3. `pending` n'est jamais rendu comme confirmé.
4. Le contenu non acquis reste distinct d'un calme connu.

### US3 — Approfondir sans perdre Maintenant (P1)

Une situation peut ouvrir un N2 contextuel. En Wide, le split apparaît seulement si un N2 est réellement ouvert. En Compact, la profondeur remplace temporairement le champ mais le retour restaure la collection et sa position.

Acceptance:
1. Root Wide calme, largeur bornée, aucun remplissage artificiel.
2. Split à partir du seuil commun Now seulement si sélection ouverte.
3. Back restaure sélection/position utile.
4. N2 montre seulement les informations déjà présentes dans le contrat Presentation ou un handoff propriétaire.

### US4 — Respecter G01 et G02 (P1)

G01 Compact conserve faible densité, conséquence dominante, CTA réel seulement.  
G02 Wide + N2 conserve le root calme et utilise le split commun.

## Runtime contract

Production:

```text
PersonalRepository.watchNow()
→ StoredProjection
→ NowSelector
→ NowSituationPresentation + MakoloSurfacePresentation
→ Now UI
```

Shape serveur v1 attendue:

```json
{
  "items": [{
    "key": "opaque",
    "kind": "journey.action",
    "dimension": "action",
    "source": {"kind": "journey", "id": "uuid"},
    "state": "action_required",
    "title": "Action requise",
    "summary": "...",
    "timing": {},
    "capabilities": [],
    "links": {}
  }]
}
```

Le selector ne parse jamais `title`/`summary` pour décider de l'action et ne calcule pas l'admission.

## Functional requirements

- **FR-001**: consommer uniquement `PersonalRepository.watchNow()` comme source production de la projection racine.
- **FR-002**: adapter une vraie `StoredProjection` vers `NowSituationPresentation`.
- **FR-003**: préserver l'ordre serveur; aucun ranking local.
- **FR-004**: utiliser `MakoloSurfacePresentation` pour disponibilité/fraîcheur/reachability/commit/failure.
- **FR-005**: traiter projection absente, loading initial, content, calm, stale, pending et erreurs non bloquantes comme états distincts.
- **FR-006**: ne jamais transformer `pending` en `confirmed`.
- **FR-007**: rendre le dominant sans transformer chaque situation en Card identique.
- **FR-008**: réutiliser `MakoloContentFrame`, `MakoloAdaptiveSplit`, `MakoloFocusPane`, `MakoloAttentionBlock`, `MakoloCard`, `MakoloMetadata` et primitives communes lorsque pertinentes.
- **FR-009**: n'afficher une action primaire que si une capability runtime exploitable est reconnue; sinon aucune action.
- **FR-010**: ouvrir N2 à partir de la sélection réelle; Wide split uniquement avec N2 ouvert.
- **FR-011**: préserver la même vérité Compact/Wide et supporter textScale 1.6 sans hauteur textuelle fixe.
- **FR-012**: ne dépendre d'aucun `PresentationFixtureUniverse` en production.
- **FR-013**: ne créer aucun modèle persistant SituationNow, domaine, router, shell, sync engine ou migration.
- **FR-014**: tester le selector avec la shape runtime v1 réelle.
- **FR-015**: conserver `PersonalRepository.watchNow()` inchangé.

## COMMON GAP

Le runtime de la lane reçoit actuellement le snapshot local via `watchNow()`, mais cette API de repository n'expose pas l'état de source sync/reachability ou le dernier refresh error. Les primitives communes savent déjà représenter ces axes.

La lane:
- ne modifie pas le sync ni ProfileStore;
- expose/teste l'état Presentation de manière injectable et compatible;
- laisse le raccord source-state à l'intégrateur commun si ce signal doit être remonté à l'écran de production.

Lanes potentiellement concernées: Now, Ongoing, Discover, Me.

## Success criteria

- Selector réel depuis `StoredProjection`.
- G01 Compact structurel: conséquence dominante, CTA conditionnel, calm.
- G02 Wide structurel: root calme + split uniquement après sélection.
- Tests: situation unique, multiples, calm, offline-known, stale, pending, refresh-error, textScale 1.6.
- Aucun import production depuis `mobile/lib/dev/**`.
- Aucun changement dans les seams protégés.
- PR laissée ouverte; CI est le merge gate.
