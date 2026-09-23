# Z10 — Continuité inter-surfaces de l'expérience personnelle

## Objet

Z10 ferme la continuité entre les projections personnelles déjà livrées. Il n'introduit ni domaine transversal, ni modèle persistant, ni état de navigation.

Règle :

```text
une réalité canonique
→ un owner métier
→ plusieurs projections UX
→ identité kind + id stable
→ links et capabilities évalués serveur
```

Un `key` opaque de projection reste une identité de ligne dérivée. Il ne remplace jamais l'identité métier `kind + id`.

## Propriétaires

```text
Activity / Occurrence                  -> Activities
Journey                                -> Journeys
Requirement                            -> Requirements
Readiness                              -> projection dérivée
Access                                 -> Access
Capacity                               -> Capacity
Dossier / Project                      -> Objectives
PersonalAsset                          -> Personal Assets
Proof / Credential                     -> Trust
Passport                               -> Sharing
Group                                  -> Groups
Recognition                            -> Recognition
Loyalty                                -> Loyalty
Partner                                -> Partner
Live / Queue / Placement / Checkpoint  -> Operations
```

Les surfaces `Maintenant`, `En cours`, `Historique`, `Moi`, `Jour J` et `Makolo Mark` ne possèdent aucune de ces vérités.

## Matrice de convergence

| Surface source | Référence canonique | Destination | Owner | Capability / handoff | Endpoint principal | Scope |
| --- | --- | --- | --- | --- | --- | --- |
| Découvrir | Activity / Occurrence | détail puis engagement owner-backed | Activities / verticale propriétaire | engagement décrit par le owner | `/api/v1/discovery/*`, puis endpoint owner | public ou personnel selon ressource |
| Maintenant | Journey `kind+id` | Journey detail | Journeys | attention dérivée ; mutation dans le owner | `/api/v1/me/journeys/<id>/` | Profile bénéficiaire |
| En cours | Journey `kind+id` | Journey detail | Journeys | `open_detail` | `/api/v1/me/journeys/<id>/` | Profile bénéficiaire |
| En cours | Dossier / Project `kind+id` | détail Objectives | Objectives | `open_detail` | `/api/v1/objectives/dossiers|projects/<id>/` | owner/autorisé |
| Maintenant | ActionProposal `kind+id` | détail/réponse Action Network | Action Network | `respond` | `/api/v1/social/action-proposals/<id>/[respond/]` | acteur actuellement autorisé |
| Maintenant | RecognitionRedemption `kind+id` | décision Recognition | Recognition | `accept`, `decline` | `/api/v1/recognition/redemptions/<id>/<decision>/` | bénéficiaire |
| Mes accès | Access `kind+id` | Access detail | Access | link `detail` | `/api/v1/me/accesses/<id>/` | bénéficiaire ou vue buyer autorisée |
| En cours | Access + Occurrence refs | Jour J | Access + Occurrence | `open_day_of` | `/api/v1/me/occurrences/<id>/day-of/` | relation participante réelle |
| Jour J | Occurrence `kind+id` | Live | Operations | `open_live` seulement en phase réelle | `/api/v1/operations/occurrences/<id>/live/` | participant autorisé |
| Historique | Journey / Access `kind+id` | détail canonique | owner correspondant | `view_detail` | détail Journey / Access | scope personnel |
| Moi → Ressources | PersonalAsset `kind+id` | Resource detail/reuse | Personal Assets | download/reuse owner-backed | `/api/v1/me/resources/*` | controller |
| Moi → Passport | Profile projection + Credential IDs | partage | Sharing / Trust | projection, pas nouvelle identité Profile | `/api/v1/me/passport/` | Profile |
| Moi → Groupes | Group `kind+id` | Group detail | Groups / Authorization | capacités d'autorité dérivées | `/api/v1/me/collectives/groups/<id>/` | membre/autorisé |
| Moi → Loyalty | programme/reward canonique | Loyalty owner API | Loyalty | `redeem` si owner l'autorise | `/api/v1/loyalty/*` | membre |
| Moi → Partner | Partner relation `kind+id` | détail économique | Partner | lecture économique scoped | `/api/v1/me/partners/<id>/` | relation personnelle |
| Mark | ressource canonique sélectionnée | owner surface | owner de la réalité | handoff, jamais propriété Mark | endpoint owner existant | scope recalculé serveur |

## Continuité d'identité et cycle de vie

Une Journey active peut être simultanément visible dans `En cours` et provoquer une attention dans `Maintenant`. Les deux portent le même `source={"kind":"journey","id":...}`. Une action owner-backed peut retirer l'attention de `Maintenant` sans terminer la Journey. Lorsqu'une Journey terminale sans représentation Access prend fin, elle quitte `En cours` et apparaît dans `Historique` avec le même ID et un lien vers le même détail.

Lorsqu'un Access devient la représentation principale d'une expérience, les selectors existants peuvent éviter de dupliquer la Journey dans les collections transverses. Ce choix de présentation ne crée pas une seconde vérité.

Les projections Journey et Access exposent une référence Occurrence séparée lorsque pertinente. `Jour J` conserve une identité de projection `occurrence_day_of`, mais expose explicitement l'Occurrence canonique. Les données planifiées et observées/live restent distinguées.

## Navigation provenance

L'origine de navigation n'est jamais persistée. Aucun `came_from_now`, `came_from_me` ou `came_from_mark` n'est introduit. Les deep links résolvent directement le scope serveur. Le bouton retour et le refresh n'ont aucun effet métier.

Makolo Mark suit le principe :

> Le Mark ouvre la porte ; le domaine accompagne la réalité.

Pour Jour J/Live, le handoff retourne à `Operations` avec l'Occurrence canonique ; aucune identité `MarkOccurrence` ou `LiveActivity` n'existe.

## Capabilities et TOCTOU

Une capability est informative. Toute mutation revalide l'autorité et l'état au moment du POST.

Z10 ajoute un handoff API pour les `ActionProposal` visibles dans Maintenant. La collection transverse ne décide pas la réponse : `respond_to_action_proposal()` reste la mutation canonique. Une réponse au nom d'un Space exige `acting_space_id` explicitement égal au Space attendu ; aucun changement silencieux d'acteur n'est accepté.

Recognition réutilise les endpoints owner-domain existants pour `accept` / `decline`. Waitlist, Transfer, Payment, Resource reuse et les autres mutations continuent d'utiliser leurs services propriétaires.

## Idempotence

La réutilisation d'une même `PersonalAssetVersion` dans la même Journey avec le même contexte retourne désormais le `JourneyArtifact` déjà créé. Elle s'appuie sur les contraintes JourneyArtifact existantes et `PersonalAssetUse`; aucune migration ni nouvelle clé de vérité n'est ajoutée. La réutilisation ne satisfait toujours aucun Requirement.

Les autres mutations conservent leurs contrats d'idempotence propriétaires. Z10 n'ajoute pas de moteur transversal d'idempotence.

## Privacy et autorité

- outsider : 404/minimal disclosure lorsque l'existence est privée ;
- Membership n'accorde aucune Permission ;
- Assignment n'accorde aucun Mandate ;
- un link vers un Space ne change jamais silencieusement l'acteur ;
- buyer et beneficiary restent distincts ;
- Access, AccessCredential et AccessUse restent distincts ;
- hidden/unknown ne sont pas reconstruits par une autre projection.

Z10 ne sérialise pas de credential secret, metadata de ledger, PII tierce ou dépendance cachée pour faciliter la navigation.

## Dates et sémantique d'inconnu

Les projections conservent le type temporel canonique : une Occurrence `date_only` reste date-only et aucun `00:00` n'est inventé. Les états `unknown`, `hidden`, `absent` et `unavailable` ne sont pas rabattus sur `false`.

## Tests de convergence

`core/test_z10_cross_surface_continuity.py` couvre directement :

- Now → Journey detail → mutation Form owner-backed → Now se retire, Ongoing continue ;
- Journey terminale → History avec le même ID ;
- Access/Ongoing → Access detail → Jour J avec le même Access et la même Occurrence ;
- Dossier/Project Ongoing → profondeurs Objectives existantes ;
- Now ActionProposal → API owner → disparition de l'attention ;
- réponse Space avec contexte explicite ;
- Now Recognition → décision owner-domain avec la même Redemption ;
- Resource reuse rejouée sans duplication ;
- Mark → Operations/Jour J sans identité parallèle ;
- chaîne IDOR Now/Ongoing/History/deep link.

Les tests Z2, Z3, Z5, Z6, Z8 et Z9 restent la preuve complémentaire pour date-only, unknown, Discovery owner handoff, readiness, Jour J/Live, Passport/Resources/Groups et Recognition/Loyalty/Partner.

## Migration

Z10 n'ajoute aucun modèle et aucune migration. Les changements sont limités aux projections, links/capabilities, API owner-backed, idempotence de service existante, tests et documentation.
