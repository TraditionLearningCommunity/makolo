# Découvrir — Sharing mobile et liens de Possibilité

Cette note décrit le raccordement **existant** entre `sharing.services`, l'API
`/api/v1/sharing/`, le menu N1 Flutter et la destination N2. Elle ne crée ni
domaine de production, ni fournisseur de partage tiers, ni secret.

## Contrat fonctionnel

- **Dans Makolo** : recherche limitée aux Profils actifs et recherchables,
  authentification requise, envoi via `ShareDelivery`, notification existante,
  contrôle du destinataire à l'ouverture. Une livraison n'est pas un Access,
  une Permission ou une opération métier.
- **À l'extérieur** : lien créé par `ShareLink` et jeton opaque, transmis par
  la feuille système `share_plus` (applications installées : Mail, WhatsApp,
  Facebook, etc.), copie ou QR. Aucun SDK Facebook n'est nécessaire pour ce
  scénario de partage de lien.
- **Ouverture** : `/s/<token>/` garde son landing Web lorsqu'il n'y a pas
  d'application ; si Android vérifie le domaine et ouvre l'application, le
  client appelle `GET /api/v1/sharing/resolve/<token>/` et navigue vers
  `/discover/items/<family>/<id>`. Les liens expirés/révoqués/non publics ne
  donnent pas de destination.
- **Livraison interne** : `/shares/<delivery-id>/` exige une session du
  destinataire ; Flutter utilise `GET /api/v1/sharing/deliveries/<id>/`,
  puis ouvre N2. Un autre compte reçoit 403.
- Le serveur ne délègue pas ses décisions d'autorité au client.
- Les actions propriétaires (inscription, paiement, réservation) ne sont
  jamais exécutées par Sharing.

## Configuration Android à fournir avec les identités réelles

Le projet contient déjà les variables de release suivantes :

- Backend Django : `MAKOLO_PUBLIC_BASE_URL` (origine publique HTTPS).
- Flutter : `MAKOLO_APP_LINKS_ENABLED`,
  `MAKOLO_APP_LINKS_SCHEME`, `MAKOLO_APP_LINKS_HOST`.
- Build Gradle : `MAKOLO_ANDROID_APP_LINK_SCHEME`,
  `MAKOLO_ANDROID_APP_LINK_HOST`.
- Signature : `mobile/android/key.properties` local ou
  `MAKOLO_ANDROID_KEYSTORE_*` existantes (jamais commitées).
- Identités Android effectives :
  `com.makolo.dev`, `com.makolo.beta`, `com.makolo` selon la flavor.

Le host du build, celui du runtime Flutter, l'origine de
`MAKOLO_PUBLIC_BASE_URL` et le domaine réellement contrôlé doivent
correspondre. Le serveur du domaine publiera une réponse HTTPS **non redirigée**
à `/.well-known/assetlinks.json` avec le package réel et l'empreinte SHA-256
de la signature installée, puis vérifiera l'association avec les outils
Android. Aucun package/fingerprint n'est ajouté arbitrairement à ce dépôt.

Pour connaître l'empreinte de la clé du build concerné, utiliser `keytool`
sur le keystore réel dans un environnement sécurisé ; ne jamais publier le
keystore, les mots de passe, les propriétés de signature ou une clé privée.

Le manifest Android contient le filtre HTTPS pour `/s/` et `/shares/`.
Les builds DEV sans host confirmé utilisent intentionnellement un domaine
`.invalid` non vérifiable. Cela permet de compiler localement sans prétendre
que l'association de production est effective.

**iOS** : le host iOS et ses entitlements ne sont pas fournis dans le dépôt
mobile courant. Les Universal Links exigent un App ID et un Team ID réels,
`Associated Domains` et le fichier
`/.well-known/apple-app-site-association`. Ne pas les remplacer par des
valeurs simulées. À intégrer seulement après disponibilité du host et de
l'identité iOS, avec validation sur appareil.

Un navigateur embarqué dans une application tierce peut choisir d'afficher
la page Web même si Makolo est installé ; ce comportement relève de la
plateforme. L'expérience Web reste donc un fallback à part entière.

## Vérifications

```powershell
cd D:\Projects\makolo
git fetch origin --prune
git switch fix/discover-a-continuation-context-20261014
git pull --ff-only
python manage.py check
python manage.py test sharing.test_discovery_share_api sharing.test_direct sharing.test_p5_hardening
cd mobile
flutter pub get
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter analyze
flutter test test/incoming_intent_test.dart
flutter test test/discovery_mature_screen_test.dart
flutter test test/guest_router_test.dart
```

Sur deux comptes de test : rechercher le destinataire, envoyer, vérifier la
notification et l'ouverture avec le bon compte ; répéter avec un compte tiers
(403), un lien révoqué (404), un Guest et sans l'application installée.
Sur Android signé et domaine vérifié : ouvrir le lien HTTPS dans le navigateur
et via la feuille native depuis plusieurs applications installées.
