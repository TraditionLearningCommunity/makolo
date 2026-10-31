# MT1 — Cartographie fermée et vérifiable des N1 → N2 → N3 de Métier Space

**Décision : MT1 close comme INVENTAIRE ET ATTRIBUTION DES ÉCARTS, non comme achèvement du runtime.**
**Date : 31 octobre 2026.** Dépôt : TraditionLearningCommunity/makolo. PR unique : #522, branche fix/discover-a-continuation-context-20261014.
**Photographie de contrôle initiale : PR HEAD f469341b52238d473234d5f9fd8ce0e4523b9b1a ; main HEAD d0f0ec421c94c255fa4c0acd3509938a70c6322f.** La PR est concurrente et peut évoluer après cette photographie. Réconcilier le HEAD à MT2.

## 0. Ce que « fermer MT1 » veut dire

MT1 n'est pas la livraison des parcours. Ce document **termine leur vérification statique à un niveau exploitable** : chaque famille a un N1, des N2 décidés, les destinations et permissions prouvées quand disponibles, les lacunes nommées et un responsable de fermeture MT2–MT8. Les « partiels » dans les lignes ci-dessous **sont des constats du produit**, et non une vérification oubliée.

Aucun Django, Flutter, PostgreSQL, navigateur ou CI exécuté dans cet inventaire. On ne prétend donc pas que les routes trouvées marchent pour toutes les données. Un audit du code ne garantit pas une qualité produit « 2027 », une absence de bug ou une couverture fonctionnelle exhaustive de tout Makolo : ce sont des gates de MT8.

**Sources :** code actuel du Work dans organizations/api/space_work_projection.py, organizations/space_work_composition.py, organizations/space_work_web.py, organizations/space_retrieval_detail_web.py, organizations/urls.py ; API organizations/api/urls.py et space_request_views.py ; propriétaires services/operator_views.py, transport/console_views.py, organizations/console_views.py, presentations/urls.py, preparation/urls.py, funding/urls.py, obtention/urls.py, groups/urls.py ; Flutter space_work_surface.dart, space_work_collection_screen.dart, space_repository.dart, space_shell_routes.dart, app/router.dart, continuity/space_retrieval_owner_screen.dart et space_request_screen.dart. Contrats : Makolo_Contrat_Metier_Space_Gele_2026-10-06.md, Makolo_Metier_Experience_Grammaire_Unique_Archetypes_Profondeurs_Contrat_Fige_2026-10-31.md, et huit contrats UX Métier archétype du 8 octobre.

## 1. Notation et échelle de preuve

- **R — reconnu** : propriétaire, route ou source **retrouvés dans le code**, sans prétendre à un parcours validé.
- **L — lecture** : N2 consultable ou sélection détaillée, mais profondeur métier incomplète.
- **A — action owner** : une mutation/action propriétaire est codée et recontrôle l'autorité ; la liaison depuis Métier doit parfois encore être créée.
- **B — branchement manquant** : fonctionnalité propriétaire disponible quelque part, mais **pas correctement proposée depuis le N2/N1 Métier**.
- **D — profondeur dédiée manquante** : une page ou composition humainement nécessaire n'est pas démontrée ; ne pas fabriquer un modèle.
- **C — conditionnel** : profondeur légitime seulement si sa réalité propriétaire est effectivement présente.
- **X — anti-feature / hors Métier** : ne doit pas être fabriquée.
- **T — test non exécuté** : preuve de source, pas preuve d'exécution.

« Partiel » est remplacé par un diagnostic opérationnel **L, B, D, C** et une affectation précise.

## 2. Socle transversal vérifié

| Contrat / élément | Preuve exacte dans le code | Verdict MT1 | Suite |
| --- | --- | --- | --- |
| Huit N1 linguistiques | organizations/space_work_composition.py, dictionnaires des huit SpaceArchetype ; presentations/grammaire des sections | **R**. Les huit grammaires sont codées, sans huit applications. | MT7/8 : apparence et parcours |
| N1 owner-backed | organizations/api/space_work_projection.py : Activity, Occurrence, Offer, CommerceOrder, Journey, TransportRoute, Vehicle | **R**. Le footprint ne transfère aucun droit. | MT2 : complétude des relations |
| Scope et sélection | build_space_work_projection(profile, space, responsibility_key, source_kind, source_id, section_key, offset) ; route API workspaces/<slug>/work/ | **R**. Filtre l'identité avant preview ; scope Mandate Activity ; authentification. | MT2 : contrat stable de depth/handoff |
| Permissions métier | ACTIVITY_VIEW/MANAGE, OPERATIONS_VIEW, COMMERCE_VIEW, REQUESTS_VIEW, SERVICES_CASES_VIEW_* ; ORDERS_VIEW séparé ; droit Space direct pour flotte | **R** ; aucune appartenance Group/Team comme autorité. | MT8 : tests de périmètre |
| Projection de la capacité | capacity.selectors.capacity_availability_many pour pools réellement attachés à Offer/Departure | **R** ; Capacity ≠ Placement ≠ Payment. | MT5 : action et lecture N2 |
| Jour J | Occurrence + permission ACTIVITY_OPERATIONS_VIEW + phase d'arrivée/live ; liens vers Operations owner | **R conditionnel** ; aucune activation fictive. | MT3–6/7 : bons handoffs |
| Media reconnaissable | organizations/space_work_media.py + presentations.media_selectors ; seulement use publié et accessible publiquement | **R conditionnel** ; pas de Resource privée promue | MT6/7 : rendu natif |
| Web N1 | organizations/space_work_web.py + templates/organizations/space/work.html | **R** ; sections projetées, quelques handoffs, pas une preuve de N2 complet. | MT3–6, MT7 |
| Web Activity/Occurrence lecture | URLs organizations:space-retrieval-activity-detail et space-retrieval-occurrence-detail, implémentées dans space_retrieval_detail_web.py | **L** : titre, statut, résumé, date. Les liens de Métier vont souvent plutôt à console-activity-detail. | MT3/4/6 |
| Web commande lecture | organizations:space-retrieval-order-detail ; ORDER_VIEW + Space/Activity croisés | **L** : état/référence, pas toute préparation/paiement/remise. | MT5 |
| Web Services opérateur | services:operator-case et actions step/blocker/assignment/evidence/review ; contrôle de scope dans services/operator_views.py | **A** ; non universellement disponible pour chaque mandat. | MT4 : composition/intégration |
| Web transport | organizations:console-transport-route-detail ; console-transport-departure-detail ; transport/console_views.py | **L/A selon surface** ; route/départ dédiés, créations owner présentes ; véhicule = console de collection seulement. | MT5 |
| Web offres | organizations:console-offers dans console_views.py | **B** : destination de console/collection, pas preuve d'un détail Offre contextualisé. | MT5 |
| Demande d'inscription Space API | organizations_api:workspace-request-detail, GET/POST ; decisions via approve_request/reject_request avec ACTIVITY_REQUESTS_VIEW/DECIDE | **A** : propriétaire et revalidation TOCTOU réels. | MT4/7 : handoff depuis Work |
| Flutter N1 | mobile/lib/features/space/space_work_surface.dart ; repo workSource/watchWork/refreshWork ; app/router.dart | **R** : sections et cartes, état synced local-first. | MT7 : composition, adaptive |
| Flutter pagination | space_work_collection_screen.dart : section+offset, validation Space/responsibility, déduplication, invalidation d'acteur | **R** ; collection n'est pas automatiquement un N2 métier. | MT7 |
| Flutter détail owner Space | spaceOwnerRoute dans presentation/contracts/space_presentation.dart + app/router.dart + continuity/space_retrieval_owner_screen.dart | **L** : activité, occurrence, offer, journey, commande, route, véhicule ; frais GET par owner. Affiche résumé/facts mais pas les N3 multiples spécialisés. | MT3–7 |
| Flutter demande et décision | mobile/lib/features/space/space_request_screen.dart + route /space/requests/:id | **A** : lecture propriétaire, confirmation, décision conditionnelle, refus/rafraîchissement sûr. | MT4/7 : entrée depuis Métier |
| Flutter Jour J/Live | /space/occurrences/:id/day-of et /live dans mobile/lib/app/router.dart + space_occurrence_screen.dart | **R conditionnel**, le client consomme owner actuel. | MT7/8 |
| Flutter autres profondeurs | mobile/lib/features/journey, access, preparation, questionnaires, commerce, payments, resources, funding | **R ailleurs dans l'app** ; usage personnel/acteur et permissions ne doivent pas être supposés utilisables pour agir au nom du Space. | MT2/4–7 : qualification de handoff |
| Perspectives métier multiples | business_world.perspectives contient principalement primary dans composition.py ; reading_groups dérivés | **D** lorsque multi-perspectives utiles ; ne pas fabriquer une perspective par verticale. | MT2 |
| Coverage honnête | _empty_section crée coverage_state established ; la racine marque composition_state established et perspective primary partial | **D** : pas encore une qualité établie par source/état d'indisponibilité ; vide ne vaut pas toujours certitude complète. | MT2 |
| Retour N3→N2 Métier | Web retrieval owner retourne à Search ou History dans _back_url, pas automatiquement à Work ; Flutter utilise push/pop mais sans contexte riche Métier | **B** : pas de contrat complet origine/section/filtre/scroll/selected/multiple N3 | MT2/7 |
| Recherche/tri/filtres Métier | Search Space et History existent ; Work N1 Flutter n'a que liens Search/History et section/offset | **B** : moteur transversal présent, mais recherche/facettes Métier contextuelles non closes. | MT2/7 |
| Actions de création | payload Work capabilities.create_activity ; aucun creator contextuel pour les huit métiers n'est établi par cette seule capacité | **B/C** : pas de CTA universel « Créer ». | MT2 puis MT3–6 |

## 3. Traçabilité par archétype — parcours détaillés

Les colonnes indiquent **owner N2**, **N3 réellement codés/possibles**, **état Web**, **état Flutter**, **écart exact**. Une absence d'action n'est pas une anomalie si l'owner n'en a pas.

### G1 / MT3 — Generic : Activités

| N2 retenu | N3 / owner | Web | Flutter | Écart exact |
| --- | --- | --- | --- | --- |
| **Activité** (Activity) | modifier/gérer par Activity ; relations Occurrence, Resources, éventuelle verticale | R console-activity-detail ; L retrieval-activity-detail | L SpaceRetrievalOwnerScreen pour activity, MPS parfois | **B/D** : composer les relations et faire émerger les N3 réellement disponibles, sans menu universel |
| **Occurrence** | Activity/Occurrence, préparation, operations, Jour J si phase et droit | L retrieval-occurrence ; R console Activity ; R Jour J séparé | L owner occurrence ; R Jour J distinct | **B** : relation au parent, contrôle d'état et retour |
| **Demande/Journey**, si owner | Journey et JourneyRequest sous permission | R source API quand ACTIVITY_REQUESTS_VIEW ; actions owner dans console/route Request | L journey sélectionné ; A SpaceRequestScreen séparé | **B** : lien exact entre Journey et Request (ne pas substituer id Journey à id Request) |
| **Lieu**, si structurant | Geography owner et Occurrences autorisées | R console-places ; pas de N2 lieu dans Métier prouvé | pas de N2 lieu depuis Work prouvé | **C/D** : seulement si le lieu est une réalité opérée, droits et relations exacts |

### G1 / MT3 — Community : Initiatives

| N2 retenu | N3 / owner | Web | Flutter | Écart exact |
| --- | --- | --- | --- | --- |
| **Initiative** (Activity contextualisée) | Occurrences, ressources, actions réelles, service/obtention/funding si existants | R Activity console ; L propriétaire générique | L activity owner | **D** : vrai langage collectif et relations, sans nouveau modèle Initiative |
| **Action terrain / réalisation** (Occurrence) | préparation, lieu, accès, Jour J si admissible | L occurrence, R Jour J | L occurrence, R Jour J | **B** : continuité contextualisée à l'initiative |
| **Demande ou contribution** | JourneyRequest / Funding owner, **seulement si présent** | A demandes ; R funding detail/manage/contribute ailleurs | A demande native ; funding contribution ailleurs mais non Space Work prouvé | **C/B** : ne pas transformer Group/Membership en droit ni Funding en passage obligé |
| **Groupe / communauté** | Group et relations sous vrai owner | R groups/urls.py mais hors identité d'initiative | pas de N3 initiative-groupe prouvé | **C** : relation sans faire d'un groupe une initiative ni autoriser implicitement ses membres |

### G2 / MT4 — Education : Programmes

| N2 retenu | N3 / owner | Web | Flutter | Écart exact |
| --- | --- | --- | --- | --- |
| **Programme** (Activity) | sessions/occurrences, inscription, Forms, Requirements, Resource, groupes, Access/Capacity si vrais | R activity console, L détail retrieval | L Activity owner | **D** : composition de programme enrichie, non simple Activity intitulée « Programme » |
| **Session** (Occurrence) | gestion de date/place, resources, capacity, access et Jour J si admissible | L occurrence ; R operations/Jour J ailleurs | L occurrence ; R Jour J | **D/B** : relation Programme/Session et N3 liés selon droits, absence de session admise |
| **Inscription / demande** (Journey et JourneyRequest) | examiner, approuver/refuser, détails d'exigences si autorisé | R console-requests + POST ; R API request detail/decision | L Work journey ; A SpaceRequestScreen | **B** : le lien Work request_detail existe quand JourneyRequest réel ; Work Flutter n'exploite pas ce handoff depuis la fiche générique |
| **Ressource/Form/Condition** | Preparation, Questionnaires, Requirements owners | R routes Preparation et Form APIs ; dépend du scope | R écrans natifs préparation/questionnaire, mais actor Space non prouvé | **C/B** : visibilité, retour et revalidation owner, ne pas confondre document et Requirement |

### G2 / MT4 — Service Provider : Prestations

| N2 retenu | N3 / owner | Web | Flutter | Écart exact |
| --- | --- | --- | --- | --- |
| **Prestation** (Activity / Service vertical) | configuration Service, préparation, demandes, occurrences | R services:operator-service-config et Activity console | L Activity owner ; service_start_screen est un flux utilisateur, pas configuration Space | **B/D** : composition offre de service et accès configuration seulement si ACTIVITY_SERVICES_CONFIGURE |
| **Dossier Service** (Journey workflow Service) | start/complete steps ; blockers ; assignments ; reviews ; evidence, artefacts sous droit | **A** services:operator-case et routes dédiées, avec service_case_scope + permissions fines | **L** Journey owner générique dans Work ; aucun équivalent opérateur multi-N3 prouvé | **D** native Service Space ; Web handoff depuis Work uniquement quand operator_case_url réellement autorisé |
| **Demande et revue** | Service review ou JourneyRequest selon owner | A revue Service owner ; R demande si JourneyRequest réelle | A Request Space si route owner ; revue Service native non prouvée | **C/B** : ne pas assimiler toute demande de dossier à une JourneyRequest décisionnelle |
| **Rendez-vous / réalisation** | Occurrence, préparation, access éventuel | L occurrence et options Jour J | L owner + Jour J si permis | **B/C** : calendrier vrai, pas un dossier créé automatiquement par date |

### G3 / MT5 — Commerce

| N2 retenu | N3 / owner | Web | Flutter | Écart exact |
| --- | --- | --- | --- | --- |
| **Offre** (Offer) | prix, publication/état, CapacityPool, Activity, opérations Commerce si autorisées | R liste console-offers, L sélection Work ; **pas de N2 Offre Web dédié prouvé** | L sélection offer avec prix, dates ; pas d'édition métier native prouvée | **D/B** : profondeur Offer utile, disponibilité vraie et actions contextuelles |
| **Commande** (CommerceOrder) | lignes, paiement propriétaire, obligation, préparation/remise réelle si owner | L space-retrieval-order-detail, R console-orders ; API workspace-commerce-order-detail | L owner Space dédié en lecture ; commerce_order_screen.dart est un écran personnel séparé | **D/B** : synthèse métier correcte et N3 conditionnels, pas confondre confirmed/payment/fulfillment |
| **Obtention** si verticale présente | Obtention/Journey/Target, réception et fulfillment owner | R obtention/urls.py owner profond, **aucune auto-composition dans Work** | écrans obtention principalement côté parcours personnel ; handoff Space à qualifier | **C/B** : seulement si Activity d'Obtention réelle, ni commande forcée ni workflow générique |
| **Réalisation / remise** si propriétaire | Occurrence ou domaine approprié | R occurrence/owner ; pas de remise universelle | L occurrence | **C** : ne rien conclure à partir d'une commande confirmée |

### G3 / MT5 — Transport

| N2 retenu | N3 / owner | Web | Flutter | Écart exact |
| --- | --- | --- | --- | --- |
| **Départ** (Occurrence + TransportDeparture) | route, véhicule affecté, pool Capacity, ops, Access/contrôle et Jour J | R console-transport-departure-detail ; Jour J séparé | L owner Occurrence avec infos générales ; R Jour J | **D/B** : synthèse de départ native + N3 multiples, ne pas confondre places physiques et vendables |
| **Route** (TransportRoute) | arrêts/Places, services ; carte seulement sur géographie vraie | R console-transport-route-detail | L owner route (liste arrêts) | **B** : cartes/relations réelles, retour, géométrie cohérente |
| **Service** (TransportService lié à Activity) | occurrences/départs, route, préparation | R console Activity ; structure transport réelle | L owner Activity | **D/B** : présenter comme service de transport et non Activity générique isolée |
| **Véhicule** (Vehicle) | affectations, capacité physique, usage ; opérations si owner | R console-transport collection ; **pas de détail véhicule Web spécifique prouvé** | L owner vehicle (label, capacité) | **D** : profondeur si elle apporte une valeur opérationnelle ; pas de départ fictif |
| **Lieu** si disponible | Place/Stop et trajets autorisés | R console-places | pas de détail spécifique Work natif prouvé | **C/D** : depuis Route/Service seulement si owner géographique applicable |

### G4 / MT6 — Creative : Créations

| N2 retenu | N3 / owner | Web | Flutter | Écart exact |
| --- | --- | --- | --- | --- |
| **Création/Œuvre** (Activity) | description, resources, media uses, Occurrences, Service/Offer réels | R console Activity ; L retrieval | L Activity owner, présentation MPS si admissible | **D** : identité de l'œuvre et liens véritablement artistiques, sans nouveau modèle Creation |
| **Présentation/événement** (Occurrence) | préparation, capacité, Access et Jour J si pertinents | L occurrence, R Jour J | L occurrence, R Jour J | **B** : contexte de la création parent, dates multiples |
| **Média lié** (PresentationMediaUse) | upload/retire/studio si permission et usage réellement publiable | R presentations:media-upload, media-retire, studio ; N1 Web montre media reconnu public | N1 SpaceWorkSurface **ne lit pas media_bindings** ; MPS de détail activity parfois affichée | **B** : reconnaissance native réelle sans média orphelin, fichiers privés non exposés |
| **Prestation/Offer** si réelle | Service/Commerce owner | R route existante ailleurs | L owner générique | **C** : ne pas réduire l'œuvre à sa vente |

### G4 / MT6 — Media : Productions

| N2 retenu | N3 / owner | Web | Flutter | Écart exact |
| --- | --- | --- | --- | --- |
| **Production durable** (Activity) | Occurrences, Resource, media use, partenaire selon droit | R Activity console, L retrieval | L Activity owner | **D** : un vrai N2 Production, pas un fichier média/post/feed |
| **Édition / épisode** (Occurrence) | date, préparation, ressources, Jour J conditionnel | L occurrence ; R Jour J | L occurrence ; R Jour J | **D/B** : liens Production/Édition et N3 appropriés |
| **Série/collection** si relation propriétaire | relation durable démontrable, **pas d'owner « Série » inventé** | aucun N2 série autonome prouvé dans Work | aucun N2 série autonome prouvé | **C** ; ne pas persister une « série » simplement parce que le métier est Media |
| **Publication / diffusion spécialisée** | PresentationMediaUse et éventuellement owner de publication réel | R media use et public presentation seulement | visualisation de MPS possible en détail Activity ; pas de CMS natif Space prouvé | **C/B** : aucune validation éditoriale ou diffusion live inventée |

## 4. Lecture exacte des permissions et de la divulgation

1. Viewer = Profile ; acteur = Space ; sélection mandatée restreint les Activity IDs. L'archétype ne donne pas de pouvoir. Membership Group/Team ≠ Mandate.
2. La liste Work inclut **uniquement** les Offers autorisées via ACTIVITY_COMMERCE_VIEW, les parcours d'inscription via ACTIVITY_REQUESTS_VIEW, les cas Service via le sélecteur et les droits de cases. Les commandes exigent ORDERS_VIEW ; routes et véhicules exigent une portée Space et un footprint transport réel.
3. JourneyRequest : la présence de Journey.pending_approval n'invente pas un JourneyRequest. Le lien request_detail est attaché seulement lorsque la demande owner existe ; la décision demande ACTIVITY_REQUESTS_DECIDE, statut admissible et non-expiration.
4. Les actions Service opérateur sont liées à service_case_scope et des permissions fines par action. Un lecteur de dossier n'est pas gestionnaire de ses notes/pièces/paiements.
5. Media : la projection n'utilise pas un asset brut comme permission. Les bindings publics de reconnaissance passent par PresentationMediaUse et la livraison revalide publication, visibilité, éligibilité et ownership.
6. Dossier, Permission, Access, Payment, Proof, Requirement, AccessCredential, Capacity et Placement gardent leurs propriétaires. Aucun N2 Métier ne doit embarquer automatiquement preuves, emails bénéficiaires, QR, secrets, paiements internes ou notes confidentielles.
7. Une URL présente dans links n'est **jamais** une délégation d'autorité. TOCTOU, acteur changé et révocation doivent être traités par chaque owner à chaque ouverture/action.

## 5. Les impasses précises que MT1 a découvertes

| ID | Constat reproductible dans le code | Gravité produit | Responsable |
| --- | --- | --- | --- |
| **I01** | Work Flutter construit visible depuis sections et ignore business_world.reading_groups, question et hiérarchie composée | **P1 — cohérence huit grammaires** | MT7 |
| **I02** | Flutter SpaceWorkSurface construit toutes les entrées avec la même MakoloCard titre/summary/metadata/status, sans représentation sémantique selon le type | **P1 — risque « TP », expérience uniforme mais pauvre** | MT7 |
| **I03** | Flutter détail SpaceRetreivalOwner est surtout read-only ; n'expose pas les multiples N3 réellement liés à un owner | **P0 — impasse d'action** | MT2 puis MT3–6/7 |
| **I04** | Work fournit request_detail conditionnel mais le chemin Work→Journey natif n'ouvre pas automatiquement SpaceRequestScreen | **P0 — action d'inscription cachée** | MT4/7 |
| **I05** | Web Service a un N3 opérateur complet sous scope ; Flutter Work ne reproduit pas ses sous-actions sous autorité Space | **P0 — écart fonctionnel clients** | MT4/7 |
| **I06** | Web détails Activity/Occurrence/Commerce de retrieval sont des synthèses et leur retour est conçu pour Search/History ; Web Work conduit souvent à Console | **P1 — navigation de contexte non fermée** | MT2/7 |
| **I07** | Web offre/vehicule conduisent à une console de collection, pas à un owner item individualisé ; Flutter peut lire l'item | **P1 — profondeur asymétrique** | MT5 |
| **I08** | BusinessWorld fournit une seule perspective primary et peu de création owner/contextuelle ; couverture static established/partial, pas vérité établie par source | **P0 — contrat de représentation et états** | MT2 |
| **I09** | La racine Work Flutter omet la hiérarchie média/conditions/next_occurrence réelle de certains archetypes quand ces faits sont dans le payload | **P1 — information utile perdue** | MT6/7 |
| **I10** | Métier ne transporte pas encore pleinement contexte de retour (Space, responsabilité, perspective, sélection, requête, filtre, curseur, ancre) jusqu'aux propriétaires multiples | **P0 — continuité et retour** | MT2/7 |
| **I11** | La recherche et les filtres Work sont encore des liens vers Search/History ou des continuations de section ; pas de stratégie finale de recherche métier/facettes owner | **P1 — découverte du travail** | MT2/7 |
| **I12** | Les capacités de créer une Activity ou gérer un domaine ne suffisent pas à déduire une action contextuelle « Nouvelle création/production/programme » | **P1 — action contextuelle** | MT2/3–6 |
| **I13** | Existence des modules Console, Funding, Obtention, Groups, Trust, CRM, Payments, Analytics et autres ≠ composition autorisée dans Métier | **P1 — risque d'orphelin ou de méga-menu** | MT2 pour cartographie des liens, MT3–6 si utile, autres portes si non |
| **I14** | Sémantique de date, status, capacity, readiness, cause de blocage et « Live » doit venir du vrai owner ; ne pas inférer tout blocage ou toute réussite depuis un champ simple | **P0 — confiance utilisateur** | MT2/3–8 |
| **I15** | QA visuelle responsive/adaptive + tests de reprise offline/révocation N1→N2→N3 multi-handoffs ne sont pas prouvés par ce relevé statique | **P0 — qualité de livraison** | MT7/8 |

Les P0 sont **prioritaires**, pas nécessairement de nouvelles migrations ou de nouveaux modèles. Les P1 ne doivent pas devenir des améliorations décoratives sans effet sur l'action.

## 6. Fonctions Makolo non perdues de vue

Les domaines majeurs ne se transforment pas tous en sections Métier permanentes. Table d'affectation :

| Domaine | Placement correct |
| --- | --- |
| Profile, Espace/Équipe, Groups, Mandates, Permissions, Trust | **Nous / contexte d'autorité**, relations dans N2 seulement si pertinentes ; pas d'autorisation implicite |
| Interests/Topics, Geography, Discovery, Presentation | **Découvrir / contexte**, détails uniquement si pertinents, non propriétaires de l'action |
| Activity/Occurrence, Journey, Service, Commerce, Transport, Obtention, Funding | Candidats forts Métier N1/N2, **uniquement s'ils sont opérés et autorisés** |
| Requirement, Form, Resource, JourneyArtifact, Proof, Credential Trust | N3 propriétaires contextuels, pas une colonne universelle de checklist |
| Access, AccessCredential, AccessUse, Capacity, Placement, Waitlist, Live Queue, Checkpoint | N3 propriétaires de droits/capacité/opérations ; distinctions canoniques obligatoires |
| CommerceOrder, Payment et obligations | Commande N2 et opérations financières N3 sous permissions distinctes |
| Sharing, Domain Events, Notifications, Automation, CRM, Analytics, Scanner/Operations | **Piloter, Nous, Maintenant, Console ou N3** selon intention et owner ; ne pas ajouter comme gros modules N1 pour « tout montrer » |
| Dossier/Project, Action Network / Ongoing | Continuité de l'action ; seulement composer leurs liens owner-backed quand ils concernent le travail de l'Espace |
| MediaUse et Presentation | Représentation authentique d'un owner ; ni CMS, ni feed, ni second stockage de vérité |
| Services de production spécialisés encore inexistants | **C conditionnel**, ne pas inventer un nouvel objet Production/Creation/Publication sans preuve |

**Règle de complétude fonctionnelle** : une capacité peut être complète dans Makolo sans être présentée au N1 Métier, si elle est correctement retrouvable et opérable dans la porte qui la possède. Son absence du N1 n'est pas automatiquement un manque ; une action vraiment nécessaire et introuvable est un manque à résoudre.

## 7. Preuves de régression disponibles (mais non exécutées)

- Backend : organizations/test_zs3_space_work_api.py, organizations/test_ws3_space_work_web.py, organizations/test_space_work_group2.py, test_space_work_group3.py, test_space_work_group4.py. Les tests couvrent notamment sélection, confidentialité, activité limitée, Journey, order, transport, media, composition.
- Flutter : mobile/test/space_work_surface_test.dart ; et tests de context switching/owner dans les sous-domaines concernés. Leur **existence ne vaut pas validation**.
- Owners : services/test_t35_operator_web.py, presentations/test_media_use.py, transport/test_space_archetype.py, autres suites pertinentes selon MT3–MT8.

**Commandes minimales de vérification quand un runtime sera disponible** :

    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py test organizations.test_zs3_space_work_api organizations.test_ws3_space_work_web organizations.test_space_work_group2 organizations.test_space_work_group3 organizations.test_space_work_group4
    cd mobile && flutter test test/space_work_surface_test.dart

Puis scénarios Web et Flutter : profil avec droits Space, mandat Activity limité, acteur changé, révocation à l'ouverture, lien étrangère/IDOR, offline/stale, retour d'un N3 parmi plusieurs, Space à plusieurs verticales, N1 vide établi vs indisponible. L'absence d'échec de test ne garantit pas une expérience visuelle mature : inspection sur Compact/Medium/Wide et sur données réelles/démonstration séparées indispensable.

## 8. Sortie MT1 et gates de transfert

**La cartographie est CLOSE** : les huit archétypes disposent de N2 identifiés, et chaque type de N3 ou absence légitime est rattaché à des propriétaires et à une tâche. On ne conservera plus la formule « partiel, à vérifier » sans justification précise.

**Le PRODUIT Métier reste PARTIEL** dans les parcours et le rendu, de manière explicitement constatée par I01–I15. Ne pas confondre clôture de l'audit avec livraison des fonctionnalités.

**MT2 ne devra pas réauditer les huit archétypes** : il commencera directement par I03, I08, I10 et la création du contrat commun owner-handoff/action/coverage, en réutilisant les URLs et les permissions prouvées ici. MT3–MT6 traiteront les N2 par paire selon les tableaux, MT7 fermera les deux clients, MT8 testera et jugera la qualité.

**Interdit à la suite** : créer huit apps, des templates N1/N2/N3 identiques, un modèle WorkItem universel, un état de readiness fictif, une chaîne paiement obligatoire, un post/feed sans fin, une nouvelle source d'autorité locale, ou contourner les tests pour accélérer le merge.

> **Makolo marche pour vous. Pas le plaisir de rester ; le plaisir d'avancer.**
