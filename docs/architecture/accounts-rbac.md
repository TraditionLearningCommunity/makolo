# Accounts, identité et autorité

## Statut

Ce document remplace l'ancien contrat RBAC global d'Accounts. Depuis le cutover canonique, `accounts` ne possède plus de rôle métier global, de `PermissionGroup`, de flag `is_organizer` / `is_scanner_agent` ni de statut générique `is_verified`.

La source canonique d'autorité est documentée dans [`authorization-boundaries.md`](authorization-boundaries.md) et suit :

```text
Profil + Rôle + Portée = Mandat
```

## Responsabilité d'Accounts

`accounts.User` reste l'identité technique du Profil global et porte :

- authentification et statut technique du compte ;
- coordonnées personnelles nécessaires au compte ;
- vérification de contact `email_verified` / `phone_verified` ;
- sécurité de connexion, appareils et sessions ;
- préférences personnelles.

`accounts.UserProfile` reste une extension 1–1 de ce même Profil. Il ne constitue ni une seconde personne, ni une identité publique autonome, ni une source d'autorité.

## Ce qu'Accounts ne possède plus

Accounts ne décide jamais qu'un Profil est « organisateur », « scanner », « finance », « marketing » ou administrateur d'un Espace. Ces responsabilités sont contextuelles et passent par `authorization.Role`, `Permission` et `Mandate`.

Le staff Django reste une capacité technique d'administration. `is_staff=True` ne remplace pas un Mandat métier.

## Vérification et confiance

`email_verified` et `phone_verified` restent des faits de contact du compte.

Toute vérification métier d'identité ou d'organisation appartient au domaine `trust`, notamment via `VerificationClaim` et `TrustEvidence`. Un écran qui affiche « Profil vérifié » doit dériver ce résultat de Trust et ne doit jamais stocker un booléen concurrent dans Accounts.

## Complétude du Profil

La complétude/activation du Profil est une projection privée dérivée. Aucun `profile_completed` persistant n'est source de vérité. `accounts.profile_activation` calcule la progression depuis les faits réellement présents.

## Inscription et JWT

L'inscription publique crée le compte mais n'émet pas automatiquement de jetons JWT. Le client appelle ensuite explicitement l'endpoint de connexion pour obtenir ses jetons.

## Limitation de débit

Les endpoints publics d'authentification conservent leurs limites applicatives. Ces limites ne remplacent pas les protections d'infrastructure nécessaires avant production.
