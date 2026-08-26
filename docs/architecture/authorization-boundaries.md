# Frontières d'autorisation Makolo

Makolo est multi-Espaces. Une appartenance à une Équipe ne donne jamais, à elle seule, accès aux données privées de l'Espace. L'autorité métier runtime est désormais basée sur **Role + Permission + Mandate** conformément au [Domain Blueprint](makolo-domain-blueprint.md).

## Principe runtime

L'identité est globale ; l'autorité est contextuelle. Une décision d'autorisation doit répondre à **qui peut faire quoi, et où ?**

La source canonique est :

```text
Profil + Rôle + Portée = Mandat
```

Les portées réellement implémentées sont désormais :

- `platform` — plateforme Makolo ;
- `space` — un Espace précis, techniquement encore représenté par `organizations.Organization` ;
- `group` — un Groupe précis, représenté par `groups.Group` ;
- `activity` — une Activity précise, représentée par `activities.Activity`.

Aucun `ContentType` ou `GenericForeignKey` n'est utilisé pour simuler ces portées.

`TeamMembership` exprime uniquement la collaboration dans une Équipe. Il ne porte aucune Permission. Les actions d'équipe créent transactionnellement la `TeamMembership` et le `Mandate` correspondant afin de conserver une UX simple sans confondre appartenance et autorité.

`GroupMembership` exprime uniquement l'appartenance d'un Profil à une population. Il ne porte lui non plus aucune Permission. L'administration d'un Groupe passe par un Mandat Groupe explicite ou, pour un Groupe appartenant à un Espace, par la règle d'héritage `space.groups.*` décrite plus bas.

## Staff Django et autorité Makolo

`is_staff` conserve sa signification Django : accès potentiel au Django Admin selon les permissions techniques. Il n'est plus un raccourci métier global vers toutes les données de tous les Espaces.

Les comptes staff qui existaient lors de la migration reçoivent un Mandat plateforme `Administrateur Makolo` afin de préserver leur comportement métier historique. Un nouveau compte créé avec seulement `is_staff=True` ne reçoit pas automatiquement cette autorité. `is_superuser` reste le privilège technique ultime et est reconnu explicitement par le résolveur d'autorisation.

Operations utilise désormais la Permission plateforme explicite plutôt que `is_staff` comme autorité métier.

## Rôles système Espace

Les anciens `OrganizationRole` sont mappés vers les rôles système canoniques suivants :

| Ancien rôle | Rôle canonique |
|---|---|
| `OWNER` | Propriétaire d'Espace |
| `ADMIN` | Administrateur d'Espace |
| `EVENT_MANAGER` | Responsable activité |
| `FINANCE` | Finance |
| `MARKETING` | Marketing / Communication |
| `SCANNER_MANAGER` | Responsable accès |

Le Propriétaire et l'Administrateur conservent les capacités opérationnelles larges existantes. La propriété reste cependant spéciale : la Permission `space.ownership.manage` appartient au Propriétaire, pas à l'Administrateur. Un Espace doit toujours conserver au moins un Mandat propriétaire actif.

## Rôles système Groupe

Le bounded context `groups` introduit trois responsabilités administratives simples :

| Rôle | Responsabilité |
|---|---|
| `group-owner` | Administration complète et transfert de propriété d'un Groupe personnel |
| `group-admin` | Informations, membres, invitations et snapshots, sans transfert de propriété |
| `group-moderator` | Lecture et gestion courante des membres |

Il n'existe volontairement **aucun rôle « membre »**. Être membre est un `GroupMembership`, pas un Mandat.

Les Permissions Groupe stables sont notamment :

```text
group.view
group.manage
group.members.view
group.members.manage
group.invitations.manage
group.snapshots.create
group.ownership.manage
```

Les Permissions Espace qui gouvernent les Groupes appartenant à un Espace sont :

```text
space.groups.view
space.groups.manage
```

Elles sont composées dans les rôles système Propriétaire/Admin d'Espace ; elles ne sont pas accordées automatiquement à tous les membres d'une Équipe.

### T27 — utiliser un Groupe dans une Activity

La découvrabilité, l'adhésion et le droit de cibler un Groupe sont trois décisions séparées. Un Groupe `LISTED` et `OPEN` n'est pas pour autant un canal que n'importe quel organisateur peut exploiter.

`ActivityGroupEligibility` relie explicitement une Activity et un Groupe. La création ou l'approbation de cette relation ne transfère aucune autorité entre les deux objets :

- le demandeur doit avoir `activity.manage` sur l'Activity exacte ;
- l'autorisation du Groupe exige `group.manage` sur le Groupe exact, ou l'héritage documenté `space.groups.manage` lorsque ce Groupe appartient à cet Espace ;
- lorsque la même personne possède les deux autorités, l'utilisation peut être approuvée immédiatement ;
- sinon la relation reste `requested` jusqu'à une décision du côté Groupe ;
- connaître l'UUID d'un Groupe ne suffit jamais pour l'attacher à une Activity ;
- être `GroupMembership.ACTIVE` rend éventuellement un Profil éligible à l'action, mais ne lui donne jamais `group.manage` ni `activity.manage`.

L'éligibilité ne crée ni Mandat, ni TeamMembership, ni Access, ni export CRM. Elle vérifie seulement, au point d'entrée métier concerné, qu'un bénéficiaire est membre actif d'au moins un Groupe approuvé. Un Access déjà acquis conserve son propre cycle et n'est pas révoqué automatiquement si l'appartenance change ensuite.

## Matrice minimale

| Domaine | Propriétaire/Admin | Responsable activité | Finance | Marketing | Responsable accès | Profil utilisateur |
|---|---:|---:|---:|---:|---:|---:|
| Créer/modifier événements | Oui | Oui | Non | Non | Non | Oui, uniquement pour ses Activities personnelles via Mandat Activity |
| Types de billets | Oui | Oui | Non | Non | Non | Public uniquement |
| Commandes / identité client | Oui | Oui | Oui | Non | Non | Ses commandes |
| Paiements / remboursements | Oui | Non | Oui | Non | Non | Ses paiements |
| Billets / identité titulaire | Oui | Oui | Non | Non | Oui | Ses billets |
| Scanner / journaux d'accès | Oui | Oui | Non | Non | Oui | Non |
| Groupes de l'Espace | Oui | Non | Non | Non | Non | Selon appartenance/Mandat Groupe |
| Partenaires / campagnes d'affiliation | Oui | Non | Finance partenaire seulement | Oui | Non | Son portail partenaire si lié |
| Promotions — règles/codes | Oui | Lecture | Lecture | Oui | Non | Utilisation au checkout |
| Promotions — détail financier des remises | Oui | Non | Oui | Non | Non | Sa commande uniquement |
| Fidélité — stratégie/niveaux/récompenses | Oui | Non | Lecture | Oui | Non | Son compte uniquement |
| Memberships — activation payante | Oui | Non | Oui | Non | Non | Demande/annulation du sien |
| CRM — lecture contacts/audiences | Oui | Oui | Non | Oui | Non | Non |
| CRM — segments/campagnes/consentements | Oui | Non | Non | Oui | Non | Ses préférences uniquement |
| CRM Automation — lecture scénarios/historique | Oui | Oui | Non | Oui | Non | Non |
| CRM Automation — créer/modifier/activer | Oui | Non | Non | Oui | Non | Non |
| Growth Analytics — cohortes/rétention/conversions | Oui | Oui | Oui | Oui | Non | Non |
| Growth Analytics — LTV/coûts/ROI/spend | Oui | Non | Oui | Non | Non | Non |

Le rôle Administrateur d'Espace n'est pas l'administrateur de la plateforme et ne reçoit pas `is_staff`.

## Pourquoi cette séparation est obligatoire

Les commandes contiennent des données d'identité client et des montants. Les paiements contiennent des références financières. Les billets contiennent les données de titulaire. Les journaux de scan contiennent des données opérationnelles d'accès. Le CRM contient des coordonnées, notes internes, états de consentement et historique d'automatisations. Les promotions contiennent à la fois des règles marketing et un historique financier de remises par commande. La fidélité contient des soldes de points, niveaux, adhésions et récompenses personnelles. Chaque domaine expose uniquement les informations nécessaires à la responsabilité concernée.

Un membre Marketing peut créer une promotion, définir ses codes et la rattacher à une campagne CRM sans obtenir la liste financière détaillée des commandes qui l'ont utilisée. Finance peut auditer remises et montants finaux sans recevoir le droit de modifier la stratégie promotionnelle. Responsable activité peut consulter les règles et compteurs utiles à l'exploitation sans obtenir les lignes monétaires de redemption. Responsable accès n'obtient aucun accès financier implicite.

Pour Loyalty, Marketing/Propriétaire/Admin définissent les règles de points, niveaux, memberships, récompenses et ajustements audités. Finance/Propriétaire/Admin peut examiner les demandes et activer manuellement un membership payant, sans modifier la stratégie de rétention. Un utilisateur ne peut lire et utiliser que ses propres soldes, memberships et récompenses.

Growth Analytics applique la même séparation à l'agrégation. Marketing et Responsable activité peuvent voir des cohortes, taux de répétition, follower → achat et conversions agrégées sans recevoir LTV, revenus attribués, coûts ou ROI. Finance/Propriétaire/Admin peut voir les lignes monétaires agrégées et gérer `GrowthSpend`. Responsable accès n'obtient aucun droit Growth implicite.

## Résolution centrale

Le service `authorization.services` est la source d'autorité commune. Les nouveaux contrôles utilisent des codes de Permission stables :

```text
can(profile, "space.manage", space)
can(profile, "finance.view", space)
can(profile, "activity.manage", activity=activity)
can(profile, "activity.access.scan", activity=activity)
can(profile, "group.members.manage", group=group)
```

La signature historique avec l'Espace positionnel reste compatible. Les portées Groupe et Activity utilisent des arguments explicites `group=` et `activity=` et aucune résolution générique par `ContentType`.

Le résolveur vérifie :

1. Profil authentifié ;
2. Rôle actif ;
3. Permission active présente dans le Rôle ;
4. Mandat actif et non révoqué ;
5. bonne portée ;
6. `valid_from` / `valid_until` ;
7. privilège superuser ou Mandat plateforme lorsque pertinent.

`effective_permission_codes`, `can_many`, `space_ids_with_permission`, `group_ids_with_permission` et `activity_ids_with_permission` permettent aux dashboards, navigations et selectors de résoudre les capacités sans refaire une requête par élément de menu.

## Héritage Espace → Groupe

Un Groupe d'Espace ne reçoit pas une copie des Mandats Espace. L'héritage est une règle métier explicite de `groups.services` :

1. vérifier d'abord une Permission Groupe directe sur le Groupe exact ;
2. sinon, si `Group.space` est renseigné, accepter `space.groups.manage` pour les opérations de gestion ;
3. pour les lectures administratives, accepter `space.groups.view` ou `space.groups.manage` ;
4. ne jamais utiliser une Permission détenue sur un autre Espace.

Cette règle permet la continuité administrative des Groupes d'Espace sans créer des centaines de Mandats artificiels. Un Mandat Groupe local ne donne réciproquement aucune autorité sur l'Espace.

## Sélecteurs comme frontière de lecture

Les lectures web/API utilisent les selectors ou Permissions explicites du domaine (`events.selectors`, `tickets.selectors`, `payments.selectors`, `scanner.selectors`, `partners.selectors`, `crm.selectors`, `loyalty.selectors`, `analytics_app.selectors`, Growth, Promotions et désormais `groups.selectors`) au lieu de filtrer simplement sur `organization__memberships__user`.

Les mutations continuent à passer par les services de domaine (`user_can_manage_event`, `user_can_manage_event_finance`, `user_can_manage_event_access`, `user_can_manage_partners`, `user_can_manage_crm`, `user_can_manage_promotions`, `user_can_manage_loyalty_strategy`, etc.). Ces helpers sont maintenant des adaptateurs lisibles autour de Permissions canoniques lorsqu'une portée Espace ou Activity existe. Les écritures Groupe passent par `groups.services`.

La règle reste :

1. le selector limite ce qui peut être lu ;
2. la Permission valide ce qui peut être ciblé ;
3. le service applique la transition métier et les verrous transactionnels.

## Propriété, équipe et Groupe

Chaque nouvel Espace est créé transactionnellement avec :

1. `Organization` ;
2. Équipe principale ;
3. `TeamMembership` active du créateur ;
4. Mandat `Propriétaire d'Espace` ;
5. projection `OrganizationMembership` temporaire pour les anciens callsites.

Ajouter une personne via l'interface d'équipe effectue également une écriture cohérente TeamMembership + Mandate. Être TeamMember sans Mandat ne donne aucune autorité.

La révocation ou désactivation du dernier propriétaire est refusée. Après ajout d'un second propriétaire, le premier peut transférer/quitter sa responsabilité sans casser l'invariant.

Un Groupe possède exactement un propriétaire logique : soit un Espace, soit un Profil personnel. Pour un Groupe personnel actif, la propriété logique et le Mandat `group-owner` sont maintenus séparément mais de façon cohérente. Le transfert accorde d'abord le Mandat au nouveau propriétaire, change `owner_profile`, puis révoque l'ancien Mandat. La suppression/anonymisation du compte est bloquée tant qu'un Groupe personnel actif n'a pas été transféré ou archivé.

Une Activity possède de même un opérateur logique explicite : `space` pour un contexte collectif ou `owner_profile` pour un contexte personnel. `created_by` conserve uniquement la provenance du Profil humain. Ni `owner_profile` ni `created_by` ne bypassent le moteur d'autorisation : la création personnelle accorde transactionnellement le rôle Activity-scoped `activity-manager`, et toute délégation utilise ensuite un Mandat Activity. Une TeamMembership ou GroupMembership seule n'accorde aucune autorité Activity.

## Verrous transactionnels PostgreSQL

Les services transactionnels Groups appliquent la discipline issue de la migration Espace :

- `select_for_update()` cible la table réellement nécessaire ;
- les `Meta.ordering` relationnels sont neutralisés par `.order_by()` avant les locks ;
- aucune FK nullable n'est `select_related()` dans un SELECT verrouillé ;
- les relations nécessaires sont chargées après le lock ;
- les conflits d'unicité récupérables de l'import CSV sont isolés dans des savepoints imbriqués afin qu'un `IntegrityError` n'empoisonne pas la transaction PostgreSQL extérieure.

T27 applique la même discipline au self-join, aux demandes d'adhésion, aux décisions et à `ActivityGroupEligibility`. Les contraintes d'unicité restent la dernière ligne de défense contre les doubles clics et courses concurrentes.

## Promotions et prix côté serveur

Le client web ou API ne calcule jamais la remise finale. Il transmet seulement un `promotion_code`. Le serveur recharge l'événement, les billets sélectionnés, l'offre et le code, puis vérifie période, Espace, événement, billets éligibles, devise, minimum de commande, quota global, quota du code et limite par client. Le montant payé par Payments reste `TicketOrder.total_amount` après validation serveur.

`PromotionRedemption` conserve les snapshots `subtotal_amount`, `eligible_amount`, `discount_amount` et `final_amount`. Une réservation compte temporairement dans les quotas avec l'état `reserved`; une vraie confirmation devient `confirmed`; une annulation ou expiration devient `reversed` et libère le quota. Les montants ne sont jamais additionnés entre devises.

## Fidélité et remboursements

Les points Makolo ne sont ni de l'argent ni une devise. Une commande confirmée crée un crédit idempotent dans `LoyaltyLedgerEntry`; un check-in peut créer un crédit distinct. Une annulation ou un remboursement inverse intégralement le crédit d'achat d'origine. Si ces points avaient déjà été dépensés, le compte fidélité peut devenir négatif : cette dette bloque les nouvelles récompenses jusqu'à compensation, mais ne bloque jamais le remboursement financier du client.

Les avantages membership/récompense qui prennent la forme d'une remise utilisent des `PromotionCode` privés à usage unique ; Promotions reste la source de vérité pour appliquer une remise au checkout.

## CRM, automatisations et consentement

L'accès à un contact CRM ne constitue jamais une autorisation de prospection. `CRMContact.marketing_consent` et les préférences du compte Makolo sont des frontières supplémentaires vérifiées au moment de la livraison. Un achat, un billet, un follow ou un déclencheur automatique ne transforme pas automatiquement un utilisateur en abonné marketing.

Les communications événementielles nécessaires sont séparées des messages marketing. Une notification Makolo promotionnelle créée par CRM Automation doit rester explicitement marquée et repasser par les garde-fous de consentement.

L'autorisation `ActivityGroupEligibility` ne modifie pas cette frontière : elle ne crée ni Contact, ni Audience, ni AudienceMember. La conversion d'un Groupe en Audience reste limitée aux Groupes du même Espace par le service CRM existant ; la réutilisation cross-owner fonctionne par référence et n'accorde aucun accès implicite aux coordonnées des membres.

## Compatibilité historique contrôlée

La source canonique d'autorité est désormais `authorization.Mandate`. Les mécanismes suivants restent temporairement présents mais **ne doivent recevoir aucune nouvelle responsabilité** :

- `OrganizationMembership.role` : projection de compatibilité pour anciens callsites/API/fixtures. Les services et le signal de transition maintiennent TeamMembership + Mandate synchronisés pendant le cutover ;
- `OrganizationRole` : vocabulaire historique mappé vers les rôles système ;
- `User.is_organizer` et `User.is_scanner_agent` : uniquement chemins historiques sans Espace encore migré ;
- `accounts.Role`, `PermissionGroup`, `User.roles`, `User.permission_groups` : ancien RBAC global conservé pour compatibilité des contrats existants, jamais utilisé comme autorité contextuelle d'un Espace, d'un Groupe ou d'une Activity ;
- `Event.organizer` / `Activity.created_by` : fallback étroit pour les anciennes Activities sans `space` ni `owner_profile` dont l'ownership n'est pas encore résolu. Les nouvelles Activities doivent utiliser un propriétaire logique explicite et un Mandat.

Le modèle canonique `groups.Group` évite également toute collision avec `User.groups`, nom déjà utilisé par l'auth Django, grâce à des relations `collective_*` explicites.

Aucune nouvelle fonctionnalité ne doit lire `OrganizationMembership.role`, un flag global User ou `created_by` pour décider une autorisation Activity. Les migrations de compatibilité pourront retirer ces adaptateurs une fois les données legacy classifiées.

## Migrations Groupe

La portée Groupe est introduite sans relation générique :

- `groups.0001_initial` crée `Group`, `GroupMembership`, `GroupInvitation`, `GroupSnapshot` et `GroupSnapshotMember` ;
- `groups.0002_group_slug_blank` aligne l'état de migration avec le slug généré par le service/modèle ;
- `groups.0003_invitation_identity_verification` conserve l'état temporaire du challenge e-mail sans stocker le code en clair ;
- `groups.0004_align_invitation_identity_constraint` aligne la contrainte d'identité d'invitation ;
- `groups.0005_community_layer` ajoute `discoverability`, `membership_policy`, `GroupJoinRequest` et la relation explicite `ActivityGroupEligibility`, avec backfill conservateur `PRIVATE → HIDDEN` et `SPACE → SPACE_ONLY` ;
- `authorization.0003_group_scope` ajoute `AuthorityScope.GROUP`, la FK explicite `Mandate.group`, les contraintes de forme de portée, les Permissions et rôles Groupe et `space.groups.*`.

Aucune GFK, FK vers `Event`/`Ticket`, QR collectif ou modèle Access provisoire n'est utilisée pour l'éligibilité Groupe.

## Régressions couvertes

Les tests vérifient notamment : portée Espace correcte, refus inter-Espaces, TeamMember sans Mandat, Mandats futurs/expirés/révoqués, Rôle/Permission inactifs, séparation Finance/Marketing/Responsable activité/Responsable accès, staff sans autorité implicite, plateforme explicite, superuser, création d'Espace complète et invariant du dernier propriétaire.

La suite Groups ajoute : appartenance sans autorité, isolation Groupe A/B, rôles owner/admin/moderator, héritage Espace contrôlé, import CSV jusqu'à 1 000 lignes, sécurité des invitations et challenge d'identité pour les nouveaux comptes, snapshots immuables et continuité du propriétaire d'un Groupe personnel.

T27 ajoute : migration de confidentialité, séparation découvrabilité/adhésion, self-join et join requests idempotents, protection `LEFT/SUSPENDED/REMOVED`, consentement cross-owner, anti-IDOR, absence de copie CRM, éligibilité `ACTIVE` uniquement et courses PostgreSQL sur join/approval/eligibility.

T24 ajoute les régressions Activity personnelles : propriétaire Profil explicite, `created_by` distinct, Mandat Activity transactionnel, délégation/révocation, sélection Space forgée refusée, staff sans rôle local implicite, Event personnel sans Organization artificielle et Discovery utilisant l'opérateur logique.

Le gate PostgreSQL exécute directement les suites pertinentes afin que les services transactionnels et contraintes soient validés sur PostgreSQL 16, pas uniquement sur SQLite.

Les suites existantes continuent aussi à protéger la séparation des PII et finances, le consentement CRM, Promotions, Loyalty, Growth, Payments, scanner et les parcours E2E multi-rôles.
