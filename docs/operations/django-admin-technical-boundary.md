# Django Admin — frontière technique et secours contrôlé

> Contrat de référence : *Makolo Platform ↔ Django Admin — Frontière canonique, matrice de responsabilités et stratégie de migration*, 2026-10-08. Le runtime `main` courant et ses tests prévalent sur les statuts d'une ancienne roadmap.

## 1. Rôle et frontière d'autorisation

**Django Admin n'est pas Makolo Platform.** Il reste une console *model-centric* de maintenance, inspection technique et configuration framework. Les décisions fréquentes, les interventions Trust, la modération, la gestion des Espaces et les actes de l'utilisateur vivent dans leurs vues et services propriétaires.

L'accès Django exige les permissions techniques Django, dont `is_staff` ; cela ne confère **jamais** une Permission ou un Mandate Makolo. Réciproquement, une Permission Platform ne crée pas un accès Django Admin. Le superuser est réservé à la maintenance, au bootstrap et à la récupération exceptionnels, pas à l'exploitation quotidienne.

Les faits de domaine ne changent pas de propriétaire selon l'interface utilisée. Les données et preuves privées ne deviennent pas publiques du seul fait qu'un modèle est enregistré dans Admin.

## 2. Matrice de responsabilité applicable

| Domaine et surface | Django Admin | Chemin normal propriétaire | Décision |
|---|---|---|---|
| Organization, Team, membership, follow | Inspection seulement, sans delete/bulk | Services Organizations, console Space, Mandate/Permission | PLATFORM / APP |
| Activity, Occurrence, OccurrencePlace, Event | Inspection seulement | `activities.services`, `events.services`, actions contextuelles autorisées | APP / PLATFORM pour modération |
| EventCategory et EventVenue | Configuration technique conservée | Configuration métier si disponible | ADMIN config / transition |
| Operations Incident, ModerationCase | Inspection seulement | `operations.services.create_incident/update_incident/moderate_event` | PLATFORM / OPERATIONS |
| OperationalControl | Mutation exceptionnelle conservée, raison obligatoire, `set_operational_control` | `operations.emergency_controls` | DUAL contrôlé |
| WorkerHeartbeat, OperationsAuditLog | Inspection seulement | Worker/service d'audit | SYSTEM / DUAL |
| PlacementAssignment | Inspection seulement | `operations.placement_services` (assign/move/unassign) | OPERATIONS |
| PlacementPlan, PlacementUnit | Configuration technique conservée | Administration de plan/unit vérifiée cas par cas | ADMIN config |
| Trust, VerificationClaim, Report, Dispute, Proof | Inspection seulement | Services Trust et file de revue | PLATFORM |
| TrustEvidence | Inspection exceptionnelle superuser ; pas de lien `file.url` brut | Ouverture explicite protégée, permission, no-store, audit | PLATFORM / forensic Admin |
| Opportunity, Revision, Source, checks, Requirement, Zone, Submission, Save | Inspection seulement | `opportunities.services` et `opportunities.staff_views` | PLATFORM / curation |
| Subscriptions, Entitlements, reviews | Pas de nouveau CRUD Admin créé | Services et vues `subscriptions` déjà autorisés | PLATFORM / APP |
| Recognition Policy | Édition de brouillon contrôlée, actions de simulation/publication **via services propriétaires**, raison, confirmation et audit | `recognition.governance_services` | DUAL transitoire |
| Recognition Signal, Account, historique | Inspection readonly | Recognition ledger, audit et projection Platform | DUAL audit |
| AchievementDefinition / RewardDefinition | Configuration de secours avec immutabilité après usage ; suppressions Admin désactivées | Gouvernance Recognition / services propriétaires | DUAL transitoire |
| DomainEventOutbox | Inspection ; requeue unitaire exceptionnel, raison, budget, verrou, audit | `domain_events.services` | ADMIN / SYSTEM |
| DomainEventConsumption | Inspection seulement | Processor idempotent | ADMIN / SYSTEM |
| Access, AccessCredential, AccessUse, Payments | Admin readonly existant, préservé | Services propriétaires Access/Payments | APP / PLATFORM |
| CapacityPool et CapacityReservation | Inspection seulement | `capacity.services` | APP / OPERATIONS |
| Offer, CommerceOrder, CommerceOrderItem | Inspection seulement | `commerce.services` | APP / OPERATIONS |
| TicketType, Order, Ticket, Transfer, Waitlist | Inspection seulement, y compris inlines | `tickets.services`, Access/Capacity canonique | APP / OPERATIONS |
| Journey, Requests, Steps, Assignments, Reviews | Inspection seulement | `journeys.services` et services complémentaires | APP / SPACE |
| JourneyArtifact, JourneyNote | Inspection forensic superuser ; liens de fichiers privés masqués | Services owner et contrats de visibilité | APP / forensic Admin |
| Sharing/Inbound | Inspection forensic superuser ; pas de mutation générique | `sharing.services` et services documents | APP / forensic Admin |
| ScannerAssignment, ScanLog, EventAccessGate | Inspection seulement | Scanner/Access et permissions opérationnelles | APP / OPERATIONS |
| User, UserProfile, UserSession, UserDevice, NotificationPreference | User technique superuser uniquement ; pas de bulk ou vérification email brute ; sous-modèles readonly ; clé de session cachée | Accounts / Trust / préférences utilisateur | APP / TECH bootstrap |
| ProviderConnection, IntelligenceRoute | Configuration technique superuser ; credentials non réaffichés, check health unitaire justifié et audité | `intelligence.credentials` et `intelligence.health` | ADMIN technique / PLATFORM projection |
| allauth SocialApp OAuth/OIDC | Configuration superuser conservée ; secret et settings non réaffichés ; rotation explicite | Setup infra via runbook, pas workflow produit | ADMIN |\n| allauth SocialToken et SocialAccount | Inspection superuser uniquement ; tokens bruts jamais affichés, pas de relink/edit/delete | Handshake allauth et services Accounts | ADMIN forensic |
| Variables d'environnement, clés, migrations, schéma | Jamais exposés comme données brutes dans Platform/Admin | Configuration environnement et engineering | ENV / ENGINEERING |

Les modèles laissés éditables ne sont **pas** une permission métier : ce sont des configurations techniques identifiées ou un secours conservé en attendant un chemin propriétaire certifié équivalent. Avant de supprimer un autre fallback, vérifier couverture du service, validation, audit, permissions et rollback.

## 3. Reprise exceptionnelle d'un Domain Event

1. Qualifier l'incident, trouver un événement `FAILED` unique et vérifier son propriétaire, son impact, ses `attempts/max_attempts` et les receipts Consumers. Ne jamais sélectionner plusieurs événements.
2. Utiliser l'action technique `Reprise ciblée` avec un superuser autorisé et une justification de 5 à 2000 caractères.
3. Le service `requeue_failed_domain_event` verrouille l'événement, exige `FAILED`, refuse les budgets épuisés et les consumers en traitement, conserve les reçus déjà réussis et les tentatives. Il n'efface ni compteur ni erreur historique pendant la remise en attente.
4. Contrôler `OperationsAuditLog` (`domain_event.requeued`) et la livraison effective du processor. Un statut `PENDING` signifie *à retraiter*, pas *succès*.
5. Si budget épuisé ou livraison encore défaillante : investiguer la cause racine et le consumer. Ne jamais forcer en SQL un retry en réinitialisant les tentatives ni réémettre le même fait avec une autre idempotency key.

Cette opération n'est pas un outil de modification du fait immuable.

## 4. Recognition Policy — double chemin strictement propriétaire

L'action Admin affiche un formulaire de confirmation pour **une** Policy avec justification et statut attendu. Les actions de simulation et de publication appellent `recognition.governance_services.record_policy_simulation` et `publish_policy_for_actor`, comme la direction Platform. Le service vérifie la Permission Makolo, la concurrence, le statut, les frontières du cursor et écrit un `OperationsAuditLog`.

Ne pas rétablir les anciennes actions `queryset.update(status=...)` : elles perdaient les garanties de validation, d'audit et de concurrence. Une policy publiée est immuable : créer une nouvelle version pour changer ses règles. La simulation n'est **pas** une publication.

**Intégration de branches :** le fichier propriétaire `recognition/governance_services.py` est également introduit par le chantier Platform en parallèle. Le réconcilier avec le HEAD réel de la PR Platform avant l'intégration ; ne pas laisser deux implémentations divergentes ni accepter silencieusement des conflits.

## 5. Comptes, accès privés et secrets

- `accounts.UserAdmin` n'est accessible en édition technique qu'à un superuser actif, lui-même staff. Les actions de masse sans validation owner (`email_verified`, activation, unlock, export) ne sont plus publiées. La vérification email/téléphone n'est pas un simple booléen à cocher dans Admin.
- Les sous-modèles de profil, préférences, devices et sessions sont consultables mais non éditables par ce chemin. `session_key` n'est ni un champ de détail visible ni un champ d'inline.
- `TrustEvidence.file` et `JourneyArtifact.file` ne produisent pas de lien direct vers le stockage depuis Admin. L'ouverture de preuve à travers Platform/Trust reste explicite, privée, contrôlée et no-store.
- Les credentials Intelligence se saisissent via un champ password vide par défaut ; une valeur vide conserve l'existante. Le stockage chiffré passe par `set_provider_secret`. Ne pas copier de clé en logs, tests, commentaires ou audit. Le check de connectivité est limité à une connexion par demande, justifié et audité ; il peut provoquer un appel externe réel.
- L'Admin SocialApp allauth demeure une configuration framework exceptionnelle, superuser-only. Les champs du secret et de la clé existants restent non affichés : utiliser les champs de remplacement facultatifs pour une rotation, et laisser vide pour conserver. Les paramètres provider existants ne sont jamais réaffichés ; leur remplacement est un objet JSON complet, validé. Les tokens OAuth et les secrets de refresh de SocialToken ne sont jamais visibles dans Django Admin. Les secrets SocialApp stockés en base par allauth ne sont **pas** présumés chiffrés au repos ; privilégier les protections de stockage et la configuration d'environnement appropriées.\n- Les secrets d'environnement n'appartiennent ni au shell Platform ni à une fiche Admin.

## 6. Validation, déploiement, rollback

Avant PR merge : vérifier `main`, CI réelle de la branche, absence de migration non souhaitée, permissions, Domain Events, Recognition, Trust et données privées. Exemples de commandes de validation dans un environnement de développement **configuré** :

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_admin_boundary recognition.test_staff_config trust.test_security_m4
```

Les tests ciblés ne remplacent pas les gates GitHub Django, PostgreSQL, sécurité et migrations. Ne jamais merger avec un gate rouge.

Aucune migration de données n'est requise par cette frontière Admin : les données et vérités métier existantes sont préservées. En cas d'incident après intégration, revenir au dernier commit Git vérifié par la procédure normale de rollback ; ne pas restaurer d'anciennes actions massives dangereuses pour « débloquer » l'exploitation. Les services propriétaires restent les voies de récupération.

La page Django Admin doit toujours se présenter comme **Administration technique**, distincte de Makolo Platform. Ne pas lui donner un habillage trompeur censé se substituer à une expérience opérateur.

## 7. Critères de fermeture A1–A7

- **A1 :** inventaire des registres Admin, domaines owners et collision audit.
- **A2 :** retirer chemins de mutations directes des lifecycle, autorité, Trust, finance, publication, Access, Capacity et dossiers privés.
- **A3 :** seules actions de secours restantes fondées sur services owner ou config framework identifiée.
- **A4 :** privacy (fichiers/credentials/sessions), permissions Django vs Makolo, action/bulk gating, audit et raison explicite.
- **A5 :** tests de refus, isolation staff/superuser, reprise idempotente, service Recognition, contrat Trust.
- **A6 :** matrice de responsabilités, runbook d'urgence, fallback et rollback.
- **A7 :** CI verte sur dernier HEAD, `main` réconcilié, pas de conflit avec Platform, PR prête pour intégration. **Le merge dépend d'une décision séparée et n'est pas exécuté dans ce chantier tant qu'il n'est pas demandé.**
