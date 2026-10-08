# Makolo — **Recherche transverse**
## Contrat UX consolidé — retrouver une réalité connue sans connaître sa taxonomie

**Date :** 2026-10-08  
**Statut :** contrat UX consolidé de référence — Recherche transverse  
**Actor Context :** Profile ou Space explicitement actif  
**Viewer :** Profile authentifié  
**Portée :** Web, Flutter, tablette/desktop adaptatif, Presentation, recherche locale et distante, handoffs owner-backed  
**Base runtime vérifiée :** `main@52eced16a35d779f98eb8d43bbea405fd7f7b4b0`  
**Nature :** contrat UX et de projection ; ne crée aucun domaine métier `Search`  
**Promesse produit :** **Makolo marche pour vous.**  
**Principe d’expérience :** **Pas le plaisir de rester. Le plaisir d’avancer.**

---

# 0. Formule

```text
Recherche transverse
=
retrouver
+
identifier
+
désambiguïser
+
ouvrir la réalité propriétaire
```

et non :

```text
Recherche
=
Discover
+
Web Search
+
base de données globale
+
nouveau domaine
```

---

# 1. Question humaine

La Recherche transverse répond à :

> **Où est la réalité que je cherche dans ce contexte Makolo ?**

Dans un Space :

> **Rechercher dans cet Espace**

Dans le contexte personnel :

> **Rechercher dans ce qui m’est déjà accessible dans Makolo**

La recherche ne demande pas à la personne de connaître le modèle propriétaire.

---

# 2. Position dans l’expérience

La Recherche transverse n’est pas un onglet principal.

Elle peut être accessible depuis :

- header ;
- raccourci clavier ;
- champ de recherche contextuel ;
- Mark ;
- une profondeur ;
- une surface secondaire ;
- une recherche spécialisée.

Elle reste une capacité transversale.

---

# 3. Recherche ≠ Découvrir

Invariant central :

```text
RECHERCHE TRANSVERSE
→ retrouver une réalité connue / déjà présente / accessible

DÉCOUVRIR
→ explorer un champ de nouvelles possibilités
```

Exemples :

```text
« Retrouver ma candidature »
→ Recherche / Mark

« Trouver une bourse »
→ Découvrir

« Retrouver la commande 493 »
→ Recherche

« Trouver un fournisseur »
→ Découvrir ou recherche métier externe selon owner
```

---

# 4. Recherche ≠ Mark

Le Mark reçoit une intention complète.

La Recherche reçoit principalement une requête de récupération.

```text
Mark
→ comprend et orchestre

Recherche
→ retrouve et ouvre
```

Le Mark peut invoquer la Recherche.

La Recherche ne devient pas un assistant conversationnel.

---

# 5. Recherche ≠ Web Search

Invariant :

```text
Recherche Makolo
≠ moteur Web externe
```

La Recherche transverse parcourt les réalités Makolo que les owners rendent recherchables pour l’Actor Context courant.

Si l’utilisateur demande une réalité externe non connue :

```text
→ Découvrir / Web Research / Mayele
```

selon le contrat approprié.

---

# 6. Recherche ≠ moteur de vérité

Trouver un résultat ne le rend pas plus vrai.

La Search :

- indexe ou interroge ;
- présente ;
- handoff.

Elle ne vérifie pas une assertion.

---

# 7. Recherche ≠ domaine propriétaire

Pas de table universelle obligatoire :

```text
SearchItem
SearchEntity
SearchObject
UniversalObject
```

La cible doit d’abord être un read model ou une fédération de selectors owner-backed.

---

# 8. Même Search, contextes différents

Il existe une seule grammaire Recherche Makolo.

Elle respecte l’Actor Context.

```text
Profile
→ recherche personnelle

Space
→ recherche limitée au Space
```

Le visuel peut rester cohérent.

Les sources interrogées et les permissions changent.

---

# 9. Actor Context explicite

Une requête lancée dans :

```text
Moi
```

ne doit pas chercher silencieusement dans :

```text
Mulykap
```

et inversement.

Une recherche multi-contextes future devrait être explicite.

Elle n’est pas imposée par ce contrat.

---

# 10. Recherche Space

Le contrat source fixe :

> **Rechercher dans cet Espace**

Elle est :

- limitée au Space ;
- permission-first ;
- éventuellement réduite par la responsabilité active.

---

# 11. Recherche personnelle

La Search personnelle peut retrouver les réalités auxquelles le Profile possède une relation légitime :

- Continuités ;
- Access ;
- ressources ;
- Proof/Credentials ;
- collectifs ;
- History ;
- éléments gardés ;
- autres owners réellement exposés.

La liste exacte dépend du runtime.

---

# 12. Permission-first

La recherche ne doit jamais fonctionner ainsi :

```text
chercher tout
→ filtrer les résultats interdits après
```

La source doit être permission-safe en amont.

---

# 13. Pas de fuite d’existence

Si un objet n’est pas visible :

la Search ne doit pas révéler :

- son titre ;
- qu’il existe ;
- son nombre ;
- son owner ;
- sa date ;
- sa présence dans le Space.

---

# 14. Responsibility lens

Dans un Space, la responsabilité sélectionnée peut réduire la Search.

Mais :

```text
responsibility
≠ Permission
```

Une recherche plus large ne peut pas contourner l’authority.

---

# 15. Recherche globale vs spécialisée

La recherche globale ne remplace pas les recherches métier.

Exemples :

```text
Recherche Space
→ retrouver un départ, une personne, un programme, une commande

Transport / recherche spécialisée
→ retrouver précisément un départ

Personnes & relations
→ rechercher une relation

Historique
→ rechercher dans le passé
```

---

# 16. Pourquoi les recherches spécialisées restent nécessaires

Une recherche spécialisée connaît mieux :

- vocabulaire ;
- filtres ;
- champs ;
- actions ;
- profondeur ;
- contexte métier.

La globale privilégie la récupération rapide.

---

# 17. Résultats humains

Préférer :

```text
Transport
Personnes
Commandes
Lieux
Programmes
```

à :

```text
Activity
CRMContact
CommerceOrder
Place
Journey
```

---

# 18. Groupes de résultats

Les groupes sont Presentation.

Ils peuvent être construits selon le contexte et les owners.

Ils ne deviennent pas une taxonomie métier universelle.

---

# 19. Libellés par archétype

Le Space peut adapter les groupes :

```text
transport_operator
→ Départs, Routes, Véhicules, Relations, Lieux

education
→ Programmes, Sessions, Personnes, Groupes, Lieux

commerce
→ Offres, Commandes, Clients, Lieux

service_provider
→ Prestations, Dossiers, Clients, Partenaires

community
→ Initiatives, Communauté, Partenaires, Lieux

creative
→ Créations, Événements, Publics, Partenaires

media
→ Productions, Événements, Publics, Partenaires

generic
→ Activités, Personnes & relations, Lieux
```

Uniquement si ces owners existent réellement.

---

# 20. Result identity

Chaque résultat doit identifier :

```text
ce que c’est humainement
+
son contexte
+
sa relation
+
sa destination
```

Exemple :

```text
Départ Lubumbashi → Kolwezi
Demain · 14:00
Transport
```

---

# 21. Personne et relation

La même personne peut apparaître plusieurs fois lorsque la relation elle-même est distincte :

```text
Marie Kalala
Collaboratrice · Exploitation

Marie Kalala
Contact CRM · Client
```

Ce n’est pas une duplication si l’objet recherché est la relation.

---

# 22. Identité de Profile ≠ identité de relation

Invariant :

```text
Profile
≠ CRMContact
≠ TeamMembership
≠ GroupMembership
≠ Partner relation
```

La Search doit garder cette distinction.

---

# 23. Fusion de résultats

Deux résultats pointant exactement vers la même réalité propriétaire peuvent être fusionnés en Presentation.

Mais deux relations différentes vers la même personne ne doivent pas être fusionnées si cela détruit le sens.

---

# 24. Query

La requête peut chercher dans :

- titre ;
- nom ;
- référence humaine ;
- lieu ;
- date ;
- identifiant public approprié ;
- relation ;
- autres champs owner-backed.

Pas de promesse de recherche sur tous les champs de base.

---

# 25. IDs techniques

Un UUID ou PK ne doit pas être l’expérience normale.

Un identifiant métier humain peut être recherché si owner-backed :

```text
Commande 493
Départ MK-214
```

si ces références existent réellement.

---

# 26. Recherche textuelle

Une recherche simple doit être tolérante aux variations usuelles lorsque le moteur le permet.

Le contrat ne fixe pas d’algorithme fuzzy.

---

# 27. Recherche sémantique

Une recherche sémantique peut être ajoutée si :

- explicable ;
- permission-safe ;
- owner-safe ;
- résultats défendables.

Elle ne doit pas relâcher silencieusement le scope.

---

# 28. Ranking

Pas de ranking par popularité.

Ordre possible :

```text
correspondance exacte
+
contexte courant
+
relation explicite
+
fraîcheur appropriée
+
pertinence propriétaire
```

Le contrat ne fixe pas un score global.

---

# 29. Exact match

Un match exact peut être privilégié.

Mais il ne doit pas masquer des homonymes importants.

---

# 30. Ambiguïté

Exemple :

```text
« Visa »
```

peut correspondre à :

- prestation ;
- dossier ;
- ressource ;
- organisation.

La Search doit grouper ou demander une clarification visuelle simple.

---

# 31. Filtres

Filtres transversaux possibles :

- type humain ;
- période ;
- lieu ;
- responsabilité ;
- état général si défendable.

Les filtres ne doivent pas devenir la taxonomie backend.

---

# 32. Filtre ≠ authority

Changer un filtre ne modifie jamais les Permissions.

---

# 33. Search-as-you-type

Possible si :

- requêtes raisonnables ;
- debouncing ;
- privacy ;
- performance.

Le contrat ne l’impose pas.

---

# 34. Submit explicite

Sur réseau coûteux ou recherche lourde, un submit explicite peut être préférable.

---

# 35. Initial state

La surface Search peut s’ouvrir avec :

```text
Rechercher dans cet Espace
[________________________]
```

et éventuellement quelques repères récents.

Elle ne doit pas afficher un feed de suggestions pour occuper l’espace.

---

# 36. Recent searches

Des recherches récentes peuvent être locales et privées.

Elles ne doivent pas être synchronisées ou exposées sans contrat.

---

# 37. Suggestions

Les suggestions doivent aider la récupération.

Pas de recommandations marketing.

---

# 38. Empty query

Une query vide n’a pas à retourner « tout le Space ».

Cela évite :

- fuite ;
- surcharge ;
- faux annuaire universel.

---

# 39. No results

Message :

```text
Aucun résultat visible pour « X » dans ce contexte.
```

Ne pas dire :

```text
X n’existe pas.
```

---

# 40. Hidden vs no result

Le produit ne doit pas distinguer publiquement :

```text
existe mais interdit
```

de :

```text
n’existe pas
```

si cela fuit une information.

---

# 41. Unknown

Une Search peut ne pas savoir.

Elle ne doit pas inventer une correspondance.

---

# 42. Search et Discover handoff

Si aucun résultat connu ne répond et que l’intention semble exploratoire :

```text
Explorer dans Découvrir
```

peut être proposé.

Pas automatiquement exécuté.

---

# 43. Search et Mark handoff

Si la requête ressemble à une action :

```text
« annule ma commande »
```

la Search peut proposer :

```text
Ouvrir dans Makolo Mark
```

ou ouvrir la commande puis owner action.

Elle ne doit pas muter depuis la Search seule.

---

# 44. Search et Historique

La Search globale peut retrouver une réalité passée.

Mais l’Historique reste la meilleure surface pour explorer le passé.

Un résultat historique doit être clairement identifié :

```text
Terminé
Passé
Historique
```

selon owner.

---

# 45. Search et Maintenant

Une réalité peut être trouvée même si elle n’est pas importante maintenant.

Search ne reprend pas la logique de Now.

---

# 46. Search et Moi

Une Resource trouvée via Search peut ouvrir Moi/owner.

Search ne la possède pas.

---

# 47. Search et Nous

Une relation ou Team member peut ouvrir Personnes & relations / Nous.

---

# 48. Search et Métier

Une réalité métier ouvre la profondeur Métier appropriée.

---

# 49. Search et Piloter

Un terme analytique peut ouvrir Piloter ou Analytics seulement si la cible est réellement une lecture de pilotage.

---

# 50. Search et Jour J

Une Occurrence trouvée peut ouvrir Jour J si admissible.

Search ne dérive pas l’admissibilité.

---

# 51. N1 — Compact

```text
← Recherche

Rechercher dans cet Espace

[ Marie________________ ]

Personnes
Marie Kalala
Collaboratrice · Exploitation

Clients
Marie Kalala
Contact CRM · Client
```

---

# 52. N1 — catégories

Les catégories doivent être peu nombreuses et utiles.

Pas de 20 groupes vides.

---

# 53. N2

La Search n’a pas besoin de sa propre N2 métier.

Un résultat ouvre l’owner.

Un preview léger peut exister sur Medium/Wide.

---

# 54. Wide

Wide peut utiliser :

```text
RESULTS | PREVIEW
```

après sélection.

Le preview ne devient pas un duplicata complet de l’owner.

---

# 55. Very Wide

Pas de trois colonnes :

```text
filters | results | analytics
```

par défaut.

---

# 56. Keyboard

Desktop peut offrir :

- focus Search ;
- navigation résultats ;
- Enter pour ouvrir ;
- Esc pour fermer.

Le raccourci exact reste ouvert.

---

# 57. Back

Le retour depuis un résultat doit restaurer :

- query ;
- filtres ;
- scroll ;
- sélection ;
- Actor Context.

---

# 58. Deep links

Une URL Search peut conserver une query si privacy acceptable.

Ne jamais exposer des termes sensibles dans un lien partagé sans prudence.

---

# 59. Local-first

Le client peut rechercher localement :

- données déjà synchronisées ;
- ressources locales ;
- historique synchronisé ;
- projections owner connues.

---

# 60. Local search ≠ global search

Invariant :

```text
résultat local
≠ exhaustivité globale
```

Le client doit pouvoir indiquer :

```text
Résultats disponibles sur cet appareil
```

si hors ligne.

---

# 61. Offline

Hors ligne :

- recherche locale possible ;
- pas de promesse d’exhaustivité ;
- handoff local si owner disponible ;
- actions sensibles revalidées plus tard.

---

# 62. Search remote

Une Search distante peut compléter les résultats locaux.

Le merge doit préserver l’identité owner.

---

# 63. Stale

Une réalité trouvée dans le cache peut être obsolète.

Le détail owner décide de la fraîcheur.

Search ne transforme pas le cache en vérité actuelle.

---

# 64. Index local

Un index local est un mécanisme technique.

Il ne devient pas owner.

---

# 65. Privacy locale

L’index local doit respecter :

- compte courant ;
- Profile courant ;
- Actor Context ;
- données sensibles ;
- logout ;
- suppression sécurisée.

---

# 66. Multi-account

Aucune recherche ou suggestion d’un compte A ne doit apparaître dans le compte B.

---

# 67. Performance

Une Search lente ne doit pas bloquer le shell.

Elle peut afficher les résultats locaux puis compléter.

---

# 68. Partial failure

Une source peut échouer :

```text
Activités ✓
Personnes ✓

Commandes
Impossible d’actualiser.
```

Sans faire croire qu’il n’existe aucune commande.

---

# 69. Timeouts

Un timeout d’une source ne vaut pas zéro résultat.

---

# 70. Accessibility

MUST :

- Search field nommé ;
- groupes avec headings ;
- résultats accessibles au clavier ;
- type/relation prononcés ;
- aucune couleur seule ;
- textScale 1.6 ;
- focus restauré ;
- résultats dynamiques annoncés sans spam.

---

# 71. Highlight

Le highlight de termes correspondants est secondaire.

Il ne doit pas réduire la lisibilité.

---

# 72. Media

Le média est rarement nécessaire dans Search.

Un avatar ou thumbnail peut aider à reconnaître.

Pas de grille média.

---

# 73. No Orphan Media

Tout média de résultat doit aider à reconnaître la cible.

---

# 74. Search analytics

Les requêtes peuvent éventuellement alimenter de la télémétrie produit selon privacy.

Elles ne deviennent pas Interests ou intentions métier automatiquement.

---

# 75. Search query ≠ Interest

Invariant :

```text
chercher X
≠ Interest(X)
```

---

# 76. Search query ≠ Watch

Invariant :

```text
chercher X
≠ Veille(X)
```

---

# 77. Search query ≠ intent durable

Une requête est éphémère sauf choix explicite.

---

# 78. Search query ≠ permission request

Chercher un objet interdit ne déclenche pas automatiquement une demande d’accès.

---

# 79. No global Search object

Ne pas créer une copie universelle de toutes les réalités uniquement pour les rendre cherchables si une architecture d’index/read model suffit.

---

# 80. Search indexing

L’index doit conserver :

- owner reference ;
- display type ;
- scope ;
- visibility ;
- safe searchable text ;
- destination.

Pas les secrets owner.

---

# 81. Search result contract candidat

Conceptuellement :

```text
SEARCH RESULT
- projection identity
- owner kind
- owner ref
- human type
- title
- context
- relation label
- timing?
- place?
- destination
- freshness?
```

Ce n’est pas un modèle imposé.

---

# 82. Dédoublonnage

Dédoublonner uniquement lorsqu’on sait que deux lignes représentent la même cible et la même relation.

---

# 83. Sources multiples

Un même owner peut être indexé depuis plusieurs sources techniques.

L’utilisateur ne doit pas voir des doublons techniques.

---

# 84. Provenance

La provenance technique n’est généralement pas visible.

La relation humaine, elle, peut l’être.

---

# 85. Specialized Search example — Transport

```text
Recherche globale
→ « Lubumbashi Kolwezi »

Résultats
Départ 14:00
Route Lubumbashi → Kolwezi
```

La recherche Transport peut offrir des filtres supplémentaires.

---

# 86. Specialized Search example — Services

```text
« Visa »

Prestations
Visa étudiant

Dossiers
Visa · Aline M.
```

---

# 87. Specialized Search example — Education

```text
« Comptabilité »

Programmes
Comptabilité générale

Sessions
Session octobre

Personnes
...
```

---

# 88. Search and relation ambiguity

Une personne peut exister comme :

- Team member ;
- CRMContact ;
- GroupMember ;
- Partner.

La Search doit montrer la relation.

---

# 89. Space boundary

Une Search Space ne doit pas retourner les ressources personnelles privées du Viewer sauf si elles sont explicitement partagées dans ce Space.

---

# 90. Profile boundary

La Search personnelle ne retourne pas les données privées d’un Space simplement parce que la personne y travaille.

---

# 91. Public Search

Une éventuelle Search publique n’est pas couverte par ce contrat interne.

---

# 92. Security

Tests minimum :

- IDOR ;
- enumeration ;
- count leaks ;
- hidden labels ;
- stale permissions ;
- local cache cross-account ;
- deep-link bypass.

---

# 93. Search history

Les requêtes récentes ne doivent pas être confondues avec Historique Makolo.

```text
search history
≠ product History
```

---

# 94. Golden candidates

## G-SEARCH-01 — Profile / Compact

Query personnelle.

Résultats hétérogènes mais humains.

---

# 95. G-SEARCH-02 — Space / Compact

```text
Rechercher dans Mulykap
```

Résultats Space only.

---

# 96. G-SEARCH-03 — Same person, two relations

Deux lignes légitimes.

Relation explicite.

---

# 97. G-SEARCH-04 — No result

Pas d’existence leak.

Handoff Discover facultatif.

---

# 98. G-SEARCH-05 — Permission limited

Activity-limited viewer.

Aucun résultat hors scope.

---

# 99. G-SEARCH-06 — Offline

Résultats locaux clairement non exhaustifs.

---

# 100. G-SEARCH-07 — Partial source error

Autres groupes utilisables.

---

# 101. G-SEARCH-08 — Specialized handoff

Résultat vers recherche Transport/Service/People.

---

# 102. G-SEARCH-09 — Wide preview

```text
RESULTS | PREVIEW
```

Pas de troisième panneau.

---

# 103. G-SEARCH-10 — Historical result

Résultat passé correctement identifié.

---

# 104. G-SEARCH-11 — Mark handoff

Query actionnelle.

Pas de mutation silencieuse.

---

# 105. G-SEARCH-12 — textScale 1.6

Groups, relation labels et titres restent lisibles.

---

# 106. États critiques

```text
initial
typing
loading
results
mixed_results
no_results
partial
offline
stale
permission_limited
error
```

---

# 107. Viewports

```text
360 × 800
430 × 932
834 × 1112
1440 × 900
1728 × 1117
```

---

# 108. Recognition test

En 500 ms :

```text
je cherche
+
dans quel Actor Context
+
voici les types humains
```

---

# 109. Anti-features

Recherche ne doit jamais devenir :

- Discover bis ;
- moteur Web universel ;
- knowledge base ;
- feed de suggestions ;
- command palette admin ;
- mega-create ;
- chatbot ;
- owner de vérité ;
- système de permission ;
- liste de modèles ;
- index public de données privées ;
- moteur de popularité ;
- source d’Interest automatique ;
- source de Watch automatique ;
- historique produit.

---

# 110. Invariants gelés

1. Search n’est pas un onglet principal.
2. Search = récupération, pas exploration.
3. Search ≠ Discover.
4. Search ≠ Mark.
5. Search ≠ Web Search.
6. Search ≠ domaine métier.
7. Actor Context explicite.
8. Profile Search ≠ Space Search.
9. Search Space limitée au Space.
10. Permission-first.
11. Responsibility peut réduire, jamais élargir.
12. Pas de fuite d’existence.
13. Résultats humains.
14. Modèles backend masqués.
15. Recherche globale ≠ recherches spécialisées.
16. La même personne peut avoir plusieurs relations.
17. Profile ≠ relation.
18. Popularité ≠ ranking.
19. Query ≠ Interest.
20. Query ≠ Watch.
21. Query ≠ engagement.
22. Query ≠ permission request.
23. Local ≠ exhaustif.
24. Cache ≠ vérité actuelle.
25. Search ouvre l’owner.
26. Search ne mute pas silencieusement.
27. Search History ≠ Historique Makolo.
28. Responsive adapte la géométrie.
29. Back conserve query.
30. Le client ne recrée pas les truths owner.

---

# 111. Runtime actuel — constat

Sur `main@52eced16a35d779f98eb8d43bbea405fd7f7b4b0` :

- les recherches spécialisées existent dans plusieurs surfaces ;
- l’Historique personnel possède déjà une recherche locale ;
- la Search Space transverse est définie dans l’architecture ;
- aucune projection dédiée `space_search_projection.py` n’a été démontrée dans le runtime inspecté ;
- aucun domaine `Search` n’est nécessaire.

---

# 112. Gap principal

Il manque surtout une fédération permission-safe et Presentation-ready permettant :

```text
Space
→ plusieurs owners
→ résultats humains
→ owner links
```

sans reproduire toutes les données.

---

# 113. Critères de sortie serveur

- federation owner-safe ;
- authority-first ;
- pas d’IDOR ;
- typed human results ;
- destination owner ;
- no hidden existence leak ;
- pagination ;
- query bounded ;
- no cross-context leak.

---

# 114. Critères de sortie Web

- Search accessible sans onglet permanent ;
- query/context visibles ;
- groups humains ;
- filters sobres ;
- back conserve état ;
- owner handoff ;
- no Discover drift.

---

# 115. Critères de sortie Flutter

- Search local-first ;
- offline local search ;
- remote enrichment ;
- context stable ;
- safe cache ;
- keyboard/native focus ;
- deep links ;
- textScale.

---

# 116. Tests ciblés

```text
profile search
space search
actor context boundary
activity-limited search
multiple owners
same profile multiple relations
owner dedupe
historical result
no result
permission-hidden item
partial owner failure
offline local-only
stale cache
deep link
back preservation
textScale 1.6
```

---

# 117. Points ouverts

- endpoint fédéré exact ;
- index technique ;
- semantic search ;
- ranking exact ;
- multi-context Search éventuelle ;
- recent queries ;
- keyboard shortcut ;
- public Search ;
- search analytics privacy.

Aucun n’exige un domaine métier Search.

---

# 118. Formulation finale

> **Recherche transverse est la capacité Makolo qui permet de retrouver rapidement une réalité déjà connue ou accessible dans l’Actor Context courant sans exiger que la personne connaisse son modèle backend ou sa porte propriétaire. Elle n’est ni Découvrir, ni Makolo Mark, ni Web Search : elle fédère de façon permission-first des résultats humains, contextualisés et owner-backed, puis ouvre la profondeur naturelle. Dans un Space, elle reste strictement limitée au Space et peut être réduite par la responsabilité active sans jamais élargir l’autorité ; dans le contexte personnel, elle ne fuit jamais les données privées des Spaces. Les recherches métier spécialisées restent nécessaires, l’offline peut retrouver ce qui est déjà synchronisé sans prétendre à l’exhaustivité, et aucune requête n’est transformée automatiquement en Interest, Watch, engagement ou nouvelle vérité.**
