# Makolo API v1 — contrat consommable et compatibilité

## Statut

Ce document formalise le contrat client commun au Web, à Flutter et aux intégrations autorisées. Il ne crée aucun modèle métier, aucun namespace `/mobile/` et aucune seconde source de vérité.

Le runtime et les domaines propriétaires restent prioritaires.

## Principes

```text
domain owner
  -> selector/service
  -> projection / DTO
  -> API v1
  -> Web / Flutter / intégration
```

Les modèles ORM ne sont pas le contrat réseau. Une projection peut évoluer sans exposer la structure interne du domaine.

Le serveur reste autoritatif pour Permission, Mandate, Readiness, Requirement satisfaction, Access, Capacity, Payment et les autres décisions sensibles.

## OpenAPI

Le schéma machine-readable est généré par `drf-spectacular`.

Commande canonique :

```bash
python manage.py spectacular --file /tmp/makolo-openapi.json --format openapi-json --validate
```

Un endpoint authentifié expose également le schéma courant :

```text
GET /api/v1/schema/
```

Le schéma sert à documenter et vérifier le contrat. Il ne devient pas propriétaire des vérités métier.

## Contrat minimum supporté

`supported-client-contract-v1.json` contient le noyau de routes qui ne peut pas disparaître silencieusement d'une PR v1.

La gate vérifie actuellement les opérations structurantes :

- health / readiness ;
- Moi ;
- Maintenant ;
- En cours ;
- Makolo Mark ;
- Découvrir ;
- Maintenant Space ;
- Découvrir Space ;
- Métier Space ;
- Nous ;
- Mark Space.

Cette liste est volontairement minimale : elle protège le handoff client principal sans prétendre que les autres routes n'ont aucun contrat.

## Règles de compatibilité

En `/api/v1/` :

- ajouter une route ou un champ optionnel est normalement additif ;
- retirer une opération supportée est breaking ;
- changer sa méthode HTTP est breaking ;
- renommer une route supportée est breaking ;
- rendre obligatoire un champ auparavant optionnel est breaking ;
- changer le sens métier d'un champ sans nouvelle version est breaking ;
- exposer directement un modèle ORM pour éviter un DTO/projection n'est pas autorisé.

Une modification breaking doit être explicitement versionnée ou accompagnée d'une migration client coordonnée. Aucun `v2` n'est créé tant qu'un besoin réel ne le justifie.

## Gate CI

Le workflow `API Contract` :

1. installe le runtime Python canonique ;
2. exécute les checks Django ;
3. génère et valide le schéma OpenAPI ;
4. vérifie que toutes les opérations du manifeste supporté existent encore.

Le gate détecte donc les suppressions et changements de méthode sur le contrat minimum. Les changements de forme plus fins restent protégés par les tests de projection/serializer propriétaires ; ils peuvent être ajoutés au manifeste lorsqu'un contrat client le nécessite.

## Flutter

Flutter consomme les APIs propriétaires existantes. Il ne doit pas dépendre :

- des modèles Django ;
- de noms de tables ;
- d'un endpoint générique `/sync/` ;
- d'un namespace `/api/v1/mobile/` ;
- d'une duplication locale de Permission, Mandate, Access, Readiness, Capacity ou Payment.

Les DTO réseau Flutter restent distincts des modèles Drift et des vérités métier.

## Dépréciation

Avant retrait d'une opération v1 réellement consommée :

1. identifier les clients concernés ;
2. fournir le remplacement ;
3. migrer Web/Flutter/intégrations ;
4. conserver les tests de compatibilité pendant la transition ;
5. retirer l'ancienne opération dans un changement explicitement breaking.

La simple ancienneté d'une route n'autorise pas sa suppression.


## C0 — Mature Surface Contract Foundation

`mature-surface-contract-foundation-v1.md` et
`fixtures/mature-surface-foundation-v1.json` constituent la fondation C0
partagée Web/Flutter pour les surfaces Mature. Ils réutilisent ce schéma et ce
gate : ils ne créent pas un second système de contrat.

Le manifeste supporté protège les routes structurantes C0 réellement présentes
dans le runtime. Les fixtures décrivent les états de surface (ready, empty,
partial, unavailable) et les forbidden client claims ; elles restent des
exemples contractuels, pas une nouvelle source de vérité métier.
