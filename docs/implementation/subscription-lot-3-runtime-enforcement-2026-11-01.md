# Subscription — Lot 3 : enforcement dans les propriétaires métier

**Périmètre** : PR #522, branche `fix/discover-a-continuation-context-20261014`.
**État** : code ajouté dans les propriétaires existants ; aucune nouvelle Feature, Plan, table, migration ou vérité d'usage. Tests ciblés versionnés, exécution non attestée dans cette session.

## Contrat d'exécution

| Feature publiée | Domaine propriétaire | Point d'enforcement | Sémantique |
| --- | --- | --- | --- |
| `activities.create` | Activities | `activities.services.create_activity` | `resolve_entitlement(space ou owner_profile, code).allowed` ; vérification avant l'INSERT ; jamais l'entitlement personnel du collaborateur à la place de celui de l'Espace |
| `team.members` | Organizations | `organizations.team_entitlement.require_team_member_capacity`, appelé par admissions canoniques, secondaires et compatibilité legacy | Compte live des Profils actifs DISTINCTS via `organizations.active_team_members` ; verrouillage de l'Espace pour admissions canoniques ; blocage d'une nouvelle personne si la capacité configurée est atteinte ; préservation des personnes existantes et des réaffectations |
| `custom_roles` | Authorization | `authorization.services.create_custom_space_role` | L'autorité de gouvernance et l'Entitlement de l'Espace sont tous deux indispensables à la création d'un Role non système ; aucune Permission ni Mandate implicite |

## Décisions canoniques

- Une absence de valeur numérique `team.members` dans `space.base` **n'est pas** une limite commerciale zéro : aucune limite chiffrée n'est inventée. Le quota est appliqué s'il est effectivement défini par BASE/ADDON/GRANT.
- La limite bloque les **nouvelles admissions distinctes**, pas l'édition d'un membre actif, son appartenance à plusieurs Teams, sa sortie, ni les données déjà conservées au-dessus du quota. Les flux legacy actifs sont protégés avant la projection.
- La suspension d'une Subscription comportant une Feature définie peut interdire une acquisition nouvelle selon le resolver canonique. Aucun composant Flutter ne recalcule ces décisions.
- Un Space et le Profil de l'agent sont des sujets indépendants. Assignment, Membership et Team n'attribuent ni Entitlement ni Mandate.
- `custom_roles` n'est pas aujourd'hui proposé par une route de création publique : on protège le service métier pour l'usage futur **sans inventer de formulaire ou d'API**. Le service normalise les permissions Espace, rejette les permissions que l'acteur ne détient pas et ne crée pas de Mandate.
- Les anciens Role, SubscriptionItem et TeamMembership restent des faits valides lors d'une réduction de formule. Aucun backfill ou effacement n'est introduit.

## Tests ciblés enregistrés

- `subscriptions/test_lot3_enforcement.py` : sujet Activity, quotas absents/configurés, refus d'admission legacy, réaffectation, suspension, création de rôle avec autorité et entitlement.
- `subscriptions/test_lot3_feature_consumers.py` : contrôle indépendant des limites et de l'isolement, gestion de rôles sans Mandate implicite, validation du service canonique.
- `subscriptions/test_lot3_feature_policy.py` : vraie BASE publiée avec `activities.create=False` (et non un GRANT False sur agrégation BOOLEAN_OR), composition des permissions de rôle sans délégation implicite.
- Tests domaine existants préservés : `activities/tests.py`, `organizations/test_task28_teams.py`, `organizations/test_team_responsibilities.py`, `authorization/tests.py`, `subscriptions/test_s2_runtime.py`.

**À contrôler lors de l'exécution ciblée** : transactions sur PostgreSQL, double admission concurrente sous quota, refus via POST Web/API, propagation d'erreurs domaine et absence de dédoublement d'un Role ou d'un Mandate.

## Limite d'attestation

Cette session opère par GitHub distant et ne possède pas une copie exécutable du dépôt. Les tests et contrôles de concurrence sur PostgreSQL ne sont donc pas déclarés exécutés ; aucune CI n'est annoncée verte. Aucun merge dans `main` n'est autorisé par cette note.
