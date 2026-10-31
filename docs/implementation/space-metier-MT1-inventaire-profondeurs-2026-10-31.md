# MT1 — Cartographie réelle des profondeurs Métier Space

**Statut : inventaire vérifié au niveau des fichiers et routes ; pas de validation d'exécution.**  
**Date : 2026-10-31. PR : #522, branche `fix/discover-a-continuation-context-20261014`.**  
**Pas de code métier modifié dans MT1.** Sources prioritaires : `organizations/api/space_work_projection.py`, `organizations/space_work_composition.py`, `organizations/space_work_web.py`, `organizations/space_retrieval_detail_web.py`, `organizations/urls.py`, `mobile/lib/features/space/space_work_surface.dart`, `space_work_collection_screen.dart`, `space_shell_routes.dart`, et les huit contrats `docs/ux/Makolo_UX_Space_Metier_*` du 8 octobre. HEAD à revérifier lors de MT2.

## Légende : vérité plutôt que promesse

- **E** : route/contrat explicitement retrouvé dans le code, **pas** la preuve d'un E2E.
- **P** : profondeur ou handoff seulement partiel, générique, Web-only ou API-only.
- **V** : à vérifier dans l'owner et les permissions ; ne pas inventer une API manquante.
- **C** : conditionnel aux capacités métier réellement présentes ; pas un manque universel.
- **X** : hors périmètre/anti-feature.

Le N1 n'a **aucun layout universel** ; le N2 n'a **aucune fiche universelle** ; le N3 représente **0..n profondeurs owner-backed** depuis une même réalité. Identité UI, shell, géométrie, navigation, Behavior, accessibilité, états et charte Makolo communs. Une seule application, huit grammaires.

## Inventaire transversal réellement retrouvé

| Surface | Preuve dans le dépôt | Diagnostic MT1 |
| --- | --- | --- |
| N1 des 8 archétypes | `space_work_composition.py` fournit `reading_groups`; API Work sert les sections owner-backed | **E (structure), P (expérience et couverture)** |
| Sélection owner `kind/id` | `build_space_work_projection(...source_kind,source_id,...)` | **E côté projection, P en profondeur complète** |
| N2 Activity/Occurrence Web | `organizations/urls.py` : `space-retrieval-activity-detail`, `space-retrieval-occurrence-detail` | **E Web — détail de lecture, pas toutes actions** |
| N2 commande Web | `space-retrieval-order-detail`, avec contrôle `ORDERS_VIEW` | **E Web — lecture owner-scopée** |
| N2 route et départ Web | `console-transport-route-detail`, `console-transport-departure-detail` | **E Web owner ; profondeur à qualifier** |
| Offre/vehicule Web | `console-offers`, `console-transport` | **P : destinations de collection/console, pas preuve d'un N2 item** |
| Dossier Services | liens opérateur dans `space_work_web.py`, cas Service dans la projection | **P : vérifier cible/capacité à chaque scope** |
| N1 Flutter | `space_work_surface.dart`, repository/work source, `space_shell_routes.dart` | **E lecture native de sections, P composition multi-granulaire** |
| Collection Flutter | `space_work_collection_screen.dart` : continuation `section` et `offset` | **E pagination de collection, P pour sélection N2** |
| N2/N3 Flutter | `SpaceWorkSurface` route par `source` et certaines actions Jour J | **P ; ne pas déclarer toutes les profondeurs propriétaires natives** |
| Variabilité de couverture | sections ont `coverage_state` et `business_world.perspectives[primary]` | **P : `established/partial/unavailable/hidden` par owner non démontré uniformément** |
| N3 multiples par N2 | plusieurs owners existent, mais pas de contrat transverse de handoff complet | **P : inventaire précis et retour contextuel nécessaires** |

## Parcours par archétype : N1 → N2 → N3 (0..n)

Le contenu N1 est déjà composé dans G1–G4 ; les N2/N3 ci-dessous sont **décidés conceptuellement mais évalués par preuve d'exécution**.

| Archétype | N1 retenu | N2 retenus | N3 réels ou conditionnels à vérifier | Qualification |
| --- | --- | --- | --- | --- |
| **Generic / Activités** | préparations et réalisations puis activités durables | Activity ; Occurrence ; demande si réelle ; lieu si owner | gestion Activity, Occurrence, resources, préparation, Journey, Capacity, Jour J | **N1 E ; Activity/Occurrence Web E ; autres P/V/C** |
| **Community / Initiatives** | initiatives et actions collectives, Occurrences réelles | Initiative=Activity contextuelle ; action terrain/Occurrence ; contribution si owner | préparation, ressources, demandes, événements, groupes sous droit | **N1 E ; Activity/Occurrence Web E ; spécificité terrain P/C** |
| **Education / Programmes** | programmes, sessions et demandes d'inscription | Programme=Activity ; Session=Occurrence ; inscription=Journey/Request | session, évaluation demande, Requirements, Forms, Resource, Capacity, Access, Jour J | **N1 E ; Activity/Occurrence Web E ; inscription N2/N3 P/V** |
| **Services / Prestations** | demandes et dossiers, catalogue durable | Prestation=Activity ; Demande ; Dossier=Journey Service ; Occurrence | examen, étape Journey, exigences, pièces, responsable, blocker, résultat | **N1 E ; cas opérateur P ; profondeurs N3 V/C** |
| **Commerce** | engagements/commandes réels + offres durables | Offer ; CommerceOrder ; réalisation ; obtention seulement si owner | modifier Offer, capacité, paiement, remise, preuves et Access si présents | **N1 E ; commande Web E ; offres item P ; autres C/V** |
| **Transport** | départs et exploitation + routes/véhicules | Départ=Occurrence+TransportDeparture ; Route ; TransportService=Activity ; Vehicle ; lieu si owner | opérations, affectation, capacité, contrôle/Access, incidents, Jour J | **N1 E ; route/départ Web E ; véhicule item P ; autres C/V** |
| **Creative / Créations** | œuvres et présentations réelles | Création=Activity contextuelle ; présentation=Occurrence ; prestation/offre si owner | ressources, média publié, préparation, date, Offer/Service réels | **N1 E ; Activity/Occurrence Web E ; création spécialisée P/C** |
| **Media / Productions** | productions durables et éditions réelles | Production=Activity ; Édition=Occurrence ; série/collection si owner attesté | ressources, média contextualisé, Jour J et diffusion seulement si owner | **N1 E ; Activity/Occurrence Web E ; diffusion/editing spécialisé V/C** |

Cette matrice **ne certifie pas** qu'un N2 Activity générique constitue déjà une bonne expérience Programme, Création ou Production. Le N2 humain peut demander une composition supplémentaire ; on réutilise la source et la profondeur propriétaire plutôt que créer un second modèle.

## Écarts critiques à traiter par MT2–MT8

**P0 — Contrat et sécurité (MT2).** Vérifier chaque lien de `BusinessEntry` depuis toutes responsabilités, notamment les mandatés Activity-limited ; identifier absence d'owner vs permission interdite ; assurer `coverage_state` honnête, sélection stable, identité, action/handoff réel, multiple N3, pas de présomption de capacité de création. Les liens sont une invitation, pas une délégation d'autorité.

**P1 — N2 spécifiques (MT3–MT6).** Dans chaque paire d'archétypes, vérifier les N2 concrètement utiles et les approfondissements N3 réellement disponibles ; compléter seulement la présentation et les handoffs manquants. Prioriser programme/session/inscription, prestation/dossier, offre/commande, départ/route/véhicule, œuvre/présentation et production/édition. Les variantes sans owner restent explicitement conditionnelles.

**P1 — Continuité de navigation (MT7).** Préserver Space, responsabilité, perspective, section, filtre, sélection, défilement, owner d'origine et retour. Un N2 peut ouvrir plusieurs N3 ; un N1 peut sauter N2 ; pas de router générique factice. Vérifier les destinations Flutter séparément des routes Web.

**P0 — Revocation/local-first (MT7/MT8).** Changement acteur, cache isolé, stale/offline, permission_loss, ressource privée, URL média révoquée, pas de Live artificiel, pas de mutation sur cache seul.

**P1 — Qualité perceptive/produit (MT7/MT8).** Auditer les huit grammaires avec une même identité visuelle adulte : typographie, rythme, adaptive, transitions, densité, sens de chaque composant et accessibilité. Refuser le template `titre/statut/gros bouton` uniforme **et** huit layouts sans parenté.

## Ce qui est explicitement non garanti par MT1

MT1 n'est **pas** un test Django/Flutter, un audit E2E exhaustif du dépôt, ni une garantie que toutes les fonctionnalités de Makolo sont livrées. Les routes propriétaires prouvées peuvent échouer en cas de permissions, état, données absentes ou bug de runtime. Les tests ciblés et scénarios réalistes sont requis dans MT2–MT8.

Une application de qualité 2027 exige : achèvement des parcours plutôt que volume d'écrans, complétude fonctionnelle **par usage légitime**, sécurité, résilience, vitesse, accessibilité, cohérence du design system, observabilité et preuve via tests utilisateurs/QA ; jamais une promesse « rien ne manquera » non démontrée.

## Prochaine sous-tâche : MT2

Pour chaque N2 de la matrice, établir un **registre de handoffs owner** : identity, scope, permission, API/reverse route, Flutter route existante ou absente, état de connaissance, navigation et retour ; combler le contrat commun sans créer de nouveaux owners ou une mutation métier. Les N2 spécifiques seront ensuite clos MT3–MT6, assemblés MT7 et validés MT8.

**Aucun nouveau modèle persistant. Aucun thème visuel indépendant par archétype. Aucun workflow universel de création, paiement ou livraison.**
