# Makolo — Contrat conceptuel gelé de `Moi` et `Nous`
## Deux surfaces distinctes : capital personnel et identité collective

**Statut :** contrat conceptuel gelé de travail  
**Portée :** expérience Web et mobile ; préparation des futurs contrats serveur, Web/Tailwind et Flutter  
**Date de gel :** 2026-10-06  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 0. Règle de lecture

Ce document traite deux surfaces proches par leur position dans le shell Makolo, mais **différentes par leur nature** :

```text
Moi
→ surface personnelle du Profile

Nous
→ surface collective du Space
```

Elles ne doivent pas être fusionnées dans une abstraction métier commune.

La proximité UX signifie seulement :

```text
contexte personnel
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi

contexte Space
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
```

La cinquième porte reste donc une porte d’identité, de structure durable et de profondeur contextuelle.

Mais :

```text
Moi
≠ Nous<Profile>

Nous
≠ Moi<Space>

MeResponse
≠ UsResponse<Actor>
```

Le backend peut réutiliser des primitives techniques de projection, mais les contrats sémantiques restent séparés.

Ce document ne fixe pas :

- un wire JSON définitif ;
- un `schema_version` définitif ;
- une nouvelle table métier ;
- un modèle générique `ActorCapital`, `ActorFoundation`, `Territory` ou `InstitutionalState` ;
- un nouveau lifecycle transverse ;
- une navigation pixel-perfect ;
- un composant UI unique ;
- un score de complétion ;
- une politique universelle de cache ;
- une hiérarchie générique de permissions côté client.

Les domaines propriétaires, leurs modèles, leurs permissions et leurs mutations restent propriétaires de leurs vérités.

---

# PARTIE I — `MOI`

# 1. Question humaine

> **Qu’est-ce qui est déjà en place autour de moi pour que Makolo marche mieux pour moi ?**

`Moi` ne répond pas :

- à ce qui mérite mon attention maintenant — `Now` ;
- à ce que j’ai déjà engagé et qui continue — `En cours` ;
- à ce que je pourrais vouloir vivre, faire ou obtenir — `Découvrir` ;
- à ce qui se déroule actuellement — `Jour J / Live` ;
- à tout mon historique.

`Moi` décrit le **capital personnel déjà disponible**, les relations durables connues et les profondeurs personnelles utiles.

---

# 2. Définition

> **Moi est la projection privée et structurée de ce qui est durablement en place autour du Profile et peut faciliter sa compréhension, sa représentation, ses relations et ses actions futures dans Makolo.**

Une unité visible dans `Moi` peut provenir de plusieurs domaines propriétaires, mais `Moi` n’en devient jamais propriétaire.

```text
Moi
≠ Account Settings
≠ profil social
≠ CV universel
≠ dashboard
≠ wallet
≠ historique
≠ En cours
≠ score personnel
≠ table de vérités copiées
```

---

# 3. Acteur et viewer

## 3.1 `ACTOR_CONTEXT`

Cardinalité :

```text
exactement 1
```

Valeur :

```text
Profile authentifié
```

Sur `/me`, le sujet ne vient jamais d’un `profile_id` fourni par le client.

## 3.2 `VIEWER`

Cardinalité :

```text
exactement 1
```

Valeur normale :

```text
le même Profile authentifié
```

Le fait que certaines profondeurs aient leurs propres règles de visibilité ne change pas le sujet de `Moi`.

---

# 4. Identité personnelle

## 4.1 `IDENTITY`

Cardinalité :

```text
exactement 1
```

Elle doit permettre de reconnaître la personne sans transformer `Moi` en dump Account.

Projection minimale typique :

```text
IDENTITY
├── kind = profile
├── id
├── display_name
├── avatar?
├── bio?
├── profession?
├── localisation générale choisie?
└── owner handoff?
```

Ne doivent pas être exposés automatiquement :

```text
email privé
téléphone privé
adresse précise
coordonnées privées
préférences techniques
tokens
Permissions brutes
Mandates bruts
device state
secrets
```

Principe :

> `IDENTITY` répond à « qui suis-je ici ? », pas à « quelles sont toutes les données de mon compte ? ».

---

# 5. Grammaire générale de `Moi`

`Moi` est une surface **SECTION-FIRST / TERRITORY-FIRST**.

```text
MOI
│
├── IDENTITY
│
├── PASSPORT
├── CONSIDERATIONS
├── COLLECTIVES
├── RESOURCES
├── APPUIS?            ← territoire de Presentation conditionnel
│
└── OWNER_HANDOFFS
```

Le mot `territory` désigne uniquement une organisation UX.

Il ne crée aucun domaine persistant.

---

# 6. `PASSPORT`

## 6.1 Nature

```text
Profile
≠ Passport
```

Le Passeport Makolo est une représentation/export contextuel de faits déjà légitimes.

Il peut composer trois natures distinctes :

```text
DECLARED
→ ce que la personne déclare

ESTABLISHED
→ faits / Proofs établis

ISSUED
→ Credentials Trust délivrés
```

Il ne devient jamais :

```text
une nouvelle vérité
un score humain
un Credential universel
un AccessCredential
```

## 6.2 Cardinalité racine

```text
PASSPORT
→ 0..1 preview structure
```

La racine peut transporter :

```text
available
preview?
owner_handoff
```

Le détail complet appartient à la profondeur Passport.

---

# 7. `CONSIDERATIONS`

Question humaine :

> **Qu’est-ce qui compte pour moi, à quoi suis-je ouvert, qu’est-ce que je veux retrouver ou continuer à observer ?**

La structure doit conserver les concepts distincts :

```text
CONSIDERATIONS
├── INTERESTS[]
├── OPEN_TO[]
├── WATCHES[]
├── BOOKMARKS[]
├── FOLLOWED_SPACES[]
└── FOLLOWED_PROFILES[]
```

Cardinalités :

```text
chaque collection → 0..n
```

Invariants :

```text
Interest
≠ OpenTo
≠ Watch
≠ Bookmark
≠ Follow

comportement observé
≠ Interest automatiquement
```

Une Veille conserve ses critères sensibles dans son owner ; `Moi` n’a besoin que d’une projection utile et autorisée.

---

# 8. `COLLECTIVES`

Question humaine :

> **À quels collectifs suis-je réellement relié, et dans lesquels puis-je réellement agir ?**

Structure :

```text
COLLECTIVES
├── AUTHORIZED_SPACES[]
├── TEAMS[]
└── GROUPS[]
```

Cardinalités :

```text
AUTHORIZED_SPACES → 0..n
TEAMS              → 0..n
GROUPS             → 0..n
```

Les trois relations restent distinctes.

```text
AUTHORIZED_SPACE
→ contexte collectif pour lequel une autorité réelle a été résolue

TEAM MEMBERSHIP
→ collaboration

GROUP MEMBERSHIP
→ appartenance / ciblage / éligibilité
```

Invariants :

```text
TeamMembership
≠ authority

GroupMembership
≠ authority

Membership
≠ Mandate
```

Le client ne déduit jamais `can_act` depuis un membership.

L’autorité nécessaire à l’inventaire `authorized_spaces` est résolue côté serveur.

---

# 9. `RESOURCES`

Question humaine :

> **Qu’est-ce que je possède ou peux mobiliser sans confondre les natures de preuve, ressource et credential ?**

Structure :

```text
RESOURCES
├── PERSONAL_ASSETS[]
├── PROOFS[]
└── CREDENTIALS_TRUST[]
```

Cardinalités :

```text
PERSONAL_ASSETS     → 0..n
PROOFS              → 0..n
CREDENTIALS_TRUST   → 0..n
```

Invariants :

```text
PersonalAsset
≠ JourneyArtifact

PersonalAsset
≠ Proof

Proof
≠ Credential Trust

Credential Trust
≠ AccessCredential

posséder un document
≠ satisfaire un Requirement
```

Les fichiers privés, storage paths, hashes, URLs privées et secrets ne sont pas placés dans la projection générale.

---

# 10. `Access` dans `Moi`

`Access` est une vérité importante mais ne devient pas une sous-famille de `RESOURCES`.

```text
Access
≠ Resource
```

La racine `Moi` doit donc privilégier :

```text
OWNER_HANDOFF → Mes accès
```

plutôt que recopier les droits et credentials dans `resources`.

Un Access durable non engagé peut rester pertinent dans le capital personnel sans devenir automatiquement `En cours`.

---

# 11. `APPUIS`

Le runtime possède déjà un regroupement humain de Presentation autour de réalités telles que :

```text
Recognition
Loyalty
Partner
```

Le contrat cible autorise ce regroupement si son utilité est réelle.

```text
APPUIS
= territoire de Presentation conditionnel
```

mais :

```text
Recognition
≠ Loyalty
≠ Partner
```

Interdits :

```text
SupportDomain universel
wallet transverse
Makolo Points
score social
total de valeur multi-domaines
```

Cardinalité :

```text
APPUIS
→ 0..1 territoire

éléments d'appui
→ 0..n
```

Une famille absente ne laisse pas nécessairement un conteneur vide.

---

# 12. `OWNER_HANDOFFS`

Les profondeurs ne doivent pas être copiées dans la racine.

Handoffs légitimes possibles :

```text
Passport
Resources
Accesses
History
Partners
Recognition
Loyalty
Groups
Collectives detail
Profile owner/settings
```

Cardinalité :

```text
0..n
```

Un handoff signifie :

> une profondeur owner-backed existe et le serveur autorise l’utilisateur à y entrer.

Le client ne construit jamais une URL par convention depuis `kind`.

---

# 13. Cardinalités finales de `Moi`

| Élément | Cardinalité |
|---|---:|
| Actor Context | 1 |
| Viewer | 1 |
| Identity | 1 |
| Passport preview | 0..1 |
| Interests | 0..n |
| Open To | 0..n |
| Watches | 0..n |
| Bookmarks | 0..n |
| Followed Spaces | 0..n |
| Followed Profiles | 0..n |
| Authorized Spaces | 0..n |
| Teams | 0..n |
| Groups | 0..n |
| Personal Assets | 0..n |
| Proofs | 0..n |
| Credentials Trust | 0..n |
| Appuis territory | 0..1 |
| Appui items | 0..n |
| Owner Handoffs | 0..n |

---

# 14. Réponse serveur conceptuelle de `Moi`

Sans figer les noms wire définitifs :

```text
ME RESPONSE
│
├── ACTOR_CONTEXT
│   └── Profile Me
│
├── VIEWER
│   └── Profile Me
│
├── IDENTITY
│
├── TERRITORIES
│   │
│   ├── PASSPORT
│   │   ├── available
│   │   ├── preview?
│   │   └── owner_handoff
│   │
│   ├── CONSIDERATIONS
│   │   ├── interests[]
│   │   ├── open_to[]
│   │   ├── watches[]
│   │   ├── bookmarks[]
│   │   ├── followed_spaces[]
│   │   └── followed_profiles[]
│   │
│   ├── COLLECTIVES
│   │   ├── authorized_spaces[]
│   │   ├── teams[]
│   │   └── groups[]
│   │
│   ├── RESOURCES
│   │   ├── personal_assets[]
│   │   ├── proofs[]
│   │   └── credentials_trust[]
│   │
│   └── APPUIS?
│       └── appui_items[]
│
└── OWNER_HANDOFFS[]
```

---

# 15. Responsabilités serveur de `Moi`

Le serveur établit :

- le Profile sujet ;
- l’identité autorisée à projeter ;
- les Spaces réellement autorisés ;
- les Team/Group memberships visibles ;
- les Interests/OpenTo/Watches/Bookmarks/Follows réellement établis ;
- les Personal Assets/Proofs/Credentials réellement accessibles ;
- l’existence légitime des appuis ;
- les links/capabilities/handoffs ;
- la divulgation minimale ;
- la provenance/fraîcheur métier lorsqu’elle est significative.

Le serveur ne doit pas :

- créer un score personnel transverse ;
- transformer un comportement observé en Interest ;
- confondre Access et Resource ;
- confondre Team/Group membership et autorité ;
- exposer des secrets pour simplifier le client.

---

# 16. Responsabilités client de `Moi`

Le client peut :

```text
ordonner et représenter les territoires selon le contrat
adapter Compact / Medium / Wide
humaniser les dates et formats
gérer sélection / scroll / profondeur locale
utiliser le snapshot local
afficher les états empty locaux
choisir les bons viewers média/document
```

Le client ne peut jamais :

```text
recalculer l'autorité d'un Space
déduire Requirement satisfaction
transformer Proof en Credential
transformer Resource en Access
reclasser les familles métier
fabriquer un score de complétion
```

---

# 17. États UX de `Moi`

## 17.1 Racine

Après authentification et projection disponible :

```text
IDENTITY existe
```

Donc `Moi` n’est normalement pas un écran globalement vide.

## 17.2 Empty local

Les absences sont locales :

```text
Passport absent
Considerations vides
Collectives vides
Resources vides
Appuis absents
```

Aucun score :

```text
Profil complété à 42 %
```

ne domine la surface.

## 17.3 Loading / first availability

Sans snapshot :

```text
first availability
```

La structure des territoires peut être préservée sans fabriquer de contenu.

## 17.4 Refresh

Avec snapshot :

```text
content + refreshing
```

Le contenu ne disparaît pas.

## 17.5 Offline

Avec snapshot :

```text
content + offline
```

Le capital connu reste lisible.

Aucune autorité nouvelle n’est créée hors connexion.

## 17.6 Failure partielle

Une erreur dans `RESOURCES` ne doit pas casser `IDENTITY`, `COLLECTIVES` ou `CONSIDERATIONS`.

La dégradation est territoire par territoire lorsque possible.

---

# 18. Local-first de `Moi`

Le client MAY conserver, selon sécurité :

```text
identity snapshot
passport preview
considerations
collectives connues
resources autorisées
appuis visibles
owner handoffs
```

Mais :

```text
local membership
≠ nouvelle authority

ancien Access
≠ validité actuelle garantie

pending edit
≠ confirmation serveur
```

La fraîcheur peut être spécifique au territoire.

---

# 19. Profondeur de `Moi`

Principe :

```text
ROOT
→ reconnaître ce qui existe

N2
→ comprendre un territoire / objet

OWNER DEPTH
→ modifier ou agir dans le domaine propriétaire
```

La largeur d’écran ne doit pas créer artificiellement plus de profondeur cognitive.

`Moi` reste :

```text
structure + capital
```

et non une grille de dashboard.

---

# 20. Critères de sortie pour une implémentation Mature de `Moi`

Une implémentation crédible doit démontrer :

- `request.user` comme sujet unique ;
- identité privée bornée ;
- Passport distinct du Profile ;
- Interest / OpenTo / Watch / Bookmark / Follow distincts ;
- Authorized Space distinct de Team/Group membership ;
- aucune autorité déduite côté client ;
- PersonalAsset / Proof / Credential Trust distincts ;
- aucun AccessCredential exposé ;
- Access conservé dans son owner ;
- appuis conditionnels sans wallet transverse ;
- owner handoffs réels ;
- empty local par territoire ;
- refresh sans disparition du contenu ;
- offline lisible ;
- isolation stricte par Profile ;
- aucune PII inutile ;
- aucun score humain ou de complétion dominant ;
- aucune régression IDOR.

---

# 21. Points volontairement non figés pour `Moi`

Restent ouverts :

1. noms JSON finaux ;
2. `schema_version` final ;
3. éventuelle présence explicite de `ACTOR_CONTEXT` et `VIEWER` au wire si le scope `/me` suffit techniquement ;
4. ordre exact des territoires ;
5. contenu précis des previews Passport/Appuis ;
6. granularité de freshness par territoire ;
7. stratégie finale de pagination des profondeurs ;
8. détail exact de l’édition Profile ;
9. microcopy finale ;
10. politique exacte de cache média/documents privés.

Aucun de ces points ne justifie un nouveau domaine persistant.

---

# PARTIE II — `NOUS`

# 22. Question humaine

> **Qui sommes-nous et comment fonctionnons-nous ensemble ?**

Développement :

> **Qui sommes-nous ? Qui peut agir ? Qui porte quoi ? Comment cette identité collective reste-t-elle durable, sûre et gouvernable ?**

`Nous` est la cinquième porte de l’expérience Space.

Il n’est pas le cœur des opérations quotidiennes.

---

# 23. Définition

> **Nous est la projection humaine de l’identité durable du Space, de sa structure collective, des responsabilités et autorités légitimement visibles, de ses relations institutionnelles utiles et des profondeurs nécessaires à sa continuité organisationnelle.**

`Nous` n’est pas :

```text
Settings
console admin
org chart obligatoire
CRM
matrice Permission brute
ERP
dashboard
Métier
Now
```

La racine doit donner une **lecture humaine du collectif**.

---

# 24. Acteur et viewer

## 24.1 `ACTOR_CONTEXT`

Cardinalité :

```text
exactement 1
```

Valeur :

```text
Space courant
```

## 24.2 `VIEWER`

Cardinalité :

```text
exactement 1
```

Valeur :

```text
Profile humain authentifié
```

Exemple :

```text
ACTOR_CONTEXT
→ Mulykap

VIEWER
→ Jean
```

Le Space n’a pas de session humaine.

L’Avatar reste Jean.

---

# 25. `VIEWER_RELATION`

Dans `Nous`, le lien entre le viewer humain et le Space doit être explicite sémantiquement.

Question :

> **Quelle est ma relation légitime avec ce Space ?**

Structure conceptuelle :

```text
VIEWER_RELATION
├── RESPONSIBILITIES[]
├── AUTHORITY_SUMMARY?
├── RELEVANT_SCOPES / CONTEXTS[]
└── HANDOFFS[]
```

Cardinalité :

```text
VIEWER_RELATION → exactement 1 structure
RESPONSIBILITIES → 0..n
RELEVANT_CONTEXTS → 0..n
HANDOFFS → 0..n
AUTHORITY_SUMMARY → 0..1
```

Cette projection est viewer-specific.

Elle ne fait pas partie de l’identité intrinsèque du Space.

---

# 26. `COLLECTIVE_IDENTITY`

Cardinalité :

```text
exactement 1
```

Structure conceptuelle :

```text
COLLECTIVE_IDENTITY
├── identity
├── representation
├── public_presence?
├── general_contacts?
├── general_location?
├── archetype
├── lifecycle
├── mission?
└── owner handoff?
```

L’identité durable du Space reste petite.

Elle peut représenter :

```text
nom
slug / id stable
description
contacts généraux
site / référence publique
localisation générale
visibilité publique
archétype
lifecycle
Trust / vérification par références utiles
mission si pertinente
```

---

# 27. Ce qui n’appartient pas à `COLLECTIVE_IDENTITY`

Ne deviennent pas identité du Space simplement parce qu’ils décrivent son activité :

```text
routes
véhicules
produits
services
prix
stock
capacity
horaires métier
Requirements
documents métier
programmes
Payments
clients
procédures
catalogues
```

Ces vérités appartiennent à leurs domaines propriétaires.

Principe :

> Une information appartient directement au Space seulement si elle caractérise durablement l’acteur collectif lui-même et qu’aucun owner canonique ne la porte correctement.

---

# 28. `TEAM / COLLABORATORS`

Question :

> **Avec qui fonctionnons-nous ?**

Structure :

```text
TEAM
├── SUMMARY?
├── TEAMS[]
└── COLLABORATORS[]
```

Cardinalités :

```text
SUMMARY        → 0..1
TEAMS          → 0..n
COLLABORATORS  → 0..n
```

Invariants :

```text
TeamMembership
≠ Mandate

TeamMembership
≠ Permission
```

La racine peut dire :

> Marie travaille avec nous.

La gouvernance peut expliquer séparément :

> Marie peut agir sur tel périmètre.

---

# 29. `RESPONSIBILITY_STRUCTURE`

Question :

> **Qui porte quoi ?**

Structure :

```text
RESPONSIBILITY_STRUCTURE
├── SUMMARY?
└── RESPONSIBILITIES[]
```

Chaque responsabilité peut conceptuellement porter :

```text
actor
kind / responsabilité humaine
scope humain
validity?
source / owner
```

Cardinalités :

```text
SUMMARY           → 0..1
RESPONSIBILITIES  → 0..n
```

Invariants :

```text
Assignment
= responsabilité

Assignment
≠ autorité
```

La racine peut montrer une synthèse.

Les détails appartiennent à une profondeur appropriée.

---

# 30. `GOVERNANCE`

Question :

> **Qui peut agir et comment l’organisation préserve-t-elle son autorité légitime ?**

Structure :

```text
GOVERNANCE
├── OWNERSHIP
├── AUTHORITY_PROJECTIONS[]
├── INSTITUTIONAL_CAPABILITIES[]
└── HANDOFFS[]
```

Cardinalité :

```text
GOVERNANCE            → 0..1 structure
OWNERSHIP holders     → 0..n
AUTHORITY_PROJECTIONS → 0..n
CAPABILITIES          → 0..n
HANDOFFS              → 0..n
```

L’autorité est résolue par le serveur depuis Mandate / Permission.

Interdits :

```text
TeamMembership → Permission
GroupMembership → Permission
Archetype → Permission
Entitlement → Permission
Creator → Owner éternel
```

Le client ne recalcule jamais l’autorité.

---

# 31. `OWNERSHIP`

L’ownership appartient conceptuellement à la gouvernance de `Nous`.

Mais :

```text
created_by
≠ owner éternel
```

L’autorité d’Owner est portée par Mandate.

Le contrat permet plusieurs Owners.

Cardinalité :

```text
0..n Owner projections
```

Le dernier Owner actif doit être protégé par les règles serveur ; le client ne porte pas cette contrainte.

---

# 32. `RELATIONS`

Question :

> **Avec quels acteurs, groupes et partenaires le Space est-il institutionnellement relié ?**

Structure racine :

```text
RELATIONS
├── SUMMARY?
└── OWNER_HANDOFFS[]
```

Cardinalité :

```text
SUMMARY        → 0..1
OWNER_HANDOFFS → 0..n
```

`Nous` peut donner accès à :

```text
Partners
CRM
Groups
Audiences
contacts institutionnels
connexions
```

mais :

```text
Nous
≠ CRM
≠ Groups
≠ Partners
```

Il ne copie pas les vérités de ces owners.

---

# 33. `TRUST`

Question :

> **Quels faits de confiance sont réellement établis sur ce Space ?**

Structure :

```text
TRUST
├── SUMMARY?
├── ESTABLISHED_FACTS[]
└── OWNER_HANDOFF?
```

Cardinalités :

```text
SUMMARY             → 0..1
ESTABLISHED_FACTS   → 0..n
OWNER_HANDOFF       → 0..1
```

Exemples :

```text
identité vérifiée
autorité d'un représentant vérifiée
fait professionnel vérifié
```

Interdit :

```text
score global de qualité du Space
```

La vérification répond à une assurance précise.

---

# 34. `ARCHETYPE`

L’archétype peut apparaître dans l’identité collective.

Il décrit :

> le centre de gravité durable du fonctionnement du Space.

Mais :

```text
Archetype
≠ Permission
≠ Mandate
≠ Entitlement
≠ forme juridique
≠ profession globale
≠ whitelist de verticales
```

Changer d’archétype ne doit pas détruire l’historique opérationnel.

---

# 35. `LIFECYCLE`

Valeurs conceptuelles actuelles :

```text
ACTIVE
SUSPENDED
ARCHIVED
```

Cardinalité :

```text
exactement 1 état lorsque la projection l'expose
```

Invariants :

```text
LIFECYCLE
≠ VERIFICATION
≠ READINESS
```

Pas de :

```text
Space 70 % prêt
Space incomplete
Space configuring
```

comme statut transverse générique.

---

# 36. `INSTITUTIONAL_HANDOFFS`

Les profondeurs de `Nous` peuvent contenir selon autorité :

```text
public presence
archetype
Team
responsibilities
ownership
Trust
Subscription
Entitlements
connections
archive / restore
Space settings
```

Cardinalité :

```text
0..n
```

Ces éléments **ne doivent pas dominer la racine**.

Règle :

```text
Nous
→ lecture humaine d'abord

Settings / gouvernance détaillée
→ profondeur institutionnelle
```

---

# 37. Cardinalités finales de `Nous`

| Élément | Cardinalité |
|---|---:|
| Actor Context | 1 |
| Viewer | 1 |
| Viewer Relation | 1 |
| Viewer Responsibilities | 0..n |
| Viewer Authority Summary | 0..1 |
| Viewer Relevant Contexts | 0..n |
| Collective Identity | 1 |
| Team Summary | 0..1 |
| Teams | 0..n |
| Collaborators | 0..n |
| Responsibility Summary | 0..1 |
| Responsibilities | 0..n |
| Governance | 0..1 |
| Owners | 0..n |
| Authority Projections | 0..n |
| Institutional Capabilities | 0..n |
| Relations Summary | 0..1 |
| Relation Handoffs | 0..n |
| Trust Summary | 0..1 |
| Trust Facts | 0..n |
| Institutional Handoffs | 0..n |

---

# 38. Réponse serveur conceptuelle de `Nous`

Sans figer les noms wire définitifs :

```text
NOUS RESPONSE
│
├── ACTOR_CONTEXT
│   └── Space
│
├── VIEWER
│   └── Profile
│
├── VIEWER_RELATION
│   ├── responsibilities[]
│   ├── authority_summary?
│   ├── relevant_contexts[]
│   └── handoffs[]
│
├── COLLECTIVE_IDENTITY
│   ├── representation
│   ├── public_presence?
│   ├── general_contacts?
│   ├── general_location?
│   ├── archetype
│   ├── lifecycle
│   ├── mission?
│   └── owner_handoff?
│
├── TEAM
│   ├── summary?
│   ├── teams[]
│   └── collaborators[]
│
├── RESPONSIBILITY_STRUCTURE
│   ├── summary?
│   └── responsibilities[]
│
├── GOVERNANCE?
│   ├── owners[]
│   ├── authority_projections[]
│   ├── institutional_capabilities[]
│   └── handoffs[]
│
├── RELATIONS
│   ├── summary?
│   └── owner_handoffs[]
│
├── TRUST
│   ├── summary?
│   ├── established_facts[]
│   └── owner_handoff?
│
└── INSTITUTIONAL_HANDOFFS[]
```

---

# 39. Responsabilités serveur de `Nous`

Le serveur établit :

- le Space acteur courant ;
- le Profile viewer ;
- la relation légitime entre viewer et Space ;
- les responsabilités réellement pertinentes ;
- l’autorité effective et les capabilities légitimes ;
- l’identité collective ;
- le lifecycle ;
- l’archétype ;
- les Teams et collaborateurs visibles ;
- les responsabilités visibles ;
- l’ownership ;
- les faits Trust ;
- les relations institutionnelles exposables ;
- les handoffs ;
- la divulgation minimale ;
- toute revalidation des mutations sensibles.

Le serveur ne doit pas :

- transformer TeamMembership en autorité ;
- exposer des Mandates/Permissions bruts sans besoin ;
- absorber CRM/Partner/Group/Analytics dans `Nous` ;
- dupliquer des ressources métier du Space ;
- produire un score universel de qualité ou de maturité.

---

# 40. Responsabilités client de `Nous`

Le client peut :

```text
présenter l'identité du Space
humaniser les responsabilités et scopes fournis
adapter la densité par écran
gérer les profondeurs locales
conserver le snapshot autorisé
afficher les faits Trust reçus
montrer les handoffs disponibles
```

Le client ne peut jamais :

```text
déduire une Permission depuis TeamMembership
déduire ownership depuis created_by
déduire authority depuis archetype
déduire authority depuis Entitlement
modifier localement le lifecycle
considérer une capability cache comme autorité permanente
```

---

# 41. États UX de `Nous`

## 41.1 Racine

Le Space possède toujours une identité lorsqu’il est accessible.

La racine n’est donc normalement pas un écran « aucune donnée ».

## 41.2 Empty local

Les absences sont locales :

```text
aucune Team secondaire
aucun partenaire visible
aucun Trust fact supplémentaire
aucune connexion institutionnelle
```

Cela ne rend pas le Space « incomplet ».

## 41.3 Loading / first availability

Sans snapshot :

```text
first availability
```

Ne pas fabriquer de gouvernance ou de counts.

## 41.4 Refresh

Avec snapshot :

```text
content + refreshing
```

La racine reste lisible.

## 41.5 Offline

Avec snapshot :

```text
content + offline
```

Le client peut continuer à montrer l’identité et les faits connus.

Mais :

```text
offline
≠ nouvelle autorité
≠ mutation institutionnelle confirmée
```

## 41.6 Permission / authority change

Une authority cache peut devenir ancienne.

Avant une mutation sensible :

```text
server revalidation required
```

---

# 42. Local-first de `Nous`

Le client MAY conserver :

```text
Space identity
public representation
known Team summaries
known relationship summaries
known Trust facts
viewer responsibilities déjà projetées
institutional handoffs
```

Le client MUST NOT être autorité pour :

```text
Mandate
Permission
ownership transfer
Space lifecycle transition
Entitlement validity
concurrent governance state
current sensitive capability
```

Principe :

> Offline `Nous` permet de comprendre le collectif ; il ne devient jamais le siège de gouvernance autoritative.

---

# 43. Profondeur de `Nous`

La racine doit rester lisible humainement.

Exemple conceptuel :

```text
Mulykap
Transport de voyageurs

Équipe
12 personnes

Responsabilités
4 domaines actifs

Relations
partenaires et groupes pertinents

Confiance
identité vérifiée
```

Puis :

```text
tap Équipe
→ Team depth

tap Responsabilités
→ Assignment / responsibility depth

tap Gouvernance
→ ownership / authority depth

tap Confiance
→ Trust depth

tap Paramètres
→ institutional settings
```

La racine ne devient pas la console administrative.

---

# 44. Critères de sortie pour une implémentation Mature de `Nous`

Une implémentation crédible doit démontrer :

- Actor Context = Space ;
- Viewer = Profile humain ;
- Avatar toujours humain ;
- Viewer Relation distincte de l’identité du Space ;
- identité Space petite et durable ;
- aucune donnée métier verticale injectée dans l’identité ;
- TeamMembership distinct de Mandate ;
- Assignment distinct de Mandate ;
- ownership basé sur Mandate, pas `created_by` ;
- plusieurs Owners supportés ;
- authority résolue serveur ;
- responsabilité et autorité représentées séparément ;
- Relations comme handoffs, pas copies CRM/Partners/Groups ;
- Trust factuel sans score global ;
- lifecycle distinct de verification/readiness ;
- Settings en profondeur, pas comme racine ;
- local-first lisible mais gouvernance revalidée ;
- divulgation minimale ;
- tests d’autorité et IDOR ;
- aucune PII membre inutile ;
- aucune régression liée au changement d’archétype.

---

# 45. Points volontairement non figés pour `Nous`

Restent ouverts :

1. noms JSON finaux ;
2. `schema_version` final ;
3. endpoint final de la racine `Nous` ;
4. forme exacte de `VIEWER_RELATION` au wire ;
5. niveau de détail des responsibility projections à la racine ;
6. niveau de détail des authority projections à la racine ;
7. distinction exacte entre summaries et owner handoffs ;
8. pagination des Teams/collaborateurs/relations ;
9. microcopy finale par archétype ;
10. politique exacte de cache/freshness des authority summaries ;
11. profondeur exacte Subscription/Entitlements ;
12. structure finale des actions d’archivage/restauration ;
13. politique finale de représentation des profils collaborateurs selon confidentialité.

Aucun de ces points ne justifie un nouveau domaine persistant.

---

# 46. Séparation finale à préserver

`Moi` et `Nous` occupent une position comparable dans le shell mais ne partagent pas un contrat métier.

```text
MOI
→ Profile
→ capital personnel
→ considérations
→ collectifs
→ ressources
→ appuis
→ profondeurs personnelles
```

```text
NOUS
→ Space
→ identité collective
→ viewer relation
→ équipe
→ responsabilités
→ gouvernance
→ relations
→ Trust
→ profondeurs institutionnelles
```

Ne pas généraliser en :

```text
Actor
→ generic territories
```

si cela oblige ensuite le client à réinterpréter la sémantique.

La réutilisation correcte se situe seulement dans les primitives :

```text
ObjectProjection
owner handoffs
links/capabilities
local-first snapshot
freshness
progressive disclosure
adaptive layout
media/document viewers
```

La signification reste propre à chaque surface.

---

# 47. Formulations finales

## `Moi`

> **Moi est la surface personnelle Makolo qui rend compréhensible ce qui est déjà en place autour du Profile : son identité, ce qui peut le représenter, ce qui compte pour lui, les collectifs auxquels il est légitimement relié, les ressources et faits de confiance qu’il peut mobiliser, ainsi que les profondeurs propriétaires utiles à la suite. Moi n’est ni un profil social, ni un dashboard, ni un portefeuille universel, ni une copie des domaines propriétaires.**

## `Nous`

> **Nous est la surface Space Makolo qui rend compréhensible l’identité collective, la relation du viewer au Space, les personnes qui y collaborent, les responsabilités, l’autorité légitime, les relations institutionnelles et les faits de confiance nécessaires pour comprendre comment le collectif fonctionne et reste gouvernable. Nous n’est ni Settings, ni CRM, ni console admin, ni matrice de Permissions, ni copie du Métier.**

---

# 48. Prochaine séquence de travail

Après ce gel :

```text
Space Now
→ Qu’est-ce qui mérite notre attention maintenant ?

Space Découvrir
→ Qu’est-ce qui pourrait nous aider à avancer ?

Space Métier / Ongoing contextuel
→ Qu’est-ce que nous opérons réellement ?
```

`Métier` ne sera pas simplement `Ongoing Me` avec `actor=Space`.

Sa composition dépendra de l’archétype et surtout de l’**Operational Footprint réel**, sans transférer l’autorité depuis l’archétype.

