# Makolo — Acteur 1 : Prospecteur

> **Statut : PX0 — fondation du runtime Prospecteur.**
>
> Base de travail initiale : `main@9c60119f4eab8628ff33b230562f85ed8500c632`.
> Le code, les migrations, les tests et le `main` courant restent prioritaires sur ce document.

## 1. Responsabilité

Le **Prospecteur** est l'acteur en amont qui prospecte le monde extérieur afin
d'identifier de nouvelles sources et ressources susceptibles de révéler des
réalités utiles au réseau d'action Makolo.

Il ne correspond pas à la surface produit **Discover** :

```text
Prospecteur : Makolo découvre ce qu'il ne connaît pas encore.
Discover    : l'utilisateur découvre ce que Makolo connaît déjà.
```

Sa question opérationnelle est :

> **Où Makolo devrait-il aller regarder pour découvrir de nouvelles réalités ?**

Le Prospecteur produit des cibles. Il ne conclut pas qu'une cible est une
`Activity`, une `Occurrence`, une organisation ou une autre vérité métier.

## 2. Frontières PX0

Le noyau `prospector/` est un package Python indépendant du framework Web.

Invariant :

```text
prospector core -X-> Django
prospector core -X-> modèles métier Makolo
prospector core -X-> réseau
prospector core -X-> Crawlee
```

Django reste l'Orchestrateur Makolo et pourra fournir configuration, contrôle
opérationnel et adaptateurs. PostgreSQL, Crawlee et les providers externes sont
des dépendances d'infrastructure derrière des ports ; aucune d'elles n'est une
propriété constitutive du core.

## 3. Pas de liste de sites à scraper

Le Prospecteur n'est pas conçu autour d'un registre manuel du type :

```python
SITES_TO_SCRAPE = ["site-a", "site-b", "site-c"]
```

Une éventuelle cible initiale n'est qu'une preuve ou une porte d'entrée parmi
d'autres. Les checkpoints ultérieurs doivent permettre l'alimentation
automatique de la Frontier par index externes, graphe Web, structures standard,
catalogues et autres mécanismes génériques autorisés.

## 4. Contrats introduits par PX0

### `ProspectingEvidence`

Provenance minimale expliquant pourquoi une ressource a été révélée. Une
preuve de prospection ne constitue pas une preuve métier.

### `ProspectingCandidate`

Locator non résolu produit par un mécanisme de prospection. Il possède au moins
une provenance mais n'a pas encore reçu l'identité canonique de Frontier.

### `ProspectingTarget`

Cible canonique admise par la Frontier. `target_key` représente son identité
opérationnelle, pas l'identité d'une réalité métier.

### `FrontierPort`

Frontière abstraite d'admission et de claim. PX1 définira le stockage durable,
la canonicalisation, la concurrence et le cycle de vie.

### `TargetSinkPort`

Sortie minimale vers l'acteur aval. Le contrat détaillé Prospecteur ->
Observateur sera figé dans son checkpoint dédié.

## 5. Invariants du contrat

- tout candidat possède une provenance ;
- les dates du contrat sont timezone-aware et normalisées en UTC ;
- les contrats sont immuables au niveau de leur structure ;
- la version du contrat est explicite ;
- aucune sémantique `Activity` / `Occurrence` / `Opportunity` n'est portée par
  les contrats du Prospecteur ;
- `target_key` est une identité de cible opérationnelle, pas une résolution
  métier ;
- aucune dépendance réseau ou framework n'est requise pour importer le core.

## 6. Train d'implémentation empilé

Le préfixe **PX** est réservé à ce chantier pour éviter les trains déjà nommés
P/Q/R/D/O/U dans Makolo.

```text
main
  └─ PX0  fondation Python pure
       └─ PX1  Frontier PostgreSQL durable
            └─ PX2  runtime Crawlee
                 └─ PX3  sécurité réseau / SSRF / budgets
                      └─ PX4  prospection autonome initiale
                           └─ PX5  contrat Prospecteur -> Observateur
                                └─ PX6  worker continu / recovery
                                     └─ PX7  politique exploration/exploitation
                                          └─ PX8  pilote Internet contrôlé
                                               └─ PX9  hardening / échelle
```

Chaque branche suivante part du checkpoint précédent. L'intégration finale doit
être réconciliée avec le `main` courant avant merge.

## 7. Hors scope PX0

PX0 n'ajoute volontairement :

- aucune migration ;
- aucun modèle Django ;
- aucune dépendance Crawlee ;
- aucun appel HTTP ;
- aucune source Common Crawl ;
- aucune liste manuelle de sites ;
- aucun Elasticsearch ;
- aucun LLM ;
- aucun traitement Observateur/Interpréteur/Résolveur.

Ces absences sont intentionnelles : PX0 fixe les dépendances et contrats avant
l'introduction des infrastructures.

## 8. Validation PX0

Validation ciblée :

```text
python -m unittest discover prospector/tests
```

Le test de frontière importe `prospector`, `prospector.contracts` et
`prospector.ports` dans un interpréteur Python vierge et vérifie qu'aucun module
Django n'est chargé.
