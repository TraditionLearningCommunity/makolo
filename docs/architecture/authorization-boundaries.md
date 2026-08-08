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
| Communication/CRM futur | Oui | Non par défaut | Non | Oui | Non | Ses préférences |

Le rôle `Admin` d'organisation n'est pas l'administrateur de la plateforme. Il hérite des capacités opérationnelles de l'organisation mais ne reçoit pas `is_staff`.

## Pourquoi cette séparation est obligatoire

Les commandes contiennent des données d'identité client et des montants. Les paiements contiennent des références financières. Les billets contiennent les données de titulaire. Les journaux de scan contiennent des données opérationnelles d'accès. Un membre Marketing n'a pas besoin de voir ces données pour accomplir sa mission ; inversement un responsable Finance n'a pas besoin d'accéder aux QR et données de contrôle d'accès.

Cette séparation réduit le risque d'exposition latérale au sein d'une équipe organisatrice et prépare les futurs domaines CRM, affiliation et analytics avec des permissions explicites.

## Sélecteurs comme frontière de lecture

Les lectures web/API doivent utiliser les sélecteurs du domaine (`tickets.selectors`, `payments.selectors`, `scanner.selectors`) au lieu de filtrer simplement sur `organization__memberships__user`.

Les mutations continuent à passer par les permissions/services (`user_can_manage_event`, `user_can_manage_event_finance`, `user_can_manage_event_access`, etc.). La règle est donc :

1. le sélecteur limite ce qui peut être lu ;
2. la permission valide ce qui peut être ciblé ;
3. le service applique la transition métier et les verrous transactionnels.

## Compatibilité historique

`Event.organizer`, `is_organizer` et les rôles historiques restent des mécanismes de compatibilité pendant la migration du modèle initial. Ils ne doivent pas être étendus. Les nouvelles capacités doivent passer par `OrganizationMembership` et les ensembles de rôles définis dans `organizations.permissions`.

## Régressions couvertes

Les tests de consolidation vérifient notamment qu'un membre Marketing ne voit pas les commandes, paiements ou billets des participants, qu'un Event manager ne reçoit pas implicitement les droits Finance, qu'un responsable Finance voit les données financières mais pas les QR/titulaires, et qu'un Scanner manager obtient les données d'accès sans obtenir les paiements.
