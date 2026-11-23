# Jour J & Makolo Live Mature — plan d'implémentation par lots

**Statut :** L1–L6 développés sur la branche #522, sans exécution de CI ni certification technique ; L7 reste à réaliser.  
**Date :** 9 novembre 2026.  
**Branche de rattachement :** PR #522, `fix/discover-a-continuation-context-20261014`.  
**Contrat cible :** `docs/ux/Makolo_Jour_J_et_Live_Contrat_Cible_Mature_Unifie_2026-11-09.md`.  
**Contrat API historique conservé :** `docs/ux/Makolo_Contrat_Jour_J_et_Makolo_Live_Gele_Implementation_API_v1_2026-10-08.md`.

> Ce document définit **comment réaliser la cible**. Il n'affirme pas que les tâches sont déjà réalisées. Aucun lot ne peut être déclaré terminé sans preuve de code et de tests au HEAD exécuté. Ne pas recréer ce qui existe déjà ; identifier le reliquat exact après réconciliation.

## Décision architecturale obligatoire

Deux **expériences/pages canoniques** : Jour J (accomplir) et Makolo Live (comprendre le réel) pour une Occurrence. **Profil et Space sont des acteurs**, pas des modes UX. Participation, organisation et plateforme sont des relations / responsabilités pouvant coexister selon autorité. La personne **ne sélectionne pas « participant », « organisateur », « financier », « logisticien » ou « scanneur » pour révéler ses boutons**. Toutes les capacités réellement autorisées se composent dans la même page ; deux commandes importantes, chacune dans son territoire, peuvent être visibles en même temps.

La coexistence visuelle **n'est pas une fusion de permission**. Les domaines owners contrôlent chaque donnée, action et mutation. La plateforme conserve ses règles de finalité et de supervision. **Unicité UX n'impose pas endpoint, projection ou classe Dart unique** ; préserver l'isolation et la compatibilité des API tant qu'une alternative n'est pas prouvée.

## État d'exécution — L1 + L2 (9 novembre 2026)

**Implémentation serveur L1/L2 poussée sur #522 ; validation d'exécution en attente.** Ce statut ne certifie ni une CI verte ni l'application de la migration en base. Le code et les tests ont été ajoutés, sans exécution des suites ou smoke tests durant cette passe.

### L1 : autorité et coexistence

- Le résolveur `operations/occurrence_experience.py` reçoit le **Profil authentifié**, résout indépendamment son éventuelle participation personnelle, son autorité opérateur et les `Journey` dont un Space mandaté est bénéficiaire. Le nombre de représentants ne multiplie pas les démarches.
- Les relations `participant`, `institutional_beneficiary`, `organizer` et `platform` sont **non exclusives**. Aucune casquette participant/organisateur, finance/logistique/Scanner, n'est requise pour découvrir une capacité.
- Permissions canoniques indépendantes : Scanner, consultation/gestion opérationnelle, finance, Access, Capacity, Commerce et lieux ; le client ne reçoit pas de faux URL pour les actions non prouvées. Scanner utilise son handoff owner.
- `Journey.beneficiary_space`, la contrainte exactement-un entre Profil/externe/Space, `create_journey` mandaté, les événements enrichis et `can_access_case` sont en place, avec migration non destructive `journeys/migrations/0006_space_beneficiary.py`.
- Un membre Space sans mandat suffisant ne lit pas le cas institutionnel ; `JourneyAssignment` conserve ses usages existants ; Dossier/Projet restent facultatifs. Les artefacts restreints et mutations ne sont pas déverrouillés par la seule consultation.
- La perspective plateforme est isolée de la section organisateur lorsque l'autorité propriétaire n'est pas établie ; chaque domaine réévalue ses permissions côté serveur.

### L2 : projections, qualités de vérité et actions

- Deux GET additifs `/api/v1/operations/occurrences/<uuid>/experience/day-of/` et `/api/v1/operations/occurrences/<uuid>/experience/live/`, enveloppe versionnée, `Cache-Control: private, no-store` ; 404 pour un viewer sans relation ni capacité ; Live dans les phases arrival/live.
- `sections.participant` et `sections.organizer` peuvent coexister. La section `institutional` contient les `Journey` communes autorisées sans les faire passer pour des credentials individuels.
- `actions[]` permet plusieurs consignes importantes de responsabilités différentes et un handoff Scanner seulement lorsque permis ; une instruction sans endpoint de mutation reste une instruction.
- `knowledge` qualifie les heures planifiées (`planned`), la mobilité estimée (`estimated`), les états réellement lus chez les owners (`observed`), et l'absence de position ou d'heure réellement observées (`unknown`). Une source indisponible est `unavailable`.
- La couverture Live est `PARTIAL` uniquement lorsqu'au moins un fait owner-backed est présent, sinon `UNAVAILABLE` ; aucune `ESTABLISHED` inventée. Les transitions et médias non prouvés restent explicitement indisponibles.
- Les facts d'opérations n'apparaissent pas si le viewer n'a pas été autorisé à consulter la section opérateur. Les API personnelles et Space historiques ne sont pas supprimées ou cassées par ces ajouts.
- Tests ajoutés : `operations/test_occurrence_experience.py` (cumul, vérité, séparation, révocation conceptuelle) et `journeys/test_space_beneficiary.py` (bénéficiaire exclusif, membre mandaté, refus extérieur, route Jour J, révocation).

### Frontière avec les lots suivants

- **L3/L4 :** présentation Web et Flutter des deux pages canoniques, branchement des nouvelles projections, densité et hiérarchie des CTA. La présence des API ne signifie pas que les écrans utilisent déjà le contrat.
- **L5 :** handoffs/écrans métier complets, permissions de mutations et cas des représentants d'un bénéficiaire externe. La représentation d'un enfant par plusieurs Profils n'est pas introduite artificiellement ici.
- **Autres workflows :** `Access` reste individuel ; Commerce/Services ne reçoivent pas automatiquement un accès institutionnel. Une Journey Space constitue une démarche institutionnelle, pas une admission physique.
- **Avant clôture technique et merge :** exécuter les tests ciblés, vérifier la migration en environnement de test, contrôler les consommateurs Journey/Services/Commerce/Access, puis seulement les suites et la CI pertinentes. Ne pas déclarer « certifié » sans ces preuves.

## État d'exécution — L3 + L4 (9 novembre 2026)

**Implémentation Web, Flutter et opt-in serveur enregistrée sur #522.** Les validations de compilation, Django, Flutter, migration et CI ne sont pas exécutées à la demande du propriétaire. Ne pas qualifier ces lots de certifiés.

### L3 — Jour J unifié

- La projection `occurrence.experience.day_of` alimente maintenant les repositories Flutter Profil et Space, sans mode participant/organisateur. `OccurrenceExperienceContent` est la présentation partagée pour toutes les entrées.
- Les blocs d'accomplissement personnel, Journey institutionnelle, opérations, responsabilités financières, Scanner et Capacity coexistent suivant les autorisations réellement renvoyées. Les actions importantes restent simultanément visibles. Les opérations sans handoff existant sont présentées comme capacités, sans bouton trompeur.
- Le Web Profil a une entrée `/me/occurrences/<id>/day-of/`. Le Web Space et le Web Profil partagent le même fragment de contenu. Une Journey dont le Space est bénéficiaire peut apparaître depuis son Space même si l'Occurrence est organisée par un autre acteur.
- La source mobile Space transmet `actor_space` ; le backend vérifie le mandat effectif, filtre les Journeys institutionnelles du Space choisi et ne fusionne pas les opérations d'un autre Space.
- La page personnelle d'une Journey propose l'accès à Jour J quand une Occurrence est liée. Le Dossier/Projet demeure facultatif.

### L4 — Live unique et *facultatif*

- `Occurrence.live_enabled` est une permission produit de publication, initialisée à `False` pour toute Occurrence (migration additive `activities/migrations/0005_occurrence_live_opt_in.py`).
- Activation/désactivation réservée au gestionnaire Activity/Space via `activities.services.set_occurrence_live_enabled`, endpoint propriétaire `POST /api/v1/operations/occurrences/<id>/experience/live-configuration/` et formulaires Web autorisés.
- Les GET composés Live renvoient indisponible si l'Occurrence n'est pas activée ou hors de la fenêtre arrival/live ; Jour J reste accessible. Les liens Live historiques et leurs capacités ne sont plus proposés automatiquement par la seule existence d'une Journey ou d'un horaire.
- `occurrence.experience.live` est consommée par Flutter et Web ; la page reality-first affiche couverture, dates prévues, faits owner-backed, incertitude de position, source et fraîcheur. Elle n'invente pas de delta, média, ou streaming.
- Les fichiers de navigation historiques restent compatibles ; une entrée directe vers un Live indisponible ne crée aucun droit ni projection nouvelle.

### Fichiers principaux

- `activities/models.py`, `activities/services.py`, migration `0005_occurrence_live_opt_in` ;
- `operations/occurrence_experience.py`, `operations/occurrence_experience_api.py`, `operations/api/urls.py`, `operations/occurrence_experience_facts.py` ;
- `organizations/space_ws5_web.py`, `core/occurrence_experience_web.py`, `core/urls.py`, `core/m8c_participant_views.py` ;
- `templates/occurrence/day_of_content.html`, `templates/occurrence/live_content.html`, wrappers Web Profil et Space ;
- `mobile/lib/features/occurrence/occurrence_experience_content.dart`, repositories et écrans DayOf/Live/Space, liens de navigation ;
- tests ajoutés : `operations/test_occurrence_experience_live_optin.py`, `core/test_occurrence_experience_web.py`, `mobile/test/occurrence_experience_content_test.dart`, extensions de `operations/test_occurrence_experience.py` et `journeys/test_space_beneficiary.py`.

### Limites et livraison

- Les pages L3/L4 consomment la grammaire nouvelle, mais le Scanner **mobile** ne dispose pas encore d'un écran / route propriétaire : les droits sont signalés, aucun faux bouton de navigation n'est créé. Les profondeurs métiers sont L5.
- Une Journey Space est une bénéficience institutionnelle, non un credential collectif ou une admission physique. La délégation multi-tuteurs externe relève d'une évolution canonique distincte.
- Les anciennes projections opérationnelles restent disponibles comme services de faits / compatibilité ; elles ne remplacent pas les nouvelles pages.
- **Validation non exécutée** : migration en base, tests serveurs, Flutter, rendu Web et CI ; aucune prétention de livraison en production et aucune fusion de #522.

## Évolution canonique Journey — bénéficiaire Space (passe ciblée)

**Décision :** une Journey autonome représente une démarche réelle, sans Dossier ni Projet obligatoire. Son bénéficiaire est exactement un Profil, un externe ou un Space. Les membres du Space ne reçoivent pas chacun une Journey. Ils peuvent consulter le cas institutionnel selon leurs **mandats Space actifs**, sans être automatiquement affectés individuellement par `JourneyAssignment`. Les opérations restreintes, les artefacts sensibles et les mutations ne sont pas déverrouillés par cette seule lecture.

**Mise en code :** champ nullable `Journey.beneficiary_space`, contrainte DB « exactement un des trois », migration expand-compatible `journeys/migrations/0006_space_beneficiary.py`, validation du service `create_journey` via permissions canoniques du Space, événement de domaine portant `beneficiary_space_id`, lecture du cas via `can_access_case`, et scénarios de test ciblés.

**Conservation :** `Access` continue de représenter un droit individuel Profil/externe. `JourneyAssignment` et les capacités Dossier existantes ne sont pas dupliquées. Les membres ne reçoivent pas automatiquement l'accès aux contenus de Services, à la finance ou aux opérations d'un autre owner.

**Limites à réconcilier séparément :** découverte UI d'une Journey institutionnelle, projection Jour J/Live d'un Space bénéficiaire, gestion de délégations pour un enfant ou externe, éventuelle bénéficience institutionnelle dans d'autres workflows (notamment Commerce/Access), et adaptation des consommateurs Services existants. La prise en charge d'un Space bénéficiaire dans le noyau Journey **n'atteste pas** que ces intégrations sont déjà disponibles.

**Validation :** tests ajoutés mais non exécutés ; aucune CI ni migration n'a été appliquée à une base dans cette passe.

## Ordre des lots et dépendances

```text
L0 Inventaire / preuves / frontières
       ↓
L1 Autorité acteur + relations + capacités composées
       ↓
L2 Contrats de projection / qualité des faits
       ↓
L3 Jour J canonique (Web + Flutter)
       ↓
L4 Makolo Live canonique (Web + Flutter)
       ↓
L5 Profondeurs et handoffs propriétaires
       ↓
L6 Continuité / local-first / révocation / accessibilité
       ↓
L7 Scénarios finaux / validation / intégration
```

**Exécution recommandée :** changements petits, testés, réversibles ; sous-lots par owner et surface ; code ajouté sur la PR #522 uniquement après audit de sa CI et de son HEAD. Les travaux de conception du présent plan **n'autorisent pas un merge**.

### L0 — Inventaire factuel et baseline (bloquant)

- **L0.1** Vérifier HEAD, état de la PR #522, diff vis-à-vis de `main`, CI, dépendances et travail parallèle ; ne pas raisonner depuis un ancien SHA.
- **L0.2** Lire blueprint canonique et contrat API Jour J/Live ; inventorier routes, vues, projections, tests Django, Web, Flutter et deep links, sans confondre type d'acteur et capacité.
- **L0.3** Matrice actuelle des owners : Activity/Occurrence, Profil, Space, Mandate/Permission, Journey, Access, Queue, Placement, Checkpoints, Capacity, Readiness, Scanner, Incidents, Media, History, Notifications.
- **L0.4** Recenser les scénarios réels : Profil bénéficiaire, Profil auteur/opérateur, Space bénéficiaire représenté par mandat, Space organisateur, personne bénéficiant et organisant, plusieurs mandats d'organisation, staff autorisé, aucun droit, révocation, clôture.
- **L0.5** Réconcilier chaque capacité cible avec une source vérifiée ou un manque explicitement qualifié. Conserver un relevé de preuves, de risques et de compatibilité ; aucune pseudo-donnée pour combler une source absente.

**Sortie L0 :** matrice owner → autorité → projection → UX → test, scénario par scénario ; plan d'intégration minimal et tests de départ documentés.

### L1 — Acteur effectif, cumul de relations et permissions (P0)

- **L1.1** Définir l'identité effective du viewer authentifié et du sujet agissant (Profil ou Space mandaté), pour une Occurrence donnée.
- **L1.2** Résoudre indépendamment les relations de bénéficiaire, auteur/organisateur, opérateur délégué, staff ; permettre leur coexistence et vérifier la portée de chacune.
- **L1.3** Agréger les capacités autorisées **sans menu de changement de rôle**, en conservant leurs owners, destinataires, périmètres et commandes spécifiques.
- **L1.4** Prévenir l'élévation : un mandat Scanner n'octroie pas Finances ; être organisateur n'ouvre pas tous les credentials ; participer n'ouvre pas les files d'autrui ; le staff ne voit que ce que son mandat et sa finalité permettent.
- **L1.5** Traiter les collisions : même personne bénéficiaire + organisatrice ; deux actions urgentes ; absence de capacités ; Space bénéficiaire ; utilisateur quittant un Space ; plusieurs Spaces.
- **L1.6** Tests serveur d'autorité positifs et négatifs, conflits d'acteurs, mandat expiré, relation retirée, actions sans permission.

**Sortie L1 :** résolution vérifiée de toutes les capacités et données visibles, indépendante du choix d'une casquette UI, avec tests empêchant l'escalade et la fuite inter-acteurs.

### L2 — Projections composées et vérité Live (P0)

- **L2.1** Définir une grammaire de présentation **commune** pour les deux pages : identité d'Occurrence, acteur effectif, faits autorisés, actions avec owner/handoff, états de chargement et source.
- **L2.2** Préserver ou adapter les projections API existantes sans rupture gratuite ; ne pas remplacer les projections protégées par un endpoint universel sans contrat d'autorisation éprouvé.
- **L2.3** Composition Jour J : contexte, situation, actions importantes (0, 1 ou plusieurs), orientation, Access, Queue, Placement, Checkpoint, Readiness, Capacity, Live intégré, suite.
- **L2.4** Composition Live : faits temporels, spatiaux, opérationnels, qualités `planned/estimated/observed/live/unknown/unavailable`, provenance, fraîcheur, couverture `ESTABLISHED/PARTIAL/UNAVAILABLE` si déterminable.
- **L2.5** Delta Live uniquement depuis une source prouvée et ordonnable ; n'inventer ni événements ni changements de snapshot. Media et incidents seulement si owners et publication vérifiés.
- **L2.6** Tests de sérialisation, minimisation de divulgation, faux vide, qualité des faits, phase distincte du fait observé, pas de QR/secrets dans les projections racines.

**Sortie L2 :** clients capables de composer les mêmes expériences sémantiques à partir de données owner-backed, même si les API spécialisées demeurent.

### L3 — Page canonique Jour J : présentation et actions coexistantes (P0)

- **L3.1** Définir la hiérarchie d'écran action-first, indépendante de Profil/Space et de « rôle sélectionné ».
- **L3.2** Afficher simultanément les actions importantes légitimes : exemple « Présenter mon accès » + « Scanner les entrées », sans switch participant/organisateur, et rendre directement disponibles finance et logistique selon mandat.
- **L3.3** Structurer les actions par territoires : accomplissement propre, opérations de l'Occurrence, supervision plateforme autorisée, sans prétendre que les trois sont des modes d'écran.
- **L3.4** Présenter correctement destination, file, attribution, checkpoints, readiness, capacités ; aucune longueur de liste trompeuse.
- **L3.5** Ajouter un résumé Live intégré s'il apporte un fait utile ; entrée vers Live focalisé lorsque justifiée.
- **L3.6** Harmoniser Web et Flutter (composants, priorités, labels, accès aux profondeurs) sans sacrifier l'accessibilité ni les comportements owner.
- **L3.7** Tests widget / Web : 0, 1, 2 actions P3 importantes ; plusieurs mandats ; deux relations ; ordre à l'écran ; refus action côté serveur ; aucun switch préalable.

**Sortie L3 :** une expérience Jour J canonique, avec tous les boutons réellement autorisés visibles/découvrables immédiatement et sans brouiller l'action courante.

### L4 — Page canonique Makolo Live : observation et couverture (P0/P1)

- **L4.1** Définir une hiérarchie reality-first réellement distincte de Jour J, commune à Profil et Space.
- **L4.2** Afficher couverture de lecture et vérité des faits, sans confondre fraîcheur, planification et observation.
- **L4.3** Montrer les faits temporels, spatiaux, opérationnels pertinents et autorisés ; différencier mesure métier réelle et comptage technique.
- **L4.4** Développer les changements significatifs uniquement si leur source est établie ; transitions sans défilement intempestif ou chronologie fictive.
- **L4.5** Coexistence bénéficiaire + organisateur : informations personnelles utiles et observations opérationnelles autorisées sur la même page, sans mélange de secrets.
- **L4.6** Média Live, incident et instruction : surfaces conditionnelles si publication, source et droit existent ; refus/indisponibilité honnêtes autrement.
- **L4.7** Parité Web/Flutter et tests qualités `unknown`, `unavailable`, `partial`, stale, absence de couverture, double relation, permissions.

**Sortie L4 :** Live capable de dire ce qui se produit, ce qu'on sait, ce qu'on ignore et ce qui a changé, sans simuler un flux temps réel.

## État d'exécution — L5 (9 novembre 2026)

**L5 a reçu sa passe d'implémentation sur la branche de #522.** Les tests ont été ajoutés mais non exécutés ; aucun rendu Flutter ou Web n'a été vérifié par démarrage de l'application. Il s'agit d'une implémentation versionnée, pas d'une certification ni d'un déploiement.

### Propriétaires réellement réutilisés

| Besoin | Intégration faite | Frontière du domaine |
| --- | --- | --- |
| Scanner | `scanner.canonical_services.scan_access_credential`, `AccessUse`, `scanner/occurrence_access.py` ; GET contexte et POST `/api/v1/scanner/occurrences/<id>/control/` | Valide une Activity/Occurrence même hors Event ; l'affectation n'accorde pas une permission |
| Checkpoint lié à un contrôle | `operations.checkpoint_services.observe_checkpoint` avec `AccessUse` accepté | Même checkpoint et mandat vérifiés, dans la transaction ; aucun nouveau statut parallèle |
| File | `operations.queue_api` et services de file existants | La file opérationnelle n'est pas une waitlist Commerce |
| Placement | `operations.placement_api` et `placement_services` | Bénéficiaire Profil ou externe vérifié, pas de placement inventé pour Space |
| Préparation | `operations.live_api` / Readiness owner | Lecture contextualisée, pas de validation simulée |
| Capacity | `capacity.selectors` | Agrégation consultation seulement, aucune nouvelle réserve |
| Commerce | `commerce.selectors` / Offer et CommerceOrder | Consultation Offer et comptes par statut ; achat et paiement restent dans leurs propriétaires |
| Finance | `payments.models` via agrégats bornés par Occurrence, protégés par mandat | Aucun paiement ou remboursement exécuté depuis Jour J, aucune coordonnée de payeur projetée |
| Orientation / lieux | `OccurrencePlace` et Geography, accès existant Jour J | Lieu prévu, pas position réelle inventée |
| Access / credential | Pages de détail et présentation QR Access existantes | Le token n'est jamais inséré dans la projection Jour J |
| Historique | Handoff Web / Flutter vers Historique déjà présent | Pas de second journal d'événements |
| Incident / média | Aucune profondeur nouvelle annoncée sans owner publiable lié à l'Occurrence | `unavailable` ou omis, jamais média ou incident fictif |

### Présentation et parcours

- `operations/occurrence_experience.py` expose `depths[]` avec `kind`, `territory`, `read_path`, `source` et `can_manage`, sans exiger de mode financier/scanneur/logisticien.
- Deux vues de profondeur Web réutilisent `operations/occurrence_web_depth.py` et un fragment commun, en conservant l'Occurrence et le contexte Profil/Space ; les mutations passent par Operations, jamais par une copie.
- Flutter possède `OccurrenceOwnerDepthScreen` qui revalide le catalogue avant lecture puis avant mutation ; confirme les actions sensibles et renvoie à la page précédente par navigation native.
- Flutter possède `OccurrenceScannerScreen` avec caméra **opt-in** et saisie manuelle, confirmation avant consommation, nouvelle lecture du mandat avant POST, résultat explicite ; aucun stockage local du code QR.
- Scanner Web réutilise la console caméra du projet pour le Space et pour une Activity personnelle, avec un résultat minimal du propriétaire canonique.
- Un Space bénéficiaire d'une Journey externe peut voir Jour J institutionnel mais ne peut ni scanner ni modifier les ressources du fournisseur dans le contexte de ce Space.
- Live reste facultatif selon `Occurrence.live_enabled` ; aucune de ces profondeurs ne publie Live ou ne fabrique une observation.

### Vérifications ajoutées mais non exécutées

- `scanner/test_occurrence_control_l5.py` : scan sans Event, idempotence, révocation, affectation insuffisante seule, passage checkpoint lié à AccessUse, absence de divulgation de token.
- `operations/test_experience_depths_l5.py` : droits Finance/Operations/Scanner distincts et cumulables, profondeur refusée à l'outsider et après révocation, mutation Web refusée.
- `mobile/test/occurrence_experience_content_test.dart` : boutons de profondeurs indépendants dans Jour J.
- Des tests ciblés et scénarios existants devront encore être **exécutés** pour vérifier syntaxe, rendu, permissions réelles, schéma, accessibilité et non-régression. La CI n'a pas été lancée à la demande du propriétaire.

### Limites explicites (pas de fonctionnalité inventée)

- Les panneaux Capacity, Commerce, Finance et lieux sont **en lecture seule** ; les opérations avancées sont réalisées par les modules métier propriétaires et leurs écrans établis, non par une mutation créée dans L5.
- La représentation multi-tuteurs d'un bénéficiaire externe, ainsi que le droit d'admission physique d'un Space, ne sont pas étendus ici.
- Il n'existe pas de rattachement propriétaire confirmé pour publier un incident ou média autorisé de cette Occurrence dans la nouvelle page ; aucun faux flux n'est rendu.
- L5 n'est **pas certifié** sans exécution des validations. L6 et L7 restent ouverts ; ne pas merger #522 à ce titre.

### L5 — Profondeurs secondaires et actions owner-backed (P1)

- **L5.1** Catalogue et routage des profondeurs réellement nécessaires : orientation, accès/credential, file, placement, checkpoint, readiness, capacity, scanner, opérations financières/logistiques, incident, média, Historique.
- **L5.2** Préférer handoff vers écran owner existant, sheet ou panneau ; créer une nouvelle page uniquement si la focalisation le justifie.
- **L5.3** Revalider les permissions au point d'exécution et au retour ; aucun bouton masqué par « rôle non sélectionné » lorsque l'acteur possède le droit.
- **L5.4** Préserver le contexte Occurrence, acteur effectif, retour, position et état ; aucun accès à une profondeur privée par deep link seul.
- **L5.5** Tests navigation, permissions, action confirmée/refusée, secret protégé, annulation et retour.

**Sortie L5 :** profondeurs minimales et cohérentes, connectées aux owners sans duplication de domaine.

## État d'exécution — L6 (9 novembre 2026)

**L6 a reçu sa passe d'implémentation sur #522.** Les tests ciblés sont versionnés mais non exécutés ; la certification de leurs résultats et la revue visuelle de l'application restent à effectuer en L7. Aucun déploiement, merge ou migration n'a été effectué pour L6.

### L6.1 — Réconciliation et fraîcheur

- Les trois écrans Flutter unifiés (Jour J Profil, Live Profil, Jour J/Live Space) rechargent depuis Operations à l'ouverture et à la reprise, avec une actualisation périodique tant qu'ils restent au premier plan : 60 secondes pour Jour J, 30 secondes pour Live.
- Les requêtes obsolètes après changement de widget ou d'acteur ne peuvent plus rétablir l'état visuel du précédent contexte.
- `OccurrenceExperienceContent` sépare une lecture fraîche d'une **dernière information connue** : source inaccessible, échec de synchronisation, fraîcheur expirée, ou fenêtre Live connue comme terminée.
- Les données d'une ancienne fenêtre Live peuvent être lisibles uniquement comme information historique explicitement étiquetée, jamais comme fait « observé actuellement ». Le handoff vers Live disparaît de Jour J si la fin connue de la fenêtre est atteinte.
- Web : les pages personnelles, Space, Scanner et profondeurs portent `Cache-Control: no-store`. Le fragment `continuity_guard.html` et `static/js/occurrence_continuity.js` revérifient la page au retour d'onglet/BFCache et signalent une lecture vieille de plus de deux minutes ; les commandes Web de cette page deviennent inactives jusqu'à nouvelle vérification.

### L6.2 — Isolation de données

- `SyncSourceDefinition.projectionEnvelope` accepte des contraintes strictes **optionnelles**, appliquées ici aux seuls snapshots Occurrence : `expectedOccurrenceId`, `expectedViewerProfileId`, `expectedActorSpaceId` et `expectedSurface`. Toute réponse incompatible lève une erreur de contrat **avant `store.putProjection`**.
- Operations expose `context.viewer_profile_id` et l'identifiant réel de l'Occurrence. Une projection `actor_space` conserve explicitement l'identité du Space mandaté.
- Le stockage reste dans les bases séparées par Profil et dans les clés réelles déjà présentes : `occurrenceId` pour Profil ; `spaceId|occurrenceId` et `SyncActorScope.space` pour Espace. Pas de cache métier ou statut supplémentaire.
- Les écrans réévaluent l'identité **même en lecture d'anciens snapshots** ; une projection non compatible n'est pas affichée. Après un retour à un acteur précédent, ils attendent une nouvelle réponse propriétaire réussie avant de présenter ses données privées, afin d'éviter une réapparition momentanée d'un mandat retiré.

### L6.3 — Révocation et commandes

- `SyncEngine` conserve ses tombstones propriétaires sur `403/404` et supprime atomiquement la projection visée ; la nouvelle logique retire également le **Live frère pour le même Profil/Space/Occurrence** lorsqu'un Jour J devient inaccessible. Une réponse Live `404` retire seulement Live et laisse Jour J légitime intact.
- La génération de synchronisation du Live frère est invalidée, empêchant une ancienne requête Live arrivée après le refus Jour J de réhydrater la représentation privée.
- Une panne réseau ou un `5xx` ne se transforme pas en révocation : les dernières données connues restent marquées comme telles, sans mutation déclenchable.
- Scanner Flutter : reprise = nouvelle vérification, arrêt de la caméra et purge de la saisie/résultat quand l'application quitte le premier plan, blocage des doubles confirmations et vérification du handoff owner avant le POST. Les profondeurs Flutter annulent leur état privé affiché lors d'une suspension.
- Le contrôle serveur reste l'autorité pour chaque mutation ; un bouton ou un cache ne peut accorder un nouveau Mandate. Jour J ne crée ni deuxième Access, ni deuxième Capacity ni nouveau flux d'incident.

### L6.4 — Robustesse et accessibilité

- Les cartes de plusieurs obligations `actions[]` sont disposées en une colonne Compact et deux colonnes Medium/Wide si la largeur réelle le permet : **les deux obligations restent présentes simultanément**, sans sélecteur de rôle.
- Les profondeurs utilisent la même adaptation de largeur ; boutons minimum 48 px logiques, libellés textuels, messages de statut `Semantics(liveRegion: true)` en Flutter et `role=status/aria-live` sur Web.
- Les listes préservent leur position via `PageStorageKey` tenant compte du Profil, de l'Occurrence, de l'acteur Space et de la surface. Le retour depuis une profondeur utilise la navigation établie.
- Les mutations Web de type file/checkpoint/placement et activation Live demandent une confirmation, même lorsque plusieurs responsabilités coexistent. Le Web Scanner ne conserve pas un code non envoyé pendant un changement d'onglet.

### L6.5 — Contrats ajoutés mais non exécutés

- `mobile/test/occurrence_continuity_l6_test.dart` : identité, espace/Profil, fin Live, hors ligne, révocation, actions simultanées et texte agrandi Compact/Wide.
- `mobile/test/occurrence_scope_parser_l6_test.dart` : rejet avant cache des réponses d'Occurrence, viewer, Space ou surface divergents.
- `mobile/test/occurrence_sync_revocation_l6_test.dart` : retrait du Live frère, absence de purge de Jour J sur Live `404`, panne réseau, isolation Space A/B et réponse Live tardive.
- `operations/test_experience_continuity_l6.py` : scopes et URL canoniques, refus après révocation, Live opt-out, en-têtes de confidentialité Web/API.
- Assertions Scanner Web héritées de L4 mises à jour selon la **vraie capacité canonique L5** (la caméra ne démarre jamais toute seule), sans relâcher le contrôle d'autorité ni le test de révocation.
- **Non exécutés :** tests Django, Flutter, visuels, CI, simulations offline réelles, cold start/foreground en appareil et smoke tests. Ils sont requis pour la certification finale L7.

### Frontières conservées

- Un `end_at` connu permet d'arrêter localement la présentation Live courante ; pour les Occurrences à dates sans heure terminale, la nouvelle vérification serveur régulière reste la seule autorité de fin de fenêtre.
- Le retrait d'une permission n'est pas détecté magiquement hors connexion : les informations affichées sont alors explicitement **dernières données connues et non autorisations actuelles**, et toute action propriétaire nécessite une nouvelle lecture.
- Les tuteurs multiporteurs Dossier, les médias incidents sans owner publiable, les paiements et réservations de capacité ne sont pas réimplémentés dans Jour J ou Live.
- Aucune CI n'a été lancée et aucune conformité visuelle ou technique de L6 n'est déclarée sans preuve d'exécution.

### L6 — Continuité et présentation robuste (P1)

- **L6.1** Réconciliation à l'ouverture, au refresh et au retour au premier plan ; distinction état courant / dernière information connue / source inaccessible.
- **L6.2** Scoping des snapshots/caches par Profil connecté, acteur effectif, Occurrence, périmètre de données et politique propriétaire ; aucun mélange entre contexte bénéficiaire et données opérateur.
- **L6.3** Révocation, mandat retiré, changement d'acteur et fin de fenêtre Live : invalidation/purge dérivée des données non autorisées, sans faux succès.
- **L6.4** Compact / Medium / Wide : un et deux CTA importants visibles et utilisables ; organisation contextuelle sans dashboardification, clavier, lecture d'écran, text scaling, focus, contrastes.
- **L6.5** Tests offline, cold start, reprise, révocation, multi-acteurs, changement de Space, lecture stale et navigation.

**Sortie L6 :** expériences utilisables, sûres et honnêtes même quand les informations et la connectivité évoluent.

### L7 — Certification et intégration (bloquant avant merge)

- **L7.1** Matrice end-to-end pour les acteurs et combinaisons : Profil participant, Profil organisateur, Space participant, Space organisateur, cumul bénéficiaire+organisateur, 3+ mandats internes, staff autorisé, outsider.
- **L7.2** Tests de non-régression API, Django permissions, Flutter widgets/intégration, Web E2E, routes et anciennes données ; migrations vérifiées si nécessaires, sans destruction.
- **L7.3** Visual QA Compact / Medium / Wide, accessibilité, écran vide, Live partiel, deux actions importantes, après fin, révocation et refus.
- **L7.4** Vérifier que Jour J n'est pas devenu un dashboard, que Live n'est pas une copie, et qu'aucune nouvelle source de vérité ne s'est glissée.
- **L7.5** Vérifier les gates CI du HEAD réellement candidat ; ne jamais affaiblir/supprimer un test. Ne merger qu'après CI verte et revue, puis vérifier `main` et les smoke tests d'environnement de test.

**Sortie L7 :** preuves de conformité au contrat cible et décision d'intégration fondée sur résultats, non déclarations.

## Scénarios de référence (tests obligatoires)

| Scénario | Jour J attendu | Live attendu | Assertion d'autorité |
| --- | --- | --- | --- |
| Profil participant seul | Mon accès et mon action | Mes faits publiables | Aucun outil opérateur |
| Space bénéficiaire représenté | Accomplissement du Space | Faits accessibles au bénéficiaire | Mandat de représentation requis |
| Profil organisateur seul | Toutes ses opérations autorisées | Faits opérationnels utiles | Pas de credential d'autrui |
| Space organisateur | Conduite de l'Occurrence | Lecture du réel opératoire | Portée des mandats vérifiée |
| Financier + logisticien + scanneur | Tous les accès utiles, sans switch | Observations de leurs territoires | Contrôle séparé des 3 owners |
| Participant ET organisateur | Deux CTA importants visibles ensemble | Faits personnels + opérationnels autorisés | Pas de fusion de données privées |
| Staff plateforme | Supervision limitée, si applicable | Faits autorisés par finalité | Pas d'accès global automatique |
| Permission retirée pendant la session | Commande retirée / refus | Projection revalidée | Mutation impossible côté serveur |
| Occurrence terminée ou annulée | Sortie naturelle | Pas de faux Live courant | Aucun événement fictif |

## Politique de livraison des lots

- Chaque lot commence par un audit du HEAD de #522 et **réutilise ce qui fonctionne déjà**. Il produit un petit diff traçable, des tests ciblés, puis les tests pertinents.
- **L0 et L1 précèdent les modifications de présentation impliquant des autorisations.** Ne pas coder une agrégation client aveugle de projections secrètes.
- La conception « tous les boutons autorisés accessibles sans mode » s'applique à la **découvrabilité**, pas à l'obligation d'afficher un mur de boutons : regroupements et priorités sont permis, aucun verrou de « casquette » n'est permis.
- Le principe précédent « une seule action P3 » est remplacé par **plusieurs actions importantes si plusieurs obligations coexistent**, avec hiérarchie et contexte clairs.
- Pour la plateforme, exiger une revue d'autorité et de confidentialité spécifique avant toute composition en surface commune.
- Aucun lot ne doit imposer une nouvelle migration, nouvelle API ou nouveau domaine sans démonstration de nécessité après L0.
- Chaque changement de code devra être annoncé avant commit/push ; préserver la branche et la CI, ne pas modifier `main` directement.

**État de ce document : L1–L6 sont développés sur #522, non certifiés faute d'exécution des validations ; L7 reste ouvert.**
