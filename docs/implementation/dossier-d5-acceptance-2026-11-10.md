# Makolo — Dossier D5 : scénario de fermeture multi-contextes

Date : 10 novembre 2026. Dépôt de travail : TraditionLearningCommunity/makolo.
Branche : fix/discover-a-continuation-context-20261014, PR #522.
Ce checkpoint décrit les changements réellement ajoutés ; il n'est pas un
procès-verbal d'exécution de tests ou de recette Android.

## Contrat de sortie

D5 relie les couches déjà présentes de D0 à D4 et fige les vérifications
transversales, sans créer de second Dossier, Project, Assignment, Mandate,
Journey, API d'action, ni de deuxième UX Flutter/Web.

Un Profil peut travailler dans plusieurs Projets à la fois, mais le Dossier
conserve son ID, ses liens Journey et son propriétaire réel. Au plus un
ProjectDossierLink actif existe par Dossier. Le mandat Projet n'est pas
automatiquement un mandat Dossier. Un Assignment conservé après révocation
ne constitue pas une permission.

## Scénarios backend ajoutés

Fichier : objectives/test_d5_cross_context_closure.py.

- Un membre a Project manager sur deux Projets A, Project viewer sur un
  Projet B, Dossier manager dans A et Dossier viewer dans B.
- Les deux détails restent liés à leurs IDs canoniques ; une Journey
  réellement visible peut être référencée dans les deux Dossiers.
- Le déplacement A1 -> A2 préserve l'historique des liens Projet, l'ID du
  Dossier, et le lien Journey ; un seul Projet reste actif.
- Un Projet B n'est pas une destination autorisée en contexte A ; la
  mutation cross-Space est rejetée, sans modification du lien existant.
- Le membre B peut lire mais ne peut ni modifier le Dossier B ni en
  détacher un enfant sans autorité.
- Après révocation du Mandate Dossier A, l'Assignment A reste actif mais
  Dossier A est inaccessible et absent des enfants visibles du Projet A.
  Les permissions B restent indépendantes.
- L'organisateur en contexte A retire le Dossier A et sa référence Journey
  après la révocation ; l'organisateur B conserve son propre Dossier et
  la référence Journey réellement autorisée.
- Une Journey privée de l'organisateur n'est pas rendue visible par le seul
  Mandate Projet ou Dossier.
- Le détail Web existant se visite avec une vraie session Django ; après
  révocation, l'accès Web et l'accès API au Dossier passent à 404.
- Un membre d'équipe dépourvu de Mandate ne reçoit ni lecture ni action
  Projet/Dossier par simple membership.

## Scénarios Flutter ajoutés

Fichier : mobile/test/objective_d5_cross_context_test.dart.

- Le même identifiant Dossier est stocké avec des resourceKey distinctes en
  Espace A et Espace B ; la lecture sans contexte ne réutilise pas la version A.
- La profondeur Projet, la pagination ProjectDossiers et l'organisateur
  utilisent les paramètres de portée et des sourceKey/resourceKey séparées.
- Le chemin sans contexte conserve sa compatibilité existante.

Les tests préexistants D1/D4 restent conservés et couvrent les invalidations,
la lecture de la hiérarchie, les filtres, les bannières, les candidats,
les refus inter-Space et les destinations autorisées.

## Revalidation à l'entrée et actions sûres

- DossierWorkspaceScreen, ProjectWorkspaceScreen et ObjectiveOrganizerScreen
  revalident la portée Espace à l'entrée même si une projection locale est
  encore considérée fraîche.
- Dossier et Projet désactivent les actions de mutation pendant une
  actualisation ou après une erreur de source propriétaire.
- En Espace, l'Organizer n'affiche la création autorisée qu'après une
  réponse de source confirmée ; la présence d'une ancienne fenêtre locale
  n'est pas considérée comme une permission.
- Les commandes continuent d'être vérifiées par les services backend,
  sans statut de succès local artificiel.
- Les données mises en cache restent des données acquises localement :
  elles ne permettent pas de conclure qu'une autorisation est toujours
  active hors ligne. Les actions hors ligne sont indisponibles.

## Commandes de contrôle ciblé

Depuis la racine du dépôt :

    python manage.py test objectives.test_d5_cross_context_closure
    python manage.py test objectives.test_dossier_actor_context objectives.test_project_authority objectives.test_d3_collaboration

Depuis mobile :

    flutter test test/objective_d5_cross_context_test.dart
    flutter test test/objective_dossier_context_test.dart test/objective_organizer_data_test.dart test/objective_context_banner_test.dart test/objective_filter_reset_test.dart

Aucun de ces résultats n'est annoncé comme exécuté ou vert par ce document.

## Recette humaine encore à exécuter

1. Sur Compact Android et sur Web/Wide, entrer en Profil puis Espace A et B.
2. Ouvrir Projet A1 -> Dossier A -> Journey ; vérifier les mêmes identités
   et noms, les capacités locales et le retour au Projet source.
3. Déplacer Dossier A de Projet A1 vers A2, puis revenir à A1/A2 et dans
   l'organisateur ; aucune copie de Dossier ni de Journey.
4. Ouvrir Projet B/Dossier B : lecture seule ; aucun CTA d'écriture validé.
5. Révoquer le Mandate Dossier A depuis l'administrateur, rafraîchir A,
   vérifier le retrait du détail, des actions et des références A ; tester
   un lien direct A, ainsi que la conservation indépendante de B.
6. Tester équipe sans Mandate, Profil tiers, Journey privée, droits partiels
   et éventuelles réponses refusées à l'API.
7. Rejouer changement rapide A -> B, réponse réseau tardive, hors ligne,
   retour arrière, démarrage avec cache récent, puis retour du réseau.
8. Vérifier absence de 500, pas de faux succès, aucun secret ni ressource
   propriétaire copiée, pas de total de ressources cachées inventé.

## Limite honnête de validation

L'ajout des tests, des corrections de lecture et du checkpoint est vérifiable
dans les fichiers de la PR #522. Le runner Python/Django complet, le SDK
Flutter et un émulateur Android ne sont pas disponibles dans l'environnement
local de ce chantier. Les cas ne sont donc pas certifiés réussis ni par cette
note ni par une inspection statique. Garder la PR non fusionnée et exiger
des vérifications réelles avant toute fusion.
