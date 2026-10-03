# Implementation Plan: Mobile Mature — Moi / Me

**Branch**: `feat/mobile-me-mature` | **Date**: 2026-10-03 | **Spec**: `specs/003-mobile-me-mature/spec.md`

## Summary
Remplacer le wrapper générique `ProjectionScreen` de Moi par un selector lane-local et une composition Flutter section-first alimentés uniquement par `personal.me`. Réutiliser MePresentation, MakoloSurfacePresentation, ContentFrame, AdaptiveGrid/Split, FocusPane, Section, Card, Metadata et états communs.

## Technical Context
**Language/Version**: Dart / Flutter courant du dépôt  
**Primary Dependencies**: Flutter, go_router, Presentation foundation existante  
**Storage**: ProfileStore / StoredProjection existants, aucune nouvelle table  
**Testing**: flutter_test, harness Presentation existant  
**Target Platform**: Android/mobile Flutter, géométrie Compact/Wide adaptative  
**Project Type**: mobile app  
**Constraints**: local-first, Profile-scoped, aucune autorité locale, aucune migration, aucune modification de seam protégé

## Constitution Check
- Runtime courant lu avant changement: PASS.
- Aucun nouveau modèle/persisted state: PASS.
- Profile reste personne globale: PASS.
- Membership ≠ authority: PASS.
- Resource/Proof/Credential/Requirement restent distincts: PASS.
- Localement disponible ≠ autoritatif: PASS.
- Aucun faux succès: PASS.
- Branche dédiée + PR + CI gate: PASS.

## Brownfield / collision audit
- Base SHA: `297a4c635dafc49d78a95fd463a30a13ffa5ef54`.
- PR ouverte Now: `#446 feat/mobile-now-mature`, scope Now seulement.
- Branche Ongoing: `feat/mobile-ongoing-mature`, scope Ongoing seulement.
- PR #448 Passport est Web/backend public identity, pas `mobile/lib/features/me/**`.
- Aucune branche/PR existante `feat/mobile-me-mature` avant création.
- Fichiers lane: `mobile/lib/features/me/**`, `mobile/test/me_mature_test.dart`, artifacts Spec Kit.
- Fichiers interdits: design partagé, presentation/contracts, dev/scenarios, dev/gallery, router, shell, actor context, sync, ProfileStore/Drift.

## Runtime shape
`personal.me` expose actuellement:
- identity;
- passport;
- considerations;
- collectives;
- resources;
- support;
- links.

Le selector mappe ces sections vers MePresentation sans reconstruire les owners.

## Responsive / G08-G09
- Compact: structure verticale.
- Wide: 1–2 territoires à partir de `MakoloLayout.meTwoColumnMinWidth == 840`.
- N2: Focus pane/split lorsque géométriquement viable; sinon profondeur plein champ.
- Jamais de dashboard 4 colonnes.

## COMMON GAP
- **Manque constaté**: `PersonalRepository.watchMe()` expose la projection mais pas l'état source reachability / refresh-error.
- **Pourquoi le socle actuel ne suffit pas**: la lane ne peut pas déduire honnêtement offline depuis l'âge du snapshot.
- **Lanes concernées**: Now, Ongoing, Me potentiellement.
- **Proposition minimale**: raccord intégrateur transversal des source-state cues vers selectors, sans nouveau sync engine ni stockage.
- La lane prépare/teste les axes Presentation injectables mais ne fabrique aucun état production.

## Tests ciblés
Selector: vraie shape, full, sparse, section empty, section malformed, resource/collective distinctions, freshness.  
Widget: Compact, Wide 2 territoires max, N2/back, offline-known injectable, textScale critique.

## Merge gate
- CI PR verte.
- Aucun fichier interdit dans le diff.
- Réconciliation avec main courant avant intégration.
- PR laissée ouverte pour le lot parallèle; aucun merge automatique.
