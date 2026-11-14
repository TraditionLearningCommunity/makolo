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


## 17. C5 — Consultation mature, recherche et fermeture (4 novembre 2026)

### Contrat serveur de la profondeur

- `GET /api/v1/conversations/{conversation_id}/points/?section=history|active|all&q=…&limit=25&cursor=…` renvoie une page de Points **publiés et réellement visibles**. Le curseur est signé et lié au viewer, à la Conversation, au filtre, à la recherche, à la taille de page et au plafond temporel. Il ne peut pas être partagé entre Profils, Conversations ou filtres.
- La profondeur et les détails réévaluent `can_view_conversation`, `point_visible_to`, la policy `FROM_JOIN`, l'audience de résolution et la visibilité de chaque réponse ou pièce jointe. Aucun ancien Point ne donne accès au contenu d'un successeur privé.
- La recherche inspecte les titres, corps, résumés de résolution, pièces et contributions Exchange, **mais ne retient un résultat que si le viewer peut lire le texte ayant effectivement correspondu**. Pas de révélation par simple existence d'un match privé. Un Point remplacé reste consultable avec une liaison vers son successeur seulement s'il est visible.
- `response_status` exprime la réponse personnelle confirmée ; `response_count` n'est fourni qu'à une autorité ou lorsque le contrat `response_visibility` autorise l'agrégat. Jamais de liste d'identités dérivée des totaux.
- Une Conversation fermée reste consultable ; elle ne projette plus de capacité de réponse ni d'attention métier et refuse les mutations de Point/Exchange au serveur. Archiver, épingler, masquer, mettre en sourdine et revoir plus tard restent **des états personnels**, jamais une fermeture partagée.

### Contrat d'expérience Web / Flutter

- Liste et détail sont deux N1 distincts ; historique et Point précis sont des profondeurs N2. L'ouverture d'une profondeur conserve la pile de retour.
- La recherche depuis le détail inclut les Points actuels et passés ; les filtres permettent de distinguer historique, tous les Points et Points actifs. Les Conversations archivées restent retrouvables séparément des Conversations à traiter.
- Un nouveau Point confirmé déclenche le chargement ciblé de son identifiant pour le focus ; sa publication ne dépend pas du succès d'un GET de rafraîchissement. Une 403/404 retire les projections locales et les rows privées déjà présentées ; un timeout préserve uniquement la dernière projection autorisée et affiche une récupération.
- Les dimensions compactes à larges, le texte agrandi, le clavier, les états sombres et les boutons directs sont couverts par des scénarios Flutter dédiés ; l'application ne simule jamais un envoi hors ligne.

### Suite ciblée et critères d'intégration

Serveur : `python manage.py test conversations.test_c3_composition conversations.test_c4_rich conversations.test_c5_mature conversations.test_j7_contracts` (adapter aux modules présents sur le checkout actuel).

Flutter, depuis `mobile/` : `flutter pub get` puis `dart format --output=none --set-exit-if-changed lib/features/continuity test/conversation_c5_mature_test.dart`, `flutter analyze`, `flutter test test/conversation_c5_mature_test.dart test/conversation_mature_repository_test.dart`, puis les régressions de navigation locale et Goldens pertinentes. Régénérer et versionner `pubspec.lock` avec **la toolchain Flutter officielle** si les dépendances C4 `record`, `just_audio` et `open_filex` restent ajoutées ; ne pas fabriquer un verrouillage de dépendances à la main.

Recette visuelle : Conversation directe, Activity/Occurrence multipoints, Space multi-audiences et Conversation longue 150+ Points ; Compact 360/430, Medium 834, Wide 1440, clair/sombre, texte 1,6, réduction des animations, clavier et retour depuis N2. Android réel : ouvrir Conversation, répondre, publier, revenir au nouveau Point, capturer/annuler/envoyer un vocal, passer en mode avion et reprendre ; recueillir captures/Goldens réels.

**État de vérification :** les changements C5 et tests ciblés sont présents dans la PR #522 ; aucune exécution locale Flutter/Django sur le HEAD C5, aucun rendu Android réel ni Golden de référence nouvellement généré n'a été attesté depuis cet environnement connecté au dépôt. Ces gates restent obligatoires pour déclarer « livré, intégré et vérifié » et pour toute fusion ; ne pas les inscrire comme verts sans preuve.


## 18. C5-UX-Liste — Lecture visuelle immédiate des Conversations (5 novembre 2026)

### Problème observé

La liste N1 affichait simultanément le contexte complet, un titre de préparation contenant une copie du contexte, puis de longs textes métier. Sur mobile, une seule Conversation pouvait occuper une grande partie de l'écran. Il manquait les repères visuels (type de contexte, forme de contenus, résultat et action attendue). L'objectif n'est **pas** de se différencier artificiellement d'une messagerie : il est de réduire l'effort pour reconnaître et ouvrir la Conversation utile.

### Contrat de présentation dérivée

La liste et la recherche gardent leurs champs API historiques (`id`, `title`, `purpose`, `context`, `attention_count`, `latest_result`, `updated_at`) et ajoutent une clé **`card`** calculée côté serveur :

- `card.title` : identité courte, privilégiant le sujet contextuel en cas de titre composé comme « Préparation pratique — [sujet] » ; le titre métier original demeure intact dans la Conversation.
- `card.context_label` : contexte secondaire, sans répéter le sujet. `card.context_kind` : famille canonique du contexte pour choisir une icône explicite.
- `card.preview` et `card.preview_kind` : résultat autorisé, à défaut Point visible, à défaut finalité existante. Le client tronque **visuellement** le texte sans réécrire ni posséder les vérités métier.
- `card.media_kinds` : maximum quatre signaux issus de Points visibles (`poll`, `form`, `confirmation`, `exchange`) ou de pièces jointes dont le téléchargement est réellement autorisé (`voice`, `audio`, `image`, `video`, `file`). Aucun nom de fichier, miniature privée, identité de répondant ou faux compte « non lu » dans la liste.
- `card.context_image_url` : seulement la couverture d'un Event propriétaire déjà publié sur une Activity publique et publiée, et uniquement si l'URL de média est relative au même site. Direct, Space, Group et autres contextes utilisent leurs icônes sans exposer d'avatar ou de média dont la politique de visibilité n'est pas démontrée.
- `card.attention_count` : nombre de Points réellement à traiter, pas nombre de messages reçus. Les archives, masquages et recherches restent scindés par viewer.

### Contrat mobile et Web

Chaque ligne a un élément visuel de 56 px environ, titre sur deux lignes maximum, contexte sur une ligne, résultat/aperçu sur une ligne, indices médias à faible poids visuel et badge d'action réel si nécessaire. La ligne entière est accessible et ouvre le même N1 (ou le Point issu d'une recherche). Couleurs, Typographies et espacements réutilisent les tokens Makolo. Flutter conserve la compatibilité avec les anciennes projections local-first dépourvues de `card`. L'aperçu ne devient jamais une timeline.

### Validation

Serveur : `python manage.py test conversations.test_c5_mature conversations.test_m9c_performance` ; inclut contexte très long, signal d'image/vocal filtré par audiences distinctes, couverture Event publiée/non publiée et lecture Web. Flutter : `flutter test test/conversation_list_tile_test.dart test/conversation_mature_repository_test.dart` et `flutter analyze`. Recette visuelle sur Android : 320/360/430 px, texte 1,6, clair/sombre ; puis tablette/large, photo de couverture publique, média privé non révélé, recherche et retour. Le budget de requêtes M9-C et les tests de permissions restent des critères de sortie.

Cette correction C5 est implémentée dans la PR #522 sans nouveau modèle, migration ni API propriétaire parallèle. L'attestation d'une compilation/flutter test et la vérification visuelle sur un Android réel exigent toujours leur exécution effective.

## 18. Détail natif d’une Conversation — J4 / #522 (5 novembre 2026)

La profondeur **Détails de la conversation** utilise le même propriétaire Conversations que la profondeur de lecture. Elle n'est pas un groupe social parallèle.

- **Objet** : `subject` est dérivé du `ConversationContext` réel. Une Activity/Occurrence peut présenter la couverture publiée, publique et déjà autorisée par Discovery. Un interlocuteur direct peut utiliser le portrait du Profil si le Passport est public **et** que sa visibilité l'autorise. Un Espace/Groupe sans média canonique conserve son pictogramme ; aucun avatar n'est inventé.
- **Personnes** : `ConversationParticipation`, `GroupMembership`, audiences et autorités sont différents. La liste dérivée des personnes ayant accès à une Conversation n'est pas un annuaire. Le couple direct est connu dans son consentement. Seul un responsable réellement autorisé voit l'aperçu des membres actifs d'un Groupe et leur total réel ; les autres contextes ne dévoilent pas implicitement un effectif ou des identités.
- **Médias** : la vue liste au maximum 24 pièces déjà autorisées et filtrées par `point_visible_to` + `can_download_attachment`. Aucun média privé n'est préchargé en clair ni servi par `Image.network` ; le lecteur éphémère actuel revalide l'autorité au téléchargement.
- **Ressources** : seules des métadonnées `ActivityResource` publiées et autorisées par `can_view_resource` peuvent être présentées pour Activity/Occurrence/Journey. Leur présence ne transforme pas les Attachments en Resources et ne transfère aucun accès.
- **Actions personnelles** : sourdine, épingle, revoir plus tard, archives, masquage consomment l'API personnelle existante et attendent la confirmation owner. Les règles communes sont présentées en lecture seule tant qu'aucune commande de gestion autorisée n'est implémentée.
- **Partage** : le partage natif propose uniquement la route Web authentifiée existante `/conversations/<id>/`. Le lien est une adresse, pas un jeton d'Access, pas une invitation et pas un transfert de Permission. Tout destinataire reste soumis à `can_view_conversation`.
- **Local-first** : les nouveaux champs sont dans la projection `conversation.detail` du Profil courant ; le dernier détail encore valide reste lisible hors ligne, mais un refus serveur explicite prime sur la copie locale.
- **Vérification** : tests ciblés de confidentialité et de navigation ajoutés à #522. Exécution Flutter/Android et CI non attestées par ce checkpoint.


## Addendum du 12 novembre 2026 — commodités des Discussions Exchange

La demande de modernisation du 12 novembre autorise les citations, modifications,
réactions, mentions, reçus et signaux contextuels de saisie/présence à l’intérieur
des Points Exchange. Elle fait évoluer les restrictions historiques de l’UX
Conversations sur ces commodités ; elle ne supprime aucune frontière du domaine.

PostgreSQL et les services Conversations restent autoritatifs. REST porte les
mutations et la synchronisation ; WebSocket accélère les invalidations. Les
signaux de présence et de saisie sont éphémères, bornés, filtrés et ne constituent
jamais un statut global ou une preuve de lecture. Les compteurs d’attention
continuent à représenter les Points qui demandent une action.

Une citation, mention ou référence documentaire n’accorde aucun accès ni autorité.
Les documents JourneyArtifact et Requirement restent servis sous les contrôles de
leurs propriétaires, sans copie silencieuse ni satisfaction automatique.

Les changements locaux, limites encore ouvertes et gates non exécutées sont
consignés dans [le relevé d’implémentation](../implementation/conversations-realtime-2026-11-12.md).
