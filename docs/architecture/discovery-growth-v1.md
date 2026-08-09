# Discovery V1 + Growth V1

Ce document décrit les lots **A2 Discovery V1** et **A3 Growth V1**. Leur objectif est volontairement limité aux six premiers mois d'usage : aider un participant à trouver un événement utile et aider un organisateur à comprendre les premières sources d'acquisition/rétention sans construire prématurément un réseau social complet ni un moteur ML.

## A2 — Discovery V1

### Périmètre

Discovery V1 fournit :

- recherche événement par mot-clé ;
- filtres catégorie, ville, organisateur, gratuit/payant et période ;
- tris bientôt, nouveautés et populaire ;
- favoris participant ;
- page `Pour vous` ;
- tendances ;
- hub `Mes événements` avec billets à venir, historique, favoris et organisateurs suivis ;
- recommandations déterministes avec raisons visibles.

Routes web :

```text
/discover/
/discover/for-you/
/discover/bookmarks/
/discover/my-events/
```

API :

```text
GET  /api/v1/discovery/events/
GET  /api/v1/discovery/for-you/
GET  /api/v1/discovery/bookmarks/
POST /api/v1/discovery/bookmarks/
DELETE /api/v1/discovery/bookmarks/<event-uuid>/
```

### Frontière publique

`public_discovery_events()` est la source de vérité Discovery. Un événement candidat doit être :

- `published` ;
- `public` ;
- non terminé ;
- non rattaché à une organisation suspendue.

Les événements `unlisted` et `private` ne sont jamais utilisés dans recherche, tendances ou recommandations, même pour un utilisateur authentifié. Les favoris ne peuvent être créés depuis Discovery que pour un événement appartenant à cette surface publique.

### Recommandation V1

Aucun modèle ML n'est utilisé. Le score est explicite et stable :

- organisateur suivi : signal fort ;
- catégorie déjà achetée ou mise en favori : signal fort ;
- ville connue via profil/achats : signal modéré ;
- commandes confirmées, favoris et followers : popularité ;
- proximité de la date : bonus léger.

Les événements déjà achetés sont retirés des recommandations personnalisées. Les raisons exposées au participant restent compréhensibles :

```text
Parce que vous suivez <organisateur>
Parce que vous aimez les événements <catégorie>
Près de vous à <ville>
Populaire en ce moment
```

Ce modèle est intentionnellement préférable à un algorithme opaque tant que Makolo ne possède pas encore une densité de données suffisante.

### Favoris

`EventBookmark` est une relation utilisateur → événement unique. Le favori :

- n'accorde aucun droit ;
- n'est pas un consentement marketing ;
- sert uniquement à l'expérience participant et comme signal explicable de Discovery.

## A3 — Growth V1

Growth V1 ne remplace pas `analytics_app`, Partners, CRM ou Promotions. Il fournit une couche simple destinée aux premiers organisateurs et réutilise ces domaines comme sources de vérité.

### Liens et QR marketing

`MarketingLink` appartient à une organisation et à un événement, avec un canal :

```text
WhatsApp
Instagram
Facebook
QR / affiche
Flyer
Partenaire
E-mail
Autre
```

Le lien public est :

```text
/g/<code>/
```

Il peut être converti en QR PNG depuis l'espace Growth.

Une visite `MarketingLinkVisit` conserve uniquement :

- le lien ;
- un hash SHA-256 de la clé de session ;
- le domaine référent, jamais l'URL référente complète ;
- l'utilisateur seulement s'il est authentifié ou s'il se connecte ensuite dans la même session ;
- le timestamp.

Aucun IP, fingerprint navigateur, pixel tiers ou donnée cachée n'est ajouté.

### Attribution source → commande

Le modèle est **last valid first-party visit** :

1. le participant ouvre `/g/<code>/` ;
2. Makolo enregistre la visite minimale dans sa session ;
3. après authentification, cette visite peut être liée au compte dans la même session ;
4. lors de la création d'une commande pour le même événement, la dernière visite encore dans sa fenêtre d'attribution est utilisée ;
5. l'attribution suit le cycle de la commande : `pending` → `confirmed` ou `reversed`.

`MarketingAttribution` est indépendant de :

- `CampaignAttribution` CRM ;
- `ReferralAttribution` Partners ;
- `PromotionRedemption`.

Ces preuves peuvent coexister sur une même commande. Makolo ne transforme pas une source marketing en attribution CRM et n'invente pas un clic CRM.

Le snapshot `revenue_amount` suit le vrai `TicketOrder.total_amount`, y compris lorsqu'une promotion légitime modifie une commande `pending` avant paiement. Les revenus restent séparés par devise.

### Feedback post-événement

`EventFeedback` est privé. Seul un participant possédant une commande/billet confirmé pour un événement terminé peut soumettre une note 1–5 et un commentaire optionnel.

Le commentaire :

- n'est jamais publié sur la page publique ;
- est visible uniquement aux rôles Owner/Admin/Event Manager/Marketing et staff ;
- n'est pas exposé à Finance par simple rôle financier ;
- peut être modifié par son auteur via un second envoi.

Growth V1 mesure uniquement le nombre de réponses et la moyenne de satisfaction. Il ne présente pas ce score comme un avis public ou une réputation plateforme.

### Presets CRM

Growth V1 propose des raccourcis qui créent de vrais `CRMWorkflow` et `CRMWorkflowAction` :

- bienvenue nouvel abonné ;
- relance réservation expirée ;
- rappel J-1 ;
- remerciement participant ;
- réactivation no-show.

Les presets sont idempotents. Une fois créés, ils restent visibles et modifiables dans CRM Automation.

Le preset no-show est explicitement `marketing_action=True`. Il conserve donc tous les contrôles existants de consentement et préférences au moment de l'exécution. Un preset ne constitue jamais un consentement implicite.

### Dashboard fondateur

Le dashboard Growth V1 affiche volontairement peu d'indicateurs :

- followers ;
- acheteurs uniques ;
- repeat buyers et repeat rate ;
- billets vendus ;
- taux de présence ;
- visites de liens marketing ;
- conversions source ;
- satisfaction privée ;
- conversions CRM.

Owner/Admin/Finance peuvent également voir les montants par devise. Marketing et Event Manager n'obtiennent pas les montants financiers individuels ou agrégés réservés à Finance.

Pour les analyses avancées (cohortes, LTV, ROI de contribution), la source reste `analytics_app` sous `/analytics/growth/`.

## Permissions

| Capacité | Owner/Admin | Marketing | Event Manager | Finance | Scanner Manager | Participant |
|---|---:|---:|---:|---:|---:|---:|
| Discovery public | oui | oui | oui | oui | oui | oui |
| Favoris personnels | personnel | personnel | personnel | personnel | personnel | personnel |
| Voir dashboard Growth V1 org | oui | oui | oui | oui | non | non |
| Créer/pause lien marketing | oui | oui | non | non | non | non |
| Générer QR marketing | oui | oui | non | non | non | non |
| Voir montants Growth V1 | oui | non | non | oui | non | non |
| Lire feedback privé | oui | oui | oui | non | non | auteur seulement via édition |
| Activer presets CRM | oui | oui | non | non | non | non |

`is_staff` conserve la supervision plateforme globale.

## Migrations

```text
discovery.0001_initial
growth.0001_initial
```

## Limites assumées

Ces lots ne comprennent volontairement pas :

- feed social entre participants ;
- commentaires/avis publics ;
- messagerie ;
- recommandations ML ;
- A/B testing ;
- multi-touch attribution ;
- tracking cross-device ;
- géolocalisation GPS persistante ;
- infrastructure Go-Live A1 (PostgreSQL, PSP réel, object storage, supervision production).

Ces sujets ne sont pas nécessaires pour valider les premières boucles Makolo : **découvrir → acheter → participer → revenir**, puis **acquérir → convertir → mesurer → réactiver**.
