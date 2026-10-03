# MPS Mobile — contrat PR2

PR2 empile le rendu mobile natif sur le noyau MPS restauré par PR1.

## Décision

MPS mobile ne transporte pas le manifest et le thème avec chaque artefact.

Le contrat local-first utilise trois projections keyed :

- `mps.artifact` : contexte autorisé de l’artefact + références ;
- `mps.template.version` : manifest publié immuable ;
- `mps.theme.version` : tokens publiés immuables.

Les deux définitions sont acquises seulement si elles manquent du store local. `Makolo Essential` est embarqué comme fallback natif, donc un artefact reste présentable même si sa définition personnalisée n’a pas encore été acquise.

## Rendu

Flutter interprète le même vocabulaire déclaratif MPS v1 que le Web, avec des widgets natifs. Il ne reçoit ni HTML, ni CSS, ni JavaScript, ni Dart dynamique.

Les composants inconnus sont ignorés localement ; une version de renderer minimale future force le fallback Essential au lieu de faire planter la surface.

## AccessCredential

Le QR reste hors de `ProjectionSnapshots` MPS. Le composant `QRCode` devient une action vers la projection sensible existante `personal.access.credential`, rechargée depuis l’owner Access.

Ainsi :

```text
Access = droit
AccessCredential = représentation sensible
MPS = présentation autorisée du droit
```

MPS ne persiste pas le secret du credential.

## Scope PR2

Le serveur expose les artefacts Activity pour `PUBLIC_PAGE`, `INVITATION`, `PROGRAM` et `BADGE`, plus `ACCESS_PASS`.

Le premier vertical slice UI réellement branché est Access Pass. Les surfaces Activity seront branchées au produit dans PR3.

Aucune migration Django ou Drift n’est ajoutée : le mobile réutilise `ProjectionSnapshots(profileId, projectionKind, resourceKey)`, `SyncSourceDefinition` et `SyncEngine`.
