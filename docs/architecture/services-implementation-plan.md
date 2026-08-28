# Makolo Services — Plan d'implémentation

> **Base de planification :** `main` au commit `9a3884a8635fbf3377c34ee8871b88d36f0c8b79` (Task 30). Ce document dérive la cible canonique décrite dans [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md) et [`services-opportunities.md`](services-opportunities.md). Il décrit l'ordre des PR, leurs dépendances et leurs gates ; il ne remplace pas les invariants de ces documents.

## 1. Principe de livraison

Makolo Services est une seule cible produit complète. Les tâches ci-dessous sont des unités techniques mergeables et testables, pas des mini-produits ni un petit MVP.

Règles :

- branche dédiée par tâche ;
- changements additifs et réversibles autant que possible ;
- services métier transactionnels avant UI ;
- permissions serveur avant exposition des données ;
- migrations non destructrices ;
- Domain Events émis uniquement depuis les services propriétaires ;
- tests ciblés puis suite pertinente ;
- `makemigrations --check --dry-run` vert ;
- PostgreSQL et E2E verts avant merge ;
- aucun merge avec CI rouge ;
- vérifier `main` après chaque squash merge.

## 2. État de départ réel

Le noyau déjà présent fournit notamment :

- Activity / Occurrence ;
- Journey / JourneyRequest / JourneyTransition ;
- Access / Credential / Use ;
- Capacity ;
- Commerce / Offer / CommerceOrder ;
- Payment provider sandbox et manual ;
- Domain Events / Notifications / Automation ;
- Role / Permission / Mandate Activity-scoped ;
- Space / Team ;
- Discovery et expérience participant canonical-first ;
- Events et Transport comme verticales composées.

Le paiement courant impose encore un `TicketOrder` ou `CommerceOrder`. Makolo Services exige donc la généralisation vers `PaymentObligation` sans casser les bridges Events/Commerce existants.

## 3. Séquence de tâches

### Task 31 — Journey long-running orchestration

**But :** donner au noyau Journey les primitives de parcours long dont Services dépend.

Contenu :

- `WorkflowKind.SERVICE` ;
- `JourneyStatus.IN_PROGRESS` + `started_at` ;
- transitions Services dans `journeys.services` ;
- Domain Event `journey.in_progress` ;
- `JourneyStep` ;
- `JourneyStepDependency` ;
- `JourneyBlocker` ;
- `JourneyAssignment` ;
- `JourneyStepAssignment` ;
- services transactionnels pour transitions, recalcul des dépendances et blockers ;
- selectors par bénéficiaire/Activity/assignment sans encore ajouter les permissions Services finales ;
- admin minimal pour diagnostic ;
- migrations et tests de concurrence.

**Invariants à tester :**

- aucun changement libre de statut hors service ;
- pas de cycle de dépendance ;
- une étape avec blocker actif ne peut pas être completed ;
- résolution du dernier blocker recalcule correctement l'étape ;
- un seul lead primaire actif ;
- aucune régression sur les workflows Journey existants.

**Dépend de :** aucun nouveau domaine.

---

### Task 32 — Journey case collaboration and private artifacts

**But :** rendre un dossier réellement exploitable par un bénéficiaire et des facilitateurs.

Contenu :

- `JourneyArtifact` privé et versionné ;
- stockage via abstraction Django ;
- `JourneyArtifactReview` ;
- `JourneyNote` ;
- téléchargement sécurisé par endpoint autorisé ;
- hash/MIME/taille ;
- politiques `normal/sensitive/restricted` ;
- services de versioning/review/note ;
- audit des changements ;
- Domain Events artifact/review.

**Gates sécurité :**

- UUID connu sans permission = accès refusé ;
- aucune URL publique permanente ;
- notes internes jamais exposées au bénéficiaire ;
- documents restreints exigent une permission dédiée une fois Task 37 en place ; pendant Task 32, selectors deny-by-default pour les opérateurs non explicitement autorisés.

**Dépend de :** Task 31.

---

### Task 33 — Services vertical core

**But :** matérialiser Services comme verticale composée sans dupliquer le noyau.

Contenu :

- app `services` ;
- `ServiceDetails` OneToOne Activity ;
- `ServicePlanTemplate` versionné ;
- TemplateStep / TemplateStepDependency ;
- `ServiceIntakeQuestion` / `ServiceIntakeAnswer` ;
- matérialisation transactionnelle d'un template dans une Journey ;
- `ServiceJourneyContext` initial sans Opportunity obligatoire ;
- completion policies contrôlées ;
- parcours sans Opportunity, ex. accompagnement CV ;
- services d'intake, confirmation, démarrage et fulfillment ;
- vocabulary/presenter Services.

**Invariants :**

- une Activity Services reste une Activity à opérateur canonique ;
- template publié immuable ;
- un nouveau template n'altère pas les Journey existantes ;
- pas de prix, permission, Payment ou Profil dupliqué dans ServiceDetails.

**Dépend de :** Tasks 31–32.

---

### Task 34 — Opportunities canonical domain

**But :** fournir un domaine Opportunity mature avec provenance et historique.

Contenu :

- app `opportunities` ;
- `Opportunity` ;
- `OpportunityRevision` immuable ;
- `OpportunityRequirement` ;
- `OpportunityZone` ;
- `OpportunitySource` ;
- `OpportunitySourceCheck` ;
- `OpportunitySave` ;
- `OpportunitySubmission` ;
- merge/dedup contract ;
- publication/withdraw/archive ;
- calcul `upcoming/open/closed` ;
- selectors publics et staff ;
- Domain Events Opportunity.

**Invariants :**

- une Opportunity externe n'est jamais transformée en Activity ;
- une révision publiée ne se réécrit pas ;
- une fermeture n'efface jamais l'historique ;
- changement de source = check + revue + éventuelle nouvelle révision ;
- merge garde la traçabilité.

**Dépend de :** Geography existante ; Domain Events existants.

---

### Task 35 — Service journey ↔ Opportunity and requirement engine

**But :** transformer une Opportunity en parcours actionnable sans dupliquer Journey.

Contenu :

- enrichissement `ServiceJourneyContext` : Opportunity + OpportunityRevision pinnée ;
- `ServiceRequirementAssessment` ;
- `ServiceRequirementEvidence` ;
- création/liaison d'étapes à partir des requirements ;
- recalcul de readiness ;
- changement de revision détecté sans modification silencieuse ;
- adoption explicite d'une nouvelle revision ;
- alertes de changements critiques ;
- vues/selectors de progression des requirements.

**Invariants :**

- chaque dossier sait exactement sur quelle revision il travaille ;
- un nouveau requirement ne modifie pas automatiquement un dossier historique ;
- preuve et assessment restent auditables ;
- `not_eligible` n'est pas confondu avec `Journey.rejected` sauf décision métier explicite via service.

**Dépend de :** Tasks 33–34.

---

### Task 36 — Payment obligations and external payment evidence

**But :** généraliser Payments pour couvrir Commerce et les obligations financières de Journey/Opportunity.

Contenu :

- `PaymentObligation` dans `payments` ;
- `PaymentEvidence` ;
- lien Payment -> PaymentObligation pour nouvelles transactions ;
- bridge CommerceOrder -> PaymentObligation ;
- conservation TicketOrder/CommerceOrder legacy pendant migration ;
- plusieurs tentatives Payment par obligation ;
- unicité d'un succès actif satisfaisant l'obligation ;
- `processing_mode = makolo_provider | external` ;
- payeur et bénéficiaire économique explicitement distincts ;
- sandbox provider pour parcours Services ;
- vérification de preuve externe sans faux Payment ;
- refunds sur transactions réellement traitées ;
- événements `payment.obligation.*` et `payment.evidence.*` ;
- synchronisation JourneyStep/Access/Commerce via services, pas signaux opaques.

**Migration :** expand -> backfill des CommerceOrders nécessaires -> double compatibilité -> cutover progressif. Aucun TicketOrder ou Payment historique supprimé dans cette tâche.

**Invariants :**

- un Payment sans transaction provider réelle n'est jamais fabriqué ;
- une obligation externe vérifiée peut être satisfied sans Payment ;
- un Payment réussi n'implique pas que Makolo est payee ;
- paiement intermédiaire ne change pas globalement Journey à `pending_payment` ;
- aucun double succès concurrent.

**Dépend de :** Tasks 31, 33, 35 + Commerce/Payments existants.

---

### Task 37 — Services authorization and privacy boundaries

**But :** fixer les permissions serveur définitives avant les consoles complètes.

Contenu :

Permissions Activity :

- `activity.services.configure` ;
- `activity.services.cases.view_all` ;
- `activity.services.cases.view_assigned` ;
- `activity.services.cases.manage` ;
- `activity.services.assignments.manage` ;
- `activity.services.steps.manage` ;
- `activity.services.blockers.manage` ;
- `activity.services.artifacts.view` ;
- `activity.services.artifacts.manage` ;
- `activity.services.artifacts.restricted_view` ;
- `activity.services.reviews.manage` ;
- `activity.services.notes.internal` ;
- `activity.services.outcomes.manage` ;
- `activity.services.payment_evidence.verify`.

Rôles Activity : Service Manager, Service Facilitator, Service Reviewer.

Permissions plateforme Opportunity : manage, review_submissions, sources.verify, merge.

Selectors/services : bénéficiaire ; manager view_all ; facilitateur/reviewer `Mandate + permission + active assignment` ; restrictions artifact ; finance séparée.

**Tests négatifs obligatoires :**

- membre Space sans permission ;
- TeamMembership sans Mandate ;
- Assignment sans Mandate ;
- Mandate sans Assignment pour `view_assigned` ;
- facilitateur d'une autre Activity ;
- reviewer sans restricted_view ;
- non-staff sur curation Opportunity.

**Dépend de :** Tasks 31–36.

---

### Task 38 — Service submission and external outcomes

**But :** fermer le parcours jusqu'au tiers et distinguer fulfillment Makolo du résultat externe.

Contenu :

- `ServiceSubmission` multi-attempt ;
- modes external_web/email/in_person/makolo_integrated/other ;
- receipt artifact ;
- acknowledgement/failure/withdrawal ;
- `ServiceOutcomeEvent` append-only ;
- projection `current_outcome` ;
- completion policies vérifiant étapes, blockers critiques, obligations requises et soumissions ;
- timeline dossier ;
- Domain Events submission/outcome.

**Invariant majeur :** `Journey.fulfilled + outcome.unsuccessful` est valide.

**Dépend de :** Tasks 33, 35–37.

---

### Task 39 — Services automation, deadlines and attention

**But :** rendre l'orchestration temporelle opérationnelle.

Contenu :

- consumers Notifications ;
- règles Automation whitelistées ;
- échéances Opportunity/Step/Blocker/PaymentObligation/Journey/Occurrence ;
- J-30/J-14/J-7/J-3/J-1/J/overdue configurables ;
- déduplication ;
- aucune notification pour condition déjà satisfaite ;
- alertes revision Opportunity, withdrawn, source changed ;
- surfaces d'attention participant/facilitateur/manager ;
- reprise après échec idempotente.

**Dépend de :** Tasks 31–38 + Domain Events/Automation existants.

---

### Task 40 — Participant Services experience

**But :** livrer le parcours participant complet avec vocabulaire naturel.

Surfaces :

- découverte Opportunities ;
- filtres et détail ;
- sources/dates/requirements/géographie ;
- saves ;
- OpportunitySubmission ;
- CTA demande d'aide ;
- intake ;
- dashboard dossier ;
- prochaines actions ;
- requirements ;
- blockers ;
- artifacts/reviews ;
- obligations de paiement sandbox / preuves externes ;
- rendez-vous ;
- notes visibles ;
- timeline ;
- submission/outcome ;
- service sans Opportunity.

Mobile et accessibilité inclus dans les gates.

**Dépend de :** Tasks 33–39.

---

### Task 41 — Facilitator and Space Services consoles

**But :** rendre l'opération humaine complète.

Facilitateur : mes dossiers, attention, plan, dependencies, requirements, reviews, blockers, rendez-vous, paiements dans sa portée, notes, soumissions, outcomes.

Manager/Espace : Activity Services, templates, intake, Mandates, affectations, charge, dossiers à risque, supervision.

Aucune console ne contourne les selectors/permissions de Task 37.

**Dépend de :** Tasks 33–40.

---

### Task 42 — Makolo Opportunity curation console

**But :** fournir au staff le workflow complet de curation.

Contenu :

- inbox OpportunitySubmission ;
- création/revision ;
- sources/checks ;
- verification ;
- publication/withdraw/archive ;
- merge/dedup ;
- changements avec Journey actives ;
- audit.

**Dépend de :** Tasks 34–39.

---

### Task 43 — Services analytics and operational reporting

**But :** mesurer l'exécution sans confondre succès Makolo et décision du tiers.

Mesures :

- Journey volume/start/fulfillment ;
- temps global et par étape ;
- blockers ;
- échéances manquées ;
- Opportunity -> Journey -> Submission -> Outcome ;
- charge facilitateurs ;
- reviews ;
- obligations financières ;
- provider vs paiement externe ;
- devises séparées ;
- privacy-safe aggregates.

**Dépend de :** Tasks 31–42 + analytics canonique.

---

### Task 44 — Services hardening, beta seed and release gate

**But :** déclarer Makolo Services V1 complète uniquement après validation transversale.

Contenu :

- seed réaliste emploi ;
- seed réaliste bourse ;
- service CV sans Opportunity ;
- Opportunities changed/withdrawn ;
- sandbox payments ;
- preuves externes ;
- rôles participant/facilitator/reviewer/manager/staff ;
- performance/query-count ;
- concurrency ;
- sécurité artifacts ;
- migrations PostgreSQL ;
- E2E desktop/mobile ;
- documentation opérations ;
- smoke tests environnement de test.

## 4. Scénarios de release obligatoires

### Emploi complet

Opportunity -> save -> Journey -> intake -> assignment -> requirements -> CV versionné -> review -> blockers -> paiement éventuel -> submission -> interview -> outcome.

### Bourse complète

Opportunity -> revision/source -> requirements -> artifacts -> frais sandbox ou external evidence -> verification -> submission -> acknowledgement -> outcome.

### Service sans Opportunity

Activity CV -> Journey -> plan -> facilitator -> artifact versions -> review -> fulfillment.

### Opportunity utilisateur

URL proposée -> staff review -> accepted/duplicate -> Opportunity canonique -> Journey.

### Changement d'Opportunity

Journey pinnée sur revision N -> revision N+1 publiée -> notification -> comparaison -> adoption explicite ou maintien de N.

### Paiement commercial

Offer -> CommerceOrder -> PaymentObligation -> sandbox Payment -> confirmation -> Access.

### Paiement Opportunity via Makolo

Financial requirement -> Step -> PaymentObligation -> sandbox -> Step ready/completed selon contrat.

### Paiement hors Makolo

Financial requirement -> external obligation -> receipt artifact -> evidence verification -> satisfied, sans Payment provider.

### Autorisation

Participant, facilitateur assigné, facilitateur non assigné, reviewer, Service Manager, autre membre Space et staff voient exactement ce qui leur est permis.

### Artifacts

Aucun accès à un document par URL/UUID connu sans autorisation ; restricted respecte la permission spécifique.

### Concurrence

- double Payment success ;
- double lead assignment ;
- transitions Step concurrentes ;
- review concurrente ;
- adoption concurrente de revision ;
- source checks concurrents.

Aucun état incohérent n'est accepté.

## 5. Gates techniques par PR

Chaque PR métier doit au minimum exécuter :

1. tests ciblés du domaine modifié ;
2. tests des frontières directement dépendantes ;
3. `python manage.py makemigrations --check --dry-run` ;
4. migrations depuis une DB de référence compatible ;
5. Django tests pertinents SQLite et PostgreSQL lorsque le pipeline le couvre ;
6. E2E affectés ;
7. contrôles permission négatifs ;
8. query-count/performance pour les listes importantes ;
9. vérification des Domain Events/idempotence si la PR en émet ;
10. CI globale requise avant merge.

Les migrations destructrices ne sont pas admises sans stratégie explicite de backup/rollback. Les bridges historiques ne sont supprimés qu'après cutover prouvé.

## 6. Gates de release V1

Makolo Services n'est déclarée prête que lorsque :

- Tasks 31–44 sont fusionnées ;
- `main` est vert après le dernier merge ;
- tous les scénarios de release ci-dessus sont E2E verts ;
- aucune migration en attente ;
- beta seed complet vert sur PostgreSQL ;
- aucune erreur serveur 500 dans les smoke tests ;
- visitor, participant, facilitator, reviewer, Space manager et staff sont couverts ;
- Journey/Access/Capacity/Commerce/Payment/Events/Transport restent sans régression ;
- les fichiers sensibles sont privés ;
- les permissions serveur sont vérifiées ;
- le provider sandbox couvre les flux financiers nécessaires ;
- IA, M-PESA réel et abonnement ne sont pas requis pour l'exploitabilité de la V1.

## 7. Ce qui reste volontairement après V1

- IA d'analyse, rédaction, matching ou recommandation ;
- M-PESA réel et autres providers réels ;
- settlement/payout spécifique provider ;
- abonnement/feature gating ;
- publication autonome par des Espaces externes ;
- import/monitoring automatisé massif de sources.

Ces capacités sont différées parce qu'elles dépendent d'intégrations ou de décisions futures, pas parce que les parcours fonctionnels de Makolo Services restent incomplets.
