# Makolo Mobile — Bloc E
## Action Continuity & Owner-Backed Depths

**Statut : CONCEPTION FERMÉE — canonique avant implémentation**  
**Date : 2026-09-28**  
**Dépôt : TraditionLearningCommunity/makolo**  
**Base de clôture : main @ 32a3bd5c53356853be8c6e4c995042501fe6365a**  
**Branche de consolidation : docs/mobile-bloc-e-final-closure**  
**Gate de base : ci/aggregate = success**

---

# 1. Objet

Le Bloc E ferme la conception des profondeurs owner-backed du mobile : les surfaces où une personne quitte les grandes projections Maintenant, Découvrir, En cours ou Moi pour entrer dans une réalité déjà suffisamment déterminée.

Il couvre quatre ensembles :

1. **E1 — Journey, Requirement, Form, Readiness et Preparation**
2. **E2 — Access, AccessCredential, Ressources personnelles et JourneyArtifact**
3. **E3 — Dossier, Project, Historique et Conversations**
4. **E4 — Occurrence, Jour J, Operations Live et Offline Action Pack en lecture**

Le principe directeur est :

> **Les domaines propriétaires calculent et décident ; le mobile reçoit, conserve, organise et présente leurs projections.**

Le Bloc E ne crée donc pas :

- de moteur Journey local ;
- de moteur Readiness local ;
- de validateur Requirement local ;
- de moteur Access local ;
- de moteur Dossier/Project local ;
- de moteur Jour J local ;
- de ranking local parallèle ;
- de task manager générique.

Le téléphone peut effectuer des opérations techniques et de présentation sur ce qu'il a légitimement reçu, mais il ne reproduit pas les systèmes métier du serveur.

---

# 2. Position dans l'architecture mobile

Les Blocs précédents fixent :

    A — Local Data Kernel
    B — Sync & Continuity Kernel
    C — Files, Media & Transfer Kernel
    D — Native Integration Kernel

Le Bloc E relie ces fondations aux réalités métier profondes :

    SERVER OWNER
    truth + rules + calculations
            ↓
    API / projection / capability
            ↓
    Repository
            ↓
    ProjectionSnapshots / ResourceIndex / files / drafts
            ↓
    Selector / controller
            ↓
    Owner-backed mobile surface

Pour une mutation :

    User intention
        ↓
    local draft if useful
        ↓
    Outbox only when replay semantics are explicit
        ↓
    owner API
        ↓
    server revalidation
        ↓
    owner projection refresh
        ↓
    local store
        ↓
    UI consequence

La réponse métier finale vient toujours du serveur.


## 2.1 Audit de clôture au 28 septembre 2026

Cette fermeture a été réancrée sur le runtime courant, pas sur les anciens drafts E.

Vérifié sur `main @ 32a3bd5c53356853be8c6e4c995042501fe6365a` :

- les documents canoniques A, B, C et D sont déjà présents sur `main` ;
- `ProjectionSnapshots` a déjà une identité locale `profileId + projectionKind + resourceKey` ;
- `ProfileStore` ne sait encore lire/écrire que les snapshots racine avec `resourceKey == ''` ;
- `PersonalRepository` consomme actuellement seulement `personal.now`, `personal.ongoing` et `personal.me` ;
- la navigation structurée existe déjà pour les destinations profondes ; une route ne vaut jamais autorité ;
- les owner APIs Mature de Z13 restent la référence de consommation pour Journey, Access, Jour J, Operations, History, Dossier/Project et autres profondeurs déjà exposées.

Au moment de cette clôture, les PR #353 et #355 sont encore ouvertes. Elles ne deviennent donc pas des sources de vérité de E. Toute évolution de contrat qu'elles introduiront devra être relue depuis le `main` effectivement fusionné avant implémentation.

Conséquence :

> **E ferme le contrat d'architecture mobile des profondeurs owner-backed ; il ne fige pas un payload historique contre un futur runtime.**

---

# 3. Règle de conception : snapshot avant nouvelle normalisation

Le Mobile Local Data Kernel courant a déjà fixé que les profondeurs suivantes sont d'abord conservées comme snapshots owner-backed :

| Réalité | Contrat serveur | Forme locale initiale |
|---|---|---|
| Journey | personal.journey.detail | snapshot + drafts séparés |
| Requirement | personal.journey.requirement.detail | snapshot détail |
| Dossier | objective.dossier.detail | snapshot détail |
| Project | objective.project.detail | snapshot détail |
| Mes accès | personal.accesses | collection bornée |
| Historique | personal.history | collection paginée |
| Operations Live | endpoint Live occurrence | snapshot court |
| Offline Action Pack | operations.offline_action_pack v1 | snapshot borné |
| Conversations | API Conversations | snapshot/collection d'abord |

Décision :

> **Bloc E ne crée aucune table métier locale supplémentaire par principe.**

Une nouvelle normalisation locale n'est légitime que si l'implémentation démontre un besoin réel de jointure, recherche, tri, continuité ou mutation indépendante impossible à satisfaire proprement par ProjectionSnapshots, ResourceIndex, drafts, files et Outbox.


### 3.1 Contrat des snapshots keyed

Les racines personnelles gardent `resourceKey = ''`. Une profondeur owner-backed utilise la clé composite existante :

    profileId
    + projectionKind
    + resourceKey

`resourceKey` identifie la ressource dans le scope de sa projection. Il reste opaque pour le métier mobile : le client ne le parse pas pour retrouver une table, une permission, un owner ou une règle d'autorité.

Décision de fermeture :

- étendre les accès `ProfileStore`/repositories vers `projectionKind + resourceKey` avant d'ajouter une table métier ;
- conserver `ResourceIndex` comme index de retrouvabilité/navigation, jamais comme copie de vérité ;
- ne créer aucun registre universel qui deviendrait un second catalogue métier ;
- réutiliser les primitives `SyncSource`, repositories, appliers et selectors du noyau A/B au lieu d'introduire une architecture parallèle.

---

# 4. Règle de fraîcheur

Chaque profondeur est classée selon sa sensibilité à la fraîcheur.

## 4.1 Stable / relisible

Peut généralement être relu localement puis rafraîchi :

- Project ;
- Dossier ;
- Resource detail ;
- History ;
- certaines Conversations.

## 4.2 Contextuel

Peut être montré depuis cache avec état de fraîcheur clair, mais nécessite refresh avant certaines actions :

- Journey ;
- Requirement ;
- Access detail ;
- Forms ;
- Conversation point actionnable.

## 4.3 Volatile

Ne doit jamais être présenté comme autoritatif longtemps :

- Operations Live ;
- queue position ;
- capacity availability ;
- placement opérationnel ;
- checkpoint courant ;
- temporal state ;
- next action ;
- credential présentable.

## 4.4 Borné explicitement

operations.offline_action_pack possède sa propre fraîcheur serveur :

    fresh_until
    expires_at
    stale
    expired
    refresh_required

Cette fraîcheur gagne sur toute heuristique mobile.

---

# 5. E1 — Journey, Requirement, Form, Readiness et Preparation

## 5.1 Rôle UX

La profondeur Journey répond à :

> **« Pour cette démarche précise, où en suis-je, qu'est-ce qui est déjà prêt, qu'est-ce qui reste réellement de mon côté et quelle conséquence vient ensuite ? »**

Elle ne doit jamais exposer la Journey comme un workflow générique à administrer.

Le serveur possède déjà le contrat personal.journey.detail.

Il compose notamment :

- identité et workflow ;
- représentation ;
- état ;
- Readiness ;
- demandes pending/rejected ;
- Requirements ;
- Forms ;
- Activity ;
- Occurrence ;
- Payment ;
- Access ;
- Resources ;
- capabilities ;
- links.

Décision :

> **Le mobile ne reconstruit jamais Readiness à partir de ces champs. Il affiche la Readiness déjà résolue par le serveur.**

---

## 5.2 Journey detail local

Clé locale recommandée :

    projection = personal.journey.detail
    resourceKey = <journey-id>

ResourceIndex peut indexer :

    resource_kind = journey
    resource_id
    label
    projection_kind
    navigation
    updated_at

Les liens Activity/Occurrence ne nécessitent pas une copie de leurs vérités : ils restent des références owner-backed.

---

## 5.3 Requirement detail

Le serveur possède personal.journey.requirement.detail avec notamment :

- Requirement ;
- assessment ;
- state ;
- consequence ;
- reason ;
- ways_to_satisfy ;
- capabilities ;
- links.

Décision :

> **assessment.state, consequence et les moyens de satisfaction sont des résultats serveur.**

Le mobile ne déduit jamais :

    document exists
    → requirement satisfied

Il ne transforme pas non plus une ressource trouvée en validation.

Invariant :

    Requirement ≠ Form ≠ Resource ≠ JourneyArtifact ≠ Proof ≠ Credential

---

## 5.4 Forms

Le Journey detail peut exposer des Forms avec :

- id ;
- required ;
- state ;
- due_at ;
- capabilities ;
- links.

Le contrat Z5 a déjà fixé qu'une capability complete_form n'est exposée que lorsqu'une FormRequest est réellement actionnable selon Readiness, avec les liens vers les APIs existantes de détail, sauvegarde et soumission.

Décision :

> **Le mobile ne fabrique pas de Form actionnable à partir d'un simple état local.**

### Draft local

Un formulaire peut légitimement posséder un LocalDraft pour éviter de perdre la saisie.

Le draft contient seulement les réponses utilisateur et le contexte owner nécessaire.

Il ne contient pas :

- Readiness ;
- Requirement satisfaction ;
- serveur-derived validation métier.

### Soumission

La soumission n'est envoyée que vers l'API owner existante.

Si le contrat de mutation est explicitement idempotent/rejouable, l'Outbox peut la porter.

Sinon :

- draft local conservé ;
- soumission différée jusqu'au réseau ;
- aucune promesse de retry aveugle.

---

## 5.5 Preparation resources

L'API actuelle Journey Preparation resources renvoie une liste brute, pas un projection envelope.

Le repository mobile doit donc utiliser un adapter spécifique.

Les ressources peuvent inclure :

- texte ;
- URL ;
- fichier ;
- visibilité ;
- version ;
- occurrence associée.

Décision :

> **La différence de transport n'oblige pas le backend à être uniformisé avant A3 ; l'adapter mobile absorbe la forme actuelle.**

Une ressource Preparation ne devient pas automatiquement une PersonalAsset.

---

## 5.6 Payments dans Journey

Le Journey detail peut projeter une obligation de paiement.

Le contrat Z5 est explicite : une capability pay ne doit pas être inventée tant qu'une mutation API consommable correspondante n'est pas vérifiée.

Décision mobile :

- afficher l'état/montant/devise reçus ;
- suivre le lien owner lorsqu'une capability réelle existe ;
- ne pas implémenter un paiement générique depuis le JSON Journey.

---

## 5.7 Readiness

Readiness reste entièrement serveur.

Le mobile peut :

- stocker le snapshot ;
- afficher state/reason/next ;
- rafraîchir ;
- signaler sa fraîcheur.

Il ne peut pas :

- recomposer Requirements ;
- recalculer blockers ;
- inférer READY ;
- transformer une absence de donnée en READY.

Formule :

> **Readiness est une projection reçue, jamais une machine d'état locale.**

---

## 5.8 Offline E1

### Autorisé

- relire une Journey récemment reçue ;
- relire Requirement detail ;
- continuer un draft local ;
- consulter des Preparation resources déjà téléchargées ;
- préparer une pièce en staging.

### Non autorisé par simple cache

- conclure qu'un Requirement est satisfait ;
- faire avancer le lifecycle Journey ;
- confirmer un Payment ;
- considérer une Form comme acceptée ;
- fabriquer une nouvelle Readiness ;
- décider qu'une capability est encore valide.

Une mutation hors ligne n'est permise que si son operation kind possède un contrat Bloc B explicite.

---

## 5.9 Gaps E1

Aucun nouveau modèle métier n'est requis.

Les gaps d'implémentation sont surtout :

- repositories Journey/Requirement/Forms ;
- controllers et selectors mobiles ;
- drafts Form ;
- mapping des capabilities/links ;
- handling de la forme non-enveloppée Preparation resources ;
- tests de stale state avant mutation.

---

# 6. E2 — Access, AccessCredential, Ressources et JourneyArtifact

## 6.1 Access

Le serveur possède :

    GET /api/v1/me/accesses/
    GET /api/v1/me/accesses/<id>/
    GET /api/v1/me/accesses/<id>/credential/

La liste et le détail distinguent notamment :

    beneficiary
    purchased_for_other

La visibilité transactionnelle de l'acheteur ne le transforme jamais en bénéficiaire.

Le détail Access général n'expose pas :

- QR payload ;
- signed token ;
- barcode payload ;
- AccessUse actor data.

Décision :

> **Access detail et AccessCredential restent deux repositories/surfaces différentes même lorsqu'ils sont présentés dans le même parcours.**

---

## 6.2 Access local

personal.accesses peut être conservé comme collection bornée.

Un détail Access peut être un snapshot keyed :

    projection = personal.access.detail
    resourceKey = <access-id>

ResourceIndex peut référencer :

- Access ;
- Activity ;
- Occurrence.

Mais :

> **un Access cached ne devient jamais une autorité locale.**

Le serveur revalide toujours les mutations et l'usage.

---

## 6.3 Credential

Le credential endpoint est sensible et séparé.

Il peut contenir une représentation :

- credential_type ;
- payload ;
- issued_at.

Décision :

> **Le credential n'entre pas dans le stockage de snapshots ordinaires par défaut.**

Stratégie :

    online fetch
    → short-lived memory/protected local representation if owner explicitly allows
    → immersive presentation
    → discard/lock

Une persistance offline durable ne sera ajoutée que lorsqu'un contrat Access explicite l'autorise.

Le Bloc F traitera l'autorité offline éventuelle ; E n'en crée aucune.

Invariant :

    Access = droit
    AccessCredential = représentation/secret
    AccessUse = observation d'usage

---

## 6.4 Mes ressources

Le serveur possède :

    personal.me.resources
    resource detail
    download
    reuse

Un PersonalAsset expose notamment :

- titre ;
- asset kind ;
- sensitivity ;
- status ;
- version ;
- validity ;
- provenance ;
- capabilities ;
- links.

Le détail communique explicitement :

    satisfied_by_presence = false
    decision_owner = requirements_readiness

C'est un invariant mobile majeur.

---

## 6.5 Ressource locale

La métadonnée owner reste snapshot/index.

Les octets suivent le Bloc C :

    owner download
    → .part
    → validation
    → private/cache
    → viewer

Un fichier offline peut être durable uniquement si l'owner le permet.

Le mobile peut montrer :

- version actuelle ;
- expiration reçue ;
- provenance ;
- disponibilité locale.

Il ne crée aucun valid=true universel.

---

## 6.6 Reuse

L'action reuse est contextuelle.

Pipeline :

    resource detail
    → reuse capability
    → journey context
    → owner API
    → JourneyArtifact snapshot created server-side
    → Journey/Requirement refresh

Le mobile n'envoie jamais :

    requirement_satisfied = true

Il demande l'action owner puis affiche la nouvelle projection.

---

## 6.7 PersonalAsset create/version

Bloc C a déjà identifié le gap :

> les services métier existent, mais l'API mobile mature de création/version doit encore être exposée.

E ne crée pas un second contrat.

Dès que cette API owner existe :

    FileRecord
    → Outbox/Transfer
    → PersonalAsset owner API
    → canonical version
    → resources refresh

---

## 6.8 JourneyArtifact create/version

Même frontière.

Le Web/service existe, mais Flutter ne doit pas poster un formulaire HTML.

Gap maintenu :

> **API JourneyArtifact owner-specific consommable par mobile.**

Le résultat serveur détermine ensuite :

- artifact créé ;
- version ;
- effet éventuel sur Readiness après recalcul serveur.

---

## 6.9 Offline E2

### Possible

- consulter un Access summary cached ;
- consulter une Resource metadata cached ;
- ouvrir un fichier explicitement disponible offline ;
- préparer un fichier ;
- consulter une ancienne représentation non sensible si owner autorise.

### Pas autorisé

- conclure qu'un Access est encore utilisable ;
- générer localement un QR Access ;
- considérer un credential cached comme droit valide ;
- valider un Requirement via présence de fichier ;
- enregistrer une AccessUse autoritative.

Ces capacités appartiennent aux owners et, pour l'offline autoritatif, au Bloc F.

---

## 6.10 Gaps E2

- PersonalAsset create/version API ;
- JourneyArtifact create/version API ;
- repositories Access/Resource ;
- storage policy credential sensible ;
- viewers PDF/image/video ;
- reuse orchestration ;
- tests buyer vs beneficiary ;
- cache privacy.

---

# 7. E3 — Dossier, Project, Historique et Conversations

## 7.1 Dossier

Le serveur possède objective.dossier.detail.

Le resolver serveur conserve :

- état collectif ;
- partial ;
- signal privacy-safe ;
- items visibles ;
- dépendances visibles ;
- responsabilité personnelle ;
- prochaine intervention personnelle lorsqu'elle vient du resolver.

Une dépendance cachée peut influencer l'état sans révéler :

- hidden Journey id ;
- hidden title ;
- hidden Profile ;
- hidden Requirement ;
- hidden URL.

Décision :

> **Le mobile affiche le résultat collectif reçu ; il ne cherche jamais à reconstruire le Dossier en agrégeant toutes les Journeys qu'il connaît localement.**

Cela protège aussi la divulgation minimale.

---

## 7.2 Project

Le serveur possède objective.project.detail.

Il expose l'horizon durable et seulement les Dossiers visibles.

Il ne crée pas :

    Task
    Kanban
    milestone artificiel
    completion percentage
    Project Readiness synthétique

Le mobile ne doit pas en introduire non plus.

> **Project reste un horizon durable, pas un task manager.**

---

## 7.3 Local Dossier/Project

Forme initiale :

    ProjectionSnapshot detail
    +
    ResourceIndex

Le cache peut être relu offline.

Avant une action :

- refresh si capability sensible ;
- owner server revalidation ;
- aucune autorité dérivée d'une Assignment.

Invariant :

    Assignment = responsabilité
    Mandate/Permission = autorité

---

## 7.4 Historique

Le serveur possède personal.history.

Historique est une projection temporelle transversale.

Le mobile peut :

- conserver des pages déjà reçues ;
- indexer les références Journey/Access/Occurrence utiles ;
- afficher offline une portion historique ;
- ouvrir le détail owner existant.

Il ne crée pas de table locale HistoryEvent en copiant tous les Domain Events.

> **Historique ≠ event log technique.**

Un événement backend n'est pas automatiquement une entrée historique UX.

---

## 7.5 Pagination History

Les pages historiques sont append/read-through.

Le repository doit préserver :

- ordre serveur ;
- cursor/page contract réel ;
- provenance ;
- capacité de refresh de la première page.

Ne pas utiliser un tri local pour réécrire l'ordre sémantique du serveur.

---

## 7.6 Conversations

Le serveur expose actuellement une API directe, non projection-envelope.

Liste :

    GET /api/v1/conversations/

avec notamment :

- results ;
- count ;
- q ;
- updated_after ;
- limit.

Une ligne contient notamment :

- id ;
- title ;
- purpose ;
- lifecycle ;
- context ;
- attention_count ;
- latest_result ;
- all_clear ;
- updated_at.

Détail :

- conversation ;
- points ;
- context ;
- updated_at.

Les Points exposent notamment :

- response_mode ;
- lifecycle ;
- importance ;
- title ;
- body ;
- requires_acknowledgement ;
- deadlines ;
- can_respond ;
- attention_reason ;
- section ;
- resolution_summary.

Décision :

> **can_respond, attention_reason et section sont des résultats serveur. Le mobile ne les recalcule pas.**

---

## 7.7 Synchronisation Conversations

updated_after fournit un mécanisme utile pour un refresh incrémental.

Le repository peut donc :

    bootstrap recent conversations
    → persist snapshot/index
    → refresh updated_after(last_success)
    → replace changed conversations

Il ne doit pas prétendre disposer d'un delta complet si le contrat API ne garantit pas suppressions/tombstones.

En cas de doute :

> refresh borné complet de la collection active.

---

## 7.8 Mutations Conversations

Les mutations vérifiées comprennent notamment :

- respond to point ;
- acknowledge ;
- invitation respond.

La réponse à un Point dispose d'une référence client/idempotence côté service, ce qui la rend compatible avec un operation kind Outbox soigneusement défini.

Mais chaque mutation doit conserver son contrat propre.

Décision :

    respond point
    → candidate Outbox mutation

    acknowledge
    → candidate Outbox mutation if replay contract verified

    invitation decision
    → server revalidation before final state

Le mobile ne marque jamais un Point resolved uniquement parce que le tap a été enregistré localement.

---

## 7.9 Conversation attention vs Maintenant

Un Point de Conversation peut alimenter Maintenant seulement si le serveur/projection établit qu'une attention actuelle est nécessaire.

unread seul ne suffit pas.

Le détail Conversation reste owner-backed même lorsqu'un Point est projeté dans Maintenant.

---

## 7.10 Offline E3

### Autorisé

- lire conversations déjà reçues ;
- lire History cached ;
- relire Dossier/Project ;
- rédiger une réponse locale ;
- éventuellement queue une réponse si son operation kind est explicitement idempotent.

### Non autorisé

- transformer une réponse locale en résolution serveur ;
- recalculer all_clear ;
- fabriquer un attention_reason ;
- déduire une autorité Dossier/Project.

---

## 7.11 Gaps E3

Pas de nouveau modèle métier requis.

Travail mobile :

- repositories Dossier/Project/History/Conversations ;
- pagination et incremental refresh ;
- drafts réponses ;
- operation kinds Conversation ;
- navigation owner-backed ;
- tests de confidentialité Dossier ;
- stale handling.

---

# 8. E4 — Occurrence, Jour J, Operations Live et Offline Action Pack

## 8.1 Rôle

E4 est la jonction entre :

    En cours
    Maintenant
    Occurrence detail
    Jour J
    Operations Live

Il prépare le mobile au monde réel sans déplacer l'autorité vers l'appareil.

Le Jour J répond :

> **« Cette Occurrence est devenue actuelle pour moi : où en suis-je, qu'est-ce qui se passe, où dois-je aller et qu'est-ce qui vient pour moi ? »**

---

## 8.2 Occurrence detail

L'API Occurrence detail fournit notamment :

- identity ;
- Activity ;
- state ;
- timing ;
- place ;
- capacity ;
- availability ;
- personal relation ;
- capabilities ;
- links.

Capacity/availability sont des snapshots serveur.

Le mobile n'utilise jamais une ancienne valeur available pour autoriser une réservation.

---

## 8.3 Day-of

Le serveur possède personal.occurrence.day_of.

Il compose notamment :

- activity ;
- occurrence ;
- situation ;
- temporal relation ;
- current position ;
- next ;
- representation ;
- timing ;
- spatial ;
- access ;
- queue ;
- placement ;
- checkpoints ;
- readiness ;
- completion ;
- capabilities ;
- links.

Décision :

> **Day-of est la composition serveur du Jour J personnel.**

Le mobile ne fabrique pas next en joignant localement Queue + Access + Placement.

---

## 8.4 Operations Live

L'endpoint Live est direct, pas projection-envelope.

Le serveur résout la perspective :

    participant
    operator
    space

Pour la personne, le payload peut notamment inclure :

- occurrence ;
- timing ;
- temporal_state ;
- phase ;
- access ;
- usable ;
- placement ;
- checkpoints ;
- next_checkpoint ;
- queue ;
- position ;
- capacity ;
- available ;
- spatial ;
- mobility ;
- hazards ;
- advices ;
- operational_readiness ;
- next_action.

Tous ces champs sont des résultats serveur.

Le mobile ne recalcule jamais :

- temporal state ;
- phase ;
- queue position ;
- capacity availability ;
- access usability ;
- next checkpoint ;
- next action ;
- hazards ;
- mobility.

---

## 8.5 Volatilité Live

Operations Live doit être traité comme une projection courte.

Politique :

    display cached very briefly
    → immediately refresh when foreground/live surface resumes
    → visibly degrade if stale

Le repository ne doit pas lui appliquer la même stratégie qu'à un Project ou History.

---

## 8.6 Jour J local

La racine Jour J peut assembler visuellement plusieurs snapshots reçus :

    Day-of
    +
    Occurrence detail
    +
    Operations Live
    +
    Access detail/credential on demand
    +
    map rendering

Mais elle ne recompute pas le métier.

La distinction est :

> **composition de présentation locale autorisée ; calcul de décision métier local interdit.**

Exemple autorisé :

- afficher côte à côte l'heure reçue et la carte du lieu reçu.

Exemple interdit :

- déduire localement « Partez maintenant » à partir de l'heure, du GPS et d'un ETA maison si le serveur n'a pas fourni cette conséquence.

---

## 8.7 Live Queue

Queue position est reçue du serveur.

Le mobile peut :

- l'animer ;
- montrer la progression ;
- focaliser l'appel ;
- présenter une notification locale déjà décidée.

Il ne peut pas :

- incrémenter/décrémenter autoritativement la position ;
- décider qu'une personne est appelée ;
- fabriquer un ordre.

---

## 8.8 Capacity et Placement

Toujours distincts :

    Capacity = combien ?
    Placement = où ?

La racine Jour J peut représenter les deux, mais ne les fusionne jamais.

Une place assignée ne prouve pas une Capacity disponible.

Une Capacity disponible ne produit pas un Placement.

---

## 8.9 Checkpoint

Un checkpoint opérationnel appartient à Operations.

Il n'est jamais transformé en JourneyStep.

Le mobile peut rendre un checkpoint dans Jour J et Scanner, mais le serveur conserve l'état opérationnel.

---

## 8.10 Credential dans Jour J

La surface QR/pass est un handoff spécialisé depuis Jour J.

Pipeline :

    Jour J
    → Access detail
    → credential endpoint
    → protected immersive surface

Pas :

    Occurrence ID
    → generate QR locally

Le credential reste distinct du droit.

---

## 8.11 Offline Action Pack

Le serveur possède operations.offline_action_pack, schema_version 1, avec :

- generated_at ;
- freshness ;
- provenance ;
- data_policy ;
- execution_contract ;
- sanitized snapshot.

Le contrat serveur dit explicitement :

    offline_data_grants_authority = false
    server_revalidation_required = true
    revocation_policy = server_current_state

et impose de revalider notamment :

- permissions ;
- mandates ;
- occurrence ;
- access ;
- checkpoint ;
- queue ;
- placement ;
- capacity.

Décision Bloc E :

> **Offline Action Pack est une projection de continuité en lecture. Il ne délègue aucune autorité.**

---

## 8.12 Usage offline E4

Lorsque le réseau tombe, l'app peut :

- ouvrir le dernier pack non expiré ;
- montrer le dernier état connu ;
- préciser la fraîcheur ;
- guider à partir de données explicitement contenues dans le pack ;
- conserver le contexte Jour J.

Elle ne peut pas, à cause du pack seul :

- valider un Access ;
- enregistrer une AccessUse autoritative ;
- faire avancer une Queue ;
- allouer Capacity ;
- changer Placement ;
- valider checkpoint ;
- exercer une Permission/Mandate.

Ces questions appartiennent au Bloc F — Offline Authority.

---

## 8.13 Pack stale / expired

### Fresh

Afficher normalement avec indication discrète si nécessaire.

### Stale mais non expired

Afficher comme dernière information connue, avec refresh recherché dès que possible.

### Expired

Ne pas continuer à présenter des décisions opérationnelles comme actuelles.

La surface doit réduire sa confiance :

> **« Information à actualiser »**

et conserver seulement ce qui reste honnêtement représentable.

Le mobile ne prolonge jamais expires_at.

---

## 8.14 Maps et GPS en Jour J

Le Bloc D a fixé :

    GPS = observation device
    MapLibre = renderer

E4 peut les utiliser pour la représentation :

- afficher position personnelle volontaire ;
- afficher place/zone reçue ;
- dessiner un point de destination ;
- montrer un trajet fourni par une source owner.

Mais le mobile ne fabrique pas une vérité Geography.

---

## 8.15 Entrées Jour J

La même surface Jour J peut être atteinte depuis :

- Maintenant ;
- En cours ;
- Occurrence detail ;
- Access ;
- notification ;
- deep link.

Il n'existe pas plusieurs Jour J.

La provenance peut seulement influencer le focus initial.

---

## 8.16 Sortie Jour J

Lorsque l'Occurrence cesse d'être actuelle :

- elle ne reste pas artificiellement en mode Live ;
- History reprend la lecture temporelle ;
- Resources/Proofs/Credentials durables restent chez leurs owners ;
- En cours disparaît lorsque la continuité pertinente est réellement terminée.

---

## 8.17 Gaps E4

Pas de nouveau modèle serveur nécessaire pour la lecture.

Travail mobile :

- repositories Occurrence/DayOf/Live/OfflinePack ;
- stratégie de fraîcheur volatile ;
- Jour J controller ;
- Access/Credential handoff ;
- maps rendering ;
- lifecycle foreground/resume ;
- explicit stale UX ;
- tests pack expiration ;
- préparation du contrat F sans l'implémenter.

---

# 9. Navigation owner-backed

Les routes mobiles ne doivent pas inventer une architecture métier parallèle.

Règle générale :

    StructuredDestination
    → owner repository
    → local snapshot if acceptable
    → refresh
    → owner surface

Les destinations profondes doivent utiliser :

- kind ;
- id ;
- les links/capabilities serveur ;
- la provenance de navigation.

Le bouton Back retourne vers l'origine réelle.

---

# 10. Capability-driven UI

Une action apparaît parce que le serveur la rend réellement consommable.

Le mobile ne déduit pas :

    state == pending
    → show "Approve"

Il consomme :

    capabilities
    links

et peut appliquer des contraintes techniques :

- offline ;
- permission OS ;
- fichier absent localement ;
- provider indisponible.

Ces contraintes peuvent empêcher temporairement l'exécution, mais elles ne créent pas une nouvelle Permission métier.

---

# 11. Error model

Les APIs actuelles ne sont pas uniformes :

- projection envelope ;
- DRF pagination ;
- direct object ;
- raw array ;
- detail errors ;
- errors ;
- field errors.

Bloc E ne bloque pas l'implémentation sur une uniformisation serveur générale.

Le network layer mobile doit normaliser techniquement :

    transport failure
    unauthenticated
    forbidden
    not found
    validation
    conflict
    rate/temporary
    server failure

sans perdre le payload owner utile.

403/404 après navigation cached sont normaux : la réalité peut avoir changé, quitter le scope courant ou ne plus être visible.

Ils invalident d'abord la capacité d'utiliser **ce snapshot dans ce scope/source**. Ils ne signifient pas, par règle globale, qu'il faut supprimer toute identité locale de la ressource : une même identité peut encore être référencée légitimement par History, une autre projection ou un autre scope. Le nettoyage de ResourceIndex et des snapshots suit donc les memberships/sources et la politique de rétention, pas une suppression universelle déclenchée par un seul 403/404.

---

# 12. Mutation policy

Avant d'ajouter une mutation à Outbox, documenter :

1. owner ;
2. endpoint ;
3. intent ID ;
4. idempotency/replay semantics ;
5. payload minimal ;
6. dependency IDs ;
7. expected confirmation ;
8. conflict handling ;
9. cancellation semantics ;
10. refresh sources after confirmation.

Si ces éléments ne sont pas clairs :

> **draft local oui ; replay automatique non.**

---

# 13. Offline policy globale du Bloc E

## E peut fonctionner offline pour

- lecture de snapshots récents ;
- History déjà reçu ;
- Project/Dossier déjà reçu ;
- Journey/Requirement cached avec fraîcheur visible ;
- ressources privées déjà téléchargées ;
- drafts ;
- préparation de fichiers ;
- Offline Action Pack borné en lecture.

## E ne promet pas offline pour

- autorité Access ;
- validation Requirement ;
- transitions Journey ;
- Payment final ;
- Queue mutation ;
- Capacity allocation ;
- Placement mutation ;
- checkpoint acceptance ;
- scanner autoritatif.

Ces derniers sujets seront explicitement traités dans le Bloc F.

---

# 14. Matrice E complète

| Surface / owner | Source serveur | Local | Mutation | Offline |
|---|---|---|---|---|
| Journey | personal.journey.detail | snapshot + index | owner API/capability | lecture + draft |
| Requirement | personal.journey.requirement.detail | snapshot | owner API seulement | lecture |
| Form | links Questionnaire | draft + snapshot | submit owner | draft oui |
| Preparation resources | raw array API | snapshot/files | owner-specific | fichiers déjà reçus |
| Dossier | objective.dossier.detail | snapshot + index | capability owner | lecture |
| Project | objective.project.detail | snapshot + index | capability owner | lecture |
| Access list | personal.accesses | collection + index | owner | lecture non autoritative |
| Access detail | personal.access.detail | snapshot | owner | lecture non autoritative |
| Credential | sensitive endpoint | memory/protected only | usage via owner | pas par défaut |
| Resources | personal.me.resources | collection + index | owner | lecture |
| Resource detail | personal resource detail | snapshot + file ref | reuse/archive/etc. owner | oui si file autorisé |
| PersonalAsset create/version | API à ajouter | FileRecord/Outbox | owner | staging seulement |
| JourneyArtifact | API à ajouter | FileRecord/Outbox | owner | staging seulement |
| History | personal.history | pages + index | none/read | oui |
| Conversations | direct API | snapshots + index | point/invitation APIs | lecture + drafts |
| Occurrence detail | occurrence detail | snapshot | owner | lecture |
| Day-of | personal.occurrence.day_of | volatile snapshot | owner/capability | lecture courte |
| Operations Live | direct API | short snapshot | operations owner | très limité |
| Offline Action Pack | v1 bounded pack | bounded snapshot | **aucune autorité** | oui, lecture bornée |

---

# 15. Anti-features Bloc E

Ne pas créer :

- LocalJourneyEngine ;
- LocalReadiness ;
- LocalRequirementEvaluator ;
- LocalAccessAuthority ;
- LocalCapacityEngine ;
- LocalQueueEngine ;
- LocalDossierReadiness ;
- LocalProjectProgress ;
- generic Task table ;
- generic Status table ;
- duplicate History database ;
- generic Resource domain fusionnant Asset/Proof/Credential/Access ;
- JourneyStep/Checkpoint fusion ;
- Access/AccessCredential fusion ;
- Waitlist/Live Queue fusion ;
- client-side capability inference.

---

# 16. Organisation de code cible

Bloc E peut rester compatible avec l'architecture A2 actuelle.

Direction conceptuelle :

    mobile/lib/
      repositories/
        journey_repository.dart
        requirement_repository.dart
        access_repository.dart
        resource_repository.dart
        objective_repository.dart
        history_repository.dart
        conversation_repository.dart
        occurrence_repository.dart
        operations_repository.dart

      features/
        journey/
        access/
        resources/
        objectives/
        history/
        conversations/
        day_of/

      data/local/
        ProjectionSnapshots
        ResourceIndex
        LocalDrafts
        OutboxOperations
        FileRecords

      platform/
        maps/
        scanner/
        notifications/
        files/

Cette structure reste indicative.

Ne pas déplacer les fichiers existants simplement pour obtenir une arborescence esthétique.

---

# 17. Ordre d'implémentation recommandé

## E-I — infrastructure repository depth

- generic projection fetch/store helper ;
- keyed detail snapshots ;
- stale/fresh representation ;
- ResourceIndex navigation ;
- normalized transport errors.

## E-II — Journey depth

- Journey detail ;
- Requirement detail ;
- Forms ;
- Preparation resources ;
- drafts ;
- owner handoffs.

## E-III — Personal capital depth

- Access list/detail ;
- credential protected presentation ;
- Resources list/detail/download/reuse ;
- PersonalAsset/JourneyArtifact APIs dès qu'elles existent.

## E-IV — continuity depth

- Dossier/Project ;
- History ;
- Conversations ;
- incremental refresh ;
- outbox-safe mutations.

## E-V — Jour J online

- Occurrence detail ;
- Day-of ;
- Live ;
- Access handoff ;
- maps ;
- Offline Action Pack read-only.

Cette séquence peut être parallélisée après collision audit.

---

# 18. Tests et gates

## Repositories

- snapshot key isolation par Profile ;
- stale/fresh ;
- 403/404 owner loss ;
- schema version mismatch ;
- raw/list/envelope adapters ;
- no cross-profile leakage.

## Journey

- Readiness jamais recalculée ;
- Requirement satisfaction jamais inférée ;
- Form draft survives restart ;
- capability disappearance after refresh ;
- Payment capability non inventée.

## Access/Resources

- buyer vs beneficiary ;
- credential absent du detail général ;
- credential protected ;
- Resource presence ≠ Requirement satisfaction ;
- version/download ;
- reuse refresh.

## Dossier/Project

- hidden dependency privacy ;
- Assignment ≠ authority ;
- no synthetic completion percentage.

## Conversations

- incremental refresh ;
- respond idempotency ;
- acknowledgement replay behavior ;
- stale can_respond rejected by server ;
- drafts survive restart.

## Jour J

- Live stale handling ;
- offline pack fresh/stale/expired ;
- no authority from offline pack ;
- queue/capacity/next action never calculated locally ;
- Access credential not synthesized ;
- resume triggers refresh.

---

# 19. Gaps serveur vérifiés à la clôture

Bloc E ne demande pas une refonte générale.

Sur le `main @ 32a3bd5c53356853be8c6e4c995042501fe6365a`, les gaps déjà documentés par C/Z13 restent ceux qu'E doit transporter sans les réinventer :

1. **PersonalAsset create/version API** — services métier existants, contrat API mobile owner non démontré sur le runtime audité ;
2. **JourneyArtifact create/version API** — services/Web existants, contrat API mobile owner non démontré ;
3. **InboundCapture API / référence de capture vers Mark** — primitive locale/native préparée par C/D, owner API serveur à exposer lorsqu'une expérience l'exige ;
4. toute mutation qui n'existe encore qu'en surface Web reste indisponible au mobile tant qu'un owner API réel, ses permissions et ses garanties de replay ne sont pas démontrés ;
5. aucune API générique `/mobile/actions` ou équivalent ne doit contourner les owners.

Ces éléments sont des **gaps de contrat**, pas une invitation à créer de nouveaux modèles. Avant implémentation, chacun doit être revalidé sur le `main` courant ; s'il a été fermé entre-temps, le runtime gagne et le gap disparaît.

Aucun token de concurrence Form universel, aucune nouvelle API realtime générique et aucun provider ne sont exigés par E sans preuve owner-specific.

---

# 20. Décisions figées du Bloc E

1. Les profondeurs mobiles consomment les owners existants ; elles ne deviennent pas des systèmes métier locaux.
2. Journey/Requirement/Dossier/Project/Access/History commencent en snapshots owner-backed.
3. ResourceIndex sert à retrouver et naviguer, pas à copier la vérité.
4. Readiness est serveur uniquement.
5. Requirement satisfaction est serveur uniquement.
6. Les Forms peuvent avoir des drafts locaux ; leur acceptation reste serveur.
7. Preparation resources gardent leur transport actuel via adapter.
8. Payment n'est pas inventé comme capability générique.
9. Access detail et Credential restent séparés.
10. Credential sensible n'entre pas dans le snapshot ordinaire.
11. Resource possession ne signifie jamais Requirement satisfaction.
12. Reuse produit une conséquence server-side puis refresh.
13. Dossier collectif n'est jamais recalculé localement.
14. Project n'est jamais transformé en task manager.
15. History est une projection temporelle, pas un event log local.
16. Conversation can_respond, attention_reason et all_clear restent serveur.
17. Operations Live est fortement volatile.
18. Jour J peut composer visuellement plusieurs projections mais ne calcule aucune décision métier.
19. Offline Action Pack est read-only du point de vue de l'autorité.
20. Toute autorité opérationnelle offline appartient au Bloc F.
21. Une mutation n'entre dans Outbox que si son replay contract est défini.
22. Les capabilities serveur commandent les actions UX ; le client ne les infère pas.
23. 403/404 après cache sont des résultats normaux à gérer.
24. Aucun nouveau modèle persistant n'est ajouté sans besoin démontré.

---

# 21. Critères de sortie de la conception

Le Bloc E est fermé comme contrat de conception lorsque :

1. main et les PR mobiles actives sont revalidés ;
2. les API payloads exacts sont vérifiés avant chaque repository ;
3. les APIs manquantes C/D nécessaires à une feature sont disponibles ou la feature reste non exposée ;
4. les operation kinds Outbox sont définis mutation par mutation ;
5. les politiques de fraîcheur sont fixées par owner ;
6. les credentials sensibles ont une politique de stockage explicite ;
7. Jour J ne dépend pas d'un calcul métier local ;
8. Offline Action Pack reste non autoritatif ;
9. les tests IDOR/confidentialité serveur restent verts ;
10. le mobile passe les tests ciblés et les gates natives seulement lorsque pertinentes.

---

# 22. Formule finale

Le Bloc E transforme Makolo Mobile en **client profond et continu** des domaines existants, sans le transformer en second serveur.

Il permet à la personne de :

- reprendre une Démarche ;
- comprendre un Requirement ;
- compléter une Form ;
- retrouver un Access ;
- présenter un credential ;
- réutiliser une ressource ;
- comprendre un Dossier ou Project ;
- retrouver son Historique ;
- répondre dans une Conversation ;
- vivre une Occurrence en Jour J ;
- conserver une continuité minimale lorsque le réseau disparaît.

Mais il maintient toujours la même frontière :

> **Le téléphone peut garder la continuité de l'expérience ; le serveur garde la continuité de la vérité et de l'autorité.**

E s'arrête volontairement avant l'autorité opérationnelle offline.

> **La question de savoir quand, comment et jusqu'où une autorité peut être explicitement déléguée au téléphone hors réseau est désormais fermée au niveau conception par `mobile-delegated-offline-authority-kernel.md` (Bloc F). E n'en crée toujours ni les règles ni l'implémentation.**

La fermeture de maturité/release est portée séparément par `mobile-mature-release-kernel.md` (Bloc G).
