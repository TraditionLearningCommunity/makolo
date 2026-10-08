# Makolo — Space Métier `education` / **Programmes**
## Contrat UX consolidé — N1, N2/N3, hiérarchie, représentations, états, adaptive, local-first, API et handoffs

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence pour l’archétype Space `education`  
**Porte visible :** **Programmes**  
**Contexte acteur :** Space  
**Viewer :** Profile authentifié agissant explicitement au nom du Space  
**Portée :** Web, mobile Flutter, tablet/desktop adaptatif, Presentation, projections serveur et continuité locale  
**Nature :** contrat UX, de projection et d’implémentation ; ne crée aucun nouveau domaine métier  
**Promesse produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 0. Objet

Ce document fixe la manière dont la porte **Métier** doit être visible et utilisable pour un Space dont l’archétype est :

```text
education
```

Le libellé visible primaire est :

```text
Programmes
```

L’icône sémantique candidate fournie par l’architecture Space est :

```text
graduation-cap
```

Le document ne redéfinit pas les domaines qui portent la vérité.

Il ne crée pas :

- un modèle `Programme` universel si `Activity` porte déjà la réalité ;
- un modèle `Session` parallèle si `Occurrence` porte déjà la session ;
- un modèle `Admission` générique si une `Journey` d’inscription porte déjà la démarche ;
- un deuxième Requirement ;
- un deuxième Form ;
- un deuxième Resource ;
- un deuxième Group ;
- un deuxième Access ;
- un deuxième Capacity ;
- un deuxième Readiness ;
- un deuxième système d’autorité.

Il répond à la question :

> **Comment rendre le monde éducatif du Space immédiatement compréhensible et opérable dans Makolo, en faisant sentir qu’on conduit des Programmes et des Sessions réels plutôt qu’un assemblage de modules backend ?**

---

# 1. Sources de cadrage

Ce contrat est dérivé principalement des documents fournis dans le projet :

- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md` ;
- `space-ux-experience-specification.md` lorsque ses décisions sont reprises par les contrats consolidés ou démontrées par le runtime ;
- `Makolo_Architecture_Experience_Mobile_Consolidee.md` ;
- `Makolo_Mobile_Visual_Charter_v1.1.md` ;
- `Makolo_Application_Behavior_Interaction_System_v1.1.md` ;
- `Makolo_UI_Engineering_Standards_v1.md` ;
- `Makolo_Mobile_Sync_Continuity_Kernel.md` ;
- `Makolo_Local_First_Synchronization_Offline_Execution_Architecture.md` ;
- `mobile-local-data-kernel.md` ;
- `Makolo_UX_Now_Contrat_Consolide.md` ;
- `Makolo_UX_En_Cours_Contrat_Consolide.md` ;
- `Makolo_UX_Decouvrir_Contrat_Consolide.md` ;
- `Makolo_UX_Presentation_Golden_Specification_v1.md` ;
- le contrat Jour J / Makolo Live consolidé du projet ;
- le contrat Space Métier Transport consolidé ;
- le code, migrations et tests du dépôt `TraditionLearningCommunity/makolo`.

La vérité runtime vérifiée pendant la rédaction est :

```text
main@d5b85ee4c737f09da7d1b2e27f7bae9d14d40131
```

La PR pertinente vérifiée est :

```text
#496 — SPACE MÉTIER — continuité et structure sur main W2
état : open
```

Elle ne constitue pas encore la vérité de `main`.

Elle apporte cependant une direction cohérente avec ce contrat :

```text
structure métier
≠
continuité métier
```

et :

```text
ContinuityFacet
→ seulement lorsqu’un owner progressif réel le justifie
→ notamment Journey
```

---

# 2. Statuts utilisés

### GELÉ

Décision UX ou invariant fixé par les sources et retenu par ce contrat.

### CIBLE UX

Comportement visible que l’implémentation doit atteindre.

### RUNTIME OBSERVÉ

Comportement réellement démontré dans `main` au moment de la rédaction.

### PR EN COURS

Comportement présent dans une branche/PR ouverte mais non encore fusionnée.

### OUVERT

Décision volontairement non figée faute de nécessité ou de vérité runtime suffisante.

---

# 3. Place de Programmes dans le shell Space

Le shell Space reste :

```text
Maintenant | Découvrir | [Makolo Mark] | Programmes | Nous
```

`Programmes` occupe la quatrième porte, c’est-à-dire la place de la continuité / du travail durable du Space.

La question générale Métier reste :

> **Qu’est-ce que nous faisons réellement exister, préparer, exécuter et délivrer ?**

Pour l’archétype `education`, elle devient naturellement :

> **Quels Programmes faisons-nous réellement vivre, quelles Sessions préparons-nous ou conduisons-nous, et où en sont les inscriptions et conditions nécessaires ?**

Le mot visible est `Programmes`.

Le terme `Education`, `Activity`, `Journey`, `Requirement`, `Access` ou `Operational Footprint` n’est pas requis pour comprendre la porte.

---

# 4. Personnalité de la surface

Les personnalités Makolo existantes restent :

```text
Maintenant
→ conséquence + air

Découvrir
→ champ + représentation

En cours
→ continuité + état

Moi
→ structure + capital

Jour J
→ réalité courante + accomplissement

Makolo Mark
→ intention + orchestration
```

Pour Programmes, le présent contrat fixe :

```text
Programmes
→ structure pédagogique + continuité de session
```

Développé :

> **Programmes montre ce que l’organisation enseigne ou fait apprendre durablement, puis ce qui doit être préparé, traité ou conduit pour que ces Programmes deviennent des Sessions réelles et accomplissables.**

La surface doit être professionnelle sans ressembler à :

- un LMS générique ;
- un tableau d’administration scolaire ;
- un CRM étudiant ;
- un dashboard KPI ;
- un catalogue marketing ;
- une todo list ;
- un kanban d’admissions.

---

# 5. Invariant principal : Programme d’abord

La source Space donne la composition naturelle :

```text
Programme
  ├── Sessions
  ├── Inscriptions / demandes
  ├── Conditions
  ├── Formulaires
  ├── Ressources
  ├── Groupes / cohortes réels
  └── Accès
```

Le contrat visible fixe donc :

```text
Programme
= contexte humain dominant
```

et non :

```text
Programmes
→ 7 modules indépendants
```

Une personne doit avoir l’impression :

> **« Je gère le Programme Comptabilité et ses Sessions. »**

pas :

> **« Je navigue entre Journey, Forms, Requirements, Resources, Groups, Capacity et Access. »**

---

# 6. Programme visible ≠ nouveau modèle Programme

Le mot `Programme` est un **vocabulaire de Presentation pour cet archétype**.

Si le runtime porte aujourd’hui le programme par une `Activity`, l’UX ne doit pas créer un modèle parallèle uniquement pour obtenir ce mot.

Invariant :

```text
backend générique
+
langage visible contextuel
```

Donc :

```text
Activity publiée dans un Space education
→ peut être présentée comme Programme
```

lorsque sa réalité et sa configuration le justifient.

Le contrat UX ne décrète pas que toute `Activity` d’un Space education est automatiquement un Programme éducatif complet.

L’Operational Footprint et les propriétaires réels restent prioritaires.

---

# 7. Session visible ≠ nouveau modèle Session

Une Session est, dans la grammaire visible, une réalisation temporelle du Programme.

Lorsque le runtime porte cette réalisation par une `Occurrence` :

```text
Occurrence
→ Session visible
```

L’UX peut afficher :

```text
Session du 12 novembre
Session de novembre
Session soir
Session Kinshasa
```

selon les faits établis.

Elle ne doit pas inventer :

- une date ;
- une heure ;
- une durée ;
- une salle ;
- un format ;
- une capacité.

---

# 8. Inscription / demande visible

Le runtime possède `Journey` avec :

```text
workflow = registration
```

Le vocabulaire produit actuel sait présenter ce workflow comme :

```text
Inscription
S’inscrire
Voir mon inscription
```

Côté opérateur Space, le contrat visible retient :

```text
Inscription
Demande d’inscription
Admission
```

selon le contexte réel et le vocabulaire du Programme.

Mais :

```text
Journey
≠ mot visible obligatoire
```

et :

```text
Journey status
≠ onglet administratif universel
```

---

# 9. Structure durable et continuité

Programmes doit séparer cognitivement deux familles :

```text
STRUCTURE DURABLE
→ les Programmes qui existent

CONTINUITÉ
→ ce qui doit avancer autour de leurs Sessions et inscriptions
```

Exemples de structure :

```text
Programme Comptabilité
Programme Anglais professionnel
Programme Développement Web
```

Exemples de continuité :

```text
Session de novembre à préparer
18 demandes d’inscription à examiner
Session du soir en cours
Conditions manquantes sur 3 demandes
```

La même réalité peut apparaître dans les deux lectures sans duplication métier.

---

# 10. Architecture cognitive générale

Structure conceptuelle de référence :

```text
PROGRAMMES
│
├── ACTOR_CONTEXT
│   └── Space
│
├── VIEWER
│   └── Profile authentifié
│
├── RESPONSIBILITY_LENS ?
│
├── HEADER
│   ├── Makolo
│   ├── contexte Space / Programmes
│   ├── recherche / filtres utiles
│   └── Avatar humain
│
├── CONTINUITY_FIELD
│   ├── SESSIONS_ACTUELLES ?
│   ├── PROCHAINES_SESSIONS ?
│   ├── À_PRÉPARER ?
│   ├── INSCRIPTIONS_À_TRAITER ?
│   └── BLOQUÉ ?
│
├── PROGRAMME_FIELD
│   └── PROGRAMME_ENTRY[]
│
├── CREATE_CAPABILITIES[]
│
└── DEPTH
    ├── PROGRAMME N2
    ├── SESSION N2
    ├── INSCRIPTION / DEMANDE N2
    └── OWNER N3
```

Cette structure est une grammaire UX.

Elle n’impose pas un schéma SQL ni un payload JSON définitif unique.

---

# 11. N1 — objectif

N1 doit permettre de comprendre en quelques secondes :

```text
1. quels Programmes existent ?
2. quelle Session est la plus proche ou actuelle ?
3. qu’est-ce qui demande réellement du travail ?
4. y a-t-il des inscriptions / demandes qui nécessitent une intervention ?
5. comment ouvrir un Programme précis ?
```

N1 ne doit pas répondre d’emblée à toutes les questions de gestion détaillée.

---

# 12. N1 — composition Compact de référence

Fixture conceptuelle :

```text
Makolo                                  Avatar

Université Kasaï ▾
Programmes
Toutes mes responsabilités ▾

Prochaine session

Comptabilité pratique
12 novembre · 08:00
Campus central
24 places

Préparation
2 éléments restent à régler

[ Ouvrir la session ]

Inscriptions à traiter
5 demandes nécessitent une décision
[ Voir les demandes ]

Programmes

Comptabilité pratique
Prochaine session · 12 nov

Anglais professionnel
Prochaine session · 18 nov

Développement Web
Aucune session planifiée

[ Nouveau programme ]   si autorisé

Maintenant   Découvrir   [Mark]   Programmes   Nous
```

Cette fixture illustre une composition.

Elle ne fixe pas la microcopy finale ni les nombres réels.

---

# 13. N1 — ordre perceptif

L’ordre de priorité visible est :

```text
P3
conséquence opérationnelle ou prochaine Session réellement importante

P2
Programme / Session concerné

P2
prochaine action légitime si elle existe

P1
métadonnées utiles : date, lieu, format, Capacity connue

P0/P1
informations de support
```

Il ne doit pas y avoir deux P3 concurrents.

Si une admission critique exige une décision aujourd’hui, elle peut devenir P3.

Si rien ne demande d’attention, la structure Programme peut redevenir dominante sans inventer une urgence.

---

# 14. Section « Prochaine session »

Une prochaine Session peut être mise en avant lorsque :

- elle est suffisamment proche pour être utile ;
- elle est légitimement visible pour le viewer ;
- elle possède une date ou fenêtre suffisamment établie ;
- son état contribue réellement à l’exploitation du Programme.

Cette mise en avant ne transforme pas automatiquement la Session en Now.

```text
Programmes
→ continuité durable

Now
→ attention actuelle
```

---

# 15. Sessions actuelles

Si une Session est effectivement actuelle :

```text
Session en cours
```

peut apparaître dans Programmes.

Mais :

```text
Session actuelle
≠ tout le Space en Live
```

Une Session actuelle peut devenir un Jour J distinct.

Plusieurs Sessions simultanées peuvent produire plusieurs Jour J.

---

# 16. Prochaines Sessions

La section peut montrer un nombre raisonnable de Sessions avec :

- Programme ;
- date / heure ;
- lieu ou format si utile ;
- état de préparation si owner-backed ;
- Capacity si pertinente et établie ;
- handoff vers la Session.

Elle ne doit pas devenir un calendrier exhaustif par défaut.

Un calendrier peut être une vue alternative si la densité temporelle le justifie.

---

# 17. « À préparer »

`À préparer` n’est pas une todo list générique.

Il représente des réalités owner-backed telles que :

- Session encore en brouillon ;
- conditions non suffisamment prêtes ;
- formulaire à finaliser ;
- ressource nécessaire ;
- Capacity à établir ;
- accès à préparer ;
- autre préparation démontrée par le propriétaire.

Makolo ne doit pas fabriquer un `PreparationStatus` universel.

---

# 18. « Inscriptions à traiter »

Cette lecture est autorisée uniquement pour un viewer disposant de l’autorité correspondante.

Elle peut regrouper :

- nouvelles demandes ;
- demandes en attente d’approbation ;
- demandes bloquées par des conditions ;
- décisions attendues ;
- inscriptions nécessitant une intervention owner-backed.

Elle ne doit jamais exposer :

- bénéficiaires non autorisés ;
- emails ou téléphones inutiles ;
- pièces privées sans besoin ;
- états d’autres Programmes hors scope.

La divulgation minimale est obligatoire.

---

# 19. « Bloqué »

Un blocker doit être relatif à une transition réelle.

Exemple :

```text
Demande de Marie
→ justificatif requis absent
→ admission impossible pour le moment
```

Ne pas traduire toute attente en blocage.

```text
attente normale
≠
blocage
```

Le contrat En cours reste applicable à cette distinction.

---

# 20. Terminés

Le passé ne doit pas dominer N1.

Les Sessions terminées, inscriptions clôturées et Programmes archivés restent accessibles :

- par historique ;
- par Programme ;
- par recherche ;
- par profondeur propriétaire.

Mais Programmes ne devient pas une archive infinie.

---

# 21. Programme Field

Le `PROGRAMME_FIELD` est la lecture structurante des Programmes légitimement visibles dans le Space.

Il ne doit pas être dérivé uniquement d’un statut technique.

Le Programme visible peut fournir :

```text
nom
résumé court
prochaine Session ?
état de disponibilité utile ?
lieu / format si structurant ?
indication de préparation si réelle ?
capability principale ?
```

Pas :

```text
Journey count
Requirement count
Form count
Access count
```

comme taxonomie première.

---

# 22. Représentation d’un Programme en N1

Forme de référence compacte :

```text
Comptabilité pratique
Prochaine session · 12 novembre
Campus central

2 éléments à préparer
```

ou, lorsqu’il n’y a rien à préparer :

```text
Comptabilité pratique
Prochaine session · 12 novembre
Tout est prêt pour la prochaine session
```

La formulation `Tout est prêt` ne peut apparaître que si Readiness ou les propriétaires permettent réellement cette conclusion.

---

# 23. Pas de pourcentage arbitraire

Interdit :

```text
Programme prêt à 73 %
```

sauf si une métrique métier défendable et propriétaire existe réellement.

Readiness reste une projection dérivée.

Le design privilégie :

```text
Ce qui est prêt
Ce qui manque
Ce qui bloque
Ce qui vient ensuite
```

---

# 24. N1 — Programme sans prochaine Session

Un Programme durable peut exister sans Session planifiée.

Exemple :

```text
Développement Web
Aucune session planifiée
```

Ce Programme ne doit pas disparaître de la structure simplement parce qu’il n’est pas actuellement « en cours ».

Invariant :

```text
Programme actif
≠
continuité active
```

---

# 25. N1 — Programme archivé ou terminé

Un Programme réellement terminé ou archivé ne doit pas être affiché comme structure active par défaut.

Il reste retrouvable dans :

```text
Historique / archives / profondeur owner
```

selon le contrat réel.

---

# 26. N1 — Session sans inscriptions

Une Session peut exister même lorsqu’aucune inscription n’est visible ou nécessaire.

L’UX ne doit pas créer artificiellement une section `Admissions` vide pour remplir l’écran.

---

# 27. N1 — Programme sans Journey

Un Programme peut être opéré sans workflow d’inscription dans Makolo.

Dans ce cas :

- aucune fausse demande ;
- aucun compteur d’admissions ;
- aucun bouton `Voir les inscriptions` ;
- aucun faux Access.

Le Programme reste légitime.

---

# 28. Recherche Programmes

La recherche porte sur le monde métier visible du Space.

Exemples de requêtes humaines :

```text
Comptabilité
Session novembre
Anglais soir
Kinshasa
```

La recherche ne doit pas imposer :

```text
Activity.status
Journey.workflow
Occurrence.status
Requirement.kind
```

comme vocabulaire.

---

# 29. Filtres Programmes

Filtres légitimes lorsque soutenus par les faits :

- Programme ;
- période ;
- Session ;
- lieu ;
- format ;
- préparation ;
- demandes nécessitant une intervention ;
- responsabilité ;
- état humain utile.

Les filtres secondaires peuvent être placés dans une bottom sheet sur mobile.

Les filtres actifs qui changent réellement le champ doivent rester visibles.

---

# 30. Calendrier

Le calendrier est une vue possible des Sessions.

Il n’est pas obligatoire simplement parce que les Sessions ont des dates.

Il devient pertinent lorsque :

- plusieurs Sessions se chevauchent ;
- l’organisation planifie fréquemment ;
- la lecture temporelle aide à agir.

Invariant :

```text
liste ↔ calendrier
```

préserve :

- filtres ;
- query ;
- Programme sélectionné ;
- période ;
- profondeur si possible.

---

# 31. Carte

La carte n’est pas une vue primaire universelle de Programmes.

Elle peut être utile si :

- les Sessions sont distribuées sur plusieurs campus ;
- plusieurs lieux physiques comptent ;
- l’orientation vers un lieu aide réellement.

Elle reste une représentation de faits géographiques existants.

---

# 32. Création contextuelle

La source Space fixe :

```text
Programmes
→ Nouveau programme
→ Nouvelle session
```

Le contrat visible ajoute :

- `Nouveau programme` peut apparaître en N1 si capability réelle ;
- `Nouvelle session` est normalement plus naturelle dans le contexte d’un Programme ;
- une action de création ne doit pas exposer `Activity`, `Occurrence`, `Journey`, `Requirement` ;
- la création ne doit jamais être autorisée seulement parce que l’action est visible côté client.

---

# 33. Placement de la création

Sur Compact :

- action de header secondaire ; ou
- bouton contextualisé en fin/début de champ ; ou
- empty state utile.

Sur Wide :

- action proche du titre de la surface ;
- jamais une palette d’administration permanente.

Le Makolo Mark reste distinct de la création directe.

---

# 34. Makolo Mark → Programmes

Exemple :

> « Ajoute une session de Comptabilité samedi prochain à 9 h. »

Le Mark peut comprendre le contexte du Space.

Mais il doit encore vérifier :

- Programme cible ;
- date / temporalité ;
- autorité ;
- owner correct ;
- informations obligatoires.

Le Mark ne contourne jamais Permission ou Mandate.

---

# 35. N2 — principe général

N2 doit conserver la réalité humaine ouverte.

Trois profondeurs dominantes existent :

```text
Programme N2
Session N2
Inscription / demande N2
```

Elles ne deviennent pas trois applications.

---

# 36. N2 Programme — objectif

N2 Programme répond :

```text
Qu’est-ce que ce Programme ?
Quelles Sessions le réalisent ?
Quelle est la prochaine Session ?
Qu’est-ce qui doit être préparé ?
Comment fonctionnent les inscriptions ?
Quelles conditions / ressources comptent ?
Quels groupes ou cohortes sont réellement liés ?
```

---

# 37. N2 Programme — composition

Structure candidate :

```text
Programme Comptabilité pratique

Résumé humain

Prochaine session
12 novembre · 08:00
Campus central
[ Ouvrir ]

Sessions
12 nov
18 jan
15 mars

Inscriptions
Ouvertes
5 demandes à examiner   si autorisé

Préparation
✓ formulaire disponible
✓ ressources publiées
! une condition reste à vérifier

Conditions
...

Ressources
...

Groupes / cohortes
Cohorte Novembre

Accès
selon contrat réel
```

L’ordre exact dépend du Programme et de l’autorité.

---

# 38. N2 Programme — Sections conditionnelles

Aucune section n’est obligatoire si le domaine ne la soutient pas.

Ainsi :

```text
Conditions absentes
→ ne pas inventer Conditions

Ressources absentes
→ ne pas afficher « 0 ressource » comme module fort

Groupes absents
→ ne pas créer Cohorte

Access non utilisé
→ ne pas créer Accès
```

---

# 39. N2 Programme — Sessions

La section Sessions peut montrer :

- prochaine ;
- futures ;
- actuelle ;
- récemment terminées si utile ;
- état de préparation ;
- lieux / format ;
- Capacity si légitime.

Elle ne devient pas un calendrier technique obligatoire.

---

# 40. N2 Programme — Inscriptions

Deux niveaux de lecture :

### Synthèse

```text
5 demandes à examiner
12 confirmées
```

uniquement si les compteurs sont réellement calculés et autorisés.

### Profondeur

Liste des démarches admissibles au viewer.

La synthèse ne doit pas exposer les personnes.

---

# 41. N2 Programme — Conditions

`Condition` est un mot UX possible.

La vérité peut être portée par `Requirement` ou autre propriétaire adapté.

Le Programme peut expliquer :

```text
Pièce d’identité requise
Niveau B1 recommandé / requis selon vérité
Paiement préalable si réellement configuré
```

Le design doit distinguer :

- condition exigée ;
- recommandation ;
- information ;
- inconnue.

---

# 42. N2 Programme — Formulaires

Les Forms sont transversaux.

Ils peuvent apparaître comme :

```text
Formulaire d’inscription
Questionnaire préalable
```

Le Programme ne crée pas `ProgrammeForm` si le moteur Forms existe déjà.

---

# 43. N2 Programme — Ressources

Les ressources peuvent être :

- document ;
- consigne ;
- lien ;
- support pédagogique ;
- autre ressource owner-backed.

No Orphan Content s’applique.

Une ressource doit servir :

- préparation ;
- apprentissage ;
- orientation ;
- preuve ;
- accomplissement.

Pas de bibliothèque média générique uniquement pour retenir l’attention.

---

# 44. N2 Programme — Groupes / cohortes

Les Groupes et cohortes apparaissent seulement s’ils existent réellement.

Ils peuvent servir à comprendre :

- qui apprend ensemble ;
- quelle Session ou période les concerne ;
- quelle ressource ou communication est liée.

Mais :

```text
GroupMembership
≠ Mandate
```

et :

```text
être membre d’une cohorte
≠ autorité opérateur
```

---

# 45. N2 Programme — Access

Access reste le droit canonique.

Dans un Programme, il peut représenter :

- confirmation ;
- droit d’entrer dans une Session ;
- accès à un lieu ou une ressource selon le contrat.

Mais :

```text
Access
≠ AccessCredential
≠ AccessUse
```

Le Programme ne duplique pas ces vérités.

---

# 46. N2 Programme — Capacity

Capacity répond à :

> **Combien ?**

Exemple :

```text
24 places
18 confirmées
```

si ces chiffres sont réellement établis par le domaine Capacity.

Le client ne reconstruit pas une Capacity globale depuis une liste locale d’inscriptions.

---

# 47. N2 Programme — personnes concernées

Les personnes concernées ne sont jamais une donnée publique par défaut.

La profondeur peut montrer :

- apprenants inscrits ;
- demandeurs ;
- responsables ;
- intervenants ;

uniquement selon l’autorité, le besoin et les contrats propriétaires.

La divulgation minimale s’applique.

---

# 48. N2 Session — objectif

Une Session répond :

```text
Quand ?
Où / dans quel format ?
Pour quel Programme ?
Est-elle prête ?
Quelle Capacity s’applique ?
Qui peut y accéder ?
Qu’est-ce qui se passe maintenant ?
```

---

# 49. N2 Session — composition candidate

```text
Session · Comptabilité pratique
12 novembre · 08:00–12:00
Campus central

État
Prête / préparation requise / inconnue

Capacity
18 / 24 confirmées   si établi

Accès
état utile selon autorité

Cohorte
Novembre

Préparation
ressources / conditions utiles

[ Ouvrir Jour J ]   lorsque admis
```

---

# 50. Session récurrente

Le runtime peut utiliser `OccurrenceSchedule` pour matérialiser des Occurrences.

L’UX ne doit pas obliger l’utilisateur à comprendre :

```text
OccurrenceSchedule
```

Elle peut dire :

```text
Tous les samedis
```

si ce fait est réellement configuré.

La Session concrète reste une Occurrence distincte lorsqu’elle existe.

---

# 51. Session date-only / all-day

Le runtime distingue :

```text
exact
date_only
all_day
```

L’UX doit préserver cette nuance.

Interdit :

```text
heure 00:00
```

pour simuler une heure inconnue.

Exemples :

```text
12 novembre
Heure à confirmer
```

ou :

```text
Toute la journée
```

---

# 52. N2 Session → Jour J

Une Session suffisamment actuelle peut être admise dans Jour J.

Flux :

```text
Programme
→ Session
→ Jour J
→ Live éventuellement
```

Le seuil d’entrée Jour J est owner/server resolved.

Le client ne décide pas :

```text
start_at proche
→ Jour J
```

tout seul.

---

# 53. Jour J d’une Session

Jour J opérateur peut concentrer :

- préparation ;
- Capacity ;
- personnes attendues dans la limite de l’autorité ;
- AccessUse ;
- contrôle ;
- incidents ;
- ressources ;
- état opérationnel.

Même Occurrence, projections différentes pour participant et opérateur.

---

# 54. Plusieurs Sessions simultanées

Un Space education peut avoir :

```text
Session A
Session B
Session C
```

simultanément.

Donc :

```text
Space
├── Jour J A
├── Jour J B
└── Jour J C
```

Le Space entier ne devient jamais Live.

---

# 55. Makolo Live

Live appartient à une Session / Occurrence actuelle via Jour J.

Il ne devient pas :

- flux général de l’école ;
- feed de cours ;
- activité récente du Programme ;
- présence implicite non observée.

Live représente seulement des faits observés ou suffisamment établis comme en train de se produire.

---

# 56. N2 Inscription / demande — objectif

Cette profondeur répond :

```text
De quelle inscription s’agit-il ?
Pour quel Programme / Session ?
Où en est-elle réellement ?
Qu’est-ce qui est déjà satisfait ?
Qu’est-ce qui manque ?
Y a-t-il un blocker ?
Qui doit agir ?
Quelle décision est autorisée ?
```

---

# 57. N2 Inscription — identité humaine

La vue doit parler :

```text
Inscription · Programme Comptabilité
Marie Kalala
```

si la personne est légitimement visible.

Pas :

```text
Journey 3e5a...
workflow=registration
status=pending_approval
```

---

# 58. N2 Inscription — continuité

La grammaire profonde En cours peut être réutilisée :

```text
SETTLED
MY_SIDE / SPACE_SIDE selon perspective
ELSEWHERE
NEXT
BLOCKERS
UNKNOWN
```

Mais le vocabulaire visible reste éducatif.

Exemple :

```text
Demande reçue
Formulaire complet
Justificatif manquant
Décision d’admission en attente
```

---

# 59. N2 Inscription — décision

Une décision d’admission peut être une action sensible.

Elle exige :

- capability réelle ;
- confirmation serveur ;
- revalidation d’autorité ;
- feedback exact.

Le client ne peut pas afficher :

```text
Admis
```

si seule une intention locale a été enregistrée.

---

# 60. N2 Inscription — Payment

Si un paiement compte pour l’inscription :

- il reste chez Payment ;
- l’inscription peut expliquer sa conséquence ;
- une confirmation Payment ne signifie pas automatiquement admission accomplie ;
- une admission ne signifie pas nécessairement Payment finalisé si le contrat dit autre chose.

---

# 61. N2 Inscription — Proof / documents

Posséder un document :

```text
≠ le retrouver
≠ satisfaire un Requirement
```

Le Programme ne doit pas confondre :

- document fourni ;
- document retrouvé ;
- preuve vérifiée ;
- Requirement satisfait.

---

# 62. N3 — principe

N3 ouvre une profondeur propriétaire lorsque l’action exige plus de précision.

Exemples :

```text
Modifier le Programme
Configurer la Session
Examiner la demande
Vérifier une condition
Consulter le formulaire
Gérer une ressource
Configurer la Capacity
Gérer l’Access
```

N3 ne doit pas être inventé par Presentation lorsqu’aucun owner ne supporte l’action.

---

# 63. N3 — pas de prison latérale

Sur Wide, un petit panneau peut servir à inspecter.

Mais une action complexe ne doit pas être enfermée artificiellement dans 300 px.

Si elle exige :

- plusieurs étapes ;
- documents ;
- décision ;
- configuration ;
- comparaison ;

elle peut devenir une vraie profondeur pleine.

---

# 64. Frontière Programmes ↔ Maintenant

Programmes conserve le monde éducatif durable.

Now sélectionne ce qui mérite une attention actuelle.

Exemple :

```text
Programmes
→ Session du 12 novembre
→ 1 condition manque
```

peut produire dans Now :

```text
Session du 12 novembre
Le formulaire d’admission n’est pas encore disponible.
La session ouvre dans 3 jours.
[ Préparer ]
```

Même vérité.

Deux projections.

---

# 65. Programmes ↔ Découvrir

Découvrir Space répond :

> **Qu’est-ce qui pourrait nous aider à avancer ?**

Programmes répond :

> **Qu’est-ce que nous opérons déjà comme offre éducative réelle ?**

Un partenaire potentiel, un lieu, un financement ou un nouveau Programme à envisager peut vivre dans Découvrir.

Une fois réellement engagé et porté par les owners du Space, il peut entrer dans Métier.

---

# 66. Programmes ↔ Nous

Programmes = ce que le Space fait.

Nous = qui est le Space et comment il fonctionne.

Donc :

```text
Programme Comptabilité
Sessions
Inscriptions
→ Programmes
```

alors que :

```text
Équipe pédagogique
Responsabilités
Mandates
Partenaires
Identité institutionnelle
→ Nous / Personnes & relations
```

Une profondeur Programme peut montrer le responsable sans devenir propriétaire de Team ou Mandate.

---

# 67. Programmes ↔ Piloter

Programmes opère.

Piloter prend du recul.

Exemples Piloter :

- tendances d’inscription ;
- Capacity ;
- délivrance ;
- finance ;
- incidents ;
- fonctionnement.

Programmes ne devient pas un dashboard KPI permanent.

---

# 68. Programmes ↔ Personnes & relations

Pour education, l’architecture Space propose :

```text
Groupes, personnes & partenaires
```

comme vocabulaire relationnel.

Programmes peut montrer les personnes strictement nécessaires à son exploitation.

Il ne remplace pas cette surface relationnelle.

---

# 69. Programmes ↔ Historique

Les Sessions passées, inscriptions terminées et Programmes archivés restent retrouvables.

Ils ne doivent pas encombrer la racine active.

---

# 70. États — matrice minimale

Programmes doit couvrir :

```text
initial
loading
content
empty
calm
success
erreur localisée
erreur globale rare
offline
stale
permission-denied
refresh
back
resume
```

Offline est principalement un axe de synchronisation, pas un remplacement automatique du contenu.

---

# 71. Initial

Avant toute donnée disponible :

- shell immédiatement reconnaissable ;
- pas de flash de faux `Aucun programme` ;
- pas de faux compteur à zéro ;
- skeleton seulement si l’attente dépasse le seuil pertinent.

---

# 72. Loading

Pour une première charge :

- skeleton de rythme Programme/Session ;
- éviter spinner plein écran si possible.

Pour refresh :

- conserver le contenu existant ;
- indicateur discret ;
- ne pas remplacer l’écran par un skeleton.

---

# 73. Content

L’état normal combine selon les données :

```text
structure Programme
+
continuité Session
+
inscriptions utiles
```

sans obligation de remplir chaque zone.

---

# 74. Empty total

Space education réellement sans Programme visible :

```text
Programmes

Aucun programme pour le moment.
```

Si capability :

```text
[ Créer un programme ]
```

Sinon, aucune action inventée.

---

# 75. Calm avec Programmes

Un état calme peut être :

```text
Programmes

Tout est en ordre. ✓

3 programmes actifs
Prochaine session · 12 novembre
```

`Tout est en ordre. ✓` n’est légitime que si les propriétaires et la fraîcheur permettent de conclure qu’aucune intervention utile n’est connue.

---

# 76. Offline avec snapshot

Exemple :

```text
Programmes

Dernières informations synchronisées · 09:15

Comptabilité pratique
Session · 12 novembre
```

La structure connue reste utilisable.

Mais :

- Capacity potentiellement partagée peut être stale ;
- admissions concurrentes ne sont pas finalisées localement ;
- Access courant ne doit pas être inventé ;
- Live n’est jamais reconstruit depuis un snapshot ancien.

---

# 77. Offline sans snapshot

Le produit doit dire qu’il ne peut pas charger les Programmes connus sur cet appareil.

Il ne doit pas afficher :

```text
Aucun programme
```

si l’absence vient du réseau / store.

---

# 78. Stale

Une donnée ancienne reste identifiable comme telle.

Exemples de faits nécessitant prudence :

- Capacity actuelle ;
- nombre de demandes ;
- décision récente ;
- état d’une inscription ;
- changement de Session ;
- Access partagé.

La présentation doit conserver la personnalité Programmes.

---

# 79. Erreur localisée

Si les Programmes chargent mais les inscriptions échouent :

```text
Programme / Sessions
→ restent visibles

Inscriptions
→ indisponibles pour le moment
```

Pas de panne globale artificielle.

---

# 80. Permission loss

Si une personne perd l’autorité de voir les demandes :

- retirer les données privées ;
- conserver les Programmes qu’elle peut encore voir ;
- expliquer localement la limite si nécessaire ;
- ne pas conserver une liste privée obsolète comme vérité active.

---

# 81. Back

Le parcours :

```text
Programmes N1
→ Programme N2
→ Session N2
→ Retour
```

restaure autant que possible :

- scroll ;
- Programme sélectionné ;
- filtres ;
- query ;
- période ;
- responsabilité ;
- vue liste/calendrier.

---

# 82. Resume

Après retour depuis l’arrière-plan :

- conserver la profondeur si encore autorisée ;
- rafraîchir discrètement les faits potentiellement obsolètes ;
- revalider une action sensible avant exécution ;
- ne pas remettre systématiquement à N1.

---

# 83. Deep links

Destinations possibles lorsque le modèle de sécurité le permet :

- Programme ;
- Session ;
- inscription/demande ;
- Jour J de Session ;
- owner depth autorisé.

Le deep link doit :

1. authentifier ;
2. résoudre Actor Context ;
3. vérifier autorité et visibilité ;
4. ouvrir la profondeur autorisée ;
5. proposer une alternative si la destination n’est plus disponible.

---

# 84. Local-first

Le client installé peut conserver localement ce qui est déjà utile et autorisé :

- Programmes connus ;
- Sessions connues ;
- projections d’inscription nécessaires au viewer ;
- ressources autorisées ;
- états de préparation connus ;
- contexte de navigation.

Le serveur reste autoritaire pour :

- Permission / Mandate ;
- Capacity globale ;
- décision d’admission ;
- état partagé récent ;
- Access partagé ;
- Payment ;
- concurrence entre plusieurs opérateurs.

---

# 85. Classes d’opération

Le langage technique A/B/C/D n’est pas exposé, mais l’implémentation doit distinguer :

### A — locale

Exemple :

```text
ouvrir un Programme déjà synchronisé
changer de vue locale
```

### B — locale puis synchronisée

Possible pour certaines préférences ou brouillons si le runtime le supporte.

### C — préparée localement puis confirmée à distance

Exemple conceptuel :

```text
préparer une modification de formulaire
```

si un owner supporte ce mode.

### D — intrinsèquement distante

Exemples :

```text
décider une admission partagée
confirmer une Capacity actuelle
révoquer un Access
```

Aucun faux succès.

---

# 86. Outbox

Une action synchronisable acceptée localement et dont la perte serait problématique doit utiliser l’outbox lorsque l’architecture la supporte.

Elle doit porter :

- identité ;
- dépendance ;
- retry ;
- idempotence ;
- statut ;
- confirmation distante.

---

# 87. Compact

Sur C-S / C-L :

```text
header
contexte Space / Programmes
responsibility lens

focus opérationnel

sections verticales
Programme rows

bottom nav
```

N2 ouvre normalement une page pleine.

Les sections de support restent progressives.

---

# 88. Medium

À environ 834 dp :

- colonne principale plus respirante ;
- possibilité de preview si la contrainte cognitive est satisfaite ;
- aucun split obligatoire ;
- calendrier possible si utile ;
- la hiérarchie reste identique à Compact.

---

# 89. Wide

Sur 1440 × 900 :

candidate :

```text
NAV RAIL
+
PROGRAMME FIELD
+
N2 sélectionné si ouvert
```

La largeur sert à conserver le contexte.

Elle ne doit pas produire automatiquement :

- KPI ;
- 8 panneaux ;
- statistiques ;
- liste de tous les modules.

---

# 90. Very Wide

Sur Very Wide :

un troisième territoire n’est admis que s’il porte un rôle cognitif distinct.

Exemple possible :

```text
Programme field
+
Session focus
+
Support contextuel
```

mais seulement lorsqu’une tâche réelle le justifie.

---

# 91. Adaptive conservation

Lors de :

```text
Compact → Medium
Medium → Wide
Wide → Compact
rotation
resize
```

préserver autant que possible :

- surface Programmes ;
- Programme sélectionné ;
- Session sélectionnée ;
- query ;
- filtres ;
- période ;
- scroll ;
- responsibility lens ;
- profondeur ;
- brouillon éventuel.

---

# 92. Text scaling

Tests minimum :

```text
1.0
1.3
1.6
```

À 1.6 :

- aucun fait essentiel tronqué ;
- metadata wrap ;
- actions accessibles ;
- pas de hauteur fixe sur Programme row ;
- split peut retomber en single pane.

---

# 93. Accessibilité

Obligatoire :

- lecteur d’écran ;
- focus visible ;
- contraste ;
- aucun sens dépendant uniquement de la couleur ;
- cibles tactiles adéquates ;
- ordre sémantique cohérent ;
- états annoncés sans bruit excessif ;
- calendrier utilisable sans geste visuel exclusif.

---

# 94. Motion

Motion doit expliquer :

- ouverture N1 → N2 ;
- changement de période ;
- insertion d’une Session ;
- feedback d’action ;

sans ralentir le travail.

`Reduce Motion` doit être supporté.

---

# 95. Média

Programmes peut utiliser :

- image contextuelle ;
- document ;
- vidéo pédagogique ;
- audio ;

seulement si le média aide à :

- comprendre ;
- préparer ;
- apprendre ;
- accomplir.

No Orphan Media s’applique.

La racine Métier ne devient pas un feed de contenus éducatifs.

---

# 96. Notifications

Une Notification est un canal.

Elle n’est pas la Session, le Programme ni la demande.

Un fait peut produire :

```text
fait métier
→ conséquence
→ éventuellement Now
→ éventuellement Notification
```

Programmes reste la profondeur durable.

---

# 97. Conversations

Une conversation peut être liée à :

- admission ;
- clarification ;
- ressource ;
- passage de relais ;

mais n’est pas automatiquement une urgence.

La conversation ne remplace pas le statut propriétaire.

---

# 98. Handoffs principaux

```text
Programmes N1
→ Programme N2
→ Session N2
→ Jour J
→ Live
```

et :

```text
Programme N2
→ Inscription N2
→ owner depth
```

et :

```text
Programmes
→ Now
→ Piloter
→ Nous / relations
```

selon contexte.

---

# 99. Contrat serveur/client — endpoint racine actuel

RUNTIME OBSERVÉ :

```http
GET /api/v1/organizations/workspaces/<slug>/work/
```

Paramètre actuellement accepté :

```text
responsibility=<key>
```

Le serveur :

- résout le Space parmi les Spaces réellement accessibles ;
- résout la portée de responsabilité ;
- filtre les Activities visibles ;
- calcule des capabilities owner-backed ;
- compose des sections ;
- répond avec `Cache-Control: private, no-store`.

Le client ne doit pas augmenter sa portée en modifiant `responsibility`.

---

# 100. Runtime education observé dans `main`

Dans `build_space_work_projection(...)` :

- `primary_business_label` provient de l’archétype ;
- pour `education`, la valeur est `Programmes` ;
- les Activities visibles sont projetées ;
- les Occurrences futures / actives sont projetées ;
- les Journey `workflow=registration` sont projetés uniquement pour les Activities où le viewer possède la capability requests correspondante ;
- les bénéficiaires ne doivent pas être exposés hors autorité ;
- la réponse fournit `authority`, `responsibility`, `operational_footprint`, `sections`, `links`, `capabilities`.

Limite actuelle de `main` :

```text
Activity PUBLISHED
→ section active
```

Cette forme mélange encore structure durable et continuité.

---

# 101. PR #496 et cible Programmes

PR EN COURS : #496 sépare :

```text
sections structurelles
≠
sections de continuité
```

Elle introduit notamment :

```text
activities
role = structure
representation = primary_business_label
```

Donc pour education :

```text
activities
→ Programmes
```

Elle ajoute `continuity_facet` seulement aux Journey progressifs.

Cette direction est cohérente avec le présent contrat :

```text
Programme publié
→ structure

Journey registration progressif
→ continuité
```

Le contrat ne considère pas la PR comme fusionnée tant qu’elle ne l’est pas.

---

# 102. Contrat cible de section

Forme conceptuelle :

```text
SECTION
├── identity
├── role
├── representation
├── coverage_state
├── items[]
├── has_more
└── links
```

Rôles possibles utiles :

```text
structure
continuity
history
```

Les noms wire définitifs restent secondaires par rapport à cette sémantique.

---

# 103. Contrat cible Programme Entry

Conceptuellement :

```text
PROGRAMME_ENTRY
├── identity
├── source
├── kind
├── title
├── summary?
├── next_session?
├── preparation_context?
├── timing?
├── place_or_format?
├── capacity_context?
├── knowledge_context
├── capabilities[]
├── links
└── handoffs[]
```

`PROGRAMME_ENTRY` est une projection UX.

Il n’est pas un modèle persistant.

---

# 104. Contrat cible Session Entry

```text
SESSION_ENTRY
├── source = Occurrence owner-backed
├── programme_reference
├── identity / label
├── temporal_facts
├── place / format
├── readiness_context?
├── capacity_context?
├── access_context?
├── day_of_handoff?
├── knowledge_context
├── capabilities[]
└── links
```

Aucune donnée n’est inventée pour remplir les champs.

---

# 105. Contrat cible Registration Entry

```text
REGISTRATION_ENTRY
├── source = Journey owner-backed
├── programme_reference
├── session_reference?
├── subject_identity?   selon autorité
├── state
├── continuity_facet
├── requirements_context?
├── form_context?
├── payment_context?
├── access_context?
├── blockers[]
├── next[]
├── capabilities[]
└── links
```

La personne concernée est minimale et scope-gated.

---

# 106. Capabilities

Les capabilities visibles doivent provenir du serveur / owner.

Runtime actuel expose notamment des capabilities autour d’Activity :

```text
view
manage
open_operations
open_commerce
open_requests
open_service_cases
```

Pour Programmes, l’UX ne doit montrer que ce qui a un sens contextuel.

Exemple :

```text
manage
→ Modifier le programme

open_requests
→ Voir les inscriptions
```

Le nom visible n’a pas à reprendre le nom technique.

---

# 107. `create_programme`

Runtime actuel de la racine expose :

```text
create_activity
```

La Presentation `education` peut le traduire en :

```text
Nouveau programme
```

Cette traduction ne crée aucune permission supplémentaire.

---

# 108. `create_session`

Le présent contrat UX exige qu’une Session puisse être créée contextuellement lorsqu’un owner et une capability réelle existent.

Mais le endpoint / capability exact n’est pas démontré par la racine `/work/` actuelle.

Statut :

```text
CIBLE UX
+
CONTRAT TECHNIQUE EXACT OUVERT
```

Ne pas inventer un endpoint dans Flutter.

---

# 109. Fraîcheur

Programmes doit distinguer :

```text
fresh
stale
unknown
unavailable
```

lorsque nécessaire.

Une Session planifiée peut être connue localement.

Le nombre actuel de places ou une décision d’admission récente peut exiger davantage de fraîcheur.

---

# 110. Coverage

Une réponse partielle ne doit pas être interprétée comme exhaustivité.

Exemple :

```text
5 demandes affichées
has_more = true
```

ne signifie pas :

```text
exactement 5 demandes existent
```

---

# 111. Pagination / continuation

La racine ne doit pas dépendre d’une limite UX conceptuelle arbitraire.

Un preview borné est permis.

La profondeur doit offrir une continuation réelle lorsque nécessaire.

Le mécanisme exact :

- continuation token ;
- pagination owner ;
- cursor ;

reste un choix technique à confirmer par le runtime.

---

# 112. Confidentialité

Données particulièrement sensibles :

- identité des demandeurs ;
- documents ;
- réponses de Form ;
- Requirements privés ;
- états d’admission ;
- données de paiement ;
- accès ;
- informations de mineurs lorsqu’elles existent.

Le contrat général de divulgation minimale s’applique strictement.

---

# 113. IDOR

Toute profondeur par identifiant doit vérifier côté serveur :

```text
viewer
+
Space
+
owner scope
+
authority
+
object relation
```

Une URL ou un ID connu ne suffit jamais.

---

# 114. Golden P01 — Programmes / Compact N1

**Purpose :** reconnaître immédiatement le monde éducatif actif sans dashboard.

**Fixture :**

```text
Université Kasaï
Programmes

Prochaine session
Comptabilité pratique
12 nov · 08:00
Campus central

À préparer
2 éléments

Inscriptions à traiter
5 demandes

Programmes
Comptabilité pratique
Anglais professionnel
Développement Web
```

**Viewport :**

```text
360 × 800
430 × 932
```

**Hierarchy :**

```text
prochaine conséquence   P3
Programme / Session     P2
CTA légitime            P2/P3
metadata                 P1
structure                P1/P2
```

**Acceptance :** en 500 ms, reconnaître :

```text
Space
+
Programmes
+
prochaine Session / travail utile
```

---

# 115. Golden P02 — Programme N2 Compact

**Fixture :** `Programme Comptabilité pratique`.

Doit montrer :

- prochaine Session ;
- Sessions ;
- inscriptions si autorisées ;
- préparation ;
- conditions / ressources seulement si présentes ;
- handoffs owner.

Le Golden échoue s’il ressemble à un menu de modules.

---

# 116. Golden P03 — Session N2 Compact

Doit montrer :

```text
Programme
Session
quand / où
état utile
Capacity si établie
préparation
Jour J si admis
```

Pas de Live inventé.

---

# 117. Golden P04 — Inscription N2 Compact

Doit montrer :

```text
contexte Programme
personne si autorisée
état humain
conditions
blocker si réel
prochaine décision
```

Aucune PII inutile.

---

# 118. Golden P05 — Medium

Viewport :

```text
834 × 1112
```

Candidate :

```text
Programme field
+
preview léger
```

Un split n’est admis que s’il conserve mieux le contexte.

---

# 119. Golden P06 — Wide master/detail

Viewport :

```text
1440 × 900
```

Candidate :

```text
NAV 80
FIELD 560–680
GUTTER 24
FOCUS 560–640
```

Pas de dashboard.

---

# 120. Golden P07 — Programme sans Session

Fixture :

```text
Développement Web
Aucune session planifiée
```

Le Programme reste structurellement visible.

---

# 121. Golden P08 — Offline

Fixture :

```text
content + offline
```

Doit conserver :

- Programmes connus ;
- Sessions connues ;
- fraîcheur visible ;
- actions distantes non faussement confirmées.

---

# 122. Golden P09 — Partial failure

Programme et Sessions chargent.

Inscriptions indisponibles.

Le Golden échoue si toute la surface devient erreur.

---

# 123. Golden P10 — Programme → Session → Jour J

Vérifie :

```text
Programme N2
→ Session actuelle
→ Jour J opérateur
```

Contexte conservé.

Retour Jour J :

```text
→ Session / Programme précédent
```

si toujours valide.

---

# 124. Golden P11 — plusieurs Sessions actuelles

Fixture :

```text
3 Sessions actuelles
1 demande l’attention
```

Programmes ne fusionne pas les Jour J.

La personne choisit la Session focalisée.

---

# 125. Matrice des états Programmes

| État | N1 | N2 | Action |
|---|---|---|---|
| content | structure + continuité | owner facts | autorisée selon capability |
| calm | structure, peu de signal | détail normal | aucune stimulation artificielle |
| empty | aucun Programme visible | n/a | créer si autorisé |
| loading | skeleton initial | preserve si refresh | aucune fausse action |
| offline + snapshot | contenu connu + fraîcheur | contenu connu | opérations sensibles bornées |
| offline sans snapshot | indisponibilité explicite | idem | retry |
| stale | contenu + date/fraîcheur | faits prudents | revalidation |
| partial error | dégradation locale | section locale | retry local |
| permission loss | données retirées | profondeur fermée | alternative sûre |

---

# 126. Anti-features spécifiques education

Programmes ne doit pas devenir :

- un LMS générique ;
- Moodle cloné ;
- un SIS/ERP scolaire universel ;
- une feuille de présence universelle ;
- un CRM étudiant ;
- un tableau de notes si le domaine ne le possède pas ;
- une bibliothèque de cours orpheline ;
- un feed pédagogique ;
- un catalogue marketing permanent ;
- un dashboard KPI ;
- un kanban Admissions ;
- une table de tous les Journey ;
- une table de tous les Requirements ;
- une table de tous les Forms ;
- un deuxième système Groups ;
- un deuxième système Access ;
- un deuxième Capacity ;
- un second Readiness ;
- un système où chaque Programme est forcé d’avoir une Session ;
- un système où chaque Session exige des inscriptions Makolo ;
- un système où tout membre d’une cohorte devient autorisé à opérer ;
- une surface qui révèle des bénéficiaires hors scope ;
- une surface qui prétend qu’une donnée locale ancienne est actuelle ;
- une surface où `paiement confirmé = admission accomplie` ;
- une surface où `formulaire rempli = Requirement satisfait` sans owner ;
- une surface où `document possédé = preuve validée` ;
- un écran qui remplit le desktop avec des statistiques sans action.

---

# 127. Invariants consolidés

1. `education` affiche **Programmes** comme porte Métier.
2. Programme est le contexte humain dominant.
3. Programme visible ne nécessite pas un nouveau modèle Programme.
4. Session visible peut être une projection d’Occurrence.
5. Programme actif ≠ continuité active.
6. Session actuelle ≠ Space globalement Live.
7. Plusieurs Sessions peuvent avoir plusieurs Jour J.
8. Journey `registration` peut porter une inscription/demande.
9. Journey n’est pas le vocabulaire visible primaire.
10. Conditions réutilisent Requirement ou owner adapté.
11. Formulaires réutilisent Forms.
12. Ressources restent owner-backed et finalisées par un contexte.
13. Groupes/cohortes n’accordent aucune autorité implicite.
14. Access ≠ AccessCredential ≠ AccessUse.
15. Capacity = combien ; le client ne la reconstruit pas localement.
16. Readiness reste dérivée.
17. Payment confirmé ≠ admission automatiquement accomplie.
18. Form rempli ≠ Requirement automatiquement satisfait.
19. Document possédé ≠ preuve validée.
20. Programmes ≠ Now.
21. Programmes ≠ Piloter.
22. Programmes ≠ Nous.
23. Programmes ≠ Découvrir.
24. Structure et continuité restent distinctes.
25. Un Programme sans Session peut rester visible.
26. Une Session sans inscription Makolo peut être légitime.
27. Une section absente ne doit pas être inventée.
28. L’archétype change le langage et les priorités, pas la vérité.
29. Responsibility filtre la lecture, jamais l’autorité.
30. Permission et Mandate sont serveur-authoritative.
31. PII et données bénéficiaires suivent divulgation minimale.
32. Presentation représente ; elle ne possède pas.
33. Offline n’est pas automatiquement Error.
34. Snapshot ancien ≠ vérité Live.
35. Refresh conserve le contexte.
36. Back restaure le champ lorsque possible.
37. Wide conserve la hiérarchie, il n’invente pas de KPI.
38. No Orphan Content / Media s’applique.
39. `create_activity` peut être présenté comme `Nouveau programme` pour education.
40. Le contrat technique exact de création Session reste à démontrer avant de figer un endpoint.

---

# 128. Points volontairement ouverts

1. critère exact qui distingue une Activity education visible comme Programme d’une Activity accessoire ;
2. structure API finale d’une section `programmes` après intégration de la séparation structure/continuité ;
3. endpoint/capability définitif de création Session ;
4. profondeur exacte des configurations de récurrence ;
5. vocabulaire exact `inscription`, `demande`, `admission` par Programme ;
6. stratégie exacte de pagination des inscriptions ;
7. synthèses/counts autorisées par owner ;
8. UX finale du calendrier ;
9. carte multi-campus ;
10. représentation détaillée des formats présentiel/distanciel si le domaine les établit ;
11. politique locale des documents et ressources sensibles ;
12. instrumentation Analytics ;
13. microcopy finale empty/calm ;
14. breakpoints exacts du master/detail Programme ;
15. composants Flutter définitifs ;
16. animations finales ;
17. stratégie de visual regression propre à Programmes ;
18. politique exacte de cache/fraîcheur par sous-domaine ;
19. distinction exacte entre Programmes archivés et terminés dans la Presentation ;
20. profondeur de cohorte lorsque Group possède sa propre UX mature.

Aucun de ces points n’autorise à inventer une nouvelle vérité métier par défaut.

---

# 129. Critères de sortie du contrat UX Programmes

Le contrat est suffisamment fermé lorsque l’implémentation peut démontrer :

- N1 reconnaissable comme Programmes ;
- Programme structurel distinct de continuité ;
- Session future / actuelle représentable ;
- Programme sans Session représentable ;
- inscription owner-backed représentable ;
- conditions owner-backed ;
- Form owner-backed ;
- ressources owner-backed ;
- cohortes réelles ;
- Access et Capacity sans duplication ;
- authority / responsibility distinctes ;
- création Programme capability-gated ;
- création Session owner-backed ;
- N1 → Programme N2 → Session N2 → Jour J ;
- N1 → inscription N2 ;
- Now/Piloter/Nous distincts ;
- offline honnête ;
- partial failure local ;
- Back/Resume ;
- Compact/Medium/Wide ;
- text scale ;
- aucune fuite de bénéficiaire ;
- aucun dashboard ERP/LMS.

---

# 130. Critères d’implémentation serveur

Minimum :

- actor Space résolu serveur ;
- viewer Profile explicite ;
- visibilité Activity correcte ;
- responsabilité bornée ;
- aucune autorité issue du filtre ;
- Programme structurel séparé des Journey progressifs ;
- Occurrences projetées comme Sessions sans inventer dates/heures ;
- Journey registration filtrés par authority ;
- beneficiary disclosure minimale ;
- blockers owner-backed ;
- capabilities owner-backed ;
- pagination/coverage honnêtes ;
- `private, no-store` tant que le contrat actuel l’exige ;
- tests IDOR ;
- tests Activity-limited authority ;
- tests Programme sans Session ;
- tests Session future/active ;
- tests registration visible/invisible ;
- tests no beneficiary leak.

---

# 131. Critères Flutter

Flutter doit :

- consommer la projection serveur ;
- ne pas reclasser arbitrairement les Programmes ;
- préserver actor context ;
- préserver responsibility lens ;
- afficher Programmes / Sessions avec langage humain ;
- lire depuis le store local lorsque disponible ;
- représenter freshness ;
- ne pas confirmer localement une admission ;
- restaurer scroll/filtres/profondeur ;
- supporter deep links ;
- supporter states critiques ;
- supporter text scale ;
- ne pas exposer PII non nécessaire ;
- ne pas transformer toute Activity en Card uniforme.

---

# 132. Critères Web

Web doit :

- utiliser le même contrat de vérité ;
- conserver le vocabulaire Programmes ;
- ne pas exposer les noms de modèles dans la navigation ;
- utiliser Wide pour conservation cognitive ;
- ne pas dashboardifier ;
- supporter clavier/focus ;
- conserver query et filtres ;
- rendre les erreurs localement ;
- respecter authority/IDOR serveur.

---

# 133. Tests UX minimum

## Recognition test

En 500 ms :

```text
où suis-je ?
→ dans le Space

quel mode mental ?
→ Programmes

qu’est-ce qui domine ?
→ Programme / Session / conséquence opérationnelle légitime
```

## Blur test

Le dominant doit rester perceptible sans lire tous les textes.

## Competition test

Une Session et un bloc admissions ne doivent pas être deux P3 permanents.

## Deletion test

Supprimer une section doit détériorer une compréhension réelle, sinon elle n’a pas sa place.

## Adaptive test

La sélection survit aux changements de taille.

## Freshness test

Un snapshot ancien ne doit pas devenir une Capacity actuelle.

## Authority test

Un viewer sans `open_requests` ne voit pas les demandes privées.

## Orphan test

Aucun média ou document sans Programme / Session / démarche / finalité.

---

# 134. Scénarios de référence

## 134.1. Programme calme

```text
Comptabilité pratique
Prochaine session · 12 novembre
Tout est prêt.
```

Pas de badge anxiogène.

## 134.2. Programme sans Session

```text
Développement Web
Aucune session planifiée.
```

Le Programme reste dans la structure.

## 134.3. Session à préparer

```text
Comptabilité pratique
Session · 12 novembre

Le formulaire d’inscription n’est pas encore publié.
[ Préparer ]
```

si cette action est owner-backed.

## 134.4. Inscriptions à traiter

```text
Programme Comptabilité
5 demandes nécessitent une décision.
[ Voir les demandes ]
```

La racine ne révèle aucun nom de demandeur.

## 134.5. Demande bloquée

```text
Marie Kalala
Inscription · Comptabilité

Justificatif d’identité manquant.
La décision d’admission attend ce document.
```

si le viewer est autorisé.

## 134.6. Session actuelle

```text
Comptabilité pratique
Session en cours · 08:00–12:00
[ Ouvrir Jour J ]
```

## 134.7. Plusieurs Sessions

```text
3 sessions se déroulent maintenant.
1 demande votre attention.
```

La personne choisit laquelle ouvrir.

## 134.8. Offline

```text
Dernières informations synchronisées · 09:15

Comptabilité pratique
Session · 12 novembre
```

Un compteur d’inscriptions potentiellement obsolète est marqué avec prudence ou omis.

## 134.9. Perte d’autorité

Le viewer garde le Programme visible mais perd la section Admissions.

Aucune donnée privée ancienne ne reste présentée comme actuelle.

---

# 135. Formulation canonique finale

> **Programmes est la porte Métier d’un Space `education`. Elle rend compréhensible et opérable ce que l’organisation fait réellement apprendre : des Programmes durables, leurs Sessions concrètes et les continuités nécessaires à leur préparation et à leur accomplissement. Le Programme reste le contexte humain dominant ; Sessions, inscriptions, conditions, formulaires, ressources, groupes/cohortes, Capacity et Access sont composés depuis leurs propriétaires canoniques sans devenir des modules concurrents ni des vérités dupliquées. Une Session peut devenir Jour J lorsqu’elle est réellement actuelle, tandis que les admissions et autres actions sensibles restent strictement bornées par l’autorité, la confidentialité et la confirmation serveur.**

---

# 136. Formule courte

```text
PROGRAMMES
=
structure pédagogique durable
+
Sessions réelles
+
continuité d’inscription et de préparation
+
profondeurs owner-backed
+
Jour J quand une Session devient actuelle
```

Et :

```text
Programme
≠ Activity affichée telle quelle

Session
≠ nouvelle vérité si Occurrence suffit

Inscription
≠ Journey exposé comme jargon

Programme actif
≠ Programme en cours

Session actuelle
≠ Space Live
```
