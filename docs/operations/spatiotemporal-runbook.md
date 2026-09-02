# M6 Spatiotemporal operations runbook

Ce runbook couvre uniquement les opérations introduites par M6. Les vérités métier restent dans Activity/Occurrence, Geography, Journey, Access et Capacity.

## Provider outage

Symptômes : `route_estimate`, trafic ou météo absents alors que la destination canonique reste visible.

Actions :

1. vérifier l’état du provider configuré par l’environnement sans exposer de credential ;
2. conserver les providers no-op/deep-link comme fallback ;
3. ne jamais écrire un ETA temporaire dans Occurrence/Journey ;
4. vérifier qu’Activity/Journey et le bouton d’itinéraire destination-only restent utilisables ;
5. réactiver le provider uniquement après retour à une fraîcheur acceptable.

## Stale routing data

Un `RouteEstimate` dont `expires_at <= now` doit être rejeté. Ne pas augmenter artificiellement le TTL pour masquer une panne. Si les données restent stale, désactiver l’implementation provider concernée et revenir au fallback.

## Hazard issue

Si une perturbation incorrecte apparaît :

1. identifier `hazard.key`, `kind`, `source` et la donnée canonique/source externe associée ;
2. corriger l’adapter ou la source, jamais le domaine canonique pour faire disparaître le rendu ;
3. vérifier l’audience avant toute notification ;
4. confirmer qu’une annulation canonique garde priorité sur routing/traffic/weather.

## Notification storm prevention

Les notifications M6 significatives utilisent `Notification.dedup_key`. Ne pas notifier chaque recalcul ETA. En cas de répétition : inspecter la stabilité de la clé source et le job appelant avant tout retry. Ne pas supprimer la contrainte de déduplication.

## Last-minute candidate issue

Si une candidate est incorrecte :

1. vérifier l’Occurrence et son statut ;
2. vérifier `CapacityPool` et `capacity_availability()` ;
3. vérifier visibilité/éligibilité ;
4. vérifier que `nearby_now` n’a été ajouté qu’avec une origine explicite ;
5. ne jamais corriger directement la capacité depuis Recommendation ;
6. le CTA canonique doit revalider l’état au moment de l’action.

Aucune coordonnée GPS utilisateur ne doit être copiée dans un ticket d’incident, un log ou une notification sauf nécessité opérationnelle explicitement autorisée et minimisée.
