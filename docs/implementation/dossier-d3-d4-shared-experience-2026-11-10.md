# Makolo — Dossier D3/D4 : présentation unique et interactions contextuelles

Date : 10 novembre 2026. Dépôt : TraditionLearningCommunity/makolo.
Branche de la PR #522 : fix/discover-a-continuation-context-20261014.

## Portée

D3 et D4 sont intégrés dans la PR #522, sans branche ou PR concurrente.
Il s'agit d'une consolidation de la présentation et des interactions Objectives
existantes ; pas d'un nouvel écran Dossier, d'un modèle, d'une migration ou
d'une deuxième règle d'autorisation.

Conserver un Dossier canonique, un ProjectDossierLink actif au maximum, la
Journey propriétaire et les capacités validées au serveur. Le Profil humain
reste le principal ; l'Espace choisi n'est qu'une portée de consultation.

## D3 — Une présentation cohérente

- La route /dossiers/:id conserve DossierWorkspaceScreen, pour Profil et Espace.
- L'écran Projet conserve ProjectWorkspaceScreen et les sous-vues Dossiers,
  sans cloner le détail Dossier.
- Le composant ObjectiveContextBanner est partagé entre les deux écrans :
  il distingue « Consultation depuis mon Profil » et « Espace actif » et
  rappelle le porteur réel projeté par Objectives. La bannière n'est pas
  un sélecteur d'autorité.
- Les vues déjà existantes sont conservées : Dossier (vue d'ensemble, liste,
  chronologie, dépendances) et Projet (synthèse, Dossiers, calendrier).
- Les informations partielles de Readiness, les dépendances autorisées,
  les Assignment et Mandate restent celles de la projection owner ; les
  écrans ne fabriquent pas de droits ou de progression.
- ObjectiveFilterReset est une commande locale réutilisable (« Tout effacer »)
  sur les listes Projet et Dossier : ni source de vérité ni mutation distante.

## D4 — Navigation, contexte, filtres et mutations

- Depuis un Projet, l'ouverture d'un Dossier conserve un identifiant de Projet
  d'origine dans le chemin de navigation. Le bouton « Retour au Projet »
  apparaît seulement si le parent visible correspond toujours à cet identifiant ;
  autrement l'action ouvre explicitement le Projet parent visible.
- Le contexte ActorContextController s'applique aussi à ProjectWorkspaceScreen,
  avec la même portée que DossierWorkspaceScreen.
- ObjectiveRepository sépare les clés locales de détail et de pagination
  Projet-Dossiers par Espace ; les fragments des autres Espaces ne peuvent
  pas être ajoutés à la vue active.
- Les endpoints de mutations Projet utilisent le même contexte Espace que
  leur lecture, après une nouvelle validation des permissions serveur.
- Un changement d'Espace rebind les flux, réacquiert le détail et neutralise
  les complétions asynchrones précédentes ; les filtres de contexte sont
  réinitialisés sans effacer les données métier.
- Les filtres de liste sont des vues locales sur les éléments acquis. Les
  états vides distinguent absence de données visibles et absence de résultats
  correspondant aux filtres. Les interfaces n'inventent pas de total caché.
- Les créations et les commandes métier conservent les services Objectives
  existants et sont confirmées à distance ; les actions désactivées hors
  ligne ne sont jamais annoncées comme réussies.

## Consolidation serveur nécessaire à D3/D4

- project_workspace et la pagination project_dossier_page prennent une portée
  actor_context facultative pour filtrer Dossiers visibles, collaborations,
  candidats et destinations autorisées dans l'Espace sélectionné.
- Les liens Projet et Dossier renvoient le suffixe de portée pertinent, sans
  réécrire la relation canonique.
- Une relation Dossier/Projet inter-Espaces peut exister et demeure canonique.
  Elle n'est pas dévoilée dans un Espace où l'objet lié est hors portée.
- Les mutations de rattachement refusent de gérer le Projet source depuis
  un contexte Espace étranger, sans transférer l'autorité au client.

## Tests ajoutés ou étendus

- objectives/test_dossier_actor_context.py : cas de Projet A relié à Dossier B,
  présentation limitée au contexte actif et refus d'action hors portée.
- mobile/test/objective_dossier_context_test.dart : clés des pages
  Projet-Dossiers différenciées entre Espaces.
- mobile/test/objective_context_banner_test.dart : porteur distinct de
  l'acteur présenté, Profil vs Espace.
- mobile/test/objective_filter_reset_test.dart : bouton de réinitialisation
  caché quand inactif et callback lorsque sollicité.

Les tests existants de Project, Dossier, Journey, permissions et sélecteurs
restent intacts. Les suites et l'émulateur ne sont pas déclarés verts par ce
document : l'utilisateur a demandé de privilégier l'implémentation D3/D4
sans attendre les vérifications CI. La PR #522 reste ouverte et non fusionnée.

## État des PR

Au moment du contrôle GitHub, seule la PR #522 était ouverte.
Aucune autre PR n'était disponible à fermer. Ne fermer aucune future PR
sans inspection de son périmètre et des changements indépendants.
