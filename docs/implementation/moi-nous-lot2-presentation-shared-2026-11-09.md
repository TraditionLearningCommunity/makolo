# Moi / Nous — Lot 2 : primitives de présentation partagées

**Branche de référence :** PR #522, sans modification de `main`.

## Portée
Les règles d'implémentation concernent uniquement l'UX : même grammaire d'identité, de Passeport, de raccourci majeur et d'index des territoires. Les acteurs Profile et Space, leurs projections, accès et destinations restent distincts.

## Flutter
- `mobile/lib/design/identity_surface.dart` : `MakoloIdentityPortrait`, `MakoloPassportGateway`, `MakoloPrimaryShortcut`, `MakoloTerritoryViewToggle`, `MakoloTerritoryListCard`, `MakoloTerritoryGridCard`.
- `me_screen.dart` et `space_us_surface.dart` utilisent le portrait et le Passeport partagés, sans transférer les données ni les permissions.
- `me_hub.dart` utilise le raccourci, la bascule liste/grille et les cartes partagés en gardant les sources Profile, les clés et la mémoire locale Profile. Les aperçus restent bornés à trois éléments et les actions fermées restent inactives.
- L'adoption du même index compact et des raccourcis métier par `Nous` appartient au **lot 3** : pas de faux `Nos démarches` ni de permission déduite d'une carte.

## Django Web
- `templates/partials/identity_passport_gateway.html` fournit le même contenu/action Passport aux deux pages, avec des liens produits par leurs propriétaires.
- `templates/partials/identity_primary_shortcut.html` remplace le markup Moi, sans changer sa destination. Nous ne possède pas encore de route analogue contractée.
- `static/css/makolo-identity-surface.css` est une couche commune opt-in de représentation ; les styles de disposition Moi/Space restent spécialisés.
- Les vues Django, routes, API, modèles et permissions sont inchangés.

## Vérification
- Widget tests des primitives et de l'absence d'action non autorisée : `mobile/test/identity_surface_test.dart`.
- Contrats existants : `mobile/test/me_mature_test.dart`, `mobile/test/space_us_surface_test.dart`, `core/test_me_n1_web.py`, `organizations/test_ws4_space_web.py`.
- Contrôler `dart format`, `flutter analyze`, tests Flutter/Django et QA Compact/Medium/Wide sur un runtime configuré avant de revendiquer une certification.
- Les checks CI de la PR ne sont pas le blocage de cette phase, mais aucun merge avec gates rouges.

## Interdits
Pas de `MeResponse = UsResponse`, de modèle générique ActorCapital, d'API unifiée, de mutation locale hors ligne, de permission calculée par la présentation ou de réutilisation implicite d'objets personnels dans Space.
