# Implementation Plan: Mobile Mature — En cours

**Branch**: `feat/mobile-ongoing-mature` | **Base**: `297a4c635dafc49d78a95fd463a30a13ffa5ef54`  
**Spec**: `specs/003-mobile-ongoing-mature/spec.md`

## Brownfield evidence

- `main` courant vérifié : `297a4c635dafc49d78a95fd463a30a13ffa5ef54`.
- Aucun PR ouvert dans le dépôt au moment de l’audit.
- Aucune branche contenant `ongoing` trouvée ; les branches Mobile existantes ne sont pas concurrentes sans PR active.
- Runtime actuel : `OngoingScreen → PersonalRepository.watchOngoing() → personal.ongoing → ProjectionScreen`.
- `personal.ongoing` est serveur-owned et compose Journey/Readiness, Access, Dossier, Project, Waitlist, Transfer et Payment.
- Le socle adaptatif expose déjà `MakoloContentFrame`, `MakoloAdaptiveSplit`, `MakoloFocusPane` et `MakoloLayout.ongoingSplitMinWidth = 960`.
- Le common contract Batch 1 est porté par `spec/mobile-personal-batch1-contract` et reste hors modification.

## Scope / ownership

### In scope
- `mobile/lib/features/ongoing/**`
- tests propres à Ongoing
- spec artifacts sous `specs/003-mobile-ongoing-mature/**`

### Petite extension autorisée
Aucun seam partagé n’est requis a priori. Un adapter/selector local Ongoing peut vivre dans `mobile/lib/features/ongoing/**`.

### Forbidden
- `mobile/lib/design/**`
- `mobile/lib/presentation/contracts/**`
- `mobile/lib/dev/gallery/**`
- `mobile/lib/dev/scenarios/**`
- router / app shell / actor context
- sync / ProfileStore / Drift
- Django/API/migrations
- nouvelles permissions ou autorité

## Architecture cible

```
PersonalRepository.watchOngoing()
→ StoredProjection personal.ongoing
→ Ongoing selector/adapter
→ OngoingContinuityPresentation
→ Ongoing collection/detail UI
```

La Presentation est une projection locale de lecture ; elle ne persiste rien et ne reconstruit pas Readiness/Payment/Access/Requirement.

## Composition

### Compact / G06
- edge 16 dp
- header 56 dp
- première Continuité à 24 dp
- identité P2
- synthèse P2
- NEXT/MY_SIDE P1/P2
- metadata P1
- action par défaut 0
- progress absent
- CALM avec contenu conservé

### Wide / G07
- test 920/960/1000
- split à ~960 uniquement si les minima géométriques sont satisfaits
- Field 360 dp cible
- gutter 24 dp
- Focus ~600 dp
- single-pane sinon
- sélection/profondeur restaurées

## États

- true empty : « Rien en cours pour le moment. »
- calm with content : collection conservée
- content + offline : connaissance locale conservée + fraîcheur
- content + refresh error : contenu conservé + message localisé
- waiting / blocker / unknown / stale : distincts
- parallel movements : plusieurs dimensions dans une même Continuité

## Tests ciblés

- selector réel depuis `StoredProjection`
- plusieurs items et owner refs
- empty/calm
- offline/stale
- stream refresh error après contenu
- blocker vs waiting
- timing/place/capability handoff
- Compact / Wide / N2
- textScale 1.6
- Golden G06/G07
- absence de fixture runtime

## Merge gate

1. Diff limité aux fichiers de lane + specs.
2. Tests ciblés verts.
3. Goldens G06/G07 revus.
4. Pas de migration.
5. Pas de fake runtime.
6. CI PR verte.
7. Réconciliation avec le `main` courant avant intégration.
8. PR laissée ouverte ; aucun merge automatique.
