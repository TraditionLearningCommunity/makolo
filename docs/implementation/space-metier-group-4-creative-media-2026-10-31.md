# Makolo / Métier Space — Groupe 4 : Créations et Productions

**Date :** 2026-10-31.
**Dépôt officiel :** `TraditionLearningCommunity/makolo`.
**PR unique :** #522 (`fix/discover-a-continuation-context-20261014`).
**Base `main` vérifiée en début de lot :** `d0f0ec421c94c255fa4c0acd3509938a70c6322f`.

## Statut et périmètre

Groupe 4 de la composition Métier **N1 serveur et Web**, sur le même moteur des groupes 1–3. Les huit archétypes sont désormais couverts par une grammaire de lecture. Aucune création d'un nouveau `Creation`, `Production`, `Post`, `Feed`, `Story`, `WorkItem`, objet persisté de Presentation, migration ou pouvoir dérivé.

Le travail se conforme à :
- `docs/ux/Makolo_UX_Space_Metier_Creations_Creative_Contrat_Consolide_2026-10-08.md`
- `docs/ux/Makolo_UX_Space_Metier_Productions_Media_Contrat_Consolide_2026-10-08.md`
- `docs/ux/Makolo_Contrat_Metier_Space_Gele_2026-10-06.md`
- modèles, sélecteurs et autorisation présents dans `activities`, `presentations`, `organizations`, `authorization`.

## 1. Métier Creative : Créations

- Question humaine : « Quelles œuvres créons-nous, que faut-il préparer et quelles présentations réelles arrivent ? »
- Groupes dérivés `creation_work` (préparation, Occurrences en cours, blocages propriétaires), `presentations` (Occurrences futures), `creations` (Activities durables), `related` (domaines réellement présents et autorisés), `history`.
- La section « Créations durables » n'est **pas** un modèle portfolio parallèle. Les offres Commerce et demandes Services éventuelles ne deviennent pas la nature première d'une œuvre.
- La prochaine présentation d'une création publiée provient de la **première Occurrence future réellement autorisée**, sans nouveau statut « en création », pourcentage ou état d'urgence construit localement.
- Un Space calme conserve les créations durables, sans inventer de lancement, de Progress ni d'Event.

## 2. Métier Media : Productions

- Question humaine : « Quelles productions réalisons-nous, quelles éditions préparons-nous et qu’est-ce qui doit être diffusé ou présenté ? »
- Groupes dérivés `production_work`, `realizations`, `productions`, `related`, `history`. Les chapitres absents de la réalité autorisée ne sont pas fabriqués.
- `Activity` donne l'identité durable de Production et `Occurrence` une édition ou réalisation précise. Une édition n'est pas la production entière.
- « Prochaine édition » vient de l'Occurrence propriétaire et non d'un planning de diffusion inventé. Aucun feed, CMS, view counter, audimat, score de popularité ou automation de publication n'est créé.
- Les ressources, offres ou services associés conservent leur propre propriétaire et les contrôles d'accès du domaine concerné.

## 3. Media contextualisée, publiée et sûre

Nouveau helper `organizations/space_work_media.py`.

- Les vignettes sont facultatives : seuls les usages `PresentationMediaUse` **explicitement publiés pour reconnaître** une Activity/Occurrence peuvent être proposés. Une `ActivityResource`, un `PresentationAsset` nu ou une image de démonstration ne constituent pas un droit de visibilité.
- La composition exige exactement les préconditions du transport média public : Space public/searchable/actif/non suspendu, Activity publique et publiée appartenant au Space, et éligibilité du profil via `eligible_activity_ids_for_profile`. Si le Space est privé, **aucun binding public n'est rendu**, même pour un propriétaire autorisé dans l'interface de travail.
- Le sélecteur canonique `public_presentation_media_for_activities` fournit les usages `PUBLISHED` et filtre sur `purpose=recognize`. Le helper n'expose qu'un image JPEG/PNG ayant la bonne liaison. Une image liée à une Occurrence n'est pas montrée comme image de l'Activity parent ou d'une Occurrence sœur.
- La projection renvoie `resource_ref`, propriétaire, texte alternatif, purpose, MIME et URL `presentations:published-media-file`. Elle **n'expose jamais URL de stockage, nom de fichier, pièce de preuve, dossier local, credentials ni données de personne**. Le endpoint de livraison refait sa propre vérification à chaque appel ; une association retirée cesse d'être visible et livrable.
- Web affiche un visuel de reconnaissance seulement si un tel binding est fourni, avec vrai `alt`, chargement différé et sans card/feed/media décorative. Sans binding, la ligne métier reste textuelle.
- Le N1 reste lisible même lorsque le fichier n'est pas accessible hors connexion ; le chargement multimédia et les politiques de cache natif appartiennent à la fermeture Flutter.

## 4. Code livré

- `organizations/space_work_composition.py` : grammaires, questions et états calmes pour Creative et Media.
- `organizations/space_work_media.py` : projection de reconnaissance publiée et strictement autorisée.
- `organizations/api/space_work_projection.py` : prochaine Occurrence des deux archétypes, binding propriétaire, libellés contextuels.
- `organizations/space_work_web.py` : « Voir la création » et « Voir la production » avec handoff Activity existant.
- `templates/organizations/space/work.html` : rendu visuel propriétaire uniquement en présence d'une autorisation.
- `organizations/test_space_work_group4.py` : tests de groupes, dates, publication/retrait, Scope, IDOR, ressource non promue, binding lié à la bonne Occurrence et Web.
- Ajustement de trois tests hérités des groupes 1–3 pour tester l'**isolation des huit grammaires** au lieu de supposer que les archétypes non encore travaillés n'ont pas `business_world`.

## 5. Frontières de sécurité et non-régression

- `Viewer=Profile`, `Actor=Space`. Ni Membership ni type d'archétype ne confèrent de droit.
- L'autorité et le filtre `responsibility` de `build_space_work_projection` restent propriétaires ; les bindings sont attachés **après** filtrage des lignes.
- Aucune donnée personnelle, privée ou média restreinte n'est ajoutée à la liste.
- Les quatre premiers groupes utilisent le même moteur ; aucun autre domaine n'est remplacé.
- Le travail ne touche pas les états financiers, Capacity, Live, Requirements ou Journeys.

## 6. Validation ciblée à exécuter localement

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test \
  organizations.test_space_work_group4 \
  organizations.test_space_work_group3 \
  organizations.test_space_work_group2 \
  organizations.test_zs3_space_work_api \
  organizations.test_ws3_space_work_web \
  presentations.test_media_use
```

**Aucune CI ni test Django/Flutter n'a été exécuté dans la session distante.** Les nouveaux tests doivent être validés localement et les causes racines des éventuels échecs corrigées dans #522. Pas de merge tant que les gates d'intégration n'ont pas été vérifiées.

## 7. Suite du programme Métier

Les **huit compositions N1 serveur/Web** sont en place sous réserve des validations ci-dessus. La phase suivante n'est pas de produire neuf architectures supplémentaires : elle doit assembler le **contrat commun Métier et les profondeurs N2/N3**, vérifier chaque destination réelle et les Mandates, compléter le Web mature et Flutter local-first (identité Space, lecture hors-ligne bornée, invalidation et révocation, réponse aux actions, accessibilité, qualité visuelle, test de reprise).

Garder **#522 comme seule branche de travail**, revalider son HEAD et les modifications concurrentes avant la phase transversale.
