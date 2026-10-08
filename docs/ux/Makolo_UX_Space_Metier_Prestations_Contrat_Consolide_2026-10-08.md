# Makolo — Space Métier `service_provider` / **Prestations**
## Contrat UX consolidé — N1, N2/N3, hiérarchie, représentations, états, adaptive, local-first, API et handoffs

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence pour l’archétype Space `service_provider`  
**Porte visible :** **Prestations**  
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
service_provider
```

Le libellé visible primaire est :

```text
Prestations
```

L’icône sémantique candidate fournie par l’architecture Space est :

```text
handshake
```

Le document ne redéfinit pas le domaine Service.

Il ne crée pas :

- un modèle `Prestation` parallèle si `Activity + ServiceDetails` portent déjà l’offre de service ;
- un modèle `DossierPrestation` universel si une `Journey` de workflow `SERVICE` porte déjà la démarche ;
- un deuxième `Requirement` ;
- un deuxième moteur de Forms ;
- un deuxième système de pièces ou d’Artifacts ;
- un deuxième Payment ;
- un deuxième Assignment ;
- un deuxième Blocker ;
- un deuxième Readiness ;
- un task manager générique ;
- un CRM parallèle ;
- un workflow UX persistant propriétaire de la vérité.

Il répond à la question :

> **Comment permettre à un Space prestataire de voir, préparer, traiter et délivrer ses prestations de manière immédiatement compréhensible, sans lui demander de naviguer dans Journey, Requirements, Payment, Artifacts ou Assignments comme dans des modules séparés ?**

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
- les contrats Space Métier Transport et Programmes consolidés ;
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

Elle introduit néanmoins une direction cohérente avec ce contrat :

```text
structure métier
≠ continuité métier
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

Comportement présent dans une branche/PR ouverte mais non fusionnée.

### OUVERT

Décision volontairement non figée faute de nécessité ou de vérité runtime suffisante.

---

# 3. Place de Prestations dans le shell Space

Le shell Space devient, pour cet archétype :

```text
Maintenant | Découvrir | [Makolo Mark] | Prestations | Nous
```

La question générale Métier reste :

> **Qu’est-ce que nous faisons réellement exister, préparer, exécuter et délivrer ?**

Pour `service_provider`, elle devient :

> **Quelles prestations proposons-nous, quelles demandes devons-nous traiter, qu’est-ce qui bloque, et qu’est-ce qui doit réellement être délivré ?**

`Prestations` est la surface durable de travail.

Elle n’est pas un raccourci vers :

```text
Services
Journey
Requirements
Payments
CRM
```

Le vocabulaire visible reste celui du service rendu.

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

Pour Prestations, ce contrat fixe :

```text
Prestations
→ service réel + conduite du dossier
```

Développé :

> **Prestations montre ce que le Space sait réellement rendre comme service, puis les demandes et dossiers qu’il doit faire progresser jusqu’au résultat attendu.**

La surface peut être dense lorsque le travail l’exige.

Elle ne doit pas devenir :

- un ticketing générique ;
- un CRM de cases ;
- un Kanban permanent ;
- un gestionnaire de tâches ;
- un dashboard KPI ;
- un système de workflow visible ;
- un écran “Journey” renommé ;
- un dossier documentaire sans finalité.

---

# 5. Invariant principal : prestation proposée ≠ dossier engagé

Deux réalités visibles doivent rester distinctes :

```text
PRESTATION PROPOSÉE
→ ce que le Space est capable de rendre
```

et :

```text
DOSSIER / DEMANDE
→ une prestation effectivement engagée pour une personne ou un bénéficiaire
```

Une prestation peut exister sans demande actuelle.

Une demande peut continuer même si la prestation n’a aucune urgence actuelle.

Le design ne doit pas mettre ces deux réalités dans une seule liste avec le même statut.

---

# 6. Prestation visible ≠ nouveau modèle métier

Une prestation visible en N1 peut être soutenue par :

```text
Activity
+
ServiceDetails
+
configuration propriétaire utile
```

L’UX peut dire :

```text
Accompagnement visa
Orientation carrière
Préparation d’entretien
Accompagnement documentaire
```

sans exposer :

```text
Activity
ServiceDetails
ServiceKind
```

La Presentation représente la prestation.

Elle ne la possède pas.

---

# 7. Demande / Dossier visible ≠ Journey affiché brut

Une demande de prestation réellement engagée peut être soutenue par :

```text
Journey(workflow=SERVICE)
+
ServiceJourneyContext
+
Steps
+
Requirements / assessments
+
Artifacts
+
Assignments
+
Blockers
+
Payment éventuel
+
Submissions / outcomes
```

Mais l’utilisateur doit voir une seule réalité humaine cohérente :

```text
Dossier Visa Canada — Marie Kalala
```

et non huit cartes concurrentes.

---

# 8. Le Dossier visible est une composition UX

Le terme `Dossier` est utilisé ici dans son sens Makolo : objectif actif composé.

Il ne devient jamais un task manager générique.

Une profondeur Dossier peut composer :

```text
personne concernée
Requirements
étapes utiles
responsable
pièces / ressources
Payment
résultat
```

La composition ne transfère jamais implicitement :

- Permission ;
- Mandate ;
- accès aux pièces privées ;
- accès aux notes internes ;
- capacité à décider un paiement ;
- autorité sur un Requirement ;
- autorité sur une revue.

---

# 9. Structure durable et continuité

Prestations doit séparer mentalement :

```text
STRUCTURE
→ prestations proposées
```

et :

```text
CONTINUITÉ
→ demandes / dossiers réellement engagés
```

Les états `À préparer`, `En traitement`, `Bloquées`, `À délivrer` et `Terminées` décrivent la continuité de dossiers lorsque les owners l’établissent.

Ils ne doivent pas être appliqués artificiellement à toute prestation proposée.

---

# 10. Architecture cognitive générale

```text
PRESTATIONS N1
│
├── CONTEXTE SPACE
│   ├── Space
│   ├── responsabilité éventuelle
│   └── recherche / filtres
│
├── CONTINUITÉ
│   ├── Demandes à traiter
│   ├── À préparer
│   ├── En traitement
│   ├── Bloquées
│   ├── À délivrer
│   └── Terminées / Histoire
│
├── STRUCTURE
│   └── Prestations proposées
│
└── DEPTH
    ├── PRESTATION N2
    ├── DOSSIER N2
    └── OWNER DEPTH N3
```

Toutes les sections ne doivent pas être rendues si elles n’existent pas réellement.

---

# 11. N1 — objectif

En entrant dans Prestations, la personne doit pouvoir comprendre rapidement :

1. quels dossiers nécessitent réellement de l’attention ou du travail ;
2. quels dossiers sont en traitement ;
3. lesquels sont bloqués ;
4. lesquels approchent du résultat ou de la délivrance ;
5. quelles prestations le Space propose durablement ;
6. ce qu’elle peut ouvrir ou créer selon son autorité.

---

# 12. N1 — composition Compact de référence

Composition candidate :

```text
┌──────────────────────────────┐
│ Makolo · Acme Services   👤  │
│ Prestations                   │
│ Toutes mes responsabilités ▾ │
│                              │
│ Demandes à traiter           │
│ ┌──────────────────────────┐ │
│ │ Visa Canada              │ │
│ │ Marie Kalala             │ │
│ │ Revue initiale attendue  │ │
│ └──────────────────────────┘ │
│                              │
│ En traitement                │
│ ┌──────────────────────────┐ │
│ │ Orientation carrière     │ │
│ │ Jean M.                  │ │
│ │ Entretien préparatoire   │ │
│ └──────────────────────────┘ │
│                              │
│ Bloquées                     │
│ ┌──────────────────────────┐ │
│ │ Dossier admission        │ │
│ │ Preuve manquante         │ │
│ └──────────────────────────┘ │
│                              │
│ Prestations proposées        │
│ Accompagnement visa          │
│ Orientation carrière         │
│                              │
└──────────────────────────────┘
```

Ce schéma est une grammaire UX, pas une maquette pixel-perfect.

---

# 13. N1 — ordre perceptif

L’ordre doit être commandé par la capacité d’agir et la continuité réelle.

Référence :

```text
DOSSIER AVEC CONSÉQUENCE UTILE       P2/P3
ACTION LÉGITIME PROCHAINE            P2/P3

IDENTITÉ DE LA PRESTATION            P2
PERSONNE / BÉNÉFICIAIRE              P1/P2 selon confidentialité
ÉTAT HUMAIN                           P1/P2
ÉCHÉANCE ÉTABLIE                     P1

MÉTADONNÉES TECHNIQUES               P0
```

Deux éléments ne doivent pas se disputer P3 simultanément sans raison.

---

# 14. Section « Demandes à traiter »

Cette section représente les demandes réellement entrées dans un état nécessitant une prise en charge légitime.

Exemples humains :

```text
Nouvelle demande
À revoir
Décision attendue
Informations reçues
```

Elle ne signifie pas :

```text
notification non lue
```

ou :

```text
JourneyStatus == X affiché brut
```

La section n’existe que si des faits owners la soutiennent.

---

# 15. Section « À préparer »

Cette section peut contenir des dossiers pour lesquels une préparation réelle reste nécessaire avant traitement ou délivrance.

Exemples :

- données à compléter ;
- plan à matérialiser ;
- conditions à vérifier ;
- paiement attendu avant démarrage si le contrat l’exige ;
- pièces nécessaires ;
- prochaine étape non encore démarrée.

Une simple ancienneté ne suffit pas.

---

# 16. Section « En traitement »

Cette section représente les dossiers dont le travail réel est engagé.

Exemples :

```text
étape en cours
revue en cours
soumission préparée
traitement externe connu
```

`En traitement` n’est pas un alias universel de `JourneyStatus.IN_PROGRESS`.

L’owner doit justifier l’état.

---

# 17. Section « Bloquées »

Un dossier peut apparaître ici lorsqu’un blocker réel empêche une transition significative.

L’UX doit distinguer :

```text
BLOQUÉ
≠
EN ATTENTE
≠
INCONNU
≠
RISQUE
```

Exemples de blocage :

- pièce requise refusée ;
- information indispensable absente ;
- décision obligatoire impossible ;
- paiement requis non résolu ;
- dépendance explicitement bloquante.

La cause doit être lisible.

---

# 18. Section « À délivrer »

Cette section existe lorsqu’un résultat réel est suffisamment prêt pour devoir être remis, confirmé, exécuté ou finalisé.

Exemples contextuels :

```text
Dossier prêt à remettre
Résultat à communiquer
Attestation à délivrer
Accompagnement prêt pour la dernière étape
```

Elle ne doit pas être inventée si le domaine Service ne fournit pas de sémantique de délivrance explicite.

---

# 19. Terminées

Les dossiers terminés appartiennent d’abord à l’histoire utile du métier.

La racine N1 peut montrer :

```text
Terminées récemment
```

si cela aide réellement la continuité.

Elle ne devient pas une archive infinie.

L’historique complet peut être une profondeur secondaire.

---

# 20. Prestations proposées — structure durable

Cette section montre ce que le Space sait réellement proposer.

Exemple :

```text
Prestations proposées

Accompagnement de candidature
Orientation éducative
Préparation d’entretien
Accompagnement documentaire
```

Une prestation active n’est pas automatiquement `En traitement`.

Invariant :

```text
PRESTATION ACTIVE
≠
DOSSIER ACTIF
```

---

# 21. Représentation d’une prestation en N1

Une prestation structurelle peut utiliser une row ou une unité compacte.

Elle peut montrer :

```text
NOM
RÉSUMÉ COURT
mode d’entrée pertinent si établi
état de disponibilité si owner-backed
```

Elle ne doit pas montrer par défaut :

- nombre total de Steps ;
- identifiants ;
- nom de template ;
- code `ServiceKind` ;
- politiques techniques ;
- métriques sans action.

---

# 22. Représentation d’un dossier en N1

Une row de dossier doit pouvoir répondre à :

```text
QUOI ?
→ quelle prestation / quel objectif ?

POUR QUI ?
→ personne concernée si autorisée

OÙ EN EST-ON ?
→ synthèse humaine

QU’EST-CE QUI COMPTE ?
→ blocage / prochaine action / échéance utile
```

Exemple :

```text
Visa Canada
Marie Kalala

Pièce d’identité reçue.
Justificatif financier à revoir.

[ Ouvrir le dossier ]
```

---

# 23. Personne concernée et divulgation minimale

Un dossier peut concerner :

- le Profile bénéficiaire ;
- un bénéficiaire externe lorsque le service le permet.

La racine ne doit jamais exposer plus d’identité que nécessaire.

Selon l’autorité, elle peut montrer :

```text
Marie Kalala
```

ou une représentation minimale suffisante.

Elle ne doit pas exposer email, téléphone, documents ou données privées simplement parce qu’ils existent.

---

# 24. Pas de pourcentage arbitraire

Prestations ne doit pas produire automatiquement :

```text
Dossier 73 % terminé
```

à partir du nombre de Steps.

La progression humaine peut être non linéaire.

Préférer :

```text
3 éléments réglés
1 condition bloque encore la soumission
```

si ces faits sont réellement établis.

---

# 25. Search Prestations

La recherche peut porter sur le monde métier autorisé.

Exemples :

```text
"Visa"
"Marie"
"orientation"
référence métier connue
```

La recherche doit respecter la confidentialité et l’autorité.

Elle ne doit pas révéler l’existence d’un dossier hors scope.

---

# 26. Filtres Prestations

Filtres humains candidats :

- À traiter ;
- En traitement ;
- Bloqués ;
- À délivrer ;
- Prestation ;
- Responsable ;
- période / échéance lorsque pertinente ;
- responsabilité courante.

Ne pas exposer directement :

```text
Journey.status
WorkflowKind
ServiceKind
AssessmentStatus
```

comme taxonomie obligatoire de l’écran.

---

# 27. Responsabilité comme lens

La personne peut choisir une responsabilité lorsque le runtime l’établit :

```text
Toutes mes responsabilités
Accompagnement
Revue
Administration
...
```

Cette lens peut réduire la lecture.

Elle ne crée jamais une Permission.

Invariant :

```text
Assignment = responsabilité
Mandate / Permission = autorité
```

---

# 28. Création contextuelle

La porte peut proposer :

```text
Nouvelle prestation
```

si la capability existe réellement.

Selon le runtime futur, elle peut aussi proposer une entrée humaine du type :

```text
Nouvelle demande
```

uniquement si le domaine Service fournit une opération owner-backed légitime.

Ne jamais exposer un menu universel :

```text
+ Activity
+ Journey
+ Requirement
+ Artifact
```

---

# 29. Placement de la création

La création ne doit pas concurrencer Makolo Mark.

Options acceptables :

- action discrète de header ;
- action dans la section structurelle ;
- empty state contextuel ;
- menu contextuel limité aux capabilities.

Pas de FAB `+` générique si le centre visuel Makolo Mark existe déjà.

---

# 30. Makolo Mark → Prestations

Dans un Space service_provider, le Mark peut comprendre des intentions telles que :

```text
Crée une nouvelle prestation d’accompagnement documentaire.
```

ou :

```text
Ajoute ce document au dossier de Marie.
```

Mais il doit encore vérifier :

- la cible ;
- l’autorité ;
- la destination owner ;
- la sensibilité du document ;
- le besoin éventuel de clarification ;
- la classe d’opération local-first.

Le Mark ne devient pas propriétaire du dossier.

---

# 31. N2 — principe général

N2 conserve une identité humaine forte.

Il ne devient pas automatiquement un écran technique.

Les deux grandes profondeurs sont :

```text
PRESTATION N2
```

et :

```text
DOSSIER N2
```

---

# 32. N2 Prestation — objectif

La profondeur d’une prestation répond à :

> **Que rendons-nous comme service, comment cette prestation fonctionne-t-elle et quelles demandes réelles y sont liées ?**

Elle peut donner accès à :

- description ;
- politique d’entrée exprimée humainement ;
- variantes / configuration owner-backed ;
- demandes actives ;
- éléments de préparation structurelle ;
- configuration si l’autorité le permet.

---

# 33. N2 Prestation — composition candidate

```text
← Prestations

Accompagnement candidature

DESCRIPTION
Ce que nous proposons

DEMANDES EN COURS
12 dossiers visibles

ENTRÉE
Comment une demande commence

PARCOURS DE RÉFÉRENCE
si légitime et utile

FORMULAIRE D’ENTRÉE
si configuré

ACTIONS
Modifier / configurer si autorisé
```

Les détails de template ne doivent pas dominer la lecture.

---

# 34. Configuration d’une prestation

Le runtime Services possède notamment des concepts de configuration :

- type de service ;
- policy d’Opportunity ;
- policy d’intake ;
- bénéficiaire externe éventuel ;
- completion policy ;
- templates versionnés ;
- questions d’intake.

Ces éléments sont légitimes en profondeur professionnelle.

Ils ne doivent pas être visibles sur N1 comme jargon.

---

# 35. Templates de parcours

Un template de service peut être une mécanique réelle de préparation.

L’UX doit le présenter comme :

```text
Parcours de référence
```

ou vocabulaire métier équivalent.

Pas comme :

```text
ServicePlanTemplate v3
```

sauf dans une profondeur explicitement technique destinée à un opérateur expert.

---

# 36. N2 Dossier — objectif

Le Dossier N2 répond à :

> **Pour cette personne et cette prestation, où en est le travail réel, qu’est-ce qui reste, qu’est-ce qui bloque et quel résultat cherche-t-on à obtenir ?**

Il doit réduire la reconstruction mentale.

---

# 37. N2 Dossier — composition de référence

```text
← Prestations

Visa Canada
Marie Kalala

SYNTHÈSE
Dossier en préparation.
Justificatif financier à revoir.

PROCHAIN MOUVEMENT
[ Revoir le justificatif ]

CONDITIONS
3 satisfaites · 1 à revoir

ÉTAPES
Préparation documentaire
Soumission
Suivi

RESPONSABILITÉ
Conseiller principal

PIÈCES
Documents utiles selon autorité

PAIEMENT
si pertinent

RÉSULTAT
état owner-backed

HISTORIQUE UTILE
si nécessaire
```

Toutes les sections sont conditionnelles.

---

# 38. Dossier — Human Context

Le titre principal doit être une réalité humaine.

Exemples :

```text
Visa Canada — Marie Kalala
Candidature Master — Jean Mbuyi
Orientation carrière — Sarah K.
```

Éviter :

```text
Journey 5f9e...
Service case #183
```

---

# 39. Dossier — objectif

`ServiceJourneyContext.objective` peut soutenir une formulation humaine du but.

Exemple :

```text
Obtenir un dossier complet pour la candidature de septembre.
```

L’objectif ne doit pas être inventé si absent.

---

# 40. Dossier — current outcome

Le domaine Services peut posséder un résultat courant contrôlé.

L’UX peut représenter des états tels que :

```text
Non soumis
Soumis
Réception confirmée
En revue
Action requise
Entretien
Réussi
Non retenu
Retiré
Inconnu
```

Le vocabulaire final doit rester adapté au service.

Le client ne doit jamais déduire seul ce résultat.

---

# 41. Dossier — Requirements

Les Requirements doivent répondre :

```text
qu’est-ce qui est attendu ?
qu’est-ce qui est établi ?
qu’est-ce qui manque ?
qu’est-ce qui doit être revu ?
```

Ils ne deviennent pas un simple checklist visuel si la vérité est plus riche.

Un document présent n’équivaut pas automatiquement à Requirement satisfait.

---

# 42. Requirement assessment

Lorsqu’une évaluation existe, l’UX peut distinguer :

```text
non évalué
satisfait / accepté selon owner
insuffisant / à revoir selon owner
inconnu
```

Le vocabulaire exact dépend du domaine Requirements.

La couleur seule ne doit jamais porter le sens.

---

# 43. Evidence / pièces

Une pièce ou preuve doit rester liée à ce qu’elle démontre.

Invariant :

```text
posséder une pièce
≠
la retrouver
≠
satisfaire un Requirement
```

L’écran peut montrer :

```text
Justificatif financier
Pièce reçue · revue nécessaire
```

si l’owner l’établit.

---

# 44. Sensibilité des pièces

Le runtime Services applique des sélecteurs de visibilité aux Artifacts.

Le design doit donc accepter :

```text
Dossier visible
+
pièce non visible
```

sans transformer cela en incohérence.

La section peut dire :

```text
Certaines pièces ne sont pas accessibles dans votre rôle.
```

si une telle explication est permise.

---

# 45. Étapes utiles

Les JourneyStep peuvent soutenir le déroulement réel.

Mais l’UX ne doit pas faire croire que le dossier est seulement une suite de tâches.

Une étape peut être montrée lorsqu’elle aide à comprendre ou agir.

Exemple :

```text
Préparer le dossier
→ en cours

Soumettre
→ à venir
```

Pas de timeline si les relations ne sont pas réellement temporelles.

---

# 46. Étape ≠ Checkpoint

Invariant :

```text
JourneyStep
≠
Checkpoint opérationnel
```

Une prestation ne doit pas emprunter le vocabulaire de Jour J simplement parce qu’elle a des étapes.

---

# 47. Responsabilité dans un Dossier

Le runtime peut avoir des `JourneyAssignment`.

La profondeur peut présenter :

```text
Responsable principal
Autres responsabilités utiles
```

Mais :

```text
Assignment
≠ Permission
```

Affecter une responsabilité n’accorde pas automatiquement la capacité de voir ou modifier toute donnée sensible.

---

# 48. Blockers

Un blocker réel doit être attaché à ce qu’il bloque.

Le Dossier peut afficher :

```text
Blocage
Justificatif financier rejeté.
Empêche la soumission.
```

Il doit être possible de distinguer :

- blocker actif ;
- blocker résolu ;
- attente ;
- risque ;
- inconnue.

---

# 49. Notes

Les notes internes ne doivent jamais être fusionnées avec les messages au bénéficiaire.

Le runtime distingue leur visibilité.

Le N2 peut afficher une section Notes seulement si :

- elle aide le travail ;
- le viewer possède la visibilité ;
- la confidentialité est explicite.

---

# 50. Payment

Un Payment peut être pertinent dans le Dossier.

Mais :

```text
Payment confirmé
≠ prestation accomplie
```

Le Payment doit répondre à sa question propre.

Le résultat du service reste distinct.

---

# 51. Preuve de paiement

Si une preuve externe doit être vérifiée, le design doit distinguer :

```text
preuve reçue
preuve vérifiée
preuve rejetée
paiement réellement confirmé
```

Ne jamais afficher `Payé` parce qu’un fichier a été déposé.

---

# 52. Submissions

Une prestation peut comporter une soumission externe.

Le Dossier peut montrer :

```text
Soumission envoyée le ...
Référence ...
Réponse attendue
```

seulement lorsque ces faits sont établis.

Une tentative d’envoi locale ne devient pas automatiquement une soumission confirmée.

---

# 53. Outcome timeline

Le domaine peut conserver des événements de résultat.

L’UX peut présenter une chronologie si elle correspond à une vraie séquence causale ou temporelle utile.

Elle ne doit pas utiliser une timeline uniquement parce que des dates existent.

---

# 54. N3 — principe

N3 est la profondeur où l’on peut devenir plus précis et propriétaire.

Exemples :

```text
Revoir une pièce
Démarrer une étape
Terminer une étape
Affecter un responsable
Créer / résoudre un blocker
Vérifier une preuve de paiement
Décider une revue
Configurer la prestation
```

N3 ne doit pas réinventer l’action.

Il appelle l’owner réel.

---

# 55. N3 — action sensible

Une action sensible doit :

1. vérifier l’autorité côté serveur ;
2. montrer le niveau réellement atteint ;
3. gérer double soumission et idempotence lorsque pertinent ;
4. ne jamais conclure succès avant confirmation nécessaire ;
5. reprojeter le Dossier après succès.

---

# 56. N3 — pas de prison latérale

Sur Wide, un détail secondaire peut être présenté dans un pane.

Mais une action complexe ne doit pas être coincée dans un panneau trop étroit.

Si la tâche nécessite espace, lecture ou concentration :

```text
N3 → page / focus approprié
```

---

# 57. Prestations ↔ Maintenant

Prestations organise le monde durable du travail.

Maintenant sélectionne les conséquences qui méritent attention.

Exemple :

```text
Prestations
→ 86 dossiers visibles
```

Mais Now peut montrer seulement :

```text
3 dossiers attendent une décision aujourd’hui.
```

ou :

```text
Le dossier de Marie est bloqué avant soumission.
```

Même vérité owner-backed, question humaine différente.

---

# 58. Prestations ↔ Découvrir

Découvrir Space demande :

> Qu’est-ce qui pourrait nous aider à avancer ?

Il peut trouver :

- opportunité pertinente pour un client ou une prestation ;
- partenaire ;
- ressource ;
- financement ;
- autre possibilité légitime.

Lorsqu’une possibilité devient une prestation ou un dossier réel, le propriétaire reprend la vérité.

Découvrir ne devient pas le dossier.

---

# 59. Prestations ↔ Nous

`Prestations` répond :

> **Que faisons-nous réellement pour les bénéficiaires ?**

`Nous` répond :

> **Qui sommes-nous et comment sommes-nous organisés ?**

Équipe, Mandates et organisation générale restent principalement dans Nous.

Le responsable d’un Dossier peut apparaître dans Prestations parce qu’il est nécessaire à l’action.

---

# 60. Prestations ↔ Clients & partenaires

Pour `service_provider`, la surface relationnelle peut être nommée :

```text
Clients & partenaires
```

Prestations n’est pas un CRM.

Une personne apparaît dans Prestations parce qu’elle est reliée à une prestation réelle.

Sa relation globale avec le Space appartient à la profondeur relationnelle appropriée.

---

# 61. Prestations ↔ Piloter

Prestations répond :

> **Que devons-nous traiter et délivrer ?**

Piloter répond :

> **Est-ce que cela fonctionne et qu’est-ce qui change ?**

Exemple :

```text
Prestations
→ Dossier X est bloqué.

Piloter
→ 24 % des dossiers de cette prestation bloquent au même Requirement.
```

Le KPI n’a pas besoin d’être sur N1 Prestations.

---

# 62. Prestations ↔ Historique

Une prestation terminée ou un Dossier accompli peut rester inspectable.

La racine peut montrer une histoire récente utile.

Elle ne doit pas conserver indéfiniment tout le passé dans la continuité active.

---

# 63. Prestations ↔ Jour J

Une prestation ne devient pas automatiquement Jour J.

Jour J appartient à une `Occurrence` devenue actuelle.

Donc :

```text
Dossier Service
≠ Jour J
```

Mais si une réalité de service possède une Occurrence légitime :

```text
Prestation
→ Occurrence réelle
→ Jour J
→ Live éventuel
```

Le handoff doit provenir de la relation canonique, pas du seul fait qu’une étape a une date.

---

# 64. États — matrice minimale

| État | Prestations |
|---|---|
| Initial | shell + structure minimale connue |
| Loading | skeleton localisé ou contenu existant |
| Content | dossiers + prestations selon autorité |
| Empty | aucun élément réel dans le scope |
| Calm | prestations existent, aucun dossier ne demande de mouvement |
| Success | niveau réellement confirmé |
| Error | localisé si possible |
| Offline | snapshot utile avec fraîcheur |
| Stale | contenu conservé, actualité signalée |
| Permission denied | retirer ou borner proprement |
| Refresh | conserver contexte |
| Back | restaurer sélection / scroll / filtres |
| Resume | revalider discrètement ce qui peut avoir changé |

---

# 65. Initial

Le shell ne doit pas flasher un écran vide si un snapshot local existe.

Si aucune projection n’est disponible :

```text
Prestations
Chargement…
```

avec skeleton minimal structuré.

---

# 66. Loading

Sous réponse courte, éviter le skeleton visible.

Lors d’un refresh avec contenu existant :

```text
contenu actuel
+
indicateur discret
```

Pas :

```text
contenu → vide → skeleton → contenu
```

---

# 67. Content

L’état nominal combine :

```text
CONTINUITÉ RÉELLE
+
STRUCTURE PRESTATIONS
```

Les sections vides inutiles peuvent disparaître.

---

# 68. Empty total

Un Space tout neuf peut voir :

```text
Prestations

Aucune prestation n’est encore configurée.

[ Nouvelle prestation ]
```

uniquement si la capability de création existe.

Sinon :

```text
Aucune prestation visible dans votre périmètre.
```

Ne pas créer une fausse prestation d’exemple.

---

# 69. Calm avec prestations

Cas fréquent :

```text
Prestations proposées
3

Aucune demande ne nécessite d’intervention actuellement.
```

Il ne faut pas remplir la surface de statistiques artificielles.

---

# 70. Aucun dossier mais structure existante

Ce cas n’est pas `empty total`.

Exemple :

```text
Prestations

Aucune demande active.

Prestations proposées
- Visa
- Orientation
- Préparation entretien
```

---

# 71. Offline avec snapshot

Le client peut montrer ce qui a déjà été synchronisé, avec fraîcheur honnête.

Exemple :

```text
Hors connexion
Dernière mise à jour : 09:42
```

Les actions nécessitant autorité fraîche ou conflit global restent limitées.

---

# 72. Offline sans snapshot

Afficher une impossibilité locale compréhensible.

Pas de faux dossier vide.

Exemple :

```text
Les Prestations de ce Space ne sont pas encore disponibles sur cet appareil.
Reconnectez-vous pour les charger.
```

---

# 73. Stale

Une donnée ancienne n’est pas une erreur.

Elle peut rester visible avec prudence :

```text
État connu il y a 2 h
Actualisation nécessaire avant décision
```

Ne jamais traiter un ancien snapshot comme vérité actuelle pour Payment, Permission ou décision concurrente.

---

# 74. Erreur localisée

Si les pièces d’un Dossier échouent à charger mais que le reste existe :

```text
Dossier visible
+
Pièces momentanément indisponibles
```

Pas d’écran global de panne.

---

# 75. Permission loss

Lorsqu’une autorité disparaît :

- retirer les actions non autorisées ;
- revalider le contenu sensible ;
- ne pas laisser le store local conserver une capacité active ;
- préserver une explication minimale si possible ;
- retourner 404 privacy-safe lorsque nécessaire côté serveur.

---

# 76. Refresh

Le refresh doit conserver :

- scroll ;
- filtre ;
- responsabilité choisie ;
- query ;
- Dossier sélectionné ;
- profondeur N2 quand encore autorisée.

---

# 77. Back

Référence :

```text
Prestations N1
→ Dossier N2
→ Requirement N3
→ Back
→ Dossier N2 au même contexte
→ Back
→ Prestations N1 au même scroll / filtre
```

---

# 78. Resume

Après interruption :

1. restaurer le contexte local ;
2. afficher l’état connu ;
3. synchroniser discrètement ;
4. revalider l’autorité ;
5. retirer ou corriger localement si la vérité distante a changé.

---

# 79. Deep links

Destinations candidates :

```text
Space Prestations
Prestation N2
Dossier N2
profondeur owner autorisée
```

Un deep link doit vérifier :

- session ;
- Actor Context ;
- visibilité ;
- autorité ;
- destination de repli si la ressource n’est plus disponible.

---

# 80. Local-first

Le client installé peut conserver, lorsque la confidentialité le permet :

- projection Prestations ;
- prestations déjà connues ;
- dossiers déjà connus ;
- synthèses ;
- Steps autorisées ;
- Requirements connus ;
- pièces explicitement autorisées ;
- brouillons ;
- actions localement préparables.

Le client local ne devient pas l’autorité pour :

- Permission ;
- Mandate ;
- Payment ;
- décision de revue ;
- Capacity partagée ;
- état global ;
- conflit multi-acteurs ;
- résultat externe récent.

---

# 81. Classes d’opération

### A — locale

Exemples possibles :

- filtre ;
- recherche locale sur snapshot ;
- sélection ;
- expansion de détail déjà présent.

### B — locale puis synchronisée

Uniquement si le domaine garantit une synchronisation sûre.

### C — préparée localement puis confirmée à distance

Exemples :

- brouillon de note ;
- préparation d’un document ;
- formulaire avant soumission ;
- intention d’affectation.

### D — intrinsèquement distante

Exemples :

- vérifier une preuve de paiement ;
- décider une revue ;
- revalider Permission ;
- établir un état partagé récent ;
- transition concurrente sur un Dossier.

---

# 82. Pas de faux succès

Le feedback doit distinguer :

```text
préparé localement
enregistré
en attente de synchronisation
envoyé
en attente de confirmation
confirmé
accompli
```

Ne jamais dire :

```text
Dossier traité
```

si seule une action locale a été enregistrée.

---

# 83. Outbox

Une opération synchronisable importante acceptée localement doit survivre à la fermeture de l’app lorsque le contrat le permet.

Elle doit gérer :

- identity ;
- dépendances ;
- retry ;
- idempotence ;
- statut ;
- échec définitif ;
- confirmation distante.

---

# 84. Compact

Sur Compact :

```text
N1 collection structurée
→ tap
→ N2 page
→ N3 page / bottom sheet selon complexité
```

La navigation basse reste visible sur N1 et N2 ordinaires sauf immersion légitime.

---

# 85. Medium

Medium peut utiliser :

```text
liste / sections
+
apercu sélectionné
```

si les deux rôles cognitifs sont distincts et si la largeur reste suffisante.

Sinon rester single-pane.

---

# 86. Wide

Wide peut adopter un master/detail :

```text
RAIL
+
PRESTATIONS FIELD
+
DOSSIER FOCUS
```

La largeur ne doit pas ajouter automatiquement :

- KPI ;
- analytics ;
- graphes ;
- colonnes de CRM ;
- détails sensibles.

---

# 87. Very Wide

Very Wide sert principalement à préserver contexte et confort.

Une troisième zone n’est justifiée que lorsqu’elle répond à une fonction cognitive distincte.

Exemple possible :

```text
FIELD
+
DOSSIER
+
DOCUMENT / REVIEW FOCUS
```

mais jamais pour remplir l’espace.

---

# 88. Adaptive conservation

Lors de :

```text
Compact → Medium
Medium → Wide
Wide → Compact
rotation
resize
```

préserver autant que possible :

- surface ;
- sélection ;
- Dossier ouvert ;
- focus ;
- scroll ;
- query ;
- filtres ;
- responsabilité ;
- brouillon non soumis.

---

# 89. Text scaling

Tester au minimum :

```text
1.0
1.3
1.6
```

À 1.6 :

- aucun statut essentiel tronqué ;
- la personne concernée reste compréhensible ;
- le prochain mouvement reste accessible ;
- les rows peuvent grandir ;
- aucune hauteur fixe critique ;
- un split peut retomber en single-pane.

---

# 90. Accessibilité

Prestations doit respecter :

- lecteur d’écran ;
- ordre de focus ;
- contraste ;
- focus visible ;
- pas de couleur seule pour état ;
- zones tactiles correctes ;
- clavier sur desktop ;
- aucun hover obligatoire ;
- libellés d’actions explicites.

---

# 91. Motion

Les animations doivent expliquer :

- ouverture N1 → N2 ;
- résolution locale d’un blocker ;
- retour ;
- mise à jour d’un état.

Elles ne doivent pas célébrer artificiellement chaque transition.

Supporter `Reduce Motion`.

---

# 92. Média et documents

Les pièces ne sont pas des médias décoratifs.

Chaque document visible doit avoir :

- contexte ;
- finalité ;
- propriétaire ;
- niveau de sensibilité ;
- action légitime.

Pas de galerie générique de documents.

---

# 93. Notifications

Une notification n’est pas un Dossier.

Flux correct :

```text
fait métier
→ conséquence
→ éventuellement Situation Now
→ éventuellement Notification
```

Prestations conserve la continuité métier.

---

# 94. Conversations

Une conversation peut être pertinente dans un Dossier si elle porte :

- une décision ;
- une information qui change l’action ;
- une intervention ;
- un handoff ;
- un échange réellement lié au résultat.

Elle ne devient pas automatiquement le centre du Dossier.

---

# 95. Handoffs principaux

Prestations doit pouvoir transmettre vers :

```text
Now
Découvrir
Clients & partenaires
Nous
Piloter
Historique
Journey / owner depth
Requirements
Artifacts
Payments
Jour J si Occurrence réelle
Makolo Mark
```

Chaque handoff conserve l’Actor Context et l’autorité.

---

# 96. Contrat serveur/client — endpoint racine actuel

RUNTIME OBSERVÉ :

```text
GET /api/v1/organizations/workspaces/<slug>/work/
```

avec option de scope par responsabilité lorsque supporté :

```text
?responsibility=<key>
```

Le serveur :

- résout le Space visible ;
- filtre par autorité ;
- compose le monde Métier ;
- marque les capabilities ;
- ne confie pas la sécurité au client.

Réponse :

```http
Cache-Control: private, no-store
```

---

# 97. Runtime service_provider observé dans `main`

Le preset `service_provider` expose :

```text
primary_business_label = Prestations
activities_label       = Prestations & activités
relationship label     = Clients & partenaires
```

Le runtime Métier compose actuellement notamment :

- Activities ;
- Occurrences ;
- Journey `SERVICE` visibles ;
- autres owners selon footprint et authority.

Les Journey Service sont récupérées via un selector tenant compte notamment :

- bénéficiaire ;
- permission view-all ;
- permission view-assigned ;
- assignments actifs.

---

# 98. Runtime Services opérateur observé

Le domaine Services possède déjà des profondeurs Web owner-backed pour :

```text
operator dashboard
case detail
review queue
service configuration
start / complete step
create / resolve blocker
notes
assignments
artifact reviews
payment evidence decisions
artifact download
```

Ce contrat ne demande pas de recopier ces vérités dans Presentation.

Il demande de les intégrer avec une grammaire Prestations cohérente.

---

# 99. PR #496 et cible Prestations

La PR #496 sépare :

```text
sections structurelles
```

et :

```text
sections de continuité
```

Elle garde un `continuity_facet` uniquement sur les Journey progressives.

Pour Prestations, cela signifie :

```text
Prestation publiée
→ structure

Journey SERVICE active
→ continuité
```

et non :

```text
Prestation publiée
→ En cours
```

Cette direction est une CIBLE UX tant que la PR n’est pas fusionnée.

---

# 100. Contrat cible de section

Conceptuellement :

```text
SECTION
├── identity
├── representation
├── role
│   ├── structure
│   ├── continuity
│   └── history
├── coverage_state
├── items[]
├── has_more
└── links
```

Ceci est un contrat de projection candidat.

Il ne crée pas un modèle `Section` persistant.

---

# 101. Contrat cible Prestation Entry

```text
PRESTATION ENTRY
├── identity
├── source
│   └── Activity / ServiceDetails
├── human_title
├── summary?
├── availability?
├── service_kind?          support de vocabulaire, pas jargon obligatoire
├── active_cases_summary?  si sûr et autorisé
├── capabilities[]
└── owner_handoffs[]
```

---

# 102. Contrat cible Dossier Entry

```text
DOSSIER ENTRY
├── identity
├── source
│   └── Journey SERVICE
├── human_context
├── beneficiary_projection
├── synthesis
├── continuity_facet
│   ├── settled[]
│   ├── next[]
│   ├── blockers[]
│   └── outcome?
├── freshness
├── capabilities[]
└── owner_handoffs[]
```

---

# 103. Contract cible Dossier N2

```text
DOSSIER DETAIL
├── actor_context
├── viewer
├── service
├── beneficiary
├── objective?
├── synthesis
├── readiness?
├── requirements[]
├── steps[]
├── blockers[]
├── assignments[]
├── artifacts[]
├── notes[]?              authority filtered
├── payments[]?
├── submissions[]?
├── current_outcome?
├── outcome_events[]?
├── capabilities[]
└── handoffs[]
```

Toutes les dimensions sont optionnelles selon owner et autorité.

---

# 104. Capabilities

Le serveur doit exposer les capacités réellement légitimes.

Exemples conceptuels :

```text
view
manage_service
view_cases
manage_case
manage_steps
manage_blockers
manage_assignments
view_artifacts
view_restricted_artifacts
manage_notes
review_artifact
verify_payment_evidence
configure_service
```

Les noms wire exacts restent ouverts sauf ceux déjà démontrés par le runtime.

---

# 105. `create_service`

La capacité visible `Nouvelle prestation` doit provenir d’une autorité réellement établie.

Le client ne déduit pas :

```text
archétype service_provider
→ droit de créer
```

---

# 106. `create_case`

Une capacité de création de demande/dossier ne doit être exposée que si :

- le domaine owner supporte réellement l’initiation ;
- l’acteur est autorisé ;
- le bénéficiaire est légitime ;
- les données minimales sont présentes.

Le nom technique final reste ouvert.

---

# 107. Fraîcheur

Les données n’ont pas toutes la même exigence de fraîcheur.

Exemples :

```text
nom de prestation
→ relativement stable

responsable courant
→ peut changer

blocker actif
→ doit être revalidé pour action

payment
→ autoritatif

outcome externe
→ fraîcheur importante
```

Le client ne doit pas utiliser un TTL unique comme vérité métier.

---

# 108. Coverage

Une réponse doit pouvoir distinguer :

```text
complete
partial
unavailable
```

ou équivalent contractuel.

`items=[]` ne doit pas automatiquement signifier :

```text
Aucun dossier n’existe.
```

si la couverture est partielle ou indisponible.

---

# 109. Pagination / continuation

La racine ne doit pas imposer un nombre UX maximum arbitraire de Dossiers.

Une stratégie technique peut utiliser :

- preview bornée ;
- continuation opaque ;
- pagination owner-backed.

Le client doit préserver l’ordre et le contexte.

---

# 110. Confidentialité

Les projections doivent appliquer la divulgation minimale.

Ne pas exposer sur N1 :

- email ;
- téléphone ;
- documents ;
- notes internes ;
- paiement détaillé ;
- identité complète d’un bénéficiaire externe ;
- données Requirement sensibles ;

sans nécessité et autorité.

---

# 111. IDOR

Un client ne doit jamais pouvoir élargir sa visibilité en changeant :

```text
space slug
journey id
activity id
responsibility key
artifact id
review id
```

Le serveur doit revalider chaque owner depth.

Les réponses privacy-safe sont préférées lorsque nécessaire.

---

# 112. Golden S01 — Prestations / Compact N1

**Purpose**  
Reconnaître immédiatement le monde Prestations sans dashboardification.

**Fixture**

```text
Space : VisaPro
Prestations proposées : 4
Demandes à traiter : 2
En traitement : 3
Bloquées : 1
À délivrer : 1
```

**Hierarchy**

```text
DOSSIER IMPORTANT     P3
PRESTATION / CONTEXTE P2
ÉTAT                  P1/P2
MÉTADONNÉE            P0/P1
```

**Acceptance**

- aucune table ERP ;
- aucune métrique décorative ;
- la structure Prestations reste visible ;
- l’action principale provient des owners.

---

# 113. Golden S02 — Dossier N2 Compact

Fixture :

```text
Visa Canada — Marie Kalala
1 Requirement à revoir
Responsable : Conseiller A
Prochain mouvement : revoir justificatif
```

Vérifier :

- priorité au sens humain ;
- prochaines actions owner-backed ;
- pièces non exposées sans autorité ;
- pas de progression arbitraire.

---

# 114. Golden S03 — Prestation N2 Compact

Fixture :

```text
Accompagnement candidature
12 dossiers visibles
Parcours de référence publié
Questions d’entrée configurées
```

Vérifier :

- la prestation domine ;
- la configuration reste secondaire ;
- pas de jargon technique obligatoire.

---

# 115. Golden S04 — Dossier bloqué

Fixture :

```text
Dossier Admission
Blocage : preuve financière refusée
Empêche : soumission
```

Vérifier distinction :

```text
bloqué ≠ attente ≠ inconnu
```

---

# 116. Golden S05 — Dossier à délivrer

Fixture :

```text
Préparation entretien
Toutes les étapes requises sont satisfaites.
Compte-rendu à remettre.
```

Aucun succès final avant vérité owner-backed.

---

# 117. Golden S06 — Medium

Tester :

```text
834 × 1112
```

avec :

- N1 field ;
- détail léger éventuel ;
- conservation scroll/sélection ;
- textScale 1.0 / 1.6.

---

# 118. Golden S07 — Wide master/detail

Tester :

```text
1440 × 900
```

Candidate :

```text
rail
+
Prestations field
+
Dossier focus
```

Pas de troisième panneau automatique.

---

# 119. Golden S08 — Offline

Fixture :

```text
content + offline
Dossier connu localement
Payment frais : fraîcheur insuffisante pour décision
```

Vérifier :

- contenu conservé ;
- état sync visible ;
- action distante non faussement finalisée.

---

# 120. Golden S09 — Partial failure

Fixture :

```text
Dossier visible
Artifacts indisponibles
Steps disponibles
```

Vérifier dégradation locale.

---

# 121. Golden S10 — Permission loss

Fixture :

```text
Dossier auparavant visible
Mandate retiré
```

Vérifier :

- données sensibles retirées ;
- action impossible ;
- retour sûr ;
- pas de cache d’autorité actif.

---

# 122. Golden S11 — Dossier + review focus Wide

Fixture :

```text
Dossier
+
Pièce à revoir
```

Une troisième zone peut exister si la revue documentaire est le focus réel.

Elle ne doit pas devenir permanente.

---

# 123. Matrice des états Prestations

| Cas | N1 | N2 | Action |
|---|---|---|---|
| aucun service | empty structure | — | créer si autorisé |
| services sans dossiers | calm | prestation | config si autorisé |
| demande reçue | demandes à traiter | dossier | owner action |
| dossier en cours | en traitement | dossier | prochaine action |
| blocker actif | bloquées | dossier | résoudre si autorisé |
| résultat prêt | à délivrer | dossier | délivrer / finaliser owner |
| terminé | histoire | lecture | aucune action artificielle |
| offline | snapshot | snapshot | selon classe opération |
| partial error | contenu préservé | erreur locale | retry local |
| permission loss | filtré | retiré / 404 | aucune |

---

# 124. Anti-features spécifiques service_provider

Prestations ne doit pas devenir :

- Zendesk générique ;
- CRM universel ;
- ticketing ;
- Kanban obligatoire ;
- gestionnaire de tâches ;
- workflow builder visible en permanence ;
- liste brute de Journey ;
- liste brute de Requirements ;
- drive documentaire ;
- page de paiements ;
- inbox ;
- dashboard KPI ;
- score de progression ;
- feed ;
- chat centric ;
- système où toute personne CRM devient un Dossier ;
- système où tout document crée un dossier ;
- système où toute étape avec date devient Jour J ;
- second moteur d’autorité.

---

# 125. Invariants consolidés

1. `service_provider` voit **Prestations** comme porte primaire.  
2. Une prestation proposée est structurelle.  
3. Un Dossier engagé est une continuité distincte.  
4. Une Journey SERVICE peut porter un Dossier sans être affichée comme Journey.  
5. Dossier ≠ task manager.  
6. Requirement ≠ Form ≠ Resource ≠ Artifact ≠ Proof.  
7. Payment ≠ résultat du service.  
8. Assignment ≠ Permission.  
9. Une pièce visible n’établit pas automatiquement un Requirement satisfait.  
10. Un blocker doit être rattaché à ce qu’il bloque.  
11. Attente ≠ blocage.  
12. Notes internes ≠ conversation bénéficiaire.  
13. La personne concernée est projetée avec divulgation minimale.  
14. Structure et continuité restent distinctes.  
15. Now sélectionne l’attention ; Prestations conserve le monde métier.  
16. Jour J n’apparaît que via une Occurrence réelle.  
17. Local-first ne crée aucune autorité locale.  
18. Les actions sensibles sont revalidées serveur.  
19. La largeur n’autorise pas davantage de vérité.  
20. Presentation représente, ne possède pas.

---

# 126. Points volontairement ouverts

Restent ouverts :

1. le nom wire exact des sections Prestations cibles ;
2. l’API détaillée d’un Dossier N2 mobile ;
3. l’existence future d’un endpoint Space spécifique aux dossiers Service ;
4. le mapping définitif `À délivrer` depuis les owners ;
5. les seuils exacts d’ordre N1 ;
6. le modèle final de continuation/pagination ;
7. le layout Medium exact ;
8. le seuil de master/detail ;
9. les microcopies finales ;
10. les composants Flutter exacts ;
11. la matérialisation locale exacte des pièces sensibles ;
12. les TTL/freshness par domaine ;
13. les transitions exactes vers Jour J pour un service avec Occurrence ;
14. les capacités de création de Dossier au nom d’un bénéficiaire ;
15. le niveau de présence des outcomes en N1 ;
16. le degré de visibilité des assignments secondaires ;
17. la politique finale de notes internes sur mobile.

Aucun de ces points ne justifie automatiquement un nouveau domaine métier.

---

# 127. Critères de sortie du contrat UX Prestations

Le contrat est suffisamment fermé lorsque l’implémentation peut démontrer :

- N1 Prestations reconnaissable ;
- structure et continuité séparées ;
- prestations proposées visibles sans faux `En cours` ;
- demandes/dossiers composés depuis owners ;
- Dossier N2 humain ;
- Requirements intégrés sans duplication ;
- Steps intégrées sans task-managerisation ;
- blockers honnêtes ;
- responsabilités distinctes de l’autorité ;
- pièces et notes filtrées ;
- Payment distinct du résultat ;
- outcome owner-backed ;
- création contextuelle ;
- recherche et filtres humains ;
- offline honnête ;
- adaptive conservation ;
- handoffs propriétaires ;
- absence de dashboardification ;
- tests d’autorité/IDOR.

---

# 128. Critères d’implémentation serveur

Une future implémentation mature devrait démontrer :

- projection Space authority-scoped ;
- prestations structurelles séparées des Journey progressives ;
- `service_journeys_visible_to(...)` ou owner équivalent comme source de visibilité ;
- beneficiary / external beneficiary correctement protégés ;
- `view_all` / `view_assigned` respectés ;
- Artifacts filtrés selon sensibilité ;
- notes filtrées selon visibilité ;
- capabilities calculées serveur ;
- blockers réels ;
- assignments réels ;
- Payment evidence owner-backed ;
- current outcome contrôlé par Services ;
- aucune duplication de Readiness ;
- aucune migration Presentation inutile ;
- cache privé ;
- erreurs privacy-safe ;
- tests IDOR ciblés.

---

# 129. Critères Flutter

Flutter doit démontrer :

- lecture depuis le store local lorsqu’une projection existe ;
- sync séparée de l’état contenu ;
- `content + offline` supporté ;
- N1 → N2 → N3 ;
- restauration de scroll ;
- filtres conservés ;
- responsabilité conservée ;
- deep link ;
- revalidation après resume ;
- aucune inférence de Permission ;
- actions C/D sans faux succès ;
- pièces sensibles non persistées sans politique ;
- text scale 1.6 ;
- Reduce Motion ;
- Goldens S01–S11.

---

# 130. Critères Web

Web doit démontrer :

- même hiérarchie métier que Flutter ;
- serveur comme autorité ;
- profondeur progressive ;
- clavier/focus ;
- aucun hover obligatoire ;
- master/detail uniquement si utile ;
- pas de cockpit ERP ;
- pas de duplication de Services dans Presentation ;
- actions Web existantes reliées proprement au Dossier ;
- protection CSRF/auth/IDOR normale ;
- états vide, erreur et permission cohérents.

---

# 131. Tests UX minimum

## Recognition test

En environ 500 ms :

```text
où suis-je ?
→ Prestations

quel mode mental ?
→ traiter et délivrer des services

quel élément domine ?
→ le dossier ou la continuité réellement importante
```

## Blur test

Les dossiers actifs doivent dominer sans que tout ressemble à un dashboard.

## Competition test

Une seule action ou conséquence majeure domine par unité.

## Deletion test

Tout élément supprimable sans perte de compréhension doit être suspect.

## Adaptive test

Compact / Medium / Wide conservent identité, sélection et priorité.

## Freshness test

Un vieux snapshot ne devient pas un résultat actuel.

## Authority test

Changer la responsabilité choisie n’augmente jamais l’autorité.

## Privacy test

Une personne non autorisée ne peut déduire l’existence d’un Dossier par search, count ou deep link.

---

# 132. Scénarios de référence

## 132.1. Prestataire calme

```text
4 prestations proposées
0 dossier demandant intervention
3 dossiers en traitement normal
```

La racine reste calme.

## 132.2. Nouvelle demande

```text
Visa Canada — Marie
Nouvelle demande à revoir
```

Action owner-backed visible si autorisée.

## 132.3. Dossier à préparer

```text
Orientation éducative — Jean
Formulaire reçu
2 conditions restent à établir
```

Pas de pourcentage arbitraire.

## 132.4. Dossier bloqué

```text
Candidature Master — Sarah
Blocage : relevé de notes refusé
Empêche : soumission
```

Le blocker est localisé.

## 132.5. Dossier en attente externe

```text
Visa Canada — Marie
Soumis
Réponse de l’ambassade attendue
```

Attente, pas blocage.

## 132.6. Dossier à délivrer

```text
Préparation entretien — Paul
Session terminée
Compte-rendu prêt à remettre
```

Résultat distinct des Steps.

## 132.7. Payment

```text
Prestation X
Preuve de paiement reçue
Vérification requise
```

Pas `Payé` avant owner confirmation.

## 132.8. Pièce sensible

Le Dossier reste visible mais une pièce restreinte n’apparaît pas pour un viewer non autorisé.

## 132.9. Offline

Le Dossier connu reste visible avec date de fraîcheur.

Une décision de revue reste indisponible sans confirmation distante.

## 132.10. Perte d’autorité

Après retrait du Mandate, l’action et les données sensibles disparaissent sans fuite.

---

# 133. Formulation canonique finale

> **Prestations est la porte Métier d’un Space `service_provider`. Elle rend compréhensible ce que le Space propose réellement comme service et la continuité des demandes effectivement engagées jusqu’à leur résultat. Elle présente les prestations comme structure durable et les dossiers comme compositions humaines owner-backed de Journey, Requirements, étapes, responsabilités, pièces, Payment et résultats, sans exposer ces domaines comme des modules indépendants. Elle préserve strictement l’autorité, la confidentialité, la distinction entre attente et blocage, la séparation entre paiement et accomplissement, et la responsabilité des owners. Elle doit donner l’impression de traiter et délivrer un service réel — jamais de naviguer dans un moteur de workflow.**

---

# 134. Formule courte

```text
PRESTATIONS
=
ce que nous savons rendre
+
les demandes réellement engagées
+
ce qui reste à préparer / traiter / délivrer
+
la profondeur owner-backed nécessaire pour agir
```

et :

```text
Prestation proposée
≠ Dossier engagé

Journey SERVICE
≠ écran Journey

Payment confirmé
≠ prestation accomplie

Assignment
≠ Permission

Dossier
≠ task manager
```
