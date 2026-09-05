# C1 — Discovery correctness hardening

C1 corrige la vérité des résultats Discovery sans introduire le futur moteur scientifique de ranking.

## Candidate identity

Candidate identity identifies the real possibility; provenance explains why it was surfaced. Related possibilities are not automatically duplicates.

- `occurrence:<occurrence_id>` identifie une réalisation temporelle canonique, quelle que soit sa verticale.
- `service_activity:<activity_id>` identifie un Service Activity-first sans fabriquer d’Occurrence.
- `opportunity:<opportunity_id>` identifie durablement l’Opportunity ; la projection conserve séparément la révision publiée observée.
- `family` décrit la structure du candidat ; `vertical` décrit la spécialisation métier. Les deux notions ne sont pas interchangeables.

Les déduplications C1 sont uniquement des déduplications d’identité exacte. Une Opportunity et le Service qui peut aider à l’atteindre restent deux possibilités distinctes.

## Relation avec le presentation contract

C1 reste indépendant du nouveau contrat de cartes de la PR #198. Le seul chevauchement intentionnel est la correction minimale de la résolution canonique de verticale Service dans `core.product_language.vertical_for`; les abstractions de présentation de #198 ne sont ni copiées ni réimplémentées ici. La convergence finale devra conserver la vérité C1 (identité, Offer/Capacity occurrence-aware, filtres et viability) dans le contrat de présentation.

## Baselines

Les poids historiques de recommandation et `build_trending()` restent disponibles comme baselines expérimentales. Trending n’est plus présenté sur la surface principale `For You` comme doctrine du futur moteur Makolo.

## Follow-ups hors C1

- instrumentation d’exposition `candidate_shown/opened/acted` seulement lorsqu’un contrat analytics/domain-event privacy-safe et sans migration est arrêté ;
- convergence média générique au-delà des primitives réellement disponibles ;
- généralisation Ticketing occurrence-aware au-delà du hardening conservateur des Occurrences Event secondaires.
