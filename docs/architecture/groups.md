# Groupes Makolo

Le bounded context `groups` porte la **communauté / population** réutilisable de Makolo.

> Groupe = communauté ou population.
>
> Équipe = collaboration opérationnelle.

Un Groupe peut représenter une promotion, une famille, des employés, des VIP, la presse, des conférenciers ou toute autre population. Il ne remplace jamais `Team`, `TeamMembership` ou les `Mandate` utilisés pour travailler ensemble et administrer un Espace ou une Activity.

## Ownership

Un `Group` possède exactement un propriétaire logique :

- `space` pour un Groupe appartenant à un Espace ;
- `owner_profile` pour un Groupe personnel.

`created_by` reste une provenance d'audit distincte.

L'ownership ne signifie pas usage exclusif : un même Groupe peut être référencé par plusieurs Activities et plusieurs opérateurs autorisés. Cette utilisation ne change jamais `Group.space` ou `Group.owner_profile` et ne clone ni le Groupe ni ses Memberships.

## Appartenance et autorité

`GroupMembership` enregistre l'appartenance d'un Profil avec les statuts `active`, `suspended`, `left` et `removed`.

**Un Membership n'accorde aucune Permission.**

L'administration reste portée par `authorization.Mandate` avec `AuthorityScope.GROUP` et une FK explicite `Mandate.group`. Les rôles système restent :

- `group-owner` ;
- `group-admin` ;
- `group-moderator`.

Pour un Groupe d'Espace, `groups.services.has_group_permission` conserve l'héritage explicite `space.groups.manage` / `space.groups.view`. Une simple appartenance à une Team ou au Groupe ne confère aucune autorité.

## Découvrabilité

La découvrabilité est indépendante de la politique d'adhésion :

- `LISTED` : trouvable dans la recherche Groupes Makolo ;
- `UNLISTED` : absent des recherches générales mais accessible avec son lien dans un contexte authentifié ;
- `HIDDEN` : existence révélée uniquement aux membres, gestionnaires et invités autorisés ; un accès direct non autorisé répond 404 ;
- `SPACE_ONLY` : comportement historique limité au périmètre autorisé de l'Espace.

La migration T27 préserve la confidentialité :

- ancien `PRIVATE` → `HIDDEN` ;
- ancien `SPACE` → `SPACE_ONLY`.

Aucun Groupe historique ne devient trouvable globalement par migration.

La recherche dédiée `/groups/explore/` est paginée et DB-first. Elle n'altère pas Discovery T26, qui reste **Activity-first**.

## Politique d'adhésion

La politique d'adhésion est une dimension distincte :

- `OPEN` : un Profile authentifié peut rejoindre directement ;
- `REQUEST` : un `GroupJoinRequest` est créé, sans Membership actif avant approbation ;
- `INVITE_ONLY` : l'adhésion self-service est refusée ; les invitations existantes restent le mécanisme canonique.

Les Groupes historiques sont migrés en `INVITE_ONLY` par défaut afin de ne pas élargir implicitement leur accès.

`GroupJoinRequest` suit : `pending`, `approved`, `rejected`, `cancelled`. Une contrainte DB empêche plusieurs demandes `pending` pour le même couple Groupe/Profile. L'approbation crée ou réactive un Membership avec source `request`.

Réadhésion :

- `LEFT` peut rejoindre à nouveau si le Groupe est `OPEN`, ou refaire une demande si la politique est `REQUEST` ;
- `SUSPENDED` et `REMOVED` ne sont jamais réactivés en libre-service ;
- un Groupe `ARCHIVED` refuse nouveaux Memberships, demandes, invitations et nouvelles utilisations.

## Invitations

`GroupInvitation` conserve une cible éventuelle (Profil, e-mail, téléphone, référence externe) sans créer de Profil fantôme. Les tokens restent aléatoires, expirants, à usage unique et stockés uniquement sous forme SHA-256. Le challenge e-mail conserve son digest HMAC. Une référence externe seule ne permet jamais le self-claim.

T27 ne crée aucune variante `InvitationV2` et ne prétend pas livrer des SMS lorsqu'aucune infrastructure SMS n'existe.

## GroupEligibility Activity-first

T27 introduit `ActivityGroupEligibility`, une relation explicite `Group ↔ Activity` sans `GenericForeignKey`.

Une relation approuvée signifie uniquement :

> le Profile doit être membre `ACTIVE` d'au moins un Groupe autorisé pour initier une nouvelle Démarche sur cette Activity.

Ne comptent pas : invitation pending, join request pending, Membership `left`, `suspended` ou `removed`.

L'éligibilité ne crée jamais automatiquement `Journey`, `Access`, ticket, paiement, commande ou capacité. Les cycles canoniques restent autonomes.

Le contrôle est appliqué à la **création** d'une nouvelle Journey. Une perte ultérieure de Membership n'annule pas une Journey existante et ne révoque jamais automatiquement un Access déjà acquis.

### Usage cross-owner

Un gestionnaire d'Activity ne peut pas cibler un `group_id` arbitraire : il doit posséder l'autorité `activity.manage`.

Si la même personne possède aussi `group.manage`, la relation peut être approuvée immédiatement. Sinon elle passe par :

`requested → approved | rejected → revoked`

La décision appartient au côté Groupe. Les demandes et décisions utilisent le système canonique Notifications avec des deep-links protégés par les mêmes contrôles anti-IDOR.

L'autorité sur l'Activity ne donne aucun droit d'administration du Groupe, et inversement.

## Groupe vivant et Snapshot

`GroupSnapshot` et `GroupSnapshotMember` restent une photo immuable des membres actifs à un instant donné.

- éligibilité dynamique : le Groupe vivant est approprié ;
- population historique pour invitation/audit : utiliser un Snapshot lorsqu'il faut figer les destinataires.

Ajouter ou retirer des membres après création ne modifie jamais un Snapshot existant.

## Confidentialité et CRM

Une Activity autorisée à utiliser un Groupe reçoit une **référence d'éligibilité**, pas la base membres.

> Group ≠ Audience.

Aucune relation `ActivityGroupEligibility` ne crée automatiquement de `CRM Contact`, `Audience` ou `AudienceMember`, et aucun export cross-owner de coordonnées n'est implicite.

La liste administrative des membres conserve ses Permissions serveur et n'est pas exposée aux membres ordinaires. Un Groupe trouvable peut afficher un compteur agrégé sans exposer les identités ni les coordonnées.

Pour un propriétaire personnel, les surfaces publiques Makolo respectent `UserProfile.public_profile` et `UserProfile.searchable` avant d'afficher son identité ; sinon elles utilisent un libellé neutre.

## Frontend

Les routes `/groups/` fournissent :

- Mes Groupes ;
- invitations et demandes en attente ;
- création personnelle ou pour un Espace autorisé ;
- découverte des Groupes `LISTED` ;
- détail avec état de relation ;
- CTA rejoindre / demander à rejoindre / invitation ;
- administration des membres et demandes ;
- invitations, CSV, snapshots, Mandats, transfert et archivage existants ;
- demandes d'utilisation d'un Groupe par une Activity ;
- Activities publiées pertinentes pour les membres du Groupe.

Cette surface reste orientée action. T27 n'ajoute ni posts, commentaires, réactions, likes, followers, stories, chat de Groupe ni feed social généraliste.

## Hors scope T27

T27 ne refond pas :

- Teams / Console Espace / opérations mobiles (T28) ;
- Commerce, Promotions ou Scanner ;
- Offer-level ou Occurrence-level GroupEligibility tant qu'un workflow concret ne le justifie pas ;
- envoi massif qui matérialiserait automatiquement des milliers de Journeys ;
- export CRM cross-owner.
