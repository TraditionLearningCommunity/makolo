# Makolo — S3 Subscription Eligibility & Requirements

## Portée livrée

S3 étend le bounded context `subscriptions` au-dessus de S1 (catalogue/versioning) et S2 (Subscription/Items/Grants/Effective Entitlements). Le kernel horizontal `requirements` reste propriétaire de `RequirementMode`, `RequirementAssessmentState`, `RequirementEvaluationResult` et `EvaluatorRegistry`.

S3 ajoute :

- `PlanRequirement` ;
- `EntitlementRequirement` ;
- `PlanEligibilityResult` calculé à la demande ;
- résolution `available`, `conditionally_available`, `not_eligible`, `hidden` ;
- validation des Requirements à la publication d'une `PlanVersion` ;
- Requirements de Feature appliqués au resolver d'Entitlements effectifs ;
- evaluators Subscription contrôlés par le code.

S3 ne crée pas de table `SubscriptionRequirementAssessment` et ne matérialise aucune population Profile × Plan × Requirement.

## Evaluators réels

### `profile.account_age_days`

Sujet : Profile (`accounts.User`).

Donnée canonique : `User.created_at`.

Operators : `>=`, `>`, `==`, `<=`, `<`.

La valeur attendue est un entier de jours non négatif. Aucun état de vérification/Trust n'est inventé.

### `space.account_age_days`

Sujet : Space (`organizations.Organization`).

Donnée canonique : `Organization.created_at`.

Operators : `>=`, `>`, `==`, `<=`, `<`.

### `space.member_count`

Sujet : Space.

Donnée canonique : `organizations.TeamMembership`, limitée aux Teams actives et aux memberships `active`, avec comptage distinct des Profiles.

Operators : `>=`, `>`, `==`, `<=`, `<`.

Aucun compteur Subscription parallèle n'est créé.

Les metadata `dependency_events` restent vides en S3 : aucun nom d'événement canonique suffisamment stable n'est inventé uniquement pour remplir le registry. L'orchestration event-driven reste différée à S5.

## PlanRequirement

Une condition est attachée explicitement à une `PlanVersion` et porte notamment : clé, phase, mode T34A, evaluator/config éventuels, mandatory, position, failure policy, grace period et disclosure.

Phases : `acquisition`, `ongoing`, `renewal`.

Policies :

- acquisition : `block`, `deny` ;
- ongoing : `warn`, `grace`, `suspend` ;
- renewal : `block`, `deny`.

`grace_period_days` n'est accepté qu'avec `ongoing + grace` et ne déclenche encore aucune orchestration automatique.

Pour `automatic`, un evaluator connu et une configuration validée sont obligatoires. Les autres modes (`action`, `verification`, `external_check`, `payment`, `review`) peuvent rester sans evaluator : leur évaluation on-demand produit alors `pending` sans créer de workflow, Payment ou donnée fictive.

## Eligibility

`resolve_plan_eligibility(subject, plan_version)` évalue une version publiée précise.

- aucun Requirement bloquant : `available` ;
- mandatory acquisition Requirement non prêt avec policy `block` : `conditionally_available` ;
- mandatory acquisition Requirement non prêt avec policy `deny` : `not_eligible` ;
- catalogue `internal`, ou `staff_only` en contexte self-service : `hidden`.

`not_applicable` est non bloquant, comme dans T34A. Un Requirement optionnel n'affecte pas automatiquement l'état global.

Une erreur de registry/configuration lève une erreur de configuration catalogue ; elle n'est jamais convertie silencieusement en `not_eligible`.

## Disclosure

- `visible` : projection explicable avec valeurs scalaires minimales ;
- `generic` : motif générique sans détails evaluator ;
- `internal` : ni evaluator/config, ni actual/expected value, ni texte interne exposé.

## EntitlementRequirement

Un Requirement de Feature pointe explicitement vers `PlanEntitlement`. Il ne duplique pas `plan_version` ou `feature`.

Le resolver S2 conserve `effective_value`. Si un Requirement mandatory applicable n'est ni `satisfied` ni `not_applicable`, il force :

```text
allowed = false
reason_code = requirement_unsatisfied
```

La valeur commerciale/technique reste donc explicable. Un `EntitlementGrant` change la valeur agrégée mais ne contourne pas automatiquement les Requirements déjà attachés aux Entitlements actifs du Plan.

## Immutabilité et publication

Les Requirements sont modifiables uniquement tant que la `PlanVersion` est `draft`. Save/delete et mutations queryset sont protégés après publication/retrait.

`publish_plan_version(...)` revalide maintenant, dans la transaction de publication :

- les `PlanRequirement` ;
- les `EntitlementRequirement` ;
- evaluator keys ;
- configs/operators ;
- subject type ;
- phase/policy ;
- grace period.

Une configuration invalide interrompt la publication avant toute transition de statut.

## Persistance et effets de bord

Une consultation Eligibility est read-only métier :

- aucune `SubscriptionRequirementAssessment` ;
- aucune `PaymentObligation` ;
- aucun Journey ;
- aucune Notification ;
- aucune Transition.

## Migration

S3 ajoute `subscriptions/migrations/0005_subscription_requirements.py`.

Aucune migration S1/S2 n'est réécrite.

## Différé

### S4

`SubscriptionTransition`, matérialisation des Requirements en `SubscriptionRequirementAssessment`, base switch, add-on add/remove, transition idempotency/concurrency et Payment bridge.

### S5

Permissions Subscription finales, Domain Events, Notifications, Automation, dependency-event orchestration, grace/suspension automatiques et Staff review final.

### S6

UX Profile/Space/Staff Subscription, analytics produit et release hardening global.
