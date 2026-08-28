# T32 — Opportunities & Requirement Engine — note d’implémentation

## Statut

T32 compose le domaine canonique `opportunities` avec la verticale `services` sans remplacer `Activity` ni dupliquer `Journey`, `Geography`, `Payment`, `Permission` ou les artifacts.

Principe conservé : **Event est une verticale. Activity est le noyau.** Une Opportunity externe reste distincte de l’Activity Services opérée par Makolo.

## Livré dans T32

- `Opportunity` et `OpportunityRevision` versionnées ; une révision publiée et ses zones/requirements sont immuables.
- provenance via `OpportunitySource` et contrôles append-only `OpportunitySourceCheck` ; une seule source primaire active.
- `OpportunityRequirement`, `OpportunityZone`, saves, propositions utilisateur et merge/déduplication conservant l’historique.
- sélecteurs publics dérivant `upcoming/open/closed` des dates de la révision courante.
- `ServiceJourneyContext` lie facultativement une Journey Services à une Opportunity et **pinnne une `OpportunityRevision` publiée**.
- `opportunity_policy=required` autorise la préparation du brouillon, mais bloque le démarrage opérationnel tant qu’aucune Opportunity/revision n’est attachée.
- `ServiceRequirementAssessment` matérialise les requirements de la révision pinnée ; statuts : `unassessed`, `satisfied`, `action_required`, `needs_review`, `not_applicable`, `not_eligible`.
- `ServiceRequirementEvidence` référence le `JourneyArtifact` canonique du même dossier ; aucun modèle de fichier parallèle.
- relation explicite `ServiceRequirementStepLink` entre une Assessment et une `JourneyStep` canonique.
- une nouvelle révision publiée est détectable sans modifier le dossier existant ; l’adoption N→N+1 est explicite, transactionnelle, auditée par `ServiceOpportunityRevisionAdoption` et émet `service.opportunity_revision.adopted`.
- les assessments/evidence/steps historiques de N restent présents après adoption de N+1.
- concurrence PostgreSQL couverte pour la création de versions et l’adoption concurrente sans régression du pin.
- seed bêta déterministe avec un emploi, une bourse, sources, zones, requirements, saves et une proposition utilisateur.

## Invariants vérifiés

1. Une Opportunity externe n’est pas une Activity Makolo.
2. Une Journey Services peut rester sans Opportunity lorsque sa policy le permet.
3. Une Journey travaille sur une révision explicite et publiée.
4. Publier N+1 ne réécrit jamais silencieusement un dossier pinné sur N.
5. Requirement décrit la condition externe ; Assessment décrit son état dans le dossier ; JourneyStep décrit l’action à réaliser.
6. Evidence réutilise `JourneyArtifact` et ne traverse jamais deux Journeys.
7. Un requirement financier peut produire une Step `payment`, mais T32 ne fabrique ni `Payment` ni `PaymentObligation`.
8. `not_eligible` est un fait d’assessment et ne force pas un `JourneyStatus=rejected`.

## Hors périmètre volontaire

- **T33** : `PaymentObligation`, `PaymentEvidence`, paiements provider/externe, `ServiceSubmission`, receipts et résultats tiers.
- **T34** : permissions finales `activity.services.*`, rôles Services finaux, selectors anti-IDOR finaux, notifications/automation et rappels.
- **T35** : UX complète participant/facilitateur/manager/staff.
- **T36** : analytics, performance, security review et release gate V1.

Cette note décrit l’implémentation réelle de T32 ; les spécifications canoniques restent `makolo-domain-blueprint.md`, `services-opportunities.md` et `services-implementation-plan.md`.
