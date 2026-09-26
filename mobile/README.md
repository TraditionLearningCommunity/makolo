# Makolo Mobile — A1 Installed Core

Ce dossier contient la première implémentation réelle du client Flutter Makolo. Il part du contrat A0 et reste un client des vérités autoritatives du serveur.

## Architecture

```text
UI
↓
repositories / use-cases
↓
projection locale Drift + outbox
↕
sync owner-scoped
↕
API Makolo
```

Pour une donnée déjà synchronisée, l'UI lit la projection locale. Le réseau sert au bootstrap, au rafraîchissement, à la synchronisation, à la confirmation et aux opérations intrinsèquement distantes.

## Configuration

Aucune URL d'environnement n'est codée en dur. Fournir la base API au build/runtime :

```bash
flutter run --dart-define=MAKOLO_API_BASE_URL=https://<hote-autorise>
```

Ne jamais committer de secret, token ou URL de production supposée.

## Validation

Flutter 3.47.3 / Dart 3.13.3 sont les versions A1 pinées.

```bash
cd mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

## Stockage

- Drift : projections personnelles allowlistées, metadata de sync, outbox, drafts et metadata de fichiers.
- Cache : uniquement reconstructible.
- Stockage privé Makolo : documents/captures autorisés et non exposés automatiquement.
- Export utilisateur : uniquement par action explicite.
- Secure storage : JWT et petits secrets locaux.

Les stores sont isolés par Profile. Une déconnexion retire les credentials actifs mais ne détruit pas silencieusement une outbox locale.

## Android / iOS

L'identité Android approuvée est désormais :

```text
applicationId / namespace : com.makolo
```

Le host Android vit sous `mobile/android/` et suit les templates Flutter 3.47.3 (Gradle 9.3.1, AGP 9.1.0, Kotlin 2.4.0, Java 17). Les sauvegardes applicatives Android sont désactivées en A1 afin de ne pas restaurer aveuglément sessions, outbox ou données privées sur un nouvel appareil.

Validation Android :

```bash
flutter build apk --debug
flutter run -d <device-id> --dart-define=MAKOLO_API_BASE_URL=https://<hote-autorise>
```

Pour les APK de test générées par GitHub Actions, le workflow manuel `Mobile APK` demande l'URL API au déclenchement. Sa valeur bêta par défaut est `https://makolo.pythonanywhere.com`. Cette valeur est un environnement de test temporaire, pas une cible de production.

Aucune identité iOS n'est encore fixée : aucun `PRODUCT_BUNDLE_IDENTIFIER` n'est inventé et aucun host iOS n'est généré dans ce chantier.

## Frontières

A1 ne recalcule jamais Readiness, Permission, Mandate, Access, Capacity, Payment, inclusion Maintenant/En cours ni autre vérité métier. Il ne crée ni `/api/v1/mobile/` ni `/sync/` générique.
