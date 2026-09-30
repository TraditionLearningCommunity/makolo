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
