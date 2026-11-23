# Journey N3 — Lot B : actions, préparation, ressources et capacités

**Branche :** `TraditionLearningCommunity/makolo`, PR #522, `fix/discover-a-continuation-context-20261014`.  
**Périmètre :** tâches B5–B7 après le lot A. Aucun merge, aucune modification directe de `main`.  
**Statut :** code poussé ; tests et validation instrumentée non exécutés dans cet environnement.

## Sources et frontières

Contrats de référence : `Makolo_UX_Demarche_Journey_Contrat_Consolide_2026-10-09.md`, `Makolo_UX_Requirements_Readiness_Contrat_Consolide_2026-10-09.md`, `Makolo_UX_Preparation_Ressources_Contextuelles_Contrat_Consolide_2026-10-09.md`, `Makolo_UX_Forms_Questionnaires_Contrat_Consolide_2026-10-09.md`, `Makolo_UX_Mes_Acces_Contrat_Consolide_2026-10-09.md`, ainsi que le contrat Jour J/Live.

Journey reste le propriétaire du parcours. Readiness est dérivée ; Forms, Requirements, Preparation, Payment, Commerce et Access conservent leurs propriétaires respectifs. Les liens vers Notifications, Conversations, En cours, Moi et Découvrir ne sont pas refondus.

## B5 — Actions et préparation

- `JourneyDetailSelector` préserve le `readiness.next.key`, les interventions parallèles, attente, blocages, éléments en ordre et faits de demandes (pending / rejected).
- Le CTA principal n'est construit que si `next.link` correspond **exactement** à un lien fourni par un propriétaire reconnu (formulaire avec capacité `complete_form`, Requirement, ressources, Activity, Occurrence, Access, Jour J ou Live).
- Les actions supplémentaires peuvent apparaître auprès de leur contrôle de Readiness ; elles ne masquent pas un autre mouvement légitime partageant le même lien.
- Un label sans destination autorisée demeure du contenu, **pas un bouton** ; une Journey terminale ne reçoit aucun CTA de continuation fabriqué.
- Attente et action restent distinctes ; l'attente a une représentation neutre, sans carte d'alerte orange ni discours réseau.
- Les éléments déjà réglés sont regroupés en bas, accessibles sans dominer le présent.
- Accepter/refuser une invitation conserve la vérification propriétaire antérieure ; aucune file locale non idempotente n'est inventée et aucun succès n'est affiché sans confirmation.

## B6 — Formulaires, Requirements, documents et ressources

- API Journey : les demandes de formulaires exposent désormais le vrai titre de la version `FormVersion` et `opens_at` en plus de l'état, des échéances et des capacités.
- Flutter : les formulaires nommés restent ouvrables en lecture même lorsque la capacité de réponse n'existe plus ; seules les capacités du propriétaire donnent le droit de compléter.
- Web : la page canonique montre les FormRequests autorisées avec leur titre, statut, obligation, échéance et route `questionnaires:request-detail`. Pas de formulaire parallèle dans Journey.
- Requirements : libellé, état, caractère obligatoire et conséquence sont conservés depuis les Assessments propriétaires, avec handoff vers le détail réel.
- Preparation : les ressources **ne sont pas recopiées dans la projection Journey**. `PreparationResourcesRepository` expose déjà `preparation.journey.resources` dans la BDD du Profil.
- Le N3 Flutter observe cette projection locale et affiche jusqu'à trois documents / liens / instructions identifiés par leur titre et type, avec ouverture vers la profondeur Preparation existante ; un owner confirmé vide ne produit pas une fausse liste.
- Les profondeurs Preparation « Documents et instructions » et « Élément nécessaire » restent lisibles sur projections locales en cas d'échec de transport. Une absence de donnée acquise donne un état neutre, tandis qu'un refus explicite 403/404 conserve son effet d'autorité ; elles ne montrent plus de blocage motivé seulement par la connectivité.
- Le cycle de synchronisation personnelle prépare progressivement les ressources des Journey connues dans `personal.ongoing`, avec les mêmes clés de Profil et des budgets bornés, sans précharger indistinctement les fichiers privés ni stocker un cache de widget.
- Dès qu'une projection Journey est acquise, ce même cycle prépare également les détails Questionnaires et Requirements référencés par des **liens owner exacts**. Chaque famille est bornée à six détails sélectionnés par cycle, sans endpoint inventé ni élévation de capability. Les formulaires conservés comprennent leurs questions et les brouillons continuent d'être gérés par les propriétaires existants.
- Un clic de ressource externe ne vaut pas accomplissement d'une Requirement ou d'une Journey.

## B7 — Informations pratiques et propriétaires composés

- L'Occurrence autorisée de la Journey expose ses horaires connus et, s'il existe, le lieu principal de la relation `OccurrencePlace`, sans inventer de localisation ou d'heure pour une date seule.
- Flutter montre la date, l'heure, le lieu et les consignes réellement exposés par le propriétaire ; les valeurs absentes ne deviennent pas des prompts techniques.
- Payment : le N3 utilise le résumé propriétaire existant et présente **chaque** obligation lorsqu'elles sont multiples. Les états `satisfied`, `waived`, `refunded` ne sont pas présentés comme des transactions payées. Les destinations natives existantes sont `/payments/obligations/:id` et `/commerce/orders/:id`, sans paiement exécuté depuis Journey.
- Access : le handoff canonique existant reste associé au droit d'accès, indépendant du fait que la Journey soit terminée.
- Jour J et Makolo Live ne sont présentés que lorsque les capacités et liens du propriétaire sont exposés. Le texte est raccourci sans se substituer aux faits.
- Activity et Occurrence sont distinguées dans la section Contexte ; aucune identité ou statut parallèle n'est créée.

## Local-first : contrainte structurante

Le rendu N3 reste consommateur de **projections locales via `ProfileStore`**, pour Journey et Preparation. Les acquisitions réseau mettent à jour les propriétaires dans la BDD du Profil, sans être une étape obligatoire pour afficher le contenu déjà acquis. Aucun « mode hors ligne » et aucun écran de tutoriel réseau. Les refus propriétaires explicites priment ; les transports échoués ne suppriment pas la consultation.

Les commandes qui demandent confirmation propriétaire ne sont jamais déclarées accomplies à cause d'un clic, d'un brouillon ou d'une tentative de transport.

## Pas de faux achèvement

Ce lot n'a ajouté ni modèle, ni migration, ni nouvelle API de paiement/permission, ni un mécanisme artificiel pour Capacity/Waitlist, JourneyArtifact, Proof ou Credential. Lorsque le détail actuel ne fournit pas un fait ou un handoff autorisé, Journey ne le fabrique pas. Les capacités spécialisées et la validation de leurs profondeurs restent chez leurs propriétaires.

## Fichiers touchés

- `core/api/detail_projections.py` et `core/api/detail_views.py` : FormVersion et lieu d'Occurrence.
- `core/participant_views.py` et `templates/core/participant_journey_detail.html` : Web Forms et messages concis.
- `mobile/lib/features/journey/journey_selector.dart` : champs propriétaires et vues de préparation.
- `mobile/lib/features/journey/journey_repository.dart` : validation des liens propriétaires vers Questionnaires et Requirements avant préparation en BDD.
- `mobile/lib/features/journey/journey_detail_screen.dart` : composition de B5–B7.
- `mobile/lib/features/journey/journey_routes.dart` : handoffs Payment / Commerce et injection Preparation.
- `mobile/lib/features/preparation/{preparation_resources_screen,requirement_detail_screen}.dart` : état local-first dans les profondeurs propriétaires.
- `mobile/lib/app/sync_lifecycle.dart` : préparation bornée de Preparation dans la même BDD locale.
- `core/test_journey_n3_lot_b.py`, `core/test_z5_detail_api.py` et `mobile/test/journey_reference_depth_test.dart` : garde-fous ciblés.

## Contrôles restants avant intégration

Pas de CI ni d'exécution Flutter/Django ou Android revendiquée à ce stade. Faire plus tard la vérification de format Dart, analyse statique, tests ciblés, page N3 depuis différentes origines, cold start après acquisition, changement de Profil, refus propriétaire, formulaire complété/lecture seule, plusieurs obligations, ressources vides/absentes et perte de réseau, puis revue visuelle.

Ne pas fusionner avec des gates rouges.
