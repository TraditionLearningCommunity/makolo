# Mayele — système autonome d’intelligence de Makolo
## Acquisition, connaissance, orchestration et alimentation continue de Molongo

**Statut :** cadre conceptuel et architectural de référence — avant architecture détaillée des communications et de la propriété des données  
**Date :** 29 septembre 2026  
**Dépôt :** TraditionLearningCommunity/makolo  
**Base Git vérifiée :** main@5e4d3a62a1ae4009c7c2591a4c11acf19db61c3e  
**Portée :** nommer et cadrer Mayele, sa relation avec Molongo et l’application Makolo, et consolider les briques techniques retenues sans prétendre qu’elles sont toutes déjà implémentées.  
**Hors périmètre :** propriété détaillée de chaque donnée, protocoles exacts entre composants, schéma final de persistance de Molongo, API finales de serving et topologie de production.

---

# 0. Décision de vocabulaire

Le projet distingue désormais trois ensembles de nature différente :

| Nom | Sens retenu dans le projet | Fonction principale |
| --- | --- | --- |
| **Makolo** | les pieds | application utilisée par les personnes pour avancer dans l’action réelle |
| **Molongo** | l’univers | univers formel autonome dans lequel les réalités, états, relations, conditions, événements, trajectoires et calculs peuvent être représentés |
| **Mayele** | l’intelligence / la sagesse | système autonome qui observe, cherche, acquiert, lit, vérifie, rapproche, historise, orchestre et prépare la matière de connaissance qui alimente Molongo |

La relation générale est :

~~~text
MONDE RÉEL / MONDE NUMÉRIQUE
            │
            ▼
         MAYELE
  acquisition + connaissance
  + cognition + orchestration
            │
            ▼
         MOLONGO
 univers formel + calculs
            │
            ▼
 projections / résultats précalculés
            │
            ▼
         MAKOLO
 application d'action
            │
            ▼
       UTILISATEUR
~~~

Formulation synthétique :

> **Mayele cherche et établit ce que le système peut raisonnablement connaître.**  
> **Molongo représente ce monde connu et permet de le calculer.**  
> **Makolo exploite les résultats pertinents pour accompagner l’action réelle.**

Une formule plus courte peut servir de mémo :

~~~text
Mayele connaît.
Molongo représente et calcule.
Makolo accompagne l'action.
~~~

Le verbe « connaître » ne signifie jamais que Mayele possède une vérité absolue. Mayele doit distinguer observation, preuve, interprétation, contradiction, incertitude, fraîcheur et vérité canonique admise.

---

# 1. Pourquoi Mayele existe

La promesse de Makolo reste :

> **« Makolo marche pour vous. »**

Dans l’expérience visée, cette promesse doit pouvoir devenir :

> **« Avance. Ce qui pouvait être préparé l’est déjà ; voici ce qui reste réellement à faire. »**

Cette expérience est impossible si l’application doit commencer tout le travail au moment précis où l’utilisateur ouvre un écran.

Une grande partie du travail doit pouvoir avoir eu lieu auparavant :

- découvrir ce qui existe ;
- lire et comprendre des sources ;
- retrouver des sources officielles ;
- observer un site ou un document ;
- détecter qu’une information a changé ;
- conserver les preuves ;
- comparer plusieurs versions ;
- résoudre des identités ;
- maintenir des relations ;
- recalculer des graphes ;
- approfondir des inconnues ;
- préparer des structures exploitables par Molongo ;
- recalculer les résultats affectés par un changement.

Mayele est le nom de cet ensemble autonome.

Invariant :

~~~text
utilisateur connecté
        !=
Mayele actif
~~~

Mayele peut travailler lorsqu’aucun utilisateur n’utilise Makolo.

---

# 2. Le parallèle avec Google : inspiration d’architecture, pas copie de produit

L’intuition de départ peut être illustrée par Google.

Un utilisateur qui lance une recherche Google n’attend pas que Google découvre le Web entier après la saisie de sa requête. Une infrastructure travaille en amont : crawl, indexation, analyse de liens, calculs, fraîcheur, signaux et structures préparées.

Schématiquement :

~~~text
Web
  ↓
Crawlers / Googlebot
  ↓
contenus observés
  ↓
index
  ↓
graphe du Web
  ↓
PageRank + autres calculs
  ↓
structures préparées
  ↓
Google Search
  ↓
requête utilisateur
~~~

Makolo ne copie ni Google Search ni PageRank. Le parallèle concerne la séparation entre :

1. le travail de fond, effectué avant la demande interactive ;
2. la représentation calculable du monde ;
3. le produit interactif, qui exploite des résultats déjà préparés.

L’architecture cible devient :

~~~text
Web + APIs + documents + systèmes connectés + événements
                         │
                         ▼
                       MAYELE
                         │
        acquisition / validation / connaissance
                         │
                         ▼
                       MOLONGO
                         │
       graphes / géométrie / dynamique / calculs
                         │
                         ▼
              résultats précalculés
                         │
                         ▼
                       MAKOLO
                         │
                         ▼
                    action réelle
~~~

Le parallèle s’arrête là où les problèmes divergent : Google Search cherche principalement des documents pertinents pour une requête ; Makolo doit comprendre ce qui compte pour rendre une action réelle possible, préparée ou exécutable.

---

# 3. Les niveaux à ne jamais confondre

Le projet doit conserver les distinctions déjà acquises :

~~~text
Monde réel
    !=
Vue métier Makolo
    !=
Backend / domaines canoniques
    !=
Molongo
~~~

Mayele traverse plusieurs frontières comme système d’acquisition, de connaissance et d’orchestration, mais il ne remplace aucun domaine propriétaire.

## 3.1 Monde réel / monde numérique externe

C’est ce qui existe indépendamment de Makolo : personnes, institutions, services, événements, routes, règles, documents, sites Web, messages, systèmes informatiques et phénomènes réels.

Le monde ne devient pas faux ou vrai selon ce que Mayele sait de lui.

## 3.2 Mayele

Mayele construit et entretient l’état de connaissance de Makolo sur ce monde.

~~~text
réalité
!=
observation
!=
interprétation
!=
résolution
!=
fait admis
~~~

## 3.3 Molongo

Molongo est un univers formel autonome.

Il ne doit pas être réduit à Neo4j, pgvector, PostgreSQL, au schéma Django, à un moteur de recommandation ou à la mémoire d’un LLM.

## 3.4 Makolo

Makolo est l’application et l’expérience d’action.

L’application peut composer :

- les vérités opérationnelles de ses domaines propriétaires ;
- les projections autorisées ;
- les résultats et projections d’intelligence précalculés issus de Molongo.

Molongo ne remplace donc pas les décisions autoritatives de Permission, Mandate, Access, Capacity, Payment ou d’autres domaines.

---

# 4. Définition canonique de Mayele

> **Mayele est le système autonome d’intelligence de l’écosystème Makolo.**
>
> Il découvre, acquiert, observe, lit, interprète, vérifie, rapproche, historise, retrouve et maintient des connaissances provenant du Web, de sources connectées et de systèmes autorisés.
>
> Il orchestre des traitements courts ou durables, exploite des agents et modèles IA lorsque cela est utile, utilise la connaissance existante avant de refaire un travail coûteux et conserve la provenance nécessaire pour expliquer ce qui est connu, pourquoi, depuis quand et avec quelles limites.
>
> Sa finalité principale n’est pas de produire une réponse jetable à chaque requête utilisateur. Sa finalité est d’agrandir et d’entretenir le capital de connaissance exploitable, puis d’alimenter Molongo de manière contrôlée afin que les calculs et projections nécessaires à Makolo puissent être préparés avant leur consommation interactive.

---

# 5. Ce que Mayele n’est pas

Mayele n’est pas :

- l’application Makolo ;
- Molongo ;
- un chatbot ;
- un unique agent IA ;
- un simple wrapper autour de Tavily ou Exa ;
- un crawler unique ;
- un RAG ;
- une base de données universelle ;
- un second backend métier ;
- une seconde source de vérité pour Activity, Occurrence, Journey, Requirement, Proof, Access, Capacity, Payment ou les autres domaines canoniques ;
- un système qui transforme toute donnée trouvée en vérité ;
- un moteur de ranking humain universel ;
- une raison de copier toutes les données privées dans un graphe global ;
- un fournisseur IA particulier.

Invariant :

~~~text
Mayele = système

Tavily / Exa / LLM / LangGraph / Temporal /
Neo4j / n8n / MCP = composants remplaçables
~~~

---

# 6. Architecture fonctionnelle de Mayele

~~~text
MAYELE
│
├── Acquisition
│   ├── Tavily
│   ├── Exa
│   ├── Web Search provider-neutral
│   ├── Crawlers
│   ├── Common Crawl / index externes
│   └── Connecteurs autorisés
│
├── Observation & contenu
│   ├── HTTP
│   ├── Browser lorsque nécessaire
│   ├── PDF
│   ├── images
│   ├── documents bureautiques
│   └── pièces jointes
│
├── Cognition
│   ├── Agents IA
│   ├── LangGraph
│   ├── RAG
│   ├── interprétation structurée
│   ├── résolution d'identité
│   ├── validation
│   ├── contradiction
│   └── revalidation
│
├── Orchestration
│   ├── Temporal
│   ├── n8n
│   ├── MCP
│   ├── workers
│   └── budgets / politiques d'arrêt
│
├── Connaissance
│   ├── PostgreSQL
│   ├── pgvector
│   ├── Cloudflare R2
│   ├── Neo4j Community
│   └── Neo4j GDS Community
│
├── Observabilité
│   ├── OpenTelemetry
│   ├── Prometheus
│   ├── Loki
│   ├── Tempo
│   └── Grafana
│
└── Alimentation de Molongo
    ├── admission contrôlée
    ├── faits canoniques propriétaires
    ├── Projecteur
    ├── snapshots / deltas
    └── déclenchement des recalculs utiles
~~~

Cette arborescence exprime des responsabilités. Elle ne signifie pas qu’un microservice distinct doit être créé pour chaque ligne.

---

# 7. Acquisition : Search, Crawl et connecteurs

Mayele doit pouvoir acquérir de la matière par plusieurs voies.

## 7.1 Search

Tavily et Exa sont retenus comme moteurs externes cibles, derrière un contrat interne stable.

~~~text
Mayele Search Port
    ├── Tavily adapter
    ├── Exa adapter
    ├── provider Web Search existant
    └── fournisseurs futurs
~~~

Le fournisseur ne possède jamais le modèle de connaissance.

## 7.2 Crawl

Search et Crawl ne sont pas synonymes :

~~~text
SEARCH
= découvrir et élargir le territoire connu

CRAWL
= explorer méthodiquement un territoire connu

WATCH
= vérifier ce qui a changé
~~~

## 7.3 Connecteurs

Mayele doit pouvoir lire, sous autorisation explicite :

- Gmail ;
- Google Drive ;
- Dropbox ;
- GitHub ;
- OneDrive / SharePoint ;
- Notion ;
- Slack ;
- APIs ;
- bases externes ;
- systèmes partenaires futurs.

Le fait qu’une source soit connectée ne signifie jamais que tout son contenu devient connaissance globale ou publique.

---

# 8. Cognition et rôles spécialisés

Mayele peut utiliser plusieurs rôles logiques :

| Rôle | Responsabilité |
| --- | --- |
| Planificateur | décomposer une mission et identifier les inconnues |
| Chercheur Web | rechercher sources et candidats |
| Chercheur de sources | remonter vers les sources primaires ou officielles |
| Lecteur documentaire | lire HTML, PDF, images, DOCX, XLSX et pièces jointes |
| Interpréteur | transformer le contenu en candidats structurés |
| Résolveur | rapprocher les candidats des réalités connues |
| Validateur | recouper, chercher contradictions et preuves |
| Historien | comparer les états successifs |
| Agent de connaissance | retrouver ce que Mayele sait déjà |
| Agent de revalidation | revérifier une connaissance sensible au temps |
| Agent connecteur | utiliser des outils externes autorisés |
| Analyste | produire une synthèse interne ou un résultat structuré |

Ces rôles peuvent être implémentés par du code déterministe, un LLM, plusieurs modèles, LangGraph, Temporal ou une combinaison.

Un rôle logique n’implique pas automatiquement un agent autonome séparé.

---

# 9. Multi-agent, LangGraph et A2A

Le multi-agent est une capacité de Mayele, mais il doit rester contrôlé.

~~~text
orchestrateur
    │
    ├── délègue une mission bornée
    ├── fournit uniquement les outils autorisés
    ├── attend une sortie structurée
    ├── mesure coût / durée / résultat
    └── décide du prochain pas
~~~

Chaque tâche agentique devrait définir :

~~~text
entrée
objectif
outils autorisés
contexte autorisé
format de sortie
budget
timeout
critère d'arrêt
politique de retry
niveau de preuve attendu
~~~

**LangGraph** est retenu pour les graphes cognitifs et transitions agentiques complexes.

**A2A** reste une capacité future utile si des agents ou systèmes réellement autonomes doivent se découvrir et se déléguer des tâches. A2A n’est pas requis pour appeler Mayele « multi-agent ».

---

# 10. RAG : récupérer avant de rechercher à nouveau

Le RAG appartient à Mayele comme mécanisme de récupération, pas comme source de vérité.

Il doit répondre d’abord à :

> « Qu’est-ce que nous savons déjà qui peut éviter une nouvelle recherche coûteuse ? »

Il pourra combiner :

- requêtes structurées PostgreSQL ;
- recherche plein texte ;
- pgvector ;
- métadonnées ;
- filtres temporels ;
- provenance ;
- graphe ;
- historique de versions.

~~~text
nouvelle mission
     ↓
connaissance existante
     ↓
inconnues réelles
     ↓
recherche complémentaire seulement si nécessaire
~~~

Invariant :

~~~text
RAG != vérité
RAG != Molongo
RAG != mémoire opaque du modèle
~~~

---

# 11. Connaissance, preuve et historique

Une recherche utile ne produit pas seulement un texte final.

Mayele doit pouvoir préserver séparément :

- source ;
- document ;
- artefact ;
- observation ;
- extrait probant ;
- affirmation candidate ;
- entité candidate ;
- relation candidate ;
- contradiction ;
- résolution d’identité ;
- état de validation ;
- version ;
- fraîcheur ;
- historique ;
- provenance ;
- calcul dérivé.

Cycle conceptuel :

~~~text
Source
  ↓
Document / page
  ↓
Evidence
  ↓
Claim candidat
  ↓
Validation / contradiction
  ↓
Résolution
  ↓
Admission éventuelle dans le domaine propriétaire
~~~

L’absence d’information ne doit jamais devenir silencieusement une information négative :

~~~text
UNKNOWN != FALSE
UNKNOWN != CLOSED
UNKNOWN != NOT_APPLICABLE
~~~

---

# 12. Temps et fraîcheur

Mayele doit être temporel par construction.

Selon la donnée, il peut être nécessaire de distinguer :

~~~text
published_at
phenomenon_at
observed_at
received_at
recorded_at
valid_from
valid_to
last_verified_at
superseded_at
next_review_at
~~~

Une nouvelle valeur ne détruit pas automatiquement l’ancienne.

Le système doit pouvoir déterminer si une différence correspond à :

- un changement réel ;
- une correction ;
- une contradiction ;
- deux contextes différents ;
- ou une information non résolue.

L’historique est une donnée, pas un déchet à écraser.

---

# 13. Validation et provenance

La finalité de Mayele n’est pas « produire beaucoup de données ». Elle est de produire de la connaissance traçable et raisonnablement défendable.

Une donnée importante doit pouvoir répondre à :

- d’où vient-elle ?
- qui l’a publiée ?
- quand ?
- quel document ou passage la soutient ?
- a-t-elle été observée directement ?
- a-t-elle été interprétée par un modèle ?
- existe-t-il une source primaire ?
- existe-t-il une contradiction ?
- quand a-t-elle été vérifiée pour la dernière fois ?
- quelle partie est un fait et quelle partie est une inférence ?

Principe :

~~~text
source de découverte
!=
source suffisante pour établir un fait critique
~~~

Une source secondaire peut découvrir une réalité ; Mayele peut ensuite rechercher le propriétaire, la source officielle ou des confirmations indépendantes.

---

# 14. PostgreSQL, pgvector, R2 et Neo4j

La stack de connaissance retenue est :

~~~text
PostgreSQL
+ pgvector
+ Cloudflare R2
+ Neo4j Community / GDS Community
~~~

## PostgreSQL

Données structurées, versionnées, transactionnelles, auditables et référentielles.

## pgvector

Embeddings et récupération sémantique.

## Cloudflare R2

Fichiers et objets binaires : PDF, images, captures, documents, pièces jointes et artefacts autorisés.

## Neo4j

Structures de graphe et calculs graphiques.

Invariant :

~~~text
Neo4j != Molongo
~~~

Neo4j est un moteur et un support de calcul. Molongo est le modèle formel.

La frontière exacte entre graphe de connaissance de Mayele, graphe/projection de Molongo, structures reconstruisibles et résultats persistés reste à définir dans le chantier suivant.

---

# 15. Pourquoi le graphe est central

Le graphe n’est pas ajouté pour produire une belle visualisation.

Il sert à faire émerger des propriétés structurelles impossibles à voir dans une simple liste d’objets.

Algorithmes envisagés :

- PageRank ;
- centralités ;
- connected components ;
- Louvain ;
- Leiden ;
- label propagation ;
- K-Core ;
- shortest paths ;
- similarité de nœuds ;
- link prediction ;
- embeddings graphiques ;
- algorithmes spécifiques futurs.

Boucle possible :

~~~text
connaissance accumulée
        ↓
graphe
        ↓
algorithme
        ↓
signal / hypothèse
        ↓
mission Mayele
        ↓
recherche / vérification
        ↓
nouvelle connaissance
        ↓
graphe mis à jour
~~~

Une hypothèse produite par un algorithme reste une hypothèse tant qu’elle n’a pas acquis le niveau de preuve requis.

---

# 16. Orchestration durable : Temporal

Mayele doit exécuter des travaux qui dépassent une requête HTTP :

- deep research ;
- ingestion massive ;
- revalidation ;
- surveillance ;
- recalculs ;
- reprise après panne ;
- attente de fenêtre temporelle ;
- synchronisation de connecteurs ;
- workflows sur plusieurs heures ou jours.

Temporal est retenu comme moteur cible de workflows durables.

~~~text
Temporal
= durée + reprise + timers + orchestration durable
~~~

Temporal ne remplace ni Django, ni LangGraph, ni les domaines métier, ni Molongo.

---

# 17. n8n et MCP

## n8n

n8n est retenu pour les intégrations événementielles, webhooks et automatisations périphériques.

~~~text
nouveau document Drive
      ↓
n8n
      ↓
entrée Mayele
      ↓
workflow durable
~~~

n8n ne doit pas devenir le propriétaire de la logique métier ni du modèle de connaissance.

## MCP

MCP est retenu comme protocole utile pour exposer certains outils et ressources aux agents.

Exemples :

~~~text
search_email()
read_email()
search_drive()
read_drive_file()
search_dropbox()
search_web()
open_url()
search_knowledge()
~~~

Tout ne doit pas obligatoirement passer par MCP. Une API directe reste acceptable lorsqu’elle apporte plus de contrôle, de sécurité, de performance ou une sémantique plus claire.

---

# 18. Modèles IA : flexibilité obligatoire

Mayele ne doit pas être lié à un fournisseur unique.

Fournisseurs possibles :

- OpenAI ;
- Gemini ;
- Claude ;
- modèles locaux ;
- fournisseurs futurs.

Le choix doit être fait par capacité et contraintes :

~~~text
tâche simple          → modèle économique
extraction structurée → modèle fiable et rapide
vision                 → modèle multimodal approprié
validation complexe    → modèle plus puissant
~~~

Invariant :

~~~text
LLM_PROVIDER != Mayele
~~~

---

# 19. Mayele travaille même sans session Makolo

Mayele possède plusieurs modes de fonctionnement autonomes :

~~~text
DISCOVER
→ découvrir ce que le système ne connaît pas encore

DEEPEN
→ approfondir une réalité partiellement connue

OBSERVE
→ acquérir le matériau réel d'une source

VERIFY
→ chercher une preuve, une source primaire ou une contradiction

WATCH
→ vérifier ce qui a changé

CRAWL
→ entretenir méthodiquement un territoire connu

REVALIDATE
→ vérifier une connaissance sensible au temps

COMPUTE
→ recalculer index, graphes et résultats dérivés

PROJECT
→ préparer les entrées et projections destinées à Molongo
~~~

Ces travaux peuvent être déclenchés :

- périodiquement ;
- par événement ;
- par changement détecté ;
- par expiration ;
- par mission interne ;
- par action utilisateur ;
- par un calcul Molongo révélant une inconnue utile.

Les budgets et critères d’arrêt restent obligatoires.

---

# 20. Alimentation de Molongo

La sortie principale de Mayele n’est pas un paragraphe de réponse.

Elle est un ensemble de connaissances et structures suffisamment contrôlées pour contribuer à Molongo.

~~~text
information trouvée
!=
fait canonique
!=
entrée Molongo admise
~~~

Lorsqu’une information correspond à une vérité métier possédée par un domaine Makolo, le chemin normal respecte le propriétaire canonique :

~~~text
source externe
   ↓
Mayele acquisition
   ↓
observation
   ↓
interprétation
   ↓
résolution / vérification
   ↓
admission contrôlée
   ↓
domaine canonique propriétaire
   ↓
Projecteur
   ↓
Molongo
~~~

Mayele peut conserver des observations, contradictions ou candidats non encore admis. Leur existence épistémique ne leur donne pas automatiquement un statut ontologique dans Molongo.

---

# 21. Compatibilité avec le pipeline Actor existant

Le nom **Mayele** ne remplace pas ce qui existe déjà ; il devient l’ombrelle conceptuelle sous laquelle les capacités actuelles trouvent leur place.

À la base Git vérifiée, le dépôt possède notamment :

~~~text
ResearchMission
      ↓
Actor 1 — Prospecteur
      ↓
Actor 2 — Observateur
      ↓
Actor 3 — Interpréteur
      ↓
Actor 4 — Résolveur
      ↓
Actor 5 — Orchestrateur
      ↓
Actor 6 — Persistateur / owners métier
      ↓
Actor 7 — Projecteur
      ↓
Actor 8 — Univers (runtime non encore livré)
~~~

Interprétation avec le nouveau vocabulaire :

~~~text
MAYELE
├── ResearchMission
├── Web Research
├── Prospecteur
├── Observateur
├── Interpréteur
├── Résolveur
├── orchestration et connaissance
├── admission vers les owners
└── Projecteur / frontière d'alimentation

MOLONGO
└── nom conceptuel retenu pour l'Univers formel autonome
~~~

Le Projecteur actuel reste important : il construit des UniverseSnapshot / UniverseDelta déterministes à partir de faits canoniques. Cette frontière doit être préservée.

---

# 22. État réel du dépôt au moment de ce cadrage

Ce document distingue explicitement le runtime courant de la cible Mayele.

## Déjà présent ou démontré sur main

- Django / Python comme cœur serveur ;
- ResearchMission ;
- pipeline Prospecteur / Observateur / Interpréteur / Résolveur / Orchestrateur ;
- Actor 6 et propriétaires métier ;
- Actor 7 Projecteur intégré ;
- Common Crawl / capacités Prospecteur existantes ;
- Crawlee dans la frontière Prospecteur / Observateur ;
- infrastructure intelligence provider-neutral ;
- génération, structured generation, embeddings, reranking ;
- capacité runtime Web Research ;
- premier adapter Web Search concret via OpenAI Responses ;
- DiscoveryOutput, DeepenOutput, WatchOutput et CyclePlan des phases Web Search 1–6 ;
- workers et garde-fous d’observation HTTP / Browser documentés.

La PR #360 « Web Search Phases 1–6 » a été fusionnée et ses workflows visibles de CI, Security supply chain, Beta seed validation, Funding PostgreSQL et Conversation PostgreSQL ont réussi.

## Cible retenue mais non déclarée déjà livrée

- Tavily ;
- Exa ;
- LangGraph ;
- Temporal ;
- MCP comme couche structurée de Mayele ;
- n8n ;
- pgvector comme couche vectorielle généralisée ;
- Cloudflare R2 comme stockage objet cible ;
- Neo4j Community + GDS Community ;
- OpenTelemetry + Grafana / Prometheus / Loki / Tempo comme stack complète ;
- runtime Molongo ;
- serving final des résultats précalculés de Molongo.

Ce document n’invente donc pas l’existence runtime de ces briques.

---

# 23. Molongo : univers autonome, pas cache de Mayele

Molongo existe indépendamment d’une question personnelle.

~~~text
Molongo global
     ↓
système pertinent pour une question
     ↓
projection contextuelle
~~~

Mayele entretient ce que le système connaît du monde ; Molongo transforme les entrées admissibles en un univers calculable.

Selon les cadres scientifiques consolidés, Molongo peut porter ou calculer :

- Corps ;
- relations ;
- conditions ;
- événements ;
- positions ;
- temps ;
- états ;
- histoires ;
- trajectoires ;
- systèmes pertinents ;
- structures de graphe ;
- grandeurs et interactions lorsqu’elles sont scientifiquement consolidées ;
- résultats analytiques dérivés.

La géométrie et la dynamique de Molongo ne doivent pas être créées à partir de la convenance d’un schéma de base de données.

---

# 24. Calculs hors ligne et précalcul

Une partie fondamentale du modèle est que les calculs lourds ne doivent pas tous être exécutés dans la requête utilisateur.

Exemples :

- index de recherche ;
- embeddings ;
- relations résolues ;
- composantes connexes ;
- centralités ;
- PageRank ;
- communautés ;
- structures réutilisables ;
- détection de changements ;
- fraîcheur ;
- projections Molongo ;
- résultats dérivés dont les dépendances n’ont pas changé.

~~~text
nouvelle connaissance / changement
          ↓
identification des calculs invalidés
          ↓
recalcul borné
          ↓
nouvelle version du résultat
          ↓
projection précalculée disponible
~~~

Le système doit éviter de recalculer tout Molongo lorsqu’un changement local ne touche qu’une partie du monde représenté.

---

# 25. Serving : ce que Makolo doit recevoir rapidement

La couche de serving finale reste à définir techniquement, mais sa responsabilité est claire.

~~~text
Mayele travaille en arrière-plan
          ↓
Molongo est mis à jour
          ↓
calculs dérivés mis à jour
          ↓
projections précalculées
          ↓
utilisateur ouvre Makolo
          ↓
composition contextuelle rapide
          ↓
« Qu'est-ce qui compte maintenant ? »
~~~

Cela ne signifie pas que chaque réponse est figée à l’avance.

La requête utilisateur peut encore déclencher :

- une sélection contextuelle ;
- un calcul léger ;
- une vérification de fraîcheur ;
- une nouvelle mission Mayele si une information critique manque ;
- un arbitrage serveur autoritatif.

Mais le système ne doit pas repartir du Web brut à chaque écran.

---

# 26. Sources privées et confidentialité

Le fait que Mayele puisse se connecter à Gmail, Drive ou Dropbox impose un invariant fort :

~~~text
donnée privée accessible à Mayele
!=
donnée autorisée à entrer dans Molongo global
!=
donnée autorisée à être montrée à un autre utilisateur
~~~

Chaque donnée doit conserver son contexte d’autorisation.

Mayele doit respecter :

- consentement ;
- portée du connecteur ;
- least privilege ;
- séparation lecture / écriture ;
- provenance ;
- sensibilité ;
- durée de conservation ;
- révocation ;
- minimisation ;
- divulgation minimale.

Une composition ne transfère jamais implicitement Permission, Mandate, Access, Payment ou accès à des données privées.

---

# 27. Observabilité

Mayele doit être observable comme un système de production.

~~~text
OpenTelemetry
     │
     ├── traces  → Tempo
     ├── metrics → Prometheus
     └── logs    → Loki
                    │
                    ▼
                 Grafana
~~~

Les corrélations doivent pouvoir suivre :

~~~text
ResearchMission
→ recherche provider
→ source
→ observation
→ interprétation
→ résolution
→ validation
→ admission
→ projection Molongo
→ calcul
→ projection servie
~~~

L’objectif est aussi de pouvoir répondre à :

> « Pourquoi le système croit-il cela et quelle chaîne de traitement l’a produit ? »

---

# 28. Infrastructure

La cible reste compatible avec :

~~~text
Django + Python
Flutter
Next.js si une interface Web séparée le justifie
Docker
VPS
~~~

Mayele peut être réparti progressivement en plusieurs processus ou machines sans modifier ses contrats conceptuels.

La topologie exacte reste une décision d’exploitation future.

---

# 29. Architecture complète, implémentation progressive

Le choix reste :

> **architecture complète dès le départ, implémentation progressive de cette même architecture.**

« Progressif » ne signifie pas « prototype jetable ».

Chaque tranche doit :

- respecter les frontières finales ;
- utiliser des contrats versionnés ;
- conserver la provenance ;
- être reconstruisible lorsque cela est prévu ;
- éviter les dépendances fournisseur dans le métier ;
- éviter les vérités parallèles ;
- être testable ;
- être observable ;
- pouvoir être remplacée sans réécrire l’ensemble.

---

# 30. Invariants Mayele

1. **Mayele travaille indépendamment de la présence d’un utilisateur.**
2. **Mayele ne devient pas une seconde source de vérité métier.**
3. **Une donnée trouvée n’est pas automatiquement une vérité admise.**
4. **Observation, interprétation, résolution, admission et projection restent distinctes.**
5. **Mayele peut conserver l’incertitude et la contradiction.**
6. **La provenance et le temps de connaissance font partie du résultat.**
7. **RAG est une méthode de récupération, pas une vérité.**
8. **Neo4j est un moteur de graphe, pas Molongo lui-même.**
9. **Les fournisseurs IA et Search restent remplaçables.**
10. **Les sources privées conservent leur portée d’autorisation.**
11. **Molongo existe indépendamment d’un Profile particulier.**
12. **Makolo consomme des résultats préparés sans être obligé de refaire l’acquisition.**
13. **Les calculs lourds doivent pouvoir être exécutés hors du chemin critique utilisateur.**
14. **Un changement doit invalider uniquement les calculs réellement dépendants lorsque cette dépendance est connue.**
15. **Le runtime courant gagne toujours sur les roadmaps et documents historiques.**

---

# 31. Anti-features

Mayele ne doit pas dériver vers :

- un crawler Internet sans bornes ;
- un système de scraping sans provenance ;
- une boucle d’agents qui conversent sans objectif ni budget ;
- un data lake où tout est stocké « au cas où » ;
- un graphe qui mélange données publiques et privées sans portée ;
- un LLM qui écrit directement dans les tables métier ;
- un score universel de valeur humaine ;
- une ontologie créée uniquement pour satisfaire une bibliothèque ;
- un système qui cache ses incertitudes ;
- un mécanisme qui confond « non trouvé » et « n’existe pas » ;
- une infrastructure qui recalcule tout à chaque requête ;
- un deuxième Makolo caché derrière Makolo.

---

# 32. Nomenclature de transition : Univers Makolo → Molongo

Le dépôt courant utilise encore le terme **Univers Makolo**, notamment dans les documents Actor 7 / Actor 8 et les contrats UniverseSnapshot, UniverseDelta et UniverseProjectionPort.

Ce document introduit **Molongo** comme nom conceptuel retenu pour cet Univers.

~~~text
« Univers Makolo » dans le runtime/docs existants
≈
Molongo dans le nouveau vocabulaire conceptuel
~~~

Cette équivalence de nom ne signifie pas qu’il faut renommer immédiatement modules Python, types de contrats, migrations, routes, variables ou documents scientifiques historiques.

Une éventuelle migration terminologique sera un chantier séparé, audité sur le main courant.

---

# 33. Schéma général consolidé

~~~mermaid
flowchart TD
    W[Monde réel / Web / systèmes externes]

    subgraph MAYELE[Mayele — intelligence autonome]
        A[Acquisition]
        O[Observation et contenu]
        C[Cognition]
        K[Connaissance]
        T[Orchestration]
        P[Admission / Projecteur]

        A --> O
        O --> C
        C <--> K
        T --> A
        T --> C
        T --> K
        C --> P
        K --> P
    end

    subgraph MOLONGO[Molongo — univers formel autonome]
        U[Corps / Relations / Conditions / Événements]
        D[États / Temps / Positions / Trajectoires]
        G[Graphes / géométrie / dynamique]
        X[Calculs et projections dérivées]
        U --> D --> G --> X
    end

    subgraph MAKOLO[Makolo — application d'action]
        S[Serving / projections précalculées]
        APP[Web / Mobile / Desktop]
        S --> APP
    end

    W --> A
    P --> U
    X --> S
~~~

Ce diagramme est conceptuel. Il ne fixe pas encore les transports réseau ni les propriétaires physiques des bases.

---

# 34. Cycle de vie complet d’une connaissance

~~~mermaid
flowchart LR
    A[Source] --> B[Découverte]
    B --> C[Observation]
    C --> D[Interprétation]
    D --> E[Résolution]
    E --> F[Validation]
    F --> G[Admission canonique]
    G --> H[Projection Molongo]
    H --> I[Calcul]
    I --> J[Résultat précalculé]
    J --> K[Makolo]

    L[Watch / Revalidation] --> C
    I -->|inconnue détectée| M[Nouvelle ResearchMission]
    M --> B
~~~

Le cycle peut repartir lorsqu’une contradiction apparaît, une source change, une preuve expire, un algorithme révèle une inconnue ou une nouvelle dépendance devient pertinente.

---

# 35. Relation avec les documents existants

Ce document ne remplace pas :

- [makolo-domain-blueprint.md](makolo-domain-blueprint.md) pour les frontières métier ;
- [makolo-web-search.md](makolo-web-search.md) pour le cycle générique de recherche Web ;
- [research-missions.md](research-missions.md) pour les missions ;
- [interpreter.md](interpreter.md) ;
- [resolver.md](resolver.md) ;
- [orchestrator.md](orchestrator.md) ;
- [persistator.md](persistator.md) ;
- [projector.md](projector.md) ;
- [../operations-runbook.md](../operations-runbook.md) pour l’exploitation actuelle ;
- les documents scientifiques de l’Univers / Molongo.

Il ajoute une couche de langage et d’architecture supérieure :

~~~text
capacités existantes et futures
        ↓
système autonome d'intelligence
        ↓
MAYELE
~~~

---

# 36. Ce qui reste volontairement ouvert

Le prochain chantier devra répondre précisément à :

- quel composant possède chaque donnée ?
- quelle donnée est canonique, dérivée, cache, index ou projection ?
- PostgreSQL et Neo4j stockent-ils les mêmes relations ou des projections différentes ?
- quel graphe appartient à Mayele et quel graphe appartient à Molongo ?
- Molongo possède-t-il une persistance propre ou est-il reconstruisible ?
- où sont stockés les résultats précalculés consommés par Makolo ?
- comment invalider les calculs lorsqu’une source change ?
- quel rôle exact joue Actor 7 dans le vocabulaire Mayele → Molongo ?
- quels flux utilisent appels synchrones, événements, Temporal, webhooks ou MCP ?
- comment Molongo peut-il demander à Mayele de rechercher une inconnue sans créer une boucle incontrôlée ?
- comment protéger les données privées nécessaires à un calcul personnel ?
- quels résultats sont globaux, collectifs, personnels ou strictement privés ?
- où placer les algorithmes Neo4j/GDS : Mayele, Molongo ou couche de calcul commune ?
- comment versionner les modèles, règles, graphes et calculs ?
- quelle stratégie de reconstruction appliquer après perte d’un index ou d’une projection ?

Ces décisions doivent découler des propriétaires conceptuels et des invariants, pas seulement des outils disponibles.

---

# 37. Conclusion

Le projet possède désormais trois noms pour trois responsabilités différentes :

~~~text
MAKOLO
les pieds
→ l'application qui accompagne l'action

MOLONGO
l'univers
→ le monde formel autonome que le système représente et calcule

MAYELE
l'intelligence / la sagesse
→ le système autonome qui cherche, observe, comprend, vérifie,
  entretient la connaissance et alimente Molongo
~~~

La chaîne directrice devient :

~~~text
MONDE
  ↓
MAYELE
  ↓
MOLONGO
  ↓
RÉSULTATS PRÉCALCULÉS
  ↓
MAKOLO
  ↓
ACTION RÉELLE
~~~

La valeur de cette architecture est précisément que **Makolo n’attend pas l’utilisateur pour commencer à travailler**.

Mayele entretient continuellement la connaissance.

Molongo conserve et calcule une représentation du monde indépendamment d’une session utilisateur.

Makolo arrive ensuite au moment de l’action avec le maximum de travail déjà effectué, tout en revalidant ce qui doit l’être et en respectant les vérités, permissions et autorités de ses domaines propriétaires.

Le prochain document devra fixer :

> **les communications entre les briques, la propriété des données, les projections reconstruisibles et la frontière exacte Mayele → Molongo → Makolo.**
