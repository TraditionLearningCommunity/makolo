# Subscription — Lot 1 : consommation personnelle Web + Flutter

**Chantier** : PR #522, branche `fix/discover-a-continuation-context-20261014`.
**Périmètre** : uniquement Subscription du Profil authentifié. Les Entitlements d'un Space ne sont jamais hérités par son Profil.
**Nature** : composition en lecture et consommation des services existants ; aucun nouveau modèle, migration, provider ou état de paiement.

## Sources canoniques consommées

- `SubscriptionProductView` : BASE, ADDONS, Effective Entitlements, catalogue, exigences continues, dernière Transition.
- `build_subscription_change_preview` : différence des capacités, quotas, warnings et conditions divulguables.
- `request_subscription_transition_for_actor`, `cancel_subscription_transition_for_actor`, `complete_subscription_transition_for_actor` : actions réelles du domaine.
- `PlanVersionBillingTerms` : termes de la version épinglée ou publiquement acquérable.
- `SubscriptionBillingObligation`, `SubscriptionTransitionPaymentObligation` et `PaymentObligation` : obligations liées à l'abonnement, sans doublon et limitées au payer Profil.
- `SubscriptionTransition` : historique paginé des demandes, sans champ de review interne.

## Surfaces fermées

| Action | Web | Flutter |
| --- | --- | --- |
| Situation personnelle | `/subscription/` | `/billing` |
| BASE, ADDONS, avantages et capacités effectives | `SubscriptionProductView` enrichi en lecture | Projection native `/api/v1/subscriptions/me/` |
| Catalogue et preview | Vues `subscriptions:web_views` | GET `/api/v1/subscriptions/me/plans/<uuid>/` |
| Changement BASE / ajout ADDON | POST Web existant | POST même ressource API, avec idempotency key |
| Retrait ADDON | POST Web existant | GET preview puis POST `.../addons/<uuid>/remove/` |
| Annulation / finalisation | Actions Web existantes | POST `.../transitions/<uuid>/cancel/|complete/` |
| Historique des transitions | `/subscription/history/` | GET `/api/v1/subscriptions/me/transitions/` |
| Facturation personnelle | `/subscription/billing/` | GET `/api/v1/subscriptions/me/obligations/` |
| Paiement d'une obligation | `payments:obligation-start` si payable | `/payments/obligations/:id` (parcours Payments existant) |

La pagination de l'historique et des obligations est privée, ordonnée et bornée ; les réponses API sont `private, no-store`. Le dernier état serveur reste autoritaire. Les conditions `INTERNAL` n'apparaissent pas dans les previews ou l'avancement. Les actions ne sont pas confirmées hors ligne.

## Points d'attention pour le lot 2 et le lot 3

- Lot 2 : brancher les mêmes services et projections sur un **Space explicitement sélectionné**, avec permissions `space.subscription.view/manage` et Mandates. Ne jamais recycler la route personnelle pour un Space.
- Lot 3 : vérifier les consommateurs métier de `activities.create`, `team.members` et `custom_roles` dans leurs propres services, sans reproduire leurs décisions côté Flutter.
- L'historique personnel n'est pas un modèle UX ; c'est une projection de `SubscriptionTransition`.
- La facturation n'est pas un nouvel agrégat ; `PaymentObligation` reste propriétaire des états.
- Les listes et cartes ne fabriquent aucun tarif ou entitlement manquant.

## Tests ciblés ajoutés

- `subscriptions/test_native_api.py` : idempotence d'un retrait finalisé, clé d'intention incompatible, contrats tarifaires, paiement Profile-only, pagination, historique Web/API.
- `mobile/test/subscription_personal_flow_test.dart` : consommation des termes réels, avantages, usage dépassé, conditions et historique.
- Conserver les tests préexistants Web et Flutter sans les affaiblir.

**Validation de branche** : intégration poussée sur #522. Les tests ajoutés ne sont pas déclarés exécutés ici ; la demande utilisateur écarte le suivi CI de ce lot.
