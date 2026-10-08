# Makolo — Space Métier `generic` / **Activités**
## Contrat UX consolidé — N1, N2/N3, hiérarchie, représentations, états, adaptive, local-first et handoffs

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence pour l’archétype Space `generic`  
**Porte visible :** **Activités**  
**Contexte acteur :** Space  
**Viewer :** Profile authentifié agissant explicitement au nom du Space  
**Portée :** Web, mobile Flutter, tablette/desktop adaptatif, Presentation, projections serveur et continuité locale  
**Nature :** contrat UX, de projection et d’implémentation ; ne crée aucun nouveau domaine métier  
**Promesse produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 0. Objet

Ce document fixe la manière dont la porte **Métier** doit être visible et utilisable pour un Space dont l’archétype est :

```text
generic
```

Le libellé visible primaire est :

```text
Activités
```

Le contrat part du cadre déjà fixé pour l’archétype `generic` :

```text
Activities
à préparer
à venir
en cours
demandes associées
lieux
terminées
```

Les verticales utilisées apparaissent seulement lorsqu’elles existent réellement.

Un Space `generic` ne reçoit pas artificiellement une verticale dominante.

L’état vide ne crée jamais une Activity fictive.

Ce document ne définit pas une nouvelle « verticale générique ».

Il fixe comment les vérités déjà détenues par :

```text
Activity
Occurrence
Journey
Requirement
Readiness
Access
Capacity
Commerce
Service
Transport
Obtention
Funding
Geography
Presentation
Authorization
```

peuvent être rendues intelligibles dans la porte **Activités**.

---

# 1. Question humaine

La porte **Activités** répond à :

> **Qu’est-ce que nous faisons réellement, qu’est-ce qui se prépare, qu’est-ce qui arrive et qu’est-ce qui continue ?**

Elle ne demande pas :

> Quels objets Makolo possédons-nous ?

Elle ne demande pas non plus :

> Quelles fonctionnalités pouvons-nous ouvrir ?

La surface doit permettre, en quelques secondes, de comprendre :

```text
ce que le Space fait
+
ce qui est actuellement vivant
+
ce qui arrive
+
ce qui a besoin de préparation
+
où entrer pour agir
```

---

# 2. Pourquoi `generic` existe

`generic` ne signifie pas :

```text
incomplet
sans métier
sans spécialisation
fourre-tout
```

`generic` signifie :

> **le Space n’a pas un archétype métier plus spécifique suffisamment dominant pour imposer une grammaire comme Transport, Programmes, Prestations ou Commerce.**

Le Space peut néanmoins avoir :

- des Activities ;
- des Occurrences ;
- des demandes ;
- des lieux ;
- des événements ;
- des services ;
- des offres ;
- du financement ;
- des réalités d’obtention ;
- des relations ;
- des groupes ;
- des accès ;
- d’autres domaines réellement utilisés.

La porte **Activités** doit donc rester très lisible tout en sachant révéler progressivement cette diversité.

---

# 3. Principe fondamental

```text
GENERIC
≠
TOUT MAKOLO
```

et :

```text
ACTIVITÉS
≠
LISTE DE MODÈLES BACKEND
```

La porte ne doit pas devenir :

```text
Activities
Occurrences
Journeys
Offers
Orders
Payments
Access
Capacity
Requirements
Resources
CRM
Groups
...
```

comme menu de modules.

Elle doit rester organisée par la réalité vécue du Space.

---

# 4. Personnalité UX

La personnalité de `Activités` est :

> **travail réel + continuité lisible + diversité maîtrisée**

Elle doit donner une impression :

- structurée ;
- calme ;
- productive ;
- flexible ;
- non bureaucratique ;
- non technique ;
- suffisamment dense pour travailler ;
- suffisamment simple pour ne pas devenir un ERP.

La densité cible est moyenne.

La racine peut devenir plus dense lorsqu’un Space opère beaucoup de réalités, mais la hiérarchie doit toujours protéger la compréhension.

---

# 5. Relation avec les autres portes

## 5.1. Maintenant

`Maintenant` répond :

> Qu’est-ce qui mérite notre attention maintenant ?

`Activités` répond :

> Qu’est-ce que nous faisons réellement, et où en est ce monde de travail ?

Une Activity peut être visible dans `Activités` sans produire de Situation Now.

Une conséquence importante issue d’une Activity peut remonter dans Maintenant.

---

## 5.2. Découvrir

`Découvrir` montre des possibilités.

`Activités` montre des réalités effectivement portées, opérées, engagées ou structurées par le Space.

Une possibilité ne devient pas une Activity seulement parce qu’elle a été vue.

---

## 5.3. Nous

`Nous` montre :

- identité ;
- équipe ;
- responsabilités ;
- relations ;
- confiance ;
- organisation.

`Activités` montre ce que le Space fait.

---

## 5.4. Piloter

`Piloter` peut montrer :

- tendances ;
- écarts ;
- volumes ;
- analytics ;
- performance.

`Activités` ne devient pas une page KPI.

---

## 5.5. Jour J / Live

Une Occurrence suffisamment actuelle peut ouvrir Jour J.

`Activités` reste la porte de continuité métier.

Jour J devient la profondeur d’accomplissement d’une Occurrence, pas un onglet permanent d’Activités.

---

# 6. Actor Context

Le contexte canonique est :

```text
ACTOR_CONTEXT
→ Space
```

Le Viewer reste :

```text
VIEWER
→ Profile
```

Exemple :

```text
Avatar = Jean
Actor Context = Fondation Upendo
Métier = Activités
```

Le Viewer peut disposer de responsabilités ou d’autorité sur seulement une partie des Activities.

La surface doit donc être filtrée serveur.

---

# 7. Authority et responsabilité

Une responsabilité active peut réduire le champ affiché.

Elle ne crée jamais de Permission.

Exemple :

```text
Toutes mes responsabilités
→ ensemble des réalités visibles selon autorité

Coordination terrain
→ subset pertinent

Finance
→ subset pertinent
```

Mais :

```text
responsibility filter
≠ authority expansion
```

Une Activity non autorisée ne devient jamais visible parce qu’un filtre la mentionne.

---

# 8. Grammaire globale N1

La racine candidate est :

```text
ACTIVITÉS
│
├── HEADER
│
├── CONTEXT
│   ├── Space
│   └── responsibility lens
│
├── PRIMARY CONTINUITY
│   ├── À préparer ?
│   ├── À venir ?
│   ├── En cours ?
│   ├── Demandes ?
│   └── autres sections réellement justifiées
│
├── PORTFOLIO
│   └── Activities durables / publiées / pertinentes
│
├── PLACES ?
├── SPECIALIZED REALITIES ? 
│   └── seulement si Operational Footprint réel
│
├── HISTORY ENTRY
│
└── DEPTH
    ├── Activity N2
    ├── Occurrence N2
    ├── Request / Journey owner
    ├── vertical owner
    ├── Jour J
    └── Live
```

Cette grammaire est UX.

Elle n’impose pas une réponse API finale.

---

# 9. N1 — Header

Le header principal suit la grammaire Space :

```text
Makolo | Space / Activités | Recherche / filtres utiles | Avatar
```

Sur Compact :

```text
Makolo
Fondation Upendo · Activités
[search] [filter] [avatar]
```

Sur Medium/Wide :

```text
Makolo | Fondation Upendo / Activités | Toutes mes responsabilités | Recherche | Avatar
```

Le header ne doit pas contenir des raccourcis vers tous les domaines.

---

# 10. N1 — Ordre de lecture

La racine doit suivre une logique :

```text
1. ce qui demande préparation ou conduite
2. ce qui arrive
3. ce qui est actuellement en réalisation
4. le portefeuille d’Activities
5. les profondeurs structurelles ou spécialisées pertinentes
6. historique
```

Ce n’est pas un ordre universel rigide.

Si aucune continuité n’existe, le portefeuille peut devenir dominant.

Si une Activity vient d’être créée mais demande préparation, sa continuité peut remonter.

---

# 11. Continuité opérationnelle

La racine peut présenter des sections comme :

```text
À préparer
À venir
En cours
Demandes
Terminées
```

mais seulement si ces mots sont vrais et utiles.

Le contrat interdit de fabriquer artificiellement toutes les sections pour chaque Space.

Exemple :

```text
Activités

À préparer
2

À venir
4

En cours
1

Toutes les activités
7
```

peut être légitime.

Mais :

```text
À préparer 0
À venir 0
En cours 0
Bloqué 0
Terminées 0
```

comme dashboard permanent ne l’est pas.

---

# 12. Portfolio d’Activities

La structure durable peut être montrée sous :

```text
Toutes les activités
```

ou un libellé plus naturel selon contexte.

Une Activity visible peut représenter :

- une activité durable ;
- une offre de participation ;
- une initiative ;
- une opération structurée ;
- une possibilité portée par le Space ;
- un service générique ;
- autre réalité dont Activity est l’enveloppe canonique.

La représentation doit parler du contenu humain.

---

# 13. Représentation d’une Activity

Une Activity ne doit pas apparaître comme :

```text
Activity #4a6c...
status=published
vertical=generic
```

Elle doit ressembler à :

```text
Atelier communautaire du samedi

Rencontres hebdomadaires pour accompagner
les jeunes du quartier.

Prochaine date
Samedi · 10:00

[Ouvrir]
```

Si aucun timing n’existe :

```text
Programme d’accompagnement local

Activité permanente

[Ouvrir]
```

---

# 14. Activity row vs card

La racine privilégie la row ou une unit compacte.

Card plus riche uniquement lorsqu’un média ou contexte spatial/visuel apporte réellement de la compréhension.

Candidate row :

```text
┌─────────────────────────────────────────┐
│ Atelier communautaire                   │
│ Samedi · 10:00                          │
│ 2 éléments à préparer                   │
│                                    ›    │
└─────────────────────────────────────────┘
```

Candidate card contextuelle :

```text
[media utile]

Festival local
12 octobre
Place de la Gare

Préparation en cours
```

Mais aucune Activity ne reçoit une image décorative obligatoire.

---

# 15. N1 — À préparer

Une entrée `À préparer` signifie qu’une réalité du Space n’est pas encore suffisamment prête pour sa prochaine étape.

La surface ne doit pas inventer un Readiness parallèle.

Sources possibles :

- Activity DRAFT ;
- Occurrence DRAFT ;
- Journey en préparation ;
- Requirement manquant ;
- ressource attendue ;
- configuration réellement nécessaire ;
- autre état propriétaire.

Le texte visible doit être humain.

Exemple :

```text
Atelier emploi · 18 octobre

Il manque le lieu.

[Compléter]
```

Pas :

```text
readiness=false
```

---

# 16. N1 — À venir

`À venir` concerne principalement des réalisations temporelles futures.

Exemple :

```text
Atelier emploi
18 octobre · 09:00
Maison des jeunes
```

Une Activity permanente ne devient pas « à venir » simplement parce qu’elle est publiée.

`À venir` dépend d’Occurrences ou faits temporels pertinents.

---

# 17. N1 — En cours

`En cours` dans un Space generic signifie :

> une réalité métier réellement engagée ou en réalisation dans ce Space.

Il ne s’agit pas d’une copie de la surface personnelle `En cours`.

Le vocabulaire peut varier selon le type réel.

Une Activity publiée n’est pas automatiquement « En cours ».

Une Journey active liée au travail du Space peut alimenter une continuité si l’autorité le permet.

---

# 18. N1 — Demandes

Les demandes associées peuvent apparaître seulement lorsque le Space utilise réellement un workflow de demandes.

Le libellé visible doit suivre le contexte :

```text
Demandes
Inscriptions
Candidatures
Réservations
Demandes d’accompagnement
```

selon la réalité.

Le generic ne force pas le mot `Journey`.

---

# 19. N1 — Lieux

Les lieux peuvent apparaître lorsque la géographie structure réellement l’activité.

Exemples :

```text
Lieux
Maison des jeunes
Centre Kimbangu
Terrain municipal
```

Un simple `Place` technique non pertinent n’a pas besoin d’être mis en avant.

La carte est optionnelle.

---

# 20. Operational Footprint

Le generic peut utiliser des verticales réelles.

Exemple :

```text
Space generic
├── event
├── service
└── obtention
```

La porte Activités peut rendre ces réalités visibles.

Mais :

```text
Operational Footprint
≠ navigation technique
```

L’utilisateur peut voir :

```text
Événements
Prestations
Distributions
```

si ces réalités existent réellement.

Il ne voit pas nécessairement :

```text
event
service
obtention
```

---

# 21. Une verticale spécialisée n’efface pas Activités

Un Space generic peut avoir une Activity Transport ou Service.

Cela ne transforme pas automatiquement son archétype.

L’archétype est le centre de gravité durable.

Le footprint exprime les domaines réellement utilisés.

Donc :

```text
generic Space
+
1 Activity Transport
≠ transport_operator
```

La porte reste **Activités**, mais la profondeur Transport peut employer sa propre grammaire.

---

# 22. N2 — Activity

La profondeur principale d’une Activity doit être structurée autour de la réalité humaine.

Candidate :

```text
← Atelier emploi

Atelier emploi

Accompagnement collectif vers l’emploi
pour les jeunes du quartier.

État
Publié

Prochaine réalisation
18 octobre · 09:00

Préparation
Lieu confirmé
Ressources à compléter

Demandes
12

Accès / capacité
si réellement utiles

[Actions contextuelles]
```

N2 ne doit pas montrer tous les domaines possibles.

---

# 23. N2 — Composition

Une Activity N2 peut composer :

```text
identity
purpose
description
timing
occurrences
place
readiness
requests
resources
requirements
capacity
access
commerce
vertical-specific facts
owner actions
```

mais uniquement selon présence et autorité.

Aucune section vide n’est obligatoire.

---

# 24. N2 — Occurrences

Une Activity peut avoir plusieurs Occurrences.

Exemple :

```text
Prochaines dates

18 oct · 09:00
25 oct · 09:00
1 nov · 09:00
```

Sélectionner une Occurrence ouvre une profondeur dédiée.

Une Occurrence peut avoir :

- date ;
- heure ;
- lieu ;
- état ;
- préparation ;
- Capacity ;
- Access ;
- Jour J ;
- Live ;
- autres vérités owner-backed.

---

# 25. N2 — Occurrence

Candidate :

```text
← Atelier emploi

18 octobre · 09:00

Maison des jeunes

Préparation
Tout est prêt

Participants attendus
si autorisé

Accès
si pertinent

[Ouvrir Jour J]
```

Le bouton Jour J n’existe que lorsque le serveur établit son admissibilité.

---

# 26. N2 — demandes et journeys

Une demande ne doit pas afficher un modèle `Journey` comme concept utilisateur.

Exemple :

```text
Demande de participation

Aline M.
Reçue hier

État
À examiner

[Examiner]
```

Si le workflow est une inscription :

```text
Inscription
```

Si c’est une réservation :

```text
Réservation
```

Le vocabulaire suit le propriétaire.

---

# 27. N3 — owner depth

N3 est la profondeur où l’UX peut devenir plus précise.

Exemples :

```text
Requirement manquant
Document à examiner
Access à contrôler
Capacity à configurer
Payment à vérifier
Journey à traiter
```

Mais le titre doit rester humain.

Préférer :

```text
Justificatif d’identité
```

à :

```text
RequirementAssessment
```

---

# 28. Création contextuelle

La création visible de base est :

```text
Nouvelle activité
```

uniquement si autorisée.

La surface ne doit pas ouvrir un méga-menu :

```text
Créer Activity
Créer Occurrence
Créer Journey
Créer Capacity
Créer Access
Créer Requirement
...
```

Après ouverture d’une Activity, des actions contextuelles peuvent apparaître :

```text
Ajouter une date
Ajouter un lieu
Préparer les inscriptions
Configurer l’accès
```

si le backend les autorise.

---

# 29. Empty state

Un Space generic sans Activity doit rester honnête :

```text
Activités

Aucune activité pour le moment.
```

Si capability :

```text
[Créer une première activité]
```

Sinon :

```text
Aucune activité visible dans votre périmètre.
```

Le système ne doit jamais injecter une Activity fictive pour « montrer » l’interface.

---

# 30. Calm state

Le Space peut avoir des Activities mais aucune continuité actuelle.

Exemple :

```text
Activités

Aucune activité ne demande de préparation maintenant.

Toutes les activités
Atelier emploi
Rencontres communautaires
Programme d’accompagnement
```

Ceci est un état normal.

---

# 31. Search

La recherche spécialisée répond :

> **Rechercher dans les activités de ce Space**

Elle peut chercher :

- Activity ;
- Occurrence ;
- lieu ;
- demande ;
- bénéficiaire si autorisé ;
- autres réalités exposées légitimement.

Les résultats parlent humainement.

---

# 32. Filtres

Filtres possibles :

```text
À préparer
À venir
En cours
Terminées
Par lieu
Par période
Par responsabilité
Par type humain
```

Le type humain peut être :

```text
Événements
Prestations
Distributions
Ateliers
```

si ces catégories sont réellement défendables.

Pas :

```text
vertical=service
workflow=registration
status=PUBLISHED
```

comme vocabulaire primaire.

---

# 33. Hiérarchie perceptive

Candidate :

```text
CURRENT WORK / NEXT REALITY        P2/P3
ACTION LEGITIME                   P2/P3

ACTIVITY IDENTITY                 P2
TIME / PLACE / STATE              P1/P2

SUPPORTING METADATA               P1
TECHNICAL DETAILS                 P0
```

Sur la racine, aucun KPI ne doit devenir P3.

---

# 34. Priority sans ranking opaque

L’ordre peut privilégier :

```text
nécessité de préparation
→ proximité temporelle
→ continuité active
→ responsabilité
→ stabilité
```

mais il doit rester explicable.

Pas de score utilisateur visible sans sens.

Pas de classement de « popularité ».

---

# 35. États visuels

La surface doit définir :

```text
content
calm
empty
loading
refreshing
offline
stale
partial
local_error
permission_loss
no_filter_match
```

---

# 36. Loading

Préférer :

```text
contenu connu
+
rafraîchissement discret
```

à :

```text
contenu
→ vide
→ skeleton
→ contenu
```

La grammaire d’Activités doit rester reconnaissable pendant refresh.

---

# 37. Offline

Le client peut conserver une projection locale sûre.

Exemple :

```text
Activités

Dernière mise à jour · hier 18:42

Atelier emploi
18 octobre · 09:00
```

Mais il ne doit pas transformer une ancienne donnée en vérité Live.

---

# 38. Stale

Un état stale doit exprimer la fraîcheur seulement lorsqu’elle compte.

Exemple :

```text
Informations datant de 2 h
```

Pas besoin de badge sur chaque row.

Les actions sensibles doivent revalider le serveur.

---

# 39. Partial failure

Une section peut échouer sans faire tomber toute la porte.

Exemple :

```text
Activités
✓ portefeuille visible
✓ prochaines dates visibles

Demandes
Impossible d’actualiser.
[Réessayer]
```

Le reste reste utilisable.

---

# 40. Permission loss

Si l’autorité change :

- retirer immédiatement les actions sensibles ;
- revalider la profondeur ;
- éviter les fuites de données ;
- expliquer humainement la limite ;
- conserver autant que possible le contexte non sensible.

---

# 41. Compact

Sur Compact :

```text
single pane
vertical sections
rows compactes
depth = navigation
bottom nav visible
```

Exemple :

```text
Activités

À préparer
Atelier emploi         ›

À venir
Forum local            ›

Toutes les activités
...
```

---

# 42. Medium

Medium peut utiliser :

```text
field
+
light preview
```

mais uniquement si cela réduit la perte de contexte.

Candidate :

```text
Activités            | aperçu
liste                | Activity sélectionnée
```

---

# 43. Wide

Wide peut utiliser :

```text
NAV
+
FIELD
+
FOCUS N2
```

après sélection.

La racine non sélectionnée peut rester centrée et modérément dense.

Le grand écran n’autorise pas automatiquement l’exposition de N2/N3.

---

# 44. Very Wide

Very Wide n’est pas une excuse pour créer :

- KPI grid ;
- dashboard ;
- colonnes vides ;
- panels analytics ;
- tableau ERP.

L’espace supplémentaire sert d’abord à préserver contexte + profondeur.

---

# 45. Adaptive conservation

Lors de :

```text
Compact → Medium
Medium → Wide
rotation
resize
```

préserver autant que possible :

- surface ;
- Activity sélectionnée ;
- profondeur ;
- query ;
- filtres ;
- responsabilité ;
- scroll ;
- brouillon.

---

# 46. Back

Back depuis N2 retourne à la racine avec :

- scroll préservé ;
- filtre préservé ;
- query préservée ;
- sélection précédente si utile ;
- section conservée.

Pas de retour brutal en haut de page.

---

# 47. Resume

Après reprise de l’application :

1. montrer le snapshot local sûr ;
2. revalider en arrière-plan ;
3. retirer les réalités devenues non autorisées ;
4. actualiser les vérités sensibles ;
5. préserver le contexte d’utilisateur.

---

# 48. Deep links

Un deep link vers une Activity :

```text
Makolo
→ Space
→ Activités
→ Activity
```

doit restaurer le bon Actor Context.

Un deep link ne doit jamais contourner l’autorité.

---

# 49. Jour J handoff

Une Occurrence peut exposer :

```text
[Ouvrir Jour J]
```

quand le serveur l’admet.

Le handoff conserve :

```text
Makolo
+
Space
+
Activity
+
Occurrence
```

Après Jour J, retour vers la même réalité métier.

---

# 50. Live handoff

Live appartient à Jour J.

Activités ne propose pas un bouton global :

```text
Live
```

sans Occurrence.

Plusieurs Occurrences peuvent être simultanément actives.

Le Space entier ne devient jamais « Live ».

---

# 51. Now handoff

Une réalité Activités peut produire une Situation Now.

Exemple :

```text
Atelier emploi · demain
Lieu non confirmé.
[Choisir un lieu]
```

Mais Activités reste la source de contexte métier, Now la projection d’attention.

---

# 52. Découvrir handoff

Découvrir peut trouver :

```text
un lieu
une ressource
un partenaire
une opportunité
```

utile à une Activity.

Le retour doit pouvoir conserver la relation avec l’Activity qui a motivé l’exploration.

---

# 53. Mark handoff

Makolo Mark peut comprendre :

> Ajoute une activité samedi à 10 h.

si le contexte Space et l’autorité sont suffisamment établis.

Il doit passer au bon owner.

Il ne crée pas d’autorité.

---

# 54. Nous handoff

Une Activity peut conduire vers :

- responsable ;
- équipe ;
- partenaire ;
- groupe.

Mais ces réalités restent propriétaires de `Nous` ou relations appropriées.

Activités ne devient pas annuaire.

---

# 55. Places

Un lieu peut être montré comme contexte d’Activity ou d’Occurrence.

Une profondeur Lieu peut agréger les réalités autorisées.

Mais :

```text
Place
≠ Activity
```

La carte n’est pas obligatoire.

---

# 56. Média

No Orphan Media s’applique.

Un média est admissible s’il aide à :

- reconnaître une Activity ;
- comprendre un lieu ;
- préparer une réalisation ;
- montrer une ressource ;
- confirmer un contexte.

Pas de feed média.

Pas de carousel automatique sans fonction.

---

# 57. Historique

Les éléments terminés peuvent être accessibles depuis :

```text
Terminées
Historique
```

selon la profondeur.

Historique n’est pas un onglet primaire.

Une Activity archivée ne doit pas polluer le champ courant.

---

# 58. Terminées

`Terminées` peut contenir :

- Occurrences terminées ;
- Activities achevées ;
- Journeys accomplis si pertinents ;
- autres owner states.

Mais la terminaison visible doit refléter le propriétaire.

---

# 59. Activity ≠ Occurrence

Invariant UX :

```text
Activity
= possibilité structurée / réalité durable

Occurrence
= réalisation temporelle concrète
```

Ne pas afficher :

```text
Atelier emploi
Atelier emploi
Atelier emploi
Atelier emploi
```

sans expliquer si l’on regarde l’Activity ou ses dates.

---

# 60. Activity published ≠ active now

Une Activity `published` ne signifie pas :

```text
En cours maintenant
```

Elle peut être disponible sans réalisation actuelle.

La surface doit éviter ce glissement.

---

# 61. Occurrence scheduled ≠ Jour J

Une Occurrence planifiée n’est pas automatiquement Jour J.

Le serveur décide l’admission.

Le client ne dérive pas Jour J depuis l’horloge seulement.

---

# 62. Demande ≠ Activity

Une demande appartient au parcours d’une personne ou organisation.

Elle ne doit pas être promue en Activity distincte sauf justification métier réelle.

---

# 63. Lieu ≠ continuité

Un lieu actif ou disponible ne devient pas une entrée En cours simplement parce qu’il existe.

Il structure ou contextualise les Activities.

---

# 64. Request queue

Lorsque beaucoup de demandes existent, la racine peut montrer :

```text
Demandes
12 à examiner
```

puis ouvrir une queue spécialisée.

La racine ne doit pas lister des centaines de personnes.

---

# 65. Capacity

Capacity apparaît uniquement quand `combien ?` est utile.

Exemple :

```text
24 / 30 places
```

Mais Activités ne crée pas un indicateur Capacity global.

---

# 66. Access

Access apparaît seulement lorsqu’un droit compte pour l’Activity/Occurrence.

Le droit reste propriétaire du domaine Access.

Un Access actif ne devient pas automatiquement une section globale.

---

# 67. Payment

Payment apparaît seulement dans une Activity qui l’utilise.

Activités ne devient pas Finance.

Un Payment échoué peut être visible comme blocker ou remonter dans Now selon conséquence.

---

# 68. Commerce

Si des Offers/Orders existent réellement dans un Space generic, Activités peut montrer une entrée contextualisée.

Exemple :

```text
Atelier premium
3 commandes à traiter
```

La profondeur peut ouvrir le propriétaire Commerce.

Mais la porte primaire reste Activités.

---

# 69. Service

Si une Activity utilise Service :

```text
Accompagnement visa
6 dossiers en traitement
```

peut être visible.

La profondeur Service suit sa grammaire Prestations/Service.

Le generic ne duplique pas Service.

---

# 70. Transport

Si une Activity utilise Transport :

```text
Navette événement
Départ 07:30
```

peut apparaître.

Une profondeur transport peut exposer Jour J selon owner.

Le Space ne devient pas transport_operator automatiquement.

---

# 71. Obtention

Si une Activity est une Obtention réelle :

```text
Distribution de kits scolaires
```

Activités peut la représenter selon son résultat humain.

Offer, Order et Payment restent optionnels et owner-backed.

---

# 72. Funding

Funding peut être :

- une Activity ;
- une possibilité ;
- une continuité ;
- une situation de pilotage.

Son placement dépend du contexte réel.

Activités ne doit pas transformer tout Funding en entrée permanente.

---

# 73. Progressive disclosure

Règle :

```text
N1
→ comprendre le champ

N2
→ comprendre une réalité

N3
→ agir avec le propriétaire
```

La racine ne doit pas exposer d’emblée :

- Requirements détaillés ;
- Access secrets ;
- Payment ledger ;
- Journey steps ;
- configuration technique ;
- logs.

---

# 74. P1 / P2 / P3

N1 :

```text
SECTION MEANING        P2
CURRENT IMPORTANT ITEM P2
PRIMARY ACTION         P2/P3 si nécessaire
METADATA               P1
```

N2 :

```text
ACTIVITY / OCCURRENCE IDENTITY   P2
CURRENT MEANING / BLOCKER        P3
NEXT LEGITIMATE ACTION           P2/P3
SUPPORTING DETAILS               P1
```

Pas deux P3 concurrents.

---

# 75. Golden candidates

## G-ACT-01 — Compact / Content

Fixture :

```text
Space: Fondation Upendo

À préparer
Atelier emploi
Lieu à confirmer

À venir
Forum local
18 octobre

Toutes les activités
Programme mentorat
Rencontres quartier
```

Viewport :

```text
360 × 800
430 × 932
```

---

## G-ACT-02 — Compact / Empty

```text
Activités

Aucune activité pour le moment.

[Créer une première activité]
```

CTA uniquement si autorisé.

---

## G-ACT-03 — Compact / Calm

```text
Activités

Aucune activité ne demande de préparation maintenant.

Toutes les activités
...
```

---

## G-ACT-04 — Compact / Offline

Snapshot présent.

Fraîcheur visible seulement si utile.

Aucune vérité Live inventée.

---

## G-ACT-05 — Medium / Activity selected

```text
FIELD              | PREVIEW
Activities         | Atelier emploi
                   | prochain rendez-vous
```

---

## G-ACT-06 — Wide / N2

```text
NAV | ACTIVITÉS       | ACTIVITY
    | rows            | synthesis
    | sections        | occurrences
    |                 | preparation
```

---

## G-ACT-07 — Activity with specialized vertical

Fixture :

```text
Distribution de kits
vertical obtention réelle
```

N1 reste Activités.

N2 emploie vocabulaire humain de distribution.

---

## G-ACT-08 — Multiple Occurrences

Une Activity avec plusieurs dates.

N1 ne duplique pas l’Activity comme si chaque date était une nouvelle activité.

---

## G-ACT-09 — Permission-limited Viewer

Viewer voit uniquement Activity mandatée.

Aucune fuite du portfolio global.

---

## G-ACT-10 — textScale 1.6

La hiérarchie reste claire.

Aucun truncation destructive.

Actions restent accessibles.

---

# 76. Accessibility

La surface doit :

- fonctionner avec text scaling ;
- exposer une hiérarchie sémantique ;
- garder des targets tactiles suffisantes ;
- ne pas encoder l’état uniquement par couleur ;
- annoncer loading/refresh sans bruit excessif ;
- respecter Reduce Motion ;
- préserver ordre de focus logique ;
- rendre les actions disabled/hidden compréhensibles.

---

# 77. Couleurs

Utiliser la palette Makolo :

```text
#5232DB
#2B176E
#FF704D
#FAF7F5
#0F172A
```

Mais la couleur ne doit pas créer de « niveaux de gravité » non soutenus par le métier.

---

# 78. Motion

Motion sert à expliquer :

- ouverture N2 ;
- insertion d’une nouvelle réalité ;
- retour ;
- changement de filtre ;
- confirmation locale.

Pas d’animation décorative qui retarde l’action.

---

# 79. Local-first

Le client peut conserver :

- Activities synchronisées ;
- Occurrences connues ;
- lieux connus ;
- projection de continuité ;
- drafts ;
- préférences UX.

Mais il ne peut pas décider localement :

- autorité ;
- Permission ;
- Capacity partagée actuelle ;
- Access valide actuel ;
- état de Payment partagé ;
- Jour J admission ;
- Live truth.

---

# 80. Mutation offline

Les mutations doivent suivre les classes de risque local-first.

Exemples potentiellement préparables localement :

- draft textuel ;
- préférences ;
- sélection ;
- brouillon Activity si architecture le permet.

Actions sensibles :

- publication ;
- accès ;
- paiement ;
- capacity ;
- autorité ;
- action multi-acteur ;
- validation ;

nécessitent confirmation distante.

---

# 81. Feedback

Préférer :

> **Activité créée. Il reste à ajouter une date.**

à :

> Success.

Préférer :

> **Date ajoutée. Elle sera synchronisée dès que la connexion revient.**

uniquement si ce niveau de confirmation est réellement garanti.

---

# 82. Erreur

Une erreur importante répond :

1. qu’est-ce qui n’a pas fonctionné ?
2. qu’est-ce qui a été conservé ?
3. que puis-je faire maintenant ?

---

# 83. API actuelle

Le runtime courant expose la projection Space Métier via la projection de travail Space.

Le contrat UX ne doit pas forcer le client à reconstruire la racine en appelant toutes les tables séparément.

La projection peut fournir :

```text
space
archetype
primary_business_label
authority
responsibility
operational_footprint
sections
links
capabilities
```

Le client présente cette projection.

Il ne réinterprète pas l’autorité.

---

# 84. Sections runtime actuelles

Le runtime actuel utilise des buckets techniques :

```text
preparation
upcoming
active
blocked
completed
```

Ces buckets sont utiles à la projection.

Ils ne sont pas nécessairement les labels finaux visibles.

Le contrat UX peut traduire :

```text
preparation → À préparer
upcoming → À venir
active → En cours / Actives
blocked → Bloquées
completed → Terminées / Passées
```

selon contexte.

---

# 85. Limite runtime actuelle

Une Activity `published` peut aujourd’hui être projetée dans `active`.

Le contrat UX rappelle :

```text
published
≠ active now
```

Une future évolution de projection peut avoir besoin d’affiner structure durable vs continuité.

Ce point ne justifie pas la création d’un nouveau lifecycle.

---

# 86. Structural vs continuity

Pour generic :

```text
PORTFOLIO
= Activities qui existent durablement

CONTINUITY
= réalités qui avancent, se préparent ou se réalisent
```

Les deux peuvent partager la même source Activity.

Mais ils ne répondent pas à la même question.

---

# 87. PR Métier et cohérence

Toute évolution du chantier Space Métier doit conserver :

- authority Activity-limited ;
- responsabilité distincte de Permission ;
- structure distincte de continuité ;
- verticales seulement lorsqu’elles existent ;
- pas de migration UX inutile ;
- projection owner-backed.

---

# 88. Anti-features

Activités ne doit jamais devenir :

- un ERP générique ;
- un dashboard KPI ;
- une todo list universelle ;
- un kanban universel ;
- un table browser ;
- une liste de modèles Django ;
- une page « modules » ;
- un feed ;
- un calendrier global déguisé ;
- un historique complet en racine ;
- un moteur de recherche global ;
- une liste de tous les Contacts ;
- une vue CRM ;
- une page Payments ;
- une page Access ;
- une page Capacity ;
- une collection infinie de Cards ;
- un classement par popularité ;
- un score opaque ;
- une source d’autorité ;
- une seconde vérité Activity ;
- un second Journey ;
- un second Readiness ;
- un conteneur où toute donnée du Space doit apparaître.

---

# 89. Invariants gelés

1. `generic` n’est pas une verticale métier.
2. La porte visible est `Activités`.
3. Une Activity reste propriétaire de son identité générale.
4. Occurrence reste distincte d’Activity.
5. `published` ne signifie pas automatiquement `en cours`.
6. Les verticales spécialisées apparaissent seulement si elles existent réellement.
7. Le generic n’invente pas de verticales.
8. L’état vide ne crée jamais d’Activity fictive.
9. N1 parle humainement.
10. N2 explique une réalité.
11. N3 délègue au propriétaire.
12. La racine peut composer préparation, à venir, en cours, demandes, lieux, terminées.
13. Toutes les sections ne sont pas obligatoires.
14. Le viewer est Profile.
15. L’actor context est Space.
16. Responsabilité ≠ autorité.
17. Assignment ≠ Permission.
18. Membership ≠ autorité.
19. Presentation représente ; elle ne possède pas.
20. Search ne révèle pas de données non autorisées.
21. Offline ne transforme pas l’ancien en Live.
22. Jour J appartient à une Occurrence admissible.
23. Live appartient à Jour J.
24. Plusieurs Occurrences peuvent être actives simultanément.
25. Le Space entier ne devient pas Live.
26. Aucun module transverse ne devient onglet primaire automatiquement.
27. La création est contextuelle.
28. Le responsive adapte la géométrie, pas la vérité.
29. Le retour préserve la continuité cognitive.
30. No Orphan Content / Media s’applique.

---

# 90. Contrat de sortie Web

La surface Web est conforme lorsque :

- le Space generic affiche `Activités` ;
- le shell conserve le contexte Space ;
- la responsabilité ne modifie pas l’autorité ;
- l’état vide est honnête ;
- les Activities sont humainement lisibles ;
- les Occurrences sont distinguées ;
- les verticales réelles peuvent apparaître ;
- les verticales absentes ne sont pas inventées ;
- les sections techniques ne deviennent pas automatiquement des labels ;
- N2/N3 restent progressifs ;
- les actions non autorisées sont absentes ou correctement gérées ;
- le serveur revalide les mutations ;
- aucun IDOR n’est introduit.

---

# 91. Contrat de sortie Flutter

La surface Flutter est conforme lorsque :

- Compact est complet ;
- Medium/Wide conservent la vérité ;
- store local et sync respectent le contrat ;
- offline montre le snapshot sans mensonge ;
- stale est explicite si nécessaire ;
- resume revalide l’autorité ;
- deep links restaurent Actor Context ;
- Back restaure état de liste ;
- textScale 1.6 reste utilisable ;
- les actions sensibles attendent la vérité serveur.

---

# 92. Tests ciblés

Tests à prévoir :

```text
generic root content
generic root empty
generic root calm
activity-limited viewer
space-wide viewer
responsibility lens
no authority escalation
no orphan specialized vertical
activity + occurrence distinction
published != live
offline snapshot
permission revoked after load
deep link access control
partial section failure
text scale
compact / medium / wide
```

---

# 93. Fixture de référence

```text
Space
Fondation Upendo

Activités

À préparer
Atelier emploi
18 octobre
Lieu à confirmer

À venir
Forum local
25 octobre · 10:00
Centre communautaire

En cours
Programme mentorat
3 accompagnements actifs

Toutes les activités
Atelier emploi
Programme mentorat
Forum local

Lieux
Centre communautaire
Maison des jeunes
```

Ce fixture illustre une composition.

Il n’impose pas que tous les Spaces generic aient toutes ces sections.

---

# 94. Exemple sans verticales

```text
Activités

À venir
Assemblée mensuelle
Samedi · 14:00

Toutes les activités
Assemblée mensuelle
Rencontre bénévoles
Réunion de coordination
```

Aucun module spécialisé n’est nécessaire.

---

# 95. Exemple avec plusieurs verticales

```text
Activités

À préparer
Distribution de kits
40 bénéficiaires attendus

À venir
Forum emploi
18 octobre

Prestations
Orientation professionnelle
4 dossiers actifs

Toutes les activités
...
```

La racine reste Activités.

Les profondeurs peuvent parler la grammaire de leur verticale.

---

# 96. Exemple Activity permanente

```text
Centre d’écoute communautaire

Disponible toute l’année

Demandes
7

Prochaine permanence
Lundi · 09:00
```

La permanence peut être une Occurrence.

L’Activity n’est pas « à venir » en entier.

---

# 97. Exemple activité sans Occurrence

```text
Accompagnement documentaire

Disponible sur demande

[Ouvrir]
```

L’absence d’Occurrence est légitime.

---

# 98. Exemple lieu structurant

```text
Terrain municipal

3 activités à venir
```

Cette profondeur n’accorde aucun accès automatique aux Activities non autorisées.

---

# 99. Points volontairement ouverts

Restent ouverts pour implémentation :

- libellés exacts des sections selon données réelles ;
- seuils précis de passage list → split ;
- composant visuel Activity final ;
- stratégie carte ;
- profondeur Lieu finale ;
- politique de média par Activity ;
- microcopy finale ;
- animations ;
- détails analytics ;
- finalisation de la séparation structure/continuité dans la projection serveur ;
- capacités de création spécialisées exposées par API ;
- comportement exact des verticales multiples en racine.

Ces points ne doivent pas remettre en cause les invariants gelés.

---

# 100. Formulation finale

> **Activités est la porte Métier d’un Space `generic`. Elle rend intelligible le monde de travail réel du Space sans lui inventer un métier artificiel : les Activities qu’il fait exister, leurs réalisations temporelles, ce qui se prépare, ce qui arrive, ce qui continue, les demandes et lieux qui comptent, ainsi que les verticales spécialisées uniquement lorsqu’elles existent réellement. La racine parle humainement et reste modérée ; la profondeur compose les domaines propriétaires ; la Presentation ne possède aucune vérité ; l’autorité est vérifiée côté serveur ; l’offline conserve la compréhension mais jamais une actualité fictive. Activités n’est ni un ERP, ni une page de modules, ni une liste de tables : c’est la représentation cohérente et opérable de ce que ce Space fait réellement.**
