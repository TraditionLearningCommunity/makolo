# Subscription — Lot 2 : consommation de l'abonnement Space

Statut : implémentation poussée dans la PR #522, sans migration ni nouvel agrégat.
Ce document décrit le travail intégré ; il ne constitue pas un rapport d'exécution de tests.

## Contrat métier

- Un Space est le sujet de sa propre Subscription, distincte de celle du Profil.
- Voir une Subscription Space exige `space.subscription.view` ou `space.subscription.manage` selon l'autorisation canonique (et les autorités plateforme explicitement accordées).
- Gérer une Subscription Space exige `space.subscription.manage` (ou l'autorité plateforme canonique équivalente).
- TeamMembership, Assignment et contexte UI ne créent aucune autorité.
- La lecture des obligations détaillées de Payments exige séparément la permission financière applicable ; `space.subscription.view` ne suffit pas pour divulguer les obligations.
- Aucun Entitlement Space n'est ajouté au Profil.

## Façade native

- `GET /api/v1/subscriptions/spaces/<slug>/` : product snapshot de l'Espace sélectionné, `can_manage`, `can_preview`, BASE/ADDONS, capacités, conditions, historique et obligations autorisées.
- `GET /api/v1/subscriptions/spaces/<slug>/plans/<uuid>/` : preview en lecture, y compris pour le seul `view`.
- `POST /api/v1/subscriptions/spaces/<slug>/plans/<uuid>/` : demande BASE ou ADDON.
- `GET/POST /api/v1/subscriptions/spaces/<slug>/addons/<uuid>/remove/` : preview puis retrait.
- `POST /api/v1/subscriptions/spaces/<slug>/transitions/<uuid>/cancel|complete/` : commandes canoniques.
- `GET /api/v1/subscriptions/spaces/<slug>/transitions/` : historique paginé.
- `GET /api/v1/subscriptions/spaces/<slug>/obligations/` : projection financière si autorisée.

Chaque mutation vérifie les droits au serveur ; la clé d'idempotence est conservée, y compris après finalisation.

## Interfaces

Web : console `/spaces/<slug>/subscription/`, aperçu et commandes existants, vues facturation et historique distinctes, composition de termes financiers depuis `PlanVersionBillingTerms`.

Flutter : `/space/<slug>/subscription`, accessible depuis le handoff autorisé de « Nous » ; réutilise `BillingScreen` et `SubscriptionActionsPanel` par sujet (Profil ou Space), sans second état de facturation. Un changement d'acteur invalide l'affichage Space ; un sujet incohérent dans la réponse serveur est refusé. Les actions de mutation sont masquées en consultation seule.

## Validation ciblée

- `subscriptions/test_space_native_api.py` : isolation par Mandate, lecture seule, catalogue, idempotence, transitions cross-Space, séparation Profil/Space, obligations financières et handoff de « Nous ».
- `mobile/test/space_subscription_screen_test.dart` : lecture seule Space, changement d'acteur et refus d'une réponse d'un autre Space.
- Aucune CI demandée ni suivie. Les tests ne sont pas déclarés exécutés dans ce checkpoint.

## Hors périmètre

Lot 3 : vérification de l'enforcement réel dans les domaines propriétaires de `activities.create`, `team.members` et `custom_roles`. Aucune nouvelle Feature n'est inventée ici.
