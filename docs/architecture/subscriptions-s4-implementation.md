# Subscriptions S4 — Transitions, Assessments & Payment Bridge

## Status

S1 ✅ Catalogue

S2 ✅ Runtime Subscription / SubscriptionItem / Effective Entitlements

S3 ✅ Eligibility & Requirements catalogue

S4 ✅ Backend transition workflow in this implementation

S5 différé : authorization finale, Domain Events complets, Notifications, Automation et lifecycle orchestré.

S6 différé : UX Profile/Space/Staff, analytics produit, E2E UX final, accessibilité et release hardening.

Pricing/billing réel reste différé.

## Base et principe

S4 a été démarrée depuis le `main` vert `878f71d914a2db968d1d7fcc0727d4e2dfaeef70`, après la correction post-PR #95 apportée par la PR #96.

Règle d’architecture :

> Une consultation est une projection. Une Transition est une intention persistée. Une completion est une mutation atomique.

`SubscriptionTransition` n’est pas une `Journey`. Aucun Journey n’est créé par S4 pour représenter un changement d’abonnement.

## Modèles

### SubscriptionTransition

Agrégat persistant de changement d’abonnement.

Types :

- `base_switch`
- `addon_add`
- `addon_remove`

Lifecycle :

- `requested`
- `in_progress`
- `ready`
- `completed`
- `rejected`
- `cancelled`
- `expired`
- `failed`

La Transition pinne une `target_plan_version` exacte. Un `base_switch` conserve aussi la `source_plan_version`. Un `addon_remove` pinne l’`source_item` historique ainsi que sa PlanVersion exacte comme cible sémantique du retrait.

Une contrainte DB impose une seule Transition ouverte (`requested`, `in_progress`, `ready`) par Subscription. Une seconde contrainte rend `(subscription, idempotency_key)` unique.

### SubscriptionRequirementAssessment

Les Assessments ne sont créés que pour une Transition réelle et uniquement pour les `PlanRequirement` d’acquisition de la PlanVersion cible pinnée.

Le state réutilise directement `requirements.RequirementAssessmentState` :

- `unassessed`
- `pending`
- `satisfied`
- `unsatisfied`
- `not_applicable`

Aucune enum Requirement parallèle n’est introduite.

Les valeurs conservées restent minimales : `reason_code`, `actual_value`, `expected_value`, timestamps, acteur et note concise.

### SubscriptionRequirementAssessmentEvent

Historique append-only local des changements significatifs d’état d’un Assessment. Il ne remplace pas le chantier Domain Events S5 : il permet seulement de reconstruire les transitions d’état persistées S4 sans réécrire l’historique.

### SubscriptionTransitionPaymentObligation

Bridge détenu par `subscriptions` entre une Transition/Assessment payment et `payments.PaymentObligation`.

`payments` ne reçoit aucune FK vers `subscriptions`.

### SubscriptionItem.created_via_transition

Relation additive et nullable permettant de relier un Item créé pendant S4 à la Transition qui l’a créé. Les Items S2 historiques ne sont pas réécrits.

## Request et Eligibility

`request_subscription_transition(...)` :

1. verrouille la Subscription ;
2. valide le type de Transition ;
3. pinne source/cible ;
4. valide subject type, Plan actif et PlanVersion publiée ;
5. applique S3 Eligibility pour les acquisitions ;
6. refuse `hidden` / `not_eligible` en self-service ;
7. garantit idempotence et absence de Transition ouverte concurrente ;
8. crée la Transition ;
9. matérialise les Requirements d’acquisition nécessaires ;
10. évalue les modes `automatic` sans effet de bord ;
11. laisse `action`, `review`, `verification`, `external_check`, `payment` en `pending` ;
12. calcule readiness.

`staff_only` est refusé par le chemin self-service et peut seulement être demandé avec `request_origin=staff`. Cela ne remplace pas l’Authorization S5.

## Requirements et re-evaluation

Les Requirements automatiques utilisent `requirements.registry.registry` et `RequirementEvaluationResult`.

Les modes manuels ne sont jamais satisfaits artificiellement. `record_transition_requirement_decision(...)` fournit une primitive backend explicite pour une décision future, exigeant un acteur authentifié mais sans introduire la matrice de permissions finale S5.

`reevaluate_transition_requirements(...)` réévalue uniquement les modes automatiques et synchronise les Assessments payment. Les décisions manuelles ne sont pas réinitialisées.

## Payment bridge

La vérité financière reste `PaymentObligation`.

S4 n’introduit pas :

- `SubscriptionPayment` ;
- `Subscription.is_paid` ;
- prix de Plan ;
- cycle de facturation ;
- devise de catalogue ;
- invoice/tax/recurrence ;
- provider production.

Le runtime T33 actuel exige encore une `Journey` pour créer une `PaymentObligation`. S4 ne contourne pas cette contrainte et ne crée pas de Journey artificielle. Un Requirement `payment` est donc matérialisé `pending`, puis une obligation canonique déjà créée par le propriétaire financier compétent peut être liée via `link_transition_payment_obligation(...)`.

Synchronisation :

- obligation `pending` / `processing` → Assessment `pending` ;
- tentative Payment failed mais obligation restaurée/open → Assessment reste `pending` ;
- obligation `satisfied` → Assessment `satisfied` ;
- obligation `waived` → Assessment `satisfied`.

La sémantique T33 de `PaymentEvidence` reste inchangée : une preuve externe soumise ne satisfait pas l’obligation ; une preuve vérifiée satisfait l’obligation sans créer de faux `Payment`. Après changement de statut de l’obligation, `sync_transition_payment_assessment(...)` projette cet état sur S4.

La création générique d’une PaymentObligation sans Journey n’est pas ajoutée silencieusement par S4 ; ce changement de contrat Payments nécessitera une décision canonique séparée si le futur pricing Subscription doit créer directement ses obligations.

## Readiness

`evaluate_transition_readiness(...)` rend la Transition `ready` lorsque tous les Requirements obligatoires matérialisés sont :

- `satisfied`, ou
- `not_applicable`.

Un Requirement optionnel pending n’est pas bloquant. Les conséquences `payment_required`, `action_required`, `needs_review`, `waiting_verification` sont des projections de `get_transition_progress(...)`, pas des statuts de Transition.

Readiness ne complète pas la Transition.

## Completion

`complete_subscription_transition(...)` est séparé de readiness, transactionnel et idempotent.

### base_switch

- lock Transition + Subscription + BASE actif ;
- vérifie que le BASE source pinné est encore le BASE actif ;
- termine l’ancien Item avec `ends_at` et `ended_reason` ;
- crée l’Item cible avec `created_via_transition` ;
- s’appuie sur la contrainte DB S2 qui interdit deux BASE actifs ;
- marque la Transition `completed` dans la même transaction.

Aucun état avec zéro ou deux BASE actifs n’est commité : toute erreur rollback l’ensemble.

### addon_add

Crée un Item actif sur la PlanVersion cible exacte. La contrainte S2 `subscription + plan` empêche deux Items actifs du même add-on logique.

### addon_remove

Termine l’Item pinné ; la ligne n’est jamais supprimée. `starts_at`, `ends_at` et `ended_reason` conservent l’historique.

## Preview

`preview_subscription_change(...)` est un DTO/read model sans mutation.

Il expose :

- version courante/cible ;
- Features gagnées/perdues ;
- changements de quotas ;
- usage courant et `over_limit_after_change` ;
- Requirements de la cible ;
- Requirements payment ;
- résultat S3 Eligibility ;
- warnings.

Le preview ne crée ni Transition, ni Assessment, ni PaymentObligation, ni SubscriptionItem.

Un downgrade ne supprime aucune donnée. La policy S2 `preserve_existing_block_new` reste canonique.

## Concurrence

S4 combine :

- `transaction.atomic` ;
- `select_for_update` sur Subscription/Transition/Items ;
- contrainte DB une Transition ouverte ;
- unicité DB d’idempotency key ;
- contraintes S2 sur BASE/ADDON actifs.

Scénarios PostgreSQL couverts :

- deux `base_switch` concurrents ;
- deux requests simultanées avec la même idempotency key ;
- completion concurrente de la même Transition ;
- completion concurrente d’un `addon_add`.

## Migration

S4 ajoute :

- `subscriptions/migrations/0006_subscription_transitions.py`

Migration additive uniquement. Les migrations S1/S2/S3 ne sont pas réécrites.

## Tests et CI

Le workflow canonique `.github/workflows/subscriptions.yml` est étendu, sans nouveau workflow parallèle permanent.

Suites S4 :

- `subscriptions.test_s4_transitions`
- `subscriptions.test_s4_concurrency` sous PostgreSQL

Les gates finaux doivent aussi conserver verts : S1, S2, S3, T34A/`requirements`, T33 Payments, `postgresql-core`, `postgresql-ops`, Beta seed, Django, frontend build, E2E et security checks.

## Différé S5

S4 n’absorbe pas :

- `space.subscription.view`
- `space.subscription.manage`
- `platform.subscriptions.*`
- anti-IDOR final
- Domain Events Subscription complets
- Notifications
- Automation
- dependency-event orchestration
- grace/suspension automatiques
- eligibility-became-available
- Staff review UX et permissions finales

## Différé S6

S4 n’absorbe pas :

- Profile Subscription UX
- Space Subscription UX
- Staff Subscription Console
- analytics produit finaux
- E2E UX complet
- accessibilité finale
- performance hardening final
- release gate
