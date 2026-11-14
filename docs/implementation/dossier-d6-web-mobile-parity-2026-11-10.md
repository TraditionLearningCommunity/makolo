# Makolo — D6 : parité Web/Flutter du contexte Projet–Dossier

Date : 10 novembre 2026. Dépôt : TraditionLearningCommunity/makolo.
Chantier : PR #522, branche fix/discover-a-continuation-context-20261014.

## Cadrage et absence de doublon

Le découpage initial D0–D5 ne définissait pas D6. Le dépôt contient déjà
objectives/test_d6_hardening.py pour les invariants métier historiques des
Projets : ce test et ces responsabilités ne sont pas recréés ici.
D6 désigne donc le reliquat d'intégration vérifiable entre les surfaces Web
Django et Flutter, sur la même identité, les mêmes références et la même
permission owner. Ce document n'est pas la preuve d'une recette complète.

## Ce qui est raccordé

- Les vues Web Mes démarches, Projet et Dossier consomment le même
  ObjectiveContext que les API native. La requête
  ?context=space&space=<slug> filtre uniquement les querysets déjà
  autorisés au Profil de session : un paramètre d'URL ne délègue rien.
- Les pages Web de liste, création et détail conservent ce contexte dans
  leurs liens et leurs retours après POST. Les appels historiques sans
  contexte restent transversaux, selon les droits du Profil authentifié.
- Le formulaire de création en contexte Espace impose côté serveur cet Espace
  porteur : un champ owning_space falsifié ne remplace pas ce porteur.
  SPACE_MANAGE reste contrôlé avant de créer.
- Les choix de rattachement ProjectDossierLink et de destination
  DossierProjectForm sont filtrés par portée, en plus des validations
  des services métier sous transaction.
- En Web, les commandes construites dans JavaScript ajoutent la même
  portée au POST. L'organisateur et la pagination Projet envoient le
  suffixe Espace à leurs propriétaires API, puis vérifient que la
  projection de continuation appartient bien à la portée demandée.
- Les préférences de vue de l'organisateur Web utilisent une clé distincte
  par Espace et Profil. Elles ne stockent pas les données privées.
- Le contexte Espace affiché en Web ne se substitue pas au propriétaire
  canonique ni à la personne qui agit.

Aucun modèle, aucune migration, aucune règle de Mandate ou Assignment
nouvelle n'a été ajoutée. Journey, Readiness, Access, Commerce, Capacity
et Payment demeurent leurs domaines propriétaires.

## Tests D6 ajoutés

objectives/test_d6_web_actor_context.py couvre notamment :

1. Le même membre autorisé dans A et B voit les bons objets dans les
   organisateurs Web A, B et la vue Profil historique.
2. Les liens et les profondeurs Projet/Dossier gardent la portée A ;
   un accès explicite en portée étrangère renvoie 404.
3. Les formulaires Projet et Dossier excluent les candidats de B
   lorsqu'ils sont affichés en A.
4. Le déplacement ou la modification directe d'un objet B depuis
   une page A ne contourne pas les permissions et ne modifie pas
   les liens ou données existants.
5. Une création Web en A reste portée par A, même si le client
   soumet l'identifiant de B.
6. Les contextes malformés et les tentatives d'impersonation sont
   rejetés ; un utilisateur sans autorité ne peut accéder ni
   aux profondeurs ni à la création.

La suite historique objectives/test_d6_hardening.py est conservée.

## Vérifications ciblées à exécuter

Depuis la racine du dépôt :

    python manage.py test objectives.test_d6_web_actor_context
    python manage.py test objectives.test_d5_cross_context_closure objectives.test_dossier_actor_context objectives.test_d6_hardening

Syntaxe des scripts :

    node --check static/js/objective-organizer.js
    node --check static/js/project-workspace.js
    node --check static/js/dossier-workspace.js

Puis reproduire dans un navigateur et sur Android :

- Profil → Mes démarches → Projet A → Dossier A → Journey ;
- Espace A → organisateur → Projet A → Dossier A ;
- Espace B → Projet B et Dossier B, sans accès croisé ;
- pagination au-delà des 50 éléments et recherche/tris, puis retour à A ;
- formulaire de création dans A, tentative de forger B ;
- rattachement et déplacement autorisés A1 → A2, cible B refusée ;
- révocation du Mandate, essai d'ancienne URL directe, liste et
  continuation dans un onglet déjà ouvert ;
- navigateur sans JS (les liens de repli conservent la portée), clavier,
  écran étroit, grand écran, reconnexion et erreurs explicites.

## Validation et prudence

Les modifications ont été écrites dans la PR #522, pas dans main.
La CI, Django et un navigateur réel ne sont pas attestés verts par ce
checkpoint. L'environnement d'exécution local ne dispose pas de Django,
et l'accès réseau GitHub en ligne de commande est indisponible : cette
validation devra être effectuée sur un runner correctement configuré.
Ne pas fusionner la PR tant que les tests et vérifications nécessaires
n'ont pas été réalisés et les éventuelles régressions corrigées.
