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

**Dossiers/Projets :** chaque porteur conserve son propre Dossier/Project; les Journey liees doivent etre accessibles au porteur. Ce n'est pas un task manager artificiel.

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
