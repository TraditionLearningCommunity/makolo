# Feature Specification: Mobile Mature — Moi / Me

**Feature Branch**: `feat/mobile-me-mature`
**Created**: 2026-10-03
**Status**: Draft
**Input**: Mature Flutter surface Moi / Me, lane indépendante du premier lot personnel Mobile Mature.

## User Scenarios & Testing

### User Story 1 - Voir le capital durable déjà en place (Priority: P1)

Comme personne utilisant Makolo, je veux voir ce qui est déjà en place autour de moi pour faciliter la suite, sans confondre Moi avec Account, Settings ou un dashboard.

**Independent Test**: une vraie `StoredProjection personal.me` produit une composition section-first avec identité et territoires réellement présents.

**Acceptance Scenarios**
1. Une projection complète affiche Identity, Passport, Considerations, Collectives et Resources sans créer de vérité métier mobile.
2. Une section vide reste locale à cette section et ne masque pas les autres territoires.
3. Une section malformée produit un état local d'erreur sans casser Identity ni les autres territoires.

### User Story 2 - Rester utile avec le contenu déjà acquis (Priority: P1)

**Independent Test**: un snapshot connu peut être présenté avec freshness/reachability dégradés sans faux succès et sans disparition du contenu.

**Acceptance Scenarios**
1. `content + offline` conserve le contenu.
2. Une observation ancienne affiche une indication de fraîcheur.
3. Une revalidation requise n'est jamais présentée comme vérité actuelle pour une action sensible.

### User Story 3 - Ouvrir une profondeur sans absorber le domaine propriétaire (Priority: P2)

**Independent Test**: une Resource/Collective preview peut ouvrir une profondeur N2 locale de présentation ; toute action owner réelle reste liée à sa destination canonique lorsqu'elle existe.

**Acceptance Scenarios**
1. Compact ouvre la profondeur naturellement.
2. Wide utilise le seuil partagé Moi autour de 840 sans dashboard 4 colonnes.
3. Back ferme d'abord la profondeur puis quitte la surface.

### Edge Cases
- Projection absente sur l'appareil.
- Payload racine malformé.
- Identity présente mais tous les territoires vides.
- Section absente, vide ou malformée.
- Membership sans authority.
- Resource présente sans implication de Requirement satisfaction.
- Grand textScale en Compact et Wide.

## Requirements

### Functional Requirements
- **FR-001**: Le runtime MUST rester `PersonalRepository.watchMe() → StoredProjection personal.me → selector Me → MePresentation → Me UI`.
- **FR-002**: Moi MUST répondre à « Qu’est-ce qui est déjà en place autour de moi pour faciliter la suite ? ».
- **FR-003**: Moi MUST rester distinct de Account, Settings, CV universel, dashboard et score de complétion.
- **FR-004**: Le selector MUST adapter la vraie shape runtime de `personal.me`.
- **FR-005**: Les territoires MUST être section-first et inclure uniquement les sections réellement supportées par le payload.
- **FR-006**: Identity, Passport, Considerations, Collectives et Resources MUST être représentables indépendamment.
- **FR-007**: Une section vide MUST NOT devenir un Moi vide global.
- **FR-008**: Une section malformée MUST être isolée comme erreur locale.
- **FR-009**: Membership MUST NOT être présentée comme Permission/Mandate.
- **FR-010**: Resource MUST NOT être présentée comme Proof, JourneyArtifact, AccessCredential ni satisfaction Requirement.
- **FR-011**: G08 Compact MUST rester vertical, calme et lisible.
- **FR-012**: G09 Wide MUST utiliser au plus deux territoires simultanés avec le seuil commun `MakoloLayout.meTwoColumnMinWidth`.
- **FR-013**: La surface MUST préserver le contenu connu en cas d'état offline/refresh-error fourni par le runtime.
- **FR-014**: La surface MUST utiliser les primitives Presentation partagées et MUST NOT créer de MeSection de convenance.
- **FR-015**: La lane MUST NOT modifier router, shell, sync, ProfileStore schema, Drift schema, design partagé, contrats Presentation partagés ni scénarios/gallery.
- **FR-016**: Aucun fake data runtime Flutter ne doit alimenter la production.
- **FR-017**: La profondeur N2 MUST rester Presentation-only et ne pas fabriquer de route/owner/capability.
- **FR-018**: Aucun modèle ou migration Django/Drift n'est autorisé dans cette lane.

### Key Entities
- **MePresentation**: contrat Presentation partagé existant, structure + capital.
- **MeTerritoryPresentation**: territoire durable indépendant avec état local.
- **MeSelection**: adaptation lane-local de la StoredProjection vers MePresentation et détails de rendu sans nouvelle vérité métier.

## Success Criteria
- **SC-001**: Les tests ciblés couvrent full, sparse, section empty/error, offline-known, freshness, Identity, Passport, Considerations, Collectives, Resources, Resource N2, Compact, Wide et textScale critique.
- **SC-002**: Aucun fichier hors `mobile/lib/features/me/**`, tests Me et artifacts Spec Kit n'est modifié.
- **SC-003**: Aucun test ne dépend directement des fixtures dev/scenarios en production.
- **SC-004**: Le selector accepte une vraie StoredProjection de forme backend actuelle et ne dépend pas d'une shape fake simplifiée.

## Assumptions
- Base vérifiée: `main@297a4c635dafc49d78a95fd463a30a13ffa5ef54`.
- Le contrat commun vit sur `spec/mobile-personal-batch1-contract` et reste read-only pour cette lane.
- Le serveur Mobile Mature Demo Universe enrichira les vraies réponses sans changer le principe d'adaptation.
- Le reachability/refresh-error de source n'est pas actuellement exposé par `PersonalRepository.watchMe()`; la lane ne modifie pas le sync pour contourner ce gap.
