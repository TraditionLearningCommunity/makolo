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
