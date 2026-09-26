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

Le dépôt canonique ne fixe encore aucun `applicationId` Android ni `PRODUCT_BUNDLE_IDENTIFIER` iOS. A0 interdit de les inventer et reporte l'identité native officielle à A4. Les hôtes natifs ne sont donc pas générés avec `com.example.*` ou un autre identifiant fictif dans cette branche. C'est un gate explicite à résoudre avec une identité approuvée avant de revendiquer un build installable Android/iOS.

## Frontières

A1 ne recalcule jamais Readiness, Permission, Mandate, Access, Capacity, Payment, inclusion Maintenant/En cours ni autre vérité métier. Il ne crée ni `/api/v1/mobile/` ni `/sync/` générique.
