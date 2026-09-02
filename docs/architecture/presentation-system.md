# Makolo Presentation System (MPS)

## Vision

Le **Makolo Presentation System** est une capacité native de Makolo Mature Base. Il transforme les données canoniques déjà fiables en représentations visuelles professionnelles pour le web et l'impression.

> **Makolo possède les faits, les droits et les décisions. MPS possède leur représentation.**

MPS est transversal. Event reste une verticale et Activity reste le noyau. Aucun modèle Presentation n'est placé dans `events` et aucune vérité métier canonique n'est recopiée.

## Trois concepts distincts

- **PresentationTemplate** : structure déclarative et versionnée.
- **PresentationTheme** : grammaire visuelle versionnée, limitée à des tokens contrôlés.
- **ActivityPresentation** : binding d'une Activity, d'une Occurrence optionnelle et d'un `purpose` vers une version de Template et une version de Theme, avec uniquement du contenu éditorial autorisé.

Une version publiée est immuable. Une Presentation reste pinnée sur les versions choisies. Un upgrade est une action explicite et revalide l'autorité, l'accès au catalogue, le purpose et les contrats de sécurité.

## Purposes et surfaces

Purposes v1 :

- `PUBLIC_PAGE`
- `INVITATION`
- `ACCESS_PASS`
- `CONFIRMATION`
- `PROGRAM`
- `BADGE`

Surfaces v1 : `WEB` et `PRINT`. PRINT repose sur HTML/CSS, `@media print` et l'impression navigateur. M3 n'introduit aucun renderer PDF serveur.

## Modèles et migrations

M3 ajoute uniquement des tables MPS : Templates et versions, Themes et versions, bindings Activity, assets Presentation, defaults Espace et métadonnées de modération communautaire. Les migrations sont additives. Il n'existe aucun backfill massif des anciennes Activities.

Les anciennes Activities restent valides : en l'absence de configuration, la résolution tombe sur **Makolo Essential**.

## Résolution et fallback

Ordre de résolution :

1. override Occurrence + purpose ;
2. override Activity + purpose ;
3. default Espace + purpose ;
4. `Makolo Essential` code-controlled.

`RETIRED` signifie indisponible pour une nouvelle sélection mais une version historique pinnée continue à être rendue si elle reste sûre. `SUSPENDED` est une décision de sécurité/modération : elle l'emporte immédiatement sur le pinning. Le resolver tente une version publiée antérieure saine, puis tombe sur Essential.

La décoration ne bloque donc jamais le droit Access ni l'accès à une Activity.

## PresentationContext

Un Template ne reçoit jamais un modèle Django, un QuerySet ou une possibilité de traverser arbitrairement des attributs Python. Les context builders produisent des projections immuables par liste blanche :

- Activity : titre, description, kind ;
- Occurrence : début, fin, Place public ;
- Organizer : nom public et logo public autorisé ;
- Recipient : nom affichable lorsque la surface et l'autorité l'autorisent ;
- Access : type contextualisé, statut et bénéficiaire autorisé ;
- Editorial : uniquement les champs du purpose ;
- Actions : destinations générées côté Makolo.

Credentials, payloads signés, tokens, cookies, sessions, permissions, Mandates, metadata provider/Payment/Journey, réponses Form et données privées non nécessaires sont exclus.

## Manifest v1

Le Template stocke un manifest JSON déclaratif `schema_version=1`. Le validator borne :

- purposes et surfaces ;
- composants et props ;
- bindings ;
- profondeur maximale ;
- nombre maximal de composants ;
- URLs déclaratives ;
- absence de raw HTML, JavaScript et CSS arbitraire.

Les URLs statiques déclaratives doivent être des chemins Makolo relatifs. Les CTA dynamiques proviennent du PresentationContext. Il n'existe ni `eval`, ni code Python utilisateur, ni template Django utilisateur.

## Component registry

La bibliothèque approuvée v1 comprend notamment : `Page`, `Section`, `Stack`, `Grid`, `Hero`, `Image`, `MakoloMark`, `OrganizerMark`, `Heading`, `Subheading`, `Text`, `OccurrenceDetails`, `DateTime`, `Place`, `Organizer`, `CallToAction`, `AccessSummary`, `QRCode`, `Divider` et `Footer`.

Chaque composant a un contrat fermé de props et d'enfants. Le texte est échappé par défaut. Les headings et alt contracts déterministes participent au gate de publication communautaire.

## Binding registry

Les bindings sont exacts et explicites, par exemple :

- `activity.display_title`
- `activity.description`
- `occurrence.starts_at`
- `occurrence.place`
- `organizer.display_name`
- `editorial.invitation_message`
- `access.display_type`
- `access.display_status`
- `actions.primary_url`

Une chaîne comme `activity.owner.user.password` n'est pas interprétée : elle est rejetée.

## Themes, tokens, fonts et motion

Les Themes utilisent des registres contrôlés pour couleurs, font family, font scale, spacing, radius, border style, hero ratio, alignment, density et motion. Les couleurs sont des hexadécimaux validés. Les polices sont limitées aux familles intégrées/système approuvées ; aucun chargement de Google Fonts, CDN ou domaine tiers n'est possible via un Theme.

Motion v1 : `none`, `fade`, `reveal`, `soft_scale`, `stagger`. Le rendu respecte `prefers-reduced-motion` et PRINT désactive toujours les mouvements.

## Assets

`PresentationAsset` est séparé d'ActivityResource : Resource reste une information/document de préparation, alors qu'un PresentationAsset est un asset graphique du rendu. L'upload MPS réutilise la primitive canonique de validation de fichiers existante, puis limite M3 aux images JPEG/PNG validées et servies par le stockage Makolo. Une URL externe forgée dans `hero_image` n'est pas acceptée comme asset.

## Access et QR

Access reste propriétaire du droit et du credential :

`Access -> AccessCredential -> render_access_credential() -> core.branding -> image QR MPS`

Le composant `QRCode` ne reçoit jamais le credential ou le payload signé. Le builder transforme le credential en image data-URI côté serveur et n'expose que ce résultat visuel au renderer. Le credential brut, son payload et ses métadonnées ne sont pas placés dans le HTML, un cache key ou une metadata de debug MPS.

La représentation participant utilise le vocabulaire canonique de la verticale (`Billet`, `Confirmation`, etc.) au lieu d'imposer le mot “Ticket”. Le scanner continue à valider le même credential canonique ; MPS ne change pas la sémantique du scan.

## Studio

La console Activity expose **Présentation**. Le Studio suit le parcours :

1. usage ;
2. galerie ;
3. Template ;
4. Theme et éditorial ;
5. aperçu Téléphone/Desktop/Impression ;
6. Enregistrer ou Utiliser ce modèle.

Les previews Activity utilisent les vraies données de l'Activity et le même renderer que la surface finale. Le navigateur n'accorde aucune autorité : `activity.manage` est vérifié côté serveur pour le Studio, le preview et la publication.

Le catalogue initial contient huit Templates : **Makolo Essential, Formal, Professional, Celebration, Stage, Heritage, Mono, Journey**. Les Themes initiaux sont : **Makolo Violet, Makolo Ink, Ivory, Midnight, Warm, Corporate Blue, Mono**.

## Generated surfaces

M3 fournit un moteur commun pour `PUBLIC_PAGE`, `INVITATION`, `ACCESS_PASS`, `CONFIRMATION`, `PROGRAM` et `BADGE`. Une Activity publique peut utiliser sa Presentation `PUBLIC_PAGE`; une Activity sans configuration reste affichable via Essential. L'Access participant peut ouvrir une représentation MPS WEB ou PRINT sans modifier le droit sous-jacent.

Les actions de réservation, inscription, commerce, paiement et accès restent canoniques dans Journey, Capacity, Commerce, Payment et Access.

## Bibliothèques et defaults Espace

Les surfaces de bibliothèque distinguent :

- Modèles Makolo ;
- Mes modèles ;
- Modèles de mon Espace ;
- Communauté.

Un modèle public/Makolo est dupliqué avant personnalisation : le global n'est jamais écrasé. La duplication conserve la provenance, crée son propre ownership et redémarre sur une version DRAFT.

Un Espace peut définir un couple Template/Theme par purpose. Cette opération exige l'autorité canonique `space.manage`; une simple membership ne suffit pas. Un default ne peut pas référencer une ressource privée appartenant à un autre propriétaire.

## Community

Le workflow M3 est : DRAFT -> preview -> SUBMITTED -> review -> PUBLISHED, avec RETIRED et SUSPENDED. Les étapes de preview/review sont des surfaces/services plutôt que des états supplémentaires inutiles.

La publication globale est réservée à l'autorité plateforme/staff. Avant publication, Makolo revalide le manifest et les contrôles d'accessibilité déterministes. Une contribution communautaire publiée passe exactement par le même safe renderer que les Templates Makolo : aucun chemin “trusted HTML” n'existe.

Les métadonnées de soumission/revue conservent auteur, dates, reviewer et note de décision sans inventer de marketplace, licence commerciale ou partage de revenus.

## Permissions

- gestion d'une Presentation Activity : `activity.manage` ;
- bibliothèque/defaults Espace : `space.manage` ;
- lecture bibliothèque Espace : `space.view` ;
- publication/suspension globale : staff ou autorité plateforme canonique.

L'ownership et la visibilité du Template/Theme sont vérifiés côté serveur lors de la sélection, duplication, default et upgrade. Les previews par ID respectent les mêmes frontières et ne permettent pas l'accès à un modèle privé d'un autre propriétaire.

## Sécurité frontend et CSP

MPS n'ajoute aucun JS utilisateur, iframe distante, inline JS arbitraire ou asset exécutable. Les styles viennent du bundle MPS et de variables issues de tokens validés. L'échappement HTML reste la règle. Les surfaces personnalisées contenant bénéficiaire/Access/QR ne sont pas destinées à un cache public partagé.

## Responsive, print et accessibilité

Le CSS MPS est responsive et prévoit un mode étroit, desktop et print. Le QR évite les coupures de page, les CTA interactifs sont masqués à l'impression, et les animations sont désactivées dans PRINT et avec reduced motion. Le rendu utilise HTML sémantique, hiérarchie de titres, textes alternatifs contractuels, focus hérité du système et des statuts textuels plutôt que couleur seule.

M3 vise l'impression navigateur A4 comme base et garde les primitives nécessaires aux formats A5/A6/badge/card. Il ne promet pas CMJN, ICC, bleed ou prépresse professionnel.

## Multi-verticales

Le moteur commun ne contient aucun `if event`, `if transport` ou `if service` pour les données communes. Les tests rendent le même Template avec une Activity générique, une Activity portant la verticale Event et une Activity portant la verticale Transport. Les différences de vocabulaire restent dans les projections/presenters contrôlés.

## Tests et release gate

La couverture M3 comprend : modèles/versioning, manifest, bindings, XSS, tokens, permissions, IDOR preview, fallback, RETIRED/SUSPENDED, defaults, duplication, upgrade, Community, assets, Access/QR/scanner, responsive/print, multi-verticales et scénarios Playwright Studio/participant.

Avant release : `makemigrations --check --dry-run`, `migrate --plan`, checks Django/PostgreSQL/frontend/CSP/security/Playwright et Beta seed lorsqu'ils sont déclenchés. Le gate transversal réel est la CI de la PR finale vers `main`.

## Exploitation

En incident de rendu : vérifier d'abord l'état de la version pinnée. Une version manifestement dangereuse doit être `SUSPENDED`, jamais simplement `RETIRED`; le resolver bascule alors immédiatement vers une version saine antérieure ou Makolo Essential. Ne pas modifier Access/credential pour résoudre un incident graphique. Un asset invalide doit être retiré/remplacé depuis MPS, pas contourné par une URL tierce.

## Extensions futures

Les registries permettent plus tard à une extension approuvée de contribuer un purpose, un context contributor ou un composant contrôlé, sans accès ORM ni raw HTML/CSS/JS. Marketplace, monétisation, white-label, mini-Canva, IA de design, PDF serveur, batch PDF et application mobile native restent hors M3.
