# Recette — Changer de contexte Moi / Space sans réseau

**PR #522 — 12 novembre 2026.** Ajustement local-first de sélection d'acteur, sans nouveau propriétaire métier.

## Diagnostic

Le bottom sheet « Agir en tant que » déclenchait une acquisition réseau à l'ouverture, répétait des textes de connectivité, bloquait le choix des Espaces pendant une requête, et exigeait un nouvel inventaire **et** un nouveau Workspace avant chaque basculement. Même un Space déjà acquis devenait impossible à sélectionner lors d'une interruption temporaire de Django. Les messages « Espaces déjà consultés… », « L'accès sera vérifié… », « Les Espaces ne peuvent pas être vérifiés… » contredisaient la règle de ligne réseau unique dans le shell.

## Correction

- Le sélecteur lit `watchInventory()` et n'effectue aucun appel réseau à son ouverture. Les explications réseau, le bouton « Vérifier mes Espaces » et la barre de vérification disparaissent.
- Le repository propriétaire `WorkspaceContextRepository.hasAcquiredSpaceContext` permet de sélectionner un contexte de **lecture** depuis le ProfileStore uniquement si l'inventaire ET le bootstrap Workspace ont déjà été acquis pour **ce Profile**, correspondent à l'identité exacte ID/slug, possèdent une source qui a déjà réussi et ne sont pas invalidés. Les erreurs transport explicitement connues n'effacent pas la lecture. Toute erreur inconnue, permission refusée, tombstone ou absence de source interdit ce chemin.
- En l'absence d'un contexte local sûr, la procédure existante de vérification par le serveur reste disponible, avant de changer l'acteur. Aucun Mandate, Permission, Access, droit de mutation ou confirmation métier n'est dérivé du choix local. Les écrans Space continuent à employer les sources propriétaires et leurs états d'invalidation.
- La sélection d'un Space acquis est immédiate, sans requête HTTP dans le bottom sheet. Le retour à Moi reste local et inchangé.

## Recette

1. En ligne : consulter et acquérir au moins un Espace (inventaire et identité Workspace).
2. Couper temporairement le service Django (sans se déconnecter du compte), ouvrir l'avatar puis « Agir en tant que » : pas de bavardage, la ligne réseau du shell suffit.
3. Choisir l'Espace acquis : l'avatar passe sur l'Espace, les vues locales déjà disponibles restent consultables. Les opérations à autorité serveur demeurent prudentes.
4. Revenir à Moi et répéter ; aucun inventaire HTTP n'est lancé *par le sélecteur*.
5. Vérifier qu'un Space jamais acquis ne devient pas accessible hors réseau, et qu'un `403/404` propriétaire empêche le basculement local.
6. Changer de Profile ; la liste privée et les sources d'autorité du Profile précédent ne sont pas réutilisées.

Tests : `mobile/test/space_repository_test.dart` (offline, révocation, isolation, widget picker). Flutter/Dart indisponibles dans ce contexte, donc tests non exécutés ici. Ne pas faire de merge sans CI obligatoire verte.
