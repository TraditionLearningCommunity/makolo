# Makolo Mobile — A1 Installed Core

Ce dossier contient le client Flutter Makolo A1. Il reste un client local-first des vérités autoritatives du serveur.

## Architecture

```text
UI
↓
repositories / use-cases
↓
projection locale Drift + drafts + outbox
↕
sync owner-scoped
↕
API Makolo
```

Pour une donnée déjà synchronisée, l'UI lit le store local. Le réseau sert au bootstrap, au rafraîchissement, à la synchronisation, à la confirmation et aux opérations intrinsèquement distantes.

## Behavior foundation

A1 fournit les comportements transversaux que les expériences suivantes réutilisent :

- contenu et synchronisation sont deux axes d'état distincts ;
- un refresh conserve le contenu local et ajoute un indicateur discret ;
- offline conserve le contenu disponible ;
- skeleton pour chargement initial perceptible, pas de spinner universel ;
- erreurs persistantes et récupérables pour les échecs importants ;
- feedback distinct pour stockage local, pending, synchronisé et confirmé ;
- toast/undo pour feedback léger et actions réellement réversibles ;
- confirmation pour actions destructives ou sensibles ;
- bottom sheet générique ;
- récupération de session vers le dernier contexte utile ;
- permission explainer sans permission OS au lancement ;
- Reduce Motion via `MediaQuery.disableAnimations` ;
- haptics encapsulés ;
- fondation NotificationRouter sans push réel.

La navigation primaire reste :

```text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
```

Le Mark est une action centrale. Il préserve l'historique afin que le back système revienne au contexte précédent.

## Configuration

Aucune URL d'environnement n'est codée en dur. Fournir la base API au build/runtime :

```bash
flutter run --dart-define=MAKOLO_API_BASE_URL=https://<hote-autorise>
```

Ne jamais committer de secret, token ou URL de production supposée.

## Validation locale

Flutter 3.47.3 / Dart 3.13.3 sont les versions A1 pinées.

```bash
cd mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

## Stockage et récupération

- Drift : projections personnelles allowlistées, metadata de sync, outbox, drafts et metadata de fichiers.
- Cache : uniquement reconstructible.
- Stockage privé Makolo : documents/captures autorisés et non exposés automatiquement.
- Export utilisateur : uniquement par action explicite.
- Secure storage : JWT et petits secrets locaux.

Les stores sont isolés par Profile. Une déconnexion ou une session expirée retire les credentials actifs mais ne détruit pas silencieusement la DB, les drafts ni l'outbox. Après reconnexion, A1 peut restaurer le dernier contexte de navigation utile du processus courant.

## Android / iOS

L'identité Android approuvée est :

```text
applicationId / namespace : com.makolo
```

Le host Android vit sous `mobile/android/` et suit les templates Flutter 3.47.3 (Gradle 9.3.1, AGP 9.1.0, Kotlin 2.4.0, Java 17). Les sauvegardes applicatives Android sont désactivées afin de ne pas restaurer aveuglément sessions, outbox ou données privées sur un nouvel appareil.

Validation Android :

```bash
flutter build apk --debug
flutter run -d <device-id> --dart-define=MAKOLO_API_BASE_URL=https://<hote-autorise>
```

Le workflow manuel `Mobile APK` peut construire un APK de test contre `https://makolo.pythonanywhere.com`. PythonAnywhere est uniquement un environnement temporaire de test/bêta, jamais une cible de production finale.

Aucune identité iOS n'est encore fixée : aucun `PRODUCT_BUNDLE_IDENTIFIER` n'est inventé et aucun host iOS n'est généré dans A1.

## CI

Le gate A1 Behavior utilise les mêmes checks rapides ; aucun workflow parallèle n’est introduit.

- `Mobile CI` : checks Flutter rapides.
- `Mobile Android Build` : compilation Android lorsque nécessaire.
- `Mobile APK` : packaging manuel/checkpoint.

Le build Android génère le code Drift avant compilation.

## Frontières

A1 ne recalcule jamais Readiness, Permission, Mandate, Access, Capacity, Payment, inclusion Maintenant/En cours ni autre vérité métier. Il ne crée ni `/api/v1/mobile/` ni `/sync/` générique.

A1 ne livre pas les expériences complètes A2, le push réel, caméra/GPS, scanner offline, OfflineGrant ni autorité Access/Capacity offline.
