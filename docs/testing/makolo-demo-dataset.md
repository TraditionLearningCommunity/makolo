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
