# Tasks: Mobile Mature — En cours

- [x] T001 — Vérifier main/commits/PR/branches et collision audit.
- [x] T002 — Lire le contrat parent Batch 1 et les contrats UX/Golden pertinents.
- [x] T003 — Définir le modèle de présentation local non persistant Ongoing et son adapter depuis `StoredProjection`.
- [x] T004 — Remplacer la racine `ProjectionScreen` par la composition Ongoing Compact dans `mobile/lib/features/ongoing/**`.
- [x] T005 — Ajouter la profondeur N2 et la composition adaptive Wide avec `MakoloAdaptiveSplit`.
- [x] T006 — Préserver identité, ordre, sélection et retour sans créer de nouvel état métier.
- [x] T007 — Couvrir true empty, calm, offline/stale et refresh error sans masquer le contenu connu.
- [x] T008 — Couvrir waiting/blocker/parallel movements et capabilities/handoff Jour J.
- [ ] T009 — Ajouter tests ciblés et Goldens G06/G07 dans la surface de tests Ongoing autorisée.
- [x] T010 — Vérifier architecture anti-fixture/fake et absence de dépendance aux seams interdits.
- [ ] T011 — Lancer convergence Spec Kit et corriger les écarts démontrés.
- [ ] T012 — Réconcilier la branche avec main courant, vérifier CI et laisser la PR ouverte.

## Dependencies

T003 → T004/T005/T006  
T007/T008 peuvent suivre T003 mais partagent la surface Ongoing.  
T009 après T004–T008.  
T010/T011 après T009.  
T012 après CI et avant intégration finale.

Aucune tâche d’implémentation n’est déclarée parallèle : toutes écrivent dans la même lane Ongoing.
