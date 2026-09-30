# MAYELE KNOWLEDGE RESEARCH
## Cadre conceptuel consolidé de la recherche et de la construction de connaissance pour Makolo — V2 sémantique

**Statut :** cadre conceptuel consolidé — V2 sémantique corrigée  
**Objet :** définir ce que Mayele cherche à connaître, quelles réalités méritent d’entrer dans son espace de connaissance, comment distinguer réalités, propriétés, relations, conditions, propositions et supports de connaissance, et comment cette connaissance reste orientée vers les besoins réels de Makolo.  
**Portée de cette version :** sémantique de connaissance uniquement. Elle ne fixe ni tables, ni stockage, ni runtime, ni agents, ni orchestration technique, ni structure définitive du dossier `mayele/`.  

**Correction structurante de la V2 :** `Fact` n'est plus traité comme une catégorie sœur de `Property`, `Relation` et `Condition`. Mayele distingue la structure décrite du monde de la proposition épistémique qui affirme quelque chose à son sujet ; le mot *fait* qualifie une proposition suffisamment établie.  


---

# 1. Finalité

La promesse générale reste :

> **Makolo marche pour vous.**

Pour pouvoir préparer, comprendre et accompagner des actions réelles, Makolo doit disposer d’une connaissance du monde qui ne soit pas reconstruite intégralement à chaque besoin.

Mayele constitue le système chargé de développer cette connaissance.

Mais Mayele n’a pas vocation à construire une encyclopédie universelle ni à indexer indistinctement tout ce qui existe.

Sa finalité est plus précise :

> **Construire progressivement la connaissance du monde nécessaire à Makolo pour comprendre ce qui peut être fait, vécu ou obtenu, ce qui le permet, ce qui le conditionne, ce qui le bloque, qui intervient, selon quelles règles, et comment reconnaître le résultat réel.**

La connaissance acquise doit être réutilisable entre plusieurs personnes, Espaces et situations.

La personnalisation vient ensuite.

La géographie, les intérêts personnels ou la situation courante d’un utilisateur ne constituent donc pas des frontières générales de ce que Mayele peut connaître. Le cadre Makolo distingue déjà acquisition globale de connaissance et pertinence locale/personnelle.

---

# 2. Principe directeur

Mayele travaille dans un espace de connaissance **cadré par le monde d’action de Makolo**.

Il connaît déjà les grandes formes d’action que Makolo veut représenter.

Il ne part donc pas d’une question illimitée comme :

> « Quelles possibilités existent dans le monde ? »

Il part de réalités dont Makolo connaît déjà la nature générale.

Les verticales d’action retenues sont :

```text
EVENT
TRANSPORT
SERVICE
OPPORTUNITY
FUNDING
OBTENTION
```

Elles correspondent respectivement à des résultats métier différents :

```text
participer / vivre quelque chose
→ Event

se déplacer / faire déplacer
→ Transport

faire traiter / exécuter / délivrer quelque chose
→ Service

accéder à une possibilité conditionnelle ou sélective
→ Opportunity

mobiliser des ressources financières
→ Funding

obtenir une chose, une ressource ou son usage
→ Obtention
```

Cette distinction est fondée sur le **résultat principal recherché**, et non sur la présence d’une date, d’un paiement, d’un document ou d’une procédure.

---

# 3. Deux grandes formes de connaissance

MAYELE KNOWLEDGE RESEARCH comporte deux ensembles complémentaires.

## 3.1. Vertical Knowledge

Il s’agit de connaître les instances réelles des verticales Makolo et ce qui est nécessaire pour les comprendre.

Exemples :

```text
un concert
un trajet ferroviaire
une consultation médicale
une bourse
un programme de financement
une possibilité de louer une machine
```

Une réalité verticale peut être retenue même si ses informations sont encore très incomplètes.

---

## 3.2. Object Knowledge

Mayele connaît également des réalités qui ne sont pas elles-mêmes des verticales mais qui peuvent participer à leur compréhension.

Exemples :

```text
TOEFL
IELTS
passeport
visa
CV
RCCM
Université de Montréal
ambassade
gare
aéroport
certificat
permis
règlement
formulaire
devise
procédure administrative
```

Ces objets peuvent exister et être connus indépendamment d’une Opportunity, d’un Transport ou d’un Service particulier.

Ils deviennent ensuite des constituants réutilisables de nombreuses relations.

---

# 4. La matrice de connaissance Makolo

Pour chaque verticale, Mayele cherche à comprendre différentes dimensions.

La matrice retenue est :

```text
POSSIBILITY
OUTCOME
REQUIREMENT
EVIDENCE
ACTOR
AUTHORITY
SPATIOTEMPORAL
PROCEDURE
ACCESS
CAPACITY
ECONOMIC
OPERATIONAL
REFERENCE
```

Ces termes désignent d’abord des **dimensions de connaissance contextuelles**, pas nécessairement des types d’objets.

---

# 5. Matrice complète

| Facette | Event | Transport | Service | Opportunity | Funding | Obtention |
|---|---|---|---|---|---|---|
| **POSSIBILITY** | Quels événements existent ? | Quels transports existent ? | Quels services existent ? | Quelles opportunités existent ? | Quels financements existent ? | Que peut-on obtenir ? |
| **OUTCOME** | Qu’est-ce qui constitue l’accomplissement réel ? | Quand le déplacement est-il réellement accompli ? | Quel résultat doit effectivement être délivré ? | Quel résultat sélectif est réellement obtenu ? | Quand les fonds sont-ils effectivement mobilisés ? | Quand la cible est-elle réellement obtenue ? |
| **REQUIREMENT** | Quelles conditions doivent être satisfaites ? | Quelles conditions permettent le déplacement ? | Quelles conditions permettent de recevoir le service ? | Quelles conditions d’éligibilité ou de candidature ? | Quelles conditions de financement ? | Quelles conditions d’obtention ? |
| **EVIDENCE** | Quelles preuves ou attestations sont acceptées ? | Quels documents ou justificatifs ? | Quels justificatifs ? | Quels diplômes, certificats ou preuves ? | Quels justificatifs ? | Quelles preuves de conformité, droit ou réception ? |
| **ACTOR** | Qui organise ou participe ? | Qui opère ou transporte ? | Qui fournit ou reçoit ? | Qui propose ou sélectionne ? | Qui finance ou reçoit ? | Qui fournit, attribue ou remet ? |
| **AUTHORITY** | Qui peut autoriser ou décider ? | Qui possède l’autorité pertinente ? | Qui peut valider ou délivrer ? | Qui décide de l’admission ou attribution ? | Qui approuve ou débourse ? | Qui peut attribuer ou transférer ? |
| **SPATIOTEMPORAL** | Où et quand ? | Origine, destination, horaire, durée ? | Où et quand ? | Dates, délais, périodes, lieux ? | Périodes et échéances ? | Où et quand retirer, recevoir ou utiliser ? |
| **PROCEDURE** | Comment participer ? | Comment réserver, embarquer, voyager ? | Comment demander et recevoir ? | Comment candidater ? | Comment demander ou mobiliser ? | Comment acheter, louer, emprunter ou recevoir ? |
| **ACCESS** | Quel droit permet de participer ? | Quel droit permet de voyager ? | Quel accès est nécessaire ? | Quel accès découle éventuellement du résultat ? | Quel accès au programme ? | Quel droit d’usage ou de possession intervient ? |
| **CAPACITY** | Combien de places ? | Combien de places ou unités disponibles ? | Combien de bénéficiaires ou créneaux ? | Combien de places ou lauréats ? | Quelle enveloppe ou capacité ? | Quelle quantité est disponible ? |
| **ECONOMIC** | Prix ou frais ? | Tarif, remboursement ? | Coût ou paiement ? | Frais, aide, rémunération ? | Montant, taux, couverture ? | Prix, caution, location, paiement ? |
| **OPERATIONAL** | Maintenu, annulé, complet ? | Actif, retardé, annulé ? | Disponible, suspendu ? | Ouverte, fermée, suspendue ? | Fonds ou programme encore disponibles ? | Ressource réellement disponible ? |
| **REFERENCE** | Quelle source officielle ? | Quelles règles ou horaires de référence ? | Quelle documentation ? | Quel règlement ou appel officiel ? | Quel programme ou règlement ? | Quelle fiche, règle ou contrat ? |

---

# 6. La matrice est contextualisée

Une recherche ne porte donc pas simplement sur :

```text
REQUIREMENT
```

mais sur :

```text
OPPORTUNITY × REQUIREMENT
TRANSPORT × REQUIREMENT
SERVICE × REQUIREMENT
...
```

De même :

```text
OUTCOME
```

n’a pas le même sens selon la verticale.

## Transport

Le résultat attendu concerne le déplacement effectivement accompli.

## Service

Le résultat concerne ce qui devait réellement être traité, exécuté ou délivré.

## Opportunity

Le résultat peut être une admission, une sélection, une attribution, un recrutement ou un accès au programme.

Déposer une candidature n’est pas nécessairement le résultat final.

## Funding

Le résultat concerne les ressources financières effectivement mobilisées selon le contrat correspondant.

## Obtention

Le résultat est la chose, la ressource ou le droit d’usage effectivement obtenu.

Un paiement ou une commande ne suffit donc pas nécessairement à conclure l’Obtention, ce qui correspond au cadre métier déjà retenu.

---

# 7. Un objet n’est pas son rôle

Principe fondamental :

```text
OBJET
!=
RÔLE DE CET OBJET DANS UNE ACTION
```

Ainsi :

```text
TOEFL != EVIDENCE
Visa != REQUIREMENT
Université != ACTOR
Ambassade != AUTHORITY
Passeport != EVIDENCE
```

TOEFL est une réalité autonome.

Dans une Opportunity particulière, une règle peut ensuite établir :

```text
TOEFL >= 90
    accepté comme Evidence
    pour un Requirement linguistique
```

Dans une autre Opportunity, le seuil peut être différent.

Dans une troisième, TOEFL peut ne pas être accepté.

Le rôle appartient donc à la **relation contextuelle**, pas à l’identité fondamentale de l’objet.

---

# 8. Structure du monde connu et structure de connaissance

Pour éviter de transformer toute information en objet de graphe ou de dupliquer la même information sous plusieurs noms, Mayele distingue désormais **deux niveaux complémentaires**.

```text
STRUCTURE DU MONDE CONNU
├── Reality
├── Property
├── Relation
└── Condition

STRUCTURE DE CONNAISSANCE MAYELE
├── Proposition / Assertion
├── état épistémique
└── Knowledge Support
```

Le terme **fait** n'est donc plus placé au même niveau que `Property`, `Relation` et `Condition`.

Un fait est une proposition que Mayele considère suffisamment établie dans un contexte et une période donnés, tout en conservant les supports qui permettent de justifier cette qualification.

Cette séparation permet de ne pas créer simultanément :

```text
Property
→ deadline = 15 janvier

Fact
→ deadline = 15 janvier
```

comme deux objets indépendants portant la même information.

---

## 8.1. Réalité

Une **Reality** est quelque chose possédant une identité propre et pouvant devenir le sujet d'autres connaissances indépendamment de la phrase ou de la source dans laquelle elle a été rencontrée.

Exemples :

```text
TOEFL
Université X
Passeport
Bourse Y
Aéroport Z
Règlement R
Certificat C
```

Une réalité peut être résolue, provisoire ou encore non résolue sans cesser pour autant d'être représentable comme réalité candidate.

---

## 8.2. Propriété

Une **Property** caractérise une réalité par un attribut et une valeur, dans un contexte éventuellement temporel.

Exemples :

```text
deadline(Opportunity X) = 15 janvier
capacity(Event Y) = 120
status(Service Z) = ouvert
price(Offer A) = 50 USD
score(Attempt B) = 95
```

Il faut distinguer conceptuellement :

```text
attribut
→ deadline

valeur
→ 15 janvier

proposition portant sur cette propriété
→ deadline(Opportunity X) = 15 janvier
```

Une valeur simple — nombre, date, booléen, statut ou quantité — ne mérite généralement pas une identité autonome.

Lorsque la « valeur » est elle-même une réalité autonome et que le lien possède une sémantique utile à Makolo, une **Relation** est généralement préférable.

Exemple :

```text
ORIGIN(Transport X, Lubumbashi)
```

est conceptuellement plus riche que :

```text
Transport X.origin = "Lubumbashi"
```

car Lubumbashi est lui-même une réalité pouvant porter d'autres faits et relations.

---

## 8.3. Relation

Une **Relation** est un lien sémantiquement significatif entre deux ou plusieurs réalités possédant chacune une identité propre.

Exemples :

```text
Université X OFFERS Opportunity Y
ETS OPERATES TOEFL
Organisation A ISSUES Certificat B
Transport X ORIGIN Lubumbashi
Transport X DESTINATION Kolwezi
```

Une relation ne devient pas automatiquement vraie parce qu'elle a été extraite d'une source.

La structure relationnelle et la proposition affirmant que cette relation tient dans un contexte donné restent conceptuellement distinctes.

---

## 8.4. Condition

Une **Condition** est une expression évaluable relativement à une situation. Elle décrit ce qui doit être satisfait, ou la règle permettant de déterminer si un critère l'est.

Exemples :

```text
âge >= 18
TOEFL.score >= 90
posséder un passeport valide
paiement reçu avant le 15 janvier
```

Une condition ne dit pas à elle seule **où** elle s'applique.

Ainsi :

```text
TOEFL.score >= 90
```

est une condition.

La proposition :

```text
Cette condition s'applique au Requirement linguistique du Master X
```

est une connaissance supplémentaire et contextuelle.

La condition peut référencer des réalités, des propriétés et, lorsque nécessaire, des relations. Elle ne devient pas pour autant une nouvelle réalité autonome.

---

## 8.5. Proposition / assertion

Une **Proposition** — ou assertion, au sens de connaissance — est ce que Mayele considère comme une affirmation susceptible d'être soutenue, contredite, datée, révisée ou laissée non résolue.

Une proposition peut porter notamment sur :

```text
1. l'existence d'une réalité
2. une valeur de propriété
3. la tenue d'une relation
4. l'applicabilité d'une condition ou d'une règle
```

Exemples :

```text
Opportunity X existe.

deadline(Opportunity X) = 15 janvier 2027.

Université X OFFERS Opportunity X.

Condition(TOEFL.score >= 90)
s'applique au Requirement linguistique R.
```

La proposition est le bon niveau pour demander :

```text
qui l'affirme ?
sur quelle source ?
à quelle date ?
dans quel contexte ?
est-elle encore valable ?
existe-t-il une contradiction ?
```

Une proposition n'est pas automatiquement un fait.

---

## 8.6. Fait

Dans MAYELE KNOWLEDGE RESEARCH, un **fait** est une proposition que Mayele considère suffisamment établie dans un contexte et une période déterminés, avec des supports de connaissance conservés.

```text
FACT
!= forme structurelle parallèle à Property / Relation / Condition
```

Le mot « fait » qualifie donc l'état atteint par une proposition ; il ne crée pas par lui-même une nouvelle réalité, une nouvelle relation ou un nouveau type technique obligatoire.

Exemple :

```text
Proposition
→ deadline(Opportunity X) = 15 janvier 2027

Supports
→ règlement officiel
→ page d'admission
→ observations datées

Évaluation
→ suffisamment établie

Qualification
→ fait Mayele dans ce contexte
```

Si une autre source crédible indique le 20 janvier, Mayele ne doit pas écraser silencieusement la première proposition. Il doit conserver le conflit, les contextes et les supports jusqu'à résolution éventuelle.

---

## 8.7. Support de connaissance

Le **Knowledge Support** justifie pourquoi Mayele considère une proposition comme soutenue, contredite ou encore incertaine.

Exemples :

```text
source
document
page
observation
passage
date d'observation
provenance
contradiction éventuelle
```

Principe :

```text
CE QUE LA SOURCE DIT
!=
CE QUE MAYELE INTERPRÈTE
!=
CE QUE MAYELE CONSIDÈRE SUFFISAMMENT ÉTABLI
```

Un même support peut contribuer à plusieurs propositions ; une même proposition peut être soutenue ou contredite par plusieurs supports.

La provenance reste une dimension transverse distincte de la connaissance métier elle-même.

---

# 9. Quand une chose mérite-t-elle une identité autonome ?

Le test principal est :

> **Cette chose peut-elle elle-même devenir le sujet d’autres faits ou relations indépendamment de la phrase ou de la source dans laquelle elle a été rencontrée ?**

### TOEFL

Oui.

Mayele peut ensuite connaître :

```text
opérateur
types de test
scores
règles
références
validité
```

TOEFL mérite donc une identité propre.

### 90

Non.

Il s’agit simplement d’une valeur.

### TOEFL >= 90

Ce n’est généralement pas une nouvelle réalité.

C’est une condition.

### Master X accepte TOEFL >= 90

Cette formulation combine plusieurs niveaux :

```text
TOEFL
→ réalité

score >= 90
→ condition

ACCEPTED_AS_EVIDENCE_FOR
→ relation contextuelle

« cette relation et cette condition s'appliquent au Master X »
→ proposition
```

Cette proposition ne devient un **fait Mayele** que lorsqu'elle est suffisamment établie dans son contexte et avec ses supports conservés.

---

# 10. Trois portes d’entrée dans la connaissance Mayele

Une réalité peut être retenue pour trois raisons principales.

## 10.1. Elle est une instance candidate d’une verticale Makolo

Toute instance suffisamment individualisable de :

```text
Event
Transport
Service
Opportunity
Funding
Obtention
```

peut être retenue.

Même si presque tout le reste est encore inconnu.

Exemple :

```text
"Programme mobilité Afrique-Europe"
type probable = Opportunity
acteur = inconnu
requirements = inconnus
dates = inconnues
```

La réalité peut déjà être reconnue comme candidate.

---

## 10.2. Elle participe à une relation relevant de la matrice

Exemple :

```text
Agence A
    ISSUES
Certificat B
```

Aucune Opportunity n’est nécessaire pour retenir ces réalités.

La relation observée elle-même suffit à montrer que les objets peuvent participer à la grammaire d’action de Makolo.

Cela permet à Mayele de construire une connaissance réutilisable avant qu’un besoin utilisateur particulier apparaisse.

---

## 10.3. Elle est nécessaire pour résoudre une inconnue structurante

Exemple :

```text
Opportunity X
    DECIDED_BY
    ?
```

Une source mentionne :

```text
"l'autorité nationale compétente"
```

Mayele peut conserver cette réalité sans inventer son identité :

```text
réalité présente
identité non résolue
rôle observé = AUTHORITY
```

---

# 11. Être retenu ne signifie pas être complet

Une réalité peut entrer dans l’espace de connaissance avec peu d’informations.

Il suffit conceptuellement de disposer de :

```text
une existence candidate observable
+
un moyen provisoire de la distinguer
+
une raison structurelle de la retenir
+
une provenance
```

Il n’est pas nécessaire de connaître immédiatement :

```text
son nom officiel
son acteur
sa géographie
son prix
sa procédure
ses Requirements
sa classification définitive
```

La connaissance peut être enrichie plus tard.

Principe :

> **Retenir une réalité signifie reconnaître qu’elle mérite une identité dans la connaissance Mayele ; cela ne signifie pas prétendre déjà la comprendre complètement.**

---

# 12. Familles principales d’objets autonomes

La liste suivante constitue une grammaire de départ.

Elle ne signifie jamais que Mayele doit rechercher exhaustivement toutes les instances de chaque catégorie.

## 12.1. Verticales

```text
Event
Transport
Service
Opportunity
Funding
Obtention
```

---

## 12.2. Acteurs, organisations et institutions

```text
personne identifiable lorsque pertinente
organisation
institution
opérateur
prestataire
issuer
autorité
organisme
```

Ils peuvent ensuite jouer :

```text
ACTOR
AUTHORITY
ISSUER
OPERATOR
PROVIDER
```

selon le contexte.

---

## 12.3. Documents et instruments

```text
passeport
visa
diplôme
certificat
permis
licence
carte
credential
résultat officiel
```

Ils peuvent participer comme Requirement, Evidence, Credential ou AccessCredential selon la relation.

Les distinctions canoniques de Makolo restent importantes : Requirement, Proof, Credential, Access et AccessCredential sont différents.

---

# 13. Tests, examens et qualifications

Exemples :

```text
TOEFL
IELTS
examen
concours
assessment
certification
```

Le système d’évaluation est une réalité autonome.

En revanche :

```text
score = 95
```

est une valeur de propriété portée par une proposition concernant une tentative ou un résultat identifiable.

Et :

```text
score >= 90
```

est une condition.

---

# 14. Références normatives

Peuvent posséder une identité propre :

```text
loi
règlement
politique
guide officiel
document normatif
programme réglementaire
```

Ces réalités peuvent ensuite être reliées à d’autres objets par des relations comme :

```text
GOVERNED_BY
DOCUMENTED_BY
```

---

# 15. Procédures, formulaires et ressources

Lorsqu’ils possèdent une identité réellement autonome :

```text
procédure de demande
procédure de renouvellement
formulaire officiel
portail
guide
template
ressource structurée
```

peuvent devenir des réalités connues.

Mais une simple phrase :

```text
"remplissez le formulaire puis envoyez-le"
```

reste une instruction ou une proposition de procédure, pas nécessairement une nouvelle réalité. Elle ne devient un fait Mayele que si elle est suffisamment établie dans le contexte étudié.

---

# 16. Lieux et infrastructures

Exemples :

```text
gare
aéroport
centre
établissement
adresse identifiable
zone
juridiction
```

peuvent être des réalités autonomes.

Mais la géographie ne constitue jamais une frontière globale imposée à la recherche.

Elle apparaît dans la connaissance comme résultat :

```text
LOCATED_AT
ORIGIN
DESTINATION
VALID_IN
JURISDICTION
SERVICE_AREA
```

---

# 17. Objets économiques

Peuvent parfois être autonomes :

```text
Offer
plan
tarif structuré
devise
programme financier
modalité contractuelle identifiable
```

En revanche :

```text
prix = 50 USD
frais = 20 USD
taux = 5 %
```

restent généralement des valeurs de propriété. Les propositions qui attribuent ces valeurs à une réalité peuvent ensuite être évaluées et, lorsqu’elles sont suffisamment établies, être qualifiées de faits Mayele.

---

# 18. Ce qui ne devient généralement pas une réalité autonome

Par défaut :

```text
nombre
date
heure
prix simple
statut
quantité
score
deadline
booléen
coordonnée
seuil
phrase
fragment de page
élément d'interface
signal de popularité
```

ne sont pas des objets indépendants.

Ils décrivent autre chose.

Cette règle est essentielle pour éviter l’explosion artificielle du graphe.

---

# 19. Grammaire minimale des relations

La connaissance ne doit pas devenir un ensemble arbitraire de verbes.

Les relations doivent appartenir à une grammaire contrôlée.

## 19.1. Porter ou proposer

```text
OFFERS
PROVIDES
OPERATES
ORGANIZES
FUNDS
ISSUES
```

## 19.2. Conditions et satisfaction

```text
REQUIRES
SATISFIES
ACCEPTS_AS_EVIDENCE
VALID_FOR
```

## 19.3. Autorité

```text
AUTHORIZED_BY
DECIDED_BY
ISSUED_BY
GOVERNED_BY
```

Un acteur et une autorité ne sont pas automatiquement la même chose.

---

## 19.4. Géographie et temps

```text
LOCATED_AT
ORIGIN
DESTINATION
OCCURS_AT
VALID_IN
VALID_FROM
VALID_UNTIL
```

---

## 19.5. Procédure et ressources

```text
HAS_PROCEDURE
USES_FORM
USES_RESOURCE
DOCUMENTED_BY
```

---

## 19.6. Accès

```text
REQUIRES_ACCESS
GRANTS_ACCESS
REPRESENTED_BY
```

Sans perdre la distinction :

```text
Access
!= AccessCredential
!= AccessUse
```

---

## 19.7. Économie

```text
HAS_OFFER
PRICED_IN
FUNDED_BY
ELIGIBLE_FOR
```

Toutes les informations économiques ne nécessitent toutefois pas une relation : certaines sont de simples propriétés.

---

# 20. Critère d’ajout d’une nouvelle relation

Une nouvelle relation n’est justifiée que si :

1. elle exprime une distinction utile à la matrice de connaissance ;
2. cette distinction ne peut pas être exprimée correctement par une relation existante accompagnée de propriétés ;
3. la distinction change réellement ce que Makolo peut comprendre, préparer ou calculer.

Une nouvelle formulation linguistique ne justifie donc pas un nouveau type de relation.

---

# 21. Identité et résolution

Mayele doit pouvoir connaître une réalité avant d’avoir complètement résolu son identité.

Trois situations conceptuelles sont utiles.

## 21.1. Identité résolue

Exemple :

```text
Université de Montréal
```

L’identité est suffisamment déterminée.

---

## 21.2. Identité provisoire

Exemple :

```text
"Programme mobilité Afrique-Europe annoncé par organisme X"
```

Mayele distingue suffisamment la réalité pour la conserver, mais certaines informations restent à résoudre.

---

## 21.3. Identité non résolue

Exemple :

```text
"l'autorité compétente"
```

Mayele sait que quelque chose occupe cette relation mais ne sait pas encore précisément quelle réalité.

Principe :

```text
absence d'identité complète
!=
absence de réalité
```

---

# 22. Déduplication et rapprochement

Deux mentions identiques en texte ne sont pas nécessairement la même réalité.

Deux noms différents peuvent au contraire désigner la même réalité.

La résolution peut s’appuyer conceptuellement sur :

```text
identifiants
aliases
acteurs liés
relations
propriétés discriminantes
temps
références
provenance
```

En cas d’incertitude :

> **ne pas fusionner artificiellement.**

L’incertitude doit pouvoir être conservée.

---

# 23. Connaissance incomplète

Mayele doit distinguer plusieurs dimensions qui ne doivent pas être mélangées.

## 23.1. Complétude d'une réalité

Une réalité peut être :

```text
connue sur certaines facettes
partiellement connue
encore très incomplète
```

## 23.2. État d'une facette

Pour une facette donnée, Mayele doit pouvoir distinguer au moins conceptuellement :

```text
KNOWN
PARTIALLY_KNOWN
UNKNOWN
CONTRADICTORY
NOT_APPLICABLE
```

Principe fondamental :

```text
UNKNOWN != FALSE
UNKNOWN != NONE
UNKNOWN != CLOSED
UNKNOWN != NOT_APPLICABLE
```

## 23.3. État d'une proposition

Une proposition peut être suffisamment soutenue pour être considérée comme établie, rester partiellement soutenue, être contredite par d'autres supports ou demeurer non résolue.

Cette évaluation ne doit pas être confondue avec la résolution d'identité de la réalité concernée.

```text
IDENTITY RESOLUTION
!=
KNOWLEDGE COMPLETENESS
!=
PROPOSITION ASSESSMENT
```

Le cadre Mayele ne transforme jamais silencieusement une absence d'information en information négative.

---

# 24. Applicabilité de la matrice

Les treize facettes ne sont pas toutes obligatoires pour chaque réalité.

Par exemple :

```text
Event gratuit sans contrôle d'entrée
```

peut ne pas nécessiter de connaissance `ECONOMIC` ou `ACCESS` particulière.

Une Opportunity peut ne pas avoir de `CAPACITY` publiquement connue.

Une Obtention peut ne pas avoir de Requirement particulier.

La question n’est donc pas :

> « Avons-nous rempli les treize cases ? »

mais :

> **« Quelles dimensions ont réellement un sens pour cette réalité, et que savons-nous sur chacune ? »**

---

# 25. Evidence métier et support de connaissance

La distinction est impérative.

## 25.1. EVIDENCE dans la matrice

Répond à :

> **Qu’est-ce qui peut prouver ou satisfaire une condition de l’action ?**

Exemple :

```text
Requirement
→ niveau linguistique requis

Evidence acceptée
→ TOEFL >= 90
```

---

## 25.2. Support de connaissance Mayele

Répond à :

> **Pourquoi Mayele considère-t-il cette proposition comme soutenue, contredite ou encore non résolue ?**

Exemple :

```text
proposition
→ Master X accepte TOEFL >= 90

support
→ règlement officiel
→ page de l'université
→ passage observé
→ date d'observation
```

Ainsi :

```text
ACTION EVIDENCE
!=
KNOWLEDGE SUPPORT
```

---

# 26. Exemple complet — Opportunity

Mayele rencontre :

```text
Master en ingénierie mécanique — Université X
```

Cette réalité peut entrer comme :

```text
Opportunity candidate
```

même si la connaissance est encore faible.

Mayele peut progressivement établir :

```text
ACTOR
→ Université X

SPATIOTEMPORAL
→ deadline 15 janvier

REQUIREMENT
→ diplôme de licence
→ niveau d'anglais

PROCEDURE
→ candidature en ligne

ECONOMIC
→ frais de candidature

REFERENCE
→ page officielle
```

Supposons ensuite :

```text
EVIDENCE pour anglais
→ inconnu
```

Une source énonce :

```text
TOEFL >= 90
IELTS >= 6.5
```

TOEFL et IELTS peuvent déjà exister comme réalités indépendantes dans la connaissance Mayele.

Mayele n’a alors pas besoin de les recréer.

Il peut interpréter ces seuils comme des **conditions**, puis construire les propositions contextuelles reliant ces conditions au Requirement linguistique :

```text
TOEFL >= 90
    ACCEPTED_AS_EVIDENCE
    FOR Requirement linguistique de Master X
```

```text
IELTS >= 6.5
    ACCEPTED_AS_EVIDENCE
    FOR Requirement linguistique de Master X
```

---

## 26.1. Stress-test transversal sur les six verticales

La distinction `Reality / Property / Relation / Condition / Proposition / Fact` doit tenir au-delà du seul cas Opportunity.

| Verticale | Réalités principales | Propriété / valeur | Relation | Condition | Proposition susceptible de devenir un fait |
|---|---|---|---|---|---|
| **Event** | Concert X, Organisation Y | date = 12 octobre ; capacité = 5 000 | `Y ORGANIZES Concert X` | âge >= 18 | « Concert X a lieu le 12 octobre », « Y organise Concert X », « âge >= 18 s'applique à l'entrée » |
| **Transport** | Transport X, Opérateur Y, Lubumbashi, Kolwezi | départ = 08:00 | `Y OPERATES X`, `X ORIGIN Lubumbashi`, `X DESTINATION Kolwezi` | billet valide requis | « X part à 08:00 », « Y opère X », « un billet valide est requis » |
| **Service** | Service X, Institution Y, Passeport | prix = 50 USD | `Y PROVIDES X` | posséder un passeport valide | « X coûte 50 USD », « Y fournit X », « le passeport valide est requis » |
| **Opportunity** | Master X, Université Y, TOEFL | deadline = 15 janvier | `Y OFFERS X` | TOEFL.score >= 90 | « Y propose X », « la deadline vaut le 15 janvier », « le seuil TOEFL s'applique au Requirement R » |
| **Funding** | Programme X, Institution Y | enveloppe = 100 000 USD | relation de financement ou de fourniture selon le contexte réel | entreprise enregistrée | propositions correspondantes, bornées par leur contexte et leur période |
| **Obtention** | Obtention X, cible Y, porteur Z | mode = RENT ; prix = 30 USD/jour | `Z PROVIDES X`, relation vers la cible selon la grammaire retenue | caution reçue avant retrait | « Z propose X », « le prix est 30 USD/jour », « la caution est requise avant retrait » |

Le test confirme :

```text
PROPERTY / RELATION / CONDITION
= formes de structure ou de règle

PROPOSITION
= affirmation contextualisée portant sur cette structure

FACT
= proposition suffisamment établie
```

Il confirme également la règle pratique suivante :

```text
valeur simple
→ propriété

autre réalité autonome + lien sémantiquement utile
→ relation par défaut
```

Cette règle reste un critère de conception, pas une transformation mécanique universelle.

---

# 27. Exemple — agence et certificat

Une source indique :

```text
Agence Makasi délivre
un certificat de participation
à ses employés ayant terminé son programme interne.
```

Cette connaissance peut être retenue même sans Opportunity actuellement connue.

### Réalités

```text
Agence Makasi
Certificat de participation Makasi
Programme interne Makasi
```

si chacune est suffisamment individualisable.

### Relations

```text
Agence Makasi
    ISSUES
Certificat Makasi
```

et éventuellement :

```text
Programme interne Makasi
    HAS_OUTCOME
Certificat Makasi
```

Plus tard, une Opportunity peut établir :

```text
Certificat Makasi
    ACCEPTED_AS_EVIDENCE
    FOR Requirement X
```

La connaissance acquise auparavant devient immédiatement réutilisable.

---

# 28. Connaître une catégorie ne justifie pas une recherche exhaustive

Mayele peut connaître la catégorie :

```text
CERTIFICATE
```

sans chercher automatiquement tous les certificats du monde.

Même chose pour :

```text
TEST
ORGANIZATION
DOCUMENT
RULE
PLACE
```

Principe :

```text
type connu
!=
obligation de découvrir toutes ses instances
```

Une instance devient pertinente lorsqu’elle entre par l’une des trois portes établies :

```text
verticale
relation structurante
inconnue structurante
```

---

# 29. La géographie n’est pas une frontière de connaissance

Principe définitif :

```text
GEOGRAPHY
!=
limite générale de recherche
```

Mayele peut connaître :

```text
une Opportunity au Japon
un Transport en RDC
un Service au Canada
une institution en Allemagne
un examen mondial
une règle européenne
```

La géographie est ensuite exprimée comme connaissance :

```text
located_at
valid_in
origin
destination
jurisdiction
service_area
delivery_area
```

Elle peut devenir déterminante pour une action donnée, sans limiter la connaissance globale.

---

# 30. La pertinence personnelle vient après

Une réalité peut être totalement inutile aujourd’hui pour une personne et devenir essentielle demain pour une autre.

Ainsi :

```text
connaissance commune
!=
pertinence personnelle
```

Mayele construit une connaissance réutilisable.

Makolo détermine ensuite ce qui compte dans une situation donnée.

---

# 31. Frontière sémantique

La matrice joue quatre rôles fondamentaux.

Elle permet de :

1. déterminer **quoi comprendre sur une verticale** ;
2. identifier **ce qui reste inconnu** ;
3. déterminer **quelles relations ont une valeur sémantique pour Makolo** ;
4. déterminer **quelles réalités rencontrées méritent une identité propre**.

Elle devient donc la frontière sémantique de MAYELE KNOWLEDGE RESEARCH.

Cette frontière n’est ni :

```text
géographique
personnelle
basée sur la popularité
basée sur tout ce qui existe sur Internet
```

Elle est basée sur la structure de l’action Makolo.

---

# 32. Anti-features

MAYELE KNOWLEDGE RESEARCH ne doit pas devenir :

```text
un moteur de connaissance universel sans limite
un clone d'un moteur de recherche général
un catalogue de tout ce qui existe
un graphe où chaque mot devient un nœud
un graphe où chaque verbe devient une relation
un système où toute information devient un objet
un système qui duplique une même information comme Property et Fact indépendants
un système qui confond structure du monde, proposition et fait établi
un système où un objet reçoit un rôle universel
un système où absence d'information = faux
un système limité par la position géographique d'un utilisateur
un système qui confond source et vérité
```

---

# 33. Invariants consolidés

## Invariant 1 — Structure du monde et connaissance ne sont pas le même niveau

```text
WORLD STRUCTURE
!=
KNOWLEDGE ASSERTION
```

## Invariant 2 — Réalité, propriété, relation et condition restent distinctes

```text
REALITY
!= PROPERTY
!= RELATION
!= CONDITION
```

## Invariant 3 — Fact n'est pas un frère de Property / Relation / Condition

```text
FACT
= proposition suffisamment établie

FACT
!= structure parallèle du monde
```

## Invariant 4 — Objet et rôle restent distincts

```text
OBJECT
!= ROLE
```

## Invariant 5 — Evidence métier et support de connaissance restent distincts

```text
EVIDENCE métier
!=
support/provenance de connaissance
```

## Invariant 6 — Source, interprétation et fait établi restent distincts

```text
CE QUE LA SOURCE DIT
!=
CE QUE MAYELE INTERPRÈTE
!=
CE QUE MAYELE CONSIDÈRE ÉTABLI
```

## Invariant 7 — Inconnu n'est pas faux

```text
UNKNOWN
!= FALSE
```

## Invariant 8 — Être retenu n'est pas être complet

```text
être retenu
!= être complet
```

## Invariant 9 — Type connu n'implique pas recherche exhaustive

```text
type connu
!= recherche exhaustive de toutes ses instances
```

## Invariant 10 — Géographie n'est pas frontière générale de connaissance

```text
géographie
!= frontière générale de connaissance
```

## Invariant 11 — Observation n'est pas admission canonique

```text
relation / propriété / condition observée ou interprétée
!= vérité canonique automatiquement admise
```

Les domaines Makolo restent propriétaires de leurs vérités métier. La connaissance externe reste sourcée, résolue et contrôlée avant toute admission éventuelle dans un domaine canonique.

---

# 34. Critère final d’admission d’une réalité

Une réalité mérite une identité dans MAYELE KNOWLEDGE RESEARCH lorsqu’au moins l’une des conditions suivantes est satisfaite :

### A. Verticale

Elle constitue une instance candidate de :

```text
Event
Transport
Service
Opportunity
Funding
Obtention
```

### B. Relation structurante

Elle possède une identité propre et participe à une relation appartenant à la grammaire de connaissance Makolo.

### C. Inconnue structurante

Elle est nécessaire pour représenter ou résoudre une inconnue appartenant à cette même grammaire.

Et dans tous les cas :

> **la réalité peut être retenue même si sa connaissance reste faible, provisoire, contradictoire ou partiellement non résolue.**

---

# 35. Formulation normative

> **MAYELE KNOWLEDGE RESEARCH est le cadre par lequel Mayele construit progressivement une connaissance structurée, sourcée et réutilisable du monde nécessaire à l'action Makolo. Il connaît explicitement les verticales Event, Transport, Service, Opportunity, Funding et Obtention, puis utilise une matrice commune — Possibility, Outcome, Requirement, Evidence, Actor, Authority, Spatiotemporal, Procedure, Access, Capacity, Economic, Operational et Reference — pour comprendre chacune de leurs instances. Il peut également retenir des réalités autonomes non verticales lorsqu'elles participent à une relation de cette grammaire ou sont nécessaires pour résoudre une inconnue structurante. Une réalité reste distincte de ses propriétés, relations et conditions. Mayele formule des propositions sur l'existence des réalités, leurs propriétés, leurs relations et l'applicabilité de conditions ; une proposition ne devient un fait Mayele que lorsqu'elle est suffisamment établie dans un contexte et une période déterminés avec ses supports conservés. L'admission d'une réalité ne suppose ni complétude, ni classification définitive, ni pertinence personnelle immédiate. La géographie est une propriété possible de la connaissance et non une frontière générale de recherche.**

---

# 36. Formule synthétique

```text
MAYELE KNOWLEDGE RESEARCH
=
VERTICALES CONNUES
+
MATRICE DE CONNAISSANCE
+
RÉALITÉS AUTONOMES
+
PROPRIÉTÉS
+
RELATIONS CONTRÔLÉES
+
CONDITIONS
+
PROPOSITIONS / ASSERTIONS
+
ÉVALUATION ÉPISTÉMIQUE
+
IDENTITÉS RÉSOLUES, PROVISOIRES OU NON RÉSOLUES
+
PROVENANCE / SUPPORT DE CONNAISSANCE
```

avec :

```text
VERTICALES
=
Event
Transport
Service
Opportunity
Funding
Obtention
```

et :

```text
MATRICE
=
Possibility
Outcome
Requirement
Evidence
Actor
Authority
Spatiotemporal
Procedure
Access
Capacity
Economic
Operational
Reference
```

Et avec la séparation structurante :

```text
PROPERTY / RELATION / CONDITION
= ce que Mayele cherche à décrire du monde

PROPOSITION
= ce que Mayele affirme à propos de cette structure

FACT
= proposition suffisamment établie
```

Le principe ultime reste :

> **Mayele ne cherche pas tout ce qui existe. Il construit ce qu'il faut connaître du monde pour que Makolo puisse comprendre et accompagner l'action réelle.**