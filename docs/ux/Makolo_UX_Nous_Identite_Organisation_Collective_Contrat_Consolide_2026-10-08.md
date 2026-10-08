# Makolo — **Nous**
## Contrat UX consolidé — identité et organisation collective

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence — surface Space `Nous`  
**Actor Context :** Space  
**Viewer :** Profile authentifié agissant explicitement dans ce Space  
**Portée :** Web, Flutter, tablette/desktop adaptatif, Presentation, projections serveur, local-first  
**Base runtime vérifiée :** `main@788a744102e124feddbe0e17b30b8ede40fb2ebe`  
**Nature :** contrat UX et de projection ; ne crée aucun nouveau domaine métier  
**Promesse produit :** **Makolo marche pour vous.**  
**Principe d’expérience :** **Pas le plaisir de rester. Le plaisir d’avancer.**

---

# 0. Formule

```text
Nous
=
identité collective
+
organisation collective
+
relations compréhensibles
+
autorité lisible sans confusion
```

et non :

```text
Nous
=
Settings
+
admin
+
CRM
+
Team management
+
dashboard
```

---

# 1. Question humaine

La surface **Nous** répond à :

> **Qui sommes-nous, avec qui fonctionnons-nous et comment sommes-nous organisés ?**

Elle permet de comprendre :

```text
quelle identité collective est active
+
ce que ce Space est
+
avec qui il fonctionne
+
comment les personnes sont reliées
+
qui porte quelles responsabilités
+
où se trouvent les profondeurs d’autorité
+
quels faits de confiance comptent
```

Elle ne répond pas à :

> Qu’est-ce que nous faisons réellement ?

Cette question appartient à **Métier**.

Elle ne répond pas à :

> Qu’est-ce qui mérite notre attention maintenant ?

Cette question appartient à **Maintenant**.

---

# 2. Modèle mental

Le modèle mental est :

```text
Nous = identité + organisation collective
```

Nous est le miroir collectif de Moi :

```text
Moi
→ identité / capital personnel

Nous
→ identité / organisation collective
```

Le couple doit être compréhensible sans documentation.

---

# 3. Space canonique

Invariant :

```text
Space
= acteur collectif durable
```

Le Space peut représenter :

- entreprise ;
- institution ;
- association ;
- école ;
- collectif ;
- marque ;
- organisation publique ;
- autre entité collective légitime.

Il n’a pas de mot de passe.

Il n’est pas une seconde personne.

---

# 4. Viewer humain

Même dans Nous :

```text
Viewer = Profile
Actor Context = Space
```

L’Avatar reste la personne.

Le Space ne devient jamais l’Avatar.

---

# 5. Nous ≠ Avatar

L’Avatar gère notamment :

- identité authentifiée ;
- Actor Context ;
- `Agir comme` ;
- compte ;
- changement de compte ;
- déconnexion.

Nous ne doit pas absorber cette fonction.

---

# 6. Nous ≠ Settings

Invariant source :

> **Nous n’est pas Settings.**

La racine doit donner une lecture humaine du collectif avant toute profondeur administrative.

---

# 7. Nous ≠ console d’administration

La racine ne doit pas ressembler à :

```text
General
Members
Roles
Permissions
Billing
Integrations
Security
Danger Zone
```

même si certaines profondeurs institutionnelles existent.

---

# 8. Nous ≠ Métier

```text
Métier
→ ce que nous faisons

Nous
→ qui nous sommes et comment nous fonctionnons
```

Un Programme, une Commande ou un Départ n’a pas vocation à dominer Nous.

---

# 9. Nous ≠ Personnes & relations

`Personnes & relations` est une profondeur majeure secondaire.

Elle répond :

> **Avec qui avançons-nous ?**

Nous peut offrir une entrée vers cette surface.

Il ne doit pas absorber toutes les listes CRM, Groups, Audiences, Partners.

---

# 10. Nous ≠ Piloter

Piloter répond :

> **Est-ce que cela fonctionne ? Qu’est-ce qui change ? Que devons-nous ajuster ?**

Nous peut fournir une entrée vers Piloter.

Il ne devient pas dashboard analytique.

---

# 11. N1 — structure générale

La racine candidate :

```text
NOUS
│
├── IDENTITY
│
├── ÉQUIPE
│
├── RESPONSABILITÉS
│
├── RELATIONS
│
├── CONFIANCE
│
├── ORGANISATION / CONTEXTE ?
│
└── DEPTH
    ├── Personnes & relations
    ├── Team
    ├── Responsibility
    ├── Authority / Mandate
    ├── Ownership
    ├── Trust
    ├── Piloter
    └── Paramètres institutionnels
```

La racine reste humaine.

---

# 12. Identité collective N1

Peut présenter selon projection :

- nom ;
- description ;
- archétype ;
- mission si pertinente ;
- localisation générale ;
- présence publique ;
- état/lifecycle si utile humainement ;
- vérification contextualisée.

Les détails de contact sensibles ou administratifs restent permission-first.

---

# 13. Exemple N1

```text
Nous

Mulykap
Transport de voyageurs

Équipe
12 personnes

Responsabilités
4 domaines actifs

Relations
Partenaires et contacts utiles

Confiance
Identité vérifiée
```

C’est une composition conceptuelle.

Les sections absentes disparaissent.

---

# 14. Hiérarchie perceptive

Candidate :

```text
SPACE IDENTITY                  P2
SECTION TITLE                   P2
ORGANIZATION FACT               P1/P2
RELATION SUMMARY                P1/P2
INSTITUTIONAL ACTION            P1
ADMIN DETAIL                    P0/P1
```

Une alerte de gouvernance réellement importante peut monter en priorité, mais la racine ne devient pas Now.

---

# 15. Densité

Référence source :

```text
Nous = densité moyenne
```

Professionnel ne signifie pas afficher toutes les permissions et tous les collaborateurs simultanément.

---

# 16. Identité collective ≠ branding seul

Nous ne doit pas être seulement :

```text
logo
cover
description
```

L’identité collective comprend aussi sa structure organisationnelle réelle.

---

# 17. Identité publique

La présence publique du Space est une projection.

Nous peut permettre de l’ouvrir ou de la gérer selon authority.

Mais la projection publique ne révèle pas :

- équipe privée ;
- Mandates ;
- Permissions ;
- contacts privés ;
- notes CRM ;
- paramètres institutionnels ;
- abonnement.

---

# 18. Archétype

L’archétype peut être visible humainement :

```text
Transport de voyageurs
Enseignement / formation
Média / journalisme
```

Il est un centre de gravité Presentation.

Il n’accorde aucune Permission.

---

# 19. Operational Footprint

Le footprint est un read model dérivé.

Il peut aider la Presentation.

Il ne doit pas être affiché comme liste technique :

```text
transport
payments
crm
analytics
```

à la racine.

---

# 20. Équipe

Nous peut donner accès à Team et aux collaborateurs.

Invariant :

```text
TeamMembership
≠ authority
```

La vue humaine peut dire :

```text
Marie travaille avec nous.
```

sans prétendre :

```text
Marie peut tout administrer.
```

---

# 21. Team count

Un nombre de membres peut être affiché si la projection l’autorise.

Il ne doit pas devenir une métrique de performance.

---

# 22. Team N2

N2 peut présenter :

- équipe ;
- membres autorisés à voir ;
- état de collaboration ;
- invitation si owner le permet ;
- lien vers gestion.

La profondeur ne doit pas inventer Mandate depuis Membership.

---

# 23. Responsabilité

```text
Assignment / responsabilité
= ce que quelqu’un porte
```

Nous doit aider à comprendre :

```text
qui porte quoi
```

sans confondre cette réponse avec :

```text
qui peut juridiquement / techniquement agir
```

---

# 24. Authority

```text
Mandate / Permission
= autorité
```

Les détails peuvent être dans une profondeur spécialisée.

---

# 25. Responsibility ≠ authority

Invariant essentiel :

```text
responsabilité
≠ autorité
```

Un filtre de responsabilité n’augmente jamais le périmètre autorisé.

---

# 26. Ownership

Ownership est une vérité d’autorité et de gouvernance.

Il peut être visible uniquement aux personnes légitimes.

La racine peut éventuellement montrer une formulation humaine :

```text
Propriété et gouvernance
```

mais pas une liste brute de Mandates.

---

# 27. Activity-limited viewer

Un Viewer peut agir pour un Space uniquement sur certaines Activities.

Dans ce cas :

```text
Actor Context = Space
authority scope = Activity-limited
```

Nous doit appliquer divulgation minimale.

Il ne doit pas révéler toute l’équipe, ownership ou configuration du Space.

---

# 28. Direct Space authority

Certaines profondeurs — gestion Team, ownership, contacts institutionnels — exigent une authority Space explicite.

Le client ne doit pas déduire ce droit parce que le Space apparaît dans le switcher.

---

# 29. Relation au switcher

```text
Agir comme
→ change Actor Context
```

Nous :

```text
→ décrit le collectif actif
```

Ces mécanismes sont liés mais distincts.

---

# 30. Relations

Nous peut résumer :

```text
partenaires
groupes
contacts
clients
publics
audiences
autres relations réelles
```

selon le Space.

La profondeur spécialisée est **Personnes & relations**.

---

# 31. Relations ne fusionnent pas les types

Invariant :

```text
CRMContact
!= TeamMember
!= GroupMember
!= Partner
!= Mandate holder
!= follower
!= participant
```

La même personne peut avoir plusieurs relations.

La Presentation doit les nommer.

---

# 32. Vocabulaire relationnel par archétype

La profondeur peut utiliser :

```text
generic            → Personnes & relations
creative           → Publics & partenaires
media              → Publics & partenaires
education          → Groupes, personnes & partenaires
commerce           → Clients & relations
service_provider   → Clients & partenaires
transport_operator → Relations
community          → Communauté & partenaires
```

Ces mots sont UX.

Ils ne créent pas de nouveaux modèles Profile.

---

# 33. Groupes

GroupMembership n’accorde pas authority.

Nous peut montrer qu’un collectif possède des groupes.

Les groupes restent leurs propriétaires.

---

# 34. CRM

Nous ne devient jamais CRM.

Il peut résumer l’existence de relations clients/contacts puis handoff.

---

# 35. Publics et audiences

Publics/Audiences peuvent être importants selon archétype.

Ils restent principalement des relations ou segments.

Ils ne deviennent pas un indicateur de popularité.

---

# 36. Partners

Partners restent relations.

Associer un partenaire ne transfère jamais :

- Permission ;
- Mandate ;
- Access ;
- visibilité privée.

---

# 37. Trust et vérification

Nous peut présenter des faits Trust utiles.

Exemple :

```text
Identité du Space vérifiée
```

si la portée de la vérification est claire.

---

# 38. Pas de score global de confiance

Interdit :

```text
Trust Score 87/100
```

comme synthèse globale si le domaine ne le possède pas.

Une vérification ne garantit pas la qualité globale des produits/services.

---

# 39. Paramètres institutionnels

Selon authority, les profondeurs peuvent contenir :

- présence publique ;
- archétype ;
- Team ;
- responsabilités ;
- ownership ;
- Trust ;
- Subscription ;
- Entitlements ;
- connexions ;
- archivage / restauration ;
- paramètres du Space.

Ces éléments ne doivent pas dominer N1.

---

# 40. Subscription

L’abonnement du Space reste distinct de l’abonnement personnel du Viewer.

Nous peut handoff vers la profondeur institutionnelle appropriée.

---

# 41. Entitlements

Entitlement détermine des capacités contractuelles.

Il ne doit pas être confondu avec Permission.

```text
Entitlement
≠ authority personnelle
```

---

# 42. Piloter

Nous peut offrir une entrée vers Piloter si le Viewer a le droit et si la capacité existe.

Piloter reste une surface autonome.

---

# 43. Maintenant

Une situation de gouvernance importante peut remonter dans Maintenant.

Exemple :

```text
Le mandat d’administration expire demain.
```

Nous conserve la structure.

Now porte l’attention.

---

# 44. Métier

Métier peut ouvrir un responsable, une équipe ou un partenaire.

Le retour vers Nous doit préserver le contexte.

---

# 45. N1 — actions

Actions N1 candidates :

```text
Voir l’équipe
Voir les responsabilités
Voir les relations
Voir la confiance
Piloter
```

uniquement si pertinentes et autorisées.

Pas de mur de boutons d’administration.

---

# 46. Modifier le Space

`Modifier` peut être disponible pour un Viewer autorisé.

Mais il ne doit pas devenir le CTA dominant permanent de Nous.

---

# 47. Search

La racine Nous n’a pas besoin d’une Search globale permanente.

La profondeur Personnes & relations peut offrir une recherche.

La Team peut avoir sa propre recherche si volume.

---

# 48. Search relationnelle

La recherche doit conserver le type réel de relation.

Exemple :

```text
Marie Kalala
Collaboratrice · Exploitation

Marie Kalala
Contact CRM · Client
```

Une même personne peut apparaître deux fois sous deux relations légitimes.

---

# 49. N2 — identité collective

Peut présenter :

- description ;
- contacts généraux autorisés ;
- localisation ;
- mission ;
- projection publique ;
- archétype ;
- lifecycle ;
- liens institutionnels.

Pas de données sensibles non nécessaires.

---

# 50. N2 — équipe

Peut présenter :

- membres ;
- TeamMembership ;
- états d’invitation si owner-backed ;
- actions de gestion si capability ;
- handoff vers Profile.

---

# 51. N2 — responsabilités

Peut présenter une structure humaine :

```text
Exploitation
Finance
Programme
Administration
```

avec qui porte quoi.

Les scopes techniques peuvent être masqués tant qu’ils ne sont pas nécessaires.

---

# 52. N3 — authority

N3 peut devenir précis :

```text
Mandate
Role
Permission
Scope
validity
```

lorsque la personne doit comprendre ou administrer l’autorité.

Cette précision n’a pas à polluer N1.

---

# 53. N2 — relations

La profondeur utilise le vocabulaire archétypal.

Elle compose sans fusionner :

- Team ;
- Groups ;
- CRM ;
- Audiences ;
- Partners.

---

# 54. N2 — Trust

Peut présenter :

- claims ;
- portée ;
- vérification ;
- provenance ;
- état.

Pas de badge marketing générique.

---

# 55. N3 — Settings

Settings est une profondeur institutionnelle.

Chemin :

```text
Nous
→ organisation / paramètres
→ settings
```

Pas :

```text
Nous = settings
```

---

# 56. Compact

Compact :

```text
single pane
identity first
sections verticales
depth par navigation
```

Candidate :

```text
Nous

Mulykap
Transport de voyageurs

Équipe
12 personnes                    ›

Responsabilités
Exploitation, Finance           ›

Relations
Partenaires et contacts         ›

Confiance
Identité vérifiée               ›
```

---

# 57. Medium

Medium peut permettre 1–2 territoires structurés.

Une sélection peut ouvrir un preview léger.

---

# 58. Wide

Wide peut utiliser :

```text
NAV | NOUS | FOCUS
```

après sélection.

La racine reste un portrait institutionnel structuré, pas un dashboard.

---

# 59. Very Wide

Interdits :

- grille KPI ;
- org chart géant par défaut ;
- permissions matrix à la racine ;
- CRM en panneau permanent ;
- analytics en panneau permanent ;
- réglages en sidebar permanente.

---

# 60. Adaptive conservation

Conserver :

- section ;
- sélection ;
- responsabilité active ;
- scroll ;
- profondeur ;
- recherche relationnelle ;
- brouillon de modification.

---

# 61. Back

N2 → Nous doit revenir à la même section et au même scroll.

---

# 62. Resume

À la reprise :

1. montrer projection locale sûre ;
2. revalider authority ;
3. retirer les profondeurs devenues interdites ;
4. conserver les données publiques/non sensibles encore légitimes ;
5. restaurer la section.

---

# 63. Local-first

Le client peut conserver selon privacy :

- identité collective déjà utile ;
- structure de sections ;
- relations déjà autorisées ;
- éléments de Team déjà autorisés ;
- données publiques ;
- préférences UX.

Le serveur reste autoritaire pour :

- Mandates ;
- Permissions ;
- ownership ;
- Team mutations ;
- Subscription ;
- Entitlements ;
- Trust updates ;
- données partagées sensibles.

---

# 64. Offline

Offline peut conserver la compréhension.

Il ne doit jamais afficher :

```text
vous pouvez administrer
```

uniquement depuis un ancien cache si l’action exige revalidation.

---

# 65. Stale authority

Si authority n’est pas fraîche :

- lecture non sensible peut rester ;
- actions sensibles sont revalidées ;
- données privées peuvent être masquées si nécessaire.

---

# 66. Partial failure

Exemple :

```text
Nous
✓ identité
✓ équipe

Relations
Impossible d’actualiser.
[Réessayer]

Confiance
✓ disponible
```

La surface reste utile.

---

# 67. Permission loss

Lorsqu’une authority est révoquée :

- retirer actions ;
- retirer données privées ;
- fermer N3 sensible ;
- conserver le contexte public/minimal ;
- expliquer humainement la limite.

---

# 68. Empty / Sparse

Nous possède normalement une identité Space.

Les autres sections peuvent être localement vides.

Exemple :

```text
Relations
Aucune relation visible dans votre périmètre.
```

Pas de faux Partner ou faux membre.

---

# 69. Calm state

Nous est naturellement calme.

Pas besoin de badges rouges pour chaque gouvernance possible.

---

# 70. Loading

Avec projection connue :

```text
contenu connu
+
refresh discret
```

Sans projection :

structure minimale sans inventer de données.

---

# 71. Accessibility

MUST :

- text scaling ;
- structure sémantique ;
- focus logique ;
- clavier desktop ;
- targets tactiles ;
- pas de statut uniquement par couleur ;
- Reduce Motion ;
- libellés d’autorité compréhensibles ;
- ne pas annoncer des données privées hors nécessité.

---

# 72. Media

Le logo ou identité visuelle du Space peut apparaître.

Mais le shell Makolo conserve sa propre marque.

```text
Space logo
≠ Makolo logo
```

---

# 73. Motion

Motion discrète.

Nous n’a pas besoin de mouvement décoratif.

---

# 74. No Orphan Content

Une mission, un document institutionnel, un logo ou une preuve doit avoir contexte et finalité.

Nous ne devient pas bibliothèque de contenu d’entreprise.

---

# 75. Anti-features

Nous ne doit pas devenir :

- Settings ;
- admin console ;
- ERP ;
- CRM ;
- org chart permanent ;
- permissions matrix N1 ;
- dashboard KPI ;
- analytics ;
- billing center ;
- social page ;
- feed ;
- leaderboard ;
- score de confiance ;
- score d’équipe ;
- annuaire universel ;
- liste de tous les modèles ;
- second système d’autorité ;
- second Team ;
- second Partner ;
- second Group ;
- container de tout le Space.

---

# 76. Invariants gelés

1. Nous = identité + organisation collective.
2. Actor Context = Space.
3. Viewer = Profile.
4. Space ≠ Profile.
5. Space n’a pas de mot de passe.
6. Avatar reste Profile.
7. Avatar ≠ Nous.
8. Nous ≠ Settings.
9. Nous ≠ admin console.
10. Nous ≠ Métier.
11. Nous ≠ Personnes & relations.
12. Nous ≠ Piloter.
13. TeamMembership ≠ Mandate.
14. GroupMembership ≠ Mandate.
15. Responsibility ≠ authority.
16. Assignment ≠ Permission.
17. Role n’accorde aucun droit sans Mandate.
18. Choisir un Space ≠ obtenir Permission.
19. Filtrer par responsabilité ≠ élargir authority.
20. Activity-limited authority reste limitée.
21. Ownership est owner-backed.
22. Relationships ne fusionnent pas les types.
23. CRMContact ≠ TeamMember ≠ Partner.
24. Trust ≠ score global.
25. Vérification ≠ garantie de qualité.
26. Entitlement ≠ Permission.
27. Subscription personnelle ≠ Subscription Space.
28. Personnes & relations reste profondeur.
29. Piloter reste profondeur.
30. Settings reste profondeur.
31. Presentation ne possède pas Team/CRM/Partner/Mandate.
32. Divulgation minimale.
33. Offline ne devient pas source d’autorité.
34. Le serveur revalide mutations sensibles.
35. Responsive adapte géométrie, pas vérité.

---

# 77. Runtime actuel — projection Nous

Le runtime actuel possède :

```text
organizations/api/space_us_projection.py
```

et compose :

```text
identity
team
responsibilities
ownership
trust
organization
authority
links
capabilities
```

C’est une base importante.

Le contrat UX ne doit pas demander un nouveau domaine `Us`.

---

# 78. Runtime actuel — authority

La projection actuelle distingue notamment :

```text
direct Space authority
vs
Activity-limited authority
```

La gestion Team et ownership exige une authority Space directe.

C’est cohérent avec le contrat.

---

# 79. Runtime actuel — identity disclosure

La projection actuelle expose davantage de contacts institutionnels seulement avec authority Space directe.

Le contrat conserve cette logique de divulgation minimale.

---

# 80. Runtime actuel — Team

La liste détaillée Team est conditionnée par `manage_team`.

Le contrat ne doit pas inventer de liste détaillée universelle.

---

# 81. Runtime actuel — Ownership

Ownership détaillé est conditionné par la capability appropriée.

La racine peut rester plus synthétique.

---

# 82. Runtime actuel — liens institutionnels

Le runtime sait déjà handoff vers :

- relationships ;
- team ;
- ownership ;
- trust ;
- settings ;
- pilot.

C’est exactement la bonne logique :

```text
Nous
→ porte humaine
→ propriétaires spécialisés
```

---

# 83. Relation au shell Space

Navigation primaire :

```text
Maintenant | Découvrir | [Mark] | Métier | Nous
```

Nous est donc le repère collectif stable, pas une destination secondaire de configuration.

---

# 84. Golden candidates

## G-NOUS-01 — Compact / Full

```text
Nous

Mulykap
Transport de voyageurs

Équipe
12 personnes

Responsabilités
Exploitation · Finance · Administration

Relations
Partenaires et contacts utiles

Confiance
Identité vérifiée
```

---

## G-NOUS-02 — Compact / Limited authority

Viewer Activity-limited.

Identité minimale.

Pas de Team privée.

Pas d’ownership.

Relations limitées au scope légitime.

---

## G-NOUS-03 — Compact / Sparse

Space récent.

Identité présente.

Équipe réduite.

Relations absentes localement.

Pas de faux contenu.

---

## G-NOUS-04 — Team N2

Test :

```text
membership
≠ authority
```

---

## G-NOUS-05 — Responsibility N2

Montre qui porte quoi.

Authority en profondeur seulement.

---

## G-NOUS-06 — Authority N3

Scope et Mandate précis.

Permission-first.

Pas de jargon en N1.

---

## G-NOUS-07 — Relationships

Vocabulaire adapté à l’archétype.

Relations distinctes.

---

## G-NOUS-08 — Trust

Portée de vérification claire.

Pas de score global.

---

## G-NOUS-09 — Wide

```text
NAV | NOUS | FOCUS
```

après sélection.

Pas de dashboard.

---

## G-NOUS-10 — Offline / permission revalidation

Lecture locale possible.

Mutation sensible bloquée/revalidée.

---

## G-NOUS-11 — textScale 1.6

Sections et identité restent lisibles.

---

# 85. Viewports Golden

Candidates :

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
full
sparse
offline
stale
partial
permission_loss
activity_limited
```

---

# 86. Tests ciblés

```text
space us full
space us sparse
space identity minimum disclosure
direct space authority
activity-limited authority
team detail hidden without capability
team membership != mandate
responsibility != authority
ownership capability
relationships handoff
relationship types distinct
trust no score
settings not root
pilot handoff
offline
permission revoked
compact / medium / wide
textScale 1.6
```

---

# 87. Critères de sortie serveur

Conforme si :

- aucune surface `Nous` ne possède ses propres vérités métier ;
- projection permission-first ;
- Activity-limited viewer borné ;
- Team details capability-gated ;
- ownership capability-gated ;
- Trust owner-backed ;
- identity private facts disclosure-gated ;
- handoffs explicites ;
- aucune Membership utilisée comme authority.

---

# 88. Critères de sortie Web

Conforme si :

- Nous est immédiatement reconnu comme portrait collectif ;
- Settings ne domine pas ;
- équipe et responsabilité sont distinctes ;
- relations sont humaines ;
- Trust contextualisé ;
- profondeurs owner-backed ;
- aucune fuite activity-limited ;
- back conserve contexte ;
- Wide ne devient pas dashboard.

---

# 89. Critères de sortie Flutter

Conforme si :

- Compact complet ;
- identité collective claire ;
- Avatar humain stable ;
- Space switcher distinct ;
- sections structurées ;
- local-first prudent ;
- authority revalidée ;
- deep links restaurent Space ;
- text scaling fonctionne ;
- split sur largeur seulement après sélection utile.

---

# 90. Points volontairement ouverts

Restent ouverts :

- microcopy finale des sections ;
- composant final identité Space ;
- place exacte de mission/description ;
- seuils Medium/Wide finaux ;
- représentation graphique éventuelle de l’organisation ;
- profondeur finale Responsibility vs Authority ;
- règles de preview Team pour viewers non managers ;
- microcopy de Trust ;
- architecture exacte des paramètres institutionnels ;
- détail de l’entrée Piloter.

Aucun de ces points ne justifie un nouveau domaine persistant.

---

# 91. Références de cadrage

Ce contrat dérive principalement de :

- `docs/architecture/makolo-domain-blueprint.md`
- `docs/architecture/profile-relevance-action-network.md`
- `docs/architecture/mature-experience-principles.md`
- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- les huit contrats Space Métier
- les contrats local-first/mobile/sync
- `organizations/api/space_us_projection.py`
- `organizations/space_web_views.py`
- `organizations/console_context.py`
- `organizations/models.py`

Le runtime courant gagne lors de l’implémentation.

---

# 92. Formulation finale

> **Nous est la surface Makolo qui rend compréhensible l’identité et l’organisation du Space actif. Elle répond à “qui sommes-nous, avec qui fonctionnons-nous et comment sommes-nous organisés ?” sans réduire le collectif à ses paramètres ni à une console d’administration. Elle compose identité collective, équipe, responsabilités, relations, ownership et Trust en conservant strictement les frontières entre Membership, Assignment, Mandate et Permission. La racine reste humaine et de densité moyenne ; les listes relationnelles, l’autorité détaillée, le pilotage et les paramètres institutionnels vivent en profondeur. Un Viewer Activity-limited ne reçoit jamais implicitement une vue Space-wide. Nous est le miroir collectif de Moi : non pas ce que nous faisons, mais la structure humaine et institutionnelle qui permet à l’action collective d’exister légitimement.**
