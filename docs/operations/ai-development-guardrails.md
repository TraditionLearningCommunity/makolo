# Makolo — Garde-fous de développement assisté par IA

**Statut :** contrat transversal de qualité pour humains et agents IA  
**Portée :** backend Django, web, desktop, mobile Flutter, API, données, migrations, tests, documentation et UX  
**Dépôt :** `TraditionLearningCommunity/makolo`

Ce document complète `AGENTS.md`, les contrats d’architecture, les contrats UX et `docs/operations/agent-orchestration.md`. Il ne remplace aucune vérité métier canonique.

---

## 1. Principe directeur : production-first

Sauf si la tâche dit explicitement `prototype`, `spike`, `exploration`, `proof of concept` ou `maquette jetable`, tout travail demandé est considéré comme **destiné à rester dans le produit**.

> Une petite tranche verticalement complète vaut mieux qu’une grande couche horizontale laissée à moitié intégrée.

> Incrémental ne veut pas dire provisoire.

Le rôle d’un agent n’est pas de produire beaucoup de code. Il est de laisser Makolo dans un état meilleur, cohérent, réellement utilisable et maintenable.

Avant de déclarer une tranche terminée, poser la question :

> **Si personne ne revient sur cette zone pendant six mois, peut-elle rester telle quelle ?**

Si la réponse est non parce qu’il faudra encore connecter l’API, remplacer un fake, traiter les permissions, gérer les erreurs, sécuriser le serveur ou corriger un comportement normal, le périmètre n’est pas terminé.

---

## 2. Le happy path ne suffit pas

Selon le domaine touché, vérifier explicitement les états et transitions pertinents :

- `loading`, `content`, `empty`, `success`, `error` ;
- offline, synchronisation, fraîcheur, conflit et reprise ;
- permission refusée et autorité serveur ;
- session expirée ;
- double soumission, retry, idempotence et concurrence ;
- données absentes, inconnues, périmées ou contradictoires ;
- retour arrière, refresh, deep link et reprise après fermeture ;
- interruption ou annulation d’une action OS ;
- compatibilité avec les données valides existantes.

Tous ces cas ne s’appliquent pas à chaque changement. L’agent doit déterminer ceux qui comptent au lieu de les ignorer par défaut.

---

## 3. Pas de dette cachée présentée comme “done”

### TODO

Un `TODO` n’est acceptable que s’il est explicitement hors périmètre, légitime, traçable et non nécessaire au fonctionnement normal de la tranche.

Ne pas fermer une tâche avec des TODO du type :

```text
TODO: integrate API later
TODO: add permission checks
TODO: handle errors
TODO: replace mock
```

si ces éléments appartiennent au périmètre demandé.

### Mocks, fakes et placeholders

Ne pas remplacer une intégration disponible par un fake seulement parce qu’il permet de montrer rapidement l’écran.

Un fake de test est distinct d’un fake de produit.

Les données de démonstration doivent rester identifiables et séparées des données réelles.

### Pas de scaffolding spéculatif

Ne pas ajouter un provider, hook, modèle, table, abstraction, service, composant générique ou couche “pour plus tard” sans besoin actuel démontré.

---

## 4. Domain-first : une vérité a un propriétaire

Avant de créer un état, un modèle, une colonne, une propriété client ou un calcul, identifier le domaine propriétaire.

Ne pas recréer côté client ou Presentation une seconde version de :

- Readiness ;
- Access ;
- Permission ;
- Mandate ;
- Capacity ;
- Journey ;
- Requirement ;
- Proof ;
- Payment ;
- ou toute autre vérité métier canonique.

Le client peut représenter, mettre en cache ou projeter une vérité. Il ne doit pas devenir un propriétaire concurrent.

Avant d’ajouter un état persistant, vérifier si le besoin appartient plutôt à :

- un selector ;
- un read model ;
- une projection ;
- un DTO ;
- un view model ;
- un service d’orchestration ;
- Presentation ;
- Analytics ;
- Domain Events.

Être utile à un écran ne donne pas automatiquement une existence métier persistante.

---

## 5. Pas de “god status”

Éviter les enums ou champs `status` qui condensent artificiellement plusieurs dimensions indépendantes : progression, autorité, préparation, disponibilité, paiement, expiration, conflit, erreur et blocage.

Un état unique n’est justifié que lorsqu’il correspond réellement à une machine d’état propriétaire du domaine.

Respecter les distinctions :

```text
absent != inconnu != faux != vide != zéro != non applicable != périmé
```

De même :

```text
état actuel != historique != événement != observation != projection
```

---

## 6. Ne pas inventer le produit

Un pattern populaire n’est pas automatiquement une fonctionnalité Makolo.

Ne pas ajouter implicitement pour “faire moderne” :

- likes ;
- followers ;
- commentaires ;
- tendances ;
- streaks ;
- badges ;
- notation ;
- popularité ;
- feed générique ;
- recommandations ;
- partage ;
- favoris ;
- statistiques ou compteurs non demandés.

Toute action visible doit avoir une justification produit, un propriétaire et un comportement réel.

Makolo ne doit pas dériver silencieusement vers un réseau social générique, une marketplace, un task manager ou un dashboard simplement parce que ces patterns sont familiers.

---

## 7. Pas de données décoratives ou inventées

Ne pas inventer pour remplir l’interface :

- pourcentages ;
- compteurs ;
- prix ;
- dates ;
- avatars ;
- classements ;
- “personnes intéressées” ;
- progression ;
- recommandations ;
- métriques ;
- badges.

Une donnée affichée doit provenir d’une vérité réelle, d’une projection définie ou d’une donnée de démonstration explicitement isolée.

Pas de `78% ready` si aucun contrat ne produit réellement cette valeur.

---

## 8. Contenu textuel : ne pas écrire comme un prototype commenté

L’IA a tendance à expliquer l’interface qu’elle vient de produire : titres longs, sous-titres permanents, paragraphes d’aide, cartes qui décrivent leur fonction, répétitions et formulations de démonstration.

Makolo doit éviter cette apparence de prototype ou d’onboarding permanent.

> **Makolo parle lorsqu’il a quelque chose d’utile à dire.**

Le texte doit principalement aider à :

- agir ;
- décider ;
- comprendre une conséquence ;
- récupérer d’un problème.

Éviter les formulations réflexives :

```text
Cette section vous permet de...
Ici vous pouvez...
Cette fonctionnalité sert à...
```

lorsque la structure de l’écran suffit.

Avant d’ajouter un paragraphe, vérifier si le problème peut être résolu par :

- un titre plus précis ;
- un label ;
- un meilleur regroupement ;
- une hiérarchie visuelle ;
- un état clair ;
- un CTA adapté.

Les explications longues sont légitimes notamment pour le consentement, les permissions sensibles, le paiement, les conflits, les données potentiellement obsolètes avant une action importante, une action irréversible ou la récupération après erreur.

Test de suppression :

> **Si je supprime ce texte, l’utilisateur comprend-il encore quoi faire, ce qui se passe et les conséquences importantes ?**

Si oui, le texte est probablement superflu.

Préférer des CTA courts et humains : `Continuer`, `Réserver`, `Ajouter`, `Vérifier`, `Réessayer`, `Envoyer`.

---

## 9. Design : production, pas “Dribbble”

Élégance ne signifie pas décoration.

Ne pas rendre une surface “professionnelle” par accumulation de :

- gradients ;
- cartes géantes ;
- ombres ;
- coins excessivement arrondis ;
- illustrations décoratives ;
- textes géants ;
- animations gratuites ;
- espaces vides qui réduisent inutilement la densité.

La densité doit correspondre au travail réel.

Le mobile, le desktop et le web ne doivent pas être la même maquette simplement étirée ou réduite. La fonction métier reste cohérente, mais la composition doit respecter le contexte d’usage.

---

## 10. Design System : ni catalogue théorique, ni réinvention locale

Ne pas créer des dizaines de composants “au cas où” avant d’avoir observé les vrais motifs du produit.

Inversement, ne pas redessiner localement un bouton, un état d’erreur, une carte ou un formulaire si un pattern canonique existe déjà.

> Le Design System normalise les motifs réellement récurrents.

Avant d’introduire un nouveau pattern visuel ou comportemental, rechercher ce qui existe déjà.

---

## 11. Une application est un système d’interactions, pas une capture d’écran

Une UI visuellement correcte n’est pas terminée si les comportements réels sont faux ou absents.

Selon la plateforme, considérer :

- scroll ;
- focus ;
- clavier ;
- sélection ;
- retour système Android ;
- conventions iOS ;
- deep links ;
- resize desktop ;
- hover ;
- raccourcis ;
- orientation ;
- permission OS refusée ;
- caméra interrompue ;
- picker annulé ;
- cycle de vie ;
- reprise après arrière-plan.

Le comportement doit être professionnel, pas seulement le rendu.

---

## 12. Composants et responsabilités

Éviter les composants “intelligents” qui finissent par charger les données, vérifier les permissions, calculer un statut, muter le domaine, naviguer, afficher les erreurs et gérer le cache.

Les composants de présentation ne doivent pas absorber silencieusement l’orchestration métier.

Inversement, éviter les fichiers monolithiques géants.

Découper par responsabilité stable, pas arbitrairement par nombre de lignes.

---

## 13. Abstraction : éviter les deux extrêmes

### Sur-abstraction

Ne pas créer une chaîne de `BaseRepository`, `AbstractRepository`, `Adapter`, `Facade` et factories pour trois méthodes si le produit ne l’exige pas.

> Généraliser après avoir observé une répétition réelle, pas en prévision d’une répétition hypothétique.

### Copier-coller

Ne pas dupliquer plusieurs fois le même comportement légèrement modifié lorsque le concept existe déjà.

Avant de créer une nouvelle structure, rechercher si le composant, service, selector, convention ou domaine existe.

---

## 14. Dépendances : chaque package a un coût

Avant d’ajouter une dépendance, vérifier si le besoin est déjà couvert par :

- Flutter/Dart ;
- Python/Django ;
- la plateforme ;
- ou une dépendance déjà présente.

Une dépendance ajoute maintenance, compatibilité, surface de sécurité, poids et dette de migration.

Pour le frontend web, respecter également les règles de versions, CSP et build définies dans les docs canoniques.

---

## 15. Local-first : pas de faux succès

Une action n’est pas “confirmée” simplement parce qu’elle est écrite localement ou placée dans une outbox.

Distinguer selon le contrat réel :

- enregistré sur cet appareil ;
- en attente de synchronisation ;
- synchronisé ;
- en attente de confirmation ;
- confirmé ;
- conflit ;
- échec.

Ne jamais afficher un niveau de certitude supérieur à celui réellement acquis.

L’inverse compte aussi : offline ne signifie pas automatiquement inutilisable si les données et actions nécessaires existent localement.

Le client ne doit pas devenir un mini-serveur Makolo.

---

## 16. Cache et calculs : pas de deuxième base de vérité

Un cache accélère une vérité ; il ne doit pas devenir une nouvelle vérité.

Éviter que certains chemins lisent une source et d’autres une copie divergente sans règle de cohérence explicite.

De même, ne pas recalculer côté Flutter, web et backend la même règle métier canonique si elle possède déjà un propriétaire.

---

## 17. Erreurs : ni silence, ni fuite technique

Ne pas avaler les erreurs :

```text
try { ... } catch (_) {}
```

Une erreur doit être gérée, propagée, observée ou transformée.

Ne pas exposer directement à l’utilisateur des détails techniques tels que stack traces, exceptions de librairie ou messages internes.

Distinguer :

- diagnostic développeur ;
- observabilité ;
- message utilisateur.

Un fallback n’est correct que si l’état de repli est réellement valide. Ne pas utiliser `?? "Unknown"` partout pour masquer une incohérence.

---

## 18. Sécurité : l’UI n’est pas une barrière d’autorisation

Masquer un bouton n’est pas un contrôle de sécurité.

Permission, Mandate, Access et autres décisions sensibles doivent être vérifiés côté autoritatif.

Considérer les risques IDOR et divulgation minimale.

Ne pas surcollecter “au cas où” dans :

- logs ;
- analytics ;
- caches ;
- payloads ;
- traces.

Ne jamais logger secrets, tokens, mots de passe, AccessCredentials complets, QR complets ou PII inutile.

---

## 19. Concurrence, retry et idempotence ne sont pas un futur “hardening”

Lorsqu’un domaine peut subir :

- double clic ;
- retry réseau ;
- plusieurs appareils ;
- plusieurs acteurs ;
- dernière place ;
- allocation partagée ;
- réservation ;
- Access ;
- Payment ;

la concurrence et l’idempotence appartiennent au contrat de la fonctionnalité.

Un scénario séquentiel de démonstration n’est pas une preuve de correction.

---

## 20. Tests : protéger le contrat, pas justifier l’implémentation

Les tests doivent prioritairement protéger :

- invariants ;
- comportements observables ;
- permissions/IDOR ;
- régressions ;
- cas limites ;
- concurrence/idempotence quand pertinentes ;
- compatibilité des données existantes.

Éviter les tests circulaires qui valident uniquement la structure interne choisie aujourd’hui.

Un test existant est une contrainte à comprendre avant de le modifier.

Ne jamais supprimer, contourner ou affaiblir un test uniquement pour obtenir du vert.

---

## 21. Migrations et données existantes

Une migration qui “passe” techniquement n’est pas forcément correcte sémantiquement.

Éviter :

- `nullable` partout comme échappatoire ;
- defaults artificiels ;
- backfills inventés ;
- valeurs sentinelles ambiguës ;
- nouveau champ `status` seulement pour simplifier une vue ;
- transformation destructive sans stratégie claire.

Les anciennes données valides doivent conserver leur signification.

Ne pas backfiller artificiellement un état historique si l’absence de la nouvelle information reste un état valide.

---

## 22. Accessibilité, i18n et plateforme dès la conception

Ne pas traiter plus tard ce qui structure déjà les composants.

Prendre en compte :

- focus et navigation clavier ;
- semantics/accessibility labels ;
- tailles de texte augmentées ;
- contraste ;
- Reduce Motion ;
- lecteurs d’écran lorsque pertinent ;
- localisation future des chaînes visibles ;
- conventions propres à Android, iOS, web et desktop.

L’identité Makolo reste commune, mais elle ne doit pas nier la plateforme hôte.

---

## 23. Commentaires et documentation

Éviter les commentaires qui paraphrasent le code :

```python
# Check if user exists
if user:
    ...
```

Un commentaire est utile s’il documente :

- un invariant ;
- une raison non évidente ;
- une contrainte externe ;
- une décision architecturale ;
- un workaround traçable ;
- un risque subtil de régression.

La documentation doit décrire des contrats durables, pas raconter étape par étape comment l’agent a produit le code.

---

## 24. Performance : ne pas laisser une simplicité locale créer un coût global

Une solution localement simple peut produire :

- N+1 ;
- appels réseau par composant ;
- rebuilds inutiles ;
- téléchargements répétés ;
- assets trop lourds ;
- packages globaux inutiles ;
- calculs dupliqués ;
- synchronisations trop larges.

Ne pas optimiser sans mesure, mais ne pas introduire une architecture manifestement coûteuse sous prétexte que le jeu de données de développement est petit.

---

## 25. Ne pas choisir seulement ce qui est facile à démontrer

Les agents ont tendance à commencer par ce qui donne vite un résultat visible : cartes, animations, skeletons, filtres, landing pages, placeholders.

Pour une capacité importante, identifier d’abord ce qui conditionne réellement sa validité :

- autorité ;
- donnée réelle ;
- conflit ;
- migration ;
- synchronisation ;
- récupération ;
- concurrence ;
- sécurité ;
- contrat serveur.

La partie difficile ne doit pas être systématiquement repoussée sous le nom de “hardening”.

---

## 26. Cohérence du produit dans le temps

Le risque principal peut être l’accumulation de changements localement raisonnables qui finissent par créer :

- plusieurs systèmes d’erreur ;
- plusieurs styles de cartes ;
- plusieurs conventions de formulaires ;
- plusieurs modèles de navigation ;
- plusieurs vérités pour les permissions ;
- plusieurs façons de calculer la même donnée ;
- Home transformée en dashboard générique ;
- Discover transformé en feed ;
- Dossier transformé en task manager.

Avant de créer un nouveau pattern, comparer avec les patterns et contrats existants.

> **La cohérence transversale fait partie de la qualité de chaque PR.**

---

## 27. Auto-revue obligatoire avant fermeture

### Réalité

- Est-ce une implémentation réelle ou une démonstration maquillée ?
- Reste-t-il un mock, placeholder ou TODO nécessaire au comportement normal ?
- Les données affichées existent-elles réellement ou sont-elles explicitement de démonstration ?

### Domaine

- Quel domaine possède chaque vérité modifiée ou affichée ?
- Une deuxième vérité métier a-t-elle été créée ?
- Un état persistant a-t-il été ajouté alors qu’une projection/read model suffisait ?

### UX

- Le happy path et les états non nominaux pertinents sont-ils couverts ?
- L’interface indique-t-elle le niveau réel de confirmation ?
- Le texte aide-t-il l’utilisateur ou commente-t-il l’interface ?
- Y a-t-il du texte supprimable sans perte de compréhension ?
- Le comportement réel de la plateforme est-il couvert ?

### Technique

- Une abstraction ou dépendance a-t-elle été ajoutée sans besoin démontré ?
- Le client recalcule-t-il une vérité déjà propriétaire ailleurs ?
- Un fallback masque-t-il une incohérence ?
- Les erreurs sont-elles réellement gérées ?
- La concurrence/idempotence est-elle couverte quand elle compte ?

### Qualité

- Les tests protègent-ils le contrat réel ?
- Un test a-t-il été modifié simplement pour devenir vert ?
- Les anciennes données valides restent-elles compatibles ?
- Les permissions sensibles sont-elles vérifiées côté autoritatif ?
- Les logs/analytics respectent-ils la divulgation minimale ?

### Produit

- Quelque chose a-t-il été ajouté uniquement parce que “les apps modernes le font” ?
- Le changement renforce-t-il Makolo ou ajoute-t-il du bruit ?
- Si personne ne revient sur cette zone pendant six mois, reste-t-elle acceptable telle quelle ?

Une réponse problématique signifie que la tranche n’est pas fermée ou que son périmètre doit être redéfini explicitement.

---

## 28. Critère de sortie compact

Une tranche est prête lorsqu’elle est :

```text
réelle
+ propriétaire de ses vérités correctement identifié
+ verticalement cohérente
+ autorisée correctement
+ robuste aux états pertinents
+ honnête sur la synchronisation et la certitude
+ testée sur le contrat utile
+ compatible avec les données existantes
+ sobre dans ses dépendances et abstractions
+ mature visuellement et rédactionnellement
+ sans dette cachée nécessaire à son fonctionnement normal
```

---

## 29. Relation avec les autres contrats Makolo

Lire ce document avec :

- `AGENTS.md` — règles d’entrée et invariants essentiels ;
- `docs/operations/agent-orchestration.md` — branches, lanes, collisions, CI et handoff ;
- `docs/architecture/makolo-domain-blueprint.md` — architecture et domaines canoniques ;
- `docs/operations-runbook.md` — exploitation et déploiement ;
- les contrats UX, web et mobile canoniques du périmètre touché.

Le runtime actuel, le code, les migrations et les tests gagnent sur l’historique.

---

## 30. Principe final

> **Ne pas livrer un prototype technique, visuel ou rédactionnel lorsqu’un produit réel a été demandé.**

> **Ne pas déplacer silencieusement vers le développeur humain le travail que l’agent aurait dû terminer dans son périmètre.**

> **Pas le plaisir de produire du code. Le plaisir d’avoir réellement avancé Makolo.**
