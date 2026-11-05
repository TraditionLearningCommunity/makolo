# Découvrir — Carte N1/N2 : finition fonctionnelle et visuelle
**Date :** 2026-11-05  
**Branche :** `fix/discover-a-continuation-context-20261014` — [PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522)  
**État :** code poussé ; vérification Flutter/Android ciblée encore nécessaire. Pas de fusion.

## Problème utilisateur

Carte n'est pas un réseau d'opportunités séparé : c'est la représentation géographique du même champ Découvrir. Le parcours `carte → lieu → opportunité → N2 → retour` doit conserver son contexte, et ses trois interactions de bas de fiche doivent rester celles de Découvrir N1. La qualité éditoriale des titres et médias de démonstration n'est pas un critère de fermeture ; le comportement, l'autorité, la lisibilité et la composition le sont.

## Changements

1. **Actions communes :** Carte affiche les trois emplacements N1 (icône `DiscoveryOrbitIcon` Enregistrer, ouverture N2, `DiscoveryShareControl`). Save appelle `_saveDiscoveryPossibility`, le même flux propriétaire que le N1 de Découvrir, plutôt que de conserver sa propre procédure courte. Les boutons Save/Sharing sont présents mais **désactivés** tant que le détail owner et la source n'ont pas été vérifiés. Une position seule ne crée jamais l'autorité.
2. **Sharing :** Carte passe `showAsSheet=true` au composant Sharing commun ; les mêmes actions internes, externes, lien et QR sont affichées dans une feuille native sans recouvrir la petite fiche. Le partage interne bénéficie maintenant du garde d'erreurs `_action` utilisé par les autres options.
3. **Reconnaissance légère :** l'index compact transmet le nom public de l'opérateur et la représentation déjà publiée (type, eyebrow, image de reconnaissance) ainsi que le temps explicite de l'Occurrence. Les faits N2, permissions, commerce et Resources ne sont pas ajoutés. Flutter les utilise dans les lignes au même lieu et dans la fiche brève sans télécharger tous les détails. Si le média manque, une icône issue de la verticale publiée remplace un pictogramme identique universel.
4. **Liste au même lieu :** deux cartes de choix initialement visibles, expansion vers la liste complète par défilement ; image/icone, titre jusqu'à trois lignes, type/porteur et heure seulement s'ils sont connus. Sélectionne l'identité canonique et restaure la même carte.
5. **Carte et localisation :** bouton « Me localiser » flottant au coin inférieur droit, ancré juste au-dessus de la fiche lorsqu'elle existe, avec marge système. Le point de localisation de l'appareil reste une donnée locale et non une opportunité Discovery.
6. **MapLibre :** une source GeoJSON issue des **seuls lieux publics admis** applique le clustering natif par proximité au faible zoom (compteur de lieux et expansion au toucher). À zoom élevé, chaque coordonnée publiée retrouve son point ; une coordonnée commune à plusieurs opportunités continue d'ouvrir le sélecteur du lieu, sans les fusionner. L'ancienne annotation `CircleOptions` reste un repli si les couches natives échouent. Les mises à jour asynchrones de source sont sérialisées pour éviter qu'une réponse périmée remplace le nouveau champ.

## Frontières et invariants

- Un même `spatial_index` compact vient de la projection Discovery : pas de recherche/map cache indépendant ni de classement Flutter.
- Pas de nouvelle table, migration, dossier ou état métier.
- Aucune autorité déduite du zoom, d'un lieu ou d'un média. Pas de fuite de données privées ou de permissions à travers l'index compact.
- Le regroupement des points proches est **cartographique** ; il ne prouve pas que les activités appartiennent au même lieu canonique. Le groupe d'une coordonnée ne transfère aucune permission.
- Les compteurs des clusters natifs portent sur les **emplacements uniques**, tandis que la liste ouverte à une coordonnée donne le nombre d'**opportunités distinctes**. Il ne faut pas confondre ces unités.
- N3, propriétaires métier, Journey, Access, Payment et flux de Découvrir hors Carte restent inchangés.

## Scénarios à valider sans grand audit

- 23 ou 27 opportunités à une coordonnée : deux aperçus, expansion, sélection du dixième, retour N2 sans perte de caméra.
- Une position seule : trois commandes visuellement stables, Save et Sharing inactifs jusqu'à confirmation owner. Après confirmation, Orbit Save et Sharing sont identiques au flux N1.
- Partager depuis Carte : feuille des quatre actions, copie via `POST /api/v1/sharing/possibilities/<family>/<id>/` pour un Profil autorisé, erreur gérée sans exception non attrapée.
- Marqueurs proches à faible zoom : clusters, compteur des lieux et zoom au toucher ; lieux distincts au fort zoom ; plusieurs opportunités au même point restent ouvrables.
- « Me localiser » : en bas à droite, au-dessus d'une fiche ouverte, sans déplacer le contexte de recherche ni créer un nouvel objet Discovery.
- Aucune image démonstrative inventée : miniature publique si connue, avatar déjà divulgué si disponible, pictogramme métier sinon.

**Tests ciblés de code ajoutés ou adaptés :**

```powershell
cd mobile
dart format lib/features/discovery/discovery_mature_view.dart lib/features/discovery/discovery_screens.dart lib/features/discovery/discovery_share_sheet.dart lib/platform/maps/discovery_map_controller.dart lib/platform/maps/makolo_map_view.dart test/discovery_mature_screen_test.dart test/discovery_compact_spatial_test.dart test/discovery_map_clusters_test.dart
flutter test test/discovery_mature_screen_test.dart test/discovery_compact_spatial_test.dart test/discovery_map_clusters_test.dart test/discovery_stage07_actions_test.dart
cd ..
python manage.py test discovery.api.test_mature_discovery.MatureDiscoveryAPITests.test_compact_spatial_keeps_every_location_and_requests_details_on_demand --keepdb
```

Exécution Android réelle du clustering MapLibre et du partage interne non attestée par une exécution dans cet échange. Vérifier et corriger les éventuels écarts ciblés, sans détour par un audit CI global.
