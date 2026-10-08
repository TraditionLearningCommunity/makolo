# Makolo — Space Métier `transport_operator` / **Transport**
## Contrat UX consolidé — N1, N2/N3, hiérarchie, représentations, états, adaptive, local-first et handoffs

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence pour l’archétype Space `transport_operator`  
**Porte visible :** **Transport**  
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
transport_operator
```

Le libellé visible primaire est :

```text
Transport
```

Le document ne redéfinit pas le domaine Transport.

Il ne remplace pas :

- `Activity` ;
- `Occurrence` ;
- `TransportService` ;
- `TransportRoute` ;
- `TransportDeparture` ;
- `Vehicle` ;
- `Capacity` ;
- `Access` ;
- `Placement` ;
- `Journey` ;
- `Readiness` ;
- `Permission` ;
- `Mandate` ;
- Jour J ;
- Makolo Live ;
- Now ;
- Piloter ;
- Nous.

Il répond à une question différente :

> **Comment rendre le monde Transport du Space immédiatement compréhensible, opérable et professionnel dans Makolo, sans exposer la taxonomie backend et sans fabriquer un mini-ERP ?**

---

# 1. Sources de cadrage

Ce contrat est dérivé principalement des documents fournis dans le projet :

- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md` ;
- `space-ux-experience-specification.md` lorsque ses décisions sont présentes dans le runtime ou reprises par les contrats consolidés ;
- `Makolo_Architecture_Experience_Mobile_Consolidee.md` ;
- `Makolo_Mobile_Visual_Charter_v1.1.md` ;
- `Makolo_Application_Behavior_Interaction_System_v1.1.md` ;
- `Makolo_UI_Engineering_Standards_v1.md` ;
- `Makolo_Mobile_Sync_Continuity_Kernel.md` ;
- `Makolo_Local_First_Synchronization_Offline_Execution_Architecture.md` ;
- `mobile-local-data-kernel.md` ;
- `Makolo_UX_Now_Contrat_Consolide.md` ;
- `Makolo_UX_En_Cours_Contrat_Consolide.md` ;
- `Makolo_UX_Presentation_Golden_Specification_v1.md` ;
- le contrat Jour J / Makolo Live consolidé du projet ;
- le code, migrations et tests du dépôt `TraditionLearningCommunity/makolo`.

Lors de la rédaction, la vérité runtime vérifiée est :

```text
main@d5b85ee4c737f09da7d1b2e27f7bae9d14d40131
```

La PR suivante est également pertinente mais n’est pas encore `main` au moment du gel :

```text
#496
SPACE MÉTIER — continuité et structure sur main W2
branch: fix/space-metier-continuity-main
head: a39e9a6da5f2d22c01cb215455a97418c6ccc456
```

Cette PR sépare déjà les collections structurelles `routes` / `vehicles` des sections de continuité.

Le présent document **confirme conceptuellement cette séparation**, sans considérer la PR comme déjà livrée.

---

# 2. Statuts utilisés dans ce document

Les formulations sont classées selon quatre statuts implicites :

### GELÉ

Décision déjà soutenue par les contrats canoniques et retenue comme invariant UX.

### CIBLE UX

Décision de présentation nécessaire pour matérialiser correctement Transport.

### RUNTIME OBSERVÉ

Comportement vérifié dans le code courant.

### OUVERT

Détail dont le choix final doit être validé pendant l’implémentation visuelle ou après preuve runtime.

Le document évite de transformer les éléments `OUVERT` en nouvelles vérités métier.

---

# 3. Place de Transport dans le shell Space

La navigation Space reste :

```text
Maintenant | Découvrir | [Makolo Mark] | Transport | Nous
```

`Transport` remplace le libellé abstrait `Métier` pour l’archétype `transport_operator`.

La porte répond à :

> **Qu’est-ce que nous faisons réellement exister, préparer, exécuter et délivrer dans notre activité de transport ?**

Transport est la **surface durable de travail** du Space.

Il n’est pas la surface de l’urgence actuelle.

Il n’est pas la surface d’analyse stratégique.

Il n’est pas l’identité du collectif.

Il n’est pas Jour J.

---

# 4. Frontières avec les autres portes

## 4.1. Transport ≠ Maintenant

`Maintenant` sélectionne ce qui mérite attention **maintenant**.

`Transport` conserve le monde de travail même quand rien ne demande une intervention immédiate.

Exemple :

```text
Transport
→ Route Lubumbashi → Kolwezi
→ Départ demain 08:00
→ Véhicule Bus 18
```

peut exister sans Situation Now.

Si aucun véhicule n’est affecté au départ imminent :

```text
Maintenant
→ Départ 14 h
→ Aucun véhicule affecté
→ Préparer
```

et simultanément :

```text
Transport
→ même départ dans son contexte métier
```

Une même vérité peut être projetée dans plusieurs surfaces.

---

## 4.2. Transport ≠ Découvrir

`Découvrir` répond :

> Qu’est-ce qui pourrait aider le Space à avancer ?

`Transport` répond :

> Qu’est-ce que nous opérons réellement ?

Une desserte candidate peut apparaître dans Découvrir.

Une route réellement portée par le Space appartient à Transport.

---

## 4.3. Transport ≠ Nous

`Nous` porte :

- identité collective ;
- équipe ;
- responsabilités ;
- autorité ;
- relations ;
- Trust ;
- paramètres institutionnels appropriés.

`Transport` porte :

- services ;
- routes ;
- départs ;
- véhicules ;
- lieux ;
- continuité d’exploitation ;
- profondeurs opérationnelles légitimes.

Une personne ou une équipe peut être montrée dans un détail Transport lorsqu’elle contribue à l’action.

Cela ne transfère pas Team, Mandate ou Permission à Transport.

---

## 4.4. Transport ≠ Piloter

`Transport` aide à faire.

`Piloter` aide à prendre du recul.

Donc :

```text
Départ 14 h
→ Transport
```

mais :

```text
ponctualité par route sur 90 jours
→ Piloter
```

Transport ne remplit pas sa racine avec des KPI pour paraître professionnel.

---

## 4.5. Transport ≠ Jour J

Transport contient la continuité avant et autour de l’Occurrence.

Jour J prend le relais lorsque l’Occurrence devient suffisamment actuelle selon la décision serveur appropriée.

```text
Transport
→ Départ
→ Jour J
   └── Live
```

Jour J reste une profondeur spécialisée.

---

# 5. Personnalité de la surface

La personnalité UX gelée de Transport est :

> **activité réelle + maîtrise opérationnelle**

Elle doit donner une impression de :

- continuité ;
- ordre ;
- activité réelle ;
- préparation ;
- mouvement ;
- maîtrise ;
- contexte spatial et temporel lorsqu’ils comptent.

Elle ne doit pas donner l’impression de :

- cockpit ;
- ERP ;
- tableau de bord KPI ;
- logiciel de dispatch générique ;
- feuille Excel maquillée ;
- application de tracking permanente ;
- feed de départs ;
- task manager.

---

# 6. Densité

La densité Transport est :

```text
moyenne à élevée
```

mais seulement lorsque le travail le justifie.

La racine doit rester lisible en quelques secondes.

La densité augmente progressivement en N2 et N3.

Principe :

```text
N1
→ reconnaître le monde Transport

N2
→ comprendre une réalité métier

N3
→ accomplir une action précise
```

---

# 7. Contexte acteur visible

Le viewer reste une personne.

```text
VIEWER = Profile
ACTOR_CONTEXT = Space
```

Exemple :

```text
Avatar = Jean
Space courant = Mulykap
Porte = Transport
```

L’Avatar ne devient jamais le logo de Mulykap.

Le contexte doit permettre de savoir sans ambiguïté :

- pour quel Space on agit ;
- dans quelle porte on se trouve ;
- quelle responsabilité éventuelle borne la lecture.

---

# 8. Responsibility filter

La surface peut proposer une lentille de responsabilité :

```text
Toutes mes responsabilités
Exploitation
Contrôle
Administration
...
```

Cette lentille :

- réduit la projection ;
- améliore la pertinence ;
- préserve le contexte ;
- ne crée jamais d’autorité.

Invariant :

```text
Assignment = responsabilité
Mandate / Permission = autorité
```

Changer le filtre ne doit jamais révéler une donnée non autorisée.

---

# 9. Architecture cognitive générale

Transport possède deux familles visibles complémentaires :

```text
TRANSPORT
│
├── CONTINUITÉ D’EXPLOITATION
│   └── ce qui est préparé, prévu ou en train de se dérouler
│
└── STRUCTURE TRANSPORT
    └── ce qui rend durablement cette exploitation possible
```

La distinction est conceptuelle.

L’interface n’affiche pas nécessairement les titres techniques :

```text
« Continuité »
« Structure »
```

Les intitulés visibles doivent être naturels.

---

# 10. Structure métier transport

La structure Transport peut comprendre, lorsque réellement supportée :

```text
Routes
Services
Véhicules
Lieux
```

Le runtime vérifié possède explicitement :

- `TransportRoute` ;
- `TransportService` ;
- `Vehicle` ;
- relations de route vers `Place` ;
- `TransportDeparture` rattaché à une `Occurrence`.

Les structures restent visibles même lorsqu’elles ne sont pas « en cours ».

Une Route active ne devient pas une continuité simplement parce qu’elle est active.

Un Véhicule actif ne devient pas une continuité simplement parce qu’il est utilisable.

---

# 11. Continuité d’exploitation

Les réalités temporelles/opérationnelles peuvent comprendre :

```text
Aujourd’hui
Départs actifs
Prochains départs
À préparer
Bloqués
Terminés
```

mais ces catégories ne sont **pas six onglets universels obligatoires**.

La composition doit dépendre des faits disponibles et de la manière la plus lisible de les présenter.

Le document préfère une racine où :

```text
Aujourd’hui
```

est le premier territoire temporel lorsqu’il contient quelque chose d’utile.

Puis :

```text
À venir
```

ou :

```text
Prochains départs
```

Puis la structure durable.

---

# 12. N1 — objectif

N1 doit répondre rapidement à quatre questions :

```text
Où suis-je ?
→ Transport de ce Space

Qu’est-ce qui se passe dans notre exploitation ?
→ départs utiles à comprendre

Qu’est-ce qui structure cette exploitation ?
→ routes / services / véhicules / lieux

Que puis-je légitimement ouvrir ou créer ?
→ capabilities serveur
```

---

# 13. N1 — composition de référence Compact

La composition de référence candidate est :

```text
┌──────────────────────────────┐
│ Makolo                 Avatar│
│ Mulykap ▾                    │
│                              │
│ Transport                    │
│ Toutes mes responsabilités ▾ │
│                    Rechercher│
│                              │
│ AUJOURD’HUI                  │
│ 14:00                        │
│ Lubumbashi → Kolwezi         │
│ Préparation                  │
│ Véhicule affecté             │
│                              │
│ 16:30                        │
│ Lubumbashi → Likasi          │
│ À préparer                   │
│                              │
│ PROCHAINS DÉPARTS            │
│ Demain · 08:00               │
│ Kolwezi → Lubumbashi         │
│                              │
│ TRANSPORT                    │
│ Routes                    8 ›│
│ Véhicules                12 ›│
│ Services                  3 ›│
│ Lieux                    15 ›│
│                              │
│ Maintenant Découvrir Mark    │
│ Transport Nous               │
└──────────────────────────────┘
```

Cette maquette textuelle est une composition conceptuelle, pas un pixel design.

---

# 14. N1 — ordre de priorité

La priorité de lecture est :

```text
P3  réalité opérationnelle dominante si elle existe
P2  identité métier / section active / prochain départ significatif
P1  contexte temporel, route, état, véhicule, capacité utile
P0  metadata secondaire
```

Aucun P3 artificiel ne doit être créé si rien ne mérite cette force visuelle.

Transport peut être calme.

---

# 15. N1 — « Aujourd’hui »

`Aujourd’hui` n’est pas un dashboard.

Il est un regroupement humain de départs dont la date locale pertinente correspond au jour opérationnel courant.

Il peut contenir :

- départs à préparer ;
- départs proches ;
- départs dans leur fenêtre Jour J ;
- départs déjà en cours ;
- départs terminés récemment si cela reste utile à l’exploitation du jour.

La vérité de phase ne doit pas être inventée par le client.

Le client présente les faits résolus par les owners/projections.

---

# 16. N1 — « Départs actifs »

Un départ actif ne doit pas automatiquement dominer l’écran.

La présence de plusieurs départs simultanés est normale.

Exemple :

```text
5 départs actifs
```

n’implique pas :

```text
Space entier = Live
```

Chaque départ reste une Occurrence distincte.

Jour J et Live restent occurrence-scoped.

---

# 17. N1 — « Prochains départs »

Cette section doit rester temporellement intelligible.

Elle privilégie :

- date ;
- heure ;
- origine → destination ;
- état de préparation utile ;
- éventuellement véhicule ;
- éventuellement capacité si elle influence l’action.

Elle ne montre pas toutes les métadonnées du départ.

---

# 18. N1 — « À préparer »

Une entrée apparaît ici lorsqu’un fait owner-backed établit qu’une préparation reste pertinente.

Exemples possibles :

- Occurrence en brouillon ;
- préparation opérationnelle non achevée ;
- véhicule non affecté si cela est réellement exigé ;
- condition bloquante établie ;
- autre état owner-backed réellement supporté.

La Presentation ne doit pas déduire elle-même une obligation depuis l’absence d’un champ sans contrat métier.

---

# 19. N1 — « Bloqués »

`Bloqué` est fort.

Il ne doit être utilisé que lorsqu’une transition réellement pertinente est empêchée.

Attente ≠ blocage.

Inconnu ≠ blocage.

Non observé ≠ blocage.

Indisponible ≠ blocage.

---

# 20. N1 — Terminés

Les départs terminés ne doivent pas envahir la racine.

La racine peut montrer :

- une petite continuité du jour ;
- un accès vers l’historique pertinent ;
- une confirmation récente utile.

Elle ne doit pas devenir une archive chronologique infinie.

---

# 21. Structure — Routes

La section Routes répond à :

> **Quelles liaisons notre activité Transport fait-elle durablement exister ?**

Une Route est une structure durable.

Elle ne doit pas être présentée comme « En cours » simplement parce que `active=true`.

Une entrée Route peut montrer :

```text
Lubumbashi → Kolwezi
3 arrêts
Active
```

si ces faits sont réellement disponibles.

Le titre humain prime sur le code technique.

---

# 22. Structure — Services

Un TransportService relie une Activity Transport à une Route.

La surface peut le représenter comme :

```text
Service Lubumbashi ↔ Kolwezi
Route Lubumbashi → Kolwezi
Route · Bus
```

ou une formulation équivalente fondée sur les faits réels.

Le terme `TransportService` n’est pas destiné au titre visible.

Si le produit utilise simplement le nom de l’Activity comme nom humain du service, cette identité doit être conservée.

---

# 23. Structure — Véhicules

Véhicules est une collection structurelle.

Une entrée peut montrer :

```text
Bus 18
Autocar
50 places
```

selon les données réellement autorisées.

Le nombre de places physiques du Vehicle ne doit pas être confondu avec la `CapacityPool` vendable d’un départ.

Invariant :

```text
Vehicle.passenger_capacity
≠ Capacity disponible de l’Occurrence
```

---

# 24. Structure — Lieux

Les lieux peuvent être utiles pour :

- arrêts ;
- origine ;
- destination ;
- embarquement ;
- zones opérationnelles ;
- orientation Jour J.

Ils ne doivent pas devenir une rubrique obligatoire si le runtime ne possède pas une collection transport proprement projetable.

Le contrat visible autorise donc :

```text
Lieux
```

mais sa matérialisation dépend du read model réellement disponible.

---

# 25. Représentation d’un départ en N1

L’unité visuelle recommandée est un **row opérationnel riche**, pas une grande Card marketing.

Exemple :

```text
14:00
Lubumbashi → Kolwezi
Quai / lieu pertinent si connu
Véhicule : Bus 18
État : Prêt
```

ou, si un problème existe :

```text
14:00
Lubumbashi → Kolwezi
Véhicule à affecter
```

Le row doit être entièrement ouvrable lorsque l’utilisateur possède la capacité de voir le détail.

---

# 26. Informations prioritaires d’un départ

Ordre candidat :

```text
1. heure / temporalité
2. origine → destination ou identité humaine équivalente
3. état utile à l’action
4. véhicule si pertinent
5. capacité si pertinente
6. metadata secondaire
```

L’ordre exact peut varier si l’Activity possède un libellé humain plus fort que l’origine/destination.

---

# 27. Capacity en N1

Capacity ne doit apparaître que si elle aide réellement à comprendre ou agir.

Exemples légitimes :

```text
42 / 50
```

si la donnée représente effectivement une capacité owner-backed pertinente.

Interdit :

```text
84 %
```

si le pourcentage masque la distinction entre :

- capacité physique ;
- capacité vendable ;
- réservations ;
- droits d’accès ;
- personnes effectivement présentes.

---

# 28. Vérité temporelle

Les temps visibles doivent conserver leur nature :

```text
planned
estimated
observed
live
unknown
unavailable
```

Une heure planifiée reste planifiée.

Un départ marqué `scheduled` n’est pas automatiquement « à l’heure ».

Un départ commencé n’est pas automatiquement géolocalisé.

---

# 29. Carte en Transport

La carte est permise lorsqu’elle répond à une question réelle :

```text
où est la route ?
où sont les arrêts ?
où dois-je opérer ?
quel lieu concerne ce départ ?
```

Elle ne doit pas apparaître automatiquement parce qu’une adresse existe.

En N1, la carte est une **vue alternative ou contextualisée**, pas nécessairement un territoire permanent.

---

# 30. Recherche Transport

La recherche porte sur le monde Transport visible du Space.

Exemples :

```text
Kolwezi
Bus 18
route Lubumbashi
Départ 14 h
```

La recherche ne doit pas exiger que l’utilisateur connaisse :

```text
Occurrence
Activity
TransportService
CapacityPool
```

---

# 31. Filtres Transport

Les filtres visibles doivent être humains.

Exemples possibles :

```text
Aujourd’hui
À venir
Actifs
À préparer
Route
Lieu
Véhicule
Responsabilité
```

Ils n’exposent pas directement les enums backend.

Le serveur reste responsable de la visibilité.

---

# 32. Tri

Transport privilégie un ordre compréhensible.

Pour les départs :

```text
temps significatif
+
stabilité
```

est préférable à un score opaque.

Une anomalie importante peut être mise en avant via Now ou une représentation owner-backed, mais la racine Transport ne doit pas réordonner arbitrairement tout le monde selon une urgence locale inventée.

---

# 33. Création contextuelle

La porte Transport peut proposer, selon capabilities :

```text
Nouveau départ
Nouvelle route
Nouveau véhicule
```

Le document source fixe explicitement cette grammaire.

Aucun méga-menu :

```text
+ Créer
→ Activity
→ Occurrence
→ Capacity
→ Access
→ Journey
...
```

n’est permis comme grammaire primaire.

---

# 34. Placement de l’action de création

CIBLE UX :

Sur Compact, l’action de création doit être disponible sans concurrencer le Makolo Mark central.

Préférence :

- action de header contextuelle ; ou
- bouton compact au niveau du territoire concerné ; ou
- menu contextuel Transport simple lorsque plusieurs créations sont légitimes.

Éviter un FAB générique permanent « + ».

Le Makolo Mark reste le geste transversal d’intention/orchestration.

---

# 35. Création et Permission

La présence de l’action est guidée par les capabilities serveur.

Son absence dans l’UI n’est pas une barrière de sécurité.

Toute création est revalidée côté serveur.

Choisir le Space ou la responsabilité n’accorde aucune Permission.

---

# 36. Makolo Mark → Transport

Le Mark peut recevoir :

> « Ajoute un départ demain à 8 h. »

Il peut ensuite :

```text
EXPRIMER
→ COMPRENDRE
→ CLARIFIER
→ HANDOFF Transport owner
```

Le Mark ne contourne jamais :

- Permission ;
- validation métier ;
- données nécessaires ;
- owner correct.

---

# 37. N2 — principe général

N2 représente **une réalité Transport reconnaissable**.

Titres légitimes :

```text
Départ Lubumbashi → Kolwezi
Route Lubumbashi → Kolwezi
Bus 18
Service Lubumbashi–Kolwezi
```

Titres déconseillés :

```text
Occurrence #...
TransportRoute #...
Vehicle object
Activity transport
```

Le détail humain prime sur l’identité technique.

---

# 38. N2 Départ — objectif

Le détail Départ doit répondre à :

```text
De quel départ parle-t-on ?
Quand ?
Où ?
Est-il suffisamment préparé ?
Quel véhicule ?
Quelle capacité utile ?
Que puis-je faire maintenant ?
Est-il entré en Jour J ?
```

---

# 39. N2 Départ — composition conceptuelle

```text
DÉPART
│
├── IDENTITY
│   ├── origine → destination / label
│   └── référence opérationnelle si utile
│
├── TIMING
│   ├── date
│   ├── heure
│   └── nature de vérité
│
├── ROUTE / SERVICE
├── VEHICLE
├── PREPARATION / READINESS
├── CAPACITY
├── PLACEMENT si utile
├── ACCESS / voyageurs selon autorité
├── CHECKPOINTS / contrôle selon contexte
├── INCIDENTS selon disponibilité
│
├── PRIMARY_ACTION
├── OWNER_HANDOFFS
└── JOUR_J_HANDOFF si admissible
```

Ce schéma est une grammaire UX, pas un modèle de données.

---

# 40. N2 Départ — préparation

La préparation compose les faits owner-backed nécessaires.

Elle peut montrer :

```text
Véhicule
Capacité
Lieu d’embarquement
Instructions
Readiness opérationnelle
```

selon ce qui existe.

Elle ne crée pas un `DepartureReadinessStatus` parallèle si Readiness sait déjà établir la réponse.

---

# 41. N2 Départ — véhicule

Si le véhicule est affecté :

```text
Véhicule
Bus 18
50 places
```

Si aucun véhicule n’est affecté et que cette absence est réellement pertinente :

```text
Véhicule
À affecter
```

Le détail peut proposer :

```text
[Affecter un véhicule]
```

uniquement si la capability existe.

---

# 42. N2 Départ — Capacity

Capacity répond :

> Combien ?

Le bloc Capacity doit clairement représenter la bonne quantité.

Il ne doit pas fusionner :

- places physiques ;
- places vendables ;
- réservations ;
- Access ;
- présence observée.

Une profondeur Capacity peut être ouverte si nécessaire.

---

# 43. N2 Départ — voyageurs

Le mot visible peut être :

```text
Voyageurs
Participants
Passagers
```

selon la grammaire métier retenue.

Mais la visibilité est strictement authority-scoped.

Le fait qu’une personne opère le départ ne garantit pas l’accès à toutes les données privées des voyageurs.

Divulgation minimale obligatoire.

---

# 44. N2 Départ — Access

Access signifie droit.

AccessCredential signifie représentation/secret.

AccessUse signifie observation d’usage/passage.

Le détail Départ ne doit jamais les fusionner.

Exemple :

```text
42 accès valides
38 passages observés
```

peuvent être deux vérités différentes si le runtime les établit réellement.

---

# 45. N2 Départ — contrôle

Contrôle peut ouvrir une profondeur opérationnelle appropriée.

Lorsque le Scanner est autorisé, le handoff doit être direct.

L’opérateur ne doit pas traverser des écrans Finance ou Analytics pour atteindre le scan d’un départ actuel.

---

# 46. N2 Départ — incidents

L’absence de données Incident ne doit pas être convertie automatiquement en :

```text
Aucun incident
```

si la couverture owner n’est pas établie.

Distinguer :

```text
aucun incident connu
```

et :

```text
incidents indisponibles / non couverts
```

selon le contrat réel.

---

# 47. N2 Départ → Jour J

Le handoff vers Jour J apparaît lorsque le serveur établit que l’Occurrence est admissible à Jour J.

Le client ne calcule pas ce seuil avec l’heure seule.

Action visible possible :

```text
[ Ouvrir Jour J ]
```

ou :

```text
Jour J
Maintenant
```

selon Presentation.

---

# 48. Jour J intégré dans la continuité Transport

Jour J ne crée pas un deuxième départ.

```text
Départ
→ Jour J
```

reste la même Occurrence.

Le retour depuis Jour J doit restaurer :

- le détail du départ ;
- la sélection ;
- le scroll de N1 ;
- les filtres ;
- le contexte Space ;
- la responsabilité sélectionnée.

---

# 49. Makolo Live

Live est une profondeur de Jour J.

Il ne devient pas un onglet Transport global.

```text
Transport
→ Départ A
   → Jour J
      → Live
```

Un Space peut posséder plusieurs départs Live simultanément.

La personne choisit celui qu’elle focalise.

---

# 50. N2 Route

Le détail Route peut montrer :

```text
Route Lubumbashi → Kolwezi
Active

Arrêts
1. Lubumbashi
2. Likasi
3. Kolwezi

Services utilisant cette route
...
```

selon les relations réellement disponibles.

Le détail ne doit pas devenir une page de graph technique.

---

# 51. N2 Route — carte

La carte devient naturelle si elle aide à comprendre la route et ses arrêts.

Elle peut être forte en N2.

Mais :

```text
Route
≠ ligne obligatoirement affichable sur carte
```

si les faits géographiques nécessaires ne sont pas disponibles.

---

# 52. N2 Service

Le détail Service doit expliquer l’offre opérationnelle durable de transport.

Il peut montrer :

- identité Activity ;
- Route ;
- mode ;
- prochains départs ;
- préparation/configuration légitime ;
- handoffs owner.

Il ne doit pas simplement afficher les champs du modèle `TransportService`.

---

# 53. N2 Véhicule

Le détail Véhicule peut montrer :

```text
Bus 18
Autocar
Immatriculation si autorisée
50 places
Actif

Prochains départs affectés
...
```

si ces relations sont réellement disponibles.

Une absence de départ futur ne signifie pas que le véhicule est inutile ou inactif.

---

# 54. N2 Lieu

Un détail Lieu depuis Transport doit rester transport-contextualisé.

Exemple :

```text
Agence Lubumbashi

Départs utilisant ce lieu
Routes concernées
Instructions d’accès
```

si ces faits existent.

Le lieu canonique reste propriétaire de sa vérité géographique.

---

# 55. N3 — principe

N3 est la profondeur d’action spécialisée.

Exemples :

```text
Affecter véhicule
Modifier départ
Gérer capacité
Plan de placement
Contrôle d’accès
Scanner
Gérer les arrêts d’une route
```

N3 peut être techniquement plus précis que N1/N2.

Mais il ne doit jamais devenir un panneau générique « propriétés de l’objet ».

---

# 56. N3 — pas de prison latérale

Sur Wide, N3 ne doit pas être systématiquement enfermé dans un petit panneau si l’action exige de l’espace.

Exemple :

```text
Scanner
```

ou :

```text
Placement
```

peut nécessiter une surface focalisée.

Adaptive layout suit la nature de l’action.

---

# 57. Actions sensibles

Confirmation recommandée lorsque l’action :

- affecte d’autres personnes ;
- modifie un droit ;
- engage un résultat opérationnel important ;
- provoque une perte irréversible ;
- possède une conséquence financière ;
- agit au nom du Space avec impact significatif.

Les actions ordinaires réversibles ne doivent pas être ralenties par des confirmations systématiques.

---

# 58. Feedback

Après une action :

```text
ACTION
→ FEEDBACK IMMÉDIAT
→ ÉTAT PROVISOIRE si nécessaire
→ CONFIRMATION AUTORITATIVE
→ CONTINUITÉ
```

Le client ne simule jamais un succès final avant confirmation lorsque l’autorité distante est requise.

---

# 59. État initial

Si le store local possède une projection valide :

```text
initial
→ contenu local immédiat
→ synchronisation discrète
```

Le produit évite un écran blanc inutile.

Si aucune projection n’existe :

```text
initial
→ loading localisé
```

---

# 60. Loading

Un chargement court ne doit pas produire de flash de skeleton.

Lors d’un refresh avec contenu existant :

```text
contenu existant
+
indication discrète de synchronisation
```

et non :

```text
écran entier → skeleton
```

---

# 61. Content

`content` peut contenir simultanément :

- départs ;
- structure ;
- sections vides localement ;
- zones partial/unavailable ;
- synchronisation en cours.

La surface ne devient pas un état technique global à cause d’une seule section.

---

# 62. Empty total

Un Space Transport réellement vide peut montrer :

```text
Transport

Aucun départ, route ou véhicule visible pour le moment.
```

Puis, seulement si autorisé :

```text
[ Créer un départ ]
```

ou une action contextuelle appropriée.

L’empty state ne doit pas inventer une Activity fictive.

---

# 63. Calm

Transport peut avoir une structure riche sans opération actuelle.

Exemple :

```text
Aucun départ prévu aujourd’hui.

Prochains départs
Demain · 08:00

Routes
8

Véhicules
12
```

Ce n’est pas un empty state.

Ce n’est pas non plus `Tout est en ordre. ✓` obligatoire.

La formulation calme dépend de la présence de réalités utiles.

---

# 64. Offline avec snapshot

```text
content + offline
```

reste Transport.

Le client peut montrer :

```text
Dernière mise à jour · 09:15
```

lorsque la fraîcheur compte.

Une donnée locale ancienne ne devient jamais Live.

---

# 65. Offline sans snapshot

Si aucune donnée Transport locale n’est disponible :

```text
Impossible de charger Transport sans connexion pour le moment.
```

avec possibilité de réessayer.

Ne pas prétendre :

```text
Aucun départ
```

si la donnée n’a pas été obtenue.

---

# 66. Stale

Un snapshot peut rester utile sans être autoritatif.

Distinguer :

```text
KNOWN BUT STALE
```

et :

```text
UNKNOWN
```

Les Capacity, Access, incidents, états Live et opérations concurrentes exigent une prudence renforcée.

---

# 67. Error localisé

Une erreur sur `Véhicules` ne doit pas faire disparaître :

- les départs ;
- les routes ;
- les autres données encore sûres.

Principe :

> **Degrade locally first.**

Une erreur doit expliquer :

1. ce qui n’a pas fonctionné ;
2. ce qui a été conservé ;
3. ce qu’on peut faire maintenant.

---

# 68. Permission loss

Si une capacité disparaît pendant l’utilisation :

- retirer l’action ;
- revalider l’affichage sensible ;
- conserver ce qui reste légitimement visible ;
- expliquer localement la limite si une action échoue.

Ne pas transformer automatiquement toute la porte en 403 si certaines sections restent autorisées.

---

# 69. Authority failure sur action

Une action refusée côté serveur n’est pas :

```text
bug réseau
```

Elle doit être présentée comme une limite d’autorité ou un état devenu invalide.

Le contexte Transport reste préservé.

---

# 70. Back

Le parcours :

```text
Transport N1
→ Départ N2
→ action N3
→ Retour
```

restaure autant que possible :

- N2 ;
- sélection ;
- scroll ;
- filtre ;
- recherche ;
- responsabilité ;
- Space courant.

---

# 71. Resume

Après interruption :

- conserver l’écran courant si le contexte reste valide ;
- rafraîchir discrètement les états potentiellement obsolètes ;
- ne pas renvoyer systématiquement à Maintenant ;
- conserver les formulaires/brouillons appropriés ;
- revalider les actions sensibles.

---

# 72. Deep links

Les destinations importantes devraient être adressables lorsque la sécurité le permet :

```text
Transport
Départ
Route
Service
Véhicule
Jour J d’une Occurrence
```

Un deep link :

1. vérifie authentification ;
2. résout le Space ;
3. vérifie visibilité et autorité ;
4. ouvre la profondeur légitime ;
5. fournit une alternative compréhensible si la cible n’est plus disponible.

---

# 73. Local-first

Le client installé suit :

```text
UI
↓
Store local
↓
Sync
↓
Serveur Makolo
```

lorsque la projection a été acquise et peut légitimement être stockée.

Le local peut conserver :

- projections Transport déjà synchronisées ;
- Activities/Occurrences utiles ;
- structure autorisée ;
- brouillons ;
- contexte de navigation ;
- actions préparables.

Le local ne décide jamais seul :

- Capacity partagée actuelle ;
- Permission ;
- Mandate ;
- Access partagé ;
- état global d’un départ ;
- vérité Live ;
- allocation concurrente.

---

# 74. Classes d’opération

Toute action Transport mobile doit être classée :

```text
A — locale
B — locale puis synchronisée
C — préparée localement puis confirmée à distance
D — intrinsèquement distante
```

Exemples candidats :

```text
A
→ ouvrir une route déjà synchronisée

B
→ préférence d’affichage locale si supportée

C
→ préparer un formulaire de départ avant soumission

D
→ vérifier une Capacity actuelle
→ affecter un véhicule partagé
→ valider un AccessUse
```

La classification finale appartient à l’implémentation owner-backed réelle.

---

# 75. Outbox

Une mutation Transport ne va dans l’outbox que si son contrat permet une opération différée.

Ne pas mettre en file locale une opération qui exige impérativement une décision fraîche et concurrente sans stratégie sûre.

Toute opération différée doit gérer :

- identité ;
- idempotence ;
- dépendances ;
- retry ;
- confirmation ;
- échec définitif.

---

# 76. Compact

Compact privilégie :

```text
N1 vertical
→ N2 page complète
→ N3 page/bottom sheet selon nature
```

Référence :

```text
360 × 800
430 × 932
```

Edge candidat :

```text
16–20 dp
```

La bottom navigation reste visible sur N1.

Elle peut être réduite/masquée sur une surface immersive Jour J/Scanner.

---

# 77. Medium

Medium peut exploiter :

```text
liste / sections
+
aperçu N2
```

seulement lorsque deux rôles cognitifs distincts coexistent naturellement.

Le split ne doit pas réduire excessivement l’action principale.

Référence :

```text
834 × 1112
```

---

# 78. Wide

Wide peut adopter un master/detail :

```text
NAV / CONTEXTE
+
FIELD TRANSPORT
+
N2 sélectionné
```

Candidate conceptuelle :

```text
rail / nav          ~80 dp
field              360–480 dp
focus N2           560–680 dp
support            seulement si réellement utile
```

La largeur ne doit pas produire automatiquement :

- KPI ;
- cartes supplémentaires ;
- historique ;
- analytics ;
- troisième panneau permanent.

---

# 79. Very Wide

Very Wide n’autorise pas la dashboardification.

Un troisième territoire n’apparaît que s’il porte un rôle cognitif distinct et utile.

Exemple légitime :

```text
Départ sélectionné
+
carte opérationnelle utile
```

ou :

```text
Jour J opérateur
+
primary operation
+
support
```

Le simple espace disponible n’est pas une justification.

---

# 80. Adaptive conservation

Lors de :

```text
Compact → Medium
Medium → Wide
Wide → Compact
rotation
resize
```

préserver autant que possible :

- Space ;
- porte Transport ;
- responsabilité ;
- recherche ;
- filtres ;
- sélection ;
- profondeur ;
- scroll ;
- carte ;
- brouillon.

La géométrie change.

La vérité et la priorité ne changent pas.

---

# 81. Text scaling

Tests requis au minimum :

```text
1.0
1.3
1.6
```

À `1.6` :

- heure lisible ;
- origine/destination non tronquées de manière destructrice ;
- métadonnées wrap ;
- actions accessibles ;
- aucun row essentiel à hauteur fixe ;
- un split peut retomber en single-pane.

---

# 82. Accessibilité

Transport doit être utilisable avec :

- lecteur d’écran ;
- focus clavier ;
- texte agrandi ;
- contraste suffisant ;
- Reduce Motion ;
- navigation sans hover obligatoire.

Les états ne dépendent jamais uniquement de la couleur.

Exemple :

```text
Bloqué
```

est un texte/semantics, pas seulement un point rouge.

---

# 83. Motion

Les animations servent :

- changement de profondeur ;
- conservation spatiale ;
- confirmation d’action ;
- transition vers Jour J ;
- scan lorsque pertinent.

Elles ne servent pas :

- rétention ;
- décoration longue ;
- gamification.

---

# 84. Média

Transport n’est pas une surface média-first.

Média autorisé lorsqu’il sert :

- identification d’un véhicule ;
- orientation dans un lieu ;
- instruction opérationnelle ;
- preuve owner-backed ;
- contexte utile.

Pas de galerie décorative générique.

Média ≠ Proof automatique.

---

# 85. Historique

L’historique Transport peut être accessible depuis :

- N1 ;
- une Route ;
- un Service ;
- un Véhicule ;
- un départ terminé ;
- Piloter selon la question.

Il ne doit pas occuper en permanence la racine.

---

# 86. Notifications

Notification ≠ entrée Transport obligatoire.

Direction correcte :

```text
fait métier
→ conséquence
→ éventuellement Now
→ éventuellement Notification
```

Transport présente le monde de travail.

Il ne devient pas une inbox.

---

# 87. Conversations

Une Conversation peut être liée à un départ ou service si elle influence réellement l’action.

Une conversation non lue n’est pas automatiquement un signal rouge dans Transport.

Une décision attendue peut remonter via Now lorsque les propriétaires l’établissent.

---

# 88. Handoffs principaux

Transport peut transmettre vers :

```text
Now
Jour J
Makolo Live
Scanner
Access
Capacity
Placement
Activity owner
Occurrence owner
Route owner
Vehicle owner
Nous
Piloter
Makolo Mark
Historique
```

Chaque handoff doit avoir une raison humaine claire.

---

# 89. Transport → Now

Le handoff peut être implicite via la projection de conséquence.

Transport ne pousse pas manuellement une entrée dans Now.

Le fait owner-backed produit éventuellement une Situation Now.

---

# 90. Transport → Piloter

Une section ou action secondaire peut permettre :

```text
Voir le pilotage Transport
```

si le viewer possède l’autorité appropriée.

La racine ne copie pas les métriques de Piloter.

---

# 91. Transport → Nous

Depuis un problème de responsabilité :

```text
Qui est responsable ?
```

un handoff vers Nous / profondeur gouvernance peut être légitime.

Mais Transport ne devient pas propriétaire des Mandates.

---

# 92. Contrat serveur/client — endpoint racine actuel

RUNTIME OBSERVÉ :

```http
GET /api/v1/organizations/workspaces/<slug>/work/
```

Filtre optionnel observé :

```http
?responsibility=<responsibility_key>
```

Le serveur :

- résout le Space parmi les workspaces visibles au viewer ;
- applique la lentille de responsabilité ;
- filtre les Activities selon autorité ;
- compose la projection ;
- renvoie `404` lorsque le scope demandé est illégitime ;
- renvoie `Cache-Control: private, no-store`.

---

# 93. Réponse runtime actuelle sur `main`

Le runtime courant expose conceptuellement :

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

Sur `main`, les sections sont encore :

```text
preparation
upcoming
active
blocked
completed
```

Cette structure mélange encore structure durable et continuité pour certains owners Transport.

---

# 94. Correction portée par PR #496

La PR #496 propose notamment :

```text
sections.preparation   role=continuity
sections.upcoming      role=continuity
sections.active        role=continuity
sections.blocked       role=continuity
sections.completed     role=history
sections.activities    role=structure
sections.routes        role=structure
sections.vehicles      role=structure
```

Le présent contrat UX retient le principe :

> **Une structure Transport ne doit jamais être forcée dans une section de continuité seulement pour simplifier l’API.**

Le nom wire final pourra évoluer.

---

# 95. Contrat cible de section

Conceptuellement, toute section projetée devrait pouvoir exprimer :

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

`role` est une information de projection, pas un nouveau statut métier.

Valeurs conceptuelles utiles :

```text
continuity
structure
history
```

La liste finale n’est pas figée comme enum universel.

---

# 96. Contrat cible d’une entrée Transport

Une entrée de projection peut conceptuellement transporter :

```text
TRANSPORT ENTRY
├── key
├── source
│   ├── kind
│   └── id
├── kind
├── title
├── summary?
├── timing?
├── state?
├── context?
├── truth / freshness si nécessaire
├── capabilities[]
└── links / handoffs
```

Cette entrée :

```text
≠ nouveau modèle BusinessEntry
≠ vérité métier
≠ Card obligatoire
```

---

# 97. Capabilities

Le serveur doit déterminer les capabilities.

Exemples conceptuels :

```text
view
manage
open_operations
create_departure
create_route
create_vehicle
open_day_of
open_scanner
```

Seules les capabilities réellement soutenues par le runtime doivent être exposées.

Le client ne les invente pas depuis l’archétype.

---

# 98. Liens / handoffs

Le serveur devrait fournir autant que possible les handoffs sûrs déjà résolus.

Le client ne devrait pas reconstruire arbitrairement des URLs owner à partir d’IDs lorsque le contrat serveur sait fournir la destination.

Les liens peuvent viser :

- détail owner ;
- Jour J ;
- Live ;
- Capacity ;
- Access ;
- Scanner ;
- action autorisée.

---

# 99. Fraîcheur

Les faits sensibles au temps devraient permettre au client de distinguer :

```text
fresh
stale
unknown
unavailable
```

ou des états équivalents déjà canoniques.

Ne pas appliquer un TTL universel à tout Transport.

Une Route durable et une Capacity Live n’ont pas le même besoin de fraîcheur.

---

# 100. Pagination / continuation

Une limite technique de projection ne doit pas devenir :

```text
le Space n’a que 20 départs
```

Le runtime actuel utilise un preview borné.

Le contrat UX exige :

- `has_more` ou continuation équivalente ;
- accès aux autres éléments ;
- pas de Top N conceptuel opaque.

---

# 101. Confidentialité

La projection Transport applique la divulgation minimale.

Le viewer ne reçoit que :

- Spaces visibles ;
- Activities visibles ;
- données dérivées de l’autorité légitime ;
- profondeur appropriée.

Une capacité de pilotage Transport ne transfère pas automatiquement :

- PII voyageurs ;
- Payment ;
- Access complet ;
- Mandate ;
- secrets de credential.

---

# 102. IDOR

Toute profondeur owner doit revalider côté serveur :

```text
Profile
+
Space
+
objet cible
+
autorité
```

Un ID connu ne suffit jamais.

---

# 103. Golden T01 — Transport / Compact N1

**Purpose**

Reconnaître immédiatement un Space Transport, les départs utiles du jour et l’existence de sa structure durable.

**Fixture**

```text
Space : Mulykap
Responsabilité : Toutes

Aujourd’hui
14:00 Lubumbashi → Kolwezi
Préparation prête
Bus 18
42/50

16:30 Lubumbashi → Likasi
Véhicule à affecter

Demain
08:00 Kolwezi → Lubumbashi

Routes : 8
Véhicules : 12
Services : 3
```

**Viewports**

```text
360×800
430×932
```

**Acceptance**

En 500 ms :

```text
1. Transport / Space
2. ce qui se passe aujourd’hui
3. ce qui structure le métier
```

Échec si la racine ressemble à un dashboard KPI.

---

# 104. Golden T02 — Transport / Compact N2 Départ

**Purpose**

Comprendre et préparer un départ sans exposer les modèles internes.

**Fixture**

```text
Départ Lubumbashi → Kolwezi
14:00
Bus 18
42 / 50
Prêt
Jour J disponible
```

**Hierarchy**

```text
Départ / action actuelle     P3
heure + route                P2
préparation                  P2
support                      P1
```

**Acceptance**

L’utilisateur peut comprendre :

```text
quel départ
quand
où
état de préparation
prochaine profondeur utile
```

sans connaître `Occurrence`, `CapacityPool` ou `TransportDeparture`.

---

# 105. Golden T03 — Transport / Medium master-detail

**Purpose**

Conserver le champ Transport tout en ouvrant un départ.

**Candidate**

```text
FIELD
Aujourd’hui
À venir

+

FOCUS
Départ sélectionné
```

Le split est abandonné si le text scaling ou l’espace disponible dégrade la compréhension.

---

# 106. Golden T04 — Transport / Wide

**Purpose**

Exploiter la largeur sans transformer Transport en cockpit.

Candidate :

```text
NAV
+
FIELD Transport 360–480
+
FOCUS Départ 560–680
```

Support supplémentaire uniquement s’il répond à une question distincte.

---

# 107. Golden T05 — Transport / Structure Route

**Purpose**

Démontrer qu’une Route appartient à la structure durable et non à `En cours`.

Fixture :

```text
Route Lubumbashi → Kolwezi
Active
3 arrêts

Lubumbashi
Likasi
Kolwezi
```

Acceptance :

- aucune étiquette `En cours` artificielle ;
- carte seulement si les faits géographiques la justifient ;
- services utilisant la route accessibles en profondeur si disponibles.

---

# 108. Golden T06 — Transport / Offline

Fixture :

```text
Transport
Dernière mise à jour 09:15

Aujourd’hui
14:00 Lubumbashi → Kolwezi
Bus 18

Hors connexion
```

Acceptance :

- le contenu reste premier ;
- aucun faux Live ;
- aucune Capacity présentée comme fraîche sans base ;
- refresh/retry localisé.

---

# 109. Golden T07 — Transport / Partial failure

Fixture :

```text
Aujourd’hui
[départs disponibles]

Véhicules
Impossible de mettre à jour cette section.
[Réessayer]

Routes
[données disponibles]
```

Acceptance :

La panne d’une section ne détruit pas la surface.

---

# 110. Golden T08 — Transport / Permission change

Fixture :

```text
Départ Lubumbashi → Kolwezi

Vous pouvez consulter ce départ.
L’affectation de véhicule n’est plus disponible pour votre responsabilité actuelle.
```

Acceptance :

- contexte préservé ;
- action supprimée ;
- aucune exposition supplémentaire ;
- retour possible.

---

# 111. Golden T09 — Transport → Jour J

Fixture :

```text
Départ Lubumbashi → Kolwezi
Aujourd’hui · 14:00

Prêt

[ Ouvrir Jour J ]
```

Acceptance :

- Jour J apparaît comme profondeur naturelle ;
- pas comme module externe ;
- retour restaure Transport N2.

---

# 112. Golden T10 — Plusieurs départs actuels

Fixture :

```text
Aujourd’hui

14:00 Lubumbashi → Kolwezi
Jour J

14:10 Kolwezi → Likasi
Jour J

14:30 Lubumbashi → Kasumbalesa
À préparer
```

Acceptance :

- le Space entier ne devient pas Live ;
- les départs restent distincts ;
- la personne choisit sa focalisation.

---

# 113. Matrice des états Transport

| État | Racine | Départ N2 | Structure |
|---|---|---|---|
| Initial | snapshot local si disponible | snapshot si disponible | snapshot si disponible |
| Loading | skeleton localisé | contenu connu d’abord | section localisée |
| Content | départs + structure | vérité du départ | collections structurelles |
| Calm | pas d’urgence artificielle | départ stable | structure disponible |
| Empty | aucune réalité visible | normalement N/A | empty local |
| Offline | snapshot + fraîcheur | pas de faux Live | lecture locale possible |
| Stale | indicateur local | prudence accrue | souvent moins critique |
| Error | localisé | préserver détail connu | localisé |
| Permission | filtrage serveur | action retirée/404 si nécessaire | filtrage serveur |
| Refresh | contenu conservé | contenu conservé | contenu conservé |
| Resume | contexte restauré | sélection restaurée | profondeur restaurée |

---

# 114. Anti-features spécifiques Transport

Transport ne doit pas devenir :

- un ERP transport générique ;
- un TMS complet par défaut ;
- un tableau de dispatch rempli de colonnes ;
- une carte temps réel inventée ;
- un tracker GPS sans observation réelle ;
- une liste infinie de départs ;
- un calendrier parce que des dates existent ;
- un kanban `À faire / En cours / Fait` ;
- un dashboard de taux de remplissage ;
- une copie de Piloter ;
- une copie de Jour J ;
- une copie du Scanner ;
- un onglet Access ;
- un onglet Capacity ;
- un menu de tables backend ;
- une surface où Routes/Véhicules sont classés `En cours` par commodité ;
- une surface où le client infère les phases Live ;
- un système où l’archétype donne des Permissions ;
- un écran où chaque départ possède cinq CTA concurrents ;
- une carte obligatoire ;
- un feed média ;
- un réseau social de voyageurs.

---

# 115. Invariants consolidés

1. **Transport est la porte Métier visible de `transport_operator`.**
2. **La porte répond au travail réel du Space, pas à la taxonomie backend.**
3. **Le viewer reste un Profile ; l’acteur courant est le Space.**
4. **Responsabilité ≠ autorité.**
5. **Choisir le Space ou une responsabilité ne crée aucune Permission.**
6. **Transport combine continuité opérationnelle et structure durable.**
7. **Route/Véhicule/Service ne deviennent pas des Continuités par défaut.**
8. **Un départ est une réalité Occurrence-scoped.**
9. **Plusieurs départs peuvent être simultanément actuels.**
10. **Le Space entier ne devient jamais Live.**
11. **Jour J appartient au départ/Occurrence.**
12. **Live appartient à Jour J.**
13. **Transport ne possède pas Capacity.**
14. **Transport ne possède pas Access.**
15. **Transport ne possède pas Placement.**
16. **Transport ne possède pas Incidents.**
17. **Transport ne possède pas Readiness.**
18. **Presentation représente les owners.**
19. **Vehicle capacity ≠ CapacityPool.**
20. **Access ≠ AccessCredential ≠ AccessUse.**
21. **planned ≠ observed ≠ live.**
22. **unknown ≠ unavailable ≠ empty.**
23. **waiting ≠ blocked.**
24. **La carte n’est utilisée que si elle aide réellement.**
25. **La racine n’est pas un dashboard.**
26. **Piloter porte le recul analytique.**
27. **Now porte l’attention actuelle.**
28. **Nous porte identité/organisation/autorité collective.**
29. **Le Mark peut créer un handoff mais jamais contourner l’autorité.**
30. **Local-first ne signifie pas autorité locale.**
31. **Le refresh préserve le contenu connu.**
32. **Une défaillance locale reste locale si possible.**
33. **Le retour restaure le contexte.**
34. **Adaptive change la géométrie, pas la vérité.**
35. **Aucune surface ne doit retenir artificiellement l’utilisateur.**

---

# 116. Points volontairement ouverts

Restent à confirmer pendant matérialisation ou implémentation :

1. disposition pixel finale du header Transport ;
2. emplacement exact des actions de création ;
3. glyph final Transport ;
4. breakpoint exact du master/detail Transport ;
5. besoin d’un Golden Very Wide spécifique hors Jour J ;
6. format exact d’une vue carte Routes ;
7. présence d’une collection Lieux dédiée dans la projection Métier ;
8. profondeur Web/mobile définitive des Routes ;
9. profondeur Web/mobile définitive des Vehicles ;
10. owner URL final de certains objets Transport ;
11. microcopy des états empty/calm ;
12. badges ou non pour certains états de préparation ;
13. règles exactes de regroupement d’un grand nombre de départs ;
14. continuation/pagination technique de la projection Space Work ;
15. freshness policy exacte par sous-domaine ;
16. liste finale des capabilities Transport exposées par `/work/` ;
17. création directe de Route/Véhicule dans l’API Space Work ou handoff owner ;
18. composition exacte de `Services` dans la projection racine ;
19. représentation des départs terminés récents ;
20. stratégie locale exacte des mutations sensibles Transport.

Aucun de ces points ne justifie un nouveau bounded context.

---

# 117. Critères de sortie du contrat UX Transport

Le contrat est considéré suffisamment fermé pour implémentation lorsque :

- N1 Compact est reconnaissable immédiatement ;
- structure et continuité sont séparées ;
- Routes et Véhicules ne sont pas artificiellement placés dans En cours ;
- le départ possède une représentation claire ;
- les vérités temporelles sont honnêtes ;
- N2 Départ est défini ;
- N2 Route est défini ;
- N2 Service est défini ;
- N2 Véhicule est défini ;
- N3 owner/action est borné ;
- Now / Jour J / Live restent distincts ;
- la transition Transport → Jour J est naturelle ;
- plusieurs départs simultanés sont supportés ;
- recherche et filtres restent métier ;
- création reste contextuelle et permission-gated ;
- local-first est honnête ;
- les erreurs se dégradent localement ;
- Back/Resume restaurent le contexte ;
- Compact/Medium/Wide sont cohérents ;
- textScale 1.6 reste utilisable ;
- aucune PII inutile n’est exposée ;
- les actions sensibles sont revalidées côté serveur ;
- le runtime `/work/` peut évoluer vers cette grammaire sans dupliquer les owners.

---

# 118. Critères d’implémentation serveur

Une implémentation mature devrait démontrer :

- admission Space sécurisée ;
- authority scope correct ;
- responsibility lens sans gain d’autorité ;
- sections structurelles séparées ;
- occurrences Transport correctement identifiées comme départs ;
- Routes/Vehicles owner-backed ;
- Services owner-backed ;
- continuation honnête ;
- capabilities owner-backed ;
- handoffs vers Activity/Occurrence/Jour J ;
- `private, no-store` pour la projection privée ;
- IDOR tests ;
- données anciennes correctement représentées ;
- aucune migration UX artificielle ;
- aucune table `TransportWorkspaceItem` ou équivalente sans besoin irréductible.

---

# 119. Critères d’implémentation Flutter

Flutter doit :

- consommer la projection serveur ;
- persister localement seulement ce qui est légitime ;
- mapper vers une Presentation Transport propre ;
- ne pas réimplémenter les règles d’autorité ;
- préserver scroll/selection/filter/responsibility ;
- supporter deep links ;
- supporter offline avec snapshot ;
- ne pas présenter un snapshot stale comme Live ;
- revalider les actions sensibles ;
- restaurer après background/session ;
- disposer de fixtures Golden déterministes ;
- couvrir C-S, C-L, M et W ;
- couvrir text scale 1.0 / 1.3 / 1.6 ;
- couvrir permission loss et partial failure.

---

# 120. Critères d’implémentation Web

Le Web doit :

- parler Transport, pas `work` ou `Occurrence` en premier niveau ;
- conserver Space + responsibility lens ;
- utiliser progressive disclosure ;
- ne pas transformer Wide en dashboard ;
- conserver owner handoffs ;
- supporter navigation clavier ;
- avoir focus visible ;
- ne pas exiger hover ;
- préserver les sections utiles pendant refresh ;
- distinguer structure et continuité ;
- ne pas afficher un empty message trompeur pour une section non couverte.

---

# 121. Tests UX minimum

## Recognition test

En 500 ms :

```text
où suis-je ?
→ Transport de Mulykap

qu’est-ce qui domine ?
→ exploitation réelle / départ utile
```

## Blur test

Le regroupement temporel et la structure doivent rester reconnaissables sans lire les détails.

## Competition test

Une seule réalité doit prétendre être P3 dans un même territoire cognitif.

## Deletion test

Chaque élément visible doit justifier son rôle dans compréhension ou action.

## Adaptive test

Passage C-L → M → W sans perte de sélection.

## Freshness test

Snapshot ancien + Capacity sensible ne doit pas produire de faux état frais.

## Authority test

Même Profile :

```text
Space owner
vs
Activity-limited mandate
```

ne reçoit pas la même projection si l’autorité diffère.

---

# 122. Scénarios de référence

## 122.1. Transport calme

```text
Mulykap / Transport

Aucun départ prévu aujourd’hui.

Demain
08:00 Lubumbashi → Kolwezi

Routes
8

Véhicules
12
```

Verdict UX : calme, utile, non vide.

---

## 122.2. Départ à préparer

```text
14:00
Lubumbashi → Kolwezi

Véhicule à affecter
```

Transport N1 montre la continuité.

Now peut produire une Situation si la conséquence mérite attention actuelle.

---

## 122.3. Départ prêt

```text
14:00
Lubumbashi → Kolwezi
Bus 18
42 / 50
Prêt
```

Pas besoin de stimulation supplémentaire.

---

## 122.4. Départ en Jour J

```text
14:00
Lubumbashi → Kolwezi
Jour J disponible
```

Ouvrir mène vers l’expérience opérationnelle de cette Occurrence.

---

## 122.5. Plusieurs départs Live

```text
5 départs actifs
```

Transport garde le champ.

Now sélectionne les conséquences.

Jour J focalise une Occurrence.

Live reste occurrence-scoped.

---

## 122.6. Route sans départ prévu

```text
Route Lubumbashi → Kasumbalesa
Active
```

Elle reste dans Routes.

Elle ne devient ni `À venir`, ni `En cours`.

---

## 122.7. Véhicule sans affectation

```text
Bus 22
50 places
Actif
```

Il reste dans Véhicules.

L’absence d’affectation n’est pas automatiquement un problème.

---

## 122.8. Offline

```text
Transport
Dernière mise à jour 09:15

14:00 Lubumbashi → Kolwezi
Bus 18
```

Le contenu reste utile.

Aucun faux Live.

---

# 123. Formulation canonique finale

> **Transport est la porte Métier du Space `transport_operator`. Elle présente dans le langage naturel du transport les structures durables que le Space fait exister — routes, services, véhicules et lieux lorsqu’ils sont réellement supportés — ainsi que les départs et continuités opérationnelles qu’il prépare, exécute ou termine. Elle ne devient ni un ERP, ni un dashboard, ni un second Now, ni un second Jour J. La racine permet de comprendre l’exploitation actuelle et sa structure ; les profondeurs N2 rendent chaque réalité métier intelligible ; les profondeurs N3 transmettent l’action au propriétaire canonique. Le viewer reste un Profile agissant explicitement pour un Space, l’autorité reste serveur, la divulgation reste minimale, le mobile reste local-first sans devenir autorité locale, et une Occurrence suffisamment actuelle peut naturellement conduire vers Jour J puis Makolo Live sans dupliquer la réalité métier.**

---

# 124. Formule courte

```text
TRANSPORT
=
continuité d’exploitation
+
structure durable
+
profondeur owner-backed
+
handoff Jour J quand le réel devient actuel
```

avec :

```text
backend générique
+
vocabulaire Transport
+
Presentation contextuelle
```

et toujours :

> **Makolo marche pour vous.**

> **Pas le plaisir de rester. Le plaisir d’avancer.**

