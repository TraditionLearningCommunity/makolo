# Analytics & Event Intelligence

## Objectif

`analytics_app` est le domaine canonique de lecture et d'aide à la décision de Makolo. Il ne remplace pas les domaines métier (`activities`, `events`, `journeys`, `services`, `opportunities`, `payments`, `scanner`, `partners`) et ne duplique pas leurs états transactionnels.

Les dashboards transactionnels sont calculés depuis les modèles canoniques. `AnalyticsFact` reste réservé à l'historique événementiel utile issu des Domain Events ; il ne devient pas une copie générale des modèles métier. Aucun snapshot Services persistant n'est nécessaire en V1 : des snapshots/materialized views ne seront ajoutés que si une mesure de performance le justifie.

## Frontières d'autorisation et de confidentialité

Analytics ne doit jamais devenir un contournement des permissions métier.

Pour les Activities appartenant à un Espace, l'accès Analytics réutilise les permissions Analytics canoniques. Pour une Activity personnelle, l'autorité vient du propriétaire logique `owner_profile` ; `created_by` n'est qu'une provenance, avec compatibilité limitée aux anciennes lignes dépourvues de propriétaire logique.

Les métriques financières ne sont exposées qu'avec la permission financière Analytics correspondante. La capacité à gérer un dossier Services ne donne pas automatiquement accès aux montants financiers. Makolo ne somme jamais des monnaies différentes dans un seul montant.

Les réponses Analytics restent agrégées et privacy-safe. Elles ne doivent pas contenir inutilement : nom, e-mail ou téléphone participant, contenu ou nom sensible d'un document, note interne, numéro de pièce, référence provider, reçu, CV ou payload libre.

## Indicateurs événement

Le détail `/analytics/events/<slug>/` expose notamment :

- billets actifs et réservations en attente ;
- capacité, remplissage et capacité restante ;
- commandes confirmées / en attente / annulées / expirées ;
- conversion commande ;
- tentatives et succès de paiement ;
- conversion paiement ;
- présence observée via billets utilisés ;
- waitlist et conversion waitlist -> billet ;
- transferts de billets ;
- vitesse de vente 7 jours vs. 7 jours précédents ;
- séries de billets émis ;
- pics de scans acceptés ;
- performance par catégorie de billet ;
- acquisition partenaires ;
- revenus brut / remboursé / net, séparés par devise lorsque le rôle y a droit ;
- commissions d'affiliation par devise lorsque le rôle y a droit.

## Analytics Services V1 — T36

Une Activity n'entre dans les Analytics Services que si elle possède le contrat canonique `ServiceDetails`. Une vue Services ne mélange donc pas automatiquement Events, Transport et Services.

Le read model Services V1 est calculé depuis `Journey`, `JourneyStep`, `JourneyBlocker`, `JourneyAssignment`, `JourneyArtifactReview`, `ServiceJourneyContext`, `ServiceSubmission`, `ServiceOutcomeEvent`, `PaymentObligation`, `Payment` et `PaymentEvidence`.

Métriques livrées :

- volume de Journeys Services ;
- taux de démarrage, défini explicitement par `journeys_started / journeys_created` ;
- taux d'accomplissement Makolo, défini par `journeys_fulfilled / journeys_started` ;
- taux de succès externe, défini séparément depuis les outcomes courants `successful / (successful + unsuccessful)` ;
- temps moyen jusqu'au fulfillment, uniquement pour les dossiers avec timestamps cohérents `started_at -> fulfilled_at` ;
- durée moyenne des Steps par type, en excluant les Steps sans timestamps de durée fiables ;
- Steps actuellement overdue et Steps terminées en retard ;
- blockers par statut, catégorie et sévérité ;
- funnel objectivement observable Opportunity -> Journey et Journey -> ServiceSubmission, sans inventer un dénominateur de vues non collecté ;
- nombre de tentatives et statuts de `ServiceSubmission` ;
- distribution des outcomes courants et historique des `ServiceOutcomeEvent`, sans confondre les deux ;
- charge opérationnelle via les `JourneyAssignment` actifs ;
- reviews et turnaround lorsque les timestamps le permettent ;
- obligations de paiement par statut/mode ;
- tentatives `Payment` provider et échecs distincts des obligations ;
- `PaymentEvidence` externe par statut ;
- montants financiers uniquement avec permission financière, toujours groupés par devise.

Chaque pourcentage expose son numérateur et son dénominateur. Une Journey non fulfilled ne reçoit jamais de durée de fulfillment fictive.

Principe essentiel :

> `Journey.fulfilled` signifie que Makolo a terminé son engagement. Il ne signifie pas qu'un tiers a accepté le participant.

Le taux d'accomplissement Makolo et le taux de succès externe restent donc deux métriques, deux sources et deux axes différents, même lorsqu'une fixture produit accidentellement la même valeur.

## Performance Analytics Services

Les agrégations Services sont DB-first (`Count`, `Avg`, `Sum`, filtres et relations canoniques). Le read model ne charge pas tous les Journeys, Steps ou Blockers en Python pour compter. Un test de croissance de requêtes vérifie que l'ajout de plusieurs Journeys n'entraîne pas une croissance N+1 du nombre de requêtes.

Aucun `DailyServiceMetric`, `ServiceJourneyMetric`, cache de vérité ou index spéculatif n'est introduit par T36.

## Event Intelligence

Les insights sont déterministes et explicables. Ils ne prétendent pas être une intelligence artificielle opaque et ne déclenchent aucune décision financière ou de capacité automatiquement.

Exemples de signaux :

- capacité >= 90 % ;
- waitlist non vide ;
- conversion paiement faible avec volume significatif ;
- accélération ou ralentissement du rythme de vente ;
- présence faible après le début de l'événement ;
- commandes en attente bloquant temporairement du stock ;
- projection de sold-out avant le début de l'événement ;
- trafic partenaire significatif mais faible conversion ;
- partenaire générant un volume confirmé remarquable.

La projection de sold-out utilise le rythme moyen de billets actifs depuis le début effectif de la vente/publication. C'est une estimation opérationnelle, pas une garantie.

## API

```text
GET /api/v1/analytics/overview/
GET /api/v1/analytics/events/<slug>/
GET /api/v1/analytics/events/<slug>/?days=7|30|90
GET /api/v1/analytics/services/activities/<uuid>/
```

Le détail Services applique les mêmes frontières d'autorisation que l'interface web. Un utilisateur hors scope reçoit la convention anti-IDOR du selector ; un rôle Analytics sans permission financière reçoit les métriques non financières sans montants.

## AnalyticsFact et Domain Events Services

T36 ne whitelist pas automatiquement tous les événements Services dans `AnalyticsFact`. Les métriques V1 sont obtenues de façon fiable depuis les modèles canoniques et, pour l'historique des résultats externes, depuis `ServiceOutcomeEvent`.

Un événement Services ne doit être projeté dans `AnalyticsFact` que lorsqu'un besoin historique réel l'exige et avec un payload minimal, idempotent et sans PII inutile. Les nouvelles Analytics ne doivent déclencher aucun side effect métier, Notification, Automation ou Audience CRM.

## Différés explicites

Ne font pas partie des Analytics Services V1 : IA/ML scoring, ranking automatique, recommandations opaques, analytics prédictives avancées, snapshots prématurés et feature gating Subscription spéculatif. Ces évolutions exigent une décision produit et des preuves de besoin distinctes.
