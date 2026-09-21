# Z3.0 / Z3.1 — Audit runtime et socle de projection des possibilités

> **Statut : audit Z3.0 terminé ; socle Z3.1 implémenté.**
> Base auditée : `main@6a4c59fd6388d481834ca33cbd7e561682c127a1`.
> Le runtime courant reste toujours prioritaire sur ce snapshot.

## 1. Objet

Z3 ferme progressivement le décalage entre l'expérience Web Mature de `Découvrir` et son API, sans introduire de moteur de ranking, de modèle universel de possibilité ni de logique métier concurrente.

Z3.0 vérifie le runtime et les collisions avant modification.

Z3.1 fournit un contrat read-only commun permettant aux futurs endpoints Z3 de transporter les faits nécessaires à Web, Flutter et aux futurs clients sans leur demander de connaître l'ORM Django ni de reconstruire Access, Journey, Capacity ou les identités métier.

Cette étape ne modifie encore aucune route HTTP. L'alignement de la collection `/api/v1/discovery/items/` avec le champ Mature appartient à Z3.2.

## 2. Etat GitHub vérifié avant changement

Au démarrage du lot :

- `main` pointe sur `6a4c59fd6388d481834ca33cbd7e561682c127a1`, merge de Z1 ;
- le statut agrégé `ci/aggregate` de ce commit est vert ;
- Z2 existe sur `task-z2-attention-continuity-projections`, exactement un commit devant `main`, et ne modifie alors que `docs/architecture/backend-ux-projection-api.md` ;
- aucune branche ou PR Z3, Z4 ou Z5 concurrente n'est ouverte au moment de l'audit ;
- les PR Observer #255/#256 ne touchent pas Discovery ;
- la PR Space archetypes #252 touche notamment `discovery/test_c1_correctness.py`, mais pas le nouveau socle `discovery/api/projections.py` ;
- la PR de recherche #223 reste un laboratoire isolé sans modification du runtime ;
- l'ancienne branche `fix/finalize-discovery-presentation` est devenue historique et très en retard sur `main`.

En conséquence, Z3 utilise la branche dédiée :

```text
task-z3-discovery-possibility-projections
```

et évite, pour Z3.0/Z3.1, le document Z1 actuellement touché par Z2 ainsi que les tests C1 touchés par #252.

## 3. Runtime Web Mature observé

`DiscoveryHomeView` compose déjà quatre familles de possibilités dans une pagination logique commune :

| Famille de projection | Vérité canonique principale | Contexte complémentaire | Conservation actuelle |
| --- | --- | --- | --- |
| `activity` | `Activity` | une Occurrence représentative et les Occurrences correspondantes | `ActivityBookmark` |
| `service_activity` | `Activity` | `ServiceDetails` | `ActivityBookmark` |
| `funding_activity` | `Activity` | `FundingDetails` | `ActivityBookmark` |
| `opportunity` | `Opportunity` | `OpportunityRevision` publiée observée | `OpportunitySave` |

La composition Web utilise déjà :

- `search_occurrences()` pour les possibilités Activity/Occurrence ;
- `public_service_discovery_items()` pour Service ;
- `public_funding_discovery_items()` pour Funding ;
- `public_opportunity_discovery_items()` pour Opportunity ;
- une déduplication par identité logique exacte ;
- une pagination après composition logique ;
- un enrichissement viewer-aware des bookmarks et saves ;
- `DiscoveryCardPresentation` et les presenters propriétaires pour la présentation.

Aucun super-modèle `DiscoverItem` persistant n'est nécessaire.

## 4. Identité et déduplication

Les identités logiques existantes sont conservées :

```text
activity:<activity_id>
service_activity:<activity_id>
funding_activity:<activity_id>
opportunity:<opportunity_id>
```

Pour une Activity issue d'Occurrences, l'Occurrence représentative reste une ressource distincte. Elle ne remplace pas l'identité Activity de la possibilité agrégée.

Opportunity garde son identité propre. Z3 ne fabrique ni Activity ni Occurrence pour une Opportunity directe.

La révision Opportunity observée est conservée séparément afin que le client puisse connaître la version publiée à l'origine des faits projetés.

## 5. Visibilité et admission dans Discover

Les selectors actuels portent déjà une partie importante de la sécurité de lecture :

- Activity doit être publiée et publique ;
- les Occurrences Discover sont planifiées et encore pertinentes temporellement ;
- les Spaces suspendus sont exclus ;
- l'éligibilité de Groupe est appliquée par le selector existant ;
- les places publiques passent par la projection Geography existante ;
- Service utilise des Activities publiées/publiques ;
- Funding utilise `public_fundings()` et sa fenêtre propriétaire ;
- Opportunity utilise les selectors `open_opportunities()` et `upcoming_opportunities()`.

Une ressource privée ne doit donc jamais être réadmise par Z3 après qu'un selector propriétaire l'a exclue.

## 6. Relation personnelle

Pour les familles Activity/Occurrence et Service, le runtime possède déjà la primitive canonique :

```text
resolve_participant_activity_state(...)
```

avec les contextes batchés :

```text
participant_state_context(...)
participant_state_context_for_activities(...)
```

Cette résolution compose notamment des faits Access, Journey, Request, CapacityReservation, CommerceOrder et Payment, strictement pour le Profile fourni par le serveur.

Z3.1 transporte l'état technique déjà résolu et son échéance éventuelle. Il ne transporte pas comme vérité métier les labels, variantes visuelles ou phrases de présentation.

Funding et Opportunity ne possèdent pas encore, dans leur pipeline Discover actuel, une relation personnelle équivalente suffisamment générale. Z3.1 les représente donc explicitement comme :

```json
{"state": "unknown"}
```

au lieu d'inventer une absence ou une compatibilité.

## 7. Availability, prix et inconnu

Z3.1 distingue les faits connus de l'inconnu :

- Activity/Occurrence reprend la disponibilité Capacity déjà calculée et, lorsqu'elle existe, le prix canonique de l'Offer applicable ;
- Service ne possède pas aujourd'hui de disponibilité générique équivalente : `availability.state = unknown` ;
- Opportunity expose son état temporel propriétaire `open` ou `upcoming` ;
- Funding est seulement admis par son selector lorsqu'il est public et dans sa fenêtre active ; cela n'est pas une déclaration d'éligibilité personnelle ;
- une valeur absente ou non résolue n'est jamais convertie en impossibilité.

Un Decimal monétaire est sérialisé en chaîne, conformément à Z1.

## 8. Conservation

Le runtime possède deux vérités de conservation distinctes :

```text
ActivityBookmark  -> Activity / Service / Funding
OpportunitySave   -> Opportunity
```

L'API Event historique de bookmark est une façade de compatibilité adossée à `ActivityBookmark`.

Z3.1 n'ajoute aucun `SavedItem` universel. Il transporte seulement :

```text
saved
not_saved
unknown
```

selon que l'état a effectivement été résolu par le caller.

Bookmark reste distinct d'Interest, Watch et engagement.

## 9. DiscoveryWatch

`DiscoveryWatch` est déjà la vérité persistante de Veille dans `discovery`. Le contrat canonique existant la décrit comme une requête Discovery privée, rejouable et owner-scoped.

Z3.1 ne tente pas encore d'inférer qu'une possibilité donnée est couverte par une Watch. Tant que Z3.6 n'a pas résolu cette relation selon le contrat réel, la projection porte :

```json
{"state": "unknown"}
```

Cette décision évite de confondre absence observée et absence réelle.

## 10. API existante et décalage confirmé

L'API actuelle expose notamment :

```text
GET /api/v1/discovery/items/
GET /api/v1/discovery/map/
GET /api/v1/discovery/for-you/
GET/POST /api/v1/discovery/bookmarks/
DELETE /api/v1/discovery/bookmarks/{event_id}/
```

Le constat Z0 est toujours valide :

- `/items/` utilise encore directement `search_occurrences()` et ne reflète donc pas le champ Web multi-famille ;
- `/map/` reste intentionnellement une projection publique bornée des Occurrences géolocalisées ;
- `/for-you/` conserve son ancien contrat `event_compatibility` et son historique de recommandations/trending ; Z3 ne généralise pas ce score ;
- l'API bookmark reste Event-shaped pour compatibilité.

Z3.2 devra aligner la collection Mature sans supprimer brutalement ces façades historiques.

## 11. Contrat Z3.1

Le socle `discovery/api/projections.py` compose une possibilité à partir de faits déjà résolus.

Forme commune :

```json
{
  "identity": {
    "family": "activity",
    "candidate_key": "activity:<uuid>",
    "resource": {"kind": "activity", "id": "<uuid>"},
    "occurrence": {"kind": "occurrence", "id": "<uuid>"},
    "revision": null
  },
  "representation": {
    "kind": "image",
    "title": "...",
    "summary": "...",
    "image_url": null,
    "route_label": null,
    "eyebrow": null
  },
  "timing": null,
  "place": null,
  "owner": {"display_name": "..."},
  "availability": {"state": "available", "remaining": 4},
  "price": {"state": "priced", "minimum": "20.00", "currency": "USD"},
  "personal_relation": {"state": "none", "availability": "available", "expires_at": null},
  "saved": {"state": "not_saved"},
  "watch": {"state": "unknown"},
  "capabilities": ["view"],
  "links": {"detail": "..."},
  "provenance": {
    "resources": [
      {"kind": "activity", "id": "<uuid>"},
      {"kind": "occurrence", "id": "<uuid>"}
    ]
  }
}
```

Ce contrat est une projection, pas une nouvelle identité métier.

## 12. Backend / frontend

Le backend Z3.1 transporte les faits dont le client a besoin :

- identités ;
- représentation factuelle déjà disponible ;
- timing et place ;
- owner public minimal ;
- prix et disponibilité ;
- relation personnelle déjà résolue ;
- état de conservation connu ;
- état de Watch connu ou explicitement inconnu ;
- capabilities techniques réellement établies ;
- links ;
- provenance des ressources métier.

Le frontend reste propriétaire :

- de la mise en page ;
- du regroupement visuel ;
- de la formulation éditoriale ;
- des sections « établi / favorable / limitant / à confirmer / inconnu » lorsqu'elles sont une lecture UX de faits reçus ;
- du choix des icônes, couleurs, densités et médias affichés.

Le frontend ne doit cependant jamais recalculer Access, Journey, Payment, Capacity, satisfaction de Requirement ou autorité.

## 13. Frontières explicitement verrouillées

Z3.1 n'introduit pas :

```text
global_score
match_percentage
attention_score
rank
relevance
probability
confidence
```

comme vérité transversale.

Il ne sérialise pas :

- `AccessCredential` ;
- QR/token/secret ;
- Permission/Mandate bruts ;
- notes privées ;
- CRM ;
- données d'un autre participant.

Il ne déduit pas :

- Requirement satisfait depuis un document ;
- éligibilité depuis une heuristique ;
- Watch depuis un Bookmark ;
- Interest depuis une consultation ;
- Journey depuis une possibilité.

## 14. Capabilities et links à ce stade

Z3.1 est volontairement conservateur.

Il peut exposer :

- `view` ;
- `save` / `unsave` seulement lorsque l'état de conservation a été réellement résolu **et** que l'autorité correspondante est explicitement établie ;
- une action de continuité déjà résolue pour une relation personnelle existante, par exemple `access`, `pay` ou `continue`.

L'état `saved/not_saved` ne confère jamais, à lui seul, l'autorité `save/unsave` : Z3.1 sépare explicitement état et capability.

Il n'expose pas encore une capability universelle d'engagement initial à partir du simple CTA de carte. La définition du handoff vers les vrais services propriétaires appartient à Z3.7.

De même, les routes HTML de save/share existantes ne sont pas promues comme APIs de mutation pour Flutter.

## 15. Performance

Le nouveau socle Z3.1 est pur/read-only et n'effectue aucune requête SQL.

Les requêtes et batchs restent dans les selectors existants. Cela permet à Z3.2 de composer une page entière sans ajouter un query Access/Journey/Payment par carte.

## 16. Migration

Aucune migration Z3.0/Z3.1.

Aucun modèle, champ, table, index ou backfill n'est ajouté.

## 17. Critères de fermeture de Z3.0 / Z3.1

Z3.0 est fermé lorsque :

- `main`, CI, PRs/branches concurrentes et collisions sont vérifiés ;
- le champ Web réel et les APIs legacy sont cartographiés ;
- les propriétaires de chaque famille et conservation sont identifiés ;
- les gaps vers Z3.2+ sont explicités.

Z3.1 est fermé lorsque :

- une forme commune read-only existe ;
- les quatre familles actuelles possèdent un adaptateur ;
- l'identité canonique et OpportunityRevision sont préservées ;
- `unknown` n'est pas converti en faux ;
- la relation personnelle existante reste serveur-résolue ;
- aucune logique de ranking/score n'est ajoutée ;
- aucun secret/credential n'est exposé ;
- aucun accès DB/N+1 n'est introduit dans la projection ;
- les tests ciblés du contrat sont verts ;
- le contrôle migrations et la CI applicable restent verts.

## 18. Suite

Z3.2 pourra maintenant faire converger la collection Mature `/api/v1/discovery/items/` vers ce contrat en réutilisant exactement les mêmes familles/selectors que le Web, sans réécrire Discovery et sans toucher à l'intelligence future.


## 19. Réconciliation parallèle après ouverture des PR Z

Après l'audit initial, les chantiers parallèles ont avancé :

- Z4 a ouvert la PR #258 sur `task-z4-me-personal-capital-projection` ; ses fichiers courants sont `config/urls.py`, `core/api/me_projection.py`, `core/api/me_views.py`, `core/api/urls.py` et `core/test_z4_me_api.py` ; aucun ne chevauche le diff Z3.0/Z3.1 ;
- Z2 a ouvert la PR #260 ; son diff courant reste dans `core/api/*`, `core/home_presentation.py`, son test Z2 et `docs/architecture/backend-ux-projection-api.md` ; aucun ne chevauche les trois fichiers Z3.0/Z3.1 ;
- Z5 n'a toujours pas de branche détectée lors de cette réconciliation.

Le collision audit reste donc favorable pour la fondation Z3.1. Une nouvelle réconciliation sera obligatoire avant Z3.2, notamment si Z3 doit toucher des URLs ou des fichiers API partagés.


## 20. Z3.2 — Collection Mature

`GET /api/v1/discovery/items/` est désormais la projection API du même champ logique que le Web Mature. Elle compose, sans ranking transversal :

- Activity/Occurrence agrégée Activity-first ;
- Service Activity ;
- Funding Activity ;
- Opportunity directe.

La pagination est bornée après composition logique commune. Une fin de résultats reste une fin de résultats : aucun filler ni feed artificiel n'est injecté.

Le contrat Event historique reste disponible sous `/api/v1/events/discover/`. `/api/v1/discovery/for-you/` demeure explicitement une compatibilité Event historique et n'est pas utilisée comme moteur de pertinence Z3.

Les gates Group sont appliqués à Activity/Occurrence, Service et Funding avant exposition. Web et API utilisent le Profile courant comme viewer ; un client ne peut pas fournir un `profile_id` arbitraire.

## 21. Z3.3 — Détail désigné

La route canonique est :

```text
GET /api/v1/discovery/items/{family}/{id}/
```

Elle fait du **retrieve**, pas une nouvelle recherche : les paramètres `q`, `place`, etc. ne redéfinissent pas l'objet demandé.

Familles acceptées :

```text
activity
service_activity
funding_activity
opportunity
```

Le détail réutilise les selectors publics/propriétaires, respecte Group eligibility et renvoie 404 lorsqu'une ressource n'est pas admissible. Private, UNLISTED, Occurrence annulée/terminée ou Opportunity hors du champ actif ne sont pas réadmis par le détail Z3.

## 22. Z3.4 — Relation personnelle et assessment factuel

Activity/Occurrence et Service continuent d'utiliser le resolver canonique de relation personnelle. Aucun `profile_id` client n'est pris en compte.

L'API expose un assessment strictement factuel :

```text
favorable
limiting
unknown
```

avec code stable, label et provenance. Les états connus de disponibilité ou Access peuvent produire un fait favorable/limitant. Lorsqu'un domaine ne permet pas de conclure, l'état reste `unknown`.

Z3 ne déduit jamais la satisfaction d'un Requirement, l'éligibilité ou la Readiness à partir de la simple possession d'un document.

## 23. Z3.5 — Conservation

Nouvelle route :

```text
PUT    /api/v1/discovery/items/{family}/{id}/saved/
DELETE /api/v1/discovery/items/{family}/{id}/saved/
```

Elle délègue aux vérités existantes :

- Activity/Service/Funding → `ActivityBookmark` ;
- Opportunity → `OpportunitySave` et services Opportunity canoniques.

La mutation est authentifiée et ne crée ni Interest, ni Watch, ni Journey, ni Dossier.

Les anciennes routes Event-shaped `/bookmarks/` restent compatibles.

## 24. Z3.6 — Veilles

Les Veilles existantes sont exposées sous :

```text
GET/POST        /api/v1/discovery/watches/
GET/PATCH/DELETE /api/v1/discovery/watches/{id}/
GET             /api/v1/discovery/watches/{id}/results/
```

Toutes les opérations sont owner-scoped sur `request.user`; un autre Profile reçoit 404.

Le replay respecte le contrat G4 actuel : Activity/Occurrence + Service. Z3 n'étend pas silencieusement `DiscoveryWatch` à Funding/Opportunity tant que leur sémantique de critères n'est pas contractée. Les résultats d'un replay sont marqués `watch.state=covered`; ailleurs, une relation inverse non résolue reste `unknown`.

Créer ou rejouer une Veille ne crée ni Bookmark, ni Interest, ni Journey.

## 25. Z3.7 — Handoff vers les domaines propriétaires

Z3 ne possède pas l'engagement.

Pour Event, où une API propriétaire réelle existe déjà, la projection fournit des liens vers :

- détail Event participant ;
- TicketTypes/offres ;
- création/listing des Ticket Orders.

Aucune Journey n'est créée lors de l'ouverture de Discover ou du détail.

Pour Service, Funding et Opportunity, Z3 expose `owner_contract` sans inventer une mutation générique. Les futurs clients doivent utiliser une API propriétaire lorsqu'elle existe réellement ; l'absence d'API propriétaire ne justifie ni POST HTML maquillé ni Journey réflexe.

## 26. Recherche, carte et localisation

La carte est construite depuis la même composition de recherche et les mêmes contraintes du viewer. Seules les possibilités réellement mappables produisent un point.

Les coordonnées `lat/lon` reçues restent des critères ponctuels de recherche. Z3 ne les persiste pas automatiquement dans Profile, CRM, Analytics ou UserDevice.

La carte ne transporte aucune relation personnelle privée.

## 27. Réconciliation avec main après Z2

Pendant Z3, `main` a avancé jusqu'à `4c3d2e5cce9ba881bf78339de5f97649e942f0e2` par merge de Z2 (#260).

Le diff Z3 n'entre pas en collision avec les fichiers Z2 mergés. La PR GitHub reste mergeable contre ce main et les checks PR s'exécutent sur le merge ref courant.

Z4 continue dans la PR #261 et touche notamment `core/api/*`, Recognition et `docs/architecture/backend-ux-projection-api.md`. Z3 évite volontairement ces fichiers partagés et garde son contrat détaillé dans ce document de chantier pour empêcher une collision documentaire pendant le parallélisme.

Une nouvelle vérification de `main` et des checks sera faite immédiatement avant merge Z3.

## 28. Fermeture Z3

Z3 est considéré implémenté lorsque :

- collection multi-famille et détail désigné sont disponibles ;
- relation personnelle est résolue serveur lorsque le runtime possède un resolver ;
- favorable/limitant/unknown ne dépassent pas les faits observés ;
- conservation et Veille restent distinctes d'Interest et engagement ;
- un handoff Event réel pointe vers l'API propriétaire ;
- aucune création réflexe de Journey n'existe ;
- carte/list/search partagent le même champ et les mêmes gates ;
- aucune donnée privée/credential n'est exposée ;
- aucun score/ranking/recommender transversal n'est créé ;
- aucune migration n'est ajoutée ;
- tests ciblés, contrôle migrations, suite pertinente et CI sont verts ;
- la PR est réconciliée puis mergée sur `main`, et `main` est revalidé.
