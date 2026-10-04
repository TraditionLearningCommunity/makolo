# MPS PR3 — intégration produit

PR3 ferme l'écart entre le noyau MPS restauré et son utilisation réelle dans Makolo.

## Décisions

- aucun nouveau modèle métier et aucune migration ;
- MPS reste propriétaire de la représentation, jamais de l'Activity, de l'Access ou du credential ;
- Studio sélectionne les versions publiées réellement accessibles : Makolo, Profil et Espace ;
- un modèle personnel ou Espace dupliqué peut être rendu utilisable sans devenir public ; la publication Communauté reste distincte et modérée ;
- PUBLIC_PAGE, INVITATION et PROGRAM ont des sorties Activity intentionnelles ;
- ACCESS_PASS, CONFIRMATION et l'INVITATION issue d'un Access sont résolus à partir du contexte canonique de l'Access ;
- le QR reste produit et revalidé par Access / AccessCredential, jamais stocké dans MPS ;
- BADGE reste dans le contrat historique MPS mais n'est pas exposé comme artefact Activity générique tant qu'aucun owner canonique de badge lié à l'Activity n'est démontré ;
- aucun CERTIFICATE n'est ajouté : le runtime courant ne démontre pas encore un owner canonique Activity-certificate suffisamment clair pour justifier un nouveau binding.

## Résolution produit d'un Access

- workflow invitation -> INVITATION ;
- workflow inscription, Service ou Funding à vocabulaire de confirmation -> CONFIRMATION ;
- sinon -> ACCESS_PASS.

Le choix configuré par l'organisateur est donc hérité par les Access réellement émis, sans créer une ligne MPS par bénéficiaire.

## Visibilité des sorties Activity

Invitation et Programme suivent la visibilité de l'Activity :

- Activity publique : artefact partageable ;
- Activity non publique : uniquement un acteur disposant de activity.manage.

Ces sorties utilisent build_activity_context() et n'ajoutent aucune donnée privée de participant.

## Bibliothèques

La duplication conserve sa provenance. L'action « Rendre utilisable » publie uniquement la version au sens de version MPS stable ; elle ne change pas la visibilité du modèle :

- modèle Profil -> reste privé au Profil ;
- modèle Espace -> reste visible dans l'Espace ;
- contribution Communauté -> suit toujours SUBMITTED -> revue -> PUBLISHED par autorité plateforme.

## Critères de sortie PR3

- Studio consomme réellement Makolo / Profil / Espace ;
- Access web et API mobile utilisent le purpose contextuel ;
- Invitation et Programme Activity sont ouvrables comme artefacts réels ;
- Event expose l'entrée Présentation aux gestionnaires ;
- aucun secret AccessCredential ne traverse le contrat MPS ;
- aucune migration.
