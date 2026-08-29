# S1 — Subscription Catalogue & Entitlements Foundation

## Runtime livré

S1 introduit le bounded context `subscriptions` sans créer de Subscription individuelle. Le runtime livré contient :

- `FeatureDefinition` : contrat technique code-owned d'une capacité produit, avec type de valeur (`boolean`, `integer`, `decimal`, `enum`), sujets Profile/Space supportés, stratégie d'agrégation, provider d'usage éventuel, policy d'enforcement, bornes numériques et activation ;
- `SubscriptionPlan` : identité stable BASE/ADDON pour exactement un type de sujet ;
- `PlanVersion` : versions `draft`, `published`, `retired`, publication N+1 et pointeur `current_version` ;
- `PlanBenefit` : présentation marketing uniquement ;
- `PlanEntitlement` : valeur strictement typée reliant une version à une Feature.

## Publication et immutabilité

`publish_plan_version(...)` est transactionnel et verrouille le Plan et les versions concernées. Il vérifie que la version est en draft, que le Plan est actif, que la séquence de version est cohérente, puis revalide Benefits, Entitlements et Features avant de publier. Une publication N+1 peut retirer l'ancienne version courante sans la supprimer, puis déplace `SubscriptionPlan.current_version`.

`retire_plan_version(...)` contrôle le retrait. La version courante ne peut pas être retirée sans qu'une version de remplacement ait d'abord été publiée.

Les mutations directes de statut, les changements structurels d'une version publiée/retirée, les ajouts/modifications/suppressions de Benefits ou Entitlements d'une telle version et les mises à jour/suppressions en masse correspondantes sont bloqués côté serveur.

## Contraintes catalogue

- `SubscriptionPlan.code` est unique et stable ;
- `plan_type`, `subject_type` et `current_version` sont protégés contre les mutations non contrôlées ;
- seul un BASE peut être `is_default` ;
- un seul BASE actif par défaut peut exister pour `profile`, et un seul pour `space` ;
- `(plan, version)`, `(plan_version, feature)` et `(plan_version, benefit.position)` sont uniques ;
- une Feature doit supporter Profile et/ou Space ;
- les contrats techniques Feature sont immuables après création ;
- les valeurs Entitlement sont validées sans coercition lâche et les enum restent fermées.

## Features initiales auditées

S1 n'enregistre que trois capacités directement justifiées par le runtime actuel :

1. `activities.create` — `activities.Activity` existe comme noyau canonique et supporte un propriétaire Profile ou Space ; Feature booléenne disponible pour les deux sujets.
2. `team.members` — `organizations.TeamMembership` porte un état `active`; la Feature est une limite entière Space dont la mesure canonique reste dans `organizations`, avec policy `preserve_existing_block_new`.
3. `custom_roles` — `authorization.Role` supporte explicitement les rôles non système rattachés à un Espace ; la Feature est un gate booléen Space.

Les exemples documentaires non démontrés par un contrat runtime (`analytics.advanced`, CRM, automation, etc.) ne sont pas seedés.

## Dépendances et frontières

`subscriptions` n'importe ni `services` ni `opportunities`. S1 ne modifie pas le kernel `requirements` et ne crée aucun `PlanRequirement`, `Subscription`, `SubscriptionItem`, `EntitlementGrant`, `EffectiveEntitlement`, Eligibility, Transition, prix, Payment, permission Subscription finale, UI, Domain Event, Notification ou Automation.

## Différé S2+

S2 pourra construire l'identité Subscription d'un Profile/Espace, le bootstrap vers le BASE par défaut publié et le pinning explicite d'une PlanVersion. Les Requirements Subscription restent différés à S3 ; le runtime d'Entitlements effectifs, Eligibility/Transitions, pricing/Payments, Authorization finale et UI restent dans les étapes ultérieures prévues par le document canonique.
