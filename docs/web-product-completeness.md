# Web Product Completeness & Role UX

Cette passe complète l'expérience web de Makolo sans ajouter de nouveau grand domaine métier.

## Entrée publique

- `/` est l'accueil produit public de Makolo pour les visiteurs anonymes.
- Un utilisateur déjà connecté qui ouvre `/` est redirigé vers `/dashboard/`.
- La découverte publique reste disponible sous `/discover/`.
- Les organisateurs ayant un profil public sont accessibles via l'annuaire `/o/` et leur page publique existante.

## Parcours compte web

Sous `/account/`, le web couvre désormais :

- création de compte ;
- demande de réinitialisation du mot de passe ;
- choix d'un nouveau mot de passe avec token Django et délai d'expiration existant ;
- changement du mot de passe d'un utilisateur connecté ;
- suppression sécurisée du compte.

L'inscription web réutilise `RegisterSerializer` afin de conserver les mêmes validations et la même initialisation `UserProfile` / `NotificationPreference` que l'API. La réinitialisation et la suppression réutilisent les services de compte partagés.

La suppression de compte reste une désactivation/anonymisation afin de conserver les références nécessaires à la billetterie, aux paiements, à la sécurité et à l'audit. Elle est bloquée si l'utilisateur est le dernier propriétaire actif d'une organisation ; la propriété doit d'abord être transférée.

Aucun champ du centre de profil introduit par la PR #29 n'a été retiré. Les préférences SMS et Push restent visibles et inchangées fonctionnellement.

## Navigation et dashboards par capacités

`core.capabilities.get_web_capabilities()` sert uniquement de read-model de présentation. Il reflète les ensembles de rôles déjà définis par les domaines (`organizations`, `crm`, `growth`, `promotions`, `loyalty`, `partners`, `analytics`) ; il ne remplace aucun contrôle d'autorisation serveur.

La navigation distingue :

- l'espace personnel pour tous les utilisateurs connectés ;
- les outils d'organisation uniquement lorsqu'un rôle actif donne accès au domaine ;
- Operations Center uniquement pour le staff Makolo.

Le dashboard est choisi de façon déterministe : `staff`, sinon `organizer` lorsqu'au moins une capacité d'organisation existe, sinon `participant`. Un utilisateur multi-rôle garde son espace personnel dans la navigation et reçoit le dashboard organisation lorsqu'il possède des responsabilités d'équipe.

Un véritable switcher d'état « Personnel / Organisation » n'est pas introduit dans cette PR : les groupes de navigation rendent déjà les deux contextes lisibles sans ajouter d'abstraction de session. Un switcher persistant peut être étudié séparément si plusieurs organisations exigent plus tard un contexte actif global.

## Operations et données de démonstration

Les seeds Makolo utilisent déjà `metadata.seed = "makolo-demo"` sur les incidents, workers, événements, paiements, scans, notifications et autres objets concernés. Le dashboard Operations exploite désormais ce marqueur pour exclure les données seedées de ses métriques de santé et de ses signaux actifs, tout en conservant les scénarios de démonstration dans la base.

Le dashboard affiche un bandeau explicite lorsqu'il détecte des données de démonstration. Le seed Operations crée également davantage d'incidents historiques résolus et seulement quelques cas encore sous surveillance.

Les données réelles ne sont jamais remplacées : un incident réel critique reste critique même si des données de démonstration sont présentes à côté.

## Pages d'erreur

Des handlers produit 403, 404 et 500 utilisent l'identité visuelle Makolo. Le handler 500 génère un identifiant de corrélation léger sous la forme `MKL-XXXXXX`, l'écrit dans les logs et l'affiche à l'utilisateur sans exposer de stack trace.

## Déploiement PythonAnywhere

Aucune migration de modèle n'est introduite par cette passe. Après le merge :

1. mettre à jour le checkout de production sur `main` ;
2. activer l'environnement virtuel habituel ;
3. exécuter `python manage.py check` ;
4. exécuter `python manage.py migrate` par sécurité (aucune nouvelle migration attendue) ;
5. recharger l'application PythonAnywhere.

Aucun service worker, manifest PWA ou chantier offline n'est ajouté. Aucun asset Tailwind/HTMX/Alpine/Lucide/QR Scanner n'est vendorisé dans cette PR ; ce chantier reste volontairement séparé.
