# Blocage de convergence — PR #505

Date: 2026-10-09

## Statut

La PR #505 n’a pas été intégrée dans le premier checkpoint de convergence.

## Motif

La règle de garde-fou requiert que la PR #505 soit intégrée seulement si son comportement est validé. Les surfaces concernées sont les vues et projections Now, ainsi que les composants Flutter associés. À ce stade, la validation de la convergence locale n’a pas encore produit de preuve suffisante pour l’intégrer sans risque dans le bloc de fusion principal.

## Isolation

La PR #505 reste isolée du branch de convergence principal et ne fait pas partie du merge validé sur la branche de travail `integration/mature-convergence-2026-10-09`.

## Prochaine étape recommandée

- valider les suites ciblées Now / mobile / contracts / golden tests ;
- vérifier les dépendances réelles avec les PR de navigation et runtime ;
- réintroduire la PR #505 dans un groupe de convergence séparé uniquement après validation explicite.
