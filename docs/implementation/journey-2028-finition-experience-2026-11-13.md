# Makolo 2028 — Démarches : finition intégrée et reliquats prouvés

**Date :** 13 novembre 2026 (Africa/Lubumbashi)  
**Dépôt/branche :** TraditionLearningCommunity/makolo · PR #522 · `fix/discover-a-continuation-context-20261014`  
**Périmètre :** Accompagnement et accomplissement des démarches, sans nouvelle verticale Journey ni refonte des autres expériences.

## Décision d'architecture

Une Journey appartient au propriétaire métier et ne reçoit pas une vérité parallèle Flutter/Web. Une action vient du propriétaire (Services, Forms, Requirements, Payment, Access, Jour J/Live). Un Profile et un Space sont deux bénéficiaires et portées d'autorité distincts. Readiness reste dérivée ; un fichier existant ne satisfait pas une Requirement ; un résultat externe n'est pas un état Journey.

Ce checkpoint corrige des écarts vérifiés dans la PR #522. Il ne déclare pas livré le parcours Space demandeur lorsque ses propriétaires natifs n'exposent pas encore toutes les capacités nécessaires.

## Modifications intégrées sur la branche

1. **Démarrage Web Services idempotent** — `services/views.py`, `templates/services/start.html` : clé d'opération conservée entre POST, reprise du résultat accepté via `start_service_journey_idempotently`, rotation sur une nouvelle visite volontaire et erreur humaine si la clé est réemployée pour une autre demande. Le serveur détermine le résultat ; aucun succès local fabriqué.
2. **Éligibilité Groups / HTTP** — le début Web applique le même filtre Activity/Group que le GET/POST natif. Une URL devinée ne court-circuite plus la sélection d'éligibilité. La validation Journey serveur reste en place.
3. **Contrat d'entrée natif** — `services/api_views.py` expose le titre et la description publics du Service via `representation`. `ServiceStartScreen` les consomme ; les libellés d'opportunité sont français et les commandes réutilisent `MakoloActionButton`. Aucun nouveau propriétaire ni endpoint.
4. **Résultat externe visible** — `core/api/detail_projections.py` expose `service_result` (code et libellé owner Services) seulement lorsqu'un `ServiceJourneyContext` personnel autorisé possède un résultat significatif. L'état Journey reste séparé. `JourneyDetailSelector` et N3 Flutter affichent la réponse de l'organisme depuis la projection locale du Profile.
5. **N3 Web unifié** — le handoff de `participant_journey_detail.html` ne dépend plus d'une condition impossible. `services/participant_workspace.html` est réduit aux faits et actions complémentaires : objectif, version d'opportunité liée, pièces et revues, réutilisation explicitement autorisée, obligations détaillées, notes autorisées, soumissions et résultat externe. Le titre, les JourneySteps et les comptes Requirements ne sont plus répétés dans une deuxième page cachée.
6. **Sécurité du transfert SQLite → PostgreSQL** — `quote_ident` refuse types non textuels/nuls et caractères NUL, échappe toujours les guillemets ; les deux suppressions Bandit B608 sont localisées et documentées, accompagnées d'un test SQLite à noms d'identifiants adversariaux. La destination PG continue d'utiliser `psycopg.sql.Identifier`.

Les modèles, migrations, transitions, permissions et contrats de domaine de Journey, Payment, Access, Requirement, Proof et Readiness sont inchangés.

## Tests ajoutés / renforcés

- `services/test_t35_participant_web.py` : double POST, replay inchangé, nouvelle intention explicite, conflit de charge utile, URL directe refusée par le Group gate.
- `services/test_t35_participant_workspace.py` : confidentialité des notes et absence des anciens doublons de progression.
- `services/test_native_start_api.py` : titre réel du Service dans la prévalidation.
- `core/test_z5_detail_api.py` : état Journey distinct de `under_review` puis `unsuccessful`, refus 404 pour un autre Profile.
- `mobile/test/journey_history_projection_test.dart` : séparation ServiceResult et état Journey.
- `mobile/test/journey_n3_lot_c_test.dart` : résultat externe sur l'écran sans conclusion Journey fabriquée.
- `scripts/test_migrate_sqlite_identifiers.py` : identifiants SQLite hostiles et valeur NUL.

**Preuve formatage :** workflow Github Actions Mobile Format du commit `d9e4a144a5`, run `43317428153`, terminé success ; journal : « Formatted 618 files (0 changed) » puis « Canonical formatting is current ». Ce résultat prouve le format, pas l'analyse Flutter ni tous les tests.

## Gates encore ouverts (ne pas fusionner)

- **CI Django/E2E Web :** l'ancien HEAD `25c25f4a6521` échouait avant les tests au gate `git diff --exit-code -- package-lock.json static/dist`. Reconstruire sur une copie synchronisée de #522 (`npm ci; npm run build`), examiner/commiter les artefacts nécessaires ; ne jamais supprimer le gate. Requalifier le dernier HEAD.
- **Sécurité :** relire le résultat Bandit sur le dernier HEAD et exécuter `python -m unittest scripts.test_migrate_sqlite_identifiers`.
- **Django :** exécuter les tests ciblés ci-dessus, `manage.py check`, tests d'autorité, PostgreSQL et concurrence. Aucun succès Django n'est revendiqué par ce checkpoint.
- **Flutter :** exécuter `flutter analyze`, tests des sélecteurs, widgets, navigation et local-first, puis recette Android émulateur/Samsung et Web responsive/accessibilité.
- **Space bénéficiaire :** `Journey.beneficiary_space` et Mandates sont déjà réels, mais Services natif/Web reste contractuellement Profil bénéficiaire, les FormRequests/Responses ciblent un Profile et les API personnelles de Preparation/Journey filtrent le bénéficiaire personnel. Ne pas émettre de bouton « agir comme Space » tant qu'un parcours owner de démarrage, formulaire, preuve et lecture Space n'a pas été autorisé, sécurisé et consommé nativement. Le Space opérateur/prestataire est distinct du Space demandeur.
- **Pièces JourneyArtifact Flutter :** le Web fournit upload/revue/version ; qualifier une projection native et les fichiers privés owner avant de promettre un handoff hors Web.
- **Validation d'ensemble :** reprise de brouillon hors réseau, révocation Space/Profile, paiement pending/refunded, permission 403/404, résultats externes, Jour J/Live, historique, double envoi Web, grands textes. Aucune recette physique n'est encore attestée.

## Commandes de vérification (Windows PowerShell)

```powershell
cd C:\Users\Public\makolo
git status --short --branch
git fetch origin
git switch fix/discover-a-continuation-context-20261014
git pull --ff-only
python -m unittest scripts.test_migrate_sqlite_identifiers
python manage.py check
python manage.py test services.test_t35_participant_web services.test_t35_participant_workspace services.test_native_start_api core.test_z5_detail_api
cd mobile
bash tool/dart_format.sh check
flutter analyze
flutter test test/journey_history_projection_test.dart test/journey_n3_lot_c_test.dart
```

Sur Windows, ne pas écraser de modifications locales : contrôler `git status` et sauvegarder le travail avant `switch/pull`.

**Livraison :** changements enregistrés sur la branche de #522, sans modification directe de `main`, sans merge et sans revendication de CI globale verte.

## Revue de cohérence complémentaire — 13 novembre 2026

Cette passe poursuit l'implémentation dans la **même branche de #522**, sans merge. À la demande du propriétaire, elle se concentre sur la vérité métier et la correction du code, **sans attendre ni déclarer les résultats CI globaux**.

### Défauts confirmés et corrigés

1. **Deux onglets Web créaient un conflit de clé** : chaque rendu du formulaire Service reçoit désormais une clé d'opération propre. Le fallback de session reste réservé aux anciens formulaires sans champ caché.
2. **Retry Web après retrait d'Opportunity** : une opération déjà acceptée est recherchée par son empreinte avant de valider la publication courante. Le propriétaire vérifie actor, Service, objectif et Opportunity d'origine ; un nouveau départ reste soumis aux conditions en vigueur.
3. **Perte des Requirements en Web N3** : le fragment Services expose à nouveau les conditions et les assessments owner, sans réintroduire le second titre, les étapes et le faux pourcentage. Le lien de réutilisation ouvre le propriétaire Trusted Reuse et n'accorde jamais une satisfaction automatique.
4. **Identité manquante dans un template inclus** : l'inclusion Services transmet explicitement le Profile bénéficiaire au contrôle d'export de JourneyArtifact. Seules les pièces autorisées affichent le bouton Exporter.
5. **Lien mort sur Opportunity retirée** : titre et issuer de la révision choisie restent lisibles, mais un objet non publié n'est plus lié à la fiche Opportunity publique. Le texte n'affirme plus que le bénéficiaire peut lui-même adopter une nouvelle révision.
6. **Réponse externe ≠ état Journey** : sur Web et Flutter, un Service Journey `fulfilled` devient « Suivi terminé dans Makolo ». Une réponse négative externe reste visible avec son statut Services, sans devenir un succès ou un refus Journey.
7. **Objectif personnel absent du N3 mobile** : nouvelle projection personnelle `service_request` (objectif, titre/issuer de l'OpportunityRevision épinglée, état de publication actuel), lue dans le ProfileStore et affichée dans un bloc `Votre demande`. Aucun lien/action vers une Opportunity retirée ni état local parallèle.
8. **Refus métier Service Flutter bloquant** : la reprise client distingue 400/422 (corriger une intention rejetée), 409 (conflit et nouvelle intention explicite), 401/403/404 (indisponibilité/autorité) et erreur réseau/5xx (rejouer la même clé et le même payload). Le brouillon garde `attempted` ; si l'échec survient avant l'appel API, les champs restent modifiables.
9. **Isolation de navigation** : la route Flutter Service start est identifiée par Profile + Service pour éviter la réutilisation visuelle du brouillon entre deux contextes.

### Tests modifiés ou ajoutés dans cette passe

- `services/test_t35_participant_web.py` : deux formulaires indépendants, replay après Opportunity retirée, projection privée cohérente, pas de lien mort.
- `services/test_task34a_requirements.py` : assessments du Service visibles dans N3.
- `services/test_t35_participant_workspace.py` : export autorisé via template inclus et état Service terminé avec résultat externe négatif.
- `core/test_z5_detail_api.py` : objectif Service owner distinct du statut et du résultat externe.
- `mobile/test/service_start_failure_test.dart` : refus/409/403/404/transport.
- `mobile/test/service_resumable_intent_test.dart` : brouillon local rééditable.
- `mobile/test/journey_history_projection_test.dart` : Service objective et Opportunity épinglée depuis la projection locale.
- `mobile/test/journey_n3_lot_c_test.dart` : écran Service actif et terminal (résultat externe), objectif et Opportunity retirée.

### Ce qui ne doit pas être annoncé comme livré

La prise en charge end-to-end d'un **Space demandeur/bénéficiaire**, des formulaires au nom du Space, et du traitement natif des JourneyArtifacts privés reste un chantier propriétaire multi-domaines. Les fondations Space Journey existent, mais cette passe n'invente pas les droits et confirmations nécessaires à leur activation. Les tests Django/Flutter, analyse, recette physique Android, PostgreSQL et concurrence doivent être exécutés sur une copie synchronisée avant toute déclaration de conformité de production. Aucun test local complet n'a été exécuté dans cette passe (dépôt non clonable dans l'environnement distant).

Commandes ciblées complémentaires :

```powershell
python manage.py test services.test_t35_participant_web services.test_t35_participant_workspace services.test_task34a_requirements core.test_z5_detail_api
cd mobile
flutter test test/service_start_failure_test.dart test/service_resumable_intent_test.dart test/journey_history_projection_test.dart test/journey_n3_lot_c_test.dart
```

## Parcours Space demandeur et JourneyArtifacts natifs — implémentation

Cette extension s'ajoute à la PR #522 sur la branche `fix/discover-a-continuation-context-20261014`, sans fusion vers `main`. La politique propriétaire reste Django ; le local Flutter reste une projection privée, jamais un décideur d'autorité.

### Space bénéficiaire d'une demande Services

- Un Space **demandeur** se distingue du Space **prestataire** et du Profile personnel. `Journey.beneficiary_space` et la création canonique Journey sont réutilisés, sans modèle parallèle ni migration.
- `services/space_beneficiary.py` décide de la consultation et de l'action avec **Mandate/Permission** actuels : `SPACE_ACTIVITIES_VIEW`, `SPACE_ACTIVITIES_MANAGE`, `SPACE_MANAGE` selon l'acte. Une appartenance à un Groupe, une Team ou une Assignment ne donne pas cette autorité. Les permissions d'opérateur Activity ne deviennent jamais automatiquement des droits sur le demandeur.
- Les GET/POST de démarrage réutilisent `ServiceStartForm` et `start_service_journey_idempotently` ; l'empreinte intègre le Space représenté et préserve exactement les clés des anciennes demandes Profile. Les gates d'éligibilité **Groups de Profiles** ne sont pas transférés implicitement au Space.
- L'intake Service, son brouillon et sa soumission restent propriétaires ; les réponses ont un actor Profile réel. Les formulaires `FormRequest` liés à la Journey collective autorisent l'enregistrement/soumission seulement pour les mandataires d'action actuels, le `FormResponse.respondent` conserve l'identité réelle de la personne.
- Les exigences et la préparation se lisent par des API Space strictement scopées. Une ressource réservée à l'opérateur n'est pas révélée à un Space client. Une Journey collective n'est pas ajoutée de force aux routes personnelles `/me`.
- Liste de reprise des demandes dans l'Espace : `/api/v1/organizations/workspaces/<slug>/beneficiary/journeys/` et projection Flutter local-first correspondante. Les routes mobiles exigent un Espace **explicitement sélectionné**.

### Pièces JourneyArtifact et preuve de Requirement

- `journeys/api_artifacts.py` expose, dans le périmètre strict de la Journey, la liste, l'ajout multipart, la nouvelle version et un téléchargement privé. Les services JourneyArtifact existants gardent signatures MIME, empreintes, versionnement, audit et fichier sur stockage privé. `FileResponse` désactive le cache partagé et refuse l'exposition directe de chemins de stockage.
- Profile et Space ont des scopes de lecture distincts. Une pièce restreinte impose un mandat Space de gestion ; les nouvelles versions ne peuvent déclasser une pièce déjà restreinte. Une pièce d'identité ne peut être déclarée « normale » par l'API. Les anciens parcours Web conservent leurs garde-fous.
- Flutter conserve localement les **métadonnées propriétaires** avec source Space/Profil vérifiée, et copie le brouillon fichier sous le Profile actuel. La synchronisation ne prend pas un upload en attente pour une action confirmée. Le lecteur privé temporaire est effacé après usage ; une confirmation précède sa consultation. Les formats PDF/image/texte sont prévisualisés ; les autres types restent transmissibles mais ne sont pas présentés comme lisibles nativement sans lecteur.
- `services/api_requirement_evidence.py` permet au bénéficiaire autorisé de sélectionner une pièce existante et la proposer explicitement à un `ServiceRequirementAssessment`. L'owner `submit_requirement_evidence` conserve la preuve et son provenance. **Aucune satisfaction automatique** n'en découle. La décision d'Assessment reste chez le prestataire autorisé.
- Flutter offre cette action depuis le détail d'une condition personnelle ou d'un Space ; en cas d'absence de pièce, l'utilisateur peut d'abord en ajouter une. L'API vérifie que pièce et Assessment appartiennent exactement à la même Journey.

### Contrats API nouveaux

- `POST /api/v1/organizations/workspaces/<slug>/beneficiary/services/<service_id>/start/`
- `GET /api/v1/organizations/workspaces/<slug>/beneficiary/journeys/`
- `GET /api/v1/organizations/workspaces/<slug>/beneficiary/journeys/<journey_id>/`
- `GET/POST .../beneficiary/journeys/<journey_id>/intake/`
- `GET .../beneficiary/journeys/<journey_id>/requirements/<assessment_id>/`
- `GET .../beneficiary/journeys/<journey_id>/resources/`
- `GET .../beneficiary/journeys/<journey_id>/resources/<resource_id>/download/`
- `GET/POST /api/v1/me/journeys/<journey_id>/artifacts/` et `GET/POST .../beneficiary/journeys/<journey_id>/artifacts/` pour un Space
- `POST .../artifacts/<artifact_id>/versions/` ; `GET .../artifacts/<artifact_id>/download/`
- `POST .../requirements/<assessment_id>/evidence/` : pièce → preuve en attente, pas de décision automatique

Les routes exactes côté Space sont assemblées par `organizations/api/urls.py`, celles des Journeys personnelles par `core/api/detail_urls.py`.

### Tests ajoutés / recette restant à attester

- `services/test_space_beneficiary_api.py` : Space mandaté, replay indépendant d'un Profile, IDOR, group gate non transféré, intake, révocation, versions, upload, copie privée, téléchargement, formulaire et respondent réel.
- `services/test_task34a_requirements.py` : POST preuve idempotent et Requirement non satisfait, refus de bénéficiaire étranger.
- `mobile/test/space_beneficiary_journey_local_first_test.dart` : séparation des identités de source, Space et Profile.
- Les autres tests Journeys/Services, autorisations, synchronisation, opérations de pièces et questionnaires de la PR existante doivent rester actifs. Ne supprimer ni affaiblir aucun test.
- À vérifier avant toute déclaration « production validée » : Django tests ciblés et PostgreSQL, `python manage.py check`, `flutter analyze`, widget tests/formatage canonique, usages Android et reprise hors connexion, permissions révoquées pendant l'affichage et partage d'un appareil entre Profiles.

Commandes de recette ciblée PowerShell après vérification des modifications locales :

```powershell
cd C:\Users\Public\makolo
git status --short --branch
git fetch origin
git switch fix/discover-a-continuation-context-20261014
git pull --ff-only
python manage.py check
python manage.py test services.test_space_beneficiary_api services.test_task34a_requirements questionnaires.tests journeys.test_space_beneficiary
cd mobile
bash tool/dart_format.sh check
flutter analyze
flutter test test/space_beneficiary_journey_local_first_test.dart
```

**Preuve d'intégration au dépôt :** fichiers et tests enregistrés sur la branche de PR #522, pas de merge. **Preuve de tests exécutés par cette passe :** aucune suite Django/PostgreSQL/Flutter locale exécutée dans cet environnement connecté à GitHub. Les workflows de formatage sont séparés de la recette produit et ne remplacent pas les tests. Ne pas présenter ce checkpoint comme une validation de production.
