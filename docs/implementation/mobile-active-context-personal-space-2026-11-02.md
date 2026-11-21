# Mobile — contexte actif Personnel / Espace, sans duplication de vérités

Date : 2026-11-02  
Branche de travail : PR #522.  
Statut : implémenté dans le client Flutter sur la branche ; exécution Android et gates non déclarées validées.

## Contrat produit

Makolo est utilisé normalement dans **deux contextes de premier rang**, Personnel et Espace. Platform reste un environnement distinct pour les agents habilités. Un Profil global authentifie toujours la personne, mais ne détermine pas nécessairement le contexte de travail qu'elle choisit.

Le contexte actif détermine :
- l'identité visuelle de l'Avatar du Header et du menu ;
- les portes primaires pertinentes (Maintenant, Découvrir, En cours/Métier, Moi/Nous) ;
- le titulaire des Connexions et de l'Abonnement affichés ;
- les sources, ressources et opérations pertinentes, sous contrôle du serveur.

Un Profil personnel, un Espace E et un Espace R ne partagent jamais automatiquement Permissions, Mandates, Access, Payment, abonnement, connexions, opération ou donnée privée. Le contexte ne crée pas une deuxième personne ni une deuxième vérité métier.

## Décisions d'implémentation

### Persistance de contexte sans duplication

`ActorContextCodec` et `FileLaunchPreferencesStore` enregistrent **un seul acteur actif par Profil et par appareil**. `shell_locations` conserve la dernière porte pertinente. Au démarrage, `runtime_builder` restaure d'abord cet acteur, puis `restoredShellPath` compose la dernière porte dans ce contexte. Un utilisateur qui a fermé Makolo dans son Espace revient directement dans l'interface de cet Espace, y compris lorsque le premier affichage utilise une projection locale admissible.

Ce ne sont que des préférences de présentation locale, **jamais une restauration d'autorité**. `SyncLifecycle` revalide inventaire et workspace quand le serveur est joignable. Un refus confirmé peut ramener l'acteur à Personnel ; hors ligne, on conserve seulement les observations locales admissibles et les actions sensibles restent soumises aux contrôles propriétaires.

Aucune nouvelle table, migration, duplication de données ou création de `Profile A in Space E` : `ProfileStore` conserve la partition par Profil ; les sources Space possèdent déjà une `SyncActorScope.space`, des clés stables composées avec l'ID Space et, lorsque pertinent, une perspective. Les vérités communes au Profil ne sont pas copiées dans chaque Espace. Les brouillons Mark existants ont une identité d'acteur explicite. Les entitlements et connexions sont toujours demandés à leurs propriétaires serveur.

### Avatar

L'Avatar du Header représente le **contexte actif** :
- Personnel : portrait existant de la personne via `ProfileAvatarImage` ;
- Espace : monogramme calculé à partir du nom d'Espace de l'inventaire local, ou du slug comme repli hors ligne. Le modèle Organization/workspace actuel ne possède pas de logo d'Espace exploitable ; aucun champ ou média n'est inventé. Le portrait privé de la personne n'est jamais utilisé comme logo d'Espace.

Le menu Avatar place **Espace actif** en premier si l'acteur est un Espace, puis indique séparément **Compte connecté : [Profil]**. En contexte Personnel, le portrait, le nom, le @username et la progression incomplète du Profil continuent d'apparaître selon leur contrat initial.

### Navigation et ressources

`connectionsRouteForActor` et `subscriptionRouteForActor` dirigent les actions globales vers :
- Personnel : `/connections`, `/billing` ;
- Espace : `/space/:slug/connections`, `/space/:slug/subscription`.

Les anciennes ouvertures de routes personnelles sont adaptées au contexte Espace courant. Les vues Space existantes restent validées par le serveur et **ne sont pas lues dans les projections personnelles**. Le forfait et les connexions de l'Université U ne deviennent jamais ceux de l'entreprise E ou de Personnel A du seul fait que A agit pour plusieurs titulaires.

## Invariants explicitement préservés

- Profil = personne globale ; Espace = contexte d'action, pas deuxième compte personnel.
- Assignment = responsabilité ; Mandate/Permission = autorité ; aucune autorité dérivée de la sélection UX.
- Aucun `actor` libre fourni par le client ne remplace une vérification serveur.
- Pas de migration Drift, pas de duplication de Profile/Organization, pas de backfill artificiel.
- Les contenus et ressources restent dans leurs domaines propriétaires ; les copies locales ne prouvent pas la fraîcheur ou un droit actuel.
- Le changement de compte continue à changer de personne, distinct du changement d'Espace.

## Régression ciblée ajoutée

`mobile/test/active_context_identity_test.dart` : route abonnements/connexions par acteur, restauration sémantique à froid, monogramme Space distinct du portrait Profil, fallback local.  
`mobile/test/avatar_actor_context_test.dart` : le menu Avatar distingue Espace actif et compte personnel, n'affiche ni portrait ni progression personnels comme identité d'Espace.  
Tests antérieurs conservés : persistance du `ActorContext`, isolation par Profil/Space, revalidation et révocation, navigation shell.

## Validation non revendiquée

La compilation Flutter, le formatage automatique, les tests sur le SDK ciblé et les parcours Android après ces changements ne sont pas exécutés depuis cette intervention. La PR #522 reste ouverte et non fusionnée. Aucun état CI n'est utilisé comme motif de refonte métier.
