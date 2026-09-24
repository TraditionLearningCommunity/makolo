# Z7 — Makolo Mark : orchestration personnelle réelle

> **Statut : intégré.** Z7 a été réconcilié et mergé via #274 ; l'ancienne PR #272 est supersédée. Le runtime courant de `main` reste prioritaire sur ce document.

## Mission

Le Makolo Mark personnel est une porte d'intake et d'orchestration :

> **J'ai quelque chose à donner à Makolo.**

Le Mark comprend seulement ce qui est nécessaire pour retrouver une réalité connue, router une recherche ouverte, préparer ou exécuter une conséquence réellement supportée, ou demander la clarification/confirmation qui bloque encore. Il ne devient propriétaire d'aucune vérité métier.

Le Mark reste strictement personnel : `request.user` est le seul Profile sujet. Aucun `space_id`, rôle, Permission, Mandate ou autre contexte fourni par le client n'accorde d'autorité.

## Contrat API

Route personnelle :

```text
POST /api/v1/me/mark/
```

Entrée v1 :

```json
{
  "input": {
    "kind": "text",
    "value": "Retrouve mon accès"
  },
  "context": {}
}
```

La modalité `text` est la seule modalité générique exposée en Z7. Les futures références de fichier, URL ou autres modalités ne doivent pas être annoncées comme supportées tant qu'un intake propriétaire n'existe pas.

La réponse utilise l'enveloppe Z `meta/data` avec `projection = personal.mark`.

États normaux d'orchestration :

```text
resolved
completed
needs_clarification
needs_confirmation
unknown
unsupported
forbidden
```

Ces états peuvent être des HTTP 200 : ils décrivent une situation métier valide, pas une erreur de transport.

## Sept capacités sémantiques

Les sept capacités restent des responsabilités internes, pas sept endpoints ni sept boutons :

1. **Comprendre** : comprendre suffisamment pour déterminer la prochaine conséquence correcte.
2. **Retrouver** : retrouver une réalité déjà liée, connue ou explicitement désignée.
3. **Réutiliser** : préparer l'usage d'une réalité existante sans conclure à la place du domaine propriétaire qu'elle satisfait une exigence.
4. **Conserver** : remettre au bon owner ce qui mérite de persister ; aucun stockage générique Mark.
5. **Faire avancer** : produire une conséquence via un service propriétaire uniquement.
6. **Faire exister** : matérialiser dans le domaine propriétaire seulement lorsqu'un contrat réel existe.
7. **Continuer pour moi** : délégation bornée, par exemple une Veille Discovery réellement exécutable.

## Search n'est pas Retrieve

`Search` explore un champ ouvert et remet à Découvrir. `Retrieve` vise une réalité déjà personnelle ou explicitement désignée et utilise les selectors propriétaires.

Exemples :

```text
"Trouve une bourse"
→ Discovery

"Retrouve la bourse que j'avais sauvegardée"
→ considérations / Bookmark personnel
```

Le Mark ne crée pas de moteur de recherche, d'index universel, de score de pertinence ou de ranking parallèle.

## Handoffs propriétaires

Z7 réutilise notamment :

- Maintenant : `/api/v1/me/now/`
- En cours : `/api/v1/me/ongoing/`
- Découvrir : `/api/v1/discovery/items/`
- Moi : `/api/v1/me/`
- Journey : `/api/v1/me/journeys/<uuid>/`
- Access : `/api/v1/me/accesses/` et détail personnel
- Historique : `/api/v1/me/history/`
- Jour J : `/api/v1/me/occurrences/<uuid>/day-of/`
- Passport : `/api/v1/me/passport/`
- Personal Assets : `/api/v1/me/resources/`
- Recognition : `/api/v1/recognition/me/`
- Loyalty : `/api/v1/loyalty/me/`
- Partner : projection personnelle existante
- Dossier / Project : APIs Objectives existantes.

Le Mark ne duplique pas leurs détails.

## Clarification et confirmation

Une clarification est demandée uniquement lorsqu'une ambiguïté bloque réellement la suite. Les options sont bornées et privacy-safe ; une cible étrangère n'est jamais sérialisée.

Une confirmation protège une conséquence significative. La confirmation décrit la conséquence humaine et la mutation est ensuite de nouveau validée côté owner.

Z7 démontre ce contrat avec Recognition : une Reward réellement exposée avec capability de redemption produit d'abord `needs_confirmation`, puis l'exécution passe par `recognition.economy.redeem_reward` et sa clé d'idempotence propriétaire.

## Idempotence

Une intention répétée ne doit pas multiplier silencieusement une conséquence.

- Bookmark réutilise l'idempotence du owner Discovery.
- Watch utilise un service Discovery qui sérialise les retries concurrents du même Profile et réutilise une Veille active équivalente.
- Recognition conserve la clé d'idempotence canonique de Redemption.

Le Mark ne crée aucun `MarkAction`, `MarkSession` ou journal de mutation parallèle.

## Privacy et autorité

Le contexte aide à interpréter ; il ne donne jamais d'autorité.

Les cibles Access, Journey, Jour J, Dossier et Project sont toujours résolues par des selectors bornés au Profile personnel. Une cible privée étrangère devient `unknown`/introuvable sans fuite d'existence.

Les entrées Mark sont privées par défaut. Z7 n'ajoute aucun logging de contenu, transcript, thread, mémoire implicite, analytics de contenu ou propagation vers Interest/OpenTo.

## Comprendre n'est pas croire

Une phrase ou un support interprété ne devient jamais automatiquement :

- Proof acceptée ;
- Credential délivrée ;
- Requirement satisfait ;
- Payment réussi ;
- Readiness ;
- vérité de Profile.

De même, posséder un PersonalAsset n'implique pas qu'il satisfasse un Requirement.

## Capacités volontairement non simulées

Z7 retourne honnêtement `unsupported` lorsqu'aucun owner-domain contract stable n'existe.

Exemples au runtime Z7 :

- intake générique de fichier vers PersonalAsset : non exposé par le Mark ;
- création/publication générique d'Activity : non exposée ;
- négociation automatique : inexistante ;
- Payment depuis Mark : non exécuté tant qu'une capability owner explicite n'est pas exposée pour la cible.

Aucun provider IA, LLM, base vectorielle, confidence score ou classifieur universel n'est requis.

## Persistance et migrations

Z7 n'ajoute aucun modèle persistant Mark et aucune migration.

Le code vit dans l'orchestration déterministe, les vues API, les routes, les services propriétaires minimaux, les tests et la documentation.

## Relation avec l'Interpréteur

L'Acteur 3 — Interpréteur Makolo du pipeline d'observation reste un composant distinct. Z7 n'en dépend pas artificiellement. Une intégration future devra passer par un contrat explicite si elle devient utile et stable.

## Critères de fermeture

Z7 est fermé lorsque :

- l'API Mark personnelle est stable et authentifiée ;
- le Web et l'API partagent le même resolver déterministe ;
- Search et Retrieve restent distincts ;
- Bookmark, Watch et Interest restent distincts ;
- ambiguity → clarification ;
- conséquence sensible → confirmation lorsque supportée ;
- les mutations passent par les owners avec leur idempotence ;
- context spoofing n'élargit jamais l'autorité ;
- unsupported est honnête ;
- aucune IA ni persistance Mark n'est requise ;
- tests ciblés, IDOR/privacy et contrôle migrations sont verts ;
- la branche est réconciliée avec `main` et la CI complète est verte avant merge.
