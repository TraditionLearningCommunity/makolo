# Interpréteur Makolo — Acteur 3

**Statut : runtime Actor 3 — contrat `ObservationMaterial v2 → InterpretedMaterial v1`**  
**Audit initial : 22 septembre 2026**  
**Base de départ auditée : `main@50f47015df7f19dea274bee15e2cee1bd82a3807`**

## Synthèse

**RETENU**

> L’Interpréteur Makolo est l’acteur interne responsable de transformer les matériaux réellement observés en descriptions structurées, candidates et traçables de ce qu’ils expriment — entités, faits, relations, contraintes et valeurs — sans décider encore de l’identité canonique des réalités ni les transformer en vérités métier.

```text
Prospecteur → ObservationTarget
Observateur → ObservationMaterial v2
Interpréteur → InterpretedMaterial v1
Résolveur → réalités rapprochées/réconciliées
```

Invariant :

```text
observation ≠ interprétation ≠ résolution ≠ vérité métier
```

L’implémentation de fermeture est **deterministic-first**. Elle n’introduit aucun provider IA, aucun refetch HTTP, aucun Browser, aucune création d’Activity/Occurrence/Journey/Requirement/etc. Une éventuelle escalade modèle future devra réutiliser le gateway `intelligence` provider-neutral déjà présent au dépôt.

---

## 1. Définition

**RETENU** — Actor 3 transforme un matériau Observer finalisé en interprétation candidate versionnée. Cette sortie peut être reprise, comparée, rejetée ou résolue par Actor 4.

## 2. Mission

Répondre à : **« Qu’est-ce que ce matériau semble exprimer ? »**

## 3. Pourquoi il existe

L’Observateur possède la réalité de l’acquisition et sa provenance technique. Le Résolveur possède le rapprochement vers les réalités canoniques. L’Interpréteur porte exclusivement la transformation intermédiaire contenu → candidats sémantiques.

## 4. Objectifs

- réutiliser `ObservationMaterial v2` sans second contrat d’entrée ;
- traiter plusieurs représentations sans explosion de doublons ;
- préférer JSON-LD/JSON/XML/structure HTML avant toute stratégie coûteuse ;
- produire des primitives composables, pas un `ParsedOpportunity` ;
- préserver négation, modalité, AND/OR, valeurs, unités, monnaies et rôles temporels explicites ;
- rendre chaque candidat traçable jusqu’à l’artefact Observer ;
- rendre replay/reprocessing possible sans refaire le Web ;
- fournir un contrat stable au Résolveur ;
- réutiliser le feedback Prospecteur existant.

## 5. Non-objectifs

**REJETÉ** : crawl, fetch HTTP, Browser, découverte de sources, création directe de domaines métier, entity resolution globale, arbitrage entre sources contradictoires, recommandation, calcul Univers Makolo, présentation utilisateur, score métier universel.

## 6. Responsabilités

1. sélectionner les artefacts interprétables ;
2. lire leurs octets via la frontière privée Observer ;
3. parser selon le média ;
4. extraire candidats structurés ;
5. dédupliquer uniquement les expressions sémantiquement identiques dans un run ;
6. conserver les contradictions ;
7. distinguer parsing réussi sans information utile et échec ;
8. persister un run versionné ;
9. projeter un résultat au Résolveur ;
10. produire le feedback Prospecteur pertinent.

## 7. Frontières et interdictions

### Interpréteur / Résolveur

Actor 3 peut produire une mention `Université de Lubumbashi`; il ne peut pas décider qu’elle est `Organization #123`. Il peut produire `X requires CCNA`; il ne décide pas que deux mentions CCNA de pages différentes sont la même réalité.

### Interpréteur / Observer

`insufficient_material` est un diagnostic technique, pas une instruction de crawl. Actor 3 ne pilote pas Browser/HTTP.

### Interpréteur / domaines métier

Les `type_hints` restent des indices candidats ; ils ne constituent pas une taxonomie parallèle de Makolo.

## 8. Entrées

**RETENU — contrat existant**

`observer.contracts.ObservationMaterial`, version 2, plus `DjangoArtifactReader`.

Le Pré-Actor 3 ne modifie pas ce contrat. Pour un futur enrichissement
contextuel, `ObservationMaterial.target_key` permet une lecture séparée et
optionnelle via `ResearchContextSourcePort`, sans faire transiter le contexte
ResearchMission par Actor 2 et sans donner à Actor 3 un accès ORM au Prospecteur.
Voir [`research-missions.md`](research-missions.md).

Le matériau expose : `material_key`, `observation_ref`, cible, handoff/génération, temporalité, locator demandé/final, profile/policy, trigger/outcome/status HTTP, Attempts, artefacts, revalidated artifacts.

Chaque `ArtifactDescriptor` porte owner `observation_ref`, rôle, origin, completeness, byte_length, SHA-256, media type, charset, transformation et protection context.

Aucun chemin de stockage privé n’est exposé.

## 9. Sorties

**RETENU — `InterpretedMaterial v1`**

```text
interpretation_ref
material_key / observation_ref / target_key
strategy_key / strategy_version / strategy_fingerprint
started_at / completed_at
outcome
candidates[]
artifact_uses[]
warning_codes[]
failure_code
```

Primitives :

- `CandidateEntity` : mention + type hints ;
- `CandidateFact` : subject optionnel + predicate + valeur + modalité ;
- `CandidateRelation` : subject/predicate/object + condition/logique ;
- `CandidateConstraint` : subject + predicate + opérateur + valeur ;
- `CandidateValue` : text/number/boolean/date/datetime/quantity/money ;
- `CandidateEvidence` : artifact owner + locator + extraction method + page/offsets possibles.

**REJETÉ** : `ParsedOpportunity`.

## 10. Contrats

### Observer → Interpreter

`ObservationMaterial v2` est l’unique contrat d’entrée. Aucune copie durable du matériau brut.

### Interpreter → Resolver

`DjangoInterpretedMaterialSource.get_material(interpretation_ref)` restitue `InterpretedMaterial v1`. Le Résolveur ne doit normalement pas refaire l’extraction brute.

### Interpreter → Prospecteur

Réutilisation de `ProspectingFeedback` :

- `interpreted` / `partial` avec candidats → `structured_information` ;
- `no_useful_information` → `no_useful_information` ;
- `failed` → aucun faux signal négatif.

Producteur : `interpreter`.

## 11. Sources de vérité

1. octets et métadonnées Observer ;
2. `ObservationMaterial v2` ;
3. run Interpreter + candidats/evidence ;
4. futures décisions Resolver ;
5. domaines métier propriétaires.

La persistance d’un candidat ne le transforme pas en vérité métier.

## 12. Données possédées / référencées / dérivées

**Possédées** : `InterpretationRun`, `InterpretationCandidate`, `InterpretationArtifactUse`.  
**Référencées** : material/observation/target/artifact refs et digests.  
**Dérivées** : candidats, warnings, stats, feedback.  
**REJETÉ** : recopier les blobs Observer.

## 13. Dépendances

- Observer contracts/material/artifact reader ;
- Prospecteur feedback existant ;
- Django/PostgreSQL ;
- `pypdf` pour PDF textuel.

**CANDIDAT futur** : gateway `intelligence` existant pour une escalade LLM/VLM bornée. Aucun provider Interpreter parallèle.

## 14. Consommateurs

Consumer canonique : **Résolveur**. Les opérations/tests peuvent inspecter les runs. Aucune surface utilisateur directe.

## 15. Déclencheurs

```text
Observation finalized
+ aucun run pour (material_key, strategy_fingerprint)
→ pending InterpretationRun
```

Une nouvelle version réelle de stratégie produit un nouveau fingerprint et autorise le reprocessing historique sans refetch.

## 16. Modes d’exécution

- `python manage.py interpreter_worker` continu ;
- `--once` pour cron/opération ;
- `--observation-ref` pour ciblage ;
- batches + leases DB ;
- hors chemin critique utilisateur.

Pas de microservice/Celery imposé.

## 17. Temporalité et fraîcheur

Une interprétation décrit **le matériau observé**, pas le Web « maintenant ».

- 304 : lire `revalidated_artifacts`, conserver leur owner historique ;
- date sans année : ne pas inventer d’année ;
- timezone absente : ne pas inventer de timezone ;
- date de publication, deadline, début, fin restent des predicates distincts seulement quand le contenu les distingue.

## 18. Cycle de vie

```text
pending → processing → finalized
```

Outcomes :

```text
interpreted | partial | no_useful_information | failed
```

Un run finalisé n’est pas silencieusement réécrit. Nouvelle stratégie = nouveau run.

## 19. Idempotence / concurrence

- unicité DB `(material_key, strategy_fingerprint)` ;
- `interpretation_ref` déterministe ;
- `candidate_ref` déterministe depuis payload sémantique ;
- `select_for_update(skip_locked)` lorsque supporté ;
- claim token + lease ;
- lease expirée récupérable ;
- vieux worker incapable de finaliser un claim remplacé ;
- evidences de candidats identiques fusionnables, valeurs contradictoires conservées séparément.

## 20. Erreurs / incertitude / retry

Familles :

```text
unsupported_media
malformed_content
parser_failure
resource_limit
insufficient_material
model_failure   # réservé futur
timeout         # réservé futur
```

Parsing réussi mais aucune information structurée = `no_useful_information`.  
Échec parseur ≠ aucune information utile.  
`TRUNCATED` / `INCOMPLETE` peuvent produire des candidats mais le run devient `partial`.

## 21. Sécurité / confidentialité

- aucun réseau dans la stratégie déterministe ;
- contenu externe = data, jamais instruction ;
- aucun secret/tool/ORM métier donné au contenu ;
- limites bytes/texte/profondeur JSON/nœuds XML/pages PDF/candidats ;
- XML `DOCTYPE`/`ENTITY` rejeté ;
- output validé avant persistance ;
- blobs restent privés chez Observer ;
- feedback sans contenu brut ;
- logs = références/compteurs, pas payload.

Prompt injection telle que `Ignore all previous instructions...` reste du texte inert.

## 22. Reconstruction / reprocessing

`InterpretedMaterial v1` est reconstructible depuis run + candidate rows + artifact uses. Les artefacts Observer historiques sont réutilisés. Aucun refetch requis.

## 23. Échelle

**RETENU pour cette phase** : batches bornés, claims concurrents, leases/recovery, hors requête utilisateur, pas de copie blobs.  
**À DÉTERMINER** : queue distribuée seulement si des mesures réelles l’exigent.

## 24. Coût

Ordre d’escalade :

```text
1 JSON-LD / JSON / XML
2 HTML structuré / text
3 PDF textuel
4 extracteur spécialisé futur
5 modèle léger futur via intelligence
6 modèle coûteux / vision seulement si justifié
```

OCR/VLM n’est jamais déclenché automatiquement.

## 25. Observabilité / métriques

Chaque run conserve notamment :

- bytes/artefacts lus ;
- candidats ;
- parse failures / unsupported artifacts ;
- pages PDF ;
- durée ;
- lease recoveries ;
- compteurs `llm_calls/ocr_calls/vision_calls` actuellement à 0.

`interpreter_metrics()` expose runs/lifecycle/outcomes/candidates/artifact uses/feedback pending.

**REJETÉ** : « plus de facts = mieux ».

## 26. Cas nominaux

### A — Offre d’emploi HTML
Network Engineer + CCNA + TOEFL >= 90 + deadline → mentions, relations `requires`, contrainte score, deadline. Aucune création métier.

### B — Formation séparée
Start/duration/price deviennent des faits candidats distincts.

### C — Session TOEFL
Lubumbashi + 14 October + 250 USD : location, date mentionnée sans année inventée, money typé.

### D — Financement
« couvre les frais... » peut produire `funds`, pas Payment/Funding canonique.

### E — JSON-LD
Données structurées privilégiées ; evidence `json_ld`.

### F — DOM rendu
`rendered_dom` est texte HTML principal ; body HTTP peut encore contribuer des données structurées.

### G — PDF textuel
Extraction page par page avec `pypdf`, evidence de page, pas OCR.

### H — source contradictoire
Deux deadlines → deux candidats distincts. Aucun arbitrage silencieux.

## 27. Cas limites

Couverture contractuelle/testée ou explicitement bornée :

- vide / boilerplate → no useful information ;
- HTML malformé tolérable ;
- JSON malformé → failed ;
- PDF sans texte → échec explicite, pas OCR ;
- tronqué/incomplet → partial ;
- mauvais encodage → replacement + warning ;
- langue source conservée quand fournie ;
- dates/timezones/devises/unités non inventées ;
- négation, optionnel, recommandé, interdit, conditionnel ;
- AND/OR non aplatis ;
- contenu répété dédupliqué uniquement à identité sémantique locale ;
- tableau/liste conservent un locator structurel ;
- prompt injection inerte ;
- XML hostile rejeté ;
- contradictions conservées ;
- mentions d’autres réalités restent candidates.

## 28. Anti-patterns

**REJETÉ**

```text
ObservedArtifact → Activity.objects.create()
LLM dit "bourse" → vérité métier
Interpreter → fetch Internet
Interpreter → Browser
Interpreter → entity resolution globale
Interpreter → choisir quelle source dit vrai
Interpreter → recommendation score
Interpreter → Univers Makolo
toute page → Opportunity
échec parseur → no_useful_information
304 → prétendre qu’un nouvel artefact a été capturé
```

## 29. Tests

La fermeture Actor 3 couvre :

- HTML/text/JSON-LD/XML ;
- rendered DOM vs HTTP body ;
- 304/revalidation ;
- valeurs, deadlines, requirements, score ;
- contradiction, négation, OR ;
- prompt injection ;
- malformed/truncated ;
- deterministic refs ;
- persistance/projection Résolveur ;
- reprocessing nouvelle version ;
- leases/recovery ;
- feedback Prospecteur ;
- migration check ;
- PostgreSQL dédié en CI.

Aucun test ne contacte un vrai site Web ni un provider IA.

## 30. Critères de sortie

Actor 3 est fermé pour cette phase lorsque :

- l’entrée Observer v2 reste unique ;
- aucun refetch n’existe ;
- HTML/text/JSON/XML/PDF textuel et DOM rendu sont correctement bornés ;
- provenance/evidence remontent à l’artefact Observer ;
- deterministic-first est opérationnel ;
- prompt injection est maîtrisée ;
- candidats ≠ vérités métier ;
- résolution d’identité reste hors Actor 3 ;
- contrat Résolveur stable/reconstructible ;
- idempotence/concurrence/reprocessing définis et testés ;
- feedback réutilise Prospecteur ;
- métriques existent ;
- migrations/tests/CI sont verts ;
- documentation correspond au code ;
- branche réconciliée avec `main` courant ;
- `main` vérifié après merge.

---

# Architecture technique

```text
Observer Observation finalized
        ↓
enqueue (material_key, strategy_fingerprint)
        ↓
InterpretationRun[pending]
        ↓ claim + lease
DjangoObservationMaterialSource + DjangoArtifactReader
        ↓
DeterministicInterpreter
  ├ JSON-LD / JSON
  ├ XML / RSS / Atom
  ├ HTML / rendered DOM
  ├ text
  └ PDF text
        ↓
InterpretationRun[finalized]
  ├ InterpretationCandidate*
  └ InterpretationArtifactUse*
        ↓
DjangoInterpretedMaterialSource → Resolver
        ↘ DjangoFeedbackStore → Prospecteur
```

Le modèle persistant est justifié par l’historique versionné, l’handoff asynchrone, l’audit, l’idempotence, la concurrence et le reprocessing. Il ne possède aucune vérité métier.

# Lots réalisés

- **I0 audit + contrats** : runtime main, Observer v2, feedback, Intelligence, collisions.
- **I1 run/provenance** : contrat v1 + migration durable.
- **I2 parseurs déterministes** : HTML/JSON/XML/text.
- **I3 structure sémantique** : entities/facts/relations/constraints/values.
- **I4 documents** : PDF textuel ; OCR systématique rejeté.
- **I5 sécurité** : limites, XML hostile, prompt injection.
- **I6 runtime async** : worker, leases, recovery, feedback.
- **I7 Resolver contract** : source privée reconstructible.
- **I8 hardening/closure** : métriques, docs, migrations, PostgreSQL/CI, réconciliation main.

# Audit de départ

L’audit a confirmé que :

- Prospecteur et Observateur sont intégrés ;
- `ObservationMaterial v2`, `DjangoObservationMaterialSource` et `DjangoArtifactReader` constituent le handoff canonique ;
- aucun Actor 3 existant n’était à dupliquer ;
- Prospecteur accepte déjà `producer=interpreter` et `structured_information/no_useful_information` ;
- `intelligence` fournit déjà une abstraction provider-neutral pour toute escalade future ;
- les PR concurrentes ouvertes concernent surtout Z5/Z6, Spaces, mobile A0 et research, sans nécessité de modifier leurs surfaces centrales ;
- au moment de l’audit, les jobs Django/PostgreSQL de `main` étaient verts mais l’E2E scanner existant était rouge. Ce défaut préexistant reste hors périmètre Actor 3 et ne doit pas être contourné en affaiblissant un test.

Le HEAD et les PR/CI doivent être revérifiés avant l’intégration finale : l’état courant gagne toujours sur cet instantané.


---

# ACT1 — Socle documentaire généraliste

## Contrat document/réalités

Actor 3 distingue désormais explicitement le **document observé** de ce que ce
document mentionne.

```text
ObservationMaterial
        ↓
SemanticDocument
  ├ title / language / document type hints
  ├ SemanticBlock*
  ├ SemanticLink*
  └ StructuredFragment*
        ↓
CandidateEntity / CandidateFact / CandidateRelation / CandidateConstraint
```

`SemanticDocument`, `SemanticBlock`, `SemanticLink` et
`StructuredFragment` sont des value objects éphémères et framework-independent.
Ils ne sont pas des modèles Django et ne créent aucune vérité métier.

Un titre d'article tel que « Le Recteur inaugure un centre de formation » décrit
le document. Il ne transforme pas automatiquement ce document en
`training`, `Activity` ou `Opportunity`. Les réalités mentionnées restent
des candidates séparées lorsqu'elles sont effectivement établies par le contenu.

## Structure et provenance

Le parser HTML générique conserve notamment :

- title, h1..h6, paragraphes et contexte de headings ;
- main/section/article/nav lorsque pertinent ;
- listes, listes de définitions et tableaux ;
- liens, canonical et hreflang ;
- formulaires et contrôles sans copier leurs valeurs sensibles ;
- time/datetime, address et metadata ;
- JSON-LD, OpenGraph/meta et microdata raisonnable.

Les locators sont dérivés de la structure HTML, pas des classes CSS métier.
Changer `.event-date` en `.details-v2` ne change donc pas un bloc lorsque la
structure sémantique reste identique.

Chaque bloc garde `artifact_ref`, l'`artifact_observation_ref` historique,
un locator stable et, pour le PDF textuel, le numéro de page. Un reprocessing
d'une Observation revalidée continue donc de pointer vers l'artefact réellement
observé au lieu de réattribuer sa provenance au run courant.

## Frontières

ACT1 reste entièrement déterministe :

- aucun fetch supplémentaire ;
- aucun navigateur dans Actor 3 ;
- aucun LLM ;
- aucun Crawl4AI ;
- PDF textuel via pypdf uniquement ;
- PDF sans texte extractible => diagnostic explicite ;
- aucune résolution canonique Actor 4 ;
- aucune écriture métier.

La stratégie généraliste passe en version `2.0` avec un nouveau
`strategy_fingerprint`. Les workers ne claim plus silencieusement les anciens
runs `pending` appartenant à un fingerprint différent ; ils restent dans
l'historique et peuvent être traités par leur stratégie correspondante.

## Compatibilité et persistance

Les contrats `InterpretedMaterial`, `Candidate*`, `CandidateValue`,
`CandidateEvidence` et `ArtifactUse` restent inchangés. Aucun nouveau modèle
persistant et aucune migration ne sont nécessaires.

La structure documentaire est une étape interne d'interprétation ; elle prépare
le grounding par blocs des phases ultérieures sans déplacer l'autorité métier
dans Actor 3.


---

# ACT2 — Extraction déterministe riche et généraliste

ACT2 remplace les règles spécialisées de benchmark par un petit vocabulaire
d'interchange réutilisable. L'Interpréteur continue à produire uniquement des
`Candidate*` ; il ne produit ni `Activity`, ni `Requirement`, ni
`Opportunity`, ni objet métier canonique.

Le module `interpreter/generalist.py` couvre de façon déterministe :

- dates complètes et datetimes avec timezone explicite ;
- durées, nombres, quantités, unités, prix/devise explicite et Capacity annoncée ;
- comparateurs et intervalles, sans inventer d'unité ou de devise ;
- modalités asserted/required/optional/recommended/prohibited/negated/conditional ;
- groupes logiques AND/OR conservés dans les relations/contraintes ;
- lieux, organisations et personnes lorsqu'ils sont explicitement étiquetés ;
- URLs de candidature, inscription, contact et référence ;
- emails, téléphones, formulaires et disponibilité.

Une date incomplète telle que `14 October` reste textuelle. Une datetime sans
timezone n'est pas convertie en instant absolu. Une valeur `Price: 100` ne
reçoit aucune devise inventée.

Les anciennes règles nommées TOEFL/IELTS/CCNA ne sont plus nécessaires au
moteur : un seuil tel que `Language score >= 80` ou `TOEFL >= 90` est traité
par le même comparateur générique.

Les huit familles `ResearchMission` servent de **scénarios de couverture** :
POSSIBILITY, REQUIREMENT, QUALIFICATION, ACTOR, SPATIOTEMPORAL, PROCEDURE,
ECONOMIC et REFERENCE. Elles ne sont jamais passées comme filtres destructifs
au parseur et ne changent pas ce que le document affirme.

# ACT3 — Normalisation avancée, Intelligence et grounding

## ContentNormalizationPort

La normalisation avancée est derrière `ContentNormalizationPort`. Le port
reçoit un `SemanticDocument` déjà acquis par Actor 2 et ne possède aucune
capacité réseau. L'implémentation de base est volontairement identitaire et
remplaçable.

### Décision Crawl4AI

Audit du 25 septembre 2026 : Crawl4AI a une release 0.9.4 publiée le
23 septembre 2026. Makolo ne l'ajoute pas au runtime Actor 3 à ce stade :

- Actor 2 possède déjà l'acquisition HTTP et Playwright ;
- Actor 3 ne doit jamais recrawler une URL externe ;
- ajouter un second stack crawler/browser augmenterait les dépendances serveur
  sans gain démontré par le benchmark Makolo ;
- le port permet une future expérimentation sur contenu **déjà observé** sans
  changer le contrat Actor 3.

Cette décision est réversible ; aucune abstraction Actor 3 ne dépend de
Crawl4AI.

## IntelligenceGateway uniquement

L'enrichissement modèle utilise exclusivement :

`IntelligenceCapability.STRUCTURED_GENERATE`
→ `IntelligenceGateway`
→ registry/routing/credentials/telemetry existants.

Actor 3 n'importe aucun SDK fournisseur et ne lit aucun secret.

Le runtime construit la registry canonique. Lorsqu'une route est disponible,
l'identité de stratégie inclut une signature non secrète des providers/modèles
routés, afin qu'un changement de route ne réutilise pas silencieusement un
ancien `interpretation_ref`.

Sans provider configuré, le chemin déterministe reste complet et aucun appel
réseau Actor 3 n'est ajouté.

## Grounding obligatoire

Le modèle reçoit seulement une projection bornée des blocs observés. Le contenu
du document est explicitement traité comme donnée non fiable et jamais comme
instruction.

Les sorties modèles sont rejetées si :

- le schéma n'est pas celui des candidates génériques ;
- une entity ref est inconnue ;
- un `evidence_block_ref` n'existe pas ;
- le label ou la valeur n'est pas réellement présent dans les blocs cités ;
- une relation cite des endpoints non groundés ;
- une contrainte est incohérente ;
- un score arbitraire de confiance est fourni.

Les preuves acceptées deviennent `CandidateEvidence` avec
`extraction_method=intelligence_grounded`. Les stats séparent appels,
candidates acceptées et candidates rejetées. Aucun contenu brut ni prompt n'est
envoyé à la telemetry.

# ACT4 — Benchmark, fermeture Actor 3 et handoff Actor 4

`interpreter/benchmark.py` mesure les résultats par sémantique utile plutôt
que par volume de candidates. Le rapport couvre notamment :

- entités/predicates attendus manquants ;
- hints explicitement interdits ;
- predicates inattendus lorsqu'un oracle exhaustif est fourni ;
- preuves absentes ;
- doublons sémantiques ;
- groupes de contradictions ;
- distribution date/datetime/money/quantity ;
- temps, bytes lus, appels intelligence et accept/reject grounding ;
- coût provider = `None` lorsque le provider ne l'expose pas.

La matrice CI couvre bourse, procédure visa, transport, requirements/
qualification, organization/place, JSON-LD, PDF textuel, rendered DOM, prix,
Capacity, formulaires et références. Elle vérifie aussi explicitement qu'un
titre d'article contenant « formation » ne devient pas une Activity/training.

## Benchmark historique UNIKIN

Aucun artefact UNIKIN ni snapshot du benchmark historique « 16 entities /
4 publication_date » n'est versionné dans le dépôt courant, et aucun résultat
ne doit être fabriqué. Le harness ACT4 travaille sur `ObservationMaterial` et
`ArtifactReader`, donc les artefacts historiques peuvent être rejoués sans
refetch dans l'environnement où le store Observer qui les possède est monté.

L'absence de ces bytes dans GitHub est une limite d'évidence du benchmark
historique, pas une raison de recrawler silencieusement les sites.

## Handoff Actor 4

Actor 4 reste inchangé. Le test de handoff vérifie qu'il consomme les nouvelles
`CandidateEntity/Fact/Relation/Constraint` et les nouveaux predicates sans que
l'Interpréteur écrive dans les domaines métier.

Classification de fermeture :

- **A — déjà géré** : candidates génériques, facts, relations, constraints et
  provenance arrivent dans Resolver ;
- **B — dette Actor 4** : une candidate peut être reçue mais rester
  `NEW_CANDIDATE/PARTIAL/UNRESOLVED` faute de lookup canonique adapté ;
- **C — défaut Actor 3** : hallucination, mauvaise provenance, faux type de
  document, écrasement de contradiction ou perte de logique ; ces cas sont
  rejetés/couverts côté Actor 3.

Actor 3 reste donc responsable de « ce que le matériau observé semble
exprimer », jamais de « quelle réalité canonique Makolo est-ce ? ».

# Fermeture du programme ACT

Le programme n'ajoute :

- aucune nouvelle table ;
- aucune migration ;
- aucun crawler réseau dans Actor 3 ;
- aucune dépendance Crawl4AI ;
- aucun SDK LLM direct ;
- aucune écriture métier ;
- aucune résolution canonique.

Le pipeline final reste :

```text
Actor 1 Prospector
→ Actor 2 Observer / ObservationMaterial v2
→ Actor 3 SemanticDocument + deterministic generalist extraction
→ optional grounded IntelligenceGateway enrichment
→ InterpretedMaterial / Candidate*
→ Actor 4 Resolver
```

Les documents, blocs et normalisations restent éphémères. Les vérités durables
restent dans leurs domaines propriétaires.

---

# ACT-F — Raffinement après test Web réel

Le 25 septembre 2026, un pilote local réel a exercé la chaîne
Prospecteur → Observateur HTTP → Interpréteur sur des pages publiques découvertes
par Common Crawl. Le runtime Actor 3 a finalisé ses runs sans échec, mais
l'inspection des candidates a révélé plusieurs faux positifs déterministes que
la matrice synthétique ne couvrait pas encore.

Corrections retenues :

- les assets techniques `.css/.js/fonts/images/media` ne deviennent plus
  `contact_url`, `registration_url` ou `reference_url` par simple présence
  de mots comme « contact », « form » ou « search » dans leur chemin ;
- les pseudo-liens vides/`#` et schémas inertes ne deviennent plus des URLs
  de procédure ;
- l'extraction téléphone exige désormais une quantité plausible de chiffres et
  rejette notamment les plages d'années telles que `2026-2027` ;
- dans un contexte d'admission, une étape procédurale telle que examen de
  dossier, entretien, sélection, validation ou confirmation n'est plus
  automatiquement transformée en `requirement_subject` sans marqueur explicite
  d'obligation/condition ;
- `WebSite` et `BreadcrumbList` restent des objets structurés de la page et ne
  sont plus fusionnés dans les `type_hints` du document courant ;
- la stratégie passe en version `2.1` avec fingerprints
  `document_structure=2` et `generalist_semantics=2`, ce qui permet de rejouer
  les mêmes ObservationMaterial sans refetch.

Le pilote a aussi montré qu'un cycle `ProspectorRuntime.run_cycle()` revendique
la Frontier READY globale, pas « la mission qui vient juste d'être lancée ».
Un batch de 10 handoffs peut donc mélanger cibles de la mission courante et
cibles READY antérieures. Une comparaison mission-scoped doit filtrer par
provenance `mission_key`; l'écart 10 cibles découvertes / 7 runs associés dans
ce pilote n'est donc pas, à lui seul, une perte Actor 3.

Aucune migration, aucun nouveau fetch, aucun changement Actor 4.
