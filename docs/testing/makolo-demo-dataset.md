# Makolo — génération de données de démonstration

**Commande unique :** `python -m scripts.demo_generation`. Les modules sous `scripts/demo_generation/` ne sont pas des scripts à lancer individuellement.

## Structure

| Module interne | Responsabilité canonique |
| --- | --- |
| `__main__.py` | CLI transversal : `inventory`, `plan`, `generate`, `timeline` |
| `scale.py` | Journey, Access, Operations, Scanner, Event/Commerce/Payment sandbox |
| `verticals.py` | Funding, Obtention, Services et Opportunities |
| `transport.py` | Activity/Occurrence transport, Capacity, Journey, Access, file d’embarquement |
| `mandates.py` | Mandates d’Activity explicitement accordés au personnel de démo |
| `content.py` | Audit Content/Presentation uniquement, sans média orphelin |
| `clock.py` | Dates et créneaux de démo, **jamais recalés implicitement** |

Les anciens points d’entrée `scripts/makolo_demo_*.py` sont supprimés. La création de Journey en double (ancien `seed_journeys`) est consolidée dans `scale.py` ; l’ancienne commande `operations` se répartit entre `scale.py` et `mandates.py`.

## Commandes PowerShell, racine du dépôt

```powershell
python -m scripts.demo_generation --help
python -m scripts.demo_generation inventory
python -m scripts.demo_generation plan --domains all --count 50 --profiles 30 --grant-roles
python -m scripts.demo_generation generate --domains all --count 50 --profiles 30 --grant-roles
```

`plan` ne demande aucune écriture. `generate` écrit sur la **SQLite de démonstration existante** sans créer de copie ou de backup automatique ; vérifier les aperçus, la taille disque et la configuration avant génération massive.

### Domaines sélectionnables

```powershell
python -m scripts.demo_generation plan --domains funding,obtention,services,opportunities --count 50
python -m scripts.demo_generation plan --domains activities,mandates,journeys,access,operations,scanner,commerce --count 100 --grant-roles
python -m scripts.demo_generation plan --domains transport --count 20
python -m scripts.demo_generation plan --domains content
```

`all` inclut les domaines réellement générables et exclut volontairement `content` (audit seulement). `activities` représente le socle Activity/Occurrence réutilisé ; les nouvelles Activity sont créées seulement par une verticale définie (`transport`). `FundingContribution` est l’intention de **Funding** ; `Payment` appartient au domaine de paiement et représente son exécution, uniquement sandbox en démo.

Les groupes indépendants sont `journeys`, `access`, `operations`, `scanner`, `commerce`, `transport`, `funding`, `obtention`, `services`, `opportunities` et `mandates`. `--grant-roles` est obligatoire pour générer explicitement les Mandates. Le nombre `--count` est un budget de scénarios (plafonds propres à chaque module), pas la promesse d’autant de lignes créées.

### Recalage temporel explicite

```powershell
python -m scripts.demo_generation timeline --demo-live
python -m scripts.demo_generation timeline --demo-live --apply
```

Ne pas relancer automatiquement `timeline`, car la temporalité est un fait métier.

## Qualité, permissions et limites

- Profils `world_*` de démo non-administrateurs. Les Mandates ne découlent pas d’un Membership et n’accordent que l’autorité explicitement prévue.
- Access, AccessCredential, AccessUse et ScanLog sont distincts ; les contrôles sont exécutés par leurs services canoniques, sans imprimer QR ou secret.
- Funding ne se confond pas avec Payment ; aucun versement réel, aucune fausse soumission à un tiers et aucun statut externe simulé comme vrai.
- Le contenu est inspecté, pas multiplié artificiellement : aucun post, média ou ressource sans usage documenté.
- Les autres domaines Django (Trust, CRM, Automation, Dossier, Project, Notifications, Recognition, etc.) nécessitent des scénarios propriétaires supplémentaires avant de pouvoir être déclarés couverts.
- Vérification préalable : `python -m compileall -q scripts/demo_generation`, `python -m unittest scripts.demo_generation.test_cli`, `python manage.py check`.
- CI/test de charge et vérification SQLite requis avant `--count 1000` ou davantage. Aucune migration n’est requise pour ce regroupement.

En cas de conflit Flutter local, terminer la résolution Git avant `pull` ; ne jamais appliquer automatiquement `stash@{0}` si `stash push` n’a rien enregistré. Les répertoires privés ne doivent ni être supprimés ni ajoutés.

## Modules ajoutes — couverture de demonstration a une date

La CLI unique supporte egalement : `media`, `groups`, `objectives`, `notifications`, `trust`, `contributions`, `forms`, `crm`. L'option `--domains all` les inclut, sauf `content` qui reste un inventaire sans mutation.

```powershell
python -m scripts.demo_generation audit
python -m scripts.demo_generation audit --at 2026-10-30T18:00:00+02:00
python -m scripts.demo_generation plan --domains media,groups,objectives,notifications,trust,contributions,forms,crm --count 20
python -m scripts.demo_generation plan --domains all --count 20 --profiles 20 --grant-roles
```

**Medias :** le meme fichier `PresentationAsset` peut etre reemploye sur plusieurs Activity de demonstration **du meme proprietaire autorise** via des lignes `PresentationMediaUse`. Le module utilise `associate_presentation_media` puis `publish_presentation_media`, verifie que le fichier existe, ne copie jamais les octets et n'accorde pas de droit inter-Profil/Espace. Les assets qui n'ont pas de proprietaire compatible ne sont pas reutilises. La publication garde un objectif `recognize`, un texte alternatif et la divulgation minimale. Pour changer de proprietaire il faut un autre contrat, pas une association automatique.

**Groupes :** un Groupe personnel de demonstration peut etre cree par un `world_*` actif, et ses membres ajoutes par le service. Membership n'accorde pas Mandate.

**Dossiers/Projets :** le domaine `objectives` de `scripts.demo_generation`
crée plusieurs Projets et Dossiers par Profil synthétique, y compris des Dossiers
indépendants, des Journey canoniques liées et des dépendances entre démarches.
Les services Objectives contrôlent chaque création, rattachement et dépendance.
Ce n'est pas un task manager artificiel et le seed ne crée aucune Journey.

### Mes démarches — jeu volumineux et sélection des profils

**Toujours commencer par le mode plan (lecture seule).** Les exemples suivants
s'exécutent depuis la racine du dépôt dans PowerShell, sur une **base SQLite de
démonstration isolée** :

```powershell
# Un profil world_ précis, avec 6 Projets et plusieurs Dossiers par Projet
python -m scripts.demo_generation plan --domains objectives --profile-username world_011_divine --count 1 --objectives-projects 6 --objectives-dossiers-per-project 4 --objectives-independent 3
python -m scripts.demo_generation generate --domains objectives --profile-username world_011_divine --count 1 --objectives-projects 6 --objectives-dossiers-per-project 4 --objectives-independent 3

# Sans username : sélection des profils world_* existants (jusqu'à 100)
python -m scripts.demo_generation plan --domains objectives --profiles 100 --count 100
python -m scripts.demo_generation generate --domains objectives --profiles 100 --count 100

# Vérifier les modèles et les données disponibles
python -m scripts.demo_generation inventory
python -m scripts.demo_generation audit
```

### Corpus personnel complet : Objectives, Journey et Access

Le domaine `objectives` **organise** les Journey déjà présentes, mais n'émet
pas d'Access : ce serait dupliquer la responsabilité canonique du domaine
`access`. Pour générer les deux ensembles dans la **même commande**,
sélectionner les domaines concernés. Le paramètre `--count` sert au budget
d'Access, tandis que `--profile-username` sélectionne un seul bénéficiaire.

```powershell
# Prévisualiser pour le persona Mobile Mature synthétique existant.
python -m scripts.demo_generation plan --domains objectives,access --profile-username beta_alain --profiles 1 --count 50 --objectives-projects 6 --objectives-dossiers-per-project 4 --objectives-independent 3

# Créer Dossiers/Projets + Access canoniques pour les Journey éligibles.
python -m scripts.demo_generation generate --domains objectives,access --profile-username beta_alain --profiles 1 --count 50 --objectives-projects 6 --objectives-dossiers-per-project 4 --objectives-independent 3
```

Les Journey préexistantes du persona Mobile Mature sont reconnues à partir
de leur Activity de provenance `mobile-mature-` (et `demo-` lorsque présente).
Les comptes `world_*` continuent d'utiliser `demo-`.
Les Accès sont émis par `access.services.issue_access` avec le credential
du domaine lorsqu'il est applicable. Les Accès historiques expirés sont
conservés comme tels ; le générateur ne simule ni un scan effectué, ni une
validation externe, ni un paiement reçu.

Le message de clôture du générateur décrit la **portée** de la commande et
l'absence d'envoi externe. Ce n'est pas une indication de données manquantes :
consulter les compteurs `eligible_journeys`, `journey_links_created`,
`access_created`, `access_existing` et `access_ineligible` pour le résultat.
Il est normal que `--domains objectives` seul n'émette aucun Access.

Les options du domaine `objectives` sont :
`--objectives-projects` (1–8, défaut 4),
`--objectives-dossiers-per-project` (1–6, défaut 3),
`--objectives-independent` (0–6, défaut 2) et
`--objectives-journeys-per-dossier` (0–4, défaut 2).

`--count` borne le nombre de Profils traités, `--profiles` borne les Profils
`world_*` candidats. `--profile-username` prend priorité pour cibler un
Profil synthétique unique. Aucun identifiant de compte n'est codé en dur.
Une cible explicitement nommée mais non reconnue comme Profil de démonstration
est refusée.

Les scénarios sont déterministes et idempotents par Profil/titre. Le générateur
préserve les rattachements existants même si un Dossier a été déplacé. Il
ne modifie pas les états des Journey, ne simule pas une réussite externe et ne
transmet aucun secret. Les dépendances nécessitent au moins deux Journey
existantes, accessibles au porteur et reliées au même Dossier.

### Schéma Django mis à jour : migrations avant génération

Les commandes `plan` et `generate` des domaines Objectives et
Journey/Access vérifient désormais les migrations en attente **et**
l'existence effective de `journeys_journey.beneficiary_space_id`.
L'absence de cette colonne signifie que le modèle `Journey` courant
et la base SQLite visée ne correspondent pas. Ce n'est pas une erreur
à contourner par une sélection partielle des champs.

Depuis la racine du projet, sur la base **locale de démonstration** :

```powershell
# Identifier les migrations disponibles et les écarts de code.
python manage.py showmigrations journeys
python manage.py migrate --plan
python manage.py makemigrations --check --dry-run

# Après sauvegarde du fichier SQLite et arrêt des processus qui y écrivent,
# appliquer seulement les migrations du projet réellement présentes.
python manage.py migrate

# Relire le jeu existant avant toute nouvelle génération.
python -m scripts.demo_generation plan --domains objectives --profiles 100 --count 100
```

Si `migrate --plan` ne prévoit aucune opération mais que la colonne
manque, vérifier que la migration du **nouveau modèle** existe et que
la base configurée est bien celle attendue. Ne pas utiliser
`--fake`, `--fake-initial` ou une instruction `ALTER TABLE` improvisée.
Si Django propose de nouvelles migrations via
`makemigrations --check --dry-run`, elles doivent être créées,
examinées et versionnées par le chantier de modèle, puis appliquées avec
une stratégie de sauvegarde. Le générateur ne déclenche jamais
`makemigrations` ou `migrate` implicitement.

### SQLite occupée pendant `generate --domains objectives`

Sur Windows, `django.db.utils.OperationalError: database is locked`
signifie qu'une autre connexion ou transaction empêche l'écriture SQLite.
Ce message **ne signifie pas** que le Profil ciblé est interdit ni qu'il
faut effacer la base. La configuration Django prévoit déjà une attente
`DJANGO_SQLITE_TIMEOUT_SECONDS` (20 secondes par défaut). Le générateur
réessaie maintenant jusqu'à trois fois **la transaction complète du Profil**
après rollback et reconnexion, exclusivement pour les erreurs de verrou
SQLite. Les autres erreurs restent visibles.

Avant une relance sur une **base de démonstration isolée**, arrêter les
serveurs Django, tâches de seed concurrentes et outils SQLite qui ont ouvert
la même base. Vérifier la cible SQLite réelle via la configuration, sans
supprimer le fichier de base ni les fichiers `-wal`/`-shm` manuellement.

```powershell
git pull --ff-only
python -m scripts.demo_generation plan --domains objectives --profile-username beta_alain --count 1 --objectives-projects 6 --objectives-dossiers-per-project 4 --objectives-independent 3
python -m scripts.demo_generation generate --domains objectives --profile-username beta_alain --count 1 --objectives-projects 6 --objectives-dossiers-per-project 4 --objectives-independent 3
```

Un `plan` n'écrit rien. Si une tentative de génération échoue, la
transaction du Profil entier est annulée ; une nouvelle exécution peut
reprendre le plan sans dupliquer les éléments déjà validés auparavant.
Un verrou qui persiste nécessite de trouver la connexion concurrente :
ne jamais désactiver la protection des écritures ou forcer le déverrouillage.

La commande Django `seed_mobile_objectives_demo`, auparavant proposée,
**n'est plus disponible** : elle dépendait d'un persona codé en dur et d'une
validation de tout `demo_seed` sans rapport direct avec Objectives.
Utiliser exclusivement la CLI unique ci-dessus.



**Notifications :** deduplication par Journey, notification interne contextuelle uniquement ; aucun email ou push reel n'est envoye depuis le generateur.

**Trust :** des feedbacks peuvent etre produits uniquement lorsque `can_submit_feedback` est vrai. Aucune `Proof`, verification de credential, ou reputation reelle n'est inventee.

**Contributions :** seulement des conseils contextualises par Activity, auteur possedant une Journey, jamais un feed generique.

**Forms :** formulaires rattaches a une Activity de demo et demandes liees a une Journey, sans les presenter comme `Requirement` satisfait.

**CRM :** contacts derives de commandes/billets de demo existants via les services de synchronisation. Pas de consentement marketing imagine ni de campagne externe.

L'audit a date mesure les donnees existantes des parcours Jour J/Live, Access, Scanner, medias, Funding, Services, Obtention et relations. `HAS_DATA` ne vaut pas preuve de couverture fonctionnelle.

### Domaines volontairement non generes sans source de verite

Credential Trust, Proof verifie, usage bancaire reel, versements Funding, scanner physique, veritable reponse de fournisseur, Operation externe, deliverabilite email/push, campagnes CRM, retention analytics, resolution Observer/Prospector et autres faits observes. Leurs tables peuvent rester vides tant qu'aucun fait source n'existe ; remplir ces modeles sans parcours canonique fabriquerait une fausse verite.

Aucun changement de schema/migration n'est requis. Les nouvelles commandes doivent etre validees en SQLite locale avec un petit `--count` et les tests cibles avant 1000 ou 10000 operations.

### Complements Jour J : placement et incidents

`placement` cree des zones logiques par Occurrence active et des affectations aux beneficiaires de Journey via `assign_placement`. **Placement ne represente pas la Capacity** ; il n'ajoute aucun siege vendu ni aucun nouveau droit d'acces.

`incidents` cree seulement des incidents explicitement synthetiques (marquage dans `metadata`) via `create_incident`, lorsque l'acteur possede l'autorite de gestion pertinente. Si les Mandates sont insuffisants, le rapport `incidents_no_authority_or_invalid` est attendu : pas de contournement.

```powershell
python -m scripts.demo_generation plan --domains placement,incidents --count 10
python -m scripts.demo_generation plan --domains media,forms,crm,groups,objectives,trust,notifications,contributions --count 10
```

Les modules `media`, `engagement`, `community`, `live` et `audit` restent **internes** au dossier `scripts/demo_generation` ; tous les appels utilisateurs passent par la CLI unique.

N'executer `generate` qu'apres un plan cible, et seulement sur SQLite de demo. La couverture `all` n'est pas une certification que les 338 tables reelles sont peuplees : elles contiennent aussi des projections, secrets, faits externes et tables d'infrastructure qu'il est dangereux de simuler par insertion directe.

## Couverture exhaustive du registre Django (octobre 2026)

`inventory` parcourt **tous** les modeles effectivement installes (338 dans la SQLite locale du 31 octobre), sans maintenir une liste de noms qui se perime :

```powershell
python -m scripts.demo_generation inventory
python -m scripts.demo_generation audit
```

Chaque ligne du catalogue fournit le nom du modele, le nombre d'enregistrements et une **politique** : `domain` (scenario via services canoniques), `context` (depend d'un proprietaire/relation), `derived` (produit par le travail/event), `observed` (fait issu du runtime), `protected` (credential/secret), `runtime` (tables framework), `review` (domaine non classe). **Toutes les tables sont controlees ; aucune ligne fictive n'est inseree automatiquement dans les tables sensibles, d'audit ou techniques.** Ce choix preserve les invariants Makolo.

`audit` presente maintenant deux mesures distinctes : **lignes dans le perimetre demo-** et **lignes dans l'ensemble de la SQLite**. Par exemple les 29 `FundingDetails`, 101 `ServiceDetails`, 27 `ObtentionDetails` de l'inventaire initial ne sont pas automatiquement des scenarii `demo-*`, mais ils ne doivent pas etre declares inexistants. L'etat `EXISTS_OUTSIDE_DEMO` signale explicitement cette difference.

### Creation canonique des verticales manquantes

Le module interne `foundations.py` cree, avec une identification `demo-generation-<domaine>-NNNN`, les **Activity + specialisee** de demonstration pour `funding`, `services` et `obtention` via les services metier. Les mandats d'autorite pour une Activity appartenant a un Profil sont ceux produits par la creation canonique ; pas de role global.

```powershell
python -m scripts.demo_generation plan --domains funding,services,obtention --count 4
python -m scripts.demo_generation generate --domains funding,services,obtention --count 4
python -m scripts.demo_generation audit
```

Les 4 cas par domaine restent des exemples : la commande `generate` doit etre testee localement avant des volumes eleves. Les intitules sont explicitement synthetiques et les paiements/reussites ne sont pas fictivement declares reels. Les modules `verticals.py` construisent ensuite les Journey, choix de mode et intentions de contribution **sur ces Activity**.

### Parcours Live

`scale.py` repartit maintenant la preparation des Journey sur des Occurrences distinctes (au lieu d'epuiser tous les profils sur la premiere) et selectionne pour les tests Scanner les **Event possedant une Occurrence actuellement active** plutot que les premiers UUID d'une table de milliers d'events. Ces corrections ciblent la cause des compteurs `scan_log: 0` / `queue_live: 0` lors de l'audit au 31 octobre.

Une date glissante et une base immuable ne garantissent pas en permanence les memes Occurrences Live. Utiliser `timeline` explicitement lorsque necessaire, et ne jamais modifier silencieusement le temps de la production.

### Partage

`community.py` offre aussi `sharing` : creation idempotente de liens de partage pour des Activity publiques de demonstration via `create_activity_share`. Les jetons ne sont jamais imprimes ni exposes. `Sharing` n'accorde aucun droit d'Access.

```powershell
python -m scripts.demo_generation plan --domains sharing,groups,objectives --count 10
```

**Important :** avoir 338 modeles recenses et evalues est possible ; exiger des objets inventes dans chaque modele n'est pas une condition de maturite. Par exemple `ProviderCredential`, `SocialToken`, `Settlement`, `VerificationClaim`, `ObserverBlob`, `DomainEventConsumption`, `PaymentEvent` et les tables Django de session/blacklist ne constituent pas des activites utilisateur a simuler par lignes directes. L'inventaire sert a piloter leur couverture par scenarios/faits canoniques.

## Scenarios supplementaires pour une BDD ayant une histoire

**Apres le controle local des 339 modeles, 120 etaient remplis et 219 vides.** Le registre dynamique `inventory` ne promet pas un objet pour chaque table technique. La preparation transversale vise une **histoire fonctionnelle** : activites terminees et futures, operations Jour J, droits et passages, achats et Funding confirmes en sandbox, opportunites proposees/revues, suivi personnel, Espaces et fidelite.

Nouveaux modules internes :

- `personal.py` : **Discovery** bookmarks/veilles, **Goals** actifs par mois, suivi d'Espaces par les `world_*`. Aucun Preference/OpenTo n'est deduit implicitement d'un bookmark.
- `ecosystem.py` : **Spaces** fictifs possedes par des Profiles, Teams et Mandates crees via `create_organization` / `add_or_update_member`, Activity/Occurrences appartenant a ces Espaces avec passage d'une Occurrence historique a `completed` par le service ; **Loyalty** programmes, tiers, memberships gratuits actives par le service ; **Automation** politiques Event par `ensure_policy`.
- `verticals.py` : **Funding** contributions liees a de vraies obligations de paiement et paiement `sandbox` via `initiate_obligation_payment` puis `complete_sandbox_payment` ; **Opportunities** soumissions et revue par un curateur ayant effectivement la permission, a defaut en attente.
- `scale.py` : paiements **Event** utilises par `create_order`, `initiate_payment`, `complete_sandbox_payment` et les services d'emission ; Scanner et AccessUse via les contrats canoniques.
- `community.py` : **Trust** Proof privee seulement si un `AccessUse.ACCEPTED` existe, et Reports marques DEMO (pas de preuve inventee).
- `mandates.py` : l'ordre d'octroi des droits sur les Activity actives est aligne sur les Occurrences Live auxquelles `scale.py` rattache les Journey.

**Sandbox pour SQLite seulement :** les operations payantes lancent temporairement les services sous `override_settings(PAYMENTS_SANDBOX_ENABLED=True)` ; ce contexte local ne modifie ni la configuration de deploiement ni le choix des providers sur le site. Les transactions bancaires reelles ne sont jamais appelees. Les services emettent leurs propres domain events, payment obligations, tickets, etc. selon leurs regles actuelles.

```powershell
python -m compileall -q scripts/demo_generation
python -m unittest scripts.demo_generation.test_cli -v
python manage.py check

python -m scripts.demo_generation plan --domains spaces,loyalty,automation,discovery,goals,space --count 5 --profiles 10
python -m scripts.demo_generation plan --domains funding,services,obtention,opportunities --count 5 --profiles 10
python -m scripts.demo_generation plan --domains all --count 10 --profiles 10 --grant-roles
```

Apres les controles ci-dessus, une demonstration integrale **de petit volume** utilise :

```powershell
python -m scripts.demo_generation generate --domains all --count 10 --profiles 10 --grant-roles
python -m scripts.demo_generation audit
python -m scripts.demo_generation inventory
```

L'enchainement `generate` execute les dependances dans cet ordre : Espaces/Loyalty/Automation, donnees personnelles, Transport, Mandates Live, fondations Funding/Services/Obtention, leurs Journey et paiements sandbox, puis parcours transversaux, placement, Trust, Forms, medias. Il n'ajoute pas de media sans contexte ni ne donne d'autorite via la seule appartenance a un Groupe.

**Important pour un vrai jeu de tests :** `plan` lit l'etat **avant** la generation. Ses compteurs `ops_no_journey` ou `scanner_candidates=0` peuvent donc disparaitre apres la creation des Journey, Access et Mandates en amont. Lire `audit` **apres** un petit `generate` pour mesurer la couverture obtenue. Si les services refusent une creation, corriger la cause racine et conserver leur validation, sans insertion SQL directe.

## Fermeture des scenarios transversaux : session d'octobre 2026

Le jeu de demonstration comporte maintenant les modules **personnels** (Discover/Veilles, Goals, suivi d'Espaces), **Espace et historique** (Space, Team, Mandates, Activity, Occurrence passe/en cours/demain, Loyalty et Membership gratuit, policies Automation), **commerce et Funding** (PaymentObligation, Payment sandbox, Ticket, Access), **Opportunities** (proposition et revue/deduplication autorisee) et **apres l'action** (`outcomes`: Journey `fulfilled`, Proof privee et reevaluation Goals apres AccessUse acceptee).

Le module `aftercare.py` n'invente pas d'accomplissement : il exige un `AccessUse` dont le resultat est `accepted` pour une Journey confirmee et exclut les parcours Services qui ont leur propre politique de completion. Le module Trust cree ensuite des feedbacks admissibles et des signalements de demonstration contextualises, sans exposer de donnees personnelles.

**Le plan ne remplit pas encore les domaines de configuration ou de fait exterieur suivants simplement parce que leur table est vide :** comptes tiers, credentials/secrets, moteur Observer/Interpreter/Prospector/Resolver, banques et paiements reels, historiques de livraison externe, analytics derivees non materialisees et marques de confiance sans fait source. Ces modeles restent dans l'inventaire dynamique et les cas d'essai des services correspondants.

La priorite du simulateur est la coherence temporelle : les droits des operateurs ciblent les memes Occurrences Live que les Journey, le Scanner redecouvre les Events actifs, le paiement sandbox emprunte les vrais services, et `outcomes` realise les demarches ayant un passage accepte. Le test utilisateur demeure indispensable pour s'assurer que les frontends Web/Flutter affichent correctement les projections.

Commandes de controle avant tout grand volume :

```powershell
python -m compileall -q scripts/demo_generation
python -m unittest scripts.demo_generation.test_cli -v
python manage.py check
python -m scripts.demo_generation inventory
python -m scripts.demo_generation audit
python -m scripts.demo_generation plan --domains all --count 10 --profiles 10 --grant-roles
```

`inventory` donnait **339** modeles installes dans le journal du 31 octobre 2026 : ne pas figer ce nombre dans le code. La ventilation et les totaux changent quand de nouveaux modeles/migrations arrivent.

## Validation automatisée (commande unique)

La CLI transversale possède `validate`, sans écriture dans la SQLite de démonstration :

```powershell
python -m scripts.demo_generation validate --quick
python -m scripts.demo_generation validate
```

- `--quick` teste l'interface et l'intégration isolée, y compris Funding, contribution, idempotence et satisfaction de PaymentObligation par services canoniques.
- Sans `--quick`, le lanceur ajoute les suites Django existantes des domaines Funding, Payments, Journey, Access, Scanner, Operations, Services, Obtention, Tickets, Présentation et Organizations.
- Django prépare une base de test distincte, applique les migrations, puis détruit cette base. `TEST.NAME` ne peut pas pointer vers la base ordinaire.
- `--failfast` interrompt au premier échec; `--verbosity 2` affiche les détails. Échec = code retour non nul.
- Le résultat ne certifie pas automatiquement les projections web/mobile ; après validation, vérifier un petit `generate` puis `audit` avant toute charge de 1000/10000.

L'interface conserve une seule entrée : `inventory`, `audit`, `validate`, `plan` et `generate` passent par `python -m scripts.demo_generation`.

## Cibler un compte existant pour les prochaines donnees

La CLI accepte `--profile-username beta_alain` pour les domaines `discovery,goals,space,journeys,access,commerce`. Le compte doit etre actif, non-staff et non-superuser. Les nouvelles Journey, Access, commandes, favoris, veilles et objectifs sont alors lies au compte explicitement selectionne, sans renommage et sans copie de donnees des profils `world_*`. Les autres domaines restent refuses explicitement sous ce mode, car certains scenarii exigent des acteurs et proprietaires differents ; ne pas utiliser `--domains all` avec cette option.

```bash
python -m scripts.demo_generation plan --domains discovery,goals,space,journeys,access,commerce --count 20 --profiles 1 --profile-username beta_alain
python -m scripts.demo_generation generate --domains discovery,goals,space,journeys,access,commerce --count 20 --profiles 1 --profile-username beta_alain
```

Le domaine `media` continue de reutiliser les `PresentationAsset` deja associes a des Activity anciennes, si le fichier existe physiquement et si l'acteur dispose des droits. Il ne copie aucun fichier ni transfert de propriete. `MEDIA ... assets_files_available=0` signale un blocage reel du stockage sur l'environnement : les 314 enregistrements ne peuvent pas devenir des images fonctionnelles sans fichier sous-jacent.

## Abonnements payants de demonstration (opt-in)

Les domaines existants `subscriptions` et `payments` gerent le catalogue `SubscriptionPlan`/`PlanVersion`/`PlanEntitlement`, les subscriptions du Profile ou Space, les transitions, `PlanVersionBillingTerms` et `SubscriptionBillingObligation` liees a `PaymentObligation`. Le module `scripts/demo_generation/subscriptions.py` cible un Profile existant et **n'invente ni tarif ni entitlement** : il choisit exclusivement des ADDON Profile publies avec termes de facturation payants dans le catalogue courant. Il passe par `request_subscription_transition`, puis paiement `sandbox` avec les services canoniques et `complete_subscription_transition` quand l'obligation est satisfaite.

```bash
python -m scripts.demo_generation plan --domains subscriptions --profile-username beta_alain --count 3
python -m scripts.demo_generation generate --domains subscriptions --profile-username beta_alain --count 3
```

Ce domaine est volontairement exclu de `--domains all` et exige un username explicite. Si aucun tarif payant n'existe dans le catalogue actif, le compteur indique `NO_PAID_CATALOG` : publier d'abord une vraie formule de demonstration et ses capacites, sans dupliquer de verites metier. Le sandbox ne correspond a aucun paiement bancaire reel.

## Selection des profils : mode general et mode cible

Le generateur ne depend d'aucun username code en dur. Pour chaque domaine accepte, `--profile-username <username>` cible le beneficiaire personnel indique ; sans cette option, les comptes synthetiques eligibles `world_*` restent selectionnes avec `--profiles N`. Les operateurs de Scanner, responsables de Space et autorites de Mandate restent des roles contextuels distincts du beneficiaire. La creation de contenus communs (catalogues, media et Activity appartenant a d'autres responsables) n'est pas automatiquement personnalisee par le username ; les droits proprietaires sont verifies par leurs services.

```bash
python -m scripts.demo_generation plan --domains all --count 20 --profiles 20
python -m scripts.demo_generation plan --domains all --count 20 --profiles 1 --profile-username beta_alain
python -m scripts.demo_generation plan --domains subscriptions --count 2 --profiles 20
python -m scripts.demo_generation plan --domains subscriptions --count 2 --profile-username beta_alain
```

`subscriptions` est volontairement opt-in : le domaine peut etre genere pour tous les `world_*` ou un seul utilisateur, mais n'est pas declenche par `all` pour eviter de facturer automatiquement chaque profil lors des lots generaux. Ce sont exclusivement des tentatives de paiement sandbox sur SQLite de test.

## Catalogue des forfaits avant attribution

La commande opt-in `--domains subscription-catalog` cree six forfaits clairement marques DEMO, pour Profil et Espace, avec versions publiees, tarifs fictifs USD par mois et Entitlements reels fondes sur les FeatureDefinition existantes. Le catalogue ne remplace aucun BASE par defaut et n'affecte aucun compte lors de sa creation. Le script est idempotent par code de forfait et refuse toute collision de type ou de sujet. Il ne constitue pas une publication de tarifs commerciaux officiels.

```bash
python -m scripts.demo_generation plan --domains subscription-catalog
python -m scripts.demo_generation generate --domains subscription-catalog
```

Les changements entre BASE (ex. gratuit vers Profil Plus ou Profil Max) exigent la transition canonique `BASE_SWITCH`, distincte de la commande de facturation add-on actuellement disponible. Ne pas employer `--domains subscriptions` pour attribuer les BASE tant que ce support n'est pas ajoute et valide. Toujours travailler dans la SQLite de demonstration.

## Connexions / Intelligence — couverture sans connexion fictive

`python -m scripts.demo_generation plan --domains connections` expose le catalogue des offres propriétaires Tavily, Exa, OpenAI API et OpenAI Web Research, puis les comptes réels de `ProviderConnection`, `IntelligenceRoute`, `ProviderCredential` et `PushEndpoint` selon leur portée. `generate --domains connections` exécute le même diagnostic sans mutation : une relation d'autorisation ne peut pas être créée par un générateur sans le consentement de son propriétaire et un véritable secret fourni par celui-ci. Le catalogue lui-même est défini dans `intelligence.connection_management.OFFERS` et n'a besoin d'aucune insertion en base. Les routes doivent provenir de `create_connection`, les clés du propriétaire chiffré, et les PushEndpoint des installations natives. Le champ `can_connect` indique la configuration serveur requise sans exposer de secret.

Pour obtenir un état réellement connecté dans la bêta, le propriétaire effectue le POST propriétaire Intelligence depuis la future UX, avec `provider`, `name`, `api_key`, `model` si requis, et `consent: true`. La disponibilité réelle de la clé n'est pas déduite de sa création. Ce protocole ne simule aucun OAuth. Aucune donnée de clé ni jeton complet ne doit apparaître dans les journaux d'audit.

## 50 choix Connexions de démonstration — application PythonAnywhere

Le domaine `connections` comprend désormais 50 simulations combinant cinq familles de capacités et dix contextes. L'API de catalogue Intelligence expose ces offres après les quatre offres externes fixes, avec `demo=true`. Un POST propriétaire sur un code `demo-*` exige `consent=true`, mais pas de clé API; il crée des `ProviderConnection` et `IntelligenceRoute` désactivées, sans `ProviderCredential`. Les vues de gestion et le DELETE existants restent disponibles. Le provider externe n'est jamais appelé par ces simulations. La projection indique `simulation_only=true`, `external_execution=false`.

Depuis la console existante (SQLite de test uniquement), pour remplir les deux profils synthétiques existants avec **50 relations démo réparties** :

```bash
python -m scripts.demo_generation generate --domains connections --count 50 --profiles 2
```

Pour choisir directement un utilisateur synthétique existant (et non en créer un) :

```bash
python -m scripts.demo_generation generate --domains connections --count 50 --profiles 2 --profile-username world_example
```

Remplacer `world_example` par un vrai username synthétique; ne pas inventer un compte. Le catalogue contient 50 options, mais ce ne sont pas 50 intégrations tierces fonctionnelles. Les connexions réelles restent soumises aux clés, à la configuration et au consentement d'origine.

## Conversations Makolo : scénarios contextualisés et temporels

Le domaine `conversations` est intégré à la CLI de démonstration. Il ne crée ni feed, ni chat type WhatsApp. Il utilise `ensure_context_conversation`, `create_point`, `submit_point_response`, `create_exchange_entry`, `resolve_point` et les politiques/permissions serveur. Les contextes sélectionnés sont **Activity, Occurrence, Journey, Space, Group, Dossier, Project, ActionProposal**. Les échanges directs entre personnes ne sont pas auto-fabriqués : ils supposent leur contrat de consentement bilatéral.

Une Conversation de démonstration contient jusqu'à quatre Points utiles : information, question, confirmation, sondage, demande ou échange selon le contexte. Les réponses structurées sont limitées aux autres profils déjà éligibles dans le contexte; aucune Membership ou Mandate n'est inventée. Les réponses, résolutions et Points sont idempotents via leurs références déterministes.

Les Occurrences déterminent le **type d'histoire au moment du lancement** : terminée (bilan), Live (coordination immédiate), future (préparation). Les états temporels du métier ne sont pas confondus avec les timestamps d'audit : on ne prétend pas qu'un Point fraîchement généré a été publié dans le passé.

Exemples pour la SQLite de test déjà configurée :

```bash
python -m scripts.demo_generation plan --domains conversations --count 500 --profiles 30 --seed 2026
python -m scripts.demo_generation generate --domains conversations --count 500 --profiles 30 --seed 2026 --conversation-points 4
python -m scripts.demo_generation generate --domains conversations --count 500 --profile-username world_011_divine --seed 2027
```

`--count 500` est un plafond de **500 Conversations contextuelles distinctes** (pas 500 publications par conversation). Le résultat peut être inférieur si les utilisateurs existants manquent de contextes admissibles. La même graine permet une sélection reproductible; changer `--seed` renouvelle la sélection des contextes mais ne crée pas de doublons pour le même contexte et la même finalité. `--profile-username` cible un compte existant pour les contextes qu'il possède ou peut gérer, sans forcer l'accès à d'autres Conversations privées.

Pour inspecter le résultat réel :

```bash
python manage.py shell -c "from conversations.models import Conversation,ConversationPoint,ConversationPointResponse; print('Conversations',Conversation.objects.count(),'Points',ConversationPoint.objects.count(),'Réponses',ConversationPointResponse.objects.count())"
```

La génération ne garantit ni la couverture de toutes les sous-tables avancées (audiences détaillées, demandes d'invitation, bridges média/formulaires), ni la création de 500 Conversations si moins de 500 contextes propriétaires sont admissibles. Ces sous-parcours ne doivent pas être inventés pour remplir artificiellement toutes les tables.

### Acteurs diversifiés et Conversations vivantes

Avec `--conversation-include-test-users`, la sélection inclut aussi les comptes synthétiques existants `beta_*` et `mobile_mature_*`, en plus de `world_*`. Aucun nouveau compte n'est créé. Cette option est utile quand l'environnement bêta ne contient que deux `world_*` mais plusieurs organisateurs/opérateurs de test.

```bash
python -m scripts.demo_generation generate --domains conversations --count 500 --profiles 30 --conversation-include-test-users --seed 2026 --conversation-points 4
python -m scripts.demo_generation generate --domains conversations --count 500 --profile-username mobile_mature_owner --seed 2027
```

Les gestionnaires ne peuvent ajouter une participation explicite que pour un autre compte de démonstration ayant déjà le droit de voir le contexte. Les Points d'information peuvent générer une confirmation de lecture; les Points Exchange, une intervention suivie d'une réponse chaînée. Certaines Conversations dont l'Occurrence est terminée sont closes par `transition_conversation` après génération; elles ne sont jamais antidatées. Les refus d'autorité sont comptabilisés et n'entraînent pas la création d'un Mandate implicite.

## Règle éditoriale des générateurs — novembre 2026

À partir de cette révision, les créations de `foundations`, `verticals`, `transport`, `scale`, `community`, `engagement`, `live`, `personal`, `ecosystem`, `media`, `subscription-catalog`, `connections` et `conversations` produisent des **titres, libellés et descriptions de présentation naturels**. Les noms issus du vocabulaire partagé (`scripts/demo_generation/editorial.py`) sont déterministes et évitent les usernames techniques ou les numérotations artificielles dans les titres.

Les références internes, slugs, codes, clés d'idempotence et métadonnées peuvent continuer à contenir `demo` : ce sont des identifiants techniques utilisés pour limiter la génération et empêcher les doublons. **Ne pas retirer ces marqueurs techniques** par remplacement global. Pour les `ProviderConnection` simulées, le marqueur interne `default_model=demo-disabled` protège contre l'activation externe ; le nom visible est naturel. Une connexion simulée attachée à un Profil possède `connected=true` au sens relationnel, mais `usable=false`, `enabled=false` et `external_execution=false` : elle n'autorise aucun appel fournisseur.

Les recherches de compatibilité acceptent les anciens libellés `[DEMO]` afin de réutiliser les objets déjà créés. **Les données déjà stockées ne sont pas renommées en masse par `generate`** : le nettoyage éditorial de la copie SQLite est une opération distincte avec sauvegarde préalable. Les offres d'abonnement publiées conservent leurs règles d'immutabilité ; aucune mise à jour silencieuse de leurs versions.

Pour examiner uniquement ces deux domaines avant de générer, ou pour viser un compte de test déjà présent :

```bash
python -m scripts.demo_generation plan --domains connections,conversations --count 500 --profiles 30
python -m scripts.demo_generation generate --domains connections --count 50 --profile-username world_011_divine
python -m scripts.demo_generation generate --domains conversations --count 500 --profile-username mobile_mature_owner --seed 2026 --conversation-points 4
```

Les comptes, les liens Activity/Occurrence/Journey et les Mandates restent ceux qui existent dans la base. Les appels sortants, les credentials, les justificatifs et les confirmations de paiement ne sont jamais inventés pour augmenter les compteurs. Le test ciblé des textes et des services est exécuté via le workflow de validation de génération et ses dépendances Django, pas via une modification directe de `main`.


## Fermeture éditoriale et reprise des données (4 novembre 2026)

Les générateurs de `scripts/demo_generation/` et les sources de `demo_seed/`
utilisent désormais des noms, descriptions et échanges naturels, sans titres
`[DEMO]`, `Exemple fictif` ou mentions de sandbox dans le contenu visible
nouvellement créé. Les slugs, codes internes et clés d'idempotence conservent
leur provenance; ils ne doivent pas être renommés par recherche/remplacement.

- `editorial.py` choisit des noms stables pour les Espaces, Groupes, Dossiers,
  Projects et Activities, sans afficher de usernames techniques.
- Les recherches de compatibilité réutilisent les anciens objets, y compris
  les noms dont un préfixe visible a déjà été retiré.
- `connections` répartit les offres par tour complet entre les utilisateurs:
  `--count 100 --profiles 2` vise 50 relations différentes par Profil,
  tandis que `--count 50 --profiles 2` en vise 25 par Profil. Le maximum
  reste 50 offres par Profil; aucune credential externe n'est créée.
- `foundations` respecte `--profile-username`, y compris via la CLI transverse.
- `conversations` peut compléter les réponses et échanges manquants d'un
  Point existant et ne réactive pas une participation déjà active. Les
  Conversations closes restent closes; les timestamps d'audit ne sont pas
  antidatés.
- Les associations média n'héritent plus des anciens alt-text de remplissage
  synthétique. Un fichier absent reste bloquant.

Les enregistrements **déjà stockés** et les versions d'Abonnement publiées
ne sont pas modifiés en masse par ces corrections de générateurs.
Le nettoyage d'une copie de la SQLite reste une opération séparée, avec
sauvegarde, comme convenu.

Tests de non-régression: `scripts.demo_generation.test_cli` vérifie
notamment la rotation complète des 50 choix pour deux Profils, la transmission
de `--profile-username`, les textes déterministes et les scénarios de
Conversations. Le workflow `demo-generation-validation.yml` est le gate
CI applicable avant toute fusion.


## Boîte à outils d'entretien — PR #522 (novembre 2026)

La source durable est le code GitHub. Les opérations sur une SQLite de démonstration
sont **manuelles** : aucune commande n'est lancée par un scheduler, le démarrage
du serveur ou un déploiement normal. Sans `--apply`, elles présentent un aperçu.

La commande unique demeure `python -m scripts.demo_generation` :

```bash
# Génération initiale ou complément (prévisualisation puis application).
python -m scripts.demo_generation plan --domains funding,services,obtention --count 20
python -m scripts.demo_generation maintain --action complete --domains funding,services,obtention --count 20
python -m scripts.demo_generation maintain --action complete --domains funding,services,obtention --count 20 --apply --backup

# Recalage : tous les slugs d'Activity commençant par demo-, pas seulement demo-2026-q4-.
python -m scripts.demo_generation timeline --database db.sqlite3 --demo-live --mode safe
python -m scripts.demo_generation timeline --database db.sqlite3 --demo-live --mode safe --backup --apply

# Cibler une sous-famille; full est un voyage temporel historique explicite.
python -m scripts.demo_generation timeline --activity-prefix demo-generation- --limit 20
python -m scripts.demo_generation timeline --activity-prefix demo-generation- --mode full --backup --apply

# Rééquilibrage borné des favoris des profils et des suivis d'Espaces synthétiques.
python -m scripts.demo_generation rebalance --target profiles --per-profile 3 --count 50
python -m scripts.demo_generation rebalance --target profiles --per-profile 3 --count 50 --apply
python -m scripts.demo_generation rebalance --target spaces --per-profile 2 --count 50 --apply --backup
# Reduire volontairement les favoris/suivis synthetiques en excedent.
python -m scripts.demo_generation rebalance --target profiles --direction trim --per-profile 3 --count 50
python -m scripts.demo_generation rebalance --target spaces --direction trim --per-profile 2 --count 50 --apply --backup
python -m scripts.demo_generation rebalance --target periods --demo-live --limit 30 --apply

# Actualisation éditoriale déterministe et répétable pour une édition donnée.
python -m scripts.demo_generation maintain --action refresh --edition 2 --count 20
python -m scripts.demo_generation maintain --action refresh --edition 2 --count 20 --apply --backup

# Entretien réversible : archiver uniquement les Activities demo sans dépendance métier.
python -m scripts.demo_generation maintain --action retire --older-than-days 30 --count 10
python -m scripts.demo_generation maintain --action retire --older-than-days 30 --count 10 --apply --backup
python -m scripts.demo_generation maintain --action restore --count 10 --apply
```

### Périmètre et protection des relations

- Le namespace technique d'Activity `demo-*` est commun à la génération, au
  recalage et aux opérations d'entretien. Le préfixe peut être **restreint** par
  `--activity-prefix`, jamais élargi silencieusement à des Activities réelles.
- `timeline --mode safe` ne recale pas une Occurrence annulée/terminée,
  un Access déjà utilisé ou un Journey terminal. Il actualise les fenêtres
  des relations actives sans déplacer les dates historiques d'usage, de
  révocation ou d'achèvement. `--mode full` permet le déplacement historique
  **explicitement** pour les seuls scénarios synthétiques visés.
- `--include-existing` pour inclure les Occurrences non synthétiques reste
  une option exceptionnelle et ne peut pas être combinée avec `--mode full`.
  L'opération écrit directement dans la SQLite choisie, sans sauvegarde implicite.
- `rebalance --target profiles` ajuste les favoris synthétiques des
  utilisateurs `world_*` ; `spaces` ajuste leurs suivis d'Espaces de démo.
  `--direction add` (défaut) complète jusqu'à `--per-profile`, tandis que
  `--direction trim` réduit seulement les relations en excès, lorsque
  `--apply` est donné, sans sauvegarde automatique. `--activity-prefix` permet
  de limiter la famille d'Activity. Ces opérations **ne changent pas**
  les propriétaires, l'appartenance Team, les Mandates, les Journey ou Payment.
- `maintain --action complete` **réutilise** les générateurs existants et leurs
  chemins idempotents, sans moteur ORM parallèle. Selon le domaine, il peut
  donc aussi créer une fondation manquante. `--domains all --apply` nécessite
  l'autorisation explicite `--grant-roles` existante.
- `refresh` ne modifie que `short_description` des Activities synthétiques
  éligibles, avec un texte stable par `--edition` ; `retire` archive sans
  supprimer des lignes et refuse les Activities liées aux Occurrences,
  Journeys, Access, Event, Offer ou Contributions Funding. `restore` réactive
  les Activities archivées sélectionnées.
- Les mutations éditoriales et les archives sont limitées aux propriétaires de
  démonstration `world_*` (Profil ou créateur de Space). Cela ne prétend
  pas entretenir les comptes bêta ou d'autres environnements.
- Par défaut, toutes les opérations `--apply` modifient la SQLite existante
  directement, sans créer de copie ni de sauvegarde. Une copie n'est produite
  qu'avec `timeline --output <chemin>` et une sauvegarde uniquement lorsque
  `--backup` est explicitement fourni. Cela vaut aussi pour
  `timeline --mode full`, `--include-existing` et `rebalance --direction trim`.
  Des échecs d'opérations
  propriétaire sont rapportés, pas compensés par des permissions inventées.

Ces commandes permettent de maintenir un univers de démo vivant, sans
supprimer les historiques ni fabriquer des attestations externes. Une
couverture réaliste n'exige ni table entièrement remplie ni volume arbitraire.


## Mes ressources : documents, preuves et titres (novembre 2026)

Les trois tuiles de « Moi > Mes ressources » reposent sur des domaines
canoniques différents : `PersonalAsset` et `PersonalAssetVersion` pour
« Mes documents », `Trust Proof` pour « Mes preuves », et `Trust Credential`
pour « Mes titres ». Il ne faut pas simuler leur compteur dans le client.

La commande `resources` enrichit la SQLite de démonstration **en place**
uniquement si `--apply` est fourni. Sans ce drapeau, elle présente un aperçu.
Elle n'effectue aucune sauvegarde par défaut ; `--backup` en crée une
uniquement lorsqu'il est demandé.

```powershell
# Cibler le compte affiché dans l'émulateur (username à vérifier dans la DB).
python -m scripts.demo_generation resources --profile-username beta_alain
python -m scripts.demo_generation resources --profile-username beta_alain --apply

# Cibler seulement les documents.
python -m scripts.demo_generation resources --domains documents --profile-username beta_alain --count 4 --apply

# Couvrir les profils world_* existants.
python -m scripts.demo_generation resources --profiles 30 --count 4 --apply

# Inclure aussi les profils beta_* et mobile_mature_* existants.
python -m scripts.demo_generation resources --include-test-users --profiles 50 --apply

# Documents texte uniquement, ou sauvegarde choisie explicitement.
python -m scripts.demo_generation resources --profile-username beta_alain --no-reuse-avatar --apply
python -m scripts.demo_generation resources --profile-username beta_alain --apply --backup
```

### Sources et cohérence

- **Documents :** un texte de démonstration original (`.txt`), dont les octets
  passent par les validations et le stockage privé des services PersonalAsset.
  Si le Profil cible possède déjà un avatar JPEG/PNG valide dans son stockage,
  le générateur peut en **copier les octets** comme « Copie de ma photo de
  profil ». Il ne copie pas l'avatar d'un tiers et ne se contente pas de
  remplir une URL fictive. `--no-reuse-avatar` désactive cette possibilité.
  Aucun téléchargement depuis un site internet n'est effectué.
- **Preuves :** uniquement si une Journey existante a été accomplie, ou si un
  AccessUse accepté établit un fait éligible ; utilisation du service
  `trust.services.issue_proof`. Le générateur ne fabrique ni AccessUse accepté
  ni Journey accomplie pour remplir artificiellement cette rubrique.
- **Titres :** une attestation de complétion/participation exige la Journey et
  le fait canonique correspondant. Pour tester les titres sans prétendre
  qu'une Journey a été accomplie, le générateur peut aussi émettre une
  **attestation générique explicitement fictive** depuis une Activity
  synthétique publiée, exclusivement si un émetteur possède réellement le
  Mandate requis par `issue_credential`. Aucun droit n'est créé par ce script.
- **Relance :** les titres d'éléments sont stables ; la commande réutilise les
  documents, Proofs et Credentials déjà présents plutôt que de créer des
  doublons. Le nombre `--count` fixe le maximum par rubrique et par Profil
  sélectionné.
- **Portée :** le username ciblé est recherché parmi les comptes existants et
  actifs, hors staff et superutilisateurs. Sans username, seuls `world_*`
  sont sélectionnés, sauf opt-in `--include-test-users`. Aucun compte n'est
  créé et aucune preuve privée d'un autre Profil n'est copiée.

Une rubrique peut rester vide si les faits ou les autorités nécessaires
n'existent pas ; c'est différent de la génération des documents, qui ne
requiert pas de Journey.


## Conversations collectives et profils principaux multiples (novembre 2026)

Le générateur de Conversations distingue désormais **profils principaux** et
**participants** : un profil ciblé est l'acteur principal, pas son propre
interlocuteur. Le script cherche des contextes réels appartenant aux profils
sélectionnés (Space, Group, Activity, Occurrence, Journey, Dossier, Project,
ActionProposal). Les autres participants proviennent du sélecteur canonique
`conversation_viewer_ids`, et les réponses passent par les permissions des
Points. Aucune Conversation `DIRECT` et aucun droit nouveau ne sont inventés.

```bash
# Aperçu : profils world_* prélevés de manière pseudo-aléatoire reproductible.
python -m scripts.demo_generation plan --domains conversations --profiles 30 --count 80 --seed 2026

# Génération générale, avec comptes beta_* et mobile_mature_* déjà présents.
python -m scripts.demo_generation generate --domains conversations --conversation-include-test-users --profiles 40 --count 80 --seed 2026

# Un seul principal, plusieurs interlocuteurs permis par ses contextes.
python -m scripts.demo_generation generate --domains conversations --profile-username beta_alain --count 30 --conversation-max-participants 8

# Trois profils principaux, dont les Conversations sont distribuées.
python -m scripts.demo_generation generate --domains conversations --conversation-usernames beta_alain,world_002_grace,world_003_sarah --count 60 --conversation-max-participants 10

# Cinq profils / contextes collectifs (sans obligation de tout remplir).
python -m scripts.demo_generation generate --domains conversations --conversation-usernames beta_alain,world_002_grace,world_003_sarah,world_004_naomi,world_005_esther --conversation-context-types space,group,activity,occurrence --count 80

# Choix ordonné, reproductible sans tirage, pour comparer des démonstrations.
python -m scripts.demo_generation plan --domains conversations --conversation-selection ordered --profiles 20
```

- `--profile-username` reste compatible (un profil principal).
  `--conversation-usernames` est une liste séparée par virgules : une,
  trois, cinq personnes ou davantage. Les deux peuvent être combinés sans
  doublons. La liste explicite n'est pas tronquée par `--profiles`.
- Sans username, `--conversation-selection random` (défaut) sélectionne des
  profils existants avec un tirage **déterministe** par `--seed`. `ordered`
  conserve le tri alphabétique. Sans opt-in, le vivier reste `world_*`.
- `--conversation-max-participants` vaut 8 par défaut (1 à 30).
  Ce sont des **autres personnes éligibles** et non des interlocuteurs
  fabriqués. Les profils ne répondent jamais à leurs propres Points comme
  faux correspondants ; des interlocuteurs distincts sont choisis selon le
  contexte et la graine.
- Les contextes sont répartis entre les acteurs avant la limite `--count`;
  les Spaces et Groups admissibles sont favorisés. Une Conversation avec un
  seul profil reste permise si aucune autre personne n'a le droit d'y accéder.
  Le nombre de participants réel dépend des membres des Espaces, Groupes,
  participants de l'Activity et autres relations effectivement présentes.
- Les Conversations et Points gardent leurs références d'idempotence.
  Relancer avec une autre graine varie la sélection ou les répondants
  admissibles, sans créer des copies de chaque Conversation existante.
- Les modifications s'appliquent à la SQLite configurée seulement via
  `generate`, jamais via `plan`. Aucune sauvegarde implicite.
