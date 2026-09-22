# Z6 — Surfaces secondaires personnelles et contextuelles

> **Statut : checkpoint 5 — Z6-C7..C12 Jour J opérationnel implémenté ; checkpoints 6 à 8 restent ouverts.**
>
> Branche initiale Z6 : `task-z6-secondary-surfaces-projections` (mergée via PR #267).\n>\n> Branche unique de continuation checkpoints 4–8 : `task-z6-continuation-jour-j-live`.
>
> Base initiale Z6 : `main@50f47015df7f19dea274bee15e2cee1bd82a3807`.
>
> Réconciliation checkpoint 3 : `main@08ba105e1ff301e2e596d7ed6c2b2dd781095518` après merge de Z5.
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
- Z5 est maintenant mergé dans `main` via la PR #264 ; les détails personnels Journey/Access et les autres profondeurs Z5 sont disponibles.

Z6 ne copie pas ces profondeurs. Depuis la réconciliation du checkpoint 3, Historique pointe vers les routes Z5 réellement livrées pour les détails Journey et Access.

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

Le checkpoint 1 Z6 ne modifiait aucun de ces fichiers. Au checkpoint 3, Z5 est mergé dans `main`; la branche Z6 a été réconciliée sans conflit et réutilise désormais ses routes de détail, sans modifier les fichiers propriétaires Z5.

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

## 16. Checkpoint 3 — Z6-B Historique

Z6-B expose une mémoire personnelle transverse sans créer de domaine `History`.

### API

```text
GET /api/v1/me/history/
```

La projection `personal.history` utilise exclusivement `request.user` et réutilise les selectors historiques canoniques Journey et Access.

Les sources admises restent **Access** et **Journey**. Notification, Domain Event, logs techniques, clics, recherches, Goal numérique ou simple `created_at` d'un modèle arbitraire ne deviennent pas des faits historiques.

### Déduplication

Une Journey possédant un Access historique n'apparaît pas comme une seconde expérience. L'Access porte alors la représentation historique de cette expérience, conformément au selector Web déjà existant.

```text
Journey liée + Access historique
→ une seule ligne d'Historique
→ source = Access
```

### Temps métier Journey

Le gap du checkpoint 1 est fermé dans le selector canonique.

`participant_unified_history_journeys()` annote désormais `history_at` avec le meilleur moment métier persisté :

```text
FULFILLED → fulfilled_at
CANCELLED → cancelled_at
EXPIRED   → expires_at
autre terminal → transition vers le statut terminal courant
legacy incomplet → updated_at seulement comme fallback
```

Aucun timestamp n'est inventé. Les anciennes données incomplètes restent valides et projetables sans backfill.

Le Web `/me/history/` consomme le même `history_at` : API et Web ne possèdent donc pas deux règles temporelles.

### Temps métier Access

Le selector Access conserve sa règle canonique :

```text
USED + passage accepté → AccessUse.used_at
VALID + Occurrence passée → Occurrence.end_at
VALID + validité finie → valid_until
autre terminal → updated_at faute de timestamp propriétaire plus précis
```

### Shape

Une ligne expose uniquement :

```text
kind
source canonique
title
occurred_at
outcome
representation contextuelle
Activity
Occurrence minimale
capabilities
links
```

Elle n'expose ni AccessCredential, ni token QR, ni contrôleur, ni `client_reference`, ni payload technique.

Après la réconciliation avec `main@08ba105e...`, Z5 est livré. Chaque ligne Historique expose donc un lien `detail` vers la profondeur canonique Z5 correspondante : `/api/v1/me/journeys/<uuid>/` ou `/api/v1/me/accesses/<uuid>/`. Z6 ne fabrique aucun endpoint de détail concurrent.

### Recherche, ordre et pagination

`q` est appliqué après le scope personnel. Le filtre `type` accepte `all`, `accesses` ou `journeys`.

La pagination est bornée par `limit/offset`, avec maximum serveur de 50. L'union Python ne charge que `offset + limit` lignes par source et applique un ordre déterministe :

```text
history_at desc
created_at desc
Access avant Journey en égalité
UUID asc
```

### Confidentialité

La réponse est `Cache-Control: private, no-store`.

Un acheteur n'acquiert jamais l'historique du bénéficiaire d'un droit acheté pour autrui. Un Profile tiers ne peut entrer dans la projection par UUID, recherche ou relation transactionnelle.

### Moi

`personal.me.links.history` référence l'Historique sans embarquer la collection dans `Moi`.

### Invariants fermés

```text
Historique != audit log
Historique != Notifications
Historique != Domain Events
passé != simple timestamp technique
buyer != beneficiary
événement passé != conséquence durable
active != historique
unknown/legacy incomplet != erreur 500
```

Aucun modèle, migration, snapshot, `HistoryItem`, ranking, score ou backfill n'est ajouté.

## 17. Checkpoint 4 — Z6-C0..C6 Jour J fondation

Le checkpoint 4 matérialise la racine personnelle Jour J sans créer de nouvel owner.

### Route

```text
GET /api/v1/me/occurrences/<uuid>/day-of/
```

Projection :

```text
personal.occurrence.day_of
```

L'Occurrence est chargée par UUID mais la réponse n'est autorisée que si `resolve_participant_occurrence_live()` confirme une relation participant réelle. Un propriétaire/opérateur sans relation participant reçoit 404 ; un Profile multi-rôle qui est aussi participant reçoit toujours la projection participant-safe.

### Composition

La racine compose :

```text
Occurrence
+ Operations participant-safe
+ Access du bénéficiaire
```

Elle ne possède aucune vérité métier et ne duplique pas le moteur Operations Live.

### Les quatre dimensions de la racine

`situation` répond explicitement à :

```text
où j'en suis temporellement
ce qui est l'état de l'Occurrence
quel est mon prochain mouvement propriétaire connu
quelle représentation est la plus utile maintenant
```

La position physique courante du participant n'étant pas observée par le runtime actuel, elle reste explicitement :

```json
{"state": "unknown", "truth": "unknown", "reason": "participant_position_not_observed"}
```

Le lieu de l'Occurrence est une destination planifiée, jamais présenté comme la position actuelle de la personne.

### Vérité temporelle et spatiale

Jour J distingue dans son payload :

```text
planned   → horaire et destination canoniques de l'Occurrence
estimated → uniquement lorsqu'une estimation mobilité réelle existe
observed  → état Access, next movement et hazards courants
unknown   → position/mobilité non observée ou indisponible
live      → handoff seulement lorsque l'Occurrence est en phase arrival/live
```

Une date-only reste une date-only ; aucun minuit artificiel n'est créé.

### Access et credential

Les Access de l'Occurrence sont composés directement dans Jour J avec état, validité et utilisabilité issue du resolver Operations.

Le credential reste une profondeur protégée :

```text
Jour J → /api/v1/me/accesses/<uuid>/credential/
```

Jour J n'expose ni token, ni `public_id`, ni payload QR. Un Access révoqué ou non présentable reste visible comme contexte mais ne reçoit aucune capability `present_credential`.

### Live

Jour J ne crée aucun moteur Live. En phase `arrival` ou `live`, il expose seulement le handoff vers :

```text
/api/v1/operations/occurrences/<uuid>/live/
```

La composition détaillée Queue/Placement/Checkpoint/Readiness appartient au checkpoint 5. Le contrat Makolo Live riche appartient au checkpoint 6.

### Confidentialité

La réponse est `private, no-store`. Elle ne sérialise ni données d'un autre participant, ni assignments opérateur, ni scanner, ni Permission/Mandate bruts.

Aucun modèle ni migration n'est ajouté.

## 18. Checkpoint 5 — Z6-C7..C12 Jour J opérationnel

Jour J compose désormais les profondeurs participant-safe déjà calculées par Operations :

```text
queue
placement
checkpoints
readiness
completion
```

### Live Queue

`queue` ne contient que les entrées de la personne. Elle expose l'état, la position lorsque connue, le moment d'appel et les links vers les APIs Operations personnelles. Aucun nom ou identifiant d'un autre participant n'est projeté.

Une entrée `called` reste prioritaire dans `situation.next`, conformément au resolver Operations. Une entrée `waiting` reste une attente normale et ne devient pas un blocker par composition.

Waitlist n'entre pas dans cette structure : **Waitlist != Live Queue**.

### Placement

`placement` reprend uniquement les assignments du Profile : plan, unité et unité parente éventuelle. Aucun autre occupant n'est exposé.

```text
Placement → où ?
Capacity  → combien ?
```

Jour J ne convertit donc pas Capacity en placement et n'inclut pas les agrégats opérateur de capacité dans cette profondeur personnelle.

### Checkpoints

`checkpoints` projette la progression opérationnelle de l'Occurrence et le prochain checkpoint propriétaire connu.

Un Checkpoint reste distinct d'un JourneyStep.

### Readiness

`readiness` reformule les contributors participant-safe d'Operational Readiness en quatre conséquences :

```text
ready
actor_interventions
waiting
blockers
```

Aucun score de Readiness n'est créé et l'utilisateur n'édite jamais cet état dérivé.

### Fin de l'Occurrence

En phase `after`, Jour J ne fabrique aucune prochaine action Live. `completion` ferme la situation et expose le handoff vers :

```text
/api/v1/me/history/
```

Les conséquences durables restent chez leurs owners. Jour J ne devient pas une archive.

Aucun modèle, migration ou état Jour J persistant n'est ajouté.

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
