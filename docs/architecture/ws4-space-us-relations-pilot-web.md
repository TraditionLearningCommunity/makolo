# WS4 — Space Nous, Relations & Pilotage Web

**Statut :** implémentation Web Space WS4  
**Base initiale auditée :** `main@f3a7cf94514c94d65198b286bcf33e1cbe470697`  
**Branche :** `ws4-space-us-relations-pilot-web`  
**Portée :** Nous, Personnes & relations, Piloter et leurs handoffs Web directs.  
**Hors portée :** WS2 Maintenant/Découvrir, WS3 Métier, WS5 Jour J/Live/Scanner/Mark, shell final WS6, Platform, Flutter, Molongo.

## 1. Problème utilisateur

WS4 ferme trois questions humaines sans créer de nouveau métier côté Web :

- **Nous** — « Qui sommes-nous, avec qui fonctionnons-nous et comment sommes-nous organisés ? »
- **Personnes & relations** — « Avec qui avançons-nous ? »
- **Piloter** — « Est-ce que cela fonctionne ? Qu’est-ce qui change ? Que devons-nous ajuster ? »

Le Web consomme les projections ZS4 déjà intégrées. Il ne relit pas les modèles privés pour reconstituer les faits et ne recalcule ni autorité, ni relation, ni analyse.

## 2. Projections ZS4 consommées

| Surface Web | Projection serveur |
| --- | --- |
| Nous | `build_space_us_projection()` / `GET /api/v1/organizations/workspaces/<slug>/us/` |
| Relations | `build_space_relationships_projection()` / `GET /api/v1/organizations/workspaces/<slug>/relationships/` |
| Piloter | `build_space_pilot_projection()` / `GET /api/v1/organizations/workspaces/<slug>/pilot/` |

La composition Web appelle directement les builders Python partagés. Il n'existe aucun appel HTTP Django→Django.

## 3. Routes Web

- `/spaces/<slug>/us/` — Nous, N1 existante du shell WS1.
- `/spaces/<slug>/relationships/` — surface secondaire majeure.
- `/spaces/<slug>/pilot/` — surface secondaire majeure.

Toutes sont Space-scoped, server-rendered, deep-linkables et compatibles refresh/back/forward. Le paramètre `responsibility` reste validé par le mixin WS1 et n'augmente jamais l'autorité.

## 4. Nous

Nous commence par l'identité collective puis compose uniquement ce que ZS4 expose :

- identité / archétype ;
- équipe bornée ;
- responsabilités ;
- ownership lorsque visible ;
- faits Trust projetés ;
- entrées secondaires vers Relations, Pilotage et outils institutionnels réellement autorisés.

Settings reste une profondeur secondaire. La racine n'est pas un formulaire d'administration.

Invariant conservé :

```text
TeamMembership != Permission
TeamMembership != Mandate
Assignment = responsabilité
Mandate / Permission = autorité
ownership != membership != responsibility
```

## 5. Personnes & relations

La page garde les sections ZS4 séparées :

- Team ;
- Groups ;
- CRM contacts ;
- Audiences ;
- Partners.

Une même personne peut donc apparaître plusieurs fois avec des relations différentes. Le Web ne fait aucune résolution d'identité ni fusion universelle.

Le libellé principal vient de `relationships_label_for_space()`, déjà centralisé par archétype côté serveur.

**Borne runtime :** chaque preview ZS4 est limitée à 12 éléments, avec `has_more` explicite. WS4 respecte cette borne et renvoie vers l'owner historique lorsque disponible.

## 6. Piloter

Piloter ne crée aucun moteur Analytics. La chaîne reste :

```text
Analytics owner
→ projection ZS4
→ présentation humaine
→ profondeur Analytics owner-backed
```

La page conserve explicitement :

```text
0 != unknown != unavailable != insufficient_data
```

Un zéro connu reste un zéro. Une valeur `insufficient_data` ne devient ni 0 %, ni « aucune activité ». Les états `unknown` et `unavailable` sont rendus distinctement si le serveur les projette.

Aucun `Space Score`, `Health Score`, `Performance Score` ou score Trust n'est construit.

La couverture Analytics actuelle reste bornée par la projection serveur (`coverage.limit`, actuellement 40 événements visibles).

## 7. Handoffs owners

WS4 ne réécrit pas la Console professionnelle. Selon projection et autorité :

- Team / gouvernance → Console Équipe ;
- Groups → Console Groupes ;
- CRM contacts → Console CRM ;
- Audiences → Console Audiences ;
- Partners → Console Partenaires ;
- Trust → Console Confiance ;
- Pilotage approfondi → Console Analytics ;
- Settings → Console Paramètres.

L'affichage d'un lien n'est jamais une autorisation. Les mutations continuent à revalider l'autorité côté owner.

## 8. Autorité, privacy et IDOR

La résolution du Space reste `workspace_spaces(request.user)`.

Conséquences :

- TeamMembership seule : aucun accès Space ;
- GroupMembership seule : aucun accès ;
- Assignment seul : aucun accès ;
- Platform-only : aucun accès implicite au Space ;
- Activity-scoped : lecture Space minimale, Relations globales et Pilotage global non élargis ;
- responsabilité étrangère/révoquée : 404 privacy-safe ;
- slug d'un autre Space : 404 si aucune autorité.

Le Web ne réinjecte ni email, téléphone, Permission brute, Mandate brut, credential, QR ou autre PII retirée des projections.

## 9. États d'expérience

Les pages utilisent les faits disponibles sans fabriquer de faux empty state :

- section absente : non rendue ;
- section projetée vide : empty connu ;
- Activity-scoped : indisponibilité expliquée ;
- Pilot `insufficient_data` : explication dédiée ;
- métrique `unknown` : inconnue ;
- métrique `unavailable` : indisponible ;
- métrique connue à zéro : 0.

Les erreurs d'autorité restent les 404 privacy-safe du serveur. Le shell WS1 conserve le comportement HTMX/refresh/back.

## 10. Responsive et accessibilité

WS4 réutilise les trois régimes W :

- Compact < 768 px ;
- Adaptive 768–1199 px ;
- Expanded >= 1200 px.

Le CSS est isolé dans `static/css/space-ws4.css`. Il ne modifie pas `mature-experience.css`.

- Nous : Focus sur Compact, grille calme sur Expanded ;
- Relations : liste/cartes puis grille en Expanded ;
- Piloter : densité plus élevée, métriques structurées sans mur de KPI.

Les surfaces utilisent titres hiérarchisés, landmarks, focus visible, liens clavier, texte sémantique en plus de la couleur et respect de `prefers-reduced-motion`.

## 11. Performance

WS4 n'ajoute aucune requête par relation ou KPI au template. Les templates consomment les projections déjà composées.

Bornes préservées :

- Nous : preview 8 ;
- Relations : preview 12 ;
- Pilot Analytics : couverture serveur bornée.

Aucun polling, cache privé persistant ou chargement de toute la Console n'est introduit.

## 12. Persistance et migrations

WS4 ajoute :

- aucun modèle ;
- aucune migration ;
- aucun état UX persistant.

Selected responsibility reste une query URL existante. Les autres états de présentation restent éphémères.

## 13. Collision audit

Au démarrage :

- WS1 était intégré sur `main` et fournit le shell Space consommé par WS4 ;
- WS2/#426 travaille en parallèle sur `organizations/space_web_views.py`, Maintenant et Découvrir ;
- WS3/#427 travaille en parallèle sur `organizations/urls.py` et Métier ;
- PR #428 corrige des régressions CI post-merge sur des tests ;
- aucune branche WS4 antérieure n'était active.

WS4 touche donc deux fichiers partagés seulement et sans refactor global :

- `organizations/space_web_views.py` — ajout des builders/vues/URLs contextuelles WS4 ;
- `organizations/urls.py` — deux routes secondaires.

WS6 devra réconcilier ces ajouts avec les versions finales de WS2/WS3, sans perdre leurs imports ni routes.

## 14. Non-objectifs

WS4 n'ajoute pas : réseau social, annuaire global, CRM parallèle, Team parallèle, Permission frontend, dashboard par rôle, score global, leaderboard, feed, task manager, ERP, nouveau moteur Analytics, nouvelle autorité ou Molongo.

# WS6 HANDOFF

**Base SHA :** `f3a7cf94514c94d65198b286bcf33e1cbe470697`  
**Branche :** `ws4-space-us-relations-pilot-web`  
**PR :** à renseigner à l'ouverture de la PR WS4.

### Routes

- `organizations:space-us` → `/spaces/<slug>/us/`
- `organizations:space-relationships` → `/spaces/<slug>/relationships/`
- `organizations:space-pilot` → `/spaces/<slug>/pilot/`

### Views

- `SpaceUsView`
- `SpaceRelationshipsView`
- `SpacePilotView`

### Templates

- `templates/organizations/space/ws4_base.html`
- `templates/organizations/space/us.html`
- `templates/organizations/space/relationships.html`
- `templates/organizations/space/pilot.html`

### Partials

Aucun partial global nouveau. WS4 reste autonome.

### CSS

- `static/css/space-ws4.css`

Aucun changement dans `static/css/mature-experience.css` ou `static/dist/makolo.css`.

### JS

Aucun JavaScript WS4 spécifique. Le shell HTMX/JS existant reste propriétaire du runtime de navigation.

### Tests

- `organizations/test_ws4_space_web.py`
- `e2e/specs/ws4-space-us-relations-pilot.spec.mjs`
- ZS4 reste couvert par `organizations/test_zs4_space_projections.py`.

### Projections consommées

- `build_space_us_projection`
- `build_space_relationships_projection`
- `build_space_pilot_projection`
- `build_space_workspace` via WS1.

### Owner links

Team, Groups, CRM, Audiences, Partners, Trust, Analytics et Settings utilisent les routes owner-backed existantes de la Console selon ce qui est réellement projeté.

### Fichiers partagés touchés

- `organizations/space_web_views.py` — collision probable WS2.
- `organizations/urls.py` — collision probable WS3.

### Conflits potentiels

WS6 doit composer, pas choisir entre branches :

- conserver les implémentations finales Maintenant/Découvrir de WS2 ;
- conserver la surface Métier et les routes WS3 ;
- conserver les vues/routes WS4 ajoutées ici ;
- conserver le shell WS1 et la navigation primaire à cinq destinations ;
- intégrer WS5 sans promouvoir Relations/Piloter en N1 mobile.

### Décisions UX importantes

- Nous reste N1 et humain, Settings secondaire ;
- Relations et Piloter sont secondaires ;
- relation kind toujours visible ;
- Activity-scoped n'élargit jamais les collections globales ;
- Pilot conserve les états sémantiques serveur ;
- aucun score global ;
- Analytics reste owner des faits ;
- aucune nouvelle persistance.

### Gaps volontaires

- pas de moteur de recherche Relations : aucun contrat owner-backed dédié n'est nécessaire à WS4 actuellement ;
- aucun graphe Web ajouté : les signaux ZS4 sont actuellement vides et WS4 n'invente pas de sémantique ;
- aucun détail relationnel propriétaire recopié ;
- aucune mutation Team/Trust/Settings/Analytics réimplémentée ;
- navigation globale finale laissée à WS6.
