# Makolo — registre de fermeture de Découvrir
**Document vivant — responsable : branche [#522](https://github.com/TraditionLearningCommunity/makolo/pull/522)**  
**Initialisé le :** 2026-10-31  
**Chantier courant :** **01 — Vérités et capacités propriétaires** (*non commencé par ce commit ; prochain travail autorisé*).  
**Chantier 00 :** **FERMÉ — réconciliation documentaire**.  
**Relevé de référence :** [chantier 00 — réconciliation](discover-stage-00-reconciliation-2026-10-31.md).

> **RÈGLE DE PASSAGE : un chantier à la fois.** Les chantiers sont **séquentiels**, non parallèles. Ne jamais ouvrir N+1 tant que tous les critères de sortie de N ne sont pas satisfaits et documentés. Les statuts `présent/partiel` décrivent l'implémentation rencontrée dans le code, **pas** l'état d'exécution du chantier. Les étapes 01–09 restent `VERROUILLÉ` ou `À OUVRIR` tant qu'on n'a pas travaillé et validé leur sortie. L'exécution CI est une exigence de la fermeture globale 09, explicitement **hors chantier 00** et non lancée ici.

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

**Critère de preuve minimal pour toute modification des chantiers 01–08 :** besoin et contrat, source de vérité, fichiers modifiés, test ciblé (ou limite explicite et action de validation), résultat, preuve que les permissions et l'identité sont préservées. Une validation non exécutée **n'est pas verte**.

### Anti-features protégées

Pas de modèle persistant générique `Possibility`, de scoring client, de deuxième source cartographique indépendante, de faux owner, de capacité créée d'après un texte, de déduction d'autorité par Membership/Space, de conversion de `unknown` en gratuit/indisponible, de Save → Journey, de Watch → engagement, de feed infini artificiel, de migration pour confort visuel, ni de refonte de Now/En cours/Moi.

## 1. Tableau de passage strict

| Étape | Nom | État d'exécution | Sortie vérifiable |
| --- | --- | --- | --- |
| **00** | Réconciliation et gel des contrats | **FERMÉ** | [Inventaire daté](discover-stage-00-reconciliation-2026-10-31.md), sources et frontières, registre unique |
| **01** | Vérités et capacités propriétaires | **À OUVRIR** | Matrice de faits par verticale, selectors propriétaire vérifiés et tests ciblés ; aucune vérité inventée par Discovery |
| **02** | Projection canonique Discovery | **VERROUILLÉ** | API collection/détail, admission, identité, sécurité, frais de connaissance et pagination contractuels |
| **03** | Médias, ressources et stockage | **VERROUILLÉ** | Publication/retrait, accès, URL first-party, viewers, volumes et compatibilité legacy contrôlés |
| **04** | Presentation N1 | **VERROUILLÉ** | N1 compact/wide et Web adaptés, faits utiles et actions sans CTA fictif |
| **05** | Recherche, carte et navigation | **VERROUILLÉ** | Une query/selection à travers liste, carte, détail et retour, continuation et état spatial préservés |
| **06** | N2, variantes et comparaison conditionnelle | **VERROUILLÉ** | Profondeur owner-backed, inconnues et variantes sans comparaison universelle inventée |
| **07** | Save, Watch, Sharing, engagements N3 | **VERROUILLÉ** | Transitions autorisées, idempotence si nécessaire, retour owner confirmé |
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
| R01 | Possibilité distincte du modèle brut, identité owner stable | `EXISTANT_SOURCE` | `discovery/api/composition.py`, `discovery/api/projections.py` | 02 |
| R02 | Admission, visibilité, Groupe et non-divulgation | `PARTIEL` — tests couvrent des cas, matrice complète à valider | `discovery/api/test_mature_discovery.py` | 02 |
| R03 | Champ multi-famille sans classement local | `EXISTANT_SOURCE` | `discovery/unified.py`, `discovery/api/composition.py` | 02 |
| R04 | Faits et prix établis par Commerce | `OWNER_EXTERNE`, mécanisme identifié | `commerce/offer_price_facts.py` | 01 |
| R05 | Horaires/Occurrences/variantes sans inférence | `PARTIEL` | `discovery/api/composition.py`, modèles Activity | 01 puis 02 |
| R06 | Lieux multiples, public/privé et rôles transports | `PARTIEL` | `discovery/api/composition.py`, tests API | 01 puis 02/05 |
| R07 | Conditions et fraîcheur des Opportunities | `OWNER_EXTERNE`, mécanisme identifié | `opportunities/knowledge.py` | 01 |
| R08 | Conditions de Funding sans éligibilité fictive | `À_VÉRIFIER` | `funding/test_discovery.py` | 01 |
| R09 | Handoff Service owner et Journey idempotente | `EXISTANT_SOURCE`, couverture à prouver | `services/native_start.py` | 01 puis 07 |
| R10 | Ressources publiques, sans données restreintes | `PARTIEL` — volume inline à borner sans cacher les items | `discovery/api/composition.py` | 02 puis 03 |
| R11 | Cohérence collection/détail/médias | `PARTIEL` | `discovery/api/media_bindings.py`, `test_media_bindings.py` | 02 puis 03 |
| R12 | Media-use owner, statut publié, retrait | `EXISTANT_SOURCE`, déploiement legacy à contrôler | `presentations/media_delivery.py`, `test_media_use.py` | 03 |
| R13 | Rétention automatique de médias réellement first-party | `ÉCART_CODE` — vérification du chemin sans origine de confiance suffisante | `discovery_offline_store.dart`, `retained_public_discovery_image.dart` | 03 puis 08 |
| R14 | N1 contextualisé et adaptatif | `PARTIEL` — rendu présent, acceptation exhaustive non attestée | `discovery_possibility_unit.dart`, `discovery-n1-layout-contract.md` | 04 |
| R15 | N1 dates à droite, faits stables, ressources dépliables | `PARTIEL` — implémentation à vérifier en UX réelle | `discovery_possibility_unit.dart` | 04 |
| R16 | Recherche/filtres/continuation sur mêmes critères | `PARTIEL` — root et Search utilisent des chemins distincts | `discovery_screens.dart`, `discovery_repository.dart` | 05 |
| R17 | Carte liée au même champ et aux mêmes critères | `ÉCART_CODE` — route autonome utilise la query par défaut | `discovery_routes.dart`, `discovery_screens.dart` | 05 |
| R18 | Retour, sélection, scroll et contexte après redémarrage | `ÉCART_CODE` — sauvegarde page/curseur seulement dans le mécanisme relevé | `discovery.presentation-position` | 05 puis 08 |
| R19 | États NO_MATCH/END_OF_FIELD/OFFLINE distincts | `PARTIEL` — code de sélection disponible, scénarios à éprouver | `discovery_selector.dart`, `discovery_wire.dart` | 05 puis 08 |
| R20 | N2 sens, profondeur, variantes et inconnues | `À_VÉRIFIER` | `discovery_mature_view.dart`, `discovery_reader.dart` | 06 |
| R21 | Comparaison conditionnelle sur faits comparables | `À_VÉRIFIER`; pas d'obligation de comparaison universelle | Contrats UX joints | 06 |
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

### 01 — Faits et capacités propriétaires **À OUVRIR**
**Entrée :** R04–R09, frontières R10/R12, `docs/architecture/owner-facts-native-actions.md`.  
**Travail :** inspecter pour chaque owner les modèles, selectors/services, API et tests ; partir de fixtures concrètes (Activity/Occurrence, Commerce, Geography/Transport, Opportunity, Funding, Service, Preparation). Corriger uniquement les faits réellement absents ou faux chez leur propriétaire, en réutilisant les fonctions existantes ; prouver la publication/visibilité, temporalité, variations et inconnues.  
**Sortie exigée :** une matrice par owner avec statut `CONFORME_PROUVÉ` ou un écart corrigé, chemin réel, résultat de tests ciblés, contrat de consommation pour 02 ; aucune nouvelle vérité Discovery.  
**Bloquant pour 02 :** un fait propriétaire encore indéfini, une autorisation floue, ou un champ ambigu dont Discovery devrait deviner le sens.

### 02 — Projection Discovery **VERROUILLÉ**
**Entrée :** sorties 01 ; R01–R03, R10–R11.  
**Travail :** admission, identité, déduplication, familles, faits/provenance, collection/detail, pagination, sécurité et payload borné.  
**Sortie :** tests API et contrat réel documenté ; aucun objet de projection persistant ajouté.

### 03 — Médias et ressources **VERROUILLÉ**
**Entrée :** sorties 02 ; R12–R13 et fichiers Preparation/Presentation.  
**Travail :** ownership/publication, médias first-party, ressources TEXT/FILE/URL, streaming/Reader, ancienne exposition publique et révocation, stockage sûr et budget.  
**Sortie :** scénarios de lecture/retrait/rejet sur stockage et URLs réels, sans média inventé ni exposition privée.

### 04 — N1 **VERROUILLÉ**
**Entrée :** sorties 03 ; R14–R15.  
**Travail :** huit zones, description expandable, faits fixes, contexte, date ajout à droite, galerie, ressources et actions, responsive Web/Flutter.  
**Sortie :** N1 compact/wide/accessibilité et variantes métier prouvées.

### 05 — Exploration / Carte / Navigation **VERROUILLÉ**
**Entrée :** sorties 04 ; R16–R19.  
**Travail :** query transférée dans la route Map, sélection, retour, état/pagination, géographie, Scroll/camera, recherche, filtres, curseur invalide.  
**Sortie :** tests de traversée complète des mêmes critères, sans deuxième champ ou changement silencieux.

### 06 — N2 / Variantes / Comparaison **VERROUILLÉ**
**Entrée :** sorties 05 ; R20–R21.  
**Travail :** profondeur réelle des propriétaires, descriptions et ressources, variantes, relations justifiées, inconnues, comparaison conditionnelle.  
**Sortie :** chaque verticale active présente N2 sans inventer des faits ou comparer des dimensions incompatibles.

### 07 — Actions et Engagement **VERROUILLÉ**
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

Pour chaque nouvelle clôture : ajouter une ligne `date | étape | HEAD de fin | fichiers | tests exécutés + résultats | anomalies restantes | décision de passage`. Ne jamais écrire `FERMÉ` pour un chantier dont les preuves n'existent pas.

## 6. Instruction impérative pour la suite

1. Recharger le HEAD courant et le delta depuis l'état du chantier 00 ; vérifier les collisions sans refaire toute l'analyse.
2. Travailler **uniquement le chantier 01** et le terminer intégralement (inventaire owners + corrections justifiées + tests ciblés + contrat de sortie).
3. Mettre à jour ce registre dans **#522** avec la preuve exacte.
4. Seulement ensuite ouvrir **02**. Ne pas pré-implémenter 02–09, même si des parties sont déjà présentes.
