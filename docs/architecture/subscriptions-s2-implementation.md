# Makolo — S2 Subscription Core & Effective Entitlements

## Statut

Ce document décrit uniquement le runtime livré par S2 au-dessus du catalogue S1. S3 (Requirements/Eligibility), S4 (Transitions/Payment bridge), S5 (authorization/events/automation Subscription) et S6 (UX) restent différés.

## Modèles S2

### `Subscription`

Agrégat durable d'un sujet `Profile XOR Space`, avec FK explicites et contraintes DB d'unicité par sujet. États structurants : `active`, `grace`, `suspended`, `closed`.

### `SubscriptionItem`

Pinne une `PlanVersion` exacte et conserve aussi l'identité du `SubscriptionPlan` et son type BASE/ADDON afin de rendre les invariants actifs enforceables en base sous concurrence.

Contraintes :

- un seul BASE actif par Subscription ;
- un seul Item actif par add-on logique (`subscription + plan`) ;
- cohérence `plan`, `plan_version`, type du Plan et type de sujet validée côté serveur ;
- une PlanVersion draft ne peut être acquise ;
- l'historique terminé est conservé et n'est pas supprimable via l'API modèle.

La publication d'une nouvelle PlanVersion ne modifie jamais le pinning d'un Item existant.

### `EntitlementGrant`

Exception produit explicitement ciblée vers `Profile XOR Space`. La valeur est validée par `FeatureDefinition`, la fenêtre temporelle est contrôlée, le Grant est révocable et ses données contractuelles restent auditables.

## BASE universels et bootstrap

S2 installe deux BASE techniques minimaux :

- `profile.base` ;
- `space.base`.

Ils ne constituent pas des offres premium et ne définissent aucun prix. Le socle donne `activities.create=true` aux deux types de sujet et `custom_roles=false` au BASE Space. S2 n'invente volontairement aucune limite commerciale `team.members`.

Une data migration backfill les Profiles et Spaces existants avec une Subscription et la PlanVersion BASE publiée courante. Les nouveaux sujets passent par les primitives idempotentes `ensure_subscription_for_profile(...)` et `ensure_subscription_for_space(...)`, appelées par l'adapter de création Subscription. Le bootstrap verrouille le sujet et les agrégats nécessaires, tandis que les contraintes uniques restent l'ultime garde DB.

L'absence d'un BASE publié par défaut lors d'un nouveau bootstrap produit une erreur métier explicite ; elle ne laisse pas silencieusement un nouveau sujet sans socle. Une Subscription déjà correctement pinnée reste utilisable si le catalogue par défaut est momentanément indisponible.

## Effective Entitlements

Aucune table `EffectiveEntitlement` n'est créée. Le resolver calcule à la demande :

```text
BASE actif + ADDONS actifs + GRANTS actifs = EffectiveEntitlements
```

Les sources sont conservées dans le résultat pour expliquer le calcul. Les stratégies S1 sont réutilisées :

- `BOOLEAN_OR` ;
- `SUM` ;
- `MAX` ;
- `REPLACE`, avec priorité `GRANT > ADDON > BASE`.

Le resolver ne dépend jamais du nom commercial d'un Plan.

## Usage / quota

Le provider réel `organizations.active_team_members` mesure les Profiles distincts ayant un `TeamMembership` actif dans un Team actif du Space. Aucun compteur Subscription parallèle n'est stocké.

Pour `preserve_existing_block_new`, le résultat expose notamment `usage`, `remaining`, `allowed` et `over_limit`. Un dépassement ne supprime aucune donnée existante ; il indique seulement que les nouveaux usages doivent être bloqués par le futur point d'enforcement.

## Activity

`resolve_activity_entitlement_subject(activity)` et `resolve_activity_subscription(activity)` appliquent l'invariant canonique :

- Activity personnelle → Subscription du Profile propriétaire ;
- Activity de Space → Subscription du Space ;
- le Profile collaborateur reste l'axe Permission/Mandate et ne remplace jamais la Subscription du Space.

## Migrations

- `0003_subscription_runtime` : schéma, FK explicites, XOR, unicités, indexes et contraintes des trois modèles S2 ;
- `0004_default_bases_and_backfill` : BASE techniques minimaux et backfill des sujets existants, sans migration destructive.

## Différé

S2 ne livre ni `PlanRequirement`, ni `EntitlementRequirement`, ni Eligibility, ni `SubscriptionTransition`, ni Payment bridge, ni permissions Subscription finales, ni orchestration Notifications/Automation, ni UI Subscription. Ces responsabilités restent respectivement S3 à S6.
