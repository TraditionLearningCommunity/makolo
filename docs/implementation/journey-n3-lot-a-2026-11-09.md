# Journey N3 — Lot A : identité, page canonique, parcours

**Branche de travail :** `fix/discover-a-continuation-context-20261014` (PR #522, `TraditionLearningCommunity/makolo`).  
**Date :** 9 novembre 2026.  
**Périmètre :** tâches A1–A4. Pas de changement de `main`, pas de merge, ni de refonte de Découvrir, Conversations, Notifications, En cours ou Moi.

## Réconciliation (A1)

Sources : `Makolo_UX_Demarche_Journey_Contrat_Consolide_2026-10-09.md`, contrats Requirements/Readiness, Préparation, En cours, décisions de conception du 9 novembre et fichiers de la branche #522.

- Le propriétaire existe : `Journey`. Le lecteur Flutter est `JourneyRepository` (`personal.journey.detail`, `ProfileStore`, clé du Profil), la route est `/journeys/:id`, et le sélecteur de représentation est `JourneyDetailSelector`.
- Le Web possède déjà un détail participant propriétaire (`ParticipantJourneyDetailView` et `participant_journey_detail.html`). Il ne faut pas créer une deuxième page Journey.
- Les données métier actuelles incluent état de parcours, Readiness, formulaires, Requirements, ressources, Activity, Occurrence et handoffs.
- Les étapes canoniques existent dans `journeys.JourneyStep` et les dépendances dans `JourneyStepDependency`, mais elles n'étaient pas exposées par la projection de détail. Le Web présentait à leur place une progression de trois jalons synthétiques issus du workflow.
- Les captures bêta montraient un titre répété, une catégorie métier peu parlante en premier, des cartes de Readiness disproportionnées et des répétitions Activity / Occurrence. Le lot A traite le haut de page et les étapes ; préparation, ressources et handoffs détaillés relèvent des lots B et C.

## Décision de page canonique (A2)

**Une Journey = une profondeur propriétaire unique par support, accessible par son identité Journey.** Les points d'entrée conservent leur navigation et leurs permissions. Les notifications et conversations restent inchangées ; leurs liens Journey aboutissent au détail existant. Le détail Découvrir sans Journey est un autre objet, hors de ce lot.

Les écrans Web et Flutter n'ont pas besoin de partager le même code de rendu, mais doivent partager les mêmes faits, les mêmes intitulés et les mêmes critères d'autorité.

## Identité (A3)

1. Montrer en premier le titre réel de l'objectif (`representation.title` / `journey.activity.title`).
2. Présenter ensuite l'état Journey et la catégorie métier, si elle éclaire la lecture.
3. Ne pas répéter une description identique au titre.
4. Ne pas transformer arbitrairement le titre en un objectif généré, ni fabriquer une illustration ou un résultat promis.
5. Conserver le fonctionnement du retour, des routes propriétaires et des actions déjà présentes.

Le mobile reçoit une composition visuelle dédiée avec symbole selon le workflow et palette Makolo. Le Web place également « Mon objectif » et le titre en premier.

## Chemin et situation (A4)

La projection personnelle Journey peut maintenant contenir `steps` provenant de `journey.steps` : `id`, `title`, `kind`, `status`, `position`, `depends_on`. Les liens sont les dépendances réelles de `JourneyStepDependency`. Aucun modèle ni migration n'a été ajouté ; aucune description interne, note, identité du staff ou preuve n'est divulguée par cette nouvelle liste.

- Sans JourneySteps : **ne dessiner aucune étape**, ni pourcentage, ni timeline.
- Avec JourneySteps : montrer les statuts et intitulés réels, sans inventer un ordre de complétion. Les dépendances connues peuvent être nommées.
- Les étapes passées restent consultables, avec un poids visuel inférieur lorsqu'il reste des étapes en cours.
- Ne pas transformer une étape opérationnelle Jour J en JourneyStep. Ne pas créer de nouveau statut de Readiness.
- La lecture Web a cessé d'utiliser `journey_progress()` dans cette page ; les vrais `journey.steps` alimentent désormais « Où j'en suis ».

## Local-first, invariant dès le lot A

L'application mobile **se compose à partir de la base locale du Profil**, via `watchDetail`/`readDetail`. Une réponse réseau n'est pas une condition de rendu. Une actualisation peut enrichir la base, mais ne remplace pas la projection locale par un état d'écran « hors ligne » ou un cache de widget.

- Les racines personnelles déjà stockées peuvent identifier des Journey actives. `JourneyRepository.knownJourneyIdsFromOngoing` sélectionne uniquement les références Journey valides de `personal.ongoing`, en respectant le Profil courant.
- Après `refreshRoots`, `SyncLifecycle` prépare progressivement au plus six détails propriétaires (`personal.journey.detail`) parmi ce corpus connu. Le budget initial des sources préparées est plafonné à quinze lectures. Ces détails sont enregistrés dans la même BDD de Profil et restent accessibles lors des visites suivantes, sans dépendre d'une réponse réseau à l'ouverture de la page.
- L'acquisition est bornée et progressive : les détails jamais acquis et les Journeys absentes du corpus local ne peuvent pas être fabriqués. Une ouverture sans détail local affiche un état neutre, sans transformer une panne réseau en écran d'erreur métier.
- Une panne de transport avec une projection locale conservée laisse le contenu intact, sans tutoriel ni message technique dans la page.
- Le seul indicateur général de réseau reste celui du shell existant.
- Une absence réelle de détail local possède un état vide non technique ; on n'invente pas de démarche pour le combler.
- Un refus explicite du propriétaire (`permission_denied` / `not_found`) reste prioritaire et empêche d'exposer une projection révoquée.
- Les actions sensibles conservent la validation propriétaire. Une intention non confirmée ne devient pas une réussite du fait de son enregistrement local.

Le Web participant reste rendu par Django : ce lot n'affirme pas lui avoir inventé une base locale navigateur. La règle local-first s'applique au client natif et à son architecture existante.

## Fichiers du lot

- `core/api/detail_projections.py` — faits JourneyStep autorisés dans la projection.
- `core/api/detail_views.py` — préchargement des dépendances.
- `core/participant_views.py` — remplacement de la progression synthétique Web.
- `templates/core/participant_journey_detail.html` — identité et étapes réelles Web.
- `mobile/lib/features/journey/journey_repository.dart` — extraction des Journey connues dans la BDD locale et préparation bornée des sources propriétaires.
- `mobile/lib/app/sync_lifecycle.dart` — acquisition progressive des détails au cours du cycle personnel.
- `mobile/lib/features/journey/journey_selector.dart` — lecture du nouveau payload local.
- `mobile/lib/features/journey/journey_detail_screen.dart` — identité, chemin et état absent/refus, sans dépendance réseau pour le rendu.
- `mobile/test/journey_reference_depth_test.dart` — tests de sélection et rendu sur `ProfileStore` sans client réseau.
- `core/test_journey_n3_lot_a.py` — projection des étapes et absence de jalons artificiels.

## Hors lot A

Les priorités des lots B/C restent : présentation complète des actions/readiness, ressources, formulaires, exigences, paiements, accès, informations pratiques, Jour J/Live, finition visuelle des autres sections et validations instrumentées. Ne pas traiter ces sujets en créant des propriétaires concurrents.

**Validation :** modifications poussées sur #522, aucun statut CI revendiqué ; aucun merge. Exécution Django/Flutter et vérification Android réelle restent à faire avant toute intégration.
