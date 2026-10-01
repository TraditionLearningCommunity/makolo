# Makolo — socle transversal de lecture et de performance

**Statut :** pattern d’architecture transversal à valider par CI et adoption représentative.  
**Portée :** Django HTML, HTMX, API, clients mobiles et futurs clients.  
**Hors portée :** ranking, recommandation, pertinence, sélection Molongo, nouvelle vérité métier, APM externe, Redis/Celery, refonte UX/CSS.

## 1. Principe

Le chemin de lecture attendu est :

```text
vérités métier canoniques
        ↓
selectors
        ↓
read models / projections partagées
        ↓
batching + query planning + budgets
        ↓
présentation spécifique
    ↙       ↓        ↘
  Web      API      Mobile
```

Presentation représente les faits ; elle ne les possède pas. Un read model transporte et compose des résultats déjà ordonnés par leurs owners. Il ne devient jamais un moteur de ranking ou de décision.

## 2. Contexte request-scoped

`request.makolo` est un contexte HTTP éphémère créé par `MakoloRequestContextMiddleware`.

Il peut contenir uniquement :

- `observed_at`, commun aux calculs d’une même requête ;
- un `request_id` borné et non sensible ;
- la `SurfaceContext` dérivée de la route et des headers HTMX ;
- une memoization strictement limitée à la requête.

Il ne contient pas de copie de `request.user`, de Journey, Activity, Readiness, Permission, Mandate ou autre vérité métier.

La memoization request-scoped est le niveau L1. Elle n’a pas d’invalidation à gérer : elle disparaît avec la requête.

## 3. Surface / shell policy

`SurfaceContext` déclare les capacités réellement nécessaires au shell.

Exemples actuels :

- `notifications` et `conversation_attention` ne sont demandées que sur la surface primaire Maintenant où les badges sont rendus ;
- `profile_activation` reste disponible pour le menu compte authentifié ;
- les surfaces Space déclarent `space_navigation` et `space_authority`.

La policy ne décide jamais d’une Permission. Elle décide seulement si Presentation doit demander au domaine propriétaire de résoudre une information.

## 4. ProjectionBudget

`ProjectionBudget` limite le nombre d’éléments qu’une projection composite peut encore exposer.

Invariant :

> Une famille qui ne peut plus atteindre la réponse ne doit pas être chargée pour produire des cartes invisibles.

Le budget ne trie pas, ne score pas et ne choisit pas « les meilleurs » éléments. Il conserve l’ordre fourni par chaque owner et arrête simplement la composition lorsque la limite de réponse est atteinte.

## 5. Read model partagé — En cours

`core.read_models.personal_ongoing.build_personal_ongoing_read_model()` est le premier contrat partagé entre Web et API.

Il :

- conserve l’ordre de familles existant ;
- borne chaque requête au nombre de places restantes ;
- utilise `resolve_many(...)` pour Journey ;
- batch la Readiness des Dossiers ;
- ne charge pas les familles suivantes lorsque le budget est plein ;
- transporte les objets canoniques + projections dérivées nécessaires aux presenters.

Le Web produit ses cartes HTML. L’API conserve son contrat JSON `personal.ongoing`. Le mobile continue à consommer l’API : il ne dépend pas de Django Templates et aucun contrat mobile n’est élargi arbitrairement.

La famille Funding reste explicitement Web-only dans ce read model tant qu’elle ne fait pas partie du contrat réseau `personal.ongoing`.

## 6. Shell global

### Notifications

Le compteur unread est résolu une seule fois par requête et seulement sur la surface qui l’affiche. La navbar consomme la valeur du context processor ; elle ne lance plus un second `COUNT` via template tag.

### Activation du Profil

La projection d’activation est memoized par requête. Un `UserProfile` manquant est représenté en mémoire sur GET ; il n’est plus créé pour rendre une page.

Les écrans de préférences suivent la même règle : les extensions absentes peuvent être représentées par une instance non persistée sur GET et ne sont créées qu’au moment d’une mutation valide.

### Conversation Attention

Le shell ne calcule Conversation Attention que sur Maintenant.

Le badge shell est volontairement borné à `9+` : il n’a pas besoin de connaître un total exact arbitrairement grand. Le calcul :

- borne le nombre de Points candidats ;
- précharge en batch les réponses actives et états utilisateur du Profil ;
- met en cache, pour le batch courant, la visibilité Conversation et l’appartenance aux AudienceSets déjà résolues ;
- conserve les contrôles canoniques d’audience et d’autorité.

Aucune audience dérivée n’est persistée comme autorité.

## 7. Space

`SpaceConsoleContext` reste propriétaire de la projection de console.

Le switcher Space résout désormais en une fois les IDs disposant d’un Mandate de portée Space, puis les réutilise pour les items du switcher. Un Mandate Activity peut rendre un Space visible dans un contexte limité, mais ne devient jamais une autorité Space.

Invariant inchangé :

```text
Assignment = responsabilité
Mandate / Permission = autorité
Membership / Group / Team != autorité
```

## 8. HTMX

`is_fragment_request()` distingue explicitement les requêtes HTMX et leur target.

`FragmentTemplateMixin` permet à une surface d’utiliser un vrai template serveur de fragment. La première adoption est `/me/ongoing/`.

Le fragment rend uniquement les parties requises par le contrat HTMX actuel :

- `#main-content` ;
- topbar/sidebar/navigation mobile nécessaires aux swaps OOB.

Il ne reconstruit pas le document, le `<head>`, le footer, la command palette ni les assets globaux.

Toute surface fragmentable renvoie :

```http
Vary: HX-Request, HX-Target
```

pour empêcher la confusion cache full/fragment.

Full et fragment consomment le même read model ; il n’existe pas de deuxième logique métier HTMX.

## 9. Assets par capacité

Le bundle principal conserve HTMX, Alpine, le runtime de workspace et le desktop shell.

Le runtime Sharing n’est plus chargé directement sur toutes les pages. `capability-loader.js` détecte `data-makolo-share` au chargement initial et après `htmx:afterSettle`, puis charge `share-actions.js` seulement lorsque nécessaire.

`share-actions.js` est idempotent grâce à un `WeakSet` : un swap HTMX ne réattache pas les listeners aux contrôles déjà initialisés.

Lucide n’est plus rescanné à la fois sur `afterSwap` et `afterSettle`, ni une seconde fois via `alpine:initialized`. Le contrat retenu est :

- un scan initial à `DOMContentLoaded` ;
- un scan après `htmx:afterSettle`.

## 10. Observabilité

`PerformanceEnvelopeMiddleware` est opt-in via :

- `MAKOLO_PERFORMANCE_LOGGING` ;
- `MAKOLO_PERFORMANCE_WARN_MS` ;
- `MAKOLO_PERFORMANCE_WARN_QUERIES` ;
- `MAKOLO_PERFORMANCE_WARN_KB`.

Quand activé, il logge seulement :

- route Django ;
- méthode ;
- statut ;
- durée totale ;
- nombre de requêtes SQL ;
- temps SQL approximatif ;
- taille de réponse ;
- mode full/fragment ;
- request ID borné.

Il ne logge ni query SQL, ni payload, ni token, ni credential, ni PII.

Les seuils à `0` sont désactivés. Ils doivent être calibrés à partir de mesures réelles d’environnement, pas inventés dans le code.

## 11. Hiérarchie de cache

Le socle distingue :

- **L0** : objets ORM déjà chargés / `select_related` / `prefetch_related` ;
- **L1** : request memoization ;
- **L2** : Django cache partagé court ;
- **L3** : cache HTTP / validators ;
- **L4** : statics fingerprintés WhiteNoise.

Cette étape implémente L0/L1 et la correction HTTP `Vary`.

Elle n’ajoute volontairement pas de L2 partagé : aucun contrat d’invalidation suffisamment général n’est démontré pour Permissions, Mandates, Access ou projections personnelles sensibles.

Elle n’ajoute pas d’ETag `304` aux racines mobiles personnelles dans cette étape : le client mobile courant ne persiste pas encore de validator HTTP et `generated_at` est généré à chaque projection. Ajouter un ETag maintenant ferait surtout recalculer la réponse avant de rendre `304`, sans supprimer le coût serveur et en introduisant un contrat réseau non consommé.

Un futur ETag/Last-Modified doit partir d’un owner/version token stable et privacy-safe, puis être ajouté avec un test client de conditional request.

Aucun Redis/provider externe n’est requis par ce pattern.

## 12. GET read-only

Une lecture de présentation ne doit pas créer silencieusement une extension Profile ou NotificationPreference.

Les mutations explicites peuvent créer l’extension manquante lorsqu’un formulaire/serializer valide est sauvegardé.

Les GET qui représentent eux-mêmes une action utilisateur explicite et historiquement contractuelle (par exemple ouvrir une notification qui la marque lue) doivent être traités séparément ; ils ne sont pas reclassés silencieusement par ce chantier.

## 13. Tests de performance

Les tests doivent privilégier deux contrats :

### Croissance bornée

Comparer une petite collection à une collection significativement plus grande et autoriser seulement une petite constante.

Adoptions initiales :

- `personal.ongoing` API ;
- `/me/ongoing/` Web ;
- Conversation Attention sur plusieurs Points partageant Conversation/Audience ;
- switcher Space avec plusieurs Espaces autorisés.

### Budget absolu

Un budget absolu n’est ajouté qu’après mesure stable sur une surface critique. Aucun nombre arbitraire n’est utilisé comme gate.

## 14. Frontière Molongo

Ce socle ne définit aucune formule de :

- pertinence ;
- ranking ;
- recommandation ;
- priorité ;
- sélection ;
- intelligence ;
- « meilleur élément ».

`ProjectionBudget` borne le coût. Les read models transportent les résultats. Les futurs algorithmes Molongo peuvent se brancher en amont des read models, à condition de respecter les owners et contrats canoniques, sans refaire l’infrastructure Web/API/mobile.

## 15. Ce qui est volontairement refusé

Dans cette étape :

- aucune nouvelle table ;
- aucune migration ;
- aucun index spéculatif ;
- aucune projection persistée ;
- aucun Redis ;
- aucun Celery ajouté pour masquer une lecture coûteuse ;
- aucune refonte CSS/UX ;
- aucun backend mobile parallèle ;
- aucune duplication de Permission/Mandate/Readiness ;
- aucune logique Molongo.

Le chemin rapide doit rester le chemin normal, mais toujours à partir des vérités canoniques.
