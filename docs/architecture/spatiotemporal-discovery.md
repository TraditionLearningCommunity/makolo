# Découverte spatio-temporelle canonique

## Formule

La Discovery publique de Makolo est construite directement sur le cœur canonique :

```text
Activity = quoi
Occurrence = quand
Place / Zone = où
Vertical presenter = comment on le présente
```

L'unité datée fondamentale est `Occurrence`. `Activity` fournit le titre, la description, la visibilité, le Space et le sens durable. Le lieu physique vient de `OccurrencePlace`, avec le rôle `primary` comme lieu principal. Une Occurrence peut rester sans Place lorsqu'elle est online ou lorsque son lieu n'est pas encore défini.

Discovery est une couche de query/presentation. Elle ne possède ni Activity, ni Occurrence, ni Place, ni prix, ni capacité, ni Journey. Aucun modèle de recherche persistant n'est introduit dans ce MVP.

## Visibilité et statut

La recherche publique ne retourne que les Activities `public` et publiées, avec des Occurrences planifiées et encore pertinentes. `unlisted` reste accessible par son URL métier mais n'apparaît pas dans Discovery ; `private` n'est jamais exposé. Les Occurrences annulées ou terminées ne sont pas des résultats normaux.

## Temps et timezones

Les filtres `today`, `tomorrow`, `weekend`, `week`, date précise et intervalle sont évalués dans une timezone de recherche explicite :

1. timezone d'un Place correspondant au contexte de lieu lorsque disponible ;
2. timezone locale Django/utilisateur disponible ;
3. `settings.TIME_ZONE` comme fallback explicite.

`Aujourd'hui` et `Demain` représentent des journées civiles locales, pas des dates UTC. `Ce week-end` couvre samedi 00:00 jusqu'à lundi 00:00 dans la timezone de recherche. Une Occurrence est pertinente lorsqu'elle chevauche la fenêtre recherchée ; une activité qui commence avant minuit et se termine pendant la période est donc correctement incluse.

## Géographie et nearby

La recherche par lieu utilise les `Place` déjà connus de Makolo. La recherche autour d'un point réutilise le socle Geography portable : bounding box pour réduire les candidats, puis distance Haversine pour le filtrage et le tri. Les rayons publics sont contrôlés à 5, 10, 25 ou 50 km. PostGIS n'est pas requis.

Un Place sans coordonnées peut apparaître dans une recherche texte/locality mais ne produit ni pin ni distance fictive. Pour Transport, le sens spatial principal d'un départ est son lieu d'origine/embarquement, matérialisé comme `OccurrencePlace primary` ; la destination reste un enrichissement du presenter Transport.

## Présentation par verticale

`DiscoveryItem` est un DTO de présentation stable. Il assemble Activity, Occurrence, Place, prix, disponibilité, URL et CTA sans exécuter de workflow métier.

Un registre léger choisit le presenter :

- Event enrichit le résultat avec son vocabulaire et sa page de détail Event ;
- Transport expose origine/destination, tarif, disponibilité et renvoie vers le détail du départ ;
- les autres Activities utilisent le presenter générique.

Le moteur commun ne requiert jamais `Event` pour afficher Transport.

Le prix public est dérivé des `Offer` actives correspondant à l'Occurrence. « Gratuit » signifie qu'au moins une Offer active et réellement utilisable a un prix nul. La disponibilité est dérivée uniquement de `CapacityPool` et de ses réservations actives/engagées ; aucun compteur Event, TicketType ou Vehicle parallèle n'est utilisé.

## Carte

MapLibre GL JS est uniquement le renderer cartographique. Il ne fournit ni tuiles ni geocoding.

La configuration applicative expose :

```text
MAP_TILE_URL
MAP_TILE_ATTRIBUTION
MAP_TILE_MAX_ZOOM
```

La bêta peut utiliser une source de tuiles OpenStreetMap compatible avec sa politique d'usage et avec attribution obligatoire. Aucun token Mapbox ou Google n'est requis. L'origine réseau des tuiles est ajoutée explicitement à la CSP au lieu d'ouvrir `connect-src` ou `img-src` globalement.

La liste est le contrat principal et reste utilisable sans JavaScript, sans tuiles et sans permission de géolocalisation. MapLibre enrichit progressivement l'écran avec pins, clustering, sélection liste/carte et fit-bounds contrôlé. « Autour de moi » demande ponctuellement la position navigateur et ne la persiste pas dans Profile.

## Limites et performance

Les requêtes publiques limitent la longueur des champs, la plage de dates, le rayon et le nombre de candidats. La liste est paginée/limitée et la carte ne charge qu'un ensemble contrôlé de résultats. Le MVP reste compatible SQLite et PostgreSQL standard ; aucun moteur FTS externe, Elasticsearch, OpenSearch, Meilisearch ou PostGIS n'est requis.

## Cutover legacy

L'ancien Explorer dont la racine était `Event.objects`, `Event.start_at`, `EventVenue` et `TicketType` n'est plus le contrat de Discovery. Les tests ne protégeant que cette architecture Event-only sont supprimés ou remplacés par des tests canoniques `Activity + Occurrence + Geography`.

Les invariants restent obligatoires : visibilité, données privées, timezone, capacité, prix serveur et isolation. La recherche Transport spécialisée origine → destination → date reste une surface métier distincte et n'est pas remplacée par Discovery.

## Hors scope

Cette tâche n'introduit pas PostGIS obligatoire, routing, trafic, géocoding externe obligatoire, Nominatim runtime, recommandations ML, ranking sponsorisé, favoris, Product Language global, polygones GIS complexes ni inventaire Transport par segment.
