# Métier — Space : checkpoint du socle serveur (PR #522)

Date : 31 octobre 2026. Dépôt unique : `TraditionLearningCommunity/makolo`, branche `fix/discover-a-continuation-context-20261014`. Base `main` observée : `d0f0ec421c94c255fa4c0acd3509938a70c6322f`.

## Décision et frontière

Le chantier 0/1 se fait dans la seule PR #522. Les autres PR de travail ont été fermées sans merge ; le checkpoint Nous issu de #528 est déjà sur la branche. Les évolutions concurrentes de Space Maintenant, de Flutter et des domaines partagés doivent être réconciliées au HEAD courant de #522. Pas de modification de `main`.

Métier reste une **projection sur des propriétaires réels**, sans `SpaceWorkItem` persistant, sans endpoint parallèle pour le même objet, sans droits implicites par archétype. Les huit compositions Web/Flutter sont volontairement hors de ce checkpoint.

## Correctifs serveur poussés

1. Les demandes et cas Service autorisés ne disparaissent plus de `requests` quand le Space n'est pas de l'archétype education/service_provider. L'archétype règle la présentation, jamais la Permission.
2. La visibilité Activity sous Mandate Activity est désormais conditionnée par des **permissions de lecture métier**. Un Mandate `activity.access.scan` seul n'expose pas le brouillon, les occurrences ou le portefeuille de travail. La requête est résolue en base via Mandate effectif, RolePermission active et Activity appartenant au Space.
3. Les dossiers Services restent filtrés par `service_journeys_visible_to`. Un lien `services:operator-case` est émis uniquement si `service_case_scope` donne une portée opérateur et si le `ServiceJourneyContext` est présent. Les anciennes démarches sans contexte restent visibles dans leur section autorisée, **sans lien cassé**.
4. Les commandes exposent le véritable détail `organizations_api:workspace-commerce-order-detail`, qui revalide `ORDERS_VIEW`, le Space et les Activity autorisées ; aucune PII acheteur n'est copiée dans le résumé.
5. Les transitions génériques `owner_transition` fabriquées par la projection Journey ont été retirées : aucune prochaine action n'est annoncée sans opération propriétaire concrète.
6. Les routes, véhicules et offres disposent d'un lien `selection` sur l'endpoint Space Work existant ; la requête de sélection est à nouveau filtrée par autorité, source et Space. Aucun faux endpoint transport n'est créé.
7. Les offres `inactive` restent retrouvables en structure `offers` avec leur état propriétaire réel, au lieu d'être silencieusement éliminées.
8. Le lien Jour J des occurrences est dérivé de la phase canonique Operations `arrival/live`, pas seulement du booléen `is_ongoing`. Les arrivées imminentes deviennent accessibles pour les opérateurs autorisés.
9. L'`Operational Footprint` des projections Workspace et Métier est filtré par permissions directes : des droits Activity ne divulguent pas automatiquement la présence de CRM, paiements, partenaires ou fidélité.
10. Le `coverage_state` global est déclaré `partial` pour la vue limitée aux Activity plutôt que de prétendre à une couverture Space-wide.

## Tests ajoutés ou étendus

`organizations.test_zs3_space_work_api` :
- Space multi-vertical générique/communautaire (inscriptions et cas Services avec permission réelle) ;
- Mandate scanner seul : non-divulgation, sélection indirecte refusée, révocation effective ;
- commande : lien de détail owner et refus du lecteur étranger ;
- Services : aucun lien sans contexte ; destination réelle pour opérateur autorisé ;
- offres inactives : structure conservée et sélection sécurisée ;
- transport : route/véhicule sélectionnables avec revalidation, accès étranger refusé ;
- phase Operations arrival : lien Jour J disponible ;
- footprint permissionné : une permission CRM n'expose pas d'autres signaux.

## Contrôles locaux à exécuter

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_zs3_space_work_api organizations.test_z15_workspace_api
```

Puis contrôler au minimum les parcours manuels : propriétaire, membre sans Mandate, Mandate scanner seul, gestionnaire Activity-scoped, responsable Services, lecteur Orders, révocation, changement de Space et sélection directe cross-Space.

**Tests non exécutés depuis cette session distante**, sur instruction de l'utilisateur de valider Django/Flutter localement ; aucun succès de CI ou de tests n'est attesté. Aucun merge effectué. Les composants Web/Flutter et les compositions Métier archétypales restent hors scope à ce stade.

## Contrat de sortie du serveur

L'API existante `GET /api/v1/organizations/workspaces/<slug>/work/` livre des sections fondées sur les owners, des permissions vérifiées, des liens revalidables vers les destinations réelles et des états honnêtes. Les actions d'écriture demeurent chez leurs propriétaires (Services, Commerce, Operations, Transport, etc.) et conservent leur contrôle d'autorité et leur gestion propre d'idempotence/concurrence. Les ressources/médias protégés ne sont ni copiés ni exposés par l'agrégateur.
