# Audit cible du modèle conceptuel — relativité, hiérarchie et grande échelle

## Périmètre

Cet audit porte uniquement sur `universe_simulation/` et sur le sous-projet `universe_sim`. Il ne concerne pas l'application Django ou les autres parties du dépôt Makolo.

Objectif : préparer le moteur conceptuel actuel à trois extensions majeures sans casser le vocabulaire physique existant :

1. dynamique relativiste des véhicules lorsque `v` devient une fraction significative de `c` ;
2. simulation hiérarchique de très grands ensembles (galaxies, systèmes, corps, véhicules) ;
3. intégration multi-échelle en espace et en temps.

Le modèle reste un laboratoire conceptuel. Il n'a pas vocation à devenir une reconstitution exhaustive de l'Univers réel.

---

# 1. Verdict général

Le modèle conceptuel est sain et doit être conservé.

Les séparations suivantes sont bonnes :

- entités physiques (`CorpsPhysique`, `Etoile`, `Planete`, `Vehicule`, `TrouNoir`, etc.) ;
- état physique séparé de l'entité ;
- systèmes séparés des corps ;
- interactions, lois et effets séparés ;
- calculs dérivés externes ;
- moteur de simulation séparé du modèle conceptuel ;
- relativité explicitement séparée du moteur classique ;
- visualisation séparée de la dynamique ;
- persistance séparée de la physique.

Le changement principal ne doit donc pas être une réécriture des classes physiques. Il doit porter sur la couche de dynamique, l'organisation hiérarchique, les backends numériques et la gestion des régimes physiques.

---

# 2. À conserver presque tel quel

## `values.py`

À conserver :

- `GrandeurPhysique` ;
- `Vecteur3` ;
- `Quaternion` ;
- `Instant` ;
- `Duree`.

Évolutions : ajouter des types relativistes (`Quadrivecteur`, `Quadrivitesse`, `Quadrimpulsion` ou objets équivalents) sans remplacer `Vecteur3`.

## `bodies.py`

À conserver : la hiérarchie des corps naturels et artificiels.

`CorpsPhysique` doit rester l'entité métier et ne doit pas devenir un tableau numérique.

Évolutions nécessaires :

- retirer la responsabilité de stockage massif de trajectoire de `historique` pour les grands runs ;
- enrichir `Vehicule` par des composants physiques séparés : masse sèche, propergol, système propulsif, orientation de poussée, limites physiques ;
- ne pas faire du véhicule lui-même un contrôleur de trajectoire.

## `derived.py`

À conserver :

- `Trajectoire` ;
- `Orbite` ;
- `Barycentre` ;
- points de Lagrange ;
- sphère de Hill ;
- sphère d'influence ;
- lobe de Roche.

Ces concepts pourront devenir importants pour le moteur hiérarchique, mais restent des structures physiques/dérivées, pas des solveurs numériques.

## `services/astrodynamics.py`

À conserver comme référence classique : éléments orbitaux, Lambert, périodes, sphères d'influence, etc.

Ces services sont valides dans leur domaine classique et ne doivent pas être remplacés par la relativité. Le domaine de validité devra simplement être explicité dans les API.

## `fields.py`

Bonne séparation entre champs, potentiels, rayonnement, atmosphère et distributions de matière.

À étendre plus tard avec des potentiels galactiques analytiques et des champs agrégés de systèmes.

---

# 3. À généraliser sans casser l'API conceptuelle

## `states.py`

### Situation actuelle

`EtatTranslationnel` contient :

- position ;
- vitesse.

`DeriveeEtat` suppose ensuite :

- `d_position` ;
- `d_vitesse`.

Cette représentation est parfaite pour le régime classique, mais devient insuffisante à vitesse relativiste.

### Cible

Conserver `EtatTranslationnel` comme état classique et ajouter un état relativiste parallèle, par exemple :

```text
EtatCinematiqueRelativiste
    position
    quantite_mouvement
    energie
    temps_propre
    gamma
```

La vitesse pourra être dérivée de la quadrimpulsion ou de la quantité de mouvement relativiste, afin que `|v| < c` soit une conséquence de la formulation et non un simple clamp numérique.

`EtatPhysique` devra pouvoir contenir un composant cinématique classique ou relativiste selon le régime choisi.

## `spacetime.py`

### Bon

- distinction modèle classique / relativiste ;
- époque de référence non cosmologique ;
- origine du référentiel non absolue ;
- référentiels et systèmes de coordonnées explicites.

### Limite

Le `Referentiel` actuel encode translation, rotation, vitesse et vitesse angulaire selon une cinématique galiléenne.

Il ne faut pas essayer de lui ajouter quelques formules de Lorentz. Il faut conserver ce référentiel pour le régime classique et introduire un référentiel/carte relativiste avec transformations de Lorentz distinctes.

`ModeleEspaceTempsRelativiste.intervalle()` doit être considéré comme une évaluation locale via métrique et non comme une distance géodésique générale entre événements d'un espace-temps courbe.

## `systems.py`

### Bon

La séparation `CorpsPhysique` / `SystemePhysique` est fondamentale et doit rester.

La présence de :

- `SystemeStellaire` ;
- `SystemePlanetaire` ;
- `AmasStellaire` ;
- `Galaxie` ;
- `GroupeGalaxies` ;
- `AmasGalaxies` ;

est exactement ce dont le moteur hiérarchique aura besoin.

### Limite

Aujourd'hui, `Univers` possède en parallèle une liste plate de tous les corps et une liste de tous les systèmes. Cela devient coûteux pour des centaines de milliers ou millions d'entités.

### Cible

Ajouter une couche de registre/index :

```text
RegistreUnivers
    corps_par_id
    systemes_par_id
    parent_par_id
    membres_materialises
```

et un état calculatoire de système contenant au moins :

- masse agrégée ;
- barycentre ;
- vitesse barycentrique ;
- rayon de couverture ;
- multipôles disponibles ;
- niveau d'activité ;
- référentiel local.

Les listes métier peuvent rester pour les petits modèles, mais le backend grande échelle ne doit pas dépendre d'une itération Python sur toute la hiérarchie à chaque pas.

---

# 4. À refondre dans la couche numérique

## `simulation/engine.py`

C'est la principale limite actuelle.

Aujourd'hui :

```text
Force -> F / m -> d_vitesse
```

Cette transformation est explicitement newtonienne.

### Cible

Le moteur doit déléguer la conversion des effets en dérivées à un `RegimeDynamique` :

```text
REGIME CLASSIQUE
    Force -> accélération

REGIME RELATIVISTE SPECIAL
    Force / poussée -> dérivée de quantité de mouvement

REGIME GEODESIQUE
    métrique -> équations géodésiques

REGIME ANALYTIQUE
    éléments orbitaux -> état(t)
```

Le moteur général orchestre ; il ne doit plus connaître lui-même `F = ma` comme unique dynamique.

## `laws/gravity.py`

### À conserver

- gravitation newtonienne directe comme solveur de référence ;
- J2 pour les champs locaux ;
- principe de modèles distincts par fidélité.

### À remplacer pour grande échelle

`ModeleGravitationPonctuelle` parcourt toutes les paires : `O(N²)`.

Créer une interface de solveur gravitationnel :

```text
SolveurGravite
    DirectNBody
    BarnesHut
    PotentielAnalytique
    AgregatHierarchique
    (plus tard FMM)
```

Le nom actuel `ModeleMultipolaire` correspond surtout à monopole + J2. Il faudra éviter de le confondre avec le futur vrai traitement multipolaire d'agrégats lointains.

## `simulation/integrators.py`

### À conserver

Euler, RK4 et Velocity-Verlet sont utiles comme intégrateurs classiques et comme références de validation.

### Limites

- copie complète d'objets Python à chaque sous-étape RK4 ;
- dictionnaires d'états par corps ;
- un seul format de dérivée ;
- aucune relativité ;
- aucun pas adaptatif ou multi-taux.

### Cible

Séparer :

```text
IntegrateurClassique
IntegrateurRelativiste
IntegrateurGeodesique
PropagateurAnalytique
```

et permettre des backends contigus NumPy/SoA pour les grandes populations.

## `simulation/simulation.py`

### Limite

Un appel `avancer(dt)` fait évoluer tout l'univers avec le même pas.

### Cible

Conserver une horloge de temps coordonnée commune, mais introduire un ordonnanceur multi-taux :

```text
HorlogeSimulation
    temps coordonné global

OrdonnanceurTemporel
    groupe local : dt secondes/minutes
    planète : dt heures/jours
    interstellaire : dt jours/années
    galactique : dt siècles/millénaires
```

Tous les objets restent sur une même ligne temporelle coordonnée. Le multi-taux signifie fréquence d'intégration différente, pas plusieurs univers ayant chacun leur temps physique indépendant.

## `simulation/managers.py`

`GestionnaireInteractions.paires()` utilise `itertools.combinations` : correct pour référence, non scalable.

Cible : index spatial / arbre hiérarchique / voisinage local.

`GestionnaireEvenements` doit évoluer vers :

- broad phase ;
- détection continue ;
- localisation d'événement entre deux pas ;
- gestion hiérarchique des événements.

---

# 5. Relativité : ce qui existe et ce qui manque

## `relativity.py`

Très bon choix existant : `ModeleGravitationRelativiste.evaluer()` refuse explicitement de passer par le moteur de forces classique et réclame un intégrateur de géodésiques.

À conserver absolument.

### Manques

- transformations de Lorentz ;
- quadrivecteurs ;
- quadrivitesse / quadrimpulsion ;
- temps propre accumulé ;
- addition relativiste des vitesses ;
- accélération propre ;
- intégrateur relativiste spécial ;
- intégrateur de géodésiques ;
- cartes de coordonnées / référentiel associé aux événements ;
- Kerr pour trou noir en rotation (plus tard).

## `services/geometry.py`

À conserver comme géométrie **classique**.

Les transformations actuelles incluent translation, rotation, vitesse d'origine et termes de rotation. Elles ne sont pas des transformations de Lorentz.

Créer un service séparé :

```text
services/relativistic_geometry.py
```

avec transformations de Lorentz et conversions entre quatre-vecteurs.

---

# 6. Propulsion

## Situation actuelle

`ModelePropulsion` reçoit des fonctions prescrites :

- poussée vectorielle ;
- débit massique.

C'est suffisant pour les démonstrations actuelles.

## Cible

Créer des concepts physiques explicites :

```text
SystemePropulsif
    poussee_max
    impulsion_specifique
    puissance
    masse_seche

EtatPropulsif
    masse_propergol
    moteur_actif
    orientation_poussee

ProfilPoussee
    segments de mission / commande
```

Pour régime classique : poussée -> force.

Pour régime relativiste : la commande doit idéalement pouvoir être exprimée en accélération propre / poussée dans le référentiel instantané du véhicule et agir sur la quadrimpulsion.

---

# 7. Événements à ajouter

Le modèle actuel gère collision, impact, fusion, fragmentation, séparation, capture gravitationnelle, éjection, transit, occultation, éclipse.

Ajouter :

```text
ENTREE_SPHERE_INFLUENCE
SORTIE_SPHERE_INFLUENCE
ENTREE_SYSTEME
SORTIE_SYSTEME
ENTREE_GALAXIE
SORTIE_GALAXIE
CHANGEMENT_REGIME_DYNAMIQUE
EPUISEMENT_PROPERGOL
ALLUMAGE_MOTEUR
COUPURE_MOTEUR
FRANCHISSEMENT_HORIZON
EFFONDREMENT_STELLAIRE
FORMATION_RESIDU_COMPACT
DESTRUCTION
MATERIALISATION_LOD
DEMATERIALISATION_LOD
```

Les deux derniers sont des événements de simulation/LOD, pas des phénomènes physiques ; ils doivent donc être séparés des événements physiques dans la couche technique.

---

# 8. Backend grande échelle

Le modèle métier peut garder ses dataclasses Python. En revanche, le calcul sur un million d'entités doit utiliser une représentation contiguë de type Structure of Arrays :

```text
positions[N, 3]
velocities[N, 3]
momenta[N, 3]
masses[N]
charges[N]
active[N]
regime[N]
level_of_detail[N]
parent_system[N]
```

Créer une couche :

```text
StateBackend
    ObjectBackend       # petit nombre de corps, tests, lisibilité
    ArrayBackend        # NumPy, grande échelle
```

Les objets physiques restent les identités et métadonnées ; le backend stocke les états chauds utilisés dans les boucles numériques.

---

# 9. Niveaux d'activité / LOD physique

Ajouter une classification calculatoire distincte du type physique :

```text
ACTIVE
ANALYTIC
AGGREGATED
TRACER
VISUAL_ONLY
```

Exemple :

- un système stellaire très éloigné est un agrégat ;
- lorsque le vaisseau s'approche, le système est ouvert ;
- les étoiles et planètes pertinentes deviennent actives ;
- les corps mineurs peuvent rester analytiques ou tracers ;
- en quittant le système, celui-ci peut être réagrégé.

Cette transition ne change pas ce que l'objet *est* physiquement. Elle change seulement la fidélité avec laquelle le simulateur le calcule.

---

# 10. Persistance

La persistance actuelle est bonne pour les petits runs et doit rester disponible.

Pour grande échelle :

- ne plus sauvegarder l'historique dans chaque `CorpsPhysique` ;
- éviter CSV pour tous les états ;
- préférer stockage chunké/binaire ;
- conserver CSV/JSON pour catalogues, résumés et événements humains.

Cible indicative :

```text
simulation_outputs/run/
    metadata.json
    manifest.json
    catalogue/
        galaxies.parquet
        systems.parquet
        bodies.parquet
        vehicles.parquet
    states/
        chunks/
        important_tracks/
    events/
        physical_events.parquet
        simulation_events.parquet
    images/
    videos/
    interactive/
```

La possibilité de rejouer une exécution à partir d'un `seed`, d'une configuration et d'un manifeste doit devenir un invariant.

---

# 11. Visualisation

La frontière `capturer_sequence() -> SequenceVisuelle -> renderer` est bonne et doit être conservée.

Mais une frame contenant un dictionnaire de toutes les positions ne passe pas à un million d'entités.

Créer :

```text
VisualQuery
    centre
    echelle
    filtres
    budget_objets
    niveaux_LOD

VisualFrame
    agrégats
    corps détaillés
    tracers échantillonnés
    trajectoires importantes
```

Les renderers ne doivent toujours jamais modifier la physique.

---

# 12. Diagnostics

Les diagnostics actuels d'énergie, quantité de mouvement et moment cinétique sont classiques et calculent notamment l'énergie potentielle par paires.

Ils doivent rester comme référence pour petits systèmes.

Ajouter :

- diagnostics par régime ;
- énergie/impulsion relativiste ;
- contrôle `v < c` ;
- erreur Barnes-Hut vs direct N-body sur échantillon ;
- erreur de pas multi-taux ;
- comptage des événements manqués/interpolés ;
- conservation locale et globale lorsqu'elle est physiquement pertinente.

---

# 13. Tests obligatoires avant méga-simulation

## Classique

- orbite deux-corps ;
- barycentre ;
- action-réaction ;
- énergie / quantité de mouvement ;
- J2 ;
- collision continue entre deux pas ;
- comparaison DirectNBody / Barnes-Hut.

## Relativité spéciale

- `v < c` pour toute poussée ;
- facteur de Lorentz ;
- dilatation du temps ;
- composition relativiste de vitesses ;
- impulsion relativiste ;
- accélération propre constante ;
- aller-retour accélération/coasting/décélération.

## Champ fort

- rayon de Schwarzschild ;
- redshift ;
- géodésiques tests connues ;
- horizon : aucune trajectoire extérieure ne réapparaît après franchissement dans le modèle choisi ;
- séparation claire Schwarzschild / Kerr.

## Grande échelle

Benchmark progressif :

```text
1 000
10 000
100 000
500 000
1 000 000
```

Mesurer : temps/pas, RAM, erreur gravitationnelle, coût persistance, coût visualisation.

---

# 14. Architecture cible

```text
MODELE CONCEPTUEL
Univers / Galaxies / Systemes / Corps / Vehicules
                    |
                    v
ETATS PHYSIQUES
classiques + relativistes + etats de systemes
                    |
                    v
RESOLUTION DU REGIME
classique / SR / geodesique / analytique
                    |
                    v
RESOLUTION SPATIALE
corps actif / systeme agrege / potentiel galactique
                    |
                    v
SOLVEURS
Direct N-body / Barnes-Hut / analytique / geodesique
                    |
                    v
ORDONNANCEUR MULTI-TAUX
                    |
                    v
EVENEMENTS
                    |
                    v
STATE BACKEND
ObjectBackend / ArrayBackend
                    |
                    v
PERSISTANCE + VISUALISATION LOD
```

---

# 15. Ordre de migration recommandé

Chaque étape doit rester testable et idéalement correspondre à un commit autonome.

## Commit 1 — types de régime et contrats

Ajouter sans changer le comportement actuel :

- `RegimeDynamique` ;
- interfaces de dynamique ;
- types de backend ;
- types de niveau d'activité ;
- nouveaux événements nécessaires.

Tous les objets existants restent en régime classique par défaut.

## Commit 2 — cinématique relativiste spéciale

Ajouter :

- quadrivecteurs / impulsion relativiste ;
- facteur gamma ;
- temps propre ;
- transformations de Lorentz ;
- tests analytiques.

Aucune gravitation GR à ce stade.

## Commit 3 — moteur multi-régime

Refactorer `MoteurPhysique` afin qu'il ne suppose plus universellement `a = F/m`.

Le régime classique doit reproduire les résultats actuels.

## Commit 4 — propulsion relativiste

- état propulsif ;
- masse sèche ;
- propergol ;
- accélération propre / poussée ;
- consommation ;
- tests `v<c`.

## Commit 5 — backend numérique vectorisé

Créer `ObjectBackend` puis `ArrayBackend` NumPy.

Comparer les deux sur les mêmes petits systèmes.

## Commit 6 — solveur gravitationnel abstrait

Extraire `DirectNBody` puis ajouter Barnes-Hut.

Validation systématique Barnes-Hut vs direct sur petits N.

## Commit 7 — hiérarchie calculatoire

Ajouter états agrégés des systèmes, rayon de couverture, barycentres, multipôles et niveaux d'activité.

## Commit 8 — ordonnanceur multi-taux

Conserver un temps coordonné global, mais permettre plusieurs fréquences d'intégration synchronisées.

## Commit 9 — événements continus et spatiaux

Index spatial, broad phase, détection entre deux pas, entrées/sorties de systèmes et sphères d'influence.

## Commit 10 — champ fort / géodésiques

Construire le vrai chemin séparé pour Schwarzschild puis, plus tard, Kerr.

Ne jamais réinjecter la GR sous forme de simple `Force` newtonienne.

## Commit 11 — persistance grande échelle

Chunks binaires/Parquet ou HDF5/NPZ selon dépendances retenues, manifeste reproductible, trajectoires importantes séparées.

## Commit 12 — visualisation LOD

Requêtes multi-échelle, agrégats, sampling de tracers, sélection dynamique des corps visibles.

## Commit 13 — benchmarks et seuils

Automatiser les benchmarks 1k/10k/100k/... et fixer les seuils réalistes avant le premier run multi-galaxies.

---

# 16. Invariants à ne pas casser

1. `t=0` reste une époque de simulation choisie, jamais l'origine absolue du temps.
2. `(0,0,0)` reste l'origine d'un référentiel choisi, jamais le centre absolu de l'Univers.
3. position/vitesse/impulsion appartiennent à l'état, pas à l'identité intemporelle du corps.
4. un système n'est pas un corps.
5. une orbite reste une relation/structure dérivée.
6. les renderers ne déterminent jamais la dynamique.
7. la persistance n'est pas une propriété physique des corps.
8. le niveau de détail calculatoire n'est pas une classification physique.
9. la relativité générale ne doit pas être convertie artificiellement en `F = ma`.
10. les approximations doivent toujours annoncer leur domaine de validité.

---

# 17. Décision

Le code actuel ne doit pas être jeté.

La stratégie recommandée est une migration incrémentale autour du modèle existant :

```text
conserver le vocabulaire physique
+ ajouter des états/régimes relativistes
+ rendre le moteur polymorphe par régime
+ vectoriser le backend numérique
+ hiérarchiser la gravité et les systèmes
+ synchroniser plusieurs pas de temps
+ persister/visualiser par niveaux de détail
```

La première modification de code à réaliser après cet audit doit être le **Commit 1 : contrats de régimes dynamiques et niveaux d'activité**, sans changer encore les résultats des simulations actuelles.
