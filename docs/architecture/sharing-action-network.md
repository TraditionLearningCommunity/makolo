# Sharing / Action Network

Makolo est un réseau d’action, pas un réseau d’attention. Partager signifie transmettre une possibilité d’avancer, sans créer de feed public, de réputation sociale, de chat ou de popularité.

## Modèle

`ShareEnvelope` porte l’intention, le créateur, l’expiration et la révocation. Les sujets sont explicites : `ActivityShareSubject`, `OpportunityShareSubject`, `JourneyShareSubject`. `ShareLink` est le relay externe à token opaque dont seul le hash est stocké. `ShareDelivery` est recipient-bound pour le direct Makolo → Makolo.

Un share n’accorde jamais Permission, Mandate, Team/Group membership, Access ou AccessCredential. Il ne transfère jamais réservation, Capacity, CommerceOrder, Payment ou validation. Les selectors/policies canoniques sont réévalués à l’ouverture et à l’acceptation.

## Journey reuse

P3 partage un chemin, pas une personne. Le snapshot est versionné et allowlist-first. Il exclut réponses de formulaires, notes privées, documents personnels/identité, paiements/reçus, accès/credentials, assignments, blockers personnels, approvals et eligibility results. `JourneyShareAcceptance` est la provenance canonique de la Journey destination et rend l’acceptation idempotente. Après acceptation, la Journey destination est indépendante : révoquer le share source ne la supprime pas.

## Documents et InboundCapture

`InboundCapture` est un staging privé, temporaire et non canonique. URL, texte et fichier sont validés avant absorption. L’absorption crée un `JourneyArtifact` ou une `JourneyNote`, puis efface la copie staging. Les captures pending expirent après 7 jours et leur cleanup est raccordé à Autopilot.

L’export documentaire est allowlist-first. `can_view != can_export`. Les identity documents, payment receipts et `AccessCredential` ne passent pas par l’export générique. Un reçu importé ne vaut pas Payment success ; un certificat importé n’est pas vérifié.

## Lifecycle

Révocation et expiration rendent le ShareEnvelope inutilisable pour de nouvelles actions, quel que soit le canal. Un ShareLink révoqué ne rend pas l’objet public canonique privé : seule la route `/s/<token>/` et son contexte de partage deviennent indisponibles. Les GET de preview/landing ne créent ni Journey, Order, Payment, Access ni artifact.

## Domain Events et analytics privés

Taxonomie retenue :

- `share.created`, `share.delivered`, `share.opened`, `share.accepted`, `share.declined`, `share.revoked` ;
- `journey.started_from_share` ;
- `capture.created`, `capture.absorbed`, `capture.discarded`, `capture.expired` ;
- `artifact.exported`.

Les événements portent des identifiants techniques minimaux : share/envelope, type de sujet, intent, recipient éventuel, resulting Journey éventuelle et canal réellement connu. Ils n’embarquent jamais réponses de formulaire, notes privées, contenu de capture/fichier, références provider Payment, credentials ou token ShareLink.

`AnalyticsFact` projette ces événements sans `profile` pour Sharing : les dashboards/opérations peuvent agréger created → delivered/opened → accepted → Journey started sans fabriquer de read receipts sociaux. `share.opened` signifie ici ouverture authentifiée d’un `ShareDelivery`; un simple GET de ShareLink externe, potentiellement crawler, n’est pas compté comme humain.

Canaux connus : `external_link`, `direct_makolo`, `journey_reuse`. Makolo ne prétend pas connaître l’application choisie après `navigator.share`.

## Anti-abus

Le direct Sharing reste unitaire, jamais bulk. Les bulk légitimes appartiennent à Audience/CRM/Notifications/Automation. Les vues réutilisent `core.web_throttling` : direct share 12/minute et 60/heure par sender, 8/heure par couple sender-recipient ; recherche Profile 30/minute par Profile/IP ; création InboundCapture 20/heure par Profile. Les réponses rate-limit sont contrôlées en HTTP 429.

La recherche Profile exige l’authentification, exige au moins 2 caractères, retourne au plus 8 résultats et seulement id, display name et username. Aucun e-mail/téléphone/CRM n’est exposé.

Les doubles envois identiques sender → recipient → sujet dans une fenêtre de 30 secondes réutilisent la delivery récente et n’ajoutent pas une seconde Notification. La déduplication reste volontairement courte afin de ne pas fusionner des intentions séparées dans le temps.

## Sécurité et limites volontaires

- tokens opaques, hashés au stockage ; admin = fingerprint uniquement ;
- recipient-bound direct shares ;
- pas de redirect externe arbitraire introduit par Sharing ;
- mutations en POST/CSRF ;
- pas de public share count, trending, top sharers ou ranking Discovery ;
- pas de chat, public feed, Follow implicite, Group/Team membership, consentement CRM ou campagne automatique ;
- pas de bulk direct sharing ;
- pas de partage/transfert de credentials.

La notion canonique de blocage inter-Profile n’est pas introduite par P5 si elle n’existe pas déjà : elle reste un sujet Safety séparé.
