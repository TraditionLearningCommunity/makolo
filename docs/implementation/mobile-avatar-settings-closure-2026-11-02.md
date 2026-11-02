# Avatar / Paramètres Flutter — fermeture ciblée dans #522

Date : 2026-11-02  
Portée : client Flutter personnel, navigation secondaire, projection locale existante.

## Intention

L'Avatar répond à « qui est connecté et au nom de qui agir ? » ; **Moi** garde l'identité, le Passeport et les ressources personnelles. L'Avatar ne recrée pas Moi ni une page Compte parallèle. Les vérités métier et l'autorité restent propriétaires du serveur.

## Parcours reliés

- L'Avatar lit la progression `identity.activation` déjà calculée par `personal.me`. Il montre une progression incomplète et ne montre jamais `100 %` une fois le Profil complet.
- `Agir comme` compose Moi + l'inventaire autorisé `GET /api/v1/organizations/workspaces/`. Un inventaire absent / non vérifié n'est pas présenté comme « aucun Espace ». Les lignes connues hors connexion n'accordent aucune autorité ; leur sélection exige une revalidation de l'inventaire et du workspace.
- Le retour à Moi ne nécessite pas d'autorité Space. Une révocation côté serveur peut restaurer le contexte personnel, sans suggérer qu'une autorité a été conservée.
- `Créer un Espace` consomme le `POST /api/v1/organizations/workspaces/` existant, avec `public_profile=false` par défaut. La réponse du POST ne donne pas automatiquement le droit d'agir : l'inventaire puis le workspace sont vérifiés avant le switch.
- Une création confirmée avec vérification interrompue peut reprendre la **vérification seule**. Après réponse POST incertaine (transport, 408/409, 5xx), le formulaire n'envoie pas un deuxième POST : il renvoie vers la consultation des Espaces. Les rejets explicites permettent de corriger les saisies.
- `Paramètres` regroupe l'apparence/accessibilité locales, Notifications, sécurité, confidentialité et disponibilité des copies locales. Les liens globaux demeurent accessibles même si le stockage des préférences d'apparence est absent.
- `Confidentialité du Profil` ouvre la profondeur `/me/profile?visibility=1` et ses champs `public_profile` / `searchable` existants. Aucune deuxième vérité de visibilité n'est créée.
- `Données hors ligne` présente uniquement la présence et l'horodatage des copies locales par Profil : Moi, Maintenant, En cours et inventaire d'Espaces. La présence d'une copie n'est pas une preuve de droits courants.
- Les préférences Notifications restent gérées par Accounts / Notifications ; Abonnement par Subscriptions. L'entrée Compte redondante est retirée de l'Avatar ; les contrôles uniques d'accès sont conservés dans Sécurité et appareils.

## Frontières préservées

Aucun nouveau modèle, endpoint, provider ou migration. Pas de capacité Space déduite d'un Membership ou d'une simple copie locale. Aucune action sensible lancée hors validation serveur. Aucun affichage de données privées supplémentaires dans l'état hors ligne.

## Vérification ciblée du code

Les tests Flutter couvrent notamment :
- pourcentage incomplet / Profil complet ;
- inventaire d'acteur non vérifié, absence de bascule offline et révocation ;
- échec de création POST sans deuxième envoi ;
- navigation Paramètres / confidentialité / sécurité ;
- lecture locale des seules métadonnées et absence de fuite de nom privé ;
- lectures Notifications et Subscription par leurs propriétaires.

## Vérification restant nécessaire sur appareil

Tester en Android réel le démarrage à froid, la fermeture des modales, le retour natif, le changement de compte, la création d'Espace avec réseau interrompu et rétabli, les révocations, le grand texte et les états locaux vides. Les modifications poussées ne prouvent pas à elles seules que ces scénarios ont été exécutés. La PR #522 reste non fusionnée jusqu'à validation indépendante des gates d'intégration.
