# Makolo Web Search — cycle générique d’acquisition, approfondissement et maintien de connaissance

**Statut : cadrage d’architecture — proposition à instancier progressivement**  
**Base de réconciliation : main@32a3bd5c53356853be8c6e4c995042501fe6365a**  
**Périmètre : recherche Web, acquisition externe, approfondissement, provenance, fraîcheur et capitalisation de connaissance**  
**Hors périmètre : redesign UX, recommandation finale à l’utilisateur, nouvelle vérité métier parallèle, dépendance à un fournisseur IA particulier**

> Makolo Web Search est une capacité Makolo, pas un produit OpenAI, Anthropic ou d’un autre fournisseur.
>
> Les moteurs externes découvrent et comprennent. Makolo vérifie, résout, capitalise et transforme cette connaissance en matière exploitable par ses domaines et ses algorithmes d’action.

---

## 1. Pourquoi ce chantier existe

Makolo veut pouvoir travailler **avant** qu’un utilisateur pose une question.

La promesse « Makolo marche pour vous » suppose que le système puisse progressivement :

- découvrir ce qui existe dans le monde ;
- approfondir ce qui a été découvert ;
- savoir ce qu’il connaît et ce qu’il ne connaît pas ;
- conserver la provenance et le temps de connaissance ;
- détecter ce qui change ;
- éviter de refaire inutilement le même travail ;
- rendre les connaissances acquises réutilisables pour plusieurs Profiles, Espaces et contextes ;
- laisser ensuite les domaines et algorithmes Makolo calculer pertinence, préparation et action.

Le but n’est donc pas :

~~~text
Utilisateur
  → LLM
  → Web
  → réponse jetable
~~~

Le but est plutôt :

~~~text
Web
  → acquisition Makolo
  → connaissance structurée et sourcée
  → domaines canoniques / PostgreSQL
  → algorithmes Makolo
  → pertinence / préparation / action
  → utilisateur
~~~

La recherche externe sert principalement à **agrandir et maintenir le capital de connaissance de Makolo**.

---

## 2. Ce qui existe déjà dans Makolo

Ce chantier ne repart pas de zéro.

Le runtime et les contrats actuels possèdent déjà plusieurs briques utiles :

- ResearchMission exprime pourquoi Makolo cherche et quelle question reste ouverte ;
- huit familles de recherche sont déjà définies ;
- Actor 1 — Prospecteur cherche où regarder ;
- Actor 2 — Observateur acquiert de la matière technique ;
- Actor 3 — Interpréteur transforme la matière observée en candidats sémantiques ;
- Actor 4 — Résolveur rapproche les candidats des réalités déjà connues ;
- Actor 5 — Orchestrateur organise l’admission vers les propriétaires métier ;
- Actor 6 — Persistateur représente la persistance contrôlée par les domaines propriétaires ;
- Actor 7 — Projecteur intervient après les vérités canoniques et reste hors de la recherche Web elle-même ;
- le package intelligence fournit déjà une infrastructure provider-neutral avec gateway, registry, routage et capacités génériques ;
- le Prospecteur possède déjà des adapters autour d’index externes, dont Common Crawl ;
- Crawlee existe déjà comme mécanisme complémentaire dans les frontières Prospecteur / Observateur.

Références principales :

- docs/architecture/research-missions.md
- docs/architecture/prospector.md
- docs/architecture/interpreter.md
- docs/architecture/resolver.md
- docs/architecture/orchestrator.md
- docs/architecture/persistator.md
- docs/architecture/intelligence-discover-program.md
- docs/architecture/makolo-domain-blueprint.md

### État courant important

À la base de cette note, le runtime intelligence possède notamment les capacités suivantes :

~~~text
TEXT_GENERATE
STRUCTURED_GENERATE
EMBED
RERANK
~~~

Il ne possède pas encore de capacité générique explicite de Web Search.

Le provider OpenAI-compatible actuel couvre la génération, la génération structurée et les embeddings via des endpoints compatibles ; il ne constitue pas encore un moteur Makolo Web Search.

Cette note définit donc une **direction d’architecture**, pas une capacité déjà livrée.

---

## 3. Principe directeur

Le principe fondamental est :

~~~text
Makolo définit le besoin, le contrat, la preuve et l’admission.
Le moteur externe n’est qu’un moyen d’acquisition ou de compréhension.
~~~

Par conséquent :

~~~text
Makolo Web Search
        ↓
capacité / port Makolo
        ↓
routing provider-neutral
        ↓
OpenAI / Anthropic / autre moteur / API / crawler
~~~

Aucun domaine métier ne doit dépendre d’un type propre à un fournisseur.

Le fournisseur doit pouvoir être remplacé sans réécrire :

- ResearchMission ;
- les contrats de résultats ;
- la validation ;
- la résolution ;
- l’admission ;
- les domaines canoniques ;
- la persistance ;
- les algorithmes de pertinence.

---

## 4. Le canevas avant les instances

Makolo ne doit pas construire séparément un moteur de bourses, un moteur d’emplois, un moteur de transports, un moteur de formations et un moteur de stages.

Ces objets sont des **missions spécialisées** d’un même cycle générique.

Le chantier doit d’abord construire le squelette :

~~~text
Canevas générique Makolo
        ↓
ResearchMission
        ↓
stratégie d’acquisition
        ↓
découverte / approfondissement / surveillance
        ↓
candidats sourcés
        ↓
résolution / admission
        ↓
connaissance Makolo
~~~

Exemples d’instanciation :

~~~text
Mission : découvrir des bourses
Mission : découvrir des emplois
Mission : découvrir des transports
Mission : approfondir les conditions d’une possibilité déjà connue
Mission : vérifier si une deadline a changé
Mission : trouver la page officielle d’un acteur déjà identifié
~~~

Le métier reste contextuel, le moteur reste générique.

---

## 5. Huit familles de recherche et une dimension transverse

Les huit familles actuelles restent pertinentes comme **questions de recherche**.

| Famille | Question principale | Exemples |
| --- | --- | --- |
| POSSIBILITY | Qu’est-ce qui existe que l’on peut faire, vivre ou obtenir ? | bourse, emploi, stage, formation, transport, service, programme |
| REQUIREMENT | Qu’est-ce qui doit être vrai ou satisfait ? | âge, diplôme, langue, expérience, deadline, prérequis |
| QUALIFICATION | Qu’est-ce qui prouve, atteste ou matérialise une condition ? | diplôme, certificat, résultat, Proof, document requis |
| ACTOR | Qui fait quoi ? | université, entreprise, ONG, autorité, opérateur, organisme |
| SPATIOTEMPORAL | Où, quand et avec quelle disponibilité ? | lieu, date, session, durée, origine, destination, capacité |
| PROCEDURE | Comment agit-on concrètement ? | candidature, inscription, réservation, étapes, formulaire |
| ECONOMIC | Combien et selon quelles modalités ? | frais, prix, devise, financement, allocation, remboursement |
| REFERENCE | Quelle ressource ou règle permet de comprendre ou accomplir l’action ? | page officielle, règlement, PDF, FAQ, documentation |

Ces familles ne deviennent pas huit tables ni huit bounded contexts.

Une même source peut produire plusieurs familles à la fois.

### Evidence / provenance

Le chantier fait apparaître une dimension transverse supplémentaire :

~~~text
EVIDENCE / PROVENANCE
~~~

Elle ne constitue pas une neuvième famille métier au même niveau. Elle répond à :

> Pourquoi Makolo croit-il ce fait, d’où vient-il et quand a-t-il été observé ?

Un fait externe important doit pouvoir rester relié conceptuellement à :

~~~text
valeur
+ source
+ evidence / claim support
+ observed_at
+ contradiction éventuelle
~~~

---

## 6. Recherche globale et pertinence locale sont deux problèmes différents

Par défaut, l’acquisition Makolo ne doit pas être enfermée dans la géographie d’un utilisateur.

Makolo cherche à construire une connaissance réutilisable du monde :

~~~text
Web mondial
   ↓
connaissance commune Makolo
   ↓
domaines canoniques
   ↓
Profile / Espace / contexte
   ↓
pertinence personnelle ou collective
~~~

La géographie reste évidemment une propriété importante de ce qui est découvert.

Elle peut aussi être intrinsèque à une mission, par exemple « trouver les transports Lubumbashi → Kolwezi ».

Mais elle ne doit pas être injectée silencieusement depuis un Profile pour limiter toute acquisition.

Invariant :

~~~text
ACQUISITION
    = connaissance globale ou scope explicite de la mission

PERSONNALISATION
    = calcul Makolo ultérieur
~~~

Cette séparation améliore la réutilisation, le coût, la confidentialité, la reproductibilité et l’auditabilité.

---

## 7. Quatre modes d’un même cycle

Makolo Web Search doit être compris comme un **cycle de connaissance**, pas comme une simple requête moteur.

Les quatre modes principaux sont :

~~~text
DISCOVER
DEEPEN
WATCH
USE
~~~

### 7.1 Discover — découvrir

Question :

> Qu’est-ce qui existe que Makolo ne connaît pas encore ?

La découverte privilégie la largeur et l’identification de réalités candidates.

### 7.2 Deepen — approfondir

Question :

> Sur cette réalité déjà découverte, qu’est-ce qu’il reste à comprendre ?

Exemple :

~~~text
Scholarship A
  ├─ ACTOR ?
  ├─ REQUIREMENT ?
  ├─ QUALIFICATION ?
  ├─ deadline ?
  ├─ PROCEDURE ?
  ├─ ECONOMIC ?
  └─ REFERENCE officielle ?
~~~

Une découverte peut donc engendrer plusieurs nouvelles ResearchMissionCandidate.

### 7.3 Watch — surveiller

Question :

> Ce que Makolo connaît déjà a-t-il changé ?

Exemple :

~~~text
deadline connue
  ↓
réobservation ciblée
  ↓
identique
    → pas de réinterprétation coûteuse

ou

modifiée
    → nouvelle observation
    → interprétation
    → résolution temporelle
    → mise à jour canonique éventuelle
~~~

### 7.4 Use — utiliser

Ce mode n’est plus de l’acquisition.

Une fois la connaissance en Makolo, les algorithmes et domaines peuvent travailler sans rappeler systématiquement un moteur externe :

~~~text
Possibilité connue
+ Requirements
+ Profile / Proof / Credential
+ Geography
+ Access
+ Capacity
+ temps
        ↓
Readiness / pertinence / préparation
        ↓
action
~~~

---

## 8. Cycle générique de connaissance

Le workflow de référence devient :

~~~text
RESEARCH MISSION
      ↓
DISCOVERY
      ↓
ENRICHMENT / DEEPENING
      ↓
INTERPRETATION
      ↓
EVIDENCE / VERIFICATION
      ↓
RESOLUTION
      ↓
ADMISSION / ORCHESTRATION
      ↓
PERSISTENCE
      ↓
FRESHNESS / WATCH
      ↓
éventuellement nouvelle RESEARCH MISSION
~~~

Ce cycle est plus important que le nombre exact d’Actors.

Les Actors sont des responsabilités exécutables. Le cycle décrit le problème complet.

---

## 9. Search, recherche approfondie et Crawl ne sont pas la même chose

Makolo doit pouvoir combiner plusieurs stratégies.

### Web Search

Question :

> Qu’est-ce qui existe et quelles sources semblent répondre à la mission ?

Usage typique : découverte large, recherche de nouvelles réalités, nouvelles sources et exploration de thèmes encore peu connus.

### Recherche approfondie / agentique

Question :

> Pour ce candidat, quelles sources permettent de répondre à plusieurs inconnues ?

Usage typique : ouvrir plusieurs résultats, reformuler la recherche, chercher une page officielle, compléter Requirement, Procedure, Economic et Reference, puis recouper plusieurs sources.

### Web Crawl

Question :

> Cette source ou ce territoire étant déjà connu, comment l’explorer et le maintenir systématiquement ?

Usage typique : parcourir un catalogue ou un site structurant, suivre les nouvelles pages, maintenir une frontier, revisiter selon une policy et détecter des changements.

Résumé :

~~~text
SEARCH
= agrandir le territoire connu

CRAWL
= explorer et entretenir méthodiquement un territoire connu

WATCH
= vérifier ce qui a changé dans la connaissance déjà acquise
~~~

Makolo peut donc utiliser Search pour découvrir un portail important, puis Crawl/Watch pour entretenir ce portail.

---

## 10. Une mission ne promet pas « tout Internet »

Le scope d’acquisition peut être mondial sans promettre une exhaustivité mathématique impossible.

Il faut distinguer :

~~~text
scope ouvert
≠
exécution infinie
~~~

Une mission peut chercher le plus largement possible tout en imposant des limites d’exécution :

~~~text
max_queries
max_candidates
max_sources
max_depth
max_elapsed_time
max_cost
~~~

Le résultat doit pouvoir signaler pourquoi l’exécution s’est arrêtée : saturation apparente, budget épuisé, absence de nouveaux candidats, limite provider, deadline d’exécution ou résultat partiel.

Makolo ne doit jamais transformer « aucun autre résultat trouvé dans cette exécution » en « il n’existe aucun autre résultat sur le Web ».

---

## 11. Découverte et approfondissement doivent rester séparables

Une recherche efficace ne doit pas exiger que chaque candidat soit entièrement enrichi dès sa découverte.

Exemple :

~~~text
DISCOVERY
  ↓
100 candidats légers
  ↓
déduplication / sélection
  ↓
DEEPEN
  ↓
20 candidats approfondis
  ↓
5 inconnues critiques
  ↓
recherches ciblées supplémentaires
~~~

Cette séparation permet moins de coût, moins de duplication, plus de contrôle et une profondeur proportionnée à la valeur du candidat.

---

## 12. Source de découverte et source de vérification

Une source secondaire peut être excellente pour découvrir une réalité sans être suffisante pour établir un fait critique.

Exemple :

~~~text
agrégateur
   ↓
découvre Scholarship X
   ↓
site officiel Scholarship X
   ↓
deadline / conditions / procédure
~~~

Politique générale :

~~~text
DISCOVERY
→ source raisonnablement exploitable

VERIFICATION
→ propriétaire / officiel de préférence
→ partenaire officiel
→ institution reconnue
→ source secondaire fiable
→ agrégateur
~~~

Cette hiérarchie ne doit pas devenir un score universel rigide. Le domaine, le fait et le risque peuvent nécessiter des policies différentes.

---

## 13. Provenance au niveau du fait

Une fiche peut combiner plusieurs sources.

Il ne suffit donc pas toujours de mettre une seule URL sur l’objet entier.

Conceptuellement :

~~~text
Candidate

title
  value = Scholarship X
  evidence = source A

deadline
  value = 2027-01-15
  evidence = source B

requirement
  value = bachelor_degree
  evidence = source A

funding
  value = full
  evidence = source C
~~~

Makolo doit pouvoir savoir quelle source soutient quel fait important.

Cela ne signifie pas qu’il faut stocker arbitrairement le texte complet de chaque page. La collecte et la conservation d’evidence doivent respecter minimisation, sécurité, volume, confidentialité et besoins réels de replay/audit.

---

## 14. États épistémiques

Le système doit protéger explicitement contre l’invention.

Un fait candidat peut être :

~~~text
OBSERVED
UNKNOWN
CONFLICTING
NOT_APPLICABLE
~~~

Une possibilité peut posséder un état temporel distinct :

~~~text
OPEN
UPCOMING
CLOSED
UNKNOWN
~~~

Invariant :

~~~text
UNKNOWN != FALSE
UNKNOWN != CLOSED
UNKNOWN != NO_LIMIT
UNKNOWN != NOT_APPLICABLE
~~~

Par exemple, « aucune limite d’âge trouvée » doit rester age_requirement = UNKNOWN et ne pas devenir automatiquement « aucune limite ».

Le moteur externe peut interpréter une formulation observée, mais il ne doit pas combler silencieusement les absences.

---

## 15. Temps de connaissance et historique

Les données Web changent.

Makolo doit distinguer au minimum le fait ou état actuel admis, l’historique des observations et le moment où Makolo a observé chaque information.

Exemple :

~~~text
Observation t1
deadline = 15 janvier
observed_at = 28 septembre

Observation t2
deadline = 31 janvier
observed_at = 20 novembre
~~~

Le système ne doit ni effacer silencieusement t1, ni traiter t1 et t2 comme deux deadlines actuelles.

Il faut conceptuellement :

~~~text
historique des observations
          ↓
résolution temporelle
          ↓
état actuel canonique
~~~

Une observation nouvelle peut changer ce que Makolo sait sans signifier que toute l’histoire précédente doit disparaître.

---

## 16. Freshness et change detection

Au début, une base presque vide nécessitera beaucoup de découverte.

À maturité, la stratégie doit évoluer :

~~~text
DÉBUT
→ beaucoup découvrir
→ beaucoup approfondir

CROISSANCE
→ chercher surtout le nouveau
→ combler les inconnues

MATURITÉ
→ surveiller beaucoup
→ réinterpréter surtout ce qui change
→ continuer la prospection de nouveaux territoires
~~~

Une optimisation importante consiste à détecter les changements avant de lancer des opérations coûteuses.

Exemple :

~~~text
ancienne représentation hash = ABC123
nouvelle représentation hash = ABC123

→ NOT_MODIFIED
→ pas de réinterprétation
→ mise à jour du contrôle de fraîcheur
~~~

Si ABC123 devient DEF987, une nouvelle observation peut être interprétée, comparée et éventuellement admise comme nouvel état.

Le runtime Prospecteur/Observateur possède déjà des notions telles que réobservation, génération de handoff et NOT_MODIFIED qui devront être réutilisées plutôt que recréées.

---

## 17. Le Prospecteur garde une raison d’être

Makolo Web Search ne remplace pas automatiquement Actor 1.

Le rôle du Prospecteur peut être compris comme :

> déterminer où chercher et ce qui mérite une acquisition parce que Makolo ne le connaît pas encore, ou parce que sa connaissance doit être réévaluée.

Le nouveau système peut lui fournir de nouvelles stratégies :

~~~text
Prospecteur
   ↓
ExternalIndex
Web Search engine
Search API
Common Crawl
sitemaps
feeds
autres sources
~~~

Le Prospecteur ne devient pas un LLM et ne conclut toujours pas la vérité métier.

---

## 18. Les Actors 1–7 restent des responsabilités, pas un dogme de trajet

Il ne faut ni supprimer les Actors pour adopter un moteur moderne, ni forcer chaque résultat externe à traverser artificiellement un chemin qui ne correspond plus à la méthode d’acquisition.

| Responsabilité du cycle | Existant Makolo / direction |
| --- | --- |
| besoin de connaissance | ResearchMission |
| découverte / prospection | Actor 1 + nouvelles sources Search |
| acquisition approfondie | Actor 2 + HTTP / browser / crawl / API selon stratégie |
| compréhension / extraction | Actor 3 ou sortie structurée compatible, avec provenance explicite |
| evidence / vérification | responsabilité transverse à consolider |
| rapprochement / déduplication | Actor 4 |
| admission / orchestration | Actor 5 |
| persistance par propriétaires | Actor 6 |
| fraîcheur / réexamen | cycle à consolider autour des missions et de l’observation |
| projection Univers | Actor 7 après le canonique, hors recherche Web |

La règle n’est donc pas que tout doit obligatoirement traverser Actor 1 → 2 → 3 → 4 → 5 → 6.

La règle est :

> toute acquisition doit préserver les responsabilités nécessaires : provenance, compréhension candidate, résolution, admission et propriété canonique.

Un moteur capable de retourner directement des candidats structurés peut réduire certaines étapes techniques, mais il ne reçoit pas pour autant l’autorité de créer des vérités métier.

---

## 19. Trois couches d’intelligence

### A. Intelligence d’acquisition

Question : qu’est-ce qui existe dans le monde ?

Moyens possibles : Web Search, recherche approfondie, crawler, HTTP, browser, API externes, documents/PDF, index externes et LLM pour compréhension ciblée.

### B. Intelligence de connaissance

Question : qu’est-ce que Makolo sait réellement ?

Elle porte notamment identité, déduplication, provenance, contradiction, état courant, historique, inconnu, fraîcheur et relations.

### C. Intelligence d’action

Question : qu’est-ce qui compte maintenant dans ce contexte et que peut-on préparer ?

Elle s’appuie sur les domaines Makolo : Profile, Geography, Requirements, Readiness, Journey, Access, Capacity, Dossier, temps et autres domaines propriétaires.

Les moteurs externes participent surtout à A et parfois à l’interprétation utile à B.

Le différenciateur produit de Makolo reste principalement C, rendu possible par A et fiabilisé par B.

---

## 20. Provider-neutral

Le contrat doit être indépendant de tout fournisseur.

Conceptuellement :

~~~text
WebResearchEnginePort
        ↓
provider registry / routing
        ↓
engine A / engine B / engine C
~~~

OpenAI, Anthropic ou un autre fournisseur ne sont que des engines possibles.

Un moteur peut fournir certaines capacités et pas d’autres. Les noms définitifs des capacités doivent être choisis après audit du runtime intelligence. Cette note ne déclare pas qu’une capacité WEB_SEARCH existe déjà.

Le routage futur pourra tenir compte de capacité, coût, disponibilité, quota, politique, qualité observée, scope autorisé et fallback.

Aucune règle métier ne doit être codée dans le provider.

---

## 21. Canevas générique d’une mission

Sans imposer immédiatement un nouveau modèle persistant, le canevas doit pouvoir exprimer conceptuellement :

~~~text
Mission
  subject
  questions
  known_context
  unknowns
  origins
  scope
  limits

Research policy
  discovery strategy
  enrichment strategy
  evidence policy
  identity policy
  freshness policy
  change policy
  stop / budget policy
~~~

ResearchMission existant porte déjà une partie importante de ce canevas.

Une persistance dédiée ne doit être ajoutée que si le runtime a réellement besoin de posséder un lifecycle durable de mission, scheduling, admission ou surveillance avant la prospection.

---

## 22. Exemple — bourses

Mission :

~~~text
subject:
  découvrir les bourses de Master en génie mécanique

primary_family:
  POSSIBILITY

questions:
  quelles possibilités existent ?
  qui les propose ?
  quelles conditions ?
  quelles dates ?
  quelles procédures ?
  quels financements ?
  quelles références officielles ?
~~~

Après Discovery, une possibilité peut être connue ainsi :

~~~text
ACTOR              connu
SPATIOTEMPORAL     connu
REQUIREMENT        partiel
QUALIFICATION      inconnu
PROCEDURE          inconnu
ECONOMIC           connu
REFERENCE          connu
~~~

Le système peut alors produire deux nouveaux besoins ciblés : approfondir QUALIFICATION et approfondir PROCEDURE.

Les sorties ne deviennent pas automatiquement un objet générique Scholarship si le modèle canonique Makolo exprime déjà ces réalités par composition.

---

## 23. Exemple — transport

Le même canevas sert à une mission différente :

~~~text
subject:
  découvrir des possibilités de transport interurbain

families utiles:
  POSSIBILITY
  ACTOR
  SPATIOTEMPORAL
  PROCEDURE
  ECONOMIC
  REFERENCE
~~~

Le moteur change de mission, pas d’architecture.

Une géographie telle que Lubumbashi → Kolwezi peut ici être intrinsèque au problème et appartient alors au scope explicite de la mission.

---

## 24. Anti-features

Makolo Web Search ne doit pas devenir :

- un clone de ChatGPT ;
- une réponse LLM jetable par requête utilisateur ;
- un système dépendant d’OpenAI ;
- une table universelle AIResult servant de seconde vérité métier ;
- un LLM qui écrit directement dans les modèles canoniques ;
- un nouveau modèle métier pour chaque type de recherche ;
- une multiplication de crawlers verticaux sans besoin démontré ;
- une recommandation qui mélange acquisition et personnalisation ;
- une machine à inférer silencieusement les champs absents ;
- un crawler infini sans budget, policy ou respect des frontières de collecte ;
- une copie de texte Web sans nécessité ;
- une suppression de l’historique simplement parce qu’un fait a changé.

---

## 25. Sécurité et confidentialité

Par défaut :

- une mission d’acquisition ne reçoit pas de données privées de Profile si elles ne sont pas nécessaires ;
- la personnalisation se fait après acquisition dès que possible ;
- les secrets providers restent dans l’infrastructure intelligence ;
- aucune clé ou credential ne remonte dans les contrats de recherche ;
- les contenus privés ou restreints ne sont pas collectés sans droit explicite ;
- la conservation d’evidence applique la divulgation minimale ;
- les logs n’enregistrent pas de contenu sensible inutile ;
- la provenance technique ne devient pas une exposition publique automatique.

---

## 26. Première verticale minimale

Une première implémentation ne doit pas essayer de couvrir tout le cycle mature.

Un vertical minimal crédible :

~~~text
ResearchMission
  → Web Search provider-neutral
  → candidats structurés et sourcés
  → validation déterministe
  → résolution / déduplication
  → admission vers propriétaires
  → persistance canonique
~~~

Critères minimaux :

1. aucun contrat métier ne dépend du nom d’un provider ;
2. une mission peut produire plusieurs candidats sourcés ;
3. les faits importants conservent une provenance exploitable ;
4. absence d’information reste UNKNOWN ;
5. le moteur ne crée pas directement de vérité canonique ;
6. les doublons possibles passent par la résolution appropriée ;
7. un résultat déjà connu peut être reconnu ;
8. une exécution possède des limites explicites ;
9. le système distingue discovery et deepen ;
10. les tests couvrent provider indisponible, sortie invalide, données contradictoires et replay.

---

## 27. Séquence de mise en œuvre recommandée

### Phase 1 — figer le contrat

Stabiliser ce document, auditer précisément ResearchMission, Prospecteur, Observer, Interpréteur, Résolveur et intelligence, choisir les ports/capacités sans doublonner les contrats existants et définir le minimum de provenance nécessaire.

### Phase 2 — premier engine Web Search

Étendre l’infrastructure provider-neutral, implémenter un premier adapter moteur, produire une sortie structurée validée et interdire toute écriture métier directe.

### Phase 3 — discovery générique

Exécuter une mission POSSIBILITY, produire des candidats, reconnaître les candidats déjà connus et mesurer couverture, coût et qualité.

### Phase 4 — deepen

Générer des recherches secondaires depuis les inconnues, compléter les familles manquantes et renforcer la préférence pour les sources officielles lorsque nécessaire.

### Phase 5 — watch / freshness

Définir les policies de réobservation, réutiliser NOT_MODIFIED, fingerprints/hashes et générations existantes, éviter les appels d’interprétation lorsqu’aucun changement n’est observé et conserver l’historique de connaissance.

### Phase 6 — consommation produit

Laisser Discover, Home, Readiness, Journey et les autres surfaces consommer les vérités canoniques. Le provider d’acquisition n’est jamais présenté comme propriétaire de la vérité.

---

## 28. Relation avec la promesse Makolo

Le Web possède beaucoup d’informations.

Les moteurs modernes peuvent en retrouver et en comprendre une partie lorsqu’ils reçoivent une mission précise.

Makolo doit transformer cette capacité ponctuelle en un système durable :

~~~text
ACQUÉRIR
  → DÉCOUVRIR
  → APPROFONDIR
  → PROUVER
  → RÉSOUDRE
  → CAPITALISER
  → SURVEILLER
  → UTILISER
  → PRÉPARER
  → AGIR
~~~

La valeur de Makolo n’est pas de reproduire un moteur de recherche général ni un LLM.

Sa valeur est de **construire progressivement une représentation exploitable du monde de l’action**, de savoir ce qui est connu, inconnu ou changé, puis d’utiliser cette connaissance pour préparer ce qui compte réellement pour les personnes et les Espaces.

---

## 29. Décisions retenues dans ce cadrage

### RETENU

- Makolo Web Search est provider-neutral.
- ResearchMission reste le point de départ conceptuel du besoin de connaissance.
- Les huit familles actuelles restent des axes de recherche.
- Evidence/Provenance est transverse.
- Acquisition globale et personnalisation sont séparées.
- Discovery, Deepen, Watch et Use sont quatre modes distincts.
- Search et Crawl sont complémentaires.
- Les observations doivent pouvoir être temporelles et historisées.
- L’absence d’information reste inconnue.
- Les domaines canoniques restent propriétaires de leurs vérités.
- Les Actors existants sont réutilisés selon leurs responsabilités, pas comme un trajet obligatoire artificiel.

### OUVERT

- nom exact du port de Web Search ;
- capacité exacte à ajouter à intelligence ;
- format minimal de résultat de recherche sourcée ;
- emplacement précis de la provenance au niveau du fait ;
- besoin ou non d’une persistance durable de missions ;
- scheduler et policies de freshness ;
- frontière exacte entre sortie structurée d’un moteur Web et Actor 3 ;
- stratégie de résolution temporelle des observations contradictoires ;
- critères d’automatisation de l’admission par type de fait.

### REJETÉ

- dépendance métier directe à OpenAI, Anthropic ou un modèle particulier ;
- vérité canonique écrite par le moteur externe ;
- recherche personnalisée par données privées sans nécessité ;
- multiplication de pipelines verticaux indépendants ;
- suppression des Actors uniquement parce qu’un moteur externe est puissant ;
- conservation aveugle de réponses LLM comme base métier.

---

## 30. Formule de référence

> **Makolo Web Search est le cycle provider-neutral par lequel Makolo transforme des besoins de connaissance bornés en découvertes et faits candidats sourcés, les approfondit lorsque nécessaire, surveille ce qui est déjà connu, puis laisse les domaines canoniques et les algorithmes Makolo transformer cette connaissance en préparation et action.**

~~~text
Web mondial
    ↓
ResearchMission
    ↓
Prospection / Search
    ↓
Discovery
    ↓
Deepen / Acquire / Observe
    ↓
Interpret
    ↓
Evidence
    ↓
Resolve
    ↓
Admit
    ↓
Persist
    ↓
Watch / Freshness
    ↓
Knowledge Makolo
    ↓
algorithmes Makolo
    ↓
pertinence / préparation / action
~~~
