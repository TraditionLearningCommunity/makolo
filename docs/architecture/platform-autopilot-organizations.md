# Makolo Platform — Organisations, équipes et Autopilot

## Principe

Makolo n'est pas le back-office d'un seul organisateur. C'est une plateforme multi-organisateurs : l'administrateur Makolo administre la plateforme, tandis qu'un utilisateur peut créer ou rejoindre une organisation et gérer uniquement les ressources que son rôle autorise.

## Modèle d'organisation

```text
Makolo platform admin
        │
        ├── modération / sécurité / configuration globale
        │
        └── Organization
              ├── Owner
              ├── Admin
              ├── Event manager
              ├── Finance
              ├── Marketing
              └── Scanner manager
                    │
                    └── Events
```

`Event.organizer` reste le créateur/référent historique pour compatibilité. `Event.organization` devient la frontière métier principale. La migration crée automatiquement une organisation personnelle pour chaque organisateur existant et rattache ses événements.

### Capacités

- Owner/Admin : équipe et organisation ;
- Event manager : création, modification, publication et billetterie de l'événement ;
- Finance : accès aux commandes/paiements et opérations financières ;
- Marketing : communication et futures campagnes/CRM ;
- Scanner manager : contrôle d'accès et affectations scanner ;
- `is_staff` / `is_superuser` restent réservés à la plateforme Makolo.

## Makolo Autopilot

`automation` exécute les opérations temporelles et réactives qui ne doivent pas dépendre d'un développeur ou d'un clic humain.

Un cycle Autopilot :

1. expire les commandes payantes arrivées à échéance et libère le stock ;
2. récupère les livraisons de notification interrompues ;
3. applique les politiques de chaque événement ;
4. crée les rappels 7 j / 24 h / 2 h activés ;
5. surveille le taux de remplissage ;
6. surveille les stocks faibles ;
7. ferme les ventes au démarrage si activé ;
8. termine l'événement après sa fin si activé ;
9. crée le suivi post-événement ;
10. traite la file d'e-mails.

Les actions ponctuelles sont dédupliquées dans `AutomationRun`.

## Configuration par l'organisateur

Chaque responsable d'événement peut ouvrir :

```text
/autopilot/events/<slug>/
```

et activer/désactiver les règles sans accès administrateur Makolo.

## Exécution autonome

En production, **personne ne lance les commandes à la main**. Le déploiement démarre un second processus persistant :

```text
python manage.py autopilot_worker --poll-seconds 30
```

Le gestionnaire de processus (systemd, Supervisor, container orchestrator, PaaS worker) redémarre automatiquement ce worker s'il tombe.

Pour les hébergements ne permettant pas de worker persistant, un cron peut appeler chaque minute :

```text
python manage.py run_autopilot
```

Ces commandes sont des interfaces d'exploitation, pas des actions quotidiennes de développeur.

## Séparation des responsabilités

Les utilisateurs métier configurent leurs règles depuis l'interface. Le moteur décide quand les exécuter. L'administrateur plateforme surveille la santé globale, les abus et les paramètres globaux. Le développeur n'intervient que pour déployer une nouvelle version ou faire évoluer le produit.

## Extensions prévues

Cette architecture prépare : liste d'attente intelligente, transfert sécurisé de billets, CRM événementiel, followers/organisateurs, codes ambassadeurs, alertes de file d'attente, segmentation, recommandations, tarification assistée et analytics prédictifs.
