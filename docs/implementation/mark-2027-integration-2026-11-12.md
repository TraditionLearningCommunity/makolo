# Makolo Mark 2027 — état d'intégration GitHub

**Date :** 12 novembre 2026  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Branche :** `fix/discover-a-continuation-context-20261014` — PR #522  
**Base consultée :** `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f`

## Périmètre et sources

Cette passe porte exclusivement sur les écarts vérifiés du parcours Mark. Sources consultées : `AGENTS.md`, blueprint canonique, contrat Z7, audit de clôture Mark Mature, contrats local-first/Sync/Infrastructure, orchestrateurs personnels et Space, vues Mark Web, écran et repository Mark Flutter, acquisition native, FileRecords/ProfileFileStore, routes Flutter propriétaires et tests.

Le runtime fait foi ; la présence d'une capacité dans l'architecture générale ne prouve pas qu'elle est exposée dans Mark. Aucun nouveau bounded context, modèle, migration, moteur de permissions, service d'intelligence ou endpoint générique n'a été ajouté.

## Capacités et limites constatées

| Capacité | État après cette passe | Source / frontière |
|---|---|---|
| Orchestration déterministe personnelle | Existante, réutilisée | `core/mark_orchestration.py` |
| Orchestration Space | Existante, réutilisée | `organizations/api/space_mark_projection.py` |
| Entrée serveur Mark | Texte uniquement | Les deux APIs annoncent `accepted_input_kinds=["text"]` |
| Texte Flutter, brouillon par acteur | Existant, sérialisation des autosaves ajoutée | `mark_repository.dart`, `DraftRepository` |
| Clarifications Flutter | Options réellement sélectionnables pour les types autorisés | `mark_navigation.dart`, `mark_screen.dart` ; nouveau passage par l'orchestrateur propriétaire |
| Handoffs Flutter | Routes explicitement connues, pas de navigation vers des URLs API | `mark_navigation.dart` ; certains owners restent sans route native vérifiée |
| Confirmation Recognition Flutter | Confirmation owner-backed et clé d'idempotence locale | `mark_repository.dart`, `mark_screen.dart` ; jamais de retry aveugle en résultat ambigu |
| Photo, image, documents | Acquisition et aperçu local ; remise explicite vers le formulaire propriétaire PersonalAsset pour les formats admissibles | `ProfileFileStore`, `DocumentFormScreen.create`, `ResourceRepository.createDocument` ; pas de transfert générique Mark |
| Audio | Enregistrement local, pause/reprise/arrêt/écoute ; dictée native conditionnelle Android, texte éditable | `record`, `just_audio`, Android `SpeechRecognizer`, sans garantie offline ou langue |
| Liens | Collage contrôlé HTTP(S), retrait, brouillon local ; partage Android entrants | Aucune exploration arbitraire, aucun enrichissement serveur prétendu |
| Web personnel | Choix de clarification et confirmation Recognition par formulaires POST/CSRF | `core/mature_experience_views.py`, `templates/core/makolo_mark.html` |
| Space Flutter | Clarification de l'identité/du rôle d'un membre d'équipe, confirmation par owner | `organizations/api/space_mark_projection.py`, `mark_team_member_clarification.dart` ; autorité serveur inchangée |
| Partage système Android | Texte, URL, fichiers routés vers Mark et copiés localement par Profile | `MainActivity.kt`, `system_share_receiver.dart`, `runtime_ingress_listener.dart`, `SharedPayloadCoordinator` ; entrée native conditionnelle |
| Retour après handoff | Retour natif via navigation existante | Restauration exhaustive du contexte de retour non certifiée |
| Profil et Space | Stockages et routes distincts | Changer de contexte ne confère aucun Mandate/Permission |
| LLM | Non requis | Aucun service IA ajouté |

### Règle de transmission explicite

Une photo, un document, un audio ou une URL conservés dans le brouillon ne sont **pas** transmis par `POST /api/v1/me/mark/` ou le Mark Space. Le repository refuse de les présenter comme une soumission multimodale. Lorsque du texte les accompagne, une confirmation explicite permet de traiter **le texte seul** ; les supports restent locaux. Une réponse `completed` pour ce texte ne supprime pas les supports non envoyés.

La proposition multimodale générique de bout en bout n'est donc **pas déclarée mature**. Une remise propriétaire précise existe désormais pour un document personnel : Mark ouvre la création dans Mes documents avec une copie locale séparée, puis le service PersonalAsset accepte ou refuse effectivement l'envoi. Il n'existe toujours pas d'endpoint Mark universel de fichiers, ni de `MarkIntent` ou de `Proof` parallèle.

### Voix : garantie réelle

Le dépôt contient déjà `record`, `just_audio`, la permission microphone et Android `RECORD_AUDIO`. L'enregistrement produit une pièce audio locale bornée à 120 secondes. Une seconde voie facultative appelle le `SpeechRecognizer` du système Android s'il est installé et disponible : les résultats sont visibles, modifiables et ne rejoignent l'intention qu'après choix de l'utilisateur. Cette capacité peut dépendre de la langue, des services et du réseau du téléphone ; elle ne promet aucun fonctionnement offline ni transcription universelle. Sans cette capacité, l'audio local et le texte manuel restent disponibles. Aucun LLM n'est nécessaire.

## Fichiers modifiés / ajoutés

- `mobile/lib/features/mark/mark_navigation.dart` : correspondance sûre vers les routes Flutter et sélection de clarification.
- `mobile/lib/features/mark/mark_repository.dart` : brouillons des références locales, confirmations et états de transport non confirmé.
- `mobile/lib/features/mark/mark_screen.dart` : composer, clarifications, destination, contexte, pièces, photo, audio, URL, confirmations.
- `mobile/lib/features/mark/mark_voice_capture.dart` : capture audio et lecture locales.
- `mobile/lib/features/mark/mark_dictation_capture.dart` : dictée Android native conditionnelle, correction humaine.
- `mobile/lib/features/mark/mark_team_member_clarification.dart` : clarification Space Team.
- `mobile/lib/features/me/me_routes.dart` et `mobile/lib/features/resources/document_form_screen.dart` : passage du fichier Mark au formulaire PersonalAsset.
- `mobile/lib/runtime/runtime_ingress.dart`, `mobile/lib/runtime/runtime_ingress_listener.dart`, `mobile/lib/platform/sharing/system_share_receiver.dart`, `mobile/android/app/src/main/kotlin/com/makolo/MainActivity.kt`, `mobile/android/app/src/main/AndroidManifest.xml` : réception native des partages et dictée.
- `mobile/test/mark_navigation_test.dart` : routes et sélection sans autorité implicite.
- `mobile/test/mark_mature_test.dart` : entrée native, statuts locaux et ordre de sauvegarde.
- `mobile/test/mark_share_ingress_test.dart`, `mobile/test/mark_dictation_capture_test.dart`, `mobile/test/mark_team_member_clarification_test.dart` : isolation du partage, indisponibilité native, détails Space.
- `core/mature_experience_views.py` : continuité des options et confirmations Web, sans troncature silencieuse.
- `templates/core/makolo_mark.html` : contrôles d'action Web accessibles.
- `core/test_mature_personal_experience.py` : tests de contrat Web.

## Vérifications et statut

**Écriture des sources GitHub : réalisée sur la branche #522.**

**Non exécutés dans ce mode de travail :** tests Django, formatter Dart canonique, analyse Flutter, compilation Android, tests sur appareil, e2e Web, accessibilité instrumentée, rendu Compact/Medium/Wide, cohérence avec les plateformes non Android.

Les tests ajoutés restent **tests écrits, non exécutés**. Aucun succès compilateur ou validation native n'est revendiqué. Les CI ne sont pas utilisées comme critères de progression de cette passe. La PR demeure ouverte, sans fusion.

## Écarts non clos au 12 novembre 2026

1. L'orchestration Mark serveur reste **texte uniquement** : les médias transmis aux propriétaires restent des actions distinctes ; aucune compréhension visuelle ou audio générique n'a été inventée.
2. Une pièce audio peut être capturée localement ; aucun propriétaire canonique d'upload audio depuis Mark n'a été prouvé. Seule la dictée conditionnelle peut produire du texte exploitable.
3. Le partage système est intégré pour Android ; aucune validation native ni prise en charge iOS/Web équivalente n'est revendiquée. La validation des permissions réelles et les récupérations après crash sont ouvertes.
4. Les handoffs Personal/Space non couverts par une route Flutter vérifiée restent honnêtement indisponibles au lieu d'utiliser arbitrairement une URL API.
5. Le parcours Web reste principalement textuel ; Mark Web n'a pas de capture ni de transfert multimodal direct validés.
6. La revue visuelle Compact/Medium/Wide, la compilation Android, l'exécution des tests Django/Flutter, les golden tests et l'accessibilité instrumentée demeurent non exécutées.
7. Les fichiers personnels sont remis au propriétaire avec choix utilisateur explicite : posséder un document ne confirme ni Proof, ni Requirement, ni Readiness.

### Conditions de clôture instrumentée distinctes

Cette passe GitHub a modifié les sources et ajouté les tests, mais **aucun test ni build n'a été exécuté** dans ce mode de travail. L'état doit être considéré comme `SOURCE MODIFIÉE — NON VALIDÉE SUR APPAREIL` jusqu'aux contrôles locaux appropriés. Aucun workflow GitHub Actions n'a été lancé, annulé, désactivé ou modifié ici. Aucun merge n'a été effectué.

**Frontière impérative :** les propriétaires Django conservent Permissions, Mandates, Access, Payment, Resource/Proof et les confirmations effectives. Les médias privés ne sont pas des vérités métier sous prétexte d'être joints à Mark.

## Complément d'implémentation Web / Desktop — 12 novembre 2026

Le périmètre de cette passe étend **la préparation et l'interface**, pas les capacités de compréhension et de réponse d'un LLM.

### Expérience Web partagée

- Les vues Web personnelle et Space réutilisent `templates/partials/mark_input_tools.html`, chargée depuis `templates/base/app.html` avec `static/js/mark-intake.js` et `static/css/mark-intake.css`. Les deux clients gardent la même question et les mêmes frontières d'autorité.
- En largeur Expanded (à partir de 1200 px), le Mark peut être placé en fenêtre d'action **non modale**, réduit puis réouvert dans la page. Ce n'est pas une conversation persistante. En Compact/Adaptive, la composition reste intégrée à la page, sans une seconde navigation.
- La sélection de fichiers, les photos, les liens et la dictée du navigateur sont préparés en mémoire ; l'interface distingue les supports locaux des données envoyées. Elle sollicite explicitement l'accord pour continuer avec le seul texte. L'API Mark personnelle/Space reste textuelle.
- L'aperçu via `<dialog>` concerne les images et certains audios réellement compatibles avec le navigateur. Un PDF ou un document sans aperçu reste sélectionné localement, jamais réputé lu ou analysé.
- La Web Speech API n'est activée que si `SpeechRecognition`/`webkitSpeechRecognition` existe. Elle dépend du navigateur, de la langue, des permissions et possiblement d'un service externe. Le transcript reste modifiable et n'est inséré qu'après validation explicite.
- Un brouillon texte/liens est stocké uniquement dans `sessionStorage` de l'onglet, borné à l'acteur utilisateur/Space. **Les fichiers File/Blob ne persistent pas après navigation/rechargement**. Le bouton d'effacement supprime le brouillon de l'onglet, sans prétendre annuler une décision métier déjà confirmée.
- Le Web personnel reçoit désormais les éléments sélectionnés en entrée `selected_kind/selected_id/selected_family`, strictement bornés ; l'orchestrateur propriétaire continue de vérifier l'existence et l'autorité. Le contexte peut être retiré sans supprimer le texte.
- Les réponses Mark Web sont servies avec `no-store`. Space permet d'annuler la confirmation Team sans la déclencher et rejette une demande vide ou plus longue que 600 caractères sans troncature silencieuse.
- **Handoff de fichier Web personnel réellement exécutable** : une pièce PDF/DOC/DOCX/TXT/JPEG/PNG sélectionnée dans Mark peut remplir, sans téléversement automatique, le formulaire canonique `PersonalAssetCreateForm` intégré dans le parcours. L'utilisateur vérifie le titre, le type et la confidentialité puis soumet directement le `POST` existant de `personal_assets:add` avec CSRF et `multipart/form-data`. Le propriétaire PersonalAsset valide et renvoie le résultat ; Mark ne persiste aucun fichier métier ni ne crée de nouvelle API d'upload. Les autres médias restent locaux et non interprétés. Si le navigateur ne permet pas `DataTransfer`, le lien d'ouverture de Mes documents garde un repli explicite.

### Handoffs Flutter ajoutés

- Les résultats Space d'Operations Jour J et Scanner ouvrent leurs routes Flutter Space vérifiées, avec l'identité d'Occurrence issue de la projection serveur. Les résultats incomplets n'ouvrent rien ; aucune route personnelle ou autorité implicite n'est dérivée.

### Contrats et preuves source

- Fichiers Web ajoutés : `templates/partials/mark_input_tools.html`, `templates/partials/mark_personal_asset_form.html`, `static/js/mark-intake.js`, `static/css/mark-intake.css`.
- Fichiers Web modifiés : `templates/base/app.html`, `templates/core/makolo_mark.html`, `templates/organizations/space/mark_ws5.html`, `core/mature_experience_views.py`, `organizations/space_ws5_web.py`. Le propriétaire `personal_assets/views.py` et ses règles n'ont pas été remplacés.
- Fichiers Flutter modifiés : `mobile/lib/features/mark/mark_navigation.dart`, `mobile/test/mark_navigation_test.dart`.
- Tests serveur ajoutés dans `core/test_mature_personal_experience.py` et `organizations/test_ws5_space_day_of_live_scanner_mark_web.py` pour le Web, les contextes sélectionnés, l'absence de faux upload, la limite textuelle, le cache privé et l'annulation.

### État réel et obstacles

**Implémentation écrite, mais non compilée ni exécutée dans cet environnement connecté GitHub.** Les tests Dart, Python, E2E Web et Android, la validation visuelle, le formatter canonique et la recette multi-écran restent à réaliser séparément. Le parcours générique de transfert multimodal entre Mark et tous les autres owners, l'interprétation visuelle, les PDF, la compréhension audio générique et toute intelligence nécessitant un fournisseur/modèle ou des contrats propriétaires non présents restent des capacités **non closes**, pas des fonctionnalités simulées.

Aucune CI, aucun workflow ni aucune configuration de workflow n'a été lancée, annulée ou modifiée dans cette passe. La PR #522 demeure ouverte et `main` non modifiée.

## Recette UX/UI mobile — corrections du 14 novembre 2026

À partir des captures d'émulateur reçues (écran Mark, pièce texte, galerie/caméra, audio enregistré et dictée), la priorité est **la présentation**, sans prétendre valider la logique serveur.

- Composeur Flutter regroupé dans une seule surface arrondie : saisie, pièces et outils forment un ensemble. Le grand bouton « Continuer » est remplacé par une flèche circulaire intégrée, inactive sans texte.
- Un **seul bouton +** ouvre le choix natif et contextuel **Appareil photo / Photos / Fichiers**. Le microphone est distinct, pour la dictée ou la pièce audio. Les sources ont des intitulés d'accessibilité et des cibles tactiles de 48 dp. Le bouton dédié « Lien » est supprimé.
- Photos et images : **miniatures locales** à taille bornée avec ouverture et retrait. Documents : **vignettes de format** et nom court ; l'appui sur un PDF ouvre le lecteur privé `PrivatePdfView` existant, les autres formats gardent une présentation sobre. La conservation PersonalAsset devient une action contextuelle du document, sans bouton de transfert permanent au milieu des miniatures.
- La caméra native demeure le propriétaire de l'interface de capture. Au retour, **Mark présente une revue de l'image** avec « Reprendre/Changer », « Garder » et « Annuler », puis ajoute une miniature seulement après consentement. L'image refusée est retirée du staging local.
- Le texte technique permanent sur le cache, les transmissions, le réseau et les fournisseurs de transcription a été ôté des surfaces normales d'édition/voix. Les erreurs qui empêchent une action restent visibles et formulées en conséquence humaine.
- Le compteur de caractères est discret et n'apparaît qu'à l'approche de la limite ; la restauration et l'annulation sans conséquence restent silencieuses.
- Les URL explicites `http(s)` saisies/collées sont reconnues **sans fetch ni exploration**. La présentation locale d'une URL ne vaut ni lecture de son contenu ni transmission d'une pièce.
- Le FocusNode reste stable lorsque le clavier s'ouvre : le symbole officiel et la question s'effacent visuellement sans recréer le champ de saisie ; le texte et les fichiers restent dans le même composeur.
- Dictée : la transcription apparaît **dans le champ Mark existant** en temps réel, puis reste modifiable après validation ; annuler restaure le texte d'avant dictée. Aucun formulaire de transcription secondaire. L'enregistrement reste une barre compacte avec durée, pause, écoute et conservation.
- Web personnel/Space : même bouton +, miniatures, vignettes de documents, dictée conditionnelle réintégrée dans le texte, flèche dans la surface de saisie et repli avec clavier sur petits écrans. La fenêtre non modale et son bouton de réduction demeurent disponibles sur ordinateur.
- **Hors périmètre décidé** : échange oral continu / mode vocal immersif ; aucun écran ne doit le promettre.

**Vérification effectuée :** relecture des composants source et de la structure des widgets. **Non effectué :** lancement, hot restart, comparaison de captures après modification, golden tests, formatter canonique, tests Flutter et recette Samsung. Ces changements UI n'impliquent aucun nouveau modèle, droit, upload ou succès serveur. La PR reste non fusionnée.

## État de clôture source — recette UX/UI consolidée du 14 novembre 2026

Les **18 points de conception examinés** ont reçu un traitement source côté composeur et gestuelles, mais **ne sont pas certifiés par une exécution**. Les conventions ChatGPT/Gemini ont servi à évaluer les gestes génériques, non à recopier leurs marques, conversations ou modes vocaux.

### Points à vérifier en recette instrumentée

- Flutter : taille du composeur au repos et clavier ouvert, adaptation Android compact/tablette, caméra réelle Samsung/émulateur, galerie, miniatures, lecteur PDF, dictée annulée/conservée, enregistrement mis en pause au changement de cycle de vie, retour par propriétaire PersonalAsset et isolation par Profil/Space.
- Web : JavaScript, CSS, HTML personnel et Space, menu média avec et sans clavier, consentement avant reconnaissance vocale du navigateur, arrêt du microphone quand la fenêtre est réduite ou l'onglet masqué, miniatures et libération des Object URLs, brouillon `sessionStorage` circonscrit, annulation avant envoi au propriétaire, capacité sans JS.
- Le sélecteur générique Web accepte toute extension locale ; le transfert à PersonalAsset reste limité par **ses propres règles**. Une pièce inconnue n'est jamais réputée analysée ni téléversée vers Mark.
- Dictée et audio Android : protection des appels microphone après disparition du widget, par exemple lorsqu'une permission arrive après un changement d'écran. Aucun microphone ne doit démarrer après l'annulation.
- Propriétaires : aucun média transmis via une API Mark textuelle, aucun document considéré comme Proof/Requirement/Readiness automatiquement, aucune permission créée par l'interface, aucune déduction de succès sur une réponse ambiguë.

**Tests adaptés/écrits mais non exécutés** : `mobile/test/mark_mature_test.dart`, `mobile/test/mark_dictation_capture_test.dart`, `core/test_mature_personal_experience.py`, `organizations/test_ws5_space_day_of_live_scanner_mark_web.py`. Aucun formatage canonique Dart, `flutter analyze`, golden, build Android, `manage.py check`, test Django ou exercice sur navigateur/appareil n'a été prétendu exécuté dans cette passe GitHub. Aucune opération sur les workflows CI ni fusion.
