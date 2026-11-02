# Registre des anomalies — Abonnement et facturation mobile (02-11-2026)

Sources : dix captures des vues Abonnement, Changer de formule, Mes options, Facturation et Historique. Les offres DEMO sont fictives. Un affichage ne prouve pas une erreur financière réelle.

| ID | Priorité | Statut | Constat et critère de sortie |
|---|---|---|---|
| S01 | P0 | À vérifier | Après Plus → Max, obligations 7 et 18 USD visibles : vérifier périodes, prorata éventuel, doublons, idempotence et politique contractuelle du serveur. |
| S02 | P0 | À vérifier | Obligation Max de « À régler » à « Réglée » : corréler statut, règlement et événement sandbox, sans inférer un paiement réel. |
| S03 | P1 | UX avérée | « Subscription demo.profile.max v1 » : remplacer par libellé métier provenant du serveur, conserver référence technique dans détail si utile. |
| S04 | P1 | Contenu ambigu | DEMO Plus et Max ont les mêmes bénéfices affichés : confirmer différences réelles dans catalogue, ne pas inventer de valeur commerciale. |
| S05 | P1 | UX avérée | Changement de formule sans comparaison synthétique : présenter écarts de prix, capacités, exigences et activation selon la preview serveur. |
| S06 | P1 | UX avérée | Changement en cours sans prochaine étape explicite : afficher statut exact et action permise par le serveur. |
| S07 | P1 | UX avérée | Historique trop sommaire : rendre visibles ancienne/nouvelle formule, date et conséquences financières accessibles. |
| S08 | P2 | Corrigé dans #522 | Double bouton Retour sur sous-pages : suppression du retour dans le contenu, conservant la flèche AppBar (commit 102efd3342389bd7c92e5cd7354e04373fda658f). |
| S09 | P2 | UX avérée | Grand espace vide initial et titres redondants : compacter sans compromettre accessibilité. |
| S10 | P2 | UX avérée | Cartes facture mal hiérarchisées et lignes cassées : montant, état, échéance et intitulé distincts ; test petits écrans. |
| S11 | P2 | UX avérée | Vocabulaire « Changement de BASE » et « sandbox » : formulations métier, mais signalement clair des données fictives. |
| S12 | P2 | UX avérée | Formule courante : deux mentions équivalentes « Déjà inclus » : éliminer répétition. |
| S13 | P1 | À vérifier | Transition ouverte : blocage d'une nouvelle demande, annulation et idempotence serveur, reprise sur erreur et concurrence. |
| S14 | P1 | À vérifier | Cohérence inter-écrans après transition : revalidation serveur, absence de statut optimiste non confirmé. |
| S15 | P1 | À vérifier | Parcours Space distinct : Mandates view/manage/finance, séparation Profile/Space, IDOR, changement d'acteur. |
| S16 | P1 | À terminer | Lot 3 Entitlements : custom_roles propriétaire et tests réels encore ouverts ; pas de fermeture sans validation. |

## Ordre d'exécution

1. Contrôler opérations Subscription et Payment pour les deux montants DEMO et transitions concurrentes.
2. Terminer les frontières Entitlements lot 3 et tests métier.
3. Corriger projections métier et présentation des formules, obligations et historique.
4. Vérifier UX mobile petit écran et droits Profile/Space.

Les tests et CI ne sont pas attestés par cet inventaire. Ne pas fusionner sur CI rouge.
