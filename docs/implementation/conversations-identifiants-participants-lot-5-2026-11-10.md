# Conversations — Lot 5 : Identifiants Makolo, participations et invitations

Date : 10 novembre 2026  
Dépôt : `TraditionLearningCommunity/makolo`  
Branche : `fix/discover-a-continuation-context-20261014`, PR #522

## Décision produit

L'accès à une Conversation n'est **pas** conditionné par un « contact »
préalable. Le sélecteur à la WhatsApp est une expérience de recherche, non
un carnet d'adresses Makolo et non une relation à créer.

La valeur décisionnelle est toujours l'**identifiant canonique exact** :

- Profil : `accounts.User.username` (présenté avec `@`).
- Espace : `organizations.Organization.slug`.
- Groupe : `groups.Group.slug`.

Les noms/prénoms, noms d'Espace et noms de Groupe servent uniquement de
**libellés d'aide à la reconnaissance**. Deux « Jean » ou deux espaces de nom
semblable ne sont jamais fusionnés ni utilisés comme identifiants de
destination. Recherche des suggestions par identifiant ou libellé autorisé ;
l'invitation ne résout jamais un libellé.

## Recherche et confidentialité

`search_invitation_candidates` exige l'autorité de gestion de la
Conversation, un minimum de 2 caractères et une liste bornée. Les Profils
sont suggérés seulement si leur découvrabilité et leur présentation le
permettent : `UserProfile.searchable`, Profil public ou signal « Ouvert à »
explicitement recherché, puis politique de visibilité de `name`.
Les Profils fermés et les relations bloquées sont exclus.

Un `username` exact peut néanmoins être saisi pour une invitation privée
si la politique du destinataire l'autorise : la recherche publique n'est
pas la condition de l'invitation, et **le consentement reste requis**.
Les politiques `ProfileContactPolicy` et les blocages canoniques
`ActionNetworkBlock` restent des gardes-fous ; aucun Contact n'est créé.

Espaces : `slug` exact, état actif, visibilité publique ou droit de vue
du demandeur. Groupes : `slug` exact, état actif, découvrabilité
`listed`/`unlisted`, propriétaire ou droits de groupe, avec l'héritage
d'un Groupe `space_only` pour les membres actifs de l'Espace.
Une relation de blocage Profile↔Espace empêche également l'invitation.

Une Conversation directe conserve ses deux parties et ne devient pas une
Conversation de Groupe. Les invitations collectives sont refusées pour
les contextes personnels sensibles (Direct, Journey, ActionProposal, Dossier).

## Participation individuelle

Réutilisation exclusive des modèles canoniques existants :

- `ConversationInvitation` (`pending` → `accepted/declined/expired/cancelled`) ;
- `ConversationParticipation` (`active/left/removed`) ;
- `ConversationJoinRequest` (`pending/approved/rejected`) ;
- `ConversationEntryMode` (derived, join, request, invite_only, direct_consent).

Envoyer une invitation **n'ajoute pas encore un participant**.
Seule l'acceptation active la `ConversationParticipation`.
La clôture ou sortie d'une participation n'efface pas des droits dérivés
qui seraient toujours valides par le contexte.

Les opérations de modération sont réservées aux responsables de la
Conversation. Les refus d'invitation et états fermés empêchent les
réinvitations silencieuses. L'adhésion et la demande d'entrée restent
soumises à l'éligibilité contextuelle canonique.

Une participation ou invitation acceptée donne le droit de publier
**dans cette Conversation uniquement**, lorsqu'elle est visible ;
elle n'accorde aucun Mandate, rôle d'Espace/Groupe ni pouvoir de gestion
d'Activity, Journey, Commerce ou Payment.

## Consentement collectif

Nouvelle *relation de composition*, et non nouvelle copie métier :
`ConversationCollectiveAccess` → `Group` **ou** `Organization`,
exactement un propriétaire canonique par lien.

- Invitation `pending`, sans accès collectif.
- Un responsable du Groupe ou Espace ayant une autorité canonique
  `GROUP_CONVERSATIONS_MANAGE`/`SPACE_CONVERSATIONS_MANAGE` accepte ou refuse.
  Le propriétaire d'un Groupe personnel peut accepter directement.
- Une acceptation établit `active`, sans créer une seule copie de
  `GroupMembership` ni de `TeamMembership`.
- Les membres visibles sont recalculés à partir des adhésions actives
  *et* du statut actuel du collectif, sur chaque nouvelle acquisition.
- La révocation `revoked` retire ce droit sans supprimer la relation
  de Groupe/Espace ni leurs permissions canoniques.
- Une demande répétée ne ressuscite pas un accès révoqué.
- Un responsable qui accepte pour un collectif ne gagne pas automatiquement
  une participation personnelle hors de son appartenance réelle.

Migration **additive** :
`conversations/migrations/0008_collective_access.py`.
L'historique des autres modèles n'est pas migré ou détruit.

## Historique « Depuis l'entrée »

`conversation_viewer_ids` résout les collectifs acceptés à partir des
membres vivants, sans extension de permission de contexte.
`profile_conversation_since` réconcilie deux sources d'admission :
participation individuelle active et collectif accepté. Le début de
l'historique `FROM_JOIN` est le plus ancien accès **actuellement valide**,
jamais antérieur à l'acceptation ni à l'arrivée réelle dans le Groupe/Espace.

Cette borne est appliquée dans `point_visible_to` **et** dans la pagination
signée `page_points_for_profile`. La révocation fait disparaître les
lecteurs et les anciens Points de la projection lors de la prochaine
acquisition serveur. Un HTTP 403/404 purge le cache de détail mobile.

## API privée

Tous les endpoints requièrent authentification et validation côté serveur.

- `GET  /api/v1/conversations/<id>/candidates/?q=...` : suggestions
  découvrables filtrées, comprenant `kind`, `identifier`, `label`.
- `GET  /api/v1/conversations/<id>/participants/` : explicit/invited/collective
  distincts, filtrés selon la capacité du viewer.
- `POST /api/v1/conversations/<id>/invite/` : `kind` et `identifier` exacts.
- `POST /api/v1/conversations/<id>/participants/<id>/remove/` :
  retrait d'une participation explicite.
- `POST /api/v1/conversations/<id>/invitations/<id>/cancel/` :
  annulation d'une invitation en attente.
- `POST /api/v1/conversations/<id>/collectives/<id>/revoke/` :
  retrait d'un collectif.
- `GET /api/v1/conversations/collective-invitations/` et
  `POST /collective-invitations/<id>/respond/` : décision du
  représentant autorisé.
- `POST /api/v1/conversations/<id>/entry/` : rejoindre,
  demander l'entrée ou quitter sa participation explicite.
- `GET /api/v1/conversations/<id>/join-requests/` et
  `POST /api/v1/conversations/<id>/join-requests/<id>/decide/` :
  traitement réservé aux gestionnaires.
- `GET /api/v1/conversations/invitations/` : conserve l'ancien
  contrat `results/count` et ajoute `collective_results`.

## Web et Flutter

Web : page `/conversations/<uuid>/participants/` avec suggestions,
saisie manuelle, état des invitations et collectifs, gestion de l'accès,
demandes d'entrée et sortie explicite. Les invitations collectives destinées
aux responsables apparaissent dans la liste des Conversations.

Flutter : l'onglet Participants permet la même recherche par identifiant,
sans relation préalable de contact. Les suggestions affichent les noms
autorisé(e)s avec l'identifiant canonique. Les opérations sensibles
requièrent un clic explicite et sont confirmées par le serveur.
Les invitations collectives apparaissent dans l'inbox mobile ; une
acceptation collective n'est pas confondue avec un accès personnel.

## Limites et vérification

La liste des membres dérivés n'est **pas** une liste de participants
explicites. La visualisation des autres utilisateurs est limitée aux
responsables, et l'énumération d'un Groupe exige en plus sa permission
canonique de voir les membres.

Aucune CI, suite de tests, exécution Django/Flutter ni déploiement n'a été
réalisé dans cette intervention, conformément à la consigne du chantier.
L'état est **code poussé, validation d'exécution restante**. La migration
doit être planifiée et appliquée avant tout essai des liens collectifs.
Ne pas merger avant la consolidation et la validation prévue au Lot 7.
