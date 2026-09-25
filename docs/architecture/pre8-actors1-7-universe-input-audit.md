# Pré-8 — Consolidation Actors 1 à 7 et frontière d'entrée de l'Univers Makolo

> Statut : audit de précondition Actor 8.
>
> Base technique initiale : Actor 7 `actor7/projector-foundation@a287a0ea6a59a384b3aac6a7c38dd7dbf5795940`. Actor 7 a ensuite été intégré via PR #282 ; la présente note est maintenant réconciliée sur `main@d1dd309f034c7aa8f0927298a4dc74e99d4cd495`.
>
> Cette note ne lance pas Actor 8. Elle fixe ce qui est réellement disponible avant de construire le moteur Univers.
>
> Réconciliation du 25 septembre 2026 : ACT1–ACT4 a fermé l’Interpréteur généraliste (compréhension documentaire, extraction déterministe, enrichissement grounding via IntelligenceGateway, benchmark et handoff Actor 4). Cette évolution renforce Actor 3 mais ne change pas la frontière : l’Interpréteur produit des candidats sémantiques et ne devient pas propriétaire des vérités métier ni de l’Univers.
>
> Le code, les migrations, les tests, les documents scientifiques consolidés les plus récents et le main courant gagnent sur cette note en cas de divergence.

## 1. Décision Pré-8

Actor 8 ne doit pas commencer par inventer des CorpsMakolo, des grandeurs ou des équations à partir des noms de modèles Django.

La séquence retenue est :

    monde extérieur
      ↓
    Actor 1 Prospecteur
      ↓ ObservationTarget
    Actor 2 Observateur
      ↓ ObservationMaterial v2
    Actor 3 Interpréteur
      ↓ InterpretedMaterial v1
    Actor 4 Résolveur
      ↓ ResolvedMaterial v1
    Actor 5 Orchestrateur
      ↓ décisions owner-safe
    Actor 6 Persistateur
      ↓ faits canoniques durables + change signals
    Actor 7 Projecteur
      ↓ UniverseSnapshot / UniverseDelta
    ---------------- FRONTIÈRE PRÉ-8 ----------------
    Actor 8 Univers Makolo

Le gate de lancement Actor 8 est donc la connaissance explicite de trois choses :

1. quelles vérités Makolo existent réellement ;
2. lesquelles sont pertinentes pour l'Univers ;
3. sous quelle représentation minimale elles peuvent franchir la frontière sans devenir une copie de l'ORM.

## 2. État vérifié des Actors 1 à 7

| Actor | État Pré-8 | Contrat principal | Frontière conservée |
| --- | --- | --- | --- |
| 1 Prospecteur | FERMÉ / main | ObservationTarget | découvre où regarder, aucune vérité métier |
| 2 Observateur | FERMÉ / main | ObservationMaterial v2 | constate ce qui a réellement été obtenu |
| 3 Interpréteur | FERMÉ / main | InterpretedMaterial v1 | produit des candidats sémantiques, pas des vérités |
| 4 Résolveur | FERMÉ / main | ResolvedMaterial v1 | rapproche identités, faits, conflits et ambiguïtés |
| 5 Orchestrateur | FERMÉ / main | décisions vers owners | décide et coordonne, ne possède pas les domaines |
| 6 Persistateur | FERMÉ / main | services owner + persistance distribuée + Domain Events | durabilité sans base universelle parallèle |
| 7 Projecteur | FERMÉ / main (#282) | UniverseSnapshot / UniverseDelta | traduit les faits canoniques sans calculer l'Univers |

Actor 7 est intégré dans `main`. La Pré-8 est donc désormais auditée sur une chaîne 1→7 complète ; aucun runtime Actor 8 n'est encore activé.

## 3. Ce que la chaîne 1 → 7 garantit déjà

### 3.1 Acquisition et compréhension

Le Prospecteur ne fabrique pas une opportunité. Il trouve des cibles.

L'Observateur ne fabrique pas un fait métier. Il conserve le matériau réellement observé.

L'Interpréteur ne crée pas Activity, Occurrence, Requirement, Access ou autre objet canonique. Il produit des candidats structurés et leur evidence.

Le Résolveur ne mute pas le métier. Il établit des correspondances, nouvelles réalités candidates, ambiguïtés, conflits, updates possibles et non-résolutions.

### 3.2 Décision et vérité canonique

L'Orchestrateur consomme une résolution, revalide fraîcheur, source, autorité et contexte, puis route une mutation vers le domaine propriétaire.

Le Persistateur n'est pas une base centrale. La vérité durable reste chez les owners Django et leurs services, contraintes, historiques, blobs privés et Domain Events.

Le résultat du pipeline n'est donc pas :

    Web → Univers

mais :

    Web
      → observation
      → interprétation
      → résolution
      → décision applicative
      → vérité canonique owner
      → projection Univers

### 3.3 Projection

Le Projecteur v1 ne transforme aucun modèle backend en CorpsMakolo par simple correspondance nominale.

Son premier mapping retenu est volontairement plus faible :

    Activity + Occurrence
      → declared_realization_plan

Une Occurrence planifiée est donc une déclaration temporelle de réalisation possible. Elle n'est pas un CorpsRéalisation.

## 4. Garde-fous scientifiques non négociables

Les sources scientifiques consolidées imposent les règles suivantes.

### 4.1 Quatre niveaux distincts

    monde physique réel
      ≠ vue métier
      ≠ backend / BDD
      ≠ Univers Makolo

Le backend représente les faits applicatifs. L'Univers constitue un modèle formel construit.

Une ligne backend n'est pas automatiquement un CorpsMakolo.

Un champ backend n'est pas automatiquement une grandeur physique.

Une absence de donnée n'est pas une absence de réalité.

### 4.2 Composition, pas copie

Un CorpsMakolo peut être constitué à partir de plusieurs faits backend et métier.

Un même fait backend peut contribuer à plusieurs corps, relations, états ou paramètres de l'Univers.

La projection doit donc être compositionnelle.

### 4.3 CorpsMakolo

Le cadre CorpsMakolo consolidé retient comme critères minimaux :

- identité propre ;
- existence temporelle ;
- état propre ;
- position propre ;
- monolocalisation lorsque la position est applicable ;
- efficacité causale ;
- autonomie macroscopique suffisante.

La taxonomie consolidée comprend :

- CorpsActeur ;
- CorpsSite ;
- CorpsRessource ;
- CorpsRéalisation.

Engagement reste une relation, pas un cinquième type de corps.

### 4.4 Occurrence et Réalisation

Invariant Pré-8 :

    Occurrence ≠ CorpsRéalisation

Une Occurrence peut conduire à :

- zéro CorpsRéalisation si elle est annulée ou ne se réalise jamais ;
- un CorpsRéalisation dans un cas ordinaire observé ;
- plusieurs CorpsRéalisation si plusieurs déroulements autonomes existent.

Un déroulement non planifié peut aussi exister sans Occurrence préalable.

Actor 8 devra donc distinguer planification et réalisation effective.

### 4.5 Sujet et CorpsActeur

Un Profile, un Space ou un ExternalBeneficiary est un sujet, pas automatiquement un CorpsActeur unique.

Un même sujet peut contribuer à plusieurs manifestations corporelles :

- Présence ;
- Ancrage ;
- Canal.

Une résidence n'est pas une présence actuelle. Un canal email n'est pas une position physique. Un intérêt n'est pas une position.

### 4.6 Place et CorpsSite

Un Place backend n'est pas automatiquement un CorpsSite.

Un CorpsSite est un locus macroscopique où un phénomène d'action peut réellement être accompli et qui possède une identité opérationnelle suffisante.

Une URL, un écran ou une ligne Place n'est donc pas automatiquement un Site de l'Univers.

### 4.7 Fichier et CorpsRessource

Un fichier n'est pas automatiquement une Ressource de l'Univers.

Une Ressource doit avoir une identité macroscopique propre et pouvoir être localisée/manipulée dans l'action.

Plusieurs fichiers ou Proofs peuvent être des représentations d'une même Ressource.

### 4.8 Géométrie actuelle

La préparation géométrique la plus récente travaille avec :

    P = (λ, φ, ψ)

où λ et φ sont les coordonnées géographiques et ψ une coordonnée logique construite à partir d'un locus logique canonique.

Les anciennes formulations utilisant le couple (g,i) ne doivent pas être réintroduites dans la géométrie commune.

Une coordonnée manquante vaut ⊥, jamais zéro.

Trois coordonnées numériques ne suffisent pas à imposer R³ euclidien.

Le saut P → Q est primitif : aucune interpolation continue n'est supposée.

La formule exacte du poids élémentaire W et une éventuelle distance Makolo restent à déterminer.

### 4.9 Grandeurs et unités

Le socle métrologique actuel conserve le SI.

Grandeurs fondamentales retenues pour le cadre :

- longueur L ;
- temps t ;
- masse m ;
- quantité de matière n ;
- charge q ;
- température Θ.

Le courant est dérivé de charge/temps. Énergie et entropie sont dérivées.

Aucune unité Makolo distincte n'est introduite et aucune constante physique fondamentale n'est modifiée.

Aucun mapping direct comme prix → masse, popularité → charge ou activité → température n'est justifié.

## 5. Inventaire des faits canoniques backend disponibles

Cette section inventorie ce que le backend sait réellement aujourd'hui. Elle ne dit pas encore que chaque donnée doit entrer dans l'Univers.

### 5.1 Activity

Owner : Activities.

Faits canoniques disponibles :

- identité UUID ;
- propriétaire logique exactement Profile ou Space ;
- titre/description ;
- lifecycle : draft, published, cancelled, completed, archived ;
- visibilité ;
- relations vers Occurrences ;
- Topics explicites via ActivityTopic ;
- relations métier provenant des verticales.

Lecture Pré-8 :

- Activity fournit une identité durable et un contexte d'action ;
- Activity n'est pas actuellement retenue comme CorpsMakolo par défaut ;
- Activity n'est pas automatiquement SystèmeMakolo ;
- son statut ontologique reste OUVERT.

### 5.2 Occurrence

Owner : Activities.

Faits canoniques disponibles :

- Activity propriétaire ;
- lifecycle : draft, scheduled, cancelled, completed ;
- timing kind : exact, date_only, all_day ;
- start_date / start_time ;
- end_date / end_time ;
- timezone ;
- schedule éventuel ;
- relations vers Places ;
- revision technique via updated_at.

Lecture Pré-8 :

- données temporelles sémantiques très fortes ;
- le futur déclaré est distinct du futur calculé ;
- updated_at reste un temps technique ;
- Occurrence est une source RETENUE pour declared_realization_plan ;
- elle n'est pas une preuve de réalisation effective.

### 5.3 Geography — Place

Owner : Geography.

Faits disponibles :

- identité ;
- nom ;
- locality / administrative area / country ;
- latitude + longitude optionnelles mais couplées ;
- timezone ;
- actif/inactif.

Lecture Pré-8 :

- longitude/latitude sont des candidats naturels pour λ/φ lorsqu'une réalité de l'Univers possède effectivement ce Place comme position ;
- Place seul ne suffit pas à définir un CorpsSite ;
- adresse textuelle complète ne doit pas franchir la frontière sans besoin.

### 5.4 Geography — Zone

Owner : Geography.

Faits disponibles :

- zone administrative ou rayon ;
- centre Place pour zone radius ;
- radius_m ;
- périmètre administratif textuel ;
- actif/inactif.

Lecture Pré-8 :

- peut participer à des contraintes spatiales ou champs futurs ;
- n'est pas une position ponctuelle ;
- n'est pas un CorpsSite par défaut.

### 5.5 Profile / UserProfile

Owner : Accounts.

Faits disponibles notamment :

- identité globale ;
- préférences personnelles ;
- langue/timezone ;
- champs de profil ;
- quelques données géographiques déclaratives ;
- relations vers Interests/OpenTo ;
- Journeys, Access, Mandates, etc.

Lecture Pré-8 :

- Profile est un SujetActeur ;
- Profile n'est pas un CorpsActeur 1:1 ;
- city/lat/lon de profil ne doivent pas être interprétés comme présence actuelle ;
- PII ne franchit pas la frontière sans nécessité scientifique explicite.

### 5.6 ExternalBeneficiary

Owner : Journeys.

Faits disponibles :

- identité minimale d'un bénéficiaire réel sans compte ;
- nom/contact à but applicatif ;
- liens Journey/Access.

Lecture Pré-8 :

- peut être source d'un SujetActeur externe ;
- aucune donnée de contact ne devient automatiquement CanalMakolo sans contrat explicite ;
- aucune PII brute dans l'entrée Univers v1.

### 5.7 Organization / Space

Owner : Organizations.

Faits disponibles :

- identité collective ;
- état ;
- identité publique ;
- Activities opérées ;
- Teams/relations ;
- OpenTo éventuels ;
- géographie selon les surfaces existantes.

Lecture Pré-8 :

- Space est un SujetActeur collectif ;
- Space n'est pas automatiquement un CorpsActeur unique ;
- siège/agence/canal doivent être distingués s'ils deviennent Ancrage/Présence/Canal.

### 5.8 Journey

Owner : Journeys.

Faits disponibles :

- initiateur ;
- bénéficiaire Profile ou External ;
- Activity ;
- Occurrence optionnelle ;
- workflow ;
- lifecycle ;
- expires/submitted/confirmed/started/fulfilled/cancelled timestamps ;
- transitions historiques ;
- requests, steps, blockers, artifacts et autres sous-domaines lorsque présents.

Lecture Pré-8 :

- forte candidate comme relation/processus/état d'engagement ;
- ne devient pas CorpsRéalisation automatiquement ;
- certains started_at / fulfilled_at peuvent plus tard contribuer à établir qu'un processus réel a effectivement eu lieu, mais le critère scientifique reste à consolider.

### 5.9 Requirement

Owners : Requirements et domaines versionnés qui les utilisent.

Faits disponibles :

- condition explicite ;
- mode/évaluation selon domaine ;
- policies de réutilisation ;
- assessments propriétaires ;
- liens vers Journey/Opportunity/Service selon le contexte.

Lecture Pré-8 :

- CANDIDAT fort pour condition de possibilité ;
- Requirement n'est pas Readiness ;
- possession de Proof/Resource/Artifact ne signifie pas satisfaction.

### 5.10 Proof / Credential Trust

Owner : Trust.

Faits disponibles :

- fait atomique établi ;
- sujet ;
- portée ;
- lifecycle / vérification ;
- credentials métier distincts.

Lecture Pré-8 :

- peut contribuer à l'état ou à la satisfaction d'une condition lorsque le domaine propriétaire l'a explicitement établi ;
- Proof n'est pas une Ressource par définition ;
- aucune donnée sensible brute n'est projetée.

### 5.11 ActivityResource / JourneyArtifact / PersonalAsset

Owners : Preparation, Journeys, Personal Assets.

Faits disponibles :

- identités et versions ;
- nature text/url/file selon Resource ;
- scope Activity/Occurrence pour ActivityResource ;
- sensibilité/visibilité ;
- historique de versions ;
- fichiers privés lorsque présents.

Lecture Pré-8 :

- CANDIDAT pour CorpsRessource uniquement lorsqu'une identité macroscopique, une localisation et un rôle manipulable sont établis ;
- le fichier binaire lui-même n'est pas le corps ;
- plusieurs représentations peuvent correspondre à une même Ressource.

### 5.12 Access

Owner : Access.

Faits disponibles :

- bénéficiaire Profile ou External ;
- Activity ;
- Occurrence optionnelle ;
- Journey optionnelle ;
- lifecycle : pending, valid, used, cancelled, revoked, expired, transferred ;
- valid_from / valid_until ;
- single_use ;
- provenance d'émission.

Lecture Pré-8 :

- CANDIDAT fort comme droit/condition/relation modifiant l'ensemble des actions accessibles ;
- Access n'est pas AccessCredential ;
- le droit peut être pertinent pour une trajectoire sans devenir un CorpsMakolo.

### 5.13 AccessCredential

Owner : Access.

Lecture Pré-8 :

- REJETÉ de la projection scientifique v1 comme contenu ;
- QR, token, public_id et autres représentations secrètes ne doivent pas franchir la frontière ;
- seule l'existence d'un droit Access éventuellement pertinente appartient au niveau supérieur.

### 5.14 AccessUse

Owner : Access.

Faits disponibles :

- Access concerné ;
- résultat de contrôle ;
- occurrence/activity de contrôle selon workflow ;
- temps d'usage ;
- actor opérationnel lorsque applicable.

Lecture Pré-8 :

- CANDIDAT comme observation d'une action réelle ;
- peut contribuer à différencier planification et réalisation ;
- ne suffit pas universellement à prouver toute la constitution d'un CorpsRéalisation.

### 5.15 Capacity

Owner : Capacity.

Faits disponibles :

- CapacityPool Activity/Occurrence ;
- total_quantity ou capacité illimitée ;
- réservations de quantité ;
- états held, committed, released, expired ;
- expirations/commits.

Lecture Pré-8 :

- CANDIDAT comme contrainte quantitative et ressource partagée ;
- Capacity répond à combien ;
- elle ne devient ni Placement, ni masse, ni quantité de matière sans construction scientifique distincte.

### 5.16 Placement / Live Queue

Owner : Operations.

Lecture Pré-8 :

- Placement répond où dans une capacité ;
- Live Queue répond attendre son tour avec le droit pertinent ;
- CANDIDAT pour état opérationnel/localisation relative ;
- ne doit pas être confondu avec Capacity ou Waitlist.

### 5.17 Dossier

Owner : Objectives.

Faits disponibles :

- propriétaire Profile XOR Space ;
- lifecycle ;
- deadline ;
- Journeys liées ;
- dépendances explicites entre Journeys ;
- assignments séparés de l'autorité.

Lecture Pré-8 :

- CANDIDAT comme frontière de système ou composition orientée objectif ;
- pas CorpsMakolo par défaut ;
- les dépendances explicites sont des relations potentiellement pertinentes.

### 5.18 Project

Owner : Objectives.

Faits disponibles :

- propriétaire Profile XOR Space ;
- horizon starts_on / ends_on ;
- lifecycle ;
- Dossiers liés.

Lecture Pré-8 :

- OUVERT comme contexte/horizon de système ;
- pas task manager ;
- pas CorpsMakolo automatique.

### 5.19 Mandate / Permission / Role

Owner : Authorization.

Faits disponibles :

- Profile ;
- Role ;
- scope explicite ;
- cible Space/Group/Activity/Dossier ;
- valid_from / valid_until ;
- active/suspended/revoked ;
- provenance.

Lecture Pré-8 :

- CANDIDAT comme relation d'autorité pouvant ouvrir/interdire des actions ;
- Membership ne remplace jamais Mandate ;
- aucune composition Univers ne doit transférer l'autorité.

### 5.20 Group / Membership / Team

Owners : Groups / Organizations.

Lecture Pré-8 :

- groupes et memberships peuvent être des relations de contexte, appartenance ou éligibilité ;
- REJETÉ comme autorité implicite ;
- projection future seulement si un phénomène étudié l'exige.

### 5.21 Topics / Interests / OpenTo

Owner : Topics.

Faits disponibles :

- Topic canonique ;
- Interest explicitement déclaré ;
- OpenTo volontaire et scoped ;
- ActivityTopic.

Lecture Pré-8 :

- utiles pour sémantique/contexte ;
- REJETÉS comme position, distance, masse, charge ou interaction physique par défaut ;
- un intérêt élevé ne crée pas une chaîne causale ;
- OpenTo peut constituer une condition de sollicitation, mais pas une capacité prouvée.

### 5.22 Commerce / Payment

Owners : Commerce / Payments.

Faits disponibles :

- offres/ordres ;
- obligations ;
- paiements/refunds ;
- états transactionnels ;
- historiques/ledger.

Lecture Pré-8 :

- OUVERT pour Univers ;
- peut devenir condition, transfert ou événement dans certains phénomènes ;
- montant/prix n'est pas masse ni énergie ;
- secrets provider restent exclus.

### 5.23 Notifications / Analytics / logs / Presentation

Lecture Pré-8 :

- REJETÉS comme primitives de l'Univers ;
- ce sont des effets, observations techniques ou projections ;
- ils ne remplacent jamais les faits propriétaires.

### 5.24 Readiness

Lecture Pré-8 :

- REJETÉ comme primitive ;
- Readiness est une projection dérivée ;
- l'Univers doit recevoir les faits qui causent la possibilité ou l'impossibilité, pas une seconde vérité Readiness opaque.

## 6. Registre de projection Pré-8

### 6.1 RETENU maintenant

| Fait backend | Projection permise | Justification |
| --- | --- | --- |
| Occurrence + Activity identity/context | declared_realization_plan | planification réelle et temporelle sans prétendre à la réalisation |
| Occurrence start/end/timing/timezone | temporal declaration avec KNOWN/UNKNOWN/NOT_APPLICABLE | sémantique temporelle canonique explicite |
| lifecycle Occurrence | lifecycle de la déclaration | cancelled/completed ne créent pas un CorpsRéalisation |
| source revision technique | fence/version de projection seulement | sert à éviter un rollback de projection, pas comme temps physique |

C'est volontairement le seul mapping scientifique/ontologique implémenté par Actor 7 v1.

### 6.2 CANDIDAT pour extensions après Pré-8

| Donnée | Usage Univers candidat | Garde-fou |
| --- | --- | --- |
| Place longitude/latitude | λ/φ d'une réalité réellement localisée | Place ≠ CorpsSite ; relation de localisation requise |
| OccurrencePlace | localisation d'un plan ou d'un futur déroulement | ne prouve pas présence réelle |
| Journey started/fulfilled + Operations/AccessUse | evidence d'un déroulement réel | critères de CorpsRéalisation à fermer avant création |
| Profile/Space/External + faits explicites de présence/ancrage/canal | source de CorpsActeur | sujet ≠ corps ; aucune inférence depuis city/profile seul |
| ActivityResource/JourneyArtifact/PersonalAsset | source potentielle de CorpsRessource | fichier ≠ ressource ; identité/autonomie requises |
| Requirement | condition de possibilité | Requirement ≠ Readiness |
| Access | relation/droit modifiant les transitions accessibles | credential exclu |
| Capacity | contrainte quantitative | Capacity ≠ Placement ≠ masse |
| Mandate | relation d'autorité | Membership/Assignment insuffisants |
| Dossier dependencies | relations entre trajectoires/démarches | Dossier ≠ task manager |

### 6.3 OUVERT — exige travail scientifique ou modèle canonique supplémentaire

- construction canonique de ψ à partir des faits backend ;
- correspondance Activity ↔ SystèmeMakolo ;
- critères backend suffisants pour la naissance et la fin d'un CorpsRéalisation ;
- modèle explicite Presence / Anchorage / Channel pour les SujetActeurs ;
- critères génériques SitePresence / SiteDeplacement / SiteTransfert / SiteTransformation / SiteRelation ;
- identité CorpsRessource au-delà des fichiers et versions ;
- projection de Dossier/Project comme systèmes ou frontières ;
- rôle précis de Payment/Commerce ;
- construction des espèces Makolo nécessaires à la quantité de matière ;
- constitution I/E/H et coefficients μσ nécessaires à la masse ;
- définition opérationnelle de charge depuis des asymétries causales réellement observables ;
- température comme agitation interne mesurable ;
- champs et interactions ;
- énergie, forces, flux, courant ;
- poids géométrique W et distance éventuelle.

### 6.4 REJETÉ comme mapping direct

Les transformations suivantes sont interdites sans nouvelle démonstration scientifique :

- Profile → un CorpsMakolo unique ;
- Profile → VéhiculeMakolo par simple type backend ;
- Activity → SystèmeMakolo par simple classe Django ;
- Occurrence → CorpsRéalisation ;
- Place → CorpsSite ;
- fichier → CorpsRessource ;
- Interest → interaction physique ;
- popularité/likes/followers → charge ;
- prix/montant → masse ou énergie ;
- Capacity.total_quantity → masse ou quantité de matière ;
- Readiness → état primitif Univers ;
- created_at/updated_at → temps physique ou temps métier ;
- Permission/Membership → Access ;
- AccessCredential → Access ;
- valeur inconnue → zéro ;
- longitude/latitude/ψ → distance euclidienne 3D automatique.

## 7. Données manquantes ou insuffisamment canoniques avant les extensions d'Actor 8

### 7.1 Position logique ψ

Le cadre géométrique récent exige ψ = E_I(locus logique canonique).

Le backend ne fournit pas encore, dans la frontière Actor 7 v1, un contrat canonique de locus logique suffisamment stable pour calculer ψ.

Décision : OUVERT. Actor 8 ne doit pas inventer ψ depuis un slug, un ID de modèle, une URL ou un score.

### 7.2 Présence réelle d'un acteur

UserProfile peut contenir ville ou latitude/longitude déclaratives, mais cela ne prouve pas une présence actuelle.

Décision : OUVERT.

Pour créer un CorpsActeur Presence, Makolo aura besoin d'un fait explicitement défini comme présence dans un contexte d'action, avec temporalité et confidentialité.

### 7.3 Ancrages et canaux

Certaines données backend peuvent jouer le rôle d'adresse, siège, agence, email ou téléphone. Il manque cependant un contrat générique disant lesquelles constituent réellement un Ancrage ou un Canal dans l'Univers.

Décision : OUVERT.

### 7.4 Réalisation effective

Occurrence représente la réalisation prévue/décrite, pas son déroulement réel.

Operations, AccessUse, Journey lifecycle et d'autres faits peuvent constituer des evidences, mais aucun mapping générique ne doit décider seul qu'un CorpsRéalisation est né.

Décision : OUVERT.

### 7.5 Sites d'action

Place indique un emplacement. Il ne précise pas, à lui seul, quel phénomène constitutif y est possible.

Décision : OUVERT.

Une future projection Site devra savoir si le locus est de type Presence, Deplacement, Transfert, Transformation ou Relation dans le phénomène étudié.

### 7.6 Ressources

Makolo possède des documents et ressources, mais leur identité macroscopique et leur localisation logique/physique ne sont pas universellement explicites.

Décision : OUVERT.

### 7.7 Grandeurs macroscopiques

Le backend possède de nombreux nombres, états et relations. Cela ne suffit pas à calculer masse, charge ou température.

La masse Makolo actuelle exige notamment une constitution d'espèces et des coefficients μσ ; cette structure n'est pas encore une projection backend disponible.

Décision : OUVERT.

## 8. Données que l'Univers ne doit jamais demander directement

Actor 8 ne doit pas contourner Actor 7 pour lire :

- modèles Django ;
- QuerySets ;
- blobs Observer ;
- InterpretedMaterial ;
- ResolvedMaterial ;
- secrets AccessCredential ;
- payment provider credentials ;
- documents privés bruts ;
- PII non nécessaire ;
- états Presentation ;
- analytics/logs comme vérité.

Actor 8 reçoit uniquement des structures Actor 7.

## 9. Contrat minimum d'entrée Actor 8

La frontière Actor 7 en PR #282 retient deux formes partageant la même sémantique.

### UniverseSnapshot

But :

- bootstrap ;
- rebuild ;
- comparaison déterministe.

Propriétés principales :

- scope_ref ;
- strategy_version ;
- roots ;
- semantic_fingerprint.

### UniverseDelta

But :

- mise à jour incrémentale ciblée.

Propriétés principales :

- scope_ref ;
- strategy_version ;
- change_ref ;
- upserts ;
- removals.

### UniverseProjectionRoot

Peut transporter :

- source_facts ;
- plans ;
- bodies ;
- relations ;
- conditions ;
- states ;
- parameters.

Pré-8 impose :

> Une collection prévue par le contrat reste vide tant qu'un mapping scientifique correspondant n'est pas RETENU.

L'existence de bodies[] ne donne donc aucun droit à Actor 7 ou Actor 8 de fabriquer des CorpsMakolo.

## 10. KNOWN, UNKNOWN et NOT_APPLICABLE

La frontière doit préserver trois états distincts :

- KNOWN : valeur réellement connue ;
- UNKNOWN : la grandeur/champ est applicable mais la valeur n'est pas connue ;
- NOT_APPLICABLE : la grandeur/champ ne s'applique pas à cette situation.

Exemple temporel :

- DATE_ONLY → heure UNKNOWN ;
- ALL_DAY → heure NOT_APPLICABLE.

Cette distinction doit être généralisée aux futures projections lorsque nécessaire.

## 11. Temporalité Pré-8

Toujours distinguer :

### Temps métier

Exemples :

- Occurrence start/end ;
- Journey started/fulfilled ;
- Access valid_from/valid_until ;
- deadline Dossier ;
- Mandate valid_from/valid_until.

### Temps technique

Exemples :

- created_at ;
- updated_at ;
- ingestion time ;
- projection revision.

### Temps de connaissance

Exemples :

- observed_at ;
- interpretation run ;
- resolution run.

Actor 8 ne doit pas mélanger ces axes.

Une nouvelle Observation peut changer K(t), ce que Makolo sait, sans changer X(t), l'état réel du corps.

## 12. Confidentialité de la frontière Univers

La projection suit le principe de divulgation minimale.

Exclure par défaut :

- email ;
- téléphone ;
- adresse complète si les coordonnées ou un locus opaque suffisent ;
- nom du Profile ;
- QR/token ;
- credentials ;
- documents bruts ;
- private notes ;
- secrets Payment ;
- données privées sans nécessité de calcul.

Une projection collective doit pouvoir utiliser une identité interne opaque ou un signal agrégé lorsque l'identité humaine n'est pas nécessaire.

## 13. Change signals disponibles

Le Domain Event catalog actuel possède déjà de nombreux signaux potentiellement utiles :

- lifecycle Activity/Occurrence ;
- Journey transitions ;
- Journey steps/blockers/artifacts ;
- Dossier/Project relations ;
- Placement / Queue / Checkpoint ;
- Resource/Form ;
- Opportunity ;
- Commerce/Payment ;
- Access ;
- Sharing ;
- Subscription, etc.

Pré-8 retient cependant la règle Actor 7 :

> le Domain Event signale qu'un fait a changé ; le Projecteur recharge le snapshot owner canonique au lieu de traiter le payload comme vérité complète.

Actor 7 v1 ajoute le signal occurrence.created et utilise aussi les transitions Occurrence pertinentes.

Aucun consumer automatique vers Actor 8 ne doit être activé avant qu'une cible durable Actor 8 existe.

## 14. Gate de démarrage Actor 8

Actor 8 ne peut être lancé que lorsque les conditions suivantes sont réunies.

### Gate G1 — chaîne 1 → 6

RETENU : satisfait sur main au moment de l'audit Pré-8.

### Gate G2 — Actor 7

RETENU : satisfait.

- PR #282 entièrement verte ;
- merge effectué dans `main` ;
- main post-merge réconcilié comme base de cette note.

### Gate G3 — entrée v1 figée

RETENU pour le démarrage minimal :

- declared realization plans ;
- temporalité canonique Occurrence ;
- lifecycle de la déclaration ;
- identity/context Activity minimal ;
- KNOWN / UNKNOWN / NOT_APPLICABLE ;
- snapshot + delta ;
- revision fence.

### Gate G4 — absence d'invention

Actor 8 doit accepter qu'au démarrage :

- bodies puisse être vide ;
- relations puisse être vide ;
- conditions puisse être vide ;
- states puisse être vide ;
- parameters puisse être vide.

Il ne doit pas remplir ces collections par analogie.

### Gate G5 — registre des inconnues

Actor 8 doit prendre comme inconnues explicites :

- ψ canonique ;
- CorpsActeur effectifs ;
- CorpsSite ;
- CorpsRessource ;
- CorpsRéalisation ;
- Activity ↔ SystèmeMakolo ;
- grandeurs macroscopiques calculables ;
- interactions/champs ;
- W/distance.

## 15. Ordre recommandé après Pré-8

La prochaine étape ne doit pas être « implémenter toute la physique ».

Actor 8 devra procéder par incréments scientifiques :

1. accepter et stocker/appliquer la projection v1 sans Django ;
2. représenter correctement les declared realization plans ;
3. définir le modèle interne de situation et de temps ;
4. ajouter une nouvelle famille de faits seulement lorsqu'un mapping scientifique est RETENU ;
5. reprojeter via une nouvelle strategy version ;
6. tester chaque extension avec contre-exemples.

Ordre de projection candidat :

    temporalité déclarée
      ↓
    géographie explicite
      ↓
    loci logiques ψ
      ↓
    manifestations Actor/Site/Resource
      ↓
    critères de Réalisation effective
      ↓
    relations/conditions
      ↓
    systèmes
      ↓
    grandeurs macroscopiques
      ↓
    champs/interactions/dynamique

Cet ordre reste dépendant des résultats scientifiques. Il n'est pas une obligation d'implémentation.

## 16. Tests de non-régression Pré-8

Toute extension Actor 7/8 devra échouer si elle réintroduit l'une de ces erreurs :

1. même titre Activity ⇒ même corps ;
2. Profile ⇒ corps unique ;
3. Occurrence scheduled ⇒ CorpsRéalisation ;
4. Place ⇒ Site ;
5. fichier ⇒ Ressource ;
6. missing ⇒ zero ;
7. updated_at ⇒ temps physique ;
8. intérêt ⇒ interaction ;
9. prix ⇒ masse ;
10. capacité ⇒ quantité de matière ;
11. Membership ⇒ autorité ;
12. AccessCredential ⇒ Access ;
13. Readiness ⇒ fait primitif ;
14. λ,φ,ψ ⇒ R³ euclidien automatique ;
15. delta ancien ⇒ écrase une révision plus récente.

## 17. Verdict final Pré-8

### Actors 1 à 6

FERMÉS et intégrés dans main.

### Actor 7

FERMÉ / intégré dans `main` pour la fondation minimale retenue.

Son choix le plus important est correct :

> il projette actuellement une déclaration de réalisation, pas un CorpsMakolo inventé.

### Données immédiatement admissibles pour Actor 8

RETENU :

- identité technique des projections ;
- références canoniques minimales Activity/Occurrence ;
- planification temporelle Occurrence ;
- lifecycle de la déclaration ;
- distinction KNOWN/UNKNOWN/NOT_APPLICABLE ;
- revisions/fingerprints techniques.

### Données prometteuses mais non encore projetables automatiquement

CANDIDAT :

- géographie ;
- conditions Requirement ;
- Access ;
- Capacity ;
- Journey/Operations/AccessUse comme evidence d'action réelle ;
- Mandates ;
- dépendances Dossier ;
- Ressources sous critères ontologiques.

### Données encore scientifiquement ouvertes

OUVERT :

- ψ ;
- CorpsActeur concrets ;
- CorpsSite ;
- CorpsRessource ;
- CorpsRéalisation ;
- statut Activity/Système ;
- masse/charge/température calculables depuis le backend ;
- champs/interactions ;
- énergie/dynamique ;
- W/distance.

### Mappings directs interdits

REJETÉ :

- ORM → CorpsMakolo 1:1 ;
- score produit → grandeur physique ;
- projection dérivée → vérité primitive ;
- secret/PII → Univers sans nécessité ;
- planification → réalisation.

## 18. Critère de fermeture de la Pré-8

La Pré-8 est fermée lorsque :

- Actor 7 est intégré avec CI verte — satisfait ;
- cette note est réconciliée avec le main post-Actor7 — satisfait ;
- le mapping v1 reste limité aux données réellement retenues ;
- les données candidates et manquantes sont explicitement enregistrées ;
- aucun besoin Actor 8 n'a forcé un nouveau champ métier artificiel ;
- Actor 8 peut démarrer uniquement à partir de UniverseSnapshot / UniverseDelta.

Jusqu'à cette fermeture, les travaux scientifiques Univers peuvent continuer sur papier et documents de recherche, mais aucun runtime Actor 8 ne doit inventer des données absentes de la frontière Projecteur.