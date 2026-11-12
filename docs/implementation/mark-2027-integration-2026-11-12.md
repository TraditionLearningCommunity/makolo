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
| Texte Flutter, brouillon par acteur | Existant, conservé | `mark_repository.dart`, `DraftRepository` |
| Clarifications Flutter | Options réellement sélectionnables pour les types autorisés | `mark_navigation.dart`, `mark_screen.dart` ; nouveau passage par l'orchestrateur propriétaire |
| Handoffs Flutter | Routes explicitement connues, pas de navigation vers des URLs API | `mark_navigation.dart` ; certains owners restent sans route native vérifiée |
| Confirmation Recognition Flutter | Confirmation owner-backed et clé d'idempotence locale | `mark_repository.dart`, `mark_screen.dart` ; jamais de retry aveugle en résultat ambigu |
| Photo, image, documents | Acquisition locale déjà existante, retrait et aperçu photo ajoutés | `ProfileFileStore`, `NativeFileAcquisitionCoordinator` ; aucun transfert Mark prétendu |
| Audio | Capture Android locale, pause/reprise/arrêt, écoute et interruption | `record`, `just_audio`, permissions natives existantes ; **pas de transcription** |
| Liens | Collage contrôlé HTTP(S), retrait, brouillon local | Aucune exploration arbitraire, aucun enrichissement serveur prétendu |
| Web personnel | Choix de clarification et confirmation Recognition par formulaires POST/CSRF | `core/mature_experience_views.py`, `templates/core/makolo_mark.html` |
| Retour après handoff | Retour natif via navigation existante | Restauration exhaustive du contexte de retour non certifiée |
| Profil et Space | Stockages et routes distincts | Changer de contexte ne confère aucun Mandate/Permission |
| LLM | Non requis | Aucun service IA ajouté |

### Règle de transmission explicite

Une photo, un document, un audio ou une URL conservés dans le brouillon ne sont **pas** transmis par `POST /api/v1/me/mark/` ou le Mark Space. Le repository refuse de les présenter comme une soumission multimodale. Lorsque du texte les accompagne, une confirmation explicite permet de traiter **le texte seul** ; les supports restent locaux. Une réponse `completed` pour ce texte ne supprime pas les supports non envoyés.

La proposition multimodale de bout en bout n'est donc **pas déclarée mature**. Le futur raccordement devra cibler des propriétaires précis et leur contrat de transfert, d'exploitation, d'autorisation et de confirmation, sans introduire une table `MarkIntent` ou une `Proof` parallèle.

### Voix : garantie réelle

Le dépôt contient déjà `record`, `just_audio`, la permission de microphone et le manifeste Android avec `RECORD_AUDIO`. Le nouveau parcours utilise ces dépendances déjà déclarées pour produire une pièce audio locale, plutôt qu'un microphone décoratif. La durée est bornée à 120 secondes. L'enregistrement interrompu est mis en pause lorsque cela fonctionne ; le stockage reste attaché au Profil. La dictée et sa couverture linguistique ne sont pas annoncées, car aucun moteur de transcription utilisable par Mark n'a été constaté.

## Fichiers modifiés / ajoutés

- `mobile/lib/features/mark/mark_navigation.dart` : correspondance sûre vers les routes Flutter et sélection de clarification.
- `mobile/lib/features/mark/mark_repository.dart` : brouillons des références locales, confirmations et états de transport non confirmé.
- `mobile/lib/features/mark/mark_screen.dart` : composer, clarifications, destination, contexte, pièces, photo, audio, URL, confirmations.
- `mobile/lib/features/mark/mark_voice_capture.dart` : capture audio et lecture locales.
- `mobile/test/mark_navigation_test.dart` : routes et sélection sans autorité implicite.
- `mobile/test/mark_mature_test.dart` : entrée native et statuts locaux honnêtes.
- `core/mature_experience_views.py` : continuité des options et confirmations Web, sans troncature silencieuse.
- `templates/core/makolo_mark.html` : contrôles d'action Web accessibles.
- `core/test_mature_personal_experience.py` : tests de contrat Web.

## Vérifications et statut

**Écriture des sources GitHub : réalisée sur la branche #522.**

**Non exécutés dans ce mode de travail :** tests Django, formatter Dart canonique, analyse Flutter, compilation Android, tests sur appareil, e2e Web, accessibilité instrumentée, rendu Compact/Medium/Wide, cohérence avec les plateformes non Android.

Les tests ajoutés restent **tests écrits, non exécutés**. Aucun succès compilateur ou validation native n'est revendiqué. Les CI ne sont pas utilisées comme critères de progression de cette passe. La PR demeure ouverte, sans fusion.

## Écarts non clos

1. Transfert propriétaire réellement confirmé des supports Mark et récupération après incident, avec destination et usage métiers explicites.
2. Interprétation utile de supports lorsque des mécanismes concrets existent ; pas de faux OCR, transcription, vision ou LLM.
3. Réception complète du partage système vers Mark et sélection d'objets contextuels multiples, selon le contrat natif.
4. Dictée conditionnelle et langues réellement supportées : choix technologique encore à justifier par les appareils cibles.
5. Couverture de tous les handoffs Space et personnels par routes natives existantes, sans URL API arbitraire.
6. Reprise complète après crash/révocation/changement de compte, et nettoyage de fichiers avec tests exécutés.
7. Aperçu PDF/document et validation propriétaire de type/taille, plus contrôles d'accessibilité et responsive sur appareils réels.
8. Web multimodal réel, au-delà de la continuité textuelle corrigée ici.

Aucun de ces points ne peut être déclaré fermé par la seule présence d'un bouton ou d'un modèle générique. Les propriétaires Django conservent la vérité et les décisions métier.
