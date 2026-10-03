# Feature Specification: Mobile Mature — Moi / Me

**Feature Branch**: `feat/mobile-me-mature`  
**Created**: 2026-10-03  
**Status**: Implemented — final CI gate pending  
**Input**: Mature Flutter surface Moi / Me, lane indépendante du premier lot personnel Mobile Mature.

## User Scenarios & Testing

### User Story 1 - Voir le capital durable déjà en place (Priority: P1)

Comme personne utilisant Makolo, je veux comprendre ce qui est déjà en place autour de moi pour faciliter la suite, sans confondre Moi avec Account, Settings, un profil social ou un dashboard.

**Independent Test**: une vraie `StoredProjection personal.me` produit une composition SECTION-FIRST avec identité et territoires réellement présents.

**Acceptance Scenarios**
1. Une projection complète affiche Identity, Passport, Considerations, Collectives et Resources sans créer de vérité métier mobile.
2. Support apparaît uniquement lorsqu'un élément support est réellement disponible.
3. Une section vide reste locale à cette section et ne masque pas les autres territoires.
4. Une section malformée produit un état local d'erreur sans casser Identity ni les autres territoires.
5. Une projection sparse conserve Moi et ses territoires avec des messages humains locaux, sans score ni gamification de complétion.

### User Story 2 - Rester utile avec le contenu déjà acquis (Priority: P1)

**Independent Test**: un snapshot connu reste visible pendant offline, syncing ou refresh-error, avec des cues issus du runtime partagé.

**Acceptance Scenarios**
1. `content + offline` conserve le contenu.
2. `content + syncing` conserve le contenu et donne un feedback discret.
3. Une erreur de la source `personal.me` conserve le snapshot et ne remplace pas Moi par un écran d'erreur.
4. Une observation ancienne affiche une indication de fraîcheur issue des métadonnées existantes.
5. Aucun TTL arbitraire n'est créé dans la feature.

### User Story 3 - Ouvrir une profondeur sans absorber le domaine propriétaire (Priority: P2)

**Independent Test**: une preview personnelle peut ouvrir une profondeur N2 de présentation sans changer de vérité métier.

**Acceptance Scenarios**
1. Compact ouvre la profondeur comme changement de focus.
2. Wide peut utiliser un pane lorsque la géométrie partagée le permet.
3. Back ferme d'abord la profondeur et restitue Moi.
4. Le resize ne change ni l'identité de la ressource sélectionnée ni la vérité présentée.

### Edge Cases
- Projection absente sur l'appareil.
- Première disponibilité offline sans snapshot.
- Identity présente avec tous les territoires vides.
- Famille imbriquée d'un territoire malformée.
- Membership sans autorité.
- Resource présente sans implication de Requirement satisfaction.
- Support entièrement indisponible.
- Grand textScale en Compact.
- Largeur 800, 840 et 900.

## Requirements

### Functional Requirements
- **FR-001**: Le runtime MUST suivre `PersonalRepository.watchMe() → StoredProjection personal.me → MeSelector → MePresentation/MeSelection → Me UI`.
- **FR-002**: L'état propriétaire MUST venir de `SyncSources` via le helper partagé `OwnerSourceState`, et l'état offline/syncing global MUST venir de `SyncStatusScope`.
- **FR-003**: Moi MUST répondre à « Qu’est-ce qui est déjà en place autour de moi pour faciliter la suite ? ».
- **FR-004**: Moi MUST rester distinct de Account, Settings, CV universel, profil social, dashboard et score de complétion.
- **FR-005**: Le selector MUST adapter la vraie shape runtime de `personal.me`.
- **FR-006**: Moi MUST être SECTION-FIRST.
- **FR-007**: Identity, Passport, Considerations, Collectives et Resources MUST être représentables indépendamment.
- **FR-008**: Support MUST être absent lorsque le runtime ne fournit aucun support disponible.
- **FR-009**: Une section vide MUST NOT devenir un Moi vide global.
- **FR-010**: Une section malformée MUST être isolée comme erreur locale.
- **FR-011**: Membership/Group/Team MUST NOT être présentés comme Permission/Mandate.
- **FR-012**: PersonalAsset, Proof et Credential MUST rester des familles distinctes.
- **FR-013**: Posséder une ressource MUST NOT être présenté comme satisfaction d'un Requirement, Proof accepté, Credential ou Access.
- **FR-014**: G08 Compact MUST rester vertical, calme et lisible.
- **FR-015**: À 800 dp la composition MUST rester single-territory; à partir de 840 dp elle MAY utiliser deux territoires uniquement si au moins deux territoires ont du contenu.
- **FR-016**: Wide MUST rester limité à deux territoires simultanés et MUST NOT devenir un dashboard.
- **FR-017**: La surface MUST préserver le contenu connu pendant offline/syncing/refresh-error.
- **FR-018**: Sans snapshot local, le loading MUST préserver la grammaire des sections au lieu d'afficher un spinner global.
- **FR-019**: La surface MUST utiliser les primitives Presentation partagées et MUST NOT créer un modèle métier persistant parallèle.
- **FR-020**: La lane MUST NOT modifier router, shell, SyncEngine, ProfileStore schema, Drift schema, design partagé, contrats Presentation partagés ni scénarios/gallery.
- **FR-021**: Aucun fake data runtime Flutter ne doit alimenter la production.
- **FR-022**: La profondeur N2 MUST rester Presentation-only et ne pas fabriquer de capability ou d'autorité.
- **FR-023**: Aucun modèle ou migration Django/Drift n'est autorisé dans cette lane.
- **FR-024**: Les textes utilisateur MUST éviter le vocabulaire d'architecture interne.

### Key Entities
- **MePresentation**: contrat Presentation partagé existant, structure + capital.
- **MeTerritoryPresentation**: territoire durable indépendant avec état local.
- **MeSelection**: adaptation non persistée de la StoredProjection vers la présentation.
- **MeItemPresentation**: preview non persistée conservant la `StructuredDestination` et la représentation humaine.
- **OwnerSourceState**: état partagé, non métier, dérivé de `SyncSources`; la feature le consomme mais ne le possède pas.

## Success Criteria
- **SC-001**: Les tests ciblés couvrent real shape, full, sparse, Support conditionnel, section empty/error, freshness, refresh avec contenu, offline local-first, source failure récupérable, N2/back, 800/840/900 et textScale 1.0/1.3/1.6.
- **SC-002**: Les seules modifications transversales autorisées sont la couture minimale `PersonalRepository.watchMeSource()` réutilisant `OwnerSourceState`; aucun schema/sync engine/design/router partagé n'est modifié.
- **SC-003**: Aucun test ne dépend des fixtures dev/scenarios comme runtime de production.
- **SC-004**: Le selector accepte une vraie StoredProjection de forme backend actuelle et ne dépend pas d'une shape fake simplifiée.
- **SC-005**: Format, analyze, tests Mobile pertinents, Android build et CI de #451 sont verts avant T015.

## Runtime vérifié
Réconciliation du 2026-10-03:
- `main@80a3c76037f0d2278a0848bf8c3e25e8566de822`;
- `personal.me` expose toujours `identity/passport/considerations/collectives/resources/support/links`;
- `OwnerSourceState` et `SyncStatusScope` existent dans le socle courant;
- les lanes Now/Ongoing/Discovery ne touchent pas `PersonalRepository` ni `features/me/**`.

## Assumptions
- Les actions profondes restent propriétaires de leurs domaines et ne sont pas inventées dans Moi.
- Une permission localisée ne peut être représentée que si le contrat runtime du territoire fournit réellement ce signal; Moi ne l'infère pas.
