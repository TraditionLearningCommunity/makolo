# M8 UX Shell Contract — expérience personnelle mobile-first

> Statut : contrat d'expérience du shell personnel Mature. Il complète `mature-experience-principles.md` sans créer de bounded context. Le code, les migrations et les tests du `main` courant restent la vérité runtime.

## Problème utilisateur

Le shell personnel historique exposait trop directement la structure interne de Makolo : Accueil, Démarches, Conversations, Profil, Espaces, Accès, Bibliothèque, Veilles et Historique se retrouvaient en concurrence dans les rails de navigation, tandis que certaines destinations étaient répétées dans la topbar.

Cette structure faisait ressembler Makolo à un site Django composé de modules plutôt qu'à une application qui aide une personne à avancer.

## Principe

> **La situation humaine précède l'objet métier.**

La promesse reste : **Makolo marche pour vous.**

La règle d'expérience reste : **Pas le plaisir de rester. Le plaisir d'avancer.**

Et le shell suit la règle :

> **Makolo doit être immense à l'intérieur et petit à l'extérieur.**

Les domaines Django restent propriétaires de leurs vérités. Le shell les compose selon la question humaine du moment ; il ne les transforme pas en navigation primaire.

## Architecture mobile de référence

La navigation personnelle primaire est :

> **Maintenant | Découvrir | [Makolo Mark] | En cours | Moi**

Elle contient quatre destinations et une action centrale.

### Maintenant

Question : **« Qu'est-ce qui mérite que je fasse quelque chose maintenant ? »**

`Maintenant` n'est ni un dashboard, ni un bulletin, ni une liste de toutes les actions possibles. Une réalité y entre seulement lorsqu'elle change ce que la personne doit faire, décider, éviter ou adapter maintenant.

Lorsque rien ne passe ce filtre :

> **Tout est en ordre. ✓**

Cette réponse est complète. Aucun contenu de rétention ne doit être ajouté pour remplir le calme.

### Découvrir

Question : **« Qu'est-ce que je pourrais avoir envie de vivre, faire ou obtenir ? »**

`Découvrir` est l'espace des possibilités, pas des nouveautés. Recherche, filtres, carte et médias sont des moyens d'exploration, pas des catégories métier. Lorsqu'une possibilité devient réellement choisie, Discover passe le relais aux domaines d'accomplissement.

### Makolo Mark

Sens : **« J'ai quelque chose à donner à Makolo. »**

Le Mark est une porte d'intake et d'orchestration. Il n'est ni une destination métier, ni un bouton `+`, ni une boîte d'upload universelle, ni un chatbot générique. La personne commence dans son propre langage ; Makolo retrouve ensuite le contexte utile sans inventer de capacité, de vérité ou d'autorité.

### En cours

Question : **« Pour ce que j'ai déjà engagé, puis-je avancer tranquille — et sinon, quelle est la plus petite chose utile qu'il me reste à faire ? »**

`En cours` compose la continuité de réalités déjà engagées. Journey, Payment, Access, Capacity, Occurrence et Readiness restent des vérités internes ; l'interface présente leur conséquence humaine.

### Moi

Question : **« Qu'est-ce qui est déjà en place autour de moi pour que Makolo marche mieux pour moi ? »**

`Moi` compose identité, Passeport Makolo, ce que la personne a demandé à Makolo de considérer, ses collectifs et ses ressources. Il ne remplace ni Compte ni Paramètres.

## Ce qui ne devient pas une destination primaire

Le shell personnel ne crée pas d'onglet global pour :

- Démarches ;
- Conversations ;
- Profil ;
- Espaces ;
- Accès ;
- Bibliothèque ;
- Veilles ;
- Historique ;
- Notifications ;
- Paramètres ;
- Plus.

Ces capacités restent accessibles lorsqu'un contexte légitime les appelle, notamment depuis les surfaces secondaires ou l'Avatar.

## Headers contextuels

Le Header reflète le mode mental courant ; il n'empile pas mécaniquement toutes les commandes globales.

- `Maintenant` : **Makolo | Conversations | Notifications | Avatar**
- `Découvrir` : **Découvrir | Recherche | Filtres / pertinence | Avatar**
- `Makolo Mark` : **Makolo | Avatar**
- `En cours` : **En cours | Calendrier / lecture temporelle | Avatar**
- `Moi` : **Moi | Avatar**

Les pages secondaires utilisent une flèche de retour vers leur surface propriétaire, un titre humain et seulement les actions contextuelles nécessaires.

## Avatar

L'Avatar contrôle identité, contexte d'acteur et compte. Il n'est pas `Moi`.

Il porte notamment :

- l'identité authentifiée ;
- l'activation du Profil Makolo lorsqu'elle est utile ;
- `Agir comme` ;
- Compte et Paramètres ;
- Abonnement et facturation lorsque pertinent ;
- changement de compte ;
- déconnexion.

`Agir comme` ne liste que des contextes réellement autorisés. Sélectionner un contexte n'accorde jamais d'autorité. Membership et Assignment ne remplacent jamais Permission/Mandate.

## Adaptation desktop

Le mobile fixe l'architecture sémantique. Le desktop exploite davantage d'espace sans réintroduire un index des domaines.

La version desktop peut utiliser un rail latéral permanent, mais ce rail porte les mêmes repères :

> **Maintenant · Découvrir · Makolo · En cours · Moi**

Une surface secondaire peut utiliser une présentation master/detail ou davantage de largeur si cela aide l'action ; elle ne crée pas une seconde IA.

## Transitions

Django reste la source de vérité HTML et de permission serveur.

Le shell peut utiliser htmx sur les routes personnelles sûres :

- swap principal sur `#main-content` ;
- `hx-push-url` pour préserver back/forward ;
- swaps out-of-band de la topbar, du rail desktop et de la bottom nav afin de synchroniser le contexte actif ;
- fallback HTML complet sans JavaScript ;
- aucun formulaire destructif ni side effect critique n'est transformé en navigation partielle par réflexe.

Les surfaces d'Espace conservent leur shell d'autorité propre.

## Langage produit

Les principes de conception restent dans les documents ; ils ne deviennent pas du texte d'interface.

L'interface doit parler de la situation de la personne et de la prochaine conséquence utile. Elle évite notamment les formulations qui expliquent la philosophie du produit, le ranking interne, les projections ou l'architecture.

Préférer :

> **Votre demande est envoyée. Ils doivent maintenant la vérifier. Rien à faire de votre côté.**

à une explication de la logique interne de Makolo.

## Compatibilité des surfaces profondes

Les routes historiques telles que `/me/journeys/`, `/me/accesses/` et `/me/history/` peuvent rester disponibles comme profondeurs contextuelles et comme cibles de deep links.

Leur existence ne leur donne plus le statut de destinations primaires.

## Non-objectifs

- pas de nouveau modèle persistant pour le shell ;
- pas de nouveau Readiness global ;
- pas de copie de vérités métier ;
- pas de migration React/Vue/SPA par réflexe ;
- pas de feed, like, popularité ou watch-time ;
- pas de contournement des permissions serveur ;
- pas de faux support de voix, IA, upload ou automatisation lorsque le runtime ne le permet pas réellement.

## Critères d'acceptation

- mobile : `Maintenant | Découvrir | Makolo | En cours | Moi` est la seule navigation personnelle primaire ;
- desktop : les mêmes repères structurent le rail personnel ;
- Conversations n'est pas dupliqué dans le rail ;
- Profil/Compte n'est pas une destination primaire ;
- les headers sont contextuels ;
- `Maintenant` peut se terminer par `Tout est en ordre. ✓` sans CTA de rétention ;
- `En cours` compose la continuité sans exposer les tables ;
- `Moi` compose les vérités personnelles sans dupliquer leurs propriétaires ;
- le Mark commence par une entrée naturelle et n'invente pas de capacité runtime ;
- les deep links secondaires restent utilisables ;
- le shell conserve un fallback HTML complet ;
- aucun changement de schéma n'est requis ;
- les artefacts frontend commités sont synchronisés avec les sources avant validation CI ;
- tests, migrations checks, sécurité et E2E restent verts.
