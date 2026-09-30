# Space — archétypes opérationnels et composition des capacités

> **Statut : cadre de conception issu d'un audit du runtime `main` au 30 septembre 2026.**
>
> Base auditée : `main@0b2f626b5c93c03e74c5ff5afc7bf6bd4a9bf1d6`.
>
> Ce document ne remplace pas le Domain Blueprint. Il précise comment l'expérience Espace doit composer les domaines déjà présents sans créer un second modèle métier.

## 1. Problème produit

Un Espace Makolo n'est pas une simple « page » informative.

Il représente une identité collective durable — entreprise, association, institution, marque, collectif, école, organisateur, etc. — au nom de laquelle des Profils peuvent agir sous Mandate/Permission.

Makolo doit aller plus loin qu'une page de réseau social : lorsqu'un Espace choisit sa manière principale de fonctionner, il doit retrouver immédiatement une expérience de travail cohérente avec ce contexte en réutilisant les domaines Makolo déjà disponibles.

Exemples :

- un prestataire de services doit naturellement retrouver prestations, demandes/dossiers, clients, tarifs, paiements, calendrier, analyses et automatisations ;
- un commerce doit naturellement retrouver ce qu'il propose, commandes, paiements, clients, promotions, fidélité et analyses ;
- un opérateur de transport doit naturellement retrouver routes, départs, véhicules, accès, capacité, paiements et opérations ;
- un artiste ou collectif créatif doit naturellement retrouver créations/activités, événements, prestations, publics, promotion, partenaires, commerce et analyses.

Cette contextualisation ne doit jamais enfermer l'Espace dans une seule verticale d'Activity.

## 2. État réel du dépôt

### 2.1 Organization / Space

Sur le `main` audité, `organizations.Organization` possède l'identité et les paramètres génériques de l'Espace : nom, slug, description, site, contacts, localisation générale, profil public, vérification et créateur.

Il n'existe actuellement **aucun champ d'archétype** sur `Organization`.

Les migrations Organizations s'arrêtent à `0004_profilefollow`.

### 2.2 Authority

L'autorité Espace est déjà séparée de l'identité :

```text
Profile + Role + Scope + Mandate
```

`TeamMembership` organise la collaboration et n'accorde pas automatiquement d'autorité.

Un futur archétype ne doit jamais accorder de Permission, Mandate ou Access.

### 2.3 Space Console

`SpaceConsoleContext` fournit déjà une Console permission-aware.

La navigation actuelle sait composer notamment :

- Activities ;
- Requests ;
- Access ;
- Services / Dossiers ;
- Transport ;
- Offers ;
- Orders ;
- Payments ;
- Funding ;
- Promotions ;
- Groups ;
- CRM ;
- Audiences ;
- Partners ;
- Loyalty ;
- Recognition ;
- Trust ;
- Places ;
- Control / Scanner ;
- Operations ;
- Analytics ;
- Growth ;
- Automation ;
- Subscription ;
- Team ;
- Settings.

Ce socle doit être **réordonné, renommé, mis en avant ou simplifié** selon l'archétype ; il ne doit pas être dupliqué par archétype.

### 2.4 Workspace Z15/W7

`organizations.api.workspace_projection.build_space_workspace()` expose déjà une projection owner-backed de capacités réellement atteignables pour un acteur autorisé.

Elle compose notamment Partners, Growth, Analytics, Loyalty, Recognition, Trust, Funding, Access Control, CRM, Automation, Promotions et Operations.

Cette projection reste liée à l'autorité effective. Elle n'est pas un registre de « ce que l'Espace est ».

### 2.5 Subscriptions / Entitlements

Subscriptions possède déjà `FeatureDefinition`, Plans et Entitlements effectifs.

La séparation canonique reste :

```text
Subscription / Entitlement
= ce que le produit rend disponible au sujet

Permission / Mandate
= ce que la personne peut faire dans cette portée
```

L'archétype ne doit pas devenir une troisième implémentation d'Entitlements.

### 2.6 Verticales Activity

`core.product_language.vertical_for(activity)` reconnaît déjà les verticales :

- Transport ;
- Event ;
- Service ;
- Funding ;
- Obtention ;
- Generic.

Une Activity appartient logiquement à un Profile **ou** à un Space. Les verticales composent Activity au lieu de remplacer le noyau.

Le futur archétype d'Espace ne doit donc pas reproduire cette taxonomie.

## 3. Décision : ce qu'est un SpaceArchetype

`SpaceArchetype` décrit la **manière principale de fonctionner** d'un Espace.

Il répond à :

> « Quel type d'acteur durable est cet Espace et comment Makolo doit-il organiser son environnement de travail par défaut ? »

Il ne répond pas à :

> « Quelles verticales cet Espace a-t-il le droit de créer ? »

Formule :

```text
SpaceArchetype
= preset opérationnel et expérience par défaut

Activity vertical
= ce que l'Espace propose/opère concrètement

Mandate / Permission
= autorité humaine

Entitlement
= disponibilité produit

Domain facts
= réalité métier effectivement créée
```

## 4. Archétypes initiaux

La V1 doit rester volontairement courte :

| Code | Sens |
| --- | --- |
| `generic` | organisation généraliste ou contexte ne nécessitant pas encore un preset spécialisé |
| `creative` | artiste, collectif créatif, studio ou acteur centré sur création/production artistique |
| `media` | média, rédaction, journalisme, production éditoriale ou information |
| `education` | école, centre de formation, acteur d'enseignement ou transmission |
| `commerce` | acteur principalement organisé autour de vente, distribution, location ou fourniture de biens/offres |
| `service_provider` | acteur principalement organisé autour de prestations de services |
| `transport_operator` | acteur principalement organisé autour de l'exploitation de transport |
| `community` | association, ONG, club, fondation ou acteur principalement organisé autour d'une communauté/mission collective |

Cette liste ne doit pas devenir une taxonomie infinie.

Ne pas créer par défaut des archétypes comme `event_organizer`, `shop`, `restaurant`, `hotel`, `consultant`, `agency`, `school`, `university`, `ngo`, `club`, `band`, `newspaper` ou `rental_company`.

Ces notions peuvent relever de la présentation, des Topics, des Activities réellement opérées ou d'une spécialisation future démontrée.

## 5. Un archétype ne limite jamais les verticales

Exemples valides :

```text
service_provider
├── Service
├── Event
├── Obtention
└── Transport

commerce
├── Obtention
├── Service
├── Event
└── Transport

education
├── Service
├── Event
├── Obtention
└── Transport

creative
├── Event
├── Service
└── Obtention
```

`transport_operator` signifie que Transport est natif, prioritaire et naturellement configuré dans l'expérience. Il ne signifie pas que les autres archétypes sont interdits d'utiliser Transport.

Inversement, un opérateur de transport peut aussi créer un Event, une Activity Service ou une Activity Obtention.

## 6. Pas de modèle persistant SpaceCapability pour l'instant

Le dépôt possède déjà plusieurs notions distinctes de capacité :

- Permissions/Mandates ;
- Workspace capabilities Z15 ;
- Subscription Entitlements ;
- Interoperability capabilities ;
- capacités dérivées des domaines et de leurs faits.

Introduire un `SpaceCapability(space, code, enabled)` générique créerait un risque de vérité parallèle.

Décision initiale :

> ne pas créer de nouveau modèle persistant SpaceCapability tant qu'un cas irréductible ne le justifie pas.

La présence d'un domaine peut souvent être dérivée de faits canoniques :

- routes/services/véhicules pour Transport ;
- Activities `service_details` pour Services ;
- `obtention_details` pour Obtention ;
- contacts/segments pour CRM ;
- règles existantes pour Automation ;
- programmes pour Loyalty ;
- etc.

## 7. Preset opérationnel dérivé, non propriétaire

Le code pourra introduire une configuration Python/read-model du type `SpaceOperatingPreset`.

Cette configuration ne possède aucune vérité métier.

Elle peut définir :

- vocabulaire de Console ;
- ordre des sections ;
- modules à mettre en avant ;
- actions primaires suggérées ;
- verticales d'Activity proposées en premier ;
- parcours d'onboarding ;
- raccourcis vers les outils existants ;
- lenses de présentation CRM / Analytics / Automation ;
- états vides contextuels.

Exemple conceptuel :

```text
SpaceOperatingPreset
├── archetype
├── navigation_priority
├── labels
├── primary_actions
├── suggested_verticals
├── featured_modules
├── onboarding_steps
└── presentation_hints
```

Aucun de ces champs ne remplace les owners canoniques.

## 8. Composition avec les fonctionnalités déjà présentes

### generic

Centre de gravité recommandé :

- Activities ;
- Requests ;
- Groups ;
- CRM/Audiences ;
- Places ;
- Analytics ;
- Automation ;
- Team ;
- Subscription.

Aucune verticale n'est privilégiée fortement.

### creative

Centre de gravité recommandé :

- Activities / créations ;
- Event ;
- Service ;
- Obtention ;
- CRM / Audiences ;
- Promotions ;
- Growth ;
- Partners ;
- Offers / Orders / Payments ;
- Loyalty ;
- Analytics ;
- Automation.

Aucun feed générique n'est créé : No Orphan Content / No Orphan Media reste applicable.

### media

Centre de gravité recommandé :

- Activities / productions ;
- Event ;
- CRM / Audiences ;
- Groups ;
- Promotions ;
- Growth ;
- Partners ;
- Trust ;
- Analytics ;
- Automation.

Les médias contenus restent attachés à une Activity, un contexte ou une finalité réelle.

### education

Centre de gravité recommandé :

- Activities / programmes ;
- Service ;
- Event ;
- Obtention ;
- Requests / Journeys ;
- Requirements ;
- Questionnaires / Forms ;
- Resources ;
- Groups ;
- Access ;
- CRM ;
- Offers / Orders / Payments ;
- Analytics ;
- Automation.

Requirements, Questionnaires et Resources restent leurs domaines propriétaires ; l'archétype ne les copie pas dans Organization.

### commerce

Centre de gravité recommandé :

- Activities avec Obtention mise en avant ;
- Offers ;
- Orders ;
- Payments ;
- Capacity lorsque pertinente ;
- CRM / Audiences ;
- Promotions ;
- Loyalty ;
- Growth ;
- Places ;
- Trust ;
- Analytics ;
- Automation.

La verticale Obtention porte la sémantique acheter/louer/emprunter/recevoir/échanger ; `commerce` décrit le fonctionnement durable de l'Espace.

### service_provider

Centre de gravité recommandé :

- Activities avec Service mis en avant ;
- Requests / Dossiers / Journeys ;
- Offers ;
- Orders ;
- Payments ;
- CRM / Audiences ;
- Places ;
- Promotions ;
- Trust ;
- Analytics ;
- Automation ;
- Team.

Un prestataire reste libre d'opérer Event, Obtention ou Transport.

### transport_operator

Centre de gravité recommandé :

- Transport : Routes / Services / Départs / Véhicules ;
- Activities / Occurrences ;
- Places ;
- Capacity ;
- Access / Control ;
- Offers ;
- Orders ;
- Payments ;
- Operations ;
- CRM ;
- Analytics ;
- Automation ;
- Team.

Transport doit être prioritaire mais ne devient pas une autorisation implicite.

### community

Centre de gravité recommandé :

- Activities / Event ;
- Groups ;
- CRM / Audiences ;
- Funding ;
- Partners ;
- Recognition ;
- Trust ;
- Promotions ;
- Growth ;
- Analytics ;
- Automation ;
- Team.

Le type juridique précis (ONG, association, fondation, club...) reste distinct de l'archétype opérationnel.

## 9. Calcul de l'expérience effective

La Console ne doit pas être construite uniquement à partir de l'archétype.

La projection cible est :

```text
                         SpaceArchetype preset
                                  +
                         faits métier existants
                                  +
                     Subscription Entitlements
                                  +
                        Mandate / Permissions
                                  +
                      disponibilité du runtime
                                  ↓
                       expérience effective
```

Règles :

1. l'archétype choisit **priorité, vocabulaire et defaults** ;
2. les faits métier empêchent de masquer une capacité réellement utilisée ;
3. les Entitlements contrôlent les limites/disponibilités produit quand ils existent ;
4. les Permissions/Mandates contrôlent toujours l'autorité de l'acteur ;
5. le runtime réel gagne : aucun CTA mort ni module fictif.

## 10. Changement d'archétype

Le changement d'archétype doit être permis.

Il ne doit jamais :

- supprimer une Activity ;
- invalider une Route Transport existante ;
- supprimer un CRMContact ;
- révoquer une Permission ou un Mandate ;
- changer un Entitlement ;
- annuler un Payment, Access, Journey ou Order.

Il change principalement le preset de fonctionnement et la présentation.

Aucune classification ne doit être inférée silencieusement depuis le nom, les Topics, Interests ou le comportement.

`generic` reste le fallback sûr.

## 11. Onboarding

Lors de la création d'un Espace :

1. créer l'identité Espace ;
2. demander la manière principale de fonctionner ;
3. appliquer le preset ;
4. présenter un petit nombre de premières actions pertinentes ;
5. laisser toutes les verticales compatibles accessibles sans imposer une whitelist ;
6. n'instancier aucun faux fait métier pour « remplir » le preset.

Exemple `service_provider` :

```text
Configurer votre Espace
├── présenter vos prestations
├── définir tarifs / offres si nécessaire
├── ajouter vos lieux ou zones
├── préparer demandes / dossiers
├── inviter l'équipe
└── configurer clients, analyses ou automatisations au moment utile
```

Le preset prépare le chemin ; les domains propriétaires créent les faits.

## 12. Conséquences pour le prochain chantier

Le prochain chantier Space doit repartir du `main` courant et rester plus petit que l'ancienne PR #252.

Ordre recommandé :

1. ajouter uniquement `Organization.archetype` avec les huit valeurs et fallback `generic` ;
2. ajouter le preset dérivé `SpaceOperatingPreset` sans état persistant supplémentaire ;
3. brancher le preset sur l'onboarding et la composition de `SpaceConsoleContext` ;
4. réutiliser les modules Z15/W7 et les surfaces déjà présentes ;
5. contextualiser labels, ordre, états vides et actions primaires ;
6. ne pas introduire de gate de verticale basé sur l'archétype ;
7. faire remonter les verticales réellement utilisées depuis les faits canoniques ;
8. intégrer les Entitlements seulement via le resolver Subscriptions existant lorsqu'un FeatureDefinition pertinent existe ;
9. tester séparément présentation, autorité et disponibilité produit.

## 13. Anti-features

Ne pas introduire :

- un compte/login propre au Space ;
- un rôle global « organisateur » sur Profile ;
- une Permission accordée par archetype ;
- un Entitlement accordé par archetype ;
- une whitelist exclusive de verticales ;
- une copie `CreativeCRM`, `EducationAnalytics`, `CommerceAutomation`, etc. ;
- une nouvelle table générique de capabilities sans besoin irréductible ;
- une taxonomie exhaustive des métiers ;
- des feeds/posts/stories génériques pour donner artificiellement du contenu aux archétypes.

## 14. Critère de sortie

Le chantier est réussi lorsqu'un utilisateur peut créer plusieurs Espaces de natures différentes et constater immédiatement que Makolo **fonctionne différemment pour chacun**, tout en vérifiant que :

- les mêmes domaines canoniques sont réutilisés ;
- une même verticale peut être opérée par plusieurs archétypes ;
- changer d'archétype ne détruit aucun fait ;
- TeamMembership n'accorde aucune autorité ;
- Mandate/Permission reste source d'autorité ;
- Entitlements restent source de disponibilité produit ;
- les données CRM, Analytics, Automation, Commerce, Access, Journey, Transport, etc. restent dans leurs domaines propriétaires ;
- aucune fonctionnalité existante utile n'est recréée localement dans Organizations.
