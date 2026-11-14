# Moi → Mes collectifs — composition native et actions réelles

**PR :** #522, branche `fix/discover-a-continuation-context-20261014`  
**Mise à jour :** 14 novembre 2026  
**Statut :** code poussé ; CI et recette Android à contrôler sur le HEAD final.  
**Référence :** maquette du 13 novembre et retour d'essai réel sur émulateur du 14 novembre.

## Décision UX appliquée

La capture d'essai a montré une hiérarchie trop lourde. La nouvelle version retire complètement le bandeau violet, les compteurs de doublon, les sous-titres pédagogiques permanents, les boutons Web redondants et les menus `···` dont la seule action était « Aperçu ».

**Navigation :** `/me/collectives` est désormais une route secondaire plein écran, extérieure au shell de navigation primaire, sans header de compte ni barre Now/Découvrir/Mark/En cours/Moi répétés. L'AppBar native contient retour à Moi, « Mes collectifs », nombre total **strictement positif et fiable**, icône de recherche ouvrant un champ et icône de tri. Android Back reste naturel ; un lien direct sans historique revient à Moi.

**Filtres :** Tous (sans décompte redondant), Espaces, Équipes, Groupes, ces trois catégories avec leur compteur positif lorsqu'il est connu. Le total est la somme des trois familles reçues, comptant des relations et non des institutions distinctes. Pas de « 0 » affiché dans les filtres. Recherche et tri locaux sur les données déjà synchronisées, sans tri de date fictif. La position dans la liste est préservée tant que le Profile et la route restent actifs.

**Contenu :** lignes natives, accessibles, plus compactes, à grande cible tactile, visuel aligné à gauche, nom principal et contexte autorisé. Les sections sont groupées en Tous ; un filtre actif n'a pas besoin de répéter son titre. Pas de doublon « Tout voir ».

## Interaction / propriété

| Nature | Interaction | Contrat |
| --- | --- | --- |
| Space autorisé | Appui sur la ligne → fiche Space existante ; « Agir » en ligne lorsque disponible | Le picker d'acteur existant ne propose que le Space ciblé et revalide le contexte acquis. Une sélection confirmée ouvre son Now. |
| Team | Appui sur la ligne → fiche du Space parent lorsque le slug est fourni | TeamMembership est collaboration, jamais Mandate. Pas de faux « Gérer » ou de faux N3 Team. |
| Group | Appui sur la ligne → profondeur Groups native autorisée | Visibilité et permission sont revérifiées dans Groups ; aucune mutation n'est ajoutée. |
| Actions secondaires | Aucun menu contextuel ornemental | N'en afficher un que si une véritable commande propriétaire existe ultérieurement. |

L'absence de réseau ne supprime pas les noms connus mais retire le CTA « Agir » sans afficher de bannière permanente. Révocation explicite et changement de Profile restent gérés par les sources natives existantes.

## Médias : vérité disponible, pas de faux logo

Le modèle canonique `Organization` présent dans le runtime n'a **pas de champ logo/avatar/photo Space**. Le sélecteur de `PresentationMediaUse` relie ses médias publiés aux **Activities/Occurrences**, pas à l'identité durable d'un Space. Ni une image d'Activity, ni l'avatar personnel d'un membre ne peuvent devenir un « logo Space » par inférence.

La présentation native accueille un `media_bindings` de reconnaissance **explicitement lié à l'objet affiché**, si le propriétaire l'expose : cible `kind/id` exacts, usage `RECOGNIZE`, ressource `presentation_media_use`, MIME image JPEG/PNG et chemin de même origine. Le rendu emploie `RetainedRecognitionImage` et son transport sécurisé ; aucune URL arbitraire ni image publique détachée de son owner n'est admise. Lorsque la projection actuelle ne fournit pas ce média, on montre un **monogramme textuel neutre**, sans créer de logo fictif.

**Écart de domaine restant :** pour qu'une vraie photo/logo durable d'Espace apparaisse, définir et livrer chez son owner un média d'identité Space publié, autorisé et projeté ; le chemin Activity ne peut pas y suppléer. Ce chantier de propriété média ne doit pas être improvisé dans les widgets Moi.

## Fichiers concernés

- `mobile/lib/features/me/me_collectives_content.dart` : sections compactes, filtres, vues et actions.
- `mobile/lib/features/me/me_collectives_screen.dart` : AppBar, recherche, tri, états de lecture et pagination.
- `mobile/lib/features/me/me_routes.dart` et `mobile/lib/app/router.dart` : route plein écran et handoffs existants.
- `mobile/test/me_collectives_content_test.dart` : filtres, compteur, permissions, offline, Group, média explicitement publié.
- `mobile/test/me_mature_test.dart` : entête N2 et recherche réelle dans le corpus local.
- `mobile/lib/features/me/me_hub.dart` : conserve la non-présentation d'un compteur zéro au point d'entrée Moi.

## Contrôles de livraison

- Formatter canonique : `cd mobile && bash tool/dart_format.sh write && bash tool/dart_format.sh check` (Flutter 3.47.3 / Dart 3.13.3).
- `flutter analyze`, `flutter test test/me_collectives_content_test.dart test/me_mature_test.dart`, puis Mobile CI et régression visuelle.
- Recette émulateur + Samsung : pile de navigation, Back, retour Moi, clavier/recherche, tri, catégories à zéro, gros texte Android, listes longues, Team sans autorité, Group privé, Space révoqué, local disponible hors réseau, médias owner-backed.
- Pas de merge #522 avec une gate rouge. Aucun runtime Web ou Django modifié par cette adaptation.

La nouvelle interface doit rester une surface qui aide à avancer : reconnaissance, sélection et handoff réel — pas un tableau de bord ni un annuaire de gestion.
