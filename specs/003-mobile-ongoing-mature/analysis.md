# Spec Kit Analysis — Ongoing Mature

## Constitution

Conforme aux principes I, II, IV, V, VI, VII, VIII, IX et X :
- runtime actuel privilégié ;
- backend/domain owners inchangés ;
- aucune nouvelle vérité persistante ;
- local-first honnête ;
- tests ciblés puis CI ;
- lane dédiée et collision audit ;
- personnalité En cours préservée ;
- workflow Spec Kit suivi.

## Contract consistency

La spec parent Batch 1 reste read-only. Cette lane ne modifie aucun fichier commun ou seam integrator-owned.

## Runtime consistency

Le runtime vérifié expose actuellement :
`watchOngoing() → personal.ongoing`, puis `ProjectionScreen`. Le changement proposé remplace uniquement la projection générique par un adapter + présentation Ongoing dans la lane feature.

## Data consistency

La shape serveur actuelle fournit les dimensions nécessaires : source, title, state, ready, actor_interventions, continuation, blocker, next, occurrence, timing, place, capabilities et links. Aucun champ métier parallèle n’est nécessaire.

## UX consistency

En cours reste « continuité + état » : plusieurs Continuités, calme avec contenu, vrai empty distinct, dimensions SETTLED/MY_SIDE/ELSEWHERE/NEXT non transformées en quatre sections obligatoires, pas de progression artificielle.

## Risk / gaps

Le refresh boundary actuel sait déclencher un refresh mais n’expose pas directement une erreur de refresh. La lane peut néanmoins préserver le contenu lorsqu’un stream émet une erreur après une valeur connue ; la matérialisation d’un statut de synchronisation plus riche reste intégrator-owned et hors scope.

Le contrat utilisateur demande une validation contre de vraies réponses API ; cette validation finale dépend du Mobile Mature Demo Universe et sera une gate d’intégration, pas une fixture runtime.

## Decision

Proceed without Clarify. Aucun point identifié ne change le scope, l’autorité, la confidentialité, les données ou la distinction Continuity / Journey / Now / Jour J.
