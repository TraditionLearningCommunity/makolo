# Conversations — Lot 3 : interactions des Points

Date : 9 novembre 2026  
Dépôt : `TraditionLearningCommunity/makolo`  
Branche : `fix/discover-a-continuation-context-20261014` — PR #522

## Périmètre

Lot 3 poursuit les Lots 1–2 : les médias sont lus au bon endroit, et les
Points doivent désormais **faire avancer la coordination**. Aucune nouvelle
table de réponse ni nouveau domaine d'interaction n'est créé.

Le contrat UX de référence est
`Makolo_UX_Conversations_Contrat_Consolide_2026-10-09.md` :
`purpose` ≠ `response_mode` ≠ `resolution_policy`, accès recalculé sur le
serveur, résolution Conversation ≠ mutation du domaine propriétaire.

## Capacités réellement disponibles

| Point | Action adaptée | Service propriétaire |
| --- | --- | --- |
| Information | Lecture ; « J'ai pris connaissance » si acknowledgement exigé | `acknowledge_point` |
| Question | Réponse texte / nombre / date / date-heure selon `response_mode` | `submit_point_response` |
| Confirmation | Oui, je confirme / Non, je ne confirme pas | `submit_point_response` |
| Request | Je m'en charge / Je ne peux pas (engagement, pas achèvement automatique de la tâche) | `submit_point_response` |
| Poll | Un choix ou plusieurs ; chaque assertion conserve son média et sa légende | `submit_point_response` |
| Form Request | Ouverture de la `FormRequest` canonique, états demandée/terminée | Questionnaires |
| Exchange | Consultation et contribution dans le Point d'échange | `create_exchange_entry` |
| Point géré | Clore les réponses / Résoudre avec conclusion et choix retenus | `close_point_responses`, `resolve_point` |

Les réponses fichier/voix restent gérées par les bridges privés existants ;
aucun média ne devient implicitement Resource, Proof, JourneyArtifact ou
document public.

## Projection serveur

Nouveau module `conversations/point_interactions.py`, appelé par
`_serialize_point` et par les tags Web :

- `can_respond` : fenêtre ouverte, audience, état de réponse personnelle
  et possibilité de changer une réponse ;
- `response_window_open`, `response_hint` : état humain lorsque répondre
  n'est plus possible (échéance, clôture, résolution, etc.) ;
- `can_acknowledge`, `acknowledged` ;
- `can_close_responses`, `can_resolve` : autorité de gestion et audience
  de résolution, jamais simplement parce que l'on peut répondre ;
- `my_response` : uniquement la réponse personnelle de ce Profile ;
- `represented_responses` : réponses d'Espaces uniquement lorsque le
  Profile dispose de `SPACE_CONVERSATIONS_PUBLISH` pour l'Espace concerné ;
- `poll_results` : décomptes des choix et nombre de réponses **agrégés**,
  seulement pour les gestionnaires ou sous les visibilités `AGGREGATE`
  et `POINT_VIEWERS`. Aucun auteur/identifiant de répondant n'est exposé
  avec ces décomptes.

Le client ne décide jamais l'autorisation : chaque mutation appelle le
service canonique avec le viewer réel et l'état actuel du Point.

## Mutations et idempotence

API sous `/api/v1/conversations/points/<uuid>/` :

- `POST respond/` : service de réponse canonique déjà existant.
- `POST acknowledge/` : service de prise de connaissance déjà existant.
- `POST close-responses/` : clôture serveur réservée aux gestionnaires.
- `POST resolve/` : conclusion de 1 à 500 caractères, éventuellement
  choix retenus d'un Sondage. Aucun état Activity/Journey/Payment/etc.
  n'est modifié par cet endpoint.

Réponses : un `client_reference` déjà confirmé retourne la même réponse
autorisée même si le Point a été clôturé entre temps ; une nouvelle réponse
doit toujours passer les règles actuelles d'ouverture et d'autorisation.
Le contrôle d'autorité pour lire/réitérer une résolution s'applique aussi
au Point déjà résolu. La confirmation de lecture exige l'audience
attendue lorsqu'elle est définie.

Une résolution automatique peut désormais afficher le libellé du choix
retenu lorsqu'un seul vainqueur existe. L'agrégation respecte les réponses
actives et la règle de résolution existante.

## Web

Le template `_point.html` se base sur les actions serveur et non sur un seul
`attention_reason`. Il propose :

- sélection de choix avec les médias propres à chaque assertion ;
- votre choix déjà enregistré et, si autorisé, les résultats agrégés ;
- champs et boutons adaptés aux différents `response_mode` ;
- `client_reference` unique par formulaire de réponse pour éviter
  les doubles soumissions ;
- prise de connaissance visible tant qu'elle est due ;
- ouverture de la FormRequest canonique même hors du filtre d'attention ;
- décision de coordination distincte, avec champs de résolution et
  bouton séparé pour clore les réponses ;
- explications quand le délai est passé ou le Point est clos.

Routes Web : `point-close-responses` et `point-resolve`. Les erreurs
d'autorisation ou de validité sont affichées sans annoncer un succès.

## Flutter

`ConversationRepository` exige une confirmation de réponse HTTP contenant
l'ID/état attendu pour la réponse ou l'acknowledgement. Il expose aussi
`closePointResponses` et `resolvePoint` avec relecture du Point après
confirmation.

`_PointCard` affiche :

- choix interactifs (unique/multiple), médias, légendes et décompte permis ;
- choix personnels déjà faits, et réponse de l'Espace représenté si celui-ci
  est explicitement sélectionné et autorisé ;
- contrôles adaptés Question/Request/Confirmation ;
- état « déjà répondu », « réponses closes », « délai passé », etc. ;
- boutons métier de clôture/résolution uniquement lorsque les permissions
  serveur le permettent ;
- dialogue de clôture délibéré ; dialogue de résolution avec texte et choix
  retenus, brouillon conservé en cas de non-confirmation.

Le résultat n'est déclaré enregistré qu'après confirmation propriétaire.
Un conflit de lifecycle provoque une nouvelle lecture et une invitation à
vérifier l'état actuel. Aucun succès optimiste n'est écrit hors ligne pour
une résolution ou une réponse sensible.

## Limites et frontières

- Les statuts métier réels, paiements, présences, accès, exigences et
  réservations demeurent chez leurs propriétaires ; la résolution ne fait
  pas ces mutations.
- Les médias de réponses et le moteur Questionnaires restent séparés du
  moteur de résolution Conversations.
- Le regroupement chronologique du passé, les sections repliables et
  l'histoire compressée relèvent du **Lot 4**, pas de ce Lot 3.
- Les droits `response_visibility` des Points historiques sont respectés :
  le Lot 3 n'élargit pas leur visibilité ni celle des auteurs individuels.
- Aucune migration métier requise pour ce lot : réutilisation des
  `ConversationPointResponse`, `ConversationPointUserState`,
  `ConversationPointResolution` et `ConversationPointOption` existants.

## Livraison et vérification

Modifications poussées uniquement sur la branche de travail de la PR #522,
sans fusion dans `main`.

Conformément à la consigne du chantier, ni CI, ni tests automatisés,
ni exécution manuelle Web/Android ne sont réalisés dans cette session.
La revue est statique : code poussé ne signifie **pas encore validé à
l'exécution**. Avant toute utilisation de test, contrôler sur l'émulateur
les rôles participant, organisateur et staff, les réponses simples/multiples,
l'ouverture du formulaire, l'accès aux résultats agrégés, les refus d'accès,
les doubles envois et le conflit de résolution.
