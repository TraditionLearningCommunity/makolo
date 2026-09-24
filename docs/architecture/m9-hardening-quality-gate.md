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

- `pip-audit` sur les profils runtime `requirements.txt`, `requirements-prospector.txt` et `requirements-observer.txt` ;
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

M9-B est fermé : la PR #229 a été mergée et `main@787dd3ee6496d9ec94744e4ea3e36be57c354d66` a été vérifié vert après merge, y compris `ci/aggregate` et les gates applicables. M9-C repart exclusivement de ce HEAD vert.

### Risques résiduels / handoff M9-C

M9-B ne traite pas les budgets de requêtes, N+1, indexes spéculatifs ni l'audit général `MigrationExecutor` : ces sujets restent à M9-C. Aucun besoin de migration destructive ou de backfill n'a été identifié dans M9-B.

## M9-C — Data, Migrations & Performance

M9-C repart de `main@787dd3ee6496d9ec94744e4ea3e36be57c354d66`. L'audit runtime a retrouvé 45 fichiers contenant `RunPython`, aucun `RunSQL`, un `SeparateDatabaseAndState`, les quatre familles de tests `MigrationExecutor` déjà présentes et `scripts/check_legacy_upgrade.py`. La fresh install reste couverte par la CI existante ; aucun framework parallèle n'est ajouté.

Le risque migration retenu est `commerce/0003_financial_quote_snapshot`, transformation sémantique des anciens totaux Order/Item vers `expected_payee_amount` et un snapshot legacy explicite. Un test `MigrationExecutor` ciblé construit les données avec les historical models de `commerce/0002`, applique `0003`, vérifie qu'aucune vérité provider/destination n'est inventée puis restaure les leaf nodes. Aucune ancienne migration n'est modifiée et aucun nouveau backfill n'est ajouté.

Côté performance, les garanties déjà présentes dans Goals, Trust, Readiness, Subscriptions, Preparation, Discover et Journey ne sont pas dupliquées. Deux croissances SQL ont été retenues : le catalogue Recognition recalculait jusqu'à trois comptes par Reward ; la liste Conversations relisait état personnel, participation/visibilité et fenêtres de Points objet par objet. Recognition utilise désormais des agrégations filtrées dans son selector propriétaire ; Conversations précharge uniquement l'état du Profile courant, ses participations explicites et les fenêtres de Points nécessaires, avec fallback vers l'autorité/audience canonique pour les accès dérivés.

Les budgets ajoutés prouvent 12 Rewards avec les trois limites en une requête catalogue et 12 Conversations accessibles par participation explicite dans un budget fixe de 8 requêtes maximum. Aucun index, champ, modèle, cache distribué, dénormalisation ou vérité Readiness persistée n'est ajouté. Les détails d'audit et de handoff sont consignés dans `docs/architecture/m9-c-data-migrations-performance.md`.

M9-C est fermé : la PR #230 a été mergée et `main@bf5f5ffb902ff0a63a97ba95eee89466057e22c5` a été vérifié vert, avec `ci/aggregate = success`. M9-D repart de ce HEAD.

## M9-D — Cross-domain Quality Gate & Closure

### Base, scope et non-duplication

M9-D repart de `main@bf5f5ffb902ff0a63a97ba95eee89466057e22c5` sur la branche `m9/quality-gate`, PR #231. Le préflight confirme que #223 reste draft et limité à `frontiere_opportunite_lab/*`, sans collision runtime, migration ou dépendance M9.

Le travail ne crée aucun domaine, modèle, endpoint général, BFF, scheduler, queue, nouvelle persistance ou migration. Les parcours déjà solides ne sont pas recopiés : en particulier Payment → Access → Scanner → AccessUse, les tests spécialisés Funding/Recognition/Subscriptions, les budgets SQL M9-C et les audits spécialisés M9-A/B restent leurs preuves propriétaires.

### Parcours de convergence retenus

Les preuves M9-D ajoutent ou consolident les jointures suivantes :

- visiteur → Discover → possibilité publique → détail Activity/Event → CTA d'action nécessitant authentification, sans navigation préalable vers `/me/` ni fuite de contenu privé ;
- Home avec action réelle puis Home calme avec `Tout est en ordre. ✓`, sans remplissage artificiel par Discover ;
- Space : membre Finance sans autorité de contrôle refusé par le serveur, puis acteur propriétaire autorisé ;
- ActionNeed → ActionProposal → acceptation → Conversation contextuelle unique, avec outsider refusé par l'autorité Conversation ;
- M7 Connection autorisée → Action réussie → Connection désactivée → même Action refusée.

La fixture Playwright globale conserve le garde-fou : tout HTTP `>=500`, erreur console, violation CSP ou asset statique manquant échoue le scénario.

### Finding réel — verrouillage PostgreSQL Action Network

Le nouveau parcours Action Network → Conversation a révélé sur PostgreSQL un défaut invisible sous SQLite : plusieurs opérations de `social/bilateral_services.py` combinaient `select_for_update()` et `select_related()` sur des relations nullable. PostgreSQL refusait alors la requête avec `FOR UPDATE cannot be applied to the nullable side of an outer join` avant même la création de l'ActionProposal.

La correction reste dans le domaine Social et ne change aucun état métier : les verrous sont bornés aux lignes propriétaires avec `select_for_update(of=("self",))`, tandis que les relations restent chargées pour les décisions d'autorité et de contexte. Les chemins concernés sont ActionNeed/ActionProposal transactionnels qui utilisaient ce motif. Le test `conversations.test_m9d_cross_domain` est la non-régression PostgreSQL de la convergence jusqu'à Conversation.

Après correction, le workflow `Conversation PostgreSQL` est vert.

### Rituels M8

M9-D ne redesigne aucun rituel. Les preuves existantes restent propriétaires pour `Est-ce que tout est prêt ?`, `Il est temps d'y aller`, Occurrence Live/terminal, Discover borné, Space Now et responsive. M9-D ajoute explicitement les deux états Home : priorité immédiate présente lorsque nécessaire, et `Tout est en ordre. ✓` lorsqu'aucune action pertinente n'exige d'attention.

Discover reste distinct de Home et l'entrée visiteur prouve une exploration publique Activity-first avant authentification.

### Autorité, confidentialité et API/server parity

Les assertions de fermeture ne se limitent pas aux boutons :

- le membre Space sans permission de contrôle reçoit un refus HTTP serveur ;
- l'outsider Conversation est refusé par les services/audiences propriétaires ;
- la désactivation d'une Connection M7 rend l'Action non autorisée côté serveur ;
- Readiness, Payment, Access, Mandates et Conversation privacy ne sont pas déplacés vers JavaScript ou des fragments HTMX.

L'invariant `Membership ≠ authority` reste démontré. Aucune normalisation artificielle 403/404 entre domaines n'est introduite.

### Error states et no-500

Les scénarios M9-D s'appuient sur les erreurs métier déjà contractualisées et sur le garde-fou Playwright `>=500`. Les suites existantes continuent de couvrir 403/404/500, Access/Payment/Occurrence/Conversation et providers selon leurs domaines propriétaires. Aucun faux succès ni 500 attendu n'a été conservé comme comportement acceptable.

Le seul nouveau défaut cross-domain reproduit pendant M9-D est le verrouillage PostgreSQL Social décrit ci-dessus ; il est corrigé et couvert par non-régression.

### Accessibilité, clavier, focus et responsive

Axe existait déjà et reste l'outil unique. M9-D étend la couverture ciblée à Journey et Occurrence Live et ajoute un chemin clavier/focus sur l'authentification. Les contrats responsive M8-E existants (320–768) et les scénarios Space/mobile restent utilisés plutôt que dupliquer une matrice de screenshots.

La matrice navigateur reste volontairement Chromium desktop, Chromium mobile et Firefox smoke ; aucun WebKit n'est ajouté sans contrat produit ou bug réel.

### Migrations

M9-D n'ajoute aucune migration. Les gates `python manage.py check`, `python manage.py makemigrations --check --dry-run`, fresh migrations SQLite/PostgreSQL et la suite Django passent sur la PR #231.

### CI PR

Sur le HEAD de PR M9-D vérifié avant merge, les workflows applicables sont verts :

- `CI` — success, incluant Django complet, PostgreSQL shards et E2E ;
- `Security supply chain` — success ;
- `Beta seed validation` — success ;
- `Conversation PostgreSQL` — success ;
- `Funding PostgreSQL` — success ;
- `Subscriptions` — success.

`ci/aggregate` n'est pas présenté comme un check PR lorsqu'il reste publié selon sa sémantique réelle post-push `main`.

### Governance externe

Au préflight M9-D, `main` reste non protégée et aucun ruleset actif n'est visible. La connexion disponible ne possède pas les permissions admin permettant de configurer honnêtement la protection.

Ce point ne bloque pas artificiellement le code M9-D mais reste un **gate administratif externe M10/pré-production** : un administrateur doit activer une règle de protection compatible avec les checks réellement publiés. M9 ne prétend pas que `main` est protégée.

### Handoff M10 — Production Readiness & Mobile Handoff

M10 doit partir du runtime et des décisions réellement présentes, sans transporter de dette M9 connue. Les sujets opérationnels à résoudre ou confirmer sont :

- **Deployment** : cible de production réelle, procédure de déploiement et rollback ; PythonAnywhere reste un environnement temporaire de test/bêta tant qu'une décision officielle différente n'existe pas ;
- **Database** : PostgreSQL de production, sizing des connexions et procédure de migration ;
- **Workers** : tâches de fond, Automation, Notifications, Domain Events et schedules réellement nécessaires ;
- **Static/media** : stockage, serving, confidentialité et lifecycle ;
- **Secrets** : secrets runtime, credentials providers et rotation opérationnelle ;
- **Backup/restore** : stratégie et exercice de restauration ;
- **Observability** : logs, metrics, alerting externe et traitement des incidents ;
- **Providers** : adapters réellement activés, configuration et modes de panne ;
- **Mobile handoff** : contrats auth, Profile, Home, Discover, Activities/Occurrences, Journeys/Readiness, Conversations, Access, Commerce/Payment et autres surfaces réellement exposées, sans construire une API mobile spéculative dans M9.

Le risque administratif de protection de `main` est explicitement transmis à M10. Aucun bug IDOR connu, race transactionnelle connue, migration cassée, N+1 majeur connu, E2E critique cassé ou finding accessibilité bloquant n'est accepté comme handoff M10.

### État de fermeture

M9-D peut être mergé lorsque le HEAD PR reste vert. La fermeture globale M9 n'est déclarée qu'après vérification du nouveau `main` post-merge, de `ci/aggregate`, des workflows spécialisés déclenchés et de l'absence de PR M9-D ouverte.

État visé après ce contrôle post-merge :

- M9-A ✅
- M9-B ✅
- M9-C ✅
- M9-D ✅
- **M9 — Mature Hardening & Quality Gate ✅**
