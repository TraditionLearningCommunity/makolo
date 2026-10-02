# Makolo — UX Découvrir
## Contrat consolidé du champ personnel des possibilités

**Statut :** cadre UX conceptuel consolidé de travail  
**Portée :** expérience personnelle Web et mobile ; grammaire réutilisable par `Découvrir` dans un Space  
**Nom UX retenu :** `Découvrir`  
**Question humaine personnelle :** « Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ? »  
**Question humaine Space :** « Qu’est-ce qui pourrait nous aider à avancer ? »  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »  
**Base runtime vérifiée avant consolidation :** `main@97b2017b5df0a94e3276858c28e51e916b185c0b`

---

# 1. Objet du document

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

# 2. Place de Découvrir dans Makolo

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

# 3. Définition de Découvrir

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

# 4. Ce que Découvrir n’est pas

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

# 5. Pertinence : frontière avec Molongo / intelligence

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

# 6. Pas de score global UX

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

# 7. Possibilité

## 7.1. Définition

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

# 8. Possibilité ≠ propriétaire canonique

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

# 9. `POSSIBILITY_BASIS`

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

# 10. `POSSIBILITY_IDENTITY`

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

# 11. Même titre ≠ même Possibilité

Deux résultats portant le même titre ne sont pas automatiquement la même réalité.

La fusion d’identité ne doit jamais reposer uniquement sur :

- titre similaire ;
- résumé similaire ;
- date proche ;
- image identique ;
- proximité textuelle.

La résolution appartient aux contrats canoniques / intelligence adaptés.

---

# 12. Plusieurs sources ≠ plusieurs Possibilités

Une même possibilité peut être soutenue par :

- une source officielle ;
- une page du porteur ;
- un PDF ;
- une observation ;
- une connaissance résolue.

Ces sources enrichissent la provenance.

Elles ne créent pas automatiquement plusieurs unités UX.

---

# 13. Résultat possible

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

# 14. `EXPLORATION_CONTEXT`

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

# 15. Search ≠ Exploration Context complet

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

# 16. `POSSIBILITY_FIELD`

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

# 17. Champ initial et expansion

Le champ initial peut être borné par l’amont pertinent.

Si rien d’utile n’est disponible, l’UX peut proposer :

> **Explorer plus largement**

Cette action exprime une intention humaine d’élargissement.

Elle ne fixe pas le mécanisme algorithmique exact.

L’UX ne relâche jamais silencieusement les critères simplement pour remplir l’écran.

---

# 18. `EXPLORATION_GROUP`

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

# 19. Plusieurs placements de la même Possibilité

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

# 20. La racine Découvrir

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

# 21. Header

Le header personnel de référence est :

```text
Makolo | Recherche | Filtres / contexte | Avatar
```

Notifications et Conversations ne sont pas au premier niveau.

Découvrir doit rester un mode exploratoire protégé des obligations quotidiennes.

---

# 22. Surface principale

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

# 23. Grammaire contextuelle

La même structure interne de Possibilité peut produire des présentations très différentes.

## Transport

```text
origine
destination
horaire
durée
prix
```

## Événement

```text
expérience
date
lieu
```

## Formation

```text
programme
format
durée
session
```

## Funding

```text
ce qui peut être financé
fenêtre
couverture
conditions importantes
```

## Obtention

```text
cible
mode
prix / conditions
disponibilité
```

Backend générique.

Métier visible contextuel.

---

# 24. Composants partagés

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

# 25. Possibilité ≠ Card

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

# 26. Médias

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

# 27. No Orphan Content / Media

Chaque contenu doit répondre à :

> **Quelle Possibilité cela m’aide-t-il à comprendre ou explorer ?**

Une vidéo sans contexte d’action n’a pas vocation à devenir un post Discover générique.

Presentation représente les réalités.

Elle ne possède pas un feed de contenu.

---

# 28. Facts et Assessment

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

# 29. `FAVORABLE`

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

# 30. `LIMITING`

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

# 31. `UNKNOWN`

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

# 32. Fraîcheur et connaissance

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

# 33. Variantes

Une Possibilité peut exposer des variantes lorsque cette structure est réellement fournie.

Exemple :

```text
Formation X
├── session matin
└── session soir
```

L’UX n’infère pas elle-même les variantes à partir de simples similarités.

---

# 34. Variante ≠ alternative

Conceptuellement :

```text
VARIANT
→ autre réalisation suffisamment proche de la même option

ALTERNATIVE
→ autre option indépendante dans le même contexte d'exploration
```

La frontière exacte peut être fournie par le domaine ou l’amont.

---

# 35. Relations entre Possibilités

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

# 36. Relation ≠ fusion

Deux possibilités reliées restent distinctes lorsqu’elles peuvent être considérées, choisies ou rejetées indépendamment.

Même objectif n’implique pas même identité.

Même porteur n’implique pas même identité.

Même contexte n’implique pas causalité.

---

# 37. Relations n-aires

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

# 38. Search

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

# 39. Filtres

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

# 40. Progressive disclosure des filtres

La racine ne doit pas afficher des dizaines de contrôles.

Les filtres secondaires peuvent être placés :

- en profondeur ;
- dans un panneau ;
- dans une bottom sheet mobile.

Les filtres actifs doivent rester visibles lorsqu’ils changent réellement le champ.

---

# 41. Carte

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

# 42. Carte seulement si utile

La carte apparaît lorsque la géographie aide réellement à comprendre ou choisir.

Elle peut être utile pour :

- événements ;
- transports ;
- lieux ;
- services physiques ;
- ressources locales.

Elle peut être inutile pour certaines possibilités numériques ou abstraites.

---