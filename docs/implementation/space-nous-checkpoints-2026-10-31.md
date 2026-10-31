# Space / Nous — S0 : réconciliation sur la PR #522

**Périmètre** : Nous uniquement. Le Passeport (Sharing, émission, PDF, partage, variantes) appartient à un autre chantier et n'est pas modifié ni planifié ici.

## Références vérifiées le 31 octobre 2026

- Dépôt : `TraditionLearningCommunity/makolo`
- Base de la PR : `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f`
- HEAD examiné de la PR #522 : `085eb5b39cdf563da22b127bef40fb39678f46db` (susceptible d'évoluer après ce commit)
- Branche unique : `fix/discover-a-continuation-context-20261014`
- 359 chemins modifiés dans #522 à la réconciliation ; vérifier à nouveau avant une écriture future.
- La PR #528 a été fermée sans merge. Son document de diagnostic a été transféré dans #522.
- Travail S0 documentaire uniquement ; pas de migration, modification d'API, mutation de permissions, changement Flutter ni exécution de tests/CI.

## Matrice de propriété et collisions

| Surface / fichiers | Situation vérifiée | Responsable | Statut pour Nous |
| --- | --- | --- | --- |
| `organizations/api/space_us_projection.py` | Projection existante dans main ; identité, team, responsibilities, ownership, trust, handoffs ; non listée parmi les chemins modifiés de #522 | Organizations / Nous | Propriétaire direct ; évolution possible après revue de contrats |
| `organizations/api/space_zs4_views.py` | `SpaceUsAPIView` privé via `workspace_spaces` et `Cache-Control: private, no-store` | Organizations / Authorization | Propriétaire de l'API privée ; préserver le contrôle serveur |
| `organizations/api/space_relationships_projection.py` | Projection existante avec Teams, Groups, CRM, Partners sous permissions | Organizations + propriétaires des relations | Propriétaire des read models Nous, pas des données métier |
| `organizations/api/public_space_views.py`, `organizations/test_public_space_api.py` | Modifiés sur #522 ; projection publique déjà présente | Organizations / Guest | **Partagé en évolution** ; lire avant modification, ne pas confondre public et opérateur |
| `organizations/api/space_work_projection.py`, `organizations/test_zs3_space_work_api.py` | Modifiés sur #522 ; checkpoint Métier distinct documenté | Space Métier | Hors propriété Nous ; seulement handoffs vers Métier |
| `mobile/lib/features/space/space_shell_routes.dart` | Surface native Nous et racines Space existantes ; pas de modification listée dans #522 au moment du scan | Space UX Flutter | Propriétaire UI Nous, mais cohabite avec Now/Discover/Métier |
| `mobile/lib/features/space/space_repository.dart` | Sources `space.us`, `space.relationships`, snapshots ; pas de modification listée dans #522 | Space mobile | À réutiliser ; inspecter source, révocation et profile isolation avant changement |
| `mobile/lib/features/guest/public_space_screens.dart` | Modifié dans #522 | Guest / Public | Partagé ; ne pas détourner la surface publique pour l'opérateur |
| `mobile/lib/data/local/profile_store.dart`, `mobile/lib/sync/sync_engine.dart`, `mobile/lib/sync/projection_contract.dart` | Modifiés dans #522 | Kernel local-first transverse | **Zone rouge de collision** ; aucune réécriture depuis Nous sans contrat explicite |
| `mobile/lib/navigation/avatar_sheet.dart`, `shell_header.dart`, `deep_link_resolver.dart`, `incoming_intent.dart` | Modifiés dans #522 | Navigation globale | **Zone rouge de collision** ; privilégier routes propriétaires |
| `sharing/**` et migrations Sharing de #522 | Nombreux fichiers modifiés | Chantier Passeport séparé | **Exclus** de Nous, aucune intervention |
| `accounts/migrations/0009_profile_visibility_policies.py`, `services/migrations/0005_service_start_operation_fingerprint.py`, `presentations/migrations/0005_presentationmediause.py`, `0006_private_presentation_assets.py`, `sharing/migrations/0006_passport_issued_public_and_sharing.py`, `topics/migrations/0005_profile_publishable_defaults.py` | Migrations additives figurant parmi les changements de la PR #522 | Domaines respectifs | Aucune migration Nous justifiée en S0 |
| `authorization/` | Selectors et Mandates canoniques existants ; aucun chemin modifié de ce répertoire dans le scan #522 | Authorization | Consommation des capacités, aucune autorité inférée par UX |

La liste de fichiers est un inventaire GitHub de la PR, **pas** une validation fonctionnelle. Les tests n'ont pas été exécutés ici.

## Écarts structurants à examiner après S0

1. L'API `space.us` est une lecture opérateur privée ; elle n'est pas la même vue que la consultation publique existante. La présence dans Team/Group ne doit pas être interprétée comme Mandate.
2. L'identité Nous et l'équipe peuvent être présentées avec une autorité limitée. Distinguer contenu absent, masqué et inconnu.
3. Chaque handoff Nous doit être relié à une vraie route native Flutter et à une destination Web utilisable, sans renvoi interne vers le Web depuis Flutter.
4. Le local-first propriétaire Space doit utiliser la persistance/synchronisation commune avec isolation et révocation ; aucun nouveau noyau.
5. Aucun travail sur le Passeport : sa représentation et son export seront traités indépendamment.

## Séquence décidée pour la suite (sans exécution dans ce commit)

- **S1** : visibilité, autorité et projections Nous, avec tests serveur ciblés.
- **S2** : racine Nous Web/Flutter, identité collective et hiérarchie de présentation.
- **S3** : organisation, équipe, groupes, responsabilités et destinations propriétaires.
- **S4** : relations et capital collectif owner-backed, sans doublons métier.
- **S5** : routes, handoffs, comportement natif, local-first et révocation en coordination avec les composants communs déjà touchés par #522.
- **S6** : validation fonctionnelle et visuelle ciblée ; l'utilisateur effectue les exécutions Django/Flutter locales. Pas de CI demandée pour avancer.

**Critère de sortie S0** : matrice propriétaire/partagé consignée, collisions identifiées, périmètre Nous séparé du Passeport, aucune modification de comportement.
