# Journey N3 — composition universelle et variantes contextuelles

**Dépôt :** TraditionLearningCommunity/makolo · **PR :** #522 · **Branche :** `fix/discover-a-continuation-context-20261014`.  
**Date :** 12 novembre 2026 · **Périmètre :** Démarche N3, sans refonte de Découvrir, Notifications, Conversations, Jour J ou Makolo Live.

## Structure universelle

La page unique est organisée en cinq niveaux, dont les contenus sont conditionnels :
1. **Mon objectif** — titre, état réel, date/plage horaire/lieu de l'Occurrence lorsqu'ils existent, compteur civil Jour −N / Jour J / Jour J +N et icône de conversation uniquement si son propriétaire autorise l'entrée. Le titre n'est pas répété dans un « Contexte » ou un résumé inutile.
2. **Description** — description propriétaire utile avant le parcours, sans carte supplémentaire ; absence si vide ou identique au titre.
3. **Situation actuelle et Mon parcours** — action, attente, blocage, plusieurs actions, étapes véritables et dépendances, pas de pourcentage ni d'étape fictive.
4. **Préparation et engagements** — formulaires, Requirements, Readiness vérifiée, paiements, commande et Access, chacun lié à son propriétaire. Une donnée absente n'engendre pas de bloc vide.
5. **Ressources, informations complémentaires et historique** — références Preparation acquises dans la BDD du Profil, adresse ou consignes réellement supplémentaires, liens Activity/Occurrence autorisés, dix dernières transitions Journey partageables.

## Les six variantes dérivées des faits

`JourneyComposition` possède une présentation déterministe : `action`, `waiting`, `blocked`, `choices`, `completed` et `calm`. Les variantes sont des configurations d'une seule page, pas des routes ou des états métier parallèles. Les branches ne sont mises en évidence que si les `JourneyStep.dependsOn` réels établissent une dépendance de type embranchement. Les étapes passées et lointaines sont repliées pour préserver la lecture du présent.

- **Action** : uniquement un mouvement autorisé par le lien propriétaire reconnu, sinon une information non cliquable.
- **Attente** : pas de bouton fabriqué, situation neutre et humaine.
- **Blocage** : obstacle réel en priorité, possibilité de résolution seulement si le propriétaire fournit un lien.
- **Choix multiples** : toutes les interventions propriétaires distinctes restent visibles, pas de sélection ou d'acquittement client.
- **Riche** : formulaires, exigences, paiement(s), commande, droit d'accès et ressources sont composés seulement s'ils sont réellement connus.
- **Terminale** : résultat réel, documents persistants accessibles, étapes réelles et historique des changements d'état ; aucune ancienne action présentée comme encore à accomplir.

## Démarche ≠ Jour J ≠ Live

Le badge civil Jour ±N n'est **pas** un état de Journey, ni une admission Jour J, ni une preuve que Makolo Live a commencé.

- Avant et après la date de l'Occurrence : repère temporel non cliquable.
- À Jour J : le badge ouvre la profondeur Jour J seulement si `open_day_of` et son lien propriétaire existent.
- Live : icône d'accès distincte seulement si `open_live` et son lien propriétaire existent ; aucun bouton Live fictif ni contenu Live dupliqué en N3.
- La page Jour J et l'expérience Live restent inchangées par cette passe.

## Local-first et propriétaires

Les vues Flutter sont composées des projections locales `ProfileStore` des domaines Journeys et Preparation. Le badge civil utilise les règles IANA embarquées ; il n'attend pas le réseau. Les erreurs de transport n'effacent pas le contenu déjà acquis ; une révocation propriétaire explicite reste autoritative.

Les documents de Preparation sont consultables en profondeur avec un texte repliable, `Consulter` distinct d'`Enregistrer une copie`. Les pièces/Proof ne deviennent pas validées par la seule possession d'un fichier. Payment reste propriétaire du statut des obligations ; Access du droit d'accès ; Commerce de la commande ; Journey de ses états et transitions.

L'historique Journey expose uniquement `id`, `state`, libellé de statut et date de transition, sans identité d'acteur, commentaire interne ni raison sensible. La projection est bornée à dix événements. Aucun modèle métier/migration ajouté.

## Ce qui n'a pas été inventé

Aucun planning opérationnel universel, placement, liste d'attente, capacité, réservation confirmée, QR ou document produit ne sont construits à partir de Journey en l'absence d'une projection de propriétaire autorisée. Le N3 n'affiche pas de zone Planning vide : les capacités et propriétaires de Jour J/Operations et Capacity/Placement restent distincts.

## Vérification

Tests introduits :
- `mobile/test/journey_universal_composition_test.dart` : six variantes, données contextuelles absentes, embranchements réels, badge Jour J et admission.
- `mobile/test/journey_history_projection_test.dart` : historique propriétaire local.
- `core/test_journey_n3_history.py` : historique borné et sans données privées.
Tests précédents conservés : Journey local-first, ressources, Payment, état terminal, Jour ±N en fuseau réel, permissions.

Les workflows Flutter/Django sur le HEAD doivent être vérifiés avant intégration ; aucun test Android réel ni compilation locale ne sont revendiqués tant qu'ils n'ont pas été exécutés. Ne pas fusionner avec CI rouge ou non vérifiée.
