# Makolo — Contrat consolidé Mark et Post-Mark
## Intention, cadrage, création, circulation et entrée dans le réseau d’action

**Statut :** contrat conceptuel consolidé  
**Date :** 2026-10-06  
**Portée :** Mark commun, Mark Me, Mark Space, cadrage progressif, création owner-backed, circulation, articulation avec Molongo, Discover et le réseau d’action  
**Dépôt officiel :** `TraditionLearningCommunity/makolo`  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 0. Objet

Ce document consolide le contrat de **Makolo Mark** et la chaîne **post-Mark**.

Il fixe :

- ce qu’est Mark ;
- ce que Mark n’est pas ;
- le noyau commun Mark ;
- les variantes de gravité `Me` et `Space` ;
- les intentions supportées ;
- la distinction `RETRIEVE` / `EXPLORE` ;
- la création d’Activity par un Profile ou un Space ;
- le cadrage progressif ;
- la création précoce de brouillons owner-backed ;
- les gates d’identité, de circulation et d’opération ;
- l’enrichissement facultatif ;
- le comportement sans LLM ;
- les clarifications et confirmations ;
- les handoffs ;
- ce qui se passe après mise en circulation ;
- la frontière entre owners, Mayele, Molongo, Discover et Presentation ;
- le rôle exclusif de Molongo dans la pertinence ;
- les anti-features et critères de sortie.

Ce document ne crée pas :

- un modèle `MarkObject` ;
- un modèle `MarkTask` ;
- un modèle `MarkDraft` métier parallèle ;
- un moteur de recherche Mark ;
- un moteur de pertinence Mark ;
- un moteur de pertinence Discover ;
- un système de validation éditoriale Makolo générique ;
- un score de complétude ;
- un score de qualité ;
- un feed social ;
- une logique de followers / likes / popularité ;
- un LLM obligatoire ;
- une nouvelle vérité métier.

---

# 1. Mark n’est pas une surface supplémentaire

Mark apparaît au centre de la navigation.

Mais :

```text
MARK
≠ cinquième destination permanente
```

Mark est :

```text
MARK
=
mode transitoire d’intention
+
cadrage
+
orchestration
+
handoff
```

Il peut occuper temporairement tout l’écran sur mobile ou une zone focalisée sur écran large.

Il ne possède pas un « monde Mark » persistant comparable à :

```text
Maintenant
Découvrir
En cours
Moi
Métier
Nous
```

---

# 2. Question humaine de Mark

Mark répond essentiellement à :

> **Qu’avez-vous en tête ?**

Dans un Space, le contexte peut rendre la formulation plus explicite :

> **Qu’avez-vous en tête pour Mulykap ?**

Le nom exact reste Presentation.

L’invariant est :

```text
ACTOR_CONTEXT
doit être évident.
```

---

# 3. Mark est l’entrée, pas le propriétaire

Mark peut recevoir :

```text
intention
texte
source
fichier
photo
URL
share-in
voix transformée en texte
starter structuré
```

mais il remet la réalité au domaine propriétaire.

Exemple :

```text
"Je veux présenter mon atelier"
↓
Mark
↓
Activity owner
```

Mark ne devient jamais owner de l’atelier.

---

# 4. Un seul Mark, contextualisé

Il n’existe pas deux produits indépendants :

```text
Mark Me
Mark Space
```

Il existe :

```text
MARK CORE
```

avec deux contextes d’acteur :

```text
Me
→ actor = Profile

Space
→ actor = Space
viewer = Profile
```

---

# 5. Gravité Me et Space

La différence est une **gravité d’usage**, pas une capacité absolue.

```text
ME
→ davantage consommation, continuité, apport
→ mais peut produire

SPACE
→ davantage production, opération, délivrance
→ mais peut consommer
```

---

# 6. Profile peut produire

Un Profile peut porter une Activity.

Donc :

```text
Profile
→ Mark
→ create Activity
```

est un chemin normal.

Il ne faut pas forcer :

```text
production
→ Space obligatoire
```

---

# 7. Space peut consommer

Un Space peut exprimer :

```text
Nous cherchons un partenaire.
Nous avons besoin d’un financement.
Nous cherchons un lieu.
```

Mark prépare alors un contexte d’exploration et remet à Space Discover.

---

# 8. Mark ne possède pas la recherche ouverte

Distinction fondamentale :

```text
RETRIEVE
≠ EXPLORE
```

## `RETRIEVE`

Retrouver une réalité déjà connue, possédée, engagée, sauvegardée ou explicitement désignée.

Exemples :

```text
Retrouve mon billet.
Où est mon dossier ?
Ouvre la commande 493.
Retrouve le départ de demain.
```

Mark utilise les selectors / owners appropriés.

## `EXPLORE`

Exprimer ce que l’acteur cherche à vivre, faire, obtenir ou trouver dans un champ ouvert.

Exemples :

```text
Je cherche une formation.
Je veux aller à Kolwezi.
Nous cherchons un partenaire.
Nous cherchons un financement.
```

Mark ne fournit pas lui-même les résultats.

Chaîne :

```text
intention Mark
↓
Exploration Context
↓
Discover
```

Donc :

```text
MARK
≠ moteur de recherche ouvert

DISCOVER
= surface d’exploration
```

---

# 9. Familles d’intention communes

Le noyau Mark peut résoudre conceptuellement :

```text
RETRIEVE
EXPLORE
CONTINUE
CREATE
UPDATE
ACT
CONTRIBUTE
```

Ces noms ne sont pas nécessairement des enums persistants.

`CONTINUE` retrouve une poursuite et remet à `En cours`, `Métier` ou l’owner.

`CREATE` fait exister une réalité chez son owner.

`UPDATE` modifie une réalité existante chez son owner.

`ACT` produit une conséquence opérationnelle.

`CONTRIBUTE` apporte une information ou ressource sans déterminer prématurément sa nature métier.

---

# 10. Contribution ≠ vérité

Toujours :

```text
fichier reçu
≠ Proof acceptée

document
≠ Requirement satisfait

photo
≠ observation vérifiée

texte
≠ fait canonique
```

---

# 11. Structure conceptuelle de Mark

```text
MARK INVOCATION
│
├── ACTOR_CONTEXT                  1
├── VIEWER                         1
├── INVOCATION_CONTEXT?           0..1
├── INPUT                          1
├── SOURCES[]                      0..n
├── AVAILABLE_STARTERS[]           0..n
└── LOCAL_INPUT_DRAFT?             0..1
```

`ACTOR_CONTEXT` vaut Profile en Me et Space en contexte collectif.

`VIEWER` reste toujours un Profile humain.

---

# 12. Invocation Context

Peut contenir légitimement :

```text
surface courante
owner courant
Possibility sélectionnée
Activity
Occurrence
Journey
Requirement
Business Entry
responsibility perspective
Exploration Context
```

Mais :

```text
INVOCATION_CONTEXT
≠ Permission
≠ Mandate
```

---

# 13. Modalités d’entrée

Conceptuellement :

```text
TEXT
VOICE_AS_TEXT
FILE_REFERENCE
IMAGE_REFERENCE
URL
SHARE_IN
STRUCTURED_STARTER
```

Une modalité n’est exposée que lorsqu’un intake réel existe.

---

# 14. Available Starters

Les starters rendent Mark utile sans IA.

Exemples Me :

```text
Présenter quelque chose
Ajouter un document
Continuer une démarche
Retrouver quelque chose
```

Exemples Space Transport :

```text
Nouveau départ
Nouvelle route
Trouver un partenaire
```

Un starter doit être contextualisé et owner-backed.

Il n’est pas un catalogue générique d’outils.

---

# 15. Pipeline Mark commun

```text
EXPRIMER
↓
ANCRER LE CONTEXTE
↓
RÉSOUDRE L’INTENTION
↓
IDENTIFIER L’OWNER
↓
CADRER SI NÉCESSAIRE
↓
CLARIFIER UNIQUEMENT SI BLOQUANT
↓
CRÉER / RETROUVER / PRÉPARER CHEZ L’OWNER
↓
ATTEINDRE LE MINIMUM REQUIS
↓
CONFIRMER SI CONSÉQUENCE SIGNIFICATIVE
↓
OWNER ACTION
↓
HANDOFF / CONTINUATION
```

---

# 16. Mark bref et Mark de cadrage

Mark peut être bref :

```text
Retrouve mon billet.
→ resolve
→ open owner
```

Il peut aussi devenir un atelier temporaire :

```text
Je veux présenter mon atelier.
→ Activity draft
→ cadrage
→ circulation
```

Règle :

> **Mark reste tant qu’il réduit réellement la friction de cadrage ou d’orchestration.**

Il sort dès qu’un owner ou une surface devient un meilleur lieu pour la suite.

---

# 17. Pas de conversation persistante générique

Plusieurs tours Mark ne créent pas automatiquement :

```text
ChatThread
ConversationHistory
MarkMessage
```

persistants.

---

# 18. Mark Input Draft

Avant owner identifié :

```text
MARK_INPUT_DRAFT
```

peut conserver localement :

```text
texte
source
fichier
intention en cours
```

Ce n’est pas une vérité métier.

---

# 19. Owner Draft

Dès qu’un owner et une identité suffisante sont établis :

```text
MARK_INPUT_DRAFT
↓
OWNER_DRAFT
```

Exemple :

```text
Activity Draft
```

Le Draft owner devient la vérité de travail.

Pas de double vérité durable Mark + owner.

---

# 20. Créer tôt

Invariant :

```text
IDENTITY suffisante
↓
CREATE OWNER DRAFT EARLY
```

Cela permet :

- autosave owner-backed ;
- reprise plus tard ;
- enrichissement progressif ;
- réduction de la perte de travail ;
- absence de méga-formulaire temporaire.

---

# 21. Exemple Activity personnelle

Entrée :

> Je veux présenter mon atelier de fabrication de meubles.

Mark peut établir :

```text
actor = Profile Jean
intent = CREATE
owner = Activity
title = Atelier de fabrication de meubles
```

Puis créer :

```text
Activity
owner_profile = Jean
status = DRAFT
```

---

# 22. Pas de validation Makolo générique

Makolo n’est pas :

```text
creator
→ submit
→ équipe Makolo
→ approval
→ publish
```

par défaut.

Une approbation n’existe que lorsqu’un domaine owner la prévoit réellement.

Donc :

```text
DRAFT
≠ EN ATTENTE DE VALIDATION
```

par défaut.

---

# 23. Cadrage progressif

Mark ne cherche pas à remplir tous les champs.

Il cherche à répondre :

> **Qu’est-ce qui manque encore pour que cette réalité puisse exister, circuler ou permettre l’action promise ?**

---

# 24. Gates de cadrage

```text
1. IDENTITY_GATE
2. CIRCULATION_GATE
3. OPERATION_GATE
4. ENRICHMENT
```

Ce sont des lectures de cadrage, pas quatre modèles ni quatre statuts persistants.

---

# 25. Identity Gate

Question :

> **Savons-nous suffisamment ce que l’utilisateur veut faire exister pour créer une réalité chez son owner ?**

---

# 26. Circulation Gate

Question :

> **Cette réalité est-elle suffisamment définie pour être mise en circulation honnêtement ?**

Pas :

> Tous les champs sont-ils remplis ?

---

# 27. Operation Gate

Question :

> **Ce qui doit être vrai pour réellement opérer cette réalité est-il suffisamment préparé ?**

Toujours :

```text
READY_TO_CIRCULATE
≠ READY_TO_OPERATE
```

Et le gate d’opération ne duplique pas Readiness, Requirements, Capacity, Access ou les autres domaines propriétaires.

---

# 28. Enrichment

Informations utiles mais non bloquantes :

```text
photo
description plus riche
accessibilité
programme détaillé
matériel conseillé
médias
```

---

# 29. Pas de liste universelle de champs

Les owners définissent leurs propres besoins.

Exemples :

```text
Activity base
→ owner + title peuvent suffire pour exister

Transport Departure
→ règles Transport propres pour publier

Obtention
→ Targets + Modes + configuration propre
```

Mark ne code pas ces règles en dur.

---

# 30. Framing owner-driven

```text
MARK
↓
OWNER IDENTIFIÉ
↓
OWNER FRAMING CONTRACT
↓
NEXT USEFUL QUESTION
```

---

# 31. Structure conceptuelle du framing

```text
MARK FRAMING
│
├── OWNER_REFERENCE                     1
├── DRAFT_REFERENCE?                    0..1
│
├── IDENTITY_GATE
│   ├── STATE                           1
│   └── NEEDS[]                         0..n
│
├── CIRCULATION_GATE
│   ├── STATE                           1
│   └── NEEDS[]                         0..n
│
├── OPERATION_CONTEXT?
│   ├── STATE
│   └── NEEDS[]
│
├── ENRICHMENTS[]                       0..n
├── CURRENT_FACTS[]                     0..n
├── NEXT_PROMPT?                        0..1
├── ACTIONS[]                           0..n
└── HANDOFFS[]                          0..n
```

---

# 32. États conceptuels de besoin

```text
SATISFIED
MISSING
UNKNOWN
UNAVAILABLE
NOT_APPLICABLE
```

Toujours :

```text
UNKNOWN
≠ MISSING
```

---

# 33. Framing Need

```text
FRAMING_NEED
├── KEY
├── PURPOSE
├── GATE
├── STATE
├── INPUT_KIND
├── SKIPPABLE
└── OWNER_TARGET
```

---

# 34. Purpose

Chaque question doit avoir une finalité d’action.

Exemples :

```text
Permettre de savoir quand venir.
Permettre de réserver.
Permettre de comprendre ce qui est proposé.
Permettre de préparer les conditions.
Permettre de déterminer où l’action se déroule.
```

Invariant :

```text
NO PURPOSE
→ NO MARK QUESTION
```

---

# 35. Priorité des questions sans LLM

```text
1. Identity blocker
2. Circulation blocker
3. Operation blocker si le but actuel est de préparer l’opération
4. Enrichment facultatif
```

À niveau égal :

```text
ordre déclaré par l’owner
```

---

# 36. Revalidation après réponse

```text
réponse
↓
owner mutation
↓
owner revalidation
↓
nouveau framing
↓
prochaine question
```

Le client ne possède pas la checklist métier.

---

# 37. Pas de wizard rigide

Éviter :

```text
Étape 1/12
Étape 2/12
...
```

La grammaire préférée est :

```text
ce qui existe déjà
+
question la plus utile
+
actions disponibles maintenant
```

---

# 38. Mise en circulation dès que possible

Dès que le gate est satisfait :

> **Votre activité peut maintenant être mise en circulation.**

Action :

```text
[ Mettre en circulation ]
```

Les enrichissements ne bloquent pas.

---

# 39. Pas de score de complétude

Interdit :

```text
72 % complété
Score qualité : 61
Ajoutez une photo pour +10
```

La progression est exprimée par des conséquences réelles :

```text
Votre activité existe.
Les personnes peuvent comprendre ce que vous proposez.
Elle peut être mise en circulation.
Les personnes peuvent maintenant réserver.
```

---

# 40. Circulation ≠ public universel

Selon l’owner, circulation peut signifier :

```text
public
unlisted
private/scoped
group-restricted
accessible à certains
opérationnel interne
```

Mark ne crée aucun système de visibilité parallèle.

---

# 41. Mark Me

Mark Me a une gravité vers :

```text
RETRIEVE
EXPLORE
CONTINUE
CONTRIBUTE
CREATE
UPDATE
ACT
```

avec davantage de consommation, continuité et apport.

Un Profile peut néanmoins créer et porter une Activity.

---

# 42. Mark Space

Mark Space a une gravité vers :

```text
CREATE
UPDATE
ACT
CONTRIBUTE
CONTINUE
RETRIEVE
EXPLORE
```

avec davantage de production et opération.

Mais Space peut également explorer et consommer.

---

# 43. Autorité Space

Toujours :

```text
Assignment
= responsabilité

Mandate / Permission
= autorité
```

Mark ne transforme jamais une responsabilité en autorité.

---

# 44. Clarification et confirmation

Clarification :

> **Qu’avez-vous voulu dire ?**

Confirmation :

> **Acceptez-vous cette conséquence ?**

Deux contrats distincts.

`NEEDS_CONFIRMATION` ne signifie pas « attendre un modérateur Makolo ».

---

# 45. États conceptuels Mark

```text
ACCEPTING_INPUT
RESOLVING
FRAMING
NEEDS_CLARIFICATION
READY_FOR_OWNER
NEEDS_CONFIRMATION
EXECUTING
COMPLETED
UNKNOWN
UNSUPPORTED
FORBIDDEN
```

Les noms wire restent ouverts.

---

# 46. Fallback sans IA

Si le texte libre n’est pas compris, Mark peut présenter quelques capacités réellement supportées :

```text
Retrouver quelque chose
Continuer une démarche
Présenter une activité
Ajouter un document
```

selon contexte.

---

# 47. Mark Core doit fonctionner sans LLM

Invariant :

```text
MARK CORE
≠ LLM
```

Il peut fonctionner avec :

```text
starters
intent registry déterministe
selectors
lexique contrôlé
owner resolvers
bounded clarification
framing contracts
owner actions
```

---

# 48. IA optionnelle plus tard

Chaîne correcte :

```text
INPUT
↓
OPTIONAL INTERPRETER
↓
candidate intent + extracted facts
↓
MARK CORE
↓
owner / authority / confirmation
```

Chaîne interdite :

```text
INPUT
↓
LLM
↓
database mutation
```

---

# 49. LLM n’accorde aucune autorité

Même s’il comprend parfaitement une action, la Permission ou le Mandate réel reste obligatoire.

---

# 50. LLM n’établit pas automatiquement les faits

Une interprétation peut être candidate.

Elle ne devient pas automatiquement :

```text
Credential valid
Requirement satisfied
Proof accepted
```

---

# 51. Handoffs

Sorties communes :

```text
RETURN_TO_CONTEXT
OPEN_OWNER
OPEN_SURFACE
```

Exemples :

```text
EXPLORE
→ Discover

CONTINUE Me
→ En cours / owner

CONTINUE Space
→ Métier / owner

CREATE Me
→ Activity / owner

CREATE Space
→ Métier / owner depth

Organization action
→ Nous / owner
```

---

# 52. Retour

Annuler Mark :

```text
→ destination précédente intacte
```

avec contexte, scroll et sélection conservés autant que possible.

---

# 53. Pas de Mark History générique

Les conséquences sont retrouvées chez leurs owners et surfaces.

Mark ne devient pas la mémoire parallèle du système.

---

# 54. Autosave et offline

Chaque réponse significative peut être sauvegardée chez l’owner lorsqu’elle est sûre.

Si une mutation reste locale :

```text
local/pending
```

reste distinct de :

```text
server-confirmed
circulated
```

Toujours :

```text
draft local
≠ serveur

queued
≠ envoyé

envoyé
≠ accepté

owner draft
≠ circulé
```

---

# 55. Transition Post-Mark

Une fois une réalité owner-backed mise en circulation, Mark n’en devient plus le centre.

```text
MARK
→ owner
→ circulation
→ réseau d’action
```

---

# 56. Correction fondamentale : pertinence = Molongo

Invariant absolu :

```text
PERTINENCE
= apanage de MOLONGO
```

Ni Mark, ni Activity, ni Discover, ni Presentation ne calculent la pertinence.

---

# 57. Frontières de la pertinence

```text
MARK
≠ pertinence

ACTIVITY
≠ pertinence

OWNER DOMAIN
≠ pertinence globale

DISCOVER
≠ pertinence

PRESENTATION
≠ pertinence

MOLONGO
→ pertinence
```

---

# 58. Molongo ne devient pas owner des réalités

Toujours :

```text
Molongo
≠ owner Activity
≠ owner Opportunity
≠ owner Funding
≠ owner Service
≠ owner Transport
```

Les faits restent chez leurs domaines canoniques.

---

# 59. Rôle de Mayele

Mayele peut :

```text
découvrir
approfondir
observer
vérifier
surveiller
revalider
résoudre
rechercher une inconnue
```

Il nourrit la connaissance et peut proposer des entrées admissibles à Molongo.

Mais :

```text
Mayele
≠ Molongo
```

---

# 60. Connaissance ≠ pertinence

Invariant :

```text
CONNAISSANCE COMMUNE
≠ PERTINENCE PERSONNELLE / COLLECTIVE
```

Mayele et les owners construisent ou maintiennent la connaissance.

Molongo contextualise ce qui compte.

---

# 61. Post-Mark — chaîne consolidée interne

Pour une réalité créée dans Makolo :

```text
OWNER REALITY
↓
CIRCULATION OWNER-BACKED
↓
CANONICAL KNOWLEDGE / FACTS / RELATIONS
↓
MOLONGO INGRESS
↓
MOLONGO
│   ├── pertinence
│   ├── ordre
│   ├── relations utiles
│   └── expansion du champ
↓
DISCOVER POSSIBILITY FIELD
↓
PRESENTATION
↓
OWNER-BACKED ENGAGEMENT
```

---

# 62. Post-Mark — réalité externe

```text
MAYELE / RESEARCH
↓
acquisition
↓
interprétation
↓
provenance / evidence
↓
résolution
↓
admission canonique
↓
owners / connaissance
↓
Molongo ingress
↓
Molongo
↓
Discover
```

---

# 63. Publication ≠ pertinence

Toujours :

```text
PUBLISHED
≠ RELEVANT
```

Une Activity peut être parfaitement publiée mais non pertinente dans un contexte donné.

---

# 64. Publication ≠ Discover

Toujours :

```text
Activity publiée
≠ automatiquement Possibility Discover
```

---

# 65. Activity n’a pas de relevance universelle

Interdit comme vérité globale :

```text
Activity.relevance = 0.87
```

La pertinence dépend de l’Actor Context, de l’Exploration Context, du temps, des relations, contraintes, trajectoires et connaissances, et appartient à Molongo.

---

# 66. Mark prépare des faits, pas de la pertinence

Le cadrage Mark peut améliorer la connaissance de :

```text
identité
provenance
temps
géographie
conditions
procédure
prix
capacité
accès
prochaine action
```

Mais Mark ne conclut jamais :

```text
cette Activity sera plus pertinente
```

---

# 67. Formulation UX correcte

Éviter :

> Ajouter le lieu vous fera apparaître plus haut.

Préférer :

> Ajouter le lieu permettra à Makolo de comprendre où cette activité peut réellement être vécue.

Molongo pourra ensuite utiliser ce fait lorsqu’il est pertinent.

---

# 68. Pas de promesse de ranking dans Mark

Interdit :

```text
ajoutez une photo
→ meilleur classement

complétez le profil
→ plus de visibilité

publiez souvent
→ plus de portée
```

---

# 69. Faits utiles post-Mark

La réalité owner-backed peut fournir des faits sur :

```text
IDENTITY
PROVENANCE
SPATIOTEMPORAL
PROCEDURE
REQUIREMENTS
ACCESS
CAPACITY
ECONOMIC
OPERATIONAL
REFERENCE
TRUST / EVIDENCE
FRESHNESS
```

Ces faits restent chez leurs owners / couche de connaissance.

---

# 70. Molongo exploite les faits

Molongo peut exploiter ces faits et relations pour établir :

```text
pertinence
relations utiles
ordre
expansion du champ
```

selon ses propres contrats.

---

# 71. Molongo peut conclure « rien »

La sortie légitime de Molongo peut être :

```text
aucune possibilité suffisamment pertinente
```

Il n’a pas à remplir Discover artificiellement.

---

# 72. Discover consomme Molongo

Invariant :

```text
Discover
→ reçoit le Possibility Field
```

Il ne recalcule jamais la pertinence.

---

# 73. Discover n’invente aucune raison

Si Molongo fournit une raison exploitable :

```text
Presentation
→ peut l’exposer
```

Sinon l’UX n’invente rien.

---

# 74. Molongo peut ordonner

L’ordre du champ peut être fourni par Molongo.

Le frontend le conserve.

Il ne reranke pas localement selon :

```text
popularité
likes
date de création
clics
```

---

# 75. Popularité ≠ pertinence

Invariant :

```text
POPULARITY
≠ RELEVANCE
```

Followers, likes, watch time ou fréquence de publication ne deviennent pas la vérité de pertinence.

---

# 76. Fait collectif utile ≠ popularité

Nuance :

```text
200 personnes inscrites
```

peut être utile si Capacity ou disponibilité en dépendent.

Ce n’est pas un bonus social.

---

# 77. Discover n’est pas un feed

Le `Possibility Field` est un ensemble actuellement explorable.

Il n’est pas un feed persistant.

---

# 78. Discover n’est pas la page des nouveautés

Toujours :

```text
NEW
≠ RELEVANT
```

---

# 79. Pas de relâchement silencieux

Si le champ est épuisé :

```text
END_OF_FIELD
```

Discover peut dire :

> Vous avez vu ce qui est disponible dans ce contexte.

Puis éventuellement :

```text
Explorer plus largement
```

sur action volontaire.

---

# 80. Possibility ≠ Activity

Toujours :

```text
Possibility
≠ Activity
≠ Opportunity
≠ Card
```

Une Possibility est une projection UX justifiable par des vérités propriétaires et les sorties de Molongo.

---

# 81. Admission au champ Discover

Discover ne s’auto-alimente pas.

Conceptuellement :

```text
owners / knowledge
+
Molongo
+
admission selectors
→ Possibility Field
```

---

# 82. Sécurité avant Presentation

Une possibilité ne doit pas apparaître si le viewer n’a pas le droit de connaître la réalité sous-jacente.

Toujours :

```text
relevance
≠ permission
```

Molongo ne transfère aucune Permission.

---

# 83. Molongo ≠ autorité

```text
MOLONGO
≠ Mandate
≠ Permission
≠ Access
```

---

# 84. Pertinence seule ne crée pas Now

Une possibilité très pertinente dans Discover ne devient pas une Situation Now simplement parce qu’elle est pertinente.

Le contrat Now exige sa propre admission.

---

# 85. Pertinence seule ne crée pas une Journey

Toujours :

```text
relevant
≠ engaged
```

L’engagement appartient aux owners.

---

# 86. Discover → engagement

```text
Possibility
↓
owner-backed action
↓
owner truth
↓
Journey / Order / Access / Activity / autre
↓
éventuellement En cours / Métier / Now
```

---

# 87. Réseau d’action

```text
REALITY
↓
CIRCULATION
↓
KNOWLEDGE
↓
MOLONGO RELEVANCE
↓
DISCOVER / autres projections
↓
OWNER-BACKED ACTION
↓
CONTINUITY
↓
OUTCOME
↓
NEW FACTS
↓
MOLONGO peut recalculer
```

Ce réseau n’est pas un graphe social de popularité.

---

# 88. Mark contribue au réseau sans le posséder

Mark fait surtout :

```text
intention
→ réalité suffisamment structurée
```

Le post-Mark fait :

```text
réalité
→ circulation
→ connaissance
→ Molongo
→ champ pertinent
```

---

# 89. Frontières finales

```text
MARK
→ aide à produire / cadrer les faits

OWNERS
→ possèdent la vérité métier

MAYELE
→ acquiert / approfondit / vérifie la connaissance

MOLONGO
→ calcule / détermine la pertinence contextuelle, l’ordre, les relations utiles et l’expansion

DISCOVER
→ explore le champ fourni

PRESENTATION
→ représente

OWNERS
→ exécutent les actions réelles
```

---

# 90. Anti-features

Mark ne doit pas devenir :

- un recommender parallèle ;
- un moteur de recherche ouvert parallèle ;
- un moteur de pertinence ;
- un chat persistant ;
- un historique de toutes les actions ;
- un système de validation centrale ;
- un formulaire universel ;
- un score de complétude ;
- un outil SEO Makolo ;
- un catalogue d’agents/outils ;
- un LLM obligatoire.

Post-Mark ne doit pas devenir :

- un feed social ;
- un ranking par popularité ;
- une page « trending » ;
- une amplification par followers ;
- une boîte de recommandations opaques côté frontend ;
- une copie de Molongo dans Discover ;
- une copie de Molongo dans Presentation ;
- une mutation owner décidée par Molongo.

---

# 91. Critères de sortie MK0

Mark Core est crédible si, sans LLM, il peut :

- ouvrir depuis Me ou Space ;
- préserver Actor Context et Viewer ;
- utiliser Invocation Context ;
- proposer quelques starters réels ;
- distinguer Retrieve et Explore ;
- retrouver une réalité connue ;
- ouvrir Discover avec un Exploration Context ;
- reprendre une continuité ;
- créer un owner draft lorsqu’une identité minimale est établie ;
- cadrer progressivement ;
- clarifier ;
- confirmer ;
- gérer unsupported ;
- gérer forbidden ;
- préserver un draft local ;
- faire un handoff ;
- ne créer aucune nouvelle autorité.

---

# 92. Critères de sortie Mark création

Doit démontrer :

- Profile peut créer une Activity personnelle ;
- Space peut créer une Activity dans son scope ;
- owner draft créé tôt ;
- aucune validation Makolo générique ;
- questions owner-driven ;
- pas de formulaire universel ;
- circulation possible dès le minimum owner ;
- enrichissement facultatif ;
- pas de completeness score ;
- autosave / reprise ;
- aucune fausse réussite offline.

---

# 93. Critères de sortie post-Mark

Doit démontrer :

- circulation distincte de pertinence ;
- owners restent source de vérité ;
- Mayele distinct de Molongo ;
- **Molongo possède la pertinence** ;
- Discover ne recalcule pas la pertinence ;
- Presentation ne recalcule pas la pertinence ;
- permissions vérifiées indépendamment ;
- popularité non utilisée comme vérité de pertinence ;
- aucune publication automatique dans Discover ;
- Possibility Field fourni par l’amont ;
- engagement seulement via owner-backed action ;
- fin du champ normale et explicite.

---

# 94. Architecture finale consolidée

```text
                         ┌──────────────────────────────┐
                         │          MAKOLO MARK          │
                         │ intention / apport / cadrage  │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                              OWNER CANONIQUE
                       Activity / Journey / Offer / ...
                                        │
                                        ▼
                               OWNER DRAFT / ACTION
                                        │
                                        ▼
                                  CIRCULATION
                                        │
                                        ▼
                      FAITS + RELATIONS + PROVENANCE
                                        │
                         ┌──────────────┴──────────────┐
                         │                             │
                         ▼                             ▼
                      MAYELE                      OWNERS / KNOWLEDGE
          découvrir / approfondir / vérifier          │
                         │                             │
                         └──────────────┬──────────────┘
                                        ▼
                                 MOLONGO INGRESS
                                        │
                                        ▼
                                     MOLONGO
                         pertinence / ordre / relations
                              / expansion du champ
                                        │
                                        ▼
                              POSSIBILITY FIELD
                                        │
                                        ▼
                                    DISCOVER
                       explorer / filtrer / cartographier
                           comparer / approfondir
                                        │
                                        ▼
                                OWNER-BACKED ACTION
                                        │
                                        ▼
                          CONTINUITÉ / MÉTIER / NOW
                                        │
                                        ▼
                                     OUTCOME
```

---

# 95. Répartition des responsabilités

| Couche | Possède |
|---|---|
| Owner métier | vérité métier, lifecycle, mutations |
| Mark | intention, cadrage, orchestration, handoff |
| Mayele | acquisition, connaissance, vérification, surveillance |
| Molongo | pertinence, ordre, relations utiles, expansion contextuelle |
| Discover | exploration du Possibility Field |
| Presentation | représentation UX |
| Now | attention actuelle |
| En cours | continuité personnelle |
| Métier | monde opérationnel Space |

---

# 96. Formulation canonique Mark

> **Makolo Mark est le mode d’entrée et d’orchestration par lequel une personne exprime une intention, apporte une information ou commence à faire exister une réalité sans devoir connaître la taxonomie interne de Makolo. Mark peut cadrer progressivement une création, créer tôt un brouillon chez son propriétaire canonique, demander uniquement ce qui débloque réellement l’existence, la circulation ou l’opération, puis remettre la suite à l’owner ou à la surface appropriée. Mark ne possède ni les réalités métier, ni leur validation générique, ni la recherche ouverte, ni la pertinence. Il doit rester pleinement fonctionnel sans LLM.**

---

# 97. Formulation canonique Post-Mark

> **Après mise en circulation, une réalité Makolo n’obtient pas automatiquement une audience ni une place dans Discover. Ses vérités restent chez leurs owners et peuvent être enrichies par la connaissance Mayele. Molongo reçoit les réalités et connaissances admissibles, détermine la pertinence contextuelle, l’ordre, les relations utiles et l’expansion du champ, puis fournit les sorties nécessaires à Discover et aux autres projections. Discover explore ce champ sans recalculer la pertinence ; Presentation le représente sans la réinterpréter ; l’engagement réel retourne toujours vers un owner canonique.**

---

# 98. Principe final

```text
MARK
→ FAIT EXISTER ET CADRE

OWNERS
→ POSSÈDENT LA VÉRITÉ

MAYELE
→ CHERCHE ET MAINTIENT LA CONNAISSANCE

MOLONGO
→ POSSÈDE LA PERTINENCE

DISCOVER
→ EXPLORE

PRESENTATION
→ REPRÉSENTE

OWNERS
→ EXÉCUTENT L'ACTION RÉELLE
```

Et :

```text
PERTINENCE
≠ POPULARITÉ

CIRCULATION
≠ AUDIENCE

PUBLICATION
≠ DISCOVER

DISCOVER
≠ RANKING ENGINE

MARK
≠ LLM
```

---

# 99. Références de cadrage principales

Ce document consolide notamment les principes issus de :

- `Makolo_UX_Decouvrir_Contrat_Consolide.md`
- `Makolo_Obtention_Verticale_Cadre_Conception_v2.md`
- `Makolo_Cadre_consolide_de_PageRank_aux_trajectoires_accessibles_2026-09-17.docx`
- `Mayele_Systeme_Autonome_Intelligence_Molongo_Cadre_Consolide_V2_2026-09-30.md`
- `makolo-web-search.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- les contrats gelés `Now`, `En cours`, `Découvrir`, `Moi`, `Nous`, `Métier` et le contrat transversal Mature.

Lors de toute implémentation, le code, les migrations, les tests et les contrats canoniques courants du dépôt `main` restent prioritaires.
