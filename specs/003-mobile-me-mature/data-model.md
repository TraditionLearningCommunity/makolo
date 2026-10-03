# Data Model: Mobile Mature — Moi / Me

Aucun nouveau modèle persistant.

## Entrée existante
`StoredProjection`
- kind = `personal.me`
- schemaVersion
- payload
- received/source timestamps
- freshUntil/expiresAt/freshnessPolicyId

## Modèles Presentation
`MePresentation` et `MeTerritoryPresentation` sont les contrats partagés existants.

## Adaptation lane-local
`MeSelection`
- MePresentation
- territoires enrichis pour rendu
- état global
- état Identity
- sous-titre/détail Identity

`MeItemPresentation`
- StructuredDestination canonique/projection-safe
- titre
- sous-titre
- métadonnées de présentation

Ces objets ne sont pas persistés et ne deviennent propriétaires d'aucune vérité métier.
