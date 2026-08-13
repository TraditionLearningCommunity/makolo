# Activity et Occurrence

`activities` est le noyau spatio-temporel transversal de Makolo.

- `Activity` porte l'identité durable : Espace principal, créateur, titre, descriptions, statut et visibilité.
- `Occurrence` porte une réalisation temporelle : début, fin éventuelle, timezone IANA et statut.
- `OccurrencePlace` relie une Occurrence à un `geography.Place` avec un rôle générique limité : `primary`, `meeting_point`, `service_point`, `other`.

Les nouvelles Activities créées par les services doivent appartenir à un Espace. `space=NULL` reste uniquement une compatibilité pour les Events historiques sans Organization ; le backfill n'invente pas d'Espace.

## Autorité

Le portefeuille Espace utilise `space.activities.view` et `space.activities.manage`. Une délégation locale utilise `activity.view` et `activity.manage` avec un Mandat de portée `activity`. La résolution accepte d'abord le Mandat Activity direct, puis l'héritage depuis l'Espace propriétaire. Un Mandat Activity ne donne aucune autorité Finance, Équipe, Groupes ou Lieux sur l'Espace.

Le rôle Espace historique devient `space-activity-manager` — Responsable des activités. Le nouveau `activity-manager` — Responsable de l'activité — est Activity-scoped.

## Compatibilité Events

`events.Event` reste la verticale runtime et compose le noyau via un `OneToOneField` vers Activity. Le backfill crée exactement une Activity et une Occurrence par Event, sans fusion par titre. `EventVenue.place` devient le lieu principal de l'Occurrence lorsqu'il existe ; `online_url` reste dans Events.

Le bridge explicite `events -> activities` synchronise création, modification, publication, annulation et fin. `activities` n'importe jamais `events`.

Les champs historiques Event restent temporairement présents : Organization/organizer, titre/descriptions, start/end/timezone, EventVenue, catégorie, fenêtres d'inscription, capacité et les FK Event des autres domaines. Journey/Request/Access, Commerce générique, Transport et le cutover final Events restent hors scope.

Aucune `GenericForeignKey` n'est introduite.
