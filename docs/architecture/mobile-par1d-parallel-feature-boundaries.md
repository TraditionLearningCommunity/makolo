# Mobile PAR-1D — Parallel Feature Boundaries

**Checkpoint :** PAR-1D  
**Base :** `main@b4ea00b1a7cf8981d105140464d9751338a510ef`  
**Objet :** réduire les hotspots centraux sans introduire de framework modulaire.

## Ownership

Feature-owned :

- `mobile/lib/features/now/**` — Maintenant ;
- `mobile/lib/features/ongoing/**` — En cours ;
- `mobile/lib/features/me/**` — Moi ;
- `mobile/lib/features/discovery/**` — Découvrir ;
- `mobile/lib/features/mark/**` — Mark ;
- les fragments et assemblies de Journey, Access, Day Of, Continuity, Preparation et Questionnaires restent près de leurs owners.

Integrator-owned pendant les trains parallèles :

- `mobile/lib/app/router.dart` ;
- `mobile/lib/app/providers.dart` ;
- `mobile/lib/main.dart` ;
- `mobile/pubspec.yaml` ;
- `mobile/android/**` ;
- `mobile/lib/data/local/**` ;
- `mobile/lib/sync/**` ;
- bootstrap/configuration plateforme ;
- CI centrale.

Une lane feature ne modifie ces hotspots qu’après coordination explicite.

## Routes

Le router top-level possède encore uniquement la création de `GoRouter`, auth, redirects globaux, shell, fallback et composition.

Règles pratiques :

- nouvelle route interne d’une feature → modifier le fragment `features/<owner>/*_routes.dart` ;
- nouvelle racine globale → intégrateur + `app/router.dart` ;
- route auth/globale → intégrateur ;
- deep link cross-feature → contrat navigation + intégrateur.

Les paths existants restent canoniques. La fragmentation n’est pas une occasion de les renommer.

## Runtime et repositories

`AppRuntime` reste une façade compatible, mais sa définition vit dans `app/runtime/app_runtime.dart`. `providers.dart` ne construit plus tous les repositories : il injecte TokenStore, SessionRecovery, runtime config et la factory de capacité location, puis délègue à `runtime_builder.dart`.

Les dépendances propres d’un domaine sont construites dans une petite assembly feature-owned lorsqu’elle réduit les collisions. Il n’existe ni service locator, ni auto-discovery, ni conteneur DI maison.

Règles :

- repository feature → factory/assembly de son owner ;
- capability plateforme → interface/frontière Makolo, jamais plugin direct depuis la feature ;
- runtime config → app/runtime-owned, jamais lue par une feature ;
- service global → fourni par la composition app/runtime.

Le seam `locationCapabilityFactoryProvider` est intentionnel : l’intégrateur peut y réconcilier PAR-1B sans déplacer l’implémentation native dans une feature. PAR-1C conserve son bootstrap/runtime service owner séparé.

## Personal roots

`ProjectionScreen` reste une primitive de présentation partagée ; ce n’est plus la racine que Now, Ongoing et Me doivent tous modifier.

- `NowScreen` consomme `PersonalRepository.watchNow()` ;
- `OngoingScreen` consomme `watchOngoing()` ;
- `MeScreen` consomme `watchMe()`.

Aucun modèle, repository, état persistant ou calcul métier parallèle n’est créé.

Mark reste une racine spéciale hors des quatre branches du shell ; seul son ownership de route est déplacé près de la feature. Son comportement de push/retour reste inchangé.

## Architecture guard

`test/architecture_guard_test.dart` analyse uniquement le Dart de production sous `lib/features/**`. Il interdit les plugins infrastructure/natifs listés dans le test, la lecture directe de runtime config, les URLs HTTP(S) codées en dur, les imports feature → app router/shell et l’accès DB direct depuis les écrans/routes.

Le test ne bloque pas Flutter, Riverpod ou go_router et ne scanne pas les fixtures/tests/docs.

Lorsqu’une capability native est nécessaire, ajouter ou utiliser d’abord sa frontière Makolo sous platform/runtime/repository, puis injecter cette frontière dans la feature.
