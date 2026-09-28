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


---

## 31. Phase 1 runtime — contrat provider-neutral minimal

**Statut : implémenté sur le chantier Phase 1, sans migration ni provider réel.**

L’audit du runtime a confirmé que Web Research ne doit ni dupliquer ResearchMission, ni se faire passer pour une Observation Actor 2, ni introduire un second registry de providers.

Le contrat minimal est donc isolé dans :

~~~text
web_research/
  contracts.py
  ports.py
~~~

Il porte quatre éléments principaux :

- WebResearchRequest : une exécution bornée adossée à une ResearchMission existante ;
- WebResearchSource : une source Web citée par le moteur, explicitement distincte d’un artefact Observer ;
- WebResearchCandidate : une réalité candidate légère, obligatoirement reliée à au moins une source du résultat ;
- WebResearchResult : le résultat provider-neutral, daté, borné et accompagné d’une raison d’arrêt.

Le port d’exécution est :

~~~text
WebResearchEnginePort
  execute(WebResearchRequest) -> WebResearchResult
~~~

### 31.1 Modes exécutables

Phase 1 formalise :

~~~text
DISCOVER
DEEPEN
WATCH
~~~

USE reste hors de ce port : l’utilisation de la connaissance canonique appartient aux domaines et algorithmes Makolo, pas au moteur d’acquisition.

### 31.2 Bornage et raisons d’arrêt

Un résultat distingue notamment :

~~~text
completed
partial
no_results
failed
~~~

et conserve une raison d’arrêt provider-neutral :

~~~text
completed
coverage_saturated
budget_exhausted
no_new_candidates
provider_limit
deadline_reached
failed
~~~

Ainsi no_results ou no_new_candidates ne signifie jamais que rien d’autre n’existe sur le Web.

### 31.3 Frontière avec Actor 2 et Actor 3

WebResearchSource ne possède volontairement aucun :

~~~text
artifact_ref
artifact_observation_ref
ObservationMaterial
~~~

Une citation produite par un moteur Web Search ne doit pas être maquillée en artefact acquis par l’Observateur.

De même, WebResearchCandidate reste volontairement plus léger que les CandidateEntity / CandidateFact / CandidateRelation / CandidateConstraint de l’Interpréteur.

Phase 1 ne décide pas encore si une recherche approfondie :

1. produit seulement des sources à faire observer par Actor 2 ;
2. produit aussi des faits candidats sourcés via un contrat spécifique ;
3. combine les deux selon le niveau de preuve demandé.

Cette couture reste à fermer avant l’admission de faits détaillés.

### 31.4 Provider metadata

WebResearchResult peut conserver des métadonnées techniques non métier telles que provider_key ou model pour la télémétrie et l’audit d’exécution.

Le contrat rejette explicitement les clés sensibles usuelles telles que :

~~~text
api_key
token
secret
credential
password
authorization
~~~

Les credentials continuent d’appartenir exclusivement à l’infrastructure intelligence.

### 31.5 Ce que Phase 1 n’ajoute pas

Aucun changement n’est apporté à :

- IntelligenceCapability ;
- ProviderProtocol ;
- OpenAICompatibleProvider ;
- ProviderConnection / IntelligenceRoute ;
- ProspectingMission ;
- ObservationMaterial ;
- InterpretedMaterial ;
- Resolver ;
- Orchestrator ;
- modèles Django ;
- migrations.

La Phase 2 pourra donc brancher ce contrat sur intelligence sans déplacer les frontières canoniques.


---

## 32. Phase 2 runtime — IntelligenceGateway et premier adapter Web Search

**Statut : implémenté sur le même chantier que la Phase 1, sans migration.**

Phase 2 raccorde le contrat Web Research au socle transversal intelligence existant :

~~~text
ResearchMission
  ↓
WebResearchRequest
  ↓
IntelligenceWebResearchEngine
  ↓
IntelligenceGateway
  ↓
IntelligenceCapability.WEB_RESEARCH
  ↓
IntelligenceRegistry
  ↓
provider adapter
  ↓
WebResearchResult
~~~

Le Gateway existant conserve donc ses responsabilités de routage en mémoire, fallback, erreurs provider et télémétrie sans payload brut.

### 32.1 Capacité runtime, sans route persistée prématurée

WEB_RESEARCH est ajouté comme IntelligenceCapability runtime.

Il n’est volontairement pas encore ajouté aux choix persistés de IntelligenceRoute. Les quatre capacités persistées restent :

~~~text
text_generate
structured_generate
embed
rerank
~~~

Cette séparation évite une migration purement mécanique avant d’avoir figé le protocole et la configuration durable des moteurs Web Research.

Conséquence : Phase 2 prouve le raccord au Gateway et au registry provider-neutral, mais ne déclare pas encore une configuration Web Research administrable en base.

### 32.2 Premier adapter : OpenAI Responses Web Search

Le premier adapter concret est OpenAIResponsesWebResearchProvider.

Il utilise l’API Responses avec l’outil web_search, conformément au protocole provider courant d’OpenAI, tout en restant derrière IntelligenceProvider et WEB_RESEARCH.

L’adapter :

- utilise POST /responses ;
- active web_search ;
- exige l’usage d’un outil pour une mission Web Research ;
- demande la liste complète des sources de web_search_call ;
- utilise Structured Outputs avec JSON Schema ;
- ne fournit aucune localisation implicite ;
- ne transmet que le scope explicitement présent dans ResearchMission ;
- utilise store=false ;
- convertit max_queries de ResearchMission.limits en max_tool_calls lorsque cette limite est définie ;
- ne retourne jamais la clé API dans le résultat.

Les détails OpenAI restent confinés à cet adapter. Un futur provider peut implémenter la même capability sans modifier WebResearchRequest ou WebResearchResult.

### 32.3 Validation des sources

Le provider produit deux flux distincts :

~~~text
sources réellement rapportées par le tool Web Search
+
candidats structurés qui citent des source_urls
~~~

IntelligenceWebResearchEngine ne conserve un candidat que si toutes ses source_urls correspondent à des sources effectivement rapportées par l’exécution provider.

Ainsi :

~~~text
URL inventée par le modèle
→ candidate_unknown_source
→ candidat rejeté
~~~

Le moteur ne transforme donc pas une simple URL générée en evidence.

### 32.4 Budgets

Deux limites du canevas sont déjà appliquées :

~~~text
max_queries
→ max_tool_calls côté adapter OpenAI

max_candidates
→ limite déterministe côté moteur Makolo
~~~

Si max_candidates est atteint, le résultat devient partiel avec budget_exhausted et conserve un warning candidate_limit_reached.

Les autres limites restent à mapper seulement lorsqu’un provider offre un contrôle explicite et stable.

### 32.5 Ce qui reste volontairement hors Phase 2

Phase 2 ne crée toujours pas :

- de nouvelle table ;
- de migration ;
- de route persistée WEB_RESEARCH ;
- de nouveau ProviderProtocol ;
- de credential store parallèle ;
- d’écriture vers Activity, Requirement ou un autre domaine ;
- de conversion automatique d’une citation Web en CandidateEvidence Actor 3 ;
- de scheduler ;
- de crawl automatique.

La prochaine couture utile est la Discovery générique : prendre un WebResearchResult, reconnaître ce qui est déjà connu, puis décider ce qui mérite observation, approfondissement ou résolution.


---

## 33. Phase 3 runtime — Discovery générique et sorties standards

**Statut : implémenté sur le même chantier, sans migration.**

Phase 3 introduit une sortie standard de Discovery qui ne dépend ni du provider Web Search, ni d’un domaine métier particulier :

~~~text
WebResearchResult
      ↓
DiscoveryNormalizer
      ↓
DiscoveryOutput v1
~~~

La sortie standard existe pour que les étapes aval puissent consommer une forme stable, même si les moteurs, les providers et les stratégies de recherche évoluent.

### 33.1 DiscoveryOutput v1

Chaque exécution produit notamment :

~~~text
request_ref
mission_ref
research_outcome
stop_reason
generated_at
source_count
candidate_count
counts_by_state
records[]
warning_codes
~~~

Chaque DiscoveryRecord conserve :

~~~text
candidate_ref
label
source_refs[]
type_hints[]
summary
knowledge_state
known_refs[]
basis_codes[]
~~~

Aucun champ provider/model n’appartient à cette sortie standard.

### 33.2 États standards de connaissance

Phase 3 formalise quatre états :

~~~text
KNOWN
NOT_KNOWN
AMBIGUOUS
UNRESOLVED
~~~

Leur sens est strict :

- KNOWN : un lookup borné a trouvé exactement une réalité Makolo connue ;
- NOT_KNOWN : le catalog interrogé a une couverture suffisante pour conclure que cette réalité n’y est pas connue ;
- AMBIGUOUS : plusieurs réalités connues restent possibles ;
- UNRESOLVED : le lookup disponible ne permet pas de conclure.

Invariant :

~~~text
UNRESOLVED != NOT_KNOWN
NOT_KNOWN != nouveau dans le monde
~~~

NOT_KNOWN signifie seulement « non connu de Makolo dans un catalog dont la couverture permet cette conclusion ».

### 33.3 DiscoveryKnowledgePort

La qualification known/not-known est derrière un port read-only :

~~~text
DiscoveryKnowledgePort.lookup(...)
    → DiscoveryLookup
~~~

La couche Discovery ne lit donc pas directement tous les domaines Makolo.

Un adapter peut fournir une connaissance plus ou moins forte, mais il doit retourner UNRESOLVED si sa couverture est insuffisante.

### 33.4 Premier adapter de connaissance

DjangoDiscoveryKnowledgeCatalog fournit un premier usage réel et volontairement prudent.

Il réutilise la canonicalisation Web du Prospecteur et effectue uniquement des rapprochements exacts de source URL vers des réalités déjà connues dans les catalogs actuellement sûrs pour ce test, notamment OpportunitySource et les websites Organization.

Il peut conclure :

~~~text
exactement une réalité
→ KNOWN

plusieurs réalités exactes
→ AMBIGUOUS

aucune correspondance exacte
→ UNRESOLVED
~~~

Il ne retourne pas NOT_KNOWN sur un simple miss, parce que l’absence d’une URL de ces tables ne prouve pas que Makolo ne connaît pas la réalité autrement.

### 33.5 Frontière avec Resolver

Discovery n’est pas un deuxième Resolver.

La sortie standard indique seulement ce que le lookup amont peut savoir avant approfondissement.

Le Resolver conserve l’autorité sur :

- identity matching complet ;
- provisional identity ;
- heuristiques bornées ;
- new_candidate ;
- relations ;
- facts ;
- updates ;
- conflicts.

Phase 3 permet simplement d’éviter de retraiter aveuglément une source dont Makolo possède déjà une correspondance exacte.

### 33.6 Sortie standard avant spécialisation

Le même DiscoveryOutput v1 doit pouvoir servir à :

~~~text
bourses
emplois
formations
transports
programmes
services
autres missions
~~~

Les spécialisations métier pourront ajouter des traitements aval, mais elles ne changent pas l’enveloppe standard de Discovery.

C’est cette stabilité qui permet d’avoir :

~~~text
plusieurs moteurs
+ plusieurs missions
+ plusieurs domaines
→ une sortie Makolo commune
~~~

### 33.7 Ce que Phase 3 ne fait pas encore

Phase 3 ne :

- crée aucune Opportunity ou autre réalité métier ;
- ne transforme pas UNRESOLVED en NEW_CANDIDATE ;
- ne lance pas automatiquement Actor 2 ;
- ne lance pas automatiquement Actor 4 ;
- ne décide pas encore quelles inconnues doivent devenir des missions DEEPEN ;
- ne persiste pas DiscoveryOutput ;
- ne crée pas de scheduler.

La prochaine phase peut travailler l’approfondissement en utilisant DiscoveryOutput v1 comme entrée stable, sans dépendre du provider qui a produit la découverte.


---

## 34. Phase 4 runtime — Deepen générique et missions secondaires standards

**Statut : implémenté sur le même chantier, sans migration ni scheduling.**

Phase 4 transforme la sortie standard de Discovery en un plan d’approfondissement également standard :

~~~text
DiscoveryOutput v1
      ↓
FamilyCoveragePort
      ↓
DeepenPlanner
      ↓
DeepenOutput v1
      ↓
ResearchMissionCandidate[]
~~~

Le but n’est pas de créer un moteur spécial bourses, transports ou emplois. Le même squelette peut être instancié avec des familles et questions différentes selon le type de mission.

### 34.1 Sortie standard DeepenOutput v1

DeepenOutput v1 expose :

~~~text
parent_mission_ref
discovery_request_ref
generated_at
target_count
suggestion_count
targets[]
suggestions[]
~~~

Chaque DeepenTarget conserve :

~~~text
candidate_ref
knowledge_state
coverage[]
suggested_mission_refs[]
~~~

Chaque FamilyCoverage associe une famille de recherche à un état standard :

~~~text
PRESENT
PARTIAL
MISSING
CONFLICTING
NOT_APPLICABLE
~~~

Invariant :

~~~text
MISSING
=
absent du matériau actuellement acquis

MISSING
!=
absent de la réalité
~~~

### 34.2 Les huit familles restent le squelette commun

Le runtime fournit une spécification générique STANDARD_ACTION_RESEARCH_SPECIFICATION couvrant les huit familles existantes :

~~~text
POSSIBILITY
ACTOR
REQUIREMENT
QUALIFICATION
SPATIOTEMPORAL
PROCEDURE
ECONOMIC
REFERENCE
~~~

Elle fournit des questions génériques et observables, sans vocabulaire propre à une verticale.

Une future instance spécialisée pourra choisir un sous-ensemble ou remplacer les questions sans modifier DeepenPlanner.

Exemple conceptuel :

~~~text
transport
→ POSSIBILITY
→ ACTOR
→ SPATIOTEMPORAL
→ PROCEDURE
→ ECONOMIC
→ REFERENCE

bourse
→ les huit familles si nécessaire
~~~

Le choix spécialisé appartient à l’instanciation de la mission, pas au moteur générique.

### 34.3 Baseline prudente de couverture

MinimalDiscoveryCoverage ne prétend connaître que ce que Discovery garantit réellement :

~~~text
POSSIBILITY
→ PRESENT parce qu’un candidat a été découvert

REFERENCE
→ PRESENT parce que le candidat possède au moins une source

autres familles
→ MISSING dans le matériau de Discovery
~~~

Cette baseline ne déduit donc pas une condition, un acteur, une procédure, un coût ou une date à partir d’un simple résumé.

Des implémentations futures de FamilyCoveragePort pourront exploiter des facts structurés, Actor 3 ou d’autres connaissances Makolo pour retourner PARTIAL, PRESENT, CONFLICTING ou NOT_APPLICABLE.

### 34.4 Réutilisation de ResearchMissionCandidate

Chaque approfondissement proposé réutilise le contrat déjà canonique ResearchMissionCandidate.

Une suggestion contient notamment :

~~~text
primary_family
subject = label de la réalité candidate
questions
known_context
unknowns
origin = previous_processing
scope hérité explicitement
limits héritées
priority héritée
~~~

Le known_context transporte seulement le contexte déjà autorisé et observé :

~~~text
candidate_ref
label
source_refs
type_hints
summary
knowledge_state
~~~

Aucune localisation utilisateur, préférence privée ou donnée de Profile n’est ajoutée implicitement.

### 34.5 Pas d’exécution automatique

DeepenPlanner produit des suggestions.

Il ne :

- schedule aucune mission ;
- ne persiste aucune mission ;
- ne déclenche pas automatiquement Web Search ;
- ne déclenche pas Actor 2 ou Actor 3 ;
- ne crée pas de vérité métier.

La frontière existante reste :

~~~text
ResearchMissionCandidate
!=
ResearchMission exécutée
~~~

Un étage d’orchestration futur décidera quelles suggestions méritent réellement une exécution selon priorité, budget, fraîcheur, doublons et profondeur.

### 34.6 KNOWN ne signifie pas « rien à approfondir »

Une réalité déjà reconnue par Makolo peut encore avoir des dimensions manquantes.

Ainsi :

~~~text
DiscoveryRecord
knowledge_state = KNOWN

mais

REQUIREMENT = MISSING
PROCEDURE = PARTIAL
ECONOMIC = MISSING
~~~

peut légitimement produire de nouvelles ResearchMissionCandidate.

La reconnaissance d’identité et la complétude de connaissance restent deux questions distinctes.

### 34.7 Standardisation avant verticalisation

Avec Phase 4, les deux premières sorties stables du cycle sont désormais :

~~~text
DiscoveryOutput v1
DeepenOutput v1
~~~

Ce principe sera conservé pour les phases suivantes : les moteurs et verticales peuvent être plus riches, mais Makolo garde au moins une enveloppe standard provider-neutral et versionnée pour chaque étape importante du cycle.


---

## 35. Phase 5 runtime — Watch, fraîcheur et réexamen standard

**Statut : implémenté sur le même chantier, sans migration ni scheduler.**

Phase 5 ajoute un troisième contrat de sortie standard :

~~~text
WatchOutput v1
~~~

Il ne réobserve pas automatiquement le Web. Il répond d’abord à une question plus simple et déterministe :

> parmi les sources déjà reliées à la connaissance Makolo, lesquelles sont encore fraîches et lesquelles doivent être revérifiées ?

Le cycle devient :

~~~text
DiscoveryOutput v1
      ↓
WatchKnowledgePort
      ↓
FreshnessPolicy
      ↓
WatchPlanner
      ↓
WatchOutput v1
~~~

### 35.1 États standards de fraîcheur

WatchOutput utilise :

~~~text
FRESH
DUE
UNRESOLVED
~~~

- FRESH : une source connue a été contrôlée dans la fenêtre de fraîcheur ;
- DUE : une source connue doit être réobservée ;
- UNRESOLVED : la source ne peut pas encore être reliée de manière assez sûre à un propriétaire de connaissance supporté par l’adapter.

Une source inconnue ne devient donc pas automatiquement DUE. Elle doit d’abord être résolue/admise dans la connaissance Makolo.

### 35.2 États standards de changement

Le contrat conserve aussi le dernier état de changement connu :

~~~text
UNCHANGED
CHANGED
UNREACHABLE
REMOVED
UNKNOWN
~~~

Ces états décrivent ce que Makolo sait du dernier contrôle ; ils ne déclenchent aucune mutation à eux seuls.

### 35.3 FreshnessPolicy

La première policy est volontairement minimale et générique :

~~~text
max_age_seconds
~~~

Pour une source connue :

~~~text
due_at = last_checked_at + max_age

due_at > maintenant
→ FRESH

due_at <= maintenant
→ DUE
~~~

Une source connue qui n’a jamais été contrôlée est DUE immédiatement.

La policy est un contrat runtime, pas un modèle persistant. Des policies spécialisées pourront être ajoutées plus tard selon la volatilité d’un fait ou d’une source, sans modifier WatchOutput v1.

### 35.4 Réutilisation d’OpportunitySource et de son historique

DjangoWatchKnowledgeCatalog réutilise les vérités déjà présentes :

~~~text
OpportunitySource.last_checked_at
OpportunitySource.status
OpportunitySourceCheck[]
~~~

Il est strictement read-only.

Il ne :

- crée aucun OpportunitySourceCheck ;
- ne change aucun OpportunitySource.status ;
- ne supprime aucun ancien check ;
- ne choisit pas une nouvelle vérité métier.

Les anciens checks restent append-only et continuent à représenter l’historique des contrôles.

### 35.5 Réutilisation future de l’Observateur

Actor 2 possède déjà :

~~~text
ObservationTrigger.WATCH
ObservationOutcome.NOT_MODIFIED
~~~

Phase 5 ne recrée pas ce mécanisme.

WatchOutput fournit les sources DUE qui pourront être confiées à l’Observateur par une orchestration ultérieure.

Le traitement attendu reste :

~~~text
source DUE
  ↓
Observer WATCH
  ↓
NOT_MODIFIED
  → aucun besoin de réinterpréter le contenu

ou

OBSERVED avec changement établi
  → nouvelle matière
  → interprétation/résolution
~~~

Une réponse HTTP réussie ou un nouvel artefact n’est pas automatiquement considéré comme un changement métier ; la comparaison de contenu et la résolution aval restent nécessaires.

### 35.6 Sortie WatchOutput v1

La sortie standard contient notamment :

~~~text
discovery_request_ref
generated_at
policy
target_count
counts_by_state
due_source_refs[]
targets[]
~~~

Chaque WatchTarget expose :

~~~text
source_ref
locator
freshness_state
known_ref
last_checked_at
due_at
last_change_state
basis_codes
~~~

Cette enveloppe ne contient aucun provider, modèle LLM ou secret.

### 35.7 Pas de suppression ni d’écrasement historique

Phase 5 maintient l’invariant posé par le cadrage :

~~~text
nouvelle vérification
!=
suppression de l’ancienne observation
~~~

Les contrôles et observations s’empilent dans les historiques propriétaires existants. L’état courant peut évoluer, mais l’ancienne connaissance reste traçable.

### 35.8 Ce que Phase 5 ne fait pas encore

Phase 5 ne :

- lance aucun scheduler ;
- n’exécute aucune requête HTTP ;
- n’appelle pas Web Search pour les sources DUE ;
- ne crée aucun SourceCheck ;
- ne transforme pas OBSERVED en CHANGED sans comparaison ;
- ne persiste pas WatchOutput ;
- ne décide pas encore comment une source changée réactive Deepen ou Resolver.

La prochaine étape peut maintenant relier les sorties standards du cycle :

~~~text
DiscoveryOutput
DeepenOutput
WatchOutput
~~~

à une orchestration bornée qui choisit explicitement quoi exécuter ensuite, sans rendre chaque suggestion automatique.


---

## 36. Phase 6 runtime — orchestration bornée du cycle standard

**Statut : implémenté sur le même chantier, sans migration et sans exécution automatique.**

Phase 6 relie les trois sorties standards déjà établies :

~~~text
DiscoveryOutput v1
DeepenOutput v1
WatchOutput v1
        ↓
CyclePlanner
        ↓
CyclePlan v1
~~~

CyclePlan v1 est une sortie de **décision**, pas une file de jobs et pas un scheduler.

Il répond à :

> étant donné ce que Makolo vient de découvrir, ce qu’il reste à approfondir et l’état de fraîcheur des sources, quelle est la prochaine action raisonnable ?

### 36.1 Actions standards

Le contrat définit :

~~~text
DEEPEN_MISSION
OBSERVE_SOURCE
WATCH_SOURCE
HOLD_FOR_RESOLUTION
NO_ACTION
~~~

Sens :

- DEEPEN_MISSION : une ResearchMissionCandidate déjà préparée mérite d’être considérée pour exécution ;
- OBSERVE_SOURCE : une source externe n’est pas encore suffisamment établie pour Watch et mérite une acquisition/observation contrôlée ;
- WATCH_SOURCE : une source Makolo connue est arrivée à échéance de fraîcheur ;
- HOLD_FOR_RESOLUTION : l’identité reste ambiguë/non résolue et aucune nouvelle mission d’approfondissement n’est actuellement nécessaire ;
- NO_ACTION : la réalité est connue, suffisamment couverte dans la spécification courante et ses sources sont encore fraîches.

Ces actions sont des directives standardisées. Elles ne sont pas exécutées par CyclePlanner.

### 36.2 Décisions déterministes

Les principales règles V1 sont :

~~~text
famille à approfondir
→ DEEPEN_MISSION

source connue + fraîcheur DUE
→ WATCH_SOURCE

source non encore watchable
→ OBSERVE_SOURCE

identité ambiguë/unresolved + aucun deepen nécessaire
→ HOLD_FOR_RESOLUTION

identité KNOWN + aucune dimension à approfondir + toutes sources FRESH
→ NO_ACTION
~~~

Les actions peuvent coexister.

Exemple :

~~~text
candidat encore unresolved
+ REQUIREMENT manquant
+ source pas encore watchable

→ DEEPEN_MISSION
→ OBSERVE_SOURCE
~~~

Le système n’est donc pas obligé de choisir artificiellement une seule action lorsque plusieurs responsabilités indépendantes sont nécessaires.

### 36.3 Sortie standard CyclePlan v1

CyclePlan contient :

~~~text
discovery_request_ref
generated_at
action_count
counts_by_action
actions[]
~~~

Chaque CycleAction expose seulement :

~~~text
action_kind
candidate_ref
source_ref
mission_ref
reason_codes
~~~

Le contrat ne contient :

- aucun nom de provider ;
- aucun modèle LLM ;
- aucun secret ;
- aucune donnée Profile implicite ;
- aucune commande ORM.

### 36.4 Frontières Actor 2 / Actor 3 / Resolver

Phase 6 ne contourne pas les Actors.

OBSERVE_SOURCE prépare une future acquisition par les mécanismes Observer appropriés.

WATCH_SOURCE prépare une future observation avec ObservationTrigger.WATCH.

HOLD_FOR_RESOLUTION ne signifie pas que DiscoveryOutput est directement consommable par Actor 4. Le Resolver conserve son entrée canonique InterpretedMaterial.

Le chemin de matière forte reste :

~~~text
source
→ Observer
→ ObservationMaterial
→ Interpreter
→ InterpretedMaterial
→ Resolver
~~~

Web Research peut découvrir et orienter ce chemin, mais ne fabrique pas artificiellement un ObservationMaterial ou un InterpretedMaterial.

### 36.5 Pas d’autonomie cachée

CyclePlanner ne :

- lance pas Web Search ;
- ne lance pas Actor 2 ;
- ne lance pas Actor 3 ;
- ne lance pas Resolver ;
- ne persiste aucune ResearchMissionCandidate ;
- ne crée aucun job ;
- ne modifie aucun domaine ;
- ne planifie aucun cron/scheduler.

La prochaine couche, si elle est nécessaire, sera une orchestration d’exécution explicite avec budgets, idempotence et admission de directives, sans changer les sorties standards déjà établies.

### 36.6 Les sorties standards du cycle

À ce stade le canevas runtime possède quatre enveloppes provider-neutral et versionnées :

~~~text
WebResearchResult
        ↓
DiscoveryOutput v1
        ↓
DeepenOutput v1
        ↓
WatchOutput v1
        ↓
CyclePlan v1
~~~

Elles permettent aux moteurs et aux verticales de devenir plus riches sans obliger les consommateurs aval à connaître les détails d’OpenAI, Anthropic, d’un crawler particulier ou d’une verticale métier particulière.
