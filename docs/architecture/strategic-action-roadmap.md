# Makolo — Strategic Action Roadmap

> **Statut : canonique pour la cible produit/architecture après le noyau Mature.** Ce document complète [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md). Il répertorie les capacités stratégiques retenues, explique comment elles se composent avec les domaines canoniques et les regroupe en trains d'implémentation. Il **ne décrit pas le runtime déjà livré** : le code, les migrations et les tests du `main` courant restent la vérité sur ce qui existe effectivement.

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
- une projection UX.

Les vérités canoniques restent notamment `Activity`, `Occurrence`, `Journey`, `JourneyStep`, `Requirement`, `Payment`, `Access`, `Capacity`, `Proof`, `Mandate` et les objets de leurs domaines propriétaires.

## 3. Les 18 capacités retenues

### 1. Sharing — circulation de l'action

- **Type** : extension déjà engagée.
- **Problème** : un lien partagé transmet souvent une destination, pas le contexte nécessaire pour agir.
- **Promesse** : **« Je ne t'envoie pas seulement quelque chose à regarder ; je t'envoie quelque chose sur lequel tu peux agir. »**
- **Mécanisme** : sujets explicites, contexte borné, livraisons internes/externes, reprise contrôlée ; aucun transfert implicite de Permission, Mandate, Access, Payment ou document sensible.
- **Domaines** : Activity, Occurrence, Opportunity, Journey, Notifications, puis documents selon le contrat Sharing.
- **Défensibilité** : Makolo fait circuler du contexte opérationnel structuré plutôt qu'une URL nue.
- **Train** : **P**.

### 2. Bibliothèque personnelle — capital documentaire durable

- **Type** : nouveau concept justifié par un gap du modèle actuel.
- **Problème** : CV, diplômes, certificats, pièces et justificatifs doivent être réimportés dans chaque démarche ; `JourneyArtifact` reste lié à une Journey.
- **Promesse** : **« Les documents utiles que vous choisissez de conserver sont déjà disponibles lorsque vous en avez besoin. »**
- **Mécanisme** : asset/document personnel durable, privé, versionné, avec provenance, sensibilité, contrôleur et sujet éventuel. L'utilisation dans une Journey doit produire/conserver une représentation auditable de la version réellement utilisée.
- **Domaines** : Profile, JourneyArtifact, private storage, Trust/Proof, Requirements, Sharing lorsque intégré.
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
- **Mécanisme** : projection explicable de Requirements contre Profile, Bibliothèque, Action Memory et Proofs ; aucun score opaque d'éligibilité.
- **Domaines** : Opportunity, Requirements, Readiness, Profile, Trust, Q.
- **Défensibilité** : Makolo relie ce que le monde exige à ce que l'utilisateur possède déjà.
- **Train** : **R**.

### 5. Proactive Preparation — surveiller les changements utiles

- **Type** : convergence de veille de Requirements, expirations, deadlines et faits actionnables.
- **Problème** : une démarche se bloque parce qu'un changement important est vu trop tard.
- **Promesse** : **« Makolo vous prévient quand un changement modifie réellement votre prochaine action utile. »**
- **Mécanisme** : Domain Events, Automation/Autopilot et Notifications existants ; aucune seconde infrastructure de scheduling.
- **Domaines** : Requirements, Opportunity, Journey, Bibliothèque, Payment, Capacity, Access, Automation, Notifications, M6 spatio-temporel lorsque pertinent.
- **Défensibilité** : alertes issues de faits métier structurés plutôt que de surveillance comportementale opaque.
- **Train** : **R**.

### 6. Dossier — objectif actif composé

- **Type** : nouveau concept majeur.
- **Problème** : un résultat réel peut exiger plusieurs Journeys, plusieurs personnes et des dépendances entre démarches ; une Journey géante ou des Journeys dispersées sont toutes deux mauvaises.
- **Promesse** : **« Tout ce qui doit avancer vers ce résultat se trouve dans un même contexte d'accomplissement. »**
- **Mécanisme** : composition de Journeys, bénéficiaires, collaborateurs, échéances, relations inter-Journeys et Readiness dérivée. Le Dossier ne duplique ni Step, Payment, Access, Capacity, Artifact ni Permission.
- **Domaines** : Journey, Profile/ExternalBeneficiary, Assignment, Mandate, Readiness, Activity/Opportunity et domaines enfants.
- **Défensibilité** : compréhension structurée d'un résultat composé et collectif.
- **Train** : **S**.

### 7. Projet — horizon durable

- **Type** : nouveau concept complémentaire au Dossier.
- **Problème** : certains objectifs durent des mois/années et produisent plusieurs Dossiers sans être eux-mêmes une urgence opérationnelle.
- **Promesse** : **« Gardez une direction durable sans transformer chaque objectif en Dossier permanent. »**
- **Mécanisme** : regroupement d'intentions, jalons et Dossiers ; ne pas devenir un Trello/Notion bis.
- **Domaines** : Profile, Space, Dossier et projections associées.
- **Défensibilité** : continuité entre horizon long terme et exécution concrète.
- **Train** : **S**.

### 8. Structured Handoff — responsabilité explicite

- **Type** : convergence de capacités existantes.
- **Problème** : dans une démarche collective, les blocages viennent souvent de l'incertitude sur qui doit agir et qui en a l'autorité.
- **Promesse** : **« Chacun sait ce qu'il doit faire et pourquoi il peut le faire. »**
- **Mécanisme** : JourneyAssignment/JourneyStepAssignment + Mandate/Permission. **Assignment = responsabilité ; Mandate = autorité.**
- **Domaines** : Journey, JourneyStep, Assignment, authorization, Notifications, Dossier.
- **Défensibilité** : orchestration liée à des processus métier, pas task manager générique.
- **Train** : **S**.

### 9. Collective Readiness — sommes-nous prêts ensemble ?

- **Type** : convergence Readiness + collectif.
- **Problème** : une équipe ou une famille doit comprendre son état global sans ouvrir chaque Journey ni exposer des détails sensibles.
- **Promesse** : **« Voyez ce qui bloque le collectif sans exposer inutilement les personnes. »**
- **Mécanisme** : agrégation privacy-safe de projections Readiness ; aucun `CollectiveReadinessState` persistant et aucune matérialisation massive de Journeys.
- **Domaines** : Readiness, Group, Dossier, Space, Journey, Requirements, Analytics.
- **Défensibilité** : coordination de plusieurs parcours individuels avec disclosure contrôlée.
- **Train** : **S**.

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
- **Train** : **T**.

### 13. Occurrence Live — Makolo pendant l'action réelle

- **Type** : extension majeure du noyau Activity/Occurrence.
- **Problème** : lorsque l'Activity commence, participants et opérateurs reviennent souvent au papier, Excel, messages et improvisation.
- **Promesse** : **« Quand l'action commence, Makolo montre à chacun ce qui compte maintenant. »**
- **Mécanisme** : projection temps réel selon acteur, contexte d'autorité et bénéficiaire, à partir des domaines propriétaires. Occurrence Live n'est pas une seconde base opérationnelle.
- **Domaines** : Occurrence, AccessUse, Scanner, Capacity, Assignments, Mandates, Analytics, M6 Temporal/Spatial/Hazards, futurs Queue/Placement/Checkpoint.
- **Défensibilité** : contexte partagé de l'exécution réelle, personnalisé sans dupliquer les vérités.
- **Train** : **T**.

### 14. Live Queue — attendre son tour, pas une place

- **Type** : nouveau mécanisme, distinct de la Waitlist commerciale/capacité existante.
- **Problème** : quelqu'un qui possède déjà son droit perd du temps dans une file physique ou au mauvais point de contrôle.
- **Promesse** : **« Makolo peut vous dire quand avancer et, lorsque les données le permettent, où l'attente est la plus courte. »**
- **Mécanisme** : queue opérationnelle, entrée de file, checkpoint, débit observé, no-show/expiration et estimation prudente. **Waitlist = attendre qu'une place se libère ; Live Queue = attendre son tour après avoir déjà le droit pertinent.**
- **Domaines** : Occurrence, Access, AccessUse, Capacity, Scanner, Notifications, Analytics.
- **Défensibilité** : chaque passage réel améliore la compréhension des flux suivants.
- **Train** : **T**.

### 15. Placement — où dois-je aller ?

- **Type** : nouveau mécanisme transversal.
- **Problème** : après admission, tables, sièges, salles, bus, chambres ou zones sont souvent gérés dans des feuilles parallèles.
- **Promesse** : **« Une fois admis, chacun sait immédiatement où aller. »**
- **Mécanisme** : plan/groupe/emplacement/assignment structurés, avec vocabulaire métier configurable. Placement répond **où ?** ; Capacity reste propriétaire de **combien ?**
- **Domaines** : Activity, Occurrence, Capacity, Access, Profile/beneficiary, Resources, Occurrence Live.
- **Défensibilité** : valeur forte lorsqu'il est combiné à Access et Flow.
- **Train** : **T**.

### 16. Checkpoints / Flow — prochain point de passage

- **Type** : nouveau mécanisme opérationnel.
- **Problème** : une Occurrence peut comporter plusieurs passages successifs et des goulots d'étranglement difficiles à voir.
- **Promesse** : **« Makolo vous guide vers le prochain point utile et aide l'opérateur à comprendre le flux. »**
- **Mécanisme** : checkpoints opérationnels successifs liés à l'Occurrence. Ne pas les confondre avec `JourneyStep` : Step = action d'une démarche ; Checkpoint = point de passage d'une exécution réelle.
- **Domaines** : Occurrence, Access, Queue, Capacity, Scanner, Placement, Analytics.
- **Défensibilité** : compréhension structurée des flux terrain et de leurs bottlenecks.
- **Train** : **T**.

### 17. Offline Action Pack — continuité en connectivité faible

- **Type** : extension d'expérience et de résilience.
- **Problème** : les informations essentielles peuvent devenir indisponibles précisément au moment où la connectivité se dégrade.
- **Promesse** : **« Les éléments essentiels restent disponibles dans les limites du contrat de sécurité. »**
- **Mécanisme** : paquet local borné de données nécessaires : instructions, contexte, représentation d'Access compatible, placement et documents explicitement choisis. Le vrai scanner offline reste un problème séparé plus exigeant.
- **Domaines** : Access, Occurrence, ActivityResource, Bibliothèque/JourneyArtifact, Placement.
- **Défensibilité** : fiabilité de l'expérience dans des environnements réels difficiles.
- **Train** : **T**.

### 18. Accueil contextuel — ce qui compte maintenant

- **Type** : convergence UX, pas bounded context.
- **Problème** : un accueil générique oblige l'utilisateur à chercher la prochaine action ; un feed générique optimise l'attention plutôt que l'accomplissement.
- **Promesse** : **« Ouvrez Makolo et voyez ce qui mérite votre attention maintenant, personnellement ou pour l'Espace dans lequel vous agissez. »**
- **Mécanisme** : projection hiérarchisée de Readiness/NextAction, Dossiers, Journeys, Assignments, Occurrences, Hazards M6, Notifications et opérations autorisées.
- **Domaines** : Readiness, M5/M6, Journey, Dossier, Occurrence, authorization, Notifications.
- **Défensibilité** : capacité à déterminer la prochaine action utile à partir de faits structurés.
- **Train** : **R**, puis enrichissement **T**.

## 4. Trains d'implémentation

Les 18 capacités sont regroupées en six trains stratégiques. Un train peut être développé sur des checkpoints empilés et intégré à `main` seulement lorsqu'il est complet et réconcilié avec le `main` du moment.

| Train | Intention | Capacités principales |
|---|---|---|
| **P — Sharing** | Faire circuler l'action | Sharing P1→P5 |
| **Q — Capital d'action personnel** | Ne plus recommencer | Bibliothèque, Action Memory, fondation Trusted Reuse |
| **R — Préparation intelligente** | Savoir ce qui est prêt et anticiper | Prepared Start, Proactive Preparation, Accueil contextuel |
| **S — Objectifs & collaboration** | Accomplir des objectifs composés, seul ou ensemble | Dossier, Projet, Structured Handoff, Collective Readiness |
| **T — Occurrence Operations** | Préparer et orchestrer le réel | Operational Readiness, Occurrence Live, Placement, Live Queue, Checkpoints/Flow, Offline Action Pack |
| **U — Intelligence cumulative** | Faire apprendre les actions précédentes aux suivantes | Proven Paths, Trusted Reuse avancé, analytics d'action/opérations |

### Train P

P est autonome. Les checkpoints P2, P3, etc. partent du checkpoint précédent et non du `main`. Le train complet est réconcilié puis intégré à `main` une seule fois en fin de P. Les détails de branche/PR restent des faits GitHub à vérifier au moment du travail, pas un invariant documentaire figé ici.

### Train Q

Q suit la même discipline :

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

Q reste autonome de P : il peut lire les contrats Sharing pour éviter une collision architecturale, mais ne dépend pas d'une branche P non intégrée.

### Trains R et S

Après les fondations Q, R et S peuvent avancer largement en parallèle. R exploite Requirements/Readiness/Memory ; S exploite Journey/Assignments/Mandates et introduit le contenant d'objectif composé.

### Train T

T peut préparer `Operational Readiness` et `Placement` dès que le contrat de contexte d'action est clair. Il réutilise le scanner canonique, AccessUse, Capacity, M6 spatio-temporel et les permissions existantes au lieu de reconstruire un système terrain parallèle.

### Train U

U doit être construit lorsque suffisamment de données réelles existent. Proven Paths et l'intelligence opérationnelle ne doivent pas prétendre apprendre de la démo comme s'il s'agissait d'une population représentative.

## 5. Dépendances principales

```text
P — Sharing (autonome)

Q — Capital personnel
        │
        ├──────────────┐
        ▼              ▼
R — Préparation    S — Objectifs & collaboration
        │              │
        └───────┬──────┘
                ▼
       T — Occurrence Operations
                │
                ▼
       U — Intelligence cumulative
```

Cette figure exprime les dépendances conceptuelles, pas une obligation de sérialiser toutes les branches.

## 6. Contexte d'action transversal

Makolo ne sépare pas le monde en comptes « participants » et « organisateurs ».

Pour toute action sensible ou opérationnelle, il faut pouvoir distinguer conceptuellement :

1. **Acteur** — quel Profil humain agit réellement ?
2. **Contexte d'autorité** — agit-il en son nom ou pour quel Espace/portée via ses Permissions/Mandates ?
3. **Bénéficiaire** — pour qui l'action produit-elle le résultat ?

Ces trois dimensions peuvent désigner trois sujets différents.

Une Assignment ne devient jamais une Permission. Une Membership ne devient jamais une autorité. L'interface peut proposer **Agir en mon nom** / **Pour l'Espace X**, mais le serveur revalide toujours la vraie autorité.

## 7. Projet, Dossier, Journey, Step et Occurrence

La granularité cible est :

| Question | Concept |
|---|---|
| Quelle direction durable poursuivons-nous ? | **Projet** |
| Quel résultat actif doit maintenant avancer ? | **Dossier** |
| Quelle démarche concrète suit un bénéficiaire dans un contexte Activity ? | **Journey** |
| Quelle action précise fait avancer cette Journey ? | **JourneyStep** |
| Que se passe-t-il réellement maintenant pour cette Activity ? | **Occurrence / Occurrence Live** |

Le Dossier absorbe l'ancien besoin conceptuel d'un « Action Graph/Mission composée » séparé. Les relations `requires/enables/related` entre Journeys sont un mécanisme interne du Dossier tant qu'aucun gap futur ne justifie un domaine distinct.

## 8. Capital documentaire et preuves

Trois notions restent séparées :

- **Bibliothèque** : ce que l'utilisateur choisit de conserver et gérer ;
- **Action Memory** : ce que Makolo retrouve et propose de réutiliser ;
- **Trusted Reuse** : ce qui est réellement acceptable pour un Requirement précis.

`JourneyArtifact` reste l'artefact d'une Journey. `ActivityResource` reste la ressource partagée de préparation d'une Activity/Occurrence. Une future Bibliothèque personnelle ne transforme aucun des deux en stockage générique.

La suppression ou le remplacement d'un asset source ne doit pas réécrire silencieusement l'historique d'une Journey qui l'a utilisé.

## 9. Readiness étendu sans nouveau domaine

Prepared Start, Collective Readiness et Operational Readiness sont des extensions de la philosophie de projection Readiness, pas des justifications pour créer trois nouvelles tables d'état.

- **Prepared Start** projette ce qui est déjà disponible avant le démarrage complet d'une démarche lorsque le contexte permet une évaluation légitime.
- **Collective Readiness** agrège des états autorisés sans révéler les détails individuels non nécessaires.
- **Operational Readiness** projette la préparation d'une Occurrence depuis ses faits opérationnels.

Les domaines propriétaires restent responsables des états et transitions.

## 10. Occurrence Operations

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

M6 reste propriétaire de ses projections temporelles/spatiales, hazards et ActionAdvice. T les compose au lieu de créer un second `Hazard`, ETA ou contexte de mobilité.

## 11. Accueil contextuel et M5

L'Accueil contextuel n'est pas un remplacement ni une duplication de l'Action Stream M5.

- **Action Stream M5** : projection sociale/action contextualisée déjà définie par M5.
- **Accueil contextuel** : projection privée et opérationnelle de ce qui nécessite l'attention de l'acteur maintenant.

Aucun `FeedItem` métier générique ne doit être créé pour réaliser l'Accueil contextuel.

## 12. Flywheels recherchés

### Personnel

`Journey accomplie → contexte utile conservé → Action Memory → Prepared Start → nouvelle Journey plus courte`.

### Collectif

`Journeys accomplies → blockers/délais agrégés → templates/resources améliorés → parcours suivants mieux préparés`.

### Opérationnel

`Occurrence → AccessUse/flows observés → goulots compris → Operational Readiness suivante améliorée`.

### Confiance

`fait réel → Proof → acceptation contextuelle → Requirement satisfait → étape supprimée`.

## 13. Actifs défendables

Makolo doit accumuler de la valeur dans les structures utiles à l'action, pas dans des compteurs de popularité :

- Requirements structurés et leurs révisions ;
- provenance/versions des éléments réutilisables ;
- ProofTypes et politiques d'acceptation ;
- parcours accomplis, dépendances, blockers et délais ;
- Resources/templates efficaces ;
- états de préparation explicables ;
- flux opérationnels, files et débits observés ;
- contexte d'action personnel/organisationnel.

## 14. Anti-duplication et anti-features

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
- un feed générique persistant pour l'Accueil contextuel ;
- des likes/réactions/popularité comme moteur central de la valeur Makolo ;
- une certification universelle implicite à partir d'une Proof.

## 15. Ripple

`Ripple` reste **explicitement non défini** dans cette roadmap. Aucune équipe ne doit créer un domaine, un modèle ou une responsabilité `Ripple` à partir d'une interprétation spéculative. Il pourra être intégré à cette roadmap lorsqu'une définition canonique apparaîtra dans le produit, le code ou une décision d'architecture explicite.

## 16. Discipline de livraison

Pour P, Q et les trains similaires :

- checkpoints empilés depuis le checkpoint précédent ;
- pas de merge partiel dans `main` si le train est conçu comme autonome ;
- réconciliation avec le `main` réel à la fin ;
- tests ciblés puis suite pertinente ;
- migrations additives et compatibles ;
- permissions serveur ;
- CI verte avant intégration ;
- aucune suppression/affaiblissement de test pour obtenir du vert.

Chaque train doit documenter son état réel, ses SHA/checkpoints et ses limites dans sa documentation d'implémentation ; cette roadmap conserve uniquement la cible stable.