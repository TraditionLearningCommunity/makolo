# Makolo — Strategic Action Roadmap

> **Statut : canonique pour la cible produit/architecture après le noyau Mature.** Ce document complète [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md). Il répertorie les 18 capacités stratégiques retenues, explique comment elles se composent avec les domaines canoniques et les regroupe dans les trains **P / Q / R / D / O / U**. Le séquencement de clôture M7→M10 et le handoff vers le programme mobile A sont définis dans [`mature-program-roadmap.md`](mature-program-roadmap.md). Les principes d'expérience destinés à M8 sont définis dans [`mature-experience-principles.md`](mature-experience-principles.md). Ce document **ne décrit pas à lui seul le runtime livré** : le code, les migrations et les tests du `main` courant restent la vérité sur ce qui existe effectivement.

## 1. Intention

Makolo ne doit pas devenir un réseau social classique, un Drive, un gestionnaire de tâches générique ou une collection de verticales indépendantes.

La cible est un **réseau d'action** capable de comprendre :

- ce qu'un Profil ou un Espace cherche à accomplir ;
- ce qui est déjà prêt ;
- ce qui manque ;
- qui doit agir ;
- au nom de qui quelqu'un agit ;
- pour quel bénéficiaire ;
- ce qui bloque ou change ;
- ce qui doit se passer maintenant ;
- ce qui peut être réutilisé ;
- ce que les actions précédentes peuvent apprendre aux suivantes.

La promesse produit reste **« Makolo marche pour vous »** et peut se lire opérationnellement comme :

> **Préparer ce qui peut l'être, orchestrer ce qui doit être fait, accompagner l'action jusqu'au terrain et transformer ce qui a déjà été accompli en avantage pour la suite.**

La direction d'expérience ajoute une qualité complémentaire :

> **Makolo vous donne envie d'avancer.**

Cette cible concerne autant les particuliers que les Espaces. Un même Profil peut agir en son nom propre ou dans un contexte d'autorité d'Espace ; il ne possède pas un type utilisateur global « participant » ou « organisateur ».

## 2. Règle de composition

Les capacités ci-dessous ne deviennent pas automatiquement autant de bounded contexts Django.

Avant de créer un modèle, une app ou un état persistant, l'implémentation doit vérifier si le besoin peut être porté par :

- un domaine canonique existant ;
- une relation explicite ;
- un service d'orchestration ;
- un selector/read model ;
- Readiness ;
- Domain Events + Automation/Autopilot ;
- Analytics ;
- Presentation ;
- Discovery ;
- une projection UX.

Les vérités canoniques restent notamment `Activity`, `Occurrence`, `Journey`, `JourneyStep`, `Requirement`, `Payment`, `Access`, `Capacity`, `Proof`, `Mandate` et les objets de leurs domaines propriétaires.

## 3. Les 18 capacités retenues

### 1. Sharing — circulation de l'action

- **Type** : extension canonique désormais intégrée au produit ; vérifier le runtime courant pour ses contrats exacts.
- **Problème** : un lien partagé transmet souvent une destination, pas le contexte nécessaire pour agir.
- **Promesse** : **« Je ne t'envoie pas seulement quelque chose à regarder ; je t'envoie quelque chose sur lequel tu peux agir. »**
- **Mécanisme** : sujets explicites, contexte borné, livraisons internes/externes, reprise contrôlée ; aucun transfert implicite de Permission, Mandate, Access, Payment ou document sensible.
- **Domaines** : Activity, Occurrence, Opportunity, Journey, Notifications et documents selon les contrats Sharing réellement livrés.
- **Défensibilité** : Makolo fait circuler du contexte opérationnel structuré plutôt qu'une URL nue.
- **Train** : **P**.

### 2. Bibliothèque personnelle — capital documentaire durable

- **Type** : nouveau concept justifié par le gap entre stockage personnel durable et `JourneyArtifact` lié à une Journey.
- **Problème** : CV, diplômes, certificats, pièces et justificatifs doivent être réimportés dans chaque démarche.
- **Promesse** : **« Les documents utiles que vous choisissez de conserver sont déjà disponibles lorsque vous en avez besoin. »**
- **Mécanisme** : asset/document personnel durable, privé, versionné, avec provenance, sensibilité, contrôleur et sujet éventuel. L'utilisation dans une Journey doit conserver une représentation auditable de la version réellement utilisée.
- **Domaines** : Profile, JourneyArtifact, private storage, Trust/Proof, Requirements, Sharing lorsqu'il est pertinent.
- **Défensibilité** : pas le fichier seul, mais fichier + provenance + versions + contexte d'utilisation + validité.
- **Train** : **Q**.

### 3. Action Memory — ne pas recommencer

- **Type** : convergence de données existantes et d'intelligence de lecture.
- **Problème** : Makolo connaît déjà une partie du passé utile d'un utilisateur mais une nouvelle action repart trop souvent de zéro.
- **Promesse** : **« Vous avez déjà fait une partie de ce travail. »**
- **Mécanisme** : retrouver des candidats dans Bibliothèque, JourneyArtifact, Proofs et autres faits explicitement réutilisables ; qualifier pertinence, fraîcheur, sensibilité et consentement. Ne pas supposer un modèle persistant `ActionMemory`.
- **Domaines** : Profile, Journey, JourneyArtifact, Trust, Requirements, Readiness, Bibliothèque.
- **Défensibilité** : historique contextualisé `artefact → démarche → exigence → décision → résultat`.
- **Train** : **Q**.

### 4. Prepared Start — commencer plus loin

- **Type** : extension de la philosophie Readiness avant une Journey matérialisée.
- **Problème** : découvrir une Opportunity ne dit pas ce qui est réellement prêt ou manquant pour agir.
- **Promesse** : **« Voici ce qui est déjà prêt et ce qui manque avant de commencer. »**
- **Mécanisme** : projection explicable de Requirements contre Profile, Bibliothèque, Action Memory et Proofs/Trusted Reuse ; aucun score opaque d'éligibilité.
- **Domaines** : Opportunity, Requirements, Readiness, Profile, Trust et Q.
- **Défensibilité** : Makolo relie ce que le monde exige à ce que l'utilisateur possède déjà.
- **Train** : **R**.

### 5. Proactive Preparation — surveiller les changements utiles

- **Type** : convergence de veille de Requirements, expirations, deadlines et faits actionnables.
- **Problème** : une démarche se bloque parce qu'un changement important est vu trop tard.
- **Promesse** : **« Makolo vous prévient quand un changement modifie réellement votre prochaine action utile. »**
- **Mécanisme** : Domain Events, Automation/Autopilot et Notifications existants ; aucune seconde infrastructure de scheduling.
- **Domaines** : Requirements, Opportunity, Journey, Bibliothèque, Payment, Capacity, Access, Automation, Notifications et M6 lorsqu'il est pertinent.
- **Défensibilité** : alertes issues de faits métier structurés plutôt que de surveillance comportementale opaque.
- **Train** : **R**.

### 6. Dossier — objectif actif composé

- **Type** : nouveau concept majeur, à introduire seulement après audit des modèles existants.
- **Problème** : un résultat réel peut exiger plusieurs Journeys, plusieurs personnes et des dépendances entre démarches ; une Journey géante ou des Journeys dispersées sont toutes deux mauvaises.
- **Promesse** : **« Tout ce qui doit avancer vers ce résultat se trouve dans un même contexte d'accomplissement. »**
- **Mécanisme** : composition de Journeys, bénéficiaires, collaborateurs, échéances, relations inter-Journeys et Readiness dérivée. Le Dossier ne duplique ni Step, Payment, Access, Capacity, Artifact ni Permission.
- **Domaines** : Journey, Profile/ExternalBeneficiary, Assignment, Mandate, Readiness, Activity/Opportunity et domaines enfants.
- **Défensibilité** : compréhension structurée d'un résultat composé et collectif.
- **Train** : **D**.

### 7. Projet — horizon durable

- **Type** : concept complémentaire au Dossier ; sa frontière avec `goals.PersonalGoal` doit rester explicite.
- **Problème** : certains objectifs durent des mois/années et produisent plusieurs Dossiers sans être eux-mêmes une urgence opérationnelle.
- **Promesse** : **« Gardez une direction durable sans transformer chaque objectif en Dossier permanent. »**
- **Mécanisme** : regroupement d'intentions et de Dossiers ; ne pas devenir un Trello/Notion bis. Tous les Dossiers n'ont pas besoin d'un Projet.
- **Domaines** : Profile, Space, Goals à auditer, Dossier et projections associées.
- **Défensibilité** : continuité entre horizon long terme et exécution concrète.
- **Train** : **D**.

### 8. Structured Handoff — responsabilité explicite

- **Type** : convergence de capacités existantes.
- **Problème** : dans une démarche collective, les blocages viennent souvent de l'incertitude sur qui doit agir et qui en a l'autorité.
- **Promesse** : **« Chacun sait ce qu'il doit faire et pourquoi il peut le faire. »**
- **Mécanisme** : JourneyAssignment/JourneyStepAssignment + Mandate/Permission. **Assignment = responsabilité ; Mandate = autorité.**
- **Domaines** : Journey, JourneyStep, Assignment, authorization, Notifications, Dossier.
- **Défensibilité** : orchestration liée à des processus métier, pas task manager générique.
- **Train** : **D**.

### 9. Collective Readiness — sommes-nous prêts ensemble ?

- **Type** : convergence Readiness + collectif.
- **Problème** : une équipe ou une famille doit comprendre son état global sans ouvrir chaque Journey ni exposer des détails sensibles.
- **Promesse** : **« Voyez ce qui bloque le collectif sans exposer inutilement les personnes. »**
- **Mécanisme** : agrégation privacy-safe de projections Readiness ; aucun `CollectiveReadinessState` persistant et aucune matérialisation massive de Journeys.
- **Domaines** : Readiness, Group, Dossier, Space, Journey, Requirements, Analytics.
- **Défensibilité** : coordination de plusieurs parcours individuels avec disclosure contrôlée.
- **Train** : **D**.

### 10. Trusted Reuse — réutilisation réellement acceptable

- **Type** : convergence Trust/Proof + Requirements + Action Memory.
- **Problème** : retrouver un document ne prouve pas qu'il satisfait une nouvelle exigence.
- **Promesse** : **« Une preuve reconnue dans ce contexte peut réellement supprimer du travail. »**
- **Mécanisme** : contrat contextuel entre Requirement, Proof/ProofType, source, fraîcheur et politique d'acceptation. Jamais de validité universelle implicite.
- **Domaines** : Requirements, Trust/Proof, JourneyArtifact, Bibliothèque, Action Memory, Readiness.
- **Défensibilité** : réseau de preuves contextuellement acceptées qui peut supprimer des étapes réelles.
- **Train** : fondation **Q**, approfondissement **U**.

### 11. Proven Paths — les chemins accomplis améliorent les suivants

- **Type** : convergence historique Journey + Analytics + Feedback + templates/resources.
- **Problème** : les mêmes blockers, délais et erreurs se répètent alors que Makolo dispose progressivement de données structurées.
- **Promesse** : **« Les difficultés rencontrées par les précédents deviennent des raccourcis pour les suivants. »**
- **Mécanisme** : agrégats privacy-safe sur Steps, dependencies, blockers, délais, Requirements, Resources, outcomes et feedback ; suggestions explicables, jamais réécriture automatique du métier.
- **Domaines** : Journey, Requirements, preparation, questionnaires, Trust/Feedback, Analytics, templates Services.
- **Défensibilité** : cartographie vivante de ce qui bloque et fonctionne dans l'action réelle.
- **Train** : **U**.

### 12. Operational Readiness — prêt pour l'exécution

- **Type** : extension de Readiness vers l'opération d'une Occurrence.
- **Problème** : les opérateurs découvrent trop tard qu'un accès, un placement, un checkpoint ou une affectation n'est pas prêt.
- **Promesse** : **« Avant l'ouverture, Makolo montre ce qui empêche l'Occurrence de fonctionner correctement. »**
- **Mécanisme** : projection dérivée des faits Activity/Occurrence, Access, Capacity, Scanner, Placement, Resources et Assignments ; aucun état opérationnel dupliqué si le fait existe déjà.
- **Domaines** : Activity, Occurrence, Access, Capacity, Scanner, preparation, authorization, futurs Placement/Flow.
- **Défensibilité** : préparation issue de vérités métier réelles plutôt qu'une checklist libre.
- **Train** : **O**.

### 13. Occurrence Live — Makolo pendant l'action réelle

- **Type** : extension majeure du noyau Activity/Occurrence.
- **Problème** : lorsque l'Activity commence, participants et opérateurs reviennent souvent au papier, Excel, messages et improvisation.
- **Promesse** : **« Quand l'action commence, Makolo montre à chacun ce qui compte maintenant. »**
- **Mécanisme** : projection temps réel selon acteur, contexte d'autorité et bénéficiaire, à partir des domaines propriétaires. Occurrence Live n'est pas une seconde base opérationnelle.
- **Domaines** : Occurrence, AccessUse, Scanner, Capacity, Assignments, Mandates, Analytics, M6 Temporal/Spatial/Hazards, futurs Queue/Placement/Checkpoint.
- **Défensibilité** : contexte partagé de l'exécution réelle, personnalisé sans dupliquer les vérités.
- **Train** : **O**.

### 14. Live Queue — attendre son tour, pas une place

- **Type** : nouveau mécanisme, distinct de la Waitlist commerciale/capacité existante.
- **Problème** : quelqu'un qui possède déjà son droit perd du temps dans une file physique ou au mauvais point de contrôle.
- **Promesse** : **« Makolo peut vous dire quand avancer et, lorsque les données le permettent, où l'attente est la plus courte. »**
- **Mécanisme** : queue opérationnelle, entrée de file, checkpoint, débit observé, no-show/expiration et estimation prudente. **Waitlist = attendre qu'une place se libère ; Live Queue = attendre son tour après avoir déjà le droit pertinent.**
- **Domaines** : Occurrence, Access, AccessUse, Capacity, Scanner, Notifications, Analytics.
- **Défensibilité** : chaque passage réel améliore la compréhension des flux suivants.
- **Train** : **O**.

### 15. Placement — où dois-je aller ?

- **Type** : nouveau mécanisme transversal.
- **Problème** : après admission, tables, sièges, salles, bus, chambres ou zones sont souvent gérés dans des feuilles parallèles.
- **Promesse** : **« Une fois admis, chacun sait immédiatement où aller. »**
- **Mécanisme** : plan/groupe/emplacement/assignment structurés, avec vocabulaire métier configurable. Placement répond **où ?** ; Capacity reste propriétaire de **combien ?**
- **Domaines** : Activity, Occurrence, Capacity, Access, Profile/beneficiary, Resources, Occurrence Live.
- **Défensibilité** : valeur forte lorsqu'il est combiné à Access et Flow.
- **Train** : **O**.

### 16. Checkpoints / Flow — prochain point de passage

- **Type** : nouveau mécanisme opérationnel.
- **Problème** : une Occurrence peut comporter plusieurs passages successifs et des goulots d'étranglement difficiles à voir.
- **Promesse** : **« Makolo vous guide vers le prochain point utile et aide l'opérateur à comprendre le flux. »**
- **Mécanisme** : checkpoints opérationnels successifs liés à l'Occurrence. Ne pas les confondre avec `JourneyStep` : Step = action d'une démarche ; Checkpoint = point de passage d'une exécution réelle.
- **Domaines** : Occurrence, Access, Queue, Capacity, Scanner, Placement, Analytics.
- **Défensibilité** : compréhension structurée des flux terrain et de leurs bottlenecks.
- **Train** : **O**.

### 17. Offline Action Pack — continuité en connectivité faible

- **Type** : extension d'expérience et de résilience.
- **Problème** : les informations essentielles peuvent devenir indisponibles précisément au moment où la connectivité se dégrade.
- **Promesse** : **« Les éléments essentiels restent disponibles dans les limites du contrat de sécurité. »**
- **Mécanisme** : O prépare le contrat backend/offline-ready : données nécessaires, provenance, sensibilité, expiration, révocation et éventuelle synchronisation sûre. Le stockage local natif, le background sync OS et le vrai protocole scanner offline appartiennent au programme mobile **A4** ; O ne les réimplémente pas dans Django ou le navigateur.
- **Domaines** : Access, Occurrence, ActivityResource, Bibliothèque/JourneyArtifact, Placement.
- **Défensibilité** : fiabilité de l'expérience dans des environnements réels difficiles.
- **Train** : **O** pour les contrats backend/web ; **A4** pour les garanties natives/offline spécialisées.

### 18. Accueil contextuel — ce qui compte maintenant

- **Type** : convergence UX, pas bounded context.
- **Problème** : un accueil générique oblige l'utilisateur à chercher la prochaine action ; un feed générique optimise l'attention plutôt que l'accomplissement.
- **Promesse** : **« Ouvrez Makolo et voyez ce qui mérite votre attention maintenant, personnellement ou pour l'Espace dans lequel vous agissez. »**
- **Mécanisme** : projection hiérarchisée de Readiness/NextAction, Dossiers, Journeys, Assignments, Occurrences, Hazards M6, Notifications et opérations autorisées. R construit les règles/projections de préparation ; D et O apportent respectivement le contexte d'objectif et l'état opérationnel ; **M8 compose la surface web Accueil** et le mobile la consomme ensuite sans créer une seconde vérité.
- **Domaines** : Readiness, M5/M6, Journey, Dossier, Occurrence, authorization, Notifications.
- **Défensibilité** : capacité à déterminer la prochaine action utile à partir de faits structurés.
- **Train** : **R** pour les contrats de préparation, enrichissement **D/O**, composition web **M8**.

## 4. Trains d'implémentation

Les 18 capacités sont regroupées dans six trains stratégiques. **Les lettres ne sont pas une suite alphabétique imposant un ordre total.** Elles nomment des lignes de travail avec des dépendances explicites.

| Train | Intention | Capacités principales |
|---|---|---|
| **P — Sharing** | Faire circuler l'action | Sharing P1→P5 |
| **Q — Capital d'action personnel** | Ne plus recommencer | Bibliothèque, Action Memory, fondation Trusted Reuse |
| **R — Préparation intelligente** | Savoir ce qui est prêt et anticiper | Prepared Start, Proactive Preparation, contrats de l'Accueil contextuel |
| **D — Dossiers, Projets & Collaboration** | Accomplir des objectifs composés, seul ou ensemble | Dossier, Projet, Structured Handoff, Collective Readiness |
| **O — Occurrence Operations** | Préparer et orchestrer le réel | Operational Readiness, Occurrence Live, Placement, Live Queue, Checkpoints/Flow, contrats Offline Action Pack |
| **U — Intelligence cumulative** | Faire apprendre les actions précédentes aux suivantes | Proven Paths, Trusted Reuse avancé, analytics d'action/opérations |

### Nommage D et O

`S` n'est plus utilisé pour Dossier/Projet : le dépôt possède déjà un programme **Subscription S1→S6**. `T` n'est plus utilisé pour Occurrence Operations : le projet possède déjà un historique de tâches Services en série T. Les nouvelles désignations canoniques sont donc **D** et **O**.

Les anciennes mentions `P→U`, `S — Objectifs & collaboration` ou `T — Occurrence Operations` dans de la documentation historique doivent être lues comme des désignations antérieures ; les documents canoniques actuels utilisent P/Q/R/D/O/U.

### Train P

P a été conçu comme train autonome de checkpoints empilés. Son état réel et ses contrats doivent toujours être vérifiés dans `main` plutôt que déduits de cette roadmap.

### Train Q

Q suit la discipline d'un train autonome empilé :

```text
main vérifié au démarrage
  ↓
Q1 — fondation Bibliothèque / capital personnel
  ↓
Q2 — UX Bibliothèque + réutilisation contrôlée vers JourneyArtifact
  ↓
Q3 — Action Memory comme intelligence de lecture
  ↓
Q4 — fondation Trusted Reuse + sécurité/hardening
  ↓
réconciliation avec le main du moment
  ↓
intégration unique de Q
```

Q ne doit pas être continuellement réécrit en fonction d'un autre train non mergé.

### Train R

R dépend matériellement de Q pour ses contrats de Bibliothèque, Action Memory et Trusted Reuse. Son audit peut commencer en parallèle de Q, mais son implémentation finale doit partir du `main` contenant les contrats Q stabilisés.

R ne dépend pas structurellement de M7 : Prepared Start et Proactive Preparation sont des capacités internes Makolo. M7 pourra ensuite exposer certaines de leurs actions/capabilities vers des providers ou extensions.

### Train D

D — Dossiers, Projets & Collaboration — peut avancer en parallèle de Q à partir d'un `main` vérifié car son noyau compose Journey, bénéficiaires, Assignment, Mandate et Readiness plutôt que le capital documentaire Q.

D doit éviter les refontes globales de `/me/`, de la navigation et des templates Journey que Q pourrait toucher ; M8 possède l'assemblage transversal.

### Train O

O — Occurrence Operations — dépend principalement d'Activity/Occurrence, Access/AccessUse, Capacity, Scanner, Assignments/Mandates, Analytics et M6. Il n'a pas de dépendance forte sur Q/R.

Par défaut, O démarre lorsque D a suffisamment stabilisé les contrats transversaux Acteur / contexte d'autorité / bénéficiaire et collaboration. Cette dépendance est de coordination : l'audit O peut commencer plus tôt.

### Train U

U doit être construit lorsque suffisamment de données réelles existent. Proven Paths et l'intelligence opérationnelle ne doivent pas prétendre apprendre de la démo comme s'il s'agissait d'une population représentative.

**U est hors du chemin critique M8→M10→mobile.** Les trains précédents doivent cependant produire les Domain Events, timestamps, causes, blockers, transitions et analytics privacy-safe nécessaires à un futur U crédible.

## 5. Dépendances principales et parallélisme

La structure de travail de référence est :

```text
M1–M6 + P
     │
     ├──────────────┬────────────────┐
     ▼              ▼                │
Q — Capital      D — Dossiers        │
personnel        / Projets           │
     │              │                │
     ▼              ▼                │
R — Préparation  O — Occurrence      │
intelligente     Operations          │
     │              │                │
     └───────┬──────┘                │
             │                  M8-PRE audit
             │                  expérience/media
             └──────────┬─────────────┘
                        ▼
                       M7
                        ↓
                       M8
                        ↓
                       M9
                        ↓
                      M10
                        ↓
                    A — Mobile

U — Intelligence cumulative : hors chemin critique, déclenchée lorsque les données réelles le justifient.
```

Le parallélisme recherché est donc celui de **deux lignes métier largement indépendantes** :

- ligne A : `Q → R` ;
- ligne B : `D → O`.

Une piste **M8-PRE** d'audit/contrats d'expérience peut avancer en parallèle sans devenir un troisième bounded context.

Les merges/reconciliations doivent rester petits, traçables et fondés sur le `main` réel du moment.

## 6. M8-PRE — préparation d'expérience, pas nouveau train métier

[`mature-experience-principles.md`](mature-experience-principles.md) définit quatre responsabilités de préparation :

- **M8-P0** — audit Presentation / Discovery / storage / media / M5 ;
- **M8-P1** — représentation Activity-first et éventuelle fondation media seulement si le gap est confirmé ;
- **M8-P2** — Bounded Exploration et contrats de Discovery ;
- **M8-P3** — Action Rituals comme scénarios d'acceptation transversaux.

M8-PRE ne crée pas un train `V — Media`. Sensory Discovery, Contextual Action Media, Bounded Exploration et Action Rituals sont des responsabilités d'expérience/composition, pas quatre bounded contexts.

Le code actuel possède déjà une représentation image dans la verticale Event. Cette compatibilité ne doit pas devenir l'architecture générique finale : la direction est **Activity-first**, après audit de M3 Presentation et des contrats storage réels.

## 7. Contexte d'action transversal

Makolo ne sépare pas le monde en comptes « participants » et « organisateurs ».

Pour toute action sensible ou opérationnelle, il faut pouvoir distinguer conceptuellement :

1. **Acteur** — quel Profil humain agit réellement ?
2. **Contexte d'autorité** — agit-il en son nom ou pour quel Espace/portée via ses Permissions/Mandates ?
3. **Bénéficiaire** — pour qui l'action produit-elle le résultat ?

Ces trois dimensions peuvent désigner trois sujets différents.

Une Assignment ne devient jamais une Permission. Une Membership ne devient jamais une autorité. L'interface peut proposer **Agir en mon nom** / **Pour l'Espace X**, mais le serveur revalide toujours la vraie autorité.

## 8. Projet, Dossier, Journey, Step et Occurrence

La granularité cible est :

| Question | Concept |
|---|---|
| Quelle direction durable poursuivons-nous ? | **Projet** |
| Quel résultat actif doit maintenant avancer ? | **Dossier** |
| Quelle démarche concrète suit un bénéficiaire dans un contexte Activity ? | **Journey** |
| Quelle action précise fait avancer cette Journey ? | **JourneyStep** |
| Que se passe-t-il réellement maintenant pour cette Activity ? | **Occurrence / Occurrence Live** |

Le Dossier absorbe le besoin conceptuel d'un « Action Graph/Mission composée » séparé. Les relations inter-Journeys appartiennent au niveau Dossier tant qu'aucun gap futur ne justifie un domaine distinct.

`goals.PersonalGoal` et Projet ne doivent pas être confondus : Goals porte aujourd'hui des cibles personnelles mesurables ; Projet vise une initiative structurante longue. Le train D doit auditer cette frontière avant création de modèle.

## 9. Capital documentaire et preuves

Trois notions restent séparées :

- **Bibliothèque** : ce que l'utilisateur choisit de conserver et gérer ;
- **Action Memory** : ce que Makolo retrouve et propose de réutiliser ;
- **Trusted Reuse** : ce qui est réellement acceptable pour un Requirement précis.

`JourneyArtifact` reste l'artefact d'une Journey. `ActivityResource` reste la ressource partagée de préparation d'une Activity/Occurrence. Une Bibliothèque personnelle ne transforme aucun des deux en stockage générique.

La suppression ou le remplacement d'un asset source ne doit pas réécrire silencieusement l'historique d'une Journey qui l'a utilisé.

## 10. Readiness étendu sans nouveau domaine

Prepared Start, Collective Readiness et Operational Readiness sont des extensions de la philosophie de projection Readiness, pas des justifications pour créer trois nouvelles tables d'état.

- **Prepared Start** projette ce qui est déjà disponible avant le démarrage complet d'une démarche lorsque le contexte permet une évaluation légitime.
- **Collective Readiness** agrège des états autorisés pour un Dossier sans révéler les détails individuels non nécessaires.
- **Operational Readiness** projette la préparation d'une Occurrence depuis ses faits opérationnels.

Les domaines propriétaires restent responsables des états et transitions.

## 11. Occurrence Operations

Occurrence Live compose le réel au lieu de le recopier :

```text
Queue       → quand avancer ?
Checkpoint  → où passer ?
Access      → peut-on passer ?
Placement   → où aller ensuite ?
```

La Waitlist commerciale existante reste distincte de Live Queue.

Le scanner reste un contrôleur d'Access ; il peut afficher une projection de Placement après un contrôle accepté mais ne devient pas propriétaire du Placement.

Capacity reste propriétaire des quantités ; Placement reste propriétaire de l'affectation spatiale/organisationnelle.

M6 reste propriétaire de ses projections temporelles/spatiales, Hazards et ActionAdvice. **O les compose** au lieu de créer un second Hazard, ETA ou contexte de mobilité.

## 12. Accueil, Discover et M5

L'Accueil contextuel n'est pas un remplacement ni une duplication de l'Action Stream M5.

- **Action Stream M5** : projection sociale/action contextualisée et bornée ;
- **Accueil** : projection privée et opérationnelle de ce qui nécessite l'attention de l'acteur maintenant ;
- **Discover** : espace volontaire d'exploration de possibilités réelles.

Aucun `FeedItem` métier générique ne doit être créé pour réaliser l'Accueil ou Discover.

M5 reste `No Orphan Content`. L'extension média suit **No Orphan Media** : un média doit conserver un contexte et une finalité, sans créer un réseau social de contenu autonome.

## 13. Flywheels recherchés

### Personnel

`Journey accomplie → contexte utile conservé → Action Memory → Prepared Start → nouvelle Journey plus courte`.

### Collectif

`Journeys accomplies → blockers/délais agrégés → templates/resources améliorés → parcours suivants mieux préparés`.

### Opérationnel

`Occurrence → AccessUse/flows observés → goulots compris → Operational Readiness suivante améliorée`.

### Confiance

`fait réel → Proof → acceptation contextuelle → Requirement satisfait → étape supprimée`.

### Désir d'action

`Discover → possibilité ressentie → Activity ouverte → action réelle → accomplissement → capital/mémoire → nouvelle possibilité mieux contextualisée`.

## 14. Actifs défendables

Makolo doit accumuler de la valeur dans les structures utiles à l'action, pas dans des compteurs de popularité :

- Requirements structurés et leurs révisions ;
- provenance/versions des éléments réutilisables ;
- ProofTypes et politiques d'acceptation ;
- parcours accomplis, dépendances, blockers et délais ;
- Resources/templates efficaces ;
- états de préparation explicables ;
- flux opérationnels, files et débits observés ;
- contexte d'action personnel/organisationnel ;
- raisons de recommandation explicables ;
- représentations média contextualisées lorsqu'elles sont réellement nécessaires.

## 15. Anti-duplication et anti-features

Ne pas créer :

- un deuxième Readiness ;
- un deuxième Trust/Proof ;
- un deuxième Requirement engine ;
- un deuxième scheduler ;
- un deuxième système de Permission ;
- des Payments/Access/Capacity propres à Dossier ou Occurrence Live ;
- une Journey artificielle pour stocker un fichier personnel ;
- un stockage généraliste type Drive ;
- un rôle universel « Protocole »/« Logisticien » lorsque Permission + Role + Mandate peuvent exprimer l'autorité ;
- un score universel de personne ou d'éligibilité ;
- un tracking de localisation permanent pour faire fonctionner Flow ;
- un feed générique persistant pour l'Accueil ou Discover ;
- likes/réactions/popularité comme moteur central de la valeur Makolo ;
- une certification universelle implicite à partir d'une Proof ;
- `VideoPost`, Reel, Story, Creator economy ou WatchTimeScore comme nouveau cœur produit ;
- un bounded context Media avant preuve d'un gap transversal réel ;
- une exploration artificiellement infinie qui dégrade ses critères uniquement pour continuer à servir des items.

## 16. Ripple

`Ripple` reste **explicitement non défini**. Aucune équipe ne doit créer un domaine, un modèle ou une responsabilité `Ripple` à partir d'une interprétation spéculative.

## 17. Discipline de livraison

Pour les trains empilés comme Q ou D lorsqu'ils sont organisés ainsi :

- checkpoints depuis le checkpoint précédent ;
- pas de merge partiel dans `main` si le train est conçu comme autonome ;
- réconciliation avec le `main` réel à la fin ;
- tests ciblés puis suite pertinente ;
- migrations additives et compatibles ;
- permissions serveur ;
- CI verte avant intégration ;
- aucune suppression/affaiblissement de test pour obtenir du vert.

Pour les trains parallèles, la règle supplémentaire est la **propriété claire des surfaces** : Q/R ne refont pas le frontend D/O et inversement ; M8 possède l'assemblage global Accueil/Discover/Journey/Occurrence.

Chaque train documente son état réel, ses SHA/checkpoints et ses limites dans sa documentation d'implémentation ; cette roadmap conserve la cible stable.

## 18. Coordination avec Makolo Mature et le programme mobile

La colonne vertébrale de clôture est définie dans [`mature-program-roadmap.md`](mature-program-roadmap.md).

Ordre de référence :

```text
M1–M6 + P
     │
     ├───────────────┐
     ▼               ▼
Q → R               D → O
     \               /
      \             /
       └── M8-PRE ─┘   (audit/contrats en parallèle)
              ↓
             M7 — Interoperability / Connections / Extensions
              ↓
             M8 — Mature Web Experience
              ↓
             M9 — Hardening & Quality Gate
              ↓
            M10 — Production Readiness & Mobile Handoff
              ↓
           A1→A4 — Mobile natif

U — Intelligence cumulative : hors chemin critique.
```

M7 vient **après stabilisation des grandes capacités internes R et O** afin que Connections, Actions et Extensions exposent des contrats déjà mûrs au lieu de figer trop tôt une plateforme d'interopérabilité autour d'un Makolo encore en construction.

M8-PRE peut commencer avant cette convergence : son rôle est d'auditer et stabiliser les contrats d'expérience nécessaires à M8, pas de refaire le frontend global en parallèle.

M8 reste le **gate d'assemblage**. Il consomme les capacités structurantes du premier web Mature et applique les principes [`mature-experience-principles.md`](mature-experience-principles.md) : séparation Accueil/Discover, Sensory Discovery, No Orphan Media, Bounded Exploration et Action Rituals.

U reste non bloquant et peut mûrir avec les données réelles après la Release Candidate.

Les capacités réellement spécifiques au device — push natif, biométrie, caméra/scanner natif, share sheet, contacts système, GPS background, geofencing, widgets, Live Activities, background tasks et protocole scanner offline — restent dans le programme A. Les règles métier qu'elles consomment restent côté backend Makolo.