# Makolo — Couvertures financées et attribution des bénéficiaires

**Statut : implémentation sur la branche de la PR #522.** Ce document décrit le comportement attendu du code courant, et non des offres commerciales nommées. Il n'atteste pas à lui seul l'exécution des tests ou le déploiement.

## 1. Responsabilités

- `SubscriptionPlan`, `PlanVersion`, `PlanEntitlement` et `FeatureDefinition` possèdent le catalogue. Plus, Max, Business, etc. ne sont que des données éventuelles configurées par Platform.
- `PlanVersionBillingTerms` possède le montant, la monnaie, la période, le mode tarifaire de couverture (`flat` ou `per_seat`) et le plafond de bénéficiaires. Ces paramètres sont figés après publication.
- `SubscriptionCoverage` possède une couverture achetée pour un cycle tarifaire exactement défini ; le financeur est Profil XOR Espace. Elle n'est ni la `Subscription` du bénéficiaire, ni une autorité sur ce dernier.
- `SubscriptionCoverageAllocation` possède l'attribution historisée. Cible XOR Profil/Espace/Groupe. Une cible Group est un périmètre de sélection, jamais un sujet final d'Entitlement. Une attribution nominative peut référencer `group_parent`.
- `PaymentObligation` est la vérité du paiement. `SubscriptionBillingObligation` utilise exactement une source : Subscription ordinaire ou Coverage financée.
- Le résolveur `resolve_effective_entitlements` incorpore les allocations effectives après consentement, état de la couverture, fenêtres temporelles, appartenance et Requirements.
- L'unique BASE effective est sélectionnée explicitement : la BASE personnelle reste stockée et réapparaît lorsque la couverture financée n'est plus effective.

## 2. Cycle d'achat et d'attribution

1. Un gestionnaire autorisé finance une `PlanVersion` publiée, avec `coverage_enabled` et quantité contractuelle.
2. Le backend calcule la période d'un cycle (jour/semaine/mois/an calendaire) suivant les Billing Terms. Une période arbitraire plus longue est rejetée.
3. Pour une couverture payante, elle reste `pending_payment` ; la réception d'un paiement satisfait via Payments fait progresser l'état. Un achat gratuit devient actif sans obligation positive.
4. Le financeur invite explicitement un bénéficiaire. L'invitation seule ne consomme pas de place et n'accorde aucun droit.
5. Une invitation nominative est acceptée par le bénéficiaire autorisé. Pour une BASE financée, le choix explicite `select_base=True` est requis.
6. Le service sérialise l'acceptation sous verrou PostgreSQL sur la couverture et la Subscription du bénéficiaire ; la capacité active ne dépasse pas `purchased_quantity`.
7. Le bénéficiaire peut refuser ou revenir à sa BASE personnelle, sans effacement d'historique et sans transférer ses données au financeur.
8. Suspension, remboursement (via le statut PaymentObligation), expiration, révocation ou départ du Groupe dynamique retirent la contribution financée, sans neutraliser des droits indépendants.

## 3. Groupes

- `Group`, `GroupMembership`, `GroupSnapshot` et `GroupSnapshotMember` restent propriétaires de la population.
- Une allocation de Groupe n'émet aucun droit personnel.
- En mode `current_members`, seuls les membres actifs, nommément invités et consentants, sont effectifs. Un départ coupe la contribution issue du Groupe.
- En mode `snapshot`, la population figée référence le snapshot existant.
- L'autorité de gestion d'un Groupe est contrôlée séparément de celle du financeur. Membership n'accorde aucune Permission/Mandate.

## 4. API native privée

Préfixe : `/api/v1/subscriptions/`

| Chemin | Action |
|---|---|
| `GET/POST me/coverages/` | Mes couvertures financées et reçues ; achat personnel |
| `POST me/coverages/<coverage_id>/allocations/` | Invitation nominative ou périmètre Groupe |
| `POST me/coverages/<coverage_id>/state/` | Suspension, reprise ou clôture |
| `POST me/allocations/<allocation_id>/<operation>/` | `accept`, `decline`, `select-base` |
| `POST me/base/personal/` | Retour à la BASE personnelle |
| `GET/POST spaces/<slug>/coverages/` | Même parcours dans le contexte Espace |
| `POST spaces/<slug>/coverages/<coverage_id>/allocations/` | Invitation sous autorité de l'Espace financeur |
| `POST spaces/<slug>/allocations/<allocation_id>/<operation>/` | Consentement via autorité de l'Espace bénéficiaire |
| `POST spaces/<slug>/base/personal/` | Retour à la BASE propre de l'Espace |

Toute mutation exige une authentification. Le financement d'Espace requiert `SPACE_SUBSCRIPTION_MANAGE`. Les réponses ont `Cache-Control: private, no-store`. La lecture d'une couverture reçue n'expose ni le financeur ni les données privées des autres bénéficiaires.

Les opérations sensibles exigent `idempotency_key` (8–128 caractères côté API). Les dates sont optionnelles : le serveur peut calculer un cycle exact. Pour un renouvellement explicite, `renewal_of` référence une couverture appartenant au même financeur.

## 5. Web / Platform

- Le catalogue Platform peut configurer les modalités des couvertures uniquement sur un draft, puis publier une version immuable.
- Moi et Nous présentent les couvertures reçues/financées et les actions d'acceptation, de refus et de sélection de BASE.
- Les capacités affichées suivent le résolveur effectif ; la BASE personnelle demeure accessible en repli.
- Il n'y a pas de création automatique d'une couverture à la simple adhésion à un Groupe.

## 6. Contrôles

Tests à faire fonctionner sur la branche : `subscriptions.test_funded_coverages`, `subscriptions.test_coverage_native_api`, `subscriptions.test_coverage_concurrency` (PostgreSQL), et les suites Subscription/Billing existantes. Vérifier `manage.py check`, `makemigrations --check --dry-run`, `migrate` et la rétrocompatibilité des obligations historiques.

Les interfaces graphiques web ne remplacent pas les règles serveur. Aucun ajout de `GroupSubscription`, `Seat` ou de nouveau système Payment.
