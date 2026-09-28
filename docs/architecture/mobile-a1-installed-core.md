# A1 — Installed Makolo Core

> Statut : A1 final integration en validation
>
> Base du dernier audit : `main@ad7f3d23f449487676eeaeda37d432cc24d1171f`
>
> Branche de fermeture : `mobile/a1-final-integration`
>
> A1 reste ouvert jusqu'à validation CI et smoke bêta de ce dernier chantier.

## 1. Objet

A1 transforme le contrat A0 en fondation Flutter installée et local-first :

```text
Serveur Makolo
      ↕
sync owner-scoped
      ↕
projection locale Drift
      ↕
repositories / use-cases
      ↓
UI
```

Une donnée déjà acquise est lue depuis le store local. Le réseau sert à l'acquisition initiale lorsqu'elle est nécessaire, au rafraîchissement, à la synchronisation, à la confirmation et aux opérations intrinsèquement distantes. Il ne remplace pas le contenu local utile par un écran vide lorsque la connectivité change.

A1 ne définit donc aucun « mode offline » parallèle : la disponibilité locale, la fraîcheur, la joignabilité de la source distante et l'autorité sont quatre propriétés distinctes. Une perte de connectivité modifie la reachability ; elle ne change ni l'architecture de lecture locale ni les frontières d'autorité.

A1 ne construit pas les expériences complètes Maintenant, Découvrir, Makolo Mark, En cours, Moi ou Avatar. Il ferme le socle transversal que ces expériences consommeront.

## 2. Stack retenue

| Capacité | Choix A1 | Raison |
| --- | --- | --- |
| Flutter | 3.47.3 | patch stable fixé par A0 |
| Dart | 3.13.3 via Flutter | toolchain A0 |
| State/DI | Riverpod 3.4.3 | orchestration/injection, jamais store durable |
| Routing | go_router 18.0.1 | navigation structurée et reprise |
| HTTP | http 1.6.0 | client minimal encapsulé par Makolo |
| DB | Drift 2.35.0 + drift_flutter 0.3.1 | transactions, migrations, requêtes locales |
| Secrets | flutter_secure_storage 11.2.0 | stockage sécurisé natif |
| Réseau | connectivity_plus 7.3.1 | signal de transport seulement |
| Fichiers | path_provider 2.1.6 | sandbox privé/cache |
| SVG | flutter_svg 2.3.0 | rendu du Makolo Mark canonique |

Aucune URL d'environnement n'est codée en dur. `MAKOLO_API_BASE_URL` doit être fournie explicitement.

## 3. Store local

Le schéma Drift est une projection applicative, pas une copie de PostgreSQL. Il contient :

- `projection_snapshots` ;
- `resource_index` ;
- `sync_sources` ;
- `outbox_operations` ;
- `local_drafts` ;
- `file_records`.

Chaque DB est ouverte sous un namespace de Profile distinct. Les fichiers privés et le cache sont eux aussi séparés par Profile.

La version courante du schéma est 2. La migration synthétique v1→v2 ajoute `resource_index` et `last_error_code` sans supprimer l'outbox existante. La stratégie normale n'est jamais « supprimer la DB puis tout resynchroniser ».

## 4. Authentification et SessionRecovery

Le client réutilise exclusivement les routes Accounts existantes :

- `POST /api/v1/accounts/auth/register/` ;
- `POST /api/v1/accounts/auth/login/` ;
- `POST /api/v1/accounts/auth/refresh/` ;
- `POST /api/v1/accounts/auth/logout/` ;
- `POST /api/v1/accounts/auth/password/forgot/` ;
- `POST /api/v1/accounts/auth/password/change/` ;
- `GET /api/v1/accounts/auth/me/`.

L'Entry natif ferme désormais les parcours login, inscription et mot de passe oublié. L'inscription suit strictement `RegisterSerializer`. Après création réussie, le client réutilise immédiatement le contrat Login existant avec les mêmes identifiants afin d'établir la session : aucune nouvelle route ni aucun token n'est inventé par Register. Le mot de passe oublié conserve la réponse anti-énumération du serveur et s'ouvre depuis Login dans une modale dédiée ; après envoi, la modale demande simplement de consulter la boîte de réception et d'ouvrir le lien reçu. Le lien reçu par e-mail continue d'ouvrir le reset Web existant : A1 n'introduit aucun App Link ou Universal Link artificiel.

`password/reset/` reste un contrat serveur valide mais n'est pas simulé dans l'application sans `uid` et `token`. `password/change/` est préparé dans le client/repository authentifié sans construire une grande surface Settings hors A1.

Access et refresh sont stockés ensemble dans une seule valeur de secure storage afin de remplacer atomiquement la paire lors d'une rotation. Les refresh concurrents sont sérialisés par un single-flight.

Une session distante invalide retire les credentials actifs sans supprimer la DB, les drafts ni l'outbox. Le contrôleur `SessionRecoveryController` conserve la dernière route utile en mémoire de processus, demande la reconnexion puis restaure cette route une seule fois après authentification. Il ne transforme pas cet état de navigation en vérité métier persistante. Toute opération sensible reste revalidée par son owner serveur.

La déconnexion est local-first pour les credentials : la session sécurisée locale est retirée avant de dépendre du réseau, puis le blacklist du refresh est tenté côté serveur. Un serveur indisponible ne réactive donc pas la session locale. « Changer de compte » ouvre désormais une surface locale de comptes déjà utilisés sur l'appareil. Chaque entrée reste une identité authentifiée distincte ; les stores locaux restent isolés par Profile. Un compte peut proposer un accès rapide uniquement lorsque la personne l'a explicitement choisi : Makolo conserve alors la session renouvelable dans le secure storage, jamais le mot de passe. Sans accès rapide, sélectionner le compte demande le mot de passe et le gestionnaire de mots de passe du système reste libre de proposer sa propre conservation. « Retirer de cet appareil » supprime uniquement cette présence locale et son accès rapide ; cela ne supprime jamais le compte serveur.

Les erreurs d'authentification visibles sont traduites en messages sûrs ; aucun détail backend brut, JWT ou payload privé n'est présenté.


### Finition Auth & identité installée

La fermeture A1 issue du smoke Android réel fixe également :

- une surface Auth violette continue, sans grand panneau blanc contenant tout le formulaire ;
- des champs Material 3 Makolo réutilisables avec validation inline, clavier/focus, autofill et états busy ;
- un header shell qui utilise le lockup Makolo dérivé de l'asset officiel avec wordmark violet ;
- « Agir en mon nom » pour le contexte personnel dans Avatar, au lieu d'un libellé administratif « Contexte actif / Personnel » ;
- le Makolo Mark central reste une action et reçoit une affordance tactile explicite (cible circulaire, contour violet, ripple/haptic) sans devenir un cinquième onglet.

## 5. Sync, outbox et deux axes d'état

A1 ne crée ni `/api/v1/mobile/` ni `/sync/`.

Le bootstrap/pull minimal utilise :

- `personal.now` → `GET /api/v1/me/now/` ;
- `personal.ongoing` → `GET /api/v1/me/ongoing/` ;
- `personal.me` → `GET /api/v1/me/`.

Le moteur applique la réponse au store avant que l'UI ne la voie. Les erreurs de source sont conservées dans `sync_sources` et l'ancienne projection utile reste disponible.

L'outbox porte identité d'opération, Profile, installation locale, owner, intention stable, idempotence owner éventuelle et politique de replay. Une opération `no-blind-retry` ambiguë devient `awaiting_confirmation` au lieu d'être rejouée automatiquement.

Le lifecycle déclenche un refresh au démarrage de l'expérience authentifiée, au resume et au retour d'un signal réseau. `connectivity_plus` n'est jamais considéré comme une preuve que le serveur est réellement joignable.\n\nA1 expose également une commande de refresh explicite via `SyncRefreshScope`. Le shell l'utilise pour le pull-to-refresh sans vider le contenu local. Toucher un onglet ne déclenche pas cette commande : navigation = retrouver ; pull-to-refresh = demander le plus récent ; resume = vérifier discrètement.

L'UI distingue deux axes indépendants :

```text
contenu : initial | loading | content | empty | success | error
sync    : synced | syncing | pending | offline | conflict | failed
```

La fondation accepte également `stale` comme indication de fraîcheur de présentation lorsque la donnée locale reste utile. `NetworkStateIndicator` représente sobrement les états sync et l'outbox, sans exposer les termes techniques du stockage.

## 6. Behavior primitives

A1 fournit des primitives réutilisables, sans métier A2/A3 :

- `MakoloLoadingState` pour les attentes ponctuelles ;
- `MakoloSkeleton` pour un chargement initial perceptible ;
- `MakoloEmptyState` ;
- `MakoloErrorState` avec message de conservation et retry ;
- `OfflineBanner` ;
- `InlineMessage` ;
- `NetworkStateIndicator` ;
- `SuccessFeedback` distinguant « Enregistré sur cet appareil », « En attente de synchronisation », « Synchronisé » et « Confirmé » ;
- `showMakoloToast` et `UndoToast` reposant sur la fondation `MakoloNotice`, avec icône + texte + Semantics ;
- `ConfirmationDialog` pour les décisions destructives/sensibles ;
- bottom sheet générique ;
- `PermissionExplainer`, y compris l'état refusé, sans demander de permission OS au lancement ;
- `MakoloHaptics`, couche fine pour sélection/succès/avertissement ;
- `NotificationRouter`, fondation de routing qui réutilise `DeepLinkResolver` sans push réel.

Ces primitives représentent les faits ; elles n'en deviennent pas propriétaires.

## 7. Loading, feedback et erreurs

Un refresh ne remplace pas le contenu local par un spinner. Le store local reste la source de lecture, tandis que l'état `syncing` est présenté séparément par une notice légère « Mise à jour… ». Un échec conserve le contenu et affiche « Impossible de mettre à jour pour le moment. » ; le mode hors connexion conserve lui aussi le contenu disponible.

Le chargement initial d'une projection inconnue utilise un skeleton. A1 ne force aucun délai artificiel pour l'afficher.

Un succès définitif n'est jamais affiché uniquement parce qu'une opération est entrée dans l'outbox. Les libellés distinguent le stockage local, l'attente de sync et la confirmation réelle.

Une erreur importante reste persistante et récupérable : elle explique ce qui n'a pas fonctionné, ce qui reste conservé et fournit un prochain geste lorsque possible. Les erreurs de champ restent destinées à une présentation inline dans les futures surfaces métier.

## 8. Continuité locale et connectivité

Après bootstrap réussi :

```text
contenu local + réseau absent
= contenu conservé + état Hors connexion
```

Le réseau dégradé ne déclenche pas un écran bloquant si les données utiles existent déjà.

Au premier lancement sans projection locale, l'application garde l'identité Makolo et explique qu'une première connexion est nécessaire.

Le retour depuis l'arrière-plan conserve la route courante et lance un refresh discret. Le Makolo Mark utilise `push` afin que le back système revienne au contexte précédent.

## 9. Motion, haptics et accessibilité

`MakoloMotion.effective` et les nouvelles primitives lisent `MediaQuery.disableAnimations`. Avec Reduce Motion, la durée fonctionnelle peut devenir nulle ; A1 n'ajoute ni bounce, ni parallaxe, ni animation spectaculaire du Mark.

Les cibles principales restent au moins à la taille tactile prévue par Flutter/Material. Les contrôles importants portent des labels Semantics. Les états réseau ne sont pas transmis uniquement par la couleur : icône et texte les accompagnent.

Les tests ciblés couvrent text scaling, Semantics, Reduce Motion, bottom sheet/back, permission explainer, états réseau ainsi que login valide/invalide, conservation de saisie, double submit, visibilité du mot de passe, inscription, récupération neutre, logout dégradé, changement de compte et SessionRecovery.

## 10. Navigation primaire

La structure A1 fermée est :

```text
Now | Découvrir | [Makolo Mark] | En cours | Moi
```

Le shell utilise `StatefulShellRoute.indexedStack` : changer d'onglet retrouve la branche existante, son état local et son scroll au lieu de recréer l'expérience. Toucher un onglet ne déclenche pas un refresh. Le Mark reste une action centrale et non un cinquième onglet ordinaire ; il utilise `push` afin que le back revienne à l'origine réelle.

Les headers A1 sont contextuels :

- Now : Makolo | Conversations | Notifications | Avatar ;
- Découvrir : Makolo | Recherche | Filtres | Avatar ;
- Mark : Makolo | Avatar ;
- En cours : En cours | Calendrier | Avatar ;
- Moi : Moi | Avatar.

Les pages secondaires utilisent retour + titre naturel + actions contextuelles uniquement. Search/Filtres/Calendrier restent des structures propres tant que leur profondeur métier n'est pas livrée.

L'Avatar ouvre une bottom sheet compacte, distincte de Moi. Elle expose l'identité active, l'activation Profile dérivée lorsqu'elle est disponible, le contexte personnel, le changement de compte et la déconnexion via les contrats Auth A1. Aucun catalogue de domaines métier n'est ajouté au menu ; Membership n'accorde jamais implicitement d'autorité.

Aucun texte visible ne mentionne A1, A2, « projection locale », owner-scoped, outbox ou schema.

## 11. Stockage et confidentialité

- tokens : secure storage uniquement ;
- DB : sandbox privé, isolée par Profile ;
- cache : reconstructible et supprimable ;
- fichiers privés : sandbox applicatif ;
- export : aucune sortie implicite vers Galerie/Files ;
- AccessCredential/Payment secrets : aucune persistance A1 prévue ;
- aucun token, QR, credential ou payload sensible n'est loggé par le code A1.

Sur Android, le host natif A1 désactive les sauvegardes applicatives afin de ne pas restaurer aveuglément sessions, outbox ou données privées sur un nouvel appareil.

## 12. Android / iOS

L'identité Android approuvée est :

```text
applicationId = com.makolo
namespace     = com.makolo
```

Le host Android vit sous `mobile/android/` et suit les templates Flutter 3.47.3 : Gradle 9.3.1, Android Gradle Plugin 9.1.0, Kotlin 2.4.0 et Java 17.

Le build debug Android est un gate A1. La signature de production reste hors de portée. L'identité iOS reste non définie ; aucun `PRODUCT_BUNDLE_IDENTIFIER` n'est inventé.

## 13. CI et bêta

La CI mobile reste séparée :

- `Mobile CI` : resolve, génération Drift, vérification du code généré, format, analyse, tests ;
- `Mobile Android Build` : compilation Android uniquement lorsque le host, les dépendances ou le toolchain le justifient, ou sur déclenchement manuel ;
- `Mobile APK` : packaging APK manuel/checkpoint.

PythonAnywhere reste uniquement un environnement temporaire de test/bêta. La fermeture A1 requiert encore, sur le commit final de cette branche, CI verte puis APK/smoke ciblé contre `https://makolo.pythonanywhere.com`.

## 14. Limites connues / handoff A2

A1 ne livre pas :

- les expériences personnelles complètes ;
- push notification réel ;
- caméra, GPS ou uploads profonds ;
- scanner / autorité terrain déléguée avancée ;
- OfflineGrant générique, Capacity ou Access autoritatifs sans owner joignable ;
- identité/host iOS.

A2 peut construire les expériences personnelles complètes sans remplacer auth, Drift, isolation Profile, repositories, client HTTP, refresh JWT, sync owner-scoped, outbox, routing, SessionRecovery, états réseau, feedback, motion, accessibilité ou interaction mobile.

Le critère de sortie de cette branche reste : tous les tests/CI requis et le smoke bêta doivent être verts avant de déclarer A1 fermé.
