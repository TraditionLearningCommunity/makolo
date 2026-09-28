# Makolo Mobile — Bloc D
## Intégration native, Push, Ingress et surfaces Ambient

**Statut : conception figée avant implémentation**  
**Date : 2026-09-28**  
**Dépôt : `TraditionLearningCommunity/makolo`**  
**Base observée : `main` @ `d2059416e748e922539ba834586dc2caa1e8a7d5`**

---

## 1. Objet

Le Bloc D ferme la conception des capacités réellement spécifiques au téléphone qui entourent le noyau local-first et les owners métier Makolo sans déplacer les calculs métier vers l'appareil.

Il couvre quatre sujets :

1. **D1 — Native Permission Wiring** ;
2. **D2 — Push backend réel** ;
3. **D3 — Native Ingress : App Links, QR, notifications et partage vers Makolo** ;
4. **D4 — Ambient Host : Android Widget puis surfaces Live**.

Le principe directeur reste :

> **Le serveur possède les vérités, règles, calculs, permissions métier et décisions. Le mobile reçoit, stocke, organise, présente et augmente la capacité d'agir grâce au téléphone.**

Architecture de référence :

```text
                    SERVER
        truth / decisions / orchestration
                         │
        ┌────────────────┴────────────────┐
        │                                 │
 Notifications / Push                Now / owners
        │                                 │
        ▼                                 ▼
 technical signal                    projections
        │                                 │
        └────────────── MOBILE ───────────┘
                         │
           capabilities / presentation
                         │
     ┌──────────┬────────┼────────┬──────────┐
 permissions   ingress   GPS/QR   ambient   share
     │          │         │        │          │
     └────────────── PHONE OS ────────────────┘
```

Le Bloc D ne crée pas un second backend sur le téléphone.

---

## 2. Sources de vérité et état runtime observé

Avant de figer ce bloc, le `main` courant a été revalidé.

Éléments observés utiles :

- le mobile dépend déjà notamment de `permission_handler`, `camera`, `mobile_scanner`, `geolocator`, `firebase_core`, `firebase_messaging`, `flutter_local_notifications`, `home_widget`, `workmanager`, `local_auth`, `share_plus` et `go_router` ;
- le routeur mobile possède déjà les racines `Now`, `Discover`, `En cours`, `Moi`, `Mark`, `Conversations`, `Notifications` et plusieurs routes owner-backed ;
- le serveur possède déjà `Notification`, `NotificationDelivery`, `DeliveryChannel.PUSH`, `NotificationPreference.push_notifications` et la navigation structurée des Notifications ;
- le dispatcher de notifications implémente actuellement le canal e-mail et ignore les autres canaux non implémentés ;
- `accounts.UserDevice` existe déjà, mais représente l'appareil lié au compte et son trust technique, pas un endpoint de transport Push ;
- le serveur possède `InboundCapture` et le Bloc C a déjà figé son usage comme staging owner pour les fichiers/entrées provisoires du Mark ;
- le Bloc C a déjà identifié comme manquants l'API mobile d'`InboundCapture`, l'acceptation d'une référence de capture par le Mark et plusieurs APIs owner de fichiers ;
- le Dart possède déjà une frontière Ambient (`AmbientSnapshot`, publisher Home Widget), mais aucun `AppWidgetProvider` Android réel n'est actuellement présent dans le host natif ;
- M10.0 a déjà figé que `Notification.navigation` est un hint de navigation structuré, jamais une permission, et que le client natif ne doit pas parser `action_url` pour reconstruire une identité métier.

Ce document distingue donc explicitement :

```text
runtime actuel
≠
décision de conception cible
≠
implémentation future
```

---

# 3. D1 — Native Permission Wiring

## 3.1 Principe

Makolo ne crée pas un domaine de permissions parallèle.

La feature connaît le **moment** et la **raison** de demander une capacité. Une frontière technique commune réalise la demande OS.

```text
Feature Makolo
    ↓
explique pourquoi
    ↓
PermissionGateway
    ↓
OS permission
    ↓
granted / denied / restricted / limited / ...
```

Le mécanisme de permission n'accorde aucune Permission/Mandate métier.

## 3.2 Capacités Android prévues

La configuration native doit être alignée sur les features réellement activées.

| Capacité | Permission/capacité native attendue |
|---|---|
| caméra photo/vidéo guidée | caméra |
| scanner QR | caméra |
| capture audio/voix/vidéo avec son | microphone |
| découverte autour de moi / carte personnelle | localisation foreground |
| push / notifications Android | autorisation notifications lorsque la version OS l'exige |
| sélection de fichier via picker système | pas de permission stockage globale |
| localisation background | hors Bloc D initial |
| contacts système | réserve |
| Bluetooth/beacons | réserve |
| NFC | réserve |

Règles :

- vérifier le **merged manifest réel** avant d'ajouter manuellement une permission déjà introduite par un plugin ;
- ne pas ajouter `READ_EXTERNAL_STORAGE` / `WRITE_EXTERNAL_STORAGE` comme raccourci architectural ;
- ne pas ajouter une permission background sans feature propriétaire et scénario réel ;
- la non-disponibilité d'une permission doit dégrader une feature, pas casser Makolo entier.

## 3.3 États minimum à traiter

Les adapters techniques doivent pouvoir représenter au minimum :

```text
service unavailable
permission denied
permission permanently denied
restricted
limited
provisional
granted
```

Discover doit rester utilisable sans géolocalisation. Un refus permanent mène à une explication Makolo et, lorsque pertinent, à l'ouverture des Réglages.

## 3.4 Biométrie

Décision figée :

```text
biométrie
= protection locale
≠ authentification Makolo
≠ Permission
≠ Mandate
≠ Access
```

La biométrie peut protéger une surface locale sensible. Toute action métier continue d'être revalidée par son owner serveur.

## 3.5 Décision D1

- aucun nouveau modèle serveur ;
- aucun domaine `Permission` mobile ;
- wiring natif seulement lorsque la feature correspondante est réellement activée ;
- iOS sera configuré lorsque le host et l'identité iOS canoniques seront disponibles ;
- les refus OS produisent une UX explicite et réversible autant que possible.

---

# 4. D2 — Push backend réel

## 4.1 Diagnostic

Le serveur possède déjà :

```text
Notification
NotificationDelivery
DeliveryChannel.PUSH
NotificationPreference.push_notifications
navigation structurée
quiet hours
```

Le mobile possède déjà des dépendances et primitives de réception Push.

Le gap est le pont complet :

```text
installation mobile
↔ endpoint de transport serveur
↔ delivery PUSH
↔ provider configuré
↔ signal reçu
↔ invalidation/refresh owner
```

Le dispatcher actuel ne livre réellement que l'e-mail.

## 4.2 Ne pas détourner `UserDevice`

`accounts.UserDevice` représente aujourd'hui un appareil de compte : identité technique, trust, OS/browser et usage.

Un endpoint Push possède un lifecycle différent :

```text
installation
→ token registration
→ token rotation
→ activation/revocation
→ delivery
```

Décision :

> **Ne pas enfouir le token Push dans `UserDevice.metadata`. Le transport Push appartient à Notifications.**

Le nom de travail de l'objet technique est :

```text
PushEndpoint
```

Ce nom pourra seulement être ajusté si l'implémentation découvre une abstraction canonique déjà propriétaire du même rôle ; la frontière métier, elle, est figée.

## 4.3 Données minimales d'un endpoint Push

Cible conceptuelle :

```text
user
installation_id
platform
provider/transport
push token
active
last_seen_at
created_at
updated_at
```

Éventuellement une version d'application si un besoin opérationnel réel la justifie.

Ne pas y stocker :

```text
GPS
contacts
historique d'utilisation
permissions métier
profilage appareil
secrets étrangers au Push
```

`installation_id` doit réutiliser l'identité d'installation mobile existante plutôt que créer une seconde identité locale concurrente.

## 4.4 Règles token

Le token Push :

- est accepté en écriture ;
- n'est jamais renvoyé par une API de lecture générale ;
- n'est jamais loggé ;
- n'est jamais copié dans `Notification.metadata` ;
- n'est pas dupliqué dans les payloads métier ;
- doit pouvoir tourner sans créer une infinité d'installations fantômes.

Rotation :

```text
same authenticated account
+ same installation_id
+ new provider token
→ update endpoint
```

Révocation :

```text
logout / account removal / invalid token / explicit revoke
→ endpoint inactive
```

## 4.5 API minimale

Ne pas créer de namespace parallèle `/api/v1/mobile/`.

L'API appartient au propriétaire Notifications et doit permettre au minimum :

```text
register/upsert current installation endpoint
revoke/deactivate current installation endpoint
```

Le write doit être idempotent selon la combinaison d'identité appropriée, au minimum :

```text
authenticated account
+ installation_id
+ transport/provider
```

La réponse ne doit pas révéler le token.

Les noms de routes exacts seront fixés au moment de l'implémentation après revalidation de l'URL space courant.

## 4.6 Multi-compte

Un token téléphone n'est pas un Profile.

Par défaut, pour éviter les fuites inter-comptes :

```text
compte actif
→ endpoint actif pour ce compte
```

Le support de notifications simultanées de plusieurs comptes sur un seul téléphone n'est pas implicite. Il nécessite une décision UX spécifique.

## 4.7 Réutiliser `NotificationDelivery`

Ne pas créer une deuxième outbox Push.

Le flux reste :

```text
Notification
    ↓
NotificationDelivery(channel=PUSH)
    ↓
Push transport adapter
```

Le token sensible ne doit pas être copié durablement dans chaque Delivery.

La Delivery doit résoudre l'endpoint actif au moment de l'envoi, directement ou via une référence technique stable.

Ainsi, une rotation de token n'invalide pas nécessairement une delivery pending et un endpoint révoqué peut être ignoré proprement selon la policy sans exposer le token dans l'audit.

## 4.8 Préférences

La politique doit séparer :

```text
category allowed?
+
channel allowed?
```

Exemple :

```text
category = event
channel = push
```

requiert conceptuellement :

```text
event_notifications == true
AND
push_notifications == true
```

Elle ne doit pas dépendre de `email_notifications`.

Les quiet hours existantes sont réutilisées. Aucune catégorie « urgente » bypassant les préférences n'est inventée dans ce bloc.

## 4.9 Payload Push

Un Push est un **signal de transport**, pas un snapshot métier complet.

Contrat cible minimal :

```text
schema_version
notification_id
structured navigation destination
owner/source invalidation hints éventuels
safe presentation fields éventuels
```

Le Push ne transporte pas :

```text
QR complet
AccessCredential
Readiness comme vérité autonome
Capacity actuelle comme autorité
document privé
payment details
token
PII inutile
```

`title` / `message` peuvent être repris d'une `Notification` serveur déjà créée : le Push transporte alors une représentation d'un fait serveur, il ne crée pas ce fait.

## 4.10 Cycle complet

```text
Domain Event
    ↓
server decides Notification
    ↓
Notification persisted
    ↓
NotificationDelivery(PUSH)
    ↓
configured push transport
    ↓
device receives signal
    ↓
invalidate relevant owner sources
    ↓
refresh
    ↓
local store
    ↓
UI
```

Une notification Push perdue ne doit jamais empêcher la convergence : au prochain refresh, l'app retrouve la vérité serveur.

## 4.11 Provider

Le mobile déclare actuellement des dépendances Firebase (`firebase_core`, `firebase_messaging`).

Cela ne suffit pas à déclarer qu'un provider de production est canoniquement configuré.

Avant implémentation :

- vérifier les fichiers/configurations natives réellement présents ;
- vérifier les variables/secrets attendus ;
- ne pas inventer de projet Firebase, compte, bundle ID, sender ID ou credentials ;
- conserver un adapter de transport afin que le domaine Notifications ne dépende pas directement d'un SDK provider.

## 4.12 Décision D2

À ajouter côté serveur :

```text
endpoint Push technique owner Notifications
registration/revocation API
channel policy
push transport adapter/dispatcher
rotation/revocation handling
retry/terminal handling
privacy-safe observability
```

À brancher côté app :

```text
provider initialization réelle
permission contextuelle
token registration
token rotation
logout/account-switch reconciliation
PushSignalProcessor wiring
owner refresh after signal
```

D2 est le principal nouveau morceau backend du Bloc D.

---

# 5. D3 — Native Ingress

## 5.1 Deux familles d'entrée

Il ne faut pas mélanger navigation structurée et contenu entrant.

### Navigation structurée

```text
Notification
Push
Widget
Makolo App Link
Makolo QR de navigation
       ↓
StructuredDestination
       ↓
IncomingIntentResolver
```

### Contenu entrant

```text
Partager texte
Partager URL
Partager image
Partager PDF
Partager fichier
       ↓
Makolo Mark / InboundCapture
```

## 5.2 Navigation structurée

M10.0 a déjà figé `Notification.navigation` comme hint de navigation versionné.

Règles :

- ne jamais parser `action_url` pour reconstruire l'identité métier ;
- utiliser `kind/id` et owner links fournis ;
- la destination n'est jamais une permission ;
- après ouverture, l'owner revalide scope, confidentialité, état et autorité ;
- 403/404 reste une réponse légitime après un ancien lien.

Le resolver mobile est étendu seulement lorsque les destinations correspondantes existent réellement dans l'expérience.

## 5.3 App Links / Universal Links

On n'invente pas aujourd'hui :

```text
canonical domain
Android package association
iOS bundle identifier
iOS signing
Associated Domains
assetlinks.json
apple-app-site-association
```

Lorsque ces identités seront officiellement décidées :

```text
https://canonical-domain/...
        ↓
verified OS link
        ↓
allowlisted parser
        ↓
StructuredDestination
        ↓
IncomingIntentResolver
```

Le parser ne décide jamais de l'autorité.

## 5.4 QR

Trois cas sont distincts.

### QR Makolo de navigation

```text
QR Makolo
→ structured destination
→ owner route
→ server revalidation
```

### QR Access / scanner métier

```text
AccessCredential representation
→ Scanner owner API
→ server verdict
```

Le mobile ne valide pas localement un droit simplement parce qu'il peut lire un QR.

### QR externe arbitraire

Aucune action métier automatique.

Le contenu peut éventuellement être proposé au Mark comme input, mais jamais envoyé/exécuté silencieusement.

## 5.5 Share into Makolo

Bloc C a déjà figé :

> **Mark file = InboundCapture, pas nouveau domaine.**

Le pipeline cible est donc conservé :

```text
local private staging
→ InboundCapture API
→ capture reference
→ Makolo Mark orchestration
→ canonical owner
→ provisional payload purge when appropriate
```

Ne pas créer :

```text
ShareInbox
MobileShare domain
MarkFile
SharedDocument generic domain
```

## 5.6 Texte et URL partagés

```text
OS share sheet
→ Makolo
→ local Mark draft
→ user sees/edits/confirms
→ POST /api/v1/me/mark/
→ server understands/orchestrates
```

Le téléphone ne prétend pas comprendre lui-même l'URL ou l'intention métier.

## 5.7 Fichier, image, vidéo ou PDF partagé

```text
OS share
→ temporary OS URI
→ immediate private Makolo staging
→ FileRecord
→ InboundCapture owner upload
→ capture reference
→ Mark orchestration
```

Règles :

- l'URI OS temporaire ne devient jamais identité métier ;
- copie rapide vers sandbox privée si nécessaire ;
- réutiliser FileRecord + Outbox/Transfer du Bloc C ;
- validation MIME/taille finale côté serveur ;
- purge selon le lifecycle de staging ;
- aucune Galerie implicite ;
- aucun média durable sans owner/finalité.

## 5.8 Gap serveur précis

Le serveur possède déjà le concept et les services `InboundCapture`, mais le contrat mobile complet doit encore être exposé.

Il manque donc essentiellement :

```text
InboundCapture owner API
+
Mark accepts authorized capture reference
```

Ce gap appartient déjà au Bloc C et est consommé par D3 ; il ne faut pas créer un second mécanisme d'upload.

## 5.9 Frontière mobile Share

Une abstraction native légère est justifiée :

```text
SystemShareReceiver
    ↓
SharedPayload
```

avec catégories techniques :

```text
text
url
files
```

Le receiver ne connaît pas Journey, Access, Requirement ou autre vérité métier. Il remet le payload au pipeline owner approprié.

Le choix entre plugin mature et code natif reste un choix d'implémentation, après audit des packages au moment du travail.

## 5.10 Décision D3

Serveur à compléter :

```text
InboundCapture API
Mark capture-reference input
```

Mobile à construire :

```text
verified App Link ingress quand identité canonique disponible
notification/widget/QR ingress wiring
system share receiver
temporary URI → private staging
share text/URL → Mark draft
share file → FileRecord/InboundCapture
```

Aucun nouveau domaine métier de partage entrant.

---

# 6. D4 — Ambient Host

## 6.1 Diagnostic

Le Dart possède déjà une frontière Ambient et un publisher Home Widget.

Le host Android ne possède pas encore de `AppWidgetProvider` réel.

Donc :

> **L'architecture Ambient existe ; le widget Android concret reste à construire.**

## 6.2 Source de vérité

Ne pas créer :

```text
WidgetRecommendationEngine
AmbientPriority domain
HomeWidgetState métier
```

La première source Ambient est `personal.now`, qui répond déjà côté serveur à :

> **Qu'est-ce qui compte maintenant ?**

Pipeline :

```text
server personal.now
       ↓
ordered items
       ↓
first usable representation
       ↓
minimal AmbientSnapshot
```

Prendre le premier élément d'une projection déjà ordonnée par le serveur n'introduit pas un classement métier local.

Si `Now` est vide, `Tout est en ordre. ✓` peut être la représentation Ambient.

## 6.3 Contenu minimal d'`AmbientSnapshot`

Le snapshot Ambient reste une projection de présentation, pas une vérité autonome.

Champs utiles :

```text
kind
title
subtitle
status
time
place
structured destination / deep link
updated_at
```

Ne pas y inclure :

```text
AccessCredential
QR complet
document privé
raw API payload
raw DB row
payment details
contact details
secrets
```

`status` reprend un état reçu. Le téléphone ne calcule pas un nouveau statut métier.

## 6.4 Confidentialité

Un widget peut être visible sans que l'utilisateur ait ouvert/déverrouillé Makolo.

Décision : prévoir une préférence **locale à l'appareil** de divulgation Ambient.

### Mode minimal par défaut

```text
Makolo
Une chose mérite votre attention
```

### Détails autorisés explicitement

Selon le contenu réellement safe :

```text
title
time
place
```

Cette préférence :

- reste device-local ;
- ne devient pas une préférence Profile globale ;
- n'accorde aucune permission métier ;
- doit être réévaluée plus strictement pour une future Lock Screen / Live Activity.

## 6.5 Refresh

Le widget ne possède pas son propre moteur métier et n'ouvre pas les APIs owners directement.

```text
owner refresh successful
        ↓
local store updated
        ↓
Ambient projection built
        ↓
AmbientSnapshotPublisher
        ↓
native widget
```

Le publish peut être déclenché après :

```text
app launch
resume
successful sync
push-triggered refresh
successful background work
```

`workmanager` reste opportuniste : aucune exactitude temporelle métier ne repose uniquement sur lui.

Si les données sont techniquement trop anciennes pour une présentation fiable :

```text
details suppressed
→ "Ouvrez Makolo pour actualiser"
```

Cette fraîcheur est technique ; elle ne remplace pas le calcul métier serveur.

## 6.6 Interaction widget

Première capacité :

```text
tap
→ StructuredDestination
→ app launch
→ authentication/context recovery
→ owner refresh/revalidation
→ destination
```

Pas d'action métier directe D4 telle que :

```text
Confirmer
Payer
Scanner
Annuler
Rejoindre
```

Ces actions exigeraient auth, idempotence, état frais et revalidation serveur et seront traitées séparément si un vrai besoin les justifie.

## 6.7 Host Android

À construire côté Android :

```text
AppWidgetProvider
widget layout
manifest registration
home_widget bridge
canonical widget name
tap ingress
```

Le nom exact du widget n'est pas inventé dans ce document. Il sera fixé lorsque le provider réel sera créé et testé.

## 6.8 iOS Widgets / Live Activities

Ne pas inventer :

```text
bundle identifier
signing identity
App Group
entitlements
widget extension identifiers
ActivityKit configuration
```

Le support iOS est ouvert architecturalement grâce à la frontière Ambient commune, mais l'implémentation attend l'identité native iOS canonique.

## 6.9 Décision D4

- Android Home Widget peut être implémenté sans nouveau domaine serveur ;
- `personal.now` est sa première source canonique ;
- le snapshot Ambient est minimal et privacy-safe ;
- interaction initiale = ouvrir Makolo sur une destination structurée ;
- iOS Widget/Live Activity attend la configuration native canonique.

---

# 7. Matrice serveur / mobile

| Bloc | Serveur déjà présent | Serveur à ajouter | Mobile déjà présent | Mobile à ajouter |
|---|---|---|---|---|
| D1 Permissions | aucune vérité métier supplémentaire nécessaire | rien | packages/gateways/adapters de capacité | wiring natif et UX de refus |
| D2 Push | Notification, Delivery, prefs, structured navigation | endpoint Push technique, API, policy et dispatcher/adapter | dépendances Push + processing primitives | init réelle, registration, rotation, account lifecycle, refresh |
| D3 Ingress | navigation structurée, Mark, InboundCapture services | InboundCapture API + capture ref Mark | resolver, staging, FileRecord/transfer kernel | App Links, Share receiver, notification/widget/QR ingress |
| D4 Ambient | `personal.now` | rien initialement | AmbientSnapshot + publisher | Android AppWidget host réel |

---

# 8. Sécurité, confidentialité et autorité

Règles transversales :

1. **OS capability ≠ Makolo authority.** Une permission caméra, GPS, notification ou biométrie ne donne aucune Permission/Mandate/Access.
2. **Push ≠ vérité.** Le Push signale ; l'owner serveur reste la source de vérité.
3. **Navigation ≠ permission.** Une destination structurée peut conduire à 403/404 après revalidation.
4. **QR lu ≠ droit valide.** Scanner remet l'observation au serveur.
5. **Widget ≠ cache autoritaire.** Il présente une projection minimale ; une action sensible exige ouverture et revalidation.
6. **Share URI ≠ document métier.** Il devient d'abord staging technique privé.
7. **Token Push = secret opérationnel.** Pas de logs, pas de payload métier, pas de lecture générale.
8. **Minimum disclosure.** Push, widget, lock screen et share preview n'exposent que ce qui est nécessaire.
9. **Profile-scoped local data.** Les artefacts entrants et snapshots restent isolés par Profile/compte selon le noyau local.
10. **Aucun provider inventé.** Les identités/configurations réelles doivent venir du dépôt et des décisions officielles.

---

# 9. Anti-features

Le Bloc D ne doit pas créer :

- un backend métier local ;
- un système de Permission mobile parallèle ;
- un namespace `/api/v1/mobile/` générique ;
- une seconde outbox Push ;
- un token Push dans `UserDevice.metadata` par commodité ;
- un feed de notifications comme moteur d'engagement ;
- un `ShareInbox` métier ;
- un `MarkFile` ;
- un moteur local de ranking pour widget ;
- un widget qui exécute directement des mutations sensibles en première version ;
- des App Links non vérifiés vers un domaine inventé ;
- une configuration iOS fictive ;
- des permissions OS anticipées sans feature réelle ;
- une permission stockage globale pour éviter les APIs modernes ;
- du GPS background sans propriétaire fonctionnel réel.

---

# 10. Ordre d'implémentation recommandé

## D-I — Permissions

```text
revalidate Android host
→ merged manifest audit
→ permission wiring par feature
→ denial/settings UX
→ tests ciblés
```

## D-II — Push server bridge

```text
revalidate Notifications runtime
→ design migration technique endpoint
→ registration/revocation API
→ channel preference policy
→ provider adapter
→ delivery/retry/revocation tests
```

## D-III — Push client

```text
revalidate native provider config
→ initialize provider
→ register installation/token
→ rotate token
→ account switch/logout reconciliation
→ push signal → owner invalidation/refresh
```

## D-IV — Ingress

```text
structured destinations
→ notification ingress
→ widget ingress
→ QR routing distinctions
→ OS share receiver
→ InboundCapture integration after server API exists
→ App Links only when canonical domain exists
```

## D-V — Ambient

```text
Now → AmbientSnapshot
→ Android AppWidgetProvider
→ privacy preference
→ tap ingress
→ refresh hooks
```

Cet ordre peut être parallélisé uniquement si les fichiers/surfaces ne collisionnent pas. Un collision audit est requis avant branches concurrentes sur host Android, navigation, notifications et sync.

---

# 11. Tests et gates attendus

## D1

- permission granted/denied/permanently denied ;
- service unavailable ;
- feature dégradée sans crash ;
- aucune permission métier créée localement.

## D2 serveur

- endpoint register idempotent ;
- token rotation ;
- revoke ;
- isolation utilisateur/IDOR ;
- préférences channel + category ;
- quiet hours ;
- invalid token ;
- retry borné ;
- aucun token dans logs/serializer général ;
- migration fraîche + historique ;
- PostgreSQL si la migration le requiert.

## D2 mobile

- registration après auth ;
- rotation token ;
- logout ;
- account switch ;
- push perdu puis refresh manuel = convergence ;
- push reçu n'invente jamais un nouvel état métier.

## D3

- destination structurée allowlistée ;
- ancienne destination 404/403 propre ;
- QR externe sans exécution silencieuse ;
- share text/URL → draft Mark ;
- share file → staging privé ;
- restart avec staging pending ;
- purge et cancellation ;
- aucune fuite cross-profile.

## D4

- widget sans données ;
- widget Now all-clear ;
- widget Now avec item ;
- détails masqués par défaut ;
- stale technique ;
- tap → récupération auth/contexte → owner route ;
- aucune mutation métier directe depuis widget ;
- update après sync/push/resume.

---

# 12. CI impact-based

Le Bloc D doit respecter le CI intelligent du dépôt :

- docs-only → pas de build Flutter inutile ;
- Dart pur → tests Dart/Flutter ciblés ;
- Android manifest/provider/widget/plugin → Android debug build + tests pertinents ;
- migration/backend Push → tests Django ciblés + migrations + suite pertinente ;
- pubspec/plugin natif → build Android ;
- changement cross-cutting inconnu → fallback sûr sur gates mobiles complètes.

Aucun test ne doit être supprimé ou affaibli pour obtenir du vert.

---

# 13. Décisions figées du Bloc D

| Sujet | Décision |
|---|---|
| Autorité | serveur uniquement pour les règles et décisions métier |
| Permissions OS | capacité locale, jamais Permission/Mandate |
| Permission storage globale | non |
| GPS background | pas sans feature propriétaire réelle |
| Biométrie | protection locale uniquement |
| Push owner | Notifications |
| Push endpoint | objet technique dédié, pas `UserDevice.metadata` |
| Push token | write-only opérationnel, jamais loggé/exposé |
| Push delivery | réutilise `NotificationDelivery` |
| Push payload | signal minimal + navigation structurée |
| Push perdu | convergence via refresh owner |
| Namespace mobile API générique | non |
| Navigation native | structured destination, pas parsing `action_url` |
| App Links | seulement avec domaine et associations canoniques |
| QR navigation | destination structurée |
| QR Access | verdict Scanner serveur |
| Share texte/URL | Mark draft puis serveur |
| Share fichier | FileRecord → InboundCapture → Mark |
| Share domain générique | non |
| Widget source initiale | `personal.now` |
| Widget ranking local | non |
| Widget mutations sensibles | non dans D4 initial |
| Widget privacy | détails minimaux par défaut, préférence device-local |
| iOS widget/live | attend identité native canonique |
| Provider Push | vérifier config réelle ; ne rien inventer |

---

# 14. Critères de sortie avant implémentation

Le Bloc D est prêt à passer de conception à implémentation lorsque :

1. ce document est relu contre le `main` courant ;
2. les branches/PR mobiles actives sont auditées pour collision ;
3. les owners Notifications et InboundCapture sont revalidés ;
4. le host Android réel est revalidé ;
5. le provider Push réellement configuré, s'il existe, est identifié sans supposition ;
6. l'identité App Links/iOS n'est utilisée que si elle existe réellement ;
7. les migrations nécessaires à l'endpoint Push sont conçues sans réutiliser abusivement un modèle métier existant ;
8. les APIs InboundCapture/Mark manquantes du Bloc C sont coordonnées avec D3 ;
9. les tests d'autorité, IDOR, rotation, révocation, stale et confidentialité sont prévus ;
10. le CI impact-based est respecté.

---

# 15. Résumé final

Le Bloc D ne transforme pas Makolo Mobile en propriétaire de nouveaux systèmes métier.

Il ferme le pont entre le noyau Makolo et le téléphone :

```text
D1 — demander correctement les capacités OS
D2 — transporter les Notifications serveur jusqu'au téléphone
D3 — recevoir des intentions et contenus depuis l'OS sans inventer de vérité locale
D4 — projeter un minimum utile hors de l'app sans dupliquer Now
```

La règle de fermeture est :

> **Le téléphone augmente la capacité d'action de Makolo ; il ne remplace jamais les owners, calculs, permissions et décisions du serveur.**
