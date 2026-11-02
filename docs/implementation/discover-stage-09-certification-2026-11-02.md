# Makolo / Découvrir — Chantier 09 : certification et décision d'intégration

**Ouvert** : 2026-11-02. **Statut : CERTIFICATION EN COURS — NON FERMÉE, AUCUN MERGE**.

## Sources et méthode

Dépôt unique : `TraditionLearningCommunity/makolo`, `main`, PR métier [#522](https://github.com/TraditionLearningCommunity/makolo/pull/522). Les livraisons 00–08 constituent le périmètre. Les tests d'exécution, suspendus explicitement jusqu'à 09, sont maintenant autorisés. Les normes de qualité, tests et interdictions du dépôt restent intacts.

Le HEAD de #522 se déplace avec des chantiers concurrents, provoquant l'annulation automatique de nombreuses exécutions Actions (`cancel-in-progress`). Pour obtenir une **preuve attachée à un SHA immuable**, la PR de certification **[#532](https://github.com/TraditionLearningCommunity/makolo/pull/532)** a été créée depuis `d337ebc0f4194dbebc4a4ef1ef526d51ba192a61`, vers `main`, **strictement pour contrôler un snapshot de #522**. Elle est **NON INTÉGRABLE** séparément : aucune fusion dans `main`, et une réussite sur son SHA ne certifierait pas les commits ultérieurs de #522.

L'environnement de travail de l'agent ne peut pas cloner GitHub (DNS indisponible) et ne possède pas Flutter. Les exécutables de test réels utilisés sont **les runners GitHub Actions**, inspectés par leurs jobs, étapes et journaux. Tout statut `queued`, `pending`, `cancelled`, `skipped` ou `in_progress` est **non probant**.

## Écarts confirmés, causes et corrections

### P0 — Formatage Flutter

- SHA initial #532 : `d337ebc0...`, run Mobile CI `41471680307`, job `125367091822`.
- Gate **Format check** : **FAIL**, 36 fichiers non canoniques, arrêt avant `flutter analyze` et les tests. Ce n'est pas un échec métier démontré.
- Correction **sans modification du contrôle** : résultat exact de `dart format` issu du log du runner réappliqué aux 36 fichiers du checkpoint, enregistré en **un commit** `bff10ab2178b19e86a855babb5a8b92331f19879`. Cette correction traverse des fichiers Découvrir et plusieurs trains simultanément modifiés : réconciliation de leur état courant nécessaire avant intégration #522.

### P0 — Bundles Web versionnés

- SHA initial #532 : run CI `41471680621`, job `125366576324`.
- Gate `git diff --exit-code -- package-lock.json static/dist` après `npm ci && npm run build` : **FAIL**, `static/dist/makolo.css` et `static/dist/makolo.js` non synchronisés.
- Correction **sans assouplissement des tests** : sorties exactes de build recopiées depuis les diffs du runner, commit `8d6c3f6872a529e940ac3bc1ad7d6f774cc63121` sur #532.

### P0 — Goldens Now non approuvés

- SHA `bff10ab...`, run [Now Presentation Goldens `41473983066`](https://github.com/TraditionLearningCommunity/makolo/actions/runs/41473983066), job `125374592690` : formatage désormais franchi mais **20 golden comparisons FAILED**, dont `G01 s1 min` (19,91 % pixels de différence). Cette différence appartient à la surface Now partagée : le chantier 09 de Découvrir **ne doit ni supprimer ni régénérer aveuglément les références**. Comparer les artefacts approuvés et les nouvelles captures, identifier si la variation est voulue ou une régression, obtenir le propriétaire UX du train et corriger le produit ou approuver explicitement de nouveaux goldens avant merge.
- Artefact de diagnostic généré par la CI : `makolo-now-golden-review` du run 41473983066. L'existence de l'artefact ne vaut pas approbation visuelle.

### P1 — Anciennes copies Reader non cloisonnées

- L'étape 08 empêchait la **lecture** des anciens fichiers `discovery/public-offline` sans pouvoir attribuer leur Profil ; les octets demeuraient sur disque.
- Correctif sur #522 : `DiscoveryOfflineStore.purgeLegacyUnscopedReader()` retire seulement le répertoire ancien lors du premier accès sûr à Reader, sans toucher aux fichiers Reader isolés par Profil ni aux Téléchargements du système. Régression ajoutée dans `mobile/test/discovery_stage08_media_privacy_test.dart`.
- Aucune migration des anciens fichiers privés vers un autre Profil n'est possible sans preuve d'owner ; aucune migration de schéma SQLite.

## Vérifications effectivement attestées sur le SHA initial `d337ebc0...`

| Gate | Preuve | Verdict |
| --- | --- | --- |
| API Contract | run `41471680458` | **SUCCESS** |
| Security supply chain | run `41471680772` | **SUCCESS** |
| Mobile Visual Golden Regression | run `41471680795` | **SUCCESS** |
| Demo generation validation | run `41471680544` | **SUCCESS** |
| Beta seed validation | run `41471680611` | **SUCCESS** |
| Orchestrator Actor 5 | run `41471680530` | **SUCCESS** |
| Interpreter Actor 3 | run `41471680949` | **SUCCESS** |
| Observer PostgreSQL | run `41471680634` | **SUCCESS** |
| Recognition | run `41471680860` | **SUCCESS** |
| Projector Actor 7 | run `41471680470` | **SUCCESS** |
| Android DEV APK build | run `41471680334` | **SUCCESS — compilation seulement, PAS un test sur appareil** |
| Funding PostgreSQL | run `41471680845` | **SUCCESS** |
| Conversation PostgreSQL | run `41471680629` | **SUCCESS** |
| Prospector PostgreSQL | run `41471680759` | **SUCCESS** |
| Mobile CI | run `41471680307` | **FAIL — formatage, correctif soumis** |
| Django CI | run `41471680621` | **FAIL — bundles, correctif soumis** |

**Attention** : le CI est lié au SHA et les runs annulés ne sont pas comptés. La réussite des jobs satellites ne certifie pas automatiquement les suites Django complètes, Flutter analyze, E2E ni le comportement Android natif. Les runs suivants après corrections doivent passer **entièrement**.

## Inventaire migrations

Le delta de #532 vers `main` contient six migrations Django :

- `accounts.0009_profile_visibility_policies`
- `presentations.0005_presentationmediause`
- `presentations.0006_private_presentation_assets`
- `services.0005_service_start_operation_fingerprint`
- `sharing.0006_passport_issued_public_and_sharing`
- `topics.0005_profile_publishable_defaults`

Lecture statique : CreateModel, AddField, AlterField et contraintes ; aucune suppression de table ou colonne dans ces six fichiers. Le job `pr-fast` inclut `manage.py check` et `makemigrations --check --dry-run`. L'application réelle PostgreSQL est sous la responsabilité des jobs CI, **à prouver par leur résultat**. La migration physique des médias historiques et leur configuration CDN restent séparées ; les modèles ne fournissent pas une preuve de migration des octets.

## Matrice des gates de fermeture

| Obligation | Preuve attendue avant FERME |
| --- | --- |
| Django | CI, système, migrations, suite pertinente, checks PostgreSQL (incl. permissions, refus, concurrence/idempotence, cartes et N1/N2) |
| Flutter | `dart format` canonique, sources générées sans diff, `flutter analyze`, tests de toutes les surfaces concernées, 01–08 |
| Web/E2E | `npm ci && npm run build`, bundles propres, tests Playwright sur Web, navigation, invité/authentifié, carte, N2/N3 |
| Media/storage | media-use owner, fichiers privés, absence d'URL divulguée, audit des octets historiques, origine et politique de cache/CDN |
| Android | Essai **sur vrai appareil** : cold start, sessions, changement Profil, connectivité coupée/rétablie, reprise d'une continuation, scanner/liens, permissions, media cache/retrait, Navigation N1/N2/N3 |
| Rollback et déploiement | Migrations non destructives confirmées, sauvegarde/restauration historique, compatibilité SQLite et données serveur, environnement de bêta, aucun 500 |
| Intégration | SHA final #522 comparé au dernier SHA CI complet, collisions réconciliées ; aucune CI rouge, aucun checkpoint parallèle mergé |

## Décision actuelle

**NO MERGE / NON CERTIFIÉ.** Corriger toutes les gates rouges, vérifier celles qui restent incomplètes, ne pas attribuer au code Découvrir des succès qui appartiennent à d'autres domaines. Aucune suppression/affaiblissement de tests ou de golden pour fabriquer du vert. La PR de checkpoint #532 ne doit pas devenir la branche canonique de livraison.

Ce dossier est **vivant** : à actualiser avec les derniers runs du SHA `8d6c3f6...`, la décision du propriétaire Now pour les goldens, le test vrai Android, le diff final #522 ↔ checkpoint et la décision d'intégration.
