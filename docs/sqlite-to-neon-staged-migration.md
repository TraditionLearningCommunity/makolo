# Makolo — migration SQLite PythonAnywhere vers Neon PostgreSQL (PR #522)

Cette procédure est **non destructive pour SQLite**. Ne jamais publier `db.sqlite3`, des dumps, des données privées ni des secrets dans GitHub, Vercel, les logs CI ou les commentaires de PR.

## Situation initiale contrôlée (12 novembre 2026)

- GitHub : `TraditionLearningCommunity/makolo`, PR #522, branche `fix/discover-a-continuation-context-20261014` ; cible `main`. Ne pas merger tant que les checks requis ne sont pas verts.
- Source fournie : `db.sqlite3` (175 214 592 octets), SQLite `integrity_check=ok`, `foreign_key_check=0` ; 362 tables, 174 non vides, 241 830 lignes au total, 264 migrations Django enregistrées.
- Neon : projet `neon-makolo` ; branche de production `main` avec base `neondb`, sans tables utilisateur ; branche de prévisualisation Vercel de la PR #522 également sans tables utilisateur lors du diagnostic.
- Le code de la PR #522 possède déjà le pilote `psycopg[binary]` et la configuration PostgreSQL propriétaire `DJANGO_DATABASE_*`. Ce n'est pas une configuration via `DATABASE_URL` automatique.

Ces chiffres correspondent **au snapshot reçu**, pas à une preuve que PythonAnywhere a cessé d'écrire.

## Procédure sûre, dans cet ordre

1. **Sauvegarder la source.** Sur PythonAnywhere, faire une sauvegarde SQLite cohérente en utilisant l'API `sqlite3.Connection.backup()` ou un arrêt temporaire des écritures. Prendre aussi une copie des fichiers `media/`, des fichiers privés des agents et des stockages d'artefacts pertinents. Ne pas importer les secrets ni les fichiers dans Git.
2. **Figer le SHA** exact de la PR #522 et vérifier ses migrations : `python manage.py check`, `python manage.py showmigrations`, `python manage.py makemigrations --check --dry-run` depuis le code correspondant. Ne pas modifier `main`. Vérifier les vérifications CI en cours et le travail parallèle avant tout nouveau commit.
3. **Préparer une destination isolée** : une nouvelle branche Neon **staging jetable**, ou la branche de preview déjà associée à la PR uniquement si aucune autre application ne l'utilise. Ne pas utiliser Neon `main` pour l'essai. Configurez Django sur cette branche via des secrets d'environnement non enregistrés dans les fichiers. Renseigner les variables `DJANGO_DATABASE_ENGINE=postgresql`, `DJANGO_DATABASE_HOST`, `DJANGO_DATABASE_NAME`, `DJANGO_DATABASE_USER`, `DJANGO_DATABASE_PASSWORD`, `DJANGO_DATABASE_PORT`, `DJANGO_DATABASE_SSLMODE=require` et `DJANGO_DATABASE_CONN_MAX_AGE=0` selon les valeurs réelles Neon. Configurer également le reste des paramètres Django requis, sans publier leur valeur.
4. **Créer le schéma Django** sur la branche staging neuve : `python manage.py migrate --noinput`. Les migrations Django, pas l'introspection brute de SQLite, doivent définir le schéma cible.
5. **Audit source local** : `python scripts/migrate_sqlite_to_postgres.py --source C:\chemin\prive\db.sqlite3 --source-only` ; ne requiert pas de connexion PostgreSQL.
6. **Audit cible en lecture seule** : `python scripts/migrate_sqlite_to_postgres.py --source C:\chemin\prive\db.sqlite3` ; vérifie tables, colonnes, clés étrangères différables, historique des migrations, et refuse toute table déjà remplie hors seeds Django (`auth_permission`, `django_content_type`, `django_migrations`). Tout écart stoppe le transfert : le corriger par une vraie migration ou un chemin de compatibilité revu.
7. **Importer uniquement sur staging validé** : `python scripts/migrate_sqlite_to_postgres.py --source C:\chemin\prive\db.sqlite3 --execute --staging-confirmation I_VERIFIED_THIS_IS_A_DISPOSABLE_STAGING_DATABASE`. La commande refuse `DJANGO_ENV=production`, maintient la source en lecture seule, ne copie pas `django_migrations`, remplace les permissions/types Django générés sur une cible initialement vide, copie les tables et vérifie les comptes dans une transaction, réajuste les séquences et force les contraintes avant commit. Une erreur annule la transaction PostgreSQL.
8. **Vérifier après import** : `python manage.py migrate --noinput` (pour régénérer types/permissions de modèles nouveaux), `python manage.py check`, `python manage.py migrate --check`, tests PostgreSQL ciblés et smoke tests par rôle (auth, Profile/Space, Activity/Occurrence, Journey, Access, Conversations, Payment, Readiness, permissions, synchronisation et outbox). Comparer les comptages métier, PK, FK et échantillons autorisés avec la source. Vérifier les utilisateurs et les secrets/hachages de mot de passe sans les afficher.
9. **Préparer le cutover** : désactiver les écritures et les workers qui pourraient créer des doublons sur PythonAnywhere. Refaire un snapshot SQLite **final** récent, recommencer le transfert sur une destination **propre** (pas sur une cible déjà importée), vérifier, réaliser un backup PostgreSQL durable, configurer l'exécution récurrente Autopilot et les autres workers (ne pas supposer qu'une fonction Vercel les héberge en continu), puis basculer l'application vers PostgreSQL après recette et décision d'exploitation. Maintenir une sauvegarde SQLite et les médias pour rollback.

## Limites et garde-fous

- Le script est strict : il refuse les tables/colonnes source manquantes côté cible, les nouvelles colonnes PostgreSQL obligatoires sans valeur, les migrations source non enregistrées sur la cible, les contraintes FK non différables et les données inattendues déjà présentes. Il ne remplace pas les migrations métier requises pour un ancien snapshot.
- Les tables supplémentaires créées par les nouvelles migrations restent vides jusqu'à ce que les processus métier les alimentent ; les nouvelles autorisations sont régénérées par `migrate` après import. Il faut les vérifier avec les tests.
- Le transfert n'est **pas** exécuté par un simple déploiement Vercel. Les jobs de migration/import doivent s'exécuter explicitement depuis un environnement contrôlé avec connectivité Neon.
- Les données privées et la copie SQLite ne doivent jamais être ajoutées à la PR. Les fichiers media/ ne sont pas contenus dans le dump SQLite.
- Aucun merge, promotion en production ou suppression de la base PythonAnywhere n'est inclus dans cette procédure de staging.