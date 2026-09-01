# Makolo Presentation System (MPS)

## Statut et vision

MPS est une capacité transversale de Makolo Mature Base. Il transforme les données canoniques de Makolo en représentations sûres, partageables et imprimables. **Makolo possède les faits, les droits et les décisions. MPS possède leur représentation.** Event reste une verticale et Activity reste le noyau.

## Concepts

- **Template** : structure déclarative. Il ne possède aucune donnée métier.
- **Theme** : grammaire visuelle contrôlée (tokens, typographie approuvée, densité, bordures, mouvement).
- **Presentation** : binding d'une Activity/Occurrence et d'un purpose vers une version de Template et une version de Theme, avec uniquement du contenu éditorial autorisé.

Purposes v1 : `PUBLIC_PAGE`, `INVITATION`, `ACCESS_PASS`, `CONFIRMATION`, `PROGRAM`, `BADGE`.
Surfaces v1 : `WEB` et `PRINT`. Le PDF est obtenu par l'impression navigateur ; M3 n'ajoute pas de renderer PDF serveur.

## Modèles et versioning

`PresentationTemplate` et `PresentationTheme` portent provenance (`MAKOLO`, `USER`, `SPACE`), ownership explicite et visibilité. Les versions sont séparées et une version publiée est immuable pour son contenu. `ActivityPresentation` pinne explicitement `template_version` et `theme_version`; aucun upgrade silencieux n'est autorisé. Une Occurrence configurée doit appartenir à l'Activity.

Les migrations M3 sont additives : aucune donnée Activity, Access, Journey, Commerce, Payment, Place, Form ou Resource n'est déplacée ou backfillée.

## PresentationContext

Un template ne reçoit jamais d'objet ORM. Les builders produisent une projection immuable et whitelistée : activité, occurrence, organisateur, recipient autorisé, résumé Access, éditorial et actions. Credentials, payloads signés, permissions, Mandates, sessions, cookies, provider metadata, réponses Form et données privées non nécessaires n'entrent pas dans la registry des bindings.

La résolution de binding passe uniquement par `ALLOWED_BINDINGS`; aucune traversée arbitraire d'attribut Python n'existe.

## Manifest v1 et composants

Le manifest est JSON déclaratif, versionné par `schema_version=1`. Publication et rendu valident : purposes, surfaces, composants, props, bindings, profondeur et nombre de composants. HTML, JavaScript et CSS utilisateur sont interdits. Les URLs à schémas dangereux sont rejetées.

Registry v1 : Page, Section, Stack, Grid, Hero, Image, MakoloMark, OrganizerMark, Heading, Subheading, Text, OccurrenceDetails, DateTime, Place, Organizer, CallToAction, AccessSummary, QRCode, Divider, Footer.

Chaque composant possède un contrat fermé de props et de children. Les sorties texte sont échappées.

## Tokens, fonts et motion

Les thèmes ne stockent que des tokens contrôlés. Les couleurs sont validées, les familles de police sont limitées à des choix distribuables/système, et les presets de mouvement sont `none`, `fade`, `reveal`, `soft_scale`, `stagger`. PRINT reste statique. Aucun chargement de font ou d'asset tiers arbitraire n'est permis par un manifest.

## Access et QR

Access reste canonique :

`Access -> AccessCredential -> render_access_credential() -> core.branding -> image QR`.

Le composant `QRCode` ne reçoit jamais le credential. Le builder Access produit seulement une image data-URI rendue côté serveur. Le credential brut, son `public_id`, le payload signé et les secrets associés ne sont jamais écrits dans le HTML du renderer MPS.

Une suspension ou une erreur de décoration ne doit jamais détruire le droit : le resolver utilise une version saine lorsqu'elle est disponible, sinon `Makolo Essential`. Essential existe aussi en définition code-controlled afin qu'un catalogue DB incomplet ne bloque jamais une Activity ou un Access.

## Permissions

La configuration d'une Presentation réutilise l'autorité canonique `activity.manage`, y compris son héritage documenté depuis un Espace. Une simple membership ne suffit jamais. Les bibliothèques Espace et la modération globale seront durcies en M3C sans accorder implicitement de pouvoir aux Spaces.

## Studio et bibliothèque

M3B ajoute les parcours Galerie -> Template -> Theme -> éditorial -> previews Téléphone/Desktop/Impression -> publication et les surfaces générées. M3C ajoute bibliothèques User/Espace, defaults par purpose, duplication et workflow Community modéré. Toutes ces surfaces consomment le même renderer sûr.

## Print

PRINT réutilise le document HTML et les composants MPS. Les styles d'impression doivent gérer A4/A5/A6 et les formats badge/card pertinents, supprimer le mouvement et préserver lisibilité et QR. Aucun prépresse professionnel, CMJN, ICC ou bleed avancé n'est promis en M3.

## Sécurité

Principes : whitelist de contexte, bindings fermés, échappement par défaut, aucun code utilisateur, aucune iframe distante, aucun accès ORM depuis le manifest, aucun credential dans logs/cache keys/debug metadata, assets servis par Makolo, permissions serveur pour preview/configuration/publication. Les surfaces personnalisées Access/recipient ne sont jamais destinées à un cache public partagé.

## Tests et extensions

M3 couvre modèles/versioning, validation manifest/theme, XSS, permissions, fallback, Access/QR/scanner, responsive/print et plusieurs verticales. Les registries pourront plus tard accepter de nouveaux purposes/context contributors/composants approuvés sans ouvrir l'accès ORM ni du HTML/CSS/JS arbitraire.
