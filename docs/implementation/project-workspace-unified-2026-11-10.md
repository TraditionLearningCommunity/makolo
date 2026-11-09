# Projet — espace unique Profil / Espace (PR #522)

**Date :** 2026-11-10  
**État :** implémentation sur la branche de PR, validation d'exécution à effectuer avant intégration.

## Principe

Il n'existe qu'un seul modèle `Project`, une seule projection `project_workspace()`, une seule vue de détail native `ProjectWorkspaceScreen` et une seule présentation Web `project_detail`. Les contextes `owner_profile` et `owning_space` changent l'autorité et les données, pas la structure des vues, menus, filtres ou cartes. La vérité des Dossiers, Journeys et permissions reste canonique.

## Contrat serveur

- `Project` possède **exactement un** porteur Profil ou Espace.
- `Authorization.Mandate` introduit la portée `project` (migration additive `authorization.0018_project_scope`) avec les rôles système `project-viewer`, `project-manager`, `project-admin`. Aucun modèle de membre Project parallèle.
- `project.view` permet la lecture du Projet. `project.manage` permet ses actions de gestion. `project.authority.manage` gouverne l'administration des mandats Projet.
- Les héritages préexistants `SPACE_VIEW` et `SPACE_MANAGE` continuent de s'appliquer aux Projets d'Espace. L'autorité du porteur Profil personnel reste explicite.
- Un mandat **Projet** ne confère **aucun** droit de consulter, créer ou gérer les Dossiers ou Journeys rattachés. Ces derniers restent filtrés par leurs selectors et services propriétaires.
- La capability `project.dossier.create` est exposée seulement lorsque le serveur autorise également la création d'un Dossier avec le même porteur, et non sur la seule base du droit de gestion Projet.
- `GET /api/v1/objectives/projects/<uuid>/` enrichit la projection avec `collaboration` : mandats Project autorisés à être divulgués, responsabilités `DossierAssignment` issues des Dossiers visibles, rôles et candidats bornés, indicateurs de vue partielle. Les personnes masquées ou liées à un Dossier invisible ne sont pas déduites.
- `POST /api/v1/objectives/projects/<uuid>/authority/` délègue exclusivement aux services Objectives/Authorization. `grant` accepte `profile_id` **ou** l'e-mail exact d'un compte existant et actif avec un rôle Project whitelisté ; `revoke` exige un `mandate_id` du Projet ciblé. Le serveur réévalue l'autorité à chaque appel.
- Le Web utilise `POST /objectives/projects/<uuid>/authority/` (route nommée `objectives:project-authority`) avec les mêmes services canoniques. CSRF et contrôle de rôle restent requis.

## Présentation

- En-tête Projet plus compact, lecture de l'horizon et actions contextuelles regroupées.
- Vues `Synthèse`, `Dossiers`, `Calendrier` identiques en contexte Profil ou Espace. Sur écran étroit, les trois modes tiennent dans une même rangée sans passer un onglet à la ligne.
- Cartes Dossier plus compactes sans troncature des objectifs. Recherche, tri, filtres et calendrier déjà acquis préservés.
- Section `Personnes et responsabilités` : distinguer mandats Project et Assignment de coordination dans des Dossiers visibles. L'absence de membres n'implique pas l'absence de collaborateurs cachés.
- La révocation explicite 403/404 d'un détail Projet supprime la projection locale et les collections remplaçables Objectives concernées dans le profil courant. Une défaillance de transport ne provoque jamais une telle purge.

## Contrôles importants

1. Un mandataire `project-viewer` voit le Projet mais **pas** les Dossiers privés ni les autres mandats non divulgués.
2. Un `project-manager` peut modifier le Projet mais ne peut pas créer un Dossier personnel appartenant à un autre Profil.
3. L'administrateur Projet peut accorder ou retirer un mandat et le retrait coupe l'accès dès la prochaine relecture propriétaire.
4. Des `DossierAssignment` apparaissent comme interventions, **sans** devenir des mandats Projet.
5. Les revocations/expirations et les requêtes vers un autre Projet sont refusées.
6. Un Projet d'Espace conserve le même écran et ses permissions canoniques de SPACE, sans duplication de flux.

## Validation encore requise

Le changement a été poussé sans attendre la CI à la demande. Les tests Django ciblés ont été **ajoutés**, mais pas exécutés depuis cette session ; aucun test Flutter/Android ni smoke test Web n'est attesté. Avant fusion, vérifier les migrations, les tests de sécurité, le formatage/analyse Flutter et les parcours réels sur émulateur.

La branche #522 reste ouverte : aucun merge n'est autorisé tant que les contrôles requis sont rouges.
