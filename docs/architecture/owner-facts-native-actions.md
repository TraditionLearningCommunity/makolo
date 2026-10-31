# Contrats propriétaires — prix, relations, actions et connaissance

> Chantier serveur transverse, **sans nouveau domaine métier**. Base initiale :
> `main@d0f0ec421c94c255fa4c0acd3509938a70c6322f`.
> Les tests, migrations, selectors et API en cours priment sur ce document.
> Ce texte décrivait initialement le sous-chantier des owners ; sa formule de
> périmètre « ne modifie pas Discovery ni Flutter » est **historique** et ne
> décrit pas à elle seule toute la PR #522 après consolidation.
> Relevé actuel : [chantier 01 / propriétaires](../implementation/discover-stage-01-owner-facts-2026-10-31.md).
> Les tests ciblés de ce relevé n'ont pas encore été exécutés.

## Problème et frontière

La collection Découvrir n'a pas à fabriquer un prix, déduire des relations,
transformer un lien Web en mutation native, ou déduire l'actualité d'un fait
de la date de génération d'une réponse.

```text
owner métier → selector / read model propriétaire → composition autorisée → client
```

Chaque consommateur décide **quand demander** un calcul plus coûteux ou une
mutation. Les propriétaires gardent l'autorité sur la vérité, les permissions,
les contraintes, la temporalité et le cycle de vie.

## Commerce — faits de prix

`commerce.offer_price_facts.offer_price_facts(activity=…)` ne regarde que
les Offers génériques réellement applicables à l'Activity.
`offer_price_facts(occurrence=…)` inclut les Offers applicables à cette
Occurrence et les Offers Activity réellement partagées.

Le contrat `OfferPriceFacts.as_dict()` distingue :

- `unknown` : aucune Offer active dans la fenêtre ou plusieurs devises non
  convertibles sans taux ;
- `free` : Offer(s) explicitement à zéro ;
- `exact` : un même montant unitaire connu ;
- `range` : plusieurs montants unitaires connus dans une devise ;
- `minimum`, `maximum`, `currency`, `offer_count` et `reason` qualifient
  exactement l'échantillon propriétaire utilisé.

`occurrence_variant_price_facts(occurrences=[…])` calcule **à la demande**,
pour 2 à 12 Occurrences distinctes de la même Activity, les termes par
Occurrence et `variant_dependent` seulement lorsque leurs prix constatés
diffèrent. Le consommateur doit avoir préalablement résolu la visibilité
des Occurrences et l'éligibilité du viewer ; ce selector n'est pas exposé
directement par ID dans une API publique.

Ces montants sont des **prix unitaires d'Offers**, et ne constituent jamais
un total client payé : taxes, frais, discounts, choix de paiement, Capacity
et Quote finale restent les responsabilités des services Commerce/Payment.

`owner_updated_at` signifie modification de ligne propriétaire, pas
vérification du prix réel. `earliest_offer_end_at` est une borne connue de
la fenêtre d'une Offer, pas la validité garantie de toute la collection.
`fact_freshness` reste `not_asserted`.

## Opportunities — connaissance et fraîcheur

`opportunities.knowledge.public_source_knowledge(opportunity_id)` ne répond
que pour les Opportunities publiées avec une révision publiée.

Le résultat borne les observations des sources **actives**, expose les
`last_checked_at`/`verified_at` réellement connus et la révision
observée, mais aucune note privée, empreinte de suivi ou identité de
curateur. Les autres statuts, révisions et secrets ne sont pas rendus publics.
Un contrôle réussi de la source **ne certifie pas** les délais, montants,
conditions ou capacités de l'Opportunity : `fact_freshness=not_asserted`.
Le drapeau `source_observations_truncated` évite de feindre
l'exhaustivité lorsque plus de huit sources existent.

Les contrôles d'autres propriétaires (Commerce, Capacity, Occurrence,
Funding, etc.) devront garder la même distinction quand ils disposent
d'observations propres.

## Services — relation canonique et divulgation

`services.selectors.service_opportunity_relation_for_viewer(journey_id, viewer)`
lit le lien déjà persisté dans `ServiceJourneyContext` : la Journey et
l'Opportunity sélectionnée avec la révision épinglée. Il passe
obligatoirement par `service_journeys_visible_to(viewer)`.

Cette relation est **privée au parcours autorisé** ; elle ne devient
jamais automatiquement une complémentarité publique entre deux
Possibilities Discovery, ni une permission sur l'Opportunity externe.
En absence de lien, ou pour un viewer non autorisé, le résultat est `None`.

## Services — vrai point de démarrage natif

`GET /api/v1/services/<uuid:service_id>/start/` fournit le contrat
de préparation : références du Service, politique Opportunity,
capability `start`, contraintes et lien de mutation.

`POST` vers le même endpoint, authentifié et avec en-tête
`Idempotency-Key` (16 à 128 caractères autorisés), accepte seulement
`objective` (maximum 1000 caractères) et `opportunity` lorsqu'elle est
admise par la politique Services.

Le serveur :

1. réutilise les règles de publication des Services et la Group Eligibility
   du Profile connecté ; ne lit aucun `profile_id` ou bénéficiaire arbitraire ;
2. utilise `ServiceStartForm` pour les contraintes de la verticale ;
3. appelle `create_service_journey`, qui demeure l'unique propriétaire de
   la mutation, de sa Journey, du template publié et de la révision liée ;
4. stocke un SHA-256 de la combinaison actor, Service et clé d'opération dans
   le `ServiceJourneyContext` existant ;
5. rend `201` pour la création, `200` pour un rejeu strictement identique,
   ou `409 idempotency_conflict` pour une même clé avec un autre payload ;
6. retourne une référence API vers la Journey créée, jamais une page HTML.

Un rejeu strictement identique renvoie l'ancienne Journey même si
l'Opportunity épinglée a changé de publication depuis la création. Une
perte d'autorisation de voir le Service, elle, continue d'interdire l'accès.

**Migration justifiée :**
`services.0005_service_start_operation_fingerprint` ajoute un champ unique
nullable au modèle existant. Les Journeys Web et historiques gardent
`NULL` et ne sont pas backfillées artificiellement. Aucun nouveau modèle
ni nouvelle table de projections n'est introduit.

## Intégration future (pas dans cette branche)

Discovery pourra composer les résultats **lorsqu'ils sont admissibles** :

- prix exact/range par owner, sans transformer l'absence en gratuité ;
- relation de contexte seulement sous autorisation, jamais déduite du texte ;
- Service handoff API uniquement si l'utilisateur et la politique permettent
  réellement l'action ;
- observations de source et état de connaissance sans garantie d'actualité.

La comparaison libre de deux objets n'a **pas** de route générique :
le domaine doit définir ce qui est comparé (prix unitaires, total final,
readiness, échéances, distance, etc.) et les permissions de chacun.
La lecture des variantes Commerce est disponible au niveau owner avant
qu'un endpoint autorisé soit justifié.

## Tests et gates

Tests ciblés à exécuter :

```bash
DJANGO_ENV=test python manage.py check
DJANGO_ENV=test python manage.py makemigrations --check --dry-run
DJANGO_ENV=test python manage.py test \
    commerce.test_offer_price_facts \
    opportunities.test_public_source_knowledge \
    services.test_owner_relations \
    services.test_native_start_api
```

Puis exécuter les tests pertinents de Commerce, Opportunities et Services,
ainsi que PostgreSQL pour l'unicité et les rejeux concurrents. Ne pas
fusionner si la CI est rouge. Les scénarios Guest, autre Profile, Group gate,
conflit d'idempotence et compatibilité Web sont des critères de sortie.


## Mise à jour : publication du porteur et interdiction des nouveaux engagements (31 octobre 2026)

La publication de l'Activity ne suffit plus à exposer un Funding ou un
Service porté par un Espace qui a retiré son profil public/recherchable,
qui est archivé ou suspendu. Le selector propriétaire doit contrôler
`Organization.public_profile`, `searchable`, `lifecycle=active`
et `verification_status != suspended`. Une Activity personnelle
avec un propriétaire `User.is_active=False` n'est pas une offre publique.

- **Funding** : `public_fundings` applique ces conditions à la découverte et
  à la lecture publique. `funding_accepts_contributions` interdit également
  la **création d'une nouvelle contribution et de son PaymentObligation**
  lorsqu'un porteur rétracte sa publication ou est suspendu. L'API de récupération
  d'une contribution déjà créée demeure distincte de cette décision ;
  aucune annulation rétroactive de paiement n'est inférée.
- **Services** : `services.views.public_services` est le selector commun
  du catalogue Web et du démarrage natif. `services.api_views` réutilise
  ce selector avant le contrôle d'éligibilité de Groupe, sans déléguer de
  Permission à Discovery. Les Journeys existantes ne sont pas effacées.
- **Consommateur Discovery** : `discovery/unified.py` contient encore un
  filtre local Service historiquement plus large ; sa réconciliation est une
  obligation explicite de l'étape 02, non une raison de démultiplier le selector.

Quatre tests de non-régression ont été ajoutés dans
`funding/test_z15_api.py` et `services/test_native_start_api.py` :
retrait du profil public, fin de recherchabilité, archive, suspension,
inactivation de propriétaire personnel, absence de nouvelle contribution ou
Journey. **Écriture vérifiée sur la branche, exécution non attestée.**
