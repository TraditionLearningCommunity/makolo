# Moi → Mes démarches — finition et vérifications sur #522

Date : 9 novembre 2026. Cette passe se limite à la présentation Flutter,
aux tests de non-régression et aux contrats API déjà propriétaires.
**Aucun modèle, migration, endpoint, règle de permission ou événement métier
nouveau.** Aucune modification directe de `main`.

## 1. Mes démarches

- Barre de création persistante : **+ Dossier** et **+ Projet**, sans actions
  cachées dans le menu principal. Recherche, filtres et tri restent en haut.
- Sélecteur secondaire Cartes/Liste/Explorateur : **aligné à droite**, bordure
  commune, icônes de 19 dp, cible tactile conservée à 44 × 44 dp. Les petits
  écrans conservent un défilement horizontal, sans tronquer les commandes.
- Cartes : suppression de la deuxième mention du type quand la description
  est vide ; espacements resserrés ; dates, état et contexte gardés.
- Compteurs : `1 projet`, `2 démarches`, `3 éléments`, `1 résultat`,
  `2 résultats`, avec mention « chargés » pour les collections partielles.
- Pas de total serveur reconstitué à partir des pages locales.

## 2. Explorateur et rattachements multiples

- `OrganizerHierarchy` compose exclusivement les entrées canoniques
  `project`, `dossier` et `journey` déjà autorisées et acquises.
- Un Projet contient les Dossiers acquis dont `project_id` le référence.
  Les Dossiers indépendants sont des racines.
- Une Journey liée à plusieurs Dossiers apparaît **une seule fois** dans
  l'Explorateur, sous le premier Dossier acquis dans l'ordre stable des IDs.
  Les liens supplémentaires sont signalés en texte. Il s'agit d'un choix de
  présentation, **pas** d'une nouvelle relation métier principale.
- Les parents non encore acquis sont indiqués comme **non chargés**, pas
  comme « indépendants ». La recherche et les filtres remontent les parents
  nécessaires et ouvrent les chemins visibles.
- Les dépendances entre Journeys restent la responsabilité du Dossier : le
  graphe et la liste accessible se consultent sur son écran dédié. La
  collection centrale ne fabrique ni arête ni statut de readiness.

## 3. Projet et Dossier

- Les propriétaires, titres, états, échéances, readiness et limitations de
  visibilité proviennent toujours des projections serveur.
- En-têtes simplifiés, pas de « PROJET · Projet personnel » ou
  « DOSSIER · Dossier personnel ».
- Dossier : commandes renommées « Ajouter un prérequis » et « Rattachement »
  pour expliciter les opérations déjà présentes.
- Les fonctions créer, rattacher, déplacer, détacher, lier une Journey,
  retirer une Journey, modifier les états, mandats et responsabilités restent
  conditionnées aux `capabilities` serveur et à la confirmation distante.
  Aucune réussite métier n'est déduite d'un tap hors ligne.
- Les détails continuent de revalider leurs projections et la première page
  de Mes démarches après mutation ; le cache périmé ne doit pas restaurer
  une relation effacée.

## 4. Vérifications codées

- `mobile/test/objective_organizer_data_test.dart` : 6 Projets / 24 Dossiers
  + Dossier indépendant, Journey liée à trois Dossiers, absence de duplication
  dans l'arbre, parents non chargés et libellés grammaticaux.
- `mobile/test/organizer_view_switcher_test.dart` : trois vues visibles,
  clics et cibles tactiles de 44 dp.
- `objectives/test_workspace_read_models.py` : Project → Dossier →
  Journey, dépendance canonique, Journey liée à deux Dossiers, Dossier
  indépendant, détachement/rattachement, conservation de la Journey et
  refus d'écriture sur les objets d'un autre Profil.
- Les tests et contrats existants d'Organizer local-first, pagination,
  actualisation, accès refusé et modèles de profondeur sont conservés.

### Exécution ciblée possible (pas de CI requise pour continuer le chantier)

```powershell
python manage.py test objectives.test_organizer_collection objectives.test_workspace_read_models
cd mobile
flutter test test/objective_organizer_data_test.dart test/organizer_view_switcher_test.dart test/objective_organizer_sync_test.dart
```

Ces commandes **ne sont pas attestées comme exécutées** par cette passe.

## 5. Vérifications restant à faire sur un client installé

1. **Mobile étroit et texte agrandi** : barre fixe, les deux créations
   visibles/atteignables, sélecteur de vues compact, aucune superposition.
2. **Profil avec plusieurs Projets** : trois vues ; recherche/tri/type/état/
   contexte/période ; suppression des filtres ; 50+ éléments et suite paginée.
3. **Dossier indépendant, projet parent incomplet, Journey partagée** :
   un seul nœud Journey dans Explorateur, mentions des autres relations et
   accès aux vrais liens depuis le détail Dossier.
4. **Dépendances** : graphe dans le Dossier, liste accessible, prérequis
   visibles et signaux de vue partielle. Aucune dépendance inventée.
5. **Création et mutations** : création Dossier/Projet, rattachement,
   détachement, Journey liée/retirée, changement de statut, retour à la
   collection actualisée ; un refus serveur reste un refus.
6. **Cache et permissions** : mode avion, démarrage à froid, pagination
   tardive, changement de Profil, retrait du droit d'accès, aucune ancienne
   projection réintroduite et aucune action hors ligne annoncée confirmée.
7. **Navigation réelle** : Mes démarches → Projet → Dossier → Journey,
   retours arrière, rafraîchissements et état de chargement.

**Statut :** modifications déposées sur la branche active de #522, tests
ajoutés mais non exécutés ici ; aucune validation Android physique ni
résultat CI revendiqués. Ne pas merger sans validation pertinente.

## Ajustement explorateur et chargement automatique — 9 novembre 2026

- Le paragraphe explicatif permanent en tête de l'Explorateur est retiré.
- Indentation minimale : 7 dp par niveau, avec une colonne de chevrons
  compacte et une zone de titre plus large. Les noeuds commencent près du bord
  gauche, sans sacrifier l'identité Projet / Dossier / Journey.
- Tous les Projets **et tous les Dossiers** disposent d'un chevron distinct du
  lien sur la ligne : le chevron ouvre/replie les enfants, toucher le titre
  ouvre la page du Projet ou du Dossier. Une Journey ouvre directement son
  parcours. Un Dossier vide s'ouvre sur un contenu vide, sans texte fictif.
- Le chargement de la collection de Mes démarches et des Dossiers d'un Projet
  devient **automatique à l'approche du bas** (seuil de 450 dp). Aucun bouton
  « Voir davantage », numéro de page ou « Suivant ». Les fenêtres serveur
  restent contiguës, propriétaires, et acquises dans le cache local. La
  progression apparaît en bas pendant l'acquisition.
- La génération de nouvelles demandes est bloquée en mode hors ligne,
  pendant un chargement en cours ou après un échec ; un rafraîchissement
  explicite permet de reprendre. Les erreurs ne doivent pas boucler
  silencieusement au moindre scroll.
- Tests de données : Dossier vide conservé sous son Projet, sans Journey
  inventée. Le comportement exact des gestes et du scroll doit encore être
  vérifié sur un émulateur/appareil ; aucun test Flutter exécuté ici.

