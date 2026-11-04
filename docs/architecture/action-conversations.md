# Makolo — Tâche J : Conversations d’action

> **Statut : canonique pour la cible d’implémentation J.**
>
> Ce document fixe les frontières et invariants de la capacité Conversation d’action. Le runtime courant reste prioritaire : avant chaque checkpoint J, revalider `main`, CI, migrations, PR/branches et docs touchées.

## 1. Promesse

Makolo Conversations n’est pas un chat ajouté au produit. La capacité doit permettre aux personnes légitimement concernées de savoir, demander, répondre, choisir, confirmer, échanger, remplir, partager, décider et résoudre sans devoir reconstruire la situation à partir d’une chronologie de messages.

Principes produit :

- **Ne jamais demander à l’utilisateur de lire le passé pour découvrir son présent.**
- **Dans une messagerie, le passé s’accumule. Dans Makolo, le passé se résout et se compresse.**
- Le badge Conversation répond à : **« combien de choses ont encore besoin de moi ? »**
- Une bonne Conversation Makolo tend naturellement vers sa propre résolution.
- `Tout est en ordre. ✓` est une conclusion valide lorsqu’aucune action n’est attendue du Profile.

## 2. Frontières canoniques

```text
Conversation ≠ ActionNeed ≠ ActionProposal ≠ ActivityInvolvement
Conversation ≠ Assignment ≠ Mandate ≠ Journey ≠ Form ≠ Notification
Point ≠ décision métier ≠ vérité canonique d’un domaine propriétaire
```

Une Conversation n’accorde jamais implicitement Permission, Mandate, Access, Journey, Payment, Capacity, ActivityInvolvement ou accès à des données privées.

Participation et autorité restent distinctes :

```text
ConversationParticipation ≠ Mandate
Audience ≠ Mandate
Membership ≠ Mandate
ActivityInvolvement ≠ Mandate
```

`social.Contribution` reste la capacité UGC contextualisée M5 ; J ne migre pas les Contributions historiques vers Conversation.

## 3. Position de J

J est une capacité transverse de coordination de l’action. Elle compose les domaines existants plutôt que de copier leur vérité : Profile, Space, Group, Activity/Occurrence, Journey, Action Network, Dossier/Project, Forms, Access, Sharing, Notifications, Domain Events, Automation, Interoperability et Presentation.

J est livré par checkpoints techniques, mais il n’existe qu’une architecture cible Mature :

```text
J0 Contracts & convergence
J1 Conversation Core
J2 Audience Engine
J3 Points & Resolution
J4 Mature Conversation Experience
J5 Contact & External Routing
J6 Forms & Media
J7 Automation, API & Hardening
```

Les checkpoints ne sont pas des versions produit jetables.

## 4. J0 — pré-convergence

Avant la première migration `conversations`, J0 doit stabiliser les dépendances déjà présentes :

1. les services Action Network utilisent réellement les permissions fines `space.action_network.*` et `activity.action_network.*` ;
2. l’autorité Activity Action Network peut être héritée explicitement d’un Mandat Space Action Network lorsque l’Activity appartient à ce Space ;
3. les événements matériels ActionNeed/ActionProposal déclarés dans `domain_events.contracts` sont réellement émis par les services transactionnels ;
4. le payload des événements reste minimal et n’embarque pas le texte libre des besoins/propositions ;
5. un selector canonique dérivé retourne toutes les `ActionProposal` actuellement `PENDING` auxquelles l’acteur est autorisé à répondre, y compris Profile, représentation d’un Space et propriétaire autorisé du Need ;
6. aucune table Inbox persistante n’est créée.

### Action Inbox

Le contrat est :

```text
action_proposals_requiring_actor_response(actor)
```

Il doit couvrir :

- invitation `OWNER_TO_CANDIDATE` vers le Profile acteur ;
- invitation vers un Space que l’acteur peut représenter avec `space.action_network.manage` ;
- proposition `CANDIDATE_TO_OWNER` sur un Need personnel de l’acteur ;
- proposition `CANDIDATE_TO_OWNER` sur un Need Space/Activity que l’acteur peut gérer via les permissions Action Network ;
- uniquement les Proposals en attente ;
- aucune fuite d’une Proposal hors autorité.

Ce selector devient la source de vérité réutilisable par les futures projections Home/Conversation/attention. Il ne transforme pas ActionProposal en Point.

### Domain Events Action Network

Événements matériels attendus :

```text
action_need.opened
action_need.paused
action_need.filled
action_need.cancelled
action_need.expired

action_proposal.created
action_proposal.accepted
action_proposal.declined
action_proposal.cancelled
action_proposal.expired
```

Les événements transportent des IDs et états minimaux. Ils ne transportent pas le message de Proposal, le titre/description libre du Need, email, téléphone ou autre PII inutile.

## 5. Conversation Core cible

La capacité sera portée par une application Django dédiée `conversations`, pas par `social` ni `notifications`.

Objets conceptuels :

- `Conversation` — espace durable de coordination ;
- `ConversationContext` — contexte primaire explicite sans GenericForeignKey universel ;
- `ConversationPolicy` — modes autorisés ;
- `ConversationParticipation`, Invitation, JoinRequest — uniquement lorsque l’accès n’est pas entièrement dérivé ;
- `ConversationUserState` — mute/hide/archive/pin/revisit personnels ;
- `ConversationAudienceSet` / `ConversationAudienceRule` — ciblage dérivé des relations canoniques ;
- `ConversationPoint` — unité de communication orientée finalité ;
- `ConversationPointResponse` — réponse structurée ;
- `ConversationPointResolution` — résultat compressé ;
- `PointExchangeEntry` — échange libre à l’intérieur d’un Point d’échange ;
- `ContactRequest`, endpoints additionnels et routes externes ;
- bridges explicites vers Forms, Sharing, Interoperability et stockage privé.

## 6. Contextes

Contextes initiaux ciblés : Space, Group, Activity, Occurrence, Dossier, Project, Journey, ActionProposal et Direct Profile↔Profile.

Pas de `GenericForeignKey` universel. Chaque type de contexte doit fournir un adapter explicite répondant au minimum à :

- qui peut voir ;
- qui peut contribuer ;
- qui peut administrer ;
- pourquoi cette personne y a accès ;
- quelles audiences sont légitimes ;
- quand la Conversation peut se fermer.

Règle : **Audience différente → Point ciblé. Finalité/confidentialité réellement différente → éventuellement Conversation distincte.**

## 7. Audience

Une Conversation officielle ne matérialise pas par défaut une ligne de destinataire par personne. Les selectors composent les relations canoniques : Access/Journey d’Occurrence, GroupMembership, ActivityInvolvement et ses fonctions, parties d’ActionProposal, participations explicites, autorités.

Chaque Point distingue :

```text
visibility_audience
response_audience
expected_action_audience
resolution_audience
response_visibility
```

Exemple : 500 personnes voient un Point, 12 speakers doivent répondre, 3 responsables autorisés voient les identités, tout le monde voit le résultat agrégé.

L’accès final est toujours recalculé côté serveur ; un cache ou index d’audience ne devient jamais une permission.

## 8. Point

Kinds initiaux : Information, Question, Confirmation, Poll, Request, Form Request, Exchange.

Séparer trois axes :

```text
purpose ≠ response_mode ≠ resolution_policy
```

Response modes initiaux : NONE, FREE_TEXT, BOOLEAN, SINGLE_CHOICE, MULTIPLE_CHOICE, NUMBER, DATE, DATETIME, FILE, VOICE.

Lifecycle cible :

```text
DRAFT → OPEN → RESPONSE_CLOSED / RESOLVED / EXPIRED / CANCELLED / SUPERSEDED
RESOLVED → SUPERSEDED
```

`deadline_at` (réponse attendue) est distinct de `valid_until` (validité opérationnelle).

## 9. Résolution et vérité courante

Une résolution de Point ne modifie jamais implicitement une vérité métier. Exemple : un sondage peut conclure à 16h30, puis une action explicite et autorisée appelle le service Activity/Occurrence qui devient propriétaire de l’horaire effectif.

Les informations remplacées sont `SUPERSEDED` et restent historiques. Search/Essentiel privilégient toujours la vérité/résolution actuelle avant les anciens échanges.

## 10. Direct Profile↔Profile

Le Profil public n’implique pas la capacité de DM. Flux cible :

```text
Profil → Contacter → intention → contexte/consentement
→ Point ou ActionProposal → éventuellement Conversation directe
```

Réutiliser `ActionNetworkBlock` comme exclusion de mise en relation ; ne pas créer un `ConversationBlock` concurrent. Une Proposal acceptée peut permettre une Conversation contextualisée, sans transfert de Permission/Mandate/Access.

## 11. Forms, media et canaux externes

- Réutiliser le moteur `questionnaires`; ne pas créer ConversationForm/Question/Answer.
- Généraliser `FormRequest` proprement pour une cible Profile non-Journey lorsque J6 l’exige.
- Réutiliser stockage privé et validation upload ; Attachment Conversation ≠ Resource ≠ Proof ≠ JourneyArtifact.
- Les routes WhatsApp/Telegram/Messenger/Viber/SMS/email/phone restent audience-scoped et privacy-safe.
- Les vraies intégrations provider/API passent par M7 `Interoperability / Connection / Action`, pas par des services provider spéciaux dans Conversation.

## 12. Notifications, Automation et realtime

```text
Point = objet de coordination
Notification = signal
Home = projection de ce qui compte maintenant
Automation = orchestration
```

Aucun `ConversationReadiness` persistant.

Autopilot reste le scheduler actuel. Le realtime est un transport optionnel après commit : la vérité passe par transaction DB. Une panne WebSocket ne doit pas empêcher la création/réponse/résolution d’un Point.

## 13. Qualité et sécurité

Chaque checkpoint J applique des tests ciblés avant la CI complète : permissions/IDOR, migrations touchées, concurrence PostgreSQL lorsque nécessaire, idempotence, compatibilité des données anciennes et divulgation minimale.

Ne jamais affaiblir un test pour obtenir du vert. Corriger la cause racine.

## 14. Critère produit de fermeture

J est fermé lorsque Makolo peut montrer à un Profile non pas combien de messages se sont accumulés, mais ce qui reste effectivement à savoir, répondre, confirmer, décider ou résoudre, tout en conservant l’historique et les frontières canoniques.

> **Pas le plaisir de rester. Le plaisir d’avancer.**


## 15. C3 — Composition Web et Flutter (contrat de consommation)

Le compositeur travaille sur une Conversation réelle et ne déclare un envoi réussi qu'après confirmation du propriétaire serveur. Il consomme la projection `composer` de `GET /api/v1/conversations/{id}/` : `can_create`, `allowed_kinds`, audiences disponibles, sélection requise, `text_mode`, échange cible et capacité explicite de représentation d'Espace.

Les commandes autorisées et leurs propriétaires sont :

- `POST /api/v1/conversations/{id}/compose/` : `mode=text` contribue au Point Exchange actif et autorisé (sélection explicite s'il y en a plusieurs) ou crée une Information seulement avec l'autorité de publication ; `mode=point` publie Information, Question, Demande, Confirmation, Sondage ou Point Exchange conformément à la policy. Un `client_reference` stable rend les reprises idempotentes.
- `POST /api/v1/conversations/points/{point_id}/entries/` : contribution textuelle au Point Exchange canonique, avec contrôle du destinataire, de l'acteur et de la période d'ouverture.
- `GET /api/v1/conversations/by-context/{kind}/{id}/` : retourne les Conversations existantes visibles et `can_ensure` calculé par le serveur.
- `POST /api/v1/conversations/by-context/{kind}/{id}/ensure/` : crée/réutilise la Conversation de contexte via le service métier si l'autorité MANAGE est vérifiée. Aucun DM direct n'est créé depuis le Profil public ; les Conversations directes autorisées déjà établies restent consommables.

La réponse d'une commande n'est pas un transfert de `Permission`, `Mandate`, `Access` ni d'autorité sur les médias. La projection Web/Flutter filtre les extraits Exchange selon la visibilité des réponses, pas seulement celle du Point. Les erreurs préservent le brouillon et la référence d'idempotence ; aucune action hors ligne n'est affichée comme envoyée. Les actions Form Request, vocal et média relèvent de C4.


## 16. C4 — Formulaires, vocaux, médias privés et profondeur Exchange

C4 raccorde des **propriétaires existants**, et non un second stockage documentaire ou un flux de messages.

**Form Request → Questionnaires.** La capacité `composer.can_form` dépend de `ConversationPolicy.allow_form_requests`, de la permission de publier et de `activity.manage` sur l'Activity portant le contexte. `composer.form_options` expose seulement les versions publiées de cette Activity. `POST /api/v1/conversations/{conversation_id}/forms/` prend `title`, `client_reference`, `audience_id` et soit `form_version_id` (réutilisation), soit `questions` (préparation de 1 à 8 questions simples). Il appelle les services de `questionnaires`, publie un Point `form_request` et matérialise **un FormRequest canonique par Profil attendu et réellement autorisé**. Le Point indique au seul destinataire `form_request.id/status/links`. Le Web ouvre `questionnaires:request-detail` ; Flutter ouvre le formulaire propriétaire sur `/conversations/{conversation_id}/forms/{request_id}` sans inventer de Journey.

**Media → stockage privé Conversation.** `composer.media_kinds` découle de la policy et de la capacité de publication ou de contribution Exchange. `POST /api/v1/conversations/{conversation_id}/media/` accepte multipart `file`, `kind`, `client_reference` et les paramètres contextuels permis. Les documents et images réutilisent `validate_artifact_upload` ; les signatures audio/vidéo sont vérifiées par le bridge Conversation. Le service crée `ConversationPointAttachment` lié au Point ou à l'entrée Exchange, avec idempotence de référence et de contenu. Les octets sont privés. `GET /api/v1/conversations/attachments/{attachment_id}/download/` revalide les droits à chaque requête, envoie `private, no-store`, et ne révèle pas un objet interdit. Flutter récupère via le transport authentifié dans un fichier temporaire, puis l'efface à la fermeture du lecteur. La capture vocale démarre au premier appui après permission OS ; pause, reprise, annulation, aperçu et envoi sont séparés. La perte réseau ne déclare jamais une réussite.

**Point Exchange → contributions.** `GET/POST /api/v1/conversations/points/{point_id}/entries/` expose une profondeur N2 paginée et une contribution textuelle via `create_exchange_entry`. Les extraits, les entrées et chaque pièce sont filtrés par `point_visible_to`, `response_visibility` et l'autorité courante ; une permission de voir un Point ne rend pas publiques les réponses privées de ses contributeurs.

**Frontières.** Un formulaire n'est pas un Point libre de questionnaire parallèle ; un média Conversation n'est ni Resource, ni Proof, ni JourneyArtifact. Aucune réponse de sondage n'altère implicitement l'Occurrence. Les accès et autorisations restent contrôlés par le serveur. Tests ciblés : version Form liée à la bonne Activity, destinataire, expiration/refus, upload valide/invalide, idempotence/concurrence, visibilité des contributions et téléchargement anti-IDOR.

**Limite de vérification :** l'exécution sur appareil Android réel, en particulier permission micro et capture, doit être attestée séparément avant de déclarer la recette matérielle fermée.

**Réponses média structurées.** Lorsqu'un Point canonique attend `response_mode=FILE` ou `VOICE`, `POST /api/v1/conversations/points/{point_id}/reply-media/` (ou sa route Web homologue) appelle `submit_point_response`, puis attache le fichier validé à **cette réponse** dans la même transaction. Cette action ne crée aucune Information supplémentaire. Une reprise avec la même référence et les mêmes octets retourne la réponse déjà confirmée, même après sa résolution ; un changement d'octets est refusé. La visibilité des pièces suit la réponse et `response_visibility`, recalculée au téléchargement.
