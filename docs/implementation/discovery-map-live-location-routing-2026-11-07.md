# Discovery mobile — cartographie, localisation en direct et routage optionnel

**Date :** 7 novembre 2026  
**Dépôt / PR :** `TraditionLearningCommunity/makolo` / #522  
**Branche :** `fix/discover-a-continuation-context-20261014`  
**Périmètre :** Flutter et configuration runtime uniquement ; aucun changement backend, migration, Beta/Production ou de fournisseur de tuiles.

## Base préservée

- MapLibre reste le moteur et MapTiler reste le style et le géocodage actifs en DEV.
- Le clustering natif conserve `clusterRadius: 56`, `clusterMaxZoom: 13`, les tailles par compteur, l'expansion native au toucher et les transitions.
- La carte, le même champ Discovery, les coordonnées admises, le panneau des opportunités colocalisées, la sélection N1/N2, Save/Sharing et les droits owner restent les autorités existantes.
- Aucune recherche ou projection métier parallèle ; aucun nouveau package Flutter.

## 1. Marqueurs et interactions

- Chaque point non clusterisé possède un attribut de présentation `selected`, distinct de tout droit métier et sans identité privée.
- Le rendu cercle natif distingue le point sélectionné par le rayon, le violet profond et un contour corail ; la couche de cluster reste identique.
- Un glyphe très court est prévu pour un type de représentation publique connu et un emplacement ne représentant qu'une seule opportunité ; les lieux à plusieurs opportunités conservent leur compteur.
- L'ajout d'une couche de glyphe est **optionnel** : une police ou un glyphe indisponible ne doit pas faire échouer le clustering.
- Lorsqu'un style MapLibre est rechargé, la source/couche native est réinstallée avant d'utiliser le repli d'annotations.

## 2. Localisation

- La carte lit le statut de permission existant sans afficher de dialogue au démarrage. Si la permission est déjà accordée, le flux GPS en premier plan démarre automatiquement ; sinon seule l'action explicite `Me localiser` peut demander l'autorisation.
- `foregroundWatch(profile: active)` entretient le point bleu avec `geolocator` déjà présent. Le bouton `Me localiser` réutilise immédiatement la dernière position valide, et n'appelle `current()` avec un délai borné que sans position connue.
- Le contrôleur met à jour **uniquement** le point utilisateur ; un fix ne re-génère pas les clusters Discovery.
- Le bouton recentre la caméra en respectant le niveau de zoom courant. Ensuite la position suit les déplacements, **sans forcer la caméra** lorsque l'utilisateur explore la carte.
- Le suivi est stoppé hors premier plan et à la destruction de la vue ; reprise si l'autorisation existe toujours ou après un choix explicite. Les démarrages concurrents et les flux en échec sont bornés.
- Message bref, flottant, non bloquant, selon le statut : refus, refus définitif avec action Paramètres, restrictions appareil, service GPS coupé, erreur temporaire. Les dialogues du système Android restent ceux du système, sans tutoriel redondant.

## 3. Recherche

- Le contrat `GeoSearchGateway` est déjà en place, sélectionné par `geo_search_gateway_factory.dart` et injecté depuis `runtime_builder.dart`.
- `DiscoverySearchScreen` transmet ce contrat à `DiscoveryFilterFields`. Carte propose désormais deux actions distinctes : chercher un lieu via le **même `GeoAutocompleteField`**, ou ouvrir les critères complets Discovery. Une suggestion de lieu recompose la **même** recherche spatiale Discovery à 25 km autour de ses coordonnées, sans créer de `Place` métier.
- MapTiler reste l'adaptateur actif. Aucune seconde recherche, clé ou configuration MapTiler n'a été ajoutée.

## 4. Routage

- `RoutingGateway` possède un contrat indépendant du fournisseur : origine, destination, marche/vélo/voiture, géométrie, distance et durée.
- `OpenRouteServiceGateway` compose les requêtes directions GeoJSON du service gratuit standard HeiGIT, avec endpoint HTTPS injectable et clé **non versionnée**.
- Endpoint par défaut de l'adaptateur : `https://api.heigit.org/openrouteservice/v2/directions` ; l'ancienne adresse `api.openrouteservice.org` est obsolète.
- `RoutingGatewayFactory` et `MakoloRuntimeConfig.routing` gardent l'accès désactivé par défaut, y compris en DEV. Activation seulement en DEV via `MAKOLO_ROUTING_ENABLED=true`, `MAKOLO_ROUTING_API_KEY`, et paramètres optionnels `MAKOLO_ROUTING_PROVIDER`, `MAKOLO_ROUTING_ENDPOINT`.
- Une clé de routage injectée dans un binaire Flutter est **exposable**. N'activer qu'une clé client explicitement approuvée et à permissions/quota réduits ; sinon mettre un proxy serveur sous autorité dans un chantier distinct. Aucune clé n'est fournie dans le dépôt et Beta/PROD restent non activables sans revue.
- Aucune API de routage n'est appelée au démarrage. `RoutingGateway` reste optionnel et désactivé sans configuration autorisée. Le parcours utilisateur d'itinéraire est utilisable **sans ce fournisseur** grâce aux liens HTTPS universels Google Maps et Waze, ouverts par `url_launcher` déjà présent. L'application de navigation choisie gère le trajet, le GPS et l'ETA ; Makolo n'en fabrique aucun. Le bouton `Itinéraire` apparaît depuis la fiche Carte et le détail N2 uniquement si la projection publique comporte des coordonnées valides. Pour plusieurs lieux d'un trajet, la personne choisit explicitement le lieu à rejoindre.

## 5. Contrôles ciblés à exécuter

```text
dart format lib/platform/maps/discovery_map_controller.dart lib/features/discovery/discovery_mature_view.dart lib/platform/routing/ lib/app/environment.dart lib/app/runtime/app_runtime.dart lib/app/runtime/runtime_builder.dart test/discovery_map_clusters_test.dart test/discovery_mature_screen_test.dart test/routing_gateway_test.dart
flutter analyze
flutter test test/discovery_map_clusters_test.dart test/discovery_mature_screen_test.dart test/location_capability_test.dart test/geo_search_gateway_test.dart test/routing_gateway_test.dart
```

Sur Android DEV réel : clusters à faible zoom et expansion ; marqueur sélectionné ; plusieurs opportunités exactes ; recherche MapTiler ; permission accordée/refusée/bloquée ; service GPS désactivé puis réactivé ; déplacement du point bleu ; bouton de recentrage ; app en arrière-plan puis retour ; carte indisponible/rechargement de style ; retour N2 avec contexte intact. Tester la lisibilité des glyphes sur le style MapTiler actif.

**État de validation :** changements écrits sur GitHub ; ni `dart format`, ni `flutter analyze`, ni `flutter test`, ni essai Android réel n'ont été exécutés depuis ce connecteur. Ne pas présenter ces validations comme réussies. Aucun merge effectué.


## Correctif #522 — index spatial complet et marqueurs lisibles (8 novembre 2026)

### Cause racine constatée avec `db.sqlite3`

Les cinq services de démonstration sont publiés, chacun admis par
`public_service_discovery_item` et lié à un `OccurrencePlace` public.
Cependant `spatial_index_from_rows` écartait toute famille autre que
`activity`. Cette exclusion empêchait leur affichage sur la carte,
malgré une admission correcte par le propriétaire Service.

### Solution

- L'index compact traite désormais `service_activity` uniquement si une
  occurrence future et publique de l'activité est admise par le sélecteur
  canonique `public_occurrences_for_activities`. La géographie provient
  de la relation canonique `OccurrencePlace`, filtrée par la même règle
  de publication `SpacePlace` que pour Activity. Les lieux privés,
  occurrences expirées et services sans lieu public ne créent aucun pin.
- Une `Activity` de Service peut apparaître aussi dans la famille générique
  `activity` lorsque l'occurrence est admise. Sa représentation spatiale
  est dédupliquée au niveau de l'identité Activity si la représentation
  `service_activity` est géolocalisable, sans supprimer de candidats N1.
- **Discovery N1 conserve ses pages et continuations signées.** La carte
  personnelle réutilise l'index spatial compact du premier chargement de
  cette même projection, construit sur tous les candidats du champ
  admis, sans faire défiler les pages N1. La carte visiteur utilise
  maintenant ce même index en une acquisition, avec des lignes de lieux
  rendues paresseusement par `ListView.builder`. La limite de sécurité
  et de coût du sélecteur par famille reste en vigueur : ceci ne crée
  pas un chargement infini ni un API de recherche parallèle.
- MapLibre conserve la source GeoJSON `cluster=true`, `clusterRadius=56`,
  `clusterMaxZoom=13`, les compteurs et l'expansion native. Un lieu
  avec **une** possibilité utilise une épingle native, un lieu exact avec
  **plusieurs** possibilités utilise un badge arrondi numéroté, et un
  véritable cluster conserve son cercle numéroté. Les états sélectionnés
  se différencient par la bordure corail, sans recalcul de clustering.
  Ces images vectorielles sont produites depuis le Canvas Flutter et
  enregistrées par `MapLibreMapController.addImage`, sans nouveau package
  ni asset externe. Si les images ne peuvent pas être enregistrées,
  la couche de cercles existante reste le repli.
- Aucun changement de modèle, migration, seed, de `db.sqlite3`, de
  configuration MapTiler ou du backend PythonAnywhere directement.

### Validation à réaliser (non exécutée ici)

```text
python manage.py test discovery.api.test_mature_discovery
cd mobile
dart format --output=none --set-exit-if-changed lib/platform/maps/discovery_map_controller.dart lib/features/guest/public_discovery_map_screen.dart test/discovery_compact_spatial_test.dart test/discovery_map_pin_counts_test.dart
flutter analyze
flutter test test/discovery_compact_spatial_test.dart test/discovery_map_clusters_test.dart test/discovery_map_pin_counts_test.dart
```

Après `git pull --ff-only`, recharger l'application Web PythonAnywhere
pour prendre en compte le backend. **La nouvelle apparence des marqueurs
nécessite également un nouveau build Flutter installé sur le téléphone.**
Le code poussé n'établit pas, à lui seul, qu'une APK déjà installée l'utilise.


### Harmonisation Carte publique

La surface `PublicDiscoveryMapScreen` demande elle aussi la première page
`include_spatial_index=compact` et lit les positions complètes de cet index
sans poursuivre la pagination de N1. `PublicDiscoveryPointsMap` réutilise
désormais `DiscoveryMapController` et son regroupement MapLibre natif,
au lieu d'ajouter une annotation `Circle` par résultat. La liste publique
reste disponible via des éléments construits paresseusement ; les points
visuellement multiples réutilisent `DiscoveryCoLocatedPicker` et les
marqueurs uniques ouvrent leur détail canonique. Aucun nouveau rendu
cartographique indépendant n'est entretenu.

## Fin de périmètre fonctionnel : Carte / GPS / recherche / itinéraires

**Décision :** ne pas ajouter de moteur de navigation, de suivi GPS propre,
de nouvelle API de géocodage ni de système de clustering parallèle.

L'expérience en DEV intègre désormais :

- MapLibre natif : caméra, marqueurs, clusters, expansion, sélection ;
- MapTiler via `GeoSearchGateway` : recherche d'un lieu sur Carte avec le
  même `GeoAutocompleteField` que Recherche, puis rafraîchissement spatial
  canonique dans un rayon de 25 km (la pagination de la liste N1 ne change pas) ;
- `geolocator` / `LocationCapability` : point bleu en premier plan, suivi
  automatique si permission existante, bouton de recentrage ;
- Lien universel d'itinéraire Google Maps par `url_launcher` : pas
  de nouvelle clé, pas de nouvel appel routier serveur, choix d'un lieu
  explicite pour les activités ayant plusieurs points géographiques ;
- API Discovery : services et événements publics à partir des lieux
  `OccurrencePlace` canoniques, sous les contrôles de visibilité existants.

**Tests ajoutés (à exécuter) :**

```text
cd mobile
flutter test test/external_directions_test.dart test/discovery_directions_sheet_test.dart test/discovery_map_place_search_test.dart test/discovery_mature_screen_test.dart test/geo_search_gateway_test.dart test/discovery_map_clusters_test.dart test/discovery_compact_spatial_test.dart
flutter analyze
```

**Une campagne Android DEV** suffit à vérifier : ouvrir Carte avec permission
déjà accordée puis marcher pour observer le point bleu ; recentrer ; rechercher
« Maseru » dans Carte et vérifier les opportunités et l'emprise ;
sélectionner un marqueur unique ; ouvrir la liste d'un lieu colocalisé ;
utiliser `Itinéraire` vers Google Maps sans étape de sélection ; ouvrir une activité à
plusieurs lieux et choisir explicitement destination ou départ ; revenir
à Makolo et vérifier la conservation du contexte Carte. Vérifier ensuite le
refus de permission, le GPS système désactivé et l'absence de crash.

**Limites connues :** le routage OpenRouteService demeure disponible comme
adaptateur optionnel désactivé, non nécessaire au parcours de navigation.
Les tests Flutter/Android n'ont pas encore été exécutés ici ; ne pas marquer
ce comportement validé tant qu'une APK issue de la branche n'a pas été essayée.
Aucune modification de la base SQLite n'est nécessaire.

### Décision navigation Android — Google Maps uniquement (8 novembre 2026)

L'action `Itinéraire` ouvre directement le lien universel HTTPS officiel
Google Maps avec la seule destination publique. Le résolveur Android
(`LaunchMode.externalApplication`) peut lancer l'application Maps installée ;
si elle n'est pas disponible, le lien peut être ouvert par un navigateur.
**Aucun sélecteur Waze/Google Maps**, aucune dépendance, aucun itinéraire
fabriqué par Makolo. Le choix explicite du **lieu** reste uniquement pour
les activités ayant plusieurs lieux (départ/arrivée/escale). L'adaptateur
OpenRouteService demeure désactivé et indépendant de cette action.
