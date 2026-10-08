# Makolo — Space Métier `media` / **Productions**
## Contrat UX consolidé — N1, N2/N3, hiérarchie, représentations, états, adaptive, local-first et handoffs

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence pour l’archétype Space `media`  
**Porte visible :** **Productions**  
**Contexte acteur :** Space  
**Viewer :** Profile authentifié agissant explicitement au nom du Space  
**Portée :** Web, mobile Flutter, tablette/desktop adaptatif, Presentation, projections serveur et continuité locale  
**Nature :** contrat UX, de projection et d’implémentation ; ne crée aucun nouveau domaine métier  
**Base runtime vérifiée :** `main@d5b85ee4c737f09da7d1b2e27f7bae9d14d40131`  
**Promesse produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 0. Objet

Ce document fixe la manière dont la porte **Métier** doit être visible et utilisable pour un Space dont l’archétype est :

```text
media
```

Le libellé visible primaire est :

```text
Productions
```

Le contrat part du cadre déjà fixé dans l’architecture Space :

```text
Productions
├── productions / Activities
├── événements
├── prestations éventuelles
└── Occurrences
```

Le même cadre impose :

```text
Audiences
Publics
Partners
→ surtout relations ou possibilités
```

et :

> **Makolo ne transforme pas un média en réseau social générique.**

Le runtime courant confirme l’archétype :

```text
label = Média / journalisme
primary_business_label = Productions
activities_label = Productions & activités
```

avec notamment des capacités ou modules potentiels autour de :

```text
activities
crm
audiences
groups
promotions
growth
partners
trust
analytics
```

Ces modules ne sont pas la structure N1 de l’écran.

---

# 1. Question humaine

La porte **Productions** répond à :

> **Qu’est-ce que nous produisons réellement, qu’est-ce qui se prépare, qu’est-ce qui doit être diffusé ou réalisé, et qu’est-ce qui continue ?**

Elle doit permettre de comprendre rapidement :

```text
ce que le Space produit
+
ce qui est en préparation
+
ce qui prend forme
+
ce qui arrive
+
ce qui doit être réalisé ou rendu disponible
+
où entrer pour poursuivre le travail
```

Elle ne demande pas :

> Qu’est-ce qui a le plus de vues ?

Elle ne demande pas :

> Qu’avons-nous posté récemment ?

Elle ne demande pas :

> Quelle audience faut-il faire rester plus longtemps ?

---

# 2. Pourquoi `Productions`

Le terme **Productions** donne au Space `media` une grammaire de travail.

Il peut représenter, selon les vérités réellement portées par le Space :

```text
production éditoriale
production audiovisuelle
production sonore
production journalistique
programme média
couverture
série
émission
édition
autre Activity média réelle
```

Ces exemples sont des traductions humaines possibles.

Ils ne créent aucun type backend obligatoire.

---

# 3. Production UX ≠ modèle métier

Invariant :

```text
PRODUCTION UX
≠ nouveau modèle Production obligatoire
```

Une Production visible peut être soutenue par :

```text
Activity
Occurrence
Resource
Media binding
Event
Service
Journey
Offer / Commerce si réel
Obtention si réel
Project / Dossier si légitime
autres propriétaires canoniques
```

La Presentation compose.

Elle ne possède pas.

---

# 4. Production ≠ fichier média

Invariant majeur :

```text
Production
≠ image
≠ vidéo
≠ audio
≠ document
```

Un fichier peut être :

- ressource ;
- livrable ;
- représentation ;
- source ;
- pièce ;
- support ;
- média lié à une Production.

Il ne devient pas une Production simplement parce qu’il est audiovisuel.

---

# 5. Media binding ≠ post

Makolo n’a pas besoin d’inventer :

```text
Post
Story
Reel
FeedItem
```

pour rendre une Production visible.

Un média lié à une Production garde :

```text
contexte
+
propriétaire
+
finalité
```

No Orphan Content / Media s’applique.

---

# 6. Personnalité UX

La personnalité de **Productions** est :

> **travail éditorial réel + continuité de production + représentation médiatique contextualisée**

La surface doit être :

- professionnelle ;
- structurée ;
- visuelle lorsque cela aide ;
- éditoriale sans devenir un CMS générique ;
- médiatique sans devenir un réseau social ;
- capable de gérer plusieurs productions ;
- capable de rester calme ;
- orientée résultat réel.

---

# 7. Relation avec Maintenant

`Maintenant` répond :

> Qu’est-ce qui mérite notre attention maintenant ?

Exemple :

```text
Interview prévue à 15:00
Autorisation non reçue
[Résoudre]
```

peut apparaître dans Maintenant.

La Production reste dans **Productions**.

---

# 8. Relation avec Découvrir

Découvrir peut aider à trouver :

- sujet ;
- lieu ;
- événement ;
- partenaire ;
- opportunité ;
- financement ;
- ressource ;
- prestation ;
- collaboration ;
- autre possibilité réelle.

Une possibilité découverte ne devient pas automatiquement une Production.

---

# 9. Relation avec Nous

`Nous` porte notamment :

- identité du média ;
- équipe ;
- responsabilités ;
- groupes ;
- publics ;
- partenaires ;
- relations ;
- confiance.

`Productions` porte ce que ce Space produit effectivement.

---

# 10. Relation avec Piloter

Piloter peut analyser :

- performance ;
- portée ;
- revenus ;
- abonnements si domaine réel ;
- audience ;
- coûts ;
- charge ;
- tendances ;
- autres analytics.

Productions ne devient jamais un dashboard Analytics permanent.

---

# 11. Audiences et publics

Les sources fixent :

```text
Audiences
Publics
→ surtout relations ou possibilités
```

Donc :

```text
Audience
≠ Production
```

Une Production peut avoir un public concerné.

Mais la racine ne devient pas :

```text
Audiences
Followers
Subscribers
Segments
```

comme centre du Métier.

---

# 12. Partners

Un Partner peut contribuer à une Production :

- coproducteur ;
- lieu ;
- institution ;
- prestataire ;
- distributeur ;
- autre relation réelle.

Mais :

```text
Partner
≠ Production
```

et la relation n’accorde aucune Permission implicite.

---

# 13. Promotions et Growth

Le runtime peut présenter `promotions` et `growth` comme modules pertinents à l’archétype.

Cela ne signifie pas :

```text
Promotions
Growth
→ sections N1 obligatoires
```

Ils peuvent soutenir une Production lorsque le contexte le justifie.

La Production reste première.

---

# 14. Actor Context

Le contexte est :

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
Avatar = Sarah
Actor Context = Radio Horizon
Métier = Productions
```

L’Avatar reste la personne.

---

# 15. Responsabilité et autorité

Une personne peut avoir :

```text
responsabilité
→ Rédaction
```

mais :

```text
Permission
→ seulement certaines Activities
```

La responsabilité peut réduire la lecture.

Elle ne doit jamais augmenter l’autorité.

---

# 16. N1 — structure conceptuelle

```text
PRODUCTIONS
│
├── HEADER
│
├── CONTEXT
│   ├── Space
│   └── responsibility lens
│
├── CURRENT PRODUCTION FIELD
│   ├── À préparer ?
│   ├── En production ?
│   ├── À réaliser ?
│   ├── À venir ?
│   └── selon vérité propriétaire
│
├── PRODUCTION PORTFOLIO
│   └── productions / Activities
│
├── EVENTS ?
├── PRESTATIONS ?
├── OCCURRENCES ?
│
└── DEPTH
    ├── Production N2
    ├── Occurrence N2
    ├── Resource / media depth
    ├── Event / Service owner
    ├── Jour J
    └── Live
```

Cette structure n’est pas un schéma de base de données.

---

# 17. Header

Le header suit le contrat Space :

```text
Makolo | Space / Productions | Recherche / filtres utiles | Avatar
```

Compact :

```text
Makolo
Radio Horizon · Productions
[search] [filter] [avatar]
```

Medium/Wide :

```text
Makolo | Radio Horizon / Productions | Toutes mes responsabilités | Recherche | Avatar
```

---

# 18. Icône

Intention sémantique candidate :

```text
newspaper
```

Le glyph peut être ajusté.

Il doit évoquer :

```text
production / édition / média
```

et non :

```text
réseau social
```

---

# 19. N1 — ordre perceptif

La racine peut privilégier :

```text
1. ce qui est actuellement en production
2. ce qui doit être préparé
3. ce qui doit être réalisé / diffusé prochainement
4. productions durables
5. événements
6. prestations éventuelles
```

Cet ordre reste dépendant des faits réels.

---

# 20. Sections visibles

Sections candidates :

```text
En production
À préparer
À venir
À réaliser
Productions
Événements
Prestations
Terminées
```

Ces libellés sont Presentation.

Ils ne sont pas des enums métier obligatoires.

Toutes les sections ne doivent pas être affichées partout.

---

# 21. `En production`

`En production` doit être owner-backed.

Il peut dériver d’une Activity, d’un Journey, d’une préparation ou d’une autre vérité métier.

Le client ne crée pas un nouveau status :

```text
PRODUCING
```

par simple commodité UX.

---

# 22. `À préparer`

Exemples illustratifs :

```text
Reportage du marché central
Lieu confirmé
Autorisation à obtenir
```

ou :

```text
Émission spéciale
Invité confirmé
Brief à compléter
```

Ces formulations sont des exemples UX.

Les propriétaires canoniques restent les sources de vérité.

---

# 23. `À venir`

Une production peut avoir une Occurrence future :

```text
Débat public
18 octobre · 19:00
```

ou une date de réalisation réellement établie.

Une Activity durable n’est pas « à venir » dans son ensemble uniquement parce qu’elle est publiée.

---

# 24. `À réaliser`

Cette section peut représenter une production prête à être accomplie ou livrée.

Elle n’est pas obligatoire.

Son usage dépend du métier réel.

Exemple :

```text
Interview finale
Demain · 11:00
```

---

# 25. Production portfolio

La structure durable peut être présentée sous :

```text
Productions
```

ou un regroupement plus naturel.

Une Production durable peut contenir plusieurs Occurrences.

---

# 26. Représentation d’une Production

Exemple textuel :

```text
Journal du soir

Édition du 18 octobre
Préparation en cours

Prochaine étape
Valider le conducteur
```

Exemple média :

```text
[visuel contextuel]

Série « Villes en mouvement »

Épisode en préparation
Prochaine réalisation · vendredi
```

Le média reste support de compréhension.

---

# 27. Row vs Card

La racine privilégie :

- row pour continuité ;
- card modérée quand un visuel aide réellement ;
- group pour séries ou productions liées ;
- media preview seulement lorsque utile.

Elle ne doit pas devenir une grille de miniatures sans hiérarchie.

---

# 28. Grid

Une grid peut être légitime pour reconnaître des productions.

Mais :

```text
grid
≠ feed
```

Elle doit conserver :

- structure ;
- section ;
- contexte ;
- fin ;
- actions ;
- sélection.

---

# 29. List

La list est préférée pour :

- préparation ;
- échéances ;
- production active ;
- événements ;
- prestations ;
- état ;
- blockers.

Une même surface peut proposer list/grid si cela sert réellement le travail.

---

# 30. Production et média

Une Production peut avoir :

```text
image
audio
video
document
thumbnail
cover
preview
```

si le domaine ou Presentation fournit ces bindings.

Le média n’est pas obligatoire.

---

# 31. No Orphan Media

Chaque média doit répondre à :

```text
quelle Production ?
quelle fonction ?
quelle provenance ?
quelle visibilité ?
```

Un fichier sans contexte n’est pas promu en N1.

---

# 32. N2 — Production

Candidate :

```text
← Journal du soir

Journal du soir
Édition du 18 octobre

État
Préparation en cours

Réalisation
Aujourd’hui · 18:30

Prochaine étape
Valider le conducteur

Ressources
5

Participants / intervenants
selon autorité

Événement lié
si réel

[Actions contextuelles]
```

---

# 33. N2 — composition

Une Production peut composer :

```text
identity
summary
media
timing
occurrences
place
readiness
resources
requirements
people
groups
partners
events
services
offers si réelles
access
capacity
journeys
owner actions
```

uniquement si présents et autorisés.

---

# 34. Production durable vs Occurrence

Invariant :

```text
Production
≠ Occurrence
```

Exemple :

```text
Émission hebdomadaire
→ Production durable

Édition du 18 octobre
→ Occurrence
```

L’UX ne doit pas dupliquer la Production comme si chaque Occurrence était une nouvelle identité durable.

---

# 35. Occurrence N2

Candidate :

```text
← Journal du soir

Édition du 18 octobre
18:30

Studio A

Préparation
Conducteur prêt
Invité confirmé

[Ouvrir Jour J]
```

si Jour J est admissible.

---

# 36. Séries et collections

Une série peut être une composition de Presentation si les relations canoniques le permettent.

Mais :

```text
Series
≠ nouveau modèle obligatoire
```

Aucune structure persistante n’est imposée ici.

---

# 37. Événements

Un Event peut être :

- émission publique ;
- débat ;
- projection ;
- conférence ;
- rencontre ;
- autre événement réel.

Il apparaît seulement s’il existe réellement.

---

# 38. Prestations éventuelles

Un Space média peut fournir des prestations :

- production pour tiers ;
- couverture ;
- enregistrement ;
- prestation éditoriale ;
- autre service réel.

Si Service est utilisé, la profondeur peut reprendre la grammaire Prestations.

Mais la racine reste Productions si `media` est le centre de gravité.

---

# 39. Offers et Commerce

Les sources ne placent pas Offers comme composant primaire de `media`.

Donc le contrat ne les impose pas.

Si le Space opère réellement Commerce, Offer/Order/Payment peuvent apparaître en profondeur ou via Operational Footprint.

Ils ne sont pas inventés pour monétiser toute Production.

---

# 40. Audience ≠ résultat de production

Une Production peut viser ou atteindre un public.

Mais :

```text
audience élevée
≠ production accomplie
```

et :

```text
audience faible
≠ production échouée
```

sans contrat métier explicite.

---

# 41. Analytics ≠ vérité de Production

Les Analytics peuvent aider à Piloter.

Ils ne doivent pas devenir :

```text
score de Production
```

universel.

Pas de score global.

---

# 42. Trust

Trust peut compter dans des contextes journalistiques ou institutionnels.

Mais la présence du module Trust dans le preset ne transforme pas chaque Production en badge de confiance.

Trust reste son domaine.

---

# 43. N3 — owner depth

N3 délègue vers :

```text
Activity
Occurrence
Resource
Requirement
Journey
Event
Service
Partner
Group
Access
Capacity
Offer
Payment
Trust
```

selon ce qui existe réellement.

---

# 44. Création contextuelle

Action candidate :

```text
Nouvelle production
```

si capability serveur.

Cette action peut créer ou préparer l’owner approprié.

Le client n’a pas besoin d’exposer :

```text
Create Activity
```

comme vocabulaire principal.

---

# 45. Actions secondaires

Depuis N2 :

```text
Ajouter une réalisation
Ajouter une ressource
Ajouter un média
Associer un événement
Associer un partenaire
Préparer une prestation
```

uniquement si légitimes.

---

# 46. Pas de mega-menu

Interdit :

```text
Créer
├ Activity
├ Occurrence
├ Media
├ Event
├ Service
├ Group
├ Partner
├ Journey
└ ...
```

La création reste contextuelle.

---

# 47. Search

Recherche spécialisée candidate :

```text
Rechercher une production, un événement ou une réalisation
```

Elle peut porter sur :

- Productions ;
- Occurrences ;
- Events ;
- Services ;
- lieux ;
- ressources ;
- partenaires selon autorité.

---

# 48. Filtres

Filtres humains possibles :

```text
En production
À préparer
À venir
À réaliser
Événements
Prestations
Terminées
Par période
Par lieu
Par responsabilité
```

Ne pas exposer la taxonomie backend.

---

# 49. Publics et Search

Rechercher un public ou une audience est une problématique relationnelle / Discover / Pilotage selon contexte.

Ce n’est pas nécessairement la recherche primaire de Productions.

---

# 50. Hiérarchie perceptive

N1 :

```text
PRODUCTION IDENTITY / CURRENT STATE    P2
IMPORTANT CONSEQUENCE                  P2/P3
NEXT LEGITIMATE ACTION                 P2/P3
MEDIA SUPPORT                          P1/P2
TIME / PLACE                           P1
AUDIENCE / RELATIONS                   P0/P1 sauf besoin
```

---

# 51. Le média ne domine pas par défaut

Une thumbnail peut faciliter la reconnaissance.

Mais si l’action principale est :

```text
Valider le conducteur
```

cette action peut devenir P3.

Le visuel reste support.

---

# 52. Maintenant handoff

Exemple :

```text
Édition de 18:30
Invité annulé.
[Réorganiser]
```

peut devenir une Situation Now.

La Production reste dans Productions.

---

# 53. Découvrir handoff

Découvrir peut être utilisé depuis une Production pour chercher :

- invité ;
- lieu ;
- partenaire ;
- ressource ;
- opportunité ;
- financement ;
- événement ;
- collaboration.

Le contexte de la Production doit pouvoir être conservé.

---

# 54. Nous handoff

Productions peut ouvrir vers :

- responsable ;
- équipe ;
- groupe ;
- partenaire ;
- relation.

Mais ces entités restent propriétaires de Nous/relations.

---

# 55. Piloter handoff

Piloter peut exploiter :

- audience ;
- portée ;
- revenus ;
- coûts ;
- performance ;
- cadence ;
- charge ;
- qualité de service ;
- tendances.

Productions ne doit pas afficher ces métriques comme centre permanent.

---

# 56. Jour J

Une Occurrence médiatique actuelle peut ouvrir Jour J.

Exemples illustratifs :

```text
édition live
enregistrement
débat
couverture événementielle
projection
diffusion programmée avec opération réelle
```

Le client ne décide pas seul l’admission.

---

# 57. Live

Live appartient à Jour J.

Important :

```text
contenu diffusé
≠ automatiquement Live Makolo
```

Makolo Live représente ce qui est effectivement observé ou suffisamment établi comme se déroulant maintenant dans l’Occurrence.

---

# 58. Live médiatique

Live peut comporter une dimension médiatique seulement si une source réelle existe.

Le contrat Jour J/Live distingue :

```text
planned
estimated
observed
live
unknown
unavailable
```

Une heure prévue n’est pas un fait Live.

---

# 59. Plusieurs productions actuelles

Un Space média peut opérer plusieurs Occurrences simultanément.

Exemple :

```text
2 studios actifs
1 couverture terrain
```

Chaque Occurrence garde son Jour J.

Le Space entier ne devient pas Live.

---

# 60. Readiness

Readiness reste dérivée.

Productions peut dire :

```text
Prêt
2 éléments à préparer
Bloqué par autorisation
```

si owner-backed.

Pas de nouveau `ProductionReadiness`.

---

# 61. Requirements

Une Production peut dépendre de :

- autorisation ;
- ressource ;
- validation ;
- document ;
- accord ;
- autre Requirement réel.

Le contrat ne crée pas de type spécifique obligatoire.

---

# 62. Resources

Resources peuvent inclure :

- documents ;
- scripts ;
- conducteurs ;
- fichiers ;
- briefs ;
- médias ;
- références ;
- plans ;
- autres ressources.

Posséder un fichier ne signifie pas satisfaire automatiquement un Requirement.

---

# 63. Proof

Un fichier média n’est pas automatiquement Proof.

Exemple :

```text
vidéo enregistrée
≠ preuve canonique
```

sauf contrat propriétaire explicite.

---

# 64. Access

Access peut s’appliquer à :

- événement ;
- studio ;
- projection ;
- ressource ;
- contenu sous droit ;
- autre droit réel.

Access reste distinct d’AccessCredential.

---

# 65. Capacity

Capacity peut servir pour :

- places ;
- sessions ;
- capacité de production ;
- nombre de participants ;
- autre `combien ?` défendable.

Elle ne doit pas devenir une métrique arbitraire de volume de contenus.

---

# 66. Placement

Placement répond à :

```text
où ?
```

et reste distinct de Capacity.

---

# 67. Commerce

Si une Production est réellement commercialisée :

```text
Offer
Order
Payment
```

peuvent intervenir.

Mais :

```text
Payment
≠ Production accomplie
```

et :

```text
vente
≠ vérité éditoriale
```

---

# 68. Publication

Le terme `publication` doit être utilisé avec prudence.

Un `Activity.status = published` éventuel n’est pas automatiquement la même chose qu’une Production médiatique « publiée » au sens éditorial.

Le client ne doit pas fusionner ces sémantiques sans owner contract.

---

# 69. Diffusion

De même :

```text
diffusé
```

peut être une vérité éditoriale ou opérationnelle.

Le présent contrat UX ne crée pas un lifecycle universel de diffusion.

---

# 70. Projection publique

Une Production peut avoir une projection publique.

Cette projection applique divulgation minimale.

Elle ne contient pas automatiquement :

- notes privées ;
- drafts ;
- sources privées ;
- responsabilités ;
- permissions ;
- analytics internes ;
- partenaires privés ;
- ressources non publiques.

---

# 71. Workspace ≠ site média public

La porte Productions est un workspace du Space.

Elle n’est pas :

```text
page d’accueil publique du média
```

Les deux peuvent présenter certaines mêmes réalités via des projections différentes.

---

# 72. No social network

Interdits :

- feed ;
- posts génériques ;
- Stories ;
- likes ;
- réactions de popularité ;
- followers comme objectif central ;
- watch time comme KPI produit ;
- scroll infini artificiel ;
- autoplay d’engagement ;
- tendances basées sur viralité ;
- ranking de productions par popularité.

---

# 73. Empty state

Space media sans Production :

```text
Productions

Aucune production pour le moment.
```

Si autorisé :

```text
[Créer une première production]
```

Sinon :

```text
Aucune production visible dans votre périmètre.
```

---

# 74. Calm state

Exemple :

```text
Productions

Tout avance normalement.

En production
Série Villes en mouvement

À venir
Débat public · vendredi
```

Pas besoin de faux KPI.

---

# 75. Loading

Préférer :

```text
snapshot existant
+
refresh discret
```

à :

```text
vide
→ skeleton
→ contenu
```

si une projection locale existe.

---

# 76. Offline

Le client peut conserver selon confidentialité :

- Productions synchronisées ;
- Occurrences ;
- ressources disponibles ;
- médias locaux autorisés ;
- brouillons ;
- contexte ;
- filtres et sélection.

Mais :

```text
offline
≠ Live
```

---

# 77. Media offline

Si un média n’est pas localement disponible :

```text
Indisponible hors connexion
```

Le reste de la Production reste lisible.

---

# 78. Stale

La fraîcheur est factuelle.

Une description durable peut rester valable longtemps.

Une information de Jour J ou Live est beaucoup plus sensible.

Le client ne doit pas appliquer un seul TTL UX à toute la surface.

---

# 79. Partial failure

Exemple :

```text
Productions
✓ Productions visibles
✓ Événements visibles

Prestations
Impossible d’actualiser.
[Réessayer]
```

La défaillance reste locale.

---

# 80. Permission loss

Si une Permission est retirée :

- revalider N2/N3 ;
- retirer actions ;
- retirer données privées ;
- préserver les projections encore légitimes ;
- ne jamais laisser le cache local devenir autorité.

---

# 81. Compact

Compact :

```text
single pane
bottom nav
sections verticales
rows/cards modérées
N2 par navigation
```

Un média ne doit pas occuper tout le viewport sans nécessité.

---

# 82. Medium

Medium peut permettre :

```text
field + preview
```

ou :

```text
list/grid + focus léger
```

selon la nature des Productions.

---

# 83. Wide

Wide peut utiliser :

```text
NAV | PRODUCTIONS | FOCUS
```

après sélection.

La racine reste structurée.

---

# 84. Very Wide

Interdits :

- mur de vidéos ;
- dashboard audience ;
- newsroom ERP générique ;
- analytics permanents ;
- feed multicolonnes ;
- sidebar de modules ;
- densité artificielle.

L’espace supplémentaire sert à conserver contexte + profondeur.

---

# 85. Adaptive conservation

Lors de resize / rotation :

conserver autant que possible :

- surface ;
- Production sélectionnée ;
- scroll ;
- query ;
- filtres ;
- responsabilité ;
- grid/list ;
- profondeur ;
- média sélectionné ;
- brouillon.

---

# 86. Back

Retour N2 → N1 conserve :

- section ;
- scroll ;
- filtre ;
- query ;
- sélection ;
- préférence de vue.

---

# 87. Resume

À la reprise :

1. afficher le snapshot sûr ;
2. refresh discret ;
3. revalider l’autorité ;
4. supprimer les données devenues interdites ;
5. préserver le contexte.

---

# 88. Deep links

Deep link :

```text
Makolo
→ Space
→ Productions
→ Production
```

doit restaurer explicitement Actor Context.

Un deep link ne transfère aucune Permission.

---

# 89. Native mobile

Capacités possibles :

- caméra ;
- micro ;
- photo picker ;
- file picker ;
- share sheet ;
- notifications ;
- localisation si contexte terrain.

Chaque Permission native est demandée au moment du besoin.

---

# 90. Capture locale

Capturer :

```text
audio
photo
video
document
```

ne signifie pas :

```text
publier
```

La chaîne peut être :

```text
capture locale
→ draft / ressource
→ association à Production
→ synchronisation
→ publication/diffusion seulement si action distincte et owner-backed
```

---

# 91. Drafts

Un brouillon significatif peut être conservé localement si le contrat le permet.

Il faut distinguer :

```text
draft local
draft synchronisé
Production active
projection publique
```

sans faux succès.

---

# 92. Feedback

Préférer :

> **Production créée. Il reste à préciser la prochaine réalisation.**

à :

> Success.

Pour un média :

> **Fichier ajouté au brouillon.**

si aucune publication n’a eu lieu.

---

# 93. Erreurs

Une erreur doit répondre :

1. qu’est-ce qui n’a pas fonctionné ?
2. qu’est-ce qui a été conservé ?
3. que faire maintenant ?

Une erreur de média ne doit pas faire tomber toute la Production.

---

# 94. Search globale vs Search Productions

Recherche globale :

```text
Rechercher dans cet Espace
```

Recherche métier :

```text
Rechercher une production, un événement ou une réalisation
```

La recherche globale ne remplace pas la recherche spécialisée.

---

# 95. API / projection actuelle

Le runtime actuel utilise la projection Space Métier commune.

Le client peut recevoir des éléments tels que :

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

Le client ne doit pas reconstituer la sécurité depuis les données visibles.

---

# 96. Runtime actuel

`main` vérifié :

```text
d5b85ee4c737f09da7d1b2e27f7bae9d14d40131
```

Le preset `media` établit :

```text
label = Média / journalisme
navigation_section_label = Production
activities_label = Productions & activités
primary_business_label = Productions
```

Cela soutient directement la porte visible définie ici.

---

# 97. Featured modules ≠ sections N1

Le runtime mentionne notamment :

```text
activities
crm
audiences
groups
promotions
growth
partners
trust
analytics
```

Ces capacités peuvent être pertinentes.

Mais :

```text
featured_modules
≠ layout
≠ onglets obligatoires
≠ sections visibles obligatoires
```

---

# 98. Runtime Space Work

La projection Space Work courante repose largement sur des sections transversales :

```text
preparation
upcoming
active
blocked
completed
```

Ces buckets peuvent alimenter Productions.

Mais ils ne constituent pas les labels UX définitifs.

---

# 99. Gap runtime / contrat

Le runtime actuel ne démontre pas nécessairement une projection Media spécialisée contenant explicitement :

```text
production_identity
editorial_stage
media_bindings
audience_context
distribution_state
```

Le contrat ne doit pas prétendre le contraire.

Ces notions restent des cibles UX seulement lorsqu’elles peuvent être soutenues par des owners existants.

---

# 100. Structure vs continuité

Pour `media` :

```text
STRUCTURE
→ productions durables
→ séries / programmes si relations réelles
→ Activities

CONTINUITÉ
→ préparation
→ réalisation
→ prochaines Occurrences
→ blockers
→ prestations / événements actuels
```

Structure et continuité peuvent partager le même owner.

Elles répondent à des questions différentes.

---

# 101. P1 / P2 / P3

N1 :

```text
PRODUCTION / CURRENT MOVEMENT   P2
IMPORTANT CONSEQUENCE           P2/P3
NEXT ACTION                     P2/P3
MEDIA PREVIEW                   P1/P2
TIME / PLACE                    P1
AUDIENCE / ANALYTICS            P0/P1
```

N2 :

```text
PRODUCTION IDENTITY             P2
CURRENT STATE / BLOCKER         P3 si critique
NEXT LEGITIMATE ACTION          P2/P3
SUPPORT                         P1
```

---

# 102. Recognition test

En environ 500 ms :

```text
où suis-je ?
→ ce Space

quel mode ?
→ Productions

qu’est-ce qui domine ?
→ travail média réel / prochaine continuité
```

Pas :

```text
feed
audience analytics
social stats
```

---

# 103. Blur test

En floutant le texte :

- champ de Productions identifiable ;
- média structuré ;
- chrome secondaire ;
- pas de mosaïque chaotique ;
- focus perceptif stable.

---

# 104. Deletion test

Pour chaque thumbnail, player ou image :

> si je retire ce média, perd-on une compréhension utile ?

Si non :

il ne doit probablement pas être au N1.

---

# 105. Competition test

Un visuel spectaculaire ne doit pas concurrencer un blocker ou une action actuelle.

Un seul P3 perceptif à la fois.

---

# 106. Golden candidates

## G-PROD-01 — Compact / Content

Fixture :

```text
Radio Horizon
Productions

En production
Journal du soir
Édition 18 octobre
Conducteur à valider

À préparer
Débat public
Vendredi · 19:00
Invité à confirmer

Productions
Villes en mouvement
Journal du soir
```

---

## G-PROD-02 — Compact / Empty

```text
Productions

Aucune production pour le moment.

[Créer une première production]
```

CTA seulement si autorisé.

---

## G-PROD-03 — Compact / Calm

```text
Productions

Tout avance normalement.

En production
Villes en mouvement

À venir
Débat public
```

---

## G-PROD-04 — Media contextual

Production avec thumbnail ou cover.

Le média aide à reconnaître.

Il ne devient pas feed.

---

## G-PROD-05 — Production without media

La surface reste complète et professionnelle sans image.

Aucun placeholder décoratif obligatoire.

---

## G-PROD-06 — Medium / selected

```text
PRODUCTIONS | PREVIEW
field       | Journal du soir
```

---

## G-PROD-07 — Wide / N2

```text
NAV | PRODUCTIONS | PRODUCTION
```

N2 peut montrer ressources, Occurrences et actions.

---

## G-PROD-08 — Event / Jour J

```text
Débat public
Aujourd’hui · 19:00

[Ouvrir Jour J]
```

si owner admissible.

---

## G-PROD-09 — Offline media

Production visible.

Média distant indisponible.

Aucune panne globale.

---

## G-PROD-10 — Authority limited

Le Viewer ne voit que les Productions de son scope Activity.

Aucune fuite du portfolio Space.

---

## G-PROD-11 — textScale 1.6

Les cards adaptent leur hauteur.

Les actions restent accessibles.

---

# 107. Viewports Golden

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
media_unavailable
```

---

# 108. Accessibility

MUST :

- text scaling ;
- ordre de focus logique ;
- tap targets suffisants ;
- Reduce Motion ;
- labels sémantiques ;
- media descriptions quand utiles ;
- sous-titres/transcriptions lorsqu’ils existent et sont pertinents ;
- aucun état seulement par couleur ;
- aucun autoplay sonore imposé.

---

# 109. Audio

Audio peut être un média central.

Mais le player doit rester secondaire à la tâche sauf si écouter est l’action principale.

Contrôles explicites.

Pas d’autoplay d’engagement.

---

# 110. Vidéo

La vidéo peut être :

- source ;
- preview ;
- résultat ;
- ressource ;
- média public.

Elle ne devient pas feed.

Le lecteur doit avoir fallback et état local d’erreur.

---

# 111. Images

Une image peut être :

- cover ;
- illustration ;
- photo terrain ;
- capture ;
- ressource ;
- résultat.

Elle n’est pas obligatoire pour toutes les Productions.

---

# 112. Documents

Les documents peuvent servir :

- préparation ;
- conducteur ;
- script ;
- brief ;
- contrat ;
- ressource.

Posséder le document ne signifie pas satisfaire automatiquement un Requirement.

---

# 113. Couleurs

Palette Makolo :

```text
#5232DB
#2B176E
#FF704D
#FAF7F5
#0F172A
```

Les médias peuvent apporter leurs couleurs.

Le shell conserve la cohérence Makolo.

---

# 114. Motion

Motion sert à :

- focus ;
- transition N1→N2 ;
- changement de filtre ;
- chargement média ;
- confirmation ;
- retour.

Pas de motion conçue pour retenir l’utilisateur.

---

# 115. Local-first

Le local peut conserver :

- Productions synchronisées ;
- Occurrences ;
- ressources ;
- médias autorisés localement ;
- drafts ;
- sélection ;
- filtres ;
- view preference.

Le serveur reste autoritaire pour :

- Permission ;
- Mandate ;
- Access ;
- Capacity partagée ;
- Payment ;
- publication partagée ;
- multi-acteur ;
- Jour J ;
- Live.

---

# 116. Privacy et média

Un fichier média peut contenir :

- identité ;
- visage ;
- voix ;
- lieu ;
- information privée ;
- source sensible.

Les projections doivent respecter :

- visibilité ;
- autorité ;
- divulgation minimale ;
- propriétaire ;
- contexte.

Le média public et le média interne ne doivent pas être confondus.

---

# 117. Source journalistique

Le preset runtime indique `Média / journalisme`.

Cependant, les fichiers sources fournis ne définissent pas ici un modèle canonique complet de `Source journalistique`.

Le présent contrat n’en invente donc pas un.

Si un domaine de source existe ou est ajouté ailleurs, il devra respecter ce contrat sans créer de fuite de confidentialité.

---

# 118. Corrections et versions

Les sources fournies ne définissent pas un système canonique complet de version éditoriale.

Le présent contrat ne crée pas :

```text
Revision
DraftVersion
PublicationVersion
```

par défaut.

Si le runtime possède un mécanisme adapté, Presentation pourra l’utiliser.

---

# 119. Distribution

Les sources fournies ne fixent pas ici un domaine universel de distribution média.

Donc :

```text
distribution
```

reste une notion UX contextuelle ou owner-backed.

Pas de nouveau système de diffusion générique inventé dans ce contrat.

---

# 120. Notifications

Une Production ne devient pas une source de notifications infinies.

Seuls les changements justifiant une notification selon les règles de Notification doivent en produire.

Les conséquences importantes peuvent remonter dans Now.

---

# 121. Anti-features

Productions ne doit jamais devenir :

- réseau social ;
- feed ;
- timeline de posts ;
- Story ;
- Reels-like UX ;
- page d’audience permanente ;
- dashboard de vues ;
- watch-time optimizer ;
- ranking de viralité ;
- mur de vidéos ;
- CMS universel ;
- newsroom ERP générique ;
- content farm ;
- bibliothèque média orpheline ;
- galerie sans contexte ;
- liste de tous les fichiers ;
- CRM ;
- Analytics ;
- Growth dashboard ;
- Promotions center ;
- second Event ;
- second Service ;
- second Journey ;
- second Readiness ;
- second Access ;
- source d’autorité ;
- système où chaque média devient une Production.

---

# 122. Invariants gelés

1. La porte visible est `Productions`.
2. `media` est un archétype de Presentation.
3. Production UX n’est pas un nouveau modèle métier.
4. Production ≠ fichier média.
5. Média ≠ Post.
6. Média ≠ Proof.
7. Activity reste une source canonique fréquente.
8. Occurrence reste distincte de Production durable.
9. La racine peut composer productions / Activities.
10. La racine peut composer événements.
11. La racine peut composer prestations éventuelles.
12. La racine peut composer Occurrences.
13. Audiences restent surtout relationnelles / possibilités.
14. Publics restent surtout relationnels / possibilités.
15. Partners restent surtout relationnels / possibilités.
16. Feed interdit.
17. Réseau social générique interdit.
18. Likes / vues / watch time ne deviennent pas objectifs UX.
19. Featured modules ≠ sections N1.
20. Analytics appartient surtout à Piloter.
21. Now porte l’attention présente.
22. Découvrir porte les possibilités.
23. Nous porte identité / organisation / relations.
24. Jour J appartient à une Occurrence admissible.
25. Live appartient à Jour J.
26. Diffusé ≠ automatiquement Live.
27. planned ≠ observed ≠ live.
28. Plusieurs Occurrences peuvent être actives simultanément.
29. Le Space entier ne devient pas Live.
30. Readiness reste dérivée.
31. Resource ≠ Requirement ≠ Proof.
32. Access reste droit.
33. Capacity ≠ Placement.
34. Actor Context = Space.
35. Viewer = Profile.
36. Responsibility ≠ authority.
37. Assignment ≠ Permission.
38. Membership ≠ Permission.
39. N1 reste lisible.
40. N2 explique une Production.
41. N3 délègue au propriétaire.
42. Offline ne fabrique pas le présent.
43. Media local ≠ media publié.
44. Le serveur revalide les mutations sensibles.
45. Responsive adapte la géométrie, pas la vérité.
46. No Orphan Content / Media s’applique.

---

# 123. Critères de sortie serveur

Le serveur est conforme lorsque :

- il identifie correctement `media` ;
- il fournit le label `Productions` ;
- il filtre authority-first ;
- il respecte scope Space / Activity ;
- il fournit les Activities visibles ;
- il fournit les Occurrences pertinentes ;
- il expose les verticales uniquement lorsqu’elles existent ;
- il fournit des capabilities ;
- il ne transforme pas audience/partners en authority ;
- il ne crée pas de Production fictive ;
- il permet profondeur owner-backed ;
- il protège médias et données privées ;
- il supporte fraîcheur et états partiels.

---

# 124. Critères de sortie Web

Le Web est conforme lorsque :

- Produções/Productions est immédiatement reconnaissable comme espace de travail ;
- aucune dérive feed ;
- média contextuel ;
- production sans média supportée ;
- Occurrences distinctes ;
- Events et Services seulement si réels ;
- audiences restent secondaires ;
- search est métier ;
- N2/N3 progressifs ;
- back conserve contexte ;
- permissions respectées ;
- responsive préserve priorité.

---

# 125. Critères de sortie Flutter

Flutter est conforme lorsque :

- Compact est complet ;
- média local-first est prudent ;
- offline reste lisible ;
- player errors restent locaux ;
- back gesture conserve sélection ;
- deep link restaure Space ;
- view preference peut être conservée ;
- textScale 1.6 fonctionne ;
- caméra/micro/fichiers sont demandés au besoin ;
- aucune capture n’est confondue avec publication ;
- actions sensibles attendent la confirmation serveur.

---

# 126. Tests ciblés

```text
media root content
media root empty
media root calm
production with media
production without media
occurrence distinction
event composition
service composition
no social feed
audience remains relational
partner remains relational
activity-limited viewer
responsibility lens
authority revoked
offline snapshot
media unavailable
deep link
jour j handoff
multiple occurrences
planned != live
textScale 1.6
compact / medium / wide
```

---

# 127. Fixture de référence

```text
Radio Horizon
Productions

En production
Journal du soir
Édition du 18 octobre
Conducteur à valider

À préparer
Débat public
Vendredi · 19:00
Invité à confirmer

À venir
Série Villes en mouvement
Nouvel épisode · lundi

Productions
Journal du soir
Villes en mouvement
Regards du terrain
```

Cette fixture est illustrative.

Elle n’impose pas ces types de productions à tout Space `media`.

---

# 128. Fixture avec média

```text
[visuel]

Villes en mouvement

Épisode en préparation
Réalisation vendredi

Prochaine étape
Confirmer le lieu
```

Le visuel soutient la reconnaissance.

Il ne crée pas un Post.

---

# 129. Fixture sans média

```text
Journal du soir

Édition du 18 octobre

Préparation
Conducteur à valider

Réalisation
18:30
```

La surface reste complète.

---

# 130. Fixture Event / Jour J

```text
Débat public

Aujourd’hui · 19:00
Centre culturel

Préparation
Tout est prêt

[Ouvrir Jour J]
```

Le CTA n’apparaît que si le serveur l’autorise.

---

# 131. Fixture prestation média

```text
Couverture événementielle

Client
Organisation X

Date
Samedi

État
Préparation en cours

[Ouvrir la prestation]
```

Cette représentation ne change pas l’archétype du Space.

---

# 132. Fixture audience relationnelle

```text
Production
Villes en mouvement

Public concerné
Jeunes urbains
```

Le public est du contexte.

Il ne devient pas un tableau Audience dans N1.

---

# 133. Points volontairement ouverts

Restent ouverts :

- vocabulaire exact des stades visibles de production ;
- existence ou non d’un owner spécialisé Media futur ;
- composant final list/grid ;
- gestion détaillée audio/vidéo ;
- publication/diffusion owner contract ;
- versions/révisions éditoriales ;
- source journalistique éventuelle ;
- workflow de validation éditoriale éventuel ;
- payload spécialisé `media` futur ;
- règles de public projection détaillées ;
- microcopy finale ;
- animations ;
- breakpoints exacts ;
- choix final de glyph ;
- analyse audience dans Piloter ;
- politique détaillée de Promotions/Growth.

Ces points ne doivent pas être remplis par invention.

---

# 134. Références de cadrage

Ce contrat dérive principalement de :

- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Mobile_Visual_Charter_v1.1.md`
- `Makolo_UI_Engineering_Standards_v1.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_UX_Now_Contrat_Consolide.md`
- `Makolo_UX_Decouvrir_Contrat_Consolide.md`
- `Makolo_UX_En_Cours_Contrat_Consolide.md`
- les contrats mobile/local-first/sync fournis dans le projet
- le runtime `main` courant lors de la consolidation

Le code, les migrations, les tests et les domaines canoniques restent prioritaires lors de l’implémentation.

---

# 135. Formulation finale

> **Productions est la porte Métier d’un Space `media`. Elle rend visible et opérable ce que le Space produit réellement à travers ses Activities, Occurrences, événements et prestations éventuelles, tout en gardant audiences, publics et partenaires principalement dans leur rôle relationnel. Une Production UX n’est ni un nouveau modèle métier ni un fichier média : images, audio, vidéo et documents restent des ressources ou représentations contextualisées. La surface peut être visuellement riche, mais ne devient jamais un feed, un réseau social ou un système de popularité. N1 rend lisible le champ de production et sa continuité, N2 explique une Production réelle, N3 délègue aux propriétaires, Jour J accompagne une Occurrence actuelle, Live ne représente que des faits réellement observés ou suffisamment établis, et le serveur demeure l’autorité pour les permissions et actions partagées.**
