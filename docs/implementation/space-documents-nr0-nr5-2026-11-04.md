# Nous — Documents de l’Espace · Fermeture NR0 → NR5

**Référence de réalisation — 4 novembre 2026 · PR #522 · à valider sur environnement d’exécution.**

## Promesse produit

Un Espace conserve ses documents institutionnels, les retrouve quand ils comptent et les mobilise dans une démarche. La surface **Nous** rend cette capacité visible sans devenir un gestionnaire de tâches ni absorber les ressources personnelles des membres.

Les interfaces utilisent un langage connu : **Documents · Ajouter · Modifier · Télécharger · Partager · Utiliser · Archiver**. Icônes familières, libellés accessibles, microcopy parcimonieuse. Même grammaire de Makolo que **Moi**, avec une identité d'acteur collectif, non un Profil personnel.

## NR0 — Propriété canonique et limites

**Choix réalisé :** `space_assets` possède les fichiers et métadonnées institutionnels durables, dans le registre des acteurs collectifs. Ce n'est pas un second `PersonalAsset`. Réemploi des règles et services de fichiers privés du noyau Journey, sans posséder ses données métier.

| Owner | Ce qu'il possède | Ce qu'il ne cède pas |
|---|---|---|
| Space Assets | Document durable Space, version immuable, archive, observation de l'utilisation | Autorité, Requirement, Trust, Passport |
| Sharing | Partage explicite à un destinataire, durée, révocation | Propriété du fichier ou droits des membres |
| Journey / Requirements | Artifact de démarche, décisions d'acceptation et de satisfaction | Bibliothèque institutionnelle |
| Trust | Preuve, Credential, vérification | Statut juridique automatiquement conclu depuis un PDF |
| Presentation | Modèles, thèmes, médias | Bibliothèque privée |
| Nous | Aperçu borné et navigation | Stockage de document et autorité métier |

Aucune Membership n'accorde un droit. Aucune mise en relation ne transfère la propriété d'un document personnel, d'une Activity ou d'une pièce Journey.

## NR1 — Cycle documentaire

Modèles : `SpaceDocument`, `SpaceDocumentVersion`, `SpaceDocumentUse` (migrations additives `space_assets/0001_initial.py`). Les versions sont immuables, la nouvelle version conserve les précédentes, et l'archivage remplace la suppression silencieuse. Fichier privé hors MEDIA_ROOT public, validation de taille, MIME et signature du contenu, aucun chemin de stockage exposé dans les projections.

La provenance conserve l'acteur humain. Les permissions sont revalidées sur chaque action et les remplacements sont sérialisés sur le document pour éviter les versions concurrentes ambiguës.

## NR2 — Confidentialité et partage

Deux expositions institutionnelles au départ :
- **Confidentiel** (par défaut) : gestionnaires Space avec `SPACE_MANAGE` direct.
- **Équipe autorisée** : détenteurs de `SPACE_VIEW` direct, ou gestionnaires.

Ce n'est **pas** une permission acquise en rejoignant un groupe ou une équipe. Les Mandates effectifs déterminent l'autorité. La distinction lecture/gestion peut être spécialisée ultérieurement si des besoins documentaires autonomes le démontrent.

Le partage direct réutilise **Sharing** : destinataire Makolo identifié, version immuable, durée 1/7/30 jours, possibilité de révocation et archivage invalidant la livraison ; aucune URL de fichier public. Le grant ne change pas la visibilité globale de l'Espace et ne donne aucun autre droit.

API privée `/api/v1/organizations/workspaces/<slug>/documents/` : liste, ajout, fiche, édition, versions, téléchargement, réutilisation, partage et révocation. Échecs d'autorisation rendus introuvables pour les autres acteurs ; `private, no-store`, `nosniff`, `no-referrer` sur les fichiers.

## NR3 — Mobiliser une ressource pour agir

L'action **Utiliser** propose seulement des démarches du même Espace auxquelles la personne peut réellement contribuer. Le service revalide Space, Mandate Activity, JourneyAssignment, statut non terminal, expiration et propriété du fichier. La version choisie est copiée explicitement en `JourneyArtifact` privé, avec une trace `SpaceDocumentUse`, sans alias du fichier d'origine.

**Un document présent ≠ accessible ≠ admissible ≠ Requirement satisfait.** Aucune satisfaction automatique, aucune mutation implicite de Proof/Trust.

## NR4 — Présentation Web et mobile

| Niveau | Expérience | État |
|---|---|---|
| N1 · Nous | Aperçu des documents institutionnels avec Passport/Presentation ; uniquement faits visibles | Implémenté |
| N2 · Nos ressources | Familles existantes + accès visible à **Documents** | Implémenté |
| N2 · Documents | Recherche, collection paginée, ajout autorisé, états vides | Web + Flutter |
| N3 · Document | Version(s), télécharger, modifier, partager, révoquer, archiver, utiliser | Web + Flutter |

Interfaces : **palette Makolo**, fonds clairs, territoires reconnaissables, carte Passeport marquée, densité maîtrisée, actions à icônes standards avec label/tooltip d'accessibilité. Pas de texte de tutoriel sur des actions familières.

Mobile : contexte Space actif vérifié au chargement et au retour d'appel ; une réponse tardive d'un autre Space ne repeint pas la fiche. Aucun fichier document durablement conservé dans le cache de la projection ; export uniquement sur action explicite. Android : Downloads ; autres plateformes : feuille de partage OS. Nettoyage de fichier temporaire dès la fin.

## NR5 — Contrôles et non-régression

Tests ajoutés dans `space_assets/tests.py` :
- document appartient réellement au Space et non au déposant individuel ;
- création, historique, nouvelle version immuable, archivage ;
- fichier falsifié, taille vide, MIME/signature incompatibles ;
- lecture permise vs gestion interdite ; membre/Activity-only/Space étranger refusés ;
- lien de partage privé au bon destinataire, durée, expiration, révocation, archivage ;
- consultation/téléchargement privés ;
- Journey étrangère ou terminée interdite ;
- Nous n'expose pas de secret, chemin de fichier ni contenu binaire.

Scénarios à exécuter sur les environnements canoniques :
```
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test space_assets organizations.test_space_us_resources organizations.test_zs4_space_projections organizations.test_ws4_space_web sharing
cd mobile && dart format lib/features/space/space_documents_screen.dart lib/features/space/space_document_detail_screen.dart lib/features/space/space_us_resources_screen.dart
cd mobile && flutter analyze && flutter test test/space_us_surface_test.dart
```

Compléter par validation Android et iOS réelle : sélecteurs et boutons à grande police, Web Compact/Medium/Wide, flux annuler/reprise, mandat révoqué, deux Spaces, retour depuis une fiche, permissions du système, fichiers PDF/Office/image et partages expirés. Aucune CI ni exécution locale verte n'est revendiquée dans cette note.

### Déploiement/migration

Migrations **additives**, pas de backfill ni de modification des PersonalAssets historiques. Avant mise en ligne bêta : sauvegarde BDD, `migrate --plan`, environnement privé de stockage disponible, rollback applicatif planifié et stockage privé à conserver (ne pas détruire des fichiers historiques). Mettre à jour les workers/app installées avec migration avant d'ouvrir les nouveaux parcours.

### Limitations assumées

- `Nos ressources` assemble aussi les familles Sharing/Presentation, mais ne copie pas tous les documents de Journey, les Proofs ni les Assets personnels.
- Le partage de document est **direct à un compte Makolo**, sans lien public par défaut.
- Aucun score de fiabilité, statut juridique ou attestation officielle n'est déduit d'un dépôt.
- La réutilisation prépare l'action, elle ne décide pas qu'un Requirement est satisfait.
- Tests, migrations et QA visuelle doivent être exécutés sur runtime réel pour déclarer la fermeture technique **validée**.

## Références

- `docs/ux/Makolo_Nous_Space_Contrat_Enrichi_N1_N3_2026-11-03.md`
- `docs/ux/Makolo_Contrat_Moi_et_Nous_Gele_2026-10-06.md`
- `docs/architecture/makolo-domain-blueprint.md`
- `docs/architecture/personal-action-capital.md`
- `docs/architecture/mobile-files-media-transfer-kernel.md`
- `docs/implementation/space-nous-checkpoints-2026-10-31.md`
