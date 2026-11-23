# Notifications — raccordement des faits réels (13 novembre 2026)

Dépôt : `TraditionLearningCommunity/makolo`. Branche : `fix/discover-a-continuation-context-20261014` ; PR #522, sans merge.

## Intention

Une notification doit signaler un fait confirmé par le domaine propriétaire, pas simuler une activité de réseau social. Les exemples du seed restent disponibles pour les recettes et sont identifiés comme **Démonstration** ; ils ne remplacent jamais les événements réels.

## Existant réutilisé

- `domain_events.services.emit_domain_event` et consommateurs enregistrés par `notifications.apps`, avec traitement après commit et idempotence.
- `notifications.services.create_notification` est propriétaire de la persistance, des préférences et de la livraison externe.
- L'API `/api/v1/notifications/` est limitée au Profil authentifié ; le client conserve un snapshot local par Profil.
- Les signaux de Journey confirmé, paiement, accès émis, changements d'Occurrence, services, formulaires, Conversations et abonnements existent déjà. Ils ne sont pas recréés ici.

## Compléments

Les consommateurs Notifications sont étendus à des transitions **déjà émises** par leurs propriétaires :

| Événement canonique | Destinataire | Signal |
| --- | --- | --- |
| `journey.cancelled` | Bénéficiaire Profil | Démarche annulée |
| `journey.expired` | Bénéficiaire Profil | Démarche expirée |
| `request.rejected` | Auteur de la Demande | Demande refusée |
| `access.revoked` | Bénéficiaire de l'Accès | Accès révoqué |

La paire `request.rejected` / `journey.rejected` est volontairement **non dupliquée** : on notifie la décision de Demande, pas deux messages pour la même décision. Les bénéficiaires externes ou Espaces sans Profil destinataire ne sont pas artificiellement convertis en compte.

Pour `journey.request.rejected` et `access.revoked`, une interruption externe peut être mise en file en suivant les préférences et heures silencieuses existantes. Une notification interne n'est pas une confirmation de livraison email/push.

La liste mobile présente d'abord son snapshot local mais rafraîchit discrètement sur chaque entrée, y compris quand la fraîcheur du dernier snapshot est encore bonne : « localement récent » ne signifie pas « aucun nouvel événement serveur ». Le comportement d'erreur et la réconciliation existants sont préservés.

`NotificationSerializer.is_demo` et les libellés Web/Flutter distinguent les seules notifications marquées `metadata.seed == "makolo-demo"`. Aucun filtrage arbitraire ni suppression des fixtures.

## Hors périmètre

- Pas de nouveau modèle, migration, Permission, endpoint ou moteur de recommandations.
- Pas de notification globale à la publication de chaque Activity : il faudrait une audience légitime et une politique propriétaire (préférences, autorité, ciblage).
- Pas d'alerte opérateur `request.created` tant que les handoffs Web/Flutter et les destinataires Activity/Space n'ont pas été contractualisés ensemble, pour éviter une notification menant vers la Journey privée d'un tiers.
- Pas d'avatar d'agent extrapolé depuis `created_by`, un destinataire ou un champ metadata libre.
- Pas de suppression rétroactive des messages de démonstration ; leurs données restent utiles à la recette.

## Vérification nécessaire

Tests ajoutés dans `notifications/test_real_lifecycle_notifications.py` : annulation, expiration, refus, révocation, destinataire, déduplication et identification demo/réel.

Exécuter localement lorsque Django est disponible :

```powershell
python manage.py test notifications.test_real_lifecycle_notifications notifications.test_m10_shell_navigation notifications.tests
python manage.py check
```

Puis, avec deux Profils dans l'environnement de recette : créer une Activity et une Journey réelles, effectuer une transition via le service propriétaire, constater la notification chez son destinataire et son absence chez l'autre, ouvrir sa destination, marquer comme lue, relancer l'écran Android en présence/absence de réseau et vérifier la copie locale sans fausse confirmation.

**État de cette intervention :** modifications poussées sur #522 ; aucune exécution locale des tests ni recette Android, CI non consultée, aucune fusion.
