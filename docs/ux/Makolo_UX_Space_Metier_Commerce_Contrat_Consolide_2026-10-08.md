# Makolo — Space Métier `commerce` / **Commerce**
## Contrat UX consolidé — N1, N2/N3, hiérarchie, représentations, états, adaptive, local-first et handoffs

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence pour l’archétype Space `commerce`  
**Porte visible :** **Commerce**  
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
commerce
```

Le libellé visible primaire est :

```text
Commerce
```

Le contrat part de la chaîne humaine déjà fixée dans l’architecture Space :

```text
ce que nous rendons disponible
→ offre
→ commande / demande
→ préparation / disponibilité
→ remise / réalisation
→ obtention accomplie
```

Il ne redéfinit pas les domaines propriétaires. Il fixe comment leurs vérités deviennent une expérience Commerce cohérente.

Il ne remplace pas :

- `Activity` ;
- `Occurrence` ;
- Obtention ;
- `Offer` ;
- `CommerceOrder` ;
- `Payment` ;
- `Capacity` ;
- `Access` ;
- `Journey` ;
- `Requirement` ;
- `Readiness` ;
- Transport ;
- Trust / Proof ;
- Permission / Mandate ;
- Maintenant ;
- Découvrir ;
- Nous ;
- Piloter ;
- Jour J / Makolo Live.

Question du contrat :

> **Comment permettre à un Space Commerce de comprendre ce qu’il rend disponible, ce qui est demandé ou commandé, ce qui doit être préparé, payé, remis ou réalisé, et ce qui est réellement accompli — sans transformer Makolo en ERP, caisse, marketplace ou moteur de paiement ?**

---

# 1. Sources de cadrage

Ce contrat est dérivé principalement de :

- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md` ;
- `space-ux-experience-specification.md` lorsque ses décisions sont reprises ou démontrées ;
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
- `Makolo_Obtention_Verticale_Cadre_Conception_v2.md` ;
- les contrats Space Métier Transport, Programmes et Prestations déjà consolidés ;
- le code, migrations et tests du dépôt `TraditionLearningCommunity/makolo`.

Au moment de rédaction, le `main` vérifié est :

```text
d5b85ee4c737f09da7d1b2e27f7bae9d14d40131
```

Le runtime courant reste prioritaire lors de toute implémentation future.

---

# 2. Statuts utilisés dans ce document

### GELÉ
Décision UX ou invariant à préserver.

### CIBLE UX
Comportement attendu, suffisamment défini pour guider l’implémentation.

### RUNTIME OBSERVÉ
Comportement réellement constaté dans `main` au moment de rédaction.

### OUVERT
Détail encore volontairement non figé.

---

# 3. Place de Commerce dans le shell Space

La navigation primaire reste :

```text
Maintenant | Découvrir | [Makolo Mark] | Commerce | Nous
```

Commerce est la porte durable du monde de travail commercial du Space.

Elle répond à :

> **Qu’est-ce que nous rendons réellement disponible, que devons-nous traiter, préparer, remettre ou accomplir ?**

La racine ne doit pas donner l’impression de gérer une base de données d’objets techniques.

---

# 4. Frontières avec les autres portes

## 4.1. Commerce ≠ Maintenant

Commerce présente le champ durable et la continuité commerciale.

Maintenant sélectionne seulement ce qui mérite une attention actuelle.

Exemple :

```text
Commerce
→ 38 commandes actives
```

mais Now peut montrer :

```text
Commande COM-493
Retrait prévu aujourd’hui.
Paiement confirmé.
Préparation non confirmée.

[ Ouvrir ]
```

Commerce ne devient pas une copie dense de Now.

## 4.2. Commerce ≠ Découvrir

Découvrir répond à ce qui pourrait aider le Space à avancer.
Commerce répond à ce que le Space rend déjà disponible et doit réellement opérer.

## 4.3. Commerce ≠ Nous

Commerce = ce que le Space vend, loue, distribue, prête, échange ou rend disponible et les continuités correspondantes.

Nous = identité collective, équipe, responsabilités, relations et organisation.

## 4.4. Commerce ≠ Piloter

Commerce aide à faire avancer les opérations réelles.
Piloter prend du recul sur tendances, flux, Capacity, finance ou délivrance.

Un graphique de chiffre d’affaires n’est pas le contenu primaire de Commerce.

## 4.5. Commerce ≠ Payment

Payment possède la vérité financière.
Commerce peut montrer qu’un paiement compte pour une commande, mais ne devient pas moteur de paiement.

## 4.6. Commerce ≠ Obtention

Commerce possède prix, Offer et Order.
Obtention peut posséder la cible, le mode d’obtention et le sens du résultat réellement obtenu.

Une Activity peut composer les deux.

---

# 5. Personnalité de la surface

Formulation de référence :

> **Commerce = disponibilité réelle + traitement + délivrance.**

Le sentiment recherché est :

```text
je sais ce qui est disponible
+
je sais ce qui doit avancer
+
je sais ce qui est prêt ou non
+
je sais ce qui doit être remis / réalisé
+
je ne confonds pas paiement et accomplissement
```

Commerce doit être professionnel, dense quand nécessaire, mais calme et lisible.

---

# 6. Densité

Densité cible : **moyenne à élevée**.

La racine doit pouvoir porter beaucoup de réalité sans devenir un tableau ERP permanent.

Principe :

```text
plus de volume
≠ plus de chrome
≠ plus de KPI
≠ plus de colonnes techniques
```

La densité vient surtout de rows structurées, groupes humains, filtres utiles et progressive disclosure.

---

# 7. Contexte acteur visible

Le contexte doit rester récupérable :

```text
Makolo
+ Space
+ Commerce
```

Le Profile reste la personne qui regarde et agit.
Le Space est l’acteur collectif.

```text
actor_context = Space
viewer = Profile
```

Le viewer ne devient jamais « vendeur global » dans son identité.

---

# 8. Responsibility filter

Lorsque plusieurs responsabilités existent, une lecture peut être réduite à une responsabilité pertinente.

Exemples :

```text
Toutes mes responsabilités
Commandes
Préparation
Finance
Remise
```

Ces libellés sont UX et doivent correspondre à des responsabilités réellement établies.

Invariant :

```text
filtrer par responsabilité
≠ augmenter l’autorité
```

La projection serveur reste permission-first.

---

# 9. Architecture cognitive générale

La racine Commerce compose deux champs :

```text
COMMERCE
│
├── CONTINUITÉ COMMERCIALE
│   ├── commandes / demandes
│   ├── à traiter
│   ├── à préparer
│   ├── à remettre / réaliser
│   ├── bloquées si réel
│   └── terminées / histoire accessible
│
└── STRUCTURE COMMERCIALE
    ├── ce que nous rendons disponible
    ├── offres
    ├── disponibilité
    └── Capacity lorsque pertinente
```

Ces deux champs ne doivent pas être fusionnés dans un simple statut universel.

---

# 10. Structure métier Commerce

La structure durable correspond à ce que le Space peut rendre disponible de manière suffisamment stable.

Elle peut être soutenue par :

- Activity ;
- Obtention lorsque la cible et le mode d’obtention le nécessitent ;
- Offers ;
- Capacity ;
- Occurrences lorsqu’une disponibilité temporelle réelle existe ;
- ressources ou lieux utiles.

Une Offer active n’est pas une continuité en cours simplement parce qu’elle est active.

---

# 11. Continuité commerciale

Une continuité commerciale apparaît lorsqu’une réalité doit effectivement progresser vers un résultat.

Exemples :

- demande reçue ;
- commande à confirmer ;
- paiement attendu lorsqu’il conditionne la suite ;
- préparation réelle ;
- disponibilité à confirmer ;
- remise ou réalisation attendue ;
- confirmation de résultat lorsque le propriétaire le prévoit.

La continuité ne crée pas un nouveau modèle `CommerceContinuity`.

---

# 12. N1 — objectif

En N1, la personne doit comprendre rapidement :

1. ce qui exige du traitement ;
2. ce qui doit être préparé ou remis ;
3. ce qui est disponible à proposer ;
4. si une limite réelle de Capacity compte ;
5. où ouvrir la profondeur légitime.

N1 ne doit pas exposer toutes les propriétés financières ou techniques.

---

# 13. N1 — composition de référence Compact

Exemple conceptuel :

```text
Commerce

[ Rechercher ]    [ Filtres ]
Toutes mes responsabilités ▾

À traiter
COM-493
Kit scolaire · 2 unités
Paiement confirmé
Préparation à faire

À remettre
COM-488
Retrait aujourd’hui · Centre-ville
Prête

Offres
Kits rentrée 2027
Babouches artisanales
Location groupe électrogène

Disponibilité
2 offres bientôt indisponibles

Voir l’historique
```

Cette composition est une référence, pas une obligation de sections identiques pour tous les Spaces.

---

# 14. N1 — ordre de priorité

Ordre perceptif recommandé :

```text
P3  conséquence opérationnelle réelle
P2  réalité commerciale / commande / offre dominante
P2  action légitime
P1  contexte utile
P0/P1 métadonnées
```

Un montant ne devient pas automatiquement P3.
Une échéance ou une préparation manquante peut être plus importante qu’un total financier.

---

# 15. N1 — « À traiter »

Cette section regroupe seulement les réalités où une intervention commerciale légitime est attendue.

Elle peut inclure :

- commande en attente ;
- demande nécessitant décision ;
- validation requise ;
- préparation à engager ;
- paiement à vérifier si l’autorité du viewer le permet ;
- action nécessaire avant remise.

Elle ne doit pas devenir une inbox universelle.

---

# 16. N1 — « À préparer »

Cette section représente des commandes ou délivrances dont le résultat attendu exige une préparation réelle.

Exemples :

```text
Kit scolaire · 2 unités
À préparer avant vendredi
```

```text
Location groupe électrogène
Matériel à rendre disponible pour le 12 oct.
```

Elle ne doit pas inventer une étape de préparation lorsque le domaine propriétaire n’en établit aucune.

---

# 17. N1 — « À remettre / réaliser »

Cette section montre ce qui est suffisamment prêt pour passer vers le résultat réel.

Exemples :

- retrait ;
- livraison lorsque réellement supportée ;
- remise physique ;
- mise à disposition ;
- activation d’un droit d’usage ;
- échange ;
- réalisation convenue.

Le libellé peut s’adapter au mode réel.

---

# 18. N1 — « Bloquées »

Un blocage n’apparaît que lorsqu’une transition nécessaire est réellement empêchée.

Exemples :

```text
Paiement requis avant confirmation
```

```text
Disponibilité insuffisante
```

```text
Document requis non validé
```

Une attente normale n’est pas automatiquement un blocage.

---

# 19. N1 — Terminées

Les réalités terminées ne doivent pas dominer la racine.

Accès possible :

```text
Historique
Terminées
Passées
```

selon le contexte.

Une commande `CONFIRMED` n’est pas nécessairement terminée au sens d’obtention réelle.

---

# 20. Structure — « Ce que nous rendons disponible »

La structure doit parler du résultat proposé, pas seulement de l’Offer technique.

Exemples :

```text
Kits scolaires
Babouches artisanales
Location de groupes électrogènes
Distribution de matériel
```

L’Offer est une couche commerciale rattachée à cette réalité.

---

# 21. Structure — Offres

Une Offer peut exprimer :

- nom ;
- prix ;
- devise ;
- fenêtre de disponibilité ;
- quantité min/max ;
- Capacity associée ;
- modes de paiement autorisés.

N1 n’affiche que ce qui aide réellement à agir ou comprendre.

---

# 22. Structure — Disponibilité

Disponibilité peut provenir de :

- fenêtre d’Offer ;
- Capacity ;
- Occurrence ;
- règle propre à Obtention ;
- autre propriétaire pertinent.

Invariant :

```text
Offer ACTIVE
≠ forcément disponible maintenant
```

Le runtime possède déjà `is_currently_available` côté Offer ; l’UX ne doit pas simplifier cela en un badge trompeur.

---

# 23. Structure — Capacity

Capacity répond à :

> **Combien ?**

Elle peut être utile pour :

- quantité limitée ;
- réservations ;
- stock logique lorsqu’il est effectivement porté par Capacity ;
- slots ;
- nombre d’unités disponibles.

Commerce ne recrée pas un stock universel si Capacity suffit.

---

# 24. Représentation d’une commande en N1

Une row de commande doit privilégier :

```text
référence humaine / commerciale
cible ou libellé principal
état utile
prochaine conséquence
moment / lieu si pertinent
montant si utile
```

Exemple :

```text
COM-493
Kit scolaire · 2 unités
Paiement confirmé
À préparer avant vendredi
```

Éviter :

```text
OrderStatus.CONFIRMED
JourneyStatus.CONFIRMED
PaymentStatus.SUCCEEDED
```

comme langage principal.

---

# 25. Représentation d’une Offer en N1

Une Offer peut être une row ou une carte compacte selon le besoin de représentation.

Exemple :

```text
Kit scolaire rentrée 2027
35 USD
Disponible jusqu’au 30 octobre
```

Si la photo aide réellement à reconnaître la cible, elle peut être utilisée.

No Orphan Media reste applicable.

---

# 26. Informations prioritaires d’une commande

Priorités possibles :

```text
1. ce qui doit arriver ensuite
2. préparation / remise
3. état réel de paiement si pertinent
4. disponibilité / Capacity si elle contraint
5. timing / lieu
6. bénéficiaire selon autorité
```

Le montant n’est pas toujours la première information.

---

# 27. Prix et montants

Un prix doit être présenté clairement lorsqu’il aide la décision ou l’opération.

Les détails de snapshot financier, frais, politique de pricing et ventilation restent en profondeur ou dans Finance/Piloter selon l’usage.

N1 ne devient pas un journal comptable.

---

# 28. Vérité temporelle

Distinguer :

- disponibilité planifiée ;
- date de retrait ;
- échéance ;
- expiration de commande ;
- fenêtre d’Offer ;
- Occurrence réelle.

Une date d’expiration d’Offer n’est pas une Occurrence.

---

# 29. Géographie

La carte n’est pas un mode obligatoire de Commerce.

Elle peut devenir utile lorsque :

- retrait physique ;
- plusieurs points de remise ;
- disponibilité par lieu ;
- tournée ou acheminement ;
- contexte de proximité.

Une adresse peut suffire si la carte n’améliore pas l’action.

---

# 30. Recherche Commerce

Recherche spécialisée possible :

```text
commande
référence
client / bénéficiaire selon autorité
cible / offre
lieu
```

Elle reste limitée au Space et permission-first.

---

# 31. Filtres Commerce

Filtres humains possibles :

```text
À traiter
À préparer
À remettre
Terminées
Paiement attendu
Prêtes
Lieu
Période
Responsabilité
```

Seulement lorsqu’ils correspondent à une réalité soutenue.

Ne pas exposer directement les enums backend.

---

# 32. Tri

Le tri doit rester stable et compréhensible.

Options possibles :

- échéance utile ;
- date de création lorsque pertinente ;
- référence ;
- prochaine action réelle.

Éviter un score opaque.

---

# 33. Création contextuelle

Pas de méga-menu universel.

Actions candidates selon capacités réelles :

```text
Nouvelle offre
Rendre quelque chose disponible
```

Si l’Activity / Obtention doit être créée avant l’Offer, l’UX doit guider la création humaine sans exposer la taxonomie backend.

Le contrat ne fige pas un unique flow de création universel.

---

# 34. Placement de l’action de création

L’action de création peut apparaître :

- dans le header secondaire ;
- à proximité de la structure « Offres » ;
- dans l’état vide ;
- via Makolo Mark.

Elle ne doit pas concurrencer le Mark avec un FAB générique permanent.

---

# 35. Création et Permission

La présence de l’archétype Commerce n’accorde rien.

Le client n’infère jamais :

```text
commerce archetype
→ permission créer Offer
```

Les capabilities doivent être établies côté serveur.

---

# 36. Makolo Mark → Commerce

Exemples :

> « Mets les kits rentrée 2027 à 35 USD. »

> « Prépare la commande COM-493 pour retrait vendredi. »

Le Mark doit résoudre :

- le Space ;
- la cible ;
- l’autorité ;
- le propriétaire canonique ;
- les données manquantes ;
- la confirmation éventuelle.

Il ne contourne jamais Commerce, Payment, Capacity ou Permission.

---

# 37. N2 — principe général

N2 montre une réalité humaine cohérente et suffisamment complète.

Les profondeurs principales sont :

```text
N2 Offre / disponibilité
N2 Commande / demande
N2 cible d’Obtention lorsque pertinente
```

N2 ne doit pas devenir un écran à onglets techniques `Order / Payment / Capacity / Journey / Access`.

---

# 38. N2 Commande — objectif

Question :

> **Qu’est-ce qui a été demandé ou commandé, où en sommes-nous réellement, qu’est-ce qui manque, et que doit-il se passer pour que le résultat soit effectivement délivré ?**

---

# 39. N2 Commande — composition conceptuelle

```text
COMMANDE / DEMANDE
│
├── IDENTITÉ
│   ├── référence
│   ├── cible / lignes
│   └── bénéficiaire selon autorité
│
├── SYNTHÈSE
│   └── où nous en sommes
│
├── COMMERCE
│   ├── Offer snapshot
│   ├── quantités
│   └── montant
│
├── PAYMENT ?
├── CAPACITY ?
├── PREPARATION ?
├── DELIVERY / FULFILLMENT ?
├── TIME / PLACE ?
├── REQUIREMENTS / PROOF ? si réellement composés
├── ACTIONS autorisées
└── OWNER HANDOFFS
```

Ce schéma est une grammaire UX, pas une table.

---

# 40. N2 Commande — synthèse

La synthèse doit être humaine :

```text
Paiement reçu. La commande reste à préparer pour vendredi.
```

ou :

```text
Commande confirmée. Retrait possible dès demain au point Centre-ville.
```

Pas :

```text
Order=CONFIRMED
Journey=CONFIRMED
```

---

# 41. N2 Commande — lignes

Les lignes montrent :

- libellé snapshot ;
- quantité ;
- prix utile ;
- bénéficiaire lorsque pertinent ;
- disponibilité si elle contraint.

Le snapshot historique de prix reste cohérent avec la commande et ne doit pas être remplacé visuellement par le prix actuel d’une Offer modifiée.

---

# 42. N2 Commande — Payment

Payment peut être présenté comme une dimension de la commande lorsque cela compte.

Exemples :

```text
Paiement attendu
Paiement en vérification
Paiement confirmé
Remboursement
```

Mais l’UX doit garder l’invariant :

```text
Payment SUCCEEDED
≠ fulfillment
```

---

# 43. N2 Commande — Capacity

Si une commande a réservé ou engagé de la Capacity, N2 peut montrer :

```text
2 unités réservées
```

ou :

```text
Disponibilité confirmée
```

sans inventer un stock global.

La concurrence reste autoritative côté serveur.

---

# 44. N2 Commande — préparation

Préparation est visible lorsqu’elle existe réellement.

Elle peut être :

- ressources à rassembler ;
- article à préparer ;
- disponibilité à sécuriser ;
- document à produire ;
- condition à satisfaire ;
- action de propriétaire.

Ne pas créer une checklist artificielle si le runtime ne porte pas ces vérités.

---

# 45. N2 Commande — remise / réalisation

Cette partie répond à :

> **Comment et quand le résultat est-il effectivement délivré ou reconnu ?**

Elle peut utiliser :

- Occurrence ;
- lieu ;
- instruction de retrait ;
- Transport ;
- Access ;
- Proof ;
- confirmation du résultat ;
- fulfillment d’Obtention.

Selon la composition réelle.

---

# 46. N2 Commande — résultat

Le résultat doit être distinct de la transaction financière.

Exemples :

```text
Commande payée
→ pas encore retirée
```

```text
Commande remise
→ obtention accomplie si le contrat le permet
```

Le langage « terminé » doit être soutenu par le propriétaire du résultat.

---

# 47. N2 Offer — objectif

Question :

> **Qu’est-ce qui est proposé, à quelles conditions, avec quelle disponibilité réelle, et quelles opérations sont possibles ?**

---

# 48. N2 Offer — composition

```text
OFFRE
├── cible / Activity
├── nom et description utile
├── prix / devise
├── disponibilité
├── quantité min/max
├── Capacity ?
├── fenêtre temporelle ?
├── Occurrence ?
├── modes de paiement ?
├── état de publication
└── actions autorisées
```

---

# 49. N2 Offer — disponibilité réelle

L’écran doit distinguer :

```text
active
mais pas encore disponible
```

```text
active
mais épuisée / Capacity atteinte
```

```text
active et disponible
```

```text
expirée / inactive
```

sans convertir toutes ces réalités en un statut unique inventé.

---

# 50. N2 cible d’Obtention

Lorsque Commerce est composé avec Obtention, une profondeur peut expliquer :

- ce qui peut être obtenu ;
- le mode : achat, location, prêt, distribution, échange, autre ;
- le résultat attendu ;
- les conditions ;
- les possibilités de délivrance.

Le client ne doit pas appeler toute Activity Commerce « Produit » si ce n’est pas son sens réel.

---

# 51. Plusieurs modes d’obtention

Le même Space peut exploiter :

```text
vente
location
prêt
distribution
échange
```

Commerce doit adapter son vocabulaire lorsque le contexte est déterminé.

Exemples :

```text
Vente
Location
Distribution
```

plutôt qu’un générique artificiel lorsque le mode est connu.

---

# 52. Commande vs demande

Une relation peut être une commande directe ou une demande nécessitant approbation.

L’UX doit respecter le workflow réel.

```text
commande
≠ demande
```

Le mot visible suit le contrat configuré.

---

# 53. N3 — principe

N3 ouvre les propriétaires précis quand l’action l’exige.

Exemples :

```text
vérifier paiement
modifier Offer
voir Capacity
voir preuve
voir Journey
ouvrir lieu / Occurrence
```

N3 ne crée pas une navigation parallèle Commerce.

---

# 54. N3 — pas de prison latérale

Une personne qui ouvre un owner doit pouvoir revenir à la commande ou à l’Offer avec :

- contexte ;
- filtre ;
- sélection ;
- scroll ;
- profondeur raisonnablement restaurés.

---

# 55. Actions sensibles

Exemples :

- confirmer commande ;
- annuler ;
- rembourser ;
- vérifier paiement ;
- réserver / engager Capacity ;
- modifier prix ou Offer ;
- déclarer remise / fulfillment si autorisé.

Ces actions demandent revalidation autoritative selon leur domaine.

---

# 56. Concurrence et idempotence

Commerce est particulièrement exposé à la concurrence.

Le client ne doit pas croire qu’une quantité est acquise tant que l’autorité n’a pas confirmé la réservation ou l’engagement approprié.

Les opérations critiques doivent respecter l’idempotence déjà prévue dans les domaines propriétaires.

---

# 57. Feedback

Le feedback exprime exactement le niveau atteint.

Préférer :

```text
Commande enregistrée. Paiement encore attendu.
```

```text
Paiement confirmé. La commande reste à remettre.
```

```text
Remise confirmée.
```

Éviter :

```text
Terminé ✓
```

si seul le paiement a réussi.

---

# 58. État initial

La surface peut afficher un snapshot local autorisé immédiatement, puis se synchroniser.

Le chargement réseau ne doit pas détruire le contenu connu.

---

# 59. Loading

Préférer :

```text
contenu connu
+ indicateur discret
```

à :

```text
vide
→ skeleton plein écran
→ contenu
```

si un snapshot sûr existe.

---

# 60. Content

État normal avec :

- structure commerciale ;
- continuités ;
- actions ;
- fraîcheur suffisante.

---

# 61. Empty total

Un Space Commerce neuf peut afficher :

```text
Commerce

Rien n’est encore proposé ici.

[ Rendre quelque chose disponible ]
```

seulement si la capability existe.

Ne pas fabriquer une Offer d’exemple dans les données réelles.

---

# 62. Calm

Commerce peut avoir beaucoup d’offres mais aucune commande à traiter.

Exemple :

```text
Aucune commande ne demande votre attention.

Offres
12 actives
```

Pas besoin de remplir l’espace avec des KPI.

---

# 63. Empty filtré

Exemple :

```text
Aucune commande à remettre aujourd’hui.
```

Ce n’est pas l’état vide du Commerce entier.

---

# 64. Offline avec snapshot

Afficher le contenu connu et une fraîcheur honnête.

Exemple :

```text
Dernière mise à jour · 09:15
```

Les actions nécessitant confirmation distante restent limitées.

---

# 65. Offline sans snapshot

Expliquer simplement :

```text
Commerce n’est pas encore disponible hors connexion sur cet appareil.
```

sans inventer un état de commandes.

---

# 66. Stale

Une donnée ancienne ne doit pas être présentée comme actuelle quand cela change l’action.

Particulièrement :

- Capacity ;
- paiement ;
- statut de commande ;
- disponibilité ;
- remise / fulfillment.

---

# 67. Error localisé

Exemple : la liste des commandes est disponible mais les informations Payment ne peuvent pas être rafraîchies.

La surface doit rester Commerce, avec erreur localisée.

Ne pas remplacer toute la page par une erreur globale.

---

# 68. Permission loss

Si le viewer perd l’autorité sur certaines commandes ou Activities :

- retirer les données non autorisées ;
- retirer les actions ;
- préserver le reste du contexte ;
- expliquer seulement ce qui est nécessaire.

---

# 69. Authority failure sur action

Si une action échoue pour autorité insuffisante :

```text
Cette action n’est plus autorisée dans ce contexte.
```

Puis reprojeter la vérité actuelle.

Pas de succès optimiste durable.

---

# 70. Back

Back doit restaurer autant que possible :

- section ;
- filtre ;
- query ;
- scroll ;
- sélection ;
- responsabilité active.

---

# 71. Resume

Au retour après interruption :

1. montrer le contenu local connu ;
2. indiquer la fraîcheur si utile ;
3. synchroniser ;
4. réconcilier ;
5. préserver la sélection tant qu’elle reste légitime.

---

# 72. Deep links

Un deep link vers une commande doit :

- résoudre le Space ;
- vérifier le viewer ;
- vérifier l’autorité ;
- ouvrir N2 si légitime ;
- ne pas révéler l’existence autrement.

Même principe pour Offer et autres profondeurs sensibles.

---

# 73. Local-first

Sur client installé :

```text
UI
↓
store local
↓
sync
↓
server
```

lorsque les données sont autorisées à être conservées.

Mais le local ne devient pas autorité sur :

- Payment ;
- Capacity partagée ;
- statut concurrent de Order ;
- Permission / Mandate ;
- fulfillment global ;
- disponibilité fraîche.

---

# 74. Classes d’opération

Exemples conceptuels :

```text
A locale
→ préférence d’affichage

B locale puis synchronisée
→ brouillon non sensible lorsque supporté

C préparée localement puis confirmée à distance
→ action commerciale sensible préparée

D distante
→ paiement, confirmation concurrente, vérification autoritative
```

Le langage technique n’est pas montré à l’utilisateur.

---

# 75. Outbox

Une action mise en outbox ne doit jamais être affichée comme accomplie avant confirmation réelle.

Exemple :

```text
En attente de synchronisation
```

plutôt que :

```text
Commande remise
```

---

# 76. Compact

Référence :

- sections verticales ;
- rows riches ;
- N2 plein écran ;
- filtres secondaires en sheet ;
- actions principales accessibles sans surcharger le header.

---

# 77. Medium

Peut utiliser :

```text
field
+
apercu / N2 léger
```

si la largeur permet de préserver correctement le contexte.

Le split n’est pas obligatoire.

---

# 78. Wide

Après sélection :

```text
NAV | COMMERCE FIELD | N2 COMMAND / OFFER
```

La racine seule reste centrée sur le champ métier.

La largeur ne justifie pas un dashboard de KPI.

---

# 79. Very Wide

Peut augmenter le calme, les marges ou la stabilité du master-detail.

Ne pas ajouter automatiquement :

- finance panel ;
- analytics panel ;
- CRM panel ;
- inventory panel.

---

# 80. Adaptive conservation

Invariant :

```text
même vérité
+
même priorité
+
même action légitime
+
géométrie adaptée
```

Préserver : sélection, filtre, query, scroll, profondeur et brouillon lorsque possible.

---

# 81. Text scaling

Tests minimum :

```text
1.0
1.3
1.6
```

À 1.6 :

- aucune référence critique tronquée sans solution accessible ;
- les montants ne concurrencent pas la conséquence ;
- les actions restent atteignables ;
- la hiérarchie reste lisible.

---

# 82. Accessibilité

Exigences :

- taille de cible suffisante ;
- contraste ;
- labels non dépendants de la couleur ;
- état annoncé aux lecteurs d’écran ;
- focus cohérent ;
- erreurs actionnables ;
- montant + devise prononçables ;
- références copiables si utile.

---

# 83. Motion

Animation seulement pour :

- conservation de contexte ;
- transition N1 → N2 ;
- confirmation perceptible ;
- réorganisation localisée.

Respecter Reduce Motion.

Pas d’animation destinée à retenir l’attention.

---

# 84. Média

Le média est légitime s’il aide à reconnaître ou comprendre ce qui est rendu disponible.

Il ne transforme pas Commerce en marketplace visuelle générique.

Une commande n’a pas besoin d’une grande image si la conséquence opérationnelle est plus importante.

---

# 85. Historique

Historique est transverse.

Commerce peut offrir :

```text
Terminées
Historique
```

mais ne possède pas toutes les preuves historiques.

---

# 86. Notifications

Une notification n’est pas une commande ni une Situation Now.

Direction :

```text
fait Commerce
→ conséquence
→ éventuellement Now
→ éventuellement Notification
```

---

# 87. Conversations

Une conversation peut être affichée dans la profondeur si elle porte une décision ou une information réellement liée à la commande.

Une conversation non lue n’est pas automatiquement urgente.

---

# 88. Handoffs principaux

```text
Commerce → Order owner depth
Commerce → Offer owner depth
Commerce → Obtention
Commerce → Payment
Commerce → Capacity
Commerce → Occurrence / Jour J si réalisation temporelle réelle
Commerce → Transport si acheminement réel
Commerce → Now si attention nécessaire
Commerce → Piloter pour analyse
Commerce → Nous / Clients & relations lorsque relationnel
```

---

# 89. Commerce → Now

Un problème Commerce devient une Situation Now seulement s’il mérite l’attention actuelle.

Exemple :

```text
Commande COM-493
Retrait aujourd’hui.
Paiement confirmé.
Préparation non confirmée.
```

Le fait reste Commerce ; Now ne le possède pas.

---

# 90. Commerce → Jour J

Jour J est pertinent uniquement lorsqu’une Occurrence réelle devient actuelle.

Exemple :

```text
Séance de distribution
→ Occurrence
→ Jour J
```

Une simple Offer disponible aujourd’hui ne devient pas Jour J.

---

# 91. Commerce → Piloter

Piloter peut analyser :

- flux ;
- conversion lorsqu’elle a un sens légitime ;
- Capacity ;
- finance ;
- délivrance ;
- échecs / retards ;
- tendances.

Commerce reste la surface d’action quotidienne.

---

# 92. Contrat serveur/client — endpoint racine actuel

**RUNTIME OBSERVÉ**

La projection Space Métier actuelle est servie par :

```http
GET /api/v1/organizations/workspaces/<slug>/work/
```

Elle est permission-first et retourne une projection de travail Space.

Ce document ne crée pas un endpoint Commerce indépendant par principe.

---

# 93. Réponse runtime actuelle sur `main`

Le runtime courant expose notamment :

```text
space
archetype
primary_business_label
responsibility
authority
operational_footprint
sections
capabilities
links
```

Les sections techniques actuelles sont :

```text
preparation
upcoming
active
blocked
completed
```

Elles ne sont pas automatiquement les sections visibles finales de Commerce.

Le client doit traduire vers une grammaire humaine sans changer la vérité.

---

# 94. Commerce dans la projection actuelle

**RUNTIME OBSERVÉ**

La projection actuelle compose notamment :

- `Offer` visibles avec capability Commerce ;
- `CommerceOrder` lorsque `ORDERS_VIEW` est disponible ;
- `Activity` et `Occurrence` visibles ;
- capabilities par Activity ;
- filtrage par responsabilité / Mandate.

Les Offers sont actuellement projetées selon leurs statuts techniques vers les sections génériques.
Les Orders `PENDING` ou `CONFIRMED` sont actuellement considérées actives dans la projection générique.

Cela ne suffit pas à représenter le fulfillment réel ; le contrat UX cible doit conserver cette distinction.

---

# 95. Contrat cible de section

Une section Commerce visible devrait être une projection avec :

```text
key
label humain
purpose
items[]
coverage_state
freshness
continuation?
links?
```

`key` peut rester technique côté wire.
`label` doit parler Commerce.

---

# 96. Contrat cible d’une entrée Commerce

Conceptuellement :

```text
COMMERCE_ENTRY
├── identity
├── source / provenance
├── kind
├── human_title
├── synthesis
├── state facts
├── timing
├── place?
├── amount?
├── availability?
├── payment_context?
├── capacity_context?
├── fulfillment_context?
├── capabilities[]
├── owner_depth
├── handoffs[]
└── freshness
```

Ce n’est pas un nouveau modèle.

---

# 97. Capabilities

Les capabilities doivent être explicites et server-derived.

Exemples conceptuels :

```text
view
manage
open_commerce
create_offer
edit_offer
view_order
confirm_order
cancel_order
open_payment
open_capacity
mark_fulfillment
```

Les noms exacts du wire restent ouverts sauf ceux déjà présents dans le runtime.

Le client ne fabrique jamais une capability depuis l’archétype.

---

# 98. Liens / handoffs

Les liens servent à entrer dans le propriétaire approprié.

Ils ne doivent pas forcer le client à reconstruire des URLs métier à partir d’IDs si le serveur peut fournir le handoff.

---

# 99. Fraîcheur

La projection doit pouvoir distinguer, selon les données disponibles :

```text
fresh
stale
unknown
unavailable
partial
```

Les termes wire peuvent varier tant que l’UX peut exprimer honnêtement l’état de connaissance.

---

# 100. Pagination / continuation

Le réel n’est pas limité conceptuellement à un Top N.

Une borne technique peut exister.

L’UX préfère :

```text
Voir plus
```

ou continuation contextuelle à des pages numérotées lorsque cela préserve mieux la continuité.

Pas de scroll infini artificiel.

---

# 101. Confidentialité

Commerce peut contenir des informations privées :

- identité bénéficiaire ;
- montant ;
- paiement ;
- documents ;
- adresse ;
- instructions ;
- historique.

La projection applique la divulgation minimale.

Un accès aux Orders n’accorde pas automatiquement accès à tous les détails Payment ou privés.

---

# 102. IDOR

Toute profondeur doit être vérifiée côté serveur.

Le fait de connaître :

- un order ID ;
- une référence ;
- un offer ID ;
- un payment ID ;
- une Activity ;

ne crée aucun droit de lecture ou mutation.

---

# 103. Golden C01 — Commerce / Compact N1

**Fixture :**

```text
À traiter
COM-493 · Kit scolaire ×2
Paiement confirmé
Préparation à faire

À remettre
COM-488 · Kit rentrée
Prête · retrait aujourd’hui

Offres
Kits rentrée 2027 · 35 USD
```

**Viewport :** 360×800 et 430×932.

Acceptance :

- Commerce reconnu en 500 ms ;
- conséquence opérationnelle dominante ;
- montant secondaire ;
- pas de dashboard.

---

# 104. Golden C02 — Commerce / Compact N2 Commande

Fixture : COM-493.

Doit montrer :

```text
référence
cible
synthèse
paiement
préparation
remise
prochaine action
```

sans onglets techniques obligatoires.

---

# 105. Golden C03 — Commerce / Medium master-detail

Tester autour d’un breakpoint candidat.

Le split n’apparaît que s’il conserve une largeur suffisante pour le field et le focus.

---

# 106. Golden C04 — Commerce / Wide

```text
NAV | FIELD | COMMANDE
```

Aucun panneau KPI permanent.

---

# 107. Golden C05 — Offer / disponibilité

Fixture :

```text
Kit rentrée 2027
35 USD
Offer active
Capacity limitée
Disponible maintenant
```

et variante :

```text
Offer active
mais Capacity épuisée
```

Le visuel doit clairement distinguer les deux.

---

# 108. Golden C06 — Payment confirmé, fulfillment non accompli

Fixture critique :

```text
COM-493
Paiement confirmé
Préparation terminée
Retrait non encore effectué
```

Acceptance : aucun « Terminé » global.

---

# 109. Golden C07 — Offline

Afficher snapshot + fraîcheur.

Les actions autoritatives doivent être limitées ou préparées sans faux succès.

---

# 110. Golden C08 — Partial failure

Orders disponibles, Payment temporairement indisponible.

La page reste Commerce.

---

# 111. Golden C09 — Permission change

Une commande devenue non visible disparaît sans fuite d’information.
Les autres restent stables.

---

# 112. Golden C10 — Distribution avec Occurrence → Jour J

Fixture : séance de distribution aujourd’hui.

```text
Commerce
→ Distribution kits rentrée
→ Occurrence
→ Ouvrir Jour J
```

Jour J reste occurrence-scoped.

---

# 113. Matrice des états Commerce

| État | Racine | N2 | Action |
|---|---|---|---|
| content | structure + continuité | détail owner-backed | selon capability |
| calm | pas d’action urgente | profondeur disponible | pas d’action artificielle |
| empty | aucun Commerce réel | n/a | création si autorisée |
| filtered empty | aucun résultat | n/a | modifier filtre |
| loading | snapshot si disponible | préserver contenu | discret |
| offline snapshot | contenu + fraîcheur | snapshot | actions sensibles limitées |
| offline no snapshot | explication | n/a | retry plus tard |
| stale | contenu connu marqué | prudence | revalidation |
| partial failure | sections restantes | erreur localisée | retry local |
| permission loss | retrait ciblé | fermeture si nécessaire | aucune mutation |

---

# 114. Anti-features spécifiques Commerce

Commerce ne doit pas devenir :

- ERP générique ;
- logiciel comptable ;
- caisse universelle ;
- marketplace infinie ;
- feed de produits ;
- gestion de stock parallèle à Capacity ;
- moteur de livraison universel ;
- moteur de Payment ;
- CRM ;
- tableau de KPI permanent ;
- kanban générique ;
- second Journey ;
- second Obtention ;
- second Readiness ;
- système où Order = fulfillment ;
- système où Payment = fulfillment ;
- système où Offer active = disponible ;
- système où tout objet commercial devient une Activity artificielle.

---

# 115. Invariants consolidés

1. Commerce parle le langage du résultat commercial réel.
2. Offer, Order, Payment, Capacity et fulfillment restent distincts.
3. Payment confirmé ne vaut jamais accomplissement par défaut.
4. Order confirmée ne vaut jamais accomplissement par défaut.
5. Offer active ne garantit pas la disponibilité actuelle.
6. Capacity répond à combien ; elle n’est pas dupliquée comme stock universel.
7. Obtention possède le sens de ce qui doit être réellement obtenu lorsqu’elle est utilisée.
8. Activity reste l’unité structurée de possibilité, pas la page Commerce.
9. Occurrence n’est créée que pour une réalisation temporelle réelle.
10. Journey reste le parcours du bénéficiaire quand il existe.
11. Requirements, Forms, Proof, Access et Transport restent leurs propriétaires.
12. Presentation représente ; elle ne possède pas.
13. L’archétype n’accorde aucune Permission.
14. Assignment n’accorde aucune autorité implicite.
15. Un filtre de responsabilité ne change jamais l’autorité.
16. La racine n’est pas un dashboard.
17. La racine peut être dense sans devenir technique.
18. L’historique ne domine pas la continuité active.
19. Aucun faux succès offline.
20. Les mutations sensibles sont revalidées côté autoritatif.
21. La concurrence sur Capacity et Order est traitée serveur.
22. Les informations privées restent minimum-disclosure.
23. Le client n’infère pas l’état global depuis un snapshot ancien.
24. Back / Resume préservent le contexte.
25. Wide adapte la géométrie, pas la vérité.
26. No Orphan Media s’applique.
27. Jour J appartient à une Occurrence, jamais au Commerce entier.
28. Now peut signaler une conséquence Commerce sans posséder la vérité.
29. Piloter analyse sans remplacer Commerce.
30. « Terminé » doit avoir une base métier défendable.

---

# 116. Points volontairement ouverts

Restent ouverts :

1. wire final spécialisé Commerce, s’il devient nécessaire ;
2. éventuel endpoint dédié racine Commerce versus projection Space Work partagée ;
3. noms exacts des capabilities nouvelles ;
4. seuil exact master-detail Medium/Wide ;
5. représentation détaillée du fulfillment selon les modes d’Obtention ;
6. UX finale de création Offer + Obtention ;
7. profondeur finale de la préparation commerciale ;
8. stratégie offline des données financières sensibles ;
9. granularité de fraîcheur Payment/Capacity ;
10. représentation finale des promotions ;
11. règles de carte pour plusieurs points de remise ;
12. visual design final des rows et cards ;
13. animations ;
14. microcopy finale ;
15. métriques Analytics finales.

Ces points ne doivent pas empêcher l’implémentation de la grammaire fondamentale.

---

# 117. Critères de sortie du contrat UX Commerce

Le contrat est suffisamment fermé si :

- N1 distingue continuité et structure ;
- Offer et Order sont lisibles sans jargon backend ;
- paiement et fulfillment sont visuellement distincts ;
- disponibilité peut être honnêtement exprimée ;
- Capacity reste propriétaire de la quantité partagée ;
- N2 Commande montre la progression réelle vers le résultat ;
- création est contextuelle ;
- recherche et filtres sont humains ;
- Compact/Medium/Wide conservent la vérité ;
- offline/stale/partial error sont définis ;
- authority et privacy sont définies ;
- handoffs vers owners, Now, Piloter et Jour J sont clairs.

---

# 118. Critères d’implémentation serveur

Une implémentation crédible doit :

- partir des owners actuels ;
- ne créer aucun modèle UX persistant inutile ;
- fournir actor Space + viewer Profile ;
- appliquer permissions et Mandates avant projection ;
- distinguer structure et continuité ;
- projeter Offers et Orders de façon traçable ;
- permettre de représenter Payment sans le confondre avec Order ;
- permettre de représenter Capacity sans duplication ;
- fournir freshness / coverage suffisantes ;
- fournir capabilities ;
- fournir owner handoffs ;
- garder `Cache-Control: private, no-store` sur projections sensibles si le contrat runtime l’exige ;
- tester IDOR ;
- tester concurrence/idempotence là où pertinente ;
- ne pas merger avec CI rouge.

---

# 119. Critères d’implémentation Flutter

Flutter doit :

- rendre depuis le store local lorsque possible ;
- ne pas recalculer l’autorité ;
- ne pas inférer fulfillment ;
- conserver query/filter/selection ;
- gérer loading/offline/stale/partial ;
- préserver N1 → N2 → owner depth ;
- revalider les actions sensibles ;
- supporter textScale ;
- produire les Goldens C01–C10 ;
- éviter un composant universel `CommerceCard` utilisé partout sans discernement.

---

# 120. Critères d’implémentation Web

Le Web doit :

- préserver la même grammaire ;
- éviter les tables administratives comme racine par défaut ;
- supporter progressive disclosure ;
- supporter recherche/filtres sans exposer la taxonomie ;
- préserver retour et sélection autant que possible ;
- rendre les actions selon capability ;
- respecter la confidentialité ;
- intégrer N2 sans casser le shell Space.

---

# 121. Tests UX minimum

## Recognition test

En 500 ms :

```text
où suis-je ?
→ Commerce

qu’est-ce qui domine ?
→ ce qui doit réellement avancer
```

## Blur test

Le dominant doit rester une réalité commerciale/actionnable, pas le chrome ni les KPI.

## Competition test

Un montant et une conséquence ne doivent pas être simultanément P3 sans raison.

## Deletion test

Retirer chaque élément ; conserver seulement ceux qui aident compréhension ou action.

## Adaptive test

Passer Compact → Medium → Wide → Compact sans perdre la vérité ni la sélection.

## Freshness test

Un vieux snapshot Capacity/Payment ne doit pas être présenté comme vérité fraîche.

## Authority test

Changer les Permissions doit changer les entrées/actions visibles sans fuite d’information.

## Fulfillment test

Une commande payée mais non remise ne doit pas être annoncée comme accomplie.

---

# 122. Scénarios de référence

## 122.1. Commerce calme

```text
Commerce

Aucune commande ne demande votre attention.

Offres
12 actives
```

## 122.2. Commande à traiter

```text
COM-493
Kit scolaire ×2
Paiement attendu

[ Ouvrir ]
```

## 122.3. Commande payée, à préparer

```text
COM-493
Paiement confirmé
Préparation à faire

[ Préparer ]
```

si cette action est réellement portée et autorisée.

## 122.4. Commande prête à remettre

```text
COM-488
Prête
Retrait aujourd’hui · Centre-ville

[ Ouvrir ]
```

## 122.5. Offer active mais indisponible

```text
Kit rentrée 2027
35 USD
Actuellement indisponible
```

La cause n’est montrée que si elle est connue et appropriée.

## 122.6. Distribution avec Jour J

```text
Distribution de kits
Session du 12 octobre

[ Ouvrir Jour J ]
```

si l’Occurrence est devenue admissible à Jour J.

## 122.7. Location

```text
Location groupe électrogène
Demande confirmée
Acompte reçu
Matériel à préparer
Remise le 15 octobre
```

Le wording parle location, pas achat.

## 122.8. Offline

```text
Commerce
Dernière mise à jour · 09:15

COM-493
Paiement confirmé à la dernière synchronisation
```

Aucune affirmation Live supplémentaire.

---

# 123. Formulation canonique finale

> **Commerce est la porte Métier d’un Space `commerce` qui rend visible et opérable la chaîne réelle par laquelle ce que le Space met à disposition devient une demande ou une commande, est confirmé, préparé, rendu disponible, éventuellement payé, remis ou réalisé, puis reconnu comme réellement accompli lorsque le contrat métier le permet. Commerce compose les vérités d’Activity, Obtention, Offer, Order, Payment, Capacity, Journey, Occurrence, Access, Transport, Requirements, Proof et autres owners sans les dupliquer. Il privilégie le langage humain, la prochaine conséquence utile, la distinction entre transaction et résultat, la divulgation minimale, l’autorité serveur et la continuité local-first. Il ne devient ni marketplace générique, ni ERP, ni caisse, ni comptabilité, ni moteur de paiement.**

---

# 124. Formule courte

```text
COMMERCE
=
ce que nous rendons disponible
+
ce qui est demandé / commandé
+
ce qui doit être préparé
+
ce qui doit être remis / réalisé
+
la vérité distincte du paiement
+
la reconnaissance honnête du résultat réel
```

Et l’invariant de fermeture est :

```text
ORDER
≠ PAYMENT
≠ FULFILLMENT
```

La personne doit pouvoir agir dans Commerce sans avoir à comprendre cette séparation technique ; Makolo doit la préserver pour elle.