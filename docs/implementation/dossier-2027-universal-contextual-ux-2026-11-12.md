# Dossier — UX mobile universelle et contextuelle (direction 2027)

Date : 12 novembre 2026. Dépôt actif : TraditionLearningCommunity/makolo.
Chantier : PR #522, branche fix/discover-a-continuation-context-20261014.
Décision : une seule identité Dossier et un seul écran natif DossierWorkspaceScreen.
Ce document décrit le contrat de composition et la première implémentation,
pas une nouvelle source de vérité ou une recette mobile certifiée.

## Intention

Le Dossier est une surface d'accomplissement, pas un ERP, un fil social
ou un gestionnaire générique de tâches. La page est un résumé lisible
et direct vers les données propriétaires. Navigation calme, progressive,
adulte, accessible. Une seule action utile mise en valeur quand
Readiness fournit une action réelle. Ne jamais générer une action,
un participant, un fichier, un pourcentage métier ou une information
d'autorité pour remplir l'écran.

## Composition universelle

Ordre recommandé au-dessus du pli, si les données existent :

1. AppBar : retour, Dossier, rafraîchissement discret et actions existantes ;
2. Projet parent visible : breadcrumb / destination, facultatif ;
3. Identité : icône Dossier, objectif, description facultative ;
4. Porteur réel : Profil ou Espace ; différent du Profil lecteur ;
5. État canonique, échéance facultative, Readiness distincte,
   indicateur de données partielles ;
6. Échanges contextuels : entrée existante, sans simuler le nombre de messages ;
7. Prochaine intervention : carte unique si Readiness fournit next_action ;
8. Actions propriétaires existantes, restreintes par capabilities ;
9. Personnes et responsabilités : aperçu compact si personnes visibles
   ou utilisateur autorisé à gérer responsabilités et accès ;
10. Démarches : aperçu jusqu'à 3 Journeys visibles, compteur et lien
    vers la liste complète ; état vide contextualisé si aucune ;
11. Conditions/dépendances : accordéon seulement si relations
    réellement visibles ; les commandes de gestion restent dans le menu ;
12. Modes Liste/Chronologie/Dépendances regroupés après la synthèse,
    sans les imposer au-dessus du contenu.

La description et la barre des statuts restent compactes. Les contrôles
de présentation ne doivent pas concurrencer le résultat ni l'action utile.

## Personnes : qualité et confidentialité

Source : DossierAssignment et Mandate de la projection
objectives/dossier_workspace.py ; Profile reste la personne globale.

- Le serveur expose seulement les identités de Profil des Assignments et
  Mandates déjà visibles au lecteur, en conservant les permissions actuelles.
- people_preview.people contient au plus 4 Profils distincts dédupliqués
  par profile_id, et remaining compte seulement les Profils distincts
  supplémentaires visibles. Les personnes cachées ne sont pas comptées.
- Un avatar (initiale tant que la photo canonique autorisée manque) est
  tappable vers la route Profil existante /people/:id.
- La page principale affiche une ligne compacte d'avatars, un +N
  activable et un lien « Personnes et responsabilités » : elle ne
  reproduit pas une deuxième liste administrative. La page dédiée
  sépare coordination opérationnelle (Assignment) et autorisations (Mandate).
  Une Assignment ne confère aucun mandat, un membre d'Espace n'est pas
  automatiquement collaborateur du Dossier, et un participant Journey
  n'est pas automatiquement coordinateur.
- Les actions attribuer/révoquer restent des commandes serveur
  déjà existantes et uniquement disponibles aux rôles autorisés.
- En l'absence de responsabilité visible et de droit de gestion,
  ne pas afficher de section humaine artificielle.

## Démarches et progression

- Le compteur affiche les Journeys visibles réellement liées.
- Lorsque visible_journeys_complete est vrai et readiness.partial est faux,
  un indicateur de répartition peut montrer le nombre de démarches
  visibles terminées parmi les démarches visibles liées.
- Cette barre NE signifie jamais que le Dossier est accompli à un pourcentage
  donné : l'état du Dossier et la Readiness restent au serveur.
- Lorsque les données sont partielles, supprimer la barre et préciser
  « données partielles ».
- Pour une liste vide, ne pas afficher de faux compteurs ou les quatre
  onglets de présentation : proposer « Lier une première démarche »
  uniquement avec la capability dossier.journey.link et une mutation
  réellement autorisée.
- Une Journey se consulte par sa route canonique. Les badges « à traiter »
  et « terminées » sont des filtres locaux de la liste, jamais des
  résultats métier parallèles.
- Une dépendance levée est signalée comme « Condition levée »,
  et non comme une condition insatisfaite.
- Les modes avancés conservent filtres, tri, chronologie et graphe
  existants ; le changement de vue repositionne en haut de la surface.
- « Informations du Dossier » regroupe uniquement les dates et échéances
  réellement connues. Il ne constitue pas un historique d'événements.
- Le porteur Espace connu permet d'ouvrir le Profil public du collectif,
  via la route existante ; le propriétaire Profil n'est jamais inféré
  à partir du libellé « Dossier personnel ». 

## Modules conditionnels prévus, non fabriqués

Le Dossier ne possède ni Resource, Requirement, Proof, Access, Capacity,
Commerce, Payment ou historique universel. Afficher leurs aperçus
seulement après identification de la projection propriétaire et des
capacités de consultation autorisées :

- Ressources et documents : liens contextuels vers les propriétaires,
  jamais inventaire local parallèle ;
- Formulaires et conditions : situés dans leurs Journeys/Requirements
  propriétaires, pas transformés en progression Dossier artificielle ;
- Activité récente : événements métier vérifiables, sans recopier les
  messages de Conversations ;
- Paiements, accès et capacité : seulement dans les contextes qui
  possèdent effectivement ces données.

La maquette 2027 illustre ces modules, mais leur absence de la première
version est intentionnelle tant que le contrat propriétaire manque.

## État local-first et sécurité

Maintenir les clés de projection par Profil/Espace et les contrôles
serveur existants. Le cache peut préserver la lecture et la présentation,
mais n'accorde ni Mandate ni Permission. La revalidation des sources
reste discrète et les commandes non confirmées ne sont jamais affichées
comme réussies. Les états indisponible, partiel, réellement vide et
recherche infructueuse restent différents.

## Fichiers touchés par la première implémentation

- objectives/dossier_workspace.py : people_preview dédupliqué et
  identifiers visibles pour les participants autorisés ;
- mobile/lib/features/continuity/dossier_workspace_screen.dart :
  synthèse progressive, avatars à initiales, action contextuelle,
  progression des Journeys visibles, accordéon de dépendances ;
- mobile/lib/features/continuity/continuity_routes.dart : handoff
  vers /people/:id et /dossiers/:id/people, sans écran Profil parallèle ;
- mobile/lib/features/continuity/dossier_people_screen.dart : page
  secondaire de consultation des Assignments et Mandates visibles ;
  les capacités de mutation demeurent dans l'écran Dossier ;
- objectives/test_d5_cross_context_closure.py : visibilité et
  déduplication des Profils ;
- mobile/test/dossier_2027_overview_test.dart : états rempli et vide ;
- mobile/test/dossier_people_screen_test.dart : vue détaillée, navigation
  Profil et non-divulgation des personnes absentes de la projection ;
- mobile/test/dossier_2027_contextual_test.dart : débordement d'avatars
  et dépendance levée. 

## Vérifications obligatoires avant validation UX

Django :
    python manage.py test objectives.test_d5_cross_context_closure
    python manage.py test objectives.test_dossier_actor_context

Flutter :
    cd mobile
    flutter test test/dossier_2027_overview_test.dart
    flutter test test/dossier_people_screen_test.dart
    flutter test test/dossier_2027_contextual_test.dart
    flutter test test/objective_dossier_context_test.dart
    flutter analyze
    ./tool/dart_format.sh

Recette Android sur les mêmes données :
- Dossier vide personnel ;
- Dossier personnel avec 4 Journeys, 2 terminées et action requise ;
- Dossier collectif avec 1–4 Profils visibles, puis plus de 4 ;
- même Profil assigné + mandaté, un seul avatar ;
- lecteur sans droit d'administration et gestionnaire autorisé ;
- contexte Espace A/B, révocation, perte de réseau ;
- Profil visible ouvrable, Profil privé non divulgué ;
- très petit écran, grand écran, accessibilité et navigation retour.

Ne pas présumer les tests verts : ils restent à exécuter sur un
environnement Flutter/Django équipé. Ne pas fusionner #522 sans validation
fonctionnelle et contrôles de sécurité pertinents.
