# Research: Mobile Mature — Moi / Me

## Décisions retenues

### Source runtime
`PersonalRepository.watchMe()` lit `StoredProjection personal.me`. Le selector lane-local consomme directement la shape backend courante; aucun GET direct depuis l'écran.

### Source-state partagé
Le socle possède déjà `mobile/lib/sync/owner_source_state.dart`. Moi réutilise `watchOwnerSourceState(... sourceKey: personal.me)` via `PersonalRepository.watchMeSource()`.

`SyncStatusScope` fournit séparément l'état de lifecycle global, notamment offline et syncing. Moi ne déduit donc ni reachability ni refresh-error depuis l'âge du snapshot.

### Composition
Moi est SECTION-FIRST. Identity structure la surface. Passport, Considerations, Collectives et Resources restent des territoires indépendants. Support n'apparaît que lorsqu'un élément support est réellement disponible.

### Sparse / Empty
Une projection sparse est du contenu valide. Les absences sont locales:
- Passport indisponible;
- rien de déclaré;
- aucun collectif lié;
- aucune ressource disponible.

Aucun score, progress bar ou acquisition marketing n'est ajouté.

### Personality
Les territoires ne sont pas rendus comme quatre cards homogènes:
- Passport: Unit riche;
- Considerations: composition légère;
- Collectives: lignes d'identité;
- Resources: previews compactes;
- Support: lignes seulement lorsqu'il existe.

### Profondeur
La lane utilise une profondeur N2 de présentation sur les previews acquises. La sélection est conservée par `StructuredDestination` et re-résolue sur la sélection courante, afin de ne pas figer un ancien objet lors d'un refresh.

### Freshness/offline
Freshness utilise les métadonnées de `StoredProjection` via `FreshnessPolicy(id: personal.me)` sans TTL inventé. Offline et source failure viennent des mécanismes partagés. Le contenu acquis reste visible pendant refresh et erreurs récupérables.

### Géométrie
Le seuil Moi est évalué sur la largeur disponible à la surface:
- 800: vertical;
- 840: deux territoires possibles;
- 900: deux territoires possibles;
- sparse: la largeur seule n'augmente pas la profondeur cognitive.

`MakoloAdaptiveGrid(maxColumns: 2)` interdit l'effet dashboard.

## Alternatives rejetées
- Réutiliser `ProjectionScreen`: trop générique.
- Créer une table locale par territoire: duplique les vérités propriétaires.
- Créer un second mécanisme source-state dans Moi: le socle `OwnerSourceState` existe déjà.
- Ajouter des routes owner sans capability démontrée: action morte ou autorité inventée.
- Utiliser les scénarios dev comme runtime: fake data.
- Afficher un spinner global à la première disponibilité: détruit la grammaire SECTION-FIRST.
