# Z8 - Passeport, Ressources personnelles et Groupes

## Objet

Z8 ferme les profondeurs secondaires du capital personnel sans déplacer les vérités des domaines propriétaires.
La racine `GET /api/v1/me/` reste un aperçu compact. Les profondeurs Z8 servent à présenter/inspecter le Passeport, retrouver/mobiliser une ressource personnelle et ouvrir un Groupe visible avec sa relation et ses capacités réelles.

Z8 reste strictement Profile-only, utilise `request.user` et n'ajoute aucun modèle, snapshot, cache persistant, score ou migration.

## Owner matrix

| Surface | Vérité propriétaire | Projection Z8 |
| --- | --- | --- |
| Passeport | Sharing / Presentation + Profile / Trust | composition contrôlée |
| PersonalAsset / versions | Personal Assets | collection, détail, provenance, validité, download/reuse |
| Proof | Trust | ressource distincte |
| Credential | Trust | ressource distincte |
| Group / Membership | Groups | relation personnelle |
| Permission / Mandate | Authorization | capabilities dérivées uniquement |

## API personnelle

```text
GET  /api/v1/me/passport/
GET  /api/v1/me/resources/
GET  /api/v1/me/resources/<asset-id>/
GET  /api/v1/me/resources/versions/<version-id>/download/
POST /api/v1/me/resources/versions/<version-id>/reuse/
GET  /api/v1/me/collectives/groups/<group-id>/
```

Les aperçus Resource et Group de `GET /api/v1/me/` et `/api/v1/me/collectives/` portent un lien vers leur profondeur Z8.

## Passeport Makolo

Z8 réutilise exclusivement `sharing.passport.build_profile_passport()` et ses variantes canoniques `public`, `complete`, `thematic`, `custom`.

Les natures de faits restent séparées :

```text
declared    -> Interests / OpenTo
established -> Proofs
issued      -> Credentials Trust
```

Le Passport ne devient jamais une seconde identité Profile et ne copie pas durablement les faits. Le custom revalide les identifiants demandés contre la sélection autorisée du sujet. La variante `public` applique la divulgation minimale de Sharing ; les variantes privées restent celles du sujet authentifié sur l'API personnelle.

Z8 n'invente pas de capability de partage : le runtime possède la présentation/export Passport Web, mais aucun nouveau mécanisme API owner-backed de share/revoke-share n'est créé ici.

## Ressources personnelles

La collection part de `personal_assets_for_controller(profile)`, est paginée par `limit/offset`, permet une recherche bornée sur le titre et annote uniquement la version courante. L'historique des versions appartient au détail.

Le détail expose identité, type, sensibilité, état actif/archivé, version courante, versions paginées, émission/expiration lorsque connues, provenance JourneyArtifact lorsque présente, capabilities et links.

Ne sont jamais sérialisés :

```text
file path
storage key
content_hash
private bucket URL
signed URL long-lived
raw backend filename
```

Le téléchargement passe par un endpoint authentifié qui réutilise `personal_asset_version_for_download()` et répond `private, no-store`. Un UUID d'un autre controller retourne 404.

La réutilisation délègue à `use_personal_asset_version_in_journey()`: elle crée un snapshot `JourneyArtifact` et conserve la provenance `PersonalAssetUse`. Elle ne transforme pas le PersonalAsset en Proof et n'affirme jamais qu'un Requirement est satisfait. Requirements/Readiness reste propriétaire de cette décision.

Les PersonalAssets archivés restent absents de la collection active. Leur propriétaire peut inspecter leur historique, mais download/reuse restent indisponibles conformément au service propriétaire.

## Frontières Trust et Access

```text
Proof != Credential Trust
Credential Trust != AccessCredential
PersonalAsset != Proof
PersonalAsset != JourneyArtifact
```

`personal.me.resources` compose PersonalAssets, Proofs et Credentials Trust dans des familles séparées. Passport place les Proofs sous `established` et les Credentials Trust sous `issued`. Aucun endpoint Z8 Passport/Resource ne lit ni ne sérialise `AccessCredential`.

## Groupes

Le détail Groupe part de `groups_for_profile(profile)`; un outsider reçoit 404. La relation distingue membership, ownership lorsqu'il existe, responsabilité laissée `null` lorsqu'aucun owner canonique ne la fournit, et autorité dérivée des services Groups/Authorization.

Les capabilities sont calculées côté serveur par `has_group_permission()`. Une membership active peut permettre `view` et `leave`, mais ne produit jamais `edit`, `manage_members`, `invite` ou `manage_ownership`.

Pour un Groupe d'Espace, seul l'héritage explicite déjà codé dans `has_group_permission()` peut produire une capacité Groupe. La membership Groupe ne crée jamais une Permission ou un Mandate Espace et Z8 n'introduit aucun mode `act_as_space`.

La profondeur ne sérialise ni Permission brute, ni Mandate brut, ni e-mail/téléphone de membres.

## Privacy / IDOR

Les endpoints Z8 exigent l'authentification, utilisent `request.user`, refusent `?profile_id=`, répondent 404 sur PersonalAsset/version/Group non visibles, ne rendent aucun secret de stockage, aucun AccessCredential et aucune donnée de contact membre.

## Performance

Resources collection = résumé + version courante seulement. Resource detail = versions paginées. Group detail réutilise le selector annoté `groups_for_profile()`. Aucun cache persistant n'est ajouté.

## Invariants

```text
Moi = aperçu ; Z8 = profondeur
Passport != Profile
Passport représente ; il ne possède pas
Proof != Credential Trust
Credential Trust != AccessCredential
PersonalAsset != JourneyArtifact
PersonalAsset != Proof
posséder != satisfaire Requirement
Membership != authority
Assignment != Mandate
Group != Space authority
unknown != invalid
```

## Interaction Z7

Z8 ne dépend pas de Makolo Mark. Mark peut router vers les mêmes ressources canoniques après intégration, sans créer de seconde identité Passport, Resource ou Group.

Le collision audit Z8 évite volontairement les fichiers Z7 à forte activité (`core/api/mark_*.py`, `core/mark_orchestration.py`, `core/mature_experience_views.py`, `config/urls.py`). Les coutures Z8 restent dans le namespace personnel déjà monté sous `/api/v1/me/`.