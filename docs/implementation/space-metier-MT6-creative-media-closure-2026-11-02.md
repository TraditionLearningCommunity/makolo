# MT6 — Créations / Productions : fermeture des profondeurs Métier N1 → N2 → N3

**Date :** 2 novembre 2026. **Dépôt :** `TraditionLearningCommunity/makolo`. **Branche et PR :** `fix/discover-a-continuation-context-20261014` / **#522**.

**Statut précis :** périmètre MT6 implémenté **dans le code serveur, Web et Flutter**, avec tests ciblés ajoutés. **Exécution Django/PostgreSQL/Flutter, formatage Dart canonique, QA sur appareil et E2E non attestés dans cette session.** Aucun merge dans `main`. Ne pas présenter MT6 comme certifié en production ni comme CI verte.

## 1. Problème résolu et frontières

Les deux grammaires N1 étaient déjà composées au groupe 4. Elles étaient toutefois surtout des entrées de lecture vers des outils existants. MT6 ajoute une véritable profondeur métier Creative/Media sans reconstruire MT1–MT5.

| Langue UX | Identité durable réelle | Réalisation datée | Règle |
| --- | --- | --- | --- |
| Creative — Créations | `Activity` | `Occurrence` (présentation, spectacle, réalisation) | Œuvre première ; commerce éventuel secondaire et réellement présent |
| Media — Productions | `Activity` | `Occurrence` (édition, épisode, réalisation) | Une édition n'est jamais la production entière |

**Pas de modèles `Creation`, `Production`, `Post`, `Feed` ou portfolio parallèle.** Pas de nouveau statut « en création », avancement chiffré, diffusion automatisée, audience, score ni paiement fictif. Les actions restent celles des vrais owners (Activity/Occurrence/Preparation/Presentation/Operations), avec leurs propres contrôles.

## 2. N1 → N2 et sélection propriétaire

- Les lignes d'Activity et d'Occurrence Creative/Media ouvrent maintenant `organizations:space-work-depth-g4` au lieu de tomber directement dans une Console générique. Le lien transporte la responsabilité courante et la section d'origine.
- Chaque GET N2 reconstruit `build_space_work_projection` avec le viewer, le Space, la responsabilité et la source précise ; aucune URL issue du client ne constitue une permission. Source non visible, activité étrangère, mandat retiré ou archétype inadapté : pas de contenu N2.
- Une Activity Creative/Media sélectionnée expose `related_occurrences` paginées à 12, avec `openable`, `offset`, `has_more`, `coverage_state`. Le détail `g4_detail` est dérivé de la même Activity autorisée (description et grammaire Creative/Media), sans état enregistré dans Presentation.
- Les dates passées encore `scheduled` restent reconnaissables comme relation mais ne deviennent pas un lien de profondeur trompeur.

## 3. Web — Création / Production, profondeur et vrais N3

Nouvelle vue `organizations/space_work_g4_web.py` et nouveau template `templates/organizations/space/work_g4_depth.html` :

- N2 de création ou production : identité, résumé, description owner, statut, éventuel média de reconnaissance publié et permis, prochaines dates connues et réalisations liées paginées.
- N2 d'Occurrence : présentation/édition précise, date, heure, lieu s'ils sont réellement établis, activité parente et navigation de retour vers celle-ci lorsque visible.
- N3 conditionnels : gérer l'Activity (Console propriétaire), gérer ses Resources (Preparation), ouvrir l'atelier de présentation et de médias (Presentation) seulement sous `ACTIVITY_MANAGE` et capacité de gestion, et Jour J uniquement si le propriétaire le rend effectivement disponible.
- Pas de lien factice vers création d'édition, CMS, vente, « publier », paiement ou Live. Les outils plus profonds restent chez leurs owners.
- Création Web depuis N1 : **Nouvelle création** / **Nouvelle production**, utilisant le formulaire et `activities.services.create_activity` existants pour créer un brouillon, sous `SPACE_ACTIVITIES_MANAGE` et entitlement du Space.

## 4. Flutter — même vérité, comportement natif

- Nouveau `mobile/lib/features/space/space_work_g4_depth.dart`, intégré dans `SpaceRetrievalOwnerScreen`. Identité Work relue sous l'acteur Space et la responsabilité actifs, présentation Creative ou Media distincte, description, dates liées, pages, actions d'ouverture seulement pour les Occurrences réellement sélectionnables.
- Le N1 affiche conditionnellement une vignette seulement si le serveur fournit un `PresentationMediaUse` publié de reconnaissance ; la destination doit être first-party et la liaison correspondre **exactement** à la source visible (kind/id). Aucun fichier privé nu ou image d'une autre édition n'est promu.
- Le N2 natif ne présente de visuel que si `owner.kind/id` correspond à l'Activity/Occurrence ouverte, avec URL publique canonique autorisée. En absence de visuel, le métier reste lisible.
- La création native réutilise `SpaceWorkCreateActivityScreen` et l'endpoint `workspace-work-activity-create`, avec vocabulaire « création » ou « production », POST serveur et confirmation explicite. Le client ne refait pas automatiquement un POST dont le résultat est incertain.
- Les changements d'acteur/portée et la révocation passent par les mécanismes préexistants de Work ; une donnée stockée localement ne devient ni une permission ni la confirmation d'une action hors ligne.

## 5. Fichiers de livraison

**Serveur/Web :** `organizations/api/space_work_projection.py`, `organizations/api/space_activity_create.py`, `organizations/space_work_web.py`, `organizations/space_work_g4_web.py`, `organizations/urls.py`, `activities/views.py`, `templates/organizations/space/work_g4_depth.html`.

**Flutter :** `mobile/lib/features/space/space_work_g4_depth.dart`, `mobile/lib/features/continuity/space_retrieval_owner_screen.dart`, `mobile/lib/features/space/space_work_surface.dart`, `mobile/lib/features/space/space_work_create_activity_screen.dart`, `mobile/lib/features/space/space_shell_routes.dart`, `mobile/lib/features/space/space_work_collection_screen.dart`, `mobile/lib/app/router.dart`.

**Tests ajoutés :** `organizations/test_space_work_mt6.py`, extension de `organizations/test_space_work_group4.py`, `mobile/test/space_work_g4_depth_test.dart`.

**Nouveaux modèles/migrations : aucun. Nouveau endpoint métier de mutation : aucun.** La nouvelle profondeur Web est une route de présentation, tandis que l'API Work reçoit des champs additionnels owner-backed.

## 6. Vérifications à exécuter avant certification

Les tests sont **écrits mais non exécutés** dans l'environnement distant de cette session. L'absence de SDK Dart/Flutter local interdit de revendiquer un formatage canonique effectué.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_space_work_mt6 organizations.test_space_work_group4 organizations.test_space_work_mt5 organizations.test_space_work_mt4 organizations.test_space_work_mt3 organizations.test_space_work_mt2
cd mobile
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter analyze
flutter test test/space_work_g4_depth_test.dart test/space_work_surface_test.dart
```

Puis QA réelle Web/Android Compact/Medium/Wide : Space vide et calme, Activity durable sans Occurrence, date passée non ouvrable, 13+ dates et retour à la bonne page, acteur et responsabilité changés, lien direct étranger, Mandate limité/révoqué, brouillon créé une seule fois malgré réponse réseau incertaine, visuel publié puis retiré, Space privé, image d'Occurrence non attribuée à sa sœur/Activity, absence de média, Jour J hors phase puis en phase. Contrôler les gates de la PR et ses collisions concurrentes avant fusion.

## 7. Handoff après MT6

**MT7** : cohérence transverse et continuité N1/N2/N3 entre huit grammaires, contexte de retour, accessibilité, local-first, et convergence des opérations propriétaires complexes uniquement lorsqu'une véritable profondeur native est requise. Cela ne justifie pas de dupliquer Activity, Occurrence, Journey, Resource, Payment ou Presentation.

**MT8** : exécuter tests et formatage canonique, PostgreSQL si pertinent, sécurité/IDOR/révocation, QA visuelle Web/Flutter et E2E ; corriger les causes racines et ne pas merger si les gates pertinentes restent rouges.

**MT6 = implémenté en source sur #522, non certifié par exécution.** Le plan d'orchestration du 31 octobre reste le contrat directeur ; il faut lire le code actualisé plutôt que supposer que les manques de l'état historique du 31 octobre persistent.

> Makolo marche pour vous. Pas le plaisir de rester. Le plaisir d'avancer.
