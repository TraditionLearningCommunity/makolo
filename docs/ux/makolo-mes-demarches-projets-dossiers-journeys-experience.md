# Makolo — Contrat détaillé d'expérience « Moi → Mes démarches → Projets → Dossiers → Démarches »

> **Statut : contrat de conception fonctionnelle et UX, à implémenter progressivement.**
>
> **Périmètre :** expérience personnelle « Moi », espace « Mes démarches », pages Projet, Dossier et continuité vers Journey ; Flutter et web comme **une seule expérience Makolo**, avec adaptations de mise en page selon le support.
>
> **Chantier de travail :** PR #522, branche `fix/discover-a-continuation-context-20261014`. Ne pas ouvrir une autre branche pour cette spécification.
>
> **Date :** 8 novembre 2026.
>
> **Nature :** document de référence détaillé, pas un compte rendu, ni la preuve qu'une interface ou qu'une API proposée est déjà implémentée. Le code, les permissions, les migrations et les tests courants restent les sources de vérité techniques.

## 0. Intention et positionnement de l'expérience

Makolo doit aider à **faire avancer des situations réelles**, non à accumuler des tâches arbitraires. Une personne peut entreprendre une démarche isolée, regrouper plusieurs démarches vers un résultat concret, puis réunir plusieurs résultats sous un horizon durable. Cette organisation doit être compréhensible à première vue, mais suffisamment rigoureuse pour accompagner des parcours personnels, professionnels, administratifs et collectifs complexes.

L'utilisateur doit pouvoir passer sans rupture :

1. de **Moi**, son espace personnel durable ;
2. à **Mes démarches**, son espace d'organisation ;
3. au **Projet**, qui donne une direction à long terme ;
4. au **Dossier**, qui coordonne un résultat concret ;
5. à la **Démarche / Journey**, où l'action métier s'accomplit réellement.

Le produit ne doit pas donner l'impression d'un exercice scolaire, d'une arborescence technique de base de données, d'un clone de Trello ou d'un explorateur informatique brut. L'inspiration des dossiers de fichiers sert à rendre la **structure familière**, pas à faire croire que tous les objets Makolo sont des fichiers, ni à réduire les parcours à des tâches ordinaires.

La qualité recherchée est celle d'un logiciel adulte : précis, accueillant, durable, calme visuellement, exigeant sur les détails, agréable en connexion faible, et capable de s'adapter à des cas simples aussi bien qu'à des situations collectives exigeantes.

### 0.1 Une application Makolo, pas deux applications concurrentes

**Makolo web et Makolo Flutter sont deux modalités d'accès au même produit.** Elles partagent les mots, le parcours, les règles de visibilité, les relations métier, la hiérarchie des informations, les états de surface et le langage visuel. Elles ne possèdent pas chacune leur conception des Projets et Dossiers. Il n'existe pas de « Projet mobile » ou de « Dossier web » séparé du modèle canonique.

Les composants techniques peuvent être différents — Flutter natif d'un côté, interfaces web de l'autre — parce que les supports, la navigation et le stockage ne sont pas identiques. La **sémantique produit** ne doit pas diverger. Même résultat visible, mêmes actions autorisées, mêmes états métier, mêmes titres et mêmes parcours principaux ; disposition responsive et interactions adaptées aux pointeurs, claviers et gestes.

Les règles métier sont calculées et confirmées par les domaines propriétaires du serveur. Le client présente des projections autorisées, conserve localement les données acquises et orchestre les interactions. Les deux supports ne recréent ni Permission, ni Readiness, ni lifecycle, ni autorité parallèle.

### 0.2 Décision sur l'ordre du chantier

On travaille d'abord **Moi → Mes démarches → Projet → Dossier → Journey**. Le regroupement futur d'« En cours » est **une conséquence à traiter séparément**, pas une condition pour rendre l'espace personnel utilisable. Ne pas profiter de ce document pour remanier tout le shell ou tout Discovery.

---

## 1. Contrat de domaine : ce que ces noms veulent dire

### 1.1 La hiérarchie, avec des rattachements facultatifs

```text
Moi
└── Mes démarches
    ├── Projet A — horizon durable
    │   ├── Dossier A1 — résultat actif composé
    │   │   ├── Démarche J1 — Journey existante
    │   │   └── Démarche J2
    │   └── Dossier A2
    │       └── Démarche J3
    ├── Projet B
    ├── Dossier indépendant C — aucun Projet parent
    │   └── Démarche J4
    └── Démarche indépendante J5 — aucun Dossier parent
```

- **Projet :** horizon, direction durable, intention suivie sur des semaines, mois ou années. Il rassemble des Dossiers, mais ne devient pas une liste de tâches génériques. Il peut être vide et rester légitime.
- **Dossier :** objectif concret, composé lorsque nécessaire de plusieurs Journeys, de dépendances et de responsabilités. Il peut être autonome, sans Projet.
- **Démarche :** Journey existante, avec sa propre vérité métier et ses propres états, Requirements, étapes, documents, paiements ou accès selon le parcours concerné. Une Journey peut être indépendante.
- **Activity / Occurrence :** restent les noyaux canoniques de l'activité et de sa réalisation. Une démarche peut être liée à une Activity et éventuellement à une Occurrence ; un Dossier ne copie ni l'une ni l'autre.
- **Profil / Espace :** un Projet ou Dossier est porté par le contexte propriétaire autorisé ; le fait d'être membre d'un Espace n'accorde pas automatiquement la gestion de toutes ses ressources.

Les relations Projet–Dossier et Dossier–Journey sont des **rattachements métier**, non une simple indentation persistée côté client. Détacher un enfant ne le supprime pas. Déplacer un Dossier vers un autre Projet ne déplace pas ses données Journey au sens de propriété métier.

### 1.2 Cardinalités et conséquences d'affichage

Un Projet peut présenter zéro, un ou plusieurs Dossiers visibles. Un Dossier peut être sans Projet. Le backend actuel impose au plus **un Projet actif par Dossier** à un instant donné ; les rattachements historiques restent distincts. Un Dossier peut être lié à plusieurs Journeys ; une Journey peut exister sans Dossier. Ne pas déduire de cette présentation une exclusivité universelle Journey–Dossier si le modèle canonique ne l'impose pas.

Une Journey n'est pas « contenue » dans un Dossier comme un document de répertoire : son identité, ses autorisations et ses faits ne changent pas quand on l'ajoute à l'organisation du Dossier. Le client conserve `kind + id` comme référence canonique et un seul détail propriétaire de la Journey.

Une même réalité peut être référencée dans plusieurs surfaces Makolo, mais **ne doit pas être comptée plusieurs fois comme plusieurs engagements distincts**. Un regroupement change la présentation, pas la quantité réelle de démarches.

### 1.3 Lifecycle ≠ readiness ≠ échéance

Les cycles de vie Projet et Dossier du modèle observé sont `draft`, `active`, `completed`, `cancelled`, `archived`. La présentation peut les humaniser : « En préparation », « En cours », « Terminé », « Annulé », « Archivé ».

À côté, la **Readiness** issue des démarches peut signaler « Prêt », « Action requise », « En attente », « Bloqué », « Terminé ». Ce signal est une projection calculée ; ce n'est **pas un nouvel état persisté** du Projet ou du Dossier.

Une échéance n'est pas une progression. Une date de création n'est pas une date à laquelle l'événement s'est réalisé. La date de début d'un Projet, sa date de fin, la date limite d'un Dossier et les dates réellement connues d'une Journey ont des significations différentes.

Un Projet actif peut contenir des Dossiers terminés. Un Dossier actif peut contenir des Journeys terminées. Archiver le Projet ne termine pas automatiquement les Dossiers ; terminer une démarche ne termine pas automatiquement son Dossier.

---

## 2. Architecture de navigation : où commence le parcours ?

Le shell personnel reste :

```text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
```

« Moi » n'est pas une copie d'« En cours ». Sa fonction est de donner accès au capital personnel, à l'identité, aux éléments durables et aux profondeurs personnelles.

### 2.1 Placement exact dans « Moi »

Après le bloc de **l'identité** (avatar, nom et accès aux informations personnelles), et dans la même zone visuelle de premier rang que le **Passeport Makolo**, installer une entrée privilégiée :

- **Titre : « Mes démarches »**.
- **Description courte : « Projets, dossiers et démarches »**.
- **Icône :** ensemble de dossiers finement dessiné ou dossier organisé ; ne pas utiliser une illustration de cartable/cartoon.
- **Affordance :** chevron ou flèche indiquant l'ouverture, grande cible tactile.
- **Rang :** immédiatement sous le Passeport, **avant** les rubriques secondaires de « Mon espace ».
- **Aspect :** traité comme une carte d'entrée premium, avec sa propre hiérarchie, pas comme une petite ligne indistincte entre « Mes accès », « Mes veilles » et d'autres liens.
- **Destinataire :** un **seul espace unifié**. Les deux entrées séparées « Mes projets » et « Mes dossiers » ne doivent plus encombrer « Moi » lorsqu'elles sont remplacées par ce contrat.

Conserver le Passeport comme objet distinct : le Passeport représente la personne et ce qu'elle choisit de partager ; Mes démarches représente ce qu'elle organise et entreprend. L'un ne doit pas absorber l'autre.

### 2.2 Ordre et transitions

```text
Moi
  → Mes démarches
      → Projet
          → Dossier
              → Démarche (détail Journey existant)
      → Dossier indépendant
          → Démarche
      → Démarche indépendante
```

Le retour ramène à la profondeur logique précédente et préserve les filtres, la position de défilement et la vue sélectionnée. Un lien direct vers un Projet, Dossier ou Journey doit ouvrir sa profondeur sans obliger à parcourir tous les ancêtres. Le fil d'Ariane n'affiche que les parents **réellement visibles** au lecteur ; il ne révèle pas un Projet caché à travers un Dossier autorisé.

Les intitulés de navigation restent humains. Éviter les labels techniques `Objectives`, `owner`, `scope`, `projection` dans l'interface.

---

## 3. Écran « Mes démarches » : explorateur personnel unifié

### 3.1 Composition et priorités de l'écran

De haut en bas :

1. **Barre d'identité de page :** retour, « Mes démarches », recherche et menu d'affichage accessible. Sur grand écran, cette barre peut devenir un en-tête dans la zone de contenu.
2. **Actions de création de premier rang :** « Créer un dossier » et « Créer un projet » avec des icônes distinctes et une hiérarchie visuelle claire. Selon contexte et droits, un Dossier peut être créé sans Projet ou directement sous un Projet ; cette intention doit rester explicite.
3. **Recherche locale immédiate :** saisie, suggestions et effacement, sans aller-retour réseau pour chaque frappe.
4. **Barre discrète des contrôles :** filtres, tri, dates, état de fraîcheur / information sur la couverture locale si utile.
5. **Sélecteur de présentation : « Cartes | Liste | Explorateur »** avec icônes et libellés ; garder le choix de l'utilisateur.
6. **Contenu organisé :** Projets racines, Dossiers indépendants, Démarches indépendantes. Le statut « indépendant » doit être compréhensible sans appeler ces objets « orphelins ».
7. **Navigation progressive :** charger plus d'éléments autorisés si la collection locale ne couvre pas toute la collection serveur connue ; ne pas inventer un inventaire total.

Les actions de création ne disparaissent pas lorsque la liste est vide. Les filtres et tri restent accessibles dans tous les modes ; si certaines options dépendent d'une information non exposée par le serveur, les présenter comme indisponibles plutôt que simuler un résultat.

### 3.2 Mode Cartes — mode recommandé par défaut

Objectif : lecture chaleureuse et professionnelle des regroupements sans arborescence trop serrée.

**Une carte Projet** montre : pictogramme, titre, description courte si disponible, état, horizon si connu, contexte personnel / Espace, nombre de Dossiers **visibles** si disponible, signal de prochaine échéance visible si calculable, et un chevron d'ouverture. Une prévisualisation compacte de deux ou trois Dossiers peut compléter la carte, sans la transformer en tableau de bord saturé. Éviter des badges redondants, trois progress bars et une dizaine de chiffres sans sens.

**Une carte Dossier indépendant** montre : titre, objectif, état, échéance, indication de Readiness si acquise et autorisée, nombre de Journeys visibles connu, éventuelle action utile.

**Une carte Démarche indépendante** montre : libellé humain de l'activité ou du parcours, état et information de temps réellement exposée par la projection Journey ; action d'ouverture vers la Journey canonique.

Sur téléphone, une colonne, cartes de hauteur adaptative, petites zones de métadonnées. Sur écran large, grille adaptée à la largeur **sans changer le sens ou le contenu de l'objet**. Ne pas imposer une hauteur identique qui coupe le titre ou cache la prochaine action.

### 3.3 Mode Liste — densité utile

Objectif : manipuler un grand nombre d'éléments rapidement. Une ligne possède au minimum : icône de type, titre, contexte parent ou indépendant, état lisible, une date pertinente selon le tri, et affordance de détail. Des colonnes additionnelles (création, échéance, propriétaire) peuvent apparaître sur écran large.

Le mode Liste peut proposer une **vue transverse aplatie** des éléments acquis ; dans ce cas, afficher leur chemin (« Projet / Dossier / Démarche ») pour préserver le contexte, et n'enregistrer chaque objet qu'une seule fois par identité. Offrir également un mode « conserver les groupes » si le volume le justifie ; ne pas forcer l'aplatissement de manière opaque.

Sélection d'une ligne = ouverture, pas activation irréversible. Les actions secondaires sont regroupées derrière un menu contextuel explicitement autorisé. Un geste sur mobile ne doit jamais archiver silencieusement un Dossier.

### 3.4 Mode Explorateur — hiérarchie professionnelle

Objectif : rendre visibles les relations comme dans un explorateur de fichiers, sans copier son apparence vieillissante.

- Trois niveaux de profondeur principale : Projet → Dossier → Démarche.
- Nœuds repliables, flèches de divulgation cohérentes, indentation maîtrisée et alignement sur une grille.
- Icônes différentes pour Projet (dossiers organisés), Dossier (dossier) et Journey (parcours / route).
- Le clic sur **la flèche** déplie/replie ; le clic sur **le titre** ouvre le détail. Les cibles doivent être distinctes.
- Afficher les Dossiers sans Projet et les Journeys indépendantes à la racine, dans des groupes clairs si cela améliore la lecture ; ne pas fabriquer un Projet « Sans projet ».
- Sur petit écran, éviter l'indentation illimitée ; autoriser l'ouverture progressive par profondeur et conserver un fil d'Ariane.
- Dans un nœud, les métadonnées (état, échéance, action requise) doivent rester lisibles.
- Replier/déplier localement, sans requête réseau à chaque interaction lorsque les descendants sont acquis.
- Si des descendants ne sont pas encore chargés, afficher « charger les éléments suivants » plutôt qu'un faux nœud vide.

Il ne faut pas confondre **état ouvert/replié de l'arbre** et état métier actif/archivé du Projet ou Dossier.

### 3.5 Comportements partagés des trois modes

Un changement de vue ne réinitialise ni la requête de recherche, ni les filtres, ni le tri, ni l'objet actuellement consulté. La préférence de vue est locale au Profil et peut être restaurée au prochain lancement. Les données sont partagées : il n'existe pas trois collections serveur pour trois modes visuels.

Une recherche qui identifie une Journey contenue dans un Dossier doit pouvoir montrer le contexte ou déplier les ancêtres **visibles** sans faire croire que la Journey est indépendante.

---

## 4. Recherche, autocomplétion, filtres et tris dans « Mes démarches »

### 4.1 Recherche locale

La recherche se fait **sur les éléments acquis et autorisés**, en lecture locale. Elle interroge les titres et, si présents et autorisés, les descriptions, libellés utiles et chemins visibles. Une normalisation de casse et d'accents améliore la recherche française ; la recherche doit aussi fonctionner pour des mots isolés, des préfixes et des expressions assez courtes. Ne pas indexer des données cachées ou des secrets.

**Autocomplétion** : dès quelques caractères, présenter des résultats réels de la base locale avec icône de type et contexte parent. Une suggestion sélectionnée ouvre directement le bon détail. Ne pas inventer des démarches « possibles » qui n'appartiennent pas au catalogue local ; « Découvrir » reste la surface dédiée à la découverte.

Si la recherche couvre seulement les 50 premiers éléments acquis, l'interface doit indiquer discrètement que la recherche concerne les données disponibles **sur cet appareil** et proposer d'obtenir d'autres éléments lorsque le réseau le permet. Aucun « zéro résultat global » trompeur.

### 4.2 Tris et filtres : deux commandes distinctes

**Trier** change l'ordre. **Filtrer** restreint les objets affichés. Un même filtre peut s'appliquer dans les trois vues ; son sens doit être constant.

| Critère | Usage dans l'interface | Fait nécessaire / précaution |
| --- | --- | --- |
| Nom A–Z / Z–A | Tri alphabétique naturel et stable | Titre autorisé, locale française ; départager les égalités avec identité stable |
| Créé récemment / anciennement | Tri de création | `created_at` exposé à la projection client ; ne pas confondre avec `updated_at` |
| Modifié récemment | Tri d'activité du dossier/projet | `updated_at` exposé ; une modification du parent n'est pas nécessairement l'activité d'un enfant |
| Début proche / lointain | Tri temporel | `starts_on` Project ou date de début réelle de Journey ; ne pas synthétiser de début Dossier |
| Échéance proche / lointaine | Tri de nécessité temporelle | `deadline` Dossier, `ends_on` Project ou fait de Journey, en conservant la distinction |
| Date d'achèvement | Tri historique si disponible | Fait d'accomplissement provenant de l'owner ; ne pas déduire une date de fin à partir d'un booléen |
| Importance personnelle | Tri explicite souhaité | Préférence déclarée à contractualiser si elle n'existe pas ; ne pas la fabriquer côté backend ni l'inférer de l'usage |
| Nécessité / prochaine action | Tri orienté action | Readiness/NextAction autorisée, date limite connue ; ne pas créer un score universel opaque |
| Type | Filtre | Projet, Dossier, Démarche ; chacun conserve son owner |
| Cycle de vie | Filtre | Préparation, actif, terminé, annulé, archivé selon l'objet |
| Attention | Filtre | Action requise, en attente, bloqué, prêt, seulement si projection connue |
| Contexte | Filtre | Personnel, Espace autorisé, partagé selon contrat de disclosure |
| Rattachement | Filtre | Dans un Projet, Dossier indépendant, Journey indépendante, selon relations connues |
| Période | Filtre | Date de création, intervalle de début, échéance, accomplissement **séparés** |
| Avec / sans échéance | Filtre | Ne pas traiter « aucune date » comme « aucune contrainte réelle » |
| Informations incomplètes | Filtre de contrôle facultatif | Distinguer inconnu, non acquis, caché, non applicable |

**Exemple essentiel :** un Projet « Recherche de bourse » créé en avril avec une échéance en novembre n'est pas nouveau en novembre. Un Dossier créé aujourd'hui et à traiter dans trois jours doit remonter dans le tri « échéance », même si sa date de création est très récente. Ne pas utiliser une seule date « du dossier » pour toutes ces notions.

Pour les dates sans heure, afficher une date seule. Ne jamais convertir un jour prévu en heure `00:00` ni en instant universel fictif.

### 4.3 Comportement du tri dans une hiérarchie

En **Cartes** et **Explorateur**, le tri s'applique aux frères d'un même niveau : Projets entre eux, Dossiers entre eux dans un Projet, Journeys entre elles dans un Dossier. Les objets indépendants restent dans la racine ou le groupe explicite choisi. Un tri ne modifie jamais les rattachements.

En **Liste**, le mode transverse peut classer tous les objets acquis ensemble, à condition d'exposer leur type et leur contexte. Ne pas faire disparaître un parent parce qu'un seul enfant correspond au filtre : soit montrer un parent contextuel non compté comme résultat, soit proposer une navigation claire vers lui.

Les dates manquantes sont placées dans une catégorie « non renseigné », non « jamais » et non « aujourd'hui ». L'importance absente ne vaut pas importance faible. Les groupes incomplets portent un signal de couverture partielle.

### 4.4 Interface de contrôle

Sur mobile, une ligne de contrôle compacte (« Filtrer », « Trier », « Dates »), ouvrant un panneau à hauteur adaptable ; les filtres actifs sont signalés par des puces sobres et un compteur, avec « Effacer ». Sur grand écran, un bandeau de recherche et des contrôles déroulants peuvent rester visibles ; options avancées dans un panneau latéral. Toujours afficher la direction de tri et permettre de réinitialiser.

Ne pas empiler vingt sélecteurs en permanence. L'écran doit rester dominé par les Projets, Dossiers et démarches, pas par un formulaire de filtrage.

---

## 5. Actions racines : créer, accéder, organiser

Deux actions permanentes de premier rang dans Mes démarches :

- **Créer un dossier** (icône dossier avec signe plus).
- **Créer un projet** (icône dossier organisé ou dossier empilé avec signe plus).

Ces actions ouvrent un parcours de saisie adapté, avec validation, résumé du contexte porteur (Profil ou Espace choisi si autorisé) et retour vers l'élément créé **après confirmation propriétaire**. Elles ne créent pas de Dossier artificiel pour chaque Journey.

La création d'un Dossier peut être déclenchée depuis la racine (indépendant) ou depuis un Projet (rattachement souhaité). Le choix doit être explicite avant d'engager une mutation et revalidé côté serveur. Rattacher un Dossier existant est une autre action, non équivalente à le recréer.

La création d'une **Démarche** n'est pas une commande générique « ajouter tâche » : l'engagement démarre depuis le parcours propriétaire approprié (Activity, Service, opportunité, etc.), puis peut être rattaché à un Dossier si l'autorité le permet. Une action « Lier une démarche existante » peut vivre dans un Dossier.

En cas d'absence de réseau, l'utilisateur peut préparer un **brouillon local** si un contrat sûr existe. L'interface dit « Brouillon sur cet appareil », jamais « Dossier créé » ou « Projet confirmé » avant réponse du serveur.

Chaque menu secondaire expose seulement les actions compatibles avec le contexte, les capabilities et les permissions vérifiées ; une capacité visible n'est pas une autorisation de mutation permanente.

---

## 6. Page Projet — identité, synthèse et pilotage d'un horizon durable

### 6.1 Fonction de la page

La page Projet répond aux questions : **Où veux-je aller ? Sur quel horizon ? Quels Dossiers me rapprochent de ce résultat ? Quelles échéances visibles méritent attention ?**

Elle doit évoquer un espace de pilotage sobre, pas un grand gestionnaire de tâches. On n'y recopie pas tous les Steps ou tous les formulaires des Journeys. La navigation principale descend dans les Dossiers, et les détails Journey restent chez leur propriétaire.

### 6.2 En-tête / couverture

À l'ouverture :

- petit fil d'Ariane « Mes démarches / Projet » (ou parent visible) ;
- icône Projet, titre complet, description humaine ;
- cycle de vie du Projet, contextualisé sans badge criard ;
- contexte porteur lisible (« Projet personnel » ou nom d'Espace si exposable) ;
- dates de début et de fin **facultatives**, comme horizon, non comme promesse d'achèvement ;
- menu d'actions autorisées, sans occuper l'espace de lecture ;
- accès aux conversations contextualisées si réellement disponibles et autorisées.

Pour un Projet sans dates, l'en-tête doit rester équilibré. Ne pas afficher « 0 mois », « date inconnue = aujourd'hui » ou une fausse barre de progression.

### 6.3 Trois vues du Projet

#### A. Synthèse — vue par défaut

Une introduction avec état et horizon, puis une vue d'ensemble en **compteurs modestes et justifiés** : nombre de Dossiers visibles, répartition des états visibles, prochaine échéance pertinente si le serveur fournit des faits suffisants, et éventuellement un signal de vigilance dérivé.

En dessous, présenter les Dossiers du Projet sous forme de cartes/listes compactes, chaque carte avec : titre, état, échéance, signal de Readiness si réellement fourni, action d'ouverture. Une section « À suivre » peut remonter les Dossiers qui demandent un mouvement, mais ne doit pas reconstituer des secrets à partir des sous-dossiers invisibles.

Un Projet vide est un cas valide : expliquer qu'il attend ses premiers Dossiers et présenter « Créer un dossier » / « Rattacher un dossier existant » si autorisé.

#### B. Dossiers — espace de gestion

Liste ou grille dédiée aux Dossiers **visibles dans ce Projet**, avec recherche locale, tri nom/date/échéance/état, filtres de cycle de vie et signal de readiness disponible. Les actions de rattachement, déplacement ou détachement apparaissent ici, en menu contextuel ou barre d'action accessible.

Chaque Dossier a un lien stable vers son détail. Une sélection multiple peut être envisagée plus tard, uniquement si ses mutations groupées sont compatibles avec les services et permissions owner-backed ; elle n'est pas supposée acquise.

Le nombre « 5 Dossiers » signifie « 5 Dossiers visibles », pas forcément « 5 Dossiers au total » si les permissions ne permettent pas cette information.

#### C. Calendrier — lecture temporelle du Projet

Visualiser l'horizon du Projet et les échéances **connues** de ses Dossiers. Sur mobile, privilégier un calendrier de jalons ou une ligne du temps verticale. Sur grand écran, une vue Gantt légère peut placer les Dossiers ayant réellement une période valide, et des marqueurs ponctuels pour les simples échéances.

**Ne pas inventer une barre début–fin pour un Dossier qui ne possède actuellement qu'une `deadline`.** Un point daté reste un jalon. Une plage temporelle demande deux faits de début/fin reconnus. Ne pas utiliser la longueur de cette barre comme pourcentage d'avancement.

Filtres locaux possibles : période, jalons proches, Dossiers actifs, éléments sans date, échéances dépassées. Le contrôle « Aujourd'hui » recentre sans changer le serveur. La navigation vers un jalon ouvre le Dossier concerné.

### 6.4 Actions Projet

Actions prévues, après évaluation des permissions :

1. **Créer un Dossier dans ce Projet**, en confirmant la création et le rattachement selon les contrats propriétaires.
2. **Rattacher un Dossier existant** que l'acteur a réellement autorité à lier.
3. **Détacher un Dossier** : confirmation claire « le Dossier restera disponible indépendamment » ; aucune suppression en cascade.
4. **Déplacer un Dossier vers un autre Projet** : choix du Projet cible autorisé, vérification de l'autorité sur la source, le Dossier et la cible, puis relecture serveur.
5. **Changer l'état du Projet** selon les transitions permises ; archiver/terminer/annuler n'impliquent pas de transition des Dossiers.
6. **Modifier les informations du Projet** (titre, description, horizon) seulement après vérification/exposition d'un service propriétaire adapté ; le fait que le modèle porte ces champs ne garantit pas qu'un endpoint natif de mise à jour existe.
7. **Ouvrir les échanges liés au Projet** via Conversations existant, sans doubler la messagerie.

Dans les menus, actions destructrices ou structurantes séparées des actions ordinaires, formulations explicites et confirmations ciblées ; pas d'icône corbeille permanente sur chaque carte.

### 6.5 Ce qui est déjà disponible et ce qui reste à contractualiser

Le modèle `Project` contient actuellement : titre, description, propriétaire Profil **ou** Espace, `starts_on`, `ends_on`, lifecycle, `created_at`, `updated_at`. `ProjectDossierLink` porte le rattachement et son historique. Les services existants gèrent création, liaison, détachement, déplacement et transitions.

Le détail API existant `GET /api/v1/objectives/projects/<uuid>/` expose `identity`, `horizon`, `state` et `visible_dossiers`. **Il n'expose pas toute la profondeur souhaitée par cette UX** : par exemple, la collection de Dossiers ne livre pas automatiquement leurs états de readiness, et le Projet ne fournit pas un « pourcentage réalisé » canonique. Le champ `capabilities` a été observé vide ; ne pas inventer de boutons actifs ou des permissions calculées en Flutter.

---

## 7. Page Dossier — espace concret d'accomplissement

### 7.1 Fonction de la page

La page Dossier répond à : **Quel résultat cherchons-nous ? Où en sommes-nous réellement ? Qui doit agir ? Quelles démarches attendent d'autres démarches ? Que peut-on faire maintenant ?**

C'est une profondeur active, pas une simple boîte contenant des liens. Un Dossier peut être personnel, partagé par responsabilité, ou porté par un Espace autorisé. Il garde ses propres règles et ne prend jamais l'autorité sur le contenu métier interne d'une Journey.

### 7.2 En-tête Dossier

- Retour et chemin parent visible (« Mes démarches / Projet / Dossier » ou « Mes démarches / Dossier »).
- Icône Dossier, titre, description/objectif.
- État de cycle de vie et échéance, distincts de la Readiness.
- Projet parent visible si lié et divulguable, avec ouverture du Projet ; sinon aucune référence qui révèle un parent caché.
- Signal collectif de Readiness : « Prêt », « Action requise », « En attente », « Bloqué », etc., selon la projection reçue. Si la projection est partielle, le dire sans déduire la personne ou la démarche masquée.
- Menu d'actions selon autorité, et entrée des conversations contextualisées si disponible.

L'en-tête reste lisible pour un Dossier sans Journey, sans échéance ou sans Projet.

### 7.3 Quatre vues du Dossier

#### A. Vue d'ensemble — entrée recommandée

La synthèse présente en priorité l'intention du Dossier et **la prochaine intervention utile** si le serveur en expose une. Afficher une carte d'action principale seulement lorsqu'une vraie action orientée acteur est fournie ; sinon montrer honnêtement « En attente », « Rien à faire pour le moment », « Informations partielles » ou « Actualisation nécessaire », selon le cas.

Proposer une lecture compacte : démarches visibles, nombre terminées si fiable, éléments à traiter, dépendances pertinentes et personnes responsables lorsque la divulgation est permise. Le compteur ne devient jamais un pourcentage d'accomplissement universel. Les sections secondaires « Démarches », « Dépendances », « Collaboration » restent accessibles sans faire défiler un tableau de bord interminable.

Chaque Démarche est une entrée vers son détail canonique, avec état et prochain mouvement autorisé ; pas un ensemble de petites cases à cocher parallèles au moteur Journey.

#### B. Liste — traitement rapide des démarches

Afficher les Journeys **visibles** liées au Dossier, avec recherche et tri local sur les données acquises : nom, état, priorité d'action si dérivée de Readiness, date connue, dernière modification si fournie. Les filtres peuvent porter sur « toutes », « à traiter », « en attente », « bloquées », « terminées », « sans date », « ma responsabilité », selon les informations réellement divulguées.

Une ligne donne le nom humain de la Journey, son état, l'éventuelle prochaine action et son responsable **si autorisé** ; le clic ouvre la Journey. Le retrait du Dossier est une action de composition distincte de l'annulation de la Journey.

Les filtres doivent rester utilisables hors connexion sur les snapshots locaux autorisés. Si seuls certains liens du Dossier ont été acquis, indiquer la couverture partielle.

#### C. Chronologie — lecture du temps

Montrer les démarches dans une chronologie verticale fluide sur téléphone, horizontale si adaptée sur grand écran. On doit distinguer :

- une **date ponctuelle** connue, par exemple une échéance ;
- une **période** réelle début–fin, si elle existe ;
- un **événement accompli** et sa date effective, si le owner l'expose ;
- une **démarche sans date**, qui reste consultable dans une section « À planifier / Date non connue ».

Une Journey peut être active avant sa date prévue, et achevée après elle ; ne pas déduire un état à partir de la position sur la frise. Deux démarches parallèles peuvent apparaître sur la même période sans dépendance entre elles. Le curseur « aujourd'hui » est purement visuel.

La chronologie peut proposer les contrôles « maintenant », zoom d'échelle (semaine, mois, trimestre), filtre des démarches et ouverture de la fiche à partir du jalon. Pas de fausse précision horaire ; une date seule reste une date seule. Si les dates métier sont insuffisantes, montrer une séquence de jalons connus et des éléments non datés plutôt qu'un Gantt artificiel.

#### D. Dépendances — graphe causal

Cette vue présente les **relations explicites** entre les Journeys d'un Dossier. Un lien signifie qu'une démarche dépend d'une autre selon le contrat `DossierJourneyDependency`, pas simplement que deux démarches appartiennent au même Dossier ou se suivent dans le temps.

Exemple illustratif, non exécutable :

```text
Préparer les documents ──► Déposer la candidature ─┐
                                                    ├──► Confirmer l'admission
Obtenir le financement ────────────────────────────┘
                                                    │
                                                    ▼
                                             Organiser le départ
```

Les liens orientés doivent suivre la sémantique « prérequis → démarche qui dépend ». Les branches parallèles restent distinctes ; une convergence explicite indique plusieurs prérequis. Le rendu présente l'état réellement connu des liens : satisfait, non satisfait, levé/waived ou inaccessible selon les champs autorisés. **La projection API actuelle n'expose pas nécessairement tout l'historique ni tous ces états fins** : la vue ne peut pas les inventer.

Interaction attendue :

- sélection d'un nœud → fiche synthétique ou ouverture du détail Journey ;
- sélection d'une arête → explication humaine « X doit être satisfait avant Y » et statut connu ;
- déplacement/zoom/pincement/recentrage sur mobile, navigation clavier et boutons de zoom sur web ;
- affichage d'un sous-graphe utile quand le graphe est dense ;
- fond discret, textes lisibles, sens des flèches explicite ; pas de labyrinthe de fils croisés ni de code couleur incompréhensible ;
- présentation accessible **en liste de dépendances équivalente**, permettant lecture clavier et lecteur d'écran ;
- si aucune dépendance n'est enregistrée : « Aucune dépendance définie », **pas** un graphe de progression auto-inventé ;
- si des liens ou des Journeys sont cachés : montrer une indication prudente de vue partielle provenant de l'owner sans exposer identité ni topologie secrète ;
- le placement des nœuds, l'échelle et les positions peuvent être enregistrés localement comme préférences **d'affichage**, jamais comme faits métier.

La création, la suppression ou la levée d'une dépendance passe par les services Objectives, exige les permissions côté serveur et doit conserver les contrôles de cycles et de cohérence. Une simple manipulation graphique d'un fil n'enregistre pas automatiquement une mutation.

### 7.4 Modules complémentaires du Dossier

**Collaboration et responsabilités.** Afficher les personnes intervenantes selon la disclosure, les Assignments réellement actifs et les rôles d'autorité dans des sections distinctes. « Responsable de cette intervention » ne signifie pas « possède le droit de gérer le Dossier ». Assignment n'accorde aucun Mandate ; le Dossier n'accorde pas automatiquement des droits sur les Journeys.

**Dépendances et blocages.** L'utilisateur doit comprendre la condition et la prochaine conséquence utile, sans recevoir un dump technique d'IDs. Une dépendance hidden/unknown reste explicitement partielle.

**Conversations.** Accès aux échanges contextualisés par Dossier déjà prévus dans la continuité Flutter ; une discussion n'est ni une Journey, ni une obligation de travail supplémentaire.

**Historique métier.** Afficher les changements réellement disponibles, avec provenance si autorisée : liaison d'une Journey, déplacement, changement de cycle de vie, levée d'un prérequis. Ne pas promettre une timeline d'audit complète si aucune projection owner ne l'expose.

**Références transverses.** Documents, Requirements, Access, Payment et Capacity appartiennent à leurs owners. Une carte Dossier peut offrir des liens vers ces profondeurs **à travers les Journeys et contrats autorisés**, pas copier des valeurs sensibles dans un « dossier numérique » parallèle.

### 7.5 Actions Dossier, avec leurs précautions

- Créer un Dossier (personnel ou pour un Espace autorisé).
- Rattacher le Dossier à un Projet visible et gérable ; le déplacer ou le détacher sans le supprimer.
- Lier une Journey existante autorisée ; retirer un lien sans supprimer ou terminer la Journey.
- Ajouter une dépendance entre Journeys déjà liées et compatibles ; la retirer ou la lever avec justification lorsque le service le permet.
- Assigner / retirer une responsabilité opérationnelle.
- Gérer les mandats d'autorité **seulement pour les acteurs réellement autorisés**.
- Modifier le cycle de vie du Dossier selon transitions serveur.
- Modifier les informations descriptives ou la date limite **seulement après vérification du contrat de mutation propriétaire**.
- Ouvrir les détails Journey et les échanges contextualisés.
- Recharger la projection après chaque mutation confirmée et refléter les états d'attente ou de conflit sans succès optimiste trompeur.

Le serveur dispose déjà de services de composition et de gestion Dossier ainsi que de vues web. Il ne faut pas supposer que tous possèdent actuellement une API native. La matrice de capabilities devra être explicitement contractée, pas déduite du type d'utilisateur.

### 7.6 Un Dossier sans Journeys

C'est un cas produit normal. Montrer l'objectif, sa date limite éventuelle, l'état du Dossier et une explication « Aucune démarche liée pour le moment ». Proposer les actions réellement autorisées « Lier une démarche existante », ou orienter vers le parcours d'engagement propriétaire, sans générer de Journey fictive pour meubler l'écran.

---

## 8. Page Démarche / Journey — réutilisation, pas reconstruction

La dernière profondeur de cette hiérarchie est **la Journey existante**. La page Journey ne doit pas être redéveloppée comme une « sous-tâche Makolo » simplement parce que l'utilisateur l'ouvre depuis un Dossier.

Elle garde la vérité de sa démarche et les opérations du domaine propriétaire : activité/opportunité de référence, occurrence si applicable, statut et Readiness, exigences, étapes de processus réellement définies, prochaines actions, formulaires, pièces et preuves, paiements ou accès seulement lorsque le workflow en comporte. Les informations restent viewer-aware et owner-backed.

### 8.1 Entrées et sorties

- **Depuis un Dossier :** ouvrir la Journey par son ID stable ; la page peut montrer « Dans : Dossier X » si le lien est visible et autorisé. Retour au Dossier sans recréer un deuxième détail.
- **Depuis Mes démarches, racine :** une Journey indépendante ouvre exactement le même écran propriétaire.
- **Depuis Maintenant / En cours / Historique :** même identité et même profondeur Journey ; seule la navigation d'origine change.
- **Depuis une notification ou un lien :** ne pas exiger qu'une projection Projet soit préchargée pour ouvrir la Journey.
- **Après action :** refetch ciblé de la Journey, puis des projections Dossier/Projet/collections impactées quand le contrat le justifie.

### 8.2 Affichage et actions Journey

Ne pas forcer les quatre vues du Dossier sur chaque Journey. Garder la page Journey adaptée à son workflow. Une étape, une échéance et un besoin de document doivent être exprimés par les données du propriétaire, sans que Flutter invente un formulaire ou une étape générique.

Si la Journey est terminale, conserver son détail et son historique autorisé ; elle n'est pas effacée du Dossier pour cette seule raison. Si elle est annulée ou dans un état non actif, utiliser le libellé métier réel ; ne pas traduire systématiquement « non actif » en « terminé ».

Les opérations de Journey peuvent être préparées localement lorsque leur contrat le permet, mais jamais déclarées réalisées sans confirmation du domaine propriétaire. Les mutations terminales sans idempotence claire ne sont pas rejouées aveuglément.

---

## 9. Règles temporelles communes aux trois profondeurs

Ce contrat exige de distinguer :

1. **Date de création** : moment où Makolo a enregistré l'objet.
2. **Date de dernière modification** : changement du fait propriétaire, pas forcément progression concrète.
3. **Date de début prévue / réelle** : uniquement si le domaine possède ce fait avec la bonne sémantique.
4. **Date de fin d'horizon** : pour Project `ends_on`, indication durable, pas automatiquement résultat accompli.
5. **Échéance d'un Dossier** : `deadline`, date limite de son objectif.
6. **Dates d'Occurrence / Journey** : selon le domaine ; date seule, plage ou instant, avec fuseau seulement lorsqu'un instant existe.
7. **Date de réalisation / d'achèvement** : fait historique explicite si exposé par le domaine concerné.
8. **Date de l'intervention attendue** : date de prochaine action si une projection la fournit ; distincte de l'échéance générale.

Ces dimensions alimentent des filtres différents. Une « urgence dans trois jours » ne doit pas être fabriquée uniquement parce que trois jours séparent la date locale de l'horizon du Projet. Ne pas afficher « en retard » lorsqu'une échéance est absente, non applicable ou masquée.

Les échéances peuvent changer. Les vues locales signalent la fraîcheur de leurs données et réconcilient l'autorité serveur lors du retour du réseau.

---

## 10. Local-first : consultation immédiate, synchronisation prudente

### 10.1 Promesse de base

L'écran « Mes démarches » **ne doit pas demander au serveur** chaque fois que l'utilisateur change de mode, ouvre/replie un nœud déjà acquis, cherche un titre, filtre, trie ou choisit une suggestion. Il lit la base locale du Profil.

De même, un détail Projet, Dossier ou Journey **déjà acquis** doit s'afficher rapidement à partir de la dernière projection utilisable, pendant que le système évalue discrètement s'il doit la revalider. Cette promesse concerne les données autorisées précédemment connues et encore utilisables selon leur politique de sécurité ; elle ne promet pas de disposer magiquement d'un détail jamais téléchargé.

### 10.2 Premier peuplement et réserve locale

Sur connexion disponible, acquérir une première fenêtre bornée, **environ 20 à 50 éléments récents autorisés** par collection, en tenant compte des pages API disponibles. Par exemple, la collection Objectives de #522 accepte un `limit` jusqu'à 50, même si le client Flutter actuel utilise 24. Le nombre final doit être justifié par les performances mesurées et par la stratégie de rétention, non choisi comme seuil destructif universel.

Conserver dans la base applicative locale :

- identités `kind + id` et métadonnées de collection ;
- dernières projections autorisées Projet, Dossier et Journey nécessaires à leur représentation ;
- relations acquises Projet–Dossier et Dossier–Journey, avec portée et provenance ;
- états et dates **exposés**, sans recopier toute la base Django ;
- indication de complétude/pagination de la collection, date de réception, fraîcheur et état source ;
- préférences locales d'affichage, filtres favoris éventuels, expansion d'arbre, position de lecture ;
- brouillons locaux autorisés, **séparés** des faits confirmés.

Les éléments anciens mais régulièrement consultés, les détails ouverts et les brouillons importants ne doivent pas disparaître uniquement parce que 50 nouveaux objets arrivent. Les politiques de rotation doivent respecter la sensibilité, la portée, les besoins de reprise et les règles existantes de l'application.

### 10.3 Flux de lecture

```text
Ouvrir Mes démarches
    ↓
Lire immédiatement la projection locale du Profil
    ↓
Afficher Cartes / Liste / Explorateur + signal de fraîcheur
    ↓
Si nécessaire et possible : revalider en arrière-plan via Objectives
    ↓
Contrôler acteur, scope, identité et version/horodatage disponibles
    ↓
Réconcilier la base locale sans effacer les brouillons ou détails utiles
    ↓
Actualiser seulement les éléments affectés
```

Même logique d'acquisition à l'ouverture d'un détail. Un pull-to-refresh ou une action « Actualiser » explicite peut déclencher une relecture quand le réseau existe. Il ne faut ni déclencher un refetch sur chaque petit changement de vue ni conserver sans limite des données dont l'autorité a été explicitement révoquée.

### 10.4 Recherche et tri locaux : limites honnêtes

La recherche et les tris portent sur **l'ensemble local acquis**, et non sur une collection supposée exhaustive. Une pagination supplémentaire peut être proposée. Le client ne doit jamais annoncer « aucun autre Projet n'existe » quand seules deux pages ont été synchronisées.

Les pages d'une collection peuvent changer pendant une pagination par offset : nouvelles créations, réordonnancement par `updated_at`, changement de droits. Prévoir déduplication par identité, recomposition de pages, protection contre les réponses tardives et relecture à partir de la première page si une continuité n'est plus fiable. Ne pas assimiler un offset à un snapshot figé.

### 10.5 Hors ligne, échec réseau, révocation

- **Données locales connues + réseau indisponible :** afficher le contenu autorisé utilisable, avec « Dernière actualisation… » ou signal de disponibilité ; recherches, vues et filtres restent locaux.
- **Aucune donnée locale au premier lancement hors ligne :** expliquer que la première synchronisation est nécessaire. Ne pas montrer « Aucun projet » comme si le compte était vide.
- **Échec temporaire de rafraîchissement :** garder les données utilisables, rendre l'erreur récupérable et proposer « Réessayer ».
- **Refus explicite `401/403/404` selon contrat :** respecter la révocation et les politiques de purge ; ne pas réafficher un détail privé comme si le refus était une simple panne de transport.
- **Changement de Profil :** isolation stricte des bases et projections, aucun résultat de recherche ni suggestion du précédent Profil.
- **Action préparée hors ligne :** libellé « brouillon » ou « en attente » seulement si le protocole le permet ; jamais « effectué » avant confirmation.
- **Conflit :** recharger les faits serveur, montrer la différence utile, préserver les saisies non confirmées si permis, demander une décision humaine lorsqu'une mutation n'est pas rejouable sûrement.

Une projection partielle ou un secret masqué reste partiel. La base locale ne sert jamais à contourner les droits du serveur.

### 10.6 Flutter et web : même promesse, stockage adapté

**Flutter installé** utilise la persistance applicative locale isolée par Profil, les sources de synchronisation et les politiques de conservation/retrait propres au runtime. L'objectif est de retrouver les informations acquises même après un cold start ou une perte de réseau.

**Web** partage les mêmes écrans et les mêmes contrats métier, mais son stockage durable dépend du navigateur, de la session, des permissions et de la politique de sécurité des données privées. Ne pas contourner `Cache-Control: private, no-store` en inventant un cache HTTP privé. Une éventuelle base applicative locale web doit être explicitement contractualisée et sécurisée ; sinon, le web peut produire la première vue à partir d'une projection serveur et maintenir une continuité locale de session contrôlée. La parité de produit n'implique pas de prétendre que les navigateurs et Flutter possèdent les mêmes garanties de conservation hors ligne.

Ne pas créer une « API Flutter » parallèle à « l'API web ». Les deux consomment les mêmes propriétaires métier, directement ou par projections de présentation conformes.

---

## 11. Conception visuelle : mature, élégante, professionnelle

### 11.1 Direction artistique

Direction : **éditoriale, structurée, intemporelle, moderne**, sans infantilisation.

- Palette de marque : violet principal `#5232DB`, violet profond `#2B176E`, corail `#FF704D`, texte clair `#FAF7F5`, texte sombre `#0F172A`.
- Surfaces claires, contraste lisible, séparateurs discrets et bordures légères plutôt que plusieurs fonds violets superposés.
- Violet : action principale, liens, sélection active, repères de navigation.
- Corail : situations d'attention justifiées, pas couleur décorative de chaque Dossier.
- Les états « terminé », « en attente » ou « bloqué » reposent sur **texte + icône + couleur**, jamais uniquement sur la couleur.
- Le Makolo Mark conserve son asset canonique ; ne pas dessiner un faux logo en forme de M ou une illustration de pied.
- Pas d'emojis décoratifs, de figurines enfantines, de faux graphiques « gamifiés », de confettis ou d'éléments qui ressemblent à un TP étudiant.
- Ne pas transformer les Projets en couvertures illustrées arbitraires : un bel agencement, une iconographie précise et des données utiles suffisent.

### 11.2 Typographie et respiration

Le titre de page constitue une ancre forte ; les titres d'objets sont affirmés sans surdimensionnement. Sous-titres utiles sur une ou deux lignes lorsque possible, mais jamais coupés si l'information est importante. Métadonnées un cran plus discrètes, sans microtexte illisible.

Rythme cohérent : petites espacements internes réguliers, marges externes respirantes, sections clairement groupées. Cartes à coins modérément arrondis, peu d'ombres et davantage de hiérarchie par l'espacement. Les nombres sont alignés, les dates demeurent lisibles, les labels ne sont pas tronqués au point de devenir ambigus.

### 11.3 Iconographie fonctionnelle

Système d'icônes cohérent, de type trait fin professionnel (Lucide ou équivalent du design system Makolo) :

| Intention | Icône indicative | Usage |
| --- | --- | --- |
| Mes démarches | `folders` | Entrée premium sous Passeport |
| Projet | `folder-kanban` ou `folders` | Horizon regroupant les Dossiers |
| Dossier | `folder` / `folder-open` | Résultat composé |
| Démarche | `route` | Journey canonique |
| Créer Projet/Dossier | `folder-plus`, `plus` | Action explicite avec label |
| Cartes | `layout-grid` | Mode de présentation |
| Liste | `list` | Mode de présentation |
| Explorateur | `folder-tree` | Mode de présentation |
| Chronologie | `calendar-range` | Lecture temporelle |
| Graphe | `git-branch` ou `network` | Dépendances |
| Filtre / tri | `list-filter` / `arrow-down-a-z` | Contrôles |
| Échéance | `calendar-clock` | Date et contexte |
| Responsabilité | `users` | Collaboration |
| Attention / blocage | `circle-alert` | Signaux explicités |
| Conversation | `message-circle` | Handoff existant |
| Retour / profondeur | `arrow-left` / `chevron-right` | Navigation |

Toujours associer l'icône à un mot pour les actions importantes. Ne pas coder des significations différentes avec la même icône partout.

### 11.4 Mobile et grand écran

Sur téléphone : en-tête compact, actions principales accessibles, trois modes lisibles, une colonne de cartes, menus contextuels, panneaux de filtres en feuille modale, gestes avec cibles confortables. Les graphes doivent pouvoir être pincés, déplacés, recentrés et lus sous une représentation textuelle alternative.

Sur tablette et web : largeur de lecture maîtrisée, grille multi-colonnes raisonnable, filtres en bandeau/panneau, possibilité de scinder « collection / détail », graphe plus ample et calendrier plus riche. Le détail peut ouvrir un panneau latéral sans perdre la collection.

**Ce ne sont pas deux produits :** même architecture de navigation, labels, regroupements, tris, filtres, permissions et états. Les variantes ne sont que des adaptations ergonomiques, non des fonctionnalités arbitrairement réservées à un support.

### 11.5 Mouvements et micro-interactions

Transitions courtes et signifiantes entre racine, Projet, Dossier, Journey ; ouverture d'arbre animée sobrement ; indication de rafraîchissement non intrusive. Respecter « réduction des animations ». Pas de transitions spectaculaires qui bloquent l'accès à une action urgente.

Focus clavier visible, ordre de tabulation, supports lecteurs d'écran, raccourcis accessibles sur web ; contrastes, tailles de cibles et alternative textuelle du graphe validés. La densité élevée ne doit pas détruire l'accessibilité.

---

## 12. Actions et menus : quelle opération à quel niveau ?

| Niveau | Actions de lecture et d'organisation locales | Mutations owner-backed à contractualiser/exposer |
| --- | --- | --- |
| Moi | Ouvrir « Mes démarches », lire l'entrée, reprendre la navigation | Aucune mutation métier depuis la tuile seule |
| Mes démarches | Recherche, suggestions, vue Cartes/Liste/Explorateur, tri, filtres, exploration, préférences | Créer Projet, créer Dossier, rattacher après création si autorisé |
| Projet | Synthèse, liste Dossiers, calendrier, filtres, ouvrir Dossier | Lier, délier, déplacer Dossier ; lifecycle Projet ; édition si service disponible |
| Dossier | Synthèse, liste, chronologie, graphe, ouvrir Journey, consulter collaboration | Lier/délier Journey ; dépendance/levée ; Assignment ; Mandate ; Projet parent ; lifecycle ; édition si contrat |
| Journey | Lecture de détail, readiness, prochaines actions, détails propriétaires | Soumission, demande, formulaire, paiement, accès ou autres actions autorisées par les owners concernés |

Une opération métier n'est jamais un simple changement cosmétique d'arbre. La confirmation et la réconciliation suivent le propriétaire. Les mutations portant sur des droits ou des relations ont une confirmation claire, des erreurs explicites et une suite de navigation déterministe.

Une fonction « Supprimer définitivement » ne doit pas être inventée en se fondant sur l'existence d'« Archiver ». La suppression de contenu n'est pas impliquée par le détachement d'un Dossier ou d'une Journey.

---

## 13. États de surface et messages humains

Chaque profondeur doit posséder au moins ces états visuels, adaptés au contexte :

| État | Attendu |
| --- | --- |
| Premier chargement sans données locales | Squelette sobre, message utile, pas de faux zéro |
| Collection connue et réellement vide | Message calme + action de création si autorisée |
| Collection partiellement acquise | Contenu local + signal « suite non chargée » ou « davantage d'éléments » |
| Résultats filtrés vides | « Aucun résultat pour ces critères » + « Effacer les filtres » |
| Dernier snapshot utilisable, réseau coupé | Contenu + indicateur discret de dernière synchronisation |
| Refresh en cours | UI utilisable, sans cacher toute la collection |
| Erreur réseau récupérable | Contenu conservé si permis + « Réessayer » |
| Donnée obsolète | Signal de fraîcheur ; ne pas qualifier d'actuel un état non revalidé |
| Accès retiré | Retrait de détail/relations concernés et message de portée, sans fuite |
| Projet vide | Horizon lisible + création/rattachement autorisé |
| Dossier sans Journey | Objectif lisible + invitation à lier une démarche si autorisée |
| Journey sans Dossier | Détail normal, sans fausse erreur de rattachement |
| Graphe sans dépendances | État vide spécialisé, pas de liens imaginés |
| Graphe partiel pour confidentialité | Signal partiel, sans noms ou arêtes cachés |
| Mutation refusée ou en conflit | Retour d'erreur propriétaire, pas de succès optimiste |
| Brouillon local non confirmé | Libellé de brouillon distinct du lifecycle canonique |

Les messages doivent être en français naturel, courts mais précis. Distinguer « aucun élément accessible », « aucune donnée acquise », « filtre sans résultat » et « actualisation impossible ». Ce sont quatre situations différentes.

---

## 14. Contrats techniques vérifiés dans la PR #522 (état de référence, à revérifier avant développement)

Les références ci-dessous décrivent les chemins et les comportements **observés** lors du cadrage, non une garantie de stabilité éternelle de la branche active.

### 14.1 Modèles et services

- `objectives/models.py` : `Project`, `Dossier`, `ProjectDossierLink`, `DossierJourneyLink`, `DossierJourneyDependency`, Assignments et lifecycles.
- `objectives/selectors.py` : collections viewer-aware, Dossiers visibles d'un Projet, liens Journey visibles et scopes d'autorité.
- `objectives/readiness.py` : Readiness collective dérivée, items et dépendances visibles, prochain mouvement utile, signal de confidentialité partielle.
- `objectives/services.py` : créations, liens et détachements, déplacements, transitions, dépendances, responsabilités et mandats selon les services existants.
- `objectives/views.py` et modèles web : interface serveur capable de création, composition et pilotage avec contrôles d'autorité.
- `objectives/test_d5_project.py` et autres tests métier : invariants de rattachement, indépendance des cycles de vie, confidentialité.

### 14.2 Projections Objectives existantes

| Route actuelle | Projection principale observée | Limites importantes pour la cible |
| --- | --- | --- |
| `GET /api/v1/objectives/projects/` | `objective.project.collection`, éléments visibles paginés, identité et statut | Fournit titre, état, relation, Espace, lien ; pas toutes les dates/relations/indicateurs nécessaires aux tris complets |
| `GET /api/v1/objectives/dossiers/` | `objective.dossier.collection`, même famille | Ne constitue pas une collection hiérarchique intégrale Journey/Projet |
| `GET /api/v1/objectives/projects/<uuid>/` | `objective.project.detail` : `identity`, `horizon`, `state`, `visible_dossiers` | Pas de calendrier complet, readiness détaillée de tous les Dossiers ni capabilities de mutation effectivement renseignées |
| `GET /api/v1/objectives/dossiers/<uuid>/` | `objective.dossier.detail` : `objective`, `state`, `deadline`, `readiness`, `visible_items`, `visible_dependencies`, `personal_responsibilities`, `actor_interventions` | Les données visibles et capacités d'édition ne couvrent pas toutes les interactions UX proposées |

Dans la branche examinée, les collections sont bornées par `limit`/`offset`, avec `limit` valide de 1 à 50. Le dépôt Flutter de collection utilise actuellement 24 éléments par page. Les détails Objectives exposent un tableau `capabilities` actuellement vide ; **ne jamais en déduire que les actions de gestion sont offertes aux clients natifs**.

Les sélecteurs de Projet/Dossier appliquent leur propre scope. La visualisation de nœuds/relations ne peut pas élargir ce scope.

### 14.3 Surfaces clientes existantes

- `mobile/lib/features/me/me_routes.dart` : routes « Mes projets » et « Mes dossiers » depuis Moi, à réunifier dans la conception cible.
- `mobile/lib/features/continuity/objective_collection_screen.dart` : listes locales paginées, actuellement peu profondes ; le commentaire du code distingue explicitement cette liste du chantier d'organisation.
- `mobile/lib/features/continuity/objective_repository.dart` : sources de détail et de collection, lecture de projections locales et rafraîchissement via le moteur partagé.
- `mobile/lib/features/continuity/objective_screen.dart` : affichage des détails Projet et Dossier existants ; entrées conversations contextualisées.
- `core/read_models/personal_ongoing.py` : projection « En cours » qui peut actuellement inclure des Dossiers et Projets ; cette conception ne prétend **pas** l'avoir déjà modifiée.

### 14.4 Écarts de contrat à résoudre avant les commandes effectives

1. Projection racine unifiée ou composition locale sûre des collections existantes, avec relations autorisées parent/enfant nécessaires aux trois vues et à la recherche contextuelle.
2. Champs autorisés de création, modification, date de début/échéance/réalisation, et indicateurs de complétude pour les tris avancés ; ne pas ajouter de fausses dates.
3. Capabilities réellement renseignées et endpoints de mutations natifs réutilisant les services Objectives, au lieu de mutations ad hoc dans Flutter.
4. Politique de cache locale Profil, revalidation et révocation pour collections, détails et relations ; ne pas conserver un aperçu privé après refus explicite.
5. Contrat des préférences de vue et éventuellement de l'importance déclarée ; ces préférences ne deviennent pas arbitrairement un nouvel état métier propriétaire.
6. Contrat de timeline et de graphe fondé sur les seules dates et dépendances exposables, avec gestion des champs masqués et des projections partielles.
7. Mise à jour web et Flutter du **même contrat UX**, tests de navigation et d'accessibilité ; ne pas remplacer les pages web matures par des stubs natifs ni traiter le web comme une app auxiliaire.

Ces écarts forment un plan d'intégration ; ils ne constituent pas une autorisation implicite d'ajouter des modèles, des migrations ou des APIs de manière indiscriminée.

---

## 15. Articulation future avec « Maintenant », « En cours » et « Historique »

Le présent chantier cible « Moi ». Il doit cependant préserver la continuité du shell :

- **Maintenant** reste la surface des conséquences et actions réellement pertinentes aujourd'hui, y compris lorsqu'elles proviennent d'une Journey dans un Dossier.
- **En cours** reste la surface des engagements actifs. Dans une phase ultérieure, son regroupement souhaité montrera les **Dossiers actifs** pour les Journeys qu'ils regroupent, et les **Journeys indépendantes actives** directement ; les Projets ne doivent pas devenir une couche de cartes opérationnelles supplémentaires. L'implémentation actuelle peut encore contenir des Projets dans sa projection : ce changement est un chantier distinct.
- **Historique** permet de retrouver les parcours achevés et les autres événements historiques selon leurs statuts réels. Une démarche annulée, abandonnée ou archivée n'est pas faussement présentée comme accomplie.
- **Moi → Mes démarches** reste l'explorateur complet, tous états et horizons confondus, pas seulement « actif ».

Exemple : 13 Journeys actives ; quatre liées au Dossier A, trois au Dossier B, deux au Dossier C et quatre indépendantes. La future vue d'« En cours » pourra montrer **trois Dossiers + quatre Journeys indépendantes** (sept entrées au lieu de treize), tout en laissant les Journeys accessibles à l'intérieur des Dossiers. C'est un **regroupement de représentation**, jamais une suppression ni une baisse artificielle des engagements.

La même Journey peut alimenter une attention dans Maintenant et rester ouverte dans son Dossier, sans duplication d'identité.

---

## 16. Scénarios détaillés de navigation à valider

### 16.1 Projet personnel avec plusieurs Dossiers

Une personne crée « Étudier au Canada » dans Mes démarches. Ce Projet possède éventuellement un horizon de début/fin. Elle crée un Dossier « Admission », un Dossier « Financement », puis un Dossier « Préparer le départ ». La page Projet présente ces Dossiers et leurs échéances connues ; la page Dossier présente les Journeys qui concourent à son objectif. Une Journey terminée reste attachée au Dossier ; le Projet reste actif jusqu'à transition validée.

### 16.2 Dossier autonome et Journey autonome

Une personne crée « Organiser mon voyage à Kolwezi » sans Projet et lui rattache deux Journeys. Ces deux démarches sont accessibles depuis le Dossier. Une autre Journey « Louer un véhicule » n'appartient à aucun Dossier ; elle reste visible à la racine Mes démarches et s'ouvre avec exactement le même écran Journey canonique.

### 16.3 Déplacer un Dossier entre Projets

Un Dossier existe dans Projet A. L'utilisateur autorisé choisit « Déplacer vers Projet B ». Makolo vérifie l'autorité sur A, B et le Dossier. Après succès, l'affichage local se réconcilie : le Dossier apparaît sous B, plus sous A. Il conserve ses Journeys, son ID et son historique de lien. En cas de refus, l'interface conserve la situation antérieure et explique le conflit.

### 16.4 Parcours temporel différent de la causalité

Une Journey « Obtenir les documents » se déroule avant la candidature ; « Financement » peut progresser en parallèle. La chronologie montre leurs dates ; le graphe montre **uniquement** les dépendances explicites. Sans dépendance enregistrée entre Financement et Candidature, le graphe ne relie pas ces deux nœuds pour « embellir » la présentation.

### 16.5 Données partielles et réseau coupé

Le téléphone conserve 24 Dossiers et deux détails Projet ; 50 autres n'ont pas encore été téléchargés. Hors ligne, l'utilisateur peut ouvrir ses détails connus, filtrer, trier et voir le graphe déjà acquis. Makolo indique la dernière actualisation et la couverture partielle ; une recherche sans résultat local ne signifie pas absence serveur. Il ne peut pas confirmer le déplacement d'un Dossier, mais peut éventuellement conserver une préparation si le contrat de mutation le permet.

### 16.6 Acteur Espace et confidentialité

Un utilisateur a le droit de voir un Projet d'Espace mais pas l'un de ses Dossiers liés. Il voit uniquement les Dossiers autorisés. Ni le nombre total caché, ni un nom, ni un noeud de graphe, ni une suggestion de recherche locale ne doivent révéler le Dossier interdit. Un Assignment simple ne permet pas de gérer les mandats.

### 16.7 Passage web / mobile

La personne consulte sur web le Projet « Étudier au Canada », puis ouvre Makolo Flutter. Elle retrouve le même Projet, le même Dossier et les mêmes Journeys selon ses permissions ; la vue peut être en calendrier large sur web et en frise verticale sur téléphone. Les états, titres et droits ne changent pas selon le support. La réconciliation suit les mêmes owners.

---

## 17. Exigences de qualité et critères d'acceptation

### 17.1 Navigation et organisation

- Une seule entrée « Mes démarches » de premier rang sous Passeport dans Moi ; les deux raccourcis redondants Projet/Dossier sont réunis.
- Trois vues cohérentes dans Mes démarches : Cartes, Liste, Explorateur ; préférence de vue restaurée.
- Les Dossiers sans Projet et Journeys sans Dossier ne disparaissent pas.
- Projet → Dossier → Journey fonctionne aussi par deep link direct ; retour préserve contexte.
- Le mode explorateur différencie ouverture du noeud et ouverture du détail ; les comptes visibles restent corrects.
- Aucune relation cachée ne fuit par les ancêtres, badges, suggestions ou compteurs.

### 17.2 Recherche, temps et données

- Recherche et autocomplétion locales sans requête pour chaque frappe ; support des accents et titres longs.
- Tris nom, création, modification, début, échéance et importance **uniquement quand le fait existe** ; aucun pseudo-tri silencieux.
- Distinction claire des filtres de date de création, horizon, échéance et date effective.
- Collections partielles identifiées, pagination cohérente, pas de duplication d'une Journey comme plusieurs engagements.
- Les dates `date-only` restent `date-only` ; dates absentes signalées proprement.

### 17.3 Projet, Dossier et Journey

- Projet : Synthèse / Dossiers / Calendrier ; dates de jalons et périodes sans faux Gantt.
- Dossier : Vue d'ensemble / Liste / Chronologie / Dépendances ; prochaine intervention issue de Readiness.
- Graphe causal fidèle aux dépendances autorisées ; nœuds sélectionnables ; alternative accessible textuelle ; pas de dépendance inférée de l'ordre des dates.
- Journey : écran propriétaire réutilisé, quel que soit l'accès depuis Projet/Dossier/En cours/Historique.
- Détachement et déplacement conservent l'identité et les données métier du Dossier ; terminaux, annulations et archives conservent leurs sémantiques propres.

### 17.4 Local-first et sécurité

- Premier affichage d'un snapshot local acquis sans bloquer l'UI sur le réseau.
- Réouverture après cold start et travail sans réseau sur les éléments déjà acquis.
- Refresh sans effacer les données utiles pendant une panne temporaire.
- Refus explicite et changement de Profil ne divulguent aucun ancien objet privé.
- Aucun état « action réussie » avant confirmation propriétaire ; brouillons persistés séparément lorsque permis.
- Pas de contournement de la politique HTTP/web et pas de duplication d'owner.

### 17.5 Présentation et accessibilité

- Vérification à plusieurs tailles : téléphone étroit, téléphone large, tablette, desktop.
- Icônes, espacements, libellés, tonalité et hiérarchie Makolo homogènes sur Flutter et web.
- Contrôle clavier complet des listes, menus, filtres et graphes ; lecteurs d'écran ; respect du mouvement réduit.
- Aucun élément critique uniquement codé par couleur ; contrastes vérifiés.
- États de chargement, zéro connu, recherche vide, offline, stale, partiel, refus et conflit visuellement distincts.
- Aucune donnée « démo » présentée comme un fait du compte réel.

---

## 18. Discipline d'implémentation sur la PR #522

**Le présent document ne modifie pas le runtime.** Lors de l'exécution ultérieure, commencer par relire le HEAD réel de #522, les diffs, le blueprint, les permissions, les tests et les chantiers qui ont pu évoluer. La PR est une branche de travail vivante : ne pas repartir du chantier D depuis zéro, ne pas recréer des modèles, ne pas ouvrir une PR parallèle pour contourner des conflits.

Ordre recommandé **incrémental**, non un « big bang » :

1. figer les contrats de projection et les gaps réels des collections/relations/dates ;
2. réunifier l'entrée Moi et l'espace « Mes démarches » à partir des repositories existants ;
3. implémenter les trois modes d'organisation et recherche/tris/filtrage locaux avec couverture partielle explicite ;
4. compléter Projet avec Synthèse, Dossiers et Calendrier, uniquement sur faits autorisés ;
5. compléter Dossier avec Vue d'ensemble, Liste, Chronologie et Graphe de dépendances ;
6. raccorder les actions à des services Objectives via des contrats sécurisés et testables ;
7. vérifier la continuité vers Journey et les conversations, sans duplication ;
8. harmoniser le web dans **le même contrat produit** ; tester les variantes responsive et l'accessibilité ;
9. réaliser les tests ciblés, suites pertinentes, vérifications de migrations éventuelles, parité des permissions, cold-start, multi-Profil, refus et CI de la PR ; ne pas merger rouge.

À chaque étape : petits commits traçables et réversibles ; résumer les fichiers et impacts avant commit/push ; conserver les tests exigeants ; ne pas affaiblir les protections pour obtenir du vert.

### Références canoniques

- `docs/architecture/makolo-domain-blueprint.md` : frontières et invariants (`Dossier`, `Project`, `Journey`).
- `docs/architecture/strategic-action-roadmap.md` : D — objectifs composés, horizons durables, structured handoff, readiness.
- `docs/ux/Makolo_Contrat_Moi_et_Nous_Gele_2026-10-06.md` : Moi comme capital personnel, non En cours bis.
- `docs/architecture/z10-cross-surface-continuity.md` : identités, destinations, scopes et handoffs.
- `docs/architecture/mobile-a0-architecture-reconciliation.md` : local-first natif et autorité serveur.
- `objectives/models.py`, `objectives/selectors.py`, `objectives/readiness.py`, `objectives/services.py`, `objectives/api_views.py` et tests Objectives.
- `mobile/lib/features/me/me_routes.dart`, `mobile/lib/features/continuity/objective_collection_screen.dart`, `objective_repository.dart` et `objective_screen.dart`.

**Règle de clôture conceptuelle :** un seul Makolo, une seule vérité métier, plusieurs profondeurs d'une même expérience ; Projet pour l'horizon, Dossier pour l'accomplissement composé, Journey pour la démarche réelle. La forme doit être belle et mature, mais jamais plus importante que la compréhension, l'action autorisée et la confidentialité.
