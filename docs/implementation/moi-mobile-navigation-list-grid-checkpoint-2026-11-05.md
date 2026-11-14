# Moi Mobile — navigation compacte et profondeurs directes

**PR :** #522 · **Date :** 2026-11-05 · **État :** modifications poussées, pas de merge.

## Décision produit

Moi répond à ce qui est déjà en place autour d'une personne pour faciliter la suite.
La racine ne déroule plus un inventaire : elle propose des destinations directes.

1. Identité personnelle, avatar, modification.
2. Passeport Makolo (projection et partage existants).
3. Deux raccourcis : **Mes projets** et **Mes dossiers**. L'organisation interne des Projets/Dossiers reste un chantier distinct.
4. Choix **Liste / Grille**, conservé localement par Profil.
5. Territoires de premier niveau, dans l'ordre :
   - Mes accès ;
   - Ce qui compte pour moi (centres d'intérêt et « Ouvert à » seulement) ;
   - Mes veilles ;
   - Mes enregistrements ;
   - Mes suivis (personnes et Espaces) ;
   - Mes collectifs ;
   - Mes ressources ;
   - Mon historique ;
   - Mes appuis, seulement si réellement disponibles.

**Liste :** titre, contexte court et au plus trois éléments tirés des projections existantes, lorsqu'ils sont connus.
**Grille :** icône et titre, sans liste embarquée.
Un clic sur le territoire ouvre immédiatement sa profondeur. Un aperçu ouvre le détail seulement si une route owner-backed existe.
Les profondeurs conservent le chargement automatique sans pagination visible, puis « Vous avez tout vu » quand l'épuisement est connu.

## Réutilisation technique

- `mobile/lib/features/me/me_screen.dart` : identité/Passeport et composition courte ;
- `mobile/lib/features/me/me_hub.dart` : choix local et index ; trois aperçus Access/History issus des snapshots **du même Profil**, sans API parallèle ;
- `me_routes.dart` : directions existantes (`/accesses`, `/history`, `/discover/watches`, `/me/saved`, `/me/considerations`, `/me/collectives`, `/me/resources`) ;
- `me_follows_screen.dart` : projection personnelle `followed_spaces` / `followed_profiles`, pagination de famille spécifique, sans nouvelle vérité ;
- `me_support_screen.dart` : lecture des seuls appuis déclarés par le serveur. Pas de fausse mutation ni de fausse profondeur métier ;
- `objectives/api_views.py`, `objectives/api_urls.py` : deux collections de lecture autorisées, sans modèles ni migrations nouveaux ;
- `objective_repository.dart` et `objective_collection_screen.dart` : collection locale owner-backed, ouverture des détails Dossier/Project existants ; **aucune gestion Project→Dossier traitée ici**.

Le serveur filtre l'autorité avec les sélecteurs `dossiers_for_profile` et `projects_for_profile`. Les éléments personnels et les autres éléments visibles sont distingués sans transfert de permissions. Les détails vérifient encore l'accès côté propriétaire.

## Frontières non négociables

- Le Profile est une personne globale.
- Dossier = objectif composé ; Project = horizon durable, pas un gestionnaire de tâches.
- Le lien Project–Dossier n'autorise aucune visibilité ou mutation implicite.
- Assignment est une responsabilité ; Mandate/Permission reste une autorité.
- Access, AccessCredential, AccessUse, PersonalAsset, Proof et Credential Trust restent distincts.
- Le mode d'affichage est une préférence de ce seul appareil et Profil. Il ne crée pas de nouveau modèle métier.
- Les données démo ne dictent pas la hiérarchie de l'app.

## Contrôles ajoutés et limites de fermeture

- `mobile/test/me_mature_test.dart` : racine, raccourcis, bascule Liste/Grille, trois aperçus, liens de détail et états ;
- `objectives/test_objective_collection_api.py` : filtrage par viewer, continuation bornée, erreurs d'arguments et refus anonyme.

Aucun merge. Aucun contournement de test.
Formatage Dart, tests ciblés Flutter/Django et vérification Android **non exécutés dans l'environnement de cette intervention**.
La profondeur Mes appuis reste une synthèse sans actions natives supplémentaires, conformément aux surfaces propriétaires actuellement vérifiées.

**Reporté volontairement :** composition hiérarchique des Projets contenant leurs Dossiers, Dossiers hors Projet, déplacements/ajouts de Dossiers, collaboration et mutations propriétaires.
