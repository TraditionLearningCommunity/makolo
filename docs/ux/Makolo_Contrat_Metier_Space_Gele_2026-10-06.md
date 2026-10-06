# Makolo — Contrat conceptuel gelé
# Métier Space

**Statut :** contrat conceptuel cible, gel de conception  
**Date :** 2026-10-06  
**Portée :** surface `Métier` dans un contexte Space  
**Clients concernés :** Django/API, Web HTML/Tailwind, Flutter  
**Dépôt officiel :** `TraditionLearningCommunity/makolo`  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 0. Objet

Ce document fixe le contrat conceptuel complet de la surface **Métier** dans un Space.

La question humaine de cette surface est :

> **Qu’est-ce que nous faisons réellement exister, préparer, exécuter et délivrer ?**

La surface Métier est la principale surface durable de travail d’un Space.

Elle n’est pas une adaptation directe de `En cours Me`.

```text
Métier Space
≠ Ongoing Me + actor = Space
```

Dans le contexte personnel :

```text
En cours
→ continuité de ce que la personne a réellement engagé
```

Dans le contexte Space :

```text
Métier
→ monde opérationnel durable réellement porté par le Space
```

`En cours` devient donc une **dimension** de ce monde opérationnel, pas une porte Space autonome.

Ce document fixe :

- le contexte acteur/viewer ;
- la relation viewer ↔ Space ;
- la place de l’archétype ;
- le rôle de l’Operational Footprint ;
- la différence entre responsabilité et autorité ;
- la notion de Perspective Métier ;
- la notion de Section Métier ;
- la Business Entry comme unité de projection UX ;
- la Continuity Facet facultative ;
- les états de composition et couverture ;
- les cardinalités ;
- les actions et créations contextuelles ;
- les owner handoffs ;
- l’historique ;
- Jour J / Live ;
- la recherche et les filtres ;
- la pagination et l’ordre ;
- les états loading / empty / partial / unavailable / offline / error ;
- les comportements Back / Resume / Refresh ;
- les règles local-first ;
- les déclinaisons par archétype ;
- les anti-features ;
- les critères de sortie serveur et client.

Ce document ne crée pas :

- un modèle `WorkItem` ;
- un modèle `BusinessItem` ;
- une table `OperationalContinuity` ;
- un lifecycle métier universel ;
- une nouvelle table de statut ;
- un task manager Makolo ;
- un ERP générique ;
- une nouvelle vérité métier ;
- une migration ;
- un contrat JSON définitif ;
- un moteur de ranking ;
- une formule Molongo ;
- une maquette pixel-perfect.

Le code, les migrations, les tests et les owners canoniques courants restent prioritaires lors de toute implémentation.

---

# 1. Position de Métier dans le shell Space

La navigation primaire Space est :

```text
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
```

Chaque porte répond à une question différente :

```text
Maintenant
→ Qu’est-ce qui mérite notre attention maintenant ?

Découvrir
→ Qu’est-ce qui pourrait nous aider à avancer ?

Makolo Mark
→ J’ai quelque chose à donner à Makolo.

Métier
→ Qu’est-ce que nous opérons réellement ?

Nous
→ Qui sommes-nous et comment fonctionnons-nous ensemble ?
```

Métier correspond au **travail durable et à la continuité opérationnelle**.

---

# 2. Frontières avec les autres surfaces

## 2.1 Métier n’est pas Now

`Now` sélectionne ce qui mérite attention actuellement.

`Métier` représente le monde opérationnel même lorsqu’aucune urgence n’existe.

Exemple :

```text
127 commandes ouvertes
→ Métier

4 commandes nécessitent intervention maintenant
→ Now
```

Donc :

```text
Métier
→ tout le travail durable dans le scope

Now
→ sous-ensemble attentionnel avec conséquence présente
```

## 2.2 Métier n’est pas Discover

`Discover` représente des possibilités.

`Métier` représente des réalités déjà opérées, préparées, engagées ou durablement utilisées.

Exemple :

```text
Funding pertinent
→ Discover

candidature Funding effectivement créée
→ owner Funding

si elle devient une réalité du travail du Space
→ Métier
```

Un Bookmark ou une simple consultation Discover ne suffit jamais.

## 2.3 Métier n’est pas Nous

```text
Nous
→ qui sommes-nous et comment fonctionnons-nous ?

Métier
→ que faisons-nous réellement exister et délivrer ?
```

Exemples :

```text
Team
Ownership
Mandates
Trust institutionnel
→ Nous

Vehicle
Route
Order
Service case
Programme
Occurrence
→ Métier
```

## 2.4 Métier n’est pas Piloter

```text
Métier
→ faire le travail

Piloter
→ comprendre si le travail fonctionne et ce qu’il faut ajuster
```

Les Analytics ou KPI ne deviennent pas des Business Entries par défaut.

Un signal de Pilotage peut toutefois devenir une Situation Now si sa conséquence devient actuelle.

---

# 3. Anti-modèles structurants

Métier n’est pas un catalogue de domaines :

```text
Activity
Occurrence
Journey
Requirement
Capacity
Access
Payment
Operations
Commerce
CRM
```

Métier n’est pas un task manager universel :

```text
Task
Subtask
Assignee
Due date
Kanban
Backlog
Sprint
```

Métier n’est pas un ERP générique.

Makolo possède déjà des owners précis ; Métier les compose sans les remplacer.

---

# 4. Acteur et viewer

## 4.1 `ACTOR_CONTEXT`

Cardinalité :

```text
1
```

Valeur :

```text
Space courant
```

## 4.2 `VIEWER`

Cardinalité :

```text
1
```

Valeur :

```text
Profile humain authentifié
```

Exemple :

```text
ACTOR_CONTEXT
→ Mulykap

VIEWER
→ Jean
```

Jean reste la personne.

Le Space est l’acteur collectif.

## 4.3 Le Space ne devient pas User

Un Space n’a pas :

```text
session humaine
Avatar humain propre
compte utilisateur collectif
Profile collectif
```

Une personne agit au nom du Space uniquement dans les limites de l’autorité canonique.

---

# 5. `VIEWER_RELATION`

Cardinalité :

```text
1
```

Structure conceptuelle :

```text
VIEWER_RELATION
├── AUTHORITY_CONTEXT
├── RESPONSIBILITY_PERSPECTIVES[]
└── SELECTED_RESPONSIBILITY_PERSPECTIVE?
```

Cette projection est viewer-specific.

Elle ne fait pas partie de l’identité intrinsèque du Space.

---

# 6. Responsabilité et autorité

Invariants :

```text
Assignment
= responsabilité

Mandate / Permission
= autorité
```

Et :

```text
TeamMembership
≠ authority

GroupMembership
≠ authority

Assignment
≠ Permission

Archetype
≠ Permission

Operational Footprint
≠ Permission
```

---

# 7. `RESPONSIBILITY_PERSPECTIVE`

Une perspective telle que :

```text
Toutes mes responsabilités
Exploitation
Finance
Administration
Contrôle · Départ 14 h
```

est un **read model UX**.

Elle peut être résolue à partir de :

```text
Assignments
Mandates
scopes
responsabilités métier
contexte
```

Elle ne devient pas un nouvel owner.

Cardinalités :

```text
RESPONSIBILITY_PERSPECTIVES[]
→ 0..n

SELECTED_RESPONSIBILITY_PERSPECTIVE
→ 0..1
```

Le filtre de responsabilité peut réduire :

```text
la lecture
les sections visibles
les entrées visibles
le langage contextuel
```

Il ne peut jamais augmenter :

```text
Permissions
Mandates
scope
capabilities réelles
```

---

# 8. `AUTHORITY_CONTEXT`

Cardinalité :

```text
1 effective summary
```

Le runtime courant distingue au moins conceptuellement :

```text
space-wide
activity-limited
```

Les noms wire finaux restent ouverts.

## 8.1 Autorité Space-wide

Une autorité directe sur le Space peut permettre une projection plus large.

Mais :

```text
Space-wide
≠ accès total à toutes les données
```

Les Permissions owner-specific continuent de s’appliquer.

## 8.2 Autorité Activity-limited

Une personne peut entrer dans un Space uniquement grâce à une autorité scoped à une Activity.

Alors Métier doit être borné à ce scope.

Peuvent apparaître selon permissions :

```text
Activity X
Occurrence X1
Journey X
Offer liée à X
service case lié à X
```

Ne doivent pas fuiter automatiquement :

```text
flotte globale
routes globales
toutes les commandes
tout le footprint
Partners globaux
CRM global
autres Activities
```

---

# 9. `ARCHETYPE`

Cardinalité :

```text
1
```

L’archétype exprime :

> le centre de gravité durable du fonctionnement du Space.

Il influence :

```text
langage
perspective préférée
priorités de Presentation
```

Il ne crée aucune vérité opérationnelle.

---

# 10. `OPERATIONAL_FOOTPRINT`

L’Operational Footprint décrit :

> les domaines réellement utilisés par le Space.

Conceptuellement :

```text
ARCHETYPE
= comment le Space fonctionne principalement

OPERATIONAL_FOOTPRINT
= ce que le Space utilise réellement
```

Exemple :

```text
archetype = commerce
```

mais Footprint :

```text
Activity
Commerce
Service
Transport
Funding
Geography
```

Le Space peut utiliser plusieurs verticales sans changer d’archétype.

Pour un viewer Activity-limited :

```text
OPERATIONAL_FOOTPRINT
→ peut être masqué ou réduit
```

Cardinalité dans la réponse :

```text
0..1 projection
```

Le Footprint ne devient jamais un menu de modules techniques.

---

# 11. Contrat racine final

```text
SPACE BUSINESS RESPONSE
│
├── ACTOR_CONTEXT                         1
├── VIEWER                                1
│
├── VIEWER_RELATION                       1
│   ├── AUTHORITY_CONTEXT                 1
│   ├── RESPONSIBILITY_PERSPECTIVES[]     0..n
│   └── SELECTED_RESPONSIBILITY?          0..1
│
├── ARCHETYPE                             1
├── OPERATIONAL_FOOTPRINT?                0..1
├── COMPOSITION_STATE                     1
│
└── BUSINESS_WORLD                        1
    ├── PREFERRED_LANGUAGE                1
    ├── PERSPECTIVES[]                    0..n
    └── SELECTED_PERSPECTIVE?             0..1
```

---

# 12. `COMPOSITION_STATE`

Métier n’a pas besoin d’un ranking primaire comme Now ou Discover.

Il a un état de composition :

```text
COMPOSITION_STATE
├── ESTABLISHED
├── PARTIAL
└── UNAVAILABLE
```

## 12.1 `ESTABLISHED`

Les sources nécessaires au scope courant sont suffisamment composées.

Alors :

```text
entries=[]
```

peut réellement signifier vide.

## 12.2 `PARTIAL`

Certaines familles sont correctement connues, d’autres non.

Exemple :

```text
Transport
├── départs       established
├── routes        established
└── véhicules     unavailable
```

La surface reste utilisable.

## 12.3 `UNAVAILABLE`

La composition métier demandée ne peut pas être établie correctement.

Cela ne signifie jamais :

```text
le Space n'opère rien
```

---

# 13. `COVERAGE_STATE`

Une Perspective ou Section peut porter :

```text
COVERAGE_STATE
├── ESTABLISHED
├── PARTIAL
└── UNAVAILABLE
```

Exemple :

```text
Véhicules
coverage = ESTABLISHED
entries = []
```

signifie : aucun véhicule connu dans ce scope.

Tandis que :

```text
Véhicules
coverage = UNAVAILABLE
```

signifie : la source ne peut actuellement être établie.

Si le viewer n’a pas le droit de savoir qu’une section existe :

```text
HIDDEN
→ section omise
```

Pas `UNAVAILABLE`.

---

# 14. `PREFERRED_LANGUAGE`

Cardinalité :

```text
1
```

Table conceptuelle :

```text
generic
→ Activités

creative
→ Créations

media
→ Productions

education
→ Programmes

commerce
→ Commerce

service_provider
→ Prestations

transport_operator
→ Transport

community
→ Initiatives
```

Le langage préféré ne force pas nécessairement la Perspective visible si le scope est plus étroit.

---

# 15. `BUSINESS_PERSPECTIVE`

Définition :

> une manière humaine durable d’entrer dans une partie du monde réellement opéré par le Space.

Structure :

```text
BUSINESS_PERSPECTIVE
│
├── PERSPECTIVE_IDENTITY                 1
├── REPRESENTATION                       1
├── COVERAGE_STATE                       1
├── SECTIONS[]                           0..n
├── CREATION_ACTIONS[]                   0..n
└── OWNER_HANDOFFS[]                     0..n
```

Une Perspective peut être exposée si au moins :

```text
VISIBLE_OWNER_REALITY
∨ LEGITIMATE_CREATION_CAPABILITY
∨ AUTHORIZED_OPERATIONAL_CONTINUITY
```

Pas simplement parce que l’archétype la suggère.

Une Perspective peut composer plusieurs owners.

Exemple :

```text
PROGRAMMES
├── Activity
├── Occurrence
├── Journey
├── Requirement
├── Form
├── Resource
├── Group
├── Capacity
└── Access
```

Cardinalités :

```text
AVAILABLE_PERSPECTIVES
→ 0..n

SELECTED_PERSPECTIVE
→ 0..1
```

---

# 16. Responsibility Perspective vs Business Perspective

```text
RESPONSIBILITY_PERSPECTIVE
→ sous quel angle de responsabilité je travaille

BUSINESS_PERSPECTIVE
→ quelle partie du monde opérationnel je regarde
```

Ils sont indépendants.

Exemple :

```text
Responsabilité
→ Finance

Perspective
→ Transport
```

peut vouloir dire : voir Transport sous le périmètre Finance.

---

# 17. `BUSINESS_SECTION`

Structure :

```text
BUSINESS_SECTION
│
├── SECTION_IDENTITY                    1
├── REPRESENTATION                      1
├── SECTION_ROLE?                       0..1
├── COVERAGE_STATE                      1
├── ENTRIES[]                           0..n
├── CONTINUATION?                       0..1
├── ACTIONS[]                           0..n
└── HANDOFFS[]                          0..n
```

---

# 18. `SECTION_ROLE`

Conceptuellement optionnel :

```text
CONTINUITY
STRUCTURE
HISTORY
CONTEXTUAL
```

Exemples :

```text
À venir
→ CONTINUITY

Routes
→ STRUCTURE

Terminées
→ HISTORY

Aujourd'hui
→ CONTEXTUAL
```

Ce rôle est une aide Presentation, jamais un statut métier persistant.

---

# 19. Section ≠ owner state

Invariant :

```text
BUSINESS_SECTION
≠ OWNER_STATE
```

Exemple :

```text
Order.status = CONFIRMED
```

peut apparaître dans `En cours` sans devenir :

```text
order.status = ongoing
```

---

# 20. Sections de continuité et sections structurelles

Métier doit pouvoir composer :

```text
CONTINUITY SECTIONS
```

et :

```text
STRUCTURAL SECTIONS
```

Exemples de continuité :

```text
À préparer
À venir
En cours
Bloqués
Terminés
```

Exemples structurels :

```text
Routes
Véhicules
Offres
Programmes
Prestations proposées
Lieux
Services
```

---

# 21. Correction fondamentale du runtime actuel

Le runtime actuel peut placer :

```text
Vehicle.active = true
→ active

Route.active = true
→ active
```

Le contrat cible distingue :

```text
vehicle lifecycle active
≠ véhicule en cours

route lifecycle active
≠ route en cours
```

La cible préfère :

```text
Vehicle
→ section Véhicules
→ owner_state = active

Route
→ section Routes
→ owner_state = active
```

Les regroupements runtime :

```text
preparation
upcoming
active
blocked
completed
```

restent légitimes pour les réalités progressives, mais ne deviennent pas une obligation universelle.

---

# 22. Ordre des Sections

Le serveur fournit un ordre déjà résolu.

Transport :

```text
Aujourd'hui
Prochains départs
Départs actifs
Routes
Véhicules
Services
Lieux
Historique
```

Prestations :

```text
Demandes
À préparer
En traitement
Bloquées
À délivrer
Terminées
```

Commerce :

```text
Offres
Commandes à traiter
À préparer
À remettre
Disponibilité
Historique
```

Le client ne trie pas les sections alphabétiquement ni selon une convention universelle.

---

# 23. `BUSINESS_ENTRY`

Définition :

> **Une Business Entry est une projection UX bornée d’une réalité owner-backed appartenant au monde réellement opéré par le Space.**

Elle n’est pas :

```text
Task
WorkItem
Activity bis
nouveau modèle métier
```

Structure :

```text
BUSINESS_ENTRY
│
├── ENTRY_IDENTITY                     1
├── SUBJECT                            1
├── REPRESENTATION                     1
├── OWNER_REFERENCE                    1 conceptuellement
├── OWNER_STATE?                       0..1
├── FACTS[]                            0..n
├── TEMPORAL_FACTS[]                   0..n
├── SPATIAL_FACTS[]                    0..n
├── RELATIONS[]                        0..n
├── CONTINUITY_FACET?                  0..1
├── RESPONSIBILITY[]                   0..n
├── AUTHORITY?                         0..1
├── CAPABILITIES[]                     0..n
├── OWNER_HANDOFFS[]                   0..n
├── KNOWLEDGE_CONTEXT                  1
└── MEDIA_BINDINGS[]                   0..n
```

---

# 24. `ENTRY_IDENTITY`

Cardinalité :

```text
1
```

Utilités :

```text
render stable
selection
back/resume
cache
dedup
refresh reconciliation
```

Lorsque la Business Entry correspond exactement à un owner simple :

```text
Occurrence 123
Vehicle 42
Order 493
```

l’identité owner peut suffire.

Pour une composition multi-owner :

```text
ENTRY_IDENTITY
→ projection identity opaque
```

Le client ne reconstruit jamais l’identité par titre, date, kind ou similarité.

---

# 25. `SUBJECT`

Cardinalité :

```text
1
```

Peut être :

```text
OBJECT
COMPOSITION
```

Exemples :

```text
Vehicle
Route
Occurrence
CommerceOrder
Journey
Activity
```

---

# 26. `REPRESENTATION`

Cardinalité :

```text
1
```

Exemples :

```text
Départ Lubumbashi → Kolwezi · 14 h
Programme Comptabilité
Commande 493
Prestation Visa
Bus 07
Route Lubumbashi–Kolwezi
```

---

# 27. `OWNER_REFERENCE`

Conceptuellement :

```text
1
```

Il répond : qui possède la vérité ?

Exemples :

```text
Activity
Occurrence
CommerceOrder
Journey
TransportRoute
Vehicle
```

---

# 28. Owner Reference ≠ Owner Handoff

```text
OWNER_REFERENCE
→ owner conceptuel

OWNER_HANDOFF
→ profondeur réellement ouvrable
```

Une Entry peut avoir un owner mais aucun handoff client stable.

Cardinalité :

```text
0..n
```

Si aucun owner link stable n’existe, le client ne construit jamais l’URL par convention locale.

---

# 29. `OWNER_STATE`

Cardinalité :

```text
0..1
```

Exemples :

```text
DRAFT
PUBLISHED
SCHEDULED
CONFIRMED
IN_PROGRESS
FULFILLED
ACTIVE
INACTIVE
ARCHIVED
```

L’état reste celui de l’owner.

Interdit :

```text
BusinessEntry.state =
PREPARING / UPCOMING / ONGOING / BLOCKED / DONE
```

comme vérité transverse.

---

# 30. Faits, temps, géographie et relations

```text
FACTS[]
→ 0..n

TEMPORAL_FACTS[]
→ 0..n

SPATIAL_FACTS[]
→ 0..n

RELATIONS[]
→ 0..n
```

Exemples relationnels :

```text
Departure
→ uses Vehicle

Session
→ belongs to Programme

Order
→ concerns Offer

Journey
→ concerns Activity
```

Les relations sont owner-backed.

Relation ≠ fusion.

---

# 31. `CONTINUITY_FACET`

Décision finale :

```text
BUSINESS_ENTRY
→ 0..1 CONTINUITY_FACET
```

Pas :

```text
Métier
→ OperationalContinuities[]
```

universel.

Définition :

> projection complémentaire indiquant qu’une Business Entry participe à une progression opérationnelle encore intelligible.

Structure :

```text
CONTINUITY_FACET
├── CONTINUITY_IDENTITY                1
├── NEXT[]                             0..n
├── BLOCKERS[]                         0..n
├── HORIZON?                           0..1
└── OUTCOME?                           0..1
```

---

# 32. Quand la Continuity Facet est naturelle

Exemples :

```text
Occurrence / Departure
CommerceOrder
Service case
Admission
Journey réellement opéré
Demande
Prestation
Dossier
certaines Funding applications
```

Elle n’est pas requise par défaut pour :

```text
Route
Vehicle
Place
Offer
Programme
```

Ces réalités peuvent être actives sans être une continuité en cours.

---

# 33. Pourquoi En cours Me n’est pas copié

Le contrat personnel possède :

```text
SETTLED
MY_SIDE
ELSEWHERE
MAKOLO
SYSTEM_OR_TIME
```

Ces dimensions répondent au besoin d’une personne bénéficiaire.

Métier Space a besoin d’une lecture opérateur.

Il conserve donc une Continuity Facet plus petite.

---

# 34. `NEXT[]`

Cardinalité :

```text
0..n
```

Plusieurs suites peuvent exister.

Ne pas forcer un faux prochain step unique.

---

# 35. `BLOCKERS[]`

Cardinalité :

```text
0..n
```

Structure :

```text
BLOCKER
├── SOURCE
├── BLOCKED_TRANSITION
├── HORIZON?
└── ALTERNATIVES[]
```

Toujours :

```text
WAITING
≠ BLOCKED

RISK
≠ BLOCKED

UNKNOWN
≠ BLOCKED
```

Un Requirement absent ou un Payment pending n’est blocker que si une transition réelle est empêchée et que l’owner/résolveur l’établit.

---

# 36. `HORIZON` et `OUTCOME`

```text
HORIZON
→ 0..1

OUTCOME
→ 0..1
```

Un résultat intermédiaire ne ferme pas forcément la continuité.

Invariant Commerce :

```text
Order confirmé
≠ Obtention accomplie

Payment réussi
≠ Obtention accomplie
```

L’owner vertical reconnaît le résultat réel.

---

# 37. Responsabilité, autorité et capabilities au niveau Entry

```text
RESPONSIBILITY[]
→ 0..n

AUTHORITY
→ 0..1 effective projection

CAPABILITIES[]
→ 0..n
```

Une capability informe la Presentation.

Elle ne remplace jamais la vérification serveur lors de la mutation.

---

# 38. TOCTOU

Flux possible :

```text
GET Métier
→ capability manage visible

Mandate révoqué

mutation
→ serveur refuse
```

Ce comportement est correct.

---

# 39. `KNOWLEDGE_CONTEXT`

Cardinalité :

```text
1
```

Structure possible :

```text
PROVENANCE[]
FRESHNESS
KNOWLEDGE_STATE
CONFIDENCE?
```

États :

```text
KNOWN
UNKNOWN
CONTRADICTORY
STALE
UNAVAILABLE
```

Le client ne transforme pas :

```text
unknown → false
unavailable → zero
```

---

# 40. Fraîcheur métier vs snapshot local

Toujours séparer :

```text
SERVER KNOWLEDGE FRESHNESS
≠
CLIENT SNAPSHOT AGE
```

---

# 41. `MEDIA_BINDINGS[]`

Cardinalité :

```text
0..n
```

Structure :

```text
MEDIA_BINDING
├── RESOURCE
├── TARGET
└── PURPOSE
```

Purposes possibles :

```text
RECOGNIZE
UNDERSTAND
ESTABLISH
PREPARE
ACT
```

No Orphan Media reste absolu.

---

# 42. Actions de création

Structure conceptuelle :

```text
CREATE_ACTION
├── INTENT                            1
├── OWNER_REFERENCE                   1
├── CONTEXT                           1
├── CAPABILITY                        1
├── HANDOFF                           1
└── INTERACTION_DEPTH                 1
```

Cardinalité :

```text
0..n
```

par Perspective ou Section.

Pour afficher une création, il faut :

```text
capacité métier réelle
+
contexte suffisamment déterminé
+
autorité suffisante
+
handoff réel
```

Pas seulement une Permission générique.

---

# 43. Aucun méga-menu Créer

Interdit :

```text
+ Créer
├ Activity
├ Occurrence
├ Journey
├ Requirement
├ Access
├ Capacity
├ Funding
└ ...
```

Le contexte métier parle naturellement.

Transport :

```text
Nouveau départ
Nouvelle route
Nouveau véhicule
```

Programmes :

```text
Nouveau programme
Nouvelle session
```

Prestations :

```text
Nouvelle prestation
```

Commerce :

```text
Nouvelle offre
```

lorsque les owners les supportent réellement.

---

# 44. Empty state

Un empty réel exige :

```text
COMPOSITION_STATE = ESTABLISHED
```

et une Perspective connue.

Avec création possible :

> **Aucun programme pour le moment.**  
> **Créer un programme**

Sans droit de création :

> **Aucun programme visible pour le moment.**

Aucun faux CTA.

Aucune Activity fictive ne doit être créée pour meubler l’état vide.

---

# 45. Section vide

Une section vide non informative peut disparaître.

Une section structurante peut rester lorsqu’elle porte :

```text
un empty utile
ou
une création légitime
```

---

# 46. Pagination et bornes

La racine doit rester bornée.

Structure :

```text
SECTION
├── entries[]
└── continuation?
```

`CONTINUATION` :

```text
0..1
```

Peut être :

```text
cursor
page
owner handoff
```

La limite runtime actuelle de 20 éléments n’est pas une constante conceptuelle.

---

# 47. Pas de scroll infini comme modèle produit

```text
pagination technique
≠ infinite work feed
```

Les grandes collections doivent disposer de profondeurs adaptées.

---

# 48. Historique

Décision :

```text
HISTORY
= profondeur temporelle du monde Métier
```

Pas une nouvelle porte primaire.

Exemples :

```text
Prestations
→ En cours / Terminées

Départs
→ À venir / Passés

Programmes
→ Actuels / Passés

Commandes
→ Actives / Terminées
```

La racine historique reste bornée, récente ou utile.

---

# 49. Ordering

Le serveur fournit l’ordre.

L’ordre peut dépendre de :

```text
temps
ordre owner
séquence métier
importance opérationnelle établie
nom
```

Le client ne choisit pas un tri global par `created_at`, `updated_at` ou popularité.

---

# 50. Tri utilisateur

Un tri peut exister si le contrat le supporte réellement.

Exemples :

```text
Date
Nom
Lieu
État exposé
```

Pas d’enums backend bruts.

---

# 51. Search Métier

Question :

> **Parmi ce que nous opérons déjà, retrouver quoi ?**

Exemple Transport :

```text
query = Kolwezi
```

peut retrouver :

```text
Route Lubumbashi–Kolwezi
Départ de 14 h
Lieu Kolwezi
```

Métier Search ≠ Discover Search.

Si aucun search owner-safe n’existe :

```text
pas de Search
```

plutôt qu’un champ trompeur.

---

# 52. Filtres

Peuvent porter sur :

```text
période
lieu
section
perspective
état métier exposé
relation
```

Éviter le jargon backend comme texte primaire.

---

# 53. Scope Activity-limited

Si le viewer possède uniquement une autorité sur `Activity X`, Métier expose seulement ce qui peut légitimement être rattaché à ce scope.

Exemples :

```text
Activity X
Occurrence X1
Journey X
Offer liée à X si permission
```

Pas :

```text
toute la flotte
toutes les routes
toutes les commandes
tout le footprint
tous les programmes
```

Une Perspective Activity-limited peut employer un langage plus spécifique que le langage principal du Space.

---

# 54. Permission denied

## 54.1 Aucun accès légitime au Space

```text
privacy-safe not found / denied
```

selon le contrat serveur courant.

## 54.2 Accès Space mais action interdite

L’Entry peut rester visible.

L’action sensible disparaît ou est refusée proprement.

## 54.3 Autorité révoquée après chargement

```text
snapshot ancien
→ peut encore exister localement

mutation
→ serveur refuse

refresh
→ projection retirée/réduite
```

La capability cache n’est jamais un token.

---

# 55. Données privées

Business Entry racine ne doit pas exposer automatiquement :

```text
beneficiary email
Requirement evidence privée
Proof evidence
AccessCredential
QR/token
notes staff
storage keys
Payment details inutiles
```

La racine montre uniquement ce qui est nécessaire pour comprendre le travail.

---

# 56. Loading

Préférer :

```text
contenu actuel
+ indicateur discret
→ contenu mis à jour
```

à :

```text
contenu
→ vide
→ skeleton
→ contenu
```

Sans snapshot :

```text
first availability
```

sans fabrication de données.

---

# 57. Refresh

Conserver :

```text
Space
Responsibility Perspective
Business Perspective
query
filters
section
scroll
selected Business Entry
depth
```

Un refresh ne change pas la vérité ni l’autorité.

---

# 58. Back

Après :

```text
Métier
→ Commande 493
→ owner depth
```

Back restaure autant que possible :

```text
Commerce
section Commandes
scroll
filters
query
```

---

# 59. Resume

Après interruption :

```text
surface
Space
Perspective
Section
selection
scroll
query
filters
```

peuvent être restaurés.

Une sélection locale ancienne ne donne aucune autorité.

---

# 60. Mutation

Flux :

```text
Métier
→ owner action
→ owner truth changes
→ refetch
→ reprojection
```

Un état local pending reste distinct de la vérité serveur.

---

# 61. Success

Confirmer uniquement le niveau réellement atteint.

```text
draft local
≠ submitted

outbox queued
≠ sent

Payment requested
≠ paid

Order confirmed
≠ Obtention accomplished
```

---

# 62. Error partielle

Une panne locale ne doit pas rendre toute la surface inutilisable.

Exemple :

```text
Programmes      established
Sessions        established
Admissions      unavailable
Resources       established
```

Métier reste visible.

Une erreur importante doit répondre :

1. qu’est-ce qui a échoué ?
2. qu’est-ce qui a été conservé ?
3. que puis-je encore faire ?

---

# 63. Offline

Avec snapshot :

```text
content + offline
```

Le monde Métier reste reconnaissable.

---

# 64. Snapshot local

Peut conserver, selon sécurité :

```text
Business Perspectives
Sections
Entry identities
representations
owner states observés
facts autorisés
temporal facts
spatial facts
links
capabilities observées
media cache autorisé
```

---

# 65. Cache viewer-scoped

La clé logique doit préserver :

```text
authenticated Profile
+
acting Space
+
scope
+
perspective
```

Un changement de compte ne doit jamais réutiliser le snapshot privé d’un autre Profile.

---

# 66. Offline ne recrée pas l’autorité

Interdits :

```text
cached capability
→ current Permission

cached Mandate
→ current authority
```

---

# 67. Offline ne recrée pas les vérités temps réel

Ne pas affirmer depuis un vieux snapshot :

```text
current Capacity
current Access
current Payment
current Operations
current Live
current blocker
current availability
```

si une fraîcheur serveur est nécessaire.

---

# 68. Mutations offline

Seulement si l’owner possède un vrai contrat :

```text
local-first mutation
idempotency
outbox
retry
conflict semantics
```

Sinon :

```text
lecture offline
→ oui

mutation sensible
→ attendre reconnexion
```

---

# 69. Jour J depuis Métier

Une Entry Occurrence peut proposer :

```text
Ouvrir Jour J
```

si :

```text
Occurrence pertinente
+
perspective opérateur
+
autorité
```

Jour J reste occurrence-scoped.

```text
Space
≠ Live

Space
≠ Jour J
```

---

# 70. Live

Live est une profondeur opérationnelle de l’Occurrence.

Il ne doit jamais être déduit uniquement depuis l’heure.

Un Space peut avoir plusieurs Occurrences actuelles sans devenir globalement Live.

---

# 71. Densité et confort

Métier est une surface de densité :

```text
moyenne à élevée
```

Cela signifie : davantage de réalités visibles, correctement structurées.

Pas : cockpit ERP compacté.

---

# 72. Compact

Principe :

```text
une Perspective
→ sections verticales
→ entries
→ détail en profondeur
```

Pas de table multi-colonnes miniature.

---

# 73. Medium

Peut utiliser la largeur pour :

```text
section
+
aperçu
```

si cela améliore réellement la lecture.

---

# 74. Wide

Un split peut apparaître seulement lorsque deux rôles cognitifs distincts existent réellement :

```text
collection
+
détail sélectionné
```

Wide ≠ ERP.

Interdits :

```text
sidebar permanente de modules
cockpit de KPI
panneaux multiples décoratifs
dense data grid par défaut
```

---

# 75. Conservation adaptative

Lors de :

```text
Compact → Medium
Medium → Wide
rotation
resize
```

préserver :

```text
Space
Responsibility Perspective
Business Perspective
section
selection
depth
focus
scroll
filters
query
```

Responsive ≠ nouvelle vérité métier.

---

# 76. Archétype `generic`

Perspective primaire :

```text
Activités
```

Composition possible :

```text
ACTIVITÉS
├── Activités
├── À préparer
├── À venir
├── En cours
├── Demandes
├── Lieux
└── Historique
```

Les verticales supplémentaires apparaissent seulement lorsqu’elles existent réellement.

État vide : ne jamais créer une Activity fictive.

---

# 77. Archétype `creative`

Perspective primaire :

```text
Créations
```

Composition :

```text
CRÉATIONS
├── Créations
├── Événements
├── Prestations réelles
├── Occurrences
└── Offres réellement opérées
```

Interdits :

```text
feed
Story
portfolio parallèle générique
média orphelin
faux publics
fausses offres
```

---

# 78. Archétype `media`

Perspective primaire :

```text
Productions
```

Composition :

```text
PRODUCTIONS
├── Productions
├── Événements
├── Prestations éventuelles
└── Occurrences
```

Publics et partenaires restent principalement relationnels.

Aucun CMS social générique n’est déduit.

---

# 79. Archétype `education`

Perspective primaire :

```text
Programmes
```

Composition possible :

```text
PROGRAMMES
├── Programmes
├── Prochaines sessions
├── Admissions / demandes
├── À préparer
├── En cours
├── Bloqués
├── Ressources pertinentes
└── Historique
```

Une profondeur Programme peut composer :

```text
Sessions
Requirements
Forms
Resources
Groups / cohortes
Capacity
Access
```

Le viewer doit avoir l’impression de gérer un Programme, une Session ou une Admission, pas de naviguer dans les abstractions backend.

---

# 80. Archétype `commerce`

Perspective primaire :

```text
Commerce
```

Chaîne humaine :

```text
ce que nous rendons disponible
→ offre
→ demande / commande
→ préparation / disponibilité
→ remise / réalisation
→ obtention accomplie
```

Composition :

```text
COMMERCE
├── Offres
├── Commandes à traiter
├── À préparer
├── À remettre / réaliser
├── Disponibilité
└── Historique
```

Payment apparaît seulement lorsqu’il compte réellement.

Toujours :

```text
Order
≠ Obtention accomplie

Payment
≠ Obtention accomplie
```

---

# 81. Archétype `service_provider`

Perspective primaire :

```text
Prestations
```

Composition :

```text
PRESTATIONS
├── Prestations proposées
├── Demandes
├── À préparer
├── En traitement
├── Bloquées
├── À délivrer
└── Terminées
```

Une profondeur Dossier peut composer :

```text
personne concernée
Requirements
étapes utiles
responsable
pièces / ressources
Payment éventuel
résultat
```

L’interface doit donner l’impression de traiter un service, pas de naviguer dans Journey.

---

# 82. Archétype `transport_operator`

Perspective primaire :

```text
Transport
```

Composition cible :

```text
TRANSPORT
├── Aujourd'hui
├── Prochains départs
├── Départs actifs
├── Routes
├── Véhicules
├── Services
├── Lieux
└── Historique
```

Une Entry Départ peut ouvrir :

```text
Départ
├── préparation
├── Jour J
│   └── Live
├── véhicule
├── Capacity
├── voyageurs / Access selon autorité
├── contrôle
└── incidents
```

Route, Vehicle et Place sont des réalités structurelles ; elles ne doivent pas être placées automatiquement dans `En cours`.

---

# 83. Archétype `community`

Perspective primaire :

```text
Initiatives
```

Composition :

```text
INITIATIVES
├── Initiatives
├── Activities
├── Événements
├── Actions terrain
└── Programmes réels
```

Funding peut être :

```text
Discover
→ possibilité

Métier
→ réalité réellement engagée/opérée

Now
→ conséquence actuelle

Piloter
→ signal
```

selon son contexte réel.

---

# 84. Anti-features

Interdits :

```text
WorkItem universel
BusinessTask universel
lifecycle universel PREPARING/ONGOING/DONE
task manager
kanban générique
ERP de modules
state owner réinterprété client
Requirement missing → Blocked
Payment pending → Blocked
Occurrence scheduled → Live
création générique par taxonomie
feed chronologique
dashboard KPI
contenu orphelin
média orphelin
```

---

# 85. Contrat final serveur

Le serveur possède :

- résolution du Space ;
- résolution du viewer ;
- autorité réelle ;
- responsibility perspectives ;
- Operational Footprint ;
- perspectives métier ;
- sections ;
- couverture ;
- Business Entries ;
- owner references ;
- owner states ;
- Continuity Facet lorsque légitime ;
- blockers owner-backed ;
- capabilities ;
- handoffs ;
- création contextuelle ;
- ordering ;
- pagination ;
- confidentialité ;
- fraîcheur métier.

Le serveur ne doit pas :

- créer un `WorkItem` universel ;
- inventer un lifecycle transverse ;
- exposer des données privées pour simplifier le client ;
- transformer l’archétype en Permission ;
- considérer le Footprint comme autorité ;
- transformer tout `active=true` en En cours ;
- dupliquer les owners.

---

# 86. Contrat final client

Web et Flutter possèdent :

```text
layout
density
responsive geometry
formatting
navigation state
scroll
focus
query UI
filters UI
offline snapshot
pending UI
media viewer
```

Ils ne doivent jamais faire :

```text
Assignment → Permission
Team → Authority
Archetype → Perspective obligatoire
Archetype → relevance
Footprint → Permission
Owner state → lifecycle universel
Requirement missing → Blocked
Payment pending → Blocked
Scheduled → Live
cached capability → current authority
kind → invented owner URL
```

---

# 87. Cardinalités racine finales

| Élément | Cardinalité |
|---|---:|
| Actor Context | 1 |
| Viewer | 1 |
| Viewer Relation | 1 |
| Authority Context | 1 |
| Responsibility Perspectives | 0..n |
| Selected Responsibility Perspective | 0..1 |
| Archetype | 1 |
| Operational Footprint | 0..1 |
| Composition State | 1 |
| Business World | 1 |
| Preferred Language | 1 |
| Business Perspectives | 0..n |
| Selected Business Perspective | 0..1 |

---

# 88. Cardinalités Business Perspective

| Élément | Cardinalité |
|---|---:|
| Perspective Identity | 1 |
| Representation | 1 |
| Coverage State | 1 |
| Sections | 0..n |
| Creation Actions | 0..n |
| Owner Handoffs | 0..n |

---

# 89. Cardinalités Business Section

| Élément | Cardinalité |
|---|---:|
| Section Identity | 1 |
| Representation | 1 |
| Section Role | 0..1 |
| Coverage State | 1 |
| Entries | 0..n |
| Continuation | 0..1 |
| Actions | 0..n |
| Handoffs | 0..n |

---

# 90. Cardinalités Business Entry

| Élément | Cardinalité |
|---|---:|
| Entry Identity | 1 |
| Subject | 1 |
| Representation | 1 |
| Owner Reference | 1 conceptuellement |
| Owner State | 0..1 |
| Facts | 0..n |
| Temporal Facts | 0..n |
| Spatial Facts | 0..n |
| Relations | 0..n |
| Continuity Facet | 0..1 |
| Responsibilities | 0..n |
| Authority | 0..1 |
| Capabilities | 0..n |
| Owner Handoffs | 0..n |
| Knowledge Context | 1 |
| Media Bindings | 0..n |

---

# 91. Cardinalités Continuity Facet

| Élément | Cardinalité |
|---|---:|
| Continuity Identity | 1 |
| Next | 0..n |
| Blockers | 0..n |
| Horizon | 0..1 |
| Outcome | 0..1 |

---

# 92. Réponse conceptuelle finale

```text
SPACE BUSINESS RESPONSE
│
├── ACTOR_CONTEXT
├── VIEWER
├── VIEWER_RELATION
│   ├── AUTHORITY_CONTEXT
│   ├── RESPONSIBILITY_PERSPECTIVES[]
│   └── SELECTED_RESPONSIBILITY?
│
├── ARCHETYPE
├── OPERATIONAL_FOOTPRINT?
├── COMPOSITION_STATE
│
└── BUSINESS_WORLD
    ├── PREFERRED_LANGUAGE
    ├── SELECTED_PERSPECTIVE?
    │
    └── PERSPECTIVES[]
        ├── PERSPECTIVE_IDENTITY
        ├── REPRESENTATION
        ├── COVERAGE_STATE
        ├── CREATION_ACTIONS[]
        ├── OWNER_HANDOFFS[]
        │
        └── SECTIONS[]
            ├── SECTION_IDENTITY
            ├── REPRESENTATION
            ├── SECTION_ROLE?
            ├── COVERAGE_STATE
            ├── CONTINUATION?
            ├── ACTIONS[]
            │
            └── ENTRIES[]
                ├── ENTRY_IDENTITY
                ├── SUBJECT
                ├── REPRESENTATION
                ├── OWNER_REFERENCE
                ├── OWNER_STATE?
                ├── FACTS[]
                ├── TEMPORAL_FACTS[]
                ├── SPATIAL_FACTS[]
                ├── RELATIONS[]
                ├── CONTINUITY_FACET?
                │   ├── CONTINUITY_IDENTITY
                │   ├── NEXT[]
                │   ├── BLOCKERS[]
                │   ├── HORIZON?
                │   └── OUTCOME?
                ├── RESPONSIBILITY[]
                ├── AUTHORITY?
                ├── CAPABILITIES[]
                ├── OWNER_HANDOFFS[]
                ├── KNOWLEDGE_CONTEXT
                └── MEDIA_BINDINGS[]
```

---

# 93. Critères de sortie serveur

Une implémentation Mature doit démontrer :

- `ACTOR_CONTEXT = Space` ;
- `VIEWER = Profile` ;
- résolution privacy-safe du Space ;
- Activity-limited correctement borné ;
- responsibility perspective distincte de l’autorité ;
- archétype distinct du Footprint ;
- perspectives dérivées du monde réel ;
- sections contextuelles ;
- conservation des owner states ;
- aucune table WorkItem ;
- aucune migration de statut universel ;
- Continuity Facet seulement lorsque légitime ;
- blocker owner-backed ;
- création contextuelle owner-backed ;
- owner handoffs réels ;
- pagination bornée ;
- composition partial/unavailable honnête ;
- aucune PII inutile ;
- IDOR couvert ;
- TOCTOU couvert ;
- aucun Membership pris pour autorité.

---

# 94. Critères de sortie Web / Flutter

Les clients doivent démontrer :

- vocabulaire métier humain ;
- conservation du Space ;
- conservation de la responsabilité ;
- conservation de la Perspective ;
- conservation du scroll ;
- conservation des filtres/query ;
- Back correct ;
- Resume correct ;
- Refresh sans écran blanc destructeur ;
- partial localisé ;
- empty distinct de unavailable ;
- offline honnête ;
- aucune authority recalculée ;
- aucune URL owner inventée ;
- aucune conversion générique owner-state → work-state ;
- aucune création générique ;
- aucun feed ;
- aucun cockpit ERP par défaut ;
- adaptation Compact/Medium/Wide sans changer la vérité.

---

# 95. Tests sémantiques minimaux

Doivent être couverts :

```text
Space direct authority
Activity-only authority
multi-Activity authority
foreign Activity
revoked Mandate

TeamMembership-only
GroupMembership-only
Platform-only

empty réel
partial composition
unavailable source

Vehicle active
→ structural, pas automatiquement En cours

Route active
→ structural, pas automatiquement En cours

Journey avec blocker owner actif
→ Bloqué

Requirement absent seul
→ pas blocker automatique

Payment pending seul
→ pas blocker automatique

Order confirmed
→ pas Obtention accomplie

transport vide + create permission
→ empty + création contextuelle

transport vide sans permission
→ empty sans CTA

owner link absent
→ aucun URL inventé

refresh
→ contexte conservé

back
→ perspective + section + scroll restaurés

offline
→ snapshot, pas vérité Live

account switch
→ aucune fuite cache inter-Profile
```

---

# 96. Tests par archétype

Minimum :

```text
generic
creative
media
education
commerce
service_provider
transport_operator
community
```

Pour chacun :

- bon langage ;
- aucune Permission induite ;
- Perspective vide correcte ;
- sections réelles seulement ;
- création contextuelle si réellement supportée ;
- absence de domaine fictif.

---

# 97. Performance

La racine doit rester bornée.

Principes :

```text
pas de toute-la-base
pas de N+1 par Entry
pas de préchargement des profondeurs owner
pas de toute-l'histoire
```

Utiliser :

```text
select_related
prefetch_related
owner selectors
pagination/continuation
```

selon les owners.

Avant cache : réduire, borner, précharger correctement.

Le cache ne doit pas devenir une seconde vérité.

---

# 98. Migrations

Le contrat cible ne nécessite intrinsèquement aucune migration.

Une future migration doit être justifiée par un besoin métier réel dans un owner canonique.

Ne pas créer de migration seulement pour :

```text
BusinessEntry
Perspective
Section
ContinuityFacet
CompositionState
```

car ce sont des projections UX.

---

# 99. Molongo

Molongo peut plus tard aider :

```text
composition
ordre
mise en avant
relations
résolution contextuelle
```

Mais aucun futur contrat Molongo n’est figé ici.

Molongo ne devient pas propriétaire des vérités métier.

---

# 100. Backend générique, métier contextuel

Le backend peut partager :

```text
ObjectProjection
OwnerReference
Capability
Handoff
KnowledgeContext
MediaBinding
Pagination
```

Mais l’interface parle :

```text
Transport
Programmes
Prestations
Commerce
Créations
Productions
Initiatives
Activités
```

---

# 101. Formulation canonique finale

> **Métier Space est la projection durable du monde opérationnel réellement porté par un Space. Il organise les vérités propriétaires en Perspectives et Sections humaines adaptées au métier, sans recréer leurs modèles ni leurs états. Une Business Entry représente une réalité owner-backed et ne reçoit une Continuity Facet que lorsqu’une progression réelle existe. L’archétype donne le langage principal, l’Operational Footprint décrit ce qui existe réellement, la responsabilité organise la lecture et l’autorité détermine ce que le viewer peut connaître et faire.**

---

# 102. Formulation produit

> **Métier montre ce que votre Space fait réellement vivre, prépare, opère et délivre — dans le langage naturel de votre activité, sans vous obliger à comprendre la structure technique de Makolo.**

---

# 103. Points volontairement non figés

Restent ouverts :

1. noms JSON définitifs ;
2. `schema_version` ;
3. identifiants wire exacts des Perspectives ;
4. identifiants wire exacts des Sections ;
5. contrat Search Métier final ;
6. politiques de tri exactes ;
7. pagination/cursor owner-specific ;
8. profondeur Route/Vehicle lorsqu’un owner stable existe ;
9. granularité finale de cache local ;
10. exact comportement des créations par verticale ;
11. Golden visuel Métier détaillé ;
12. seuils exacts Compact/Medium/Wide ;
13. extensions Molongo futures ;
14. politique détaillée de `CoverageState` si plusieurs sources contribuent à une même Section.

Aucun de ces points ne justifie un nouveau modèle persistant transverse.

---

# 104. Statut de fermeture

Le noyau conceptuel de Métier Space est considéré **gelé** autour de :

```text
Space
→ Business World
→ Business Perspectives
→ Business Sections
→ Business Entries
→ optional Continuity Facet
→ owner depth
```

avec :

```text
Archetype
→ langage

Operational Footprint
→ réel opéré

Responsibility
→ angle de lecture

Authority
→ droit réel

Presentation
→ composition humaine
```

Ce contrat peut désormais servir de base à :

```text
server projection
→ Web Presentation
→ Flutter Presentation
```

sans recréer un ERP, un WorkItem universel ou une seconde vérité métier.
