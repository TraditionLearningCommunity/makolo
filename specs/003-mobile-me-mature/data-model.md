# Data Model: Mobile Mature — Moi / Me

Aucun nouveau modèle persistant.

## Entrées existantes

### StoredProjection
- kind = `personal.me`
- schemaVersion
- payload
- received/source timestamps
- freshUntil/expiresAt/freshnessPolicyId

### OwnerSourceState
Projection technique non persistée directement par Moi, construite depuis la table partagée `SyncSources`:
- lastSuccessAt
- invalidated
- lastErrorCode
- reachability dérivée par le helper partagé

### SyncStatus
État transversal de lifecycle fourni par `SyncStatusScope`:
- synced
- syncing
- pending
- offline
- conflict
- failed
- stale

## Modèles Presentation existants
`MePresentation` et `MeTerritoryPresentation` restent les contrats partagés.

## Adaptation lane-local

### MeSelection
- MePresentation
- territoires enrichis pour rendu
- état de surface
- état Identity
- sous-titre/détail Identity
- nombre de territoires possédant du contenu pour l'adaptation géométrique

### MeItemPresentation
- StructuredDestination
- titre
- sous-titre
- métadonnées de présentation

Ces objets ne sont pas persistés et ne deviennent propriétaires d'aucune vérité métier.

## Absences explicites
Aucun:
- MeState;
- table de territoire;
- cache métier parallèle;
- Permission/Mandate locale;
- score de profil;
- modèle Passport mobile;
- copie locale autonome de Resource/Proof/Credential.
