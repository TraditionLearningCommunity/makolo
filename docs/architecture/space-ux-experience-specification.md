# Makolo — Space UX Experience Specification

> **Statut : spécification conceptuelle consolidée de l’expérience Space**
>
> **Dépôt de référence :** `TraditionLearningCommunity/makolo`
>
> **Base vérifiée avant cette révision :** main@3b348dfa3a881a1f9d1e929e1e81c5a39983ffb1
>
> **Contrat mobile Space associé :** [Makolo_Space_Architecture_Experience_Mobile_Consolidee.md](Makolo_Space_Architecture_Experience_Mobile_Consolidee.md)
>
> **Portée :** définir l’architecture d’expérience d’un Space, ses préoccupations humaines, sa priorisation, ses grandes portes UX, ses contrats de comportement, ses variantes par archétype et son articulation avec Jour J / Makolo Live.
>
> **Hors périmètre :** pixel design, responsive détaillé, choix définitif des composants, implémentation Django/Flutter, nouvelle persistance, schémas API finaux, algorithmes de ranking Molongo, migrations.
>
> Le code, les migrations et les tests du `main` courant restent la vérité sur le runtime effectivement livré. Ce document décrit la cible d’expérience et ne crée aucune nouvelle vérité métier.

---

# 1. Intention produit

La promesse reste :

> **Makolo marche pour vous.**

Pour un Space, cela signifie que Makolo ne doit pas demander à une personne autorisée de comprendre la structure interne du logiciel afin d’opérer l’organisation.

L’expérience doit permettre à une personne de répondre rapidement à des questions humaines :

~~~text
Qu’est-ce qui mérite mon attention ?

Qu’est-ce que nous faisons réellement ?

Avec qui avançons-nous ?

Qu’est-ce qui pourrait nous faire avancer ?

Est-ce que cela fonctionne ?

Qui sommes-nous et qui peut agir ?
~~~

Le Space est une identité collective durable et un acteur opérationnel. Il n’est ni un User collectif, ni un second Profile, ni un conteneur universel de toutes les vérités métier.

L’UX Space doit donc composer les domaines propriétaires sans les absorber.

Principe :

> **Presentation représente les faits ; elle ne les possède pas.**

---

# 2. Invariants non négociables

L’UX Space respecte toujours les invariants canoniques Makolo :

~~~text
Profile = personne humaine globale
Space = identité collective durable

Assignment = responsabilité
Mandate / Permission = autorité

TeamMembership != Mandate
GroupMembership != Mandate

Readiness = projection dérivée

Requirement != Form
Requirement != Resource
Requirement != Proof

Access = droit
AccessCredential = représentation / secret du droit
AccessUse = observation de l’usage

Capacity = combien ?
Placement = où ?

Waitlist != Live Queue

JourneyStep != Checkpoint

Dossier != task manager
Project != task manager

posséder un document
!= le retrouver
!= satisfaire un Requirement
~~~

Une composition UX ne transfère jamais implicitement :

- Permission ;
- Mandate ;
- Access ;
- Entitlement ;
- Payment ;
- credential ;
- données privées ;
- autorité d’un contexte à un autre.

Les projections collectives et publiques appliquent la divulgation minimale.

---

# 3. Principe directeur : partir du souci humain, pas du module

Le Space runtime peut posséder Activities, Requests, Access, Capacity, Payments, CRM, Groups, Partners, Analytics, Automation et de nombreux autres domaines.

Cela ne signifie pas que l’humain doit rencontrer Makolo comme une liste de modules.

Le modèle cible est :

~~~text
quelque chose se passe
        ↓
cela concerne ma responsabilité
        ↓
Makolo m’explique la situation
        ↓
j’agis
        ↓
si nécessaire j’entre
dans la profondeur métier canonique
~~~

et non :

~~~text
j’ai une fonctionnalité
        ↓
elle reçoit un module
        ↓
le module reçoit une entrée
        ↓
je choisis le domaine
        ↓
je découvre ensuite ce qui se passe
~~~

Une capacité métier existante peut être excellente et correctement sécurisée tout en étant trop visible, trop technique ou mal placée dans l’expérience générale.

---

# 4. Contexte supérieur : entrer dans un Space avant d’agir

La chaîne conceptuelle est :

~~~text
PROFILE HUMAIN
     ↓
ENTRER DANS UN SPACE
     ↓
ESPACE CHOISI
     ↓
AGIR COMME
     ↓
EXPÉRIENCE SPACE
~~~

Le Profile reste la personne globale.

Le Space est le contexte collectif dans lequel elle agit.

## 4.1. Agir comme est toujours Space-scoped

`Agir comme` ne liste jamais tous les rôles que la personne possède dans Makolo.

Il expose seulement les responsabilités pertinentes **dans le Space courant**, directement ou dans les scopes opérationnels de ce Space.

Exemple :

~~~text
Mulykap

Agir comme :
✓ Tout ce que je peux faire ici
  Administration
  Exploitation
  Finance
  Contrôle des accès
  Scanner · Départ Lubumbashi → Kolwezi
~~~

Dans un autre Space, la liste peut être totalement différente.

## 4.2. Valeur par défaut

La valeur par défaut est :

> **Tout ce que je peux faire ici**

Makolo compose alors toutes les réalités et actions que la personne est effectivement autorisée à voir ou accomplir dans ce Space.

Il ne fabrique pas un dashboard par rôle.

## 4.3. Le filtre ne crée aucune autorité

Choisir :

> Finance

n’accorde aucun droit Finance.

Choisir :

> Scanner

n’accorde aucune Permission de scan.

Le filtre réduit la lecture cognitive. Les Permissions et Mandates continuent de gouverner les données et les actions côté serveur.

## 4.4. Le scope doit être compréhensible

Lorsque le rôle seul est ambigu, l’UX peut montrer la portée humaine :

~~~text
Scanner · Départ Lubumbashi → Kolwezi

Responsable · Programme Génie civil
~~~

Le terme technique `scope` n’a pas besoin d’être exposé.

---

# 5. Archétypes Space

Les huit archétypes initiaux restent :

1. `generic`
2. `creative`
3. `media`
4. `education`
5. `commerce`
6. `service_provider`
7. `transport_operator`
8. `community`

Un archétype est un **centre de gravité durable**.

Il ne devient jamais :

- une Permission ;
- un Mandate ;
- un Entitlement ;
- une forme juridique ;
- une profession globale ;
- une whitelist de verticales ;
- une seconde vérité métier.

La réalité opérationnelle reste distincte :

~~~text
ARCHETYPE
= manière principale de fonctionner

OPERATIONAL FOOTPRINT
= ce que le Space utilise réellement
~~~

L’archétype influence notamment :

- vocabulaire ;
- ordre de priorité naturel ;
- composition de la porte opérationnelle ;
- densité relative des préoccupations ;
- suggestions de création pertinentes.

Il ne restreint jamais les verticales réellement opérées.

---

# 6. Six préoccupations humaines substantielles

L’expérience Space repose sur six préoccupations humaines stables.

## 6.1. Produire / opérer

> Qu’est-ce que notre organisation fait réellement exister et fonctionner ?

## 6.2. Servir / délivrer

> Qu’est-ce que nous devons accomplir pour les personnes qui comptent sur nous ?

## 6.3. Coordonner

> Avec qui agissons-nous, qui fait quoi et qui peut faire quoi ?

## 6.4. Possibilités

> Qu’est-ce qui pourrait permettre au Space d’avancer ?

Cette préoccupation remplace conceptuellement le mot trop étroit `Développer`.

Elle couvre aussi bien une entreprise, une école, un artiste, un média, une ONG ou un transporteur.

## 6.5. Piloter

> Est-ce que cela fonctionne ? Qu’est-ce qui dérive ? Que faut-il ajuster ?

## 6.6. Gouverner

> Qui sommes-nous ? Qui peut agir ? Comment préserver la continuité de l’organisation ?

---

# 7. Maintenant est une méta-préoccupation

`Maintenant` n’est pas de même nature que les six préoccupations précédentes.

Il répond :

> **Parmi tout ce qui existe dans ce Space et que je suis autorisé à traiter, qu’est-ce qui mérite mon attention maintenant ?**

Donc :

~~~text
                    MAINTENANT
              sélection de l’attention
                        ↓
 ┌────────────┬────────────┬──────────────┐
 Produire     Délivrer     Coordonner
 ├────────────┼────────────┼──────────────┤
 Possibilités Piloter      Gouverner
 └────────────┴────────────┴──────────────┘
~~~

`Maintenant` n’est ni :

- un dashboard ;
- une todo list générique ;
- une inbox ;
- un feed ;
- une copie des Notifications.

---

# 8. Familles de responsabilités humaines

Les familles suivantes sont des **perspectives UX / read-models**, pas nécessairement de nouveaux Roles persistants.

## A. Orientation / stewardship / direction collective

Vision globale, arbitrage, continuité, décision.

## B. Production / exploitation

Fait fonctionner les Activities, programmes, départs, opérations ou productions.

## C. Délivrance / accompagnement / traitement

Accomplit les engagements envers des personnes concrètes.

## D. Relations / possibilités

Développe publics, partenaires, collaborations et possibilités externes.

## E. Économique / finance

Traite commandes, paiements, financement et obligations économiques.

## F. Terrain / accès / contrôle

Exécute au bord du réel : admission, scan, contrôle, passage, opération terrain.

## G. Organisation / administration

Structure l’organisation, les équipes, responsabilités, Mandates et paramètres institutionnels.

Ces perspectives peuvent être dérivées plus tard depuis les Mandates, Assignments, scopes et contextes réels.

Elles ne deviennent pas une taxonomie de professions.

---

# 9. Déformation naturelle selon la responsabilité

Tendance conceptuelle :

| Responsabilité | Produire | Délivrer | Coordonner | Possibilités | Piloter | Gouverner |
|---|---:|---:|---:|---:|---:|---:|
| Orientation / direction | ↑↑ | ↑↑ | ↑↑ | ↑↑ | ↑↑↑ | ↑↑↑ |
| Production / exploitation | ↑↑↑ | ↑↑ | ↑↑ | ↑ | ↑↑ | — |
| Délivrance / traitement | ↑ | ↑↑↑ | ↑↑ | ↑ | ↑↑ | — |
| Relations / possibilités | ↑ | ↑ | ↑↑ | ↑↑↑ | ↑↑ | — |
| Finance / économique | ↑ | ↑↑ | ↑ | ↑ | ↑↑↑ | ↑ |
| Terrain / contrôle | ↑↑ | ↑↑↑ | ↑↑ | ○ | ↑ | ○ |
| Administration | ○ | ○ | ↑↑↑ | ↑ | ↑↑ | ↑↑↑ |

Ces tendances ne sont jamais des Permissions.

---

# 10. Situations Space

Les situations Space sont des lectures UX dérivées de faits canoniques.

Elles ne nécessitent pas par défaut un modèle persistant `SpaceSituation`.

## 10.1. Une décision nous attend

Quelqu’un ou quelque chose attend une décision réelle.

Exemples :

- Request ;
- inscription ;
- exception opérationnelle ;
- décision d’accès ;
- relation à accepter ;
- arbitrage.

## 10.2. Quelqu’un attend quelque chose de nous

Le Space a un engagement concret à tenir.

Exemples :

- prestation ;
- transport ;
- admission ;
- réponse ;
- remise ;
- traitement d’une demande.

## 10.3. Quelque chose doit être prêt bientôt

Une action future risque de mal se dérouler si rien n’est préparé.

Exemples :

- Occurrence ;
- départ ;
- session ;
- événement ;
- véhicule ;
- Resource ;
- Requirement opérateur ;
- Access ;
- responsable.

## 10.4. Ça commence

Une Occurrence devient actuelle.

## 10.5. Nous sommes en train de l’opérer

L’action réelle est actuellement en cours.

## 10.6. Quelque chose bloque

Une condition empêche la progression.

## 10.7. Quelque chose dévie

Un fait réel ne suit plus ce qui était attendu.

Exemples :

- incident ;
- retard ;
- paiement échoué ;
- automation échouée ;
- opération interrompue.

## 10.8. Une ressource devient critique

Capacity, disponibilité, place, ressource, véhicule, financement, argent dû ou autre contrainte approche d’un seuil significatif.

## 10.9. Il faut passer le relais

Une responsabilité doit changer de main ou l’autorité disponible ne permet pas de terminer ce qui est attendu.

## 10.10. Une possibilité utile vient d’apparaître

Une possibilité suffisamment pertinente peut faire avancer le Space.

## 10.11. Nous devons ajuster notre manière de fonctionner

Les faits accumulés suggèrent qu’un ajustement de gestion mérite examen.

## 10.12. C’est accompli

Une action réelle a atteint son niveau d’achèvement propriétaire.

Cette situation peut apparaître brièvement mais ne doit pas remplir artificiellement `Maintenant`.

## 10.13. Tout est en ordre

Lorsque rien ne demande réellement une intervention :

> **Tout est en ordre. ✓**

Makolo ne doit pas inventer du contenu pour empêcher cet état.

---

# 11. Règle de priorité UX

La priorité n’est pas l’ordre du menu.

Elle ne doit pas être codée conceptuellement comme un simple score arbitraire.

Le contrat d’ordonnancement est :

~~~text
1. AUTORITÉ
   Puis-je connaître ou agir sur ce fait ?

2. SITUATION
   Se passe-t-il réellement quelque chose ?

3. CONSÉQUENCE
   Que se passe-t-il si personne n’agit ?

4. TEMPS
   Quand cela devient-il pertinent ?

5. RESPONSABILITÉ
   Est-ce dans ma responsabilité actuelle ?

6. ARCHÉTYPE
   Est-ce naturellement central ici ?

7. OPERATIONAL FOOTPRINT
   Le Space utilise-t-il réellement cette capacité ?

8. CONTINUITÉ
   Est-ce lié à ce que je suis déjà en train de faire ?
~~~

L’autorité décide si un fait peut entrer dans le corpus.

La priorité décide où il se place une fois admissible.

## 11.1. Niveaux conceptuels

### P0 — Agir maintenant

Intervention réelle requise.

### P1 — Préparer / suivre de près

Risque prochain ou préparation nécessaire.

### P2 — Travail courant

Cœur normal du métier.

### P3 — Possibilités / amélioration

Évolution, opportunité ou amélioration sans urgence immédiate.

### P4 — Gouvernance / profondeur

Configuration durable et institutionnelle.

Un fait P4 peut temporairement remonter si sa conséquence devient critique.

## 11.2. Algorithmes futurs

Le ranking définitif pourra provenir de moteurs d’intelligence / Univers Molongo.

L’UX Space ne calcule pas cet algorithme.

Elle définit :

- les candidats admissibles ;
- les familles de situations ;
- les informations nécessaires à leur représentation ;
- la nécessité d’une explication humaine.

Makolo ne doit pas afficher un score mystérieux comme vérité.

Il doit pouvoir dire par exemple :

> Départ dans 25 minutes et aucun véhicule n’est affecté.

et non :

> Priorité 93 %.

---

# 12. Architecture sémantique et shell visible

Les six préoccupations restent l’architecture sémantique de l’expérience Space :

~~~text
MAINTENANT
MONDE OPÉRATIONNEL CONTEXTUALISÉ
PERSONNES & RELATIONS
POSSIBILITÉS
PILOTER
GOUVERNER
~~~

Elles répondent à six questions différentes et restent utiles pour concevoir les projections, les profondeurs et les responsabilités.

Elles ne doivent toutefois pas être copiées mécaniquement dans la navigation primaire.

## 12.1. Un seul Makolo, plusieurs contextes d’acteur

Entrer dans un Space ne signifie jamais quitter Makolo pour une autre application.

Le shell de marque et d’identité reste celui de Makolo :

~~~text
Makolo                                             Avatar humain
~~~

Le logo / Makolo Mark à gauche et l’Avatar à droite appartiennent à l’application globale.

L’Avatar reste toujours la personne authentifiée, même lorsqu’elle agit au nom d’un Space.

~~~text
Avatar = personne connectée
Space = acteur collectif courant
~~~

Un Space ne possède ni session humaine propre ni Avatar de compte collectif.

La sélection du Space change le contexte d’action, pas l’identité de l’application.

## 12.2. Changement d’acteur

Le menu global peut exposer :

~~~text
Agir comme

Moi
Mulykap
Fondation Upendo
Studio K
...
~~~

Sélectionner un Space ouvre directement son expérience, normalement sur Maintenant.

Le logo Makolo ramène au Maintenant de l’acteur courant. Il ne force pas un retour au contexte personnel.

Pour revenir au contexte personnel, la personne choisit explicitement :

> Agir comme → Moi

## 12.3. Contexte Space persistant

Une fois dans un Space, le shell doit rendre visibles sans lourdeur :

~~~text
Mulykap ▾
Toutes mes responsabilités ▾
~~~

Le premier contrôle permet de changer de Space.

Le second réduit la lecture cognitive aux responsabilités de la personne dans ce Space précis.

Il peut proposer, selon les autorités réelles :

~~~text
Toutes mes responsabilités
Exploitation
Finance
Administration
Contrôle · Départ 14 h
~~~

Il n’affiche jamais les responsabilités détenues dans d’autres Spaces.

Cette sélection ne crée aucune Permission ni aucun Mandate.

## 12.4. Navigation primaire visible

La navigation mobile Space reprend la grammaire Makolo personnelle sans copier son contenu métier :

~~~text
PROFIL
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi

SPACE
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
~~~

La navigation Space comporte donc quatre destinations et la même action centrale Makolo Mark.

### Maintenant

Question visible :

> Qu’est-ce qui mérite notre attention maintenant ?

### Découvrir

Découvrir est le libellé utilisateur du territoire conceptuel Possibilités.

Question visible :

> Qu’est-ce qui pourrait nous aider à avancer ?

Le terme Possibilités reste utile dans l’architecture et les algorithmes ; il n’est pas imposé comme jargon de navigation.

### Makolo Mark

Le même Makolo Mark est utilisé dans tous les contextes.

Son sens reste :

> J’ai quelque chose à donner à Makolo.

Lorsque l’acteur courant est un Space, l’intention est interprétée dans le contexte de ce Space et de l’autorité réelle de la personne.

Le Mark ne crée ni capacité ni privilège.

### Métier

Le quatrième repère représente le monde opérationnel principal du Space.

Il porte un vocabulaire naturel déterminé par l’archétype et la réalité opérationnelle.

### Nous

Nous est le libellé visible de la préoccupation institutionnelle / gouvernance.

Question visible :

> Qui sommes-nous, avec qui fonctionnons-nous et comment sommes-nous organisés ?

Nous est le miroir collectif de Moi.

~~~text
Moi ↔ Nous
~~~

Nous ne signifie pas Settings et ne transforme pas le Space en fiche administrative.

## 12.5. Vocabulaire métier primaire par archétype

| Archétype | Libellé primaire recommandé | Icône sémantique candidate |
|---|---|---|
| generic | Activités | calendar-range |
| creative | Créations | palette |
| media | Productions | newspaper |
| education | Programmes | graduation-cap |
| commerce | Commerce | shopping-bag |
| service_provider | Prestations | handshake |
| transport_operator | Transport | bus-front |
| community | Initiatives | heart-handshake |

Ces icônes sont des repères sémantiques, pas encore un pixel contract définitif.

Le contenu interne peut employer un vocabulaire plus spécialisé :

- Transport peut contenir Exploitation, Routes, Départs, Véhicules et Contrôle ;
- Commerce peut contenir Offres, Commandes, Disponibilité et Remise ;
- Programmes peut contenir Sessions, Inscriptions, Conditions, Ressources et Groupes ;
- Initiatives peut contenir Activities, événements, programmes et actions terrain.

## 12.6. Icônes stables du shell

Les repères dont le sens reste identique conservent leur identité entre Profil et Space :

| Destination | Icône sémantique |
|---|---|
| Maintenant | clock-3 |
| Découvrir | compass |
| Makolo | Makolo Mark officiel |
| Nous | users-round |

Moi conserve une représentation personnelle telle que user-round.

Cette répétition est volontaire : elle renforce l’impression d’être toujours dans Makolo.

## 12.7. Personnes & relations et Piloter

Personnes & relations et Piloter restent des surfaces majeures.

Elles ne sont plus obligées d’occuper la navigation basse permanente.

Elles peuvent être atteintes depuis :

- Maintenant lorsqu’une situation le justifie ;
- le monde métier ;
- Nous ;
- Découvrir ;
- la recherche ;
- une profondeur déjà déterminée ;
- un deep link légitime.

Cette accessibilité ne transfère jamais leur propriété métier à Nous ou à une autre surface.

## 12.8. Nous n’est pas un écran Paramètres

La racine Nous doit d’abord être humaine et collective.

Elle peut donner une lecture compacte de :

~~~text
notre identité
notre équipe
nos responsabilités
nos relations
notre confiance / vérification
notre fonctionnement collectif
~~~

Les réglages, l’abonnement, les connexions, l’archivage et les détails d’autorité sont des profondeurs.

## 12.9. Mobile et desktop

Sur mobile, la navigation primaire est normalement une bottom navigation :

~~~text
Maintenant | Découvrir | [Mark] | Métier | Nous
~~~

Sur desktop, les mêmes repères peuvent être présentés dans un rail permanent avec davantage d’espace.

Le desktop peut également rendre Piloter plus directement accessible lorsque la responsabilité courante le justifie.

Il ne réintroduit jamais une navigation primaire organisée par modules backend.

## 12.10. Surfaces contextuelles majeures

Jour J et Live restent hors de la navigation primaire.

Une Occurrence actuelle peut ouvrir Jour J et, lorsque de la vérité réellement live existe, Makolo Live.

Une surface immersive peut réduire temporairement le chrome global, mais elle reste identifiable comme :

~~~text
Makolo
+ Space courant
+ contexte métier / Occurrence
~~~


# 13. Contrat transversal des portes

Une porte apparaît lorsque trois conditions sont généralement réunies :

~~~text
autorité pertinente
+
faits ou capacité réellement présents
+
préoccupation raisonnablement liée
à la responsabilité actuelle
~~~

Exception :

- `Maintenant` reste la racine naturelle du contexte Space ;
- le monde opérationnel reste retrouvable pour les personnes qui opèrent réellement le Space.

L’UX ne doit pas réordonner totalement son architecture à chaque rôle.

Elle conserve une structure reconnaissable et adapte :

- visibilité ;
- contenu ;
- densité ;
- actions ;
- langage.

---

# 14. Porte 1 — Maintenant

## Mission

> **Qu’est-ce qui mérite mon attention dans ce Space ?**

`Maintenant` est une projection d’attention.

## 14.1. La racine doit permettre de comprendre

Pour chaque situation importante :

~~~text
Quoi ?
Pourquoi maintenant ?
Quelle conséquence ?
Quelle action possible ?
Dans quel contexte ?
~~~

Exemple :

> **Départ Lubumbashi → Kolwezi · 14 h**  
> Aucun véhicule n’est affecté.  
> Départ dans 35 minutes.  
> **Préparer**

## 14.2. Familles admissibles

- Décider ;
- Faire avancer ;
- Préparer ;
- Jour J ;
- Débloquer ;
- Réagir ;
- Surveiller ;
- Passer le relais ;
- Saisir une possibilité ;
- Ajuster ;
- Accompli brièvement.

## 14.3. Sections possibles

Seulement lorsqu’elles ont du contenu :

- À traiter ;
- À surveiller ;
- Jour J / actuellement ;
- Prochainement ;
- possibilité réellement urgente ou fortement pertinente.

Les sections vides disparaissent.

## 14.4. Interdits

La racine ne doit jamais devenir :

- liste exhaustive de modules ;
- copie des Notifications ;
- dashboard de KPI ;
- feed chronologique ;
- liste de toutes les Occurrences ;
- liste de toutes les commandes ;
- score algorithmique opaque ;
- remplissage artificiel.

## 14.5. Actions principales

Selon le domaine :

- agir directement si l’action est simple et sûre ;
- ouvrir le contexte canonique ;
- ouvrir Jour J ;
- résoudre un blocage ;
- décider ;
- passer le relais ;
- approfondir dans la porte correspondante.

## 14.6. État vide

> **Tout est en ordre. ✓**  
> Rien ne demande votre intervention maintenant.

## 14.7. Erreur partielle

Une source qui ne se rafraîchit pas ne doit pas nécessairement rendre tout `Maintenant` inutilisable.

Makolo conserve les informations encore fiables et indique clairement ce qui n’a pas pu être actualisé.

## 14.8. Déclinaison archétypale

| Archétype | Sources d’attention naturellement fortes |
|---|---|
| generic | Activities proches, demandes, engagements, lieux |
| creative | création/événement imminent, prestation, demandes, offres |
| media | production/Activity, événement, relation ou public réellement actionnable |
| education | session, admissions, Requirements, Resources, Capacity, Access |
| commerce | commandes à délivrer, disponibilité, Payments bloquants, Capacity |
| service_provider | demandes, dossiers, blocages, relais, prestations |
| transport_operator | départs, véhicules, Capacity, Access, incidents, Jour J |
| community | initiative, activité terrain, décision, Funding/ressource critique, partenaire |

---

# 15. Porte 2 — Monde opérationnel contextualisé

`Opérer` est le nom d’architecture de cette préoccupation.

Ce n’est pas nécessairement le mot visible.

## Mission

> **Qu’est-ce que ce Space fait réellement exister, prépare, exécute et délivre ?**

C’est la principale surface durable de travail.

## 15.1. La racine doit permettre de comprendre

- ce que le Space opère ;
- ce qui est à préparer ;
- ce qui arrive ;
- ce qui est en cours ;
- ce qui est bloqué ;
- ce qui est terminé ;
- où entrer pour poursuivre le travail réel.

## 15.2. Horizon transversal

Lorsque pertinent :

~~~text
À préparer
À venir
En cours
Terminés
~~~

`En cours` est donc une dimension du monde opérationnel Space, pas une septième porte permanente.

## 15.3. Interdits

- catalogue de modèles backend ;
- domaines absents de l’Operational Footprint ;
- Finance globale sans lien opérationnel ;
- CRM global ;
- Analytics global ;
- Settings ;
- task manager générique.

## 15.4. Création

La création reste contextuelle.

Pas de bouton universel `+ Créer` ouvrant toute la taxonomie Makolo.

---

# 16. Monde opérationnel par archétype

## 16.1. generic — Activités

Langage principal :

> **Activités**

Composition possible :

- activités ;
- à préparer ;
- à venir ;
- en cours ;
- demandes associées ;
- lieux pertinents ;
- terminées.

Les verticales réellement utilisées apparaissent lorsqu’elles existent.

## 16.2. creative — Créations & activités

Langage principal :

> **Créations & activités**

Composition :

- créations/Activities ;
- événements ;
- prestations ;
- Occurrences ;
- offres réellement opérées.

La création/production domine tant que commerce et autres domaines ne deviennent pas réellement centraux.

Interdits :

- feed ;
- story ;
- portfolio parallèle générique ;
- média orphelin.

## 16.3. media — Productions & activités

Langage principal :

> **Productions & activités**

Composition :

- productions/Activities ;
- événements ;
- prestations éventuelles ;
- Occurrences.

Publics, audiences et partenaires restent surtout relationnels.

Aucun CMS social générique n’est déduit de l’archétype.

## 16.4. education — Programmes & sessions

Langage principal :

> **Programmes & sessions**

Composition forte :

~~~text
Programme
  ├── Sessions
  ├── Inscriptions / demandes
  ├── Conditions
  ├── Formulaires
  ├── Ressources
  ├── Groupes / cohortes réels
  └── Accès
~~~

Une racine programme doit pouvoir expliquer :

- prochaine session ;
- préparation ;
- personnes en attente ;
- conditions manquantes ;
- ressources nécessaires.

Elle ne doit pas exposer ces éléments comme une simple collection de modules indépendants.

## 16.5. commerce — Offres & commandes

Langage principal :

> **Offres & commandes**

Chaîne conceptuelle :

~~~text
ce que nous rendons obtenable
→ offre
→ demande / commande
→ préparation / disponibilité
→ remise / réalisation
→ Obtention accomplie
~~~

Sections possibles :

- offres ;
- commandes à traiter ;
- à préparer ;
- à remettre / rendre disponible ;
- contraintes de Capacity ;
- terminées.

Payment apparaît lorsqu’il compte réellement dans la chaîne.

Invariant :

> une commande ou un paiement ne suffit jamais à conclure automatiquement l’Obtention.

## 16.6. service_provider — Prestations

Langage principal :

> **Prestations**

Composition :

- prestations proposées ;
- demandes ;
- à préparer ;
- en traitement ;
- bloquées ;
- à délivrer ;
- terminées.

Un dossier de prestation peut composer :

- personne concernée ;
- Requirements ;
- étapes utiles ;
- responsable ;
- ressources / pièces ;
- Payment si pertinent ;
- résultat.

La surface doit ressembler à la gestion professionnelle d’un service, pas à une navigation Journey technique.

## 16.7. transport_operator — Exploitation

Langage principal :

> **Exploitation**

Composition :

- aujourd’hui ;
- départs ;
- routes ;
- services ;
- véhicules ;
- lieux.

Un départ devient un contexte fort :

~~~text
Départ
├── préparation
├── Jour J
│   └── Live
├── véhicule
├── Capacity
├── voyageurs / Access selon autorité
├── contrôle
└── incidents
~~~

## 16.8. community — Initiatives & activités

Langage principal :

> **Initiatives & activités**

Composition :

- initiatives ;
- Activities ;
- événements ;
- actions terrain ;
- programmes lorsqu’ils existent réellement.

Groups, Publics et Partners conservent fortement leur sens relationnel.

---

# 17. Porte 3 — Personnes & relations

## Mission

> **Avec qui avançons-nous, dans quelle relation, et qui porte quoi ?**

Cette porte compose plusieurs vérités relationnelles sans inventer un domaine universel `Relation`.

## 17.1. La racine doit préserver les natures de relation

Elle peut composer :

~~~text
Interne
→ équipes / collaborateurs

Collectifs
→ groupes

Relations métier
→ CRM contacts / clients réels

Publics
→ audiences

Écosystème
→ partenaires

Responsabilités
→ lecture humaine des responsabilités autorisées
~~~

## 17.2. Invariant relationnel

~~~text
CRMContact
!= TeamMember
!= GroupMember
!= Partner
!= Mandate holder
!= follower
!= participant
~~~

La même personne peut apparaître dans plusieurs relations distinctes sans être fusionnée conceptuellement.

## 17.3. Sections possibles

Seulement si elles existent :

- équipe ;
- groupes ;
- clients / contacts ;
- publics / audiences ;
- partenaires ;
- autres relations métier réelles.

## 17.4. Interdits

- carnet universel de personnes ;
- participant transformé automatiquement en CRMContact ;
- voyageur transformé automatiquement en client durable ;
- apprenant transformé automatiquement en contact CRM ;
- Membership présenté comme autorité ;
- données privées exposées par simple composition.

## 17.5. Actions principales

Selon autorité :

- ajouter un collaborateur ;
- créer/gérer un groupe ;
- ajouter/gérer un contact CRM ;
- gérer une audience ;
- établir/gérer un Partner ;
- examiner les responsabilités d’un collaborateur.

Chaque mutation reste portée par son domaine propriétaire.

## 17.6. Recherche relationnelle

Une recherche peut réunir plusieurs sources visuellement, mais chaque résultat conserve sa relation réelle.

Exemple :

~~~text
Marie Kalala
Collaboratrice · Exploitation

Marie Kalala
Contact CRM · Client
~~~

## 17.7. Déclinaison archétypale

| Archétype | Accent relationnel |
|---|---|
| generic | Personnes & relations |
| creative | Publics & partenaires |
| media | Publics & partenaires |
| education | Groupes, personnes & partenaires |
| commerce | Clients & relations |
| service_provider | Clients & partenaires |
| transport_operator | Relations ; les voyageurs restent principalement opérationnels |
| community | Communauté & partenaires |

Les termes apprenant, voyageur, bénéficiaire, client, public restent des vocabulaires contextuels, jamais des rôles Profile globaux.

---

# 18. Porte 4 — Possibilités

## Mission

> **Qu’est-ce qui pourrait faire avancer ce Space ?**

Cette porte est l’exploration collective de Makolo.

Elle ne signifie pas automatiquement croissance commerciale.

## 18.1. La racine peut montrer

Des possibilités réelles suffisamment pertinentes :

- Opportunity ;
- Funding ;
- partenaire possible ;
- Activity ;
- lieu ;
- ressource ;
- public/contexte ;
- autre fait canonique permettant une action réelle.

Chaque proposition devrait permettre de comprendre :

~~~text
Qu’est-ce que c’est ?
Pourquoi cela peut concerner ce Space ?
Qu’est-ce que cela pourrait permettre ?
Quelle est la source / réalité ?
Que puis-je faire ensuite ?
~~~

## 18.2. Sections possibles

Selon la réalité :

- pour ce Space ;
- à proximité / dans une zone pertinente ;
- partenariats ;
- financements ;
- publics / débouchés ;
- ressources / lieux ;
- explorer plus largement.

## 18.3. Interdits

- feed infini ;
- popularité comme proxy de pertinence ;
- contenu sans contexte ni finalité ;
- publicité déguisée ;
- possibilité impossible à relier au Space ;
- données privées d’autres Spaces ;
- `trending` comme finalité.

## 18.4. Actions principales

Seulement celles soutenues par le domaine :

- ouvrir ;
- comprendre ;
- répondre / candidater ;
- établir une relation ;
- explorer plus largement.

La porte ne justifie pas à elle seule un modèle persistant générique d’intérêt Space.

## 18.5. État vide

> **Aucune possibilité suffisamment pertinente pour le moment.**

Option possible :

> Explorer plus largement.

Makolo préfère un vide honnête à un remplissage artificiel.

## 18.6. Déclinaison archétypale

### generic

Activities, partenaires, lieux et opportunités compatibles avec le fonctionnement réel.

### creative

Événements, lieux, collaborations, partenaires, prestations, publics pertinents.

### media

Collaborations, partenaires, événements, opportunités éditoriales contextualisées, publics.

### education

Partenaires, ressources, programmes, lieux, possibilités de transmission/formation.

### commerce

Canaux/contextes d’Obtention, partenaires, publics, lieux, débouchés.

### service_provider

Zones, clients/contextes potentiels, partenaires, prestations connexes.

### transport_operator

Dessertes possibles, besoins de mobilité, lieux/stops, partenariats, réseau.

### community

Funding, appels, partenaires, ressources, lieux, mobilisation et opportunités alignées sur la mission.

---

# 19. Porte 5 — Piloter

## Mission

> **Est-ce que cela fonctionne ? Qu’est-ce qui change ? Que devons-nous ajuster ?**

`Piloter` est une surface de recul et de décision.

Elle n’est pas un dashboard obligatoire.

## 19.1. Commencer par le sens

La racine devrait privilégier les signaux utiles avant les graphiques.

Exemples :

> Les départs de 17 h approchent régulièrement de la capacité maximale.

> La majorité des dossiers bloqués s’arrêtent sur la même condition.

> Les commandes prennent plus longtemps à être délivrées cette semaine.

Les métriques expliquent ensuite.

## 19.2. Sections possibles

Selon autorité, archétype et Operational Footprint :

- fonctionnement ;
- demandes / flux ;
- Capacity ;
- délivrance / progression ;
- finance ;
- relations / acquisition ;
- incidents ;
- Automation ;
- tendances.

## 19.3. Interdits

- galerie de KPI ;
- vanity metrics ;
- popularité comme objectif ;
- score global arbitraire du Space ;
- zéro utilisé lorsque la vérité est inconnue ;
- pourcentage sans dénominateur significatif ;
- données sensibles hors autorité ;
- causalité inventée.

Distinction obligatoire :

~~~text
0
!= inconnu
!= indisponible
!= données insuffisantes
~~~

## 19.4. Actions principales

- approfondir un signal ;
- changer une période pertinente ;
- examiner une cause ;
- atteindre la profondeur métier permettant réellement l’ajustement.

Piloter ne devient pas propriétaire des mutations des autres domaines.

## 19.5. États vides

### Données insuffisantes

> **Pas encore assez d’activité pour dégager une tendance utile.**

### Aucun signal particulier

> Le fonctionnement observé ne fait ressortir aucun point particulier sur cette période.

Ce n’est pas le même état que `Tout est en ordre`, qui appartient à l’attention immédiate.

## 19.6. Déclinaison archétypale

| Archétype | Questions naturelles |
|---|---|
| generic | Activities, demandes, Occurrences, participation, blocages |
| creative | activités/événements, prestations, offres, publics légitimes |
| media | productions, audiences utiles, partenaires, événements ; jamais simple popularité |
| education | inscriptions, progression, Requirements, sessions, Capacity, participation |
| commerce | demande, commandes, délivrance, Capacity, Payments, Obtention |
| service_provider | charge, délais, blocages, progression des dossiers, résultats |
| transport_operator | départs, Capacity, Access usage, incidents, exploitation, finance |
| community | initiatives, participation, mobilisation, Funding, partenaires, mission observable |

---

# 20. Porte 6 conceptuelle — Gouverner / surface visible Nous

## Mission

> **Qui sommes-nous ? Qui peut agir ? Comment cette identité collective reste-t-elle durable, sûre et gouvernable ?**

Cette porte est institutionnelle.

Elle n’est pas le cœur du travail quotidien.

## 20.1. Identité

La racine peut représenter :

- nom ;
- description ;
- contacts généraux ;
- présence publique ;
- lieux généraux appropriés ;
- archétype ;
- lifecycle.

## 20.2. Confiance

- vérification ;
- éléments Trust appropriés.

## 20.3. Organisation

- Team ;
- collaborateurs ;
- responsabilités ;
- Mandates/autorités via langage humain ;
- ownership.

## 20.4. Produit

- Subscription ;
- Entitlements pertinents.

## 20.5. Continuité

- connexions / intégrations ;
- audit/histoire administrative lorsque légitime ;
- archivage / restauration.

## 20.6. Ce qui n’est pas intrinsèquement propriété de cette porte

Même lorsqu’ils existent dans le Space :

- routes ;
- véhicules ;
- produits ;
- services ;
- prix ;
- disponibilité / stock ;
- Requirements ;
- documents métier ;
- Payments ;
- clients ;
- programmes ;
- autres vérités de domaines propriétaires.

## 20.7. Interdits d’autorité

La porte ne doit jamais produire :

~~~text
TeamMembership → Permission
GroupMembership → Permission
Archetype → Permission
Entitlement → Permission
Creator → Owner éternel
~~~

Changer d’archétype ne détruit pas l’historique opérationnel.

## 20.8. Actions principales

Permission-gated :

- modifier l’identité ;
- modifier la projection publique ;
- changer l’archétype ;
- gérer Team ;
- gérer responsabilités et autorité ;
- gérer ownership ;
- gérer Trust / vérification ;
- gérer abonnement ;
- gérer connexions ;
- archiver / restaurer.

## 20.9. État vide

Nous n’est normalement jamais vide puisqu’une identité collective existe.

Les sous-sections peuvent être vides.

Exemples :

> Aucune équipe secondaire.

> Aucune connexion configurée.

Mais :

~~~text
aucune Team
!= aucune autorité

aucune donnée visible
!= absence de donnée réelle
~~~

## 20.10. Déclinaison archétypale

Contrairement au monde opérationnel, les huit archétypes restent relativement proches dans cette porte.

- `generic` : identité généraliste ;
- `creative` : identité créative/publique plus saillante ;
- `media` : identité éditoriale/publique et Trust plus saillants ;
- `education` : identité institutionnelle et Trust, sans accréditation fictive ;
- `commerce` : identité commerciale, sans absorber catalogue/orders ;
- `service_provider` : identité professionnelle, sans absorber prestations/tarifs ;
- `transport_operator` : identité opérateur, routes/véhicules restant dans Exploitation ;
- `community` : mission/identité publique plus saillante, sans déduire statut légal, bénéficiaires ou Funding.

---

# 21. Jour J Space

Jour J n’est pas une septième porte permanente.

Il appartient à une Occurrence devenue actuelle.

Un Space peut avoir plusieurs Jour J simultanément.

Exemple :

~~~text
Space transport

Jour J — départ A
  └── Live A

Jour J — départ B
  └── Live B

Jour J — départ C
  └── Live C
~~~

Le Space entier ne devient jamais globalement `Live`.

## 21.1. Accès à Jour J

Jour J peut être atteint depuis :

- Maintenant ;
- monde opérationnel ;
- notification légitime ;
- deep link ;
- contexte métier déjà déterminé.

## 21.2. Choix humain

La présence de plusieurs Jour J ne doit pas voler automatiquement l’écran.

`Maintenant` peut dire :

> 5 départs sont actuellement actifs, 2 demandent votre attention.

La personne choisit le Jour J à ouvrir.

Une fois choisi, il peut temporairement devenir la surface dominante pour cette personne.

## 21.3. Perspective opérateur vs participant

Même Occurrence, vérités canoniques communes, projections différentes.

### Participant

- où aller ;
- Access ;
- Placement ;
- Queue ;
- prochain mouvement personnel ;
- expérience personnelle.

### Opérateur Space

- préparation ;
- personnes attendues dans la limite d’autorité ;
- Capacity ;
- AccessUse ;
- contrôle ;
- incidents ;
- ressources ;
- état opérationnel.

Il ne faut jamais créer deux Occurrences ou deux vérités métier pour satisfaire ces perspectives.

---

# 22. Makolo Live

Makolo Live appartient à Jour J.

Relation :

~~~text
Occurrence
  → Jour J
      → Live
      → autres profondeurs opérationnelles
~~~

Live représente :

> **ce qui se déroule effectivement maintenant dans cette Occurrence.**

Live ne signifie pas automatiquement vidéo.

Il peut être :

- opérationnel ;
- spatial ;
- temporel ;
- médiatique uniquement si une source média canonique existe.

Distinctions obligatoires :

~~~text
planned
estimated
observed
live
unknown
unavailable
~~~

Un horaire planifié n’est pas une observation Live.

Une position non observée ne doit pas être inventée.

Une donnée indisponible ne devient pas une donnée sûre.

---

# 23. Continuité et provenance de navigation

L’identité canonique d’une réalité reste distincte de la provenance de navigation.

Exemple :

~~~text
Maintenant
→ paiement échoué
→ commande
→ paiement
→ corriger
→ retour au contexte commande
~~~

Pas :

~~~text
paiement corrigé
→ accueil générique Payments
→ l’utilisateur doit reconstruire son intention
~~~

Une profondeur conserve autant que possible :

1. le Space ;
2. la responsabilité actuelle ;
3. le contexte d’origine.

Le bouton retour revient à l’origine réelle lorsque cette origine existe encore.

---

# 24. Recherche Space

La recherche n’est pas une septième porte.

Elle appartient au shell Space.

Question :

> **Rechercher dans cet Espace**

Elle est :

- Space-scoped ;
- authority-first ;
- éventuellement réduite par `Agir comme`.

Elle peut trouver plusieurs natures de réalités mais les résultats sont présentés humainement.

Exemple :

~~~text
Exploitation
Personnes
Commandes
Lieux
Programmes
~~~

plutôt que seulement :

~~~text
TransportRoute
CRMContact
CommerceOrder
SpacePlace
Activity
~~~

Les recherches spécialisées restent disponibles dans les profondeurs.

---

# 25. Création contextuelle

La création appartient au contexte où son sens est évident.

Exemples :

~~~text
Exploitation
→ Nouveau départ
→ Nouvelle route
→ Nouveau véhicule
~~~

~~~text
Programmes & sessions
→ Nouveau programme
→ Nouvelle session
~~~

~~~text
Personnes & relations
→ Ajouter un collaborateur
→ Créer un groupe
~~~

Les actions proposées dépendent :

- de l’autorité ;
- du Space ;
- de la responsabilité sélectionnée ;
- de l’archétype ;
- du contexte courant.

L’archétype n’accorde jamais la possibilité métier de créer par lui-même.

---

# 26. Loading

Le chargement doit confirmer que le système travaille sans créer d’attente perçue inutile.

Principes :

- pas de loader pour une réponse quasi instantanée ;
- feedback local pour une attente courte ;
- skeleton ou indicateur local lorsque l’attente devient perceptible ;
- progression déterminée uniquement si mesurable ;
- conserver les données déjà disponibles lors d’un refresh lorsqu’elles restent utilisables ;
- verrouiller une double soumission lorsqu’elle serait dangereuse.

Préférer :

~~~text
contenu actuel
+ indicateur discret
→ contenu mis à jour
~~~

à :

~~~text
contenu
→ vide
→ skeleton
→ contenu
~~~

---

# 27. Empty states

Un écran vide peut signifier quatre choses différentes :

## 27.1. Initialisation

Aucune donnée n’a encore été créée.

L’UX explique brièvement le contexte et propose l’action principale si elle est autorisée.

## 27.2. Résultat de filtre

Des données existent mais aucune ne correspond aux critères.

Les critères restent visibles et peuvent être réinitialisés.

## 27.3. Achèvement

Rien ne nécessite d’action.

Pour Maintenant :

> **Tout est en ordre. ✓**

## 27.4. Indisponibilité contextuelle

Une capacité n’existe pas ou n’est pas pertinente dans ce contexte.

Elle ne doit pas être présentée comme une erreur.

---

# 28. Success

Une action réussie doit confirmer uniquement le niveau réellement atteint.

Ne pas afficher :

> Envoyé

si le système sait seulement que l’action a été mise dans une file locale.

Une action structurelle peut :

- modifier clairement l’état ;
- montrer la prochaine étape ;
- confirmer avec sobriété.

Makolo évite par défaut :

- confettis ;
- gamification ;
- célébration disproportionnée.

---

# 29. Error et recovery

Une erreur importante répond :

1. Qu’est-ce qui n’a pas fonctionné ?
2. Qu’est-ce qui a été conservé ?
3. Que puis-je faire maintenant ?

Une erreur bloquante reste visible tant qu’elle nécessite une action.

Ne jamais exposer :

- stack trace ;
- message backend brut ;
- secret ;
- identifiant interne inutile.

Une erreur de champ reste proche du champ.

Une erreur globale reste au niveau de la surface ou de l’action concernée.

Une perte de réseau ne transforme pas automatiquement une surface possédant encore des données utilisables en écran d’erreur total.

---

# 30. Responsabilité sans autorité

L’UX doit savoir représenter le cas :

> cette personne est responsable, mais ne possède pas l’autorité nécessaire pour cette action.

Elle ne doit ni :

- accorder implicitement l’autorité ;
- masquer silencieusement le problème ;
- se limiter à un 403 incompréhensible lorsque le contexte peut être expliqué.

Exemple :

> Cette décision nécessite une autorité que vous n’avez pas actuellement.

Lorsque la vérité et la confidentialité le permettent, Makolo peut indiquer la prochaine voie légitime :

- personne/role autorisé ;
- passage de relais ;
- demande d’intervention ;
- retour au contexte.

---

# 31. Historique

L’historique n’est pas une septième porte permanente Space.

Il reste une dimension temporelle transverse.

Exemples :

~~~text
Prestations
→ En cours / Terminées

Départs
→ À venir / Passés

Programmes
→ Actuels / Historique

Commandes
→ Actives / Terminées
~~~

Piloter peut exploiter l’histoire.

Jour J ne devient pas une archive permanente après la fin de l’Occurrence.

---

# 32. Densité d’information

Tendance conceptuelle :

| Surface | Densité |
|---|---|
| Maintenant | faible |
| Jour J | moyenne / focalisée |
| Live | élevée mais strictement pertinente |
| Monde opérationnel | moyenne à élevée |
| Personnes & relations | moyenne |
| Possibilités | moyenne / exploratoire |
| Piloter | élevée mais structurée |
| Nous | moyenne / institutionnelle |

Makolo ne doit pas être dense partout simplement parce qu’il s’agit d’un outil professionnel.

---

# 33. Mobile et desktop

Cette spécification ne définit pas encore le responsive.

Elle fixe seulement la hiérarchie commune :

~~~text
Space
→ responsabilité
→ porte
→ contexte métier
→ profondeur
~~~

Mobile n’est pas une console desktop compressée.

Desktop n’est pas un téléphone étiré.

Les deux restent projections des mêmes vérités et des mêmes contrats d’expérience.

---

# 34. Hiérarchie finale de l’expérience Space

Le système UX distingue désormais clairement architecture sémantique et navigation visible.

~~~text
NIVEAU 0 — CONTEXTE COLLECTIF
Space courant
+ responsabilités dans ce Space

NIVEAU 1 — NAVIGATION PRIMAIRE VISIBLE
Maintenant
Découvrir
Makolo Mark
Métier contextualisé
Nous

NIVEAU 1B — SURFACES MAJEURES SECONDAIRES
Personnes & relations
Piloter
Recherche
autres profondeurs légitimes

NIVEAU 2 — CONTEXTES MÉTIER
Programme
Départ
Prestation
Initiative
Offre
Commande
etc.

NIVEAU 3 — PROFONDEURS CANONIQUES
Journey
Requirement
Access
Payment
Capacity
Partner
CRM
etc.

CONTEXTE TEMPOREL MAJEUR
Occurrence
→ Jour J
→ Live
~~~

Correspondance conceptuelle :

~~~text
Possibilités → Découvrir
Gouverner / identité collective → Nous
Produire / délivrer → métier contextualisé
Coordonner → Relations et projections contextuelles
Piloter → surface majeure secondaire
~~~


# 35. Anti-features UX Space

L’expérience Space ne doit pas devenir :

- une console organisée uniquement par bounded contexts ;
- un ERP générique ;
- un task manager ;
- un dashboard KPI permanent ;
- un réseau social d’organisations ;
- un feed ;
- une timeline générique ;
- un catalogue de modules ;
- un système de popularité ;
- un moteur d’engagement artificiel ;
- un second modèle de Permissions ;
- un second modèle de responsabilités ;
- un second CRM ;
- un second Analytics ;
- un second moteur Live ;
- un second historique métier ;
- un système où l’archétype crée automatiquement des faits ;
- une expérience différente au point de devenir huit applications indépendantes.

---

# 36. Ce qui est universel et ce qui est contextuel

## Universel

- un seul shell Makolo pour Profil et Space ;
- logo / Makolo Mark global et Avatar humain stables ;
- Space choisi avant le filtre de responsabilité ;
- responsabilités limitées au Space courant ;
- Toutes mes responsabilités comme lecture par défaut lorsqu’elle est légitime ;
- navigation primaire Space : Maintenant / Découvrir / Mark / métier / Nous ;
- Maintenant comme sélection de l’attention ;
- Découvrir comme langage visible du champ collectif des possibilités ;
- Mark comme action centrale commune ;
- Nous comme identité collective visible ;
- priorité authority-first ;
- Jour J attaché à Occurrence ;
- Live attaché à Jour J ;
- continuité de navigation ;
- séparation responsabilité / autorité ;
- états loading / empty / success / error ;
- divulgation minimale ;
- absence de duplication métier.

## Contextuel

- libellé et icône de la porte métier ;
- vocabulaire interne du monde opérationnel ;
- poids des relations ;
- types de faits dominants ;
- actions de création ;
- densité ;
- sections visibles ;
- contenu de Découvrir ;
- dimensions de Pilotage ;
- profondeurs accessibles depuis Nous ;
- profondeur Jour J ;
- surface Live.


# 37. Résumé par archétype

| Archétype | Porte métier visible | Relations dominantes | Découvrir met l’accent sur | Pilotage dominant |
|---|---|---|---|---|
| generic | Activités | personnes, groupes, contacts | opportunités multidomaines | activité, demandes, blocages |
| creative | Créations | publics, partenaires | lieux, collaborations, événements | activités, prestations, offres |
| media | Productions | publics, audiences, partenaires | collaborations, événements, contexte éditorial | productions, audiences utiles, partenaires |
| education | Programmes | groupes, personnes, partenaires | ressources, programmes, lieux, partenaires | inscriptions, progression, Requirements, Capacity |
| commerce | Commerce | clients, partenaires | publics, canaux, lieux, partenaires | commandes, délivrance, Capacity, Payments |
| service_provider | Prestations | clients, partenaires | zones, clients/contextes, partenaires | charge, délais, blocages, résultats |
| transport_operator | Transport | équipe, partenaires, CRM réel | dessertes, lieux, réseau, besoins | départs, Capacity, incidents, Access, finance |
| community | Initiatives | communauté, publics, partenaires | Funding, appels, partenaires, mobilisation | initiatives, participation, Funding, mission |


# 38. Critères de sortie UX Space conceptuelle

Avant rapprochement runtime, la spécification est considérée suffisamment fermée si :

1. la personne reste visiblement dans Makolo lorsqu’elle entre dans un Space ;
2. l’Avatar reste la personne authentifiée et ne devient jamais l’identité du Space ;
3. la personne sait toujours dans quel Space elle agit ;
4. le filtre de responsabilité n’expose que ce qu’elle porte dans ce Space ;
5. une personne multi-rôle peut travailler en vue combinée sans concaténation de dashboards ;
6. la navigation primaire visible est compréhensible sans connaissance de l’architecture interne ;
7. Maintenant peut représenter les situations sans connaître l’algorithme final de ranking ;
8. Découvrir peut représenter les possibilités collectives sans devenir un feed ;
9. le Mark conserve la même identité et ne contourne jamais l’autorité ;
10. la porte métier parle le vocabulaire naturel de l’archétype ;
11. Nous donne accès à l’identité collective sans devenir un écran Paramètres ;
12. Personnes & relations restent composées sans fusionner leurs vérités ;
13. Piloter peut conclure données insuffisantes plutôt que fabriquer une métrique ;
14. une action réelle peut ouvrir sa profondeur canonique sans perdre le contexte ;
15. plusieurs Jour J peuvent coexister dans un Space ;
16. Live reste attaché à un Jour J déterminé ;
17. les huit archétypes partagent la même architecture cognitive sans devenir huit applications indépendantes ;
18. les états loading, empty, success et error ont un sens clair ;
19. le retour arrière conserve le contexte ;
20. responsabilité et autorité restent distinctes ;
21. aucune projection ne transfère des droits ou des données privées ;
22. l’état final peut être calme.


# 39. Étape suivante

La spécification conceptuelle et le shell visible sont désormais suffisamment stabilisés pour passer au design des écrans.

La séquence UX suivante est :

1. shell Space mobile ;
2. racine Maintenant ;
3. racine Découvrir ;
4. racines métier par archétype ;
5. racine Nous ;
6. Personnes & relations ;
7. Piloter ;
8. Jour J opérateur ;
9. Makolo Live opérateur ;
10. profondeurs et transitions.

Le design d’écran reste distinct du rapprochement runtime.

Après fermeture de ces contrats visuels et interactionnels vient le rapprochement avec :

- runtime actuel ;
- selectors / read models ;
- routes et surfaces existantes ;
- gaps de projection ;
- contrats API réellement nécessaires ;
- implémentation Web et Mobile.


# 40. Règle finale

Toute décision UX Space doit pouvoir répondre :

> **Est-ce que Makolo aide cette personne à faire avancer le Space dans le monde réel, ou lui demande-t-il de travailler pour comprendre Makolo ?**

Si la personne doit penser en termes de modules internes avant de pouvoir agir, l’expérience n’est pas encore Mature.

Si Makolo comprend suffisamment le contexte pour présenter le bon travail, la bonne relation, la bonne possibilité ou le bon Jour J au moment utile, alors :

> **Makolo marche pour vous.**
