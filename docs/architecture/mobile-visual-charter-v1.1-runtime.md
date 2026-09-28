# Mobile visual charter V1.1 — runtime implementation note

> Branche : `mobile/a2-visual-charter-v1-1`
>
> Base de création : `mobile/a1-installed-makolo-core@fcf77a3a329a89d190c302adf907be1bc89b333f`
>
> Statut : stacked on A1, ne pas merger avant réconciliation A1/A2.

## Objet

Ce chantier réduit le delta entre la charte visuelle mobile V1.1 et le runtime Flutter A1. Il ne redéfinit ni A1, ni les surfaces métier A2, ni Splash / Brand Moment / Onboarding.

La charte canonique installée dans le dépôt est :

- `docs/architecture/mobile-visual-charter-v1.1.md`.

## Collision audit

La branche `mobile/a2-launch-onboarding@6a60fef1965cb7a52c20df5b910a1005c7211802` est divergée de l'A1 courant, avec merge-base `2cc0d88aa917f91add69da03785a73fc2dab5aed`.

Fichiers communs sensibles :

- `mobile/lib/app/makolo_app.dart` ;
- `mobile/lib/app/app_shell.dart` ;
- `mobile/lib/app/router.dart` ;
- `mobile/lib/app/providers.dart` ;
- `mobile/lib/features/splash/**` ;
- `mobile/android/app/src/main/res/**`.

Décisions de ce chantier :

- aucun changement de `router.dart`, providers, auth, guest, onboarding ou splash natif ;
- `makolo_app.dart` est modifié uniquement pour brancher light/dark et la politique de zones système ;
- `app_shell.dart` est modifié dans un commit isolé uniquement pour la navigation adaptative ;
- aucune résolution arbitraire avec launch/onboarding n'est tentée.

## Design system livré

### Couleurs et surfaces

Le runtime n'utilise plus `ColorScheme.fromSeed` comme source principale de l'identité.

Deux schemes explicites sont fournis :

- `buildMakoloLightTheme()` ;
- `buildMakoloDarkTheme()`.

`MakoloSurfaces` centralise les surfaces dépendantes du thème, y compris :

- canvas ;
- low ;
- surface ;
- raised ;
- brand ;
- border ;
- couleurs sémantiques nécessaires aux primitives.

La hiérarchie dark reste bornée à Ink + trois niveaux de surface.

### Tokens

Spacing :

`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64`.

Radii :

- control 12 ;
- card 16 ;
- large 24 ;
- sheet 28 ;
- pill réservé aux chips/statuts appropriés.

Motion :

- 120 ms ;
- 160 ms ;
- 240 ms ;
- 320 ms.

`MakoloMotion.effective` conserve Reduce Motion.

### Typographie

L'échelle V1.1 est installée dans `TextTheme`.

Aucun fichier Manrope/Inter n'existe dans l'arbre A1 vérifié. Le runtime utilise donc volontairement le fallback sans-serif plateforme et ne déclare pas un `fontFamily` inexistant.

**FONT ASSET BLOCKER** : fournir ultérieurement les fichiers locaux officiels/licenciés nécessaires pour Manrope et Inter, puis déclarer uniquement les poids réellement utilisés.

### Components

Le thème partagé couvre notamment :

- FilledButton ;
- OutlinedButton ;
- TextButton ;
- IconButton ;
- InputDecoration ;
- Card ;
- Chip ;
- navigation ;
- BottomSheet ;
- Dialog ;
- SnackBar ;
- Divider.

Les primitives Behavior existantes restent propriétaires de leur comportement ; elles consomment désormais davantage les surfaces du thème.

## Edge-to-edge

Le côté Flutter utilise `SystemUiMode.edgeToEdge` et une politique centralisée de barres système transparentes avec contraste d'icônes light/dark.

Les ressources splash Android ne sont pas réécrites ici afin d'éviter la collision avec `mobile/a2-launch-onboarding`.

## Navigation adaptative

La sémantique reste quatre destinations + Makolo Mark.

- espace compact : barre basse ;
- espace réellement large : rail ;
- la décision utilise la taille disponible, pas une catégorie d'appareil.

Le routeur, les branches persistantes et le contrat back ne sont pas réécrits.

## Mark

`MakoloMark` accepte maintenant trois rôles sémantiques :

- informative ;
- structural ;
- decorative.

Le mode décoratif retire le Mark de l'arbre Semantics sans modifier la géométrie SVG. Les appels existants restent compatibles.

## Visual regression

Le harness initial couvre volontairement peu de références :

- système visuel light ;
- système visuel dark ;
- all-clear avec text scaling élevé.

Les fixtures sont déterministes et sans donnée personnelle réelle.

## Launch/onboarding compatibility

Audit rapide de `mobile/a2-launch-onboarding` :

- Brand Moment consomme déjà `MakoloMotion` et `MakoloMark` ;
- Onboarding consomme les tokens, chips et buttons partagés ;
- guest mode reste dans sa branche propriétaire ;
- Splash natif, Brand Moment et Onboarding restent distincts ;
- aucune librairie d'animation lourde n'est ajoutée par ce chantier.

La réconciliation devra conserver son `LaunchGate` tout en reprenant le branchement light/dark et system UI de cette branche.

## Backend / migrations

Aucun modèle Django, aucune migration Django/Drift, aucune API, Permission, Mandate, Access, Readiness ou autre vérité métier n'est ajouté ou modifié.
