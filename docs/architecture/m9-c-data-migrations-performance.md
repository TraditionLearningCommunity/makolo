# M9-C — Data, Migrations & Performance

Ce document complète `m9-hardening-quality-gate.md` avec les preuves détaillées du checkpoint M9-C. Il ne crée aucun domaine ni état métier.

## Base auditée

- `main@787dd3ee6496d9ec94744e4ea3e36be57c354d66`, merge de la PR #229 M9-B.
- Le HEAD de départ a été vérifié vert sur les gates applicables, dont `aggregate-main-status`, Django, E2E, Security supply chain, fresh SQLite/PostgreSQL et les shards PostgreSQL.
- PR parallèle #223 : uniquement `frontiere_opportunite_lab/*`, sans collision runtime, migration ou surface M8 centrale.
- Aucun chantier M9-C antérieur n'existait ; branche créée : `m9/data-migrations-performance`, PR #230.

## Inventaire migrations

L'audit du runtime courant a retrouvé 45 fichiers contenant `RunPython`, aucun `RunSQL`, un usage de `SeparateDatabaseAndState`, ainsi que les tests `MigrationExecutor` existants dans Tickets, Discovery, Operations et Groups. `scripts/check_legacy_upgrade.py` reste un préflight du plan de migration ; la preuve d'upgrade peuplé vers les leaf nodes existe déjà dans `tickets/test_migrations.py`.

Les grands cutovers Tickets/Payments/Events et les seeds simples déjà couverts n'ont pas été dupliqués. Aucun framework parallèle de migration testing n'est ajouté.

### Risque retenu : Commerce financial snapshot

`commerce/0003_financial_quote_snapshot` est une transformation sémantique irréversible : les anciens totaux Order/Item deviennent `expected_payee_amount` et un `financial_snapshot` explicitement marqué `commerce_v1_backfill`. Le forward utilise correctement les historical models et n'invente ni provider ni destination financière.

M9-C ajoute `commerce/test_m9c_migrations.py` : état historique `commerce/0002` → données legacy valides → migration `0003` → assertions sur les montants et snapshots → restauration vers les leaf nodes. Aucune migration historique n'est éditée et aucun nouveau backfill n'est introduit.

## Performance

L'inventaire des budgets existants a confirmé des garanties ciblées dans Goals, Trust, Readiness, Subscriptions et Preparation. Discover et Journey possèdent déjà des prefetch/batch resolvers structurés ; aucun changement spéculatif n'y est ajouté.

### Recognition reward catalog

Avant M9-C, `active_rewards()` pouvait exécuter jusqu'à trois `COUNT` supplémentaires par Reward pour `max_per_owner`, stock et `max_per_beneficiary`. La croissance était donc linéaire avec le nombre de Rewards.

La correction reste dans `recognition/selectors.py` : les trois compteurs sont des agrégations filtrées du queryset catalogue. Les flags d'éligibilité restent transitoires et la redemption transactionnelle continue de revalider les contraintes. Aucun compteur métier n'est persisté.

Budget : 12 Rewards avec les trois limites actives doivent être résolus par une seule requête catalogue, indépendamment du nombre de Rewards.

### Conversations list

Avant M9-C, la projection liste relisait `ConversationUserState`, participation/visibilité et fenêtres de Points conversation par conversation. Le chemin d'accès dérivé canonique reste complexe et ne doit pas être remplacé par Membership=Permission.

La correction reste dans `conversations/presentation.py` : la projection liste précharge, pour le Profile courant seulement, son état personnel, ses participations explicites actives, les Points actifs et les Points résolus. Une participation explicite active prouve directement la visibilité correspondante ; les Conversations sans cette preuve continuent d'utiliser `can_view_conversation()` et donc les règles d'autorité/audience existantes. Aucune donnée privée supplémentaire n'est exposée.

Budget ciblé : une liste de 12 Conversations accessibles par participation explicite reste dans un budget fixe de 8 requêtes maximum au lieu d'ajouter des lectures par Conversation.

## Indexes et modèle

Aucun index n'est ajouté : aucun besoin mesuré ne justifie un index après correction des N+1. Aucun champ, modèle, cache distribué, dénormalisation ou vérité Readiness persistée n'est ajouté.

## Validation

À fermer uniquement après : tests ciblés, `makemigrations --check --dry-run`, fresh migrate, tests MigrationExecutor, PostgreSQL pertinent, Security supply chain, Django/E2E applicables, puis vérification du `main` post-merge.

## Handoff M9-D

M9-D repartira du `main` vert post-M9-C et restera concentré sur le Cross-domain Quality Gate & Closure. Les sujets production (sizing, APM, backups, zero-downtime final, credentials) restent M10.
