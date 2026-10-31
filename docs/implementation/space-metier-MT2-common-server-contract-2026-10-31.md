# MT2 — Contrat serveur commun des profondeurs Métier Space

**Date :** 31 octobre 2026. **Dépôt :** `TraditionLearningCommunity/makolo`. **Branche de PR :** `fix/discover-a-continuation-context-20261014` (#522).
**Statut :** checkpoint serveur implémenté ; **tests ajoutés, non exécutés dans cette session** faute de runtime Django/PostgreSQL local. Ne pas présenter comme clôture E2E ou comme fermeture N2/N3 de chaque archétype.
**Base de lecture :** main `d0f0ec421c94c255fa4c0acd3509938a70c6322f` ; avant travail PR HEAD `fc34cdacd84a5c37944dd91979ae0405ea0c7a0b`. PR évolue simultanément, revalidation obligatoire avant la suite.

## 1. Problème traité

MT1 (voir `space-metier-MT1-inventaire-profondeurs-2026-10-31.md`) avait prouvé plusieurs owners et vues Web/Flutter sans un **contrat explicite par BusinessEntry** des identités, sélections, handoffs multiples, responsabilité active et états de connaissance. La couverture de l'unique perspective `primary` restait `partial` même lorsqu'une lecture complète était connue ; un slice `kind/id` pouvait déclarer `composition_state=established` pour tout le Space. La continuation d'une section n'avait pas d'URL serveur.

La correction est **additive, sans nouveau modèle, état persistant, migration, permission ou endpoint**. Le domaine propriétaire garde la vérité et l'autorité. Ce n'est ni un N1/N2/N3 universel ni une nouvelle navigation applicative.

## 2. Contrat wire complémentaire, par entrée visible

Pour chaque row `sections[section_id].items[]` réellement divulguée par les selectors propriétaires :

- `entry_identity` : égale à la clé stable existante `key` (ex. `activity:<uuid>`, `journey:<uuid>`).
- `owner_reference` : copie explicite de `source {kind,id}`, sans transformer un Journey en ServiceCase modèle, ni un Activity en Programme/Création modèle.
- `knowledge_context` : `knowledge_state: known` pour **l'identité affichée uniquement**, `provenance: [{kind,id}]`, `coverage_state` de la section. **Aucun faux timestamp de fraîcheur** : âge du snapshot Flutter et connaissances serveur restent distincts.
- `links.selection` : URL GET existante `organizations_api:workspace-work`, avec `kind`, `id`, et `responsibility` du lecteur présent. La projection revalide le scope avant de rendre la sélection. Les URLs précédentes sans `responsibility` restent acceptées par défaut.
- `owner_handoffs[]` (0..n) : objets `{intent,label,owner:{kind,id},channel,url}`. Ces destinations ne sont **pas des permissions**. Le client doit respecter `channel`, la fraîcheur de ses droits, et la revalidation du propriétaire.
  - `inspect` → `space_work` GET owner-scoped, lorsque `view` est présent ;
  - `open_request` → `journey_request` GET/POST **seulement si JourneyRequest réel et lié** (le `request_id` n'est jamais remplacé par l'ID du Journey) ; l'action de décider est encore réservée au propriétaire et exige sa propre permission `ACTIVITY_REQUESTS_DECIDE` ;
  - `open_service_case` → URL `web` propriétaire Service **seulement si service_case_scope/context et capability l'autorisent**. Ce handoff Web n'implique pas une profondeur Flutter équivalente ;
  - `open_day_of` → URL `api` Operations **seulement si occurrence dans la phase admissible et capability réelle**.
- D'autres handoffs métier (Payment, Capacity, Access, etc.) seront ajoutés dans MT3–MT6 **uniquement après confirmation du propriétaire, des relations et des permissions**.

Cette structure permet déjà plusieurs N3 **sur la même entrée**, sans forcer aucune création, paiement, décision ou Live. Les consommateurs existants qui lisent `links` et `capabilities` restent compatibles.

## 3. Contrat de section et couverture

- `sections[section_id].links.continuation` apparaît seulement si `has_more=True`, avec une URL serveur existante GET `?section=...&offset=...&responsibility=...`. Les requêtes restent bornées et réautorisées. Les clients peuvent encore calculer leur propre page selon l'ancien contrat, mais devraient consommer la destination fournie à terme.
- Une lecture **complète et Space-authorized** peut annoncer `composition_state=established`, `coverage_state=established` et `business_world.perspectives[primary].coverage_state=established` pour les sources qu'elle sait effectivement composer.
- Un accès **Activity-limited**, une sélection `kind/id` ou une page `section/offset` est `partial` ; il ne prouve **jamais** que le monde entier est vide ou en ordre. Chaque section présente dans la réponse porte le même degré de couverture de cette observation.
- Un élément **caché par permission reste omis**. On ne crée pas un item `unavailable` pour en révéler l'existence.
- Aucun `unavailable` global n'est inventé : cela exigerait une détection de défaillance source réelle. Toute défaillance doit rester un échec explicite de l'owner, pas une liste vide silencieuse.
- Pas de multiperspective artificielle : `primary` reste seule tant qu'une seconde perspective exploitable, autorisée et navigable n'a pas de cas démontré. Les huit grammaires et leurs `reading_groups` sont préservés.

## 4. Sécurité et invariants

Un Mandate Activity sélectionné ne doit pas élargir le périmètre ; le code `_activity_scope_from_responsibility` impose la restriction avant les projections. Une ancienne URL de handoff ne constitue ni une capability ni une preuve de droit. Le serveur vérifie l'acteur Space, `ACTIVITY_*`, `ORDERS_VIEW`, les selectors Service, le timing Jour J et l'owner de décision. Le changement de rôle, l'expiration, la révocation et TOCTOU sont résolus au niveau propriétaire.

Les identités de bénéficiaire, les pièces, preuves, QR, AccessCredential, secrets, données de paiement privées, Notes Service, fichiers non publiés et identités de groupes non pertinentes ne sont pas ajoutés. `Presentation` ne possède aucune vérité. `Capacity` reste séparé de `Placement` et de `Payment`.

## 5. Fichiers de ce checkpoint

1. `organizations/api/space_work_projection.py` : enrichissement post-filtrage, liens contextualisés, provenance, handoffs vérifiés, pagination et coverage prudente.
2. `organizations/space_work_composition.py` : couverture de la perspective dérivée du scope et des sections, sans changer les huit grammaires.
3. `organizations/test_space_work_mt2.py` : tests ciblés des huit archétypes, reconnaissance owner et sélection, Mandate sélectionné/révoqué, demande réelle, dossier Service, Jour J, continuation et privacy.
4. Le présent document.

**Migrations : aucune.** **API : champs additionnels seulement.** **Client Web/Flutter : aucun changement à cette étape.**

## 6. Vérification requise avant d'affirmer que MT2 est exécuté

Exécuter quand un runtime Django et une base de test sont disponibles :

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_space_work_mt2 organizations.test_zs3_space_work_api organizations.test_space_work_group2 organizations.test_space_work_group3 organizations.test_space_work_group4 organizations.test_ws3_space_work_web
```

Puis vérification sous PostgreSQL dans les gates pertinentes, si la suite touche aux transactions, et revue des warnings/CI. Aucun test n'a été supprimé ni assoupli. Vérifier avec un vrai profil Space, un utilisateur Activity-limited, une demande ayant un JourneyRequest réel, une demande sans JourneyRequest, un cas Services sans puis avec contexte, un Jour J hors fenêtre, un après révocation, et les huit archétypes. Le résultat de test n'est **pas connu dans cette session**.

## 7. Handoff MT3–MT8 sans confusion de responsabilité

- **MT3 :** N2/N3 Generic + Community ; brancher leurs vrais owners et relations.
- **MT4 :** Education + Service Provider ; programmes/sessions/inscriptions et prestations/dossiers ; réutiliser `open_request` et `open_service_case` existants.
- **MT5 :** Commerce + Transport ; Offer/Order/Departure/Route/Vehicle, capacité, opérations selon owners disponibles.
- **MT6 :** Creative + Media ; œuvres/productions, occurrences et médias publiés autorisés.
- **MT7 :** composer `owner_handoffs` dans Web/Flutter, préserver le contexte de retour, accessibilité, local-first et état de fraîcheur, sans utiliser les URL web dans un écran natif comme permission.
- **MT8 :** tests multi-acteur/permissions/révocation, QA visuelle 8 grammaires, performance et E2E.

**Statut MT2 : contrat serveur implémenté, à valider en exécution ; ne pas annoncer les huit parcours N2/N3 comme terminés.**
