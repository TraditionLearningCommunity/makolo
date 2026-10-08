# Makolo — **Personnes & relations**
## Contrat UX consolidé — relations du Space, pluralité des liens, recherche et profondeur owner-backed

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence — surface majeure secondaire Space  
**Question humaine :** **Avec qui avançons-nous ?**  
**Actor Context :** Space  
**Viewer :** Profile authentifié agissant explicitement dans ce Space  
**Portée :** Web, Flutter, tablette/desktop adaptatif, Presentation, recherche relationnelle, local-first, handoffs owner  
**Base runtime vérifiée :** `main@52eced16a35d779f98eb8d43bbea405fd7f7b4b0`  
**Nature :** contrat UX et de projection ; ne crée aucun nouveau domaine `Person`, `Relationship` ou CRM universel  
**Promesse produit :** **Makolo marche pour vous.**  
**Principe d’expérience :** **Pas le plaisir de rester. Le plaisir d’avancer.**

---

# 0. Formule

```text
Personnes & relations
=
relations réelles du Space
+
sens propre de chaque relation
+
recherche transversale sans fusion
+
profondeurs propriétaires
```

et non :

```text
Personnes & relations
=
base universelle de personnes
+
CRM unique
+
annuaire de tout le monde
+
permissions implicites
```

---

# 1. Question humaine

La surface répond à :

> **Avec qui avançons-nous ?**

Elle doit permettre de comprendre rapidement :

```text
qui travaille avec nous
+
quels groupes existent réellement
+
quels contacts / clients comptent
+
quels publics ou audiences sont structurés
+
quels partenaires sont reliés au Space
+
quelle relation exacte nous relie à chacun
```

Elle ne doit jamais répondre en fusionnant ces réalités dans une catégorie générique « personne ».

---

# 2. Position dans l’expérience Space

La navigation primaire reste :

```text
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
```

`Personnes & relations` est une **surface majeure secondaire**.

Elle ne devient pas un sixième onglet primaire.

Chemins naturels :

```text
Nous
→ Personnes & relations
```

ou depuis une profondeur métier légitime :

```text
Prestation
→ personne concernée
→ relation propriétaire
```

```text
Programme
→ groupe / cohorte
→ relation propriétaire
```

```text
Initiative
→ partenaire
→ relation propriétaire
```

---

# 3. Frontière avec Nous

```text
Nous
→ qui sommes-nous et comment sommes-nous organisés ?

Personnes & relations
→ avec qui avançons-nous ?
```

`Nous` peut résumer :

- équipe ;
- responsabilités ;
- relations ;
- Trust ;
- identité collective.

`Personnes & relations` devient la surface de **collection, recherche et profondeur relationnelle**.

`Nous` ne devient pas propriétaire de CRM, Groups, Audiences ou Partners.

---

# 4. Frontière avec Team

```text
TeamMembership
= collaboration
```

mais :

```text
TeamMembership
≠ Mandate
≠ Permission
```

La Team est une famille relationnelle possible dans cette surface.

L’owner Team conserve ses mutations et son autorité.

---

# 5. Frontière avec CRM

```text
CRMContact
= relation CRM du Space
```

Il peut être lié à un Profile Makolo ou exister sans Profile.

Mais :

```text
CRMContact
≠ Profile
≠ TeamMember
≠ Partner
```

La surface ne transforme pas Makolo en CRM universel.

---

# 6. Frontière avec Groupes

```text
Group
= collectif ou segmentation explicite détenue par son owner
```

```text
GroupMembership
= appartenance
```

mais :

```text
GroupMembership
≠ authority
```

Un groupe Space et un groupe personnel restent distincts.

La surface Space ne récupère pas silencieusement les groupes personnels des membres.

---

# 7. Frontière avec Audiences

Une Audience peut être :

- créée manuellement ;
- issue d’un Groupe ;
- issue d’un snapshot de Groupe ;
- structurée pour le CRM.

Mais :

```text
Audience
≠ Group
≠ follower count
≠ public abstrait universel
```

Le contrat conserve la provenance de l’Audience.

---

# 8. Frontière avec Partners

```text
Partner
= relation partenaire du Space
```

Un Partner peut être lié à un Profile, mais peut aussi exister sans compte Makolo lié.

```text
Partner
≠ TeamMember
≠ CRMContact
≠ Mandate holder
```

Une relation Partner n’accorde aucune autorité implicite.

---

# 9. Distinction canonique

Invariant source :

```text
CRMContact
!= TeamMember
!= GroupMember
!= Partner
!= Mandate holder
!= follower
!= participant
```

La même personne peut apparaître dans plusieurs relations différentes.

---

# 10. Même Profile, plusieurs relations

Exemple :

```text
Marie Kalala
Collaboratrice · Exploitation
```

et :

```text
Marie Kalala
Contact CRM · Client
```

peuvent être deux résultats légitimes.

La Presentation peut reconnaître qu’il s’agit du même Profile lorsque l’identité canonique le permet.

Elle ne doit pas fusionner les relations.

---

# 11. Pas de `UniversalPerson`

Ce contrat ne justifie pas un nouveau modèle :

```text
Person
Relationship
SpacePerson
RelationshipRole
UniversalContact
```

Le besoin de recherche transverse est un besoin de **projection**, pas une raison de recopier les domaines propriétaires.

---

# 12. Pas de déduplication par nom

Deux lignes portant le même nom ne doivent jamais être fusionnées sur le seul nom.

```text
nom identique
≠ identité identique
```

---

# 13. Pas de déduplication par email inter-domaines improvisée

Le CRM possède ses propres invariants d’identité.

Partner possède les siens.

Team et Profile possèdent les leurs.

La Presentation ne doit pas créer un resolver local sur la base de l’email.

---

# 14. Identité Profile quand elle existe

Lorsqu’un owner expose explicitement un `profile_id`, la surface peut utiliser :

- nom Profile ;
- avatar autorisé ;
- lien vers Profile si projection légitime.

Mais la relation affichée reste celle de l’owner.

---

# 15. Relation sans Profile

Un CRMContact ou Partner peut exister sans Profile Makolo.

La surface doit rester pleinement utilisable :

```text
Acme Consulting
Partenaire · Agence
```

ou :

```text
Jean M.
Contact client
```

Pas de message « Profile manquant » comme erreur UX.

---

# 16. Personnalité UX

La personnalité est :

> **relations + provenance + clarté**

La surface doit être :

- humaine ;
- searchable ;
- de densité moyenne ;
- claire sur le type de relation ;
- prudente sur les données privées ;
- professionnelle sans devenir un back-office ;
- capable de montrer qu’une personne appartient à plusieurs mondes relationnels.

---

# 17. N1 — structure générale

```text
RELATIONSHIPS
│
├── HEADER
│   ├── retour vers Nous
│   ├── titre archétypal
│   └── recherche
│
├── CONTEXT
│   ├── Space
│   └── authority / responsibility si utile
│
├── RELATION FAMILIES
│   ├── Team ?
│   ├── Groups ?
│   ├── CRM contacts ?
│   ├── Audiences ?
│   ├── Partners ?
│   └── autres owner-backed réelles ?
│
└── DEPTH
    ├── relation N2
    ├── collection owner
    ├── Profile projection si légitime
    └── owner management
```

---

# 18. Titre par archétype

Le titre visible est contextuel :

```text
generic
→ Personnes & relations

creative
→ Publics & partenaires

media
→ Publics & partenaires

education
→ Groupes, personnes & partenaires

commerce
→ Clients & relations

service_provider
→ Clients & partenaires

transport_operator
→ Relations

community
→ Communauté & partenaires
```

Ces libellés sont UX.

Ils ne créent aucun nouveau modèle.

---

# 19. Pourquoi le titre change

Le backend reste générique.

Le vocabulaire visible reflète le centre de gravité du Space.

Le même owner CRM peut être présenté comme :

```text
Clients
Contacts
Personnes
```

selon contexte, sans modifier sa vérité.

---

# 20. Le titre ne filtre pas arbitrairement les owners

`Clients & partenaires` n’implique pas que Team ou Groups cessent d’exister.

Le titre priorise le modèle mental.

Les sections visibles restent déterminées par :

- données réelles ;
- authority ;
- capabilities ;
- Operational Footprint ;
- intérêt UX.

---

# 21. Header secondaire

La surface étant secondaire, le header suit :

```text
← | titre humain | actions contextuelles
```

Exemple :

```text
← Nous
Clients & relations
[Recherche]
```

Le Space actif reste reconnaissable dans le shell.

---

# 22. Question visible

Le titre peut être accompagné, surtout à la racine, par :

> **Avec qui avançons-nous ?**

Cette question n’a pas besoin d’être répétée dans toutes les profondeurs.

---

# 23. Densité

Référence :

```text
Personnes & relations
→ densité moyenne
```

La surface n’est ni aussi calme que Maintenant, ni aussi dense que Piloter.

---

# 24. Organisation N1

La racine est **section-first**, mais orientée collection.

Exemple :

```text
Clients & relations

Clients / contacts
...

Partenaires
...

Groupes
...

Équipe
...
```

L’ordre varie par archétype.

---

# 25. Sections absentes

Invariant :

> **Les sections absentes disparaissent.**

Ne jamais produire :

```text
Équipe 0
Groupes 0
Clients 0
Audiences 0
Partenaires 0
```

comme dashboard vide.

---

# 26. Masqué ≠ vide

Invariant de sécurité et de langage :

```text
section non exposée par authority
≠ collection vide
```

Le client ne doit pas dire :

```text
Aucun partenaire
```

si la réalité est :

```text
vous ne pouvez pas voir les partenaires
```

---

# 27. Root sans section visible

Si aucune collection relationnelle globale n’est exposée :

```text
Aucune collection relationnelle n’est disponible dans votre contexte actuel.
```

Si l’authority est Activity-limited :

```text
Votre responsabilité actuelle est limitée à certaines activités.
Makolo n’élargit pas ce périmètre aux relations privées du Space.
```

---

# 28. Activity-limited viewer

Le runtime courant ne rend aucune collection globale à un Viewer `activity_limited`.

Ce contrat conserve cette frontière.

Une personne liée à une Activity peut néanmoins apparaître **dans la profondeur de cette Activity** si l’owner autorise la projection.

Mais :

```text
relation métier locale
≠ accès aux relations globales du Space
```

---

# 29. Direct Space authority

Les collections globales sont permission-first.

Le simple fait de pouvoir `Agir comme` un Space ne garantit pas l’accès à toutes les relations.

---

# 30. Team — runtime actuel

Le runtime expose actuellement la Team dans cette projection seulement avec :

```text
direct Space authority
+
SPACE_TEAM_MANAGE
```

Le contrat n’invente pas aujourd’hui une Permission de lecture Team supplémentaire.

Une évolution future peut ajouter une capability read-only owner-backed, mais elle devra être explicite.

---

# 31. Groups — runtime actuel

La section Groups peut être visible avec :

```text
SPACE_GROUPS_VIEW
ou
SPACE_GROUPS_MANAGE
```

et seulement en authority Space directe dans la projection actuelle.

---

# 32. CRM — runtime actuel

La section CRM contacts et Audiences dépend de :

```text
CRM_VIEW
```

sur authority Space directe.

Les mutations CRM restent capability-gated séparément.

---

# 33. Partners — runtime actuel

Le runtime actuel expose Partners à certains viewers directs disposant de capacités Partner appropriées, notamment gestion ou finance.

Le contrat ne généralise pas un accès Partner universel.

---

# 34. Capabilities ≠ sections

Une section visible ne signifie pas nécessairement qu’elle est modifiable.

```text
VIEW
≠ MANAGE
```

Le client doit lire les capabilities owner-backed pour les actions.

---

# 35. Team section

La section Équipe présente une relation de collaboration.

Row candidate :

```text
Marie Kalala
Collaboratrice · Équipe
```

Si une responsabilité est disponible via un owner adapté :

```text
Marie Kalala
Collaboratrice · Exploitation
```

mais ne pas inventer la responsabilité depuis TeamMembership.

---

# 36. Team section ≠ authority matrix

La section Équipe ne montre pas par défaut :

- tous les Roles ;
- toutes les Permissions ;
- tous les scopes ;
- tous les Mandates.

Ces détails appartiennent aux profondeurs d’autorité.

---

# 37. Groups section

La section Groupes montre les collectifs Space réellement visibles.

Row candidate :

```text
Cohorte 2027
Groupe
```

ou un vocabulaire naturel :

```text
Promotion 2027
42 personnes
```

uniquement si le count est owner-backed.

---

# 38. Group discoverability

La visibilité/discoverability d’un Groupe est owner-backed.

La surface interne ne doit pas transformer un Groupe caché en projection publique.

---

# 39. Group membership policy

Les actions :

```text
Rejoindre
Demander à rejoindre
Inviter
```

ne sont proposées que selon la policy et l’autorité réelles.

---

# 40. CRM contacts section

Row candidate :

```text
Marie Kalala
Client · Contact CRM
```

ou :

```text
Acme SARL
Contact CRM
```

Le nom `CRM` peut disparaître du langage primaire si le contexte `Clients & relations` suffit.

---

# 41. CRM relation type

La Presentation doit expliquer la relation, pas le système :

Préférer :

```text
Client
Prospect
Contact
```

si owner-backed.

Éviter :

```text
CRMContact #UUID
```

---

# 42. CRM interaction history

L’historique d’interactions CRM appartient au CRM.

La racine Personnes & relations ne devient pas une timeline de toutes les interactions.

---

# 43. Audience section

Une Audience est une collection structurée.

Row candidate :

```text
Abonnés newsletter Lubumbashi
Audience
```

ou :

```text
Parents · Programme secondaire
Public
```

si le langage owner/context le permet.

---

# 44. Audience ≠ popularité

Ne pas afficher une Audience comme :

```text
12 400 followers
```

si elle est en réalité un segment CRM.

Pas de logique de popularité.

---

# 45. Audience source

Si utile en profondeur, le produit peut expliquer :

```text
Issue du groupe Alumni 2025
```

ou :

```text
Ajout manuel
```

sans polluer N1.

---

# 46. Partners section

Row candidate :

```text
Centre médical X
Partenaire · Entreprise
```

ou :

```text
Studio K
Partenaire média
```

selon `partner_kind` owner-backed.

---

# 47. Partner profile link

Si Partner est lié à un Profile :

```text
relation Partner
+
Profile associé
```

restent deux faits distincts.

Un tap principal ouvre d’abord la relation utile au contexte.

Un lien secondaire peut ouvrir le Profile si légitime.

---

# 48. Finance Partner

Les données financières Partner ne doivent jamais apparaître dans la racine relationnelle par simple présence d’un Partner.

Elles restent dans le domaine Partner/Finance avec authority adaptée.

---

# 49. Followers

Le runtime possède des relations de Follow privées.

Mais :

```text
follower
≠ CRMContact
≠ AudienceMember
≠ Partner
```

La surface ne crée pas de compteur public de followers.

---

# 50. Participants

Un participant à une Activity ou Occurrence n’est pas automatiquement un contact global du Space.

```text
participant
≠ CRMContact
```

Cette frontière est particulièrement importante pour Transport, Events et Education.

---

# 51. Voyageur ≠ client CRM automatique

Un Access ou une commande Transport ne doit pas créer implicitement une relation CRM persistante si le domaine ne le prévoit pas.

La surface globale ne transforme pas toute personne opérée en contact.

---

# 52. Bénéficiaire ≠ CRMContact automatique

Un bénéficiaire Service/Obtention peut rester contextuel à son dossier.

Le CRM reste une relation explicite.

---

# 53. Élève / participant ≠ Team

Une personne inscrite à un Programme n’est pas un collaborateur.

Une cohorte réelle peut être un Group si le domaine le porte.

---

# 54. Public ≠ Audience automatiquement

Le mot « public » peut être une traduction UX.

Il ne faut pas créer une Audience seulement parce qu’une Activity a un public.

---

# 55. Partenaire ≠ fournisseur universel

Un partenaire peut être agence, média, communauté, entreprise, ambassadeur ou autre owner-backed kind.

Ne pas réduire tous les Partners à « fournisseurs ».

---

# 56. Ordre des sections — generic

Candidate :

```text
Équipe
Groupes
Contacts
Partenaires
Audiences si réellement utilisées
```

L’ordre final peut être piloté par les sections présentes et les priorités contextuelles.

---

# 57. Ordre — creative

Titre :

```text
Publics & partenaires
```

Candidate :

```text
Publics / Audiences
Partenaires
Contacts
Groupes
Équipe
```

Le créatif ne devient pas réseau social.

---

# 58. Ordre — media

Titre :

```text
Publics & partenaires
```

Candidate :

```text
Audiences / Publics
Partenaires
Contacts
Groupes
Équipe
```

Les analytics d’audience restent dans Piloter.

---

# 59. Ordre — education

Titre :

```text
Groupes, personnes & partenaires
```

Candidate :

```text
Groupes / cohortes
Personnes / contacts
Partenaires
Équipe
Audiences si réelles
```

Les inscrits restent dans leurs owners métier lorsqu’ils ne sont pas une relation collective durable.

---

# 60. Ordre — commerce

Titre :

```text
Clients & relations
```

Candidate :

```text
Clients / contacts
Audiences
Partenaires
Groupes
Équipe
```

Commandes et Payments restent dans Commerce.

---

# 61. Ordre — service_provider

Titre :

```text
Clients & partenaires
```

Candidate :

```text
Clients / contacts
Partenaires
Groupes / audiences si réels
Équipe
```

Les Dossiers restent dans Prestations.

---

# 62. Ordre — transport_operator

Titre :

```text
Relations
```

Candidate :

```text
Contacts réels
Partenaires
Groupes éventuels
Équipe
```

Les voyageurs d’un départ restent dans le contexte Activity/Occurrence/Access selon autorité.

---

# 63. Ordre — community

Titre :

```text
Communauté & partenaires
```

Candidate :

```text
Groupes / communauté
Partenaires
Contacts
Audiences
Équipe
```

Les initiatives restent dans Métier.

---

# 64. L’ordre n’est pas une copie de `featured_modules`

Invariant :

```text
featured_modules
≠ sections N1 obligatoires
```

Les modules servent de signal produit, pas de layout.

---

# 65. Aperçu N1

Le runtime actuel borne chaque collection à un preview.

La racine peut montrer quelques entrées représentatives et :

```text
Voir l’équipe
Voir les groupes
Ouvrir les contacts
Voir les partenaires
```

Le nombre exact de lignes visibles reste adaptatif.

---

# 66. `has_more`

Si le serveur indique `has_more` :

```text
Voir tout
```

ou une formulation owner naturelle.

Éviter :

```text
Aperçu limité à 12 relations
```

comme langage final si l’information technique n’aide pas l’utilisateur.

---

# 67. Count

Ne pas afficher un total précis si la projection ne le fournit pas explicitement.

```text
has_more
≠ count total
```

---

# 68. Recherche transverse — rôle

La recherche répond à :

> **Qui ou quel collectif cherchons-nous dans les relations de ce Space ?**

Elle peut réunir plusieurs owners.

Elle ne fusionne pas leurs résultats.

---

# 69. Recherche — exemple canonique

```text
Marie Kalala
Collaboratrice · Exploitation

Marie Kalala
Contact CRM · Client
```

Le même nom peut apparaître plusieurs fois.

Chaque résultat dit **pourquoi il est là**.

---

# 70. Recherche — familles

La recherche peut couvrir, selon authority :

- Team ;
- Groups ;
- CRM contacts ;
- Audiences ;
- Partners ;
- autres relations owner-backed réellement admises.

Elle ne doit pas rechercher arbitrairement tous les Profiles Makolo.

---

# 71. Recherche globale ≠ recherche relationnelle

```text
Recherche globale Makolo
→ retrouver des réalités de l’application

Recherche relationnelle Space
→ retrouver une relation réelle de ce Space
```

La seconde est bornée par Space + authority.

---

# 72. Recherche et previews

La recherche ne doit pas se limiter aux 12 previews N1.

Une recherche mature nécessite une interrogation owner-backed ou une projection indexée autorisée.

Le client ne doit pas conclure « aucun résultat » après avoir cherché uniquement dans le cache de preview.

---

# 73. Recherche offline

Offline, le client peut chercher dans les données relationnelles déjà disponibles localement.

Il doit signaler la portée :

```text
Résultats disponibles sur cet appareil.
```

Il ne doit pas affirmer :

```text
Aucun résultat dans le Space.
```

si la recherche distante n’a pas été possible.

---

# 74. Recherche et relation type

Chaque résultat DOIT exposer au minimum :

```text
identité lisible
+
type de relation humain
```

Exemple :

```text
Marie Kalala
Partenaire · Ambassadrice
```

---

# 75. Recherche sans résultat

État :

```text
Aucune relation visible ne correspond à « Marie K. ».
```

Pas :

```text
Cette personne n’existe pas.
```

---

# 76. Recherche et création

Après NO_MATCH, le produit peut proposer une action owner-specific si capability réelle :

```text
Ajouter comme contact
Inviter dans l’équipe
Créer un partenaire
Créer un groupe
```

Mais il ne doit jamais proposer :

```text
Ajouter une personne
```

sans préciser la relation à créer.

---

# 77. Pas de bouton `Nouvelle personne`

Invariant majeur :

```text
Personne
≠ relation
```

La création porte toujours sur une relation ou un owner :

```text
Inviter un collaborateur
Ajouter un contact
Créer un groupe
Créer une audience
Ajouter un partenaire
```

---

# 78. Création contextuelle

La racine peut exposer des actions contextualisées selon sections et capabilities.

Sur Compact, utiliser un menu léger ou actions dans section.

Sur Wide, ne pas créer une toolbar ERP.

---

# 79. Mutation Team

Ajouter à l’équipe appartient à Organizations/Team.

Le serveur revalide authority au moment de la mutation.

La surface relationnelle ne doit pas exécuter la mutation localement par simple mise à jour optimiste de liste.

---

# 80. Mutation Group

Créer, inviter, approuver ou retirer un GroupMembership appartient à Groups.

`GroupMembershipSource` conserve sa provenance.

---

# 81. Mutation CRM

Créer/modifier un contact ou enregistrer une interaction appartient à CRM.

La surface relationnelle ne possède pas le lifecycle CRM.

---

# 82. Mutation Audience

Créer/modifier une Audience ou ses membres appartient à CRM/Audience.

Un Groupe source ou snapshot doit rester cohérent avec le Space.

---

# 83. Mutation Partner

Ajouter/modifier/clôturer un Partner appartient au domaine Partners.

Les éléments de finance/attribution restent dans leurs profondeurs owner.

---

# 84. N2 — principe

Sélectionner une ligne ouvre une **relation**, pas un profil universel.

N2 répond :

> **Quelle est exactement notre relation avec cette personne, ce groupe, ce public ou ce partenaire ?**

---

# 85. N2 — Team member

Candidate :

```text
← Équipe

Marie Kalala
Collaboratrice

Équipe
Équipe principale

Responsabilités
si owner-backed

Autorité
entrée vers profondeur appropriée si autorisé

[Actions owner]
```

Ne pas déduire authority depuis TeamMembership.

---

# 86. N2 — CRM contact

Candidate :

```text
← Clients

Marie Kalala
Client

Relation CRM
source / contexte si utile

Interactions récentes
seulement si owner et permission

[Ouvrir dans Clients]
```

Le Profile lié peut être une action secondaire.

---

# 87. N2 — Group

Candidate :

```text
← Groupes

Cohorte 2027
Groupe

Description
Politique d’adhésion
Discoverability si utile

Membres
selon authority

[Ouvrir le groupe]
```

---

# 88. N2 — Audience

Candidate :

```text
← Publics

Parents · Programme secondaire
Audience

Origine
Groupe Parents 2026

Membres
selon authority

[Ouvrir l’audience]
```

Pas d’analytics de performance ici.

---

# 89. N2 — Partner

Candidate :

```text
← Partenaires

Centre médical X
Partenaire · Entreprise

État
Actif

Profil lié
si disponible et légitime

[Ouvrir le partenariat]
```

Les finances Partner restent en profondeur si authority.

---

# 90. Profile projection depuis N2

Si un Profile est lié :

```text
Voir le profil
```

peut être disponible selon privacy.

Mais :

```text
relation
→ Profile
```

n’implique pas que le Profile donne accès à ses données privées.

---

# 91. N3 — owner management

N3 peut exposer les outils propres au domaine :

```text
Team management
Group membership
CRM interaction
Audience membership
Partner finance
Mandate / Permission
```

seulement si authority.

---

# 92. Relation ≠ authority

Aucune relation présentée dans cette surface ne transfère implicitement :

- Permission ;
- Mandate ;
- Access ;
- Payment ;
- données privées ;
- visibilité d’une Activity.

---

# 93. Composition relationnelle ≠ fusion

La surface peut présenter plusieurs owners dans une même expérience.

Elle ne crée pas un lifecycle relationnel universel.

---

# 94. Pas de `RelationshipStatus` universel

Les états :

```text
active
invited
paused
archived
suspended
```

n’ont pas la même sémantique selon Team, Group, Audience ou Partner.

La Presentation doit les contextualiser.

---

# 95. Pas de statut couleur universel

Un Partner `paused` et un GroupMembership `suspended` ne sont pas « orange = attention » par défaut.

Le sens vient du domaine.

---

# 96. Relation et Maintenant

Une relation peut produire une Situation Now si une conséquence actuelle le justifie.

Exemple :

```text
Invitation Team expirant aujourd’hui
```

ou :

```text
validation partenaire nécessaire
```

si les owners définissent cette conséquence.

La surface relationnelle conserve la relation durable.

---

# 97. Relation et Métier

Une relation peut être utile à une Activity :

```text
Programme
→ Groupe

Prestation
→ Client

Initiative
→ Partenaire
```

Le Métier compose le lien contextuel.

Personnes & relations conserve la relation transverse du Space lorsqu’elle existe vraiment.

---

# 98. Relation et Découvrir

Découvrir peut faire émerger une possibilité de relation :

- partenaire potentiel ;
- lieu / acteur ;
- communauté ;
- autre possibilité.

Mais :

```text
possibilité
≠ relation établie
```

---

# 99. Relation et Makolo Mark

Le Mark peut recevoir :

```text
« retrouve Marie dans nos contacts »
« ajoute Jean comme partenaire »
« ouvre le groupe Alumni »
```

Il doit handoff vers les owners et respecter authority.

---

# 100. Relation et Nous

Nous peut présenter :

```text
Relations
Partenaires et contacts utiles
[Ouvrir]
```

Personnes & relations approfondit.

---

# 101. Relation et Piloter

Piloter peut analyser :

- évolution d’un portefeuille relationnel ;
- conversion ;
- activité CRM ;
- audience ;
- partenaires ;
- groupes ;

si les domaines Analytics le permettent.

Personnes & relations ne devient pas dashboard.

---

# 102. Privacy — principe

La surface applique la divulgation minimale.

Le fait qu’une relation existe n’autorise pas l’exposition de toutes les données de la personne.

---

# 103. Email et téléphone

Email et téléphone ne sont pas des métadonnées N1 par défaut.

Ils apparaissent uniquement :

- si utiles ;
- si owner-backed ;
- si autorisés ;
- dans une profondeur adaptée.

---

# 104. Notes CRM

Les notes CRM privées ne doivent jamais être projetées dans une card relationnelle générique sans contrat explicite.

---

# 105. Partner notes

Même règle pour les notes Partner.

---

# 106. Group external reference

Les références externes de membership sont techniques/sensibles et restent owner depth.

---

# 107. Public projection

Une relation interne du Space n’est pas automatiquement publique.

```text
Team member
Partner
Audience
CRM contact
Group member
```

ne devient pas public par défaut.

---

# 108. Search et privacy

La recherche doit être permission-first.

Ne jamais :

1. rechercher globalement ;
2. recevoir des résultats ;
3. masquer après coup.

La source doit déjà être bornée.

---

# 109. IDOR

Toute profondeur reçoit des identifiants owner.

Le serveur doit vérifier :

- Space actif ;
- relation au Space ;
- Permission ;
- portée ;
- owner.

Un UUID connu ne suffit jamais.

---

# 110. Loading

Avec snapshot :

```text
relations connues
+
refresh discret
```

Sans snapshot :

```text
structure de surface
+
loading minimal
```

Pas de flash de toutes les cards.

---

# 111. Refresh

Refresh doit préserver :

- query ;
- section ;
- scroll ;
- sélection ;
- Actor Context.

---

# 112. Offline

Offline peut montrer des relations déjà synchronisées si leur conservation locale est autorisée.

Mais :

```text
cache local
≠ authority actuelle
```

Les mutations sensibles revalident à distance.

---

# 113. Freshness

La surface relationnelle peut utiliser une politique SWR/contextual.

La fraîcheur de :

- nom d’un groupe ;
- membership ;
- Partner status ;
- authority ;

n’a pas la même criticité.

Le client ne doit pas avoir un seul badge stale anxiogène.

---

# 114. Permission loss

Si l’autorité est retirée pendant que la surface est ouverte :

- retirer les sections devenues privées ;
- fermer une profondeur sensible ;
- retirer actions ;
- conserver seulement ce qui reste légitime ;
- expliquer la limite.

---

# 115. Partial failure

Une source peut échouer sans casser les autres.

Exemple :

```text
Clients ✓
Groupes ✓

Partenaires
Impossible d’actualiser.
[Réessayer]
```

La défaillance reste locale.

---

# 116. Owner unavailable

Si une section preview existe mais son owner depth est momentanément indisponible :

```text
relation visible
+
profondeur indisponible
```

ne doit pas devenir :

```text
relation supprimée
```

---

# 117. Mutations offline

Par défaut, les mutations de relation multi-acteur sont prudentes :

```text
Team invite
Group membership
Partner invite
CRM shared mutation
Audience membership
```

peuvent être préparées localement si contrat précis, mais leur résultat final n’est pas confirmé sans serveur.

---

# 118. No blind retry

Sans idempotence owner démontrée :

- pas de double invitation ;
- pas de double création Partner ;
- pas de double CRMContact ;
- pas de double membership.

---

# 119. Compact — racine

Single pane.

Structure candidate :

```text
← Nous
Clients & relations

[Rechercher]

Clients
Marie Kalala
Client                         ›
...
Voir les clients

Partenaires
Centre médical X
Partenaire                     ›
...
```

---

# 120. Compact — priorité

```text
SURFACE LABEL           P2
SEARCH                  P1/P2
SECTION TITLE           P2
RELATION IDENTITY       P1/P2
RELATION TYPE           P1
ACTION                  P1
```

Aucune relation individuelle ne doit devenir P3 sans contexte particulier.

---

# 121. Compact — section depth

Taper `Voir les clients` ouvre une collection owner ou une collection Presentation dédiée.

Le bottom nav Space peut rester visible tant qu’aucune profondeur immersive ne l’exige.

---

# 122. Medium

Medium peut utiliser :

```text
collection
+
preview relationnel
```

après sélection.

La racine peut rester single-column si cela améliore la lecture.

---

# 123. Wide — root

Wide peut utiliser :

```text
NAV | RELATION FIELD
```

avec largeur bornée.

Une grille de sections en deux colonnes est possible uniquement si chaque section reste lisible et non dashboard-like.

---

# 124. Wide — search

Après recherche ou sélection :

```text
NAV | RESULTS | RELATION FOCUS
```

Candidate :

```text
results  320–380 dp
focus    520–640 dp
gutter    24 dp
```

---

# 125. Very Wide

Interdits :

- cinq colonnes Team/CRM/Groups/Audience/Partners en parallèle ;
- matrice de permissions ;
- analytics ;
- activité timeline ;
- dashboard de compteurs.

Le surplus d’espace sert au focus.

---

# 126. Adaptive conservation

Lors de resize/rotation, conserver :

- surface ;
- query ;
- section ;
- résultat sélectionné ;
- relation owner ;
- scroll ;
- Actor Context ;
- profondeur.

---

# 127. Back

Depuis une relation N2 :

```text
Back
→ résultats ou section précédente
```

avec query et scroll préservés.

---

# 128. Deep links

Un deep link relationnel doit restaurer :

```text
Space
+
relation owner
+
authority
```

Il ne doit pas ouvrir un contact d’un autre Space.

---

# 129. Resume

Après reprise :

1. restaurer snapshot sûr ;
2. restaurer query/sélection ;
3. revalider authority ;
4. refresh ;
5. retirer les relations non légitimes.

---

# 130. Avatar et médias

Les avatars peuvent aider à reconnaître un Profile.

Ils restent secondaires.

Une relation sans avatar ne doit pas sembler incomplète.

---

# 131. No Orphan Media

Aucune photo de partenaire, groupe ou personne ne doit être utilisée comme décoration sans contexte ou autorisation.

---

# 132. Accessibility

MUST :

- textScale 1.6 ;
- focus keyboard ;
- ordre de lecture logique ;
- type de relation annoncé ;
- pas de distinction seulement par couleur ;
- targets tactiles suffisantes ;
- actions icon-only avec labels ;
- Reduce Motion ;
- ne pas annoncer des données privées inutilement.

---

# 133. Couleurs

Palette Makolo :

```text
#5232DB
#2B176E
#FF704D
#FAF7F5
#0F172A
```

Le type de relation ne doit pas dépendre d’un code couleur difficile à apprendre.

Le texte humain reste primaire.

---

# 134. Motion

Motion légère pour :

- ouverture N2 ;
- filtre ;
- apparition de résultat ;
- confirmation owner.

Pas de motion sociale ou décorative.

---

# 135. Recognition test

En ~500 ms, la personne doit reconnaître :

```text
où ?
→ dans ce Space

quel mode ?
→ relations

quel sens ?
→ avec qui nous avançons
```

---

# 136. Blur test

Texte flouté :

- sections perceptibles ;
- recherche secondaire ;
- pas de KPI ;
- focus relationnel clair.

---

# 137. Deletion test

Pour chaque donnée affichée :

> Si je la supprime, perd-on la compréhension de la relation ou une action légitime ?

Sinon, elle n’a probablement pas besoin d’être N1.

---

# 138. Competition test

Pas de cinq CTA concurrents.

Une section peut avoir une action secondaire.

Une relation sélectionnée peut avoir un CTA owner principal en profondeur.

---

# 139. Golden G-REL-01 — Generic / Compact

```text
Fondation Upendo
Personnes & relations

[Rechercher]

Équipe
Marie Kalala
Collaboratrice · Équipe

Groupes
Bénévoles terrain
Groupe

Contacts
Jean M.
Contact

Partenaires
Centre X
Partenaire
```

---

# 140. Golden G-REL-02 — Commerce / Compact

Titre :

```text
Clients & relations
```

Dominant : contacts/clients.

Orders/Payments absents de cette racine.

---

# 141. Golden G-REL-03 — Education / Compact

Titre :

```text
Groupes, personnes & partenaires
```

Groupes/cohortes visibles avant contacts si réels.

Inscriptions restent dans Programmes.

---

# 142. Golden G-REL-04 — Creative / Compact

Titre :

```text
Publics & partenaires
```

Audiences et Partners possibles.

Aucun follower count, feed ou popularité.

---

# 143. Golden G-REL-05 — Same Profile, two relations

Recherche :

```text
Marie
```

Résultats :

```text
Marie Kalala
Collaboratrice · Équipe

Marie Kalala
Contact · Client
```

Le Golden échoue si l’UI fusionne en :

```text
Marie Kalala
Collaboratrice / Client / Partner / ...
```

sans distinguer les owners.

---

# 144. Golden G-REL-06 — Activity-limited

```text
Relations globales indisponibles dans cette responsabilité.
```

Pas de sections privées.

Pas de hint sur leur nombre.

---

# 145. Golden G-REL-07 — Hidden vs empty

Fixture A : section `partners` absente par permission.

Fixture B : section `partners` visible et vide.

Les deux états doivent être différents.

---

# 146. Golden G-REL-08 — Contact without Profile

```text
Acme Consulting
Contact
```

Aucune erreur « profil absent ».

---

# 147. Golden G-REL-09 — Relation N2

```text
Marie Kalala
Client

Relation CRM
...
```

Le Profile est secondaire.

---

# 148. Golden G-REL-10 — Wide Search

```text
NAV | RESULTS | FOCUS
```

Après sélection seulement.

Pas de dashboard à la racine.

---

# 149. Golden G-REL-11 — Offline

Recherche locale bornée au snapshot.

Message de portée explicite.

Aucune conclusion globale `not found`.

---

# 150. Golden G-REL-12 — Permission loss

Relation ouverte.

Permission retirée.

N2 sensible disparaît ou se referme.

Aucune donnée privée conservée visuellement.

---

# 151. Golden G-REL-13 — textScale 1.6

Le type de relation reste visible.

Pas de truncation qui transforme :

```text
Contact CRM · Client
```

en information ambiguë.

---

# 152. Viewports de référence

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

---

# 153. États critiques

```text
content
sparse
empty-visible-section
no-visible-section
authority-limited
loading
refreshing
offline
stale
partial
search-results
search-no-match
permission-loss
owner-unavailable
```

---

# 154. Runtime actuel — projection

Le runtime courant possède :

```text
organizations/api/space_relationships_projection.py
```

et une projection `space.relationships` consommable par le client Flutter.

Les sections actuelles sont :

```text
team
groups
crm_contacts
audiences
partners
```

selon authority.

---

# 155. Runtime actuel — label archétypal

Le code courant possède déjà `SPACE_RELATIONSHIP_LABELS` avec les huit libellés définis par le contrat source.

Il ne faut pas recréer cette table côté clients.

---

# 156. Runtime actuel — preview

Chaque section serveur est actuellement bornée à un preview avec `has_more`.

C’est une bonne base N1.

La recherche complète et les collections profondes doivent continuer à s’appuyer sur owners, pas sur le preview.

---

# 157. Runtime actuel — Web

Le Web actuel possède déjà :

```text
/space/.../relationships/
```

avec :

- retour vers Nous ;
- question `Avec qui avançons-nous ?` ;
- sections séparées ;
- owner deep links ;
- distinction authority-limited ;
- distinction section masquée / collection vide.

Ce contrat conserve ces bonnes décisions mais précise la cible mature.

---

# 158. Runtime actuel — Flutter

Le repository Flutter sait déjà :

```text
watchRelationships
refreshRelationships
space.relationships
```

Le runtime inspecté ne démontre pas encore une surface Flutter relationnelle complète au même niveau que le Web.

Le contrat sert donc de cible de convergence.

---

# 159. Runtime actuel — authority

La projection actuelle est plus stricte que de simples liens UI :

- authority Space directe ;
- permissions owner ;
- capabilities de gestion séparées.

Le client ne doit pas relâcher ces frontières.

---

# 160. Runtime actuel — open PR / collision

Au moment de la consolidation :

```text
main = 52eced16a35d779f98eb8d43bbea405fd7f7b4b0
open PRs = aucune
```

Le dernier merge ferme Jour J / Live Space et ne justifie pas de redessiner cette surface relationnelle.

---

# 161. Gap — recherche transverse

Le document source demande explicitement une recherche pouvant réunir plusieurs sources en indiquant la relation réelle.

La projection N1 actuelle fournit des previews séparés.

La cible mature doit donc ajouter une stratégie de recherche relationnelle owner-backed ou une projection dédiée, sans table universelle.

Le nom d’endpoint exact reste ouvert.

---

# 162. Gap — N2 relationnel

Le Web actuel deep-linke vers les consoles owners.

La cible peut ajouter une profondeur Presentation plus humaine avant le handoff owner, si cela réduit la rupture cognitive.

Cette profondeur ne doit pas dupliquer les données.

---

# 163. Gap — Flutter

La couche local-first sait déjà conserver la projection.

Il reste à construire la vraie expérience :

- racine ;
- recherche ;
- section depth ;
- relation N2 ;
- permission loss ;
- offline ;
- adaptive.

---

# 164. Gap — responsabilités

La route Web conserve le filtre de responsabilité au niveau shell, mais la projection relations actuelle est globalement space-level et strictement limitée si authority n’est pas Space directe.

Le contrat ne demande pas d’élargir arbitrairement cette projection.

---

# 165. Target projection — principes

Une projection cible peut exposer :

```text
label
space
actor_context
authority
sections
capabilities
links
freshness
```

et, pour la recherche :

```text
query
results[]
relation kind
owner identity
human label
profile reference optional
owner link
```

Le format wire exact reste à déterminer au moment de l’implémentation.

---

# 166. Target result contract

Chaque résultat transverse doit permettre de répondre à :

```text
Qui / quoi ?
Quelle relation ?
Quel owner ?
Puis-je l’ouvrir ?
Puis-je agir ?
```

Sans obliger le client à deviner.

---

# 167. Owner links

Les owner links sont préférables à une duplication de logique client.

Le client ne construit pas des URLs en devinant la structure d’un domaine.

---

# 168. No new migration by default

Ce contrat ne justifie à lui seul aucune migration.

Avant toute table ou état persistant nouveau, vérifier si le besoin peut être porté par :

- projection ;
- selector ;
- index de recherche ;
- owner existant ;
- Presentation.

---

# 169. Critères de sortie serveur

Une implémentation mature doit démontrer :

- permission-first ;
- sections owners distinctes ;
- hidden ≠ empty ;
- Activity-limited borné ;
- recherche transverse bornée par authority ;
- provenance de relation ;
- Profile optionnel ;
- aucune fusion par nom/email locale ;
- owner links ;
- capabilities séparées ;
- IDOR couvert ;
- pagination / `has_more` correcte ;
- pas de nouveau modèle universel inutile.

---

# 170. Critères de sortie Web

Conforme si :

- titre archétypal ;
- question claire ;
- sections pertinentes seulement ;
- type de relation visible ;
- recherche transverse ;
- une personne peut apparaître plusieurs fois ;
- hidden ≠ empty ;
- authority limitée respectée ;
- owner handoff ;
- back conserve query/scroll ;
- Wide ne devient pas dashboard.

---

# 171. Critères de sortie Flutter

Conforme si :

- projection local-first consommée ;
- Compact complet ;
- recherche bornée ;
- offline honnête ;
- no-match local ≠ no-match global ;
- permission loss retire les données ;
- N2 relationnel ;
- adaptive conservation ;
- textScale 1.6 ;
- deep link owner-safe ;
- aucune mutation sensible confirmée offline.

---

# 172. Tests ciblés

```text
relationships generic label
relationships creative label
relationships media label
relationships education label
relationships commerce label
relationships service_provider label
relationships transport label
relationships community label
team section permission
team membership != mandate
groups view vs manage
crm view vs manage
partners permission
activity-limited sees no global relations
hidden section != empty section
same profile multiple relations
contact without profile
partner with profile
search cross-owner
search no match
search offline scope
owner deep link
relation N2
permission revoked during N2
partial source failure
refresh preserves query
back preserves scroll
compact
medium
wide
textScale 1.6
```

---

# 173. Anti-features

`Personnes & relations` ne devient jamais :

- CRM universel ;
- annuaire global Makolo ;
- fichier client universel ;
- People database ;
- social graph ;
- follower dashboard ;
- leaderboard ;
- profile browser ;
- Team admin comme racine ;
- permissions matrix ;
- Group manager universel ;
- Audience analytics ;
- Partner finance dashboard ;
- inbox ;
- feed ;
- timeline de toutes les interactions ;
- système où chaque participant devient contact ;
- système où chaque contact devient Profile ;
- système où chaque Profile lié est fusionné entre owners ;
- nouveau système d’autorité ;
- nouvelle vérité relationnelle persistante.

---

# 174. Invariants gelés

1. La question est `Avec qui avançons-nous ?`.
2. La surface est majeure mais secondaire.
3. Elle n’est pas un onglet primaire permanent.
4. Nous résume ; Personnes & relations approfondit.
5. `CRMContact != TeamMember != GroupMember != Partner != Mandate holder != follower != participant`.
6. La même personne peut apparaître dans plusieurs relations.
7. Les relations ne sont jamais fusionnées par simple identité visuelle.
8. Profile et relation restent distincts.
9. Une relation peut exister sans Profile lié.
10. Pas de modèle `UniversalPerson`.
11. Pas de modèle `UniversalRelationship`.
12. Le titre dépend de l’archétype.
13. Le vocabulaire archétypal reste Presentation.
14. Les sections absentes disparaissent.
15. Masqué par permission ≠ vide.
16. Preview ≠ collection complète.
17. `has_more` ≠ count total.
18. Search transverse ≠ recherche dans previews.
19. Search transverse respecte la relation owner.
20. No match ≠ personne inexistante.
21. Pas de bouton générique `Nouvelle personne`.
22. Les créations sont owner-specific.
23. TeamMembership ≠ Mandate.
24. GroupMembership ≠ Mandate.
25. CRMContact ≠ participant.
26. Audience ≠ Group.
27. Audience ≠ popularity.
28. Partner ≠ authority.
29. Follower ≠ CRMContact.
30. Relation ≠ transfert de données privées.
31. Relation ≠ Permission.
32. Relation ≠ Access.
33. N1 garde une densité moyenne.
34. N2 explique une relation.
35. N3 délègue au propriétaire.
36. Activity-limited ne reçoit pas les relations privées globales du Space.
37. Search est permission-first.
38. Deep link est permission-first.
39. Local cache ≠ authority.
40. Permission loss retire les données devenues illégitimes.
41. Les erreurs se dégradent localement d’abord.
42. Offline search signale sa portée.
43. Responsive adapte la géométrie, pas la vérité.
44. Wide ne devient pas dashboard.
45. Aucun nouveau modèle persistant n’est requis par ce contrat.

---

# 175. Références de cadrage

Ce contrat consolide principalement :

- `docs/architecture/makolo-domain-blueprint.md`
- `docs/architecture/profile-relevance-action-network.md`
- `docs/architecture/mature-experience-principles.md`
- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_Mobile_Visual_Charter_v1.1.md`
- `Makolo_UI_Engineering_Standards_v1.md`
- les contrats consolidés `Nous` et Space Métier
- les contrats local-first / sync mobile
- `organizations/api/space_relationships_projection.py`
- `organizations/space_product.py`
- `organizations/space_web_views.py`
- `templates/organizations/space/relationships.html`
- `mobile/lib/features/space/space_repository.dart`
- `organizations/models.py`
- `groups/models.py`
- `crm/models.py`
- `crm/canonical_models.py`
- `partners/models.py`

Le code, les migrations, les tests et les owners canoniques du `main` courant restent prioritaires lors de l’implémentation.

---

# 176. Formulation finale

> **Personnes & relations est la surface Space qui répond à « Avec qui avançons-nous ? ». Elle rassemble dans une même expérience les relations réellement utiles du collectif — équipe, groupes, clients ou contacts, publics, audiences, partenaires et autres relations owner-backed — sans jamais les fusionner. Une même personne peut donc apparaître plusieurs fois lorsque plusieurs relations légitimes la relient au Space. La surface adapte son vocabulaire à l’archétype, mais ne crée aucun nouveau Profile, aucune Person universelle et aucun Relationship générique. Sa recherche transverse préserve le type et la provenance de chaque relation ; ses sections disparaissent lorsqu’elles ne sont pas pertinentes ou autorisées ; une section masquée n’est jamais présentée comme vide ; et un Viewer Activity-limited n’acquiert jamais une vue globale des relations privées du Space. N1 donne le champ relationnel, N2 explique une relation, N3 délègue au propriétaire. Team, Groups, CRM, Audiences, Partners et Authorization conservent leurs vérités, leurs permissions et leurs mutations. La surface reste de densité moyenne, local-first lorsque sûr, adaptive sans devenir dashboard, et strictement orientée vers la compréhension des liens qui permettent au Space d’avancer réellement.**