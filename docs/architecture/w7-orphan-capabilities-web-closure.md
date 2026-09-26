# W7 — Fermeture web des capacités orphelines Z15

> **Statut : chantier W de composition web/desktop.** W7 consomme les contrats serveur Z15 sans recréer leurs permissions ni leurs vérités métier. Platform reste hors de ce chantier.

## Objectif

Z15 a classé et exposé les capacités qui existaient côté serveur mais restaient totalement ou partiellement orphelines. W7 leur donne un chemin Mature depuis la Console Espace, sous le Mandate/Permission déjà décidé par le serveur.

La règle est :

```text
Z15 owner contract
→ SpaceConsoleContext
→ destination Mature
→ outil propriétaire existant
```

W7 ne crée aucun modèle ni migration.

## Capacités reconnectées

La navigation Espace consomme désormais directement la projection `build_space_workspace()` de Z15 pour décider si les modules suivants sont visibles :

- Partners ;
- Growth / acquisition ;
- Loyalty ;
- Recognition Espace ;
- Trust Espace ;
- Funding.

Les modules déjà présents avant Z15 restent sur leurs chemins canoniques : CRM/Audiences/Promotions, Analytics, Automation, Control/Scanner et Operations. W7 ferme aussi leur reachability secondaire : Analytics mène vers les analyses Growth avancées lorsqu'elles sont autorisées, Automatisations mène vers les scénarios CRM owner-backed, et Contrôle d'accès expose les outils Scanner compatibility utiles (historique, portes, agents) sans recréer Access.

## Composition

- **Commercial** : Financements rejoint Tarifs, Commandes, Paiements et Promotions.
- **Relations** : Partenaires, Fidélité, Reconnaissance et Confiance.
- **Pilotage** : Acquisition rejoint Analyses et Automatisations ; les détails avancés restent accessibles depuis ces surfaces canoniques plutôt que par une nouvelle entrée primaire.

La présence d'un module ne vient pas d'un rôle frontend ni d'un simple Membership. Elle vient du read-model Z15, lui-même dérivé des Mandates/Permissions directs.

## Hubs Mature

Partners, Growth, Loyalty, Recognition et Trust reçoivent une entrée Console Espace légère. Le hub garde le contexte de l'Espace et mène ensuite vers l'outil owner-backed déjà existant ; W7 ne crée pas une seconde implémentation métier.

Funding reçoit une vue Espace dédiée qui liste uniquement les financements réellement gérables. La création conserve le contexte Espace en présélectionnant l'Espace demandé lorsque le formulaire autorise effectivement cet Espace.

## Frontières

- Platform n'est pas exposé dans la Console Espace.
- TeamMembership n'accorde aucune capacité.
- Platform authority n'accorde aucune capacité Espace.
- Access reste propriétaire du droit ; Scanner reste un outil d'observation/validation.
- Loyalty et Recognition restent distincts.
- Funding continue d'utiliser Activity et PaymentObligation.
- Analytics n'est pas dupliqué.

## Legacy

Les anciens workspaces Partners/Growth/Loyalty/Recognition/Trust restent des destinations secondaires owner-backed. W7 les rend atteignables depuis la Console Espace au lieu de les dupliquer ou de supprimer brutalement leurs URLs.

Les anciennes racines Network/Event/Ticket/Scanner restent compatibility selon Z15 ; W7 ne les remet pas dans la navigation primaire. Les outils Scanner encore nécessaires sont atteignables depuis « Contrôle d'accès », tandis que les Event façades restent des adaptateurs historiques.

## Tests ciblés

`organizations/test_w7_orphan_reachability.py` couvre :

- visibilité des modules Z15 pour un Space Owner ;
- reachability web des six nouvelles entrées Mature ;
- absence d'accès par TeamMembership seul ;
- absence d'héritage Platform → Space ;
- conservation du contexte Espace pour la création Funding ;
- reachability des Analytics Growth avancés depuis Analyses ;
- reachability des scénarios CRM depuis Automatisations ;
- reachability des outils Scanner compatibility depuis Contrôle d'accès.

## Platform

La future expérience Platform reste un chantier séparé : une porte unique puis un univers Platform. W7 n'ajoute aucun lien dispersé vers Operations globales, Trust staff, gouvernance ou runtime interne.
