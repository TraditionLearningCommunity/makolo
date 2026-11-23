# Makolo / Découvrir — Chantier 08 : local-first et confidentialité

**Date** : 2026-11-02  
**Dépôt / PR** : `TraditionLearningCommunity/makolo` / #522, branche `fix/discover-a-continuation-context-20261014`  
**Statut** : implémentation **livrée en code**, certification différée à 09. **Aucune CI, analyse Flutter, suite Django ni session appareil exécutée** à cette étape.

## 1. Objet et frontière

Fermer **R13, R18, R19, R25 et R26** autour du champ Découvrir N1, recherche, carte, N2, Veilles et ressources déjà acquises. Partir du noyau existant : `ProfileStore`, `MakoloDatabase` (Drift), `SyncEngine`, `SyncSourceDefinition`, `FreshnessPolicy`, `DiscoveryRepository`, `DiscoveryOfflineStore`, les composants et écrans Flutter. **Aucun nouveau moteur de sync, nouveau modèle métier, état d'autorité local, migration serveur ni nouveau SQL schema.**

- **Le store local** détient les projections personnelles déjà reçues et une continuité de présentation bornée.
- **Le serveur et les propriétaires** déterminent admission, visibilité, Watch, Save, Sharing, Access, Capacity, Payment, Permission et toute action N3.
- **Offline** est une condition de réseau indépendante de l'état de contenu. Une possibilité déjà acquise reste reconnaissable (avec indication de fraîcheur) ; une nouvelle possibilité ne peut pas être fabriquée hors ligne.
- Le client ne déclare jamais une action C ou D réussie sans réponse du propriétaire.

Références d'architecture utilisées : `docs/architecture/mobile-local-data-kernel.md`, `docs/architecture/mobile-sync-continuity-kernel.md`, `docs/architecture/mobile-a2-local-first-surfaces.md`, `docs/architecture/mature-experience-principles.md`, ainsi que les contrats Behavior/UX Découvrir du projet. Le code courant prime sur les documents de destination.

## 2. Projections, Profile et lecture locale

### 2.1. Scopes et identité

- La base `MakoloDatabase.openForProfile(profileId)` préexistante utilise une base SQLite propre au Profil ; `ProfileStore` impose déjà `profileId` dans toutes ses lectures, écritures et suppressions.
- `DiscoveryRepository._readAvailable` centralise la décision de **lecture locale** pour listes, cartes, détails et Veilles : une tombstone de refus owner 403/404, un `expiresAt` dépassé, un wire liste d'un autre viewer, un schéma non reconnu ou une identité N2 contradictoire empêchent toute présentation.
- `watchItems` (y compris la page 1), `readItems`, `watchMap/readMap`, `watchItem/readItem`, `watchWatches` et les pages de résultats Watch passent par cette frontière. La même source ne peut pas être réutilisée comme un `viewer` différent.

### 2.2. Snapshot ≠ fraîcheur ≠ autorisation

- `ProfileStore` conserve `receivedAt`, `sourceGeneratedAt`, `lastVerifiedOnlineAt`, `expiresAt`, `freshnessPolicyId` séparément du contenu ; `FreshnessPolicy` distingue fresh, refresh recommended, usable but old, revalidation required et expired.
- `SyncEngine` distingue transport failure (ne détruit pas un snapshot) de refus explicite de l'owner (révocation). Tous les refus HTTP 403/404 sont normalisés en `permission_denied` ou `not_found`, quelle que soit la valeur d'erreur propriétaire, pour conserver une tombstone intelligible après démarrage à froid.
- **N1 root, Recherche, carte et N2** peuvent afficher les faits déjà reçus avant retour du serveur, mais leur `_verifiedFieldKey` / `_verifiedItemKey` est **volatile et initialement nul**. Le Save et le handoff N3 ne sont réactivés qu'après une réponse owner valide pour le contexte exact, sans refus ou erreur. Le redémarrage à froid réévalue donc l'autorité même si SQLite présente un snapshot récent.
- L'unité `DiscoveryPossibilityUnit` accepte `allowOwnerActions` et retire les boutons sensibles ainsi que les destinations natives si faux, sans inventer un statut commercial. N2 explique que les faits conservés ne valent pas nouvelle autorisation.

## 3. Révocation, réseau et concurrence

- `SyncEngine` suit une **génération par source** : la réponse d'un ancien refresh ne peut ni écraser un refus plus récent ni fabriquer un succès.
- Une **époque de révocation Discovery** invalide également les requêtes Discovery, Activity et Occurrence **encore en vol sur d'autres sources** au moment d'un refus (pas seulement la requête ayant reçu 403). C'est une barrière de cohérence locale, et non une décision métier.
- Le traitement explicite de 403/404 retire, **dans le Profil concerné seulement**, les collections, cartes, détails, previews, résultats Watch et curseurs de présentation dérivés. Le statut de la source refusée reste tombstoné ; les clés des sources Discovery sont invalidées pour réacquisition, sans effacer les données d'autres Profils.
- Un timeout, un échec DNS, un transport interrompu ou un code technique inconnu **ne** déclenche **pas** ces suppressions : les éléments déjà acquis restent visibles comme anciennes observations. Le retour online acquiert de nouveau auprès de l'owner.
- Les snapshots en mémoire d'une carte ne valent pas preuve d'un Access actuel ni d'une réservation.

## 4. Rotation, continuation et reprise

- `ProfileStore.pruneProjectionsOfKind` est une **rotation bornée par Profil et par type**, triée par date de réception et respectant explicitement les clés protégées. L'implémentation n'évince pas un owner canonical d'un autre domaine.
- Les valeurs courantes sont des plafonds de **rétention locale**, non des limites métier : 48 pages de transport, 80 détails, 120 previews Activity, 120 previews Occurrence, 24 pages Watch et 12 cartes. Elles n'ont aucun effet sur le nombre total de possibilités publiées par le serveur.
- La fenêtre de présentation cumulée conserve au maximum **50 candidats réellement reçus** ; sa provenance et ses timestamps restent ceux du serveur. Une première page fraîche invalide une fenêtre rattachée à une continuation précédente ; une fenêtre dérivée ne peut pas précéder sa page racine actuelle.
- Les pages courantes et les premières pages nécessaires sont protégées durant la rotation. Le code n'invente jamais un nouveau jeton : `continuation` reste opaque, signé et contrôlé par l'API.
- Le stockage `discovery.presentation-position` existant conserve uniquement la page, le curseur réel, le scroll et la candidate key dans le Profil. Une continuation rejetée repart du contexte premier sans fabriquer une nouvelle page.
- Les mêmes critères de recherche/carte restent la base de restitution ; la lecture hors ligne d'une page jamais synchronisée retourne l'absence, pas le lot précédent déguisé.

## 5. Médias : public automatique versus Reader privé

- `DiscoveryOfflineStore` conserve ses protections déjà existantes : origine de confiance, chemin media-use public publié, extension MIME contrôlée par les composants, quota de 10 images / 32 MiB pour la reconnaissance automatique, 8 MiB par image, écritures atomiques sérialisées.
- `purgeAutomaticRecognition` supprime **exclusivement** les images de reconnaissance automatique après refus owner, derrière la file des écritures. Une écriture en vol ne peut pas remettre les octets après le retrait.
- Le défaut corrigé : le lecteur conservait des fichiers explicitement choisis dans `discovery/public-offline` commun à l'appareil. Le stockage Reader est maintenant séparé `profiles/<profileId>/discovery/reader` via `ProfilePaths.safeProfileId`, en utilisant l'identité **du Profil authentifié** et non du Space courant.
- Une session invitée ne peut garder pour usage hors ligne que les chemins de média publique `/presentation/media/uses/<uuid>/file/` de la même origine vérifiée, sans query/token. Les URLs étrangères, privées, signées ou non vérifiables restent hors rétention automatique.
- **Les anciens fichiers Reader non cloisonnés ne sont pas relus/migrés** : ils pourraient mélanger des données de plusieurs personnes. `purgePrivateReader` permet le retrait sélectif du Profil après refus du propriétaire. Les fichiers volontairement exportés dans les Téléchargements Android relèvent du système et ne sont pas prétendus révoqués par Makolo.
- `DiscoveryReader`, `DiscoveryPossibilityUnit` et les compositions compactes / larges / spatiales transmettent `profileId` jusqu'au store privé. La commande de rétention n'est plus proposée aux invités pour des ressources non publiques. Les octets en mémoire du lecteur sont invalidés dès que le Profil ou la destination change. Même pour un Profil authentifié, les URLs signées, contenant des identifiants ou non HTTP(S) restent transitoires et ne deviennent pas des copies Reader hors ligne.

## 6. HTTP : données personnelles non mises en cache par un intermédiaire

Les façades `discovery/api/views.py` et `sharing/api_views.py` appliquent désormais un boundary `finalize_response` commun à leurs routes : **`Cache-Control: private, no-store`** et conservation des en-têtes `Vary: Authorization, Cookie`. Cela s'applique aux pages publiques, aux projections personnelles, aux détails, aux Watches, aux ressources Saved, aux liens opaques, aux destinataires et aux réponses de refus. Ce mécanisme ne donne aucun nouveau droit : il empêche le mélange de réponses sensibles via un cache HTTP.

## 7. Watch et Save : cohérence de projections

Après une mutation Watch **confirmée par le propriétaire** (création, statut, renommage, remplacement des critères, suppression), `DiscoveryRepository._applyConfirmedWatch` met à jour la projection de liste locale **à partir de la réponse owner** et conserve sa datation réelle. L'ancienne page de résultats de cette Watch est retirée après modification ou suppression. Un refresh réseau échoué après une mutation confirmée ne prétend pas que l'ancienne liste est l'état récent.

Save reste une mutation distante avec vérification `family/id/saved.state` et sans file d'exécution locale fictive ; la réponse tardive d'un ancien candidat ne peut pas marquer le candidat actuellement affiché.

## 8. Tests ajoutés — **NON EXÉCUTÉS**

- `mobile/test/discovery_stage08_local_first_test.dart` : offline avec snapshot, absence de nouveaux candidats locaux, isolation inter-Profils, rejet viewer/identité contradictoires, cascade 403 et autres Profils préservés, réponse tardive 200 après 404, rotation et clé active préservée.
- `mobile/test/discovery_stage08_media_privacy_test.dart` : fichiers Reader séparés par Profil, ancien stockage partagé non repris, invité limité à média public first-party, quotas/révocation automatique versus copie privée.
- `mobile/test/discovery_stage08_action_boundary_test.dart` : N2 stale consultable sans Save ni N3, parcours N3 ouvert seulement après revalidation propriétaire.
- `discovery/api/test_stage08_http_privacy.py` : en-têtes `no-store` / `Vary` sur Discovery public, personnel, Watch et refus, ainsi que les resolveurs Sharing.

Ces fichiers ne sont **pas** des résultats d'exécution. Aucune promesse de fonctionnement sur l'appareil Android n'est établie avant la certification 09.

## 9. Limites explicites et handoff vers 09

- Les opérations réelles de fichiers système et de caches WebView/OS/MapLibre sur Android doivent être observées sur appareil ; la révocation n'efface pas les copies déjà exportées hors de l'app.
- Les anciens fichiers de `discovery/public-offline` ne sont **pas** repris par le nouveau lecteur. Leur suppression physique sur les installations anciennes doit être traitée par la politique locale de maintenance/upgrade ; la lecture a été coupée pour éviter toute exposition croisée.
- Un fichier local ou snapshot acquis hors ligne ne peut pas témoigner d'une publication toujours actuelle tant que l'owner n'a pas été contacté ; les opérations autoritatives sont suspendues jusqu'à revalidation.
- La certification doit inspecter les erreurs de compilation/analyse, les transitions App lifecycle, les changements de compte, la fermeture/ouverture SQLite, les futures concurrentes, les erreurs HTTP 403/404/500, les widgets à texte agrandi, l'Android réel et le comportement des liens externes.
- CI et tests ciblés, PostgreSQL, migrations/compatibilité, Flutter analyzer/format, UI Web/Flutter, Android end-to-end et éventuel merge **restent réservés au chantier 09**.

**Verdict de livraison : chantier 08 implémenté et documenté au niveau code ; résultat exécuté NON ATTESTÉ. Prochain chantier autorisé : 09 seulement.**
