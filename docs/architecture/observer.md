# Observateur Makolo — architecture runtime, Lot 3 HTTP et Lot 4 Browser public

## 1. Rôle

L’Observateur est l’acteur interne chargé d’exécuter des tentatives d’observation sur des ressources externes déjà identifiées, de capturer fidèlement ce qui a été techniquement obtenu ou constaté, puis de rendre ce résultat traçable aux acteurs suivants.

Question de responsabilité :

> **Qu’est-ce que Makolo a effectivement pu obtenir ou constater de cette ressource, ici et maintenant, dans ce contexte d’observation ?**

L’Observateur ne déclare jamais qu’un contenu constitue une Activity, Occurrence, Requirement, Proof, Access ou autre vérité métier. Cette interprétation appartient aux acteurs aval.

## 2. Frontières

~~~text
Prospecteur
  ↓ ObservationTarget
Observateur
  ↓ Observation / Attempt / ObservedArtifact
Interpréteur
  ↓ faits candidats
Résolveur
  ↓ réalité réconciliée
Orchestrateur
~~~

Le Prospecteur possède la découverte, la Frontier et l’intention explicite de réobserver. L’Observateur référence les identifiants du handoff mais ne possède pas la vérité du Prospecteur.

Le Lot 3 reste strictement :

~~~text
HTTP public direct
+ sécurité réseau
+ robots
+ politeness
+ redirects
+ capture brute
+ revalidation HTTP
~~~

Il n’introduit pas :

- Browser ou Playwright ;
- rendu JavaScript ;
- cookies ou session privée ;
- credentials / Authorization ;
- contournement de contrôle d’accès ;
- extraction sémantique ;
- vérité métier ;
- action externe au nom d’un utilisateur.

## 3. Modèle durable

### ObserverHandoff

Copie durable et idempotente du contrat reçu du Prospecteur. Un handoff décrit une intention amont, pas une Observation déjà réalisée.

### ObservationSeries

État longitudinal mutable d’une cible sous un profil d’observation comparable.

Elle porte notamment :

- cible et locator ;
- profil et fingerprint ;
- prochaine échéance de retry ;
- prochaine échéance de watch ;
- validators HTTP lorsqu’ils sont attachés à un artefact durable.

Une nouvelle génération explicite du Prospecteur ne modifie jamais rétroactivement une Observation déjà ouverte.

### Observation

Épisode borné et traçable commencé uniquement au moment du claim réel.

~~~text
due / handoff présent
      ↓
claim atomique
      ↓
Observation OPEN
      ↓
Attempt(s)
      ↓
Observation FINALIZED
~~~

Un item seulement planifié ou en attente n’est pas une Observation.

### ObservationAttempt

Invocation concrète d’une stratégie d’acquisition. Le Lot 3 utilise `direct_http`.

Un Attempt mémorise notamment :

- locator demandé / final ;
- statut HTTP ;
- outcome technique ;
- code d’échec ;
- retry_after_at ;
- nombre de redirects ;
- octets réseau capturés ;
- octets décodés.

### ObservedArtifact

Occurrence immuable d’une représentation effectivement obtenue.

L’identité logique d’artefact est distincte du stockage physique :

~~~text
lundi  : HTTP 200 → artefact A
mardi  : HTTP 200 mêmes octets → artefact B

blob physique :
SHA-256 identique → stockage dédupliqué possible
~~~

Le stockage Observer est privé et hors des médias publics.

## 4. Statuts HTTP et résultat d’Observation

### 2xx et réponses ordinaires

Une réponse HTTP effectivement obtenue est une observation technique. Un 404 peut donc être `OBSERVED` avec un artefact de corps éventuel.

Cela ne signifie jamais « l’Activity est supprimée » ou toute autre conclusion métier.

### 304

Un 304 produit une nouvelle Observation `NOT_MODIFIED`, mais aucun nouvel artefact.

Il doit référencer un artefact durable antérieur de la même série.

~~~text
O1 → artefact A + ETag
O2 → 304
     └─ revalidated_artifacts = [A]
~~~

Un 304 sans baseline durable devient un échec technique explicite ; l’Observateur ne fabrique pas de représentation antérieure.

### 429 / erreurs transitoires

Un 429 devient un échec technique avec `retry_at`, en respectant `Retry-After` lorsqu’il est exploitable.

Les retries automatiques courts sont limités aux pannes plausiblement transitoires : DNS non résolu, timeout et erreur réseau.

Les erreurs TLS, protocole malformé, taille excessive ou violation de sécurité restent visibles sans boucle de retry agressive.

## 5. Sécurité réseau

Le contrôle effectué par le Prospecteur avant handoff ne suffit pas : l’Observateur revalide au moment où la connexion réelle est exécutée.

Pour chaque connexion, y compris après redirect :

1. normalisation stricte de l’URL ;
2. schéma HTTP/HTTPS seulement ;
3. credentials embarqués refusés ;
4. port explicitement autorisé ;
5. résolution DNS immédiate ;
6. validation de **toutes** les adresses retournées ;
7. refus si une adresse n’est pas globale ;
8. sélection d’une IP validée ;
9. connexion TCP directe à cette IP ;
10. hostname original conservé pour Host/SNI/TLS ;
11. vérification que le peer réellement connecté est l’IP validée.

Cette séquence protège notamment contre :

- localhost ;
- RFC1918 / loopback / link-local ;
- metadata cloud ;
- DNS rebinding ;
- réponses DNS mixtes public/privé ;
- redirects vers réseaux privés ;
- scanner de ports arbitraires ;
- second lookup DNS implicite de la bibliothèque HTTP.

Ports par défaut : 80 et 443. Toute extension est explicite.

Le downgrade HTTPS → HTTP est refusé par défaut.

## 6. Redirects

Les redirects sont suivis manuellement afin que chaque hop repasse par :

- politique de port ;
- DNS ;
- sécurité IP ;
- politeness ;
- robots de la destination lorsque la destination n’est pas elle-même un `robots.txt`.

Les boucles sont détectées et le nombre de redirects est borné.

Les validators conditionnels d’une ressource ne sont jamais transférés vers une ressource différente après redirect.

## 7. Robots Exclusion Protocol

Le Lot 3 traite `robots.txt` par **origine** :

~~~text
scheme + host + port
~~~

La politeness reste, elle, partagée au niveau du host.

Le product token robots doit être un token RFC 9309 valide et apparaître dans le User-Agent envoyé.

Le cache normal ne peut pas dépasser 24 heures.

Makolo applique une politique volontairement conservatrice :

- 2xx : règles parseables appliquées ;
- 401/403 : ne pas crawler ;
- autres 4xx : ressource robots considérée indisponible, accès possible ;
- 5xx/429 : ne pas crawler maintenant ; retry borné ;
- erreur réseau : échec technique, pas de contournement.

Les redirects de `robots.txt` restent soumis à la sécurité réseau. Les règles finalement obtenues s’appliquent à l’origine initiale observée.

## 8. Politeness et concurrence

`ObserverScopeState` porte un état partagé entre workers.

### Host scope

Il assure :

- lease exclusive ;
- `not_before` ;
- dernière requête ;
- cadence minimale.

Deux workers PostgreSQL ne peuvent donc pas lancer simultanément une requête pour le même host sous le contrat courant.

Le même worker doit lui aussi respecter `not_before` entre deux requêtes.

Un petit délai peut être attendu inline. Un délai supérieur à la borne inline ferme l’épisode courant avec un retry planifié au lieu de bloquer un worker arbitrairement longtemps.

### Origin scope

Il porte le cache robots sans confondre HTTP et HTTPS ni deux ports différents.

## 9. Bornes de ressources

Le Lot 3 possède des limites explicites sur :

- timeout de connexion ;
- timeout de lecture ;
- durée totale d’une Observation HTTP ;
- redirects ;
- taille du corps reçu ;
- taille après décompression ;
- taille de `robots.txt` ;
- temps d’attente inline ;
- ports autorisés.

La deadline totale traverse robots, redirects et fetch final : une chaîne de réponses lentes ne peut pas maintenir une Observation ouverte indéfiniment.

La lease d’Observation doit être strictement supérieure à cette deadline.

Le transport accepte `gzip` et `deflate` sous limite décodée. Un encodage non supporté ou une expansion au-delà de la limite échoue avant création d’artefact.

## 10. Revalidation HTTP

Lorsqu’un artefact durable existe, sa série peut retenir :

- `ETag` ;
- `Last-Modified` ;
- `validator_artifact_ref`.

Le fetch suivant peut envoyer `If-None-Match` / `If-Modified-Since`.

Les validators ne sont pas conservés comme baseline si aucune représentation durable n’existe.

## 11. Scheduling

Les sources d’une nouvelle Observation sont :

- nouveau handoff explicite ;
- retry arrivé à échéance ;
- watch arrivé à échéance.

Priorité :

~~~text
handoff explicite
    > retry/watch autonome
~~~

Le watch autonome n’a aucune cadence de production par défaut. Il n’existe que si `watch_interval_seconds` est fourni explicitement.

Un handoff explicite nouveau efface les timers autonomes devenus secondaires pour cette série au moment du claim.

## 12. Crash et recovery

Une Observation ouverte appartient à un worker via :

- claim token ;
- worker id ;
- lease expiration.

Si la lease expire, le recovery :

1. finalise les Attempts ouverts en `INTERRUPTED` ;
2. finalise l’Observation en échec technique ;
3. programme le retry de recovery ;
4. rend l’ancien claim inutilisable.

L’identité d’une Observation n’est donc pas simplement la durée de vie d’un process.

## 13. Sorties

### Vers Prospecteur

`ObservationReport` reste structure-only :

- handoff / target / generation ;
- observation_ref ;
- status ;
- dates ;
- locator demandé/final ;
- statut HTTP ;
- media type ;
- références structurelles lorsqu’elles existent ;
- failure/retry ;
- métriques techniques bornées.

Aucun corps de page ni fait métier n’est transmis dans ce contrat.

La construction et la soumission du rapport sont séparées. L’ack Observer n’est écrit qu’après succès du sink. Un replay après crash reste donc possible et le sink aval doit conserver son propre contrat d’idempotence.

### Vers Interpréteur

`ObservationMaterial` expose les descriptors d’artefacts ou les références revalidées, sans exposer le chemin physique de stockage.

Le Lot 3 ne choisit pas encore la stratégie d’interprétation.

## 14. Activation opérationnelle

L’acquisition HTTP live est **opt-in**.

Sans activation explicite, `observer_worker` garde le comportement control-plane du Lot 2.

Pour autoriser Internet il faut notamment :

- `--enable-http-acquisition` ;
- une identité `--http-user-agent` explicite ;
- la queue réellement configurée dans l’environnement.

Aucune queue, URL opérateur, hostname de production ou credential n’est codé dans le dépôt.

Le kill switch Operations `observer` est vérifié avant l’ouverture de la queue puis avant chaque nouveau claim.

## 15. Tests de sortie du Lot 3

Le Lot 3 est fermé seulement si les tests couvrent au minimum :

- HTML/texte 200 ;
- 404 observé sans conclusion métier ;
- 304 avec baseline ;
- 304 sans baseline ;
- redirects et boucle ;
- downgrade HTTPS→HTTP ;
- DNS revalidé à chaque hop ;
- DNS public + privé ;
- localhost / private / link-local / metadata ;
- peer mismatch ;
- port non autorisé ;
- robots allow/disallow ;
- robots indisponible/unreachable ;
- destination de redirect régie par robots ;
- host lease et concurrence PostgreSQL ;
- crawl-delay ;
- 429 / Retry-After ;
- timeout réseau ;
- deadline totale ;
- corps trop grand ;
- gzip bomb ;
- encodage non supporté ;
- absence Authorization/Cookie ;
- artefact privé ;
- validators persistés ;
- revalidation sans copie d’artefact ;
- failure terminal sans retry artificiel ;
- kill switch ;
- activation live explicitement opt-in ;
- rapport Prospecteur structure-only.

Les tests HTTP utilisent des transports/résolveurs factices. La CI ne dépend pas d’Internet.

## 16. Lot 4 — Browser public / rendu JavaScript contrôlé

Le Lot 4 ajoute une seconde stratégie d’acquisition, `browser_render`, sans modifier les frontières canoniques de l’Observateur.

Il répond au cas suivant :

~~~text
ressource web publique connue
        ↓
le HTML brut seul n’est pas une représentation suffisante
        ↓
exécuter le JavaScript dans un navigateur isolé
        ↓
capturer la représentation technique rendue
~~~

Le Lot 4 ne décide pas automatiquement qu’une page « a besoin » d’un navigateur. Il fournit seulement une stratégie Browser explicite. La politique d’escalade HTTP → Browser appartient à un lot ultérieur, afin que ses critères soient mesurables et qu’un même Attempt ne mélange pas artificiellement deux stratégies.

### 16.1 Profil d’observation séparé

Le Browser est une série comparable distincte du HTTP direct :

~~~text
public-http
public-browser
~~~

Le fingerprint `public-browser` inclut notamment :

- engine Chromium ;
- version Playwright ;
- locale ;
- viewport ;
- ressources volontairement bloquées ;
- timeout de settle ;
- budgets requêtes/octets/DOM ;
- fingerprint du profil HTTP sous-jacent.

Une observation HTTP et une observation Browser de la même URL ne sont donc jamais déclarées comparables par simple égalité de locator.

### 16.2 Chromium exécute JavaScript, il ne possède pas le réseau

Invariant du Lot 4 :

> **Chromium n’est jamais le client réseau externe de Makolo.**

Chaque requête HTTP(S) du contexte Browser est interceptée avant sortie réseau puis servie via le gateway HTTP sûr du Lot 3.

~~~text
JavaScript / DOM
      ↓ demande HTTP(S)
BrowserContext.route
      ↓
SafeHttpResourceSession
      ↓
robots + politeness + DNS + IP pinning + ports + limites
      ↓
réponse technique
      ↓
route.fulfill
      ↓
Chromium
~~~

Ainsi, chaque sous-ressource et chaque destination de redirect repasse par les contrôles runtime SSRF/DNS de l’Observateur.

Le navigateur est lancé avec un proxy sink loopback comme seconde ligne de défense : tout trafic non couvert par les routes Observer doit échouer au lieu de sortir directement.

### 16.3 Capacités réseau volontairement bloquées

Le profil Browser public interdit :

- méthodes HTTP autres que GET ;
- cookies ou Authorization sortants ;
- propagation de Referer privé ;
- `Set-Cookie` depuis une réponse externe ;
- Service Workers ;
- WebSocket ;
- WebRTC ;
- WebTransport ;
- `sendBeacon` ;
- popups `window.open` ;
- downloads ;
- redirects vers protocoles non HTTP(S) ;
- downgrade HTTPS → HTTP sauf activation explicite de la même politique Lot 3.

Les ressources `image`, `media` et `font` sont bloquées par défaut pour réduire coût, fingerprinting et trafic sans empêcher le rendu structurel principal. Cette liste appartient au profil et donc au fingerprint.

Le contexte Browser est non persistant. Il n’est pas une session utilisateur Makolo.

### 16.4 Budgets

Le Lot 4 borne :

- nombre de requêtes Browser routées ;
- volume réseau cumulé ;
- volume décodé cumulé ;
- taille maximale du DOM rendu ;
- durée totale héritée de l’Observation HTTP ;
- timeout court d’attente après `DOMContentLoaded`.

Le runtime n’utilise pas `networkidle` comme preuve de fin : une page peut maintenir indéfiniment des connexions, timers ou requêtes. Le DOM est capturé après un settle borné.

### 16.5 Artefacts

Une Observation Browser peut produire deux artefacts distincts :

~~~text
browser_main_response_body
  origin = CAPTURED

rendered_dom
  origin = RENDERED
~~~

Le DOM rendu n’est pas modélisé comme simple transformation du HTML initial : son état peut dépendre de scripts et autres réponses routées pendant l’Attempt Browser.

Le `rendered_dom` peut être :

- `COMPLETE` si le rendu borné s’est achevé sans ressource bloquée/échouée pertinente ;
- `INCOMPLETE` lorsque le rendu demeure exploitable mais une ressource attendue hors exclusions explicites du profil a échoué ou a été refusée ;
- `TRUNCATED` si la taille maximale de capture DOM est atteinte.

Aucun de ces statuts n’est une conclusion sémantique sur la page.

### 16.6 Persistance

Le Lot 4 n’ajoute aucun modèle métier ni migration.

Il réutilise :

- `ObservationSeries` avec un fingerprint Browser distinct ;
- `Observation` ;
- `ObservationAttempt(strategy=browser_render)` ;
- `ObservedArtifact(origin=rendered)`.

Cela respecte la règle : une stratégie technique supplémentaire ne doit pas dupliquer une vérité métier.

### 16.7 Activation

Le profil Browser est **opt-in** et exclusif du profil HTTP direct dans un process `observer_worker`.

~~~text
control-plane
OU public-http
OU public-browser
~~~

Le déploiement d’un nouveau SHA ne lance jamais Chromium implicitement.

En l’absence de politique d’escalade dans ce lot, un worker `public-browser` traite les handoffs éligibles comme une **série Browser autonome**. Il ne doit pas être compris comme un fallback automatique du worker HTTP. Exécuter simultanément les deux profils sur la même population produit volontairement deux observations techniques distinctes.

L’environnement Browser doit disposer du package Playwright Python et du binaire Chromium compatible. La CI Observer installe explicitement Chromium et exécute un test d’intégration avec des réponses en mémoire : aucun accès Internet réel n’est requis par les tests.

### 16.8 Tests de sortie du Lot 4

Le Lot 4 est fermé seulement si les tests couvrent au minimum :

- JavaScript inline exécuté et DOM modifié ;
- script externe servi via le gateway Observer ;
- aucune sortie réseau Browser directe ;
- Service Worker bloqué ;
- WebSocket/WebRTC/WebTransport bloqués ;
- méthodes non GET bloquées ;
- cookies/Authorization/Referer non propagés ;
- redirect one-hop puis revalidation au hop suivant ;
- downgrade HTTPS → HTTP refusé ;
- budget nombre de requêtes ;
- budgets wire/décodés cumulés ;
- deadline totale ;
- DOM COMPLETE / INCOMPLETE / TRUNCATED ;
- raw main response et DOM rendu distincts ;
- profil Browser distinct et versionné ;
- worker Browser opt-in ;
- modes HTTP/Browser mutuellement exclusifs ;
- kill switch toujours respecté ;
- tests Chromium sans Internet externe.

## 17. Lot 5 — profil public adaptive HTTP → Browser

Le Lot 5 n'ajoute ni une nouvelle source de vérité ni un nouvel acteur. Il
compose les stratégies techniques déjà auditées des Lots 3 et 4 afin d'éviter
de rendre systématiquement toutes les pages dans Chromium.

### 17.1 Principe

Le profil `public-adaptive` suit une séquence bornée :

~~~text
Observation adaptive
  ↓
Attempt 1 — direct_http
  ↓
résultat HTTP
  ├─ contenu statique / non HTML / échec → fin
  └─ HTML avec signal d'exécution JS
         ↓
       Attempt 2 — browser_render
         ↓
       fin
~~~

Le Browser n'est donc ni un fallback générique sur toute erreur HTTP, ni un
crawler autonome. Une erreur réseau, un 429, un 5xx ou une violation de
sécurité HTTP reste un résultat technique de l'Attempt HTTP et ne déclenche
pas Chromium.

### 17.2 Signal d'escalade

La décision d'escalade est volontairement **technique et déterministe**.

Le Lot 5 inspecte seulement un préfixe HTML borné et recherche une balise
`script` exécutable. Sont notamment exclus du signal :

- JSON-LD ;
- JSON de données ;
- import maps ;
- speculation rules ;
- réponses non HTML ;
- réponses HTTP non 2xx ;
- contenu absent ou échec d'acquisition.

Le seuil de lecture du préfixe appartient à la policy et à son fingerprint.
Aucun mot-clé métier, score de pertinence, LLM ou compréhension du texte ne
participe à la décision.

Cette règle est volontairement conservative : elle peut laisser une page
techniquement dynamique en HTTP-only si aucun signal n'apparaît dans le
préfixe inspecté. Une future amélioration devra rester mesurable et versionnée
au lieu d'introduire une heuristique opaque.

### 17.3 Provenance multi-Attempt

HTTP et Browser sont deux opérations techniques distinctes. Le Lot 5 ne les
fusionne jamais dans un faux Attempt « adaptive ».

Lorsqu'une escalade a lieu :

~~~text
Observation
  Attempt 1
    strategy = direct_http
    └─ artefact HTTP éventuel

  Attempt 2
    strategy = browser_render
    └─ artefacts Browser éventuels
~~~

Chaque Attempt est finalisé et persisté avant le suivant. Ainsi :

- un Browser réussi n'efface pas la représentation HTTP réellement obtenue ;
- un Browser échoué laisse l'Attempt HTTP réussi dans l'historique ;
- chaque artefact conserve son `producing_attempt_ref` ;
- l'outcome final de l'Observation décrit le dernier résultat nécessaire à
  l'épisode, sans réécrire ses étapes antérieures.

Le runtime supporte un plan d'acquisition borné ; le profil Lot 5 utilise au
maximum deux Attempts.

### 17.4 Profil comparable

Le profil adaptive est distinct de `public-http` et `public-browser`.

Son fingerprint inclut notamment :

- fingerprint du profil HTTP ;
- fingerprint du profil Browser ;
- version de la règle d'escalade ;
- nombre maximal d'octets HTML inspectés.

Une série adaptive n'est donc jamais confondue avec une série HTTP ou Browser
pure.

### 17.5 Revalidation HTTP

Le probe HTTP adaptive n'utilise pas une réponse conditionnelle 304 comme
preuve que le rendu Browser serait inchangé.

Un shell HTML peut rester identique alors que les scripts ou APIs consommés
pendant le rendu ont changé. Le premier Attempt adaptive part donc sans
validators conditionnels de série. Les profils HTTP directs conservent leur
mécanisme ETag/Last-Modified du Lot 3.

### 17.6 Deadline et lease

Chaque stratégie reste soumise à sa propre deadline technique, mais aucune
étape ne peut dépasser la `leased_until` de l'Observation.

~~~text
deadline effective
  = min(deadline stratégie, lease Observation)
~~~

L'escalade Browser ne crée donc jamais un droit implicite à prolonger
indéfiniment l'épisode déjà claimé.

### 17.7 Activation

Le mode adaptive est explicitement opt-in :

~~~bash
python manage.py observer_worker \
  --queue-name <QUEUE_NAME> \
  --enable-adaptive-acquisition \
  --http-user-agent "MakoloObserver/1.0 (<CONTACT_OPS>)"
~~~

Les modes suivants sont mutuellement exclusifs dans un même process :

- `--enable-http-acquisition` ;
- `--enable-browser-acquisition` ;
- `--enable-adaptive-acquisition`.

Sans l'un de ces flags, le worker reste control-plane.

L'option `--adaptive-html-probe-bytes` versionne la borne du probe HTML.
Ses valeurs par défaut sont des garde-fous techniques, pas une politique de
production immuable.

### 17.8 Critères de sortie du Lot 5

Le Lot 5 est fermé seulement si les tests prouvent au minimum :

- HTML statique → un seul Attempt HTTP ;
- script inline exécutable → HTTP puis Browser ;
- script externe exécutable → HTTP puis Browser ;
- JSON-LD/non-exécutable → pas d'escalade ;
- réponse JSON/non HTML → pas d'escalade ;
- échec/retry HTTP → pas d'escalade ;
- probe HTML borné ;
- au plus une escalade Browser ;
- HTTP et Browser persistés comme Attempts distincts ;
- artefacts reliés au bon Attempt ;
- échec Browser conservant la provenance HTTP ;
- retry final piloté par l'échec Browser ;
- profil/fingerprint adaptive distinct et versionné ;
- deadlines HTTP/Browser plafonnées par la lease ;
- worker adaptive opt-in et mutuellement exclusif des autres modes ;
- aucune migration métier ni accès privé ajouté.

## 18. Hors Lot 5

Restent hors du Lot 5 tant que leurs politiques ne sont pas définies
explicitement :

- extraction automatique de liens ou structures riches depuis les artefacts ;
- interprétation sémantique par l'Interpréteur ;
- credentials privés explicitement autorisés ;
- navigation authentifiée/session privée ;
- stratégie de rétention à grande échelle ;
- orchestration live du `ObservationReport` vers une
  `ExpansionPolicy` Prospecteur : le contrat existe, mais aucune valeur de
  budget/expansion de production ne doit être inventée ;
- orchestration aval complète vers l'Interpréteur.

Le profil adaptive reste un mécanisme **d'acquisition technique**. Il ne
devient ni un agent autonome, ni un scraper sémantique, ni un nouveau domaine
métier.
