# Conversations — Lot 2 : présentation et composition sémantiques des Points

Date : 9 novembre 2026  
Dépôt : `TraditionLearningCommunity/makolo`  
Branche : `fix/discover-a-continuation-context-20261014` (PR #522)

## Contrat UX appliqué

Un Point est compris et utilisé à travers **sa structure et ses actions**, non
par une simple étiquette « Question », « Sondage » ou « Demande ». Les médias
ne sont pas une liste technique ajoutée après les réponses ou assertions.

Ordre de présentation :

1. Type / auteur / sujet du Point, puis texte principal et précisions.
2. Médias propres au Point, avec la légende de **chaque fichier** et lecteur
   adapté (réutilisation du Lot 1).
3. Pour un Sondage : chaque choix canonique dans l'ordre défini, son texte,
   puis **ses propres médias et légendes**, avant de passer au choix suivant.
4. Interactions autorisées (vote simple ou multiple, confirmation, réponse
   texte/fichier/vocal, prise en charge, ouverture d'un Form Request).
5. Contributions Exchange : texte de chaque entrée, ses propres médias,
   puis l'entrée suivante.
6. Réponses dont les pièces sont accessibles : contenu de réponse autorisé,
   puis pièces rattachées à cette réponse. Ne pas dériver d'identité privée.

Chaque ensemble de plusieurs médias s'ouvre également dans la visionneuse
commune, avec navigation, téléchargement et partage sous ACL.

## Source de vérité et migration

- `ConversationPoint` demeure le propriétaire de la publication.
- `ConversationPointOption` conserve les assertions du Sondage.
- `ConversationPointAttachment` reste un média privé lié au Point : deux
  champs additifs, `option` (FK nullable, PROTECT) et `caption`.
- Une pièce est rattachée à **un seul contexte** parmi : Point racine,
  Option, Response ou PointExchangeEntry.
- Contrainte SQL `conv_attachment_single_context`, validation de propriété
  de l'Option et des droits de l'auteur.
- Migration additive : `conversations/migrations/0007_semantic_point_media.py`.
  Aucune ancienne pièce ne perd son lien : `option=NULL`, `caption=""`
  préservent l'interprétation de données historiques.
- Un média de choix n'est jamais un nouveau modèle Poll ni une Resource.
  Le modèle canonique Questionnaire conserve son autorité sur les questions
  des formulaires.

## Écriture serveur

- Nouveau service `publish_semantic_point_with_media` : contrôle policy,
  format/signature réelle, 1–24 médias, volume total plafonné à 64 Mio,
  légendes bornées, choix appartenant au Point.
- Même transaction PostgreSQL/Django pour publier le Point, ses choix
  et leurs fichiers. En cas d'échec DB, tentative de nettoyage des fichiers
  créés durant cette opération (le stockage objet n'est pas transactionnel).
- `POST /api/v1/conversations/<uuid>/semantic-media/` : multipart avec
  `media_manifest` et fichiers nommés `media_0`, `media_1` etc.,
  `scope=point|option`, `option_index` uniquement pour un Poll.
- Le `client_reference` existant protège le rejeu : le même envoi retourne
  ses médias s'ils sont identiques ; un changement de contenu, d'Option,
  de légende ou d'ordre est refusé.
- Validation ACL serveur avant publication et avant chaque téléchargement.
  Aucun nouveau endpoint de lecture public.
- Aucune possibilité de greffer un fichier de choix sur un autre Point
  ou sur un Poll ayant déjà des réponses.

## Projection autorisée

`_serialize_point` fournit :

- `attachments` : seulement les pièces du Point racine.
- `options[].attachments` : seulement les pièces de cette Option.
- `exchange_preview[].attachments` : pièces de cette entrée d'Échange.
- `response_media[]` : réponses dotées de médias réellement lisibles
  pour le viewer, avec éventuel texte de réponse autorisé.

Le Web construit les mêmes sections via
`conversation_point_media_sections` et `can_download_attachment`.
Aucune projection n'autorise l'accès sur la seule base d'un ID média.

## Flutter

- `_PointCard` : Point, médias racine, assertions avec médias et choix,
  contributions d'Échange avec médias, puis actions et réponses.
- `ConversationMediaGroup` et `ConversationAttachmentViewer` du Lot 1
  réutilisés : photos/vidéos en galerie, lecteur audio/PDF/doc et captions.
- `ConversationExchangeSheet` : chaque entrée conserve texte, média,
  légende et détails ; plus de liens de fichiers isolés.
- Éditeur de Points : plusieurs pièces au niveau du Point, ou plusieurs
  pièces par Option d'un Poll, chacune avec sa propre légende. L'index
  des choix est réconcilié après suppression.
- `ConversationLocalDelivery` / Outbox existants : copies de préparation
  dans la portée privée du Profil, rejeu stable vers la même mutation
  multipart, aperçu local des médias sous leurs sections. Un échec réseau
  ne devient pas un succès optimiste ; le statut d'envoi demeure explicite.
- Si le transport de l'Outbox n'est pas disponible, le dépôt garde un
  chemin direct owner-confirmed via `ConversationRepository`.

## Web

- `_point.html` et `_attachment_gallery.html` : sections sémantiques,
  légendes et fenêtres de lecture au bon emplacement.
- `_composer.html` + `_semantic_media_controls.html` : champ média
  principal et panneaux de choix enrichis avec légendes.
- `conversations-semantic-composer.js` : soumission multipart de tout
  le Point dans une opération atomique ; publie par l'ancien formulaire
  si aucun fichier n'est sélectionné.
- Un changement de libellé de choix ne conserve pas silencieusement ses
  anciens fichiers : il faut les vérifier/rattacher.
- Vérification côté client des types média annoncés par la policy ;
  le serveur reste seul garant des autorisations.

## Frontières et limites non maquillées

- Les modèles `FormQuestion` du domaine canonique Questionnaires portent
  `label` et `help_text`, mais n'exposent **pas** de relation de média
  propre à chaque question. Le Point Form Request et sa pièce liée sont
  présentés dans Conversations, puis ouvrent le Questionnaire propriétaire.
  Nous n'avons ni copié les questions dans Conversations ni inventé des
  médias de champs. L'enrichissement individuel des questions requiert
  une décision d'extension du propriétaire Questionnaires.
- DOC/DOCX sans lecteur natif : ouverture compatible depuis le Lot 1,
  pas de conversion silencieuse.
- Les médias privés gardent les mêmes restrictions d'accès, de révocation
  et de conservation sélective que leurs propriétaires.
- L'ordre chronologique global du fil et le regroupement des Points clos
  appartiennent au Lot 4, pas au Lot 2.
- Les capacités complètes de vote, réponse et résolution métier dépassant
  la mise en page sémantique relèvent du Lot 3 ; les droits existants
  sont conservés.

## État de vérification

Code poussé sur la branche de #522. **Pas de merge**.

À la demande du chantier, aucune suite de tests, CI ni validation manuelle
Android/Web n'a été exécutée ici. La présence du code et de la migration ne
constitue pas une certification de comportement ni un déploiement. Prévoir
l'application de la migration avant de tester les nouveaux envois ; conserver
une sauvegarde et un chemin de retour opérationnel.
