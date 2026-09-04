# O5 — Offline Action Pack

O5 expose un snapshot opérationnel minimal d’une `Occurrence` pour les clients qui doivent rester utiles lorsque la connectivité devient intermittente. Ce snapshot est une projection de lecture : il ne crée aucun état métier persistant et ne remplace aucune vérité canonique.

## Contrat serveur

Endpoint :

`GET /api/operations/occurrences/<occurrence_id>/offline-action-pack/`

Le pack réutilise la projection viewer-aware `Occurrence Live`, qui compose déjà O1 Placement, O2 Checkpoints/Flow, O3 Live Queue, O4 Operational Readiness, ainsi que les contextes Access, Capacity, Scanner et M6 lorsqu’ils sont applicables.

Le contrat courant utilise `schema = operations.offline_action_pack` et `schema_version = 1`. Il expose `generated_at`, `fresh_until`, `expires_at`, `state`, `stale`, `expired` et `refresh_required`.

La fenêtre actuelle est volontairement courte : une minute de fraîcheur et quinze minutes d’expiration maximale, bornées par la fin de l’Occurrence. Une Occurrence terminée ou annulée produit immédiatement un pack expiré. Ces durées guident l’affichage et la synchronisation du client ; elles n’accordent jamais d’autorité.

## Minimisation des données

Le pack est viewer-aware et conserve uniquement le contexte opérationnel déjà autorisé par `Occurrence Live`. Avant sérialisation offline, il retire les champs de transport ou sensibles qui ne sont pas nécessaires pour agir hors connexion, notamment credentials, QR brut, token, secret, coordonnées de contact, données de paiement, URL d’action/itinéraire et historique de localisation.

La réponse HTTP est marquée `Cache-Control: private, no-store` pour éviter qu’un cache HTTP partagé ou navigateur ne devienne un stockage implicite du pack. Le stockage offline explicite appartient au client mobile A4.

Le pack ne contient aucune capacité de validation Access offline et aucun secret permettant de la simuler.

## Offline data ≠ Authority

Un pack téléchargé précédemment n’accorde aucun droit. Toute mutation reçue par le serveur continue à évaluer l’état serveur courant : permissions, Mandates, Occurrence, Access, Checkpoint, Queue, Placement et Capacity selon l’opération concernée.

Les mutations live Operations refusent désormais une Occurrence `completed`, `cancelled` ou dont `end_at` est dépassé. Les opérations terminales de nettoyage restent possibles : fermeture d’une queue/checkpoint, expiration ou annulation d’une entrée, fin d’une affectation et désaffectation de placement.

## Frontière mobile A4

O5 ne fournit pas de stockage mobile chiffré, SQLite native, background sync OS, scanner réellement offline, validation Access offline, protocole double-use/double-spend, réconciliation multi-device, résolution de conflit, géofencing, GPS de fond, biométrie ou secure enclave/keystore. Ces responsabilités appartiennent au runtime mobile A4.
