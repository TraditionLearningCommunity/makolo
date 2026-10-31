# Découvrir — chantier 00 : réconciliation de la PR #522
**Date du constat :** 2026-10-31  
**Portée :** uniquement l'inventaire, les frontières, la provenance des contrats et les dépendances ; aucune correction fonctionnelle.  
**Branche de travail :** `fix/discover-a-continuation-context-20261014` ([PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522)).  
**Référence inspectée :** `7fc241864176f5f246a4a8d01aa655a4e8b28562`.  
**Main inspecté :** `d0f0ec421c94c255fa4c0acd3509938a70c6322f`.  
**Registre vivant :** [discover-closure-register.md](discover-closure-register.md).

> Ce document est un relevé daté, non une promesse que le HEAD, les validations ou les PR empilées restent inchangés. Lors de l'ouverture du chantier suivant, relire uniquement les deltas postérieurs à ce relevé. Aucune CI ou suite de tests n'a été exécutée pendant ce chantier, à la demande de l'utilisateur.

## 1. Décision d'intégration et règle de vérité

- **Une seule branche d'intégration : #522.** Ne pas fusionner individuellement les PR historiques transférées ; ne pas fusionner automatiquement #522 dans `main`.
- **Un chantier à la fois.** Le chantier N+1 ne commence que lorsque le registre marque N comme `FERME`, avec les preuves explicites de sa sortie. Le fait qu'un module soit déjà partiellement développé n'ouvre pas son chantier.
- **Les contrats joints sont conceptuels**, non un schéma ORM, un JSON imposé ou une preuve de livraison ; ils orientent la conformité, tandis que le code actuel, les migrations, les contrôles d'accès et les tests font foi pour l'état réellement implémenté.
- **Pas de nouvelle vérité Discovery :** pas de modèle `Possibility`, calcul local de ranking, permission déduite, relation fondée sur la similarité des textes, Journey déclenchée par Save ou substitution d'un mock au propriétaire métier.
- **Web et Flutter consomment les mêmes vérités admises** ; leur Presentation peut différer.

## 2. Références contractuelles vérifiées

### Documents joints par l'utilisateur (hors dépôt ; ne pas les dupliquer)

1. `Makolo_Contrat_Maitre_Now_Ongoing_Decouvrir_Me_2026-10-05(3).md` — gel conceptuel personnel ; la partie III régit Découvrir, les autres parties régissent les frontières avec Now/En cours.
2. `Makolo_DecouvrirMe_Contrats_Donnees_Serveur_Client_Presentation_Consolidation_2026-10-10(1).md` — chaîne owner → selector/read model → Discovery → projection → Presentation N1/N2/N3 → action propriétaire ; définit l'admission, l'identité, l'exploration et la connaissance.
3. `Makolo_UX_Decouvrir_Contrat_Consolide.md` — champ personnel des possibilités, liste/carte, comparaison conditionnelle, Save/Watch/Engage, local-first, anti-features et fins du champ.

Ces fichiers sont des **entrées de travail externes à ce dépôt**. Leur disponibilité dans la conversation ne signifie pas qu'ils sont versionnés par Git. Les liens et les formulations ci-dessus n'assertent aucune implémentation.

### Documents présents sur #522

| Document | Valeur | Précaution |
| --- | --- | --- |
| `docs/architecture/makolo-domain-blueprint.md` | Autorités et domaines canoniques | Source de conception architecture, à interpréter avec le code actuel |
| `docs/architecture/z3-discovery-projection-audit.md` | Inventaire de composition et des quatre familles | Snapshot historique ; ses SHAs et statuts ne sont pas ceux de la branche courante |
| `docs/architecture/backend-ux-projection-api.md` | Contrats projection / UX | Vérifier son état contre les projections réelles |
| `docs/architecture/discovery-n1-layout-contract.md` | Huit zones N1 et deux ressources initialement visibles | « Implémenté » ne prouve pas que tous les scénarios Web/Flutter ont été testés |
| `docs/architecture/owner-facts-native-actions.md` | Prix, connaissance, relation et démarrage Services | Sa phrase « ne modifie pas Discovery ni Flutter » décrivait un chantier propriétaire antérieur, pas #522 consolidée |
| `docs/architecture/p2-presentation-media-use-contract.md` | Association des médias et publication | Distinguer relation propriétaire et présentation |
| `docs/architecture/p2-p5-presentation-media-n1-handoff.md` | Média N1 et livraison contrôlée | Les notes sur l'ancien stockage public et `private_file` sont successives ; vérifier le routage legacy réel |
| `docs/architecture/discovery-sharing-mobile-handoff.md` | Liens partagés et App Links | Domaines, signatures et `assetlinks.json` de production non déductibles du dépôt |
| `docs/architecture/mobile-geographic-search-foundation.md` | Fondations recherche géographique | La correspondance liste ↔ carte est à éprouver |
| `docs/operations/android-discovery-beta-local-repro-2026-10-19.md` | Procédure de reproduction Android | Diagnostic, non preuve de résolution sur appareil |
| `docs/operations/discover-n1-media-demo.md` | Seed/démo et audit de fichiers physiques | Ne pas confondre fichiers de démo manquants et bug de livraison |
| `specs/004-mobile-discovery-mature/tasks.md` | T001–T013 cochées | Trace de réalisation historique, non clôture produit générale |

**Décision documentaire :** ne pas réécrire ni uniformiser les contrats historiques. Le présent relevé fixe leur provenance ; [le registre vivant](discover-closure-register.md) porte désormais le statut courant d'acceptation.

## 3. État Git inspecté

- Comparaison `main...fix/discover-a-continuation-context-20261014` : branche en avance sur `main`, sans commit `main` manquant dans le résultat interrogé ; base commune `d0f0ec421c94c255fa4c0acd3509938a70c6322f`.
- **381 chemins modifiés** selon l'inventaire paginé de fichiers de la PR #522 ; **24 racines**. Le compare REST peut limiter son aperçu à 300 fichiers : ne jamais substituer ce plafond au listing paginé de la PR.
- Répartition exacte des 381 chemins à ce relevé :

| Racine | Chemins | Racine | Chemins | Racine | Chemins |
| --- | ---: | --- | ---: | --- | ---: |
| `.github` | 2 | `accounts` | 9 | `commerce` | 8 |
| `config` | 1 | `core` | 26 | `discovery` | 12 |
| `docs` | 17 | `domain_events` | 1 | `e2e` | 2 |
| `funding` | 5 | `mobile` | 150 | `obtention` | 2 |
| `opportunities` | 2 | `organizations` | 17 | `payments` | 3 |
| `preparation` | 4 | `presentations` | 27 | `requirements.txt` | 1 |
| `scripts` | 20 | `services` | 9 | `sharing` | 18 |
| `static` | 11 | `templates` | 29 | `topics` | 5 |

Les modifications dépassent donc Discovery et touchent les surfaces et propriétaires voisins. **Ce n'est pas une autorisation de refaire ces domaines pendant la fermeture de Découvrir.**

### Migrations présentes dans le diff (six)

1. `accounts/migrations/0009_profile_visibility_policies.py`
2. `presentations/migrations/0005_presentationmediause.py`
3. `presentations/migrations/0006_private_presentation_assets.py`
4. `services/migrations/0005_service_start_operation_fingerprint.py`
5. `sharing/migrations/0006_passport_issued_public_and_sharing.py`
6. `topics/migrations/0005_profile_publishable_defaults.py`

**Statut : recensées, non exécutées ni certifiées dans le chantier 00.** Les vérifier dans le chantier propriétaire correspondant et dans la fermeture globale.

## 4. Provenance des travaux voisins et risques de double fusion

| PR | Relation observée | Consigne de réconciliation |
| --- | --- | --- |
| [#523](https://github.com/TraditionLearningCommunity/makolo/pull/523) | Décrit explicitement son transfert vers #522 : Commerce / Opportunities / Services | Ne pas merger séparément ; vérifier dans le chantier 01 les contracts et fichiers courants |
| [#525](https://github.com/TraditionLearningCommunity/makolo/pull/525) | Décrit son transfert vers #522 : `PresentationMediaUse`, tests et documentation | Ne pas merger séparément ; distinguer association et livraison des médias |
| [#526](https://github.com/TraditionLearningCommunity/makolo/pull/526) | Marquée superseded par #522 ; trois fichiers reportés, commits documentés | Ne pas rejouer les mêmes changements dans Flutter |
| [#527](https://github.com/TraditionLearningCommunity/makolo/pull/527) | #522 annonce le transfert des quatre commits et la fermeture de #527 | Ne pas dupliquer `SyncEngine` / `SyncLifecycle` ; vérifier la régression dans le chantier 08 |
| [#524](https://github.com/TraditionLearningCommunity/makolo/pull/524) | PR empilée sur #522 pour erreurs bêta Android ; la description ne confirme pas son transfert définitif | **Dépendance non résolue par le seul texte** : comparer son diff/état avant tout rebase ou cherry-pick ; ne pas supposer intégré |
| [#528](https://github.com/TraditionLearningCommunity/makolo/pull/528) | Chantier Nous/Space reconnaissant des collisions avec les composants partagés de #522 | Ne pas merger à l'aveugle ; maintenir la frontière Nous et contrôler `accounts`, `organizations`, `mobile` commun |

**Réconciliation terminée pour le chantier 00** signifie que les dépendances sont **identifiées et attribuées** ; elle ne prétend pas que #524/#528 sont intégrées, ni que leurs modifications sont nécessaires à la livraison de Découvrir.

## 5. Carte des propriétaires et modules existants

| Responsabilité | Propriétaire / fichiers existants | Test ou vérification à réutiliser | Chantier destinataire |
| --- | --- | --- | --- |
| Prix, Offres, checkout | `commerce/offer_price_facts.py`, `commerce/native_activity_checkout_api.py` | `commerce/test_offer_price_facts.py`, `commerce/test_native_activity_checkout_api.py` | 01 |
| Activity / Occurrence / faits temporels | `discovery/search.py`, modèles `activities`, `discovery/api/composition.py` | `discovery/api/test_mature_discovery.py` | 01 puis 02 |
| Places / transports | modèles `geography`, `transport`, faits `discovery/api/composition.py` | `mobile/test/dg_discovery_geography_test.dart`, tests API | 01 puis 02/05 |
| Funding | `funding/api_serializers.py`, `funding/api_views.py` | `funding/test_discovery.py` | 01 |
| Opportunity / provenance | `opportunities/knowledge.py`, `discovery/unified.py` | `opportunities/test_public_source_knowledge.py` | 01 |
| Services / Journey | `services/native_start.py`, `services/selectors.py` | `services/test_native_start_api.py`, `services/test_owner_relations.py` | 01 puis 07 |
| Ressources métier | `preparation/services.py`, `preparation/views.py` | `preparation/tests.py` | 01 puis 03 |
| Admission, déduplication, wire | `discovery/api/composition.py`, `discovery/api/projections.py`, `discovery/api/views.py` | `discovery/api/test_mature_discovery.py`, `discovery/api/test_projections.py` | 02 |
| Médias de représentation | `presentations/media_models.py`, `presentations/media_services.py`, `presentations/media_delivery.py` | `presentations/test_media_use.py`, `discovery/api/test_media_bindings.py` | 03 |
| N1/Web | `templates/discovery/_universal_card.html`, `discovery/views.py` | `discovery/test_m8b_mature_discover.py` | 04 |
| N1/Flutter et N2 | `mobile/lib/presentation/possibilities/discovery_possibility_unit.dart`, `mobile/lib/features/discovery/discovery_mature_view.dart` | `mobile/test/discovery_mature_screen_test.dart`, `mobile/test/discovery_reader_test.dart` | 04 puis 06 |
| Recherche, map et navigation | `mobile/lib/features/discovery/discovery_routes.dart`, `discovery_screens.dart`, `discovery_repository.dart` | `mobile/test/dg_discovery_geography_test.dart`, `mobile/test/discovery_offline_position_test.dart` | 05 |
| Sharing / Save / Watch | `sharing/api_views.py`, `discovery/api/views.py`, `mobile/lib/features/discovery/discovery_share_sheet.dart` | `sharing/test_discovery_share_api.py`, `discovery/api/test_personal_primary_actions.py` | 07 |
| Local-first, sync, retenue | `mobile/lib/sync/sync_engine.dart`, `mobile/lib/data/local/profile_store.dart`, `mobile/lib/presentation/possibilities/discovery_offline_store.dart` | `mobile/test/sync_engine_test.dart`, `mobile/test/discovery_recognition_offline_test.dart` | 08 |

Les chemins désignent des points d'entrée inspectés ou inventoriés, **pas** une attestation que leurs tests passent.

## 6. Écarts démontrés, questions non prouvées et destinations

| ID | Nature | Constats à ce relevé | Chantier |
| --- | --- | --- | --- |
| D-01 | **Écart de code constaté** | La route `/discover/map` construit `DiscoveryMapScreen` sans la requête de recherche ; l'écran utilise `static const _query = DiscoveryQuery()`. | 05 |
| D-02 | **Écart de portée constaté** | `discovery.presentation-position` retient page et continuation, pas un état complet query/filtres/sélection/scroll. | 05 puis 08 |
| D-03 | **Risque concret à corriger** | `isPublishedRecognitionUri` vérifie le chemin mais pas l'origine de confiance ; le widget accepte une URL HTTP(S) et la charge. | 03 puis 08 |
| D-04 | **Risque de coût** | La projection API expose les ressources publiques sans limite de nombre, avec `text_content` des ressources TEXT inline ; étudier la borne de poids sans supprimer les ressources légitimes. | 02 puis 03 |
| D-05 | **Validation non établie** | Search et root ont des mécanismes distincts de pagination ; continuité et cursors expirés à éprouver sur les deux. | 05 |
| D-06 | **Dette legacy / déploiement** | Anciennes URL `PresentationAsset.file` et nouveaux `private_file` ; leur exposition effective dépend du routage et du stockage de déploiement. | 03 |
| D-07 | **Couverture à mesurer** | Actions N3, relations/variantes, galerie, ressources, profondeur et comparaison conditionnelle sur chaque famille ; ne pas présumer absent sans tests. | 01, 04, 06, 07 |
| D-08 | **Validation non attestée** | Cold start Android, changement de Profile, offline, révocation, Web/E2E et intégration finale n'ont pas de preuve vérifiée dans cet audit. | 08 puis 09 |
| D-09 | **Coordination externe** | #524 empilée et #528 partage des composants ; leur état final doit être reconsulté avant intégration susceptible de les croiser. | 01 / 09 selon collision |

**Terminologie :** `constaté` = localisé dans le code ; `risque` = chemin suspect sans incident reproduit ; `à mesurer` = couverture inconnue ; `non attesté` = aucune exécution vérifiée, et non « tests échoués ».

## 7. Frontières explicites — travail interdit dans le chantier 00

- Aucun nouveau modèle, migration, API, widget, algorithme, extension opportuniste, test artificiel ou changement de droits.
- Aucun lancement ou modification de CI, aucun merge, aucun déploiement, aucun dédoublonnage manuel de commits sans preuve.
- Ne pas corriger prématurément D-01 à D-09 : les problèmes sont désormais classés et affectés ; leur traitement attend le chantier destinataire.
- Ne pas transformer les limites conceptuelles volontairement ouvertes (ranking, Molongo, comparaison universelle, nouvelles relations n-aires, watch non owner-backed) en obligations de développement.
- Ne pas fusionner les vérités Now, En cours, Moi et Découvrir.

## 8. Critères de sortie du chantier 00

- [x] Branche, base et HEAD de référence identifiés.
- [x] Périmètre de PR et migrations inventoriés.
- [x] Contrats joints et documents du dépôt classés par provenance et autorité.
- [x] Transferts des PR voisines recensés, incertitudes explicites.
- [x] Propriétaires, modules, tests existants et responsabilités cartographiés.
- [x] Écarts, risques et validations non prouvées assignés à des chantiers futurs.
- [x] Règle de séquentialité et interdiction des nouvelles vérités fixées.
- [x] Registre vivant associé au présent relevé.

**Sortie du chantier 00 : DOCUMENTATION / RÉCONCILIATION FERMÉE** après présence de ce fichier et du registre vivant dans #522. Aucune sortie technique de chantier 01–09 n'est attestée ici. Une évolution ultérieure du HEAD appelle une revue de delta, pas une réouverture générale de 00.
