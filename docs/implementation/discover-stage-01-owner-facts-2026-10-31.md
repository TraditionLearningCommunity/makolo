# Découvrir — chantier 01 : vérités et capacités propriétaires

**Date du relevé :** 2026-10-31  
**Intégration :** [PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522) ; branche `fix/discover-a-continuation-context-20261014`.  
**Précondition :** [chantier 00](discover-stage-00-reconciliation-2026-10-31.md), fermé.  
**Nature :** travail terminé côté source et tests ajoutés ; **exécution des tests non possible dans le contexte d'édition GitHub utilisé**. Aucun CI, déploiement, migration ni merge n'a été lancé.  
**Registre :** [discover-closure-register.md](discover-closure-register.md).

## 1. Décision : réutiliser avant de corriger

Cette étape ne crée aucun modèle de Possibilité, ne modifie pas `discovery/api/composition.py`, ne forge pas de permission et ne calcule aucun fait de domaine côté Flutter. Le contrat est :

`owner canonique → selector/read model owner → Discovery (étape 02) → Presentation`.

Le statut `code existant` signifie qu'une implementation a été inspectée ; **il ne signifie jamais `tests verts`**.

## 2. Matrice propriétaire vérifiée sur les sources

| Domaine / obligation | Source canonique ou méthode effectivement inspectée | Conclusion et traitement étape 01 | Tests existants ou ajoutés |
| --- | --- | --- | --- |
| Activity : publication, visibilité, propriétaire logique | `activities/models.py` ; `discovery/search.py::_base_queryset`, `search_occurrences` | `ActivityStatus.PUBLISHED`, `ActivityVisibility.PUBLIC`, Occurrences `SCHEDULED` et filtre temporel existants. Les critères de composition Discovery restent au chantier 02. **Pas de modèle ni règle temporelle parallèle créée.** | `discovery/api/test_mature_discovery.py`, `discovery/test_m8b_mature_discover.py` |
| Occurrence : horaires et variantes | `activities/models.py` (`timing_kind`, `start_at`, `end_at`, dates/heures et timezone) ; `commerce/offer_price_facts.py::occurrence_variant_price_facts` | Les Occurrences gardent leurs identités et fenêtres. Le client ne doit pas reconstruire une variante depuis une description. **Réutilisation.** | `commerce/test_offer_price_facts.py`, `discovery/api/test_mature_discovery.py` |
| Commerce : prix réels | `commerce/selectors.py::applicable_offers`, `currently_available_offers` ; `commerce/offer_price_facts.py::offer_price_facts`, `offer_price_facts_many`, `occurrence_variant_price_facts` | `unknown/free/exact/range`, devise unique, offres actives dans leur fenêtre, prix unitaires, variantes bornées (2..12) et `fact_freshness=not_asserted` existent. Les remises, taxes, Quote/Payment ne sont **pas** des facts Discovery. **Aucun changement.** | `commerce/test_offer_price_facts.py` |
| Geography : places et divulgation | `geography/models.py::Place`, `SpacePlace` ; `discovery/presentation.py::_space_place_is_public` | Les coordonnées sont optionnelles, par paire et validées ; `SpacePlace` possède `is_public` et `is_active`. Les décisions de projection, rôle et sélection des lieux demeurent dans l'étape 02. **Aucun changement.** | `discovery/api/test_mature_discovery.py`, `mobile/test/dg_discovery_geography_test.dart` |
| Transport : itinéraires et départs | `transport/models.py::TransportRouteStop`, `TransportService`, `TransportDeparture` | Les positions, places, restrictions d'embarquement/débarquement, mode, Occurrence et contraintes de même Space sont propriétaires. Ne pas inventer de coordonnées, itinéraires ou places dans Discovery. **Aucun changement.** | `discovery/api/test_mature_discovery.py` (rôles spatiaux) |
| Opportunity : source et degré de connaissance | `opportunities/selectors.py::published_opportunities` ; `opportunities/knowledge.py::public_source_knowledge` | Révision publiée, sources actives bornées à huit avec indicateur de troncation, horodatage des observations ; `fact_freshness=not_asserted`. Contrôle de source ≠ certification des faits. **Aucun changement.** | `opportunities/test_public_source_knowledge.py` |
| Funding : ouverture, conditions, progression | `funding/models.py::FundingDetails`, `funding/selectors.py::funding_progress[_many]`, `funding_accepts_contributions`, `public_fundings` ; `funding/services.py::create_funding_contribution` | **Écart corrigé** : un Space non public/non recherchable, suspendu ou archivé ne publie plus de Funding dans la collection owner, et ne peut plus créer d'obligation de contribution nouvelle. Compte personnel inactif exclu. La fenêtre `opens_at/closes_at` et les montants restent owner-backed. | Tests préexistants `funding/tests.py`, `funding/test_discovery.py`, `funding/test_z15_api.py` ; deux nouveaux tests dans `funding/test_z15_api.py` |
| Service : publication et démarrage Journey | `services/views.py::public_services` ; `services/api_views.py::ServiceStartAPIView` ; `services/native_start.py` ; `services/selectors.py::service_opportunity_relation_for_viewer` | **Écart corrigé** : catalogue Services Web et démarrage natif partagent désormais le filtrage du Space public/recherchable, actif et non suspendu, ainsi que l'owner Profile actif. L'identité d'opération idempotente et la relation privée Journey → Opportunity demeurent propriétaires. | `services/test_native_start_api.py`, `services/test_owner_relations.py` ; deux nouveaux tests dans `services/test_native_start_api.py` |
| Preparation / Resources : contenu, versions et autorité | `preparation/services.py::can_view_resource`, `create_resource`, `publish_resource`, `replace_resource`, `retire_resource` ; `preparation/views.py::ResourceDownloadView`, `ResourceTextReadView` | Public/participant/restreint ont des droits distincts ; fichiers et textes restent livrés par les routes propriétaires avec `no-store`. Les tests de capacité d'affichage et poids inline relèvent des étapes 02–03. **Aucun changement.** | `preparation/tests.py`, `discovery/api/test_resource_previews.py` |

## 3. Implémentation ciblée livrée sur #522

### Funding : publication owner et contribution nouvelle

1. `funding/selectors.py::public_fundings` refuse désormais les Spaces qui ne sont pas `public_profile`, `searchable`, `lifecycle=active`, ou dont `verification_status=suspended`. Il refuse aussi un propriétaire personnel désactivé. Ne modifie pas les données, l'historique ou les obligations déjà créées.
2. `funding/selectors.py::funding_accepts_contributions` applique ces mêmes restrictions owner à la **création** de contributions, tout en conservant le test de fenêtre et la règle `PRIVATE` existante. Il ne fait ni remboursement, ni retrait ou annulation de Payment déjà produit.
3. `funding/services.py::create_funding_contribution` utilise le verrou existant et précharge `activity__space` et `activity__owner_profile` avant de décider et de créer une obligation.
4. `funding/test_z15_api.py` vérifie Space suspendu, archivé, non public ou non recherchable, absence de nouvelle `FundingContribution`, restauration du comportement quand l'owner redevient public, propriétaire personnel inactif.

### Services : un seul selector d'admission owner pour Web et natif

1. `services/views.py::public_services` sélectionne les Services publiés/publics dont le porteur est un Space public, recherchable, actif et non suspendu, ou un Profile propriétaire actif.
2. `services/api_views.py::_public_service_for_viewer` réutilise ce selector sans ajouter une deuxième exception locale ; l'éligibilité de Groupe reste contrôlée par le gate déjà présent.
3. `services/test_native_start_api.py` vérifie que GET/POST `/api/v1/services/<uuid>/start/` retournent 404 après retrait de la publication de l'owner, sans créer de Journey, et redeviennent accessibles après restauration ; propriétaire personnel désactivé également couvert.

**Invariants préservés :** aucun nouveau schéma/migration, aucune nouvelle autorité, aucun `profile_id` client, aucune mutabilité retroactive d'un Payment ou d'une Journey existante.

## 4. Contrat de consommation à transmettre à l'étape 02 (sans l'implémenter ici)

- **Commerce** : choisir Activity ou Occurrence selon le contexte admis ; ne pas rabattre les prix de deux sessions sur un seul prix fictif. `OfferPriceFacts.as_dict()` est un fait indicatif unitaire, non une Quote.
- **Activity / Occurrence** : identité de possibilité et variantes à composer à partir des IDs admis ; ne pas transformer les mentions de dates dans une description en champs `timing`.
- **Geography / Transport** : ne divulguer que les Place et roles dont le propriétaire confirme la publication ; coordonnées nulles ne deviennent pas des pins inventés.
- **Opportunity** : fenêtre owner, `current_revision` et `public_source_knowledge` ; source vérifiée ≠ faits certifiés actuels.
- **Funding** : **réutiliser exclusivement `public_fundings`** comme source publique avec gate Groupe existant ; `funding_accepts_contributions` pour savoir si une contribution est effectivement possible maintenant ; ne pas déclarer l'éligibilité individuelle.
- **Services** : `public_services` est maintenant le selector canonique de publication Web et API native ; les branches Discovery utilisant directement `ServiceDetails.objects.filter(...)` doivent être **réconciliées au chantier 02**, pas modifiées ici. Le handoff Service reste owner-backed.
- **Preparation** : distinguer visibilité des Resources, occurrence liée, publication, autorité du lecteur et existence physique ; le document n'est pas automatiquement un média de reconnaissance.

**Point d'intégration explicite :** `discovery/unified.py::public_service_discovery_item[s]` maintient un filtre `ServiceDetails` local historiquement distinct de `public_services`; le chantier 02 doit remplacer ou aligner ce gate avant de certifier la cohérence Web/natif. Ne pas appeler le chantier 01 une validation de tous les consommateurs Discovery.

## 5. Contrôles et limites

**Revues statiques effectuées :** inspection des sources ci-dessus et relecture sur GitHub des fichiers corrigés. Des tests de régression nouveaux sont présents, mais **ni leur exécution ni celle des tests existants ne sont attestées**. L'environnement d'édition GitHub de cette intervention ne fournit pas un checkout exécutable du dépôt ; le container ne peut joindre GitHub. L'absence de résultat ne vaut pas échec ni succès.

**Commandes ciblées prêtes, SANS CI globale :**

```bash
python manage.py test commerce.test_offer_price_facts opportunities.test_public_source_knowledge
python manage.py test funding.tests funding.test_discovery funding.test_z15_api
python manage.py test services.test_native_start_api services.test_owner_relations
python manage.py test preparation.tests discovery.api.test_mature_discovery
python manage.py check
python manage.py makemigrations --check --dry-run
```

Les tests Discovery dans cette liste sont **des gardes d'intégration des propriétaires**, pas l'ouverture anticipée du chantier 02.

## 6. Décision de sortie

- [x] Tous les domaines propriétaires attendus ont été inspectés et attribués à un selector/service existant.
- [x] Les vérités Commerce/Occurrence/Geography/Transport/Opportunity/Preparation ne sont pas dupliquées.
- [x] Les écarts Funding et Services constatés ont reçu des corrections propriétaires ciblées.
- [x] Quatre tests de régression owner ont été ajoutés (deux Funding, deux Service).
- [x] Le contrat de consommation et le risque de décalage Service/Discovery sont consignés pour le chantier 02.
- [ ] **Les tests ciblés n'ont pas été exécutés et leurs résultats ne sont pas attestés.**

**Statut d'ingénierie : IMPLÉMENTÉ, EN ATTENTE DE VALIDATION CIBLÉE.** Conformément à la règle séquentielle du registre, **ne pas commencer le chantier 02** tant que les tests ciblés n'ont pas confirmé la sortie et que le statut 01 n'a pas été changé en `FERMÉ`. Ne pas présenter le chantier 01 comme certifié par une CI inexistante.
