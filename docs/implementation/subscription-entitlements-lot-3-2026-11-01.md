# Subscription — Lot 3 : enforcement chez les propriétaires métier

**Branche de travail :** PR #522, `fix/discover-a-continuation-context-20261014`.  
**Nature :** raccordement des trois Features techniques déjà publiées aux services métier.  
**Pas de** Feature supplémentaire, modèle, migration, compteur duplicatif, Plan, prix ou permission inventée.

## Source de vérité

- `subscriptions.entitlements.resolve_entitlement(subject, feature_code)` calcule valeurs, blocages, usage réel, Requirements, statut et provenance depuis BASE, ADDONS et GRANTS.
- Les clients Web/Flutter montrent ce que prépare le serveur ; ils ne décident jamais des droits.
- Un Profil acteur n'emprunte pas les capacités d'un Espace. Permission/Mandate reste une autorité distincte de Subscription/Entitlement.

## Matrice d'enforcement

| Feature | Consommateur propriétaire | Condition lors de la mutation | Comportement préservé |
| --- | --- | --- | --- |
| `activities.create` | `activities.services.create_activity` | `resolve_entitlement(owner_profile ou space, 'activities.create').allowed` avant `Activity.save` et avant Domain Events | édition, publication, Occurrences et Activity existantes ne sont pas supprimées ; le créateur au nom d'un Espace n'emprunte pas sa Subscription personnelle |
| `team.members` | `organizations.services.add_or_update_member`, `add_existing_collaborator_to_team`, projection legacy `sync_legacy_membership_to_authority`, garde `pre_save` legacy | vérifier seulement une **nouvelle personne distincte** active dans un Team actif, avec le provider `organizations.active_team_members` ; la ligne Organization est verrouillée par les services canoniques | réaffectation d'un membre existant, second Team, modification de rôle, retrait, ancienne donnée et Mandates indépendants restent intacts |
| `custom_roles` | `authorization.services.create_custom_space_role` | propriétaire/gouvernance habilitée + `resolve_entitlement(space, 'custom_roles').allowed` ; seules les Permissions Espace actives que détient l'acteur peuvent être déléguées | rôles système inchangés ; anciens rôles personnalisés et Mandates ne sont ni effacés ni rétroactivement modifiés |

## Décisions de contrat

1. **Quota absent :** `space.base` ne publie aucune valeur `team.members`. `effective_value=None` signifie qu'aucun plafond numérique commercial n'est configuré ; nous ne fabriquons pas `0` et n'interdisons pas arbitrairement les admissions. Dès qu'un plafond numérique est effectivement résolu, `allowed=False` refuse uniquement l'admission nette nouvelle.
2. **Concurrence :** les voies de mutation canoniques Teams prennent le verrou de la même ligne Organization avant de mesurer et créer/réactiver la personne. La mesure compte les `user_id` distincts dans les Teams actifs, pas le nombre de `TeamMembership` et sans compteur persistant nouveau.
3. **Legacy :** une nouvelle écriture `OrganizationMembership` active est vérifiée en `pre_save` avant sa synchronisation. La projection elle-même passe par le même garde du domaine Organizations. Les écritures ORM massives contournant services et signaux ne constituent pas une API métier autorisée.
4. **Roles :** l'administration `Role` est déjà en lecture seule et aucun CRUD public de rôles personnalisés n'était livré. La nouvelle création contrôlée se fait par service du domaine Authorization ; ce lot n'invente pas un écran ou un endpoint Role. Les fixtures ORM et rôles historiques sont conservés.
5. **Erreurs utilisateur :** `activities.views.ActivityCreateView`, `events.views.EventCreateView` et `events.api.views.EventViewSet` convertissent les refus métier en erreurs de formulaire/validation ; `funding`, `obtention` et `transport` possédaient déjà les catches de ValidationError correspondants.
6. **Périmètre :** le gating ne sert pas à révoquer des Mandates, à réécrire des plans publiés, à rendre les données historiques invalides ou à bloquer les opérations de nettoyage.

## Tests ciblés ajoutés

`subscriptions/test_lot3_enforcement.py` :

- création personnelle bloquée par suspension de sa Subscription, et création pour un autre Espace toujours possible ;
- isolation de la Subscription propriétaire quand le Profil acteur est suspendu ;
- Activity existante conservée et modifiable après interdiction d'en créer une nouvelle ;
- formulaire de création Activity avec message métier sans erreur 500 ;
- absence de quota `team.members` respectée (pas de zéro fictif) ;
- plafond numérique avec SUM de GRANTS, personnes distinctes et plusieurs Teams ;
- réaffectation/usage existant conservé, refus d'une nouvelle personne au plafond ;
- compatibilité legacy création/réactivation refusée avant sa mutation ;
- rôles personnalisés refusés sans capacité, refusés sans autorité, autorisés avec capacité, unicité et confinement par Espace ;
- ancien rôle préservé après révocation de la capacité.

## Validation

Code et tests commités dans la PR #522. **Aucune exécution des tests ni validation CI n'est attestée ici.** Les validations à réaliser avant intégration restent les tests ciblés Django (PostgreSQL pour scénarios de concurrence) puis les gates adaptées au dépôt courant. Aucune suppression ni désactivation de tests.
