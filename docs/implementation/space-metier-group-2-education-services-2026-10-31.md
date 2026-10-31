# Makolo / Métier Space — Groupe 2 : Programmes et Prestations

**Date** : 2026-10-31.
**PR unique** : #522 (`fix/discover-a-continuation-context-20261014`).
**Base main auditée au départ** : `d0f0ec421c94c255fa4c0acd3509938a70c6322f`.
**Contrats UX** : `docs/ux/Makolo_UX_Space_Metier_Programmes_Contrat_Consolide_2026-10-08.md` et `docs/ux/Makolo_UX_Space_Metier_Prestations_Contrat_Consolide_2026-10-08.md`.
**Périmètre** : groupe 2 de la composition N1 serveur + Web ; le lot complet N2/N3 et Flutter suivra après les groupes 3 et 4.

## Problèmes utilisateur fermés dans ce groupe

- Une organisation éducative doit reconnaître d'abord ses **Programmes** durables, puis leurs **Sessions** réellement prévues, et les **inscriptions/démarches** dont elle est habilitée à connaître l'état.
- Un prestataire doit distinguer **prestations proposées**, **demandes reçues**, **dossiers engagés** et **conditions évaluées**, sans se retrouver dans une liste générique de modèles backend.
- Une Journey PENDING_APPROVAL n'est pas automatiquement une JourneyRequest sur laquelle un opérateur peut décider ; les décisions viennent **exclusivement** du propriétaire JourneyRequest existant.
- Un dossier Services doit ouvrir sa profondeur opérateur seulement si le viewer y possède l'autorité et si un ServiceJourneyContext réel existe. La représentation N1 ne doit ni divulguer l'objectif privé, ni les documents, ni les notes, ni les personnes concernées.
- Ni la structure d'une Activity publiée ni une évaluation partielle ne doivent être réinterprétées comme un faux `ongoing`, `ready` ou `blocked`.

## Fichiers et livrables

### `organizations/space_work_composition.py`

La composition dérivée `business_world` couvre désormais quatre archétypes :
- `generic` : continuité / portfolio / spécialisé / historique (groupe 1 préservé).
- `community` : continuité collective / initiatives / spécialisé / passé (groupe 1 préservé).
- `education` : **portfolio Programmes d'abord**, Sessions & préparation, inscriptions & démarches, verticales réellement présentes, historique.
- `service_provider` : demandes, dossiers, prestations proposées, rendez-vous et réalisations, verticales réelles, historique.

Les groupes ne sont affichés que si une section déjà autorisée contient des lignes ou une continuation. Le contexte calme et l'ordre sont dérivés **sans tâche, état ou base de données nouvelle**. Les quatre autres archétypes restent inchangés jusqu'aux prochains groupes.

### `organizations/api/space_work_projection.py`

- Les Activities publiées des Programmes et Prestations peuvent signaler leur **prochaine Occurrence réelle** (session ou réalisation) ; l'Activity reste structurelle.
- Une inscription `Journey.REGISTRATION` reçoit une sélection read-only `links.selection` de l'endpoint Work existant ; aucun faux droit de décision n'est produit.
- Lorsqu'une vraie `JourneyRequest` pending existe et que sa Journey se trouve dans une section d'inscription autorisée, la projection fournit `links.request_detail` vers `organizations_api:workspace-request-detail` et `open_request`. L'endpoint propriétaire revérifie viewer, Space, scope d'Activity, responsabilité et décision au moment de l'appel. Le lien n'autorise pas à lui seul une décision.
- Les démarches `REGISTRATION` et `SERVICE` ont respectivement les étiquettes de présentation « Inscription » et « Dossier de prestation ». Aucun bénéficiaire, credential, message ou pièce privé n'est inclus.
- Un dossier Service avec scope opérateur et contexte valide conserve son lien `services:operator-case` et peut exposer `service_outcome` actuel **provenant de ServiceJourneyContext**.
- Pour les dossiers opérateur effectivement visibles dans les pages N1, une agrégation unique des **ServiceRequirementAssessment réels** indique `total/satisfied/awaiting/unsatisfied` ; elle n'inclut ni intitulés de pièces, ni notes, ni Evidence ni verdict synthétique `ready`. Aucun compteur n'est inventé quand le propriétaire ne possède pas d'assessment.
- Les permissions/ Mandates ne sont pas transférés par la composition, et les sections existantes restent disponibles pour les consommateurs historiques.

### Web

- `organizations/space_work_web.py` : un dossier Services ouvre la profondeur `services:operator-case` uniquement lorsque la projection donne `open_service_case` et `links.detail`. Pas de fallback vers la Console Activity pour un opérateur Services qui n'y a pas accès.
- `templates/organizations/space/work.html` : rendu des libellés humains, prochaines sessions/réalisations, synthèse des conditions réellement évaluées et action « Ouvrir le dossier » lorsque disponible.
- Les groupes de lecture et questions restent fournis par le serveur ; Web ne trie pas ou ne réinterprète pas les états métier.

## Tests ciblés ajoutés

`organizations/test_space_work_group2.py` :
1. Programmes → Session → Inscription avec absence de divulgation du bénéficiaire et sélection read-only.
2. Décision d'inscription : lien et capacité seulement en présence d'une vraie JourneyRequest ; accès refusé au viewer étranger.
3. Prestations : demandes et dossiers séparés, contexte et résultat owner, lien opérateur et confidentialité.
4. ServiceRequirementAssessment réel : agrégation correcte, aucun détail ou note privés, pas de faux `ready`.
5. Web Programmes : ordre, prochaine session et sections réellement présentes.
6. Web Prestations : lien vers le vrai dossier Services et aucune divulgation privée.
7. Non-régression de l'archétype Créatif qui ne reçoit pas prématurément la composition du groupe 2.

Vérification Django locale par l'utilisateur :

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_space_work_group2 organizations.test_zs3_space_work_api organizations.test_ws3_space_work_web
```

**Exécution** : les changements et tests sont poussés sur #522 ; aucune suite Django/Flutter et aucune CI n'ont été exécutées dans cette session distante. Ne pas déclarer `tests green` sans vérification locale. Aucun merge.

## Invariants et limites

- Pas de nouveau modèle Programme, Session, Prestation, dossier, Requirements, Readiness ou WorkItem.
- Aucune mutation, transition, permission ou état sensible créée dans Presentation.
- `JourneyRequest` possède la décision, `Journey` la démarche et `ServiceRequirementAssessment` l'état de l'évaluation.
- Owner Web/serveur revalide toujours l'autorité au clic ; un lien de lecture n'accorde pas d'autorité.
- Pas d'historique ou de métrique financière calculée à partir d'états partiels ; aucune donnée de bénéficiaire ou Evidence projetée.
- Les clients Flutter existants continuent à lire les sections historiques; la composition N1 native et les profondeurs complètes sont planifiées après le groupe 4.

## Suite

**Groupe 3 : Commerce + Transport**, même PR #522, composition owner-backed et distinction structure/offre/commande/départ/opérations avant l'intégration native. Relire le HEAD et faire un collision audit, car #522 accueille aussi des travaux concurrents Now/Nous/Flutter.
