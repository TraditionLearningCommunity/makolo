# Accounts & RBAC

## Objectif

Makolo doit utiliser une source d'autorisation cohérente pour les rôles métier, tout en conservant la compatibilité avec le socle actuel.

## Source de vérité

Pour tout nouveau code métier, les rôles dynamiques de `accounts.Role` sont la source privilégiée :

```text
User
  ↓
roles
  ↓
permissions métier
```

Les groupes de permissions (`PermissionGroup`) peuvent regrouper plusieurs rôles et seront utilisés lorsque les besoins d'autorisation deviendront plus fins.

## Compatibilité avec les booléens historiques

Le modèle `User` contient encore :

- `is_organizer` ;
- `is_scanner_agent`.

Ces champs sont conservés temporairement pour ne pas casser les données existantes. Le helper d'autorisation utilisé par l'API consulte d'abord les rôles actifs, puis ces booléens comme fallback de compatibilité.

Aucun nouveau module ne doit ajouter d'autres booléens métier de type `is_*` lorsqu'un rôle peut représenter la même information.

## Codes de rôles réservés

Les codes suivants sont réservés :

- `organizer`
- `scanner-agent`

D'autres rôles système pourront être ajoutés de manière explicite, par exemple `platform-admin`, `participant` ou `partner`, lorsque les modules concernés seront implémentés.

## Plan de migration

Une phase ultérieure devra :

1. créer/garantir les rôles système nécessaires ;
2. migrer les utilisateurs dont les booléens historiques sont actifs vers les rôles correspondants ;
3. supprimer l'utilisation fonctionnelle des booléens ;
4. supprimer les champs historiques dans une migration séparée après validation des données.

## Politique d'inscription et JWT

L'inscription publique crée le compte mais n'émet plus automatiquement de jetons JWT.

Le client doit appeler explicitement l'endpoint de connexion pour obtenir un couple access/refresh. Cela sépare la création de compte de l'authentification et permet d'ajouter ensuite une politique de vérification sans changer le contrat d'inscription.

À ce stade, `is_verified`, `email_verified` et `phone_verified` sont des états métier exposés, mais la connexion n'est pas encore bloquée sur ces états. Les modules sensibles devront appliquer une permission de vérification lorsque leurs règles métier seront définies.

## Limitation de débit

Les endpoints publics d'authentification disposent de limites locales :

- inscription : 5 requêtes/heure par adresse IP anonyme ;
- connexion : 10 requêtes/minute par adresse IP anonyme.

Ces limites constituent une première protection. Une stratégie distribuée (Redis, reverse proxy, WAF ou équivalent) sera nécessaire avant montée en charge.
