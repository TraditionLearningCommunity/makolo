Oui. Et à ce stade je reformulerais la question générale un peu plus sévèrement :

$$
\boxed{
\text{Quel problème Makolo veut-il résoudre, et quelle représentation du monde est nécessaire pour le résoudre ?}
}
$$

Pas encore :

$$
\text{quel algorithme utiliser ?}
$$

Et même pas encore :

$$
\text{comment transformer les faits en masse, charge, température ?}
$$

La physique, les graphes, les règles, le ML, les agents doivent venir **après**.

---

# 1. Posons d'abord une hypothèse nulle

Il faut partir de :

> **Peut-être que l'Univers Makolo n'est pas nécessaire.**

Supposons qu'on puisse obtenir exactement le même résultat avec :

* Search ;
* recommender ;
* moteur de règles ;
* workflow ;
* graphe de connaissances ;
* planificateur ;
* solveur de contraintes ;
* calendrier ;
* agent logiciel.

Alors il faut utiliser ces moyens plus simples.

L'Univers Makolo n'est justifié que si le problème demande réellement quelque chose comme :

$$
\boxed{
\text{état persistant du monde}
+
\text{évolution}
+
\text{interactions}
+
\text{futurs accessibles}
+
\text{interventions}
}
$$

C'est notre test de falsification.

---

# 2. La meilleure candidate actuelle pour la différence Makolo

Je pense qu'elle n'est pas :

> « trouver les meilleures opportunités ».

Elle serait plutôt :

> **Maintenir une représentation dynamique de la situation réelle d'une personne et des systèmes avec lesquels elle est engagée, déterminer quelles évolutions restent réellement possibles, détecter ce qui peut modifier ces évolutions, puis accomplir ou préparer les transformations autorisées qui facilitent l'action réelle.**

En notation :

$$
X(t)
\longrightarrow
\mathcal R(X(t))
\longrightarrow
\text{perturbations}
\longrightarrow
\text{interventions possibles}.
$$

Le véritable objet calculé n'est donc peut-être ni le Profile ni l'Opportunity.

Il pourrait être :

$$
\boxed{\text{l'espace des futurs réalisables depuis la situation présente}}
$$

---

# 3. Question 1 — Quelle décision particulière Makolo doit-il pouvoir prendre ?

Le candidat le plus intéressant serait :

> **Déterminer ce qu'il faut faire — ou ne pas faire — maintenant pour préserver, ouvrir ou rendre exécutable une possibilité future réelle.**

Exemple.

Une formation dans quatre mois est intéressante.

Un recommender peut dire :

> « cette formation correspond à votre profil ».

Un moteur de règles peut dire :

> « vous satisfaites 8 critères sur 10 ».

Un workflow peut montrer :

> « étape 4 sur 9 ».

Makolo devrait pouvoir arriver à quelque chose comme :

> « La formation est actuellement réalisable. Le seul élément susceptible de bloquer le départ est une démarche médicale dont la fenêtre de réalisation ferme avant celle du visa. Le visa ne nécessite aucune action maintenant. Le document financier déjà utilisé l'an dernier peut être réutilisé. La seule action utile cette semaine est donc le rendez-vous médical. »

Cela exige de raisonner simultanément sur plusieurs systèmes.

Mais attention :

### ce n'est pas encore la preuve que la physique est nécessaire.

Un bon planificateur causal pourrait également le faire.

C'est précisément ce qu'il faudra tester.

---

# 4. Question 2 — Quel système évolue ?

Je ne pense plus que la réponse soit :

$$
\boxed{\text{le Profile}}
$$

Le Profile seul est trop petit.

Et :

$$
\boxed{\text{tout l'Univers Makolo}}
$$

est trop grand.

La bonne unité pourrait être un **système d'intérêt dynamiquement délimité**.

Par exemple :

$$
\mathcal S=
\{
P,
J_{\rm visa},
J_{\rm soins},
Y_{\rm voyage},
A_{\rm formation},
Access,
Capacity,
E_{\rm pertinent}
\}.
$$

La frontière du système dépend de la question.

Pour :

> « Puis-je suivre cette formation ? »

nous incluons ce qui peut effectivement modifier cette possibilité.

Nous n'incluons pas toutes les activités de Makolo.

Donc :

$$
\boxed{
\text{système pertinent}
=
\text{corps et variables capables d'influencer le problème étudié}
}
$$

C'est très proche d'une fermeture causale locale.

---

# 5. Cela donne une idée fondamentale : Makolo ne devrait pas simuler « tout »

Makolo ne doit pas construire une copie intégrale du monde à chaque décision.

À partir d'une question ou d'une trajectoire active, il faut déterminer le sous-système causalement pertinent.

$$
\mathcal U
\supset
\mathcal S_{\rm pertinent}.
$$

Cela permettrait justement de ne pas tomber dans une simulation impossible.

---

# 6. Question 3 — Qu'est-ce qu'un état minimal suffisant ?

Nous pouvons emprunter ici une notion très solide aux systèmes dynamiques.

Un état est suffisant si, pour la question considérée, connaître cet état rend l'histoire plus ancienne inutile pour calculer la suite, sauf ce qui est déjà résumé dans l'état.

Schématiquement :

$$
X_t
$$

doit contenir ce qui est nécessaire pour calculer :

$$
X_{t+\Delta t}
$$

ou les distributions/possibilités futures.

L'idée est :

$$
\boxed{
\text{état}
=
\text{mémoire minimale suffisante du système}
}
$$

Pas :

$$
\text{toutes les données disponibles}.
$$

C'est extrêmement important pour Makolo.

---

# 7. Exemple

Pour déterminer si quelqu'un peut prendre un vol demain, nous pouvons avoir besoin de :

* localisation ;
* billet ;
* droit d'accès ;
* état du vol ;
* disponibilité temporelle ;
* document nécessaire.

Nous n'avons probablement pas besoin :

* de sa photo de profil ;
* du texte de sa bio ;
* des anciennes activités sans rapport ;
* de son nombre de relations.

Ces informations peuvent être vraies tout en étant dynamiquement inutiles.

---

# 8. Question 4 — Quelle trajectoire intéresse réellement Makolo ?

Je ne choisirais pas une seule.

Il faut en distinguer au moins quatre.

### Trajectoire réalisée

$$
\Gamma_{\rm réel}
$$

Ce qui s'est effectivement produit.

### Trajectoire prévue

$$
\widehat{\Gamma}
$$

Ce que Makolo estime susceptible de se produire.

### Ensemble des trajectoires admissibles

$$
\mathcal T(X_0)
$$

Tout ce qui peut se produire depuis l'état actuel sous les contraintes considérées.

### Trajectoires contrôlables

$$
\mathcal T_u(X_0)
$$

Celles qu'une intervention autorisée peut rendre possibles ou modifier.

Pour le produit, je pense que les deux dernières sont les plus intéressantes.

Makolo ne doit pas seulement demander :

> « Que va-t-il arriver ? »

mais :

$$
\boxed{
\text{Qu'est-ce qui peut encore arriver ?}
}
$$

et :

$$
\boxed{
\text{Que pouvons-nous encore changer ?}
}
$$

---

# 9. Question 5 — Qu'est-ce qu'un état accessible ?

Il faut effectivement refuser un simple booléen « possible/impossible ».

Un état peut être :

* physiquement possible ;
* temporellement possible ;
* administrativement admissible ;
* juridiquement permis ;
* accessible au regard des droits ;
* compatible avec les capacités disponibles ;
* compatible avec les ressources ;
* causalement atteignable.

L'état réellement exécutable doit satisfaire **l'ensemble des contraintes nécessaires**.

On pourrait écrire :

$$
X_f\in
\mathcal R_{\rm phys}
\cap
\mathcal R_{\rm temps}
\cap
\mathcal R_{\rm access}
\cap
\mathcal R_{\rm capacité}
\cap
\mathcal R_{\rm exigences}
\cap\cdots
$$

Il ne s'agit pas d'un score.

Il faut qu'il existe au moins un chemin admissible.

$$
\boxed{
X_f\text{ est exécutable}
\iff
\exists\Gamma:X_0\rightsquigarrow X_f
}
$$

satisfaisant toutes les contraintes applicables.

---

# 10. C'est très différent d'« éligible »

Une personne pourrait être éligible à une formation mais :

* inscription fermée ;
* aucun siège ;
* passeport expiré ;
* chevauchement avec une intervention médicale obligatoire ;
* absence du droit nécessaire.

Donc :

$$
\boxed{
\text{éligible}
\neq
\text{atteignable}
\neq
\text{exécutable}
}
$$

Cette distinction pourrait être très importante pour Makolo.

---

# 11. Question 6 — Qu'est-ce qui modifie réellement une trajectoire ?

Il faut utiliser un critère causal.

Une variable \(A\) n'est pas pertinente simplement parce qu'elle est associée à \(B\).

Elle devient dynamiquement importante si une modification réelle de \(A\) peut modifier :

$$
X_B(t+\Delta t)
$$

ou :

$$
\mathcal R_B(X).
$$

Autrement dit :

$$
\boxed{
A\text{ compte dynamiquement}
\iff
\operatorname{do}(A)
\text{ peut modifier l'évolution pertinente}
}
$$

conceptuellement.

---

# 12. Exemple du document

Le PDF du passeport enregistré dans Drive n'est pas nécessairement causal.

Mais :

> « passeport valide »

peut l'être si la règle d'accès exige un passeport valide.

Et :

> « Makolo connaît l'existence du passeport »

est encore autre chose.

Nous avons donc trois niveaux :

$$
\boxed{
\text{réalité}
\neq
\text{preuve de la réalité}
\neq
\text{connaissance par Makolo}
}
$$

C'est essentiel.

---

# 13. Question 7 — Qu'est-ce qu'un blocage ?

Voici une définition que je trouve beaucoup plus solide :

> **Un blocage relatif à un état cible est une condition ou un ensemble de conditions qui empêche actuellement l'existence d'une trajectoire admissible vers cet état.**

Si :

$$
X_f\notin\mathcal R(X_0),
$$

il y a blocage relativement à \(X_f\).

Mais on veut surtout trouver :

$$
C^\*
$$

l'ensemble minimal de contraintes qu'il faudrait transformer pour obtenir :

$$
X_f\in\mathcal R(X_1).
$$

C'est beaucoup plus utile que :

> « votre dossier est bloqué ».

Makolo devrait pouvoir dire :

> **« exactement ceci empêche actuellement la suite ».**

---

# 14. Il existe différents blocages

Il faudrait probablement distinguer :

* blocage dur ;
* blocage temporaire ;
* blocage transformable ;
* blocage externe ;
* blocage par capacité ;
* blocage par dépendance ;
* blocage par autorité ;
* blocage seulement apparent parce que Makolo manque d'information.

Ce dernier est particulièrement important.

$$
\boxed{
\text{Makolo ne sait pas qu'un chemin existe}
\neq
\text{aucun chemin n'existe}
}
$$

---

# 15. Question 8 — Qu'est-ce qu'une intervention Makolo ?

Je proposerais :

> **Une intervention est une action autorisée dont l'exécution modifie effectivement l'état du système ou les conditions gouvernant ses transitions futures.**

$$
u:
X_0\rightarrow X_1.
$$

Exemples possibles :

* effectuer une réservation autorisée ;
* soumettre un élément ;
* récupérer une preuve ;
* préparer un formulaire ;
* demander une information ;
* sélectionner un créneau ;
* coordonner deux acteurs ;
* déclencher une démarche autorisée.

Une notification, prise isolément, n'est pas nécessairement une intervention.

Mais une information peut devenir une **intervention informationnelle** si sa réception modifie réellement le système décisionnel humain. Il faudra traiter ce cas séparément plutôt que dire que toutes les notifications sont des interventions.

---

# 16. Question 9 — Comment plusieurs trajectoires interagissent-elles ?

Nous avons déjà un excellent exemple :

$$
\Gamma_{\rm visa},
\Gamma_{\rm soins},
\Gamma_{\rm travail},
\Gamma_{\rm voyage},
\Gamma_{\rm formation}.
$$

Elles ne doivent surtout pas devenir :

$$
\text{score global}=68\%.
$$

Leur interaction peut prendre plusieurs formes :

### Prérequis

$$
A\rightarrow B
$$

A doit atteindre un certain état avant B.

### Ressource commune

A et B utilisent la même ressource.

### Exclusion temporelle

$$
A@t
$$

empêche :

$$
B@t.
$$

### Facilitation

A rend certains états de B accessibles.

### Blocage

A ferme une trajectoire de B.

### Synchronisation

A et B doivent atteindre certains états dans une fenêtre commune.

C'est du **couplage de trajectoires**, pas de l'agrégation de scores.

---

# 17. Question 10 — Quelle information ne doit pas entrer dans l'état ?

La réponse théorique est élégante :

> **Toute information dont la suppression ne change ni la dynamique pertinente, ni l'accessibilité, ni la décision d'intervention, pour le problème considéré.**

Cela peut être formalisé comme une forme d'indépendance conditionnelle.

Si deux situations :

$$
X_A
$$

et :

$$
X_B
$$

diffèrent sur une donnée \(z\), mais produisent exactement :

* les mêmes futurs pertinents ;
* les mêmes contraintes ;
* les mêmes actions possibles ;

alors \(z\) n'a probablement pas besoin d'être une variable d'état pour ce problème.

Elle peut rester un fait du backend sans entrer dans l'état dynamique.

---

# 18. Question 11 — Observation et état réel

C'est absolument central.

Le monde possède :

$$
X_t.
$$

Makolo reçoit des observations :

$$
Y_t.
$$

Et en déduit :

$$
\widehat X_t.
$$

Donc :

$$
\boxed{
X_t\neq Y_t\neq\widehat X_t.
}
$$

Exemple :

réalité :

> passeport expiré.

Observation ancienne dans Makolo :

> passeport valide il y a six mois.

Estimation erronée :

> probablement valide.

Le moteur ne doit jamais confondre ces niveaux.

---

# 19. Il faudra donc probablement gérer l'incertitude explicitement

Un état estimé peut être accompagné de :

* source ;
* date ;
* qualité ;
* confiance ;
* fraîcheur ;
* contradiction éventuelle.

Mais cela reste **l'épistémologie de Makolo**, pas l'état physique lui-même.

---

# 20. Question 12 — Quand une différence d'état est-elle utile ?

Excellent filtre.

Deux états physiquement distincts peuvent être **opérationnellement équivalents**.

Si :

$$
X_A\neq X_B
$$

mais qu'ils impliquent :

$$
\mathcal R(X_A)=\mathcal R(X_B)
$$

et les mêmes interventions utiles,

alors Makolo n'a peut-être pas besoin d'exposer la différence à l'utilisateur.

Nous pouvons définir une équivalence opérationnelle :

$$
X_A\sim X_B
$$

lorsqu'ils conduisent aux mêmes conséquences pertinentes pour l'action considérée.

C'est extrêmement utile pour éviter de « calculer pour calculer ».

---

# 21. Question 13 — Qu'est-ce qu'une bifurcation importante ?

Pas simplement :

> deux trajectoires deviennent différentes.

Une bifurcation devient importante pour Makolo lorsqu'elle modifie qualitativement :

* les futurs accessibles ;
* les actions requises ;
* les ressources nécessaires ;
* le temps disponible ;
* les droits ;
* les risques ;
* ou l'effort futur demandé à la personne.

Schématiquement :

$$
\mathcal R_A\neq\mathcal R_B.
$$

Une toute petite différence interne sans conséquence pratique peut être ignorée.

Une petite modification qui ferme une possibilité majeure doit être détectée.

---

# 22. Question 14 — Que signifie « préparer » ?

Je modifierais légèrement notre première formule.

Préparer ne signifie pas nécessairement :

$$
\mathcal R(X_1)\supset\mathcal R(X_0).
$$

Parfois une bonne préparation **réduit volontairement** certaines possibilités dangereuses ou incompatibles.

Je proposerais :

> **Préparer consiste à effectuer maintenant une transformation autorisée qui améliore les conditions d'exécution d'une trajectoire future pertinente, réduit l'effort ou l'incertitude future, élimine un blocage, protège une possibilité ou place le système dans un état où la prochaine action nécessaire sera immédiatement exécutable.**

On peut avoir :

$$
X_0\xrightarrow{u_{\rm prep}}X_1.
$$

L'effet recherché peut être :

$$
P(X_f\text{ atteignable}\mid X_1)
>
P(X_f\text{ atteignable}\mid X_0),
$$

si le modèle est probabiliste,

ou simplement :

$$
X_f\notin\mathcal R(X_0)
\quad\rightarrow\quad
X_f\in\mathcal R(X_1).
$$

---

# 23. « Préparer » peut aussi signifier préserver

Très important.

Supposons :

$$
X_f\in\mathcal R(X_0)
$$

aujourd'hui.

Mais une fenêtre ferme demain.

Une action peut empêcher :

$$
X_f\notin\mathcal R(X_{demain}).
$$

Donc préparer peut vouloir dire :

$$
\boxed{
\text{empêcher la disparition d'une trajectoire actuellement accessible}
}
$$

et pas seulement en créer une nouvelle.

---

# 24. Question 15 — Comment prouver que l'Univers Makolo sert réellement ?

C'est probablement notre prochain chantier expérimental.

Il faut construire une batterie de situations.

Pas des exemples conçus pour faire gagner Makolo.

Des **crash-tests adversariaux**.

Pour chaque scénario, on donne les mêmes faits à plusieurs architectures conceptuelles :

1. Search ;
2. Recommendation ;
3. Rules ;
4. Workflow ;
5. Constraint solver / planner ;
6. Knowledge graph ;
7. agent avec outils ;
8. Univers Makolo.

Puis on demande exactement la même sortie.

---

# 25. Les scénarios doivent casser les solutions naïves

Par exemple :

### A. Opportunity pertinente mais inaccessible

Le ranking doit échouer.

### B. Opportunity inconnue mais trajectoire soudainement ouverte

L'historique de préférence ne suffit pas.

### C. Événement non intéressant mais causalement perturbateur

La similarité sémantique échoue.

### D. Deux démarches valides séparément mais incompatibles ensemble

Le traitement objet-par-objet échoue.

### E. Changement externe qui ferme une trajectoire déjà préparée

Le workflow statique devient insuffisant.

### F. Une ancienne preuve rend une nouvelle démarche immédiatement plus facile

Il faut capitaliser l'action passée.

### G. Une information manquante fait croire à tort à un blocage

Il faut distinguer état réel et connaissance.

### H. Makolo peut agir maintenant avant que l'utilisateur demande quoi que ce soit

Il faut montrer la valeur de la préparation.

---

# 26. Et il faut être prêt à ce qu'un planner classique gagne

C'est important scientifiquement.

Supposons qu'un :

$$
\text{graphe causal}
+
\text{solveur de contraintes}
+
\text{planificateur}
$$

résolve parfaitement tous les scénarios.

Alors notre conclusion doit être :

> **Nous n'avons pas encore démontré la nécessité d'une physique Makolo.**

Pas :

> « trouvons quand même une manière d'utiliser masse et charge ».

Ce serait exactement le contraire de notre méthode.

---

# 27. Il y a cependant une possibilité intéressante

Peut-être que la valeur ne résidera pas dans **un algorithme nouveau**.

Elle peut résider dans **l'objet calculé**.

Un moteur de recherche est organisé autour de documents/items.

Un recommender autour de :

$$
(\text{user},\text{item}).
$$

Un workflow autour d'un processus prédéfini.

Un rule engine autour de conditions.

Un planificateur autour d'un état, d'actions et d'un objectif.

Makolo pourrait être organisé de manière permanente autour de :

$$
\boxed{
\text{situation dynamique réelle d'une personne}
+
\text{réseau d'actions}
+
\text{systèmes externes}
+
\text{futurs accessibles}
}
$$

Ce serait peut-être sa vraie architecture distinctive.

Pas nécessairement un algorithme mystérieux.

---

# 28. Et il existe encore une question plus profonde

Notre question :

> « Qu'est-ce que Makolo doit être capable de faire que les systèmes actuels ne font pas ? »

peut être améliorée.

Parce qu'un système suffisamment programmable peut, en théorie, presque toujours être étendu pour faire quelque chose.

La question plus solide est :

$$
\boxed{
\text{Quel objet Makolo doit-il représenter nativement pour résoudre correctement son problème ?}
}
$$

C'est différent.

On ne demande plus :

> « est-ce techniquement impossible ailleurs ? »

mais :

> « quelle représentation rend ce raisonnement naturel, cohérent, généralisable et maintenable ? »

---

# 29. Ma candidate actuelle

Je la formulerais comme ceci :

> **L'objet central de Makolo est une situation d'action dynamique : un système composé d'une personne, de ses démarches et engagements pertinents, des réalités externes capables de les affecter, de leurs états présents et des transitions encore accessibles.**

Makolo cherche à déterminer :

$$
\boxed{
(X,\mathcal T,\mathcal R,U)
}
$$

où :

* \(X\) = état actuel ;
* \(\mathcal T\) = trajectoires admissibles ;
* \(\mathcal R\) = états accessibles ;
* \(U\) = interventions autorisées.

Puis :

$$
\boxed{
\text{quoi faire maintenant ?}
}
$$

peut être dérivé de cette structure.

---

# 30. Cela donne peut-être notre vrai « contrat d'utilité »

Je proposerais provisoirement :

> **Makolo doit être capable de maintenir une représentation suffisante de la situation réelle d'une personne, de déterminer les évolutions encore accessibles à partir de cette situation, d'identifier les changements internes ou externes capables de modifier ces évolutions, et d'exécuter ou préparer les interventions autorisées qui réduisent le travail nécessaire pour accomplir une action réelle.**

Cela est beaucoup plus précis que :

> « recommander des opportunités ».

---

# 31. Et je poserais désormais cinq questions avant toute nouvelle capacité

Avant d'introduire une grandeur, un modèle ou un algorithme :

$$
\boxed{1.\ \text{Quel système étudions-nous ?}}
$$

$$
\boxed{2.\ \text{Quel état devons-nous connaître ?}}
$$

$$
\boxed{3.\ \text{Quelle évolution voulons-nous déterminer ?}}
$$

$$
\boxed{4.\ \text{Quelle décision ou intervention dépend de ce calcul ?}}
$$

$$
\boxed{5.\ \text{Pourquoi une solution plus simple ne suffit-elle pas ?}}
$$

Si nous ne pouvons pas répondre aux cinq, nous ne modélisons pas encore.

---

## Là où je pense que nous devons poursuivre

Le prochain pas ne devrait même pas être de résoudre abstraitement les 15 questions une par une.

Il faudrait prendre **un premier cas réel complet** — par exemple *formation à l'étranger + voyage + visa + documents + capacité + changement extérieur* — et construire successivement :

$$
\boxed{Système}
$$

$$
\downarrow
$$

$$
\boxed{État minimal}
$$

$$
\downarrow
$$

$$
\boxed{Transitions}
$$

$$
\downarrow
$$

$$
\boxed{Trajectoires admissibles}
$$

$$
\downarrow
$$

$$
\boxed{Blocages}
$$

$$
\downarrow
$$

$$
\boxed{Interventions}
$$

$$
\downarrow
$$

$$
\boxed{\text{Décision utile pour la personne}}
$$

puis seulement faire entrer en face :

$$
\text{Search / Rules / Workflow / Planner / Agent / Univers Makolo}
$$

et voir **où se trouve réellement la différence**.

C'est ce test qui nous dira ensuite si nous avons besoin de masse, charge, champs et dynamique physique — ou si nous étions en train d'essayer de résoudre avec de la physique un problème qui appartient en réalité à la planification et aux contraintes.


Oui. Alors faisons le test de manière sévère : **on ne cherche pas à prouver Makolo ; on cherche ce qui résiste quand on casse les solutions simples**.

# 1. Protocole du crash-test

Pour chaque situation, on impose la même question :

$$
\boxed{\text{Que faut-il comprendre ou faire maintenant ?}}
$$

Puis on vérifie si la réponse peut être obtenue avec seulement :

* recherche ;
* recommandation ;
* règles ;
* workflow ;
* calendrier ;
* graphe de dépendances ;
* planification/contraintes ;
* agent exécutant des actions.

Et surtout on observe **quelle information supplémentaire devient indispensable**.

Le test est réussi seulement s’il fait émerger une structure nécessaire.

---

# TEST A — L’opportunité idéale qui n’est pas réellement accessible

### Situation

Une formation à Nairobi correspond parfaitement au Profile.

Elle commence dans 45 jours.

Le Profile :

* a les qualifications ;
* a le budget ;
* a une place disponible dans la formation ;
* possède un passeport valide ;
* doit obtenir un visa ;
* doit fournir un certificat médical ;
* ne possède pas encore ce certificat ;
* le certificat ne peut être obtenu qu’après un examen ;
* le prochain examen disponible est dans 40 jours ;
* le traitement du visa exige ensuite au minimum 10 jours.

### Recherche

Trouve la formation.

### Recommender

Peut la classer très haut.

### Rules

Peut conclure :

> certificat médical manquant.

### Workflow

Peut montrer :

> étape 3 : certificat médical.

Mais aucune de ces conclusions ne suffit.

Le problème réel est :

$$
40+10>45.
$$

Donc même si chaque étape est individuellement réalisable :

$$
\boxed{\text{la trajectoire entière ne l'est plus}}
$$

dans la fenêtre disponible.

### Bonne conclusion Makolo

> Cette formation correspond à ton profil, mais elle n’est plus réalisable dans les conditions temporelles actuelles. Le blocage n’est pas simplement « certificat manquant » : il n’existe plus de séquence admissible permettant certificat → visa → départ avant le début de la formation.

### Ce que le test force

Il faut représenter :

$$
\boxed{\text{états + transitions + durées + ordre + fenêtre temporelle}}
$$

et calculer l’existence d’un chemin :

$$
X_0\rightsquigarrow X_f.
$$

Premier résultat :

$$
\boxed{\text{matching}\neq\text{reachability}}
$$

---

# TEST B — Toutes les règles passent, mais deux trajectoires entrent en collision

### Situation

Le même Profile possède :

* une intervention médicale importante vendredi ;
* un entretien professionnel vendredi ;
* un vol vendredi soir ;
* un document qui doit être remis physiquement avant le vol.

Chaque démarche, examinée séparément, est valide.

Le visa est bon.

Le billet est bon.

L’entretien est confirmé.

L’intervention médicale est confirmée.

Le document est prêt.

### Un workflow par démarche

Dit partout :

$$
\text{vert}.
$$

### Moteur de règles

Chaque règle isolée passe.

### Le problème

Les quatre trajectoires utilisent :

* la même personne ;
* le même temps ;
* parfois le même lieu ;
* éventuellement le même moyen de transport.

Il existe donc une contrainte commune.

Individuellement :

$$
\Gamma_1,\Gamma_2,\Gamma_3,\Gamma_4
$$

sont possibles.

Ensemble :

$$
\boxed{
\Gamma_1+\Gamma_2+\Gamma_3+\Gamma_4
}
$$

peuvent être impossibles.

### Ce que le test force

Il faut représenter :

$$
\boxed{\text{plusieurs trajectoires simultanées partageant des ressources}}
$$

avec notamment :

* temps ;
* personne ;
* capacité ;
* lieu lorsque pertinent ;
* ressources engagées ;
* dépendances.

Deuxième résultat :

$$
\boxed{
\text{possibilité locale}
\not\Rightarrow
\text{possibilité globale}
}
$$

---

# TEST C — Une chose sans intérêt devient importante

### Situation

Le Profile doit suivre une formation en ligne importante à 18 h.

Il ne s’intéresse absolument pas au match qui a lieu ailleurs.

Le match ne correspond :

* ni à ses intérêts ;
* ni à son historique ;
* ni à ses recherches.

Mais le match provoque localement une surcharge réseau suffisamment importante pour compromettre la connexion nécessaire à la formation.

### Recommender

Le match a pratiquement une pertinence nulle.

Il l’ignore.

### Search

Personne n’a cherché le match.

Il l’ignore également.

### Pourtant

Une chaîne causale existe :

$$
\text{match}
\rightarrow
\text{surcharge réseau}
\rightarrow
\text{qualité connexion}
\rightarrow
\text{formation}
$$

et donc :

$$
\text{match}
\rightarrow
\Gamma_{\rm formation}.
$$

### Bonne conclusion

Makolo n’a pas besoin de recommander le match.

Il doit éventuellement dire :

> La connexion risque d’être insuffisante pendant ta formation ; une alternative de connexion ou de lieu est utile avant 18 h.

### Ce que le test force

Il faut distinguer :

$$
\boxed{\text{pertinence sémantique}}
$$

de :

$$
\boxed{\text{pertinence causale}}
$$

Troisième résultat :

$$
\boxed{
\text{ce qui compte}
\neq
\text{ce qui m'intéresse}
}
$$

Une réalité compte lorsqu’elle peut modifier une trajectoire pertinente.

---

# TEST D — Le problème n’existe pas encore, mais Makolo doit agir maintenant

### Situation

Un billet est actuellement disponible.

Une place dans une formation est réservée pendant 48 heures.

Le Profile satisfait déjà toutes les conditions.

Il n’a rien demandé aujourd’hui.

Dans trois jours :

$$
Capacity=0.
$$

Si rien n’est fait, la trajectoire disparaît.

Aujourd’hui :

$$
X_f\in\mathcal R(X_0).
$$

Après expiration :

$$
X_f\notin\mathcal R(X_3).
$$

### Système réactif classique

Attend une requête :

> « Je veux m’inscrire. »

Mais il sera alors trop tard.

### Ce que Makolo devrait comprendre

L’état actuel comporte une possibilité qui va disparaître si aucune transformation n’a lieu.

Il y a donc une différence entre :

$$
\boxed{\text{résoudre un problème existant}}
$$

et :

$$
\boxed{\text{préserver une trajectoire encore ouverte}}
$$

### Bonne intervention

Selon l’autorité disponible :

* réserver ;
* préparer la réservation ;
* demander la confirmation nécessaire ;
* avertir seulement si une action humaine est indispensable.

### Ce que le test force

Il faut représenter :

$$
\boxed{
\text{fenêtres de validité}
+
\text{évolution future}
+
\text{interventions autorisées}
}
$$

Quatrième résultat :

> **Préparer peut signifier empêcher qu’un futur actuellement accessible cesse de l’être.**

---

# TEST E — Makolo croit qu’il y a un blocage, mais le monde dit le contraire

### Situation

Une démarche exige :

$$
R=\text{preuve d'identité valide}.
$$

Makolo ne retrouve pas de document correspondant.

Il conclut naïvement :

> preuve manquante.

Mais la personne possède réellement le document. Makolo ne le connaît simplement pas.

Nous avons :

### réalité

$$
X:\text{preuve existante}
$$

### observation Makolo

$$
Y:\text{aucune preuve retrouvée}
$$

### estimation

$$
\widehat X:\text{preuve probablement absente}.
$$

Ces trois objets sont différents.

### Mauvaise conclusion

> Vous devez obtenir une nouvelle preuve.

### Bonne conclusion

> Makolo ne dispose pas actuellement d’une preuve suffisante permettant de confirmer cette condition.

Ce n’est pas la même chose.

### Ce que le test force

Il faut absolument conserver :

$$
\boxed{
X\neq Y\neq\widehat X
}
$$

c’est-à-dire :

* monde ;
* observations ;
* représentation estimée.

Cinquième résultat :

$$
\boxed{
\text{inconnu}
\neq
\text{absent}
\neq
\text{faux}
}
$$

C’est un invariant majeur.

---

# TEST F — Une action passée ouvre un futur que personne ne cherchait

### Situation

Il y a six mois, la personne a réalisé une démarche qui a produit :

* une Proof ;
* une Credential ;
* une qualification reconnue.

Aujourd’hui apparaît une nouvelle formation.

La personne :

* ne la cherche pas ;
* ne suit pas le domaine explicitement ;
* n’a jamais exprimé de préférence correspondante.

Mais sa qualification antérieure signifie qu’elle peut accéder directement à un niveau avancé et éviter plusieurs démarches.

### Recommender

Peut ne rien voir.

### Search

Ne voit rien tant que la personne ne cherche pas.

### Makolo

Peut constater :

$$
X_{\rm passé}
\rightarrow
\text{capital d'action}
\rightarrow
X_{\rm futur}\text{ désormais accessible}.
$$

### Ce que le test force

Il faut que certaines transformations produisent des effets persistants réutilisables.

Donc :

$$
\boxed{
\text{histoire passée}
\rightarrow
\text{modification durable de l'état présent}
}
$$

Mais attention :

Makolo n’a pas besoin de conserver tout le passé dans son état.

Il doit conserver **ce que le passé a laissé de causalement pertinent aujourd’hui**.

C’est exactement le principe de l’état minimal suffisant.

---

# TEST G — Une même information ne doit pas produire la même décision pour tout le monde

### Situation

Une nouvelle règle de voyage apparaît.

Trois personnes :

### A

Aucun voyage prévu.

### B

Voyage prévu dans huit mois, aucune démarche urgente.

### C

Vol dans six jours et document affecté par la nouvelle règle.

La nouvelle règle est identique.

### Mauvais système

Envoie la même notification aux trois.

### Meilleur système

Pour A :

$$
\text{aucune conséquence opérationnelle actuelle}.
$$

Pour B :

$$
\text{éventuellement information à conserver}.
$$

Pour C :

$$
\boxed{\text{bifurcation immédiate de trajectoire}}
$$

avec action nécessaire.

### Ce que le test force

Une différence dans le monde devient importante relativement à :

$$
\boxed{
\text{l'état actuel du système qu'elle peut affecter}
}
$$

et non simplement parce que l’information est « pertinente ».

---

# TEST H — Une très petite modification produit une très grande conséquence

### Situation

Un dossier est entièrement prêt.

Une seule chose change :

$$
\text{heure limite}=17:00
$$

devient :

$$
16:00.
$$

Tout le reste de l’état est presque identique.

Pourtant le Profile n’arrive qu’à :

$$
16:30.
$$

Une toute petite différence de variable fait passer :

$$
X_f\in\mathcal R(X_0)
$$

à :

$$
X_f\notin\mathcal R(X_0).
$$

### Ce que le test force

Makolo ne peut pas mesurer l’importance d’une modification seulement par sa taille numérique.

Il faut regarder son effet sur :

$$
\boxed{\mathcal R(X)}
$$

l’espace des futurs accessibles.

C’est notre meilleure définition actuelle d’une **bifurcation opérationnellement importante**.

---

# Qu’est-ce qui sort de ces tests ?

Voilà le résultat intéressant.

Aucun test n’a encore forcé :

$$
m
$$

ou :

$$
q
$$

ou :

$$
T
$$

ou un champ physique particulier.

C’est très important.

En revanche, les tests forcent déjà huit structures.

---

## 1. Un état présent

Il faut pouvoir écrire :

$$
\boxed{X(t)}
$$

qui représente suffisamment la situation actuelle.

Pas toutes les données.

Seulement ce qui peut modifier les évolutions étudiées.

---

## 2. Des sous-systèmes distincts

Il ne faut surtout pas mettre tout dans le Profile.

Nous avons :

$$
X_P,\quad
X_{visa},\quad
X_{soins},\quad
X_{voyage},\quad
X_{formation},\ldots
$$

et un système composé lorsque nécessaire :

$$
\boxed{
X_{\mathcal S}
=
(X_1,X_2,\ldots,X_n,X_{\rm interactions})
}
$$

---

## 3. Des transitions

Il faut connaître :

$$
\boxed{
X_a\rightarrow X_b
}
$$

et les conditions permettant cette transformation.

C’est plus fondamental qu’un workflow fixe.

---

## 4. Des contraintes

Certaines transitions sont interdites ou deviennent impossibles selon :

* Requirements ;
* Access ;
* Capacity ;
* temps ;
* ressources ;
* autorités ;
* état d’autres systèmes.

Nous avons donc quelque chose comme :

$$
\boxed{\mathcal C(X,t)}
$$

l’ensemble des contraintes applicables.

---

## 5. Des dépendances causales

Il faut pouvoir savoir que :

$$
A\rightarrow B
$$

signifie réellement :

> une modification pertinente de \(A\) peut modifier l’évolution de \(B\).

Pas simplement :

> A et B sont reliés dans une base.

---

## 6. Un ensemble des états accessibles

C’est probablement l’un des objets les plus importants qui émerge :

$$
\boxed{
\mathcal R(X)
}
$$

et pas seulement une liste d’Opportunities.

Makolo veut savoir :

$$
\boxed{
\text{quels futurs restent atteignables depuis ici ?}
}
$$

---

## 7. Des interventions possibles

Nous avons besoin d’un ensemble :

$$
\boxed{
\mathcal U(X)
}
$$

contenant les actions réellement autorisées depuis l’état courant.

Par exemple :

$$
u_1=\text{préparer},
$$

$$
u_2=\text{réserver},
$$

$$
u_3=\text{demander},
$$

$$
u_4=\text{vérifier}.
$$

Et l’intervention transforme :

$$
X\xrightarrow{u}X'.
$$

---

## 8. Une couche de connaissance séparée

Il faut enfin :

$$
\boxed{
X,\quad Y,\quad\widehat X
}
$$

réalité, observations, estimation.

Sans cela Makolo fera des affirmations abusives sur le monde.

---

# Un résultat beaucoup plus profond apparaît

Regardons ce que Makolo semble réellement surveiller.

Pas principalement :

$$
\text{Opportunity}.
$$

Pas :

$$
\text{Profile}.
$$

Pas même :

$$
\text{Journey}.
$$

L’objet central semble être :

$$
\boxed{
\mathcal R(X)
}
$$

**l’espace des futurs encore réalisables à partir de la situation présente.**

Et ce qui compte maintenant est une chose capable de modifier cet espace.

On obtient alors une définition candidate extrêmement intéressante :

> **Une réalité est opérationnellement pertinente pour Makolo lorsqu’elle peut modifier de manière significative l’ensemble des états futurs accessibles ou les interventions actuellement nécessaires pour le système considéré.**

C’est beaucoup plus précis que :

> « pertinent pour moi ».

---

# Cela permet également de définir « maintenant »

Pourquoi quelque chose doit-il apparaître sur Home ?

Pas nécessairement parce que sa date est proche.

Mais parce que :

$$
\boxed{
\text{une action maintenant}
$$

est différente de :

$$
\boxed{
\text{la même action plus tard}.
}
$$

Par exemple :

$$
\mathcal R(X_{\rm après\,action\,maintenant})
\neq
\mathcal R(X_{\rm après\,inaction}).
$$

Cela pourrait donner un sens très fort à :

> **Qu’est-ce qui compte maintenant ?**

---

# Une candidate de définition de « compte maintenant »

Je proposerais de tester :

> **Quelque chose compte maintenant lorsque son traitement présent peut modifier une trajectoire pertinente, préserver ou ouvrir un futur accessible, lever un blocage, éviter une bifurcation défavorable ou supprimer du travail futur qui ne pourra pas être supprimé aussi efficacement plus tard.**

C’est très différent d’un feed.

---

# Et le principe « Tout est en ordre ✓ » devient testable

Makolo peut conclure :

> Tout est en ordre.

lorsque, pour les trajectoires pertinentes actuellement surveillées :

1. aucun blocage nécessitant une action présente n’est détecté ;
2. aucune fenêtre critique ne nécessite d’intervention ;
3. aucune bifurcation significative imminente n’est détectée ;
4. tout ce que Makolo pouvait préparer avec son autorité a été préparé ;
5. les incertitudes restantes ne justifient pas une action maintenant.

C’est une définition beaucoup plus forte qu’un simple dashboard sans notifications.

---

# Et maintenant : est-ce déjà différent d’un planner ?

Pas complètement.

C’est le résultat scientifique le plus important du crash-test.

Un excellent système composé de :

$$
\text{état}
+
\text{contraintes}
+
\text{graphe causal}
+
\text{planification}
+
\text{agent}
$$

pourrait probablement réaliser une grande partie de cela.

Donc :

$$
\boxed{
\text{nous avons commencé à justifier Makolo, mais pas encore la physique Makolo}
}
$$

Et c’est très bien.

Il ne faut pas tricher avec le résultat.

---

# Le prochain crash-test doit donc être encore plus difficile

Il faut maintenant essayer de casser **ce système dynamique minimal lui-même**.

Autrement dit, prendre :

$$
X,\quad
\mathcal C,\quad
\mathcal R,\quad
\mathcal U
$$

et demander :

> Est-ce suffisant ?

Je vois déjà quatre situations qui peuvent commencer à forcer quelque chose de plus riche :

### 1. Influence diffuse

Aucun lien explicite A → B n’existe, mais une modification du milieu affecte plusieurs systèmes simultanément.

C’est là que la notion de **champ** pourrait éventuellement devenir nécessaire.

### 2. Quantité continue accumulée

Ce n’est plus un simple vrai/faux ou une transition discrète : l’effet dépend de la quantité, de la distribution et du temps.

C’est là que les grandeurs continues pourraient commencer à être nécessaires.

### 3. Interactions collectives

Des milliers de CorpsMakolo produisent un comportement agrégé qui n’est pas raisonnablement représentable relation par relation.

C’est là que les modèles de continuum peuvent devenir utiles.

### 4. Dynamique où l’histoire instantanée et les interactions produisent spontanément des évolutions non codées comme workflows

C’est là qu’une véritable loi dynamique peut devenir intéressante.

---

## Donc nous avons maintenant notre premier résultat expérimental

Avant toute question d’algorithme, Makolo semble au minimum devoir posséder conceptuellement :

$$
\boxed{
\mathcal M=
(
X,
\mathcal C,
\mathcal D,
\mathcal R,
\mathcal U,
\mathcal O
)
}
$$

où :

* \(X\) = état actuel ;
* \(\mathcal C\) = contraintes ;
* \(\mathcal D\) = dynamique/transitions et dépendances causales ;
* \(\mathcal R\) = espace atteignable ;
* \(\mathcal U\) = interventions possibles ;
* \(\mathcal O\) = observation/connaissance du système.

Ce n’est pas encore un algorithme.

C’est **ce qu’il faut représenter avant de pouvoir choisir le processus de calcul**.

Et je pense que le prochain bon mouvement est précisément de prendre maintenant ce noyau et de lui faire subir le **deuxième niveau de crash-test** : les cas de milieu, influence diffuse, foule/capacité, perturbation extérieure, propagation, accumulation et interactions collectives.

C’est ce deuxième test qui devrait enfin nous dire si les notions de **champ, masse, charge, température, densité, énergie**, etc., apportent réellement quelque chose ou si elles restent superflues.


Oui. Alors faisons le test de manière sévère : **on ne cherche pas à prouver Makolo ; on cherche ce qui résiste quand on casse les solutions simples**.

# 1. Protocole du crash-test

Pour chaque situation, on impose la même question :

$$
\boxed{\text{Que faut-il comprendre ou faire maintenant ?}}
$$

Puis on vérifie si la réponse peut être obtenue avec seulement :

* recherche ;
* recommandation ;
* règles ;
* workflow ;
* calendrier ;
* graphe de dépendances ;
* planification/contraintes ;
* agent exécutant des actions.

Et surtout on observe **quelle information supplémentaire devient indispensable**.

Le test est réussi seulement s’il fait émerger une structure nécessaire.

---

# TEST A — L’opportunité idéale qui n’est pas réellement accessible

### Situation

Une formation à Nairobi correspond parfaitement au Profile.

Elle commence dans 45 jours.

Le Profile :

* a les qualifications ;
* a le budget ;
* a une place disponible dans la formation ;
* possède un passeport valide ;
* doit obtenir un visa ;
* doit fournir un certificat médical ;
* ne possède pas encore ce certificat ;
* le certificat ne peut être obtenu qu’après un examen ;
* le prochain examen disponible est dans 40 jours ;
* le traitement du visa exige ensuite au minimum 10 jours.

### Recherche

Trouve la formation.

### Recommender

Peut la classer très haut.

### Rules

Peut conclure :

> certificat médical manquant.

### Workflow

Peut montrer :

> étape 3 : certificat médical.

Mais aucune de ces conclusions ne suffit.

Le problème réel est :

$$
40+10>45.
$$

Donc même si chaque étape est individuellement réalisable :

$$
\boxed{\text{la trajectoire entière ne l'est plus}}
$$

dans la fenêtre disponible.

### Bonne conclusion Makolo

> Cette formation correspond à ton profil, mais elle n’est plus réalisable dans les conditions temporelles actuelles. Le blocage n’est pas simplement « certificat manquant » : il n’existe plus de séquence admissible permettant certificat → visa → départ avant le début de la formation.

### Ce que le test force

Il faut représenter :

$$
\boxed{\text{états + transitions + durées + ordre + fenêtre temporelle}}
$$

et calculer l’existence d’un chemin :

$$
X_0\rightsquigarrow X_f.
$$

Premier résultat :

$$
\boxed{\text{matching}\neq\text{reachability}}
$$

---

# TEST B — Toutes les règles passent, mais deux trajectoires entrent en collision

### Situation

Le même Profile possède :

* une intervention médicale importante vendredi ;
* un entretien professionnel vendredi ;
* un vol vendredi soir ;
* un document qui doit être remis physiquement avant le vol.

Chaque démarche, examinée séparément, est valide.

Le visa est bon.

Le billet est bon.

L’entretien est confirmé.

L’intervention médicale est confirmée.

Le document est prêt.

### Un workflow par démarche

Dit partout :

$$
\text{vert}.
$$

### Moteur de règles

Chaque règle isolée passe.

### Le problème

Les quatre trajectoires utilisent :

* la même personne ;
* le même temps ;
* parfois le même lieu ;
* éventuellement le même moyen de transport.

Il existe donc une contrainte commune.

Individuellement :

$$
\Gamma_1,\Gamma_2,\Gamma_3,\Gamma_4
$$

sont possibles.

Ensemble :

$$
\boxed{
\Gamma_1+\Gamma_2+\Gamma_3+\Gamma_4
}
$$

peuvent être impossibles.

### Ce que le test force

Il faut représenter :

$$
\boxed{\text{plusieurs trajectoires simultanées partageant des ressources}}
$$

avec notamment :

* temps ;
* personne ;
* capacité ;
* lieu lorsque pertinent ;
* ressources engagées ;
* dépendances.

Deuxième résultat :

$$
\boxed{
\text{possibilité locale}
\not\Rightarrow
\text{possibilité globale}
}
$$

---

# TEST C — Une chose sans intérêt devient importante

### Situation

Le Profile doit suivre une formation en ligne importante à 18 h.

Il ne s’intéresse absolument pas au match qui a lieu ailleurs.

Le match ne correspond :

* ni à ses intérêts ;
* ni à son historique ;
* ni à ses recherches.

Mais le match provoque localement une surcharge réseau suffisamment importante pour compromettre la connexion nécessaire à la formation.

### Recommender

Le match a pratiquement une pertinence nulle.

Il l’ignore.

### Search

Personne n’a cherché le match.

Il l’ignore également.

### Pourtant

Une chaîne causale existe :

$$
\text{match}
\rightarrow
\text{surcharge réseau}
\rightarrow
\text{qualité connexion}
\rightarrow
\text{formation}
$$

et donc :

$$
\text{match}
\rightarrow
\Gamma_{\rm formation}.
$$

### Bonne conclusion

Makolo n’a pas besoin de recommander le match.

Il doit éventuellement dire :

> La connexion risque d’être insuffisante pendant ta formation ; une alternative de connexion ou de lieu est utile avant 18 h.

### Ce que le test force

Il faut distinguer :

$$
\boxed{\text{pertinence sémantique}}
$$

de :

$$
\boxed{\text{pertinence causale}}
$$

Troisième résultat :

$$
\boxed{
\text{ce qui compte}
\neq
\text{ce qui m'intéresse}
}
$$

Une réalité compte lorsqu’elle peut modifier une trajectoire pertinente.

---

# TEST D — Le problème n’existe pas encore, mais Makolo doit agir maintenant

### Situation

Un billet est actuellement disponible.

Une place dans une formation est réservée pendant 48 heures.

Le Profile satisfait déjà toutes les conditions.

Il n’a rien demandé aujourd’hui.

Dans trois jours :

$$
Capacity=0.
$$

Si rien n’est fait, la trajectoire disparaît.

Aujourd’hui :

$$
X_f\in\mathcal R(X_0).
$$

Après expiration :

$$
X_f\notin\mathcal R(X_3).
$$

### Système réactif classique

Attend une requête :

> « Je veux m’inscrire. »

Mais il sera alors trop tard.

### Ce que Makolo devrait comprendre

L’état actuel comporte une possibilité qui va disparaître si aucune transformation n’a lieu.

Il y a donc une différence entre :

$$
\boxed{\text{résoudre un problème existant}}
$$

et :

$$
\boxed{\text{préserver une trajectoire encore ouverte}}
$$

### Bonne intervention

Selon l’autorité disponible :

* réserver ;
* préparer la réservation ;
* demander la confirmation nécessaire ;
* avertir seulement si une action humaine est indispensable.

### Ce que le test force

Il faut représenter :

$$
\boxed{
\text{fenêtres de validité}
+
\text{évolution future}
+
\text{interventions autorisées}
}
$$

Quatrième résultat :

> **Préparer peut signifier empêcher qu’un futur actuellement accessible cesse de l’être.**

---

# TEST E — Makolo croit qu’il y a un blocage, mais le monde dit le contraire

### Situation

Une démarche exige :

$$
R=\text{preuve d'identité valide}.
$$

Makolo ne retrouve pas de document correspondant.

Il conclut naïvement :

> preuve manquante.

Mais la personne possède réellement le document. Makolo ne le connaît simplement pas.

Nous avons :

### réalité

$$
X:\text{preuve existante}
$$

### observation Makolo

$$
Y:\text{aucune preuve retrouvée}
$$

### estimation

$$
\widehat X:\text{preuve probablement absente}.
$$

Ces trois objets sont différents.

### Mauvaise conclusion

> Vous devez obtenir une nouvelle preuve.

### Bonne conclusion

> Makolo ne dispose pas actuellement d’une preuve suffisante permettant de confirmer cette condition.

Ce n’est pas la même chose.

### Ce que le test force

Il faut absolument conserver :

$$
\boxed{
X\neq Y\neq\widehat X
}
$$

c’est-à-dire :

* monde ;
* observations ;
* représentation estimée.

Cinquième résultat :

$$
\boxed{
\text{inconnu}
\neq
\text{absent}
\neq
\text{faux}
}
$$

C’est un invariant majeur.

---

# TEST F — Une action passée ouvre un futur que personne ne cherchait

### Situation

Il y a six mois, la personne a réalisé une démarche qui a produit :

* une Proof ;
* une Credential ;
* une qualification reconnue.

Aujourd’hui apparaît une nouvelle formation.

La personne :

* ne la cherche pas ;
* ne suit pas le domaine explicitement ;
* n’a jamais exprimé de préférence correspondante.

Mais sa qualification antérieure signifie qu’elle peut accéder directement à un niveau avancé et éviter plusieurs démarches.

### Recommender

Peut ne rien voir.

### Search

Ne voit rien tant que la personne ne cherche pas.

### Makolo

Peut constater :

$$
X_{\rm passé}
\rightarrow
\text{capital d'action}
\rightarrow
X_{\rm futur}\text{ désormais accessible}.
$$

### Ce que le test force

Il faut que certaines transformations produisent des effets persistants réutilisables.

Donc :

$$
\boxed{
\text{histoire passée}
\rightarrow
\text{modification durable de l'état présent}
}
$$

Mais attention :

Makolo n’a pas besoin de conserver tout le passé dans son état.

Il doit conserver **ce que le passé a laissé de causalement pertinent aujourd’hui**.

C’est exactement le principe de l’état minimal suffisant.

---

# TEST G — Une même information ne doit pas produire la même décision pour tout le monde

### Situation

Une nouvelle règle de voyage apparaît.

Trois personnes :

### A

Aucun voyage prévu.

### B

Voyage prévu dans huit mois, aucune démarche urgente.

### C

Vol dans six jours et document affecté par la nouvelle règle.

La nouvelle règle est identique.

### Mauvais système

Envoie la même notification aux trois.

### Meilleur système

Pour A :

$$
\text{aucune conséquence opérationnelle actuelle}.
$$

Pour B :

$$
\text{éventuellement information à conserver}.
$$

Pour C :

$$
\boxed{\text{bifurcation immédiate de trajectoire}}
$$

avec action nécessaire.

### Ce que le test force

Une différence dans le monde devient importante relativement à :

$$
\boxed{
\text{l'état actuel du système qu'elle peut affecter}
}
$$

et non simplement parce que l’information est « pertinente ».

---

# TEST H — Une très petite modification produit une très grande conséquence

### Situation

Un dossier est entièrement prêt.

Une seule chose change :

$$
\text{heure limite}=17:00
$$

devient :

$$
16:00.
$$

Tout le reste de l’état est presque identique.

Pourtant le Profile n’arrive qu’à :

$$
16:30.
$$

Une toute petite différence de variable fait passer :

$$
X_f\in\mathcal R(X_0)
$$

à :

$$
X_f\notin\mathcal R(X_0).
$$

### Ce que le test force

Makolo ne peut pas mesurer l’importance d’une modification seulement par sa taille numérique.

Il faut regarder son effet sur :

$$
\boxed{\mathcal R(X)}
$$

l’espace des futurs accessibles.

C’est notre meilleure définition actuelle d’une **bifurcation opérationnellement importante**.

---

# Qu’est-ce qui sort de ces tests ?

Voilà le résultat intéressant.

Aucun test n’a encore forcé :

$$
m
$$

ou :

$$
q
$$

ou :

$$
T
$$

ou un champ physique particulier.

C’est très important.

En revanche, les tests forcent déjà huit structures.

---

## 1. Un état présent

Il faut pouvoir écrire :

$$
\boxed{X(t)}
$$

qui représente suffisamment la situation actuelle.

Pas toutes les données.

Seulement ce qui peut modifier les évolutions étudiées.

---

## 2. Des sous-systèmes distincts

Il ne faut surtout pas mettre tout dans le Profile.

Nous avons :

$$
X_P,\quad
X_{visa},\quad
X_{soins},\quad
X_{voyage},\quad
X_{formation},\ldots
$$

et un système composé lorsque nécessaire :

$$
\boxed{
X_{\mathcal S}
=
(X_1,X_2,\ldots,X_n,X_{\rm interactions})
}
$$

---

## 3. Des transitions

Il faut connaître :

$$
\boxed{
X_a\rightarrow X_b
}
$$

et les conditions permettant cette transformation.

C’est plus fondamental qu’un workflow fixe.

---

## 4. Des contraintes

Certaines transitions sont interdites ou deviennent impossibles selon :

* Requirements ;
* Access ;
* Capacity ;
* temps ;
* ressources ;
* autorités ;
* état d’autres systèmes.

Nous avons donc quelque chose comme :

$$
\boxed{\mathcal C(X,t)}
$$

l’ensemble des contraintes applicables.

---

## 5. Des dépendances causales

Il faut pouvoir savoir que :

$$
A\rightarrow B
$$

signifie réellement :

> une modification pertinente de \(A\) peut modifier l’évolution de \(B\).

Pas simplement :

> A et B sont reliés dans une base.

---

## 6. Un ensemble des états accessibles

C’est probablement l’un des objets les plus importants qui émerge :

$$
\boxed{
\mathcal R(X)
}
$$

et pas seulement une liste d’Opportunities.

Makolo veut savoir :

$$
\boxed{
\text{quels futurs restent atteignables depuis ici ?}
}
$$

---

## 7. Des interventions possibles

Nous avons besoin d’un ensemble :

$$
\boxed{
\mathcal U(X)
}
$$

contenant les actions réellement autorisées depuis l’état courant.

Par exemple :

$$
u_1=\text{préparer},
$$

$$
u_2=\text{réserver},
$$

$$
u_3=\text{demander},
$$

$$
u_4=\text{vérifier}.
$$

Et l’intervention transforme :

$$
X\xrightarrow{u}X'.
$$

---

## 8. Une couche de connaissance séparée

Il faut enfin :

$$
\boxed{
X,\quad Y,\quad\widehat X
}
$$

réalité, observations, estimation.

Sans cela Makolo fera des affirmations abusives sur le monde.

---

# Un résultat beaucoup plus profond apparaît

Regardons ce que Makolo semble réellement surveiller.

Pas principalement :

$$
\text{Opportunity}.
$$

Pas :

$$
\text{Profile}.
$$

Pas même :

$$
\text{Journey}.
$$

L’objet central semble être :

$$
\boxed{
\mathcal R(X)
}
$$

**l’espace des futurs encore réalisables à partir de la situation présente.**

Et ce qui compte maintenant est une chose capable de modifier cet espace.

On obtient alors une définition candidate extrêmement intéressante :

> **Une réalité est opérationnellement pertinente pour Makolo lorsqu’elle peut modifier de manière significative l’ensemble des états futurs accessibles ou les interventions actuellement nécessaires pour le système considéré.**

C’est beaucoup plus précis que :

> « pertinent pour moi ».

---

# Cela permet également de définir « maintenant »

Pourquoi quelque chose doit-il apparaître sur Home ?

Pas nécessairement parce que sa date est proche.

Mais parce que :

$$
\boxed{
\text{une action maintenant}
$$

est différente de :

$$
\boxed{
\text{la même action plus tard}.
}
$$

Par exemple :

$$
\mathcal R(X_{\rm après\,action\,maintenant})
\neq
\mathcal R(X_{\rm après\,inaction}).
$$

Cela pourrait donner un sens très fort à :

> **Qu’est-ce qui compte maintenant ?**

---

# Une candidate de définition de « compte maintenant »

Je proposerais de tester :

> **Quelque chose compte maintenant lorsque son traitement présent peut modifier une trajectoire pertinente, préserver ou ouvrir un futur accessible, lever un blocage, éviter une bifurcation défavorable ou supprimer du travail futur qui ne pourra pas être supprimé aussi efficacement plus tard.**

C’est très différent d’un feed.

---

# Et le principe « Tout est en ordre ✓ » devient testable

Makolo peut conclure :

> Tout est en ordre.

lorsque, pour les trajectoires pertinentes actuellement surveillées :

1. aucun blocage nécessitant une action présente n’est détecté ;
2. aucune fenêtre critique ne nécessite d’intervention ;
3. aucune bifurcation significative imminente n’est détectée ;
4. tout ce que Makolo pouvait préparer avec son autorité a été préparé ;
5. les incertitudes restantes ne justifient pas une action maintenant.

C’est une définition beaucoup plus forte qu’un simple dashboard sans notifications.

---

# Et maintenant : est-ce déjà différent d’un planner ?

Pas complètement.

C’est le résultat scientifique le plus important du crash-test.

Un excellent système composé de :

$$
\text{état}
+
\text{contraintes}
+
\text{graphe causal}
+
\text{planification}
+
\text{agent}
$$

pourrait probablement réaliser une grande partie de cela.

Donc :

$$
\boxed{
\text{nous avons commencé à justifier Makolo, mais pas encore la physique Makolo}
}
$$

Et c’est très bien.

Il ne faut pas tricher avec le résultat.

---

# Le prochain crash-test doit donc être encore plus difficile

Il faut maintenant essayer de casser **ce système dynamique minimal lui-même**.

Autrement dit, prendre :

$$
X,\quad
\mathcal C,\quad
\mathcal R,\quad
\mathcal U
$$

et demander :

> Est-ce suffisant ?

Je vois déjà quatre situations qui peuvent commencer à forcer quelque chose de plus riche :

### 1. Influence diffuse

Aucun lien explicite A → B n’existe, mais une modification du milieu affecte plusieurs systèmes simultanément.

C’est là que la notion de **champ** pourrait éventuellement devenir nécessaire.

### 2. Quantité continue accumulée

Ce n’est plus un simple vrai/faux ou une transition discrète : l’effet dépend de la quantité, de la distribution et du temps.

C’est là que les grandeurs continues pourraient commencer à être nécessaires.

### 3. Interactions collectives

Des milliers de CorpsMakolo produisent un comportement agrégé qui n’est pas raisonnablement représentable relation par relation.

C’est là que les modèles de continuum peuvent devenir utiles.

### 4. Dynamique où l’histoire instantanée et les interactions produisent spontanément des évolutions non codées comme workflows

C’est là qu’une véritable loi dynamique peut devenir intéressante.

---

## Donc nous avons maintenant notre premier résultat expérimental

Avant toute question d’algorithme, Makolo semble au minimum devoir posséder conceptuellement :

$$
\boxed{
\mathcal M=
(
X,
\mathcal C,
\mathcal D,
\mathcal R,
\mathcal U,
\mathcal O
)
}
$$

où :

* \(X\) = état actuel ;
* \(\mathcal C\) = contraintes ;
* \(\mathcal D\) = dynamique/transitions et dépendances causales ;
* \(\mathcal R\) = espace atteignable ;
* \(\mathcal U\) = interventions possibles ;
* \(\mathcal O\) = observation/connaissance du système.

Ce n’est pas encore un algorithme.

C’est **ce qu’il faut représenter avant de pouvoir choisir le processus de calcul**.

Et je pense que le prochain bon mouvement est précisément de prendre maintenant ce noyau et de lui faire subir le **deuxième niveau de crash-test** : les cas de milieu, influence diffuse, foule/capacité, perturbation extérieure, propagation, accumulation et interactions collectives.

C’est ce deuxième test qui devrait enfin nous dire si les notions de **champ, masse, charge, température, densité, énergie**, etc., apportent réellement quelque chose ou si elles restent superflues.

Oui. Le troisième crash-test donne justement le droit de supprimer des concepts si nécessaire. La question n’est plus « comment définir la masse Makolo ? », mais :

$$
\boxed{\text{Si j'enlève cette grandeur, quelle capacité Makolo devient impossible ?}}
$$

Si la réponse est « aucune », elle n’appartient pas au noyau.

# Troisième crash-test — Les grandeurs physiques doivent gagner leur place

Nous partons du système qui a déjà résisté aux tests précédents :

$$
\mathcal M=
(X,\mathcal E,\mathcal C,\mathcal D,\mathcal R,\mathcal U,\mathcal O)
$$

où :

* \(X\) = état ;
* \(\mathcal E\) = environnement pertinent ;
* \(\mathcal C\) = contraintes ;
* \(\mathcal D\) = dynamique/transitions ;
* \(\mathcal R\) = ensemble atteignable ;
* \(\mathcal U\) = interventions possibles ;
* \(\mathcal O\) = observation/connaissance.

Et nous essayons maintenant d’ajouter successivement :

$$
m,\quad q,\quad n,\quad T,\quad E.
$$

---

# I. MASSE — que perd-on si elle n’existe pas ?

Notre candidate historique était :

> quantité de réalité effectivement engagée dans le CorpsMakolo.

Prenons un cas volontairement favorable à cette idée.

## Cas A — deux projets apparemment identiques

Deux démarches \(A\) et \(B\) ont le même objectif et sont au même état apparent.

Mais \(A\) engage :

* 1 personne ;
* aucune réservation ;
* aucun contrat ;
* très peu de ressources.

\(B\) engage :

* 200 personnes ;
* plusieurs contrats ;
* des réservations ;
* des infrastructures ;
* des ressources déjà mobilisées.

Il paraît intuitif que \(B\) soit plus difficile à arrêter ou réorienter.

On pourrait être tenté de dire :

$$
m_B>m_A
$$

et :

> B possède plus d’inertie.

Très séduisant.

Mais faisons le crash-test.

---

## Peut-on expliquer cela sans masse ?

Oui.

On peut représenter explicitement :

$$
X_B=
(
\text{contrats},
\text{personnes engagées},
\text{réservations},
\text{coûts de sortie},
\text{dépendances},
\text{ressources},
\ldots
)
$$

et calculer les conséquences d’une modification.

Par exemple :

$$
C_{\rm changement}(B)
>
C_{\rm changement}(A).
$$

Ou encore représenter les transitions admissibles :

$$
\mathcal U(B)
$$

comme beaucoup plus contraintes.

Nous pouvons donc expliquer la « résistance au changement » sans introduire une masse.

---

## Qu’apporterait véritablement \(m\) ?

Pour justifier une masse physique, il faudrait qu’un seul scalaire :

$$
m
$$

permette une prédiction supplémentaire du type :

$$
F=ma
$$

ou une autre loi physique applicable.

Il faudrait que deux systèmes ayant le même état pertinent sauf \(m\) évoluent différemment **selon une loi stable dépendant de \(m\)**.

Nous ne l’avons pas démontré.

### Verdict

$$
\boxed{
m_{\rm Makolo}\;:\;\text{non nécessaire actuellement}
}
$$

La notion de « réalité engagée » reste intéressante conceptuellement, mais les tests montrent qu’elle peut probablement être représentée plus proprement par les ressources, engagements et dépendances réels.

Donc je descendrais son statut :

**CANDIDAT faible / À DÉMONTRER.**

La **masse physique réelle**, évidemment, reste applicable lorsqu’on simule réellement un objet matériel.

---

# II. CHARGE — une asymétrie causale est-elle réellement une charge ?

Notre candidate disait approximativement :

$$
q>0
$$

pour une influence ouvrant des trajectoires,

et :

$$
q<0
$$

pour une influence convergente ou résolutive.

Testons-la.

## Cas

Une Credential obtenue ouvre :

$$
20
$$

possibilités nouvelles.

Une interdiction ferme :

$$
15
$$

possibilités.

On pourrait être tenté d’écrire :

$$
q_{\rm credential}>0
$$

$$
q_{\rm interdiction}<0.
$$

Mais avons-nous besoin de charge ?

---

## Sans charge

Nous avons simplement :

$$
\mathcal R(X_1)\supset\mathcal R(X_0)
$$

dans le premier cas,

et :

$$
\mathcal R(X_2)\subset\mathcal R(X_0)
$$

dans le second.

C’est déjà exactement l’information qui nous intéresse.

Nous pouvons même mesurer :

$$
\Delta\mathcal R.
$$

Pas besoin de \(q\).

---

## Test encore plus sévère

Pour qu’une charge physique soit justifiée, il faudrait retrouver quelque chose comme :

* conservation de charge ;
* densité de charge ;
* courant ;
* source de champ ;
* loi de couplage ;
* éventuellement Maxwell si nous parlons réellement de charge électromagnétique.

Or une Credential peut :

> ouvrir dix possibilités

sans « perdre » une quantité correspondante ailleurs.

Une règle peut fermer un futur sans qu’une charge se soit déplacée.

Donc la conservation même échoue probablement.

### Verdict

$$
\boxed{
q_{\rm Makolo}\;:\;\text{ne résiste pas au crash-test actuel}
}
$$

Je serais même plus sévère qu’avant :

### SANS ÉQUIVALENT démontré à ce stade

pour la **charge causale Makolo**.

Cela ne remet évidemment pas en cause la charge électrique réelle :

$$
q_{\rm électrique}.
$$

---

# III. QUANTITÉ DE MATIÈRE — faut-il vraiment des moles Makolo ?

Prenons un événement avec :

$$
500
$$

places.

Une bourse avec :

$$
100
$$

allocations.

Un transport avec :

$$
50
$$

sièges.

Il existe clairement une quantité.

Mais est-ce :

$$
n
$$

au sens physique de quantité de matière ?

---

## Sans mole

Nous avons naturellement :

$$
N=500
$$

places,

ou :

$$
Capacity=500.
$$

Cela suffit parfaitement pour :

$$
N_{\rm disponibles}
=
N_{\rm total}-N_{\rm occupés}.
$$

Aucune conversion :

$$
n=\frac N{N_A}
$$

n’apporte quelque chose.

Dire qu’un concert possède :

$$
\frac{500}{N_A}\;\text{mol de places}
$$

serait mathématiquement constructible mais physiquement vide.

---

## Quand \(n\) devient-il réel ?

Seulement lorsque nous parlons d’une véritable espèce physique :

* molécules ;
* atomes ;
* particules ;
* constituants matériels appropriés.

Alors :

$$
n=N/N_A
$$

reprend son sens standard.

### Verdict

Pour les places, bourses, billets, unités d’accès :

$$
\boxed{
\text{count / Capacity}
}
$$

est suffisant.

Donc :

$$
\boxed{
n_{\rm Makolo}
\text{ n'est pas nécessaire comme primitive du réseau d'action}
}
$$

La quantité de matière physique reste bien sûr disponible dans un secteur matériel réel.

---

# IV. TEMPÉRATURE — l’agitation Makolo gagne-t-elle quelque chose ?

Prenons le meilleur cas possible.

Un système comporte énormément de micro-transitions.

À un instant :

* beaucoup de changements ;
* beaucoup de fluctuations ;
* comportements peu cohérents.

On pourrait appeler cela :

> « système chaud ».

Mais faisons le test.

---

## Peut-on le représenter autrement ?

Oui.

Par exemple :

$$
\lambda(t)
$$

pour un taux de transitions,

$$
\sigma_v
$$

pour une dispersion,

ou différents indicateurs de variance/désordre appropriés.

Ces grandeurs disent exactement ce que nous observons.

---

## Pour avoir une vraie température

Il faudrait que le système possède quelque chose de beaucoup plus fort :

* grand nombre de degrés de liberté ;
* description statistique appropriée ;
* équilibre ou quasi-équilibre pertinent ;
* énergie interne ;
* relation thermodynamique ;
* échanges thermiques ;
* température intensive ;
* conséquences conformes à la thermodynamique.

Par exemple :

$$
\frac1T=
\left(
\frac{\partial S}{\partial U}
\right)_{V,N}
$$

dans un contexte thermodynamique approprié.

Nous ne pouvons pas obtenir cela simplement avec :

> « beaucoup d’activité ».

### Verdict

$$
\boxed{
T_{\rm Makolo}
\text{ comme agitation du réseau d'action n'est pas nécessaire actuellement}
}
$$

Une vraie température physique :

$$
T_{\rm physique}
$$

reste évidemment pertinente lorsqu’elle intervient réellement : météo, chaîne du froid, organisme matériel, machine, environnement, etc.

---

# V. ÉNERGIE — peut-elle représenter la capacité d’agir ?

Crash-test extrêmement important.

Supposons qu’un Profile possède :

* argent ;
* temps ;
* accès ;
* véhicule ;
* autorisation ;
* disponibilité.

Il possède donc beaucoup de « capacité à agir ».

Sommes-nous autorisés à appeler cela énergie ?

Non.

---

## Sans énergie

On peut représenter séparément :

$$
B=\text{budget}
$$

$$
\tau=\text{temps disponible}
$$

$$
A=\text{Access}
$$

$$
C=\text{Capacity}
$$

etc.

Les contraintes déterminent si l’action est possible.

Cela fonctionne.

---

## Avec une énergie abstraite

Supposons :

$$
E_{\rm Makolo}=73.
$$

Qu’est-ce que 73 permet de calculer ?

Rien que nous ne sachions déjà.

Et surtout :

$$
100€+2h+\text{un visa}
$$

ne produit pas une grandeur homogène en joules.

L’analyse dimensionnelle seule détruit cette tentative.

---

## Quand l’énergie devient réellement pertinente ?

Dans un problème physique réel.

Exemples :

* batterie nécessaire à un véhicule ;
* énergie nécessaire à un déplacement ;
* consommation électrique d’une infrastructure ;
* chauffage ;
* rayonnement ;
* mécanique.

Alors :

$$
E
$$

est exactement l’énergie physique standard.

### Verdict

$$
\boxed{
E_{\rm Makolo}
\text{ comme "capacité à agir" : SANS ÉQUIVALENT}
}
$$

Mais :

$$
\boxed{
E_{\rm physique}
}
$$

reste pleinement disponible lorsque le problème la requiert.

---

# VI. Ce test provoque quelque chose d’important

Regardons ce qui vient de se produire.

Nous avons essayé :

$$
m,q,n,T,E
$$

comme grandeurs propres aux objets d’action Makolo.

Et aucune n’a encore démontré qu’elle était indispensable.

C’est une découverte, pas un échec.

Elle nous évite probablement une énorme erreur de conception.

---

# VII. Peut-être avons-nous mis la physique au mauvais endroit

Jusqu’ici nous demandions parfois :

> Quelle masse donner à une formation ?

> Quelle charge possède un Profile ?

> Quelle température possède un ensemble d’activités ?

Mais nos crash-tests suggèrent une autre architecture :

$$
\boxed{
\text{La physique n'est peut-être pas à fabriquer dans les objets métier.}
}
$$

Elle est peut-être déjà **dans le monde dans lequel ces objets agissent**.

C’est radicalement différent.

---

# VIII. Exemple : voyage

Pour organiser un voyage, Makolo manipule :

### Couche d’action

* billet ;
* visa ;
* Access ;
* Requirements ;
* Capacity ;
* rendez-vous ;
* preuve ;
* horaires.

Mais le voyage se produit aussi dans un monde physique contenant :

* distances ;
* vitesses ;
* véhicules ;
* météo ;
* énergie ;
* infrastructures ;
* foule ;
* gravité ;
* géographie ;
* temps.

Nous n’avons pas besoin de donner une « masse Makolo » au visa.

Nous devons simplement savoir comment l’état administratif du visa **conditionne l’accès à une trajectoire physique réelle**.

Voilà quelque chose de beaucoup plus propre.

---

# IX. Deux catégories commencent donc à émerger

## A. Variables d’action

Elles appartiennent à l’organisation humaine :

$$
Access,\ Requirement,\ Capacity,\ Proof,\ Mandate,\ Journey,\ldots
$$

Elles ne doivent pas être déguisées en grandeurs physiques.

---

## B. Variables physiques

Elles appartiennent aux systèmes physiques réellement constitués :

$$
x,t,m,q,T,E,\rho,\mathbf v,\ldots
$$

Elles conservent exactement leur sens scientifique normal.

---

# X. Et les deux couches peuvent se rencontrer

C’est probablement là que se trouve le véritable Univers Makolo.

Supposons :

> Visa absent.

C’est une condition d’action :

$$
Access_{\rm frontière}=0.
$$

Le vol physique existe toujours.

L’avion possède toujours :

$$
m,\mathbf v,E,\ldots
$$

La géographie existe toujours.

Mais la trajectoire physique :

$$
\Gamma_{\rm Profile}
$$

qui traverse cette frontière n’est pas admissible pour ce Profile dans le système d’action.

Donc :

$$
\boxed{
\text{condition d'action}
\longrightarrow
\text{restriction des trajectoires physiques admissibles}
}
$$

sans transformer le visa en force, masse ou charge.

C’est très puissant conceptuellement.

---

# XI. Un autre exemple : Capacity

Un stade possède :

$$
Capacity=50\,000.
$$

Ce n’est pas une masse.

Mais lorsque :

$$
49\,999
$$

personnes sont déjà admises, il reste :

$$
1
$$

droit de placement disponible.

Une fois les personnes physiquement présentes, elles ont chacune :

* masse physique réelle ;
* position ;
* vitesse ;
* interactions matérielles.

Si la foule devient suffisamment dense, alors :

$$
\rho_m(x,t)
$$

ou une densité de nombre :

$$
n_{\rm count}(x,t)
$$

peut devenir physiquement pertinente.

Donc :

$$
\boxed{
Capacity
\neq
\text{densité physique}
}
$$

mais Capacity peut déterminer combien de Corps physiques seront susceptibles d’entrer dans un système où la densité devient ensuite importante.

---

# XII. Cela donne une interface très intéressante entre métier et physique

Prenons :

$$
A
$$

une décision/action Makolo.

Elle modifie :

$$
X_{\rm action}.
$$

Cela peut rendre possible une transformation du monde physique :

$$
X_{\rm physique}.
$$

Puis l’évolution physique produit de nouvelles conditions :

$$
X_{\rm physique}(t+\Delta t)
$$

qui peuvent à leur tour modifier :

$$
X_{\rm action}.
$$

On obtient :

$$
\boxed{
X_{\rm action}
\leftrightarrow
X_{\rm physique}
}
$$

sans les confondre.

---

# XIII. Un exemple complet : formation à Nairobi

### État d’action

$$
X_A=
(
visa,
billet,
admission,
documents,
Access,
Capacity,
horaires
).
$$

### État physique

$$
X_P=
(
position,
vitesse,
environnement,
transport,
\ldots
).
$$

Le visa passe à :

$$
visa=accordé.
$$

Cela ne pousse pas physiquement Christophe vers Nairobi.

Il modifie l’espace des trajectoires admissibles :

$$
\mathcal R_A.
$$

Le Profile peut ensuite choisir/exécuter une action physique de déplacement.

Cette action produit :

$$
g(t):
Kinshasa\rightarrow Nairobi
$$

par exemple.

Voilà la jonction.

---

# XIV. Et maintenant le champ revient, mais correctement

Un champ peut être pertinent lorsque l’environnement physique réellement rencontré par la trajectoire le nécessite.

Exemples :

$$
T(x,t)
$$

champ de température ;

$$
\mathbf E(x,t)
$$

champ électrique ;

$$
\mathbf B(x,t)
$$

champ magnétique ;

$$
g_{\mu\nu}(x)
$$

champ métrique gravitationnel dans la relativité ;

ou d’autres champs physiques standards.

Mais un « champ de bourses » n’est pas nécessaire.

Une distribution géographique de bourses peut être une fonction :

$$
B(g,t)
$$

dans une base de données, sans devenir un champ physique fondamental.

---

# XV. La distinction « mathématique » / « physique » devient essentielle

On peut représenter mathématiquement :

$$
f(x,t)
$$

pour énormément de choses :

* disponibilité de taxis ;
* places libres ;
* qualité estimée du réseau ;
* prix ;
* événements.

Cela constitue un **champ mathématique spatio-temporel** au sens large d’une fonction définie sur un domaine.

Mais il ne faut pas automatiquement lui attribuer :

* énergie ;
* impulsion ;
* équations de champ fondamentales ;
* vitesse physique de propagation.

Donc :

$$
\boxed{
\text{field-like data}
\neq
\text{champ physique fondamental}
}
$$

Cette distinction nous protège.

---

# XVI. Qu’est-ce qui survit réellement au troisième crash-test ?

Beaucoup de concepts physiques **structurels** survivent remarquablement bien.

### Corps / système

$$
\boxed{\text{RETENU}}
$$

### État

$$
\boxed{\text{RETENU}}
$$

### Espace d’états

$$
\boxed{\text{RETENU}}
$$

### Trajectoire

$$
\boxed{\text{RETENU}}
$$

### Dynamique

$$
\boxed{\text{RETENU}}
$$

### Interaction

$$
\boxed{\text{RETENU}}
$$

### Contraintes

$$
\boxed{\text{RETENU}}
$$

### Systèmes couplés

$$
\boxed{\text{RETENU}}
$$

### Environnement

$$
\boxed{\text{RETENU}}
$$

### Description distribuée / champs mathématiques lorsque nécessaire

$$
\boxed{\text{RETENU}}
$$

### Systèmes discrets, continus et hybrides

$$
\boxed{\text{RETENU}}
$$

### Accessibilité / espace atteignable

$$
\boxed{\text{RETENU / CANDIDAT très fort}}
$$

### Contrôle / intervention

$$
\boxed{\text{CANDIDAT très fort}}
$$

---

# XVII. Ce qui ne survit pas comme primitive universelle Makolo

À ce stade :

$$
\boxed{
m_{\rm Makolo}
}
$$

non démontrée.

$$
\boxed{
q_{\rm Makolo}
}
$$

non démontrée, probablement à retirer comme analogie causale.

$$
\boxed{
n_{\rm Makolo}
}
$$

non nécessaire pour représenter Capacity/count.

$$
\boxed{
T_{\rm Makolo}
}
$$

non démontrée hors systèmes réellement thermodynamiques.

$$
\boxed{
E_{\rm Makolo}
}
$$

non pertinente comme « capacité d’action ».

Cela ne supprime aucune grandeur de la physique.

Cela supprime seulement l’idée qu’il faudrait obligatoirement en fabriquer une version métier.

---

# XVIII. Et voici peut-être la découverte la plus importante jusqu’ici

Nous étions partis implicitement vers :

$$
\text{Makolo facts}
\rightarrow
\text{pseudo-physical quantities}
\rightarrow
\text{physics}.
$$

Les crash-tests suggèrent plutôt :

$$
\boxed{
\text{Makolo facts}
\rightarrow
\text{state/constraints/actions}
}
$$

et parallèlement :

$$
\boxed{
\text{physical reality}
\rightarrow
\text{standard physical state}
}
$$

puis :

$$
\boxed{
\text{interaction entre les deux couches}.
}
$$

Autrement dit :

$$
\boxed{
\text{on ne transforme pas nécessairement le métier en physique}
}
$$

mais :

$$
\boxed{
\text{on fait cohabiter proprement l'action et le monde physique dans un même système dynamique}
}
$$

C’est beaucoup plus défendable.

---

# XIX. Alors à quoi sert « Univers Makolo » ?

Il commence à avoir une définition beaucoup plus nette.

> **L’Univers Makolo est le cadre dynamique dans lequel des CorpsMakolo et systèmes possèdent des états, évoluent dans le temps, suivent des trajectoires, interagissent entre eux et avec leur environnement, tandis que les faits d’action — droits, démarches, conditions, capacités, preuves et autorités — contraignent ou rendent possibles certaines transformations sans être artificiellement convertis en grandeurs physiques.**

Cette définition est beaucoup plus robuste que :

> « tout devient masse, charge et énergie ».

---

# XX. Et la question opérationnelle devient

Pour une personne dans un état :

$$
X_0,
$$

avec environnement :

$$
\mathcal E_0,
$$

et contraintes d’action :

$$
\mathcal C_0,
$$

Makolo cherche :

$$
\boxed{
\mathcal R(X_0,\mathcal E_0,\mathcal C_0)
}
$$

les états futurs réellement accessibles.

Puis :

$$
\boxed{
\mathcal U(X_0)
}
$$

les interventions actuellement possibles.

Et enfin :

$$
\boxed{
u^\*
}
$$

une intervention utile lorsqu’il y en a une.

Mais « utile » devra encore être défini sans introduire arbitrairement une fonction d’optimisation qui choisirait la vie de l’utilisateur à sa place.

---

# XXI. Voilà notre prochain problème

Nous venons de découvrir **ce qu’il faut représenter**.

Mais une question gigantesque reste ouverte :

$$
\boxed{
\text{Parmi tous les futurs accessibles, lesquels Makolo doit-il considérer ?}
}
$$

Parce que :

$$
\mathcal R(X)
$$

peut être immense.

Makolo ne peut ni :

* explorer tout ;
* afficher tout ;
* choisir arbitrairement à la place de la personne.

Il faut donc maintenant distinguer :

$$
\boxed{
\text{possible}
}
$$

$$
\boxed{
\text{pertinent}
}
$$

$$
\boxed{
\text{souhaité}
}
$$

$$
\boxed{
\text{engagé}
}
$$

$$
\boxed{
\text{important maintenant}
}
$$

et :

$$
\boxed{
\text{actionnable maintenant}.
}
$$

Et cette question est peut-être encore plus importante que masse ou charge :

> **Comment Makolo réduit-il l’immense espace des futurs possibles sans redevenir un simple moteur de recommandation et sans décider à la place de la personne ?**

C’est là, à mon avis, que le prochain crash-test doit frapper.

Oui. Et je pense que c’est ici que Makolo peut réellement éviter de redevenir un recommender.

Le problème n’est pas :

$$
\text{« parmi 1 million de futurs, lesquels ont le meilleur score ? »}
$$

Ce serait exactement un ranking.

Le problème est plutôt :

$$
\boxed{
\text{« parmi tout ce qui est possible, qu'est-ce qui mérite même d'entrer dans le champ de décision de la personne maintenant ? »}
}
$$

Et cette réduction peut être faite **sans décider ce que la personne doit vouloir**.

---

# 1. Il ne faut pas passer directement de \(\mathcal R(X)\) à une liste

Nous avons :

$$
\mathcal R(X)
$$

l’ensemble des états futurs accessibles depuis l’état actuel.

Cet ensemble peut être gigantesque.

La mauvaise solution serait :

$$
\mathcal R(X)
\xrightarrow{\text{score}}
\text{Top 10}.
$$

Cela donnerait :

$$
\boxed{\text{Univers Makolo}\rightarrow\text{recommender sophistiqué}}
$$

et nous aurions échoué.

Il faut plusieurs réductions de nature différente.

---

# 2. Première réduction : ce qui est réellement admissible

Avant toute notion d’intérêt :

$$
\mathcal R_0=\text{futurs concevables}
$$

devient :

$$
\boxed{
\mathcal R_1=
\text{futurs réellement atteignables}
}
$$

après application de :

* causalité ;
* temps ;
* Access ;
* Requirements ;
* Capacity ;
* ressources ;
* contraintes physiques ;
* contraintes réglementaires ;
* dépendances entre systèmes.

C’est une réduction objective relativement au modèle.

Elle ne dit rien de ce que l’utilisateur préfère.

---

# 3. Deuxième réduction : les futurs qui touchent quelque chose déjà engagé

Le Profile n’est pas sans histoire.

Il existe des choses auxquelles la personne est déjà liée :

* Journey active ;
* réservation ;
* rendez-vous ;
* travail ;
* voyage ;
* formation ;
* responsabilité ;
* projet ;
* engagement pris ;
* personne ou espace dont elle a la responsabilité.

Appelons cet ensemble :

$$
\mathcal K(X)
$$

l’ensemble des **engagements actifs**.

Nous pouvons rechercher parmi les futurs ceux qui modifient réellement un engagement existant.

$$
\boxed{
\mathcal R_{\rm engagement}
=
\{X_f\in\mathcal R(X)\mid
X_f\text{ affecte un engagement actif}\}
}
$$

Ici Makolo ne dit pas :

> « tu devrais aimer ceci ».

La personne a déjà donné un signal beaucoup plus fort qu’un like :

$$
\boxed{\text{elle est engagée dans quelque chose}}
$$

---

# 4. Troisième réduction : les obligations

Certaines choses ne dépendent même pas d’une préférence.

Exemple :

* visa expirant ;
* rendez-vous obligatoire ;
* facture ;
* Requirement à satisfaire ;
* renouvellement ;
* action imposée par une responsabilité assumée.

Appelons :

$$
\mathcal O(X)
$$

les obligations actives pertinentes.

Un futur mérite l’attention s’il détermine :

$$
\text{satisfaction}
$$

ou :

$$
\text{violation}
$$

d’une obligation réelle.

Cela n’est pas une recommandation.

Makolo ne dit pas :

> « je pense que tu aimerais renouveler ton document ».

Il constate :

> « sans cette transition, une démarche à laquelle tu es déjà engagé ne pourra plus continuer ».

---

# 5. Quatrième réduction : les futurs qui risquent de disparaître

C’est probablement une catégorie Makolo très importante.

Aujourd’hui :

$$
X_f\in\mathcal R(X_t).
$$

Demain, sans intervention :

$$
X_f\notin\mathcal R(X_{t+\Delta t}).
$$

Donc quelque chose compte maintenant parce qu’il possède une **fenêtre d’action**.

Appelons :

$$
\mathcal W(X,t)
$$

les trajectoires dont l’accessibilité est temporellement fragile.

Ce sont par exemple :

* inscription qui ferme ;
* Capacity qui diminue ;
* document qui expire ;
* tarif ou réservation qui expire ;
* fenêtre administrative ;
* correspondance temporelle ;
* ressource temporairement disponible.

Makolo ne choisit toujours pas l’objectif.

Il dit :

> **« Si cette possibilité t’importe, la décision ne peut pas attendre beaucoup plus longtemps. »**

C’est très différent.

---

# 6. Cinquième réduction : ce qui peut provoquer une bifurcation importante

Nous avons déjà une définition candidate.

Une réalité devient importante si elle modifie significativement :

$$
\mathcal R(X).
$$

Supposons :

$$
A
$$

ne change presque rien.

Alors Makolo peut l’ignorer.

Mais :

$$
B
$$

fait passer :

$$
|\mathcal R(X)|
$$

ou surtout sa structure de :

$$
\mathcal R_1
$$

à :

$$
\mathcal R_2
$$

avec perte ou apparition de trajectoires importantes.

Alors :

$$
B
$$

mérite attention.

Le critère n’est pas :

> « B ressemble à tes centres d’intérêt ».

Mais :

$$
\boxed{
\text{B change ce que tu pourras réellement faire}
}
$$

---

# 7. Sixième réduction : l’actionnabilité

Beaucoup de choses importantes ne demandent aucune action maintenant.

C’est crucial.

Supposons :

* visa en instruction ;
* aucun document supplémentaire demandé ;
* délai normal ;
* aucune échéance ;
* rien que Makolo ou l’utilisateur puisse faire aujourd’hui.

La situation est importante.

Mais :

$$
\boxed{
\mathcal U(X)=\varnothing
}
$$

pour cette trajectoire à cet instant.

Pourquoi encombrer Home ?

Makolo peut continuer à surveiller silencieusement.

Donc nous introduisons :

$$
\boxed{
\text{important}
\neq
\text{actionnable maintenant}
}
$$

C’est probablement fondamental pour :

> **« Qu’est-ce qui compte maintenant ? »**

---

# 8. Septième réduction : Makolo peut-il déjà s’en charger ?

Supposons qu’une action soit nécessaire.

Mais Makolo possède déjà :

* les données ;
* l’autorité ;
* les permissions ;
* le moyen technique ;
* aucune décision humaine supplémentaire n’est requise.

Alors :

$$
u\in\mathcal U_{\rm Makolo}.
$$

Pourquoi demander à l’utilisateur ?

Makolo peut accomplir ou préparer ce qui est autorisé.

Cela transforme :

$$
\text{« voici une tâche pour toi »}
$$

en :

$$
\boxed{
\text{« ceci devait être fait ; Makolo l'a préparé ou accompli »}
}
$$

sous les limites d’autorité établies.

---

# 9. Il reste donc seulement une frontière décisionnelle humaine

Après toutes ces réductions, ce qui doit arriver devant la personne devrait être beaucoup plus petit.

Appelons-le :

$$
\boxed{
\mathcal F_H(X,t)
}
$$

la **frontière de décision humaine**.

Elle contient les situations où :

1. quelque chose compte réellement ;
2. une action ou décision doit avoir lieu maintenant ou bientôt ;
3. Makolo ne peut pas légitimement la prendre seul ;
4. l’utilisateur dispose réellement d’un choix.

C’est là que l’humain doit apparaître.

---

# 10. Et Makolo ne doit pas choisir à cet endroit

C’est essentiel.

Supposons :

$$
u_1=\text{accepter une formation}
$$

$$
u_2=\text{conserver son emploi actuel}
$$

et que les deux soient incompatibles.

Makolo peut calculer :

* conséquences ;
* dates ;
* coûts ;
* dépendances ;
* Requirements ;
* réversibilité ;
* effets sur les autres trajectoires.

Mais il ne doit pas conclure :

> « tu dois choisir la formation ».

Sauf si l’utilisateur a explicitement établi un objectif ou une préférence décisionnelle correspondante.

---

# 11. Cela nous donne une séparation très forte

Makolo peut être **autoritaire sur les faits**, mais pas sur les finalités personnelles.

Par exemple :

> « Ces deux rendez-vous se chevauchent. »

Factuel.

> « Si tu prends le vol, tu manqueras le rendez-vous. »

Conséquence.

> « Le visa expire avant le deuxième départ. »

Factuel.

Mais :

> « Le travail est plus important que la formation. »

Ce n’est plus un fait.

Donc :

$$
\boxed{
\text{Makolo peut calculer les conséquences}
}
$$

mais :

$$
\boxed{
\text{la personne choisit les finalités lorsqu'elles lui appartiennent}
}
$$

---

# 12. C’est peut-être la meilleure protection contre le recommender

Un recommender répond :

$$
\boxed{
\text{« lequel devrait-on te montrer ? »}
}
$$

Makolo peut répondre :

$$
\boxed{
\text{« quelles décisions sont réellement devant toi ? »}
}
$$

C’est complètement différent.

---

# 13. Il faut donc réduire par nécessité, pas par préférence

Je pense que c’est une règle très forte.

### Recommender

$$
\text{score(Profile,item)}
$$

puis classement.

### Makolo

Réduction successive :

$$
\mathcal R
$$

$$
\downarrow\quad\text{atteignabilité}
$$

$$
\mathcal R_{\rm admissible}
$$

$$
\downarrow\quad\text{engagements / obligations}
$$

$$
\mathcal R_{\rm concerné}
$$

$$
\downarrow\quad\text{bifurcations / fenêtres}
$$

$$
\mathcal R_{\rm sensible}
$$

$$
\downarrow\quad\text{actionnabilité}
$$

$$
\mathcal R_{\rm actionnable}
$$

$$
\downarrow\quad\text{ce que Makolo peut déjà gérer}
$$

$$
\boxed{
\mathcal F_H
}
$$

la frontière restante pour l’humain.

Ce n’est pas du ranking.

C’est une **réduction structurelle du problème**.

---

# 14. Crash-test : 10 000 possibilités de formation

Prenons :

$$
10\,000
$$

formations.

Un recommender chercherait peut-être :

$$
\text{Top }20.
$$

Makolo ne devrait pas forcément faire cela.

Supposons que la personne ait déjà exprimé :

> « Je veux devenir infirmier spécialisé en soins intensifs. »

Alors cet objectif devient une donnée de finalité **fournie par la personne**.

On peut examiner les trajectoires compatibles avec :

$$
G_{\rm utilisateur}.
$$

Après Requirements, localisation, temps, financement, disponibilité, etc., il reste :

$$
12
$$

trajectoires réellement accessibles.

Makolo ne doit pas forcément choisir la première.

Il peut dire :

> « Il existe 12 voies actuellement réalisables. Trois nécessitent une décision ce mois-ci. Les neuf autres restent ouvertes sans action immédiate. »

Cela est beaucoup plus Makolo.

---

# 15. Et si l’utilisateur n’a aucun objectif ?

Très important.

Makolo ne peut pas rester totalement aveugle.

C’est ici que **Discover** prend sa place.

Mais Discover n’est pas Home.

### Home

part de :

$$
\text{engagements + conséquences + décisions actuelles}.
$$

### Discover

élargit volontairement :

$$
\boxed{\text{l'espace des possibilités considérées}}
$$

pour permettre à la personne de découvrir des futurs qu’elle n’avait pas encore formulés.

Donc :

$$
\boxed{
Home:\ \text{réduction}
}
$$

et :

$$
\boxed{
Discover:\ \text{expansion contrôlée}
}
$$

C’est une distinction de produit extrêmement forte.

---

# 16. Discover ne doit toujours pas devenir un feed

Discover devrait pouvoir montrer :

> des **possibilités de trajectoire**,

et pas simplement :

> des contenus.

Par exemple :

* « Tu pourrais suivre cette formation » ;
* « cette qualification ouvre ces démarches » ;
* « dans cette région, trois possibilités deviennent accessibles avec ce document » ;
* « cette activité peut s’insérer dans tes disponibilités actuelles ».

La personne explore.

Elle n’est pas poussée à rester.

---

# 17. Lorsqu’elle choisit quelque chose dans Discover, son statut change

C’est très important.

Une possibilité :

$$
P
$$

peut être seulement explorée.

Puis l’utilisateur dit :

> « ça m’intéresse ».

Cela ne doit peut-être pas encore devenir un engagement fort.

On pourrait avoir plusieurs niveaux intentionnels.

Par exemple :

$$
\text{inconnu}
\rightarrow
\text{découvert}
\rightarrow
\text{à explorer}
\rightarrow
\text{intention}
\rightarrow
\text{engagement}
\rightarrow
\text{action}.
$$

Mais attention : ces états devront être définis proprement dans les domaines Makolo existants (`Interests`, `Open to`, `Veilles`, Journey, etc.) et non inventés comme nouveau modèle sans vérification.

Conceptuellement, cependant, cette distinction est importante.

---

# 18. Cela répond aussi à une question : d’où viennent les finalités ?

Pas uniquement d’un profil prédictif.

Elles peuvent venir de plusieurs sources.

### Finalité explicite

La personne dit :

> « Je veux aller à Nairobi ».

### Engagement révélé par une action réelle

Elle achète un billet.

### Responsabilité

Elle doit accomplir quelque chose au nom d’un Espace.

### Obligation

Une règle impose une action.

### Exploration

Elle demande à découvrir des possibilités.

Mais Makolo doit toujours savoir **d’où vient la finalité**.

Il ne doit pas inventer :

> « nous avons déduit que tu veux changer de métier ».

---

# 19. Cela donne une notion importante : la provenance de l’objectif

On pourrait conceptuellement associer à une finalité :

$$
G_k
$$

une provenance :

$$
\operatorname{source}(G_k)
$$

par exemple :

$$
\text{explicit-user}
$$

$$
\text{committed-action}
$$

$$
\text{responsibility}
$$

$$
\text{legal/required}
$$

$$
\text{exploration-request}.
$$

Cela protège l’autonomie.

---

# 20. Il faut également distinguer « préférable » et « dominant »

Ici les mathématiques peuvent nous aider sans choisir pour la personne.

Supposons deux trajectoires \(A\) et \(B\).

Si elles conduisent exactement au même résultat voulu, mais :

* A coûte moins ;
* A prend moins de temps ;
* A comporte moins de démarches ;
* A ne perd aucune possibilité supplémentaire ;

alors \(B\) peut être **strictement dominée**.

Makolo peut éliminer B sans avoir besoin d’une préférence arbitraire.

Conceptuellement :

$$
A\succ_{\rm dom}B.
$$

Mais si :

* A est moins chère ;
* B est plus rapide ;

aucune ne domine nécessairement l’autre.

Makolo doit présenter le choix.

---

# 21. Voilà une deuxième protection contre le ranking

Makolo peut utiliser une **frontière de Pareto** conceptuelle.

Au lieu de dire :

$$
A=92,\quad B=87,\quad C=73,
$$

on conserve les options non dominées.

$$
\boxed{
\mathcal P=
\{\Gamma:
\nexists\Gamma'
\text{ qui domine }\Gamma\}
}
$$

La personne choisit ensuite selon ses propres arbitrages.

Cela préserve beaucoup mieux l’agence humaine.

---

# 22. Exemple

Trois façons de rejoindre une formation :

| Trajectoire | Temps |  Coût | Démarches supplémentaires |
| ----------- | ----: | ----: | ------------------------: |
| A           |   2 h | 150 € |                         0 |
| B           |   2 h | 200 € |                         2 |
| C           |   1 h | 300 € |                         0 |

B est dominée par A :

* même durée ;
* plus chère ;
* plus de démarches.

Makolo peut la retirer.

Mais A et C impliquent un véritable arbitrage :

$$
\text{argent}\leftrightarrow\text{temps}.
$$

Makolo ne devrait pas choisir sans connaître la préférence correspondante.

---

# 23. « Qu’est-ce qui compte maintenant ? » commence donc à avoir une définition formelle

Un élément appartient à l’ensemble :

$$
\boxed{
\mathcal N(X,t)
}
$$

des choses qui comptent maintenant s’il existe au moins une conséquence telle que :

* une trajectoire engagée risque de changer ;
* une obligation approche ;
* une fenêtre va se fermer ;
* une bifurcation significative est proche ;
* une intervention est désormais possible ;
* une décision humaine est devenue nécessaire ;
* une incertitude doit être levée avant qu’une trajectoire puisse continuer.

C’est beaucoup plus fort qu’une notification chronologique.

---

# 24. Et l’ordre d’affichage ?

Nous devons être prudents : même une Home peut nécessiter un ordre.

Mais cet ordre ne doit pas forcément être un « score d’intérêt ».

On peut employer une priorité partielle fondée sur des contraintes objectives.

Par exemple :

### Niveau 1

Action nécessaire maintenant pour empêcher un échec imminent.

### Niveau 2

Décision humaine dont la fenêtre ferme bientôt.

### Niveau 3

Blocage actuel dont une intervention est possible.

### Niveau 4

Préparation que Makolo peut effectuer.

### Niveau 5

Information sans action immédiate.

Cette structure vient des **conséquences temporelles et causales**, pas de la popularité ou du potentiel d’engagement.

---

# 25. Mais même cette priorité ne doit pas être absolue

Deux éléments peuvent être incomparables.

Par exemple :

* rendez-vous médical important ;
* décision professionnelle urgente.

Makolo peut expliquer les conséquences des deux.

Mais il ne doit pas nécessairement dire :

> « le professionnel est numéro 1 ».

La relation de priorité peut être :

$$
\boxed{\text{ordre partiel}}
$$

plutôt qu’un classement total.

C’est une idée très importante.

---

# 26. Le ranking force artificiellement un ordre total

Un recommender tend à produire :

$$
A>B>C>D>E.
$$

Mais la vie réelle ressemble souvent plutôt à :

$$
A>B
$$

$$
C>D
$$

avec :

$$
A\parallel C.
$$

C’est-à-dire que A et C sont **incomparables sans choix de valeurs supplémentaire**.

Makolo doit pouvoir conserver cette incomparabilité.

---

# 27. Cela permet une règle d’autonomie très forte

### RETENU candidat

> **Makolo ne transforme pas automatiquement des alternatives incomparables en classement total. Lorsque la décision nécessite un arbitrage de valeurs qui n’est pas déjà établi par la personne ou par une contrainte objective, Makolo conserve les alternatives et expose leurs conséquences.**

C’est probablement l’un des principes produit les plus importants que nous ayons trouvés.

---

# 28. Et Makolo peut demander une préférence uniquement lorsqu’elle devient utile

Pas :

> « remplis 150 préférences au début ».

Mais lorsqu’une bifurcation réelle apparaît :

> « Tu as deux options : A préserve le budget, B préserve le temps. Qu’est-ce qui compte davantage ici ? »

La réponse devient alors une information utile pour cette décision.

Elle peut éventuellement être retenue si l’utilisateur souhaite qu’elle serve à l’avenir.

Cela produit une personnalisation beaucoup plus ancrée dans l’action.

---

# 29. On obtient donc une boucle

$$
X
$$

état courant.

Puis :

$$
\mathcal R(X)
$$

futurs accessibles.

Puis réduction structurelle :

$$
\mathcal R^\*(X)
$$

futurs concernés.

Puis :

$$
\mathcal F_H
$$

frontière décisionnelle.

La personne choisit éventuellement :

$$
u_H.
$$

Puis :

$$
X\xrightarrow{u_H}X'.
$$

Et :

$$
\mathcal R(X')
$$

est recalculé.

C’est une boucle d’action :

$$
\boxed{
\text{état}
\rightarrow
\text{possibilités}
\rightarrow
\text{décision nécessaire}
\rightarrow
\text{action}
\rightarrow
\text{nouvel état}
}
$$

---

# 30. Et Makolo peut être presque invisible

Voilà un résultat produit intéressant.

Si :

* aucune bifurcation importante ;
* aucune échéance ;
* aucun blocage ;
* aucune décision requise ;
* tout ce qui peut être préparé l’est ;

alors :

$$
\mathcal F_H=\varnothing.
$$

Home peut simplement dire :

> **Tout est en ordre. ✓**

C’est cohérent avec :

> Pas le plaisir de rester. Le plaisir d’avancer.

---

# 31. Premier crash-test : une possibilité très séduisante

Une bourse prestigieuse apparaît.

Elle correspond extrêmement bien au Profile.

Mais :

* la personne est déjà engagée dans une trajectoire incompatible ;
* elle n’a demandé aucune exploration ;
* aucun engagement actuel n’est affecté ;
* aucune obligation ;
* aucune conséquence causale sur ses trajectoires.

### Recommender

La montre en premier.

### Makolo Home

Probablement :

$$
\boxed{\text{rien}}
$$

Elle peut appartenir à Discover.

C’est une différence extrêmement forte.

---

# 32. Deuxième crash-test : possibilité peu séduisante mais importante

Renouvellement administratif banal.

Aucun intérêt.

Aucun plaisir.

Mais sans lui :

$$
\Gamma_{\rm voyage}
$$

sera bloquée dans 20 jours.

### Recommender

Très faible score.

### Makolo

Important maintenant.

Pourquoi ?

Parce que :

$$
\boxed{
\text{inaction présente}
\rightarrow
\text{perte future d'une trajectoire engagée}
}
$$

---

# 33. Troisième crash-test : 20 opportunités équivalentes

Un recommender doit les ordonner.

Makolo peut conclure :

> « 20 solutions satisfont toutes les contraintes. Elles sont équivalentes au regard de ce que tu m’as indiqué. »

Puis soit :

* présenter la diversité ;
* permettre l’exploration ;
* demander quel critère doit départager ;
* choisir aléatoirement si l’utilisateur demande « n’importe laquelle » ;
* utiliser un critère opérationnel objectif si l’utilisateur l’autorise.

Il n’est pas nécessaire d’inventer une différence.

---

# 34. Quatrième crash-test : la meilleure action est de ne rien faire

Très important.

Un moteur d’engagement veut toujours produire quelque chose.

Makolo doit pouvoir calculer :

$$
u^\*=\varnothing
$$

ou :

$$
\boxed{\text{aucune intervention actuellement nécessaire}}
$$

C’est probablement un signe de maturité essentiel.

---

# 35. Cinquième crash-test : Makolo pourrait améliorer un résultat contre le souhait humain

Supposons :

* option A est objectivement moins chère et plus rapide ;
* option B est un trajet que la personne veut faire pour voir sa famille.

Si Makolo choisit A uniquement parce qu’elle « optimise », il échoue.

Parce que l’objectif réel n’était pas uniquement :

$$
\min(\text{prix},\text{temps}).
$$

Donc :

$$
\boxed{
\text{optimisation}
\text{ sans finalité correctement spécifiée}
=
\text{mauvaise décision}
}
$$

---

# 36. Cela donne une hiérarchie conceptuelle extrêmement intéressante

Je la formulerais ainsi :

### Niveau 0 — Univers concevable

$$
\Omega
$$

Tout ce que notre modèle peut représenter.

### Niveau 1 — Accessible

$$
\mathcal R(X)
$$

Ce qui peut réellement être atteint.

### Niveau 2 — Concerné

$$
\mathcal C_R(X)
$$

Ce qui touche engagements, obligations ou systèmes pertinents.

### Niveau 3 — Sensible

$$
\mathcal S_R(X,t)
$$

Ce qui risque de changer significativement.

### Niveau 4 — Actionnable

$$
\mathcal A(X,t)
$$

Ce sur quoi une intervention est actuellement possible.

### Niveau 5 — Automatisable

$$
\mathcal A_M(X,t)
$$

Ce que Makolo peut légitimement traiter.

### Niveau 6 — Décision humaine

$$
\boxed{
\mathcal F_H(X,t)
}
$$

Ce qui doit effectivement arriver devant la personne.

Cette cascade pourrait devenir l’un des fondements de Makolo.

---

# 37. Et Discover suit la direction inverse

C’est très élégant.

Home réduit :

$$
\Omega
\rightarrow
\mathcal F_H.
$$

Discover fait presque l’inverse :

$$
\text{contexte actuel}
\rightarrow
\text{élargissement volontaire de l'espace des possibles}.
$$

Donc :

$$
\boxed{
Home=\text{compression vers l'action}
}
$$

$$
\boxed{
Discover=\text{expansion vers la possibilité}
}
$$

C’est une distinction architecturale extrêmement nette.

---

# 38. Je pense qu'on tient une réponse forte à la question

> Comment Makolo réduit-il l’immense espace des futurs sans devenir un recommender ?

Réponse candidate :

> **Makolo ne réduit pas d’abord l’espace des futurs par préférence ou similarité. Il l’élimine et le structure par atteignabilité, engagements existants, obligations, causalité, contraintes, fenêtres temporelles, conséquences sur les trajectoires et possibilité d’intervention. Il automatise ce qu’il est autorisé à traiter et ne soumet à la personne que la frontière restante de décisions qui exigent réellement son jugement. Lorsque plusieurs alternatives restent incomparables sans arbitrage personnel, Makolo conserve cette incomparabilité au lieu d’inventer un classement.**

Je pense que cette formulation est assez fondamentale.

---

# 39. Et cela modifie légèrement la promesse

« Makolo marche avec vous » devient beaucoup plus précis.

Makolo ne dit pas :

> « voici ce que tu devrais faire ».

Il fait plutôt :

$$
\boxed{
\text{éliminer le bruit}
}
$$

$$
\boxed{
\text{préserver les possibilités}
}
$$

$$
\boxed{
\text{préparer ce qui peut l'être}
}
$$

$$
\boxed{
\text{exposer les conséquences}
}
$$

$$
\boxed{
\text{faire remonter uniquement les vraies décisions}
}
$$

puis laisser :

$$
\boxed{
\text{la décision de finalité à la personne}.
}
$$

Cela commence à donner une définition extrêmement concrète de **« Makolo marche avec vous »**, sans tomber ni dans le feed, ni dans le ranking, ni dans un assistant qui décide de la vie de l’utilisateur.
