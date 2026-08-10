# Données de démonstration Makolo

Makolo fournit un seeder déterministe destiné aux environnements de démonstration, en particulier l'instance web PythonAnywhere.

## Période couverte

La référence par défaut est le **10 août 2026**. Le jeu simule une activité historique à partir de 2024 et contient aussi des événements futurs jusqu'à fin 2027.

Il couvre notamment : comptes et profils, organisations et équipes, followers, événements et lieux, billetterie, commandes, paiements et remboursements, listes d'attente, transferts, contrôle d'accès, notifications, promotions, CRM, automatisations, Growth, partenaires/affiliation, fidélité, dépenses Growth, incidents Operations et modération.

Les identifiants du seed sont déterministes. Relancer le même seed met à jour les mêmes objets au lieu de créer une nouvelle copie de chaque ligne. Les données existantes qui ne font pas partie du seed ne sont pas supprimées.

## Commande Django

```bash
python manage.py seed_makolo_demo --scale large --as-of 2026-08-10 --demo-password 'votre-mot-de-passe-temporaire'
```

Pour éviter d'écrire le mot de passe dans l'historique du shell :

```bash
read -s -p "Mot de passe demo: " MAKOLO_DEMO_PASSWORD; echo
export MAKOLO_DEMO_PASSWORD
python manage.py seed_makolo_demo --scale large --as-of 2026-08-10
unset MAKOLO_DEMO_PASSWORD
```

Échelles disponibles :

- `small` : utilisée par la CI ;
- `medium` : démonstration intermédiaire ;
- `large` : environ 180 utilisateurs, 36 événements et plusieurs centaines de commandes/billets.

Le fichier racine `seed_makolo_demo.py` peut également être appelé directement après initialisation de l'environnement Django.

## Comptes de démonstration

Quelques comptes faciles à retrouver :

- `demo.user001@makolo.test` — superuser/staff Makolo ;
- `demo.user002@makolo.test` — staff/organisateur ;
- `demo.user011@makolo.test` — profil orienté accès/scanner ;
- `demo.user026@makolo.test` — participant.

Tous utilisent le mot de passe fourni au moment du seeding. Aucun mot de passe de démonstration n'est versionné.

## Garde-fous

La commande s'exécute dans une transaction atomique. À la fin, elle inspecte tous les modèles métier Makolo et échoue si un modèle concret n'a reçu aucune donnée. La CI vérifie aussi l'idempotence en exécutant le seed deux fois.

Les fichiers associés aux pièces justificatives de démonstration sont uniquement des chemins factices en base ; aucune vraie pièce d'identité n'est versionnée ou générée.
