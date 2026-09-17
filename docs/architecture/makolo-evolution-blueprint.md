# Makolo — Evolution Blueprint

## Makolo Mature → Makolo Mobile → Makolo Intelligence Kernel → Makolo Agent

> **Statut : blueprint d’évolution canonique proposé.**
>
> Ce document ne remplace pas [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md), [`mature-program-roadmap.md`](mature-program-roadmap.md), [`strategic-action-roadmap.md`](strategic-action-roadmap.md), [`mature-experience-principles.md`](mature-experience-principles.md) ni [`intelligence-discover-program.md`](intelligence-discover-program.md). Il fixe la trajectoire cumulative au-dessus de ces contrats.
>
> Le code, les migrations, les tests et l’état GitHub du `main` courant restent la vérité sur ce qui est effectivement livré. Pour l’état opérationnel daté, voir [`current-program-status.md`](current-program-status.md).

**Snapshot d’alignement : 17 septembre 2026.**

---

## 1. Décision de produit et d’architecture

Makolo ne remplace pas son réseau d’action pour « devenir une IA ».

La trajectoire est cumulative :

```text
Makolo Mature
    ↓
Makolo Mobile
    ↓
Makolo Intelligence Kernel
    ↓
Makolo Agent
    ↓
Compétences / agents spécialisés
```

Chaque étage conserve le précédent et l’augmente.

- **Makolo Mature** est le réseau d’action fiable, déterministe et exploitable sans LLM.
- **Makolo Mobile** est le client natif actif : présence ambiante, capacités OS, capteurs, actionneurs et offline borné, sans déplacer la vérité métier hors du backend.
- **Makolo Intelligence Kernel** est la couche transverse qui reçoit les faits Makolo, observations du monde, contexte autorisé, mémoire utile et capacités disponibles, puis fournit perception, contexte, raisonnement, planification, policy, tools et vérification.
- **Makolo Agent** est le comportement en boucle : Makolo observe, comprend, planifie, agit dans des limites explicites, vérifie puis se réajuste.
- Les **spécialisations** viennent ensuite : bourses/opportunités, emploi, événements/concerts, voyage, opérations, services, etc.

La séparation fondamentale reste :

> **Le cœur Makolo possède les vérités. L’intelligence interprète le contexte. L’agent orchestre des actions autorisées.**

---

## 2. État réel au 17 septembre 2026

Le blueprint doit être lu avec l’état courant du dépôt, pas avec son ancien snapshot du 4 septembre.

### 2.1 Makolo Mature

Le dépôt documente désormais :

```text
M1 ✅ Readiness
M2 ✅ Forms / Questionnaires / Preparation Resources
M3 ✅ Presentation
M4 ✅ Trust & Quality
M5 ✅ Social Action Network
M6 ✅ Spatiotemporal Intelligence
M7 ✅ Interoperability / Connections / Extensions
G  ✅ Profil, pertinence & réseau d’action
```

Les grands trains Q/R/D/O sont largement intégrés, ainsi que l’Intelligence Foundation et les fondations Discover.

M9 a déjà été exécuté et fermé sur une base antérieure du runtime. La PR #234 rouvre M8 uniquement comme **convergence finale mobile-first de l’expérience personnelle**, sans annuler le hardening M9.

La séquence actuelle doit être comprise ainsi :

```text
M1–M7 / G / grands trains        ✅
M8 initial                        ✅
M9 hardening                      ✅ fermé sur sa base auditée
M8 convergence mobile-first       🔄 PR #234
        ↓
réconciliation post-M8
        ↓
M10 / Mature Closure actualisé
        ↓
Mobile A0/A1
```

### 2.2 Makolo Mobile

La doctrine mobile est établie, Flutter est le choix retenu et une branche `mobile/a0-phase-0-foundation` existe. Au snapshot courant, elle ne porte pas encore une implémentation Flutter distincte de `main`.

### 2.3 Intelligence Kernel

Le Kernel n’est pas encore livré comme runtime agentique complet, mais plusieurs de ses fondations existent déjà :

- app transverse `intelligence` ;
- gateway / provider registry / routing ;
- structured output / timeout / fallback / telemetry ;
- Action Memory / Trusted Reuse ;
- Domain Events ;
- Automation / Autopilot ;
- Notifications ;
- Prepared Start / NextAction / Proactive Preparation ;
- M7 Connections / Actions / Extensions ;
- Geography / Hazards / spatiotemporal context ;
- Opportunity source checks comme exemple de provenance et changement externe.

Il faut donc **élever ces fondations en Kernel**, pas créer une seconde plateforme IA.

### 2.4 Makolo Agent

Makolo Agent n’est pas encore livré comme boucle générale multi-étapes. Les comportements déterministes actuels sont des précurseurs, pas un agent général.

---

## 3. Ce qui ne change pas

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

Invariant :

> **une spécialisation compose le cœur Makolo ; elle ne le recrée pas.**

---

## 4. Les quatre couches

| Couche | Rôle | Source de vérité | Valeur principale |
| --- | --- | --- | --- |
| **Makolo Mature** | Réseau d’action, préparation, accès, opérations, confiance | Backend et domaines canoniques | Fiabilité métier |
| **Makolo Mobile** | Présence native et interaction avec le monde physique | Backend Makolo ; état local borné | Proximité, capteurs, ambient, offline |
| **Makolo Intelligence Kernel** | Perception, contexte, mémoire, raisonnement, tools, vérification | Ne possède pas la vérité métier | Intelligence transverse |
| **Makolo Agent** | Boucle autonome bornée orientée objectif | Agit via services canoniques | Proactivité et accomplissement |

Ces couches ne sont pas quatre produits distincts pour l’utilisateur. Elles décrivent quatre niveaux d’aptitude du même Makolo.

---

# PARTIE I — MAKOLO MATURE

## 5. Makolo Mature : le système fiable avant l’agent

Makolo Mature doit rester un produit complet backend + web + API même si :

- aucun modèle IA n’est disponible ;
- un provider tombe en panne ;
- Internet est partiellement inaccessible ;
- une Connection est révoquée ;
- une observation externe est stale ou contradictoire.

Le réseau d’action porte les vérités et projections permettant déjà de répondre à :

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

Le réseau d’action devient donc le **world model métier** du futur Agent.

### 5.1 Fondations déjà agent-compatibles

Makolo possède déjà :

- Readiness ;
- Requirements ;
- Personal Assets ;
- Action Memory ;
- Trusted Reuse ;
- Prepared Start ;
- Contextual NextAction ;
- Proactive Preparation ;
- Domain Events ;
- Automation ;
- Notifications ;
- Connections / Actions / Extension Platform ;
- Intelligence Foundation ;
- Geography / Hazards ;
- Trust / Proof / Credentials ;
- Dossiers / Journeys / Operations.

Le futur Kernel doit les composer, pas les recopier.

---

# PARTIE II — MAKOLO MOBILE

## 6. Le mobile n’est pas un simple écran plus petit

Règle :

> **Le backend Makolo décide. Le mobile présente, orchestre et utilise les capacités du téléphone.**

Makolo Mobile devient un nœud natif du réseau d’action.

### A0 — Foundation

Prépare le dépôt, le workspace Flutter, CI, contrats API, environnements et stratégie de tests.

### A1 — Application native

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

### A2 — Native Capabilities

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

### A3 — Ambient Makolo

```text
widgets
lock screen
Live Activities / équivalents
notifications contextuelles
```

Makolo peut ainsi accompagner l’utilisateur sans exiger l’ouverture constante de l’application.

### A4 — Operations & Offline R&D

Le téléphone peut devenir un nœud d’exécution terrain : scanner offline borné, données strictement nécessaires hors ligne, background sync et réconciliation.

Le backend reste source de vérité ; pas de `last write wins` naïf pour Access ou Payment.

---

## 7. Le mobile comme périphérie sensorielle

Avec le Kernel, le mobile peut alimenter Makolo en signaux autorisés :

```text
heure locale
géographie ponctuelle
caméra / document fourni
scan
notification interaction
calendrier connecté
contacts explicitement consentis
intent / voice explicite
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

Le Kernel est la couche transverse qui reçoit et organise tout ce qui est nécessaire au raisonnement agentique :

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
état des tools et providers
objectif utilisateur courant
contexte d’autorité
```

Il ne devient pas un bounded context métier universel.

---

## 9. Architecture cible

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

## 10. Perception et Observation

Makolo acquiert des « yeux et oreilles » via :

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

Invariant :

> **Observation ≠ Fact.**

Une observation doit conserver au minimum conceptuellement :

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

Elle peut être vraie, stale, contradictoire, incomplète ou mal résolue. Le domaine propriétaire décide quand et comment elle devient révision, fait, alerte ou action.

---

## 11. Context Builder

Le Context Builder produit un contexte borné et explicable :

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

Le modèle ne reçoit pas « toute la base ».

---

## 12. Mémoire

Le Kernel distingue :

- **mémoire métier canonique** : domaines Makolo ;
- **Action Memory** : capital réutilisable existant ;
- **working memory agentique** : état temporaire d’une exécution ;
- **mémoire cognitive éventuelle** : uniquement si sa persistance est justifiée, auditable, contrôlable et distincte des faits métier.

Pas de shadow profile psychologique opaque.

---

## 13. Reasoner / Planner

Le Reasoner peut :

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

Le modèle est probabiliste. Il ne possède aucune autorité métier implicite.

---

## 14. Policy / Consent / Authorization Gate

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

---

## 15. Tool Gateway

Les tools sont les actionneurs de l’agent :

```text
search
fetch
compare
extract
notify
draft
prepare
start canonical workflow
reuse an asset
call provider capability
invoke external action
```

Pour modifier Makolo :

```text
LLM / Planner
    ↓
Tool Gateway
    ↓
Policy / Authorization
    ↓
Canonical service
    ↓
Domain Event
```

Jamais :

```text
LLM → ORM direct → vérité métier
```

---

## 16. Verification / Evaluation

Le Kernel vérifie les résultats avec les meilleurs oracles disponibles :

- validation de schema ;
- règles déterministes ;
- source primaire ;
- statut canonique ;
- comparaison avant/après ;
- tests ;
- confirmation utilisateur ;
- évaluateurs spécialisés.

L’autonomie durable dépend davantage de la boucle **générer → vérifier → corriger** que de la seule puissance du modèle.

---

## 17. Exécution event-driven

Le Kernel doit réutiliser :

```text
Domain Events
Automation / Autopilot
notifications
deferred jobs existants
external change events
```

pour réveiller un raisonnement lorsqu’un signal matériel apparaît.

Le modèle n’a pas besoin de tourner en permanence pour chaque utilisateur.

---

## 18. Données froides, tièdes et chaudes

### Froides / stables

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

### Tièdes / dérivées

```text
Readiness
NextAction
Prepared Start
recommendation
Operational Readiness
```

### Chaudes

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

Makolo doit savoir quand une donnée a été observée, d’où elle vient, combien de temps elle reste pertinente et si elle peut influencer une décision.

---

## 19. Conscience situationnelle

Dans ce blueprint, « conscience » signifie **conscience situationnelle opérationnelle**, pas une affirmation de sentience.

À un instant `t`, Makolo doit pouvoir répondre :

```text
Qui suis-je en train d’aider ?
Dans quel contexte d’autorité ?
Qu’essaie cette personne ou ce Space d’accomplir ?
Qu’est-ce que Makolo sait déjà ?
Qu’est-ce que le monde vient de signaler ?
Qu’est-ce qui a changé ?
Qu’est-ce qui est certain, incertain ou stale ?
Qu’est-ce qui manque ?
Qu’est-ce qui est urgent ?
Qu’est-ce que Makolo peut préparer ?
Qu’est-ce qu’il peut exécuter ?
Qu’est-ce qui exige une confirmation humaine ?
```

---

# PARTIE IV — MAKOLO AGENT

## 20. Quand le Kernel devient Agent

Makolo Agent apparaît lorsqu’on ferme la boucle :

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
  └──────────────→ repeat or stop
```

Le passage important n’est pas « ajouter un chat ».

C’est :

> **Makolo peut poursuivre un objectif à travers plusieurs étapes, utiliser des tools autorisés, vérifier les résultats et s’arrêter aux frontières qui exigent l’utilisateur.**

---

## 21. Échelle d’autonomie

| Niveau | Exemple | Confirmation |
| --- | --- | --- |
| Observer | « La source officielle a changé. » | Non |
| Comprendre | « La deadline a avancé de cinq jours. » | Non |
| Conseiller | « Cette démarche devient prioritaire. » | Non |
| Préparer | Préremplir, réunir des pièces, produire un draft | Selon sensibilité |
| Agir réversiblement | Sauvegarder, classer, créer un draft, planifier une veille | Policy |
| Agir avec impact | Soumettre, réserver, envoyer à un tiers | Oui par défaut |
| Décision critique | Paiement final, Permission, Mandate, Access, identité, validation réglementaire | Domaine déterministe / humain |

L’autonomie doit être progressive, mesurable et révocable.

---

## 22. Agents / compétences spécialisés

Une spécialisation doit être :

```text
Specialized Agent
= Shared Kernel
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
+ nouvelle mémoire générale
+ nouvelles permissions implicites
```

### Scholarship / Opportunity

Compose Opportunity, Requirements, Prepared Start, Action Memory, Trusted Reuse, Journey, Notifications, Geography et sources officielles.

### Events / Concerts

Compose Activity, Occurrence, Discovery, Commerce, Capacity, Access, Operations, Sharing, Social et M6.

### Travel / Mobility

Compose Geography, Journey, Occurrence, Providers, Hazards, Access/Commerce lorsque pertinents.

### Operations

Compose Operational Readiness, Placement, AccessUse, Scanner, Capacity, Queue/Flow et anomalies opérationnelles.

L’utilisateur n’a pas besoin de choisir quel agent utiliser : pour lui, **c’est toujours Makolo**.

---

# PARTIE V — EXPÉRIENCE

## 23. Pas d’onglet IA obligatoire

La transformation doit apparaître dans l’expérience existante.

Les surfaces restent :

```text
Maintenant
Découvrir
Makolo Mark
En cours
Moi
+ surfaces contextuelles Activity / Journey / Space / Operations
```

Exemples :

### Maintenant

```text
2 choses ont changé depuis hier.
Votre dossier X peut maintenant avancer.
Makolo a déjà préparé les éléments réutilisables.
```

### Découvrir

```text
Une nouvelle possibilité a été détectée.
Source officielle vérifiée.
Voici pourquoi elle peut modifier votre trajectoire.
```

### Journey

```text
Makolo a préparé 6 éléments.
1 confirmation est nécessaire.
Cette exigence a changé.
```

### Activity / Occurrence

```text
Départ recommandé : 17:52.
Le trafic a changé.
Votre Access est prêt.
La porte vient de changer.
```

La navigation reste familière ; l’expérience devient plus vivante et proactive.

---

## 24. Données externes et réseaux sociaux

Le fait qu’une information soit publique ou qu’un utilisateur possède un compte externe ne constitue pas automatiquement une autorisation à l’aspirer.

Makolo privilégie :

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

Une donnée externe peut produire un **candidate fact** ; elle ne devient pas automatiquement Proof, Permission, éligibilité ou vérité canonique.

---

# PARTIE VI — INVARIANTS

## 25. Invariants non négociables

1. **Canonical Core > Intelligence.** Le cœur décide ; l’intelligence propose/interprète.
2. **Observation ≠ Fact.** Toute donnée chaude conserve provenance et fraîcheur.
3. **No direct ORM for agents.** Les actions passent par les services propriétaires.
4. **No implicit permission.** Agent, modèle, extension ou Connection ne créent aucune autorité implicite.
5. **Consent before external personal data.** Minimisation et scope avant accès.
6. **Provider-neutral.** Le produit ne dépend pas d’un fournisseur unique.
7. **Graceful degradation.** Makolo reste utile sans Agent.
8. **Structured output + validation.** Les sorties produit sont validées.
9. **Sensitive data minimization.** Pas de logs bruts sensibles par défaut.
10. **Bounded autonomy.** Les actions à impact fort sont bornées et confirmées selon policy.
11. **Explainability where action matters.** Source, raison et changement doivent pouvoir être expliqués.
12. **No shadow social-credit profile.** Pas de score humain global ou de profil psychologique opaque.

---

# PARTIE VII — TRAJECTOIRE DE LIVRAISON

## 26. Séquencement actuel

À partir du runtime observé le 17 septembre 2026 :

### Étape 1 — Fermer la convergence Mature

```text
PR #234 M8 mobile-first
→ merge
→ gates post-merge
→ M10 actualisé / Mobile handoff
```

M9 n’est pas à refaire comme programme complet ; ses garanties doivent être revalidées là où le runtime final M8 les touche.

### Étape 2 — Makolo Mobile

```text
A0 — foundation Flutter / repo / CI / tests
A1 — application native
A2 — native capabilities
A3 — Ambient Makolo
A4 — operations & offline
```

### Étape 3 — Élever l’Intelligence Foundation en Kernel

```text
Kernel contracts
→ Perception / Observation
→ Context Builder
→ working memory
→ Reasoning / Planning
→ Tool Gateway
→ Policy / Consent gate
→ Verification / Evaluation
→ event-driven execution
```

Ne pas créer tous les modèles à l’avance. Chaque persistance doit être justifiée par l’absence d’un domaine canonique existant.

### Étape 4 — Makolo Agent généraliste borné

Premiers objectifs possibles :

```text
« Qu’est-ce qui a changé ? »
« Qu’est-ce qui compte maintenant ? »
« Prépare ce que tu peux. »
« Cherche ce qui manque. »
« Surveille ce qui peut modifier ma prochaine action. »
```

### Étape 5 — Spécialisations

Ajouter les compétences par valeur réelle et vérifiabilité.

Chaque spécialisation définit :

```text
scope métier
sources légitimes
tools autorisés
données nécessaires
actions interdites
confirmation policy
évaluateurs
fallback
métriques de succès
```

---

## 27. Critères de réussite du Kernel

Le Kernel est suffisamment mûr pour accueillir des spécialisations lorsque :

- Makolo Mature reste fonctionnel Intelligence OFF ;
- un signal externe est observé avec provenance/fraîcheur ;
- le Context Builder compose faits internes + observations sans fuite de données ;
- le Reasoner propose une action structurée ;
- toute action passe par Authorization/Policy puis un Tool contrôlé ;
- le résultat peut être vérifié ;
- le système sait s’arrêter et demander confirmation ;
- Domain Events permettent de reprendre la boucle ;
- telemetry/audit expliquent pourquoi une action a été exécutée ;
- un agent spécialisé peut être ajouté sans créer une nouvelle mémoire utilisateur, permission ou plateforme providers.

---

## 28. Non-objectifs

Cette trajectoire ne vise pas à :

- prouver que Makolo est sentient ;
- remplacer l’application par une conversation ;
- créer un chatbot comme nouvelle homepage ;
- surveiller les utilisateurs en permanence ;
- aspirer les réseaux sociaux sans consentement ou base légitime ;
- donner au LLM l’autorité sur Payment, Permission, Mandate, Access ou identité ;
- créer un agent par verticale avant le Kernel commun ;
- déplacer les vérités canoniques vers une vector database ;
- rendre Makolo dépendant d’un provider unique ;
- abandonner le réseau d’action Mature.

---

## 29. Questions avant implémentation du Kernel

1. Quelle partie du contrat d’observation doit être persistée, et dans quel domaine ?
2. Quelle mémoire cognitive est réellement utile au-delà d’Action Memory ?
3. Où placer le runtime d’orchestration sans dupliquer `automation` et `intelligence` ?
4. Quel contrat Tool peut envelopper les services canoniques sans exposer l’ORM ?
5. Quelle policy de confirmation pour les actions externes ?
6. Quelles données mobile peuvent être utilisées comme contexte, avec quelle rétention ?
7. Comment représenter source, confiance, fraîcheur et contradictions ?
8. Comment évaluer objectivement chaque spécialisation ?
9. Comment sandboxer tools, coût, temps, retries et appels réseau ?
10. Comment rendre visibles actions et provenance sans transformer l’UX en console technique ?

---

## 30. Formule de synthèse

```text
Makolo Mature
= réseau d’action + vérités canoniques

Makolo Mobile
= Makolo Mature + présence native + capteurs/actionneurs device

Makolo Intelligence Kernel
= Mature + Mobile context + perception + memory + reasoning + tools + verification

Makolo Agent
= Kernel + boucle observe/plan/act/verify + autonomie bornée

Specialized Agent
= Makolo Agent + playbook métier + sources + tools + policy + evaluators
```

> **La cible n’est pas de transformer Makolo en « application IA ». La cible est que Makolo reste le réseau d’action, mais devienne progressivement capable de voir le monde, comprendre la situation de l’utilisateur, préparer ce qui peut l’être et agir utilement au bon moment.**

---

## 31. Documents liés

- [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md) — domaines et frontières canoniques ;
- [`current-program-status.md`](current-program-status.md) — snapshot opérationnel daté ;
- [`mature-program-roadmap.md`](mature-program-roadmap.md) — stream Mature et handoff mobile ;
- [`strategic-action-roadmap.md`](strategic-action-roadmap.md) — réseau d’action et capacités stratégiques ;
- [`mature-experience-principles.md`](mature-experience-principles.md) — expérience Mature ;
- [`intelligence-discover-program.md`](intelligence-discover-program.md) — Intelligence Foundation et Discover ;
- [`domain-events-automation.md`](domain-events-automation.md) — système événementiel et automation ;
- [`authorization-boundaries.md`](authorization-boundaries.md) — frontières d’autorisation ;
- [`spatiotemporal-intelligence.md`](spatiotemporal-intelligence.md) — temps, espace, hazards et providers ;
- [`m9-hardening-quality-gate.md`](m9-hardening-quality-gate.md) — preuves M9 ;
- `docs/operations-runbook.md` — exploitation réelle.
