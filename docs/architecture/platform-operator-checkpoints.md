# Makolo Platform — composition opérateur (branche feat/platform-mature)

**Contrat :** `docs/ux/Makolo_Platform_Architecture_Experience_Consolidee_2026-10-08.md`.

**Invariants :** le Profile humain est l'acteur ; un Mandate/Permission Makolo est l'autorité ; le domaine propriétaire exécute les transitions ; Platform n'est ni un Space, ni un second RBAC, ni Django Admin, ni une base métier parallèle.

## Parcours livrés pour validation

| Checkpoint | Surface Platform | Source canonique ou parcours owner |
|---|---|---|
| P1 | Shell sombre/violet, opérateur identifié, navigation et états | Templates Platform |
| P2 | Bootstrap capability-driven | `authorization.services.effective_permission_codes`, `core.platform_presentation` |
| P3 | Supervision Operations, décisions Space et Event explicites | `operations.product_overview`, `operations.services`, `events.services` |
| P4 | Files Trust et décisions vérification/report/dispute | `trust.models`, `trust.forms`, `trust.services`; Evidence ouverte seulement via endpoint owner protégé |
| P5 | Submissions, révisions, contrôle de sources, lifecycle, fusion | `opportunities.services` et `services.attention_selectors`; créations/édition détaillée via éditeur owner |
| P6 | Plans, Subscriptions et Requirement reviews projetés selon Permission | `subscriptions.*` ; mutations et Grants via `operations.subscription_views` qui réutilise services owner |
| P7 | Policies, simulation, schedule/publish, Rewards/Achievements availability, audit | `recognition.governance_services`, `recognition.simulation`, `recognition.models` |
| P8 | Connexions Platform et états bornés, sans secrets | Projection `intelligence.interoperability` |
| P9 | Recherche bornée + investigations Space/Event + handoff owners | Selectors Operations, Opportunity, Recognition, Trust/Subscriptions selon droit |
| P10 | Runtime Operations, workers, Domain Events et consommateurs sans payload | `operations.product_overview`, `core.platform_system_projection` |
| P11 | Thème, responsive, focus, clavier, tables, états, confirmation | CSS et templates Platform ; E2E dédiés sur quatre viewports |

## Opérations fortes

Les POST Platform demandent une cible, un motif et une confirmation. La Permission est réévaluée au serveur, et les mutations passent par les services de domaine ; les flux ajoutés vérifient également l'état/version d'origine pour refuser une action périmée. Les décisions significatives sont tracées avec l'acteur humain, la cible, la raison et le résultat. Leurs conséquences restent sous la responsabilité de l'owner.

## Frontières volontaires et non-fonctionnalités

- **Django Admin** conserve la maintenance technique et les workflows de secours. Ce chantier ne modifie pas les ModelAdmin.
- **Domain Event requeue** reste indisponible dans Platform : aucune relance sans contexte consumer, erreur, idempotence, conséquence, revalidation et audit owner complet.
- **Search Platform** n'invente pas de fédération Profile/Payment/Access/Evidence sans selectors owner-safe, Permission et besoin de PII explicites. La couverture est présentée comme partielle.
- **Subscriptions** conservent leur moteur, leurs Requirement/Grant decisions et leurs pages métier owners. Platform expose les files et handoffs permissionnés, pas une deuxième logique contractuelle.
- **Recognition** : la simulation n'est jamais une publication ; ni les Rewards ni les credits ne sont des Payments.
- **Système** : les états Domain Events n'affichent ni payload brut, ni credentials, ni logs sans limite ; une absence d'observation n'est pas déclarée saine.
- Aucun nouveau modèle persistant Platform ni migration.

## Gates avant merge

La présence des routes/fichiers ci-dessus **ne vaut pas PASS**. Vérifier le dernier HEAD avec les tests ciblés, `manage.py check`, `makemigrations --check`, Security/API Contract, PostgreSQL owners concernés, E2E navigateur, responsive Medium/Wide/Very Wide, clavier, axe, concurrence, IDOR et no-secret leakage. Réconcilier à nouveau `main` si celui-ci avance, puis squash merge seulement lorsque toutes les gates sont vertes. Après merge, vérifier le HEAD et les workflows `main`.

Ce document consigne les surfaces et limites ; il ne remplace pas un rapport de validation.
