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

Le premier run du nouveau gate a reproduit un finding critique réel : `maplibre-gl 6.4.0` était affecté par `GHSA-jrc7-96c5-q579` / `CVE-2026-85061`, un contournement du sanitizer XSS. La correction upstream ciblée est `6.4.1`. M9-A a donc mis à jour uniquement cette dépendance directe et son lockfile généré par npm ; `npm ci` puis `npm audit --omit=dev --audit-level=high` passent après correction. Les artifacts frontend versionnés ont ensuite été régénérés avec le lock corrigé afin que le gate de synchronisation du build reste strict. Aucun ignore d'advisory n'a été ajouté.

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

## M9-B — Integrity, Concurrency & External Resilience

### Base et audit de réalité

M9-B repart de `main@8a21379e804807d9ff11acf3ee54d09024e7636c`, obtenu après le merge de M9-A (#227) puis son correctif CI post-merge (#228). Le HEAD de départ a été vérifié vert sur les gates réellement applicables, dont `CI`, `ci/aggregate`, `Security supply chain`, Beta seed validation et les matrices PostgreSQL déclenchées.

Aucun travail M9-B antérieur n'existait au moment de l'audit : aucune branche, PR, commit, correction ou clôture documentaire correspondante. La branche `m9/integrity-resilience` et la PR #229 ont donc été créées depuis cette base verte. La PR parallèle #223 reste limitée au laboratoire `frontiere_opportunite_lab/*` et ne crée pas de collision runtime ni de migration avec M9-B.

### Garanties déjà présentes avant M9-B

Le runtime possédait déjà des transactions atomiques, `select_for_update`, contraintes uniques/conditionnelles et clés d'idempotence dans plusieurs domaines. Les matrices PostgreSQL couvraient déjà Access, Payments/Subscriptions, Capacity/Commerce, Services, Funding, Recognition, Conversations, Domain Events, Notifications et Automation. M9-B ne duplique pas ces garanties et n'introduit ni lock distribué, ni outbox générique, ni queue, ni nouveau moteur de workflow.

### Finding confirmé — Access / Scanner

Un test PostgreSQL concurrent déterministe, synchronisé par `Barrier`, a reproduit une collision de même `(actor, client_reference)` sur deux `Access` différents. Les deux transactions pouvaient franchir la relecture d'idempotence car elles verrouillaient des lignes `Access` distinctes ; la contrainte `access_use_actor_client_ref_unique` protégeait bien l'intégrité finale mais le perdant recevait un `IntegrityError` brut au lieu du conflit métier attendu.

La correction reste dans `access/services.py` : `_record_use()` exécute l'insert dans un savepoint local. Si la contrainte d'idempotence gagne la course, le savepoint est rollbacké puis la référence est relue. Une collision sur un autre `Access` est transformée en `ValidationError("Cette référence client appartient à un autre contrôle.")`; un replay sur le même `Access` réutilise l'`AccessUse` existant. Aucun lock global n'est ajouté.

Preuves :

- reproduction PostgreSQL dans `access.test_concurrency` ;
- état final protégé par la contrainte DB existante ;
- sémantique séquentielle d'idempotence conservée.

### Finding confirmé — Payments webhook

Le test de reproduction PostgreSQL a prouvé que `process_sandbox_webhook()` enregistrait `PaymentEvent.processing_error` puis relançait l'exception à l'intérieur de la même transaction atomique. L'événement lui-même disparaissait après rollback, donc la trace annoncée comme durable ne l'était pas. La logique de duplicate assimilait en outre un même `event_id`/payload existant à un replay final même lorsque `processed=False`, ce qui aurait empêché un vrai retry une fois la trace rendue durable.

La correction reste dans `payments/services.py` et réutilise les champs existants :

- l'identité `PaymentEvent` est persistée avant la transaction de mutation métier ;
- un événement `processed=True` avec même payload reste un duplicate idempotent ;
- un événement `processed=False` avec même payload est repris pour retry ;
- le même `event_id` avec payload différent reste rejeté ;
- la mutation du paiement et le passage de l'événement à `processed=True` restent dans une transaction atomique avec verrouillage des lignes concernées ;
- si cette transaction échoue, les effets métier sont rollbackés puis `processing_error`/`processed_at` sont persistés hors de la transaction échouée.

Aucun nouvel état métier n'est créé et aucune réécriture de Payments n'est faite.

### Finding confirmé — Notifications / e-mail

`dispatch_delivery()` remettait auparavant en `QUEUED` toute exception tant que `max_attempts` n'était pas atteint. Pour l'adapter e-mail Django utilisé ici, un `TimeoutError` pendant `send()` représente un résultat externe ambigu : l'absence de réponse ne prouve ni l'acceptation ni le rejet par le serveur SMTP. Un retry automatique pouvait donc dupliquer un e-mail déjà accepté.

M9-B réutilise `DeliveryStatus.FAILED` : un `TimeoutError` devient terminal immédiatement et conserve l'erreur redacted, sans retry automatique. Les erreurs clairement pré-envoi telles qu'un `ConnectionRefusedError` gardent la politique de retry existante. Aucun état `UNKNOWN` générique n'est ajouté.

Les tests `notifications.test_m9b_delivery_resilience` couvrent les deux branches du contrat.

### Provider HTTP runtime

Le provider HTTP runtime identifié reste `intelligence.providers.openai_compatible.OpenAICompatibleProvider`. Il possédait déjà les garanties nécessaires : timeout explicite, redirects refusés, classification des erreurs HTTP/réseau/timeout, validation du payload et absence de retry automatique. M9-B ne modifie donc pas le provider ; des fault-injection tests complètent la preuve pour connection failure, HTTP non-2xx et réponse JSON malformée.

### Domain Events / M7

`deliver_domain_event(...)` reste un contrat avec transport injecté/testé ; aucun transport runtime général n'a été identifié. M9-B ne crée donc ni outbox, ni queue, ni worker, ni saga, ni provider générique pour satisfaire artificiellement le gate.

### Migrations et données

M9-B n'ajoute aucune migration. Les corrections reposent sur les modèles, contraintes et états existants. Le contrôle `makemigrations --check`/fresh migrate reste délégué aux gates CI existants.

### CI et fermeture

La première exécution tests-only de la PR #229 a volontairement échoué sur les deux reproductions PostgreSQL confirmées : Access dans `postgresql-core (identity)` et Payments dans `postgresql-ops-commerce`. Les autres shards observés, dont E2E, `postgresql-ops-events`, `postgresql-ops-product`, `postgresql-core (commerce/services)`, `pr-fast` et Security supply chain, étaient verts.

La clôture de M9-B n'est pas déclarée par ce texte : elle requiert encore que le HEAD contenant les corrections ci-dessus passe intégralement les tests ciblés, les matrices PostgreSQL, la suite Django, Security supply chain, E2E et tous les workflows PR applicables avant merge, puis les gates push du `main` post-merge.

### Risques résiduels / handoff M9-C

M9-B ne traite pas les budgets de requêtes, N+1, indexes spéculatifs ni l'audit général `MigrationExecutor` : ces sujets restent à M9-C. Aucun besoin de migration destructive ou de backfill n'a été identifié dans M9-B.

## M9-C — à compléter après merge M9-B

La fresh install est déjà un gate CI. Des tests `MigrationExecutor` et `assertNumQueries` existent déjà dans plusieurs domaines. M9-C cible seulement les data migrations réellement risquées sans preuve historique suffisante et les projections M8 sans budget de requêtes borné.

## M9-D — à compléter après merge M9-C

M9-D fermera avec des parcours cross-domain sélectifs, les gaps clavier/focus réellement observés, tous les workflows pertinents du runtime courant et le handoff M10.