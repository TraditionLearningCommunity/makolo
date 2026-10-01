# Socle transversal de lecture et performance

**Statut :** fondation adoptée progressivement  
**Portée :** Django HTML, HTMX, API et clients installés consommant les mêmes vérités de lecture  
**Frontière :** ce socle ne définit aucun ranking, recommandation, sélection de pertinence ou intelligence Molongo.

## 1. Chemin de lecture

Le chemin cible est :

```text
domaines canoniques
  -> selectors
  -> read models partagés
  -> batching / query planning / ProjectionBudget
  -> presenters Web ou serializers API
  -> Web / HTMX / mobile / futurs clients
```

Un read model ne possède pas les vérités métier. Il compose des faits déjà
autorisés par leurs owners. Il ne transfère jamais Permission, Mandate, Access,
Payment ni accès à des données privées.

## 2. Request scope

`request.makolo` est un contexte HTTP éphémère. Il contient uniquement :

- `observed_at` ;
- un `request_id` non métier ;
- la surface dérivée du routage ;
- une memoization strictement limitée à la requête.

Il ne duplique ni `request.user`, ni session, ni Journey, ni Permission, ni
Readiness. Son middleware ne fait aucune requête lors de l'attachement.

La memoization de requête est le niveau L1. Elle ne nécessite aucune
invalidation inter-requêtes.

## 3. Surface policy

`SurfaceContext` décrit les capacités de shell nécessaires à la route
courante. Presentation décide ce qu'elle demande ; les domaines propriétaires
décident toujours ce qui est vrai.

Adoption initiale :

- le badge Notifications n'est résolu que sur la surface primaire Maintenant ;
- le badge Conversation n'est résolu que sur cette même surface et son travail
  est borné pour l'affichage `9+` ;
- l'activation du Profil est memoïsée quand le menu compte en a besoin ;
- les surfaces Space demandent navigation/autorité Space et ne paient pas les
  badges personnels Maintenant.

Le masquage d'un élément de shell n'est jamais un contrôle de sécurité.

## 4. ProjectionBudget

`core.projections.ProjectionBudget` borne le nombre d'éléments qu'une
projection composite peut encore présenter.

Il conserve l'ordre fourni par les owners et ne choisit jamais les éléments
« les plus pertinents ». Il ne doit donc recevoir aucun algorithme Molongo.

Règle :

> une famille qui ne peut plus fournir de ligne à la réponse ne doit pas être
> matérialisée.

Des sondes `exists()` restent légitimes lorsqu'une information d'existence est
elle-même affichée, par exemple un lien secondaire.

## 5. Read models partagés

`core.read_models.personal_ongoing.build_personal_ongoing_read_model()` est la
première adoption représentative.

Il compose, dans l'ordre contractuel existant, Journey, Access, Dossier,
Project, Waitlist, Transfer et Payment. Le Web peut demander en plus la famille
Funding sans élargir silencieusement le contrat réseau mobile.

- Readiness Journey reste batchée par `resolve_many(...)` ;
- Readiness Dossier reste batchée par son owner ;
- Access utilise une profondeur ORM adaptée à la projection ;
- le Web et l'API appliquent désormais le même budget de 18 avant présentation.

Le Web consomme directement le read model Python ; il n'appelle pas sa propre
API JSON.

## 6. GET sans écriture implicite

`build_profile_activation_summary()` n'utilise plus
`UserProfile.objects.get_or_create()`.

Une extension Profile historique manquante est représentée en mémoire pendant
la lecture. Sa création appartient aux flux explicites de création/édition du
compte, pas au rendu d'une page.

## 7. HTMX

`is_fragment_request()` et `FragmentTemplateMixin` fournissent une convention
serveur explicite.

L'adoption initiale `/me/ongoing/` :

- réponse normale : document complet ;
- requête HTMX ciblant `main-content` : base fragmentaire ;
- même read model et mêmes partials métier dans les deux cas ;
- topbar/sidebar/bottom-nav restent disponibles pour les sélections OOB ;
- le fragment ne reconstruit pas `<head>`, les bundles globaux, le footer ni
  la palette de commande.

`hx-select` reste une technique client ; il n'est plus considéré, à lui seul,
comme une optimisation serveur.

## 8. Assets par capacité

`share-actions.js` n'est plus chargé par le shell universel.

Il est chargé uniquement sur les surfaces qui rendent effectivement des
contrôles Share : Discover et les détails Activity/Opportunity/Funding/Obtention
concernés. Le découpage reste par capacité, pas par micro-page.

## 9. Cache : niveaux autorisés

Le modèle de référence est :

```text
L0 ORM déjà chargé
L1 memoization request-scoped
L2 Django cache court, seulement avec contrat d'invalidation clair
L3 HTTP conditional/cache headers sur réponses compatibles
L4 statics fingerprintés/immutables
```

Cette fondation implémente L1 et conserve L4 existant. Elle n'ajoute pas L2/L3
aux Permissions, Mandates, Access, Readiness ou projections privées : aucun
contrat d'invalidation assez robuste ne justifie encore ce risque. Aucun Redis,
Celery ou provider externe n'est introduit.

## 10. Observabilité

`PerformanceEnvelopeMiddleware` est désactivé par défaut et activable par
`MAKOLO_PERFORMANCE_LOGGING`.

Il mesure sans payload ni PII :

- route nommée ;
- méthode ;
- statut ;
- durée totale ;
- nombre de requêtes SQL ;
- temps SQL approximatif ;
- taille de réponse ;
- mode full/fragment ;
- request id.

Les seuils `MAKOLO_PERFORMANCE_WARN_MS`,
`MAKOLO_PERFORMANCE_WARN_QUERIES` et `MAKOLO_PERFORMANCE_WARN_KB` sont
configurables. La valeur zéro désactive le seuil correspondant. Aucun seuil
métier arbitraire n'est figé avant mesure.

## 11. Contrats de régression

La fondation ajoute des tests sur :

- stabilité/memoization du contexte request-scoped ;
- absence de calcul Notifications/Conversation hors de Maintenant ;
- absence d'écriture Profile pendant une lecture ;
- croissance SQL bornée de la vue Web En cours ;
- vrai fragment HTMX sans document/assets complets ;
- absence de Share JS sur une surface qui ne le nécessite pas ;
- policy Space sans badges personnels ;
- enveloppe d'observabilité sans email/payload.

Les contrats Z12 existants continuent de couvrir la croissance SQL des
projections API, Access, Dossier Readiness et Resources.

## 12. Décisions volontairement refusées

Cette fondation n'introduit pas :

- de domaine ou table `Performance` ;
- de snapshot métier persistant ;
- de Redis ;
- de cache partagé de Permission/Mandate/Access ;
- d'index spéculatif ;
- de migration ;
- de nouvelle vérité mobile serveur ;
- de moteur de ranking, pertinence, recommandation ou priorité ;
- de refonte CSS/UX.

Les prochains read models doivent adopter ces primitives uniquement lorsqu'un
chemin de lecture réel le justifie, après mesure et sans déplacer la propriété
métier.
