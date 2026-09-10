# Frontière d’opportunité — Makolo lab

Ce dossier est un **laboratoire isolé**. Il ne modifie aucun domaine, modèle, migration, selector, service, template ou comportement runtime de Makolo.

Objectif : appliquer la formulation mathématique « Frontière d’opportunité » à un univers **typé Makolo**, d’abord pour un `Profile` qui agit en son nom propre.

## Frontière du laboratoire

- `main` reste la base de vérité.
- Aucun import Django : la simulation est exécutable avec Python standard.
- Les types du laboratoire représentent des **projections de calcul**, jamais de nouveaux modèles canoniques.
- `Profile` agit ici comme personne. Toute action qui n’existe que grâce à une Permission/Mandate d’un Space est hors du contexte personnel.
- Les règles fortes (terminal, blocker, obligation, deadline) passent avant le Pareto.
- La Frontière compare uniquement des plans encore admissibles ; elle ne remplace ni Readiness, ni Access, ni Capacity, ni Authorization.
- Aucun score pondéré composite n’est utilisé.

## Fichiers

- `audit_makolo.md` — audit des briques existantes utilisées pour construire la simulation.
- `simulation.py` — modèle typé, scénarios riches, Pareto local/global, filtre d’acteur personnel, screening et évolution temporelle.
- `expected_output.json` — sortie déterministe de référence produite par `python frontiere_opportunite_lab/simulation.py`.

## Exécution

```bash
python frontiere_opportunite_lab/simulation.py
```

La simulation écrit aussi `frontiere_opportunite_lab/output.json` lorsqu’elle est exécutée depuis le dépôt. Ce fichier d’exécution peut rester non versionné ; `expected_output.json` sert d’oracle lisible.

## Ce que cette simulation cherche à valider

1. Une projection personnelle n’absorbe aucune action Space obtenue uniquement par autorité déléguée.
2. Une cible Makolo peut posséder plusieurs plans admissibles.
3. Les plans localement dominés sont éliminés avant comparaison inter-cibles.
4. Une cible accessible peut être absente de la Frontière globale.
5. Plusieurs cibles peuvent survivre simultanément sans score arbitraire.
6. Après une action réelle, le calcul repart du nouvel état courant et une cible auparavant dominée peut entrer en Frontière.
7. Un certificat de screening ne supprime une cible que lorsqu’une borne inférieure est dominée par un témoin réellement faisable.

Ce laboratoire n’est pas encore une intégration produit du « grand bouton Makolo ». Il sert à vérifier la traduction de la théorie sur les concepts actuels avant toute modification du runtime.
