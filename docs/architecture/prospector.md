# Makolo — Acteur 1 : Prospecteur

> **Statut du train : PX4 — sécurité, admissibilité et budgets.**
>
> Base initiale du train : main@9c60119f4eab8628ff33b230562f85ed8500c632.
> PX3 est empilé sur PX2@a3b676303c4144db80e68a0515064e906e7c0c92.
> Le code, les migrations, les tests et le main courant restent prioritaires.

## 1. Mission

Le Prospecteur cherche **où regarder** pour révéler des fragments utiles au
réseau d'action Makolo. Il ne cherche pas une « opportunité complète ».

Une condition, une procédure, une session, un centre, un financement, une
deadline, une ressource ou un moyen d'accès peuvent être des découvertes
importantes même si aucune source ne contient la chaîne d'action complète.

Le Prospecteur ne comprend pas la sémantique métier du contenu. Il remet des
cibles à l'Observateur ; Interpréteur et Résolveur établissent ensuite les faits
et les identités métier.

## 2. PX2 : aucune liste de sites à scraper

PX2 introduit ProspectingMission. Une mission décrit un **périmètre de
couverture**, pas un registre de sites :

- TLD ou espaces techniques à couvrir ;
- langues recherchées comme contexte de mission ;
- termes de chemins servant à borner la prospection d'index ;
- types MIME ;
- budget maximum de candidats ;
- contexte de couverture.

Il n'existe pas de champ sites/domains_to_scrape.

Exemple conceptuel :

~~~text
mission
  host_tlds = [cd]
  path_terms = [formation, admission, inscription]
  max_candidates = 500
~~~

Ces sélecteurs sont des politiques de prospection, jamais des assertions selon
lesquelles les URLs trouvées contiennent effectivement une formation ou une
admission.

## 3. Port générique d'index externe

~~~text
ProspectingMission
        ↓
ExternalIndexSourcePort
        ↓
SourceBatch
        ↓
IndexProspector
        ↓
ProspectingCandidate
        ↓
Frontier
~~~

Une source externe renvoie IndexedResource :

- locator ;
- provider ;
- révision de l'index ;
- référence de provenance ;
- timestamp observé ;
- métadonnées techniques éventuelles.

Aucun IndexedResource n'est une Activity, Occurrence, Requirement, Proof,
Access ou autre vérité métier.

## 4. Common Crawl

Le premier adapter est CommonCrawlIndexSource.

PX2 utilise le **CDXJ Index public** pour obtenir des URLs déjà présentes dans
les crawls Common Crawl. Il ne télécharge pas les corps WARC.

Règles PX2 :

- le crawl courant est découvert dynamiquement via collinfo.json ;
- User-Agent descriptif obligatoire ;
- HTTP(S) uniquement vers les endpoints Common Crawl codés dans l'adapter ;
- pagination ZipNum avec pageSize=1 ;
- budget dur de requêtes par passage ;
- status 200 et MIME sont filtrés côté index ;
- une regex de chemin borne la mission ;
- les réponses sont dédupliquées avant admission ;
- un scan TLD sans path_terms est refusé afin de ne pas transformer l'API
  publique en mécanisme de bulk scan.

Common Crawl lui-même recommande le CDXJ pour retrouver des captures/URLs
individuelles et le URL Index columnar pour les requêtes analytiques ou bulk.
Si Makolo a besoin plus tard de scans massifs, un autre adapter pourra utiliser
le URL Index via DuckDB/Spark/Athena sans modifier le core du Prospecteur.

## 5. Checkpoint durable

ProspectorSourceCheckpoint persiste pour chaque source + mission :

- fingerprint exact de la mission ;
- révision du fournisseur ;
- curseur ;
- état exhausted ;
- date du checkpoint.

Le curseur n'avance **qu'après** admission réussie de tout le SourceBatch.
Ainsi, un crash pendant l'admission rejoue le lot précédent ; la Frontier PX1
absorbe ce replay idempotent.

Quand une mission change, son fingerprint change et l'ancien curseur n'est pas
réutilisé.

Pour Common Crawl, un checkpoint exhausted vérifie périodiquement la collection
courante : une nouvelle révision recommence à selector/page/offset zéro.

## 6. PX3 : contrat Prospecteur ↔ Observateur

PX3 fige la frontière sans implémenter encore l'Observateur réseau.

### Prospecteur → Observateur

`ObservationTarget` contient uniquement les informations techniques minimales :

- `handoff_key` idempotent et versionné ;
- `target_key` de la Frontier ;
- `handoff_generation` ;
- locator et kind ;
- date de demande ;
- `observation_hints` techniques.

Le contrat ne transmet pas la provenance complète, le contexte métier, des
Activity/Requirement/Proof/Access, ni une supposition sur ce que contient la
page.

La clé de handoff est dérivée de :

~~~text
target_key + handoff_generation
~~~

et **pas** du `claim_token`. Un worker qui meurt après soumission peut donc
être remplacé : la nouvelle lease obtient un nouveau claim token, mais le même
handoff reste idempotent côté Observateur.

Un `requeue` explicite incrémente `handoff_generation` et crée donc une
nouvelle observation intentionnelle.

### Accusé de réception

L'Observateur renvoie `ObservationReceipt` avec une disposition :

~~~text
ACCEPTED
ALREADY_ACCEPTED
DEFERRED
REJECTED
~~~

`DEFERRED` exige un `reason_code` et un `retry_at`.
`REJECTED` exige un `reason_code` et est terminal au niveau du contrat.

PX3 ne décide pas encore comment un REJECTED devient suppression, revue ou
autre politique Frontier : cette décision appartient à PX4/PX6.

### Observateur → Prospecteur

Le retour structurel est `ObservationReport`.

Il peut contenir :

- locator demandé et locator final ;
- statut HTTP et MIME ;
- références découvertes ;
- métadonnées techniques ;
- échec technique éventuel.

Une `ObservedReference` transporte une relation technique ouverte, par exemple :

~~~text
link
redirect
canonical
sitemap
feed
alternate
~~~

Le vocabulaire reste extensible sans transformer ces relations en vérités
métier.

Le report ne transporte **jamais le corps HTML**, ni les faits sémantiques
extraits. Le contenu et les faits candidats suivent la frontière
Observateur → Interpréteur, hors du Prospecteur.

### Statuts de résultat

~~~text
OBSERVED
NOT_MODIFIED
FAILED
~~~

Un résultat FAILED doit porter un `failure_code`; il peut porter un
`retry_at`. Les résultats réussis ne portent pas de code d'échec.

## 7. Génération durable de handoff

PX3 ajoute `handoff_generation` à chaque FrontierEntry.

~~~text
nouvelle cible       generation = 1
lease expirée        generation inchangée
defer                generation inchangée
redécouverte         generation inchangée
requeue explicite    generation += 1
~~~

Cela distingue deux choses :

- **retry technique du même besoin d'observation** ;
- **nouvelle intention explicite de réobserver**.

Cette génération est durable en PostgreSQL et ne dépend pas de l'identité du
worker.

## 8. PX4 : découverte ≠ droit de collecte

Une cible peut exister dans la Frontier sans être admissible pour une collecte.
PX4 ajoute donc un `ObservationGate` **après le claim Frontier et avant le
handoff Observateur**.

Ordre des gates :

~~~text
claim Frontier
  ↓
kill switch
  ↓
kind / locator
  ↓
scope host / path / profondeur
  ↓
secret dans query
  ↓
IP littérale / DNS preflight
  ↓
domaine enregistrable PSL
  ↓
budgets atomiques
  ↓
ALLOW / REJECT / DEFER
~~~

### Sécurité réseau

Le gate rejette notamment :

- localhost et sous-domaines `.localhost` ;
- IP littérales non globales ;
- toute résolution DNS contenant une adresse non globale ;
- credentials embarqués ;
- paramètres de query portant des noms sensibles connus ;
- hosts/paths explicitement interdits par politique.

Une résolution DNS impossible est **différée**, pas supprimée définitivement.

Le DNS du Prospecteur est uniquement un preflight. L'Observateur doit refaire
la résolution et la validation de l'adresse réellement connectée **à chaque
connexion et à chaque redirect** afin de couvrir DNS rebinding et redirect vers
réseau privé.

### Kill switch

`ObservationPolicy.enabled = false` retourne DEFER avant DNS et avant budget.
Aucune cible n'est supprimée par une pause opérationnelle.

### Domaine enregistrable

PX4 utilise `tldextract==5.3.2` derrière `DomainScopePort`, avec :

~~~text
suffix_list_urls=()
include_psl_private_domains=True
~~~

La Public Suffix List embarquée est donc utilisée **sans fetch réseau runtime**.
Cela évite les erreurs de type `bbc.co.uk → co.uk` et sépare les tenants de
suffixes privés comme `github.io`.

### Budgets

Les limites sont explicitement injectées par politique ; PX4 n'invente aucune
valeur de production.

Scopes disponibles :

~~~text
host
domain
mission
campaign
branch
~~~

Chaque réservation est atomique en PostgreSQL et idempotente par :

~~~text
handoff_key + policy_key + period_start
~~~

Un retry du même handoff ne consomme pas deux fois. Des handoffs concurrents
sur le même scope utilisent des advisory locks et ne peuvent pas dépasser la
limite.

Une politique demandant un scope absent échoue fermée.

### Suppression durable

La Frontier peut maintenant passer :

~~~text
CLAIMED → SUPPRESSED
~~~

avec `suppressed_at` et `suppression_reason`.

Une simple redécouverte ne réactive pas la cible. Un `requeue` explicite
efface la suppression et incrémente `handoff_generation`.

## 9. Ce que PX4 ne fait pas

PX4 ne :

- maintient aucune liste manuelle de sites ;
- ne récupère aucun HTML de page ;
- n'utilise pas Crawlee ;
- n'interprète pas le contenu ;
- ne décide pas qu'une URL est une opportunité ;
- ne crée aucune vérité métier ;
- n'utilise ni Elasticsearch, Redis, Kafka, LLM ni navigateur headless ;
- ne fait pas encore de WebGraph, sitemap ou feed expansion : PX5 ;
- ne porte pas encore la sécurité réseau générique SSRF/DNS : PX4.

## 10. Train

~~~text
PX0  fondation Python pure
 ↓
PX1  Frontier PostgreSQL durable
 ↓
PX2  sources autonomes / index externes
 ↓
PX3  contrat Prospecteur ↔ Observateur            ← courant
 ↓
PX4  sécurité réseau / admissibilité / budgets
 ↓
PX5  expansion autonome : graphe Web, sitemaps, feeds, anti-traps
 ↓
PX6  runtime continu + Crawlee / recovery / backpressure
 ↓
PX7  feedback aval + exploration/exploitation
 ↓
PX8  pilote Internet réel
 ↓
PX9  hardening / échelle
~~~

## 11. Validation PX4

Tests core :

~~~text
python -m unittest discover prospector/tests -v
~~~

Tests stockage :

~~~text
python manage.py test prospector.django_app.tests
~~~

Gates :

~~~text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
~~~

Tous les tests Common Crawl utilisent un transport factice. La CI ne dépend
jamais d'Internet réel.


Tests PX3 spécifiques :

~~~text
python -m unittest   prospector.tests.test_observation_contracts   prospector.tests.test_observation_handoff

python manage.py test   prospector.django_app.tests.test_frontier
~~~

Ils vérifient notamment :

- stabilité de la clé de handoff lors d'un reclaim de lease ;
- changement de clé après requeue explicite ;
- idempotence d'un FakeObserver ;
- refus d'un receipt qui accuse réception d'une autre cible ;
- absence de corps ou faits métier dans ObservationReport ;
- conservation de la génération lors de defer/reclaim.


Tests PX4 spécifiques :

~~~text
python -m unittest   prospector.tests.test_security   prospector.tests.test_domain_scope

python manage.py test   prospector.django_app.tests.test_budget   prospector.django_app.tests.test_frontier   prospector.django_app.tests.test_concurrency
~~~

La CI ne résout aucun host Internet pour ces tests : DNS et budgets sont
contrôlés par fakes, sauf les tests PostgreSQL de verrouillage. La PSL est la
snapshot embarquée par tldextract et aucun téléchargement de suffix list n'est
autorisé au runtime.
