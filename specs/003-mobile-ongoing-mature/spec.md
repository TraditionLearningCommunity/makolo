# Feature Specification: Mobile Mature — En cours / Ongoing

**Feature Branch**: `feat/mobile-ongoing-mature`  
**Base SHA**: `297a4c635dafc49d78a95fd463a30a13ffa5ef54`  
**Status**: Draft → implementation lane  
**Parent contract**: `specs/002-mobile-personal-batch1-contract/spec.md` (read-only; parent branch `spec/mobile-personal-batch1-contract`)

## User Story 1 — Lire la continuité personnelle réelle (P1)

En tant que personne utilisant Makolo, je veux comprendre parmi ce que j’ai réellement engagé où j’en suis et ce qui continue, sans reconstruire moi-même Journey, Access, Requirement, Payment, Waitlist ou Dossier.

**Acceptance**
- Given une vraie `StoredProjection` issue de `personal.ongoing`, When Ongoing la lit, Then elle la transforme via un adapter/selector local en `OngoingContinuityPresentation` sans nouveau modèle métier.
- Given plusieurs items, Then chaque Continuité conserve l’identité owner `source.kind + source.id` lorsque fournie.
- Given une même réalité également visible dans Now, Then la référence owner reste compatible sans réutiliser la présentation Now.

## User Story 2 — Distinguer calme, vide et connaissance locale (P1)

- Given plusieurs Continuités sans intervention urgente, Then elles restent visibles comme CALM WITH CONTENT.
- Given `items: []` synchronisé, Then afficher exactement « Rien en cours pour le moment. ».
- Given contenu connu hors ligne, Then conserver ce contenu et indiquer sa fraîcheur lorsqu’elle est pertinente.
- Given refresh stream error après contenu connu, Then conserver le contenu et localiser l’erreur sans basculer en écran vide/global error.

## User Story 3 — Composer sans fabriquer de progression (P1)

La représentation peut exposer identité, synthèse, SETTLED, MY_SIDE, ELSEWHERE, NEXT, blocker, waiting, timing/place et handoff Jour J lorsque les faits existent.

Interdits : pourcentage, progress bar artificielle, checklist générique, copie locale de Readiness/Payment/Access/Requirement state, faux succès.

## User Story 4 — S’adapter à Compact/Wide sans perdre la continuité (P1)

- Compact : collection calme, rows lisibles, ouverture vers profondeur.
- Wide : master/detail naturel à partir de ~960 dp, avec Field ≥ 320 dp, gutter 24 dp, Focus protégé par le socle commun.
- À textScale 1.6, aucun contenu essentiel n’est tronqué et le split peut retomber en single-pane.

## Functional Requirements

- FR-001 : La production suit `PersonalRepository.watchOngoing() → StoredProjection personal.ongoing → selector/adapter → OngoingContinuityPresentation → UI`.
- FR-002 : Le selector/adapter consomme la shape runtime réelle actuelle : `kind`, `source`, `state`, `title`, `ready`, `actor_interventions`, `continuation`, `blocker`, `next`, `occurrence`, `timing`, `place`, `capabilities`, `links`.
- FR-003 : `waiting`, `blocked`, `unknown`, `stale` et erreur de flux restent distincts.
- FR-004 : Les quatre dimensions `SETTLED/MY_SIDE/ELSEWHERE/NEXT` sont des dimensions de lecture, pas des sections obligatoires.
- FR-005 : Le média reste secondaire et contextuel ; aucun média orphelin.
- FR-006 : Les actions affichées sont dérivées uniquement de capabilities/links réellement présents.
- FR-007 : Le handoff Jour J n’est représenté que lorsqu’un `occurrence` et la capability/lien correspondants existent.
- FR-008 : L’état local connu est préservé pendant offline/refresh error ; aucune fraîcheur distante n’est inventée.
- FR-009 : Le vrai empty n’est pas remplacé par Discover ou des suggestions.
- FR-010 : L’ordre est stable et compréhensible ; aucune ranking opaque locale.
- FR-011 : Aucun modèle métier/persistant `Continuity`, aucun schema Drift/Django, aucun changement router/shell/sync/app runtime.
- FR-012 : Les primitives communes existantes sont réutilisées ; aucun `OngoingCard` de convenance.

## Acceptance scenarios

1. Plusieurs Continuités : Visa/Vol/Formation lisibles sans todo-list.
2. Calm with content : contenu présent, aucune urgence artificielle.
3. True empty : « Rien en cours pour le moment. ».
4. Offline : contenu conservé + indicateur de fraîcheur honnête.
5. Refresh error : contenu conservé + erreur localisée.
6. Blocker : le blocker est rattaché à la transition concernée.
7. Waiting : attente distincte d’un blocker.
8. Parallel movements : plusieurs `MY_SIDE/NEXT/ELSEWHERE` peuvent coexister.
9. Compact : G06.
10. Wide + N2 : G07, seuil ~960.
11. N2 : sélection conservée au retour.
12. textScale 1.6 : pas de troncature essentielle.
13. Jour J : handoff seulement avec Occurrence réelle/capability réelle.
14. Production : aucune dépendance à `PresentationFixtureUniverse`.

## Goldens

- G06 — En cours / Compact : plusieurs Continuités, identité + synthèse + NEXT/MY_SIDE, action 0 par défaut, progress absent.
- G07 — En cours / Wide + N2 : Field 360 dp, gutter 24 dp, Focus ~600 dp, split seulement lorsque les contraintes sont satisfaites, profondeur sans perte de collection.

Références : viewport 360×800 et 1440×900 ; textScale 1.0/1.3/1.6 ; seuil split 920/960/1000.

## Out of scope / forbidden

`mobile/lib/design/**`, `mobile/lib/presentation/contracts/**`, `mobile/lib/dev/gallery/**`, `mobile/lib/dev/scenarios/**`, router, app shell, actor context, sync, ProfileStore/Drift schema, Django migrations.

Aucune nouvelle vérité métier, API, migration, sync engine, shell, router, universal presentation item, fake success ou fixture runtime.

## Common Gap

Si une primitive partagée manque réellement : documenter le manque, pourquoi le socle ne suffit pas, les lanes concernées et la plus petite extension possible. Ne pas la dupliquer localement.

## Success Criteria

- La chaîne runtime réelle est couverte par tests ciblés.
- G06/G07 sont couverts par Goldens.
- CALM WITH CONTENT ≠ TRUE EMPTY.
- Offline et refresh error préservent le contenu connu.
- Waiting ≠ blocker.
- Owner identity reste stable lorsqu’elle est fournie.
- Aucune dépendance production aux fixtures fake.
- Aucun fichier interdit n’est modifié.
