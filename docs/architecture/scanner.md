# Module Scanner

## Responsabilité

`scanner` est la couche Makolo de contrôle d’accès. Il consomme les QR signés produits par `tickets`, vérifie l’autorisation de l’agent et de l’événement, marque un billet comme utilisé de façon transactionnelle et conserve un journal d’audit de chaque tentative.

Le module ne fait jamais confiance au contenu du QR côté client. La décision finale est prise par le serveur.

## Modèles

### ScannerAssignment

Une affectation relie un agent à un événement. Elle contient :

- l’événement ;
- l’agent ;
- l’organisateur/staff qui l’a affecté ;
- un libellé de porte ou zone ;
- un état actif/inactif ;
- une fenêtre facultative `valid_from` / `valid_until` ;
- des notes opérationnelles.

Un couple événement + agent est unique.

### ScanLog

Chaque tentative autorisée d’un terminal crée un journal avec :

- l’événement contrôlé ;
- le billet lorsqu’il a pu être identifié ;
- l’agent ;
- l’affectation ;
- le résultat ;
- l’heure ;
- la porte ;
- une référence client idempotente ;
- une empreinte SHA-256 du QR.

Le jeton QR brut n’est jamais stocké dans les journaux.

## Résultats

```text
accepted          accès autorisé
duplicate         billet déjà utilisé
invalid_token     signature/format QR invalide
unknown_ticket    code signé mais billet absent
wrong_event       billet valide pour un autre événement
invalid_status    billet annulé, remboursé ou autrement non valide
event_unavailable événement non publié ou terminé
```

## Autorisation

Le droit de scanner un événement est accordé à :

1. un compte staff ;
2. l’organisateur propriétaire de l’événement ;
3. un utilisateur ayant le rôle actif `scanner-agent` (ou le fallback historique `is_scanner_agent`) **et** une affectation active/courante pour l’événement.

Avoir seulement le rôle scanner-agent ne donne donc pas accès à tous les événements Makolo.

## Anti-double-scan

Le service `scan_ticket()` exécute la décision dans `transaction.atomic()` et verrouille l’événement puis le billet avec `select_for_update()`.

Pour un premier scan valide :

```text
Ticket.valid
  -> lock DB
  -> vérification événement / signature / billet
  -> Ticket.used + used_at
  -> ScanLog.accepted
  -> commit
```

Pour un second scan :

```text
Ticket.used
  -> ScanLog.duplicate
  -> accès refusé
```

Une contrainte conditionnelle de base de données impose en plus qu’un billet ne possède jamais plus d’un `ScanLog` avec le résultat `accepted`.

PostgreSQL reste la cible de production recommandée pour garantir le verrouillage ligne par ligne sous forte concurrence. SQLite reste adapté au développement local mais ne reproduit pas exactement la sémantique de verrouillage de PostgreSQL.

## Idempotence réseau

Les clients peuvent transmettre `client_reference`. Pour un même agent, une nouvelle requête portant la même référence retourne le résultat déjà enregistré au lieu de consommer une deuxième fois le billet.

Cette règle protège notamment les terminaux mobiles contre les doubles soumissions dues à un réseau instable.

## API v1

```text
GET              /api/v1/scanner/events/
GET/POST         /api/v1/scanner/assignments/
GET/PATCH/DELETE /api/v1/scanner/assignments/<id>/
GET              /api/v1/scanner/logs/
POST             /api/v1/scanner/scan/
```

Exemple de requête de scan :

```json
{
  "event_id": "<uuid>",
  "token": "<jeton-qr-signe>",
  "client_reference": "<uuid-du-terminal>",
  "gate": "Porte A"
}
```

Le endpoint de scan est limité à 180 requêtes par minute et par utilisateur authentifié.

## Interface web

```text
/scanner/
/scanner/event/<slug>/
/scanner/event/<slug>/scan/
/scanner/logs/
/scanner/assignments/
```

La console tente d’utiliser l’API navigateur `BarcodeDetector` et la caméra arrière. Si le navigateur ne la supporte pas ou si la permission caméra est refusée, la saisie manuelle du contenu QR reste disponible.

Aucune validation de sécurité n’est effectuée dans JavaScript : le navigateur ne fait que capturer le texte du QR et l’envoyer au serveur.

## Audit et confidentialité

- le QR brut n’est pas persisté ;
- chaque acceptation et chaque refus lié à une tentative autorisée est horodaté ;
- les participants ne peuvent pas consulter les journaux ;
- un agent voit ses propres scans ;
- un organisateur voit les scans de ses événements ;
- le staff dispose du périmètre global.

## Extensions prévues

- mode PWA/offline contrôlé avec synchronisation et politique explicite de conflit ;
- statistiques temps réel dans `analytics_app` ;
- notifications d’incidents ;
- zones multiples / capacités par porte ;
- intégration de matériels scanners dédiés via l’API v1.
