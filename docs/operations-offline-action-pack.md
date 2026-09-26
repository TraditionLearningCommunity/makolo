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

La réponse HTTP est marquée `Cache-Control: private, no-store` pour éviter qu’un cache HTTP partagé, navigateur ou intermédiaire ne devienne un stockage implicite du pack. Après A0, un client installé authentifié peut toutefois absorber explicitement les champs autorisés du pack dans sa projection locale protégée. Cette persistance applicative appartient à la fondation local-first A1 ; elle n’est ni un cache HTTP ni une nouvelle vérité métier.

Le pack ne contient aucune capacité de validation Access offline et aucun secret permettant de la simuler.

## Offline data ≠ Authority

Un pack téléchargé précédemment n’accorde aucun droit. Toute mutation reçue par le serveur continue à évaluer l’état serveur courant : permissions, Mandates, Occurrence, Access, Checkpoint, Queue, Placement et Capacity selon l’opération concernée.

Les mutations live Operations refusent désormais une Occurrence `completed`, `cancelled` ou dont `end_at` est dépassé. Les opérations terminales de nettoyage restent possibles : fermeture d’une queue/checkpoint, expiration ou annulation d’une entrée, fin d’une affectation et désaffectation de placement.

## Frontière mobile A1 / A4 / A5

O5 reste une projection serveur et ne fournit aucun runtime mobile.

La fondation **A1 — Installed Makolo Core** possède le stockage privé local, la base SQLite/Drift, les migrations locales, l’outbox durable, la synchronisation owner-scoped, la reprise après crash et la convergence multi-device côté client. Cela rend Makolo local-first sans déplacer l’autorité métier.

**A4 — Native & Ambient Makolo** possède les déclencheurs propres aux OS et aux capacités natives lorsqu’ils deviennent nécessaires : fenêtres de background, push, caméra, localisation, share sheet, widgets et deep links natifs.

**A5 — Field Operations & Delegated Offline Authority** possède le scanner réellement offline, la validation Access hors connexion, le protocole double-use/double-spend, le clock skew, les allocations déléguées, les coordinateurs locaux et la réconciliation terrain.

La biométrie/secure enclave/keystore peut protéger les données ou secrets locaux dès que le client en a besoin ; elle ne crée jamais une Permission, un Mandate, un Access ni une autorité offline.
