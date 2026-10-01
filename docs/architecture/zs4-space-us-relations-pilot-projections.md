# ZS4 — Space Nous, Relations & Pilotage projections

**Statut :** checkpoint d'implémentation ZS4 prêt à intégrer dans le train ZS  
**Base auditée :** `main@ef1e0f5a25233cfe240588d42c5902cbdf70ebe9`  
**Branche :** `zs4-space-us-relations-pilot-projections`  
**Portée :** projections serveur `Nous`, `Personnes & relations` et `Piloter` pour un Space.  
**Hors portée :** modèles, migrations, templates, Flutter, redesign, ranking, score global, algorithmes Molongo.

## 1. Audit de base et collisions

ZS4 a été démarré après vérification du `main` courant, des commits récents, des branches ZS et des PR ouvertes visibles.

Constats au démarrage :

- `main` est à `ef1e0f5a25233cfe240588d42c5902cbdf70ebe9`, merge ZS1 ;
- la branche `zs3-space-work-archetype-projections` est exactement trois commits en avance sur ce même `main` et touche uniquement :
  - `organizations/api/space_work_projection.py` ;
  - `organizations/api/space_work_views.py` ;
  - `organizations/api/urls.py` ;
- aucune branche ZS2 ou ZS4 n'existait sous ces noms lors de l'audit ;
- les PR ouvertes #408 (performance read-path) et #410 (Mayele identity resolution) ne touchent pas les modules de projection ZS4 ;
- le seul conflit prévisible avec ZS3 est l'ajout de routes dans `organizations/api/urls.py`.

Le choix de couture est donc : trois modules de projection indépendants, une vue de routage ZS4 commune, et une modification centralisée de `urls.py`.

## 2. Owners réutilisés

ZS4 ne crée aucune vérité métier.

### Nous

Réutilise :

- `Organization` pour l'identité du Space ;
- ZS1 `build_space_workspace()` pour le contexte d'autorité, les responsabilités, les capabilities, Trust public et les modules ;
- `TeamMembership` pour la collaboration ;
- `Mandate` pour l'ownership et l'autorité ;
- Trust via la projection ZS1 existante.

### Relations

Réutilise sans fusion :

- Team / `TeamMembership` ;
- Groups / `Group` ;
- CRM / `CRMContact` ;
- CRM Audience / `Audience` ;
- Partners / `Partner`.

Une même personne peut apparaître dans plusieurs familles avec le même Profile canonique lorsque les owners possèdent déjà ce lien. Aucune identité `SpaceRelationship` ou `UnifiedPerson` n'est introduite.

### Piloter

Réutilise :

- `analytics_app.services.build_portfolio_analytics()` ;
- les Permissions Analytics existantes ;
- les montants financiers déjà produits par Analytics.

ZS4 ne crée ni second Analytics ni moteur d'interprétation.

## 3. Contrat Nous

Route :

```text
GET /api/v1/organizations/workspaces/<slug>/us/
```

La projection retourne :

- `identity` : identité humaine du Space ;
- `team` : résumé et preview bornée uniquement lorsque `space.team.manage` le permet ;
- `responsibilities` : perspectives ZS1 ;
- `ownership` : owners réels issus des Mandates, uniquement avec autorité correspondante ;
- `trust` : claims publics/appropriés déjà exposés par ZS1 ;
- `organization` : preset de présentation et footprint lorsque disponible ;
- `authority`, `links`, `capabilities`.

Une personne Activity-scoped reçoit une projection volontairement minimale : pas de Team globale, pas d'ownership global, pas de contacts généraux privés.

`created_by` n'est jamais utilisé comme owner runtime.

## 4. Contrat Relations

Route :

```text
GET /api/v1/organizations/workspaces/<slug>/relationships/
```

Les sections sont indépendantes et n'apparaissent que si l'autorité directe du Space et la Permission correspondante permettent leur divulgation :

- `team` ;
- `groups` ;
- `crm_contacts` ;
- `audiences` ;
- `partners`.

Les identités métier restent explicites :

```text
kind=team_member
kind=group
kind=crm_contact
kind=audience
kind=partner
```

Les previews sont bornées à 12 éléments avec `has_more`.

Les contacts CRM n'exposent pas email, téléphone, consent metadata, notes ou historique. Partner n'expose pas de données financières dans la racine Relations.

Le langage relationnel par archétype est centralisé dans `organizations.space_product`, avec les huit libellés canoniques prévus par le contrat Space.

## 5. Contrat Piloter

Route :

```text
GET /api/v1/organizations/workspaces/<slug>/pilot/
```

La première composition livrée est volontairement limitée au contrat Analytics existant.

Avec `analytics.view`, la section `analytics` expose :

- compteurs owner-backed ;
- présence ;
- commandes confirmées ;
- waitlist ;
- totaux financiers uniquement lorsque l'owner Analytics les rend visibles ;
- `generated_at` ;
- couverture explicite `latest_visible_events`, bornée aux 40 événements visibles déjà utilisés par l'owner Analytics ;
- deep link vers l'API Analytics propriétaire.

Aucun signal interprétatif n'est fabriqué :

```json
{"signals": []}
```

lorsqu'aucune règle owner-backed ne permet de conclure.

### 0, unknown et insufficient_data

Le contrat protège explicitement :

```text
0 != unknown != unavailable != insufficient_data
```

Sur un Space sans événement visible :

- `events_count` vaut réellement `0` avec `state=known` ;
- les métriques nécessitant un dénominateur absent, comme `attendance_percent`, portent `state=insufficient_data` et `value=null` ;
- la section globale Analytics porte `state=insufficient_data` ;
- aucun faux trend n'est créé.

Les montants Decimal sont sérialisés en chaînes avec devise explicite.

## 6. Responsabilité vs autorité

ZS4 consomme le contexte ZS1.

Les projections ne déduisent jamais une Permission depuis :

- TeamMembership ;
- GroupMembership ;
- Partner ;
- Assignment ;
- archetype ;
- Platform authority.

Une responsabilité reste une perspective de lecture. Toute mutation continue à être revalidée par l'owner.

## 7. Activity-only et Platform

Le scope Activity-only peut ouvrir le contexte Space conformément à ZS1, mais ZS4 ne l'étend pas vers les collections globales.

Tests dédiés :

- Activity-only : Nous minimal, Relations vide, Piloter sans Analytics Space ;
- Platform-only : 404 sur les projections Space ;
- Membership-only : 404.

## 8. TOCTOU

Le contrat teste :

```text
GET Nous
→ capability manage_team
→ révocation du Mandate
→ POST Team
→ refus
```

La capability de projection n'est donc jamais un token d'autorisation.

## 9. Performance locale

Les racines utilisent des previews bornées.

Aucune collection complète CRM/Team/Partner n'est embarquée.

Aucun cache spéculatif n'est ajouté.

Les owners existants restent responsables des profondeurs paginées ou spécialisées.

## 10. Migrations

ZS4 n'ajoute :

- aucun modèle ;
- aucun champ ;
- aucune migration ;
- aucun état UX persistant.

Aucun fichier de migration n'est modifié par la branche.

Le gate final doit conserver :

```bash
python manage.py makemigrations --check --dry-run
```

vert.

## 11. Tests ciblés

`organizations/test_zs4_space_projections.py` couvre notamment :

- authentification ;
- outsider ;
- Membership sans authority ;
- Activity-only ;
- Platform-only ;
- identité Nous ;
- Team/ownership owner-backed ;
- mêmes Profile avec relations Team + CRM + Partner ;
- absence de PII CRM ;
- Group et Partner sans transfert d'autorité ;
- `created_by` comme provenance, jamais ownership ;
- Analytics Marketing sans Permission financière et sans fuite de montants ;
- huit labels d'archétype ;
- zéro réel vs `insufficient_data` ;
- absence de score global ;
- capability révoquée puis mutation refusée.

## 12. Gaps laissés volontairement

ZS4 ne ferme pas :

- les signaux de Maintenant — ZS2 ;
- les sections Métier — ZS3 ;
- Jour J / Live / Scanner — ZS5 ;
- la réconciliation sécurité/performance globale — ZS6 ;
- le ranking, la pertinence, les tendances synthétiques ou les algorithmes Molongo.

Les futurs enrichissements de Piloter doivent continuer à partir de faits owner-backed et de règles déterministes défendables. Une projection représente les vérités ; elle ne les possède pas.
