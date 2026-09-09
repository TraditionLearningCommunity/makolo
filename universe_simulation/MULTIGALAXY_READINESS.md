# Préparation à la simulation multi-galaxies

Ce document complète `IMPLEMENTATION_STATUS_RELATIVITY_SCALE.md` après les derniers commits de consolidation. Il décrit le point de départ recommandé pour la prochaine phase : génération puis exécution d'une simulation multi-galaxies.

## 1. Statut

Le moteur possède maintenant les briques structurantes nécessaires pour construire le scénario multi-galaxies sans réécrire la relativité ou le moteur numérique :

- Newton classique conservé ;
- relativité spéciale fondée sur l'impulsion ;
- 1PN ;
- relativité générale sur métriques prescrites ;
- Schwarzschild, Kerr, Reissner-Nordström/Kerr-Newman, FLRW ;
- géodésiques et lignes d'univers forcées ;
- temps propre ;
- photons / géodésiques nulles ;
- horizons et garde causal ;
- backend NumPy ;
- Barnes-Hut 3D et backend Numba ;
- hiérarchie de systèmes / agrégats ;
- LOD ;
- temps multi-taux ;
- événements spatiaux continus ;
- persistance chunkée ;
- visualisation LOD ;
- population SR vectorisée ;
- migration dynamique SR -> GR ;
- retour GR -> SR uniquement par projection locale explicitement fournie ;
- diagnostic de potentiel lointain pour choisir le régime ;
- référentiels inertiels hiérarchiques avec transformations de Poincaré/Lorentz.

## 2. Activité physique et propriété numérique

Une distinction explicite existe désormais entre :

```text
active
    = le corps existe / est physiquement actif

participating
    = ce backend numérique possède actuellement son évolution
```

Cela rend possible :

```text
vaisseau SR dans tableau massif
        |
        | entrée dans zone où la courbure devient pertinente
        v
ligne SR suspendue (corps toujours actif)
        |
        v
objet matérialisé en GR
        |
        | sortie + projection locale explicitement choisie
        v
ligne SR réactivée
```

Un invariant d'orchestration interdit à deux domaines d'avancer simultanément le même corps.

## 3. Couplage gravitationnel des vaisseaux relativistes

Le moteur ne fait pas :

```text
vaisseau à 0.99c
+ champ galactique
-> F_newton / m
```

À la place, le champ lointain agrégé sert d'abord à calculer un indicateur faible-champ :

```text
|Phi| / c^2
```

avec la vitesse `v/c` et la précision demandée.

Le sélecteur décide ensuite :

```text
SR reste suffisant
ou
GR devient nécessaire
```

La requête de potentiel ne modifie pas la trajectoire. Une région agrégée signale aussi si un véhicule pénètre dans son rayon de couverture, ce qui permet d'ouvrir son LOD.

## 4. Pas de double comptage hiérarchique

Une nouvelle frontière d'agrégation ne renvoie jamais simultanément :

```text
galaxie agrégée
+ ses systèmes agrégés descendants
```

Si la galaxie est fermée, elle est la source lointaine.

Si elle est ouverte, le calcul descend vers ses systèmes.

Cela évite de compter deux fois la même masse.

## 5. Référentiels et précision numérique

Les états locaux ne doivent pas être stockés comme :

```text
coordonnée intergalactique ~ 1e22 m
+ orbite lunaire ~ 1e8 m
```

car cela dégrade inutilement la précision flottante.

La stratégie retenue est :

```text
cadre du groupe galactique
    |
    +-- cadre de galaxie
            |
            +-- cadre de système stellaire
                    |
                    +-- états locaux
```

Les changements entre cadres inertiels utilisent des événements espace-temps et transformations de Lorentz/Poincaré. On ne prétend pas transformer un snapshot spatial relativiste entier en conservant la simultanéité, puisque celle-ci dépend du référentiel.

Les tableaux de grandes populations restent donc autoritaires dans leur propre cadre ; les transformations sont effectuées au moment d'un événement de transition individuel.

## 6. Persistance hybride

Une même exécution peut désormais conserver :

```text
domains/
    stellar-population/
        states/chunks/*.npz

    relativistic-ships/
        states/chunks/*.npz

    gr-local/
        states/worldlines.jsonl
```

Les chunks des tableaux enregistrent séparément :

- activité physique ;
- participation numérique.

Les objets GR matérialisés enregistrent :

- `ct, x, y, z` ;
- tangente 4D ;
- paramètre affine ;
- temps propre ;
- type causal ;
- carte de coordonnées.

## 7. Échelle validée

Les benchmarks sont indicatifs et dépendent de la machine.

Le chemin Barnes-Hut + Numba a été testé jusqu'à environ :

```text
100 000 corps : ~ ordre de la seconde / évaluation
500 000 corps : ~ 4.5 à 6 s / évaluation selon réglages
```

Le million de corps n'a pas terminé dans la fenêtre d'exécution disponible et reste donc :

```text
OBJECTIF
!=
CAPACITÉ VALIDÉE
```

Pour la première simulation ambitieuse, la cible recommandée est par conséquent de l'ordre de **500 000 entités cataloguées**, avec seulement une fraction `ACTIVE` à chaque échelle.

## 8. Le point essentiel : 500 000 entités ne signifient pas 500 000 N-body actifs à chaque pas

Le scénario doit employer :

```text
ACTIVE
ANALYTIC
AGGREGATED
TRACER
VISUAL_ONLY
```

Exemple :

- galaxie lointaine : agrégat ;
- systèmes lointains : agrégats ou analytiques ;
- planètes stables : propagateurs analytiques ;
- astéroïdes visuels : tracers ;
- vaisseaux relativistes : SR actif ;
- voisinage visité : matérialisation détaillée ;
- trou noir approché : GR local.

C'est cette hiérarchie, et non un N-body direct d'un demi-million de corps à chaque micro-pas, qui rend la simulation longue réaliste numériquement.

## 9. Premier scénario recommandé

Le premier run multi-galaxies devrait viser approximativement :

```text
10 galaxies
~2 000 à 2 500 systèmes stellaires catalogués
quelques milliers d'étoiles
~15 000 à 25 000 planètes
plusieurs dizaines de milliers de satellites naturels
plusieurs centaines de milliers d'astéroïdes/débris/tracers
~5 000 voyageurs interstellaires/relativistes
~500 000 entités au total
```

Les corps artificiels rapides peuvent couvrir plusieurs classes :

```text
0.01c - 0.2c
0.2c  - 0.8c
0.8c  - 0.99c
0.99c - 0.999999c
```

Les vitesses sont SR par construction et ne dépassent jamais `c`.

## 10. Durée recommandée

Une durée de l'ordre de :

```text
1 à 5 millions d'années de temps coordonné
```

est cohérente pour observer :

- traversées de bras/secteurs ;
- passages de nombreux systèmes ;
- départs et arrivées interstellaires ;
- quelques voyages intergalactiques dans un groupe compact ;
- différences importantes entre temps coordonné et temps propre de certains véhicules.

La dynamique galactique elle-même restera lente à cette échelle temporelle ; on ne fera pas artificiellement tourner les galaxies à une vitesse visuellement spectaculaire mais physiquement fausse.

## 11. Multi-taux envisagé

Le run ne doit pas avoir un `dt` unique.

Ordres de grandeur de cadence à adapter :

```text
agrégats galactiques       : centaines / milliers d'années
systèmes stellaires lointains : années / décennies
voyage interstellaire SR   : jours / mois / années selon événement
système local ouvert       : heures / jours
orbites rapprochées        : secondes / minutes
GR près d'objet compact    : pas adaptatif propre au solveur
```

Toutes les sorties communes sont faites à des barrières de temps coordonné où les domaines sont synchronisés.

## 12. Ce qui reste avant de lancer le gros run

Il ne reste plus une refonte physique générale. La prochaine phase est principalement **construction du scénario** :

1. générateur déterministe des 10 galaxies ;
2. catalogue des systèmes et corps locaux en coordonnées hiérarchiques ;
3. matérialisation à la demande d'un système ;
4. population initiale des véhicules SR et missions ;
5. politiques de LOD/régime utilisant les événements et diagnostics existants ;
6. test miniature du scénario ;
7. run 10k ;
8. run 100k ;
9. run ~500k ;
10. seulement ensuite simulation longue complète.

La relativité, la grande échelle, la propriété numérique, la persistance hybride et les transitions de régime n'ont plus à être redessinées pour commencer cette phase.
