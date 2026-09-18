# Makolo — Acteur 1 : Prospecteur

> **Statut du train : PX2 — sources autonomes / index externes.**
>
> Base initiale du train : main@9c60119f4eab8628ff33b230562f85ed8500c632.
> PX2 est empilé sur PX1@9c2654bac8b8cfc54234359e18c65afb66138edc.
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

## 6. Ce que PX2 ne fait pas

PX2 ne :

- maintient aucune liste manuelle de sites ;
- ne récupère aucun HTML de page ;
- n'utilise pas Crawlee ;
- n'interprète pas le contenu ;
- ne décide pas qu'une URL est une opportunité ;
- ne crée aucune vérité métier ;
- n'utilise ni Elasticsearch, Redis, Kafka, LLM ni navigateur headless ;
- ne fait pas encore de WebGraph, sitemap ou feed expansion : PX5 ;
- ne définit pas encore le contrat complet Prospecteur ↔ Observateur : PX3 ;
- ne porte pas encore la sécurité réseau générique SSRF/DNS : PX4.

## 7. Train

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
PX8  pilote Internet réel
 ↓
PX9  hardening / échelle
~~~

## 8. Validation PX2

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
