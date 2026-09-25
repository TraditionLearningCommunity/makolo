# Z15 — Réconciliation des capacités orphelines

> **Statut : chantier de fermeture backend.** Z15 ne crée pas une nouvelle expérience, ne refait pas W et ne construit ni desktop ni mobile. Il classe et expose proprement les capacités déjà présentes afin que Personnel, Espace et Platform restent trois contextes distincts.

## 1. Mission

Une capacité Makolo ne doit plus rester dans l'état « le code existe mais son contexte, son owner ou son contrat serveur sont indéterminés ».

Z15 applique la règle suivante :

```text
vérité propriétaire
→ selector / service / projection
→ contrat serveur permissionné
→ client futur
```

Aucun modèle ou état persistant Z15 n'est introduit.

## 2. Trois contextes

### PERSONAL

Le sujet est toujours `request.user` comme Profile global.

Les projections personnelles Mature restent propriétaires de leur composition : Maintenant, Découvrir, Mark, En cours, Moi, Journey, Access, Resources, Passport, Groups, Recognition personnelle, Loyalty personnelle et relation Partner personnelle.

Z15 ne crée pas de seconde projection personnelle. Les contrats Z1–Z14 restent canoniques.

### SPACE

Un Profile agit dans un Espace uniquement sous Mandate/Permission réel. TeamMembership, GroupMembership et `OrganizationMembership` ne suffisent jamais.

Z15 ajoute une projection d'inventaire permissionnée :

```text
GET /api/v1/organizations/workspaces/
GET /api/v1/organizations/workspaces/<slug>/
```

Elle ne possède aucune vérité métier. Elle indique seulement, pour l'Espace déjà autorisé :

- les capacités réellement visibles ;
- les actions réellement autorisées ;
- les owner APIs à consommer ;
- le statut du contrat quand une compatibilité historique subsiste.

### PLATFORM

Platform est séparé de Personnel et d'Espace.

Z15 ajoute une porte **serveur**, pas une UX Platform :

```text
GET /api/v1/platform/capabilities/
```

Elle est résolue exclusivement depuis les Permissions Platform et n'inclut aucune capacité personnelle ou Espace.

## 3. Classification auditée

| Capacité | Classe | État Z15 | Owner / contrat |
| --- | --- | --- | --- |
| Maintenant / En cours / Moi / Mark | PERSONAL | actif | projections Z existantes |
| Journey / Access / Resources / Passport / Groups | PERSONAL | actif | owners existants |
| Recognition personnelle | PERSONAL | actif | `/api/v1/recognition/me/` |
| Loyalty personnelle | PERSONAL | actif | `/api/v1/loyalty/me/` |
| Partner personnel | PERSONAL | actif | projection Moi/Partner existante |
| Partners Espace | SPACE | actif, auparavant partiellement orphelin de composition | selectors Partners + collections filtrables par Espace |
| Growth | SPACE | actif avec compatibilité Event | Growth owner + Analytics owner ; aucun stockage métrique Z15 |
| Analytics | SPACE | actif avec adaptateurs verticaux | analytics_app ; Event/Service restent des vues verticales |
| Loyalty Espace | SPACE | actif | Loyalty APIs ; collection de programmes filtrable par Espace |
| Recognition Espace | SPACE | **reconnecté** | nouveau contrat API owner-backed |
| Trust Espace | SPACE | **reconnecté** | résumé opérateur + demande de vérification API |
| Funding | SPACE/PERSONAL/PUBLIC | **reconnecté** | Activity + Funding + PaymentObligation |
| Scanner / contrôle | SPACE / Activity | actif avec compatibilité Event | Access décide le droit ; Scanner observe/valide |
| CRM / Audiences | SPACE | actif | CRM owner |
| Promotions | SPACE | actif | Promotions owner |
| Automation CRM | SPACE | actif, scoping corrigé | CRM permission + Automation runtime |
| Operations locales | SPACE / Activity / Occurrence | actif | Operations occurrence-scoped |
| Trust review staff | PLATFORM | actif, owner web contract | `platform.trust.review` |
| Operations globales | PLATFORM | actif | Operations Platform API |
| Subscription governance | PLATFORM | actif | Subscriptions owner |
| Recognition governance | PLATFORM | actif | Recognition Platform permissions |
| Opportunity curation | PLATFORM | actif | Opportunities owner |
| Discovery publique | PUBLIC | actif | Discovery |
| Funding publié | PUBLIC | actif | Funding public view + contribution authentifiée |
| Trust public | PUBLIC | actif | Trust public summaries / verify endpoints |
| Event/Ticket façades | LEGACY / COMPATIBILITY | conservées | verticales historiques, pas noyau transversal |
| Scanner Event gates/logs/live | LEGACY / COMPATIBILITY | conservés | adaptateurs autour d'Access / Activity |
| OrganizationMembership.role | LEGACY / COMPATIBILITY | aucune nouvelle autorité | Mandate reste source d'autorité |
| anciennes surfaces `network/` | LEGACY / COMPATIBILITY | non reconnectées comme feed | ActionNeed/Contribution/Group conservent leurs owners |
| Prospector | INTERNAL_RUNTIME | runtime actif | worker/leases/healthcheck |
| Observer | INTERNAL_RUNTIME | runtime actif selon activation | acquisition + worker |
| Interpreter | INTERNAL_RUNTIME | runtime actif | worker + material |
| Resolver | INTERNAL_RUNTIME | runtime actif | worker + resolution |
| Projector | INTERNAL_RUNTIME | Actor 7 présent | snapshot/delta, rebuild dry-run |
| cible Actor 8 / application Universe | LAB / NOT_DELIVERED | non livrée | aucune cible inventée |
| intelligence cumulative future | LAB / NOT_DELIVERED | hors Z15 | programme futur |

## 4. Partners

Les selectors Partners étaient déjà permissionnés par `partners.manage` / `partners.finance`, mais les collections mélangeaient les Espaces visibles.

Z15 conserve les APIs existantes et ajoute le filtre facultatif :

```text
?organization=<uuid-ou-slug>
```

sur partners, campaigns, codes, commissions et payouts.

Le filtre est appliqué **après** le selector de visibilité : il peut réduire le scope, jamais l'élargir.

Les métriques Partner restent dans Partners/Analytics. Z15 ne crée aucun second Analytics et ne transforme pas Partner en Team/Membership.

## 5. Growth et Analytics

Growth possède déjà ses APIs Space-scoped et ses Permissions canoniques.

Les dépendances restantes `MarketingLink → Event` et `EventFeedback → Event` sont classées `active_with_event_compatibility`. Elles ne justifient ni duplication Activity ni migration spéculative en Z15.

Analytics reste propriétaire de ses agrégats. Les métriques Event et Service sont des adaptateurs verticaux ; le read-model Espace ne les copie pas.

## 6. Loyalty et Recognition

Loyalty reste une relation d'avantages propre à un Espace. Recognition reste une économie de reconnaissance Makolo distincte.

Z15 ne fusionne aucun solde.

Pour Loyalty, l'API management existante est conservée et devient filtrable par Espace.

Pour Recognition, le backend possédait déjà le compte Espace et l'UX web mais pas de contrat API Espace. Z15 ajoute :

```text
GET  /api/v1/recognition/spaces/<space-id>/
POST /api/v1/recognition/spaces/<space-id>/rewards/<reward-id>/redeem/
POST /api/v1/recognition/spaces/<space-id>/redemptions/<redemption-id>/<accept|decline>/
```

Les lectures exigent `space.recognition.view` ou `space.recognition.spend`; les mutations exigent `space.recognition.spend`. L'idempotence et l'économie restent dans Recognition.

## 7. Trust

Trust reste séparé selon le sujet :

- PERSONAL : Proofs, Credentials, Journey feedback/report ;
- SPACE : état Trust opérateur, claims et demande de vérification ;
- PLATFORM : revue staff, disputes/reports/Proof review globaux.

Z15 ajoute uniquement le gap Espace :

```text
GET  /api/v1/trust/spaces/<space-id>/operator/
POST /api/v1/trust/spaces/<space-id>/verification-requests/
```

La projection Espace ne sérialise pas les notes privées Platform. Les décisions de revue restent Platform et ne sont pas déplacées dans l'Espace.

## 8. Funding

Funding était fonctionnel sur le Web et correctement construit sur Activity + PaymentObligation, mais sans API.

Z15 expose les services existants :

```text
GET  /api/v1/funding/?space=<space-id>
POST /api/v1/funding/
GET  /api/v1/funding/<id>/
PATCH /api/v1/funding/<id>/
POST /api/v1/funding/<id>/contributions/
```

Créer pour un Espace continue d'exiger `space.activities.manage` **et** `finance.manage`.

Gérer un financement continue d'exiger l'autorité Activity et Finance définie par `funding.services.can_manage_funding`.

Une contribution crée toujours une `PaymentObligation` via Payments. Z15 ne crée aucun Payment parallèle.

## 9. Scanner

Scanner reste un adaptateur opérationnel autour d'Access :

```text
Access = droit
Scanner = validation/observation
AccessUse = observation canonique
```

Les assignments sont déjà Activity/Occurrence-aware. Z15 ajoute seulement `?space=<uuid>` à leur collection afin qu'un client Espace puisse demander son scope sans reconstruire les liens Event/Activity.

Les routes Event gates/logs/live restent `LEGACY / COMPATIBILITY` tant que leurs consommateurs existent.

## 10. Automation, CRM, Audiences, Promotions

CRM/Audiences/Promotions sont déjà branchés : Z15 ne les reconstruit pas.

Un défaut a toutefois été confirmé dans la lecture Automation sans filtre : elle utilisait encore `OrganizationMembership.role` comme fallback.

Z15 remplace ce fallback par `space_ids_with_permission(..., crm.view)`.

Cela protège l'invariant :

```text
Membership != authority
```

Les modèles `CRMWorkflow` conservent encore des références Event/Ticket pour certains triggers historiques. Elles sont des compatibilités fonctionnelles ; Z15 ne les généralise pas sans migration métier démontrée.

## 11. Social / Network

Les anciennes routes `network/` ne sont pas remises dans la navigation.

Les responsabilités réelles restent :

- ActionNeed / ActionProposal : réseau d'action bilatéral ;
- Contributions : contenu contextuel ;
- Groups : owner Group ;
- Discover / Maintenant : projections lorsque le contexte l'exige.

Aucun feed générique n'est réintroduit.

## 12. Operations

Deux contrats distincts restent obligatoires :

```text
Operations Espace
→ Activity / Occurrence / Access / Queue / Placement / Checkpoint

Operations Platform
→ supervision globale / incidents / modération / workers
```

`/api/v1/platform/capabilities/` peut indiquer l'accès Platform Operations, mais ne copie pas les données Operations.

## 13. Runtime interne

Prospector, Observer, Interpreter et Resolver restent des runtimes internes. Leur existence n'impose aucune page utilisateur.

Projector est présent dans le runtime actuel comme Actor 7 : contrats snapshot/delta, mapping et `projector_rebuild --dry-run`.

Actor 8 n'est pas implémenté. Le rebuild dry-run ne pousse donc vers aucune cible inventée.

Le runtime courant gagne sur les anciens documents qui pourraient encore décrire Projector comme absent.

## 14. Sécurité

Z15 respecte :

- `request.user` comme identité authentifiée ;
- Mandate/Permission comme autorité ;
- selectors avant sérialisation ;
- 404 pour les détails privés cross-Space lorsque pertinent ;
- aucune donnée Platform dans le read-model Espace ;
- aucune finance Partner sans `partners.finance` ;
- aucune mutation Recognition Espace sans `space.recognition.spend` ;
- aucune donnée Trust opérateur sans `space.trust.view/manage` ;
- aucune autorité Automation depuis `OrganizationMembership.role` ;
- aucun AccessCredential dans Analytics/Workspace.

## 15. Persistance

Z15 ne crée aucun modèle et aucune migration.

Les ajouts vivent dans :

```text
selectors existants
services propriétaires
read models
API
tests
docs
```

## 16. Handoff W

W peut ensuite intégrer les modules Espace sans reconstruire les règles métier :

1. charger les Espaces depuis `/api/v1/organizations/workspaces/` ;
2. ouvrir `/workspaces/<slug>/` ;
3. rendre uniquement les modules fournis ;
4. suivre les owner links ;
5. afficher uniquement les actions présentes dans `capabilities`.

W ne doit pas :
- déduire l'autorité depuis Membership ;
- joindre plusieurs anciens dashboards pour savoir si un module existe ;
- injecter Platform dans la Console Espace ;
- reconstruire Growth/Analytics/Recognition/Trust/Funding depuis l'ORM.

La porte visuelle Platform reste hors Z15.
