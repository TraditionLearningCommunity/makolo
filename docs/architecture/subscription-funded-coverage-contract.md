# Couvertures financées — contrat d'implémentation

**Statut : implémentation dans la PR #522, non fusionnée.**
**Domaine propriétaire : `subscriptions`.**
**Document de conception d'origine : `Makolo_Contrat_Couvertures_Financees_2026-11-03.md` (transfert projet).**

## Promesse

Un Profil ou un Espace finance une offre versionnée pour des bénéficiaires distincts (Profils, Espaces ou périmètre de Groupe), sans obtenir leurs permissions, mandats, activités ou données privées. Le financement est distinct de l'abonnement ordinaire du bénéficiaire.

Le catalogue reste générique : les noms de plans, leurs prix et les quantités sont des instances de `SubscriptionPlan`, `PlanVersion` et `PlanVersionBillingTerms`. Aucun nom commercial n'est codé en dur.

## Sources de vérité

- `Subscription` et `SubscriptionItem` restent exclusivement Profile XOR Space.
- `SubscriptionCoverage` représente un achat financé, son payeur Profile XOR Space, son `PlanVersion` publiée, ses termes tarifaires figés, son prix/quantité et sa fenêtre contractuelle.
- `SubscriptionCoverageAllocation` représente les attributions historiques, cibles Profile XOR Space XOR Group. Une attribution à Group qualifie une population : elle ne produit jamais directement d'Entitlement.
- `GroupMembership` et `GroupSnapshotMember` restent propriétaires de l'éligibilité des membres. Une attribution personnelle consentie peut se rattacher à une attribution Group par `group_parent`.
- `SubscriptionBillingObligation` applique deux chemins XOR : Subscription ordinaire ou `SubscriptionCoverage`; `PaymentObligation` demeure la vérité financière.
- `PlanEntitlement` est résolu par la provenance : BASE/ADDON du bénéficiaire, couverture financée active et acceptée, grants administratifs. Aucune copie aveugle en `EntitlementGrant`.
- Les `PlanRequirement` et `EntitlementRequirement` sont évalués pour la version financée ; évaluation invalide = droit non accordé.

## Tarification et durée

`PlanVersionBillingTerms` a des attributs de couverture optionnels (`coverage_enabled`, `coverage_pricing_mode`, `coverage_max_quantity`). Seuls les brouillons sont configurables via le catalogue Platform.

- **flat** : achat de la capacité forfaitaire exacte, un montant par cycle.
- **per_seat** : prix unitaire multiplié par quantité achetée, dans la limite publiée.
- La fenêtre `starts_at → ends_at` couvre **exactement un cycle tarifaire** défini par les termes figés. Un achat ne peut pas payer un mois pour déclarer un an.
- Chaque nouvelle période requiert une nouvelle couverture ou un renouvellement explicite. La date d'expiration coupe les contributions même si l'état administratif n'a pas encore été matérialisé en `ended`.
- Gratuit : aucune obligation positive fictive. Payant : `PaymentObligation` créée pour le payeur, plateforme bénéficiaire ; activation seulement après règlement.
- Suspension de la couverture coupe uniquement ses propres droits. La BASE personnelle du bénéficiaire reste persistée.

## Flux serveur

1. Le payeur autorisé crée une couverture versionnée (création idempotente, verrouillage transactionnel).
2. Le payeur invite individuellement des Profils/Espaces ou déclare un Groupe qualifiant.
3. Un Profil ne reçoit des droits effectifs qu'après invitation nominative, éligibilité et acceptation explicite. La même règle s'applique à un Espace via Permission.
4. Une attribution personnelle issue d'un Groupe doit toujours satisfaire sa politique : membres courants ou snapshot.
5. La capacité se calcule par nombre d'attributions effectives simultanées, hors racines de Groupe.
6. Une BASE financée n'entre dans la résolution que si elle a été explicitement choisie ; l'ancienne BASE personnelle reste disponible en repli.
7. Refus, révocation, échéance, sortie d'un Groupe dynamique, suspension ou impayé retirent uniquement la contribution correspondante.
8. Les changements émettent des Domain Events typés, avec identifiants de sources seulement, sans données personnelles de consommation.

## API native

Sur les routes existantes `api/v1/subscriptions/` :

- `me/coverages/` : couvertures personnelles financées/reçues et achat.
- `me/coverages/allocations/<uuid>/` : acceptation, refus, choix de BASE ou retour au BASE personnel.
- `spaces/<slug>/coverages/` : couvertures financées/reçues par un Espace, selon les permissions de Subscription.
- `spaces/<slug>/coverages/allocations/<uuid>/` : décision d'un gestionnaire autorisé au nom de l'Espace.
- `coverages/<uuid>/` : consultation d'une couverture par son financeur.
- `coverages/<uuid>/allocations/` : invitations contrôlées (Profil/Espace/Groupe).
- `coverages/<uuid>/status/` : suspension, reprise, terminaison justifiées.

Les projections de financement montrent prix/obligations **uniquement si** `payments.selectors.obligations_visible_to(actor)` accorde cette visibilité. Aucun endpoint ne donne au financeur la consommation privée des bénéficiaires. Toutes les réponses de ces vues sont `private, no-store`.

Web : vue Moi abonnement et console Nous montrent les allocations reçues, le choix/retour de BASE et le suivi minimal des couvertures financées.

## Points de contrôle

- Deux modèles persistants ajoutés dans `subscriptions/migrations/0009_financed_coverages.py`. Aucun changement destructeur ou backfill des souscriptions historiques.
- Décompte des places sous verrou de couverture ; `Subscription` du destinataire verrouillée lors de choix BASE pour sérialiser les conflits.
- Protection serveur contre IDOR et déduction d'appartenance : acteur bénéficiaire ou Permission `SPACE_SUBSCRIPTION_MANAGE` ; financeur Profil propriétaire ou financeur Espace autorisé ; gestion du Groupe requiert `GROUP_MANAGE`.
- Tests : `subscriptions.test_funded_coverages`, `subscriptions.test_funded_coverage_native_api`, `subscriptions.test_funded_coverage_concurrency` (PostgreSQL), et régressions Subscription historiques.

## Exclusions conservées

Pas de `GroupSubscription`, `GiftSubscription`, `Seat` ni de `GroupEntitlement` supplémentaire ; pas de droit/autorité transmis par paiement, Membership ou Group ; pas de prix codé en dur ; pas de réecriture des `SubscriptionItem` historiques.

**Limite opérationnelle :** ce document décrit le code livré dans #522 et ses invariants prévus ; il ne remplace pas les résultats effectifs de migrations, de tests PostgreSQL ni de revue de sécurité avant déploiement.
