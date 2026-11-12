# Conversations — modifications locales du 12 novembre 2026

## Contrat de changement

- Objectif : moderniser les Discussions Exchange sans remplacer les Points ni leur attention métier.
- Propriétaire de la branche et des écritures de cette intervention : Codex, exécution locale unique.
- Base locale : `79fea9f95b38c05d187ce9a1f8e620f0e37b908a`.
- Branche imposée : `fix/discover-a-continuation-context-20261014`, PR existante #522.
- `origin/main` rafraîchi ; aucun rapprochement, merge, push ou lancement/consultation de CI effectué.
- Surfaces : Conversations, configuration ASGI, notifications propriétaires, shell Web et client Flutter Conversations ; tests et documentation correspondants.
- Zones exclues : `main`, données privées locales non suivies, autres domaines métier et infrastructure de production.
- Acceptation : mêmes propriétaires/ACL pour REST, Web et Flutter ; confirmation durable, idempotence et reprise ; aucun transfert de Permission/Access/Requirement ; aucune réussite non confirmée affichée.
- Gate d’intégration : exécution des suites et migrations ci-dessous, recette Redis/PostgreSQL/Web/appareil, puis rapprochement avec `main` et gates de la PR existante par son propriétaire. Ce document ne vaut pas validation de ces gates.

## Code ajouté

- Transport Channels/Redis opt-in, ASGI HTTP conservé, ticket Redis hashé à usage unique et expiration de 60 secondes, authentification initiale bornée, origine et trames bornées, budgets atomiques, abonnements de Points revalidés, signaux sans corps de message.
- Ordre par Point sous verrou, version de projection, empreinte de l’intention originale, ACK REST, pagination historique et delta incluant modifications, tombstones et réactions. Compatibilité du curseur historique conservée.
- Citations, édition optimiste/versionnée et audit par empreintes ; suppression logique et révocation du téléchargement ; invalidation des citations dépendantes.
- Réactions bornées, mentions de Profiles actuellement éligibles, recherche serveur filtrée, reçus monotones par Profile et Point. Les résumés de reçus n’exposent pas d’identités de destinataires.
- Références à FK typées, contrôlées à la publication et à la consultation par les propriétaires Journey/Requirement. Aucune copie documentaire ni satisfaction de Requirement.
- Médias Exchange sans faux corps texte, contrôle signature/MIME/extension, normalisation des images et suppression des métadonnées ; réutilisation des pièces jointes privées.
- Web : composant commun à la page, au panneau global et aux fenêtres flottantes, trois fenêtres, maintien hors du swap HTMX, brouillons par Profile, REST et rattrapage périodique, médias avec progression XHR, capture vocale explicite.
- Flutter : projections d’Entries dans le store Drift existant, index Profile/Point/séquence et curseur `SyncSources` transactionnel ; lecture locale avant acquisition ; outbox et brouillons existants ; coordinateur de transferts existant ; progression réelle ; adaptateur WebSocket par repository ; conservation des intentions et fichiers non confirmés.
- Header optionnel `X-Makolo-Profile` pour empêcher un ancien onglet/repository d’agir sous le nouveau compte après un changement de session. Les clients historiques sans header conservent leur contrat.
- Domain Events et consumer Notifications pour messages, mentions et réponses ; pas de corps privé dans les événements/push, préférences et mute externes respectés, aucun événement de réaction ordinaire.

## Migrations et exploitation

1. `0009_exchange_stream` : colonnes et métadonnées, backfill déterministe `(created_at, id)` conservant UUID/dates/citations/pièces jointes, puis séquence non nulle et unicité. Lots de mise à jour bornés à 500 lignes. Les anciens uploads gardent une reconnaissance compatible avec leur normalisation historique ; aucune charge originale ambiguë n’est inventée.
2. `0010_entry_references` : enfants à FK typées et contrainte exactement une cible.
3. `0011_exchange_search_index` : `pg_trgm` et index GIN partiel PostgreSQL ; aucun SQL spécifique sur SQLite. Le rollback conserve l’extension partagée.

Prévoir une fenêtre de maintenance sans écritures Exchange pour la bascule. Sur PostgreSQL, la migration tient les verrous jusqu’au commit ; ce n’est pas une migration en ligne sans interruption. Sauvegarder et contrôler les données existantes. Le rôle de migration doit pouvoir installer `pg_trgm`, ou l’extension doit être installée préalablement par l’administrateur.

Le temps réel est désactivé par défaut. Pour l’activer, fournir une vraie `CONVERSATIONS_REDIS_URL`, un `CONVERSATIONS_REDIS_PREFIX` propre au déploiement et `CONVERSATIONS_REALTIME_ENABLED=true`. Aucun fournisseur ni hôte de production n’est présumé. Servir l’application ASGI derrière la terminaison HTTPS/WSS et les origines/hôtes autorisés existants. Une panne du transport ne doit pas bloquer les mutations REST ; les clients ouverts tentent aussi le rattrapage REST toutes les 20 secondes au premier plan.

Le cache Flutter existant reste une base SQLite applicative ; aucun chiffrement SQLCipher, chiffrement intégral des drafts/outbox ou chiffrement de bout en bout n’est revendiqué par cette intervention.

## Éléments encore incomplets

Les lots R0–R7 ont des modifications concrètes, mais le périmètre industriel complet du prompt **n’est pas fermé** :

- R0/R6 : abonnement temps réel par Conversation et rafraîchissement global des Discussions non ouvertes ; les abonnements actuels ciblent les Points ouverts.
- R2/R6 : rejoindre une citation située hors de l’historique actuellement chargé.
- R3/R6 : pagination des résultats de recherche dans les interfaces et recherche serveur Flutter ; Flutter propose actuellement la recherche dans les messages déjà reçus.
- R4 : le Web affiche les reçus réellement acquis par les appareils, mais n’émet pas d’ACK « livré » depuis un cache Web durable. Il ne prétend donc pas avoir persisté/reçu durablement un message sur cet appareil.
- R5 : parcours natif complet de consultation/export d’un JourneyArtifact référencé ; le client affiche les métadonnées autorisées. Aucun export propriétaire n’est contourné.
- R6 : virtualisation Web des très grands historiques, approfondissement du regroupement/date et de la navigation tactile/clavier, Hover Cards et recette visuelle/accessibilité complète.
- R7 : stratégie de chiffrement des caches sensibles au repos et son déploiement ; validation opérationnelle complète des nouveaux chemins.

Ces manques ne sont pas masqués par des capacités simulées et ne doivent pas être déclarés livrés.

## Vérifications effectuées et limites

Lecture des signatures/propriétaires pertinents, parsing syntaxique Python, vérification syntaxique Node, `git diff --check` et formatter canonique Flutter/Dart. SDK local : Dart 3.13.3. Les dépendances déclarées Channels 4.3.1 / channels-redis 4.3.0 / Daphne 4.2.2 ont été vérifiées dans les métadonnées de leurs publications PyPI, sans avis de vulnérabilité signalé pour ces versions lors de la consultation.

**Aucun test Django, Flutter, E2E, migration réelle, analyse Flutter, build, benchmark, workflow ou CI n’a été exécuté.** Aucun succès PostgreSQL, Redis, navigateur ou Samsung n’est revendiqué.

Tests ajoutés : contrats de flux/ACL/idempotence/concurrence PostgreSQL, migration historique, transport/tickets/révocation, Drift et reprise/isolation, états locaux et contrats UI Web/HTMX. Les réponses simulées sont limitées aux tests UI ; le runtime n’utilise pas de mocks.

## Commandes manuelles

Depuis la racine, dans l’environnement Django configuré pour les données de test :

```bash
python -m pip install -r requirements.txt
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py migrate
python manage.py test conversations.test_exchange_stream conversations.test_realtime_transport conversations.test_exchange_migration
python manage.py test conversations notifications
```

Les tests de concurrence nécessitent PostgreSQL. Prévoir aussi une recette avec Redis réel pour les TTL/GETDEL, les coupures et plusieurs workers ASGI ; les doubles de test du transport ne prouvent pas ces comportements en infrastructure.

```bash
cd mobile
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter test test/conversation_exchange_stream_test.dart test/conversation_local_delivery_test.dart
```

Depuis la racine avec les dépendances E2E habituelles :

```bash
npm run test:e2e -- e2e/specs/conversations-messaging.spec.mjs
```

Ne pas intégrer avant traitement des manques et des résultats de ces gates.
