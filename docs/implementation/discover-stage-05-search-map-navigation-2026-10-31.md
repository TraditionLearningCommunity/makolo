# Makolo — Découvrir : chantier 05, recherche, carte et navigation

**Relevé :** 31 octobre 2026  
**Intégration :** [PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522), branche `fix/discover-a-continuation-context-20261014`  
**Décision :** **implémentation livrée en code**, tests ciblés enregistrés ; tests/CI/deployment différés à la certification du chantier 09 conformément à l'instruction explicite de l'utilisateur. Ne pas qualifier ces tests d'exécutés ou de verts.  
**Frontière :** même source propriétaire Discovery et ses curseurs opaques ; aucune nouvelle table, aucune migration, pas de moteur de pertinence, pas de deuxième vérité cartographique, pas de modification N2/N3.

## 1. Problèmes d'entrée identifiés dans #522

1. `DiscoveryMapScreen` ignorait toute recherche initiale : `static const _query = DiscoveryQuery()`. La route `/discover/map` n'injectait pas les critères de Recherche, et le bouton global Carte ouvrait la route vide.
2. La carte personnelle utilisait bien `watchItems`, mais `MakoloSpatialFrame` présentait **seulement la liste** sous `mapMinWidth`. Une destination Carte sur téléphone ne montrait donc pas de carte.
3. Le plan MapLibre initial ne figurait pas les coordonnées owner en repères sélectionnables ; choisir un item recentrait le composant en le recréant et perdait le réglage de caméra.
4. La Recherche utilisait un curseur pour « Suivant », sans conserver les curseurs déjà vus pour « Précédent ». Un écran ouvert via deep link ne savait pas retrouver une page antérieure sans inventer le token.
5. Le marqueur `discovery.presentation-position` ne mémorisait que page/token et n'enregistrait ni scroll ni candidat sélectionné.
6. La carte publique invitée et son retour utilisaient des paramètres manuels ou un retour `/discover` sans filtres, entraînant une possible perte du contexte après navigation autonome.
7. Les signaux de panne/continuation de la carte n'étaient pas associés à la source Discovery ; l'absence de snapshot pouvait être interprétée comme une absence de candidats.

## 2. Implémentation retenue

### A. Une requête canonique et portable

`DiscoveryQuery.fromRouteParameters()` reconstruit les paramètres existants : `q`, `place`, `when`, `period`, `vertical`, `price`, `date`, `date_from`, `date_to`, `lat`, `lon`, `radius_km`, `page`, `page_size` et le `continuation` opaque. `routeLocation(screen, selectedCandidateKey: ...)` les sérialise pour la navigation, en séparant `selected` (état UI) des arguments serveur.

La route rejette les coordonnées invalides, les filtres spatiaux partiels et une page avancée sans token au lieu de supprimer silencieusement la géographie ou d'inventer une continuation. Les route builders rendent une erreur de critères explicite. `DiscoveryRepository` conserve aussi `activeExploration` pour que les boutons Search/Map de la barre globale pointent sur les critères du Profile en cours, pas sur une nouvelle recherche vide.

`discovery_routes.dart` transmet `query`, `initialSelectedCandidateKey` et les handlers d'ouverture d'identité canonique. Les routes Search/Map sont transmises au mécanisme existant de reprise `runtime.recovery.rememberLocation`.

### B. Liste et carte = une même projection de candidats

La carte personnelle continue à consommer **`watchItems(_query)` et `DiscoverySelector.spatialAnchorsFromCollection`**, jamais un deuxième corpus ou `watchMap`. Les possibilités sans coordonnées restent dans la liste, sans pin inventé.

`DiscoverySpatialView` offre `showMapOnCompact` pour la route dédiée : vraie carte de hauteur bornée sur mobile et champ défilant utilisable dessous ; `MakoloSpatialFrame` est explicitement autorisé sur largeur compacte, sans remplacer la carte par son propre fallback de liste. En cas de désactivation ou erreur MapLibre, le texte d'indisponibilité s'affiche et la liste reste consultable.

Les coordonnées owner admises produisent des repères `CircleOptions` de MapLibre ; les cercles sont sélectionnables et associés à leur `candidateKey`. L'absence de coordonnées ne produit aucune annotation. La sélection du champ et la sélection cartographique se répondent ; le contrôleur anime le centre sans réinitialiser systématiquement la carte sur la route dédiée. Après ajout d'un lot serveur, les annotations sont recalculées à partir du **même** champ, sans classement de client.

### C. Recherche et navigation signée

`DiscoverySearchScreen` réhydrate ses champs depuis `initialQuery` et peut être ouverte directement depuis les critères visibles sur Carte. Chaque changement de critères repart à la première page et invalide les tokens précédents ; `_pageTokens` ne retient que les jetons réellement émis par le serveur.

« Suivant » prend `collection.continuationToken`. « Précédent » réutilise uniquement un token déjà rencontré ; si la page antérieure inconnue ne peut pas être demandée sûrement, le client revient à la première page **avec les mêmes filtres**. Le refus `continuation_rejected` repart de la première page sans effacer la recherche. Les chemins root et Search restent distincts : root utilise la concaténation bornée existante, Search les pages signées.

`DiscoveryMapScreen` gère également « Précédent/Suivant » sans les inverser, conserve l'état de sélection, et revalide les erreurs de source. En cas de refus du jeton, la première page du **même** champ est rechargée ; aucune « page supplémentaire » n'est simulée.

### D. Reprise et retour

Le marqueur local de la **racine** `discovery.presentation-position` contient maintenant `scroll_offset` et `selected_candidate_key` en plus de `page/continuation`. Ces hints sont validés et stockés via `ProfileStore`, déjà isolé par Profile. Le contrôleur de scroll revient à l'offset conservé après chargement d'une collection, borné à l'étendue réellement rendue. Le scroll de la liste continue reste lié à `mapFingerprint` et ne change pas d'identité lors de l'append d'une nouvelle page.

`DiscoveryExplorationView` accepte un focus initial et notifie les changements d'élément sélectionné. Les écrans de recherche/carte liés par `GoRouter.push` restent montés sous le détail ; lorsqu'un écran est reconstruit via URL, les paramètres et la sélection sont réinjectés plutôt qu'inférés depuis le contenu.

La recherche publique invitée lit les mêmes critères d'URL et maintient le texte, le lieu, la date, les bornes de dates, la période, le type, le prix, les coordonnées/rayon owner-backed et la taille de page ; son retour autonome de Carte vers Découvrir transporte les paramètres et le curseur plutôt que de faire `go('/discover')`. La carte invitée réutilise **la page, la taille de page et le cursor du champ invité**, sans augmenter silencieusement la pagination à 50 ; l'absence totale de critères URL conserve le défaut d'affichage public antérieur de 12 éléments. Modifier le lieu nommé efface les anciennes coordonnées du lien plutôt que de les combiner arbitrairement. Une URL spatiale invalide est refusée explicitement pour les deux parcours.

## 3. Fichiers modifiés

| Couche | Sources |
| --- | --- |
| Navigation + état | `mobile/lib/features/discovery/discovery_repository.dart`, `discovery_routes.dart`, `discovery_screens.dart`, `mobile/lib/app/app_shell.dart` |
| Presentation cartographique | `mobile/lib/features/discovery/discovery_mature_view.dart`, réutilisation de `mobile/lib/platform/maps/makolo_map_view.dart` |
| Parcours public invité | `mobile/lib/app/router.dart`, `mobile/lib/features/guest/guest_screen.dart`, `mobile/lib/features/guest/public_discovery_map_screen.dart` |
| Contrats de non-régression | `mobile/test/dg_discovery_geography_test.dart`, `mobile/test/discovery_offline_position_test.dart`, `mobile/test/discovery_mature_screen_test.dart`, `mobile/test/discovery_shell_contract_test.dart` |

## 4. Tests écrits

- Aller-retour `DiscoveryQuery → /discover/map → /discover/search` : filtres, dates, coordonnées, rayon, page, taille et continuation opaque sont conservés, avec `selected` en état UI hors API.
- Entrées malformées : coordonnées invalides/incomplètes, rayon invalide, page avancée sans token → erreur de contrat et pas d'élargissement silencieux.
- Origine root : persistance des hints scroll et focus, rejet d'un offset invalide ou d'un mauvais type de projection.
- UI compacte : présence d'une **zone cartographique**, fallback MapLibre explicite, liste toujours accessible, sélection d'un autre candidat.
- UI large : le champ transmet sa sélection au lien Carte.
- Invariants d'intégration : même `watchItems`, géolocalisation depuis `spatialAnchorsFromCollection`, navigation globale et publique depuis les critères disponibles.

**Important :** les tests ont été ajoutés, pas exécutés. Les repères MapLibre interactifs doivent être éprouvés sur Android/Web lors du chantier 09, tout comme la navigation, les erreurs réseau et la caméra réelle.

## 5. Limites honnêtement conservées

- Un curseur signé de page précédente **inconnu** n'est jamais recréé. Retour garanti à page 1 du même champ, pas retour artificiel à une page 2 sans token.
- La reprise locale du scroll et focus de la racine est bornée à ce qui existe encore dans le snapshot. Si les données ont changé ou ont été révoquées, la sélection périmée ne devient pas une vérité d'Activity.
- La carte ne montre que les coordonnées publiées et autorisées. Elle n'essaie pas de géocoder les titres ni de tracer une route de transport approximative.
- La couche MapLibre dépend de la configuration/style déjà fournis par le runtime ; aucune clé fictive, fournisseur de tuiles ou téléversement de fichiers n'est ajouté.
- Aucun effet d'engagement, Save ou Watch n'est créé par le passage Carte/Liste : les transitions restent chez leurs propriétaires.

## 6. Sortie de livraison du chantier 05

- [x] Liste/Recherche/Carte utilisent le même contexte filtré et identité de candidat.
- [x] Navigation directe et retour avec query, sélection et pages signées sans inférence de token.
- [x] Carte visible sur mobile, liste toujours utilisable si les tuiles échouent.
- [x] Repères owner-backed sélectionnables et recentrage sans réinitialisation volontaire de caméra dans la route Carte.
- [x] Scroll root, focus et état de page conservés par le ProfileStore et le contexte GoRouter.
- [x] Public invité : URL et retour gardent les critères, les entrées malformées sont visibles comme erreurs.
- [x] Distinction source indisponible / résultat absent et refus de continuation dans Map.
- [x] Tests ciblés et contrat de sortie enregistrés.
- [ ] Exécution des tests, Android, Web, CI et tests carte réelle : différés au chantier 09, sans aucune attestation de succès.

**Décision : chantier 05 — implémentation livrée en code, validation exécutée différée. Prochain chantier : 06 exclusivement.**
