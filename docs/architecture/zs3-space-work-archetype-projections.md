# ZS3 — Space work & archetype projections

**Programme :** ZS — Space Backend UX Projection & API Composition  
**Base auditée :** `main@ef1e0f5a25233cfe240588d42c5902cbdf70ebe9`  
**Branche :** `zs3-space-work-archetype-projections`  
**Statut :** checkpoint ZS3 prêt pour réconciliation du train ZS.

## 1. Frontière

ZS3 prépare la quatrième porte Space : **Métier**.

Il ne crée ni modèle, ni migration, ni état métier générique, ni ranking, ni logique Molongo, ni template Web, ni code Flutter.

La composition suit :

~~~text
owners métier existants
→ selectors / autorisation existants
→ read-model ZS3
→ API Space stable
→ clients Web / Mobile
~~~

Les vérités restent propriétaires. La projection ne possède aucune mutation.

## 2. Couture runtime retenue

ZS1 reste le bootstrap Space dans `organizations/api/workspace_projection.py`.

ZS3 est isolé dans :

~~~text
organizations/api/space_work_projection.py
organizations/api/space_work_views.py
organizations/test_zs3_space_work_api.py
~~~

Le seul montage central nécessaire est l'ajout de la route dans `organizations/api/urls.py`.

Route :

~~~text
GET /api/v1/organizations/workspaces/<slug>/work/
~~~

Paramètre de lecture optionnel :

~~~text
?responsibility=all
?responsibility=mandate:<uuid>
~~~

Une perspective est toujours revalidée contre les Mandates courants du Profile et le Space courant. Elle ne peut jamais élargir l'autorité.

## 3. Contrat commun

La réponse expose :

~~~text
space
archetype
primary_business_label
authority
responsibility
operational_footprint
sections
links
capabilities
~~~

Les sections communes sont :

~~~text
preparation
upcoming
active
blocked
completed
~~~

Chaque collection est bornée à un preview de 20 items et expose :

~~~text
items
has_more
links
~~~

Aucune priorité, score ou urgence n'est calculé.

Une section vide reste une collection vide connue.

## 4. Identité canonique

Chaque item conserve :

~~~json
{
  "source": {
    "kind": "occurrence",
    "id": "..."
  }
}
~~~

La clé d'item est dérivée et opaque. Elle ne remplace jamais l'identité owner.

Les liens Activity/Occurrence utilisent les APIs owner existantes :

~~~text
/api/v1/activities/<id>/
/api/v1/occurrences/<id>/
~~~

Lorsqu'aucune API owner stable n'existe déjà pour une profondeur, ZS3 n'en invente pas une : le lien reste absent ou retombe sur l'Activity canonique.

## 5. Vocabulaire d'archétype

ZS3 consomme `organizations.space_product.operating_preset_for_space()`.

| Archetype | Métier |
| --- | --- |
| generic | Activités |
| creative | Créations |
| media | Productions |
| education | Programmes |
| commerce | Commerce |
| service_provider | Prestations |
| transport_operator | Transport |
| community | Initiatives |

L'archétype ne donne aucune Permission et ne crée aucune vérité.

## 6. Owners réutilisés

### Base commune

- `Activity`
- `Occurrence`

Les états owner sont conservés. ZS3 ne crée pas `work_status`.

### Education

Les Journey `REGISTRATION` ne sont projetées que lorsque l'autorité Activity Requests existe.

Aucune donnée bénéficiaire n'est sérialisée dans le résumé.

### Commerce

Les `Offer` sont visibles uniquement sur les Activities où `activity.commerce.view` est réellement accordé.

Les `CommerceOrder` ne sont composées qu'avec `orders.view` Space et restent limitées au Space + Activities visibles.

Un Order confirmé reste un Order confirmé. Il ne devient jamais une preuve d'obtention accomplie et aucun Payment n'est fusionné dans son état.

### Service

Les cases Service passent par `services.selectors.service_journeys_visible_to()`.

La projection ne sérialise ni bénéficiaire, ni Requirement privé, ni artefact, ni paiement.

Un élément entre dans `blocked` uniquement si un `JourneyBlocker` owner est réellement actif.

### Transport

Les Occurrences Transport restent des Occurrences canoniques et sont présentées comme `kind=departure` lorsqu'un `TransportDeparture` owner existe.

Les `TransportRoute` et `Vehicle` sont exposés uniquement sous autorité Space directe ; une autorité Activity limitée ne reçoit pas toute la flotte ni toutes les routes.

ZS3 n'ajoute aucune donnée Live, aucun Scanner capability et aucune logique Jour J.

## 7. Regroupements UX dérivés

Les regroupements sont des conséquences de lecture, pas des états persistants.

Exemples :

- Activity draft → `preparation`
- Occurrence future scheduled → `upcoming`
- Occurrence en cours selon son owner temporel → `active`
- Journey avec blocker owner actif → `blocked`
- Journey fulfilled/terminal ou Occurrence completed → `completed`

Les valeurs `state` restent les valeurs owner originales.

ZS3 ne déduit jamais :

~~~text
Requirement absent → blocked
Payment failed → Order blocked
Journey existe → prestation active
archetype transport_operator → scan autorisé
~~~

## 8. Autorité et divulgation minimale

Le point d'entrée réutilise `workspace_spaces()` de ZS1.

Sont exclus comme source d'autorité Space :

- TeamMembership seule ;
- GroupMembership seule ;
- ScannerAssignment seule ;
- Platform authority seule.

Pour une autorité Activity-scoped :

- seules les Activities mandatées du Space sont visibles ;
- le footprint Space global n'est pas exposé ;
- Routes/Vehicles Space ne sont pas exposés ;
- une perspective de responsabilité étrangère retourne 404.

Les capabilities sont calculées côté serveur depuis les permissions réellement présentes.

## 9. Operational Footprint

Le footprint est le read-model dérivé existant de `organizations.space_product`.

Il aide à savoir quelles familles existent réellement mais n'active aucune capacité.

Pour un viewer Activity-limited, le footprint Space global est volontairement masqué afin de ne pas révéler des verticales hors scope.

## 10. Performance

Les collections racines sont bornées.

Les lectures utilisent des `select_related` / `prefetch_related` ciblés pour les relations sérialisées.

Aucun cache, aucune dénormalisation, aucun préchargement de toute la base et aucun calcul Molongo n'ont été ajoutés.

ZS6 reste responsable de la passe performance transverse finale.

## 11. Tests ciblés

`organizations/test_zs3_space_work_api.py` couvre notamment :

- non authentifié ;
- outsider ;
- TeamMembership-only ;
- ScannerAssignment-only ;
- GroupMembership-only ;
- Platform-only ;
- collections vides ;
- les huit labels d'archétype ;
- identité Activity/Occurrence et owner links ;
- scope Activity-only ;
- responsibility lens sans élargissement ;
- Offer sous autorité Commerce Activity ;
- Journey Education sans fuite bénéficiaire ;
- Service case via selector owner sans Requirement privé ;
- Route/Vehicle Transport sous autorité Space.

## 12. Absence de migration

ZS3 n'ajoute aucun modèle et ne modifie aucun modèle existant.

Le gate attendu avant intégration est :

~~~text
python manage.py makemigrations --check --dry-run
~~~

Aucune migration ZS3 n'est attendue.

## 13. Gaps volontairement laissés

### ZS2

- attention ;
- urgence ;
- priorité ;
- pertinence ;
- sélection de ce qui remonte dans Maintenant.

### ZS4

- Team ;
- CRM ;
- Groups ;
- Partners ;
- Trust ;
- Pilotage / Analytics institutionnelles.

### ZS5

- Jour J complet ;
- Live ;
- Scanner focalisé ;
- Mark Space ;
- orchestration d'intention.

### Molongo

- ranking ;
- score ;
- pertinence synthétique ;
- recommandation ;
- calcul de priorité.

## 14. Références

ZS3 doit être lu avec :

- `docs/architecture/makolo-domain-blueprint.md`
- `docs/architecture/Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `docs/architecture/space-ux-experience-specification.md`
- `docs/architecture/zs1-space-ux-projection-foundation.md`
- `docs/architecture/backend-ux-projection-api.md`
- `docs/architecture/z15-orphan-capabilities-reconciliation.md`
- `docs/architecture/authorization-boundaries.md`
- `docs/architecture/current-program-status.md`
- `docs/architecture/activities.md`
- `docs/architecture/commerce-capacity.md`
- `docs/architecture/contextual-actions.md`

Le runtime courant reste prioritaire sur toute formulation historique.
