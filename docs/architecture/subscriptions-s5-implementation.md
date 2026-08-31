# Makolo — Subscription S5 implementation

## Statut

Ce document décrit l'implémentation de **S5 — Subscription Authorization, Domain Events, Notifications & Automation** portée par la PR S5. La base réelle vérifiée au démarrage était `main` à `9b3662d461e3241085047adc26768dbdb54a0b5a`, avec S4 déjà mergée via la PR #97 et les correctifs postérieurs de la PR #100.

S5 compose le runtime S1–S4 existant. Elle ne recrée ni catalogue, ni Entitlements, ni kernel Requirements, ni workflow de Transition, ni vérité financière.

## Séparation des responsabilités

Les invariants restent :

```text
Permission != Entitlement != Requirement
actor != Subscription subject
```

`authorization` décide qui peut agir. `subscriptions` décide de l'état produit. `payments` reste propriétaire des états financiers. Les Domain Events décrivent les faits committés; Notifications et Automation les consomment.

## Authorization

### Permission codes

Espace :

```text
space.subscription.view
space.subscription.manage
```

Plateforme :

```text
platform.subscriptions.catalog.view
platform.subscriptions.catalog.manage
platform.subscriptions.view
platform.subscriptions.manage
platform.subscriptions.grants.manage
platform.subscriptions.reviews.manage
```

Aucune permission billing n'est introduite : le runtime courant ne possède pas de billing Subscription complet.

### Bundles système initiaux

| Acteur / rôle | View | Manage | Grants | Reviews |
| --- | --- | --- | --- | --- |
| Profile sur sa propre Subscription | oui, self-authority | oui, self-authority | non | non |
| `space-owner` sur son Space | oui | oui | non | non |
| `space-admin` sur son Space | oui | non par défaut | non | non |
| rôle Space personnalisé | selon Permissions | selon Permissions | non | non |
| TeamMember sans Mandate | non | non | non | non |
| outsider | non | non | non | non |
| Django `is_staff` sans Mandate | non | non | non | non |
| `makolo-platform-admin` | oui plateforme | oui plateforme | oui | oui |

Un rôle Space personnalisé peut déléguer les permissions Space. Un simple `TeamMembership` n'est jamais une autorité.

### Selectors et façades anti-IDOR

`subscriptions.authorization` fournit des queries déjà scoppées avant chargement de l'objet :

```text
get_subscription_for_actor
a get_profile_subscription_for_actor
get_space_subscription_for_actor
get_transition_for_actor
get_subscription_assessment_for_actor
get_entitlement_grant_for_actor
```

Les mutations exposables passent par `subscriptions.security_services` pour demander/annuler/compléter une Transition et créer/révoquer un Grant. Les primitives S2/S4 restent des primitives de domaine internes; la façade S5 porte l'Authorization applicative.

Les Grants sont des exceptions plateforme : la self-authority d'un Profile et `space.subscription.manage` ne donnent pas `platform.subscriptions.grants.manage`.

## Reviews humaines

`review_subscription_requirement(...)` exige `platform.subscriptions.reviews.manage`, verrouille l'Assessment par `select_for_update`, accepte seulement un Requirement `review` encore `unassessed/pending`, puis réutilise le service S4 de décision.

L'audit append-only S4 conserve l'acteur, la date, l'état et le reason code. Deux reviewers concurrents ne peuvent pas écraser silencieusement une décision terminale.

## Domain Events

S5 utilise exclusivement l'outbox canonique `domain_events`. Aucun second publisher/outbox Subscription n'est ajouté. `emit_domain_event(...)` conserve la transaction, l'idempotence du producer et l'idempotence persistante des consumers.

### Faits Subscription publiés

```text
subscription.transition.requested
subscription.transition.ready
subscription.transition.completed
subscription.transition.rejected
subscription.transition.cancelled
subscription.transition.failed
subscription.transition.expired
subscription.requirement.changed
subscription.plan.changed
subscription.addon.activated
subscription.addon.removed
subscription.grace.started
subscription.grace.ended
subscription.suspended
subscription.reactivated
subscription.eligibility.available
```

`subscription.plan.changed` / `addon.activated` / `addon.removed` sont dérivés uniquement d'une Transition `completed` réelle.

Les payloads restent minimaux : IDs d'agrégat/sujet/Transition/PlanVersion/Requirement, ancien et nouvel état, disclosure et échéance éventuelle. Ils n'embarquent ni token, secret, document, `actual_value` interne ni payload financier complet.

`subscription.requirement.changed` n'est émis que lorsqu'un état/reason significatif change, pas à chaque lecture.

## Organizations -> Subscription dependency event

S5 ajoute dans le domaine propriétaire Organizations :

```text
organization.team_membership.changed
```

Le payload contient le `space_id`, l'identifiant de membership et les anciens/nouveaux statuts. Organizations ne dépend pas de Subscriptions.

L'evaluator S3 :

```text
space.member_count
```

déclare désormais ce fait dans `dependency_events`. Les evaluators temporels `profile.account_age_days` et `space.account_age_days` restent sans faux événement quotidien.

## Eligibility ciblée

Le consumer `subscriptions.dependencies` reçoit un événement avec un sujet Space explicite. Il :

1. résout uniquement ce Space;
2. identifie les evaluator keys dont `dependency_events` contient ce type d'événement;
3. réévalue l'éventuelle Subscription de ce Space;
4. charge uniquement les PlanVersions publiées, publiques, self-service, Space et possédant un Requirement d'acquisition lié à ces evaluators;
5. publie `subscription.eligibility.available` si le Plan est actuellement `available`.

La déduplication producer est :

```text
subscription-eligibility:<space>:<plan_version>
```

Il n'existe aucune table `subject x plan` et aucun scan de tous les Profiles/Spaces.

Les plans `internal`, non publics ou `staff_only` ne déclenchent pas cette notification promotionnelle.

## Notifications

`notifications.subscriptions` consomme les facts utiles au produit :

- Transition ready/completed/rejected/expired;
- Requirement devenu unsatisfied;
- grace started/ended;
- suspended/reactivated;
- eligibility available.

La déduplication suit le pattern Notifications canonique :

```text
domain:<domain_event>:<recipient>:<template>
```

`create_notification(...)` continue de gérer préférences e-mail, quiet hours, delivery queue et retries.

Destinataires :

- Profile : le sujet lui-même;
- Space : uniquement les Profiles actifs disposant de `space.subscription.view` via Mandate.

Disclosure :

- `internal` : aucun détail Requirement n'est notifié;
- `generic` : message générique;
- `visible` : seul le titre autorisé du Requirement peut être repris.

## Ongoing Requirements

S5 réutilise `RequirementMode`, `RequirementAssessmentState`, `RequirementEvaluationResult` et le registry T34A. Aucun second moteur de règles n'est créé.

Une persistence minimale non polymorphe est ajoutée :

```text
SubscriptionOngoingRequirementState
  subscription
  plan_requirement
  state
  reason_code
  first_unsatisfied_at
  last_evaluated_at
```

Elle sert uniquement à détecter un vrai changement/idempotence pour les Requirements ongoing d'une Subscription active. Elle ne copie ni le Plan, ni la Feature, ni le sujet et ne matérialise pas l'Eligibility globale.

`evaluate_subscription_ongoing_requirements(subscription)` verrouille la Subscription et évalue seulement les Requirements `ongoing + automatic` attachés à ses Items actifs.

Policies :

- `warn` : Subscription reste active;
- `grace` : `active -> grace`, avec `grace_until` calculé une seule fois à partir de `grace_period_days`; les réévaluations ne prolongent pas l'échéance;
- `suspend` : `active/grace -> suspended` sans destruction de données;
- recovery : retour vers `active` uniquement après agrégation de tous les blockers applicables;
- une suspension/grace dont `status_reason` n'appartient pas au lifecycle `ongoing_*` n'est jamais réactivée arbitrairement par S5.

Plusieurs Requirements sont évalués ensemble avant la décision globale; `suspend` domine `grace`, et `warn` n'entraîne pas de suspension.

## Effective Entitlements pendant suspension

La source contractuelle reste intacte : PlanEntitlement, SubscriptionItem et EntitlementGrant ne sont pas mutés lors d'une suspension.

Le resolver conserve :

```text
effective_value
sources
usage
remaining
```

mais une Subscription `suspended` rend la capacité indisponible :

```text
allowed = false
reason_code = subscription_suspended
```

S5 ne supprime aucune Activity, membre, donnée CRM, Event ou historique.

## Automation

Le scheduler canonique appelle `run_subscription_deadlines(...)`. Cette primitive ne parcourt ni Profiles, ni Spaces, ni Plans : elle sélectionne uniquement les lignes dont une échéance indexable est déjà due.

Cas livrés :

```text
Subscription grace + grace_until <= now
  -> evaluate_subscription_ongoing_requirements(subscription)

open SubscriptionTransition + expires_at <= now
  -> expire_subscription_transition(transition)
```

Les services de lifecycle conservent leurs locks et leur idempotence. S5 n'ajoute pas de moteur de scheduler parallèle.

Review reminders, Grant-expiration notifications et reevaluation temporelle proactive des account-age plans ne sont pas ajoutés sans besoin produit/runtime démontré.

## Migrations S5

```text
authorization/0013_subscription_permissions.py
subscriptions/0007_subscription_ongoing_requirement_state.py
```

Les migrations S1–S4 ne sont pas réécrites.

## Tests S5

Les tests additifs couvrent notamment :

- self-authority Profile et refus cross-Profile;
- owner Space view/manage;
- admin Space view sans manage par défaut;
- TeamMembership sans Mandate refusé;
- custom Space role;
- `is_staff` sans Mandate refusé;
- Grant réservé à la permission plateforme;
- stabilité de `grace_until` et recovery;
- suspension conservant `effective_value` mais bloquant `allowed`;
- présence des contrats Domain Events.

Les workflows canoniques Subscriptions, CI/PostgreSQL et Beta seed restent les gates d'intégration S1–S5.

## Différé S6

S6 conserve : UX finale Profile/Space/Staff, wizard final, progression Requirements, usage visualization, analytics produit final, hardening performance/accessibilité final, matrice E2E produit complète et release gate Subscription.
