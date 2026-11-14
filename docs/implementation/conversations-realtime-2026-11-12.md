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

La continuation configure SQLite3MultipleCiphers pour la base Flutter, incluant les drafts/outbox qu’elle contient. Le binaire natif doit être reconstruit avec les hooks déclarés ; une bibliothèque SQLite sans chiffrement est refusée en release. Les clés ne sont ni exportées ni recréées lorsque la base chiffrée existe sans clé accessible. Configuration fondée sur les [instructions Drift](https://drift.simonbinder.eu/platforms/encryption/) et les [hooks sqlite3](https://pub.dev/documentation/sqlite3/latest/topics/hook-topic.html).

## Reliquats du commit f7ee18ba8 — raccordements de continuation

Les reliquats identifiés ont maintenant les raccordements suivants dans le code ; leur recette reste à exécuter par le propriétaire :

- Abonnements Conversation, invalidations d’inbox candidates par Profile puis revalidation avant émission, dernière entrée visible et non-lus dérivés des reçus ; listes Web/panneau/Flutter actualisées et rattrapage périodique REST. Un seul adaptateur/socket par repository ou shell, avec leases et protection des reconnexions.
- Recherche ciblée d’une Entry autorisée avant acquisition de son contexte historique borné ; navigation, ancrage et mise en évidence Web/Flutter ; tombstones et placeholder sans identifiant pour les citations désormais inaccessibles.
- Recherche immédiate Drift, recherche serveur et pagination dédupliquée Flutter ; pagination et navigation vers les résultats Web. Une erreur réseau conserve les résultats locaux ; une révocation connue les masque.
- Pages IndexedDB transactionnelles, contrôle du stockage persistant avant ACK de livraison Web et lecture uniquement après interaction réelle sur un préfixe effectivement visible. Aucun ACK depuis un preload, une fenêtre réduite ou une navigation programmatique. Préférence de partage des lectures dans `ConversationUserState`, consultable/modifiable depuis les deux clients.
- Références consultables depuis les deux clients ; fichier JourneyArtifact servi sous les ACL de l’Entry et du propriétaire. Export/partage vérifiés à nouveau via le service Sharing propriétaire et confirmation explicite quand requise. Les viewers natifs ne réutilisent jamais une ancienne autorisation d’export.
- Fenêtres agrandissables, réduction/restauration avec scroll conservé, brouillons/fichiers séparés par Point, historique Web à fenêtre DOM bornée et hauteurs mesurées, regroupements/date, filtres, menus et cartes d’information accessibles au focus/tactile.
- SQLite chiffré via le moteur natif SQLite3MultipleCiphers supporté par Drift/sqlite3, clé aléatoire par Profile dans Keystore/Keychain, contrôle du moteur en release, migration en arrière-plan. La source est conservée jusqu’à réouverture chiffrée et comparaison logique exacte ; clés indisponibles ou copies divergentes bloquent l’ouverture sans remplacer les données. Les journaux et copies dérivées sont nettoyés seulement après les contrôles appropriés. Les fichiers médias existants restent à leurs emplacements privés et ne sont pas supprimés par la migration SQLite. Aucun E2EE ni chiffrement applicatif des fichiers médias externes à SQLite n’est revendiqué.

Migration Django additive supplémentaire : `0012_read_receipt_privacy`. Pas de nouvelle migration du schéma Drift : chiffrement du fichier existant et conservation de ses données/schemaVersion.

Les essais de migration native réelle, clés verrouillées/restaurées, multi-workers Redis/PostgreSQL, écran/appareil, accessibilité et performances restent **non exécutés**. Aucune fermeture de ces gates n’est revendiquée sur la seule base du code ou du formatter.

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
python manage.py collectstatic --noinput
python manage.py test conversations.test_exchange_stream conversations.test_exchange_continuity conversations.test_realtime_transport conversations.test_exchange_migration
python manage.py test conversations notifications
```

Les tests de concurrence nécessitent PostgreSQL. Prévoir aussi une recette avec Redis réel pour les TTL/GETDEL, les coupures et plusieurs workers ASGI ; les doubles de test du transport ne prouvent pas ces comportements en infrastructure.

```bash
cd mobile
flutter pub get
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter test test/conversation_exchange_stream_test.dart test/conversation_local_delivery_test.dart test/encrypted_profile_database_test.dart
flutter build apk --debug
```

Depuis la racine avec les dépendances E2E habituelles :

```bash
npm run test:e2e -- e2e/specs/conversations-messaging.spec.mjs
```

Le build natif est obligatoire pour embarquer le moteur de chiffrement ; ne pas distribuer une mise à jour Dart seule. Valider une mise à niveau sur une copie représentative de bases existantes et les cas de clé indisponible avant intégration. Ces commandes ne sont pas exécutées par l’agent.
