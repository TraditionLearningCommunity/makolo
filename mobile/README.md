# Makolo Mobile — Phase 0

Fondation Flutter du client natif Makolo dans le dépôt unique.

## Frontières

- Django reste source de vérité métier et d'autorisation.
- Flutter ne recalcule ni Readiness, ni Permission/Mandate, ni Access, ni Payment, ni Capacity.
- Aucune URL d'environnement, clé, token, bundle id ou application id n'est inventé ici.
- Les hôtes Android/iOS seront générés après décision canonique sur les identifiants et la distribution.

## Validation locale

```bash
cd mobile
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

Le backend sera fourni plus tard via configuration de runtime, jamais codé en dur.
