# Makolo Mobile — PAR-1A Runtime Configuration & Android Environments

**Checkpoint :** PAR-1A  
**Portée :** configuration runtime et flavors Android uniquement.  
**Base :** `main@8c26e09d94a5012d7c732ebfc0a5955d9a3f075c`.

## Frontière

La configuration suit une seule direction :

```text
config/*.json / --dart-define-from-file
        ↓
MakoloRuntimeConfig
        ↓
platform / runtime services
        ↓
features
```

Les features ne lisent jamais directement une URL, un fournisseur ou une variable d'environnement.

`MakoloRuntimeConfig` vit dans `mobile/lib/app/environment.dart`. `runtimeConfigProvider` l'injecte dans le runtime applicatif et `MakoloApiClient` reçoit uniquement l'URI déjà validée.

## Environnements Android

| Flavor | applicationId | fichier de base |
|---|---|---|
| `dev` | `com.makolo.dev` | `config/dev.json` |
| `beta` | `com.makolo.beta` | `config/beta.json` |
| `prod` | `com.makolo` | `config/prod.json` |

Le `namespace` Kotlin reste `com.makolo`. Changer l'`applicationId` n'exige donc pas de déplacer `MainActivity`.

`config/dev.json` porte désormais les valeurs client réelles de l'environnement DEV approuvé : backend de test PythonAnywhere, style MapLibre/MapTiler DEV, Firebase/FCM, Sentry Flutter et capability de localisation background. App Links reste désactivé. `beta.json` et `prod.json` restent volontairement incomplets tant que leurs valeurs canoniques n'existent pas ; le runtime refuse PROD sans `MAKOLO_API_BASE_URL`.

Pour une surcharge locale ou CI non canonique, copier le fichier de base vers `config/<env>.local.json`. Ces fichiers sont ignorés par Git. Une valeur DEV versionnée doit rester une configuration client distribuable dans l'application ; aucun secret serveur ne doit y entrer.

## Clés runtime

- `MAKOLO_ENVIRONMENT` : `dev`, `beta` ou `prod`.
- `MAKOLO_API_BASE_URL` : URL HTTP(S) Makolo ; optionnelle en DEV/BETA, obligatoire en PROD.
- `MAKOLO_MAPS_ENABLED` + `MAKOLO_MAP_STYLE` : activation et style/configuration MapLibre. Aucun provider n'est codé en dur.
- `MAKOLO_FIREBASE_ENABLED` : déclaration d'activation. PAR-1A n'appelle pas `Firebase.initializeApp`.
- `MAKOLO_SENTRY_ENABLED` + `MAKOLO_SENTRY_DSN` : sélection future entre `SentryCrashReporter` et `NoopCrashReporter`. PAR-1A ne fait pas le bootstrap.
- `MAKOLO_APP_LINKS_ENABLED` + `MAKOLO_APP_LINKS_SCHEME` + `MAKOLO_APP_LINKS_HOST` : contrat runtime. Aucun domaine n'est inventé et aucun intent-filter App Links n'est ajouté tant que la valeur canonique n'existe pas.
- `MAKOLO_BACKGROUND_LOCATION_ENABLED` : capability infrastructurelle destinée au futur moteur PAR-1B. Elle ne crée aucune logique de localisation.

Validation : une capability désactivée n'exige pas ses paramètres. Si elle est activée sans configuration nécessaire, `MakoloConfigurationException` est levée avec un message explicite.

## Commandes

DEV reproductible :

```bash
cd mobile
flutter run --flavor dev --dart-define-from-file=config/dev.json
flutter build apk --debug --flavor dev --dart-define-from-file=config/dev.json
```

BETA, après préparation d'un fichier local explicite :

```bash
cp config/beta.json config/beta.local.json
# renseigner uniquement les valeurs réellement disponibles
flutter build apk --debug --flavor beta --dart-define-from-file=config/beta.local.json
```

PROD, seulement après fourniture des vraies valeurs :

```bash
cp config/prod.json config/prod.local.json
# MAKOLO_API_BASE_URL est obligatoire ; ne rien inventer
flutter build appbundle --release --flavor prod --dart-define-from-file=config/prod.local.json
```

Ce dernier build n'implique pas qu'une release store soit prête : le signing production reste hors PAR-1A et n'est pas inventé.

## Firebase Android

Le projet Firebase DEV réel est maintenant raccordé via les source sets de flavor standards :

```text
mobile/android/app/src/dev/google-services.json
mobile/android/app/src/beta/google-services.json
mobile/android/app/src/prod/google-services.json
```

`mobile/android/app/src/dev/google-services.json` provient du projet Firebase réel associé à `com.makolo.dev` et est versionné comme configuration client Android. BETA et PROD restent absents tant que leurs projets réels ne sont pas créés. Le plugin Google Services et le bootstrap conditionnel sont fournis par PAR-1C.

`google-services.json` est une configuration client Firebase, pas une clé privée serveur. Ne jamais committer : service-account JSON, clé privée, secret signing, keystore, token serveur ou credential administratif Firebase.

Pour un flavor où Firebase reste désactivé, l'absence du fichier client ne bloque pas le build.

## Maps

`MakoloMapView` reçoit déjà un `styleString` de son appelant. PAR-1A ne change pas cette abstraction.

La configuration fournit `MAKOLO_MAP_STYLE`. Elle peut plus tard désigner un style/provider réellement choisi sans modifier Now, Discovery, Journey ou une autre feature. `MAKOLO_MAPS_ENABLED=true` sans style est rejeté.

Aucune URL OpenFreeMap, MapLibre, OSM ou autre provider n'est ajoutée dans `mobile/lib/features/**`.

## Sentry

L'architecture existante `CrashReporter / NoopCrashReporter / SentryCrashReporter` est conservée. PAR-1A fournit seulement `enabled + dsn`.

Un DSN Sentry est une valeur client et n'est pas assimilé à une clé privée serveur, mais Makolo le garde externe au dépôt tant qu'une politique explicite n'en décide pas autrement. Le DSN client du projet Sentry Flutter DEV est versionné dans `config/dev.json`; il ne confère aucune autorité serveur. Les credentials Sentry administratifs restent interdits.

## App Links

La configuration peut représenter scheme + host, mais la capability est désactivée dans les trois fichiers versionnés. Aucun domaine Makolo canonique n'ayant été établi pour ce checkpoint, le Manifest ne contient pas de faux App Link.

## CI

`Mobile Android Build` construit explicitement `devDebug` avec `config/dev.json`.

`Mobile APK` reste un checkpoint bêta/test : il construit explicitement `betaDebug`, part de `config/beta.json` puis injecte l'URL bêta/test fournie au workflow dans un fichier temporaire non versionné.

La CI n'a besoin d'aucune configuration PROD fictive.

## Sécurité

Configuration client publique potentielle : applicationId, flags de capability, host App Links, style de carte public, DSN client selon politique, configuration Firebase client.

Secrets interdits dans le dépôt et dans les fichiers `dart-define` versionnés : mot de passe, token, clé privée, service account, secret signing, keystore, credential serveur, PII.

## Handoff PAR-1B / PAR-1C

PAR-1B peut consommer `runtimeConfigProvider` pour Maps et background location sans modifier les features.

PAR-1C peut consommer la même configuration pour Firebase/Sentry et sélectionner automatiquement le `google-services.json` du flavor Android. Il ne doit pas déplacer la configuration dans une feature ni créer une seconde architecture d'environnement.
