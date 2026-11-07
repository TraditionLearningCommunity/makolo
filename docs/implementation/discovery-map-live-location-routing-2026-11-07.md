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

- L'écran ne demande pas le GPS spontanément. L'utilisateur déclenche `Me localiser`.
- `LocationCapability.current()` fournit le premier fix, puis `foregroundWatch(profile: active)` entretient le point bleu tant que la carte est active et que la session est valable.
- Le contrôleur met à jour **uniquement** le point utilisateur ; un fix ne re-génère pas les clusters Discovery.
- Le bouton recentre la caméra en respectant le niveau de zoom courant. Ensuite la position suit les déplacements, **sans forcer la caméra** lorsque l'utilisateur explore la carte.
- Le suivi est stoppé hors premier plan et à la destruction de la vue ; reprise seulement après un choix de localisation préalable. Les démarrages concurrents et les streams en échec sont bornés.
- Message bref, flottant, non bloquant, selon le statut : refus, refus définitif avec action Paramètres, restrictions appareil, service GPS coupé, erreur temporaire. Les dialogues du système Android restent ceux du système, sans tutoriel redondant.

## 3. Recherche

- Le contrat `GeoSearchGateway` est déjà en place, sélectionné par `geo_search_gateway_factory.dart` et injecté depuis `runtime_builder.dart`.
- `DiscoverySearchScreen` transmet ce contrat à `DiscoveryFilterFields`. Le bouton Recherche de Carte ouvre cet écran avec la requête actuelle.
- MapTiler reste l'adaptateur actif. Aucune seconde recherche, clé ou configuration MapTiler n'a été ajoutée.

## 4. Routage

- `RoutingGateway` possède un contrat indépendant du fournisseur : origine, destination, marche/vélo/voiture, géométrie, distance et durée.
- `OpenRouteServiceGateway` compose les requêtes directions GeoJSON du service gratuit standard HeiGIT, avec endpoint HTTPS injectable et clé **non versionnée**.
- Endpoint par défaut de l'adaptateur : `https://api.heigit.org/openrouteservice/v2/directions` ; l'ancienne adresse `api.openrouteservice.org` est obsolète.
- `RoutingGatewayFactory` et `MakoloRuntimeConfig.routing` gardent l'accès désactivé par défaut, y compris en DEV. Activation seulement en DEV via `MAKOLO_ROUTING_ENABLED=true`, `MAKOLO_ROUTING_API_KEY`, et paramètres optionnels `MAKOLO_ROUTING_PROVIDER`, `MAKOLO_ROUTING_ENDPOINT`.
- Une clé de routage injectée dans un binaire Flutter est **exposable**. N'activer qu'une clé client explicitement approuvée et à permissions/quota réduits ; sinon mettre un proxy serveur sous autorité dans un chantier distinct. Aucune clé n'est fournie dans le dépôt et Beta/PROD restent non activables sans revue.
- Aucune API de routage n'est appelée au démarrage ni depuis Discovery ; aucune action d'itinéraire inachevée ne s'affiche.

## 5. Contrôles ciblés à exécuter

```text
dart format lib/platform/maps/discovery_map_controller.dart lib/features/discovery/discovery_mature_view.dart lib/platform/routing/ lib/app/environment.dart lib/app/runtime/app_runtime.dart lib/app/runtime/runtime_builder.dart test/discovery_map_clusters_test.dart test/discovery_mature_screen_test.dart test/routing_gateway_test.dart
flutter analyze
flutter test test/discovery_map_clusters_test.dart test/discovery_mature_screen_test.dart test/location_capability_test.dart test/geo_search_gateway_test.dart test/routing_gateway_test.dart
```

Sur Android DEV réel : clusters à faible zoom et expansion ; marqueur sélectionné ; plusieurs opportunités exactes ; recherche MapTiler ; permission accordée/refusée/bloquée ; service GPS désactivé puis réactivé ; déplacement du point bleu ; bouton de recentrage ; app en arrière-plan puis retour ; carte indisponible/rechargement de style ; retour N2 avec contexte intact. Tester la lisibilité des glyphes sur le style MapTiler actif.

**État de validation :** changements écrits sur GitHub ; ni `dart format`, ni `flutter analyze`, ni `flutter test`, ni essai Android réel n'ont été exécutés depuis ce connecteur. Ne pas présenter ces validations comme réussies. Aucun merge effectué.
