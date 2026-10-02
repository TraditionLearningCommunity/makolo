# Makolo — UX Now  
## Contrat consolidé de la surface d’attention actuelle et de la Situation Now

**Statut :** cadre UX conceptuel consolidé de travail  
**Portée :** Web et mobile, personnel et Space  
**Nom UX retenu :** `Now`  
**Question humaine :** « Qu’est-ce qui compte maintenant ? »  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 1. Objet du document

Ce document fixe le contrat conceptuel de **Now**, la surface Makolo dédiée à ce qui mérite l’attention actuelle d’un acteur.

Il consolide notamment :

- la définition de la **Situation Now** ;
- son admission dans Now ;
- sa grammaire sémantique ;
- sa représentation visuelle ;
- l’usage du média ;
- la composition globale de Now ;
- les niveaux d’attention ;
- les relations entre Situations ;
- leur cycle d’attention ;
- leur promotion et rétrogradation ;
- le passage de la Situation à l’action réelle ;
- les frontières avec les domaines canoniques ;
- les règles de confidentialité, d’autorité, de fraîcheur et de local-first ;
- les anti-features ;
- les points volontairement laissés ouverts avant les algorithmes et les pixels.

Ce document est un **contrat UX et de projection**.

Il ne fixe pas :

- un modèle de base de données ;
- une table `Situation` ;
- un format API définitif ;
- un algorithme de ranking ;
- un moteur de recommandation ;
- un nombre maximum de Situations ;
- une maquette pixel-perfect ;
- un composant visuel unique ;
- une politique exacte de persistance ;
- une taxonomie technique finale ;
- les seuils numériques de priorité.

---

# 2. Place de Now dans Makolo

Now répond à une question différente de Discover, du métier ou de l’historique.

```text
Discover
→ Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?
→ Qu’est-ce qui pourrait nous aider à avancer ?

Now
→ Qu’est-ce qui mérite mon / notre attention maintenant ?

Métier / En cours
→ Qu’est-ce qui existe déjà, se poursuit ou doit être opéré ?

Jour J / Live
→ Qu’est-ce qui se déroule effectivement maintenant et exige une interaction focalisée ?

Notification
→ Faut-il porter une information jusqu’à la personne hors de Now ?
```

Now ne cherche donc pas à montrer tout ce qui est pertinent.

Il cherche à montrer ce qui, **dans la situation présente**, mérite réellement attention parce qu’une action, une décision, une préparation, une surveillance, une attente consciente ou une compréhension est utile maintenant.

---

# 3. Définition de Now

> **Now est la projection minimale mais suffisante du champ d’attention actuel d’un acteur.**

Il contient uniquement ce qui mérite une attention présente pour que les actions, engagements, possibilités ou responsabilités déjà légitimes puissent être :

- préservés ;
- préparés ;
- débloqués ;
- exécutés ;
- décidés ;
- surveillés ;
- compris ;
- transmis ;
- ou volontairement laissés en attente.

Now n’est pas une simple vue chronologique.

Une réalité dans trois mois peut compter maintenant.

Une réalité dans trente minutes peut ne pas compter maintenant si aucune intervention n’est utile.

---

# 4. Ce que Now n’est pas

Now n’est pas :

- un dashboard ;
- une inbox ;
- une liste de notifications ;
- un feed ;
- une timeline ;
- une page de KPI ;
- une todo list générique ;
- une liste exhaustive de toutes les opérations ;
- un moteur d’engagement ;
- un historique ;
- un mini-ERP ;
- un deuxième Journey ;
- un deuxième Readiness ;
- un task manager parallèle ;
- un conteneur de toutes les données Makolo.

Now ne doit jamais être rempli artificiellement pour éviter le vide.

---

# 5. La Situation Now

## 5.1. Définition

> **Une Situation Now est une projection attentionnelle, contextuelle et temporaire de faits et connaissances suffisamment établis qui explique, pour un acteur donné, ce qui mérite actuellement attention, pourquoi cela compte, à qui appartient le prochain mouvement et quelle réponse légitime peut faire avancer, préserver, surveiller ou comprendre la suite.**

Une Situation Now :

```text
≠ Task
≠ Notification
≠ Journey
≠ Activity
≠ Occurrence
≠ Requirement
≠ Readiness
≠ Incident
≠ Reminder
≠ Card
≠ vérité métier autonome
```

Elle compose des vérités appartenant déjà aux domaines propriétaires.

Elle peut provenir d’un fait unique ou d’une combinaison de plusieurs faits.

---

# 6. Situation Now et notion scientifique de Situation

Le mot `Situation` peut exister dans d’autres cadres formels Makolo/Molongo.

Le contrat UX distingue explicitement :

```text
Situation scientifique / formelle
≠
Situation Now UX
```

Dans le présent document, **Situation Now** désigne uniquement la projection attentionnelle de Now.

Un nom technique comme `NowSituationProjection` pourrait être utilisé plus tard pour éviter toute ambiguïté, mais il n’est pas figé ici.

---

# 7. Contexte acteur

Une Situation Now n’existe jamais « globalement » sans perspective.

Elle est toujours relative à un acteur et à un viewer.

## 7.1. `ACTOR_CONTEXT`

Répond à :

> Pour qui cette Situation existe-t-elle ?

Exemples :

```text
Profile Gilbert Bemwiz
Space SOMAF
Space Église X
Space Entreprise Y
```

## 7.2. `VIEWER`

Répond à :

> Qui regarde actuellement ?

Le viewer est généralement un Profile authentifié.

## 7.3. `HUMAN_CONTEXT`

Répond à :

> De quelle réalité humaine parle-t-on ?

Exemples :

```text
Voyage à Montréal
Départ Lubumbashi → Kolwezi · 14 h
Commande 493
Contrat d’édition
Demande fournisseur
```

## 7.4. `SUBJECT`

Répond à :

> Qu’est-ce qui est précisément concerné dans ce contexte ?

Exemples :

```text
passeport
affectation du véhicule
signature du document
paiement
réponse fournisseur
```

---

# 8. Responsabilité, autorité et prochain mouvement

Now doit préserver strictement les invariants Makolo :

```text
Assignment = responsabilité
Mandate / Permission = autorité
```

Une responsabilité peut influencer :

- la visibilité ;
- la lecture ;
- l’ordre ;
- les Situations pertinentes.

Elle ne suffit jamais à autoriser une action.

## 8.1. `TURN`

`TURN` répond à :

> **À qui appartient le prochain mouvement ?**

Exemples :

```text
Gilbert
Makolo
Équipe Finance
fournisseur
ambassade
transporteur
aucun acteur pour l’instant
```

`TURN` ne duplique ni Assignment ni Mandate.

Il est une projection humaine dérivée de la situation actuelle.

---

# 9. Noyau sémantique d’une Situation Now

La grammaire conceptuelle retenue est :

```text
SITUATION NOW

ACTOR_CONTEXT
VIEWER
HUMAN_CONTEXT
SUBJECT

STATE
DELTA?
WHY_NOW
CONSEQUENCE

TURN
RESPONSE

HORIZON?
MAKOLO_PREPARATION?

EXIT_CONDITION
OWNER / DEPTH
```

---

# 10. `STATE`

`STATE` répond à :

> Qu’est-ce qui se passe maintenant ?

Exemples :

```text
Votre dossier est complet.
Aucun véhicule n’est affecté.
Votre demande est en cours d’examen.
Votre voiture est arrivée à Ruzizi.
```

`STATE` ne crée pas un second état métier.

Il présente le sens humain des vérités propriétaires.

---

# 11. `DELTA?`

`DELTA` répond à :

> Qu’est-ce qui a changé par rapport à l’état précédent ?

Exemples :

```text
Votre relevé de notes a été validé ce matin.
Le fournisseur a répondu.
La Capacity disponible est passée de 5 à 1.
Votre départ a été déplacé de 14 h à 16 h.
```

`DELTA` est optionnel.

Une Situation peut devenir pertinente simplement parce que le temps avance, même si aucun événement externe n’a eu lieu.

---

# 12. `WHY_NOW`

`WHY_NOW` répond à :

> Pourquoi cette Situation mérite-t-elle de compter maintenant ?

Exemples :

```text
La demande peut maintenant être envoyée.
Le départ est dans 35 minutes.
La fenêtre de confirmation ferme demain.
Le paiement vient d’être confirmé.
Une réponse vous attend.
```

`WHY_NOW` est différent du timestamp.

Un événement récent n’est pas automatiquement important.

---

# 13. `CONSEQUENCE`

`CONSEQUENCE` répond à :

> Qu’est-ce qui est réellement affecté si rien ne change ?

Exemples :

```text
La fenêtre de visa peut être perdue.
Le départ risque de ne pas pouvoir commencer.
La réservation ne pourra plus être confirmée.
La commande restera bloquée.
```

La conséquence est conceptuellement importante pour l’admission et la priorité.

Elle n’a pas besoin d’être affichée si elle est évidente.

---

# 14. `RESPONSE`

`RESPONSE` répond à :

> Quelle est la bonne réponse à cette Situation ?

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

Ces termes ne constituent pas encore un enum technique obligatoire.

Exemples :

```text
TURN = Gilbert
RESPONSE = DECIDE

TURN = fournisseur
RESPONSE = WAIT

TURN = Makolo
RESPONSE = PREPARE
```

---

# 15. `HORIZON?`

`HORIZON` répond à :

> Jusqu’à quand ou jusqu’à quel événement cette configuration reste-t-elle valable ?

Il peut être temporel :

```text
avant vendredi
dans 35 minutes
avant 16 h
```

ou événementiel :

```text
jusqu’à la réponse du fournisseur
à l’ouverture des inscriptions
jusqu’à confirmation du paiement
jusqu’au retour de Capacity
```

Il ne doit pas être réduit à une date.

---

# 16. `MAKOLO_PREPARATION?`

`MAKOLO_PREPARATION` représente ce que Makolo a déjà préparé, retrouvé, vérifié ou rendu disponible.

Exemples :

```text
Formulaire prérempli.
Pièces retrouvées.
Coordonnées vérifiées.
Document disponible.
Réservation préparée.
```

Important :

```text
MAKOLO_PREPARATION
≠
TURN = Makolo
```

Le premier décrit le travail déjà effectué.

Le second dit que le prochain mouvement appartient actuellement à Makolo.

---

# 17. `EXIT_CONDITION`

Toute Situation Now doit avoir conceptuellement une condition de sortie.

Exemples :

```text
document signé
véhicule affecté
réponse reçue
échéance dépassée
responsabilité transférée
objectif abandonné
information devenue non pertinente
Situation absorbée par une nouvelle composition
```

`EXIT_CONDITION` n’a pas besoin d’être visible.

Elle évite les Situations immortelles.

---

# 18. `OWNER / DEPTH`

Chaque Situation doit savoir quelle réalité propriétaire possède la profondeur.

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

Now ne recrée jamais une profondeur déjà possédée ailleurs.

---

# 19. Contexte de connaissance

La connaissance n’est pas une simple métadonnée visuelle.

Elle peut modifier l’action.

On distingue conceptuellement :

```text
KNOWLEDGE_CONTEXT

PROVENANCE?
FRESHNESS
KNOWLEDGE_STATE
CONFIDENCE? si défendable
```

Exemples de `KNOWLEDGE_STATE` :

```text
KNOWN
UNKNOWN
CONTRADICTORY
STALE
UNAVAILABLE
```

Exemple :

```text
Votre voiture est à Ruzizi.
```

est différent de :

```text
Dernière position connue : Ruzizi · 09:18.
```

Une connaissance périmée ne doit jamais être présentée comme une vérité Live.

---

# 20. Admission dans Now

Une réalité n’entre pas dans Now simplement parce qu’elle existe.

Une Situation Now est admissible lorsque plusieurs conditions sont réunies :

```text
LEGITIMATE_RELATION
∧ PRESENT_SIGNIFICANCE
∧ CONSEQUENCE
∧ USEFUL_RESPONSE
∧ SUFFICIENT_KNOWLEDGE
```

## 20.1. `LEGITIMATE_RELATION`

Pourquoi cette réalité doit-elle compter pour cet acteur ?

Exemples :

- Journey engagé ;
- obligation réelle ;
- Activity personnellement concernée ;
- responsabilité active ;
- action déjà entreprise ;
- veille explicitement légitime ;
- conséquence réelle sur une trajectoire engagée ;
- autre lien canonique suffisamment établi.

Une possibilité simplement intéressante n’entre pas automatiquement dans Now.

---

# 21. Frontière Discover → Now

Une deadline urgente pour une Opportunity n’est pas nécessairement une urgence pour la personne.

Exemple :

```text
Formation très pertinente
Inscriptions ferment demain
```

Si la personne n’a exprimé aucune intention suffisamment établie :

```text
→ Discover
```

et non automatiquement :

```text
→ Now
```

Le seuil exact entre :

```text
intérêt
→ intention
→ engagement
→ orchestration active
```

reste volontairement ouvert.

Now ne doit pas créer un nouveau modèle persistant simplement pour fermer cette ambiguïté.

---

# 22. Situation Now ≠ Card

Une Situation Now est une unité sémantique.

Sa représentation peut être :

- une phrase ;
- une ligne compacte ;
- un avatar + texte ;
- une image ;
- une carte ;
- un PDF directement lisible ;
- un graphique ;
- une composition de plusieurs composants ;
- une surface interactive ;
- une Card ;
- une combinaison de plusieurs de ces formes.

Principe :

```text
Situation Now
≠
composant UI fixe
```

La représentation doit servir la compréhension et l’action, pas imposer une forme uniforme.

---

# 23. Densité cognitive

Now est une surface de faible densité cognitive.

Cela ne signifie pas :

```text
peu d’éléments maximum
```

Cela signifie :

> **peu de bruit inutile et peu de choses concurrentes à comprendre sans nécessité.**

Une Situation peut occuper une grande partie de l’écran si cela réduit l’effort cognitif.

Inversement, une grille de dix petites Cards peut être cognitivement dense.

Principe :

```text
densité cognitive
≠
densité géométrique
```

---

# 24. No Orphan Media dans Now

Un média n’est pas ajouté pour embellir l’écran.

Il doit servir au moins une des cinq fonctions suivantes :

```text
RECOGNIZE
UNDERSTAND
ESTABLISH
PREPARE
ACT
```

En français :

1. reconnaître ;
2. comprendre ;
3. constater ;
4. préparer ;
5. agir.

Si un média n’aide à aucune de ces fonctions, il ne devrait pas être dans Now.

---

# 25. Media Binding

Un média peut être attaché :

- à la Situation entière ;
- à `SUBJECT` ;
- à `HUMAN_CONTEXT` ;
- à `STATE` ;
- à `DELTA` ;
- à `TURN` ;
- à `MAKOLO_PREPARATION` ;
- à l’action.

Exemples :

```text
SUBJECT
→ photo du véhicule

TURN
→ avatar de Gilbert

HUMAN_CONTEXT
→ carte du lieu

MAKOLO_PREPARATION
→ aperçu PDF

ACTION
→ QR ou document à présenter
```

---

# 26. Média ≠ Proof automatique

Une photo, une vidéo ou un document affiché dans Now reste une représentation.

Exemple :

```text
photo voiture
→ peut aider à reconnaître le véhicule
```

mais :

```text
photo voiture
≠ Proof métier automatiquement
```

Si un média doit satisfaire un Requirement, devenir Proof ou être admis comme Evidence métier, cette décision appartient au domaine propriétaire.

---

# 27. `PRESENTATION_METADATA`

La projection peut contenir des métadonnées de présentation.

Elles peuvent porter :

- Media Bindings ;
- variantes de représentation ;
- informations d’accessibilité ;
- hints de présentation bornés.

Elles ne portent jamais :

- Readiness ;
- Permission ;
- Mandate ;
- Requirement ;
- Payment state ;
- Access ;
- Capacity ;
- ou une vérité métier sans propriétaire.

---

# 28. Composition globale de Now

Now est une **surface de composition du champ d’attention**.

Il ne s’agit pas simplement d’une liste d’objets.

La structure conceptuelle retenue est :

```text
NOW
│
├── ACTOR CONTEXT
│
├── ATTENTION SUMMARY ?
│
├── FOREGROUND
│
├── NEAR
│
├── WATCHED BACKGROUND
│
└── CALM
```

Cette structure est sémantique.

Elle ne fixe pas encore les sections visuelles de l’écran.

---

# 29. `ATTENTION SUMMARY?`

Une synthèse d’attention peut apparaître lorsqu’elle aide réellement.

Exemples :

```text
2 choses demandent votre attention.
5 départs sont actifs, 2 demandent votre attention.
3 validations vous attendent.
```

Elle est optionnelle.

Elle sert à orienter.

Elle ne remplace pas obligatoirement les Situations qui suivent.

---

# 30. `FOREGROUND`

Le Premier plan contient les Situations nécessitant réellement une attention ou une intervention actuelle.

Exemples :

- décision à prendre ;
- action devenue nécessaire ;
- fenêtre qui ferme ;
- blocage actuellement actionnable ;
- incident ;
- changement qui demande une réaction ;
- consentement désormais nécessaire.

Le Premier plan peut contenir :

```text
1 Situation
4 Situations
17 Situations
```

si la réalité le justifie.

Il n’existe pas de quota conceptuel.

---

# 31. `NEAR`

Le Champ proche contient les préparations utiles ou fenêtres à préserver.

Exemples :

- document qui peut être préparé maintenant ;
- rendez-vous à prendre suffisamment tôt ;
- action pas encore urgente mais qui réduit un risque futur ;
- étape que Makolo peut déjà préparer.

Le Champ proche ne signifie pas « importance moyenne ».

Il signifie :

> **agir ou préparer maintenant est utile, sans être nécessairement critique immédiatement.**

---

# 32. `WATCHED_BACKGROUND`

L’Arrière-plan surveillé contient les situations pour lesquelles attendre ou surveiller est actuellement correct.

Exemples :

```text
demande de visa en examen
voiture en transit
réponse fournisseur attendue
paiement en confirmation
```

Une Situation surveillée n’est pas oubliée.

Elle reste connue, avec un horizon ou un déclencheur attendu lorsqu’il existe.

---

# 33. `OUT`

Une Situation sort de Now lorsque sa présence n’apporte plus rien à :

- l’action ;
- la décision ;
- la préparation ;
- la surveillance ;
- l’attente consciente ;
- la compréhension actuelle.

La réalité métier peut toujours exister ailleurs.

Now ne devient pas un historique.

---

# 34. Le scroll est légitime

Si trente Situations sont réellement admissibles dans Now, Now peut en présenter trente.

Le scroll n’est pas une anti-feature.

Anti-feature :

```text
scroll infini fabriqué pour retenir
```

Comportement légitime :

```text
scroll sur l’ensemble réel des Situations actuelles
```

Makolo ne doit pas :

- cacher des Situations légitimes pour respecter un quota ;
- forcer une pagination conceptuelle « Page 1 / 2 / 3 » ;
- injecter du contenu artificiel après la dernière Situation.

Après la dernière Situation réelle, le contenu peut simplement se terminer.

---

# 35. Compression sémantique, pas numérique

Dans Now :

```text
compression
≠ Top N
≠ cacher
≠ réduire arbitrairement le nombre d’éléments
```

La compression signifie d’abord :

```text
univers des faits
→ Situations réellement admissibles maintenant
```

Ensuite, un regroupement ou une synthèse n’est utilisé que s’il réduit réellement l’effort cognitif.

Exemple légitime :

```text
5 départs actifs, 2 demandent votre attention.
```

Exemple illégitime :

```text
dette + départ + demande fournisseur
→ fusion forcée parce qu’il y a trop d’éléments
```

---

# 36. État calme

Définition retenue :

> **`Tout est en ordre. ✓` signifie qu’aucune intervention, décision ou attention active n’est actuellement requise de l’acteur courant.**

Cela peut coexister avec une surveillance autonome de Makolo.

Exemple :

```text
Tout est en ordre. ✓

Makolo surveille :
- votre demande de visa ;
- l’arrivée de votre voiture ;
- la réponse du fournisseur.
```

En revanche, si l’acteur doit lui-même surveiller un phénomène parce qu’une intervention peut devenir nécessaire, Now n’est pas en état calme.

---

# 37. Ordre partiel

Now ne force pas un classement total de toutes les Situations.

Deux Situations peuvent être :

```text
toutes deux importantes
mais incomparables
```

Exemple :

- rendez-vous médical important ;
- décision professionnelle urgente.

Makolo peut expliquer les conséquences des deux sans inventer :

```text
A > B
```

lorsqu’aucune contrainte objective ou préférence légitime ne le justifie.

La focalisation peut alors rester à la personne.

---

# 38. Stabilité de l’ordre

À importance comparable et sans changement significatif, Now doit préserver autant que possible la stabilité.

Éviter :

```text
11:56 → A B C
11:57 → C A B
11:58 → B C A
```

sans raison compréhensible.

Un changement d’ordre doit idéalement correspondre à une différence sémantique utile.

---

# 39. Promotion et rétrogradation

Une Situation peut changer de niveau d’attention.

## 39.1. Promotion

Une Situation monte lorsque des changements de :

- temps ;
- état ;
- conséquence ;
- disponibilité ;
- autorité ;
- TURN ;
- connaissance ;
- relation avec d’autres Situations ;

rendent une attention plus utile maintenant.

Exemples :

```text
WAIT
→ réponse reçue
→ DECIDE

préparation utile
→ fenêtre qui approche
→ ACT

état normal
→ incident
→ REACT
```

## 39.2. Rétrogradation

Une Situation descend lorsque :

- l’action immédiate a été accomplie ;
- le prochain mouvement passe à un tiers ;
- Makolo prend le relais ;
- elle devient une attente légitime ;
- l’échéance est repoussée ;
- le risque diminue ;
- une dépendance doit d’abord se résoudre.

Principe :

> **Une Situation ne descend jamais simplement parce qu’il y en a beaucoup.**

---

# 40. `DELTA` ne signifie pas promotion automatique

Un changement déclenche une réévaluation.

Il ne déclenche pas automatiquement une montée.

Exemple :

```text
Votre voiture est arrivée à Ruzizi.
```

peut rester :

```text
WATCHED_BACKGROUND
```

si aucune action n’est nécessaire.

En revanche :

```text
Votre voiture est retenue à Ruzizi faute de document.
```

peut devenir :

```text
FOREGROUND
```

Principe :

```text
DELTA
→ réévaluer STATE, WHY_NOW, CONSEQUENCE, TURN, RESPONSE
```

et non :

```text
DELTA
→ toujours monter
```

---

# 41. Le temps seul ne décide pas

Now ne suit pas une règle universelle :

```text
J-30 → background
J-7 → near
J-1 → foreground
```

Exemple :

```text
Vol dans 2 heures
mais tout est prêt
→ aucune intervention
```

Exemple inverse :

```text
Formation dans 4 mois
mais rendez-vous médical à prendre aujourd’hui
→ FOREGROUND possible
```

Le temps agit avec :

- conséquence ;
- possibilité d’intervention ;
- horizon ;
- dépendances ;
- réversibilité.

---

# 42. Relations entre Situations

Plusieurs Situations peuvent être reliées.

Les relations utiles peuvent inclure conceptuellement :

```text
dépendance
facilitation
ressource partagée
mutualisation
synchronisation
conflit
alternative
cascade
rétroaction
même action
même TURN
même conséquence
même changement
contradiction
```

Ces noms ne constituent pas encore un contrat API.

---

# 43. Relation ≠ fusion

Deux Situations peuvent être fortement liées et rester distinctes.

Elles restent séparées lorsque :

- les actions diffèrent ;
- les TURN diffèrent ;
- les horizons diffèrent ;
- les autorités diffèrent ;
- les conséquences diffèrent.

Principe :

```text
Relation
≠
Fusion
```

---

# 44. Quatre traitements des Situations reliées

Lorsque plusieurs Situations semblent liées, Now peut choisir entre :

```text
A. rester séparées
B. être regroupées visuellement
C. être synthétisées
D. produire une Situation composée
```

---

# 45. Rester séparées

Cas par défaut.

Exemple :

```text
Voyage à Nairobi

- renouveler le passeport ;
- payer l’hôtel ;
- répondre à l’organisateur.
```

Même contexte, mais actions indépendantes.

Règle :

> **Si comprendre ou résoudre A ne réduit pas substantiellement le besoin de comprendre ou résoudre B, elles restent séparées.**

---

# 46. Regroupement visuel

Les Situations restent distinctes mais partagent un contexte de lecture.

Exemple :

```text
Voyage à Nairobi
  - Passeport à renouveler
  - Hôtel à payer
  - Organisateur attend votre réponse
```

`Voyage à Nairobi` peut n’être qu’un repère de composition.

Le regroupement ne doit pas suggérer une dépendance qui n’existe pas.

---

# 47. Synthèse

Une synthèse décrit plusieurs Situations sans créer une nouvelle Situation.

Exemples :

```text
3 documents sont encore nécessaires.
2 départs demandent un véhicule.
4 validations vous attendent.
```

Formule :

```text
information commune dérivée
+
Situations toujours distinctes
```

---

# 48. Situation composée

Une relation peut elle-même produire un nouveau problème présent.

Exemple :

```text
Situation A
→ rendez-vous médical demain 10 h

Situation B
→ réunion SOMAF demain 10 h

Relation
→ incompatibilité temporelle
```

Nouvelle Situation composée :

```text
Deux engagements se chevauchent demain à 10 h.
Vous devrez réorganiser l’un des deux.
```

Une Situation composée doit pouvoir définir elle-même :

```text
STATE
WHY_NOW
CONSEQUENCE
TURN
RESPONSE
EXIT_CONDITION
```

Sinon, elle est probablement seulement une synthèse ou un regroupement.

---

# 49. Fusion de faits ≠ Situation composée

Distinction :

```text
Fusion
faits
→ une Situation
```

Exemple :

```text
passeport expire
+
visa exige 6 mois
+
voyage prévu
→
Votre passeport doit être renouvelé.
```

Situation composée :

```text
Situation A
+
Situation B
+
relation émergente
→
Situation C
```

Les deux mécanismes ne doivent pas être confondus.

---

# 50. Situation composée bornée

Une Situation composée reste une projection temporaire d’attention.

Si elle commence à posséder durablement :

- objectif propre ;
- étapes ;
- ressources ;
- documents ;
- historique ;
- Assignments ;
- progression ;

elle risque de devenir un faux :

```text
Journey
ou
Dossier
```

Dans ce cas, la réalité doit retourner vers le domaine propriétaire approprié.

---

# 51. Confidentialité avant composition

Une synthèse ou agrégation ne peut jamais révéler des éléments invisibles séparément.

Conceptuellement :

```text
vérités disponibles
↓
scope acteur
+ visibilité
+ autorité
+ divulgation minimale
↓
projections admissibles
↓
fusion / relation / synthèse / composition
```

Exemple interdit :

```text
3 dossiers sensibles demandent une validation
```

si le viewer n’est autorisé à connaître qu’un seul dossier.

---

# 52. Cycle d’attention

Le cycle d’attention n’est pas le cycle métier.

Une réalité peut durer plusieurs mois alors que sa Situation Now :

- apparaît ;
- devient stable ;
- change ;
- descend ;
- remonte ;
- se résout ;
- sort.

On distingue trois axes.

---

# 53. Axe 1 — Niveau d’attention

```text
FOREGROUND
NEAR
WATCHED_BACKGROUND
OUT
```

---

# 54. Axe 2 — Continuité

```text
NEW
STABLE
CHANGED
RETURNED
```

Cela répond :

> Comment cette Situation se présente-t-elle par rapport à ce que l’acteur connaissait déjà ?

---

# 55. Axe 3 — Événements du cycle

```text
ENTERED
UPDATED
REACTIVATED
RESOLVED
EXITED
```

Cela répond :

> Que vient-il de se passer dans son cycle d’attention ?

`WAIT` n’appartient pas à ce cycle.

`WAIT` est une `RESPONSE`.

---

# 56. `NEW` ≠ important

Une Situation nouvelle peut entrer directement en arrière-plan.

Une Situation ancienne peut rester au Premier plan.

Principe :

```text
NEW
≠
PRIORITY
```

---

# 57. `SEEN` ≠ résolu

Une Situation lue peut rester importante.

Principe :

```text
SEEN
≠
RESOLVED
≠
DEMOTED
```

L’état « vu » peut aider à la représentation, mais il ne change jamais la conséquence réelle.

---

# 58. Stabilité

Si rien de significatif n’a changé :

- ne pas recréer la Situation ;
- ne pas la réannoncer comme nouvelle ;
- ne pas mélanger inutilement son ordre ;
- ne pas changer son sens.

Le refresh technique ne doit jamais recréer artificiellement le cycle d’attention.

---

# 59. `RETURNED`

Une Situation revient lorsqu’elle avait cessé d’exiger une attention active puis qu’un changement significatif la rend de nouveau pertinente.

Exemple :

```text
Demande envoyée
→ WAIT
→ fournisseur répond
→ RETURNED
→ DECIDE
```

Elle n’est pas « nouvelle ».

Elle est une continuité réactivée.

---

# 60. Continuité de projection

Now a besoin conceptuellement d’une identité de continuité.

```text
CONTINUITY_IDENTITY
```

Elle permet de comprendre que :

```text
Votre contrat doit être signé
```

puis :

```text
Votre contrat a été envoyé
```

peuvent appartenir à la même continuité humaine.

Mais :

```text
CONTINUITY_IDENTITY
≠
identité métier
```

Le mécanisme technique de persistance ou de calcul n’est pas encore fixé.

---

# 61. Résolution et sortie

Lorsqu’une action est accomplie :

```text
ACTION
→ feedback réel
→ nouvel état
→ reprojection
```

La Situation peut ensuite :

- disparaître ;
- descendre ;
- devenir attente ;
- se transformer ;
- être remplacée par une nouvelle Situation ;
- sortir définitivement.

Une résolution ne doit pas provoquer une disparition brutale qui laisse la personne sans confirmation.

---

# 62. Passage de la Situation à l’action réelle

Now doit permettre l’action au niveau le plus proche possible de la Situation, sans sacrifier :

- compréhension ;
- autorité ;
- confidentialité ;
- fraîcheur ;
- intégrité métier.

Trois profondeurs sont retenues :

```text
DIRECT_NOW
FOCUSED
DOMAIN_DEPTH
```

et :

```text
NONE
```

lorsqu’aucune interaction n’est utile.

---

# 63. `DIRECT_NOW`

Action directe lorsque tout le contexte nécessaire est déjà suffisamment clair.

Exemples :

```text
Valider
Télécharger
Accepter
Refuser
Confirmer une information simple
```

Une action courte peut néanmoins exiger une confirmation si elle a un impact important.

---

# 64. `FOCUSED`

Interaction bornée lorsqu’une seule intention nécessite quelques choix supplémentaires.

Exemple :

```text
Affecter un véhicule
→ choisir parmi les véhicules admissibles
→ confirmer
```

L’interaction peut prendre la forme d’un bottom sheet, d’une surface temporaire ou d’un autre composant adapté.

Le composant n’est pas fixé ici.

---

# 65. `DOMAIN_DEPTH`

La profondeur métier devient nécessaire lorsque l’action exige le vrai contexte métier.

Exemples :

- Dossier complexe ;
- plusieurs pièces ;
- historique nécessaire ;
- arbitrage Capacity ;
- Jour J ;
- incident ;
- commande complexe ;
- comparaison détaillée ;
- procédure longue.

Principe :

```text
Now
→ Situation
→ domaine propriétaire
```

---

# 66. Profondeur dépend du contexte

Il n’existe pas :

```text
action X = toujours directe
```

Exemple :

```text
Affecter un véhicule
```

peut être focalisé dans une petite flotte.

La même action peut nécessiter une profondeur complète dans une grande flotte avec :

- contraintes ;
- conducteurs ;
- Capacity ;
- maintenance ;
- affectations concurrentes.

---

# 67. Makolo Preparation doit réduire la profondeur humaine

Objectif :

```text
sans Makolo
→ chercher
→ remplir
→ retrouver
→ vérifier
→ joindre
→ choisir
→ envoyer
```

Avec Makolo :

```text
Makolo prépare ce qui peut l’être
→ humain vérifie / consent / décide seulement où nécessaire
```

Exemple :

```text
Votre demande est prête.
Formulaire prérempli.
Pièces retrouvées.

[ Vérifier et envoyer ]
```

---

# 68. Préparer ≠ exécuter

Makolo peut préparer tant que cela ne franchit pas une frontière de décision légitime.

```text
MAKOLO_PREPARES
≠
MAKOLO_EXECUTES
```

Exemple :

```text
Makolo a préparé la réservation.
```

ne signifie pas :

```text
Makolo a réservé.
```

---

# 69. Possibilité technique ≠ autorité

Une action techniquement possible peut être :

- interdite ;
- non déléguée ;
- non souhaitée ;
- soumise à consentement ;
- susceptible d’affecter des tiers ;
- dépendante d’une ressource partagée.

L’urgence ne crée jamais l’autorité.

Une action réversible n’est pas automatiquement légitime.

---

# 70. Une décision humaine reste humaine

Makolo peut :

- préparer ;
- vérifier ;
- comparer ;
- expliquer ;
- simuler ;
- retrouver ;
- surveiller.

Il ne choisit pas à la place de la personne lorsqu’il reste un arbitrage réel de valeurs non délégué.

Exemple :

```text
moins cher
vs
plus rapide
```

sans préférence déjà établie :

```text
Makolo explique
→ humain décide
```

---

# 71. Now ne possède jamais l’action métier

Même si le bouton apparaît dans Now :

```text
[ Affecter un véhicule ]
```

l’action appartient au domaine propriétaire.

Flux conceptuel :

```text
Situation Now
↓
Action
↓
Domaine propriétaire
↓
Vérité canonique mise à jour
↓
Reprojection Now
↓
Situation mise à jour / remplacée / sortie
```

Jamais :

```text
Situation
→ change son propre statut métier
→ synchronise ensuite
```

---

# 72. Feedback et pas de faux succès

Le feedback doit exprimer le niveau réellement atteint.

Exemples possibles :

```text
préparé
enregistré localement
en attente de synchronisation
envoyé
en attente de confirmation
confirmé
accompli
conflit
échec
```

Ne jamais afficher :

```text
Confirmé
```

si seul l’envoi a eu lieu.

Ne jamais afficher :

```text
Obtention accomplie
```

si seul le Payment est confirmé.

---

# 73. Local-first

Now peut utiliser les projections locales déjà autorisées et disponibles.

Mais le client local n’est jamais l’autorité pour :

- Permission ;
- Mandate ;
- Access partagé ;
- Payment ;
- Capacity globale ;
- allocation concurrente ;
- état actuel du monde à partir d’une donnée potentiellement ancienne.

Une opération peut être :

```text
locale
locale puis synchronisée
préparable localement puis confirmée à distance
intrinsèquement distante
```

Le langage UX doit refléter le niveau réellement atteint, sans exposer ces classes techniques à l’utilisateur.

---

# 74. Refresh

Lors d’un refresh :

```text
contenu actuel
+ indicateur discret
→ contenu mis à jour
```

est préférable à :

```text
contenu
→ vide
→ skeleton
→ contenu
```

Le cycle technique du chargement ne doit pas réinitialiser le cycle attentionnel.

---

# 75. Conservation du contexte

Parcours attendu :

```text
Now
→ Situation
→ profondeur métier
→ action
→ retour
```

Le retour doit préserver autant que possible :

- position de scroll ;
- actor context ;
- région de Now ;
- Situation précédemment ouverte ;
- filtre éventuel.

Si la Situation n’existe plus après l’action, Now doit préserver l’ancre cognitive par un feedback ou une transition compréhensible, pas afficher une représentation devenue fausse.

---

# 76. Notification ≠ Situation Now

Direction correcte :

```text
fait métier
→ conséquence
→ éventuellement Situation Now
→ éventuellement Notification
```

Une Situation peut :

- apparaître ;
- changer ;
- revenir ;

sans produire de notification.

La notification ne sert que lorsque l’information doit légitimement atteindre la personne avant sa prochaine consultation normale de Makolo.

Le silence est une fonctionnalité.

---

# 77. Conversations

Une conversation peut devenir pertinente dans Now lorsqu’elle porte :

- une décision attendue ;
- une information qui change l’action ;
- un passage de relais ;
- une intervention dont la personne est le prochain acteur.

Un message non lu n’est pas automatiquement une Situation urgente.

---

# 78. Familles de présentation

Des familles humaines peuvent aider à la présentation :

```text
Décider
Préparer
Faire avancer
Débloquer
Réagir
Surveiller
Passer le relais
Saisir une possibilité
Attendre intelligemment
```

Elles ne constituent pas automatiquement :

- un enum backend ;
- un statut persistant ;
- un domaine ;
- une vérité métier.

`Jour J` doit être traité avec prudence : il s’agit surtout d’un contexte opérationnel spécialisé pouvant produire plusieurs Situations, pas simplement d’un synonyme de famille d’attention.

---

# 79. Profil et Space

Le même concept Situation Now peut servir :

```text
Profile
et
Space
```

Mais leur centre de gravité diffère.

## Profil

> Qu’est-ce qui mérite mon attention maintenant pour que ce que je veux vivre, faire ou obtenir puisse avancer ?

## Space

> Qu’est-ce qui mérite notre attention maintenant pour que ce que nous opérons, produisons ou délivrons puisse avancer ?

Même structure conceptuelle.

Vocabulaire et représentations adaptés au contexte.

---

# 80. Multi-contextes

Une même personne peut avoir simultanément :

```text
Now personnel
Now SOMAF
Now Église
Now entreprise
```

Chaque Situation conserve :

- son `ACTOR_CONTEXT` ;
- sa responsabilité ;
- son autorité ;
- sa confidentialité ;
- sa divulgation.

Une future vue transversale pourrait composer ces contextes.

Mais :

> **Une composition multi-contextes ne transfère jamais implicitement Mandate, Permission, Access, Payment ou données privées d’un contexte vers un autre.**

L’existence et la forme d’une telle vue ne sont pas figées ici.

---

# 81. No Orphan Content / Media

Dans Now :

- aucun média sans finalité ;
- aucun contenu générique pour retenir ;
- aucun média décoratif imposé ;
- aucune Story générique ;
- aucun autoplay destiné à l’engagement ;
- aucun catalogue média sans Situation.

Mais l’inverse est également vrai :

> **Une Situation ne doit pas être condamnée au texte lorsqu’un média disponible permet de reconnaître, comprendre, constater, préparer ou agir plus rapidement.**

---

# 82. Anti-features

Now ne doit pas devenir :

- un feed ;
- une todo list générique ;
- un inbox universel ;
- un dashboard ;
- une page de KPI ;
- un centre de notifications ;
- une timeline historique ;
- un flux infini artificiel ;
- un système de streaks ;
- un système de badges anxiogènes ;
- un classement de vie ;
- un score global ;
- un moteur de popularité ;
- une duplication des domaines ;
- un espace où tout devient urgent ;
- un système où « nouveau » signifie automatiquement « important » ;
- un ensemble de Cards uniformes ;
- un écran où chaque Situation doit avoir un bouton ;
- un écran où chaque Situation doit avoir une image ;
- une surface où tout est rouge parce qu’une échéance existe ;
- une surface qui cache les Situations légitimes pour respecter un quota arbitraire.

---

# 83. Invariants consolidés

1. **Now est un champ d’attention, pas une liste exhaustive du backend.**
2. **Une Situation Now est une projection, pas une nouvelle vérité métier.**
3. **Situation Now ≠ Card.**
4. **Profile et Space partagent le même concept, mais leur langage est contextuel.**
5. **Actor Context, Viewer, Responsibility, Authority et TURN restent distincts.**
6. **Assignment = responsabilité ; Mandate / Permission = autorité.**
7. **Readiness reste une projection dérivée propriétaire de son domaine.**
8. **Une Situation n’entre pas dans Now uniquement parce qu’elle est récente ou urgente pour elle-même.**
9. **Discover ne devient pas Now sans relation légitime suffisante.**
10. **Une Situation doit expliquer pourquoi elle compte maintenant.**
11. **Une Situation doit avoir une conséquence pertinente.**
12. **Une Situation doit avoir une réponse utile, y compris WAIT ou UNDERSTAND.**
13. **Toute Situation possède conceptuellement une condition de sortie.**
14. **Un média doit servir reconnaître, comprendre, constater, préparer ou agir.**
15. **Média ≠ Proof automatique.**
16. **Metadata ne porte pas les vérités métier.**
17. **Compression sémantique ≠ Top N.**
18. **Si 30 Situations sont réellement admissibles, Now peut en présenter 30.**
19. **Le scroll sur la réalité est légitime ; le scroll fabriqué pour retenir ne l’est pas.**
20. **Relation ≠ fusion.**
21. **Synthèse ≠ Situation composée.**
22. **Une Situation composée reste une projection temporaire et ne devient pas Journey ou Dossier.**
23. **NEW ≠ priorité.**
24. **SEEN ≠ résolution.**
25. **WAIT est une réponse, pas un état du cycle.**
26. **Un refresh ne recrée pas artificiellement les Situations.**
27. **Une action de Now appartient au domaine propriétaire.**
28. **Préparer ≠ exécuter.**
29. **Possibilité technique ≠ autorité.**
30. **Pas de faux succès.**
31. **La confidentialité est appliquée avant agrégation et synthèse.**
32. **La représentation peut évoluer sans changer la vérité métier.**
33. **Now peut conclure `Tout est en ordre. ✓`.**
34. **Le silence est une fonctionnalité.**
35. **Makolo doit réduire le travail humain là où il peut le faire légitimement.**

---

# 84. Exemples consolidés

## 84.1. Document prêt

### Représentation textuelle

```text
Votre document est prêt.
Vous pouvez le lire et le signer pour continuer.

[ Lire et signer ]
Télécharger
```

### Représentation média

```text
Votre document est prêt.

[ PDF directement lisible ]

Makolo a déjà préparé les informations connues.

[ Lire et signer ]
Télécharger
```

Même Situation.

Impact cognitif différent.

---

## 84.2. Voiture à Ruzizi

```text
[ photo de la voiture ]

Votre voiture est arrivée à la frontière de Ruzizi.

Aucune action n’est nécessaire actuellement.
Makolo surveille la suite.
```

Ici :

```text
MEDIA PURPOSE = RECOGNIZE
TURN = autre acteur / système externe
RESPONSE = WAIT
LEVEL = WATCHED_BACKGROUND
```

---

## 84.3. Départ Space

```text
Transport · Départ Lubumbashi → Kolwezi
14 h

Aucun véhicule n’est encore affecté.
Départ dans 35 minutes.

[ Affecter un véhicule ]
```

Si le choix est simple :

```text
INTERACTION_DEPTH = FOCUSED
```

Si la flotte nécessite un contexte opérationnel complexe :

```text
INTERACTION_DEPTH = DOMAIN_DEPTH
```

---

## 84.4. Demande fournisseur

État 1 :

```text
La demande doit être envoyée avant 16 h.

TURN = Gilbert
RESPONSE = ACT
LEVEL = FOREGROUND
```

Après envoi :

```text
Demande envoyée au fournisseur.

TURN = fournisseur
RESPONSE = WAIT
LEVEL = WATCHED_BACKGROUND
```

Après réponse :

```text
Le fournisseur a répondu.
Son devis expire demain.

TURN = Gilbert
RESPONSE = DECIDE
CONTINUITY = RETURNED
LEVEL = FOREGROUND
```

---

## 84.5. Conflit

```text
Rendez-vous médical demain 10 h
+
Réunion SOMAF demain 10 h
```

Situation composée :

```text
Deux engagements se chevauchent demain à 10 h.

Vous devrez réorganiser l’un des deux.
```

Les deux engagements continuent d’exister dans leurs domaines propriétaires.

---

# 85. Schéma conceptuel consolidé

```text
SITUATION NOW
│
├── CONTINUITY
│   └── projection continuity identity
│
├── ACTOR
│   ├── ACTOR_CONTEXT
│   ├── VIEWER
│   ├── RESPONSIBILITY
│   └── AUTHORITY
│
├── SEMANTIC CORE
│   ├── HUMAN_CONTEXT
│   ├── SUBJECT
│   ├── STATE
│   ├── DELTA?
│   ├── WHY_NOW
│   ├── CONSEQUENCE
│   ├── TURN
│   ├── RESPONSE
│   ├── HORIZON?
│   ├── MAKOLO_PREPARATION?
│   ├── EXIT_CONDITION
│   └── OWNER / DEPTH
│
├── KNOWLEDGE CONTEXT
│   ├── PROVENANCE?
│   ├── FRESHNESS
│   ├── KNOWLEDGE_STATE
│   └── CONFIDENCE? si légitime
│
├── ATTENTION
│   ├── LEVEL
│   │   ├── FOREGROUND
│   │   ├── NEAR
│   │   ├── WATCHED_BACKGROUND
│   │   └── OUT
│   │
│   ├── CONTINUITY STATE
│   │   ├── NEW
│   │   ├── STABLE
│   │   ├── CHANGED
│   │   └── RETURNED
│   │
│   └── LIFECYCLE EVENT
│       ├── ENTERED
│       ├── UPDATED
│       ├── REACTIVATED
│       ├── RESOLVED
│       └── EXITED
│
├── ACTION
│   ├── business action?
│   └── INTERACTION_DEPTH
│       ├── DIRECT_NOW
│       ├── FOCUSED
│       ├── DOMAIN_DEPTH
│       └── NONE
│
└── PRESENTATION METADATA
    ├── MEDIA BINDINGS
    │   ├── TARGET
    │   └── PURPOSE
    │       ├── RECOGNIZE
    │       ├── UNDERSTAND
    │       ├── ESTABLISH
    │       ├── PREPARE
    │       └── ACT
    │
    └── representation / accessibility
```

---

# 86. Ce qui reste volontairement ouvert

Avant toute formalisation algorithmique ou implémentation dédiée, restent ouverts :

1. le seuil exact Discover → intention → engagement → Now ;
2. l’identité technique exacte de continuité ;
3. la persistance ou le recalcul des Situations ;
4. les algorithmes exacts d’admission ;
5. les mécanismes exacts de niveau d’attention ;
6. les règles numériques éventuelles de promotion/rétrogradation ;
7. l’ordre exact à l’intérieur d’un niveau ;
8. la forme précise des relations entre Situations côté projection ;
9. les contrats API ;
10. la représentation finale mobile et web ;
11. la vue éventuelle multi-contextes ;
12. les noms techniques définitifs ;
13. les mécanismes de réobservation et de freshness selon les domaines ;
14. les seuils exacts d’usage des notifications.

Ces questions doivent être traitées à partir du runtime, des domaines existants et des cas réels.

---

# 87. Doctrine d’implémentation future

Avant d’ajouter un nouveau modèle ou état persistant pour Now :

1. vérifier les domaines canoniques existants ;
2. vérifier Presentation ;
3. vérifier les selectors/read models ;
4. vérifier Readiness ;
5. vérifier Domain Events ;
6. vérifier Notifications ;
7. vérifier les projections UX existantes ;
8. vérifier le besoin réel d’historisation ;
9. vérifier l’autorité de la donnée ;
10. préférer une projection dérivée tant qu’aucune vérité persistante irréductible n’est démontrée.

Par défaut :

> **Situation Now doit être pensée comme projection/read model avant d’être pensée comme modèle métier.**

---

# 88. Critères de sortie d’une future implémentation Now

Une première implémentation crédible de Now devra démontrer au minimum :

- Situation Now dérivée de vérités propriétaires ;
- aucun Readiness/Permission/Mandate/Requirement dupliqué ;
- séparation Profile / Space ;
- Actor Context explicite ;
- respect des Assignments et Mandates ;
- confidentialité et divulgation minimale ;
- plusieurs niveaux d’attention ;
- scroll borné par la réalité, sans quota artificiel ;
- absence de scroll infini artificiel ;
- support d’au moins une Situation textuelle ;
- support d’au moins une Situation média ;
- support d’une attente légitime ;
- support d’une action directe ;
- support d’une interaction focalisée ;
- support d’un handoff vers profondeur métier ;
- feedback sans faux succès ;
- continuité après action ;
- refresh sans perte de contexte ;
- représentation offline honnête ;
- action sensible revalidée côté autoritatif ;
- état calme `Tout est en ordre. ✓` ;
- aucune notification artificielle ;
- tests d’autorité/IDOR ;
- tests de données anciennes/freshness ;
- tests de plusieurs Situations simultanées ;
- tests d’au moins un conflit ou relation entre Situations ;
- tests de disparition/réactivation d’une Situation.

---

# 89. Références de cadrage

Ce contrat consolide principalement les principes issus de :

- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_Cadre_consolide_de_PageRank_aux_trajectoires_accessibles_2026-09-17.docx`
- `makolo_questions_de_conception.md`
- `Makolo_Obtention_Verticale_Cadre_Conception_v2.md`
- `Mayele_Systeme_Autonome_Intelligence_Molongo_Cadre_Consolide_V2_2026-09-30.md`
- les invariants canoniques Makolo concernant Profile, Space, Assignment, Mandate, Permission, Journey, Requirement, Readiness, Access, Capacity, Payment, Presentation et confidentialité.

Le runtime courant et les domaines canoniques restent prioritaires sur ce document lors de toute future implémentation.

---

# 90. Formulation finale

> **Now est la surface Makolo qui compose, pour un acteur donné, les Situations qui méritent réellement son attention actuelle. Une Situation Now n’est ni une tâche, ni une notification, ni un objet métier autonome : c’est une projection temporaire de faits suffisamment établis qui explique ce qui se passe, pourquoi cela compte maintenant, ce qui peut arriver, à qui appartient le prochain mouvement et quelle réponse légitime est utile. Now peut être textuel, visuel, documentaire, cartographique ou interactif ; il peut présenter une Situation ou trente ; il peut aider à agir, décider, préparer, attendre, surveiller ou comprendre ; et il peut aussi conclure que tout est en ordre. Il ne possède jamais les vérités métier qu’il représente, n’invente pas d’urgence, ne transforme pas le média en feed et ne retient pas artificiellement l’attention. Son objectif est que Makolo marche pour la personne, puis s’efface lorsque rien d’utile ne reste à faire.**
