# Passeport personnel — corrections UX11 Web/API/Flutter (PR #522)

**Date :** 2 novembre 2026  
**Branche :** `fix/discover-a-continuation-context-20261014` ; aucune fusion.  
**Statut :** modifications et tests ciblés poussés ; tests locaux, build Android et CI non exécutés dans cette session.

## Point de départ

Les captures Android font apparaître un décalage entre les variantes, la confidentialité, le téléchargement PDF et le comportement attendu. Les quatre variantes restent `complete`, `public`, `thematic` et `custom`. Le Passeport demeure une projection, pas une identité civile, une Proof ou un nouveau domaine.

## 11 anomalies et résolution

| # | Problème | Résolution |
| --- | --- | --- |
| 1 | Le bouton PDF ouvre un sélecteur d’emplacement | **Corrigé sur Android 10+** : réutilisation du pont natif MediaStore `makolo/downloads` déjà présent ; PDF inséré directement dans Téléchargements, fichier temporaire nettoyé. Autres plateformes : sélecteur conservé. |
| 2 | Le Passeport Public paraît vide malgré des règles « Public » | **Contrat explicité, confusion supprimée** : les seuls faits présents et publiables paraissent ; un réglage de visibilité ne crée aucune valeur. Les champs vides sont regroupés dans la configuration. Les détails `owner_details` sensibles (téléphone, adresse, naissance, genre…) ne deviennent pas publics. |
| 3 | Thématique semble retirer l’identité | **Vérifié** : l’identité n’est pas filtrée par les Topics côté serveur. Explication de l’état vide et test ciblé du socle identitaire. |
| 4 | Personnalisé semble retirer l’identité | **Corrigé** : nom, photo autorisée publiquement, profession et localisation publiquement autorisées sont conservés implicitement. Une photo/ville explicitement privée ne fuit pas. Le reste demeure sélectionnable. |
| 5 | Absence de thèmes sans issue | **Corrigé** : message expliquant les Topics et accès « Choisir mes centres d’intérêt », puis rafraîchissement serveur au retour. |
| 6 | Sélecteur d’audience d’une information trop envahissant | **Corrigé** : feuille compacte, choix rapides « Tout le monde » / « Moi uniquement » ; audiences choisies et recherche de personne dans les options avancées repliées. |
| 7 | Confidentialité liste tous les réseaux vides comme publics | **Corrigé** : `has_value` est une projection owner-only dérivée ; les informations vides sont présentées sous une section repliable, sans changer leur politique. |
| 8 | Émission d’une version conditionnée à l’export PDF | **Corrigé** : `POST /api/v1/me/passport/issue/` crée un `PassportSnapshot` daté sans PDF ; même builder et mêmes permissions que l’export. |
| 9 | Partage indirect et peu explicite | **Corrigé** : action « Émettre et partager cette sélection » pour les variantes partageables, historique séparé, lien public distingué. Le Passeport complet n’est toujours pas partageable via un grant. |
| 10 | Barre supérieure encombrée et titre tronqué | **Corrigé** : titre « Passeport », actions principales Télécharger et Partager ; Confidentialité, Versions et Émettre sans PDF dans un menu secondaire libellé. |
| 11 | Éditeur trop long | **Corrigé** : sections localisation, profession et liens facultatifs repliables ; identité, date de naissance, genre, téléphone et visibilité conservent leur accès. |

## Frontières canoniques

- Les variantes publiques ne recopient jamais `owner_details` ni les informations non autorisées par Accounts.
- `ProfileVisibilityResolver` reste la décision unique des audiences des champs ; `has_value` ne confère aucun droit.
- Une version datée est immuable et ne peut être partagée que par un grant Sharing distinct, révocable et expirant.
- L’émission sans PDF ne nécessite pas de nouvelle table ou migration. Le PDF continue à émettre et à rendre dans une transaction atomique.
- La version thématique filtre les faits liés au Topic, pas le socle identitaire.
- Sur Android, le pont MediaStore existant refuse les fichiers vides et nettoie toute écriture interrompue ; sur API <29, il échoue explicitement plutôt que de promettre une sauvegarde publique impossible.

## Parcours visés

1. Ouvrir le Passeport et choisir une variante ; les données privées du Passeport complet ne se retrouvent pas dans la projection publique.
2. Si aucun thème : accéder aux centres d’intérêt, revenir, actualiser et choisir un Topic.
3. Personnaliser : l’identité publiquement admissible reste visible ; sélection explicite pour les autres contenus.
4. Émettre une version dans le menu, sans générer de PDF ; la retrouver dans « Versions datées ».
5. Émettre et partager une variante partageable avec un délai ; révoquer ensuite son lien si nécessaire.
6. Télécharger : Android inscrit directement le PDF dans Téléchargements, sans sélecteur.
7. Confidentialité : choisir rapidement Public/Privé, ou ouvrir les options avancées ; champs vides repliés.

## Tests ciblés ajoutés/actualisés

- `sharing.test_passport_variant_identity` et `sharing.test_g6_passport` : identité des variantes, photo, ville privée et contenu complet distinct.
- `sharing.test_passport_issuance_sharing` : émission sans PDF, historique, authentification et refus des paramètres de contexte.
- `accounts.test_profile_visibility` : distingue règle publique et présence effective de la donnée.
- `mobile/test/me_passport_history_test.dart` : menu d’actions, émission sans PDF, Public/Thématique et identité stable.
- `mobile/test/me_passport_visibility_compact_test.dart` : champs non renseignés, sélection d’audience compacte.
- `mobile/test/me_profile_privacy_test.dart` : édition Accounts existante de la date de naissance et du genre.

Commandes facultatives de validation ultérieure :

```bash
python manage.py test sharing.test_passport_variant_identity sharing.test_g6_passport sharing.test_passport_issuance_sharing accounts.test_profile_visibility
cd mobile
dart format lib/features/me/me_passport_screen.dart lib/features/me/me_passport_visibility_screen.dart lib/features/me/me_profile_screen.dart lib/platform/files/passport_pdf_saver.dart test/me_passport_history_test.dart test/me_passport_visibility_compact_test.dart
flutter test test/me_passport_history_test.dart test/me_passport_visibility_compact_test.dart test/me_profile_privacy_test.dart
```

La vérification visuelle Android, notamment le dossier Téléchargements réel, reste à réaliser sur appareil après compilation de cette branche. Aucune fusion ni opération sur `main`.
