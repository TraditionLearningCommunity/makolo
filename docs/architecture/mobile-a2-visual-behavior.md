# A2 — Visual & Behavior contract

> **Portée : surfaces personnelles mobile A2**
>
> **Statut : contrat A2-P0**
>
> Ce document complète le système Behavior transversal et les tokens A1. Il ne crée pas un nouveau design system.

## 1. Intention

A2 doit paraître :

- calme ;
- précis ;
- contemporain ;
- chaleureux ;
- confiant ;
- tactile ;
- vivant sans être festif ;
- professionnel sans devenir institutionnel.

La hiérarchie de chaque écran suit :

~~~text
contexte
→ ce qui compte
→ prochain geste
→ détails secondaires
~~~

A2 ne vise ni la densité d'un dashboard SaaS, ni le rendu d'un prototype Flutter, ni la copie responsive du Web.

## 2. Identité Makolo

Tokens canoniques installés par A1 :

| Rôle | Valeur |
|---|---|
| Makolo Indigo | #5232DB |
| Makolo Deep | #2B176E |
| Makolo Pulse | #FF704D |
| Makolo Warm | #FAF7F5 |
| Makolo Ink | #0F172A |

Le Pulse est rare. Il ne devient pas une seconde couleur primaire.

Le Makolo Mark officiel est la signature centrale. A2 utilise les assets canoniques A1 et ne dessine jamais un M approximatif, un FAB générique ou une variante mobile de la marque.

Une ancienne formulation de brand-visual-system-v1 mentionne un M temporaire et un Warm historique différent. Le runtime A1 et le Product Signature System courant gagnent : Mark officiel et Warm #FAF7F5.

## 3. Typographie

A1 prévoit :

- Manrope pour marque et titres lorsque disponible ;
- Inter pour UI et texte ;
- fallbacks système sûrs.

A2 n'ajoute ni téléchargement de fonte ni package de fonte sans vérification de licence et décision orchestrateur.

Le text scaling doit rester fonctionnel. Aucun titre critique ne dépend d'une hauteur fixe fragile.

## 4. Espacement, rayons et motion

Réutiliser les primitives A1 :

- spacing : 4 / 8 / 16 / 24 / 32 ;
- radii : 10 / 16 / 24 ;
- motion : courte 160 ms, moyenne 240 ms.

Une feature peut composer ces tokens ; elle ne crée pas A2Spacing, A2Radii, A2Theme ou équivalent.

## 5. Langage de surfaces

### Maintenant

Sensation : **calme / priorité**.

- beaucoup d'espace si peu de choses comptent ;
- premier bloc = ce qui mérite réellement une action ;
- différencier action requise et information ;
- un vrai all-clear peut devenir l'élément principal ;
- ne jamais remplir artificiellement l'écran.

### Découvrir

Sensation : **envie / exploration**.

- plus visuel que Maintenant ;
- média seulement s'il appartient à la représentation propriétaire ;
- date, lieu, owner et contexte quand réellement disponibles ;
- cards plus expressives autorisées ;
- fin de corpus explicite ;
- pas d'autoplay ni scroll infini fabriqué.

### Makolo Mark

Sensation : **simplicité / intention**.

- Mark ;
- question ;
- champ naturel ;
- résultat, clarification ou confirmation ;
- pas de menu de capacités internes ;
- pas d'UI de chatbot persistant par défaut.

### En cours

Sensation : **continuité / progression**.

- distinguer rapidement ce qui demande une action, ce qui suit son cours et ce qui est prêt ;
- utiliser les structures serveur ;
- pas de Kanban ;
- pas de todo list générale ;
- pas de pourcentage global artificiel.

### Moi

Sensation : **identité / capital personnel**.

- identité douce ;
- sections et previews ;
- Passeport, considérations, collectifs, ressources, support selon données disponibles ;
- pas de formulaire géant ;
- pas de grille de raccourcis techniques.

### Avatar

Sensation : **compte / contexte acteur**.

- pattern court, idéalement bottom sheet si le contenu tient ;
- identité minimale ;
- contexte réellement autorisé ;
- compte, sécurité, paramètres, déconnexion lorsque supportés ;
- ce n'est pas une sixième destination principale.

## 6. Headers contextuels

Le header exprime le mode mental courant.

### Maintenant

Peut contenir :

~~~text
Makolo | Conversations | Notifications | Avatar
~~~

Uniquement les contrôles réellement routés.

### Découvrir

~~~text
Découvrir | Recherche | Filtres/contexte | Avatar
~~~

Les filtres secondaires vont de préférence en bottom sheet.

### Mark

~~~text
Makolo | Avatar
~~~

Le retour système/natif reste prioritaire lorsqu'il est empilé.

### En cours

~~~text
En cours | lecture temporelle si utile | Avatar
~~~

Ne pas ajouter un calendrier si la projection ne justifie pas cette lecture.

### Moi

~~~text
Moi | Avatar
~~~

Avatar et Moi ne sont jamais fusionnés.

## 7. Bottom navigation

Contrat immuable A2 :

~~~text
Maintenant | Découvrir | [Mark] | En cours | Moi
~~~

Le Mark est une action centrale, pas un cinquième onglet.

L'état actif doit être compréhensible par :

- forme ;
- label ;
- couleur.

Il ne dépend jamais seulement de la couleur.

Le Mark doit être reconnaissable sans devenir surdimensionné ou gadget.

## 8. Cards et surfaces

Interdit : transformer chaque information en Card.

Préférer selon le contenu :

- surface ouverte ;
- section ;
- ligne ;
- liste ;
- groupe ;
- chip ;
- média ;
- card importante.

Une Card est utilisée quand l'objet mérite un contenant autonome ou un geste propre.

La hiérarchie peut venir de l'espace, de la typographie et de l'alignement, pas de border + shadow + radius répétés partout.

## 9. Loading

Règle :

- si le contenu local existe, le conserver ;
- aucun loader plein écran pour un simple refresh ;
- skeleton uniquement lorsqu'aucune projection utile n'est disponible ;
- éviter un flash de skeleton pour une réponse quasi instantanée ;
- une action locale significative reçoit un feedback immédiat.

Séquence préférée :

~~~text
contenu actuel
+ indicateur discret
→ store mis à jour
→ UI se met à jour
~~~

Pas :

~~~text
contenu
→ vide
→ spinner
→ contenu
~~~

## 10. Empty states

Chaque empty state répond à la question de sa surface.

Il faut distinguer au minimum :

- **non bootstrapé** : aucune projection connue sur cet appareil ;
- **vrai vide** : projection synchronisée et collection vide ;
- **all-clear** : absence volontaire de chose nécessitant l'attention ;
- **recherche sans résultat** : critères présents, aucun résultat ;
- **fin de corpus** : exploration bornée terminée.

Exemple critique :

> **Tout est en ordre. ✓**

n'est affiché dans Maintenant que si le serveur a réellement produit un items vide connu. L'absence de snapshot n'est jamais un accomplissement.

## 11. Error

Une erreur mature dit :

1. ce qui n'a pas marché ;
2. ce qui reste disponible ;
3. ce que la personne peut faire.

Exemple :

> Impossible de mettre à jour pour le moment. Ce qui était déjà disponible reste accessible. Réessayer.

Ne jamais montrer SocketException, HTTP 500, schema, projection, outbox ou owner.

## 12. Offline et stale

Offline et contenu sont des axes indépendants.

Exemples normaux :

~~~text
content + offline
content + syncing
content + stale
empty + synced
~~~

Si un contenu local utile existe :

- il reste visible ;
- l'indication réseau reste discrète ;
- la surface ne bascule pas en erreur plein écran.

Stale n'est affiché que lorsque l'âge de la donnée peut modifier une décision ou une action.

Avant une action qui exige une vérité fraîche, revalider côté serveur.

## 13. Refresh

Le pull-to-refresh ou refresh contextuel :

- garde le contenu ;
- démarre une synchronisation discrète ;
- met à jour le store ;
- laisse l'UI observer le store ;
- conserve scroll/query/filtres autant que possible.

Ne jamais réinitialiser automatiquement la destination au début de l'application.

## 14. Retour et navigation

Le geste retour naturel doit fonctionner.

Scénario de référence :

~~~text
liste → détail → retour
~~~

doit préserver raisonnablement :

- scroll ;
- query ;
- filtres ;
- sélection ;
- onglet actif.

Pour une surface empilée comme Mark ou un bottom sheet Avatar, back ferme d'abord la surface supérieure.

Aucune feature ne remplace le routeur par un système de navigation local parallèle.

## 15. Bottom sheets

Pattern préféré pour :

- filtres Discovery ;
- actions contextuelles secondaires ;
- Avatar ;
- petits détails ou confirmations non destructrices lorsqu'un dialogue bloquant n'est pas requis.

Un bottom sheet doit :

- utiliser SafeArea ;
- accepter le clavier ;
- rester scrollable avec grands textes ;
- être fermable naturellement ;
- ne pas devenir un écran complet déguisé si la profondeur appartient à A3.

## 16. Clavier et focus

- input Mark : clavier texte naturel, action adaptée ;
- recherche Discovery : search action ;
- ne pas masquer le champ actif ;
- retour clavier ne doit pas détruire la surface ;
- conserver un draft Mark lors d'une interruption ;
- le focus initial automatique est utilisé seulement s'il n'agresse pas l'accessibilité.

## 17. Motion

La motion explique :

- continuité ;
- causalité ;
- changement ;
- progression.

Autorisé :

- translation courte ;
- fade ;
- transition de sélection ;
- morphing Mark court s'il clarifie l'ouverture de l'intake.

Interdit :

- rebond cartoon ;
- parallaxe gratuite ;
- confettis ;
- attente artificielle ;
- animation bloquant l'action ;
- autoplay décoratif.

Reduce Motion :

- supprime les grands déplacements ;
- raccourcit ou annule les transitions non essentielles ;
- conserve l'information finale sans dépendre de l'animation.

## 18. Haptics

Haptics possibles pour :

- choix important ;
- confirmation ;
- accomplissement réel ;
- erreur locale claire ;
- ouverture/confirmation Mark significative.

Pas de haptic à chaque tap ou scroll.

Une action distante n'utilise pas un haptic de succès définitif avant confirmation autoritative.

## 19. Touch targets

Tout contrôle interactif important doit être confortable au pouce et rester atteignable à grande taille de texte.

Les cibles tactiles ne sont pas réduites pour faire entrer davantage d'actions sur une ligne. Les actions secondaires passent plutôt en menu/bottom sheet.

## 20. Accessibilité

Gate obligatoire :

- Semantics avec nom, rôle et état ;
- ordre de lecture logique ;
- text scaling/grands textes ;
- contraste ;
- information non dépendante uniquement de la couleur ;
- cibles tactiles ;
- Reduce Motion ;
- états de sync annoncés sans spam de live region ;
- médias avec alternative utile si nécessaire.

Les goldens ne remplacent pas un test Semantics.

## 21. Confidentialité visuelle

Les projections personnelles appliquent la divulgation minimale.

Ne pas exposer dans :

- toast ;
- notification système ;
- preview de fenêtre ;
- logs ;
- capture de test committée ;

des tokens, QR complets, credentials, secrets de paiement, PII inutile ou contenu privé non nécessaire.

Un écran de sélection de compte/contexte n'affiche que le minimum requis pour identifier l'acteur.

## 22. Performance perçue

Priorités :

- lecture locale immédiate ;
- aucun flash blanc ;
- contenu préservé ;
- média progressif ;
- dimensions média stabilisées avant chargement si possible ;
- pas de layout shift inutile ;
- listes fluides ;
- transitions courtes.

## 23. Screenshots et visual QA

Chaque lane produit des captures représentatives :

- petit téléphone ;
- téléphone moyen ;
- grand téléphone ;
- état contenu ;
- vide ;
- offline ;
- erreur ;
- loading ;
- text scaling.

Revue visuelle :

- hiérarchie ;
- clipping ;
- whitespace ;
- densité ;
- contraste ;
- identité ;
- touch targets ;
- cohérence des états.

Les cinq surfaces doivent appartenir à la même application sans être cinq copies d'un template.

## 24. Goldens ciblés

Candidats utiles :

- shell/navigation ;
- Maintenant all-clear ;
- une composition Maintenant avec action ;
- Discover card/section stable ;
- Mark intake ;
- Moi header/section ;
- empty state majeur.

Ne pas snapshotter tout le produit au pixel près.

## 25. ANTI-GENERIC-FLUTTER

A2 refuse explicitement :

- AppBar/Scaffold par défaut laissé sans composition ;
- Card identique pour chaque ligne ;
- bleu Material par défaut ;
- FAB générique à la place du Makolo Mark ;
- spinner plein écran à chaque visite ;
- placeholder technique visible ;
- dashboard de tuiles uniformes ;
- CRUD mobile ;
- copie littérale des templates Web ;
- couleurs ou ombres utilisées comme unique hiérarchie ;
- texte A1, A2, outbox, projection, schema, owner, payload ou backend dans l'UX ;
- message expliquant l'architecture au lieu d'aider la personne ;
- action sans destination utile ;
- contenu factice pour remplir un écran.

## 26. Definition of polished

Une surface est polie si :

- sa question humaine est comprise en quelques secondes ;
- l'information importante ressort ;
- le prochain geste est évident ou l'absence de geste est claire ;
- le vide semble intentionnel ;
- le refresh n'interrompt pas ;
- offline reste utile ;
- stale est honnête ;
- les transitions sont causales ;
- le grand texte reste utilisable ;
- le lecteur d'écran comprend l'ordre ;
- l'écran semble conçu, pas assemblé.
