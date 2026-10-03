# Feature Specification: Mobile Personal Mature — Batch 1 Parallel Contract

**Feature Branch**: `spec/mobile-personal-batch1-contract`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Créer uniquement le contrat commun Spec Kit du premier lot parallèle Mobile Personal Mature pour Maintenant, Découvrir, En cours et Moi, sans implémenter de surface produit."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lancer quatre lanes réellement indépendantes (Priority: P1)

En tant qu’intégrateur Mobile Personal Mature, je veux que les quatre surfaces Maintenant, Découvrir, En cours et Moi disposent de frontières communes explicites afin que quatre agents ou développeurs puissent commencer depuis le même `main` sans dépendance entre lanes et sans réécrire les fondations Presentation.

**Why this priority**: Le but même de ce work item est de rendre le parallélisme sûr avant toute implémentation de surface.

**Independent Test**: À partir de cette seule spécification, quatre propriétaires distincts peuvent chacun identifier leur question humaine, leur périmètre de feature, les zones qu’ils ne doivent pas modifier et les fondations qu’ils doivent réutiliser, sans devoir attendre le travail d’une autre lane.

**Acceptance Scenarios**:

1. **Given** le `main` vérifié et le socle Presentation partagé déjà fermé, **When** les quatre lanes sont préparées, **Then** chacune part du même SHA de base et aucune lane n’est déclarée dépendante d’une autre.
2. **Given** un besoin de composition propre à une surface, **When** une primitive partagée existante couvre déjà le besoin, **Then** la lane la réutilise au lieu d’introduire une variante locale de convenance.
3. **Given** une même réalité canonique visible sur plusieurs surfaces, **When** elle est projetée dans Maintenant et En cours, **Then** son identité propriétaire peut rester commune tandis que la sémantique de présentation reste distincte.

---

### User Story 2 - Préserver la personnalité de chaque surface (Priority: P1)

En tant que personne utilisant Makolo, je veux que Maintenant, Découvrir, En cours et Moi restent immédiatement reconnaissables par leur rôle humain même s’ils partagent le même langage visuel, afin que Makolo ne devienne pas un dashboard uniforme de cartes.

**Why this priority**: Le partage de composants n’a de valeur que s’il ne détruit pas les modèles mentaux distincts des quatre surfaces.

**Independent Test**: Une revue de chaque lane peut démontrer que sa composition répond à sa question humaine propre et n’est pas seulement une variation de padding, radius, grille ou breakpoint d’une surface générique.

**Acceptance Scenarios**:

1. **Given** la surface Maintenant, **When** son expérience est définie, **Then** elle priorise conséquence et respiration cognitive autour de « Qu’est-ce qui compte maintenant ? ».
2. **Given** la surface Découvrir, **When** son expérience est définie, **Then** elle priorise champ et représentation autour de « Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ? ».
3. **Given** la surface En cours, **When** son expérience est définie, **Then** elle priorise continuité et état autour de « Parmi ce que j’ai réellement engagé, où en suis-je et qu’est-ce qui continue ? ».
4. **Given** la surface Moi, **When** son expérience est définie, **Then** elle priorise structure et capital autour de « Qu’est-ce qui est déjà en place autour de moi pour faciliter la suite ? ».

---

### User Story 3 - Intégrer les surfaces avec la vérité runtime (Priority: P1)

En tant qu’utilisateur mobile, je veux que les quatre surfaces présentent le réel déjà acquis localement et se réconcilient avec le serveur sans faux succès ni faux état global d’erreur, afin que Makolo reste utile et honnête lorsque le réseau varie.

**Why this priority**: Le Mobile Mature ne peut pas être validé sur de faux objets Presentation isolés ; la continuité local-first et l’autorité serveur font partie du contrat produit.

**Independent Test**: Chaque lane peut être validée avec contenu local disponible, perte réseau, refresh en erreur, opération en attente et vrai vide synchronisé, sans transformer ces états en une seconde vérité métier.

**Acceptance Scenarios**:

1. **Given** un contenu déjà acquis localement, **When** le réseau disparaît, **Then** le contenu reste consultable avec un état réseau honnête au lieu d’un écran d’erreur global.
2. **Given** une action locale en attente de confirmation distante, **When** l’interface la présente, **Then** elle n’affiche pas un niveau de succès supérieur à celui réellement acquis.
3. **Given** une réponse serveur seedée de démonstration ou une réponse serveur réelle de même contrat, **When** elle traverse la chaîne runtime, **Then** le code de production ne dépend pas de l’origine « démo » ou « réelle » du serveur.

---

### User Story 4 - Réconcilier les quatre lanes sans redesign (Priority: P2)

En tant qu’intégrateur, je veux une étape finale unique de réconciliation après les quatre PR de lane afin de valider l’ensemble comme une seule expérience mobile cohérente sans rouvrir la conception propre de chaque surface.

**Why this priority**: Le parallélisme réduit le temps de réalisation mais crée un risque transversal qui doit être traité une fois, explicitement, après les quatre lanes.

**Independent Test**: Les quatre lanes peuvent être évaluées ensemble sur navigation, continuité, identité cross-surface, offline/reconnect, adaptation, thèmes, grands textes et références Golden sans modifier leurs responsabilités métier.

**Acceptance Scenarios**:

1. **Given** quatre PR de lane terminées, **When** la réconciliation finale commence, **Then** elle vérifie les écarts transversaux réels plutôt que de redesign les quatre surfaces.
2. **Given** une divergence de primitive partagée, **When** elle est détectée, **Then** elle est résolue au niveau commun approprié et non par quatre copies locales.
3. **Given** une lane terminée avant les autres, **When** son PR est prête, **Then** sa disponibilité ne force pas un merge anticipé qui compromettrait la réconciliation prévue.

### Edge Cases

- Une lane découvre qu’aucune primitive commune existante ne couvre un besoin réel : elle déclenche le protocole `COMMON GAP` au lieu de créer une copie locale.
- Une lane estime devoir modifier un seam protégé : elle doit déclarer le blocker avant toute modification ; le besoin reste intégrateur-owned tant qu’il n’est pas requalifié explicitement.
- Le `main` évolue avant le lancement d’une lane : la lane doit revalider sa base et ses collisions avant de commencer, plutôt que d’utiliser le SHA historique de cette spec comme vérité permanente.
- Une surface possède du contenu local mais un refresh échoue : le contenu reste présent et l’échec de rafraîchissement reste un axe distinct.
- Une surface est vide après synchronisation valide : ce vide ne doit pas être confondu avec « contenu non acquis » ou « erreur réseau ».
- Une même réalité apparaît sur plusieurs surfaces : l’identité canonique peut être commune, mais les projections Presentation ne sont pas fusionnées dans un modèle universel.
- Un Golden structurel et le rendu Flutter divergent légèrement : le Golden protège hiérarchie, composition et comportement ; un SVG ou une maquette n’est pas une vérité pixel parfaite du runtime.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le contrat MUST définir exactement quatre lanes sœurs : Maintenant / Now, Découvrir / Discover, En cours / Ongoing et Moi / Me.
- **FR-002**: Les quatre lanes MUST partir du même `main` vérifié au moment de leur création et MUST rester indépendantes les unes des autres.
- **FR-003**: Chaque lane MUST posséder sa composition de surface, ses selectors/adapters propres, ses tests, ses références Golden et ses fichiers de feature, sans posséder les fondations communes.
- **FR-004**: Les lanes MUST réutiliser en priorité le socle Presentation partagé déjà fermé, notamment les primitives et contrats communs existants, avant toute création locale équivalente.
- **FR-005**: Une primitive visuelle commune MUST rester une forme de rendu et MUST NOT devenir une sémantique métier universelle.
- **FR-006**: Une même identité canonique MAY soutenir plusieurs surfaces, mais les projections de Maintenant, En cours, Découvrir et Moi MUST conserver leur sémantique propre.
- **FR-007**: Le contrat MUST préserver les personnalités suivantes : Maintenant = conséquence + air ; Découvrir = champ + représentation ; En cours = continuité + état ; Moi = structure + capital.
- **FR-008**: Le contrat MUST interdire qu’un partage de primitives transforme les quatre surfaces en variantes d’un dashboard générique de Cards.
- **FR-009**: Les écrans de production MUST être alimentés par la chaîne de vérité runtime `API réelle → synchronisation/repository → store local → selector/adapter → Presentation → UI`; les scénarios Presentation de développement MUST NOT devenir la source runtime principale.
- **FR-010**: Le code de production MUST NOT dépendre du fait que le serveur utilise des données réelles ou des données seedées de démonstration, tant que le contrat serveur est identique.
- **FR-011**: Le contrat MUST préserver `localement disponible ≠ localement autoritaire` et `acquis localement ≠ déjà vu`.
- **FR-012**: Les surfaces MUST permettre les combinaisons `content + offline`, `content + pending`, `content + refresh error` et `empty + synced` sans les réduire à un état global unique.
- **FR-013**: Les zones communes/integrator-owned sont : `mobile/lib/design/**`, `mobile/lib/presentation/contracts/**`, `mobile/lib/dev/scenarios/**`, `mobile/lib/dev/gallery/**`, `mobile/test/support/**` et `docs/architecture/mobile-presentation-foundation-closure.md`.
- **FR-014**: Les seams actor context, app runtime, shell, router, sync engine, ProfileStore, Drift schema et fondations d’acteur Space MUST rester integrator-owned.
- **FR-015**: La lane Now MUST être bornée à `mobile/lib/features/now/**` et à ses tests propres ; la lane Ongoing à `mobile/lib/features/ongoing/**` et à ses tests ; la lane Discover à `mobile/lib/features/discovery/**` et à ses tests ; la lane Me à `mobile/lib/features/me/**` et à ses tests.
- **FR-016**: Toute lane qui détecte un manque partagé MUST utiliser le protocole `COMMON GAP` avec : manque constaté, insuffisance du socle actuel, lanes potentiellement concernées et proposition minimale d’extension.
- **FR-017**: Les lanes MUST NOT modifier un seam protégé sans blocker démontré et déclaré avant modification ; les seams protégés incluent actor context, app runtime, shell, router, sync engine, ProfileStore schema, Drift schema, migrations Django, migrations Drift, permissions globales et architecture Space.
- **FR-018**: Le premier batch MUST couvrir les références Golden G01–G09 : Now G01–G02, Discover G03–G05, En cours G06–G07 et Moi G08–G09.
- **FR-019**: Les vraies baselines de rendu MUST utiliser le harness commun ; les références graphiques externes ne MUST NOT être traitées comme vérité pixel parfaite du runtime.
- **FR-020**: Les lanes MUST réutiliser les règles adaptatives partagées et MUST NOT redéfinir localement breakpoints, marges, max-width, viabilité de split, minima de grille, comportements Focus/Depth, ratios média ou composition globale des états.
- **FR-021**: Le passage Compact ↔ Wide MUST préserver la même vérité métier et, lorsque pertinent, la sélection, la profondeur, le focus, le scroll, les filtres, la requête, la position carte, le zoom et le brouillon.
- **FR-022**: Le contrat MUST interdire les abstractions ou duplications suivantes dans les lanes : `UniversalMakoloCard`, `GoldenCard`, `GenericSurface`, `UniversalScreen`, `UniversalPresentationItem`, nouveau modèle mobile `Possibility`, modèle persistant `SituationNow`, modèle persistant `Continuity`, ranking local, Readiness locale, nouveau shell, nouveau router, deuxième système d’état, deuxième sync engine, JSON UI universel, média décoratif orphelin, fake success et CTA inventé sans capability réelle.
- **FR-023**: Le chantier serveur Mobile Mature Demo Universe MUST être traité comme dépendance d’intégration et MUST NOT bloquer le démarrage des quatre lanes avec les contrats runtime, fixtures, Goldens et selectors déjà disponibles.
- **FR-024**: Aucune lane MUST être considérée intégrée avant validation contre les vraies réponses API seedées prévues pour le Mobile Mature Demo Universe.
- **FR-025**: La stratégie de livraison MUST conserver une branche et une PR par lane ; les PR MAY rester ouvertes pendant le développement parallèle et MUST être réconciliées avec le `main` courant avant intégration finale.
- **FR-026**: Une étape finale unique MUST vérifier ensemble les quatre surfaces, la vraie API, le store local, l’identité cross-surface, la navigation, Back/restoration, offline/reconnect, thèmes clair/sombre, text scaling, adaptation responsive, Goldens, Component Gallery, absence de primitives dupliquées, CI, build Android et APK de test.
- **FR-027**: L’étape finale de réconciliation MUST corriger uniquement les écarts transversaux démontrés et MUST NOT devenir un redesign des quatre surfaces.
- **FR-028**: Cette feature commune MUST NOT contenir un plan de codage détaillé des quatre surfaces, MUST NOT créer de tasks d’implémentation produit et MUST NOT implémenter de surface mobile.

### Key Entities *(include if feature involves data)*

- **Lane**: unité indépendante de travail pour une seule surface personnelle ; possède sa composition, ses adapters/selectors, tests et références Golden, mais pas les fondations communes.
- **Common Presentation Foundation**: ensemble déjà fermé de primitives, contrats, états, géométrie adaptative, médias, scénarios, gallery et harness communs que les lanes doivent réutiliser.
- **Protected Seam**: zone transversale dont l’ownership reste à l’intégrateur et qui ne peut être modifiée par une lane sans blocker explicite.
- **COMMON GAP**: signal structuré utilisé lorsqu’un besoin réellement partagé n’est pas couvert par la fondation commune.
- **Integration Gate**: validation finale commune après les quatre lanes, destinée à détecter les divergences transversales sans redéfinir leurs personnalités.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Les quatre lanes peuvent être lancées depuis une même base vérifiée sans dépendance séquentielle entre elles et avec un owner de fichiers non ambigu pour 100 % des zones explicitement couvertes par ce contrat.
- **SC-002**: Les neuf références Golden G01–G09 sont attribuées exactement une fois à une lane et aucune n’est orpheline ou possédée par plusieurs lanes.
- **SC-003**: Une revue du contrat ne trouve aucune primitive commune de convenance explicitement autorisée à être dupliquée localement et aucun seam protégé sans owner défini.
- **SC-004**: Les quatre personnalités de surface peuvent être expliquées chacune en une phrase distincte et aucune n’exige un modèle Presentation universel partagé pour être comprise.
- **SC-005**: Les scénarios critiques local-first couverts par le contrat distinguent au minimum quatre combinaisons indépendantes : contenu hors ligne, contenu avec opération en attente, contenu avec erreur de refresh et vide synchronisé.
- **SC-006**: La réconciliation finale possède un gate explicite couvrant les quatre surfaces ensemble et n’ajoute aucune cinquième feature produit.
- **SC-007**: Le contrat commun peut être utilisé pour ouvrir quatre features Spec Kit séparées sans devoir modifier cette spec pour préciser les frontières de fichiers, les seams protégés, le protocole COMMON GAP, les Goldens ou la doctrine local-first.

## Assumptions

- Le SHA de référence vérifié pour ce work item est `main@297a4c635dafc49d78a95fd463a30a13ffa5ef54`; toute lane future revalidera le `main` courant avant de démarrer.
- Le commit `6b2b4b4748b2e7f01f1deacd12f7fbbf46a59ec8` a déjà fermé le socle Presentation partagé et est intégré dans `main`.
- Au moment de cette spécification, aucune pull request ouverte ne collisionne avec `mobile/**`; les nombreuses branches `mobile/*` existantes sont traitées comme historiques ou dormantes tant qu’aucune PR active ne les rend concurrentes.
- Les contrats UX canoniques actuels de Now, Ongoing, Discover, Personal Action Capital/Moi, ainsi que les contrats mobile, local-first et backend UX projection, restent les références sémantiques ; le runtime courant garde priorité s’ils évoluent.
- Les scénarios et fixtures Presentation sont des moyens de développement et de validation, pas une source de vérité de production.
- Le Mobile Mature Demo Universe serveur est un chantier parallèle distinct : il peut fournir les données d’intégration finales sans devenir une dépendance de démarrage des lanes.
- Cette feature ne crée ni modèle métier, ni migration, ni API, ni nouveau composant de production, ni cinquième surface.
