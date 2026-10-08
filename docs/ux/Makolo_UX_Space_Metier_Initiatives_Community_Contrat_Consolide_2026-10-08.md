# Makolo — Space Métier `community` / **Initiatives**
## Contrat UX consolidé — N1, N2/N3, hiérarchie, représentations, états, adaptive, local-first et handoffs

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence pour l’archétype Space `community`  
**Porte visible :** **Initiatives**  
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
community
```

Le libellé visible primaire est :

```text
Initiatives
```

Le contrat part du cadre déjà fixé :

```text
Initiatives
├── initiatives
├── Activities
├── événements
├── actions terrain
└── programmes réels
```

Il conserve également les frontières déjà établies :

```text
Groups
Publics
Partners
→ surtout relationnels

Funding
→ possibilité
→ Activity
→ ou signal de Pilotage
selon le contexte réel
```

Le document ne crée pas un modèle métier `Initiative`.

Il fixe la manière de présenter, organiser et opérer des réalités canoniques déjà existantes dans Makolo.

---

# 1. Question humaine

La porte **Initiatives** répond à :

> **Qu’est-ce que nous faisons concrètement avancer ensemble, sur le terrain ou dans la durée ?**

Elle doit permettre de comprendre rapidement :

```text
ce que le collectif porte
+
ce qui est en préparation
+
ce qui se déroule
+
ce qui arrive
+
ce qui mobilise des personnes ou ressources
+
ce qui doit produire un résultat réel
```

Elle ne demande pas :

> Combien de membres avons-nous ?

Elle ne demande pas :

> Qui nous suit ?

Elle ne demande pas :

> Quel contenu publier ?

Ces questions appartiennent à d’autres territoires.

---

# 2. Pourquoi `Initiatives`

Le mot **Initiatives** traduit le centre de gravité de l’archétype `community`.

Il est suffisamment large pour accueillir :

- actions communautaires ;
- projets locaux ;
- programmes ;
- campagnes concrètes ;
- événements ;
- actions terrain ;
- activités récurrentes ;
- distributions ;
- mobilisation de ressources ;
- actions citoyennes ;
- activités associatives ;
- autres réalisations collectives réelles.

Mais il ne devient pas un concept backend universel.

---

# 3. Principe fondamental

```text
INITIATIVE UX
≠ nouveau modèle Initiative
```

et :

```text
INITIATIVES
≠ feed communautaire
```

Une initiative visible peut être portée par :

```text
Activity
Occurrence
Journey
Funding
Obtention
Event
Service
Project / Dossier si légitime
autres propriétaires canoniques
```

selon le réel.

La Presentation compose.

Elle ne possède pas.

---

# 4. Personnalité UX

La personnalité d’Initiatives est :

> **mobilisation réelle + continuité collective + impact concret**

La surface doit donner une impression :

- vivante sans être un feed ;
- collective sans être un réseau social ;
- orientée accomplissement ;
- structurée ;
- humaine ;
- tournée vers le réel ;
- capable de montrer le terrain ;
- capable de montrer la durée ;
- capable de rester calme quand rien ne presse.

---

# 5. Différence avec les autres portes

## 5.1. Maintenant

`Maintenant` :

> Qu’est-ce qui mérite notre attention maintenant ?

`Initiatives` :

> Qu’est-ce que nous faisons réellement avancer ensemble ?

Une initiative peut exister pendant plusieurs mois sans apparaître dans Now chaque jour.

Une conséquence importante peut remonter dans Now.

---

## 5.2. Découvrir

`Découvrir` :

> Qu’est-ce qui pourrait aider notre organisation à avancer ?

`Initiatives` :

> Qu’est-ce que nous avons réellement décidé de porter, préparer ou réaliser ?

Une possibilité découverte n’est pas une initiative engagée.

---

## 5.3. Nous

`Nous` répond :

> Qui sommes-nous et comment fonctionnons-nous ensemble ?

Il porte notamment :

- identité collective ;
- équipe ;
- responsabilités ;
- groupes ;
- partenaires ;
- relations ;
- confiance.

`Initiatives` montre ce que ce collectif fait.

---

## 5.4. Piloter

Piloter peut montrer :

- tendances ;
- résultats agrégés ;
- financement ;
- performance ;
- besoins ;
- ressources ;
- analytics.

Initiatives ne devient pas un dashboard d’impact.

---

# 6. Groups, Publics, Partners

Invariant :

```text
Groups
Publics
Partners
≠ initiatives par défaut
```

Ils restent surtout relationnels.

Exemple :

```text
Groupe bénévoles
→ Nous / relations
```

mais :

```text
Journée de nettoyage du quartier
→ Initiatives
```

Le groupe peut être lié à l’initiative.

Il ne la remplace pas.

---

# 7. Funding

Funding a plusieurs placements possibles.

## 7.1. Funding comme possibilité

```text
Appel à financement externe
→ Découvrir
```

## 7.2. Funding comme Activity réellement portée

```text
Collecte pour financer l’ambulance
→ Initiatives
```

si la mobilisation de fonds est elle-même une action structurée du collectif.

## 7.3. Funding comme signal de Pilotage

```text
Budget insuffisant pour poursuivre trois initiatives
→ Piloter / Maintenant selon conséquence
```

Donc :

```text
Funding
≠ toujours une initiative
```

---

# 8. Actor Context

Le contexte est :

```text
ACTOR_CONTEXT
→ Space
```

Le Viewer :

```text
VIEWER
→ Profile
```

Exemple :

```text
Avatar = Jean
Actor Context = Fondation Upendo
Métier = Initiatives
```

L’Avatar ne devient jamais le logo du Space.

---

# 9. Responsabilité et autorité

Un membre peut avoir :

```text
responsabilité
→ Coordination terrain
```

sans avoir :

```text
Permission
→ gérer toutes les initiatives
```

La surface peut être filtrée par responsabilité.

Elle ne doit jamais élargir l’autorité.

---

# 10. N1 — structure conceptuelle

```text
INITIATIVES
│
├── HEADER
│
├── CONTEXT
│   ├── Space
│   └── responsibility lens
│
├── CONTINUITY FIELD
│   ├── À préparer ?
│   ├── En cours ?
│   ├── À venir ?
│   ├── Terrain aujourd’hui ?
│   ├── Bloquées ?
│   └── selon le réel
│
├── INITIATIVE PORTFOLIO
│   └── réalités durables / engagées
│
├── EVENTS ?
├── PROGRAMMES ?
├── FIELD ACTIONS ?
├── FUNDING ?
│
└── DEPTH
    ├── Initiative N2
    ├── Occurrence N2
    ├── owner domain
    ├── Jour J
    └── Live
```

Toutes les sections sont optionnelles.

---

# 11. Header

Le header suit :

```text
Makolo | Space / Initiatives | Recherche / filtres utiles | Avatar
```

Compact :

```text
Makolo
Fondation Upendo · Initiatives
[search] [filter] [avatar]
```

Medium/Wide :

```text
Makolo | Fondation Upendo / Initiatives | Toutes mes responsabilités | Recherche | Avatar
```

---

# 12. Icône

L’intention sémantique candidate est :

```text
heart-handshake
```

Le glyph final peut changer selon la charte.

Mais le sens doit rester :

```text
agir ensemble
```

et non :

```text
réseau social
```

---

# 13. N1 — ordre perceptif

La racine doit privilégier :

```text
1. ce qui doit avancer
2. ce qui est en cours de réalisation
3. ce qui arrive
4. les initiatives durables
5. les programmes / événements / actions terrain utiles
6. les profondeurs owner-backed
```

Le détail exact dépend des données.

---

# 14. Continuité collective

La continuité peut utiliser des regroupements humains comme :

```text
À préparer
En cours
À venir
Sur le terrain
À relancer
Bloquées
Terminées
```

mais aucune liste n’est universelle.

Le vocabulaire doit suivre le réel.

---

# 15. Ce qu’est une entrée d’Initiatives

Une entrée UX doit être la plus petite réalité collective cohérente que la personne peut reconnaître et ouvrir.

Exemples :

```text
Campagne de nettoyage du quartier
Programme de mentorat des jeunes
Distribution de kits scolaires
Journée de vaccination
Collecte pour l’ambulance
Forum citoyen
```

Chaque entrée doit être justifiée par un propriétaire canonique.

---

# 16. Initiative durable vs action ponctuelle

Une initiative peut être durable :

```text
Programme mentorat
→ plusieurs mois
→ plusieurs sessions
```

ou ponctuelle :

```text
Nettoyage du quartier
→ samedi
```

Le contrat UX supporte les deux.

---

# 17. Activity

`Activity` reste une base canonique fréquente.

Mais l’écran ne doit pas afficher :

```text
Activity
```

comme jargon si un terme humain est disponible.

Exemple :

```text
Programme mentorat
```

plutôt que :

```text
Activity #...
```

---

# 18. Occurrence

Une réalisation temporelle concrète peut être portée par Occurrence.

Exemple :

```text
Journée de nettoyage
12 octobre · 08:00
```

L’initiative durable peut avoir plusieurs Occurrences.

---

# 19. Actions terrain

`Actions terrain` désigne une Presentation humaine.

Ce n’est pas nécessairement un modèle.

Exemples :

```text
distribution
visite
collecte
nettoyage
sensibilisation
installation
permanence
```

Le backend reste propriétaire de la réalité canonique.

---

# 20. Événements

Un événement peut être visible dans Initiatives lorsqu’il participe réellement au travail collectif.

Exemple :

```text
Forum citoyen
```

Il peut ensuite utiliser la verticale Event.

L’archétype community ne copie pas Event.

---

# 21. Programmes

Un programme réel peut être montré comme structure durable.

Exemple :

```text
Programme mentorat jeunesse
```

Il peut contenir :

- sessions ;
- participants ;
- ressources ;
- groupes ;
- Access ;
- autres réalités.

Mais l’expérience reste Programme.

---

# 22. N1 — représentation

La racine privilégie des rows ou cards modérées.

Exemple row :

```text
Nettoyage du quartier

Samedi · 08:00
42 bénévoles attendus

Préparation en cours                    ›
```

Exemple initiative durable :

```text
Programme mentorat

12 jeunes accompagnés
Prochaine session · mardi

En cours                                ›
```

---

# 23. Média

Un média peut être utile pour :

- reconnaître un lieu ;
- comprendre une action terrain ;
- montrer une ressource ;
- documenter une réalisation ;
- préparer une intervention.

Mais :

```text
photo
≠ post
```

et :

```text
video
≠ feed
```

No Orphan Media s’applique.

---

# 24. Aucun feed

Interdits :

- feed chronologique permanent ;
- stories ;
- likes ;
- réactions de popularité ;
- scroll infini artificiel ;
- « tendances » par engagement ;
- classement des initiatives ;
- boucle de publication sans finalité.

La porte est conçue pour faire avancer l’action collective.

---

# 25. N2 — initiative

Candidate :

```text
← Programme mentorat

Programme mentorat jeunesse

Accompagnement de jeunes de 16 à 22 ans.

État
En cours

Prochaine session
Mardi · 16:00

Préparation
2 éléments restent à préparer

Personnes concernées
selon autorité

Ressources
3

Partenaires
2 liés

[Ouvrir]
```

---

# 26. N2 — composition

Une profondeur peut composer :

```text
identity
purpose
summary
timing
occurrences
place
readiness
people
groups
partners
resources
requirements
funding
capacity
access
journeys
outcomes
media
owner actions
```

uniquement si présents et autorisés.

---

# 27. Personnes concernées

La surface peut montrer des personnes seulement si l’autorité le permet.

Exemple :

```text
Bénévoles attendus
42
```

ou :

```text
Participants
12
```

Mais les listes nominatives ne doivent pas être exposées sans nécessité.

---

# 28. Groups

Un Group peut servir à structurer une initiative.

Exemple :

```text
Équipe terrain Nord
```

Mais la profondeur Initiative ne doit pas transférer implicitement l’autorité du Group.

Membership ≠ Permission.

---

# 29. Partners

Un Partner peut être lié à une initiative.

Exemple :

```text
Partenaire
Centre de santé X
```

Le lien reste relationnel.

La profondeur complète du Partner appartient au domaine relationnel approprié.

---

# 30. Publics

Un public peut aider à comprendre pour qui l’initiative existe.

Exemple :

```text
Pour
jeunes de 16–22 ans
```

Mais l’UX ne crée pas un « audience manager » dans Initiatives.

---

# 31. Funding dans N2

Funding peut apparaître comme contexte si utile :

```text
Financement
7 500 / 10 000 USD mobilisés
```

seulement si le domaine Funding soutient cette vérité.

Pas de faux pourcentage.

Pas de montant agrégé calculé dans l’UI.

---

# 32. N2 — action terrain

Candidate :

```text
← Nettoyage du quartier

Samedi · 08:00
Avenue Lumumba

Préparation
Matériel prêt
Transport bénévoles à confirmer

Équipe terrain
selon autorité

[Ouvrir Jour J]
```

---

# 33. N3 — owner depth

N3 délègue aux propriétaires :

```text
Requirement
Funding
Group
Partner
Access
Capacity
Journey
Payment
Resource
Occurrence
```

Le titre reste humain.

Préférer :

```text
Confirmer le transport des bénévoles
```

à :

```text
JourneyStep 8
```

---

# 34. Création contextuelle

La création primaire peut être :

```text
Nouvelle initiative
```

si le contrat serveur expose cette capacité.

Mais techniquement, la création peut conduire vers Activity ou une verticale adaptée.

Le client n’a pas besoin d’exposer le modèle sous-jacent.

---

# 35. Actions de création secondaires

Depuis une profondeur :

```text
Ajouter une date
Ajouter une action terrain
Associer un groupe
Associer un partenaire
Ajouter une ressource
```

uniquement si :

- la relation est légitime ;
- l’autorité est présente ;
- le domaine propriétaire le permet.

---

# 36. Pas de mega-menu

Interdit :

```text
Créer
├ Activity
├ Occurrence
├ Group
├ Funding
├ Journey
├ Partner
├ Access
├ Resource
└ ...
```

La création suit le contexte humain.

---

# 37. Empty state

Space sans initiative :

```text
Initiatives

Aucune initiative pour le moment.
```

Si autorisé :

```text
[Créer une première initiative]
```

Sinon :

```text
Aucune initiative visible dans votre périmètre.
```

---

# 38. Calm state

Exemple :

```text
Initiatives

Rien ne demande d’intervention immédiate.

En cours
Programme mentorat

À venir
Forum citoyen · 18 octobre
```

Le calme est une réussite.

---

# 39. Search

La recherche spécialisée peut couvrir :

- initiatives ;
- Activities ;
- programmes ;
- événements ;
- actions terrain ;
- lieux ;
- partenaires liés si autorisés ;
- groupes liés si autorisés ;
- personnes selon autorité.

Elle reste limitée au Space.

---

# 40. Filtres

Filtres humains possibles :

```text
À préparer
En cours
À venir
Terrain
Programmes
Événements
Terminées
Par lieu
Par période
Par responsabilité
```

Pas :

```text
activity.vertical
workflow
owner_type
```

comme langage principal.

---

# 41. Géographie

La carte est pertinente lorsque les initiatives sont territoriales.

Exemple :

```text
3 actions cette semaine
dans 2 quartiers
```

Une carte peut aider.

Mais l’archétype community n’impose pas une carte permanente.

---

# 42. Places

Les lieux peuvent représenter :

- quartier ;
- centre ;
- école ;
- terrain ;
- point de distribution ;
- lieu d’événement.

Le lieu reste propriétaire de ses faits géographiques.

---

# 43. Calendar / temporalité

Une lecture calendrier peut être utile si plusieurs Occurrences existent.

Mais Initiatives ne devient pas un calendrier générique.

Le calendrier est une vue.

Pas la vérité.

---

# 44. Hiérarchie perceptive

N1 :

```text
CURRENT COLLECTIVE MOVEMENT      P2/P3
NEXT REAL ACTION                 P2/P3
INITIATIVE IDENTITY              P2
TIME / PLACE / PEOPLE SUMMARY    P1/P2
RELATIONAL CONTEXT               P1
```

N2 :

```text
CURRENT MEANING / BLOCKER        P3
NEXT LEGITIMATE ACTION           P2/P3
CONTEXT                          P1/P2
SUPPORT                          P1
```

---

# 45. No popularity

L’ordre ne dépend jamais :

- likes ;
- vues ;
- commentaires ;
- partage social ;
- popularité.

Il peut dépendre de :

```text
préparation
temps
conséquence
responsabilité
continuité
autorité
```

avec résultat explicable.

---

# 46. Now promotion

Une initiative peut produire une Situation Now :

```text
Distribution demain
200 kits attendus
Transport non confirmé
[Résoudre]
```

Initiatives conserve le contexte durable.

Now porte l’attention.

---

# 47. Découvrir handoff

Découvrir peut proposer :

- partenaire ;
- lieu ;
- financement ;
- ressource ;
- programme ;
- opportunité.

Une exploration peut être liée à une initiative existante.

---

# 48. Nous handoff

La profondeur Initiative peut ouvrir :

```text
Groupe bénévoles
Partenaire X
Responsable Y
```

vers Nous / relations appropriées.

Mais Initiatives ne possède pas ces relations.

---

# 49. Piloter handoff

Piloter peut prendre en charge :

- historique ;
- impact agrégé ;
- financement ;
- tendances ;
- allocation ;
- charge ;
- performance.

Initiatives reste tournée vers l’action.

---

# 50. Jour J

Une Occurrence admissible peut ouvrir Jour J.

Exemple :

```text
Journée de distribution
Aujourd’hui · 09:00

[Ouvrir Jour J]
```

Le client ne décide pas seul l’admission.

---

# 51. Live

Live appartient à Jour J.

Une initiative de six mois n’est pas Live pendant six mois.

Seule une réalisation actuelle suffisamment observée peut avoir une projection Live.

---

# 52. Plusieurs Jour J

Le Space peut avoir plusieurs actions terrain simultanées.

Exemple :

```text
3 distributions aujourd’hui
```

Chaque Occurrence garde son propre Jour J.

Le Space entier ne devient pas Live.

---

# 53. Readiness

Readiness reste dérivée.

Initiatives peut montrer :

```text
Prêt
2 éléments à préparer
Bloqué par autorisation
```

si cela vient de faits propriétaires.

Pas de statut Readiness local arbitraire.

---

# 54. Blockers

Un blocker doit être rattaché à ce qu’il bloque.

Exemple :

```text
Autorisation municipale manquante
bloque l’action terrain de samedi
```

Pas de liste globale « Problèmes ».

---

# 55. Capacity

Capacity peut répondre à :

```text
combien de places ?
combien de kits ?
combien de bénéficiaires ?
combien de ressources ?
```

seulement lorsque le domaine Capacity est approprié.

---

# 56. Access

Access peut apparaître pour :

- entrée à un événement ;
- distribution contrôlée ;
- accès à une ressource ;
- participation conditionnée.

Access reste un droit canonique.

---

# 57. Requirements

Une initiative peut avoir des Requirements.

Exemple :

```text
Autorisation municipale
preuve d’identité
document partenaire
```

Mais Initiatives ne crée pas `InitiativeRequirement`.

---

# 58. Resources

Ressources peuvent inclure :

- documents ;
- matériel ;
- guides ;
- liens ;
- plans ;
- fichiers.

Le contenu doit être relié à une action ou un contexte.

No Orphan Content.

---

# 59. Outcomes

Une initiative peut avoir un résultat réel.

Exemple :

```text
500 kits remis
```

si la vérité est observée et propriétaire.

Ne pas confondre :

```text
activité terminée
≠ impact prouvé
```

---

# 60. Historique

Les initiatives terminées restent accessibles.

Mais l’historique n’est pas la racine.

Exemple :

```text
Terminées
Voir l’historique
```

---

# 61. Etats UX

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
```

---

# 62. Loading

Préserver le contenu connu.

Utiliser un refresh discret.

Éviter le flash destructeur.

---

# 63. Offline

Le snapshot peut conserver :

- initiatives connues ;
- dates ;
- lieux ;
- relations déjà synchronisées ;
- ressources locales autorisées.

Mais :

```text
offline snapshot
≠ état actuel du terrain
```

---

# 64. Stale

Si la fraîcheur compte :

```text
Dernière mise à jour · 08:15
```

Le message doit rester local.

Pas de bannière anxiogène globale si non nécessaire.

---

# 65. Partial failure

Exemple :

```text
Initiatives
✓ programmes visibles
✓ événements visibles

Financement
Impossible d’actualiser.
[Réessayer]
```

La surface ne s’effondre pas.

---

# 66. Permission loss

Si l’autorité change :

- retirer les actions ;
- masquer les données devenues interdites ;
- revalider N2/N3 ;
- conserver le contexte non sensible ;
- éviter toute fuite.

---

# 67. Compact

Compact :

```text
single pane
bottom navigation
sections verticales
rows / cards modérées
N2 par navigation
```

---

# 68. Medium

Medium peut utiliser :

```text
field + preview
```

si la sélection bénéficie de conservation cognitive.

---

# 69. Wide

Wide peut utiliser :

```text
NAV | INITIATIVES | FOCUS N2
```

après sélection.

La racine ne devient pas un dashboard d’association.

---

# 70. Very Wide

Interdits :

- KPI wall ;
- activity heatmap sans but ;
- « engagement stats » comme centre ;
- mur de photos ;
- liste membres + initiatives + finance en simultané sans besoin.

Le surplus d’espace sert à préserver contexte et profondeur.

---

# 71. Adaptive conservation

Conserver :

- surface ;
- initiative sélectionnée ;
- scroll ;
- query ;
- filtres ;
- responsabilité ;
- profondeur ;
- brouillon ;
- carte si utilisée.

---

# 72. Back

Retour N2 → N1 doit préserver :

- section ;
- scroll ;
- filtre ;
- recherche ;
- sélection.

---

# 73. Resume

À la reprise :

1. rendre snapshot sûr ;
2. actualiser ;
3. revalider l’autorité ;
4. retirer les faits devenus privés ;
5. préserver le contexte.

---

# 74. Deep links

Deep link :

```text
Makolo
→ Space
→ Initiatives
→ initiative / occurrence
```

L’Actor Context doit être restauré explicitement.

---

# 75. Mobile behavior

Bottom sheets peuvent servir pour :

- filtres ;
- actions secondaires ;
- carte ;
- choix rapides ;
- relation à un groupe / partenaire.

Pas pour cacher l’action principale.

---

# 76. Native mobile

Utiliser les capacités natives quand pertinentes :

- caméra ;
- share sheet ;
- photo picker ;
- localisation ;
- notifications ;
- permissions.

La permission est demandée au moment du besoin.

---

# 77. Partage

Une initiative peut être partageable si sa projection est publique.

Mais :

```text
partage
≠ exposition des données internes
```

Une URL publique ne contient jamais implicitement :

- notes privées ;
- participants privés ;
- permissions ;
- données de bénéficiaires.

---

# 78. Media documentation

Une action terrain peut générer des médias.

Mais la Presentation doit toujours répondre :

```text
pourquoi ce média est ici ?
```

Exemples légitimes :

- preuve contextuelle ;
- préparation ;
- reconnaissance du lieu ;
- résultat documenté.

---

# 79. Local-first

Le client local peut conserver selon contrat :

- initiatives synchronisées ;
- Occurrences ;
- lieux ;
- ressources ;
- drafts ;
- sélection ;
- contexte ;
- certaines relations.

Le serveur reste autoritaire pour :

- permissions ;
- Mandates ;
- Access ;
- Capacity partagée ;
- financement partagé ;
- actions multi-acteurs ;
- Jour J admission ;
- Live.

---

# 80. Mutations sensibles

Une mutation sensible doit être revalidée côté serveur.

Exemples :

- affecter un responsable ;
- accepter un bénéficiaire ;
- publier une Activity ;
- valider une distribution ;
- accorder un Access ;
- consommer Capacity ;
- changer financement ;
- conclure un résultat.

---

# 81. Feedback

Préférer :

> **Action terrain créée. Il reste à préciser le lieu.**

à :

> Success.

Préférer :

> **Partenaire associé.**

seulement après vérité serveur si la relation est partagée.

---

# 82. Recherche globale vs spécialisée

Recherche globale Space :

```text
Rechercher dans cet Espace
```

Recherche Initiatives :

```text
Rechercher une initiative, un programme ou une action terrain
```

Les deux ont des responsabilités différentes.

---

# 83. API / projection actuelle

Le runtime Space Métier expose déjà une projection de travail commune.

Le contrat Initiatives peut consommer les champs transversaux :

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

Le client ne doit pas reconstruire l’autorité.

---

# 84. Runtime current gap

La projection commune actuelle organise surtout les objets selon :

```text
preparation
upcoming
active
blocked
completed
```

Ce découpage peut alimenter Initiatives.

Mais il ne suffit pas à exprimer toute la grammaire community :

```text
initiatives
actions terrain
programmes
events
Funding contextuel
relations liées
```

Le contrat UX décrit la cible Presentation.

Il ne déclare pas que tous ces champs existent déjà dans le payload.

---

# 85. Runtime archetype

Le preset courant `community` établit déjà :

```text
primary_business_label = Initiatives
activities_label = Activités & initiatives
```

et met notamment en avant :

```text
activities
groups
crm
funding
partners
recognition
trust
growth
analytics
automation
```

Mais cette liste de modules n’est pas la structure de l’écran.

---

# 86. Modules ≠ N1

Invariant :

```text
featured_modules
≠ sections visibles obligatoires
```

Le fait que `groups` ou `crm` soient importants pour un Space community ne justifie pas :

```text
onglet Groups
onglet CRM
```

dans Initiatives.

---

# 87. Structure vs continuité

Pour Community :

```text
STRUCTURE
→ initiatives durables
→ programmes
→ Activities

CONTINUITÉ
→ préparation
→ actions terrain
→ événements actuels
→ prochaines réalisations
→ blockers
```

Les deux peuvent s’entrecroiser.

Elles ne doivent pas être confondues.

---

# 88. Anti-features

Initiatives ne doit jamais devenir :

- réseau social ;
- feed ;
- mur de publications ;
- stories ;
- timeline communautaire ;
- CRM ;
- annuaire membres ;
- page partenaires ;
- page Groups ;
- tableau Funding permanent ;
- dashboard d’impact ;
- page Analytics ;
- todo list ;
- kanban universel ;
- ERP associatif ;
- système de popularité ;
- classement de bénévoles ;
- système de badges d’engagement ;
- média gallery orpheline ;
- copie de Project Management ;
- copie de Journey ;
- source de Permission ;
- source de Readiness ;
- page où tout devient une Initiative.

---

# 89. Goldens

## G-INI-01 — Compact / Content

Fixture :

```text
Fondation Upendo
Initiatives

À préparer
Distribution de kits
Samedi · 08:00
Transport à confirmer

En cours
Programme mentorat
12 jeunes accompagnés

À venir
Forum citoyen
18 octobre
```

---

## G-INI-02 — Compact / Empty

```text
Initiatives

Aucune initiative pour le moment.

[Créer une première initiative]
```

si autorisé.

---

## G-INI-03 — Compact / Calm

```text
Tout avance normalement.

En cours
Programme mentorat

À venir
Forum citoyen
```

Pas de faux problème.

---

## G-INI-04 — Compact / Action terrain

```text
Nettoyage du quartier
Samedi · 08:00
Avenue Lumumba

Préparation
Matériel prêt
Transport à confirmer
```

---

## G-INI-05 — Medium / selected

```text
INITIATIVES | PREVIEW
field       | Programme mentorat
```

---

## G-INI-06 — Wide / N2

```text
NAV | INITIATIVES | PROGRAMME
```

N2 conserve hiérarchie.

---

## G-INI-07 — Funding contextual

```text
Collecte ambulance
6 500 / 10 000 USD
```

uniquement si vérité owner-backed.

Pas de faux progrès.

---

## G-INI-08 — Relationship safe

Initiative liée à :

```text
Groupe bénévoles
Partenaire Centre X
```

sans fuite d’autorité.

---

## G-INI-09 — Offline

Snapshot + fraîcheur.

Aucune affirmation terrain Live.

---

## G-INI-10 — textScale 1.6

Aucun truncation essentielle.

Actions accessibles.

---

# 90. Tests Golden

Viewports :

```text
360 × 800
430 × 932
834 × 1112
1440 × 900
1728 × 1117
```

Text scale :

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
```

---

# 91. Accessibility

MUST :

- hiérarchie sémantique ;
- tap targets suffisants ;
- keyboard / focus desktop ;
- text scaling ;
- Reduce Motion ;
- état non dépendant de la couleur ;
- feedback lisible ;
- ordre logique ;
- actions nommées humainement.

---

# 92. Couleurs

Palette Makolo :

```text
#5232DB
#2B176E
#FF704D
#FAF7F5
#0F172A
```

La couleur n’invente pas l’urgence.

---

# 93. Motion

Motion peut aider à :

- ouvrir N2 ;
- changer filtre ;
- associer une relation ;
- confirmer une action ;
- revenir à la racine.

Pas d’animation d’engagement.

---

# 94. Recognition test

En 500 ms, l’utilisateur doit reconnaître :

```text
je suis dans ce Space
+
je suis dans Initiatives
+
voici ce qui avance
```

---

# 95. Blur test

Même texte flouté :

- le champ principal doit rester identifiable ;
- aucune grille KPI ne domine ;
- le chrome reste secondaire ;
- l’action principale reste claire.

---

# 96. Deletion test

Pour chaque élément :

> Si je le supprime, perd-on compréhension ou capacité d’action ?

Si non, il ne doit probablement pas être au N1.

---

# 97. Competition test

Deux initiatives ne doivent pas chacune être P3 en même temps.

La surface peut avoir plusieurs entrées importantes.

Mais la hiérarchie globale reste calme.

---

# 98. Invariants gelés

1. La porte visible est `Initiatives`.
2. `community` est un archétype, pas un domaine propriétaire.
3. `Initiative` UX n’est pas un nouveau modèle métier.
4. Activities peuvent porter des initiatives.
5. Occurrence reste distincte d’Activity.
6. Events peuvent être composés.
7. Actions terrain sont une grammaire Presentation.
8. Programmes réels peuvent être composés.
9. Groups restent surtout relationnels.
10. Publics restent surtout relationnels.
11. Partners restent surtout relationnels.
12. Funding change de placement selon le contexte.
13. Funding ≠ initiative par défaut.
14. Le Viewer est Profile.
15. Actor Context = Space.
16. Membership ≠ Permission.
17. Assignment ≠ Permission.
18. Responsibility ≠ authority.
19. N1 parle action collective.
20. N2 explique une initiative réelle.
21. N3 délègue au propriétaire.
22. Pas de feed.
23. Pas de Stories.
24. Pas de likes.
25. Pas de popularité.
26. Pas de média orphelin.
27. Pas de dashboard KPI à la racine.
28. Now reste la surface d’attention.
29. Nous reste la surface relationnelle/institutionnelle.
30. Piloter reste la surface analytique.
31. Jour J appartient à une Occurrence admissible.
32. Live appartient à Jour J.
33. Le Space entier ne devient pas Live.
34. Readiness reste dérivée.
35. Access reste droit canonique.
36. Capacity répond à combien.
37. Funding reste propriétaire de ses faits.
38. Presentation représente, ne possède pas.
39. Offline ne crée pas de vérité actuelle.
40. Le serveur revalide toute action sensible.

---

# 99. Critères de sortie serveur

Une implémentation serveur conforme doit :

- identifier le Space et son archetype community ;
- exposer `Initiatives` comme langage primaire ;
- filtrer permission-first ;
- supporter scope Space / Activity limité ;
- exposer les Activities pertinentes ;
- exposer Occurrences pertinentes ;
- permettre la composition owner-backed ;
- ne pas transférer authority via Group/Partner ;
- exposer des capabilities serveur ;
- supporter états partiels ;
- supporter fraîcheur ;
- ne pas inventer Funding / impact ;
- ne pas exiger un modèle Initiative.

---

# 100. Critères de sortie Web

Le Web est conforme lorsque :

- N1 est immédiatement reconnaissable ;
- pas de feed ;
- pas de dashboard ;
- actions terrain et programmes sont lisibles ;
- Groups/Partners restent contextuels ;
- recherche et filtres sont humains ;
- N2/N3 sont progressifs ;
- Back conserve contexte ;
- les permissions sont respectées ;
- plusieurs Occurrences restent distinctes ;
- Jour J est un handoff, pas un onglet.

---

# 101. Critères de sortie Flutter

Flutter est conforme lorsque :

- Compact est complet ;
- local-first conserve le contexte ;
- offline est honnête ;
- resume revalide ;
- deep links restaurent Space ;
- back gesture conserve sélection/scroll ;
- bottom sheets servent seulement la profondeur légère ;
- camera/location sont demandées au besoin ;
- text scale 1.6 reste utilisable ;
- responsive conserve vérité/priorité.

---

# 102. Tests ciblés

Prévoir :

```text
community root content
community root empty
community root calm
initiative activity visible
programme visible
event visible
field action visible
funding as activity
funding absent when not relevant
group relation safe
partner relation safe
activity-limited viewer
responsibility lens
authority revocation
offline snapshot
deep link
jour j handoff
multiple occurrences
partial failure
textScale 1.6
compact / medium / wide
```

---

# 103. Fixture de référence

```text
Fondation Upendo
Initiatives

À préparer
Distribution de kits scolaires
Samedi · 08:00
Transport à confirmer

En cours
Programme mentorat jeunesse
12 jeunes accompagnés
Prochaine session mardi

À venir
Forum citoyen
18 octobre · Centre communautaire

Actions terrain
Nettoyage avenue Lumumba
Samedi · 07:00

Programmes
Mentorat jeunesse
Santé communautaire
```

Cette fixture n’impose pas ces sections à tous les Spaces.

---

# 104. Fixture avec Funding

```text
Initiatives

Collecte ambulance
Objectif 10 000 USD
6 500 USD mobilisés

Résultat attendu
Financer l’achat de l’ambulance
```

Ce placement n’est correct que si la collecte elle-même est l’Activity portée.

---

# 105. Fixture relationnelle

```text
Programme mentorat

Partenaire
Université X

Groupe
Mentors bénévoles
```

Ces liens ne transfèrent aucune Permission.

---

# 106. Fixture terrain

```text
Distribution de kits

Aujourd’hui · 09:00
École Mwangaza

Préparation
Kits prêts
Équipe terrain confirmée
Accès bénéficiaires à contrôler

[Ouvrir Jour J]
```

---

# 107. Points volontairement ouverts

Restent ouverts :

- libellés exacts selon contexte ;
- représentation finale initiative vs programme ;
- carte par défaut ou optionnelle ;
- traitement visuel du Funding ;
- politique de média détaillée ;
- création `Nouvelle initiative` vers quel owner exact selon type ;
- payload cible complet de community ;
- split breakpoint final ;
- microcopy finale ;
- animations ;
- profondeur publique/privée ;
- analytics de Pilotage ;
- modèle final de partage public ;
- composants Flutter finaux.

Ces points ne remettent pas en cause les invariants.

---

# 108. Références de cadrage

Ce contrat dérive principalement de :

- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_UX_En_Cours_Contrat_Consolide.md`
- `Makolo_UX_Now_Contrat_Consolide.md`
- `Makolo_UX_Decouvrir_Contrat_Consolide.md`
- les contrats local-first/mobile disponibles dans le projet
- le runtime `main` courant lors de la consolidation

Le code, migrations, tests et domaines propriétaires restent la vérité runtime pour l’implémentation.

---

# 109. Formulation finale

> **Initiatives est la porte Métier d’un Space `community`. Elle rend visible ce que le collectif fait réellement avancer : initiatives durables, Activities, programmes, événements, actions terrain et autres réalisations légitimes. Elle ne crée pas un nouveau modèle Initiative, ne transforme pas Groups, Publics ou Partners en travail métier, et ne force pas Funding à une place unique. Elle privilégie l’action collective réelle, la continuité, le terrain et le résultat plutôt que la publication, la popularité ou l’engagement numérique. La racine reste lisible et modérée ; N2 explique la réalité ; N3 délègue aux propriétaires ; Jour J accompagne les Occurrences actuelles ; l’offline conserve la compréhension sans inventer le présent ; et l’autorité reste vérifiée côté serveur.**
