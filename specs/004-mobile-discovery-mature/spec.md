# Feature Specification: Mobile Mature — Découvrir / Discover

**Feature Branch**: `feat/mobile-discovery-mature`  
**Created**: 2026-10-03  
**Status**: Implementing  
**Base**: `main@297a4c635dafc49d78a95fd463a30a13ffa5ef54`

## User problem

La surface Flutter personnelle `Découvrir` possède déjà acquisition local-first, snapshots, `DiscoveryRepository`, `DiscoverySelector`, recherche, save/unsave, détails owner et fondation MapLibre, mais sa Presentation reste principalement une liste uniforme et la carte vit comme un corpus séparé.

La lane doit maturer la Presentation autour de :

> **Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

Découvrir reste un champ de possibilités réelles, exploratoire, visuel, spatial lorsque pertinent, multi-famille et contextuel. Ce n’est ni un feed, ni une liste de nouveautés, ni un ranking Flutter.

## Parallel contract

Cette lane applique `specs/002-mobile-personal-batch1-contract/spec.md` lu depuis `spec/mobile-personal-batch1-contract`. Elle ne modifie pas ce contrat.

**Lane owner**: Discover  
**In scope**:
- `mobile/lib/features/discovery/**`
- tests Discovery dédiés
- `specs/004-mobile-discovery-mature/**`

**Protected / forbidden**:
- `mobile/lib/design/**`
- `mobile/lib/presentation/contracts/**`
- `mobile/lib/dev/gallery/**`
- `mobile/lib/dev/scenarios/**`
- router/app shell/actor context
- sync engine / ProfileStore / Drift schema
- migrations Django / Drift
- ranking/relevance locale

## User stories

### US1 — Explorer un champ de possibilités sans feed (P1)

Étant donné une vraie projection `discovery.items`, la personne voit les possibilités dans l’ordre serveur, sous des représentations adaptées à leur famille et à leurs données, sans CTA d’engagement systématique.

Acceptance:
1. Le selector conserve l’ordre serveur.
2. Une possibilité n’est pas modélisée comme une Card universelle.
3. Le média est rendu seulement lorsqu’il existe ou qu’un fallback contextuel est utile.
4. Aucun score/re-ranking n’est calculé côté Flutter.

### US2 — Adapter G03/G04 sans changer la vérité (P1)

Compact présente un champ lisible avec la possibilité suivante perceptible. Wide utilise la largeur pour une vraie grille adaptative commune, sans dashboard ni complexité artificielle.

Acceptance:
1. G03 Compact à 360x800 utilise une composition verticale.
2. G04 Wide à 1440x900 utilise `MakoloAdaptiveGrid`.
3. Compact/Wide conservent les mêmes items, leur ordre et leurs owner links.
4. textScale 1.6 reste utilisable.

### US3 — Spatialiser le même champ G05 (P1)

La carte est une représentation du même champ sélectionné, pas un second corpus de vérité.

Acceptance:
1. G05 utilise `MakoloSpatialFrame`.
2. Les points cartographiables sont dérivés de `DiscoveryCollectionPresentation`.
3. La sélection d’une possibilité dans la liste pilote la représentation spatiale.
4. Une possibilité distante ou non cartographiable reste visible dans le champ.
5. Le runtime legacy `discovery.map` peut rester compatible, mais G05 ne dépend pas d’un second dataset.

### US4 — Distinguer les fins et le réseau (P1)

Acceptance:
1. `NO_MATCH`: critères présents + résultat vide.
2. `NO_CURRENT_PROPOSAL`: aucun critère + champ connu vide.
3. `END_OF_FIELD`: dernier corpus/page utile atteint.
4. `OFFLINE_WITH_SNAPSHOT`: snapshot conservé, fraîcheur/reachability honnêtes.
5. `OFFLINE_NO_SNAPSHOT`: impossibilité de charger du nouveau, jamais rendue comme « aucun résultat ».
6. Aucun élargissement silencieux des critères.

### US5 — Préserver contexte et owner depth (P1)

Acceptance:
1. query/filtres restent dans `DiscoveryQuery` et ne sont pas supprimés lors d’un refresh.
2. pagination conserve la query.
3. save/unsave reste owner-backed et distinct de Watch/engagement.
4. N2 continue via les owners/detail existants; aucune Journey n’est créée par save.
5. la Production ne dépend pas de `PresentationFixtureUniverse`.

## Runtime contract

```text
vraie API Discovery
→ DiscoveryRepository / SyncSource
→ ProfileStore StoredProjection
→ DiscoverySelector
→ DiscoveryFieldSelection / DiscoveryItemPresentation
→ Discover UI
```

La collection réelle reste `GET /api/v1/discovery/items/` / projection `discovery.items`.

## Functional requirements

- **FR-001**: préserver `DiscoveryRepository`, snapshots et `DiscoverySelector`; évolution, pas réécriture.
- **FR-002**: consommer une vraie `StoredProjection` `discovery.items`.
- **FR-003**: préserver strictement l’ordre serveur.
- **FR-004**: ne calculer aucun score, ranking, popularity ou pertinence Molongo locale.
- **FR-005**: ne créer aucun modèle persistant `Possibility`.
- **FR-006**: G03 doit utiliser le système commun et une composition compacte non uniforme.
- **FR-007**: G04 doit utiliser `MakoloAdaptiveGrid`.
- **FR-008**: G05 doit dériver ses points du même `DiscoveryCollectionPresentation` et utiliser `MakoloSpatialFrame`.
- **FR-009**: réutiliser `MakoloMediaFrame`; média absent reste légitime.
- **FR-010**: distinguer explicitement NO_MATCH, END_OF_FIELD, NO_CURRENT_PROPOSAL, OFFLINE_WITH_SNAPSHOT et OFFLINE_NO_SNAPSHOT.
- **FR-011**: un refresh ne doit pas effacer un snapshot utilisable.
- **FR-012**: une erreur de refresh avec contenu reste recoverable.
- **FR-013**: query/filtres restent stables lors de pagination/refresh.
- **FR-014**: save/unsave reste strictement capability-backed; Bookmark != Watch != engagement.
- **FR-015**: aucun CTA d’engagement systématique.
- **FR-016**: owner depth existante reste propriétaire des détails.
- **FR-017**: une possibilité peut ne pas être cartographiable sans disparaître du champ.
- **FR-018**: le code Production ne doit pas importer `mobile/lib/dev/**`.
- **FR-019**: aucun seam protégé ni migration n’est modifié.
- **FR-020**: tests ciblés couvrent parsing réel, G03/G04/G05 structurels, fins, offline, média, spatialité, ordre, textScale et save contract.

## COMMON GAP

Le composant partagé `ConfiguredMakoloMapView` expose aujourd’hui un viewport initial et un tap carte, mais pas:
- d’API commune de markers/annotations;
- de callback de changement de caméra;
- de contrôleur partagé permettant de restaurer précisément centre + zoom.

La lane ne duplique pas MapLibre localement et ne modifie pas `mobile/lib/platform/maps/**`.

Conséquence bornée:
- G05 utilise le même field et peut piloter le viewport initial depuis la sélection;
- la persistance exacte du zoom/centre et une sélection marker ↔ liste complète restent un **COMMON GAP** pour l’intégrateur Presentation/Maps.

Lanes potentiellement concernées: Discover, futures surfaces spatiales/Jour J.

## Success criteria

- G03 Compact structurel vert.
- G04 Wide grid structurel vert.
- G05 Wide Spatial structurel vert sur le même field.
- vraies shapes `StoredProjection` testées.
- états de fin et offline distincts.
- aucune dépendance Production aux fixtures.
- aucune duplication de repository/sync/router/shell.
- PR ouverte, non mergée; CI comme gate.
