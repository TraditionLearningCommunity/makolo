# Géographie Makolo

## Contrat métier

`Place` représente un **Lieu physique précis et réutilisable**. `Zone` représente un **périmètre**. Une origine, une destination ou une étape de transport sera plus tard une relation métier vers un `Place`, jamais un type global de `Place`.

La bêta stocke des coordonnées WGS84 (`latitude`, `longitude`) uniquement dans le bounded context `geography`. Elles sont facultatives mais toujours présentes par paire. Les recherches de proximité appliquent d’abord une bounding box en SQL, puis Haversine sur un nombre borné de candidats.

`SpacePlace` exprime la relation Espace ↔ Lieu. `created_by` sur `Place` est de l’audit et ne crée pas d’ownership exclusif. Deux Lieux peuvent partager la même adresse ou des coordonnées proches sans être fusionnés automatiquement.

`events.EventVenue` conserve sa sémantique présentiel/en ligne/hybride et ses anciens champs pendant la transition. Son FK `place` devient la référence géographique partagée ; la suppression d’un `Place` ne supprime pas l’historique EventVenue.

## Cible spatiale

La cible d’évolution est **GeoDjango + PostgreSQL/PostGIS** pour `PointField`, index spatiaux, distances en base, polygones, intersections et zones complexes. PostGIS n’est pas requis pour le runtime bêta actuel.

Migration future :

1. activer PostGIS sur l’infrastructure ;
2. ajouter un `PointField` à `Place` ;
3. backfiller depuis latitude/longitude ;
4. vérifier les valeurs ;
5. basculer les selectors spatiaux vers GeoDjango ;
6. conserver temporairement les colonnes latitude/longitude ;
7. les retirer après cutover validé.

Cette évolution change le moteur spatial, pas la sémantique métier de `Place` ou `Zone`.

Aucune API cartographique, aucun géocodage réseau et aucun stockage de position courante d’un Profil ne font partie de cette fondation.
