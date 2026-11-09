# Makolo — Lot 3 : racine Nous N1 harmonisée avec Moi

**Date :** 2026-11-09  
**PR de travail :** [#522](https://github.com/TraditionLearningCommunity/makolo/pull/522)  
**Portée :** Presentation Flutter et Web, sans migration ni modification des API Django.

## 1. Décision et architecture

Même grammaire de reconnaissance N1 que Moi : identité de l'acteur, Passeport Makolo, index des territoires et choix Liste/Grille. Les données et permissions demeurent propres au Profile ou au Space ; l'identité du viewer reste distincte de l'identité de son Espace.

Le socle du lot 2 (`mobile/lib/design/identity_surface.dart`) est réutilisé, pas recopié. L'API `organizations/api/space_us_projection.py`, les destinations `handoffs`, les routes et les propriétaires métier restent inchangés.

## 2. Flutter

`mobile/lib/features/space/space_us_surface.dart` devient un widget à état de présentation, conservant ses protections de liens par slug, et la racine `space-us-projection`.

Ordre :
1. Nom, description, contexte et représentation collective ;
2. Passeport autorisé, visuellement prioritaire ;
3. `Notre espace` : liste ou grille avec `MakoloTerritoryViewToggle` et `MakoloTerritoryListCard/MakoloTerritoryGridCard` ;
4. Entrées `Ma place dans cet Espace`, `Notre équipe`, `Nos relations`, `Nos ressources`, `Notre gouvernance`, `Notre confiance` lorsque les faits et permissions les rendent visibles ;
5. `Informations et gestion` secondaire : abonnement, connexions, paramètres, pilotage selon handoffs réels.

La visibilité `visible` est exigée explicitement pour les aperçus Team, Relations et Ownership, sur Flutter comme sur Web. Un champ `items` résiduel sous une visibilité `restricted`, `unknown` ou `unavailable` ne doit pas être rendu.

Les aperçus sont limités à trois valeurs réellement projetées. Les totaux sont affichés seulement quand le serveur les fournit explicitement et que la famille est visible. Aucun item personnel n'est copié vers Space.

Les liens N2/N3 sont acceptés uniquement sous la forme exacte `/space/<slug>/us/<depth>` prévue par l'owner, ou les handoffs institutionnels autorisés déjà existants. Les liens forgés cross-Space sont neutralisés. Une collection sans handoff reste informative, pas artificiellement actionnable.

Le choix Liste/Grille est une **préférence d'appareil indexée par slug Space** dans FlutterSecureStorage ; une bascule de Space remet temporairement l'interface en Liste puis relit sa préférence propre. Les données métier restent dans les projections owner, sans stockage de nouveaux faits sensibles.

## 3. Web Django

- `templates/organizations/space/us.html` conserve ses faits, contrôles d'autorité, liens et profondeurs, et présente l'index `Notre espace` avec choix Liste/Grille.
- `static/css/space-us-n1.css` fournit la densité compacte, les états et les dispositions adaptatives, sans modifier les cartes dans les autres verticales.
- `static/js/space-us-layout.js` applique une préférence visuelle `sessionStorage` bornée à l'ID de l'Espace et réinitialise les fragments HTMX. Le composant n'appelle aucune API ni ne calcule de permission.
- `templates/base/app.html` charge cet adaptateur passif globalement pour qu'il reste disponible lors des transitions HTMX, sans dépendre de scripts insérés dans une réponse partielle.

## 4. « Nos démarches » : décision de non-fabrication

L'agrégateur actuellement audité (`objectives/organizer.py`) est explicitement privé et Profile-scoped (`build_organizer_page(profile)`) ; `organizations/api/space_us_projection.py` ne fournit aucun handoff `objectives/organizer` collectif. Par conséquent, **le lot 3 n'affiche pas de fausse carte « Nos démarches »**. Un futur raccourci collectif exige de prouver un owner-backed read model de Projects/Dossiers/Journeys propre à ce Space avec permissions et continuité réelle ; ce sujet reste dans la validation des handoffs métier, pas dans Presentation.

## 5. Tests et invariants

Les tests Flutter `mobile/test/space_us_surface_test.dart` couvrent les tailles Compact/Medium/Wide, les ouvertures réelles N2, le basculement Liste/Grille, la séparation des Spaces, les aperçus, la révocation des ressources/équipe et les liens forgés.

`organizations/test_ws4_space_web.py` vérifie le nouvel index, les contrôles Web, les liens owner, le chargement CSS/JS, les invariants serveur et le `Cache-Control: private, no-store`.

La modification ne change pas la structure du modèle, la résolution de Mandate, ni les URLs/API. Les tests, l'analyse Flutter, les captures appareils et la CI restent **à exécuter sur runner configuré** : aucun statut vert n'est présumé.

## 6. Passage au lot 4

Le lot 4 doit confirmer et fermer les comportements de profondeur et le retour de navigation, la séparation des données local-first par acteur, les mises à jour/revocations au runtime et les éventuelles lacunes d'autorisation. Aucun nouvel owner n'est créé pour contourner un lien absent.
