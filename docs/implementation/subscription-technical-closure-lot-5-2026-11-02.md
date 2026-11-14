# Subscription — Lot 5 : fermeture technique et validation croisée

Date : 2 novembre 2026. Branche : PR #522 (`fix/discover-a-continuation-context-20261014`).

## Portée

Le lot 5 vérifie et durcit l'intégration des lots 1–4, **sans nouveau modèle, migration, Feature, paiement ni autorité**. Le runtime (code et tests) prime sur ce document ; la PR #522 agrège aussi de nombreux chantiers indépendants.

### Corrections réalisées

1. **Continuation Event sujet exact** : `events.views.EventCreateView` reconnaît `?space=<slug>` seulement si l'acteur possède `space.activities.manage`. Lors d'un refus Subscription sur création Event pour un Espace, le handoff vers sa Subscription conserve cette identité dans la reprise. La liste autorisée de `subscriptions/ux_continuation.py` refuse une reprise Event sans le même slug, un Event personnel avec slug Espace, les URL externes, les chemins admin, les query keys supplémentaires et les URL d'un autre Espace.
2. **Encodage de retour** : assertion corrigée pour ne pas produire `?next=next=...` dans le test d'aller-retour. `subscription_return_home` conserve un seul `next` validé, jamais une redirection vers l'extérieur.
3. **Race Flutter contexte acteur** : `SubscriptionActionsPanel` vérifie de nouveau l'identité du Space et la permission de gestion immédiatement **avant** le POST de preview confirmé. Un dialogue ouvert alors que l'acteur passe de Space A à Space B/Moi ne doit jamais envoyer une commande à A. Le serveur revalide systématiquement l'autorisation de toute façon.
4. **Concurrence quota d'équipe** : le test PostgreSQL `subscriptions/test_lot5_team_concurrency.py` fait concourir deux profils à une seule place libre, sous le verrou Organization. L'issue exigée est une admission et un refus structuré, avec exactement deux profils actifs (propriétaire inclus).

### Couverture CI renforcée sans affaiblir les gates

Dans `.github/workflows/subscriptions.yml` :
- test d'enforcement `subscriptions.test_lot3_enforcement` ajouté au shard catalogue/runtime ;
- `subscriptions.test_space_native_api` (lot 2) et `subscriptions.test_lot4_continuation` ajoutés au shard UX ;
- `subscriptions.test_lot5_team_concurrency` ajouté au shard PostgreSQL concurrence ;
- le mode fast/draft couvre également les tests des lots 2–4.

Dans `.github/workflows/mobile-ci.yml` :
- exécution explicite de `test/space_subscription_screen_test.dart` et `test/space_subscription_test.dart` après génération, contrôle du format, architecture et analyse existants ;
- ajout au test Flutter du cas « changer d'acteur pendant un aperçu de formule » : aucun POST de l'ancien Space ne doit être émis.

### Commandes de validation locale (à partir du HEAD réconcilié)

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test subscriptions.test_space_native_api subscriptions.test_lot3_enforcement subscriptions.test_lot4_continuation
# Avec PostgreSQL de test : 
python manage.py test subscriptions.test_lot5_team_concurrency
cd mobile
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test test/space_subscription_screen_test.dart test/space_subscription_test.dart
```

### Matrice d'acceptation avant merge

| Scénario | Preuve exigée |
| --- | --- |
| Profil personnel, Activity | action permise et refus Subscription réellement serveur, sans détournement vers le Space |
| Space A, Activity/Event | permission Space nécessaire et propriétaire logique préservé après retour |
| Space B | ni contexte, ni Billing, ni état conservé depuis A |
| Équipe | quota absent sans zéro fictif, quota présent sans double admission, Membership ≠ Mandate |
| Roles | `custom_roles` et autorité indépendants, pas de modification rétroactive |
| Formulaire Web | raison visible, lien propriétaire seulement avec droit de lecture, `next` filtré |
| Flutter | consultation seule, changer d'acteur invalide l'écran et le dialogue avant POST |
| Billing | permissions Payments séparées des permissions Subscription, pas de fuite de factures |
| Offre/changement | seul le serveur tranche Conditions/Eligibility/Payment et active l'Entitlement |
| Sécurité | IDOR, URL externe, réactivation legacy, idempotence, annulation/échec |
| Tests | PostgreSQL Subscription, Flutter format/analyze/test, CI pertinente toutes vertes |
| Après merge | HEAD `main` réconcilié, gates pertinentes confirmées |

### Limites de validation dans cette session

Le dépôt n'est pas clonable depuis le conteneur (DNS `github.com` inaccessible), et Dart/Flutter n'y est pas installé. Les corrections, tests et workflows sont poussés via l'intégration GitHub. **Ne pas considérer ces tests comme exécutés par ce document.** Les jobs GitHub Actions ont été relancés par les nouveaux commits ; inspecter leur résultat exact avant fermeture définitive et ne pas fusionner une PR avec CI rouge ou annulée.

Aucune modification directe de `main` et aucun test retiré, affaibli ou ignoré pour obtenir du vert.
