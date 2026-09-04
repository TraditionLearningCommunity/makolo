# Makolo — Evolution Blueprint

## Makolo Mature → Makolo Mobile → Makolo Intelligence Kernel → Makolo Agent

> **Statut : proposition d’architecture à valider.**
>
> Ce document ne remplace pas `makolo-domain-blueprint.md`, `mature-program-roadmap.md`, `strategic-action-roadmap.md`, `mature-experience-principles.md` ni `intelligence-discover-program.md`. Il propose une lecture d’évolution au-dessus de ces contrats : terminer **Makolo Mature**, construire **Makolo Mobile** comme client natif actif, étendre la fondation `intelligence` vers un **Makolo Intelligence Kernel**, puis ajouter progressivement **Makolo Agent** par spécialisations.
>
> Le code, les migrations, les tests et le `main` courant restent la vérité sur ce qui est effectivement livré.

**Snapshot de référence : 4 septembre 2026.**

---

## 1. Décision de produit et d’architecture

Makolo ne doit pas abandonner ce qui a déjà été construit pour « devenir une IA ».

La trajectoire proposée est cumulative :

```text
Makolo Mature
    ↓
Makolo Mobile
    ↓
Makolo Intelligence Kernel
    ↓
Makolo Agent
    ↓
Agents / compétences spécialisés
```

Chaque étage conserve le précédent et l’augmente.

- **Makolo Mature** est le réseau d’action fiable, déterministe et exploitable sans LLM.
- **Makolo Mobile** est le client natif qui apporte présence ambiante, capacités OS, capteurs, actions locales et offline contrôlé sans déplacer la vérité métier hors du backend.
- **Makolo Intelligence Kernel** est la couche transverse qui reçoit les observations du monde, le contexte Makolo, la mémoire autorisée et les capacités disponibles, puis fournit perception, contexte, raisonnement, planification, vérification et routage d’outils.
- **Makolo Agent** est le comportement agentique visible dans l’expérience : Makolo observe, comprend, propose, prépare, agit dans des limites explicites, vérifie et se réajuste.
- Les **spécialisations** viennent ensuite : bourses, emploi, événements/concerts, voyage, opérations, services, etc. Elles n’ont pas chacune leur propre plateforme IA ; elles utilisent le même Kernel avec des politiques, sources, outils et évaluateurs spécialisés.

La séparation fondamentale reste :

> **Le cœur Makolo possède les vérités. L’intelligence interprète le contexte. L’agent orchestre des actions autorisées.**

---

## 2. Ce qui ne change pas

Le principe architectural central reste :

> **« Event est une verticale. Activity est le noyau. »**

Les vérités canoniques restent dans leurs domaines propriétaires : Profile, Space, Group, Geography, Activity, Occurrence, Journey, Requirements, Access, Capacity, Commerce, Payment, Trust, Authorization, Notifications, Automation, etc.

Makolo Agent ne doit pas introduire un second modèle parallèle de :

```text
Profile
participant
Activity
Occurrence
Journey
Requirement
Place
Capacity
Price
Payment
Access
Permission
Status
Readiness
Proof
```

Le même invariant doit s’appliquer aux futurs agents spécialisés :

> **une spécialisation compose le cœur Makolo ; elle ne le recrée pas.**

---

## 3. Les quatre couches

| Couche | Rôle | Source de vérité | Valeur principale |
|---|---|---|---|
| **Makolo Mature** | Réseau d’action, préparation, accès, opérations, confiance | Backend et domaines canoniques | Fiabilité métier |
| **Makolo Mobile** | Présence native et interaction avec le monde physique | Backend Makolo ; état local borné | Proximité, capteurs, ambient, offline |
| **Makolo Intelligence Kernel** | Perception, contexte, mémoire, raisonnement, outils, vérification | Ne possède pas la vérité métier | Intelligence transverse |
| **Makolo Agent** | Boucle autonome bornée orientée objectif | Agit via services canoniques | Proactivité et accomplissement |

Ces couches ne sont pas quatre applications différentes pour l’utilisateur. Elles correspondent à quatre niveaux d’aptitude du même Makolo.

---

# PARTIE I — MAKOLO MATURE

## 4. Makolo Mature : le système fiable avant l’agent

Makolo Mature doit être un produit complet **backend + web + API**, même si aucun provider IA n’est configuré et même si l’application mobile n’existe pas encore.

Il porte notamment :

```text
Profile / Space / Group
Activity / Occurrence
Journey / JourneyRequest
Requirements / Readiness
Forms / Resources / Personal Assets
Trust / Proof / Action Memory
Capacity / Commerce / Payment
Access / AccessCredential / AccessUse
Notifications / Automation / Domain Events
Social Action Network
Spatiotemporal Intelligence
Preparation
Dossier / Project / Collaboration
Operations
Interoperability / Connections / Extensions
```

Makolo Mature répond déjà à des questions qui seront centrales pour l’agent :

```text
Que cherche la personne à accomplir ?
Qu’est-ce qui est prêt ?
Qu’est-ce qui manque ?
Qu’est-ce qui bloque ?
Quelle est la prochaine action ?
Qui peut agir ?
Au nom de qui ?
Pour quel bénéficiaire ?
Qu’est-ce qui a changé ?
Qu’est-ce qui peut être réutilisé ?
```

Le réseau d’action constitue donc le **world model métier** de Makolo Agent.

### 4.1 Résilience essentielle

Makolo Mature doit rester utilisable si :

- aucun modèle n’est disponible ;
- un provider IA est en panne ;
- Internet est partiellement inaccessible ;
- un connecteur externe est révoqué ;
- une observation externe est stale ou contradictoire.

L’IA augmente Makolo ; elle ne doit pas rendre le produit fragile.

---

## 5. Fondations agentiques déjà présentes

Le `main` courant possède déjà plusieurs briques qu’il faut **réutiliser plutôt que recommencer**.

### 5.1 Intelligence Foundation

Le programme Intelligence & Discover a déjà établi une app transverse `intelligence` avec :

- capabilities provider-neutral ;
- gateway ;
- registry et routing ;
- providers configurables ;
- health / timeout / fallback ;
- structured output ;
- telemetry privacy-safe ;
- fonctionnement provider-free.

Cette fondation doit devenir un composant du futur **Intelligence Kernel**. Le Kernel ne doit pas être une deuxième infrastructure provider concurrente.

### 5.2 Action Memory et Trusted Reuse

Makolo possède déjà une mémoire d’action capable de retrouver des candidats issus de la bibliothèque personnelle, d’anciens JourneyArtifacts et de Proofs, en tenant compte de provenance, fraîcheur, sensibilité et confirmation.

Le futur Kernel doit composer cette mémoire ; il ne doit pas créer un `AgentProfileMemory` qui recopierait les mêmes faits.

### 5.3 Prepared Start / Contextual NextAction / Proactive Preparation

Le train R fournit déjà une première forme de comportement intelligent déterministe :

```text
contexte actuel
→ projection
→ prochaine action
→ changement matériel
→ réévaluation
→ notification utile
```

C’est une préfiguration directe de la boucle agentique.

### 5.4 Domain Events + Automation

Domain Events et Automation constituent déjà le système nerveux interne. Le futur agent doit s’y raccorder plutôt que créer une deuxième infrastructure de scheduler et de déclencheurs.

### 5.5 Sources externes structurées

Les Opportunities possèdent déjà des notions de source, contrôle de source, provenance, état de changement et révision. Cela fournit un exemple concret du principe :

> **observation externe ≠ vérité canonique.**

---

# PARTIE II — MAKOLO MOBILE

## 6. Makolo Mobile n’est pas un simple écran plus petit

Le programme mobile existant établit une règle forte :

> **Le backend Makolo décide. Le mobile présente, orchestre et utilise les capacités du téléphone.**

Makolo Mobile ne « refait » pas Makolo. Il devient un **nœud natif du réseau d’action**.

### 6.1 A1 — Application Makolo

A1 fournit le client natif :

```text
navigation
auth
API client
state management
secure storage
design system
deep links
error handling
basic caching
```

Il consomme les contrats Mature et ne réimplémente pas Readiness, permissions, Payment state, Access validity, Hazards ou ranking.

### 6.2 A2 — Native Capabilities

Le téléphone apporte des capacités que le web ne possède pas de la même manière :

```text
push natif
biométrie locale
caméra / scanner
share sheet
contacts consentis
localisation native
geofencing
voice / intents
haptique
```

Ces capacités deviennent plus tard des **capteurs et actionneurs** du Kernel, toujours avec consentement et policy.

### 6.3 A3 — Ambient Makolo

Makolo peut devenir présent sans exiger l’ouverture permanente de l’application :

```text
widgets
lock screen
Live Activities / équivalents
notifications contextuelles
```

Exemples :

```text
Tout est prêt.
Partez maintenant.
Votre entrée est désormais Porte B.
Une place vient de se libérer.
Une exigence de votre démarche a changé.
```

Le mobile affiche une projection calculée par Makolo ; il n’invente pas sa propre vérité.

### 6.4 A4 — Operations & Offline R&D

Le téléphone devient aussi un nœud d’exécution terrain : scanner offline borné, données participant nécessaires hors ligne, background sync et réconciliation.

Le backend reste la source de vérité ; aucune stratégie naïve `last write wins` pour Access ou Payment.

---

## 7. Le mobile comme périphérie sensorielle de Makolo

Une fois le Kernel introduit, le mobile peut alimenter Makolo en signaux autorisés :

```text
heure locale
géographie ponctuelle
mouvement / proximité lorsque légitime
caméra / document fourni
scan
notification interaction
calendrier connecté
contacts explicitement consentis
intent/voice explicite
état offline / connectivité
```

Mais :

- pas de tracking permanent par défaut ;
- pas de collecte « parce que le téléphone le permet » ;
- pas de transformation implicite d’un signal en vérité métier ;
- pas d’accès à une donnée externe sans Connection/consentement/permission lorsqu’ils sont requis.

Le mobile rend Makolo **plus proche du monde**, pas plus intrusif.

---

# PARTIE III — MAKOLO INTELLIGENCE KERNEL

## 8. Rôle du Kernel

Le Makolo Intelligence Kernel est la **couche transverse qui reçoit et organise tout ce qui est nécessaire au raisonnement agentique**.

Il doit réunir :

```text
faits canoniques Makolo
projections Readiness / NextAction
Action Memory
Domain Events
observations Internet
sources officielles / APIs
Connections autorisées
signaux mobile consentis
temps / espace / hazards
état des outils et providers
objectif utilisateur courant
contexte d’autorité
```

Le Kernel ne devient pas un nouveau bounded context métier universel.

Il fournit des primitives d’intelligence et d’orchestration aux domaines et aux futurs agents spécialisés.

---

## 9. Architecture cible du Kernel

```text
                    MONDE EXTÉRIEUR
     Web · APIs · institutions · providers · partenaires
                         │
                         ▼
              ┌─────────────────────┐
              │     PERCEPTION      │
              │ search/fetch/watch  │
              │ extract/connectors  │
              └──────────┬──────────┘
                         │ observations
                         ▼
              ┌─────────────────────┐
              │ OBSERVATION LAYER   │
              │ source/provenance   │
              │ freshness/confidence│
              │ sensitivity/scope   │
              └──────────┬──────────┘
                         │
          ┌──────────────┼──────────────────┐
          │              │                  │
          ▼              ▼                  ▼
   MAKOLO CORE      MOBILE SIGNALS     ACTION MEMORY
   + Domain Events  + device context   + user context
          │              │                  │
          └──────────────┼──────────────────┘
                         ▼
              ┌─────────────────────┐
              │  CONTEXT BUILDER    │
              │   state at time t   │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │ REASONER / PLANNER  │
              │ models + strategies │
              └──────────┬──────────┘
                         │ proposal
                         ▼
              ┌─────────────────────┐
              │ POLICY / CONSENT    │
              │ AUTHORIZATION GATE  │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │   TOOL GATEWAY      │
              │ canonical services  │
              │ external actions    │
              └──────────┬──────────┘
                         ▼
                 ACTION / RESULT
                         │
                         ▼
              ┌─────────────────────┐
              │ VERIFIER / FEEDBACK │
              └──────────┬──────────┘
                         │
                         └──────────────► new context
```

---

## 10. Les composants du Kernel

### 10.1 Perception

Makolo acquiert des « yeux et oreilles » :

- recherche Web ;
- lecture/fetch de sources ;
- APIs ;
- feeds ;
- documents ;
- sources officielles ;
- providers ;
- services connectés ;
- signaux device ;
- change detection.

La perception découvre et observe. Elle ne modifie pas directement le cœur métier.

### 10.2 Observation Layer

Le Kernel a besoin d’un contrat commun pour décrire ce qui a été observé, sans décider trop tôt qu’il faut créer un modèle Django universel.

Conceptuellement :

```text
subject / entity candidate
source
source_type
observed_at
source_timestamp
freshness
confidence
provenance
sensitivity
scope
fingerprint
raw reference
```

Invariant :

> **Observation ≠ Fact.**

Une observation peut être vraie, stale, contradictoire, incomplète ou mal résolue. Les domaines propriétaires décident quand et comment elle devient une révision, un fait, une alerte ou une action.

### 10.3 Context Builder

Le Context Builder produit un état borné et explicable pour une situation donnée :

```text
actor
viewer
controller
subject
beneficiary
active Space / authority context
current goal / intent
relevant Journeys / Dossiers
Readiness / NextAction
relevant Action Memory
recent changes
current time / place
external observations
available tools
consent / permissions
```

Le modèle ne doit pas recevoir « toute la base ».

### 10.4 Memory

Le Kernel distingue :

- **mémoire métier canonique** : domaines Makolo ;
- **Action Memory** : capital réutilisable déjà défini ;
- **mémoire de travail** : état nécessaire à l’exécution agentique en cours ;
- **mémoire cognitive éventuelle** : préférences, corrections, stratégies déjà essayées, uniquement si leur persistance est explicitement justifiée, auditable et contrôlable par l’utilisateur.

Ne pas créer de profil psychologique opaque ou de shadow profile.

### 10.5 Reasoner / Planner

Le Reasoner transforme contexte + objectif en hypothèses et actions proposées :

```text
comprendre
comparer
classer
résumer
planifier
chercher une information manquante
choisir un outil
réévaluer après résultat
```

Le Reasoner est probabiliste. Il ne possède aucune autorité métier implicite.

### 10.6 Policy / Consent / Authorization Gate

Avant toute action :

```text
actor autorisé ?
subject accessible ?
Mandate / Permission suffisant ?
Connection autorisée ?
scope externe suffisant ?
consentement requis ?
donnée sensible nécessaire ?
action réversible ?
confirmation utilisateur requise ?
```

Le LLM ne contourne jamais cette couche.

### 10.7 Tool Gateway

Les outils sont les actionneurs de l’agent :

```text
search
fetch
compare
extract
notify
draft
prepare
start a canonical workflow
call provider capability
invoke external action
```

Pour modifier Makolo : **outil → service du domaine propriétaire**.

Jamais :

```text
LLM → ORM direct → vérité métier
```

### 10.8 Verification / Evaluation

Le Kernel doit vérifier les résultats avec les meilleurs oracles disponibles :

- validation de schema ;
- règles déterministes ;
- tests ;
- source primaire ;
- statut canonique ;
- comparaison avant/après ;
- confirmation utilisateur ;
- score métier explicable lorsqu’un domaine le définit.

La capacité à vérifier est ce qui permet l’autonomie de longue durée sans transformer chaque hallucination en action.

### 10.9 Triggers et boucle

Le Kernel doit réutiliser :

```text
Domain Events
Automation / Autopilot
deferred jobs existants
notifications
external change events
```

pour réveiller un raisonnement seulement lorsqu’un signal pertinent apparaît.

Le modèle n’a pas besoin de tourner en permanence pour chaque utilisateur.

---

## 11. Données froides, tièdes et chaudes

### 11.1 Données froides / stables

Faits canoniques relativement durables :

```text
Profile
Space
Activity
Journey
Proof
Payment
Access
Requirement publié
```

### 11.2 Données tièdes / dérivées

Projections recalculables :

```text
Readiness
NextAction
Prepared Start
recommendation
Operational Readiness
```

### 11.3 Données chaudes

Observations à durée de validité courte :

```text
source Web modifiée
disponibilité
prix externe
trafic
météo
horaire courant
position ponctuelle
nouvelle Opportunity
deadline externe modifiée
état live d’une Occurrence
```

Makolo doit savoir **quand** une donnée a été observée, d’où elle vient, combien de temps elle reste pertinente et si elle peut influencer une décision.

---

## 12. Conscience situationnelle Makolo

Dans ce document, « conscience » signifie **conscience situationnelle opérationnelle**, pas une affirmation de sentience.

À un instant `t`, Makolo doit pouvoir reconstruire un état tel que :

```text
Qui suis-je en train d’aider ?
Dans quel contexte d’autorité ?
Qu’essaie cette personne ou ce Space d’accomplir ?
Qu’est-ce que Makolo sait déjà ?
Qu’est-ce que le monde vient de signaler ?
Qu’est-ce qui a changé depuis la dernière observation ?
Qu’est-ce qui est certain, incertain ou stale ?
Qu’est-ce qui manque ?
Qu’est-ce qui est urgent ?
Qu’est-ce que Makolo peut préparer ?
Qu’est-ce qu’il peut exécuter ?
Qu’est-ce qui exige une confirmation humaine ?
```

On peut résumer :

```text
Situational Awareness
= Identity
+ Goal
+ Memory
+ World
+ Time
+ Space
+ Change
+ Uncertainty
+ Permissions
+ Available Actions
```

---

# PARTIE IV — MAKOLO AGENT

## 13. Quand le Kernel devient Agent

Le Kernel fournit les primitives. Makolo Agent apparaît lorsqu’on ferme la boucle :

```text
Goal
  ↓
Observe
  ↓
Understand
  ↓
Plan
  ↓
Act
  ↓
Verify
  ↓
Update context
  └──────────────→ repeat
```

Le passage important n’est donc pas « ajouter un chat ».

C’est :

> **Makolo peut poursuivre un objectif à travers plusieurs étapes, en utilisant des outils autorisés, en vérifiant les résultats et en s’arrêtant aux frontières qui exigent l’utilisateur.**

---

## 14. Échelle d’autonomie

| Niveau | Exemple | Confirmation |
|---|---|---|
| **Observer** | « La source officielle a changé. » | Non |
| **Comprendre** | « La deadline a avancé de 5 jours. » | Non |
| **Conseiller** | « Cette démarche devient prioritaire. » | Non |
| **Préparer** | Préremplir, réunir les pièces, produire un brouillon | Selon sensibilité |
| **Agir réversiblement** | Sauvegarder, classer, créer un draft, planifier une veille | Policy |
| **Agir avec impact** | Soumettre, réserver, envoyer à un tiers | Oui par défaut |
| **Décision critique** | Paiement final, Permission, Mandate, Access, identité, validation réglementaire | Le domaine déterministe / humain reste autorité |

L’autonomie doit être progressive, mesurable et révocable.

---

## 15. Agents spécialisés

Une fois le Kernel suffisamment stable, Makolo peut recevoir des spécialisations.

Le principe est :

```text
Specialized Agent
= Kernel
+ Domain Playbook
+ Specialized Sources
+ Specialized Tools
+ Specialized Policies
+ Specialized Evaluators
```

et non :

```text
Specialized Agent
= nouvelle plateforme
+ nouvelle base utilisateur
+ nouvelle mémoire
+ nouvelles permissions
```

### 15.1 Scholarship / Opportunity Agent

Comprend notamment :

```text
éligibilité
institution
programme
deadline
nationalité
niveau académique
documents
financement
application process
source officielle
```

Il compose Opportunity, Requirements, Prepared Start, Action Memory, Trusted Reuse, Journey et Notifications.

### 15.2 Events / Concert Agent

Comprend notamment :

```text
artiste / type d’Activity
Occurrence
lieu
horaire
billetterie / Offer
Capacity
Access
mobilité
amis / partage
jour J
```

Il compose Activity/Occurrence, Discovery, Commerce, Access, M6, O et Social/Sharing.

### 15.3 Travel / Mobility Agent

Comprend notamment :

```text
origine / destination
horaire
route / transport
risque
météo / trafic
réservation
documents
correspondances
arrival window
```

Il compose Geography, Journey, Activity/Occurrence, M6, providers, Access/Commerce lorsque pertinents.

### 15.4 Operations Agent

Comprend l’exécution terrain : Operational Readiness, Placement, AccessUse, Scanner, Capacity, Queue/Flow et anomalies opérationnelles.

Il peut expliquer et coordonner ; il ne décide pas arbitrairement qu’un Access invalide devient valide.

---

## 16. Orchestration des spécialisations

L’utilisateur ne devrait pas être obligé de choisir « quel agent » utiliser.

Pour lui, c’est toujours **Makolo**.

Conceptuellement :

```text
User intent / event
        ↓
Makolo Agent Supervisor / Router
        ↓
┌──────────────┬──────────────┬──────────────┐
│ Scholarship  │ Events       │ Travel       │ ...
│ competence   │ competence   │ competence   │
└──────────────┴──────────────┴──────────────┘
        ↓
Shared Kernel + canonical Makolo tools
```

Les spécialisations peuvent être des agents distincts, des policies, des toolsets ou des stratégies différentes utilisant le même modèle. La séparation logique doit précéder une multiplication physique de runtimes.

---

# PARTIE V — EXPÉRIENCE UTILISATEUR

## 17. Aucun « onglet IA » obligatoire

La transformation doit être visible dans **l’expérience**, pas nécessairement dans la navigation.

Les surfaces actuelles restent : Accueil/Cockpit, Discover, Réseau, Activities, Journeys, Profil, consoles Space, etc.

### Accueil

Avant :

```text
Vos démarches
Vos activités
Vos notifications
```

Avec Agent :

```text
2 choses ont changé depuis hier.
Votre dossier X peut maintenant avancer.
Une nouvelle possibilité correspond à votre objectif.
Makolo a déjà préparé les éléments réutilisables.
```

### Discover

Avant : recherche et recommandations.

Avec Agent : nouvelles possibilités détectées, contexte chaud, source/fraîcheur, raisons personnalisées et capacité à préparer l’action.

### Journey

Avant : étapes et Readiness.

Avec Agent :

```text
Makolo a préparé 6 éléments.
1 confirmation est nécessaire.
Cette exigence a changé.
La prochaine action la plus utile est maintenant X.
```

### Activity / Occurrence

Avant : fiche + contexte.

Avec Agent :

```text
Départ recommandé : 17:52.
Le trafic a changé.
Votre Access est prêt.
La porte vient de changer.
Makolo vous préviendra au bon moment.
```

La navigation reste familière ; Makolo devient vivant.

---

## 18. Réseaux sociaux et données externes utilisateur

Le fait qu’une information existe publiquement ou qu’un utilisateur ait un compte sur un réseau social ne constitue pas automatiquement une autorisation à l’aspirer.

Makolo doit privilégier :

```text
Connection explicitement autorisée
API officielle / mécanisme supporté
import demandé par l’utilisateur
source publique légalement et techniquement exploitable
```

Distinguer :

```text
observé
déclaré
importé
confirmé
vérifié
prouvé
expiré
```

Un profil externe peut proposer un **candidate fact** ; il ne devient pas automatiquement Proof, Permission, éligibilité ou vérité canonique.

L’utilisateur doit pouvoir comprendre la provenance, corriger une interprétation et révoquer une Connection.

---

# PARTIE VI — INVARIANTS DE SÉCURITÉ ET DE CONFIANCE

## 19. Invariants non négociables

1. **Canonical Core > Intelligence.** Le cœur décide ; l’intelligence propose/interprète.
2. **Observation ≠ Fact.** Toute donnée chaude conserve provenance et fraîcheur.
3. **No direct ORM for agents.** Les actions passent par les services propriétaires.
4. **No implicit permission.** Agent, modèle, extension ou Connection ne créent aucune autorité implicite.
5. **Consent before external personal data.** Minimisation et scope avant accès.
6. **Provider-neutral.** Le produit ne dépend pas d’un fournisseur unique.
7. **Graceful degradation.** Makolo reste utile sans Agent.
8. **Structured output + validation.** Les sorties utilisées par le produit sont validées.
9. **Sensitive data minimization.** Pas de prompt/réponse brute sensible dans les logs par défaut.
10. **Bounded autonomy.** Les actions à impact fort sont bornées et confirmées selon policy.
11. **Explainability where action matters.** Source, raison et changement doivent pouvoir être expliqués.
12. **No shadow social-credit profile.** Pas de score humain global ou de profil psychologique opaque.

---

# PARTIE VII — TRAJECTOIRE DE LIVRAISON

## 20. Séquencement recommandé

Le séquencement reste volontairement conservateur : on ne met pas l’agent avant un produit stable.

### Étape 1 — Terminer Makolo Mature

```text
M7
→ M8
→ M9
→ M10
```

Objectif de sortie : produit backend/web/API complet, durci, observable et prêt pour mobile.

### Étape 2 — Construire Makolo Mobile

```text
A1 — Application
A2 — Native Capabilities
A3 — Ambient Makolo
A4 — Operations & Offline R&D
```

Le mobile doit d’abord être excellent comme client de Makolo Mature.

### Étape 3 — Élever l’Intelligence Foundation en Kernel

Ordre conceptuel proposé, à nommer officiellement seulement après audit :

```text
Kernel contracts
→ Perception / Observation
→ Context Builder
→ Agent working memory
→ Reasoning / Planning
→ Tool Gateway
→ Policy / Consent gate
→ Verification / Evaluation
→ event-driven execution
```

Ne pas créer tous les modèles à l’avance. Chaque persistance doit être justifiée par un besoin réel et par l’absence d’un domaine canonique existant.

### Étape 4 — Makolo Agent généraliste borné

Premier objectif : un Makolo capable d’utiliser plusieurs outils communs et plusieurs domaines, pas encore un spécialiste parfait.

Exemples :

```text
« Qu’est-ce qui a changé ? »
« Qu’est-ce qui compte maintenant ? »
« Prépare ce que tu peux. »
« Cherche ce qui manque. »
« Surveille ce qui peut modifier ma prochaine action. »
```

### Étape 5 — Spécialisations

Ajouter ensuite les compétences par valeur réelle et vérifiabilité : Opportunity/Scholarship, Events, Travel, Operations, etc.

Chaque spécialisation doit définir :

```text
scope métier
sources légitimes
outils autorisés
données nécessaires
actions interdites
confirmation policy
évaluateurs
fallback
métriques de succès
```

---

## 21. Critères de réussite du Kernel

Le Kernel est suffisamment mature pour accueillir des agents spécialisés lorsque :

- Makolo Mature reste pleinement fonctionnel Intelligence OFF ;
- un signal externe peut être observé avec provenance/fraîcheur ;
- le Context Builder peut composer faits internes + observations pertinentes sans fuite de données ;
- le Reasoner peut proposer une action structurée ;
- toute action passe par Authorization/Policy puis par un Tool contrôlé ;
- un résultat peut être vérifié ;
- le système sait s’arrêter et demander confirmation ;
- Domain Events permettent de reprendre la boucle après un changement ;
- telemetry et audit permettent de comprendre pourquoi une action a été exécutée ;
- un nouvel agent spécialisé peut être ajouté sans créer une nouvelle mémoire utilisateur, une nouvelle permission ou un nouveau système de providers.

---

## 22. Non-objectifs

Cette trajectoire ne vise pas à :

- prouver que Makolo est sentient ;
- remplacer l’application par une conversation ;
- créer un chatbot comme nouvelle homepage ;
- surveiller les utilisateurs en permanence ;
- aspirer les réseaux sociaux sans consentement ou contrat légitime ;
- donner au LLM l’autorité sur Payment, Permission, Mandate, Access ou identité ;
- créer un agent par verticale avant le Kernel commun ;
- déplacer les vérités canoniques vers une vector database ;
- rendre Makolo dépendant d’un provider unique ;
- abandonner le réseau d’action Mature.

---

## 23. Questions d’architecture à décider avant implémentation du Kernel

Ces points doivent faire l’objet d’un audit spécifique au moment de démarrer le programme :

1. Quelle partie du contrat d’observation doit être persistée, et dans quel domaine ?
2. Quelle mémoire cognitive est réellement utile au-delà d’Action Memory ?
3. Où placer le runtime d’orchestration sans dupliquer `automation` et `intelligence` ?
4. Quel contrat commun d’outil peut envelopper les services canoniques sans exposer l’ORM ?
5. Quelle policy de confirmation pour les actions externes ?
6. Quelles données mobile peuvent être utilisées comme contexte, avec quelle rétention ?
7. Comment représenter source, confiance, fraîcheur et contradictions ?
8. Comment évaluer objectivement chaque agent spécialisé ?
9. Comment sandboxer les outils et borner coût, temps, retries et appels réseau ?
10. Comment rendre visibles à l’utilisateur les actions de Makolo et leur provenance sans transformer l’UX en console technique ?

---

## 24. Scénario cible de bout en bout

Exemple futur : un utilisateur cherche implicitement à financer ses études.

```text
1. Une source officielle publie une nouvelle bourse.
2. Perception détecte la source.
3. Observation Layer conserve provenance, date et fingerprint.
4. Le domaine Opportunity résout/déduplique et publie la vérité canonique selon ses règles.
5. Domain Event signale la nouvelle Opportunity.
6. Kernel identifie les Profiles pour lesquels le changement est pertinent selon des contrats autorisés.
7. Context Builder compose Profile + Goals + Action Memory + Requirements + lieu/temps utiles.
8. Scholarship competence évalue ce qu’il faut rechercher et expliquer.
9. Prepared Start détermine ce qui est déjà prêt sans demander au LLM d’inventer une éligibilité.
10. Makolo prépare ce qui est réutilisable.
11. Une action sensible manque : confirmation utilisateur.
12. L’Accueil, Discover et la Journey existants reflètent le nouvel état.
13. Si la source change, la boucle se réactive.
```

Pour l’utilisateur, aucune nouvelle architecture n’est visible. Il voit seulement :

> **« Une possibilité pertinente vient d’apparaître. Vous avez déjà une grande partie de ce qu’il faut. Makolo a préparé ce qu’il peut ; il reste deux décisions à prendre. »**

---

## 25. Formule de synthèse

```text
Makolo Mature
= réseau d’action + vérités canoniques

Makolo Mobile
= Makolo Mature + présence native + capteurs/actionneurs device

Makolo Intelligence Kernel
= Mature + Mobile context + perception + mémoire + reasoning + tools + verification

Makolo Agent
= Kernel + boucle observe/plan/act/verify + autonomie bornée

Specialized Agent
= Makolo Agent + playbook métier + sources + outils + policy + évaluateurs
```

La cible n’est pas de transformer Makolo en « application IA ».

> **La cible est que Makolo reste le réseau d’action, mais devienne progressivement capable de voir le monde, comprendre la situation de l’utilisateur, préparer ce qui peut l’être et agir utilement au bon moment.**

---

## 26. Relation avec les documents existants

Ce blueprint proposé doit rester compatible avec :

- `docs/architecture/makolo-domain-blueprint.md` — domaines et frontières canoniques ;
- `docs/architecture/strategic-action-roadmap.md` — réseau d’action, Prepared Start, Proactive Preparation, Proven Paths, opérations ;
- `docs/architecture/mature-program-roadmap.md` — clôture Mature et programme mobile A1–A4 ;
- `docs/architecture/mature-experience-principles.md` — expérience Accueil/Discover et Action Rituals ;
- `docs/architecture/intelligence-discover-program.md` — fondation `intelligence`, provider-neutral, fallback et structured output ;
- `docs/architecture/domain-events-automation.md` — système événementiel et automation ;
- `docs/architecture/authorization-boundaries.md` — frontières d’autorisation ;
- `docs/architecture/spatiotemporal-intelligence.md` — temps, espace, hazards et providers ;
- `docs/operations-runbook.md` — exploitation réelle.

### État constaté au snapshot

Le `main` consulté le 4 septembre 2026 contient déjà l’Intelligence Foundation/Discover 2027 et le train R1–R3 de préparation intelligente. Ce document propose donc une **extension de ces fondations**, pas leur remplacement.
