# Makolo — Moi / Nous / Conversations : réalisation UX sociale et contextuelle

**Branche de travail :** PR #522 (aucun merge de main).  
**Recette :** Conversations n'est pas une messagerie parallèle, les interlocuteurs sont toujours des Profiles humains. Les Espaces fournissent un contexte d'activité et d'autorité.

## Comportements implémentés

### Header de Moi et Nous
- La même icône `Conversations` que dans le header Now, avec indicateur d'attention uniquement quand le moteur canonical le rapporte.
- L'avatar du contexte actif reste distinct de l'icône Conversations.
- La barre `Échanger` qui occupait le sommet du contenu Nous a été retirée. Aucun raccourci `Nos conversations` n'est créé dans les territoires.
- Le header Nous passe `context=space&space=<space_id>` à la route existante de Conversations ; Moi ouvre la même route sans paramètre Space. L'acteur réel est vérifié dans le routeur, et un contexte obsolète ou forgé n'affiche jamais la boîte personnelle de secours.

### Une capacité Conversations canonique, plusieurs lectures
- `ConversationListScreen` est réutilisé dans les deux acteurs, sans doublon de modèle ou d'API.
- En contexte personnel : la collection Conversations locale et les vues `Toutes/À traiter/Archives` existantes sont préservées.
- En contexte Space : le même écran affiche les résultats **explicitement attachés à cet Espace** renvoyés par `Conversations.by-context/space/<id>`, uniquement après contrôle du serveur. Aucune liste personnelle en cache ne sert de substitut en cas de refus ou de transport hors ligne. Les Conversations attachées à une Activity / un Project / un Dossier possèdent leur propre contexte primaire et ne sont pas abusivement classées comme Conversations Space.
- Lorsque le serveur déclare `can_ensure`, l'action d'ouverture d'une Conversation contextuelle reste disponible **dans la liste**, jamais en barre permanente sur Nous.
- Détails, Points, audiences, réponses, actions et permissions restent la propriété des services Conversations existants.

### Les échanges restent entre personnes
- Le sérialiseur d'un Point nomme désormais son `published_by` comme auteur humain (selon la politique d'identité déjà utilisée), et fournit séparément `author.space_label` quand la personne intervient dans le cadre d'un Espace.
- Flutter affiche le Profile humain et une mention secondaire du contexte Espace. Le Space ne remplace plus le nom de l'auteur.
- Aucune autorité n'est inférée d'une participation. Les mandats cumulés restent validés par les services d'autorisation serveur.
- **Limite explicite** : le modèle `ConversationPoint` conserve `published_by` et `represented_space`, mais ne stocke pas une photographie historique du mandat choisi lors de la publication. Aucune étiquette de rôle rétrospectif n'est inventée à partir des mandats présents au moment de la lecture. Ceci relève d'un contrat d'attribution historique à traiter séparément si désiré, et non d'une migration improvisée dans #522.

### Présentation des personnes — Moi et Nous
- Nouvelle primitive pure `MakoloPeopleAvatarStack` qui empile les initiales des personnes **déjà visibles dans une projection autorisée**, jamais des portraits fictifs.
- Nous l'utilise pour `Notre équipe` et `Notre gouvernance`, en Liste et Grille ; un éventuel `+N` utilise exclusivement un total explicite autorisé.
- Moi l'utilise pour les Profiles réellement présents dans `Mes suivis`, et garde les icônes des collectifs quand aucune liste de personnes n'est fournie. On ne déduit jamais les membres d'un collectif de son seul nom.

## Critères de recette

1. Header Moi, Nous, Now : une seule icône Conversations à 48 dp, indicateur d'attention identique et avatar contextuel toujours disponible.
2. Nous N1 : aucune bande `Échanger` au-dessus de l'identité ; Équipe et Gouvernance montrent des piles d'avatars uniquement quand leurs données sont visibles.
3. Entrée Conversations depuis Moi : liste personnelle classique ; entrée depuis Nous : liste strictement de l'Espace actif, sans retomber sur le cache personnel en cas de refus.
4. Changement d'Espace : les appels à une ancienne route `?context=space&space=<ancien>` sont rejetés.
5. Dans un Point publié au nom d'un Espace : on reconnaît d'abord le Profile émetteur, puis le cadre collectif en sous-libellé.
6. Aucun changement dans Projects, Dossiers, Journey, Event, migrations ou schéma de permissions.

## Tests ajoutés ou étendus

- `mobile/test/shell_header_test.dart`
- `mobile/test/identity_surface_test.dart`
- `mobile/test/space_us_surface_test.dart`
- `mobile/test/conversation_c5_mature_test.dart`
- `mobile/test/conversation_person_context_test.dart`
- `conversations/test_j7_contracts.py`

L'analyse Dart, les suites de tests Flutter/Django, les smoke tests Android et la CI de #522 restent à exécuter dans un runner complet. Ne pas présenter cette livraison comme une validation runtime.
