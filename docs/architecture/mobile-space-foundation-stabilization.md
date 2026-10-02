# Mobile Space — stabilisation de la fondation actor-aware

**Statut :** handoff PR4  
**Base initiale vérifiée :** `main@63a7de0beaba98290c27eb3c27c909bf1bd7186e`  
**Fondations :** #433 ActorContext, #435 local-first actor-scoped, #436 actor-aware shell

## Objet

PR4 stabilise les coutures communes Profile/Space avant la parallélisation des surfaces Mobile.

Elle ne livre pas les surfaces finales Maintenant, Découvrir, Métier, Nous, Relations, Piloter, Jour J, Live, Scanner ou Mark Space complet.

Le contrat reste :

```text
Account / Session
  -> Profile authentifié
  -> ActorContext
       -> Personal
       -> Space
            -> perspective éventuelle
  -> SyncSource actor-scoped
  -> base locale Profile-scoped
  -> shell actor-aware
```

Un changement d'acteur ne change ni de compte, ni de Profile, ni de base locale Profile-scoped.

## Seams stabilisés

| Seam | Contrat retenu | Couverture |
| --- | --- | --- |
| Session / Profile | le Profile reste la personne authentifiée | tests compte existants + isolation Profile |
| ActorContext | Personal ou Space ; aucune autorité embarquée | `actor_context_test.dart`, `actor_context_stabilization_test.dart` |
| Persistance acteur | préférence indexée par Profile | tests de restauration et écritures concurrentes |
| Workspace inventory | inventaire serveur autoritatif des Spaces disponibles | `space_repository_test.dart` |
| Space identity | `id` stable pour l'identité locale ; `slug` pour le routage serveur | `space_repository_test.dart` |
| Perspective | clé opaque de lecture ; `all` reste le fallback | tests repository + shell |
| Sync actor scope | source/resource key par Space et par perspective seulement lorsque le contrat l'exige | `space_repository_test.dart`, `space_foundation_stabilization_test.dart` |
| DB locale | une DB Profile-scoped ; Personal -> Space n'ouvre pas une autre DB | runtime builder + tests store |
| Shell | même Makolo, portes sémantiques Personal/Space | `space_actor_shell_test.dart` |
| Route racine | une route ne crée pas d'autorité ; elle est reconciliée avec l'acteur courant | `feature_root_routes_test.dart` |
| Makolo Mark | conserve explicitement l'ActorContext courant ; Avatar reste le Profile humain | `space_actor_shell_test.dart` |
| Recovery | acteur, perspective et porte sont restaurables par Profile puis revalidés | tests actor context, shell recovery et repository |
| Revocation | seul un résultat autoritatif pertinent peut rabattre Space -> Personal | tests repository + controller |
| Offline | transport failure conserve contexte et snapshots autorisés | tests sync/repository existants |

## Corrections racines de PR4

### 1. Ordre des transitions ActorContext

Les changements d'acteur sont maintenant sérialisés et la dernière intention gagne.

Une persistance lente d'un ancien choix ne peut plus republier un Space A après une sélection plus récente de Space B.

Une perspective sélectionnée reste une perspective de lecture. Elle ne devient ni Permission ni Mandate.

### 2. Résultats de revalidation obsolètes

Une réponse de révocation reçue tardivement pour Space A ne peut plus rabattre vers Personal si l'utilisateur agit déjà pour Space B.

Si le même Space reste l'acteur demandé, une révocation autoritative continue à produire le fallback sûr vers Personal.

### 3. Préférences de lancement concurrentes

Les mutations du fichier de préférences sont sérialisées par chemin de fichier, y compris entre instances successives du store.

Cela empêche une écriture ActorContext, shell location, thème ou autre préférence de perdre une écriture concurrente issue du même fichier, notamment pendant les transitions multi-Profile/restart.

Aucun nouveau stockage métier n'est introduit.

## Isolation et races prouvées

Les tests de PR4 couvrent explicitement :

- Personal -> Space A -> Space B -> Personal en conservant la porte sémantique ;
- persistance Profile-scoped de l'acteur et de la route shell ;
- sélection concurrente A/B avec écriture A terminant tardivement ;
- révocation A arrivant après un switch vers B ;
- réponse réseau Space A arrivant après l'acquisition Space B ;
- réponse perspective `all` arrivant après `finance` ;
- re-key du rendu Space afin qu'un snapshot A ne soit pas présenté sous B ;
- Mark en Personal puis en Space sans remplacer l'Avatar humain ;
- route `/space/now` sous ActorContext Personal sans acquisition d'autorité par l'URL.

Les garanties déjà présentes de #435 restent en place :

- 403/404 invalide uniquement la source concernée ;
- les autres snapshots restent conservés ;
- transport failure/offline ne vaut pas révocation ;
- un inventory autoritatif absent du Space actif provoque Space -> Personal ;
- un même `space.id` avec nouveau slug répare l'identité sans dupliquer le Space ;
- une perspective disparue retombe sur `all` lorsque le Space reste légitime ;
- Personal, Spaces et perspectives utilisent des resource keys distinctes ;
- les stores restent isolés par Profile.

## Offline, fraîcheur et autorité

PR4 ne modifie ni `FreshnessPolicy` ni les règles d'invalidation.

Les invariants restent :

```text
stale != invalid
stale != current
snapshot != authority
offline != revoked
transport failure != revoked
cached capability != current authority
```

Le serveur reste autoritatif pour Permission, Mandate, Access partagé, Payment, Capacity globale, concurrence et état Live courant.

## Deep links, notifications et scanner

Le pipeline d'ingress actuel transporte des `StructuredDestination` et résout des routes canoniques. Il ne crée pas un ActorContext Space.

PR4 vérifie la couture racine : une route Space ne transforme pas à elle seule Personal en Space.

Aucun nouveau système Push, Scanner ou QR n'est introduit. Les expériences Scanner/Jour J/Live restent des chantiers ultérieurs.

## Makolo Mark

Le Mark actuel lit l'ActorContext du runtime et conserve le contexte Space lorsqu'il est actif.

PR4 ne crée pas de moteur Mark parallèle et ne finalise pas les mutations au nom d'un Space. Le contrat complet Mark Space reste ouvert pour sa lane dédiée.

## Migrations

- Django migrations : **none**
- Drift migrations : **none**
- nouvelles tables : **none**

La structure existante `ProfileStore` / `ProjectionSnapshots` / `SyncSources` suffit pour cette stabilisation.

## Sécurité et confidentialité

PR4 n'ajoute aucune autorité locale.

```text
Account != ActorContext
Profile != Space
Perspective != Authority
Assignment != Permission
Membership != Permission
Route != authority
Deep link != authority
Owner != actor scope
```

Aucun cache n'est utilisé comme preuve durable d'autorité et aucune donnée d'un Profile n'est volontairement projetée dans le store d'un autre Profile.

## Fichiers centraux à considérer comme seams partagés

Les lanes suivantes doivent éviter de modifier simultanément, sauf bug démontré :

- `mobile/lib/app/runtime/actor_context.dart`
- `mobile/lib/app/runtime/actor_context_controller.dart`
- `mobile/lib/app/runtime/app_runtime.dart`
- `mobile/lib/app/runtime/runtime_builder.dart`
- `mobile/lib/app/launch_preferences.dart`
- `mobile/lib/app/app_shell.dart`
- `mobile/lib/app/router.dart`
- `mobile/lib/sync/sync_engine.dart`
- `mobile/lib/sync/sync_source.dart`
- `mobile/lib/data/local/profile_store.dart`
- `mobile/lib/features/space/space_repository.dart`
- `mobile/lib/navigation/actor_selector.dart`
- `mobile/lib/navigation/space_context_bar.dart`

Les surfaces doivent consommer ces contrats, pas créer `SpaceRuntime`, `SpaceDatabase`, `SpaceSyncEngine`, `SpaceRouter` ou une autorité locale parallèle.

## Gaps volontairement ouverts

Restent hors PR4 :

- Maintenant Mature et son selector/ranking ;
- Découvrir Mature, Search/Map et pertinence ;
- Métier Mature ;
- Nous Mature ;
- Relations et Piloter ;
- mutations Space Mobile et sémantique actor-aware future de l'Outbox ;
- Jour J opérateur ;
- Live ;
- Scanner ;
- Mark Space complet ;
- richer media ;
- Molongo / intelligence et selectors futurs.

## Parallélisation après PR4

Sous réserve du `main` courant au démarrage de chaque chantier, les lanes peuvent désormais partir du même noyau commun :

1. Maintenant + Découvrir ;
2. En cours / Moi + Métier / Nous, puis Relations / Piloter ;
3. Makolo Mark + Jour J + Live + Scanner.

Chaque lane doit refaire son collision audit avant de modifier un seam central.
