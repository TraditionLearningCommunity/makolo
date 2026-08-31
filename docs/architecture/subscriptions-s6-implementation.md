# Makolo — Subscription S6 implementation

## Statut

Ce document décrit l'implémentation de **S6 — Subscription Product UX, Analytics, Hardening & Release Gate**.

S6 est actuellement une **release candidate** sur `task-s6-subscription-product-ux-hardening`. Elle ne doit être marquée `DONE` qu'après validation de la PR, des workflows canoniques et du `main` post-merge.

Base réellement auditée au démarrage :

```text
dff2ba49b9c16708d12e7bb3ed4e7c49c9cb5725
```

Pendant S6, `main` a avancé vers :

```text
db4de6cacf6a12f604c16bc37383df99a23a8d02
```

Ce changement parallèle clôt uniquement la documentation Services V1/T36. La branche S6 a été resynchronisée par un merge Git explicite après inspection des deux fichiers concernés.

S6 compose S1-S5. Elle n'ajoute aucun modèle Subscription de présentation, aucun billing récurrent, aucun pricing commercial et aucune responsabilité parallèle à Authorization, Payments, Requirements, Domain Events, Notifications ou Automation.

## Profile UX

Surface réelle :

```text
/subscription/
```

La navigation « Pour moi » expose `Abonnement` pour le Profile connecté. L'écran utilise `SubscriptionProductView`, un read-model non persisté qui compose :

- BASE actif et ADDONS actifs ;
- Benefits de présentation ;
- Effective Entitlements du resolver S2 ;
- usage seulement lorsqu'un provider canonique existe ;
- catalogue publié/public/self-service ;
- Eligibility S3 ;
- Transition S4 et progression des Assessments ;
- état ongoing/grace/suspension S5.

Aucun accès n'est dérivé d'un Benefit marketing.

### Preview et mutation

Le preview appelle `build_subscription_change_preview(...)` et reste une lecture. Il ne crée ni Transition, ni Assessment, ni PaymentObligation ni SubscriptionItem.

La confirmation est un POST distinct. Elle passe par `request_subscription_transition_for_actor(...)` et exige une clé d'idempotence. La garantie principale reste la contrainte/service S4 côté serveur.

Les actions cancel/complete sont scoppées à la Subscription Profile avant l'appel à la façade S5, afin qu'une autorité possédée ailleurs par le même acteur ne puisse pas être réutilisée via une route Profile.

## Space UX

Surface réelle :

```text
/spaces/<slug>/subscription/
```

Le module `subscription` est intégré à `SpaceConsoleContext` dans le groupe Espace. Sa visibilité dépend de :

```text
space.subscription.view
space.subscription.manage
```

`view` permet la page et le preview. `manage` est requis côté serveur pour toute mutation. Un TeamMembership sans Mandate n'ouvre ni le module ni les mutations.

La page identifie explicitement :

```text
Abonnement de l'Espace
Espace · <nom>
```

Les actions Transition sont également scoppées à la Subscription de l'Espace courant pour éviter une confusion entre plusieurs Espaces administrés par le même acteur.

La Feature `team.members` utilise le resolver S2 et son usage provider Organizations ; la vue ne recompte pas les membres elle-même.

## Disclosure

Les surfaces self-service appliquent :

- `visible` : titre/description autorisés ;
- `generic` : message générique ;
- `internal` : aucun élément de condition n'est rendu.

Les evaluator keys, configs, actual values internes et notes Staff ne sont pas exposés.

## Staff / Operations UX

Surface réelle :

```text
/operations/subscriptions/
```

L'accès n'est pas dérivé de `is_staff`. Les écrans utilisent les PermissionCodes S5 :

```text
platform.subscriptions.catalog.view
platform.subscriptions.catalog.manage
platform.subscriptions.view
platform.subscriptions.manage
platform.subscriptions.grants.manage
platform.subscriptions.reviews.manage
```

Les surfaces livrées couvrent :

- Plans et versions ;
- création d'un Plan ;
- création/édition d'une PlanVersion draft ;
- Benefits ;
- Entitlements sélectionnés uniquement parmi les FeatureDefinition connues ;
- PlanRequirements ;
- EntitlementRequirements ;
- publication/retrait via `publish_plan_version` / `retire_plan_version` ;
- support d'une Subscription individuelle ;
- Transitions ;
- Grants et révocation auditée ;
- reviews humaines via `review_subscription_requirement`.

Une version publiée ou retirée reste consultable mais n'est pas éditée en place.

### Configuration des Requirements

Les forms Staff sont construites à partir des evaluators Subscription enregistrés et de leurs opérateurs/paramètres connus. Elles n'acceptent pas de Python, SQL, JavaScript, import path ni expression arbitraire.

Les codes techniques utilisent le validateur canonique `technical_code_validator`.

## Analytics

S6 réutilise `analytics_app` et `AnalyticsFact`. Aucun second pipeline Analytics n'est créé.

Le consumer existant projette les Domain Events Subscription utiles, notamment :

```text
subscription.transition.requested
subscription.transition.completed
subscription.transition.rejected
subscription.transition.cancelled
subscription.transition.expired
subscription.plan.changed
subscription.addon.activated
subscription.addon.removed
subscription.grace.started
subscription.suspended
subscription.reactivated
subscription.eligibility.available
```

La projection est idempotente via la contrainte existante :

```text
(domain_event, fact_type)
```

Les dimensions conservées sont minimales : Profile ou Space lorsqu'ils sont explicitement le sujet, type de fact et date. Aucun payload Requirement interne, note Staff ou faux revenu n'est copié.

La surface Operations agrège également l'état courant des Subscriptions, BASE, ADDONS, Grants et blockers à partir des modèles canoniques sans matérialisation subject × plan.

## Performance

S3 précharge déjà les Requirements du catalogue avant l'évaluation de plusieurs PlanVersions.

S6 supprime le N+1 principal identifié sur Effective Entitlements : les `EntitlementRequirement` obligatoires sont maintenant chargés en lot pour toutes les Features résolues dans une requête, au lieu d'une requête par Feature.

Un test de query count couvre ce contrat avec plusieurs Features/Requirements.

Les listes Staff Subscription sont paginées et utilisent `select_related`/`prefetch_related` sur les relations nécessaires.

## Sécurité

Les surfaces S6 revalident côté serveur :

- Profile self-scope ;
- Space scope ;
- view vs manage ;
- TeamMembership sans Mandate ;
- Platform Mandate ;
- PlanVersion publiée/public/self-service pour le self-service ;
- Transition attachée au bon sujet ;
- Grant attaché au sujet supporté ;
- review via la façade S5.

Le frontend n'est jamais la source d'autorité.

## Accessibilité et responsive

Les surfaces réutilisent le design system Makolo existant et restent en cards/stacked layouts plutôt qu'en grands tableaux sur mobile.

Les éléments critiques comprennent :

- headings structurés ;
- labels de forms ;
- boutons pour les mutations et liens pour les navigations ;
- états textuels en plus des badges ;
- `<progress>` avec `aria-label` et équivalent textuel ;
- messages `role="status"`/`role="alert"` lorsque nécessaire ;
- absence de scripts inline ajoutés par S6.

Le parcours Playwright mobile vérifie l'absence de débordement horizontal critique sur Profile et Space.

## E2E et fixtures

Le reset E2E historique effectue un `flush`, ce qui supprime les données des migrations de seed. S6 ne dépend donc pas de l'ordre des specs :

```text
prepare_e2e
prepare_transport_e2e
prepare_discovery_e2e
prepare_services_e2e
prepare_subscriptions_e2e
```

`prepare_subscriptions_e2e` rejoue explicitement les permissions Subscription S5 puis le seed BASE S2 après la création de tous les users/Spaces E2E, et ajoute uniquement des données factices dédiées au navigateur.

Les parcours S6 couvrent :

- Profile desktop : formule, catalogue, preview, Transition, progression ;
- Space owner : identité Space, preview et demande ;
- Space viewer : consultation sans mutation ;
- TeamMember sans Mandate : refus ;
- Staff avec Platform Mandate : création Plan interne, draft, publication ;
- Profile + Space mobile : absence d'overflow critique.

## Migrations S6

```text
Aucune.
```

S6 n'introduit aucun modèle uniquement pour présenter des données.

## Release gates

Le workflow canonique `.github/workflows/subscriptions.yml` couvre désormais S1-S6 et exécute les tests S6 UX/performance/analytics sur SQLite rapide et PostgreSQL.

La clôture de ce document sera mise à jour uniquement après résultats réels de :

```text
python manage.py check
makemigrations --check --dry-run
Subscriptions S1-S6
T34A Requirements
Authorization
Domain Events
Notifications
Automation
Payments pertinent
postgresql-core
postgresql-ops
frontend build / artifacts
CSP/runtime
WhiteNoise/static
Playwright/E2E
Beta seed
aggregate-main-status post-merge
```

## Hors scope V1

S6 n'invente pas :

- pricing commercial complet ;
- billing récurrent ;
- taxes ;
- invoices ;
- production payment provider ;
- coupons/discount engine ;
- revenue recognition ;
- contracting enterprise.

Ces sujets restent hors Subscription V1 tant qu'une décision canonique ultérieure ne les introduit pas.
