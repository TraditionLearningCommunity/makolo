# Z12 — Performance, stabilité et coût des projections UX personnelles

Statut : implémentation Z12 sur le runtime courant.

## 1. Périmètre et méthode

Z12 mesure avant d'optimiser. Il ne crée ni modèle UX persistant, ni snapshot,
ni cache de projection, ni moteur de recommandation, ni index spéculatif.

Le baseline a été établi sur le runtime Z6–Z11 déjà fusionné. Les garde-fous
existants ont été conservés : scope personnel SQL-first, `private, no-store`,
Readiness dérivée, Access distinct de AccessCredential, autorité owner-domain,
Decimal/date-only/unknown inchangés.

Les tests de régression Z12 utilisent le nombre de requêtes et la croissance
face à plusieurs lignes plutôt qu'un seuil chronométrique fragile.

## 2. Collision audit

Base de départ : `main@373e04367996460f5b704a7737bc60e5111f4799`.

Les branches Z6, Z8, Z9, Z10 et Z11 sont entièrement derrière `main`.
La branche Z7 réconciliée est derrière `main`; l'ancienne branche Z7 non
réconciliée diverge encore et ne doit pas servir de base. Les travaux Actor
récents ont convergé sur `main`; Pré-8 est documentaire. Z12 reste limité aux
projections personnelles, à leurs selectors et à des tests ciblés.

## 3. Matrice de baseline

| Surface | Volume/bornage observé | Baseline structurelle | Gap mesuré/observé | Correction Z12 | Cache |
|---|---:|---|---|---|---|
| Maintenant | Journey 20, Dossier 3, Conversation 6, Proposal 6, Recognition 4, legacy 4 | sources déjà bornées, Readiness Journey batchée | pas de cache requis | preuve/conservation des bornes | non |
| En cours | réponse 18 | chaque famille chargeait jusqu'à 18 candidats avant le slice final | travail inutile pouvant atteindre 7 fenêtres et Readiness Dossier hors réponse | budget restant propagé famille par famille; arrêt dès 18 | non |
| Moi | preview 6 | sections bornées | `_bounded` faisait systématiquement COUNT + page; Resources préchargeait toutes les versions des assets retenus | probe `limit+1`, COUNT seulement si nécessaire; version courante via Subquery | non |
| Mes accès | 24, max 50 | pagination offset bornée | selector générique préchargeait credentials, uses et profondeurs Journey non nécessaires; buyer chargeait des credentials qu'il ne peut pas voir | reset des prefetchs; relations de collection explicites; credentials actifs seulement pour le bénéficiaire | non |
| Historique | 24, max 50 | deux fenêtres bornées à `offset+limit`, merge déterministe | pas de chargement de tout l'historique pour la première page | conservé; tests Z6 existants couvrent pagination/stabilité | non |
| Resources | 24, max 50 | collection annotée par version courante; détail versions paginé | racine Moi utilisait encore un prefetch profond des versions | alignée sur une projection de version courante | non |
| Discover | 20, max 50; corpus candidat plafonné | dédup avant sérialisation de page; participant context batché | corpus de recherche peut aller à 500/famille mais reste explicitement borné | pas de nouvelle architecture Z12 | non |
| Journey detail | un Journey | Readiness préchargée/batch owner, profondeur ciblée | riche mais borné à un sujet; aucune collection infinie identifiée | pas de cache/index sans mesure supplémentaire | non |
| Jour J / Live | une Occurrence + perspective participant | scope participant et données Operations owner | vérité volatile et sécurité Access incompatibles avec cache naïf | no-store conservé; aucun cache | non |
| Passport / Groups / Recognition / Loyalty / Partner | owner-backed | profondeurs séparées de Moi; plusieurs collections déjà bornées | pas de justification de snapshot transversal | conserver owners et deep links | non |
| Mark | intent-directed | resolver Z7 cible les owners | aucun motif pour charger une racine personnelle globale | aucun changement Z12 | non |

## 4. Régressions structurelles ajoutées

`core/test_z12_projection_performance.py` couvre :

- En cours rempli par les Journeys : aucune famille suivante n'est interrogée ;
- Mes accès bénéficiaire : la croissance de 1 à 20 Access ne crée pas un N+1 ;
- achat pour autrui : la collection ne charge pas AccessCredential ;
- preview Resources de Moi : le coût ne croît pas avec toutes les versions des
  documents et la réponse reste bornée à six documents.

Ces tests capturent la forme du coût plutôt qu'un nombre SQL absolu qui
deviendrait fragile à chaque évolution légitime du contrat.

## 5. Décisions explicites

Aucun cache n'est ajouté. Les vérités Access, Capacity, Live Queue, Placement,
Readiness et autorité gardent leur fraîcheur et leurs validations owner-domain.

Aucun index n'est ajouté : les corrections retenues concernent la quantité de
travail ORM et les profondeurs chargées, pas un filtre PostgreSQL démontré lent
par EXPLAIN.

Aucune migration et aucune dénormalisation ne sont nécessaires.

## 6. Risques restants

Discover compose encore un corpus multi-famille pouvant atteindre plusieurs
centaines de candidats avant pagination commune. Cette borne est volontaire
pour préserver la pagination logique actuelle. Une évolution vers une fusion
plus DB-first ne doit être entreprise qu'avec une mesure représentative et sans
changer le contrat de déduplication multi-famille.

Les détails Dossier/Project et les agrégats Partner peuvent devenir plus chers
avec des graphes exceptionnellement riches. Z12 ne matérialise pas ces vérités :
un futur changement exige une mesure ciblée du owner concerné.

## 7. Gate de fermeture

Avant merge :

- tests Z12 ciblés verts ;
- suites Z2/Z4/Z5/Z6/Z8/Z9 et sécurité Z11 pertinentes vertes ;
- `makemigrations --check --dry-run` vert ;
- CI complète verte ;
- branche réconciliée avec le `main` courant ;
- vérification du `main` après merge.

La règle de fermeture reste : une optimisation ne doit ni élargir la visibilité,
ni déplacer une vérité métier vers une projection, ni rendre une donnée
transactionnelle stale.
