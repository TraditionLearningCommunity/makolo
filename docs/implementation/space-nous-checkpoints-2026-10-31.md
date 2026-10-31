# Space / Nous — S0 : réconciliation sur la PR #522

**Périmètre** : Nous uniquement. Le Passeport (Sharing, émission, PDF, partage, variantes) appartient à un autre chantier et n'est pas modifié ni planifié ici.

## Références vérifiées le 31 octobre 2026

- Dépôt : `TraditionLearningCommunity/makolo`
- Base de la PR : `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f`
- HEAD examiné de la PR #522 : `085eb5b39cdf563da22b127bef40fb39678f46db` (susceptible d'évoluer après ce commit)
- Branche unique : `fix/discover-a-continuation-context-20261014`
- 359 chemins modifiés dans #522 à la réconciliation ; vérifier à nouveau avant une écriture future.
- La PR #528 a été fermée sans merge. Son document de diagnostic a été transféré dans #522.
- Travail S0 documentaire uniquement ; pas de migration, modification d'API, mutation de permissions, changement Flutter ni exécution de tests/CI.

## Matrice de propriété et collisions

| Surface / fichiers | Situation vérifiée | Responsable | Statut pour Nous |
| --- | --- | --- | --- |
| `organizations/api/space_us_projection.py` | Projection existante dans main ; identité, team, responsibilities, ownership, trust, handoffs ; non listée parmi les chemins modifiés de #522 | Organizations / Nous | Propriétaire direct ; évolution possible après revue de contrats |
| `organizations/api/space_zs4_views.py` | `SpaceUsAPIView` privé via `workspace_spaces` et `Cache-Control: private, no-store` | Organizations / Authorization | Propriétaire de l'API privée ; préserver le contrôle serveur |
| `organizations/api/space_relationships_projection.py` | Projection existante avec Teams, Groups, CRM, Partners sous permissions | Organizations + propriétaires des relations | Propriétaire des read models Nous, pas des données métier |
| `organizations/api/public_space_views.py`, `organizations/test_public_space_api.py` | Modifiés sur #522 ; projection publique déjà présente | Organizations / Guest | **Partagé en évolution** ; lire avant modification, ne pas confondre public et opérateur |
| `organizations/api/space_work_projection.py`, `organizations/test_zs3_space_work_api.py` | Modifiés sur #522 ; checkpoint Métier distinct documenté | Space Métier | Hors propriété Nous ; seulement handoffs vers Métier |
| `mobile/lib/features/space/space_shell_routes.dart` | Surface native Nous et racines Space existantes ; pas de modification listée dans #522 au moment du scan | Space UX Flutter | Propriétaire UI Nous, mais cohabite avec Now/Discover/Métier |
| `mobile/lib/features/space/space_repository.dart` | Sources `space.us`, `space.relationships`, snapshots ; pas de modification listée dans #522 | Space mobile | À réutiliser ; inspecter source, révocation et profile isolation avant changement |
| `mobile/lib/features/guest/public_space_screens.dart` | Modifié dans #522 | Guest / Public | Partagé ; ne pas détourner la surface publique pour l'opérateur |
| `mobile/lib/data/local/profile_store.dart`, `mobile/lib/sync/sync_engine.dart`, `mobile/lib/sync/projection_contract.dart` | Modifiés dans #522 | Kernel local-first transverse | **Zone rouge de collision** ; aucune réécriture depuis Nous sans contrat explicite |
| `mobile/lib/navigation/avatar_sheet.dart`, `shell_header.dart`, `deep_link_resolver.dart`, `incoming_intent.dart` | Modifiés dans #522 | Navigation globale | **Zone rouge de collision** ; privilégier routes propriétaires |
| `sharing/**` et migrations Sharing de #522 | Nombreux fichiers modifiés | Chantier Passeport séparé | **Exclus** de Nous, aucune intervention |
| `accounts/migrations/0009_profile_visibility_policies.py`, `services/migrations/0005_service_start_operation_fingerprint.py`, `presentations/migrations/0005_presentationmediause.py`, `0006_private_presentation_assets.py`, `sharing/migrations/0006_passport_issued_public_and_sharing.py`, `topics/migrations/0005_profile_publishable_defaults.py` | Migrations additives figurant parmi les changements de la PR #522 | Domaines respectifs | Aucune migration Nous justifiée en S0 |
| `authorization/` | Selectors et Mandates canoniques existants ; aucun chemin modifié de ce répertoire dans le scan #522 | Authorization | Consommation des capacités, aucune autorité inférée par UX |

La liste de fichiers est un inventaire GitHub de la PR, **pas** une validation fonctionnelle. Les tests n'ont pas été exécutés ici.

## Écarts structurants à examiner après S0

1. L'API `space.us` est une lecture opérateur privée ; elle n'est pas la même vue que la consultation publique existante. La présence dans Team/Group ne doit pas être interprétée comme Mandate.
2. L'identité Nous et l'équipe peuvent être présentées avec une autorité limitée. Distinguer contenu absent, masqué et inconnu.
3. Chaque handoff Nous doit être relié à une vraie route native Flutter et à une destination Web utilisable, sans renvoi interne vers le Web depuis Flutter.
4. Le local-first propriétaire Space doit utiliser la persistance/synchronisation commune avec isolation et révocation ; aucun nouveau noyau.
5. Aucun travail sur le Passeport : sa représentation et son export seront traités indépendamment.

## Séquence décidée pour la suite (sans exécution dans ce commit)

- **S1** : visibilité, autorité et projections Nous, avec tests serveur ciblés.
- **S2** : racine Nous Web/Flutter, identité collective et hiérarchie de présentation.
- **S3** : organisation, équipe, groupes, responsabilités et destinations propriétaires.
- **S4** : relations et capital collectif owner-backed, sans doublons métier.
- **S5** : routes, handoffs, comportement natif, local-first et révocation en coordination avec les composants communs déjà touchés par #522.
- **S6** : validation fonctionnelle et visuelle ciblée ; l'utilisateur effectue les exécutions Django/Flutter locales. Pas de CI demandée pour avancer.

**Critère de sortie S0** : matrice propriétaire/partagé consignée, collisions identifiées, périmètre Nous séparé du Passeport, aucune modification de comportement.


## Implémentation Nous intégrée à la PR #522 — 31 octobre 2026

**Passeport / Sharing : strictement hors périmètre, aucun fichier de ce domaine modifié par ce chantier.** Les projections ne créent aucune vérité métier ni autorité.

### Réalisé dans ce passage

1. **Serveur Nous** — `organizations/api/space_us_projection.py` expose une visibilité explicite pour `team` et `ownership`. La racine compose les aperçus bornés de `space_relationships_projection.py`, sous permissions propriétaires, sans pouvoir d'écriture ni nouvelles tables. Le handoff relations n'est exposé que si une section est réellement visible.
2. **Web Nous** — `organizations/space_web_views.py` respecte le handoff autorisé. `templates/organizations/space/us.html` rend la synthèse des relations, humanise la gouvernance et évite le CTA Relations sans cible autorisée.
3. **Flutter Nous** — nouvelle `mobile/lib/features/space/space_us_surface.dart`, raccordée à `space_shell_routes.dart`. Identité collective, archétype/preset fourni, lifecycle non actif, responsabilités non combinées, équipe selon visibilité, relations autorisées, gouvernance, Trust factuel, destinations exactes du Space. Les chemins falsifiés inter-Space ne sont pas proposés.
4. **Profondeurs Flutter** — `SpaceNousDepthScreen` rejette le changement d'acteur, vérifie le handoff exact et charge la liste complète de l'équipe par l'API `/team/` si accessible. L'aperçu autorisé reste possible hors réseau, sans fabriquer de droits. Les vues de responsabilités et gouvernance sont humanisées.
5. **Paramètres institutionnels Flutter** — nouvel `space_us_settings_screen.dart`, route native `/space/:slug/us/settings` ajoutée à `mobile/lib/app/router.dart`. GET frais de `space.us` avant formulaire, vérification Space actif et `update_space`, PATCH de l'API workspace existante, revalidation serveur, rafraîchissement des projections après succès. Aucun enregistrement offline fictif.
6. **Contrats ciblés ajoutés** — assertions Django dans `organizations/test_zs4_space_projections.py` et `organizations/test_ws4_space_web.py`, plus `mobile/test/space_us_surface_test.dart` couvrant visibilité limitée, tailles et liens inter-Space.

### Non exécuté / non prétendu terminé

- Les tests Django, Flutter, analyseur Dart et la CI **n'ont pas été exécutés** à la demande de l'utilisateur (exécution locale prévue). Aucun résultat vert n'est revendiqué.
- Les opérations natives d'équipe et de transfert de propriété appellent les API owners existantes avec contrôle serveur. Les options de rôles viennent du catalogue canonique autorisé. Aucun Mandate n'est généré par une projection.
- L'édition native de la visibilité publique est une mutation autorisée de l'identité Space ; les autres domaines publics restent propriétaires de leur découverte.
- Les profondeurs Trust, Pilot et Relations utilisent leurs propriétaires et flux existants ; aucune projection Passport n'est introduite.
- Aucune migration ni modification de `main`. PR #522 non fusionnée.

### Commandes recommandées pour la validation locale

```sh
python manage.py test organizations.test_zs4_space_projections organizations.test_ws4_space_web
cd mobile
flutter test test/space_us_surface_test.dart test/space_actor_shell_test.dart test/nous_deep_link_test.dart
flutter analyze lib/features/space lib/app/router.dart
```

Vérifier manuellement : visiteur et Profile hors Space (404 privé), membre sans Mandate, Activity-only, Mandate Space, bascule d'acteur pendant une profondeur, liste équipe complète, refus réseau, mutation settings interdite après révocation, Compact/Medium/Wide et UI Web. Le fait de récupérer un snapshot hors réseau n'autorise jamais une mutation.

### Complément d'intégration native

Les profondeurs Équipe et Gouvernance appellent les API canoniques Team et Ownership avec confirmation. Le serveur reste souverain sur les rôles et transferts. Une panne réseau conserve les observations locales non expirées, mais désactive les mutations ; une invalidation d'autorité masque les données sensibles. Aucun travail Passeport n'est inclus.


## Fermeture des profondeurs et comportements Nous — 31 octobre 2026

Travaux **implémentés et poussés** sur la PR #522, sans modifier le domaine Passeport/Sharing, les migrations ni `main`.

### Profondeurs utiles

- **Responsabilités** : les Mandates existants, présentés comme perspectives et non comme autorisations nouvelles, proposent une continuation vers Métier selon le `key` exact reçu du serveur ; Web passe `?responsibility=mandate:…` (encodé) à la route Métier propriétaire, Flutter change seulement `ActorPerspective`, puis ouvre `/space/work`. Le serveur revalide.
- **Relations Web** : chaque ligne d'équipe, groupe, contact CRM, audience ou partenaire visible peut ouvrir la sélection relationnelle bornée `?kind=…&id=…` ; sa route propriétaire n'est proposée qu'après vérification par la projection.
- **Relations Flutter** : `SpaceInsightScreen` est verrouillé au slug d'origine sur les routes Nous. Son état de recherche est annulé au changement d'acteur ; au retour du détail propriétaire, recherche temporaire effacée puis projection réactualisée. Refus d'une recherche à code 401/403/404 : nouvelle vérification de l'owner source, sans conserver un résultat distant potentiellement obsolète.
- **Gouvernance** : les faits de propriété restent des Mandates actifs ; transfert confirmé vers l'API `ownership/transfer/` existante, choix explicite du collaborateur actif, conservation de la propriété actuelle par défaut et vérifications serveur inchangées.
- **Confiance** : l'écran natif affiche les `claims` actives de `workspace.verification` (type, état, validité éventuelle), jamais un score. La racine Nous présente maintenant le handoff Confiance uniquement s'il est effectivement autorisé par le serveur.
- **Équipe et Paramètres** : mutations natives existantes, toujours confirmées par les API propriétaires ; pas de droits déduits d'une simple appartenance.

### Comportements fermés

- Au retour d'un écran natif propriétaire vers la racine Nous, rafraîchissement de la projection Nous.
- Les pages Web Nous et Relations sont explicitement `Cache-Control: private, no-store`.
- Pendant la résolution d'un deep link, le changement d'acteur engagé par la personne n'est pas écrasé par une réponse d'inventaire tardive.
- À chaque changement d'acteur, les détails complets de Team en mémoire sont éliminés ; un retour au Space d'origine exige une nouvelle acquisition.
- Les snapshots locaux non expirés peuvent servir d'observation quand l'API est indisponible, mais aucune mutation Team/Ownership n'est proposée sans source récemment validée. Une invalidation d'autorité reste bloquante. Les profondeurs manquantes ou expirées proposent un véritable réessai.
- Les états vides de Relations distinguent une collection autorisée mais vide, une recherche sans correspondance et un contexte dépourvu d'autorité.

### Tests de contrat modifiés, non exécutés

- `organizations/test_ws4_space_web.py` : handoffs vers Métier, encodage de la perspective, relations directement consultables, confidentialité/no-store.
- `mobile/test/space_actor_shell_test.dart` : faits de confiance affichés et disparition de la Team après changement d'acteur.
- `mobile/test/space_us_surface_test.dart` : ouverture du handoff Confiance, en complément des contrôles de visibilité et de lien inter-Space existants.

**À valider localement par l'utilisateur** : Django, Flutter analyzer, widgets, retour depuis une opération, permissions IDOR, révocation avec réseau et hors réseau. Aucune CI lancée, aucun merge effectué, aucun résultat de test revendiqué.


## Retours d'exécution locale — réparation ciblée (31 octobre 2026)

- Retour utilisateur : `flutter analyze` et `flutter test` ne compilaient pas `space_us_surface.dart`, à cause de deux conditions combinant `&&` avec `case final target?` dans les handoffs `settings` et `pilot`. Corrigé par des variables de destinations `String?` calculées après contrôle de `activity_limited`, puis des tests `!= null`. Assertions Flutter ajoutées pour l'affichage autorisé et l'absence des actions dans le contexte limité.
- Avertissements Dart `prefer_interpolation_to_compose_strings`, `curly_braces_in_flow_control_structures` et `use_null_aware_elements` nettoyés dans les fichiers Nous concernés, sans modification de logique métier ni des autorisations.
- Retour Django : 26/27 tests réussissaient ; une assertion cherchait le mot `permissions` dans tout le HTML de Nous. La trace indiquait que l'occurrence venait d'une phrase explicative de la surface relationnelle. La version courante du template dit désormais `respecte ses propres règles d’accès`, ce qui supprime la cause du conflit **sans modifier ni supprimer l'assertion de test**.
- Les correctifs sont poussés dans la même PR #522. Aucun test ni CI exécuté depuis cet environnement ; **attendre les nouveaux résultats du poste local avant de déclarer vert**.


## Retour Flutter du 31 octobre — test d'interaction et contexte acteur

Le poste local confirme **27/27 tests Django** réussis et `flutter analyze` sans problème. Les tests Flutter restaient rouges pour deux causes identifiées :

- Les boutons Confiance/Paramètres/Piloter étaient présents dans un `ListView` plus grand que la fenêtre. `ensureVisible` seul n'avait pas rendu leur centre atteignable par `tap` dans le banc de test. Les scénarios de trois largeurs font désormais défiler `Scrollable` avec `scrollUntilVisible`, puis attendent la stabilisation avant d'activer le bouton.
- Les tests historiques de commutation d'acteur simulaient une sélection UI avec un `WorkspaceContextRepository` sans moteur de synchronisation. Or le sélecteur réel impose désormais une revalidation réseau de l'inventaire et du Workspace (invariant sécurité). Les tests de shell utilisent les transitions explicites du contrôleur, tandis qu'un test séparé vérifie que le sélecteur **refuse** de passer au Space lorsque le contexte n'est pas vérifiable hors réseau. Aucun contrôle de production n'a été affaibli.
- La profondeur Équipe expose légitimement le titre dans l'AppBar et le corps ; le test vérifie maintenant précisément le titre de l'AppBar au lieu d'imposer une occurrence globale unique.

Corrections enregistrées dans la PR #522 ; **aucune nouvelle exécution Flutter dans cet environnement**, verdict vert non revendiqué.
