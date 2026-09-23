# Z11 — Sécurité, confidentialité et autorité de l'expérience personnelle

> Statut : hardening transversal en cours sur le runtime courant.
>
> Z11 ne crée ni domaine, ni surface UX, ni vérité persistante. Il durcit les selectors, services, projections, vues, headers et tests existants.

## 1. Contrat central

Une composition UX peut rapprocher des vérités, jamais élargir les droits.

Pour toutes les surfaces personnelles :

```text
viewer = request.user
subject = request.user
client-selected actor = interdit
authority = owner-domain selector/service
projection = divulgation minimale
mutation = autorité revérifiée au moment du POST
```

Le contexte personnel n'accepte pas de changement silencieux d'acteur via `profile_id`, `user_id`, `beneficiary_id`, `subject_id`, `act_as_space`, `space_id`, `space_context` ou `organization_actor`.

Les réponses JSON personnelles composées utilisent `Cache-Control: private, no-store`. Les profondeurs contenant un secret, un document ou une représentation de credential restent également `no-store`.

## 2. Autorité : invariants non transférables

Z11 maintient explicitement :

```text
Profile = personne globale
Membership != authority
Assignment != Mandate
Permission/Mandate = autorité
Access != AccessCredential != AccessUse
Credential Trust != AccessCredential
Capacity != Placement
Waitlist != Live Queue
JourneyStep != Checkpoint
PersonalAsset != Proof
posséder une ressource != satisfaire un Requirement
buyer != beneficiary
Partner relation != Space authority
Loyalty membership != Space authority
```

Une association technique ou métier ne crée jamais automatiquement une Permission, un Mandate, un Access, un Payment, un droit de mutation ou un accès à des données privées.

## 3. Matrice viewer / subject / owner

| Ressource | Owner de la vérité | Subject personnel | Visibilité personnelle | Mutation |
|---|---|---|---|---|
| Profile / Moi | Accounts + Profile | request.user | identité minimale du Profile courant | réglages compte séparés |
| Journey | Journey + owner domains | beneficiary=request.user | selector participant uniquement | service propriétaire revérifie |
| Activity / Occurrence | Activity | viewer selon visibilité/engagement/autorité | private et draft restent scope-safe | permissions Activity |
| Dossier / Project | Objectives | owner_profile=request.user ou autorité explicite | dépendances cachées opaques, `partial` possible | owner service |
| Requirement / Readiness | owner du Requirement | Journey visible | conséquence dérivée, evidence privée non sérialisée | owner Requirement |
| Access | Access | beneficiary=request.user ; buyer relation séparée | buyer peut retrouver son achat sans devenir bénéficiaire | service Access |
| AccessCredential | Access | beneficiary=request.user uniquement | secret jamais transmis au buyer distinct | owner Access, état revérifié |
| AccessUse | Access / Operations | beneficiary ou autorité Operations légitime | absent des projections générales et buyer-only | Operations |
| PersonalAsset | Personal Assets | controller/request.user | UUID tiers en 404 ; storage internals absents | service PersonalAsset |
| Proof | Trust / owner domain | subject autorisé | evidence et review metadata privées | service propriétaire |
| Credential Trust | Trust | subject/projection publique contrôlée | jamais sérialisé comme AccessCredential | Trust |
| Passport | Sharing/Profile projection | request.user ou viewer du share | projection choisie puis re-filtrée par owners | Sharing |
| Group | Groups + Authorization | member/request.user | group privé outsider en 404 ; PII membre minimale | Group Permission/Mandate |
| Recognition | Recognition | account/request.user | compte et redemption personnels | services transactionnels + idempotence owner |
| Loyalty | Loyalty | user=request.user | compte/programme local uniquement | service revalide l'éligibilité |
| Partner | Partner | Partner.user=request.user | projection personnelle sans buyer PII/notes | aucune Space authority induite |
| Operations Live | Operations | participant bénéficiaire | perspective participant explicite | opérateur séparé par Permission/Mandate |

## 4. Buyer != beneficiary : correctif Z11

La relation `purchased_for_other` reste une vue transactionnelle de l'acheteur. Elle ne donne plus aucune capacité de présentation du credential du titulaire.

```text
buyer distinct
→ peut retrouver l'Access acheté selon le contrat transactionnel
→ ne reçoit ni AccessCredential, ni QR/token, ni capability present_credential
→ ne reçoit pas l'historique AccessUse du bénéficiaire
→ ne reçoit pas la Journey privée du bénéficiaire
```

La profondeur :

```text
GET /api/v1/me/accesses/<uuid>/credential/
```

est strictement bénéficiaire. Elle retourne 404 à l'acheteur distinct, aux tiers, aux Access révoqués/terminaux et aux droits dont la fenêtre de validité est expirée.

## 5. Personnel : scope serveur

`PersonalProjectionAPIView` constitue le garde partagé des projections Mature privées. Le sujet vient du serveur via `request.user`.

Now, Ongoing, détails Journey/Requirement/Access, Moi, Passport, Resources, Group detail, Partner detail et Mark utilisent ou réutilisent ce contrat. Une route directe refait ses checks ; aucune provenance de navigation n'est une permission.

Mark possède une seconde protection : les clés d'autorité placées dans `context` (`profile_id`, `user_id`, `beneficiary_id`, `subject_id`, Space/role/mandate/permission et variantes) provoquent un résultat `personal_scope_only`. Un contexte aide à résoudre une cible ; il ne donne aucun droit.

## 6. Staff et autorité métier

`is_staff` est une capacité Django/admin, pas une Permission métier universelle.

Z11 retire les bypass `is_staff` identifiés dans les chemins métier audités :

- lecture des PaymentObligations ;
- ouverture d'une CommerceOrder étrangère pour démarrer un paiement ;
- review de PaymentEvidence ;
- révocation d'un ShareEnvelope tiers.

La supervision métier utilise les Permissions/Mandates canoniques ou l'autorité plateforme explicite. Le bypass Django `is_superuser` déjà assumé par Authorization reste un contrat technique explicite ; Z11 ne le recopie pas manuellement.

## 7. Existence, IDOR et divulgation minimale

Les deep links personnels doivent chercher dans un queryset déjà scopé ou résoudre via le service owner. Une ressource privée hors scope est rendue indisponible sans exposer son titre, owner ou autre metadata.

Les projections ne doivent pas transporter :

```text
credential secret / QR / barcode brut
private storage path / key
Proof review notes
private member PII
Partner buyer PII
fulfillment internals
raw Permission/Mandate dumps
private operational observations non nécessaires
```

Les counts, recherches et paginations sont calculés après le scope personnel.

## 8. Jour J / Live

La surface personnelle appelle `resolve_participant_occurrence_live()`, qui exige une relation bénéficiaire et force la perspective `participant`. Une Permission opérateur possédée par ailleurs ne transforme pas la projection personnelle en vue opérateur.

```text
participant → participant projection
operator authorized → Operations owner surface
membership only → aucune autorité opérateur
```

Capacity, Placement, Waitlist, Live Queue, JourneyStep et Checkpoint restent séparés.

## 9. Ressources et Requirement

Le téléchargement et la réutilisation de PersonalAsset passent par les services Personal Assets. Le POST de réutilisation refuse les overrides d'acteur et revérifie l'accès à la Journey cible.

Réutiliser une version crée un `JourneyArtifact`; cela ne déclare jamais un Requirement satisfait. Requirement/Readiness reste propriétaire de cette décision.

## 10. Payments

Les montants/devise/statuts viennent des owners serveur. Les endpoints Payment existants ignorent les champs financiers forgés du client et les services revérifient l'acteur, l'état et l'idempotence. Les mutations Recognition conservent leur idempotence propriétaire ; Z11 rend également la mutation Loyalty reward replay-safe via une clé d'idempotence API, sans nouveau champ ni migration.

Z11 confirme en plus :

```text
is_staff seul != finance authority
buyer != beneficiary
CommerceOrder étrangère != payable par simple staff flag
PaymentEvidence review != staff flag
```

## 11. Sharing

Un ShareEnvelope révoqué/expiré est revalidé à l'ouverture. La révocation appartient au créateur ou à une autorité plateforme explicite ; `is_staff` seul ne suffit plus.

Un share n'importe jamais implicitement Permission, Mandate, Access ou droit de mutation hors du contrat propriétaire.

## 12. Tests de régression ajoutés

Le hardening ajoute ou étend notamment :

- buyer distinct → credential API 404 ;
- collection `purchased_for_other` sans secret, lien ni capability credential ;
- buyer Web → aucun QR ni AccessUse et réponse `no-store` ;
- fenêtre Access expirée → credential non présentable même si le status legacy reste `valid` ;
- Now/Ongoing → `no-store` et rejet des actors fournis par le client ;
- Mark → matrice de context spoofing élargie et rejet d'override top-level ;
- simple `is_staff` → aucune ouverture de CommerceOrder d'un tiers ;
- simple `is_staff` → aucune lecture PaymentObligation étrangère ;
- simple `is_staff` → aucune révocation Sharing tierce ;
- Recognition et Loyalty personnels → `private, no-store` ;
- Loyalty reward deep link → reward appartenant à un programme où le Profile possède réellement un compte ;
- Loyalty reward redeem → clé d'idempotence obligatoire côté API et replay sans second débit.

Les suites Z5–Z9 existantes restent les garde-fous pour hidden Dossier dependencies, Assignment != authority, private/unlisted Activities, participant-safe Live, Resources/Passport/Groups, Recognition/Loyalty/Partner et autres frontières déjà livrées.

## 13. Logs, cache, analytics et events

Z11 n'introduit aucun cache. Les projections privées ne partagent donc aucune clé cross-Profile.

Aucun nouveau log de payload personnel, credential, QR, URL privée, document ou donnée de paiement n'est ajouté. Les Domain Events et Analytics continuent d'utiliser leurs contrats minimaux existants ; Z11 ne sérialise aucun secret AccessCredential dans ces flux.

## 14. Migration

Aucune nouvelle vérité persistante n'est nécessaire.

```text
Z11 migration = aucune
```

Aucun `SecurityState`, `AccessMatrix`, `ProjectionPermission` ou `UserVisibility` n'est introduit.

## 15. Gate de fermeture

Z11 est mergeable seulement après :

1. tests ciblés IDOR/authority/credential/payment/sharing verts ;
2. suites Z2–Z9 pertinentes vertes ;
3. `makemigrations --check --dry-run` vert ;
4. CI globale verte ;
5. réconciliation sur le `main` courant ;
6. réaudit des collisions ;
7. réaudit de Z10.

Au démarrage de Z11, Z10 n'était pas encore livré. Avant fermeture, la branche a été réconciliée avec le `main` courant après le merge de Z10 et les coutures nouvelles ont été réauditées : le lien détail Access Z10 est conservé, le handoff Mark Jour J reste propriétaire d'Operations, et le hardening Z11 n'élargit aucun droit. Aucun conflit de vérité métier n'a été introduit.
