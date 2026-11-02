# Subscription — Validation des parcours réels Web/mobile (2 novembre 2026)

Périmètre volontaire : **parcours utilisateur**, sans modification de workflow CI, sans fusion et sans prétention de validation sur appareil.

## Parcours vérifiés et renforcés dans le code

| Départ | Action serveur | Refus attendu | Continuité |
| --- | --- | --- | --- |
| Moi → Créer Activity | `create_activity(owner_profile=actor)` | `ValidationError(subscription)` si `activities.create` indisponible | Subscription personnelle → retour au formulaire → nouvelle tentative |
| Space A → Créer Activity | `create_activity(space=A)` sous `SPACE_ACTIVITIES_MANAGE` | Entitlement de A, jamais du Profil opérateur | Subscription A (si visible au Mandate) → `/activities/create/?space=A` |
| Profil/Space → Event | `create_event` puis Activity owner | Même gate que l'Activity propriétaire | Subscription du sujet → formulaire Event pré-sélectionnant le Space autorisé |
| Space A → Nous → Équipe → Ajouter | `add_or_update_member` | `team.members` sur profils actifs distincts ; permission équipe séparée | Subscription A (si visible) → retour équipe, sans mutation automatique |
| Space B et Profil | Services propriétaires distincts | Blocage A sans contagion vers B | Pas de fuite inter-sujet |
| Acteur sans droit Subscription | Refus uniquement de capacité | Ne pas afficher des données de gestion ou billing | Indication de contacter la personne autorisée, aucun lien de lecture privé |

## Corrections du passage final

- `mobile/lib/features/space/space_shell_routes.dart` : les réponses d'erreur d'une mutation équipe arrivant après un changement d'acteur ne produisent plus de Snackbar périmée. Les réponses 401/403/404 et les refus Subscription restent distincts ; seul un handoff effectivement exposé par Nous autorise « Comprendre ».
- `subscriptions/test_lot4_continuation.py` : scénarios de reprise **réelle** : refus de capacité, consultation de Subscription, ajout d'une capacité réelle par le service de grants, retour à l'équipe, admission d'un nouveau Profil, répétition idempotente du Profil déjà compté ; blocage d'A sans empêcher l'ajout dans B.
- Les tests précédents couvrent URL externes, slug inconnu, retour Event lié au propriétaire, acteur équipe sans Mandate Subscription et validation du POST après changement d'acteur Flutter.

## Exclusions et état de preuve

Ce chantier ne change pas de modèles, migrations, plan, prix, workflow CI, secrets, ni permissions. Il ne fusionne pas #522. Les changements sont poussés sur sa branche.

Le code a été inspecté à partir du HEAD réel de la branche et des tests ciblés ont été ajoutés. **Un passage réel navigateur et Android, et l'exécution locale des tests Django/Flutter, ne sont pas attestés** dans cette session faute de checkout Flutter/Django exécutable. Les tests sont donc des preuves écrites de contrat, pas une attestation de validation E2E sur appareil.

Les opérations de paiement, d'éligibilité, de Mandate et de confirmation restent arbitres sur leurs services propriétaires. Le retour depuis Subscription n'exécute jamais le geste initial à la place de l'utilisateur.
