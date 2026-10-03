# Research: Mobile Mature — Moi / Me

## Décisions retenues

### Source runtime
`PersonalRepository.watchMe()` lit `StoredProjection personal.me`. Le selector lane-local consomme directement la shape backend courante; aucun GET direct depuis l'écran.

### Composition
Moi est section-first. Les territoires racine retenus sont ceux réellement exposés aujourd'hui: Passport, Considerations, Collectives, Resources; Support n'apparaît que si le serveur indique un capital disponible.

### Identité
Identity est un territoire visuel calme mais ne devient ni Account ni Settings. Aucun score d'activation/completion n'est affiché.

### Profondeur
La lane utilise une profondeur N2 Presentation locale sur les previews déjà acquises. Elle n'invente aucune nouvelle route owner et ne modifie pas le router.

### Freshness/offline
Freshness utilise les métadonnées de StoredProjection via `FreshnessPolicy(id: 'personal.me')` sans TTL inventé. Reachability et refresh-error restent des cues injectables; leur raccord production est un COMMON GAP intégrateur.

### Géométrie
Compact reste vertical. Wide utilise le seuil partagé `MakoloLayout.meTwoColumnMinWidth` (840) et `MakoloAdaptiveGrid(maxColumns: 2)`.

## Alternatives rejetées
- Réutiliser ProjectionScreen: trop générique, ne protège pas la personnalité de Moi.
- Créer une table locale par territoire: duplique les vérités propriétaires.
- Ajouter un router Resource/Passport depuis cette lane: seam protégé et capability non démontrée.
- Utiliser les scénarios dev comme source runtime: fake data runtime.
