# Conversations — Lot 4 : chronologie et compression du passé

**Date :** 9 novembre 2026  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Branche :** `fix/discover-a-continuation-context-20261014`  
**PR :** #522 — aucune fusion de `main`

## Décision produit

Conversations garde un **fil chronologique fidèle** : publication la plus
ancienne en haut, plus récente en bas. Le regroupement n'est pas une nouvelle
chronologie ni un tri par type de Point, importance ou priorité.

Le présent ne doit pas être noyé sous les Points achevés : les Points terminés
**consécutifs et d'une même journée** sont repliés *à leur place*. Le résumé
du groupe et son nombre sont visibles ; un clic déplie les vrais Points avec
texte, médias, réponses, décisions et heures. Les actions toujours dues et
les Points épinglés ou marqués « à revoir » restent visibles.

Ce comportement ne transforme ni les Points en messages génériques, ni
les données de résolution en état de domaine propriétaire.

## Source de vérité serveur

Nouveau `conversations/timeline.py` :

- `recent_timeline_for_profile(profile, conversation)` réutilise strictement
  `page_points_for_profile(section="all", limit=40)`. Ce mécanisme C5
  impose les audiences, la confidentialité historique `FROM_JOIN`,
  le tri `published_at DESC, pk DESC` et un curseur signé borné au viewer,
  à la Conversation, au filtre, à la limite et au snapshot.
- Pour l'écran principal seulement, **inversion d'affichage** de la page
  validée par le serveur : ancien → récent. La base ne change pas d'ordre.
- `timeline_presentation` calcule la possibilité de replier un Point
  selon l'état canonique et les interactions autorisées pour ce Profile.
  Terminés : `resolved`, `expired`, `cancelled`, `superseded` ;
  `response_closed` si aucune décision autorisée en attente ; questions,
  confirmations, demandes et sondages déjà répondus ; formulaires
  terminés pour le destinataire ; prise de connaissance enregistrée.
- Si un Point exige encore une confirmation, une décision de résolution,
  une clôture accessible, ou a été marqué « à revoir », il ne se replie
  pas. Les épingles partagées conservent leur visibilité avant résolution.
- Résumés de résolution accessibles **uniquement** sous
  `point_resolution_visible_to`; autrement un libellé neutre remplace
  toute décision privée.
- `group_timeline_points` regroupe uniquement les **segments adjacents**
  repliables, dans la même journée. Il ne déplace aucun Point actif.
  Le résumé du dernier résultat clôt le groupe.
- Pas de nouvelle table, migration, statut métier ou copie de réponse.

La projection `ConversationDetailAPIView` expose
`timeline[]` (40 Points accessibles ordonnés) et
`timeline_next_cursor` (page antérieure). Chaque Point possède
`timeline_compact` et `timeline_summary`, produits par le serveur.
Les anciens champs `points`, `essential`, `elsewhere` restent dans
la projection pendant la compatibilité des clients déjà installés.

## Web

`templates/conversations/detail.html` :

- remplace « À vous », « L'essentiel », « En cours ailleurs », « À savoir »
  comme **mode d'ordonnancement du fil** par une seule chronologie ;
- garde le résumé « Depuis votre dernière visite », la recherche, les
  actions et le compositeur hors fil ;
- insère les sauts de jour chronologiques ;
- utilise `_timeline_group.html` pour la compression native
  `<details><summary>`, accessible au clavier ;
- offre « Voir les Points précédents » au-dessus de la chronologie,
  réutilisant le curseur signé de l'historique.

`history.html` conserve ses filtres et la recherche C5 ; chaque page
est affichée dans le sens ancien → récent, avec regroupements locaux.
Le clic vers un Point ciblé l'ouvre directement ; si ce Point est dans
un groupe du fil, le groupe se déplie par `focus`. Si le Point ciblé
n'appartient pas à la fenêtre récente, il apparaît dans une zone
« Point recherché » distincte, sans prétendre qu'il est adjacent aux
dernières publications.

`_point.html` place l'heure réelle et l'icône de publication confirmée
au **coin inférieur droit**. Aucune coche de livraison/lecture n'est
inventée.

## Flutter

`ConversationDetailScreen` utilise le champ `timeline[]` canonique,
au lieu de recomposer le fil depuis les sections d'attention/importance.
Les anciennes projections locales restent consultables selon la logique
historique jusqu'au prochain rafraîchissement autorisé.

L'écran :

- affiche séparateurs de jour, anciens en haut, récents en bas ;
- présente un résumé repliable pour chaque suite de Points terminés
  du même jour, avec accès intégral à chaque Point déplié ;
- conserve les médias et les interactions des Lots 1–3 ;
- **entrelace les publications en Outbox** et les Points autorisés selon
  leurs dates réelles d'observation/publication, même si une publication
  locale non confirmée est plus ancienne qu'un Point reçu ensuite ;
  les Points en attente coupent naturellement les groupes terminés,
  et ne sont pas annoncés comme publiés sans confirmation du serveur ;
- suit les derniers messages si l'utilisateur est déjà en bas, sinon
  propose un saut explicite plutôt que de lui déplacer le défilement ;
- peut charger les pages plus anciennes par le même cursor C5
  (`pointDepth(section="all", limit=40)`). Les nouvelles entrées sont
  **ajoutées au-dessus** et l'offset visuel est compensé ;
- invalide les pages anciennes temporaires quand le snapshot de
  projection change, évitant de prolonger un droit d'accès révoqué ;
- ouvre un groupe replié si un lien profond pointe vers son contenu.
  Un Point ciblé hors fenêtre apparaît dans un panneau distinct,
  sans fausse continuité chronologique.

`ConversationHistoryScreen` adopte à son tour l'ordre ancien → récent,
même quand plusieurs pages du curseur sont chargées. Il présente
les groupes terminés repliables, et chaque résultat ouvre le Point
canonique dans la Conversation. La recherche et les filtres restent
C5, pas un index local de contenus inaccessibles.

`ConversationPointShell` utilise désormais le **coin inférieur droit**
pour l'heure et le statut d'envoi confirmé, y compris pour les
publications en attente de l'Outbox avec leurs icônes spécifiques.
Ce n'est pas un accusé de réception du lecteur.

## Sécurité et limites

- Le serveur recalcule les droits à chaque acquisition de page ;
  aucun compte d'éléments invisibles n'est transmis dans un groupe.
- Un groupe est calculé seulement à partir des Points *déjà autorisés*.
  L'extension en profondeur utilise le même service C5 signé.
- La compression ne ferme ni ne résout les Points. La résolution
  Conversations ne modifie pas Activity, Journey, Payment, Access,
  Capacity, Questionnaire ou une autre vérité propriétaire.
- Les réponses et médias des Points demeurent attachés aux propriétaires
  canoniques et au service de téléchargement privé.
- Une page Web d'historique n'affiche qu'une fenêtre C5 à la fois ;
  Flutter peut préfixer plusieurs pages dans la même vue.
- Une projection mobile hors ligne datant d'avant ce lot n'invente pas
  des groupes terminés : elle reste lisible avec son ancienne sélection.

## État de livraison

Code poussé dans la branche active de la PR #522, sans fusion ni
modification directe de `main`.

Conformément à la consigne du chantier, **pas de CI, pas de tests
automatisés ni de validation d'exécution Web/Flutter** dans cette session.
La revue réalisée est statique. Les parcours doivent être éprouvés avant
déploiement de test avec participants, organisateurs et staff, en particulier
`FROM_JOIN`, permissions d'audience, liens profonds vers des Points repliés,
chargement multi-pages, déconnexion et révocation d'accès.
