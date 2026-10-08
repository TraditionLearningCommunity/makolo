# Makolo — **Piloter**
## Contrat UX consolidé — recul, compréhension, tendances, écarts, décision et ajustement

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence — surface Space `Piloter`  
**Actor Context :** Space  
**Viewer :** Profile authentifié agissant explicitement dans ce Space  
**Portée :** Web, Flutter, tablette/desktop adaptatif, Presentation, Analytics, local-first, handoffs owner-backed  
**Base runtime vérifiée :** `main@52eced16a35d779f98eb8d43bbea405fd7f7b4b0`  
**Nature :** contrat UX et de projection ; ne crée aucun domaine métier `Piloter`  
**Promesse produit :** **Makolo marche pour vous.**  
**Principe d’expérience :** **Pas le plaisir de rester. Le plaisir d’avancer.**

---

# 0. Formule

```text
Piloter
=
comprendre ce qui fonctionne
+
repérer ce qui change
+
expliquer ce qui mérite une décision
+
ouvrir la bonne profondeur
+
ajuster légitimement
```

et non :

```text
Piloter
=
dashboard KPI
+
mur de graphiques
+
score global du Space
```

---

# 1. Question humaine

Piloter répond à :

> **Est-ce que cela fonctionne ? Qu’est-ce qui change ? Que devons-nous ajuster ?**

Cette question impose une surface de recul.

Piloter n’est pas la surface du travail courant.

Il ne répond pas d’abord :

> Que dois-je faire maintenant ?

Cette question appartient à **Maintenant**.

Il ne répond pas :

> Qu’est-ce que nous opérons réellement ?

Cette question appartient à **Métier**.

Il ne répond pas :

> Qui sommes-nous ?

Cette question appartient à **Nous**.

---

# 2. Position dans Makolo

Piloter est une **surface majeure secondaire** du Space.

Il ne devient pas un onglet primaire permanent.

Le shell principal reste :

```text
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
```

Piloter peut être atteint notamment depuis :

- Nous ;
- une profondeur Métier ;
- un signal analytique ;
- une situation Now ;
- une profondeur owner ;
- un lien contextualisé.

---

# 3. Modèle mental

Le modèle mental de référence est :

```text
Piloter
→ recul
→ sens
→ tendance
→ cause / contexte
→ profondeur
→ décision / ajustement
```

La surface commence par une **lecture utile**.

Les métriques ne deviennent visibles que lorsqu’elles expliquent cette lecture ou permettent de l’approfondir.

---

# 4. Commencer par le sens

Préférer :

> **Les départs de 17 h approchent régulièrement de la capacité maximale.**

à :

> **Capacity KPI = 92 %.**

Préférer :

> **Les paiements échouent plus souvent cette semaine.**

à :

> **Payment conversion: 64 %.**

Préférer :

> **Les demandes prennent plus longtemps à être délivrées.**

à :

> **Median processing time +31 %.**

La mesure explique ensuite.

---

# 5. Piloter ≠ Analytics

Invariant :

```text
Piloter
≠ Analytics
```

Analytics est un owner ou une profondeur spécialisée.

Piloter est une Presentation qui compose des faits utiles à la décision.

---

# 6. Analytics reste propriétaire

Les séries, agrégats, tendances, mesures et calculs appartiennent aux owners analytiques ou aux domaines propriétaires.

Piloter :

- sélectionne ;
- explique ;
- hiérarchise ;
- handoff.

Il ne duplique pas les agrégats comme nouvelle vérité.

---

# 7. Piloter ≠ dashboard

Un dashboard présente souvent :

```text
KPI 1
KPI 2
KPI 3
KPI 4
graph 1
graph 2
table 1
```

Piloter doit plutôt présenter :

```text
SIGNAL
→ pourquoi cela compte
→ contexte
→ mesure défendable
→ profondeur
→ ajustement possible
```

---

# 8. Piloter ≠ Now

Un signal analytique peut être important sans être urgent.

Exemple :

```text
Les départs du vendredi sont progressivement plus chargés.
```

→ Piloter.

Si demain 17 h est déjà à capacité et une décision immédiate est nécessaire :

→ Maintenant.

---

# 9. Piloter ≠ Historique

Historique répond :

> Qu’est-ce qui s’est passé ?

Piloter répond :

> Qu’est-ce que les faits passés et présents nous apprennent pour agir ou ajuster ?

Une même donnée peut alimenter les deux.

La surface ne doit pas confondre trace et interprétation.

---

# 10. Piloter ≠ rapport statique

Piloter est vivant.

Il peut comparer des périodes et montrer des tendances.

Mais il ne devient pas un PDF permanent ou un reporting mensuel rigide.

Un export peut être une action secondaire.

---

# 11. Piloter ≠ cockpit opérationnel

Jour J et Live portent l’opération actuelle.

Piloter prend du recul.

Donc :

```text
scanner
incidents temps réel
file actuelle
passage courant
```

ne doivent pas envahir Piloter.

Leur conséquence agrégée peut y apparaître après observation.

---

# 12. Pas de score global

Invariant :

```text
Space score
= interdit
```

Pas de :

```text
Health Score 84/100
Performance Score
Trust Score global
Growth Score
Engagement Score
```

sans owner métier explicite qui possède réellement ce concept.

---

# 13. Pas de popularité comme objectif

Makolo ne pilote pas vers :

- likes ;
- watch time ;
- temps passé ;
- scroll ;
- réactions ;
- vues brutes ;
- popularité.

Une audience peut être utile si elle sert une finalité réelle.

Elle n’est pas une fin en soi.

---

# 14. Mesurer l’action réelle

Les métriques centrales doivent rester liées à :

- accomplissement ;
- capacité ;
- accès ;
- délivrance ;
- délais ;
- disponibilité ;
- incidents ;
- finance ;
- demandes ;
- présence réelle ;
- usage réel ;
- conversion métier défendable ;
- résultats réels.

---

# 15. Zéro ≠ inconnu

Invariant :

```text
0
≠ inconnu
≠ indisponible
≠ données insuffisantes
```

Ces états doivent avoir des représentations différentes.

---

# 16. Zéro

`0` signifie :

```text
mesure connue
+
valeur zéro
```

Exemple :

```text
0 demande en attente
```

peut être une bonne nouvelle.

---

# 17. Inconnu

`inconnu` signifie :

```text
la valeur existe conceptuellement
mais Makolo ne la connaît pas suffisamment
```

---

# 18. Indisponible

`indisponible` signifie :

```text
capacité ou source absente / non accessible
```

Pas :

```text
0
```

---

# 19. Données insuffisantes

`données insuffisantes` signifie :

```text
des données existent
mais elles ne suffisent pas à établir une tendance défendable
```

Message canonique possible :

> **Pas encore assez d’activité pour dégager une tendance utile.**

---

# 20. Pas de tendance sur peu de données

Une seule observation ne doit pas produire :

```text
tendance en hausse
```

sans seuil défendable.

La surface doit préférer :

```text
1 observation connue
```

ou :

```text
pas assez d’activité pour dégager une tendance
```

---

# 21. Pas d’inférence décorative

Le client ne doit jamais inventer :

- pente ;
- tendance ;
- prévision ;
- alerte ;
- anomalie ;
- comparaison ;
- score.

Ces éléments doivent venir d’un owner ou d’un calcul explicitement défini.

---

# 22. Prévision

Une prévision peut être affichée si :

- modèle défendable ;
- horizon explicite ;
- provenance ;
- limites ;
- fraîcheur.

Une prévision n’est jamais un fait observé.

---

# 23. Forecast ≠ vérité

Exemple :

```text
Au rythme actuel, la capacité pourrait être atteinte vendredi.
```

doit rester une prévision.

Pas :

```text
Complet vendredi.
```

---

# 24. Signal

L’unité UX principale de Piloter est un **Signal de pilotage**.

Un Signal n’est pas nécessairement un nouveau modèle.

Il peut être une projection dérivée de :

- Analytics ;
- Capacity ;
- Payments ;
- AccessUse ;
- Operations ;
- CRM ;
- Growth ;
- Service ;
- Commerce ;
- Transport ;
- autres owners.

---

# 25. Définition d’un Signal

Un Signal doit idéalement répondre à :

```text
QUOI ?
→ qu’est-ce qui change ou mérite compréhension ?

POURQUOI ?
→ pourquoi cela compte ?

BASE ?
→ sur quels faits ?

PORTÉE ?
→ quel Space / Activity / période ?

CONFIANCE ?
→ connu / estimé / insuffisant ?

SUITE ?
→ approfondir / ajuster / surveiller
```

---

# 26. Signal ≠ alerte

Un signal peut être :

- positif ;
- négatif ;
- neutre ;
- descriptif ;
- incertain.

Piloter ne doit pas transformer toutes les variations en warning.

---

# 27. Signal positif

Exemple :

> **Les délais de délivrance diminuent depuis trois semaines.**

Le produit peut simplement expliquer.

Pas besoin de confetti ou de gamification.

---

# 28. Signal négatif

Exemple :

> **Les échecs de paiement augmentent sur les commandes mobiles.**

Le produit doit expliquer la mesure et la profondeur.

Pas de rouge partout.

---

# 29. Signal neutre

Exemple :

> **Le samedi concentre désormais la majorité des demandes.**

Ce n’est ni bon ni mauvais sans finalité.

---

# 30. Hiérarchie perceptive

N1 :

```text
MEANINGFUL SIGNAL          P3
WHY / CONSEQUENCE          P2
TREND / SUPPORTING FACT    P1/P2
METRIC                     P1
CHART                      P0/P1
OWNER LINK                 P1
```

Un chiffre n’est jamais P3 simplement parce qu’il est grand.

---

# 31. N1 — structure conceptuelle

```text
PILOTER
│
├── CONTEXTE SPACE
├── SIGNALS UTILES
├── TERRITOIRES
│   ├── Fonctionnement ?
│   ├── Flux ?
│   ├── Capacity ?
│   ├── Délivrance ?
│   ├── Finance ?
│   ├── Acquisition ?
│   ├── Relations ?
│   ├── Incidents ?
│   ├── Automation ?
│   └── Tendances ?
│
└── DEPTH
    ├── Signal N2
    ├── Territory N2
    ├── Analytics
    ├── owner domain
    └── action légitime
```

Toutes les sections sont conditionnelles.

---

# 32. Sections possibles

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

Aucune section n’est obligatoire.

---

# 33. Sections absentes

Une section absente :

```text
≠ 0
```

Elle peut être :

- capability non utilisée ;
- owner absent ;
- permission absente ;
- données non pertinentes.

Ne pas afficher une grille remplie de zéros.

---

# 34. Operational Footprint

Le Footprint peut aider à déterminer les territoires pertinents.

Il reste un read model.

Il ne devient pas :

```text
liste de modules
```

visible à la racine.

---

# 35. Vocabulaire

La surface doit parler humainement.

Préférer :

```text
Capacité
Finance
Demandes
Délivrance
Relations
```

à :

```text
analytics.capacity
orders.metric
crm.segment
```

---

# 36. Adaptation métier

Les huit archétypes peuvent voir des priorités différentes.

Mais il existe une seule surface Piloter.

Pas huit dashboards.

---

# 37. Generic

Peut prioriser :

- activités ;
- demandes ;
- fonctionnement ;
- capacité ;
- résultats ;
- relations.

---

# 38. Creative

Peut prioriser :

- créations réellement produites ;
- événements ;
- délivrance ;
- offres ;
- publics ;
- finance.

Mais pas popularité sociale.

---

# 39. Media

Peut prioriser :

- productions ;
- réalisation ;
- cadence ;
- événements ;
- audience utile ;
- finance ;
- incidents.

Pas watch time comme objectif central.

---

# 40. Education

Peut prioriser :

- programmes ;
- sessions ;
- admissions ;
- préparation ;
- capacité ;
- présence ;
- résultats réels.

Pas classement arbitraire des apprenants.

---

# 41. Commerce

Peut prioriser :

- demandes / commandes ;
- préparation ;
- disponibilité ;
- remise / obtention ;
- paiement ;
- capacité ;
- relations.

Payment confirmé ≠ obtention accomplie.

---

# 42. Service provider

Peut prioriser :

- demandes ;
- traitement ;
- blockers ;
- délivrance ;
- délai ;
- outcomes ;
- finance.

Dossier terminé ≠ résultat positif automatique.

---

# 43. Transport

Peut prioriser :

- départs ;
- capacité ;
- accès utilisé ;
- incidents ;
- ponctualité owner-backed ;
- flux ;
- finance.

Planifié ≠ observé.

---

# 44. Community

Peut prioriser :

- initiatives ;
- actions terrain ;
- participation ;
- capacité ;
- financement ;
- résultats ;
- partenaires.

Activité terminée ≠ impact prouvé.

---

# 45. Responsabilité

Owner, Finance, exploitation, programme ou développement peuvent voir des lectures différentes.

Mais :

```text
même Piloter
+
projection différente
```

Pas :

```text
Dashboard Finance
Dashboard Ops
Dashboard Marketing
Dashboard Owner
```

comme produits séparés.

---

# 46. Responsibility lens

Le sélecteur peut réduire :

- signaux ;
- sections ;
- Activities ;
- owners ;
- mesures.

Il ne crée aucune Permission.

---

# 47. Authority

Une mesure n’est visible que si l’autorité le permet.

Exemple :

```text
finance
```

peut être masquée alors que fonctionnement reste visible.

---

# 48. Activity-limited authority

Une personne limitée à une Activity ne reçoit pas automatiquement le pilotage global du Space.

Le runtime actuel choisit déjà de ne pas exposer les Analytics Space globaux dans ce cas.

Le contrat conserve cette prudence.

---

# 49. Space-wide vs Activity analytics

Piloter peut handoff vers :

```text
Space
→ lecture globale

Activity
→ profondeur analytique de cette Activity
```

sans mélanger les scopes.

---

# 50. Finance

Les montants sont particulièrement sensibles.

Leur présence exige :

- Permission ;
- devise ;
- période ;
- portée ;
- owner ;
- définition claire.

---

# 51. Multi-devise

Interdit :

```text
USD + EUR + CDF
→ un seul total arbitraire
```

sans taux, date et règle de conversion défendables.

Le runtime actuel conserve les devises séparées.

Le contrat recommande de maintenir cette honnêteté.

---

# 52. Gross / refunds / net

Si exposés :

```text
Brut
Remboursements
Net
```

doivent garder leur définition owner.

Pas de réinterprétation locale.

---

# 53. Finance ≠ profit

```text
net payments
≠ profit
```

sans coûts complets et contrat comptable approprié.

Piloter ne doit pas afficher « bénéfice » depuis de simples paiements nets.

---

# 54. Capacity

Capacity répond :

```text
combien ?
```

Piloter peut montrer :

- niveau ;
- pression ;
- saturation ;
- disponibilité ;
- tendance.

Mais Capacity ne dit pas :

```text
où ?
```

Placement reste distinct.

---

# 55. Capacity ≠ débit

Un système peut avoir de la capacité mais un mauvais flux.

Exemple :

```text
1000 places
+
une seule entrée fonctionnelle
```

Piloter doit pouvoir distinguer Capacity et débit si owners disponibles.

---

# 56. Waitlist

Waitlist :

```text
attendre une place
```

Elle ne doit pas être confondue avec Live Queue :

```text
attendre son tour avec un droit
```

Les métriques de pilotage doivent préserver cette distinction.

---

# 57. Access

Access peut produire des signaux de droits accordés.

AccessUse peut produire des observations d’usage.

```text
Access
≠ AccessUse
```

---

# 58. Participation / présence

Exemple :

```text
used_tickets / active_tickets
```

peut produire un taux de présence dans un contrat Event spécifique.

Ce ratio ne devient pas un taux universel pour toutes les Activities.

---

# 59. Flux

Flux peut couvrir selon owner :

- entrées ;
- sorties ;
- débit ;
- demandes ;
- transitions ;
- commandes ;
- dossiers ;
- passages.

Le mot doit rester contextualisé.

---

# 60. Délivrance

La délivrance doit mesurer un résultat réel selon le domaine.

Exemples :

- Service délivré ;
- obtention accomplie ;
- commande remise ;
- session réalisée ;
- trajet accompli.

Pas simplement :

```text
Payment succeeded
```

---

# 61. Outcomes

Un outcome doit venir du propriétaire.

Piloter ne déduit pas :

```text
succès
```

depuis un status technique générique.

---

# 62. Acquisition

Acquisition peut être utile pour certains Spaces.

Mais elle ne doit pas devenir :

- Growth vanity metrics ;
- impressions ;
- vues ;
- clicks ;

sans lien clair avec une finalité réelle.

---

# 63. Relations

Piloter peut comprendre :

- nouveaux contacts ;
- relations actives ;
- demandes ;
- partenaires ;
- groupes ;
- publics ;
- fidélité.

Mais la surface relationnelle principale reste Personnes & relations.

---

# 64. Audiences

Une Audience est un owner CRM.

Piloter peut montrer une évolution pertinente.

Mais il ne confond pas :

```text
Audience
≠ followers
≠ popularity
```

---

# 65. Partners

Les performances partenaire peuvent exister si owner-backed.

Mais un partenaire n’est pas noté globalement par défaut.

---

# 66. Incidents

Un incident actuel important :

→ Now / Jour J.

Une tendance d’incidents :

→ Piloter.

Exemple :

> **Les contrôles invalides augmentent sur l’entrée Nord depuis quatre semaines.**

---

# 67. Automation

Piloter peut expliquer :

- combien d’automations sont actives ;
- quelles conséquences elles produisent ;
- quels échecs significatifs existent ;
- quels volumes sont affectés.

Mais :

```text
nombre de règles
≠ performance
```

---

# 68. Automation health

Une Automation ne doit pas être jugée « bonne » simplement parce qu’elle s’exécute.

Il faut relier l’analyse à sa finalité.

---

# 69. Tendances

Une tendance doit expliciter :

- période ;
- comparaison ;
- base ;
- sens ;
- éventuellement incertitude.

---

# 70. Périodes

Les périodes candidates peuvent être :

```text
7 jours
30 jours
90 jours
personnalisé
```

mais elles ne sont pas universelles.

Le domaine et la densité de données doivent guider.

---

# 71. Comparaison

Comparaisons légitimes :

```text
période précédente
même période précédente
avant / après un changement
cohorte comparable
Activity comparable
```

si le calcul est défendable.

---

# 72. Comparaison trompeuse

Interdit :

```text
cette semaine vs semaine précédente
```

si la première n’est qu’à moitié écoulée sans normalisation ou explication.

---

# 73. Causalité

Piloter doit distinguer :

```text
corrélation
≠ cause
```

Bon :

> **Les abandons ont augmenté après le changement de paiement. Cela mérite vérification.**

Mauvais :

> **Le changement de paiement a causé les abandons.**

sans preuve.

---

# 74. Anomalie

Une anomalie doit provenir d’un calcul défendable.

Pas de badge « anomalie » basé sur une simple variation visuelle.

---

# 75. Explication

Une profondeur Signal peut montrer :

```text
Signal
Base
Période
Comparaison
Ce que Makolo sait
Ce qui reste incertain
Owner
Action possible
```

---

# 76. Action depuis Piloter

Une action peut être :

- ouvrir Capacity ;
- ajuster une configuration ;
- ouvrir Payment ;
- inspecter une Activity ;
- ouvrir Automation ;
- revoir un partenaire ;
- préparer une action via Mark ;
- surveiller.

Mais Piloter ne devient pas la source de la mutation.

---

# 77. Action importante

Une mutation importante doit passer par l’owner et ses confirmations.

Piloter peut dire :

> **Ajuster la capacité**

mais la mutation appartient à Capacity.

---

# 78. Mark

Piloter peut handoff vers Mark :

```text
« Prépare une analyse de ces échecs de paiement. »
```

ou :

```text
« Aide-moi à ajuster les prochains départs. »
```

Mark orchestre.

Piloter ne crée pas un chat analytique permanent.

---

# 79. Maintenant

Un Signal peut produire une Situation Now si :

- conséquence actuelle ;
- action légitime ;
- urgence ou importance présente.

Pas automatiquement.

---

# 80. Métier

Piloter peut handoff vers l’objet métier concerné.

Exemple :

```text
départs de 17 h
→ Transport
→ route / occurrences
```

---

# 81. Nous

Nous reste la porte institutionnelle depuis laquelle Piloter est naturellement accessible.

Retour doit conserver le contexte.

---

# 82. Personnes & relations

Un signal relationnel peut handoff vers Personnes & relations.

Exemple :

> **Les demandes provenant des partenaires augmentent.**

→ profondeur Partners/CRM selon owner.

---

# 83. Historique

Piloter peut ouvrir Historique pour examiner les faits passés.

Historique ne doit pas absorber la synthèse de pilotage.

---

# 84. Jour J / Live

Piloter peut handoff vers une Occurrence si l’analyse pointe une réalité actuelle.

Mais Piloter ne devient pas temps réel.

---

# 85. N1 — représentation

Candidate :

```text
Piloter

À comprendre

Les départs de 17 h approchent régulièrement
de la capacité maximale.

Sur les 4 dernières semaines,
3 départs sur 4 ont dépassé 90 %.

[Comprendre] [Voir les départs]

Autres signaux
...
```

Les chiffres soutiennent le message.

---

# 86. N1 — pas de wall

La racine doit éviter :

```text
12 métriques
8 graphiques
5 tableaux
```

Le volume doit être borné par l’utilité.

---

# 87. Priorité des signaux

Ordre candidat :

```text
impact sur accomplissement
+
conséquence potentielle
+
confiance
+
période
+
responsabilité
```

Pas :

```text
plus grosse variation
```

automatiquement.

---

# 88. Signal cardinalité

La racine peut afficher plusieurs signaux.

Mais elle n’a pas besoin d’un quota artificiel fixe.

Un Space calme peut avoir :

```text
aucun signal utile
```

---

# 89. Calm state

Exemple :

```text
Piloter

Rien ne demande d’ajustement évident pour le moment.

Les données récentes restent stables.
```

Seulement si base suffisante.

---

# 90. Insufficient data state

Exemple :

```text
Piloter

Pas encore assez d’activité
pour dégager une tendance utile.

Les faits connus restent disponibles.
```

---

# 91. Empty owner state

Si aucun owner Analytics pertinent n’existe :

```text
Aucune lecture de pilotage n’est disponible pour le moment.
```

Pas :

```text
0 partout
```

---

# 92. Permission state

Exemple :

```text
Piloter

Le pilotage global n’est pas disponible
dans votre responsabilité actuelle.
```

Ne pas révéler les métriques cachées.

---

# 93. Partial state

Exemple :

```text
Fonctionnement ✓
Capacity ✓

Finance
Impossible d’actualiser.
[Réessayer]
```

Le reste reste utilisable.

---

# 94. Offline

Piloter peut conserver un snapshot.

Mais les tendances sensibles doivent afficher leur fraîcheur si elle compte.

---

# 95. Snapshot ≠ actuel

Un signal local stale ne doit pas être présenté comme vérité présente.

Exemple :

```text
Dernière analyse connue · hier 18:00
```

---

# 96. Freshness

Chaque territoire peut avoir sa propre fraîcheur.

Finance, Live operations et CRM n’ont pas forcément le même horizon.

---

# 97. Refresh

Préserver :

- signaux connus ;
- sélection ;
- période ;
- filtres ;
- profondeur.

Pas de flash destructeur.

---

# 98. Error

Une erreur répond :

1. quelle lecture a échoué ?
2. quelles données restent utilisables ?
3. quand a eu lieu la dernière actualisation ?
4. que peut-on faire ?

---

# 99. N2 — Signal

Candidate :

```text
← Piloter

Capacité des départs de 17 h

Ce qui change
3 départs sur 4 ont dépassé 90 %.

Période
4 dernières semaines

Ce que cela peut signifier
La marge restante est faible.

Ce que Makolo ne sait pas encore
Cette tendance ne dit pas si la demande continuera.

Données
[graph simple]

[Voir les départs]
[Approfondir dans Analytics]
```

---

# 100. N2 — Territory

Exemple :

```text
Finance

À comprendre
Les remboursements augmentent.

Mesures
Brut
Remboursements
Net

Par devise
USD
CDF

[Approfondir]
```

---

# 101. N3

N3 appartient aux owners :

- Analytics ;
- Growth ;
- Payment ;
- Capacity ;
- Event Analytics ;
- Service Analytics ;
- CRM ;
- Operations ;
- Automation.

Piloter ne recrée pas ces profondeurs.

---

# 102. Graphiques

Un graphique existe seulement s’il améliore une comparaison.

Types candidats :

- ligne ;
- barres ;
- distribution ;
- série temporelle ;
- breakdown ;
- cohortes si légitimes.

Pas de camembert décoratif automatique.

---

# 103. Graphique ≠ visualisation obligatoire

Si :

```text
3 sur 4 départs > 90 %
```

est plus clair en texte, le graphique peut être inutile.

---

# 104. Axes et unités

Tout graphique doit préciser :

- période ;
- unité ;
- échelle ;
- légende utile.

Pas de graphique sans contexte.

---

# 105. Couleur

La couleur ne porte pas seule :

- hausse ;
- baisse ;
- positif ;
- négatif.

Utiliser labels, flèches, texte ou symboles accessibles.

---

# 106. Rouge

Rouge n’est pas synonyme de :

```text
baisse
```

Une baisse peut être positive.

Exemple :

```text
incidents ↓
```

est bonne nouvelle.

---

# 107. Green washing UX

Une hausse n’est pas automatiquement verte.

Exemple :

```text
remboursements ↑
```

n’est pas positive.

Le sens dépend du domaine.

---

# 108. Tables

Une table est légitime pour comparaison détaillée.

Sur Compact, préférer rows.

Sur Wide, table si le volume et les colonnes le justifient.

---

# 109. Drill-down

Le drill-down doit suivre :

```text
sens
→ données
→ owner
```

pas :

```text
dashboard
→ dashboard
→ dashboard
```

---

# 110. Search

Piloter n’a pas besoin d’une Search globale permanente.

Une profondeur analytique peut rechercher une Activity ou un événement si volume.

---

# 111. Filtres

Filtres possibles :

- période ;
- Activity ;
- territoire ;
- responsabilité ;
- lieu ;
- type de réalité.

Uniquement si owner-backed.

---

# 112. Filtres ≠ authority

Un filtre ne doit pas permettre d’afficher une Activity hors scope.

---

# 113. Compact

Compact :

```text
single pane
signals first
graphs compact
N2 par navigation
```

Pas de grille KPI 2x4 en haut.

---

# 114. Medium

Medium peut utiliser :

```text
signals + preview
```

si une sélection est ouverte.

---

# 115. Wide

Wide peut utiliser :

```text
NAV | SIGNALS | FOCUS
```

après sélection.

Ou :

```text
content max width
```

si aucun N2.

---

# 116. Very Wide

L’espace supplémentaire ne justifie pas :

- plus de métriques ;
- plus de charts ;
- sidebar permanente de KPIs ;
- heatmap décorative.

Il peut servir à :

- comparer ;
- ouvrir N2 ;
- montrer un graphique réellement utile.

---

# 117. Adaptive conservation

Conserver :

- période ;
- responsabilité ;
- filtres ;
- signal sélectionné ;
- scroll ;
- territoire ;
- chart focus ;
- owner depth.

---

# 118. Back

N2 → N1 conserve :

- signal ;
- scroll ;
- période ;
- filtres.

---

# 119. Resume

Après interruption :

1. montrer snapshot sûr ;
2. actualiser ;
3. revalider authority ;
4. signaler changements significatifs ;
5. préserver sélection.

---

# 120. Local-first

Le client peut conserver :

- projection Piloter ;
- signaux calculés serveur ;
- mesures visibles ;
- période ;
- sélection.

Le client ne devient pas owner des calculs.

---

# 121. Calcul local

Des calculs purement Presentation peuvent être locaux si :

- déterministes ;
- non autoritatifs ;
- clairement basés sur données locales ;
- aucune décision sensible.

Mais les métriques métier doivent préférer owner/backend.

---

# 122. Authority revalidation

Toute profondeur sensible exige revalidation.

Finance notamment.

---

# 123. Privacy

Les agrégats peuvent révéler des informations privées.

Exemple :

```text
1 bénéficiaire
+
montant
+
petit groupe
```

peut permettre une réidentification.

La projection doit appliquer divulgation minimale.

---

# 124. Small-n protection

Quand un agrégat porte sur très peu de personnes, la Presentation peut devoir :

- masquer ;
- regrouper ;
- arrondir ;
- réduire la profondeur.

Seulement selon contrat privacy.

Le client ne doit pas inventer une règle statistique silencieuse.

---

# 125. PII

Piloter ne doit pas exposer des listes nominatives sauf si une profondeur owner et authority l’exige.

---

# 126. Export

Export CSV/PDF peut exister en profondeur.

Il n’est pas une action primaire N1.

Il doit respecter les mêmes permissions.

---

# 127. Sharing

Partager une analyse n’accorde pas la visibilité aux données sources.

Toute projection partagée doit avoir son propre contrat.

---

# 128. Notifications

Piloter n’envoie pas des notifications pour chaque variation.

Une tendance devient notification seulement si elle a une conséquence importante selon Notification/Now.

---

# 129. Automation

Un signal ne crée pas automatiquement une Automation.

Le passage :

```text
signal
→ règle automatique
```

est une décision distincte et autorisée.

---

# 130. Adjustement

Piloter peut proposer un ajustement seulement si :

- owner existe ;
- capability existe ;
- conséquence compréhensible ;
- authority présente.

---

# 131. Suggestion ≠ décision

Exemple :

> **Vous pourriez ouvrir davantage de capacité si l’exploitation le permet.**

n’est pas :

> **Makolo augmentera la capacité.**

---

# 132. Human choice

Quand plusieurs options impliquent des arbitrages :

- coût ;
- expérience ;
- équité ;
- risque ;
- ressources ;

Makolo présente le choix.

Il ne fabrique pas une préférence globale.

---

# 133. Externalités

Une action de pilotage peut affecter des tiers.

Exemple :

```text
augmenter Capacity
→ plus de personnes
→ charge opérationnelle
→ sécurité
```

Piloter doit pouvoir handoff vers les owners nécessaires.

---

# 134. Causal stop

L’analyse doit s’arrêter lorsqu’aller plus loin ne change plus :

- décision ;
- action ;
- surveillance ;
- explication utile.

Piloter n’est pas un outil d’analyse infinie.

---

# 135. Current runtime — projection

Le runtime actuel possède :

```text
organizations/api/space_pilot_projection.py
```

La projection comprend actuellement :

```text
authority
sections
signals
links
capabilities
```

La section `analytics` peut exposer :

```text
metrics
money
signals
source
generated_at
coverage
```

---

# 136. Current runtime — authority

Actuellement, la vue globale Analytics Space exige :

```text
direct Space authority
+
analytics.view
```

Les financials ajoutent :

```text
analytics.financials.view
```

Le contrat conserve ces séparations.

---

# 137. Current runtime — métriques

La projection actuelle sait notamment produire :

- events_count ;
- published_count ;
- upcoming_count ;
- active_tickets ;
- used_tickets ;
- confirmed_orders ;
- waitlist_waiting ;
- attendance_percent ;
- money totals.

Ces métriques sont surtout Event/Ticket-centric.

Elles ne doivent pas être présentées comme universelles pour tous les archétypes.

---

# 138. Current runtime — coverage

Le portfolio actuel est borné aux derniers événements visibles, jusqu’à une limite technique.

Le contrat exige que la portée soit affichable et compréhensible.

Une limite technique ne doit pas être confondue avec « toutes les données du Space ».

---

# 139. Current runtime — signals

Le payload possède déjà :

```text
signals
```

mais la projection Space actuelle les laisse vides.

Le contrat UX donne précisément le rôle cible de cette couche :

```text
sens avant métrique
```

---

# 140. Current runtime — Analytics profond

`analytics_app` possède déjà des insights Event capables de signaler :

- pression Capacity ;
- Waitlist ;
- friction de paiement ;
- accélération ou ralentissement de ventes ;
- présence ;
- prévision de sold-out ;
- commandes pending.

Ces capacités doivent être réutilisées ou généralisées proprement.

Ne pas réécrire un second moteur d’insights dans Presentation.

---

# 141. Current runtime — finance

Le runtime conserve les devises séparées et applique des permissions financières.

C’est un bon invariant à préserver.

---

# 142. Current runtime — Flutter

Le repository Flutter connaît déjà :

```text
space.pilot
```

et sait le synchroniser comme projection Space.

Le contrat ne justifie donc pas une nouvelle architecture mobile.

Il faut faire mûrir sa Presentation.

---

# 143. Gap principal

La projection actuelle est encore :

```text
metrics-first
```

La cible est :

```text
meaning-first
```

Il faut donc pouvoir dériver ou fournir des Signaux défendables sans déplacer les vérités métier dans le client.

---

# 144. Gap archétypal

Le runtime actuel est surtout Event/Ticket analytics.

Le contrat cible :

- Transport ;
- Education ;
- Services ;
- Commerce ;
- Community ;
- Creative ;
- Media ;
- Generic ;

uniquement lorsque les owners correspondants disposent de mesures défendables.

---

# 145. Gap transversal

Le futur Piloter doit être capable de composer plusieurs owners sans les fusionner.

Exemple :

```text
Capacity
+
Payment
+
Operations
```

peuvent expliquer une même situation.

Mais chacun garde ses faits.

---

# 146. Pas de migration exigée

Ce contrat n’impose pas de nouveau modèle.

Priorité :

1. réutiliser Analytics existants ;
2. enrichir selectors / services ;
3. composer Presentation ;
4. ajouter read models si nécessaire ;
5. ne persister un Signal que si un besoin métier spécifique le justifie réellement.

---

# 147. Golden candidates

## G-PILOT-01 — Compact / Signal utile

```text
Piloter

À comprendre

Les départs de 17 h approchent
régulièrement de la capacité maximale.

3 sur 4 au-dessus de 90 %
sur les 4 dernières semaines.

[Comprendre]
```

---

# 148. G-PILOT-02 — Compact / Insufficient data

```text
Piloter

Pas encore assez d’activité
pour dégager une tendance utile.

Les faits connus restent disponibles.
```

---

# 149. G-PILOT-03 — Compact / Stable

```text
Piloter

Rien ne demande d’ajustement évident
pour le moment.

Les données récentes restent stables.
```

seulement si défendable.

---

# 150. G-PILOT-04 — Compact / Finance hidden

Functioning visible.

Finance absent.

Aucun placeholder :

```text
Finance: 0
```

---

# 151. G-PILOT-05 — Compact / Activity-limited

```text
Le pilotage global n’est pas disponible
dans cette responsabilité.
```

Aucune fuite.

---

# 152. G-PILOT-06 — N2 Signal

Signal + base + période + incertitude + owner handoff.

---

# 153. G-PILOT-07 — Medium

```text
SIGNALS | PREVIEW
```

après sélection.

---

# 154. G-PILOT-08 — Wide

```text
NAV | PILOTER | SIGNAL DETAIL
```

Pas de KPI wall.

---

# 155. G-PILOT-09 — Multi-currency

```text
USD
CDF
EUR
```

séparées.

Pas de total global sans conversion défendable.

---

# 156. G-PILOT-10 — Forecast

Prévision explicitement marquée.

Pas de confusion avec observé.

---

# 157. G-PILOT-11 — Partial error

Capacity disponible.

Finance en erreur.

Surface restante utilisable.

---

# 158. G-PILOT-12 — Offline / stale

Snapshot conservé.

Freshness visible là où elle compte.

---

# 159. G-PILOT-13 — Archétype service

```text
Les dossiers prennent plus longtemps
à être délivrés depuis trois semaines.
```

Handoff vers Services Analytics / dossiers.

---

# 160. G-PILOT-14 — Archétype community

```text
Les actions terrain mobilisent plus de participants,
mais le financement disponible reste stable.
```

Seulement si deux owners fournissent ces faits.

Pas de score d’impact.

---

# 161. G-PILOT-15 — textScale 1.6

Le signal reste premier.

Les metrics wrap.

Un split peut retomber en single pane.

---

# 162. Viewports Golden

```text
360 × 800
430 × 932
834 × 1112
1440 × 900
1728 × 1117
```

Text scale :

```text
1.0
1.3
1.6
```

---

# 163. États critiques

```text
signal
multiple_signals
stable
insufficient_data
known_zero
unknown
unavailable
partial
offline
stale
permission_denied
activity_limited
forecast
multi_currency
```

---

# 164. Recognition test

En 500 ms :

```text
où suis-je ?
→ Piloter

quel mode ?
→ recul / compréhension / ajustement

qu’est-ce qui domine ?
→ un sens utile
```

Pas :

```text
un compteur
un chart
un KPI
```

---

# 165. Blur test

Texte flouté :

- le signal principal reste dominant ;
- les métriques sont secondaires ;
- le chrome est calme ;
- aucune grille KPI ne devient le dominant visuel.

---

# 166. Deletion test

Chaque métrique doit répondre :

> Si je la retire, perd-on une compréhension ou une décision utile ?

Si non, elle n’a probablement pas besoin d’être au N1.

---

# 167. Competition test

Une surface ne doit pas avoir :

```text
8 nombres P3
```

Un signal principal peut dominer.

Les autres restent P1/P2.

---

# 168. Accessibility

MUST :

- charts compréhensibles sans couleur ;
- alternative textuelle aux visualisations ;
- text scale ;
- focus clavier ;
- unités prononcées clairement ;
- nombres formatés localement ;
- Reduce Motion ;
- tab order logique ;
- état connu/inconnu/insuffisant accessible ;
- aucune information critique uniquement visuelle.

---

# 169. Motion

Motion sobre.

Un changement de tendance peut être signalé par transition légère.

Pas d’animation de ticker financier ou dashboard temps réel.

---

# 170. Palette

Palette Makolo :

```text
#5232DB
#2B176E
#FF704D
#FAF7F5
#0F172A
```

La couleur rouge/verte ne doit pas encoder seule le sens.

---

# 171. Anti-features

Piloter ne doit jamais devenir :

- dashboard KPI par défaut ;
- score global ;
- health score ;
- wall de charts ;
- admin dashboard ;
- cockpit temps réel ;
- BI générique ;
- ERP ;
- page Analytics brute ;
- page Finance générique ;
- Growth dashboard permanent ;
- ranking de performances humaines ;
- ranking de Spaces ;
- popularity dashboard ;
- watch-time dashboard ;
- social engagement analytics ;
- faux forecast ;
- faux insight ;
- calcul local de vérité ;
- tendance avec une seule donnée ;
- regroupement arbitraire de devises ;
- somme de métriques incomparables ;
- alertes sur chaque variation ;
- deuxième Now ;
- deuxième Jour J ;
- second moteur Analytics.

---

# 172. Invariants gelés

1. Piloter est une surface majeure secondaire.
2. Piloter = recul, pas travail courant.
3. Piloter ≠ dashboard.
4. Piloter ≠ Analytics.
5. Piloter ≠ Now.
6. Piloter ≠ Historique.
7. Piloter ≠ Jour J.
8. Piloter commence par le sens.
9. Signal utile > KPI brut.
10. Les chiffres approfondissent.
11. Graphique seulement s’il aide.
12. 0 ≠ inconnu.
13. 0 ≠ indisponible.
14. 0 ≠ données insuffisantes.
15. Inconnu ≠ données insuffisantes.
16. Forecast ≠ observé.
17. Corrélation ≠ causalité.
18. Pas de score global.
19. Pas de popularité comme objectif.
20. Pas de watch time comme objectif.
21. La mesure suit l’action réelle.
22. Analytics reste owner.
23. Finance reste permission-first.
24. Multi-devise reste séparée sans conversion défendable.
25. Net payments ≠ profit.
26. Capacity ≠ Placement.
27. Capacity ≠ débit.
28. Waitlist ≠ Live Queue.
29. Access ≠ AccessUse.
30. Payment ≠ fulfillment.
31. Activité terminée ≠ impact prouvé.
32. Responsibility ≠ authority.
33. Filtre ≠ Permission.
34. Activity-limited ≠ Space-wide.
35. Les sections absentes disparaissent.
36. Section absente ≠ zéro.
37. Signal positif ≠ gamification.
38. Signal négatif ≠ rouge obligatoire.
39. Les actions mutent via owner.
40. Presentation ne possède pas les agrégats.
41. Offline conserve un snapshot, pas le présent.
42. Erreur locale ≠ panne globale.
43. Responsive adapte la géométrie, pas les vérités.
44. Same surface, different responsibility projections.
45. Une analyse s’arrête quand aller plus loin n’améliore plus l’action ou l’explication.

---

# 173. Critères de sortie serveur

Le serveur / owners doivent démontrer :

- authority-first ;
- scope explicite ;
- période explicite ;
- état connu/inconnu/insuffisant ;
- generated_at ;
- coverage ;
- finance permission-gated ;
- multi-devise honnête ;
- aucune mesure inventée ;
- signals owner-backed ou dérivés par service explicable ;
- handoffs vers owner ;
- aucun score global ;
- pas d’IDOR.

---

# 174. Critères de sortie Presentation

Presentation est conforme si :

- sens avant mesure ;
- signal principal lisible ;
- chiffres secondaires ;
- chart optionnel ;
- état insuffisant clair ;
- zéro clair ;
- scope clair ;
- incertitude claire ;
- owner depth progressive ;
- pas de dashboardification.

---

# 175. Critères de sortie Web

Le Web est conforme lorsque :

- Piloter reste secondaire ;
- il est accessible depuis Nous ;
- la racine est meaning-first ;
- Activity-limited est protégé ;
- finance est permission-first ;
- les sections absentes disparaissent ;
- le drill-down Analytics reste owner ;
- Wide n’ajoute pas des KPIs ;
- Back conserve période et sélection.

---

# 176. Critères de sortie Flutter

Flutter est conforme lorsque :

- `space.pilot` est consommé depuis le store local ;
- snapshot affichable ;
- refresh non destructeur ;
- offline honnête ;
- sections owner-backed ;
- signals-first ;
- chart accessible ;
- adaptive conservation ;
- deep link vers owner ;
- authority revalidée ;
- textScale 1.6 ;
- aucune logique Analytics métier dupliquée dans le client.

---

# 177. Tests ciblés

```text
pilot known signal
pilot no useful signal
pilot insufficient data
pilot known zero
pilot unknown
pilot unavailable
pilot partial failure
pilot offline
pilot stale
pilot direct-space analytics permission
pilot no analytics permission
pilot activity-limited
pilot financials visible
pilot financials hidden
pilot multi-currency
pilot forecast != observed
pilot no global score
pilot no popularity KPI
pilot signal → owner handoff
pilot responsibility filter
pilot compact
pilot medium
pilot wide
pilot textScale 1.6
```

---

# 178. Tests archétypaux

Au moins un scénario par archétype :

```text
generic
creative
media
education
commerce
service_provider
transport_operator
community
```

Le test vérifie :

- vocabulaire ;
- owner ;
- métriques appropriées ;
- absence de métriques artificielles.

---

# 179. Tests de vérité

Tester explicitement :

```text
0
unknown
unavailable
insufficient_data
```

avec quatre fixtures distinctes.

---

# 180. Tests de causalité

Un insight qui n’est qu’une corrélation doit être formulé sans causalité abusive.

---

# 181. Tests de finance

Tester :

- permission ;
- plusieurs devises ;
- refunds ;
- aucune agrégation abusive ;
- absence de profit inventé.

---

# 182. Tests de freshness

Un snapshot vieux ne doit pas produire une phrase affirmant un changement « actuel » sans avertissement.

---

# 183. Points volontairement ouverts

Restent ouverts :

- contrat précis d’un `Signal` serveur spécialisé ou read model ;
- seuils par domaine ;
- période par défaut ;
- composants chart finaux ;
- mécanismes d’anomaly detection ;
- profondeur Growth finale ;
- expansion Analytics au-delà Event/Ticket ;
- agrégations Transport/Services/Education/Commerce ;
- export ;
- partage ;
- politique small-n ;
- forecast avancé ;
- comparaisons cohortes ;
- microcopy finale.

Aucun de ces points ne justifie à lui seul un nouveau domaine persistant `Piloter`.

---

# 184. Références de cadrage

Ce contrat consolide principalement :

- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_UX_Now_Contrat_Consolide.md`
- les contrats `Nous`, `Personnes & relations` et Space Métier
- les contrats Jour J / Live
- `makolo_questions_de_conception.md`
- `Makolo_Cadre_consolide_de_PageRank_aux_trajectoires_accessibles_2026-09-17.docx`
- le runtime courant :
  - `organizations/api/space_pilot_projection.py`
  - `templates/organizations/space/pilot.html`
  - `analytics_app/services.py`
  - `mobile/lib/features/space/space_repository.dart`
  - `authorization/constants.py`

Le code, les migrations, les tests et les owners canoniques restent prioritaires lors de l’implémentation.

---

# 185. Formulation finale

> **Piloter est la surface Makolo qui permet à une personne autorisée de prendre du recul sur le fonctionnement réel d’un Space afin de comprendre ce qui fonctionne, ce qui change et ce qui mérite un ajustement. Elle commence par le sens et les Signaux utiles, puis seulement par les mesures, graphiques et profondeurs analytiques capables de les expliquer. Piloter ne crée ni score global, ni dashboard KPI, ni objectif de popularité ; il distingue strictement zéro, inconnu, indisponible et données insuffisantes, conserve les frontières de Permission et de responsabilité, ne transforme aucune corrélation en causalité et ne remplace jamais les owners Analytics, Capacity, Payment, CRM, Operations ou autres. Les rôles peuvent voir des lectures différentes d’une même surface, les archétypes peuvent prioriser des territoires différents, et chaque action d’ajustement retourne vers le domaine propriétaire qui détient la vérité et l’autorité.**
