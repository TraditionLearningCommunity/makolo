# Frontières d'autorisation Makolo

Makolo est multi-organisateurs. Une appartenance à une organisation ne donne jamais, à elle seule, accès à toutes les données de cette organisation.

## Principe

Les droits de plateforme (`is_staff`, `is_superuser`) restent séparés des droits métier. Pour les utilisateurs non-staff, l'accès est dérivé du rôle actif dans `OrganizationMembership` et du domaine concerné.

## Matrice minimale

| Domaine | Owner/Admin | Event manager | Finance | Marketing | Scanner manager | Participant |
|---|---:|---:|---:|---:|---:|---:|
| Créer/modifier événements | Oui | Oui | Non | Non | Non | Non |
| Types de billets | Oui | Oui | Non | Non | Non | Public uniquement |
| Commandes / identité client | Oui | Oui | Oui | Non | Non | Ses commandes |
| Paiements / remboursements | Oui | Non | Oui | Non | Non | Ses paiements |
| Billets / identité titulaire | Oui | Oui | Non | Non | Oui | Ses billets |
| Scanner / journaux d'accès | Oui | Oui | Non | Non | Oui | Non |
| Partenaires / campagnes d'affiliation | Oui | Non | Finance partenaire seulement | Oui | Non | Son portail partenaire si lié |
| CRM — lecture contacts/audiences | Oui | Oui | Non | Oui | Non | Non |
| CRM — segments/campagnes/consentements | Oui | Non | Non | Oui | Non | Ses préférences uniquement |

Le rôle `Admin` d'organisation n'est pas l'administrateur de la plateforme. Il hérite des capacités opérationnelles de l'organisation mais ne reçoit pas `is_staff`.

## Pourquoi cette séparation est obligatoire

Les commandes contiennent des données d'identité client et des montants. Les paiements contiennent des références financières. Les billets contiennent les données de titulaire. Les journaux de scan contiennent des données opérationnelles d'accès. Le CRM contient des coordonnées, notes internes et états de consentement. Chaque domaine expose uniquement les informations nécessaires au rôle concerné.

Un membre Marketing n'a pas besoin de voir les références financières ou les QR pour accomplir sa mission ; il peut gérer le CRM et l'acquisition à travers des vues dédiées. Un responsable Finance n'a pas besoin d'accéder aux contacts CRM, aux notes relationnelles ou aux données de contrôle d'accès. Un Event manager peut lire les contacts et audiences utiles au pilotage de son événement, mais ne peut ni modifier un consentement ni envoyer une campagne sans rôle Marketing/Owner/Admin.

Cette séparation réduit le risque d'exposition latérale au sein d'une équipe organisatrice et maintient des permissions explicites pour CRM, affiliation et analytics.

## Sélecteurs comme frontière de lecture

Les lectures web/API doivent utiliser les sélecteurs du domaine (`tickets.selectors`, `payments.selectors`, `scanner.selectors`, `partners.selectors`, `crm.selectors`) au lieu de filtrer simplement sur `organization__memberships__user`.

Les mutations continuent à passer par les permissions/services (`user_can_manage_event`, `user_can_manage_event_finance`, `user_can_manage_event_access`, `user_can_manage_partners`, `user_can_manage_crm`, etc.). La règle est donc :

1. le sélecteur limite ce qui peut être lu ;
2. la permission valide ce qui peut être ciblé ;
3. le service applique la transition métier et les verrous transactionnels.

## CRM et consentement

L'accès à un contact CRM ne constitue jamais une autorisation de prospection. `CRMContact.marketing_consent` et les préférences du compte Makolo sont des frontières supplémentaires vérifiées au moment de la livraison. Un achat ou un billet ne transforme pas automatiquement un participant en abonné marketing.

Les communications événementielles nécessaires à un événement sont séparées des campagnes marketing : elles utilisent les audiences événementielles et respectent `event_notifications` pour les comptes Makolo, tandis que les campagnes marketing exigent un consentement `subscribed` actif et proposent un désabonnement signé.

## Compatibilité historique

`Event.organizer`, `is_organizer` et les rôles historiques restent des mécanismes de compatibilité pendant la migration du modèle initial. Ils ne doivent pas être étendus. Les nouvelles capacités doivent passer par `OrganizationMembership` et les ensembles de rôles définis dans les permissions de domaine.

## Régressions couvertes

Les tests de consolidation vérifient notamment qu'un membre Marketing ne voit pas les commandes, paiements ou billets des participants, qu'un Event manager ne reçoit pas implicitement les droits Finance, qu'un responsable Finance voit les données financières mais pas les QR/titulaires ni le CRM, qu'un Scanner manager obtient les données d'accès sans obtenir les paiements, et que le CRM isole les contacts entre organisations. Les tests CRM vérifient aussi le consentement marketing, le désabonnement, les segments dynamiques et la séparation entre lecture Event manager et gestion Marketing.
