# Makolo Mobile — Bloc E
## Action Continuity & Owner-backed Depths Kernel

**Statut : conception figée avant implémentation**  
**Date : 2026-09-28**  
**Dépôt : TraditionLearningCommunity/makolo**  
**Base runtime auditée : main@ce1525075b61a7255e2a33ee8779af8a08c40008**  
**Branche de conception : docs/mobile-e-f-g-conception**

---

## 1. Objet

Le Bloc E ferme la conception des **profondeurs owner-backed** nécessaires pour transformer le shell personnel A2 en application Makolo capable d'accompagner réellement une action jusqu'à sa continuité, son Jour J et sa conséquence durable.

Le Bloc E correspond principalement à **A3 — Action Continuity** du programme mobile.

Il couvre :

1. **E1 — Journey, Requirements, Readiness et Forms** ;
2. **E2 — Access, AccessCredential, Resources, JourneyArtifact et Preparation Resources** ;
3. **E3 — Dossier, Project, Historique et Conversations** ;
4. **E4 — Occurrence, Jour J, Operations Live et faible connectivité sans autorité offline** ;
5. **E5 — autres profondeurs personnelles owner-backed nécessaires à Moi et à la continuité : Passeport, Groupes, Recognition, Loyalty et Partner**.

Le principe fondamental reste :

> **Le serveur calcule les systèmes, décide les conséquences métier, arbitre l'autorité et expose des projections, capabilities et links. Le mobile reçoit, conserve, présente, prépare localement ce qui peut l'être et demande au bon owner d'agir.**

Le Bloc E ne crée donc ni moteur Journey local, ni Readiness locale, ni Access local autoritatif, ni système d'objectifs mobile, ni historique parallèle, ni moteur Live autonome.

---

## 2. Position dans l'architecture mobile

Les blocs précédents ont déjà fixé :

~~~text
Bloc A — Local Data Kernel
Bloc B — Sync & Continuity Kernel
Bloc C — Files, Media & Transfer Kernel
Bloc D — Native Integration, Push, Ingress & Ambient
~~~

Le Bloc E répond maintenant à :

> **Comment les surfaces profondes de Makolo consomment-elles ces kernels sans reconstruire les domaines serveur ?**

Architecture cible :

~~~text
Maintenant / Découvrir / Mark / En cours / Moi
                     ↓
           owner-backed depth
                     ↓
        feature controller / use-case
                     ↓
            repository propriétaire
              ↙                ↘
Projection locale             SyncSource
+ draft/pending               owner API
+ fichiers privés                 ↓
              ↘                ↙
                 serveur Makolo
       règles + calculs + autorité
~~~

La profondeur n'est pas un second owner.

---

## 3. Audit runtime au moment de la fermeture de E

### 3.1 Git

Base auditée :

~~~text
main@ce1525075b61a7255e2a33ee8779af8a08c40008
Docs — freeze mobile Bloc D native integration kernel (#352)
~~~

Les derniers changements après A2 sont principalement documentaires et CI. Le runtime mobile applicatif de base reste celui issu d'A2.

PR mobile ouverte observée pendant cet audit :

- #351 — device feedback sur launch, onboarding et guest search.

Elle ne touche pas les owner depths E et ne justifie pas de baser E sur sa branche.

### 3.2 Mobile actuel

Le runtime mobile possède déjà :

- shell Maintenant · Découvrir · [Mark] · En cours · Moi ;
- auth et session recovery ;
- ProjectionSnapshots ;
- ResourceIndex ;
- SyncSources ;
- OutboxOperations ;
- LocalDrafts ;
- FileRecords ;
- network, sync, background et native kernels ;
- routes secondaires pour Journey, Activity, Occurrence, Access, Dossier, Project et Group.

Mais ces profondeurs sont encore des placeholders.

PersonalRepository observe actuellement seulement :

~~~text
personal.now
personal.ongoing
personal.me
~~~

Le Bloc E doit donc installer les **repositories et sources dynamiques de profondeur**, pas refaire les racines A2.

### 3.3 Serveur déjà disponible

Le runtime serveur expose déjà notamment :

| Profondeur | Contrat courant |
|---|---|
| Journey | GET /api/v1/me/journeys/<id>/ |
| Requirement | GET /api/v1/me/journeys/<journey>/requirements/<assessment>/ |
| FormRequest | GET /api/v1/questionnaires/requests/<id>/ |
| Form save | POST /api/v1/questionnaires/requests/<id>/save/ |
| Form submit | POST /api/v1/questionnaires/requests/<id>/submit/ |
| Journey Resources | GET /api/v1/preparation/journeys/<id>/resources/ |
| Mes accès | GET /api/v1/me/accesses/ |
| Access detail | GET /api/v1/me/accesses/<id>/ |
| AccessCredential | GET /api/v1/me/accesses/<id>/credential/ |
| Resources | GET /api/v1/me/resources/ |
| Resource detail | GET /api/v1/me/resources/<id>/ |
| Resource download | GET /api/v1/me/resources/versions/<id>/download/ |
| Resource reuse | POST /api/v1/me/resources/versions/<id>/reuse/ |
| Dossier | GET /api/v1/objectives/dossiers/<id>/ |
| Project | GET /api/v1/objectives/projects/<id>/ |
| Historique | GET /api/v1/me/history/ |
| Conversations | GET /api/v1/conversations/ + détail et mutations |
| Jour J | GET /api/v1/me/occurrences/<id>/day-of/ |
| Operations Readiness | GET /api/v1/operations/occurrences/<id>/readiness/ |
| Operations Live | GET /api/v1/operations/occurrences/<id>/live/ |
| Offline Action Pack | GET /api/v1/operations/occurrences/<id>/offline-action-pack/ |
| Passeport | GET /api/v1/me/passport/ |
| Group detail | GET /api/v1/me/collectives/groups/<id>/ |
| Recognition | GET /api/v1/recognition/me/ + owner mutations |
| Loyalty | GET /api/v1/loyalty/me/ + reward redemption |
| Partner | GET /api/v1/me/partners/<id>/ |

Aucun namespace /api/v1/mobile/ n'est requis.

---

# 4. E0 — Contrat général d'une profondeur owner-backed

## 4.1 Une profondeur n'est pas un GET → spinner → écran

Lorsqu'un détail a déjà été observé sur l'appareil :

~~~text
route
  ↓
repository
  ↓
snapshot local immédiat
  ↓
UI
  +
refresh owner discret si nécessaire
  ↓
store
  ↓
UI mise à jour
~~~

Le réseau n'est pas le store de présentation.

Le réseau :

- enrichit ;
- rafraîchit ;
- confirme ;
- revalide ;
- exécute les mutations ;
- arbitre les conflits.

## 4.2 Pas une table Django par écran

Par défaut, E réutilise :

~~~text
ProjectionSnapshots
ResourceIndex
SyncSources
LocalDrafts
OutboxOperations
FileRecords
~~~

Le Bloc E **n'exige pas de nouvelle table Drift** pour simplement ouvrir Journey, Access, Dossier, Project, Historique ou Jour J.

OccurrenceFactsIndex, défini conceptuellement par le Bloc A mais absent du schéma runtime actuel, reste un enrichissement justifié seulement si les requêtes locales calendaires ou spatiales réelles démontrent son besoin pendant l'implémentation.

> **Ne pas normaliser localement un domaine simplement parce que sa projection contient plusieurs champs.**

## 4.3 Clé de snapshot

Pour les détails :

~~~text
projectionKind = contrat logique
resourceKey    = identité owner stable
~~~

Exemples conceptuels :

~~~text
personal.journey.detail       + journey:<id>
personal.journey.requirement  + assessment:<id>
personal.access.detail        + access:<id>
personal.resource.detail      + resource:<id>
objective.dossier.detail      + dossier:<id>
objective.project.detail      + project:<id>
personal.occurrence.day_of    + occurrence:<id>
operations.occurrence_live    + occurrence:<id>
conversation.detail           + conversation:<id>
questionnaire.form_request    + form-request:<id>
~~~

Pour une API directe sans meta.schema_version, le repository utilise un **adapter contract version** local. Il ne prétend pas que le serveur a fourni une version qu'il n'a pas fournie.

sourceGeneratedAt reste nul si l'owner ne donne pas d'instant de composition.

## 4.4 Collections et requêtes

Les collections paginées ou recherchées utilisent des sources distinctes de leurs détails.

Exemples :

~~~text
accesses:<relationship>:<query-fingerprint>
history:<filter>:<query-fingerprint>
resources:<query-fingerprint>
conversations:<query-fingerprint>
~~~

Le fingerprint doit éviter de mettre une requête potentiellement sensible en clair dans un identifiant de log ou de source.

La payload locale peut naturellement contenir le résultat reçu dans la DB privée du Profile.

## 4.5 Bootstrap

Aucune profondeur E n'est chargée intégralement au bootstrap.

Le bootstrap reste petit :

~~~text
auth/me
Now
Ongoing
Me
Discover pack borné
~~~

Les profondeurs E sont **demand-driven**.

Elles deviennent source active lorsqu'elles sont :

- ouvertes ;
- référencées par Now, Ongoing ou Me ;
- nécessaires à une action en cours ;
- utilisées par Jour J ;
- invalidées par une mutation ou un push.

## 4.6 ResourceIndex

Toute profondeur avec identité stable peut alimenter ResourceIndex :

~~~text
kind
id
label
projection kind
navigation
updated_at
~~~

Mais ResourceIndex reste un **répertoire d'identité et de navigation**, jamais une copie EAV du domaine.

## 4.7 Freshness

E adopte les familles du Bloc B sans TTL universel.

| Famille | Politique |
|---|---|
| Structure Journey, titre, metadata | stale-displayable |
| Readiness / Requirement consequence | refresh-on-open + revalidate-before-action |
| Form schema publié | stable pour le FormRequest donné |
| Form editability / response state | changeable |
| Access metadata | stale-displayable pour compréhension |
| AccessCredential | fresh + sensible + non persisté par défaut |
| Resource metadata/version | stable/changeable |
| Dossier/Project | stale-displayable, owner refresh |
| Historique | ancien reste utile ; premier écran refresh |
| Conversation attention/can_respond | changeable |
| Jour J | court |
| Queue/Placement/Live | volatile |
| Offline Action Pack | obey server fresh_until/expires_at |
| Recognition/Loyalty value | refresh avant redemption |

Une donnée stale peut rester informative.

Elle ne devient jamais autorité pour une mutation.

## 4.8 Pending local

Une mutation pending est une **couche technique séparée**.

Elle ne réécrit jamais :

~~~text
Journey.status
Readiness
Requirement satisfaction
Access.status
Payment.status
Queue position
Capacity
Dossier readiness
Conversation server outcome
~~~

Exemple :

~~~text
form draft local = "réponse préparée sur cet appareil"
≠
FormRequest completed
~~~

## 4.9 403/404 après une donnée locale

Un snapshot local privé peut avoir été légitime hier et ne plus l'être aujourd'hui.

Après une revalidation authentifiée explicite :

~~~text
403/404 owner
→ marquer la ressource inaccessible
→ retirer les actions
→ retirer ResourceIndex actif
→ purger la payload sensible selon retention policy
~~~

Ne pas conserver indéfiniment une ancienne représentation privée comme si l'autorité n'avait pas changé.

Offline sans revalidation reste différent : le client peut montrer ce qu'il savait légitimement, selon la policy de sensibilité.

## 4.10 Navigation et provenance

Une identité métier n'est pas une provenance de navigation.

~~~text
Now → Journey
Ongoing → Journey
Notification → Journey
History → Journey
Mark → Journey
~~~

ouvrent **le même Journey**.

La pile de navigation conserve seulement l'origine pour le retour.

Le repository et la vérité Journey ne varient pas selon la porte d'entrée.

## 4.11 Correction de couture découverte pendant l'audit E

Le backend M10 fournit des destinations structurées en minuscules :

~~~text
journey
access
occurrence
conversation
group
partner
dossier
project
resource
activity
~~~

et, pour Resources, resource.kind = personal_asset.

Le DeepLinkResolver mobile courant matche encore des formes telles que :

~~~text
Journey
Access
Occurrence
Dossier
...
~~~

E considère ce décalage comme une **couture mobile à corriger avant les profondeurs**.

Décision :

> **L'ingress mobile normalise sur le contrat canonique M10, pas sur la casse de tests historiques.**

Le parser doit distinguer :

- navigation.target : destination UX et owner ;
- navigation.resource.kind/id : identité canonique.

Il ne déduit jamais une permission du type ou du lien.

---

# 5. E1 — Journey, Requirements, Readiness et Forms

## 5.1 Question humaine

La profondeur Journey répond à :

> **« Où en est ce que je poursuis, qu'est-ce qui est déjà réglé, qu'est-ce qui reste de mon côté, et quelle est la prochaine conséquence utile ? »**

Elle ne devient pas une checklist de modèles.

## 5.2 Contrat serveur Journey existant

personal.journey.detail expose actuellement notamment :

~~~text
identity
representation
state
readiness
requests
requirements
forms
activity
occurrence
payment
access
resources
capabilities
links
~~~

readiness est déjà groupée serveur en :

~~~text
ready
actor_interventions
waiting
blockers
next
~~~

Le mobile ne recalcule aucune de ces catégories.

## 5.3 Repository Journey

Responsabilité :

~~~text
watchJourney(id)
refreshJourney(id)
invalidateJourney(id)
~~~

Source logique :

~~~text
journey:<id>
~~~

Stockage :

- snapshot complet de la projection ;
- ResourceIndex journey/id ;
- refs Activity, Occurrence et Access connues ;
- pending overlays séparés.

Le repository ne modifie jamais le payload pour « faire avancer » localement la Journey.

## 5.4 Ouverture

~~~text
local snapshot présent
→ afficher
→ refresh discret

local snapshot absent + online
→ loader/skeleton borné
→ fetch owner
→ persist
→ afficher

local snapshot absent + offline
→ première disponibilité nécessaire
~~~

## 5.5 Readiness

Readiness reste strictement serveur.

Le mobile peut :

- grouper visuellement les checks déjà catégorisés ;
- masquer les groupes vides ;
- choisir une morphologie UI ;
- afficher le label humain fourni ;
- ouvrir next.link.

Il ne peut pas :

- décider qu'un Requirement est satisfait ;
- convertir un document présent en ready ;
- promouvoir une action depuis un statut brut ;
- calculer un pourcentage de préparation ;
- fusionner waiting et blocker.

## 5.6 Requirement detail

Source :

~~~text
personal.journey.requirement.detail
~~~

Le serveur donne :

~~~text
requirement
assessment.state
assessment.consequence
ways_to_satisfy
links
~~~

Décision :

> **Le Requirement detail est read-only côté mobile tant qu'un owner link ou capability de mutation n'est pas explicitement exposé.**

Une action de paiement, JourneyStep ou ressource n'est affichée que si le contrat owner fournit un chemin réellement consommable.

Après toute action externe qui peut influencer ce Requirement :

~~~text
refresh requirement
+ journey
+ ongoing
+ now si la conséquence peut affecter l'attention
~~~

Pas de mutation locale de satisfaction.

## 5.7 Forms : vérité serveur

Les FormRequests sont owner-backed par Questionnaires.

Le payload actuel expose :

- request id ;
- Journey ou target Profile ;
- required ;
- status ;
- opens_at ;
- due_at ;
- FormVersion id, key, version, title et description ;
- questions et contraintes ;
- réponse existante et answers.

La FormVersion publiée est structurellement immuable.

C'est favorable au local-first : le schéma d'un request donné peut être conservé localement.

## 5.8 Forms : draft local

Le draft local utilise LocalDrafts, pas une table Form parallèle.

Payload conceptuel :

~~~text
owner = questionnaires
resource_kind = form_request
resource_id = <request-id>

form_version_id
form_version_number
answers
base_server_answers
base_response_id?
base_response_updated_at?
draft_updated_at
~~~

Le draft doit survivre :

- background ;
- kill process ;
- faible connectivité ;
- session expirée.

Il reste isolé par Profile.

## 5.9 Validation locale

Le client peut appliquer les contraintes de présentation explicites reçues :

- required ;
- min/max length ;
- min/max numeric ;
- choix autorisés ;
- type date, boolean et number.

Cette validation améliore l'UX.

Elle ne devient jamais l'autorité.

Le serveur revalide toujours.

## 5.10 Opens/due

Le client peut utiliser opens_at et due_at comme indication d'interface.

Mais :

> **l'horloge du téléphone n'est pas une autorité métier.**

Une soumission ou sauvegarde doit être revalidée par le serveur.

## 5.11 Save

Cycle cible :

~~~text
saisie
→ LocalDraft autosave
→ réseau disponible
→ preflight/refetch si nécessaire
→ POST .../save/
→ réponse serveur
→ FormRequest snapshot appliqué
→ draft local réconcilié
~~~

Une perte réseau après POST ne doit pas conduire à une répétition aveugle.

## 5.12 Gap maturité Form multi-device

Le payload FormResponse courant n'expose pas updated_at, alors que le modèle possède déjà ce timestamp.

Le save API ne possède pas de précondition de concurrence.

Pour un vrai local-first multi-device, E retient un gap owner minimal :

1. exposer response.updated_at lorsqu'une réponse existe ;
2. accepter une précondition de save fondée sur la version observée, sans créer un moteur générique de versioning ;
3. en cas de mismatch, répondre en conflit et permettre le refetch de l'état courant.

Une solution possible sans migration métier est un contrat propriétaire autour de l'updated_at existant.

La syntaxe HTTP ou body exacte sera décidée à l'implémentation.

Tant que ce contrat n'est pas livré :

> **pas d'auto-replay silencieux d'un draft Form offline sur une réponse serveur qui peut avoir changé ailleurs.**

Le mobile refetch, compare et préserve les deux contenus en cas de divergence.

## 5.13 Submit

Submit est une transition terminale de la réponse.

Cycle :

~~~text
draft local
→ save/reconcile
→ refresh request
→ user confirms submission consequence if needed
→ POST .../submit/
→ server validates
→ apply response
→ invalidate Journey/Requirement/Now/Ongoing
~~~

Replay :

> **no-blind-retry.**

Si la réponse HTTP est perdue :

~~~text
refetch FormRequest
→ si submitted/completed : reconcile success
→ sinon permettre retry explicite
~~~

## 5.14 Reopen

Le backend peut rouvrir une réponse.

Au refresh :

- le mobile accepte le nouveau statut ;
- ne conserve pas l'ancienne UI « définitivement soumise » ;
- peut restaurer un nouveau draft à partir de la réponse serveur réouverte.

Aucune déduction depuis un ancien état local.

## 5.15 Journey Resources / Preparation

GET /api/v1/preparation/journeys/<id>/resources/ expose une collection directe :

~~~text
id
title
description
kind
visibility
version
occurrence_id
text
external_url
download_url
~~~

Le mobile peut conserver la liste comme snapshot owner-specific.

### Gap download natif découvert en E

Pour une Resource de type FILE, download_url pointe actuellement vers la route Web Preparation resource-download.

Cette route est une vue Django Web, pas une owner API DRF/Bearer dédiée.

Un client natif ne doit pas transformer cela en téléchargement fiable par heuristique de cookies ou de session.

E exige donc, avant un téléchargement natif de Preparation Resource :

> **un endpoint API owner de download qui réutilise can_view_resource(), répond en Bearer auth, private, no-store et nosniff.**

Pas de duplication du storage ni de signed URL longue durée.

## 5.16 Handoffs Journey

Journey peut ouvrir :

- Activity ;
- Occurrence ;
- Requirement ;
- Form ;
- Access ;
- Resources ;
- Jour J ;
- Operations Live lorsque le serveur le permet.

Le mobile suit les links et capabilities.

Pas de bouton générique « Continuer » sans conséquence identifiable.

## 5.17 Décision E1

- Journey = snapshot owner + pending overlays séparés ;
- Readiness = serveur uniquement ;
- Requirement = lecture serveur, mutations via owners ;
- Form schema cacheable ;
- Form draft = local ;
- save = owner + preflight et concurrence ;
- submit = online + no blind retry ;
- Journey Preparation Resources = lecture owner ;
- téléchargement natif Preparation FILE nécessite une vraie API owner ;
- aucun moteur Journey local.

---

# 6. E2 — Access, Credential, Resources et JourneyArtifact

## 6.1 Access : question humaine

> **« Quel droit ai-je, pour quoi, pour qui, pendant quelle période, et comment l'utiliser lorsque le moment vient ? »**

La collection Mes accès et le détail restent distincts de Journey.

## 6.2 Collection Mes accès

personal.accesses supporte :

- relationship beneficiary ;
- relationship purchased_for_other ;
- recherche ;
- offset/limit ;
- page bornée ;
- refs Activity, Occurrence et Journey ;
- résumé credential uniquement pour le bénéficiaire légitime.

Stockage local :

- snapshot de collection par query fingerprint ;
- ResourceIndex pour chaque Access ;
- détail chargé à la demande.

Offline :

- consultation des droits observés ;
- aucune affirmation que le droit reste actuellement utilisable si une revalidation est nécessaire.

## 6.3 Access detail

personal.access.detail expose notamment :

~~~text
right.state
single_use
valid_from
valid_until
holder.relationship
activity
occurrence
journey
capabilities
links
~~~

Le mobile ne calcule pas :

- validité ;
- usage ;
- single-use restant ;
- relation bénéficiaire ;
- droit Jour J.

## 6.4 AccessCredential

Le credential est une profondeur sensible distincte.

Contrat :

~~~text
GET /api/v1/me/accesses/<id>/credential/
~~~

Il n'existe que si le serveur le considère présentable.

Policy E :

- pas dans ResourceIndex comme payload ;
- pas dans les snapshots généraux ;
- pas dans les logs ;
- pas dans analytics ;
- pas dans crash breadcrumbs ;
- pas de persistance locale par défaut ;
- possibilité de protection locale par biométrie selon D1 ;
- mémoire de session seulement dans E initial.

> **AccessCredential ≠ Access.**

## 6.5 Credential offline

E ne crée aucune promesse d'Access offline.

Si le réseau est absent :

- le détail Access connu peut rester consultable ;
- le credential non persisté peut ne pas être disponible ;
- aucune consommation ou validation locale n'est enregistrée comme vraie.

La véritable autorité Access offline appartient au Bloc F / A5.

## 6.6 Resources personnelles

personal.me.resources compose séparément :

- PersonalAssets ;
- Proofs ;
- Credentials Trust.

Le mobile ne les fusionne pas en un modèle Document générique.

La collection est bornée ; le détail PersonalAsset expose versions, provenance, validité et capabilities.

## 6.7 Download Resource

Le download PersonalAsset possède déjà une API authentifiée dédiée :

~~~text
GET /api/v1/me/resources/versions/<id>/download/
~~~

Bloc C reste propriétaire du cycle fichier :

~~~text
download temp
→ validation transport
→ private durable ou cache selon intention
→ FileRecord
→ open/share owner-authorized
~~~

Une version explicitement gardée offline est privée et Profile-scoped.

## 6.8 Resource reuse

Contrat :

~~~text
POST /api/v1/me/resources/versions/<id>/reuse/
body: journey_id
~~~

Le service actuel :

- vérifie controller ;
- vérifie Journey accessible ;
- crée un JourneyArtifact snapshot ;
- conserve PersonalAssetUse ;
- retourne le même JourneyArtifact si la même version est déjà utilisée dans le même contexte correspondant.

E ferme donc l'incertitude de B :

> **Le replay de la même intention ResourceVersion + Journey est owner-idempotent dans le contrat actuel.**

Le mobile doit réutiliser le même intent local pour un retry technique.

Après succès ou résultat ambigu :

~~~text
refresh resource detail
refresh journey
refresh requirement concerné si connu
refresh ongoing
refresh now si pertinent
~~~

Et surtout :

> **reuse crée un JourneyArtifact ; il ne satisfait jamais localement un Requirement.**

## 6.9 PersonalAsset create/new version

Le serveur possède les services métier, mais pas encore une API Mature native générique pour :

- créer PersonalAsset ;
- ajouter une version.

Ce gap a déjà été figé au Bloc C.

E le consomme ainsi :

- lecture, download et reuse peuvent être livrés immédiatement ;
- « Ajouter à Mes ressources » ou « Nouvelle version » ne devient actif qu'après livraison de l'owner API ;
- aucun POST vers un formulaire Web.

## 6.10 JourneyArtifact

Les services serveur existent.

Le mobile a besoin d'une owner API pour les scénarios tels que :

> **« Voici le document demandé pour cette démarche. »**

Pipeline cible C + E :

~~~text
camera/file picker
→ staging privé
→ FileRecord
→ JourneyArtifact owner upload
→ server artifact/version
→ refresh Journey
→ refresh Requirement
→ refresh Now/Ongoing
~~~

Gap actuel :

> **API JourneyArtifact mobile consommable manquante.**

E ne crée pas une API générique /upload/.

L'endpoint final doit appartenir au Journey ou à l'owner concerné et réutiliser les services existants.

## 6.11 JourneyArtifact != PersonalAsset

La présence d'un artifact dans Journey ne l'ajoute pas automatiquement à Mes ressources.

Le sens reste :

~~~text
JourneyArtifact = pièce dans le contexte de la démarche
PersonalAsset   = actif personnel durable contrôlé par la personne
~~~

Une absorption vers la bibliothèque doit utiliser le chemin owner canonique lorsqu'il est exposé.

## 6.12 Proof / Credential Trust

Le mobile peut afficher leur provenance et validité lorsqu'elles sont fournies.

Il ne peut pas :

- transformer PersonalAsset en Proof ;
- transformer Proof en Credential ;
- transformer Credential Trust en AccessCredential ;
- certifier un document local.

## 6.13 Décision E2

- Access read local-first ;
- Access validity server-owned ;
- Credential sensible non persisté par défaut ;
- Access offline = F ;
- Resources metadata + fichiers explicites ;
- reuse owner-idempotent démontré ;
- JourneyArtifact upload owner API à ajouter ;
- PersonalAsset create/version owner API à ajouter ;
- aucune satisfaction Requirement locale.

---

# 7. E3 — Dossier, Project, Historique et Conversations

## 7.1 Dossier

Question humaine :

> **« Pour cet objectif actif composé, qu'est-ce qui est réellement en place, quelles dépendances sont visibles et qu'est-ce qui reste de mon côté ? »**

Le serveur expose objective.dossier.detail avec notamment :

- objective ;
- lifecycle ;
- deadline ;
- dossier readiness ;
- visible_items ;
- visible_dependencies ;
- personal_responsibilities ;
- actor_interventions.

Le mobile ne calcule pas les dépendances.

Il ne déduit pas l'autorité depuis personal_responsibilities.

## 7.2 Dossier local

Source :

~~~text
dossier:<id>
~~~

Policy :

- stale-displayable ;
- refresh à l'ouverture et au resume si pertinent ;
- offline lecture ;
- actor_interventions restent des faits observés, pas une outbox locale.

L'API detail actuelle expose capabilities: [].

Donc E n'invente :

- edit ;
- add Journey ;
- complete objective ;
- assignment mutation.

La surface initiale est read-only sauf handoff vers Journey owner.

## 7.3 Project

Question humaine :

> **« Quel horizon durable est-ce, et quels Dossiers visibles le composent actuellement ? »**

Le serveur expose objective.project.detail avec :

- horizon ;
- lifecycle ;
- dates ;
- visible_dossiers ;
- links.

L'API actuelle expose aussi capabilities: [].

Donc Project mobile est initialement une profondeur de compréhension et de navigation, pas un task manager ni une console d'édition.

## 7.4 Historique

Historique répond :

> **« Qu'est-ce qui s'est effectivement passé pour moi ? »**

Le runtime actuel admet volontairement seulement :

~~~text
Journey historiques
Access historiques
~~~

avec déduplication lorsque l'Access représente déjà l'expérience liée à Journey.

Le mobile ne doit pas élargir l'Historique à :

- Notifications ;
- Domain Events ;
- logs ;
- recherches ;
- clicks ;
- simple created_at.

## 7.5 Historique local-first

Source par requête :

~~~text
history:<filter>:<query-fingerprint>
~~~

Pagination :

- offset/limit ;
- max owner 50.

Policy :

- première page rafraîchie ;
- anciennes pages restent fortement utiles ;
- recherche offline limitée aux items et pages acquis ;
- si le corpus local n'est pas complet, ne pas prétendre que le résultat offline est exhaustif.

Chaque item indexe son Journey ou Access et son link de détail canonique.

## 7.6 Historique ne copie pas les détails

Ouvrir une ligne :

~~~text
History Access → Access detail repository
History Journey → Journey detail repository
~~~

Pas de HistoricalJourneyModel ni HistoricalAccessModel.

## 7.7 Conversations : rôle E

Conversations reste une surface secondaire transversale.

Elle peut contribuer à Now lorsqu'un point demande réellement une action, mais E ne transforme pas Conversations en chat générique.

Le serveur fournit :

~~~text
GET /api/v1/conversations/
GET /api/v1/conversations/<id>/
POST /api/v1/conversations/points/<id>/respond/
POST /api/v1/conversations/points/<id>/acknowledge/
GET /api/v1/conversations/invitations/
POST /api/v1/conversations/invitations/<id>/respond/
~~~

## 7.8 Conversation list

Le serveur calcule déjà :

- attention_count ;
- latest_result ;
- all_clear ;
- contexte ;
- lifecycle.

Le mobile ne calcule pas l'attention depuis unread.

Le list endpoint supporte updated_after.

E l'utilise comme optimisation éventuelle, pas comme changefeed parfait :

- il n'existe pas de tombstone transverse ;
- full bounded refresh reste le chemin de convergence de base ;
- une collection locale ne conclut pas qu'une conversation a été supprimée simplement parce qu'elle n'est pas revenue dans un delta.

## 7.9 Conversation detail

Le serveur fournit les Points avec :

~~~text
response_mode
lifecycle
importance
requires_acknowledgement
opens_at
deadline_at
valid_until
can_respond
attention_reason
section
resolution_summary
~~~

Ces champs sont des décisions owner.

Le mobile ne recalcule pas :

- can_respond ;
- attention_reason ;
- section ;
- résolution.

## 7.10 Draft réponse Conversation

Un Point textuel ou à choix peut utiliser LocalDrafts.

Le draft est local.

La réponse active n'est confirmée qu'après serveur.

## 7.11 Idempotence réponse Point

submit_point_response() possède déjà client_reference.

Décision E :

~~~text
same human intent
→ stable client_reference
→ same retry
~~~

Si le même client_reference est rejoué avec même point, sujet et valeur, le serveur renvoie la réponse existante.

Si les données changent sous la même référence, le serveur refuse.

C'est le bon contrat pour Outbox C.

## 7.12 Acknowledge

Acknowledge est state-setting côté owner.

Le mobile peut le représenter optimistic ou pending, mais le serveur reste canonique.

Après erreur ambiguë : refetch conversation.

## 7.13 Invitation Conversation

Accept ou decline est une décision terminale.

Le service retourne l'état existant si l'invitation n'est plus pending.

E ne fait toutefois pas de blind-retry terminal après résultat ambigu :

~~~text
ambiguous
→ refetch invitations/conversation
→ reconcile
~~~

## 7.14 Attachments Conversation

Le Bloc C a déjà établi que l'API attachment owner et les MIME audio, voice et video ne sont pas encore complètement alignés.

Donc E initial :

- texte, choix, acknowledge et invitation peuvent fonctionner ;
- aucune pièce jointe mobile n'est inventée ;
- le média Conversation attend le contrat C.

## 7.15 Notifications et E

Notification n'est pas propriétaire des profondeurs E.

Une notification structurée peut ouvrir :

- Journey ;
- Access ;
- Conversation ;
- Dossier ;
- Project ;
- Resource ;
- Activity ;
- Occurrence.

Une fois ouverte :

> **le repository owner prend le relais et revalide.**

## 7.16 Décision E3

- Dossier et Project = lecture owner initialement ;
- aucune action sans capability + API native ;
- Historique = projection temporelle, pas domaine ;
- Conversations = owner-backed, pas unread-driven ;
- Point response = client_reference idempotent ;
- invitations terminales = refetch après ambiguïté ;
- attachments restent gap C.

---

# 8. E4 — Occurrence, Jour J et Operations Live

## 8.1 Responsabilité

Jour J répond :

> **« Cette Occurrence est maintenant réelle pour moi : comment la vivre correctement depuis ma situation actuelle jusqu'à sa fin ? »**

Il reste une grande surface contextuelle, pas un sixième onglet.

## 8.2 Sources distinctes

Jour J utilise plusieurs owners sans les fusionner :

~~~text
Occurrence detail
personal.occurrence.day_of
operations occurrence readiness
operations occurrence live
offline action pack
Access detail / credential
device location éventuellement
~~~

Chaque source conserve son propriétaire et sa fraîcheur.

## 8.3 Day-of comme racine personnelle

personal.occurrence.day_of expose déjà :

- situation ;
- timing ;
- spatial ;
- access ;
- queue ;
- placement ;
- checkpoints ;
- readiness ;
- completion ;
- capabilities ;
- links.

Le mobile doit prendre cette projection comme **racine de composition Jour J**.

Il n'assemble pas manuellement Access + Queue + Placement à partir d'APIs basses pour recréer la même décision.

## 8.4 Truth levels

Le serveur distingue déjà :

~~~text
planned
estimated
observed
unknown
~~~

Le mobile doit préserver ces différences visuellement.

Il ne transforme pas :

- planned en live ;
- estimated en observed ;
- destination de l'Occurrence en position actuelle du Profile ;
- absence de donnée en zéro ou false.

## 8.5 Représentation dominante

Le serveur fournit situation.representation.kind.

Le mobile peut choisir la morphologie correspondante :

~~~text
timing
orientation
access
adaptation
live
completion
...
~~~

C'est un choix de présentation basé sur un signal sémantique explicite.

Ce n'est pas un calcul métier local.

## 8.6 Operations Live

GET /api/v1/operations/occurrences/<id>/live/ reste l'owner détaillé.

Participant Live peut contenir :

- Access ;
- Placement ;
- flow/checkpoints ;
- Queue ;
- Capacity ;
- spatial ;
- Operational Readiness ;
- next_action.

Le mobile ne calcule pas :

- queue position ;
- available capacity ;
- next checkpoint ;
- next action ;
- access usable ;
- hazards ;
- operational readiness.

## 8.7 Refresh Live

Aucun WebSocket ou SSE générique n'est canonique aujourd'hui.

E retient donc :

~~~text
foreground Jour J
→ refresh HTTP adaptatif et borné
→ push invalidation quand D2 est disponible
→ manual refresh/retry
~~~

Pas de fréquence numérique inventée dans l'architecture.

La cadence réelle sera calibrée avec :

- volatilité de l'owner ;
- coût API ;
- batterie ;
- tests device ;
- charge serveur.

En background, l'app ne maintient pas un polling permanent.

## 8.8 Position device

La localisation native D peut enrichir la carte et l'orientation.

Elle reste :

~~~text
device observation
≠ server participant position
≠ Place truth
~~~

Le mobile ne modifie pas le payload current_position serveur avec une position GPS locale comme si le serveur l'avait observée.

La présentation peut afficher explicitement :

> **votre position sur cet appareil**

à côté de la destination owner.

## 8.9 Queue

La Queue personnelle est volatile.

Offline :

- dernière position observée peut être montrée seulement comme ancienne observation ;
- aucun appel ou tour n'est inventé ;
- aucune entrée globale n'est mutée sans serveur en E.

Waitlist reste hors de Live Queue.

## 8.10 Placement

Placement = où.

Le snapshot local peut être consulté offline.

Mais toute modification ou opération partagée reste serveur.

Capacity = combien ; jamais fusionnée.

## 8.11 Checkpoints

Checkpoint opérationnel ≠ JourneyStep.

Le mobile peut afficher :

- terminé ;
- actuel ;
- prochain owner-provided.

Il ne marque pas un checkpoint complété localement sans mutation Operations confirmée.

## 8.12 Access dans Jour J

Jour J peut afficher un résumé Access.

Le credential reste chargé par sa profondeur sensible séparée.

Si present_credential disparaît après refresh, le mobile retire l'action.

## 8.13 Offline Action Pack

Le serveur fournit :

~~~text
schema = operations.offline_action_pack
schema_version = 1
generated_at
freshness
provenance
data_policy
execution_contract
snapshot
~~~

Le mobile respecte **les timestamps fournis**.

Il ne hardcode pas les valeurs serveur courantes de fraîcheur comme règle produit.

### fresh

Le snapshot peut être rendu normalement comme observation offline.

### stale mais non expiré

Il peut être rendu comme information potentiellement ancienne.

Les actions qui exigent état actuel sont bloquées ou revalidées.

### expired

Ne plus présenter les faits volatils comme actuels.

Fallback vers :

- timing planifié ;
- occurrence detail ;
- Journey ou Access context known ;
- message d'actualisation nécessaire.

## 8.14 Offline pack ≠ OfflineGrant

Invariant :

~~~text
offline_data_grants_authority = false
server_revalidation_required = true
~~~

E ne permet donc pas offline :

- scan autoritatif ;
- AccessUse confirmé ;
- Queue globale mutée ;
- Capacity allouée ;
- Placement coordonné ;
- Checkpoint opérateur confirmé ;
- Payment.

Cela appartient à F/A5.

## 8.15 Phase after

Après la fin :

- Jour J peut conserver une phase immédiate de completion ;
- completion.links.history conduit vers Historique ;
- la surface n'archive pas elle-même les faits ;
- les ressources, Proofs et Credentials durables restent chez leurs owners.

## 8.16 Live média

Le runtime audité ne possède pas de source média Live canonique Occurrence.

Donc E n'invente :

- aucun lecteur live générique ;
- aucune URL YouTube ou Facebook ;
- aucun feed média.

Quand un owner média réel existera, il pourra être branché à Jour J conformément au contrat UX.

## 8.17 Décision E4

- Day-of = racine Jour J ;
- Live = owner Operations ;
- HTTP refresh baseline ;
- pas de pseudo realtime ;
- GPS local = overlay explicite ;
- offline pack = lecture seulement ;
- toute autorité terrain offline = F ;
- fin de Jour J → Historique et owners durables.

---

# 9. E5 — Autres profondeurs personnelles owner-backed

A3 et les contrats UX personnels impliquent aussi plusieurs profondeurs accessibles depuis Moi, Mark, Maintenant ou une autre réalité.

E les ferme techniquement sans les transformer en nouvelles destinations principales.

## 9.1 Passeport

Source :

~~~text
GET /api/v1/me/passport/
~~~

Variants serveur :

- public ;
- complete ;
- thematic ;
- custom.

Policy locale :

- snapshot privé Profile-scoped ;
- la variante fait partie de l'identité de source ;
- custom contenant une sélection ad hoc peut rester éphémère si aucune continuité n'exige sa persistance ;
- aucune donnée privée additionnelle n'est inférée.

Le Passeport représente des faits.

Il ne possède pas Profile, Proof ou Credential.

### Gap share

La lecture est disponible.

Une API native owner-backed de création ou révocation de ShareEnvelope n'est pas démontrée.

Donc :

> **pas de bouton natif de partage Passport qui fabrique un lien ou secret.**

## 9.2 Groupes

Le détail Group expose :

- relation ;
- membership ;
- authority synthétique ;
- members count ;
- capabilities ;
- links.

Mais plusieurs links d'action sont actuellement des routes Web :

~~~text
leave_web
edit_web
members_web
invite_web
~~~

Décision E :

> **Une capability sans API native consommable ne devient pas un CTA de mutation Flutter.**

La surface peut expliquer la relation et l'autorité.

Les mutations Group mobiles dédiées restent un gap futur si le mode Profile en a besoin.

Membership ne crée jamais l'autorité.

## 9.3 Recognition

Source :

~~~text
GET /api/v1/recognition/me/
~~~

Mutations propriétaires actuelles :

~~~text
redeem reward
accept/decline redemption
~~~

Règles :

- crédits privés ;
- pas de wallet transversal ;
- pas de score social ;
- idempotency_key stable pour reward redeem ;
- accept ou decline terminal : refetch après résultat ambigu ;
- balance locale ne devient pas autoritative après tap.

Après redemption :

~~~text
refresh Recognition
+ owner conséquence produite, par exemple Access ou Promotion
+ Now/Ongoing si concerné
~~~

## 9.4 Loyalty

Source :

~~~text
GET /api/v1/loyalty/me/
~~~

Règles :

- comptes séparés par programme et organisation ;
- aucune somme inter-programmes ;
- reward redeem utilise l'idempotency key owner obligatoire ;
- la condition de reward est revalidée transactionnellement serveur ;
- aucun débit de points confirmé localement avant réponse owner.

## 9.5 Partner

Sources personnelles :

~~~text
GET /api/v1/me/partners/
GET /api/v1/me/partners/<id>/
~~~

Le détail expose relation, commissions et payouts bornés et informations autorisées.

Le runtime actuel n'expose pas de payout self-service personnel.

Donc Partner mobile initial est lecture et continuité.

Une relation Partner ne crée jamais Permission ou Mandate Space.

## 9.6 Local storage E5

Ces profondeurs suivent les mêmes primitives :

~~~text
ProjectionSnapshots
ResourceIndex
SyncSources
~~~

Pas de :

~~~text
WalletTable
PointsTable universelle
PassportFacts copy
GroupAuthority local truth
PartnerFinance ledger local autoritatif
~~~

---

# 10. Registry des sources E

Le registry initial recommandé est :

| SourceKey logique | Owner | Contrat |
|---|---|---|
| journey:<id> | Journey / Readiness | personal.journey.detail |
| requirement:<assessment-id> | Requirements | personal.journey.requirement.detail |
| form-request:<id> | Questionnaires | FormRequest direct |
| journey-resources:<journey-id> | Preparation | collection directe |
| accesses:<fingerprint> | Access | personal.accesses |
| access:<id> | Access | personal.access.detail |
| access-credential:<id> | Access | sensible et éphémère, pas snapshot général |
| resources:<fingerprint> | Personal Assets / Trust | personal.me.resources |
| resource:<id> | Personal Assets | personal.resource.detail |
| dossier:<id> | Objectives | objective.dossier.detail |
| project:<id> | Objectives | objective.project.detail |
| history:<fingerprint> | History projection | personal.history |
| conversations:<fingerprint> | Conversations | collection directe |
| conversation:<id> | Conversations | détail direct |
| conversation-invitations | Conversations | collection directe |
| day-of:<occurrence-id> | Jour J composition | personal.occurrence.day_of |
| operations-readiness:<occurrence-id> | Operations | direct |
| operations-live:<occurrence-id> | Operations | direct volatile |
| offline-pack:<occurrence-id> | Operations | operations.offline_action_pack v1 |
| passport:<variant-fingerprint> | Sharing / Trust | personal.me.passport |
| group:<id> | Groups / Authorization | personal.group.detail |
| recognition:me | Recognition | owner direct/projection |
| loyalty:me | Loyalty | owner direct/projection |
| partner:<id> | Partner | personal partner detail |

Le nom Dart exact peut différer.

La responsabilité logique ne doit pas changer.

---

# 11. Matrice de mutations E

| Intention | Owner | Classe | Optimistic local | Replay |
|---|---|---|---|---|
| modifier draft Form | device | A | oui | n/a |
| save Form serveur | Questionnaires | B/C | draft oui, serveur non | refetch-before-retry ; conditional save cible |
| submit Form | Questionnaires | C | non | no-blind-retry |
| reuse Resource | Personal Assets → Journey | C | non | owner-idempotent même version + Journey |
| upload JourneyArtifact | Journey owner | C | staging/progress oui | contrat owner à livrer |
| create/version PersonalAsset | Personal Assets | C | staging/progress oui | contrat owner à livrer |
| répondre Point Conversation | Conversations | C | draft/pending oui | stable client_reference |
| acknowledge Point | Conversations | B/C | pending oui | state-setting/refetch |
| répondre invitation | Conversations | C | pending oui | refetch après ambiguïté |
| Recognition redeem | Recognition | C/D | non sur résultat final | idempotency key owner |
| Recognition accept/decline | Recognition | C | pending | no blind terminal + refetch |
| Loyalty redeem | Loyalty | C/D | non | idempotency key owner |
| AccessUse / passage | Access / Operations | D | jamais confirmé | online owner ; F pour offline |
| Queue/Placement/Checkpoint mutation | Operations | C/D | seulement pending explicite | owner-specific |
| Payment | Payments | D | jamais succeeded localement | owner/provider only |

---

# 12. Invalidation après mutation

Le client n'invalide pas « toute l'application ».

Il invalide les sources susceptibles d'avoir changé.

## Form submit

~~~text
form-request:<id>
journey:<id>
requirement concerné(s)
personal.ongoing
personal.now
~~~

## Resource reuse

~~~text
resource:<id>
journey:<id>
requirements liés si connus
personal.ongoing
personal.now si conséquence actionnelle
~~~

## Conversation response

~~~text
conversation:<id>
conversations
personal.now
~~~

## Recognition / Loyalty redemption

~~~text
owner value source
produced owner, par exemple Access ou Promotion
personal.ongoing si continuation
personal.now si décision ou action
~~~

## Operations

~~~text
day-of:<occurrence>
operations-live:<occurrence>
operations-readiness:<occurrence>
personal.now si prochain mouvement actuel
personal.ongoing
~~~

L'invalidation signifie « rafraîchir », pas « inventer la nouvelle valeur ».

---

# 13. Routage mobile des profondeurs

Le routeur peut utiliser des paths Flutter internes, mais l'identité reste kind/id.

Destinations à supporter sémantiquement après E :

~~~text
journey
activity
occurrence
access
dossier
project
group
resource
conversation
partner
~~~

Et, par navigation contextuelle interne :

~~~text
requirement
form request
credential
history
day-of
live
passport
recognition
loyalty
~~~

Une destination serveur ne doit pas avoir besoin de connaître le path Flutter.

Une évolution du path local ne change pas le contrat owner.

---

# 14. États d'écran communs

Toutes les profondeurs E supportent deux axes.

## Contenu

~~~text
initial
loading
content
empty
success
error
~~~

## Continuité / sync

~~~text
synced
syncing
pending
offline
conflict
failed
stale
~~~

Exemples valides :

~~~text
content + syncing
content + offline
content + stale
content + pending
draft + conflict
~~~

Ne pas remplacer toute la page par un spinner lorsqu'une donnée locale utile existe.

---

# 15. UX et présentation

E ne fixe pas les pixels.

Il fixe les responsabilités.

## Journey

Doit faire comprendre :

- où j'en suis ;
- ce qui est déjà réglé ;
- ce qui reste de mon côté ;
- ce qui continue ;
- prochaine conséquence.

## Requirement

Doit expliquer :

- ce qui est demandé ;
- état owner ;
- conséquence ;
- façons réellement exposées de satisfaire.

## Form

Doit permettre :

- saisie continue ;
- reprise ;
- erreur par champ ;
- distinction draft et soumis ;
- conflit multi-device honnête.

## Access

Doit faire comprendre :

- droit ;
- période ;
- relation ;
- prochain usage ;
- credential séparé.

## Dossier / Project

Doivent expliquer composition et horizon sans devenir task manager.

## Historique

Doit être temporel et récupérable, pas audit log.

## Jour J

Doit représenter la situation, pas seulement la raconter.

---

# 16. Gaps serveur réellement identifiés par E

## E-G1 — Form concurrency token

Pour un local-first mature multi-device :

- exposer un marqueur de version observable de la réponse, idéalement response.updated_at existant ;
- permettre une save conditionnelle propriétaire ;
- retourner un conflit explicite lorsque la base a changé.

Aucune migration métier nouvelle n'est nécessaire si l'updated_at existant suffit.

## E-G2 — Preparation Resource API download

La collection Journey Resource donne actuellement un download vers une vue Web.

Ajouter une vraie route API authentifiée et Bearer pour FILE Resource, réutilisant la policy owner existante.

## E-G3 — JourneyArtifact API mobile

Exposer les services existants via une owner API pour upload, version et download selon le scénario participant.

C'est nécessaire pour le cas « fournir la pièce attendue » depuis le mobile.

## E-G4 — PersonalAsset create/version API

Gap déjà fermé conceptuellement en C.

Nécessaire pour « ajouter à Mes ressources » et « nouvelle version » natifs.

## E-G5 — Conversation attachments

Nécessaire seulement lorsque le média Conversation est activé.

Doit réconcilier MIME, taille ou durée, owner API, staging et purge.

## E-G6 — Passport share API

Lecture Passport livrée.

ShareEnvelope natif create/revoke n'est pas démontré.

Ne pas fabriquer de share link côté mobile.

## E-G7 — Group mutations native

Group detail livré.

Les mutations de gestion pointent encore vers des routes Web.

Ne pas POSTer des formulaires Web depuis Flutter.

## E-G8 — Live média

Aucune source média Occurrence canonique actuelle.

Pas de faux stream.

---

# 17. Gaps mobile réellement identifiés par E

## E-M1 — Owner depth repositories

Le mobile n'a aujourd'hui qu'un PersonalRepository racine.

Il faut introduire des repositories owner-scoped, par exemple conceptuellement :

~~~text
JourneyRepository
QuestionnaireRepository
AccessRepository
ResourceRepository
ObjectiveRepository
HistoryRepository
ConversationRepository
OperationsRepository
PersonalCapitalRepository
~~~

Ce sont des frontières de consommation, pas des domaines métier mobiles.

## E-M2 — Generic keyed snapshot support

ProfileStore.watchProjection() ne lit actuellement que resourceKey == ''.

Les profondeurs exigent :

~~~text
watchProjection(kind, resourceKey)
readProjection(kind, resourceKey)
putProjection(kind, resourceKey, ...)
deleteProjection(...)
~~~

C'est une extension de store, pas une nouvelle table.

## E-M3 — Dynamic SyncSources

Le SyncEngine A1 est surtout câblé sur Now, Ongoing et Me.

E doit permettre à un repository de déclarer ou enregistrer une source dynamique owner-specific.

Le moteur central ne doit pas contenir une liste hardcodée de tous les détails.

## E-M4 — Route destinations

Les placeholders Journey, Access et autres doivent devenir des vraies destinations owner-backed.

Il faut aussi corriger le contrat de casse et target de navigation structurée M10.

## E-M5 — Presentation models

Les widgets ne consomment pas directement le JSON.

Chaque feature transforme la payload reçue en presentation model **sans recalculer le métier**.

## E-M6 — Draft et reconcile Forms / Conversation Points

Réutiliser LocalDrafts.

Ne pas créer une base de brouillons par feature.

## E-M7 — Jour J refresh coordinator

Un coordinateur de surface doit pouvoir rafraîchir Day-of et Live de façon bornée pendant que Jour J est au premier plan.

Il réutilise le Sync et Background kernel.

Pas de deuxième moteur realtime.

---

# 18. Ce que E n'ajoute pas au schéma Drift

E initial ne justifie pas automatiquement :

~~~text
JourneyTable complète
RequirementTable
AccessTable
DossierTable
ProjectTable
HistoryItemTable
ConversationPointTable
QueueTable
PlacementTable
ReadinessTable
WalletTable
~~~

Le runtime générique actuel est suffisant pour commencer :

~~~text
ProjectionSnapshots
ResourceIndex
SyncSources
OutboxOperations
LocalDrafts
FileRecords
~~~

Une migration Drift ultérieure doit prouver une requête locale réelle, pas une préférence esthétique pour la normalisation.

---

# 19. Retention

## Détails actifs

Conserver tant qu'ils alimentent une continuité utile ou une navigation récente, selon quota local.

## Historique

Les pages acquises peuvent rester longtemps : le temps ne rend pas un fait passé « stale » au même sens qu'une Queue.

Le premier écran est rafraîchi pour intégrer de nouveaux faits.

## AccessCredential

Pas de persistance générale.

## Operations Live

Snapshot court, remplaçable.

## Offline Action Pack

Respect strict expires_at.

Une version expirée peut être conservée techniquement pour diagnostic interne si policy le permet, mais ne doit plus être présentée comme opération courante.

## Form drafts

Conserver jusqu'à :

- submit confirmé ;
- abandon explicite ;
- request annulé avec décision de purge ;
- suppression compte ou appareil ;
- policy de rétention documentée.

Une réponse locale ne doit pas être perdue juste parce que le FormRequest serveur change ; en cas de conflit, préserver pour récupération humaine.

---

# 20. Multi-device

Le serveur est le point de convergence.

## Journey

Deux appareils peuvent observer des états différents temporairement ; refresh owner tranche.

## Form

C'est le cas critique de contenu mutable : d'où E-G1.

## Resource

Versions serveur explicites ; aucun écrasement local silencieux.

## Access

Révocation et usage serveur gagnent.

## Conversation

client_reference protège la répétition d'une même réponse Point.

## Live

Le plus récent payload owner observé remplace l'ancien ; aucun LWW métier écrit depuis le mobile.

---

# 21. Sécurité et confidentialité

E applique au minimum :

- Profile-scoped DB ;
- aucun override profile_id, beneficiary_id ou act_as_space ;
- 404/403 owner revalidé ;
- AccessCredential séparé ;
- fichiers privés via Bloc C ;
- aucune PII dans source keys ou logs ;
- aucun raw payload dans crash report ;
- aucune Permission ou Mandate brute nécessaire à la présentation ;
- aucune identité d'un autre participant dans Queue ;
- aucun Placement d'autrui ;
- aucune hidden Dossier dependency exposée ;
- aucune donnée Passport privée hors projection sélectionnée ;
- aucune donnée bancaire Partner ;
- aucun solde universel Recognition + Loyalty.

---

# 22. Offline policy synthétique

| Surface | Offline lecture | Offline préparation | Offline conséquence métier |
|---|---|---|---|
| Journey | oui | oui selon drafts/resources | non sans owner confirmation |
| Requirement | oui | préparer owner input | non |
| Form | schema + draft | oui | submit non |
| Access | contexte | très limité | usage/validité non |
| Credential | non garanti | non | non |
| Resources | metadata + fichiers choisis | staging possible | reuse nécessite owner |
| Dossier/Project | oui | non dans contrat actuel | non |
| Historique | oui, pages acquises | recherche locale | n/a |
| Conversations | oui, cache | draft réponse | réponse owner |
| Jour J | oui | contexte local | non |
| Live | dernière observation | non autoritative | non |
| Offline Pack | oui jusqu'à policy | non autoritative | non |
| Recognition/Loyalty | lecture snapshot | intention possible | redemption serveur |
| Partner | lecture | n/a | owner uniquement |

---

# 23. Ordre d'implémentation recommandé

## E-I — Infrastructure owner-depth

1. corriger StructuredDestination M10 ;
2. étendre ProfileStore à resourceKey ;
3. registry de sources dynamiques ;
4. generic owner repository helpers ;
5. purge 403/404 ;
6. tests local-first depth.

## E-II — Journey / Requirement

1. Journey detail ;
2. Requirement detail ;
3. links et capabilities ;
4. retour Now/Ongoing ;
5. offline snapshot.

## E-III — Forms

1. FormRequest detail ;
2. local draft ;
3. validation présentation ;
4. save/reconcile ;
5. conditional concurrency server gap ;
6. submit no-blind-retry ;
7. invalidations.

## E-IV — Access / Resources

1. Mes accès ;
2. Access detail ;
3. credential sensitive surface ;
4. Resources collection/detail ;
5. download Bloc C ;
6. reuse ;
7. owner API gaps upload/artifact.

## E-V — Objectives / History / Conversations

1. Dossier ;
2. Project ;
3. Historique ;
4. Conversation list/detail ;
5. point response, acknowledge et invitation.

## E-VI — Jour J / Live

1. Day-of root ;
2. Live refresh ;
3. offline pack ;
4. map/location overlay D ;
5. credential handoff ;
6. end → Historique.

## E-VII — Other personal depths

1. Passport ;
2. Group read/detail ;
3. Recognition ;
4. Loyalty ;
5. Partner.

Le parallélisme est possible après collision audit.

Les fichiers à forte collision probable :

- mobile/lib/app/router.dart ;
- providers/runtime wiring ;
- shared repository/store helpers ;
- source registry ;
- tests navigation.

Ces fichiers doivent rester propriété de l'intégrateur, pas de plusieurs lanes en parallèle.

---

# 24. Stratégie de développement parallèle

Deux développeurs peuvent travailler simultanément si les surfaces sont découplées.

Exemple :

~~~text
Lane E-A
Journey + Requirement + Forms

Lane E-B
Access + Resources

Intégrateur
store keyed sources + router + registry
~~~

Puis :

~~~text
Lane E-C
Objectives + History + Conversations

Lane E-D
Jour J + Live
~~~

Les migrations et gaps backend sont isolés par owner.

Pas deux branches simultanées modifiant le même routeur central ou la même migration Drift.

---

# 25. Tests E1

## Journey

- owner snapshot local immédiat ;
- online refresh ;
- offline avec snapshot ;
- offline sans snapshot ;
- 404 après accès retiré ;
- additive fields schema v1 ;
- readiness non recalculée ;
- links et capabilities respectés.

## Requirement

- outsider 404 ;
- consequence server affichée ;
- resource present ne devient pas satisfied ;
- invalidation après owner action.

## Form

- tous types de questions supportés ;
- contraintes locales alignées ;
- draft après kill et restart ;
- server validation field errors ;
- due/open server refusal ;
- multi-device conflict ;
- submit ambiguous → refetch ;
- Profile isolation.

---

# 26. Tests E2

## Access

- beneficiary vs purchased_for_other ;
- credential seulement bénéficiaire présentable ;
- credential jamais dans DB générale ni logs ;
- revoked after cached snapshot ;
- Jour J seulement bénéficiaire réel.

## Resources

- pagination et search ;
- versions ;
- download privé ;
- fichier Profile A inaccessible à Profile B ;
- reuse même intent ne crée pas second artifact ;
- reuse ne satisfait pas Requirement ;
- archived asset non réutilisable.

## JourneyArtifact

Quand l'API est ajoutée :

- upload retry ;
- MIME et taille ;
- sensitivity ;
- owner permission ;
- staging purge après confirmation ;
- No Orphan Media.

---

# 27. Tests E3

## Dossier

- hidden dependencies non exposées ;
- Assignment != authority ;
- actor intervention serveur seulement ;
- read-only quand capabilities vides.

## Project

- Dossiers visibles seulement ;
- aucun task manager local ;
- stale et offline lecture.

## Historique

- Access et Journey seulement ;
- déduplication ;
- ordre et pagination ;
- search offline limitée ;
- buyer != beneficiary history.

## Conversations

- viewer scope ;
- can_respond owner ;
- client_reference idempotence ;
- même référence avec valeur différente rejetée ;
- acknowledge replay ;
- invitation terminal reconciliation ;
- aucune inférence unread → Now.

---

# 28. Tests E4

- participant légitime Jour J ;
- outsider 404 ;
- owner/operator non participant 404 sur Jour J personnel ;
- multi-rôle participant safe ;
- planned, estimated, observed et unknown ;
- current_position unknown non remplacé par serveur fictif ;
- Queue identité privée ;
- Placement personnel seulement ;
- AccessCredential séparé ;
- Live refresh foreground ;
- offline pack fresh, stale et expired ;
- aucune mutation autoritative offline ;
- after → History ;
- cancelled → aucune fausse action Live.

---

# 29. Tests E5

## Passport

- variants ;
- divulgation minimale ;
- aucune ShareEnvelope inventée.

## Group

- Membership != authority ;
- capabilities sans API native ne produisent pas CTA mutation ;
- outsider 404.

## Recognition / Loyalty

- idempotency keys ;
- aucun total transversal ;
- pas de solde optimiste final.

## Partner

- subject scope ;
- pas de banking data ;
- pas de payout self-service inventé.

---

# 30. CI impact-based

E respecte le CI mobile existant.

- repository/store Dart → tests targeted + Flutter checks ;
- Drift migration éventuelle → codegen + migration tests ;
- router → navigation tests ;
- Android/native non touché par E normal → pas de build natif inutile ;
- backend owner API → tests Django owner + IDOR + PostgreSQL si concurrence ou migration ;
- docs-only → aucun build Flutter ;
- cross-cutting non classé → fallback mobile full.

Aucun test ne doit être affaibli.

---

# 31. Anti-features

Le Bloc E interdit :

- local Journey engine ;
- local Readiness engine ;
- generic Task model ;
- local Requirement satisfaction ;
- local Access validity engine ;
- local Capacity ou Queue algorithm ;
- local Dossier dependency engine ;
- local History database propriétaire ;
- chat générique ;
- sync de tout le backend au login ;
- table Drift par modèle Django ;
- parse d'une URL Web pour décider du métier ;
- CTA basé uniquement sur un status enum ;
- POST vers formulaires HTML ;
- secret credential dans snapshot général ;
- blind retry d'une décision terminale ;
- upload générique sans owner ;
- wallet Recognition, Loyalty et Partner ;
- pseudo Live via timer local ;
- faux média Live ;
- autorité offline issue de l'Offline Action Pack.

---

# 32. Matrice finale — existe / manque / mobile

| Capacité | Existe serveur | Manque serveur | Mobile E |
|---|---|---|---|
| Journey detail | oui | rien pour lecture | repository + UI |
| Requirement detail | oui | owner action links selon futurs cas | repository + UI |
| Form detail/save/submit | oui | concurrence conditionnelle mature | draft/reconcile/UI |
| Journey Resources list | oui | **download API natif FILE** | repository/download C |
| JourneyArtifact service | oui | **owner API mobile** | staging/upload C |
| Access list/detail | oui | rien online | repository + UI |
| AccessCredential | oui | rien online | surface sensible |
| Access offline | non autoritatif | protocole F | hors E |
| Resource list/detail/download/reuse | oui | create/version API | repository/files/reuse |
| Dossier detail | oui | mutations seulement si produit le demande | read-only UI |
| Project detail | oui | mutations seulement si produit le demande | read-only UI |
| Historique | oui | rien | paging/cache/search local |
| Conversation list/detail | oui | attachment media gap | repository/drafts |
| Conversation point response | oui + client_reference | rien | outbox idempotent |
| Jour J | oui | rien online | contextual surface |
| Operations Live | oui | realtime transport non requis | adaptive HTTP refresh |
| Offline Action Pack | oui | authority intentionally absent | read-only offline |
| Live media | non | owner media source | ne rien inventer |
| Passport read | oui | ShareEnvelope native API | depth UI |
| Group read/detail | oui | mobile management API | depth UI |
| Recognition | oui | rien principal | owner depth/mutations |
| Loyalty | oui | rien principal | owner depth/mutations |
| Partner | oui | payout self-service absent volontairement | read-only depth |

---

# 33. Décisions figées du Bloc E

1. Les profondeurs sont demand-driven, pas bootstrap global.
2. Une profondeur lit le local avant le réseau lorsqu'un snapshot utile existe.
3. ProjectionSnapshots.resourceKey devient la clé de profondeur.
4. E n'impose aucune nouvelle table Drift par domaine.
5. Les APIs directes gardent leur hétérogénéité ; le Sync Core les adapte.
6. Readiness reste exclusivement serveur.
7. Requirement satisfaction reste exclusivement owner et serveur.
8. Form draft est device-owned ; Form submitted est serveur.
9. Form submit n'est jamais blind-retry.
10. Le contrat Form multi-device mérite une précondition owner de concurrence.
11. Access reste le droit ; Credential reste secret et représentation séparée.
12. Credential n'est pas persisté par défaut en E.
13. Access offline autoritatif appartient à F/A5.
14. Resource reuse actuel est owner-idempotent pour la même version et Journey.
15. Resource reuse ne satisfait jamais localement un Requirement.
16. JourneyArtifact upload réutilise Bloc C et attend une owner API.
17. Dossier et Project ne deviennent pas task manager.
18. Dossier et Project actuels sont read-only côté client tant que leurs capabilities et APIs de mutation ne sont pas livrées.
19. Historique reste Access et Journey dans le contrat actuel ; il n'est pas un audit log.
20. Conversations ne deviennent pas un chat générique.
21. Conversation can_respond et attention restent serveur.
22. client_reference protège le replay Point.
23. Jour J consomme personal.occurrence.day_of comme racine.
24. Operations Live calcule Queue, Placement, Capacity et next action.
25. GPS device n'écrase pas la vérité serveur.
26. Offline Action Pack est lecture seulement.
27. Le mobile obéit aux fresh_until et expires_at serveur, sans hardcoder les durées.
28. Aucun realtime fictif ; HTTP adaptatif suffit tant qu'aucun transport canonique n'existe.
29. Passeport, Group, Recognition, Loyalty et Partner restent leurs owners.
30. Une capability sans API native consommable ne devient pas un bouton mort.
31. Navigation structurée est normalisée sur les targets et kinds M10 canoniques.
32. 403/404 après revalidation retire la ressource privée active du store.
33. Pending local ne réécrit jamais la vérité owner.
34. Retour de navigation préserve l'origine ; l'identité owner reste unique.
35. Toute action sensible est revalidée serveur.

---

# 34. Critères de sortie de conception

Le Bloc E est considéré fermé quand :

- E1 à E5 possèdent un owner explicite ;
- chaque source possède stockage, freshness et invalidation définis ;
- chaque mutation possède une classe et une replay policy ;
- les gaps serveur sont séparés des tâches Flutter ;
- aucune nouvelle vérité métier n'est créée côté mobile ;
- Jour J et Live sont clairement séparés de F/A5 ;
- le routing M10 structuré est aligné côté Flutter ;
- les surfaces secondaires UX gelées peuvent toutes être rattachées à un contrat owner réel ou à un gap explicitement documenté ;
- aucun besoin de /api/v1/mobile/ n'est apparu ;
- aucun modèle Drift métier parallèle n'est nécessaire par défaut.

---

# 35. Critères avant implémentation

Avant de coder E :

1. revalider le main courant ;
2. revalider les PR mobiles ouvertes ;
3. réauditer les routes et APIs owners touchés ;
4. vérifier migrations Django et Drift ;
5. ouvrir les gaps backend uniquement dans leurs owners ;
6. implémenter E-M1 à E-M7 sans refonte esthétique de l'arborescence ;
7. tests ciblés par owner ;
8. PostgreSQL pour les changements concurrence et idempotence backend ;
9. migration fresh + historical si une migration apparaît ;
10. security et IDOR pour chaque profondeur privée ;
11. ne pas merger tant que CI n'est pas verte.

---

# 36. Formule finale

Le Bloc E ne synchronise pas des pages.

Il rend **les vérités propriétaires déjà calculées par Makolo utilisables comme continuité mobile** :

~~~text
En cours
→ ouvre la bonne réalité
→ le téléphone montre ce qu'il sait déjà
→ le serveur actualise ce qui a changé
→ la personne prépare localement ce qui peut l'être
→ l'owner décide la conséquence réelle
→ le mobile réconcilie
→ Maintenant reprend la main seulement si l'attention devient utile
→ Jour J accompagne l'exécution réelle
→ Historique et le capital personnel conservent les conséquences qui leur appartiennent
~~~

> **Le mobile conserve le fil. Le serveur conserve la vérité. La personne ne recommence pas ce qui est déjà prêt.**
