# Makolo — **Moi**
## Contrat UX consolidé — identité et capital personnel

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence — surface personnelle `Moi`  
**Actor Context :** Profile  
**Viewer :** Profile authentifié lui-même  
**Portée :** Web, Flutter, tablette/desktop adaptatif, Presentation, local-first, projections privées  
**Base runtime vérifiée :** `main@788a744102e124feddbe0e17b30b8ede40fb2ebe`  
**Nature :** contrat UX et de projection ; ne crée aucun nouveau domaine métier  
**Promesse produit :** **Makolo marche pour vous.**  
**Principe d’expérience :** **Pas le plaisir de rester. Le plaisir d’avancer.**

---

# 0. Formule

```text
Moi
=
identité personnelle
+
capital déjà disponible
+
relations personnelles déjà établies
+
représentations contrôlées
```

et non :

```text
Moi
=
compte
+
profil social
+
paramètres
+
dashboard personnel
```

---

# 1. Question humaine

La surface **Moi** répond à :

> **Qu’est-ce qui est déjà en place autour de moi pour faciliter la suite ?**

Elle doit permettre de comprendre :

```text
qui je suis dans Makolo
+
ce qui compte explicitement pour moi
+
ce que je possède déjà ou peux réutiliser
+
les collectifs auxquels je suis réellement relié
+
les preuves, titres et ressources déjà disponibles
+
ce que je peux choisir de représenter ou partager
```

Elle ne répond pas à :

> Qu’est-ce que je dois faire maintenant ?

Cette question appartient à **Maintenant**.

Elle ne répond pas à :

> Où en sont mes démarches ?

Cette question appartient à **En cours**.

Elle ne répond pas à :

> Que puis-je découvrir ?

Cette question appartient à **Découvrir**.

---

# 2. Modèle mental

Le modèle mental de référence est :

```text
Moi = identité + capital personnel
```

La personnalité Presentation est :

```text
structure + capital
```

La grammaire Golden est :

```text
Moi = SECTION-FIRST
```

La racine ne doit donc pas être une carte géante de profil, une liste d’actions urgentes ou une grille de métriques.

---

# 3. Profile canonique

Invariant :

```text
Profile
= personne globale
```

Le Profile n’est jamais globalement :

```text
participant
organisateur
client
bénéficiaire
membre
collaborateur
```

Ces mots décrivent des relations ou des contextes.

Une seule personne conserve une seule identité Profile même lorsqu’elle agit dans plusieurs Espaces ou réalités.

---

# 4. Moi ≠ compte

Le compte d’authentification et ses réglages peuvent être accessibles depuis l’Avatar ou une profondeur adaptée.

Mais **Moi** n’est pas une page de compte.

La racine ne doit pas être dominée par :

```text
email
mot de passe
sécurité de session
déconnexion
appareils
préférences techniques
```

Ces éléments restent légitimes ailleurs.

---

# 5. Moi ≠ profil social

Interdits comme centre de la surface :

- followers ;
- likes ;
- compteurs de popularité ;
- mur de publications ;
- Story ;
- feed ;
- score de réputation global ;
- score social ;
- watch time ;
- classement.

Le Profile public est une projection contrôlée de certains faits.

Il ne transforme pas Moi en profil social.

---

# 6. Profil privé et projection publique

Makolo conserve un seul Profile.

```text
Profile privé
≠ modèle distinct
```

et :

```text
Profil public
= projection contrôlée
```

La projection publique peut utiliser uniquement les faits explicitement rendus publics selon leurs propriétaires et contrats.

Moi reste privé par défaut.

---

# 7. `public_profile` ≠ `searchable`

Deux décisions différentes doivent rester distinctes :

```text
public_profile
→ une projection publique existe

searchable
→ le Profile accepte d’être candidat dans certaines recherches autorisées
```

L’une ne doit pas activer implicitement l’autre.

---

# 8. N1 — structure générale

La racine candidate est :

```text
MOI
│
├── IDENTITY
│
├── PASSEPORT MAKOLO
│
├── CE QUI COMPTE POUR MOI
│   ├── Interests
│   ├── Open to
│   ├── Veilles
│   ├── éléments gardés
│   └── suivis
│
├── MES COLLECTIFS
│   ├── Espaces autorisés
│   ├── Teams
│   └── Groupes
│
├── MES RESSOURCES
│   ├── Personal Assets
│   ├── Proofs
│   └── Credentials Trust
│
├── MES APPUIS ? 
│   └── uniquement lorsqu’ils existent et sont utiles
│
└── DEPTH
    ├── owner
    ├── Passeport
    ├── ressource
    ├── collectif
    ├── partenaire
    ├── Access durable
    └── Historique
```

Cette grammaire suit le runtime courant sans transformer les noms d’API en titres obligatoires.

---

# 9. Header

Le shell personnel reste Makolo.

La surface doit conserver :

```text
Makolo                                      Avatar
```

Le header n’a pas besoin de répéter lourdement `Moi` si la navigation et la hiérarchie rendent le mode évident.

L’identité humaine peut apparaître dans le contenu de la surface.

---

# 10. Identité N1

L’identité constitue le premier repère P2.

Elle peut présenter selon disponibilité et préférence :

- nom d’affichage ;
- `@identifiant` ;
- avatar ;
- profession déclarée ;
- localisation générale choisie ;
- bio courte.

Elle ne doit pas exposer automatiquement :

- email ;
- téléphone ;
- adresse précise ;
- date de naissance complète ;
- secrets ;
- informations privées non nécessaires.

---

# 11. Hiérarchie Golden

Référence :

```text
IDENTITY            P2
SECTION TITLE       P2
SECTION CONTENT     P1/P2
ACTION              P1
MEDIA               P0/P1
MOTION              0
```

Conséquence :

> Moi est une surface structurée, pas une surface d’urgence.

Une action exceptionnelle peut monter temporairement en priorité si un owner l’exige, mais cela ne doit pas transformer Moi en Now.

---

# 12. Pas de score de complétion dominant

Le runtime peut disposer d’une information dérivée de complétude Profile.

Mais le contrat visible impose :

```text
score de complétion
≠ dominant permanent
```

Moi doit rester utile même avec un Profile incomplet.

La personne ne doit pas être obligée de « finir son profil » pour accéder à son capital déjà réel.

---

# 13. Identité incomplète

L’incomplétude doit être locale.

Exemple :

```text
Identité
Ville non renseignée
[Ajouter]
```

plutôt que :

```text
Votre profil est à 63 %
```

comme message principal permanent.

---

# 14. Passeport Makolo

Le **Passeport Makolo** est une projection/export contrôlé.

Invariant :

```text
Passeport Makolo
≠ nouvelle source de vérité
```

Il compose des faits propriétaires déjà établis.

---

# 15. Passeport N1

À la racine, Passeport peut être une section simple :

```text
Passeport Makolo
Ce qui peut vous représenter selon le contexte.
[Ouvrir]
```

La racine n’a pas besoin d’exposer tous les éléments du Passeport.

---

# 16. Passeport N2

N2 peut permettre de comprendre et sélectionner :

- identité autorisée ;
- Interests publics ;
- Open to publics ;
- Activities personnelles publiques ;
- Proofs sélectionnables ;
- Credentials sélectionnables ;
- thèmes ;
- variante de projection.

Le serveur et les owners restent responsables des règles de divulgation.

---

# 17. Passeport ≠ CV builder

Le Passeport ne devient pas :

- CV universel ;
- profil RH générique ;
- scoring de personne ;
- vérification globale de qualité ;
- agrégateur de tout l’historique.

Il représente ce qui est légitime dans un contexte.

---

# 18. Ce qui compte pour moi

Le runtime courant compose notamment :

```text
Interests
Open to
Veilles
Bookmarks
Spaces suivis
Profiles suivis
```

La formulation visible peut être :

```text
Ce qui compte pour moi
```

car elle regroupe des choix explicites de la personne.

---

# 19. Interest

```text
Interest
= ce qui m’intéresse explicitement
```

Il ne doit pas être inféré silencieusement du comportement.

Une activité consultée ne devient pas automatiquement un Interest.

---

# 20. Open to

```text
Open to
= pour quoi j’accepte volontairement d’être sollicité
```

Il est distinct de Interest.

Exemple :

```text
Intérêt
→ photographie

Ouvert à
→ mentorat
```

Ces faits ne doivent pas être fusionnés.

---

# 21. Veille

Une Veille répond à :

> Que doit continuer à rechercher Makolo pour moi ?

Elle peut être visible dans Moi parce qu’elle constitue un capital de recherche durable.

Mais elle reste propriétaire du domaine Discovery/Watch.

---

# 22. Bookmark / élément gardé

Un Bookmark signifie :

```text
je veux garder cet objet
```

Il ne signifie pas :

```text
je l’ai engagé
je vais le faire
je l’ai acheté
j’ai commencé une Journey
```

La profondeur doit pouvoir handoff vers le propriétaire réel.

---

# 23. Follow

Suivre un Space ou un Profile est une relation explicite.

Cela ne signifie pas :

- membership ;
- authority ;
- partenariat ;
- intérêt thématique automatique ;
- visibilité réciproque.

---

# 24. Mes collectifs

Le runtime actuel peut composer :

```text
Espaces autorisés
Teams
Groupes
```

Le territoire visible est :

```text
Mes collectifs
```

---

# 25. Espace autorisé

Un Space autorisé signifie que la personne possède une voie légitime d’Actor Context vers ce Space.

Cela ne signifie pas que toute vérité du Space appartient à Moi.

Moi peut dire :

```text
Mulykap
Vous pouvez agir dans cet Espace.
```

La profondeur d’action appartient au contexte Space.

---

# 26. Changer d’acteur

Depuis un Space visible dans Moi :

```text
Ouvrir
→ peut proposer Agir comme ce Space
```

si le shell le permet.

Mais :

```text
sélectionner Space
≠ obtenir Permission
```

L’autorité a été établie en amont par le serveur.

---

# 27. Team

Une TeamMembership signifie collaboration.

Invariant :

```text
TeamMembership
≠ Mandate
```

Moi peut montrer l’appartenance sans prétendre à l’autorité.

---

# 28. Groupe

GroupMembership représente appartenance, ciblage ou éligibilité.

Invariant :

```text
GroupMembership
≠ Mandate
```

Un Groupe n’est pas un Space.

---

# 29. Mes ressources

Le territoire runtime actuel compose :

```text
Personal Assets
Proofs
Credentials Trust
```

La formulation visible peut rester :

```text
Mes ressources
```

avec une profondeur qui préserve les distinctions.

---

# 30. Resource ≠ file

Invariant Golden :

```text
Resource
≠ file
```

Un fichier peut être une représentation ou version d’une ressource.

La surface ne doit pas réduire tout capital personnel à un explorateur de fichiers.

---

# 31. Resource ≠ Proof

```text
Resource
≠ Proof
```

Posséder un document ne signifie pas qu’un fait est établi.

---

# 32. Proof

```text
Proof
= fait atomique établi selon le domaine Trust
```

Moi peut le présenter.

Moi ne le fabrique pas.

---

# 33. Credential Trust

```text
Credential Trust
= attestation délivrée par un émetteur
```

Il reste distinct de :

```text
AccessCredential
```

qui représente un droit d’accès.

---

# 34. Personal Asset

Un Personal Asset peut être réutilisable dans plusieurs contextes.

Sa valeur dans Moi vient de la réduction future de friction :

```text
déjà disponible
→ peut servir plus tard
```

---

# 35. Posséder ≠ retrouver ≠ satisfaire

Invariant :

```text
posséder un document
≠ le retrouver
≠ satisfaire un Requirement
```

Moi peut montrer la disponibilité.

Readiness/Requirement décide de la suffisance dans un contexte donné.

---

# 36. Access durable

Un Access actif et durable peut être pertinent dans Moi lorsqu’aucune poursuite active ne justifie En cours.

Exemple :

```text
Carte d’accès annuelle
```

Mais Access reste son domaine.

Moi n’invente pas un portefeuille générique de droits.

---

# 37. Mes appuis

Le runtime actuel expose conditionnellement des appuis comme :

- Recognition ;
- Loyalty ;
- Partners personnels.

Ce territoire ne doit apparaître que si des faits réels existent.

---

# 38. Appui ≠ score personnel

Recognition ou Loyalty ne doivent pas produire :

```text
score global de valeur
```

Moi ne classe pas la personne.

---

# 39. Partners personnels

Une relation Partner peut être visible dans Moi si elle est réellement personnelle et autorisée.

Elle ne doit pas être confondue avec un partenaire d’un Space.

---

# 40. N1 — règle de densité

Moi est une surface de densité faible à moyenne.

La racine doit éviter :

- plus de détails que nécessaire ;
- longues tables ;
- identifiants techniques ;
- métadonnées de sécurité ;
- répétition de compteurs.

---

# 41. Sparse state

Les absences sont locales aux territoires.

Exemple :

```text
Mes ressources
Aucun titre ou document réutilisable pour le moment.
```

Cela ne transforme pas toute la page en Empty.

---

# 42. Empty root

Un vrai Empty root de Moi est rare parce que l’identité existe normalement.

Si les autres territoires sont vides :

```text
Moi
[Identité]

Ce qui compte pour moi
Rien pour le moment.

Mes collectifs
Aucun collectif.

Mes ressources
Aucune ressource.
```

La surface reste complète.

---

# 43. Calm state

Moi est naturellement calme.

Il ne doit pas créer une alerte parce qu’un territoire est vide.

---

# 44. Loading

Avec snapshot local :

```text
contenu connu
+
refresh discret
```

Sans snapshot :

```text
structure de sections
+
loading minimal
```

---

# 45. Offline

Moi est particulièrement compatible avec local-first.

Le client peut conserver selon sécurité :

- identité ;
- considérations ;
- collectifs connus ;
- ressources autorisées ;
- projections nécessaires.

Mais une copie locale ne devient pas autorité.

---

# 46. Offline et ressources sensibles

Une ressource sensible peut ne pas être conservable localement.

La surface doit pouvoir dire :

```text
Disponible lorsque vous êtes connecté.
```

sans prétendre que la ressource a disparu.

---

# 47. Freshness

La fraîcheur doit être territoriale.

Exemple :

```text
Identité
→ stable

Credential
→ peut nécessiter revalidation

Access
→ potentiellement plus sensible
```

Pas de bannière globale stale si seule une section est concernée.

---

# 48. Partial failure

Exemple :

```text
Moi
✓ Identité
✓ Passeport
✓ Mes collectifs

Mes ressources
Impossible d’actualiser.
[Réessayer]
```

Le reste reste utilisable.

---

# 49. Privacy

Moi est privé par défaut.

Les données sensibles ne doivent jamais être exposées parce qu’elles sont visibles dans Moi.

Toute projection publique ou partage applique divulgation minimale.

---

# 50. Search

Moi ne nécessite pas nécessairement une recherche N1 permanente.

Une recherche locale peut apparaître en profondeur pour :

- ressources ;
- Credentials ;
- collectifs ;
- historique.

Elle ne devient pas Search global Makolo.

---

# 51. Actions

Les actions sont secondaires P1 par défaut.

Exemples légitimes :

```text
Modifier mon identité
Gérer mes intérêts
Ouvrir mon Passeport
Ajouter une ressource
Voir mes collectifs
```

Pas de CTA agressif unique à remplir.

---

# 52. Création

La création appartient au territoire.

Exemple :

```text
Mes ressources
→ Ajouter une ressource
```

et non :

```text
+ Créer
→ tout Makolo
```

---

# 53. Frontière avec Maintenant

Capital disponible :

```text
Passeport valide jusqu’en 2031
→ Moi
```

Conséquence actuelle :

```text
Passeport expire bientôt et bloque le voyage
→ Maintenant
```

Même vérité propriétaire.

Projections différentes.

---

# 54. Frontière avec En cours

Exemple :

```text
Moi
→ Passeport valide jusqu’en 2031

En cours / Voyage Nairobi
→ Passeport déjà prêt ✓
```

En cours consomme le capital.

Moi le conserve comme ressource durable.

---

# 55. Frontière avec Découvrir

Moi peut nourrir la pertinence de Découvrir à partir de faits légitimes :

- Interests ;
- Open to ;
- géographie ;
- collectifs ;
- ressources pertinentes.

Mais Découvrir ne doit pas exposer la totalité de Moi.

---

# 56. Frontière avec Jour J

Moi peut fournir :

- Access durable ;
- Credential ;
- Resource ;
- Proof.

Jour J utilise uniquement ce qui est pertinent pour l’Occurrence courante.

---

# 57. Frontière avec Historique

Historique répond :

> Qu’est-ce qui est terminé et reste utile à retrouver ?

Moi conserve surtout ce qui est durablement disponible ou pertinent.

Le passé ne doit pas remplir Moi.

---

# 58. N2 — territoire

Sur Compact :

```text
Moi
→ Mes ressources
→ liste
→ ressource
```

Sur Medium/Wide, un territoire peut rester visible avec une profondeur adjacente.

---

# 59. N2 — Resource

La profondeur d’une ressource peut montrer :

- identité ;
- type ;
- sensibilité ;
- version ;
- dates d’émission/expiration si owner-backed ;
- actions légitimes ;
- contextes de partage ;
- liens owner.

Elle ne doit pas prétendre qu’un Requirement est satisfait.

---

# 60. N2 — Collectif

Une profondeur collectif doit distinguer :

```text
relation
+
capacité d’agir éventuelle
```

sans transférer automatiquement authority.

---

# 61. N2 — Interest / Open to / Watch

Ces profondeurs restent simples.

Pas de grand workflow administratif.

---

# 62. N3

N3 est owner-backed.

Exemples :

```text
Resource owner
Trust Credential
Group
Space
Discovery Watch
Access
Passport sharing
```

Moi ne recrée aucun owner.

---

# 63. Compact

Référence Golden :

```text
sections verticales
single pane
identity first
```

Mesures candidates :

```text
edge                       16 dp
header                     56 dp
header → identity          24 dp
identity line gap           4–8 dp
identity → first section   32 dp
section title → content    12 dp
row gap                    12–16 dp
section gap                32 dp
```

---

# 64. Medium

Candidate :

```text
1–2 territoires
```

Si deux territoires sont visibles en parallèle, ils doivent avoir une largeur permettant la lecture.

---

# 65. Wide

La largeur structure les territoires.

Elle ne crée pas une grille de dashboard.

Référence candidate :

```text
rail            80 dp
outer edges     32 dp
content max   1040–1120 dp
territory gap   24–32 dp
```

---

# 66. Split

Le split est utile lorsqu’un élément est sélectionné.

Il ne doit pas exposer une profondeur N2/N3 simplement parce que l’écran est large.

---

# 67. Adaptive conservation

Conserver autant que possible :

- territoire sélectionné ;
- item sélectionné ;
- scroll ;
- profondeur ;
- query locale ;
- brouillon ;
- état de section.

---

# 68. Back

Retour N2 → Moi conserve :

- scroll ;
- territoire ;
- sélection ;
- état précédent.

---

# 69. Resume

Après interruption :

1. rendre snapshot local ;
2. revalider les sections nécessaires ;
3. conserver la position ;
4. retirer ce qui n’est plus autorisé ;
5. ne pas afficher de faux succès.

---

# 70. Deep links

Deep link vers une ressource ou un collectif :

```text
Makolo
→ Moi
→ territoire
→ owner depth
```

doit vérifier la visibilité.

---

# 71. Accessibility

MUST :

- text scale ;
- focus logique ;
- targets tactiles suffisantes ;
- sections sémantiques ;
- états non basés seulement sur couleur ;
- Reduce Motion ;
- descriptions utiles pour médias d’identité ;
- aucune information sensible annoncée inutilement par assistive tech.

---

# 72. Media

Avatar et médias de ressources peuvent apparaître.

Mais :

```text
MEDIA P0/P1
```

dans la hiérarchie Golden.

Moi ne devient pas galerie.

---

# 73. Motion

Référence :

```text
MOTION = 0
```

comme personnalité de base.

Les transitions peuvent exister mais doivent rester fonctionnelles et discrètes.

---

# 74. Anti-features

Moi ne doit pas devenir :

- page de compte ;
- Settings ;
- profil social ;
- CV builder ;
- portfolio universel ;
- wallet universel ;
- explorateur de fichiers ;
- dashboard personnel ;
- score de complétion ;
- score de valeur ;
- feed ;
- historique ;
- En cours ;
- Now ;
- Dossier ;
- Journey ;
- bibliothèque de tout ;
- source de Trust ;
- source de Permission ;
- moteur de recommandation ;
- page de KPI.

---

# 75. Invariants gelés

1. Moi = identité + capital personnel.
2. Actor Context = Profile.
3. Viewer = Profile.
4. Profile est une personne globale.
5. Moi ≠ compte.
6. Moi ≠ profil public.
7. Profil public = projection.
8. `public_profile` ≠ `searchable`.
9. Moi est SECTION-FIRST.
10. Identity = P2.
11. Pas de score de complétion dominant.
12. Les absences sont locales aux territoires.
13. Passeport Makolo = projection/export.
14. Passeport ≠ source de vérité.
15. Interest ≠ Open to.
16. Follow ≠ Interest.
17. Bookmark ≠ engagement.
18. Veille ≠ Dossier.
19. TeamMembership ≠ Mandate.
20. GroupMembership ≠ Mandate.
21. Authorized Space ≠ propriété de Moi.
22. Resource ≠ file.
23. Resource ≠ Proof.
24. Credential Trust ≠ AccessCredential.
25. Posséder ≠ retrouver ≠ satisfaire Requirement.
26. Access durable peut être projeté sans devenir En cours.
27. En cours peut consommer le capital de Moi.
28. Presentation représente, ne possède pas.
29. Privacy et divulgation minimale sont obligatoires.
30. Offline conserve la compréhension, pas l’autorité.
31. Les erreurs sont locales quand possible.
32. Responsive adapte la géométrie, pas la vérité.

---

# 76. Runtime actuel — ce qui existe

Le runtime `personal.me` actuel compose déjà :

```text
identity
passport
considerations
collectives
resources
support
```

avec notamment :

```text
considerations:
  interests
  open_to
  watches
  bookmarks
  followed_spaces
  followed_profiles

collectives:
  authorized_spaces
  teams
  groups

resources:
  documents
  proofs
  credentials

support:
  recognition
  loyalty
  partners
```

Le contrat doit réutiliser cette ossature avant de créer toute nouvelle abstraction.

---

# 77. Runtime actuel — écarts / prudences

Le runtime expose une complétude d’identité dérivée.

Le Golden impose qu’elle ne devienne pas un dominant permanent.

Le runtime expose `support` comme agrégat de plusieurs domaines.

Le contrat UX autorise ce territoire seulement lorsqu’il aide réellement la personne ; il ne doit pas devenir un fourre-tout.

---

# 78. API et Presentation

Le client doit consommer une projection owner-backed.

Il ne doit pas :

- fusionner Proof et Credential ;
- déduire authority depuis Team ;
- réinterpréter la sensibilité d’une ressource ;
- inventer le caractère public ;
- considérer un Follow comme relation réciproque.

---

# 79. Golden candidates

## G-MOI-01 — Compact / Full

```text
Moi

Jean Kalala
@jeank
Ingénieur · Lubumbashi

Passeport Makolo
[Ouvrir]

Ce qui compte pour moi
Technologie
Ouvert au mentorat
Veille · Bourses internationales

Mes collectifs
Mulykap
Équipe Innovation

Mes ressources
Passeport
Certificat X
```

---

## G-MOI-02 — Compact / Sparse

Identité présente.

Trois territoires localement vides.

Aucun score de manque.

---

## G-MOI-03 — Compact / Offline

Snapshot lisible.

Fraîcheur locale.

Une ressource distante peut être indisponible sans bloquer la page.

---

## G-MOI-04 — Resource N2

Test :

```text
Resource
≠ file
≠ Proof
≠ Credential
```

---

## G-MOI-05 — Wide

Deux territoires possibles.

Pas de dashboard.

Pas de KPI.

---

## G-MOI-06 — Public projection boundary

Moi privé contient davantage que la projection publique.

Aucune donnée privée n’est révélée.

---

## G-MOI-07 — Collective boundary

Space visible.

Team visible.

Aucune authority inventée.

---

## G-MOI-08 — textScale 1.6

Sections lisibles.

Identité non tronquée de façon destructive.

---

# 80. Tests ciblés

```text
personal.me full
personal.me sparse
personal.me offline
identity missing optional facts
identity privacy
passport available
interests/open_to distinction
watch private
bookmark != engaged
authorized space
team membership != authority
group membership != authority
resource != proof
credential != access credential
local section error
permission / visibility loss
compact
800 / 840 / 900 adaptive
textScale 1.6
```

---

# 81. Critères de sortie Web

Conforme si :

- Moi est reconnaissable comme capital personnel ;
- identité reste humaine ;
- sections structurées ;
- pas de profil social ;
- pas de dashboard ;
- pas de score dominant ;
- owner boundaries visibles ;
- privacy respectée ;
- profondeurs progressives ;
- erreurs locales ;
- retour conserve contexte.

---

# 82. Critères de sortie Flutter

Conforme si :

- SECTION-FIRST ;
- Compact complet ;
- 1–2 territoires sur Medium selon largeur ;
- Wide sans dashboard ;
- store local utile ;
- offline honnête ;
- back conserve scroll/sélection ;
- deep links owner-safe ;
- textScale fonctionne ;
- refresh ne détruit pas la surface.

---

# 83. Points volontairement ouverts

Restent ouverts :

- microcopy finale de certains territoires ;
- visibilité exacte de `Mes appuis` ;
- profondeur finale de Passeport ;
- place exacte d’Access durable ;
- détails de partage ;
- composant visuel final des ressources ;
- seuils finaux Medium/Wide après tests réels ;
- éventuels regroupements si le capital devient très riche ;
- détails de compte/Settings hors Moi.

Aucun de ces points ne justifie un nouveau modèle métier.

---

# 84. Références de cadrage

Ce contrat dérive principalement de :

- `docs/architecture/makolo-domain-blueprint.md`
- `docs/architecture/profile-relevance-action-network.md`
- `docs/architecture/mature-experience-principles.md`
- `Makolo_UX_En_Cours_Contrat_Consolide.md`
- `Makolo_UX_Decouvrir_Contrat_Consolide.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- les contrats mobile/local-first/sync
- `core/api/me_projection.py`
- `mobile/lib/features/me/me_selector.dart`
- `mobile/lib/features/me/me_screen.dart`

Le runtime courant gagne lors de l’implémentation.

---

# 85. Formulation finale

> **Moi est la surface personnelle Makolo qui rend compréhensible l’identité du Profile et le capital déjà disponible autour de lui pour faciliter la suite. Elle compose, sans les fusionner, identité, Passeport Makolo, Interests, Open to, Veilles, éléments gardés, collectifs, ressources, Proofs, Credentials et appuis réels. Elle n’est ni un compte, ni un profil social, ni un dashboard, ni un wallet universel. Ses absences sont locales, sa hiérarchie est section-first, son contenu est privé par défaut et ses profondeurs restent owner-backed. Moi permet à Makolo de réutiliser ce qui est déjà là sans obliger la personne à reconstruire sa situation à chaque nouvelle action.**
