# Makolo — Contrat maître des surfaces personnelles
## `Now Me` · `Ongoing Me / En cours` · `Découvrir Me`

**Statut :** gel conceptuel consolidé de travail  
**Date :** 2026-10-05  
**Portée :** expérience personnelle Makolo — serveur Django, seam Molongo/intelligence, Web HTML/Tailwind, Flutter et local-first  
**Nature :** contrat UX, sémantique et de projection ; **ce document n'est pas un schéma de base de données ni un wire JSON définitif**  
**Promesse produit :** « Makolo marche pour vous. »  
**Principe d'expérience :** « Pas le plaisir de rester. Le plaisir d'avancer. »

---

# 0. Objet du document maître

Ce document réunit dans un seul contrat de référence les trois grandes surfaces personnelles qui organisent l'avancement dans Makolo :

```text
NOW ME
→ Qu'est-ce qui compte maintenant ?

ONGOING ME / EN COURS
→ Pour ce que j'ai déjà engagé, où en suis-je et qu'est-ce qui continue ?

DÉCOUVRIR ME
→ Qu'est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?
```

Il ne s'agit pas de trois variantes d'une même liste. Chacune possède une unité UX, une question humaine, une logique d'admission et une structure sémantique propres :

```text
Now Me
→ Situation Now

Ongoing Me
→ Continuité En cours

Découvrir Me
→ Possibilité Discover
```

Le présent document conserve les contrats détaillés déjà consolidés, leurs exemples, invariants, anti-features et doctrines de profondeur, puis ajoute après chaque partie un **gel conceptuel 2026-10-05** intégrant les décisions prises lors de l'étude détaillée serveur/client.

## 0.1. Règle de vérité

Pour toute future implémentation, la priorité reste :

1. code, migrations et tests du `main` courant ;
2. `docs/architecture/makolo-domain-blueprint.md` ;
3. contrats UX et docs canoniques pertinents ;
4. `docs/operations-runbook.md` ;
5. état GitHub courant ;
6. historique et transferts comme contexte seulement.

Les SHA ou états runtime mentionnés dans les documents sources ci-dessous sont **des repères historiques de consolidation**. Ils ne doivent jamais être traités comme le `main` actuel sans nouvelle vérification.

## 0.2. Invariants transversaux non négociables

```text
Profile = personne globale
Assignment = responsabilité
Mandate / Permission = autorité
Membership / Group / Team ≠ autorité implicite
Readiness = projection dérivée
Requirement ≠ Form ≠ Resource ≠ JourneyArtifact ≠ Proof ≠ Credential Trust ≠ AccessCredential
Access = droit
AccessCredential = représentation / secret
AccessUse = observation d'usage
Capacity = combien ?
Placement = où ?
Waitlist ≠ Live Queue
JourneyStep ≠ Checkpoint opérationnel
Dossier ≠ task manager générique
Project ≠ task manager générique
posséder un document ≠ le retrouver ≠ satisfaire un Requirement
composition ≠ transfert de Permission, Mandate, Access, Payment ou visibilité privée
```

La confidentialité et la divulgation minimale s'appliquent **avant** composition, synthèse, comparaison ou agrégation.

## 0.3. Architecture commune

Les trois surfaces suivent la même direction architecturale :

```text
vérités propriétaires canoniques
        ↓
selectors / services / read models propriétaires
        ↓
composition serveur
        ↓
seam Molongo / intelligence lorsque pertinent
        ↓
projection sémantique canonique
        ↓
Web / Flutter Presentation
```

Le futur contrat d'entrée ou de sortie de Molongo n'est pas inventé ici. Tant qu'il n'existe pas, le seam peut rester explicite et neutre.

Règle :

> **Le serveur ne produit pas l'interface. Le client ne reconstruit pas l'écosystème.**

Et :

> **Le client peut interpréter la forme de la donnée ; il ne réinterprète jamais sa vérité métier.**

## 0.4. Équation de rendu

```text
Response serveur
+
contexte / état local client
+
calculs locaux sûrs
+
Presentation
=
unité UX réellement vécue à l'écran
```

Donc :

```text
UNITÉ UX CANONIQUE
≠ RESPONSE SERVEUR
≠ ÉTAT LOCAL CLIENT
≠ VIEW MODEL / PRESENTATION CLIENT
```

## 0.5. Calculs sûrs côté client

Le client peut notamment :

- humaniser dates et heures ;
- formater montants et unités ;
- calculer une distance géométrique à partir de coordonnées légitimement connues ;
- choisir un viewer à partir du type MIME ;
- adapter la densité et le layout au viewport ;
- conserver scroll, sélection, vue, carte, filtres, état d'ouverture ;
- gérer cache, snapshot, outbox, drafts et opérations locales en attente ;
- calculer des durées ou compte-à-rebours sans réinterpréter leur importance métier.

Il ne peut jamais déduire localement :

- qu'une deadline crée une Situation Now ;
- qu'une Membership ou Assignment crée une autorité ;
- qu'un Payment rend une Journey terminée ;
- qu'un document satisfait un Requirement ;
- qu'une possibilité est pertinente ;
- qu'une donnée ancienne reste actuelle ;
- qu'une action sensible est autorisée ;
- qu'une relation propriétaire existe parce que deux textes se ressemblent.

## 0.6. Local-first transversal

Le client local peut conserver ce qui a déjà été légitimement acquis et ce qui permet la continuité personnelle. Il ne devient jamais un mini-serveur Makolo.

```text
SERVER CANONICAL TRUTH
≠ LOCAL SNAPSHOT
≠ LOCAL PENDING STATE
```

Une opération locale en attente ne réécrit jamais la vérité canonique avant confirmation.

Exemple :

```text
serveur : saved = false
client : requête save dans l'outbox
→ « Enregistrement en cours… »
≠ saved = true confirmé
```

## 0.7. Presentation

Presentation représente les faits ; elle ne les possède pas.

Aucune des trois unités n'est un composant UI fixe :

```text
Situation Now ≠ Card
Continuité En cours ≠ Card
Possibilité Discover ≠ Card
```

Un shell visuel partagé est permis. Une sémantique métier universelle rigide ne l'est pas.

---
# I. Now Me — contrat détaillé de référence

## Makolo — UX Now  
### Contrat consolidé de la surface d’attention actuelle et de la Situation Now

**Statut :** cadre UX conceptuel consolidé de travail  
**Portée :** Web et mobile, personnel et Space  
**Nom UX retenu :** `Now`  
**Question humaine :** « Qu’est-ce qui compte maintenant ? »  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

## 1. Objet du document

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

## 2. Place de Now dans Makolo

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

## 3. Définition de Now

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

## 4. Ce que Now n’est pas

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

## 5. La Situation Now

### 5.1. Définition

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

## 6. Situation Now et notion scientifique de Situation

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

## 7. Contexte acteur

Une Situation Now n’existe jamais « globalement » sans perspective.

Elle est toujours relative à un acteur et à un viewer.

### 7.1. `ACTOR_CONTEXT`

Répond à :

> Pour qui cette Situation existe-t-elle ?

Exemples :

```text
Profile Gilbert Bemwiz
Space SOMAF
Space Église X
Space Entreprise Y
```

### 7.2. `VIEWER`

Répond à :

> Qui regarde actuellement ?

Le viewer est généralement un Profile authentifié.

### 7.3. `HUMAN_CONTEXT`

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

### 7.4. `SUBJECT`

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

## 8. Responsabilité, autorité et prochain mouvement

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

### 8.1. `TURN`

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

## 9. Noyau sémantique d’une Situation Now

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

## 10. `STATE`

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

## 11. `DELTA?`

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

## 12. `WHY_NOW`

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

## 13. `CONSEQUENCE`

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

## 14. `RESPONSE`

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

## 15. `HORIZON?`

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

## 16. `MAKOLO_PREPARATION?`

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

## 17. `EXIT_CONDITION`

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

## 18. `OWNER / DEPTH`

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

## 19. Contexte de connaissance

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

## 20. Admission dans Now

Une réalité n’entre pas dans Now simplement parce qu’elle existe.

Une Situation Now est admissible lorsque plusieurs conditions sont réunies :

```text
LEGITIMATE_RELATION
∧ PRESENT_SIGNIFICANCE
∧ CONSEQUENCE
∧ USEFUL_RESPONSE
∧ SUFFICIENT_KNOWLEDGE
```

### 20.1. `LEGITIMATE_RELATION`

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

## 21. Frontière Discover → Now

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

## 22. Situation Now ≠ Card

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

## 23. Densité cognitive

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

## 24. No Orphan Media dans Now

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

## 25. Media Binding

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

## 26. Média ≠ Proof automatique

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

## 27. `PRESENTATION_METADATA`

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

## 28. Composition globale de Now

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

## 29. `ATTENTION SUMMARY?`

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

## 30. `FOREGROUND`

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

## 31. `NEAR`

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

## 32. `WATCHED_BACKGROUND`

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

## 33. `OUT`

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

## 34. Le scroll est légitime

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

## 35. Compression sémantique, pas numérique

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

## 36. État calme

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

## 37. Ordre partiel

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

## 38. Stabilité de l’ordre

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

## 39. Promotion et rétrogradation

Une Situation peut changer de niveau d’attention.

### 39.1. Promotion

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

### 39.2. Rétrogradation

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

## 40. `DELTA` ne signifie pas promotion automatique

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

## 41. Le temps seul ne décide pas

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

## 42. Relations entre Situations

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

## 43. Relation ≠ fusion

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

## 44. Quatre traitements des Situations reliées

Lorsque plusieurs Situations semblent liées, Now peut choisir entre :

```text
A. rester séparées
B. être regroupées visuellement
C. être synthétisées
D. produire une Situation composée
```

---

## 45. Rester séparées

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

## 46. Regroupement visuel

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

## 47. Synthèse

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

## 48. Situation composée

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

## 49. Fusion de faits ≠ Situation composée

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

## 50. Situation composée bornée

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

## 51. Confidentialité avant composition

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

## 52. Cycle d’attention

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

## 53. Axe 1 — Niveau d’attention

```text
FOREGROUND
NEAR
WATCHED_BACKGROUND
OUT
```

---

## 54. Axe 2 — Continuité

```text
NEW
STABLE
CHANGED
RETURNED
```

Cela répond :

> Comment cette Situation se présente-t-elle par rapport à ce que l’acteur connaissait déjà ?

---

## 55. Axe 3 — Événements du cycle

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

## 56. `NEW` ≠ important

Une Situation nouvelle peut entrer directement en arrière-plan.

Une Situation ancienne peut rester au Premier plan.

Principe :

```text
NEW
≠
PRIORITY
```

---

## 57. `SEEN` ≠ résolu

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

## 58. Stabilité

Si rien de significatif n’a changé :

- ne pas recréer la Situation ;
- ne pas la réannoncer comme nouvelle ;
- ne pas mélanger inutilement son ordre ;
- ne pas changer son sens.

Le refresh technique ne doit jamais recréer artificiellement le cycle d’attention.

---

## 59. `RETURNED`

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

## 60. Continuité de projection

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

## 61. Résolution et sortie

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

## 62. Passage de la Situation à l’action réelle

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

## 63. `DIRECT_NOW`

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

## 64. `FOCUSED`

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

## 65. `DOMAIN_DEPTH`

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

## 66. Profondeur dépend du contexte

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

## 67. Makolo Preparation doit réduire la profondeur humaine

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

## 68. Préparer ≠ exécuter

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

## 69. Possibilité technique ≠ autorité

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

## 70. Une décision humaine reste humaine

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

## 71. Now ne possède jamais l’action métier

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

## 72. Feedback et pas de faux succès

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

## 73. Local-first

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

## 74. Refresh

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

## 75. Conservation du contexte

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

## 76. Notification ≠ Situation Now

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

## 77. Conversations

Une conversation peut devenir pertinente dans Now lorsqu’elle porte :

- une décision attendue ;
- une information qui change l’action ;
- un passage de relais ;
- une intervention dont la personne est le prochain acteur.

Un message non lu n’est pas automatiquement une Situation urgente.

---

## 78. Familles de présentation

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

## 79. Profil et Space

Le même concept Situation Now peut servir :

```text
Profile
et
Space
```

Mais leur centre de gravité diffère.

### Profil

> Qu’est-ce qui mérite mon attention maintenant pour que ce que je veux vivre, faire ou obtenir puisse avancer ?

### Space

> Qu’est-ce qui mérite notre attention maintenant pour que ce que nous opérons, produisons ou délivrons puisse avancer ?

Même structure conceptuelle.

Vocabulaire et représentations adaptés au contexte.

---

## 80. Multi-contextes

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

## 81. No Orphan Content / Media

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

## 82. Anti-features

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

## 83. Invariants consolidés

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

## 84. Exemples consolidés

### 84.1. Document prêt

#### Représentation textuelle

```text
Votre document est prêt.
Vous pouvez le lire et le signer pour continuer.

[ Lire et signer ]
Télécharger
```

#### Représentation média

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

### 84.2. Voiture à Ruzizi

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

### 84.3. Départ Space

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

### 84.4. Demande fournisseur

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

### 84.5. Conflit

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

## 85. Schéma conceptuel consolidé

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

## 86. Ce qui reste volontairement ouvert

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

## 87. Doctrine d’implémentation future

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

## 88. Critères de sortie d’une future implémentation Now

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

## 89. Références de cadrage

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

## 90. Formulation finale

> **Now est la surface Makolo qui compose, pour un acteur donné, les Situations qui méritent réellement son attention actuelle. Une Situation Now n’est ni une tâche, ni une notification, ni un objet métier autonome : c’est une projection temporaire de faits suffisamment établis qui explique ce qui se passe, pourquoi cela compte maintenant, ce qui peut arriver, à qui appartient le prochain mouvement et quelle réponse légitime est utile. Now peut être textuel, visuel, documentaire, cartographique ou interactif ; il peut présenter une Situation ou trente ; il peut aider à agir, décider, préparer, attendre, surveiller ou comprendre ; et il peut aussi conclure que tout est en ordre. Il ne possède jamais les vérités métier qu’il représente, n’invente pas d’urgence, ne transforme pas le média en feed et ne retient pas artificiellement l’attention. Son objectif est que Makolo marche pour la personne, puis s’efface lorsque rien d’utile ne reste à faire.**


## Gel conceptuel 2026-10-05 — `NowMeResponse`

Cette section complète le contrat détaillé ci-dessus avec les décisions stabilisées lors de l'étude serveur/client.

### A. Admission

Une Situation Now est admissible lorsque les conditions suivantes sont suffisamment établies :

```text
LEGITIMATE_RELATION
∧ PRESENT_SIGNIFICANCE
∧ CONSEQUENCE
∧ USEFUL_RESPONSE
∧ SUFFICIENT_KNOWLEDGE
```

Une Opportunity pertinente ou urgente en elle-même n'entre pas automatiquement dans Now.

### B. Familles de porteurs sémantiques

Les briques de référence sont :

```text
OBJECT
FACT
RELATION
TRANSITION
COMPOSITION
```

Elles ne remplacent pas les structures spécialisées de `WHY_NOW`, `CONSEQUENCE`, `TURN`, `HORIZON`, `AUTHORITY`, `RESPONSIBILITY`, `ATTENTION`, `BUSINESS_ACTION` ou `MEDIA_BINDING`.

#### `OBJECT`

Un `OBJECT` est une **projection autorisée d'une réalité canonique**, jamais un modèle Django brut.

```text
OBJECT
├── IDENTITY
│   ├── kind
│   └── id
├── REPRESENTATION
├── CONTEXT spécifique au kind
├── CAPABILITIES[]
└── LINKS
```

Trois profondeurs conceptuelles sont distinguées :

```text
REFERENCE
INLINE
DETAIL
```

- `REFERENCE` : relation secondaire compacte ;
- `INLINE` : assez riche pour être compris directement dans Now ;
- `DETAIL` : profondeur propriétaire complète.

Le porteur minimal suffisamment riche doit être préféré. Une `OccurrenceInline` peut, par exemple, contenir Activity + timing + place nécessaires au contexte sans répéter ces objets comme membres parallèles.

#### `FACT`

```text
FACT
├── subject
├── predicate / what
├── value / state
├── time?
└── provenance / source?
```

`FACT` répond à « qu'est-ce qui est vrai ? ».

#### `TRANSITION`

```text
TRANSITION
├── kind
├── subject
├── from?
├── to?
├── at?
└── actor / source?
```

`TRANSITION` répond à « qu'est-ce qui vient de changer ou doit changer ? ».

#### `RELATION`

```text
RELATION
├── kind
├── members[]
└── context / basis?
```

Une relation peut être n-aire. `RELATION ≠ FUSION`.

#### `COMPOSITION`

```text
COMPOSITION
├── members[]
└── relations[]
```

Elle n'est utilisée que lorsqu'aucun porteur canonique unique ne suffit à représenter honnêtement le rôle. Elle reste bornée et ne devient jamais un Journey ou Dossier déguisé.

### C. Cardinalités stabilisées

```text
ACTOR_CONTEXT       exactement 1 OBJECT
VIEWER              exactement 1 Profile
RESPONSIBILITY      0..n responsabilités pertinentes
AUTHORITY           0..1 projection d'autorité effective pertinente
HUMAN_CONTEXT       exactement 1 OBJECT | COMPOSITION
SUBJECT             exactement 1 OBJECT | FACT | RELATION | TRANSITION | COMPOSITION
STATE               exactement 1 FACT
DELTA               0..1 TRANSITION
WHY_NOW             exactement 1 structure de raison
CONSEQUENCE         exactement 1 structure de conséquence
TURN                0..1 prochain mouvement sémantique
RESPONSE            exactement 1
HORIZON             0..1
MAKOLO_PREPARATION  0..n
OWNER_DEPTH         normalement exactement 1
PROVENANCE          0..n
FRESHNESS           exactement 1 structure quand pertinente
KNOWLEDGE_STATE     exactement 1
CONFIDENCE          0..1
ATTENTION LEVEL     exactement 1
CONTINUITY STATE    exactement 1
LIFECYCLE EVENT     0..1
BUSINESS_ACTIONS    0..n
MEDIA_BINDINGS      0..n
```

### D. Responsibility, Authority, Turn

```text
RESPONSIBILITY
→ qui porte réellement une responsabilité opérationnelle ?

AUTHORITY
→ qui possède l'autorité légitime dans cette portée ?

TURN
→ à qui appartient le prochain mouvement ?

BUSINESS_ACTION
→ qu'est-ce qui peut réellement être fait maintenant ?
```

Ces quatre questions restent distinctes.

`RESPONSIBILITY` est naturellement plurielle lorsque plusieurs Assignments pertinents coexistent. `AUTHORITY` est une projection effective agrégée par le serveur à partir de Mandates/Permissions et règles propriétaires ; le client ne reçoit pas une liste brute de Mandates à recalculer.

`TURN` est borné conceptuellement à :

```text
PROFILE
COLLECTIVE
EXTERNAL
MAKOLO
NONE
```

`SYSTEM` n'est pas introduit comme faux acteur général : le temps ou un traitement automatisé peuvent conduire à `TURN = NONE` avec un `HORIZON` ou une attente adaptée.

### E. `STATE`, `DELTA`, `WHY_NOW`, `CONSEQUENCE`

```text
STATE
→ FACT

DELTA
→ TRANSITION?

WHY_NOW
→ REASON + BASIS[]

CONSEQUENCE
→ TARGET + EFFECT (+ condition/horizon si nécessaire)
```

Le client ne décide jamais seul qu'un fait ou un delta justifie l'attention actuelle.

### F. `HORIZON`

`HORIZON` n'est pas réduit à une date :

```text
HORIZON
├── TEMPORAL
└── EVENT
```

Exemples : avant vendredi, dans 35 minutes, jusqu'à la réponse du fournisseur, à l'ouverture des inscriptions.

### G. Knowledge Context

```text
KNOWLEDGE_CONTEXT
├── PROVENANCE[]
├── FRESHNESS
├── KNOWLEDGE_STATE
│   ├── KNOWN
│   ├── UNKNOWN
│   ├── CONTRADICTORY
│   ├── STALE
│   └── UNAVAILABLE
└── CONFIDENCE? si défendable
```

La fraîcheur métier serveur reste distincte de la fraîcheur du snapshot client.

### H. Attention

```text
ATTENTION
├── LEVEL
│   ├── FOREGROUND
│   ├── NEAR
│   ├── WATCHED_BACKGROUND
│   └── OUT
├── CONTINUITY_STATE
│   ├── NEW
│   ├── STABLE
│   ├── CHANGED
│   └── RETURNED
└── LIFECYCLE_EVENT?
    ├── ENTERED
    ├── UPDATED
    ├── REACTIVATED
    ├── RESOLVED
    └── EXITED
```

```text
NEW ≠ PRIORITY
SEEN ≠ RESOLVED ≠ DEMOTED
WAIT = RESPONSE, pas lifecycle
```

### I. Actions et profondeur

Une Situation peut exposer plusieurs actions. Chaque action garde sa profondeur propre :

```text
BUSINESS_ACTION
├── intent / action
├── target
├── owner / handoff
├── capability
├── interaction_depth
│   ├── DIRECT_NOW
│   ├── FOCUSED
│   ├── DOMAIN_DEPTH
│   └── NONE
└── confirmation/context owner-backed si nécessaire
```

Toute mutation appartient au domaine propriétaire et est revalidée côté serveur.

### J. Média

```text
MEDIA_BINDING
├── RESOURCE
├── TARGET
└── PURPOSE
    ├── RECOGNIZE
    ├── UNDERSTAND
    ├── ESTABLISH
    ├── PREPARE
    └── ACT
```

Un média peut cibler Situation, Subject, Human Context, State, Delta, Turn, Makolo Preparation ou une Action. `Média ≠ Proof automatique`.

### K. État racine

Le contrat parfait distingue l'état d'attention de l'acteur :

```text
ACTOR_ATTENTION_STATE
→ ACTIVE | CALM
```

`CALM` peut coexister avec des Situations en arrière-plan surveillées par Makolo ou un tiers. Il ne se réduit donc pas nécessairement à `situations.length == 0`.

### L. Contrat conceptuel serveur final

```text
NOW ME RESPONSE
│
├── ACTOR_CONTEXT
├── VIEWER
├── ACTOR_ATTENTION_STATE
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

`EXIT_CONDITION` reste conceptuellement obligatoire côté moteur/projection, mais n'a pas besoin d'être exposée au client par défaut.

### M. Ce qui reste volontairement non figé

- noms JSON définitifs ;
- `schema_version` final ;
- calcul/persistance exacte de `CONTINUITY_IDENTITY` ;
- forme exacte des projections `REFERENCE / INLINE / DETAIL` par kind ;
- endpoints définitifs de chaque owner ;
- futur contrat Molongo.


---

# II. Ongoing Me / En cours — contrat détaillé de référence

## Makolo — UX En cours
### Contrat consolidé de la continuité personnelle

**Statut :** cadre UX conceptuel consolidé de travail  
**Portée :** expérience personnelle Web et mobile ; grammaire réutilisable par `Métier` dans un Space  
**Nom UX retenu :** `En cours`  
**Question humaine :** « Pour ce que j’ai déjà engagé, où en suis-je et qu’est-ce qui continue ? »  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »  
**Base runtime vérifiée avant consolidation :** `main@6fda1e8c448aacd0100e72d02103d92b5a9ed079`

---

## 1. Objet du document

Ce document fixe le contrat conceptuel de **En cours**, la surface personnelle Makolo consacrée à la continuité de ce que le Profile a réellement engagé.

Il consolide notamment :

- la définition d’une réalité engagée ;
- les critères d’admission dans En cours ;
- l’unité de composition appelée ici **Continuité En cours** ;
- la base canonique permettant de justifier une continuité ;
- la stabilité d’identité d’une continuité à travers plusieurs propriétaires ;
- la synthèse « où j’en suis » ;
- ce qui est réglé ;
- ce qui reste du côté de la personne ;
- ce qui continue ailleurs ;
- ce que Makolo prépare ou surveille ;
- ce qui vient ensuite ;
- les blocages et leurs limites ;
- l’horizon et la connaissance disponible ;
- les relations entre Continuités ;
- la composition globale de la surface ;
- la lecture temporelle / Calendrier ;
- la représentation, les médias et la profondeur ;
- la frontière avec Now, Discover, Moi, Jour J, Historique et Métier ;
- les règles local-first, de fraîcheur, de retour et de continuité cognitive ;
- les anti-features ;
- les points volontairement laissés ouverts avant l’implémentation mature.

Ce document est un **contrat UX et de projection**.

Il ne fixe pas :

- un nouveau modèle métier ;
- une table `Continuity` ;
- une table `Engagement` ;
- un nouveau lifecycle universel ;
- un nouveau Readiness ;
- un format API définitif ;
- une clé technique définitive de continuité ;
- un algorithme de ranking ;
- un nombre maximum de Continuités ;
- une maquette pixel-perfect ;
- un composant visuel unique ;
- une politique définitive de persistance ;
- un graphe métier parallèle ;
- un vocabulaire backend supplémentaire.

Le runtime courant, les propriétaires canoniques, leurs permissions et leurs tests restent prioritaires.

---

## 2. Place de En cours dans Makolo

Les principales surfaces personnelles répondent à des questions différentes.

```text
Discover
→ Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?

Now
→ Qu’est-ce qui mérite mon attention maintenant ?

En cours
→ Parmi ce que j’ai réellement engagé, où en suis-je et qu’est-ce qui continue ?

Moi
→ Qu’est-ce qui est déjà en place autour de moi pour faciliter la suite ?

Jour J / Live
→ Qu’est-ce que je suis effectivement en train de vivre ou d’accomplir maintenant ?

Historique
→ Qu’est-ce qui est terminé et reste utile à retrouver ?
```

En cours ne cherche donc pas à sélectionner uniquement ce qui est urgent.

Il conserve la **continuité intelligible** de ce qui reste ouvert pour la personne.

Une réalité peut rester En cours pendant des semaines sans mériter Now.

Inversement, une Situation Now peut exister sans devenir une Continuité durable dans En cours.

---

## 3. Définition de En cours

> **En cours est la projection personnelle de la continuité des réalités que le Profile a effectivement engagées et dont une suite pertinente existe encore pour lui.**

Sa question humaine peut être développée ainsi :

> **Pour ce que j’ai déjà engagé, puis-je avancer tranquille — et sinon, qu’est-ce qui reste réellement de mon côté ?**

En cours réduit la charge mentale liée aux réalités déjà engagées.

Il évite à la personne de devoir reconstruire elle-même une continuité à partir de Journey, Payment, Access, Requirement, Waitlist, Dossier, Project, Occurrence, documents, réservations ou validations dispersés.

---

## 4. Ce que En cours n’est pas

En cours n’est pas :

- une liste de tâches ;
- une liste de Journey ;
- une liste de Dossier ;
- une liste de Project ;
- une liste d’Access ;
- une liste de Payment ;
- une liste de Waitlist ;
- une boîte de réception ;
- une timeline complète ;
- un historique ;
- un dashboard ;
- un moteur de priorité ;
- un deuxième Now ;
- un deuxième Readiness ;
- un task manager ;
- un workflow universel ;
- un graphe causal propriétaire ;
- une projection Molongo ;
- une mesure de masse ou d’engagement physique ;
- un conteneur de tous les objets auxquels le Profile est lié.

Les domaines propriétaires fournissent les faits.

En cours compose leur **sens de continuité humaine**.

---

## 5. Réalité engagée

### 5.1. Définition

> **Une réalité engagée est une réalité avec laquelle le Profile a franchi une frontière effective entre possibilité et poursuite, et dont une suite pertinente existe encore pour lui.**

La suite peut consister à :

- agir ;
- attendre ;
- préparer ;
- bénéficier d’un droit ;
- poursuivre un objectif ;
- recevoir une réponse ;
- vivre une Occurrence ;
- obtenir quelque chose ;
- terminer une réalisation ;
- recevoir une conséquence encore ouverte.

Le terme « engagée » est ici un terme UX de poursuite.

Il ne désigne pas l’engagement constitutif utilisé par l’Univers Molongo dans ses grandeurs physiques.

---

## 6. Admission dans En cours

Une réalité ne devient pas En cours simplement parce qu’elle existe dans le backend.

La règle conceptuelle est :

```text
PERSONAL_RELATION
∧ EFFECTIVE_PURSUIT
∧ CONTINUATION
∧ REMAINING_RELEVANCE
∧ LEGITIMATE_VISIBILITY
```

### 6.1. `PERSONAL_RELATION`

La poursuite concerne réellement le Profile dans son contexte personnel.

Exemples :

- bénéficiaire ;
- demandeur ;
- détenteur d’un droit ;
- participant ;
- initiateur personnel ;
- personne en Waitlist ;
- destinataire ou expéditeur d’un transfert personnel ;
- propriétaire personnel d’un Dossier ou Project réellement poursuivi.

Le simple fait d’apparaître quelque part dans les données ne suffit pas.

### 6.2. `EFFECTIVE_PURSUIT`

Une frontière réelle a été franchie entre possibilité et poursuite.

Exemples :

```text
Opportunity simplement vue
→ non

candidature effectivement commencée
→ potentiellement oui
```

```text
Activity simplement découverte
→ non

participation / réservation réellement engagée
→ oui
```

```text
idée conservée sans suite
→ non nécessairement

Dossier réellement commencé pour atteindre l’objectif
→ oui
```

La frontière reste dérivée des vérités propriétaires.

Il ne faut pas ajouter un champ générique `is_engaged` pour la fabriquer.

### 6.3. `CONTINUATION`

Quelque chose possède encore une suite.

Il peut rester :

- une transition ;
- une attente ;
- une échéance ;
- un droit à utiliser ;
- une réponse à recevoir ;
- une Occurrence à vivre ;
- une action de la personne ;
- une action d’un tiers ;
- une clôture à constater ;
- un résultat à produire.

### 6.4. `REMAINING_RELEVANCE`

La suite doit encore avoir du sens pour la personne.

Un objet peut exister techniquement sans avoir encore de raison d’apparaître dans En cours.

### 6.5. `LEGITIMATE_VISIBILITY`

La projection respecte la visibilité, la confidentialité et l’autorité des propriétaires.

Composer plusieurs faits ne donne aucun nouveau droit de voir leur contenu.

---

## 7. En cours personnel et contexte Space

En cours personnel n’est pas la somme de tout ce qu’un Profile fait dans Makolo.

Une personne peut simultanément :

```text
agir comme elle-même
et
agir au nom d’un Space
```

Ces contextes restent distincts.

Exemple :

```text
Affecter le véhicule d’un départ SOMAF
→ Métier / Now du Space SOMAF
```

alors que :

```text
Gilbert détient personnellement un billet pour ce départ
→ En cours personnel de Gilbert
```

Invariant :

```text
Profile présent dans les données
≠
Continuité personnelle
```

Une responsabilité dans un Space ne transfère pas la réalité dans En cours personnel.

Assignment reste responsabilité.

Mandate / Permission restent autorité.

---

## 8. L’unité de composition : la Continuité En cours

### 8.1. Définition

> **Une Continuité En cours est la plus petite projection humainement cohérente d’une poursuite effectivement engagée dont la suite reste pertinente pour le Profile.**

Elle répond principalement à :

> **Où en suis-je dans cette chose que j’ai déjà engagée ?**

Une Continuité peut être fondée sur un seul propriétaire ou composer plusieurs réalités canoniques reliées.

Mais :

```text
Continuité En cours
≠ Journey
≠ Dossier
≠ Project
≠ Access
≠ Payment
≠ Waitlist
≠ Occurrence
≠ Card
≠ nouveau modèle métier
```

---

## 9. Objet propriétaire ≠ unité UX

Une projection comme :

```text
Journey
Payment
Requirement
Access
```

peut représenter une seule réalité humaine.

Exemple :

```text
Visa Canada
```

peut être constitué par :

```text
Journey
+ Payment
+ Requirements
+ rendez-vous
+ documents
```

La personne ne doit pas nécessairement voir cinq entrées concurrentes.

Elle peut voir :

```text
Visa Canada

Demande déposée.
Frais réglés.
Le consulat examine le dossier.
Biométrie le 18 octobre.
```

Les vérités restent chez leurs propriétaires.

---

## 10. `CONTINUITY_BASIS`

Nous n’utilisons pas un ancrage unique obligatoire.

Conceptuellement :

```text
CONTINUITY_BASIS
```

désigne :

> **l’ensemble minimal de faits et relations canoniques qui permet de justifier que plusieurs éléments appartiennent à la même poursuite humaine.**

La base peut être :

```text
un Journey
```

ou :

```text
Waitlist
+ relation canonique vers Access
+ Occurrence concernée
```

ou une autre composition légitimement démontrée.

La base ne peut jamais être créée seulement à partir :

- d’un titre similaire ;
- d’une date similaire ;
- d’une proximité textuelle ;
- d’une inférence de présentation non supportée.

---

## 11. `CONTINUITY_IDENTITY`

En cours a besoin d’une identité conceptuelle de stabilité.

```text
CONTINUITY_IDENTITY
```

signifie :

> **l’identité de stabilité d’une projection humaine tant que les faits canoniques permettent encore de reconnaître la même poursuite engagée.**

Elle permet de comprendre qu’une même continuité peut passer par :

```text
Waitlist
→ place offerte
→ Access
→ Occurrence
```

sans être présentée comme quatre histoires sans rapport.

Mais :

```text
CONTINUITY_IDENTITY
≠ identité métier
```

Ce document ne décide pas :

- si elle est persistée ;
- comment elle est calculée ;
- si une clé serveur existe ;
- si elle est reconstruite localement ;
- quel algorithme la produit.

Il fixe seulement le besoin UX de continuité.

---

## 12. `HUMAN_CONTEXT`

Une Continuité doit parler dans le vocabulaire humain de sa réalité.

Exemples :

```text
Visa Canada
Voyage Nairobi
Formation Data Science
Commande de l’ordinateur
Contrat d’édition
Réparation de la toiture
```

Le nom visible ne doit pas exposer inutilement :

```text
Journey #481
Payment Obligation
Access object
Dossier lifecycle
```

Backend générique, métier contextuel.

---

## 13. Synthèse de continuité

Le noyau de la représentation est :

```text
SYNTHESIS
→ Où j’en suis ?
```

Cette synthèse n’est pas un statut universel.

Elle résulte de plusieurs dimensions.

Exemples :

> Demande déposée. Le consulat examine votre dossier.

> Tout est prêt pour lundi.

> Vous avez fait votre part. Nous attendons la réponse du fournisseur.

> Votre commande est préparée et attend la remise.

Ces phrases sont des représentations de faits.

Elles ne deviennent pas des états métier persistants.

---

## 14. Pas de `MOTION` canonique

En cours ne possède pas un lifecycle universel :

```text
PREPARING
→ WAITING
→ READY
→ REALIZING
→ DONE
```

Une même Continuité peut simultanément avoir :

```text
document
→ prêt

demande
→ en attente

transport
→ en préparation

paiement
→ réglé
```

Par conséquent, des termes comme :

- préparer ;
- avancer ;
- attendre ;
- prêt ;
- réaliser ;

peuvent être utilisés pour expliquer humainement la situation, mais ne constituent pas un axe canonique obligatoire d’En cours.

---

## 15. Quatre dimensions fondamentales de compréhension

La continuité doit pouvoir répondre à quatre questions principales :

```text
SETTLED[]
MY_SIDE[]
ELSEWHERE[]
NEXT[]
```

Ces dimensions ne sont pas quatre blocs obligatoires de l’interface.

Elles peuvent être synthétisées en une ou deux phrases lorsqu’elles sont suffisantes.

---

## 16. `SETTLED[]` — ce qui est déjà réglé

`SETTLED` représente ce que la personne n’a plus besoin de refaire ou de rechercher pour cette poursuite.

Exemples :

```text
frais confirmés
place sécurisée
Access disponible
document reçu
condition satisfaite
réservation confirmée
```

En cours ne montre pas toutes les vérifications techniques satisfaites.

Il ne montre que celles qui réduisent réellement l’incertitude ou expliquent la suite.

---

## 17. `MY_SIDE[]` — ce qui reste de mon côté

`MY_SIDE` répond à :

> **Dans ce que j’ai déjà engagé, qu’est-ce qui reste réellement de mon côté pour que la suite puisse avancer ?**

Exemples :

```text
transmettre le certificat
choisir un créneau
signer le document
prendre rendez-vous
présenter le credential
```

Important :

```text
MY_SIDE
≠
action à faire maintenant
```

Une action peut rester du côté de la personne tout en pouvant attendre.

Si elle devient digne d’attention actuelle, Now peut la projeter comme Situation Now.

---

## 18. `ELSEWHERE[]` — ce qui continue ailleurs

`ELSEWHERE` représente ce qui continue légitimement hors de l’intervention actuelle de la personne.

Exemples :

```text
le consulat examine
le fournisseur doit répondre
le transporteur a pris en charge
l’université évalue
le paiement est en confirmation distante
```

En cours doit savoir dire :

> Vous avez fait votre part.

> Nous attendons la suite.

> Rien à faire de votre côté pour l’instant.

Une attente normale n’est pas un échec de l’expérience.

---

## 19. `MAKOLO[]` — ce que Makolo prépare ou surveille

La continuité peut aussi exposer ce que Makolo fait réellement lorsque le runtime le permet.

Exemples :

```text
documents retrouvés
formulaire préparé
échéance surveillée
source revalidée
informations regroupées
```

Mais le langage doit rester exact :

```text
préparé
≠ envoyé

envoyé
≠ confirmé

confirmé
≠ résultat humain accompli
```

Makolo ne franchit jamais une frontière d’autorité ou de consentement simplement parce qu’il peut techniquement préparer quelque chose.

---

## 20. `SYSTEM_OR_TIME[]`

Certaines suites dépendent principalement :

- du temps ;
- d’une fenêtre ;
- d’un traitement automatisé autoritatif ;
- d’un événement futur déjà établi.

Exemples :

```text
les inscriptions ouvrent lundi
la période de retrait commence le 18
la réservation devient utilisable à 14 h
```

Cela permet d’éviter de forcer un acteur humain fictif dans chaque transition.

---

## 21. `NEXT[]` — ce qui vient ensuite

Une Continuité peut posséder plusieurs prochaines réalités significatives.

Conceptuellement :

```text
NEXT[]
```

peut contenir :

```text
réponse du consulat
biométrie mardi
ouverture de la période de retrait
début de l’Occurrence
```

La racine En cours peut n’en montrer qu’une seule lorsqu’un repère domine réellement.

En cours ne doit jamais transformer `NEXT[]` en la liste exhaustive de toutes les étapes futures.

La profondeur propriétaire possède le détail lorsque nécessaire.

---

## 22. `HORIZON`

Une Continuité peut avoir un horizon :

- date limite ;
- prochaine fenêtre ;
- début d’Occurrence ;
- réponse attendue ;
- période d’Access ;
- autre événement suffisamment établi.

L’horizon sert à comprendre la suite.

Il ne doit pas être inventé pour rendre la représentation plus précise qu’elle ne l’est réellement.

---

## 23. Blockers relatifs

En cours ne possède pas un statut universel :

```text
CONTINUITY = BLOCKED
```

sans préciser ce qui est réellement bloqué.

Un blocker doit conceptuellement pouvoir répondre à :

```text
SOURCE
BLOCKS
HORIZON?
ALTERNATIVES?
```

Autrement dit :

> Qu’est-ce qui empêche quoi, dans quel horizon, et existe-t-il une autre voie ?

Une Continuité peut ensuite être synthétisée comme bloquée uniquement lorsque cette formulation est réellement justifiée.

---

## 24. Attente, blocage, risque et inconnue

Ces notions restent distinctes :

```text
WAITING
≠ BLOCKED
≠ RISK
≠ UNKNOWN
```

Exemples :

```text
Le consulat examine le dossier.
→ attente
```

```text
Le traitement ne peut pas continuer sans passeport.
→ blocage possible
```

```text
Makolo ne sait pas si le passeport a été reçu.
→ inconnue
```

```text
Le délai devient court et le document peut arriver trop tard.
→ risque
```

Une absence d’information ne doit jamais devenir un blocage réel par défaut.

---

## 25. Readiness

Readiness reste une projection dérivée appartenant à son contrat propre.

En cours peut consommer Readiness pour expliquer :

- ce qui est prêt ;
- ce qui manque ;
- ce qui bloque ;
- la prochaine action utile.

Mais :

```text
Readiness
≠ En cours
```

et :

```text
pas de ContinuityReadiness universel
```

En cours ne duplique ni les checks, ni le statut, ni les règles de Readiness.

---

## 26. Contexte de connaissance

Une Continuité peut dépendre d’informations plus ou moins fraîches.

Conceptuellement :

```text
KNOWLEDGE_CONTEXT

PROVENANCE?
FRESHNESS
KNOWLEDGE_STATE
CONFIDENCE? seulement si défendable
```

Exemples de connaissance :

```text
KNOWN
UNKNOWN
CONTRADICTORY
STALE
UNAVAILABLE
```

Exemple :

```text
Votre colis est à Lubumbashi.
```

est différent de :

```text
Dernière position connue : Lubumbashi · hier 18:40.
```

Une donnée locale ancienne peut rester utile à la compréhension sans être présentée comme vérité actuelle.

---

## 27. Trois notions de fin à ne pas confondre

Il faut distinguer :

```text
OWNER_COMPLETION
OUTCOME
CONTINUITY_EXIT
```

### 27.1. `OWNER_COMPLETION`

Un propriétaire termine son cycle.

Exemple :

```text
Payment = SUCCESS
```

### 27.2. `OUTCOME`

Un résultat humain pertinent est réellement atteint.

Exemples :

```text
billet obtenu
commande réellement remise
formation réellement suivie
visa réellement accordé
```

### 27.3. `CONTINUITY_EXIT`

Il ne reste plus de suite pertinente à représenter dans En cours.

Ces trois événements peuvent être séparés dans le temps.

---

## 28. `CONTINUITY_EXIT_CONDITION`

Toute Continuité possède conceptuellement une condition de sortie.

```text
CONTINUITY_EXIT_CONDITION
```

répond à :

> **Qu’est-ce qui devra être vrai pour que cette poursuite n’ait plus de suite pertinente dans En cours ?**

Exemples :

```text
objectif réellement atteint
réalisation achevée sans suite
abandon
annulation
expiration sans continuation
transformation vers une autre continuité réellement distincte
```

Après sortie, les réalités peuvent rester disponibles dans :

- Historique ;
- Moi ;
- Proof ;
- Credential ;
- domaines propriétaires ;
- autres projections légitimes.

---

## 29. Une Continuité peut traverser plusieurs propriétaires

Exemple :

```text
Waitlist
→ place offerte
→ Access
→ Occurrence
→ réalisation réelle
```

La fin de Waitlist ne signifie pas nécessairement la fin de la Continuité.

De même :

```text
Payment terminé
≠ Continuité terminée
```

ou :

```text
Occurrence terminée
≠ automatiquement aucune suite
```

La Continuité suit la poursuite humaine, pas la durée de vie d’un objet arbitraire.

---

## 30. Relations entre Continuités

Plusieurs Continuités peuvent être reliées.

Les sémantiques utiles peuvent inclure :

```text
DEPENDENCY
FACILITATION
SHARED_RESOURCE
SYNCHRONIZATION
CONFLICT
MUTUALIZATION
ALTERNATIVE
CASCADE
FEEDBACK
```

Mais En cours n’est pas propriétaire d’un nouveau graphe métier.

La direction correcte est :

```text
relation canonique / orchestration
        ↓
projection utile de la relation
        ↓
En cours
```

Seules les relations qui changent réellement la compréhension ou la suite doivent être représentées.

---

## 31. Relation ≠ fusion

Deux Continuités fortement reliées peuvent rester distinctes.

Elles restent séparées lorsque leurs :

- évolutions ;
- horizons ;
- résultats ;
- actions ;
- propriétaires ;
- fins ;

peuvent diverger de manière significative pour la personne.

Exemple :

```text
Visa
DEPENDS_ON
Passeport
```

peut rester deux Continuités si le renouvellement du passeport possède sa propre poursuite autonome.

---

## 32. Relations n-aires

Une relation n’est pas obligatoirement binaire.

Exemple :

```text
Rendez-vous médical
Entretien professionnel
Vol
        ↓
même ressource temps vendredi
```

Il ne faut pas forcer artificiellement toutes les relations pair-à-pair si la vérité porte sur une ressource partagée commune.

---

## 33. Même contexte ≠ relation causale

Des Continuités peuvent partager un contexte humain :

```text
Voyage Nairobi
```

avec :

```text
Visa
Vol
Formation
```

sans qu’elles dépendent toutes causalement les unes des autres.

Ce partage appartient à la composition de présentation.

Conceptuellement :

```text
PRESENTATION_GROUP
```

et non :

```text
DEPENDENCY
```

Le contexte aide à lire.

Il n’invente pas une causalité.

---

## 34. Relation En cours → Situation Now

Une relation entre Continuités peut créer une conséquence actuelle.

Exemple :

```text
Continuité A
→ rendez-vous médical vendredi 10 h

Continuité B
→ entretien vendredi 10 h
```

La relation reste observable dans En cours.

Mais si elle exige un arbitrage actuel, Now peut produire :

> Deux engagements se chevauchent vendredi.

La règle est :

```text
Continuités + relation
→ conséquence actuelle digne d’attention
→ Situation Now
```

Une relation ne crée normalement pas une nouvelle Continuité durable.

Après résolution de la Situation Now, les Continuités sources peuvent continuer.

---

## 35. Composition globale de En cours

La structure conceptuelle de la racine est :

```text
EN COURS
│
├── ACTOR = Profile
│
├── OVERVIEW ?
│
├── PRESENTATION GROUPS ?
│   ├── CONTINUITY
│   ├── CONTINUITY
│   └── ...
│
├── UNGROUPED CONTINUITIES
│
└── CALENDAR
    └── temporal projection
```

Les groupes sont facultatifs.

Les Continuités n’ont pas besoin d’être forcées dans des rubriques universelles comme :

```text
Bloqué
En attente
Prêt
À venir
```

car plusieurs dimensions peuvent coexister dans une même Continuité.

---

## 36. Pas de Top N conceptuel

Si la personne possède réellement :

```text
3 Continuités
15 Continuités
50 Continuités
```

elles doivent rester accessibles.

Le produit ne doit pas cacher arbitrairement des réalités légitimes pour respecter un quota visuel.

Le scroll sur la réalité est normal.

Le scroll artificiellement prolongé pour retenir l’attention ne l’est pas.

Une limite technique de read model, de pagination ou de synchronisation n’est pas une règle UX disant que les autres Continuités n’existent pas.

---

## 37. Le budget runtime actuel n’est pas le contrat UX

Le runtime `personal.ongoing` est actuellement borné.

Cette borne sert la projection existante.

Elle ne signifie pas :

```text
un Profile ne peut avoir que N réalités En cours
```

Une future implémentation mature doit distinguer :

```text
budget technique
pagination / chargement
contrat de synchronisation
```

de :

```text
admission UX réelle
```

---

## 38. Ordre de lecture

En cours ne définit pas encore un ranking global.

L’ordre doit être :

- stable ;
- compréhensible ;
- compatible avec les prochains moments significatifs ;
- compatible avec les mouvements encore ouverts ;
- sensible au contexte humain lorsque cela aide.

Il ne doit pas devenir un score opaque disant quelles réalités « comptent le plus dans la vie ».

À importance de lecture comparable et sans changement significatif, la stabilité doit être privilégiée.

---

## 39. Regroupements humains

Les regroupements peuvent utiliser un contexte compréhensible :

```text
Voyage Nairobi
    Visa
    Vol
    Formation

Mon livre
    Correction
    Dossier éditeur
```

Le regroupement :

- n’efface pas les identités ;
- ne transfère aucune autorité ;
- n’invente aucune relation métier ;
- n’oblige pas toutes les Continuités à appartenir à un groupe.

---

## 40. Calendrier En cours

Le header personnel peut exposer :

```text
En cours | Calendrier | Avatar
```

Le Calendrier répond à :

> **Quand les réalités déjà engagées vont-elles rencontrer mon temps ?**

Il n’est pas propriétaire des événements.

---

## 41. `TEMPORAL_FACTS`

Le Calendrier est une projection temporelle des faits significatifs associés aux Continuités admises.

Une Continuité peut produire plusieurs faits temporels :

```text
12 octobre
→ document attendu

18 octobre
→ biométrie

3 novembre
→ départ
```

Un même fait temporel peut également concerner plusieurs Continuités.

Conceptuellement :

```text
TEMPORAL FACT
→ 1..n Continuités
→ représentation Calendrier
```

---

## 42. Timestamp backend ≠ événement humain

Ne deviennent pas automatiquement des entrées Calendrier :

```text
created_at
updated_at
synced_at
last_seen_at
```

Un fait temporel doit avoir un sens humain réel pour la continuité.

Exemples admissibles selon les propriétaires :

- Occurrence ;
- rendez-vous ;
- deadline ;
- ouverture de fenêtre ;
- période d’Access ;
- période de retrait ;
- autre moment canonique réellement établi.

---

## 43. Le Calendrier n’impose pas une grille mensuelle

La meilleure représentation peut être :

- liste chronologique ;
- timeline ;
- semaine ;
- mois ;
- agenda focalisé ;
- autre représentation adaptée.

Le contrat fixe la fonction.

Il ne fige pas le composant.

---

## 44. Continuité ≠ Card

Une Continuité est une unité sémantique.

Sa représentation peut être :

- une ligne ;
- un bloc ;
- une Card ;
- du texte ;
- un aperçu document ;
- une image contextualisée ;
- une carte géographique ;
- une mini-timeline légitime ;
- une composition de plusieurs éléments.

Le nom d’un composant UI ne crée jamais un modèle métier.

---

## 45. Ce que la racine doit permettre de comprendre

Sans obliger une mise en page fixe, une représentation racine devrait idéalement permettre de comprendre :

```text
QUOI ?
OÙ J’EN SUIS ?
QU’EST-CE QUI RESTE DE MON CÔTÉ ?
QU’EST-CE QUI CONTINUE AILLEURS ?
QU’EST-CE QUI VIENT ENSUITE ?
```

Exemple :

> **Visa Canada**  
> Dossier en examen · rien à faire de votre côté  
> Biométrie le 18 octobre

Il n’est pas nécessaire d’imprimer les cinq questions.

---

## 46. No Orphan Media

En cours réutilise la doctrine média commune de Makolo.

Un média doit aider à :

```text
RECOGNIZE
UNDERSTAND
ESTABLISH
PREPARE
ACT
```

Exemples :

```text
photo du véhicule
→ reconnaître

carte du trajet
→ comprendre

aperçu du document
→ préparer / agir

credential
→ agir
```

Un média n’est pas ajouté pour rendre la surface plus attractive.

---

## 47. Média ≠ Proof automatique

Une image ou un document présenté dans En cours reste une représentation.

```text
aperçu du passeport
≠ Proof automatiquement
≠ Requirement satisfait automatiquement
```

L’admission comme Proof, Evidence ou satisfaction d’un Requirement appartient au propriétaire compétent.

---

## 48. Pas de progression générique

En cours ne doit pas inventer :

```text
72 %
```

simplement parce que plusieurs étapes sont connues.

```text
3 étapes sur 5
≠ nécessairement 60 % accompli
```

Une étape restante peut être décisive.

Une Journey peut être non linéaire.

Un pourcentage n’est affiché que si un propriétaire possède réellement une mesure de progression valable.

---

## 49. Timeline seulement si réelle

Une timeline peut aider lorsqu’une séquence est suffisamment établie.

Exemple :

```text
Demande déposée
→ examen
→ biométrie
```

Elle ne doit pas inventer un workflow linéaire lorsqu’il existe :

- parallélisme ;
- alternatives ;
- bifurcations ;
- dépendances externes ;
- transitions non ordonnées.

---

## 50. Progressive disclosure

La profondeur peut suivre :

```text
ROOT SUMMARY
    ↓
CONTINUITY COMPOSITION si utile
    ↓
OWNER DEPTH
```

### 50.1. Racine

Assez pour reconnaître et comprendre où en est la poursuite.

### 50.2. Composition de Continuité

Assez pour comprendre :

- ce qui est réglé ;
- ce qui reste ;
- ce qui continue ailleurs ;
- les relations utiles ;
- les documents ou médias utiles ;
- les prochains moments.

Cette profondeur n’est pas obligatoire pour chaque Continuité.

### 50.3. Propriétaire

Quand le traitement exige la vérité complète :

```text
Journey
Dossier
Access
Payment
Occurrence
Order
etc.
```

on entre dans le propriétaire.

---

## 51. En cours ne possède jamais l’action métier

Même lorsqu’une action apparaît depuis En cours :

```text
[ Transmettre le document ]
[ Choisir un créneau ]
[ Voir mon accès ]
```

la mutation appartient au propriétaire.

Flux :

```text
En cours
↓
intention / action
↓
domaine propriétaire
↓
vérité canonique
↓
reprojection
↓
Continuité actualisée / transformée / sortie
```

Jamais :

```text
Continuité
→ change son propre statut métier
→ synchronise ensuite
```

---

## 52. Autorité

Une action visible doit toujours respecter :

- Permission ;
- Mandate ;
- Access ;
- ownership ;
- visibilité ;
- autres règles du domaine propriétaire.

Dans le contexte personnel, l’existence d’une Continuité ne suffit pas à autoriser toute action sur ses constituants.

Composition ne signifie jamais transfert d’autorité.

---

## 53. Feedback et niveau réel atteint

Le feedback doit exprimer uniquement ce qui est réellement vrai.

Exemples :

```text
préparé
enregistré localement
en attente de synchronisation
synchronisé
envoyé
en attente de confirmation
confirmé
accompli
conflit
échec
```

Ne jamais utiliser :

```text
Confirmé
```

si seul un envoi a été effectué.

Ne jamais considérer un Payment comme preuve universelle d’accomplissement.

---

## 54. Local-first

En cours se prête particulièrement bien au local-first parce qu’il porte des réalités déjà liées à la personne.

Le client peut conserver, lorsque les contrats le permettent :

- projections En cours ;
- Journey déjà connus ;
- Dossier déjà connus ;
- Activities / Occurrences déjà synchronisées ;
- certains Access ;
- Requirements et états de préparation connus ;
- ressources explicitement disponibles localement.

Mais le client local ne devient jamais l’autorité pour :

- Permission ;
- Mandate ;
- Access partagé ;
- Payment ;
- Capacity globale ;
- concurrence entre personnes ;
- état actuel du monde à partir d’une copie potentiellement ancienne.

---

## 55. Offline

Une Continuité peut rester utile offline.

Exemple :

> **Visa Canada**  
> Dernière mise à jour : hier 18:40  
> Dossier en examen lors de la dernière synchronisation.

Il est interdit de transformer une ancienne donnée en vérité actuelle.

Une action nécessitant une confirmation autoritative doit être présentée comme telle.

---

## 56. Refresh

Lors d’un refresh :

```text
contenu actuel
+ indicateur discret
→ contenu actualisé
```

est préférable à :

```text
contenu
→ vide
→ skeleton
→ contenu
```

Le refresh technique ne doit pas donner l’impression que les Continuités disparaissent puis réapparaissent comme de nouvelles réalités.

---

## 57. Retour et continuité cognitive

Le parcours :

```text
En cours
→ Continuité
→ profondeur propriétaire
→ retour
```

doit préserver raisonnablement :

- position de scroll ;
- groupe ;
- filtre éventuel ;
- tri éventuel ;
- sélection ;
- contexte de lecture.

Une surface dédiée à la continuité ne doit pas détruire sa propre continuité cognitive.

---

## 58. Deep links

Une destination propriétaire importante peut rester adressable directement lorsque la sécurité le permet.

Un deep link doit :

1. restaurer l’authentification si nécessaire ;
2. vérifier la visibilité ;
3. vérifier l’autorité ;
4. ouvrir la profondeur correcte ;
5. fournir une alternative compréhensible si la destination n’est plus disponible.

La Continuité peut rester une projection intermédiaire sans devenir propriétaire de la route finale.

---

## 59. État vide

Un état réellement vide signifie :

> aucune Continuité personnelle actuellement admise.

La microcopy exacte n’est pas figée ici.

Une formulation possible est :

> Rien en cours pour le moment.

L’interface ne doit pas remplir ce vide par des suggestions artificielles.

Discover reste la surface des possibilités.

---

## 60. Continuités calmes

Une personne peut avoir plusieurs Continuités et aucune inquiétude particulière.

Exemple :

```text
Visa Canada
→ en examen, rien à faire

Voyage Nairobi
→ tout est prêt pour samedi

Livre
→ éditeur en lecture
```

Cette situation constitue une réussite produit.

Le concept de **calme avec Continuités** est distinct de l’état vide.

La microcopy finale reste une décision de design ultérieure.

---

## 61. Frontière avec Now

La différence fondamentale est :

```text
En cours
→ Où en est ce que j’ai déjà engagé ?

Now
→ Qu’est-ce qui mérite mon attention maintenant ?
```

Une Continuité peut produire zéro, une ou plusieurs Situations Now au fil du temps.

Conceptuellement :

```text
1 Continuité En cours
→ 0..n Situations Now dans le temps
```

Ce n’est pas une cardinalité de base de données.

C’est une relation UX.

---

## 62. Une Continuité peut exister sans Now

Exemple :

> Votre demande de visa est en examen.  
> Vous avez fait votre part.

Elle reste En cours.

Elle peut ne produire aucune Situation Now.

Ainsi :

```text
absence de Now
≠ absence de Continuité
```

---

## 63. Une Situation Now n’est pas nécessairement En cours

Une conséquence actuelle peut mériter Now sans représenter une poursuite durable devant apparaître dans En cours.

Donc :

```text
Now
≠ sous-ensemble strict de En cours
```

et :

```text
En cours
≠ Now moins urgent
```

---

## 64. Frontière avec Discover

Discover contient les possibilités.

Une possibilité simplement intéressante, recommandée ou sauvegardée ne devient pas En cours automatiquement.

Il faut franchir une frontière effective de poursuite.

Le seuil exact :

```text
intérêt
→ intention
→ engagement
→ orchestration active
```

reste partiellement ouvert et doit être dérivé des propriétaires réels plutôt que remplacé par un modèle générique.

---

## 65. Frontière avec Moi

Moi conserve le capital durable déjà en place.

Exemple :

```text
Moi
→ Passeport valide jusqu’en 2031
```

La même vérité peut contribuer à une Continuité :

```text
En cours / Voyage Nairobi
→ Passeport déjà prêt
```

Même fait.

Deux projections.

Pas de duplication métier.

Un Access durable sans poursuite active peut appartenir à Moi plutôt qu’à En cours.

---

## 66. Frontière avec Historique

Une Continuité terminée sort d’En cours.

En cours ne doit pas accumuler :

```text
Voyage 2024
Visa 2025
Commande terminée
Formation passée
```

simplement parce que ces réalités existent toujours en base.

Le passé appartient aux propriétaires et à l’Historique lorsqu’il reste utile à retrouver.

---

## 67. Jour J

Jour J est l’expérience d’accomplissement lorsque ce qui était préparé devient une réalité à vivre maintenant.

Une Continuité peut conduire vers :

```text
Occurrence suffisamment proche
→ Jour J
→ Live éventuellement
```

Jour J n’est pas un état générique d’En cours.

Il est une profondeur spécialisée.

---

## 68. Pendant Jour J

La Continuité peut continuer d’exister pendant Jour J.

Jour J concentre :

- timing ;
- accès ;
- orientation ;
- checkpoint ;
- placement ;
- Live Queue ;
- opérations réellement en cours.

Après la réalisation :

```text
suite pertinente ?
├── oui → Continuité continue
└── non → sortie En cours
```

---

## 69. `Métier` dans un Space

`Métier` partage avec En cours la grammaire profonde de continuité.

Mais son acteur est un Space.

Et son vocabulaire visible dépend de l’archétype.

Exemples :

```text
transport_operator
→ Départs / Transport

education
→ Programmes

commerce
→ Commandes / Commerce

service_provider
→ Prestations
```

Il ne faut pas exposer un objet générique nommé « Continuité » simplement pour uniformiser l’interface.

Principe :

> **Même grammaire profonde de continuité, vocabulaire visible du contexte.**

---

## 70. En cours et Métier ne fusionnent pas les contextes d’autorité

Le même humain peut :

```text
agir comme Profile
et
agir pour un Space
```

Une future composition transversale ne transfère jamais :

- Permission ;
- Mandate ;
- Access ;
- Payment ;
- données privées ;
- responsabilité ;

d’un contexte vers l’autre.

Le contexte acteur reste explicite.

---

## 71. Runtime actuel : ce qui existe déjà

Le runtime actuel possède déjà une projection :

```text
personal.ongoing
```

alimentée notamment par :

- Journey ;
- Access ;
- Dossier ;
- Project ;
- Waitlist ;
- Transfer ;
- certains Payment ;
- Funding dans certains chemins Web.

Il expose déjà plusieurs notions utiles :

```text
ready
actor_interventions
continuation
blocker
next
timing
place
capabilities
links
```

Cette ossature doit être considérée avant toute nouvelle abstraction.

---

## 72. Runtime actuel : écarts avec le contrat mature

Le contrat mature met en évidence plusieurs écarts potentiels à traiter lors d’une future implémentation.

### 72.1. Composition par familles propriétaires

Le read model actuel parcourt encore plusieurs familles propriétaires.

La cible UX raisonne en Continuités humaines.

Cela ne justifie pas une nouvelle table.

Cela suggère de renforcer la composition et la déduplication lorsque les relations canoniques le permettent.

### 72.2. Budget de projection

La borne actuelle de la projection est un choix technique.

Elle ne doit pas devenir une limite conceptuelle du nombre de Continuités.

### 72.3. Access actif

Un Access actif n’appartient pas automatiquement à En cours.

Un droit durable sans poursuite active peut être mieux représenté dans Moi.

### 72.4. DRAFT

Un Dossier ou Project `DRAFT` n’est ni automatiquement engagé, ni automatiquement exclu.

Il faut vérifier s’il représente encore une poursuite vivante.

Ces points sont des écarts potentiels entre runtime actuel et contrat cible, pas des déclarations de bug en eux-mêmes.

---

## 73. Schéma conceptuel consolidé

```text
CONTINUITÉ EN COURS
│
├── PROJECTION
│   ├── CONTINUITY_IDENTITY
│   └── CONTINUITY_BASIS
│       └── faits + relations canoniques minimales
│
├── ACTOR
│   └── PROFILE_CONTEXT
│
├── HUMAN
│   ├── HUMAN_CONTEXT
│   └── SYNTHESIS
│       └── "où j'en suis"
│
├── CONTINUATION
│   ├── SETTLED[]
│   ├── MY_SIDE[]
│   ├── ELSEWHERE[]
│   ├── MAKOLO[]
│   ├── SYSTEM_OR_TIME[]
│   ├── NEXT[]
│   ├── BLOCKERS[]
│   │   ├── source
│   │   ├── blocked_transition
│   │   ├── horizon?
│   │   └── alternatives?
│   ├── HORIZON?
│   ├── OUTCOME?
│   └── CONTINUITY_EXIT_CONDITION
│
├── KNOWLEDGE_CONTEXT
│   ├── PROVENANCE?
│   ├── FRESHNESS
│   ├── KNOWLEDGE_STATE
│   └── CONFIDENCE? si défendable
│
├── RELATION_PROJECTIONS
│   └── dérivées de relations canoniques
│
├── TEMPORAL_FACTS
│   └── alimentent Calendrier
│
├── PRESENTATION
│   ├── texte
│   ├── row
│   ├── card
│   ├── média
│   ├── timeline si réelle
│   ├── map si utile
│   └── composition
│
└── DEPTH
    ├── composition de Continuité si utile
    └── domaine propriétaire
```

Ce schéma n’est pas un schéma de base de données.

---

## 74. Anti-features

En cours ne doit pas devenir :

- une todo list ;
- un dashboard personnel ;
- un kanban générique ;
- une liste de toutes les tables actives ;
- un deuxième Now ;
- un Historique déguisé ;
- un second Readiness ;
- un score de progression universel ;
- une barre de progression arbitraire ;
- un workflow universel ;
- une liste permanente « bloqué / prêt / attente » imposée à toutes les réalités ;
- un flux infini artificiel ;
- un feed média ;
- une collection uniforme de Cards ;
- un système où tout Access actif devient une Continuité ;
- un système où tout Draft devient une Continuité ;
- un système où tout ce qu’un Profile fait pour un Space entre dans son En cours personnel ;
- un graphe parallèle réinventant les relations propriétaires ;
- une source d’autorité locale ;
- une projection qui transforme une ancienne donnée offline en état Live ;
- un moyen de contourner Permission, Mandate, Access ou confidentialité.

---

## 75. Invariants consolidés

1. **En cours = continuité personnelle de réalités effectivement engagées.**
2. **Une réalité engagée a franchi une frontière effective entre possibilité et poursuite.**
3. **Il doit rester une suite pertinente.**
4. **Une Continuité En cours est une projection UX, pas une vérité métier.**
5. **Continuité En cours ≠ Journey ≠ Dossier ≠ Project ≠ Access ≠ Payment.**
6. **Continuité En cours ≠ Card.**
7. **Une Continuité se justifie par une `CONTINUITY_BASIS`, pas nécessairement un propriétaire unique.**
8. **`CONTINUITY_IDENTITY` est une identité de projection, pas une nouvelle identité métier.**
9. **Pas de lifecycle universel En cours.**
10. **Pas de `MOTION` canonique.**
11. **Pas de `TURN` unique obligatoire.**
12. **Pas de `NEXT` unique obligatoire en profondeur.**
13. **Attente ≠ blocage ≠ risque ≠ inconnue.**
14. **Un blocker est relatif à la transition qu’il empêche.**
15. **Readiness nourrit En cours ; En cours ne recrée pas Readiness.**
16. **Ce qui est réglé n’est affiché que si cela réduit utilement l’incertitude.**
17. **Ce qui reste de mon côté ne signifie pas automatiquement “à faire maintenant”.**
18. **Ce qui continue ailleurs peut être la bonne réponse.**
19. **Makolo peut préparer et surveiller sans inventer de succès ni d’autorité.**
20. **Owner terminé ≠ résultat humain atteint ≠ Continuité terminée.**
21. **Toute Continuité possède conceptuellement une condition de sortie.**
22. **Une Continuité peut traverser plusieurs propriétaires.**
23. **Relation entre Continuités ≠ fusion.**
24. **En cours ne possède pas un nouveau graphe de relations.**
25. **Les relations peuvent être n-aires.**
26. **Même contexte = regroupement de présentation, pas causalité.**
27. **Une relation qui crée une conséquence actuelle peut produire une Situation Now.**
28. **Le Calendrier projette des faits temporels significatifs liés aux Continuités.**
29. **Timestamp backend ≠ événement humain.**
30. **Toutes les Continuités légitimes doivent rester accessibles ; pas de Top N conceptuel.**
31. **Une borne technique de projection n’est pas une limite UX du réel.**
32. **L’ordre privilégie stabilité et compréhension plutôt qu’un score opaque.**
33. **En cours personnel n’absorbe pas automatiquement le travail fait au nom d’un Space.**
34. **Métier partage la grammaire de continuité mais parle le langage de l’archétype.**
35. **No Orphan Content / Media reste applicable.**
36. **Média ≠ Proof automatique.**
37. **Pas de pourcentage de progression sans mesure métier défendable.**
38. **La racine montre l’essentiel ; les propriétaires portent la profondeur.**
39. **Toute mutation appartient au propriétaire canonique.**
40. **Le feedback annonce uniquement le niveau réellement atteint.**
41. **Offline peut conserver la compréhension, jamais inventer l’actualité.**
42. **Refresh et retour doivent préserver la continuité cognitive.**
43. **Une page En cours calme est une réussite produit.**
44. **En cours ≠ Now moins urgent.**
45. **En cours ≠ Moi.**
46. **En cours ≠ Historique.**
47. **Jour J / Live est une profondeur d’accomplissement, pas un état universel d’En cours.**
48. **La continuité UX n’est ni CorpsMolongo, ni constituant massique, ni unité de masse.**

---

## 76. Exemples consolidés

### 76.1. Visa en attente normale

```text
Visa Canada

Demande déposée.
Frais réglés.
Le consulat examine votre dossier.

De votre côté
Rien à faire pour l’instant.

Ensuite
Biométrie le 18 octobre.
```

Ce cas est En cours même s’il ne mérite aucune Situation Now.

### 76.2. Visa avec action future de mon côté

```text
Visa Canada

Votre demande est enregistrée.

De votre côté
Transmettre le certificat avant le 15 novembre.

En cours ailleurs
Le consulat vérifie déjà les autres pièces.
```

Le certificat appartient à `MY_SIDE`.

Cela ne signifie pas automatiquement qu’il doit être affiché dans Now aujourd’hui.

### 76.3. Waitlist → Access

État initial :

```text
Concert samedi

Vous êtes en liste d’attente.
Rien à faire pour l’instant.
```

Puis :

```text
Concert samedi

Une place est disponible.
Vous pouvez accepter avant 18 h.
```

Après acceptation :

```text
Concert samedi

Votre accès est disponible.
Tout est prêt pour samedi.
```

La Continuité humaine peut rester reconnaissable alors que le propriétaire dominant change.

### 76.4. Paiement intermédiaire

```text
Commande de l’ordinateur

Paiement confirmé.
Le vendeur prépare la commande.

Ensuite
Remise prévue vendredi.
```

Le Payment est terminé.

La Continuité ne l’est pas.

### 76.5. Conflit entre deux Continuités

```text
En cours

Rendez-vous médical
Vendredi · 10 h

Entretien professionnel
Vendredi · 10 h
```

La relation temporelle peut produire dans Now :

```text
Deux engagements se chevauchent vendredi à 10 h.
```

La Situation Now disparaît après arbitrage.

Les deux Continuités restent si elles possèdent encore une suite.

### 76.6. Capital de Moi utilisé par En cours

```text
Moi
→ Passeport valide jusqu’en 2031
```

Dans :

```text
En cours
Voyage Nairobi
→ Passeport déjà prêt ✓
```

Même vérité propriétaire.

Deux projections utiles.

### 76.7. Space distinct du personnel

```text
SOMAF
Affecter un véhicule au départ de 14 h
→ Métier / Now du Space
```

et :

```text
Gilbert
Billet personnel pour le départ de 14 h
→ En cours personnel
```

Le Profile est la même personne.

Le contexte acteur est différent.

---

## 77. Ce qui reste volontairement ouvert

Avant une implémentation mature, restent ouverts :

1. la méthode exacte de calcul de `CONTINUITY_IDENTITY` ;
2. la méthode exacte de dérivation de `CONTINUITY_BASIS` lorsqu’une poursuite traverse plusieurs propriétaires ;
3. les seuils qualitatifs exacts entre intérêt, intention, engagement et poursuite active ;
4. le traitement des Draft réellement poursuivis versus brouillons simplement conservés ;
5. l’ordre exact lorsqu’un Profile possède beaucoup de Continuités ;
6. la pagination ou stratégie de chargement technique ;
7. le niveau de persistance éventuel de la projection ;
8. la structure API définitive ;
9. les représentations Web et mobile finales ;
10. la microcopy exacte des états vide et calme ;
11. les règles exactes de regroupement contextuel ;
12. la manière de représenter les relations n-aires ;
13. le niveau de matérialisation locale nécessaire pour la continuité inter-propriétaires ;
14. la stratégie exacte de synchronisation quand la base de continuité change ;
15. les seuils d’entrée automatique dans Jour J.

Aucun de ces points ne justifie, à lui seul, un nouveau domaine persistant.

---

## 78. Doctrine d’implémentation future

Avant d’ajouter un nouveau modèle pour En cours :

1. vérifier les propriétaires canoniques ;
2. vérifier les relations existantes ;
3. vérifier `personal.ongoing` ;
4. vérifier les selectors/read models ;
5. vérifier Readiness ;
6. vérifier les Domain Events ;
7. vérifier Presentation ;
8. vérifier les projections mobiles locales ;
9. vérifier le Sync & Continuity Kernel ;
10. vérifier les besoins réels de stabilité d’identité ;
11. préférer la composition et les read models aux copies de vérité.

Par défaut :

> **Continuité En cours doit être pensée comme projection/read model avant d’être pensée comme modèle métier.**

---

## 79. Critères de sortie d’une future implémentation mature

Une implémentation mature d’En cours devrait démontrer au minimum :

- admission fondée sur une poursuite réelle ;
- séparation personnelle / Space ;
- aucune duplication de Readiness ;
- aucune duplication de Payment, Access, Requirement ou Journey state ;
- composition de plusieurs propriétaires lorsqu’une relation canonique le justifie ;
- continuité d’identité stable pour les cas nécessaires ;
- Waitlist → Access → Occurrence correctement représentable ;
- Access durable non engagé pouvant rester dans Moi ;
- Draft non vivant ne restant pas indéfiniment En cours ;
- `SETTLED`, `MY_SIDE`, `ELSEWHERE` et `NEXT` dérivés honnêtement ;
- plusieurs mouvements parallèles supportés ;
- plusieurs `NEXT` possibles en profondeur ;
- blocker rattaché à ce qu’il bloque ;
- attente, risque, inconnue et blocage distingués ;
- résultat intermédiaire distinct de fin de Continuité ;
- sortie naturelle vers Historique / Moi / propriétaire ;
- relations entre plusieurs Continuités ;
- conflit pouvant produire une Situation Now sans créer une Continuité artificielle ;
- lecture temporelle des faits humains ;
- aucune dépendance à un nombre UX maximum de Continuités ;
- ordre stable ;
- retour avec restauration du contexte ;
- refresh sans flash destructeur de continuité ;
- représentation offline honnête ;
- revalidation autoritative des actions sensibles ;
- état vide ;
- état calme avec Continuités existantes ;
- handoff vers Jour J lorsque réel ;
- aucune régression d’autorité ou d’IDOR.

---

## 80. Références de cadrage

Ce contrat consolide principalement les principes issus de :

- `docs/architecture/ux-now.md`
- `docs/architecture/m8-ux-shell-contract.md`
- `docs/architecture/mobile-a2-surface-contracts.md`
- `docs/architecture/mobile-visual-charter-v1.1.md`
- `docs/architecture/mobile-sync-continuity-kernel.md`
- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Cadre_consolide_de_PageRank_aux_trajectoires_accessibles_2026-09-17.docx`
- `Makolo_Obtention_Verticale_Cadre_Conception_v2.md`
- les invariants canoniques Makolo concernant Profile, Space, Assignment, Mandate, Permission, Activity, Occurrence, Journey, Requirement, Readiness, Access, Capacity, Dossier, Project, Payment, Presentation, confidentialité et local-first.

Le code, les migrations, les tests et les contrats du `main` courant restent la vérité runtime lors de toute future implémentation.

---

## 81. Formulation finale

> **En cours est la surface personnelle Makolo qui rend intelligible la continuité de ce que la personne a réellement engagé. Son unité UX, la Continuité En cours, n’est ni une tâche, ni un Journey, ni un nouveau modèle métier : c’est la plus petite projection humaine cohérente permettant de comprendre où en est une poursuite, ce qui est déjà réglé, ce qui reste du côté de la personne, ce qui continue ailleurs, ce que Makolo prépare ou surveille et ce qui vient ensuite. Une Continuité peut traverser plusieurs propriétaires canoniques sans copier leurs vérités ; elle peut rester calme pendant longtemps, produire ponctuellement des Situations Now, entrer en Jour J lorsqu’une Occurrence devient réelle, puis sortir lorsque plus aucune suite pertinente ne subsiste. En cours n’invente ni urgence, ni progression, ni blocage, ni autorité. Il conserve la continuité nécessaire pour que la personne puisse avancer sans avoir à reconstruire elle-même le système.**


## Gel conceptuel 2026-10-05 — `OngoingMeResponse`

Cette section transforme les principes précédents en contrat conceptuel serveur/client stabilisé sans ajouter de domaine métier.

### A. Unité UX

Une Continuité est une **poursuite humaine unitaire**. La pluralité des propriétaires ne transforme pas son `HUMAN_CONTEXT` en tableau hétérogène.

```text
PROFILE_CONTEXT
→ exactement 1 Profile

HUMAN_CONTEXT
→ exactement 1 réalité humaine compréhensible

SYNTHESIS
→ exactement 1 synthèse « où j'en suis »
```

La pluralité vit principalement dans `CONTINUITY_BASIS` et les dimensions de continuation.

### B. Continuity Identity

```text
CONTINUITY_IDENTITY
→ exactement 1 identité de projection stable
```

Elle permet à une poursuite de traverser plusieurs propriétaires, par exemple :

```text
Waitlist
→ place offerte
→ Access
→ Occurrence
```

sans devenir quatre histoires sans rapport.

Elle n'est pas une identité métier. Le client ne la reconstruit jamais par similarité de texte, date, titre ou source.

### C. Continuity Basis

```text
CONTINUITY_BASIS
├── canonical objects / facts[]
└── canonical relations[]
```

La base est conceptuellement requise pour justifier l'admission et la continuité, mais elle n'est pas nécessairement imprimée ni exposée sous une forme brute à l'interface.

Une base peut être un seul Journey, ou une composition de vérités comme Journey + Payment + Requirements + rendez-vous + documents. Cette composition ne signifie pas que le `HUMAN_CONTEXT` ou la synthèse deviennent multiples.

### D. Dimensions de continuation et cardinalités

```text
SETTLED[]         0..n
MY_SIDE[]         0..n
ELSEWHERE[]       0..n
MAKOLO[]          0..n
SYSTEM_OR_TIME[]  0..n
NEXT[]            0..n
BLOCKERS[]        0..n
HORIZON           0..1
OUTCOME           0..1
RELATIONS         0..n
TEMPORAL_FACTS    0..n
ACTIONS           0..n
MEDIA_BINDINGS    0..n
KNOWLEDGE_CONTEXT 1 structure sémantique lorsque nécessaire
```

Il n'existe pas de `TURN` unique obligatoire ni de `NEXT` unique obligatoire en profondeur.

### E. Settled

`SETTLED[]` ne liste que les faits qui réduisent réellement l'incertitude ou expliquent la suite : frais confirmés, place sécurisée, Access disponible, document reçu, condition satisfaite, réservation confirmée, etc.

Les éléments peuvent être représentés comme `FACT` ou `OBJECT` owner-backed selon leur nature.

### F. My Side

`MY_SIDE[]` répond à : « qu'est-ce qui reste réellement de mon côté ? ».

```text
MY_SIDE ≠ action à faire maintenant
```

Une action peut rester de mon côté sans mériter une Situation Now. Lorsqu'elle devient digne d'attention actuelle, Now peut la projeter séparément.

### G. Elsewhere

`ELSEWHERE[]` décrit les mouvements légitimes qui continuent hors de l'intervention actuelle de la personne : consulat, fournisseur, transporteur, université, confirmation distante, autre acteur ou processus.

Chaque item peut conceptuellement porter :

```text
actor / holder
process / transition
target?
horizon?
knowledge?
```

### H. Makolo

`MAKOLO[]` décrit uniquement ce que Makolo fait réellement : retrouver, préparer, surveiller, revalider, regrouper.

```text
préparé ≠ envoyé
envoyé ≠ confirmé
confirmé ≠ résultat humain accompli
```

### I. System or Time

`SYSTEM_OR_TIME[]` couvre les suites qui dépendent d'une fenêtre, du temps, d'un traitement automatisé autoritatif ou d'un événement futur établi, sans fabriquer un faux acteur humain.

### J. Next

`NEXT[]` peut contenir plusieurs prochaines réalités significatives : réponse, rendez-vous, ouverture de fenêtre, début d'Occurrence, etc.

La racine peut n'en mettre qu'une en avant lorsqu'un repère domine réellement, mais la profondeur ne transforme jamais `NEXT[]` en workflow exhaustif artificiel.

### K. Blockers

```text
BLOCKER
├── SOURCE
├── BLOCKED_TRANSITION
├── HORIZON?
└── ALTERNATIVES[]
```

```text
WAITING ≠ BLOCKED ≠ RISK ≠ UNKNOWN
```

Il n'existe pas de statut universel `continuity = blocked` qui perde ce qui est réellement empêché.

### L. Pas de state ou motion universel

Le contrat mature ne réduit pas une Continuité à :

```text
waiting | blocked | ready | realizing | done
```

Une même Continuité peut simultanément contenir plusieurs vérités de nature différente. La synthèse est une projection sémantique, pas un lifecycle universel.

### M. Outcome et sortie

```text
OWNER_COMPLETION
≠ OUTCOME
≠ CONTINUITY_EXIT
```

`OUTCOME` décrit le résultat humain réellement obtenu. `CONTINUITY_EXIT_CONDITION` répond à ce qui doit être vrai pour qu'il ne reste plus de suite pertinente dans En cours. Cette condition peut rester interne au serveur.

### N. Knowledge Context

Même contrat que Now :

```text
KNOWLEDGE_CONTEXT
├── PROVENANCE[]
├── FRESHNESS
├── KNOWLEDGE_STATE
│   ├── KNOWN
│   ├── UNKNOWN
│   ├── CONTRADICTORY
│   ├── STALE
│   └── UNAVAILABLE
└── CONFIDENCE? si défendable
```

La fraîcheur du snapshot local reste distincte de la fraîcheur métier.

### O. Relations et regroupements

Les relations entre Continuités sont des projections de relations propriétaires/orchestrées : dependency, facilitation, shared resource, synchronization, conflict, mutualization, alternative, cascade, feedback, etc.

```text
RELATION ≠ FUSION
```

Les regroupements comme « Voyage Nairobi » sont de la `PRESENTATION_GROUP`, pas des causalités ajoutées.

### P. Temporal Facts / Calendrier

```text
TEMPORAL_FACT
→ événement humain significatif
→ 1..n Continuités possibles
```

`created_at`, `updated_at`, `synced_at`, `last_seen_at` ne deviennent pas automatiquement des événements calendrier.

### Q. Actions et profondeur

Toute action visible depuis En cours appartient au propriétaire canonique :

```text
En cours
→ intention / action
→ owner domain
→ vérité canonique
→ reprojection
```

Progressive disclosure :

```text
ROOT SUMMARY
→ CONTINUITY COMPOSITION si utile
→ OWNER DEPTH
```

La Continuité n'est jamais propriétaire de la mutation finale.

### R. Média

Même doctrine que Now :

```text
MEDIA_BINDING
├── resource
├── target
└── purpose
    ├── RECOGNIZE
    ├── UNDERSTAND
    ├── ESTABLISH
    ├── PREPARE
    └── ACT
```

`Média ≠ Proof automatique` et `aperçu document ≠ Requirement satisfait`.

### S. Local-first, refresh et retour

Le client peut conserver projections En cours, owners déjà connus, ressources autorisées et snapshots utiles. Il ne devient jamais autorité sur Permission, Mandate, Payment, Access partagé, Capacity globale, concurrence ou état mondial courant.

Offline : conserver la compréhension et afficher honnêtement la dernière connaissance.

Refresh : préférer le contenu courant + indicateur discret à une disparition/reconstruction artificielle.

Retour : préserver scroll, groupe, filtre, sélection et contexte de lecture.

### T. Empty et calm

```text
EMPTY
→ aucune Continuité personnelle admise

CALM WITH CONTINUITIES
→ des Continuités existent mais rien n'exige une inquiétude ou intervention actuelle
```

Le calme avec Continuités est une réussite produit.

### U. Contrat conceptuel serveur final

```text
ONGOING ME RESPONSE
│
├── PROFILE_CONTEXT
└── CONTINUITIES[]
    ├── CONTINUITY_IDENTITY
    ├── CONTINUITY_BASIS
    ├── HUMAN_CONTEXT
    ├── SYNTHESIS
    ├── SETTLED[]
    ├── MY_SIDE[]
    ├── ELSEWHERE[]
    ├── MAKOLO[]
    ├── SYSTEM_OR_TIME[]
    ├── NEXT[]
    ├── BLOCKERS[]
    │   ├── source
    │   ├── blocked_transition
    │   ├── horizon?
    │   └── alternatives[]
    ├── HORIZON?
    ├── OUTCOME?
    ├── KNOWLEDGE_CONTEXT
    ├── RELATION_PROJECTIONS[]
    ├── TEMPORAL_FACTS[]
    ├── ACTIONS[]
    ├── MEDIA_BINDINGS[]
    └── DEPTH / OWNER HANDOFF
```

`CONTINUITY_EXIT_CONDITION` reste conceptuellement obligatoire et peut rester interne au moteur/projection.

### V. Ce qui reste volontairement non figé

- wire JSON définitif ;
- algorithme/persistance exacte de `CONTINUITY_IDENTITY` ;
- stratégie finale de regroupement ;
- ordre global exact ;
- représentation n-aire détaillée ;
- matérialisation locale nécessaire pour continuités multi-owner ;
- stratégie de synchronisation lorsque la base change ;
- seuil exact de handoff Jour J.


---

# III. Découvrir Me — contrat détaillé de référence

## Makolo — UX Découvrir
### Contrat consolidé du champ personnel des possibilités

**Statut :** cadre UX conceptuel consolidé de travail  
**Portée :** expérience personnelle Web et mobile ; grammaire réutilisable par `Découvrir` dans un Space  
**Nom UX retenu :** `Découvrir`  
**Question humaine personnelle :** « Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ? »  
**Question humaine Space :** « Qu’est-ce qui pourrait nous aider à avancer ? »  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »  
**Base runtime vérifiée avant consolidation :** `main@97b2017b5df0a94e3276858c28e51e916b185c0b`

---

## 1. Objet du document

Ce document fixe le contrat conceptuel de **Découvrir**, la surface Makolo dédiée à l’exploration du champ des possibilités.

Il consolide notamment :

- la définition d’une possibilité ;
- l’admission dans le champ Discover ;
- l’unité UX appelée ici **Possibilité Discover** ;
- l’identité de projection et la provenance ;
- l’`Exploration Context` ;
- le `Possibility Field` ;
- la relation avec la pertinence calculée en amont ;
- les faits connus, évaluations favorables/limitantes et inconnues ;
- les variantes et relations utiles ;
- la recherche, les filtres et la carte ;
- les regroupements de présentation ;
- la comparaison ;
- le Bookmark et la Veille ;
- le passage de l’exploration vers un engagement réel ;
- les frontières avec Now, En cours, Moi, Space, Search et les propriétaires canoniques ;
- les médias ;
- la fraîcheur, le local-first et l’offline ;
- les états de fin du champ ;
- les anti-features ;
- les écarts connus du runtime actuel ;
- les points volontairement laissés ouverts avant l’implémentation Mature finale.

Ce document est un **contrat UX et de projection**.

Il ne fixe pas :

- un modèle de base de données `Possibility` ;
- une table `DiscoverItem` ;
- un lifecycle universel de découverte ;
- une table `Intent` ;
- un algorithme de pertinence ;
- un score de matching ;
- un ranking global ;
- un calcul Pareto ;
- une métrique de distance Molongo ;
- une formule de recommandation ;
- un nombre maximum de possibilités ;
- une maquette pixel-perfect ;
- un composant visuel unique ;
- une structure API définitive ;
- un moteur Web Search ;
- une nouvelle vérité métier de Bookmark ou de Watch ;
- un nouveau graphe transversal propriétaire.

Le runtime courant, les domaines propriétaires, Molongo/intelligence, leurs permissions, admissions et tests restent prioritaires.

---

## 2. Place de Découvrir dans Makolo

Les surfaces personnelles répondent à des questions différentes.

```text
Découvrir
→ Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?

Now
→ Qu’est-ce qui mérite mon attention maintenant ?

En cours
→ Parmi ce que j’ai réellement engagé, où en suis-je et qu’est-ce qui continue ?

Moi
→ Qu’est-ce qui est déjà en place autour de moi pour faciliter la suite ?

Jour J / Live
→ Qu’est-ce que je suis effectivement en train de vivre ou d’accomplir maintenant ?

Historique
→ Qu’est-ce qui est terminé et reste utile à retrouver ?
```

Découvrir est **l’espace des possibles**, pas l’espace des nouveautés.

Il aide à passer de :

```text
je ne sais pas encore
j’ai une envie vague
j’ai une contrainte
```

vers :

```text
ça, j’ai envie de l’explorer
ça, je veux le garder
ça, je veux le surveiller
ça, je veux réellement l’engager
```

sans transformer automatiquement l’exploration en obligation.

---

## 3. Définition de Découvrir

> **Découvrir est la surface UX qui rend explorable le champ des possibilités que Makolo connaît et que l’amont pertinent a retenues pour l’Actor Context et l’Exploration Context courants.**

Découvrir ne calcule pas lui-même la pertinence.

Il reçoit un champ de possibilités et permet de :

- reconnaître ;
- explorer ;
- rechercher ;
- filtrer ;
- cartographier ;
- comparer ;
- approfondir ;
- garder ;
- surveiller lorsque le contrat le permet ;
- engager via le propriétaire canonique.

---

## 4. Ce que Découvrir n’est pas

Découvrir n’est pas :

- un feed ;
- une page de nouveautés ;
- un réseau social ;
- une page Trending ;
- une page Popular ;
- un catalogue brut des modèles backend ;
- un moteur de rétention ;
- un flux infini artificiel ;
- un centre de notifications ;
- un centre de conversations ;
- un nouveau domaine `Possibility` ;
- un propriétaire de la pertinence ;
- un propriétaire de l’engagement ;
- un moteur de ranking UX ;
- un score de vie ;
- un système où voir signifie aimer ;
- un système où Bookmark signifie vouloir ;
- un système où Watch signifie engager ;
- un système où toute possibilité doit avoir un CTA principal.

---

## 5. Pertinence : frontière avec Molongo / intelligence

Le contrat UX considère que la pertinence est produite en amont.

Conceptuellement :

```text
réalités / connaissance / domaines
            ↓
      Molongo / intelligence
            ↓
champ de possibilités pertinent
+ ordre éventuel
+ relations éventuelles
+ raisons explicables éventuelles
            ↓
        Discover UX
```

Découvrir n’ajoute pas ensuite dans Flutter, JavaScript ou un template :

```text
+10 si proche
+5 si Interest
-4 si cher
```

L’UX représente le résultat fourni.

Elle ne possède pas la formule.

---

## 6. Pas de score global UX

Le contrat n’introduit pas :

```text
relevance_score
match_percentage
global_rank
attention_score
life_score
```

comme vérité de Presentation.

Si l’amont fournit un ordre ou une relation de pertinence, Découvrir peut la respecter.

Il ne doit pas transformer cette information en jugement global sur ce qui « compte le plus » dans la vie de la personne.

---

## 7. Possibilité

### 7.1. Définition

> **Une Possibilité Discover est la plus petite projection humainement cohérente d’une option réelle que l’acteur peut considérer comme distincte en vue de vivre, faire ou obtenir quelque chose.**

Exemples :

```text
participer à un concert
suivre une formation
rejoindre Nairobi
obtenir un financement
louer une ressource
recevoir un service
```

La Possibilité est une unité UX.

Elle n’est pas un nouveau domaine.

---

## 8. Possibilité ≠ propriétaire canonique

Une Possibilité peut être soutenue par :

- `Activity` ;
- `Occurrence` ;
- `Opportunity` ;
- `Funding` ;
- `Service` ;
- `Obtention` ;
- lieu ;
- ressource ;
- relation ;
- autre vérité canonique.

Donc :

```text
Possibilité Discover
≠ Activity
≠ Occurrence
≠ Opportunity
≠ Funding
≠ Service
≠ Card
```

Plusieurs faits peuvent composer une seule Possibilité.

Un seul objet propriétaire peut aussi suffire.

---

## 9. `POSSIBILITY_BASIS`

`POSSIBILITY_BASIS` reste un principe architectural :

> **Toute Possibilité présentée doit pouvoir être justifiée par un ensemble minimal de faits et relations canoniques.**

Cela peut correspondre à :

```text
Opportunity
```

ou :

```text
Activity
+ Occurrence
+ place
+ disponibilité
```

ou une autre composition légitime.

Ce document ne demande pas qu’un champ API `possibility_basis` soit ajouté.

Les identités et provenances actuelles peuvent suffire.

---

## 10. `POSSIBILITY_IDENTITY`

Une Possibilité a besoin d’une identité de projection suffisamment stable pour :

- déduplication ;
- détail ;
- Bookmark ;
- retour ;
- cache ;
- comparaison ;
- placements multiples.

Mais :

```text
POSSIBILITY_IDENTITY
≠ nouvelle identité métier
```

Les identités propriétaires ou candidate keys existantes doivent être réutilisées tant qu’elles suffisent.

---

## 11. Même titre ≠ même Possibilité

Deux résultats portant le même titre ne sont pas automatiquement la même réalité.

La fusion d’identité ne doit jamais reposer uniquement sur :

- titre similaire ;
- résumé similaire ;
- date proche ;
- image identique ;
- proximité textuelle.

La résolution appartient aux contrats canoniques / intelligence adaptés.

---

## 12. Plusieurs sources ≠ plusieurs Possibilités

Une même possibilité peut être soutenue par :

- une source officielle ;
- une page du porteur ;
- un PDF ;
- une observation ;
- une connaissance résolue.

Ces sources enrichissent la provenance.

Elles ne créent pas automatiquement plusieurs unités UX.

---

## 13. Résultat possible

Une Possibilité doit permettre de comprendre :

> **Qu’est-ce que cela pourrait permettre de vivre, faire ou obtenir ?**

Cette exigence peut être satisfaite par :

- le domaine ;
- le titre ;
- la grammaire verticale ;
- le résumé ;
- une présentation explicite.

Il n’est pas nécessaire de créer un champ persistant `possible_outcome`.

---

## 14. `EXPLORATION_CONTEXT`

> **L’Exploration Context est le contexte temporaire qui exprime ce que l’acteur cherche actuellement à explorer.**

Il peut contenir :

```text
query?
intention explicite?
contraintes?
filtres?
vue courante?
contexte spatial?
```

Exemples :

```text
aller à Nairobi samedi
formation pour apprendre Python
quelque chose à faire ce soir
financement pour mon projet
```

Il ne devient pas un modèle persistant générique par défaut.

---

## 15. Search ≠ Exploration Context complet

Search est une manière d’exprimer ou de préciser le contexte.

Une exploration peut aussi commencer depuis :

- le champ général fourni ;
- un Interest ;
- un OpenTo ;
- une Veille ;
- une Continuité existante ;
- un lieu ;
- une autre intention explicite.

Donc :

```text
SEARCH QUERY
≠ EXPLORATION_CONTEXT complet
```

---

## 16. `POSSIBILITY_FIELD`

> **Le Possibility Field est l’ensemble actuellement explorable des Possibilités fournies pour l’Actor Context et l’Exploration Context courants.**

Il peut être :

- large ;
- réduit par recherche ;
- réduit par filtres ;
- contextualisé ;
- spatial ;
- issu d’une Veille ;
- orienté vers une Continuité existante.

Mais :

```text
POSSIBILITY_FIELD
≠ feed
≠ table persistante
```

---

## 17. Champ initial et expansion

Le champ initial peut être borné par l’amont pertinent.

Si rien d’utile n’est disponible, l’UX peut proposer :

> **Explorer plus largement**

Cette action exprime une intention humaine d’élargissement.

Elle ne fixe pas le mécanisme algorithmique exact.

L’UX ne relâche jamais silencieusement les critères simplement pour remplir l’écran.

---

## 18. `EXPLORATION_GROUP`

Découvrir peut organiser le champ avec des regroupements de Presentation.

Exemples :

```text
Ce week-end
Pour apprendre
Autour de vous
Pour votre voyage
À distance
Pour votre projet
```

Mais :

```text
EXPLORATION_GROUP
≠ catégorie métier
≠ relation causale
≠ preuve de pertinence
```

---

## 19. Plusieurs placements de la même Possibilité

Une Possibilité peut apparaître dans plusieurs regroupements :

```text
Formation X
→ Pour apprendre Python
→ En novembre
→ À Nairobi
```

Elle conserve une seule identité logique.

Donc :

```text
1 Possibilité
→ 0..n placements de Presentation
```

Le Bookmark, le détail et les relations personnelles restent cohérents.

---

## 20. La racine Découvrir

La structure conceptuelle est :

```text
DÉCOUVRIR
│
├── ACTOR_CONTEXT
│
├── HEADER
│   ├── Makolo
│   ├── Search
│   ├── Filters / context
│   └── Avatar
│
├── EXPLORATION_CONTEXT ?
│
├── POSSIBILITY_FIELD
│   ├── EXPLORATION_GROUP ?
│   │   ├── POSSIBILITY
│   │   └── POSSIBILITY
│   ├── POSSIBILITY
│   └── ...
│
├── VIEWS
│   ├── MAIN
│   ├── SPATIAL
│   └── COMPARISON
│
├── END_STATE
│
└── DEPTH
    └── POSSIBILITY DETAIL
```

Ce schéma est une grammaire UX.

Il n’est pas un schéma API.

---

## 21. Header

Le header personnel de référence est :

```text
Makolo | Recherche | Filtres / contexte | Avatar
```

Notifications et Conversations ne sont pas au premier niveau.

Découvrir doit rester un mode exploratoire protégé des obligations quotidiennes.

---

## 22. Surface principale

La racine doit permettre de reconnaître rapidement :

```text
QU'EST-CE QUE C'EST ?
QU'EST-CE QUE CELA POURRAIT ME PERMETTRE ?
QUEL FAIT IMPORTANT CHANGE LE CHOIX ?
```

Et lorsque cela compte :

```text
OÙ ?
QUAND ?
COMBIEN ?
```

Elle n’a pas besoin d’évaluer complètement chaque Possibilité avant ouverture.

---

## 23. Grammaire contextuelle

La même structure interne de Possibilité peut produire des présentations très différentes.

### Transport

```text
origine
destination
horaire
durée
prix
```

### Événement

```text
expérience
date
lieu
```

### Formation

```text
programme
format
durée
session
```

### Funding

```text
ce qui peut être financé
fenêtre
couverture
conditions importantes
```

### Obtention

```text
cible
mode
prix / conditions
disponibilité
```

Backend générique.

Métier visible contextuel.

---

## 24. Composants partagés

Un composant partagé `DiscoveryCard` est permis.

Ce qui est interdit est une sémantique universelle rigide du type :

```text
image
titre
date
bouton
```

appliquée à toutes les possibilités en effaçant leur grammaire métier.

Principe :

```text
shell visuel partagé
→ possible

sens métier uniformisé
→ non
```

---

## 25. Possibilité ≠ Card

La Possibilité est sémantique.

Sa représentation peut être :

- Card ;
- ligne ;
- bloc visuel ;
- résultat de recherche ;
- élément cartographique ;
- aperçu document ;
- composition ;
- média contextualisé.

Le composant ne crée jamais le modèle.

---

## 26. Médias

Découvrir est la surface la plus visuelle de Makolo.

Image, vidéo, carte, document ou audio sont légitimes lorsqu’ils aident à comprendre une Possibilité.

Ils doivent servir :

```text
RECOGNIZE
UNDERSTAND
ESTABLISH
PREPARE
ACT
```

Le média n’est jamais une fin en soi.

---

## 27. No Orphan Content / Media

Chaque contenu doit répondre à :

> **Quelle Possibilité cela m’aide-t-il à comprendre ou explorer ?**

Une vidéo sans contexte d’action n’a pas vocation à devenir un post Discover générique.

Presentation représente les réalités.

Elle ne possède pas un feed de contenu.

---

## 28. Facts et Assessment

Le détail distingue :

```text
FACTS
→ ce qui est réellement établi

ASSESSMENT
→ FAVORABLE[]
→ LIMITING[]
→ UNKNOWN[]
```

`ESTABLISHED` n’est donc pas un quatrième assessment équivalent.

C’est la couche de faits connus.

---

## 29. `FAVORABLE`

Un fait favorable peut aider l’acteur à comprendre pourquoi une possibilité peut être plus envisageable.

Exemples :

```text
votre credential actuel peut couvrir un prérequis
une session existe dans la période recherchée
une ressource déjà possédée peut être utilisée
```

Cela ne signifie pas :

> choisissez cette possibilité.

---

## 30. `LIMITING`

Une limitation indique une contrainte réelle connue.

Exemples :

```text
deadline proche
capacity restante faible
coût connu élevé par rapport à une contrainte explicite
condition propriétaire non satisfaite lorsqu'elle est réellement établie
```

La Presentation ne transforme pas une inconnue en limitation.

---

## 31. `UNKNOWN`

Invariant :

```text
UNKNOWN
≠ FALSE
≠ IMPOSSIBLE
≠ READY
```

Exemple :

```text
Votre éligibilité n’est pas encore établie.
```

est différent de :

```text
Vous n’êtes pas éligible.
```

---

## 32. Fraîcheur et connaissance

Quand cela change le choix, la Possibilité peut exposer :

```text
Dernière vérification...
À confirmer...
Information ancienne...
```

Notamment pour :

- prix ;
- places ;
- deadline ;
- disponibilité ;
- horaire ;
- localisation.

Le design ne doit jamais rendre une information plus certaine ou plus fraîche qu’elle ne l’est.

---

## 33. Variantes

Une Possibilité peut exposer des variantes lorsque cette structure est réellement fournie.

Exemple :

```text
Formation X
├── session matin
└── session soir
```

L’UX n’infère pas elle-même les variantes à partir de simples similarités.

---

## 34. Variante ≠ alternative

Conceptuellement :

```text
VARIANT
→ autre réalisation suffisamment proche de la même option

ALTERNATIVE
→ autre option indépendante dans le même contexte d'exploration
```

La frontière exacte peut être fournie par le domaine ou l’amont.

---

## 35. Relations entre Possibilités

Découvrir peut présenter des relations utiles lorsqu’elles sont fournies par l’amont ou les propriétaires.

Exemples humains :

```text
Autres façons d’y arriver
Autres sessions
Peut aider à financer cette formation
Peut compléter cette option
```

Découvrir ne devient pas propriétaire d’un nouveau graphe canonique.

---

## 36. Relation ≠ fusion

Deux possibilités reliées restent distinctes lorsqu’elles peuvent être considérées, choisies ou rejetées indépendamment.

Même objectif n’implique pas même identité.

Même porteur n’implique pas même identité.

Même contexte n’implique pas causalité.

---

## 37. Relations n-aires

Les relations peuvent concerner plusieurs possibilités à la fois.

Exemple :

```text
Option A
Option B
Option C
    ↓
même contrainte temporelle
```

L’UX ne doit pas forcer une série artificielle de relations pair-à-pair si la vérité porte sur une relation collective.

---

## 38. Search

Search réduit ou recompose le même champ.

Exemples :

```text
quelque chose à faire ce soir
formation pour apprendre X
moyen de rejoindre Goma
financement pour mon projet
ordinateur à louer
```

La personne n’a pas besoin de connaître les noms de modèles ou de verticales backend.

---

## 39. Filtres

Les filtres ajustent le champ avec un vocabulaire humain.

Exemples possibles :

- Quand ;
- Où ;
- Distance ;
- Prix ;
- Format ;
- Mode ;
- autres critères contextuellement utiles.

Ils ne doivent pas exposer directement :

```text
model
database state
internal enum
```

simplement parce que ces structures existent.

---

## 40. Progressive disclosure des filtres

La racine ne doit pas afficher des dizaines de contrôles.

Les filtres secondaires peuvent être placés :

- en profondeur ;
- dans un panneau ;
- dans une bottom sheet mobile.

Les filtres actifs doivent rester visibles lorsqu’ils changent réellement le champ.

---

## 41. Carte

La carte est une lecture spatiale du même champ d’exploration.

Mais :

```text
1 Possibilité
≠ 1 point cartographique
```

Une Possibilité peut être soutenue par plusieurs Occurrences ou lieux.

La formulation correcte est :

> **La carte projette les faits spatiaux significatifs associés au Possibility Field courant.**

---

## 42. Carte seulement si utile

La carte apparaît lorsque la géographie aide réellement à comprendre ou choisir.

Elle peut être utile pour :

- événements ;
- transports ;
- lieux ;
- services physiques ;
- ressources locales.

Elle peut être inutile pour certaines possibilités numériques ou abstraites.

---

## 43. Changer de vue ne change pas l’exploration

Invariant :

```text
LIST → MAP
MAP → LIST
```

ne doit pas réinitialiser :

- query ;
- filtres ;
- contexte ;
- sélection ;
- comparaison.

Le changement de représentation n’est pas un nouveau champ implicite.

---

## 44. Comparaison

La comparaison est une projection temporaire de plusieurs Possibilités réellement comparables.

Elle peut montrer :

```text
Option A      Option B

quand
où
coût
durée
format
conditions
disponibilité
inconnues
```

Elle ne devient pas un nouveau propriétaire.

Elle ne doit pas calculer un gagnant UX générique.

---

## 45. Comparables seulement

Une formation et une bourse qui la finance ne sont pas nécessairement des alternatives.

La bourse peut être un complément.

Donc la comparaison doit respecter la nature réelle de la relation.

---

## 46. Détail d’une Possibilité

La profondeur de référence peut comprendre :

```text
POSSIBILITY DETAIL

IDENTITY / REPRESENTATION
POSSIBLE MEANING
FACTS
ASSESSMENT
    FAVORABLE[]
    LIMITING[]
    UNKNOWN[]
VARIANTS?
RELATIONS?
MEDIA?
TIME / PLACE / COST?
FRESHNESS?
PROVENANCE? si utile
PERSONAL_RELATION
CAPABILITIES
OWNER_DEPTH
```

Cette forme est conceptuelle.

Elle n’impose pas un payload API unique.

---

## 47. Owner Depth

Lorsque la vérité complète devient nécessaire, Découvrir ouvre le domaine propriétaire approprié.

Exemples :

```text
Activity
Occurrence
Opportunity
Funding
Service
Obtention
```

Découvrir ne copie pas leurs règles.

---

## 48. Bookmark

Bookmark signifie :

> **Je veux pouvoir retrouver cette possibilité plus tard.**

Il ne signifie pas :

```text
Interest
Watch
Intent
Engagement
```

Le runtime peut continuer à déléguer cette conservation aux vérités propriétaires existantes.

Aucun `UniversalBookmark` métier n’est requis.

---

## 49. Veille

Une Veille signifie :

> **Continuer à observer un champ ou une condition sans s’engager.**

Mais la Veille n’est pas une action universelle disponible sur chaque Possibilité.

Elle n’est proposée que lorsqu’un contrat réel peut exprimer la surveillance demandée.

Donc :

```text
WATCH
= capability
```

---

## 50. Bookmark ≠ Veille ≠ engagement

Invariant :

```text
SAVE
≠ WATCH
≠ ENGAGE
```

Une personne peut sauvegarder sans surveiller.

Elle peut surveiller sans sauvegarder.

Elle peut faire les deux.

Aucune de ces actions ne crée automatiquement En cours.

---

## 51. Intention

L’intention reste une notion humaine utile :

> **Une orientation explicite de la personne vers un résultat ou une option, sans que la poursuite propriétaire soit nécessairement déjà engagée.**

Mais :

```text
IntentStatus
IntentLifecycle
```

ne sont pas introduits par ce contrat.

---

## 52. Pas de lifecycle Discover universel

Ce document ne persiste pas :

```text
DISCOVERED
→ EXPLORED
→ CONSIDERED
→ INTENDED
→ ENGAGED
```

La personne peut :

```text
voir → réserver
```

directement.

Ou :

```text
voir → garder → jamais engager
```

Ces mots peuvent aider à réfléchir.

Ils ne définissent pas un workflow générique.

---

## 53. Préparer ≠ engager

Découvrir peut permettre de :

- comprendre les Requirements ;
- retrouver les ressources déjà disponibles ;
- préparer un brouillon ;
- comparer ;
- calculer ce qui manque ;

sans établir une poursuite réelle.

Invariant :

```text
PREPARE
≠ ENGAGE
```

---

## 54. Engagement

Découvrir ne possède jamais :

```text
possibility.status = engaged
```

Le flux est :

```text
Possibilité Discover
        ↓
action explicite et légitime
        ↓
domaine propriétaire
        ↓
vérité canonique créée / modifiée
        ↓
poursuite réellement engagée
        ↓
En cours peut projeter une Continuité
```

---

## 55. CTA d’engagement

Le CTA visible utilise le verbe naturel du propriétaire.

Exemples :

```text
Candidater
Réserver
S'inscrire
Acheter
Louer
Demander
Participer
Rejoindre la liste
```

Pas :

```text
Engager
Créer Journey
Start workflow
```

---

## 56. Possibilité non immédiatement engageable

Une Possibilité reste légitime même si aucune mutation propriétaire n’est actuellement disponible.

Elle peut permettre seulement :

```text
Ouvrir
Comprendre
Garder
Partager
Surveiller si possible
```

Découvrir n’invente pas un endpoint ou un Journey pour fournir artificiellement un CTA.

---

## 57. Possibilité déjà engagée

La réalité publique peut rester visible après engagement.

Mais la relation personnelle peut conduire l’UX à montrer :

```text
Déjà engagé
Voir en cours
```

plutôt qu’un CTA qui recommencerait le processus.

---

## 58. Frontière avec En cours

```text
Découvrir
→ options encore explorables

En cours
→ poursuites effectivement engagées qui continuent
```

Donc :

```text
OPEN
SAVE
WATCH
SHARE
COMPARE
PREPARE
≠ engagement automatique
```

Le seuil d’engagement appartient au domaine propriétaire.

---

## 59. Frontière avec Now

Une possibilité pertinente avec une deadline proche n’entre pas automatiquement dans Now.

```text
PERTINENCE
+ DEADLINE
≠ NOW
```

Une Situation Now peut apparaître lorsqu’il existe :

```text
relation personnelle légitime
+ conséquence actuelle
```

Exemple :

```text
Veille explicite
→ condition devenue vraie
→ conséquence actuelle
→ Situation Now possible
```

---

## 60. Frontière avec Moi

Moi peut apporter du capital utile :

- Credential ;
- Access ;
- Resource ;
- vécu ;
- préférence explicitement déclarée.

Ce capital peut modifier l’évaluation fournie ou la compréhension d’une possibilité.

Mais :

```text
capital disponible
≠ pertinence automatique
```

Et Découvrir ne copie pas les vérités de Moi.

---

## 61. Découvrir et Space

Le même concept existe côté Space.

Personnel :

> **Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

Space :

> **Qu’est-ce qui pourrait nous aider à avancer ?**

Le contexte acteur change.

La grammaire profonde reste comparable.

Les possibilités personnelles et collectives ne fusionnent pas simplement parce que le même humain les consulte.

---

## 62. Autorité

Une Possibilité visible ne confère aucun droit supplémentaire.

La visibilité d’une action dépend toujours :

- du propriétaire ;
- de Permission ;
- de Mandate ;
- d’Access ;
- du contexte acteur ;
- de la confidentialité ;
- des autres règles canoniques.

Composition ne transfère jamais l’autorité.

---

## 63. Freshness et mutation

Une action sensible doit être revalidée par le propriétaire lorsque nécessaire.

Exemple :

```text
place visible il y a 20 minutes
≠ place encore garantie au moment de réserver
```

Le détail local peut rester utile.

L’action canonique doit vérifier le monde réel courant.

---

## 64. Local-first

Découvrir peut conserver localement ce qui a déjà été acquis :

- projections de possibilités déjà vues ;
- détails déjà consultés ;
- recherches déjà matérialisées ;
- éléments sauvegardés ;
- certaines Veilles et résultats déjà synchronisés.

Mais le client local ne doit pas prétendre :

- découvrir exhaustivement le monde actuel ;
- recalculer globalement la pertinence ;
- connaître une disponibilité actuelle depuis une copie ancienne ;
- reconstruire un classement Molongo.

---

## 65. Offline avec snapshot

Si un snapshot existe :

```text
OFFLINE_WITH_SNAPSHOT
```

Découvrir peut continuer à présenter ce qui était connu.

Il doit préserver la fraîcheur et ne pas prétendre actualiser le champ.

---

## 66. Offline sans snapshot

Si aucune donnée locale n’existe :

```text
OFFLINE_NO_SNAPSHOT
```

l’interface ne doit pas dire :

> aucune possibilité n’existe.

Elle doit expliquer :

> de nouvelles possibilités ne peuvent pas être chargées pour le moment.

---

## 67. Refresh

Un refresh doit préserver autant que possible :

- identité ;
- scroll ;
- query ;
- filtres ;
- comparaison ;
- contexte ;
- sélection ;
- position de carte.

Le refresh technique ne doit pas recréer visuellement toutes les Possibilités comme de nouveaux objets.

---

## 68. Retour et continuité cognitive

Le parcours :

```text
Découvrir
→ Possibilité
→ propriétaire
→ retour
```

doit restaurer raisonnablement :

- contexte d’exploration ;
- recherche ;
- filtres ;
- scroll ;
- groupe ;
- sélection ;
- carte ;
- comparaison éventuelle.

---

## 69. États de fin

Découvrir distingue au moins cinq situations UX :

```text
NO_MATCH
END_OF_FIELD
NO_CURRENT_PROPOSAL
OFFLINE_WITH_SNAPSHOT
OFFLINE_NO_SNAPSHOT
```

Ce ne sont pas des états métier.

---

## 70. `NO_MATCH`

La recherche ou les filtres actuels ne correspondent à aucune possibilité.

L’UX peut proposer, lorsque pertinent :

- retirer une contrainte ;
- modifier la date ;
- élargir la zone ;
- changer la recherche.

Elle ne doit pas relâcher silencieusement les critères.

---

## 71. `END_OF_FIELD`

Le champ utile courant a été parcouru.

Cette fin est légitime.

Exemple de sens :

> Vous avez vu ce qui est disponible dans ce contexte.

L’interface n’ajoute pas du filler pour continuer le scroll.

---

## 72. `NO_CURRENT_PROPOSAL`

L’amont ne propose actuellement aucune possibilité suffisamment utile dans le contexte courant.

Découvrir peut alors proposer volontairement :

> **Explorer plus largement**

sans inventer de contenu.

---

## 73. Découvrir doit savoir s’arrêter

Quand la personne a trouvé, Découvrir peut s’effacer.

Quand plus rien de vraiment différent n’est disponible, il peut s’arrêter.

Quand continuer n’apporte plus de valeur, il n’a aucune obligation de maintenir l’attention.

Abandonner une possibilité peut également être une bonne issue.

---

## 74. Pagination technique

Pagination, cursors et lazy loading sont légitimes.

Mais :

```text
page 1
page 2
page 3
```

n’est pas le modèle mental du produit.

La personne explore un champ de possibilités.

Pas un feed destiné à être consommé sans fin.

---

## 75. Runtime actuel : bases déjà utiles

Le runtime Mature possède déjà notamment :

- collection multi-famille ;
- identité logique ;
- déduplication ;
- détail désigné ;
- provenance ;
- availability/prix lorsque connus ;
- personal relation lorsque résolue ;
- Bookmark / Save ;
- DiscoveryWatch ;
- Search ;
- carte ;
- pagination ;
- assessment `favorable / limiting / unknown` ;
- handoff propriétaire Event réel ;
- local-first mobile avec fraîcheur.

Ces briques doivent être réutilisées avant d’introduire une nouvelle abstraction.

---

## 76. Runtime actuel : Web

Le Web Mature est déjà proche du contrat cible avec :

- question humaine ;
- recherche en langage naturel ;
- contraintes comprises ;
- filtres ;
- proximité ;
- liste ;
- carte ;
- aperçu sans perdre la liste ;
- pagination ;
- fin explicite du champ ;
- absence d’élargissement silencieux.

Ces éléments ne doivent pas être réécrits par principe.

---

## 77. Runtime actuel : mobile

Le mobile possède une fondation saine :

```text
title
summary
owner
place
timing
price
availability
```

avec Search, Map, détail, save et cache local.

Les principaux écarts UX vers la cible Mature concernent surtout :

- richesse média ;
- grammaires verticales ;
- assessment plus lisible ;
- variantes ;
- relations utiles ;
- comparaison ;
- regroupements exploratoires ;
- états de fin plus précis ;
- continuité complète du contexte liste/carte/détail.

Ce sont des gaps d’expression, pas une justification pour recréer Discovery.

---

## 78. `Pour vous` et anciens concepts V1

Les anciennes surfaces ou APIs :

```text
Pour vous
Trending
Popular
Nouveautés
```

peuvent subsister comme compatibilités historiques.

Elles ne définissent pas le contrat Mature de Découvrir.

Le contrat Mature reste centré sur le champ des possibilités.

---

## 79. Web Search / Mayele

Les résultats Web bruts ne deviennent pas automatiquement des Possibilités Discover.

Le cycle attendu reste conceptuellement :

```text
acquisition
→ interprétation
→ résolution
→ admission
→ connaissance / propriétaires
→ pertinence
→ Discover
```

Découvrir ne présente pas des URLs simplement parce qu’elles contiennent les bons mots.

---

## 80. Molongo n’est pas propriétaire des réalités

Molongo peut déterminer ou contribuer à déterminer :

- pertinence ;
- ordre ;
- relations utiles ;
- expansion du champ.

Mais :

```text
Molongo
≠ owner Activity
≠ owner Opportunity
≠ owner Funding
≠ owner Service
```

Les vérités restent chez les domaines canoniques.

---

## 81. Anti-features

Découvrir ne doit pas devenir :

- un feed social ;
- un TikTok de possibilités ;
- un scroll infini artificiel ;
- un moteur de nouveautés ;
- une page « populaire » par défaut ;
- un classement de vie ;
- un score global ;
- une boîte de recommandations opaques ;
- un catalogue de tables backend ;
- un centre de notifications ;
- une collection uniforme de Cards ;
- une surface où chaque item possède le même CTA ;
- une surface où chaque item possède obligatoirement une image ;
- une page où Bookmark implique Interest ;
- une page où Watch implique Engagement ;
- un système où voir réécrit les Interests ;
- un système où popularité signifie pertinence ;
- une interface qui invente les alternatives ;
- une interface qui invente l’éligibilité ;
- une interface qui invente la disponibilité ;
- une interface qui relâche silencieusement les critères ;
- une source d’autorité locale offline ;
- un propriétaire générique de toutes les mutations.

---

## 82. Invariants consolidés

1. **Découvrir est un champ d’exploration, pas un feed.**
2. **Découvrir est l’espace des possibles, pas celui des nouveautés.**
3. **La pertinence est fournie par l’amont Molongo/intelligence ; l’UX ne la recalcule pas.**
4. **Pas de score global UX de pertinence.**
5. **Une Possibilité Discover est une projection UX, pas un nouveau modèle métier.**
6. **Possibilité ≠ Activity ≠ Opportunity ≠ Card.**
7. **Toute Possibilité doit être justifiable par des vérités propriétaires.**
8. **`POSSIBILITY_BASIS` reste un invariant avant d’être un éventuel champ.**
9. **`POSSIBILITY_IDENTITY` est une identité de projection, pas une nouvelle identité métier.**
10. **Même titre ≠ même Possibilité.**
11. **Plusieurs sources ≠ plusieurs Possibilités.**
12. **`EXPLORATION_CONTEXT` n’est pas un modèle persistant obligatoire.**
13. **Search est un moyen d’exprimer l’exploration, pas un domaine séparé.**
14. **`POSSIBILITY_FIELD` n’est pas un feed persistant.**
15. **L’UX n’invente jamais une raison de pertinence.**
16. **Faits établis ≠ assessment.**
17. **Assessment = favorable / limiting / unknown lorsque ces lectures sont supportées.**
18. **Unknown ≠ false ≠ impossible ≠ ready.**
19. **Variant ≠ Alternative.**
20. **Les relations entre Possibilités sont présentées lorsqu’elles sont fournies ; l’UX ne crée pas un nouveau graphe.**
21. **Relation ≠ fusion.**
22. **Même contexte ≠ causalité.**
23. **Un groupe d’exploration est Presentation seulement.**
24. **Une Possibilité peut avoir plusieurs placements sans duplication d’identité.**
25. **Carte = projection spatiale du champ, pas `1 Possibilité = 1 point`.**
26. **Changer de vue ne réinitialise pas l’exploration.**
27. **Comparaison = projection temporaire.**
28. **Complément ≠ alternative.**
29. **Bookmark ≠ Veille ≠ engagement.**
30. **Veille seulement si un contrat réel peut exprimer la surveillance.**
31. **Pas de lifecycle Discover universel.**
32. **Préparer ≠ engager.**
33. **Le seuil d’engagement appartient au domaine propriétaire.**
34. **Pas de CTA générique `Engager`.**
35. **Une Possibilité peut être légitime sans être immédiatement engageable.**
36. **Une Possibilité déjà engagée peut rester publiquement découvrable.**
37. **Discover → owner → vérité canonique → éventuellement En cours.**
38. **Pertinence seule ne crée pas Now.**
39. **Moi peut faciliter une possibilité sans rendre celle-ci automatiquement pertinente.**
40. **Profile Discover et Space Discover gardent des Actor Contexts distincts.**
41. **Un composant partagé est permis ; une sémantique métier uniforme ne l’est pas.**
42. **Découvrir peut être la surface la plus visuelle de Makolo.**
43. **No Orphan Content / Media reste strict.**
44. **Freshness reste visible lorsqu’elle change le choix.**
45. **Offline représente le déjà-acquis, jamais le monde actuel inventé.**
46. **Le retour restaure le contexte d’exploration.**
47. **La fin du champ est une issue normale.**
48. **Explorer plus largement est une action volontaire.**
49. **Pagination technique ≠ scroll infini conceptuel.**
50. **Les anciens `Pour vous`, Trending ou Popular ne définissent pas le contrat Mature.**
51. **Web Search brut ≠ Possibilité Discover.**
52. **Molongo peut calculer la pertinence sans devenir propriétaire des réalités métier.**

---

## 83. Exemples consolidés

### 83.1. Recherche de transport

```text
Exploration Context
→ Aller à Nairobi samedi

Possibility Field
├── Vol direct
├── Vol avec escale
└── Bus
```

La recherche exprime l’intention.

Les options restent distinctes.

La carte peut représenter les points spatiaux pertinents sans imposer `1 option = 1 point`.

### 83.2. Formation avec plusieurs sessions

```text
Formation Data Science
├── Session novembre
├── Session décembre
└── Session janvier
```

Selon les propriétaires et l’amont, ces sessions peuvent rester des variantes d’une même Possibilité ou devenir plusieurs possibilités indépendantes si elles changent substantiellement le choix.

Le frontend ne décide pas cette identité à partir du titre.

### 83.3. Formation et bourse

```text
Formation Montréal
```

et :

```text
Bourse X
```

ne sont pas nécessairement des alternatives.

Une relation fournie peut être présentée comme :

> **Peut aider à financer cette formation**

sans fusionner les deux réalités.

### 83.4. Bookmark

```text
Formation X
→ Garder
```

signifie seulement :

> retrouver plus tard.

Aucune Journey n’est créée.

Aucune Continuité En cours n’est créée.

### 83.5. Veille

```text
Recherche
→ bourses pour Master Architecture
```

peut devenir une Veille si le contrat DiscoveryWatch sait réellement exprimer cette requête.

Cela ne signifie pas que la personne a engagé une candidature.

### 83.6. Engagement réel

```text
Possibilité
→ Formation X

CTA propriétaire
→ Candidater

domaine propriétaire
→ candidature réellement commencée

projection
→ Continuité En cours possible
```

Discover ne possède pas l’état de candidature.

### 83.7. Possibilité sans CTA d’engagement

```text
Nouvelle session annoncée pour l’année prochaine
```

peut permettre :

```text
Ouvrir
Garder
Surveiller si disponible
```

sans bouton artificiel `Engager`.

### 83.8. État vide précis

Recherche :

```text
formation demain
+ rayon 2 km
```

aucun résultat :

> **Aucune possibilité ne correspond à ces critères.**

Le produit peut proposer de modifier les critères.

Il ne relâche pas silencieusement la recherche.

### 83.9. Fin du champ

Après parcours du champ courant :

> **Vous avez vu ce qui est disponible dans ce contexte.**

Puis éventuellement :

> **Explorer plus largement**

si la personne le souhaite.

---

## 84. Points volontairement ouverts

Avant une implémentation Mature finale, restent ouverts :

1. le format précis des sorties Molongo consommées par Discover ;
2. l’ordre exact fourni à la Presentation ;
3. la manière d’exposer les raisons de pertinence lorsqu’elles existent ;
4. le contrat final des relations et variantes fournies par l’amont ;
5. la composition exacte des Cards par verticale ;
6. la comparaison mobile et desktop ;
7. les regroupements de Presentation réellement utiles ;
8. la microcopy finale des états de fin ;
9. le comportement précis de `Explorer plus largement` ;
10. la manière de préserver l’Exploration Context à travers toutes les profondeurs ;
11. le traitement précis des possibilités déjà engagées ;
12. l’extension éventuelle de DiscoveryWatch à d’autres familles ;
13. les représentations média par verticale ;
14. la stratégie finale de pagination/cursor ;
15. la convergence progressive avec les façades legacy `for-you` et autres contrats V1.

Aucun de ces points ne justifie à lui seul un nouveau domaine persistant.

---

## 85. Doctrine d’implémentation future

Avant d’ajouter un modèle ou un état pour Découvrir :

1. vérifier les domaines propriétaires ;
2. vérifier les selectors d’admission ;
3. vérifier Z3 et les projections Discovery existantes ;
4. vérifier les identités logiques et la provenance ;
5. vérifier les sorties Molongo/intelligence ;
6. vérifier les Relations existantes ;
7. vérifier Bookmark / OpportunitySave ;
8. vérifier DiscoveryWatch ;
9. vérifier Search et les Research Missions ;
10. vérifier Presentation ;
11. vérifier le cache mobile/local-first ;
12. préférer read models et composition aux copies de vérités.

Par défaut :

> **Découvrir doit rester une projection d’exploration avant d’être pensé comme un nouveau modèle métier.**

---

## 86. Critères de sortie d’une future implémentation Mature

Une implémentation Mature de Découvrir devrait démontrer au minimum :

- champ de possibilités alimenté par l’amont pertinent ;
- aucune logique de pertinence reconstruite dans le frontend ;
- identité stable et déduplication ;
- multi-famille ;
- provenance conservée ;
- Search et filtres sur le même champ ;
- carte cohérente avec le même Exploration Context ;
- `1 Possibilité ≠ 1 point` lorsque plusieurs faits spatiaux existent ;
- retour avec restauration du contexte ;
- détails riches sans exposer la taxonomie backend ;
- faits / favorable / limiting / unknown clairement distingués ;
- unknown préservé ;
- Bookmark distinct de Watch ;
- Watch seulement lorsque supporté ;
- aucune création réflexe de Journey ;
- handoff propriétaire réel ;
- CTA contextualisé au domaine ;
- possibilité sans CTA d’engagement supportée ;
- possibilité déjà engagée représentable sans recommencer ;
- médias contextualisés ;
- comparaison sans score gagnant universel ;
- fin du champ ;
- `NO_MATCH` ;
- `NO_CURRENT_PROPOSAL` ;
- offline avec snapshot ;
- offline sans snapshot ;
- fraîcheur honnête ;
- aucun élargissement silencieux ;
- aucune régression d’autorité, visibilité ou IDOR.

---

## 87. Références de cadrage

Ce contrat consolide principalement les principes issus de :

- `docs/architecture/ux-now.md`
- `docs/architecture/ux-ongoing.md`
- `docs/architecture/m8-ux-shell-contract.md`
- `docs/architecture/z3-discovery-projection-audit.md`
- `docs/architecture/user-navigation-and-discovery.md`
- `docs/architecture/discovery-growth-v1.md` comme contexte historique, non comme cible Mature
- `docs/architecture/mobile-a2-surface-contracts.md`
- `docs/architecture/mobile-visual-charter-v1.1.md`
- `docs/architecture/mobile-sync-continuity-kernel.md`
- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_Obtention_Verticale_Cadre_Conception_v2.md`
- `makolo-web-search.md`
- les contrats Molongo / intelligence pertinents pour la pertinence et les relations, sans transférer leurs calculs à la Presentation.

Le code, les migrations, les tests et les contrats du `main` courant restent la vérité runtime lors de toute future implémentation.

---

## 88. Formulation finale

> **Découvrir est la surface Makolo qui rend explorable le champ des possibilités sans transformer l’exploration en obligation. Son unité UX, la Possibilité Discover, est une projection humaine d’une option réelle soutenue par des vérités canoniques ; elle n’est ni une Activity, ni une Opportunity, ni une Card, ni un nouveau modèle universel. La pertinence est déterminée en amont, notamment par Molongo/intelligence, tandis que l’UX se concentre sur reconnaître, comprendre, rechercher, filtrer, cartographier, comparer, garder, surveiller lorsque le contrat le permet et transmettre l’engagement au domaine propriétaire. Découvrir peut être visuellement riche, mais ne devient jamais un feed : il doit pouvoir finir, préserver les inconnues et la fraîcheur, respecter l’Actor Context, et s’effacer lorsque la personne a trouvé ce qu’elle cherchait.**


## Gel conceptuel 2026-10-05 — `DiscoverMeResponse`

Cette section consolide le contrat cible serveur/client de Découvrir sans transformer la projection en nouveau domaine métier.

### A. Actor Context

```text
ACTOR_CONTEXT
→ exactement 1 Profile pour Discover Me
```

Le même viewer humain peut consulter un futur Discover Space, mais les Actor Contexts personnel et collectif ne fusionnent pas.

### B. Exploration Context

```text
EXPLORATION_CONTEXT
├── query?
├── intention explicite?
├── constraints[]
├── filters[]
├── current_view?
├── spatial_context?
└── autre contexte établi
```

Le client peut envoyer un contexte brut. Si l'amont interprète réellement ce contexte, le serveur peut retourner un `RESOLVED_EXPLORATION_CONTEXT`. Search reste une expression de l'exploration, pas son équivalent complet.

### C. Possibility Field

```text
POSSIBILITY_FIELD
├── possibilities[]
├── ordering déjà résolu
├── continuation / pagination?
├── presentation placements / groups?
├── spatial projection data?
└── end_state?
```

Le client respecte l'ordre amont et ne recalcule pas un ranking global de pertinence.

### D. Possibility Identity

```text
POSSIBILITY_IDENTITY
→ exactement 1 identité de projection stable
```

Elle sert à la déduplication, au détail, au bookmark, à la watch, au retour, au cache, à la comparaison et aux placements multiples.

Elle n'est pas une nouvelle identité métier et ne se reconstruit jamais par titre, date, image ou similarité de texte.

### E. Possibility Basis

`POSSIBILITY_BASIS` est un invariant architectural : toute Possibility doit pouvoir être justifiée par un ensemble minimal de vérités propriétaires.

```text
POSSIBILITY_BASIS
→ obligatoire conceptuellement côté serveur
→ pas obligatoirement sérialisé comme champ dédié
```

Un seul owner suffisamment riche peut suffire. Une `Occurrence` enrichie peut, par exemple, porter Activity + timing + place + availability nécessaires sans composition artificielle.

### F. Representation et Possible Meaning

La Possibility doit permettre de comprendre :

```text
QU'EST-CE QUE C'EST ?
QU'EST-CE QUE CELA POURRAIT PERMETTRE ?
QUEL FAIT IMPORTANT CHANGE LE CHOIX ?
OÙ ? QUAND ? COMBIEN ? lorsque pertinent
```

`POSSIBLE_MEANING` est une obligation sémantique, pas nécessairement un champ wire autonome. Le titre, la grammaire verticale, le résumé ou la représentation peuvent suffire.

Le shell visuel peut être partagé ; la grammaire métier reste contextuelle.

### G. Facts et Assessment

```text
FACTS[]
→ faits réellement établis

ASSESSMENT
├── FAVORABLE[]
├── LIMITING[]
└── UNKNOWN[]
```

```text
UNKNOWN ≠ FALSE ≠ IMPOSSIBLE ≠ READY
```

`FAVORABLE` n'est pas une recommandation automatique. `LIMITING` exige une contrainte réellement connue. Les faits restent distincts de leur lecture d'assessment.

### H. Variants et Alternatives

```text
VARIANT
→ autre réalisation suffisamment proche de la même option

ALTERNATIVE
→ autre Possibility indépendante
```

Le frontend ne crée pas les variants à partir d'une similarité de titre ou date.

### I. Relations

```text
RELATION
├── kind
├── members[]
└── context / basis?
```

Les relations peuvent être n-aires et doivent être fournies par l'amont ou les owners. `RELATION ≠ FUSION`. Complément ≠ alternative.

### J. Temporal et Spatial Facts

Le contrat cible généralise les simples champs uniques :

```text
TEMPORAL_FACTS[]
SPATIAL_FACTS[]
```

Une Possibility peut avoir plusieurs Occurrences, fenêtres ou lieux. Ainsi :

```text
1 Possibility ≠ 1 map point
```

Une représentation compacte peut toutefois sélectionner un timing ou lieu principal lorsque l'amont le permet.

### K. Cost

`COST` est une structure 0..1 pouvant représenter selon le propriétaire :

```text
free
exact
minimum
range
variant-dependent
unknown
```

Le runtime actuel `minimum + currency` reste utilisable là où il suffit, mais n'est pas une loi universelle du contrat Mature.

### L. Media

```text
MEDIA_BINDING
├── resource
├── target
└── purpose
    ├── RECOGNIZE
    ├── UNDERSTAND
    ├── ESTABLISH
    ├── PREPARE
    └── ACT
```

Découvrir peut être la surface la plus visuelle de Makolo, mais aucun média orphelin n'est admis.

### M. Provenance, knowledge et freshness

```text
PROVENANCE[]
→ plusieurs sources peuvent soutenir une même Possibility
```

Plusieurs sources ne créent pas plusieurs Possibilities.

La fraîcheur doit rester attachée aux connaissances lorsqu'elle change le choix : prix, places, deadline, disponibilité, horaire, localisation, etc. Une observation ancienne ne devient jamais disponibilité actuelle.

### N. Personal Relation

```text
PERSONAL_RELATION
├── OWNER_RELATION
├── SAVED_STATE
└── WATCH_STATE
```

```text
SAVE ≠ WATCH ≠ ENGAGE
```

Bookmark signifie « retrouver plus tard ». Watch n'est disponible que lorsqu'un contrat réel de surveillance existe. Aucune de ces actions ne crée automatiquement Ongoing.

### O. Capabilities et engagement

Le serveur fournit les `CAPABILITIES[]` et handoffs réellement supportés. Une Possibility peut être légitime sans CTA d'engagement.

Lorsqu'un engagement est possible, le CTA utilise le verbe naturel du owner : candidater, réserver, s'inscrire, acheter, louer, demander, participer, rejoindre la liste, etc.

Flux :

```text
Possibility Discover
→ action owner-backed
→ domaine propriétaire
→ vérité canonique créée / modifiée
→ poursuite réellement engagée
→ Ongoing peut éventuellement projeter une Continuité
```

Découvrir ne possède jamais `possibility.status = engaged`.

### P. Possibilité déjà engagée

Une Possibility publique peut rester visible après engagement. `PERSONAL_RELATION` peut conduire Presentation à afficher « Déjà engagé » / « Voir en cours » plutôt qu'à recommencer le processus.

### Q. Owner Depth

```text
PRIMARY_OWNER_DEPTH
→ 0..1 profondeur principale
```

Des handoffs complémentaires peuvent exister via relations, variants ou actions. Le client ne déduit jamais l'owner depuis `family` seul.

### R. Exploration Groups / placements

```text
1 Possibility
→ 0..n placements de Presentation
```

Un `EXPLORATION_GROUP` est Presentation uniquement : ni catégorie métier, ni causalité, ni preuve de pertinence.

### S. List / Map / Comparison

```text
LIST ⇄ MAP
```

préserve query, filtres, Exploration Context, sélection et comparaison. La carte projette le même field ; elle ne crée pas une seconde recherche implicite.

La comparaison est une projection temporaire de Possibilities réellement comparables. Elle n'a pas d'owner et ne calcule pas de gagnant universel.

### T. End States

Au minimum :

```text
NO_MATCH
END_OF_FIELD
NO_CURRENT_PROPOSAL
OFFLINE_WITH_SNAPSHOT
OFFLINE_NO_SNAPSHOT
```

Ces états sont UX, pas métier.

- `NO_MATCH` : les critères courants ne correspondent à rien ; les relâcher doit être volontaire.
- `END_OF_FIELD` : le champ courant a été parcouru ; c'est une fin légitime.
- `NO_CURRENT_PROPOSAL` : l'amont n'a rien de suffisamment utile maintenant ; « Explorer plus largement » peut être proposé explicitement.
- `OFFLINE_WITH_SNAPSHOT` : présenter ce qui était connu avec fraîcheur honnête.
- `OFFLINE_NO_SNAPSHOT` : dire que de nouvelles possibilités ne peuvent pas être chargées, jamais qu'aucune n'existe.

### U. Local-first

Le client peut conserver possibilités déjà vues, détails consultés, recherches matérialisées, saves, certaines watches, résultats synchronisés et médias acquis.

Il ne recalcule jamais exhaustivement le monde actuel, la pertinence globale, le classement Molongo ou la disponibilité courante depuis une copie ancienne.

Refresh et retour préservent autant que possible : identité, scroll, query, filtres, contexte, sélection, map position et comparaison.

### V. Contrat conceptuel serveur final

```text
DISCOVER ME RESPONSE
│
├── ACTOR_CONTEXT
│   └── Profile Me
│
├── RESOLVED_EXPLORATION_CONTEXT?
│   ├── query?
│   ├── intention?
│   ├── constraints[]
│   ├── filters[]
│   ├── spatial_context?
│   └── other resolved context
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
    │   ├── FRESHNESS / KNOWLEDGE
    │   ├── PERSONAL_RELATION
    │   │   ├── OWNER_RELATION
    │   │   ├── SAVED_STATE
    │   │   └── WATCH_STATE
    │   ├── CAPABILITIES[]
    │   └── OWNER_DEPTH / HANDOFF
    │
    ├── PRESENTATION_PLACEMENTS / GROUPS?
    ├── CONTINUATION / PAGINATION?
    └── END_STATE?
```

### W. Cardinalités stabilisées

```text
Actor Context          1
Exploration Context    0..1
Possibility Field      1
Possibilities          0..n
Possibility Identity   1
Possibility Basis      1 conceptuellement
Representation         1
Possible Meaning       1 sémantiquement
Facts                  0..n
Favorable              0..n
Limiting               0..n
Unknown                0..n
Variants               0..n
Relations              0..n
Temporal Facts         0..n
Spatial Facts          0..n
Cost                    0..1 structure
Media Bindings         0..n
Provenance             0..n
Personal Relation      0..1 structure
Capabilities           0..n
Primary Owner Depth    0..1
Presentation placements 0..n
End State              0..1
```

### X. Ce qui reste volontairement non figé

- wire JSON exact et `schema_version` ;
- format précis Molongo → Discover ;
- explication exacte des raisons de pertinence ;
- contrat wire final des variants et relations ;
- grammaires visuelles exactes par verticale ;
- UX détaillée de comparaison mobile/desktop ;
- regroupements utiles ;
- stratégie finale de cursor/pagination ;
- comportement exact d'« Explorer plus largement » ;
- traitement final des possibilités déjà engagées ;
- extensions de DiscoveryWatch ;
- représentations média exactes par verticale.


---



# IV. Concordance transversale finale

## 1. Trois questions, trois unités

```text
NOW ME
Situation Now
→ pourquoi cela compte maintenant ?

ONGOING ME
Continuité En cours
→ où en est ce que j'ai réellement engagé ?

DISCOVER ME
Possibilité Discover
→ qu'est-ce que je pourrais vouloir vivre, faire ou obtenir ?
```

Une réalité canonique peut participer à plusieurs projections sans duplication de vérité métier.

Exemple :

```text
Occurrence
→ Possibility dans Discover
→ constituant d'une Continuité dans Ongoing après engagement
→ Human Context ou Subject d'une Situation Now lorsqu'une conséquence actuelle apparaît
→ owner profond dans Jour J / Live
```

Ce sont plusieurs projections d'une même réalité, pas plusieurs copies de la réalité.

## 2. Relations entre les surfaces

```text
Discover
→ exploration
→ owner action réelle
→ engagement canonique
→ Ongoing possible

Ongoing
→ une poursuite continue
→ une conséquence actuelle apparaît
→ Now possible

Now
→ action / décision / attente / compréhension
→ owner update
→ reprojection
→ peut retourner au calme, rester Ongoing, ou sortir
```

Aucune flèche n'est un lifecycle universel obligatoire.

## 3. Ce que le serveur possède

Le serveur / orchestration possède notamment :

- admission dans chaque surface ;
- identité de projection lorsqu'elle est nécessaire ;
- relations canoniques et autorisées ;
- responsabilité et autorité effectives ;
- pertinence globale / ordering amont ;
- état sémantique ;
- conséquences et why-now ;
- knowledge state et freshness métier ;
- capabilities ;
- handoffs ;
- privacy/minimal disclosure ;
- mutations owner-backed ;
- revalidation concurrente/autoritative.

## 4. Ce que le client possède

Web/Flutter possèdent :

- rendu ;
- densité ;
- layout ;
- wording contextualisé à partir de sémantiques stables ;
- navigation locale ;
- sélection ;
- focus ;
- scroll ;
- tabs/modes de vue ;
- map camera ;
- viewers ;
- formatage de date, nombre et monnaie ;
- distance géométrique lorsqu'elle est calculable à partir de coordonnées reçues ;
- cache ;
- snapshot freshness ;
- offline presentation ;
- drafts ;
- outbox ;
- pending UI ;
- accessibility.

Le client ne possède jamais une seconde logique métier parallèle.

## 5. Structure transversale de `OBJECT`

Lorsqu'une projection sémantique transporte une réalité canonique :

```text
OBJECT
├── IDENTITY
│   ├── kind
│   └── id
├── REPRESENTATION
├── CONTEXT spécifique
├── CAPABILITIES[]
└── LINKS
```

Les projections `REFERENCE / INLINE / DETAIL` permettent d'éviter à la fois les références trop pauvres et les payloads récursifs/gigantesques.

## 6. Discipline de composition

Avant d'ajouter un modèle, un statut ou une copie de vérité :

1. vérifier si un owner canonique possède déjà le fait ;
2. vérifier relations, selectors, read models et Readiness ;
3. vérifier Domain Events / Analytics / Presentation si le besoin est dérivé ;
4. préférer une projection ou composition à une table nouvelle ;
5. ne jamais transférer implicitement Permission, Mandate, Access, Payment ou visibilité privée à travers une composition.

## 7. Discipline d'implémentation future

Avant tout chantier Django/Web/Flutter sur ces contrats :

1. rafraîchir `main` ;
2. vérifier HEAD, commits récents, PR/branches pertinentes, CI, migrations et docs touchées ;
3. comparer le runtime aux présents contrats ;
4. corriger les projections serveur avant d'ajouter des heuristiques client ;
5. versionner les changements de contrat lorsqu'ils cassent un snapshot mobile existant ;
6. tester permissions/IDOR, confidentialité, données anciennes, offline, pending sync et revalidation ;
7. ne jamais backfiller artificiellement des vérités anciennes si leur état actuel reste valide ;
8. préserver les owners et invariants canoniques.

## 8. Critère ultime

Le contrat est correct lorsque :

```text
le serveur prépare proprement
ce qu'il sait,
ce qu'il peut exposer,
ce qu'il a compris,
et ce qui peut réellement être fait,

pendant que

le client transforme cette projection
en une expérience claire, contextuelle,
belle et professionnelle,
sans reconstruire Makolo localement.
```

> **Makolo marche pour vous.**
