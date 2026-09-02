# Spatiotemporal Intelligence — M6

## Vision

M6 traduit les dimensions **où**, **quand** et **ce qui change** en contexte d’action sans créer de seconde vérité métier.

Invariants :

- `Activity` reste le noyau ; Event, Service et Transport sont des verticales.
- `Occurrence` reste propriétaire des horaires, timezone et statut canonique.
- `Place` / `Zone` restent propriétaires de la géographie.
- `Journey` reste le parcours individuel ; `JourneyStep` peut fournir le prochain engagement pertinent.
- Readiness, Capacity, Access, Commerce, Notifications, Automation, Operations et M5 Discovery conservent leurs responsabilités.
- Les données externes sont des signaux temporaires et non des champs canoniques.

## TemporalContext

`spatiotemporal.temporal.get_temporal_context()` dérive :

- `starts_at`, `ends_at`, timezone ;
- `starts_in`, `ends_in` ;
- `UPCOMING`, `SOON`, `ACTIVE`, `ENDED`, `CANCELLED`.

Aucun countdown n’est persisté. Le seuil `SOON` est centralisé par `SPATIOTEMPORAL_SOON_THRESHOLD_MINUTES` (120 minutes par défaut).

`ActionWindow` et `ArrivalWindow` sont des contrats de projection. Une verticale peut fournir une vraie politique d’arrivée ; M6 ne copie pas ces politiques dans une table générique.

## Geography & privacy

`SpatialContext` compose l’Occurrence, ses `OccurrencePlace`, le `Place` primaire et, lorsque possible, une `Zone` administrative existante.

Une origine utilisateur est un `GeoPoint` **explicitement fourni et éphémère**. M6 n’ajoute ni `current_latitude`, ni `current_longitude`, ni historique de localisation au Profile.

La distance locale est une distance Haversine `straight_line`; elle n’est jamais présentée comme une distance routière. L’itinéraire fallback est un deep-link centralisé et peut fonctionner sans origine.

## Providers & MobilityContext

Les contrats provider-neutral sont :

- `RoutingProvider.estimate_route(origin, destination, departure_at)` ;
- `TrafficProvider.traffic_context(route, observed_at)` ;
- `WeatherProvider.weather_context(place, at, observed_at)`.

Le registry M6 utilise des providers no-op par défaut. Aucun fournisseur commercial, clé ou variable secrète n’est inventé par M6.

`RouteEstimate`, `TrafficSignal` et `WeatherSignal` portent `source`, `observed_at` et, lorsque nécessaire, `expires_at`. Un résultat expiré est ignoré. Les timeouts/indisponibilités se dégradent vers le contexte canonique sans provoquer de 500.

`recommended_departure = target_arrival - route.duration - safety_buffer`.

Le buffer générique est centralisé par `SPATIOTEMPORAL_SAFETY_BUFFER_MINUTES` (10 minutes par défaut). Sans route fiable, M6 ne produit pas d’heure de départ précise.

## Hazards & ActionAdvice

Un `Hazard` est une projection de fait ou signal, jamais une notification. M6 supporte :

- interne : annulation d’Occurrence, Access indisponible ;
- changements canoniques explicitement fournis : retard, changement de Place, gate ou instruction ;
- externe : trafic important, météo de severity WARNING/CRITICAL fournie par un provider.

Les hazards ont une clé stable, une classe INTERNAL/EXTERNAL, une severity, une audience, une source et une fraîcheur. Les hazards expirés sont filtrés et les clés stables permettent la déduplication sans table Hazard parallèle.

Precedence d’action :

1. annulation canonique ;
2. action Access ;
3. `leave_now` lorsque calculable ;
4. warnings trafic/météo ou changement opérationnel significatif ;
5. information.

Une annulation supprime toute suggestion de départ. La météo n’altère pas Readiness à elle seule.

Les notifications M6 utilisent `notifications.services.create_notification()` et ses `dedup_key`. Les recalculs ETA ne déclenchent pas une notification à chaque variation.

## Last-minute opportunities & M5

`LastMinuteOpportunity` est une projection, pas un ticket ni une offre commerciale.

Le pipeline borne tôt les candidates :

1. Occurrences publiées et proches temporellement ;
2. Capacity active et disponible ;
3. visibilité et éligibilité canoniques ;
4. distance locale si une origine a été fournie ;
5. adaptation vers le moteur Recommendation M5.

`capacity_released` exige une vraie `CapacityReservation` récemment `RELEASED`; `nearby_now` n’existe qu’avec une origine explicite. La Waitlist Events, lorsqu’elle existe, reste propriétaire de sa priorité. Le prix reste dans Commerce et le CTA doit toujours revalider Capacity côté serveur.

M5 reste l’unique moteur de recommandations Activity-first. M6 lui fournit seulement des reason codes/candidates. Les projections Journey privées (`leave_soon`, annulation, Access indisponible) restent des éléments personnels non persistants et ne deviennent jamais des posts sociaux.

## Journey & Readiness

M6 recherche d’abord le prochain `JourneyStep` non terminal lié à une Occurrence, puis retombe sur `Journey.occurrence`.

M1 reste propriétaire du status Readiness. Les blockers déjà canoniques (Occurrence annulée, Access indisponible) restent traités par les contributors M1 existants ; M6 ajoute des `ActionAdvice` spatio-temporels sans créer de `SpatiotemporalReadiness`.

## Automation

M6 ne crée aucun scheduler. `spatiotemporal.automation.run_spatiotemporal_automation_cycle()` est branché sur le `automation.scheduler.run_autopilot_cycle()` canonique.

La reevaluation est bornée, provider-free et limitée aux Journeys non terminales avec une Occurrence dans l’horizon configuré. Elle peut donc détecter les hazards canoniques importants (notamment annulation / Access indisponible) et produire des Notifications idempotentes sans GPS, sans polling seconde par seconde et sans appel Routing/Weather de masse.

Les opportunités last-minute restent calculées à la demande et peuvent être notifiées par leurs helpers dédiés lorsqu’un workflow canonique dispose d’une audience bornée. M6 ne scanne pas tous les Profiles pour réserver ou distribuer automatiquement une Capacity.

## Web & API

API :

- `/api/v1/spatiotemporal/journeys/<journey_id>/context/` — participant propriétaire uniquement ; origine optionnelle `lat` + `lon` ;
- `/api/v1/spatiotemporal/last-minute/` — candidates du participant, origine optionnelle.

Le Journey detail consomme la projection M6 et propose l’itinéraire destination-only sans demander automatiquement la géolocalisation. Le generic Activity detail peut afficher le contexte public d’Occurrence. `/me/` reçoit uniquement une projection temporelle minimale et privée ; il ne devient pas le Command Center M8.

Le backend reste utilisable sans JavaScript et sans provider externe.

## Multi-vertical

Le même cœur M6 est exercé sur Event, Service, Transport et Activity générique. Aucune décision spatio-temporelle n’est placée dans `events` et aucun modèle parallèle de lieu, horaire, capacité, accès ou prix n’est créé.

## Security & data minimization

- aucune position précise persistée par défaut ;
- Journey context filtré sur `beneficiary=request.user` ;
- aucun AccessCredential, Profile complet, email, Payment ou CommerceOrder envoyé aux providers ;
- pas de coordonnées privées dans les notification metadata/dedup keys ;
- aucun provider réseau réel dans les tests CI ;
- les pages publiques n’utilisent jamais l’origine privée du participant ;
- l’Automation M6 n’utilise aucune origine GPS et ne met aucune position en cache public.

## Fallbacks

Provider routing indisponible : destination et deep-link restent disponibles, sans ETA inventé.

Traffic/Weather indisponible : aucune dégradation du fait canonique Activity/Journey.

Place absent : aucun bouton itinéraire, mais l’Occurrence reste exploitable.

## Futures capacités

M7 pourra fournir de véritables implementations provider via ces interfaces. M8 pourra composer TemporalContext, SpatialContext, MobilityContext, Hazards et ActionAdvice dans le Cockpit/Journey Command Center. Le futur mobile pourra demander une origine ponctuelle ou afficher `leave_now`; M6 n’introduit ni tracking background, geofence natif, turn-by-turn, Live Activity ni push natif.
