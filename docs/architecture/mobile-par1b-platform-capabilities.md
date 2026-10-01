# Makolo Mobile — PAR-1B Platform Capabilities & Background Location

**Checkpoint :** PAR-1B  
**Base de départ vérifiée :** `main@b4ea00b1a7cf8981d105140464d9751338a510ef`  
**Portée :** frontières appareil/natives Android et runtime Location.  
**Hors portée :** Firebase/FCM, notifications globales, Workmanager bootstrap, Sentry bootstrap, Home Widget, ingress global, navigation globale, iOS et redesign des features.

## 1. Frontière

PAR-1B conserve la direction suivante :

```text
feature
  ↓
frontière Makolo
  ↓
platform capability
  ↓
plugin Flutter / Android
```

Les features ne configurent pas directement Geolocator, MapLibre, Camera, ImagePicker, FilePicker, MobileScanner, permission_handler, local_auth, share_plus ou url_launcher.

Une permission Android reste une capacité appareil. Elle n'est jamais une `Permission` ou un `Mandate` Makolo.

Une observation GPS reste une `LocationFix`. Elle n'est jamais automatiquement `Placement`, `Geography`, une preuve d'arrivée ni une preuve d'Access.

## 2. Location : quatre intentions

### ONCE

`LocationCapability.current()` acquiert une position ponctuelle avec `locationWhenInUse`, vérifie que le service de localisation est actif, puis demande un fix au `LocationService`.

Aucun stream durable n'est créé.

### FOREGROUND WATCH

`LocationCapability.foregroundWatch()` démarre un stream explicitement stoppable. L'ancien alias `watch()` est conservé pour compatibilité et délègue à ce mode.

Le `LocationWatchHandle.stop()` est idempotent et annule sa souscription.

### BACKGROUND SESSION

`LocationCapability.startBackgroundSession()` crée une session explicite et unique.

Contrat :

1. vérifier d'abord `backgroundCapabilityEnabled` ;
2. obtenir `locationWhenInUse` ;
3. obtenir ensuite `locationAlways` ;
4. vérifier le service Location ;
5. démarrer le stream Android avec foreground notification ;
6. conserver un seul handle de session.

Un second `startBackgroundSession()` réutilise la session active au lieu de démarrer un deuxième moteur GPS. `stopBackgroundSession()` est idempotent. Une erreur de démarrage ou de stream nettoie la session afin qu'aucune session fantôme ne reste active.

### AMBIENT / LOW-COST CONTEXT

L'ambient n'est pas un scheduler ni un geofence. Il s'agit d'un profil de tracking moins coûteux pouvant être utilisé lorsqu'une surface a besoin de contexte sans tracking actif haute précision.

Aucun historique GPS n'est persisté automatiquement.

## 3. Profils énergie

Le runtime expose trois profils de tracking :

| Profil | Accuracy | Distance filter | Intervalle indicatif | Usage |
|---|---|---:|---:|---|
| `ambient` | low | 250 m | 2 min | contexte faible coût |
| `balanced` | medium | 50 m | 30 s | suivi normal |
| `active` | high | 10 m | 5 s | Jour J / déplacement / opération active |

Ces valeurs sont des defaults techniques du runtime, pas des vérités métier ni des knobs d'environnement.

Une feature choisit une intention/profil. Elle ne construit jamais `AndroidSettings` ou `ForegroundNotificationConfig`.

Le runtime n'impose donc pas `LocationAccuracy.high` en permanence.

## 4. PermissionGateway

`PermissionGateway` distingue désormais :

- `locationWhenInUse` ;
- `locationAlways`.

Le flow background est séquentiel. Une permission déjà accordée n'est pas redemandée.

Les états continuent d'être normalisés sous la frontière Makolo :

- granted ;
- denied ;
- permanentlyDenied → settings required ;
- restricted ;
- limited/provisional lorsque le plugin les expose.

Le service Location produit en plus des états explicites :

- service unavailable ;
- disabled by runtime configuration ;
- failed.

Lorsque `MakoloRuntimeConfig.location.backgroundCapabilityEnabled == false`, aucune vérification ni demande de permission background n'est déclenchée.

## 5. Android background location

Le Manifest applicatif déclare explicitement :

- `ACCESS_COARSE_LOCATION` ;
- `ACCESS_FINE_LOCATION` ;
- `ACCESS_BACKGROUND_LOCATION` ;
- `FOREGROUND_SERVICE` ;
- `FOREGROUND_SERVICE_LOCATION`.

Le service Android lui-même reste celui fourni par `geolocator_android`. PAR-1B n'ajoute aucun `Service` Android custom.

Le foreground service reçoit une notification technique stable :

```text
Makolo — action en cours
Localisation active pour poursuivre cette action.
```

Cette notification indique un tracking technique actif. Elle ne prétend pas qu'une Journey, un Access ou une action métier est accomplie.

## 6. Limites Android

Le runtime ne promet pas une exécution illimitée.

En particulier :

- Android peut suspendre ou terminer le process ;
- un force-stop utilisateur n'est pas contourné ;
- les restrictions de démarrage d'un foreground service restent celles de la plateforme ;
- une permission retirée ou un service Location désactivé peut interrompre le stream ;
- Workmanager n'est pas utilisé pour simuler un tracking continu.

Le démarrage de la session doit intervenir depuis une action/surface appropriée pendant que l'application possède les prérequis nécessaires.

PAR-1C reste propriétaire du Workmanager général et des services runtime non Location.

## 7. Maps

`MakoloMapView` reste l'encapsulation brute de MapLibre.

`ConfiguredMakoloMapView` ajoute la consommation de `MakoloMapsConfig` fournie par PAR-1A :

```text
MakoloRuntimeConfig.maps
  ↓
ConfiguredMakoloMapView
  ↓
MakoloMapView
  ↓
MapLibre
```

États runtime explicites :

- `disabled` lorsque Maps est désactivé ;
- `loading` pendant le chargement du style ;
- `ready` lorsque le style est chargé ;
- `error` lorsqu'aucun style n'est configuré ou que le chargement dépasse la fenêtre technique.

Le fallback est fourni par l'appelant ; la donnée géographique déjà acquise n'est ni supprimée ni transformée.

Aucune URL OpenFreeMap, OSM, MapTiler, Mapbox ou autre fournisseur n'est codée en dur. Le style reste entièrement fourni par la configuration PAR-1A.

## 8. Camera

Audit conservateur : `IntegratedCamera` / `IntegratedCameraSession` encapsulent déjà `camera`.

Le wrapper couvre :

- sélection de lens avec fallback ;
- preview ;
- photo ;
- démarrage/arrêt vidéo ;
- audio optionnel ;
- dispose.

`CameraController` ne fuit pas dans les features. Aucun refactor n'est nécessaire dans PAR-1B.

## 9. Media Picker

`SystemMediaPicker` reste distinct de la caméra intégrée.

`ImagePickerSystemMediaPicker` couvre :

- image ;
- vidéo ;
- capture système ;
- gallery ;
- récupération Android d'une sélection interrompue.

Aucun doublon de `IntegratedCamera` n'est créé.

## 10. Files

`SystemFilePicker` reste la frontière `file_picker`.

Avec `file_picker` 13.x, `pickFiles()` est déjà l’opération de sélection multiple ; `pickFile()` est l’opération mono-fichier. `NativeFileAcquisitionCoordinator` continue de copier les octets dans le staging privé `ProfileFileStore` et nettoie les fichiers déjà acquis si un lot échoue partiellement.

Invariants :

```text
bytes locaux
!= Resource
!= Proof
!= Credential
!= JourneyArtifact
```

Le File Kernel n'est pas reconstruit.

## 11. Scanner

`MakoloCodeScanner` n'expose plus `MobileScannerController`.

Le plugin reste entièrement encapsulé dans `platform/scanner`.

Le chemin demeure :

```text
code lu
→ ScannedCode
→ StructuredDestination éventuelle
→ IncomingIntent
```

Un QR ne crée ni ne valide un Access.

## 12. QR renderer

`MakoloQrView` reste presentation-only.

Le domaine propriétaire fournit le payload. Le renderer ne crée pas de credential, ne décide pas de sa validité, ne le persiste pas et ne le log pas.

## 13. Sharing

`ShareGateway` / `SystemShareGateway` restent la frontière pour :

- texte ;
- fichiers ;
- URI externe.

Les erreurs restent visibles au caller via les Futures/retours existants ; elles ne sont pas transformées en faux succès.

La frontière n'ajoute jamais automatiquement des données privées dans une URL.

## 14. Biométrie

`LocalProtection` / `LocalAuthProtection` restent la frontière `local_auth`.

Le host Android courant utilise `FlutterFragmentActivity`, compatible avec cette intégration. Le Manifest ajoute `USE_BIOMETRIC`.

La biométrie n'est pas déclenchée au bootstrap global et ne devient jamais Permission, Mandate, Access ou Trust.

## 15. Façade B-owned

PAR-1B ne crée pas de `DevicePlatformCapabilities` global supplémentaire.

Les frontières existantes sont déjà petites, nommées et testables. Ajouter une façade uniquement pour regrouper des objets non encore composés créerait une abstraction spéculative et augmenterait la collision avec le wiring PAR-1C.

L'intégrateur final peut composer B + C lorsqu'un besoin concret de runtime commun existe.

## 16. Wiring central

Le seul hotspot central touché est `mobile/lib/app/providers.dart`.

Le changement est volontairement minimal : le `LocationCapability` existant reçoit `config.location.backgroundCapabilityEnabled`.

Aucune restructuration de providers, router ou main n'est effectuée.

## 17. Ce qui reste à PAR-1C

PAR-1B ne touche pas :

- Firebase bootstrap ;
- FCM ;
- notifications globales ;
- Workmanager bootstrap ;
- Sentry bootstrap ;
- Home Widget runtime ;
- push ingress ;
- app lifecycle global.

## 18. Ce qui reste à l'intégrateur

L'intégrateur final pourra :

- composer les capabilities B avec les services C ;
- brancher `ConfiguredMakoloMapView` dans les surfaces qui doivent réellement afficher MapLibre ;
- sélectionner les profils Location selon les scénarios produit autorisés ;
- résoudre les éventuels conflits de wiring centraux avec PAR-1C/D.

Aucune feature n'est redesignée dans PAR-1B.

## 19. Validation attendue

Commandes de référence :

```bash
cd mobile

dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test test/location_capability_test.dart
flutter test test/map_runtime_test.dart
flutter test test/native_file_acquisition_test.dart
flutter test --exclude-tags golden
flutter build apk --debug --flavor dev --dart-define-from-file=config/dev.json
```

Le manifest merger du build Android doit conserver le service `GeolocatorLocationService` du plugin avec son type `location`.

Aucun secret, provider URL ni credential ne doit être ajouté au dépôt.
