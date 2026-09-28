# Mobile production infrastructure

**Statut :** socle technique mobile de production.  
**Base de conception :** application Flutter local-first, serveur Makolo autoritatif pour les vérités partagées et sensibles.

## Architecture

```text
UI / Experiences
        ↓
Application / controllers / use cases
        ↓
Repositories propriétaires
        ↓
Local Core (Drift + fichiers privés) + Remote Core (MakoloApiClient)
        ↓
Sync / Continuity / Outbox
        ↓
Native Capabilities
```

Le Design System, l'observabilité et l'intégration de plateforme restent transversaux. Les packages tiers sont des détails d'implémentation sous des frontières Makolo ; ils ne deviennent ni modèles métier, ni repositories métier, ni autorités.

## Classes de stockage

| Donnée | Stockage |
|---|---|
| projection métier structurée | Drift, isolé par Profile |
| capture ou fichier en préparation | staging privé du Profile |
| actif privé durable autorisé | private Profile file store |
| média distant reconstructible | cache média reconstructible, isolé par Profile |
| cache cartographique reconstructible | répertoire maps isolé par Profile |
| JWT et petits secrets | secure storage |

`file_records`, l'outbox et les tables existantes sont réutilisés. Ce chantier n'ajoute aucune table Drift ni migration. Un cache d'image tiers global n'est pas utilisé comme source de vérité : les octets privés passent par le cache Makolo isolé par Profile et sont ensuite présentés depuis un fichier local.

## Network Core

`MakoloApiClient` reste la frontière unique exposée au reste de l'application. Dio est le transport et ne fuit pas dans les features.

Le client porte JSON, requêtes publiques et authentifiées, GET/POST/PUT/PATCH/DELETE, headers, timeouts, annulation, multipart, upload/download et progression. Le refresh JWT reste single-flight ; une rotation est persistée avant retry. Les erreurs serveur et transport sont normalisées. Il n'existe aucun retry aveugle des mutations ni endpoint générique inventé : l'owner repository fournit l'endpoint réel et sa politique d'idempotence.

Les nouveaux DTO réseau structurés utilisent `json_annotation` + `json_serializable`. Un DTO réseau n'est ni un modèle Drift ni une vérité métier. Les fichiers `*.g.dart` restent générés et ignorés conformément à la politique existante du dépôt.

## File / Media Core

Pipeline de base :

```text
capture / picker
→ staging privé
→ file_records
→ opération owner/outbox si nécessaire
→ transfert owner-specific
→ confirmation owner
→ promotion vers fichier privé durable
→ nettoyage du staging devenu inutile
```

`ProfileFileStore` sécurise staging, promotion et metadata locale. `FileOwnerTransfer` laisse au domaine propriétaire l'endpoint, la version serveur et la confirmation. `ProfileMediaCache` utilise un fichier `.part`, progression et annulation puis commit atomique du cache. Une reprise métier de transfert reste owner-specific : si le serveur offre plus tard un protocole chunk/range, l'adaptateur owner l'utilise sans changer cette frontière.

Les PDF et vidéos privés sont lus depuis des fichiers locaux. `pdfrx` et `video_player` sont des viewers, pas des propriétaires de données.

## Background / continuity

`BackgroundCoordinator`, `TaskRegistry` et `BackgroundScheduler` séparent l'orchestration Makolo de Workmanager. Les familles prévues sont flush outbox, refresh borné, upload, download et maintenance de cache.

Workmanager n'est qu'un ordonnanceur OS : une tâche peut être retardée ou refusée. Launch, resume, reconnect et action utilisateur restent des chemins valides de continuité. Une feature enregistre son handler owner-specific dans le registry ; elle ne crée pas son propre moteur de background.

## Platform capabilities

Les frontières stables vivent sous `mobile/lib/platform/` :

- permissions : `PermissionGateway` ;
- biométrie locale : `LocalProtection` ;
- localisation : `LocationService` ;
- cartes : `MakoloMapView` sur MapLibre ;
- capture simple : `SystemMediaPicker` ;
- caméra intégrée : `IntegratedCamera` ;
- fichiers système : `SystemFilePicker` ;
- scanner : `MakoloCodeScanner` ;
- rendu QR : `MakoloQrView` ;
- push : `PushSignalReceiver` ;
- notifications locales : `LocalNotificationScheduler` ;
- partage / ouverture externe : `ShareGateway` ;
- ambient : `AmbientSnapshotPublisher`.

Une abstraction n'est ajoutée que lorsqu'elle protège un plugin natif, stabilise un contrat ou rend les tests utiles.

### Geography / maps

Les faits Geography restent propriétaires côté Makolo. Le renderer MapLibre reçoit un style depuis son appelant ; aucune URL de tuiles, aucun provider et aucun serveur OSM public ne sont codés en dur. Le cache cartographique possède déjà un espace reconstructible isolé par Profile. L'offline map provider-specific sera construit derrière cette frontière, sans modifier les vérités Geography. Le geofencing reste volontairement en réserve.

### Camera / documents

`image_picker` couvre la sélection/capture système simple et la récupération d'une sélection interrompue. `camera` couvre une expérience caméra intégrée. Les deux restent distincts. Toute sortie destinée à Makolo doit être copiée dans le staging privé avant que l'application ne dépende durablement du chemin temporaire fourni par l'OS.

### QR / Access

Le scanner lit une représentation ; le renderer en produit une. Aucun des deux ne crée Access. Toute validation ou consommation d'un AccessCredential reste sous l'autorité Access et les contrats serveur existants. Aucune autorité offline nouvelle n'est créée.

### Biométrie

La biométrie protège localement une surface, un fichier, un credential local ou une opération locale. Elle ne crée jamais Permission, Mandate, Access ni Trust.

## Push, notifications et ingress

```text
push reçu
→ normalisation/validation
→ invalidation des sources concernées
→ refresh par l'owner
→ store local mis à jour
→ présentation / destination canonique
```

Le push est un signal, jamais la vérité. Le scheduler de notification locale est technique et n'invente aucune deadline ni règle de rappel.

`IncomingIntentResolver` unifie notification, push, QR, widget, App Link et custom scheme autour de `StructuredDestination` puis réutilise le `DeepLinkResolver` existant. Une destination protégée est conservée pendant l'authentification ; aucune entrée ne contourne les contrôles serveur de Permission, Mandate ou Access.

## Ambient

`AmbientSnapshot` est une projection locale minimale : kind, title, subtitle, status, time, place, deep link, updated_at. Elle peut être publiée vers un home-screen widget sans exposer la DB. La même frontière est prévue pour une future Live Activity/équivalent.

Le host iOS n'existe pas encore. Par conséquent aucun bundle identifier, App Group, entitlement ou identifiant de Live Activity n'est inventé. L'adaptateur iOS correspondant sera ajouté derrière `AmbientSnapshotPublisher` quand l'identité iOS canonique sera fixée.

## Observabilité

`CrashReporter` et `Diagnostics` ont une implémentation no-op. `SentryCrashReporter` est disponible mais aucun DSN n'est fabriqué. Les tags diagnostiques filtrent notamment authorization, password, token, secret, credential, QR, payload, document et chemin de fichier ; les payloads sensibles ne doivent jamais être envoyés.

## Stack retenue

Le socle existant reste : Riverpod, go_router, Drift/drift_flutter, secure storage, connectivity_plus, path_provider et flutter_svg.

Ajouts structurants : Dio, json_serializable/json_annotation, image_picker, camera, file_picker, video_player, pdfrx, geolocator, maplibre_gl, mobile_scanner, pretty_qr_code, permission_handler, local_auth, share_plus, url_launcher, workmanager, firebase_core/firebase_messaging, flutter_local_notifications, home_widget et sentry_flutter.

MapLibre 0.27.1 impose JDK 21 pour le build Android ; la CI Android utilise donc JDK 21 tandis que le bytecode applicatif reste ciblé Java/Kotlin 17. Le `minSdk` applicatif est au moins 24, cohérent avec les plugins sélectionnés.

## Configuration externe volontairement absente

Le dépôt ne fournit actuellement pas de vérité canonique permettant d'inventer :

- projet/options Firebase ;
- DSN Sentry ;
- style/provider/URL de tuiles ;
- identité et signing iOS ;
- App Group, push entitlements, widget/Live Activity identifiers iOS ;
- nom de widget natif réellement livré.

Les adaptateurs sont prêts, mais restent inactifs tant que la configuration propriétaire correspondante n'existe pas. L'unique décision bloquant la création du host iOS est la fixation de son identité applicative canonique et des capacités/signatures qui en dérivent.

## Capacités en réserve

Contacts OS, speech-to-text, OCR, NFC, geofencing, calendrier OS, Bluetooth/beacons, AR, WebSocket/SSE et moteurs audio spécialisés ne sont pas intégrés. Aucune interface morte n'est créée pour eux.

## CI incrémentale

`mobile/tool/ci_scope.sh` classe le diff PR/base en docs, design, app-shell, network, data, drift, sync, platform, native, dependencies, feature et visual. Le sélecteur est lui-même testé.

- docs only : aucun Flutter ;
- visual : checks Dart ciblés + golden séparé ;
- network : tests network/auth/contract, sans build natif ;
- Drift : génération + DB/migration/file tests ;
- sync : sync/outbox/contract ;
- platform : tests des frontières Makolo ;
- pubspec/lock/Flutter/native Android : Android debug build ;
- changement mobile non classé : fallback vers la suite Flutter complète.

Les goldens ne se déclenchent que pour les surfaces pouvant affecter le rendu. `Mobile APK` est exclusivement manuel. Un build Android debug est un gate d'intégration, pas un « APK de composant ».

## Règles d'extension

1. Identifier l'owner métier avant l'endpoint, la persistence ou l'idempotence.
2. Lire les données déjà synchronisées depuis le store local.
3. Utiliser `MakoloApiClient`, jamais Dio directement dans une feature.
4. Copier une capture/fichier durable dans le staging privé avant traitement.
5. Laisser la confirmation distante au repository propriétaire.
6. Un plugin OS ne crée aucune autorité métier.
7. Un signal push ou ambient déclenche invalidation/refresh ; il ne modifie pas directement une vérité métier.
8. Ajouter une abstraction seulement si elle protège réellement une dépendance ou stabilise un contrat testable.
9. Toute nouvelle donnée locale privée doit rester Profile-scoped et minimisée.
10. Toute nouvelle surface native doit déclarer explicitement permissions, reprise après interruption et comportement lorsque l'OS refuse ou retarde l'action.
