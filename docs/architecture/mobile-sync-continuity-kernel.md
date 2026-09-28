# Makolo Mobile — Sync & Continuity Kernel

> **Statut : Bloc B fermé — contrat canonique de conception**
>
> **Objet :** fixer comment l'application mobile reçoit, rafraîchit, invalide, applique, prépare, rejoue et réconcilie les données et intentions avec les owners serveur Makolo.
>
> **Base runtime vérifiée lors de cette consolidation :** `main@96f3992b38afc5352c1da2572a9a9b695359a5de` — A1 Installed Makolo Core (#306).
>
> **Dépendance logique :** `docs/architecture/mobile-local-data-kernel.md` (Bloc A, PR #337 au moment de cette consolidation).
>
> Le runtime courant gagne toujours sur ce document. Avant toute implémentation, revalider `main`, les PR mobiles ouvertes, les contrats API, les migrations Drift, les tests et les docs canoniques.

---

## 1. Objet

Le Bloc A a fixé ce que le téléphone peut connaître localement.

Le Bloc B fixe :

> **comment cette connaissance arrive, reste suffisamment fraîche, repart vers le serveur lorsqu'une action est faite, puis converge avec la vérité canonique.**

Le Sync & Continuity Kernel n'est pas un domaine métier. Il n'est pas propriétaire de Journey, Access, Discovery, Payment, Capacity, Queue, Profile ou Activity.

Il orchestre leurs owners.

La formule générale est :

```text
SERVER OWNER
    ↓
MakoloApiClient
    ↓
SyncSource / Remote Contract
    ↓
Applier
    ↓ transaction
Local Data Kernel
    ↓
Selectors
    ↓
Experience
```

Pour les écritures :

```text
Experience
    ↓
intention
    ↓
draft / pending overlay / OutboxOperation
    ↓
OutboxHandler owner-specific
    ↓
SERVER OWNER
    ↓
canonical response or reconciliation
    ↓
Applier / invalidation / refetch
    ↓
Local Data Kernel
```

Invariant :

> **Le serveur décide et calcule les vérités Makolo. Le mobile reçoit, conserve, synchronise, présente et peut calculer seulement les conséquences déterministes de données qu'il possède déjà.**

---

## 2. Principes structurants

1. **Un seul Network Core** derrière `MakoloApiClient`.
2. **Un Sync Engine owner-scoped**, jamais un `syncEverything()`.
3. **Une SyncSource représente une source serveur, pas un écran Flutter.**
4. **La fraîcheur d'affichage et l'autorisation d'agir sont distinctes.**
5. **Les pulls s'appliquent atomiquement.**
6. **Les Appliers sont explicites par contrat.**
7. **Une invalidation demande une revalidation ; elle ne détruit pas la donnée locale.**
8. **Une OutboxOperation représente une intention durable, pas une vérité métier.**
9. **La replay policy appartient à l'owner.**
10. **Un résultat réseau ambigu nécessite parfois une réconciliation, pas un retry aveugle.**
11. **Le push signale qu'une vérité mérite d'être revérifiée ; il n'est pas la vérité.**
12. **Background, resume, reconnect et push déclenchent le même moteur ; aucun n'en devient propriétaire.**
13. **Aucun endpoint `/api/v1/mobile/sync/` ni cursor transverse n'est introduit sans besoin démontré.**

---

## 3. Network Core

Le contrat mobile reste :

```text
Feature / Repository
        ↓
MakoloApiClient
        ↓
transport technique
```

Le transport concret peut être Dio, mais Dio ne doit pas fuir dans les features ni dans les repositories.

`MakoloApiClient` doit couvrir :

- GET ;
- POST ;
- PUT ;
- PATCH ;
- DELETE ;
- JSON ;
- multipart ;
- upload/download ;
- progression upload/download ;
- annulation ;
- timeouts ;
- headers ;
- refresh JWT single-flight ;
- normalisation des erreurs.

### 3.1 Authentification

Cycle canonique :

```text
request
  ↓
401
  ↓
single-flight refresh
  ↓
rotation du refresh token persistée
  ↓
retry une fois
```

Si le refresh est définitivement invalide :

```text
invalidate tokens
→ session recovery
→ re-authentication
```

Cinq requêtes simultanées en 401 ne déclenchent jamais cinq refresh token concurrents.

---

## 4. SyncSource

Une `SyncSource` représente :

> **une source serveur identifiable que le mobile sait rafraîchir, valider, interpréter et appliquer localement.**

Conceptuellement :

```text
SyncSource
├── sourceKey
├── owner
├── actorScope
├── requestDefinition
├── responseContract
├── supportedSchemaVersions
├── applier
├── freshnessPolicy
├── retentionPolicy
├── paginationPolicy?
├── sensitivity
└── refreshTriggers
```

Ce contrat ne signifie pas qu'une seule classe Dart monolithique doit contenir toutes ces responsabilités. Il fixe les informations nécessaires.

### 4.1 sourceKey

`sourceKey` est l'identité logique locale de la source.

Exemples conceptuels :

```text
account.me
personal.now
personal.ongoing
personal.me

activity:<id>
occurrence:<id>
journey:<id>
access:<id>
resource:<id>
group:<id>

day-of:<occurrence-id>
operations-live:<occurrence-id>
offline-pack:<occurrence-id>

notifications
history:<context>
discover:<query-fingerprint>
watch-results:<watch-id>:<query-fingerprint>
```

Le `sourceKey` n'est pas l'URL. Une évolution de route HTTP ne doit pas invalider l'identité logique locale.

### 4.2 owner

L'owner métier reste explicite : Profile, Journey, Access, Discovery, Operations, Notifications, Conversations, Recognition, etc.

Le Sync Engine ne réimplémente pas la logique métier de cet owner.

### 4.3 actorScope

Le contrat actuel est principalement Profile personnel.

La conception garde la possibilité future d'un scope distinct quand un Profile agit légitimement pour un Space.

> **Changer de contexte n'accorde aucune autorité. Membership ≠ Permission/Mandate.**

La clé de source ne doit donc jamais devenir une autorité implicite.

### 4.4 requestDefinition

La source sait comment demander sa projection ou son owner payload.

Le moteur central ne doit pas accumuler cinquante `if endpoint == ...`.

### 4.5 responseContract

Le runtime Makolo expose plusieurs formes :

1. projection envelope `meta + data` ;
2. pagination DRF `count/next/previous/results` ;
3. objets directs owner-specific ;
4. collections directes ;
5. payloads opérationnels directs.

Le Sync Core accepte cette hétérogénéité. Il ne force pas artificiellement tous les owners à imiter `personal.now`.

---

## 5. Catégories de sources

### 5.1 Root sources

Exemples :

- `personal.now`
- `personal.ongoing`
- `personal.me`

Elles alimentent les grandes expériences transverses.

### 5.2 Resource/detail sources

Exemples :

- `activity:<id>`
- `occurrence:<id>`
- `journey:<id>`
- `access:<id>`
- `resource:<id>`
- `group:<id>`
- `partner:<id>`

### 5.3 Collection sources

Exemples :

- History ;
- Resources ;
- Accesses ;
- Notifications ;
- Conversations.

La pagination reste owner-specific.

### 5.4 Query sources

Exemples :

- Discovery items ;
- Discovery map ;
- Watch results.

Une requête Discovery n'est pas une nouvelle vérité métier. Son cache reste reconstructible.

### 5.5 Operational sources

Exemples :

- Jour J ;
- Operations Readiness ;
- Operations Live ;
- Offline Action Pack.

Elles suivent des politiques plus volatiles et plus strictes.

---

## 6. Registre initial des sources

| sourceKey conceptuel | Route/owner actuelle | Forme | Persistance | Freshness | Applier / effet local |
| --- | --- | --- | --- | --- | --- |
| account.me | `GET /api/v1/accounts/auth/me/` | objet compte | état session minimal | session | identité locale minimale |
| personal.now | `GET /api/v1/me/now/` | envelope | snapshot root | SWR | refs + snapshot ; admission serveur conservée |
| personal.ongoing | `GET /api/v1/me/ongoing/` | envelope | snapshot root | SWR | ResourceIndex + OccurrenceFactsIndex |
| personal.me | `GET /api/v1/me/` | envelope | snapshot root | SWR | identité utile + ResourceIndex |
| personal.considerations | `GET /api/v1/me/considerations/` | envelope | snapshot | contextuel | refs Interest/OpenTo/Watch/Bookmark |
| personal.collectives | `GET /api/v1/me/collectives/` | envelope | snapshot | contextuel | refs Space/Team/Group ; aucune autorité inférée |
| personal.passport | `GET /api/v1/me/passport/` | envelope | snapshot protégé | contextuel | refs présentables seulement |
| personal.resources | `GET /api/v1/me/resources/` | envelope/collection | collection | contextuel | ResourceIndex + metadata |
| resource:<id> | `GET /api/v1/me/resources/<id>/` | envelope | snapshot détail | contextuel | versions/provenance |
| discovery:<query> | `GET /api/v1/discovery/items/` | envelope query | cache reconstructible | query cache | pas de catalogue global local |
| discovery-map:<query> | `GET /api/v1/discovery/map/` | objet direct | cache reconstructible | query/volatile | représentation spatiale du pack reçu |
| watch:<id> | `GET /api/v1/discovery/watches/<id>/` | envelope | snapshot owner | contextuel | vérité Veille |
| watch-results:<id>:<query> | `GET /api/v1/discovery/watches/<id>/results/` | envelope | cache query | query | résultats server-owned |
| activity:<id> | `GET /api/v1/activities/<id>/` | envelope | snapshot détail | contextuel | ResourceIndex + refs Occurrence |
| occurrence:<id> | `GET /api/v1/occurrences/<id>/` | envelope | snapshot détail | contextuel | OccurrenceFactsIndex |
| journey:<id> | `GET /api/v1/me/journeys/<id>/` | envelope | snapshot détail | contextuel | ResourceIndex + OccurrenceFactsIndex |
| requirement:<id> | `GET /api/v1/me/journeys/<journey>/requirements/<assessment>/` | envelope | snapshot détail | contextuel | aucune décision locale |
| access-list | `GET /api/v1/me/accesses/` | envelope collection | collection | SWR/contextuel | ResourceIndex |
| access:<id> | `GET /api/v1/me/accesses/<id>/` | envelope | snapshot détail | revalidation critique | refs Activity/Occurrence |
| access-credential:<id> | `GET /api/v1/me/accesses/<id>/credential/` | envelope sensible | hors DB générale | sensitive | stockage minimal / à la demande |
| history:<context> | `GET /api/v1/me/history/` | envelope paginée | collection | reference/SWR | ResourceIndex |
| day-of:<occurrence> | `GET /api/v1/me/occurrences/<id>/day-of/` | envelope | snapshot opérationnel | volatile | faits non volatils d'Occurrence seulement |
| ops-readiness:<occurrence> | `GET /api/v1/operations/occurrences/<id>/readiness/` | objet direct | snapshot court | volatile | aucune Readiness locale |
| operations-live:<occurrence> | `GET /api/v1/operations/occurrences/<id>/live/` | objet direct | snapshot court | volatile | aucune autorité durable |
| offline-pack:<occurrence> | `GET /api/v1/operations/occurrences/<id>/offline-action-pack/` | objet versionné | snapshot borné | server_bounded | respecter fresh_until/expires_at |
| notifications | `GET /api/v1/notifications/` | pagination DRF | collection | SWR | inbox locale |
| notification:<id> | `GET /api/v1/notifications/<id>/` | objet | snapshot/détail | contextuel | navigation structurée |
| conversations | `GET /api/v1/conversations/` | objet results/count | collection | incrémental possible | updated_after |
| conversation:<id> | `GET /api/v1/conversations/<id>/` | objet direct | snapshot détail | contextuel | points server-computed |
| partners | `GET /api/v1/me/partners/` | envelope | collection/snapshot | contextuel | ResourceIndex |
| partner:<id> | `GET /api/v1/me/partners/<id>/` | envelope | snapshot détail | contextuel | owner projection |

Cette liste initiale n'interdit pas l'ajout d'une source future. Elle interdit seulement de l'ajouter sans owner, freshness, applier et raison d'usage.

---

## 7. Resource identity et source membership

Une ressource et son appartenance à une projection sont deux réalités différentes.

Exemple :

```text
Occurrence 456
```

peut apparaître simultanément dans :

```text
personal.now
personal.ongoing
journey:123
day-of:456
discovery:<query>
```

Donc :

> **Resource identity ≠ source membership.**

La conception Drift détaillée devra permettre de préserver cette relation many-to-many ou un équivalent reconstructible.

Le retrait de Journey 123 de `personal.now` signifie seulement :

> Journey 123 n'appartient plus à cette composition Maintenant.

Il ne signifie pas :

> supprimer Journey 123 du téléphone.

---

## 8. FreshnessPolicy

La fraîcheur répond à deux questions différentes :

1. puis-je encore afficher ce que je sais ?
2. puis-je agir à partir de cette connaissance sans revalidation ?

Décisions conceptuelles :

```text
FRESH
USABLE_REFRESH
STALE_DISPLAYABLE
REFRESH_REQUIRED
REVALIDATE_BEFORE_ACTION
EXPIRED
```

Les noms techniques exacts peuvent évoluer, pas leur sens.

### FRESH

Utilisable normalement.

### USABLE_REFRESH

Affichage local immédiat, refresh discret souhaité.

### STALE_DISPLAYABLE

Dernière observation encore utile si son ancienneté reste perceptible lorsque nécessaire.

### REFRESH_REQUIRED

Trop ancien pour être présenté comme état actuel.

### REVALIDATE_BEFORE_ACTION

Affichable, mais l'action critique impose une consultation owner.

Exemples : Access, Capacity concurrente, Permission/Mandate, Payment, credential validity.

### EXPIRED

Le contrat serveur interdit l'utilisation de cette copie comme état courant.

Le meilleur exemple existant est l'Offline Action Pack après `expires_at`.

### 8.1 Pas de TTL universel

La policy combine :

- `source_generated_at` ;
- `source_updated_at` lorsqu'il existe ;
- `received_at` ;
- `last_verified_online_at` ;
- `fresh_until` ;
- `expires_at` ;
- nature de la source ;
- nature de l'action.

### 8.2 generated_at

`generated_at` signifie que la projection a été composée à cet instant. Ce n'est pas une version universelle de tous ses sous-objets.

Une version/updated_at/observed_at owner-specific gagne lorsqu'elle existe.

---

## 9. Pull cycle

Cycle canonique :

1. contexte demande une source ;
2. le coordinator résout la `SyncSource` ;
3. `FreshnessPolicy.evaluate(...)` décide si le réseau est nécessaire ;
4. `MakoloApiClient` exécute ;
5. le response contract valide projection/schema/scope/forme ;
6. l'Applier applique en transaction ;
7. snapshot, memberships, indexes et SyncSource metadata convergent ensemble ;
8. l'invalidation est levée après commit réussi ;
9. Drift émet ;
10. selectors recomposent ;
11. Riverpod propage à l'UI.

Invariant :

> **Une réponse non validée ne touche jamais la base locale.**

---

## 10. Appliers

Un Applier répond à :

> **comment cette réponse serveur devient-elle de la connaissance locale cohérente ?**

Conceptuellement :

```text
Applier
├── validate
├── persist snapshot
├── update ResourceIndex
├── update OccurrenceFactsIndex lorsque légitime
├── update source memberships
├── update provenance/freshness
└── commit atomically
```

Appliers explicites recommandés :

- PersonalNowApplier ;
- PersonalOngoingApplier ;
- PersonalMeApplier ;
- ActivityDetailApplier ;
- OccurrenceDetailApplier ;
- JourneyDetailApplier ;
- AccessDetailApplier ;
- DiscoveryItemsApplier ;
- DayOfApplier ;
- NotificationApplier ;
- ConversationApplier.

Aucun `GenericProjectionNormalizer(anyJson)` ne doit interpréter arbitrairement des champs.

### 10.1 Payload partiel

- champ absent : cette projection ne se prononce pas ;
- champ présent avec `null` : cette projection affirme explicitement l'absence seulement si son contrat lui donne ce sens.

Une projection sparse ne doit pas effacer un fait plus riche qu'elle ne transporte pas.

### 10.2 Une source ne supprime que son membership

Un refresh de collection retire les memberships devenus absents de cette collection. Il ne détruit pas automatiquement la ressource ni ses autres projections.

---

## 11. Invalidation

`invalidate(sourceKey)` signifie :

> **la dernière copie peut ne plus être suffisante ; cette source doit être revalidée selon sa policy.**

Cela ne signifie pas DELETE.

Sources d'invalidation :

- mutation locale/confirmée ;
- réponse serveur ayant une conséquence sur d'autres projections ;
- push ;
- retour foreground ;
- expiration temporelle ;
- changement de session/contexte ;
- refresh utilisateur.

### 11.1 Coalescence

Une source ne doit pas lancer cinq pulls identiques parce que cinq signaux arrivent presque simultanément.

Contrat :

```text
sourceKey → one refresh in flight
```

Si une nouvelle invalidation arrive pendant le pull, la source peut rester marquée pour un nouveau refresh après completion si nécessaire.

### 11.2 Priorité de refresh

Les invalidations peuvent être classées conceptuellement :

- immediate ;
- foreground ;
- whenObserved ;
- background.

Une mutation ne déclenche pas quinze appels HTTP par défaut.

---

## 12. Push

Le push n'est jamais la source de vérité métier.

Chaîne :

```text
push
→ signal
→ invalidate owner/source
→ owner refresh
→ Applier
→ Local Kernel
→ UI
```

Interdit :

```text
push says capacity = 2
→ UPDATE local canonical capacity = 2
```

Un push peut transporter assez d'information pour router ou prioriser, mais la vérité partagée est relue auprès de l'owner lorsque nécessaire.

---

## 13. OutboxOperation

Une `OutboxOperation` représente :

> **une intention locale durable destinée à produire une conséquence chez un owner distant.**

Partie conceptuellement immuable :

```text
operation_id
profile_id
device_instance_id

owner
operation_kind

resource_kind
resource_id

intent_id
owner_idempotency_key?

payload
dependencies
sequence_group

observed_at
replay_policy
```

Partie d'exécution :

```text
state
attempts
next_retry_at
last_attempt_at?
last_error_code?
remote_confirmation_ref?
```

La forme Drift finale sera décidée lors du schéma.

### 13.1 intent_id

Identifie l'intention humaine.

### 13.2 operation_id

Identifie une opération technique Outbox.

Une intention peut nécessiter plusieurs opérations dépendantes.

### 13.3 owner_idempotency_key

Seulement lorsque l'owner possède réellement ce contrat. Pas de header d'idempotence fictif imposé à tous les endpoints.

---

## 14. Replay policies

Le socle actuel contient les bonnes familles :

```text
safe
idempotent
refetch-before-retry
no-blind-retry
```

### safe

L'owner garantit qu'un replay technique ne crée pas un second effet significatif.

### idempotent

Le serveur possède un contrat d'idempotence explicite. Un retry de la même intention réutilise la même clé.

### refetch-before-retry

Après timeout/réponse perdue, consulter d'abord l'owner pour savoir si l'effet a déjà eu lieu.

### no-blind-retry

Jamais de replay automatique après résultat ambigu. Passer en `awaiting_confirmation` ou réconciliation owner-specific.

Aucune règle globale `retry 3 times` pour POST/PATCH/DELETE.

---

## 15. Etats Outbox

Etats retenus :

```text
queued
in_flight
awaiting_confirmation
confirmed
conflict
failed
cancelled
```

Transitions principales :

```text
queued
  ↓
in_flight
  ├── confirmed
  ├── awaiting_confirmation
  ├── conflict
  └── failed
```

`awaiting_confirmation` peut devenir : confirmed, queued, conflict ou failed après réconciliation.

`conflict` ne se rejoue jamais aveuglément.

Une nouvelle décision humaine crée une nouvelle intention plutôt que de muter silencieusement l'ancienne.

---

## 16. OutboxHandler

Chaque owner possède un Handler adapté.

Responsabilités conceptuelles :

```text
OutboxHandler
├── preflight
├── execute
├── classify
└── reconcile
```

### preflight

Vérifie si l'intention a encore du sens avec la dernière connaissance disponible lorsque l'owner l'exige.

### execute

Construit la requête owner-specific.

### classify

Traduit la réponse en état Outbox et invalidations.

### reconcile

Résout un résultat ambigu en relisant l'owner.

---

## 17. Cycle complet d'une mutation

1. UI exprime une intention.
2. Use case/repository valide localement ce qui peut l'être.
3. Transaction locale crée draft/pending overlay et OutboxOperation lorsque l'action est outbox-eligible.
4. UI peut refléter un état pending sans falsifier la vérité confirmée.
5. Processor attend dépendances, sequence group et retry window.
6. Handler preflight si nécessaire.
7. Handler execute auprès de l'owner.
8. Serveur revalide autorité, état courant et invariants.
9. Handler classify.
10. Si réponse canonique complète : Applier immédiat.
11. Si reçu seulement : invalidate sources affectées puis pull.
12. Si réponse ambiguë : awaiting_confirmation + reconcile.
13. Drift/Selectors réconcilient confirmed + pending.
14. UI explique la conséquence humaine.

---

## 18. Pending local ≠ snapshot serveur

Exemple :

```text
confirmed server fact
+ pending local intent
= provisional presentation
```

Le snapshot confirmé n'est pas réécrit pour faire semblant que le serveur a déjà accepté.

Cette règle protège :

- Bookmark ;
- read state ;
- formulaires ;
- uploads ;
- réservations ;
- Journey actions ;
- autres mutations compatibles.

---

## 19. Dépendances et sequence groups

Une opération est exécutable lorsque :

```text
dependencies confirmed
AND retry window reached
AND no blocking conflict in sequence group
```

Exemple :

```text
A upload fichier
B créer JourneyArtifact
C soumettre l'élément dans le contexte owner
```

B dépend de A ; C dépend de B.

`sequenceGroup` protège l'ordre lorsque plusieurs opérations touchent une même séquence sans dépendance de résultat explicite.

---

## 20. Résultat ambigu et réconciliation

Exemple :

```text
POST réservation
→ serveur traite
→ connexion casse avant réception
```

Le mobile ne sait pas si la réservation existe.

Il ne doit ni déclarer `failed` automatiquement, ni rejouer aveuglément.

Etat :

```text
awaiting_confirmation
```

Puis :

```text
owner query
→ effet retrouvé → confirmed
→ effet absent + retry autorisé → queued/retry
→ monde changé → conflict
→ action impossible → failed
```

---

## 21. Définition d'un conflit

Une différence entre local et serveur n'est pas automatiquement un conflit UX.

Un conflit existe lorsque :

> **l'intention ne peut plus être appliquée telle quelle sans une nouvelle décision humaine ou une nouvelle interprétation.**

Exemple : place choisie disparue, alternative nécessaire.

Une Capacity corrigée par le serveur après une réservation réussie est une convergence normale, pas nécessairement un conflit.

---

## 22. Sources affectées après mutation

Chaque mutation owner-specific déclare les sources susceptibles d'être obsolètes.

Exemple conceptuel :

```text
Journey submit
→ journey:<id> immediate
→ personal.ongoing foreground
→ personal.now foreground
→ autres sources whenObserved selon contrat
```

Cette connaissance ne doit pas devenir un gigantesque switch central.

Le Handler/owner fournit ses invalidations.

---

## 23. Catalogue initial des mutations

Le catalogue ci-dessous classe les mutations déjà exposées ou démontrées dans le runtime. Il ne remplace jamais le contrat owner final.

| Mutation | API actuelle | Classe | Optimistic | Replay par défaut | Réconciliation / invalidations |
| --- | --- | --- | --- | --- | --- |
| Garder une possibilité | `PUT /api/v1/discovery/items/{family}/{id}/saved/` | B | oui | state-setting / safe à confirmer par tests owner | discovery item + considerations/me selon projections |
| Retirer une possibilité gardée | `DELETE .../saved/` | B | oui | state-setting / safe à confirmer | mêmes sources |
| Legacy bookmark Event | `POST /api/v1/discovery/bookmarks/` | B | oui | get_or_create côté serveur ; convergence explicite | Discovery legacy uniquement |
| Supprimer legacy bookmark | `DELETE /api/v1/discovery/bookmarks/{event_id}/` | B | oui | state-setting | legacy Discovery |
| Créer une Veille | `POST /api/v1/discovery/watches/` | C | draft local possible | no-blind-retry sauf contrat futur d'idempotence | watches + me/considerations si nécessaire |
| Modifier une Veille | `PATCH /api/v1/discovery/watches/{id}/` | C | possible selon champ | refetch-before-retry conseillé si ambigu | watch detail/results |
| Supprimer une Veille | `DELETE /api/v1/discovery/watches/{id}/` | C | présentation pending possible | no-blind-retry/refetch owner | watches/results |
| Notification lue | `POST /api/v1/notifications/{id}/read/` | B | oui | state-setting | notifications + unread-count |
| Toutes notifications lues | `POST /api/v1/notifications/read-all/` | B | oui | state-setting | notifications + unread-count |
| Réponse Conversation Point | `POST /api/v1/conversations/points/{id}/respond/` | C | draft oui, résultat non | owner-specific ; utiliser `client_reference` si contrat démontré | conversation detail/list/Now selon conséquence |
| Acknowledge Conversation Point | `POST /api/v1/conversations/points/{id}/acknowledge/` | B/C | oui | state-setting owner-specific | conversation detail/list |
| Répondre invitation Conversation | `POST /api/v1/conversations/invitations/{id}/respond/` | C | pending possible | no-blind-retry/refetch owner | invitations + conversation/list |
| Réutiliser Resource dans Journey | `POST /api/v1/me/resources/versions/{id}/reuse/` | C | non sur résultat final | no-blind-retry tant qu'idempotence owner non démontrée | resource detail + journey detail + requirement/readiness |
| Mark personnel | `POST /api/v1/me/mark/` | C/D | draft local uniquement | no-blind-retry par défaut | résultat owner/handoff ; aucune vérité Mark locale universelle |
| Opérations Journey/Access/Capacity/Queue | owner links exposés par projections | C/D | seulement si contrat précis | strictement owner-specific | refetch owner + roots affectées |
| Payment | owner Payment/provider | D | jamais `succeeded` localement | contrat provider/idempotence seulement | Payment/Order/Journey |
| AccessUse / passage | owner Access/Operations | D | jamais confirmé offline sans contrat terrain explicite | revalidation forte | Access + Live/Day-of |
| Recognition/Loyalty redemption | owner APIs lorsqu'exposées | C/D | résultat final non | idempotence owner seulement | owner + En cours/Now si conséquence |

### 23.1 Classes

- **A** : local uniquement, pas d'Outbox.
- **B** : état local immédiat + convergence simple avec owner.
- **C** : préparation locale possible, conséquence finale serveur.
- **D** : intrinsèquement distante ou autoritative ; aucune fausse confirmation offline.

Cette classification ne suffit jamais à elle seule à définir le replay.

---

## 24. Bootstrap

Après authentification :

```text
account.me
→ personal.now
→ personal.ongoing
→ personal.me
→ application transactionnelle des roots
→ app usable
```

Les pulls roots peuvent être parallélisés lorsque cela ne crée pas de collision de refresh token et que leur application reste transactionnelle par source.

Le bootstrap ne télécharge pas automatiquement :

- tout l'Historique ;
- toutes les Conversations ;
- tous les détails Journey ;
- tous les fichiers ;
- tout Discovery ;
- toutes les Activities.

La profondeur se construit au fil de l'usage.

---

## 25. Launch, resume et reconnect

### Launch avec DB existante

```text
ouvrir DB
→ afficher le réel local
→ évaluer freshness
→ flush outbox pertinent
→ refresh roots invalidées/stales
```

### Resume

Rafraîchir d'abord ce qui est observé et ce qui est devenu sensible au temps.

Si l'utilisateur est dans Jour J, les sources opérationnelles ont priorité. S'il est dans Moi, Operations Live n'a aucune raison d'être rafraîchi.

### Reconnect

```text
resume pending outbox
→ respecter replay policies
→ reconcile ambiguities
→ refresh invalidated sources
```

Pas de `syncEverything()`.

---

## 26. BackgroundCoordinator

Architecture :

```text
                 Sync / owner handlers
                        ↑
             BackgroundCoordinator
                        ↑
          ┌─────────────┴─────────────┐
          │                           │
foreground/resume             OS scheduler
                              Workmanager/etc.
```

Familles de travail :

- flushOutbox ;
- refresh ;
- upload ;
- download ;
- cacheMaintenance.

L'OS scheduler exécute. Il ne possède pas le cerveau de synchronisation.

Le même handler doit pouvoir être déclenché immédiatement, au resume, au reconnect ou en background.

---

## 27. Concurrence

Paralléliser les pulls indépendants pour réduire la latence est légitime.

Sérialiser lorsque l'ordre porte du sens :

- refresh token single-flight ;
- sequence group ;
- mutations dépendantes ;
- opérations sur une même ressource lorsque l'owner l'exige.

Formule :

> **Parallélisme pour la latence ; sérialisation lorsque l'ordre porte du sens.**

---

## 28. Pagination et incrémental

Aucun cursor universel.

Chaque owner conserve son contrat.

Exemples :

- DRF page/offset ;
- Discovery page/page_size ;
- Resources offset/limit ;
- Conversations `updated_after`.

Conversations constitue déjà un bon exemple de synchronisation incrémentale owner-specific.

Un refresh de première fenêtre peut invalider une continuation offset précédente lorsque l'owner ne garantit pas la stabilité.

---

## 29. Maintenant

`personal.now` reste calculé serveur.

Le mobile peut :

- présenter localement le dernier snapshot ;
- afficher un timing déterministe à partir de données déjà reçues ;
- appliquer des faits locaux utiles à la présentation.

Il ne décide pas qu'une Journey doit entrer dans Maintenant.

> **Admission dans Maintenant = serveur. Présentation de la projection reçue = mobile.**

---

## 30. Découvrir

Le serveur possède le champ global de possibilités et sa composition.

Le mobile peut, sur un pack reçu :

- afficher ;
- filtrer localement lorsque le filtre est purement local et compatible avec le contrat ;
- trier sans falsifier la sémantique owner ;
- calculer une distance à partir de coordonnées reçues ;
- cartographier.

Nouvelle intention ouverte ou besoin d'élargir le champ : serveur Discovery.

---

## 31. Jour J / Live

Le mobile peut dériver des conséquences déterministes comme temps écoulé ou distance entre coordonnées déjà connues.

Restent serveur/owner :

- Queue réelle ;
- Placement réel ;
- checkpoint partagé ;
- Access utilisable ;
- changement opérationnel ;
- Capacity ;
- position globale reçue d'une source Live ;
- Readiness opérationnelle.

L'Offline Action Pack peut être utilisé seulement dans sa fenêtre contractuelle et n'accorde aucune autorité offline implicite.

---

## 32. Erreurs réseau normalisées

Les features ne doivent pas interpréter directement des exceptions transport.

Catégories utiles :

- authentication ;
- authorization ;
- validation ;
- notFound ;
- throttled ;
- conflict / owner-specific ambiguity ;
- timeout ;
- offline / transport ;
- server ;
- schemaIncompatible ;
- cancelled.

Un HTTP 200 avec `state=waiting` reste un état métier, pas une erreur réseau.

---

## 33. Compatibilité de schéma

Si la version reçue est incompatible :

- ne pas écraser le dernier snapshot utilisable ;
- ne pas parser approximativement ;
- marquer la source incompatible ;
- empêcher les actions exigeant la nouvelle vérité ;
- demander une mise à jour client si nécessaire.

Les champs additifs compatibles restent tolérés.

---

## 34. Sécurité et confidentialité

Le Sync Core ne doit pas :

- logger des payloads sensibles complets ;
- persister des AccessCredentials complets dans la DB générale ;
- mettre des secrets dans sourceKey ou query fingerprint ;
- exposer des données privées dans push ;
- copier des données privées entre scopes ;
- considérer Membership comme autorité.

Les query keys utilisent des empreintes déterministes plutôt que le texte utilisateur brut lorsque celui-ci pourrait être sensible.

Le logout/remove-account applique le contrat de purge du Local Data Kernel.

---

## 35. Ce que le Bloc B ne crée pas côté serveur

Non retenus :

- `GET /api/v1/sync/?since=...` générique ;
- `POST /api/v1/mobile/sync/` ;
- cursor transverse Makolo ;
- changefeed viewer-aware global ;
- table serveur spécifique au moteur mobile ;
- ETag universel imposé à tous les owners ;
- WebSocket/SSE global par principe ;
- endpoint par écran Flutter.

Ces primitives ne deviendront légitimes que si l'usage réel démontre un besoin commun et mesurable.

---

## 36. Ce que le Bloc B laisse pour les blocs suivants

Le Bloc B ne choisit pas encore :

- le provider push final ;
- le scheduler OS final par plateforme ;
- la politique détaillée de fichiers/media ;
- l'upload PersonalAsset générique manquant ;
- le transport realtime spécialisé d'un futur Live ;
- la topologie native caméra/QR/maps ;
- la stratégie de deep links ;
- l'observabilité provider-specific ;
- les détails de background iOS/Android.

Il fixe les contrats auxquels ces capacités devront se brancher.

---

## 37. Conséquences pour le schéma Drift à concevoir

Le schéma détaillé devra réconcilier au minimum :

- `ProjectionSnapshots` ;
- `ResourceIndex` ;
- `SyncSources` ;
- `OutboxOperations` ;
- `LocalDrafts` ;
- `FileRecords` ;
- `OccurrenceFactsIndex` ;
- une représentation ou un équivalent reconstructible des memberships source↔resource ;
- provenance suffisante pour éviter qu'un payload sparse efface un fait plus riche.

Le Bloc B ne force pas encore le nom physique des nouvelles tables.

---

## 38. Critères de sortie avant implémentation

Avant coder Bloc B :

1. revalider `main` et les PR A2/infrastructure ;
2. vérifier le schéma Drift réellement présent ;
3. fixer les interfaces Dart finales `SyncSource`, `FreshnessPolicy`, Applier, Coordinator, Handler ;
4. fixer les migrations nécessaires ;
5. écrire les tests de pull atomique ;
6. écrire les tests absence vs null ;
7. écrire les tests de coalescence des refresh ;
8. écrire les tests refresh JWT single-flight ;
9. écrire les tests Outbox state machine ;
10. écrire les tests résultat ambigu / awaiting_confirmation ;
11. écrire les tests dependencies / sequence groups ;
12. écrire les tests replay policy par owner initial ;
13. écrire les tests restart/crash entre intent et confirmation ;
14. vérifier permissions/IDOR serveur des mutations touchées ;
15. vérifier idempotence réelle avant de déclarer une opération `idempotent` ;
16. vérifier confidentialité des logs et payloads persistés ;
17. faire un collision audit avec les PR mobiles ouvertes.

Aucun test ne doit être affaibli pour satisfaire l'architecture.

---

## 39. Décisions gelées du Bloc B

| Question | Décision |
| --- | --- |
| Network Core | `MakoloApiClient` unique |
| Transport | détail derrière le client, Dio acceptable |
| Sync globale | non |
| SyncSource | owner-scoped, pas écran-scoped |
| sourceKey | identité logique, pas URL |
| Resource vs membership | distincts |
| Freshness | policy par source/action |
| Affichage stale | possible quand honnête |
| Action critique stale | revalidation owner |
| Pull | atomique |
| Applier | explicite par contrat |
| Normalizer JSON universel | non |
| Invalidation | marque à revérifier, ne delete pas |
| Push | signal d'invalidation |
| Outbox | intention durable |
| Retry global POST | non |
| Replay | owner-specific |
| awaiting_confirmation | oui |
| Reconciliation | owner-specific |
| Conflict | seulement si nouvelle décision/interprétation nécessaire |
| Background | coordinator commun, OS exécuteur |
| Realtime global | non |
| Pagination | owner-specific |
| Maintenant local engine | non |
| Discovery global local engine | non |
| Readiness/Capacity/Authority locales | non |
| Offline authority implicite | aucune |

---

## 40. Etat GitHub lors de la consolidation

Lors de cette fermeture :

- `main = 96f3992b38afc5352c1da2572a9a9b695359a5de` ;
- PR #337 — Local Data Kernel — reste ouverte ;
- plusieurs PR mobiles A2/infrastructure restent ouvertes ;
- le document Bloc B est placé sur une branche docs-only indépendante afin de ne pas réécrire leurs fichiers runtime ;
- ces états sont historiques : toujours revérifier avant implémentation.

---

## 41. Formule finale

Le Sync & Continuity Kernel ne synchronise pas des écrans.

Il synchronise des **sources propriétaires**, conserve des **observations locales**, prépare des **intentions durables**, demande à chaque owner de décider sa conséquence, puis réconcilie le téléphone avec le réel partagé.

> **Afficher vite ce que Makolo sait déjà. Revalider ce qui peut avoir changé ailleurs. Préserver l'intention de la personne. Ne jamais transformer une hypothèse locale en vérité serveur.**

C'est la traduction infrastructurelle de :

> **« Makolo marche pour vous. »**
