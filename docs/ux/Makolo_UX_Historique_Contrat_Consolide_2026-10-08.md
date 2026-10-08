# Makolo — **Historique**
## Contrat UX consolidé — passé significatif, récupération temporelle et continuité de mémoire

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence — Historique transverse  
**Actor Context :** Profile ou Space explicitement actif  
**Viewer :** Profile authentifié  
**Portée :** Web, Flutter, tablette/desktop adaptatif, Presentation, local-first, projections owner-backed  
**Base runtime vérifiée :** `main@52eced16a35d779f98eb8d43bbea405fd7f7b4b0`  
**Nature :** contrat UX et de projection ; ne crée aucun domaine métier `History`  
**Promesse produit :** **Makolo marche pour vous.**  
**Principe d’expérience :** **Pas le plaisir de rester. Le plaisir d’avancer.**

---

# 0. Formule

```text
Historique
=
ce qui s’est réellement passé
+
reste significatif
+
reste légitime à retrouver
+
ouvre la vérité propriétaire
```

et non :

```text
Historique
=
audit log
+
timeline de tous les événements techniques
+
archive de toute la base
```

---

# 1. Questions humaines

Contexte personnel :

> **Qu’est-ce qui s’est déjà passé pour moi ?**

Formulation consolidée :

> **Qu’est-ce qui est terminé et reste utile à retrouver ?**

Contexte Space :

> **Qu’est-ce qui s’est réellement passé dans ce Space et reste utile à retrouver ?**

---

# 2. Historique est transverse

Historique n’est pas un onglet primaire.

Il est une surface secondaire d’inspection et récupération.

La dimension historique existe aussi à l’intérieur des owners :

```text
Prestations
→ En cours / Terminées

Départs
→ À venir / Passés

Programmes
→ Actuels / Passés

Commandes
→ Actives / Terminées
```

---

# 3. Historique global vs histoires locales

Les owners conservent leur histoire locale.

Historique transverse permet de retrouver à travers plusieurs owners.

```text
Historique transverse
≠ remplacement des historiques métier
```

---

# 4. Historique ≠ Moi

Invariant :

```text
Historique
→ passé significatif

Moi
→ capital durable disponible maintenant
```

Exemple :

```text
Voyage Nairobi terminé
→ Historique

Passeport encore valide
→ Moi
```

---

# 5. Historique ≠ En cours

Une Continuité terminée sort d’En cours.

Elle peut devenir historique.

En cours ne doit pas accumuler le passé.

---

# 6. Historique ≠ Maintenant

Une réalité passée peut produire une conséquence actuelle.

Exemple :

```text
paiement échoué hier
mais remboursement à traiter aujourd’hui
```

La conséquence actuelle peut apparaître dans Now.

L’événement passé reste dans l’owner / Historique.

---

# 7. Historique ≠ Piloter

Historique répond :

```text
qu’est-ce qui s’est passé ?
```

Piloter répond :

```text
qu’est-ce que cela nous apprend ?
```

Piloter peut utiliser l’histoire.

Il ne la possède pas.

---

# 8. Historique ≠ Analytics

Analytics agrège.

Historique récupère des réalités significatives.

```text
12 commandes terminées
→ Analytics

Commande 493 terminée
→ Historique / Commerce
```

---

# 9. Historique ≠ Audit log

Un audit log répond à :

```text
qui a changé quoi, quand ?
```

Historique répond à :

```text
quelle expérience / démarche / opération significative s’est terminée ou a eu lieu ?
```

Les deux sont distincts.

---

# 10. Historique ≠ Domain Events

Domain Events sont une mécanique métier/technique.

Ils peuvent contribuer à déterminer l’histoire.

Ils ne deviennent pas une timeline utilisateur brute.

---

# 11. Historique ≠ notifications

Une notification est un mécanisme d’attention.

Elle ne devient pas un souvenir durable simplement parce qu’elle a été envoyée.

---

# 12. Historique ≠ backup

Historique n’est pas une garantie de restauration de données supprimées.

La retention appartient aux owners et aux politiques de données.

---

# 13. Historique ≠ archive de tout

Toute ligne de base ancienne ne mérite pas l’Historique.

Il faut une valeur de récupération humaine.

---

# 14. Éligibilité historique

Une réalité peut apparaître si :

- elle s’est réellement produite ou terminée ;
- elle est pertinente pour l’Actor Context ;
- l’owner permet la projection ;
- elle reste visible selon authority/privacy ;
- elle possède une identité humaine récupérable.

---

# 15. Terminé ≠ historique automatiquement

Un détail technique terminé peut rester invisible.

Exemple :

```text
retry réseau terminé
```

ne mérite pas l’Historique.

---

# 16. Passé ≠ terminé

Une réalité peut être passée mais non résolue.

Exemple :

```text
Occurrence passée
+
litige en cours
```

L’Occurrence peut être historique.

La conséquence continue ailleurs.

---

# 17. Histoire et conséquences durables

Une réalité historique peut produire :

- Proof ;
- Credential ;
- Resource ;
- Access durable ;
- Recognition ;
- données Analytics ;
- nouvelle possibilité.

Ces conséquences restent chez leurs owners.

---

# 18. Une vérité, plusieurs projections

Exemple :

```text
Formation terminée
→ Historique

Certificat obtenu
→ Moi

Tendance de réussite
→ Piloter

Nouvelle formation pertinente
→ Découvrir
```

Même réel.

Questions différentes.

---

# 19. Jour J après la fin

Après fin :

```text
Jour J
→ se ferme naturellement
```

Il ne devient pas archive infinie.

La réalité peut rester inspectable dans l’owner et Historique.

---

# 20. Live après la fin

Live cesse lorsque la réalité n’est plus actuelle.

Le passé observé peut devenir :

- AccessUse ;
- Operations history ;
- Proof ;
- Analytics ;
- History projection.

---

# 21. Historique personnel

Le runtime actuel possède déjà une projection partielle.

Il compose actuellement :

- Journey historiques ;
- Access historiques.

Le contrat cible une projection transverse extensible, sans forcer tous les owners à y apparaître.

---

# 22. Historique Space

Le Space architecture fixe l’histoire comme transverse.

Les owners métier possèdent déjà :

- Terminées ;
- Passés ;
- historique métier.

Une surface Space transverse peut fédérer ces owners si elle apporte une vraie valeur de récupération.

---

# 23. Même concept, Actor Context différent

```text
Profile History
→ ce qui s’est passé pour moi

Space History
→ ce qui s’est passé pour ce collectif
```

Une même implémentation Presentation peut supporter les deux.

Les sources et permissions diffèrent.

---

# 24. Pas de mélange implicite

L’Historique personnel ne doit pas afficher toute l’histoire des Spaces auxquels la personne appartient.

L’Historique Space ne doit pas afficher l’histoire privée personnelle du Viewer.

---

# 25. Responsibility lens

Dans un Space, une responsabilité active peut réduire l’Historique.

Elle ne transfère aucune Permission.

---

# 26. Authority historique

Une perte de Permission peut réduire la visibilité de faits historiques.

Le fait d’avoir vu un élément dans le passé ne donne pas un droit perpétuel.

---

# 27. Retention ≠ Permission

Une donnée peut être conservée juridiquement/techniquement mais non visible à un Viewer.

---

# 28. Suppression

Si l’owner supprime réellement une donnée selon son contrat, l’Historique ne doit pas maintenir une copie métier interdite.

---

# 29. Projection seulement

Invariant :

```text
History Item
= projection UX
```

Pas besoin d’un modèle universel `HistoryItem` si un read model suffit.

---

# 30. Unité UX

L’unité doit représenter la plus petite expérience passée cohérente.

Exemple :

```text
Voyage Lubumbashi → Kolwezi
12 septembre
Terminé
```

Pas nécessairement chaque Payment, Scan et AccessUse séparément.

---

# 31. Éviter le double souvenir

Le runtime personnel possède déjà un principe utile :

> les démarches et accès liés restent consultables sans être répétés comme deux souvenirs distincts.

Le contrat généralise :

```text
plusieurs owner facts liés
→ une mémoire UX cohérente
→ owners toujours accessibles
```

---

# 32. Regroupement ≠ fusion métier

Une ligne historique peut composer :

- Journey ;
- Access ;
- Occurrence ;
- Payment ;
- Proof.

Mais elle ne fusionne pas ces vérités.

---

# 33. History identity

Une projection historique doit pouvoir répondre :

- quoi ;
- quand ;
- avec qui / où si utile ;
- résultat ou état final humain ;
- owner principal ;
- conséquences utiles.

---

# 34. Temps historique

Le temps présenté doit être le temps humain pertinent.

Exemples :

- date de l’Occurrence ;
- date d’accomplissement ;
- date de livraison ;
- date de terminaison.

Pas automatiquement `updated_at`.

---

# 35. `updated_at` n’est pas l’histoire

Invariant :

```text
updated_at
≠ historique_at universel
```

Une modification technique tardive ne doit pas remonter artificiellement un événement ancien en haut de l’Historique.

---

# 36. Temps du réel vs temps de connaissance

Makolo peut apprendre aujourd’hui qu’un événement a eu lieu hier.

Le contrat doit pouvoir distinguer :

```text
happened_at
learned_at
```

conceptuellement.

La Presentation utilise le temps réel pertinent lorsque fiable.

---

# 37. Temps inconnu

Si la date réelle est inconnue :

ne pas inventer.

On peut présenter :

```text
Date non précisée
```

ou utiliser une date de clôture explicitement owner-backed.

---

# 38. Ordre

Par défaut :

```text
plus récent historiquement
→ plus ancien
```

selon le temps significatif.

---

# 39. Groupement temporel

Groupes possibles :

- Aujourd’hui ;
- Cette semaine ;
- Ce mois ;
- année ;
- période.

Ils sont Presentation.

---

# 40. Pas de timeline infinie artificielle

Historique peut être long.

Utiliser :

- pagination ;
- chargement borné ;
- filtres ;
- recherche.

Pas de scroll conçu pour retenir.

---

# 41. Search historique

La Search dans Historique est légitime.

Exemples :

- activité ;
- organisateur ;
- lieu ;
- ville ;
- trajet ;
- référence ;
- relation.

---

# 42. Search globale vs History Search

```text
Search globale
→ peut trouver passé + présent

History Search
→ uniquement passé éligible
```

---

# 43. Filtres personnels

Le runtime actuel offre :

```text
Tout
Participations / accès
Démarches
```

Le contrat cible peut s’élargir seulement si d’autres owners fournissent de vraies projections historiques.

---

# 44. Filtres Space

Possibles selon footprint :

- activités ;
- Occurrences ;
- commandes ;
- prestations ;
- programmes ;
- relations ;
- accès ;
- autres owners.

Pas de filtre vide obligatoire.

---

# 45. Vocabulaire archétypal

L’Historique Space doit parler le métier.

Exemples :

```text
Transport
→ Départs passés

Education
→ Sessions passées

Commerce
→ Commandes terminées

Services
→ Prestations terminées

Community
→ Initiatives terminées / actions passées
```

La surface globale peut garder `Historique` comme titre.

---

# 46. Historique owner-local

Une profondeur Transport peut afficher `Passés`.

Une profondeur Commerce peut afficher `Terminées`.

Cela reste préférable quand la personne connaît déjà le contexte.

---

# 47. Historique transverse — utilité

Il devient utile quand la personne pense :

```text
« Je sais que ça s’est passé, mais je ne sais plus où. »
```

---

# 48. Historique et Mark

Mark peut retrouver :

```text
« Retrouve mon voyage de septembre. »
```

et handoff vers Historique/owner.

---

# 49. Historique et Search

Search transverse peut retourner un item historique.

Elle doit le marquer comme passé.

---

# 50. Historique et Découvrir

L’histoire peut nourrir la pertinence ailleurs.

Historique ne devient pas recommandation.

---

# 51. Historique et Moi

Une expérience historique peut avoir produit une ressource durable.

Le détail peut afficher :

```text
Résultat durable
→ Certificat
[Ouvrir dans Moi]
```

---

# 52. Historique et Piloter

Piloter agrège les faits historiques.

Historique peut ouvrir les cas individuels sous-jacents si autorisé.

---

# 53. Historique et Personnes & relations

Une relation passée peut être inspectable si l’owner l’expose.

Elle ne réactive pas automatiquement la relation.

---

# 54. Historique et Payment

Un paiement historique peut être visible en contexte.

Mais :

```text
Payment
≠ expérience complète
```

La profondeur owner reste Finance/Commerce.

---

# 55. Historique et Access

Access peut être historique après expiration/utilisation.

AccessUse est une observation distincte.

---

# 56. Historique et Proof

Proof peut rester durable dans Moi/Trust.

Historique peut montrer l’événement d’obtention.

---

# 57. Historique et Recognition/Loyalty

Les mouvements peuvent être inspectables si utiles.

Historique ne devient pas wallet.

---

# 58. N1 — personnel

```text
Historique

[Rechercher________________]

Septembre

Voyage Lubumbashi → Kolwezi
12 sept.
Trajet terminé                         ›

Formation Sécurité
4 sept.
Participation terminée                ›
```

---

# 59. N1 — Space

```text
Historique
Mulykap

Octobre

Départ Lubumbashi → Kolwezi
8 oct. · 14:00
Terminé                               ›

Commande 493
7 oct.
Remise terminée                       ›
```

Uniquement si ces owners sont légitimes.

---

# 60. N2

Le détail historique n’est pas un nouvel écran propriétaire.

Il peut soit :

- ouvrir directement l’owner ;
- utiliser un preview historique léger puis owner.

---

# 61. Preview historique

Peut montrer :

- identité ;
- date ;
- résultat ;
- lieu ;
- acteurs si autorisés ;
- conséquences durables ;
- lien owner.

---

# 62. N3

Toujours owner-backed.

---

# 63. État final humain

Préférer :

```text
Trajet terminé
Dossier clôturé
Commande remise
Session terminée
```

à :

```text
FULFILLED
CLOSED
COMPLETED
```

---

# 64. Statut technique

Le statut technique peut être utile en profondeur admin.

Pas N1.

---

# 65. Annulé

Une réalité annulée peut appartenir à l’Historique si cela reste significatif.

---

# 66. Rejeté

Une démarche rejetée peut être historique.

La surface doit éviter une formulation stigmatisante.

---

# 67. Expiré

Un Access ou une demande expirée peut être historique si owner le considère pertinent.

---

# 68. Draft abandonné

Un brouillon jamais engagé ne doit pas rester indéfiniment dans l’Historique.

---

# 69. Deleted draft

Pas d’historique produit automatique d’un draft supprimé.

---

# 70. Résultat partiel

Une Journey peut avoir eu un résultat intermédiaire sans être terminée.

Elle reste En cours si sa continuité existe.

---

# 71. Réouverture

Pas de bouton générique :

```text
Reprendre
```

sur tout l’Historique.

Seul l’owner peut permettre une nouvelle action.

---

# 72. Refaire

Une action :

```text
Refaire
Réserver à nouveau
S’inscrire à nouveau
```

peut exister si l’owner crée une nouvelle réalité.

Elle ne réactive pas silencieusement l’ancienne.

---

# 73. Copier

Historique ne doit pas cloner automatiquement des dossiers/commandes.

---

# 74. Export

Un reçu, certificat ou preuve peut être exporté depuis son owner.

Historique n’est pas le générateur de documents.

---

# 75. Share

Partager une expérience historique exige un contrat public explicite.

Rien n’est public par défaut.

---

# 76. Privacy

Le passé peut être sensible.

Historique respecte :

- privacy actuelle ;
- authority actuelle ;
- retention ;
- minimal disclosure.

---

# 77. Right to forget / retention

Le contrat UX ne remplace pas les règles légales.

Historique n’est pas une excuse pour conserver tout indéfiniment.

---

# 78. Space privacy

Les anciens collaborateurs ne gardent pas automatiquement accès au passé du Space.

---

# 79. Profile privacy

Agir dans un Space ne donne pas au Space l’historique personnel complet du Profile.

---

# 80. Local-first

L’architecture comportementale permet de synchroniser un historique utile.

Le client peut conserver :

- items déjà synchronisés ;
- safe summaries ;
- owner refs ;
- dates ;
- recherche locale.

---

# 81. Offline

Historique est une bonne candidate à la lecture offline.

Mais :

- données sensibles selon politique ;
- owner detail peut nécessiter réseau ;
- visibilité doit être revalidée.

---

# 82. Offline ≠ droit perpétuel

Un cache historique ne contourne pas une révocation de Permission.

---

# 83. Freshness

Une donnée historique est moins sensible au temps réel.

Mais :

- retrait de visibilité ;
- correction ;
- remboursement ;
- révocation ;
- rectification

peuvent changer ce qui est légitime.

---

# 84. Correction historique

Une erreur factuelle corrigée par l’owner doit se refléter.

Historique ne conserve pas une copie obsolète comme vérité officielle.

---

# 85. Append-only UX interdit

Le monde réel n’est pas nécessairement append-only du point de vue Presentation.

Les owners peuvent rectifier.

---

# 86. Partial failure

Une source historique peut échouer.

Exemple :

```text
Démarches ✓
Accès ✓

Commandes
Impossible d’actualiser.
```

Ne pas afficher zéro.

---

# 87. Loading

Préférer :

```text
snapshot connu
+
refresh discret
```

---

# 88. Empty

Personnel :

```text
Aucun élément dans votre historique pour le moment.
```

Space :

```text
Aucun élément historique visible dans votre périmètre.
```

---

# 89. Empty ≠ rien ne s’est jamais passé

Si la projection ne couvre que certains owners :

le message doit éviter de prétendre à l’exhaustivité.

---

# 90. Coverage

Une projection Historique devrait pouvoir décrire sa couverture si partielle.

---

# 91. Search no match

```text
Aucun résultat pour « Nairobi » dans cet historique visible.
```

---

# 92. Compact

Single pane.

Sections temporelles ou liste.

Search et filtres en haut.

---

# 93. Medium

Peut utiliser :

```text
list + preview
```

après sélection.

---

# 94. Wide

```text
NAV | HISTORY | OWNER PREVIEW
```

seulement si sélection.

Pas de timeline décorative permanente.

---

# 95. Very Wide

Pas de calendrier géant par défaut.

Pas de graphes Analytics.

---

# 96. Back

Depuis owner :

retour conserve :

- query ;
- filtre ;
- période ;
- scroll.

---

# 97. Deep links

Un deep link historique doit pointer vers l’owner ou une projection sûre.

Il ne contourne pas les permissions actuelles.

---

# 98. Accessibility

MUST :

- ordre chronologique compréhensible ;
- dates localisées ;
- état final annoncé ;
- filtres accessibles ;
- Search label ;
- textScale 1.6 ;
- focus restauré ;
- pas de couleur seule.

---

# 99. Dates

Utiliser date/heure locale pertinente.

Éviter les timestamps techniques.

---

# 100. Timezone

Le temps présenté doit respecter le contexte temporel défini par l’owner et le client.

Ne pas réordonner naïvement des événements multi-timezones sans contrat.

---

# 101. Médias

Un média historique peut apparaître s’il aide réellement à reconnaître l’expérience.

Pas de galerie souvenir générique.

---

# 102. No Orphan Media

Photo passée :

```text
≠ souvenir automatique
```

Elle doit appartenir à une réalité.

---

# 103. Historical narrative

Le produit peut présenter une courte synthèse.

Il ne doit pas inventer une narration émotionnelle ou un résumé IA non fondé.

---

# 104. Search indexing

Les items historiques peuvent être indexés pour Search.

Index ≠ owner.

---

# 105. Pagination

Le runtime personnel utilise déjà une pagination bornée.

Le contrat conserve l’idée de bornage.

---

# 106. Infinite scroll

Un scroll technique progressif est possible.

Il ne doit pas être conçu comme boucle d’engagement.

---

# 107. Groupement par owner

Filtre :

```text
Démarches
Accès
Commandes
...
```

peut être utile.

Les types doivent rester humains.

---

# 108. Groupement par période

Peut être combiné avec owner filters.

Éviter une matrice complexe.

---

# 109. Recent history preview

Une petite projection récente peut apparaître sur une autre surface si utile.

Mais le passé ne doit pas coloniser Now.

---

# 110. Home/Now preview

Si quelques éléments récents sont montrés dans un hub, ils doivent être secondaires.

---

# 111. Runtime actuel — personnel

`ParticipantHistoryView` existe déjà.

Il compose :

```text
participant_unified_history_accesses
participant_unified_history_journeys
```

avec :

- recherche ;
- filtres ;
- pagination ;
- tri par `history_at`.

---

# 112. Runtime actuel — déduplication

Le template explique déjà que démarches et accès liés doivent rester consultables sans être répétés comme deux souvenirs distincts.

C’est un invariant à conserver.

---

# 113. Runtime actuel — limites

La projection personnelle actuelle couvre surtout :

```text
Access
Journey
```

Elle ne constitue pas encore un historique transversal complet de tous les domaines.

---

# 114. Runtime actuel — temps

Le code utilise :

```text
history_at
```

avec fallback vers `updated_at`.

Le contrat cible une sémantique temporelle owner-backed plus forte lorsque possible.

---

# 115. Runtime actuel — Space

Les sources architecture décrivent l’Histoire Space comme transverse et les owners possèdent leurs propres sections passées/terminées.

Aucune projection Space History consolidée dédiée n’a été démontrée dans l’inspection courante.

---

# 116. Runtime actuel — Flutter

Aucun écran Flutter History autonome n’a été démontré dans les chemins inspectés.

Le kernel local-first prévoit néanmoins la conservation d’un historique utile déjà synchronisé.

---

# 117. Gap principal

Le principal gap est :

```text
History personnel partiel
+
histoires owner locales
→ projection transverse mature Profile / Space
```

sans créer un owner `History`.

---

# 118. Gap temporel

Il faut améliorer progressivement :

```text
updated_at fallback
→ happened_at / completed_at owner-backed
```

lorsque les domaines savent exprimer le temps humain pertinent.

---

# 119. Gap de couverture

L’UX doit dire honnêtement quand l’Historique ne couvre que certains domaines.

---

# 120. Golden candidates

## G-HIST-01 — Personal / Compact

Journey + Access composés.

Pas de double souvenir.

---

# 121. G-HIST-02 — Personal / Empty

Identité calme.

Pas de marketing.

---

# 122. G-HIST-03 — Search

Query + filtres.

Retour conserve query.

---

# 123. G-HIST-04 — Durable consequence

Expérience terminée + Credential ouvert dans Moi.

---

# 124. G-HIST-05 — Space / Compact

Plusieurs owners, types humains.

---

# 125. G-HIST-06 — Space / Activity-limited

Pas de passé Space-wide.

---

# 126. G-HIST-07 — Owner-local

Transport `Passés` reste accessible sans imposer Historique global.

---

# 127. G-HIST-08 — Offline

Snapshot lisible.

Permission revalidée dès que possible.

---

# 128. G-HIST-09 — Correction

Ancienne projection corrigée par owner.

Pas de double entrée.

---

# 129. G-HIST-10 — Unknown date

Pas de date inventée.

---

# 130. G-HIST-11 — Wide preview

History list + owner preview.

---

# 131. G-HIST-12 — textScale 1.6

Dates, titres, states lisibles.

---

# 132. États critiques

```text
content
empty
search
no_match
loading
offline
stale
partial
permission_loss
coverage_partial
```

---

# 133. Recognition test

En 500 ms :

```text
je regarde le passé
+
dans quel Actor Context
+
chaque item est une réalité significative
```

---

# 134. Blur test

Pas de dashboard.

Pas de média dominant.

Timeline lisible.

---

# 135. Deletion test

Chaque item doit avoir une valeur réelle de récupération.

Sinon l’owner local suffit.

---

# 136. Anti-features

Historique ne doit jamais devenir :

- feed nostalgique ;
- audit log ;
- changelog technique ;
- notification center ;
- backup browser ;
- Analytics ;
- Piloter ;
- En cours ;
- Moi ;
- wallet ;
- timeline de chaque mutation ;
- archive infinie de drafts ;
- source de vérité ;
- owner métier ;
- média gallery ;
- page de gamification ;
- système de streaks.

---

# 137. Invariants gelés

1. Historique n’est pas un onglet primaire.
2. Historique est transverse.
3. Historique ≠ owner.
4. Historique ≠ audit log.
5. Historique ≠ Domain Events.
6. Historique ≠ Notifications.
7. Historique ≠ Analytics.
8. Historique ≠ Piloter.
9. Historique ≠ Moi.
10. Historique ≠ En cours.
11. Historique ≠ Now.
12. Historique ≠ backup.
13. Passé ≠ historique automatiquement.
14. Terminé ≠ historique automatiquement.
15. Une réalité peut être historique et avoir une conséquence active.
16. Capital durable va dans Moi/owner.
17. Jour J se ferme après fin.
18. Live ne devient pas archive.
19. Owner-local history reste légitime.
20. Global History fédère sans remplacer.
21. Plusieurs facts liés peuvent composer une mémoire UX.
22. Composition ≠ fusion métier.
23. `updated_at` ≠ temps historique universel.
24. Temps réel ≠ temps de connaissance.
25. Date inconnue reste inconnue.
26. Actor Context reste explicite.
27. Profile History ≠ Space History.
28. Responsibility ≠ authority.
29. Ancien accès ≠ droit perpétuel.
30. Cache ≠ Permission.
31. Correction owner modifie la projection.
32. Search historique reste bornée au passé visible.
33. Pas de réactivation générique.
34. Pas de copie générique.
35. Divulgation minimale.
36. Responsive adapte la géométrie.
37. Back conserve contexte.
38. Offline conserve ce qui est déjà acquis, pas toute la vérité.
39. Coverage partielle doit être honnête.
40. Historique doit servir la récupération, pas la rétention.

---

# 138. Critères de sortie serveur

- federation owner-backed ;
- temps historique sémantique ;
- authority-first ;
- retention respectée ;
- corrections ;
- dedupe Presentation ;
- coverage ;
- pagination ;
- search ;
- no IDOR ;
- no copy of owner truth.

---

# 139. Critères de sortie Web

- Historique secondaire ;
- Search intégrée ;
- filtres humains ;
- owner handoffs ;
- pas de timeline technique ;
- pas de double souvenir ;
- back state ;
- Profile/Space boundary.

---

# 140. Critères de sortie Flutter

- historique synchronisé utile ;
- offline read ;
- local search ;
- authority refresh ;
- owner deep link ;
- pagination/bounded loading ;
- back restoration ;
- textScale.

---

# 141. Tests ciblés

```text
personal history journey
personal history access
journey+access dedupe
space history
activity-limited
owner-local history
search history
no match
unknown date
history time vs updated_at
durable consequence → Moi
current consequence → Now
pilot aggregation
offline
permission revoked
correction
retention removal
partial owner failure
coverage partial
compact
medium
wide
textScale 1.6
```

---

# 142. Points ouverts

- endpoint transverse Space ;
- extension personal au-delà Journey/Access ;
- semantic history time par owner ;
- stratégie dedupe multi-owner ;
- retention UX détaillée ;
- export ;
- public sharing ;
- grouping temporel final ;
- coverage metadata ;
- Flutter screen exact.

Aucun de ces points n’exige un modèle métier History universel.

---

# 143. Formulation finale

> **Historique est la projection temporelle transverse de Makolo qui permet de retrouver ce qui s’est réellement passé et reste humainement utile à inspecter, sans transformer le passé en une nouvelle source de vérité. Il est distinct de Moi, En cours, Maintenant, Piloter, Analytics, notifications, audit logs et Domain Events : les owners continuent de posséder les réalités et leurs histoires métier locales, tandis qu’Historique compose une mémoire UX cohérente et permission-safe. Une expérience terminée peut y apparaître tandis que ses conséquences durables restent dans Moi ou leurs owners et que ses effets actuels remontent dans Maintenant. Le temps affiché doit refléter autant que possible le moment réel de l’expérience plutôt qu’un simple `updated_at`, les faits liés doivent éviter le double souvenir, l’offline peut conserver un passé déjà synchronisé sans créer de droit perpétuel, et l’Historique doit servir la récupération — jamais la rétention ou l’engagement.**
