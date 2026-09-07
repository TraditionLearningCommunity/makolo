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
