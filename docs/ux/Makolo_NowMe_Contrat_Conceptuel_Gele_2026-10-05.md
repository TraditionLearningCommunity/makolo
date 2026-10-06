# Makolo — Now Me
## Contrat conceptuel gelé de `NowMeResponse` et de la consommation client

**Statut :** gel conceptuel de travail  
**Date :** 2026-10-05  
**Portée :** `Now Me` personnel — serveur Django / futur Molongo / client Web HTML-Tailwind / client Flutter  
**Nature du document :** contrat de conception ; ne fixe pas encore le wire JSON définitif ni l’implémentation technique  

---

# 1. Objet

Ce document fige la compréhension conceptuelle de **Now Me** avant tout chantier d’implémentation.

Il définit :

- ce qu’est une **Situation Now** ;
- ce que le serveur doit savoir et projeter ;
- ce que le client peut légitimement dériver ;
- les cardinalités des rôles ;
- les familles de valeurs sémantiques transportables ;
- les responsabilités respectives de Django, du futur seam Molongo et des clients Web/Flutter ;
- les invariants à préserver ;
- ce qui reste volontairement ouvert.

Ce document ne remplace pas les domaines propriétaires. Il organise leur projection vers Now.

Règle structurante :

```text
Le serveur fournit la Situation comprise.
Le client fournit la Situation vécue à l’écran.
```

Et :

```text
Le serveur ne produit pas l’interface.
Le client ne reconstruit pas l’écosystème.
```

---

# 2. Définition de Now Me

`Now Me` répond à :

> **Qu’est-ce qui compte maintenant pour moi ?**

Une Situation Now est une **projection UX temporaire et contextuelle** d’une réalité canonique ou d’une composition de réalités canoniques.

Elle n’est jamais :

- un nouveau modèle métier ;
- une tâche générique ;
- un doublon de Journey ;
- un doublon de Readiness ;
- un système de notifications ;
- un feed ;
- un dashboard ;
- une Card comme unité métier ;
- une copie des domaines propriétaires.

Une Situation Now doit être admissible parce qu’il existe au minimum :

```text
LEGITIMATE_RELATION
∧ PRESENT_SIGNIFICANCE
∧ CONSEQUENCE
∧ USEFUL_RESPONSE
∧ SUFFICIENT_KNOWLEDGE
```

Une Opportunity intéressante, récente ou urgente en elle-même n’entre pas automatiquement dans Now.

---

# 3. Équation de rendu

Une unité réellement rendue à l’utilisateur résulte de :

```text
Response serveur
+
contexte / état local client
+
calculs locaux sûrs
+
Presentation
=
Situation réellement vécue à l’écran
```

Donc :

```text
UNITÉ UX CANONIQUE
≠ RESPONSE SERVEUR
≠ ÉTAT LOCAL CLIENT
≠ VIEW MODEL CLIENT
```

---

# 4. Now Me — enveloppe conceptuelle

Le serveur produit conceptuellement :

```text
NOW ME RESPONSE

ACTOR_CONTEXT
→ Profile Me

VIEWER
→ Profile Me

ACTOR_ATTENTION_STATE
→ ACTIVE | CALM

SITUATIONS[]
```

Le nom `ACTOR_ATTENTION_STATE` n’est pas encore un nom wire définitif.

`CALM` signifie :

> aucune intervention, décision ou attention active n’est actuellement requise de l’acteur courant.

Cela peut coexister avec une surveillance autonome de Makolo.

Le texte :

```text
Tout est en ordre. ✓
```

reste une formulation client.

---

# 5. Situation Now — grammaire gelée

Chaque Situation contient conceptuellement :

```text
SITUATION NOW
│
├── CONTINUITY_IDENTITY
│
├── RESPONSIBILITY[]
├── AUTHORITY?
│
├── HUMAN_CONTEXT
├── SUBJECT
├── STATE
├── DELTA?
├── WHY_NOW
├── CONSEQUENCE
│
├── TURN
├── RESPONSE
│
├── HORIZON?
├── MAKOLO_PREPARATION[]
│
├── OWNER_DEPTH
│
├── KNOWLEDGE_CONTEXT
│   ├── PROVENANCE[]
│   ├── FRESHNESS
│   ├── KNOWLEDGE_STATE
│   └── CONFIDENCE?
│
├── ATTENTION
│   ├── LEVEL
│   ├── CONTINUITY_STATE
│   └── LIFECYCLE_EVENT?
│
├── BUSINESS_ACTIONS[]
└── MEDIA_BINDINGS[]
```

`EXIT_CONDITION` existe conceptuellement côté moteur/projection serveur, mais n’a pas besoin d’être transportée par défaut au client.

---

# 6. Cardinalités gelées

```text
ACTOR_CONTEXT       1
VIEWER              1

RESPONSIBILITY      0..n
AUTHORITY           0..1 projection effective

HUMAN_CONTEXT       1
SUBJECT             1
STATE               1
DELTA               0..1
WHY_NOW             1
CONSEQUENCE         1

TURN                0..1
RESPONSE            1
HORIZON             0..1
MAKOLO_PREPARATION  0..n

OWNER_DEPTH         1

PROVENANCE          0..n
FRESHNESS           1
KNOWLEDGE_STATE     1
CONFIDENCE          0..1

ATTENTION.LEVEL             1
ATTENTION.CONTINUITY_STATE  1
ATTENTION.LIFECYCLE_EVENT   0..1

BUSINESS_ACTIONS    0..n
MEDIA_BINDINGS      0..n
```

---

# 7. Portage sémantique minimal

Règle :

> **Choisir le plus petit porteur canonique suffisamment riche pour représenter honnêtement le rôle UX.**

Ne jamais composer mécaniquement tous les objets liés.

Exemple :

```text
Occurrence
→ connaît déjà son Activity parent
→ porte sa temporalité
→ peut porter ses lieux et son contexte vertical utile
```

Donc si une projection Occurrence suffisamment riche suffit :

```text
HUMAN_CONTEXT = Occurrence
```

et non :

```text
Activity + Occurrence + route + horaire
```

La composition n’est justifiée que si aucun porteur unique ne suffit honnêtement.

---

# 8. Familles de valeurs sémantiques

Now utilise cinq briques générales :

```text
OBJECT
FACT
RELATION
TRANSITION
COMPOSITION
```

Elles ne sont pas des modèles Django.

Elles expriment la nature de la valeur transportée vers le client.

---

# 9. OBJECT

Un `OBJECT` représente une réalité canonique suffisamment porteuse.

Exemples possibles selon les rôles :

```text
Profile
Space
Team
Group
Activity
Occurrence
Journey
Request
Requirement
Dossier
Project
Order
Payment
Access
Place
Conversation
ActionProposal
Waitlist
Transfer
Resource
Proof / Credential Trust projection
...
```

Un modèle existant n’est pas automatiquement admissible partout dans Now.

## 9.1. Identité minimale

Toujours :

```text
kind
id
```

## 9.2. Projection d’objet

Conceptuellement :

```text
OBJECT
├── IDENTITY
│   ├── KIND
│   └── ID
│
├── REPRESENTATION
│   └── données minimales pour reconnaître l’objet
│
├── CONTEXT
│   └── données spécifiques au kind nécessaires ici
│
├── CAPABILITIES[]
└── LINKS
```

Aucun champ comme `title`, `status`, `place`, `timing` ou `owner` n’est universel.

## 9.3. Trois profondeurs

```text
REFERENCE
INLINE
DETAIL
```

### REFERENCE

Utilisée pour relier secondairement un objet :

```text
kind
id
représentation minimale éventuelle
```

### INLINE

Utilisée lorsqu’un objet porte directement un rôle Now :

```text
HUMAN_CONTEXT
SUBJECT
TURN
OWNER_DEPTH
```

Elle contient suffisamment de matière pour être comprise sans charger immédiatement le détail.

### DETAIL

Reste la profondeur du domaine propriétaire.

Now ne recopie jamais cette profondeur.

---

# 10. Exemples de projections inline

## 10.1. Profile

```text
identity
representation:
  display_name
  avatar
context autorisé utile
links
```

## 10.2. Space

```text
identity
representation:
  name
  mark/logo éventuel
context autorisé utile
links
```

## 10.3. Activity

```text
identity
representation
owner éventuel
personal relation utile
links
```

Pas la collection complète des Occurrences dans un inline Now.

## 10.4. Occurrence

Une `OccurrenceInline` doit généralement comprendre assez de contexte pour être humainement reconnaissable :

```text
identity
activity compact
state
timing
place
contexte vertical utile
links
```

Ainsi une Occurrence peut suffire comme `HUMAN_CONTEXT`.

## 10.5. Journey

```text
identity
representation
activity
occurrence?
state contextuel utile
links
```

Pas tous les Requirements, Forms, Payments et Artifacts dans Now.

## 10.6. Access

```text
identity
representation
activity
occurrence?
state
validity?
links
```

Jamais le secret AccessCredential dans l’inline générique.

## 10.7. Requirement

Reste distinct de :

```text
Form
Resource
JourneyArtifact
Proof
Credential
```

Le client ne déduit jamais qu’un Requirement est satisfait parce qu’un document existe.

---

# 11. FACT

Un `FACT` exprime ce qui est vrai ou établi.

Exemples :

```text
dossier complet
aucun véhicule affecté
demande en examen
paiement confirmé
voiture observée à Ruzizi
```

Structure conceptuelle :

```text
FACT
├── WHAT / PREDICATE
├── SUBJECT
├── VALUE / STATE
├── TIME?
└── SOURCE?
```

`STATE` d’une Situation est typiquement un `FACT`.

Le client ne reconstruit pas ce Fact à partir des champs bruts d’un modèle.

---

# 12. RELATION

Une `RELATION` exprime une relation sémantiquement utile entre plusieurs réalités.

Exemples conceptuels :

```text
dependency
facilitation
shared_resource
synchronization
conflict
alternative
cascade
feedback
same_action
same_turn
same_consequence
contradiction
```

Structure :

```text
RELATION
├── KIND
├── MEMBERS[]
└── CONTEXT / BASIS?
```

Une Relation n’implique jamais une fusion automatique.

---

# 13. TRANSITION

Une `TRANSITION` exprime ce qui vient de changer ou ce qui constitue un mouvement.

Exemples :

```text
relevé validé
fournisseur a répondu
Capacity 5 → 1
départ 14 h → 16 h
document signé
```

Structure conceptuelle :

```text
TRANSITION
├── KIND
├── SUBJECT
├── FROM?
├── TO?
├── AT?
└── ACTOR / SOURCE?
```

`DELTA` est typiquement une `TRANSITION`.

Distinction :

```text
FACT
→ ce qui est vrai maintenant

TRANSITION
→ ce qui a changé ou vient de se produire
```

---

# 14. COMPOSITION

Une vraie composition est utilisée uniquement lorsqu’un rôle unique doit réellement représenter plusieurs porteurs pour rester honnête.

Structure :

```text
COMPOSITION
├── MEMBERS[]
└── RELATIONS[]
```

`MEMBERS[]` peut contenir notamment :

```text
OBJECT
FACT
TRANSITION
COMPOSITION
```

Les relations restent dans `RELATIONS[]`.

Une composition ne doit pas devenir profonde ou récursive au point de créer un Journey/Dossier déguisé.

## 14.1. Exemple : conflit temporel

```text
HUMAN_CONTEXT
→ COMPOSITION
    members:
      Occurrence A
      Occurrence B
    relations:
      temporal_conflict(A, B)

SUBJECT
→ RELATION temporal_conflict
```

La Situation reste unique.

---

# 15. ACTOR_CONTEXT

Pour Now Me :

```text
ACTOR_CONTEXT
→ Profile Me
```

Conceptuellement, le contrat Now démontre :

```text
Profile
Space
```

comme Actor Contexts possibles selon la surface.

`ACTOR_CONTEXT` reste singulier.

Il ne donne aucune autorité par lui-même.

---

# 16. VIEWER

Pour Now Me :

```text
VIEWER
→ Profile authentifié courant
```

Il reste distinct de l’Actor Context dans les surfaces Space.

---

# 17. RESPONSIBILITY

Invariant :

```text
Assignment = responsabilité
```

Une Situation peut avoir plusieurs responsabilités pertinentes.

Structure conceptuelle :

```text
RESPONSIBILITY
└── ITEMS[]
    ├── ACTOR
    ├── KIND
    ├── SCOPE
    ├── SOURCE?
    └── VALIDITY?
```

Un `PRIMARY?` est possible uniquement si le domaine propriétaire possède réellement cette notion.

La responsabilité n’accorde jamais l’autorité.

Exemples de sources propriétaires actuelles possibles :

```text
JourneyAssignment
JourneyStepAssignment
DossierAssignment
CheckpointAssignment
ScannerAssignment
...
```

Le client ne connaît pas les règles de ces modèles.

---

# 18. AUTHORITY

Invariant :

```text
Mandate / Permission = autorité
```

Le client ne reçoit pas des Mandates bruts pour recalculer les permissions.

Le serveur produit une projection **effective et pertinente** pour la Situation.

Conceptuellement :

```text
AUTHORITY
├── EFFECTIVE
├── ACTOR
├── SCOPE
├── RELEVANT_CAPABILITIES / PERMISSIONS?
├── VALIDITY?
└── BASIS?     seulement si utile à l’explication ou à une profondeur supérieure
```

Plusieurs Mandates/Permissions peuvent contribuer à une seule autorité effective.

Donc :

```text
RESPONSIBILITY = 0..n
AUTHORITY = 0..1 projection effective
```

Cas valides :

```text
RESPONSIBILITY présente
AUTHORITY absente
```

et :

```text
RESPONSIBILITY vide
AUTHORITY effective
```

---

# 19. TURN

`TURN` répond uniquement à :

> À qui appartient le prochain mouvement ?

Il ne duplique ni Responsibility ni Authority.

Cardinalité :

```text
TURN = 0..1
```

Formes conceptuelles gelées :

```text
TURN
├── PROFILE
├── COLLECTIVE
├── EXTERNAL
├── MAKOLO
└── NONE
```

## 19.1. PROFILE

Un Profile Makolo identifiable.

## 19.2. COLLECTIVE

Une réalité collective canonique, aujourd’hui au moins :

```text
Space
Team
```

D’autres types ne sont pas ajoutés sans preuve canonique.

## 19.3. EXTERNAL

Un acteur extérieur au graphe canonique Makolo peut être représenté sans créer un modèle universel `ExternalActor`.

Exemple conceptuel :

```text
EXTERNAL
├── display_name
├── kind? / role?
├── organization?
├── reference? si un domaine en possède réellement une
└── autres détails autorisés strictement nécessaires
```

Exemples humains :

```text
fournisseur
ambassade
transporteur
```

## 19.4. MAKOLO

Makolo est une forme sémantique du TURN.

Ne pas fabriquer un faux objet métier `system:makolo` si aucun domaine ne le nécessite.

## 19.5. NONE

Aucun acteur ne possède actuellement le prochain mouvement.

Ne pas créer un faux `SystemActor` pour le temps, une fenêtre ou un traitement automatique.

---

# 20. RESPONSE

`RESPONSE` exprime la réponse correcte pour l’Actor Context.

Valeurs conceptuelles retenues :

```text
ACT
DECIDE
PREPARE
EXECUTE
WAIT
MONITOR
UNDERSTAND
HANDOFF
```

Exemples :

```text
TURN = Profile Gilbert
RESPONSE = DECIDE

TURN = fournisseur
RESPONSE = WAIT

TURN = Makolo
RESPONSE = PREPARE
```

`RESPONSE` n’est pas l’action du TURN.

---

# 21. HUMAN_CONTEXT

`HUMAN_CONTEXT` répond :

> De quelle réalité humaine parle-t-on ?

Cardinalité :

```text
1
```

Formes :

```text
OBJECT
COMPOSITION
```

Cas normal : un porteur unique suffit.

Exemples :

```text
Activity
Occurrence
Journey
Order
Dossier
...
```

La composition est exceptionnelle et uniquement utilisée lorsque la réalité humaine elle-même est irréductiblement composée.

---

# 22. SUBJECT

`SUBJECT` répond :

> Qu’est-ce qui est précisément concerné ?

Cardinalité :

```text
1
```

Formes :

```text
OBJECT
FACT
RELATION
TRANSITION
COMPOSITION
```

Exemples :

```text
Payment                 → OBJECT
affectation véhicule    → RELATION
signature document      → TRANSITION
réponse fournisseur     → TRANSITION / fait attendu selon owner
conflit horaire         → RELATION
```

---

# 23. STATE

`STATE` répond :

> Qu’est-ce qui est vrai maintenant ?

Forme :

```text
STATE → FACT
```

Le serveur le dérive des vérités propriétaires.

Le client ne construit pas lui-même un état métier à partir d’un statut brut.

---

# 24. DELTA

`DELTA` répond :

> Qu’est-ce qui a changé ?

Forme :

```text
DELTA → TRANSITION
```

Optionnel.

Une Situation peut être pertinente même sans Delta, notamment par simple passage du temps ou changement d’Horizon.

---

# 25. WHY_NOW

`WHY_NOW` répond :

> Pourquoi cette Situation mérite-t-elle de compter maintenant ?

Ce n’est pas un texte libre ni un timestamp.

Conceptuellement :

```text
WHY_NOW
├── REASON
└── BASIS[]
```

Exemples :

```text
horizon_approaching
basis → HORIZON

dependency_resolved
basis → TRANSITION

response_requires_decision
basis → FACT/TRANSITION
```

Le client ne décide jamais lui-même qu’une deadline ou un délai crée Now.

---

# 26. CONSEQUENCE

`CONSEQUENCE` répond :

> Qu’est-ce qui est réellement affecté si rien ne change ?

Conceptuellement :

```text
CONSEQUENCE
├── TARGET
├── EFFECT
└── CONDITION / HORIZON?
```

Elle ne se réduit pas à `severity=high` ou `blocking=true`.

---

# 27. HORIZON

`HORIZON` ne se réduit jamais à une date.

Deux grandes formes :

```text
TEMPORAL
EVENT
```

Exemples temporels :

```text
avant 16 h
le 18
entre lundi et mercredi
```

Exemples événementiels :

```text
jusqu’à réponse du fournisseur
jusqu’à confirmation du paiement
à l’ouverture des inscriptions
```

Le client peut formater les dates, heures, durées et countdowns sans changer leur sens.

---

# 28. MAKOLO_PREPARATION

Collection naturelle :

```text
MAKOLO_PREPARATION[]
```

Exemples :

```text
formulaire prérempli
pièces retrouvées
coordonnées vérifiées
document disponible
réservation préparée
```

Peut contenir principalement des projections `FACT`, `OBJECT` ou transitions préparées.

Invariant :

```text
préparé ≠ envoyé
 envoyé ≠ confirmé
 confirmé ≠ résultat humain accompli
```

Et :

```text
MAKOLO_PREPARATION ≠ TURN = Makolo
```

---

# 29. OWNER_DEPTH

Chaque Situation connaît la réalité propriétaire de sa profondeur.

Cardinalité :

```text
1
```

Exemples :

```text
Journey
Occurrence
Activity
Order
Dossier
Access
Payment
Transport
Service
Obtention
```

Principe :

> **Now explique pourquoi entrer. Le domaine propriétaire explique tout le reste.**

Le handoff se fait via les links/capabilities fournis par le serveur.

Le client ne reconstruit jamais un endpoint depuis `kind`.

---

# 30. KNOWLEDGE_CONTEXT

Structure spécialisée :

```text
KNOWLEDGE_CONTEXT
├── PROVENANCE[]
├── FRESHNESS
├── KNOWLEDGE_STATE
└── CONFIDENCE?
```

## 30.1. PROVENANCE

0..n sources légitimes ayant permis d’établir la connaissance.

La liste exacte des types de provenance reste ouverte.

## 30.2. FRESHNESS

Décrit la fraîcheur de la connaissance métier.

Elle est différente de la fraîcheur du snapshot Flutter/Web.

## 30.3. KNOWLEDGE_STATE

Valeurs conceptuelles :

```text
KNOWN
UNKNOWN
CONTRADICTORY
STALE
UNAVAILABLE
```

## 30.4. CONFIDENCE

Optionnelle et seulement utilisée si le serveur peut réellement la défendre.

Ne pas fabriquer un score simplement parce qu’un système d’IA est impliqué.

---

# 31. Deux fraîcheurs distinctes

```text
SERVER KNOWLEDGE FRESHNESS
→ fraîcheur de ce que Makolo sait du monde
```

versus :

```text
CLIENT SNAPSHOT FRESHNESS
→ fraîcheur de la copie reçue par cet appareil
```

Le client ne transforme jamais un cache local ancien en `KNOWLEDGE_STATE=STALE` métier.

---

# 32. ATTENTION

Trois axes indépendants :

```text
ATTENTION
├── LEVEL
├── CONTINUITY_STATE
└── LIFECYCLE_EVENT?
```

## 32.1. LEVEL

```text
FOREGROUND
NEAR
WATCHED_BACKGROUND
OUT
```

## 32.2. CONTINUITY_STATE

```text
NEW
STABLE
CHANGED
RETURNED
```

## 32.3. LIFECYCLE_EVENT

```text
ENTERED
UPDATED
REACTIVATED
RESOLVED
EXITED
```

Invariants :

```text
NEW ≠ PRIORITY
SEEN ≠ RESOLVED ≠ DEMOTED
WAIT ≠ lifecycle state
```

`WAIT` est une `RESPONSE`.

Les états client :

```text
seen
opened
selected
expanded
```

restent Presentation/local state.

---

# 33. CONTINUITY_IDENTITY

Now a besoin d’une identité de continuité stable pour reconnaître qu’une Situation a changé sans devenir artificiellement nouvelle.

Exemple :

```text
Votre contrat doit être signé
```

puis :

```text
Votre contrat a été envoyé
```

peuvent appartenir à la même continuité humaine.

Invariant :

```text
CONTINUITY_IDENTITY
≠ identité métier
```

Le serveur doit fournir une identité opaque/stable.

Le client ne la reconstruit jamais depuis :

```text
kind + id
title
text similarity
same Payment
same Journey
```

Le mécanisme technique de calcul/persistance reste volontairement ouvert.

---

# 34. BUSINESS_ACTIONS

Une Situation peut avoir plusieurs actions légitimes.

Donc :

```text
BUSINESS_ACTIONS[]
```

Chaque action appartient au domaine propriétaire.

Conceptuellement :

```text
BUSINESS_ACTION
├── ACTION / INTENT
├── TARGET
├── OWNER / HANDOFF
├── CAPABILITY
├── INTERACTION_DEPTH
├── CONFIRMATION? si owner-backed
└── autres paramètres owner-backed strictement nécessaires
```

Une capability est informative et contextuelle.

Toute mutation revalide autorité et état côté serveur.

---

# 35. INTERACTION_DEPTH

Valeurs :

```text
DIRECT_NOW
FOCUSED
DOMAIN_DEPTH
NONE
```

La profondeur appartient mieux à chaque Business Action qu’à la Situation entière.

## DIRECT_NOW

Action réalisable directement depuis Now.

## FOCUSED

Interaction bornée nécessitant quelques choix supplémentaires.

## DOMAIN_DEPTH

Le vrai contexte métier est nécessaire.

## NONE

Aucune interaction utile.

Le client choisit le composant concret : bouton, sheet, dialog, navigation, split view, etc.

Le serveur choisit la profondeur sémantique.

---

# 36. MEDIA_BINDINGS

Collection naturelle :

```text
MEDIA_BINDINGS[]
```

Chaque binding porte conceptuellement :

```text
MEDIA_BINDING
├── RESOURCE
├── TARGET
└── PURPOSE
```

## TARGET possible

```text
Situation entière
SUBJECT
HUMAN_CONTEXT
STATE
DELTA
TURN
MAKOLO_PREPARATION
ACTION
```

## PURPOSE

```text
RECOGNIZE
UNDERSTAND
ESTABLISH
PREPARE
ACT
```

Le serveur fournit la ressource et sa finalité.

Le client décide du viewer approprié selon la forme de la donnée.

Exemples :

```text
image/jpeg → image viewer
application/pdf → PDF viewer
video/mp4 → video player
coordinates → map
```

Invariant :

```text
média ≠ Proof automatique
```

---

# 37. EXIT_CONDITION

Toute Situation possède conceptuellement une condition de sortie.

Exemples :

```text
document signé
véhicule affecté
réponse reçue
échéance dépassée
responsabilité transférée
objectif abandonné
information devenue non pertinente
```

`EXIT_CONDITION` évite les Situations immortelles.

Elle reste par défaut interne à la projection/moteur serveur et n’est pas requise dans `NowMeResponse` client.

---

# 38. État calme

`CALM` signifie :

```text
aucune intervention,
aucune décision,
aucune attention active
n’est requise du Profile courant
```

Cela peut coexister avec :

```text
WATCHED_BACKGROUND
TURN = fournisseur / Makolo / none
RESPONSE = WAIT / MONITOR
```

Donc :

```text
CALM
≠ nécessairement situations.length == 0
```

Le serveur fournit la sémantique de calme.

Le client choisit la formulation :

```text
Tout est en ordre. ✓
```

---

# 39. ATTENTION_SUMMARY

Une synthèse d’attention peut exister lorsqu’elle aide réellement.

Elle reste :

```text
optionnelle
```

Elle ne doit jamais inventer une vérité métier ni transformer plusieurs Situations en un score ou une urgence artificielle.

Elle n’est pas obligatoire dans le contrat de base.

---

# 40. Frontière serveur / client

## 40.1. Serveur

Le serveur est propriétaire de :

```text
admission dans Now
ordre sémantique / attention level
continuity identity
actor context
responsibility
authority
human context
subject
state
delta
why now
consequence
turn
response
horizon
makolo preparation
owner depth
knowledge state
knowledge freshness
provenance
confidence si légitime
attention axes
business actions
interaction depth
media semantics
links
capabilities
```

## 40.2. Client

Le client est propriétaire de :

```text
locale
timezone appareil
horloge locale
online/offline
freshness snapshot local
pending/outbox
drafts locaux
seen/opened/selected/expanded
cache média
viewport
Compact/Medium/Wide
text scale/accessibility
navigation locale
```

Le client peut calculer uniquement des dérivations sûres à partir de données déjà légitimement connues :

```text
datetime → "demain"
datetime → "dans 35 min"
number → format numérique
money → format monétaire
coordinates → distance géométrique
coordinates → route/itinéraire si mécanisme disponible
mime type → viewer approprié
screen size → layout
```

---

# 41. Règle de décision serveur/client

## Question 1

Le résultat dépend-il d’une vérité métier, relation canonique, autorité, provenance, état concurrent/global ou connaissance que le client ne possède pas complètement ?

```text
Oui → serveur / futur Molongo
```

## Question 2

Le résultat est-il entièrement déterministe à partir de données déjà légitimement connues du client, avec une signification déjà fixée ?

```text
Oui → calcul client possible
```

## Question 3

Est-ce uniquement de la représentation ?

```text
Oui → client
```

Principe :

```text
mathematical derivation ≠ authority over meaning
```

---

# 42. Dual source / local-first

Le client ne fusionne jamais silencieusement un état local pending avec une vérité canonique serveur.

Exemple :

```text
server.saved = false
client.pending_operation = save
```

Le client rend :

```text
Enregistrement en cours…
```

et non :

```text
saved = true
```

Même principe :

```text
server Payment = pending
client request sent
```

n’est pas :

```text
Payment confirmed
```

Conserver séparément :

```text
canonical state
local pending/draft/outbox
server knowledge freshness
client cache freshness
server place
current device position
server media metadata
local cached bytes
server personal relation
local pending mutation
```

---

# 43. Situation Now ≠ composant UI fixe

Une Situation peut devenir :

```text
phrase
ligne compacte
avatar + texte
image
carte
PDF lisible
graphique
surface interactive
Card
composition de plusieurs composants
```

Donc :

```text
Situation Now ≠ Card
```

Le client construit la représentation N1/N2/N3 selon le contexte, l’écran et les données disponibles.

---

# 44. Confidentialité et divulgation minimale

Toute projection est viewer-safe.

Ne jamais exposer génériquement :

```text
password
password hash
secret token
private key
AccessCredential secret complet
provider credential
raw ledger metadata
private evidence
PII tierce inutile
hidden dependency identity
internal DB/cache records
```

Un objet inline n’est jamais un dump du modèle Django.

Une composition multi-contextes ne transfère jamais implicitement :

```text
Permission
Mandate
Access
Payment
private data
```

---

# 45. Invariants Now Me gelés

1. Now est un champ d’attention, pas une liste exhaustive du backend.
2. Une Situation Now est une projection, pas une nouvelle vérité métier.
3. Situation Now ≠ Card.
4. Profile et Space partagent le concept Now mais gardent leur langage contextuel.
5. Actor Context, Viewer, Responsibility, Authority et TURN sont distincts.
6. Assignment = responsabilité.
7. Mandate/Permission = autorité.
8. Membership/Team/Group n’accorde jamais d’autorité implicitement.
9. Readiness reste une projection dérivée du domaine propriétaire.
10. Une Situation doit expliquer pourquoi elle compte maintenant.
11. Une Situation doit avoir une conséquence pertinente.
12. Une Situation doit avoir une réponse utile, y compris WAIT ou UNDERSTAND.
13. Toute Situation possède conceptuellement une condition de sortie.
14. Relation ≠ fusion.
15. Plusieurs faits ayant servi au raisonnement ≠ COMPOSITION automatique.
16. Si un porteur unique suffisamment riche existe, il gagne sur la composition.
17. Une OccurrenceInline peut porter Activity + timing + place utiles sans duplication artificielle.
18. SUBJECT reste singulier même dans une Situation composée.
19. TURN reste singulier.
20. TURN ≠ Responsibility ≠ Authority.
21. `SYSTEM` n’est pas fabriqué comme acteur fictif quand TURN=NONE suffit.
22. BUSINESS_ACTION appartient au domaine propriétaire.
23. Une Situation peut exposer plusieurs BUSINESS_ACTIONS.
24. InteractionDepth appartient naturellement à l’action concernée.
25. Capabilities serveur ≠ Permission persistée côté client.
26. Toute mutation revalide l’autorité côté serveur.
27. CONTINUITY_IDENTITY ≠ identité métier.
28. Le client ne reconstruit jamais la continuité par similarité.
29. KNOWLEDGE freshness ≠ client snapshot freshness.
30. UNKNOWN ≠ FALSE ≠ ABSENT ≠ UNAVAILABLE.
31. NEW ≠ PRIORITY.
32. SEEN ≠ RESOLVED ≠ DEMOTED.
33. WAIT est une RESPONSE, pas un état du cycle d’attention.
34. Un média doit servir reconnaître, comprendre, constater, préparer ou agir.
35. Média ≠ Proof automatique.
36. Préparer ≠ exécuter.
37. Possibilité technique ≠ autorité.
38. Une projection inline applique toujours la divulgation minimale.
39. Le serveur ne produit pas l’interface.
40. Le client ne reconstruit pas l’écosystème.

---

# 46. Ce qui est gelé

Sont considérés conceptuellement gelés pour Now Me :

```text
la définition de Situation Now
la frontière serveur/client
les cardinalités principales
les cinq familles OBJECT/FACT/RELATION/TRANSITION/COMPOSITION
les trois profondeurs REFERENCE/INLINE/DETAIL
la règle du porteur minimal suffisant
la structure Responsibility
la structure Authority effective
les formes TURN
la séparation State/Delta/WhyNow/Consequence
les formes Horizon
Knowledge Context
Attention axes
BusinessActions[]
InteractionDepth par action
MediaBindings[]
OwnerDepth
état Calm/Active
```

---

# 47. Ce qui reste volontairement non figé

Ne sont pas encore gelés :

```text
noms exacts des champs JSON
snake_case final
schema_version final
null/[]/{}/unknown exacts pour chaque champ wire
algorithme/persistance de CONTINUITY_IDENTITY
liste exhaustive des kinds OBJECT exposables
schémas exacts de chaque ObjectInline
schémas exacts de provenance
noms exacts des reason/effect/predicate kinds
links/endpoints finaux par owner
mécanisme Molongo futur
mécanisme éventuel de cache/déduplication transport
stratégie de migration depuis les projections API existantes
```

Ces points sont techniques ou implémentatoires. Ils ne remettent plus en cause la compréhension UX de Now Me.

---

# 48. Pipeline cible

```text
request.user Profile
      ↓
selectors / services / read models propriétaires
      ↓
composition sémantique serveur
      ↓
seam Molongo explicite
(identity/no-op aujourd’hui tant que son vrai contrat n’est pas connu)
      ↓
NowMeResponse canonique
      ↓
Web HTML/Tailwind
ou
Flutter local-first
      ↓
Presentation N1 / N2 / N3
      ↓
action owner-backed
      ↓
revalidation serveur
      ↓
nouvelle projection
```

Aucun futur input Molongo spéculatif n’est défini ici.

---

# 49. Conclusion

Now Me est désormais conceptuellement assez fermé pour servir de référence lors du futur redesign des projections Django, du Web et de Flutter.

La règle de fermeture est :

```text
Serveur
→ comprend la Situation
→ décide ce qui est vrai, pertinent, autorisé et actionnable
→ projette les objets/faits/relations/transitions nécessaires

Client
→ reçoit cette vérité structurée
→ ajoute son contexte local légitime
→ humanise
→ choisit la représentation
→ permet l’action sans réinventer le métier
```

Le prochain chantier conceptuel peut désormais passer à **Continuité En cours**, en réutilisant la même discipline de séparation entre vérité serveur, projection sémantique et Presentation client.
