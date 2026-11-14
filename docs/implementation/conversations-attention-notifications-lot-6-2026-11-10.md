# Makolo Conversations — Lot 6 : attention, notifications et coordination

**Date :** 10 novembre 2026  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Branche :** `fix/discover-a-continuation-context-20261014`  
**PR :** #522 (ouverte ; aucune fusion vers `main`)

## Décision produit et frontière de propriété

Le contrat Now reste une projection du présent ; Conversations reste
**contexte d'action + Points structurés + audiences + réponses + résolution
+ mémoire compressée**. La chronologie du Lot 4 n'est ni filtrée ni triée
par la priorité de l'attention.

Trois sections sont calculées **en dehors** du fil et chacune renvoie au
Point canonique concerné :

- **Pour moi** : réponse, confirmation de prise de connaissance ou
  questionnaire effectivement attendus du Profil courant.
- **À régler** : décision de résolution désormais autorisée au gestionnaire
  concerné. Une Conversation ouverte n'est pas, à elle seule, une tâche.
- **À savoir** : Point personnel « à revoir », information récente,
  résultat récent ou fenêtre future explicitement ciblée.

Une notification n'est **pas** une Situation Now, un Point, une tâche ou
une vérité métier. Elle interrompt seulement lorsque le domaine le justifie.
Les rappels restent possédés par Notifications et exécutés dans Autopilot.

## Correction du moteur d'attention

`conversations/attention.py` utilise désormais les autorisations réelles :

- `point_visible_to` garantit les audiences et la règle `FROM_JOIN`,
  y compris quand un Groupe ou Espace a été ajouté au Lot 5 ;
- `point_interactions_for_profile` vérifie les droits d'action réels,
  les réponses déjà apportées, les fenêtres ouvertes et les actions
  possibles : attendre une réponse ne suffit pas à supposer qu'on peut
  répondre ;
- un Point futur ne compte pas dans les actions dues ;
- un Point résolu ou une Conversation fermée ne réclame plus de réponse ;
- les décisions de résolution peuvent remonter même si l'audience de
  résolution explicite est absente, notamment à la clôture des réponses ;
- un marqueur personnel `revisit` n'est pas additionné au compteur
  d'**actions exigibles** ;
- la sélection globale des actions est parcourue en pages de DB jusqu'à
  la limite de **Points autorisés** : une première fenêtre entièrement
  invisible à l'utilisateur ne peut plus produire un faux zéro ;
- badges, `attention-presence`, listes « À traiter » et présentation
  d'action de Now reposent sur les mêmes raisons d'attention réelles.

La permission serveur `acknowledge_point` interdit également une
confirmation avant `opens_at` et après `valid_until` ; le client
ne constitue pas une frontière de sécurité.

## Synthèse des trois sections

`conversations/attention_projection.py` fournit
`conversation_attention_sections(profile, conversation)`.

- Points ouverts ou réponses closes examinés indépendamment de leur âge :
  un vieux Point non réglé ne disparaît pas sous les publications récentes.
- Résultats récents bornés, revisites personnelles anciennes réintroduites
  explicitement, avec vérification d'audience et historique à chaque lecture.
- Chaque carte : `id`, `conversation_id`, `reason`,
  `reason_label`, `deadline_at`, `deadline_state`, `actionable`,
  `url` vers le Point exact.
- Aucun résultat de résolution privé ni Point inaccessible n'est renvoyé.
- `action_count` comptabilise les actions actuelles ; le nombre de
  cartes affichées est borné et `more_actions` l'indique explicitement.
- L'ordre des actions peut suivre les échéances réelles.
  **Le fil chronologique lui-même ne change jamais d'ordre**.

API privées, sans cache partagé :

- `GET /api/v1/conversations/<uuid>/attention/` ;
- `GET /api/v1/conversations/<uuid>/` ajoute `attention` sans retirer
  `timeline`, `points`, `essential` ou `elsewhere` existants.

Web : `templates/conversations/_attention.html` au-dessus de
`templates/conversations/detail.html`.
Flutter : section déroulante « À présent » au-dessus du fil, sans
modifier son `ScrollController` ni la position des publications.
Chaque carte mène au Point précis, même lorsque celui-ci est dans un
groupe de Points terminés ou hors de la fenêtre récente ; les échéances
restent affichées en heure locale.

## Suivi personnel d'un Point

Réutilisation **sans migration** de
`ConversationPointUserState.revisit_at` et `pinned_at`.

- `update_point_personal_state` exige un Point toujours accessible et
  n'affecte aucun autre utilisateur, aucun statut métier ni Mandate.
- `POST /api/v1/conversations/points/<uuid>/personal-state/`
  accepte les booléens `revisit`/`pinned`.
- Bouton Web et Flutter « Revoir ce Point » / « Ne plus revoir ».
- Un Point ancien ou résolu marqué `revisit` peut être retrouvé dans
  « À savoir » si le Profil possède encore son accès.
- Marquer « À revoir » n'est pas une clôture, une priorité globale,
  ni un déclencheur arbitraire de push.

## Rappels et ouvertures via Autopilot existant

`automation/service_reminders.py`, déjà appelé par
`automation/scheduler.run_autopilot_cycle`, comprend deux passages
supplémentaires :

1. **J-3 / J-1** avant `ConversationPoint.deadline_at`,
   dans la fenêtre de jalon du moteur de rappels existant ;
2. **ouverture de fenêtre** lors de `ConversationPoint.opens_at`,
   uniquement si une action devient réalisable.

Pour chaque destinataire, le moteur recalcule l'audience prévue, le droit
`point_visible_to`, la possibilité actuelle
`point_attention_reason` et les blocages d'accès du Lot 5.

La création utilise `notifications.services.create_notification`,
avec `dedup_key` contenant Point, jalon, destinataire et échéance.
Une seconde exécution ne crée pas de message identique. Notifications
conserve la notification interne même si la Conversation est en sourdine ;
les interruptions externes (push) ne sont pas mises en file pour une
Conversation actuellement muette. Les préférences et heures calmes
restent celles de Notifications.

Aucune nouvelle table d'Automation, politique de scheduler, migration
de statut ou minuterie parallèle n'a été créée.

## Domain Events et notifications en attente

`notifications/conversation_domain_event_consumer.py` continue à
consommer les Domain Events canoniques de publication, clôture, résultat
et invitation, avec :

- vérification de l'accès au Point pour chaque destinataire ;
- lien ciblé `?focus=<point_id>#point-<point_id>`, au lieu de
  l'en-tête générique de la Conversation ;
- distinction entre notification interne et livraison externe muette ;
- aucune notification d'action à quelqu'un qui ne peut réellement plus agir.

Au **moment de l'expédition externe**,
`notifications.services.dispatch_delivery` revérifie la visibilité
de la Conversation, du Point, l'action toujours due, la résolution
toujours visible et la sourdine actuelle. Une notification dépassée est
ignorée pour la livraison externe au lieu de révéler un contenu devenu
privé ou d'interrompre inutilement un destinataire.

`notifications.navigation` transmet le `point_id` structuré.
Les routeurs Web et Flutter conservent ce Point en ouvrant la
Conversation ; son endpoint reste l'autorité de lecture finale.
Aucun titre ou texte libre de notification n'est interprété comme
identifiant de destination.

## Compatibilité et validation

- Les Lots 1–5 et les modèles canoniques de Questionnaire restent
  propriétaires de leurs propres actions et données.
- Les clients qui ignorent les nouveaux champs `attention`, `revisit`,
  `more_actions` et `navigation.point_id` conservent les anciennes
  projections de détail et de liste.
- Le volet d'attention ne modifie pas le classement chronologique établi
  au Lot 4 ni la visibilité des participants établie au Lot 5.
- Aucun changement de schéma ni migration supplémentaire pour le Lot 6.

**Statut : code poussé sur la branche de la PR #522, sans fusion.**
Conformément à la consigne explicite du chantier en cours, **aucun test
automatisé, aucune CI, compilation Web/Flutter ni déploiement** n'ont été
exécutés lors de cette intervention. La vérification réalisée est
statique (fichiers, points d'entrée, liens, délimiteurs). Cette limite
empêche de déclarer la fonction validée à l'exécution.

La validation de terrain du Lot 7 devra couvrir au minimum la perte de
permission, `FROM_JOIN`, un Point clos/rouvert, une réponse faite après
la mise en file du rappel, une Conversation en sourdine, un nouvel
identifiant de Groupe/Espace accepté puis retiré, les dates/fuseaux,
les liens vers Points anciens, l'absence de doublons après deux cycles
Autopilot, et les vues Web/Android.
