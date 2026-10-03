# Makolo — Public Experience Contract

> **Statut :** contrat Web de l’expérience avant authentification.
>
> **Portée :** shell public, accueil, Découvrir, Espaces, détails publics, connexion et création de compte.
>
> **Priorité :** le code, les permissions, les migrations et les tests du `main` courant restent la vérité runtime.

## 1. Problème

Le Makolo historique présentait encore publiquement le produit comme une plateforme principalement orientée événements, voyages, réservations et billets.

Le Makolo actuel est plus large. L’expérience publique doit refléter cette évolution sans exposer les domaines internes ni transformer la page d’accueil en catalogue de modules.

La règle reste :

> **Backend générique, métier contextuel.**

Et l’expérience doit rester :

> **Makolo marche pour vous.**

## 2. Architecture validée

### Avant connexion

```text
Makolo
├── Accueil public
├── Découvrir
├── Espaces
├── Détail d'une possibilité
├── Détail public d'un Espace
├── Connexion
└── Créer un compte
```

La navigation publique primaire est volontairement petite :

```text
Découvrir | Espaces | Connexion | Créer un compte
```

Un visiteur peut explorer les vérités publiques et ouvrir leurs détails.

Il ne possède pas encore une surface personnelle `Maintenant`, `En cours` ou `Moi`.

Il ne peut pas agir au nom d’un Espace tant qu’un Profile authentifié et une autorité serveur légitime ne l’autorisent pas.

### Après connexion — Profile

```text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
```

Les profondeurs publiques ouvertes depuis ce contexte conservent le shell personnel lorsque l’utilisateur est authentifié.

### Après changement explicite d’acteur — Space

```text
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
```

Le changement d’acteur ne crée pas une nouvelle application.

## 3. Langage public

Le public parle de ce qu’une personne peut faire, pas de l’architecture interne.

Préférer :

- vivre ;
- faire ;
- obtenir ;
- découvrir ;
- avancer ;
- Espace ;
- possibilité ;
- vocabulaire métier naturel d’une verticale.

Éviter comme langage global :

- organisateur ;
- participant ;
- billetterie ;
- réservations ;
- événements comme centre du produit ;
- IA ;
- ranking ;
- projection ;
- noms de modèles backend.

Ces termes restent possibles lorsqu’ils sont naturellement justifiés par une réalité précise.

## 4. Accueil public

L’accueil public ne possède aucune vérité métier.

Il sert de seuil vers Découvrir et vers les Espaces publics.

Il ne reconstruit pas manuellement les familles Discovery.

La recherche principale passe le relais à Découvrir.

## 5. Découvrir

Découvrir conserve son contrat multi-famille.

Un visiteur utilise le shell public.

Un Profile authentifié utilise le shell personnel.

La vérité, l’ordre, les actions légitimes et les propriétaires métier ne changent pas avec le shell.

## 6. Espaces publics

Le nom visible est **Espace**.

Les noms internes historiques tels que `Organization` ou `organizer_public` peuvent rester tant qu’un renommage n’apporte aucune valeur métier et risquerait de casser les routes.

Une page publique d’Espace présente son identité publique et permet d’explorer les possibilités qui lui sont liées sans réduire l’Espace à ses événements.

Aucune composition publique ne transfère Permission, Mandate, Access, Payment ou visibilité privée.

## 7. Détail d’une possibilité

Une possibilité reste une unité UX, pas un nouveau modèle universel.

Le détail est porté par le propriétaire adapté : Event, Transport, Funding, Opportunity, Obtention ou autre propriétaire canonique.

Le shell dépend seulement du contexte d’authentification :

```text
visiteur       → shell public
Profile        → shell personnel
Space autorisé → shell Space lorsqu’une profondeur Space le demande
```

## 8. Authentification

Connexion et création de compte restent des frontières simples.

Les formulaires, protections serveur, `next`, rate limits, politiques de mot de passe et serializers existants restent propriétaires de leur comportement.

La Presentation ne promet pas seulement billets, événements ou voyages.

## 9. Non-objectifs

Ce chantier ne crée pas :

- de migration ;
- de nouveau modèle ;
- de nouvelle Permission ;
- de nouveau Mandate ;
- de nouveau moteur Discovery ;
- de nouvelle identité `Possibility` persistante ;
- de feed ;
- de landing page expliquant l’intelligence interne de Makolo.

## 10. Critères de sortie

- l’accueil n’est plus centré Event/Transport/Ticket ;
- la navigation publique est `Découvrir | Espaces` avec authentification ;
- `Organisateurs` n’est plus le concept visible global ;
- Découvrir fonctionne anonymement dans le shell public ;
- les détails publics basculent vers le shell personnel une fois authentifié ;
- la connexion et l’inscription utilisent le langage Makolo actuel ;
- les routes et vérités métier existantes restent compatibles ;
- aucun changement de schéma n’est requis ;
- tests Django et E2E ciblés restent verts.
