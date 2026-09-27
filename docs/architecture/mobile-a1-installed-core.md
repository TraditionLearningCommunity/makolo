# A1 — Installed Makolo Core

> Statut : A1 Behavior Closure en validation
>
> Base du dernier audit : `main@993e17d64372dea2d4da36c5c3274e5df378cb89`
>
> Branche de fermeture : `mobile/a1-behavior-closure`
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

Une donnée déjà synchronisée est lue depuis le store local. Le réseau sert au bootstrap, au rafraîchissement, à la synchronisation, à la confirmation et aux opérations intrinsèquement distantes. Il ne remplace pas le contenu local utile par un écran vide lorsque la connectivité change.

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

- `POST /api/v1/accounts/auth/login/` ;
- `POST /api/v1/accounts/auth/refresh/` ;
- `POST /api/v1/accounts/auth/logout/` ;
- `GET /api/v1/accounts/auth/me/`.

Access et refresh sont stockés ensemble dans une seule valeur de secure storage afin de remplacer atomiquement la paire lors d'une rotation. Les refresh concurrents sont sérialisés par un single-flight.

Une session distante invalide retire les credentials actifs sans supprimer la DB, les drafts ni l'outbox. Le contrôleur `SessionRecoveryController` conserve la dernière route utile en mémoire de processus, demande la reconnexion puis restaure cette route une seule fois après authentification. Il ne transforme pas cet état de navigation en vérité métier persistante. Toute opération sensible reste revalidée par son owner serveur.

Les erreurs d'authentification visibles sont traduites en messages sûrs ; aucun détail backend brut, JWT ou payload privé n'est présenté.

## 5. Sync, outbox et deux axes d'état

A1 ne crée ni `/api/v1/mobile/` ni `/sync/`.

Le bootstrap/pull minimal utilise :

- `personal.now` → `GET /api/v1/me/now/` ;
- `personal.ongoing` → `GET /api/v1/me/ongoing/` ;
- `personal.me` → `GET /api/v1/me/`.

Le moteur applique la réponse au store avant que l'UI ne la voie. Les erreurs de source sont conservées dans `sync_sources` et l'ancienne projection utile reste disponible.

L'outbox porte identité d'opération, Profile, installation locale, owner, intention stable, idempotence owner éventuelle et politique de replay. Une opération `no-blind-retry` ambiguë devient `awaiting_confirmation` au lieu d'être rejouée automatiquement.

Le lifecycle déclenche un refresh au démarrage de l'expérience authentifiée, au resume et au retour d'un signal réseau. `connectivity_plus` n'est jamais considéré comme une preuve que le serveur est réellement joignable.

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
- toast léger et `UndoToast` uniquement pour une action réellement réversible ;
- `ConfirmationDialog` pour les décisions destructives/sensibles ;
- bottom sheet générique ;
- `PermissionExplainer`, y compris l'état refusé, sans demander de permission OS au lancement ;
- `MakoloHaptics`, couche fine pour sélection/succès/avertissement ;
- `NotificationRouter`, fondation de routing qui réutilise `DeepLinkResolver` sans push réel.

Ces primitives représentent les faits ; elles n'en deviennent pas propriétaires.

## 7. Loading, feedback et erreurs

Un refresh ne remplace pas le contenu local par un spinner. Le store local reste la source de lecture, tandis que l'état `syncing` est présenté séparément.

Le chargement initial d'une projection inconnue utilise un skeleton. A1 ne force aucun délai artificiel pour l'afficher.

Un succès définitif n'est jamais affiché uniquement parce qu'une opération est entrée dans l'outbox. Les libellés distinguent le stockage local, l'attente de sync et la confirmation réelle.

Une erreur importante reste persistante et récupérable : elle explique ce qui n'a pas fonctionné, ce qui reste conservé et fournit un prochain geste lorsque possible. Les erreurs de champ restent destinées à une présentation inline dans les futures surfaces métier.

## 8. Offline et continuité

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

Les tests ciblés couvrent text scaling, Semantics, Reduce Motion, bottom sheet/back, permission explainer et états réseau.

## 10. Navigation primaire

La structure reste :

```text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
```

Le Mark reste une action centrale et non un cinquième onglet ordinaire. Les destinations structurées restent des placeholders propres tant que leur expérience métier n'est pas construite.

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
- scanner/offline authority avancée ;
- OfflineGrant, Capacity ou Access autoritatifs offline ;
- identité/host iOS.

A2 peut construire les expériences personnelles complètes sans remplacer auth, Drift, isolation Profile, repositories, client HTTP, refresh JWT, sync owner-scoped, outbox, routing, SessionRecovery, états réseau, feedback, motion, accessibilité ou interaction mobile.

Le critère de sortie de cette branche reste : tous les tests/CI requis et le smoke bêta doivent être verts avant de déclarer A1 fermé.
