# Frontières d'autorisation Makolo

Makolo est multi-Espaces. Une appartenance à une Équipe ne donne jamais, à elle seule, accès aux données privées de l'Espace. L'autorité métier runtime est désormais basée sur **Role + Permission + Mandate** conformément au [Domain Blueprint](makolo-domain-blueprint.md).

## Principe runtime

L'identité est globale ; l'autorité est contextuelle. Une décision d'autorisation doit répondre à **qui peut faire quoi, et où ?**

La source canonique est :

```text
Profil + Rôle + Portée = Mandat
```

Pour cette première migration, les portées réellement implémentées sont :

- `platform` — plateforme Makolo ;
- `space` — un Espace précis, techniquement encore représenté par `organizations.Organization`.

Les portées Activity et Group seront ajoutées lorsque ces domaines canoniques existeront. Aucun `ContentType` ou `GenericForeignKey` n'est utilisé pour simuler ces futures portées.

`TeamMembership` exprime uniquement la collaboration dans une Équipe. Il ne porte aucune Permission. Les actions d'équipe créent transactionnellement la `TeamMembership` et le `Mandate` correspondant afin de conserver une UX simple sans confondre appartenance et autorité.

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

## Matrice minimale

| Domaine | Propriétaire/Admin | Responsable activité | Finance | Marketing | Responsable accès | Profil utilisateur |
|---|---:|---:|---:|---:|---:|---:|
| Créer/modifier événements | Oui | Oui | Non | Non | Non | Non |
| Types de billets | Oui | Oui | Non | Non | Non | Public uniquement |
| Commandes / identité client | Oui | Oui | Oui | Non | Non | Ses commandes |
| Paiements / remboursements | Oui | Non | Oui | Non | Non | Ses paiements |
| Billets / identité titulaire | Oui | Oui | Non | Non | Oui | Ses billets |
| Scanner / journaux d'accès | Oui | Oui | Non | Non | Oui | Non |
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
can(profile, "activity.manage", space)
can(profile, "access.manage", space)
```

Le résolveur vérifie :

1. Profil authentifié ;
2. Rôle actif ;
3. Permission active présente dans le Rôle ;
4. Mandat actif et non révoqué ;
5. bonne portée ;
6. `valid_from` / `valid_until` ;
7. privilège superuser ou Mandat plateforme lorsque pertinent.

`effective_permission_codes`, `can_many` et `space_ids_with_permission` permettent aux dashboards, navigations et selectors de résoudre les capacités sans refaire une requête par élément de menu.

## Sélecteurs comme frontière de lecture

Les lectures web/API utilisent les selectors ou Permissions explicites du domaine (`events.selectors`, `tickets.selectors`, `payments.selectors`, `scanner.selectors`, `partners.selectors`, `crm.selectors`, `loyalty.selectors`, `analytics_app.selectors`, Growth et Promotions) au lieu de filtrer simplement sur `organization__memberships__user`.

Les mutations continuent à passer par les services de domaine (`user_can_manage_event`, `user_can_manage_event_finance`, `user_can_manage_event_access`, `user_can_manage_partners`, `user_can_manage_crm`, `user_can_manage_promotions`, `user_can_manage_loyalty_strategy`, etc.). Ces helpers sont maintenant des adaptateurs lisibles autour de Permissions canoniques lorsqu'une portée Espace existe.

La règle reste :

1. le selector limite ce qui peut être lu ;
2. la Permission valide ce qui peut être ciblé ;
3. le service applique la transition métier et les verrous transactionnels.

## Propriété et équipe

Chaque nouvel Espace est créé transactionnellement avec :

1. `Organization` ;
2. Équipe principale ;
3. `TeamMembership` active du créateur ;
4. Mandat `Propriétaire d'Espace` ;
5. projection `OrganizationMembership` temporaire pour les anciens callsites.

Ajouter une personne via l'interface d'équipe effectue également une écriture cohérente TeamMembership + Mandate. Être TeamMember sans Mandat ne donne aucune autorité.

La révocation ou désactivation du dernier propriétaire est refusée. Après ajout d'un second propriétaire, le premier peut transférer/quitter sa responsabilité sans casser l'invariant.

## Promotions et prix côté serveur

Le client web ou API ne calcule jamais la remise finale. Il transmet seulement un `promotion_code`. Le serveur recharge l'événement, les billets sélectionnés, l'offre et le code, puis vérifie période, Espace, événement, billets éligibles, devise, minimum de commande, quota global, quota du code et limite par client. Le montant payé par Payments reste `TicketOrder.total_amount` après validation serveur.

`PromotionRedemption` conserve les snapshots `subtotal_amount`, `eligible_amount`, `discount_amount` et `final_amount`. Une réservation compte temporairement dans les quotas avec l'état `reserved`; une vraie confirmation devient `confirmed`; une annulation ou expiration devient `reversed` et libère le quota. Les montants ne sont jamais additionnés entre devises.

## Fidélité et remboursements

Les points Makolo ne sont ni de l'argent ni une devise. Une commande confirmée crée un crédit idempotent dans `LoyaltyLedgerEntry`; un check-in peut créer un crédit distinct. Une annulation ou un remboursement inverse intégralement le crédit d'achat d'origine. Si ces points avaient déjà été dépensés, le compte fidélité peut devenir négatif : cette dette bloque les nouvelles récompenses jusqu'à compensation, mais ne bloque jamais le remboursement financier du client.

Les avantages membership/récompense qui prennent la forme d'une remise utilisent des `PromotionCode` privés à usage unique ; Promotions reste la source de vérité pour appliquer une remise au checkout.

## CRM, automatisations et consentement

L'accès à un contact CRM ne constitue jamais une autorisation de prospection. `CRMContact.marketing_consent` et les préférences du compte Makolo sont des frontières supplémentaires vérifiées au moment de la livraison. Un achat, un billet, un follow ou un déclencheur automatique ne transforme pas automatiquement un utilisateur en abonné marketing.

Les communications événementielles nécessaires sont séparées des messages marketing. Une notification Makolo promotionnelle créée par CRM Automation doit rester explicitement marquée et repasser par les garde-fous de consentement.

## Compatibilité historique contrôlée

La source canonique d'autorité est désormais `authorization.Mandate`. Les mécanismes suivants restent temporairement présents mais **ne doivent recevoir aucune nouvelle responsabilité** :

- `OrganizationMembership.role` : projection de compatibilité pour anciens callsites/API/fixtures. Les services et le signal de transition maintiennent TeamMembership + Mandate synchronisés pendant le cutover ;
- `OrganizationRole` : vocabulaire historique mappé vers les rôles système ;
- `User.is_organizer` et `User.is_scanner_agent` : uniquement chemins historiques sans Espace encore migré ;
- `accounts.Role`, `PermissionGroup`, `User.roles`, `User.permission_groups` : ancien RBAC global conservé pour compatibilité des contrats existants, jamais utilisé comme autorité contextuelle d'un Espace ;
- `Event.organizer` : fallback des anciens événements sans Organization.

Aucune nouvelle fonctionnalité ne doit lire `OrganizationMembership.role` pour décider une autorisation. La migration Activity/Occurrence permettra de retirer une nouvelle couche de ces adaptateurs.

## Régressions couvertes

Les tests vérifient notamment : portée Espace correcte, refus inter-Espaces, TeamMember sans Mandat, Mandats futurs/expirés/révoqués, Rôle/Permission inactifs, séparation Finance/Marketing/Responsable activité/Responsable accès, staff sans autorité implicite, plateforme explicite, superuser, création d'Espace complète et invariant du dernier propriétaire.

Les suites existantes continuent aussi à protéger la séparation des PII et finances, le consentement CRM, Promotions, Loyalty, Growth, Payments, scanner et les parcours E2E multi-rôles.