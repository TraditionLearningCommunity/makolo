# Implementation Plan: Mobile Mature — Moi / Me

**Branch**: `feat/mobile-me-mature` | **Date**: 2026-10-03 | **Spec**: `specs/003-mobile-me-mature/spec.md`

## Summary
Remplacer le wrapper générique de Moi par une composition SECTION-FIRST alimentée par `personal.me`, adapter la vraie shape runtime via `MeSelector`, et raccorder les états local-first à l'infrastructure partagée déjà existante sans créer de vérité métier ou de sync parallèle.

## Technical Context
**Language/Version**: Dart 3.13.3 / Flutter 3.47.3 selon la CI actuelle  
**Primary Dependencies**: Flutter, Presentation foundation existante, `OwnerSourceState`, `SyncStatusScope`  
**Storage**: `ProjectionSnapshots` et `SyncSources` existants, aucune nouvelle table  
**Testing**: flutter_test, PresentationHarness, CI Mobile officielle  
**Target Platform**: Flutter Android/mobile, géométrie adaptative  
**Project Type**: mobile app  
**Constraints**: local-first, Profile-scoped, aucune autorité locale, aucune migration, aucun nouveau moteur sync

## Constitution Check
- Runtime courant relu avant correction: PASS.
- Aucun nouveau modèle/persisted state: PASS.
- Profile reste personne globale: PASS.
- Membership ≠ authority: PASS.
- Resource/Proof/Credential/Requirement restent distincts: PASS.
- Localement disponible ≠ autoritatif: PASS.
- Aucun faux succès: PASS.
- Branche dédiée + PR + CI gate: PASS.

## Brownfield / collision audit
État vérifié avant correction:
- `main@80a3c76037f0d2278a0848bf8c3e25e8566de822`.
- Lane Moi avant corrections: `c22e55424b5a13276a9ae9867c2433dc12c87060`.
- PR #451 ouverte.
- PR #446 Now: `features/now/**` uniquement.
- branche Ongoing: `features/ongoing/**` uniquement.
- PR #453 Discovery: `features/discovery/**` + seed/templates publics.
- PR #452 Demo Universe: pas de collision Me/repository/sync partagés détectée.
- Le commit `main` ajouté depuis l'ancienne base ne touche aucun fichier mobile.
- Aucun parallèle audité ne touche `mobile/lib/repositories/personal_repository.dart`.

## Scope code final
- `mobile/lib/features/me/me_screen.dart`
- `mobile/lib/features/me/me_selector.dart`
- `mobile/lib/repositories/personal_repository.dart` — couture minimale source-state
- `mobile/test/me_mature_test.dart`
- `specs/003-mobile-me-mature/**`

Aucun changement dans router, shell, SyncEngine, tables Drift, Presentation contracts, design system ou scénarios dev.

## Runtime shape
`personal.me` expose actuellement:
- identity;
- passport;
- considerations;
- collectives;
- resources;
- support;
- links.

Le selector mappe ces sections sans reconstruire les owners.

## Source-state / local-first
Le gap initial est fermé en réutilisant le socle existant:

```text
PersonalRepository.watchMe()
  → ProjectionSnapshots / personal.me

PersonalRepository.watchMeSource()
  → watchOwnerSourceState(...)
  → SyncSources / personal.me

SyncStatusScope
  → offline / syncing global lifecycle
```

Aucune nouvelle table, aucun TTL arbitraire, aucune duplication de SyncEngine.

## Responsive / G08-G09
- < 840: sections verticales.
- >= 840: deux territoires seulement si au moins deux territoires ont du contenu.
- maximum 2 colonnes.
- N2: `MakoloAdaptiveSplit` lorsque la géométrie `fieldMin + gutter + focusMin` le permet; sinon plein champ.
- Le breakpoint est calculé sur la largeur disponible à la surface, avant le padding du ContentFrame.

## Personality de territoire
- Passport: Unit plus riche.
- Considerations: rows légères.
- Collectives: rows d'identité.
- Resources: collection compacte avec familles visuellement distinctes.
- Support: uniquement si disponible.

## Tests ciblés
- selector: vraie shape, full, sparse, support conditionnel, nested malformed, freshness, distinctions resources/collectives;
- widget: local empty copy, refresh conservant contenu, source failure récupérable, N2/back;
- responsive: 800, 840, 900 et sparse wide;
- accessibility: textScale 1.0, 1.3, 1.6;
- integration locale: `MeScreen` + snapshot + `SyncStatusScope.offline`.

## Merge gate
- format vert;
- analyze vert;
- tests Mobile impactés verts;
- Android build vert;
- CI #451 verte;
- branche réconciliée avec le `main` courant;
- rerun des gates après réconciliation;
- T015 reste ouverte jusqu'à ces conditions.
