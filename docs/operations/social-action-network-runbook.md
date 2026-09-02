# M5 — Social Action Network operational runbook

Ce runbook couvre uniquement les opérations ajoutées par M5. Il complète `docs/operations-runbook.md` sans modifier les procédures générales de déploiement, sauvegarde ou Autopilot.

## Contribution moderation

Les Contributions sont retirées ou masquées via les services M5 (`moderate_contribution`) et les permissions serveur existantes. Ne pas supprimer physiquement une ligne pour traiter un incident normal : les threads, l’audit minimal et les références historiques doivent rester cohérents.

Pour un contenu problématique :

1. identifier le contexte canonique (Group, Space, Activity, Occurrence) et le viewer concerné ;
2. vérifier l’autorité de modération réelle (auteur pour son propre retrait, modérateur Group, autorité Activity/Space selon périmètre, ou staff) ;
3. passer la Contribution à `HIDDEN` ou `REMOVED` selon le cas ;
4. ne jamais transformer automatiquement ce retrait en sanction Trust ;
5. si un vrai signalement M4 est requis, utiliser le contrat `trust.Report` applicable au contexte vérifiable. Ne jamais créer un système `SocialReport` parallèle.

Les raisons internes de modération ne doivent pas être exposées dans le réseau public ou aux membres ordinaires.

## Incident de contenu privé

Si un membre non autorisé voit une Contribution de Group privé :

1. traiter l’incident comme une régression sécurité prioritaire ;
2. vérifier `GroupMembership`, `GROUP_VIEW`, `can_view_contribution` et les selectors de Group/stream ;
3. vérifier qu’aucun cache public partagé n’a été introduit ;
4. retirer temporairement le contenu de la surface si nécessaire sans supprimer l’historique ;
5. reproduire avec membre autorisé et outsider avant correction ;
6. ajouter ou renforcer un test IDOR/privacy avant merge de la correction.

M5 ne stocke pas de média Contribution ; il n’existe donc pas d’URL média sociale publique à purger dans cette version.

## Action Stream / Recommendations incident

Le flux M5 est une projection, pas une table à reconstruire. En cas d’item manquant, dupliqué ou privé :

- vérifier d’abord Follow, Group membership, Activity visibility/status et Contribution status ;
- vérifier les limites par source, fenêtre temporelle, déduplication et cap de diversité ;
- vérifier les reason codes Discovery et le filtrage des candidates avant ranking ;
- ne jamais lancer de backfill `FeedItem` et ne pas créer de cron de matérialisation pour corriger un incident ;
- ne jamais utiliser followers, likes ou vues comme contournement de ranking.

Une recommendation issue d’un historique privé peut utiliser un reason code générique (`past_activity_interest`) mais ne doit jamais révéler le détail de la Journey privée.

## Personal Goals incident

Les valeurs de progrès sont dérivées des Journeys canoniques `FULFILLED`. Si un Goal semble bloqué ou complété à tort :

1. vérifier la période du Goal et son `goal_type` ;
2. vérifier les Journey facts canoniques du propriétaire ;
3. exécuter l’évaluation idempotente via le service Goals approprié ;
4. vérifier la notification in-product dédupliquée ;
5. ne jamais éditer manuellement un compteur de progrès — il n’existe pas comme vérité persistée ;
6. ne jamais ajouter/retirer des points Loyalty pour « réparer » un Goal.

Un Goal reste privé. Toute fuite d’un Goal entre Profiles est une régression IDOR à corriger côté serveur.

## Diagnostic minimal après déploiement M5

Vérifier au minimum :

- visiteur : aucune fuite de Group privé ;
- participant : Follow Space, `/network/`, recommendation avec explication, Group autorisé, History, Goals ;
- Group outsider : 403/absence de contenu privé ;
- opérateur autorisé : update officielle dans son périmètre seulement ;
- staff : modération sans élévation des droits participant ;
- aucun 500 sur les surfaces M5.

PythonAnywhere, lorsqu’utilisé, reste uniquement un environnement temporaire de test et ne change pas ces contrats d’architecture.
