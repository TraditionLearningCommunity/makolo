# Space / Nous — checkpoint A, réconciliation du 31 octobre 2026

Base examinée : `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f`. Branche de travail : `feat/space-nous-mature-20261031`.

## Sources et règle

Code et tests du `main` prioritaires sur les contrats. Références : `docs/architecture/makolo-domain-blueprint.md`, `Makolo_Space_Specification_Consolidee.md`, `space-ux-experience-specification.md`, contrats Moi/Nous des 6 et 10 octobre 2026, Behavior, Mobile, Presentation et Golden. Ce checkpoint documente des écarts constatés, **pas des fonctionnalités livrées**.

## Inventaire court

| Surface | Existe | Fonctionne (preuve limitée) | Écart constaté | Propriétaire | Priorité |
| --- | --- | --- | --- | --- | --- |
| Projection Nous | Oui, `organizations/api/space_us_projection.py` | Génère identité, équipe bornée, responsabilités, ownership, trust et handoffs | Pas de Passeport collectif, relations ni ressources dans la racine ; identité limitée selon scope | Organizations / Sharing / owners | P1 |
| API Nous | Oui, `SpaceUsAPIView` | Authentification, `workspace_spaces`, no-store | Cet endpoint privé n'est pas la projection de consultation publique ou de membre sans Mandate | Organizations / Authorization | P0 |
| Navigation Flutter Nous | Oui, `mobile/lib/features/space/space_shell_routes.dart` | `space.us`, snapshots, refresh, navigation handoff | Racine de sections en liste ; des liens demandent vérification des routes réelles | Mobile / Presentation | P0 |
| Projection relations | Oui, `space_relationships_projection.py` | Sources Teams, Groups, CRM et Partners sous permissions distinctes | Examiner les profondeurs natives et les états masqués vs vides | Owners / Organizations | P1 |
| Shell et stockage Space | Oui, `space_repository.dart` | Source `space.us`, `StoredProjection`, fraîcheur | Contrôler révocation, séparation par Profile/Space et media local-first | Mobile / Sync | P0 |
| Passeport collectif | Contrat blueprint | Non validé à ce checkpoint | Examiner les builders, formats, variantes, export et routes avant adaptation | Sharing / Trust | P1 |
| Web Nous | Travaux historiques présents | Non validé à ce checkpoint | Comparer destinations Web et Flutter | Organizations / Web | P1 |

Ne pas confondre absence de membre autorisé à être affiché et équipe vide. Ne pas élever une Membership ou Assignment en Permission.

## Collisions

- PR #522 ouverte, HEAD observé `9001db777076811f06031639b6e431c28dee14f2` : modifications massives de `mobile/lib`, medias, local-first, Moi et navigation. Ne pas réécrire ces composants partagés en parallèle.
- Branches historiques `ws4-space-us-relations-pilot-web`, `feat/space-relations-pilot-mature`, `mobile/space-local-first-sync` existent ; existence de branche ≠ chantier actif. Vérifier diff et PR avant réemploi.
- Ce checkpoint ne change aucune API, migration ni permission.

## Checkpoints d'exécution

### B — Contrat de consultation et sécurité
1. Cartographier les routes publiques Space existantes et la représentation Passport collective ; **ne pas** ouvrir `SpaceUsAPIView` au public par simple suppression du filtre.
2. Définir un handoff vers une projection publique déjà disponible, ou introduire un selector public strictement borné si réellement manquant, séparé du contexte opérateur.
3. Tests serveur : visiteur, authentifié hors Space, membre sans autorité, Activity-only, Mandate Space, admin, révocation, IDOR et champs privés.

### C — Racine Nous et profondeurs
1. Tracer chaque handoff serveur vers route Web et GoRouter réellement enregistrées ; supprimer les CTA sans destination.
2. Composer identité collective d'abord, organisation et responsabilités pertinentes ensuite, puis relations/ressources seulement si faits autorisés et destination owner.
3. États vides locaux par section, aucune section artificielle. Tests Compact/Medium/Wide et retour arrière.

### D — Passeport collectif
1. Réutiliser le moteur Sharing/Passport et génération PDF existants.
2. Vérifier variantes, preuve, titres émis, média autorisé, partage et export; pas de reconnaissance juridique implicite.
3. Tests de divergence public/membre/admin, sortie documentaire et révocation.

### E — Local-first et qualité
1. Partir des snapshots existants (et de la réconciliation #522), ne pas créer un second kernel Space.
2. Tester cold start, changement de Profile/Space, refus explicite, cache d'image, hors réseau, retrait et révalidation d'actions sensibles.
3. Vérifier Web + Flutter sur les mêmes fixtures. Exécuter ciblés puis gates CI. Ne jamais merger avec CI rouge.

## Décision d'intégration

Ce checkpoint A est **documentaire seulement**. B, C, D et E ne sont pas déclarés réalisés. Avant code, vérifier le HEAD courant et réconcilier les fichiers communs contre #522. Branche dédiée, PR non fusionnée.
