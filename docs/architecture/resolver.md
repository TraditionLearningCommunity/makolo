# Actor 4 — Résolveur Makolo

> **Statut : contrat runtime Actor 4.** Le code, les migrations et les tests du
> `main` courant restent la vérité. Ce document définit la frontière
> `InterpretedMaterial v1 → ResolvedMaterial v1 → Orchestrateur`.

## 1. Définition

**RETENU**

Le Résolveur Makolo est l'acteur interne qui détermine à quelles réalités
connues ou nouvelles se rapportent les candidats de l'Interpréteur, établit
leurs correspondances, relations, ambiguïtés, mises à jour et contradictions
avec une provenance traçable, sans modifier lui-même les vérités métier
propriétaires.

```text
ObservationMaterial v2
        ↓
Interpréteur
        ↓
InterpretedMaterial v1
        ↓
Résolveur
        ↓
ResolvedMaterial v1
        ↓
Orchestrateur
```

Observation ≠ interprétation ≠ résolution ≠ mutation métier.

## 2. Mission

Transformer une interprétation structurée en **assertions de résolution
réversibles et explicables** :

- correspondance avec une réalité canonique existante ;
- nouvelle réalité candidate ;
- ambiguïté entre plusieurs réalités ;
- fait/relation/contrainte rattaché(e) à une identité résolue ou provisoire ;
- mise à jour temporelle ;
- conflit ;
- information encore non résolue.

Le Résolveur conclut sur l'identité et le rattachement. L'Orchestrateur décide
de l'effet métier.

## 3. Pourquoi il existe

L'Interpréteur peut savoir que « CCNA » est une entité et que « Network
Engineer requires CCNA » est une relation sans savoir si cette mention
correspond à une réalité déjà connue de Makolo. Le Résolveur ferme ce manque
sans transformer une extraction en écriture de domaine.

## 4. Objectifs

1. réduire les doublons sans encourager les false merges ;
2. faire converger plusieurs observations quand les preuves sont suffisantes ;
3. conserver l'incertitude quand elles ne le sont pas ;
4. préserver les contradictions au lieu de choisir silencieusement ;
5. permettre le replay avec de nouvelles stratégies ;
6. livrer à l'Orchestrateur une entrée stable et sans dépendance ORM directe.

## 5. Non-objectifs

Le Résolveur n'est ni crawler, ni Browser, ni Interpréteur bis, ni moteur de
Readiness, ni Univers Makolo, ni moteur de permissions, ni présentateur, ni
service de mutation métier.

Il ne décide pas INSERT/UPDATE/DELETE dans Activity, Occurrence, Organization,
Opportunity, Journey, Requirement, Proof, Access, Capacity, Payment, Profile,
Dossier ou Project.

## 6. Responsabilités

- candidate generation bornée ;
- résolution d'identité ;
- rapprochement intra/inter-sources ;
- déduplication prudente ;
- références externes scopées ;
- comparaison de faits ;
- temporalité update/conflit ;
- provenance multi-source ;
- degré de résolution explicite ;
- replay/versionnement ;
- feedback Prospecteur.

## 7. Frontières et interdictions

**REJETÉ**

- même nom ⇒ même entité ;
- même URL ⇒ même réalité métier éternellement ;
- nearest embedding ⇒ MERGE ;
- LLM says same ⇒ MERGE ;
- source la plus récente ⇒ toujours vraie ;
- source officielle ⇒ autorité universelle ;
- unresolved ⇒ création métier ;
- résolution ⇒ transfert de Permission, Mandate, Access ou Payment.

Le Résolveur n'appelle aucun service de mutation comme
`Activity.objects.create()` ou `merge_opportunities()`.

## 8. Entrée

L'entrée canonique est `InterpretedMaterial v1`, obtenue par
`DjangoInterpretedMaterialSource`.

Elle contient les refs de provenance, la stratégie d'interprétation, l'outcome,
les candidats Entity/Fact/Relation/Constraint, les Evidence, modalités,
conditions et groupes logiques AND/OR.

Seuls les outcomes `interpreted` et `partial` sont résolus. Les échecs ou
matériaux sans information utile restent la responsabilité de l'étage amont.

## 9. Sortie

La sortie canonique est `ResolvedMaterial v1` :

- identité du run et de l'interprétation source ;
- stratégie/version/fingerprint ;
- outcome ;
- assertions de résolution ;
- warnings/failure ;
- provenance originale incluse dans le payload candidat.

Les assertions utilisent des `CanonicalRef(domain, object_ref)` opaques. Le
contrat générique n'importe pas les modèles Django.

## 10. Contrats

### Entity

Statuts utiles : `matched`, `new_candidate`, `ambiguous`, `unresolved`,
`rejected`.

Une nouvelle réalité reçoit une référence provisoire déterministe. Elle n'est
pas encore un objet métier.

### Fact / Constraint

Le Résolveur rattache la proposition au sujet résolu/provisoire et conserve sa
valeur originale, sa modalité, son evidence et son fingerprint sémantique.

### Relation

Les deux extrémités sont préservées indépendamment. Une relation peut rester
`partial` si une seule extrémité est résolue. Les groupes AND/OR, négations,
conditions et modalités survivent inchangés.

### Conflict

Un conflit est une conclusion normale. Il porte les candidate refs concernées
et sa base explicative.

## 11. Sources de vérité

Le Résolveur lit seulement les domaines canoniques existants. Les domaines
propriétaires restent la vérité. Les tables `resolver_*` possèdent uniquement
les conclusions techniques de résolution et leur historique.

Les mécanismes existants sont réutilisés :

- canonicalisation URL du Prospecteur ;
- source/provenance et merges Opportunity ;
- Activity/Occurrence ;
- Organization ;
- Geography ;
- journal de feedback Prospecteur.

## 12. Données possédées / référencées / dérivées

**Possédées** : ResolutionRun, ResolutionAssertionRow.

**Référencées** : interpretation_ref, candidate_ref, target_key,
CanonicalRef.

**Dérivées** : normalisations de comparaison, fingerprints, alternatives,
provisional refs, outcome de résolution.

Aucune copie de `ResolvedActivity`, `ResolvedOccurrence` ou
`ResolvedOrganization` n'est créée.

## 13. Dépendances

Actor 3 Interpreter, domaines lus par adaptateurs, PostgreSQL/Django ORM et
Prospector feedback. Aucune dépendance réseau extérieure.

## 14. Consommateurs

Le consommateur primaire est Actor 5 — Orchestrateur via
`ResolvedMaterialSourcePort` / `DjangoResolvedMaterialSource`.

Le Prospecteur reçoit uniquement des signaux de feedback sans faits métier.

## 15. Déclencheurs

Un run est enqueue lorsqu'une nouvelle interprétation finalisée
`interpreted|partial` n'a pas encore été traitée par le fingerprint courant.
Un replay ciblé peut être demandé par `interpretation_ref`.

## 16. Modes d'exécution

Worker continu ou cycle `--once`. Aucun appel Internet caché. La stratégie V1
est deterministic-first et provider-neutral.

## 17. Temporalité et fraîcheur

Fraîcheur de l'identité ≠ fraîcheur d'un fait.

Un même endpoint + même predicate + même fingerprint observé plus tard est une
réobservation. Une valeur différente provenant de la même source dans une
observation ultérieure est marquée `update`; elle ne détruit pas la valeur
historique. Une valeur incompatible provenant d'une autre source devient
`conflict`.

La récence seule ne décide pas la vérité.

## 18. Cycle de vie

```text
pending → processing → finalized
```

Outcomes finaux :

`resolved | partial | ambiguous | conflict | unresolved | failed`.

Les trois états ambiguity/conflict/unresolved ne sont pas des pannes.

## 19. Idempotence et concurrence

L'unicité logique d'un run est :

```text
interpretation_ref + resolver_strategy_fingerprint
```

Les refs de run, assertions et nouvelles réalités candidates sont
déterministes. Les claims utilisent token + lease et les leases expirées sont
récupérables.

Deux workers sur la même interprétation ne doivent produire qu'un run. Deux
interprétations simultanées peuvent produire la même conclusion provisoire
lorsque leur identité déterministe le permet ; l'Orchestrateur reste
responsable de la création canonique atomique et doit revalider l'état courant
avant mutation.

## 20. Erreurs / incertitude / retry

Erreurs techniques : contract/strategy/backend/resource. Incertitudes métier :
ambiguous/unresolved/conflict.

Une panne de feedback Prospector ne détruit pas le résultat : le feedback reste
retentable séparément.

## 21. Sécurité et confidentialité

Les candidats externes sont des données, jamais des instructions. Aucun texte
du Web n'est exécuté.

Les adaptateurs effectuent des lectures bornées. Une résolution ne donne aucun
nouveau droit de lecture ou de divulgation. Les projections aval doivent
appliquer la divulgation minimale. Aucun contenu candidat/PII/secret n'est
journalisé dans les métriques.

## 22. Reconstruction / reprocessing

Changer le `strategy_fingerprint` crée un nouveau ResolutionRun à partir du
même InterpretedMaterial. L'ancienne conclusion reste immuable. Observation et
Interprétation ne sont pas rejouées.

## 23. Échelle

Le V1 ne compare jamais un candidat à toute la base par fuzzy global.

Ordre :

1. clés externes scopées / source canonique connue ;
2. lookups déterministes bornés ;
3. blocking par domaine ;
4. signaux textuels faibles seulement comme alternatives possibles.

Les adaptateurs limitent la génération de candidats. Candidate generation ≠
décision de match.

## 24. Coût

Aucun LLM, embedding, OCR ou réseau n'est utilisé en V1. Les stats exposent
`model_calls=0` et `network_calls=0`.

Une future méthode probabiliste doit rester derrière une stratégie versionnée
et ne pourra pas produire une fusion irréversible.

## 25. Observabilité / métriques

Compteurs : lifecycle, outcomes, assertions, exact/matched/new/ambiguous,
conflits, durée, lease recoveries, feedback pending. Le nombre de merges n'est
jamais une métrique d'optimisation.

## 26. Cas nominaux

### A — Organization existante

Un identifiant/website suffisamment discriminant peut produire `MATCHED`.
Le nom seul produit au plus une alternative `POSSIBLE`.

### B — alias

« UNILU » n'est pas fusionné automatiquement avec « Université de Lubumbashi »
sans preuve additionnelle. Résultat possible : `AMBIGUOUS` ou
`NEW_CANDIDATE`.

### C — même offre sur deux pages

Une URL déjà enregistrée comme `OpportunitySource`, ou une référence externe
identique dans le même namespace source, constitue un signal exact. Un titre
identique seul ne suffit pas.

### D — Activity + Occurrence

Une Activity décrit l'identité durable. Un titre + date structurée peut
permettre de résoudre une Occurrence précise ; le Résolveur ne remplace pas
l'Occurrence par l'Activity.

### E — nouvelle réalité

Aucun match sûr ⇒ `NEW_CANDIDATE` avec provisional_ref, sans création ORM.

### F — contradiction

Même réalité + même predicate + valeurs incompatibles inter-sources ⇒
`CONFLICT`.

Dans un même `InterpretedMaterial`, deux valeurs différentes ne constituent
pas automatiquement une contradiction. Les prédicats naturellement
multivalués (contacts, liens, références, conditions, etc.) sont additifs.
`same_material_conflicting_values` n'est produit que pour des facts dont la
sémantique est explicitement mono-valuée par la stratégie (par exemple une
deadline unique). Les `Constraint` restent additives par défaut : plusieurs
conditions peuvent décrire simultanément la même réalité.

### G — update

Même source, observation ultérieure, même identité/predicate et valeur nouvelle
⇒ `UPDATE`, avec ancienne candidate_ref conservée.

## 27. Cas limites

- noms identiques : ambiguïté ;
- copies/syndication : convergence seulement si preuves suffisantes ;
- même nom + dates différentes : Occurrences potentiellement distinctes ;
- changement d'URL : l'identité peut survivre via d'autres preuves ;
- domaine recyclé : hostname seul n'est pas une identité éternelle ;
- archive ancienne : provenance et chronologie conservées ;
- traduction/acronyme : signaux faibles, jamais preuve unique ;
- identifiant provider : toujours scoped au namespace source ;
- page multi-réalités : traitement par candidats, jamais 1 page = 1 réalité ;
- une réalité multi-pages : convergence possible via preuves partagées.

## 28. Anti-patterns

Tout appel de mutation de domaine depuis `resolver/` est une régression
architecturale. Toute confiance numérique opaque, score global de source ou
règle « plus récent gagne » est exclue du V1.

## 29. Tests

La suite Actor 4 couvre :

- contrat Interpreter → Resolver ;
- ResolvedMaterial → Orchestrator ;
- exact/new/ambiguous ;
- protection same-name ;
- Activity/Occurrence ;
- contradictions et updates ;
- logique relationnelle ;
- idempotence/reprocessing ;
- leases ;
- PostgreSQL ;
- absence de mutation des domaines propriétaires.

Le workflow `Resolver Actor 4` exécute check migrations + tests sur PostgreSQL.

## 30. Critères de sortie

Actor 4 est fermé lorsque :

- `InterpretedMaterial v1 → ResolvedMaterial v1` fonctionne ;
- known/new/ambiguity/conflict/unresolved sont représentables ;
- provenance et historique sont conservés ;
- Activity/Occurrence restent distincts ;
- exact/deterministic précèdent les heuristiques ;
- replay/versionnement/lease/idempotence sont opérationnels ;
- feedback Prospecteur réutilise son contrat existant ;
- aucune mutation canonique n'est réalisée ;
- Actor 5 dispose de `DjangoResolvedMaterialSource` ;
- migrations/tests/CI sont verts ;
- documentation = runtime.

## Train effectivement livré

- **R0** audit runtime/contrats/collisions ;
- **R1** contrats `ResolvedMaterial v1` + persistance minimale ;
- **R2** lifecycle, leases, worker et replay ;
- **R3** exact identity / external source keys ;
- **R4** adapters Organization/Geography ;
- **R5** Activity/Occurrence + facts/relations ;
- **R6** temporalité/conflits/multi-source ;
- **R7** heuristiques bornées et candidate generation ;
- **R8** contrat Orchestrator + feedback Prospecteur ;
- **R9** tests, operations, CI et fermeture.

Aucune phase ne crée un nouveau domaine métier.
