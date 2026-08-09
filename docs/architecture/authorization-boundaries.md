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
| CRM Automation — lecture scénarios/historique | Oui | Oui | Non | Oui | Non | Non |
| CRM Automation — créer/modifier/activer | Oui | Non | Non | Oui | Non | Non |

Le rôle `Admin` d'organisation n'est pas l'administrateur de la plateforme. Il hérite des capacités opérationnelles de l'organisation mais ne reçoit pas `is_staff`.

## Pourquoi cette séparation est obligatoire

Les commandes contiennent des données d'identité client et des montants. Les paiements contiennent des références financières. Les billets contiennent les données de titulaire. Les journaux de scan contiennent des données opérationnelles d'accès. Le CRM contient des coordonnées, notes internes, états de consentement et historique d'automatisations. Chaque domaine expose uniquement les informations nécessaires au rôle concerné.

Un membre Marketing n'a pas besoin de voir les références financières ou les QR pour accomplir sa mission ; il peut gérer le CRM, l'acquisition et ses parcours automatiques à travers des vues dédiées. Un responsable Finance n'a pas besoin d'accéder aux contacts CRM, aux notes relationnelles ou aux données de contrôle d'accès. Un Event manager peut lire les contacts, audiences et historiques CRM utiles au pilotage de son événement, mais ne peut ni modifier un consentement, ni envoyer une campagne, ni créer ou activer un workflow sans rôle Marketing/Owner/Admin.

Cette séparation réduit le risque d'exposition latérale au sein d'une équipe organisatrice et maintient des permissions explicites pour CRM, affiliation, automatisation et analytics.

## Sélecteurs comme frontière de lecture

Les lectures web/API doivent utiliser les sélecteurs ou permissions explicites du domaine (`tickets.selectors`, `payments.selectors`, `scanner.selectors`, `partners.selectors`, `crm.selectors`, permissions CRM Automation) au lieu de filtrer simplement sur `organization__memberships__user`.

Les mutations continuent à passer par les permissions/services (`user_can_manage_event`, `user_can_manage_event_finance`, `user_can_manage_event_access`, `user_can_manage_partners`, `user_can_manage_crm`, etc.). La règle est donc :

1. le sélecteur ou la permission de lecture limite ce qui peut être lu ;
2. la permission valide ce qui peut être ciblé ;
3. le service applique la transition métier et les verrous transactionnels.

## CRM, automatisations et consentement

L'accès à un contact CRM ne constitue jamais une autorisation de prospection. `CRMContact.marketing_consent` et les préférences du compte Makolo sont des frontières supplémentaires vérifiées au moment de la livraison. Un achat, un billet, un follow ou un déclencheur automatique ne transforme pas automatiquement un participant en abonné marketing.

Les communications événementielles nécessaires à un événement sont séparées des messages marketing. Les modèles `marketing` exigent un consentement `subscribed` actif puis revalident les préférences globales et, lorsqu'elles existent, les préférences propres au follow de l'organisateur. Une notification Makolo créée par CRM Automation doit être explicitement marquée `marketing_action` si elle est promotionnelle ; ce marquage déclenche la même revalidation de consentement et de préférences. Les e-mails marketing automatiques proposent un désabonnement signé et limité à l'organisation concernée.

Un workflow peut ajouter/retirer un tag ou notifier l'équipe sans transformer ces opérations internes en consentement marketing. Les actions automatiques restent auditées dans `CRMWorkflowRun` et `CRMWorkflowActionRun`.

## Compatibilité historique

`Event.organizer`, `is_organizer` et les rôles historiques restent des mécanismes de compatibilité pendant la migration du modèle initial. Ils ne doivent pas être étendus. Les nouvelles capacités doivent passer par `OrganizationMembership` et les ensembles de rôles définis dans les permissions de domaine.

## Régressions couvertes

Les tests de consolidation vérifient notamment qu'un membre Marketing ne voit pas les commandes, paiements ou billets des participants, qu'un Event manager ne reçoit pas implicitement les droits Finance, qu'un responsable Finance voit les données financières mais pas les QR/titulaires ni le CRM, qu'un Scanner manager obtient les données d'accès sans obtenir les paiements, et que le CRM isole les contacts entre organisations. Les tests CRM vérifient aussi le consentement marketing, le désabonnement, les segments dynamiques et la séparation entre lecture Event manager et gestion Marketing.

Les tests CRM Automation ajoutent la séparation Marketing/Finance, la réévaluation des segments, les garde-fous de consentement e-mail et notification Makolo, l'idempotence des déclencheurs, les délais multi-étapes, la suspension des workflows, les retries et les déclencheurs temporels/no-show/anniversaire.
