# Makolo — Contrat conceptuel gelé de `Jour J` et `Makolo Live`
## Accomplissement actuel, vérité observée, orientation et opération réelle

**Statut :** contrat conceptuel cible, gel de conception  
**Date :** 2026-10-07  
**Portée :** expérience personnelle et Space ; Django/API, Web HTML/Tailwind, Flutter, local-first et Presentation  
**Dépôt officiel :** `TraditionLearningCommunity/makolo`  
**Branche de vérité runtime :** `main`  
**HEAD vérifié pendant la consolidation :** `d5b85ee4c737f09da7d1b2e27f7bae9d14d40131`  
**Nature :** contrat UX, sémantique et de projection ; ce document ne fixe ni modèle de base de données, ni wire JSON définitif, ni pixel design final  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 0. Objet

Ce document ferme le contrat conceptuel de deux réalités d’expérience étroitement liées mais distinctes :

```text
JOUR J
→ Qu’est-ce que je suis effectivement en train de vivre ou d’accomplir maintenant,
  et que dois-je faire pour que cela se passe correctement ?

MAKOLO LIVE
→ Qu’est-ce que Makolo sait être effectivement observé ou en train de se produire
  maintenant dans cette Occurrence ?
```

Le contrat fixe :

- la place de Jour J dans l’architecture d’expérience Makolo ;
- la relation stricte `Occurrence → Jour J → Live` ;
- les contextes acteur et viewer ;
- les perspectives participant et opérateur ;
- les règles d’entrée, de focalisation et de sortie ;
- la structure sémantique d’un Jour J ;
- le rôle de l’action courante et de l’orientation ;
- Access, Placement, Live Queue, Checkpoints, Capacity et Readiness dans la composition ;
- le Scanner comme profondeur opérationnelle focalisée ;
- la définition précise de Makolo Live ;
- la séparation `Realtime ≠ Live` ;
- les états de vérité `planned`, `estimated`, `observed`, `live`, `unknown`, `unavailable` ;
- la fraîcheur et la provenance ;
- l’offline et le local-first ;
- les mutations, confirmations et revalidations d’autorité ;
- les handoffs avec Now, En cours, Métier, Mark, Notifications, Historique et owners ;
- les règles de Presentation Compact / Medium / Wide ;
- les anti-features ;
- les critères de sortie d’une implémentation Mature.

Ce document ne crée pas :

- un modèle `JourJ` ;
- un modèle `DayOfState` ;
- un modèle `LiveState` transverse ;
- une table `LiveFact` générique ;
- une seconde `Occurrence` ;
- un nouveau moteur Operations ;
- un nouveau Readiness ;
- un nouveau système Access ;
- un second système Queue ;
- un second système Placement ;
- un second système Checkpoint ;
- un second Scanner ;
- une nouvelle Permission ;
- une nouvelle autorité locale ;
- un feed temps réel ;
- une archive Jour J ;
- une maquette pixel-perfect ;
- un protocole realtime universel ;
- une structure API définitive.

---

# 1. Règle de vérité

Pour toute implémentation future, la priorité reste :

```text
1. code, migrations et tests du main courant
2. docs/architecture/makolo-domain-blueprint.md
3. contrats UX et docs canoniques pertinents
4. docs/operations-runbook.md
5. état GitHub courant
6. historique / transferts comme contexte
```

Le runtime gagne toujours sur un ancien SHA, une ancienne branche ou une ancienne roadmap.

Le présent gel décrit la cible conceptuelle. Lorsqu’une capacité cible n’existe pas encore dans le runtime, le client doit représenter honnêtement l’indisponibilité au lieu de simuler la capacité.

---

# 2. Sources consolidées

Le contrat a été consolidé à partir des familles de sources suivantes.

## 2.1. Contrats gelés 2026-10-05 / 2026-10-06

- `Makolo_Contrat_Maitre_Now_Ongoing_Decouvrir_Me_2026-10-05.md`
- `Makolo_NowMe_Contrat_Conceptuel_Gele_2026-10-05.md`
- `Makolo_Contrat_Mark_et_Post_Mark_Consolide_2026-10-06.md`
- `Makolo_Contrat_Metier_Space_Gele_2026-10-06.md`
- `Makolo_Contrat_Moi_et_Nous_Gele_2026-10-06.md`
- `Makolo_Contrat_Space_Now_et_Decouvrir_Gele_2026-10-06.md`
- `Makolo_Contrat_Transversal_Mature_Experience_2026-10-06.md`

## 2.2. Contrats d’expérience et Presentation

- `Makolo_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `space-ux-experience-specification.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_Mobile_Visual_Charter_v1.1.md`
- `Makolo_UI_Engineering_Standards_v1.md`
- `Makolo_Presentation_UX_System_Points_1_2_3_2026-10-02-1.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_UX_Now_Contrat_Consolide.md`
- `Makolo_UX_En_Cours_Contrat_Consolide.md`
- `Makolo_UX_Decouvrir_Contrat_Consolide.md`

## 2.3. Contrats local-first et mobile natif

- `Makolo_Local_First_Synchronization_Offline_Execution_Architecture.md`
- `Makolo_Mobile_Analyse_Local_First_et_Noyau_Donnees_2026-09-27.md`
- `mobile-local-data-kernel.md`
- `Makolo_Mobile_Sync_Continuity_Kernel.md`
- `Makolo_Mobile_Bloc_D_Integration_Native_Push_Ingress_Ambient_2026-09-28.md`

## 2.4. Runtime et docs d’implémentation vérifiés

Le runtime courant contient notamment :

```text
operations/occurrence_live.py
operations/space_day_of.py
operations/space_day_of_api.py
scanner/space_context.py
```

et les contrats d’implémentation :

```text
docs/architecture/zs5-space-day-of-live-scanner-mark.md
docs/architecture/ws5-space-day-of-live-scanner-mark-web.md
```

Ces sources confirment notamment l’existence actuelle de :

```text
resolve_occurrence_live(...)
build_space_operator_day_of(...)
build_scanner_context(...)
```

et des profondeurs occurrence-scoped correspondantes.

---

# 3. Invariants non négociables

```text
Profile = personne globale
Space = acteur collectif durable
Assignment = responsabilité
Mandate / Permission = autorité
Membership / Group / Team ≠ autorité implicite
Readiness = projection dérivée
Requirement ≠ Form ≠ Resource ≠ JourneyArtifact ≠ Proof ≠ Credential Trust ≠ AccessCredential
Access = droit
AccessCredential = représentation / secret
AccessUse = observation de l’usage
Capacity = combien ?
Placement = où ?
Waitlist ≠ Live Queue
JourneyStep ≠ Checkpoint opérationnel
Dossier ≠ task manager générique
Project ≠ task manager générique
posséder un document ≠ le retrouver ≠ satisfaire un Requirement
composition ≠ transfert de Permission, Mandate, Access, Payment ou visibilité privée
```

Pour Jour J et Live, trois invariants supplémentaires deviennent centraux :

```text
JOUR J ≠ nouvelle vérité métier
LIVE ≠ REALTIME
OBSERVÉ / LIVE ≠ PLANIFIÉ / ESTIMÉ
```

---

# 4. Position de Jour J dans Makolo

Les surfaces répondent à des questions différentes.

```text
Découvrir
→ Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?

Maintenant
→ Qu’est-ce qui mérite mon / notre attention maintenant ?

En cours / Métier
→ Qu’est-ce qui est déjà engagé, continue ou doit être opéré ?

Moi / Nous
→ Qu’est-ce qui est durablement en place autour de moi / de nous ?

Jour J
→ Qu’est-ce que je suis réellement en train de vivre ou d’accomplir,
  et que dois-je faire maintenant ?

Live
→ Qu’est-ce qui est réellement observé ou en train de se produire maintenant
  dans cette Occurrence ?

Historique
→ Qu’est-ce qui est terminé et reste utile à retrouver ?
```

Jour J n’est donc pas `Now plus urgent`.

Jour J est un changement de mode mental :

```text
préparer / suivre
↓
accomplir dans le réel
```

---

# 5. Définition de Jour J

> **Jour J est la projection UX occurrence-scoped qui concentre, pour un acteur et un viewer légitimes, ce qui est nécessaire pour accomplir correctement une Occurrence devenue suffisamment actuelle : état courant, prochain mouvement utile, orientation, accès, placement, flux opérationnel et vérités Live réellement disponibles.**

Jour J :

```text
≠ Occurrence
≠ Journey
≠ Readiness
≠ Operations
≠ Scanner
≠ Access
≠ Now
≠ En cours
≠ Métier
```

Il compose ces propriétaires lorsque leur vérité est nécessaire à l’accomplissement.

---

# 6. Jour J est une profondeur, pas une porte primaire

Jour J n’est pas un onglet permanent du shell.

Il apparaît parce qu’une Occurrence réelle devient suffisamment actuelle pour justifier un mode d’accomplissement focalisé.

Navigation primaire personnelle :

```text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
```

Navigation primaire Space :

```text
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
```

Jour J s’ouvre depuis le contexte réel ; il ne s’ajoute pas à ces navigations.

---

# 7. Une Occurrence, un Jour J

Invariant :

```text
1 Occurrence canonique
→ 0..1 contexte Jour J courant par perspective/viewer
```

Il n’existe jamais :

```text
Occurrence
+
OccurrenceJourJ copiée
```

L’identité canonique de l’Occurrence reste la référence fondamentale.

Une éventuelle identité technique de projection peut exister pour cache/reconciliation, mais elle ne devient jamais une nouvelle identité métier.

---

# 8. Plusieurs Jour J simultanés

Un Space peut avoir :

```text
Jour J — départ A
Jour J — départ B
Jour J — session C
Jour J — prestation D
```

simultanément.

Donc :

```text
SPACE
≠ JOUR J GLOBAL
≠ LIVE GLOBAL
```

La personne choisit la réalité qu’elle focalise, sauf interruption légitime liée à une conséquence critique réellement établie.

---

# 9. Jour J personnel et Jour J Space

Le même contrat d’accomplissement se décline selon le contexte acteur.

## 9.1. Participant personnel

```text
ACTOR_CONTEXT = Profile
VIEWER = même Profile
PERSPECTIVE = participant
```

La surface répond principalement :

- où dois-je aller ?
- que dois-je faire maintenant ?
- mon Access est-il utilisable ?
- où suis-je placé ?
- suis-je dans une Live Queue ?
- quel Checkpoint vient ensuite ?
- qu’est-ce qui a réellement changé ?

## 9.2. Opération pour un Space

```text
ACTOR_CONTEXT = Space
VIEWER = Profile humain
PERSPECTIVE = opérateur
```

La surface répond principalement :

- qu’est-ce que nous opérons ici ?
- quelle est mon opération primaire maintenant ?
- quel état de Capacity est utile à cette opération ?
- quels flux Access/AccessUse sont légitimement visibles ?
- quelles Queues, Placements ou Checkpoints demandent une action ?
- le Scanner est-il disponible et autorisé ?
- quelle anomalie ou indisponibilité empêche la suite ?

Le Profile reste une personne globale. `participant` ou `opérateur` ne deviennent jamais des rôles globaux du Profile.

---

# 10. Même Occurrence, projections différentes

```text
Occurrence O42
├── Jour J participant-safe
└── Jour J opérateur autorisé
```

Les deux projections :

- ne créent pas deux Occurrences ;
- peuvent exposer des informations différentes ;
- respectent la divulgation minimale ;
- n’ont pas nécessairement les mêmes capabilities ;
- peuvent avoir des compositions visuelles différentes ;
- doivent rester cohérentes avec les mêmes vérités propriétaires.

---

# 11. Entrées légitimes vers Jour J

Jour J peut être atteint depuis :

```text
En cours
Maintenant
Métier
Notification légitime
Deep link
Makolo Mark après résolution légitime
owner Occurrence / Activity
```

Chaque entrée conserve sa provenance de navigation lorsque cela aide Back/Resume.

La provenance ne change jamais l’identité ni l’autorité de l’Occurrence.

---

# 12. En cours → Jour J

Une Continuité peut mener vers Jour J lorsque :

```text
Occurrence liée
+
relation personnelle légitime
+
fenêtre d’accomplissement suffisamment actuelle
+
contexte suffisamment établi
```

La Continuité peut continuer d’exister pendant Jour J.

Après Jour J :

```text
suite pertinente ?
├── oui → En cours continue
└── non → En cours peut sortir
```

Jour J n’est jamais un statut générique de la Continuité.

---

# 13. Maintenant → Jour J

Now peut signaler qu’une Occurrence demande une interaction focalisée.

Exemple :

```text
Départ Lubumbashi → Kolwezi
L’embarquement est ouvert.

[ Ouvrir Jour J ]
```

Now explique pourquoi entrer.

Jour J prend ensuite le relais pour l’accomplissement.

Now ne recopie pas la profondeur Jour J.

---

# 14. Métier → Jour J

Une Business Entry de type Occurrence peut exposer :

```text
[ Ouvrir Jour J ]
```

si l’amont a établi :

```text
Occurrence légitime
+
perspective opérateur
+
autorité suffisante
+
fenêtre Jour J admissible
```

Le client ne déduit pas l’admissibilité depuis `start_at` seul.

---

# 15. Discover ne saute pas directement dans Jour J

Une Possibilité Discover ne devient pas Jour J uniquement parce que son Occurrence est aujourd’hui.

Chaîne correcte :

```text
Possibilité
→ engagement owner-backed
→ relation légitime
→ continuité / accès / participation selon owner
→ Occurrence actuelle
→ Jour J possible
```

Discover n’accorde ni Access ni autorité opérationnelle.

---

# 16. Admission conceptuelle de Jour J

Jour J n’apparaît pas simplement parce qu’une date approche.

Admission cible :

```text
CANONICAL_OCCURRENCE
∧ LEGITIMATE_RELATION
∧ DAY_OF_WINDOW_ESTABLISHED
∧ SUFFICIENT_KNOWLEDGE
∧ VIEWER_CAN_KNOW
∧ PERSPECTIVE_RESOLVED
```

Pour une opération au nom d’un Space, s’ajoute :

```text
EFFECTIVE_AUTHORITY
```

Pour un participant personnel, la relation légitime peut provenir notamment d’une participation, Journey, Access, Checkpoint beneficiary ou autre owner canonique.

Les conditions exactes restent owner-backed.

---

# 17. `DAY_OF_WINDOW` appartient à l’amont

Le client ne calcule jamais :

```text
start_at - 24 h
→ Jour J
```

ou :

```text
heure actuelle > start_at
→ Live
```

sans contrat owner-backed.

La cible conceptuelle exige un résultat résolu par le serveur / owner de l’Occurrence et des opérations.

Le seuil temporel exact peut varier selon :

- Activity ;
- type d’Occurrence ;
- préparation nécessaire ;
- mobilité ;
- fenêtre Access ;
- Checkpoint ;
- rôle opérationnel ;
- autres faits canoniques.

Aucune valeur numérique universelle n’est gelée ici.

---

# 18. Phases d’accomplissement

Le runtime courant expose déjà une phase issue du contexte temporel :

```text
before
arrival
live
after
cancelled
```

Le contrat cible conserve l’idée sémantique suivante :

```text
AVANT L’ACCOMPLISSEMENT
→ préparation immédiate / orientation éventuelle

ARRIVÉE / APPROCHE
→ rejoindre, présenter, attendre, se positionner

ACTUEL / LIVE
→ accomplir ce qui se déroule

APRÈS
→ clôturer le mode Jour J et remettre les conséquences aux owners

ANNULÉ
→ expliquer la conséquence sans simuler une opération Live
```

Les noms wire définitifs restent ouverts.

---

# 19. Phase ≠ vérité Live

Une phase de l’Occurrence et la qualité d’une information sont deux axes différents.

Exemple valide :

```text
Occurrence phase = live
position véhicule = unknown
horaire prévu = planned
porte = observed
```

Donc :

```text
PHASE LIVE
≠ toutes les données sont Live
```

Cette distinction est obligatoire dans la cible Mature.

---

# 20. Structure conceptuelle racine de Jour J

Sans figer les noms JSON :

```text
JOUR J RESPONSE
│
├── ACTOR_CONTEXT                         1
├── VIEWER                                1
├── OCCURRENCE_CONTEXT                    1
├── PERSPECTIVE                           1
├── DAY_OF_AVAILABILITY                   1
├── ACTION_PHASE                          1
├── KNOWLEDGE_CONTEXT                     1
│
├── CURRENT_STATE                         1
├── CURRENT_MOVE                          0..1
├── ORIENTATION                           0..1
│
├── READINESS_CONTEXT                     0..1
├── ACCESS_CONTEXT                        0..1
├── PLACEMENT_CONTEXT                     0..1
├── QUEUE_CONTEXT                         0..1
├── FLOW_CONTEXT                          0..1
├── CAPACITY_CONTEXT                      0..1
├── INCIDENT_CONTEXT                      0..1
│
├── LIVE_CONTEXT                          0..1
├── SCANNER_CONTEXT                       0..1
│
├── CAPABILITIES[]                        0..n
├── OWNER_HANDOFFS[]                      0..n
└── MEDIA_BINDINGS[]                      0..n
```

Ces rôles sont des concepts de projection.

Ils ne créent aucun modèle persistant portant ces noms.

---

# 21. `OCCURRENCE_CONTEXT`

`OCCURRENCE_CONTEXT` répond :

> **Quelle réalité est effectivement en train d’être accomplie ?**

Il doit rester suffisamment petit pour reconnaître l’Occurrence sans recopier tout son owner.

Il peut comprendre conceptuellement :

```text
identity
representation humaine
Activity parent minimale
état owner utile
temporalité pertinente
lieu principal si pertinent
owner handoff
```

Le client ne recompose pas l’Occurrence depuis plusieurs endpoints s’il existe déjà une projection canonique suffisante.

---

# 22. `CURRENT_STATE`

`CURRENT_STATE` répond :

> **Qu’est-ce qui est effectivement vrai pour mon accomplissement maintenant ?**

Il peut être produit à partir de plusieurs owners.

Exemples :

```text
L’embarquement est ouvert.
Votre accès est prêt.
Votre tour n’est pas encore appelé.
Le départ est annulé.
Le contrôle est temporairement indisponible.
```

`CURRENT_STATE` ne devient pas une seconde vérité métier.

---

# 23. `CURRENT_MOVE`

`CURRENT_MOVE` répond :

> **Quel est le mouvement utile maintenant ?**

Il constitue normalement le dominant d’action de Jour J.

Familles conceptuelles possibles :

```text
GO
PRESENT
WAIT
JOIN_QUEUE
MOVE_TO_CHECKPOINT
USE_ACCESS
SCAN
HANDLE_EXCEPTION
CONFIRM
NONE
```

Ces noms ne sont pas des enums backend imposés.

La source canonique et la capability réelle doivent être fournies ou résolues en amont.

---

# 24. Un seul dominant P3

La racine Jour J ne doit pas faire concourir cinq actions principales.

Règle Presentation :

```text
CURRENT STATE / CURRENT MOVE
→ P3

ORIENTATION nécessaire
→ P2/P3

OCCURRENCE IDENTITY
→ P2

PLACEMENT / ACCESS utile
→ P1/P2

metadata / support
→ P1
```

Si plusieurs opérations sont possibles, la surface doit expliquer la hiérarchie plutôt que produire un dashboard de boutons.

---

# 25. `CURRENT_MOVE = NONE`

Jour J peut être actif sans action immédiate.

Exemples :

```text
Aucune action immédiate.
Restez disponible près de la porte B.
Votre préparation est complète ; attendez l’ouverture.
```

Cela n’est pas un état `empty`.

C’est une conclusion locale légitime à l’intérieur d’une Occurrence actuelle.

---

# 26. Orientation

`ORIENTATION` répond à trois questions :

```text
où suis-je ?
où dois-je aller ?
par où passer ?
```

Elle peut utiliser :

- Place ;
- Zone ;
- instructions d’accès ;
- mobilité ;
- itinéraire owner-backed ;
- prochaine zone / porte / quai / salle ;
- hazards et conseils d’action légitimement établis.

La carte est une représentation possible, pas une obligation.

---

# 27. Carte ≠ vérité spatiale

Une carte représente une connaissance spatiale.

Elle ne transforme jamais :

```text
adresse planifiée
```

en :

```text
position observée actuelle
```

Si la dernière observation spatiale est ancienne, l’UX doit pouvoir dire :

> Dernière position connue · 14:02

et non :

> Position actuelle

sans base suffisante.

---

# 28. Access dans Jour J

Jour J peut consommer Access pour répondre :

```text
ai-je le droit pertinent ?
ce droit est-il utilisable maintenant ?
que dois-je présenter ?
```

Toujours :

```text
Access = droit
AccessCredential = représentation / secret
AccessUse = observation d’usage
```

La racine Jour J ne doit pas exposer le secret d’un AccessCredential dans une projection générique.

Une profondeur de présentation QR/credential peut exister si le contrat Access l’autorise.

---

# 29. Access invalide, pending et fenêtre future

Ne jamais fusionner :

```text
PENDING
NOT_YET_VALID
INVALID / UNUSABLE
UNKNOWN
UNAVAILABLE
```

Ces états produisent des conséquences UX différentes.

Exemples :

```text
Votre accès est encore en préparation.
Votre accès est prêt ; sa fenêtre s’ouvre à 13:45.
Votre accès ne peut pas être utilisé pour cette Occurrence.
Impossible de vérifier votre accès pour le moment.
```

---

# 30. Placement

Placement répond :

> **Où suis-je assigné ?**

Il reste distinct de Capacity.

```text
Capacity = combien ?
Placement = où ?
```

Exemples :

```text
Siège 14A
Salle B · table 3
Quai 4 · zone C
```

Un Placement connu peut être affiché offline s’il reste utile, avec indication de fraîcheur si nécessaire.

---

# 31. Waitlist ≠ Live Queue

Invariant absolu :

```text
WAITLIST
→ attendre qu’une place / capacité devienne disponible

LIVE QUEUE
→ attendre son tour après avoir obtenu le droit pertinent
```

Jour J peut représenter une Live Queue.

Il ne renomme jamais une Waitlist en Queue simplement parce que l’Occurrence est proche.

---

# 32. Live Queue

Une Queue peut répondre :

```text
suis-je en attente ?
ma position est-elle connue ?
mon tour est-il appelé ?
où dois-je me présenter ?
```

Lorsque le tour est appelé, ce fait peut devenir P3 :

> **C’est votre tour. Présentez-vous maintenant à Contrôle B.**

Une position de Queue est volatile.

Elle exige donc une fraîcheur adaptée avant d’être présentée comme actuelle.

---

# 33. Checkpoint opérationnel

Toujours :

```text
JourneyStep
≠ Checkpoint opérationnel
```

Jour J peut utiliser les Checkpoints pour représenter :

- ce qui a déjà été observé comme accompli ;
- le prochain Checkpoint ;
- un Checkpoint bloqué ;
- une consigne associée ;
- une responsabilité opérationnelle.

La racine n’a pas besoin de montrer toute la chaîne si seul le prochain mouvement est utile.

---

# 34. `FLOW_CONTEXT`

`FLOW_CONTEXT` est une projection d’accomplissement, pas un nouveau workflow engine.

Il peut regrouper :

```text
completed checkpoints
next checkpoint
queue relation
blocked reason
```

lorsque ces informations sont réellement nécessaires.

Le propriétaire reste Operations / Checkpoints / Queue.

---

# 35. Readiness

Jour J peut consommer Operational Readiness.

Il ne crée jamais :

```text
DayOfReadiness
LiveReadiness
ParticipantReadiness persistante
```

comme nouvelle vérité générique.

Readiness reste une projection dérivée.

La Presentation privilégie la conséquence humaine :

```text
Prêt à embarquer.
```

ou :

```text
Un placement obligatoire manque encore.
```

plutôt qu’un dump de checks techniques.

---

# 36. Capacity

Capacity répond à :

```text
combien ?
```

Dans un Jour J opérateur, elle peut aider à décider ou opérer.

Dans un Jour J participant, elle ne doit apparaître que lorsqu’elle change réellement l’action de la personne.

Le fait que le runtime transporte une Capacity ne force pas Presentation à l’afficher comme KPI.

---

# 37. Incidents

Les incidents sont légitimes dans Jour J seulement lorsqu’un owner ou selector occurrence-scoped les établit.

Le runtime vérifié ne possède pas encore, dans la projection Space Jour J actuelle, un selector incidents suffisamment owner-backed ; il expose donc explicitement :

```text
truth = unavailable
items = []
```

La cible Mature doit préserver la distinction :

```text
aucun incident établi
≠ incidents indisponibles
```

Le client ne peut jamais transformer `unavailable + []` en :

> Aucun incident.

---

# 38. Scanner — place dans Jour J

Le Scanner est une profondeur opérationnelle focalisée de Jour J.

Il n’est pas :

- un onglet principal ;
- un module ERP ;
- un système Access parallèle ;
- une Permission ;
- un simple lecteur QR sans contexte.

Pour une personne dont la responsabilité courante est le contrôle, Scanner peut devenir presque toute l’expérience utile.

---

# 39. Scanner — responsabilité et autorité

Toujours :

```text
ScannerAssignment = responsabilité
Permission / Mandate = autorité
```

Une Assignment seule ne permet pas de scanner.

L’autorité doit être revalidée par le propriétaire avant toute mutation sensible.

---

# 40. Scanner — cycle UX

Cycle de référence :

```text
READY
→ SCAN
→ CHECKING
→ RESULT
   ├── VALID
   ├── INVALID
   ├── UNKNOWN / UNREADABLE
   └── NETWORK / AUTHORITY FAILURE
→ SETTLE
→ NEXT
```

Le scanner doit favoriser :

```text
contexte
→ scan
→ résultat
→ récupération
→ passage suivant
```

et non :

```text
menu
→ sous-menu
→ écran de contrôle
→ scanner
```

---

# 41. Scanner — distinctions obligatoires

```text
échec de lecture
≠ accès invalide

credential lu
≠ accès validé

accès validé
≠ passage confirmé

passage confirmé
→ peut produire un AccessUse selon owner
```

Aucun niveau ne doit être sauté dans la microcopy.

---

# 42. Scanner — caméra et fallback

La caméra est une capacité native / navigateur, pas une vérité métier.

Le runtime Web vérifié utilise une caméra opt-in sur la surface WS5 et conserve des fallbacks image / saisie lorsque le moteur historique les supporte.

Le contrat UX retient :

- demander la caméra au moment utile ;
- expliquer pourquoi elle est nécessaire ;
- ne pas bloquer toute la récupération si la lecture échoue ;
- proposer un fallback seulement s’il existe réellement ;
- ne jamais inventer une validation en cas d’échec technique.

---

# 43. Scanner — confidentialité

Interdits :

- logguer le credential complet ;
- placer un secret dans l’URL ;
- conserver un QR complet dans Analytics ;
- afficher des PII non nécessaires au contrôle ;
- sérialiser AccessCredential dans la projection Jour J générale.

La divulgation doit être minimale et adaptée au contrôle réel.

---

# 44. Définition de Makolo Live

> **Makolo Live est la projection de ce qui est effectivement observé ou suffisamment établi comme étant en train de se produire maintenant dans une Occurrence donnée, pour une perspective et un viewer légitimes.**

Structure :

```text
Occurrence
→ Jour J
   └── Live
```

Donc :

```text
Live
≠ Space entier
≠ page globale de nouveautés
≠ feed
≠ WebSocket
≠ polling
≠ push
≠ chronologie exhaustive
```

---

# 45. Live appartient à Jour J

Live ne devient pas une sixième porte personnelle ni une septième porte Space.

Jour J est le contexte d’accomplissement.

Live est la dimension du réel actuel dans ce contexte.

La profondeur Live peut être ouverte séparément lorsque la quantité ou la nature de l’information justifie une focalisation supplémentaire.

---

# 46. Live intégré vs Live focalisé

Décision de Presentation gelée :

```text
LIVE INTÉGRÉ
→ état Live utile directement dans Jour J
→ comportement par défaut lorsque peu de matière suffit

LIVE FOCALISÉ
→ profondeur dédiée lorsque spatialité, opérations,
  média ou plusieurs changements simultanés exigent plus d’espace
```

Il ne s’agit pas de deux vérités.

```text
même Live owner-backed
→ deux formes de Presentation
```

---

# 47. `Realtime ≠ Live`

Invariant :

```text
REALTIME
→ mécanisme de livraison rapide du changement

LIVE
→ qualité / nature de ce qui est effectivement observé maintenant
```

Un événement reçu en WebSocket peut être :

- planifié ;
- estimé ;
- observé ;
- une invalidation ;
- une notification de changement.

Sa vitesse d’arrivée ne le transforme pas automatiquement en vérité Live.

---

# 48. Pipeline realtime correct

```text
WebSocket / push / polling / refresh
↓
signal de changement
↓
reconciliation autoritative
↓
projection / store
↓
Presentation
```

Chaîne interdite :

```text
push dit « porte B »
↓
UI modifie seule la vérité canonique
↓
« Live : porte B »
```

sans revalidation prévue par le contrat owner.

---

# 49. États de vérité Live

Le contrat conserve les six familles conceptuelles :

```text
planned
estimated
observed
live
unknown
unavailable
```

Elles ne sont pas automatiquement des enums wire universels pour chaque owner.

Elles forment la grammaire conceptuelle que Presentation doit préserver.

---

# 50. `planned`

`planned` signifie :

> une réalité prévue par le owner, mais non encore établie comme observation actuelle.

Exemples :

```text
Départ prévu à 14:00.
Porte prévue : B.
Salle prévue : 204.
```

Interdit :

```text
Départ dans 18 min · En direct
```

si la seule base est `start_at` planifié.

---

# 51. `estimated`

`estimated` signifie :

> une estimation défendable, distincte du plan et de l’observation.

Exemples :

```text
Départ estimé : 14:08.
Arrivée estimée : 17:20.
```

L’origine de l’estimation doit rester owner-backed.

Le client peut recalculer un compte-à-rebours à partir d’une estimation reçue, mais ne peut pas créer l’estimation métier elle-même.

---

# 52. `observed`

`observed` signifie :

> un fait a été constaté / reçu comme observation à un instant déterminé.

Exemple :

```text
Véhicule observé au quai 4 · 13:52.
```

Une observation peut devenir ancienne.

Donc :

```text
observed_at
```

est souvent essentiel à sa compréhension.

---

# 53. `live`

`live` signifie :

> le système possède une base suffisamment fraîche et autoritative pour représenter cette information comme actuelle dans le contexte présent.

Le niveau exact de fraîcheur dépend du owner et du type de donnée.

Il n’existe pas un TTL universel `Live = moins de N secondes`.

---

# 54. `unknown`

`unknown` signifie :

> le système ne connaît pas actuellement la valeur.

Toujours :

```text
unknown
≠ false
≠ zero
≠ none métier
```

Exemple :

> Position actuelle inconnue.

---

# 55. `unavailable`

`unavailable` signifie :

> la source ou capacité nécessaire ne peut actuellement pas être obtenue ou établie.

Exemple :

> Impossible d’obtenir la position actuelle.

Cela ne signifie pas :

> Le véhicule n’a pas de position.

---

# 56. Une page Live peut contenir plusieurs qualités de vérité

Exemple correct :

```text
Départ prévu
14:00                  planned

Départ estimé
14:08                  estimated

Véhicule
Quai 4 · observé 13:52 observed

Embarquement
ouvert                  live

Position après le quai
inconnue                unknown
```

La page ne doit pas peindre tout son contenu du label `Live` sans distinction.

---

# 57. Structure conceptuelle de `LIVE_CONTEXT`

Sans figer le wire :

```text
LIVE_CONTEXT
│
├── OCCURRENCE_REFERENCE                  1
├── PERSPECTIVE                           1
├── COVERAGE_STATE                        1
├── OBSERVED_AT?                          0..1 global snapshot time
│
├── TEMPORAL_FACTS[]                      0..n
├── SPATIAL_FACTS[]                       0..n
├── OPERATIONAL_FACTS[]                   0..n
├── TRANSITIONS[]                         0..n
├── CURRENT_INSTRUCTIONS[]                0..n
├── MEDIA_BINDINGS[]                      0..n
│
├── KNOWLEDGE_CONTEXT                     1
├── CAPABILITIES[]                        0..n
└── OWNER_HANDOFFS[]                      0..n
```

`LIVE_CONTEXT` est une projection.

Il n’est pas un modèle métier.

---

# 58. `COVERAGE_STATE` de Live

La cible distingue conceptuellement :

```text
ESTABLISHED
PARTIAL
UNAVAILABLE
```

## `ESTABLISHED`

Les sources nécessaires pour la lecture Live demandée ont été suffisamment établies.

## `PARTIAL`

Une partie du réel est connue, une autre ne peut pas être établie.

## `UNAVAILABLE`

La lecture Live demandée ne peut pas être obtenue honnêtement.

Cette couverture n’efface pas la qualité de vérité de chaque fait.

---

# 59. Aucun faux vide Live

```text
facts = []
```

n’est pas suffisant pour conclure :

> Rien ne se passe.

Il faut savoir si la couverture est établie.

```text
ESTABLISHED + aucun fait significatif
→ peut produire une lecture calme locale

UNAVAILABLE + []
→ aucune conclusion sur le réel
```

---

# 60. Temporal Live

Le volet temporel peut représenter :

- heure planifiée ;
- estimation ;
- début observé ;
- fin observée ;
- décalage établi ;
- fenêtre actuelle ;
- compte-à-rebours calculable localement à partir d’une base légitime.

Le client peut formater et compter le temps.

Il ne peut pas décider que l’Occurrence a réellement commencé seulement parce que son horloge a atteint `start_at`.

---

# 61. Spatial Live

Le volet spatial peut représenter :

- Place actuelle établie ;
- Zone ;
- porte / quai / salle ;
- position observée ;
- dernière position connue ;
- destination opérationnelle ;
- mobilité ;
- instruction de déplacement.

Une position non observée n’est jamais inventée.

---

# 62. Operational Live

Le volet opérationnel peut représenter, selon owner et autorité :

- état du flux ;
- Checkpoints ;
- Live Queue ;
- Placement ;
- Capacity utile ;
- AccessUse agrégé ou borné ;
- Scanner state ;
- incidents lorsqu’ils sont owner-backed ;
- instructions courantes ;
- prochaines actions légitimes.

La surface ne devient pas un cockpit ERP.

---

# 63. Media Live

Un média ne devient Live que si :

```text
source canonique / légitime
+
contexte Occurrence
+
provenance suffisamment établie
+
utilité d’accomplissement
```

Exemples possibles :

- flux vidéo réellement rattaché à l’Occurrence ;
- image opérationnelle actuelle ;
- audio d’instruction ;
- télémétrie représentée visuellement.

Interdits :

- vidéo décorative ;
- feed média ;
- Story ;
- média non rattaché ;
- média ancien présenté comme direct.

---

# 64. No Orphan Media s’applique pleinement

Tout média Jour J / Live doit aider au moins à :

```text
RECOGNIZE
UNDERSTAND
ORIENT
ESTABLISH
ACT
```

Sinon il ne doit pas occuper l’attention de la surface.

---

# 65. Live n’est pas une timeline exhaustive

Un journal exhaustif :

```text
13:31 événement A
13:32 événement B
13:33 événement C
...
```

n’est pas automatiquement une bonne UX Live.

Jour J/Live doit prioriser :

```text
ce qui est vrai maintenant
+
ce qui vient de changer si cela modifie l’action
+
ce que je dois faire
```

L’historique appartient à une profondeur propriétaire lorsqu’il est utile.

---

# 66. Delta Live

Une transition devient visible lorsqu’elle aide à comprendre ou agir.

Exemples :

```text
Porte B → Porte D
Départ 14:00 → estimé 14:20
Votre tour vient d’être appelé
Checkpoint 2 terminé
Contrôle suspendu
```

Un changement technique sans conséquence humaine n’a pas besoin de devenir un événement fort.

---

# 67. Interruption légitime

Une vérité critique peut temporairement interrompre la lecture normale si elle modifie réellement l’action.

Exemples :

- annulation ;
- appel de Live Queue ;
- changement de porte qui exige un déplacement ;
- révocation d’un Access nécessaire ;
- incident opérationnel affectant la personne ;
- perte d’autorité pendant une opération sensible.

Cette capacité d’interruption est exceptionnelle.

Elle ne devient pas une mécanique de rétention ou de notification permanente.

---

# 68. Notification ≠ Live

Une Notification peut signaler :

> Votre porte a changé.

Mais :

```text
Notification
= canal

Live Fact / Transition
= vérité owner-backed
```

La notification doit conduire vers une profondeur légitime qui revalide la vérité courante.

---

# 69. Deep link Jour J / Live

Pipeline :

```text
AUTHENTICATE
↓
RESOLVE ACTOR
↓
VERIFY AUTHORITY / LEGITIMATE RELATION
↓
RESOLVE OCCURRENCE
↓
RESOLVE CURRENT PROJECTION
↓
OPEN JOUR J / LIVE
```

Un ancien deep link ne garantit pas que Jour J existe encore.

Après fin ou révocation :

- résoudre privacy-safe ;
- proposer le contexte owner encore légitime si possible ;
- ne jamais rouvrir un faux Jour J historique.

---

# 70. Back

Back doit revenir au contexte précédent autant que possible :

```text
Jour J
→ Back
→ Now / En cours / Métier / owner précédent
```

avec restauration :

- sélection ;
- scroll ;
- responsabilité ;
- Space ;
- filtres ;
- carte ;
- autre contexte légitime.

Jour J ne réinitialise pas la surface d’origine par principe.

---

# 71. Resume

Après arrière-plan ou interruption :

```text
conserver Jour J
→ rafraîchir / réconcilier discrètement
→ préserver l’action si elle reste légitime
```

Si le contexte n’est plus valide :

```text
ancienne action
→ retirée
→ nouvelle vérité expliquée
```

Ne pas remettre arbitrairement l’utilisateur à l’accueil.

---

# 72. Refresh

Préférer :

```text
contenu actuel
+ indicateur discret
→ reconciliation
→ contenu actualisé
```

à :

```text
contenu
→ écran vide
→ skeleton
→ contenu
```

La réalité opérationnelle déjà connue reste utile pendant le refresh tant qu’elle est présentée honnêtement.

---

# 73. Local-first de Jour J

Le client installé peut conserver :

- Occurrence déjà acquise ;
- timing planifié ;
- Place ;
- Access connu selon sécurité ;
- Placement connu ;
- ressources nécessaires ;
- dernière projection Jour J ;
- dernier snapshot Live autorisé ;
- état local de navigation ;
- carte / viewport ;
- brouillons ou opérations locales réellement supportées.

Mais :

```text
LOCAL SNAPSHOT
≠ vérité actuelle garantie
```

---

# 74. Offline Jour J

Une perte réseau ne détruit pas automatiquement Jour J.

Exemple :

```text
Départ Lubumbashi → Kolwezi
14:00
Porte B
Siège 14A

Hors connexion
Dernière mise à jour : 13:42
```

peut rester utile.

Mais aucun élément ancien ne doit porter une apparence `Live` sans base suffisante.

---

# 75. Offline Live

Règle stricte :

```text
OFFLINE
→ peut montrer la DERNIÈRE INFORMATION CONNUE
→ ne peut pas affirmer le PRÉSENT non vérifié
```

Préférer :

> Dernière information connue · 13:42

à :

> En direct

lorsque la fraîcheur ne peut plus être garantie.

---

# 76. Compte-à-rebours local

Le client peut calculer localement :

```text
durée = cible temporelle connue - horloge locale
```

Cela est un calcul de Presentation.

Mais :

```text
countdown arrivé à zéro
≠ confirmation que l’événement réel a commencé
```

Après zéro, le client doit attendre ou obtenir une vérité owner-backed appropriée.

---

# 77. Mutations dans Jour J

Toute mutation significative suit le cycle transversal :

```text
PREPARED
→ LOCAL / QUEUED si permis
→ SENDING
→ SENT
→ AWAITING_CONFIRMATION si nécessaire
→ CONFIRMED
```

avec branches :

```text
FAILED
CONFLICT
```

La microcopy reste humaine.

---

# 78. Aucun faux succès

Interdits :

```text
scan lu
→ « passage confirmé »
```

sans confirmation owner.

```text
réservation queued
→ « place réservée »
```

sans confirmation Capacity.

```text
Access affiché localement
→ « accès valide maintenant »
```

si une revalidation est requise.

---

# 79. Actions sensibles

Sont typiquement sensibles :

- valider un Access ;
- créer un AccessUse ;
- affecter une Capacity concurrente ;
- appeler / déplacer une Queue selon owner ;
- affecter un Placement ;
- confirmer un Checkpoint ;
- modifier un état opérationnel ;
- traiter un incident ;
- agir au nom d’un Space.

Le client ne devient jamais autoritatif par simple présence du bouton.

---

# 80. TOCTOU

Cas normal à supporter :

```text
GET Jour J
→ capability scan visible
→ Mandate révoqué
→ POST scan
→ refus owner-backed
→ reconciliation
```

L’UX doit répondre :

1. ce qui n’a pas été fait ;
2. ce qui a été conservé ;
3. ce que la personne peut faire maintenant.

---

# 81. Autorité et perspective

```text
PERSPECTIVE
≠ AUTHORITY
```

Le fait d’être présenté comme `opérateur` ou de sélectionner une responsabilité `Contrôle` ne donne aucun droit.

La perspective réduit et organise la lecture.

L’autorité détermine les actions et données réellement accessibles.

---

# 82. Minimal disclosure

Une projection Jour J participant ne révèle pas automatiquement :

- liste des autres participants ;
- Access des autres ;
- incidents internes ;
- Capacity interne détaillée ;
- Assignment des opérateurs ;
- ScannerAssignment ;
- données CRM ;
- informations privées du Space.

Une projection opérateur ne donne pas automatiquement accès à toutes les données du Space.

---

# 83. `HIDDEN ≠ UNAVAILABLE ≠ EMPTY`

Toujours distinguer :

```text
HIDDEN
→ non divulgué dans ce scope

UNAVAILABLE
→ source/capacité non disponible

EMPTY
→ source établie et aucune donnée
```

Le client ne doit jamais révéler l’existence d’une donnée sensible via un état d’erreur trop précis.

---

# 84. Personnalité UX de Jour J

Jour J est :

```text
réalité courante
+
accomplissement
```

Sa densité est :

```text
moyenne / focalisée
```

Il doit donner l’impression :

> **Makolo sait où j’en suis et m’aide à faire le prochain mouvement réel.**

Pas :

> Voici tous les modules associés à votre Occurrence.

---

# 85. Personnalité UX de Live

Live est :

```text
réel observé
+
changement utile
+
strictement ce qui compte pour l’accomplissement
```

Sa densité peut être plus élevée que Jour J, mais uniquement parce que l’action réelle le justifie.

```text
Live = dense mais pertinent
≠ dense parce que professionnel
```

---

# 86. Shell immersif

Jour J, Live, Scanner, QR et carte opérationnelle peuvent réduire :

- le Header ;
- la bottom navigation ;
- le rail ;
- le chrome secondaire.

Cette immersion ne crée pas une nouvelle application.

Le contexte doit rester récupérable :

```text
Makolo
+
acteur courant
+
Occurrence courante
```

---

# 87. Header Jour J

Le header secondaire doit rester humain.

Exemples :

```text
←  Départ Lubumbashi → Kolwezi
←  Session Comptabilité
←  Rendez-vous Visa
```

Éviter :

```text
Occurrence #983
Operations Live
CapacityPool
```

comme titre principal.

---

# 88. Compact — participant

Le Golden de référence conserve :

```text
CURRENT STATE / ACTION   P3
ORIENTATION              P2/P3
OCCURRENCE IDENTITY      P2
PLACEMENT                P1/P2
metadata                 P1
```

Sur Compact :

- une colonne ;
- action-first ;
- peu de chrome ;
- Access / Placement / Queue seulement lorsque pertinents ;
- carte en mode ou profondeur si nécessaire ;
- pas de dashboard miniaturisé.

---

# 89. Medium — participant

À partir d’un espace suffisant, action et spatialité peuvent coexister.

Structure candidate existante :

```text
action pane min  ~360 dp
gutter            24 dp
map min           ~420 dp
```

Le seuil reste un candidat de Presentation, pas une vérité métier.

Si textScale ou largeur utile ne permet plus une bonne lecture, le split retombe en single-pane.

---

# 90. Wide — opérateur

Le workspace opérateur répond à trois questions :

```text
CONTEXT
→ où / pour quoi j’opère ?

PRIMARY OPERATION
→ que fais-je maintenant ?

SUPPORT
→ quelle information secondaire m’aide ?
```

Structure candidate existante :

```text
context      ~220–240 dp
operation    ~480 dp min
support      ~260–300 dp
gutters      ~24 dp
```

Un troisième pane n’est utilisé que s’il réduit réellement la friction.

---

# 91. Wide n’autorise pas la dashboardification

Interdit :

```text
écran large
→ afficher automatiquement
  Capacity + Queue + Scanner + Incidents + Analytics + Finance + Team
```

La largeur adapte la géométrie.

Elle ne change ni la vérité ni la priorité cognitive.

---

# 92. Scanner Compact

Sur téléphone terrain, Scanner peut occuper presque tout l’écran :

```text
Occurrence / contexte
↓
zone caméra
↓
résultat
↓
action de settlement si nécessaire
↓
Scanner le suivant
```

Les informations de support doivent être accessibles sans polluer la boucle principale.

---

# 93. Feedback scanner

Un résultat doit être perceptible :

- visuellement ;
- textuellement ;
- via `aria-live` / équivalent accessible ;
- éventuellement par haptique lorsque cela améliore l’usage terrain.

La couleur seule ne suffit jamais.

Un son ne doit pas être la seule confirmation.

---

# 94. Animations et mouvement

Les animations Jour J / Live doivent servir :

- continuité ;
- changement d’état ;
- localisation ;
- confirmation ;
- orientation de l’attention.

Interdits :

- pulsation permanente pour faire « live » ;
- animation décorative continue ;
- déplacement qui empêche de lire ;
- auto-scroll agressif lors des updates realtime.

---

# 95. Insertion realtime et stabilité visuelle

Une nouvelle donnée ne doit pas casser :

- le focus ;
- le scroll ;
- la sélection ;
- l’opération en cours ;
- la caméra ;
- le formulaire d’exception.

Une vérité critique peut être remontée explicitement.

Les changements secondaires sont réconciliés sans saut cognitif.

---

# 96. Search dans Jour J

Jour J n’a pas besoin d’une recherche globale par défaut.

Une recherche locale / spécialisée est légitime seulement si l’opération l’exige, par exemple :

- retrouver une personne autorisée dans un contrôle ;
- retrouver un placement ;
- retrouver une ressource opérationnelle ;
- rechercher un incident owner-backed.

La recherche reste permission-first et scoped à l’Occurrence.

---

# 97. Filtres dans Jour J

Les filtres sont exceptionnels sur participant.

Sur opérateur, ils peuvent aider à réduire une collection opérationnelle réelle.

Exemples possibles :

```text
Queue active
Checkpoint
zone
état de contrôle
```

Ils ne deviennent jamais une taxonomie de modèles backend.

---

# 98. Historique

Jour J ne devient pas une archive infinie.

Après fin :

```text
Occurrence owner
AccessUse
Proof / Evidence si owner légitime
Analytics
Historique
En cours si suite
```

conservent les conséquences utiles.

Aucun `JourJHistory` transverse n’est créé.

---

# 99. Fin naturelle de Jour J

Lorsque l’Occurrence sort de sa fenêtre d’accomplissement :

```text
Jour J
→ se ferme naturellement
```

Une courte confirmation terminale peut exister si elle aide à comprendre :

> Trajet terminé.

Mais la surface ne doit pas rester un monde actif indéfiniment.

---

# 100. Annulation

Une Occurrence annulée ne devient pas un faux Jour J Live.

La surface doit expliquer :

- ce qui est annulé ;
- la conséquence ;
- ce qui reste valide ;
- la prochaine profondeur utile.

Exemple :

```text
Départ annulé.
Votre billet reste consultable dans Mes accès.
[ Voir les options disponibles ]
```

uniquement si ces handoffs sont réellement supportés.

---

# 101. Après Jour J → En cours

Si une suite pertinente subsiste :

```text
Occurrence terminée
→ Continuité reste En cours
```

Exemples :

- résultat à recevoir ;
- Proof à établir ;
- paiement final ;
- retour ;
- démarche post-Occurrence ;
- livraison ultérieure.

Jour J ne décide pas seul que l’objectif humain global est terminé.

---

# 102. Après Jour J → Historique

Si aucune suite n’existe :

```text
Occurrence terminée
→ profondeur owner / Historique
```

Le passage n’est pas un archivage de la page Jour J elle-même.

---

# 103. Relation avec Now après fin

Une conséquence post-Occurrence peut produire une nouvelle Situation Now.

Exemples :

- incident à traiter ;
- paiement échoué ;
- pièce à envoyer après l’événement ;
- résultat reçu nécessitant décision.

Ce n’est pas Jour J qui reste ouvert pour porter cette conséquence.

---

# 104. Relation avec Mark

Mark peut :

- retrouver une Occurrence ;
- continuer vers un Jour J légitime ;
- préparer une action owner-backed ;
- contribuer une information si le owner l’accepte.

Mais :

```text
Mark
≠ owner Jour J
≠ moteur Live
≠ authority
```

Un handoff Mark vers Jour J revalide l’Occurrence, le contexte acteur et l’autorité.

---

# 105. Relation avec Moi / Nous

`Moi` et `Nous` restent des surfaces durables.

Ils ne doivent pas absorber Jour J.

Exemples :

```text
Access durable
→ Moi / owner Access

responsabilité Scanner durable
→ Nous / owner Assignment selon contexte

contrôle réel du départ de 14 h
→ Jour J / Scanner
```

---

# 106. Owner mapping

| Besoin Jour J / Live | Owner canonique principal |
|---|---|
| identité et timing de l’Occurrence | Activity / Occurrence |
| Readiness | Readiness / Operations projection |
| droit d’entrée | Access |
| représentation du droit | AccessCredential |
| usage/passage | AccessUse |
| combien | Capacity |
| où | Placement |
| attendre son tour | Live Queue |
| parcours opérationnel | Checkpoints / Operations |
| scanner | Scanner + Access authority |
| lieu / zone | Geography / Occurrence Place |
| mobilité / orientation | Spatiotemporal owners / projections |
| incidents | owner Operations/Incident lorsque disponible |
| média Live | owner média / source canonique réelle |
| historique | owners + History projection |
| analytics | Analytics owner |

La table ne crée aucun owner transverse.

---

# 107. Runtime courant — ce qui existe réellement

Au HEAD vérifié, le runtime possède :

```text
resolve_occurrence_live(...)
```

avec perspectives actuelles :

```text
participant
operator
space
```

et composition notamment de :

- timing ;
- Access ;
- Placement ;
- Queue ;
- Capacity ;
- spatial ;
- Operational Readiness ;
- next action ;
- Checkpoints pour les perspectives opérateur ;
- Scanner state pour les perspectives opérateur.

---

# 108. Runtime courant — phase

Le runtime mappe actuellement le contexte temporel :

```text
UPCOMING  → before
SOON      → arrival
ACTIVE    → live
ENDED     → after
CANCELLED → cancelled
```

Cette mécanique est une vérité d’implémentation actuelle.

Le contrat UX ne doit pas extrapoler à partir de cette phase des observations qui n’existent pas.

---

# 109. Runtime courant — Space Jour J

Le runtime possède :

```text
build_space_operator_day_of(...)
```

et l’endpoint :

```text
GET /api/v1/operations/occurrences/<id>/day-of/
```

La projection actuelle :

- exige une Occurrence portée par un Space ;
- exige une perspective `space` ou `operator` ;
- n’ouvre Jour J que pour les phases `arrival` ou `live` ;
- compose Readiness, Capacity, Access control, Queue, Placement, Checkpoints, Live et Scanner ;
- ne crée aucun état Jour J persistant.

---

# 110. Runtime courant — Live

Le runtime possède :

```text
GET /api/v1/operations/occurrences/<id>/live/
```

Il ne possède pas encore un enum universel de vérité `planned|estimated|observed|live|unknown|unavailable` pour chaque sous-champ.

Presentation doit donc :

```text
préserver ce qui est réellement exposé
```

et non inventer une précision absente du owner.

---

# 111. Runtime courant — Scanner

Le runtime Space Scanner expose un contexte occurrence-scoped et vérifie l’autorité canonique.

Le POST canonique de scan générique n’existe pas encore pour toutes les Activities.

Le runtime peut donc annoncer :

```text
next_scan.state = unavailable
reason = no_owner_scan_endpoint_for_activity
```

Cible UX : montrer l’indisponibilité honnêtement, jamais simuler un contrôle.

---

# 112. Runtime courant — Incidents

La projection Space Jour J actuelle ne possède pas de selector Incident occurrence-scoped complet.

Elle marque les incidents indisponibles.

Le contrat cible garde donc Incident comme capacité légitime future, mais n’autorise aucune interface à afficher :

> Aucun incident

à partir du runtime actuel.

---

# 113. Runtime courant — Realtime

Le Web WS5 vérifié n’ajoute actuellement aucun polling Live.

La surface fonctionne en server-rendered + refresh/back/forward.

Le contrat cible autorise plus tard :

```text
WebSocket
push
polling
```

mais uniquement comme mécanismes de livraison et après définition endpoint par endpoint.

---

# 114. Cible Mature ≠ obligation de réécrire le runtime

Le gel conceptuel peut être plus riche que le runtime.

Mais la future implémentation doit avancer par composition :

```text
owners existants
→ projections plus explicites
→ Presentation
```

et non :

```text
nouveau domaine JourJ
→ copie Operations
→ copie Access
→ copie Queue
→ copie Live
```

---

# 115. Responsabilités serveur

Le serveur / les owners doivent établir :

- l’Occurrence ;
- le contexte acteur ;
- le viewer ;
- la relation légitime ;
- la perspective ;
- la fenêtre Jour J ;
- l’autorité et les capabilities ;
- le Current State ;
- le Current Move / next action lorsque calcul métier nécessaire ;
- les vérités Access ;
- Queue ;
- Placement ;
- Capacity ;
- Checkpoints ;
- Readiness ;
- Live facts ;
- provenance/fraîcheur métier ;
- couverture partielle / indisponible ;
- owner handoffs.

---

# 116. Responsabilités client

Le client peut :

- adapter Compact / Medium / Wide ;
- formater date, heure, durée et distance ;
- calculer un countdown depuis une base déjà légitime ;
- choisir carte / texte / média selon metadata ;
- conserver scroll, sélection, carte, profondeur ;
- afficher snapshot local ;
- gérer sync state ;
- afficher pending / offline ;
- demander caméra / localisation selon capacité ;
- produire feedback haptique / visuel accessible ;
- préserver l’ancre lors d’updates.

Le client ne peut jamais :

- décider qu’une Occurrence est Jour J depuis l’horloge seule ;
- transformer `planned` en `live` ;
- déduire une Permission depuis Assignment ;
- déclarer un Access valide sans owner ;
- confirmer un AccessUse avant confirmation ;
- inventer une position ;
- inventer un incident vide ;
- reranker les opérations par heuristique locale opaque.

---

# 117. Responsabilités Presentation

Presentation décide :

- quoi rendre dominant ;
- quelle information secondaire cacher derrière une profondeur ;
- quand la carte aide ;
- quand Live doit rester intégré ;
- quand Live mérite une profondeur focalisée ;
- comment représenter `unknown`, `unavailable`, `stale` ;
- comment adapter la géométrie ;
- comment conserver la personnalité de surface.

Presentation ne possède jamais la vérité.

---

# 118. Identité et reconciliation

Les updates Jour J / Live doivent pouvoir :

```text
ADD
UPDATE
REMOVE
INVALIDATE
MARK_STALE
```

sans reconstruire l’identité par :

- titre ;
- heure ;
- image ;
- proximité de texte.

L’identité owner de l’Occurrence est la base naturelle.

Une identité opaque de sous-projection peut être fournie lorsque nécessaire.

---

# 119. Pas d’append aveugle Live

Une nouvelle réponse Live n’est pas automatiquement ajoutée comme un nouvel événement à la fin.

Il faut :

```text
état acquis
+
nouvel état
→ reconciliation
```

Le Live courant peut remplacer ou invalider une ancienne valeur.

---

# 120. États UX racine de Jour J

Jour J n’a normalement pas d’`empty root` lorsque son admission est correcte.

États utiles :

```text
CONTENT
CONTENT + SYNCING
CONTENT + OFFLINE
PARTIAL
UNAVAILABLE localement
PERMISSION LOST
CANCELLED
ENDED / HANDOFF
ERROR localisé
```

Une absence totale de projection peut mener à une résolution privacy-safe plutôt qu’à un écran vide.

---

# 121. Loading

Sans snapshot :

```text
loading initial
→ structure minimale
→ contenu ou résolution
```

Avec snapshot :

```text
contenu actuel
+ refresh discret
```

La priorité est de garder l’utilisateur orienté dans une situation potentiellement terrain.

---

# 122. Error locale avant globale

Exemples :

```text
carte indisponible
→ action principale reste visible

Capacity indisponible
→ Scanner peut rester utilisable si indépendant

média Live indisponible
→ instructions textuelles restent disponibles
```

Une panne locale ne devient pas une panne globale si le reste reste honnêtement utilisable.

---

# 123. Permission lost

Si l’autorité disparaît :

```text
opération sensible
→ retirée / refusée
```

La surface peut encore montrer un contexte minimal si celui-ci reste légitimement visible.

Elle ne doit ni conserver un bouton dangereux ni dévoiler pourquoi une ressource privée existe si cela serait une fuite.

---

# 124. Accessibilité

Jour J / Live doit couvrir :

- textScale élevé ;
- navigation clavier sur Web ;
- focus visible ;
- lecteurs d’écran ;
- message textuel en plus de la couleur ;
- résultat Scanner annoncé ;
- alternative à une information purement cartographique ;
- alternative au son/haptique ;
- actions tactiles suffisamment grandes ;
- ordre de focus cohérent dans les splits ;
- réduction des mouvements.

---

# 125. Performance

La performance doit privilégier l’action réelle :

- lire localement ce qui est déjà acquis ;
- rafraîchir sans effacer ;
- ne pas précharger toutes les Occurrences du Space ;
- ne pas charger tous les participants si non nécessaires ;
- borner les collections opérationnelles ;
- ne pas introduire du polling arbitraire ;
- éviter les requêtes par item côté client ;
- charger média/carte seulement quand utiles.

---

# 126. Anti-features Jour J

Jour J ne doit pas devenir :

- une fiche Occurrence enrichie ;
- un dashboard ;
- une todo list ;
- un cockpit ERP ;
- une timeline exhaustive ;
- un centre de notifications ;
- une navigation par modèles backend ;
- un écran de tous les participants ;
- une page KPI ;
- un écran « tout Operations » ;
- une archive permanente ;
- un prétexte pour du média ;
- une vue qui transforme l’heure planifiée en réalité actuelle ;
- un endroit où Assignment devient Permission.

---

# 127. Anti-features Live

Makolo Live ne doit pas devenir :

- un feed en direct ;
- un réseau social ;
- un mur d’événements ;
- un stream média obligatoire ;
- une page de télémétrie générique ;
- un WebSocket affiché ;
- un badge « live » sur toute donnée récente ;
- une animation permanente ;
- une vérité créée côté client ;
- une duplication d’Operations.

---

# 128. Exemple participant — transport

```text
Départ Lubumbashi → Kolwezi

Embarquement ouvert
Porte B · Quai 4

[ Me guider ]

Billet
Prêt ✓

Place
14A

Votre tour
Pas encore appelé

Live
Véhicule observé au quai 4 · 13:52
Départ estimé 14:08
```

Hiérarchie :

```text
embarquement / mouvement courant
→ dominant

orientation
→ immédiatement actionnable

Access / Placement
→ soutien

Live
→ explique le réel utile
```

---

# 129. Exemple participant — éducation

```text
Session de laboratoire
Biologie · Groupe B

Vous pouvez entrer maintenant.
Salle L2

[ Ouvrir mon accès ]

Votre poste
Table 6

Ensuite
Contrôle de sécurité

Live
La session a commencé.
Dernière mise à jour 09:03
```

Le contrat n’est pas spécifique au transport.

---

# 130. Exemple participant — service / rendez-vous

```text
Rendez-vous biométrie

Présentez-vous au guichet 4.

Accès
Convocation disponible

File
Vous êtes en attente.
Position connue : 3

[ Voir où aller ]
```

La Live Queue reste distincte d’une Waitlist préalable de rendez-vous.

---

# 131. Exemple opérateur — transport

```text
Départ Lubumbashi → Kolwezi
14:00 · Porte B

OPÉRATION COURANTE
Contrôle d’embarquement

[ Scanner ]

Support
47 passages confirmés
5 en attente dans la Queue
Capacity utile : 52 / 55

Live
Embarquement ouvert
Quai 4
```

Les chiffres apparaissent parce qu’ils servent l’opération, pas pour remplir l’écran.

---

# 132. Exemple Scanner

```text
Départ Lubumbashi → Kolwezi
Porte B

[ zone caméra ]

✓ Accès valide
Jean Kabeya
Siège 14A

[ Confirmer le passage ]
```

Après confirmation owner-backed :

```text
✓ Passage confirmé

[ Scanner le suivant ]
```

Avant confirmation, le premier résultat ne doit pas être formulé comme un AccessUse déjà enregistré.

---

# 133. Exemple Live partiel

```text
Départ Lubumbashi → Kolwezi

Embarquement
ouvert                    live

Porte
B · observée 13:55        observed

Départ
estimé 14:08              estimated

Position véhicule
indisponible              unavailable
```

La page reste utile malgré une couverture partielle.

---

# 134. Exemple offline

```text
Départ Lubumbashi → Kolwezi

Hors connexion
Dernière mise à jour : 13:42

Porte B
Siège 14A
Billet disponible sur cet appareil

Dernière position connue du véhicule
Quai 4 · 13:40
```

Interdit :

```text
● LIVE — Quai 4
```

si la connexion perdue empêche de garantir cette actualité.

---

# 135. Matrice participant / opérateur

| Dimension | Participant | Opérateur |
|---|---|---|
| centre | accomplir son expérience | accomplir l’opération autorisée |
| Actor Context | Profile | Space |
| Viewer | Profile | Profile |
| Access | personnel | agrégé / contrôlé selon autorité |
| Placement | personnel | plans/assignments selon scope |
| Queue | mes entrées | queues occurrence-scoped |
| Capacity | seulement si utile à la personne | support opérationnel possible |
| Checkpoints | prochain / accomplis utiles | état opérationnel autorisé |
| Scanner | généralement non | profondeur majeure si autorisé |
| incidents | seulement conséquences personnelles | selon owner et scope |
| Live | participant-safe | operational-safe |

---

# 136. Matrice des qualités temporelles

| Qualité | Signification | Peut être affichée offline ? |
|---|---|---|
| planned | prévu par owner | oui, comme prévu |
| estimated | estimation owner-backed | oui, avec âge si nécessaire |
| observed | constaté à un instant | oui, comme dernière observation connue |
| live | actuel suffisamment établi | seulement tant que le contrat de fraîcheur le permet |
| unknown | inconnu | oui |
| unavailable | source/capacité indisponible | oui |

Offline ne modifie pas la vérité source ; il modifie ce que le client peut encore garantir comme actuel.

---

# 137. Matrice de Presentation

| Surface | Compact | Medium | Wide |
|---|---|---|---|
| Jour J participant | immersive action-first | action + spatial si utile | contenu borné, espace respirant |
| Live participant | intégré par défaut ; profondeur si besoin | action + Live/spatial | jamais dashboard |
| Jour J opérateur | opération primaire ; scanner possible | opération + support | workspace multi-pane si utile |
| Scanner | plein écran focalisé | caméra + support | caméra + résultat + support borné |
| Live opérateur | faits strictement utiles | split possible | support opérationnel structuré |

---

# 138. Goldens existants à préserver

La Golden Specification possède déjà :

```text
G10 — Jour J participant / Compact
G11 — Jour J participant / Medium
G12 — Jour J opérateur / Wide
```

Le présent contrat ne remplace pas ces Goldens.

Il leur donne le contrat sémantique complet.

---

# 139. États Golden à couvrir

Au minimum :

```text
planned
estimated
observed
live
unknown
unavailable
offline
partial coverage
queue waiting
queue called
access pending
access not-yet-valid
access unavailable
scan valid
scan invalid
scan unreadable
network failure
authority failure
cancelled
ended
```

Tous n’ont pas besoin d’un Golden distinct ; une fixture déterministe doit néanmoins permettre de les exercer.

---

# 140. Tests de reconnaissance

En environ 500 ms, un écran Jour J doit permettre de reconnaître :

```text
1. quelle Occurrence je suis en train d’accomplir
2. ce qui est vrai maintenant
3. ce que je dois faire / attendre
4. où aller si la spatialité compte
```

Un écran opérateur doit en plus permettre de reconnaître :

```text
5. pour quel Space / contexte j’opère
6. quelle opération est dominante
```

---

# 141. Blur test

En floutant le texte :

- le dominant d’action reste-t-il perceptible ?
- la carte/caméra ne vole-t-elle pas le P3 sans raison ?
- les panneaux de support restent-ils secondaires ?
- Live ne devient-il pas visuellement un feed ?

---

# 142. Deletion test

Pour chaque bloc Jour J :

> Si je le supprime, l’accomplissement réel devient-il plus difficile, moins sûr ou moins compréhensible ?

Si non, le bloc est suspect.

---

# 143. Competition test

Deux éléments ne doivent pas prétendre simultanément être l’action principale.

Exemple suspect :

```text
[ Scanner ]
[ Voir Capacity ]
[ Ouvrir Queue ]
[ Voir participants ]
[ Gérer incidents ]
```

avec le même poids visuel.

---

# 144. Tests d’autorité

Couvrir au minimum :

- participant légitime ;
- outsider ;
- Assignment seule ;
- Permission valide ;
- Permission révoquée après GET ;
- Activity-limited ;
- Space-wide sans Permission owner spécifique ;
- Occurrence étrangère ;
- donnée Hidden ;
- action visible puis refus TOCTOU ;
- absence de fuite IDOR.

---

# 145. Tests de vérité Live

Couvrir :

```text
planned ne devient pas live
estimated reste estimated
observed affiche observed_at
unknown ≠ false
unavailable ≠ empty
offline ne conserve pas un faux badge Live
realtime update passe par reconciliation
position absente n’est pas inventée
phase live avec données partielles reste partielle
```

---

# 146. Tests Scanner

Couvrir :

- caméra refusée ;
- credential illisible ;
- credential inconnu ;
- Access invalide ;
- Access valide ;
- passage non encore confirmé ;
- passage confirmé ;
- double scan ;
- retry idempotent lorsque owner le permet ;
- réseau perdu ;
- autorité révoquée ;
- mauvais Activity ;
- mauvaise Occurrence ;
- aucun secret dans logs / URL / analytics.

---

# 147. Tests local-first

Couvrir :

- Jour J ouvert puis perte réseau ;
- dernier snapshot affiché ;
- Live dégradé en dernière information connue ;
- retour réseau ;
- reconciliation ;
- changement de porte pendant offline ;
- action sensible non confirmée offline ;
- changement de Profile ;
- changement d’acteur Profile → Space ;
- reprise après background.

---

# 148. Tests adaptatifs

Couvrir :

```text
Compact → Medium
Medium → Wide
Wide → Compact
rotation
window resize
textScale 1.0 / 1.3 / 1.6
```

Préserver autant que possible :

- Occurrence ;
- current move ;
- sélection ;
- caméra state raisonnablement récupérable ;
- map position ;
- profondeur ;
- scroll ;
- résultat non encore settled ;
- contexte acteur.

---

# 149. Critères de sortie serveur Mature

Une implémentation serveur crédible de Jour J / Live doit démontrer :

- Occurrence canonique unique ;
- acteur et viewer explicites ou déductibles sans ambiguïté ;
- perspective résolue serveur ;
- admission Jour J owner-backed ;
- aucune heuristique client d’entrée ;
- Readiness dérivée, non dupliquée ;
- Access / AccessCredential / AccessUse séparés ;
- Capacity / Placement séparés ;
- Waitlist / Live Queue séparées ;
- JourneyStep / Checkpoint séparés ;
- current move owner-backed ;
- knowledge/freshness suffisants ;
- partial/unavailable représentables ;
- capabilities viewer-scoped ;
- autorité revalidée sur mutations ;
- privacy-safe failures ;
- aucun secret dans projection générale ;
- sortie naturelle après fin ;
- aucune migration `JourJ` ou `LiveState` sans besoin canonique nouveau démontré.

---

# 150. Critères de sortie Web Mature

Le Web doit démontrer :

- routes occurrence-scoped ;
- deep links sûrs ;
- Jour J focalisé ;
- Live issu du serveur ;
- aucune déduction `Date.now() → Live` ;
- refresh sans flash destructeur ;
- Back/forward cohérents ;
- scanner accessible ;
- caméra permission-aware ;
- résultats textuels ;
- TOCTOU géré ;
- aucun dashboard Space ;
- aucun historique Jour J parallèle.

---

# 151. Critères de sortie Flutter Mature

Flutter doit démontrer :

- lecture depuis le store local lorsque possible ;
- snapshot Jour J / Live viewer-scoped ;
- freshness visible ;
- offline honnête ;
- deep links / push ingress revalidés ;
- lifecycle background/resume ;
- caméra / QR / permissions natives ;
- carte seulement lorsque pertinente ;
- haptics accessibles et non indispensables ;
- pending ≠ confirmed ;
- aucune autorité reconstruite localement ;
- isolation Profile / actor / Space ;
- adaptive conservation ;
- aucune fuite de credentials.

---

# 152. Critères de sortie Presentation

Presentation doit démontrer :

- une personnalité Jour J reconnaissable ;
- un dominant P3 unique ;
- Live sans faux temps réel ;
- distinction planned/estimated/observed/live/unknown/unavailable ;
- participant-safe vs opérateur autorisé ;
- action-first sur Compact ;
- action + spatialité sur Medium lorsque utile ;
- workspace opérateur sur Wide seulement lorsque justifié ;
- Scanner focalisé ;
- erreurs locales ;
- offline qui conserve la grammaire ;
- absence de feed / dashboardification ;
- respect No Orphan Media.

---

# 153. Décisions conceptuelles gelées

Le présent document gèle :

1. `Jour J` est une profondeur d’accomplissement occurrence-scoped.
2. `Makolo Live` appartient à Jour J.
3. Un Space n’est jamais globalement Jour J ou Live.
4. Même Occurrence, projections participant et opérateur différentes.
5. `ACTOR_CONTEXT` personnel = Profile ; opération Space = Space ; viewer = Profile humain.
6. L’admission Jour J est résolue en amont ; le client ne la déduit pas de l’heure.
7. Phase de l’Occurrence et qualité de vérité Live sont deux axes distincts.
8. `Realtime ≠ Live`.
9. `planned`, `estimated`, `observed`, `live`, `unknown`, `unavailable` doivent rester distinguables.
10. Jour J possède un `CURRENT_STATE` et un `CURRENT_MOVE` focalisés.
11. Jour J compose Access, Placement, Queue, Checkpoints, Capacity et Readiness sans les posséder.
12. Waitlist ≠ Live Queue.
13. JourneyStep ≠ Checkpoint.
14. Access ≠ AccessCredential ≠ AccessUse.
15. Scanner est une profondeur focalisée, pas une autorité.
16. Credential lu ≠ passage confirmé.
17. Incidents indisponibles ≠ aucun incident.
18. Live peut être intégré ou focalisé selon besoin de Presentation.
19. Offline conserve la dernière connaissance, jamais un faux présent.
20. Jour J se ferme naturellement ; il ne devient pas une archive.
21. Les conséquences retournent à leurs owners / En cours / Now / Historique selon le réel.
22. Compact/Medium/Wide changent la géométrie, pas la vérité.
23. Live ne devient ni feed, ni télémétrie générique, ni média social.
24. Aucun nouveau domaine persistant n’est justifié par ce contrat seul.

---

# 154. Points volontairement ouverts

Restent ouverts avant implémentation finale :

1. wire JSON définitif de Jour J ;
2. wire JSON définitif de Live ;
3. nom technique exact de `DAY_OF_AVAILABILITY` ;
4. seuils exacts d’entrée Jour J par owner / verticale ;
5. besoin éventuel d’une projection participant `/day-of/` séparée du resolver Live existant ;
6. protocole realtime endpoint par endpoint ;
7. WebSocket vs polling vs push selon surface ;
8. TTL / freshness policy précise par type de fait ;
9. représentation exacte des mixed truth states ;
10. structure finale Incident occurrence-scoped ;
11. généralisation éventuelle du POST Scanner au-delà de l’adaptateur Event courant ;
12. stratégie offline des opérations Scanner sensibles ;
13. profondeur exacte des cartes et itinéraires ;
14. composants Flutter définitifs ;
15. animations finales ;
16. microcopy finale ;
17. politique média Live détaillée ;
18. instrumentation Analytics exacte ;
19. seuils finaux des breakpoints Golden ;
20. noms finaux des états Presentation `LIVE intégré / focalisé`.

Aucun de ces points ne justifie à lui seul un modèle persistant supplémentaire.

---

# 155. Formulation finale — Jour J

> **Jour J est la profondeur Makolo d’accomplissement réel attachée à une Occurrence devenue suffisamment actuelle. Il ne copie ni l’Occurrence ni ses domaines : il compose, pour un acteur et un viewer légitimes, le contexte, l’état courant, le prochain mouvement utile, l’orientation, l’Access, le Placement, la Live Queue, les Checkpoints, la Readiness et les opérations nécessaires pour avancer dans le monde réel. Une même Occurrence peut produire une lecture participant-safe et une lecture opérateur autorisée sans devenir deux réalités. Jour J est immersif lorsque l’action l’exige, se ferme naturellement lorsque l’Occurrence cesse d’être actuelle et remet ensuite les conséquences à leurs owners, à En cours, à Now ou à l’Historique selon ce qui reste réellement à accomplir.**

---

# 156. Formulation finale — Makolo Live

> **Makolo Live est la dimension de Jour J qui représente uniquement ce qui est effectivement observé ou suffisamment établi comme se produisant maintenant dans l’Occurrence. Live ne signifie ni “reçu récemment”, ni “prévu pour maintenant”, ni “mis à jour par WebSocket”. Makolo distingue le planifié, l’estimé, l’observé, le Live, l’inconnu et l’indisponible ; il conserve la provenance et la fraîcheur nécessaires pour ne jamais transformer une copie locale, une estimation ou une heure planifiée en faux présent. Live peut rester intégré dans Jour J ou devenir une profondeur focalisée lorsque la spatialité, les opérations ou un média réellement owner-backed l’exigent.**

---

# 157. Principe final

```text
JOUR J
= accomplir le réel

LIVE
= représenter honnêtement le réel observé maintenant

REALTIME
= transporter plus vite les changements
```

Donc :

```text
MAKOLO NE SIMULE PAS LE PRÉSENT.
MAKOLO AIDE À AGIR DANS LE PRÉSENT QU’IL PEUT RÉELLEMENT ÉTABLIR.
```

Et toujours :

> **Makolo marche pour vous.**

> **Pas le plaisir de rester. Le plaisir d’avancer.**
