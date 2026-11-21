# Découvrir 2028 — journal d'exécution

Dépôt : `TraditionLearningCommunity/makolo` · branche de livraison : `fix/discover-a-continuation-context-20261014` · PR #522.

Ce journal suit la maturation du **produit déjà livré en code**, sans rouvrir artificiellement les chantiers Discovery 01–08. Il distingue réalisation, contrat propriétaire et validation en situation. L'expérience reste une exploration d'actions réelles, pas un feed, un back-office ou un client cartographique universel.

## 0 — Branche et collisions · TRAITÉ

- La PR #507 (`feat/platform-mature`) est déjà fusionnée depuis octobre 2026 : ne pas tenter de la rouvrir.
- #522 est la PR ouverte de livraison. Aucun changement sur `main`, aucune branche concurrente.
- Éviter les fichiers Métier, Space et couches globales non requis par Découvrir.
- Les changements sont de composition et de consommation, sans migration ni mutation métier.
- Les autres contributions peuvent faire avancer le HEAD ; toujours relire les blobs avant écriture.

## 1 — Propriétaires Django · PRÉSERVÉ

- Les propriétaires existants restent maîtres d'Activity, Occurrence, Services, Funding, Opportunities, Geography, Commerce, Journey, Sharing, Permission et Mandate.
- Aucun champ de prix, capacité, pertinence, disponibilité ou permission n'est ajouté dans Discovery à des fins visuelles.
- En contexte Space, `_space_read_only_items` demeure un garde délibéré : ne pas exposer des engagements personnels ni inventer une mutation collective.
- Pas de modèle `Possibility` ou `UniversalOpportunity`.

## 2 — API et projections · PRÉSERVÉ

- `discovery/api/composition.py` et `projections.py` restent l'unique composition Discovery.
- Les mêmes identités et critères fondent liste, carte et détail ; aucune API parallèle.
- N3 utilise les destinations propriétaires existantes.
- Aucun endpoint, migration ou classement client ajouté dans cette passe.

## 3 — Web N1, carte et N2 · CODE MODIFIÉ

- `templates/discovery/home.html` : liste et carte dans une même grille en écran large, modes compacts à icônes accessibles, résultats et états vides plus discrets.
- Le panneau historique `discovery/_preview.html` n'est plus monté : aucun geste actif ne l'alimentait. La fiche N2 reste la profondeur de consultation; le champ Web récupère toute sa largeur, même hors carte.
- `static/js/discovery-ux.js` : état actif visible de la bascule carte/liste ; le runtime cartographique existant garde la main sur caméra, sélection et affichage.
- `templates/discovery/_universal_card.html` : visuel publié en tête ouvrant N2, hauteur bornée, quatre faits utiles visibles avec ordre par famille, faits secondaires repliables et ressources en une seule divulgation. Le titre ouvre également le même N2 plutôt qu'une destination différente.
- `templates/discovery/_action_bar.html` : Save / owner / Sharing factorisés, avec commandes iconographiques accessibles. Aucun comportement de mutation déplacé.
- `templates/discovery/possibility_detail.html` : média agrandissable, transport sans photo présenté par le trajet réellement connu, informations structurées, Save et Sharing accessibles depuis N2 personnel, conditions formulées humainement.
- `templates/discovery/watch_list.html` et `watch_detail.html` : vues de Veilles moins administratives, résultats ouverts via les routes existantes et actions accessibles, suppression protégée par confirmation.
- Le partage des contrôles entre N1 et N2 évite de créer deux moteurs d'interaction. Le retour N2 → N1 utilise l'historique natif seulement lorsque le contexte exact d'origine correspond, sans sauvegarde privée dans le navigateur.
- `static/css/mature-experience.css` : disposition spatiale bornée, sans écraser les composants communs ni rogner les menus de partage.
- `discovery/views.py` : ordre de lecture des faits N1 Web par nature de l'opportunité, sans modifier l'admission ni le classement.

## 4 — Flutter · CODE MODIFIÉ

- `mobile/lib/presentation/possibilities/discovery_possibility_unit.dart` : visuel avant les faits, image bornée, galerie plus discrète, détails secondaires progressifs, retrait de l'explication technique sur les informations conservées.
- `mobile/lib/presentation/media/retained_public_discovery_image.dart` : adaptation du mode de remplissage de l'image, sans nouvelle source de rétention.
- `mobile/lib/features/discovery/discovery_mature_view.dart` : skeleton natif réutilisé pour une pagination en cours ; états sobres.
- `mobile/lib/features/discovery/discovery_screens.dart` : vocabulaire de recherche plus naturel et icône de réglage plutôt que métaphore magique.
- `mobile/lib/features/discovery/discovery_watch_screens.dart` : acquisition initiale représentée par un skeleton existant ; états vides et résultats formulés comme des opportunités.
- Le média N1 ouvre N2 ; le média N2 ouvre le Reader. Les quatre premiers faits sont utiles selon leur famille et les autres restent accessibles.
- Une image effectivement absente cesse d'afficher le squelette de chargement ; les copies publiques autorisées sont gardées par le mécanisme existant.
- Les médias publics first-party demeurent seuls concernés par la conservation automatique autorisée ; aucun téléchargement exhaustif de ressources privées.

## 5 — Profile, Space et actions · FRONTIÈRE CONSERVÉE

- Une même identité de possibilité et un même N2 ; pas de variantes de fiche par bénéficiaire/producteur.
- Save et Sharing personnels restent distincts des Veilles et engagements N3.
- Le Space reste en lecture collective tant qu'un propriétaire n'a pas explicitement reconnu un geste de bénéficiaire collectif. Ne pas contourner le gate serveur pour satisfaire un écran.
- Les expériences Métier et Operations restent propriétaires des travaux spécialisés.

## 6 — Finition et preuve de fonctionnement · NON CERTIFIÉ

- Code poussé sur #522 sans attestation d'exécution de Django, navigateur, Flutter, Android ou formatteur Dart dans cette session.
- Aucun test supprimé ou affaibli, aucune CI forcée, aucun déploiement revendiqué.
- Une validation visuelle et native restera requise avant de déclarer la qualité de production ; les problèmes CI externes à Découvrir ne deviennent pas automatiquement des défauts Discovery.
- Les composants à observer en priorité sont : affichage réel des médias, adaptation wide de la carte, N2 et Sharing Web, gestes Flutter, redémarrage et refus d'autorité.

## Contraintes permanentes

- Langage métier simple et calme. Aucune explication du cache, de la synchronisation ou des mécanismes serveur dans l'interface.
- Skeleton uniquement durant une attente réelle sans contenu utile ; une absence confirmée reste un vrai état vide.
- Icônes accessibles avec nom compréhensible ; les gestes sensibles gardent une conséquence claire.
- Unknown n'est ni gratuit, ni disponible, ni refusé.
- Conserver les composants et l'identité Makolo existants ; ne jamais redessiner le Makolo Mark.

## Relecture corrective du 13 novembre 2026 — revue du code, sans exécution

Les correctifs suivants ont été apportés sur la PR #522 à partir des fichiers effectivement consultés :

- `frontend/src/discovery-map.js` et `static/dist/discovery-map.js` : la carte ne déduit plus la position (0, 0) à partir de coordonnées `null`, vides ou hors bornes. Le code servi est aligné avec le source.
- `frontend/src/discovery-map.js`, `static/dist/discovery-map.js` et `static/js/discovery-ux.js` : l'absence de service de tuiles ou une erreur initiale déclenche un repli vers la liste. Une erreur de tuile une fois la projection cartographique initialisée n'interrompt plus systématiquement une carte utilisable.
- `templates/discovery/watch_list.html` : la pagination déjà possédée par Django (30 Veilles par page) possède désormais un moyen d'accéder aux pages suivantes.
- `mobile/lib/features/discovery/discovery_watch_screens.dart` : les pages de Veilles locales sont présentées avant rafraîchissement discret ; les flux sont séparés par Profile, Veille et page afin de ne pas montrer brièvement la projection précédente lors d'un changement de contexte.
- `templates/discovery/_action_bar.html` : les commandes absentes ne réservent plus de colonnes vides ; le geste N1 de consultation sans action propriétaire conduit au N2 canonique.
- `mobile/lib/presentation/possibilities/discovery_possibility_unit.dart` : suppression des commandes Save/Share inactives dans les situations où les conditions de présentation établies ne permettent pas de les offrir.

**Vérifications effectuées :** lecture des sources GitHub, de la composition serveur, des templates, du JavaScript source et servi, des contrats de widgets Flutter et de la navigation. Il ne s'agit pas d'une certification d'exécution.

**Non effectué :** test automatisé, CI, analyse Flutter, compilation Android, navigation réelle dans le navigateur, recette de permission réelle, merge ou déploiement.

**Reste à établir sur environnement réel avant certification :** rendu des styles après reconstruction officielle des assets, comportement MapLibre sur appareil, interactions et accessibilité en situation, gestion concurrente des changements d'acteur, gestes Save/Sharing et continuité N3 avec toutes les verticales. Ces points ne doivent pas être déclarés défaillants sans preuve d'exécution.
