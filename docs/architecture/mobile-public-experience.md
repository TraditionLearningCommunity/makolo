# Makolo Mobile — Public Experience

**Base auditée :** `main@26db3db3438573332cff6c7bfb59e337966a3e21`  
**Portée :** Flutter invité et projection HTTP publique minimale des Espaces.  
**Hors portée :** charte visuelle, onboarding introductif, création de vérités métier, nouvelles Permissions/Mandates, accès privés, migration.

## Problème utilisateur

La première entrée mobile se limitait à une liste de vingt possibilités déjà reçues, filtrées uniquement dans le client. Le Web permet déjà une vraie exploration publique : recherche, verticales, filtres, détails et Espaces.

Une personne sans compte doit pouvoir explorer les mêmes **vérités publiques**, sans disposer de surfaces personnelles ni d'autorité Space.

## Contrats réutilisés

- `GET /api/v1/discovery/items/` : champ public multi-famille, mêmes contraintes `q`, `vertical`, `when`, `place`, `price`, pagination serveur.
- `GET /api/v1/discovery/items/<family>/<uuid>/` : détail public et présentation de l'action propriétaire.
- `GET /api/v1/discovery/map/` : résultats réellement géolocalisés, bornés par le serveur.
- `DiscoveryQuery` et `DiscoverySelector` : objets de requête et lecture canonique de Presentation.
- `SessionRecoveryController` : reprise d'intention protégée après authentification.
- `MakoloMapsConfig` : carte exclusivement lorsque le runtime l'autorise.

Nouvelle projection **sans modèle persistant** :

- `GET /api/v1/organizations/public-spaces/?q=&page=&page_size=`
- `GET /api/v1/organizations/public-spaces/<slug>/?page=&page_size=`

Un Espace est public ici seulement si `public_profile`, `searchable` et `lifecycle=active`. Les champs retournés sont délibérément bornés à l'identité publique. Les possibilités liées à un Espace proviennent de `compose_discovery(..., profile=None)` et non de la liste brute de ses Activity.

## Parcours visiteur

```text
Onboarding existant
    → Accueil public (/welcome)
       ├── Découvrir (/discover)
       │    ├── résultats / filtres / pagination serveur
       │    ├── carte (/discover/map)
       │    └── possibilité publique (/discover/items/:family/:id)
       ├── Espaces (/spaces)
       │    └── détail Space (/spaces/:slug)
       │         └── possibilité publique
       └── Connexion / créer un compte
```

Le shell invité ne contient ni Maintenant, ni En cours, ni Moi, ni Mark. Le shell personnel et les profondeurs Space existants restent inchangés. Une navigation vers une route personnelle ou une action protégée conserve son origine via `SessionRecoveryController`.

## Invariants

- Aucune identité Profile fictive, aucune autorité dérivée d'une appartenance à un Space.
- La recherche locale ne remplace pas la recherche publique serveur.
- Pas de score ou ranking dans Flutter ; le serveur fournit le champ des possibilités.
- Aucune copie de `Readiness`, `Access`, `Capacity`, `Journey` ou de la visibilité canonique.
- Pas de permission système à la première ouverture. La carte reste soumise à la configuration native.
- Une donnée privée ou non publiée ne devient jamais publique du fait de la composition d'un Espace.
- Les erreurs réseau ne créent ni fausses possibilités ni fausse confirmation d'action.
- Les médias et liens présentés proviennent des faits publics exposés par le serveur.

## Contrôles ciblés

- Django : répertoire anonyme, visibilité minimale, pagination, Espace inaccessible lorsqu'il est non publié/non searchable/inactif, composition publique bornée à l'Espace.
- Flutter : entrée invité, recherche qui déclenche une vraie requête `q`, pagination serveur, détail public, consultation d'Espace, aucune auth forcée pour lecture publique, auth requise sur profondeur personnelle.
- Gate mobile existante : introduction conservée, arrivée sur le nouvel accueil public après `Découvrir Makolo`.

## Suivi de livraison

Après mise en PR : contrôle CI agrégé, format/analyse Flutter, tests widget ciblés, tests Django ciblés et tests de non-régression avant toute fusion. PythonAnywhere reste l'environnement de bêta/test ; aucun déploiement n'est implicitement déclenché par cette PR.
