# Makolo Mobile — PAR-1C Runtime Services

**Checkpoint :** PAR-1C  
**Base :** `main@b4ea00b1a7cf8981d105140464d9751338a510ef`

## Frontières

Les plugins C-owned restent derrière les abstractions Makolo :

```text
feature
  -> service/runtime Makolo
  -> abstraction Makolo
  -> plugin/provider
```

Un push ou une notification est un signal. Il ne devient jamais une vérité métier. Les acquisitions passent par les owners, le SyncEngine et les projections locales existantes.

## Bootstrap

`main.dart` charge `MakoloRuntimeConfig`, puis `MakoloRuntimeBootstrap` initialise les services optionnels. Firebase et Sentry sont conditionnels. Workmanager possède un bootstrap idempotent séparé. Une panne d'un service optionnel ne transforme pas une action métier en échec.

## Firebase / FCM

`MAKOLO_FIREBASE_ENABLED=false` n'appelle pas `Firebase.initializeApp`. Quand Firebase est activé, une seule frontière l'initialise puis enregistre le handler background top-level.

Le handler background reste volontairement minimal : il n'ouvre aucune base Profile arbitraire, ne navigue pas et ne décide aucune vérité owner-backed. La reprise sûre se fait au foreground/resume.

Les interactions foreground/opened/initial restent représentées par `PushSignalReceiver`. Une destination push est décodée avec `StructuredDestinationCodec` et devient un `IncomingIntent`. Un payload invalide est ignoré.

`PushTokenSource` expose le token courant et ses rotations. Aucun endpoint de registration serveur stable n'a été trouvé : PAR-1C n'en invente pas. Le token complet ne doit jamais être journalisé.

### Android flavors

La configuration client Firebase attendue reste :

- DEV : `mobile/android/app/src/dev/google-services.json` pour `com.makolo.dev` ;
- BETA : `mobile/android/app/src/beta/google-services.json` pour `com.makolo.beta` ;
- PROD : `mobile/android/app/src/prod/google-services.json` pour `com.makolo`.

Le plugin Google Services est déclaré, mais ses tâches sont désactivées pour un flavor sans fichier client. Le build DEV standard reste donc possible sans compte Firebase externe lorsque Firebase est désactivé. Aucun fichier fictif n'est versionné.

## Notifications locales

`FlutterLocalNotificationScheduler` reste la frontière. Son initialisation est idempotente et ses taps réutilisent `StructuredDestinationCodec -> IncomingIntent`. La permission reste contextuelle via `PermissionGateway / MakoloPermission.notifications`; elle n'est pas demandée au lancement.

Aucune registry de channels spéculative n'est ajoutée : les usages réels restent trop peu nombreux pour justifier plusieurs catégories permanentes.

## Background

`BackgroundCoordinator`, `TaskRegistry`, `BackgroundScheduler` et `WorkmanagerBackgroundScheduler` existaient déjà et sont conservés. `WorkmanagerRuntime` ferme l'initialisation unique.

Workmanager est opportuniste/deferred. Il ne garantit aucune exécution à une heure exacte. Access, Payment, Capacity, deadlines et autres vérités sensibles restent autoritatifs côté owner/server.

L'isolate Workmanager PAR-1C reste borné tant qu'une composition Profile-safe du SyncEngine/Outbox n'est pas disponible dans cet isolate. Il ne crée donc pas de second moteur de sync.

## Observability

`ObservabilityRuntime` sélectionne `NoopCrashReporter` lorsque Sentry est désactivé et `SentryCrashReporter` après bootstrap lorsque Sentry est activé. L'environnement vient de `MakoloRuntimeConfig.environment`. Aucun DSN n'est codé en dur et `sendDefaultPii=false`.

`safeDiagnosticTags` filtre les clés sensibles, notamment authorization, password, secret, token, credential, AccessCredential, QR, payload, document, file path et JWT.

Activation externe :

```text
MAKOLO_SENTRY_ENABLED=true
MAKOLO_SENTRY_DSN=<DSN client du projet Sentry Flutter>
```

## Ambient / Android Home Widget

Le host Android réel est `MakoloAmbientWidgetProvider`. Il lit uniquement les clés minimales publiées par `AmbientSnapshot` via `home_widget`. Le widget n'est pas une base métier et ses erreurs sont non fatales.

Le wiring vers une projection réelle `personal.now` reste volontairement à l'intégrateur final afin de ne pas prendre possession de l'UX Now. PAR-1C ferme le host et la frontière de publication, pas la source métier.

## App Links

Aucun host HTTPS canonique n'est configuré. PAR-1C n'invente donc aucun verified App Link. Le contrat PAR-1A reste désactivé tant qu'un host réel n'est pas fourni.

## Gaps intentionnels

- registration serveur du device push token : aucun contrat canonique stable trouvé ;
- source réelle de l'AmbientSnapshot : à brancher par l'intégrateur sur une projection locale existante ;
- traitement lourd FCM/Workmanager en isolate : différé jusqu'à une composition Profile-safe ; reprise foreground/resume ;
- aucun Firebase/Sentry/PROD/signing fictif.
