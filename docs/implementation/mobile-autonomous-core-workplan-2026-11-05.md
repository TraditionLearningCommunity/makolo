# Makolo Mobile — Refondation du noyau applicatif autonome

**Statut :** plan d'execution transversal, non commence par ce document.
**Date de cadrage :** 5 novembre 2026.
**Depot :** TraditionLearningCommunity/makolo.
**Branche unique d'execution :** \`fix/discover-a-continuation-context-20261014\` (PR #522).
**Baseline revalidee au cadrage :** \`main@d0f0ec421c94c255fa4c0acd3509938a70c6322f\` ; \`PR #522@0795ab65f538b289f2f8c86a3c92104a53c5cf79\`.
**Perimetre des changements de ce chantier :** \`mobile/**\` et documentation explicitement liee. Aucun backend, API, migration Django ni Web.
**Nature des identifiants C0-C8 :** checkpoints internes de ce chantier, pas nouveau train LF, A, M ou programme officiel.

> Makolo marche pour vous. Meme lorsque le reseau ne marche pas.

## 1. Objectif et regle directrice

Le parcours normal est : **Owner distant -> acquisition coordonnee -> stockage local durable -> selectors/repositories locaux -> Flutter**.
Pour l'ecriture admise : **intention -> brouillon/operation locale durable -> transmission sous contrat owner -> reconciliation -> lecture locale reactualisee**.

Le reseau n'est pas une condition de construction de l'ecran. Le local n'est pas une nouvelle autorite metier. N'introduire ni cache par ecran, ni seconde source de verite, ni API, ni modele metier ni nouvelle table sans demonstration que l'existant ne couvre pas le besoin.

## 2. Baseline verifiee et travaux existants a reutiliser

- Le schema Drift v2 de \`mobile/lib/data/local/makolo_database.dart\` contient six tables : \`ProjectionSnapshots\`, \`ResourceIndex\`, \`SyncSources\`, \`OutboxOperations\`, \`LocalDrafts\`, \`FileRecords\`.
- Il existe deja \`ProfileStore\`, \`SyncEngine\`, \`ProjectionSelector\`, des repositories, la gestion d'outbox et des tests cibles.
- La PR #522 porte deja des changements local-first recents (Now, Discover, Moi, ressources, medias, outbox, revocations). Ne pas recommencer ou supprimer sans lecture du code courant.
- La PR #522 comporte aussi des changements non Flutter et est volumineuse. Geler tout ajout hors mobile dans ce chantier. Une revue de collision et de CI est obligatoire avant integration finale.
- Sources de conception a revalider sur le runtime : \`docs/architecture/mobile-local-data-kernel.md\`, \`mobile-sync-continuity-kernel.md\`, \`mobile-action-continuity-kernel.md\`, \`mobile-par1d-parallel-feature-boundaries.md\`, \`mobile-a2-acceptance-matrix.md\`, \`mobile-api-contract.md\`, \`docs/architecture/makolo-domain-blueprint.md\`, \`AGENTS.md\`, \`docs/operations/agent-orchestration.md\`, \`docs/operations/ai-development-guardrails.md\`.
- Aucun resultat Android ou verdict global de CI n'est atteste par ce document. Relever le HEAD et les gates a chaque checkpoint.

## 3. Regle de chaque tache

Chaque checkpoint doit posseder : owner, base SHA au moment de commencer, fichiers autorises/interdits, changement minimal, tests cibles, verification manuelle pertinente, resultat de CI et preuve de non-regression. Commits petits et tracables. Aucun checkpoint n'est termine sur la seule base du code ecrit. Mettre a jour ce document avec une preuve (SHA, commande/test, resultat, limites).

## 4. Checkpoints d'execution

### C0 — Stabiliser la baseline et les flux existants

**Responsable :** integrateur. **Dependance :** aucune.

- Rafraichir \`main\`, tete de #522, statut/CI, derniers commits, branches et PR en collision.
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
- Ne pas introduire \`OccurrenceFactsIndex\` ou \`SourceMembership\` sans cas de requete, proprietaire et test prouvant leur necessite.

**Sortie :** un fait acquis reutilisable par plusieurs contextes sans lecture HTTP pour la consultation ; tests Drift, migrations, deduplication, isolation et cold start.

### C2 — Acquisition coordonnee, incrémentale et reprenable

**Responsable :** developpeur A. **Dependance :** C1.

- Reorganiser l'existant \`SyncEngine\`, \`SyncSource\`, appliers et orchestration lifecycle ; une source represente un contrat owner, pas un ecran.
- Declenchements : lancement/reprise, contexte, connectivite, invalidation, priorite utile, refresh demande, travail en attente. Respecter les contraintes Android/iOS.
- Budgets : temps, octets, batterie, stockage, medias, nombre de sources ; backoff et reprise sans boucle agressive.
- Pagination : 10 puis 10 puis 40, accumulation et deduplication autorisees, provenance du scope, curseurs invalides, sans extrapoler une exhaustivite globale.
- Garantir atomisme et comportement des reponses tardives ; ne pas detruire l'observation partageable sur simple erreur reseau.

**Sortie :** acquisition demonstrablement independante de l'ouverture d'une vue ; tests sync, interruption, replay, pagination et rafraichissement.

### C3 — Continuite d'action, brouillons et operations

**Responsable :** developpeur B. **Dependance :** C0 puis contrat stable de C1 ; peut avancer en parallele de C2 sur fichiers disjoints.

- Reutiliser \`LocalDrafts\`, \`OutboxOperations\`, \`DraftRepository\`, \`OutboxProcessor\` et handlers existants ; ne pas creer un moteur concurrent.
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
- Reutiliser les proprietaires existants de media et \`FileRecords\`; distinguer copie durable autorisee, cache recomposable, fichier explicitement conserve, credential protege.
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

Creer un guide versionne dans \`docs/architecture/\` (nom a verifier au moment du travail), avec **un exemple reel tiré d'une feature existante** et un test de conformite architectural, sans feature fictive. Le guide doit expliquer :

1. Identifier owner distant, scope de visibilite, source et payload autorise.
2. Declarer/brancher une \`SyncSource\` existante, son acquisition, son applier transactionnel et sa politique d'invalidation.
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

**Sortie :** evidence des dix scenarios, \`flutter analyze\`, tests cibles + suite pertinente, formatting canonique, CI pertinente verte, revue des diff ; merge uniquement si gates verts et reconciliation avec \`main\`.

## 5. Dependances et deux developpeurs sans creer de branche

~~~text
C0
  -> C1 -> C2 -----+
     \-> C3 -------+-> C4 -> C5 -> C6 -> C7 -> C8
~~~

Le schema donne l'ordre logique, pas un monolithe obligatoire. C3 peut commencer avec le contrat C1 stabilise, pendant C2.

- **A — Connaissance/acquisition :** \`mobile/lib/data/local/**\`, appliers et pull sous \`mobile/lib/sync/**\`, selectors communs. Ne touche pas aux outbox handlers tenus par B.
- **B — Continuite d'action :** brouillons, intents, outbox handlers owner, tests d'operations. Ne modifie pas le schema Drift ni \`SyncEngine\` sans validation de l'integrateur.
- **Integrateur unique :** \`app/router.dart\`, \`app/providers.dart\`, runtime builder, bootstrap, \`pubspec.yaml\`, \`mobile/android/**\`, schema Drift/migrations, signatures communes, CI, commits integres et push de la branche.
- **Une seule branche distante:** \`fix/discover-a-continuation-context-20261014\`. Deux espaces de travail peuvent etre crees en \`git worktree --detach\` sur le SHA approuve (sans nouvelle branche). Les contributeurs transmettent des commits SHAs ; l'integrateur les cherry-pick ou applique de facon controlee sur cette unique branche puis pousse. Personne ne force-push. Ne pas ecrire en parallele le meme fichier.
- Apres chaque integration : comparer HEAD/CI, tester le contrat touche et actualiser le checkpoint. Ne pas traiter #522 comme deja fusionnee.

## 6. Gate de qualite minimal

\`cd mobile && bash tool/dart_format.sh write && bash tool/dart_format.sh check\`, puis \`flutter analyze\`, tests cibles, tests d'architecture et suites pertinentes. Outils canoniques dans \`AGENTS.md\` (Flutter 3.47.3 / Dart 3.13.3). Aucun test affaibli, pas de faux succes et pas de nouveau serveur/API/Web dans ce chantier.

## 7. Etat de suivi

| Checkpoint | Etat initial | Preuve requise |
|---|---|---|
| C0 Baseline | A faire | HEADs, collisions, CI, matrice |
| C1 Connaissance | A faire | tests Drift/selectors/cold start |
| C2 Acquisition | A faire | 10/10/40, reprise, budgets |
| C3 Actions | A faire | draft/outbox, replay owner |
| C4 Autorite | A faire | revocation, profils, secrets |
| C5 Cycle de vie | A faire | media, stockage, resume |
| C6 Composition | A faire | couverture des surfaces |
| C7 Extensibilite | A faire | guide + exemple reel + tests |
| C8 Android/fermeture | A faire | 10 scenarios + CI verte |

**Regle de fermeture globale :** le noyau est reutilisable par une nouvelle fonctionnalite sans que celle-ci doive reconstruire persistance, acquisition, lecture, brouillons, retries ni reconciliation. Les limites distantes demeurent explicites et legitimes.
