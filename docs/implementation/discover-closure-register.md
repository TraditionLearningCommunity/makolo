# Makolo — registre de fermeture de Découvrir
**Document vivant — responsable : branche [#522](https://github.com/TraditionLearningCommunity/makolo/pull/522)**  
**Initialisé le :** 2026-10-31  
**Chantier courant :** **06 — N2, variantes et comparaison conditionnelle, CODE LIVRÉ**. Compte rendu : [chantier 06](discover-stage-06-n2-variants-comparison-2026-10-31.md). **Prochain : 07**, non commencé ici.  
**Chantier 00 :** **FERMÉ — réconciliation documentaire**.  
**Relevé de référence :** [chantier 00 — réconciliation](discover-stage-00-reconciliation-2026-10-31.md).

> **RÈGLE DE PASSAGE : un chantier à la fois.** Les chantiers sont **séquentiels**, non parallèles. Ne jamais ouvrir l'implémentation N+1 tant que la livraison de code de N n'est pas achevée et documentée. À la demande explicite de l'utilisateur, la validation exécutée (tests/CI/appareil) est regroupée à l'étape 09 ; cela ne signifie ni tests verts ni certification anticipée. Les statuts `présent/partiel` décrivent l'implémentation rencontrée dans le code, **pas** l'état d'exécution du chantier. Les étapes 01–09 restent `VERROUILLÉ` ou `À OUVRIR` tant qu'on n'a pas travaillé et validé leur sortie. L'exécution CI est une exigence de la fermeture globale 09, explicitement **hors des chantiers 00–08** pour cette séquence de livraisons ; aucun résultat n'est revendiqué avant exécution.

## 0. Doctrine de fermeture et niveaux de preuve

**Faire seulement ce qui manque.** Le code existant est la base de réalisation, pas un chantier à recommencer. L'objectif est de fermer progressivement la chaîne :

`owner métier → selector/read model → admission/composition Discovery → projection → Web/Flutter N1/N2 → handoff N3 owner → reprojection / local-first`.

### Vocabulaire obligatoire

- `EXISTANT_SOURCE` : chemin/mécanisme identifié dans le HEAD, sans certification automatique.
- `CONFORME_PROUVÉ` : code + scénario/test réellement vérifié, avec preuve enregistrée.
- `ÉCART_CODE` : divergence localisée dans un fichier et explicable.
- `PARTIEL` : mécanisme existant, obligation ou scénario non couvert complètement.
- `À_VÉRIFIER` : absence non démontrée ; ne pas lancer une implémentation spéculative.
- `OWNER_EXTERNE` : vérité ou mutation sous l'autorité d'un domaine hors Discovery ; corriger là si nécessaire.
- `OUVERT_CONCEPTUEL` : capacité optionnelle ou non définie par un owner, non bloquante.
- `FERMÉ` : critères de sortie du chantier satisfaits et consignés.

**Critère de livraison de code pour 01–08 :** besoin et contrat, source de vérité, fichiers modifiés, tests de régression ajoutés/ajustés, risques et handoff consignés. Les tests non exécutés restent **non vérifiés** jusqu'à 09 ; aucune étape n'est dite certifiée avant les preuves d'exécution.

### Anti-features protégées

Pas de modèle persistant générique `Possibility`, de scoring client, de deuxième source cartographique indépendante, de faux owner, de capacité créée d'après un texte, de déduction d'autorité par Membership/Space, de conversion de `unknown` en gratuit/indisponible, de Save → Journey, de Watch → engagement, de feed infini artificiel, de migration pour confort visuel, ni de refonte de Now/En cours/Moi.

## 1. Tableau de passage strict

| Étape | Nom | État d'exécution | Sortie vérifiable |
| --- | --- | --- | --- |
| **00** | Réconciliation et gel des contrats | **FERMÉ** | [Inventaire daté](discover-stage-00-reconciliation-2026-10-31.md), sources et frontières, registre unique |
| **01** | Vérités et capacités propriétaires | **LIVRÉ EN CODE — validation différée à 09** | [Relevé owner 01](discover-stage-01-owner-facts-2026-10-31.md), correctifs Funding/Services, six tests ajoutés |
| **02** | Projection canonique Discovery | **LIVRÉ EN CODE — validation différée à 09** | [Relevé projection 02](discover-stage-02-canonical-projection-2026-10-31.md), admission Services, ressources, prix, pagination et tests |
| **03** | Médias, ressources et stockage | **CODE LIVRÉ — migration physique et validation différées** | [Relevé média 03](discover-stage-03-media-resources-2026-10-31.md) : gate owner commun, fichiers, Flutter, imports éditoriaux MPS privés, commande de migration conservatrice ; déploiement non réalisé |
| **04** | Presentation N1 | **LIVRÉ EN CODE — validation différée à 09** | [Relevé N1 04](discover-stage-04-presentation-n1-2026-10-31.md) : huit zones, ajout relatif, sens des faits et des contextes, média MIME/alt ; tests enregistrés |
| **05** | Recherche, carte et navigation | **LIVRÉ EN CODE — validation différée à 09** | [Relevé exploration 05](discover-stage-05-search-map-navigation-2026-10-31.md) : routes filtrées, carte compacte et repères, pagination signée, scroll/focus et public invité |
| **06** | N2, variantes et comparaison conditionnelle | **LIVRÉ EN CODE — validation différée à 09** | [Relevé 06](discover-stage-06-n2-variants-comparison-2026-10-31.md) : profondeur Web/Flutter, trois assessment states, variantes occurrence, comparaison strictement conditionnelle, aucun classement fictif, tests écrits |
| **07** | Save, Watch, Sharing, engagements N3 | **PROCHAIN CHANTIER** | Transitions autorisées, idempotence si nécessaire, retour owner confirmé |
| **08** | Local-first et confidentialité | **VERROUILLÉ** | Snapshots, reprise, offline, profils, cache/révocation et cold-start contrôlés |
| **09** | Certification et intégration | **VERROUILLÉ** | Tests et validation réels attestés, CI requise, rapport de fermeture final, décision explicite de merge |

**Règle de retour :** si un chantier clos révèle une régression lors du suivant, créer une anomalie avec preuve et la corriger dans l'étape active comme dépendance bloquante ; ne pas relancer tout le périmètre ancien. Mise à jour du présent registre obligatoire.

## 2. Frontière des propriétaires (préparation de l'étape 01)

| Owner | Sources repérées | Obligation à prouver au chantier 01 | Interdit dans Discovery |
| --- | --- | --- | --- |
| **Activity / Occurrence** | Modèles `activities`, selectors `discovery/search.py`, `discovery/api/composition.py` | Publication, Occurrences réellement admises, horaires et variantes identifiées | Deviner des sessions à partir du texte |
| **Commerce** | `commerce/offer_price_facts.py`, `commerce/native_activity_checkout_api.py` | `unknown/free/exact/range`, prix unitaires, fenêtres, variantes par Occurrence | Calculer Quote, paiement, remise ou devise |
| **Geography / Transport** | `geography`, `transport`, `discovery/api/composition.py` | Lieux publics, rôle départ/arrivée/escale, localisation explicite | Inventer coordonnées, trajet ou lieux |
| **Opportunities** | `opportunities/knowledge.py`, `discovery/unified.py` | Révision/source admissible, provenance et réserve sur fraîcheur | Inventer une certitude ou relation |
| **Funding** | `funding/api_views.py`, `funding/api_serializers.py` | Fenêtres, conditions déclarées et inconnues | Déclarer un utilisateur éligible sans owner |
| **Services / Journey** | `services/native_start.py`, `services/selectors.py` | Démarrage autorisé, idempotence, lien privé à Opportunity | Créer une Journey depuis Save ou Watch |
| **Preparation / Resource** | `preparation/services.py`, `preparation/views.py` | Version, visibilité, contenu et accès effectifs | Promouvoir arbitrairement un document en média N1 |
| **Presentation / Storage** | `presentations/media_models.py`, `media_delivery.py`, `media_services.py` | Publication, propriété, retrait et livraison de fichiers | Déduire qu'une URL quelconque est publique |

La présence de ces fichiers est attestée par l'inventaire de #522. Leur conformité n'est **pas encore validée** dans l'étape 01.

## 3. Registre d'exigences — couverture actuelle et destination

Les statuts ci-dessous sont des **observations d'audit**, pas des tâches commencées. Dans l'étape propriétaire, remplacer chaque `PARTIEL` ou `À_VÉRIFIER` par une preuve, une correction ciblée ou une limite owner légitime.

| ID | Exigence contractuelle | Observation au 31/10 | Source / preuve d'entrée | Responsable de fermeture |
| --- | --- | --- | --- | --- |
| R01 | Possibilité distincte du modèle brut, identité owner stable | `EXISTANT_SOURCE` conservé ; aucun nouveau modèle ni ID métier artificiel, implémentation 02 livrée | `discovery/api/composition.py`, `discovery/api/projections.py` | 02 |
| R02 | Admission, visibilité, Groupe et non-divulgation | `ÉCART_CODE` corrigé pour Services via selector owner ; ressources contrôlées par Preparation et tests ajoutés, non exécutés | `discovery/unified.py`, `discovery/api/composition.py`, `discovery/api/test_mature_discovery.py` | 02 |
| R03 | Champ multi-famille sans classement local | `EXISTANT_SOURCE` préservé ; aucune nouvelle pertinence locale, aucun score | `discovery/unified.py`, `discovery/api/composition.py` | 02 |
| R04 | Faits et prix établis par Commerce | `OWNER_EXTERNE`, mécanisme identifié | `commerce/offer_price_facts.py` | 01 |
| R05 | Horaires/Occurrences/variantes sans inférence | `PARTIEL` | `discovery/api/composition.py`, modèles Activity | 01 puis 02 |
| R06 | Lieux multiples, public/privé et rôles transports | `PARTIEL` | `discovery/api/composition.py`, tests API | 01 puis 02/05 |
| R07 | Conditions et fraîcheur des Opportunities | `OWNER_EXTERNE`, mécanisme identifié | `opportunities/knowledge.py` | 01 |
| R08 | Conditions de Funding sans éligibilité fictive | `ÉCART_CODE` corrigé côté owner : Space suspendu/archivé/retiré refuse désormais publication/contribution ; tests ajoutés, non exécutés | `funding/selectors.py`, `funding/services.py`, `funding/test_z15_api.py` | 01 |
| R09 | Handoff Service owner et Journey idempotente | Selector Web/natif owner harmonisé, tests de retrait ajoutés non exécutés ; Discovery doit réutiliser ce gate en étape 02 | `services/views.py`, `services/api_views.py`, `services/native_start.py`, `services/test_native_start_api.py` | 01 puis 07 |
| R10 | Ressources publiques, sans données restreintes | `ÉCART_CODE` corrigé : droits Preparation, scope Occurrence, textes inline bornés sans supprimer les références ; tests non exécutés | `discovery/api/composition.py`, `discovery/api/test_resource_previews.py` | 02 ; livraison/stockage 03 |
| R11 | Cohérence collection/détail/médias | Collection/détail conservent la même composition et admission owner ; droits et fichiers des médias encore réservés à 03 | `discovery/api/composition.py`, `discovery/api/media_bindings.py`, `discovery/api/test_mature_discovery.py` | 02 ; médias 03 |
| R12 | Media-use owner, statut publié, retrait | `ÉCART_CODE` corrigé : media selector/livraison même admission owner, Group et Occurrence ; audit/migration legacy ajoutés, exécution non réalisée | `presentations/media_selectors.py`, `media_delivery.py`, `management/commands/harden_presentation_media_assets.py` | 03 ; migration déploiement |
| R13 | Rétention automatique de médias réellement first-party | `ÉCART_CODE` corrigé : origine de confiance obligatoire, remplacement non destructeur, retrait sérialisé ; tests écrits non exécutés | `mobile/lib/presentation/possibilities/discovery_offline_store.dart`, `mobile/lib/presentation/media/retained_public_discovery_image.dart` | 03 ; états offline 08 |
| R14 | N1 contextualisé et adaptatif | `ÉCART_CODE` corrigé : rôles géographiques, notes limitantes et variantes owner, section pratique adaptative, MIME/alt galerie ; tests N1 écrits, non exécutés | `discovery_possibility_unit.dart`, `discovery/views.py`, `templates/discovery/_universal_card.html` | 04 |
| R15 | N1 dates à droite, faits stables, ressources dépliables | Date ajout humanisée à droite et accessible exactement, description dépliable, deux ressources puis toutes et trois interactions réutilisées ; tests écrits non exécutés | `discovery_possibility_unit.dart`, `templates/discovery/_universal_card.html`, tests Flutter/Web | 04 |
| R16 | Recherche/filtres/continuation sur mêmes critères | `ÉCART_CODE` corrigé : routes conservent mêmes filtres, pages signées et historique local des curseurs réels, sans inventer de token ; tests ajoutés non exécutés | `discovery_repository.dart`, `discovery_screens.dart`, `discovery_routes.dart` | 05 |
| R17 | Carte liée au même champ et aux mêmes critères | `ÉCART_CODE` corrigé : query passée par URL, même watchItems, MapLibre avec repères owner, véritable carte compacte et sélection ; tests non exécutés | `discovery_routes.dart`, `discovery_screens.dart`, `discovery_mature_view.dart` | 05 |
| R18 | Retour, sélection, scroll et contexte après redémarrage | `ÉCART_CODE` corrigé au niveau navigation : scroll et candidat sélectionné stockés avec la page/continuation root, critères transportés par route ; profil et révocation complets relèvent de 08 | `discovery_screens.dart`, `discovery_offline_position_test.dart` | 05 puis 08 |
| R19 | États NO_MATCH/END_OF_FIELD/OFFLINE distincts | Présentation Map raccordée au state de source, échecs/continuation traités sans créer de résultats ; tests réels et local-first de 08/09 restent non attestés | `discovery_screens.dart`, `discovery_selector.dart`, `discovery_wire.dart` | 05 puis 08 |
| R20 | N2 sens, profondeur, variantes et inconnues | `ÉCART_CODE` corrigé : N2 Web et Flutter owner-backed, favorable/limiting/unknown, ressources complètes, variantes et relations admises ; scénarios écrits non exécutés | `discovery_n2_model.dart`, `discovery_n2_depth.dart`, `discovery/n2_presentation.py`, `templates/discovery/possibility_detail.html` | 06 |
| R21 | Comparaison conditionnelle sur faits comparables | `ÉCART_CODE` corrigé : table facultative seulement pour ≥2 Occurrences d'une même Activity dont une dimension Début/Fin/Lieu est connue pour chacune ; pas d'alternative inter-verticale fictive | `discovery_n2_model.dart`, `discovery/n2_presentation.py`, tests dédiés | 06 |
| R22 | Save distinct de Watch distinct de Engage | `EXISTANT_SOURCE`, scénarios nécessaires | `discovery/api/views.py`, `discovery_watch_screens.dart` | 07 |
| R23 | Sharing interne/externe, reprise et refus | `PARTIEL` | `sharing/api_views.py`, `discovery-sharing-mobile-handoff.md` | 07 |
| R24 | N3 owner-backed sans action fictive | `PARTIEL`, couverture verticale non attestée | `discovery/api/test_personal_primary_actions.py` | 07 |
| R25 | Snapshot distingué de fraîcheur réseau | `EXISTANT_SOURCE`, tests réels manquants | `sync_engine.dart`, `discovery_repository.dart` | 08 |
| R26 | Pages bornées, reprise, profils, révocation | `PARTIEL` | `profile_store.dart`, `discovery_offline_store.dart` | 08 |
| R27 | Cold start Android, liens et UI vraie | `À_VÉRIFIER` ; absence d'attestation | Runbook Android et tests Flutter | 09 |
| R28 | Migrations, compatibilité, CI, déploiement | `À_VÉRIFIER` — non exécuté à l'étape 00 | Six migrations listées dans le relevé | 09 |

### Hors fermeture obligatoirement implémentée

| Référence | Statut | Raison |
| --- | --- | --- |
| Scoring/ranking universel Molongo/Mayele | `OUVERT_CONCEPTUEL` | Aucun algorithme nouveau requis par le contrat ; le seam existant peut rester neutre |
| Comparaison universelle de toutes les possibilités | `OUVERT_CONCEPTUEL` | Propriétaire et dimensions comparables nécessaires |
| Relations n-aires inférées | `OUVERT_CONCEPTUEL` | Un texte similaire ne prouve pas un lien canonique |
| Veille sans owner contractuel | `OUVERT_CONCEPTUEL` | Ne pas inventer la persistance ou la notification |
| Média obligatoire sur chaque possibilité | `OUVERT_CONCEPTUEL` | Une possibilité sans image reste valide |

## 4. Entrée et sortie complètes de chaque chantier

### 00 — Réconciliation **FERMÉ**
**Entrées :** les trois fichiers joints, le code et les documents de #522, inventaire Git.  
**Sorties vérifiées :** relevé daté, 381 chemins / six migrations, héritage de PR, propriétaires et tests, registre R01–R28, frontières de responsabilité et séquence obligatoire.  
**Non réalisé volontairement :** tests, CI, correction de code des étapes suivantes, déploiement et merge.

### 01 — Faits et capacités propriétaires **LIVRÉ EN CODE / VALIDATION À 09**
**Entrée :** R04–R09, frontières R10/R12, `docs/architecture/owner-facts-native-actions.md`. **Résultat technique :** [relevé de réalisation 01](discover-stage-01-owner-facts-2026-10-31.md).  
**Travail :** inspecter pour chaque owner les modèles, selectors/services, API et tests ; partir de fixtures concrètes (Activity/Occurrence, Commerce, Geography/Transport, Opportunity, Funding, Service, Preparation). Corriger uniquement les faits réellement absents ou faux chez leur propriétaire, en réutilisant les fonctions existantes ; prouver la publication/visibilité, temporalité, variations et inconnues.  
**Sortie exigée :** une matrice par owner avec statut `CONFORME_PROUVÉ` ou un écart corrigé, chemin réel, résultat de tests ciblés, contrat de consommation pour 02 ; aucune nouvelle vérité Discovery.  
**Bloquant pour 02 :** un fait propriétaire encore indéfini, une autorisation floue, ou un champ ambigu dont Discovery devrait deviner le sens.

### 02 — Projection Discovery **LIVRÉ EN CODE / VALIDATION À 09**
**Entrée :** sorties 01 ; R01–R03, R10–R11.  
**Travail :** admission, identité, déduplication, familles, faits/provenance, collection/detail, pagination, sécurité et payload borné.  
**Sortie livrée :** code de l'admission et de la projection, scénarios API ajoutés, [dossier 02](discover-stage-02-canonical-projection-2026-10-31.md) ; aucun objet de projection persistant ajouté. Tests non exécutés, résultat non certifié.

### 03 — Médias et ressources **CODE LIVRÉ / DÉPLOIEMENT À VÉRIFIER**
**Entrée :** sorties 02 ; R12–R13 et fichiers Preparation/Presentation.  
**Travail :** ownership/publication, médias first-party, ressources TEXT/FILE/URL, streaming/Reader, ancienne exposition publique et révocation, stockage sûr et budget.  
**Sortie livrée :** [relevé 03](discover-stage-03-media-resources-2026-10-31.md) : gate owner partagé, liens contrôlés, client Flutter first-party, migration historique opt-in et tests écrits. Les tests, fichiers de production et CDN ne sont pas vérifiés. Les anciens liens éditoriaux `hero_image` réclament une action de migration avant suppression physique.

### 04 — N1 **LIVRÉ EN CODE / VALIDATION À 09**
**Entrée :** sorties 03 ; R14–R15.  
**Travail :** huit zones, description expandable, faits fixes, contexte, date ajout à droite, galerie, ressources et actions, responsive Web/Flutter.  
**Sortie de code livrée :** [relevé 04](discover-stage-04-presentation-n1-2026-10-31.md), huit zones préservées, date ajout relative, faits contextualisés, médias owner et tests ciblés écrits. Compatibilité réelle Flutter/Web non attestée sans exécution.

### 05 — Exploration / Carte / Navigation **LIVRÉ EN CODE / VALIDATION À 09**
**Entrée :** sorties 04 ; R16–R19.  
**Travail :** query transférée dans la route Map, sélection, retour, état/pagination, géographie, Scroll/camera, recherche, filtres, curseur invalide.  
**Sortie livrée :** [relevé 05](discover-stage-05-search-map-navigation-2026-10-31.md), query canonique Liste/Carte/Search, scroll/focus, pin et caméra owner, curseurs signés, public invité et tests écrits. Tests d'exécution non réalisés.

### 06 — N2 / Variantes / Comparaison **LIVRÉ EN CODE / VALIDATION À 09**
**Entrée :** sorties 05 ; R20–R21.  
**Travail :** profondeur réelle des propriétaires, descriptions et ressources, variantes, relations justifiées, inconnues, comparaison conditionnelle.  
**Sortie livrée :** [rapport 06](discover-stage-06-n2-variants-comparison-2026-10-31.md) ; chaque famille admise possède N2 en lecture, assessment nuancé, variantes propriétaire liées à Occurrence, comparaison conditionnelle uniquement sur faits complets. Tests écrits non exécutés.

### 07 — Actions et Engagement **PROCHAIN CHANTIER**
**Entrée :** sorties 06 ; R22–R24.  
**Travail :** Save/Watch/Share/owner engagement, handoff et retour, refus, auth, idempotence si nécessaire.  
**Sortie :** chaque CTA affiché est réellement autorisé et produit une confirmation owner vérifiable.

### 08 — Local-first et Confidentialité **VERROUILLÉ**
**Entrée :** sorties 07 ; R13/R18/R19/R25–R26.  
**Travail :** snapshots, rotation, reprise, Profile isolation, media caches, refus/révocation, erreur réseau, démarrage à froid.  
**Sortie :** aucun faux succès offline, aucune donnée révoquée présentée comme fraîche, reprise vérifiée.

### 09 — Certification finale **VERROUILLÉ**
**Entrée :** sorties 08 ; R27–R28.  
**Travail :** tests Django/PostgreSQL, Flutter/Web/E2E, migration, formatage/analyse, compatibilité, vrai Android, CI, contrôle de la branche et décision d'intégration.  
**Sortie :** rapport de fermeture et preuve des gates pertinentes, aucun défaut bloquant ou non justifié.

## 5. Journal des décisions et des preuves

| Date | Étape | Décision / preuve | Effet |
| --- | --- | --- | --- |
| 2026-10-31 | 00 | Relevé `discover-stage-00-reconciliation-2026-10-31.md` ; main `d0f0ec4`, branche observée `7fc2418`, 381 fichiers, six migrations ; contrats joints examinés | Inventaire et frontières fixés |
| 2026-10-31 | 00 | Différences document historique ↔ runtime déclarées ; transferts #523/#525/#526/#527 reconnus ; **ascendance #524 vérifiée**, **divergence #528 vérifiée** | Pas de re-cherry-pick #524, pas de merge aveugle #528 |
| 2026-10-31 | 00 | **Chantier 00 fermé.** Aucun test, CI, changement fonctionnel ou merge. | **Prochain chantier autorisé : 01 exclusivement** |
| 2026-10-31 | 01 | Implémentation propriétaire Funding/Services sur #522 : visibilité du porteur, refus de nouvelle contribution et de démarrage après retrait ; six tests ajoutés, contrat des huit propriétaires consigné dans `discover-stage-01-owner-facts-2026-10-31.md`. | **Livrée en code ; certification différée à 09 sur demande utilisateur.** |
| 2026-10-31 | 02 | Projection multi-famille Discovery réconciliée avec Services, droits Preparation et scope Occurrence, texte inline borné, URLs publiques validées, prix Commerce prioritaires, curseur validé avant composition, erreurs HTTP 400 ; tests et document `discover-stage-02-canonical-projection-2026-10-31.md`. | **Livrée en code, tests non exécutés.** |
| 2026-10-31 | 03 | Gate Publication/Delivery owner+Group+Occurrence, trusted API origin Flutter, sauvegarde atomique/retrait sérialisé, nouveaux MPS hero en privé, commande migration legacy optionnelle et tests, dossier `discover-stage-03-media-resources-2026-10-31.md`. | **Code livré ; migration physique, CDN, anciens `hero_image` et tests non exécutés.** |
| 2026-10-31 | 04 | N1 Web/Flutter : date d'ajout relative à droite, signification des faits temporaux/spatiaux, absence d'inférence, notes limitantes et variantes réelles, galerie MIME/alt et sections conditionnelles ; tests dédiés dans `discovery_mature_screen_test.dart` et `test_m8b_mature_discover.py`, relevé `discover-stage-04-presentation-n1-2026-10-31.md`. | **Code livré, tests non exécutés.** |
| 2026-10-31 | 05 | Query Search/Carte, filtres et focus transités par URL et navigation globale/guest, vraie carte compacte et repères MapLibre, scroll root sauvegardé par profil, curseurs historiques, erreur continuation et sources ; tests et dossier `discover-stage-05-search-map-navigation-2026-10-31.md`. | **Code livré ; tests et carte réelle non certifiés.** |
| 2026-10-31 | 06 | N2 Flutter & Web sur `detail_projection` owner-admis, trois états d'assessment, variants Occurrence, relations explicites, ressources complètes, comparaison bornée aux dimensions réellement communes et tests `discovery_n2_depth_test.dart`/`test_n2_presentation.py`. | **Code livré ; tests/CI/appareil/Web non exécutés ; prochain 07 exclusivement.** |

Pour chaque livraison : ajouter une ligne `date | étape | commit de fin | fichiers | tests ajoutés | résultats exécutés (ou « non exécutés ») | anomalies restantes`. Le mot **certifié** reste réservé à l'exécution du chantier 09.

## 6. Instruction impérative pour la suite

1. Recharger le HEAD courant et le delta depuis l'état du chantier 00 ; vérifier les collisions sans refaire toute l'analyse.
2. La validation exécutée de 01–06 est différée à la certification 09, selon l'instruction explicite de l'utilisateur. Ne jamais prétendre que les tests ont réussi.
3. Conserver dans **#522** la traçabilité des livraisons 01–06 ; toute régression ultérieure se corrige à l'étape active avec un test ciblé.
4. **Ouvrir uniquement le chantier 07** à la prochaine instruction, sans anticiper 08–09. Les opérations physiques de stockage et la certification restent distinctes des livraisons de code.
