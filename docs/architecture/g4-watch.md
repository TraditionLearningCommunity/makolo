# G4 — Veille Makolo

Une Veille est une requête Discovery privée et rejouable. `DiscoveryWatch` vit dans `discovery`, possède un utilisateur, un nom, un état actif/en pause, des critères structurés validés, des dates de création/modification et un lien Dossier personnel optionnel.

Les critères persistés sont uniquement ceux que Discovery exécute déjà : texte, lieu, période/date, verticale, prix, proximité, tri et timezone. Aucun filtre Topic explicite n'est persisté tant que `search_occurrences()` ne sait pas l'exécuter. Les combinaisons Service sont refusées lorsque la projection Service ignore aujourd'hui le filtre demandé.

Les résultats ne sont pas copiés : `execute_watch()` rejoue les critères via `search_occurrences()` et `public_service_discovery_items()`. La création depuis Discover reprend les paramètres courants et demande seulement un nom et, facultativement, un Dossier du même propriétaire.

Les Veilles ne sont exposées que derrière authentification et filtrage propriétaire. Elles ne sont pas publiées sur le profil, la recherche de personnes ou le Passeport.

G4 n'ajoute ni scheduler ni notification intelligente. Le point d'extension futur est `execute_watch(watch.criteria, profile=watch.owner)`: Notifications/Automation pourra l'appeler et conserver son propre état de comparaison afin de détecter de nouvelles correspondances sans créer de moteur parallèle dans Discovery.
