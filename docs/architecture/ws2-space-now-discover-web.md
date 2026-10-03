# WS2 — Space Maintenant & Découvrir Web

**Statut :** branche WS2 réconciliée, candidate à intégration.  
**Base initiale auditée :** `main@f3a7cf94514c94d65198b286bcf33e1cbe470697`.  
**Base finale réconciliée :** `main@1eb8e7969528945739e5f70c9cd51ff1e8d17b0e` après intégration de WS5 (#430) et MY5 (#425).  
**Branche finale :** `ws2-space-now-discover-web-final`.  
**Frontière :** Web Space `Maintenant` et `Découvrir` uniquement.

## 1. Problème utilisateur

WS2 doit permettre à une personne autorisée agissant pour un Space de répondre honnêtement à deux questions :

- **Maintenant** — « Qu’est-ce qui mérite notre attention maintenant ? »
- **Découvrir** — « Qu’est-ce qui pourrait nous aider à avancer ? »

La présentation ne doit jamais fabriquer une sélection que le serveur ne possède pas.

## 2. Audit de départ

Le `main` audité contient déjà WS1 intégré via PR #421 ainsi que son closeout via PR #424.

Le shell Space Web existe donc déjà et fournit :

- `/spaces/<slug>/` comme racine Maintenant ;
- `/spaces/<slug>/discover/` ;
- le contexte Space ;
- la navigation primaire Space ;
- la responsabilité de lecture via query parameter `responsibility` ;
- le responsive Compact / Adaptive / Expanded ;
- la progressive enhancement HTMX.

Au moment du branchement WS2 :

- aucune branche WS3, WS4 ou WS5 n’est présente ;
- les PR ouvertes pertinentes sont mobiles et ne touchent pas ces surfaces Web Space ;
- WS2 consomme donc le shell WS1 réel au lieu d’en créer un second.

## 3. Contrat ZS2 réellement observé

Les builders et APIs courants sont :

~~~text
build_space_now_projection(...)
build_space_discover_projection(...)

GET /api/v1/organizations/workspaces/<slug>/now/
GET /api/v1/organizations/workspaces/<slug>/discover/
~~~

Le runtime retourne actuellement :

~~~json
{
  "selection": {
    "state": "unavailable",
    "reason": "no_safe_selection_contract"
  },
  "items": [],
  "has_more": false
}
~~~

Cette réponse signifie :

~~~text
items = []
→ collection vide pour cette projection

selection.state = unavailable
→ aucun mécanisme de sélection suffisamment sûr n’est disponible
~~~

Elle ne signifie pas :

- permission refusée ;
- absence générale de données métier ;
- absence définitive de possibilités ;
- « Tout est en ordre ».

WS2 ne modifie pas cette vérité.

## 4. Architecture Web retenue

La chaîne reste :

~~~text
owner / autorité
→ projection ZS
→ composition de présentation WS2
→ Django template
~~~

Le Web appelle directement les builders ZS existants. Aucun appel HTTP interne vers la propre API Django n’est ajouté.

WS2 ajoute seulement une petite composition de présentation :

~~~text
projection ZS
→ content | empty | unavailable | partial | error
~~~

Cette composition ne calcule ni priorité, ni pertinence, ni ranking, ni recommandation.

## 5. Maintenant

### 5.1. Rôle

Maintenant reste une surface d’attention à faible densité.

WS2 n’y injecte aucun :

- Payment ;
- Capacity ;
- Request ;
- Notification ;
- Conversation ;
- incident ;
- Analytics ;
- Automation ;
- compteur ;
- échéance ;
- score ;
- heuristique frontend.

### 5.2. États

- `unavailable` : « La sélection n’est pas encore disponible. »
- `empty` : « Tout est en ordre. ✓ » uniquement si le serveur indique réellement un empty connu.
- `content` : réservé à une sélection serveur réelle.
- `partial` : conserve les éléments reçus sans compléter ce qui manque.
- `error` : surface récupérable ; le contexte Space est conservé et l’échec n’est pas déguisé en empty.

Le reason technique `no_safe_selection_contract` reste hors de l’interface primaire.

## 6. Découvrir

Découvrir reste une surface collective de possibilités.

WS2 ne réutilise pas silencieusement :

- Discover personnel ;
- tendances ;
- popularité ;
- récence ;
- suggestions statiques ;
- Funding/Partners/Activities injectés manuellement ;
- algorithme Molongo ;
- moteur IA.

Le runtime actuel ne possède pas encore de sélection collective sûre. La surface représente donc honnêtement `unavailable`.

Aucun champ de recherche ou filtre décoratif n’est ajouté tant qu’un contrat collectif réel ne les supporte pas.

## 7. Responsabilité

WS1 avait déjà propagé la responsabilité dans les URLs Web.

WS2 ferme la couture de consommation sur Découvrir :

~~~text
responsibility
→ validation serveur courante
→ projection Maintenant / Découvrir
~~~

La responsabilité reste un filtre de lecture.

~~~text
Responsibility != authority
~~~

Une responsabilité étrangère, révoquée ou invalide ne tombe jamais silencieusement sur `all`.

## 8. Sécurité

Les garanties WS1 / ZS restent intactes :

- visiteur → authentification ;
- outsider → 404 privacy-safe ;
- TeamMembership seul → aucune autorité Space ;
- Platform authority seule → aucune autorité Space ;
- Activity-scoped Mandate → contexte Space borné ;
- responsabilité invalide → 404 ;
- aucune Permission/Mandate brute inutile dans le template ;
- aucun credential, token, QR sensible, secret ou donnée étrangère privée.

Le template n’est jamais une barrière de sécurité.

## 9. Behavior

WS2 applique le contrat Behavior Makolo :

~~~text
Comprendre
→ Agir
→ Recevoir du feedback
→ Récupérer
→ Terminer
~~~

Principes appliqués :

- URLs normales ;
- deep links ;
- back/forward ;
- refresh ;
- contexte Space conservé ;
- responsabilité conservée dans la navigation ;
- erreur récupérable ;
- pas de flash artificiel ;
- aucune persistance de loading/empty/unavailable ;
- aucune fausse réussite.

Le Web ne simule pas le local-first Flutter.

## 10. Responsive et accessibilité

WS2 réutilise les trois régimes W / WS1 :

~~~text
Compact  < 768 px
Adaptive 768–1199 px
Expanded >= 1200 px
~~~

Aucun second shell responsive n’est créé.

La couverture E2E ciblée vérifie 400, 800, 1199, 1200 et 1440 px, les URLs directes, l’absence d’overflow horizontal et l’historique navigateur.

Les états utilisent du texte explicite et ne dépendent pas de la couleur seule.

## 11. Performance

WS2 ajoute :

- aucun polling ;
- aucun cache ;
- aucun appel API par carte ;
- aucun préchargement massif ;
- aucun chargement de tout le Space ;
- aucune duplication JSON + HTML obligatoire ;
- aucun ranking JavaScript.

`has_more` reste une vérité du serveur. Le runtime courant vaut `false`.

## 12. Persistance et migrations

WS2 ajoute :

- **aucun modèle** ;
- **aucune migration** ;
- **aucun état UX persistant**.

La responsabilité reste URL-scoped.

## 13. Tests propriétaires WS2

Tests Django ciblés :

- runtime actuel `unavailable` ;
- distinction `empty / unavailable / partial / error` ;
- absence de raw reason technique dans l’UI ;
- responsabilité valide Web + API ;
- responsabilité invalide privacy-safe ;
- visiteur ;
- outsider ;
- TeamMembership seul ;
- Platform-only ;
- erreur projection → 503 récupérable ;
- absence de matériau sensible ;
- absence de réutilisation du Discover personnel.

E2E ciblé :

- Maintenant et Découvrir aux largeurs 400 / 800 / 1199 / 1200 / 1440 ;
- absence d’overflow ;
- direct URL ;
- back / forward ;
- état `unavailable` correctement rendu.

Le cas `content` n’est pas fabriqué : le runtime actuel ne sait produire aucun item réel pour ZS2.

## 14. Non-objectifs

WS2 ne possède pas :

- shell global final → WS1 / WS6 ;
- Métier / archetypes → WS3 ;
- Nous / Relations / Pilotage → WS4 ;
- Jour J / Live / Scanner / Mark complet → WS5 ;
- Platform ;
- Flutter ;
- Molongo ;
- nouveau moteur de sélection ;
- nouvelle vérité métier.

## 15. Zones de collision potentielles

Fichiers centraux touchés :

- `organizations/api/space_attention_projection.py` ;
- `organizations/api/space_attention_views.py` ;
- `organizations/space_web_views.py`.

Templates propriétaires WS2 :

- `templates/organizations/space/now.html` ;
- `templates/organizations/space/discover.html`.

Tests propriétaires :

- `organizations/test_ws2_space_now_discover_web.py` ;
- `e2e/specs/ws2-space-now-discover.spec.mjs`.

WS2 ne modifie pas le shell global, la navbar, la sidebar centrale, le Makolo Mark global ni les templates WS3–WS5.

## 16. Handoff vers WS6

### WS2 possède

- composition Web Space Maintenant ;
- composition Web Space Découvrir ;
- distinction `empty/unavailable/error` ;
- consommation responsabilité pour ces deux projections ;
- templates et tests associés.

### WS2 ne possède pas

- navigation globale ;
- Métier ;
- Nous ;
- Relations ;
- Pilotage ;
- Jour J ;
- Live ;
- Scanner ;
- orchestration Mark complète.

### Décisions à préserver

1. `unavailable` ne devient jamais `empty`.
2. « Tout est en ordre. ✓ » n’apparaît que sur un empty connu.
3. Découvrir ne reprend jamais le Discover personnel par défaut.
4. Aucune sélection/ranking n’est calculé côté Web.
5. Responsibility reste un filtre de lecture et doit être revalidée.
6. Une panne reste une panne ; elle n’est pas rendue comme absence de contenu.
7. Aucun contenu n’est ajouté seulement pour remplir l’écran.

## 17. Gates de fermeture

Avant merge :

- tests WS2 ciblés ;
- tests ZS6 attention concernés ;
- tests WS1 Space foundation pertinents ;
- `python manage.py check` ;
- `python manage.py makemigrations --check --dry-run` ;
- frontend artifact / E2E réellement imposés par la CI ;
- réconciliation avec le `main` courant ;
- CI GitHub verte.

Aucun test ne doit être affaibli pour obtenir du vert.

## 18. Règle finale

> **Maintenant sélectionne ce qui mérite l’attention ; il ne liste pas tout ce qui existe.**

> **Découvrir ouvre ce qui pourrait nous aider à avancer ; il ne devient pas un feed.**

> **Le silence est une fonctionnalité.**

> **Makolo marche pour vous.**
