# Space — spécification amont et archétypes opérationnels

> **Statut : spécification de conception fermée pour l’amont Space.**
>
> Base réconciliée : `main@873af7245bead12cd6a97c5bcfe54364747cac97`.
>
> Cette spécification précise ce qu’est un Space, ce qu’il possède réellement, comment son archétype fonctionne et comment il compose les domaines Makolo existants. Elle ne fixe pas encore l’UX « Maintenant », les dashboards, les KPI détaillés, les écrans finaux, les APIs ni le schéma Django définitif.
>
> Le Domain Blueprint reste la source canonique supérieure. Le présent document ferme les décisions spécifiques nécessaires au prochain chantier Space.

---

## 1. Définition canonique

Un **Space** est l’identité collective durable d’un acteur qui opère dans Makolo.

Il peut représenter notamment une entreprise, une association, une institution, une marque, un collectif, une école, une organisation publique, un artiste structuré, un média ou un opérateur.

Un Space :

- n’est jamais un `User` déguisé ;
- n’a pas de mot de passe ni de session propre ;
- est opéré par des Profils humains ;
- peut être l’opérateur logique de plusieurs Activities ;
- peut composer plusieurs domaines Makolo sans les posséder ;
- possède une identité publique contrôlée et un contexte opérationnel privé ;
- peut fonctionner différemment d’un autre Space grâce à son archétype sans changer le noyau métier de Makolo.

Formule :

```text
Profile
= personne humaine

Space
= acteur collectif durable

Activity
= chose organisée, proposée ou opérée

SpaceArchetype
= manière principale de fonctionner du Space
```

---

## 2. Responsabilité et frontière

Le Space possède seulement ce qui relève réellement de son identité collective et de sa configuration propre.

Il peut **référencer ou composer** :

- Activities / Occurrences ;
- Teams ;
- Mandates ;
- Groups ;
- CRM / Audiences ;
- Places / Zones ;
- Commerce / Offers / Orders ;
- Payments ;
- Capacity ;
- Access ;
- Trust ;
- Funding ;
- Partners ;
- Loyalty ;
- Recognition ;
- Growth ;
- Analytics ;
- Automation ;
- Operations ;
- Subscriptions / Entitlements ;
- verticales Event, Service, Transport, Funding, Obtention et autres verticales canoniques.

Il ne doit jamais absorber ces domaines dans `Organization`.

Principe :

```text
SPACE
= identité + configuration propre + relations

SPACE
!= copie locale de tous les domaines Makolo
```

---

## 3. Identité minimale du Space

L’identité générique doit rester volontairement petite.

Le runtime possède déjà notamment :

```text
name
slug
description
website
contact_email
contact_phone
country
city
public_profile
verification_status
created_by
created_at
updated_at
```

La cible ajoute conceptuellement :

```text
archetype
lifecycle
```

sans décider ici de la forme exacte des champs ou modèles Django.

### 3.1 Ce qui n’entre pas automatiquement dans Organization

Ne pas ajouter par réflexe à `Organization` :

- forme juridique détaillée ;
- secteur métier ;
- licence ;
- zones desservies ;
- horaires métier ;
- moyens de paiement ;
- véhicules ;
- produits ;
- services ;
- ressources ;
- catalogues ;
- règles de capacity ;
- conditions d’accès ;
- procédures ;
- documents métier.

Ces vérités appartiennent aux domaines qui les possèdent lorsqu’elles deviennent réellement nécessaires.

---

## 4. Lifecycle minimal

Le lifecycle opérationnel du Space est distinct de son état de vérification.

Cible minimale :

```text
ACTIVE
SUSPENDED
ARCHIVED
```

### ACTIVE

Le Space existe et peut fonctionner normalement selon Permissions, Entitlements et règles métier.

### SUSPENDED

Le Space et son historique restent conservés, mais les opérations nouvelles peuvent être bloquées selon les règles de suspension.

La suspension :

- ne supprime aucun fait ;
- ne révoque pas silencieusement l’historique ;
- ne signifie pas « non vérifié ».

### ARCHIVED

Le Space n’est plus exploité comme acteur actif mais son historique reste conservé.

L’archivage :

- n’efface pas les Activities, Journeys, Payments, Access, Analytics ou audits historiques ;
- n’est pas une suppression physique ;
- ne doit pas réutiliser le slug ou l’identité de manière ambiguë sans règle explicite.

### Vérification séparée

`verification_status` reste un axe Trust / assurance.

```text
lifecycle
!=
verification_status
```

« Vérifié » ne signifie jamais « organisation de qualité » ou « activité garantie ».

---

## 5. Création, responsabilité humaine et ownership

Le runtime actuel applique déjà le bon principe à la création :

```text
Profile crée Space
      ↓
Organization.created_by = Profile
      +
Team principale
      +
TeamMembership active
      +
Mandate SPACE_OWNER
```

Le contrat à conserver est :

- `created_by` est une provenance/audit ;
- `created_by` n’est pas une propriété éternelle ;
- l’autorité réelle vient des Mandates ;
- plusieurs Owners peuvent exister ;
- le dernier Owner ne peut pas être retiré sans transfert ou remplacement valide ;
- modifier l’ownership exige une Permission dédiée ;
- quitter ou retirer quelqu’un du Space doit révoquer les Mandates locaux concernés sans toucher les autres Espaces ni les responsabilités sans rapport.

Formule :

```text
créateur historique
!=
autorité actuelle

TeamMembership
!=
ownership

SPACE_OWNER Mandate
= responsabilité actuelle d’ownership
```

---

## 6. Team, Group et autorité

### Team

Une Team organise la collaboration interne.

```text
TeamMembership
= collaboration
```

Elle n’accorde aucune Permission par elle-même.

Un Space conserve une Team principale et peut posséder des Teams secondaires.

### Group

Un Group sert à l’appartenance, au ciblage ou à l’éligibilité.

```text
GroupMembership
!=
TeamMembership
!=
Mandate
```

### Autorité

La source de vérité reste :

```text
Profile + Role + Scope = Mandate
```

L’archétype ne donne jamais de Permission.

---

## 7. SpaceArchetype

`SpaceArchetype` décrit la **manière principale de fonctionner** d’un Space.

Il répond à :

> « Quel genre d’acteur durable est cet Espace et comment Makolo doit-il préparer son environnement de travail par défaut ? »

Il ne répond pas à :

> « Quelles Activities cet Espace a-t-il le droit de créer ? »

Séparation :

```text
SpaceArchetype
= centre de gravité opérationnel

Activity vertical
= nature de ce que le Space fait concrètement

Mandate / Permission
= autorité humaine

Entitlement
= disponibilité produit

Domain facts
= réalité métier effectivement créée
```

---

## 8. Les huit archétypes initiaux

La V1 est volontairement courte :

| Code | Sens |
| --- | --- |
| `generic` | organisation généraliste ou sans centre de gravité spécialisé |
| `creative` | artiste, collectif créatif, studio, production artistique |
| `media` | média, rédaction, journalisme, production éditoriale |
| `education` | école, centre de formation, enseignement, transmission |
| `commerce` | vente, distribution, location, fourniture de biens ou ressources |
| `service_provider` | prestations de services |
| `transport_operator` | exploitation organisée de transport |
| `community` | association, ONG, club, fondation, communauté structurée |

Ne pas créer par défaut `restaurant`, `hotel`, `shop`, `consultant`, `agency`, `school`, `university`, `ngo`, `club`, `band`, `newspaper`, `rental_company`, etc.

Un nouvel archétype n’est justifié que si :

1. il représente une grande manière durable de fonctionner ;
2. il change réellement la composition/configuration Makolo ;
3. cette différence ne peut pas être portée correctement par un archétype existant + Activities + Topics + Presentation + faits métier.

---

## 9. Contrat commun d’un preset opérationnel

Un archétype produit un preset dérivé du type conceptuel :

```text
SpaceOperatingPreset
├── labels / vocabulary
├── featured_modules
├── suggested_verticals
├── relevant_domains
├── setup_recommendations
├── crm_lens
├── analytics_lens
├── automation_suggestions
└── presentation_hints
```

Le preset :

- prépare ;
- ordonne ;
- contextualise ;
- suggère ;
- met en avant.

Il ne :

- crée pas de faits métier ;
- n’accorde pas de Permission ;
- n’accorde pas d’Entitlement ;
- n’interdit pas une verticale ;
- ne remplace pas les owners canoniques.

---

# 10. Configuration — generic

## Définition

Organisation généraliste, multidomaine ou sans besoin de spécialisation forte.

## Centre de gravité

```text
organiser et opérer des Activities
sans hypothèse métier dominante
```

## Verticales suggérées

```text
Event
Service
Obtention
Transport
Funding lorsque pertinent
```

Aucune n’est obligatoire.

## Domaines Makolo prioritaires

- Activities / Occurrences ;
- Requests / Journeys ;
- Groups ;
- CRM / Audiences ;
- Places ;
- Commerce / Payments selon usage ;
- Analytics ;
- Automation ;
- Team ;
- Subscription.

## Configuration utile

- identité ;
- première Activity ;
- lieux/zones si nécessaires ;
- équipe ;
- groupes/contacts lorsque réellement utilisés ;
- commerce/paiement seulement si le métier le nécessite.

## Interdictions

Le preset ne crée automatiquement :

- aucune Activity ;
- aucun contact ;
- aucun groupe ;
- aucune offre ;
- aucun Requirement.

`generic` n’est jamais une version pauvre de Makolo.

---

# 11. Configuration — creative

## Définition

Artiste, collectif créatif, studio ou acteur principalement structuré autour de création et production artistique.

## Centre de gravité

```text
créer
présenter
faire vivre
prester
éventuellement commercialiser
```

## Verticales suggérées

```text
Event
Service
Obtention
Transport si nécessaire
```

## Domaines Makolo prioritaires

- Activities / Occurrences ;
- Event ;
- Service ;
- Obtention ;
- CRM / Audiences ;
- Partners ;
- Promotions ;
- Growth ;
- Offers / Orders / Payments ;
- Loyalty lorsque pertinente ;
- Analytics ;
- Automation ;
- Team.

## Configuration utile

- identité artistique ;
- premières créations/Activities ;
- prochaines Occurrences/Event si nécessaire ;
- prestations/bookings si le métier en a ;
- offres/obtention lorsque des biens ou usages sont proposés ;
- publics/contacts ;
- partenaires ;
- paiements lorsque le commerce existe.

## Interdictions

- aucun feed générique obligatoire ;
- aucun Post/Story générique créé pour « faire réseau social » ;
- aucun média orphelin ;
- aucun faux portfolio métier dupliquant Activities/Resources/Presentation.

---

# 12. Configuration — media

## Définition

Média, rédaction, journaliste structuré, organisation éditoriale ou acteur de production/diffusion d’information.

## Centre de gravité

```text
produire
documenter
organiser des publics
travailler avec partenaires
opérer des activités éditoriales ou événementielles
```

## Verticales suggérées

```text
Event
Service
Obtention lorsque pertinente
Transport lorsque pertinent
```

## Domaines Makolo prioritaires

- Activities ;
- Event ;
- CRM / Audiences ;
- Groups ;
- Partners ;
- Trust ;
- Promotions ;
- Growth ;
- Commerce / Payments lorsque nécessaire ;
- Analytics ;
- Automation ;
- Team.

## Configuration utile

- identité éditoriale ;
- premières productions/Activities ;
- publics/audiences ;
- groupes ;
- partenaires ;
- Trust/références lorsque pertinent ;
- commerce ou prestations si le média en opère.

## Interdictions

- pas de timeline générique ;
- pas de feed infini comme finalité ;
- pas de métriques de popularité comme vérité centrale ;
- contenu et média restent attachés à un contexte ou une finalité Makolo.

---

# 13. Configuration — education

## Définition

École, université, centre de formation ou acteur principalement structuré autour d’enseignement et transmission.

## Centre de gravité

```text
programmes
sessions
inscriptions / demandes
conditions
ressources
participation réelle
```

## Verticales suggérées

```text
Service
Event
Obtention
Transport
```

## Domaines Makolo prioritaires

- Activities / Occurrences ;
- Journeys / Requests ;
- Requirements ;
- Questionnaires / Forms ;
- Resources ;
- Groups ;
- Access ;
- CRM / Audiences ;
- Commerce / Payments ;
- Places ;
- Analytics ;
- Automation ;
- Team.

## Configuration utile

- identité de l’établissement ;
- premier programme/Activity ;
- sessions/Occurrences ;
- Requirements ;
- formulaires/questionnaires ;
- ressources ;
- groupes/cohortes si nécessaires ;
- tarifs/paiements si applicables ;
- lieux ;
- équipe.

## Interdictions

- ne pas créer automatiquement de cours, apprenants, Requirements ou groupes fictifs ;
- un Group Makolo ne vaut pas automatiquement promotion académique officielle ;
- aucune autorité pédagogique n’est inférée depuis l’archétype.

---

# 14. Configuration — commerce

## Définition

Acteur principalement structuré autour de vente, distribution, location ou fourniture de biens, ressources ou droits d’usage.

## Centre de gravité

```text
proposer
faire obtenir
commander
payer
remettre / rendre disponible
```

## Verticales suggérées

```text
Obtention
Service
Event
Transport
```

## Domaines Makolo prioritaires

- Obtention ;
- Activities ;
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
- Automation ;
- Team.

## Configuration utile

- première Activity Obtention ;
- cible d’obtention ;
- modes : achat, location, emprunt, réception, échange selon le contrat Obtention ;
- offre/prix ;
- disponibilité/capacité ;
- lieux de retrait/remise lorsque nécessaires ;
- paiements ;
- CRM.

## Interdictions

- un paiement ne signifie jamais automatiquement Obtention accomplie ;
- ne pas recréer Product/Inventory génériques dans Organization sans besoin de domaine démontré ;
- ne pas transformer `commerce` en whitelist de la verticale Obtention.

---

# 15. Configuration — service_provider

## Définition

Entreprise, cabinet, professionnel ou organisation principalement structurée autour de prestations.

## Centre de gravité

```text
recevoir une demande
préparer
exécuter / traiter / délivrer
constater le résultat
```

## Verticales suggérées

```text
Service
Event
Obtention
Transport
```

## Domaines Makolo prioritaires

- Service ;
- Activities ;
- Journeys / Requests / Dossiers ;
- Requirements ;
- Questionnaires / Forms lorsque nécessaires ;
- Offers ;
- Orders ;
- Payments ;
- CRM / Audiences ;
- Places / Zones ;
- Trust ;
- Promotions ;
- Analytics ;
- Automation ;
- Team.

## Configuration utile

- première prestation ;
- procédure de demande ;
- Requirements ;
- formulaire éventuel ;
- offre/tarif ;
- lieux/zones ;
- modalités de réalisation ;
- équipe ;
- CRM.

## Interdictions

- pas de faux client ;
- pas de faux service ;
- pas de faux tarif ;
- pas de Requirement inventé pour remplir une configuration ;
- un prestataire reste libre d’opérer Event, Obtention, Funding ou Transport.

---

# 16. Configuration — transport_operator

## Définition

Organisation principalement structurée autour de l’exploitation de transport.

## Centre de gravité

```text
routes
services
départs
véhicules
capacité
accès
exploitation
```

## Verticales suggérées

```text
Transport
Service
Event
Obtention
```

## Domaines Makolo prioritaires

- TransportRoute / TransportService / Departure / Vehicle ;
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

## Configuration utile

- lieux/stops ;
- première Route ;
- TransportService ;
- véhicules ;
- Departure ;
- Capacity ;
- offre/tarif ;
- Access/control ;
- équipe.

## Interdictions

- `transport_operator` ne donne aucune Permission Transport ;
- les autres archétypes peuvent aussi opérer Transport ;
- aucun véhicule ou départ fictif n’est créé automatiquement ;
- l’archétype ne devient pas propriétaire des vérités Transport.

---

# 17. Configuration — community

## Définition

Association, ONG, club, fondation ou acteur principalement structuré autour d’une mission, d’un collectif ou d’une communauté.

Ce n’est pas une classification juridique.

## Centre de gravité

```text
mission
activités
groupes
publics
partenaires
mobilisation
financement lorsque pertinent
```

## Verticales suggérées

```text
Event
Service
Funding
Obtention
Transport lorsque pertinent
```

## Domaines Makolo prioritaires

- Activities ;
- Event ;
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

## Configuration utile

- mission/identité ;
- première Activity ;
- groupes utiles ;
- publics/contacts ;
- partenaires ;
- Funding lorsque réel ;
- Trust/reconnaissance lorsque nécessaire ;
- équipe.

## Interdictions

- `GroupMembership` ne vaut pas automatiquement adhésion juridique ;
- aucun statut légal n’est déduit de `community` ;
- aucune collecte Funding n’est créée automatiquement ;
- aucune relation sociale générique ne remplace les relations métier réelles.

---

## 18. Preset vs empreinte opérationnelle

Décision définitive :

```text
ARCHETYPE
= configuration de départ et centre de gravité

OPERATIONAL FOOTPRINT
= ce que le Space utilise réellement
```

L’empreinte opérationnelle est une **projection dérivée**, pas une nouvelle source de vérité persistée.

Exemples de signaux :

- Transport : Routes, Services, Vehicles, Departures ;
- Service : Activities avec `service_details` ;
- Obtention : `obtention_details` ;
- CRM : contacts/segments réellement présents ;
- Automation : règles existantes ;
- Loyalty : programmes existants ;
- Funding : faits Funding existants ;
- Commerce : Offers/Orders réellement liés ;
- Access : droits/usages existants.

La présence réelle d’un domaine peut donc faire évoluer ce que Makolo met en avant sans changer l’archétype.

Exemple :

```text
archetype = service_provider

empreinte réelle :
Service ✓
Obtention ✓
Transport ✓
CRM ✓
Payments ✓
```

Le Space reste `service_provider`.

---

## 19. Pas de SpaceCapability générique

Ne pas introduire pour l’instant :

```text
SpaceCapability(space, code, enabled)
```

Le dépôt possède déjà plusieurs notions distinctes :

- Permissions / Mandates ;
- Workspace capabilities ;
- Subscription Entitlements ;
- Interoperability capabilities ;
- faits canoniques des domaines.

Un registre générique supplémentaire risquerait de contredire ces vérités.

Il ne pourra être introduit que si un besoin irréductible apparaît et qu’aucune projection depuis les domaines existants ne suffit.

---

## 20. Changement d’archétype

Le changement d’archétype est permis.

Exemples :

```text
generic → service_provider
creative → commerce
community → generic
```

Il ne doit jamais implicitement :

- supprimer une Activity ;
- supprimer ou invalider Route/Vehicle/Departure ;
- supprimer un CRMContact ;
- modifier un Group ;
- révoquer une Permission ou un Mandate ;
- modifier un Entitlement ;
- annuler un Order ou Payment ;
- annuler une Journey ;
- révoquer un Access ;
- effacer Analytics ou audit historique.

Le changement modifie principalement :

- le preset ;
- le vocabulaire ;
- les priorités ;
- les suggestions de configuration ;
- la Presentation.

Aucune classification ne doit être modifiée silencieusement depuis Topics, nom, historique d’usage ou comportement.

Makolo peut éventuellement suggérer un changement ; la décision reste explicite.

---

## 21. Composition entre Spaces

Un Space peut être en relation avec d’autres Spaces au travers de domaines réels :

- Partners ;
- Activities partagées selon les contrats existants ;
- Funding ;
- Commerce ;
- Sharing ;
- Trust ;
- autres relations métier futures.

Une composition ne transfère jamais implicitement :

- Permission ;
- Mandate ;
- Access ;
- Payment ;
- Entitlement ;
- données privées.

Le réseau entre Spaces doit émerger de relations d’action réelles et non d’un graphe social générique ajouté par défaut.

---

## 22. Projection publique et contexte privé

Un Space possède plusieurs projections d’une même identité :

```text
Space canonical identity
├── projection publique
├── contexte opérationnel privé
└── projection Discovery / Presentation
```

La projection publique applique la divulgation minimale.

Elle peut présenter :

- identité ;
- Activities publiques ;
- lieux publics utiles ;
- informations Trust divulguables ;
- moyens de contact publics ;
- faits nécessaires à l’action.

Elle n’expose jamais automatiquement :

- CRM ;
- Analytics internes ;
- Mandates ;
- équipe complète ;
- incidents ;
- paiements ;
- automatisations ;
- données privées.

Presentation représente les faits ; elle ne les possède pas.

---

## 23. Ce qui reste hors scope de cette fermeture amont

Les éléments suivants sont volontairement reportés à l’UX et à l’implémentation :

- « Maintenant » du Space ;
- « en cours » ;
- dashboard ;
- KPI finaux ;
- ordre pixel-précis de navigation ;
- écrans mobile/desktop ;
- responsive ;
- wording final ;
- notifications ;
- suggestions intelligentes détaillées ;
- modèles Django finaux ;
- migration finale ;
- APIs finales ;
- FeatureDefinition/Entitlements supplémentaires éventuels ;
- stratégie définitive d’Analytics par archetype ;
- bibliothèque finale de templates Automation.

Ils devront respecter cette spécification, pas la redéfinir.

---

## 24. Anti-features consolidées

Ne pas introduire :

- un login propre au Space ;
- un `User` par organisation ;
- un rôle global « organisateur » sur Profile ;
- une Permission accordée par archetype ;
- un Entitlement accordé par archetype ;
- une whitelist de verticales par archetype ;
- une taxonomie exhaustive des métiers ;
- un `SpaceCapability` générique sans besoin irréductible ;
- des copies `CreativeCRM`, `EducationAnalytics`, `CommerceAutomation`, etc. ;
- des champs Organization servant de dépôt pour toutes les données métier ;
- un feed/posts/stories générique sans besoin démontré ;
- des métriques de popularité comme finalité ;
- une suppression de faits métier lors d’un changement d’archetype ;
- une inférence silencieuse d’autorité ou d’identité depuis l’usage.

---

## 25. Invariants définitifs Space

1. **Space est une identité collective durable.**
2. **Profile reste la personne humaine globale.**
3. **Un Space n’a pas de compte de connexion autonome.**
4. **Le créateur historique n’est pas la source éternelle d’autorité.**
5. **Mandate/Permission reste la source d’autorité.**
6. **TeamMembership organise la collaboration, pas l’autorité.**
7. **GroupMembership organise appartenance/ciblage, pas l’autorité.**
8. **SpaceArchetype décrit une manière de fonctionner.**
9. **SpaceArchetype ne limite aucune verticale d’Activity.**
10. **SpaceArchetype ne crée aucun Entitlement.**
11. **Les faits métier restent propriétaires de leur domaine.**
12. **L’Operational Footprint est dérivée des faits existants.**
13. **Changer d’archetype est non destructif.**
14. **Lifecycle et Verification restent distincts.**
15. **Archiver conserve l’historique.**
16. **Une composition entre Spaces ne transfère aucun droit implicitement.**
17. **Les projections publiques appliquent la divulgation minimale.**
18. **Presentation représente les faits ; elle ne les possède pas.**
19. **Aucun module spécialisé ne justifie à lui seul un nouveau bounded context Space.**
20. **L’expérience peut varier fortement par archetype tout en réutilisant le même noyau Makolo.**

---

## 26. Critère de sortie de la conception amont

La conception amont de Space est considérée fermée lorsque les implémentations futures peuvent répondre sans nouvelle invention aux questions suivantes :

```text
Qu’est-ce qu’un Space ?
→ identité collective durable

Qui agit réellement ?
→ Profile humain sous Mandate

Qui possède les vérités métier ?
→ domaines canoniques

Comment l’organisation fonctionne-t-elle principalement ?
→ SpaceArchetype

Que fait-elle réellement aujourd’hui ?
→ Operational Footprint dérivée

Quelles fonctions produit sont disponibles ?
→ Subscription / Entitlements lorsqu’applicables

Que peut faire la personne connectée ?
→ Permissions / Mandates

Que se passe-t-il si l’archetype change ?
→ aucune destruction de faits

Que se passe-t-il si le Space est archivé ?
→ historique conservé, exploitation active arrêtée

Comment deux Spaces coopèrent-ils ?
→ relations métier explicites, aucun transfert implicite de droits
```

La suite du chantier peut donc passer à la **propriété des données et aux modèles nécessaires**, puis à l’UX, sans rouvrir ces principes fondamentaux sauf contradiction démontrée par le runtime.
