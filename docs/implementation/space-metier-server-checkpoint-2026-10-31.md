# Space Métier — checkpoint serveur sur PR #522 (31 octobre 2026)

## Source vérifiée
- Dépôt officiel : `TraditionLearningCommunity/makolo`.
- Base `main` observée : `d0f0ec421c94c255fa4c0acd3509938a70c6322f`.
- Branche de travail unique : `fix/discover-a-continuation-context-20261014` / PR #522.
- #528 fermée sans merge, diagnostic Nous déjà présent dans `docs/implementation/space-nous-checkpoints-2026-10-31.md`.
- Le chantier Space Métier utilise `organizations/api/space_work_projection.py`, `organizations/api/space_work_views.py`, `organizations/space_product.py` et leurs tests existants. Aucune nouvelle vérité persistante ni nouvel endpoint introduit.

## Correction de domaine de présentation intégrée
Les sections `requests` étaient limitées par `space.archetype == education` ou `service_provider` alors même que les droits Activity correspondants et les propriétaires Journey/Services autorisaient la consultation. L'archétype ne doit définir que le langage et l'ordre de présentation, non bloquer un vertical réellement utilisé.

Le serveur dérive désormais l'exposition de `requests` exclusivement des Activity visibles et des capacités `ACTIVITY_REQUESTS_VIEW` / `ACTIVITY_SERVICES_CASES_VIEW_*`; les requêtes Services restent soumises au selector `service_journeys_visible_to(profile)`. Les autres sections ne changent pas de propriétaire métier. La sélection et la pagination continuent à appliquer le périmètre Activity / Space.

## Tests ajoutés, exécution locale en attente
- Un Space générique ou communautaire détenant une activité mixte doit afficher les inscriptions et dossiers de service autorisés dans `requests`.
- Le test vérifie aussi que l'e-mail du bénéficiaire n'est pas divulgué.
- Contrôle recommandé : `python manage.py test organizations.test_zs3_space_work_api` avec l'environnement Django approprié.

## Reste à traiter, non déclaré réalisé
- Vérifier toutes les transitions/action endpoints propriétaires et les véritables destinations N2/N3 avant d'ajouter des capacités dans la projection.
- Vérifier les routes de transport/véhicules réellement exploitables : les liens actuels sont vides, donc pas d'action inventée.
- Vérifier les états de couverture réels; ne pas présenter un owner partiel comme complet par défaut.
- Vérifier l'IDOR, les Mandates (Space et Activity), les révocations et permissions de ressources/médias dans des parcours de bout en bout.
- Refaire une vérification récente du HEAD et des changements concurrents avant les fichiers partagés.
- L'utilisateur exécutera Django et Flutter localement. La CI n'est pas un prérequis d'avancement demandé ici, mais aucun merge n'est effectué.

## Frontières
Pas de composition Web ou Flutter dans ce checkpoint. Pas de modification de `main`, pas de migration, pas de suppression ou affaiblissement de test.
