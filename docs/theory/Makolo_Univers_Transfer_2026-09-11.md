# Makolo — Dossier de transfert de la modélisation de l'Univers Makolo

**Date de consolidation : 2026-09-11**  
**Projet : Makolo**  
**Dépôt officiel : `TraditionLearningCommunity/makolo`**  
**Branche principale : `main`**

---

# 0. Objet de ce document

Ce document sert à transférer l'état complet du travail conceptuel sur **l'Univers Makolo** vers une nouvelle conversation ChatGPT sans recommencer l'analyse depuis zéro.

Il doit être lu comme un **dossier de continuité intellectuelle**, pas comme une spécification logicielle finale.

Le travail en cours n'est **pas** :
- un exercice de physique pour le plaisir ;
- un TP de transposition ;
- une tentative de faire correspondre chaque table Django à un objet physique ;
- une conception prématurée d'algorithmes ;
- une réécriture de Makolo pour coller à la physique.

Le travail en cours est :

> **concevoir un Univers Makolo cohérent, objectif et dynamique, inspiré et contraint par les sciences physiques établies, afin que des algorithmes exploitables puissent être découverts ensuite comme conséquence de cette structure.**

La séquence de travail actuelle est donc :

\[
\boxed{
Univers \rightarrow objets \rightarrow états \rightarrow relations \rightarrow lois \rightarrow dynamique
}
\]

et **seulement après** :

\[
\boxed{
dynamique \rightarrow algorithmes
}
\]

---

# 1. Finalité produit à ne jamais perdre

Makolo vient du lingala et signifie **« les pieds »**.

Makolo doit **marcher pour l'utilisateur**.

Promesse produit :

> **« Makolo marche pour vous. »**

Formulation d'expérience :

> **« Avance, tout est déjà prêt. »**

Le problème que Makolo cherche à résoudre n'est pas le manque d'information.

Le monde contient déjà :
- des bourses ;
- des emplois ;
- des événements ;
- des transports ;
- des services ;
- des financements ;
- des formations ;
- des activités culturelles ;
- des démarches ;
- des publications ;
- des opportunités multiples.

Le problème est plutôt :

> **une personne ne sait pas toujours quelle action est pertinente maintenant, ce qui devient urgent, ce qui peut être préparé avant d'en avoir besoin, ou quelles possibilités se combinent entre elles.**

Exemple central : Typhon vient de finir son bachelier.

Il peut avoir simultanément dans son univers :
- une bourse future aux États-Unis ;
- une formation d'anglais en ligne ;
- une PME locale qui cherche un développeur pour trois mois ;
- un passeport à obtenir ;
- un visa à préparer plus tard ;
- plusieurs autres possibilités.

Un moteur classique peut dire :
> « cette bourse correspond à ton profil ».

Makolo doit pouvoir finir par produire quelque chose de plus structurel :
> « la bourse est future ; l'anglais et le passeport sont préparables maintenant ; le travail local est compatible avec la période ; certaines actions ouvrent plusieurs possibilités futures. »

**Mais cette conséquence algorithmique n'est pas encore l'étape courante.**

Nous construisons d'abord l'Univers qui permettra plus tard de découvrir ce type d'algorithmes.

---

# 2. Règles du projet Makolo

## 2.1 Dépôt et vérité courante

Dépôt unique :

`TraditionLearningCommunity/makolo`

Branche principale :

`main`

Ne jamais supposer qu'une ancienne PR, branche, roadmap ou SHA est encore actuelle.

Avant toute modification importante :
- vérifier HEAD de `main` ;
- vérifier commits récents ;
- PR/branches pertinentes ;
- CI ;
- migrations ;
- docs touchées.

Sources de vérité, par priorité :

1. code, migrations et tests actuels ;
2. `docs/architecture/makolo-domain-blueprint.md` ;
3. docs canoniques pertinentes :
   - `mature-program-roadmap.md`
   - `strategic-action-roadmap.md`
   - `profile-relevance-action-network.md`
   - `mature-experience-principles.md`
   - docs du domaine concerné ;
4. `docs/operations-runbook.md` ;
5. GitHub courant ;
6. historique/transferts comme contexte.

Le runtime courant gagne sur l'historique.

---

# 3. Vision canonique Makolo

Makolo est un **réseau d'action**.

Il doit :
- découvrir des possibilités réelles ;
- préparer ce qui peut l'être ;
- orchestrer ce qui reste à faire ;
- accompagner l'action réelle ;
- capitaliser ce qui facilitera la suite.

Principe :

> **backend générique, métier contextuel.**

Les abstractions canoniques parlent de :
- Activity ;
- Occurrence ;
- Journey / Démarche ;
- Access ;
- Requirement ;
- Proof ;
- etc.

L'interface utilise le vocabulaire naturel du contexte :
- événement ;
- départ ;
- candidature ;
- service ;
- financement ;
- etc.

Makolo ne doit pas devenir :
- un réseau social générique ;
- un feed infini ;
- un job board générique ;
- un task manager ;
- une plateforme optimisée pour le watch time.

Principe d'expérience :

> **« Pas le plaisir de rester. Le plaisir d'avancer. »**

---

# 4. Invariants canoniques à protéger

Ces invariants ne doivent jamais être violés pour faire tenir une analogie physique.

- Un **Profile** est une personne globale ; jamais un participant ou organisateur global.
- **Assignment = responsabilité.**
- **Mandate / Permission = autorité.**
- Membership / Group / Team n'accorde pas automatiquement d'autorité.
- **Readiness** est une projection dérivée, pas un état générique à dupliquer.
- Requirement, Form, Resource, JourneyArtifact, Proof, Credential Trust et AccessCredential sont distincts.
- **Access = droit.**
- **AccessCredential = représentation / secret.**
- **AccessUse = observation de l'usage/passage.**
- **Capacity = combien ?**
- **Placement = où ?**
- Waitlist != Live Queue.
- JourneyStep != checkpoint opérationnel.
- Dossier = objectif actif composé.
- Project = horizon durable.
- Aucun ne devient task manager générique.
- Posséder un document != le retrouver != satisfaire un Requirement.
- Une composition ne transfère jamais implicitement Permission, Mandate, Access, Payment ni accès à des données privées.
- Les projections publiques/collectives appliquent la divulgation minimale.
- Presentation représente les faits ; elle ne les possède pas.
- Pas de contenu ou média orphelin.

---

# 5. Statuts formels autorisés

Utiliser **uniquement** les quatre statuts suivants :

- **RETENU**
- **CANDIDAT**
- **À DÉTERMINER**
- **SANS ÉQUIVALENT**

Ne pas inventer :
- CANDIDAT FORT ;
- GELÉ ;
- REJETÉ ;
- etc.

Les nuances peuvent être exprimées en prose, mais le champ de statut reste l'un de ces quatre.

---

# 6. Source physique V2.3 et position actuelle

Un document de travail physique antérieur existe :

**`Modele_Univers_Dynamique_V2_3_Detaille.docx`**

Il représente l'état auquel la modélisation physique personnelle s'était arrêtée.

Point fondamental désormais **RETENU** :

> **V2.3 n'est pas la perfection ni la limite scientifique.**

Il y a eu des versions antérieures et il aurait pu y avoir V2.4, V3, V4, etc.

Donc :

\[
\boxed{
Sciences\ physiques\ établies > V2.3
}
\]

comme référence scientifique.

V2.3 reste utile comme :
- contexte ;
- vocabulaire ;
- historique de modélisation ;
- noyau déjà réfléchi.

Mais si mécanique analytique, relativité, cosmologie, électromagnétisme, théorie des systèmes ou autre physique établie apportent une structure absente de V2.3, on peut l'utiliser.

---

# 7. Doctrine de transposition physique

**RETENU**

> **Une loi physique n'est transposée à Makolo que si chacune des grandeurs et opérations qu'elle relie possède un équivalent Makolo fonctionnellement justifié. La forme de la loi n'est alors pas réinventée : elle est conservée. Si un terme n'a pas d'équivalent légitime, la transposition reste À DÉTERMINER ou SANS ÉQUIVALENT.**

Et :

> **Nous ne créons pas de nouvelles « lois Makolo » pour combler les trous de la transposition.**

Les constantes physiques restent physiques.

Si une loi utilise :
- \(G\) ;
- \(c\) ;
- \(\hbar\) ;

on n'invente pas `G_Makolo` ou `c_Makolo`.

Si les unités et dimensions ne sont pas compatibles, la transposition échoue.

---

# 8. L'Univers Makolo n'est pas la BDD

C'est un acquis central.

\[
\boxed{
BDD\ Makolo \neq Univers\ Makolo
}
\]

Les objets de la BDD :
- donnent des faits ;
- décrivent des relations ;
- enregistrent des événements ;
- servent de sources d'observation.

Ils ne sont pas automatiquement :
- des corps ;
- des énergies ;
- des masses ;
- des coordonnées ;
- des charges ;
- des champs.

Une grandeur physique Makolo peut être **dérivée** de plusieurs faits sans être persistée.

Par exemple, conceptuellement :

\[
M=\mathcal M[X]
\]

\[
E=\mathcal E[X]
\]

\[
P^\mu=\mathcal P^\mu[X]
\]

Une future énergie Makolo pourrait être un résultat calculé à partir de l'état global, même si aucun champ `energy` n'existe.

**RETENU**

---

# 9. Objets de base déjà acquis

On ne doit pas recommencer à zéro à chaque tour.

Les correspondances de travail déjà acquises sont :

## 9.1 Activity ↔ SystemePhysique

\[
\boxed{
Activity \leftrightarrow SystemePhysique
}
\]

**CANDIDAT / base de travail déjà stabilisée**

L'Activity est l'**ancre** du système considéré.

Mais attention :

\[
\boxed{
Systeme(Activity)
\neq
\{\text{seulement les Occurrences dont activity\_id = Activity}\}
}
\]

**RETENU**

---

## 9.2 Occurrence ↔ Corps / Planète

\[
\boxed{
Occurrence \leftrightarrow CorpsPhysique
}
\]

et, dans le modèle cosmique de travail :

\[
\boxed{
Occurrence \leftrightarrow Planete
}
\]

**CANDIDAT / acquis de travail**

La tension cycle de vie / nature exacte reste à garder à l'esprit, mais on ne rouvre pas sans raison.

---

## 9.3 Profile ↔ Véhicule

\[
\boxed{
Profile \leftrightarrow Vehicule
}
\]

**CANDIDAT / acquis de travail**

Un Profile est une personne globale ; son rôle de participant, organisateur, etc. reste contextuel.

---

# 10. Système ≠ conteneur applicatif

Acquis important issu de l'exemple Coupe du Monde.

Une Occurrence provenant d'une autre Activity peut appartenir au système étudié.

Exemple :

```text
Coupe du Monde
├── matchs
├── vols
├── transports locaux
├── hébergements
├── services
├── rendez-vous administratifs
├── fan zones
└── autres occurrences dynamiquement pertinentes
```

Un vol peut appartenir à une Activity Transport différente, mais être inclus dans le système Coupe du Monde selon le modèle étudié.

Donc :

\[
Activity(O)\neq A
\]

n'interdit pas :

\[
O\in S_A
\]

**RETENU**

---

# 11. Frontière des systèmes

La frontière :

\[
\partial S
\]

ne correspond pas aux ForeignKeys.

Elle dépend :
- du modèle physique ;
- du niveau de description ;
- de l'intervalle étudié ;
- de ce qu'on considère comme interne/externe.

Notation utile :

\[
\boxed{
S_A^{(M)}(t)
}
\]

système ancré sur Activity \(A\), considéré sous modèle \(M\), à l'instant \(t\).

**RETENU** :
- appartenance au système != ownership applicatif ;
- frontière du système dépend du modèle/niveau d'étude.

**CANDIDAT** :
- une même Occurrence peut appartenir à plusieurs systèmes considérés.

---

# 12. Identité, composition et état

Pour tout système \(S\), distinguer :

\[
Id(S)
\]

son identité ;

\[
\mathcal B_S(t)
\]

ses corps/membres ;

\[
X_S(t)
\]

son état.

On peut avoir :

\[
Id(S,t_1)=Id(S,t_2)
\]

mais :

\[
\mathcal B_S(t_1)\neq\mathcal B_S(t_2)
\]

et :

\[
X_S(t_1)\neq X_S(t_2)
\]

**RETENU**

De plus :

\[
\boxed{
Etat(Systeme)\neq somme\ simple\ des\ Etats(Occurrences)
}
\]

Le système peut posséder :
- propriétés collectives ;
- relations ;
- champs ;
- flux ;
- contraintes ;
- configuration ;
- grandeurs dérivées.

---

# 13. EtatGlobalMakolo

Il faut un état global :

\[
\boxed{
X_M(t)
}
\]

distinct de la liste des objets.

Deux univers peuvent contenir les mêmes corps mais être dans des états différents :

\[
\mathcal B(t_1)=\mathcal B(t_2)
\]

et :

\[
X_M(t_1)\neq X_M(t_2)
\]

**RETENU**

Exemple historique :
- même bourse ;
- mêmes 30 Profiles ;
- à \(t_0\), 0 candidature finalisée ;
- à \(t_1\), 27 finalisées.

La composition corporelle peut être identique mais l'état global différent.

---

# 14. Etat complet

Définition de travail :

> **Un état Makolo est complet pour un modèle donné s'il contient suffisamment d'information présente pour déterminer l'évolution future selon les lois et influences futures, sans devoir relire arbitrairement toute l'histoire.**

Formellement :

\[
X(t)+\mathcal L+\text{influences futures}
\Rightarrow X(t+\Delta t)
\]

**RETENU**

Cela implique :

\[
\boxed{
EtatGlobalMakolo \neq toute\ la\ base\ de\ données
}
\]

Certaines données peuvent être :
- historiques ;
- descriptives ;
- éditoriales ;
- de présentation ;
- de provenance ;
- d'observation.

---

# 15. Réalité physique ≠ représentation

Changer un libellé ne change pas forcément l'Univers.

Exemple :
- `Bus 12`
- devient `Express Kolwezi`

sans autre changement.

Alors :

\[
X_M'=X_M
\]

peut rester vrai.

Changer l'heure de départ ou une contrainte peut donner :

\[
X_M'\neq X_M
\]

Donc :

\[
\boxed{
modification\ BDD \not\Rightarrow modification\ physique
}
\]

**RETENU**

---

# 16. Observation ≠ réalité

Un même Univers peut être présenté différemment à plusieurs observateurs sans devenir plusieurs univers.

Conceptuellement :

\[
\mathcal X
\]

état réel,

et :

\[
\mathcal O(V,\mathcal X)
\]

observation/projection pour un observateur \(V\).

Discovery et Presentation peuvent vivre dans cette couche.

**CANDIDAT** :

\[
Discovery \leftrightarrow couche\ observationnelle/projection
\]

À ne pas confondre avec une force physique.

---

# 17. Position

Acquis très important :

\[
\boxed{
Position \neq Etat
}
\]

\[
\boxed{
Position \neq Configuration
}
\]

\[
\boxed{
Position \neq Readiness
}
\]

\[
\boxed{
changement\ d'état \neq mouvement
}
\]

**RETENU**

La position doit rester une notion géométrique :
- référentiel ;
- coordonnées ;
- déplacement ;
- vitesse.

La géographie reste le candidat le plus solide pour une composante positionnelle réelle.

La structure exacte de `PositionMakolo` reste :

**À DÉTERMINER**

---

# 18. Position réelle et position connue

Pour un véhicule \(V\) :

\[
x_V(t)
\]

peut désigner sa position réelle conceptuelle.

Makolo peut seulement connaître :

\[
\hat{x}_V(t)
\]

via :
- localisation autorisée ;
- ville déclarée ;
- résidence ;
- lieu prévu ;
- autres observations.

Donc :

\[
\boxed{
PositionConnueParMakolo\neq PositionPhysiqueExacte
}
\]

**RETENU**

`EtatEstiméMakolo` :

**CANDIDAT**

---

# 19. Espace physique et virtuel

Chaque Occurrence possède au minimum un **lieu**, physique ou virtuel.

Mais cela ne veut pas dire que physique et virtuel appartiennent déjà à une seule métrique.

Exemple :

- utilisateur au Pérou ;
- formateur en Chine ;
- formation en ligne.

La distance géographique reste grande.

On ne doit pas écrire artificiellement :

\[
d_{geo}\approx0
\]

La bonne conclusion est plutôt :

> l'interaction concernée ne demande pas nécessairement une colocalisation physique.

Donc :

\[
\boxed{
distance\ géographique\ grande
\not\Rightarrow
interaction\ impossible
}
\]

**RETENU**

Pour un concert physique, la colocalisation peut être nécessaire.

Pour une formation en ligne, un canal/connectivité peut suffire.

La géométrie exacte du lieu virtuel reste :

**À DÉTERMINER**

Hypothèses ouvertes :
- autre espace ;
- couche de connectivité ;
- graphe ;
- relation ;
- autre structure.

---

# 20. Temps

Le temps est l'une des dimensions les plus nettes.

Une Occurrence possède au minimum une temporalité :
- instant ;
- intervalle ;
- fenêtre ;
- deadline.

Exemples :
- bus à 13h ;
- concert à 20h ;
- deadline le 20 mars ;
- formation mardi 18h–20h.

**RETENU**

\[
\boxed{
temps\ de\ l'Univers \neq timestamps\ de\ persistence
}
\]

`created_at` et `updated_at` ne sont pas le temps physique/opérationnel.

Un événement peut exister dans le monde avant que Makolo le découvre.

---

# 21. « Où ? Quand ? Sous quelles conditions ? »

Intuition récente importante.

Toute possibilité semble pouvoir être analysée selon trois grandes familles :

\[
\boxed{\text{Où ?}}
\]

\[
\boxed{\text{Quand ?}}
\]

\[
\boxed{\text{Sous quelles conditions ?}}
\]

Mais ne pas conclure trop vite à trois coordonnées scalaires.

**CANDIDAT** comme **trois familles fondamentales d'observation/situation**.

Interprétation actuelle :

- **où** → espace/support/géométrie ;
- **quand** → temps ;
- **conditions/aléas** → état + relations + champs + contraintes + événements + perturbations.

---

# 22. Les aléas

Ne pas modéliser `AléaMakolo` comme un scalaire universel sans preuve.

Exemples d'« aléas » :
- panne du bus ;
- pluie ;
- embouteillage ;
- route coupée ;
- bus complet ;
- chauffeur absent ;
- ticket invalide ;
- retard ;
- changement de Requirement.

Ils relèvent de catégories physiques différentes :
- état interne ;
- environnement/champ ;
- contrainte ;
- composition ;
- relation ;
- événement ;
- processus stochastique.

Donc :

`AleaMakolo` comme troisième coordonnée universelle :

**À DÉTERMINER**

Aléas comme famille de perturbations/conditions :

**CANDIDAT**

---

# 23. Relations

Une relation peut changer alors que l'état intrinsèque d'un véhicule reste identique.

\[
R(V,A,t_1)\neq R(V,A,t_2)
\]

avec :

\[
\sigma_V(t_1)=\sigma_V(t_2)
\]

**RETENU**

Cela protège l'invariant :

\[
SAVOIR \neq PROUVER \neq ETRE\ AUTORISE \neq POUVOIR\ AGIR\ ICI\ MAINTENANT
\]

Les relations appartiennent à l'Univers mais ne doivent pas être confondues avec l'état intrinsèque du véhicule.

---

# 24. Aptitude

**RETENU**
- l'aptitude est intrinsèque au véhicule ;
- elle ne doit pas dépendre directement de la cible ;
- savoir faire quelque chose != posséder une preuve ;
- Proof/Credential/expérience ne sont pas l'aptitude elle-même.

`EtatAptitude` :

**CANDIDAT**

Dimensions et représentation :

**À DÉTERMINER**

Pas de score global arbitraire.

---

# 25. Orientation

**RETENU**
- une orientation instantanée unique peut exister ;
- elle peut changer sans Position ;
- orientation != destination ;
- orientation != Dossier ;
- orientation != Interest ;
- orientation != OpenTo ;
- orientation != aptitude ;
- orientation != direction de vitesse ;
- orientation != direction d'accélération.

`EtatOrientationnelMakolo` :

**CANDIDAT**

Représentation exacte :

**À DÉTERMINER**

Quaternion/3D universel pour tout Makolo :

**SANS ÉQUIVALENT**

---

# 26. Couplage

Même environnement + récepteurs différents peut produire des réponses différentes.

Concepts de travail :

\[
ProprietesDeCouplage(V,t)
\]

**CANDIDAT**

\[
CouplageEffectif(V,X,t)
\]

**CANDIDAT**

Mais :

- Interest = charge → **SANS ÉQUIVALENT**
- OpenTo = charge → **SANS ÉQUIVALENT**
- Aptitude = charge → **SANS ÉQUIVALENT**
- charge scalaire universelle Makolo → **SANS ÉQUIVALENT**

Les faits applicatifs pourraient éventuellement contribuer à établir des propriétés de couplage, mais pas par simple ressemblance.

---

# 27. Champs, sources, flux, interactions, effets

Séparation **RETENUE** :

\[
\boxed{
Source \neq Champ \neq Flux \neq Interaction \neq Effet
}
\]

`SourceMakolo` comme rôle :

**CANDIDAT**

`ChampMakolo` comme mécanisme général :

**CANDIDAT**

Familles concrètes de champs :

**À DÉTERMINER**

Un champ :
- est distinct de ses sources ;
- ne doit pas être une liste de résultats Discovery ;
- ne doit pas être un score personnalisé ;
- doit exister indépendamment du récepteur si on veut respecter l'idée physique de champ.

Une interaction :
- n'est pas un candidat Discovery ;
- n'est pas une compatibilité ;
- n'est pas un voisinage ;
- n'est pas automatiquement un effet ;
- peut produire zéro effet.

---

# 28. Dynamique continue et événements discrets

Le modèle doit probablement être **hybride**.

Partie continue :

\[
\frac{dX}{dt}=F(X,t)
\]

Transitions discrètes :

\[
X^+=\Psi(X^-,e)
\]

**CANDIDAT**

Acquis :

\[
\boxed{
tout\ changement \neq translation
}
\]

Une relation ou un droit peut changer discrètement sans déplacement physique.

---

# 29. Configuration et espace des états

Acquis :

\[
\boxed{
EspaceTemps \neq EspaceDesEtats
}
\]

On peut avoir :

\[
x^\mu\in\mathcal M_M
\]

pour la position spatio-temporelle,

et :

\[
X\in\Gamma_M
\]

pour l'état complet.

`EspaceDesEtatsMakolo` / `EspaceDesPhasesMakolo` :

**CANDIDAT**

Structure exacte :

**À DÉTERMINER**

---

# 30. Coordonnées généralisées

La mécanique analytique établie autorise :

\[
q=(q^1,\ldots,q^n)
\]

mais il ne faut pas transformer chaque propriété métier en coordonnée.

Test proposé pour une vraie coordonnée candidate :

1. **Identité** : sa variation ne change pas l'identité du corps.
2. **Référentiel** : elle est définie dans un cadre explicite.
3. **Voisinage** : un petit \(dq_i\) a un sens.
4. **Cinématique** : \(\dot q_i\) est significatif.
5. **Conjugaison dynamique** : un \(Q_i\) peut éventuellement exister avec
   \[
   \delta W=\sum_i Q_i\,dq_i
   \]
6. **Cohérence système** : ce n'est pas un score local spécifique à une seule verticale.
7. **Projection indépendante** : Readiness/relevance peuvent dépendre de \(q_i\), mais ne définissent pas \(q_i\).

À ce stade, aucune grandeur métier non géographique n'a pleinement passé le test.

---

# 31. Masse

`MasseMakolo` :

**À DÉTERMINER**

Signature physique étudiée :
- masse instantanée ;
- inertie ;
- momentum ;
- source gravitationnelle ;
- barycentre ;
- composition ;
- énergie ;
- variable mass ;
- masse-énergie relativiste.

Écartés comme masse directe :

- Credits ;
- argent disponible ;
- Capacity ;
- Aptitude ;
- Interest ;
- OpenTo ;
- Proof ;
- Credential ;
- Access ;
- Permission ;
- Mandate ;
- Readiness ;
- Dossier ;
- Journey ;
- Personal Assets / action capital ;
- complétude du Profile ;
- score arbitraire.

Tous : **SANS ÉQUIVALENT** comme masse.

Au niveau relativiste :

\[
E^2=P^2c^2+M^2c^4
\]

et au centre d'impulsion :

\[
M=\frac{E_{\text{total}}}{c^2}
\]

Donc :

\[
M_S\neq \sum_i m_i
\]

en général.

La somme des masses des constituants n'est qu'une approximation classique selon le régime.

---

# 32. Energie

`EnergieMakolo` :

**À DÉTERMINER**

Ne pas chercher « où est l'énergie dans la BDD ».

Elle peut être :

\[
E=\mathcal E[X]
\]

une fonction de l'état global.

Candidats directs déjà éliminés :
- Readiness ;
- CV ;
- Proof ;
- Credential ;
- argent ;
- Aptitude ;
- nombre de candidats ;
- nombre de Requirements satisfaits ;
- nombre d'actions ;
- nombre d'objets BDD.

Tous : **SANS ÉQUIVALENT** comme énergie directe.

Signature d'une candidate énergie :
1. unité commune cohérente ;
2. présence/stockage selon le modèle ;
3. transfert ;
4. transformation entre formes ;
5. conservation dans les régimes appropriés ;
6. échange via travail/flux ;
7. cohérence avec momentum ;
8. cohérence masse-énergie si régime relativiste.

---

# 33. Momentum

`QuantiteMouvementMakolo` :

**À DÉTERMINER**

Physique de référence :

\[
\mathbf p=m\mathbf v
\]

dans le régime classique approprié.

\[
\mathbf F=\frac{d\mathbf p}{dt}
\]

Relativiste :

\[
p^\mu=
\left(
\frac Ec,\mathbf p
\right)
\]

Acquis :

\[
\boxed{
existence\ de\ momentum \not\Rightarrow conservation\ du\ momentum
}
\]

La conservation dépend du système et des symétries.

---

# 34. Travail et puissance

Physique :

\[
dW=\mathbf F\cdot d\mathbf r
\]

\[
W=\int\mathbf F\cdot d\mathbf r
\]

\[
P=\mathbf F\cdot\mathbf v
\]

**RETENU**

\[
Force\neq Travail\neq Energie\neq Puissance
\]

`TravailMakolo` :

**À DÉTERMINER**

`PuissanceMakolo` :

**À DÉTERMINER**

« Toute action utile = travail physique » :

**SANS ÉQUIVALENT**

« progression d'une Journey = déplacement physique » :

**SANS ÉQUIVALENT**

---

# 35. Potentiel

`PotentielMakolo` :

**À DÉTERMINER**

En mécanique conservatrice :

\[
U=U(q)
\]

\[
F_i=-\frac{\partial U}{\partial q_i}
\]

Ne pas appeler :
- Requirement ;
- Readiness ;
- complétude ;
- difficulté ;

« potentiel » sans relation physique démontrée.

---

# 36. Hamiltonien

`HamiltonienMakolo` :

**À DÉTERMINER**

Si un véritable Hamiltonien existe :

\[
H(q,p,t)
\]

alors :

\[
\dot q_i=\frac{\partial H}{\partial p_i}
\]

\[
\dot p_i=-\frac{\partial H}{\partial q_i}
\]

Mais ne jamais introduire \(H\) avant d'avoir des variables physiques légitimes.

---

# 37. Symétries et Noether

La physique établie donne :

\[
translation\ temporelle
\Rightarrow énergie
\]

\[
translation\ spatiale
\Rightarrow momentum
\]

\[
rotation
\Rightarrow moment\ cinétique
\]

dans les conditions appropriées.

**RETENU** comme méthode scientifique.

Important :
- changement de représentation != symétrie dynamique de Noether ;
- permutation d'UUID != charge de Noether ;
- vocabulaire UI != symétrie physique continue.

Symétries globales exactes Makolo :

**À DÉTERMINER**

Energie globale universelle conservée :

**SANS ÉQUIVALENT** actuellement / ne pas supposer.

---

# 38. Causalité

Piste de travail actuelle.

Concept :

\[
X\prec Y
\]

pour dire :

> X peut dynamiquement/physiquement influencer Y dans le modèle considéré.

`RelationCausaleMakolo` :

**CANDIDAT**

Structure exacte :

**À DÉTERMINER**

Cette notion pourrait aider à comprendre :
- frontières de systèmes ;
- appartenance d'Occurrences externes ;
- interaction ;
- espace physique/virtuel ;
- propagation ;
- rôle du temps ;
- certains aléas.

Mais ne pas en faire encore une loi ou un graphe algorithmique.

---

# 39. Diversification des situations : obligatoire

Ne pas rester seulement sur la bourse.

Batterie minimale de situations :

## 39.1 Bourse / Opportunity
- fenêtre de candidature ;
- Requirements ;
- capacité éventuelle ;
- Profiles en compétition ;
- états collectifs différents.

## 39.2 Evénement
- conférence ;
- concert ;
- plusieurs Occurrences ;
- présence physique ou hybride ;
- capacité ;
- Access.

## 39.3 Transport
- route ;
- arrêts ;
- départs exacts ;
- véhicule ;
- capacité ;
- trajectoire ;
- géographie forte.

## 39.4 Service
- passeport ;
- accompagnement administratif ;
- étapes ;
- dépendances ;
- outcomes ;
- délais.

## 39.5 Financement
- objectif financier ;
- contributions ;
- fenêtre temporelle ;
- système évoluant sans déplacement spatial.

## 39.6 Système composé
Exemple :
- Coupe du Monde ;
- matchs ;
- vols ;
- hôtels ;
- services ;
- transports ;
- fan zones ;
- autres Activities intégrées dans un même système dynamique.

Ce qui survit à toutes ces verticales est plus crédible comme structure fondamentale.

---

# 40. Faits actuels vérifiés dans `main`

Au moment de la consolidation, `main` était au commit :

`4e925eb24de4224300d3386db12edd958186987a`

Ce commit converge Discovery sur :
- Activity / Occurrence ;
- Event ;
- Transport ;
- Service ;
- Opportunity ;
- Funding.

Quelques faits utiles du runtime actuel :

## Event
Event est du vocabulaire au-dessus d'`Activity + une ou plusieurs Occurrences`.

## Transport
Le Transport compose :
- `TransportService` ↔ Activity ;
- `TransportDeparture` ↔ Occurrence ;
- Route avec arrêts ordonnés ;
- véhicule ;
- CapacityPool ;
- heure exacte obligatoire pour un départ.

## Funding
Funding ajoute à Activity :
- devise ;
- target_amount ;
- minimum/maximum contribution ;
- opens_at ;
- closes_at ;
- contributions ;
- Payment reste vérité d'exécution.

## Service
Service ajoute :
- type de service ;
- politiques ;
- templates de plan ;
- étapes ;
- dépendances entre étapes ;
- Journey context ;
- outcome courant.

Ces faits doivent servir à diversifier les exemples, pas à copier les tables dans l'Univers.

---

# 41. Exemple des deux bourses

Expérience historique importante.

Deux bourses identiques :
- même nature ;
- même nombre de places : 2 ;
- mêmes conditions générales.

### A1
- 30 personnes ont entrepris la démarche ;
- 27 ont finalisé ;
- deadline dans 20 jours ;
- sélection non faite ;
- un 31e peut encore gagner.

### A2
- 6 candidats ;
- aucun n'a complété les critères.

Un nouveau Profile correspond aux deux.

Intuition :
Makolo devrait percevoir que les deux systèmes ne sont pas dans le même état.

Acquis :

\[
\mathcal X_{A1}\neq \mathcal X_{A2}
\]

même si :
- type identique ;
- Capacity identique ;
- Requirements identiques.

Mais ne pas conclure directement :
- A2 = moins de masse ;
- A2 = plus d'énergie ;
- A2 = plus attractive.

Ces identifications sont **SANS ÉQUIVALENT** ou **À DÉTERMINER** selon le cas.

---

# 42. Expérience système fermé / ouvert

Autre acquis important.

Un système peut changer profondément sans changer son énergie totale.

En physique :
- système fermé ;
- transformations internes ;
- même énergie totale possible.

Donc :

\[
Etat(t_0)\neq Etat(t_1)
\]

n'implique pas :

\[
E(t_0)\neq E(t_1)
\]

**RETENU**

Pour un système ouvert, il faut considérer les flux à travers la frontière.

Cela renforce l'importance de :

\[
\partial S
\]

avant d'étudier conservation, énergie ou masse.

---

# 43. Pièges à éviter absolument

## 43.1 Ne pas repartir à zéro
Ne pas remettre en question tous les acquis à chaque nouveau domaine.

## 43.2 Ne pas faire de mapping table ↔ physique
Exemple interdit :
- `FundingContribution = énergie`
- `Requirement = barrière de potentiel`
- `Journey = momentum`

sans preuve physique.

## 43.3 Ne pas fabriquer des scores
Pas de :
- masse = popularité ;
- énergie = readiness ;
- distance = score de matching ;
- potentiel = complétude.

## 43.4 Ne pas déformer la géographie
Une formation en ligne Chine–Pérou ne rend pas la distance géographique nulle.

## 43.5 Ne pas confondre interaction et recommandation
Une recommandation ou une carte Discovery n'est pas une force physique.

## 43.6 Ne pas transformer tous les changements en mouvement
Un droit, une relation ou une preuve peut changer sans translation.

## 43.7 Ne pas confondre source et émission
Source != champ != flux != interaction != effet.

## 43.8 Ne pas confondre état intrinsèque et relation
Exemple :
- aptitude intrinsèque ;
- proof relationnel/établissant ;
- access droit ;
- readiness projection.

## 43.9 Ne pas faire du vocabulaire produit une ontologie physique
Un objet Django nommé `Vehicle` n'est pas automatiquement `VehiculeMakolo`.

## 43.10 Ne pas introduire les algorithmes trop tôt
Le but final est algorithmique, mais l'étape actuelle est ontologique/physique.

---

# 44. Photo actuelle de l'Univers Makolo

Squelette provisoire :

\[
\boxed{
\mathcal U_M
=
(
\mathcal M,
\mathcal B,
\mathcal S,
X,
\mathcal R,
\mathcal F,
\Phi,
\mathcal I,
\mathcal C,
\mathcal L
)
}
\]

où :

- \(\mathcal M\) : espace / espace-temps ;
- \(\mathcal B\) : corps ;
- \(\mathcal S\) : systèmes ;
- \(X\) : états ;
- \(\mathcal R\) : relations ;
- \(\mathcal F\) : champs ;
- \(\Phi\) : flux / rayonnements ;
- \(\mathcal I\) : interactions ;
- \(\mathcal C\) : contraintes / conditions ;
- \(\mathcal L\) : lois physiques.

Puis des grandeurs dérivées potentielles :

\[
M[X],\quad E[X],\quad P^\mu[X],\quad J[X],\ldots
\]

plusieurs restant **À DÉTERMINER**.

Dynamique :

\[
X(t)\rightarrow X(t+\Delta t)
\]

avec composantes continues et événements discrets.

---

# 45. Points considérés acquis et à ne pas rouvrir sans contradiction réelle

- objet != état ;
- état != position ;
- relation != état intrinsèque ;
- Activity ancre un système ;
- système != conteneur FK ;
- Occurrence sert de Corps/Planète de travail ;
- Profile sert de Véhicule de travail ;
- système peut inclure des Occurrences d'autres Activities ;
- frontière dépend du modèle ;
- masse/énergie peuvent être dérivées ;
- Readiness est une projection ;
- Access est un droit ;
- Capacity = combien ;
- Placement = où ;
- virtuel != distance géographique nulle ;
- timestamp DB != temps de l'Univers ;
- état global != BDD complète ;
- progression métier != mouvement physique ;
- même composition != même état ;
- même état applicatif apparent != nécessairement même état physique ;
- description != état physique.

---

# 46. Grands inconnus encore ouverts

\[
\boxed{\text{géométrie exacte de l'espace Makolo}}
\]

\[
\boxed{\text{statut physique exact du lieu virtuel}}
\]

\[
\boxed{\text{structure exacte de l'état complet}}
\]

\[
\boxed{\text{frontière générale d'un système}}
\]

\[
\boxed{\text{relation causale}}
\]

\[
\boxed{\text{propriétés de couplage}}
\]

\[
\boxed{\text{familles concrètes de champs}}
\]

\[
\boxed{\text{masse}}
\]

\[
\boxed{\text{énergie}}
\]

\[
\boxed{\text{momentum}}
\]

\[
\boxed{\text{potentiel}}
\]

\[
\boxed{\text{Hamiltonien éventuel}}
\]

\[
\boxed{\text{rôle physique exact des conditions/aléas}}
\]

\[
\boxed{\text{symétries réelles de l'Univers Makolo}}
\]

---

# 47. Point de reprise recommandé

La conversation s'était arrêtée juste avant d'approfondir :

\[
\boxed{
\text{causalité + espace + temps + conditions}
}
\]

Question de reprise :

> **Dans l'Univers Makolo, que signifie physiquement qu'un corps, une Occurrence, un champ ou un événement puisse encore influencer un autre objet ou événement ?**

Pourquoi c'est le prochain bon point :
- ça peut clarifier la frontière des systèmes ;
- ça peut expliquer pourquoi une Occurrence d'une autre Activity appartient parfois au système étudié ;
- ça peut éclairer le virtuel sans falsifier la distance géographique ;
- ça relie temps, espace et propagation ;
- ça peut permettre de ranger certains « aléas » ;
- ça reste ontologique/physique, sans entrer prématurément dans les algorithmes.

---

# 48. Méthode de travail pour la suite

À chaque nouveau concept :

1. **Partir de la physique établie.**
2. Décrire clairement le concept physique.
3. Vérifier sa structure mathématique et ses hypothèses.
4. Tester plusieurs situations Makolo réalistes :
   - bourse ;
   - concert ;
   - transport ;
   - service ;
   - financement ;
   - système composé.
5. Chercher ce qui est invariant.
6. Ne jamais forcer un mapping de table.
7. Ne pas transformer un mot métier en grandeur physique juste parce que le nom ressemble.
8. Classer :
   - RETENU ;
   - CANDIDAT ;
   - À DÉTERMINER ;
   - SANS ÉQUIVALENT.
9. Mettre à jour le registre consolidé.
10. Ne parler d'algorithmes qu'après avoir établi l'Univers et les lois pertinentes.

---

# 49. Ton de collaboration souhaité

Répondre principalement en français.

Style :
- concret ;
- technique ;
- progressif ;
- rigoureux ;
- sans exagération ;
- sans flatterie ;
- sans « analogies jolies » qui ne tiennent pas physiquement.

Pour une tâche complexe :
- diagnostic court ;
- plan ;
- progression ;
- consolidation périodique.

Toujours challenger les hypothèses.

Le but n'est pas de confirmer l'utilisateur, mais de **découvrir une structure qui résiste aux contre-exemples**.

---

# 50. Prompt prêt à coller dans une nouvelle conversation

Copier le prompt ci-dessous avec ce document attaché.

---

## PROMPT DE TRANSFERT

Tu reprends une conversation de recherche conceptuelle sur **l'Univers Makolo**.

Lis intégralement le document joint `Makolo_Univers_Transfer_2026-09-11.md` avant de poursuivre.

Règles essentielles :

1. Ne recommence pas l'analyse depuis zéro.
2. Les acquis indiqués comme RETENU ou comme bases de travail déjà stabilisées doivent servir de contraintes, sauf contradiction physique ou canonique nouvelle clairement démontrée.
3. Utilise uniquement les statuts formels :
   - RETENU
   - CANDIDAT
   - À DÉTERMINER
   - SANS ÉQUIVALENT
4. La référence scientifique est **la physique établie**, pas seulement V2.3.
5. V2.3 est un état historique de modélisation, pas une limite scientifique.
6. L'Univers Makolo n'est pas la BDD Makolo.
7. Ne cherche pas des correspondances naïves `champ Django -> masse/énergie/position`.
8. Une grandeur physique peut être dérivée de plusieurs faits sans être stockée.
9. Ne fabrique aucune « loi Makolo » pour combler les trous : une loi transposée garde sa forme physique et exige des équivalents légitimes pour tous ses termes.
10. Ne conçois pas encore les algorithmes. Nous sommes au stade :
   `Univers -> objets -> états -> relations -> lois -> dynamique`.
   Les algorithmes viendront ensuite.
11. Diversifie toujours les situations :
   - bourse/opportunité ;
   - événement ;
   - transport ;
   - service ;
   - financement ;
   - systèmes composés comme une Coupe du Monde.
12. Ne réduis jamais le système d'une Activity à ses seules Occurrences applicatives : des Occurrences d'autres Activities peuvent appartenir au même système dynamique.
13. Garde les invariants canoniques Makolo intacts.
14. Challenge les hypothèses avec de vrais contre-exemples.
15. Ne traite jamais :
   - Readiness comme énergie ;
   - Journey comme momentum ;
   - Requirement comme potentiel ;
   - popularité comme masse ;
   - distance de matching comme position ;
   sans démonstration physique complète.

Point de reprise :

Nous venons de consolider l'Univers Makolo. La prochaine piste est **la causalité dans l'espace-temps Makolo**, reliée à :
- la frontière des systèmes ;
- l'appartenance d'Occurrences venant d'autres Activities ;
- les lieux physiques et virtuels ;
- le temps ;
- les conditions/aléas.

Commence par rappeler très brièvement les acquis nécessaires puis poursuis cette question :

> **Dans l'Univers Makolo, que signifie physiquement qu'un corps, une Occurrence, un champ ou un événement puisse encore influencer un autre objet ou événement ?**

Ne saute pas aux algorithmes.

---
