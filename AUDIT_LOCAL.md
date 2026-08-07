# Audit local du projet Makolo

Date : 2026-08-06

## Compréhension du produit

Makolo est conçu comme une plateforme intelligente de gestion événementielle. Le découpage prévu couvre les organisateurs, les événements, la billetterie, le contrôle des billets par scanner, les paiements, les partenaires, les notifications et l'analytique.

L'état actuel est celui d'un socle technique :

- la gestion avancée des comptes et l'API JWT sont réellement implémentées ;
- l'administration Django des comptes est fournie ;
- le tableau de bord est rendu correctement ;
- les modules `events`, `tickets`, `scanner`, `payments`, `partners`, `notifications` et `analytics_app` ne contiennent pas encore de logique métier ;
- les chiffres du tableau de bord sont statiques et les liens de navigation pointent vers `#`.

## Problèmes corrigés

### Critiques

1. Tout utilisateur authentifié pouvait lister les utilisateurs et modifier le profil d'un autre compte. Les listes et suppressions sont maintenant réservées aux administrateurs ; un utilisateur ordinaire ne peut lire ou modifier que son propre compte.
2. Une clé Django de développement était conservée comme valeur de secours en production. La production refuse maintenant de démarrer sans `DJANGO_SECRET_KEY`.
3. Le jeton de déconnexion n'était pas vérifié comme appartenant à l'utilisateur courant. Cette vérification est maintenant appliquée.

### Fiabilité et développement local

4. Aucun manifeste de dépendances n'existait. `requirements.txt` et `requirements-dev.txt` ont été ajoutés.
5. Aucun test n'existait. Cinq tests de permissions et de validation d'inscription ont été ajoutés.
6. Les mots de passe d'inscription ne passaient pas dans les validateurs Django. Ils sont maintenant validés et la création du compte est atomique.
7. `www.makolo.smnasarl.com`, vu dans les journaux de production, a été ajouté aux hôtes autorisés par défaut.
8. Les paramètres HSTS et de redirection HTTPS sont désormais configurables par variables d'environnement.
9. Un script `run_local.ps1` lance les migrations et le serveur local sur `127.0.0.1:8765`.

## Contrôles réussis

- `manage.py check` : aucune anomalie en développement.
- `makemigrations --check --dry-run` : aucune migration manquante.
- Tests Django : 5/5 réussis.
- Compilation Python : réussie.
- Contrôle Ruff ciblé sur les erreurs réelles : réussi.
- `pip check` : dépendances cohérentes.
- `pip-audit` : aucune vulnérabilité connue dans les dépendances installées.
- Bandit : aucune anomalie de sévérité moyenne ou élevée ; uniquement des détections faibles sur des chaînes de test/développement.
- Vérification HTTP : `200 OK` sur `http://127.0.0.1:8765/`.
- Vérification navigateur : tableau de bord rendu correctement, accents compris.

## Risques et travaux restants

### Priorité élevée

1. Les modules métier sont encore vides. Makolo ne gère pas réellement les événements, billets, scans, paiements ou statistiques.
2. L'inscription publique émet immédiatement des jetons JWT même lorsque `is_verified`, `email_verified` et `phone_verified` sont faux. La politique de vérification doit être décidée et appliquée.
3. Aucun mécanisme de limitation de débit n'est configuré pour l'inscription et la connexion. Ajouter le throttling DRF et une protection contre les tentatives répétées.
4. Les téléversements d'avatars et de documents d'identité n'ont pas de validation explicite de taille, extension ou type MIME.

### Priorité moyenne

5. La base `db.sqlite3` téléchargée contient un utilisateur et une session de production. Elle est ignorée par Git, mais une base locale assainie doit la remplacer avant un travail d'équipe.
6. Le tableau de bord est accessible sans authentification et affiche des données fictives.
7. Les bibliothèques d'interface sont chargées depuis des CDN sans SRI et nécessitent Internet.
   Le navigateur signale également que `cdn.tailwindcss.com` est réservé au développement ; les styles Tailwind devront être compilés localement pour la production.
8. Le sérialiseur détaillé utilise une liste d'exclusion. Une liste explicite de champs est préférable pour éviter l'exposition accidentelle de futurs champs sensibles.
9. Les fonctions d'administration volumineuses ne sont couvertes par aucun test.
10. Le contrôle Ruff complet relève de nombreuses dettes mineures : imports inutilisés dans les modules vides, ordre d'imports et annotations de constantes de classe.

## Verdict

Le socle Django fonctionne localement et la partie comptes/API est exploitable après les corrections. L'application métier Makolo reste à construire : le tableau de bord actuel est une maquette connectée à aucune donnée événementielle.
