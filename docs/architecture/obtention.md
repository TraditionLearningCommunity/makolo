# Makolo — Verticale Obtention

> **Statut : contrat d’architecture et d’implémentation de la verticale Obtention.**
> Base de conception : `main@f64e5dd3b7026ae9057284ed17d884065184f8f6`.
> Le runtime courant gagne toujours sur ce snapshot.

## 1. Intention

Obtention est une verticale d’`Activity` dont le résultat propre consiste à obtenir effectivement une chose, une ressource ou son usage.

Elle respecte :

> **backend générique, métier contextuel.**

Le noyau reste :

```text
Activity
  ├─ Occurrence(s)
  └─ Journey(s)
```

Obtention n’ajoute que les vérités irréductibles nécessaires à cette famille métier.

## 2. Vérités propriétaires

La verticale possède :

- l’identité `ObtentionDetails` rattachée 1:1 à l’`Activity` ;
- une configuration versionnée et publiée ;
- les `Target` : ce qui doit réellement être obtenu ;
- les `Mode` admissibles : `BUY`, `RENT`, `BORROW`, `RECEIVE`, `EXCHANGE`, `OTHER` ;
- la sémantique de fulfillment : résultat attendu, règle `ALL|ANY|AT_LEAST_N`, confirmations éventuellement exigées ;
- le contexte exact d’une Journey : version de configuration et mode choisis ;
- le constat quantitatif de réception par cible et les confirmations réellement requises.

La verticale ne possède pas :

- Journey/Steps/Blockers/Assignments ;
- Forms ;
- Resources ;
- Requirements/Assessments ;
- Readiness ;
- Offer/Order ;
- Payment ;
- Access ;
- Capacity ;
- Transport ;
- Proof/Trust.

Ces faits restent dans leurs domaines propriétaires.

## 3. Versioning

Une configuration publiée est structurellement immuable.

Toute révision crée une nouvelle version puis retire la version précédemment publiée. Chaque Journey Obtention pinne :

```text
Journey
  → ObtentionConfiguration exacte
  → ObtentionMode exact
```

Une Journey active ne change donc jamais de cible, de mode admissible, de Requirement ou de critère d’accomplissement parce que le porteur modifie ensuite l’Activity.

## 4. Target et Offer

`ObtentionTarget` répond à :

> Qu’est-ce qui doit être obtenu ?

`Offer` répond éventuellement à :

> Quelle proposition commerciale peut aider à l’obtenir ?

Une cible n’exige aucune Offer Makolo. Elle peut être satisfaite par une source externe, un don, un prêt, plusieurs offres ou une combinaison de sources.

Les caractéristiques contextuelles non canoniques d’une cible sont bornées dans `characteristics` ; elles ne justifient pas une taxonomie globale ou un modèle produit parallèle.

## 5. Modes et Journey workflow

Le mode d’Obtention exprime la relation métier. Il n’est ni un `PaymentMode`, ni un `WorkflowKind`.

Journey fournit désormais le workflow générique :

```text
FULFILLMENT
```

Il représente un parcours d’accomplissement sans prétendre qu’un don, un prêt ou une attribution est un achat.

Les workflows existants `PURCHASE`, `ORDER_APPROVAL` ou `RESERVATION` peuvent être choisis lorsqu’ils décrivent réellement le lifecycle transversal nécessaire.

## 6. Fulfillment

Le fulfillment Obtention est dérivé à partir de la configuration pinnée et des constats de réception.

Une cible est satisfaite lorsque :

1. la quantité effectivement reçue atteint la quantité cible ;
2. la confirmation bénéficiaire existe lorsqu’elle est requise ;
3. la validation du porteur existe lorsqu’elle est requise.

La règle de configuration agrège ensuite les cibles par `ALL`, `ANY` ou `AT_LEAST_N`.

Même lorsque ce contrat vertical est satisfait, la Journey ne peut être clôturée que si la projection `Readiness` canonique est `READY`.

Ainsi, ne suffisent jamais à eux seuls :

- une page ouverte ;
- une Order créée ;
- un Payment réussi ;
- un formulaire soumis ;
- un article expédié ;
- une Step quelconque terminée.

## 7. JourneyPlanTemplate générique

Le besoin de parcours reproductible n’est pas propre à Obtention.

Le domaine Journey possède donc :

- `JourneyPlanTemplate` versionné ;
- `JourneyPlanTemplateStep` ;
- dépendances de Steps ;
- matérialisation vers de vraies `JourneyStep`.

Une Step de template déclare son acteur :

```text
beneficiary | operator
```

La matérialisation ne transfère aucune Permission.

Une Step opérateur crée l’affectation de dossier nécessaire, mais l’écriture reste soumise à la Permission Activity correspondante. Une Step bénéficiaire peut être accomplie seulement par le bénéficiaire auquel elle appartient.

Le modèle historique `ServicePlanTemplate` n’est pas copié en `ObtentionPlanTemplate`. Services conserve sa persistance historique tant qu’une migration dédiée n’est pas nécessaire à son contrat ; les nouvelles compositions génériques peuvent utiliser `JourneyPlanTemplate`.

## 8. Requirements génériques

Le package `requirements` conserve son kernel d’évaluateurs et ajoute la persistance horizontale nécessaire aux nouvelles compositions :

- `RequirementDefinition` versionné par Activity ;
- `JourneyRequirementAssessment` par Journey.

Les persistances historiques Services/Subscriptions ne sont ni déplacées ni backfillées artificiellement.

Une configuration Obtention lie les versions exactes de Requirements via un lien de composition. Un Requirement de mode `action` peut référencer la clé d’une Step du plan. Dans ce cas, la completion de cette Step satisfait le Requirement par projection ; Requirement et Step restent deux vérités distinctes.

Les états génériques alimentent Readiness :

- `satisfied` → satisfait ;
- `not_applicable` → non applicable ;
- `unassessed|pending` → attente ;
- `unsatisfied` obligatoire → blocage.

## 9. Forms et Resources

Obtention réutilise directement les domaines existants :

- `questionnaires` pour Forms/FormVersion/FormRequest/FormResponse ;
- `preparation` pour `ActivityResource` et ressources de Journey.

L’interface de configuration expose les gestionnaires existants. Une Resource informative n’est jamais transformée implicitement en obligation ; une action obligatoire doit être représentée par une Step, un Requirement ou un autre fait canonique approprié.

## 10. Occurrences

Une réalisation datée utilise une vraie `Occurrence` de l’Activity.

La verticale expose une création contextualisée de date/disponibilité, mais persiste exclusivement dans `activities.Occurrence`.

Une Journey peut ensuite cibler l’Occurrence choisie. Aucun `ObtentionOccurrence` n’existe.

## 11. Commerce, Payment, Capacity, Access, Transport, Proof et Trust

Ces domaines restent indépendants.

Une Journey Obtention peut les composer lorsqu’ils existent. Leur état contribue à Readiness selon leurs contributeurs canoniques.

En particulier :

```text
Payment.succeeded
≠ Obtention fulfilled
```

```text
Order created
≠ target received
```

```text
Access
≠ AccessCredential
```

```text
document possessed
≠ Requirement satisfied
```

## 12. Autorité

Le porteur logique de l’Activity reste exactement un Profile ou un Space.

Créer au nom d’un Space exige `SPACE_ACTIVITIES_MANAGE`.

Configurer l’Obtention, valider une remise ou évaluer un Requirement exige une vraie autorité Activity via `can(... ACTIVITY_MANAGE ...)`.

Une `JourneyAssignment` n’accorde pas la Permission. Une TeamMembership/Membership n’accorde pas la Permission.

Le bénéficiaire peut uniquement effectuer ses actions personnelles explicitement prévues : démarrer sa Journey, progresser ses propres Steps et confirmer ce qu’il a réellement reçu.

## 13. API

Namespace domaine :

```text
/api/v1/obtention/
```

Principales opérations :

```text
GET/POST  /api/v1/obtention/
GET/PATCH /api/v1/obtention/{id}/
POST      /api/v1/obtention/{id}/occurrences/
POST      /api/v1/obtention/{id}/journeys/

GET       /api/v1/obtention/journeys/{id}/
POST      /api/v1/obtention/journeys/{id}/steps/{step}/start/
POST      /api/v1/obtention/journeys/{id}/steps/{step}/complete/
POST      /api/v1/obtention/journeys/{id}/targets/{target}/receipt/
POST      /api/v1/obtention/journeys/{id}/targets/{target}/operator-confirm/
POST      /api/v1/obtention/journeys/{id}/requirements/{assessment}/assess/
POST      /api/v1/obtention/journeys/{id}/fulfill/
```

Les réponses privées sont `private, no-store`.

Les profondeurs Journey filtrent le queryset par bénéficiaire ou permission Activity avant résolution de l’ID ; un tiers reçoit donc `404`, pas une fuite d’existence.

Les configurations d’evaluator Requirements restent serveur et ne sont pas exposées dans la projection publique.

## 14. Web

Surfaces :

- création/configuration porteur ;
- détail public ;
- ajout d’Occurrence ;
- démarrage de Journey par mode ;
- dossier bénéficiaire ;
- Steps ;
- Requirements ;
- confirmations de réception ;
- validations porteur ;
- fulfillment final.

La grammaire produit est contextuelle via `core.product_language`. Exemple :

```text
BUY, porteur       → Vente / Mettre en vente
BUY, bénéficiaire  → Achat / Acheter
RENT, porteur      → Mise en location
RENT, bénéficiaire → Location / Louer
BORROW             → Prêt / Emprunt
RECEIVE            → Distribution / Recevoir
```

Le backend reste stable ; les mots changent selon mode et perspective.

## 15. Migrations

Le chantier est expand-compatible :

- Journey ajoute `FULFILLMENT` ;
- Journey ajoute ses nouveaux templates génériques sans supprimer `ServicePlanTemplate` ;
- Requirements ajoute une nouvelle persistance générique sans déplacer les agrégats historiques ;
- Obtention ajoute ses propres tables nouvelles ;
- aucune donnée historique n’est inventée ;
- aucune migration destructive.

## 16. Anti-features

Le chantier n’introduit pas :

- `ObtentionJourney` ;
- `ObtentionStep` ;
- `ObtentionRequirement` ;
- `ObtentionForm` ;
- `ObtentionResource` ;
- `ObtentionOrder` ;
- `ObtentionPayment` ;
- `ObtentionAccess` ;
- `ObtentionCapacity` ;
- `ObtentionReadiness` ;
- sous-verticales Sale/Rental/Borrow/Distribution ;
- moteur de règles arbitrary ;
- transfert implicite d’autorité.

## 17. Gates de sortie

La verticale est fermée seulement si :

- migrations fresh et upgrade passent ;
- `makemigrations --check --dry-run` est propre ;
- création Profile et Space fonctionne selon les Permissions ;
- versioning protège les Journeys actives ;
- modes multiples fonctionnent ;
- Steps/Requirements/Forms/Resources/Occurrences composent leurs domaines propriétaires ;
- paiement/commande seuls ne clôturent pas la Journey ;
- fulfillment réel et Readiness sont nécessaires ;
- Web et API couvrent porteur et bénéficiaire ;
- IDOR est négatif ;
- grammaire contextuelle est testée ;
- CI est verte.
