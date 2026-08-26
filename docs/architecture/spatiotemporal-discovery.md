# Découverte spatio-temporelle canonique

## Formule

La Discovery publique de Makolo est construite directement sur le cœur canonique :

```text
Activity = quoi
Occurrence = quand
Place / Zone = où
Vertical presenter = comment on le présente
```

L'unité datée fondamentale est `Occurrence`. `Activity` fournit le titre, la description, la visibilité et l'opérateur logique (`owner_profile` ou `space`). Le lieu physique vient de `OccurrencePlace`, avec le rôle `primary` comme lieu principal. Une Occurrence peut rester sans Place lorsqu'elle est online ou lorsque son lieu n'est pas encore défini.

Discovery est une couche de query/presentation. Elle ne possède ni Activity, ni Occurrence, ni Place, ni prix, ni capacité, ni Journey. Aucun modèle de recherche persistant n'est introduit.

## Recherche globale et recherche personnelle

La recherche globale porte uniquement sur ce qui est publiquement découvrable dans `Activity + Occurrence + Geography`. Elle n'indexe jamais Journey, Access, Payment, CommerceOrder, CRM ou `ExternalBeneficiary`.

Les recherches personnelles partent au contraire des selectors déjà autorisés (`participant_journeys`, `participant_accesses`, achats visibles au buyer, Activities possédées), puis appliquent texte, filtres et pagination. Un filtre de recherche ne constitue jamais une permission.

Le bénéficiaire externe introduit par T25 reste privé : son nom peut être recherché dans les billets explicitement achetés par le buyer concerné, mais ni son nom, ni son email, ni son téléphone ne deviennent des champs Search publics.

## Favoris

Un Favori signifie « enregistrer cette Activity pour la retrouver ». Le stockage canonique est `ActivityBookmark(user, activity)`, transversal aux verticales. Sauvegarder ne crée ni Journey, ni Access, ni CommerceOrder, ni Payment, ni CapacityReservation.

Les anciens `EventBookmark` sont backfillés vers `event.activity`. L'ancienne URL/API Event peut rester une compatibilité, mais toutes les nouvelles écritures utilisent la même table Activity-first. Un Favorite peut rester visible même lorsqu'aucune Occurrence publique à venir n'est disponible ; il représente l'intention de sauvegarde, pas un état de participation.

## Visibilité et statut

La recherche publique ne retourne que les Activities `public` et publiées, avec des Occurrences planifiées et encore pertinentes. `unlisted` reste accessible par son URL métier si son contrat le permet mais n'apparaît pas dans Discovery ; `private` n'est jamais exposé. Les Occurrences annulées ou terminées ne sont pas des résultats normaux.

## Temps et timezones

Les filtres `today`, `tomorrow`, `weekend`, `week`, date précise et intervalle sont évalués dans une timezone de recherche explicite :

1. timezone d'un Place correspondant au contexte de lieu lorsque disponible ;
2. timezone locale Django/utilisateur disponible ;
3. `settings.TIME_ZONE` comme fallback explicite.

`Aujourd'hui` et `Demain` représentent des journées civiles locales, pas des dates UTC. `Ce week-end` couvre samedi 00:00 jusqu'à lundi 00:00 dans la timezone de recherche. Une Occurrence est pertinente lorsqu'elle chevauche la fenêtre recherchée.

## Géographie et nearby

La recherche par lieu utilise les `Place` déjà connus de Makolo. La recherche autour d'un point réutilise le socle Geography portable : bounding box pour réduire les candidats, puis distance Haversine pour le filtrage et le tri. Les rayons publics sont contrôlés à 5, 10, 25 ou 50 km. PostGIS n'est pas requis.

`ordering=proximity` est distance-first, puis horaire. Un Place sans coordonnées peut apparaître dans une recherche texte/locality mais ne produit ni pin ni distance fictive. Pour Transport, le sens spatial principal d'un départ est son lieu d'origine/embarquement, matérialisé comme `OccurrencePlace primary`.

## Présentation par verticale

`DiscoveryItem` est un DTO de présentation stable. Il assemble Activity, Occurrence, Place, prix, disponibilité, participant state, URL et CTA sans exécuter de workflow métier.

Un registre léger choisit le presenter :

- Event enrichit le résultat avec son vocabulaire et sa page de détail Event ;
- Transport expose origine/destination, tarif, disponibilité et renvoie vers le détail du départ ;
- les autres Activities utilisent le presenter générique.

Le moteur commun ne requiert jamais `Event` pour afficher Transport. Les CTA réutilisent les projections T23/T25 : buyer et beneficiary restent distincts et un billet acheté pour un tiers ne devient pas un Access personnel du buyer.

Le prix public est dérivé des `Offer` actives correspondant à l'Occurrence. Les choix `OfferPaymentOption` restent du ressort Commerce : Discovery ne crée ni mode `mixed`, ni faux Payment. Une réservation `on_site` ne doit jamais être présentée comme payée.

## Carte

MapLibre GL JS est uniquement le renderer cartographique. Il ne fournit ni tuiles ni geocoding.

La liste est le contrat principal. Sans coordonnées `lat + lon` validées, `nearby_active=false` et la grande carte web n'est ni rendue ni chargée. Après l'action explicite « Autour de moi », la géolocalisation ponctuelle alimente la requête, les distances et la carte contextuelle.

Sur mobile, la liste reste le mode initial même en proximité active ; le participant choisit ensuite Carte ou Liste. Un refus GPS ou un échec MapLibre laisse la recherche textuelle entièrement utilisable.

La position précise n'est pas persistée automatiquement dans Profile, UserDevice, CRM, analytics ou localStorage. L'API cartographique publique Event/Activity historique conserve son contrat borné pour compatibilité, mais son existence ne déclenche pas l'affichage de la carte web.

La configuration applicative expose :

```text
MAP_TILE_URL
MAP_TILE_ATTRIBUTION
MAP_TILE_MAX_ZOOM
```

L'origine réseau des tuiles reste explicitement contrôlée par la CSP.

## Recommandations et legacy Event

La recherche universelle est `search_occurrences()`. Les endpoints historiques `search_discovery_events`, `serialize_event` et la recommandation Event peuvent rester comme contrats de compatibilité, mais ne sont pas la vérité Search canonique.

La surface « Pour vous » doit annoncer honnêtement toute limitation Event tant qu'un contrat de recommandations multi-vertical n'existe pas. La popularité n'est qu'un signal secondaire issu d'actions réelles (réservations/sauvegardes), jamais un système de likes ou de prestige social.

La route historique « Mes événements » n'est plus un hub participant canonique : T23/T24/T25 répartissent désormais les responsabilités entre Mes démarches, Mes accès, billets achetés, activités organisées et Favoris.

## Limites et performance

Les requêtes publiques limitent la longueur des champs, la plage de dates, le rayon et le nombre de candidats. Les listes personnelles sont filtrées côté serveur et paginées. Le MVP reste compatible SQLite et PostgreSQL standard ; aucun moteur FTS externe, Elasticsearch, OpenSearch, Meilisearch ou PostGIS n'est requis.

Les artefacts frontend versionnés de `static/dist` font partie du contrat reproductible de la verticale : après `npm run build`, la CI exige que `package-lock.json` et `static/dist` restent sans diff.

## Cutover legacy

L'ancien Explorer dont la racine était `Event.objects`, `Event.start_at`, `EventVenue` et `TicketType` n'est plus le contrat de Discovery. La recherche Transport spécialisée origine → destination → date reste une surface métier distincte et n'est pas remplacée par Discovery.

La découvrabilité complète des Groupes reste volontairement reportée à T27, qui doit d'abord définir leur contrat public/non répertorié/caché et leurs règles d'adhésion.

## Hors scope

Cette tâche n'introduit pas PostGIS obligatoire, routing, trafic, geocoding externe obligatoire, Nominatim runtime, recommandations ML/LLM, ranking sponsorisé, feed social, likes/réactions, persistance GPS, polygones GIS complexes ni inventaire Transport par segment.
