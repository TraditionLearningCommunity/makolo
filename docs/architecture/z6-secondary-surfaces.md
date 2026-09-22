# Z6 — Surfaces secondaires personnelles et contextuelles

> **Statut : checkpoint 2 — Z6-A Mes accès implémenté ; runtime et contrat transversal conservés.**
>
> Branche unique Z6 : `task-z6-secondary-surfaces-projections`.
>
> Base du checkpoint : `main@50f47015df7f19dea274bee15e2cee1bd82a3807`.
>
> Le runtime courant gagne sur ce document si `main` évolue avant l'intégration finale.

## 1. Mission

Z6 ferme trois familles d'expérience déjà suffisamment déterminées :

```text
Mes accès  → quels droits ai-je actuellement à disposition et comment les utiliser ?
Historique → qu'est-ce qui s'est déjà réellement passé pour moi ?
Jour J     → cette Occurrence est actuelle pour moi : comment la vivre correctement jusqu'à sa fin ?
```

`Makolo Live` n'est pas une quatrième destination concurrente. Il appartient à `Jour J` et représente ce qui est effectivement en train de se produire dans l'Occurrence.

Z6 compose les vérités propriétaires. Il ne crée ni domaine secondaire générique, ni table de projection, ni nouveau moteur Live.

## 2. État du runtime audité

### 2.1. Programme Z

Au snapshot du checkpoint :

- Z2 est mergé : `Maintenant` et `En cours` sont exposés dans `/api/v1/me/` ;
- Z3 est mergé : la projection Mature de `Découvrir` est disponible ;
- Z4 est mergé : `Moi` et ses profondeurs personnelles sont disponibles ;
- Z5 reste ouvert sur PR #264, branche `task-z5-engaged-detail-projections`, head `6350e140e118620ccba62c9aa14d6512c0a2407e`.

Z5 ajoute notamment les détails personnels Journey et Access, les détails Activity/Occurrence et Objectives. Z6 ne copie pas ces profondeurs. La réconciliation finale devra utiliser les identités et links Z5 effectivement mergés.

### 2.2. CI au point de départ

Le `main@50f47015...` audité a un `ci/aggregate` rouge à cause d'un scénario E2E participant/scanner ; les jobs Django et PostgreSQL de ce run étaient verts.

La PR Z5 audité avait elle-même un job Django rouge sur un test de fixture Questionnaire, alors que ses autres gates spécialisées et son E2E étaient verts.

Ces états sont des **baselines observées**, pas des raisons d'affaiblir un test. Z6 ne doit jamais être mergé tant que son propre head et le `main` de réconciliation ne satisfont pas les gates exigées.

### 2.3. Migrations

Aucune migration Z6 n'est nécessaire au checkpoint 1. Le besoin est déjà porté par les domaines, selectors, read models, APIs, projections et surfaces Web existants.

## 3. Matrice runtime → responsabilité Z6

| Besoin UX | Vérité / owner actuel | Runtime réutilisable | Gap Z6 |
| --- | --- | --- | --- |
| droits personnels actuels | Access | `participant_active_accesses()`, `participant_accesses_visible_to_buyer()`, Web `/me/accesses/` | collection API Mature et contrat de récupération |
| détail d'un droit | Access | Z5 prévoit `/api/v1/me/accesses/<uuid>/` | réutiliser Z5 après merge, ne pas recopier |
| credential | AccessCredential | services Access + Web detail | profondeur protégée seulement lorsqu'elle est légitime ; jamais dans la collection générale |
| usage/passage | AccessUse | Access + scanner/operations | conséquence historique ou détail propriétaire, pas identité du droit |
| historique personnel | Journey + Access principalement | selectors historiques + Web `/me/history/` | projection API transverse, business timestamp Journey à durcir, extensions seulement si sens humain prouvé |
| Occurrence actuelle | Activity/Occurrence + relation participant | Web participant Live + Operations | contrat Jour J et bridges ; pas de second owner |
| Live participant | Operations | `resolve_participant_occurrence_live()` et `/api/v1/operations/occurrences/<uuid>/live/` | réutilisation d'abord, gaps seulement |
| queue | Operations | endpoints participant `queues/me` | composer dans Jour J |
| placement | Operations | endpoints participant `placements/me` | composer dans Jour J ; Capacity reste distincte |
| checkpoints | Operations | endpoints participant `checkpoints/me` | composer dans Jour J ; JourneyStep reste distinct |
| operational readiness | Operations/Readiness | endpoint occurrence readiness | consommer comme projection dérivée, ne pas dupliquer |

## 4. Contrat transversal des surfaces secondaires

Une surface secondaire n'est pas une surface mineure.

> **Elle est secondaire uniquement parce qu'une situation, une réalité ou une intention est déjà suffisamment déterminée.**

Elle peut donc être riche, immersive, directement accessible et temporairement centrale sans devenir un élément permanent de navigation.

Les cinq destinations permanentes restent :

```text
Maintenant | Découvrir | Makolo Mark | En cours | Moi
```

Les surfaces Z6 peuvent être atteintes depuis plusieurs portes :

```text
Maintenant
En cours
détail canonique
Makolo Mark
notification légitime
deep link
autre surface secondaire
```

La multiplicité des portes ne crée jamais plusieurs réalités.

## 5. Identité canonique et provenance de navigation

Z6 sépare :

```text
identité canonique de la réalité
!=
provenance de navigation du client
```

Il n'existe pas de modèles ou ressources comme :

```text
AccessFromNow
HistoryFromMe
JourJFromNotification
SecondarySurface
UserSurfaceItem
NavigationOrigin
```

Le client conserve normalement sa pile de navigation réelle. Un link peut porter un focus contextuel lorsqu'il est utile, mais ce focus ne devient ni identité métier ni état persistant.

Le bouton retour d'une surface secondaire revient vers l'origine réelle lorsque cette origine existe encore ; il ne redirige pas systématiquement vers l'accueil.

## 6. Header secondaire

Le contrat d'expérience est :

```text
retour / sortie appropriée
+ titre humain naturel
+ actions contextuelles réellement utiles
```

Une sous-surface immersive — QR/pass, carte active, Live média, navigation — peut réduire encore ce header. Le backend expose les vérités et links ; il ne persiste pas le chrome de navigation.

## 7. Mes accès

Question humaine :

> **« Quels droits ai-je actuellement à disposition, et comment puis-je les utiliser ? »**

Invariant :

```text
Access           = droit
AccessCredential = représentation / secret du droit
AccessUse        = observation de l'usage / passage
```

`Mes accès` est centré sur Access. Ce n'est ni un wallet QR, ni une liste de commandes, ni un historique.

La porte structurée naturelle peut être `En cours → Mes accès`, sans transfert de propriété. Une action actuelle peut aussi ouvrir directement l'Access ou son credential depuis `Maintenant`, une Occurrence, une Démarche, le Mark ou un deep link.

Le buyer et le beneficiary restent distincts. La visibilité transactionnelle d'un acheteur ne transforme jamais celui-ci en bénéficiaire.

Quand le droit n'est plus actuellement disponible, la question humaine peut devenir historique sans déplacer ni copier l'objet Access dans une autre base.

## 8. Historique

Question humaine :

> **« Qu'est-ce qui s'est déjà passé pour moi ? »**

Historique est une projection temporelle transverse. Il n'est ni un bounded context, ni un `HistoryItem` persistant, ni un audit log, ni une collection de Notifications ou Domain Events.

Le runtime Web possède déjà une composition Journey/Access et une déduplication explicite par `Access.journey`. Z6 doit l'extraire/réutiliser plutôt que reconstruire la vérité.

Le temps métier doit commander l'ordre. Le selector Access possède déjà un `history_at` orienté usage/fin de validité/fin d'Occurrence. La Journey Web utilise encore `updated_at` comme moment historique : ce point est un gap explicite de Z6-B à corriger sans inventer de faux timestamp.

Un événement passé et sa conséquence durable restent distincts :

```text
expérience passée → Historique
Proof/Credential/Resource durable éventuel → owner correspondant / capital personnel
```

## 9. Jour J

Question humaine :

> **« Cette Occurrence est maintenant devenue réelle pour moi : comment est-ce que je la vis correctement depuis ma situation actuelle jusqu'à sa fin ? »**

Jour J est une **surface contextuelle majeure**, pas une sixième destination permanente. Lorsqu'une Occurrence devient actuelle, Jour J peut temporairement devenir l'expérience principale de Makolo pour la personne.

La racine Jour J doit permettre de comprendre :

```text
où j'en suis
ce qui se passe
ce qui vient pour moi
quelle représentation est utile maintenant
```

La représentation peut privilégier selon la situation : temps, déplacement, carte, Access, credential, Live Queue, Placement, checkpoint, programme, mouvement ou Live.

Jour J ne force aucun workflow universel. Une Occurrence simple peut n'exiger que heure + lieu + Access ; une Occurrence complexe peut justifier plusieurs profondeurs.

## 10. Makolo Live appartient à Jour J

Relation canonique :

```text
Occurrence
  → Jour J
      → Makolo Live
      → Mon accès / credential
      → Ma file
      → Ma place
      → carte / orientation
      → autres profondeurs réellement justifiées
```

Makolo Live signifie :

> **ce qui est effectivement en train de se produire dans l'Occurrence maintenant.**

Il peut être opérationnel, spatial, temporel ou médiatique. Live ne signifie pas automatiquement vidéo.

Le runtime Operations possède déjà une API forte et une projection participant explicite. Z6 ne crée donc pas par défaut `/api/v1/me/live/` et ne crée pas un second moteur Live. `Maintenant`, `En cours`, Z5 et les notifications légitimes doivent fournir des links vers l'Occurrence/Jour J concernée.

## 11. Vérité temps réel

Z6 conserve les distinctions :

```text
planned
estimated
observed
live
unknown
unavailable
```

Un horaire planifié n'est pas Live. Une porte planifiée n'est pas une observation temps réel. Une source indisponible ne devient jamais `safe=true`. Une position ou une ETA n'est jamais inventée.

Le caractère immersif n'autorise aucune divulgation supplémentaire.

## 12. Frontières non négociables

```text
Access != AccessCredential != AccessUse
Waitlist != Live Queue
Capacity != Placement
JourneyStep != Checkpoint
Readiness = projection dérivée
Membership != authority
Assignment = responsabilité
Mandate / Permission = autorité
Historique != audit log
En cours != Jour J
Maintenant != Jour J
Jour J != Makolo Live
physical Access != media Access
presence physique != participation Live
```

La composition ne transfère jamais Permission, Mandate, Access, Payment, visibilité privée ou credential.

## 13. Collision audit

Z5 ouvert touche actuellement :

```text
activities/api_urls.py
activities/api_views.py
activities/occurrence_api_urls.py
capacity/selectors.py
config/urls.py
core/api/detail_projections.py
core/api/detail_urls.py
core/api/detail_views.py
core/test_z5_detail_api.py
objectives/api_urls.py
objectives/api_views.py
services/requirement_services.py
docs/architecture/z5-engaged-detail-projections.md
```

Le checkpoint 1 Z6 ne modifie aucun de ces fichiers. Il travaille uniquement le contrat documentaire transversal. Les futurs links vers Access/Journey/Occurrence detail seront réconciliés après stabilisation réelle de Z5.

## 14. Plan de réalisation sur une seule branche

Tous les checkpoints Z6 restent sur `task-z6-secondary-surfaces-projections` :

```text
1. Z6.0 + Z6.1 — runtime + contrat transversal
2. Z6-A        — Mes accès
3. Z6-B        — Historique
4. Z6-C0..C6   — racine Jour J, timing, espace, Access, credential
5. Z6-C7..C12  — Queue, Placement, Checkpoint, Readiness, fin
6. Z6-D        — Makolo Live
7. Z6-E        — bridges Maintenant / En cours / Z5 / Moi / Mark
8. Z6-F        — IDOR, privacy, performance, docs, réconciliation, CI
```

Avant chaque checkpoint, comparer la branche au `main` courant et réauditer les collisions. Avant PR finale/merge, réconcilier complètement Z2/Z3/Z4/Z5 et les routes effectivement livrées.

## 15. Checkpoint 2 — Z6-A Mes accès

Z6-A est implémenté sans nouveau modèle ni migration.

### API de collection

```text
GET /api/v1/me/accesses/
```

La projection `personal.accesses` utilise exclusivement `request.user`.

Par défaut, elle retourne les Access **actuellement portés par le Profile** via `participant_active_accesses()`. Les Access utilisés, expirés, révoqués, annulés, transférés ou passés ne sont pas réinjectés ici : leur mémoire appartient à Historique.

Le contrat est paginé par `limit/offset` avec une borne serveur de 50 et accepte `q` après application du scope personnel.

### Achat pour autrui

La visibilité transactionnelle de l'acheteur reste distincte :

```text
GET /api/v1/me/accesses/?relationship=purchased_for_other
```

Cette relation réutilise `participant_purchased_accesses_for_others()`.

Elle n'affirme jamais que l'acheteur est bénéficiaire et n'expose pas la Journey privée du titulaire. Le payload peut montrer le nom minimal du titulaire nécessaire pour retrouver le droit acheté ; il n'expose ni e-mail, ni téléphone, ni coordonnées privées.

### Credential

La collection ne transporte jamais le token, `public_id`, version ou QR brut. Elle expose uniquement la disponibilité/type de représentation et, lorsqu'elle est réellement présentable, une capability `present_credential`.

La profondeur protégée est :

```text
GET /api/v1/me/accesses/<access-id>/credential/
```

Elle est disponible uniquement :

- au bénéficiaire ; ou
- à l'acheteur pour un Access issu de sa propre CommerceOrder, selon le selector existant.

Un tiers obtient 404. Un Access terminal ne réexpose pas de payload. La réponse qui contient la représentation signée est explicitement `Cache-Control: private, no-store` et `X-Content-Type-Options: nosniff`.

Le token reste la représentation opaque produite par `render_access_credential()`. Z6 ne crée aucune seconde signature, aucun QR parallèle et aucune identité AccessCredential publique supplémentaire.

### Shape de la collection

Chaque ligne conserve notamment :

```text
identity Access
relationship
state
representation contextuelle
Activity
Occurrence + timing + place minimal
validity
holder minimal si achat pour autrui
Journey seulement pour le bénéficiaire
credential summary sans secret
capabilities
links
```

Une date-only reste une date-only. Aucun minuit n'est inventé.

### Moi

`personal.me.links.accesses` pointe vers la surface secondaire sans recopier la collection Access dans `Moi`.

### Invariants fermés par Z6-A

```text
Access != AccessCredential != AccessUse
buyer != beneficiary
collection générale != secret credential
Access historique != Mes accès actuels
scope personnel avant recherche
connaître un UUID != pouvoir lire le droit
```

Tests ciblés : auth, rejet `profile_id`, scope bénéficiaire, séparation historique, achat pour autrui, recherche/pagination, secret absent de la collection, credential no-store, buyer autorisé, tiers 404 et Access terminal sans réexposition.

## 15. Critères de sortie du checkpoint 1

Checkpoint 1 est fermé lorsque :

- le runtime Access/History/Operations Live est cartographié ;
- l'état réel de Z2/Z3/Z4/Z5 est consigné ;
- le baseline CI et les migrations sont connus ;
- le contrat de surface secondaire est fixé ;
- la provenance de navigation est séparée de l'identité métier ;
- `Mes accès`, `Historique`, `Jour J` et `Makolo Live` ont des responsabilités non ambiguës ;
- Jour J est la racine contextuelle de l'Occurrence actuelle ;
- Makolo Live est une profondeur de Jour J ;
- aucune route `/me/live/` ni aucun nouveau owner n'est décidé sans besoin démontré ;
- aucun modèle, migration, score, ranking ou algorithme n'est ajouté ;
- le collision audit Z5 est explicite.
