# Module Events

## Responsabilité

Le module `events` est la source de vérité Makolo pour la préparation, la publication et le cycle de vie d’un événement. La billetterie, le scanner, les paiements et l’analytique devront référencer ce module au lieu de dupliquer ses données.

## Modèles

### EventCategory

Catalogue de catégories réutilisables. Les catégories peuvent être désactivées sans supprimer les événements existants.

### EventVenue

Lieu réutilisable avec trois modes :

- `physical` : présentiel ;
- `online` : en ligne ;
- `hybrid` : hybride.

Les lieux en ligne et hybrides exigent une URL.

### Event

Contient notamment : organisateur, catégorie, lieu, titre, slug public stable, descriptions, couverture, visibilité, dates, fenêtre d’inscription, fuseau horaire, capacité et métadonnées internes.

## États

```text
draft
  └── publish ──> published
                    ├── cancel ──> cancelled
                    └── complete -> completed

draft ── cancel ──> cancelled
```

Les changements d’état passent par `events/services.py`. Le champ `status` n’est pas directement modifiable par l’API d’écriture.

## Autorisation

La création exige le rôle actif `organizer` ou un compte staff. Le booléen historique `is_organizer` reste seulement un fallback de compatibilité, conformément à `accounts-rbac.md`.

Un organisateur peut modifier uniquement ses propres événements. Le staff peut administrer tous les événements.

## Visibilité API

- visiteur anonyme : événements `published + public` dans la liste ;
- lien direct : `published + public/unlisted` ;
- utilisateur authentifié : mêmes événements publics, plus ses propres événements ;
- staff : tous les événements.

Les événements `private` ne sont jamais exposés publiquement.

## API v1

```text
GET/POST       /api/v1/events/
GET/PATCH/DEL  /api/v1/events/<slug>/
POST           /api/v1/events/<slug>/publish/
POST           /api/v1/events/<slug>/cancel/
POST           /api/v1/events/<slug>/complete/
GET            /api/v1/events/categories/
GET            /api/v1/events/venues/
```

## Interface web

```text
/events/
/events/new/
/events/<slug>/
/events/<slug>/edit/
```

Les actions de publication, annulation et clôture utilisent des requêtes POST protégées par CSRF.

## Règles de données

- `end_at` doit être strictement postérieur à `start_at` ;
- une fenêtre d’inscription doit être chronologiquement valide ;
- une capacité renseignée doit être supérieure ou égale à 1 ;
- le slug est généré une fois et reste stable lorsque le titre change ;
- une couverture est limitée à 8 Mo et aux formats JPEG, PNG ou WebP.

## Extension prévue

Le module `tickets` devra référencer `Event` et appliquer la capacité ainsi que les fenêtres d’inscription sans recopier la logique de cycle de vie de l’événement.
