# UNIVERS MAKOLO
## Théorie physico-géométrique consolidée de représentation et de dynamique

**Version proposée pour consolidation canonique — 14 septembre 2026**  
**Statut du document : synthèse scientifique structurée pour validation**

---

# Résumé

L’Univers Makolo est un **univers formel construit**, distinct à la fois du point de vue métier et du système de stockage ou d’exécution informatique. Il possède ses propres objets, états, relations, coordonnées, structures géométriques et règles d’évolution. Les données extérieures peuvent servir à **projeter** des faits vers cet univers, mais, une fois cette projection effectuée, la structure interne de l’Univers Makolo ne dépend plus de la sémantique métier ni de la représentation technique de la source.

La présente théorie fixe cette séparation et clarifie un point méthodologique central : la géométrie interne de Makolo n’a pas à être « découverte » comme si elle était une propriété cachée de la Terre ou des URI. Elle peut être **posée constitutivement** comme une structure mathématique de l’univers construit. En revanche, les applications de cette géométrie, les projections qui alimentent ses coordonnées et les futures lois dynamiques doivent rester cohérentes, stables, falsifiables et explicitement limitées à leurs hypothèses.

Le secteur complet des PointsMakolo est ainsi organisé autour de deux coordonnées internes,

\[
p=(g,i),
\]

où \(g\) est une coordonnée géographique Makolo et \(i\) une coordonnée logique Makolo. Ces coordonnées ne sont ni des kilomètres, ni des nombres d’actions, ni des difficultés, ni des valeurs humaines. Elles sont des coordonnées internes du modèle.

La structure géométrique retenue pour le secteur complet est le **plan affine euclidien réel de dimension deux**, muni du produit scalaire standard. Les conséquences classiques — vecteurs de déplacement, norme, distance euclidienne, orthogonalité, translations, rotations et théorème de Pythagore — sont donc des résultats mathématiques de cette structure. Elles ne prétendent pas reproduire la métrique terrestre ni une métrique sémantique des URI.

La théorie distingue également les loci complets des loci partiels, la position de l’état interne, l’ontologie de la dynamique, les relations, les systèmes et la frontière endogène/exogène. La dynamique générale reste relationnelle : aucune loi universelle de type newtonien, lagrangien, hamiltonien ou quantique n’est actuellement imposée. Les théories scientifiques établies doivent être transposées **lorsque leurs hypothèses sont satisfaites**, et non réinventées ni importées par simple analogie.

---

# 1. Nature de l’Univers Makolo

## 1.1. Trois niveaux strictement distincts

La théorie impose la séparation :

\[
\boxed{
\text{point de vue métier}
\neq
\text{backend}
\neq
\text{Univers Makolo}
}
\]

**RETENU**.

Le **point de vue métier** décrit les objets et situations tels qu’ils sont compris dans l’activité humaine : une personne, un voyage, un concert, une occurrence, une adresse, un besoin ou une destination.

Le **backend** décrit leur représentation informatique : modèles, tables, identifiants, relations techniques, clés, sérialisations, timestamps, formats de données et structures d’exécution.

L’**Univers Makolo** est une représentation formelle autonome. Il contient des CorpsMakolo, des états, des relations, des loci, des systèmes et des structures dynamiques. Ses coordonnées et ses opérations n’ont pas à reproduire directement le vocabulaire métier ni les structures du backend.

Cette séparation interdit notamment :

\[
\boxed{
\text{structure de stockage}
\Rightarrow
\text{structure physique}
}
\]

et :

\[
\boxed{
\text{sémantique métier}
\Rightarrow
\text{géométrie interne}
}
\]

sans règle de projection explicite.

---

## 1.2. Univers construit et statut scientifique

L’Univers Makolo est un **modèle formel construit**. Il n’est pas présenté comme une nouvelle théorie fondamentale de la Nature.

Cette distinction permet de séparer trois types d’énoncés :

### A. Décisions constitutives

Elles définissent la structure du modèle.

Exemples :

- la forme d’un PointMakolo ;
- le choix d’un espace affine réel ;
- le choix d’une métrique euclidienne interne ;
- la distinction entre une composante absente et la valeur zéro.

Une décision constitutive peut être **RETENU** par définition du modèle sans prétendre être une observation empirique sur le monde extérieur.

### B. Théorèmes dérivés

Ils suivent mathématiquement des décisions constitutives.

Exemples :

- relation de Chasles ;
- théorème de Pythagore dans le secteur euclidien ;
- invariance de la norme sous les rotations orthogonales ;
- bornage d’une projection donnée ;
- injectivité d’un encodage sous des hypothèses précises.

### C. Hypothèses dynamiques ou de projection

Elles portent sur la manière dont des faits sources alimentent l’univers, ou sur la manière dont les états évoluent.

Elles restent **CANDIDAT** ou **À DÉTERMINER** jusqu’à ce que leur domaine et leurs conséquences soient suffisamment établis.

---

# 2. Principe de projection et autonomie interne

## 2.1. Projection vers l’Univers

Soit \(S_G\) un domaine de faits géographiques sources et \(S_I\) un domaine de faits logiques sources.

On introduit deux applications de projection :

\[
\pi_G:S_G\rightarrow \mathbb R,
\]

\[
\pi_I:S_I\rightarrow \mathbb R.
\]

Elles produisent les coordonnées internes :

\[
g=\pi_G(s_G),
\qquad
 i=\pi_I(s_I).
\]

Le PointMakolo complet est alors :

\[
\boxed{p=(g,i)}.
\]

**RETENU**.

---

## 2.2. Principe d’effacement sémantique après projection

Une fois \(g\) ou \(i\) obtenus, les opérations géométriques de l’Univers Makolo portent sur les coordonnées internes et non sur la sémantique originale de leur source.

\[
\boxed{
\text{source}
\xrightarrow{\pi}
\text{coordonnée Makolo}
\quad\Longrightarrow\quad
\text{géométrie interne indépendante de la source}
}
\]

**RETENU**.

Cela signifie notamment qu’après projection :

- \(g\) n’est plus « une longitude » ;
- \(i\) n’est plus « une URI » ;
- une différence \(|g_2-g_1|\) n’est pas une distance terrestre ;
- une différence \(|i_2-i_1|\) n’est pas une difficulté logique ;
- une norme dans Makolo n’est pas une utilité humaine.

La projection peut volontairement préserver certaines propriétés de la source, mais uniquement si ces propriétés sont inscrites dans son **contrat de représentation**.

---

## 2.3. Contrat de représentation

Une projection scientifique doit préciser ce qu’elle cherche à préserver.

Le contrat peut contenir, selon le secteur :

1. **déterminisme** : une même source canonique donne toujours la même coordonnée ;
2. **stabilité** : la règle de projection ne dépend pas du contexte utilisateur ;
3. **typabilité** : une composante géographique et une composante logique ne sont pas confondues ;
4. **injectivité opérationnelle** : deux sources distinctes qui doivent rester distinguables ne sont pas confondues sur le domaine déclaré ;
5. **bornage** : lorsque souhaité, les coordonnées restent dans une plage contrôlée ;
6. **localité ou ordre** : seulement si l’on décide qu’une propriété de voisinage ou d’ordre doit survivre à la projection ;
7. **isométrie** : uniquement si une distance source doit réellement être préservée.

La théorie actuelle **n’exige pas** qu’une projection soit une isométrie du monde source.

**RETENU**.

---

# 3. Espace des loci Makolo

## 3.1. Coordonnées

La composante géographique Makolo est notée :

\[
g\in\mathbb R_G,
\]

et la composante logique :

\[
i\in\mathbb R_I.
\]

Dans la présente théorie, \(\mathbb R_G\) et \(\mathbb R_I\) sont deux copies typées du corps des réels.

\[
\boxed{g,i\in\mathbb R}
\]

est **RETENU comme décision constitutive de représentation**.

Le fait d’utiliser les réels ne signifie pas que les sources sont elles-mêmes continues. Cela définit seulement le codomaine interne des coordonnées.

---

## 3.2. Absence d’une composante

On conserve deux symboles typés :

\[
\bot_G,
\qquad
\bot_I,
\]

avec :

\[
\boxed{\bot_G\neq0,\qquad \bot_I\neq0}.
\]

**RETENU**.

Une composante absente n’est donc jamais remplacée par zéro.

Trois types de loci sont admis :

\[
(g,i),
\qquad
(g,\bot_I),
\qquad
(\bot_G,i).
\]

En revanche :

\[
(\bot_G,\bot_I)
\]

ne définit aucun locus.

---

## 3.3. Espace stratifié des loci

On définit :

\[
\mathcal P_{GI}=\{(g,i):g,i\in\mathbb R\},
\]

\[
\mathcal P_G=\{(g,\bot_I):g\in\mathbb R\},
\]

\[
\mathcal P_I=\{(\bot_G,i):i\in\mathbb R\}.
\]

L’espace des loci est la réunion disjointe :

\[
\boxed{
\mathcal P_M
=
\mathcal P_{GI}
\sqcup
\mathcal P_G
\sqcup
\mathcal P_I.
}
\]

**RETENU**.

Cette écriture donne à l’espace une structure **stratifiée** :

- une strate complète bidimensionnelle ;
- une strate géographique unidimensionnelle ;
- une strate logique unidimensionnelle.

Aucune distance entre deux strates différentes n’est définie automatiquement.

---

# 4. Géométrie interne du PointMakolo

## 4.1. Secteur complet

Le secteur complet \(\mathcal P_{GI}\) est défini comme un **plan affine réel de dimension deux**.

\[
\boxed{
\mathcal P_{GI}\simeq \mathbb A^2(\mathbb R)
}
\]

**RETENU comme décision constitutive**.

Son espace vectoriel directeur est :

\[
V_M\simeq\mathbb R^2.
\]

Pour deux points :

\[
p_A=(g_A,i_A),
\qquad
p_B=(g_B,i_B),
\]

le déplacement est :

\[
\boxed{
\overrightarrow{AB}
=
p_B-p_A
=
(\Delta g,\Delta i)
}
\]

avec :

\[
\Delta g=g_B-g_A,
\qquad
\Delta i=i_B-i_A.
\]

La relation de Chasles suit immédiatement :

\[
\boxed{
\overrightarrow{AB}
+
\overrightarrow{BC}
=
\overrightarrow{AC}.
}
\]

**RETENU comme théorème dérivé**.

---

## 4.2. Produit scalaire Makolo

Le secteur complet est muni du produit scalaire standard :

\[
\boxed{
\langle(a,b),(c,d)\rangle_M
=
ac+bd.
}
\]

**RETENU comme décision constitutive**.

Il induit la norme :

\[
\boxed{
\|(a,b)\|_M
=
\sqrt{a^2+b^2}
}
\]

et la distance interne :

\[
\boxed{
 d_M(A,B)
=
\sqrt{
(g_B-g_A)^2
+
(i_B-i_A)^2
}.
}
\]

**RETENU comme définition géométrique interne**.

Cette distance est exprimée en **unités géométriques Makolo**.

Elle ne représente pas, par elle-même :

- des kilomètres ;
- des secondes ;
- une difficulté ;
- un nombre d’actions ;
- un coût ;
- une utilité ;
- une probabilité ;
- une accessibilité humaine.

Ces interprétations sont **SANS ÉQUIVALENT** dans la géométrie seule.

---

## 4.3. Orthogonalité et égalité d’échelle

Les vecteurs de base :

\[
e_G=(1,0),
\qquad
 e_I=(0,1)
\]

satisfont :

\[
\langle e_G,e_I\rangle_M=0,
\]

\[
\|e_G\|_M=\|e_I\|_M=1.
\]

Par conséquent :

\[
\boxed{G\perp I}
\]

et :

\[
\boxed{1G=1I}
\]

sont **RETENU à l’intérieur de la géométrie constitutive du secteur complet**.

Ils ne signifient pas qu’un degré géographique source et un degré logique source possèdent la même signification externe.

---

## 4.4. Homogénéité et isotropie internes

Le plan euclidien choisi est homogène et isotrope du point de vue purement géométrique.

Ainsi, pour toute translation \(T\) :

\[
 d_M(A+T,B+T)=d_M(A,B),
\]

et pour toute transformation orthogonale \(R\) :

\[
\|Rv\|_M=\|v\|_M.
\]

**RETENU comme propriétés mathématiques de la géométrie choisie**.

Ces invariances sont des invariances de la géométrie interne. Elles ne sont pas encore des symétries des lois dynamiques, puisque les lois dynamiques concrètes restent ouvertes.

---

## 4.5. Strates partielles

La strate \(\mathcal P_G\) hérite naturellement d’une géométrie euclidienne unidimensionnelle :

\[
 d_G^M(g_1,g_2)=|g_2-g_1|.
\]

De même :

\[
 d_I^M(i_1,i_2)=|i_2-i_1|.
\]

Ces distances sont **internes à Makolo**.

Elles ne doivent pas être confondues avec une distance terrestre pour \(G\) ni avec une difficulté ou une distance sémantique pour \(I\).

Aucune distance canonique n’est définie entre, par exemple, \((g,\bot_I)\) et \((g',i')\) tant qu’une règle de complétion ou de comparaison inter-strates n’est pas explicitement définie.

---

# 5. Projections candidates vers les axes

## 5.1. Projection géographique candidate

Soient :

\[
\lambda=\text{longitude},
\qquad
\varphi=\text{latitude}.
\]

Sur le domaine opérationnel de coordonnées stockées à précision décimale finie, on peut les modéliser comme rationnelles.

La projection candidate est :

\[
\boxed{
E_G(\lambda,\varphi)
=
\frac{\lambda}{\sqrt2}
+
(2-\sqrt2)\varphi.
}
\]

**CANDIDAT**.

Pour :

\[
\lambda\in[-180,180],
\qquad
\varphi\in[-90,90],
\]

elle vérifie :

\[
\boxed{-180\le g\le180}.
\]

**RETENU comme théorème conditionnel à cette projection**.

Sur le domaine rationnel déclaré, elle est injective : l’irrationalité de \(\sqrt2\) empêche deux couples rationnels distincts d’avoir la même image.

**RETENU comme théorème conditionnel au domaine rationnel**.

Sur le continuum réel complet :

\[
E_G:\mathbb R^2\rightarrow\mathbb R
\]

n’est pas injective. Par exemple :

\[
\Delta\varphi=1,
\qquad
\Delta\lambda=2(1-\sqrt2)
\]

appartient à son noyau.

**RETENU comme théorème mathématique**.

Cette non-injectivité sur \(\mathbb R^2\) n’est pas contradictoire avec l’usage opérationnel sur un domaine discret ou rationnel déclaré.

---

## 5.2. Ce que \(E_G\) n’est pas obligé de préserver

La projection \(E_G\) n’est pas supposée être une isométrie de la Terre.

En particulier :

\[
|E_G(x)-E_G(y)|
\]

n’est pas une distance géodésique.

Le rôle de \(E_G\) est de produire une coordonnée interne stable et compacte.

La question de savoir si elle doit en plus préserver un ordre, une notion de voisinage ou une localité géographique est **À DÉTERMINER par le contrat de représentation**, et non imposée par la géométrie euclidienne interne.

---

## 5.3. Projection logique candidate

Une source logique est d’abord transformée en une séquence canonique :

\[
\Gamma(u)=(c_0,c_1,\ldots,c_k),
\]

avec :

\[
 c_j\in\mathbb Q\cap[-1,1].
\]

La canonisation est **scheme-aware** : la structure d’une URI dépend de son scheme et ne doit pas être réduite à une segmentation uniforme.

Cette règle générale est **RETENU**.

La fonction exacte qui associe des coefficients rationnels aux nœuds canoniques reste :

**À DÉTERMINER**.

Une construction candidate est :

\[
\alpha=e^{-1},
\]

\[
\boxed{
E_I(c_0,\ldots,c_k)
=
180(1-\alpha)
\left[
\sum_{j=0}^{k}c_j\alpha^j
+
\tau\alpha^{k+1}
\right],
}
\]

avec \(\tau\in\mathbb Q\setminus\{0\}\) et \(|\tau|\le1\).

**CANDIDAT**.

Sous ces hypothèses :

\[
|i|<180.
\]

La transcendance de \(e^{-1}\) implique également l’injectivité de la représentation polynomiale lorsque la séquence canonique est unique et rationnelle.

**RETENU comme théorème conditionnel**.

---

## 5.4. Interprétation de l’axe logique

Le nombre \(i\) est d’abord une **coordonnée interne**.

Une grande différence \(|i_2-i_1|\) ne signifie pas automatiquement :

- plus de difficulté ;
- plus d’étapes ;
- moins de possibilités ;
- plus de coût.

Ces notions sont extérieures à la géométrie elle-même.

La géométrie interne peut néanmoins utiliser \(i\) comme axe euclidien parce que cette propriété est constitutive de l’Univers Makolo, et non parce qu’elle prétend reproduire une métrique universelle des URI.

---

# 6. Temps et situations

## 6.1. Temps

Le temps est représenté par un ensemble ordonné :

\[
\boxed{t\in T}.
\]

**RETENU**.

Au minimum, \(T\) ordonne les situations.

Une structure temporelle métrique ou continue n’est pas universellement imposée.

---

## 6.2. État et situation

L’état global à l’instant \(t\) est :

\[
X(t)\in\Gamma_M,
\]

et une situation est :

\[
\boxed{
\Xi=(t,X)\in\Sigma_M\subseteq T\times\Gamma_M.
}
\]

**RETENU**.

L’état doit être suffisamment complet pour contenir toute information encore pertinente pour l’évolution endogène future.

Si deux situations possédant le même \(X\) et les mêmes paramètres ont des futurs endogènes différents, alors soit :

- l’état est incomplet ;
- une variable pertinente manque ;
- la loi dynamique est incorrectement formulée.

---

## 6.3. Temps continu sectoriel

Lorsqu’un secteur dispose d’un paramétrage temporel réel :

\[
 t\in I\subseteq\mathbb R,
\]

et d’une trajectoire suffisamment régulière, les outils classiques de la cinématique différentielle deviennent applicables.

Cette spécialisation est :

**CANDIDAT sectoriel**.

Le simple ordre de \(T\) ne suffit pas à justifier des dérivées.

---

# 7. CorpsMakolo et états physiques

## 7.1. CorpsMakolo

Un CorpsMakolo est représenté au minimum par :

\[
\boxed{
B=(Id_B,Q_B,\sigma_B)
}
\]

où :

- \(Id_B\) est son identité ;
- \(Q_B\) sa configuration ;
- \(\sigma_B\) son état interne.

**RETENU**.

La distinction :

\[
\boxed{
Identité
\neq
Configuration
\neq
ÉtatInterne
}
\]

est **RETENU**.

---

## 7.2. Localisation d’un Corps

La localisation est une composante possible de la configuration :

\[
Loc_B:Q_B\rightharpoonup\mathcal P_M.
\]

Lorsqu’elle est définie :

\[
 p_B(t)=Loc_B(Q_B(t)).
\]

Un Corps n’est pas réduit à son PointMakolo.

\[
\boxed{B\neq p_B}
\]

**RETENU**.

---

## 7.3. Correspondances sectorielles

Dans le secteur actuellement étudié :

\[
Profile\leftrightarrow VéhiculeMakolo,
\]

\[
Occurrence\leftrightarrow PlanèteMakolo,
\]

\[
Activity\leftrightarrow SystèmeMakolo.
\]

Ces correspondances sont **RETENU** comme vocabulaire sectoriel de l’Univers.

Elles n’importent aucune gravitation, masse, rigidité ou mécanique planétaire par analogie nominale.

---

# 8. Relations et destination

## 8.1. Relations physiques

Une relation peut porter sur plusieurs Corps :

\[
R(B_1,\ldots,B_n).
\]

Elle peut avoir un état propre lorsque le secteur l’exige.

**RETENU**.

Une relation n’est pas automatiquement une force, une distance ou un champ.

---

## 8.2. Destination active

La destination active est une relation :

\[
R_D(t)\subseteq\mathcal V\times\mathcal O.
\]

**RETENU**.

Elle satisfait :

\[
\boxed{
\forall V,t,
\quad
|\{O:(V,O)\in R_D(t)\}|\le1.
}
\]

**RETENU**.

Elle est donc le graphe d’une fonction partielle :

\[
\boxed{
D_t:\mathcal V\rightharpoonup\mathcal O.
}
\]

Cette unicité est une **contrainte structurelle sectorielle**.

Elle n’implique :

- ni attraction ;
- ni persistance ;
- ni loi de changement ;
- ni force.

La loi gouvernant l’évolution temporelle de \(D_t\) reste :

**À DÉTERMINER**.

---

# 9. Cinématique interne

## 9.1. Mouvement

Pour un Corps localisable :

\[
\gamma_B:t\mapsto p_B(t).
\]

Il y a déplacement positionnel lorsque :

\[
 p_B(t_1)\neq p_B(t_2).
\]

Dans le secteur complet :

\[
\Delta p_B
=
(\Delta g_B,\Delta i_B).
\]

**RETENU**.

Le changement de \(\sigma_B\) n’est pas nécessairement un déplacement.

**RETENU**.

---

## 9.2. Vitesse et accélération conditionnelles

Dans un secteur où :

- le temps est paramétré par un réel ;
- \(p_B(t)\) est différentiable ;

on définit :

\[
\boxed{
\mathbf v_B(t)
=
\dot p_B(t)
=
(\dot g_B,\dot i_B)
}
\]

et :

\[
\boxed{
\mathbf a_B(t)
=
\ddot p_B(t).
}
\]

Sous la géométrie euclidienne :

\[
\boxed{
 v_B(t)
=
\|\mathbf v_B(t)\|_M
=
\sqrt{\dot g_B^2+\dot i_B^2}.
}
\]

Ces définitions sont des transpositions directes de la cinématique classique.

Elles ne constituent pas une loi dynamique.

---

## 9.3. Longueur de trajectoire

Pour une trajectoire régulière :

\[
\boxed{
L[\gamma]
=
\int
\sqrt{
\left(\frac{dg}{dt}\right)^2
+
\left(\frac{di}{dt}\right)^2
}
\,dt.
}
\]

**RETENU conditionnellement aux hypothèses de régularité et de temps continu sectoriel**.

---

# 10. Dynamique générale

## 10.1. Architecture relationnelle

La dynamique endogène générale est représentée par :

\[
\boxed{
\mathcal D:
\Sigma_M\times\Lambda_M
\rightarrow
\mathcal P(\Sigma_M).
}
\]

**RETENU**.

La relation de transition est :

\[
\boxed{
\Xi\rightsquigarrow\Xi'
\iff
\Xi'\in\mathcal D(\Xi;\Lambda).
}
\]

**RETENU**.

Cette architecture est plus générale qu’une équation différentielle unique.

---

## 10.2. Admissibilité et réalisation

Une continuation admissible n’est pas nécessairement la continuation effectivement réalisée.

\[
\boxed{
admissible\neq réalisé
}
\]

**RETENU**.

Une histoire réalisée est une application :

\[
\mathcal H:t\mapsto X(t).
\]

Elle ne définit pas à elle seule la loi qui a rendu cette histoire admissible.

---

## 10.3. Endogène et exogène

On distingue :

\[
\boxed{
information\ exogène
\neq
intervention\ exogène.
}
\]

**RETENU**.

Une information peut modifier une estimation de l’état sans modifier l’état physique.

Une intervention réelle peut produire :

\[
X^-\xrightarrow{ext}X^+.
\]

Une transition véritablement exogène ne réfute pas automatiquement une loi endogène.

---

## 10.4. Première loi dynamique

Aucune première loi dynamique concrète \(L_1\) n’est actuellement établie.

Les candidats H1-v1, H2-v1 et H3-v1 restent :

**CANDIDAT**.

\[
\boxed{L_1\text{ reste À DÉTERMINER}.}
\]

Cela ne fragilise pas la géométrie constitutive du modèle : géométrie et loi dynamique sont des niveaux distincts.

---

# 11. Composition et systèmes

## 11.1. Corps composite et SystèmeMakolo

Un Corps composite et un SystèmeMakolo sont distincts.

**RETENU**.

Un SystèmeMakolo est défini relativement à un phénomène et à une frontière de modélisation.

On distingue :

- identité du système ;
- composition ;
- état ;
- frontière.

L’état du système ne se réduit pas nécessairement à la somme des états de ses parties.

\[
\boxed{
X_{\mathscr S}
\neq
\sum_B X_B.
}
\]

**RETENU**.

---

## 11.2. Bilans

Un bilan différentiel ne devient applicable que si le secteur définit réellement :

- une quantité \(K\) ;
- une règle de composition ;
- une structure temporelle différentiable ;
- une frontière ;
- un flux ;
- une source ou un puits.

Sous ces hypothèses, une relation du type :

\[
\frac{dK_{\mathscr S}}{dt}
=
-\mathcal F_K(\partial\mathscr S)
+
S_K
\]

peut être transposée depuis la théorie classique des systèmes ouverts.

Aucun \(K\) universel n’est actuellement établi.

Aucune masse ou énergie n’est introduite uniquement pour remplir cette équation.

---

# 12. Symétries, invariants et conservations

## 12.1. Symétries géométriques

La géométrie euclidienne interne possède son groupe d’isométries mathématiques.

Ces transformations préservent la métrique interne.

Elles ne sont pas automatiquement des symétries de la dynamique physique de Makolo.

Une symétrie dynamique doit préserver les lois :

\[
S\circ Evolution
=
Evolution\circ S.
\]

**RETENU comme critère**.

---

## 12.2. Invariants structurels

L’unicité de destination :

\[
|\{O:(V,O)\in R_D(t)\}|\le1
\]

est un invariant structurel sectoriel des états admissibles.

**RETENU**.

Elle n’est pas une quantité conservée au sens mécanique.

Aucune énergie, masse ou quantité de mouvement Makolo universelle n’est actuellement dérivée.

---

## 12.3. Noether

Le théorème de Noether reste disponible comme science établie :

\[
\text{symétrie continue d’une action}
\Rightarrow
\text{quantité conservée}
\]

sous les hypothèses usuelles.

Mais aucune action universelle Makolo n’est actuellement définie.

L’application de Noether reste donc :

**À DÉTERMINER sectoriellement**.

---

# 13. Principe de transposition scientifique

La méthode de travail générale est :

\[
\boxed{
\text{appliquer}
>
\text{adapter}
>
\text{composer}
>
\text{inventer en dernier recours}
}
\]

**RETENU**.

Pour toute structure Makolo :

1. identifier précisément sa forme mathématique ;
2. rechercher le cadre scientifique établi correspondant ;
3. expliciter les hypothèses de ce cadre ;
4. vérifier lesquelles sont satisfaites ;
5. transférer directement les résultats valides ;
6. n’adapter que ce qui diffère ;
7. n’introduire une structure nouvelle qu’après insuffisance démontrée des cadres pertinents.

Ainsi :

- un plan euclidien utilise la géométrie euclidienne ;
- une trajectoire différentiable utilise le calcul différentiel ;
- un secteur lagrangien utiliserait Euler-Lagrange ;
- un secteur hamiltonien utiliserait Hamilton ;
- une action symétrique utiliserait Noether.

Aucun de ces cadres n’est rebaptisé artificiellement « version Makolo ».

---

# 14. Ce que la géométrie signifie — et ne signifie pas

## 14.1. Signification positive

La géométrie fournit une structure interne pour comparer des positions et des déplacements.

Elle répond à des questions du type :

- deux loci internes sont-ils identiques ?
- quel est leur vecteur de séparation dans le secteur complet ?
- quelle est leur distance interne ?
- une trajectoire est-elle continue ou régulière dans un secteur approprié ?
- quelle longueur interne possède cette trajectoire ?

---

## 14.2. Absence de sémantique humaine directe

La géométrie ne répond pas, à elle seule, à :

- « est-ce facile ? » ;
- « est-ce souhaitable ? » ;
- « est-ce accessible à cette personne ? » ;
- « est-ce une meilleure possibilité ? » ;
- « combien d’effort humain cela exige ? ».

Une grande distance interne peut être favorable dans un contexte et défavorable dans un autre.

Une petite distance interne peut être sans intérêt ou inaccessible.

La théorie géométrique demeure donc **descriptive de structure**, et non normative.

---

# 15. État consolidé des neuf dimensions

| Dimension | État actuel | Statut principal |
|---|---|---|
| Arène | \(T,\Gamma_M,\Sigma_M\) | `RETENU` |
| Objets | Corps, relations, systèmes | `RETENU` |
| États | \(Id,Q,\sigma\), état global complet relativement à l’endogène | `RETENU` |
| Géométrie | espace stratifié ; secteur complet affine euclidien | `RETENU` pour la structure constitutive |
| Projections | \(E_G\), \(E_I\) comme réalisations concrètes | `CANDIDAT` |
| Symétries | isométries géométriques connues ; symétries dynamiques ouvertes | `RETENU` géométrique / `À DÉTERMINER` dynamique |
| Dynamique | relation \(\mathcal D\) | `RETENU` |
| Lois concrètes | aucune \(L_1\) établie | `À DÉTERMINER` |
| Observables | états, relations, loci ; protocoles sectoriels à préciser | `RETENU` structurel / `À DÉTERMINER` opérationnel |
| Invariants | unicité sectorielle de destination ; invariants géométriques | `RETENU` |
| Conservations mécaniques | aucune universelle | `SANS ÉQUIVALENT` actuellement |
| Causalité/localité | influence dérivée ; aucune localité dynamique universelle | `À DÉTERMINER` |
| Composition | Corps composites et systèmes distingués | `RETENU` |

---

# 16. Théorèmes et conséquences mathématiques consolidés

## T1 — Chasles

Dans le secteur affine complet :

\[
\overrightarrow{AB}+\overrightarrow{BC}=\overrightarrow{AC}.
\]

## T2 — Pythagore

Dans la métrique euclidienne interne :

\[
\|\Delta p\|_M^2=(\Delta g)^2+(\Delta i)^2.
\]

## T3 — Invariance par translation

\[
 d_M(A+T,B+T)=d_M(A,B).
\]

## T4 — Invariance orthogonale

Pour \(R^TR=I\) :

\[
\|Rv\|_M=\|v\|_M.
\]

## T5 — Bornage de \(E_G\)

Sous son domaine déclaré :

\[
-180\le E_G(\lambda,\varphi)\le180.
\]

## T6 — Injectivité rationnelle de \(E_G\)

Sur le domaine rationnel déclaré, \(E_G\) est injective.

## T7 — Non-injectivité réelle de \(E_G\)

Sur \(\mathbb R^2\), \(E_G\) possède un noyau non trivial.

## T8 — Bornage de \(E_I\)

Sous \(|c_j|\le1\), \(|\tau|\le1\) :

\[
|E_I|<180.
\]

## T9 — Injectivité conditionnelle de \(E_I\)

Avec coefficients rationnels, séquence canonique unique, marqueur terminal rationnel non nul et \(\alpha=e^{-1}\), deux séquences distinctes ont des images distinctes.

---

# 17. Questions encore ouvertes

La théorie est maintenant suffisamment structurée pour isoler précisément ce qui reste ouvert.

## 17.1. Projection géographique

Le choix concret \(E_G\) satisfait compacité, bornage et injectivité sur le domaine rationnel déclaré.

Reste à déterminer si le contrat final exige également :

- préservation d’un voisinage ;
- stabilité sous certaines variations ;
- conservation d’un ordre ;
- autre propriété structurelle.

Aucune conservation exacte de la distance terrestre n’est requise par la théorie actuelle.

---

## 17.2. Projection logique

La construction polynomiale \(E_I\) reste incomplète tant que la fonction exacte :

\[
\text{nœud logique canonique}\mapsto c_j
\]

n’est pas fixée.

Cette définition doit être stable, déterministe, scheme-aware et indépendante du contexte utilisateur.

---

## 17.3. Temps

Il reste à déterminer quels secteurs disposent :

- d’un simple ordre ;
- d’une durée ;
- d’un paramètre réel ;
- d’une dynamique continue ;
- d’une dynamique discrète ;
- d’une combinaison hybride.

---

## 17.4. Lois dynamiques

La structure géométrique est désormais suffisamment indépendante pour que la recherche de lois ne nécessite pas de réinventer la géométrie.

En revanche, aucune loi universelle concrète ne doit être postulée sans phénomène correspondant.

Les prochaines lois devront être obtenues par transposition de cadres physiques établis lorsque leurs hypothèses sont effectivement présentes dans un secteur Makolo.

---

# 18. Statuts finaux proposés

| Élément | Statut proposé | Nature |
|---|---|---|
| séparation métier / backend / Univers | `RETENU` | principe d’architecture |
| \(p=(g,i)\) | `RETENU` | définition constitutive |
| \(g,i\in\mathbb R\) | `RETENU` | décision de représentation |
| \(\bot_G,\bot_I\neq0\) | `RETENU` | définition typée |
| espace stratifié \(\mathcal P_M\) | `RETENU` | dérivation structurelle |
| plan affine du secteur complet | `RETENU` | décision constitutive |
| produit scalaire euclidien interne | `RETENU` | décision constitutive |
| distance interne \(d_M\) | `RETENU` | définition dérivée |
| \(G\perp I\) et \(1G=1I\) | `RETENU` | conséquence de la métrique choisie |
| interprétation de \(d_M\) comme km/difficulté/effort | `SANS ÉQUIVALENT` | non impliquée |
| projection \(E_G\) | `CANDIDAT` | réalisation de projection |
| projection \(E_I\) | `CANDIDAT` | réalisation de projection |
| attribution exacte des \(c_j\) | `À DÉTERMINER` | projection logique |
| structure générale \(\mathcal D\) | `RETENU` | dynamique abstraite |
| H1/H2/H3 | `CANDIDAT` | lois candidates |
| \(L_1\) | `À DÉTERMINER` | loi dynamique |
| mécanique newtonienne universelle | `SANS ÉQUIVALENT` | non justifiée |
| masse/énergie/momentum universels | `SANS ÉQUIVALENT` | non dérivés |
| Lagrange/Hamilton/Noether sectoriels | `À DÉTERMINER` | transposition conditionnelle |

---

# 19. Conclusion

La clarification centrale de cette version est la suivante :

\[
\boxed{
\text{la géométrie Makolo est une structure interne du modèle,}
\text{ pas une copie de la géométrie des sources.}
}
\]

Le rôle des projections est de faire entrer des faits sources dans cette structure selon un contrat explicite. Une fois les coordonnées obtenues, la théorie travaille sur \(g\), \(i\), les Corps, les états et les relations de l’Univers Makolo.

Le plan euclidien complet est donc légitime comme **choix constitutif**, sans avoir à prouver que la Terre ou l’espace des URI sont eux-mêmes euclidiens au sens Makolo. Les projections \(E_G\) et \(E_I\), en revanche, restent des objets scientifiques à contrôler : stabilité, injectivité sur leur domaine, bornage et propriétés structurelles qu’elles prétendent préserver.

Cette distinction résout l’ambiguïté qui subsistait entre « valider Euclide par des données extérieures » et « choisir Euclide comme géométrie interne ». Dans la présente théorie, Euclide est la géométrie interne du secteur complet ; ce qui doit encore être étudié est la qualité des projections et la dynamique qui s’exerce dans cet espace.

La suite de la recherche peut ainsi utiliser les mathématiques et les physiques établies sans recommencer à zéro : géométrie euclidienne pour la structure spatiale interne, cinématique classique lorsque le temps et la régularité le permettent, puis cadres dynamiques établis seulement dans les secteurs où leurs hypothèses apparaissent réellement.

---

# Références normatives et scientifiques

1. T. Berners-Lee, R. Fielding, L. Masinter, **RFC 3986 — Uniform Resource Identifier (URI): Generic Syntax**, IETF, 2005.
2. National Geospatial-Intelligence Agency, **World Geodetic System 1984 (WGS 84)**, documentation officielle.
3. NOAA / National Geodetic Survey, documentation **INVERSE/FORWARD** pour les calculs géodésiques.
4. Résultats classiques de géométrie affine et euclidienne : espaces affines réels, produits scalaires, normes, isométries orthogonales et théorème de Pythagore.
5. Résultat classique de transcendance : \(e\) est transcendant ; par conséquent \(e^{-1}\) l’est également.
6. Corpus scientifique Makolo : socle consolidé, théorie unifiée corrigée, PointMakolo, rapport LAPM A–J, annexe d’audit et diff canonique proposé.
