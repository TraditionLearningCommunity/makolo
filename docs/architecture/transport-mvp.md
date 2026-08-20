# Task 12 — Transport MVP

Transport est la première verticale Makolo créée nativement par composition sur le cœur canonique. **Transport est une verticale ; Activity reste le noyau.** Aucun Event n'est nécessaire.

```text
Space
  │
TransportRoute ── TransportRouteStop ── Place
  │
Activity ── TransportService
  │
Occurrence ── TransportDeparture ── Vehicle
  │
  ├── CapacityPool
  ├── Offer
  │
Journey
  │
CommerceOrder / Payment optional
  │
Access
  │
AccessCredential / AccessUse
```

## Responsabilités

- **Route** : itinéraire métier Transport directionnel et arrêts ordonnés, tous référencés vers `geography.Place`.
- **Activity** : service durable, identité éditoriale, Space, visibilité et statut générique.
- **Occurrence** : départ concret ; `start_at`, `end_at`, `timezone` et statut restent exclusivement canoniques.
- **TransportDeparture** : propriétés opérationnelles propres au départ, véhicule, pool passagers et instructions d'embarquement. Aucun horaire dupliqué.
- **Vehicle** : ressource physique d'un Space et plafond physique connu. Ce n'est pas l'inventaire commercial.
- **CapacityPool** : seule vérité des places vendables. Plusieurs Tarifs peuvent partager le même pool.
- **Offer** : Tarif, prix et devise. Le frontend ne fournit jamais le prix faisant foi.
- **Journey** : démarche individuelle du voyageur ; le premier cut limite le parcours public à un bénéficiaire et une place.
- **CommerceOrder / Payment** : commande canonique ; Payment n'existe que lorsqu'un paiement Makolo a réellement lieu. `on_site` et gratuit ne fabriquent aucun paiement réussi.
- **Access** : billet individuel ; `AccessCredential` fournit le QR et `AccessUse` représente l'embarquement.

## Invariants Transport

Une Route valide contient au moins deux stops. `TransportService.activity.space == route.space`. Une `TransportDeparture` cible une Occurrence dont l'Activity possède un TransportService. La CapacityPool passagers cible la même Activity et la même Occurrence. Si un véhicule est affecté, la capacité vendable ne dépasse pas sa capacité physique et une réaffectation ne peut pas descendre sous la capacité déjà held/committed.

Le manifeste est dérivé des Access/AccessUse de l'Occurrence ; aucune table passager parallèle n'est créée. Le contrôle utilise le Scanner canonique et son scope Activity/Occurrence, donc un billet du mauvais départ est refusé et un second scan single-use reste `already_used`.

## Hors scope explicite

Pas de SeatMap ou siège numéroté, pas d'inventaire par segment, pas de GPS live, pas de carte ou découverte spatiale, pas de routing/navigation, pas de GTFS, pas de multi-leg, pas d'objet RoundTrip, pas de settlement marketplace, pas de moteur aérien/ferroviaire avancé, pas de fret ni de logistique chauffeur complexe.

## Cutover

Makolo n'étant pas en production, aucune compatibilité avec une expérimentation ou fake data Transport n'est requise. Aucun ancien modèle Transport incompatible n'a été identifié sur `main` au démarrage de la tâche ; aucun bridge Event/Transport n'est introduit.

## Passage à la Tâche 13

La verticale expose Route, Stops/Places, Occurrences futures, Offers et capacité. La Tâche 13 pourra construire la découverte spatio-temporelle globale sur ces sources sans déplacer la propriété des données vers Transport et sans introduire de géographie parallèle.
