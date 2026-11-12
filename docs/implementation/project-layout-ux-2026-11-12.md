# Makolo — Projet : composition universelle après validation de maquette

Date : 12 novembre 2026. Branche : PR #522.

## Règles fermes de présentation

1. **Une seule page Projet** pour un porteur Profil ou Espace. Le serveur
   décide le porteur, la visibilité des membres, les capacités et les faits ;
   Flutter et le Web composent la même présentation.
2. Afficher en tête **titre et état** du Projet. Ne pas répéter les mots
   « Projet personnel », « Espace actif » ou « Contexte porteur ».
3. Conserver la navigation à trois icônes **Synthèse / Dossiers / Calendrier**
   avec tooltip et noms d'accessibilité.
4. **Immédiatement après cette ligne**, montrer la description `horizon.description`
   comme une ligne de contenu naturel, **sans titre**. Une icône `info`
   l'accompagne discrètement. Description absente ou blanche : aucune zone.
5. Replier la description **seulement si elle dépasse trois lignes rendues**,
   avec commande pour développer / replier. Une description courte n'a aucun
   chevron. Déterminer le débordement à la largeur réelle, pas par un nombre
   fixe de caractères. Préserver le texte exact fourni par le serveur,
   sans résumé inventé.
6. Puis afficher un aperçu compact **Personnes et accès**, avant les
   indicateurs : le porteur réel et jusqu'à quatre personnes possédant
   un mandat visible. Pas de nombre déduit de personnes cachées. Le symbole
   `+` ouvre la profondeur, ce n'est pas un compteur calculé.
7. Distinguer porteur, mandataires Projet et contributions transversales ;
   aucun mandat Projet n'accorde implicitement accès aux Dossiers,
   Conversations ou autres domaines.
8. Les avatars affichent actuellement des représentations neutres
   (initiales Flutter, pictogrammes Web). Les vraies photos et l'ouverture
   directe des Profils nécessitent un **contrat de projection d'identité
   autorisée et une route de Profil approuvée** ; ne pas les inventer.
9. Les indicateurs ne montrent pas de zéros inutiles et ne calculent
   aucun pourcentage d'accomplissement fictif.
10. Les vues Dossiers / Calendrier restent les mêmes composants et les
    mêmes filtres indépendamment du porteur.

## Code existant utilisé

- `ProjectWorkspaceScreen` est conservé, aucune variante personnelle/Espace.
- Nouveau composant réutilisable `ProjectDescription`, alimenté exclusivement
  par `project.horizon.description`.
- `_peoplePreview` compose `owner` et `collaboration.members` déjà
  projetés par `project_workspace()` ; l'ouverture donne accès aux mandats
  et à la délégation si autorisée.
- Web : `project_detail.html`, `project-workspace.js`,
  `project-workspace.css` ; le texte est intégral sans JS et se replie
  seulement lorsque le client peut mesurer son débordement.
- Aucune migration, nouveau modèle, URL métier, ou permission introduite.

## Vérification

- Description vide : rien, pas d'encart ni contrôle.
- Description courte : texte intégral, aucun chevron.
- Description longue : trois lignes puis commande ; expansion/réduction ;
  retour au repli après changement du texte.
- La zone apparaît immédiatement après les vues, avant Personnes.
- Identité du porteur visible même quand aucun mandat n'a été délégué.
- Lecteur d'un Projet partagé : uniquement les mandats que le serveur
  autorise à lui révéler. Un bouton ne suppose jamais une autorité.
- Même présentation depuis Profil et Espace, en mobile et Web.
- Aucun lien vers un Profil non autorisé ; photo/URL non contractuelle non
  rendue.
- Analyse Flutter, tests widget et Django, rendu sur émulateur et smoke
  tests Web à exécuter avant validation complète.

Ne pas merger #522 avec une CI obligatoire rouge.
