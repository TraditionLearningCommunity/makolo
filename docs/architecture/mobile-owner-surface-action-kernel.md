# Makolo Mobile — Bloc E
## Owner Surfaces, Action Continuity & Domain Depth Kernel

**Statut : conception figée avant implémentation**  
**Date : 2026-09-28**  
**Dépôt : TraditionLearningCommunity/makolo**  
**Base observée : main @ ce1525075b61a7255e2a33ee8779af8a08c40008**

---

## 1. Objet

Le Bloc E ferme la conception des profondeurs métier consommables par le mobile après les fondations A–D.

Les Blocs précédents ont fixé :

- **A** — ce que le téléphone peut conserver et réutiliser localement ;
- **B** — comment ces données et intentions se synchronisent avec les owners serveur ;
- **C** — comment les fichiers et médias sont acquis, transférés et conservés ;
- **D** — comment le téléphone s’intègre aux capacités natives, au Push, aux entrées OS et aux surfaces Ambient.

Le Bloc E répond maintenant à une autre question :

> **Comment remplacer les profondeurs mobiles encore génériques ou placeholders par de vraies surfaces owner-backed, sans reconstruire les systèmes métier côté Flutter ?**

Principe :

> **Le serveur décide, calcule et autorise. Le mobile reçoit, conserve, présente, prépare l’intention et appelle le bon owner.**

Le Bloc E n’est ni une refonte backend, ni une copie locale des domaines, ni un framework métier mobile.

---

## 2. Etat runtime observé

Au main audité :

- le routeur mobile expose déjà Now, Discover, En cours, Moi, Mark, Conversations et Notifications ;
- les routes profondes existent déjà pour Journey, Activity, Occurrence, Access, Dossier, Project et Group ;
- plusieurs routes profondes aboutissent encore à un écran secondaire générique ;
- PersonalRepository ne lit actuellement que personal.now, personal.ongoing et personal.me ;
- le schéma Drift sait déjà stocker un resourceKey, mais ProfileStore n’expose aujourd’hui que les snapshots racine avec resourceKey vide ;
- ResourceIndex, SyncSources, OutboxOperations, LocalDrafts et FileRecords existent déjà ;
- le serveur expose déjà la majorité des profondeurs owner-backed nécessaires.

Le Bloc E ferme donc essentiellement :

~~~
root projection
→ owner detail
→ owner action
→ local continuity
→ canonical refresh
~~~

sans inventer un second moteur métier.

---

# 3. Les quatre cycles du Bloc E

Le Bloc E est divisé en quatre cycles :

1. **E1 — Navigation owner-backed & Detail Registry**
2. **E2 — Journey, Requirements, Forms & Resources**
3. **E3 — Access, Historique, Jour J & Operations**
4. **E4 — Dossier, Project, Conversations & Capital personnel secondaire**

Ces cycles partagent les primitives A–D, mais chaque surface conserve son owner.

---

# 4. E1 — Navigation owner-backed & Detail Registry

## 4.1 Problème

Le routeur sait déjà construire des destinations Flutter comme :

~~~
/journeys/:id
/activities/:id
/occurrences/:id
/accesses/:id
/dossiers/:id
/projects/:id
/groups/:id
~~~

Mais une route n’est pas encore une expérience réelle.

La profondeur doit savoir :

- quelle API owner interroger ;
- quelle projection locale lire ;
- quelle freshness appliquer ;
- quels links et capabilities suivre ;
- comment restaurer la navigation ;
- comment réagir si le scope ou l’autorité a changé.

## 4.2 Règle de résolution

Le mobile ne transforme jamais une route Flutter en autorité.

~~~
StructuredDestination
        ↓
route locale
        ↓
owner repository
        ↓
snapshot local éventuel
        ↓
refresh owner
        ↓
server revalidation
        ↓
detail presentation
~~~

Une route peut légitimement finir en 404, 403, indisponible ou expiré sans que le client tente de contourner le serveur.

## 4.3 Kind / id / link

Identité canonique :

~~~
kind + id
~~~

Le link serveur reste le handoff préféré lorsqu’il est fourni.

Le client ne doit pas :

- parser une URL HTML pour reconstruire une permission ;
- déduire un owner depuis un label ;
- utiliser le nom de route Flutter comme clé métier ;
- inventer une route owner lorsque le serveur n’en fournit pas.

## 4.4 Detail Registry

Un registre technique de profondeurs est légitime côté mobile.

~~~
DetailDefinition
├── resourceKind
├── sourceKey(resourceId)
├── owner
├── remote loader
├── parser
├── applier
├── freshness policy
├── sensitivity policy
├── presentation mapper
└── supported actions
~~~

Il évite un routeur contenant des dizaines de décisions réseau. Il ne devient pas un catalogue métier universel.

## 4.5 Exploiter resourceKey

ProjectionSnapshots possède déjà :

~~~
projectionKind
resourceKey
~~~

Décision :

> **Les profondeurs owner-backed utilisent le resourceKey existant avant d’ajouter une table métier locale complète.**

Exemples :

~~~
projectionKind = personal.journey.detail
resourceKey    = <journey-id>

projectionKind = personal.access.detail
resourceKey    = <access-id>

projectionKind = occurrence.detail
resourceKey    = <occurrence-id>
~~~

Conséquences :

- étendre ProfileStore et les repositories pour lire/observer kind + resourceKey ;
- aucune migration Drift requise uniquement pour cela ;
- une migration future n’est justifiée que par une requête locale réelle.

## 4.6 Activity

Serveur existant :

~~~
GET /api/v1/activities/<id>/
projection = activity.detail
~~~

Le serveur fournit identity, representation, owner, state, occurrences, capacity, availability, personal_relation, capabilities et links.

Le mobile affiche, conserve un snapshot, alimente ResourceIndex et peut enrichir un index Occurrence légitime. Il ne recalcule ni Capacity ni availability.

## 4.7 Occurrence

Serveur existant :

~~~
GET /api/v1/occurrences/<id>/
projection = occurrence.detail
~~~

Le mobile réutilise timing, place, Activity reference, état reçu, links et capabilities. Il ne dérive jamais une autorité opérationnelle de cette profondeur.

## 4.8 Navigation retour

Chaque profondeur préserve son origine réelle :

~~~
Maintenant → Journey → retour → Maintenant
En cours → Access → retour → En cours
Historique → Journey → retour → Historique
Discover → Activity → Occurrence → retour → Activity → Discover
~~~

Le retour restaure autant que possible scroll, query, filtres, carte, onglet et contexte précédent.

## 4.9 Décision E1

A faire côté app :

- resource-keyed projection reads ;
- detail repository registry ;
- owner-backed detail loaders ;
- canonical route mapping ;
- state restoration ;
- UX 404/403/unavailable.

A faire côté serveur :

- rien de structurel pour Activity, Occurrence, Journey, Access, Dossier et Project déjà exposés.

Aucune nouvelle table métier locale n’est imposée par E1.

---

# 5. E2 — Journey, Requirements, Forms & Resources

## 5.1 Journey comme profondeur d’action

Serveur :

~~~
GET /api/v1/me/journeys/<id>/
projection = personal.journey.detail
~~~

Le payload contient déjà identity, representation, state, readiness, requests, requirements, forms, activity, occurrence, payment, access, resources, capabilities et links.

> **Le mobile n’a aucun Journey Engine.**

Il ne recalcule pas readiness, blocker, waiting, satisfaction Requirement, transition Journey, validité Access ou état Payment.

## 5.2 Readiness

Le serveur expose déjà ready, actor_interventions, waiting, blockers et next.

Le mobile peut choisir une hiérarchie visuelle, regrouper la présentation, afficher une action principale et indiquer un état ancien lorsque la freshness l’exige.

Il ne reconstruit pas une Readiness depuis les sous-objets et ne convertit pas un document local en Requirement satisfait.

## 5.3 Requirements

Serveur :

~~~
GET /api/v1/me/journeys/<journey-id>/requirements/<assessment-id>/
projection = personal.journey.requirement.detail
~~~

Le serveur fournit requirement, assessment, ways_to_satisfy, capabilities et links.

assessment.consequence est déjà calculé côté serveur.

> **Aucun modèle local global Requirement n’est requis par défaut.**

Un snapshot détail suffit tant qu’aucune requête locale transverse ne justifie davantage.

## 5.4 Forms

APIs existantes :

~~~
GET  /api/v1/questionnaires/requests/
GET  /api/v1/questionnaires/requests/<id>/
POST /api/v1/questionnaires/requests/<id>/save/
POST /api/v1/questionnaires/requests/<id>/submit/
~~~

Le serveur fournit schema de questions, types, contraintes, choix, réponse existante et état du FormRequest.

Le mobile peut posséder un draft local.

~~~
FormRequest owner
        ↓
local draft
        ↓
save owner
        ↓
server validation
        ↓
submit owner
        ↓
Journey / Requirement refresh
~~~

## 5.5 Validation Forms

Le client peut faire un préflight UX sur required, min/max length, number, date et choices.

La validation serveur reste autoritative. Le client ne copie pas des règles serveur non transportées explicitement.

## 5.6 Retry Forms

Le runtime actuel n’expose pas une idempotency key générique pour save ou submit.

### Save

- draft local conservé ;
- tentative serveur ;
- résultat ambigu → refetch request avant répétition lorsque nécessaire.

### Submit

- conséquence terminale ;
- pas de blind retry ;
- résultat ambigu → refetch owner ;
- le mobile ne marque jamais submitted uniquement parce que la requête a quitté l’appareil.

## 5.7 Journey Resources

Serveur :

~~~
GET /api/v1/preparation/journeys/<journey-id>/resources/
~~~

La collection expose text, URL, file, version, visibility et occurrence.

Le mobile peut lire, présenter, conserver metadata et télécharger si le contrat de téléchargement est réellement consommable par le client natif.

### Gap détecté

Le download_url observé pour une Resource FILE pointe vers la route preparation:resource-download, pas vers un contrat API versionné explicitement mobile/JWT.

Décision :

> **Avant d’annoncer le téléchargement Journey Resource natif comme fermé, vérifier puis exposer si nécessaire une vraie route owner API authentifiable par le client mobile.**

Flutter ne doit pas poster ou naviguer dans une page Web comme contournement.

## 5.8 PersonalAsset

Serveur :

~~~
GET  /api/v1/me/resources/
GET  /api/v1/me/resources/<id>/
GET  /api/v1/me/resources/versions/<id>/download/
POST /api/v1/me/resources/versions/<id>/reuse/
~~~

Le serveur conserve versions, provenance, sensitivity, validité, owner et reuse vers JourneyArtifact.

Reuse garde explicitement :

~~~
satisfied_by_reuse = false
decision_owner = requirements_readiness
~~~

Ce point reste visible dans le contrat mobile.

## 5.9 Gap PersonalAsset création/version

Comme fixé au Bloc C :

- services serveur présents ;
- vraie API mobile de création/nouvelle version non démontrée.

A ajouter au bon owner :

- create PersonalAsset ;
- add PersonalAsset version.

Pas de /api/v1/mobile/files/ générique.

## 5.10 JourneyArtifact

Pipeline :

~~~
capture/import
→ FileRecord
→ Outbox owner operation
→ JourneyArtifact API
→ server validation
→ Journey refresh
→ Requirement refresh
~~~

Gap Bloc C confirmé :

> **API owner JourneyArtifact mobile consommable à exposer.**

Le fichier n’accorde aucune satisfaction Requirement par lui-même.

## 5.11 Décision E2

Serveur réutilisé :

- Journey detail ;
- Requirement detail ;
- Forms read/save/submit ;
- Journey resources ;
- PersonalAsset read/detail/download/reuse.

Serveur à compléter :

- Journey Resource FILE download API native/JWT si la route actuelle est insuffisante ;
- PersonalAsset create/version API ;
- JourneyArtifact create/version API.

Mobile à construire :

- Journey detail repository/surface ;
- Requirement detail ;
- Form renderer owner-driven ;
- LocalDraft integration ;
- no-blind-retry submit ;
- Resource list/view/download ;
- PersonalAsset detail/reuse ;
- FileRecord/Outbox integration.

---

# 6. E3 — Access, Historique, Jour J & Operations

## 6.1 Access

Serveur :

~~~
GET /api/v1/me/accesses/
GET /api/v1/me/accesses/<id>/
~~~

Le serveur distingue beneficiary et purchased_for_other. Le mobile ne confond pas buyer et beneficiary.

## 6.2 Access ≠ AccessCredential

~~~
Access = droit
AccessCredential = représentation / secret
AccessUse = observation de l’usage
~~~

Le détail Access normal n’embarque pas le secret.

Credential :

~~~
GET /api/v1/me/accesses/<id>/credential/
projection = personal.access.credential
~~~

## 6.3 Credential

Le credential est privé, no-store HTTP, sensible et présenté seulement lorsque le serveur l’autorise.

Décision mobile :

- chargement à la demande ;
- aucun payload secret dans ResourceIndex ;
- pas de persistance par défaut dans ProjectionSnapshots générale ;
- mémoire ou stockage local protégé uniquement si une expérience validée le justifie ;
- aucun log/crash breadcrumb contenant le payload.

Le mobile ne valide pas lui-même le droit.

## 6.4 Historique

Serveur :

~~~
GET /api/v1/me/history/
projection = personal.history
~~~

Sources canoniques : Journey et Access.

Ce n’est pas un audit log, Notifications, Domain Events ou une timeline de clics.

Le payload fournit occurred_at, outcome, activity, occurrence et canonical detail link.

Le mobile peut donc construire un historique local-first sans créer un domaine History.

## 6.5 Jour J

Serveur :

~~~
GET /api/v1/me/occurrences/<id>/day-of/
projection = personal.occurrence.day_of
~~~

Il compose déjà Occurrence + participant-safe Operations + beneficiary Access.

Le serveur fournit situation, timing, spatial, access, queue, placement, checkpoints, readiness, completion, capabilities et links.

Le mobile ne reconstruit pas cette situation.

## 6.6 Vérité spatiale

Jour J distingue planned, estimated, observed et unknown.

Le téléphone ne transforme pas le GPS device en vérité serveur de présence physique automatiquement.

Une position device peut enrichir une expérience locale de carte ou distance, mais :

> **device location ≠ attendance ≠ checkpoint ≠ AccessUse**

## 6.7 Operations Live

Serveur :

~~~
GET /api/v1/operations/occurrences/<id>/live/
GET /api/v1/operations/occurrences/<id>/readiness/
~~~

Le serveur résout la perspective et calcule phase, access usable, placement, checkpoint, queue position, capacity, spatial context, operational readiness et next_action.

Le mobile affiche ces résultats.

## 6.8 Queue participant

APIs :

~~~
GET  /api/v1/operations/occurrences/<id>/queues/me/
POST /api/v1/operations/queues/<queue-id>/entries/me/
POST /api/v1/operations/queue-entries/<entry-id>/me/cancel/
~~~

Le self-entry accepte client_reference.

Décision :

- client_reference stable pour la même intention ;
- pas de queue position inventée localement ;
- après mutation, refresh Jour J / Live / queue owner ;
- pending local distinct du statut serveur.

## 6.9 Checkpoints et Placement

Participant :

~~~
GET /api/v1/operations/occurrences/<id>/checkpoints/me/
GET /api/v1/operations/occurrences/<id>/placements/me/
~~~

Les mutations checkpoint/placement restent principalement operator-owned.

> **Le mobile personnel participant n’expose pas des mutations opérateur simplement parce que les routes existent.**

## 6.10 Offline Action Pack

Serveur :

~~~
GET /api/v1/operations/occurrences/<id>/offline-action-pack/
~~~

Contrat :

~~~
schema = operations.offline_action_pack
schema_version = 1
fresh_until
expires_at
stale
expired
offline_data_grants_authority = false
server_revalidation_required = true
~~~

Le mobile peut l’utiliser pour lecture de continuité.

Il ne peut pas en déduire droit d’entrée, consommation de credential, allocation Capacity, décision Queue, Permission/Mandate ou Payment réussi.

## 6.11 Mode opérationnel personnel

~~~
Journey / Access
       ↓
     Jour J
       ↓
Operations Live si pertinent
~~~

Jour J ne devient pas un sixième onglet permanent. Live ne devient pas un feed.

## 6.12 Décision E3

Serveur réutilisé :

- Access list/detail ;
- credential ;
- Historique ;
- Jour J ;
- Operations Readiness ;
- Operations Live ;
- Offline Action Pack ;
- participant Queue ;
- participant Checkpoints ;
- participant Placement.

Serveur à compléter :

- aucun nouveau moteur personnel nécessaire ;
- les gaps futurs restent owner-specific et doivent être démontrés.

Mobile à construire :

- Access list/detail ;
- credential presentation protégée ;
- History repository/surface ;
- Day-of repository/surface ;
- Operations Live viewer ;
- participant queue join/cancel ;
- offline-pack persistence policy ;
- freshness/revalidation UX.

---

# 7. E4 — Dossier, Project, Conversations & capital personnel secondaire

## 7.1 Dossier

Serveur :

~~~
GET /api/v1/objectives/dossiers/<id>/
projection = objective.dossier.detail
~~~

Il expose objective, lifecycle, deadline, readiness, visible_items, visible_dependencies, personal_responsibilities, actor_interventions et links.

Le serveur calcule resolve_dossier_readiness.

Le mobile ne construit pas un Dossier task manager.

## 7.2 Project

Serveur :

~~~
GET /api/v1/objectives/projects/<id>/
projection = objective.project.detail
~~~

Il expose horizon, lifecycle, visible_dossiers et links.

Règle :

~~~
Dossier = objectif actif composé
Project = horizon durable
~~~

Le mobile préserve cette différence.

## 7.3 Mutations Dossier / Project

Les détails actuels sont principalement de lecture.

> **Ne pas inventer des actions d’édition mobile simplement parce que l’écran existe.**

Une mutation ne devient visible que si une API owner et une capability réelle existent.

## 7.4 Conversations

Serveur :

~~~
GET  /api/v1/conversations/
GET  /api/v1/conversations/<id>/
POST /api/v1/conversations/points/<id>/respond/
POST /api/v1/conversations/points/<id>/acknowledge/
GET  /api/v1/conversations/invitations/
POST /api/v1/conversations/invitations/<id>/respond/
~~~

Le serveur fournit purpose, lifecycle, context, attention_count, latest_result, all_clear, points, can_respond, attention_reason, section et resolution_summary.

Le mobile ne recalcule pas ces conséquences.

## 7.5 Conversations ≠ chat générique

Un Point peut représenter information, action attendue, acknowledge, réponse, formulaire ou résolution.

La surface mobile suit le modèle réel.

Ne pas transformer le domaine en message bubbles, typing indicator, presence, read receipts et chat feed générique sans besoin démontré.

## 7.6 Réponse à un Point

submit_point_response accepte client_reference et le serveur possède une idempotence réelle pour la même réponse/sujet.

Décision :

- une intention locale crée un client_reference stable ;
- retry technique de la même intention réutilise la même référence ;
- réponse différente = nouvelle intention ;
- ne pas changer silencieusement la valeur sous la même référence.

C’est un bon candidat Outbox owner-specific.

## 7.7 Acknowledge

L’acknowledge est convergent serveur-side.

Il peut être représenté localement en pending puis confirmé.

Après action, conversation detail, conversation list et éventuellement personal.now peuvent être invalidés.

## 7.8 Invitations Conversation

Le serveur renvoie l’état courant si l’invitation n’est plus pending.

Le mobile peut afficher pending local, puis refetch après résultat ambigu.

## 7.9 Notifications

Le Bloc D a fermé le transport Push. E ferme la surface Notification :

~~~
GET  /api/v1/notifications/
GET  /api/v1/notifications/unread-count/
GET  /api/v1/notifications/<id>/
POST /api/v1/notifications/<id>/read/
POST /api/v1/notifications/read-all/
~~~

La navigation structurée serveur est canonique.

Le mobile peut conserver une collection bornée, représenter pending-read, suivre navigation et ne parse pas action_url pour reconstruire une identité.

## 7.10 Passport, Groups, Partners

### Passport

Serveur :

~~~
GET /api/v1/me/passport/
~~~

Projection de présentation, pas seconde identité Profile.

Le partage mobile n’invente pas un ShareEnvelope tant qu’un owner API réel n’est pas livré.

### Group

Serveur :

~~~
GET /api/v1/me/collectives/groups/<id>/
~~~

Le serveur distingue Membership et authority.

Le mobile affiche relationship, capabilities et owner-backed authority.

Membership ne devient jamais Permission/Mandate.

Certaines actions de gestion restent non exposées en API mobile : Flutter ne poste pas des formulaires Web.

### Partner

Les APIs personnelles Partner existent. Une relation Partner n’accorde pas une autorité Space.

## 7.11 Recognition / Loyalty

Ces profondeurs restent owner-specific.

Le mobile peut les consommer lorsqu’elles entrent dans Moi.

Ne pas créer solde Makolo global, wallet universel ou économie commune Recognition + Loyalty + Payment.

## 7.12 Décision E4

Serveur réutilisé :

- Dossier ;
- Project ;
- Conversations ;
- Notifications ;
- Passport ;
- Group ;
- Partner ;
- Recognition ;
- Loyalty.

Serveur à compléter seulement si scénario démontré :

- Group management owner APIs mobiles ;
- Passport share owner API ;
- éventuelles owner actions Dossier/Project réellement nécessaires.

Mobile à construire :

- Dossier detail ;
- Project detail ;
- Conversations list/detail/actions ;
- Notifications list/detail/read ;
- Passport presentation ;
- Group/Partner/Recognition/Loyalty depths selon navigation Moi.

---

# 8. Matrice générale : existe / manque / mobile

| Domaine/surface | Serveur déjà présent | Gap serveur réel | Travail mobile |
|---|---|---|---|
| Activity | detail | aucun | détail + cache snapshot |
| Occurrence | detail | aucun | détail + réutilisation timing/place |
| Journey | detail + readiness + forms links | aucun moteur manquant | surface complète owner-driven |
| Requirement | detail + consequence | aucun | lecture + handoff |
| Forms | read/save/submit | pas d’idempotence submit générique | drafts + validation UX + refetch |
| Journey Resources | list | download natif/JWT à confirmer | liste/viewer/download |
| PersonalAsset | list/detail/download/reuse | create/version API | library mobile |
| JourneyArtifact | services/Web | create/version API mobile | capture/upload via Bloc C |
| Access | list/detail | aucun | droit + relation |
| AccessCredential | protected detail | aucun | présentation sensible |
| Historique | personal.history | aucun | collection locale bornée |
| Jour J | personal.day_of | aucun | surface contextuelle |
| Operations Live | live/readiness | aucun | viewer par refresh |
| Queue participant | join/cancel/read | aucun | actions owner avec client_reference |
| Checkpoint participant | read | aucun | progression reçue |
| Placement participant | read | aucun | présentation reçue |
| Offline Action Pack | oui | aucun | continuité bornée |
| Dossier | detail | mutations seulement si besoin | profondeur |
| Project | detail | mutations seulement si besoin | profondeur |
| Conversations | list/detail/respond/ack/invite | attachments Bloc C | expérience Point-based |
| Notifications | list/detail/read | Push traité D | inbox + navigation |
| Passport | read | share API si besoin | projection privée |
| Group | read detail | management APIs mobiles | relation/capabilities |
| Partner | read | selon actions owner | profondeur |
| Recognition/Loyalty | owner APIs | aucun moteur transversal | surfaces owner-specific |

---

# 9. Règles de persistance E

## 9.1 Snapshot avant table spécialisée

Ordre de préférence :

~~~
ProjectionSnapshot
→ ResourceIndex
→ index structuré seulement si requête locale prouvée
→ table métier locale seulement en dernier recours
~~~

E n’introduit pas automatiquement Journey table, Access table, Requirement table, Dossier table, Project table ou Conversation table complète.

## 9.2 resourceKey comme clé de profondeur

Le schéma actuel permet déjà une clé de ressource.

Une profondeur non racine ne force pas une nouvelle migration uniquement pour avoir son snapshot.

## 9.3 Drafts

LocalDrafts est approprié pour :

- Form ;
- Conversation Point text response ;
- Mark ;
- préparation de contenu owner-safe ;
- metadata de capture avant upload.

Il n’est pas un domaine Document ou Message.

## 9.4 Données sensibles

Ne pas persister dans la DB générale :

- AccessCredential payload ;
- QR secret ;
- Payment secrets ;
- Push token ;
- JWT ;
- secrets de partage ;
- fichiers sensibles eux-mêmes.

---

# 10. Freshness par profondeur

## Faible risque

Exemples : Project horizon, historique passé, title Activity, Resource metadata.

## Changeable

Exemples : Journey state, Form request state, Conversation point, Dossier readiness.

## Critique

Exemples : Access usable, credential presentability, Queue position, Capacity, Placement Live, Operations next action, Payment.

Action critique :

~~~
revalidate owner
~~~

---

# 11. Capabilities et actions

> **Un enum reçu n’autorise jamais une action par lui-même.**

Le mobile préfère :

~~~
capability
+
owner link / known owner endpoint
+
freshness sufficient
~~~

et le serveur revalide toujours.

Une capability sans API consommable mobile ne produit pas un bouton mort.

---

# 12. Error handling

Le Network Core normalise les formes historiques :

~~~
{"error": ...}
{"detail": ...}
{"errors": ...}
field errors
404 / 403 / 204
~~~

Les écrans ne connaissent pas ces différences de transport.

Catégories utiles :

- authentication ;
- authorization ;
- notFound ;
- validation ;
- conflict ;
- unavailable ;
- timeout ;
- offline ;
- schemaIncompatible ;
- server.

Un état métier waiting, blocked ou unknown reste du contenu, pas une erreur.

---

# 13. Invalidation après actions

### Form submit

~~~
form request
→ journey:<id>
→ requirement:<id> si concerné
→ personal.ongoing
→ personal.now
~~~

### Resource reuse

~~~
resource detail
→ journey:<id>
→ requirement/readiness
→ personal.ongoing
~~~

### Queue join/cancel

~~~
queue owner
→ day-of:<occurrence>
→ operations-live:<occurrence>
~~~

### Conversation response

~~~
conversation:<id>
→ conversations
→ personal.now si le point alimentait Maintenant
~~~

### Notification read

~~~
notifications
→ unread-count
~~~

Cette connaissance appartient aux handlers owners, pas à un switch global central.

---

# 14. UX de continuité

Chaque profondeur respecte :

~~~
local snapshot first
+ background refresh
+ content preserved during refresh
+ pending separate from confirmed
+ retry local when safe
+ no full-screen spinner if usable local state exists
~~~

La personne ne perd pas sa position parce qu’un refresh a commencé.

---

# 15. Ce que le Bloc E ne crée pas

Ne pas créer :

- Journey Engine mobile ;
- Requirement Engine mobile ;
- Readiness mobile ;
- Access Wallet universel ;
- History domain ;
- DayOf domain ;
- Operations mobile parallèle ;
- Dossier task manager ;
- Project task manager ;
- chat générique ;
- Share domain générique ;
- Group authority locale ;
- notification-as-truth ;
- table locale par endpoint ;
- route Flutter comme autorité ;
- capability comme autorisation durable ;
- mutation mobile non supportée par un owner API.

---

# 16. Changements serveur à ouvrir pendant l’implémentation

Les gaps actuellement démontrés sont limités.

## Priorité 1

1. **PersonalAsset create/version API**
2. **JourneyArtifact create/version API**
3. **Journey Resource FILE download API native/JWT si la route actuelle n’est pas suffisante**

## Priorité 2 — seulement si la surface entre réellement dans le lot

4. **Conversation Attachment API** — déjà Bloc C
5. **Group management APIs mobiles**
6. **Passport share API**

Pas de migration métier générique pour E.

---

# 17. Changements mobile structurants

E exige probablement :

1. ProfileStore capable de lire/observer kind + resourceKey ;
2. repository limité pour snapshots owner-backed ou repositories spécialisés ;
3. Detail Registry ;
4. source definitions B pour les profondeurs ;
5. parsers explicites par API ;
6. presentation models ;
7. LocalDrafts pour Form/Conversation ;
8. owner invalidation sets ;
9. private credential boundary ;
10. routes réelles à la place des placeholders.

Le schéma Drift actuel possède déjà la plupart des primitives.

---

# 18. Ordre d’implémentation recommandé

## E-I — Infrastructure de profondeurs

~~~
resource-keyed store
→ source registry
→ repository patterns
→ detail route shell
→ error/freshness contract
~~~

## E-II — Journey action chain

~~~
Journey
→ Requirement
→ Form
→ Resources
→ PersonalAsset reuse
~~~

Ce premier parcours prouve snapshot, draft, mutation, invalidation, refetch et fichier.

## E-III — Access / Day-of

~~~
Access
→ credential
→ Jour J
→ Operations Live
→ queue join/cancel
~~~

Ce parcours prouve fraîcheur et sensibilité.

## E-IV — Secondary owner depths

~~~
Historique
Dossier
Project
Conversations
Notifications
Passport / Group / Partner
~~~

---

# 19. Parallélisme

Deux développeurs peuvent avancer si les surfaces sont réellement indépendantes.

### Lane E-A

~~~
Journey
Requirements
Forms
Resources
~~~

### Lane E-B

~~~
Access
History
Day-of
Operations
~~~

L’orchestrateur garde ProfileStore, SyncSource registry, route registry, shared design components, migrations Drift et common repositories.

Ne pas laisser deux lanes réécrire simultanément app/router.dart, providers.dart ou le schéma DB.

---

# 20. Tests de conception attendus

## Store

- snapshot root + resourceKey ;
- absence cross-resource ;
- profile isolation ;
- schema incompatible ;
- stale snapshot preserved.

## Journey

- server readiness unchanged ;
- waiting ≠ blocker ;
- form action seulement si capability ;
- submit ambiguous → refetch ;
- Resource reuse ne satisfait pas Requirement.

## Access

- buyer ≠ beneficiary ;
- credential 404 non présentable ;
- secret absent des logs/store général ;
- stale Access revalidated avant action.

## Historique

- canonical Journey/Access links ;
- pagination ;
- pas de Notifications dans History.

## Jour J

- current_position unknown reste unknown ;
- no local queue position ;
- offline pack expiry respected ;
- live handoff uniquement si capability.

## Conversations

- client_reference stable retry ;
- different response ≠ same intent ;
- acknowledge convergence ;
- can_respond server-owned.

## Navigation

- origin restoration ;
- stale deep link 404 ;
- logout/login autre Profile ;
- notification → owner detail ;
- no cross-profile cache leak.

---

# 21. CI impact-based

- parsers/repositories Dart → tests Dart/Flutter ciblés ;
- Drift query/migration → codegen + migration tests ;
- widget owner detail → widget/golden ciblés ;
- router/deep-link → navigation tests ;
- backend owner gap → Django tests + migration check si modèle changé ;
- files/media mutation → Bloc C tests + Android build seulement si plugin/native touché ;
- docs-only → pas de build inutile.

---

# 22. Collision audit au moment de la fermeture E

main observé :

~~~
ce1525075b61a7255e2a33ee8779af8a08c40008
Docs — freeze mobile Bloc D native integration kernel (#352)
~~~

La PR mobile ouverte la plus directement pertinente observée est #351 :

~~~
Mobile — close device feedback on launch, onboarding and guest search
~~~

Elle touche surtout launch, onboarding, guest, auth et le formatter workflow. Elle ne modifie pas actuellement les profondeurs E principales.

Le risque de collision documentaire E est faible.

Avant implémentation E, revalider les branches/PR mobiles.

---

# 23. Décisions figées du Bloc E

| Sujet | Décision |
|---|---|
| Owner business logic | serveur |
| Route Flutter | navigation uniquement |
| Detail persistence | snapshot kind + resourceKey d’abord |
| Tables métier locales | seulement si requête locale démontrée |
| Journey engine local | non |
| Readiness locale | non |
| Requirement decision locale | non |
| Form draft | oui |
| Form validation client | préflight seulement |
| Form submit blind retry | non |
| PersonalAsset reuse | owner API, ne satisfait pas Requirement |
| Credential | frontière sensible séparée |
| Access stale action | revalidation |
| Historique | projection Journey/Access, pas domaine |
| Jour J | projection contextuelle, pas sixième onglet |
| Operations Live | serveur calcule |
| Queue position | serveur |
| Offline Action Pack | lecture bornée, aucune autorité |
| Dossier | objectif actif composé |
| Project | horizon durable |
| Conversation | Points owner-driven, pas chat générique |
| Notification navigation | structured navigation |
| Membership | n’accorde pas authority |
| Group management | pas sans vraie owner API |
| Retour | origine + contexte restaurés |
| Placeholder route | remplacé seulement par profondeur utile réelle |

---

# 24. Critères de sortie avant implémentation

Le Bloc E est prêt pour implémentation lorsque :

1. le main courant est revalidé ;
2. les API owners E sont revalidées ;
3. ProfileStore resource-keyed est spécifié ;
4. les sources B de profondeurs sont enregistrées ;
5. la politique de persistance du credential est fixée ;
6. les drafts Forms/Conversations sont branchés conceptuellement sur LocalDrafts ;
7. les invalidations owner par action sont figées ;
8. les trois gaps serveur prioritaires sont assignés à leur owner ;
9. aucune route Web n’est utilisée comme mutation native de contournement ;
10. les tests IDOR/freshness/retry/profile isolation sont prêts ;
11. le collision audit router/providers/DB est refait ;
12. aucun F/G n’est anticipé par une abstraction prématurée.

---

# 25. Ce que E laisse volontairement à F et G

Le Bloc E ferme les profondeurs et actions métier mobiles.

Il ne doit pas absorber les prochains blocs.

Les sujets transverses restant à traiter séparément incluent notamment :

- hardening opérationnel complet ;
- observabilité/crash/performance ;
- stratégie de tests end-to-end mobile complète ;
- release engineering ;
- qualité appareil réel ;
- sécurité finale des builds ;
- politique de livraison ;
- ordre global d’implémentation et fermeture programme.

Ils seront traités dans F/G selon leur propre objectif.

---

# 26. Résumé final

Après A–D, Makolo Mobile possède les fondations techniques nécessaires.

Le Bloc E fixe comment les vraies profondeurs métier doivent maintenant les utiliser :

~~~
Root projection
   ↓
owner identity
   ↓
local snapshot
   ↓
owner detail
   ↓
user intent
   ↓
draft / outbox si approprié
   ↓
server decision
   ↓
canonical refresh
   ↓
continuity
~~~

Règle finale :

> **Le mobile ne reconstruit pas la signification du système. Il rend immédiatement accessible ce que le serveur a décidé, permet de préparer ce qui peut l’être localement, appelle le bon owner pour agir, puis réconcilie l’expérience avec la vérité canonique.**

C’est la profondeur nécessaire pour que :

> **« Makolo marche pour vous. »**
