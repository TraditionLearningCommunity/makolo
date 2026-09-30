# Makolo — Space
## Spécification conceptuelle consolidée

> **Statut : spécification amont consolidée**
>
> **Dépôt de référence :** TraditionLearningCommunity/makolo
>
> **Base vérifiée :** main@d3bdb0b2a81a2f6107b708cebc5ba334380c0b79
>
> **Portée :** fixer ce qu’est un Space dans Makolo, ses frontières, son cycle de vie conceptuel, son autorité, ses archétypes et leurs configurations métier, ainsi que ses relations avec les domaines canoniques.
>
> **Hors périmètre :** UX détaillée, « Maintenant », « en cours », dashboards, navigation finale, écrans, responsive/mobile, APIs finales, schémas Django, migrations et choix de persistance.
>
> Le document docs/architecture/makolo-domain-blueprint.md reste la source canonique supérieure pour les frontières générales de Makolo. Le présent document consolide la spécification propre à Space.

---

# 1. Définition

Un **Space** est l’identité collective durable d’un acteur qui opère dans Makolo.

Il peut représenter notamment une entreprise, une association, une institution, une organisation publique, une marque, un collectif, une école, un centre de formation, un média, une structure créative, un opérateur de transport, une fondation ou une organisation communautaire.

Un Space est plus proche, par son rôle d’identité publique, d’une Page Facebook ou LinkedIn Entreprise que d’un compte personnel. Mais Makolo va plus loin : un Space n’est pas seulement une représentation informative. C’est un **acteur opérationnel** capable d’organiser, proposer, opérer et composer les capacités métier de Makolo.

~~~text
Profile
= personne humaine globale

Space
= acteur collectif durable

Activity
= chose organisée, proposée ou opérée

SpaceArchetype
= manière principale de fonctionner du Space
~~~

Un Space n’est jamais un User déguisé. Il ne possède ni mot de passe propre ni session propre. Des Profils humains agissent au nom du Space sous une autorité explicite.

---

# 2. Quand un Space est justifié

Makolo ne doit pas obliger toute personne ayant un métier ou une activité à créer un Space.

Un Profile peut agir directement en son nom.

Un Space est justifié lorsqu’il existe un contexte durable suffisamment autonome, par exemple :

- une identité collective ou professionnelle distincte ;
- des Activities opérées au nom de cette identité ;
- une équipe ;
- des responsabilités distribuées ;
- des ressources ou lieux propres ;
- des relations avec des clients, publics, partenaires ou groupes ;
- un historique devant survivre au changement des personnes qui l’opèrent ;
- des Permissions/Mandates au nom de l’entité ;
- des opérations, paiements, accès, capacités ou démarches appartenant réellement à l’organisation.

Test conceptuel :

> Si retirer le Space ferait perdre une vraie frontière d’identité, d’action, de responsabilité ou d’historique, le Space est probablement justifié.

Inversement :

> Si retirer le Space ne fait perdre qu’une étiquette comme « musicien », « consultant » ou « journaliste », un Space n’est pas nécessairement justifié par cette seule caractéristique.

Un artiste solo peut donc utiliser uniquement son Profile, ou créer un Space lorsqu’il agit sous une identité artistique/professionnelle durable qui doit porter des Activities, partenaires, paiements, équipe ou historique propres.

---

# 3. Responsabilité canonique

Le Space est l’**opérateur logique collectif** des Activities et capacités métier d’une entité lorsqu’elle agit dans Makolo.

Il peut être relié ou composer :

- Activities / Occurrences ;
- Journeys / Requests ;
- Requirements ;
- Resources ;
- Questionnaires / Forms ;
- Access ;
- Capacity ;
- Commerce / Offers / Orders ;
- Payments ;
- Geography / Places / Zones ;
- CRM / Audiences ;
- Groups ;
- Partners ;
- Funding ;
- Trust ;
- Promotions ;
- Growth ;
- Loyalty ;
- Recognition ;
- Sharing ;
- Operations ;
- Analytics ;
- Automation ;
- Subscriptions / Entitlements ;
- Teams ;
- Mandates.

Mais le Space **ne possède pas la vérité métier de ces domaines**.

~~~text
SPACE
= identité + configuration propre + relations vers les domaines

SPACE
!= agrégat contenant toutes les vérités métier de l'organisation
~~~

Les domaines propriétaires restent propriétaires de leurs faits.

---

# 4. Identité minimale du Space

L’identité générique d’un Space doit rester petite et durable.

Elle couvre conceptuellement :

~~~text
nom
identifiant/slug stable
description générale
contacts généraux
site ou référence publique
localisation générale
visibilité publique
provenance de création
état de vérification
archétype
lifecycle
timestamps/audit
~~~

Cette liste décrit la responsabilité conceptuelle ; elle ne fixe pas un schéma de persistance.

Ne doivent pas être ajoutés à l’identité du Space simplement parce qu’ils décrivent son activité :

~~~text
forme juridique détaillée
secteur métier détaillé
licences
horaires métier
zones desservies
moyens de paiement
véhicules
routes
produits
services
ressources
catalogues
tarifs
stock
capacity
conditions
requirements
procédures
documents métier
~~~

Ces informations doivent être portées par Trust, Geography, Activity, Transport, Commerce, Requirements ou les autres domaines compétents lorsqu’un besoin réel le justifie.

Règle :

> Une information n’appartient directement au Space que si elle caractérise durablement l’acteur collectif lui-même et qu’aucun domaine propriétaire ne la porte correctement.

---

# 5. Cycle de vie conceptuel

Le cycle de vie opérationnel du Space est distinct de la vérification.

La cible minimale est :

~~~text
ACTIVE
SUSPENDED
ARCHIVED
~~~

## ACTIVE

Le Space existe et peut fonctionner normalement, sous réserve des Permissions/Mandates, des Entitlements, des règles des domaines métier et des décisions de Trust applicables.

## SUSPENDED

Le Space existe toujours et son historique reste conservé. Les nouvelles opérations ordinaires doivent être bloquées ou limitées conformément à la cause de suspension.

La suspension ne supprime aucun fait, ne réécrit pas l’historique et ne signifie pas simplement « non vérifié ».

## ARCHIVED

Le Space n’est plus exploité comme acteur actif. Son identité et son historique restent conservés.

L’archivage n’est pas une suppression physique. Il ne supprime pas ses Activities historiques, Journeys, Payments, Access, Analytics ou traces d’audit.

## Axes séparés

~~~text
LIFECYCLE
!=
VERIFICATION
!=
READINESS
~~~

Une future notion de préparation ou de complétude doit être dérivée ; elle ne justifie pas des états génériques draft/configuring/ready/complete sur Space.

---

# 6. Vérification et Trust

La vérification répond à une question d’assurance précise.

Elle peut concerner notamment l’identité de l’entité, l’autorité d’un représentant, une information professionnelle, une information de paiement ou une preuve particulière.

Elle ne signifie jamais :

~~~text
Space vérifié
=
bonne organisation
=
activité garantie
=
qualité certifiée
~~~

Trust reste propriétaire de ces garanties.

---

# 7. Créateur, ownership et responsabilité humaine

À la création d’un Space, le Profile qui effectue l’action est conservé comme provenance.

~~~text
Profile crée Space
        ↓
provenance de création
        +
Team principale
        +
TeamMembership
        +
Mandate SPACE_OWNER
~~~

Le créateur n’est pas le propriétaire éternel :

~~~text
created_by
!=
autorité actuelle
~~~

L’ownership du Space est une responsabilité exprimée par Mandate.

Décisions :

1. plusieurs Owners peuvent exister ;
2. aucun propriétaire parallèle ne doit concurrencer les Mandates ;
3. le dernier Owner actif doit être protégé ;
4. ajouter un Owner consiste à accorder l’autorité correspondante ;
5. transférer l’ownership consiste d’abord à établir un nouvel Owner valide puis, si souhaité, à retirer l’ancien ;
6. retirer un Owner exige une autorité explicite appropriée ;
7. un Owner peut cesser d’être Owner sans que l’histoire du Space change.

---

# 8. Team, Group et Mandate

## Team

Une Team représente la collaboration interne.

~~~text
TeamMembership
= cette personne collabore dans cette Team
~~~

Une Team n’accorde aucune Permission par elle-même.

Un Space peut avoir une Team principale et plusieurs Teams secondaires.

## Group

Un Group représente appartenance, ciblage, population ou éligibilité.

~~~text
GroupMembership
!=
TeamMembership
!=
Mandate
~~~

## Mandate

Le Mandate reste la source de vérité de l’autorité contextuelle.

~~~text
Profile + Role + Scope = Mandate
~~~

Ni l’archétype, ni TeamMembership, ni GroupMembership ne donnent automatiquement une Permission.

---

# 9. Topic, OpenTo et Archetype

Ces notions ne doivent jamais être confondues.

~~~text
Topic
= sujet

SpaceOpenTo
= consentement explicite à certaines sollicitations

SpaceArchetype
= manière principale de fonctionner
~~~

Un musicien peut parler de technologie. Un média peut couvrir le sport. Une école peut organiser un événement culturel. Le Topic ne définit donc pas la nature opérationnelle du Space.

SpaceOpenTo exprime ce à quoi le Space accepte potentiellement de répondre ; il ne décrit pas ce que le Space est.

---

# 10. Activities et verticales

Une Activity a exactement un opérateur logique :

~~~text
Profile XOR Space
~~~

Un même Space peut opérer plusieurs types d’Activities.

Les verticales Activity structurantes incluent notamment Event, Transport, Service, Funding, Obtention et Generic lorsque aucune spécialisation n’est nécessaire.

Opportunity reste distincte lorsque le runtime la représente comme possibilité externe plutôt que comme Activity opérée ; un Space peut y être relié sans que cela transforme Opportunity en archetype.

Principe :

> **Activity décrit ce que l’acteur fait. SpaceArchetype décrit comment l’acteur fonctionne.**

Il n’existe donc aucune correspondance 1:1 entre archetype et verticale.

---

# 11. SpaceArchetype

SpaceArchetype est le **centre de gravité opérationnel durable** d’un Space.

Il n’est jamais :

- une Permission ;
- un Mandate ;
- un Entitlement ;
- un Topic ;
- une forme juridique ;
- une verticale d’Activity ;
- une liste de fonctionnalités autorisées.

Les huit archétypes initiaux sont :

~~~text
generic
creative
media
education
commerce
service_provider
transport_operator
community
~~~

Cette liste doit rester courte.

---

# 12. Critère pour ajouter un nouvel archetype

Un nouvel archetype n’est justifié que si :

1. il correspond à une manière durable et largement reconnaissable de fonctionner ;
2. cette manière change réellement les domaines et configurations normalement utiles dans Makolo ;
3. cette différence ne peut pas être exprimée correctement par un archetype existant, des Activities, Topics, OpenTo, relations métier ou autres faits canoniques.

Ne pas ajouter automatiquement restaurant, hotel, shop, consultant, agency, school, university, NGO, club, band, newspaper, photographer, doctor, lawyer, rental company, etc.

---

# 13. Contrat commun de configuration

Chaque archetype est défini avec les mêmes huit dimensions :

~~~text
1. définition
2. centre de gravité
3. vocabulaire métier conceptuel
4. domaines Makolo prioritaires
5. domaines transversaux utiles
6. verticales naturellement proposées
7. configurations métier normalement utiles
8. faits à ne jamais créer automatiquement
~~~

Cette configuration est un preset conceptuel. Elle ne crée aucune vérité métier.

---

# 14. generic

1. **Définition** — organisation généraliste, multidomaine ou sans centre de gravité spécialisé.
2. **Centre de gravité** — organiser et opérer des Activities sans hypothèse métier dominante.
3. **Vocabulaire conceptuel** — Espace, Activités, Demandes, Contacts, Groupes, Lieux, Équipe.
4. **Domaines prioritaires** — Activity/Occurrence, Journey/Requests, Groups, CRM/Audiences, Geography/Places.
5. **Transversaux utiles** — Commerce/Payments selon usage, Trust, Analytics, Automation, Subscription, Team.
6. **Verticales naturellement proposées** — Event, Service, Obtention, Transport ; Funding lorsqu’il correspond au besoin réel.
7. **Configuration normalement utile** — identité, première Activity, lieux/zones nécessaires, équipe, contacts/groupes lorsqu’ils existent réellement.
8. **Ne crée jamais automatiquement** — Activity, contact, groupe, Offer, Requirement, Journey ou autre fait métier.

generic n’est jamais une édition réduite de Makolo.

---

# 15. creative

1. **Définition** — artiste, collectif créatif, studio ou structure principalement tournée vers création/production artistique.
2. **Centre de gravité** — créer, présenter, faire vivre, prester et éventuellement commercialiser.
3. **Vocabulaire conceptuel** — Créations, Activités, Événements, Prestations, Publics, Partenaires, Offres.
4. **Domaines prioritaires** — Activity/Occurrence, Event, Service, Obtention, CRM/Audiences, Partners.
5. **Transversaux utiles** — Promotions, Growth, Commerce, Payments, Loyalty, Trust, Analytics, Automation, Team.
6. **Verticales naturellement proposées** — Event, Service, Obtention ; Transport lorsque réellement utilisé.
7. **Configuration normalement utile** — identité créative, Activities, Occurrences/Event, prestations réelles, offres/Obtention, publics, partenaires, paiements lorsque nécessaires.
8. **Ne crée jamais automatiquement** — feed, Post, Story, portfolio parallèle, média orphelin, faux public, fausse prestation ou offre.

No Orphan Content / No Orphan Media reste applicable.

---

# 16. media

1. **Définition** — média, rédaction, organisation journalistique ou structure de production éditoriale/informationnelle.
2. **Centre de gravité** — produire, documenter, organiser des publics, travailler avec des partenaires et opérer des activités éditoriales, événementielles ou de service.
3. **Vocabulaire conceptuel** — Productions, Activités, Événements, Audiences, Publics, Partenaires, Références.
4. **Domaines prioritaires** — Activity, Event, CRM/Audiences, Groups, Partners, Trust.
5. **Transversaux utiles** — Promotions, Growth, Commerce/Payments si nécessaires, Analytics, Automation, Team.
6. **Verticales naturellement proposées** — Event, Service, Obtention ; Transport lorsqu’il est pertinent.
7. **Configuration normalement utile** — identité éditoriale, productions/Activities, audiences/groupes, partenaires, Trust/références, prestations ou commerce réellement opérés.
8. **Ne crée jamais automatiquement** — timeline générique, feed infini, métriques sociales comme vérité centrale, source journalistique transformée en CRMContact, contenu sans contexte ni finalité.

---

# 17. education

1. **Définition** — école, université, centre de formation ou acteur principalement structuré autour de l’enseignement et de la transmission.
2. **Centre de gravité** — programmes, sessions, demandes/inscriptions, conditions, ressources et participation réelle.
3. **Vocabulaire conceptuel** — Programmes, Sessions, Inscriptions, Conditions, Formulaires, Ressources, Groupes.
4. **Domaines prioritaires** — Activity/Occurrence, Journey/Requests, Requirements, Questionnaires/Forms, Resources, Groups, Access.
5. **Transversaux utiles** — CRM/Audiences, Commerce/Payments, Geography/Places, Trust, Analytics, Automation, Team.
6. **Verticales naturellement proposées** — Service, Event, Obtention, Transport.
7. **Configuration normalement utile** — programme/Activity, sessions, Requirements, questionnaires, Resources, groupes/cohortes réels, tarifs/paiements, lieux, équipe.
8. **Ne crée jamais automatiquement** — cours, apprenant, promotion, Requirement, questionnaire, Access ou autorité pédagogique fictifs.

---

# 18. commerce

1. **Définition** — acteur principalement structuré autour de vente, distribution, location ou fourniture de biens, ressources ou droits d’usage.
2. **Centre de gravité** — proposer, faire obtenir, commander, payer et remettre/rendre disponible.
3. **Vocabulaire conceptuel** — Offres, Obtention, Commandes, Paiements, Disponibilité, Clients, Promotions.
4. **Domaines prioritaires** — Obtention, Activity, Offers, Orders, Payments, Capacity lorsque pertinente.
5. **Transversaux utiles** — CRM/Audiences, Promotions, Loyalty, Growth, Geography/Places, Trust, Analytics, Automation, Team.
6. **Verticales naturellement proposées** — Obtention, Service, Event, Transport.
7. **Configuration normalement utile** — cible d’Obtention, mode acheter/louer/emprunter/recevoir/échanger, Offer/prix, disponibilité/capacité, lieux de retrait/remise, paiements, CRM.
8. **Ne crée jamais automatiquement** — Product/Inventory générique parallèle, commande, paiement, stock ou Obtention accomplie fictifs.

Une commande ou un paiement ne suffit jamais à conclure automatiquement l’Obtention.

---

# 19. service_provider

1. **Définition** — entreprise, cabinet, professionnel ou organisation principalement structurée autour de prestations.
2. **Centre de gravité** — recevoir une demande, préparer, exécuter/traiter/délivrer et constater le résultat.
3. **Vocabulaire conceptuel** — Prestations, Demandes, Dossiers, Clients, Conditions, Tarifs, Lieux/Zones.
4. **Domaines prioritaires** — Service, Activity, Journey/Requests/Dossiers, Requirements, Offers, Orders, Payments, CRM.
5. **Transversaux utiles** — Questionnaires/Forms, Geography/Places/Zones, Trust, Promotions, Analytics, Automation, Team.
6. **Verticales naturellement proposées** — Service, Event, Obtention, Transport ; Funding lorsqu’une vraie Activity le justifie.
7. **Configuration normalement utile** — prestation, procédure de demande, Requirements, formulaire éventuel, Offer/tarif, lieux/zones, modalités de réalisation, équipe, CRM.
8. **Ne crée jamais automatiquement** — Service, client, tarif, Requirement, dossier, Journey ou contact fictifs.

---

# 20. transport_operator

1. **Définition** — organisation principalement structurée autour de l’exploitation de transport.
2. **Centre de gravité** — routes, services, départs, véhicules, capacité, accès et exploitation.
3. **Vocabulaire conceptuel** — Routes, Services, Départs, Véhicules, Lieux, Voyageurs, Tarifs, Contrôle.
4. **Domaines prioritaires** — TransportRoute, TransportService, Departure, Vehicle, Activity/Occurrence, Geography/Places, Capacity, Access/Control.
5. **Transversaux utiles** — Offers, Orders, Payments, Operations, CRM, Trust, Analytics, Automation, Team.
6. **Verticales naturellement proposées** — Transport, Service, Event, Obtention.
7. **Configuration normalement utile** — lieux/stops, Route, TransportService, véhicules, Departure, Capacity, Offer/tarif, Access/control, équipe.
8. **Ne crée jamais automatiquement** — Route, Vehicle, Departure, tarif, Access, voyageur ou Mandate.

transport_operator signifie que Transport est le centre de gravité du Space. Il ne signifie pas que les autres archetypes sont interdits d’utiliser Transport.

---

# 21. community

1. **Définition** — association, ONG, club, fondation ou acteur principalement structuré autour d’une mission et d’une communauté. Ce n’est pas une classification juridique.
2. **Centre de gravité** — mission, activités, groupes, publics, partenaires, mobilisation et financement lorsqu’il est pertinent.
3. **Vocabulaire conceptuel** — Initiatives, Activités, Groupes, Publics, Partenaires, Financement, Reconnaissance.
4. **Domaines prioritaires** — Activity/Event, Groups, CRM/Audiences, Funding, Partners.
5. **Transversaux utiles** — Recognition, Trust, Promotions, Growth, Analytics, Automation, Team, Commerce/Payments lorsqu’ils sont réellement utilisés.
6. **Verticales naturellement proposées** — Event, Service, Funding, Obtention ; Transport lorsque pertinent.
7. **Configuration normalement utile** — mission/identité, Activity, groupes, publics/contacts, partenaires, Funding réel, Trust/reconnaissance, équipe.
8. **Ne crée jamais automatiquement** — adhésion juridique depuis GroupMembership, collecte Funding, bénéficiaire, partenaire, statut légal ou relation sociale générique.

---

# 22. Archetype ne limite jamais les verticales

Un archetype décrit la manière principale de fonctionner, pas l’ensemble des choses que le Space peut faire.

~~~text
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
├── Obtention
└── Transport
~~~

Un Space peut devenir très multidomaine sans devenir plusieurs Spaces ni plusieurs archetypes.

---

# 23. Archetype vs réalité opérationnelle

Décision structurante :

~~~text
ARCHETYPE
= centre de gravité durable

OPERATIONAL FOOTPRINT
= ce que le Space utilise réellement
~~~

L’empreinte opérationnelle est dérivée des faits canoniques.

Exemples :

~~~text
Transport
→ Routes / Services / Vehicles / Departures

Service
→ faits Service

Obtention
→ faits Obtention

CRM
→ contacts / audiences réellement présents

Automation
→ règles existantes

Funding
→ faits Funding

Commerce
→ Offers / Orders

Access
→ Access / AccessUse
~~~

Exemple :

~~~text
Space.archetype = commerce

Operational Footprint:
Obtention ✓
Service ✓
Transport ✓
Event ✓
CRM ✓
Payments ✓
~~~

Le Space reste commerce.

L’empreinte peut éventuellement être matérialisée plus tard comme projection reconstructible pour performance, mais elle ne devient pas une vérité métier autonome.

---

# 24. Pas de SpaceCapability générique

Makolo possède déjà plusieurs notions de capacité :

~~~text
Permission / Mandate
→ ce qu'une personne peut faire

Subscription / Entitlement
→ ce que le produit rend disponible

Interop capabilities
→ ce qu'un système/provider sait faire

Domain facts
→ ce que le Space utilise réellement
~~~

Créer un registre universel SpaceCapability(space, code, enabled) risquerait de créer une vérité parallèle.

Décision :

> Aucun concept persistant générique SpaceCapability n’est introduit tant qu’un cas irréductible ne le justifie.

---

# 25. Changement d’archetype

Le changement d’archetype est autorisé.

~~~text
generic → service_provider
creative → commerce
community → generic
~~~

Un changement d’archetype ne modifie jamais implicitement :

- Activities ;
- Occurrences ;
- Journeys ;
- Requirements ;
- Routes ;
- Vehicles ;
- Access ;
- CRM ;
- Orders ;
- Payments ;
- Groups ;
- Mandates ;
- Entitlements ;
- faits Trust ;
- historique Analytics.

Il change le centre de gravité du Space, pas son histoire métier.

Aucune classification ne doit être modifiée silencieusement à partir du nom, des Topics, de l’usage, de l’historique ou de comportements observés.

---

# 26. Relations entre Spaces

Un Space peut collaborer avec d’autres Spaces au travers de relations métier explicites.

~~~text
Space A partenaire de Space B
Space A finance une Activity de B
Space C opère Transport pour une Activity
Space D fournit un Service
~~~

Ces relations doivent utiliser les domaines compétents : Partners, Funding, Activity, Sharing, Commerce, Trust ou autres relations métier démontrées.

Ne pas introduire par défaut un graphe social générique entre Spaces.

Une relation entre Spaces ne transfère jamais implicitement :

~~~text
Permission
Mandate
Access
Entitlement
Payment
données privées
~~~

---

# 27. Space comme nœud du réseau d’action

Un Space est une identité. Les rôles qu’il joue sont contextuels.

Un même Space peut être organisateur d’un Event, opérateur d’un Transport, prestataire d’un Service, fournisseur d’une Obtention, partenaire d’un autre Space, acteur d’un Funding ou émetteur d’un Credential.

~~~text
SPACE
!=
RÔLE DU SPACE DANS UNE RELATION
~~~

Cette règle permet au réseau d’action de se composer sans transformer les rôles contextuels en identités rigides.

---

# 28. CRM et relations

CRM est transversal, mais ne devient pas la vérité universelle de toutes les relations du Space.

~~~text
CRMContact
!= TeamMember
!= GroupMember
!= Partner
!= Mandate holder
!= follower
!= participant
~~~

CRM peut organiser une relation client/prospect/contact lorsqu’elle existe, mais ne remplace jamais les domaines propriétaires.

---

# 29. Analytics, Automation et Entitlements

Analytics et Automation sont des capacités transversales utilisables par tous les archetypes.

L’archetype peut déterminer quelles dimensions sont normalement pertinentes, mais il ne crée pas de moteurs séparés CreativeAnalytics, EducationAnalytics, CommerceAutomation, etc.

La disponibilité produit reste distincte de l’archetype :

~~~text
SpaceArchetype
→ manière de fonctionner

Entitlement
→ capacité produit disponible

Permission / Mandate
→ autorité humaine
~~~

Un archetype n’accorde aucun Entitlement, et un Entitlement n’accorde aucune Permission.

---

# 30. Public, privé et divulgation

Un Space peut avoir une projection publique, mais son existence ne rend pas toutes ses informations publiques.

~~~text
identité canonique
!=
projection publique
!=
données opérationnelles privées
!=
données sensibles
~~~

Une projection collective doit toujours appliquer la divulgation minimale.

CRM, Analytics internes, Mandates, équipe complète, incidents, Payments, Automation et autres données privées ne deviennent jamais publics par simple composition.

Presentation représente les faits ; elle ne les possède pas.

---

# 31. Archivage et histoire

L’histoire d’un Space appartient à son identité durable.

Archiver un Space ne transforme pas ses anciens faits en faux faits.

Doivent rester interprétables selon leurs propres domaines :

- Activities passées ;
- Occurrences ;
- Journeys ;
- AccessUse ;
- Orders ;
- Payments ;
- relations historiques ;
- Analytics ;
- audits ;
- responsabilités historiques lorsque la politique de conservation le permet.

L’archivage arrête l’exploitation active ; il n’efface pas le passé.

---

# 32. Anti-features

Space ne doit pas devenir :

- un compte utilisateur collectif ;
- un second Profile ;
- un conteneur universel de tous les domaines métier ;
- une taxonomie exhaustive de professions ;
- une Permission implicite ;
- un système d’Entitlements ;
- une whitelist de verticales ;
- un réseau social générique d’organisations ;
- un feed générique ;
- un mécanisme de popularité ;
- un clone de CRM ;
- un clone d’Analytics ;
- un clone d’Automation ;
- un clone de Commerce ;
- un clone de Transport ;
- un task manager générique ;
- un moyen d’inférer silencieusement l’autorité ou des données privées.

---

# 33. Invariants consolidés

1. Un Space est une identité collective durable.
2. Un Profile reste une personne humaine globale.
3. Un Space n’a pas de login autonome.
4. Une Activity possède exactement un opérateur logique : Profile XOR Space.
5. Le créateur historique n’est pas l’autorité éternelle.
6. Ownership et responsabilités sont exprimés par Mandates.
7. Le dernier Owner actif est protégé.
8. TeamMembership signifie collaboration, pas autorité.
9. GroupMembership signifie appartenance/ciblage, pas autorité.
10. Topic décrit un sujet, pas la nature du Space.
11. SpaceOpenTo décrit un consentement à certaines sollicitations, pas la nature du Space.
12. SpaceArchetype décrit la manière principale de fonctionner.
13. SpaceArchetype n’est ni une verticale, ni une Permission, ni un Entitlement.
14. Un archetype ne limite jamais les verticales que le Space peut opérer.
15. Les huit archetypes initiaux restent volontairement larges.
16. Un nouvel archetype exige une distinction opérationnelle réellement structurante.
17. Les faits métier restent propriétaires de leurs domaines.
18. L’Operational Footprint est dérivée des faits canoniques.
19. Il n’existe pas de SpaceCapability générique tant qu’un besoin irréductible ne le justifie pas.
20. Changer d’archetype est non destructif.
21. Lifecycle, Verification et éventuelle Readiness restent distincts.
22. Archiver conserve l’histoire.
23. Une composition entre Spaces ne transfère aucun droit implicitement.
24. CRM ne remplace pas Team, Group, Partner ou Mandate.
25. Analytics et Automation restent transversaux.
26. Toute projection collective applique la divulgation minimale.
27. Presentation représente les faits ; elle ne les possède pas.
28. Le réseau entre Spaces émerge de relations d’action réelles, pas d’un graphe social artificiel.

---

# 34. Décisions fermées

À l’issue de cette consolidation, les questions suivantes sont considérées comme fermées :

~~~text
✓ définition de Space
✓ critère de création d'un Space
✓ frontière Profile / Space
✓ responsabilité canonique
✓ identité minimale
✓ lifecycle ACTIVE / SUSPENDED / ARCHIVED
✓ séparation lifecycle / verification
✓ création et provenance humaine
✓ ownership via Mandates
✓ protection du dernier Owner
✓ Team / Group / Mandate
✓ distinction Topic / OpenTo / Archetype
✓ relation Space / Activity
✓ 8 archetypes initiaux
✓ contrat commun de configuration
✓ configuration des 8 archetypes
✓ absence de whitelist de verticales
✓ archetype vs Operational Footprint
✓ absence de SpaceCapability générique
✓ changement d'archetype non destructif
✓ composition entre Spaces
✓ public / privé / divulgation minimale
✓ relations avec CRM, Analytics, Automation et Entitlements
✓ anti-features et invariants
~~~

---

# 35. Hors périmètre de cette spécification

Ce document ne décide volontairement pas :

- « Maintenant » du Space ;
- « en cours » ;
- dashboard ;
- cartes ou KPI ;
- navigation finale ;
- wording final des écrans ;
- responsive ;
- mobile ;
- notifications ;
- suggestions intelligentes ;
- modèles Django finaux ;
- tables ;
- migrations ;
- APIs finales ;
- stratégie de cache ;
- matérialisation éventuelle des projections dérivées.

La suite doit utiliser cette spécification pour déterminer ce qui relève du domaine persistant, des projections dérivées ou de la configuration produit, sans rouvrir les principes fondamentaux de Space sauf contradiction démontrée avec le runtime ou le Domain Blueprint.


---

# 36. Décisions de traduction architecture/runtime

Cette section décide ce qui doit réellement être persistant, dérivé ou configuré à partir de la spécification ci-dessus. Elle ne fixe pas encore les écrans ni l'UX.

## 36.1 État persistant propre à Space

Le noyau Space ne nécessite, à ce stade, que deux nouvelles vérités persistantes au-delà de l'identité déjà présente :

~~~text
Organization.archetype
Organization.lifecycle
~~~

### archetype

- valeur explicite choisie pour le Space ;
- huit valeurs initiales définies dans ce document ;
- fallback sûr : generic ;
- modifiable explicitement ;
- aucun changement implicite depuis Topics, Activities ou historique ;
- aucun effet d'autorité ni d'Entitlement.

### lifecycle

Valeurs :

~~~text
ACTIVE
SUSPENDED
ARCHIVED
~~~

Default pour les Espaces existants qui ne sont pas historiquement suspendus : ACTIVE.

Aucun autre état persistant générique de préparation n'est ajouté.

## 36.2 Aucun nouveau modèle Space de configuration

Ne pas créer :

~~~text
SpaceSettings
SpaceCapability
SpaceModule
SpaceFeature
SpaceOperatingProfile
SpaceOwner
SpaceArchetypeHistory
SpaceLifecycleHistory
~~~

à ce stade.

Justification :

- les presets sont dérivables de l'archetype ;
- l'Operational Footprint est dérivable des faits métier ;
- l'ownership est déjà exprimé par Mandate ;
- les Entitlements existent déjà ;
- Operations/Domain Events possèdent déjà les mécanismes nécessaires pour tracer les décisions importantes ;
- créer ces modèles ajouterait des vérités parallèles.

Si un besoin futur irréductible apparaît, il devra être démontré domaine par domaine avant ajout d'un nouvel état.

## 36.3 Presets d'archetype = configuration Python dérivée

Le preset opérationnel reste une configuration de code immutable/versionnée avec le produit, du type conceptuel :

~~~text
SpaceOperatingPreset
├── archetype
├── labels conceptuels
├── domains prioritaires
├── domains transversaux
├── suggested_verticals
└── configuration hints
~~~

Il n'est pas stocké par Space.

Le fichier actuellement utilisé sur la branche peut rester dans organizations comme couche d'orchestration produit tant qu'il :

- ne possède aucune vérité métier ;
- ne crée aucun fait ;
- ne décide aucune Permission ;
- ne décide aucun Entitlement.

Il n'est pas nécessaire de créer un bounded context Presentation uniquement pour stocker cette table de correspondance.

## 36.4 Operational Footprint = read model dérivé

L'Operational Footprint devient un read model reconstructible.

Cible conceptuelle :

~~~text
SpaceOperationalFootprint
= ensemble des domaines/verticales réellement présents pour un Space
~~~

Il doit être calculé depuis les owners canoniques, par exemple :

~~~text
Activity / verticales
Transport facts
Service facts
Obtention facts
Funding facts
CRM
Groups
Partners
Commerce
Payments
Access
Automation
Loyalty
Trust
...
~~~

Aucune table source de vérité n'est créée.

Une matérialisation/cache pourra être ajoutée uniquement pour performance, à condition d'être explicitement reconstructible et invalidable depuis les faits canoniques.

## 36.5 Lifecycle : séparation progressive de l'ancien verification_status

Le runtime actuel surcharge encore Organization.verification_status avec une valeur suspended utilisée par de nombreux consommateurs publics et Operations.

Cette ambiguïté doit être corrigée sans migration destructive.

Décision de transition :

1. ajouter Organization.lifecycle avec ACTIVE par défaut ;
2. lors de la migration initiale, tout Space dont verification_status vaut suspended reçoit lifecycle=SUSPENDED ;
3. conserver temporairement OrganizationVerificationStatus.SUSPENDED comme valeur de compatibilité ;
4. migrer progressivement les décisions d'exploitation et les selectors de visibilité vers lifecycle ;
5. Trust continue à posséder les VerificationClaim ;
6. une décision de vérification rejetée/révoquée ne doit plus, à terme, signifier automatiquement suspension opérationnelle ;
7. seule une décision explicite de gouvernance/modération peut faire passer le lifecycle à SUSPENDED ;
8. supprimer la valeur legacy suspended de verification_status seulement après disparition de tous ses consommateurs.

Ainsi :

~~~text
Trust decision
!=
lifecycle decision
~~~

même si le runtime historique les a parfois couplées.

## 36.6 Historique de lifecycle : réutiliser Operations et Domain Events

Aucun modèle SpaceLifecycleHistory n'est nécessaire.

Les transitions sensibles doivent passer par des services transactionnels et produire les traces déjà prévues par Makolo :

- audit Operations lorsque la transition relève de modération/gouvernance ;
- Domain Event lorsque nécessaire pour informer les autres domaines/projections ;
- actor humain conservé pour toute mutation autorisée.

Le champ Organization.lifecycle porte l'état courant ; les mécanismes d'audit portent l'histoire.

## 36.7 Ownership : aucun nouveau modèle

Le runtime possède déjà la structure correcte :

~~~text
created_by
= provenance historique

TeamMembership
= collaboration

Mandate SPACE_OWNER
= ownership actuel
~~~

Décision :

- ne pas créer primary_owner ;
- ne pas créer SpaceOwner ;
- conserver plusieurs Owners possibles ;
- conserver l'invariant du dernier Owner.

Une opération de transfert mérite en revanche un **service d'orchestration atomique** dédié, pas un modèle :

~~~text
transfer_space_ownership(...)
~~~

Son contrat devra :

1. verrouiller le Space et les Mandates d'ownership concernés ;
2. vérifier SPACE_OWNERSHIP_MANAGE ;
3. accorder d'abord l'ownership au destinataire ;
4. révoquer l'ancien Owner uniquement si demandé ;
5. préserver l'invariant d'au moins un Owner ;
6. tracer actor, source et résultat.

Les primitives d'autorisation existantes restent propriétaires des Mandates.

## 36.8 CRM : garder l'ownership actuel

Le runtime actuel est déjà correct :

~~~text
CRMContact.organization
Audience.organization
CRMInteraction.activity (optionnel)
~~~

Décision :

- le CRM appartient au Space ;
- une Activity peut contextualiser une interaction CRM ;
- ne pas créer de CRMContact appartenant simultanément à une Activity ;
- ne pas dupliquer un contact par archetype ;
- Team, Group, Partner et Mandate restent distincts du CRM.

Aucun nouveau modèle Space n'est requis ici.

## 36.9 Geography : SpacePlace est la relation métier

Le runtime possède déjà SpacePlace avec des rôles comme siège, bureau, agence/succursale et point de service.

Décision :

~~~text
Organization.country / city
= identité générale / compatibilité / présentation grossière

SpacePlace + Place
= géographie structurée réelle du Space
~~~

Les lieux des Activities/Occurrences restent leurs propres faits.

Ne pas enrichir Organization avec des listes d'adresses, zones, agences ou stops.

## 36.10 Trust : VerificationClaim est canonique

Le runtime possède déjà VerificationClaim.subject_space.

Décision :

- Trust possède les assertions de vérification ;
- Organization.verification_status reste une projection legacy de compatibilité pendant la transition ;
- ne pas créer SpaceVerification ou champs de confiance supplémentaires dans Organization ;
- lifecycle reste séparé de Trust.

## 36.11 Subscriptions / Entitlements : réutiliser l'existant

FeatureDefinition sait déjà cibler un Space et les Entitlements définissent la disponibilité produit.

Décision :

- aucun Entitlement n'est dérivé automatiquement de l'archetype ;
- aucun archetype ne contourne un FeatureDefinition ;
- ne pas créer SpacePlan, ArchetypeCapability ou FeatureSet parallèle dans organizations.

## 36.12 Activity : conserver l'ownership XOR existant

Le runtime possède déjà :

~~~text
Activity.space
XOR
Activity.owner_profile
~~~

Décision :

- aucune table intermédiaire SpaceActivity n'est nécessaire ;
- Space reste opérateur logique direct lorsqu'une Activity appartient à l'organisation ;
- l'archetype n'intervient pas dans l'ownership Activity ;
- ne pas durcir immédiatement les anciennes données legacy sans audit préalable des lignes historiques qui pourraient encore n'avoir aucun owner logique.

## 36.13 Relations entre Spaces : pas de relation universelle

Ne pas créer SpaceRelation ou SpaceComposition générique.

Réutiliser les relations propriétaires :

- Partners pour partenariat ;
- Funding pour financement ;
- Sharing pour partage ;
- Activity lorsque plusieurs acteurs ont des rôles dans une action selon les contrats du domaine ;
- Trust pour attestations ;
- Commerce pour relations économiques lorsque pertinent.

Un besoin de nouvelle relation doit d'abord trouver son owner métier.

## 36.14 Services lifecycle centralisés

Pour éviter des vérifications dispersées, le runtime devra disposer de services/selectors Space explicites, conceptuellement :

~~~text
space_is_operational(space)
require_space_operational(space)
suspend_space(...)
archive_space(...)
restore_space(...)
~~~

Les domaines consommateurs ne doivent pas réinventer chacun la signification de ACTIVE/SUSPENDED/ARCHIVED.

Les décisions d'autorité de ces services doivent utiliser les Permissions/Mandates existants ou la gouvernance Platform selon la cause de transition.

## 36.15 Résumé de classification

| Besoin | Décision |
| --- | --- |
| Archetype courant | Persistant sur Space |
| Lifecycle courant | Persistant sur Space |
| Preset d'archetype | Configuration Python dérivée |
| Operational Footprint | Read model dérivé |
| Capability métier du Space | Dérivée des faits / Entitlements / Permissions selon le sens |
| Ownership | Mandates existants |
| Historique ownership | Mandates/audit existants |
| Historique lifecycle | Operations audit + Domain Events |
| Vérification | Trust VerificationClaim |
| Géographie structurée | Geography SpacePlace |
| CRM | CRM existant, owner Space |
| Subscription | Subscriptions/Entitlements existants |
| Verticales Activity | Domaines Activity existants |
| Relations Space ↔ Space | Domaines métier existants |
| Readiness | Projection dérivée si un jour nécessaire |
| Configuration UX | Hors de cette spécification |

## 36.16 Ordre d'implémentation retenu

La suite doit être réalisée dans cet ordre :

1. **Foundation** — Organization.archetype + Organization.lifecycle + migration de compatibilité ;
2. **Lifecycle cutover** — services/selectors centralisés et migration progressive des usages legacy de verification_status=SUSPENDED ;
3. **Ownership orchestration** — service atomique de transfert, en réutilisant Mandates ;
4. **Operating preset** — finaliser la configuration dérivée sans nouveau modèle ;
5. **Operational Footprint** — selector/read model dérivé des domaines existants ;
6. **Consumers** — seulement ensuite faire consommer ces contrats par Console, API et futures expériences.

Aucun autre modèle Space n'est autorisé par défaut dans ce cycle sans démonstration d'un besoin que les domaines existants ne peuvent pas porter.


## 36.17 État runtime livré par le chantier #252

Le runtime correspondant à cette spécification utilise désormais :

~~~text
Organization.archetype
Organization.lifecycle = ACTIVE | SUSPENDED | ARCHIVED
~~~

La migration Organizations `0006_organization_lifecycle` initialise les anciens
Espaces `verification_status=SUSPENDED` en `lifecycle=SUSPENDED` sans supprimer
la valeur legacy de vérification. Les autres anciens Espaces restent `ACTIVE`.

La séparation est désormais explicite :

~~~text
Trust VerificationClaim
= vérité de vérification

Organization.lifecycle
= état opérationnel du Space
~~~

Une révocation Trust ne suspend plus automatiquement le Space. La suspension
opérationnelle relève de la gouvernance Platform et passe par les services
lifecycle canoniques.

Le transfert d'ownership est assuré par `transfer_space_ownership(...)` :

- verrouillage du Space et du Membership cible ;
- vérification de `SPACE_OWNERSHIP_MANAGE` ;
- attribution de `SPACE_OWNER` au destinataire avant toute renonciation ;
- maintien de l'ancien Owner comme `SPACE_ADMIN` lorsqu'il renonce ;
- conservation de l'invariant du dernier Owner ;
- audit Operations ;
- aucune modification implicite des Groups, autres Spaces ou Mandates Activity.

`SpaceOperatingPreset` reste dérivé dans le code. `SpaceOperationalFootprint`
est un read model dérivé de faits appartenant aux domaines propriétaires ; aucune
table `SpaceCapability` ou copie persistante des modules utilisés n'est créée.

Le contrat Workspace API expose, sous autorité serveur :

- identité utile, archetype, lifecycle et visibilité publique ;
- projection Trust publique minimale ;
- capabilities calculées ;
- preset et footprint lorsque l'autorité Space le permet ;
- résumés Team/ownership minimaux ;
- création/mise à jour ;
- archive/restore ;
- opérations Team/member ;
- transfert d'ownership.

Les mutations sensibles restent online et sont confirmées par le serveur. Le
client mobile peut conserver un snapshot local de ces projections, mais ne
devient jamais autorité pour lifecycle, ownership, Permission, Mandate ou Trust.
