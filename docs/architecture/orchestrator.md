# Actor 5 — Orchestrateur Makolo

> **Statut : contrat runtime Actor 5.** Le code, les migrations, les tests et le
> `main` courant restent la vérité. L'Orchestrateur est une responsabilité
> applicative distribuée ; ce document ne crée pas un bounded context métier
> propriétaire de toutes les vérités Makolo.

## O0 — audit du runtime

Audit réalisé sur `main` à partir de `b4b74cc1363e99d9d668506007de57d9f2e8fa6a`,
merge d'Actor 4.

### Conclusion

Actor 5 **ne nécessite pas un nouveau gros runtime central**. Makolo possède
déjà l'essentiel de l'orchestration dans les services applicatifs/domaines :

- services transactionnels Activity, Journey, Access, Capacity, Commerce,
  Payment, Opportunity, Trust, Objectives, etc. ;
- autorité canonique `Permission/Mandate` ;
- outbox et consumers Domain Events ;
- idempotence et verrous portés par les propriétaires ;
- Automation et workers ;
- contrats d'actions externes M7 dans `interoperability.actions` ;
- orchestration contextuelle déjà présente sur certaines surfaces, notamment
  Makolo Mark.

Le manque réel était surtout une frontière explicite et sûre
`ResolvedMaterial v1 -> décision applicative -> owner`, ainsi qu'un contrat
commun interdisant de transformer l'Orchestrateur en God Object.

Aucun runtime `Projector` ou `Univers Makolo` n'est actuellement présent
dans le code du `main` audité. Actor 5 ne fabrique donc aucun faux handoff vers
ces acteurs. Ces ports devront être ajoutés seulement lorsque leurs contrats
runtime existeront.

## Formule stabilisée

> **L'Orchestrateur Makolo est la responsabilité interne qui décide quelle
> action applicative doit suivre un fait, une résolution, une demande ou un
> événement, puis coordonne les domaines et acteurs propriétaires pour
> l'accomplir, sans devenir propriétaire de leurs vérités, de leurs calculs, de
> leur persistance spécialisée, de leurs effets externes ou de leur
> présentation.**

---

# SPEC — 30 dimensions

## 1. Définition

Responsabilité applicative distribuée qui transforme une entrée déjà structurée
en une décision explicite, puis délègue au propriétaire canonique compétent.

Il n'existe pas de classe globale `MakoloOrchestrator`.

## 2. Mission

Répondre à deux questions :

1. **qui possède cette vérité ou cette opération ?**
2. **quelle opération propriétaire est légitime dans l'état actuel ?**

## 3. Pourquoi il existe

Une résolution, un événement, une requête HTTP ou un résultat calculé ne sont
pas des mutations métier. Une couche de décision est nécessaire pour empêcher
les raccourcis du type extraction externe -> ORM ou calcul -> effet externe.

## 4. Objectifs

- protéger ownership et invariants ;
- rendre les décisions explicables ;
- réutiliser les services existants ;
- revalider l'état et l'autorité au moment de la mutation ;
- préserver idempotence et concurrence ;
- permettre le no-op comme résultat normal ;
- séparer décision, persistance, calcul, exécution et présentation.

## 5. Non-objectifs

Actor 5 n'est pas :

- un nouveau schéma de données universel ;
- un second bus d'événements ;
- un moteur CQRS générique ;
- un task manager ;
- un moteur de Readiness ;
- le Projecteur ;
- l'Univers Makolo ;
- l'Exécutant ;
- le Présentateur ;
- une source de vérité métier.

## 6. Responsabilités

- classifier l'effet applicatif d'une entrée ;
- trouver le propriétaire canonique ;
- revalider fraîcheur, état et autorité ;
- appeler le service propriétaire ;
- préserver les conflits et incertitudes ;
- produire un résultat applicatif structuré ;
- déléguer les effets externes à leurs contrats dédiés.

## 7. Frontières et interdictions

Interdits :

- `ResolvedMaterial -> Model.objects.create/update` générique ;
- `setattr(object, predicate, value)` ;
- déduire une autorité d'un Membership/Group/Team ;
- recopier Readiness ;
- importer toute règle métier dans un God Service ;
- faire de chaque Domain Event une notification ;
- faire d'un résultat Univers une autorisation ;
- générer HTML/UI.

Le runtime `orchestration/` ne possède qu'un registre explicite de handlers
owner-backed. Il n'effectue aucun dispatch dynamique vers des modèles Django.

## 8. Entrées

Entrées conceptuelles :

- `ResolvedMaterial v1` ;
- commande utilisateur déjà validée au transport ;
- Domain Event ;
- résultat futur de l'Univers ;
- réaction de workflow/application.

Le premier contrat livré est `ResolvedMaterial v1`.

## 9. Sorties

Une décision applicative structurée :

- `apply` ;
- `no_action` ;
- `defer` ;
- `review` ;
- `reject` ;
- `conflict`.

Les mutations réelles restent des retours de services propriétaires.

## 10. Contrats

Contrats runtime livrés :

- `OrchestrationContext` ;
- `OrchestrationDecision` ;
- `OwnerDecision` ;
- `OrchestrationDecisionRecord` ;
- `OrchestrationResult` ;
- `ResolvedMaterialOwnerRegistry` ;
- `orchestrate_resolved_material()` ;
- `orchestrate_resolution()`.

Le contrat Actor 4 est consommé via son port/source ; Actor 5 n'importe pas les
tables Resolver pour obtenir le matériau.

## 11. Sources de vérité

Chaque domaine propriétaire reste la source de vérité.

Les décisions Actor 5 en mémoire ne deviennent pas une copie durable de l'état
métier. Les Domain Events existants restent l'outbox canonique lorsqu'un owner
en émet.

## 12. Données possédées / référencées / dérivées

**Possédées durablement : aucune table Actor 5.**

Références : refs de résolution/assertion, owner domain, object refs opaques.

Dérivées : décision, reason code, opération appelée, ref de résultat.

## 13. Dépendances

Actor 4 Resolver, services propriétaires, Authorization et, selon le workflow,
Domain Events / M7 Interoperability.

Aucune dépendance à une implémentation Univers inexistante.

## 14. Consommateurs

- services/applications appelants ;
- futures boucles event-driven ;
- Presenter via un résultat déjà autorisé ;
- futur Persistateur pour les décisions de durabilité sous ownership métier ;
- futur Projecteur lorsque son port existera.

## 15. Déclencheurs

Le V1 peut être invoqué directement sur un `ResolvedMaterial` ou sur une
`resolution_ref` via `ResolvedMaterialSourcePort`.

Les autres déclencheurs restent portés par les chemins existants plutôt que
centralisés artificiellement.

## 16. Modes d'exécution

- synchrone dans un service/application handler ;
- event-driven via l'infrastructure Domain Events existante ;
- worker seulement lorsqu'un workflow existant le justifie.

Aucun worker Actor 5 générique n'est créé.

## 17. Temporalité et fraîcheur

Une résolution est datée. Avant mutation, l'owner relit l'objet courant sous le
verrou approprié.

Le premier handler Activity refuse automatiquement d'écraser un état dont
`updated_at` est plus récent que `ResolvedMaterial.completed_at`.

La récence seule ne rend toutefois pas une source autoritative.

## 18. Cycle de vie

Actor 5 n'a pas de lifecycle persistant global.

Une invocation fait :

`entrée -> décision -> owner éventuel -> résultat`.

Un workflow durable continue d'utiliser le lifecycle de son domaine
propriétaire.

## 19. Idempotence / concurrence

L'idempotence est portée au niveau logique pertinent :

- identity Resolver stable ;
- no-op si l'état canonique contient déjà la valeur ;
- contraintes/idempotency keys des owners ;
- verrous `select_for_update` lorsque le domaine l'exige ;
- outbox Domain Events idempotente.

Actor 5 ne crée pas de lock global.

## 20. Erreurs / incertitude / retry

- `ambiguous/unresolved/partial` -> `defer` ;
- conflit -> `conflict`, sans mutation ;
- new candidate -> `review` tant qu'un owner n'a pas une politique suffisante ;
- invariant/autorité owner refusé -> `reject` ;
- panne technique : elle reste technique et peut être retentée selon le chemin
  appelant.

Un retry ne transforme jamais un refus métier en autorisation.

## 21. Sécurité / confidentialité

Le contexte d'autorité est serveur.

Pour une Activity d'Espace, fournir un `represented_space` ne crée aucun
droit : le scope doit correspondre et `Permission/Mandate` est revalidé.

Pour une Activity personnelle, injecter un Espace représenté est rejeté.

Les logs ne contiennent que refs/codes techniques, jamais le payload externe
complet ni des secrets.

## 22. Reconstruction

Actor 5 n'ajoute pas de vérité opaque à reconstruire. Les vérités durables
restent dans les domaines, leurs événements et les étages d'observation /
interprétation / résolution appropriés.

## 23. Échelle

Le dispatch est par owner explicite et constant ; aucun scan global de modèles
ou découverte dynamique de handlers.

L'échelle réelle reste celle des services propriétaires.

## 24. Coût

Aucun LLM, réseau, OCR ou calcul Univers dans le runtime Actor 5 livré.

Le bon résultat peut être zéro mutation.

## 25. Observabilité / métriques

Chaque décision Resolver -> Actor 5 logue seulement :

- `resolution_ref` ;
- `assertion_ref` ;
- décision ;
- reason code ;
- owner ;
- operation.

Les métriques futures peuvent agréger apply/no-op/defer/review/reject/conflict,
sans faire du nombre de mutations un KPI de qualité.

## 26. Cas nominaux

### A — nouvelle réalité candidate

`NEW_CANDIDATE -> REVIEW` par défaut. Aucun objet canonique n'est créé.

### B — Activity connue, information nouvelle

Un `UPDATE` vers une Activity canonique peut être routé vers
`activity.update_common` seulement si :

- predicate explicitement supporté ;
- état non plus récent ;
- politique d'autorité de source explicitement satisfaite ;
- acteur authentifié ;
- représentation Space correcte ;
- Permission/Mandate valide.

### C — Requirement découvert

Aucun handler générique n'est inventé. Le résultat reste `REVIEW` jusqu'à ce
qu'un contrat propriétaire Requirement/versionné réellement adapté soit
identifié.

### D — nouvelle Occurrence

Même règle : pas de création à partir du seul fait d'avoir une date. Une
politique owner Activity/Occurrence dédiée devra décider la sémantique.

### E — contradiction

`CONFLICT -> CONFLICT + aucune mutation`.

### F — utilisateur commence une action

Les services Journey existants restent owners. Actor 5 ne crée pas un Journey
parallèle.

### G — action au nom d'un Space

Le Mandate/Permission est revalidé serveur ; Membership seul ne suffit pas.

### H — résultat Univers

Aucun runtime Univers n'existe dans le `main` audité. Le contrat reste :
calcul != autorisation. Aucun faux adapter n'est créé.

### I — action externe

M7 fournit déjà `interoperability.actions`, qui vérifie action,
autorisation, Connection et idempotency avant handler. Actor 5 doit lui fournir
une commande déjà décidée, pas dupliquer ce registre.

## 27. Cas limites

Couverts ou explicitement protégés :

- replay même update -> no-op ;
- résolution plus vieille que l'état canonique -> review ;
- objet canonique absent -> review ;
- conflit -> aucune mutation ;
- Membership sans Mandate -> rejet ;
- spoofing Profile/Space -> rejet ;
- predicate inconnu -> review ;
- owner non enregistré -> review ;
- source non autoritative -> review par défaut.

Capacity/Payment/Executor restent couverts par leurs propres garanties jusqu'à
ce qu'un use case Actor 5 les appelle explicitement.

## 28. Anti-patterns

Rejetés :

- modèle `OrchestrationState` sans besoin durable ;
- `MakoloOrchestrator` géant ;
- generic CRUD depuis le Resolver ;
- mapping automatique predicate -> field ;
- source récente = vraie ;
- Membership = authority ;
- Domain Event = notification ;
- Domain Event = commande externe ;
- Univers = Executor ;
- Dossier/Project = moteur de workflow ;
- Readiness dupliquée.

## 29. Tests

La suite Actor 5 couvre :

- contrat Resolver -> Orchestrator ;
- match identité -> no-op ;
- new candidate -> review sans création ;
- conflit -> aucune mutation ;
- owner non enregistré -> review ;
- Activity update owner-backed ;
- source authority explicite ;
- stale-resolution protection ;
- replay idempotent ;
- Profile/Space boundary ;
- Membership sans autorité ;
- predicate inconnu ;
- handoff via le port Actor 4.

Le workflow PostgreSQL exécute également `makemigrations --check --dry-run` :
Actor 5 ne crée aucune migration.

## 30. Critères de sortie

Actor 5 est fermé lorsque :

- le contrat Resolver -> décision applicative est exécutable ;
- les défauts sont non destructifs ;
- un owner route réel démontre la délégation sans ORM générique ;
- autorité/fraîcheur/provenance sont revalidées ;
- idempotence/replay sont testés ;
- aucune nouvelle table Actor 5 n'existe ;
- Projector/Univers/Executor/Presenter ne sont pas absorbés ;
- les chemins existants restent propriétaires de leurs règles ;
- tests/CI sont verts ;
- documentation = runtime ;
- `main` est vérifié après merge.

---

# Frontières vers les acteurs suivants

## Actor 6 — Persistateur

Actor 5 ne produit jamais `save_this_json`.

Une décision durable est exprimée comme une opération du domaine propriétaire,
par exemple `activity.update_common`. La persistance spécialisée demeure la
responsabilité de l'owner et du futur travail Actor 6.

## Actor 7 — Projecteur

Aucun Projecteur runtime n'est présent aujourd'hui. Lorsque son contrat existera,
il devra consommer des faits/événements canoniques, pas les objets internes de
l'Orchestrateur.

## Actor 8 — Univers Makolo

L'Univers calcule ; il n'autorise pas.

## Actor 10 — Exécutant

Le contrat M7 `interoperability.actions` est le point existant le plus proche
de cette frontière : capability, owner, authorization, Connection et
idempotency y sont explicites.

## Actor 11 — Présentateur

Actor 5 retourne des décisions et reason codes. Le Presenter choisit le langage,
HTTP, Web ou Flutter, dans les limites de divulgation autorisées.

---

# Train réellement retenu

Le train initial O0-O8 a été réduit après audit :

- **O0** audit runtime/collisions/contrats ;
- **O1** contrats Actor 5 + safe decision boundary ;
- **O2** premier owner routing Activity, provenance explicite, idempotence ;
- **O3** authority/freshness/privacy hardening dans cette frontière ;
- **O4** tests PostgreSQL + observabilité + operations ;
- **O5** fermeture et handoff Actor 6.

Les lots génériques Projecteur/Univers/Executor n'ont pas été implémentés sans
runtime correspondant. Les workflows utilisateur et event-driven déjà corrects
ne sont pas réécrits uniquement pour porter l'étiquette Actor 5.
