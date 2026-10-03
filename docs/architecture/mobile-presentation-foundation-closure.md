# Mobile — fermeture du socle Presentation partagé

**Statut :** contrat de fermeture commun avant développement parallèle des surfaces personnelles  
**Portée :** Flutter Presentation uniquement  
**Base de travail :** main@b0ca5e4edd823a3124ea61b198f761a4ab4ceff2

## 1. But

Cette fermeture prépare quatre lanes qui pourront travailler en parallèle sur Maintenant, En cours, Découvrir et Moi sans réinventer les mêmes règles de Card, Section, responsive, états local-first, média, Focus ou fixtures.

Elle ne livre pas les écrans finaux.

> Presentation représente les faits ; elle ne les possède pas.

Une même vérité canonique peut soutenir plusieurs projections ; la question humaine de la surface reste distincte.

## 2. Ce que la fondation possède

La fondation partagée possède seulement :

- les tokens et classes de largeur Presentation ;
- les règles géométriques génériques ContentFrame, AdaptiveSplit, AdaptiveGrid, FocusPane et SpatialFrame ;
- le cadre média commun et ses ratios ;
- la composition des états déjà portée par MakoloSurfacePresentation ;
- des contrats d'entrée Presentation minimaux et distincts pour Now, Ongoing, Moi et Mark ;
- le catalogue déterministe de scénarios ;
- la gallery dev-only ;
- le harness de tests Presentation.

Elle ne possède ni Readiness, ni Permission, ni Mandate, ni Access, ni Capacity, ni Payment, ni Journey, ni Requirement, ni ranking, ni autorité.

## 3. Réutilisation obligatoire

Les lanes réutilisent avant toute création locale :

- MakoloCard ;
- MakoloSection ;
- MakoloMetadata ;
- MakoloStatus ;
- MakoloAttentionBlock ;
- MakoloStateTransition ;
- MakoloTimeline lorsqu'une vraie séquence existe ;
- MakoloDetailHeader ;
- MakoloSkeleton ;
- MakoloEmptyState ;
- MakoloErrorState ;
- MakoloNotice et les indicateurs réseau/succès existants.

Aucune lane ne crée une NowCard, OngoingCard, DiscoverCard ou MeSection uniquement pour du padding, un radius ou un breakpoint.

## 4. Adaptive Presentation

MakoloLayout reste le propriétaire unique des tokens partagés. Les classes Presentation sont :

    Compact   < 720
    Medium    >= 720
    Wide      >= 960
    VeryWide  >= 1440

Ces classes décrivent l'espace disponible. Elles ne décrivent pas un appareil.

Les seuils de composition restent distincts du shell :

    Moi two-column       840
    Jour J participant   880 candidat v1.1
    En cours split       960
    Now Focus split      960
    Discover Spatial    1040
    Jour J opérateur    1200
    Very Wide           1440

Le seuil du rail du shell existant reste inchangé. Une surface peut donc changer de composition sans changer la navigation.

MakoloAdaptiveSplit n'autorise un split que lorsque le seuil demandé ET les minima géométriques Field + gutter + Focus tiennent réellement.

## 5. Média et spatial

Ratios communs :

    1:1   identité / avatar / petite ressource
    4:3   représentation standard
    16:9  paysage / vidéo contextuelle
    3:4   document / credential / affiche
    fluid map / scanner / espace spatial

Le média reste contextuel. Il ne devient ni contenu orphelin ni propriétaire d'une vérité.

MakoloSpatialFrame reçoit un vrai composant spatial en production et peut recevoir une fixture déterministe dans la gallery ou les tests.

## 6. États

La fermeture conserve le système multi-axes existant :

    availability
    freshness
    reachability
    authority
    commit
    failure
    refreshing

Il ne faut pas créer un second enum global SurfaceState.

Combinaisons à préserver explicitement :

- content + offline : le contenu connu reste visible ;
- content + pending : aucun faux succès ;
- content + refresh error : le contenu reste visible avec support local ;
- empty + synced : vrai vide connu.

Les familles de vide ont des sens différents et ne doivent pas être confondues :

    TRUE EMPTY
    COMPLETION / CALM
    NO MATCH
    UNAVAILABLE / NOT ACQUIRED
    LOCAL SECTION EMPTY

Exemples : « Tout est en ordre. ✓ » est un calme Now, pas une absence d'acquisition ; « aucun résultat » dans Discover n'affirme pas qu'aucune possibilité n'existe globalement.

## 7. Identité cross-surface

Les scénarios réutilisent les références canoniques StructuredDestination(kind, id) déjà présentes dans le runtime.

Une même Journey demo-visa-canada peut donc soutenir une Situation Now et une Continuité En cours sans créer un VisaCardModel.

    NowSituationPresentation != OngoingContinuityPresentation

Même identité logique possible, sémantique Presentation différente.

## 8. Scénarios

Le catalogue mobile/lib/dev/scenarios/ est exclusivement développement, test et Golden futur.

Règles :

- horloge fixe 2026-11-12T13:42:00Z ;
- identités stables ;
- aucune valeur aléatoire ;
- aucune image publique ni dépendance réseau ;
- fixture:// pour les médias de démonstration ;
- distinction explicite runtimeCompatible / targetPresentation.

Les scénarios couvrent Now, Discover, Ongoing, Moi, Jour J participant/opérateur et Mark, avec une correspondance G01-G14.

Les payloads runtime-compatibles suivent les shapes actuelles utiles aux futurs tests selector → Presentation → UI. Les scénarios target peuvent représenter un contrat Golden mature sans prétendre qu'un payload serveur identique existe déjà.

## 9. Gallery et tests

Entrée dev-only :

    mobile/lib/dev/main_presentation_gallery.dart

Elle n'est importée ni par mobile/lib/main.dart, ni par le router de production.

La gallery expose Foundations, Primitives, Patterns, States et Scenario Catalog, avec contrôles de thème, viewport, text scale et Reduce Motion.

Le harness partagé permet de pomper un composant avec viewport, thème, text scale et Reduce Motion déterministes.

Les tests de fermeture protègent :

- classification adaptive ;
- seuils et minima Field/Focus ;
- largeur maximale de lecture ;
- content + offline ;
- content + refresh error ;
- content + pending ;
- identités et horloge déterministes ;
- présence des scénarios G01-G14 ;
- absence de réseau dans les fixtures ;
- démarrage et reflow de la gallery.

## 10. Frontières pour le travail parallèle

Après merge :

    commun / intégrateur
    mobile/lib/design/**
    mobile/lib/presentation/contracts/**
    mobile/lib/dev/scenarios/**
    mobile/lib/dev/gallery/**
    mobile/test/support/**
    docs/architecture/mobile-presentation-foundation-closure.md

    lane Now
    mobile/lib/features/now/**

    lane En cours
    mobile/lib/features/ongoing/**

    lane Discover
    mobile/lib/features/discovery/**

    lane Moi
    mobile/lib/features/me/**

Les seams acteur, shell, router et sync restent intégrateur-owned.

Une lane qui découvre un vrai manque commun propose une petite extension du socle au lieu de créer une copie locale.

## 11. Anti-features

Interdits dans les lanes :

- UniversalMakoloCard ;
- GoldenCard ;
- GenericSurface / UniversalScreen ;
- modèle persistant Possibility, SituationNow ou Continuity côté mobile ;
- PresentationItem universel ;
- ranking local ;
- Readiness locale ;
- deuxième router, shell, système d'état ou sync engine ;
- JSON UI universel ;
- média décoratif sans contexte.

La fermeture vise une cohérence commune sans effacer la personnalité propre de chaque surface.
