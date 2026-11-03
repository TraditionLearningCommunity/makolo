# MT1–MT8 — Réconciliation CI sur PR #522

**Date :** 4 novembre 2026.  
**Dépôt :** `TraditionLearningCommunity/makolo` ; **branche unique** `fix/discover-a-continuation-context-20261014` (**PR #522**, non fusionnée).  
**Portée :** fermeture Métier Space (8 archétypes) et dépendances bloquantes sur la même PR.

## Statut prouvé

Les derniers jobs GitHub Actions visibles pour cette branche se rapportent au **SHA historique `25cd222b11a6c0044097b3cfeee7018005f9fb67`**, et non aux correctifs ci-dessous. Ils ne peuvent **pas** servir de validation verte/rouge du HEAD courant. Les derniers jobs visibles à ce SHA étaient :

| Contrôle | Verdict historique | Cause observée |
| --- | --- | --- |
| Mobile CI / Mobile DEV APK | rouge | `build_runner` : `conversation_screens.dart` ligne 934, parenthèse incorrecte sur l'ancien commit de fusion |
| Now Presentation Goldens | rouge | erreur de compilation : `unawaited` manquant dans `now_screen.dart` |
| CI Django / E2E | rouge | `static/dist` non synchronisé après `npm ci && npm run build` |
| Conversation PostgreSQL | rouge | copies d'interface J4/J6 modifiées sans compatibilité des parcours attestée |
| Subscription catalog runtime | rouge | réponse API `funded` absente des clés de collection |
| Subscription concurrency | rouge | `serialized_rollback=True` restaure des `ContentType` déjà créés par `post_migrate` |
| API Contract, Security, Mobile Visual Golden, PostgreSQL core (identity/services), Funding, Recognition | vert à ce SHA | **Seulement historique ; ne certifie pas le HEAD** |

## Corrections source committées sur #522

- `mobile/lib/features/now/now_screen.dart` : import `dart:async` réel pour `unawaited`. La syntaxe `conversation_screens.dart` à l'origine du build_runner rouge a été corrigée par des commits déjà présents sur #522 avant cette réconciliation ; ne pas ajouter une réparation factice.
- `static/dist/makolo.css`, `static/dist/makolo.js`, `static/dist/scanner.js` : application **exacte** du diff du build production CI. Empreintes Git vérifiées contre le runner : `29f9e7c...`, `d784905...`, `0ccc8ae...`. Aucun ignore du contrôle artefact.
- `subscriptions/coverage_native_api.py` : conserve les deux représentations `financed` (actuelle) et `funded` (compatibilité du contrat), toutes deux tirées **du même queryset déjà autorisé**, sans nouvelle divulgation des bénéficiaires.
- `templates/conversations/_point.html` : action de Form explicite `Compléter le formulaire` sur la vraie route Questionnaire propriétaire.
- `subscriptions/test_lot5_team_concurrency.py` : retire la sérialisation complète de la DB test, source du doublon `ContentType`, et réensemence uniquement les rôles système/FeatureDefinitions **depuis les fonctions des migrations canoniques** après flush. Le scénario de verrouillage PostgreSQL, les deux workers, les assertions `admitted/limited` et l'unicité du siège ne sont ni supprimés ni affaiblis.
- `mobile/lib/features/space/space_work_surface.dart` : état vide partiel explicite, compatible avec la couverture mandatée ou la limite d'aperçu ; il ne déclare jamais que l'Espace entier est vide.

## Gate MT dédié

Le nouveau workflow `.github/workflows/space-metier-mt.yml` sépare :
1. **PostgreSQL** : `manage.py check`, `makemigrations --check --dry-run`, et suites `organizations.test_space_work_mt2` à `mt7`, créations natives, opérations, G2/G3/G4, WS3 et ZS3.
2. **Flutter** : dépendances verrouillées, `build_runner`, politique de code généré, format canonique, `flutter analyze`, et six tests Work G1–G4 + composition MT7/8.

Cette CI couvre la sortie du programme MT sans importer le succès d'autres domaines ni reproduire un audit de conception. Les contrôles existants `CI`, `Mobile CI`, `API Contract` et `Mobile DEV APK` restent en vigueur, sans désactivation ni condition artificielle.

## Critère final et limitation d'exécution

**Le code de correction est poussé, mais le gate CI courant n'est pas encore vérifié.** Les connecteurs GitHub exposent des exécutions anciennes sans nouvelle exécution liée au HEAD actuel malgré les pushes. Il n'a pas été possible de lancer ici un `workflow_dispatch` sur ce SHA : le connecteur GitHub n'offre que la consultation et la relance d'anciens run IDs, pas un dispatch arbitraire du HEAD, et le runtime local n'a ni checkout GitHub ni SDK Flutter. On ne substitue pas un ancien rerun ni un statut « vert » non prouvé.

**Aucun merge et aucune modification directe à `main`.** La PR #522 reste la surface de finalisation. Ne pas fusionner si un gate obligatoire reste rouge. Corriger les futures erreurs au module propriétaire concerné, sans supprimer les tests ni créer MT9.
