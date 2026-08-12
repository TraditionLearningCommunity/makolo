# Groupes Makolo

Le bounded context `groups` implémente la population collective décidée dans le Domain Blueprint.

## Modèle

Un `Group` représente une population : promotion, classe, employés, VIP, presse, speakers, famille ou collectif privé. Il possède exactement un propriétaire logique :

- `space` pour un Groupe appartenant à un Espace ;
- `owner_profile` pour un Groupe personnel.

`created_by` reste un champ d'audit distinct de ce propriétaire logique.

`GroupMembership` enregistre l'appartenance d'un Profil avec un statut (`active`, `suspended`, `left`, `removed`), une source et une `external_reference` contextuelle. Cette appartenance **ne confère aucune Permission**.

`GroupInvitation` conserve une cible éventuelle (Profil, e-mail, téléphone, référence externe) sans créer de Profil fantôme. Le token d'invitation est aléatoire, expirant, à usage unique et stocké uniquement sous forme SHA-256. Une invitation e-mail non encore liée à un Profil exige après inscription un second challenge envoyé à la boîte invitée avant le rattachement. Le code de challenge est lui aussi stocké uniquement sous forme de digest HMAC. Une référence externe seule ne permet jamais le self-claim.

`GroupSnapshot` et `GroupSnapshotMember` forment une photo immuable des membres actifs au moment de la création. Les ajouts/retraits ultérieurs du Groupe courant ne changent pas le snapshot historique.

## Autorité

L'administration est portée par `authorization.Mandate` avec `AuthorityScope.GROUP` et une FK explicite `Mandate.group`.

Rôles système :

- `group-owner` ;
- `group-admin` ;
- `group-moderator`.

Pour un Groupe d'Espace, `groups.services.has_group_permission` applique la règle d'héritage explicite : Permission Groupe directe d'abord, puis `space.groups.manage`/`space.groups.view` sur l'Espace propriétaire. Aucun Mandat Espace n'est copié vers tous ses Groupes.

## Import CSV

`import_group_csv` accepte jusqu'à 1 000 lignes et les colonnes :

```text
email,phone,external_reference,first_name,last_name
```

Le parser utilise la bibliothèque standard `csv`. Avant les écritures, il normalise les identités, rejette les colonnes inconnues, détecte les doublons et les contradictions intra-fichier. Pendant l'import :

- un Profil existant correspondant clairement devient membre ;
- une personne absente devient invitation en attente ;
- une identité ambiguë ou une référence externe déjà attribuée devient conflit ;
- un import répété n'ajoute pas de doublon destructeur ;
- un historique suspendu/retiré n'est pas réactivé silencieusement.

Le résultat détaille membres ajoutés, invitations créées, doublons ignorés, lignes invalides et conflits.

## Frontend

Les routes `/groups/` fournissent aujourd'hui : Mes Groupes, création, détail, administration des membres, invitations, import CSV, snapshots, délégation de Mandats, transfert d'un Groupe personnel et archivage. Les Espaces exposent simplement un lien vers leurs Groupes sans reconstruire la Console Espace.

Les membres ordinaires peuvent consulter leur Groupe mais n'obtiennent pas la vue administrative contenant les coordonnées des autres membres. Les routes de gestion appliquent les Permissions côté serveur et répondent 403 en cas d'accès direct non autorisé.

## Hors scope intentionnel

Cette étape ne crée pas `GroupEligibility`, Activity/Occurrence, Journey/Request/Access, QR Groupe, ticket Groupe, paiement Groupe ni moteur de segmentation CRM. Les futures primitives d'éligibilité pourront référencer Groupes/Snapshots sans détour par `Event`, `Ticket` ou `ContentType`.