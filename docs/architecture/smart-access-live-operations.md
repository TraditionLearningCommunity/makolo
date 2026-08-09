# Smart Access & Live Operations — Lot 4

## Objectif

Le Lot 4 transforme le scanner Makolo en système d’exploitation des entrées. Le scanner reste la source transactionnelle qui consomme un billet exactement une fois, tandis que Smart Access ajoute des portes configurées, du débit live, des seuils et des anomalies explicables.

Aucune donnée participant n’est nécessaire dans le tableau de pilotage live : les métriques sont agrégées à partir de `ScanLog`, `Ticket`, `ScannerAssignment` et `EventAccessGate`.

## Modèle de porte

`EventAccessGate` appartient à un événement et contient :

- nom et slug stables dans l’événement ;
- état actif / pause ;
- débit cible accepté par minute ;
- seuil de taux de refus ;
- priorité d’affichage ;
- notes opérationnelles et auteur de création.

`ScannerAssignment.access_gate` permet d’affecter un agent/terminal à une porte précise. `ScanLog.access_gate` référence la porte utilisée et `ScanLog.gate` reste un snapshot texte pour préserver l’historique et la compatibilité avec les anciens clients.

Une porte liée à des journaux ou affectations n’est pas détruite silencieusement par l’API : elle est désactivée.

## Sécurité du scan

Le chemin critique ne change pas :

1. l’événement est verrouillé ;
2. l’autorisation scanner est vérifiée côté serveur ;
3. l’affectation active est résolue ;
4. la porte demandée doit appartenir au même événement et, pour un agent affecté à une porte, ne peut pas être remplacée par une autre ;
5. une porte en pause produit `gate_unavailable` sans consommer le billet ;
6. le QR signé est validé ;
7. le billet est verrouillé et consommé exactement une fois ;
8. le journal conserve le fingerprint SHA-256, jamais le QR brut.

Les garanties anti-double-scan existantes restent la source de vérité : verrou transactionnel + contrainte conditionnelle d’un seul `ScanLog.ACCEPTED` par billet.

## Intelligence live

`scanner.intelligence.event_access_snapshot()` calcule une vue read-only :

- billets valides/utilisés, check-in et reste à entrer ;
- fenêtres 5, 15 et 60 minutes ;
- débit accepté par minute ;
- taux de refus, doubles scans, QR invalides/inconnus, mauvais événement ;
- débit et charge par porte ;
- série de vélocité par tranches de 5 minutes sur une heure ;
- incidents déterministes et recommandations opérationnelles.

Les incidents sont des signaux explicables, pas des prédictions IA :

- taux de refus élevé ;
- pic de doubles scans ;
- pic de QR invalides ;
- billets d’un autre événement ;
- congestion probable lorsqu’une porte atteint ou dépasse son débit cible ;
- refus élevés au-dessus du seuil propre à la porte.

Les anciennes tentatives sans `access_gate` sont conservées et regroupées sous « Non attribué / terminaux hérités ».

## Permissions

- staff : global ;
- Owner/Admin/Event Manager/Scanner Manager : périmètre organisation via les capacités d’accès existantes ;
- scanner-agent : uniquement les événements avec affectation active ;
- participant : aucun accès aux consoles ou métriques scanner.

Le tableau live peut être consulté par un agent autorisé car il n’expose aucune PII. La création/modification des portes reste réservée aux rôles qui gèrent l’accès de l’événement.

## Web

- `/scanner/` — événements scannables + accès Live ;
- `/scanner/gates/` — portes ;
- `/scanner/gates/new/` ;
- `/scanner/gates/<uuid>/edit/` ;
- `/scanner/event/<slug>/` — scanner avec porte assignée/sélectionnée ;
- `/scanner/event/<slug>/live/` — Smart Access Live ;
- `/scanner/event/<slug>/live.json` — snapshot JSON pour rafraîchissement/intégrations internes ;
- `/scanner/logs/` — historique.

## API

- `GET/POST /api/v1/scanner/gates/` ;
- `GET/PATCH/DELETE /api/v1/scanner/gates/<uuid>/` ;
- `GET /api/v1/scanner/events/<slug>/live/` ;
- `POST /api/v1/scanner/scan/` accepte `access_gate_id` en option ;
- affectations et journaux exposent leur porte structurée.

## Concurrence et production

Le Lot 4 ne remplace pas le besoin PostgreSQL en production. Le contrôle exact-once dépend des transactions/verrous côté base ; SQLite reste adapté au développement local mais ne simule pas la concurrence réelle d’un événement à plusieurs portes.

Smart Access ne nécessite aucun daemon supplémentaire : le snapshot est calculé à la lecture à partir des sources métier. Un futur flux WebSocket/SSE pourra remplacer le rafraîchissement périodique sans modifier le modèle de vérité.
