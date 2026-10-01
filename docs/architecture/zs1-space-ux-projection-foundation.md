# ZS1 — Space UX Projection Foundation

**Statut :** implémenté sur branche ZS1  
**Base auditée :** `main@565bbc977aad3a45cdf08430b7d015254095f77f`  
**Périmètre :** projection serveur commune permettant aux clients Web/Mobile d'entrer dans un contexte Space sans reconstruire l'autorité.

## Problème UX

Z15 expose déjà un inventaire permissionné de capacités backend owner-backed. ZS1 complète ce contrat pour répondre à une question différente : au nom de quel Space la personne agit-elle, sous quelle portée générale, avec quelles perspectives présentables et dans quel langage métier ?

ZS1 ne construit ni Maintenant, ni Découvrir, ni Métier profond, ni Nous, ni Jour J.

## Owners réutilisés

- `Organization`, `SpaceArchetype` et lifecycle restent propriétaires de l'identité Space.
- `Mandate`, `Role`, `Permission` et le resolver d'autorisation restent propriétaires de l'autorité.
- `Assignment`, TeamMembership et GroupMembership ne deviennent pas autorité.
- `space_product.py` reste propriétaire du vocabulaire de présentation dérivé de l'archétype.
- Z15 reste propriétaire de l'inventaire de modules owner-backed.

Aucun modèle, champ persistant ou migration n'est ajouté.

## Contrat API

Les endpoints existants `/api/v1/organizations/workspaces/` et `/api/v1/organizations/workspaces/<slug>/` restent les points d'entrée.

Le détail conserve le contrat Z15 et ajoute/normalise :

- `space` : identité minimale, archetype, lifecycle ;
- `authority` : `space` ou `activity_limited` ;
- `responsibilities` : perspectives dérivées des Mandates courants dans le Space ;
- `operating_preset.primary_business_label` : langage primaire UX ;
- `links.workspace` : continuation owner-backed ;
- `capabilities` : actions utiles dérivées, jamais autorisation durable ;
- `operational_footprint` uniquement avec autorité Space directe ;
- `modules` : inventaire Z15 inchangé dans son rôle.

Une perspective combinée `Toutes mes responsabilités` compose les perspectives visibles ; elle ne crée aucun rôle, Mandate ou Permission.

Une perspective Activity-scoped conserve explicitement l'identité et le titre de l'Activity. Aucun scope métier plus riche n'est inventé.

## Archetype et langage

Le libellé primaire est centralisé dans `SpaceOperatingPreset` :

| Archetype | Libellé |
| --- | --- |
| generic | Activités |
| creative | Créations |
| media | Productions |
| education | Programmes |
| commerce | Commerce |
| service_provider | Prestations |
| transport_operator | Transport |
| community | Initiatives |

Ce langage n'accorde aucune capacité.

## Sécurité et divulgation minimale

La collection de Spaces reste fondée uniquement sur les Mandates Space/Activity courants. Platform authority, TeamMembership, GroupMembership et Assignment seuls n'ouvrent pas un Space.

Un outsider reçoit 404 sur le détail. Une personne uniquement Activity-scoped ne reçoit ni Operational Footprint, ni résumé Team, ni résumé Ownership. Les Permissions brutes et les Mandates complets ne sont pas sérialisés.

Les capabilities du bootstrap sont indicatives à l'instant de lecture. Toute mutation continue à passer par les services owner-backed et leur revalidation serveur ; une révocation entre lecture et mutation ne peut donc pas être contournée par le payload lu précédemment.

## Known / absent / hidden

Une collection connue vide reste `[]`. L'absence d'un bloc privé signifie qu'il n'est pas divulgué dans ce scope ; elle ne doit pas être interprétée comme inexistence métier. ZS1 n'invente pas de routes futures pour ZS2+.

## Tests ciblés

Les tests Z15/ZS1 couvrent notamment : authentification, Mandate Space, Mandate Activity limité, Membership seul, GroupMembership seul, Assignment seul, Platform authority séparée, outsider, responsabilités bornées au Space courant, absence de dump Permission, huit archetypes et revalidation après révocation.

## Collision audit

À la base auditée, les PR ouvertes #408 (performance read-path) et #410 (Mayele identity resolution) ont été examinées. #410 est indépendante. #408 touche `organizations/console_context.py` mais pas les fichiers ZS1 modifiés ; ZS1 évite volontairement `console_context.py` et les templates.

## Gaps laissés à ZS2+

ZS1 ne compose pas les données de Maintenant/Découvrir/Métier/Nous/Jour J. Il ne fabrique pas une taxonomie professionnelle à partir des rôles. Les futures tâches peuvent enrichir les projections humaines lorsqu'un mapping canonique et démontrable existe.

## Sortie

Un client n'a plus besoin d'inspecter l'ORM, les Memberships, Assignments ou Permissions pour connaître le Space courant, son langage primaire, la portée générale de l'autorité et les perspectives présentables. L'autorité réelle reste exclusivement serveur.
