# A1 — Installed Makolo Core

> Statut : implémentation A1 en validation
>
> Base de départ : `main@015e4681d5a0473c77a9650999fb2cff539500b7`
>
> Branche : `mobile/a1-installed-makolo-core`

## 1. Objet

A1 transforme le contrat A0 en fondation Flutter réellement local-first :

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

Une donnée déjà synchronisée est lue depuis le store local. Le réseau ne devient pas une dépendance de rendu écran par écran.

## 2. Stack retenue

| Capacité | Choix A1 | Raison |
| --- | --- | --- |
| Flutter | 3.47.3 | patch stable fixé par A0 |
| Dart | 3.13.3 via Flutter | toolchain A0 |
| State/DI | Riverpod 3.4.3 | orchestration/injection, jamais store durable |
| Routing | go_router 18.0.1 | navigation structurée et reprise |
| HTTP | http 1.6.0 | client minimal encapsulé par Makolo |
| DB | Drift 2.35.0 + drift_flutter 0.3.1 | transactions, migrations, requêtes locales |
| Secrets | flutter_secure_storage 11.2.0 | Keychain/Keystore |
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

## 4. Authentification

Le client réutilise exclusivement les routes Accounts existantes :

- `POST /api/v1/accounts/auth/login/` ;
- `POST /api/v1/accounts/auth/refresh/` ;
- `POST /api/v1/accounts/auth/logout/` ;
- `GET /api/v1/accounts/auth/me/`.

Access et refresh sont stockés ensemble dans une seule valeur de secure storage afin de remplacer atomiquement la paire lors d'une rotation.

Les refresh concurrents sont sérialisés par un single-flight. Une session distante devenue invalide supprime les credentials actifs mais ne supprime ni DB, ni drafts, ni outbox : l'utilisateur revient à l'authentification et retrouve son contexte local après reconnexion.

## 5. Sync et outbox

A1 ne crée ni `/api/v1/mobile/` ni `/sync/`.

Le bootstrap/pull minimal utilise :

- `personal.now` → `GET /api/v1/me/now/` ;
- `personal.ongoing` → `GET /api/v1/me/ongoing/` ;
- `personal.me` → `GET /api/v1/me/`.

Le moteur applique la réponse au store avant que l'UI ne la voie. Les erreurs de source sont conservées dans `sync_sources` et l'ancienne projection utile reste disponible.

L'outbox porte identité d'opération, Profile, installation locale, owner, intention stable, idempotence owner éventuelle et politique de replay. Une opération `no-blind-retry` ambiguë devient `awaiting_confirmation` au lieu d'être rejouée automatiquement.

Le lifecycle déclenche un refresh au démarrage de l'expérience authentifiée, au resume et au retour d'un signal réseau. `connectivity_plus` n'est jamais considéré comme une preuve que le serveur est réellement joignable.

## 6. UX foundation

La navigation primaire est :

```text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
```

Le Mark est une action centrale et utilise les SVG canoniques copiés depuis `static/brand/`.

A1 branche une verticale réelle sur les projections personnelles déjà persistées. Les expériences complètes restent A2.

Primitives déjà livrées :

- loading ;
- empty ;
- error ;
- offline banner ;
- inline message ;
- feedback/pending représentable par les états locaux ;
- taille tactile minimale ;
- sémantique des destinations ;
- fondation Reduce Motion.

## 7. Stockage et confidentialité

- tokens : secure storage uniquement ;
- DB : sandbox privé, isolée par Profile ;
- cache : reconstructible et supprimable ;
- fichiers privés : sandbox applicatif ;
- export : aucune sortie implicite vers Galerie/Files ;
- AccessCredential/Payment secrets : aucune persistance A1 prévue ;
- aucun token, QR, credential ou payload sensible n'est loggé par le code A1.

La configuration de backup OS ne peut pas encore être figée sans les hôtes natifs officiels.

## 8. Android / iOS

Le dépôt courant et A0 ne définissent toujours aucun `applicationId` Android ni `PRODUCT_BUNDLE_IDENTIFIER` iOS.

A1 n'invente donc aucun identifiant permanent et ne génère pas des hôtes portant `com.example.makolo`.

Cette absence est un blocker explicite pour déclarer un build Android/iOS installable. Elle doit être résolue par une identité native approuvée conformément à A0 avant fermeture complète du gate « application installée ».

## 9. CI

Le workflow `.github/workflows/mobile-ci.yml` est filtré sur le mobile et les contrats mobiles. Il exécute :

```text
flutter pub get
dart run build_runner build --delete-conflicting-outputs
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

Les workflows backend génériques CI, Conversations PostgreSQL, Funding PostgreSQL et Beta seed ignorent désormais les changements strictement mobiles. Les workflows de sécurité transversaux restent actifs.

## 10. Handoff A2

A2 doit pouvoir construire les expériences complètes Maintenant, Découvrir, Mark, En cours, Moi et Avatar sans remplacer :

- auth ;
- Drift ;
- isolation Profile ;
- repositories ;
- client HTTP ;
- refresh JWT ;
- sync owner-scoped ;
- outbox ;
- routing ;
- tokens visuels.

A5 peut ajouter plus tard l'autorité offline sensible sans remplacer ce moteur local-first.
