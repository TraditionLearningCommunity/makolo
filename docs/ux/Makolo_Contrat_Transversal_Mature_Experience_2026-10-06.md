# Makolo — Contrat transversal Mature
# Collections, continuation, états, synchronisation et continuité d’expérience

**Statut :** contrat transversal conceptuel gelé  
**Date :** 2026-10-06  
**Portée :** serveur Django/API, Web, Flutter, local-first, Presentation  
**Dépôt officiel :** `TraditionLearningCommunity/makolo`  
**Principe produit :** « Makolo marche pour vous. »  
**Principe d’expérience :** « Pas le plaisir de rester. Le plaisir d’avancer. »

---

# 0. Objet

Ce document fixe les contrats transversaux d’expérience qui doivent être cohérents dans toutes les surfaces Makolo.

Il s’applique notamment à :

```text
Maintenant
Découvrir
En cours
Moi
Space Maintenant
Space Découvrir
Métier
Nous
Jour J
Live
Historique
Recherche
Profondeurs owner-backed
```

Il ne définit pas les vérités métier propres à ces surfaces.

Il fixe la manière dont les vérités déjà établies sont :

```text
chargées
continuées
actualisées
fusionnées
retirées
mises en cache
synchronisées
présentées
restaurées
protégées
```

Les contrats principaux sont :

```text
Collection & Continuation
Terminal Semantics
Identity & Reconciliation
Ordering Stability
Loading & Refresh
Back / Resume
Search / Filter / Sort
Freshness & Knowledge State
Local-first / Offline
Mutation Lifecycle
Outbox / Retry / Idempotence
Authority Revalidation
Realtime Change Delivery
Deep Links
Media Loading
Adaptive Conservation
Accessibility
Privacy & Minimal Disclosure
```

---

# 1. Principe maître

Le contrat transversal repose sur :

```text
LE SERVEUR POSSÈDE LA VÉRITÉ ET BORNE LES DONNÉES.

LE CLIENT POSSÈDE LA CONTINUITÉ DE L’EXPÉRIENCE.

PRESENTATION TRADUIT LES ÉTATS TECHNIQUES EN SENS HUMAIN.
```

Le client ne doit jamais reconstruire une vérité métier que le serveur ou un owner canonique n’a pas établie.

---

# 2. Pagination serveur ≠ pagination UX

Makolo distingue :

```text
PAGINATION SERVEUR
→ mécanisme technique de lecture bornée

CONTINUATION CLIENT
→ expérience fluide et continue
```

Le serveur peut paginer avec :

```text
Django Paginator
cursor
keyset
offset
read-model borné
autre stratégie owner-specific
```

Le client ne doit pas dépendre du mécanisme exact.

---

# 3. Taille des lots

Le serveur peut renvoyer :

```text
5
6
10
15
20
25
50
...
```

éléments selon :

```text
surface
densité
owner
performance
coût de sérialisation
fraîcheur
contexte
```

Aucun `PAGE_SIZE` global n’est un invariant produit.

---

# 4. Pagination UX interdite sur les surfaces principales

Éviter :

```text
Page 1
1 2 3 4 5
Suivant >
```

pour les surfaces principales.

Cette présentation peut rester légitime exceptionnellement dans des interfaces administratives très spécifiques si le contexte l’exige, mais elle n’est pas la grammaire Mature de Makolo.

---

# 5. Contrat `COLLECTION_SLICE`

Structure conceptuelle :

```text
COLLECTION_SLICE
│
├── ITEMS[]                  0..n
├── COVERAGE_STATE           1
└── CONTINUATION             1
    ├── STATE                1
    └── TOKEN?               0..1
```

---

# 6. `CONTINUATION.STATE`

États conceptuels :

```text
MORE
END
UNKNOWN
```

Les noms wire finaux restent ouverts.

---

# 7. `MORE`

Signifie :

> une suite légitime existe dans le contexte courant.

Le client peut alors demander automatiquement la continuation.

---

# 8. `END`

Signifie :

> aucune continuation supplémentaire n’existe dans ce contexte.

Cela ne signifie pas automatiquement :

```text
Tout est en ordre.
```

La sémantique de fin dépend de la surface.

---

# 9. `UNKNOWN`

Signifie :

> le système ne peut pas actuellement établir honnêtement s’il existe une suite.

Le client ne doit pas conclure :

```text
fin du champ
```

ni :

```text
encore du contenu
```

sans base.

---

# 10. Token opaque

Lorsque nécessaire :

```text
CONTINUATION.TOKEN
```

doit être opaque au client.

Le client ne doit pas dépendre de :

```text
page = 7
offset = 120
row id interne
SQL cursor
```

---

# 11. Backend libre, contrat stable

Exemple :

```text
Owner A
→ Django Paginator

Owner B
→ cursor

Owner C
→ keyset

Owner D
→ read-model fixe
```

Tous peuvent exposer :

```text
items
continuation
```

au niveau Presentation.

---

# 12. Cursor et collections mouvantes

Pour les collections dont l’ordre peut changer rapidement :

```text
Now
Discover
certaines recherches
realtime operational fields
```

un cursor/keyset est souvent plus robuste qu’une page numérique.

Le contrat n’impose toutefois pas une seule stratégie technique.

---

# 13. Chargement automatique

Le client doit normalement charger la suite automatiquement.

Flux :

```text
contenu acquis
↓
approche de la fin
↓
prefetch
↓
fusion
↓
continuation de lecture
```

---

# 14. Préchargement anticipé

Le client ne doit pas attendre que l’utilisateur atteigne exactement le dernier pixel.

Le seuil peut dépendre de :

```text
surface
densité
taille moyenne des unités
réseau
mémoire
viewport
```

Aucun seuil universel n’est gelé.

---

# 15. Scroll continu

Makolo autorise :

```text
scroll continu
chargement automatique
corpus très long
virtualisation
```

---

# 16. Scroll infini artificiel interdit

Makolo interdit :

```text
contenu fabriqué pour maintenir le scroll
relâchement silencieux de pertinence
popularité comme remplissage
répétition artificielle
contenu sans finalité
```

---

# 17. Doctrine de continuation

```text
SCROLL CONTINU
OUI

CHARGEMENT AUTOMATIQUE
OUI

CORPUS POTENTIELLEMENT TRÈS LONG
OUI

SCROLL ARTIFICIELLEMENT SANS FIN
NON
```

---

# 18. Le serveur peut dire stop

Principe :

```text
LE SERVEUR PEUT DIRE :
« IL N’Y A PLUS RIEN D’UTILE À AJOUTER ICI. »
```

Le client doit savoir s’arrêter proprement.

---

# 19. Trois niveaux de fin

Toujours distinguer :

```text
FIN TECHNIQUE D’UN LOT
≠
FIN DU CORPUS
≠
CONCLUSION HUMAINE
```

---

# 20. Fin technique d’un lot

Exemple :

```text
20 éléments reçus
```

ne signifie rien sur la fin réelle du corpus.

---

# 21. Fin du corpus

Établie uniquement par :

```text
CONTINUATION.STATE = END
```

ou équivalent sémantique owner-backed.

---

# 22. Conclusion humaine

Dépend de la surface.

Exemples :

```text
Now
→ Tout est en ordre. ✓

Discover
→ Vous avez vu ce qui est disponible dans ce contexte.

Métier
→ fin silencieuse ou fin de section

Historique
→ fin des éléments disponibles
```

---

# 23. `TERMINAL_SEMANTICS`

Grammaire Presentation commune :

```text
CALM
EMPTY
NO_MATCH
NO_CURRENT_PROPOSAL
END_OF_FIELD
END_OF_COLLECTION
```

Toutes les surfaces ne supportent pas tous ces états.

---

# 24. `CALM`

Signifie :

> la surface a suffisamment établi qu’aucune intervention ou tension pertinente n’est requise.

Exemple Now :

```text
selection established
+ situations = []
+ continuation = END
→ CALM
```

Copie :

> **Tout est en ordre. ✓**

---

# 25. `EMPTY`

Signifie :

> la collection est réellement vide dans le contexte actuel.

Exemple Métier :

```text
Aucun programme pour le moment.
```

---

# 26. `NO_MATCH`

Signifie :

> une recherche ou des filtres explicites ne trouvent aucun résultat.

Ne pas confondre avec :

```text
EMPTY global
```

---

# 27. `NO_CURRENT_PROPOSAL`

Spécifique aux champs de sélection/exploration :

> aucune proposition suffisamment pertinente n’est actuellement retenue.

---

# 28. `END_OF_FIELD`

Signifie :

> le champ d’exploration courant est épuisé.

Exemple Discover :

> Vous avez vu ce qui est disponible dans ce contexte.

---

# 29. `END_OF_COLLECTION`

Signifie :

> la collection bornée est terminée.

Souvent aucun message visible n’est nécessaire.

---

# 30. `Tout est en ordre` n’est jamais un `has_more=false`

Invariant :

```text
has_more = false
≠ Tout est en ordre
```

Il faut une conclusion sémantique réellement établie.

---

# 31. Discover et `Explorer plus largement`

Lorsque :

```text
END_OF_FIELD
```

Discover peut proposer :

```text
Explorer plus largement
```

Cette action doit être volontaire.

Elle modifie explicitement l’Exploration Context.

---

# 32. Pas de relâchement silencieux

Interdit :

```text
plus rien de pertinent
↓
serveur ajoute automatiquement du contenu moins pertinent
```

uniquement pour prolonger le scroll.

---

# 33. Identité stable

Toute unité répétable importante doit avoir une identité stable.

```text
ITEM_IDENTITY
```

---

# 34. Utilités de l’identité stable

Elle permet :

```text
ADD
UPDATE
REMOVE
INVALIDATE
DEDUP
SELECTION
BACK/RESUME
CACHE
RECONCILIATION
```

---

# 35. Identité owner vs identité de projection

Lorsque l’unité correspond à un owner unique :

```text
owner identity
```

peut suffire.

Lorsque plusieurs owners sont composés :

```text
projection identity opaque
```

peut être nécessaire.

---

# 36. Déduplication interdite par similarité

Ne jamais utiliser :

```text
même titre
même date
même image
texte proche
```

comme identité.

---

# 37. Reconciliation

La synchronisation entrante doit pouvoir :

```text
ADD
UPDATE
REMOVE
INVALIDATE
MARK_STALE
SIGNAL_CONFLICT
```

---

# 38. Fusion de continuation

Lorsqu’un nouveau lot arrive :

```text
lot acquis
+
nouveau lot
→ reconciliation
```

Pas :

```text
append aveugle
```

---

# 39. Stabilité d’ordre

Le client doit préserver l’ordre serveur.

Il ne recalculera pas un ranking global.

---

# 40. Collection mouvante

Une nouvelle donnée peut apparaître avant des éléments déjà affichés.

Le client doit éviter de déplacer brutalement l’utilisateur.

---

# 41. Ancre visuelle

Si l’utilisateur lit :

```text
item 47
```

et que trois éléments arrivent en tête, préserver l’ancre autant que possible.

---

# 42. Mises à jour au-dessus

Préférer selon surface :

```text
[ 3 mises à jour ]
```

ou une insertion sans déplacement perceptible.

---

# 43. Exception opérationnelle

Une vérité critique réellement urgente peut avoir un contrat d’interruption spécifique.

Cette exception ne doit pas devenir la norme.

---

# 44. Virtualisation

```text
LOGICAL COLLECTION
≠ ALL RENDERED NODES
```

Le client peut conserver une collection logique très grande sans rendre tous les éléments simultanément.

---

# 45. Flutter

Utiliser des primitives lazy/virtualisées adaptées.

---

# 46. Web

Virtualiser lorsque cela est réellement nécessaire.

Ne pas introduire une complexité de virtualisation sur de petites collections sans bénéfice.

---

# 47. Loading initial

Quand aucun snapshot utile n’existe :

```text
INITIAL
→ LOADING
→ CONTENT / EMPTY / ERROR
```

---

# 48. Loading avec contenu existant

Préférer :

```text
CONTENT + SYNCING
```

à :

```text
CONTENT
→ EMPTY SCREEN
→ SKELETON
→ CONTENT
```

---

# 49. Refresh

Contrat :

```text
contenu actuel
+ indicateur discret
→ reconciliation
→ contenu actualisé
```

---

# 50. Refresh préserve le contexte

Préserver autant que possible :

```text
actor
Space
responsibility
business perspective
query
filters
sort
scroll
selection
depth
map camera
comparison
draft
```

---

# 51. Refresh ne change pas l’autorité

Un refresh ne donne aucun droit supplémentaire.

---

# 52. Refresh ne relance pas arbitrairement le ranking client

Le serveur reste propriétaire de l’ordre sémantique.

---

# 53. Back

Contrat :

```text
DEPTH
→ BACK
→ CONTEXTE PRÉCÉDENT
```

---

# 54. Back ne réinitialise pas la racine

Interdit :

```text
detail
→ back
→ scroll = 0
→ filters perdus
```

---

# 55. Resume

Après interruption :

```text
surface
actor
Space
query
filters
scroll
selection
depth
draft
```

peuvent être restaurés lorsque le contexte reste valide.

---

# 56. Revalidation après Resume

Une ancienne sélection locale ne crée aucune autorité.

Les actions sensibles restent revalidées.

---

# 57. Retour depuis arrière-plan

L’application devrait :

```text
conserver l’écran
rafraîchir discrètement
ne pas réafficher un splash
ne pas perdre le travail local
```

---

# 58. Session expirée

Le travail local utile ne doit pas être détruit.

Flux :

```text
conserver local
→ demander reconnexion
→ restaurer contexte
→ revalider actions
```

---

# 59. Search

Le client exprime une intention.

Le serveur/owner établit le corpus lorsque la recherche dépasse le corpus local acquis.

---

# 60. Search local

Autorisé sur un corpus explicitement acquis.

Le client doit savoir qu’il recherche seulement dans ce corpus.

---

# 61. Search local ≠ Search globale

Interdit :

```text
20 éléments acquis
→ filtre local
→ UI prétend avoir cherché partout
```

---

# 62. Filter

Les filtres peuvent être :

```text
server-backed
local-on-acquired-corpus
hybrides
```

Leur portée doit être honnête.

---

# 63. Sort

Le tri ne doit pas inventer une sémantique métier.

Exemples simples :

```text
Date
Nom
Distance géométrique
```

Mais :

```text
plus pertinent
plus urgent
meilleur
```

doivent venir de l’amont s’ils existent.

---

# 64. Query state

Search, Filter et Sort font partie du contexte restaurable.

---

# 65. Deux axes d’état

Toute surface possède au moins :

```text
CONTENT STATE
```

et :

```text
SYNC STATE
```

---

# 66. Content State

Conceptuellement :

```text
INITIAL
LOADING
CONTENT
EMPTY
SUCCESS
ERROR
```

---

# 67. Sync State

Conceptuellement :

```text
SYNCED
SYNCING
PENDING
OFFLINE
CONFLICT
FAILED
```

---

# 68. Combinaisons autorisées

Exemples :

```text
CONTENT + OFFLINE
CONTENT + SYNCING
CONTENT + PENDING
EMPTY + SYNCED
ERROR + ONLINE
```

---

# 69. Offline n’est pas un écran global

Une perte réseau ne transforme pas automatiquement une surface avec données locales en erreur.

---

# 70. Freshness

Toujours distinguer :

```text
KNOWN
UNKNOWN
STALE
CONTRADICTORY
UNAVAILABLE
HIDDEN
```

---

# 71. Known

Valeur connue.

---

# 72. Unknown

Valeur non connue.

Pas :

```text
false
```

---

# 73. Stale

Une donnée connue est trop ancienne pour certains usages.

---

# 74. Contradictory

Plusieurs sources pertinentes se contredisent.

---

# 75. Unavailable

Une source ou capacité ne peut actuellement être obtenue.

---

# 76. Hidden

La donnée n’est pas divulguée dans le scope.

Elle ne doit pas être convertie en absence métier.

---

# 77. Freshness serveur vs âge local

Toujours :

```text
SERVER FACT FRESHNESS
≠
LOCAL SNAPSHOT AGE
```

---

# 78. Local-first

Pour les données déjà acquises lorsque le contrat le permet :

```text
UI
↓
LOCAL STORE
↓
SYNC ENGINE
↓
SERVER
```

---

# 79. Le réseau sert principalement à

```text
synchroniser
enrichir
rafraîchir
confirmer
résoudre les opérations globales
```

---

# 80. Local-first ≠ local authoritative

Le client local n’est pas automatiquement autoritatif sur :

```text
Permission
Mandate
Access partagé
Payment
Capacity globale
allocation concurrente
état Live
```

---

# 81. Snapshot

Le snapshot local représente :

> le dernier état acquis autorisé.

Pas :

> la vérité actuelle garantie.

---

# 82. Cache viewer-scoped

Les données locales privées doivent être isolées par :

```text
Profile
actor
Space
scope
```

selon besoin.

---

# 83. Changement de Profile

Interdit :

```text
Profile A
→ logout
→ Profile B
→ voit snapshot A
```

---

# 84. Changement d’acteur

Le viewer peut rester le même mais l’acteur changer.

Exemple :

```text
Jean agit comme lui-même
→ Jean agit pour Mulykap
```

Les données et capabilities incompatibles doivent être recontextualisées.

---

# 85. Outbox

Toute opération synchronisable dont la perte serait problématique doit pouvoir utiliser une outbox durable.

---

# 86. Une entrée d’outbox doit pouvoir porter

```text
identity
order si nécessaire
dependencies
retry information
idempotency
status
terminal failure
remote confirmation
```

---

# 87. Mutation lifecycle

Conceptuellement :

```text
PREPARED
LOCAL
QUEUED
SENDING
SENT
AWAITING_CONFIRMATION
CONFIRMED
FAILED
CONFLICT
```

Toutes les surfaces ne doivent pas afficher ces noms littéralement.

---

# 88. Langage humain de mutation

Exemples :

```text
Enregistré
En attente d’envoi
Envoi en cours
Envoyé
En attente de confirmation
Confirmé
Échec
Conflit à résoudre
```

---

# 89. Aucun faux succès

Invariant :

```text
clic
≠ succès

stockage local
≠ synchronisé

queued
≠ envoyé

envoyé
≠ accepté

Payment
≠ résultat métier
```

---

# 90. Feedback immédiat

Toute action volontaire significative doit produire un retour perceptible rapidement.

---

# 91. Double-submit

Le client doit éviter qu’un double tap ou double clic crée deux opérations.

---

# 92. Idempotence

Une opération synchronisable devrait disposer d’une identité stable.

```text
retry
≠ nouvelle action
```

---

# 93. Idempotence serveur

Les domaines soumis à concurrence doivent définir leurs garanties propres.

---

# 94. Optimistic UI

Autorisé seulement lorsque le niveau affiché reste honnête.

---

# 95. Optimistic UI interdit pour certaines vérités

Ne pas déclarer localement comme confirmés :

```text
Payment
Access accordé
Capacity attribuée
Mandate accordé
passage validé
```

sans confirmation autoritative.

---

# 96. Pending

Le client peut dire :

```text
En attente
```

sans modifier la vérité canonique.

---

# 97. Retry

Le retry doit réutiliser l’identité de l’opération lorsque le contrat le permet.

---

# 98. Undo

Undo est approprié si l’action est :

```text
réversible
faible risque
réellement annulable
```

---

# 99. Confirmation

Utiliser une confirmation lorsque :

```text
action irréversible
action fortement conséquente
risque réel
```

Pas pour chaque micro-action.

---

# 100. Conflict

Un conflit n’est pas un échec réseau générique.

Il signifie :

> deux états légitimes ne peuvent être fusionnés silencieusement.

---

# 101. Authority revalidation

Toujours :

```text
capability affichée
≠ authority token
```

---

# 102. TOCTOU

Cas normal :

```text
GET
→ capability visible
→ Mandate révoqué
→ mutation
→ refus
→ reconciliation
```

---

# 103. Permission denied

La surface doit distinguer :

```text
aucun accès à l’objet
```

de :

```text
objet visible mais action interdite
```

---

# 104. Privacy-safe failure

Lorsque l’existence d’une ressource est sensible :

```text
404 / absence de divulgation
```

peut être préférable à un détail explicite d’autorisation.

---

# 105. Minimal disclosure

Une projection ne doit transporter que ce qui est nécessaire.

---

# 106. Error locale avant globale

Principe :

```text
FAIL LOCALLY BEFORE FAILING GLOBALLY
```

---

# 107. Partial

Exemple :

```text
source A ✓
source B ✓
source C unavailable
source D ✓
```

Conserver A, B et D.

---

# 108. Erreur globale

Seulement si ce qui reste ne permet plus une expérience honnête ou utile.

---

# 109. Message d’erreur

Une erreur importante doit répondre :

```text
qu’est-ce qui a échoué ?
qu’est-ce qui est conservé ?
que puis-je faire ?
```

---

# 110. Realtime

Realtime est un mode de livraison du changement.

Pas une vérité métier.

---

# 111. Pipeline realtime

```text
WebSocket / push / polling
↓
signal de changement
↓
reconciliation autoritative
↓
store / projection
↓
UI
```

---

# 112. Push payload

Un push ne devient pas automatiquement une vérité permanente.

---

# 113. Realtime ≠ Live

```text
REALTIME
→ arrivé rapidement

LIVE
→ effectivement observé maintenant
```

---

# 114. États temporels distincts

```text
planned
estimated
observed
live
unknown
unavailable
```

---

# 115. Insertion realtime

Ne doit pas casser le scroll ou la sélection.

---

# 116. Deep Link

Un deep link doit reconstruire suffisamment de contexte.

---

# 117. Pipeline Deep Link

```text
AUTHENTICATE
↓
RESOLVE ACTOR
↓
VERIFY AUTHORITY
↓
RESOLVE OWNER
↓
RECONSTRUCT PRESENTATION CONTEXT
↓
OPEN DEPTH
```

---

# 118. Deep Link après authentification

Si la session est expirée :

```text
deep link
→ login
→ retour à la destination
```

si le contexte reste légitime.

---

# 119. Notification routing

Une notification doit conduire vers une profondeur légitime.

---

# 120. Notification ancienne

Si la destination n’existe plus ou n’est plus autorisée :

```text
privacy-safe resolution
+
alternative utile si possible
```

---

# 121. Media loading

Le média ne doit pas bloquer le texte ou l’action lorsque ceux-ci suffisent.

---

# 122. Media pipeline

```text
metadata
→ placeholder contextualisé
→ lazy load
→ media
```

---

# 123. Media cache

Un média en cache ne confère pas un droit d’accès permanent.

---

# 124. Sensitive media

Les ressources sensibles doivent respecter les contrats de stockage local et de confidentialité.

---

# 125. Adaptive Conservation

Compact, Medium et Wide changent :

```text
géométrie
densité
placement
```

pas :

```text
vérité
autorité
priorité métier
action légitime
```

---

# 126. Conserver lors d’une adaptation

```text
actor
surface
selection
depth
focus
scroll
filters
query
map position
draft
```

autant que possible.

---

# 127. Responsive ≠ refetch métier

Un changement de largeur n’implique pas automatiquement une nouvelle requête métier.

---

# 128. Largeur ≠ densité forcée

Un écran large ne doit pas être rempli uniquement pour occuper l’espace.

---

# 129. Progressive disclosure

Une racine explique l’essentiel.

Les détails apparaissent en profondeur lorsqu’ils deviennent utiles.

---

# 130. Accessibilité

L’accessibilité est un contrat de base.

Pas une étape finale de QA.

---

# 131. Keyboard

Toute action importante accessible à la souris doit être utilisable au clavier lorsque la plateforme le permet.

---

# 132. Focus

Le focus doit être :

```text
visible
prévisible
conservé ou restauré intelligemment
```

---

# 133. Screen reader

Les unités doivent avoir :

```text
labels
ordre de lecture
états
actions
```

compréhensibles.

---

# 134. Text scaling

Le contenu doit rester utilisable avec augmentation significative du texte.

---

# 135. Reduced Motion

Les animations essentielles doivent avoir une alternative compatible avec `reduce motion`.

---

# 136. Touch targets

Les actions tactiles doivent disposer de cibles suffisantes.

---

# 137. Hover

Aucune action essentielle ne doit dépendre uniquement du hover.

---

# 138. Couleur

Une information importante ne doit pas dépendre uniquement de la couleur.

---

# 139. Gesture-only interdit

Une action essentielle ne doit pas être accessible uniquement par un geste caché.

---

# 140. Matrice d’application — Now

Collections :

```text
Situations[]
```

Continuation :

```text
auto
```

Fin :

```text
CALM seulement si sélection établie
```

Realtime :

```text
reconciliation calme
```

Scroll :

```text
borné par la réalité
```

---

# 141. Matrice — Discover

Collections :

```text
Possibilities[]
```

Continuation :

```text
auto
```

Fin :

```text
NO_MATCH
NO_CURRENT_PROPOSAL
END_OF_FIELD
```

Expansion :

```text
Explorer plus largement
→ volontaire
```

---

# 142. Matrice — En cours

Collections :

```text
Continuities[]
```

Continuation :

```text
auto si nécessaire
```

Fin :

```text
END_OF_COLLECTION
```

Calm :

```text
peut exister avec continuités encore ouvertes
```

---

# 143. Matrice — Moi

Collections :

```text
Sections / territories
```

Continuation :

```text
principalement locale aux sections
```

Fin :

```text
empty local
```

---

# 144. Matrice — Space Now

Même doctrine que Now personnel, avec scope Space et responsabilité.

---

# 145. Matrice — Space Discover

Même doctrine que Discover, avec actor Space et relevance collective.

---

# 146. Matrice — Métier

Collections :

```text
Business Sections
Business Entries
```

Continuation :

```text
auto au niveau de section
```

Fin :

```text
END_OF_COLLECTION
```

Pas de :

```text
Tout est en ordre
```

simplement parce qu’une section est terminée.

---

# 147. Matrice — Nous

Collections :

```text
team
relations
governance
territories
```

Continuation :

```text
par section
```

Fin :

```text
souvent silencieuse
```

---

# 148. Matrice — Jour J

Jour J n’est pas principalement une surface de continuation longue.

Priorité :

```text
current context
operation
support
```

---

# 149. Matrice — Historique

Continuation :

```text
auto
```

Fin :

```text
END_OF_COLLECTION
```

---

# 150. Matrice — Search

Continuation :

```text
auto
```

Fin :

```text
NO_MATCH
END_OF_COLLECTION
```

Le scope de recherche doit être clair.

---

# 151. `Tout est en ordre. ✓`

Cette phrase est réservée aux contextes où le système peut réellement conclure au calme.

Principalement :

```text
Now
Space Now
```

et éventuellement d’autres surfaces si leur contrat futur le définit explicitement.

---

# 152. Silence comme fonctionnalité

Lorsqu’il n’y a plus rien d’utile :

```text
ne pas remplir
ne pas recommander artificiellement
ne pas générer une notification
ne pas ajouter du contenu décoratif
```

---

# 153. No Orphan Content

Toute unité chargée doit avoir :

```text
contexte
purpose
owner
```

---

# 154. No Orphan Media

Tout média doit avoir :

```text
target
purpose
```

---

# 155. Privacy et cache

Le cache local doit respecter :

```text
Profile
actor
scope
sensitivity
revocation behavior
```

---

# 156. Secrets

Ne jamais stocker ou exposer inutilement :

```text
tokens
AccessCredentials complets
QR secrets
private keys
provider secrets
PII inutile
```

---

# 157. Telemetry produit

Les métriques doivent mesurer :

```text
accomplissement
temps vers action utile
réduction des blocages
continuité
succès réel
qualité des handoffs
```

---

# 158. Métriques interdites comme objectifs centraux

```text
watch time
scroll depth pour retenir
streak
likes
engagement artificiel
```

---

# 159. Tests transversaux obligatoires

Chaque grande surface doit tester :

```text
initial
loading
content
empty/calm
partial
error
offline
permission denied
refresh
back
resume
deep link
continuation
end
```

selon pertinence.

---

# 160. Tests Continuation

Couvrir :

```text
0 item + END
1 lot + END
plusieurs lots
lot partiel + MORE
MORE puis END
UNKNOWN
retry continuation
duplicate prevention
item update entre deux lots
item removal
new item before anchor
```

---

# 161. Tests Scroll

Couvrir :

```text
position preserved
new items do not jump user
back restores anchor
resume restores position
viewport change preserves selection
```

---

# 162. Tests Mutation

Couvrir :

```text
single submit
double submit
retry
idempotence
outbox
offline queue
remote confirmation
conflict
terminal failure
```

---

# 163. Tests Authority

Couvrir :

```text
capability visible puis révocation
foreign actor
wrong Space
Activity-limited
hidden data
permission denied action
privacy-safe root
```

---

# 164. Tests Freshness

Couvrir :

```text
known
unknown
stale
contradictory
unavailable
hidden
offline stale snapshot
```

---

# 165. Tests Realtime

Couvrir :

```text
add
update
remove
invalidate
no scroll jump
no false Live
```

---

# 166. Tests Accessibility

Couvrir :

```text
keyboard
focus
screen reader labels
text scale
reduced motion
touch targets
no hover-only action
```

---

# 167. Points volontairement non figés

Restent ouverts :

1. noms JSON exacts ;
2. type de cursor exact par endpoint ;
3. tailles de lots par surface ;
4. seuils exacts de prefetch ;
5. stratégie de virtualisation Web exacte ;
6. seuils mémoire Flutter ;
7. wording final de tous les terminal states ;
8. protocole realtime endpoint par endpoint ;
9. politique de cache détaillée par owner ;
10. stratégie exacte de conflict resolution par domaine ;
11. implémentation finale des deep links ;
12. instrumentation analytics exacte ;
13. primitives UI techniques finales.

Aucun de ces points ne remet en cause le contrat conceptuel.

---

# 168. Formulation finale

> **Makolo sépare strictement la pagination technique de l’expérience de continuation. Le serveur peut lire les données par lots bornés et décider quand une suite existe ; le client présente ces lots comme une continuité fluide, automatiquement chargée, sans pages visibles ni contenu artificiel. Une fin technique ne devient jamais automatiquement une conclusion humaine : chaque surface interprète la fin selon son contrat — calme dans Maintenant, fin de champ dans Découvrir, fin de collection dans Métier ou Historique.**

> **La même doctrine s’applique à l’ensemble de l’expérience : les unités gardent une identité stable, les mises à jour se réconcilient sans casser le scroll, le refresh conserve le contenu utile, Back et Resume restaurent le contexte, les mutations distinguent pending et confirmé, l’offline conserve ce qui est honnêtement connu, l’autorité est toujours revalidée, le realtime transporte des changements sans devenir vérité, et l’adaptation d’écran change la géométrie sans changer le sens.**

---

# 169. Principe final

```text
LE SERVEUR PAGINE.
LE CLIENT CONTINUE.
LE SERVEUR DÉCIDE QUAND LE CHAMP EST TERMINÉ.
LA SURFACE DÉCIDE CE QUE CETTE FIN SIGNIFIE HUMAINEMENT.
```

Et :

```text
MAKOLO PEUT SCROLLER TRÈS LOIN.

MAKOLO N’A PAS BESOIN DE SCROLLER POUR TOUJOURS.
```

La fin utile fait partie de l’expérience.
