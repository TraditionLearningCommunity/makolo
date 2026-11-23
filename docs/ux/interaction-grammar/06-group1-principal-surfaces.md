# Groupe 1 — Migration des cinq pages principales vers les interactions communes

**Statut : code migré sur la branche de la PR #522 ; validation CI et visuelle à confirmer avant clôture.**  
**Périmètre strict :** Maintenant, Découvrir, En cours, Moi et Makolo Mark, Web et Flutter.  
**Dépendances :** contrats A–D, F1 (04) et F2 (05). Aucun changement de responsabilité métier.

## 1. Décision

Les composants réutilisables sont définis **une seule fois par interface**. Le Web conserve des templates Django/HTMX et le fichier global `static/css/makolo-interactions.css`, sans créer de CSS pour un bouton dans Découvrir, puis un autre dans Moi. Flutter consomme le thème Makolo et les composants transversaux dans `mobile/lib/design`.

Une page garde uniquement sa composition : hiérarchie des informations, grille ou rail, taille des médias, présentation de sa verticale et disposition de ses actions. Le sens et l'apparence des actions courantes ne sont pas redéfinis par page.

Les shells `templates/base/app.html` (**personnes connectées**) et `templates/base/public.html` (**visiteurs**, notamment Découvrir) chargent le même socle CSS/JS F1–F2. Sans cela la recherche publique conserverait des boutons sans style.

Le Web dispose des variantes partagées `mk-action-button` (`primary`, `secondary`, `ghost`, `danger`, `link`) et du `mk-disclosure-trigger`. Flutter ajoute `mobile/lib/design/action_controls.dart` : `MakoloActionButton` (`primary`, `secondary`, `quiet`) et `MakoloIconActionButton` (cible minimale de 48 dp et tooltip requis). Ces contrôles s'appuient sur le `ThemeData` et les tokens existants ; ils ne résolvent pas les permissions.

## 2. Inventaire et adoption des cinq pages

| Entrée | Web : migrations réalisées | Flutter : migrations réalisées | Spécificités à conserver |
| --- | --- | --- | --- |
| **Maintenant** | Actions principales et secondaires de situations, navigation de profondeur et boutons de décision avec `mk-action-button` ; détail « Voir plus » avec `mk-disclosure-trigger` | Retry, retour depuis profondeur, handoff propriétaire et lecture des médias avec `MakoloActionButton` | Projection Now, choix de décision via POST owner, continuité par curseur, médias et profondeur N2 |
| **Découvrir** | Recherche/filtre server-backed inchangés ; boutons de recherche, raccourcis, pagination, sauvegarde, partage et actions des cartes passent à `mk-action-button` | Pagination de l'exploration et action « Autour de moi » via le contrôle partagé ; preview carte (fermer/ouvrir/itinéraire) via contrôles partagés | Recherche transverse propriétaire, rang serveur, vue carte, géolocalisation consentie, partage et sauvegarde |
| **En cours** | Liens de retour, handoff de chaque unité, toggle de sauvegarde, commandes de partage et divulgation « Voir plus » adoptent les classes communes | Retry, retour de profondeur et action principale N1 utilisent le socle partagé | Continuité Journey/owner, actions de sauvegarde et partage existantes, calendrier, N2 |
| **Moi** | Liens « Modifier mon passeport » et « Gérer/Voir tout » du hub sur `mk-action-button` ; couleurs de l'écran branchées aux tokens Makolo, duplications de focus et de boutons retirées | Édition de profil via `MakoloIconActionButton` | Profil, Passeport, collectifs, collections et permissions propres aux objets |
| **Makolo Mark** | CTA `Continuer` migré, formulaire POST maintenu, marque et choix de navigation inchangés ; entrée `data-mk-surface="mark"` | CTA et trois actions Joindre/Photo/Voix utilisent les contrôles communs | Entrée intent/context, acquisitions média permises, état de récupération et clarification |

### Preuves de sources

- Web : `templates/core/participant_home.html`, `_now_stream_items.html`, `_participant_ongoing_content.html`, `_ongoing_unit.html`, `participant_me.html`, `makolo_mark.html`, `templates/discovery/home.html`, `templates/discovery/_universal_card.html`.
- Flutter : `mobile/lib/features/now/now_screen.dart`, `discovery/discovery_screens.dart`, `discovery/discovery_mature_view.dart`, `ongoing/ongoing_screen.dart`, `me/me_screen.dart`, `mark/mark_screen.dart`.
- Tokens et placement : `static/css/makolo-interactions.css`, `static/css/me-n1.css`, `static/css/mature-experience.css`, `mobile/lib/design/action_controls.dart`.

## 3. CSS : ce qui est centralisé et ce qui reste légitime

- **Centralisé :** hauteur/forme/couleur/focus/variantes des boutons, liens d'action, menus et commandes de divulgation. Les classes de pages peuvent servir au placement, à l'alignement et aux états d'expansion spécifiques.
- **Retiré ou borné :** duplication des couleurs propres à Moi au profit de `--mk-*`, anciens styles locaux de ses boutons de navigation, focus local redondant ; styles `mk-now-cta` et commandes En cours gardés en **fallback pour les profondeurs non migrées** seulement lorsque la classe commune n'est pas présente.
- **Conservé :** charte de composition, disposition des cartes, aperçu média, espaces, ordre sémantique, affordances particulières d'un contenu propriétaire. `static/css/me-n1.css` n'est pas supprimé : il contient encore des règles propres au **layout et au contenu de Moi**, pas une deuxième bibliothèque de boutons.
- **Compatibilité :** anciens `mk-btn` et `mk-panel` peuvent rester ailleurs tant que les groupes 2/3 ne sont pas migrés. Pas de remplacement global de tout le projet, pas de migration destructive.

Dans Découvrir, ne **jamais** connecter le tri DOM local F2 à la collection propriétaire de recherche : elle peut être partielle et son ordre reste contractuel côté serveur. Les formulaires existants conservent méthodes, actions et CSRF. Les opérations de sauvegarde/partage ne sont pas remplacées par un endpoint générique.

## 4. Flutter : mêmes intentions, pas d'écran générique

Le nouveau fichier `mobile/lib/design/action_controls.dart` **compose** `FilledButton`, `OutlinedButton`, `TextButton` et `IconButton`, tous stylés par `buildMakoloTheme`. Aucun nouveau thème ni design system parallèle.

- `MakoloActionAppearance.primary` : action la plus utile et autorisée dans son contexte.
- `MakoloActionAppearance.secondary` : action alternative ou contextuelle.
- `MakoloActionAppearance.quiet` : navigation secondaire, retour, retry ou inspection.
- `MakoloIconActionButton` : affordance iconique seulement avec tooltip humain, taille tactile minimale, callback provenant de l'écran propriétaire.
- `busy=true` désactive l'invocation ; il ne signifie **pas** réussite ou état métier confirmé.

Les actions comportant un composant spécialisé (`DiscoveryOrbitIcon`, share control, caméra native, états de lecture) restent spécialisées, mais consomment le thème commun. Les écrans N2/N3, formulaires métier et assistants dédiés ne font **pas** partie du Groupe 1, même lorsqu'ils sont accessibles depuis les onglets principaux.

## 5. Contrôles et scénarios de non-régression

### Tests ajoutés

- `mobile/test/action_controls_test.dart` : boutons primary/quiet/secondary, cible 48 dp, action désactivée, absence de double soumission en attente, tooltip obligatoire.
- `e2e/specs/interaction-group1.spec.mjs` : cinq routes principales et Découvrir visiteur, chargement CSS/JS F1/F2 dans les deux shells, recherche Découvrir toujours GET et propriétaire, CTA et liens communs, formulaires Now toujours natifs, actions Moi et Mark, cible tactile compacte.

### Tests existants obligatoires

- Tests Web Now/Ongoing/Discovery/Me/Mark, E2E clavier, navigation, recherche, partage, états et permissions.
- Tests Flutter principaux de ces surfaces, `action_controls_test.dart`, `interaction_primitives_test.dart`, `interaction_f2_test.dart`, couverture de présentation/semantics et golden tests pertinents.
- Les screens doivent conserver leur aspect en clair/sombre, 390 px, 768/1199/1200+ CSS px selon contrats, grand texte et reduced motion.
- Le serveur reste propriétaire des autorisations, accès et mutations. Aucune migration de base ni nouveau service métier.

**Validation obtenue dans ce chantier :** inspection du code réel et diff GitHub ; vérification de la présence des primitives partagées sur toutes les entrées Web et les six fichiers Flutter impliqués.  
**Validation à constater depuis les jobs GitHub :** formatage officiel Dart, analyseur Flutter, exécution des tests, E2E et captures visuelles. Ne pas déclarer le Groupe 1 « CI verte » avant la fin des checks requis.

## 6. Sortie du lot

La **migration de présentation du Groupe 1 est réalisée** sans convertir les surfaces en tableaux de bord et sans dupliquer les styles applicatifs. La sortie définitive du lot exige néanmoins les gates runtime : aucune régression de l'identité actor, des URL/retours, du rendu compact, des outils de recherche, des autorisations et des parcours de confirmation. En cas de CI rouge, corriger l'origine, jamais les assertions de couverture pour obtenir du vert.

Le Groupe 2 concerne ensuite les **pages secondaires** et le Groupe 3 les **profondeurs N1/N2/N3/Space**, sur **la même branche #522** selon la décision du projet.


## 7. Garde-fou continu et verrouillage des dépendances

- `scripts/check_group1_interactions.py` vérifie statiquement que les huit templates du Groupe 1 utilisent les commandes communes, que les six fichiers Flutter principaux consomment `action_controls.dart`, que les deux shells Web chargent F1/F2 et que le CSS spécifique Moi ne redéfinit pas les boutons partagés.
- Le job `django` de `.github/workflows/ci.yml` exécute ce garde-fou **avant npm ci et le build**, pour fournir une preuve indépendante de la génération des assets.
- Le blocage Flutter `flutter pub get` identifié avant le Groupe 1 provenait d'un `mobile/pubspec.lock` non synchronisé avec les dépendances déjà déclarées dans `mobile/pubspec.yaml`. Le verrouillage a été synchronisé **à partir du diff exact** de Flutter 3.47.3 (cinq hunks, 104 lignes ajoutées, aucune version déclarée modifiée). Le blob résultant correspond au SHA du verrouillage généré dans le runner.
- Cette correction de lockfile permet de dépasser le premier gate Flutter, mais **ne garantit pas** que l'analyseur, le formatage Dart, les tests et les goldens soient verts. Le contrôle de la CI réelle reste obligatoire.

Le garde-fou interdit la réintroduction de styles locaux de boutons sur les cinq entrées ; il ne remplace pas les tests fonctionnels des propriétaires et n'étend pas son champ aux groupes secondaires.
