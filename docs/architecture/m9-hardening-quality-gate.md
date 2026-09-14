# M9 — Mature Hardening & Quality Gate

Ce document suit les preuves de fermeture de M9. Il décrit uniquement les garanties vérifiées sur le runtime courant ; il ne crée aucun domaine ni état métier.

## Base auditée

- Dépôt : `TraditionLearningCommunity/makolo`.
- Base M9 initiale : `main@c487e138958410a9d8e45033e7dc9d63e3a8ff58` (merge M8-E).
- Au démarrage de M9 : `ci/aggregate = success`.
- PR parallèle : #223, laboratoire `frontiere_opportunite_lab/*` uniquement ; aucun chevauchement runtime M9 identifié.

## Découpage

1. M9-A — Security, Authority, Privacy & Supply Chain.
2. M9-B — Integrity, Concurrency & External Resilience.
3. M9-C — Data, Migrations & Performance.
4. M9-D — Cross-domain Quality Gate & Closure.

Chaque PR repart du `main` vert obtenu après la précédente.

## M9-A — audit et garanties

### Autorité

Les tests M9 complètent les tests propriétaires existants ; ils ne créent pas d'ACL parallèle.

Matrice de contrôle utilisée selon la surface :

| Acteur | Autorité présumée ? | Règle M9 |
| --- | --- | --- |
| anonymous | non | uniquement surfaces publiques explicites |
| authenticated outsider | non | pas de fuite d'existence ou de contenu privé |
| Profile owner / beneficiary | contextuelle | seulement ses propres faits et droits |
| other Profile | non | aucun droit par identité devinée |
| Space member sans Mandate | non | Membership n'accorde pas l'autorité métier |
| Assignment | non par lui-même | responsabilité distincte de Permission/Mandate |
| Activity/Space authorized actor | oui, dans le scope | permission serveur obligatoire |
| staff technique | non par lui-même | staff n'est pas une autorité métier universelle |
| platform-authorized actor | oui, pour les permissions plateforme explicites | scope serveur explicite |

Les combinaisons non pertinentes à une surface ne sont pas artificiellement testées.

### Fichiers privés

L'inventaire a confirmé un stockage privé partagé déjà réutilisé. M9-A ne crée pas de second storage.

Trois gaps de réponse HTTP ont été reproduits sur des downloads déjà protégés côté serveur :

- Preparation `ActivityResource` : `nosniff` existait, `Cache-Control: private, no-store` manquait.
- Trust `TrustEvidence` : autorisation et storage privé existaient, `nosniff` et `Cache-Control: private, no-store` manquaient.
- Services `JourneyArtifact` : autorisation canonique existait, `nosniff` et `Cache-Control: private, no-store` manquaient.

Les corrections restent dans leurs vues propriétaires et les tests anti-IDOR existants sont conservés.

### XSS, redirects et sorties navigateur

L'audit ciblé n'a trouvé aucun `mark_safe`. Le seul filtre template `safe` observé concerne le `help_text` du formulaire Django de changement de mot de passe. Les usages `format_html` trouvés sont des previews admin utilisant l'échappement des arguments.

`safe_post_next` et la redirection login utilisent déjà les primitives Django de validation d'hôte/schéma. Aucun client HTTP runtime général consommant une URL utilisateur n'a été trouvé ; l'adapter OpenAI-compatible existant refuse les redirects. M9 n'ajoute donc pas de seconde couche URL/SSRF sans défaut reproductible.

### Supply chain

M9-A ajoute un gate `Security supply chain` pour les workflows gouvernant `main` :

- `pip-audit` sur `requirements.txt` ;
- `bandit` sur le code Python first-party runtime, hors tests/migrations/assets/lab de recherche ;
- `npm audit --omit=dev --audit-level=high` ;
- garde-fou contre les refs GitHub Actions mutables dans les workflows actifs de `main`.

Le premier run du nouveau gate a reproduit un finding critique réel : `maplibre-gl 6.4.0` était affecté par `GHSA-jrc7-96c5-q579` / `CVE-2026-85061`, un contournement du sanitizer XSS. La correction upstream ciblée est `6.4.1`. M9-A a donc mis à jour uniquement cette dépendance directe et son lockfile généré par npm ; `npm ci` puis `npm audit --omit=dev --audit-level=high` passent après correction. Aucun ignore d'advisory n'a été ajouté.

Les SHA ont été résolus depuis les refs officielles `actions/*` :

| Action | Version lisible | SHA pinné |
| --- | --- | --- |
| `actions/checkout` | v4.4.0 | `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/setup-python` | v5 | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/setup-node` | v4 | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `actions/upload-artifact` | v4 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `actions/github-script` | v7 | `f28e40c7f34bde8b3046d885e986cb6290c5673b` |

`Q4 Trusted Reuse validation` n'est pas câblé sur `main` : il cible l'ancienne branche `capital/q4-trusted-reuse-hardening` et `workflow_dispatch`. Le garde-fou M9 ne le présente donc pas comme un check automatique de `main`.

### Repository governance

Au démarrage M9, aucun ruleset n'était visible et la connexion GitHub disponible possède `push` mais pas `admin`. La protection de branche ne peut donc pas être appliquée honnêtement depuis cette orchestration.

Gate externe actuellement **non satisfait** : un administrateur du dépôt doit configurer une protection/ruleset de `main` cohérente avec les checks réellement publiés, afin d'exiger les PR pour les changements importants, empêcher le merge avec les checks requis rouges et limiter les push directs accidentels. Les noms de checks requis doivent être pris depuis les runs M9 verts ; `ci/aggregate` ne doit pas être configuré comme check PR tant qu'il n'est publié que sur les pushes `main`.

M9 ne déclarera pas cette protection active tant qu'elle n'aura pas été vérifiée via GitHub.

## M9-B — à compléter après merge M9-A

Les matrices PostgreSQL existantes couvrent déjà une part importante des races Payment, Capacity, Access, Funding, Subscriptions, Services, Recognition et Domain Events. M9-B se limite aux trous réellement démontrés autour des providers, webhooks, replay/retry et résilience externe.

## M9-C — à compléter après merge M9-B

La fresh install est déjà un gate CI. Des tests `MigrationExecutor` et `assertNumQueries` existent déjà dans plusieurs domaines. M9-C cible seulement les data migrations réellement risquées sans preuve historique suffisante et les projections M8 sans budget de requêtes borné.

## M9-D — à compléter après merge M9-C

M9-D fermera avec des parcours cross-domain sélectifs, les gaps clavier/focus réellement observés, tous les workflows pertinents du runtime courant et le handoff M10.
