# LP6 — Vérification finale du langage produit (Web, Flutter, projections, données)

**Date :** 4 novembre 2026
**Véhicule unique :** PR [#522](https://github.com/TraditionLearningCommunity/makolo/pull/522), branche `fix/discover-a-continuation-context-20261014`.
**Statut :** corrections LP6 poussées ; certification d'exécution **non attestée**. Aucun merge ni déploiement.

## 1. Objet et principe éditorial

LP6 **ne refait pas LP1–LP5**. Il vérifie les contrats déjà installés et les régressions introduites par les commits ultérieurs.

Un texte n'est jamais jugé à sa longueur : il peut rester court, devenir plus développé ou rester inchangé. La bonne mesure est sa capacité à rendre intelligibles le contexte, le prochain geste, l'incertitude et les conséquences, sans répétition artificielle et sans réduire la voix de Makolo à un vocabulaire mécanique. Les textes originaux des porteurs ne sont pas réécrits.

**Frontières :** Presentation n'invente aucun fait ; `UNKNOWN` ne devient jamais `FALSE` ; Access, Permission, Mandate, Payment et Readiness demeurent aux domaines propriétaires ; une fiche démonstrative ne devient pas une offre réelle par son titre naturel.

## 2. Reconciliation depuis LP5

Après le checkpoint LP5 `ffa854267ed649d05d8e8356d4ff167ed668a42d`, **57 commits** existaient déjà sur #522 lors de la première comparaison LP6, essentiellement autour des générateurs de démonstration et de Discovery. Les générateurs avaient remplacé les titres artificiels `Exemple — …` par des titres naturels, mais les tests `core/test_demo_seed.py`, le validateur `demo_seed/mobile_mature_validation.py` et `docs/demo-data.md` exigeaient encore le contraire.

**Correction :** le titre reste naturel et reconnaissable par son contenu ; la provenance synthétique reste dans les références de seed et l'environnement de démonstration. Les OpportunitySource indicatives ne sont ni marquées officiellement vérifiées ni présentées comme confirmation de l'existence d'une candidature fictive. La fonction `_demo_title` accepte les anciens titres pour une reprise idempotente sans réafficher le préfixe.

Le texte des activités du jeu mobile n'est plus une même phrase appliquée indistinctement à Event, Transport, Service et Funding. Les summaries des opportunités fictives utilisent leur titre et l'état du scénario, sans attribuer de démarche privée à un lecteur public ni annoncer de candidature réelle.

## 3. Matrice de contrôle des surfaces (revue statique)

| Surface | Web — base relue | Flutter — base relue | Verdict de revue |
| --- | --- | --- | --- |
| Maintenant personnel | `templates/core/participant_home.html`, `core/home_presentation.py`, `core/api/personal_projections.py` | `mobile/lib/features/now/now_screen.dart` | Copie source et branches « tout en ordre » / partial / unavailable distinctes dans le code ; **E2E non exécuté** |
| En cours personnel | `templates/core/_participant_ongoing_content.html` | `mobile/lib/features/ongoing/ongoing_screen.dart`, `ongoing_presentation.dart` | Présence des états manque de snapshot / chargement / erreur / liste ; **E2E non exécuté** |
| Découvrir | `templates/discovery/home.html`, `discovery/api/composition.py` | `mobile/lib/features/discovery/discovery_mature_view.dart` | Intention, filtres, carte et présentation de l'inconnu vérifiés en source ; **E2E non exécuté** |
| Space / Maintenant, Métier, Découvrir, Nous | `templates/organizations/space/{now,work,discover,us}.html` | `mobile/lib/features/space/{space_us_surface,space_work_surface}.dart` | Corrections de jargon Web « Décision dans le métier », « Aperçu borné » ; **parité comportementale non certifiée** |
| Projections et messages dynamiques | `core/participant_action_presentation.py`, `core/api/personal_projections.py`, `discovery/api/composition.py` | Adaptateurs consommateurs | Aucune nouvelle vérité persistée ; faits, dates, refus, statuts et permissions restent propriétaires |
| Démonstration | `demo_seed/{beta,mobile_mature_universe,obtention,mobile_mature_validation}.py`, `scripts/demo_generation/editorial.py` | Projection par API, sans modèle de démo parallèle | Titres naturels, provenance interne conservée, candidature fictive non certifiée ; **reseed DB non exécuté** |

Cette matrice atteste la **lecture de sources**, pas un parcours utilisateur ni un résultat d'exécution.

## 4. Changements LP6

- Réconciliation des assertions bêta et du contrôle de corpus mobile avec la politique de titres naturels.
- Rectification de `docs/demo-data.md` pour empêcher la résurgence de l'ancienne règle de préfixes.
- Amélioration des descriptions synthétiques Event, Transport, Service et Funding par domaine et contexte ; les informations absentes ne deviennent pas des promesses.
- Summaries des candidatures synthétiques contextualisées par `relation`, sans copie uniformément mécanique, sans identité privée et sans offre réelle présumée.
- Tests ciblés ajoutés sur le contenu et les deux chemins de provenance.
- Deux corrections Web isolées sur Space, sans refonte des écrans.

**Pas de modèle, migration, endpoint, permission, changement de donnée réelle ou nouvelle PR.** Le code Flutter n'a pas été modifié ; sa mise en forme canonique ne peut donc pas être revendiquée comme exécutée sur cette passe.

## 5. Exécution / preuve

La session de travail a accès aux sources et à l'historique GitHub, mais ne dispose pas d'un checkout exécutable du dépôt ni du runtime Django/Flutter. Aucune commande de test locale n'a été exécutée ici. Ne pas confondre tests présents et tests réussis.

Observation CI historique lors de la revue : workflow **Demo generation validation** réussi sur le commit `25cd222b11…` (run `41737627654`), tandis que **Now Presentation Goldens** et **Mobile CI** échouaient sur ce même ancien commit (runs `41737628077` et `41737627697`). Les logs anciens montrent notamment un problème `unawaited` dans `now_screen.dart`, alors que le HEAD relu contient `import 'dart:async';`. **Ces runs ne certifient ni n'invalident les corrections LP6 ultérieures.** Vérifier les runs du HEAD courant avant intégration.

### Vérifications ciblées à exécuter sur le HEAD courant de #522

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_product_language core.test_lp5_language_sources core.test_demo_seed core.test_now_composition
python manage.py test discovery.api.test_projections discovery.api.test_mature_discovery
python -m unittest scripts.demo_generation.test_cli
```

```bash
cd mobile
bash tool/dart_format.sh check
flutter analyze
flutter test test/now_selector_test.dart test/now_screen_test.dart test/ongoing_presentation_test.dart test/ongoing_screen_test.dart test/discovery_mature_selector_test.dart test/space_us_surface_test.dart test/space_work_surface_test.dart
```

Le reseed, lorsqu'il est requis pour constater la rédaction des fiches, se fait **uniquement sur une base de démonstration isolée, avec sauvegarde et date explicite**, puis avec `validate_makolo_demo` et `assert_mobile_mature_demo_coverage`. Ne jamais effectuer cette opération sur des données réelles.

## 5 bis. Vérification d'exécution et audit des résultats CI (4 novembre 2026)

### Preuve de test local transmise par l'opérateur

Commande (environnement Windows, `python manage.py test`) :

```text
python manage.py test core.test_product_language core.test_lp5_language_sources core.test_demo_seed core.test_now_composition
Found 23 test(s).
System check identified no issues (0 silenced).
Ran 23 tests in 65.813s
OK
Destroying test database for alias 'default'...
```

Les scénarios bêta exécutés dans ce lot ont notamment validé un ensemble de **125 Activities mobile mature**, **125 Occurrences**, **25 unités par verticale**, **454 Resources**, **228 fichiers** et **40 Journeys** pour le persona de référence. Le rapport a été émis plusieurs fois lors des tests de génération et de reprise ; ce n'est pas une multiplication des données. Le SHA du checkout local n'était pas présent dans la sortie fournie : cette preuve **n'atteste pas à elle seule** le HEAD distant.

### Historique CI et vérification des causes

- `main` a été vérifié à `d0f0ec421c94c255fa4c0acd3509938a70c6322f` ; à la date du contrôle, une seule PR ouverte était #522.
- Le run CI `41737627603` sur `25cd222b11…` échouait sur le contrôle de synchronisation des artefacts `static/dist/makolo.css` et `makolo.js`. Les versions compilées ont depuis été mises à jour par les commits `a9e0870c77fa` et `b35500bf62fb` respectivement. Seule une nouvelle exécution pourra certifier leur adéquation aux versions et dépendances actuelles.
- Les workflows Flutter `41737627697` et `41737628077` sur ce même ancien commit échouaient lors de la génération / compilation. L'erreur visible `unawaited` dans `mobile/lib/features/now/now_screen.dart` a fait l'objet du commit `ab6c46c972aa` (import `dart:async`), présent dans la branche actuelle.
- Le test Subscription qui échouait parce que la réponse ne comportait pas `funded` a été suivi du correctif `46e83570cd26` dans `subscriptions/coverage_native_api.py`, conservant les lignes strictement rattachées au payeur. Les autres échecs Abonnements de l'ancien run restent à certifier par une nouvelle exécution.
- Le run Conversations PostgreSQL `41737627995` signalait d'anciennes assertions sur « 1 pour vous » et « Tout est en ordre ». Le test actuel `conversations/test_j4_experience.py` attend désormais « 1 à traiter » et « En cours ailleurs » après le commit `a9ad4c8e89af`. Une nouvelle exécution est nécessaire pour attester que la sémantique et la continuation restent correctes.
- Le workflow de validation des générateurs de démonstration `41737627654` était **vert**, mais lui aussi sur `25cd222b11…`, antérieur à LP6.
- Aucun run de CI sur le HEAD LP6 vérifié au cours de cette session n'a pu être attesté. L'environnement de travail ne dispose pas d'un checkout Django/Flutter exécutable et les outils GitHub disponibles ne proposent pas de `workflow_dispatch` direct. La tentative de déclenchement via navigateur connecté n'a pas démarré faute de crédit disponible dans ce navigateur ; aucun nouveau run n'a été lancé.

### Conséquence de release

**Les 23 tests ciblés LP6 sont réussis sur le checkout local de l'opérateur ; aucune certification CI du HEAD courant n'est acquise.** Ne pas fusionner. Les échecs de l'ancien SHA sont documentés et une partie a déjà reçu des correctifs, sans preuve d'exécution post-correctif.

## 6. Décision et critères de fermeture

**LP6 : changements de code réalisés ; 23 tests ciblés exécutés et réussis localement ; certification générale CI/Web/Flutter non attestée.**

Fermeture finale uniquement lorsque :
1. les tests ciblés Django/Flutter et l'analyse Flutter passent sur le HEAD actualisé ;
2. les flux Web/Flutter réels distinguent correctement chargement, inconnu, refus, attente et réussite confirmée ;
3. un seed isolé et sa validation conservent provenance, idempotence et absence de faux faits réels ;
4. les workflows requis de #522 sont verts sur le commit candidat et les éventuelles collisions sont réconciliées ;
5. aucun texte authentique n'est raccourci ou remplacé par une formule générique sans motif documenté.

Ne pas merger sur un statut CI rouge ou non vérifié.
