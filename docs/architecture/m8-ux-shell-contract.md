# M8 UX Shell Contract — navigation claire et transitions modernes

> Statut : contrat d'expérience pour le chantier M8-UX. Ce document complète `mature-experience-principles.md` et ne crée aucun bounded context. Le code, les migrations et les tests du `main` courant restent la vérité runtime.

## Problème utilisateur

Le retour bêta sur `/me/` montre une expérience trop proche d'un site Django classique : destinations répétées, rails concurrents, clics avec rafraîchissement pleine page visible, et impression de logiciel ancien.

Makolo doit devenir un assistant d'action fluide : l'utilisateur comprend où il est, ce qui demande son attention et quelle action le fait avancer.

## Principe

> Makolo ne doit pas multiplier les menus. Makolo doit exposer le prochain contexte utile.

La promesse reste : **Makolo marche pour vous.**

La règle d'expérience reste : **Pas le plaisir de rester. Le plaisir d'avancer.**

## Hiérarchie de navigation

### 1. Navigation primaire personnelle

La navigation personnelle permanente doit rester courte et stable.

Destinations canoniques :

1. **Accueil** — ce qui compte maintenant.
2. **Découvrir** — ouvrir une possibilité réelle.
3. **Mes démarches** — ce que j'ai commencé ou ce qui reste à accomplir.
4. **Mes Espaces** — agir dans un contexte d'autorité explicite.

`Découvrir` peut aussi rester présenté comme carte d'appel en bas de sidebar, parce que cette carte n'introduit pas une deuxième vérité de navigation : elle pointe vers la même destination canonique et sert de rappel visuel de la promesse exploratoire. Les autres destinations ne doivent pas être dupliquées en cartes permanentes équivalentes.

### 2. Retrouver

Les surfaces de récupération ne sont pas le rail d'action principal. Elles servent à retrouver ce qui existe déjà :

- Mes accès ;
- Bibliothèque ;
- Mes veilles ;
- Historique.

Elles restent visibles mais séparées du groupe `Avancer`.

### 3. Compte et identité

Le Profil n'est pas une destination primaire permanente. Il appartient au menu utilisateur et aux cartes d'activation lorsqu'une étape utile manque.

Un Profil reste une personne globale. La navigation ne doit pas le transformer en module métier central ni en rôle global.

### 4. Conversations

Conversations n'est pas une messagerie sociale générique. La surface doit apparaître comme action ou attention lorsqu'une réponse est utile.

Contrat actuel :

- entrée topbar avec badge d'attention ;
- accès possible depuis les contextes qui lient une action réelle ;
- pas de lien permanent dans le rail primaire personnel.

### 5. Espace / autorité

Entrer dans un Espace change de contexte. La navigation d'Espace est autorisée par `Mandate`/`Permission`, jamais par simple Membership.

La composition visuelle ne transfère pas implicitement Permission, Mandate, Access, Payment ni données privées.

## Transitions modernes

Makolo peut utiliser un app shell progressif sans devenir une SPA lourde.

Contrat :

- Django reste source de vérité HTML et permission serveur ;
- htmx peut remplacer progressivement des fragments sûrs ;
- `#main-content` est le candidat de swap pour les routes personnelles stables ;
- `hx-push-url` doit préserver back/forward ;
- les icônes Lucide doivent être réinitialisées après swap ;
- fallback HTML complet obligatoire sans JavaScript ;
- aucun formulaire destructif ou flux critique ne passe en navigation partielle avant audit.

Implémentation de ce slice :

- boost htmx limité au rail personnel `Avancer` / `Retrouver`, à la bottom nav mobile et à la carte `Découvrir` ;
- swap principal sur `#main-content` ;
- swaps out-of-band pour topbar, sidebar desktop, sidebar mobile et bottom nav mobile afin de garder titre, active state et actions de contexte synchronisés ;
- indicateur discret sur `#main-content` pendant la requête ;
- les liens d'Espace, d'opérations, de plateformes et les formulaires restent en navigation HTML complète.

Premières routes candidates :

- `/me/` ;
- `/me/journeys/` ;
- `/me/accesses/` ;
- `/me/history/` ;
- `/account/profile/` depuis le menu compte ou une carte d'activation ;
- `/conversations/` seulement comme surface d'attention/contextuelle.

## Accueil mature

`/me/` doit rester privé, contextuel et orienté accomplissement.

Structure cible :

1. **Maintenant** — une action prioritaire ou `Tout est en ordre. ✓`.
2. **Ensuite** — peu d'éléments, ordonnés par utilité réelle.
3. **Prêt / pas prêt** — projection dérivée quand disponible.
4. **Retrouver** — raccourcis utiles, sans recréer un catalogue.

Accueil ne devient pas un feed. Discover reste l'espace exploratoire.

## Non-objectifs

- Pas de migration React/Vue/SPA complète par réflexe.
- Pas de feed, like, popularité ou watch-time.
- Pas de nouveau modèle persistant pour la navigation.
- Pas de contournement des permissions serveur.
- Pas de duplication de vérités métier dans l'UI.

## Critères d'acceptation pour le premier slice

- `Profil` n'apparaît plus comme lien primaire permanent dans la sidebar personnelle.
- `Conversations` n'apparaît plus comme lien primaire permanent dans la sidebar personnelle ni dans la bottom nav mobile.
- `Découvrir` devient une destination primaire explicite et conserve sa carte d'appel en bas de sidebar.
- Le menu utilisateur garde l'accès au Profil.
- La topbar garde l'accès Conversation seulement comme action d'attention.
- Les routes personnelles stables peuvent utiliser le shell progressif htmx avec fallback HTML complet.
- Les tests existants restent verts.

## Suite

Le prochain slice doit traiter la finition visuelle et comportementale après validation bêta : perception mobile/tablette, polish de `/me/`, tests E2E de back/forward htmx si les gates actuels valident le contrat, et audit no-JS/accessibilité.
