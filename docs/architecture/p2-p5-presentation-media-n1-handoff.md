# Makolo — P2–P5 : médias de représentation N1 (branche #522)

## Principe

Les données persistées et leurs propriétaires font autorité. Un seed ne fabrique pas une image dans l'API. Une possibilité sans média est valide. Le fichier (`PresentationAsset`), l'association (`PresentationMediaUse`), la publication, la ressource de préparation (`ActivityResource`) et le rendu MPS (`ActivityPresentation`) restent des responsabilités distinctes.

## P2 : usage propriétaire

- `PresentationMediaUse` est une relation Activity/Occurrence vers PresentationAsset avec purpose, ordre, état et texte alternatif.
- Services `associate_presentation_media`, `publish_presentation_media`, `retire_presentation_media`, `replace_presentation_media`, `reorder_presentation_media`.
- `ACTIVITY_MANAGE` ne vaut pas permission implicite sur un asset tiers.
- Le Studio de l'Activity dispose d'un formulaire séparé pour importer et publier une image JPEG/PNG de reconnaissance, sans Template, et la retirer.
- L'Event `cover_image` existant est conservé comme source métier spécialisée.

## P3 : projection et livraison

- `public_presentation_media_for_activities` retourne des usages publiés sur les Activities publiées et publiques, sans URL directe brute.
- `project_rows` compose une collection bornée pour la page admise, les restrictions de Groupe et la portée Occurrence, puis projette `media_bindings[]` (purpose RECOGNIZE) et `representation.image_url` depuis la même relation.
- La couverture de spécialité est conservée comme repli ; les Resources ne sont jamais promues automatiquement en couvertures.
- `presentations:published-media-file` retourne le contenu par `FileResponse` après vérification au moment de l'accès : état publié, propriétaire du sujet public/actif, Groupe admissible, ownership et disponibilité physique. Réponse non mise en cache, 404 sinon.
- L'API et le détail empruntent le même `project_rows`.

## P4 : N1 mobile

- `DiscoveryPossibilityUnit` consomme déjà `representation.image_url` et `media_bindings` ; `baseUri` permet de résoudre les chemins relatifs sous l'origine API.
- La profondeur N2 résout désormais elle aussi l'URL relative sans créer un deuxième inventaire de médias.
- Les médias manquants n'ont pas d'image de remplissage synthétique.
- Pas de nouvelle capacité de galerie/vidéo/audio dans ce lot ; N1 est le premier périmètre.

## P5 : validation et déploiement de test

Tests ciblés : `python manage.py test presentations.test_media_use`, `python manage.py check`, `python manage.py makemigrations --check --dry-run`, puis les tests Discovery pertinents. Sur Flutter : `flutter test test/discovery_mature_screen_test.dart test/guest_router_test.dart`.

Cas manuels sur données réellement stockées :
1. aucune image : possibilité N1 lisible ;
2. Event avec couverture : lien média chargeable depuis l'API de test ;
3. Activity personnelle et Activity Espace : image importée au Studio avec autorité ;
4. publication explicite : binding RECOGNIZE et image_url cohérents sur collection/détail ;
5. retrait : URL de consultation du media-use retourne 404 et la projection ne le renvoie plus ;
6. propriété étrangère, Groupe privé, Activity privée, propriétaire non public : aucune divulgation ;
7. fichier absent dans le stockage : 404, pas d'erreur 500 ;
8. réponse API et N1 mobile sur la même base/test.

Un APK DEV généré par GitHub Actions référence l'API HTTPS prévue par `mobile/config/dev.json`, actuellement une URL PythonAnywhere de test. **L'APK ne déploie pas le backend Django** : la branche #522 et la migration doivent être appliquées séparément à cet environnement de test avant de valider les nouveaux médias. Pas de déploiement de production ni de merge implicite.

## Limite de confidentialité héritée à traiter

`PresentationAsset.file` demeure actuellement un FileField utilisant le stockage MEDIA par défaut. L'ancien Studio expose déjà `asset.file.url` dans `hero_image`. Un URL brut `/media/presentations/assets/...` servi publiquement par l'hébergeur peut contourner la révocation de l'URL `published-media-file`. **Ce chantier n'efface pas cette dette historique** : sécuriser ou migrer le stockage des assets sans casser les données existantes doit faire l'objet d'une validation de migration physique et du routage serveur, avant exposition de médias sensibles. Ne jamais placer d'actif confidentiel dans ce stockage public.

## État et gates

Implémentation sur #522 non fusionnée. Les contrôles CI et les tests pertinents restent obligatoires avant merge ; la demande utilisateur de reporter leur fermeture à après P5 ne transforme pas une CI rouge en validation. Aucun nouveau seed ni backfill artificiel.


## Ajout P2 : stockage protégé des nouveaux médias N1

La migration additive `presentations.0006_private_presentation_assets` conserve `PresentationAsset.file` pour les anciens rendus MPS et ajoute `PresentationAsset.private_file`, stocké hors du `MEDIA_ROOT` public via `PrivatePresentationStorage`. Le formulaire d'import N1 écrit seulement dans ce champ protégé. La publication et le téléchargement autorisé privilégient `private_file` et conservent une lecture de compatibilité des anciens assets `file`. Les anciens liens `editorial_data.hero_image` ne sont pas automatiquement migrés ; leur confidentialité reste à vérifier selon le routage serveur existant.


## Addendum — clôture du chantier 03 (31 octobre 2026)

Le relevé précédent décrivait des états historiques de #522. Depuis le
[chantier 03](../implementation/discover-stage-03-media-resources-2026-10-31.md) :

- `public_presentation_media_for_activities` et `published_media_file`
  appliquent la visibilité logique du Space/Profile, l'éligibilité Groupe
  du viewer et l'état de l'Occurrence à l'instant de l'accès ;
- les nouveaux imports N1 et les nouveaux uploads `hero_image` du Studio
  MPS sont protégés (`private_file`) : les seconds passent par
  `presentations:editorial-media-file`, sous contrat de publication de
  `ActivityPresentation` ou autorité de lecture/preview ;
- les liens bruts déjà enregistrés dans les anciens `editorial_data`
  ne sont **pas** convertis automatiquement. La commande
  `harden_presentation_media_assets` traite les assets liés à des
  media-uses, avec audit/copie privée et purge optionnelle seulement si
  les références éditoriales connues le permettent ;
- la rétention automatique Flutter exige désormais l'origine API de
  confiance, et les refus explicites 403/404 purgent les images retenues
  après les écritures en cours.

La migration des octets historiques, l'inspection des règles nginx/CDN
et les tests en exécution demeurent à réaliser sur le déploiement. Les
versions de production ne sont pas modifiées par ces commits.
