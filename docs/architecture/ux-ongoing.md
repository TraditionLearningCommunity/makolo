# Makolo — UX En cours
## Contrat consolidé de la continuité personnelle

**Statut :** cadre UX conceptuel consolidé de travail  
**Portée :** expérience personnelle Web et mobile ; grammaire réutilisable par `Métier` dans un Space  
**Nom UX retenu :** `En cours`  
**Question humaine :** « Pour ce que j’ai déjà engagé, où en suis-je et qu’est-ce qui continue ? »  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »  
**Base runtime vérifiée avant consolidation :** `main@6fda1e8c448aacd0100e72d02103d92b5a9ed079`

---

# 1. Objet du document

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

# 2. Place de En cours dans Makolo

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

# 3. Définition de En cours

> **En cours est la projection personnelle de la continuité des réalités que le Profile a effectivement engagées et dont une suite pertinente existe encore pour lui.**

Sa question humaine peut être développée ainsi :

> **Pour ce que j’ai déjà engagé, puis-je avancer tranquille — et sinon, qu’est-ce qui reste réellement de mon côté ?**

En cours réduit la charge mentale liée aux réalités déjà engagées.

Il évite à la personne de devoir reconstruire elle-même une continuité à partir de Journey, Payment, Access, Requirement, Waitlist, Dossier, Project, Occurrence, documents, réservations ou validations dispersés.

---

# 4. Ce que En cours n’est pas

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

# 5. Réalité engagée

## 5.1. Définition

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

# 6. Admission dans En cours

Une réalité ne devient pas En cours simplement parce qu’elle existe dans le backend.

La règle conceptuelle est :

```text
PERSONAL_RELATION
∧ EFFECTIVE_PURSUIT
∧ CONTINUATION
∧ REMAINING_RELEVANCE
∧ LEGITIMATE_VISIBILITY
```

## 6.1. `PERSONAL_RELATION`

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

## 6.2. `EFFECTIVE_PURSUIT`

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

## 6.3. `CONTINUATION`

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

## 6.4. `REMAINING_RELEVANCE`

La suite doit encore avoir du sens pour la personne.

Un objet peut exister techniquement sans avoir encore de raison d’apparaître dans En cours.

## 6.5. `LEGITIMATE_VISIBILITY`

La projection respecte la visibilité, la confidentialité et l’autorité des propriétaires.

Composer plusieurs faits ne donne aucun nouveau droit de voir leur contenu.

---

# 7. En cours personnel et contexte Space

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

# 8. L’unité de composition : la Continuité En cours

## 8.1. Définition

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

# 9. Objet propriétaire ≠ unité UX

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

# 10. `CONTINUITY_BASIS`

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

# 11. `CONTINUITY_IDENTITY`

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

# 12. `HUMAN_CONTEXT`

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

# 13. Synthèse de continuité

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

# 14. Pas de `MOTION` canonique

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

# 15. Quatre dimensions fondamentales de compréhension

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

# 16. `SETTLED[]` — ce qui est déjà réglé

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

# 17. `MY_SIDE[]` — ce qui reste de mon côté

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

# 18. `ELSEWHERE[]` — ce qui continue ailleurs

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

# 19. `MAKOLO[]` — ce que Makolo prépare ou surveille

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

# 20. `SYSTEM_OR_TIME[]`

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

# 21. `NEXT[]` — ce qui vient ensuite

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

# 22. `HORIZON`

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

# 23. Blockers relatifs

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

# 24. Attente, blocage, risque et inconnue

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

# 25. Readiness

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

# 26. Contexte de connaissance

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

# 27. Trois notions de fin à ne pas confondre

Il faut distinguer :

```text
OWNER_COMPLETION
OUTCOME
CONTINUITY_EXIT
```

## 27.1. `OWNER_COMPLETION`

Un propriétaire termine son cycle.

Exemple :

```text
Payment = SUCCESS
```

## 27.2. `OUTCOME`

Un résultat humain pertinent est réellement atteint.

Exemples :

```text
billet obtenu
commande réellement remise
formation réellement suivie
visa réellement accordé
```

## 27.3. `CONTINUITY_EXIT`

Il ne reste plus de suite pertinente à représenter dans En cours.

Ces trois événements peuvent être séparés dans le temps.

---

# 28. `CONTINUITY_EXIT_CONDITION`

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

# 29. Une Continuité peut traverser plusieurs propriétaires

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

# 30. Relations entre Continuités

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

# 31. Relation ≠ fusion

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

# 32. Relations n-aires

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

# 33. Même contexte ≠ relation causale

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

# 34. Relation En cours → Situation Now

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

# 35. Composition globale de En cours

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

# 36. Pas de Top N conceptuel

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

# 37. Le budget runtime actuel n’est pas le contrat UX

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

# 38. Ordre de lecture

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

# 39. Regroupements humains

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

# 40. Calendrier En cours

Le header personnel peut exposer :

```text
En cours | Calendrier | Avatar
```

Le Calendrier répond à :

> **Quand les réalités déjà engagées vont-elles rencontrer mon temps ?**

Il n’est pas propriétaire des événements.

---

# 41. `TEMPORAL_FACTS`

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

# 42. Timestamp backend ≠ événement humain

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

# 43. Le Calendrier n’impose pas une grille mensuelle

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

# 44. Continuité ≠ Card

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

# 45. Ce que la racine doit permettre de comprendre

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

# 46. No Orphan Media

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

# 47. Média ≠ Proof automatique

Une image ou un document présenté dans En cours reste une représentation.

```text
aperçu du passeport
≠ Proof automatiquement
≠ Requirement satisfait automatiquement
```

L’admission comme Proof, Evidence ou satisfaction d’un Requirement appartient au propriétaire compétent.

---

# 48. Pas de progression générique

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

# 49. Timeline seulement si réelle

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

# 50. Progressive disclosure

La profondeur peut suivre :

```text
ROOT SUMMARY
    ↓
CONTINUITY COMPOSITION si utile
    ↓
OWNER DEPTH
```

## 50.1. Racine

Assez pour reconnaître et comprendre où en est la poursuite.

## 50.2. Composition de Continuité

Assez pour comprendre :

- ce qui est réglé ;
- ce qui reste ;
- ce qui continue ailleurs ;
- les relations utiles ;
- les documents ou médias utiles ;
- les prochains moments.

Cette profondeur n’est pas obligatoire pour chaque Continuité.

## 50.3. Propriétaire

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

# 51. En cours ne possède jamais l’action métier

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

# 52. Autorité

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

# 53. Feedback et niveau réel atteint

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

# 54. Local-first

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

# 55. Offline

Une Continuité peut rester utile offline.

Exemple :

> **Visa Canada**  
> Dernière mise à jour : hier 18:40  
> Dossier en examen lors de la dernière synchronisation.

Il est interdit de transformer une ancienne donnée en vérité actuelle.

Une action nécessitant une confirmation autoritative doit être présentée comme telle.

---

# 56. Refresh

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

# 57. Retour et continuité cognitive

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

# 58. Deep links

Une destination propriétaire importante peut rester adressable directement lorsque la sécurité le permet.

Un deep link doit :

1. restaurer l’authentification si nécessaire ;
2. vérifier la visibilité ;
3. vérifier l’autorité ;
4. ouvrir la profondeur correcte ;
5. fournir une alternative compréhensible si la destination n’est plus disponible.

La Continuité peut rester une projection intermédiaire sans devenir propriétaire de la route finale.

---

# 59. État vide

Un état réellement vide signifie :

> aucune Continuité personnelle actuellement admise.

La microcopy exacte n’est pas figée ici.

Une formulation possible est :

> Rien en cours pour le moment.

L’interface ne doit pas remplir ce vide par des suggestions artificielles.

Discover reste la surface des possibilités.

---

# 60. Continuités calmes

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

# 61. Frontière avec Now

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

# 62. Une Continuité peut exister sans Now

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

# 63. Une Situation Now n’est pas nécessairement En cours

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

# 64. Frontière avec Discover

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

# 65. Frontière avec Moi

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

# 66. Frontière avec Historique

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

# 67. Jour J

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

# 68. Pendant Jour J

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

# 69. `Métier` dans un Space

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

# 70. En cours et Métier ne fusionnent pas les contextes d’autorité

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

# 71. Runtime actuel : ce qui existe déjà

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

# 72. Runtime actuel : écarts avec le contrat mature

Le contrat mature met en évidence plusieurs écarts potentiels à traiter lors d’une future implémentation.

## 72.1. Composition par familles propriétaires

Le read model actuel parcourt encore plusieurs familles propriétaires.

La cible UX raisonne en Continuités humaines.

Cela ne justifie pas une nouvelle table.

Cela suggère de renforcer la composition et la déduplication lorsque les relations canoniques le permettent.

## 72.2. Budget de projection

La borne actuelle de la projection est un choix technique.

Elle ne doit pas devenir une limite conceptuelle du nombre de Continuités.

## 72.3. Access actif

Un Access actif n’appartient pas automatiquement à En cours.

Un droit durable sans poursuite active peut être mieux représenté dans Moi.

## 72.4. DRAFT

Un Dossier ou Project `DRAFT` n’est ni automatiquement engagé, ni automatiquement exclu.

Il faut vérifier s’il représente encore une poursuite vivante.

Ces points sont des écarts potentiels entre runtime actuel et contrat cible, pas des déclarations de bug en eux-mêmes.

---

# 73. Schéma conceptuel consolidé

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

# 74. Anti-features

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

# 75. Invariants consolidés

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

# 76. Exemples consolidés

## 76.1. Visa en attente normale

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

## 76.2. Visa avec action future de mon côté

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

## 76.3. Waitlist → Access

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

## 76.4. Paiement intermédiaire

```text
Commande de l’ordinateur

Paiement confirmé.
Le vendeur prépare la commande.

Ensuite
Remise prévue vendredi.
```

Le Payment est terminé.

La Continuité ne l’est pas.

## 76.5. Conflit entre deux Continuités

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

## 76.6. Capital de Moi utilisé par En cours

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

## 76.7. Space distinct du personnel

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

# 77. Ce qui reste volontairement ouvert

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

# 78. Doctrine d’implémentation future

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

# 79. Critères de sortie d’une future implémentation mature

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

# 80. Références de cadrage

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

# 81. Formulation finale

> **En cours est la surface personnelle Makolo qui rend intelligible la continuité de ce que la personne a réellement engagé. Son unité UX, la Continuité En cours, n’est ni une tâche, ni un Journey, ni un nouveau modèle métier : c’est la plus petite projection humaine cohérente permettant de comprendre où en est une poursuite, ce qui est déjà réglé, ce qui reste du côté de la personne, ce qui continue ailleurs, ce que Makolo prépare ou surveille et ce qui vient ensuite. Une Continuité peut traverser plusieurs propriétaires canoniques sans copier leurs vérités ; elle peut rester calme pendant longtemps, produire ponctuellement des Situations Now, entrer en Jour J lorsqu’une Occurrence devient réelle, puis sortir lorsque plus aucune suite pertinente ne subsiste. En cours n’invente ni urgence, ni progression, ni blocage, ni autorité. Il conserve la continuité nécessaire pour que la personne puisse avancer sans avoir à reconstruire elle-même le système.**
