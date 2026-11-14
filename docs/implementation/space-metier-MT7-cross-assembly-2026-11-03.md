# MT7 — Assemblage transversal de Métier Space (8 archétypes)

**Date :** 3 novembre 2026  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Branche de travail unique :** `fix/discover-a-continuation-context-20261014` — **PR #522**.  
**Base historique du chantier :** `51a7d9e6afc077f00e650cdefd53a263eb09129e` (simple point de départ, pas le HEAD courant).  
**Intégration :** les sources et tests MT7 sont désormais présents directement dans #522. La PR intermédiaire #533 a été **fermée sans merge** ; elle ne doit pas servir de branche ou de cible d'intégration. **Aucune modification directe de `main`.**

**Statut : implémentation source MT7 poussée, tests ajoutés mais non exécutés.** Le dépôt est modifié en parallèle sur #522 : réconcilier son HEAD, vérifier l'absence de conflits et exécuter les gates avant fusion. Ce checkpoint ne donne aucune autorisation de merge avec CI rouge.

## 1. Problème utilisateur et décision d'architecture

Les huit archétypes disposent de leurs `N1` et de plusieurs profondeurs `N2/N3` des MT3–MT6, mais l'assemblage était inégal : la composition `business_world.reading_groups` du serveur était ignorée dans le client Flutter, les cartes avaient une même lecture générique, les longues collections Web n'avaient pas de vraie pagination native, les profondeurs oubliaient leur section et leur page de départ, et les `owner_handoffs` étaient traités au cas par cas.

**Décision :** assemblage de présentation et navigation **sans nouvelle table, nouveau lifecycle, nouvelle Permission, ni mutation propriétaire**. Les huit grammaires restent des projections des faits Activity/Occurrence/Journey/Commerce/Transport/Services/Presentation. Tout accès ou mutation doit rester autorisé par l'owner serveur au moment de la requête.

## 2. Matrice d'assemblage (N1, N2, N3)

| Archétype | Chapitres N1 (composition serveur) | N2 existant | N3 réel et borné |
| --- | --- | --- | --- |
| `generic` | Continuité, Activités, spécialités réelles | G1 Activity/Occurrence/Journey | Resources, Activity, demandes et Jour J autorisés |
| `community` | Initiatives et terrain | G1 | Funding uniquement si réel, Resources, Journey, Jour J |
| `education` | Programmes, Sessions, Inscriptions | G2 Activity/Occurrence/Journey | Inscription exacte, Forms et Resources au propriétaire |
| `service_provider` | Demandes, Dossiers, Prestations | G2 | ServiceCase natif (lorsque réellement offert) ou Web owner |
| `commerce` | Commandes, Disponibilités, Offres | G3 Activity/Offer/Order | Modification Offer par owner ; paiement/remise jamais inférés |
| `transport_operator` | Départs, Routes, Véhicules, Services | G3 | Départ/exploitation et Jour J conditionnels, Capacity/Vehicle distincts |
| `creative` | Œuvres, présentations, créations durables | G4 Activity/Occurrence | Resources et atelier Presentation owner, média de reconnaissance publié |
| `media` | Productions, éditions, réalisations | G4 | Même garde, une édition n'est pas une production et un média n'est pas une Publication propriétaire |

Les structures et dates n'ont pas été remodelées. L'archétype change le **langage et le groupement**, jamais les droits du lecteur.

## 3. Flutter : N1 → N2 → N3

- `SpaceWorkSurface` consomme l'ordre `presentation.section_order`, les groupes `presentation.reading_groups`, la question métier et le message calme. Les sections inconnues mais réellement visibles sont conservées en secours, sans classement/ranking mobile. Les lignes en continuation même temporairement vides restent actionnables.
- Les Activity sont reconnues selon la grammaire Space (Activité, Initiative, Programme, Prestation, Commerce, Service Transport, Création, Production) via le contexte et des icônes sémantiques ; statut, prochaine date, prix, capacité et médias ne sont affichés que s'ils proviennent réellement du serveur.
- `spaceWorkOwnerRoute` véhicule uniquement `work_section` et `work_collection`, bornés à des sections connues. Il ne véhicule aucune autorité.
- `SpaceRetrievalOwnerScreen` ouvre le vrai owner par l'API courante, contrôle Space ID, responsabilité, owner kind/id et acteur courant. Il présente `Retour à Métier`, utilise le vrai stack de navigation quand il existe, et offre un fallback vers le root ou la collection si la profondeur vient d'un deep link.
- Les widgets G1/G2/G3/G4 propagent le même contexte vers les Occurrences, démarches, offres et autres sous-profondeurs réellement ouvrables.
- Nouveau `SpaceWorkOwnerActions` : seules les destinations **API first-party, owner-identifiées, explicitement autorisées et implémentées nativement** sont offertes (`open_request`, `open_service_case_native`, `open_day_of` quand ouvert). Aucune URL Web n'est traitée comme une route native, et aucun lien ne devient permission.
- La racine Space reste local-first : lecture depuis les projections synchronisées existantes ; un snapshot ancien ne crée pas un droit, et les profondeurs reconsultent toujours le serveur. La modification ne crée pas de confirmation offline fictive.

## 4. Web : collections, retours et handoffs

- Nouvelle route `/spaces/<slug>/work/collection/<section>/` (`organizations:space-work-collection`) ; chaque page de 12 éléments interroge le **même `build_space_work_projection`**, autorisé pour le viewer, Space et Mandate présents. L'offset est borné et le résultat indique sa couverture partielle.
- Les boutons `Afficher la suite` du N1 ouvrent cette collection plutôt qu'un cul-de-sac. Pages suivantes/précédentes, lien de retour à Métier, section et responsabilité explicites. Les collections vides ne prétendent pas que tout l'Espace est vide.
- `work_origin_page` accompagne les liens des N2 G1–G4 depuis une collection et traverse leurs sous-liens Work/parents/pages sans confondre page d'origine Work et pagination des relations N2. Le bouton retour renvoie à la **page de la collection** sous la même responsabilité.
- Les URLs étrangères, les autres canaux et les handoffs sans correspondance owner/capability ne deviennent pas des actions Web. Seul un `open_service_case` Web déjà fourni sous `open_service_case` et `links.detail` correspondant est affiché comme action secondaire.
- `Rechercher` et `Historique` pointent vers les surfaces Space déjà propriétaires, avec la responsabilité active conservée.

## 5. Frontières canoniques et sécurité

- **Profile reste global** ; **Space reste acteur collectif**, sans permission dérivée de Membership/Assignment/Group/Team.
- **Mandate/Permission** restent serveur ; autorité et source owner revérifiées à chaque N2, page paginée et N3.
- **Activity ≠ Occurrence ≠ Journey** ; pas de nouveau `WorkItem`, `Post`, `Feed`, `Continuity` persistant ou Readiness universel.
- Pas de duplication de Payment, Capacity, Access, Resource, Proof, Credential ou PresentationMediaUse. Aucun état de paiement ni droit d'accès n'est inféré.
- Les pages et les origines sont des **indices de navigation non sensibles**, jamais un élargissement du scope ; aucun retour sur une page 2 n'accorde l'accès à une ligne retirée.

## 6. Fichiers livrés

**Serveur et Web :**
- `organizations/space_work_navigation.py` (nouveau)
- `organizations/space_work_web.py`, `organizations/space_work_g1_web.py`, `organizations/space_work_g2_web.py`, `organizations/space_work_g3_web.py`, `organizations/space_work_g4_web.py`, `organizations/urls.py`
- `templates/organizations/space/work.html`
- `organizations/test_space_work_mt7.py` (nouveau)

**Flutter :**
- `mobile/lib/presentation/contracts/space_presentation.dart`
- `mobile/lib/features/space/space_work_surface.dart`
- `mobile/lib/features/continuity/space_retrieval_owner_screen.dart`
- `mobile/lib/features/space/space_work_g1_realizations.dart`, `space_work_g2_depth.dart`, `space_work_g3_depth.dart`, `space_work_g4_depth.dart`
- `mobile/lib/features/space/space_work_owner_actions.dart` (nouveau)
- `mobile/lib/app/router.dart`
- `mobile/test/space_work_mt7_test.dart` (nouveau)

## 7. Validation à exécuter — gate MT7/MT8

Les tests ont été écrits, **aucune exécution Django/Flutter ou PostgreSQL, aucune validation device ni E2E n'a été obtenue dans cette session**. Une relecture source n'est pas un test réussi.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_space_work_mt7 organizations.test_space_work_mt6 organizations.test_space_work_mt5 organizations.test_space_work_mt4 organizations.test_space_work_mt3 organizations.test_space_work_mt2 organizations.test_ws3_space_work_web organizations.test_zs3_space_work_api
cd mobile
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter analyze
flutter test test/space_work_mt7_test.dart test/space_work_surface_test.dart test/space_work_g1_realizations_test.dart test/space_work_g2_depth_test.dart test/space_work_g3_depth_test.dart test/space_work_g4_depth_test.dart
```

Puis Web/Android sur Compact 360 et 430 dp, Medium 834, Wide 1440 et Very Wide 1728 ; texte 1.0/1.3/1.6 ; claviers, lecteur d'écran, lecteurs de média autorisés. Couvrir huit archétypes, 13+ éléments, retour N3→N2→page2 N1, navigation en direct sans historique, action Web sans route native, mandat Activity limité, révocation en cours de lecture, changement d'acteur, offline avec snapshot daté, public/privé, 404/403/401, absence de faux état « tout est en ordre ».

**Dépendance d'intégration :** #522 évolue en parallèle. Reprendre son HEAD, auditer les collisions sur `space_work_surface.dart`, `space_work_g2_depth.dart`, `app/router.dart` et réconcilier les autres changements avant merge. Ne pas fusionner si CI est rouge. Aucun déploiement autorisé sur ce checkpoint.

## 8. Résultat et passage MT8

**MT7 implémenté en source**, non encore **certifié**. L'intégration reste sous réserve du formatage Dart canonique, des tests Django/PostgreSQL, Flutter, tests de navigation et revue visuelle réelle. MT8 peut désormais contrôler cette chaîne commune et corriger les bugs observables plutôt que reconstruire les huit verticales.

> **Makolo marche pour vous. Pas le plaisir de rester. Le plaisir d'avancer.**
