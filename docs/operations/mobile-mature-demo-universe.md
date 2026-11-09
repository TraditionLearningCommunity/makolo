# Mobile Mature Demo Universe

## But

Fournir au client Flutter un univers serveur riche, déterministe et réexécutable, construit à partir des modèles Django canoniques.

Le corpus n'est pas une fixture Flutter. Le flux attendu est :

```text
modèles Django
→ projections/API existantes
→ HTTP
→ sync mobile
→ stockage local
→ sélecteurs Flutter
```

Aucun score Molongo, ranking complexe ou moteur de pertinence n'est requis pour ce chantier.

## Persona principal

Le compte de référence est un persona fictif :

- **Alain Kabeya**
- base principale : **Lubumbashi**
- vie multi-ville : Lubumbashi, Kolwezi, Kinshasa
- projets internationaux : notamment Montréal / Canada
- activité professionnelle, apprentissage, déplacements, services, financements et obtentions

Identifiant de seed : `beta.alain@makolo.test`.

Le mot de passe n'est jamais versionné. Il est fourni à la commande de seed par l'environnement d'exécution.

## Volume

Le corpus principal contient **150 réalités**, réparties à parts égales :

| Verticale | Volume |
| --- | ---: |
| Event | 25 |
| Transport | 25 |
| Service | 25 |
| Opportunity | 25 |
| Funding | 25 |
| Obtention | 25 |

Répartition temporelle de la matrice :

- 2025 : passé riche ;
- 2026 : passé récent, présent autour de `--as-of`, engagements actifs et attentes ;
- 2027 : futur déjà connu ou projeté.

Les Activity/Occurrence associées, les Journeys et les Resources font croître le volume réel de la base au-delà de ces 150 lignes de matrice.

## Médias et Resources

Les Activity de l'univers mature utilisent de vraies `ActivityResource`.

Le seed couvre notamment :

- images PNG ;
- galeries ;
- PDF structurés ;
- XLSX ;
- DOCX ;
- CSV ;
- WAV ;
- MP4 ;
- URLs publiques.

Les documents privés d'Alain sont synthétiques mais contiennent des informations crédibles : titre, lieu, année, situation et contexte utile.

Les contenus publics peuvent être référencés sans recopier leurs octets. Le seed utilise notamment des références vers :

- Town-Event ;
- Air Fast Congo et son magazine de bord ;
- Catalogue des Services Publics de la RDC ;
- IRCC ;
- EduCanada ;
- Banque africaine de développement ;
- PNUD Careers.

Une URL publique de référence ne signifie jamais qu'une relation personnelle fictive d'Alain est un fait public.

## Projets, Dossiers et démarches — Moi > Mes démarches

Le même profil fictif comprend désormais un ensemble d'Objectives suffisamment
dense pour examiner les **trois vues** du client : Cartes, Liste et Explorateur.

- **6 Projets** avec des horizons et états différents ;
- **28 Dossiers**, dont **24 rattachés** à des Projets et **4 indépendants** ;
- des Dossiers sans Journey, d'autres avec 2 à 4 Journeys canoniques déjà
  présentes dans le corpus Mobile Mature ;
- des **prérequis entre Journeys** du même Dossier via
  `DossierJourneyDependency`, sans reproduire les tâches dans Objectives ;
- des états draft, active, completed, cancelled et archived, exercés par les
  services de transition canoniques.

Les Project et Dossier sont personnels au persona synthétique. Les liens sont
créés par les services de domaine ; les identités Objectif du seed sont stables
et la réexécution ne multiplie pas les entités ou les liens. Aucun score
Mayele/Molongo ni règle de présentation client n'est ajouté.

La projection qui alimente cet écran est
`GET /api/v1/objectives/organizer/?limit=50&offset=0`. Le client conserve
ses pages acquises localement. Pour explorer le volume après seeding, ouvrir
**Moi → Mes démarches** puis sélectionner Cartes, Liste et Explorateur.

**Attention :** ces éléments sont ajoutés par les commandes **déjà existantes**
`seed_mobile_mature_demo` et `seed_makolo_demo --scale beta`. Ne jamais
lancer un seed sur les données réelles d'un utilisateur : utiliser exclusivement
une base de démonstration ou de test isolée, après vérification de sa cible.

## API mobile

Les surfaces existantes restent propriétaires :

- `GET /api/v1/me/now/`
- `GET /api/v1/me/ongoing/`
- `GET /api/v1/me/`
- `GET /api/v1/objectives/organizer/?limit=50&offset=0`
- `GET /api/v1/objectives/projects/<uuid>/`
- `GET /api/v1/objectives/dossiers/<uuid>/`
- `GET /api/v1/discovery/items/`
- `GET /api/v1/preparation/journeys/<journey>/resources/`

Discovery expose en plus un aperçu borné des Resources publiques associées à chaque Activity/Opportunity. Chaque entrée peut fournir :

```json
{
  "id": "...",
  "title": "...",
  "description": "...",
  "kind": "file | url | text",
  "mime_type": "...",
  "external_url": "...",
  "download_url": "..."
}
```

Le client n'a pas à recalculer la pertinence ni à reconstruire une vérité métier.

## Exécution

Exemple local :

```bash
# Pour le corpus complet de démonstration bêta :
python manage.py seed_makolo_demo --scale beta --as-of 2026-10-03 --demo-password "<password-local>"

# Ou, pour le corpus autonome destiné au client mobile :
# MAKOLO_DEMO_PASSWORD est injecté depuis l'environnement de test isolé.
python manage.py seed_mobile_mature_demo --as-of 2026-10-03

# Si le corpus Mobile Mature existe déjà et qu'on veut seulement ajouter
# Projets et Dossiers, sans toucher aux identifiants de connexion :
python manage.py seed_mobile_objectives_demo --as-of 2026-10-03 --confirm-demo-database
```

Le seed doit rester :

- déterministe pour un même `--as-of` ;
- idempotent ;
- compatible SQLite et PostgreSQL ;
- sans migration spécifique au corpus ;
- sans suppression ou affaiblissement des contrôles métier.

## Validation

Le gate `Beta seed validation` vérifie notamment :

- 25 réalités par verticale ;
- 125 Activity canoniques pour les cinq verticales Activity-backed ;
- 25 Opportunities ;
- 125 Occurrences ;
- un corpus significatif de Resources et fichiers ;
- plusieurs dizaines de Journeys pour Alain ;
- couverture 2025 / 2026 / 2027 ;
- idempotence SQLite et PostgreSQL ;
- réponses 200 de Now, En cours, Découvrir et Moi ;
- présence de Resources téléchargeables ou externes dans les réponses destinées au mobile.

Les marqueurs techniques du seed (`mobile-mature-*`, provenance, identifiants de fixture) restent internes. Les titres, résumés, organismes, Resources et actions visibles sont rédigés comme des données produit normales.
