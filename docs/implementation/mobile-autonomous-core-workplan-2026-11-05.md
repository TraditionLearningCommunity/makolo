# Makolo Mobile — Refondation du noyau applicatif autonome

**Statut :** C0 audite ; C1-C6 implementes sur la PR #522 avec tests cibles ecrits. Verification Flutter/Android non executee dans cet environnement ; C7-C8 restent a faire.
**Date de cadrage :** 5 novembre 2026.
**Depot :** TraditionLearningCommunity/makolo.
**Branche unique d'execution :** `fix/discover-a-continuation-context-20261014` (PR #522).
**Baseline revalidee au cadrage :** `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f` ; `PR #522@0795ab65f538b289f2f8c86a3c92104a53c5cf79`.
**Perimetre des changements de ce chantier :** `mobile/**` et documentation explicitement liee. Aucun backend, API, migration Django ni Web.
**Nature des identifiants C0-C8 :** checkpoints internes de ce chantier, pas nouveau train LF, A, M ou programme officiel.

> Makolo marche pour vous. Meme lorsque le reseau ne marche pas.

## 1. Objectif et regle directrice

Le parcours normal est : **Owner distant -> acquisition coordonnee -> stockage local durable -> selectors/repositories locaux -> Flutter**.
Pour l'ecriture admise : **intention -> brouillon/operation locale durable -> transmission sous contrat owner -> reconciliation -> lecture locale reactualisee**.

Le reseau n'est pas une condition de construction de l'ecran. Le local n'est pas une nouvelle autorite metier. N'introduire ni cache par ecran, ni seconde source de verite, ni API, ni modele metier ni nouvelle table sans demonstration que l'existant ne couvre pas le besoin.

## 2. Baseline verifiee et travaux existants a reutiliser

- Le schema Drift v2 de `mobile/lib/data/local/makolo_database.dart` contient six tables : `ProjectionSnapshots`, `ResourceIndex`, `SyncSources`, `OutboxOperations`, `LocalDrafts`, `FileRecords`.
- Il existe deja `ProfileStore`, `SyncEngine`, `ProjectionSelector`, des repositories, la gestion d'outbox et des tests cibles.
- La PR #522 porte deja des changements local-first recents (Now, Discover, Moi, ressources, medias, outbox, revocations). Ne pas recommencer ou supprimer sans lecture du code courant.
- La PR #522 comporte aussi des changements non Flutter et est volumineuse. Geler tout ajout hors mobile dans ce chantier. Une revue de collision et de CI est obligatoire avant integration finale.
- Sources de conception a revalider sur le runtime : `docs/architecture/mobile-local-data-kernel.md`, `mobile-sync-continuity-kernel.md`, `mobile-action-continuity-kernel.md`, `mobile-par1d-parallel-feature-boundaries.md`, `mobile-a2-acceptance-matrix.md`, `mobile-api-contract.md`, `docs/architecture/makolo-domain-blueprint.md`, `AGENTS.md`, `docs/operations/agent-orchestration.md`, `docs/operations/ai-development-guardrails.md`.
- Aucun resultat Android ou verdict global de CI n'est atteste par ce document. Relever le HEAD et les gates a chaque checkpoint.

## 3. Regle de chaque tache

Chaque checkpoint doit posseder : owner, base SHA au moment de commencer, fichiers autorises/interdits, changement minimal, tests cibles, verification manuelle pertinente, resultat de CI et preuve de non-regression. Commits petits et tracables. Aucun checkpoint n'est termine sur la seule base du code ecrit. Mettre a jour ce document avec une preuve (SHA, commande/test, resultat, limites).

## 4. Checkpoints d'execution

### C0 — Stabiliser la baseline et les flux existants

**Responsable :** integrateur. **Dependance :** aucune.

- Rafraichir `main`, tete de #522, statut/CI, derniers commits, branches et PR en collision.
- Inventorier les chemins acquisition -> applier -> SQLite -> selector -> repository -> UI, ainsi que UI -> operation -> reconciliation.
- Classer les usages existants : reutilisable, mauvais niveau, manquant, doublon. Relever les dependances HTTP obligatoires dans les constructeurs/chargements de vues.
- Identifier le commit de l'APK Android teste lorsque cette preuve est disponible.
- Fixer les contracts et les fichiers partages avant parallele. **Ne pas entreprendre un audit general du backend.**

**Sortie :** matrice courte des responsabilites et collisions, baseline CI, premiere liste d'ecarts testables sans ajouter de code abstrait.

### C1 — Lecture locale durable et connaissance partagee

**Responsable :** developpeur A. **Dependance :** C0.

- Conserver Drift/ProfileStore ; verifier atomicite des appliers, isolation de Profil/acteur, migrations et compatibilite des anciennes donnees.
- Faire converger les identites/provenances partageables et les relations utiles dans l'index existant, si les owners publient des identites suffisantes.
- Etablir les queries/selectors locaux reactifs reutilisables (recherche sur corpus acquis, details, temporalite autorisee).
- Distinguer jamais acquis, connu vide, connu disponible, ancien presentable, expire, revocation explicite, echec de transport.
- Ne pas introduire `OccurrenceFactsIndex` ou `SourceMembership` sans cas de requete, proprietaire et test prouvant leur necessite.

**Sortie :** un fait acquis reutilisable par plusieurs contextes sans lecture HTTP pour la consultation ; tests Drift, migrations, deduplication, isolation et cold start.

### C2 — Acquisition coordonnee, incrémentale et reprenable

**Responsable :** developpeur A. **Dependance :** C1.

- Reorganiser l'existant `SyncEngine`, `SyncSource`, appliers et orchestration lifecycle ; une source represente un contrat owner, pas un ecran.
- Declenchements : lancement/reprise, contexte, connectivite, invalidation, priorite utile, refresh demande, travail en attente. Respecter les contraintes Android/iOS.
- Budgets : temps, octets, batterie, stockage, medias, nombre de sources ; backoff et reprise sans boucle agressive.
- Pagination : 10 puis 10 puis 40, accumulation et deduplication autorisees, provenance du scope, curseurs invalides, sans extrapoler une exhaustivite globale.
- Garantir atomisme et comportement des reponses tardives ; ne pas detruire l'observation partageable sur simple erreur reseau.

**Sortie :** acquisition demonstrablement independante de l'ouverture d'une vue ; tests sync, interruption, replay, pagination et rafraichissement.

### C3 — Continuite d'action, brouillons et operations

**Responsable :** developpeur B. **Dependance :** C0 puis contrat stable de C1 ; peut avancer en parallele de C2 sur fichiers disjoints.

- Reutiliser `LocalDrafts`, `OutboxOperations`, `DraftRepository`, `OutboxProcessor` et handlers existants ; ne pas creer un moteur concurrent.
- Classer chaque action : A locale ; B locale puis synchronisee ; C preparable et confirmee par owner ; D intrinsequement distante.
- Persistance des formulaires pendant saisie, fermeture, redemarrage, restauration ; etats transmission/reception/decision distincts.
- Politique de replay par owner : idempotence reelle, retries, reponse ambiguë, conflits, dependances, refus, revalidation.
- Cas de reference : creation d'Espace **brouillon toujours local** ; transmission differée uniquement si l'API owner fournit un replay sur. Sinon conserver l'intention en attente de verification/confirmation humaine sans POST aveugle.

**Sortie :** parcours creer/preparer/interrompre/reprendre/communiquer/reconcilier teste sans faux succes ni permission locale.

### C4 — Autorite, confidentialite, expiration et revocation

**Responsable :** integrateur avec A et B en revue. **Dependances :** C1-C3.

- Tester isolement des Profils, actor context Profile/Space, logout/login, ecriture sensible et traces.
- Distinguer droit observe, autorite effectivement revalidee et presence d'un Space connu. Membership/Assignment n'accordent aucune Permission ou Mandate.
- Revocation/refus explicite : retrait scoped des projections, capacites et secrets concernes ; empecher une reponse tardive de les reintroduire.
- Echec de transport : jamais une revocation implicite. Horloge, TTL, expiration et credentials sensibles sont contractuels.
- Pas de secrets dans des projections generiques, journaux, analytics ou exemples.

**Sortie :** tests d'actor switching, 403/revocation, no resurrection, expiration, protection des secrets et isolation.

### C5 — Cycle de vie, fichiers, medias et stockage

**Responsable :** developpeur A ; B en revue des brouillons. **Dependances :** C1, C2 et C4.

- Stabiliser cold start, fermeture forcee, reprise, interruption sync, quotas/retenue, nettoyage, croissance SQLite et pression stockage.
- Reutiliser les proprietaires existants de media et `FileRecords`; distinguer copie durable autorisee, cache recomposable, fichier explicitement conserve, credential protege.
- Ne jamais preacquerir massivement videos, fichiers prives ou credentials ; purger selon revocation/contrat.
- Verifier fenetres temporelles et comportements lorsque l'appareil change de fuseau ou d'horloge.

**Sortie :** tests ciblés de retention, reprise, nettoyage et scenarios OS ; aucune disparition arbitraire du travail utilisateur.

### C6 — Composition de toute l'application sur le noyau

**Responsable :** integrateur ; A pour lecture, B pour interactions. **Dependances :** C2-C5.

- Inventaire transversal : shell, Now, Discover, En cours, Moi, Passport, Historique, Journey/Requirement, Access/Jour J, Resources, Dossier/Project, Conversations, Notifications, Interests/Watches, Connections, Billing, Space/Nous/Metier et autres surfaces livrees.
- Chaque feature lit d'abord localement via son repository/selector ; le refresh distant ne remplace pas tout l'ecran lorsque la connaissance locale est consultable.
- Faire remonter au noyau les besoins de source ; supprimer les decisions reseau propres aux widgets si elles doublonnent le noyau.
- Representation discrète des etats d'action et des vraies limites d'autorite selon les contrats Behavior/Presentation. Aucun redesign general.

**Sortie :** matrice de couverture surface x lecture/interaction/erreur/reprise et parcours sans Internet apres acquisition.

### C7 — Contrat d'extension public aux futurs developpeurs Flutter

**Responsable :** integrateur, revue par A et B. **Dependances :** contrats C1-C4 stabilises ; demo apres C6.

Creer un guide versionne dans `docs/architecture/` (nom a verifier au moment du travail), avec **un exemple reel tiré d'une feature existante** et un test de conformite architectural, sans feature fictive. Le guide doit expliquer :

1. Identifier owner distant, scope de visibilite, source et payload autorise.
2. Declarer/brancher une `SyncSource` existante, son acquisition, son applier transactionnel et sa politique d'invalidation.
3. Inserer l'identite partageable dans les structures deja disponibles ; reutiliser snapshots/index existants.
4. Exposer un selector local et un repository pour la feature ; pas de GET obligatoire dans widget/route.
5. Pour ecriture, binder un brouillon et une operation au handler owner et a une politique de replay **explicitement prouvee**.
6. Fournir les etats de connaissance, de confirmation, d'expiration et de recovery corrects.
7. Brancher la feature dans son assembly et ses routes selon PAR-1D ; laisser au seul integrateur les hotspots globaux.
8. Ajouter tests local-first, isolation, reponse tardive, changement d'acteur, redemarrage et migrations si reellement necessaires.

**Sortie :** un developpeur futur peut ajouter une feature sans toucher au moteur central ni creer cache/outbox/scheduler paralleles ; exceptions documentees et revues.

### C8 — Acceptation systeme et Android reel

**Responsable :** QA + integrateur. **Dependances :** C6 et C7.

Demonstrations obligatoires :

1. Installation alimentee -> mode avion -> fermeture -> redemarrage -> consultation/navigation/recherche/preparation.
2. Brouillon -> interruption -> reprise -> intention -> envoi -> statut owner exact.
3. Acquisition progressive 10/10/40 ; provenance et deduplication.
4. Jour J : Access acquis, consignes/horaires ; credential seulement si autorise, aucun AccessUse invente.
5. Changement de Profil/Space : confidentialite et absence d'autorite deduite.
6. Reconnexion : operation rejouee selon politique, ack ≠ decision, doublons/conflits/refus.
7. Premiere installation sans reseau : shell accessible, connaissance inconnue, aucune fausse session.
8. Offline prolonge : temps, brouillons, outbox, coherence.
9. Revocation explicite : invalidation, pas de resurrection ; panne reseau sans fausse revocation.
10. Android reel : suspension, reprise, force-stop, stockage, batterie, reseau intermittent.

Mesures : cold start local, latence navigation/recherche, taille SQLite, latence sync, memoire, consommation raisonnable.

**Sortie :** evidence des dix scenarios, `flutter analyze`, tests cibles + suite pertinente, formatting canonique, CI pertinente verte, revue des diff ; merge uniquement si gates verts et reconciliation avec `main`.

## 5. Dependances et deux developpeurs sans creer de branche

~~~text
C0
  -> C1 -> C2 -----+
     \-> C3 -------+-> C4 -> C5 -> C6 -> C7 -> C8
~~~

Le schema donne l'ordre logique, pas un monolithe obligatoire. C3 peut commencer avec le contrat C1 stabilise, pendant C2.

- **A — Connaissance/acquisition :** `mobile/lib/data/local/**`, appliers et pull sous `mobile/lib/sync/**`, selectors communs. Ne touche pas aux outbox handlers tenus par B.
- **B — Continuite d'action :** brouillons, intents, outbox handlers owner, tests d'operations. Ne modifie pas le schema Drift ni `SyncEngine` sans validation de l'integrateur.
- **Integrateur unique :** `app/router.dart`, `app/providers.dart`, runtime builder, bootstrap, `pubspec.yaml`, `mobile/android/**`, schema Drift/migrations, signatures communes, CI, commits integres et push de la branche.
- **Une seule branche distante:** `fix/discover-a-continuation-context-20261014`. Deux espaces de travail peuvent etre crees en `git worktree --detach` sur le SHA approuve (sans nouvelle branche). Les contributeurs transmettent des commits SHAs ; l'integrateur les cherry-pick ou applique de facon controlee sur cette unique branche puis pousse. Personne ne force-push. Ne pas ecrire en parallele le meme fichier.
- Apres chaque integration : comparer HEAD/CI, tester le contrat touche et actualiser le checkpoint. Ne pas traiter #522 comme deja fusionnee.

## 6. Gate de qualite minimal

`cd mobile && bash tool/dart_format.sh write && bash tool/dart_format.sh check`, puis `flutter analyze`, tests cibles, tests d'architecture et suites pertinentes. Outils canoniques dans `AGENTS.md` (Flutter 3.47.3 / Dart 3.13.3). Aucun test affaibli, pas de faux succes et pas de nouveau serveur/API/Web dans ce chantier.

## 7. Etat de suivi

| Checkpoint | Etat initial | Preuve requise |
|---|---|---|
| C0 Baseline | Audit et cartographie realises | HEADs, collisions et matrice ci-dessous |
| C1 Connaissance | Code et tests ajoutes, execution non attestee | Recherche indexee owner-backed, profils, expirations, detail |
| C2 Acquisition | Code et tests ajoutes, execution non attestee | Working set, 10/10/40, erreurs, invalidation, reconnect |
| C3 Actions | Code et tests ajoutes, execution non attestee | Drafts durables, outbox, bail, refus, recovery, Space/Questionnaires |
| C4 Autorite | Code et tests ajoutes, execution non attestee | Profils, Space/Access 403/404, tombstones, actor, QR, expiration, outbox |
| C5 Cycle de vie | Code et tests ajoutes, execution non attestee | Stage/download durable, cache borne, maintenance, crash et horloge |
| C6 Composition | Code raccorde, matrice couverte, execution non attestee | Runtime unique, lectures locales, acquisition borne, Me, Notifications, Nous/Mark, erreurs et reprises |
| C7 Extensibilite | A faire | guide + exemple reel + tests |
| C8 Android/fermeture | A faire | 10 scenarios + CI verte |

**Regle de fermeture globale :** le noyau est reutilisable par une nouvelle fonctionnalite sans que celle-ci doive reconstruire persistance, acquisition, lecture, brouillons, retries ni reconciliation. Les limites distantes demeurent explicites et legitimes.


---

## 8. Compte rendu d'execution C0-C2 — 5 novembre 2026

### C0 — Diagnostic du runtime et decision d'architecture

**Baseline observee au lancement :** `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f` ; `#522@1084370bd82947a59a80a1a796365a90c67d22c8`. La PR #522 etait ouverte/non fusionnee. La PR empilee #533 est fermee sans merge ; #527 a ete fusionnee dans #522 ; #528 est fermee sans merge. Ces statuts ne constituent pas de nouvelles branches de ce travail. Ne pas figer le HEAD au-dela du jour de la verification.

**Flux identifies dans le code :**

| Famille | Lecture existante | Acquisition existante | Constat initial |
| --- | --- | --- | --- |
| Now / En cours / Moi | `PersonalRepository.watchNow/watchOngoing/watchMe` -> `ProfileStore.watchProjection` | racines `SyncEngine.refreshRoots` | deja locales, acquisition de trois racines au lancement |
| Discover | `DiscoveryRepository.watchItems` -> snapshots `discovery.items` par fingerprint -> selector | `itemsSource`/`refreshItems`, souvent initie par la surface | collections deja persistantes mais preacquisition de champ insuffisante |
| Access / Resources / History | repositories owners -> snapshots collections et details | source page/detail owner, acquisition a l'ouverture | details et collections reutilisables mais absence de priorite de working set |
| Conversations / Notifications | repositories owners -> snapshots collections | `listSource` / `refreshList` | owner sources definies mais chargement initie par leur destination |
| Space / agir comme | `WorkspaceContextRepository` -> projection inventory + contexte acteur | `inventorySource`/`refreshInventory` | inventaire connu non prepare systematiquement au lancement personnel |
| Actions | `DraftRepository`, `OutboxOperations`, handlers owner | transmission et reconciliation selon type | conserve pour C3, non refondu ici |

**Causes communes confirmees :** (1) sources owner disponibles mais pas orchestrees dans un working set au lancement ; (2) index `ResourceIndex` defini dans Drift mais encore peu exploite en lecture transversale ; (3) acquisition encore en partie initiee par navigation et cycle de vie d'ecrans ; (4) distinguo transport, source revokee et revalidation a proteger dans la politique proactive.

**Decisions :** Drift v2 et les six tables conserves ; aucune migration locale ni Django ; pas de nouveau scheduler ; pas de `SourceMembership` ou de facts index generique sans cas d'usage verifie ; snapshots owners restent uniques ; C3 (mutations) et C6 (composition de toutes les vues) ne sont pas absorbes artificiellement par C1/C2.

### C1 — Noyau de lecture et identite de ressources

**Code pousse :**

- `mobile/lib/data/local/profile_store.dart` : `IndexedResource`, `putResourceReference`, `readKnownResources`, `watchKnownResources`.
- L'index se joint obligatoirement au snapshot owner encore present et non expire. Une ligne d'index orpheline ne rend jamais une ressource consultable ; aucun champ Permission/Access/Readiness invente.
- `mobile/lib/sync/sync_source.dart` : opt-in explicite `indexedResourceKind` pour des details owners **personnels et identifies**, ecriture de projection + index dans la transaction de `SyncEngine`, controle du champ `id` lorsqu'il est presente par l'owner.
- Sources effectivement branchees : Activity, Occurrence, PersonalAsset et Access. Aucun contenu de credential ou document n'est recopie dans l'index : identite, label simple si publie, type et pointeur seulement.
- Les snapshots de collections Discovery restent distincts des details indexes. Ils ne sont pas arbitrairement convertis en une nouvelle verite ou collection exhaustive.
- `mobile/test/local_database_test.dart` et `mobile/test/sync_engine_test.dart` : isolation Profile, disparition/expiration de projection, index apres acquisition, rejet d'une identite owner divergente.

**Statut :** code et tests cibles integres sur #522 ; verification par execution de Dart/Flutter et Android non attestee ici. Aucune nouvelle version de schema Drift.

### C2 — Working set d'acquisition coordonnee

**Code pousse :**

- `SyncEngine.registerPreparedSource` permet au runtime de declarer des sources owner stables, sans dependance aux widgets. Les continuation URLs signees et les scopes Space non verifies sont exclus de ce registre.
- `SyncEngine.refreshPreparedSources` prepare un maximum de **sept** sources par cycle. Sa priorite est l'ordre d'enregistrement ; les donnees sont appliquees via les parsers/appliers owners deja en production, et la lecture se fait depuis la base.
- Quand un owner possede des traitements apres acquisition, le registre prend un executant de repository, plutot que de contourner son contrat : `DiscoveryRepository.refreshItems` conserve previews/fenetres et `WorkspaceContextRepository.refreshInventory` revalide le contexte acteur. Le moteur relit le statut durable, car certains repositories absorbent eux-memes les erreurs de transport.
- Sources actuellements declarees par `runtime_builder.dart`, dans cet ordre : inventaire Space pour le Profile, Discover premiere page sans criteres, Access beneficiary premiere page, Resources personnels premiere page, Conversations liste, Notifications inbox, History premiere page.
- Les racines Now, En cours, Moi et Interoperability restent dans `refreshRoots` ; elles ne sont pas dupliquees dans la nouvelle liste.
- Fraicheur durable lue dans `SyncSources.lastSuccessAt` et snapshots. Une source recente n'est pas redechargee a chaque ouverture ; une source absente/expiree ou explicitement invalidee est eligibile. Delai memoire de protection contre les rafales ; reconnexion le reinitialise.
- Un refus owner explicite 403/404 retire sa representation suivant le contrat existant et n'est pas rejoue en boucle. Une invalidation explicite nettoie l'erreur pour permettre revalidation legitime. Un echec de transport preserve les donnees locales et arrete le lot.
- `SyncLifecycle` pilote le working set sur lancement, reprise, retour reseau et changement du contexte acteur ; les widgets ne sont plus les seuls initiateurs.
- Tests nouveaux dans `sync_engine_test.dart` : acquisition des pages 10 + 10 + 40 par cycles bornes, scope Profile, pas de rechargement intempestif des sources fraiches, refus owner suivi d'une revalidation legitime, echec de transport remonte par executant owner et blocage d'un cursor signe rejoue comme source stable.

**Statut :** noyau et integration au cycle Flutter ecrits/pousses. Ces tests ne sont pas des resultats d'execution. Aucun travail Workmanager permanent ni acquisition illimitee n'est promis.

### Frontieres et suites

- C1 ne pretend pas avoir normalise tous les items de toutes les collections. Les fingerprints Discovery conservent leur signification de resultats owner contextuels ; l'index partage couvre ici les details owners avec identite stable.
- C2 prepare un working set borne, non l'univers Makolo exhaustif. Les donnees jamais acquises demeurent inconnues. Les cursors pagines supplementaires doivent rester controles par les contrats owners (et par le futur travail de consolidation des collections si besoin).
- C3 implemente la persistance et la transmission selon les contrats owner existants ; C4 devra encore auditer les permissions/revocations, C5 fichiers/media, C6 l'harmonisation de toutes les experiences, C7 le guide d'extension, C8 les parcours Android.
- **Validation non attestee dans l'environnement d'execution actuel :** Dart/Flutter SDK absent ; `dart_format.sh`, `flutter analyze`, tests cibles et tests Android n'ont pas ete executes. Une revue statique des sources a ete realisee ; elle ne remplace pas le compilateur. Le souhait de ne pas bloquer sur la CI globale est respecte, mais aucune gate rouge ne doit etre decrite comme verte.


---

## 9. Compte rendu d'execution C3 — Continuite d'action, 5 novembre 2026

### Baseline et collision

Debut C3 : `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f` et `#522@07d7624863e5c1dccc75a17bd37fec01f44a890b`. La PR #522 etait ouverte. Depuis la fin de C2, 25 commits avaient ete apportes a #522, dont Conversations, Discovery et leurs tests. Les travaux C3 restent dans les chemins Flutter ci-dessous et le present suivi ; ils ne changent aucun endpoint, API Django, modele de domaine ni migration.

### Classes d'intentions : qui peut faire quoi ?

| Classe | Experience | Propriete |
| --- | --- | --- |
| A — Purement locale | Saisie d'un questionnaire, preparation du nom et de la visibilite d'un futur Espace | Brouillon sur l'appareil ; aucune mutation ni autorite distante |
| B — Intention explicitement rejouable | Operation couverte par un owner avec idempotence ou innocuite prouvee ; politique `idempotent`/`safe` | Replay automatique autorise uniquement sous ce contrat ; meme intent/idempotency key |
| C — Preparable, decision owner | Soumission de Questionnaire avec `refetch-before-retry`, creation d'Espace via POST manuel | Relecture/reconciliation avant toute reprise ambiguë ; jamais de succes local presume |
| D — Intrinsequement distante | Paiement, usage d'Access, verification de QR, mutation exigeant autorite en temps reel | Aucune activation/revalidation offline par simple projection ; aucun outbox generique invente |

La presence d'un draft, d'un intent ou d'un cache ne vaut jamais autorisation, Readiness, Permission, Mandate, Payment ou Access.

### Noyau commun : changements effectifs

- `mobile/lib/sync/outbox/outbox_repository.dart` : enregistrement transactionnel avec dedup par `profile_id + intent_id`, identite operationnelle immuable ; bail d'execution SQLite `next_retry_at` de deux minutes ; tentative revendiquee par compare-and-swap sur etat/attempts/lease ; retry temporaire avec backoff 10 s -> 300 s ; erreurs permanentes exclues du replay automatique ; annulation uniquement des intentions encore `queued` avec zero tentative ; status de dependances et instant du prochain retry lisibles par le cycle applicatif.
- `mobile/lib/sync/outbox/outbox_processor.dart` : refus owner definitifs en conflit, authentification requise en attente, transport incertain traite selon la politique, `unknown policy` sans dispatch ; lien optionnel handler -> owner verifie avant execution ; dependance temporairement en echec bloquante mais non conflictuelle ; jamais de reconfirmation locale sans observation owner.
- Une operation `refetch-before-retry` demeure soumise a son reconciler ; une operation `no-blind-retry` deja envoyee ne repart pas automatiquement. Un handler absent n'est pas remplace par un POST generique.
- `mobile/lib/repositories/draft_repository.dart` : isolation stricte profil/owner/ressource, transaction `saveAndQueue` (brouillon et intention ensemble, rollback si echec), payload local distinct du payload de l'operation, garde optionnelle de single active intent. Draft/Outbox doivent partager la meme connexion SQLite et le meme Profil.
- `mobile/lib/app/sync_lifecycle.dart` : reutilisation du lifecycle Flutter pour re-armer les retries durables pendant l'execution au premier plan. Android peut suspendre les timers ; au resume/reconnect, les timestamps SQLite restent l'autorite de scheduling. Pas de second daemon, ni de promesse d'heure exacte en arriere-plan. Une fois les roots owners authentifies avec succes, seules les intentions 401 suspendues de politique `safe`/`idempotent` sont relancees ; `no-blind-retry` reste suspendue, et `refetch-before-retry` revalide son owner.

### Cas owner 1 — Questionnaires

- `QuestionnaireSubmitCoordinator.enqueue` utilise la transaction `DraftRepository.saveAndQueue`. Les reponses du brouillon et les liens owner du message sortant sont volontairement distincts ; seule la seconde partie constitue une intention envoyable.
- Le handler est lie explicitement a `Questionnaires` **et** a la politique `refetch-before-retry`, revalidee par l'OutboxProcessor avant tout dispatch. La recuperation apres interruption continue de consulter le detail owner et ne renvoie pas aveuglement la soumission. Une alteration locale vers `safe` est refusee.
- Les chemins d'API mis en outbox doivent etre relatifs et sous `api/v1/`, pas des destinations externes arbitraires.
- `QuestionnaireFormScreen` serialize l'autosave avec l'enqueue, desactive l'edition pendant commit/attente, et n'ecrit plus un brouillon tardif apres une soumission confirmee. Une intention en echec de transport avec retry programme reste active : aucune deuxieme soumission n'est proposee ; le message UX explique que la meme intention sera retentee. Les erreurs de validation owner conservent les reponses editables.

### Cas owner 2 — Creation d'Espace

- `SpaceCreateScreen` persiste `name`, `public_profile` et un `submission_state` dans `LocalDrafts` sous Organizations / `space.creation`.
- **Avant le POST**, l'etat est `verification_required` et doit etre durablement ecrit ; si ce stockage echoue, le POST n'est pas tente. Une erreur de transport ne rend pas cette demande rejouable.
- **Apres reponse du POST**, le draft peut contenir `created_space_id` et `created_space_slug` sous `created_unverified` pour permettre de reprendre la verification du droit.
- La fermeture/reouverture relit ces donnees, evite un second POST aveugle et propose la verification de l'inventaire et du workspace. Si l'identite de l'Espace n'a pas ete recue, la reprise du brouillon demande une confirmation humaine explicite apres consultation des Espaces ; elle ne declenche pas de POST automatique. Une identite retournee par POST ne confere ni membership ni autorite.
- La suppression du draft intervient apres confirmation des lectures owners et selection explicite de l'acteur ; un echec de nettoyage local ne retire pas une autorite deja verifiee.
- **Pas d'operation Space.create en outbox** tant que l'API Organizations ne garantit pas une idempotence/reconciliation fiable. Aucun nouvel endpoint ni faux Space local n'a ete cree.

### Tests ajoutes ou ajustes

- `mobile/test/local_database_test.dart` : profil et owner pour les brouillons, rollback d'enqueue, dedup d'intent, single active form.
- `mobile/test/outbox_processor_test.dart` : lease durable et reprise, owner 403, backoff/replay meme intent, politiques inconnues, owner mismatch, refus permanent, annulation seulement avant dispatch, reauthentification 401 et blocage d'un deuxieme intent tant qu'un retry est prevu.
- `mobile/test/lf5_outbox_reconciliation_test.dart` : simulated crash avec lease echue, dependance en attente d'un prerequis temporairement indisponible.
- `mobile/test/space_creation_draft_test.dart` : brouillon Space conserve apres reentree, incertitude avant reconciliation sans nouveau POST, confirmation humaine obligatoire pour reouvrir l'intention, retour owner cree mais autorite non encore verifiee.

### Limites et conditions de fermeture

- **Les tests sont ecrits et pousses, mais non executes dans cette session** : le SDK Dart/Flutter n'est pas accessible au runtime local ; compilation, formatage et tests Android restent a valider. Une lecture statique n'est pas un resultat de test.
- Le bail protege les processeurs concurrents jusqu'a son expiration. Comme tout bail sans heartbeat, il ne prouve pas « exactement une execution » si un handler reste actif au-dela ; les operations rejouables doivent conserver leur contrat owner d'idempotence, et les autres passent par reconciliation ou attente.
- La creation d'Espace refuse volontairement le POST automatique en cas de reponse incertaine. Un futur contrat serveur prouve peut etendre ce cas, pas l'inverse.
- Le cycle de vie Android au premier plan n'est pas Workmanager : les travaux C5/C8 doivent verifier les suspensions et redemarrages reels avant toute affirmation de scheduling garanti.
- Le dernier HEAD de #522 et le statut des autres PR doivent etre reverifies au prochain checkpoint. Aucune integration vers `main` ou merge n'a ete effectue.


---

## 10. Compte rendu d'execution C4 — Autorite, confidentialite, expiration, revocation (5 novembre 2026)

### Baseline, frontieres et collision

Au debut de C4, le HEAD verifie de `main` etait `d0f0ec421c94c255fa4c0acd3509938a70c6322f`, celui de la PR #522 etait `3045c61c409e32068969df9aa5be13536d523fbe`. Les changements C4 ont ete apportes directement a la branche `fix/discover-a-continuation-context-20261014`. Aucun nouveau train, schema métier, endpoint Django, migration Drift ou branche ne sont introduits.

La verification de fin de travail a releve un commit concurrent dans `mobile/lib/features/continuity/conversation_screens.dart`, sans conflit apparent avec les fichiers propres a C4. Ce fichier ne fait pas partie des modifications C4 effectuees ici.

**Regle directrice :** Presence d'un Profile, d'un Space, d'un Assignment, d'une collection Access ou d'un brouillon n'est pas une autorite. Le proprietaire valide les actes, le mobile ne fait que retenir une observation privee, son contexte et sa fraicheur. Revoquer un droit est different de perdre le reseau.

### 10.1 Frontiere Profile et changement d'acteur

- `ProfilePaths.safeProfileId` est desormais la cle canonique unique des chemins privees (SQLite, media, staging, ressources). `MakoloDatabase.profileDirectoryKey` la reutilise. Les identifiants canoniques composes de lettres/chiffres/tirets/underscores conservent leur ancien chemin ; les autres utilisent un encodage reversible sans collision, contrairement a la substitution avec perte. Les identifiants d'assets passent par la meme regle dans le stockage local.
- Une copie locale ancienne sous un chemin non canonique avec collisions potentielles **n'est pas copiee automatiquement** : seule une migration auditée avec preuve d'appartenance serait acceptable. Les identifiants habituels déjà conformes restent a leur chemin courant.
- `AccessRepository` refuse une combinaison `ProfileStore` / `SyncEngine` / base ne correspondant pas au `profileId`.
- `OutboxProcessor` accepte un `canDispatch` controlant le Profil authentifie avant reconciliation et juste apres claim et avant handler. `QuestionnaireAssembly` raccorde ce gate au `TokenStore.readSession`; `QuestionnaireSubmitCoordinator` reverifie la session avant enregistrement/soumission owner et reconciliation.
- Une intention bloque par changement de Profil reste dans l'outbox du bon Profil, pas rejouee sous le nouveau. Une fois les owner roots autentifies de nouveau pour le bon Profil, seules les operations effectivement `safe` / `idempotent` peuvent etre relachees. Les politiques sans replay aveugle restent soumises a reconciliation.
- `WorkspaceContextRepository` n'alterera pas le contexte acteur si le `SyncEngine` du runtime ancien a ete desactive. Les preferences d'acteur ne conferent pas d'autorite.

### 10.2 Retrait scoped Space

- `SyncEngine` possede des epochs en memoire lies au Profil et au Space (partagees entre engines du meme objet SQLite). Elles font tomber les anciennes reponses en vol apres un retrait owner.
- Un 403/404 sur `space.workspace` est la perte de l'entree d'autorite de ce Space : projections `space.*` et operationales `space.occurrence.*` du Space cible retirees, sources correspondantes invalidees, inventaire local redige, contexte acteur retourne a Personnel si ce Space etait selectionne.
- Un refus de la liste `space.inventory` retire toutes les vues Space du Profil et l'acteur Space selectionne. Un refus de `space.pilot`, `space.now` ou d'une perspective seule ne devient pas une revocation transversale des autres espaces ou modules.
- La relecture de l'inventaire authoritative sait identifier un Space present auparavant puis absent et appliquer le meme retrait scoped. Une reponse d'inventaire 200 ne peut pas reinserer une identite `space.workspace` qui porte toujours un tombstone 403/404.
- Ni une invalidation douce, ni un timeout ni un 500 n'effacent un refus owner. Les lectures de Space restent bloquees tant qu'une revalidation legitime de l'owner Workspace/inventory n'a pas resolu le tombstone. Les autres Espaces et les donnees des autres Profils restent intacts.
- Le travail personnel de l'utilisateur (brouillons/outbox) n'est pas efface par une revocation d'une projection Space.

### 10.3 Retrait scoped Access et QR

- Un 403/404 sur `personal.access.detail` retire ce detail et son Access de toutes les collections actuellement reutilisees ; un nouvel arrivage de collection est filtre par les refus keyed-owner durables. Le QR correspondant est retire du coffre protege (independamment du blocage SQLite qui reste decisif).
- Un refus de collection `beneficiary` retire cette famille et invalide la presentation des credentials beneficiaires ; un refus de `purchased_for_other` ne revoque pas les beneficiaires independants.
- Un `AccessCredential` ne peut pas etre ecrit comme `personal.access.credential` dans `ProfileStore.putProjection`. Aucun QR, token ou payload secret n'est ajoute a `ResourceIndex`, Analytics, aux journaux ou aux fixtures.
- `AccessRepository` revalide la frontiere de Profil, utilise des identifiants URL-encodes, et refuse le resultat d'un appel credential surclasse par une autre reponse owner 403/404, meme provenant d'un second repository de la meme base.
- `readRetainedCredential` reconsulte les tombstones apres une lecture asynchrone du coffre ; un 403 arrive pendant l'acces a Keystore/Keychain empêche de retourner le secret.
- Une presentation QR offline est seulement *display-only*, jamais preuve d'AccessUse. Le coffre verifie desormais `checkedAt <= maintenant < expiresAt`, avec un intervalle owner correctement ordonne. Une horloge incoherente ou une fin de validite rend la representation inutilisable. Le secret reste hors des projections Drift generiques.

### 10.4 Tests cibles ecrits

- `mobile/test/space_repository_test.dart` : 403 workspace scoped, purge du selected actor et des vues operationnelles, autre Space preserve, reponse tardive ignoree, inventaire mis a jour sans resurrection, suppression owner de l'inventaire, refus global et isolation Profile, timeout/503 apres retrait, runtime ferme ne changeant plus l'acteur.
- `mobile/test/c4_access_scope_test.dart` : 403 Access individuel, redaction de liste actuelle et de liste arrivee tardivement, refus durable meme sur 503, refus de collection acheteur sans perte de la collection beneficiaire.
- `mobile/test/access_offline_qr_test.dart` : un 403 sur un repository invalide une reponse QR en vol sur un autre, verifications de fenetres temporelles, mauvais Profile refuse, lecture de coffre interrompue par une revocation.
- `mobile/test/local_database_test.dart` : profils non collisionnants dans SQLite et ProfilePaths, chemin canonique preserve, AccessCredential interdit en projection generique.
- `mobile/test/outbox_processor_test.dart` : changement de Profil avant dispatch et entre le claim et le handler ; une intention `safe` ne repart qu'apres re-authentification legitime.

### 10.5 Limites de verification

Les changements ci-dessus sont codes, pousses et relus statiquement ; ils ne sont **pas declares testes par execution**. Le SDK Dart/Flutter n'est pas disponible dans le runtime local de cette session et les tests widget/SQLite/Android restent a executer. La CI globale n'est pas un prerequis a la poursuite de #522 conformement a la demande, mais cette absence de gate ne constitue pas un succes de validation, ni une autorisation de merger en rouge.

Le modele n'invente pas de permission dans Drift. L'owner serveur doit toujours imposer les autorisations reellement en vigueur. Les verifications C5-C8 couvriront notamment suspension OS, stockage/médias, composition de toutes les surfaces et parcours Android.

---

## 11. Execution C5 — Cycle de vie, fichiers, medias, stockage (5 novembre 2026)

**Baseline verifiee :** `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f` ; `#522@e821151ad68808e5834bab368cde523a0f28757a` au demarrage C5. Branche unique `fix/discover-a-continuation-context-20261014`. Perimetre des modifications C5 : Flutter `mobile/**` et present plan, sans modification d'API backend, domaine metier ou migration Drift v2.

### Conservation des fichiers et reprise

- `ProfileFileStore.stageCopy` ecrit dans un fragment `.part`, verifie qu'il existe et contient des octets avant son renommage, puis insere le `FileRecord`. Un echec ne publie jamais un fichier partiel. Le chemin physique emploie `stage-<nonce>` plutot qu'un nom utilisateur ou une representation potentiellement sensible.
- Le `fileId` est immuable : un ID deja enregistre n'est jamais reimporte par un upsert qui ecraserait un autre Profile ou une capture encore necessaire.
- `promoteToPrivate` copie dans un fragment prive, renomme, met a jour `FileRecords` avec condition sur le chemin original puis supprime seulement ensuite la copie staging. Un crash peut laisser un doublon temporaire, pas supprimer la derniere copie. La promotion deja achevee est idempotente.
- `FileDownloadCoordinator` reprend un telechargement entierement stage avec le meme owner, purpose et sensitivity sans refaire un download. Un owner different ne peut pas se servir du meme fileId.
- `ProfileFileStore.read` refuse une entree FileRecord dont le chemin sort des dossiers du Profile.

### Nettoyage prudent et pression de stockage

- `cleanupStaging` respecte l'accord explicite du caller `canRemove` mais conserve le fichier s'il est encore reference par un `LocalDraft` ou une `OutboxOperation` non resolue. Un payload illisible ne constitue jamais une preuve d'absence de dependance.
- `cleanupInterruptedStaging` et `cleanupInterruptedPrivateCopies` retirent seulement les fragments/copies physiques `stage-*` non enregistres dans FileRecords et vieux d'au moins un jour. Les fichiers suivis, copies volontairement conservees et documents de l'utilisateur ne sont pas nettoyes.
- `ProfileStore.purgeExpiredProjections` supprime les snapshots expires et les pointeurs `ResourceIndex` orphelins dans une meme transaction SQLite par Profile. Il ne touche pas les brouillons, l'outbox ou les ressources d'un autre Profile.
- **Ne pas appliquer de quota aux octets personnels durables** sans contrat owner. En particulier, copie explicitement demandee, Reader retenu et fichier servant une demarche ne sont pas un cache evictable.

### Cache reconstructible et images publiees

- `ProfileMediaCache` serialise acquisition/purge par repertoire : deux requetes concurrentes sur le meme objet ne provoquent pas deux telechargements ; une purge ne peut pas etre annulee par une ancienne ecriture encore en vol.
- Le media n'apparait comme cache valide qu'apres un download complet, non vide et dans la limite de taille. Les fichiers `.part` abandonnes et fichiers invalides sont nettoyes de maniere bornee ; les bytes de FileRecords ne sont jamais touches.
- Budget **technique de cache uniquement** : au plus 60 fichiers, 128 Mio pour le dossier, 20 Mio par objet. Le hash du nom passe de 32 a 64 bits, sans devenir une preuve d'integrite ni une autorite metier.
- `ProfileRecognitionImageStore` protege la copie precedente par backup durant une mise a jour ; `remove/purge` attendent les sauvegardes en cours pour eviter une resurrection apres un retrait owner. Il rejette les chemins non publies et peut restaurer la copie precedente lors d'un restart apres crash d'une operation de remplacement.
- Aucune preacquisition de videos massives, documents prives, fichiers QR ou AccessCredentials n'est ajoutee.

### Cycle de vie, horloge, OS

- `SyncLifecycle` conserve son orchestrateur existant. Au lancement/reprise du Profile (au plus une fois toutes les six heures sous horloge normale), il entretient les projections expirees, les fragments orphelins, le cache media et les backups de recognition, avec des erreurs d'entretien non bloquantes pour la connaissance locale.
- `FreshnessPolicy` ne classe plus une observation future comme `fresh` en cas de recul de l'horloge : elle demande une revalidation pour les faits sensibles, ou recommande le refresh pour les donnees ordinaires.
- `SyncEngine.refreshPreparedSources` revalide une `lastSuccessAt` future et ne laisse plus un delai memoire lui aussi situe dans le futur bloquer l'acquisition jusqu'au rattrapage de l'horloge. Les dates restent normalisees en UTC.
- Pas de Workmanager, daemon, garantie d'heure d'execution Android, ni de second orchestrateur de synchronisation. Les maintenances reprendront lors des cycles au premier plan.

### Couverture cible ecrite

- `profile_file_cleanup_test.dart` : protection drafts/outbox, IDs duplicatifs inter-Profiles, interruption de capture, vieux orphelins vs stage suivi et promotion idempotente.
- `file_transfer_continuity_test.dart` : reprise d'un download sans transport et fermeture/reouverture d'une **vraie SQLite** avec FileRecord, bytes, draft, operation.
- `file_media_core_test.dart` : meme media demande simultanement, erreur laissant un fragment, purge durant acquisition, limite de 60 fichiers.
- `profile_recognition_image_store_test.dart` : backup de media publie apres interruption, purge serialisee, verification des chemins autorises.
- `local_database_test.dart` : compactage des pointeurs Index seulement apres disparition de la projection owner, sans perte de brouillon ni de donnees d'autre Profile.
- `freshness_test.dart` : fuseaux horaires et horloge reculee.
- `sync_engine_test.dart` : une observation durable dans le futur n'empeche pas la reprise de l'acquisition.

### Sortie et limites

**Implementation et tests pousses dans #522 ; tests non executes dans cet environnement.** Le SDK Dart/Flutter et un Android reel/emule n'y sont pas disponibles. Le formatage officiel, `flutter analyze`, les tests cibles et les parcours OS devront etre executes pour une validation prouvee. L'absence de blocage par la CI globale ne signifie pas que les gates soient vertes.

Les politiques metier continuent d'appartenir aux owners ; cette maintenance ne decide jamais un AccessUse, une Permission, une Proof ni une satisfaction de Requirement. C6 (composition des vues), C7 (guide d'extension) et C8 (verification Android) restent distincts.


---

## 12. C6 — Composition de l'application sur le noyau autonome (5 novembre 2026)

### 12.1 Etat de base, proprietaires et collision

Avant C6 : `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f`, `#522@a58416ccbee0d8a0811c7fa134ae540c131481fb` (PR ouverte). Seule la branche existante `fix/discover-a-continuation-context-20261014` a ete modifiee. Le collision audit des autres PR ouvertes n'en a trouve aucune autre a cette date ; des changements Discovery ont ete observes simultanement **dans la meme PR**, conserves sans les ecraser. Reconciliation des fichiers centraux par blob SHA au moment des ecritures. Pas de nouveau serveur, API, migration Drift, modele metier ni train concurrent.

**Une seule composition :**
- `AppRuntime` assemble les objets Profile-scoped et les repositories ; `runtime_builder.dart` est le point de composition.
- `ProfileStore`/Drift et les selectors existants sont la source de lecture locale ; `SyncEngine` applique les observations des owners. `SyncLifecycle` reste l'unique orchestration foreground/resume/reconnect.
- `DraftRepository` + `OutboxRepository` + **un** `OutboxProcessor` portent les intentions explicitement rejouables. Questionnaires et Conversations y branchent leurs handlers, sans creer de queue par ecran. Les autres mutations conservent leur politique owner prouvee.
- Fichiers : `FileRecords` et les coordinateurs C5, avec cache reconstructible borne distinct des pieces durables. `Presentation` presente des faits sans les posseder.
- Donnees de lecture ≠ autorite de mutation : Permission, Mandate, AccessCredential, Payment, Proof, Requirement et Readiness continuent d'etre verifies par leur owner, meme si la derniere observation est disponible localement.

### 12.2 Changement de code C6 — sans seconde infrastructure

1. `AppRuntime.notifications` est construit une seule fois dans `runtime_builder.dart`, reutilise par `notification_routes.dart` pour Inbox et Preferences. La construction opportuniste d'un nouveau `NotificationRepository` dans chaque route est supprimee et le repository impose l'identite ProfileStore/SyncEngine.
2. `SyncEngine.refreshPersonalMe()` reemploie sa **source canonique** `personal.me` avec controles de profil, revocation et versions. Les mutations confirmees de `MeProfileScreen`, `MeConsiderationsScreen` et `MeSavedScreen` passent par ce meme refresh lorsqu'elles sont composees depuis `me_routes.dart`. Les chemins d'injection historique ne sont maintenus que pour les environnements isoles sans SyncEngine ; ils n'operent pas en double dans la vraie application.
3. `ObjectiveRepository` reste proprietaire des collections Project/Dossier ; seules ses **premieres pages** rejoignent l'ensemble prepare deja existant. `SyncLifecycle` a un budget de neuf demandes pour neuf sources personnelles bornees au lancement, pas de crawl et pas de pages secondaires preacquises. Les details restent demandes par contexte d'action.
4. `SpaceWorkCollectionScreen` restaure d'abord la projection `space.work` de la perspective active, a condition de respecter Space ID, responsibility, TTL et absence de retrait owner. La page detaillee reste un GET de continuation explicitement autorise, qui reconcilie les elements sans effacer l'observation locale en cas de 503. Aucun nouveau cache pour les collections Metier.
5. `SpaceDocumentsScreen` conserve **en memoire dans la session courante uniquement** les documents deja affiches pendant une panne transitoire ; le droit de gestion cesse d'etre propose jusqu'a revalidation. 401/403/404 et changement d'acteur retirent les anciennes lignes. Les documents confidentiels ne sont pas verses dans une projection SQLite generique non couverte par une politique owner offline explicite.
6. `MarkScreen` rebind son repository, ses captures et sa lecture de brouillon au runtime/acteur actifs. Les revisions de contexte empechent une restauration asynchrone, une selection fichier ou un resultat de soumission de l'ancien Profil de rejaillir dans la nouvelle session. Le Mark reutilise les brouillons et FileRecords existants, pas une deuxieme queue.

### 12.3 Matrice de couverture : surface × lecture / interaction / erreur / reprise

Legende : **L** = projection/selector local; **M** = Memoire locale ephemere d'une session; **O** = action/le moment critique reste sous verification owner online; **P** = public/visiteur, sans privilege personnel. La colonne « etat C6 » distingue reemploi confirme, correction C6 et limite volontaire ; ce n'est **pas** une certification par tests executables.

| Surface Flutter / contexte | Lecture et source de verite | Interactions | Panne / autorite | Reprise et etat C6 |
| --- | --- | --- | --- | --- |
| Splash / onboarding / authentification | Preferences appareil et TokenStore existants ; aucune projection inventee | Sessions/compte par Auth owner | Sans session, pas de lecture du Profile precedent | Runtime reconstruit selon session ; **reemploi** |
| Shell personnel, navigation, selection acteur | AppRuntime, ActorContextController et routes existantes | Preference locale d'acteur, non Mandate | Retrait Space revient a Personnel ; pas d'acces implicite | Etat de navigation deja persiste ; **reemploi** |
| Now / Accueil | personal.now, PersonalRepository.watchNow, NowSelector | Handoff owner, pas de marqueur local de succes | Projection connue reste consultable sous sa fraicheur, refus retire | Refresh roots existant ; **reemploi** |
| En cours / calendrier | personal.ongoing, selector et ressources connues | Continuation vers owners | Handoff lie aux faits autorises ; contenu ancien non presente comme en cours certain | Relecture locale + source ; **reemploi** |
| Moi / tableau personnel | personal.me et MeLocalPreview | Routes explicites vers objectifs, suivis, passeport | Distinction inconnu/absence, isolement Profile | Rafraichissement owner canonique ; **raccorde C6** |
| Moi : profil, considerations, enregistrements | Editor/draft, personal.me.settings, preview bookmarks et personal.me | PUT/PATCH/DELETE explicites via leurs owners | Aucun echec GET ne transforme un choix retenu en choix supprime | Un seul root de reconciliation SyncEngine en production ; **raccorde C6** |
| Moi : suivis, collectifs, appuis | personal.me preview / flux locaux ; pagination sur demande | Ouverture contextuelle vers owner | N2 peut etre incomplet ; jamais une autorite par simple membership | Lectures locales existantes ; **reemploi** |
| Passeport personnel, portrait et documents lecteur | Portrait prive et sous-projections owner autorisees ; Reader explicite | Publication, export, version, privacy selon owner | Secret et credential jamais deduits de la copie document | C4/C5 + couches Passport ; **reemploi**, mutation **O** |
| Decouvrir, recherche, carte, detail, watches | DiscoveryRepository, projections locales, geometrie et Presentation | Selection, recherche, Watch / owner handoffs | Le cache media n'est pas source de verite ; pas de continuation signee preacquise | Prepared source premier pack, autres contextuelles ; **reemploi** |
| Journey / Preparation / Requirement | JourneyRepository, RequirementRepository et sources keyed | Formulaires/preparations reelles, confirmation owner | Artifact ≠ Proof ≠ Requirement satisfait | Dossiers et pieces local-first ; **reemploi** |
| Questionnaires | Detail local, DraftRepository et OutboxResourceOperation | Save + submit sous politique refetch-before-retry | Pas d'envoi sous mauvais Profil, pas de replay aveugle | C3/C4 conserve ; **reemploi** |
| Projets / Dossiers (Objectives) | ObjectiveRepository : collection project/dossier + details | Creation/continuation owner uniquement | Collection locale ne prouve pas acces aux artefacts | Premiere page ajoutee au working set, suite a la demande ; **raccorde C6** |
| Historique / retrieval | HistoryRepository, index local et query-scoped owner | Ouvrir contextuellement, pas de publication automatique | Reponse plus recente et refus owner priment sur l'ancien | Premiere page preparee ; **reemploi** |
| Mes ressources / downloads | ResourceRepository + FileRecords/Reader | Download, export, rattachement sous owner | Posseder le fichier ≠ satisfaire un Requirement | Premiers resultats prepares, fichiers C5 conserves ; **reemploi** |
| Access / Credential / Jour J / Live | AccessRepository, DayOfRepository, LiveRepository | Presentations QR et operations revalidees | Access ≠ AccessCredential ≠ AccessUse ; horloge/expiration bornee | Cache local informatif, QR coffre protege, Jour J volatile ; **reemploi**, critique **O** |
| Conversations / invitations / archives | ConversationRepository, snapshots Drift et owner source | Compose local, OutboxProcessor partage et reconciliation | Autorite + destinataire + confirmation owner, pas de message « envoye » fictif | First page preparee, drafts C3 et intent idempotent ; **reemploi** |
| Notifications / preferences | **Une** NotificationRepository depuis AppRuntime | Read/preferences par owner | Refus et transport distingues, pas de faux accusé de lecture | Meme repository pour Inbox et Preferences ; **raccorde C6** |
| Interoperabilite / Connections (Personnel) | personal.interoperability root puis repository existant | Actions owner, integrations autorisees | Disponibilite technique ≠ autorite / connexion valide | Root existant etendu sans deuxieme model ; **reemploi** |
| Nous : inventory / Now / Discover / Metier / Pilot | WorkspaceContextRepository, Scope Space/perspective, selectors | Handoffs owner et permissions independantes | Inventory/membership ≠ Permission/Mandate, retrait atomique C4 | Vue Metier detaillee lit root locale d'abord ; **raccorde C6** |
| Nous : Work collection, Programme/Transport, Occurrences | Space Work source, SpaceOccurrenceRepository et vues detaillees | Creation / Operations par APIs owner revalidees | Aucun droits derives de simples items ou du cache | Root connue + continuation ponctuelle ; **raccorde C6**, mutation **O** |
| Nous : relations / Passeport / settings | Projections Space autorisees, certains editeurs restent owner-only | Changement institutionnel, version/visibilite, Mandate | Un cache public ne permet pas edition ou partage prive | Donnees sensibles requierent revalidation **O** |
| Nous : Documents confidentiels | **M** liste observee sur session active, pas de persistance generique des contenus | Upload owner direct sous `can_manage` revalide | 503 conserve lecture mais retire gestion ; 403 retire lignes | Changement acteur vide liste ; **raccorde C6**, mutation **O** |
| Commerce / checkout / commandes | Etat temporaire d'interaction et lecture owner | Checkout, selection et idempotence owner | Stock/Capacity/Payment ne sont jamais calcules hors ligne | ResumableInteractionStore existant ; **reemploi**, acte **O** |
| Services / Obtention / funding / Payments | Preparation de l'interaction, verification owner | Journey, paiement, contribution, obligation | Pas de droit obtenu ni paiement « reussi » hors connexion | Idempotence et continuation existantes ; **reemploi**, acte **O** |
| Subscription / Billing / support financier | Reponses owner revalidees, pas d'inference a partir d'un abonnement ancien | Souscription/gestion par owner | Montants, statut et droit de gestion sont critiques ; pas d'optimisme offline | Consultation ou edition peut exiger reseau (**O** intentionnel) |
| Makolo Mark (intake) | DraftRepository/ProfileFileStore, preview personal.me | Texte, photo, fichier, relecture avant owner POST | Space selectionne ne donne pas de Mandate, offline_draft ≠ traitement | Changement runtime/acteur et restaurations gardes ; **raccorde C6** |
| Visiteur / espace public / carte publique | Projection publique uniquement et presentation autorisee | Lecture publique, handoff vers login si necessaire | Ne jamais montrer une projection privee anterieure au visiteur | Aucun profil global cree par visiteur ; **P** |
| Parametres / push / compte | Preferences locales, source Notifications, services Auth/Platform | Push, settings, compte, actions owner | Push OS ≠ evenement metier, notification != preuve d'action | Preferences unifiees, push natif conserve ; **raccorde C6** |

La couverture des familles mobiles (`access, auth, commerce, continuity, day_of, discovery, funding, guest, interoperability, journey, live, mark, me, now, obtention, onboarding, ongoing, payments, personal, preparation, questionnaires, resources, services, settings, space, splash`) est explicitee ci-dessus sans reinventer leur vocabulaire ni un deuxieme ecran pour chaque couche.

### 12.4 Parcours sans Internet apres acquisition : sortie observable

1. **Profil / Now / En cours / Moi** : au second lancement sans connexion, la projection autorisee deja observee est consultable avec sa provenance et ses limites ; le refresh en echec ne fabrique pas une liste vide.
2. **Discover** : premier pack recu lisible/recherchable selon retention ; navigation sur une ressource absente exprime « non disponible » et non « rien n'existe ». Cartes et medias conservent leurs propres limitations.
3. **Dossier / Project / Resource** : premieres pages observees restent, l'ouverture keyed-detail necessite que le detail ait ete acquis ou une connexion ; aucun nouveau droit n'est deduit du listing. Les brouillons et octets explicites survivent au redemarrage.
4. **Conversations et Questionnaires** : intents prets restent dans l'outbox du Profile ; pas de send ni confirmation sous mauvais acteur. Les retries respectent l'owner.
5. **Nous/Metier** : une continuation locale peut montrer le root Work du **meme** Space et Mandate/perspective apres un 503. 403/404 ou changement d'acteur retire l'affichage.
6. **Nous/Documents** : dernier listing dans le widget reste visible apres un 503 ; upload interdit tant que les droits ne sont pas reverifies ; aucune copie durable automatique de documents confidentiels.
7. **Access/Jour J/Payment** : connaissance locale affichable selon TTL mais le serveur reste seul proprietaire de l'usage, de la confirmation et de l'echange.
8. **Mark** : brouillon et FileRecords retrouves sous le Profil et acteur d'origine ; une ancienne reponse ne rejoint jamais l'interface d'un autre Profil.

### 12.5 Tests C6 ajoutes ou modifies

- `c6_notification_composition_test.dart` : meme repository dans Inbox et Preferences, lecture locale sans API et impossibilite de relier un store d'un autre Profile.
- `space_mature_composition_test.dart` : Work local de perspective precise visible apres 503, puis masque lors du changement d'acteur.
- `c6_space_documents_composition_test.dart` : documents acquis conserves seulement en memoire apres 503, action de gestion retiree, refus 403 efface les lignes, retour Personnel les masque.
- `sync_engine_test.dart` : reconciliation du seul root `personal.me` et retention en cas de panne.
- `mark_mature_test.dart` : changement de runtime A → B dans le meme StatefulWidget et restauration du brouillon B, jamais celui de A.
- Reutilisation des tests de contrats C1–C5 des Selectors, Drift, QR, outbox, autorite, media et runtime de remplacement.

### 12.6 Conformite Behavior / Presentation Golden

Le contrat `Makolo_Application_Behavior_Interaction_System_v1.1.md` distingue explicitement l'etat du contenu (`initial/loading/content/empty/success/error`) et l'etat de synchronisation (`synced/syncing/pending/offline/conflict/failed`). Les corrections C6 gardent la combinaison `content + offline` ou `content + refresh error` lorsque le contenu local est autorise et utilisable. Le message indique ce qui n'a pas marche, ce qui est conserve et quelle action est possible ; il ne transforme pas un 503 en empty, et ne transforme jamais une preparation en succes confirme.

`Makolo_UX_Presentation_Golden_Specification_v1.md` impose de garder la grammaire visuelle de la surface lorsque loading/error/offline se produisent. C6 ne cree pas d'ecran « panne globale », de redesign general ou de force-navigation : Work et Documents conservent leur surface et un retry contextualise. Les tests Golden multi-breakpoints/execution Android ne sont pas attestes ici, ils restent une validation C8.

### 12.7 Gate de qualite et limites

Les changements C6 sont commits dans #522 et revus statiquement. **Flutter/Dart tests, analyseur, formatteur et Android n'ont pas ete executes dans l'environnement courant** : la fermeture est **implementation ecrite**, pas validation instrumentee. Les ecrans online-only critiques (Permissions, Checkout, Payments, Billing, Passport prive, gestion de documents) sont des exceptions voulues, pas des copies persistantes a inventer pour satisfaire artificiellement un critere offline. Un manque reel de contrat d'owner n'est pas transforme en API fictive.

C7 reste le guide d'extension avec exemple et test d'architecture ; C8 reste la validation Android/reconnect/kill/resume sur appareil. Aucune fusion dans `main` n'est autorisee sur la base de cette seule verification statique.
