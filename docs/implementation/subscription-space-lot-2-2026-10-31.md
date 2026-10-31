# Subscription — Lot 2 : consommation de l'abonnement d'un Espace

**PR** : #522, branche `fix/discover-a-continuation-context-20261014`.
**Périmètre** : l'abonnement d'un Space explicite, différent de celui du Profile connecté.
**Principe** : réutiliser les domaines Subscription, Authorization, Payments et les projections serveur ; ne créer aucun état métier ni entitlement Flutter.

## Contrat

- L'autorité de consultation est résolue par `space.subscription.view` **ou** `space.subscription.manage`, sur le Space demandé.
- La mutation exige `space.subscription.manage` ; la lecture seule peut toujours ouvrir un aperçu de transition sans la confirmer.
- L'appartenance à une équipe, un rôle sur une Activity ou les entitlements personnels ne confèrent aucune autorité sur l'abonnement de l'Espace.
- Les fonctionnalités de l'Espace sont résolues avec `subscription.subject == Space`. Les entitlements du Profile restent inchangés.
- Les obligations Payment sont projetées seulement si l'acteur dispose aussi de `finance.view` pour cet Espace. `subscription.view` ne transfère pas le droit de consulter le détail financier.
- Une clé d'idempotence correspond à une intention précise pour une Subscription précise, même si l'Item d'origine est terminé lors d'une répétition réseau.

## Capacités réutilisées

| Capacité | Web Space | Flutter Space |
| --- | --- | --- |
| BASE, ADDONS, avantages | Console Subscription existante enrichie en BillingTerms | `BillingScreen` réutilisé, sujet Space explicite |
| Entitlements, usage, quotas, conditions | `SubscriptionProductView` existant | Projection `GET /api/v1/subscriptions/spaces/<slug>/` |
| Catalogue, éligibilité et aperçus | Services et vues existants | `.../plans/<version>/` |
| Changement de BASE / ADDON_ADD | POST Web existant | POST plan, clé d'idempotence |
| Retrait ADDON | GET preview et POST existants | `.../addons/<item>/remove/` |
| Annuler / finaliser | Façade S5 existante | `.../transitions/<transition>/<action>/` |
| Historique | `/spaces/<slug>/subscription/history/` | `.../transitions/`, pagination |
| Facturation | `/spaces/<slug>/subscription/billing/` | `.../obligations/`, pagination, sous autorité `finance.view` |
| Point d'entrée | Module Abonnement de la console Space | Handoff autorisé « Nous → Abonnement de cet Espace » |

## Routage et continuité Flutter

- Nouvelle route client `/space/:slug/subscription`, ouverte seulement si `SpaceActorContext.space.slug` correspond.
- La requête native valide aussi la valeur du `space.id` retourné contre le contexte sélectionné ; le nom d'un Space voisin ne peut pas remplacer celui de l'acteur courant.
- Un changement d'acteur invalide les données affichées. Une perte du droit de lecture (401/403/404) efface l'état précédent, sans continuer à montrer un abonnement devenu privé.
- Aucun achat, accès, paiement ou migration n'est confirmé localement : confirmation, statut, quotas et transition restent ceux du serveur.

## Projections et services

- `subscriptions/space_native_api_views.py` : façade Space autorisée, appelle les mêmes services `security_services`, `product_read`, `product_preview`.
- `subscriptions/billing_presentation.py`, `space_billing_view.py` : obligations avec exact `payer_space`, contrôle `finance.view`, `PaymentObligation` propriétaire.
- `subscriptions/personal_history.py` : historique `SubscriptionTransition` générique, entrée personnelle conservée.
- `subscriptions/authorization.py` : correction du cas `manage` sans `view` explicite.
- `organizations/console_subscription.py` : termes et historiques exposés via les vues existantes, sans nouveau modèle.
- `organizations/api/space_us_projection.py` : handoff serveur présent uniquement si une permission Subscription Space existe.
- `mobile/lib/features/settings/billing_screen.dart` et `subscription_actions_panel.dart` : composants partagés, mode Space et mode Profile strictement séparés.

## Scénarios ciblés ajoutés

`subscriptions/test_space_native_api.py` :
- anonyme, membre sans Mandate, VIEW, MANAGE ;
- catalogue et preview en lecture seule ;
- demande idempotente avec autorité MANAGE ;
- refus de transition croisée entre plusieurs Espaces ;
- termes, obligations et historique liés au bon `payer_space` ;
- non-transfert des obligations à la Subscription personnelle ;
- handoff « Nous » commandé par la permission ;
- correction `manage` implique lecture du même Espace.

`mobile/test/space_subscription_test.dart` :
- retour de la projection Space correcte ;
- disparition immédiate des données en passant à un autre acteur ;
- aperçu consultable sans confirmation lorsque `can_manage=false`.

**Statut** : implémentation poussée en PR #522. Tests ajoutés mais non déclarés exécutés dans cette session, à la demande explicite de ne pas suivre la CI.
