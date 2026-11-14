# MT8 — Fermeture fonctionnelle de Métier / Space

**Date :** 4 novembre 2026  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Branche unique de livraison :** `fix/discover-a-continuation-context-20261014` (**PR #522**)  
**Programme :** Métier Space, MT1 → **MT8 final**. **Aucun MT9 Métier.** Le `M9` du programme Mature est distinct.

## Décision de fermeture

**MT8 clôt la phase de construction fonctionnelle de Métier Space en source.**
Les huit grammaires s'appuient sur les projections et propriétaires existants, avec une racine N1, un N2 contextualisé et des N3 appartenant au domaine concerné. La livraison MT8 corrige les points de continuité et de vérité de présentation observables à partir du code, **sans ouvrir de nouveau programme, modèle persistant, permission ou mutation**.

**Statut de preuve :** les changements sont committés dans #522 et les fichiers ont été relus. Conformément à la consigne d'exécution de ce chantier, il n'y a pas eu de campagne de tests/CI, ni de certification PostgreSQL, navigateur ou appareil dans cette session. Il serait incorrect d'affirmer que tous les scénarios ont réussi en runtime. La fermeture du périmètre fonctionnel source n'est donc pas une certification production.

## 1. Métier à travers ses huit grammaires

| Archetype | Entrée N1 orientée action | Profondeur N2 propriétaire | N3 réel |
| --- | --- | --- | --- |
| Generic | Activités, préparation, dates et réalisations | Activity / Occurrence / Journey | Gestion Activity, ressources, demandes et Jour J si ouvert |
| Community | Initiatives et actions sur le terrain | Activity / Occurrence / Journey | Activity, Resources, Funding si porté et autorisé |
| Education | Programmes, sessions, inscriptions | Activity / Occurrence / Journey | Requirements/inscription propriétaire, ressources, actions requises |
| Service Provider | Prestations, demandes et dossiers | Activity / Occurrence / Journey | ServiceCase propriétaire, exigences évaluées et suivi autorisé |
| Commerce | Commandes, offres, disponibilité | Activity / Offer / CommerceOrder | Offre éditable si autorisée ; Payment distinct du fait de commande |
| Transport Operator | Départs, services, routes, véhicules | Activity / Occurrence / Route / Vehicle | Exploitation du départ, capacité et Jour J par leurs owners |
| Creative | Créations durables, présentations réelles | Activity / Occurrence | Ressources et atelier Presentation, médias publiés seulement |
| Media | Productions durables, éditions réelles | Activity / Occurrence | Ressources et Presentation, aucune diffusion/« feed » inventée |

**Invariants :** un Profil reste une personne globale ; Space, Activity, Occurrence, Journey et les propriétaires conservent leurs identités et frontières. Membership/Team/Assignment n'accordent pas Permission/Mandate. Une source autorisée ne transfère ni Access, ni Payment, ni données privées. Un média représente une réalité propriétaire ; il ne devient ni un post ni un nouveau propriétaire.

## 2. Fermetures spécifiques de MT8

### 2.1 Handoffs Flutter : source exacte, action exacte

`mobile/lib/features/space/space_work_owner_actions.dart` vérifie maintenant **la destination API canonique exacte** de `open_request`, `open_service_case_native` ou `open_day_of`, y compris Space et identifiant source. Une chaîne contenant simplement le même UUID ne suffit plus ; les URLs externes et les destinations d'un autre owner sont rejetées. Le N3 réinterroge ses propres permissions. Aucun lancement de commande hors ligne n'est autorisé par Work.

### 2.2 Retour explicite et détails non vérifiés

`mobile/lib/features/continuity/space_retrieval_owner_screen.dart` distingue une erreur de disponibilité d'un accès réellement refusé (401/403/404), n'affiche pas une ancienne copie du détail comme fraîche et garde une action d'actualisation. Le bouton **Retour à Métier** ouvre la surface Métier ou sa collection contextuelle, au lieu d'effectuer un `pop()` potentiellement dirigé vers Search, History ou un autre N3. L'historique normal garde son geste Retour système indépendant.

### 2.3 Preview et couverture sans faux « établi »

`organizations/api/space_work_projection.py` marque chaque section avec continuation `has_more` comme **`coverage_state=partial`**, même avec Permission Space complète. La composition/lecture racine est également partielle si le preview est borné. Une page paginée ou un mandat Activity limité reste partiel ; le code ne prétend pas que le premier aperçu montre tout l'Espace. Readiness ne devient pas un état persistant ou un score global.

### 2.4 Pagination Web bornée et sortie

`organizations/space_work_web.py` n'émet plus de destination page suivante après `MAX_WORK_PAGE` (respect de la borne API). À la limite d'une collection encore tronquée, `templates/organizations/space/work.html` oriente vers la recherche Space plutôt qu'un lien cassé. N1 → N2 → collection d'origine conserve la responsabilité et la page de départ via le contrat MT7, sans en faire une permission.

### 2.5 Échec de continuation mobile

`mobile/lib/features/space/space_work_collection_screen.dart` différencie un premier chargement impossible d'une erreur d'actualisation d'éléments auparavant relus avec succès. Ces éléments ne sont pas décrits comme « à jour » ; toute action propriétaire revalide sa permission sur l'API. Une révocation d'autorité efface toujours la collection (comportement préexistant).

### 2.6 Parité des faits propriétaires N1 sur Flutter

`mobile/lib/features/space/space_work_surface.dart` expose les données déjà disponibles et autorisées, sans les recomposer :

- **Transport** : route réelle, véhicule affecté uniquement si le serveur le divulgue et capacité physique identifiée comme telle.
- **Capacity** : disponibilité/limite/désactivation uniquement pour les faits émis par un `CapacityPool`, sans inférer Placement ni passage.
- **Service** : nombre de conditions satisfaites sur le total quand la base est `service_requirement_assessment`, **sans conclure « prêt »**.
- **Permission** : un Work limité par les mandats porte une mention explicite, comme sur Web.

Cela complète les dates, lieux, prix unitaires, statut propriétaire et médias de reconnaissance préexistants, sans transformer les offres en paiements ni les réalisations en publications génériques.

## 3. États de comportement retenus

| État | Comportement |
| --- | --- |
| Vide réellement établi | Le message calme/owner n'est utilisé que pour la vue qu'il décrit, pas pour tout le système. |
| Vue partielle | Mention de responsabilité limitée ou continuation ; jamais « tout est couvert ». |
| Source indisponible | Message de vérification impossible, possibilité de réessayer ; pas de contenu ancien présenté comme actuel. |
| Permission perdue | Relecture sous Space/Mandate courant, refus sans projection d'un autre Space/Profil. |
| Hors réseau / actualisation échouée | Pas de nouvelle autorité locale. Une collection déjà lue est étiquetée comme non actualisée ; les N2/N3 recontrôlent l'owner. |
| Succès d'action propriétaire | Les effets de création, paiement, opération, accès, etc. restent chez leurs owners ; Work ne simule aucun succès. |

## 4. Frontières et non-objectifs de fermeture

- Pas de modèle `WorkItem` ou `BusinessEntry`, de workflow universel, de feed, de CMS, ni d'analytics/watch-time.
- Aucun changement de schéma, migration, backfill, rôle global ni nouvelle API de mutation.
- Aucun changement direct à `main`; tout est dans **#522**, avec fermeture de la PR redondante #533 déjà réalisée dans MT7.
- La suite des capacités indépendantes de **Nous**, **Piloter**, **Maintenant**, **Découvrir** ou de l'expérience Mature ne justifie pas un MT9.

## 5. Éléments de vérification disponibles et limite honnête

- Le code consolidé MT1–MT7 et les owners G1–G4 ont été comparés pendant MT8.
- Un cas serveur ciblé a été ajouté dans `organizations/test_space_work_mt7.py` contre les previews faussement `established`.
- Un cas Flutter ciblé a été ajouté dans `mobile/test/space_work_mt7_test.dart` contre les handoffs contenant le bon identifiant comme simple sous-chaîne.
- **Ces tests ne sont pas déclarés exécutés.** Aucun contrôle visuel ou E2E réel n'a été effectué depuis ce connecteur GitHub. Ce document ne certifie pas une qualité d'appareil ni un déploiement.
- En cas de défaut réel découvert plus tard, corriger l'owner ou le renderer concerné, sans redémarrer artificiellement MT9.

## 6. Sortie du programme MT

**Le chantier de construction Métier Space est fermé en source à MT8, dans la PR #522.** Les preuves d'exécution et la validation de mise en circulation restent des responsabilités du programme Mature/qualité du produit, **pas de nouveaux trains MT**. Le programme de fermeture global reste distinct : M7 → M8 → M9 → M10 → Mobile.

> Makolo marche pour vous. Pas le plaisir de rester. Le plaisir d'avancer.
