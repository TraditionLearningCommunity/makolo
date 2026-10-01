# Makolo Mobile

Client Flutter local-first de Makolo. Le serveur reste autoritatif pour l'état partagé, la concurrence, Access, Permission, Mandate, Capacity, Payment et les autres décisions sensibles.

## Architecture

```text
UI / Experiences
↓
application / use-cases
↓
repositories propriétaires
↓
Local Core + Remote Core
↓
Sync / Continuity
↓
Native Capabilities
```

Le socle détaillé et ses règles d'extension sont dans `docs/architecture/mobile-production-infrastructure.md`.

## Développement

Flutter 3.47.3 / Dart 3.13.3 sont pinés.

```bash
cd mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test --exclude-tags golden
```

Les `*.g.dart` sont générés et ignorés par Git. Drift et json_serializable utilisent le même passage build_runner.

## Configuration

La frontière runtime est `MakoloRuntimeConfig`, alimentée par `--dart-define-from-file`. `config/dev.json` porte désormais la configuration client réelle de l'environnement de développement ; BETA et PROD restent non configurés tant que leurs valeurs canoniques n'existent pas. Aucune valeur serveur privée, clé privée, service account, token administratif ou secret de signature ne doit entrer dans ces fichiers.

```bash
flutter run --flavor dev --dart-define-from-file=config/dev.json
```

Le DEV courant utilise le backend de test PythonAnywhere, MapLibre avec un style MapTiler DEV, Firebase/FCM pour `com.makolo.dev`, Sentry Flutter et la capability de localisation background. App Links reste désactivé. Les identifiants client nécessaires au runtime DEV peuvent être versionnés ; les secrets serveur restent interdits.

DEV/BETA/PROD, Firebase, Maps, Sentry, App Links et la capability de localisation background sont documentés dans `docs/architecture/mobile-par1a-runtime-configuration.md`.

Ne jamais committer de secret serveur ni supposer une URL de production.

## Stockage

- Drift : projections allowlistées, sync sources, outbox, drafts et metadata de fichiers.
- Staging privé : captures/fichiers en préparation.
- Private Profile file store : actifs locaux durables autorisés.
- Cache média/cartes : reconstructible et isolé par Profile.
- Secure storage : JWT et petits secrets.

Déconnexion ou session expirée retirent les credentials sans effacer silencieusement DB, drafts, outbox ou fichiers privés.

## Android / iOS

L'identité Android déjà approuvée reste `com.makolo`. Le host Android est sous `mobile/android/`. Les plugins actuels exigent au moins API 24 ; MapLibre exige JDK 21 pour la compilation Android. Le bytecode de l'application reste ciblé Java/Kotlin 17.

Validation native :

```bash
flutter build apk --debug --flavor dev --dart-define-from-file=config/dev.json
```

Le workflow `Mobile APK` est uniquement manuel et exige une URL de bêta/test fournie explicitement au lancement.

Aucun host iOS n'est présent. Aucun bundle identifier, signing team, provisioning, App Group ou entitlement iOS n'est inventé.

## CI

- `Mobile CI` : sélection du scope réel du diff, format/analyze/codegen et tests impactés avec fallback sûr.
- `Mobile Android Build` : debug build seulement pour dependency/native impact.
- `Mobile Visual Golden Regression` : design/surfaces visuelles uniquement.
- `Mobile APK` : checkpoint manuel.

Un changement backend-only ne lance pas Flutter. Un changement mobile inconnu tombe sur la suite Flutter complète.

## Frontières métier

Le client ne recalcule jamais Readiness et ne crée jamais Permission, Mandate, Access, Capacity ou Payment. Il ne crée ni `/api/v1/mobile/`, ni `/sync/` générique, ni endpoint générique d'upload. Les owners métier possèdent leurs contrats et leur idempotence.
