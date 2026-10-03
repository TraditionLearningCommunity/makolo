# Analyze: Mobile Mature Discover

## Consistency

PASS entre spec, plan et contrat commun.

## Runtime findings

1. Le repository/source-state existe déjà: aucune duplication permise.
2. Le selector préserve déjà l’ordre serveur: à conserver.
3. La collection API contient les coordonnées owner pour les Activities cartographiables.
4. La carte séparée actuelle consomme `discovery.map`; G05 doit au contraire spatialiser le même `discovery.items`.
5. Les écrans actuels ne distinguent pas NO_MATCH / NO_CURRENT_PROPOSAL / OFFLINE_NO_SNAPSHOT.
6. `ConfiguredMakoloMapView` ne fournit pas markers/camera change callbacks: COMMON GAP transversal, pas à contourner localement.

## Risk review

- **Authority**: aucun changement; save reste serveur.
- **Privacy**: seules coordonnées déjà présentes dans la projection admissible sont utilisées.
- **Offline**: snapshot reste affiché; refresh error recoverable.
- **Ranking**: interdit et non nécessaire.
- **Migration**: aucune.
- **Collision**: #446 Now est disjoint; #449 Web/public est hors mobile et ne doit pas être touchée.

## Implementation decision

Faire évoluer Presentation et selector lane-local; conserver repository/sync owner et routes existantes.
