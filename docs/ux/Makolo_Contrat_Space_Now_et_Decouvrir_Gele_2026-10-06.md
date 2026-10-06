# Makolo — Contrat conceptuel gelé
# Space Now & Space Découvrir

**Statut :** contrat conceptuel cible, gel de conception  
**Date :** 2026-10-06  
**Portée :** Space `Maintenant` et Space `Découvrir`  
**Clients concernés :** Django/API, Web HTML/Tailwind, Flutter  
**Sources de conception principales :**
- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `space-ux-experience-specification.md`
- contrats conceptuels déjà gelés pour `Now Me` et `Découvrir Me`

---

# 0. Objet du document

Ce document fixe le contrat conceptuel complet de deux surfaces Space :

```text
SPACE NOW
→ Qu’est-ce qui mérite notre attention maintenant ?

SPACE DÉCOUVRIR
→ Qu’est-ce qui pourrait nous aider à avancer ?
```

Les deux surfaces partagent un même contexte d’acteur :

```text
ACTOR_CONTEXT
→ Space

VIEWER
→ Profile humain authentifié
```

mais elles ne constituent pas une même projection.

```text
SPACE NOW
≠ SPACE DISCOVER
```

`Space Now` est une projection d’attention et d’intervention présente.

`Space Découvrir` est une projection d’exploration collective de possibilités réelles.

Le présent document décrit la **cible Mature**. Le runtime courant peut être plus pauvre, notamment lorsque la sélection collective sûre n’est pas encore disponible. Le runtime ne doit donc pas être confondu avec la forme finale décrite ici.

---

# 1. Règles canoniques communes

Les invariants Makolo restent inchangés.

```text
Profile
= personne globale

Space
= acteur collectif durable

Assignment
= responsabilité

Mandate / Permission
= autorité
```

Et :

```text
TeamMembership
≠ Mandate

GroupMembership
≠ Mandate

Assignment
≠ Permission

Archetype
≠ Permission

Operational Footprint
≠ Permission

Entitlement
≠ Permission
```

Une composition UX ne transfère jamais implicitement :

```text
Permission
Mandate
Access
Payment
données privées
autorité métier
```

Toute mutation sensible est revalidée côté serveur.

---

# 2. Position dans le shell Space

La grammaire primaire reste :

```text
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
```

Les deux surfaces étudiées ici occupent les mêmes positions cognitives que leurs équivalents personnels :

```text
Maintenant
→ attention présente

Découvrir
→ exploration
```

Le changement essentiel vient du contexte d’acteur :

```text
personnel
ACTOR_CONTEXT = Profile

Space
ACTOR_CONTEXT = Space
```

Le viewer reste une personne humaine.

---

# 3. Le Space est l’acteur ; le Profile est le viewer

Exemple :

```text
ACTOR_CONTEXT
→ Mulykap

VIEWER
→ Jean
```

Jean ne disparaît pas.

Le Space ne possède pas :

```text
session humaine
Avatar humain
compte utilisateur collectif
Profile collectif
```

Le Space est une identité collective durable au nom de laquelle une personne peut agir seulement lorsque l’autorité canonique le permet.

---

# 4. Socle commun de contexte

Les deux réponses conceptuelles reposent sur :

```text
SPACE SURFACE CONTEXT
│
├── ACTOR_CONTEXT
├── VIEWER
├── VIEWER_RELATION
│   ├── AUTHORITY_CONTEXT
│   ├── RESPONSIBILITY_PERSPECTIVES[]
│   └── SELECTED_RESPONSIBILITY_PERSPECTIVE?
├── ARCHETYPE
├── OPERATIONAL_FOOTPRINT?
└── SELECTION_STATE
```

Ces éléments ont des rôles distincts.

Ils ne doivent pas être fusionnés.

---

# 5. `ACTOR_CONTEXT`

Cardinalité :

```text
1
```

Valeur :

```text
Space courant
```

Projection minimale possible :

```text
ACTOR_CONTEXT
├── kind = space
├── id
├── slug / stable route identity
├── representation
└── owner handoff?
```

Le client ne choisit jamais le Space en envoyant une autorité fabriquée.

Le Space courant doit être résolu via le contexte autorisé par le serveur.

---

# 6. `VIEWER`

Cardinalité :

```text
1
```

Valeur :

```text
Profile authentifié
```

Le viewer détermine :

- ce qu’il peut connaître ;
- les responsabilités/perspectives qui peuvent lui être présentées ;
- les actions qui peuvent lui être proposées ;
- les scopes qui doivent rester cachés.

Deux viewers peuvent donc recevoir des projections différentes du même Space sans création de deux vérités métier.

---

# 7. `VIEWER_RELATION`

Cardinalité :

```text
1 structure
```

Rôle :

> Expliquer comment le Profile courant est légitimement relié au Space pour la surface courante.

Structure conceptuelle :

```text
VIEWER_RELATION
├── AUTHORITY_CONTEXT
├── RESPONSIBILITY_PERSPECTIVES[]
├── SELECTED_RESPONSIBILITY_PERSPECTIVE?
└── HANDOFFS?
```

Cette projection est viewer-specific.

Elle ne fait pas partie de l’identité intrinsèque du Space.

---

# 8. `AUTHORITY_CONTEXT`

Cardinalité :

```text
1 effective summary
```

Le runtime actuel distingue déjà conceptuellement au moins :

```text
SPACE-WIDE
ACTIVITY-LIMITED
```

Les noms wire ne sont pas gelés.

`AUTHORITY_CONTEXT` répond :

> Quelle portée générale d’autorité possède ce viewer dans ce Space pour cette expérience ?

Il ne remplace pas les vérifications fines par owner/action.

---

# 9. Autorité directe Space vs autorité Activity-limited

## 9.1 Autorité Space

Un Mandate Space peut permettre une lecture plus large du Space selon les Permissions réelles.

Cela ne signifie pas :

```text
toutes les données
toutes les actions
tous les modules
```

## 9.2 Autorité limitée à une Activity

Une personne peut légitimement entrer dans le contexte du Space uniquement grâce à une autorité scoped à une Activity du Space.

Dans ce cas, la projection doit être réduite.

Ne doivent pas fuiter automatiquement :

```text
Team globale
Ownership global
Operational Footprint global
autres Activities
Partners globaux
CRM global
Funding privé étranger au scope
données institutionnelles non nécessaires
```

Le contrat doit préférer :

```text
scope minimal
```

à :

```text
projection globale puis filtrage client
```

---

# 10. `RESPONSIBILITY_PERSPECTIVE`

Il faut distinguer :

```text
Assignment
→ responsabilité canonique

Responsibility Perspective
→ read model UX
```

Une perspective visible telle que :

```text
Toutes mes responsabilités
Finance
Exploitation
Administration
Scanner · Départ 14 h
```

n’est pas obligatoirement un Assignment brut.

Elle peut être dérivée serveur depuis :

```text
Assignments
Mandates
scopes
responsabilités métier
contexte actuel
```

sans en devenir une nouvelle vérité persistante.

---

# 11. Cardinalités des perspectives de responsabilité

```text
RESPONSIBILITY_PERSPECTIVES[]
→ 0..n

SELECTED_RESPONSIBILITY_PERSPECTIVE
→ 0..1
```

La vue combinée peut être représentée par :

```text
selected = none
```

ou un identifiant explicite de type `all`.

Le choix technique reste ouvert.

---

# 12. Le filtre de responsabilité ne crée jamais d’autorité

Invariant :

```text
selected perspective = Finance
≠ Permission Finance
```

Le filtre réduit seulement le champ de lecture.

Il peut modifier :

```text
sélection
ordre
densité
langage
groupement
```

Il ne peut pas modifier :

```text
Permissions
Mandates
droits métier
scope canonique
```

Le serveur revalide toujours la perspective demandée.

---

# 13. `ARCHETYPE`

Cardinalité :

```text
1
```

L’archétype représente :

> le centre de gravité durable du Space.

Exemples actuels :

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

L’archétype influence :

```text
langage
saillance
préférences de Presentation
certaines heuristiques de contexte
```

Il ne crée aucune vérité métier.

---

# 14. `OPERATIONAL_FOOTPRINT`

Rôle :

> représenter les domaines réellement utilisés par le Space.

Cardinalité dans une réponse :

```text
0..1 projection
```

car il peut être caché lorsque le viewer n’a pas un scope suffisamment large.

Un Space `commerce` peut réellement utiliser :

```text
Service
Transport
Event
Funding
```

sans changer d’archétype.

Donc :

```text
ARCHETYPE
≠ OPERATIONAL_FOOTPRINT
```

---

# 15. Ce que le client ne fait jamais avec Archetype/Footprint

Le client ne doit jamais calculer :

```text
archetype → Permission
archetype → priorité Now
archetype → possibilité pertinente
footprint → actionability
footprint → authority
```

L’amont peut utiliser ces informations pour la sélection.

Le client les utilise seulement pour représenter ce qui a déjà été résolu.

---

# 16. Divulgation minimale

Agir au nom d’un Space ne signifie jamais :

> voir tout ce qui appartient au Space.

La projection doit respecter :

```text
VIEWER
+ AUTHORITY
+ SCOPE
+ MINIMAL DISCLOSURE
```

Une donnée cachée ne devient pas une absence métier.

---

# 17. `SELECTION_STATE`

Pour Now et Discover, une collection vide est ambiguë si le serveur ne dit pas si la sélection elle-même était possible.

Le contrat conceptuel introduit donc :

```text
SELECTION_STATE
```

Cardinalité :

```text
1
```

Familles conceptuelles :

```text
ESTABLISHED
PARTIAL
UNAVAILABLE
```

Les noms wire finaux restent ouverts.

---

# 18. `ESTABLISHED`

Signifie :

> la sélection est suffisamment défendable pour tirer une conclusion sur le champ demandé.

Exemples :

```text
Space Now
ESTABLISHED + situations=[]
→ calme réel possible

Space Discover
ESTABLISHED + possibilities=[]
→ aucune proposition courante suffisamment pertinente
```

---

# 19. `PARTIAL`

Signifie :

> certaines sources ou parties du champ sont fiables, d’autres n’ont pas pu être établies.

Le client peut présenter le contenu connu.

Il ne peut pas conclure :

```text
Tout est en ordre
```

ou :

```text
aucune possibilité n’existe
```

comme vérité globale.

---

# 20. `UNAVAILABLE`

Signifie :

> aucun mécanisme de sélection suffisamment sûr n’est actuellement disponible.

Ce n’est pas un état vide.

```text
UNAVAILABLE
≠ []
```

Le client ne doit ni reranker, ni générer localement des candidats, ni conclure à l’absence de contenu.

---

# PARTIE I — SPACE NOW

# 21. Question humaine

> **Qu’est-ce qui mérite notre attention maintenant ?**

Ou, du point de vue du viewer :

> **Parmi tout ce qui existe dans ce Space et que je suis autorisé à traiter, qu’est-ce qui mérite mon attention maintenant ?**

---

# 22. Définition

> **Space Now est la projection minimale mais suffisante du champ d’attention actuel du Space, présentée au Profile viewer selon son autorité et son scope réels.**

`Space Now` n’est pas :

```text
dashboard
inbox
feed
liste de notifications
liste exhaustive des opérations
page KPI
todo list générique
```

---

# 23. Unité fondamentale : `SITUATION NOW`

Aucun modèle `SpaceSituation` n’est nécessaire par défaut.

La Situation est une projection UX dérivée de vérités propriétaires.

Elle peut être soutenue par :

```text
Activity
Occurrence
Journey
Payment
Access
Capacity
Request
Funding
Partner
Operations
Trust
CRM
autre owner canonique
```

sans devenir propriétaire de ces réalités.

---

# 24. Admission d’une Situation Space

Admission conceptuelle :

```text
LEGITIMATE_SPACE_REALITY
∧ VIEWER_CAN_KNOW
∧ PRESENT_SIGNIFICANCE
∧ CONSEQUENCE
∧ USEFUL_RESPONSE
∧ SUFFICIENT_KNOWLEDGE
```

Une vérité peut exister sans entrer dans Now.

Exemples :

```text
Occurrence future lointaine
→ pas automatiquement Now

Payment terminé sans conséquence actuelle
→ pas automatiquement Now

nouveau Funding disponible
→ Discover par défaut
```

---

# 25. Responsabilité dans l’admission

La responsabilité peut influencer :

```text
visibilité
ordre
lecture
densité
pertinence
```

Elle ne suffit jamais à autoriser une action.

---

# 26. Autorité dans l’admission

L’autorité peut limiter :

```text
ce que le viewer voit
ce qu’il peut ouvrir
ce qu’il peut faire
```

Une Situation peut être visible sans que toutes ses actions soient disponibles.

---

# 27. Forme racine de `SpaceNowResponse`

```text
SPACE NOW RESPONSE
│
├── ACTOR_CONTEXT                    1
├── VIEWER                           1
├── VIEWER_RELATION                  1
│   ├── AUTHORITY_CONTEXT            1
│   ├── RESPONSIBILITY_PERSPECTIVES  0..n
│   └── SELECTED_PERSPECTIVE         0..1
│
├── SELECTION_STATE                  1
├── ACTOR_ATTENTION_STATE            0..1
│
└── SITUATIONS                       0..n
```

---

# 28. `ACTOR_ATTENTION_STATE`

Cardinalité :

```text
0..1
```

Familles conceptuelles :

```text
ACTIVE
CALM
```

Il ne doit être exposé que lorsque la sélection permet réellement la conclusion.

```text
ESTABLISHED + situation active
→ ACTIVE

ESTABLISHED + aucune attention requise
→ CALM

PARTIAL
→ ne pas affirmer CALM globalement

UNAVAILABLE
→ aucune conclusion
```

---

# 29. Grammaire complète d’une Situation Space

On réutilise le contrat Now déjà gelé :

```text
SITUATION
│
├── CONTINUITY_IDENTITY
├── RESPONSIBILITY[]
├── AUTHORITY?
├── HUMAN_CONTEXT
├── SUBJECT
├── STATE
├── DELTA?
├── WHY_NOW
├── CONSEQUENCE
├── TURN
├── RESPONSE
├── HORIZON?
├── MAKOLO_PREPARATION[]
├── OWNER_DEPTH
├── KNOWLEDGE_CONTEXT
├── ATTENTION
├── BUSINESS_ACTIONS[]
└── MEDIA_BINDINGS[]
```

---

# 30. Cardinalités d’une Situation

| Élément | Cardinalité |
|---|---:|
| Continuity Identity | 1 |
| Responsibility | 0..n |
| Authority | 0..1 effective projection |
| Human Context | 1 |
| Subject | 1 |
| State | 1 |
| Delta | 0..1 |
| Why Now | 1 |
| Consequence | 1 |
| Turn | 0..1 |
| Response | 1 |
| Horizon | 0..1 |
| Makolo Preparation | 0..n |
| Owner Depth | 1 |
| Knowledge Context | 1 |
| Attention | 1 |
| Business Actions | 0..n |
| Media Bindings | 0..n |

---

# 31. `CONTINUITY_IDENTITY`

Cardinalité :

```text
1
```

Identité opaque de continuité UX.

Elle permet de reconnaître une même situation humaine malgré l’évolution de son état.

Le client ne la calcule pas par :

```text
source.kind + source.id
titre
similarité de texte
même date
```

---

# 32. `RESPONSIBILITY[]` dans la Situation

Cardinalité :

```text
0..n
```

Question :

> Qui porte réellement le travail ou la responsabilité liée à cette Situation ?

Structure conceptuelle possible :

```text
RESPONSIBILITY_ITEM
├── actor
├── kind
├── scope
├── source?
└── validity?
```

---

# 33. Perspective racine vs responsabilités de la Situation

Ne pas confondre :

```text
SELECTED RESPONSIBILITY PERSPECTIVE
```

avec :

```text
SITUATION RESPONSIBILITY[]
```

Le premier est un filtre de lecture.

Le second décrit la réalité de la Situation.

---

# 34. `AUTHORITY?` dans la Situation

Cardinalité :

```text
0..1 effective projection
```

Elle répond :

> Quelle autorité pertinente possède le viewer/acteur pour cette Situation ?

Elle peut agréger plusieurs Mandates/Permissions en amont.

Le client ne reçoit pas nécessairement les codes bruts.

---

# 35. Autorité racine vs autorité Situation

Même si :

```text
AUTHORITY_CONTEXT = SPACE-WIDE
```

une action particulière peut rester interdite.

Exemple :

```text
viewer voit le départ
viewer comprend qu'aucun véhicule n'est affecté
viewer n'a pas le droit d'affecter un véhicule
```

La Situation existe.

L’action `assign_vehicle` n’est pas exposée.

---

# 36. `HUMAN_CONTEXT`

Cardinalité :

```text
1
```

Question :

> Dans quelle réalité humaine cette Situation existe-t-elle ?

Porteur :

```text
OBJECT
ou
COMPOSITION
```

Utiliser le plus petit porteur canonique suffisamment riche.

Exemples :

```text
Occurrence Départ Lubumbashi → Kolwezi
Journey d'admission
Order
Funding application
Activity
```

---

# 37. `SUBJECT`

Cardinalité :

```text
1
```

Porteur :

```text
OBJECT
FACT
RELATION
TRANSITION
COMPOSITION
```

Le Subject décrit précisément ce qui est concerné.

Exemple :

```text
Human Context
→ Occurrence Départ 14 h

Subject
→ relation vehicle_assignment
```

---

# 38. `STATE`

Cardinalité :

```text
1
```

Nature :

```text
FACT
```

Il exprime ce qui est actuellement vrai.

Exemple :

```text
vehicle_assigned = false
```

La Presentation transforme ensuite cela en langage humain.

---

# 39. `DELTA`

Cardinalité :

```text
0..1
```

Nature :

```text
TRANSITION
```

Il exprime un changement pertinent.

Une Situation peut être pertinente sans Delta.

---

# 40. `WHY_NOW`

Cardinalité :

```text
1
```

Structure conceptuelle :

```text
WHY_NOW
├── REASON
└── BASIS[]
```

Il répond :

> Pourquoi cette réalité mérite-t-elle une attention maintenant ?

---

# 41. `CONSEQUENCE`

Cardinalité :

```text
1
```

Structure conceptuelle :

```text
CONSEQUENCE
├── TARGET
├── EFFECT
└── CONDITION / HORIZON?
```

La conséquence empêche Now de devenir une liste de simples anomalies techniques.

---

# 42. `TURN`

Cardinalité :

```text
0..1
```

Familles :

```text
PROFILE
COLLECTIVE
EXTERNAL
MAKOLO
NONE
```

Question :

> À qui appartient le prochain mouvement ?

`TURN` n’est pas :

```text
Assignment
Mandate
Permission
```

---

# 43. `RESPONSE`

Cardinalité :

```text
1
```

Familles conceptuelles :

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

Il décrit la posture utile attendue du point de vue de la Situation.

---

# 44. `HORIZON`

Cardinalité :

```text
0..1
```

Formes :

```text
TEMPORAL
EVENT
```

Pas de date artificielle si aucun horizon réel n’est établi.

---

# 45. `MAKOLO_PREPARATION[]`

Cardinalité :

```text
0..n
```

Décrit ce que Makolo a déjà légitimement préparé, retrouvé ou vérifié.

Ne pas confondre :

```text
Makolo a préparé quelque chose
≠ TURN = Makolo
```

---

# 46. `OWNER_DEPTH`

Cardinalité :

```text
1
```

Question :

> Quel domaine possède la vérité complète et la profondeur naturelle ?

Exemples :

```text
Occurrence
Operations
Activity
Journey
Access
Payment
Funding
Partner
CRM
```

Règle :

> Now explique pourquoi entrer ; l’owner explique tout le reste.

---

# 47. `KNOWLEDGE_CONTEXT`

Cardinalité :

```text
1
```

Structure :

```text
KNOWLEDGE_CONTEXT
├── PROVENANCE[]
├── FRESHNESS
├── KNOWLEDGE_STATE
└── CONFIDENCE?
```

États :

```text
KNOWN
UNKNOWN
CONTRADICTORY
STALE
UNAVAILABLE
```

---

# 48. Fraîcheur métier vs fraîcheur locale

Toujours séparer :

```text
SERVER KNOWLEDGE FRESHNESS
≠
CLIENT SNAPSHOT FRESHNESS
```

Une donnée ancienne côté appareil ne transforme pas automatiquement la connaissance métier en `STALE`.

---

# 49. `ATTENTION`

Cardinalité :

```text
1
```

Structure :

```text
ATTENTION
├── LEVEL
├── CONTINUITY_STATE
└── LIFECYCLE_EVENT?
```

Le client ne transforme pas `seen/opened` en résolution métier.

---

# 50. `BUSINESS_ACTIONS[]`

Cardinalité :

```text
0..n
```

Chaque action est owner-backed.

Structure conceptuelle :

```text
BUSINESS_ACTION
├── intent
├── target
├── capability
├── owner / handoff
├── interaction_depth
└── confirmation/context owner-backed si nécessaire
```

Une capability ne vaut jamais Permission permanente.

---

# 51. Action dominante et confort UX

Plusieurs actions peuvent exister.

Mais à la racine Now :

> une seule action devrait généralement dominer visuellement.

Exemple :

```text
[Affecter un véhicule]  ← principale
[Ouvrir le départ]
[Voir les véhicules]
```

La priorité sémantique doit venir de l’amont.

Le client choisit seulement le composant et la disposition.

---

# 52. `INTERACTION_DEPTH`

Familles conceptuelles :

```text
DIRECT_NOW
FOCUSED
DOMAIN_DEPTH
```

Exemples :

```text
DIRECT_NOW
→ action simple et sûre inline

FOCUSED
→ surface bornée / sheet / modal / flow court

DOMAIN_DEPTH
→ ouverture du domaine propriétaire
```

Le serveur ne prescrit pas le widget exact.

---

# 53. `MEDIA_BINDINGS[]`

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

No Orphan Media :

> tout média doit aider à comprendre ou agir dans la Situation.

---

# 54. Familles humaines Space Now

Les documents Space utilisent les familles :

```text
Décider
Faire avancer
Préparer
Jour J
Débloquer
Réagir
Surveiller
Passer le relais
Saisir une possibilité
Ajuster
Accompli
```

Elles ne deviennent pas automatiquement un enum métier persistant.

Elles peuvent être :

```text
vocabulaire UX
classement Presentation
signal de sélection
```

---

# 55. `Décider`

Une décision réelle attend.

Exemple :

```text
demande en attente d'approbation
exception opérationnelle
décision d'accès
arbitrage
```

La Situation doit quand même posséder :

```text
State
Why Now
Consequence
Response
Actions éventuelles
```

---

# 56. `Faire avancer`

Quelqu’un attend quelque chose du Space.

Exemples :

```text
réponse
prestation
livraison
traitement
admission
transport
```

Ce n’est pas une todo générique.

---

# 57. `Préparer`

Une réalité importante approche et n’est pas suffisamment prête.

La préparation doit provenir de faits canoniques.

Ne pas inventer :

```text
Readiness universelle
```

si aucun owner ne la produit.

---

# 58. `Jour J`

Une Occurrence pertinente devient actuelle ou entre dans sa fenêtre opérationnelle.

Now ne copie pas Jour J.

Il produit un handoff vers la profondeur occurrence-scoped.

---

# 59. Plusieurs Jour J simultanés

Un Space peut avoir :

```text
5 Occurrences actuelles
2 seulement demandent attention
```

Now n’affiche pas automatiquement les cinq.

Et :

```text
Space entier
≠ Live
```

Le Live reste occurrence-scoped.

---

# 60. `Débloquer`

Une condition canonique empêche une transition réelle.

Un blocker ne doit pas être inféré génériquement depuis :

```text
Payment
Requirement
Capacity
```

Il doit venir du owner ou d’un resolver suffisamment sûr.

---

# 61. `Réagir`

Une déviation ou un incident réel demande intervention.

Exemple :

```text
départ retardé
incident Operations
résultat inattendu
```

---

# 62. `Surveiller`

Une contrainte approche d’un état significatif.

Ce n’est pas :

```text
tout ce qui change
```

La conséquence et le horizon doivent justifier l’attention.

---

# 63. `Passer le relais`

Une responsabilité doit changer de main ou l’autorité disponible ne permet pas de terminer l’action attendue.

Cette famille illustre particulièrement :

```text
Responsibility
≠ Authority
```

---

# 64. `Saisir une possibilité`

Une Possibility Discover devient suffisamment liée à une conséquence actuelle pour entrer dans Now.

Cela ne fusionne pas les deux surfaces.

---

# 65. `Ajuster`

Des faits de pilotage établis indiquent qu’une décision mérite attention.

Now ne devient pas Piloter.

Il peut seulement signaler une conséquence présente puis remettre à Piloter/owner.

---

# 66. `Accompli`

Une réalisation importante peut apparaître brièvement pour confirmer le niveau réellement atteint.

Elle ne doit pas remplir artificiellement Now.

---

# 67. Sections visuelles possibles

Exemples :

```text
À traiter
À surveiller
Jour J / actuellement
Prochainement
Possibilité fortement pertinente
```

Ce sont des placements de Presentation.

Pas des statuts métier.

Les sections vides disparaissent.

---

# 68. Cardinalité des placements

```text
1 Situation
→ 0..n placements conceptuels
```

Mais le rendu racine devrait éviter de dupliquer visuellement la même Situation sans raison.

---

# 69. Ranking Space Now

Le client ne calcule jamais le ranking final.

Le contrat de sélection peut tenir compte de :

```text
autorité
situation
conséquence
temps
responsabilité
archétype
operational footprint
continuité
```

Des moteurs futurs, notamment Molongo, pourront améliorer la sélection et l’ordre.

Le résultat doit rester explicable.

---

# 70. Calme réel

Condition :

```text
SELECTION_STATE = ESTABLISHED
+
aucune intervention/décision/attention actuelle
```

Alors :

> **Tout est en ordre. ✓**

Makolo ne remplit pas l’écran pour éviter le vide.

---

# 71. Sélection partielle

Avec :

```text
SELECTION_STATE = PARTIAL
```

le client peut montrer les Situations connues.

Il ne doit pas affirmer un calme global.

---

# 72. Sélection indisponible

Avec :

```text
SELECTION_STATE = UNAVAILABLE
```

ne jamais afficher :

> Tout est en ordre.

La bonne expérience dit honnêtement que la sélection actuelle n’a pas pu être établie.

---

# 73. Notification ≠ Situation

Direction :

```text
fait métier
→ conséquence
→ éventuellement Situation Now
→ éventuellement Notification
```

Une Notification est un canal.

Le nombre de notifications ne devient pas un signal Now par défaut.

---

# 74. Conversation ≠ Situation

Une conversation peut devenir pertinente seulement lorsqu’elle porte une conséquence présente réelle.

Le chat lui-même ne remplit pas Now.

---

# 75. Loading Space Now

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

---

# 76. Refresh Space Now

Un refresh doit préserver autant que possible :

```text
Space courant
responsibility perspective
scroll
sélection locale
profondeur de navigation
```

Il ne doit pas remettre l’utilisateur à zéro sans nécessité.

---

# 77. Après mutation

Flux :

```text
action owner
→ résultat réel
→ refetch
→ reprojection Now
```

Si la Situation a disparu car elle est résolue, le client ne la maintient pas artificiellement.

---

# 78. Offline Space Now

Avec snapshot :

```text
content + offline
```

Les Situations connues restent consultables.

Mais :

```text
ancien snapshot
≠ vérité actuelle garantie
```

Particulièrement pour :

```text
Capacity
Access
Operations
Live
Payment
authority
```

---

# 79. All-clear offline

Le dernier all-clear peut être affiché comme dernier état connu si le contrat Presentation l’autorise.

Il ne doit pas être réaffirmé comme vérité courante lorsque la fraîcheur nécessaire n’est plus suffisante.

---

# 80. Error partielle

Une panne d’un owner ne doit pas effacer les autres informations sûres.

Exemple :

```text
Funding indisponible
Operations disponible
Activity disponible
```

Alors :

```text
SELECTION_STATE = PARTIAL
```

peut être approprié.

---

# 81. Erreur bloquante

Une erreur importante doit répondre :

1. qu’est-ce qui n’a pas fonctionné ?
2. qu’est-ce qui a été conservé ?
3. que puis-je faire maintenant ?

---

# PARTIE II — SPACE DÉCOUVRIR

# 82. Question humaine

> **Qu’est-ce qui pourrait nous aider à avancer ?**

Autre formulation :

> **Qu’est-ce qui pourrait faire avancer ce Space ?**

---

# 83. Définition

> **Space Découvrir est la projection exploratoire du champ actuel de possibilités réelles susceptibles d’aider le Space à avancer, selon son contexte collectif et dans les limites de ce que le viewer peut légitimement connaître.**

Il ne s’agit pas uniquement de croissance commerciale.

---

# 84. Space Découvrir n’est pas

```text
feed
marketplace universelle
catalogue de tout Makolo
trending
publicité déguisée
timeline
liste d'Opportunity seulement
moteur de ranking client
```

---

# 85. Unité fondamentale : `POSSIBILITY`

La Possibility est la plus petite projection humainement cohérente d’une option réelle que le Space peut envisager.

Elle peut être soutenue par :

```text
Opportunity
Funding
Partner
Activity
Occurrence
place
resource
public
collaboration
route / desserte
need
program
service
autre vérité canonique
```

---

# 86. `POSSIBILITY ≠ owner`

```text
Possibility
≠ Opportunity
≠ Funding
≠ Activity
≠ Partner
≠ card
```

Un seul owner peut suffire.

Plusieurs owners peuvent aussi soutenir une même possibilité.

---

# 87. `POSSIBILITY_BASIS`

Chaque Possibility possède conceptuellement une base :

> l’ensemble minimal de faits et relations canoniques justifiant que cette possibilité est réelle et présentable.

Cette base est obligatoire conceptuellement côté serveur.

Elle n’a pas besoin d’être exposée comme champ API complet si identité, provenance et faits suffisent.

---

# 88. Admission d’une Possibility Space

Formule :

```text
REAL_CANONICAL_OPTION
∧ LEGITIMATE_SPACE_RELEVANCE
∧ VIEWER_CAN_KNOW
∧ EXPLORABLE_MEANING
∧ MINIMUM_SUFFICIENT_KNOWLEDGE
```

---

# 89. Visibilité ≠ actionabilité

Une possibilité peut être visible sans que le viewer soit personnellement autorisé à engager l’action.

Exemple :

```text
Funding pertinent pour le Space
viewer = responsable exploitation
pas de Permission finance
```

Résultat possible :

```text
Possibility visible
CTA de candidature absent
```

---

# 90. Contexte de pertinence collective

Lorsque légitime, l’amont peut considérer :

```text
Archetype
Operational Footprint
SpaceOpenTo / faits équivalents
geography
Activities
Partners
publics
needs
current context
responsibility perspective
```

Aucun de ces éléments n’est suffisant seul.

---

# 91. Archetype ≠ pertinence

Exemple interdit :

```text
transport_operator
→ tout Funding transport est pertinent
```

Le Space réel, son footprint, ses besoins et le contexte doivent être pris en compte.

---

# 92. Forme racine de `SpaceDiscoverResponse`

```text
SPACE DISCOVER RESPONSE
│
├── ACTOR_CONTEXT                    1
├── VIEWER                           1
├── VIEWER_RELATION                  1
│   ├── AUTHORITY_CONTEXT            1
│   ├── RESPONSIBILITY_PERSPECTIVES  0..n
│   └── SELECTED_PERSPECTIVE         0..1
│
├── RESOLVED_EXPLORATION_CONTEXT     0..1
├── SELECTION_STATE                  1
│
└── POSSIBILITY_FIELD                1
    ├── POSSIBILITIES                0..n
    ├── PRESENTATION_PLACEMENTS      0..n
    ├── CONTINUATION / PAGINATION    0..1
    └── END_STATE                    0..1
```

---

# 93. `EXPLORATION_CONTEXT`

Cardinalité :

```text
0..1 structure
```

Peut contenir conceptuellement :

```text
query
intention
constraints
filters
spatial context
linked Activity
linked initiative
linked need
explicit expansion
```

Search n’est qu’une expression de ce contexte.

---

# 94. Requête brute vs contexte résolu

Séparer :

```text
RAW INPUT
```

de :

```text
RESOLVED EXPLORATION CONTEXT
```

Le client peut envoyer :

> financement pour ce programme

Mais il ne doit pas lui-même conclure :

```text
Funding
+ Program X
+ telle eligibility
+ telle géographie
```

si cette résolution nécessite le serveur/Molongo.

---

# 95. `POSSIBILITY_FIELD`

Le field représente :

> l’ensemble actuellement explorable des Possibilities retenues pour ce Space et ce contexte.

Il ne devient pas :

```text
table persistante
feed éternel
liste de tout le marché
```

---

# 96. Ordre du field

Le client préserve l’ordre amont.

Il ne recalcule pas :

```text
global relevance
popular
trending
best for you
best for organization
```

---

# 97. Structure d’une Possibility Space

```text
POSSIBILITY
│
├── POSSIBILITY_IDENTITY
├── REPRESENTATION
├── POSSIBLE_MEANING
├── FACTS[]
├── ASSESSMENT
│   ├── FAVORABLE[]
│   ├── LIMITING[]
│   └── UNKNOWN[]
│
├── VARIANTS[]
├── RELATIONS[]
├── TEMPORAL_FACTS[]
├── SPATIAL_FACTS[]
├── COST?
├── MEDIA_BINDINGS[]
├── PROVENANCE[]
├── KNOWLEDGE_CONTEXT
├── ACTOR_RELATION?
├── CAPABILITIES[]
└── OWNER_DEPTH / HANDOFFS
```

---

# 98. Cardinalités d’une Possibility Space

| Élément | Cardinalité |
|---|---:|
| Possibility Identity | 1 |
| Possibility Basis | 1 conceptuellement |
| Representation | 1 |
| Possible Meaning | 1 sémantiquement |
| Facts | 0..n |
| Assessment | 1 |
| Favorable | 0..n |
| Limiting | 0..n |
| Unknown | 0..n |
| Variants | 0..n |
| Relations | 0..n |
| Temporal Facts | 0..n |
| Spatial Facts | 0..n |
| Cost | 0..1 structure |
| Media Bindings | 0..n |
| Provenance | 0..n |
| Knowledge Context | 1 |
| Actor Relation | 0..1 |
| Capabilities | 0..n |
| Primary Owner Depth | 0..1 |
| Owner Handoffs | 0..n |
| Presentation Placements | 0..n |

---

# 99. `POSSIBILITY_IDENTITY`

Cardinalité :

```text
1
```

Elle doit être stable assez pour :

```text
dedup
detail
cache
comparison
return
placement multiple
save/watch si owner existe
```

Elle n’est pas nécessairement une nouvelle identité métier.

---

# 100. Déduplication

Interdits :

```text
même titre
même image
même date
texte proche
→ même Possibility
```

La déduplication doit être établie amont.

---

# 101. `REPRESENTATION`

Cardinalité :

```text
1
```

Elle doit permettre de reconnaître l’option.

Mais pas de shell métier universel imposant :

```text
title
image
date
button
```

à toutes les verticales.

---

# 102. Grammaire métier contextualisée

Exemples :

```text
Funding
→ couverture
→ fenêtre
→ conditions

Partner
→ identité
→ relation potentielle
→ domaine / zone

Lieu
→ localisation
→ usage possible
→ capacité connue si pertinente

Desserte
→ origine
→ destination
→ logique réseau
```

Backend générique, vocabulaire UX contextuel.

---

# 103. `POSSIBLE_MEANING`

Obligation sémantique :

> Qu’est-ce que cela pourrait permettre au Space ?

Il peut être exprimé par la représentation sans champ autonome obligatoire.

---

# 104. `FACTS[]`

Cardinalité :

```text
0..n
```

Faits établis sur la possibilité.

Exemples :

```text
deadline
place
price
available window
scope
organizer
capacity connue
```

---

# 105. `ASSESSMENT`

Cardinalité :

```text
1 structure
```

Structure :

```text
ASSESSMENT
├── FAVORABLE[]
├── LIMITING[]
└── UNKNOWN[]
```

Il s’agit d’une lecture contextualisée relative au Space.

---

# 106. `FAVORABLE[]`

Cardinalité :

```text
0..n
```

Exemples :

```text
compatible avec un besoin explicite
zone compatible
resource déjà possédée
window compatible
```

Cela ne signifie jamais :

> choisissez cette option.

---

# 107. `LIMITING[]`

Cardinalité :

```text
0..n
```

Exemples :

```text
deadline très proche
coût au-delà d'une contrainte explicite
zone incompatible
condition connue non satisfaite
```

---

# 108. `UNKNOWN[]`

Cardinalité :

```text
0..n
```

Exemples :

```text
eligibility inconnue
prix non confirmé
availability non vérifiée
```

Invariant :

```text
UNKNOWN
≠ FALSE
≠ IMPOSSIBLE
≠ READY
```

---

# 109. Pas de score global

Interdits par défaut :

```text
match 92 %
best fit
green/yellow/red universel
compatibility score
```

Un moteur futur peut produire des raisons de pertinence.

Presentation ne les transforme pas automatiquement en score.

---

# 110. `VARIANTS[]`

Cardinalité :

```text
0..n
```

Une Variant est une autre réalisation suffisamment proche de la même possibilité.

Exemple :

```text
même programme
→ session novembre
→ session décembre
```

---

# 111. Variant ≠ Alternative

```text
VARIANT
→ même option, autre réalisation

ALTERNATIVE
→ autre Possibility indépendante
```

Le client ne décide pas cela depuis le titre.

---

# 112. `RELATIONS[]`

Cardinalité :

```text
0..n
```

Structure :

```text
RELATION
├── kind
├── members[]
└── context/basis?
```

Relations possibles :

```text
alternative
complement
can_fund
can_enable
nearby
shared constraint
```

---

# 113. Relation ≠ fusion

Deux Possibilities restent distinctes si elles peuvent être choisies ou rejetées indépendamment.

Exemple :

```text
Formation
+
Funding capable de la financer
```

Le Funding n’est pas une Variant de la formation.

---

# 114. `TEMPORAL_FACTS[]`

Cardinalité :

```text
0..n
```

Une possibilité peut avoir plusieurs fenêtres ou Occurrences.

Ne pas réduire systématiquement à :

```text
one date
```

---

# 115. `SPATIAL_FACTS[]`

Cardinalité :

```text
0..n
```

Invariant :

```text
1 Possibility
≠ 1 map point
```

Une desserte ou un programme peut concerner plusieurs lieux.

---

# 116. `COST`

Cardinalité :

```text
0..1 structure
```

Peut représenter :

```text
free
exact
minimum
range
variant-dependent
unknown
```

Pas nécessairement un seul nombre.

---

# 117. `MEDIA_BINDINGS[]`

Cardinalité :

```text
0..n
```

Structure :

```text
MEDIA_BINDING
├── resource
├── target
└── purpose
```

No Orphan Media :

> le média doit aider à comprendre la Possibility.

---

# 118. Types de média

Exemples :

```text
image
video
audio
map
document
PDF
```

Découvrir peut être visuel.

Il ne devient pas un feed média.

---

# 119. `PROVENANCE[]`

Cardinalité :

```text
0..n
```

Plusieurs sources peuvent soutenir une seule Possibility.

```text
plusieurs sources
≠ plusieurs Possibilities
```

---

# 120. `KNOWLEDGE_CONTEXT`

Cardinalité :

```text
1
```

Peut porter :

```text
provenance
freshness
knowledge state
confidence si défendable
```

Les faits sensibles au temps doivent conserver leur fraîcheur.

---

# 121. `ACTOR_RELATION`

Cardinalité :

```text
0..1 structure
```

Rôle :

> Quelle relation canonique le Space possède-t-il déjà avec cette Possibility ?

Structure conceptuelle :

```text
ACTOR_RELATION
├── OWNER_RELATIONS[]
├── SAVED_STATE?
├── WATCH_STATE?
└── ENGAGEMENT_HINTS?
```

Seulement lorsque les owners correspondants existent réellement.

---

# 122. Ne pas copier le modèle personnel

Space Discover ne doit pas recevoir automatiquement :

```text
saved
watch
engaged
```

simplement parce que Discover Me les connaît.

Ces relations doivent avoir un owner Space réel.

---

# 123. Relations Space possibles

Exemples owner-backed :

```text
déjà partenaire
déjà candidat
déjà engagé dans une Activity liée
déjà Funding applicant
déjà suivi si un vrai contrat Watch Space existe
```

Pas d’état générique universel.

---

# 124. `CAPABILITIES[]`

Cardinalité :

```text
0..n
```

Les capabilities décrivent les actions présentables maintenant.

Elles ne sont pas des Permissions permanentes.

---

# 125. Handoff owner

Chaque action profonde doit conduire au domaine propriétaire.

Exemples :

```text
Funding
Partner
Activity
Opportunity
Geography
Service
Obtention
```

Découvrir ne possède jamais le résultat.

---

# 126. CTA métier

Préférer :

```text
Candidater
Contacter
Proposer
Demander
Réserver
Créer la relation
Voir le financement
Explorer le lieu
```

à :

```text
Engager
```

générique.

---

# 127. Possibility visible mais non actionnable

Une Possibility peut rester utile à connaître même si le viewer ne possède pas l’autorité d’agir.

Le serveur peut exposer :

```text
Possibility
+ aucun CTA sensible
```

La politique exacte dépend du scope et de la confidentialité.

---

# 128. Authority Activity-limited dans Discover

Un viewer limité à une Activity ne doit pas recevoir automatiquement le champ stratégique global du Space.

Deux possibilités légitimes :

```text
field borné au contexte Activity
```

ou :

```text
SELECTION_STATE = UNAVAILABLE
```

si aucun contrat sûr n’existe.

---

# 129. Fuites interdites pour Activity-limited

Ne pas révéler automatiquement :

```text
Partners globaux
Funding d'autres programmes
CRM global
stratégie globale
Operational Footprint complet
besoins internes non liés
```

---

# 130. Placements Presentation

Sections possibles :

```text
Pour ce Space
À proximité / dans la zone
Partenariats
Financements
Publics / débouchés
Ressources / lieux
```

Ce sont des placements UX.

Pas des catégories métier.

---

# 131. Cardinalité des placements

```text
1 Possibility
→ 0..n placements
```

La même identité peut apparaître dans plusieurs placements sans duplication métier.

---

# 132. Recherche

Search réduit le même Possibility Field.

Exemples :

```text
partenaire logistique à Lubumbashi
financement pour ce programme
lieu pour notre événement
nouvelle desserte pertinente
ressource pour cette initiative
```

---

# 133. Filtres

Les filtres doivent utiliser du vocabulaire humain.

Ils ne doivent pas exposer la taxonomie backend brute.

---

# 134. Carte

La carte apparaît lorsque la géographie aide réellement à choisir.

Elle ne possède pas une seconde recherche indépendante.

```text
LIST
⇄
MAP
```

doivent conserver le même :

```text
exploration context
filters
selection
field
```

---

# 135. Comparaison

La comparaison est une projection temporaire.

Elle compare seulement les dimensions réellement comparables.

Exemples :

```text
coût
lieu
temps
conditions
availability
unknowns
```

Elle ne doit pas produire un gagnant générique.

---

# 136. End states

Familles conceptuelles :

```text
NO_MATCH
NO_CURRENT_PROPOSAL
END_OF_FIELD
SELECTION_UNAVAILABLE
```

Offline est une dimension client distincte.

---

# 137. `NO_MATCH`

Une requête ou un filtre précis ne trouve aucun résultat.

Exemple :

> Aucune possibilité ne correspond à ces critères.

L’utilisateur peut modifier explicitement ses critères.

---

# 138. `NO_CURRENT_PROPOSAL`

La sélection est établie mais rien n’est suffisamment pertinent maintenant.

Copie recommandée :

> **Aucune possibilité suffisamment pertinente pour le moment.**

---

# 139. `END_OF_FIELD`

Le champ courant a été réellement parcouru.

C’est un succès.

Makolo n’ajoute pas du contenu artificiel pour continuer le scroll.

---

# 140. `SELECTION_UNAVAILABLE`

La sélection n’a pas pu être établie.

Ne pas afficher :

> Aucune possibilité.

---

# 141. `Explorer plus largement`

Action explicite :

```text
user chooses expansion
→ exploration context changes
→ new server selection
```

Jamais :

```text
silent criteria relaxation
```

---

# 142. Pagination

La pagination peut être technique :

```text
cursor
page
limit
```

mais ne doit pas imposer un scroll infini.

Le champ doit pouvoir finir.

---

# 143. Confort Discover : refresh

Conserver :

```text
Space
responsibility perspective
query
filters
scroll
selected Possibility
map/list mode
map camera
comparison
```

Le refresh ne doit pas ramener automatiquement en haut.

---

# 144. Confort Discover : retour détail

Flux :

```text
Possibility detail
→ back
→ même field
→ même selection
→ même scroll
```

Si le contenu a changé serveur, le client réconcilie sans inventer un état permanent.

---

# 145. Local-first Discover

Le client peut stocker un pack borné :

```text
possibility identities
representation
facts autorisés
timing
place
known price
actor relation
capabilities
links
provenance
media cache autorisé
```

---

# 146. Recherche offline

La recherche locale ne porte que sur le corpus acquis.

Elle ne doit pas laisser croire qu’elle interroge le monde actuel complet.

---

# 147. Ce que le client ne reconstruit pas offline

```text
global relevance
current world availability
current Capacity
current price si périmé
current authority
new global possibilities
Molongo ranking
```

---

# 148. No Orphan Content

Tout contenu doit avoir :

```text
context
purpose
owner
```

Pas :

```text
post
story
video feed
article générique
```

sans besoin démontré.

---

# 149. Découvrir doit rester exploratoire

Ne pas polluer la surface avec :

```text
3 urgences
12 notifications
5 retards
alertes opérationnelles anxiogènes
```

Ces réalités appartiennent à Now ou Métier.

---

# PARTIE III — FRONTIÈRES ENTRE NOW ET DÉCOUVRIR

# 150. Discover → Now

Une Possibility ne devient pas Situation Now parce qu’elle est :

```text
nouvelle
proche
populaire
fortement scorée
```

Elle peut entrer dans Now seulement si existent :

```text
relation légitime au Space
+
signification présente
+
conséquence
+
réponse utile maintenant
```

---

# 151. Exemple Funding

```text
Funding disponible
→ Discover
```

Puis :

```text
Funding lié à notre programme
deadline demain
candidature encore possible
→ peut produire une Situation Now
```

La même réalité owner peut participer à deux projections UX distinctes.

---

# 152. Now → Discover

Une Situation peut produire un besoin d’exploration.

Exemple :

```text
Situation Now
→ lieu actuel devenu indisponible
→ besoin d'une alternative
```

Handoff :

```text
Now
→ Discover
→ Exploration Context prérempli
```

avec :

```text
Space
Activity
date
géographie
besoin = lieu
```

---

# 153. Now ne devient pas moteur de recherche

Now transmet le contexte.

Discover possède l’exploration.

---

# 154. Discover ne devient pas moteur d’attention

Discover présente des possibilités.

Now décide si une conséquence présente mérite attention.

---

# PARTIE IV — STRESS-TESTS PAR ARCHÉTYPE

# 155. Transport Operator — Now

Exemple :

```text
Départ Lubumbashi → Kolwezi · 14 h
Aucun véhicule affecté
Départ dans 35 minutes
```

Projection :

```text
Human Context
→ Occurrence

Subject
→ vehicle assignment relation

State
→ vehicle assigned = false

Why Now
→ départ imminent

Consequence
→ départ impossible à exécuter correctement

Response
→ ACT

Action
→ assign vehicle si autorité
```

---

# 156. Transport Operator — Discover

Possibilités possibles :

```text
nouvelle desserte
nouveau stop
partenaire transport
Funding mobilité
nouveau lieu
besoin de mobilité
```

Une nouvelle desserte n’entre pas Now simplement parce qu’elle existe.

---

# 157. Education — Now

Exemples :

```text
session demain
admission à décider
Requirement critique réellement bloquant
Capacity demandant une décision
Access à préparer
```

---

# 158. Education — Discover

Possibilités :

```text
partenaire académique
nouveau lieu
Funding
programme complémentaire
resource pédagogique
possibilité de transmission
```

---

# 159. Commerce — Now

Exemples :

```text
Order réellement bloquée
livraison à préparer
Payment dont la conséquence actuelle demande décision
Capacity critique
```

Payment seul ne devient pas blocker sans vérité owner.

---

# 160. Commerce — Discover

Possibilités :

```text
nouveau canal
Partner
public
lieu
débouché
contexte d'Obtention
```

---

# 161. Service Provider — Now

Exemples :

```text
demande à traiter
prestation qui approche
dossier bloqué
responsabilité à transférer
```

---

# 162. Service Provider — Discover

Possibilités :

```text
zone
client/context potentiel
partner
prestation connexe
lieu
resource
```

---

# 163. Community — Now

Exemples :

```text
Funding déjà lié à une initiative
deadline présente
resource critique manquante
partenaire attendu
activité terrain actuelle
```

---

# 164. Community — Discover

Possibilités :

```text
Funding
appel
Partner
resource
lieu
mobilisation
mission context
```

---

# 165. Creative — Now

Exemples :

```text
événement imminent
prestation à préparer
offre nécessitant décision
création avec conséquence actuelle
```

---

# 166. Creative — Discover

Possibilités :

```text
événement
lieu
collaboration
partner
prestation
public
```

---

# 167. Media — Now

Exemples :

```text
production actuelle
Activity à préparer
événement
relation actionnable
```

---

# 168. Media — Discover

Possibilités :

```text
collaboration
partner
événement
opportunité éditoriale contextualisée
```

Pas de CMS social générique déduit.

---

# 169. Generic — Now

Exemples :

```text
Activity proche
demande
engagement
lieu
décision
```

---

# 170. Generic — Discover

Possibilités :

```text
Activity
Partner
lieu
Opportunity compatible
```

---

# PARTIE V — CONFIDENTIALITÉ ET CONNAISSANCE

# 171. Composition ≠ transfert de données

Une Possibility ou Situation qui référence un autre Space ne donne pas accès à ses données privées.

---

# 172. Données interdites dans projections générales

Ne pas exposer :

```text
AccessCredential secret
QR/token brut
private storage path
private proof evidence
review staff notes
API tokens
provider secrets
private keys
PII inutile
```

---

# 173. Known / absent / unknown / unavailable / hidden

Doctrine :

```text
[]
→ collection connue vide

null
→ absence connue lorsque le contrat l'autorise

UNKNOWN
→ valeur inconnue

UNAVAILABLE
→ source/capacité/sélection indisponible

HIDDEN / omitted
→ non divulgué dans le scope
```

---

# 174. Conversions interdites côté client

```text
unknown → false
unavailable → 0
hidden → absent métier
partial → established
```

---

# PARTIE VI — CONTRAT CLIENT

# 175. Ce que Web/Flutter peuvent faire

```text
adapter layout
humaniser dates
formatter monnaie
calculer distance géométrique
rendre carte
choisir viewer média
gérer scroll
sélection locale
map camera
comparison UI
offline snapshot
pending mutation UI
```

---

# 176. Ce que Web/Flutter ne font jamais

```text
Assignment → Permission
Team → Authority
Role label → Permission
Archetype → relevance
Archetype → Permission
Footprint → actionability
heure → Live
Payment → blocker
Requirement → blocker
prix bas → favorable
distance faible → pertinent
Notification unread → Situation
title similaire → même Possibility
```

---

# 177. Pending mutation

Exemple :

```text
server saved = false
client save queued
```

Rendu :

> Enregistrement en cours…

Pas :

```text
saved = true
```

comme vérité serveur.

---

# 178. TOCTOU

Contrat :

```text
GET projection
→ capability visible
→ Mandate révoqué
→ mutation owner
→ refus serveur
```

Le client doit accepter cette possibilité.

---

# PARTIE VII — CONTRATS CONCEPTUELS FINAUX

# 179. Space Now final

```text
SPACE NOW RESPONSE
│
├── ACTOR_CONTEXT
│   └── Space
│
├── VIEWER
│   └── Profile
│
├── VIEWER_RELATION
│   ├── AUTHORITY_CONTEXT
│   ├── RESPONSIBILITY_PERSPECTIVES[]
│   └── SELECTED_PERSPECTIVE?
│
├── ARCHETYPE
├── OPERATIONAL_FOOTPRINT?
├── SELECTION_STATE
├── ACTOR_ATTENTION_STATE?
│
└── SITUATIONS[]
    ├── CONTINUITY_IDENTITY
    ├── RESPONSIBILITY[]
    ├── AUTHORITY?
    ├── HUMAN_CONTEXT
    ├── SUBJECT
    ├── STATE
    ├── DELTA?
    ├── WHY_NOW
    ├── CONSEQUENCE
    ├── TURN
    ├── RESPONSE
    ├── HORIZON?
    ├── MAKOLO_PREPARATION[]
    ├── OWNER_DEPTH
    ├── KNOWLEDGE_CONTEXT
    ├── ATTENTION
    ├── BUSINESS_ACTIONS[]
    └── MEDIA_BINDINGS[]
```

---

# 180. Cardinalités finales Space Now

| Élément | Cardinalité |
|---|---:|
| Actor Context | 1 |
| Viewer | 1 |
| Viewer Relation | 1 |
| Authority Context | 1 |
| Responsibility Perspectives | 0..n |
| Selected Responsibility Perspective | 0..1 |
| Archetype | 1 |
| Operational Footprint projection | 0..1 |
| Selection State | 1 |
| Actor Attention State | 0..1 |
| Situations | 0..n |

Pour chaque Situation :

| Élément | Cardinalité |
|---|---:|
| Continuity Identity | 1 |
| Responsibility | 0..n |
| Authority | 0..1 |
| Human Context | 1 |
| Subject | 1 |
| State | 1 |
| Delta | 0..1 |
| Why Now | 1 |
| Consequence | 1 |
| Turn | 0..1 |
| Response | 1 |
| Horizon | 0..1 |
| Makolo Preparation | 0..n |
| Owner Depth | 1 |
| Knowledge Context | 1 |
| Attention | 1 |
| Business Actions | 0..n |
| Media Bindings | 0..n |

---

# 181. Space Discover final

```text
SPACE DISCOVER RESPONSE
│
├── ACTOR_CONTEXT
│   └── Space
│
├── VIEWER
│   └── Profile
│
├── VIEWER_RELATION
│   ├── AUTHORITY_CONTEXT
│   ├── RESPONSIBILITY_PERSPECTIVES[]
│   └── SELECTED_PERSPECTIVE?
│
├── ARCHETYPE
├── OPERATIONAL_FOOTPRINT?
├── RESOLVED_EXPLORATION_CONTEXT?
├── SELECTION_STATE
│
└── POSSIBILITY_FIELD
    ├── POSSIBILITIES[]
    │   ├── POSSIBILITY_IDENTITY
    │   ├── REPRESENTATION
    │   ├── POSSIBLE_MEANING
    │   ├── FACTS[]
    │   ├── ASSESSMENT
    │   │   ├── FAVORABLE[]
    │   │   ├── LIMITING[]
    │   │   └── UNKNOWN[]
    │   ├── VARIANTS[]
    │   ├── RELATIONS[]
    │   ├── TEMPORAL_FACTS[]
    │   ├── SPATIAL_FACTS[]
    │   ├── COST?
    │   ├── MEDIA_BINDINGS[]
    │   ├── PROVENANCE[]
    │   ├── KNOWLEDGE_CONTEXT
    │   ├── ACTOR_RELATION?
    │   ├── CAPABILITIES[]
    │   └── OWNER_DEPTH / HANDOFFS
    │
    ├── PRESENTATION_PLACEMENTS[]
    ├── CONTINUATION / PAGINATION?
    └── END_STATE?
```

---

# 182. Cardinalités finales Space Discover

| Élément | Cardinalité |
|---|---:|
| Actor Context | 1 |
| Viewer | 1 |
| Viewer Relation | 1 |
| Authority Context | 1 |
| Responsibility Perspectives | 0..n |
| Selected Responsibility Perspective | 0..1 |
| Archetype | 1 |
| Operational Footprint projection | 0..1 |
| Exploration Context | 0..1 |
| Selection State | 1 |
| Possibility Field | 1 |
| Possibilities | 0..n |
| Presentation Placements | 0..n |
| Continuation / Pagination | 0..1 |
| End State | 0..1 |

Pour chaque Possibility :

| Élément | Cardinalité |
|---|---:|
| Possibility Identity | 1 |
| Possibility Basis | 1 conceptuellement |
| Representation | 1 |
| Possible Meaning | 1 sémantiquement |
| Facts | 0..n |
| Assessment | 1 |
| Favorable | 0..n |
| Limiting | 0..n |
| Unknown | 0..n |
| Variants | 0..n |
| Relations | 0..n |
| Temporal Facts | 0..n |
| Spatial Facts | 0..n |
| Cost | 0..1 |
| Media Bindings | 0..n |
| Provenance | 0..n |
| Knowledge Context | 1 |
| Actor Relation | 0..1 |
| Capabilities | 0..n |
| Primary Owner Depth | 0..1 |
| Owner Handoffs | 0..n |

---

# PARTIE VIII — ANTI-FEATURES

# 183. Anti-features Space Now

Interdits :

```text
dashboard KPI
todo manager
inbox universelle
feed
chronologie exhaustive
copie Notifications
toutes les Occurrences
toutes les commandes
score algorithmique opaque
remplissage artificiel
priorité recalculée client
```

---

# 184. Anti-features Space Discover

Interdits :

```text
feed infini
popularité = pertinence
trending comme objectif
publicité déguisée
contenu orphelin
média orphelin
données privées d'autres Spaces
ranking client
relâchement silencieux de critères
```

---

# 185. Anti-features communes

Interdits :

```text
client reconstruisant Permission
client reconstruisant relevance
client reconstruisant blocker
client reconstruisant Live
client reconstruisant identity par similarité
Space globalement Live
archetype comme autorité
responsibility filter comme autorité
```

---

# PARTIE IX — ÉTAT DU RUNTIME ET CIBLE

# 186. Runtime actuel

Les endpoints Space `now/` et `discover/` existent déjà.

Le runtime courant choisit volontairement une réponse prudente lorsqu’aucun sélecteur collectif sûr n’est disponible :

```text
selection.state = unavailable
items = []
```

Ce comportement est correct comme protection.

Il ne représente pas la forme cible Mature.

---

# 187. Ce qu’il ne faut pas faire pendant l’implémentation future

Ne pas remplacer :

```text
UNAVAILABLE
```

par une heuristique locale ou serveur fragile uniquement pour avoir du contenu.

Ne pas introduire :

```text
SpaceSituation table
SpacePossibility table
generic relevance score
generic priority score
```

sans besoin démontré.

---

# 188. Pipeline cible

```text
request.user Profile
+ Space autorisé
+ owner facts / selectors / read models
+ responsibility context
+ authority context
+ Molongo seam si disponible
→ canonical Space semantic projection
→ Web / Flutter Presentation
```

---

# 189. Molongo

Aucun contrat d’entrée futur Molongo n’est figé ici.

Le serveur prépare ce qu’il sait déjà posséder.

Molongo pourra plus tard améliorer :

```text
sélection
priorité
pertinence
relations
ordre
```

sans transférer la vérité métier hors des owners.

---

# 190. Critères de sortie Space Now

Une future implémentation Mature doit démontrer :

- Space actor explicite ;
- Profile viewer explicite ;
- scope viewer respecté ;
- responsibility perspective distincte de l’autorité ;
- sélection réellement défendable ;
- Situation Now canonique ;
- conséquence présente ;
- actions owner-backed ;
- calme seulement si établi ;
- plusieurs Jour J sans Space global Live ;
- erreur partielle honnête ;
- local-first sans vérité inventée ;
- aucune fuite Activity-limited ;
- aucune Permission déduite client ;
- IDOR/TOCTOU couverts.

---

# 191. Critères de sortie Space Discover

Une future implémentation Mature doit démontrer :

- Space actor explicite ;
- Profile viewer explicite ;
- exploration contextuelle ;
- sélection défendable ;
- Possibility identity stable ;
- relevance collective non reconstruite client ;
- facts/assessment distincts ;
- unknown distinct de false ;
- variants/relations owner-backed ;
- géographie multi-point possible ;
- No Orphan Media ;
- end states honnêtes ;
- field borné ;
- Activity-limited privacy-safe ;
- actions owner-backed ;
- local-first limité au corpus acquis ;
- aucune publicité/trending déguisée.

---

# 192. Points volontairement non figés — Space Now

Restent ouverts :

1. noms JSON exacts ;
2. `schema_version` final ;
3. algorithme de sélection/priorité ;
4. mécanisme final Molongo ;
5. forme wire précise de Responsibility Perspective ;
6. représentation wire de `SELECTION_STATE` ;
7. mode de persistance/calcul de Continuity Identity ;
8. politique exacte de Presentation placement ;
9. microcopy finale ;
10. densité Compact/Medium/Wide ;
11. politiques fines de cache/freshness par source.

---

# 193. Points volontairement non figés — Space Discover

Restent ouverts :

1. noms JSON exacts ;
2. `schema_version` final ;
3. algorithme de pertinence ;
4. mécanisme final Molongo ;
5. forme exacte de `ACTOR_RELATION` ;
6. contrats Save/Watch Space éventuels ;
7. exact wire des Variants/Relations ;
8. politique de comparaison ;
9. pagination/cursor ;
10. groupements Presentation finaux ;
11. politique de carte ;
12. politique fine des médias ;
13. comportement détaillé d’Explorer plus largement ;
14. stratégie de cache/freshness du corpus acquis.

---

# 194. Formulation finale — Space Now

> **Space Now est la projection d’attention actuelle du Space pour un Profile viewer donné. Elle sélectionne uniquement les réalités suffisamment significatives, conséquentes et actionnables ou compréhensibles dans le scope légitime du viewer. La responsabilité organise la lecture ; l’autorité gouverne l’accès et les actions ; l’archétype donne du langage ; l’Operational Footprint décrit le réel. Now n’est ni un dashboard, ni une inbox, ni une liste exhaustive du travail du Space.**

---

# 195. Formulation finale — Space Découvrir

> **Space Découvrir est la projection exploratoire des possibilités réelles susceptibles d’aider le Space à avancer. Il compose les owners canoniques sans les absorber, tient compte du contexte collectif sans réduire la pertinence à l’archétype, distingue faits, évaluations, variantes, relations et inconnues, et remet toute action au domaine propriétaire. Découvrir n’est ni un feed, ni un catalogue universel, ni un moteur de popularité.**

---

# 196. Formulation finale commune

> **Le Space est l’acteur. Le Profile est le viewer. La responsabilité organise la lecture. L’autorité gouverne l’accès et les actions. L’archétype donne du langage. L’Operational Footprint décrit le réel. Aucun de ces axes ne remplace les autres.**

---

# 197. Séquence suivante

Une fois ce contrat gelé, la prochaine surface Space à traiter est :

```text
MÉTIER
→ Qu’est-ce que nous opérons réellement ?
```

`Métier` ne doit pas être obtenu par simple substitution :

```text
Ongoing Me
+ actor = Space
```

Le travail durable Space dépend :

```text
Operational Footprint
owners réellement utilisés
archétype pour le langage
responsabilité du viewer
autorité réelle
```

et `En cours` devient une dimension du monde opérationnel, pas nécessairement une porte autonome.

