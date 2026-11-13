# Moi → Mes collectifs — maquette retenue et contrat d'implémentation

**Chantier :** PR #522, branche fix/discover-a-continuation-context-20261014  
**Référence :** maquette choisie le 13 novembre 2026.  
**État :** implémentation Flutter dans cette branche ; formatage SDK, CI et recette Android à confirmer.  
**Périmètre :** Moi → Mes collectifs N2, sans changement du backend propriétaire.

## Intention de la page

Permettre au Profile de reconnaître ses relations collectives et d'avancer : quels Spaces sont autorisés, quelles Teams relèvent de sa collaboration, quels Groups sont visibles, et où ouvrir le contexte adéquat. Le contrat COLLECTIVES reste le wire existant de personal.me, composé de authorized_spaces, teams, groups.

Ni TeamMembership ni GroupMembership n'accordent une Permission, un Mandate, un Assignment, ou une capacité générale de gestion. Flutter ne déduit aucune autorité d'un intitulé ni d'une appartenance.

## Composition visuelle retenue

1. Conserver l'en-tête et la navigation de Makolo ; ne pas redessiner le Mark.
2. Afficher une phrase de contexte et un bandeau violet avec total fiable et compteurs par nature. **Ne jamais montrer de compteur zéro.**
3. Offrir les filtres Tous, Espaces, Équipes, Groupes, une recherche locale et un tri local par nom (Nom A à Z) ou ordre propriétaire déjà reçu. **Pas de faux tri Plus récents**, aucune date fiable n'étant projetée.
4. En Tous, rendre des sections distinctes Espaces où je peux agir (cartes horizontales adaptées aux petits écrans), Mes équipes et Mes groupes (lignes contextuelles).
5. Chaque entrée affiche nom, type implicite par section, relation effectivement établie et contexte parent déjà visible. Pas de nombre de responsabilités fictif, de statut de membre déduit pour Group, ni de logo Space inventé.
6. Tout voir applique le filtre de la section ; aucun écran de doublon n'est créé.
7. Le menu contextuel propose seulement Aperçu, action locale existante. Les autres commandes attendront de vraies capabilities propriétaires.

## Actions réellement branchées

- **Space autorisé :** Agir ouvre le sélecteur d'acteur Makolo existant. Il ne bascule pas silencieusement vers une autre identité : le sélecteur n'affiche que le Space ciblé parmi les contextes réellement présents dans l'inventaire, revalide le contexte acquis et demande une sélection explicite. Si cette action n'est pas disponible, Ouvrir donne accès à la fiche Space existante, lorsque son slug est disponible.
- **Team :** aucune route native Team N3 autorisée n'existe sur cette page. Lorsque le Space parent possède un identifiant et un slug reçus du serveur, Voir l'Espace ouvre sa fiche ; sinon, Aperçu restitue les faits locaux. Cette action ne prétend pas ouvrir l'annuaire de l'équipe.
- **Group :** Ouvrir utilise le détail natif /groups/:id existant, validé à nouveau par le propriétaire Groups. Aucune mutation d'adhésion ou de gestion n'est inventée.
- Toutes les actions de gestion, invitation, sortie, ownership, responsabilité et composition d'équipe restent réservées aux profondeurs et owners déjà autorisés, jusqu'à vérification de leurs capacités explicites.

## Local-first, données et confidentialité

- personal.me et MeSelector restent les sources reçues puis conservées par PersonalRepository et ProfileStore sous le Profile courant.
- Les comptes viennent des familles count (ou de la longueur d'une famille complète). Ne pas remplacer un compteur inconnu par la taille d'une page partielle.
- La recherche et le tri portent sur les données déjà acquises. Si la pagination n'est pas épuisée, la portée de la recherche est explicitée et la suite est chargée par la continuité loadMoreMe existante.
- Au retour hors connexion, garder les relations déjà conservées ; une ancienne autorisation ne peut pas être annoncée comme un droit d'action actuel. Agir est retiré hors ligne au profit d'une simple ouverture admissible.
- La révocation de la source personal.me préexistante prime sur la présentation ; aucune donnée privée interdite n'est conservée dans une nouvelle table.
- Une famille vide connue n'implique pas de compter zéro dans le bandeau. Une famille incomplète n'est pas présentée comme entièrement explorée.
- Conserver le scroll et l'état de filtre/recherche dans la session du Profile ; le contenu est recréé au changement de Profile.

## Code touché

- mobile/lib/features/me/me_collectives_content.dart : composition et interactions visuelles opt-in, sans nouveau propriétaire.
- mobile/lib/features/me/me_collectives_screen.dart : intégration à la profondeur local-first, conservation de la pagination et du refus.
- mobile/lib/features/me/me_routes.dart : réemploi du picker d'acteur Makolo ciblé pour l'action Agir.
- mobile/lib/navigation/actor_selector.dart : filtre opt-in sur l'identifiant du Space demandé ; le sélecteur général reste inchangé.
- mobile/test/me_collectives_content_test.dart : tests de regroupement, absence de zéro, filtres, recherche partielle, Team≠autorité, offline et navigation Group.

## Tests et recette avant merge

1. cd mobile && bash tool/dart_format.sh write && bash tool/dart_format.sh check, avec Flutter/Dart canoniques 3.47.3/3.13.3 ; à défaut, workflow manuel Mobile Format sur la branche de #522.
2. flutter analyze et flutter test test/me_collectives_content_test.dart test/me_mature_test.dart.
3. Vérifier les autres tests mobiles dépendants de la navigation et du picker d'acteur.
4. Vérifier sur émulateur et Samsung : formats compacts, scale de texte, swipe horizontal des Spaces, filtre/recherche, scroll/reprise, changement de Profile, données absentes, synchronisation tardive, source révoquée et mise hors ligne.
5. Dans le picker, vérifier que Agir n'accorde jamais un contexte non acquis ou révoqué.
6. Vérifier la CI de #522 et éviter tout merge si une gate obligatoire reste rouge.

**Limite connue :** Agir passe par le picker existant, filtré sur le Space de la carte, mais exige toujours une confirmation humaine et la revalidation du contexte acquis. Aucun passage automatique et aucune autorité supplémentaire ne sont créés. Une vraie profondeur Team nécessitera de prouver une destination et sa permission ; la fiche du Space parent ne s'y substitue pas.
