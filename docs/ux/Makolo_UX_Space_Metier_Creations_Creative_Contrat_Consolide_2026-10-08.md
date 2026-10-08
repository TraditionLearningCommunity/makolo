# Makolo — Space Métier `creative` / **Créations**
## Contrat UX consolidé — N1, N2/N3, hiérarchie, représentations, états, adaptive, local-first et handoffs

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence pour l’archétype Space `creative`  
**Porte visible :** **Créations**  
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
creative
```

Le libellé visible primaire est :

```text
Créations
```

Le contrat part du cadre déjà fixé dans l’architecture Space :

```text
Créations
├── créations / Activities
├── événements
├── prestations
├── Occurrences
└── offres réellement opérées
```

Invariant majeur :

> **La création artistique reste première lorsque le Space n’est pas principalement commercial.**

Interdits déjà établis :

```text
feed
Story
portfolio parallèle générique
média orphelin
faux publics
fausses offres
```

Le présent document transforme ces principes en contrat UX visible et implémentable.

---

# 1. Question humaine

La porte **Créations** répond à :

> **Qu’est-ce que nous créons réellement, qu’est-ce qui se prépare, qu’est-ce qui prend forme et comment le faire exister jusqu’au public ou au résultat attendu ?**

Elle permet de comprendre rapidement :

```text
ce que nous créons
+
où chaque création en est
+
ce qui se prépare
+
ce qui arrive
+
ce qui doit être présenté / joué / livré / publié réellement
+
ce qui a besoin d’une action
```

Elle ne demande pas :

> Qu’avons-nous posté récemment ?

Elle ne demande pas :

> Quel contenu a le plus de vues ?

Elle ne demande pas :

> Comment maximiser l’engagement ?

---

# 2. Pourquoi `Créations`

Le mot **Créations** est le centre de gravité visible de l’archétype `creative`.

Il peut couvrir :

- œuvre ;
- spectacle ;
- concert ;
- exposition ;
- performance ;
- production artistique ;
- pièce ;
- collection ;
- création visuelle ;
- création sonore ;
- création scénique ;
- projet créatif ;
- commande créative ;
- prestation artistique ;
- événement de présentation ;
- autre Activity réellement portée par le Space.

Mais `Création` UX n’impose aucun nouveau modèle persistant.

---

# 3. Création UX ≠ modèle métier

Invariant :

```text
CRÉATION UX
≠ modèle Creation obligatoire
```

Une création visible peut être soutenue par :

```text
Activity
Occurrence
Service
Event
Offer
Obtention
Journey
Resource
Media
Project / Dossier si légitime
autres domaines canoniques
```

La Presentation compose ces faits.

Elle ne les possède pas.

---

# 4. Personnalité UX

La personnalité de la surface est :

> **œuvre réelle + progression concrète + représentation visuelle contextualisée**

Elle doit être :

- visuelle lorsque le réel le justifie ;
- calme ;
- élégante ;
- professionnelle ;
- expressive sans être décorative ;
- orientée accomplissement ;
- capable de montrer l’évolution d’une création ;
- capable de montrer une date ou une présentation publique ;
- capable de montrer un service créatif ;
- capable de rester sobre sans média.

---

# 5. Création artistique première

Si le Space est `creative`, la racine doit d’abord répondre :

> **Qu’est-ce que nous créons ?**

et non :

> Qu’est-ce que nous vendons ?

Même si des Offers ou Payments existent.

Donc :

```text
Création
→ primaire

Commerce éventuel
→ support ou profondeur
```

sauf si le Space est réellement devenu principalement commercial, ce qui relève de l’archétype ou du contexte produit, pas d’un simple changement d’écran.

---

# 6. Commerce ne prend pas le dessus

Exemple :

```text
Album Kinshasa Nights
```

peut avoir :

- Offer ;
- précommande ;
- Payment ;
- retrait ;
- livraison.

Mais la racine `Créations` doit d’abord parler de :

```text
Album
état de préparation
sortie
présentation
```

Le commerce reste composé.

---

# 7. Relations avec les autres portes

## 7.1. Maintenant

`Maintenant` répond :

> Qu’est-ce qui mérite notre attention maintenant ?

Une répétition dans deux heures avec un élément manquant peut devenir une Situation Now.

La création elle-même reste dans Créations.

---

## 7.2. Découvrir

`Découvrir` peut aider à trouver :

- lieu ;
- partenaire ;
- opportunité ;
- festival ;
- financement ;
- ressource ;
- prestataire ;
- public potentiel ;
- collaboration.

La possibilité ne devient pas automatiquement une création.

---

## 7.3. Nous

`Nous` porte notamment :

- équipe ;
- identité ;
- partenaires ;
- publics ;
- responsabilités ;
- relations ;
- confiance.

Créations porte le travail créatif réel.

---

## 7.4. Piloter

`Piloter` peut analyser :

- ventes ;
- fréquentation ;
- coûts ;
- portée ;
- charge ;
- disponibilité ;
- tendances.

Créations ne devient pas Analytics.

---

# 8. Actor Context

Le contexte reste :

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
Avatar = Aïcha
Actor Context = Studio K
Métier = Créations
```

L’Avatar n’est jamais remplacé par l’identité du Space.

---

# 9. Responsabilité et autorité

Exemple :

```text
responsabilité
→ Direction artistique

autorité
→ gérer uniquement certaines Activities
```

La surface peut être filtrée par responsabilité.

Elle ne doit jamais élargir les Permissions.

---

# 10. N1 — structure conceptuelle

```text
CRÉATIONS
│
├── HEADER
│
├── CONTEXT
│   ├── Space
│   └── responsibility lens
│
├── CURRENT CREATIVE FIELD
│   ├── À préparer ?
│   ├── En création ?
│   ├── À présenter ?
│   ├── À venir ?
│   └── selon le réel
│
├── CREATIONS PORTFOLIO
│   └── créations / Activities durables
│
├── EVENTS ?
├── PRESTATIONS ?
├── OFFERS ?
├── OCCURRENCES ?
│
└── DEPTH
    ├── Création N2
    ├── Occurrence N2
    ├── Service owner
    ├── Commerce owner
    ├── Jour J
    └── Live
```

Cette structure est une grammaire UX.

---

# 11. Header

Le header principal suit :

```text
Makolo | Space / Créations | Recherche / filtres utiles | Avatar
```

Compact :

```text
Makolo
Studio K · Créations
[search] [filter] [avatar]
```

Wide :

```text
Makolo | Studio K / Créations | Toutes mes responsabilités | Recherche | Avatar
```

---

# 12. Icône

Intention sémantique candidate :

```text
palette
```

Le glyph final peut être adapté.

Le sens doit rester :

```text
création
```

et non :

```text
publication sociale
```

---

# 13. N1 — ordre perceptif

La racine peut privilégier :

```text
1. ce qui est en création / préparation
2. ce qui doit être présenté ou réalisé bientôt
3. créations durables
4. événements
5. prestations réellement opérées
6. offres réellement opérées
```

L’ordre s’adapte au réel.

---

# 14. Sections visibles

Sections possibles :

```text
En création
À préparer
À présenter
À venir
Créations
Événements
Prestations
Offres
Terminées
```

Aucune n’est obligatoire universellement.

Une section vide n’a pas besoin d’exister.

---

# 15. `En création`

`En création` ne doit pas être un statut générique arbitraire.

Il doit être dérivable depuis :

- Activity réellement active ;
- Project/Dossier légitime ;
- workflow propriétaire ;
- préparation ;
- autre vérité canonique.

Le client n’invente pas cet état.

---

# 16. `À préparer`

Peut contenir :

- création à compléter ;
- répétition à préparer ;
- lieu à confirmer ;
- ressource manquante ;
- équipe à coordonner ;
- Requirement ;
- Occurrence draft ;
- autre préparation réelle.

Exemple :

```text
Concert acoustique
12 octobre

Lieu confirmé
Sonorisation à finaliser

[Préparer]
```

---

# 17. `À présenter`

Cette section peut être utile lorsqu’une création va rencontrer un public ou être remise.

Exemples :

```text
Exposition
Première
Sortie
Livraison
Projection
Concert
Vernissage
```

Mais le libellé exact reste contextuel.

---

# 18. Événements

Events apparaissent lorsqu’ils existent réellement.

Exemple :

```text
Concert de sortie
18 octobre · 19:00
```

Un événement n’est pas inventé pour chaque création.

---

# 19. Prestations

Une activité créative peut prendre la forme d’une prestation :

```text
Portrait sur commande
Direction artistique
Animation musicale
Création graphique
```

Si Service est réellement utilisé, la racine peut rendre ces prestations visibles.

Mais le Space reste centré sur ses créations s’il n’est pas principalement service_provider.

---

# 20. Offers

Une Offer peut apparaître seulement si elle est réellement opérée.

Exemples :

```text
Billet concert
Tirage limité
Commande personnalisée
Licence / accès
```

La présence d’un prix ne transforme pas la racine en Commerce.

---

# 21. Pas de fausse offre

Interdit :

```text
création
→ automatiquement Offer
```

Si aucune Offer canonique n’existe, la surface n’affiche pas :

```text
Acheter
Réserver
Commander
```

par simple convention créative.

---

# 22. Publics

Le Space creative peut avoir des publics.

Mais un public :

```text
≠ création
≠ audience feed
```

Il reste surtout relationnel ou pertinent pour Découvrir/Nous/Piloter selon le contexte.

---

# 23. N1 — représentation d’une création

Exemple visuel :

```text
[media contextuel]

Kinshasa Nights
Album

Mixage final en cours
Sortie prévue · 18 novembre
```

Exemple sans média :

```text
Pièce « Le Passage »

Répétitions en cours
Première · 2 décembre
```

Le média n’est jamais obligatoire.

---

# 24. Card vs row

Une création peut légitimement bénéficier d’une card plus riche que Transport ou Prestations.

Mais :

```text
card riche
≠ feed
```

La racine doit conserver des sections et une fin.

Une liste structurée peut être préférable pour la continuité.

---

# 25. Média primaire mais contextualisé

Le média peut devenir un élément de reconnaissance.

Exemples :

- cover ;
- affiche ;
- photo de scène ;
- planche ;
- extrait ;
- image de l’œuvre ;
- audio ;
- vidéo ;
- maquette.

Mais il doit avoir une fonction.

---

# 26. No Orphan Media

Chaque média doit répondre à une question :

```text
que montre-t-il ?
à quelle création appartient-il ?
pourquoi est-il utile ici ?
```

Pas de média isolé pour remplir l’espace.

---

# 27. Pas de feed

Interdits :

- timeline de posts ;
- stories ;
- likes ;
- commentaires comme centre ;
- vues comme ranking ;
- autoplay ;
- recommandation par engagement ;
- « tendance » par popularité ;
- scroll infini artificiel.

Créations est un workspace.

---

# 28. Portfolio parallèle interdit

La porte elle-même rend visible le travail créatif.

Il ne faut pas ajouter un autre concept :

```text
Portfolio
```

comme deuxième source de vérité générique si Activity/Presentation suffisent.

Une projection publique peut exister.

Mais elle représente les mêmes réalités.

---

# 29. Projection publique ≠ workspace

Le workspace Créations peut contenir :

- drafts ;
- préparation ;
- éléments privés ;
- ressources internes ;
- personnes ;
- contrats ;
- paiements ;
- autorité.

La projection publique doit appliquer divulgation minimale.

---

# 30. N2 — création

Candidate :

```text
← Kinshasa Nights

Kinshasa Nights
Album

[cover]

État
Mixage final

Sortie
18 novembre

Prochaine étape
Valider le master

Présentation
Concert de sortie · 20 novembre

Ressources
...

Offre
si réellement opérée

[Actions contextuelles]
```

---

# 31. N2 — composition

Une profondeur peut composer :

```text
identity
description
media
stage / current synthesis
occurrences
events
services
resources
requirements
people
partners
offers
payments
capacity
access
places
owner actions
```

uniquement selon le réel.

---

# 32. N2 — progression

Pas de pourcentage de progression sans mesure défendable.

Préférer :

```text
Mixage final
Master à valider
```

à :

```text
82 % terminé
```

si aucun calcul métier ne justifie 82 %.

---

# 33. N2 — événements liés

Une création peut avoir plusieurs Occurrences/Events.

Exemple :

```text
Présentation
18 nov · écoute privée
20 nov · concert de sortie
4 déc · showcase
```

La création reste une seule identité.

---

# 34. N2 — prestation liée

Exemple :

```text
Création graphique sur commande

Client
...

Livrable attendu
Affiche finale

État
À valider
```

La profondeur peut passer vers Service si le workflow réel est Service.

---

# 35. N2 — offre liée

Exemple :

```text
Tirage signé
30 exemplaires
50 USD
```

si Offer + Capacity existent réellement.

Le stock/capacité n’est pas inventé depuis un texte marketing.

---

# 36. N3 — owner depth

N3 délègue vers :

```text
Activity
Occurrence
Service
Offer
Order
Payment
Access
Capacity
Requirement
Resource
Partner
Journey
```

Le titre reste humain.

---

# 37. N3 — création et ressources

Une ressource peut être :

- fichier ;
- plan ;
- brief ;
- script ;
- partition ;
- référence ;
- contrat ;
- image ;
- audio ;
- vidéo.

Elle reste Resource/Artifact selon propriétaire.

---

# 38. Création contextuelle

Action primaire candidate :

```text
Nouvelle création
```

si capability serveur.

Mais cette action peut créer une Activity avec le bon contexte.

Elle ne nécessite pas un modèle `Creation`.

---

# 39. Actions secondaires

Depuis N2 :

```text
Ajouter une date
Ajouter un média
Ajouter une ressource
Créer une présentation
Associer une prestation
Associer une offre
```

uniquement si légitimes et autorisées.

---

# 40. Pas de mega-menu

Interdit :

```text
Créer
├ Activity
├ Occurrence
├ Event
├ Offer
├ Service
├ Resource
├ Journey
├ Access
└ ...
```

La création reste contextuelle.

---

# 41. Empty state

Space creative vide :

```text
Créations

Aucune création pour le moment.
```

Si autorisé :

```text
[Créer une première création]
```

Pas de faux exemple persistant.

---

# 42. Calm state

Exemple :

```text
Créations

Tout avance normalement.

En création
Kinshasa Nights

À venir
Concert acoustique · 18 octobre
```

Le calme n’exige pas de remplir l’écran.

---

# 43. Search

Recherche spécialisée :

```text
Rechercher une création, un événement ou une prestation
```

Selon autorité, elle peut couvrir :

- créations ;
- Events ;
- Occurrences ;
- prestations ;
- Offers ;
- lieux ;
- personnes liées ;
- ressources.

---

# 44. Filtres

Filtres possibles :

```text
En création
À préparer
À venir
À présenter
Événements
Prestations
Offres
Terminées
Par période
Par lieu
Par responsabilité
```

Pas de taxonomie backend comme langage primaire.

---

# 45. Media view

Une vue plus visuelle peut être légitime.

Exemple :

```text
Grid
```

pour reconnaître des œuvres.

Mais :

```text
grid visuelle
≠ feed
```

Elle doit conserver :

- sections ;
- contexte ;
- action ;
- fin ;
- sélection.

---

# 46. List view

La liste reste meilleure pour :

- préparation ;
- échéances ;
- prestations ;
- continuité ;
- états ;
- actions.

Le client peut permettre grid/list selon contexte.

---

# 47. Remember my choice

Le client peut mémoriser :

```text
grid / list
```

si c’est une préférence explicite et sûre.

Il ne mémorise pas aveuglément des filtres temporaires.

---

# 48. Hiérarchie perceptive

N1 :

```text
CREATION IDENTITY / CURRENT STAGE      P2
CURRENT CONSEQUENCE                    P2/P3
NEXT ACTION                            P2/P3
MEDIA                                  P1/P2 selon rôle
TIME / PLACE                           P1
COMMERCE                               P1 sauf action bloquante
```

---

# 49. Le média ne devient pas automatiquement P3

Une belle image ne doit pas prendre le contrôle de la hiérarchie si l’utilisateur doit surtout agir.

Exemple :

```text
Master à valider aujourd’hui
```

peut être P3.

La cover reste support.

---

# 50. Now handoff

Une création peut produire :

```text
Master à valider avant 16 h.
```

dans Now.

Créations garde la continuité et la profondeur.

---

# 51. Découvrir handoff

Découvrir peut aider à trouver :

```text
festival
lieu
collaborateur
financement
ressource
public
service
transport
```

La recherche peut partir depuis une création existante.

---

# 52. Nous handoff

La création peut pointer vers :

- équipe ;
- partenaire ;
- collaborateur ;
- public ;
- responsable.

Mais les relations restent propriétaires de Nous/CRM/Partners.

---

# 53. Piloter handoff

Piloter peut analyser :

- revenus ;
- coûts ;
- ventes ;
- fréquentation ;
- conversion ;
- capacité ;
- calendrier ;
- charge ;
- performance.

Créations ne doit pas afficher ces métriques en permanence.

---

# 54. Jour J

Une Occurrence réelle peut ouvrir Jour J.

Exemples :

```text
Concert
Vernissage
Première
Showcase
Session d’enregistrement
Remise / livraison si contrat adapté
```

Jour J n’est pas une tab globale de Créations.

---

# 55. Live

Live appartient à Jour J.

Exemple :

```text
Concert en cours
```

peut avoir une projection Live.

Une création durable n’est pas Live pendant des mois.

---

# 56. Plusieurs Occurrences

Une création peut avoir plusieurs Occurrences simultanées ou successives.

Le client ne duplique pas la création comme si chaque date était une création différente.

---

# 57. Readiness

Readiness reste dérivée.

Créations peut dire :

```text
Prêt pour la première
2 éléments à préparer
```

si owner-backed.

Pas de `creative_readiness` parallèle.

---

# 58. Requirements

Exemples :

```text
autorisation
contrat
validation du client
fichier final
preuve
```

Ils restent Requirements/owner facts.

---

# 59. Capacity

Capacity peut être utile pour :

- places ;
- tirages ;
- sessions ;
- commandes ;
- disponibilités.

Elle répond à `combien ?`.

Elle ne répond pas à `où ?`.

---

# 60. Placement

Si Placement existe dans une Occurrence :

```text
sièges
zones
emplacements
```

il répond à `où ?`.

Ne pas confondre avec Capacity.

---

# 61. Access

Access peut représenter :

- billet ;
- invitation ;
- droit d’entrée ;
- droit de téléchargement ;
- autre droit.

La création ne possède pas Access.

---

# 62. Commerce

Offer/Order/Payment apparaissent lorsqu’ils comptent.

Invariant :

```text
paiement
≠ création accomplie
```

et :

```text
vente
≠ preuve de réussite artistique
```

---

# 63. Service

Une commande créative peut être Service.

Exemple :

```text
Création d’une identité visuelle
```

Le dossier de prestation peut composer Requirements, étapes, Payment et résultat.

La racine reste Créations si le Space est principalement creative.

---

# 64. Event

Un concert ou vernissage peut être Event.

Le contrat Event reste propriétaire.

Créations peut l’intégrer comme réalisation d’une création.

---

# 65. Obtention

Une œuvre peut être obtenue :

- achat ;
- location ;
- prêt ;
- distribution ;
- licence ;
- autre mode.

Obtention peut composer Commerce.

Créations reste la porte du créateur.

---

# 66. Media et Proof

Un média ne vaut pas automatiquement Proof.

Une photo de scène :

```text
≠ preuve juridique
≠ AccessUse
≠ fulfillment
```

sans contrat owner-backed.

---

# 67. Publication

Publier une projection publique ne doit pas être confondu avec :

```text
ActivityStatus.PUBLISHED
```

si ces concepts ont des sémantiques différentes.

L’UX doit utiliser un langage clair.

---

# 68. Public projection

Une création peut avoir une présentation publique.

Elle applique :

- divulgation minimale ;
- médias autorisés ;
- texte public ;
- Offers publiques seulement si réellement actives ;
- aucune note privée ;
- aucun Payment privé ;
- aucune ressource interne.

---

# 69. États UX

Le contrat supporte :

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
media_unavailable
```

---

# 70. Loading

Préserver le contenu connu.

Ne pas vider un grid puis afficher des skeletons si un snapshot existe.

---

# 71. Offline

Le client peut montrer :

- créations déjà synchronisées ;
- médias locaux autorisés ;
- dates connues ;
- ressources disponibles localement ;
- drafts.

Mais il ne confirme pas :

- disponibilité globale actuelle ;
- paiement ;
- Access ;
- Capacity concurrente ;
- état Live.

---

# 72. Media offline

Un média localement disponible peut rester visible.

Un média non téléchargé peut afficher :

```text
Indisponible hors connexion
```

sans casser toute la création.

---

# 73. Stale

Une création durable peut tolérer plus de stale que :

- place restante ;
- disponibilité d’Offer ;
- Jour J ;
- Live.

La fraîcheur est locale au fait.

---

# 74. Partial failure

Exemple :

```text
Création visible
Dates visibles
Ressources visibles

Offres
Impossible d’actualiser.
```

Le reste reste utilisable.

---

# 75. Permission loss

Si l’autorité est révoquée :

- retirer mutations ;
- retirer données privées ;
- revalider profondeur ;
- garder projection publique si autorisée ;
- expliquer la limite.

---

# 76. Compact

Compact :

```text
single pane
bottom nav
sections verticales
cards/rows
N2 par navigation
```

La card média ne doit pas être trop haute au point de cacher la continuité.

---

# 77. Medium

Medium peut permettre :

```text
field visuel
+
preview
```

ou :

```text
grid
+
focus
```

si le contexte reste clair.

---

# 78. Wide

Wide :

```text
NAV | CRÉATIONS | FOCUS
```

après sélection.

La racine peut utiliser une grille plus respirante.

Mais pas une galerie infinie.

---

# 79. Very Wide

Interdits :

- mur de médias ;
- dashboard KPI ;
- timeline sociale ;
- trois colonnes de métriques ;
- galerie sans hiérarchie.

L’espace supplémentaire conserve contexte + focus.

---

# 80. Adaptive conservation

Conserver autant que possible :

- surface ;
- création sélectionnée ;
- scroll ;
- query ;
- filtres ;
- view grid/list ;
- responsabilité ;
- profondeur ;
- brouillon ;
- média sélectionné.

---

# 81. Back

Retour N2 → N1 restaure :

- section ;
- scroll ;
- filtre ;
- grid/list ;
- sélection.

---

# 82. Resume

À la reprise :

1. montrer snapshot sûr ;
2. revalider ;
3. actualiser médias métadata si nécessaire ;
4. retirer contenus non autorisés ;
5. préserver contexte.

---

# 83. Deep links

Deep link :

```text
Makolo
→ Space
→ Créations
→ création
```

Doit restaurer Actor Context.

Il ne contourne jamais l’autorité.

---

# 84. Native mobile

Selon contexte :

- caméra ;
- photo picker ;
- fichiers ;
- audio ;
- share sheet ;
- permissions ;
- deep link.

La permission est demandée au moment du besoin.

---

# 85. Capture média

Ajouter un média ne signifie pas automatiquement publier.

Exemple :

```text
Ajouter une photo
→ média local / ressource
→ confirmation / association
→ publication seulement si action distincte
```

---

# 86. Brouillons

Un draft créatif peut être local-first si le domaine l’autorise.

Le client doit distinguer :

```text
brouillon local
brouillon synchronisé
création publiée
```

sans fausse confirmation.

---

# 87. Search globale vs spécialisée

Recherche globale Space :

```text
Rechercher dans cet Espace
```

Recherche Créations :

```text
Rechercher une création, un événement ou une prestation
```

---

# 88. API / projection actuelle

Le runtime Space Métier fournit une projection commune.

Le contrat peut consommer :

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

Le client ne reconstruit pas l’autorité.

---

# 89. Runtime archetype

Le preset actuel `creative` établit :

```text
primary_business_label = Créations
activities_label = Créations & activités
```

et met notamment en avant des modules tels que :

```text
activities
crm
audiences
promotions
growth
partners
analytics
```

Mais :

```text
featured_modules
≠ sections visibles obligatoires
```

---

# 90. Runtime gap

La projection Space Work actuelle regroupe principalement :

```text
preparation
upcoming
active
blocked
completed
```

Elle peut porter une première racine.

Mais elle ne suffit pas forcément à exprimer toutes les nuances visibles :

```text
créations durables
présentations
événements
prestations
offres
médias contextuels
```

sans évolution de Presentation/projection.

Le contrat UX décrit la cible sans inventer de vérité.

---

# 91. Structure vs continuité

Pour creative :

```text
STRUCTURE
→ créations durables
→ œuvres / activités
→ séries / programmes créatifs si existants

CONTINUITÉ
→ préparation
→ production actuelle
→ prochaine présentation
→ livraison
→ événement
```

Ces dimensions peuvent se croiser.

---

# 92. Anti-features

Créations ne devient jamais :

- feed ;
- Story ;
- réseau social ;
- galerie générique sans finalité ;
- portfolio parallèle universel ;
- page Instagram interne ;
- mur de médias ;
- autoplay feed ;
- système de likes ;
- ranking de vues ;
- classement d’artistes ;
- moteur de viralité ;
- CRM ;
- Commerce complet ;
- dashboard Analytics ;
- task manager ;
- kanban générique ;
- second Journey ;
- second Readiness ;
- source d’autorité ;
- bibliothèque média orpheline ;
- faux catalogue ;
- fausse offre ;
- faux public.

---

# 93. Golden candidates

## G-CRE-01 — Compact / Content

Fixture :

```text
Studio K
Créations

En création
Kinshasa Nights
Album
Mixage final

À préparer
Concert acoustique
12 octobre
Sonorisation à finaliser

À venir
Exposition Lumières
18 novembre
```

---

## G-CRE-02 — Compact / Empty

```text
Créations

Aucune création pour le moment.

[Créer une première création]
```

si autorisé.

---

## G-CRE-03 — Compact / Calm

```text
Créations

Tout avance normalement.

En création
Kinshasa Nights

À venir
Exposition Lumières
```

---

## G-CRE-04 — Media contextual

Une création avec cover.

Test :

- média reconnaissable ;
- texte reste lisible ;
- média ne devient pas feed ;
- next action reste visible.

---

## G-CRE-05 — Grid / Compact Large

Grid de créations si écran assez large.

Aucune infinité.

Sections conservées.

---

## G-CRE-06 — Medium / selected

```text
CREATIONS | PREVIEW
grid/list | Kinshasa Nights
```

---

## G-CRE-07 — Wide / N2

```text
NAV | CRÉATIONS | CRÉATION
```

N2 conserve stages + events + offers contextuelles.

---

## G-CRE-08 — Offer contextual

Création :

```text
Tirage signé
Offer active
```

Commerce visible comme support.

La racine reste Créations.

---

## G-CRE-09 — Offline media

Texte + média local visible.

Média distant absent n’effondre pas la surface.

---

## G-CRE-10 — textScale 1.6

Aucun contenu essentiel tronqué.

Card adapte sa hauteur.

---

# 94. Viewports Golden

```text
360 × 800
430 × 932
834 × 1112
1440 × 900
1728 × 1117
```

Text scales :

```text
1.0
1.3
1.6
```

États :

```text
content
calm
empty
offline
stale
partial
permission_loss
media_unavailable
```

---

# 95. Recognition test

En 500 ms :

```text
où suis-je ?
→ Studio K

quel mode ?
→ Créations

qu’est-ce qui domine ?
→ création / continuité réelle
```

Pas :

```text
gallery
social feed
analytics
```

---

# 96. Blur test

Texte flouté :

- section principale identifiable ;
- médias structurés ;
- chrome secondaire ;
- aucune mosaïque chaotique.

---

# 97. Deletion test

Pour chaque média :

> Si je le supprime, la reconnaissance ou l’action souffre-t-elle ?

Si non :

il ne devrait probablement pas être là.

---

# 98. Competition test

Une image spectaculaire ne doit pas concurrencer une action urgente.

Un seul P3 perceptif à la fois.

---

# 99. Accessibility

MUST :

- text scaling ;
- alt / semantics pour médias utiles ;
- focus keyboard ;
- tap targets ;
- Reduce Motion ;
- états non basés uniquement sur couleur ;
- captions/transcriptions lorsque pertinentes ;
- pas d’autoplay avec son ;
- actions toujours identifiables.

---

# 100. Audio et vidéo

Si audio/vidéo est central :

- contrôle explicite ;
- pas d’autoplay agressif ;
- état de chargement local ;
- fallback ;
- accessibilité ;
- transcript/caption si disponible.

---

# 101. Couleurs

Palette Makolo :

```text
#5232DB
#2B176E
#FF704D
#FAF7F5
#0F172A
```

Une création peut porter ses propres médias/couleurs.

Le shell Makolo reste cohérent.

---

# 102. Motion

Motion peut soutenir :

- ouverture ;
- sélection ;
- preview ;
- chargement média ;
- confirmation ;
- retour.

Pas de motion destinée à retenir l’attention.

---

# 103. Local-first

Le client peut conserver :

- projections de créations ;
- médias autorisés téléchargés ;
- ressources ;
- drafts ;
- sélection ;
- view preference ;
- dates ;
- contexte.

Serveur autoritaire pour :

- permissions ;
- publication partagée ;
- Payment ;
- Capacity ;
- Access ;
- Orders ;
- multi-acteur ;
- Jour J ;
- Live.

---

# 104. Feedback

Préférer :

> **Création enregistrée. Il reste à ajouter une date de présentation.**

à :

> Success.

Préférer :

> **Photo ajoutée au brouillon.**

si elle n’est pas encore publiée.

---

# 105. Erreur média

Exemple :

```text
Impossible de charger la vidéo.
La création reste disponible.

[Réessayer]
```

Une erreur média reste locale.

---

# 106. Erreur de mutation

Répondre à :

1. qu’est-ce qui a échoué ?
2. qu’est-ce qui reste conservé ?
3. que faire maintenant ?

---

# 107. Privacy

Les médias peuvent contenir des personnes.

La surface doit respecter :

- visibilité ;
- consentement / droits si domaine concerné ;
- divulgation minimale ;
- projections publiques distinctes ;
- aucune fuite de ressources internes.

---

# 108. No Orphan Content

Texte, image, audio, vidéo et document doivent avoir :

```text
contexte
+
finalité
+
propriétaire
```

Sinon ne pas les promouvoir dans la porte.

---

# 109. Invariants gelés

1. La porte visible est `Créations`.
2. `creative` est un archétype de Presentation.
3. `Création` UX n’est pas un modèle universel.
4. La création artistique reste première.
5. Commerce éventuel reste composé.
6. Events apparaissent seulement s’ils existent.
7. Prestations apparaissent seulement si réellement opérées.
8. Offers apparaissent seulement si réellement opérées.
9. Occurrence reste distincte d’Activity.
10. Activity reste propriétaire de son identité.
11. Presentation ne possède pas.
12. Feed interdit.
13. Story interdite.
14. Portfolio parallèle générique interdit.
15. Média orphelin interdit.
16. Faux public interdit.
17. Fausse offre interdite.
18. Media ≠ Proof.
19. Payment ≠ accomplissement créatif.
20. Vente ≠ réussite artistique.
21. Public projection ≠ workspace.
22. Actor Context = Space.
23. Viewer = Profile.
24. Responsibility ≠ authority.
25. Assignment ≠ Permission.
26. Membership ≠ authority.
27. Readiness reste dérivée.
28. Capacity ≠ Placement.
29. Access reste droit canonique.
30. N1 reste lisible.
31. N2 explique une création.
32. N3 délègue au propriétaire.
33. Jour J appartient à une Occurrence admissible.
34. Live appartient à Jour J.
35. Une création durable n’est pas Live.
36. Plusieurs Occurrences peuvent coexister.
37. Offline ne fabrique pas l’actualité.
38. Média local ne signifie pas média publié.
39. Le serveur revalide les mutations sensibles.
40. Le responsive adapte la géométrie, pas la vérité.

---

# 110. Critères de sortie serveur

Le serveur doit pouvoir :

- identifier l’archétype creative ;
- exposer le label `Créations` ;
- filtrer authority-first ;
- exposer Activity/Occurrence owner-backed ;
- exposer capabilities ;
- exposer verticales présentes ;
- ne pas inventer Offer/Event/Service ;
- permettre handoffs owner ;
- préserver privacy ;
- supporter états partiels ;
- supporter freshness ;
- permettre profondeur Jour J lorsque admissible.

---

# 111. Critères de sortie Web

Le Web est conforme lorsque :

- Créations est reconnaissable immédiatement ;
- création artistique domine ;
- aucune dérive feed ;
- média contextualisé ;
- grid/list possible sans feed ;
- N2/N3 progressifs ;
- Offers/Services restent contextuels ;
- permissions correctes ;
- back conserve contexte ;
- responsive conserve priorité.

---

# 112. Critères de sortie Flutter

Flutter est conforme lorsque :

- Compact complet ;
- média local-first raisonnable ;
- offline honnête ;
- media unavailable localisé ;
- deep links restaurent Space ;
- back gesture conserve sélection ;
- grid/list conserve préférence ;
- textScale 1.6 fonctionne ;
- camera/photo picker au moment du besoin ;
- publication partagée reste serveur-authoritative.

---

# 113. Tests ciblés

```text
creative root content
creative root empty
creative root calm
creation with media
creation without media
event composition
service composition
offer composition
no fake offer
no fake audience
no orphan media
activity-limited viewer
responsibility lens
authority loss
offline snapshot
offline media unavailable
deep link
jour j handoff
multiple occurrences
textScale 1.6
compact / medium / wide
```

---

# 114. Fixture de référence

```text
Studio K
Créations

En création
Kinshasa Nights
Album
Mixage final

À préparer
Concert acoustique
12 octobre · 19:00
Sonorisation à finaliser

À venir
Exposition Lumières
18 novembre

Créations
Kinshasa Nights
Lumières
Portraits de ville
```

---

# 115. Fixture création + Offer

```text
Portraits de ville

Série photographique

Présentation
18 novembre

Tirages disponibles
30 exemplaires

[Voir l’offre]
```

L’Offer existe réellement.

Elle ne transforme pas la racine en Commerce.

---

# 116. Fixture prestation

```text
Création d’affiche

Client
Festival X

État
Version finale à valider

Échéance
Vendredi

[Ouvrir la prestation]
```

---

# 117. Fixture événement / Jour J

```text
Concert acoustique

Aujourd’hui · 19:00
Salle Malemba

Préparation
Tout est prêt

[Ouvrir Jour J]
```

---

# 118. Fixture média offline

```text
Kinshasa Nights

[cover locale disponible]

Mixage final

Vidéo making-of
Indisponible hors connexion
```

La création reste pleinement intelligible.

---

# 119. Points volontairement ouverts

Restent ouverts :

- composant final row/card/grid ;
- politique exacte d’autoplay : par défaut non ;
- pipeline de média final ;
- droits média détaillés ;
- microcopy finale ;
- breakpoints précis grid/list ;
- profondeur publique ;
- partage public ;
- composant Flutter media ;
- création contextualisée exacte ;
- payload creative spécialisé ;
- sélection de cover ;
- structure éventuelle de collections/séries si domaine justifié ;
- analytics détaillés côté Piloter ;
- animations finales.

Ces points ne changent pas les invariants.

---

# 120. Références de cadrage

Ce contrat s’appuie principalement sur :

- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Mobile_Visual_Charter_v1.1.md`
- `Makolo_UI_Engineering_Standards_v1.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_UX_Now_Contrat_Consolide.md`
- `Makolo_UX_Decouvrir_Contrat_Consolide.md`
- `Makolo_UX_En_Cours_Contrat_Consolide.md`
- les contrats local-first et sync mobile du projet
- le runtime `main` courant au moment de la consolidation

Le code, les migrations, les tests et les domaines canoniques restent prioritaires lors de l’implémentation.

---

# 121. Formulation finale

> **Créations est la porte Métier d’un Space `creative`. Elle rend visible et opérable ce que le Space crée réellement : créations et Activities, événements, prestations, Occurrences et offres lorsqu’elles existent vraiment. Elle conserve la création artistique comme centre de gravité, même lorsque Commerce, Service, Event, Media, Access ou Capacity participent à l’accomplissement. Elle peut être visuellement riche sans devenir un feed : tout média reste contextualisé, tout contenu garde une finalité et la surface peut se terminer. N1 montre le champ créatif vivant, N2 explique une création, N3 délègue aux propriétaires, Jour J accompagne une réalisation actuelle, et le serveur reste l’autorité pour les permissions, actions partagées et vérités sensibles.**
