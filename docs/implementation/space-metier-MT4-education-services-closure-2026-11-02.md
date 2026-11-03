# MT4 — Programmes / Prestations : fermeture des profondeurs N1 → N2 → N3

**État : implémentation source du périmètre MT4 réalisée sur la PR #522, sans merge.**
**Date : 2 novembre 2026.** Dépôt officiel : `TraditionLearningCommunity/makolo`.
Branche : `fix/discover-a-continuation-context-20261014`.
**Tests et formatage runtime non exécutés localement dans cette session.** Ne pas prétendre une validation Django/PostgreSQL, Flutter ou E2E. Le commanditaire a demandé de ne pas se concentrer sur les CI, non de les déclarer vertes.

## 1. Périmètre et modèle réel

MT4 suit MT1 (cartographie), MT2 (owner-handoffs) et MT3 (Generic/Community), sans remplacer G1–G4. Les compositions N1 des deux archétypes existaient déjà. Le problème MT4 est l'accès réel à leurs profondeurs métier.

| UX | Vérité persistante | Énoncé humain |
| --- | --- | --- |
| Programme N2 | `Activity` dans un Space `education` | Programme durable, même sans Session |
| Session N2 | `Occurrence` liée à l'Activity | Date, lieu, Capacity et Jour J uniquement établis |
| Inscription N2 | `Journey(workflow=registration)` | Demande et continuité réelle |
| Décision N3 | `JourneyRequest` existante | Examiner/approuver/refuser sous le droit `ACTIVITY_REQUESTS_DECIDE` du propriétaire |
| Prestation N2 | `Activity` spécialisée par `ServiceDetails` | Service durable et règles réellement configurées |
| Dossier N2 | `Journey(workflow=service)` avec `ServiceJourneyContext` si réel | Travail concret, outcome, étapes et exigences |
| Dossier opérateur N3 | `JourneyStep`, `JourneyBlocker`, `ServiceRequirementAssessment`, services de collaboration et permissions Services | Gérer les étapes et blocages, lire les conditions ; opérations sensibles du domaine |
| Form et Resource | `questionnaires` / `preparation` | Formulaires/ressources réellement attachés et gérés par leurs owners |

Pas de modèles `Programme`, `Session`, `ServiceCase`, `BusinessEntry` ou `Task` persistants créés par MT4.

## 2. N2 Web — expérience dédiée à chaque archétype

- `organizations:space-work-depth-g2` pour `activity`, `occurrence`, `journey`, exclusivement dans `education` et `service_provider`.
- Relecture de `build_space_work_projection(kind,id,responsibility)` avec sélection owner-scopée **avant** tout détail. Une URL ou un lien N1 n'apporte jamais une permission.
- Programme N2 : Session et inscriptions liées, deux collections paginées séparément (12 par page), statut, retour au Programme et au N1 dans la bonne section. Inscription = Journey réelle ; `JourneyRequest` est une identité distincte, jamais déduite du Journey ID.
- Session N2 : timing exact ou date-only, Place si réellement projetée, Capacity seulement si factuelle et Jour J uniquement sous permission/phase propriétaire.
- Prestation N2 : services/dossiers liés et réalisations réelles. Configuration possible par `services:operator-service-config` **uniquement** si `ServiceDetails` existe et `ACTIVITY_SERVICES_CONFIGURE` est détenue.
- Dossier N2 : état propriétaire, résultat courant et agrégation réelle d'assessments si ce contexte est autorisé. Ouverture de `services:operator-case` uniquement depuis un `owner_handoff` réellement autorisé. Pas de notes privées, preuves, QR ou emails bénéficiaires dans une carte N1/N2 non habilitée.
- Préparation N3 : `preparation:manage` lorsque `ACTIVITY_MANAGE` existe ; `questionnaires:manage` pour Education lorsque ce même owner autorise la configuration Form.
- L'existant du domaine Services Web reste propriétaire des configurations détaillées, reviews, assignments, evidences, notes et commandes complexes ; aucune deuxième implémentation des transactions.

Fichiers : `organizations/space_work_g2_web.py`, `templates/organizations/space/work_g2_depth.html`, `organizations/space_work_web.py`, `organizations/urls.py`.

## 3. API Work — relations prouvées, non duplicatives

- Une Activity sélectionnée en G2 renvoie ses `related_occurrences` paginées (12, même owner/protocole que G1) et `related_work` (registration Journeys autorisées ou Services Journeys visibles pour l'opérateur).
- `related_work_offset` : GET borné à 0–10 000, seulement si `kind=activity` et `id` sélectionné ; aucun scope élargi.
- Conversion explicite de l'UUID Activity avant comparaison aux sets de permissions. Le problème chaînes/UUID a été corrigé.
- Pour l'Education, `request_owner` n'existe que si un `JourneyRequest` **réel** et en attente existe ; les listes ne divulguent pas de bénéficiaire.
- Pour Services, le selector `service_journeys_visible_to` et `service_case_scope` distinguent opérateur autorisé et bénéficiaire personnel ; aucune attribution de droit depuis Space membership.
- `related_work.coverage_state` est `partial` si pagination ; ne pas déclarer un ensemble complet à partir d'une première page.
- Le Journey Service sélectionné avec `open_service_case` expose également `open_service_case_native` owner-scopé, sans convertir l'URL API en action autorisée autonome.
- Aucun faux `next` de Journey, aucune readiness persistée, aucune preuve de paiement inventée.

Fichiers : `organizations/api/space_work_g2.py`, `organizations/api/space_work_projection.py`, `organizations/api/space_work_views.py`.

## 4. Native Flutter — relations et opérateur Services

- `SpaceRetrievalOwnerScreen` consomme `related_occurrences`, `related_work`, `owner_handoffs` de la sélection fraîche, avec vérification du Space et de la responsabilité.
- `SpaceWorkG2Depth` présente deux collections distinctes et paginées : Session/Réalisation et Inscription/Dossier, sans inventer de contenu dans un état vide.
- Une vraie inscription peut ouvrir le `SpaceRequestScreen` déjà propriétaire des décisions natives et de sa vérification d'autorité.
- `SpaceServiceCaseScreen` consomme GET/POST `workspace-service-case` : état, objectif, outcome, assessments agrégés, étapes et blocages actifs, avec pages bornées de 50 et navigation suivante/précédente.
- La route native des dossiers exige le Space acteur courant ; l'API impose Space, activité propriétaire, Mandate sélectionné, Services case scope et permissions fines. Le serveur refait ces contrôles à chaque commande.
- `start_step`, `complete_step`, `resolve_blocker` passent exclusivement par `journeys.collaboration_services` et sa politique d'autorisation Services. Confirmation humaine avant POST ; état mis à jour **après confirmation owner** puis GET ; pas de succès optimiste ni de mutation locale hors ligne.
- Changement d'acteur, révocation, page tardive ou réseau incertain : suppression des actions périmées et revalidation. Un POST incertain n'est pas rejoué automatiquement.
- Les opérations avancées Services Web (notes internes, document restreint, assignments et revues) ne sont pas reconstituées hors de leur propriétaire : convergence native spécialisée à faire dans MT7 lorsqu'une profondeur Flutter réelle en a besoin.

Fichiers : `mobile/lib/features/space/space_work_g2_depth.dart`, `space_service_case_screen.dart`, `mobile/lib/features/continuity/space_retrieval_owner_screen.dart`, `mobile/lib/app/router.dart`.

## 5. Création réelle G2 — Web et Flutter

- `education` : création Programme = `Activity` brouillon, sans inventer une Session.
- `service_provider` : création Prestation = `Activity` brouillon **plus** `ServiceDetails` de type valide, dans **une transaction atomique**. Si Services refuse sa configuration, l'Activity est rollback ; pas de Prestation orpheline.
- Deux clients et une composition propriétaire `create_g2_owner` qui délègue à `activities.services.create_activity` et `services.services.create_service_details`. Aucun doublon de service métier, aucun nouveau champ ni migration.
- Authority : `SPACE_ACTIVITIES_MANAGE` réellement active et `activities.create` autorisé pour le propriétaire Space. Les rôles Activity, GroupMembership et bénéficiaires ne créent jamais pour le Space par simple association.
- Web : `space-work-create-g2` et formulaire contextualisé, Space fixé, type Service obligatoire seulement pour Prestations, retour Métier après confirmation.
- API : `workspace-work-g2-create`, rejet explicite d'un propriétaire ou statut fourni par le client, validations `ActivityCreateForm`, transaction propriétaire, réponse 201 `private, no-store`.
- Flutter : le formulaire natif réutilise la surface de création Activity existante avec grammaire Programme/Prestation, choix du type Service réel, validation de l'identité et du résultat owner, refresh Work et aucune seconde émission automatique en cas de réponse ambiguë.
- Les CTAs N1 sont dérivés de `capabilities.create_g2` du serveur et cachés dans une responsabilité Activity-limited, dans un archetype différent ou lorsque l'entitlement du Space est refusé.

Fichiers : `organizations/space_work_g2_creation.py`, `space_work_g2_create_web.py`, `templates/organizations/space/work_g2_create.html`, `organizations/api/space_work_g2_create.py`, `organizations/api/urls.py`, `mobile/lib/features/space/space_work_create_activity_screen.dart`, `space_work_surface.dart`, router et template N1.

## 6. Tests ciblés et contrôles à exécuter (non exécutés dans cette session)

Backend : `organizations/test_space_work_mt4.py` — entrées N1/N2, inscription sans/sous vrai JourneyRequest, session, pagination, Mandate limité/révoqué, scope Services, actions owner-confirmées, autre dossier refusé, absence de PII, création atomique, formulaire Web, abonnement et aucun rôle implicite Group.
Flutter : `mobile/test/space_work_g2_depth_test.dart` et `mobile/test/space_work_surface_test.dart` — collections, pagination, états calmes, liens sélectionnables et CTA conditionnel. Le run Flutter, l'analyse/formatage Dart et les essais Android réels ne sont pas certifiés.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_space_work_mt4 organizations.test_space_work_group2 organizations.test_space_work_mt3 organizations.test_space_work_mt2
cd mobile
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter test test/space_work_g2_depth_test.dart test/space_work_surface_test.dart
```

Critères de sortie produit à vérifier dans MT8 : vrais clients Web/Flutter, Espace avec permissions directes, manager Service mandaté, bénéficiaire seul, révocation pendant lecture/action, demande sans JourneyRequest, plusieurs Sessions date-only/all-day, Service sans contexte, contexte Service avec steps/blockers, un owner externe, mode déconnecté, retour, démarrage multiple, et visualisation Compact/Medium/Wide.

## 7. Frontières de MT4 et suite

**Implémentation MT4 G2 : faite dans #522.** À ne pas réinventer : Programme, Session, Inscription, Prestation, Dossier, Requirements, Forms, Payments, Access, preuves et CRM sont déjà des domaines propriétaires distincts. Les tâches suivantes n'ont pas à reconstruire ce qui est implémenté ici.

**MT5** traitera Commerce + Transport, **MT6** Créations + Productions, **MT7** l'assemblage comportemental transversal et la convergence native des outils administratifs propriétaires, **MT8** la QA/validation d'exécution et le jugement de qualité produit. Un chantier ne doit pas annoncer la parité native totale de tous les outils métier si elle reste à livrer dans MT7.

**Aucun changement direct main, aucune migration, aucun merge.** La PR #522 demeure le point d'intégration à revérifier avant tout commit concurrent.

> Makolo marche pour vous. Pas le plaisir de rester. Le plaisir d'avancer.
