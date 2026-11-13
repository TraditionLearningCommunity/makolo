# Conversations — finition UX et continuité locale (13 novembre 2026)

## Périmètre

Branche de la PR #522 : `fix/discover-a-continuation-context-20261014`.
Finition ciblée du fil, des Points, des choix structurés, du contexte d'attention,
des réponses hors connexion, de la liste, des médias et de la déclinaison Web.
Aucun nouveau domaine, modèle, table ou autorité. Les services Conversations
existants conservent les décisions d'acceptation, de publication, de réponse,
de résolution, de téléchargement et d'accès.

## Implémenté dans ce passage

- Les actions secondaires d'un Point Flutter (signet et gestion) sont dans
  l'en-tête. `Gérer ce Point` n'ajoute plus une rangée et un mini-tutoriel à
  chaque carte. Les choix de gestion sont toujours limités aux projections
  `can_close_responses` et `can_resolve` fournies par le serveur ;
  la commande propriétaire revalide les droits.
- Les sondages Flutter proposent des lignes complètes touchables avec repère
  de sélection. Les médias d'un choix restent dans sa zone, avec leur geste
  distinct. Les compteurs nuls n'encombrent plus les options.
- Les confirmations proposent des choix courts `Oui` / `Non` ;
  les demandes conservent `Je m'en charge` / `Je ne peux pas`.
- Le composant de Point affiche `Discussion` plutôt que le terme
  technique `Échange`, sans changer le type métier ni la permission.
- `À présent` ne réaffiche pas plusieurs fois un même ID de Point issu
  d'une projection ancienne ; deux Points distincts portant un même libellé
  sont conservés et peuvent être distingués par leur publication réelle.
- Les Conversations homonymes utilisent leur objet réel si celui-ci est
  disponible et distinct du titre/de l'aperçu. Aucun doublon n'est supprimé
  par comparaison des titres.
- Le lecteur de média utilise une icône d'ouverture accessible à la place
  d'un bouton explicatif répété.
- Web : signet et menu de gestion dans l'en-tête, formulaires de gestion
  conservés sans exposer leurs commandes par défaut, choix du sondage
  accessibles sur toute la ligne, résultats et compteurs plus sobres.
- Les vocaux, images et documents envoyés **en réponse à un Point** sont
  copiés dans le stockage privé du Profil avant l'envoi. Le mode
  `media_response` partage l'outbox canonique, mais passe par son endpoint
  propriétaire distinct et ne se confirme qu'après un accusé de réception
  complet. La feuille média se ferme après conservation durable, sans
  présenter l'upload comme déjà accepté.
- Les réponses structurées aux Points peuvent être **conservées dans l'outbox
  existante du Profil** avant toute tentative réseau. La valeur exacte,
  l'identifiant du Point, l'espace représenté et la référence d'idempotence
  sont enregistrés dans l'opération `conversation.point.compose` avec
  `mode=response`. Le dispatch utilise exclusivement l'API propriétaire
  `points/<point_id>/respond/`. Le client exige une réponse contenant
  l'identifiant du Point et de la réponse ; la réconciliation relit le
  détail sans rétrograder une confirmation en erreur réseau.
- L'état d'une réponse en attente apparaît **dans son Point**, pas comme
  un nouveau message. Une réponse mise en attente n'est pas annoncée comme
  confirmée, et un double toucher pendant l'enregistrement local est bloqué.
  Lorsque la livraison persistante n'est pas configurée, l'ancien transport
  direct et sa reprise explicite restent disponibles.
- Tests de régression ajoutés pour la réponse booléenne `false` conservée
  hors connexion et sa seule livraison autorisée, ainsi que pour les choix
  tactiles et le menu des Points.

## Règles préservées

- `Point`, `Conversation`, `Response` et les autorisations restent
  propriétaires côté Django. La sélection locale et l'outbox sont des
  intentions, jamais des réponses confirmées.
- Ne jamais fusionner deux Points différents parce que leurs textes sont
  identiques.
- Les réponses média aux Points sont éligibles à une reprise idempotente
  parce que `submit_point_media_response` vérifie le Point, le Profil, le
  contexte représenté, la référence et l'empreinte du fichier. L'outbox
  `mode=media_response` envoie ce fichier privé au seul endpoint propriétaire
  `points/<point_id>/reply-media/` et exige `response_id`, `point_id`
  et `attachment` avant de considérer une confirmation. Ne pas transformer
  un timeout ou un accusé de réception incomplet en succès.
- Aucune synchronisation n'efface un brouillon ou un média privé de façon
  spéculative.

## Validation à réaliser (non attestée ici)

L'agent ne dispose ni du SDK Flutter/Dart du dépôt ni du téléphone/émulateur
de l'utilisateur. Le formatage Dart officiel et les tests ne sont donc pas
déclarés exécutés par cette intervention. Selon `AGENTS.md`, la branche
doit passer par `mobile/tool/dart_format.sh` ou par le workflow manuel
`Mobile Format` de la branche avant livraison.

Cibles ciblées :
- `flutter test test/conversation_local_delivery_test.dart`
- `flutter test test/conversation_point_ux_test.dart` (gestes, menu, densité)
- `flutter test test/conversation_c5_mature_test.dart test/conversation_list_tile_test.dart`
- `flutter analyze`
- Tests Django Conversations adaptés aux Points et à l'idempotence
- Recette Samsung et émulateur, clair/sombre et grandes polices, raccordement
  ADB reverse, lecture déconnectée, réponse en file, reconnexion, refus métier,
  double toucher, historique et médias.

La recette visuelle sur dispositif réel et les tests de sécurité/permission
restent des critères de sortie ; leur absence n'est pas une validation implicite.

## Risques / reliquats à ne pas masquer

- Le rejeu des réponses vocales/fichiers repose explicitement sur
  l'idempotence et la vérification d'empreinte déjà présentes dans le service
  propriétaire. La recette doit couvrir un upload interrompu, puis la
  reprise avec exactement le même fichier conservé, sans duplicat.
- Les résultats de sondage, audiences et capacités dépendent du serveur.
  Les composants Flutter ne déduisent ni éligibilité ni résultat propriétaire.
- Les états `conflict` et `awaiting_confirmation` de l'outbox doivent être
  vérifiés sur la recette réseau réelle, y compris la reprise en avant-plan.
- Les changements de structure de cartes demandent une inspection réelle des
  largeurs 320/360/430, du texte agrandi et du clavier, après formatage.

**Critère UX** : comprendre le Point, choisir ou répondre, puis continuer ;
ni boîte de dialogue explicative, ni succès fictif, ni outil de gestion
constamment visible dans le fil.
