# Mobile — diagnostic des skeletons persistants

## Contrat de travail

- Objectif : rétablir les transitions chargement → contenu / vide / erreur sur Now, Découvrir et En cours, en conservant la lecture locale et l'autorité serveur.
- Owner : Codex, exécution locale unique ; aucune délégation concurrente.
- Base locale : `9888c9fc4fb34a52cf4e45f658e24800a5ab9c7f`, branche initiale `feature/mobile-local-experience`.
- `origin/main` rafraîchi : `26db3db3`, ancêtre direct de la base locale ; PR #518 intégrée. Recherche des PR ouvertes : aucune renvoyée par le connecteur.
- Branche de correction : `codex/mobile-skeleton-root-cause`.
- Surfaces : cycle de vie du runtime Flutter, états de présentation et lectures personnelles/locales des trois écrans ; tests associés.
- Interdit : nouveaux faits métier, seed, migrations, modifications des contrats API, contournement de SQLite, permissions ou authentification.
- Acceptation : projections reçues visibles ou vide confirmé ; acquisition échouée récupérable ; données locales conservées en cas de panne ; aucune résurrection d'un snapshot retiré.
- Gate d'intégration ultérieur : revue du diff et CI verte sur une PR réconciliée avec main. À la demande de l'utilisateur, aucun commit, push, PR ou merge effectué ici.

## Diagnostic causal

Le défaut confirmé concerne la durée de vie du runtime de session. `appRuntimeProvider` ferme l'ancien `AppRuntime` lors de son invalidation : client API, contrôleurs et base Drift sont disposés. `MakoloApp` utilisait cependant `AsyncValue.when` avec son comportement par défaut `skipLoadingOnRefresh: true`. La valeur précédente pouvait donc encore reconstruire le router et les lecteurs après fermeture du store.

Une erreur `ActorContextController was used after being disposed` a été capturée sur le Samsung. Le test `runtime_replacement_test.dart` reproduit la réutilisation : avant correction, `NowScreen` reste monté pendant le remplacement du runtime fermé ; après correction, il est démonté et le runtime suivant peut ouvrir son propre store. Les trois surfaces lisent ce même runtime local, ce qui explique leur défaillance commune possible.

Limite de la reproduction initiale : l'utilisateur a arrêté puis relancé l'application pendant le diagnostic et a constaté le retour du contenu. L'état exact des trois skeletons avant ce relancement n'a donc pas été conservé pour une inspection complète. Le défaut de cycle de vie est confirmé indépendamment par le log et le test ; le relancement réouvrant les données est cohérent avec ce mécanisme.

Les skeletons eux-mêmes ne représentaient pas uniquement du réseau. Now et En cours attendaient aussi les premiers événements Drift ; Découvrir pouvait conserver une disponibilité `initial` alors qu'une acquisition avait échoué. Les branches d'erreur n'étaient pas toutes rendues avant le chargement.

## Chaîne vérifiée et données réelles

La chaîne reste : owner Django → enveloppe JSON → `MakoloApiClient` → parseur `SyncSourceDefinition` / `ProjectionEnvelope` → transaction de synchronisation → `ProfileStore` → stream Drift → widget.

- Django Now/En cours utilise le profil authentifié, les projections propriétaires et `projection_envelope` ; Discovery applique sa portée publique/personnelle et rejette une substitution arbitraire de `profile_id`.
- L'enveloppe `{meta, data}` avec `schema_version: 1` correspond au parseur Flutter. Aucun contrat ou DTO n'a été changé.
- Sur le profil local utilisé sur le Samsung, SQLite contient `personal.now` et `personal.ongoing`, avec `items: []`, `selection.state: empty` et `terminal.state: empty`.
- `discovery.items` contient 24 résultats dans le pack acquis, avec `selection.state: ready` et `terminal.state: ok`.
- Les sources correspondantes ont un succès enregistré et aucun code d'erreur après retour au backend. Les timestamps de génération/réception ont été renouvelés.
- Aucun token, mot de passe, credential ou payload personnel brut n'a été affiché. Les copies temporaires de diagnostic SQLite ont été supprimées.

Un HTTP 200 seul n'a pas été utilisé comme preuve : la présence et la forme des snapshots, l'état des sources puis le rendu Android ont été vérifiés.

## Corrections

- `mobile/lib/app/makolo_app.dart` : `skipLoadingOnRefresh: false` interdit le rendu de l'ancien runtime disposé pendant sa reconstruction.
- `mobile/lib/design/surface_states.dart` : une erreur récupérable sans contenu prend priorité sur le skeleton ; avec contenu et message explicite, elle conserve la surface et propose Réessayer.
- `mobile/lib/features/now/now_screen.dart` : erreurs locales/source sans snapshot rendues explicitement ; reprise via le lifecycle de synchronisation ; contenu local conservé.
- `mobile/lib/features/ongoing/ongoing_screen.dart` : abonnements stables et rebinding lors du changement de repository ; lecture de l'état de la source ; distinction absence locale / vide confirmé / erreur ; retrait du cache mémoire lorsqu'un snapshot local est effectivement retiré.
- `mobile/lib/features/discovery/discovery_screens.dart` : erreurs de lecture/hydratation remontées à la présentation ; erreurs de source prises en compte même sans snapshot ; garde mounted après les lectures asynchrones.
- `mobile/lib/features/discovery/discovery_mature_view.dart` : message et reprise cohérents avec les possibilités déjà enregistrées.
- Tests : `runtime_replacement_test.dart`, `surface_loading_regression_test.dart` et nouveau cas dans `ongoing_screen_test.dart`.

La modification préexistante de `mobile/android/app/src/debug/AndroidManifest.xml` autorisant HTTP en debug a été conservée, sans modification par cette correction. Le commit local préexistant sur l'écran invité reste également intact.

## Validation

Toolchain : Flutter 3.47.3 / Dart 3.13.3.

Suite ciblée élargie : **70 tests passent**, sur les fichiers suivants :

```text
surface_loading_regression_test.dart
runtime_replacement_test.dart
now_screen_test.dart
ongoing_screen_test.dart
discovery_mature_screen_test.dart
discovery_mature_selector_test.dart
sync_engine_test.dart
local_database_test.dart
account_session_test.dart
guest_router_test.dart
session_recovery_test.dart
post_login_handoff_test.dart
```

Après ajout du cas de retrait d'une projection privée, les **5 tests** de `ongoing_screen_test.dart` passent. Le nouveau cas vérifie que le dernier contenu en mémoire n'est pas réaffiché après retrait du snapshot. Les tests existants de conservation du contenu, d'isolation des profils et de retrait owner-scoped sur 403/404 sont conservés.

Les trois nouveaux cas HTTP 500 traversent client API, parseur d'erreur, synchronisation, SQLite puis widget et vérifient : aucun skeleton, erreur explicite, données conservées et action Réessayer.

- `flutter analyze --no-pub` : aucun problème.
- `bash tool/dart_format.sh write` puis `check` avec le SDK canonique : passent ; contrôle final sans modification.
- `git diff --check` : passe.
- APK debug flavor dev construit avec le profil Local USB (`MAKOLO_API_BASE_URL=http://127.0.0.1:9999`), installé par `adb install -r` sur Samsung SM-N981U.

### Observations Android

| Scénario | Résultat observé |
|---|---|
| Now, backend local | `Tout est en ordre. ✓`, conforme au snapshot vide confirmé |
| En cours, backend local | `Rien en cours pour le moment.` |
| Découvrir, backend local | Possibilités visibles à partir du pack local de 24 résultats |
| HTTP 503 injecté, Now | Erreur de mise à jour et Réessayer, aucun skeleton permanent |
| HTTP 503 injecté, En cours | Erreur de mise à jour, conservation annoncée et Réessayer |
| HTTP 503 injecté, Découvrir | Possibilités conservées, erreur et Réessayer |
| Backend rendu inaccessible via ADB reverse | Données acquises conservées ; Découvrir reste consultable avec reprise explicite |
| Backend restauré + Réessayer dans Découvrir | Erreur et bouton de reprise disparaissent, possibilités visibles ; code d'erreur source effacé |

Les fautes ont été injectées uniquement sur le transport du téléphone, avec un serveur diagnostic local répondant 503, puis retrait temporaire du reverse. Le serveur Django et ses données n'ont pas été modifiés. Le reverse original `tcp:9999 → tcp:9999` a été restauré et les sources personnelles/Discovery ont de nouveau réussi.

Le profil utilisé n'a aucun élément personnel en cours : la conservation Android d'engagements non vides n'est donc pas démontrée sur ce profil. Elle est couverte par les tests de contenu connu, de rafraîchissement échoué et de persistance offline. Aucun nouveau contenu n'a été créé pour remplir ce manque.

## Auto-revue

Le propriétaire de la panne reste le runtime mobile et ses lecteurs locaux. Aucun domaine, état métier, endpoint, dépendance, migration ou autorité locale n'a été ajouté. Aucun timer ne termine artificiellement le chargement. Les échecs deviennent récupérables et le contenu acquis reste lisible. Les tests existants n'ont pas été affaiblis. Le retrait d'une projection privée n'est pas annulé par un cache mémoire. La validation ne prétend ni une CI distante ni une migration PostgreSQL, puisque le backend et son schéma n'ont pas été modifiés.
