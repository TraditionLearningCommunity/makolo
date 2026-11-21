# Dossier — D1 et D2 : contexte, autorité et projection canonique

Date : 10 novembre 2026. Chantier : PR #522 sur la branche fix/discover-a-continuation-context-20261014.
Nature : checkpoint technique ; il ne certifie ni CI entièrement verte ni recette Android.

## Règles préservées

Un Dossier conserve son identité et ses relations réelles lorsqu'un membre travaille dans plusieurs Projets ou plusieurs Espaces. Le Profil authentifié reste l'acteur humain et le seul principal de sécurité. L'Espace actif est une portée de présentation, jamais un mandat ou une permission créée côté client.

Il existe un seul détail Dossier Flutter, une projection partagée Web/Flutter, et un seul service propriétaire par mutation. Le Dossier garde au maximum un Projet parent actif. Assignment ne vaut pas Permission. Journey, Readiness, Requirement, Access, Capacity, Commerce, Payment, Ressources et Conversations demeurent leurs propres sources de vérité.

## D1 — Contextes et contrôles serveur

- Résolution de contexte centralisée dans objectives/context.py.
- Contexte facultatif sur les endpoints Objectives existants : context=space et space=<slug> ; aucun nouveau endpoint ni modèle.
- La portée Espace filtre les querysets déjà autorisés ; l'identité utilisateur provient toujours de request.user.
- Le détail Dossier, ses mutations et les destinations Projet refusent un contexte Espace différent de l'Espace porteur. Les collections Projet/Dossier et l'Organizer appliquent également la portée demandée.
- Création explicite sous Espace : le serveur utilise cet Espace porteur et refuse un owning_space_id contradictoire.
- Contexte mal formé ou tentative de profile_id, actor_id ou viewer_id client : 400. Objet hors portée ou invisible : 404. Refus métier par le service propriétaire : 403.
- Les appels sans contexte, ou en contexte personal, conservent l'index transcontextuel autorisé du Profil : les Dossiers d'Espaces autorisés restent accessibles, sans être présentés comme personnellement possédés.
- Sous Espace, l'Organizer ne montre que les Projets/Dossiers visibles de cet Espace et les Journeys du participant réellement liées à ces Dossiers. Le détail Dossier utilise son propre selector de Journeys visibles.

## D2 — Composition du Dossier

La projection objectives/dossier_workspace.py conserve identité, objectif, lifecycle, échéance, Projet parent visible, Journeys visibles, dépendances, Readiness partielle, responsabilités, mandats, candidats, transitions, capacités et liens owner.

Nouveaux champs de projection : viewer (Profil authentifié), actor_context (portée de consultation) et owner.id / owner.slug (porteur réel). Les liens self/actions conservent le contexte demandé. Les candidats Projet sont filtrés par contexte et par can_manage_project côté serveur.

Aucune donnée métier source n'est copiée dans Dossier. Les actions restent des handoffs vers les propriétaires canoniques.

## Flutter local-first

La route existante /dossiers/:id ouvre DossierWorkspaceScreen. ActorContextController fournit le contexte actif. ObjectiveRepository conserve une clé historique par Profil pour les consultations non contextualisées et utilise une clé distincte par Dossier/Espace pour les consultations contextualisées. La transition d'acteur rebinde les streams et revalide le détail ; les commandes passent le même contexte que la lecture. Aucun succès métier n'est fabriqué hors ligne.

## Couverture

Nouveau test backend : objectives/test_dossier_actor_context.py (identité stable, deux Espaces, non-divulgation inter-Espace, destination Projet, création, Organizer, rejet d'override). Nouveau test Flutter : mobile/test/objective_dossier_context_test.dart (clés de cache et URL de contexte).

Tests de régression existants : objectives/test_d3_collaboration.py, objectives/test_workspace_read_models.py, objectives/test_objective_collection_api.py, objectives/test_organizer_collection.py, mobile/test/actor_context_test.dart et mobile/test/objective_organizer_sync_test.dart.

Un correctif de graph de migrations sans aucune opération SQL est présent : authorization/migrations/0019_merge_project_scope_recognition.py. Il réunit deux feuilles 0018 additives (Project scope et Recognition permissions). Il ne supprime ni tables ni données.

## Gates et suites

Le workflow API Contract est passé vert après la fusion des migrations. Les autres suites (Django, Flutter, PostgreSQL, E2E) et les scénarios Android doivent être vérifiés sur le HEAD final, et la PR ne doit pas être mergée si la CI reste rouge. L'audit d'UX visuelle complète, des modes de présentation et des retours Profil/Espace appartient à D3/D4/D5 ; aucun écran Dossier parallèle ne doit être introduit.
