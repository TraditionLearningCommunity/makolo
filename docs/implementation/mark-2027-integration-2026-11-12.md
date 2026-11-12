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
