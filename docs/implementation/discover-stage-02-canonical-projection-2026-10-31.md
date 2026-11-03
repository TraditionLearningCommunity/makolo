# Makolo — Découvrir : chantier 02, projection canonique Discovery

**Date :** 2026-10-31  
**Branche :** `fix/discover-a-continuation-context-20261014` ([PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522))  
**Livraison :** implémentation et tests de régression ajoutés ; exécution de tests/CI reportée à la certification finale sur instruction explicite de l'utilisateur.  
**Prérequis :** chantier 00 réconcilié ; chantier 01 implémenté dans les domaines propriétaires.  
**Frontière :** aucune modification Flutter, aucun nouveau modèle `Possibility`, aucune migration, aucun algorithme Molongo, aucune ouverture des chantiers 03–09.

## 1. Invariants conservés par le code préexistant

- `discovery/api/composition.py::compose_discovery` demeure le point de composition des quatre familles (`activity`, `service_activity`, `funding_activity`, `opportunity`) sur les candidats des propriétaires. Aucun nouveau ranking ou score client.
- `_combine_candidates` préserve l'ordre amont et déduplique par identité canonique de candidat ; les IDs et révisions propriétaires subsistent.
- `project_rows` et `detail_projection` produisent la même grammaire de possibilité, les faits et métadonnées connus ; l'endpoint détail ne remplace pas Search.
- Group eligibility, `request.user`, sauvegarde, relations personnelles et permissions owner continuent à déterminer l'accès, jamais une identité fournie par le client.
- Le token de continuation signé est lié à la requête et au viewer. **Il ne constitue pas un snapshot immuable** : une modification du corpus entre deux pages peut encore modifier les résultats recalculés. Cela n'autorise pas une promesse plus forte.

## 2. Écarts corrigés

| Réf. | Ancien comportement | Implémentation effectuée | Preuve de code |
| --- | --- | --- | --- |
| P02-A — Admission Services | `discovery/unified.py` reconstruisait un filtre de statut/visibilité inférieur au `services.views.public_services` de l'étape 01. Le détail et la collection pouvaient donc présenter un Service dont l'owner a retiré sa publication. | `public_service_discovery_item` et `public_service_discovery_items` réutilisent `public_services()` ; le gate de Groupe est conservé. | `discovery/unified.py`, tests `test_service_and_funding_admission_reuse_owner_publication_rules` |
| P02-B — Handoff Services | Le relevé des handoffs recherchait des `ServiceDetails` sur les IDs admis, sans passer par le selector de publication owner. | `_service_handoffs` passe par `public_services()` sur les IDs déjà admis. Aucune nouvelle capacité n'est calculée. | `discovery/api/composition.py::_service_handoffs` |
| P02-C — Ressources documentaires | `_activity_resource_previews` s'appuyait sur `status=PUBLISHED` et `visibility=PUBLIC`, sans vérifier la même autorité de lecture que `preparation:resource-text` et `preparation:resource-download`. Elle pouvait inclure du texte ou des titres devenus non consultables. | Contrôle par `preparation.services.can_view_resource(profile, resource)` sur le viewer courant, cache de contrôle borné à ce calcul par requête et contexte Activity/Occurrence. Métadonnées et contenu exclus ensemble si le lecteur serait refusé. | `discovery/api/composition.py::_activity_resource_previews`, test de retrait de la visibilité owner |
| P02-D — Portée des ressources | Une ressource d'une Occurrence non sélectionnée pouvait être présentée avec l'Activity agrégée. | Les `matching_occurrence_ids` admis bornent la présence de ressources spécifiques à une Occurrence. Les ressources Activity génériques restent disponibles ; aucun autre événement n'est inventé. | `project_rows` et `test_occurrence_specific_resource_stays_with_admitted_variant` |
| P02-E — Poids des TEXT inline | La collection N1 pouvait inclure un `text_content` public de taille arbitraire pour chaque Resource. | Aperçu par TEXT limité à **1 400 caractères**, budget cumulé par Activity à **8 400 caractères**. `text_truncated` informe honnêtement de la coupure ; `read_url` permet de lire le contenu entier chez Preparation. **Tous les titres/IDs de ressources autorisées sont toujours exposés, sans limite silencieuse de six ou treize.** | `DISCOVERY_RESOURCE_INLINE_CHARS`, `DISCOVERY_RESOURCE_ACTIVITY_INLINE_BUDGET`, tests TEXT et budget |
| P02-F — Liens externes historiques | Une URL conservée dans une ancienne donnée pouvait être sérialisée sans validation du protocole au moment de projeter, notamment sur les `OpportunitySource`. | Les liens externes public RESOURCE et Opportunity utilisent `_safe_public_http_url` : http(s), host valide non vide, sans identifiants d'URL ni contrôles ASCII de nouvelle ligne/tabulation. Une URL refusée devient `null`, sans inventer une destination. | `_safe_public_http_url`, `_opportunity_source_previews`, tests URL héritée |
| P02-G — Prix `unknown` | `project_rows` ne réinjectait Commerce que lorsque son état était connu ; l'adaptateur Presentation pouvait donc laisser une valeur dérivée malgré `unknown` du owner. | Lorsque le selector `offer_price_facts_many` a fourni une valeur, elle est toujours la vérité de prix projetée, y compris `unknown`, `no_applicable_offer` et `mixed_currencies`. Ne convertit pas l'inconnu en gratuit. | `project_rows`, test `test_collection_price_uses_commerce_unknown_and_exact_owner_truth` |
| P02-H — Pagination/API | Les exceptions `django.core.exceptions.ValidationError` de pagination et d'exploration n'étaient pas normalisées en erreur DRF côté collection/carte. Une continuation invalide devait au contraire être un rejet HTTP propre. | `DiscoveryItemsAPIView` et `DiscoveryMapAPIView` convertissent en `rest_framework.exceptions.ValidationError` (400), sans cacher les échecs. `paginated_projection` valide le curseur **avant** la composition coûteuse. | `discovery/api/views.py`, `composition.py::paginated_projection`, tests d'expiration/contexte/tampering/paramètres |

## 3. Tests ajoutés et ajustés

### `discovery/api/test_mature_discovery.py`
- Règles owner identiques collection/détail pour Service et Funding : publication Space, recherchabilité, archive, suspension ; récupération après rétablissement.
- Absence de divulgation d'une Resource lorsque Preparation refuse la consultation.
- Rejet d'une URL historique `javascript:` dans la projection publique d'une Opportunity.
- Rejet HTTP 400 de curseurs modifiés, de changements de query, de page size, de viewer, de paramètres invalides et de filtre temporel incompatible sur Map.
- Prix Commerce `unknown → exact → unknown/mixed_currencies` représenté sans fausse valeur.

### `discovery/api/test_resource_previews.py`
- Une ressource TEXT longue est tronquée dans la collection mais complète via son endpoint propriétaire `read_url`.
- Conservation de toutes les références avec budget total inline.
- Retrait propriétaire sans divulgation du titre ou du contenu ; endpoint refusé.
- URLs externes et liens avec identifiants ou sauts de ligne écartés.
- Les ressources spécifiques à une autre Occurrence ne se mélangent pas à la variante sélectionnée.

**Note de méthode :** l'ajout et la vérification du contenu de ces tests ne signifie **pas** qu'ils ont été exécutés. La CI, l'Android et les E2E ne sont pas des étapes de ce chantier ; ils sont reportés au chantier 09 sur demande de l'utilisateur.

## 4. Contrat projeté pour l'étape 03

1. Les médias de représentation continuent d'être admis par `presentations.media_selectors.public_presentation_media_for_activities` et `apply_recognition_media` ; ce chantier **n'a pas refait leurs droits, fichiers, révocations, origines ou caches**.
2. Les ressources `TEXT` et `FILE` ont des lecteurs propriétaires ; N1 expose un résumé/document, pas une nouvelle autorité de lecture. En cas de refus ultérieur, la route de Preparation revalide le droit.
3. Les images de reconnaissance, les ressources de Journey, les documents, les liens externes et les assets privés restent des objets distincts.
4. Le chantier 03 doit étudier les anciens chemins publics `PresentationAsset.file` et les `private_file`, le stockage, la révocation et les URL first-party, sans dupliquer le contrat Discovery.
5. L'optimisation d'acquisition (préchargement, disponibilité offline, Reader) reste du ressort de 03/08 ; elle ne doit jamais contourner un refus de lecture.

## 5. Frontières des prochaines étapes

- **04** : agencement N1, dates lisibles, contextualisation, gabarits, responsive Web/Flutter.
- **05** : l'écran Map autonome Flutter n'hérite pas encore systématiquement de la query/liste/sélection. Le serveur map n'est **pas** une deuxième source de pertinence, mais la continuité UX est un travail distinct. Les scénarios avec critères changés sont couverts ici uniquement au niveau de l'erreur de continuation.
- **06** : N2, variantes/comparaison conditionnelle et profondeur métier.
- **07** : Save/Watch/Share/engagement N3, décisions et mutation dans les propriétaires.
- **08** : snapshot, restauration du scroll et de l'état, rétention locale, quotas, révocation offline.
- **09** : tests exécutés, CI, device et décision de fusion.

## 6. Critères de sortie de la livraison de code 02

- [x] Un seul selector Services pour Web/natif/Discovery, avec le filtre de Groupe inchangé.
- [x] Admission collection et détail des quatre familles préservée ; tests de retrait owner ajoutés.
- [x] Identité et déduplication des candidats non modifiées, aucun score nouveau.
- [x] Ressources admises par Preparation et par Occurrence, sans fuite de texte privé.
- [x] Payload inline TEXT borné, sans suppression de références légitimes.
- [x] Prix du selector Commerce prioritaire, même inconnu.
- [x] Validation cursor/requête et réponse HTTP 400 explicite.
- [x] Tests ciblés créés dans le dépôt ; documentation et handoff à 03 préparés.
- [ ] Exécution de Django/PostgreSQL, Flutter, CI, Android : **différée, non revendiquée**.

**Décision : CHANTIER 02 — IMPLÉMENTATION LIVRÉE.** La certification des résultats d'exécution attend le chantier 09. Aucun chantier 03 n'a été exécuté dans cette livraison.
