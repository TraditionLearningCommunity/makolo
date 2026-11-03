# MT3 — Fermeture des profondeurs Generic / Community de Métier Space

**Date :** 2026-11-01  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Branche/PR :** `fix/discover-a-continuation-context-20261014` / #522.  
**Statut :** périmètre MT3 G1 implémenté côté serveur, Web et Flutter (création native comprise). Tests ciblés ajoutés, **non exécutés** dans cet environnement (pas de checkout Django ni SDK Flutter). Ceci ne certifie pas une exécution E2E ni la validation du formatage Dart. **Ne pas confondre clôture de code MT3 et validation de sortie MT8.**

## 1. Problème résolu

G1 était une grammaire N1 de lecture, dont les objets Generic / Community ouvraient directement une Console ou une profondeur générique. Il fallait rendre l'Activity, l'Occurrence et la démarche compréhensibles et navigables, sans créer un modèle Initiative, reproduire un groupe comme Initiative ni inventer des actions.

La règle reste : **une application, deux clients, profondeur N2 contextuelle, 0..n N3 réels.** Generic et Community partagent la même topologie et le design system, pas un nouveau thème. L'initiative est une Activity contextualisée et l'action terrain une Occurrence réelle.

## 2. Livré côté serveur et Web

- Route N2 protégée : `organizations:space-work-depth` / `<slug>/work/<kind>/<owner_id>/`, pour `activity`, `occurrence` et `journey` lorsque l'archétype est `generic` ou `community`. `SpaceWebMixin` contrôle l'acteur et la responsabilité active ; `build_space_work_projection(kind,id,responsibility)` valide l'identité/propriétaire avant de montrer le détail. Aucun accès cross-Space ou à un owner étranger.
- N1 Generic/Community lie ses lignes vers ce N2, avec `responsibility` et `from=<section>`. Retour aux sections par ancre ; Occurrence ouverte depuis une Activity revient vers son parent, y compris la page de réalisations. Le Web utilise le même shell Makolo.
- Création N1 conditionnelle : pour `generic/community` avec `SPACE_ACTIVITIES_MANAGE` et responsabilité `all`, lien « Nouvelle activité » / « Nouvelle initiative ». Le formulaire canonique `activities:create?space=<slug>` pré-sélectionne uniquement un Space effectivement autorisé, effectue sa propre vérification à l'envoi, appelle `create_activity` et revient à la vue Métier après succès. L'autorité Activity-only ne crée rien pour l'Espace. Aucune deuxième mutation de création, aucune forme métier fictive.
- N2 Activity/Initiative : identité, description et état owner ; réalisations en pages de **12** avec nom, date, statut et navigation. Une Activity durable sans Occurrence reste valide. Une Occurrence qui n'est plus sélectionnable par Work (date passée encore `scheduled`) reste une relation visible, **sans lien mort**.
- N2 Occurrence/action terrain : date/heure/lieu et Activity parente ; `Jour J` visible uniquement si le serveur fournit `open_day_of` et le lien owner. Les URL Jour J conservent la responsabilité.
- N2 Journey/démarche : état owner, activité liée, aucune identité privée bénéficiaire ajoutée. Un vrai `JourneyRequest` lié ouvre **la demande précise** dans la Console existante, via `request=<UUID>&activity=<UUID>&status=all`. `SpaceConsoleRequestsView` filtre cette demande par le sélecteur owner autorisé ; ses décisions restent dans `approve_request/reject_request`. Il n'existe pas de nouvelle mutation générique.
- N3 sous conditions vérifiées : gérer Activity, gérer Resources via `preparation:manage` (exige `ACTIVITY_MANAGE`), Jour J (scope/phase), cas Services (operator scope et `ServiceJourneyContext`), Funding (uniquement `FundingDetails` réellement présent et `can_manage_funding`). Aucun Funding obligatoire ni autorité par GroupMembership.

## 3. Livraison native / Flutter

Le N1 `SpaceWorkSurface` existant ouvre déjà `/space/:slug/retrieval/:kind/:id`. Le détail `SpaceRetrievalOwnerScreen` relit systématiquement l'owner sous l'acteur et la perspective actifs. MT3 le complète :

- Création G1 désormais native, pas reportée à MT7 : `SpaceWorkSurface` propose « Nouvelle activité » ou « Nouvelle initiative » seulement lorsque `responsibility=all`, `SPACE_ACTIVITIES_MANAGE` et `resolve_entitlement(space, 'activities.create').allowed` sont établis par le serveur. Le formulaire `SpaceWorkCreateActivityScreen` envoie un POST connecté à `/api/v1/organizations/workspaces/<slug>/work/activities/` ; `SpaceG1ActivityCreateAPIView` impose l'acteur, l'archétype et la permission, valide les mêmes champs que `ActivityCreateForm`, délègue `create_activity` au propriétaire canonique et renvoie un brouillon. Aucune création n'est confirmée hors ligne. Après une réponse réseau ambiguë, le client ne renvoie pas automatiquement le POST ; il invite à vérifier Métier.
- Pour une sélection Activity Generic/Community, l'API Work renvoie `selection.related_occurrences` : liste bornée de **12**, `offset`, `limit`, `has_more`, `openable`. Pas de vue complète persistance, ni média privé, ni données bénéficiaires.
- `related_offset` est un paramètre GET borné à 0–10 000, valide seulement pour une Activity sélectionnée ; chaque page redemande au serveur une sélection autorisée. Le mobile affiche pages suivantes/précédentes et suit les liens uniquement si l'Occurrence est réellement sélectionnable.
- `SpaceWorkG1Realizations` représente les faits dans les composants natifs communs : « Actions et réalisations » pour Community, « Dates et réalisations » pour Generic, calme réel sans fausse Occurrence.
- Une démarche ne propose « Examiner la demande » que quand `owner_handoffs` contient `open_request` avec l'identité réelle `journey_request`. La route `/space/requests/:id` et son action native owner réévaluent les droits et ne mutent jamais en cache.
- Jour J reste la route native `/space/occurrences/:id/day-of` déjà en place. Pas d'ouverture simulée d'une page Web propriétaire à la place d'un écran Flutter ni de mutation hors ligne inventée.

**Limite restante hors spécialité MT3 :** les outils administratifs propriétaires Resources/Funding/Service n'ont pas tous une profondeur opérateur Flutter équivalente ; leur convergence transverse relève de MT4–MT7. La création G1 native et son endpoint serveur sont implémentés ici. Une commande de création incertaine n'est pas rejouée automatiquement : aucune déduplication serveur générique n'a été inventée.

## 4. Fichiers MT3 modifiés ou créés

- `organizations/space_work_g1_web.py` : N2 G1 et N3 autorisés.
- `templates/organizations/space/work_depth.html` : profondeur Web et liens sans impasses.
- `organizations/space_work_web.py` : N1 → N2 G1 avec origine/responsabilité.
- `organizations/urls.py` : URL N2 dédiée.
- `organizations/console_views.py` : filtrage exact du `JourneyRequest` owner déjà visible dans la Console.
- `activities/views.py`, `templates/activities/activity_form.html` : contexte Space G1 sécurisé sur le formulaire Activity canonique.
- `templates/organizations/space/work.html` : CTA de création G1 seulement lorsque l'autorité effective le permet.
- `organizations/api/space_work_views.py` : validation de `related_offset`.
- `organizations/api/space_activity_create.py`, `organizations/api/urls.py` : création G1 native avec autorité, formulaire et service propriétaire ; `space_work_projection.py` tient compte de l'entitlement Space.
- `organizations/api/space_work_projection.py` : relation d'Occurrences bornée, source/propriétaire, règle commune d'ouvrabilité.
- `mobile/lib/features/continuity/space_retrieval_owner_screen.dart` : sélection, pagination, détail lié, demande owner.
- `mobile/lib/features/space/space_work_g1_realizations.dart` : composant natif G1 partagé.
- `mobile/lib/features/space/space_work_create_activity_screen.dart`, `mobile/lib/app/router.dart`, `mobile/lib/features/space/space_work_surface.dart` : formulaire natif sous acteur Space, confirmation et reprise sans double émission.
- `organizations/test_space_work_mt3.py` : tests Web/API de profondeur, scopes, revocation, pages, état ancien, JourneyRequest exact, Funding et case Service.
- `mobile/test/space_work_g1_realizations_test.dart` : tests de calme, pagination, non-navigable, navigation autorisée.
- `organizations/test_space_work_mt3_native_create.py` : POST, ownership, refus Mandate, validation, entitlement.
- `mobile/test/space_work_surface_test.dart` : visibilité conditionnelle du CTA natif G1.
- Cette documentation.

**Aucun nouveau modèle, migration, tableau de tâches générique, statut de Readiness ni permission introduits.**

## 5. Gates de vérification ciblés

Pas de CI bloquante demandée par le commanditaire, mais les tests ne doivent pas être déclarés « verts » sans exécution.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_space_work_mt3 organizations.test_space_work_mt3_native_create organizations.test_space_work_mt2 organizations.test_zs3_space_work_api organizations.test_ws3_space_work_web
cd mobile
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter test test/space_work_g1_realizations_test.dart test/space_work_surface_test.dart
```

Le formatter Flutter canonique est obligatoire avant de déclarer une modification Dart prête à fusionner. Ce checkout distant ne dispose pas du SDK Dart local ; aucune validation de format, analyse Flutter ou capture visuelle n'a été prétendue dans cette session.

Cas réels QA : création G1 en brouillon, sélection et retour Space, refus d'un POST forgé sans Permission, acteur Space autorisé, Mandate limité, revoked, Group sans droit, Activity durable sans Occurrence, 13+ Occurrences, ancien scheduled, demande réelle et inexistante, case Service sous scope, Funding optionnel, jour J hors phase et en phase, retour au parent et au N1, passage Web↔Flutter, rotation/compact et état offline.

## 6. Frontières et handoff

**MT3 n'est pas MT4/MT5/MT6** : pas d'interface Programme/Dossier Service/Offre/Véhicule/Production fabriquée. **MT7** conserve le mandat d'assemblage comportemental transversal et de convergence native des outils propriétaires déjà exposés ; **MT8** porte les QA Web/Flutter/permissions/visuelles, la validation d'exécution et le merge gate.

Le travail restant sur MT3 après ce checkpoint est **la validation réelle des tests/formatter et des parcours**, pas une nouvelle cartographie ni un nouveau moteur métier. Aucun merge demandé ni effectué.

**Makolo marche pour vous. Pas le plaisir de rester ; le plaisir d'avancer.**
