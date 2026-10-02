# WS3 — Space Métier & Archetypes Web

**Statut :** implémentation WS3 autonome, à réconcilier par WS6  
**Base initiale auditée :** `main@f3a7cf94514c94d65198b286bcf33e1cbe470697
base finale réconciliée = 1eb8e7969528945739e5f70c9cd51ff1e8d17b0e`  
**Base finale réconciliée :** `main@1eb8e7969528945739e5f70c9cd51ff1e8d17b0e`  
**Branche :** `ws3-space-work-archetype-web`  
**Périmètre :** racine Web Métier, sections Work, langage d'archétype, owner handoffs, responsive et tests Web.

## 1. Problème utilisateur

La porte Métier doit répondre à :

> **Qu'est-ce que nous faisons réellement exister, préparer, exécuter et délivrer ?**

Elle doit présenter le travail durable d'un Space dans son langage naturel sans obliger la personne à comprendre les abstractions `Activity`, `Occurrence`, `Journey`, `Offer` ou `TransportRoute`.

WS3 ne devient propriétaire d'aucun de ces domaines.

## 2. Audit de départ

Le chantier a été créé depuis le HEAD exact de `main` indiqué ci-dessus.

Au démarrage :

- WS1 était déjà intégré via la PR #421, avec closeout #424 ;
- la branche parallèle `ws2-space-now-discover-web` était en avance sur le même `main` et modifiait notamment `organizations/space_web_views.py` ;
- les PR ouvertes #422/#423 concernaient Flutter/mobile et #425 Mayele ;
- aucune branche WS3 préexistante n'était utilisée comme base.

### Collision audit

WS3 évite volontairement `organizations/space_web_views.py`, modifié par WS2.

Les écritures WS3 sont concentrées dans :

- `organizations/space_work_web.py` ;
- `templates/organizations/space/work.html` ;
- `organizations/test_ws3_space_work_web.py` ;
- `e2e/specs/ws3-space-work-archetype.spec.mjs` ;
- le présent document.

Le raccord Web partagé reste `organizations/urls.py`, uniquement pour importer le `SpaceWorkView` WS3 depuis son module dédié. La route et son nom restent inchangés.

Le gate E2E a révélé sur la base initiale une corruption syntaxique préexistante de `e2e/specs/permissions.spec.mjs`, et la suite Django un ancien contrat `403` devenu `404` sur la racine Space privacy-safe. Ces deux réparations ont ensuite été intégrées sur `main` via les travaux concurrents avant la réconciliation finale ; WS3 ne les duplique donc plus dans son diff final.

## 3. Projection ZS3 consommée

WS3 consomme directement :

~~~text
build_space_work_projection(...)
GET /api/v1/organizations/workspaces/<slug>/work/
~~~

Le builder ZS3 reste propriétaire de :

- la visibilité des Activities ;
- le scope d'autorité `space` / `activity_limited` ;
- la responsabilité de lecture ;
- le libellé `primary_business_label` ;
- l'Operational Footprint ;
- la sélection des items ;
- les sections ;
- les links ;
- les capabilities ;
- la limite d'aperçu.

WS3 ne refait pas ces calculs depuis l'ORM.

## 4. Architecture Web

Le `SpaceWorkView` WS3 hérite du `SpaceWebMixin` WS1 afin de conserver :

- la résolution privacy-safe du Space ;
- les responsabilités revalidées serveur ;
- le shell Mature ;
- les URLs directes ;
- le transport de la responsabilité dans la navigation ;
- HTMX comme progressive enhancement.

Le module WS3 appelle ensuite le builder ZS3 avec la responsabilité déjà revalidée et compose uniquement une structure de présentation des sections.

Aucune requête HTTP interne n'est ajoutée.

## 5. Archetype et vocabulaire

Le titre visible vient exclusivement de :

~~~text
projection.primary_business_label
~~~

La table canonique reste `organizations.space_product.SPACE_OPERATING_PRESETS`.

WS3 ne possède donc aucune table parallèle :

~~~text
generic            -> Activités
creative           -> Créations
media              -> Productions
education          -> Programmes
commerce           -> Commerce
service_provider   -> Prestations
transport_operator -> Transport
community           -> Initiatives
~~~

Le fallback éventuel reste la responsabilité du helper canonique existant.

## 6. Operational Footprint

WS3 ne transforme pas l'Operational Footprint en whitelist d'archétype.

Le footprint reste un signal dérivé ZS. La sélection visible continue d'être produite par ZS3 à partir des vérités métier et de l'autorité réelles.

Invariant conservé :

~~~text
ARCHETYPE
= présentation / centre de gravité

OPERATIONAL FOOTPRINT
= domaines réellement utilisés
~~~

## 7. Sections

WS3 rend les sections exactement dans l'ordre du contrat ZS3 :

~~~text
preparation -> À préparer
upcoming    -> À venir
active      -> En cours
blocked     -> Bloqués
completed   -> Terminés
~~~

La correspondance est une présentation de clés serveur déjà stabilisées ; elle ne contient aucune règle de sélection.

En particulier, WS3 ne calcule jamais `blocked`. Un Journey apparaît dans cette section seulement si ZS3 l'y a placé, notamment à partir d'un `JourneyBlocker` owner actif.

Les empty states n'inventent aucun travail.

## 8. Owner handoffs

Chaque item conserve ses `links` ZS3.

Pour le Web, WS3 ajoute un handoff vers la Console Activity uniquement lorsque la projection expose déjà un owner Activity :

- Activity : `links.detail` ZS3 ;
- Occurrence / Offer / Journey / CommerceOrder : `links.activity` ZS3 + `context.activity.id`.

Le Web ne déduit pas un owner depuis le type seul.

Lorsque ZS3 n'expose pas de lien owner exploitable, WS3 n'en invente aucun. C'est actuellement le cas des `TransportRoute` et `Vehicle` projetés avec `links={}`.

La Console historique reste la profondeur owner-backed générale.

## 9. Création contextuelle

ZS3 expose actuellement `capabilities.create_activity`, mais WS3 n'ajoute pas de bouton générique `+ Créer`.

Raison : le contrat ne fournit pas encore un lien Web owner-backed contextualisé suffisamment précis pour ouvrir une création métier sans exposer la taxonomie interne.

WS3 préfère donc ne rien inventer.

## 10. Responsabilité

La responsabilité reste un filtre de lecture.

Le `SpaceWebMixin` revalide la clé contre les responsabilités courantes issues de ZS1. WS3 transmet ensuite cette clé au builder ZS3.

Une responsabilité :

- peut réduire la vue ;
- ne peut pas élargir l'autorité ;
- étrangère ou révoquée retourne 404 ;
- n'est jamais stockée comme permission côté navigateur.

## 11. Sécurité et confidentialité

WS3 réutilise les frontières serveur ZS1/ZS3 :

- visiteur : login ;
- outsider : 404 ;
- TeamMembership seul : 404 ;
- Platform authority seule : 404 ;
- Activity authority : vue bornée aux Activities autorisées ;
- responsabilité étrangère/révoquée : 404.

Le template ne sérialise pas de Permission ou Mandate brut, de credential, QR, secret ou PII bénéficiaire.

Les tests vérifient également que les détails privés d'un blocker et l'email d'un bénéficiaire ne remontent pas dans Métier.

## 12. Behavior

La surface suit le contrat Behavior existant :

- `content` : sections projetées ;
- `empty` : message explicite sans donnée fictive ;
- `refresh/back/forward` : navigation Web standard + shell HTMX WS1 ;
- `permission denied` : frontière privacy-safe existante ;
- `error` : aucune fausse réussite locale ni reconstruction métier.

ZS3 ne porte pas actuellement un état `partial/unavailable` distinct par section. WS3 ne transforme donc pas une absence de contrat en `0` ou `false` inventé.

## 13. Responsive

WS3 réutilise les régimes W/WS1 :

~~~text
Compact   < 768 px
Adaptive  768-1199 px
Expanded  >= 1200 px
~~~

La composition reste volontairement Focus : sections lisibles et navigation horizontale bornée.

Aucune action essentielle ne dépend du hover, d'un panneau Expanded ou d'un raccourci clavier.

Aucun nouveau CSS ou JavaScript WS3 n'est ajouté.

## 14. Performance

WS3 :

- appelle une seule fois le builder ZS3 ;
- ne fait aucune requête par carte ;
- ne précharge aucune profondeur owner ;
- respecte `PREVIEW_LIMIT` et `has_more` produits par ZS3 ;
- ne charge pas toute la Console ;
- ne crée aucun cache navigateur persistant.

Les éventuelles optimisations de query count restent la responsabilité du read path ZS3, déjà borné.

## 15. Non-objectifs

WS3 ne construit pas :

- Maintenant / Découvrir ;
- Nous / Relations / Pilotage ;
- Jour J / Live / Scanner / Makolo Mark complet ;
- un nouveau shell ;
- un ERP, kanban ou task manager ;
- une Permission frontend ;
- un nouveau modèle Activity/Journey/Transport/Commerce ;
- une persistance UX ;
- une migration ;
- un moteur Molongo.

## 16. Tests

Tests Django WS3 :

~~~text
organizations.test_ws3_space_work_web
~~~

Ils couvrent notamment :

- visiteur / outsider ;
- TeamMembership seul ;
- Platform-only ;
- Activity-scoped ;
- responsabilité valide, étrangère et révoquée ;
- libellés des huit archétypes ;
- absence d'autorité induite par l'archétype ;
- sections ZS3 ;
- blocked owner-backed ;
- confidentialité ;
- owner link présent/absent selon le contrat.

E2E WS3 :

~~~text
e2e/specs/ws3-space-work-archetype.spec.mjs
~~~

Viewport gates :

~~~text
400 / 800 / 1199 / 1200 / 1440 px
~~~

Le test vérifie l'absence d'overflow, la lisibilité des sections, l'URL directe et le retour après handoff owner lorsqu'un lien est disponible.

## 17. Migrations

Aucun modèle et aucune migration WS3.

Le gate inclut :

~~~text
python manage.py check
python manage.py makemigrations --check --dry-run
~~~

## 18. WS6 HANDOFF

### Base commit

~~~text
f3a7cf94514c94d65198b286bcf33e1cbe470697
~~~

### Branch

~~~text
ws3-space-work-archetype-web
~~~

### PR

`#427` a été fermée automatiquement pendant la réconciliation lorsque la branche a été momentanément alignée sur `main`. La PR finale est créée après cette réconciliation.

### Routes

Route Web conservée :

~~~text
/spaces/<slug>/work/
name = organizations:space-work
~~~

### Views

~~~text
organizations/space_work_web.py
  SpaceWorkView
~~~

### Templates

~~~text
templates/organizations/space/work.html
~~~

### Partials

Aucun partial global ajouté.

### CSS

Aucun fichier CSS modifié.

### JS

Aucun fichier JS modifié.

### Tests

~~~text
organizations/test_ws3_space_work_web.py
e2e/specs/ws3-space-work-archetype.spec.mjs
~~~

### Owner contracts

~~~text
build_space_work_projection
SPACE_OPERATING_PRESETS / operating_preset_for_space
SpaceWebMixin / build_space_workspace
Console Activity detail
Console Espace
~~~

### Archetype helpers utilisés

Le vocabulaire est consommé via les projections ZS existantes ; aucune table WS3 dupliquée.

### Fichiers à collision

~~~text
organizations/urls.py
~~~

`organizations/space_web_views.py` reste volontairement évité. La réconciliation finale conserve également les routes et views WS5 déjà intégrées sur `main`.

### Décisions UX importantes

- Métier affiche les cinq sections ZS3, sans les recalculer.
- Composition Focus commune à Compact/Adaptive/Expanded ; pas de master/detail artificiel.
- Handoff Activity seulement si ZS3 expose déjà le lien owner.
- Pas de bouton générique de création.
- Pas de filtre/recherche décoratif.
- Pas d'icône archétype locale : WS1 garde actuellement son système d'icônes et WS6 pourra réconcilier le hook global si une source canonique d'icône existe alors.

### Gaps volontairement laissés à WS6 ou aux owners

- réconciliation finale du shell avec WS2/WS4/WS5 ;
- éventuel hook d'icône archétype dans la navigation globale ;
- lien Web profond Route/Vehicle si le contrat owner l'expose plus tard ;
- création contextuelle uniquement lorsque des liens owner-backed sont disponibles.
