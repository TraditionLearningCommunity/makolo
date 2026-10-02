# Makolo — Space Architecture d’expérience mobile consolidée

**Nature :** contrat UX mobile consolidé pour le contexte Space  
**Portée :** expérience d’un Profile agissant explicitement au nom d’un Space, shell mobile, navigation primaire, responsabilités, archétypes, surfaces principales, surfaces secondaires, Jour J opérateur, Makolo Live et règles transversales.  
**Base vérifiée avant création :** main@3b348dfa3a881a1f9d1e929e1e81c5a39983ffb1  
**Document sémantique associé :** space-ux-experience-specification.md  
**Principe de lecture :** le code, les migrations, les tests et les contrats d’autorité du main courant restent la vérité runtime. Le présent document fixe l’expérience cible ; il ne crée ni Permission, ni Mandate, ni bounded context, ni algorithme de ranking.

---

# 1. Promesse et doctrine générale

La promesse reste :

> **Makolo marche pour vous.**

Dans un Space, Makolo doit aider une personne à faire avancer une réalité collective sans lui demander de comprendre l’architecture interne du produit.

Le principe d’expérience reste :

> **Pas le plaisir de rester. Le plaisir d’avancer.**

Et lorsque rien ne demande d’intervention :

> **Tout est en ordre. ✓**

L’expérience Space conserve aussi le principe :

> **Makolo doit être immense à l’intérieur et petit à l’extérieur.**

Le backend peut exposer Activity, Occurrence, Journey, Requirement, Access, Capacity, Commerce, Payment, CRM, Groups, Partners, Funding, Operations, Analytics, Automation, Trust et de nombreux autres domaines.

L’interface ne doit pas transformer cette richesse en un menu de modules.

La règle reste :

> **Backend générique, métier contextuel.**

## 1.1. Un Space n’est pas un autre compte utilisateur

Le Profile est la personne authentifiée.

Le Space est une identité collective durable au nom de laquelle une personne peut agir seulement lorsque l’autorité canonique le permet.

~~~text
Profile = personne globale

Space = acteur collectif durable

Assignment = responsabilité

Mandate / Permission = autorité
~~~

Un Space ne possède pas sa propre session humaine.

Il ne remplace pas le Profile.

Il ne devient jamais un second Avatar.

## 1.2. Changer d’acteur ne change pas d’application

Passer de Moi à Mulykap ne signifie pas ouvrir une autre application.

La bonne représentation est :

~~~text
MAKOLO
  ├── contexte personnel
  └── contexte Space
~~~

et non :

~~~text
Makolo
  → console professionnelle séparée
~~~

La marque, le Makolo Mark, l’Avatar humain, les principes d’interaction et les fondations visuelles restent Makolo.

## 1.3. La situation humaine précède l’objet métier

La personne doit pouvoir comprendre :

- qu’est-ce qui mérite notre attention ;
- qu’est-ce qui pourrait nous aider à avancer ;
- qu’est-ce que nous faisons réellement ;
- qui sommes-nous ;
- qui fait quoi ;
- qui peut agir ;
- ce qui est prêt ;
- ce qui bloque ;
- ce qui se déroule maintenant.

Elle ne doit pas devoir choisir d’abord entre CRM, Analytics, Payments, Capacity, Journey, Access ou Automation pour comprendre la situation.

---

# 2. Architecture principale du shell mobile Space

## 2.1. Le shell global reste Makolo

Le Header global conserve deux repères stables :

~~~text
Makolo                                      Avatar
~~~

Le logo / wordmark / Mark de marque est à gauche.

L’Avatar humain est à droite.

Le Space courant ne remplace aucun de ces deux repères.

Une identité visuelle propre au Space peut apparaître dans son contexte et dans Nous, mais elle ne remplace jamais la marque Makolo dans le shell global.

## 2.2. Le logo Makolo respecte l’acteur courant

Lorsque la personne agit pour un Space, toucher le logo Makolo revient normalement au Maintenant de ce Space.

Exemple :

~~~text
Mulykap
→ Transport
→ Départ
→ toucher Makolo
→ Maintenant de Mulykap
~~~

Pour revenir à son contexte personnel, la personne choisit explicitement :

> **Agir comme → Moi**

Le logo ne change pas implicitement d’acteur.

## 2.3. L’Avatar reste la personne

Même lorsque Jean agit pour Mulykap :

~~~text
Avatar = Jean
acteur courant = Mulykap
~~~

Le menu Avatar peut rappeler :

> **Agit actuellement pour Mulykap**

mais l’Avatar ne devient jamais le logo ou l’identité du Space.

## 2.4. Agir comme

Le menu global d’acteur peut présenter :

~~~text
Agir comme

Moi
Mulykap
Fondation Upendo
Studio K
...
~~~

La liste ne contient que des contextes auxquels la personne possède réellement un accès ou une autorité légitime selon les contrats serveur.

Sélectionner un Space n’accorde aucune Permission.

## 2.5. Contexte Space persistant

Une fois le Space choisi, le shell présente de manière compacte :

~~~text
Mulykap ▾
Toutes mes responsabilités ▾
~~~

Le premier contrôle change de Space.

Le second réduit la lecture aux responsabilités de la personne dans ce Space.

Exemples :

~~~text
Toutes mes responsabilités
Exploitation
Finance
Administration
Contrôle · Départ 14 h
Scanner · Départ Lubumbashi → Kolwezi
~~~

Le vocabulaire technique Scope n’est pas nécessairement affiché.

## 2.6. Navigation basse

La navigation primaire mobile Space est :

> **Maintenant | Découvrir | [Makolo Mark] | Métier | Nous**

Elle contient quatre destinations et une action centrale.

| Élément | Question humaine | Rôle |
|---|---|---|
| Maintenant | Qu’est-ce qui mérite notre attention maintenant ? | Attention et intervention actuelle |
| Découvrir | Qu’est-ce qui pourrait nous aider à avancer ? | Exploration collective |
| Makolo Mark | J’ai quelque chose à donner à Makolo. | Intake et orchestration dans le contexte du Space |
| Métier | Qu’est-ce que nous opérons réellement ? | Travail durable et continuité opérationnelle |
| Nous | Qui sommes-nous et comment fonctionnons-nous ensemble ? | Identité collective, organisation et profondeurs institutionnelles |

## 2.7. Continuité avec le Profil

La grammaire personnelle est :

~~~text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
~~~

La grammaire Space devient :

~~~text
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
~~~

La personne reste dans la même application.

Elle retrouve :

- Maintenant au même endroit ;
- Découvrir au même endroit ;
- le même Makolo Mark ;
- une porte de continuité / travail à la quatrième position ;
- Moi devenu Nous lorsque l’acteur est collectif.

## 2.8. Icônes sémantiques

Les icônes dont le sens reste stable doivent rester stables entre Profil et Space.

- **Maintenant** : clock-3 ou équivalent d’instant, pas calendrier.
- **Découvrir** : compass ou équivalent d’exploration.
- **Makolo Mark** : véritable Makolo Mark officiel, jamais un plus générique.
- **Nous** : users-round ou représentation collective simple.
- **Métier** : icône contextualisée par archétype.

L’Avatar supérieur reste distinct de Nous.

## 2.9. Icône et libellé Métier par archétype

| Archétype | Libellé primaire | Icône sémantique candidate |
|---|---|---|
| generic | Activités | calendar-range |
| creative | Créations | palette |
| media | Productions | newspaper |
| education | Programmes | graduation-cap |
| commerce | Commerce | shopping-bag |
| service_provider | Prestations | handshake |
| transport_operator | Transport | bus-front |
| community | Initiatives | heart-handshake |

Ces icônes sont des intentions sémantiques. Le design final peut ajuster le glyph si la charte mobile impose un meilleur symbole.

## 2.10. Ce qui ne devient pas un onglet primaire

Il n’existe pas d’onglet principal permanent obligatoire pour :

- CRM ;
- Contacts ;
- Groupes ;
- Audiences ;
- Partners ;
- Payments ;
- Funding ;
- Promotions ;
- Loyalty ;
- Recognition ;
- Trust ;
- Capacity ;
- Access ;
- Scanner ;
- Operations ;
- Analytics ;
- Growth ;
- Automation ;
- Team ;
- Responsibilities ;
- Subscription ;
- Settings ;
- Historique ;
- Piloter ;
- Personnes & relations ;
- Jour J ;
- Live ;
- Plus.

Ces capacités restent majeures lorsqu’un contexte humain les appelle.

## 2.11. Headers principaux

Le Header reste Makolo mais adapte ses actions au mode mental.

### Maintenant

Repères :

> **Makolo | contexte Space | actions d’attention réellement utiles | Avatar**

Les Notifications et Conversations peuvent rester accessibles, mais une conséquence réellement importante doit pouvoir remonter dans Maintenant sans obliger l’utilisateur à ouvrir une cloche.

### Découvrir

Repères :

> **Makolo | contexte Space | Recherche / filtres pertinents | Avatar**

Découvrir doit rester exploratoire et ne pas être pollué par des badges opérationnels anxiogènes.

### Makolo Mark

Repères :

> **Makolo | contexte Space | Avatar**

Le Mark peut réduire encore le chrome lorsqu’une interaction focalisée le justifie.

### Métier

Repères :

> **Makolo | Space / contexte métier | recherche ou filtres métier utiles | Avatar**

Le Header parle le métier : Transport, Programmes, Prestations, Commerce, etc.

### Nous

Repères :

> **Makolo | Nous | Avatar**

Nous n’est pas un écran Paramètres. Le Header reste humain et léger.

## 2.12. Headers secondaires

Une profondeur utilise :

> **← | titre humain ou contexte naturel | actions contextuelles uniquement**

Exemples :

- Départ Lubumbashi → Kolwezi ;
- Programme Comptabilité ;
- Commande 493 ;
- Prestation Visa ;
- Partenaire X ;
- Équipe Exploitation.

Éviter les noms de modèles backend comme titre principal.

## 2.13. Surfaces immersives

Jour J, Scanner, contrôle d’accès, QR, carte opérationnelle et Live peuvent réduire temporairement le Header ou masquer la navigation basse.

Cette immersion ne crée pas une nouvelle application.

Le contexte doit rester récupérable :

~~~text
Makolo
+ Space
+ réalité courante
~~~

---

# 3. Doctrine de composition

## 3.1. Une vérité canonique, plusieurs projections

Une même réalité peut apparaître dans plusieurs surfaces parce que la question humaine change.

Exemple Payment :

- Maintenant : un paiement échoué demande une intervention ;
- Commerce : le paiement bloque une commande ;
- Piloter : les flux financiers sont analysés.

Il s’agit du même Payment canonique.

## 3.2. Presentation représente, ne possède pas

Aucune surface UX ne devient propriétaire d’une réalité parce qu’elle permet d’y entrer.

- Maintenant ne possède pas les situations ;
- Découvrir ne possède pas toutes les Opportunities ;
- Nous ne possède pas Team, CRM, Partner ou Mandate ;
- Piloter ne possède pas Analytics, Payments ou Capacity ;
- Jour J ne possède pas Occurrence ;
- Live ne possède pas Operations.

## 3.3. Archétype et Operational Footprint

~~~text
ARCHETYPE
= centre de gravité durable

OPERATIONAL FOOTPRINT
= domaines réellement utilisés
~~~

L’archétype change la manière de présenter.

Il ne crée aucune vérité.

Un Space commerce peut utiliser Service, Transport, Event et Funding sans changer automatiquement d’archétype.

## 3.4. Responsabilité et autorité

~~~text
Assignment = responsabilité
Mandate / Permission = autorité
~~~

La responsabilité peut influencer la lecture.

Elle ne suffit jamais à autoriser une action.

## 3.5. Divulgation minimale

Le fait qu’une personne agisse pour un Space ne lui donne pas automatiquement accès à toutes les données du Space.

Les projections doivent être limitées par l’autorité et le scope réels.

---

# 4. Maintenant — contrat Space

## 4.1. Question centrale

> **Qu’est-ce qui mérite notre attention maintenant ?**

Maintenant est la racine normale après entrée dans un Space.

Ce n’est pas :

- un dashboard ;
- un inbox ;
- un feed ;
- une liste de notifications ;
- une liste de toutes les opérations ;
- une page de KPI ;
- une todo list générique.

## 4.2. Familles de situations

Maintenant peut représenter :

### Décider

Une décision réelle attend.

### Faire avancer

Quelqu’un attend quelque chose du Space.

### Préparer

Une réalité importante approche et n’est pas suffisamment prête.

### Jour J

Une Occurrence pertinente est actuelle ou entre dans sa fenêtre opérationnelle.

### Débloquer

Une condition empêche la progression.

### Réagir

Une déviation ou un incident demande une intervention.

### Surveiller

Une contrainte approche d’un état significatif.

### Passer le relais

Une responsabilité doit changer de main.

### Saisir une possibilité

Une possibilité devient réellement pertinente maintenant.

### Ajuster

Les faits indiquent qu’une décision de pilotage mérite attention.

### Accompli

Une réalisation importante peut être confirmée brièvement.

## 4.3. Chaque entrée doit être explicable

Une situation doit répondre autant que possible à :

~~~text
Quoi ?
Pourquoi maintenant ?
Quelle conséquence ?
Que puis-je faire ?
Dans quel contexte ?
~~~

Exemple :

> **Départ Lubumbashi → Kolwezi · 14 h**  
> Aucun véhicule n’est affecté.  
> Départ dans 35 minutes.  
> **Préparer**

Pas :

> vehicle_assignment = null

## 4.4. Priorité

L’UX ne calcule pas elle-même le ranking final.

Le contrat conceptuel reste :

~~~text
autorité
→ situation
→ conséquence
→ temps
→ responsabilité
→ archétype
→ operational footprint
→ continuité
~~~

Des moteurs futurs, notamment issus de l’Univers Molongo, pourront améliorer la sélection et l’ordre.

Le résultat présenté doit rester explicable humainement.

## 4.5. Plusieurs Jour J simultanés

Un Space peut opérer plusieurs Occurrences simultanément.

Exemple :

~~~text
5 départs actifs
2 demandent votre attention
~~~

Maintenant ne transforme pas le Space entier en Live.

La personne choisit le Jour J auquel elle prête attention.

## 4.6. Vue combinée et filtre de responsabilité

En :

> **Toutes mes responsabilités**

Maintenant fusionne les situations admissibles.

Il ne concatène pas des dashboards de rôle.

En :

> **Finance**

il réduit le champ aux situations pertinentes pour cette responsabilité, sans augmenter l’autorité.

## 4.7. État calme

Lorsque rien ne mérite d’intervention :

> **Tout est en ordre. ✓**

Makolo ne remplit pas l’écran avec des statistiques ou suggestions artificielles.

---

# 5. Découvrir — contrat collectif

## 5.1. Question centrale

> **Qu’est-ce qui pourrait nous aider à avancer ?**

Découvrir est le langage visible du territoire conceptuel des possibilités.

Il ne s’agit pas simplement de croissance commerciale.

## 5.2. Différence avec Découvrir personnel

Découvrir personnel demande :

> Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?

Découvrir Space demande :

> Qu’est-ce qui pourrait permettre à notre organisation d’avancer ?

Le même verbe conserve une grammaire Makolo stable.

Le contexte d’acteur modifie la pertinence.

## 5.3. Sources possibles

Selon les domaines réels, Découvrir peut représenter :

- Opportunity ;
- Funding ;
- partenaires potentiels ;
- Activities ;
- lieux ;
- ressources ;
- publics ;
- collaborations ;
- dessertes ;
- besoins ;
- programmes ;
- autres réalités canoniques utiles.

## 5.4. Une possibilité doit avoir un sens

Une proposition devrait permettre de comprendre :

~~~text
Qu’est-ce que c’est ?
Pourquoi cela peut nous concerner ?
Qu’est-ce que cela pourrait permettre ?
Quelle réalité ou source la soutient ?
Que pouvons-nous faire ensuite ?
~~~

## 5.5. Le contexte collectif

La pertinence peut utiliser lorsque légitime :

- archétype ;
- Operational Footprint ;
- SpaceOpenTo ou faits équivalents réellement établis ;
- géographie ;
- Activities ;
- Partners ;
- publics ;
- besoins ;
- contexte actuel.

L’archétype ne suffit jamais à conclure qu’une possibilité convient.

## 5.6. Recherche, filtres et carte

Search réduit le même champ de possibilités.

Exemples :

- partenaire logistique à Lubumbashi ;
- financement pour ce programme ;
- lieu pour notre événement ;
- nouvelle desserte pertinente ;
- possibilité de prestation ;
- ressource pour cette initiative.

Les filtres ne doivent pas exposer la taxonomie backend.

La carte apparaît lorsque la géographie aide réellement à choisir.

## 5.7. No Orphan Content / Media

Découvrir peut utiliser image, vidéo, carte, document ou audio lorsque cela aide à comprendre une possibilité.

Il ne devient jamais un feed média générique.

## 5.8. Exploration bornée

Découvrir peut être riche et scrollable.

Il ne doit pas être infini par principe.

Makolo peut conclure :

> **Aucune possibilité suffisamment pertinente pour le moment.**

Option possible :

> Explorer plus largement.

## 5.9. Passage à l’action

Une possibilité peut conduire vers :

- un domaine propriétaire ;
- une relation Partner ;
- une Activity ;
- Funding ;
- un contexte géographique ;
- une réponse ou candidature ;
- une autre action légitime.

Découvrir ne devient jamais propriétaire du résultat.

---

# 6. Makolo Mark dans un Space

## 6.1. Même Mark

Il n’existe pas de Space Mark, Business Mark ou Admin Mark.

Il existe un seul :

> **Makolo Mark**

Le contexte courant lui donne son sens.

## 6.2. Question

> **J’ai quelque chose à donner à Makolo.**

Dans un Space, cela peut être :

- une intention ;
- une information ;
- une photo ;
- un document ;
- un lien ;
- une situation ;
- une demande de création ;
- une demande de préparation ;
- une demande de retrouver ;
- une demande de continuer.

## 6.3. Le contexte est connu

Si la personne agit pour Mulykap, le Mark peut comprendre une phrase telle que :

> Ajoute un départ demain à 8 h.

comme une intention dans ce Space.

Mais il doit encore vérifier :

- cible suffisamment déterminée ;
- capacité métier réelle ;
- autorité ;
- données nécessaires ;
- action owner correcte.

## 6.4. Le Mark ne contourne jamais l’autorité

Une personne sans Permission de créer un Departure ne l’obtient pas parce qu’elle a utilisé le Mark.

Le Mark peut expliquer la limite ou orienter vers la voie légitime.

## 6.5. Handoff

Le Mark peut transmettre vers :

- Maintenant ;
- Découvrir ;
- Métier ;
- Nous ;
- Personnes & relations ;
- Piloter ;
- une profondeur canonique ;
- Jour J ;
- un domaine propriétaire.

Il ne devient propriétaire d’aucune de ces capacités.

---

# 7. Métier — contrat opérationnel

## 7.1. Question générale

> **Qu’est-ce que nous faisons réellement exister, préparer, exécuter et délivrer ?**

Cette porte est la principale surface durable de travail.

## 7.2. En cours n’est pas un onglet Space

Contrairement au contexte personnel, le Space ne possède pas nécessairement un onglet En cours autonome.

La continuité est déjà naturellement portée par son monde métier.

Une racine métier peut composer :

~~~text
À préparer
À venir
En cours
Bloqués
Terminés
~~~

selon le métier.

## 7.3. Le libellé parle le métier

Le mot Opérer est un terme d’architecture.

L’utilisateur voit :

- Activités ;
- Créations ;
- Productions ;
- Programmes ;
- Commerce ;
- Prestations ;
- Transport ;
- Initiatives.

## 7.4. Création contextuelle

Pas de méga-bouton + Créer ouvrant toute la taxonomie Makolo.

Exemples :

~~~text
Transport
→ Nouveau départ
→ Nouvelle route
→ Nouveau véhicule
~~~

~~~text
Programmes
→ Nouveau programme
→ Nouvelle session
~~~

~~~text
Prestations
→ Nouvelle prestation
~~~

Les actions proposées restent Permission-gated.

---

# 8. Racines métier par archétype

## 8.1. generic — Activités

La racine peut composer :

- Activities ;
- à préparer ;
- à venir ;
- en cours ;
- demandes associées ;
- lieux ;
- terminées.

Les verticales utilisées apparaissent seulement lorsqu’elles existent réellement.

L’état vide ne doit pas créer une Activity fictive.

## 8.2. creative — Créations

La racine peut composer :

- créations / Activities ;
- événements ;
- prestations ;
- Occurrences ;
- offres réellement opérées.

La création artistique reste première lorsque le Space n’est pas principalement commercial.

Interdits :

- feed ;
- Story ;
- portfolio parallèle générique ;
- média orphelin ;
- faux publics ;
- fausses offres.

## 8.3. media — Productions

La racine peut composer :

- productions / Activities ;
- événements ;
- prestations éventuelles ;
- Occurrences.

Audiences, publics et partenaires restent surtout des relations ou des possibilités.

Makolo ne transforme pas un média en réseau social générique.

## 8.4. education — Programmes

La composition naturelle est :

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
- admissions ou demandes ;
- conditions manquantes ;
- ressources nécessaires ;
- Capacity ;
- personnes concernées selon autorité.

Elle ne doit pas exposer ces réalités comme sept modules indépendants.

## 8.5. commerce — Commerce

La chaîne humaine est :

~~~text
ce que nous rendons disponible
→ offre
→ commande / demande
→ préparation / disponibilité
→ remise / réalisation
→ obtention accomplie
~~~

La racine peut composer :

- offres ;
- commandes à traiter ;
- à préparer ;
- à remettre ;
- disponibilité ;
- Capacity ;
- Payments lorsqu’ils comptent ;
- terminées.

Invariant :

> commande ou paiement ne signifie pas automatiquement obtention accomplie.

## 8.6. service_provider — Prestations

La racine peut composer :

- prestations proposées ;
- demandes ;
- à préparer ;
- en traitement ;
- bloquées ;
- à délivrer ;
- terminées.

Une profondeur Dossier peut composer :

- personne concernée ;
- Requirements ;
- étapes utiles ;
- responsable ;
- pièces / ressources ;
- Payment ;
- résultat.

L’UX doit donner l’impression de traiter un service, pas de naviguer dans Journey.

## 8.7. transport_operator — Transport

La racine peut composer :

- aujourd’hui ;
- prochains départs ;
- départs actifs ;
- routes ;
- services ;
- véhicules ;
- lieux.

Un départ peut ouvrir :

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

Le terme Exploitation peut être utilisé à l’intérieur lorsque le contexte professionnel le justifie.

La navigation primaire préfère Transport, plus immédiatement compréhensible.

## 8.8. community — Initiatives

La racine peut composer :

- initiatives ;
- Activities ;
- événements ;
- actions terrain ;
- programmes réels.

Groups, Publics et Partners restent surtout relationnels.

Funding peut être une possibilité, une activité ou un signal de Pilotage selon son contexte réel.

---

# 9. Nous — contrat d’expérience

## 9.1. Question centrale

> **Qui sommes-nous, avec qui fonctionnons-nous et comment sommes-nous organisés ?**

Nous est le miroir collectif de Moi.

~~~text
Moi = identité / capital personnel
Nous = identité / organisation collective
~~~

## 9.2. Nous n’est pas Settings

La première vue ne doit pas être une page administrative.

Elle doit donner une lecture humaine du collectif.

Exemple conceptuel :

~~~text
Nous

Mulykap
Transport de voyageurs

Équipe
12 personnes

Responsabilités
4 domaines actifs

Relations
partenaires, groupes et contacts pertinents

Confiance
identité vérifiée
~~~

La mise en page finale reste à concevoir.

## 9.3. Identité collective

Nous peut rendre compréhensible :

- nom ;
- description ;
- présentation publique ;
- contacts généraux ;
- localisation générale ;
- archétype ;
- lifecycle ;
- mission lorsqu’elle est pertinente.

## 9.4. Équipe

Nous peut donner accès à Team et aux collaborateurs.

Mais :

> TeamMembership n’accorde jamais automatiquement d’autorité.

La vue humaine peut dire :

> Marie travaille avec nous.

La profondeur gouvernance peut expliquer séparément :

> Marie peut agir dans tels scopes.

## 9.5. Responsabilités et autorité

Nous peut permettre de comprendre :

- qui porte quoi ;
- qui peut agir ;
- ownership ;
- Mandates ;
- responsabilités administratives.

Le vocabulaire visible doit rester humain.

Les détails Permission / Mandate peuvent rester dans des profondeurs appropriées.

## 9.6. Relations

Nous peut offrir une entrée vers Personnes & relations.

Cela ne signifie pas que Nous devient propriétaire de CRM, Groups, Audiences ou Partners.

## 9.7. Piloter

Pour les responsabilités appropriées, Nous peut offrir une entrée vers Piloter.

Piloter reste une surface autonome de recul.

## 9.8. Trust et vérification

La confiance, la vérification et les faits Trust peuvent être présentés lorsqu’ils sont utiles.

Il ne faut pas fabriquer un score global de qualité du Space.

## 9.9. Paramètres institutionnels

Les profondeurs de Nous peuvent contenir selon autorité :

- présence publique ;
- archétype ;
- Team ;
- responsabilités ;
- ownership ;
- Trust ;
- Subscription ;
- Entitlements ;
- connexions ;
- archivage / restauration ;
- paramètres du Space.

Ces éléments ne doivent pas dominer la racine.

---

# 10. Avatar, acteur, compte et responsabilités

## 10.1. Avatar

> **L’Avatar contrôle l’identité humaine, le contexte d’acteur et le compte.**

Avatar ≠ Nous.

## 10.2. Contenu conceptuel

Le menu peut contenir :

1. identité authentifiée ;
2. rappel de l’acteur courant ;
3. Agir comme ;
4. Compte et paramètres ;
5. changer de compte ;
6. se déconnecter.

L’abonnement personnel reste distinct de l’abonnement / Entitlement du Space.

## 10.3. Agir comme Moi

Lorsqu’un Space est actif, le menu propose une voie évidente :

> **Agir comme moi**

Elle revient au contexte personnel sans changer de compte authentifié.

## 10.4. Changer de compte

Changer de compte change l’identité authentifiée.

Ce n’est pas la même chose que changer d’acteur.

## 10.5. Toutes mes responsabilités

Le sélecteur de responsabilité ne liste que le Space courant.

Il peut être absent ou simplifié lorsqu’une seule perspective est pertinente.

Il ne doit pas occuper visuellement l’écran plus que nécessaire.

---

# 11. Personnes & relations — surface majeure secondaire

## 11.1. Question

> **Avec qui avançons-nous ?**

Cette surface compose les relations sans les fusionner.

## 11.2. Distinctions

~~~text
CRMContact
!= TeamMember
!= GroupMember
!= Partner
!= Mandate holder
!= follower
!= participant
~~~

La même personne peut apparaître dans plusieurs relations différentes.

## 11.3. Sections possibles

Selon le Space :

- équipe ;
- groupes ;
- clients / contacts ;
- publics ;
- audiences ;
- partenaires ;
- autres relations métier réelles.

Les sections absentes disparaissent.

## 11.4. Vocabulaire archétypal

- generic : Personnes & relations ;
- creative : Publics & partenaires ;
- media : Publics & partenaires ;
- education : Groupes, personnes & partenaires ;
- commerce : Clients & relations ;
- service_provider : Clients & partenaires ;
- transport_operator : Relations ;
- community : Communauté & partenaires.

Ces termes restent des libellés UX, pas de nouveaux modèles Profile.

## 11.5. Recherche

Une recherche peut réunir plusieurs sources tout en indiquant la relation réelle.

Exemple :

~~~text
Marie Kalala
Collaboratrice · Exploitation

Marie Kalala
Contact CRM · Client
~~~

---

# 12. Piloter — surface majeure secondaire

## 12.1. Question

> **Est-ce que cela fonctionne ? Qu’est-ce qui change ? Que devons-nous ajuster ?**

Piloter est une surface de recul.

Ce n’est pas un dashboard par défaut.

## 12.2. Commencer par le sens

Préférer :

> Les départs de 17 h approchent régulièrement de la capacité maximale.

à :

> Capacity KPI = 92 %.

Les chiffres et graphiques approfondissent ensuite.

## 12.3. Sections possibles

Selon autorité et Operational Footprint :

- fonctionnement ;
- flux ;
- Capacity ;
- délivrance ;
- finance ;
- acquisition ;
- relations ;
- incidents ;
- Automation ;
- tendances.

## 12.4. Zéro, inconnu et données insuffisantes

~~~text
0
!= inconnu
!= indisponible
!= données insuffisantes
~~~

Lorsque les données sont insuffisantes :

> **Pas encore assez d’activité pour dégager une tendance utile.**

## 12.5. Pas de score global

Makolo ne fabrique pas un score global du Space.

Il ne transforme pas popularité, likes ou watch time en objectifs de pilotage.

## 12.6. Responsabilités

Owner, Finance, exploitation, programme ou développement peuvent voir des lectures différentes.

Il s’agit d’une même surface adaptée, pas d’un dashboard par rôle.

---

# 13. Jour J opérateur et Makolo Live

## 13.1. Une Occurrence, un Jour J

Jour J appartient à une Occurrence devenue actuelle.

Il n’appartient pas au Space entier.

## 13.2. Plusieurs Jour J simultanés

Un transporteur peut avoir plusieurs bus en mouvement.

Une école peut avoir plusieurs sessions.

Un organisateur peut avoir plusieurs Occurrences.

Donc :

~~~text
Space
├── Jour J A
├── Jour J B
└── Jour J C
~~~

Le Space ne passe jamais globalement en Live.

## 13.3. Le choix de focalisation appartient à la personne

Maintenant peut signaler :

> 5 départs actifs, 2 demandent votre attention.

La personne choisit celui qu’elle ouvre.

Une fois ouvert, Jour J peut temporairement prendre le dessus.

## 13.4. Jour J opérateur vs Jour J participant

Même Occurrence, projections différentes.

### Participant

- où aller ;
- Access ;
- Placement ;
- Queue ;
- mouvement personnel ;
- expérience personnelle.

### Opérateur

- préparation ;
- Capacity ;
- personnes attendues dans la limite de l’autorité ;
- AccessUse ;
- contrôle ;
- incidents ;
- ressources ;
- état opérationnel.

Il n’existe pas deux Occurrences.

## 13.5. Makolo Live

Live appartient à Jour J.

Il représente ce qui est effectivement observé ou se déroule maintenant.

Il peut être :

- opérationnel ;
- temporel ;
- spatial ;
- médiatique seulement si une source réelle existe.

## 13.6. Vérité temps réel

Distinguer :

~~~text
planned
estimated
observed
live
unknown
unavailable
~~~

Une heure planifiée n’est pas un fait Live.

Une position non observée n’est pas inventée.

## 13.7. Scanner

Pour une personne dont la responsabilité est contrôle / scanner, le Jour J peut devenir presque toute l’expérience utile.

Makolo doit pouvoir réduire le reste du shell pour favoriser :

- identification du contexte ;
- scan ;
- résultat ;
- anomalie ;
- récupération ;
- passage suivant.

Le scanner ne doit pas traverser des menus Finance, Analytics ou Settings.

## 13.8. Fin naturelle

Lorsque l’Occurrence se termine, Jour J ne devient pas une archive infinie.

Les conséquences passent vers leurs propriétaires : Historique, Proof, AccessUse, Analytics, etc.

---

# 14. Recherche Space

## 14.1. Recherche globale au Space

La recherche n’est pas un onglet principal.

Question :

> **Rechercher dans cet Espace**

Elle est :

- limitée au Space ;
- permission-first ;
- éventuellement réduite par la responsabilité active.

## 14.2. Résultats humains

Préférer :

~~~text
Transport
Personnes
Commandes
Lieux
Programmes
~~~

à une simple liste de noms de modèles.

## 14.3. Recherche spécialisée

Les profondeurs peuvent avoir leurs recherches :

- rechercher un départ ;
- rechercher un dossier ;
- rechercher une commande ;
- rechercher une personne ;
- rechercher une Activity.

La recherche globale ne remplace pas les recherches métier.

---

# 15. Création et actions

## 15.1. Création contextuelle

La création appartient au contexte naturel.

Pas de méga-menu universel.

## 15.2. État vide

Un état vide peut être le meilleur endroit pour proposer la première action.

Exemple :

> Aucun programme pour le moment.  
> **Créer un programme**

uniquement si la personne est autorisée.

## 15.3. Responsabilité sélectionnée

Si la personne choisit Finance, le shell peut réduire les actions opérationnelles proposées.

Cela ne modifie pas l’autorité sous-jacente.

## 15.4. Feedback

Une action significative doit produire un retour perceptible.

Préférer :

> **Départ créé. Il reste à affecter un véhicule.**

à :

> Success.

---

# 16. Historique et temps

## 16.1. Historique n’est pas un onglet primaire

L’histoire reste transverse.

Exemples :

~~~text
Prestations
→ En cours / Terminées

Départs
→ À venir / Passés

Programmes
→ Actuels / Passés

Commandes
→ Actives / Terminées
~~~

## 16.2. Piloter et histoire

Piloter peut utiliser l’histoire pour identifier tendances et écarts.

Il ne devient pas propriétaire de l’historique.

## 16.3. Jour J après la fin

Après la fin, Jour J se ferme naturellement.

La réalité peut continuer à être inspectable dans le domaine propriétaire.

---

# 17. États loading, empty, success, error et offline

## 17.1. Loading

Le chargement doit confirmer le travail sans créer de flash inutile.

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

## 17.2. Empty

Distinguer :

- initialisation ;
- aucun résultat de filtre ;
- rien à faire ;
- capacité indisponible dans ce contexte.

Pour Maintenant :

> **Tout est en ordre. ✓**

Pour Découvrir :

> **Aucune possibilité suffisamment pertinente pour le moment.**

Pour Piloter :

> **Pas encore assez d’activité pour dégager une tendance utile.**

## 17.3. Success

Confirmer uniquement le niveau réellement atteint.

Ne pas annoncer envoyé si l’action est seulement en attente locale.

## 17.4. Error

Une erreur importante répond :

1. qu’est-ce qui n’a pas fonctionné ?
2. qu’est-ce qui a été conservé ?
3. que puis-je faire maintenant ?

Une erreur bloquante reste visible.

## 17.5. Offline

Une perte réseau ne doit pas transformer automatiquement tout le Space en panne si des données locales sûres restent disponibles.

Mais une donnée locale ancienne ne doit jamais être présentée comme Live ou sûre lorsqu’une actualité serveur est nécessaire.

Les actions sensibles restent soumises aux contrats local-first, idempotence, autorité et synchronisation réellement supportés.

---

# 18. Notifications, Conversations et attention

## 18.1. Notification ≠ situation

Une Notification est un canal.

Maintenant est une projection de conséquence actuelle.

Direction correcte :

~~~text
fait métier
→ conséquence
→ éventuellement Maintenant
→ éventuellement Notification
~~~

## 18.2. Conversations

Une conversation peut devenir pertinente lorsqu’elle porte :

- une décision attendue ;
- une information qui change l’action ;
- un passage de relais ;
- une intervention dont la personne est le prochain acteur.

Une conversation non lue n’est pas automatiquement une urgence.

## 18.3. Silence

Le silence est une fonctionnalité.

Rien à faire ne doit pas générer de stimulation artificielle.

---

# 19. Langage et convivialité

## 19.1. Le langage visible est humain

Le design ne doit pas exposer comme navigation primaire :

- Operational Footprint ;
- Mandate ;
- Permission ;
- Journey ;
- Requirement ;
- AccessCredential ;
- CRM ;
- Analytics.

Ces termes restent légitimes dans l’architecture et certaines profondeurs professionnelles, mais pas comme prérequis de compréhension.

## 19.2. Moi ↔ Nous

Le couple :

~~~text
Moi ↔ Nous
~~~

doit être privilégié parce qu’il se comprend sans documentation.

Nous est plus humain que L’Espace comme repère primaire.

## 19.3. Possibilités ↔ Découvrir

Possibilités reste un concept de conception.

Découvrir est le mot visible parce qu’il est immédiatement actionnable et déjà appris dans le contexte personnel.

## 19.4. Exploitation ↔ Transport

Exploitation peut être un vocabulaire métier interne à la porte Transport.

Transport est préférable comme libellé primaire lorsqu’il est plus immédiatement compréhensible.

## 19.5. Pas de jargon pour démontrer la sophistication

Makolo peut être techniquement profond et visiblement simple.

Le langage de l’interface n’a pas à exposer la complexité interne pour paraître professionnel.

---

# 20. Densité et hiérarchie

## 20.1. Densité indicative

| Surface | Densité |
|---|---|
| Maintenant | faible |
| Découvrir | moyenne / exploratoire |
| Métier | moyenne à élevée |
| Nous | moyenne |
| Personnes & relations | moyenne |
| Piloter | élevée mais structurée |
| Jour J | moyenne / focalisée |
| Live | élevée mais strictement pertinente |

## 20.2. Professionnel ne signifie pas dense partout

Les logiciels professionnels échouent souvent en montrant trop d’informations en permanence.

Makolo doit utiliser la densité seulement lorsque l’action l’exige.

## 20.3. Progressive disclosure

Une racine explique l’essentiel.

Les détails, statistiques, règles, IDs, historiques techniques et paramètres sont accessibles en profondeur lorsqu’ils deviennent utiles.

---

# 21. Invariants métier à préserver

Ces distinctions ne doivent jamais être effacées par le design :

- Profile = personne globale ;
- Space = acteur collectif durable ;
- Assignment = responsabilité ;
- Mandate / Permission = autorité ;
- TeamMembership ≠ Mandate ;
- GroupMembership ≠ Mandate ;
- Readiness = projection dérivée ;
- Requirement ≠ Form ≠ Resource ≠ JourneyArtifact ≠ Proof ≠ Credential Trust ≠ AccessCredential ;
- Access = droit ;
- AccessCredential = représentation / secret ;
- AccessUse = observation de l’usage ;
- Capacity = combien ;
- Placement = où ;
- Waitlist ≠ Live Queue ;
- JourneyStep ≠ Checkpoint ;
- Dossier ≠ task manager ;
- Project ≠ task manager ;
- posséder un document ≠ le retrouver ≠ satisfaire un Requirement ;
- composition ≠ transfert de Permission, Mandate, Access, Payment ou visibilité privée.

---

# 22. Anti-features mobile Space

L’expérience ne doit pas devenir :

- une application professionnelle séparée de Makolo ;
- une console d’administration ;
- un ERP générique ;
- une navigation par modèles backend ;
- un task manager ;
- un dashboard KPI permanent ;
- un feed ;
- un réseau social de Spaces ;
- un système de popularité ;
- un portail CRM universel ;
- un portefeuille universel ;
- un second moteur Live ;
- un second système de Permissions ;
- un système où l’archétype invente des données ;
- huit applications complètement différentes selon l’archétype ;
- un écran Nous réduit à Paramètres ;
- un Mark qui contourne l’autorité ;
- une bottom navigation avec un onglet Plus servant de débarras.

---

# 23. État de gel et éléments volontairement non figés

Le présent contrat fixe :

- un seul shell Makolo ;
- Avatar humain stable ;
- changement d’acteur ;
- contexte Space ;
- responsabilité Space-scoped ;
- navigation primaire ;
- langage visible ;
- archétypes ;
- Maintenant ;
- Découvrir collectif ;
- Mark contextualisé ;
- métier ;
- Nous ;
- Personnes & relations ;
- Piloter ;
- Jour J ;
- Live ;
- recherche ;
- création ;
- états comportementaux ;
- frontières d’autorité.

Il ne fixe pas encore :

- pixel design final ;
- dimensions exactes des bars ;
- taille exacte des icônes ;
- composants Flutter définitifs ;
- animations finales ;
- transitions exactes ;
- choix définitif de chaque glyph métier ;
- responsive tablette final ;
- arrangement exact de chaque carte ;
- algorithmes Molongo ;
- contrats API non démontrés ;
- nouvelles capacités runtime.

Le design final doit suivre la nature de l’action et de l’information, pas imposer un même composant à toutes les surfaces.

---

# 24. Formules canoniques finales

## Shell

> **Un seul Makolo ; plusieurs contextes d’acteur.**

## Acteur

> **L’Avatar reste la personne. Le Space est le contexte collectif au nom duquel elle agit.**

## Navigation

> **Maintenant = attention.**  
> **Découvrir = possibilités collectives.**  
> **Makolo Mark = intention, apport et orchestration.**  
> **Métier = ce que nous faisons réellement.**  
> **Nous = identité et fonctionnement collectif.**

## Navigation personnelle et Space

~~~text
Profil
Maintenant | Découvrir | [Mark] | En cours | Moi

Space
Maintenant | Découvrir | [Mark] | Métier | Nous
~~~

## Maintenant

> **Maintenant sélectionne ce qui mérite l’attention ; il ne liste pas tout ce qui existe.**

## Découvrir

> **Découvrir ouvre ce qui pourrait nous aider à avancer ; il ne devient pas un feed.**

## Métier

> **Le backend reste générique ; la porte parle le langage naturel du Space.**

## Nous

> **Nous présente le collectif ; il ne réduit pas le Space à ses paramètres.**

## Jour J

> **Une Occurrence actuelle peut devenir un Jour J ; un Space peut en avoir plusieurs simultanément.**

## Live

> **Live appartient à un Jour J et représente seulement ce qui est réellement observé ou en train de se produire.**

## Autorité

> **Choisir un Space ou une responsabilité ne crée jamais de Permission.**

## Principe final

> **Makolo marche pour vous.**

> **Pas le plaisir de rester. Le plaisir d’avancer.**

> **Tout est en ordre. ✓**
