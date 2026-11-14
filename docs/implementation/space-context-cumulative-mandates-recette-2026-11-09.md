# Recette Space — Contexte par avatar et autorisations cumulatives

**Date :** 2026-11-09  
**Cible :** PR #522  
**Nature :** correction UX + préservation des mandats canoniques existants ; aucune migration.

## Décision UX

- L'en-tête Space affiche l'avatar de l'acteur actif. Les deux boutons contextuels redondants (nom de l'Espace et filtre global « Toutes mes responsabilités ») sont retirés du shell Flutter.
- L'avatar reste l'entrée pour retrouver l'Espace actif et changer d'acteur via le sélecteur existant.
- Les rôles, Mandates et permissions Space actifs **se cumulent** : attribuer un rôle ne doit pas désactiver une autre attribution active.
- « Maintenant » et « Métier » en contexte Space utilisent désormais la perspective `all`, correspondant aux faits accessibles au Profile dans ce Space, sous les permissions recalculées par leurs propriétaires.
- La profondeur des rôles reste lisible sans transformer une carte Mandate en commutateur de droits global.

## Corrections Flutter

- `mobile/lib/app/app_shell.dart` : retrait du `MakoloSpaceContextBar` au niveau du shell.
- `mobile/lib/features/space/space_shell_routes.dart` : lectures `now/work` toujours sous `ActorPerspective.all()`, suppression du changement global de contexte depuis la profondeur Mandate, libellés d'ajout de rôle et affichage des rôles actifs d'un membre.
- `mobile/lib/app/runtime/actor_context_controller.dart` : normalisation des anciens contextes enregistrés avec un filtre Mandate en contexte Space cumulatif ; sélection d'un Space et appels historiques de sélection de perspective n'enregistrent plus une autorité exclusive.
- `mobile/lib/navigation/actor_selector.dart` : sélectionner un Space ne réactive plus une ancienne sélection de mandat.
- `mobile/test/app_shell_test.dart` et `mobile/test/actor_context_test.dart` : absence de la barre de sélecteurs, avatar conservé, compatibilité des données enregistrées.

## Corrections serveur

- `authorization/services.py` : `grant_standard_space_role` ajoute un Mandate standard de façon idempotente, sans supprimer les autres Mandates. L'ancien nom `replace_standard_space_role` est conservé comme entrée de compatibilité additive.
- `organizations/services.py` : admission d'un membre et synchronisation legacy ajoutent les rôles au lieu de révoquer les autres. La représentation legacy à rôle unique n'est pas une source d'autorité.
- `organizations/team_responsibilities.py` : l'édition d'une responsabilité devient l'ajout d'un mandat ; la cession explicite d'Ownership retire uniquement le Mandate Owner de l'ancien propriétaire après avoir accordé celui du bénéficiaire. Les autres mandats restent actifs.
- `organizations/api/workspace_views.py` : le lecteur d'équipe renvoie la liste `roles` de chaque membre en plus du champ `responsibility` de compatibilité.
- Tests ciblés : coexistence Finance/Marketing, idempotence, révocation explicite d'un seul mandat, transfert de propriété sans perte des mandats non concernés, contrat de réponse équipe.

## Limites de portée

- Les mécanismes de contrôle de permissions existants (`authorization.can`, validation côté owner, révocation explicite, accès aux Activity et aux Groups) ne sont pas élargis.
- Une Assignment opérationnelle ne devient ni un Mandate ni une Permission.
- Le transfert explicite de propriété et le retrait d'un membre conservent leur capacité de révocation, avec la règle du dernier Owner.
- Les sélections ponctuelles de données dans des profondeurs propriétaire ne confèrent pas de permissions supplémentaires ; aucun « rôle actif exclusif » n'est persisté au niveau du shell.
- Tests à faire tourner sur runner configuré : `mobile/test/app_shell_test.dart`, `mobile/test/actor_context_test.dart`, `organizations/test_team_responsibilities.py`, `organizations/test_z15_workspace_api.py`, et contrôles Space Now/Work. Les fichiers préparés ne constituent pas une attestation de tests verts.

## Critère de recette

Sur un émulateur Android :
1. Ouvrir le contexte Space ; seuls les repères normaux du shell et l'avatar en haut sont présents.
2. Ouvrir l'avatar ; le Space actif est reconnaissable et le changement d'acteur reste disponible.
3. Ajouter Marketing à un membre déjà Finance : les deux mandats et leurs permissions sont conservés.
4. Ouvrir Maintenant, Découvrir, Métier, Nous : aucune de ces surfaces ne remplace le contexte par un seul mandat.
5. Révoquer un mandat précis et vérifier que les autres restent actifs ; transférer Owner explicitement et vérifier la conservation des autres rôles.
