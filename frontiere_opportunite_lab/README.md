# Frontière d’opportunité — Makolo personal lab

Ce dossier est un **laboratoire de recherche isolé à la racine du dépôt**. Il applique la théorie de la Frontière d’opportunité à un univers typé Makolo sans modifier le runtime de Makolo.

Base auditée : `main` au commit `a840455af8cd3cfc185404b4dc8c28a53bbb9eb6`.

## Périmètre

Le laboratoire traite uniquement :

```text
actor = Profile
represented_space = None
```

Le Profile agit donc **comme personne et en son nom propre**. Une Permission, un Mandate ou une responsabilité portant sur un Space ne fait jamais entrer une action Space dans le pool personnel. Le cas `acting_as_space` est volontairement hors de ce laboratoire.

## Ce qui est versionné ici

- `audit_makolo.md` — audit des contrats Makolo effectivement utilisés par la simulation ;
- `engine.py` — moteur générique de Pareto local/global, identité canonique, gate sémantique et safe screening ;
- `simulation.py` — univers Makolo synthétique riche et évolution de l’état courant ;
- `expected_output.json` — oracle compact des transitions importantes ;
- `results.md` — interprétation de l’exécution de référence.

Aucun import Django n’est nécessaire. Les deux fichiers Python utilisent uniquement la bibliothèque standard.

## Exécution

Depuis la racine du dépôt :

```bash
python frontiere_opportunite_lab/simulation.py
```

Le script imprime la simulation complète en JSON et écrit aussi :

```text
frontiere_opportunite_lab/output.json
```

`output.json` est une sortie d’exécution ; `expected_output.json` est l’oracle compact à conserver en version.

## Règles de traduction

Les classes du laboratoire sont des **projections de calcul**, pas de nouveaux modèles métier. Elles ne créent ni `OpportunityFrontier`, ni `Task`, ni copie de Readiness, Access, Capacity, Permission ou Journey.

La séquence est :

```text
faits simulés conformes aux contrats Makolo audités
    -> filtre actor=Profile / represented_space=None
    -> déduplication par identité canonique exacte
    -> règles fortes R2 (priority, actionability, deadline-state)
    -> plans encore admissibles
    -> Pareto local par cible
    -> safe screening certifié sur l’ensemble fini
    -> Pareto global étiqueté par cible
```

La Frontière **ne remplace pas** les règles `P0..P4`. Un blocker, une annulation, une perte d’Access ou une échéance canonique ne peuvent pas être compensés par un score de préférence.

## Performance vectorielle du laboratoire

Tous les axes sont des coûts à minimiser :

```text
deadline_minutes
user_effort_min
cash_cdf
travel_min
elapsed_min
interactions
p0_after
p1_after
p2_after
p3_after
```

Les quatre dernières composantes décrivent la charge d’action restante après exécution du plan. Cela empêche le Pareto de devenir simplement « choisir l’action la moins chère » alors que deux actions changent différemment l’état personnel.

Aucune somme pondérée n’est utilisée.

## Données

Les **lois** du scénario sont dérivées des contrats audités du dépôt : Readiness, R2 Contextual Actions, Prepared Start, Access, Capacity, M6, Dossier, Conversations et Action Network.

Les **valeurs du scénario** — montants, durées, horaires, distances, capacité disponible — sont synthétiques et servent uniquement à tester le comportement de la théorie. Elles ne sont pas présentées comme des données de production Makolo.

## Critères de conformité

L’exécution contient des assertions qui échouent si notamment :

- une action Space entre dans la Frontière personnelle ;
- un doublon Dossier/Journey à identité canonique exacte est compté deux fois ;
- un hold Capacity expiré reste considéré sécurisé ;
- une révocation Access ne déclenche pas le blocker/chemin de réparation attendu ;
- une Occurrence annulée laisse passer une action inférieure ;
- une cible réellement sur la Frontière est éliminée par le safe screening ;
- Discover promeut une occurrence annulée ou une possibilité sans capacité ;
- le scénario final ne conserve pas plusieurs compromis Pareto lorsqu’ils sont réellement non dominés.

Ce laboratoire est une étape de validation scientifique/application avant toute intégration du grand bouton Makolo dans le runtime.