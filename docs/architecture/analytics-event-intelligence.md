# Analytics & Event Intelligence

## Objectif

`analytics_app` est un domaine de lecture et d'aide à la décision. Il ne remplace pas les domaines métier (`events`, `tickets`, `payments`, `scanner`) et ne duplique pas leurs états transactionnels.

Les indicateurs sont calculés à partir des sources de vérité existantes :

- événements et capacité ;
- commandes et catégories de billets ;
- billets valides/utilisés/remboursés ;
- paiements et remboursements ;
- waitlist et transferts ;
- scans acceptés.

Aucun modèle analytique persistant n'est nécessaire dans cette première version : cela évite les désynchronisations pendant que le produit évolue rapidement. Des snapshots/materialized views pourront être ajoutés plus tard si le volume le justifie.

## Frontières d'autorisation

Analytics ne doit jamais devenir un contournement des permissions métier.

Tous les rôles d'équipe peuvent recevoir des indicateurs agrégés compatibles avec leur fonction :

- Owner / Admin : vue complète ;
- Event manager : performance événementielle et billetterie ;
- Finance : performance événementielle + revenus/remboursements ;
- Marketing : performance agrégée, ventes, remplissage, waitlist, sans données clients ;
- Scanner manager : performance agrégée et contrôle d'accès, sans données financières.

Les métriques financières ne sont exposées qu'aux rôles finance (`Owner`, `Admin`, `Finance`) ou au staff plateforme. Les réponses Analytics ne contiennent aucun nom, e-mail, téléphone, QR ou identifiant de paiement client.

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
- revenus brut / remboursé / net, séparés par devise lorsque le rôle y a droit.

Makolo ne somme jamais des monnaies différentes dans un seul montant.

## Event Intelligence

Les insights sont déterministes et explicables. Ils ne prétendent pas être une intelligence artificielle opaque et ne déclenchent aucune décision financière ou de capacité automatiquement.

Exemples de signaux :

- capacité >= 90 % ;
- waitlist non vide ;
- conversion paiement faible avec volume significatif ;
- accélération ou ralentissement du rythme de vente ;
- présence faible après le début de l'événement ;
- commandes en attente bloquant temporairement du stock ;
- projection de sold-out avant le début de l'événement.

La projection de sold-out utilise le rythme moyen de billets actifs depuis le début effectif de la vente/publication. C'est une estimation opérationnelle, pas une garantie.

## API

```text
GET /api/v1/analytics/overview/
GET /api/v1/analytics/events/<slug>/
GET /api/v1/analytics/events/<slug>/?days=7|30|90
```

Les mêmes frontières d'autorisation que l'interface web s'appliquent à l'API.

## Évolutions prévues

Lorsque Makolo aura davantage de volume, ce domaine pourra évoluer vers :

- snapshots journaliers immuables ;
- cohortes et rétention d'audience ;
- attribution partenaires/ambassadeurs ;
- funnel visite -> commande -> paiement ;
- comparaison entre éditions ;
- modèles de prévision plus robustes ;
- détection d'anomalies de scans/paiements ;
- recommandations actionnables avec historique d'explication.
