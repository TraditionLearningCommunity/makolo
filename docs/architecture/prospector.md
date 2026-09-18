# Makolo — Acteur 1 : Prospecteur

> **Statut du train : PX8 — pilote Internet réel borné et mesurable.**
>
> Base réconciliée : main@dcef775870afec0736cbfc018ad09d40913e01c6.
> PX8 est empilé sur PX7@1dc377cd96b3a3c876e9066bad571fa1a061347e.
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

## 9. PX5 : expansion autonome bornée

PX5 ferme la boucle structurelle :

~~~text
Frontier parent
      ↓
Observateur
      ↓ ObservationReport.references
PX5 Expansion
      ↓
Frontier enfants
      ↓
Observateur
~~~

Le Prospecteur ne reparcourt jamais le HTML/XML pour découvrir ces enfants.
L'Observateur est responsable de produire les références structurelles ; PX5
ne fait que les classer, borner et admettre.

### Familles génériques

PX5 reconnaît trois familles techniques :

~~~text
web_graph
  link
  redirect
  redirect_final
  canonical
  alternate

sitemap
  sitemap
  sitemap_index
  sitemap_entry

feed
  feed
  feed_entry
~~~

Ce vocabulaire ne crée aucune vérité métier. Une `sitemap_entry` signifie
uniquement qu'une ressource a été révélée par une structure sitemap.

Il n'existe aucun agent par site, média, université ou domaine.

### Héritage du contexte

Le report Observateur ne répète pas mission/campagne/branche/profondeur.
PX5 relit le parent par `target_key` dans la Frontier puis propage :

~~~text
mission_key
campaign_key
branch_key
autres contextes de politique
depth + 1
~~~

La provenance durable de l'enfant contient :

~~~text
source_target_key
source_observation_ref
method = web_graph | sitemap | feed
relation technique
handoff_generation source
fingerprint de politique d'expansion
~~~

Ainsi le graphe utile reste un **graphe borné de provenance dans la Frontier**,
pas une copie générale du Web.

### Anti-traps

`ExpansionPolicy` exige explicitement les limites suivantes :

~~~text
max_depth
max_references_per_report
max_candidates_per_report
max_same_host_candidates
max_cross_host_candidates
max_unique_cross_hosts
max_per_host_candidates
max_per_url_shape
max_query_parameters
max_path_segments
~~~

Aucune valeur de production n'est codée en dur.

`ExpansionPolicy.enabled = false` coupe uniquement l'expansion structurelle ;
l'Observation peut continuer. Les limites same-host/cross-host/query/path
acceptent explicitement `0` pour exprimer « interdit » sans règle implicite.

Les formes d'URL compactent uniquement des structures susceptibles d'exploser
dans un même report : valeurs de pagination, dates, identifiants numériques,
UUID et longs identifiants hexadécimaux. Les query values sont ignorées dans
la forme, mais les noms de paramètres sont conservés.

Exemple :

~~~text
/calendar/2026-09-18?page=1
/calendar/2026-09-19?page=999
                 ↓
même forme bornable
~~~

Cela ne fusionne pas les identités Frontier : la canonicalisation cible
conserve toujours l'URL complète et sa query. La forme sert uniquement au
budget anti-explosion.

### Dédoublonnage local et boucles

Dans un même report, PX5 élimine avant admission :

- self-reference vers le parent ;
- duplicata de target_key ;
- relation inconnue ;
- kind non supporté ;
- locator invalide ;
- dépassement de profondeur/query/path/fan-out/host/forme.

Une rediffusion du même ObservationReport ne crée ni nouvelle FrontierEntry ni
nouvelle ligne d'arête : les identités PX1 compactent le replay.

### Divulgation minimale

PX5 ne copie pas librement `ObservedReference.attributes`.

Seuls les attributs techniques explicitement autorisés sont propagés, par
défaut :

~~~text
media_type
hreflang
rel
type
~~~

Un titre, du texte, un pseudo-fait, un secret ou une annotation sémantique
arbitraire ne devient donc pas de la provenance Prospecteur.

## 10. PX6 : runtime continu et frontière Crawlee

PX6 transforme les contrats PX1→PX5 en une boucle d'exécution continue :

~~~text
Frontier READY
    ↓ claim + lease PostgreSQL
ObservationGate PX4
    ↓
Observateur durable
    ↓ receipt
    ├── ACCEPTED / ALREADY_ACCEPTED → Frontier COMPLETED
    ├── DEFERRED                   → Frontier READY à retry_at
    └── REJECTED                   → Frontier SUPPRESSED
~~~

Le runtime est `ProspectorRuntime`. Ses paramètres sont injectés via
`RuntimePolicy` :

- worker_id ;
- taille de claim ;
- durée de lease ;
- délai de retry sur panne technique ;
- cadence de polling ;
- choix explicite de propager ou non le backpressure Observateur au reste du
  batch déjà claimé.

Aucune valeur de production n'est codée en dur.

### Recovery

Avant l'accusé de réception Observateur, la lease PX1 reste la source de
recovery.

~~~text
worker A claim
  ↓
crash avant ACCEPTED
  ↓ expiration lease
worker B reclaim
  ↓
même target_key
même handoff_generation
même handoff_key
~~~

Le nouvel envoi reste donc idempotent côté Observateur.

Une exception technique lors du handoff libère explicitement le claim vers
`READY` avec le délai `exception_retry_seconds`.

Une violation de contrat `ProspectorContractError` n'est jamais masquée par
ce retry : elle remonte pour être corrigée.

### Backpressure

Un receipt Observateur `DEFERRED` porte déjà son `retry_at`.

Par défaut PX6 considère ce signal comme un backpressure du consumer :

- le claim courant est différé ;
- les autres claims déjà acquis dans le batch sont libérés au même
  `retry_at` ;
- aucun appel Observateur supplémentaire n'est effectué dans ce batch.

Cette propagation est désactivable explicitement par
`stop_on_observer_deferred=False`.

### Crawlee

PX6 ajoute `crawlee==1.10.1` comme dépendance explicite.

Makolo utilise ici **RequestQueue comme frontière d'exécution**, pas comme
Frontier ni comme vérité métier.

`CrawleeObservationInbox` :

- reçoit uniquement `ObservationTarget` ;
- construit un `Request` Crawlee ;
- force `unique_key = handoff_key` ;
- place le contrat technique sous `user_data["makolo"]` ;
- ne transmet ni provenance complète, ni contexte métier, ni faits ;
- détecte un handoff déjà présent avant le contrôle de capacité ;
- retourne `ALREADY_ACCEPTED` pour les replays ;
- retourne `DEFERRED / observer.capacity` lorsque la queue atteint le plafond
  explicite.

Le seuil de queue et le délai de retry sont injectés via
`CrawleeQueuePolicy`. Une capacité `0` est une pause dure valide.

### Stockage Crawlee

PX6 **ne choisit pas** le stockage Crawlee de production.

Le caller doit injecter une `RequestQueue` appartenant à l'Observateur avec
la durabilité requise par son déploiement. Makolo ne suppose donc ni disque
local, ni Redis, ni SQL Crawlee, ni credentials.

La Frontier PostgreSQL Makolo reste la seule vérité durable du Prospecteur.

### Séparation des acteurs

PX6 ne transforme pas le Prospecteur en crawler HTTP.

~~~text
Prospecteur
  ↓ ObservationTarget
Crawlee RequestQueue
  ↓
Observateur
  ↓ fetch / robots / redirects / contenu
~~~

Le fetch réel, la revalidation DNS à chaque connexion/redirect, robots,
politeness, contenu et production d'`ObservationReport` restent propriété de
l'Observateur.

C'est volontaire : utiliser Crawlee dans PX6 ne doit pas faire disparaître la
frontière architecturale validée en PX3.

### Assemblage Django

`build_django_crawlee_runtime(...)` compose :

- DjangoFrontierStore ;
- ObservationGate ;
- SystemDnsResolver ;
- TldExtractDomainScope ;
- DjangoBudgetStore ;
- CrawleeObservationInbox ;
- SafeObservationHandoff ;
- ProspectorRuntime.

La RequestQueue est injectée par l'appelant ; aucune configuration de
production n'est inventée.

## 11. PX7 : apprentissage opérationnel sans vérité métier

PX7 ajoute un retour aval borné permettant au Prospecteur d'apprendre **où
prospecter davantage**, sans conclure lui-même qu'une page est une Activity,
Requirement, Proof ou autre fait métier.

### Signaux aval

Le contrat `ProspectingFeedback` est volontairement petit :

~~~text
event_key
target_key
signal
producer
source_ref
occurred_at
~~~

Signaux admis :

~~~text
observation_valid
structured_information
reality_new
reality_refreshed
no_useful_information
downstream_rejected
~~~

Ces valeurs signifient uniquement qu'un acteur aval a déclaré un résultat de
pipeline. Le Prospecteur ne reçoit ni contenu, ni faits extraits, ni objets
métier.

Le `event_key` rend chaque feedback idempotent. Une collision du même
event_key avec un autre payload est une erreur de contrat.

### Attribution technique

Au moment d'enregistrer l'événement, PX7 photographie uniquement des dimensions
déjà connues dans la Frontier :

~~~text
lineage_target
method
provider
mission
campaign
branch
~~~

`lineage_target` inclut la cible elle-même et les parents
`source_target_key`. Ainsi un enfant découvert à partir d'une cible productive
peut bénéficier de ce signal sans copier le contenu ni la vérité métier du
parent.

### Journal brut et projection

PX7 sépare :

~~~text
ProspectorFeedbackEvent
        = événement brut immuable

ProspectorFeedbackStat
        = projection de score reconstruisible

ProspectorFeedbackProjection
        = checkpoint de projection par politique
~~~

Les poids appartiennent à `FeedbackPolicy` et doivent être explicitement
fournis pour **chaque signal**.

Le fingerprint dépend du policy_key et de tous les poids. Changer les poids
crée donc une nouvelle projection qui peut rejouer le même journal brut depuis
l'événement 1. Aucun historique n'est réécrit.

### Score

PX7 n'emploie ni modèle opaque ni float caché.

Pour chaque dimension configurée :

~~~text
sample_count
score_sum
~~~

sont combinés par des poids de dimension explicites.

Le score moyen est une fraction exacte :

~~~text
weighted_score_sum / weighted_samples
~~~

Il n'existe aucun prior implicite.

### Exploration / exploitation

`AdaptivePolicy` exige explicitement :

~~~text
dimension_weights
min_samples_for_exploitation
exploration_numerator
exploration_denominator
candidate_pool_multiplier
projection_batch_size
~~~

La Frontier garde son `priority` existant comme contrôle de base.

PX7 procède en deux étages :

~~~text
1. priority / available_at
   → bornent le candidate pool

2. dans ce pool :
   - cibles peu échantillonnées → exploration
   - cibles suffisamment échantillonnées → exploitation par rendement
~~~

Une part du batch est réservée à l'exploration. Le reste exploite les routes
mieux documentées. Si l'une des classes manque de candidats, l'autre remplit
les places restantes.

Une exploration_numerator = 0 désactive explicitement la réserve
d'exploration.

### Concurrence

`DjangoAdaptiveFrontierStore` conserve les verrous PX1 :

- `select_for_update(skip_locked=True)` sur PostgreSQL ;
- leases ;
- claim tokens ;
- handoff_generation.

L'apprentissage ne crée donc pas une deuxième file d'attente et ne permet pas
à deux workers de prendre la même cible.

### Intégration runtime

PX7 ajoute `build_django_adaptive_crawlee_runtime(...)`.

La seule différence avec PX6 est la stratégie de claim. Gates, budgets,
Crawlee, receipts, recovery et transitions restent inchangés.

Le runtime non adaptatif PX6 reste disponible : activer l'apprentissage est
donc une décision explicite, pas un changement silencieux de comportement.

## 12. PX8 : pilote Internet réel borné

PX8 ne transforme pas le Prospecteur en crawler général. Il rend possible un
**pilotage live explicite** de la chaîne que l'acteur Prospecteur possède déjà :

~~~text
Common Crawl public
      ↓
ProspectingMission bornée
      ↓
IndexProspector
      ↓
Frontier PostgreSQL
      ↓
(scorecard PX8)
~~~

Si un runtime Observateur est injecté par le déploiement, le runner PX8 sait
également exécuter un nombre borné de cycles :

~~~text
Frontier
  ↓
PX4 gates / budgets
  ↓
RequestQueue Observateur
~~~

PX8 n'invente cependant aucune RequestQueue de production. La commande Django
live fournie dans ce checkpoint reste donc **source → Frontier** par défaut.

### 12.1 Confirmation et bornes obligatoires

La commande `prospector_live_pilot` refuse tout accès Internet sans
`--confirm-live-internet`.

Elle exige explicitement :

~~~text
user_agent
mission_key
host_tld
path_term
max_candidates
max_source_requests
source_passes
request_interval_seconds
timeout_seconds
~~~

Il n'existe ni site seedé, ni domaine métier codé en dur, ni valeur de
production cachée.

Une mission reste une couverture :

~~~text
TLD + termes de chemin + langues + MIME + budget
~~~

et jamais une liste de sites à scraper.

### 12.2 Corrections découvertes par le premier probe live

Le premier probe PX8 contre Common Crawl a invalidé deux hypothèses PX2.

**1. Forme TLD CDXJ**

La forme précédente :

~~~text
url=*.cd
matchType=domain
~~~

n'est pas la bonne forme pour le scan TLD borné utilisé ici.

PX8 utilise :

~~~text
url=*.cd/*
~~~

sans `matchType=domain`.

**2. Termes de chemin ≠ sous-chaînes arbitraires**

Le filtre précédent :

~~~text
formation
~~~

pouvait sélectionner une URL contenant :

~~~text
information
~~~

PX8 génère donc une regex avec des séparateurs URL explicites. Les termes
restent des sélecteurs techniques ; ils ne constituent toujours pas une
interprétation métier.

### 12.3 Politesse Common Crawl

Le provider accepte désormais `request_interval_seconds` et sérialise ses
requêtes. Un pilote live exige une valeur strictement positive.

HTTP 429/503 devient une erreur opérationnelle de rate limit et **n'entraîne
aucune boucle de retry agressive**.

Les pages CDX 400/404 sont traitées comme fin du sélecteur courant.

La CI continue d'utiliser un transport factice et ne contacte jamais Internet.

### 12.4 Scorecard

PX8 mesure uniquement des faits techniques agrégés :

~~~text
source:
  passes
  revision
  records reçus
  admissions tentées

Frontier:
  nouvelles cibles uniques
  redécouvertes
  statuts
  suppressions
  méthodes de provenance
  providers

runtime, si injecté:
  claimed
  handoff accepted
  deferred
  suppressed
  errors
  backpressure released

feedback aval:
  événements
  signaux réellement reçus
~~~

Le scorecard ne contient ni liste d'URLs, ni contenu Web, ni PII, ni objets
métier.

Les ratios sont représentés par `numerator/denominator`, pas par un score
flottant opaque.

Si l'Observateur ou le feedback aval ne sont pas exécutés, le rapport indique
explicitement :

~~~text
observer_runtime_not_run
downstream_feedback_not_observed
~~~

Il ne transforme jamais l'absence de données en succès.

### 12.5 Commande live

Exemple **illustratif, non production** :

~~~text
python manage.py prospector_live_pilot \
  --confirm-live-internet \
  --user-agent "Makolo Prospecteur PX8 (operator contact)" \
  --mission-key px8-rdc-fragments \
  --host-tld cd \
  --path-term formation \
  --path-term admission \
  --max-candidates 25 \
  --max-source-requests 2 \
  --source-passes 1 \
  --request-interval-seconds 2 \
  --timeout-seconds 20 \
  --report-file /existing/path/px8-scorecard.json
~~~

L'exemple n'est pas une configuration permanente du produit.

## 13. Ce que PX8 ne fait pas

PX8 ne :

- maintient aucune liste manuelle de sites ;
- ne récupère aucun HTML de page ;
- n'interprète pas le contenu ;
- ne décide pas qu'une URL est une opportunité ;
- ne crée aucune vérité métier ;
- n'utilise ni Elasticsearch, Kafka, LLM ni navigateur headless ;
- ne produit aucune vérité métier à partir du score ;
- ne modifie pas les Permissions, Mandates, Access, Readiness ou données privées ;
- ne choisit pas le stockage de production de la queue Observateur ;
- n'implémente pas le fetch HTTP/JS de l'Observateur ;
- ne transforme pas une correspondance de chemin en fait métier ;
- ne considère pas l'absence de feedback aval comme une preuve de qualité ;

## 14. Train

~~~text
PX0  fondation Python pure
 ↓
PX1  Frontier PostgreSQL durable
 ↓
PX2  sources autonomes / index externes
 ↓
PX3  contrat Prospecteur ↔ Observateur
 ↓
PX4  sécurité réseau / admissibilité / budgets
 ↓
PX5  expansion autonome : graphe Web, sitemaps, feeds, anti-traps
 ↓
PX6  runtime continu + Crawlee / recovery / backpressure
 ↓
PX7  feedback aval + exploration/exploitation
 ↓
PX8  pilote Internet réel                                          ← courant
 ↓
PX9  hardening / échelle
~~~

## 15. Validation PX8

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


Tests PX5 spécifiques :

~~~text
python -m unittest   prospector.tests.test_traps   prospector.tests.test_expansion

python manage.py test   prospector.django_app.tests.test_expansion
~~~

Ils vérifient notamment :

- WebGraph, sitemap et feed sans parsing de contenu dans le Prospecteur ;
- propagation de mission/campagne/branche/profondeur depuis le parent ;
- provenance parent + observation ;
- dédoublonnage self/duplicate ;
- limites same-host/cross-host/hôtes uniques ;
- limite par forme d'URL ;
- bornes query/path/profondeur/fan-out ;
- whitelist d'attributs techniques ;
- replay sans duplication de cible ni de ligne de provenance.

PX5 n'ajoute aucune migration.


Tests PX6 spécifiques :

~~~text
python -m unittest   prospector.tests.test_runtime   prospector.tests.test_crawlee_queue

python manage.py test   prospector.django_app.tests.test_runtime
~~~

Ils vérifient notamment :

- ACCEPTED / ALREADY_ACCEPTED → complete ;
- gate REJECT → suppress ;
- gate DEFER → defer ;
- observer REJECTED → suppress ;
- observer DEFERRED → backpressure du batch ;
- panne technique → defer/retry sans perte ;
- violation de contrat → erreur visible, pas retry silencieux ;
- boucle continue bornable par superviseur/tests ;
- unique_key Crawlee = handoff_key ;
- user_data minimal et technique ;
- duplicate Crawlee → ALREADY_ACCEPTED ;
- queue saturée → DEFERRED ;
- capacité zéro → pause dure ;
- transitions réelles PostgreSQL completed/ready.

PX6 n'ajoute aucune migration.


Tests PX7 spécifiques :

~~~text
python -m unittest   prospector.tests.test_feedback

python manage.py test   prospector.django_app.tests.test_feedback   prospector.django_app.tests.test_feedback_concurrency   prospector.django_app.tests.test_adaptive_frontier
~~~

Ils vérifient notamment :

- contrat feedback sans payload métier ;
- fingerprint de politique ;
- scopes lineage/method/provider/mission/campaign/branch ;
- propagation du rendement parent vers enfant ;
- replay idempotent d'un événement ;
- collision event_key détectée ;
- projection positive/neutre/négative ;
- changement de poids → projection indépendante reconstruite ;
- exploration réservée ;
- exploitation par rendement ;
- exploration désactivable explicitement ;
- recovery de lease inchangé ;
- feedback concurrent compté une seule fois ;
- deux workers adaptatifs sans double claim.

PX7 ajoute la migration `prospector_storage.0005_feedback_learning`.


Tests PX8 spécifiques :

~~~text
python -m unittest \
  prospector.tests.test_common_crawl \
  prospector.tests.test_pilot

python manage.py test \
  prospector.django_app.tests.test_pilot \
  prospector.django_app.tests.test_pilot_command
~~~

Ils vérifient notamment :

- forme live `*.tld/*` sans `matchType=domain` ;
- bornes de termes URL (`formation` ne matche pas `information`) ;
- cadence entre requêtes Common Crawl ;
- arrêt explicite sur 503/rate limit ;
- 404 CDX traité comme fin de sélecteur ;
- source passes bornées ;
- runtime cycles bornés lorsqu'un runtime est injecté ;
- refus d'un runtime demandé mais absent ;
- scorecard sans URL ;
- snapshot Django strictement scoped par mission fingerprint ;
- refus de la commande live sans confirmation explicite ;
- commande testée sans Internet via provider factice.

PX8 n'ajoute aucune migration.
