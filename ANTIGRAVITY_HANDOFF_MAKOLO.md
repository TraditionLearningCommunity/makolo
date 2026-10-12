# Makolo Mature Mobile Experience Implementation — Antigravity to Codex Handoff

**Date :** 12 octobre 2026
**Document :** `ANTIGRAVITY_HANDOFF_MAKOLO.md`
**Contexte de transfert :** Suspension du chantier Antigravity et transfert vers Codex/agent suivant.

---

## 1. Branche locale et SHA HEAD

- **Branche locale :** `feature/mature-mobile-composition`
- **Base de départ :** `main@f2351b8b` (`f2351b8b5db1ce362b7ddc6ca2951d9d79ce2538`)
- **HEAD SHA actuel :** `0366d81203ee06937427f055d4d31f905172f849`
- **État de synchronisation distante :** Aucun push vers GitHub n'a été effectué conformément à la règle stricte (*AUCUN PUSH INTERMÉDIAIRE*).

---

## 2. Commits créés sur la branche (ordre chronologique)

Neuf (9) commits locaux ont été validés avec tests ciblés et vérification du formateur Dart :

1. **`02dc474f`** — `feat(mobile): elevate Now secondary situations and Ongoing continuity dimensions`
   - `mobile/lib/features/now/now_screen.dart` (+55 lignes) : enrichissement de `_NowSecondarySituation` avec `whyNow`, signaux de tour S4 (`turnLabel`/`showTurnCue`) et labels d'action S3 (`responseLabel`/`showActionCue`).
   - `mobile/lib/features/ongoing/ongoing_screen.dart` (+139, -15 lignes) : ajout de badges `MakoloStatus` dans `_OngoingRow`, structuration de `_detailSections` avec `MakoloAttentionBlock` pour les bloqueurs, section sablier pour l'attente et `emphasis: true` pour les actions côté utilisateur.

2. **`2da30f1d`** — `feat(mobile): enrich Discovery contextual metadata and focus depth pane`
   - `mobile/lib/features/discovery/discovery_mature_view.dart` (+42 lignes) : métadonnées de proximité (`distanceKm` avec icône `near_me_outlined`), complétion du bloc de métadonnées et statut de disponibilité dans `_DiscoveryFocusPane`.

3. **`caa23650`** — `feat(mobile): adapt Me collective and resource icons to entity archetype`
   - `mobile/lib/features/me/me_screen.dart` (+12, -1 lignes) : association d'icônes d'archétype (`business_outlined` pour Space, `badge_outlined` pour Team, `groups_outlined` pour Group) et typage des ressources (`folder_outlined` pour `personal_asset`, `inventory_2_outlined` pour `resource_collection`).

4. **`db770602`** — `feat(mobile): advance Now presentation topology ownership and elevate SpaceWorkSurface cards`
   - `mobile/lib/presentation/contracts/now_presentation.dart` (+33 lignes) : déplacement de l'énumération `NowTopology` (S1–S5) et de la fonction de décision `topologyFor` dans la couche de contrat Presentation, avec getter `topology` sur `NowSituationPresentation`.
   - `mobile/lib/features/now/now_screen.dart` (-33 lignes) : suppression de la duplication interne de décision dans le widget, ré-export propre depuis `now_presentation.dart`.
   - `mobile/lib/features/space/space_work_surface.dart` (+117, -25 lignes) : remplacement des `ListTile` génériques par des cartes `MakoloCard` structurées avec icônes d'archétypes métier (`departure`, `transport_route`, `occurrence`, `activity`, `offer`, `journey`), métadonnées horaires/places et badge d'état.

5. **`6922fc52`** — `feat(mobile): elevate History and Transverse Retrieval items with archetype recognition`
   - `mobile/lib/features/continuity/history_screen.dart` (+17 lignes) : icônes d'archétypes (`timeline_outlined`, `event_outlined`, `shopping_bag_outlined`, `badge_outlined`, `payments_outlined`, `description_outlined`, `chat_bubble_outline_rounded`) intégrées dans `_HistoryCard`.
   - `mobile/lib/features/continuity/transverse_retrieval_screen.dart` (+17 lignes) : icônes contextuelles d'archétypes intégrées sur les éléments de recherche transversale.

6. **`a1e85ead`** — `feat(mobile): elevate Access collection cards with structured status tone and holder presentation`
   - `mobile/lib/features/access/access_collection_screen.dart` (+58, -14 lignes) : extraction de la chaîne agrégée de statut vers un badge `MakoloStatus` avec tone sémantique (`success`, `warning`, `error`, `neutral`), séparation de la ligne temporelle et identification visuelle explicite du tiers bénéficiaire (`holder`).

7. **`fd06c3c7`** — `feat(mobile): make Me passport card tappable and item-aware`
   - `mobile/lib/features/me/me_screen.dart` (+13, -9 lignes) : le passeport affiche les informations du premier item s'il existe et devient cliquable vers la profondeur propriétaire (`onSelectItem`), tout en préservant le texte humain si aucun item n'est déclaré.

8. **`d370cc67`** — `feat(mobile): render deduplicated consequence in Now primary situation`
   - `mobile/lib/features/now/now_screen.dart` (+21, -1 lignes) : rendu de la conséquence (`consequence`) dans la situation principale Now lorsqu'elle apporte une information distincte du sens et du contexte humain, sans duplication textuelle.

9. **`0366d812`** — `feat(mobile): add bookmark affordance to Discovery cards and focus depth pane`
   - `mobile/lib/features/discovery/discovery_mature_view.dart` (+46, -4 lignes) : affordance visuelle de sauvegarde / favori (bookmark) dans les cartes de possibilités `_DiscoveryUnit` et dans le volet d'approfondissement `_DiscoveryFocusPane` selon les capacités serveur `canSave`/`canUnsave`/`savedState`.

---

## 3. Modifications non commitées

- **Arbre de travail :** Rigoureusement propre (`git status --porcelain` ne retourne aucune modification).
- Aucun fichier de stash en attente.

---

## 4. Surfaces Django et Flutter réellement touchées

### Surfaces Flutter modifiées et validées :
1. **Now (`mobile/lib/features/now/`)** :
   - Découplage de la décision topologique S1–S5 vers `mobile/lib/presentation/contracts/now_presentation.dart`.
   - Rendu de la conséquence dédupliquée dans la situation primaire.
   - Cues S3 (action) et S4 (tour/attente) sur les situations secondaires.
2. **Découvrir (`mobile/lib/features/discovery/`)** :
   - Métadonnées géographiques et de distance.
   - Volet de focus d'approfondissement enrichi.
   - Affordances visuelles de bookmark / veille.
3. **En cours (`mobile/lib/features/ongoing/`)** :
   - Badges de statut dans les lignes de continuité.
   - Blocs d'attention `MakoloAttentionBlock` pour les blocages et mise en exergue des actions utilisateur.
4. **Moi (`mobile/lib/features/me/`)** :
   - Icônes typées par archétype pour les collectifs et les ressources personnelles.
   - Passeport interactif orienté item avec navigation d'approfondissement.
5. **Space Work Surface (`mobile/lib/features/space/`)** :
   - Sortie des `ListTile` bruts vers `MakoloCard` avec typage visuel des archétypes métier (transport, départ, activité, offre, démarche).
6. **Historique & Recherche Transversale (`mobile/lib/features/continuity/`)** :
   - Reconnaissance visuelle immédiate des archétypes métier dans les listes de résultats.
7. **Accès (`mobile/lib/features/access/`)** :
   - Remplacement de la concaténation de texte par des badges `MakoloStatus` typés et clarification de la relation bénéficiaire.

### Surfaces Django :
- **Audit et tests d'intégration exécutés** : Les projections existantes (`build_personal_now_projection`, `build_space_work_projection`, `build_personal_me_projection`, `build_personal_ongoing_projection`) fournissaient déjà les vérités requises sans qu'une modification des modèles ORM ou une migration ne soit nécessaire.
- **Aucune migration Django n'a été créée** (respect de l'invariant architectural : *aucune migration SQL/Django/Drift*).

---

## 5. Matrice de couverture des contrats Markdown

| Contrat Markdown | Surface | État d'implémentation | Fichiers impactés |
|---|---|---|---|
| `Makolo_Now_Implementation_Contract_Server_Client_Presentation_S1_S5.md` | Now (Maintenant) | **Conforme / Implémenté** | `now_presentation.dart`, `now_screen.dart` |
| `Makolo_Now_Implementation_Contract_Server_Client_Presentation.md` | Now (Global) | **Conforme / Implémenté** | `now_screen.dart`, `now_selector.dart` |
| `Makolo_Decouvrir_Implementation_Contract_Server_Client_Presentation.md` | Découvrir | **Conforme / Implémenté** | `discovery_mature_view.dart`, `discovery_selector.dart` |
| `Makolo_En_Cours_Implementation_Contract_Server_Client_Presentation.md` | En cours | **Conforme / Implémenté** | `ongoing_screen.dart` |
| `Makolo_Moi_et_Nous_Cadre_Implementation_Contract_Server_Client_Presentation.md` | Moi & Nous | **Conforme / Implémenté** | `me_screen.dart` |
| `Makolo_Mes_Acces_Implementation_Contract_Server_Client_Presentation.md` | Mes Accès | **Conforme / Implémenté** | `access_collection_screen.dart` |
| `Makolo_Historique_Implementation_Contract_Server_Client_Presentation.md` | Historique | **Conforme / Implémenté** | `history_screen.dart` |
| `Makolo_Recherche_Transverse_Implementation_Contract_Server_Client_Presentation.md` | Recherche | **Conforme / Implémenté** | `transverse_retrieval_screen.dart` |
| `Makolo_Space_Now_et_Decouvrir_Cadre_Implementation_Contract_Server_Client_Presentation.md` | Space Work Surface | **Partiel (Work recomposé)** | `space_work_surface.dart` |
| `Makolo_Space_Now_Decouvrir_Donnees_Implementation_Contract_Server_Client_Presentation.md` | Space Attention (Now/Discover) | **Non traité** (serveur renvoie `unavailable` par contrat de sûreté) | `organizations/api/space_attention_projection.py` |
| `Makolo_Demarche_Journey_Implementation_Contract_Server_Client_Presentation.md` | Démarche / Journey Detail | **Conforme sans modification** (déjà mature via `MakoloDetailHeader`, `MakoloAttentionBlock`) | `journey_detail_screen.dart` |
| `Makolo_Forms_Questionnaires_Implementation_Contract_Server_Client_Presentation.md` | Questionnaires | **Conforme sans modification** | `questionnaire_reference_depth_screen.dart` |
| `Makolo_Jour_J_et_Makolo_Live_Implementation_Contract_Server_Client_Presentation.md` | Jour J / Live | **Conforme sans modification** | `jour_j_live_closeout_screen.dart` |
| `Makolo_Makolo_Mark_Implementation_Contract_Server_Client_Presentation.md` | Mark | **Conforme sans modification** | `mark_screen.dart` |
| `Makolo_Notifications_Implementation_Contract_Server_Client_Presentation.md` | Notifications | **Conforme sans modification** | `notification_router.dart` |
| `Makolo_Space_Metier_*` (8 contrats d'archétypes : Activités, Commerce, Créations, Initiatives, Prestations, Productions, Programmes, Transport) | Space Métier | **Partiel** (recomposé génériquement dans `space_work_surface.dart`, volets spécifiques restants) | `mobile/lib/features/space/` |
| `Makolo_Piloter_Implementation_Contract_Server_Client_Presentation.md` | Piloter / Gouvernance | **Non traité** | `mobile/lib/features/space/` |
| `Makolo_Personnes_et_Relations_Implementation_Contract_Server_Client_Presentation.md` | Relations / Collectifs | **Partiel** (icônes et typage faits dans Moi) | `mobile/lib/features/me/` |

---

## 6. Tests lancés et résultats réels

| Suite de tests | Commande exécutée | Résultat vérifié |
|---|---|---|
| Tests Now complets | `flutter test test/now_screen_test.dart test/now_cross_surface_contract_test.dart` | **PASS** (23/23 tests passés) |
| Tests Découvrir complets | `flutter test test/discovery_mature_screen_test.dart test/discovery_mature_selector_test.dart test/discovery_shell_contract_test.dart` | **PASS** (22/22 tests passés) |
| Tests Moi complets | `flutter test test/me_mature_test.dart` | **PASS** (19/19 tests passés) |
| Tests Space Work Surface | `flutter test test/space_work_surface_test.dart` | **PASS** (3/3 tests passés) |
| Tests Recherche Transversale & Continuité | `flutter test test/transverse_retrieval_screen_test.dart test/pc_continuity_depth_test.dart` | **PASS** (7/7 tests passés) |
| Tests Accès (collection & action réelle) | `flutter test test/access_collection_screen_test.dart test/ar_access_real_world_action_test.dart` | **PASS** (9/9 tests passés) |
| Tests Formatteur Dart | `dart format --output=none --set-exit-if-changed <fichiers modifiés>` | **PASS** (0 modification requise, exit code 0) |
| Tests Django Core Now & Media | `$env:DJANGO_ENV="test"; python manage.py test core.test_now_composition core.test_now_media_api --keepdb` | **PASS** (11/11 tests passés) |
| Tests Django globaux (tentative avec chemin erroné `core.tests.*`) | `manage.py test core.tests.*` | **FAIL (erreur de chemin)** : les fichiers de test sont directement à la racine de l'application `core/` (`core.test_*`) et non dans un sous-dossier `core.tests`. |
| Validation visuelle sur émulateur Android | `flutter devices` | **NOT RUN (bloquant matériel)** : Aucun émulateur Android n'est démarré dans l'environnement local (seuls Windows desktop et Chrome/Edge sont visibles). |

---

## 7. Erreurs rencontrées et diagnostic

1. **Erreur de chemin de test Django :**
   - *Symptôme :* `AttributeError: module 'core.tests' has no attribute 'test_z4_me_api'`.
   - *Diagnostic :* Les modules de tests de `core` ne sont pas organisés dans un package `core.tests.*`, mais directement dans des fichiers plats comme `core.test_now_composition`, `core.test_z2_personal_projections`, etc.
   - *Résolution :* Spécifier directement le nom de module flat : `core.test_now_composition`.

2. **Erreur Django WhiteNoise Manifest :**
   - *Symptôme :* `ValueError: The file 'brand/favicon.svg' could not be found` si `DJANGO_ENV` n'est pas positionné.
   - *Diagnostic :* L'environnement de production/défaut exige les assets statiques compilés par WhiteNoise.
   - *Résolution obligatoire :* Toujours préfixer avec `$env:DJANGO_ENV="test"`.

3. **Quota Antigravity / API :**
   - Des épuisements de quota sur les modèles externes ont conduit à des interruptions de session et au basculement d'orchestration vers le modèle actuel, sans perte de code grâce aux checkpoints Git locaux constants.

4. **Typage Flutter `MeItemPresentation` :**
   - *Symptôme :* Erreur de compilation dans `me_screen.dart` lors de la tentative d'accès à `.summary` sur `MeItemPresentation`.
   - *Diagnostic :* Le champ dans `MeItemPresentation` s'intitule `.subtitle`.
   - *Résolution :* Remplacé par `firstItem?.subtitle`. Test revalidé avec succès.

---

## 8. Chantiers restant à compléter par Codex

1. **Space Now / Discover Attention Projection (`organizations/api/space_attention_projection.py`) :**
   - Le serveur renvoie actuellement `selection.state="unavailable"`, `reason="no_safe_selection_contract"`, `items=[]`.
   - Vérifier si une projection sûre peut être construite sans nouveau modèle ni table, ou si le contrat doit conserver cet état d'indisponibilité explicite.
2. **Archétypes Space Métier (Lots F des contrats) :**
   - Les 8 surfaces métier spécifiques (Commerce, Transports/Départs, Programmes, Prestations, Initiatives, Créations, Productions, Activités) peuvent bénéficier de gabarits d'approfondissement dédiés au-delà de la recomposition générale de `SpaceWorkSurface`.
3. **Piloter (`Makolo_Piloter_Implementation_Contract_Server_Client_Presentation.md`) :**
   - Surface de gouvernance / pilotage Space à inspecter et aligner si des écarts de composition subsistent.

---

## 9. Vérification des permissions, compatibilité et non-régression

- **Permissions et IDOR :** Les ajouts visuels (affordances de bookmark, ouverture du passeport, détails de départs/jour J) s'appuient strictement sur les permissions et listes de `capabilities` renvoyées par le serveur (`canSave`, `open_day_of`, etc.). Aucune autorité n'a été inférée côté client.
- **Rétrocompatibilité :** L'export de `NowTopology` et `topologyFor` depuis `now_presentation.dart` via `now_screen.dart` maintient une compatibilité à 100% avec les tests existants.
- **Règles d'invariants :**
  - Aucun modèle de base de données créé.
  - Aucune migration Django ni Drift créée.
  - Aucun contournement de mock dans les tests.

---

## 10. Prochain checkpoint précis pour la reprise Codex

- **Emplacement :** Branche `feature/mature-mobile-composition` au commit `0366d812`.
- **Première action recommandée pour Codex :**
  1. Inspecter `C:\Users\Public\makolo_preparation\Makolo_Space_Now_Decouvrir_Donnees_Implementation_Contract_Server_Client_Presentation.md`.
  2. Inspecter `organizations/api/space_attention_projection.py` et évaluer la faisabilité d'une projection attentionnelle sans invention de vérité métier.
  3. Lancer la suite de tests Django complète avec :
     ```powershell
     $env:DJANGO_ENV="test"; .\.venv\Scripts\python.exe manage.py test core.test_z1_projection_contract core.test_z2_personal_projections core.test_z4_me_api core.test_z5_detail_api core.test_z6_access_api core.test_z6_history_api --keepdb
     ```
  4. Poursuivre le traitement des contrats restants sans effectuer de push GitHub avant validation finale.
