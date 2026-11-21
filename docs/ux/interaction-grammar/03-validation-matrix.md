# D — Matrice de validation et critères de qualité Makolo Interaction Grammar

**Statut : plan de validation, tests NON exécutés dans ce chantier documentaire.**  
**Périmètre :** futures implémentations du contrat 01-interaction-contract.md à partir du catalogue 02-primitives-catalog.md.  
**Référence d'audit :** 00-audit.md, main @ d0f0ec421c94c255fa4c0acd3509938a70c6322f.

## 1. Critère de succès

**Une personne non technicienne comprend l'action sans tutoriel, trouve la même intention dans plusieurs contextes, retrouve son travail en revenant et ne reçoit jamais une confirmation mensongère.**

Le rendu doit être calme, adulte, soigné et professionnel. Une interface jugée « jolie » mais difficile à utiliser au clavier, trompeuse sur l'état ou incohérente entre les clients ne passe pas.

La matrice distingue :
- **Prouvé actuellement** : preuve présente dans le code/tests lus, sans présumer de leur exécution aujourd'hui.
- **À tester à l'implémentation** : comportement attendu, pas encore revendiqué comme livré.
- **Bloqué par owner** : action impossible à exiger tant que le service, les permissions et le transport requis n'existent pas.

## 2. Trames de test transversales

| ID | Intention / scénario | Web attendu | Flutter attendu | Critère commun |
| --- | --- | --- | --- | --- |
| T01 | Ouvrir une ligne puis retour | URL / historique / scroll conservés | Retour natif, scroll conservé | Aucun saut ni perte de filtre |
| T02 | Ouvrir actions secondaires | ⋯ / clic droit conditionnel / focus | ⋯ / appui long optionnel | Actions et libellés cohérents, pas de droit supplémentaire |
| T03 | Aperçu de contenu autorisé | Panneau Inspect quand largeur utile | Sheet/détail selon espace | Même vérité, fermeture/retour sûrs |
| T04 | Sélection multiple | Cases, clavier, mode signalé | Mode sélection, cases accessibles | Pas d'ouverture accidentelle en mode sélection |
| T05 | Trier par critère | Menu de tri, contexte restaurable | Contrôle de tri équivalent | Tri de lecture ≠ classement métier |
| T06 | Réordonner manuellement | Poignée, clavier Monter/Descendre | Poignée, commandes alternatives | Présent seulement avec ordre owner modifiable |
| T07 | Déplacer un Dossier | Déplacer vers et drop optionnel | Choix de destination ; drag optionnel | Même commande owner, même résultat autoritatif |
| T08 | Lier une Démarche | Associer, jamais déplacer implicitement | Associer, jamais déplacer implicitement | Relation préservant ownership Journey |
| T09 | Changer d'état | Transition proposée par owner | Même transition pertinente | Jamais transition induite du seul glissement |
| T10 | Éditer sur place | Enter/validation/Escape | Saisie/validation/annulation | Brouillon conservé, pas d'écrasement concurrent |
| T11 | Annuler opération | Action inverse proposée si sûre | Action inverse proposée si sûre | Pas de bouton Undo factice |
| T12 | Recherche | Ctrl/Cmd+K = navigation, recherche transverse distincte | Recherche transverse dédiée | Recherche locale bornée et sans fuite |
| T13 | Feedback pendant mutation | Progression, blocage double-submit | Pending, sync et haptique adaptée | Succès seulement après confirmation |
| T14 | Préférences et reprise | Tri, filtre, scroll, sélection/overlay restaurés | Même contexte dans scope acteur | Pas de fuite entre comptes/acteurs |
| T15 | État sans résultat / calme | Empty ≠ No Match ≠ fin corpus | Même distinction sémantique | Texte minimal sans faux « tout est en ordre » |

T06/T07/T09/T10/T11 sont **conditionnels** : la matrice ne crée pas les commandes absentes.

## 3. Scénarios de validation métier (quatre contextes différents)

| ID | Contexte | Scénario | Attendus / restrictions |
| --- | --- | --- | --- |
| O01 | Projet et Dossier | Attacher un Dossier visible à un Projet permis | Même autorité que link_dossier_to_project ; aucune autre permission acquise |
| O02 | Projet et Dossier | Déplacer un Dossier du Projet A vers B | Vérification source + cible, nouvelle relation confirmée ; pas de clone |
| O03 | Projet et Dossier | Détacher un Dossier | Relation retirée, Dossier persiste ; wording distinct de « Supprimer » |
| O04 | Dossier et Démarche | Associer / dissocier une Journey | Pas de transfert de propriétaire ni changement des droits de Journey |
| O05 | Dossier et dépendance | Visualiser une dépendance causale ; éventuellement la modifier via commande autorisée | Représentation causale ≠ tri ni position des cartes |
| E01 | En cours personnel | Naviguer entre situations / détails puis retour | Conservation du contexte, absence de Kanban ou TODO global imposé |
| E02 | En cours personnel | Tri d'une liste ordonnée par le serveur | Pas de ranking client inventé, pas de poignée si pas d'ordre manuel |
| S01 | Space Métier | Menu et aperçu d'un objet accessible à un membre | Dépend de sa Permission/Mandate, pas de la seule membership |
| S02 | Space Métier | Comparer contexte personnel et acteur Space | Préférences, actions, caches et sélection isolés |
| J01 | Jour J / opérations | Choisir une action critique sur une Occurrence | Capacité/revalidation owner ; zéro faux succès |
| J02 | Jour J / opérations | Indisponibilité réseau au moment d'un contrôle | Résultat selon autorité offline déléguée réelle, sinon pas de validation inventée |

**Priorité d'essai pratique :** O01–O04 pour le pilote ; E01/E02 pour vérifier que la grammaire ne devient pas gestionnaire de tâches ; S01/S02 pour les permissions ; J01/J02 pour sécurité et continuité.

## 4. Matrice négative — indispensable

| ID | Condition | Résultat exigé |
| --- | --- | --- |
| N01 | Viewer sans droit sur source ou destination | Pas d'action exploitable ; refus serveur ; pas de fuite de nom/existence privé |
| N02 | Droit révoqué après affichage du menu | Mutation refusée, menu réconcilié, contexte restauré |
| N03 | Drop sur conteneur invalide | Aucune mutation, retour du visuel, raison compréhensible si nécessaire |
| N04 | Objets modifiés par autre utilisateur entre début du geste et drop | Conflit ou revalidation ; aucun écrasement silencieux |
| N05 | Double clic, double tap ou retry réseau | Pas de double mutation ; identité d'opération cohérente si owner le permet |
| N06 | Perte réseau après envoi, issue inconnue | Ne pas annoncer succès ; réconcilier plutôt que réémettre aveuglément |
| N07 | Session expirée ou changement de compte | Ne pas perdre le brouillon utile ; ne pas rejouer une action sous autre acteur |
| N08 | Erreur de validation | État et contenu préservés ; explication locale ; aucune disparition trompeuse |
| N09 | Undo pas réellement disponible | Pas d'Undo affiché ; confirmation de risque lorsque justifiée |
| N10 | Sélection d'objets aux capacités hétérogènes | Actions groupées limitées aux opérations réellement communes / explicitement partielles |
| N11 | Ensemble serveur changé pendant le tri/chargement | Identité stable, pas de doublon, focus et ancre conservés autant que possible |
| N12 | Hors ligne avec commande non délégable | Pas de fausse confirmation ni de mutation locale faisant autorité |
| N13 | Icône masquée / texte agrandi | Action encore identifiable et activable |
| N14 | Surface interactive en chargement / refresh | Contenu existant conservé quand possible ; pas d'écran vide fugitif |

La politique de réponse serveur, transaction/compensation et autorité offline doit être **démontrée au moment de l'implémentation**, pas imaginée ici.

## 5. Accessibilité et adaptation : matrice d'appareils

| Configuration | Cas à prouver |
| --- | --- |
| Web clavier uniquement, 1440 px | Tab/Shift+Tab, Enter/Espace, Escape, focus trap/restore, action alternative au drag |
| Web souris, 1440 px | Menus ⋯ et clic droit facultatif, drag source/cible, aperçu sans perte d'ancre |
| Web tablette tactile, 800 et 1199 px | Pas de hover obligatoire, layout adaptatif sans double panneau forcé |
| Web compact à 400 px | Navigation basse lisible, contrôles accessibles, aucun débordement horizontal |
| Web expanded à 1200 px | Composition Master/Detail/Inspect seulement si utile |
| Flutter téléphone Android | Touch targets 48 dp, clavier natif, Back, SafeArea et haptique mesurée |
| Flutter iOS quand environnement disponible | Retour/gestes natifs, zoom texte, VoiceOver, SafeArea |
| Flutter tablette / grand écran | MakoloLayout selon espace réel, pas de cartes mobiles artificiellement étirées |
| Web lecteur d'écran | Libellés d'actions, sélection, menu, progression, invalid drop, annonces non spammées |
| Flutter TalkBack / VoiceOver | Semantics labels, états sélection, actions alternatives, notifications sobres |
| Dark mode / Light mode | Contraste et icônes lisibles, états distinguables sans couleur seule |
| Texte agrandi / Reduce Motion | Reflow, pas de clipping, aucun geste ni statut dépendant d'une animation |

Seuils de référence existants : Web compact <768 CSS px, adaptive 768–1199, expanded >=1200 ; Flutter suit les classes Presentation existantes, distinctes des breakpoints du shell. Les seuils ne sont pas à homogénéiser artificiellement.

## 6. Scénarios de reconnaissance sans tutoriel

Trois exercices qualitatifs sur plusieurs surfaces et profils de test, sans instruire où cliquer :

1. Trouver comment ouvrir les actions secondaires d'un Dossier, puis les actions d'une autre entité.
2. Comprendre la différence entre « trier une liste » et « changer manuellement l'ordre » ; reconnaître l'absence de poignée quand l'ordre est figé.
3. Déplacer un Dossier par la voie alternative accessible, puis comprendre pourquoi « Associer une Démarche » n'est pas « Déplacer ».

**À relever** : réussite sans aide, confusion du symbole, erreur de navigation, abandon, compréhension des conséquences et de la confirmation. Ne pas inventer de scores d'utilisabilité à l'avance ; conserver des observations reproductibles, par rôle, appareil, écran et scénario.

L'absence de tutoriel ne signifie pas absence d'accessibilité : libellés vocaux, confirmations justifiées et messages d'erreur utiles restent obligatoires.

## 7. Tests existants à conserver / étendre plus tard

- **Web :** e2e/specs/interactions.spec.mjs (navigation/clavier/menu, shell et mobile Web), objectives-product.spec.mjs (rattachement, détachement, permissions, mobile, a11y), accessibility.spec.mjs et permissions.spec.mjs.
- **Serveur :** objectives/test_d3_collaboration.py, test_d4_readiness.py, test_d5_project.py, test_d6_hardening.py et tests de services owners concernés.
- **Flutter :** mobile/test/behavior_primitives_test.dart, presentation_state_contract_test.dart, presentation_layout_test.dart, resumable_interaction_store_test.dart, visual_regression_test.dart, tests de sync/permissions lorsque concernés.

Pour les nouveaux comportements, ajouter tests **de contrat de primitive**, **d'intégration métier autoritative** et **E2E geste + alternative**. Ne pas affaiblir les tests existants pour passer la CI. Les golden/screenshots sont un complément, pas une preuve d'autorité ou de Semantics.

## 8. Conditions bloquantes par lot de future implémentation

### Gate G0 — conception

- A, B, C, D revus sur le main courant ; source Behavior historique réconciliée si récupérée.
- Registre d'icônes confirmé (Lucide/Material) et langage Product Language respecté.
- Collision audit : CSS global, navigation, runtime HTMX, design Flutter, sync, owner APIs.
- Matrice de tests du lot sélectionnée ; dépendances métiers prouvées.

### Gate G1 — sécurité et modèle

- Source d'autorité explicitée, permissions serveur et visibilité des destinations démontrées.
- Sémantique MOVE/LINK/REORDER/TRANSITION non interchangeable.
- Idempotence, refus, concurrence et compensation définis par owner.
- API mobile ou autre transport supporté : **preuve runtime requise**, jamais simulé.
- Aucune migration destructive ni copie de vérité dans le client.

### Gate G2 — expérience

- Voies souris, tactile, clavier et lecteur d'écran réelles.
- Feedback pending/refused/confirmed et récupération du contexte.
- Light/dark, grand texte, motion réduite, cibles tactiles et viewport adaptatif.
- Pas d'explication d'architecture à l'utilisateur, pas de tutoriel imposé ni animation décorative.
- Captures / golden / scénarios de reconnaissance non technicien réalisés.

### Gate G3 — intégration

- Tests ciblés puis suite pertinente, checks CI entièrement verts.
- PR dédiée, réconciliation avec main avant merge, pas de merge rouge.
- Vérification main après merge puis smoke tests par rôle dans un environnement de test réel, sans qualifier PythonAnywhere de production.

## 9. Décision d'ordonnancement

**Première future PR fonctionnelle recommandée :** stabilisation du registre/contrat de menus, états et aperçu, avec scénarios accessibles. **Pilote métier suivant :** déplacement Dossier → Projet après audit du transport de mutation mobile. **Ensuite seulement :** sélection multiple, ordre manuel et visualisations riches lorsque le propriétaire possède les opérations nécessaires.

Le présent chantier **n'exécute aucun de ces gates runtime**, ne déclare aucune fonctionnalité livrée et ne valide pas la CI par anticipation. Sa définition de terminé est documentaire : audit sourcé, décisions sans ambiguïté, catalogue sans doublons et scénarios négatifs inclus.
