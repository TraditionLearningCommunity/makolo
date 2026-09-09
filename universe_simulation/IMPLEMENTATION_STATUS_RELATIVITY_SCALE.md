# État d'implémentation — relativité et grande échelle

Ce document décrit l'état **réellement implémenté** du sous-projet `universe_simulation/` après la migration relativiste et grande échelle. Il ne remplace pas l'audit de migration ; il sert de photographie technique avant la première simulation multi-galaxies.

## 1. Modèle conceptuel conservé

Le vocabulaire physique reste inchangé dans son principe :

- `Univers`, `Galaxie`, `SystemeStellaire`, `SystemePlanetaire` ;
- `Etoile`, `Planete`, `SatelliteNaturel`, `TrouNoir` ;
- `Vehicule`, `SondeSpatiale`, `SatelliteArtificiel`, `DebrisSpatial` ;
- état physique séparé des entités ;
- lois, interactions, effets, intégrateurs, persistance et visualisation séparés.

Les optimisations de calcul ne changent pas ce qu'est un corps physiquement.

## 2. Régimes physiques disponibles

### Classique newtonien

Conservé pour :

- vitesses faibles devant `c` ;
- champ gravitationnel faible ;
- systèmes planétaires, satellites, astéroïdes et populations galactiques lorsque la précision demandée le permet.

Deux chemins existent :

- moteur objet historique ;
- backend vectorisé NumPy pour grandes populations.

### Relativité spéciale

Implémentée avec :

- facteur de Lorentz ;
- quadrivecteurs ;
- quadrivitesse ;
- quadrimpulsion ;
- énergie relativiste ;
- transformations de Lorentz ;
- composition relativiste des vitesses ;
- temps propre ;
- Doppler relativiste ;
- dynamique canonique `dp/dt = F` ;
- accélération propre ;
- population SR vectorisée ;
- propulsion relativiste idéale de type Ackeret avec perte de masse.

La quantité de mouvement est l'état canonique. Une vitesse supérieure ou égale à `c` n'est pas produite par la dynamique. Une protection numérique traite uniquement le cas où `float64` arrondit une vitesse mathématiquement inférieure à `c` à exactement `c`.

### Post-newtonien 1PN

Une dynamique relative deux-corps 1PN et un intégrateur associé sont disponibles pour les régimes où Newton est insuffisant mais où une intégration GR complète n'est pas requise.

### Relativité générale sur métriques prescrites

Implémentée avec :

- interface générique de métrique 4D ;
- Minkowski ;
- Schwarzschild ;
- Schwarzschild en coordonnées Kerr-Schild traversant l'horizon ;
- Kerr ;
- Reissner-Nordström / Kerr-Newman pour trous noirs chargés ;
- FLRW plate à facteur d'échelle prescrit ;
- Christoffel / géométrie différentielle ;
- intégration géodésique RK4 ;
- intégration géodésique adaptative par step-doubling ;
- lignes d'univers forcées pour corps propulsés en espace-temps courbe ;
- géodésiques temporelles et nulles ;
- temps propre ;
- franchissement d'horizon ;
- garde causal empêchant une réémergence numérique de l'intérieur d'un horizon ;
- tétrades locales pour mesures physiques par un observateur.

La GR n'est jamais convertie en fausse force newtonienne `F/m`.

## 3. Ce qui n'est volontairement pas implémenté

Le projet ne résout pas dynamiquement les équations d'Einstein sur une grille. Il ne simule donc pas de façon auto-cohérente :

- fusion de trous noirs avec espace-temps dynamique ;
- génération complète d'ondes gravitationnelles ;
- hydrodynamique relativiste d'un effondrement stellaire ;
- rétroaction de toute la matière simulée sur une métrique GR globale dynamique.

Ces exclusions sont intentionnelles. Les métriques GR actuelles sont prescrites.

## 4. Sélection du régime

Le sélecteur n'utilise pas la taille géométrique de la scène comme critère principal.

Il utilise notamment :

- `beta = v/c` ;
- `beta²` ;
- profondeur réduite du potentiel `|Phi|/c²` ;
- précision relative demandée.

Règle conceptuelle :

```text
v faible + champ faible           -> Newton
corrections faibles mesurables    -> 1PN
v relativiste + gravité négligeable -> SR
v relativiste + courbure pertinente -> GR
champ fort                         -> GR
```

Une galaxie entière peut donc rester newtonienne/agrégée alors qu'un petit véhicule à `0.99c` est SR ou GR selon son environnement gravitationnel.

## 5. États physiques

`EtatPhysique` accepte trois sources cinématiques exclusives :

```text
translation   -> mécanique classique
relativiste   -> espace plat SR, position + impulsion + temps propre
espace_temps  -> GR/FLRW, x^mu + tangente + paramètre affine + temps propre
```

La position et la vitesse sont exposées par une API commune pour la visualisation et la persistance.

Les conversions sont explicites :

- classique -> SR ;
- SR -> classique uniquement sous un garde `beta` ;
- classique/SR -> espace-temps courbe avec métrique/carte explicitement choisie.

La conversion GR -> SR n'est pas automatisée car elle exige un choix d'observateur/tétrade local.

## 6. Calcul grande échelle

### Backend d'état

`ArrayStateBackend` utilise une Structure-of-Arrays NumPy :

```text
positions[N,3]
velocities[N,3]
momenta[N,3]
masses[N]
charges[N]
proper_times[N]
active[N]
regime_codes[N]
```

Il supporte les populations Newton et SR. Les trajectoires GR restent volontairement sur le backend objet/géodésique.

### Gravitation

Trois niveaux sont disponibles :

1. N-body direct vectorisé par blocs — référence exacte `O(N²)` ;
2. Barnes-Hut 3D Python — référence algorithmique `O(N log N)` ;
3. Barnes-Hut 3D Numba — chemin performant optionnel.

L'auto-gravitation d'une particule par un nœud agrégé est explicitement évitée.

### Hiérarchie calculatoire

Un système peut être représenté par :

- masse agrégée ;
- barycentre ;
- vitesse barycentrique ;
- rayon de couverture ;
- quadrupôle ;
- niveau d'activité/LOD.

La hiérarchie calculatoire reste séparée des classes physiques.

## 7. Niveaux de calcul

Les niveaux disponibles sont :

```text
ACTIVE
ANALYTIC
AGGREGATED
TRACER
VISUAL_ONLY
```

Ils décrivent le coût/fidélité de simulation, pas la nature physique du corps.

## 8. Temps multi-taux

Deux couches existent :

- ordonnanceur abstrait de cadences ;
- exécution grande échelle multi-taux avec temps numérique par domaine.

Une barrière globale n'existe que lorsque tous les domaines atteignent le même temps coordonné. Entre barrières, une politique de couplage doit explicitement prédire/interpoler les autres domaines si nécessaire ; aucune simultanéité fictive n'est supposée.

## 9. Événements spatiaux

La détection inclut :

- broad phase par grille spatiale ;
- franchissement continu de sphère entre deux pas ;
- entrée et sortie dans un même grand pas ;
- sphères d'influence / systèmes / galaxies ;
- horizon de trou noir ;
- événements moteur/propergol ;
- séparation des événements physiques et des événements techniques de LOD/régime.

## 10. Persistance

Trois niveaux sont disponibles :

- persistance historique CSV/JSON pour petits runs classiques ;
- persistance multi-régime détaillée ;
- persistance grande échelle en chunks NPZ compressés.

Pour les populations chaudes, les positions et impulsions canoniques sont stockées ; les vitesses de tracers de masse nulle sont stockées explicitement.

La persistance multi-domaines peut sauvegarder séparément par exemple :

```text
domains/
  stellar-population/
  relativistic-ships/
  debris/
```

sans resynchroniser les objets Python à chaque frame.

## 11. Visualisation LOD

La visualisation peut limiter le nombre de corps matérialisés par :

- centre et rayon de vue ;
- budget maximal ;
- IDs prioritaires ;
- masse/importance ;
- échantillonnage déterministe ;
- agrégats de systèmes.

Un système `AGGREGATED` masque ses membres détaillés afin d'éviter de dessiner simultanément l'agrégat et tous ses corps.

## 12. Validation de pipeline

Un test de bout en bout combine actuellement :

- 64 étoiles newtoniennes ;
- 256 véhicules SR ;
- poussée puis rétro-poussée ;
- temps propre des véhicules ;
- 200 s de temps coordonné commun ;
- persistance multi-domaines ;
- aucune synchronisation objet imposée pendant les pas chauds.

Les vitesses SR restent strictement inférieures à `c`.

## 13. Performances mesurées

Les chiffres dépendent de la machine et ne sont pas des garanties universelles.

Barnes-Hut Numba, après compilation :

- `100k` corps : ordre de grandeur ~1 s par évaluation sur les premiers essais ;
- `500k` corps : ~4.5–6 s selon les paramètres/tuning ;
- `1M` corps : non validé dans la fenêtre d'exécution disponible.

Un compromis testé avec `theta ~= 0.8` et feuilles plus larges donne une erreur p95 d'environ quelques pourcents sur le jeu de validation utilisé. La référence exacte reste Direct N-body.

Le benchmark reproductible est dans :

```text
benchmarks/benchmark_scaling.py
BENCHMARK_SCALING.md
```

Le million de corps doit rester annoncé comme **objectif**, pas comme capacité validée, tant qu'un benchmark complet n'a pas réussi.

## 14. État avant simulation multi-galaxies

Le socle est maintenant suffisamment avancé pour préparer une scène multi-galaxies, mais deux mécanismes doivent encore être consolidés avant le gros run :

1. migration dynamique d'un corps entre backend massif et chemin objet/GR lorsqu'un changement de régime ou de LOD est déclenché ;
2. stratégie de couplage inter-domaines à grande distance (agrégats/potentiels) sans appliquer Newton naïvement à un véhicule relativiste.

Ensuite seulement viennent :

- générateur de galaxies/systèmes/planètes/satellites/véhicules ;
- validation progressive 10k -> 100k -> 500k ;
- première simulation multi-galaxies longue durée.

## 15. Règles à ne pas casser

1. Newton reste disponible et n'est pas remplacé par la relativité.
2. La relativité est choisie par le régime physique, pas par la taille de la scène.
3. `t=0` est une époque choisie, jamais le début absolu du temps.
4. `(0,0,0)` est une origine de référentiel, jamais le centre absolu de l'Univers.
5. Une position/vitesse/impulsion appartient à l'état, pas à l'identité intemporelle du corps.
6. Un niveau LOD n'est pas une propriété physique.
7. Une métrique GR prescrite n'est pas un espace-temps auto-cohérent résolu par Einstein.
8. Une fusée accélérée en GR suit une ligne d'univers forcée, pas une géodésique.
9. Un objet ayant franchi un horizon ne doit pas réémerger par artefact numérique.
10. Toute approximation doit conserver un domaine de validité explicite.
