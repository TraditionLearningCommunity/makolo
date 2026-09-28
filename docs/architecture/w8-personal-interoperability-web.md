# W8 — Consommation Web Profil de l’interopérabilité Makolo

> **Statut : fermeture Web Profil W8.** W8 consomme le contrat Z16 sans reconstruire M7, l’ORM Intelligence, les credentials ou l’autorité. La surface reste strictement personnelle.

## 1. Objectif

W8 rend l’interopérabilité personnelle visible depuis le Web Mature :

```text
Profil
→ Avatar
→ Connexions
→ projection Z16 Profile
```

La route Web est :

```text
GET /me/connections/
```

La source serveur reste :

```text
GET /api/v1/me/interoperability/
schema_version = z16.v1
```

Le Web ne possède aucune nouvelle vérité métier.

## 2. Composition

L’API Profile Z16 et la vue Web utilisent la même composition serveur :

```text
build_profile_interoperability_payload(request.user)
```

Cette composition sélectionne les Connections Profile du sujet courant, puis applique les projections Z16. La vue Web ne lit jamais directement `ProviderConnection`, `ProviderCredential`, `InteroperabilityRegistry`, `ActionRegistry`, `ExtensionRegistry` ou `DomainEventOutbox`.

W8 n’effectue pas un appel HTTP interne vers sa propre API : API et Web partagent le même read-model Z16 afin d’éviter une seconde interprétation du contrat.

## 3. Navigation

Les cinq destinations personnelles restent inchangées :

```text
Maintenant | Découvrir | Makolo Mark | En cours | Moi
```

`Connexions` est une profondeur de `Moi`, accessible depuis le menu Avatar existant. Elle n’apparaît pas dans le shell Space et ne devient pas une sixième N1.

## 4. Services et Connections

La page affiche seulement les informations déjà projetées par Z16, notamment :

- `display_name` ;
- `available` ;
- `connected` ;
- `usable` ;
- `manageable` ;
- `enabled` ;
- `health` public ;
- les capabilities allowlistées.

Elle ne sérialise ni n’affiche endpoint provider, modèle interne, latence, priorité, credential, secret ou clé.

Les états restent distincts. W8 ne déduit jamais `manageable` depuis `connected`, ni `usable` depuis `available`.

## 5. Empty state

Les listes vides sont un contrat produit valide.

Lorsque Z16 retourne zéro provider, zéro Connection, zéro Action et zéro Extension, W8 affiche notamment :

```text
Aucun service n’est encore disponible pour votre Profil.
Aucune extension disponible pour le moment.
```

Aucun Gmail, Calendar, Drive, OpenAI ou autre service n’est inventé pour remplir l’écran.

## 6. Actions

W8 filtre les Actions par l’autorisation déjà calculée par Z16. Il ne recalcule aucune Permission/Mandate.

Le contrat Z16 `z16.v1` courant ne fournit pas encore de lien d’exécution générique pour une Action M7. W8 ne fabrique donc aucun CTA, endpoint ou faux OAuth. Lorsqu’un owner exposera un parcours exécutable dans le contrat canonique, la présentation pourra le consommer sans déplacer l’autorité côté frontend.

Les mutations restent exclusivement chez leurs owners serveur. W8 n’ajoute aucun endpoint de mutation.

## 7. Extensions et Webhooks

Les Extensions ne sont présentées que si Z16 les projette comme disponibles et activées. Le runtime courant peut légitimement retourner une liste vide.

W8 ne construit aucune marketplace, installation de package, notation, popularité ou catalogue infini.

Aucune UX Webhook personnelle n’est créée. Les Webhooks techniques restent absents de la surface tant que le contrat Profile ne fournit pas un besoin produit explicite.

## 8. Sécurité et confidentialité

La page est authentifiée et renvoie `Cache-Control: private, no-store`.

Les garanties de sélection restent celles de Z16 :

- Profile A ne reçoit pas les Connections Profile B ;
- aucune Connection Space ne remonte dans le payload Profile ;
- aucune Connection Platform privée ne remonte ;
- Membership ne transfère aucune autorité ;
- credentials, secrets, endpoints privés et détails techniques restent non sérialisés.

Le template Django conserve l’échappement HTML par défaut. W8 n’ajoute ni redirection externe, ni mutation, ni nouveau formulaire sensible.

## 9. États d’expérience

- **loading** : navigation document/HTMX existante du shell ; aucun faux état optimiste ;
- **empty** : message produit explicite ;
- **success** : services/Connections réellement projetés ;
- **partial/unavailable** : état `enabled`, `usable` et health public de Z16 ;
- **permission denied** : route Web authentifiée, aucune sélection cross-Profile ;
- **server error** : gestion d’erreur globale du Web ; W8 ne masque pas une panne backend par une fausse réussite.

## 10. Collision audit

W8 est basé sur `main@9448f0a51d6627995b6d314fd5112e0db945403d`.

La PR #308 reste ouverte sur la fermeture de hiérarchie Personal UX et peut toucher navigation/`/me/`. W8 ne reprend pas sa cartographie non mergée comme vérité : il applique le `main` courant et borne son changement à l’entrée Avatar, la route Connexions et son rattachement à `Moi`.

Les PR #353/#354 concernent l’identité/auth Web ; W8 ne modifie ni `config/urls.py` ni les flows d’authentification. La PR #358 appartient au programme mobile A2.x et ne doit pas être confondue avec W8.

## 11. Persistance

Aucun modèle. Aucune migration.

W8 est une composition de projection, route, template, navigation et tests.

## 12. Tests ciblés

La couverture W8 vérifie :

- visiteur : route protégée et aucune entrée Avatar ;
- Profil authentifié : entrée `Connexions` ;
- empty state sans provider fictif ;
- Connection Profile réelle et états Z16 ;
- isolation cross-Profile ;
- absence de Connection Space/Platform ;
- absence de credential, secret, endpoint et modèle provider ;
- conservation des cinq N1 ;
- rattachement de Connexions à `Moi` ;
- réponse privée `no-store`.

Les tests Z16 restent propriétaires des gates serveur d’autorité sur les Connections.

## 13. Handoff Mobile A2.x

A2 n’est pas une tâche atomique déjà terminée : c’est un **programme composé de plusieurs sous-tâches A2.x**. Le merge historique #333 est un checkpoint d’intégration mobile, pas la preuve que tout le groupe A2 est fermé.

Les sous-tâches Mobile qui consomment l’interopérabilité doivent reproduire le parcours natif :

```text
Avatar mobile
→ Connexions
→ GET /api/v1/me/interoperability/
```

Web et Mobile partagent Z16, pas le HTML ni une logique métier frontend.

## 14. Non-objectifs

W8 ne construit pas :

- Space → Connexions ;
- Platform → Connexions ;
- Flutter ;
- un nouveau provider ;
- un OAuth fictif ;
- une marketplace ;
- une nouvelle N1 ;
- un second menu Avatar ;
- un nouveau système de permissions ;
- une nouvelle persistance.
