# Makolo Conversations — Lot 7 : consolidation et validation des Lots 1–6

**Date :** 10 novembre 2026  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Branche de travail :** `fix/discover-a-continuation-context-20261014`  
**PR :** [#522](https://github.com/TraditionLearningCommunity/makolo/pull/522), ouverte et non fusionnée.

## 1. Objet et sources de vérité

Finaliser le travail déjà présent sur #522 sans le redémarrer. Le principe
reste **« Event est une verticale. Activity est le noyau. »**

Vérifications croisées avec :

1. code, migrations, tests et API courants de la branche ;
2. `docs/architecture/makolo-domain-blueprint.md` ;
3. `docs/architecture/ux-now.md` et
   `docs/architecture/notifications.md` ;
4. le contrat consolidé Makolo UX Conversations du 9 octobre 2026 ;
5. les documentations de mise en œuvre des Lots 1–6.

La PR #522 est une branche de consolidation qui contient également
d'autres chantiers Makolo. **Aucun de ces autres chantiers ne doit être
modifié ou fusionné implicitement par la validation Conversations.**

## 2. État réel au terme de cette intervention

| Lot | Livrables vérifiés dans le code | Risque restant |
|---|---|---|
| 1 — Médias | Lecteurs et mosaïques Web/Flutter, PDF, audio, vidéo, téléchargement/partage privé | Décodage appareils, lecteur natif, navigation rapide : smoke à exécuter |
| 2 — Médias structurels | Media au niveau Point, option, réponse et pont vers Questionnaire canonique | Versions publiées, ACL et stockage réel à valider |
| 3 — Points interactifs | Sondages, confirmations, réponses, Forms, décisions et APIs owner | Concurrence et conflits en environnement réel |
| 4 — Chronologie | Pagination signée, fil ancien→récent, regroupement **in situ** des Points terminés | Longue chronologie et restoration scroll/cold-start |
| 5 — Participation | username/slug, invitations individuelles, consentement collectif, accès dérivé live et FROM_JOIN | Autorisations Group/Space et migration 0008 en base réelle |
| 6 — Attention/Notifications | Actions dues, résumé « Pour moi / À régler / À savoir », Autopilot et liens directs aux Points | Cadence scheduler, fuseaux, push fournisseur et révocations en vol |

**Aucun lot ne crée un double modèle Event de participants, de média
Questionnaire, de membership Space/Group ou de notification.**

### Défauts concrets corrigés pendant le Lot 7

- `point_services.acknowledge_point` avait perdu son décorateur transactionnel
  lors de l'insertion de l'état personnel du Point : `@transaction.atomic`
  a été rétabli, sans transaction imbriquée inutile sur la nouvelle fonction.
- `point_interactions` relisait les réponses et états d'un Profil
  individuellement, malgré les préchargements existants M9-C :
  réutilisation des attributs déjà préchargés, sans cache inter-requêtes.
- Les nouvelles synthèses d'attention analysent les Points ouverts anciens,
  sans limite globale trompeuse ni matérialisation illimitée du fil.
- Un Point futur ne devient « À venir » que si son destinataire dispose
  réellement d'une action future (réponse, lecture ou formulaire encore dû).
  Une Information programmée n'est pas présentée prématurément comme
  une information déjà disponible.
- Le lecteur privé Flutter libère les fichiers téléchargés devenus
  obsolètes lorsque l'utilisateur change rapidement de média ou ferme
  la vue pendant l'initialisation audio/vidéo.
- Les assertions pré-Lot-4/6 de `test_j7_contracts.py` ont été remplacées
  par des exigences **plus fortes et actuelles** : ordre chronologique réel,
  absence d'action exigible avant ouverture, notification interne préservée
  sous sourdine mais livraison externe supprimée.

Aucun test n'a été supprimé ou affaibli pour obtenir artificiellement du vert.

## 3. Jeux de non-régression ajoutés

- `conversations/test_lot7_closure.py` :
  attention autorisée, disparition après réponse, refus 404 pour outsider,
  faux `upcoming`, fenêtres d'acknowledgement, revisite personnelle
  et révocation, rappel J-1 idempotent, revalidation push après réponse,
  sourdine sans perte d'information, ouverture programmée idempotente,
  refus de nom ambigu, consentement et adhésion dynamique des Groupes,
  FROM_JOIN et révocation.
- `questionnaires/test_lot7_media.py` :
  médias de version racine, question et assertion de choix ;
  intégrité du lien aux choix, publication immuable,
  visibilité réservée à la cible du FormRequest ou au gestionnaire.
- `mobile/test/notification_router_test.dart` :
  focus Point explicitement identifié, refus des paramètres forgés.
- `mobile/test/conversation_lot7_media_cleanup_test.dart` :
  fichiers privés abandonnés et fermeture du lecteur.
- `conversations/test_j7_contracts.py` et
  `conversations/point_interactions.py` :
  alignement avec le comportement actuel sans affaiblir le principe
  « non lu ≠ attention ».

Les tests existants couvrant Questions, Questionnaire, médias, Policy,
historique, performance M9-C et Notifications restent dans la sélection.

## 4. Gate reproductible

Lancer depuis une copie de la branche avec **base de test jetable** et
dépendances Python, Node, Dart et Flutter installées :

```sh
sh scripts/verify_conversations_lot7.sh
```

Pour exécuter la partie serveur/Web sur un environnement sans Flutter :

```sh
VERIFY_MOBILE=0 sh scripts/verify_conversations_lot7.sh
```

Le script **ne déploie rien**, n'applique aucune migration et ne modifie
aucune donnée existante. Il exécute :

1. vérification Django et `makemigrations --check --dry-run` ;
2. `migrate --plan` pour confirmer le plan de migration ;
3. suites ciblées Conversations, Questionnaires, Notifications ;
4. analyse syntaxique des JavaScript propriétaires ;
5. formatage/analyse et widgets Flutter si disponibles.

En environnement réel avant toute migration, vérifier la sauvegarde,
le plan d'application **additif** de
`conversations/0007_semantic_point_media`,
`conversations/0008_collective_access` et
`questionnaires/0003_questionnaire_media`, puis valider les anciennes
données et le rollback. Ne pas appliquer de migration destructive.

## 5. Matrice de fumée Web / Android

Ces scénarios sont les **critères de réception**, non des tests revendiqués
comme exécutés pendant cette intervention.

| ID | Profil / scénario | Attendu |
|---|---|---|
| L7-01 | Visiteur non authentifié | Aucune pièce jointe privée, liste ou réponse divulguée |
| L7-02 | Participant sur Question ouverte | Réponse confirmée par owner ; disparition d'Attention |
| L7-03 | Participant ciblé avant opens_at | Aucun CTA prématuré ni badge exigible |
| L7-04 | Point expiré, résolu ou remplacé | Résultat/statut réel, aucune mutation caduque |
| L7-05 | Organisateur sur Point à résoudre | Autorisation serveur et résolution uniquement du Point |
| L7-06 | Fil long > 40 Points | Plus anciens accessibles ; aucun tri attentionnel dans la chronologie |
| L7-07 | Points terminés adjacents | Compression sur place ; focus/dépliage correct |
| L7-08 | Image+vidéo+audio+PDF+DOC | Vignette, lecteur privé, navigation, échec/reprise, export explicite |
| L7-09 | Média option/Questionnaire | Emplacement exact et ACL/version publiée intacts |
| L7-10 | Identifiants homonymes | Destination résolue par username/slug exact, sans Contact obligatoire |
| L7-11 | Invitation collective refusée | Aucun membre ajouté ; droits inchangés |
| L7-12 | Groupe accepté et adhésion modifiée | Visiteurs recalculés, pas de copie de membership |
| L7-13 | FROM_JOIN et révocation | Aucun Point antérieur/privé retrouvé par API, galerie ou cache mobile |
| L7-14 | Sourdine et préférences | Notification interne distincte des interruptions, sécurité propriétaire préservée |
| L7-15 | Autopilot exécuté deux fois | Même événement/échéance : aucune notification dupliquée |
| L7-16 | Réponse avant dispatch | Push en attente écarté ; la vérité de la réponse gagne |
| L7-17 | Notification vers Point ancien | Web/Flutter ouvrent le Point accessible, y compris groupe compressé |
| L7-18 | Android hors ligne puis retour réseau | Lecture snapshot autorisé, action sensible non confirmée sans serveur |
| L7-19 | Participant, organisateur et staff Makolo | Permissions différenciées, aucun accès obtenu d'un libellé UI |
| L7-20 | Navigation et accessibilité | Focus clavier, lecteur d'écran, retour/scroll, affichage compact |
| L7-21 | Déploiement bêta de test | Absence d'erreurs 500 et contrôle des routes privées par acteur |

PythonAnywhere, s'il est utilisé pour L7-21, reste **uniquement** un
environnement temporaire de test, pas la future production.

## 6. Critères de sortie de #522

Une consolidation de code n'est pas une attestation d'exécution.

**État démontré dans cette intervention :**
code, tests et documentation poussés dans #522, fichiers/raccordements
relus statiquement, pas de modification de `main`, pas de merge.

**Non démontré :** compilation Dart/Flutter, exécution des tests Django
sur PostgreSQL, validation des migrations avec données réelles,
E2E Web/Android, build Android, golden visuels, push fournisseur, smoke
sur déploiement et CI verte.

Les workflows du HEAD consulté portaient le statut GitHub
`action_required` (approbation/intervention nécessaire) : ce n'est
**ni vert ni une exécution réussie**. Ce blocage est à lever par une personne
habilitée via GitHub. Il ne faut pas contourner ni retirer les gates.

**Ne fusionner #522 que si :** les tests ciblés et pertinents passent,
les migrations non destructrices sont validées, les parcours de sécurité/
accessibilité sont vérifiés, aucune CI requise n'est rouge ou en attente,
et le HEAD examiné n'a pas changé depuis la validation.

Un nouveau commit après validation invalide l'attestation du HEAD précédent.
La PR pouvant recevoir des modifications d'autres chantiers, refaire les
gates globales avant intégration. Préférer le squash merge si l'équipe le
décide ; vérifier ensuite que `main` est verte.
