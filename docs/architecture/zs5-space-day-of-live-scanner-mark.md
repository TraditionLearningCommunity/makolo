# ZS5 — Space Jour J, Live, Scanner & Makolo Mark

**Base auditée :** `main@ef1e0f5a25233cfe240588d42c5902cbdf70ebe9`  
**Branche :** `zs5-space-day-of-live-scanner-mark`  
**Portée :** composition UX serveur uniquement ; aucune migration, aucun template, aucun Flutter, aucun algorithme Molongo.

## 1. Collision audit

ZS5 a été ouvert après vérification du `main` courant et des branches ZS parallèles.

- ZS3 `zs3-space-work-archetype-projections` est basé sur le même `main` et touche surtout `organizations/api/space_work_*.py`, son test et deux lignes d'URL.
- ZS4 `zs4-space-us-relations-pilot-projections` est basé sur le même `main` et ajoute `organizations/api/space_us_projection.py`.
- aucune branche ZS2 nommée comme telle n'était visible lors de l'audit.
- ZS5 utilise donc des modules séparés. Le seul point de collision volontaire est l'ajout de la route Mark dans `organizations/api/urls.py`; ZS6 devra réconcilier ce fichier avec ZS3 avant intégration du train.

Le runtime gagne sur les plans historiques.

## 2. Owners réutilisés

ZS5 ne crée aucun owner métier.

| Surface | Owner / contrat réutilisé |
| --- | --- |
| Jour J opérateur | Activity/Occurrence + Operations `resolve_occurrence_live` |
| Readiness | Operational Readiness existante |
| Live | `operations/occurrence_live.py` et API Live existante |
| Capacity | Capacity selectors déjà consommés par Operations |
| Placement | Operations Placement |
| Queue | Operations Live Queue |
| Checkpoints | Operations Checkpoints |
| Access | Access, sans exposer AccessCredential |
| Scanner | Scanner + Access authority / AccessUse owner |
| Space actor | ZS1 `workspace_spaces()` / Mandates |
| Mark | orchestration sans persistance, handoff vers owners existants |

## 3. Jour J opérateur

Nouvelle projection :

```text
GET /api/v1/operations/occurrences/<occurrence-id>/day-of/
projection = space.occurrence.day_of
scope = space
```

Jour J reste strictement attaché à une Occurrence canonique. La projection ne crée ni `DayOfState`, ni identifiant secondaire, ni état `space.live`.

Elle est ouverte seulement lorsque le resolver Operations existant fournit une perspective opérateur/Space et une phase canonique `arrival` ou `live`. ZS5 n'ajoute pas d'heuristique `start_at <= now + 24h`.

Plusieurs Occurrences actuelles peuvent donc produire plusieurs projections Jour J simultanées, chacune avec la même identité canonique `occurrence + id`.

La projection compose de façon bornée :

- contexte Space / Activity / Occurrence ;
- Operational Readiness ;
- Capacity ;
- résumé Access ;
- Live Queue ;
- Placement ;
- Checkpoints ;
- état Scanner ;
- profondeur Live ;
- links et capabilities calculés pour le viewer.

Les incidents ne possèdent pas encore de selector Occurrence owner-backed dans ce runtime. ZS5 ne prétend donc pas qu'ils sont connus vides : la projection les marque `truth=unavailable` avec une collection vide.

Toutes les réponses sont `private, no-store`.

## 4. Live

ZS5 ne crée aucun resolver Live.

La profondeur reste :

```text
GET /api/v1/operations/occurrences/<occurrence-id>/live/
```

Le resolver existant conserve ses perspectives `participant`, `operator` et `space`. La projection Jour J réutilise son résultat sans recopier l'Occurrence ni créer un second moteur.

Les horaires et lieux planifiés restent les faits de l'Occurrence. Une absence de position observée n'est pas remplacée par une position inventée. ZS5 ne transforme aucune valeur planifiée en observation supplémentaire.

## 5. Scanner / contrôle

Nouvelle projection focalisée :

```text
GET /api/v1/scanner/occurrences/<occurrence-id>/context/
projection = space.scanner.context
scope = space
```

Elle ne charge pas le Space complet. Elle expose uniquement :

- Space ;
- Activity ;
- Occurrence ;
- responsabilité Scanner active éventuelle ;
- disponibilité réelle du prochain scan ;
- capabilities ;
- handoffs Jour J / Live / Scanner owner.

Invariant conservé :

```text
ScannerAssignment = responsabilité
Permission / Mandate = autorité
```

La projection exige `user_can_scan_activity()`. Une Assignment seule reçoit donc 404.

Le runtime Scanner possède aujourd'hui un POST de scan canonique consommable via l'adaptateur Event historique. ZS5 n'invente pas un POST générique Activity. Pour une Activity non-Event, le contexte Scanner peut être autorisé mais annonce :

```text
next_scan.state = unavailable
reason = no_owner_scan_endpoint_for_activity
```

et n'expose pas la capability `scan`.

Aucun token, QR, AccessCredential ni secret n'est sérialisé dans cette projection générale.

L'idempotence des usages reste celle d'Access/Scanner ; ZS5 n'ajoute aucune clé ou journal transversal.

## 6. Makolo Mark Space

Nouvelle route explicite :

```text
POST /api/v1/organizations/workspaces/<space-slug>/mark/
projection = space.mark
scope = space
```

Elle ne détourne jamais `POST /api/v1/me/mark/`.

L'acteur Space est résolu par le serveur via `workspace_spaces(request.user)`. Les clés client prétendant fournir `permission`, `mandate`, `role`, `space_id`, `profile_id` ou un autre changement d'acteur sont rejetées.

`context.responsibility` peut être conservé comme information d'interprétation, mais n'accorde aucun droit.

L'ajout d'un membre à l'équipe fournit un exemple fermé de mutation Mark owner-backed : le Mark collecte une identité et un rôle d'autorité explicite, demande une confirmation décrivant la conséquence humaine, revalide `SPACE_TEAM_MANAGE`, puis appelle `find_user_for_team()` et `add_or_update_member()`. Ce rôle explicite est distinct de `context.responsibility`, qui n'accorde aucun droit. Un replay converge sur la même `TeamMembership`; aucune écriture ORM n'est effectuée par l'orchestrateur.

Sur la base auditée, le Mark Space ferme seulement les handoffs dont les owners sont déjà stables sur `main` :

- Jour J / Live → Operations ;
- Scanner → Scanner ;
- Équipe → Organizations.

Les demandes de création Commerce, Transport, Partner, Finance ou Payment dont la couture owner ZS3/ZS4 n'est pas encore présente sur `main` répondent honnêtement `unsupported` au lieu d'écrire directement dans l'ORM ou de reconstruire le métier. ZS6 pourra enrichir ces handoffs après réconciliation du train.

Le seul input générique annoncé est `text`. Les fichiers/images/liens ne sont pas prétendus supportés par un pipeline inexistant.

Le Mark ne persiste ni session, ni intention, ni journal métier et ne fait aucune mutation ORM directe.

## 7. Autorité et divulgation minimale

ZS5 conserve :

```text
Membership != authority
Assignment != authority
Platform Permission != Space authority
responsibility != authority
```

Une autorité Activity-only ne peut ouvrir que les Occurrences de cette Activity. Les lookups étrangers retournent 404 lorsque nécessaire pour éviter les fuites d'existence.

Les mutations owners restent responsables de leur revalidation. ZS5 ne transforme jamais une capability GET en jeton d'autorité.

## 8. TOCTOU

Les projections recalculent l'autorité à chaque requête.

Scénario couvert :

```text
GET Jour J → autorisé
révocation Mandate
GET Jour J → 404
```

Le POST Scanner existant et les services owners continuent eux-mêmes de revalider leur autorité et leurs invariants.

## 9. Identités et continuité

Aucune identité `DayOfOccurrenceId`, `LiveDepartureId`, `ScannerAccessId` ou `MarkOrderId` n'est créée.

Les chaînes restent :

```text
Occurrence(kind+id)
→ Jour J
→ Live

Occurrence(kind+id)
→ Scanner context
→ owner Scanner / AccessUse
→ refetch Jour J
```

La provenance de navigation n'est pas persistée.

## 10. Tests ciblés

Le module `operations/test_zs5_space_action_api.py` couvre notamment :

- auth requise ;
- outsider / minimal disclosure ;
- autorité Activity-only ;
- autre Activity refusée ;
- Occurrence non actuelle refusée ;
- plusieurs Jour J simultanés ;
- Assignment Scanner seule refusée ;
- Permission Scanner réelle ;
- absence de secret dans la projection Scanner ;
- TOCTOU après révocation ;
- Space Mark explicite ;
- Membership sans autorité ;
- responsabilité qui ne crée aucune Permission ;
- spoof d'autorité client rejeté ;
- clarification bornée ;
- unsupported honnête ;
- input non-text non annoncé comme supporté ;
- mutation Team owner-backed, confirmation et replay idempotent.

Les suites Scanner existantes restent propriétaires des tests détaillés d'Access invalide/révoqué/wrong occurrence et de replay/idempotence.

## 11. Absence de migration

ZS5 n'ajoute aucun modèle ni champ persistant.

Gate obligatoire avant fermeture :

```bash
python manage.py makemigrations --check --dry-run
```

## 12. Gaps laissés à ZS6

ZS6 doit réconcilier :

1. `organizations/api/urls.py` avec la branche ZS3 avant intégration finale ;
2. les handoffs Mark vers les projections ZS2–ZS4 réellement mergées ;
3. le gap owner Scanner générique pour Activity non-Event si le train décide de le fermer hors ZS5 ;
4. l'éventuelle projection owner-backed d'incidents réellement Occurrence-scoped si le domaine Operations la fournit ;
5. les chaînes de continuité finales Maintenant/Métier/Nous/Piloter → Occurrence → Jour J.

Aucun de ces gaps ne justifie de créer une vérité ZS5 parallèle.
