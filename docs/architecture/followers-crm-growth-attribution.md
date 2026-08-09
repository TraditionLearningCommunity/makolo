# Followers, CRM enrichi et attribution campagne → vente

## Objectif

Cette évolution relie la découverte sociale, le CRM organisateur, les campagnes de communication et la conversion commerciale sans confondre les droits de la plateforme, les préférences globales du compte et les consentements propres à une organisation.

La chaîne cible est :

```text
Participant
  ↓ suit
Organisateur
  ↓ préférences propres à cette organisation
Nouveaux événements / annonces
  ↓
Audience CRM dynamique
  ↓
Campagne réutilisable
  ↓ lien signé
Clic
  ↓
Commande
  ↓
Paiement / confirmation
  ↓
Vente attribuée à la campagne
```

## Suivre un organisateur

`OrganizationFollow` relie un compte Makolo à une `Organization`. Cette relation est distincte de `OrganizationMembership` : suivre une organisation ne donne aucun droit sur son espace de travail.

Chaque abonnement possède quatre préférences :

- notifications Makolo pour les nouveaux événements ;
- notifications Makolo pour les annonces ;
- e-mail en plus pour les nouveaux événements ;
- e-mail en plus pour les annonces.

Les options e-mail sont secondaires à leur canal principal : désactiver les notifications d'un type désactive aussi son e-mail associé.

### Consentement

Suivre un organisateur **n'est pas** un opt-in e-mail automatique. Les e-mails d'un organisateur doivent être activés explicitement. Lorsque ce choix est fait, le contact CRM de cette organisation reçoit un consentement local avec la source `organization_follow_preferences`.

Un désabonnement depuis une campagne d'une organisation :

1. désabonne le `CRMContact` de cette organisation ;
2. coupe les options e-mail du `OrganizationFollow` correspondant ;
3. ne change pas `NotificationPreference.marketing_notifications` du compte ;
4. ne désabonne pas le participant des autres organisateurs.

Les préférences globales Makolo restent un garde-fou supérieur. Un utilisateur qui coupe les e-mails ou le marketing au niveau du compte ne doit pas recevoir une campagne parce qu'un organisateur conserve un consentement local.

## Nouveaux événements

La publication d'un événement déclenche un signal après commit. Les followers ayant activé `notify_new_events` reçoivent une notification Makolo dédupliquée par événement/utilisateur. Le canal e-mail n'est ajouté que lorsque `email_new_events` est actif et reste soumis aux préférences globales.

## Contacts CRM depuis les followers

Les followers alimentent le CRM comme les commandes, billets et waitlists. Le contact reste isolé par `Organization` : un même utilisateur peut donc avoir des préférences, tags, champs et consentements différents auprès de plusieurs organisateurs.

## Tags CRM

`CRMTag` appartient à une organisation. `CRMContactTag` matérialise son affectation à un contact et conserve l'auteur de l'affectation.

Les segments peuvent exiger plusieurs tags. Les tags sont combinés avec une logique **ET** : un contact doit posséder tous les tags demandés.

Aucun membre d'une autre organisation ne peut affecter un tag à un contact hors de son périmètre.

## Champs CRM personnalisés

`CRMCustomField` permet à une organisation de définir ses propres données structurées :

- texte ;
- nombre ;
- oui/non ;
- date ;
- liste de choix.

`CRMContactFieldValue` conserve la valeur et le dernier membre ayant effectué la mise à jour.

Les valeurs sont validées par type dans le service CRM. Une liste de choix refuse toute valeur non déclarée. Les segments peuvent appliquer des filtres exacts via `custom_filters`, par exemple :

```json
{
  "niveau": "premium",
  "entreprise": "SMNA"
}
```

Les clés correspondent aux `CRMCustomField.key` actifs de l'organisation.

## Audience followers

`AudienceKind.FOLLOWERS` constitue une audience dynamique basée sur `OrganizationFollow`. Elle peut être combinée avec le consentement marketing, des tags, une ville/pays et des champs personnalisés.

Le segment ne copie pas une liste d'utilisateurs : il est recalculé depuis les sources de vérité jusqu'au snapshot de campagne.

## Modèles de campagne

`CampaignTemplate` est propre à une organisation et stocke :

- type de communication ;
- objet ;
- pré-en-tête ;
- corps ;
- CTA ;
- état actif ;
- compteur d'utilisation.

Créer une campagne depuis un modèle copie son contenu dans `CommunicationCampaign`. Le snapshot rend donc la campagne historiquement stable même si le modèle est modifié plus tard.

## Attribution campagne → vente

### Lien signé

Lorsqu'une campagne avec `track_conversions=True` possède un CTA, Makolo ne met pas directement l'URL finale dans l'e-mail. Il génère un lien signé vers :

```text
/crm/c/<signed-token>/
```

Le jeton identifie un `CampaignRecipient` et sa campagne sans exposer un identifiant forgeable comme preuve d'attribution.

À l'ouverture du lien :

1. signature et fenêtre d'attribution sont vérifiées ;
2. le clic est comptabilisé ;
3. le destinataire de campagne est enregistré dans la session ;
4. le navigateur est redirigé vers le CTA réel.

Pour un client API/mobile, le même jeton signé peut être envoyé dans `campaign_token` lors de `POST /api/v1/tickets/orders/`.

### Création de commande

La prochaine commande compatible peut créer un `CampaignAttribution`. Makolo vérifie :

- même organisation ;
- même événement si la campagne est liée à un événement ;
- fenêtre d'attribution toujours valide ;
- une seule attribution CRM par commande.

L'attribution partenaires/ambassadeurs peut coexister : les deux domaines décrivent des canaux différents et ne s'écrasent pas.

### Cycle de vérité

Une commande payante crée une attribution `pending`. La vente n'est pas considérée comme une conversion avant `TicketOrder.status=confirmed`.

```text
clic → order pending → attribution pending
                    ↓ paiement confirmé
                order confirmed
                    ↓
             attribution confirmed
```

Une annulation ou expiration inverse l'attribution :

```text
confirmed/pending → order cancelled/expired → attribution reversed
```

`revenue_amount` et `currency` sont des snapshots de la commande confirmée. Les métriques regroupent les revenus par devise et ne mélangent jamais USD, CDF ou autres monnaies.

## Métriques de campagne

Le détail de campagne et l'API exposent :

- audience snapshot ;
- envoyés, ignorés, échecs ;
- destinataires ayant cliqué ;
- nombre total de clics ;
- taux de clic ;
- conversions confirmées ;
- conversions inversées ;
- taux clic → conversion ;
- revenu attribué par devise.

Makolo n'ajoute pas de pixel d'ouverture invisible. Les métriques reposent sur des événements observables et utiles : livraison, clic volontaire et conversion métier.

## Autorisations

Owner/Admin et Marketing peuvent gérer tags, champs, modèles, segments et campagnes. Event manager conserve sa lecture CRM prévue par la matrice d'autorisation. Finance et Scanner n'obtiennent aucun droit CRM par implication.

Les participants ne voient que leurs propres abonnements organisateur via le web ou `/api/v1/organizations/follows/`.

## API principale

```text
GET/POST   /api/v1/organizations/follows/
PATCH/DEL  /api/v1/organizations/follows/<id>/

GET/POST   /api/v1/crm/tags/
GET/POST   /api/v1/crm/custom-fields/
GET/POST   /api/v1/crm/templates/
POST       /api/v1/crm/contacts/<id>/tags/
DELETE     /api/v1/crm/contacts/<id>/tags/<tag-id>/
POST       /api/v1/crm/contacts/<id>/fields/<field-id>/
```

Les endpoints CRM existants de contacts, segments et campagnes restent la frontière principale d'accès.

## Invariants à préserver

1. Following ≠ rôle organisateur.
2. Following ≠ consentement marketing implicite.
3. Désabonnement organisation A ≠ désabonnement organisation B.
4. Les préférences globales du compte restent prioritaires.
5. Les tags/champs ne traversent jamais les organisations.
6. Une campagne ne peut attribuer une commande d'une autre organisation ou d'un autre événement imposé.
7. Une attribution n'est revenue confirmé qu'après confirmation réelle de la commande.
8. Annulation/expiration inverse l'attribution.
9. Les devises restent séparées.
10. Aucun pixel d'ouverture caché n'est requis pour mesurer la conversion.
