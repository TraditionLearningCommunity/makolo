# Android Discovery — test local après correction (19 octobre 2026)

## Périmètre et état

Branche de correction : `fix/android-discovery-beta-visible-errors-20261019`.

Base : `fix/discover-a-continuation-context-20261014` / PR #522, pas le `main` historique.

Ce chantier ne déclare pas la panne observée sur le téléphone définitivement résolue. Le parseur Flutter n'a pas été exécuté sur un téléphone depuis cet environnement. Les traces de phases permettent de localiser l'échec réel au lieu de masquer les exceptions.

Les modifications ciblent : restauration locale non bloquante, écriture locale post-réponse non bloquante, délai maximum de la requête publique, erreurs typées visibles, tests du contrat et fixtures Django réconciliées. Aucune nouvelle migration ni nouveau modèle.

## 1. Récupérer les commits (PowerShell)

Ne pas effacer un répertoire contenant du travail local non commité.

```powershell
cd D:\Projects\makolo
git status --short
git fetch origin
git switch --track origin/fix/android-discovery-beta-visible-errors-20261019
git log -5 --oneline
```

Si la branche existe déjà localement, utiliser `git switch fix/android-discovery-beta-visible-errors-20261019` puis `git pull --ff-only`. Cette branche dérive de #522 ; les modifications de #522 sont présentes, sans fusion avec main.

## 2. Tests serveur ciblés

```powershell
$env:DJANGO_ENV = "test"
python manage.py check
python manage.py test discovery.api.test_projections discovery.test_presentation_contract core.tests
```

Une autre session lance le serveur local :

```powershell
cd D:\Projects\makolo
python manage.py migrate
python manage.py runserver 0.0.0.0:9999
```

Capturer la réponse exacte attendue par l'APK (12 résultats, et non la page 20 du navigateur historique) :

```powershell
Invoke-WebRequest "http://127.0.0.1:9999/api/v1/discovery/items/?page=1&page_size=12" -OutFile "$env:TEMP\discovery-page12.json"
```

Ne pas partager les éventuelles coordonnées, tokens, descriptions privées ni les fichiers de logs bruts.

## 3. Tests Flutter ciblés

Depuis `D:\Projects\makolo\mobile` :

```powershell
flutter pub get
dart run build_runner build --delete-conflicting-outputs
dart format lib/features/guest/guest_screen.dart test/guest_router_test.dart test/discovery_wire_test.dart
flutter test test/guest_router_test.dart test/discovery_wire_test.dart test/progressive_search_coordinator_test.dart
flutter analyze
```

La version du SDK attendue par le dépôt est Flutter 3.47.3 / Dart 3.13.3. Conserver toute erreur de compilation, de formatage ou de test ; corriger la cause au lieu d'enlever le test.

## 4. Exécuter sur un téléphone physique

Ne pas modifier ni committer `mobile/config/dev.json` pour rediriger la connexion vers Django local : le fichier est la configuration de développement partagée. Construire plutôt un fichier temporaire en dehors du dépôt.

Via USB + débogage USB (option recommandée pour éviter de divulguer une adresse LAN) :

```powershell
cd D:\Projects\makolo\mobile
adb devices
adb reverse tcp:9999 tcp:9999
$cfg = Get-Content ".\config\dev.json" -Raw | ConvertFrom-Json
$cfg.MAKOLO_API_BASE_URL = "http://127.0.0.1:9999/"
$localConfig = Join-Path $env:TEMP "makolo-local-android.json"
[System.IO.File]::WriteAllText($localConfig, ($cfg | ConvertTo-Json -Depth 12), ([System.Text.UTF8Encoding]::new($false)))
flutter run --debug --flavor dev --dart-define-from-file="$localConfig"
```

Le manifeste Android `debug` autorise temporairement le HTTP local. Le même mécanisme n'est pas une configuration de production.

Alternative Wi-Fi : remplacer dans le fichier temporaire uniquement `MAKOLO_API_BASE_URL` par `http://ADRESSE_LAN_DU_PC:9999/`; le téléphone et le PC doivent communiquer sur le même réseau et le pare-feu doit autoriser le port 9999.

Pour installer une APK fraîche :

```powershell
flutter build apk --debug --flavor dev --dart-define-from-file="$localConfig"
adb install -r ".\build\app\outputs\flutter-apk\app-dev-debug.apk"
```

## 5. Traces à obtenir

Dans les logs Flutter Debug, rechercher le préfixe `[DISCOVERY_PUBLIC]` :

```text
RESTORE_BEGIN
RESTORE_DONE / RESTORE_ERROR
SEARCH_SCHEDULED
SEARCH_START revision=N
API_REQUEST_START revision=N
API_RESPONSE revision=N status=200 chars=...
WIRE_OK / WIRE_OR_SELECT_ERROR
SELECT_OK revision=N items=...
REVISION_ACCEPTED / REVISION_DISCARDED
LOAD_FINISHED revision=N state=...
FRAME_BUILT revision=N
```

Ces logs ne contiennent volontairement ni texte de recherche, ni coordonnées, ni token, ni contenu JSON. La pile d'exception est imprimée uniquement dans les builds Debug. Les erreurs HTTP et de contrat deviennent des états visibles avec **Réessayer**. La restauration ou l'écriture locale en défaut devient une alerte non bloquante.

Scénarios indispensables : Découvrir invité avant connexion ; première page ; filtre Voyager ; recherche tapée rapidement ; changer de filtre pendant une requête ; retour depuis une fiche ; actualisation ; recherche vide ; téléphone hors ligne ; relance après fermeture ; version APK confirmée.

## 6. Limites et réception

- Aucun test d'appareil réel n'est exécuté automatiquement par ce patch.
- La réponse Django et le JSON historique de page_size 20 ne sont pas des preuves suffisantes pour le client page_size 12.
- Les problèmes distincts de qualité des données, confidentialité des descriptions publiques et habilitation native Services doivent être jugés sur les propriétaires et les données réellement consommées.
- Les échecs Playwright hors parcours corrigé restent visibles ; ne pas mettre une PR dans main avec une CI rouge.
