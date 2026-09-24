# M10.0 — Fermeture Shell & Structured Navigation

> **Statut : gate final M10.0.** Lorsque ce document est présent sur `main` après CI verte, M10.0 est fermé. Ce document ferme une couture transversale entre le backend personnel Mature et le futur client natif. Il ne rouvre pas le programme Z et ne déclare pas M10 globalement terminé.

## Mission

M10.0 prouve que le shell personnel peut être construit sans inférence métier locale :

```text
Maintenant | Découvrir | Makolo Mark | En cours | Moi
```

et que ses outils transversaux utilisent les owners existants :

- Conversations ;
- Notifications ;
- identité/compte ;
- préférences ;
- activation Profile dérivée ;
- lecture temporelle d'En cours.

Aucun domaine `Shell`, `Calendar`, `MobileNavigation` ou `NotificationTarget` persistant n'est introduit.

## Navigation structurée des Notifications

`Notification.navigation` devient un hint de navigation additif versionné :

```json
{
  "schema_version": 1,
  "target": "journey",
  "journey_id": "uuid",
  "activity_id": "uuid éventuel",
  "resource": {
    "kind": "journey",
    "id": "uuid"
  },
  "links": {
    "api": "/api/v1/me/journeys/<uuid>/"
  }
}
```

Le serializer conserve les identifiants historiques Event/Order/Payment/Ticket et accepte les identifiants structurés Mature déjà portés par les notifications :

```text
activity_id
journey_id
access_id
occurrence_id
conversation_id
group_id
partner_id
dossier_id
project_id
personal_asset_id
```

Le champ `action_url` reste compatible Web/legacy mais le client natif ne le parse jamais pour reconstruire une identité métier.

Une destination structurée n'est jamais une permission. L'endpoint owner reste responsable du scope, de l'autorité, de la confidentialité et de l'état courant ; il peut légitimement retourner 404/403.

Event reste une compatibilité particulière : un `event_id` seul n'autorise pas Makolo à inventer un slug ou un owner link.

## APIs privées du shell

Les lectures privées utilisées directement par le shell sont explicitement `Cache-Control: private, no-store` :

```text
GET /api/v1/accounts/auth/me/
GET /api/v1/accounts/notification-preferences/
GET /api/v1/notifications/...
GET /api/v1/conversations/...
GET /api/v1/me/...
```

Les mutations correspondantes protégées par ces vues conservent la même politique de cache lorsque leur réponse contient de l'état personnel.

## Avatar et Moi

Avatar et Moi restent distincts.

Avatar utilise les owners existants pour :

- identité authentifiée ;
- édition de Profile ;
- préférences de notification ;
- compte.

L'activation Profile affichable dans le shell vient de la projection dérivée déjà fournie par `GET /api/v1/me/`. Le champ historique `profile_completed` n'est pas élevé au rang de vérité Mature.

M10.0 ne crée aucun mode `act_as_space`. Le mode Profile représentant un Space reste un programme séparé soumis aux Permissions/Mandates réels.

## Calendrier En cours

Le calendrier du header `En cours` est une lecture UX de la temporalité déjà exposée par `personal.ongoing`.

Il n'existe pas et M10.0 ne crée pas :

```text
/api/v1/me/calendar/
Calendar
CalendarItem
CalendarState
```

Le client peut organiser visuellement les champs `timing`, `next` et les états de continuité fournis par En cours sans créer une nouvelle vérité métier.

## Ce qui reste explicitement hors M10.0

M10.0 ne ferme pas artificiellement :

- mutations Group mobile dédiées ;
- upload PersonalAsset depuis mobile ;
- création/révocation ShareEnvelope Passport mobile ;
- Universal Links / Android App Links ;
- push natif ;
- realtime générique ;
- offline mutations/sync ;
- provider Payment production ;
- modalité fichier/voix générique du Mark ;
- mode Space actor.

Ces capacités restent chez leurs owners et/ou dans les programmes A/M10 appropriés lorsqu'un besoin réel les exige.

## Persistance et migrations

Aucun modèle et aucune migration.

La navigation structurée est une projection calculée à partir des FKs canoniques et métadonnées fonctionnelles déjà présentes sur Notification.

## Gate de fermeture

M10.0 est fermé lorsque :

- le `main` de départ est vert ;
- les routes shell réutilisent les APIs owners existantes ;
- Notification navigation couvre les identités Mature démontrées sans parser `action_url` ;
- legacy Event/Order/Payment/Ticket reste compatible ;
- les APIs privées du shell sont `private, no-store` ;
- aucun actor override client n'est introduit ;
- aucun Calendar/domain/mobile namespace parallèle n'est ajouté ;
- tests ciblés, contrôle migrations et CI complète sont verts ;
- la PR est mergée puis `main` redevient vert.
