# Makolo — Découvrir : chantier 03, médias et ressources

**Date :** 2026-10-31  
**Branche :** `fix/discover-a-continuation-context-20261014` — [PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522).  
**État :** **implémentation livrée en code**, tests écrits, exécution des tests et CI volontairement différée à l'étape 09.  
**Frontière :** pas de nouvelle identité métier, pas de modèle de Possibilité, pas de re-conception N1/N2, pas de migration automatique destructrice, aucun déploiement/merge réalisé.

## 1. Autorités et principes

- `PresentationAsset` : octets, provenance, ownership et stockage.
- `PresentationMediaUse` : association explicite à Activity/Occurrence, purpose, ordre, alt, publication et retrait.
- `ActivityResource` (Preparation) : document/texte/lien propriétaire, ses versions et son contrôle d'accès. Il n'est pas une image de couverture.
- `Discovery` : consomme les références publiques autorisées et les projette sans déduire la publication d'un simple fichier.
- `Flutter` : peut conserver des octets publics déjà acquis, mais ne fait aucune autorisation, ne déduit aucun droit privé et ne remplace pas l'API.

## 2. Corrections livrées

| Réf. | Dysfonctionnement / risque | Code réalisé | Contrôles ajoutés |
| --- | --- | --- | --- |
| M03-01 | Le sélecteur Presentation ne vérifiait pas la publication effective du propriétaire (retrait Space/Profile), mais la route de livraison la vérifiait : risque de divulguer ID, alt et URL d'un usage devenu non public. | `presentations/media_selectors.py::public_media_activities` introduit le gate canonique partagé : Activity publiée et publique, Space actif/recherchable/public et non suspendu, ou UserProfile personnel actif, public et recherchable. | `presentations/test_media_use.py` : suspension, archivage, non-publication, profil privé/non recherchable. |
| M03-02 | Les médias pouvaient être projetés sans le contrôle de Groupe du viewer et sans vérifier la validité courante de l'Occurrence. | `public_presentation_media_for_activities(..., profile=...)` recoupe l'éligibilité Group, les Occurrences `SCHEDULED` admises, le propriétaire de l'asset et le mime JPEG/PNG. `discovery/api/composition.py` transmet le viewer réel. | Groupe fermé vs membre autorisé, Occurrence annulée et propriété d'asset. |
| M03-03 | La route de fichier devait rester strictement alignée sur ce gate pour empêcher qu'un lien capturé antérieurement fournisse les octets après retrait. | `presentations/media_delivery.py` réutilise `public_media_activities`, le gate Group et l'état de l'Occurrence ; vérifie encore l'owner et le stockage à **chaque requête**. 404 en cas de refus ; `Cache-Control: private, no-store, max-age=0`, `nosniff`, `Content-Disposition: inline` et `Cross-Origin-Resource-Policy: same-site`. Aucun redirect vers `MEDIA_ROOT`. | Tests de retrait et de lecture refusée, tests existants des fichiers physiquement absents et médias retirés. |
| M03-04 | Le stockage automatique Flutter ne validait que la forme de `/presentation/media/uses/<uuid>/file/` ; un domaine externe imitant cette forme pouvait être conservé. | `DiscoveryOfflineStore` exige désormais une origine explicitement fournie par la configuration API (`trustedOrigin`) et la correspondance exacte scheme/host/port, en plus du chemin, sans query/fragment/userinfo. `RetainedPublicDiscoveryImage` et l'écran Découvrir lui transmettent cette origine. | Test de faux domaine et de refus sans origine de confiance. |
| M03-05 | Enregistrement mobile : suppression de la cible avant le rename et possibilité qu'une révocation 403/404 soit suivie par une écriture déjà en vol. | Remplacement via staging + backup/rollback pour images et documents explicitement conservés ; file d'opérations qui sérialise téléchargements, remplacement et suppression. Le retrait d'un média public passe **après** les écritures déjà en vol. | Tests de remplacement atomique en fonctionnement normal et de révocation gagnant sur une écriture concurrente. |
| M03-06 | Les anciens `PresentationAsset.file` peuvent rester physiquement sous `MEDIA_ROOT`, parfois exposé directement par nginx/CDN, même si l'URL `published-media-file` est révoquée. | Commande additive `harden_presentation_media_assets` : audit par défaut, `--apply` copie les assets associés à des usages vers `private_file`, vérifie SHA-256 source/copie ; `--purge-public` après copie et contrôle des références JSON `ActivityPresentation.editorial_data`, sans purge silencieuse. | `presentations/test_legacy_media_migration.py` : audit, copie, lecture via media-use après retrait du fichier brut, blocage sur lien éditorial historique. |
| M03-07 | Le Studio MPS générait encore de **nouveaux** liens `asset.file.url` vers la racine MEDIA publique pour `hero_image`. | `_editorial_from_post` importe maintenant avec `protected=True` et écrit une URL `presentations:editorial-media-file`. La nouvelle route exige un lien exact depuis une `ActivityPresentation` ; un brouillon n'est accessible qu'à son éditeur autorisé ; une présentation publiée doit satisfaire visibilité propriétaire/Groupe ou les droits personnels Invitation/Access. Le fichier reste privé et `no-store`. | `presentations/test_editorial_media_delivery.py` : aucun fichier public neuf, brouillon 404 pour tiers, prévisualisation owner, publication et retrait du Profile. |

## 3. Ressources Preparation (réutilisées, non réécrites)

Le chantier 02 a déjà assuré que l'aperçu documentaire de Discovery respecte `preparation.services.can_view_resource`, la portée Occurrence, les textes inline bornés et le retour vers les endpoints propriétaires `preparation:resource-text` et `preparation:resource-download`. Ce chantier ne recrée ni fichier, ni droits de lecteur, ni couche de cache pour les documents de Journey. Le Reader explicitement conservé reste distinct de la conservation automatique des images RECOGNIZE.

Le nombre de ressources légitimement exposées **n'est pas plafonné à six**. Les limites de taille concernent les octets inline, non le nombre de documents.

## 4. Stockage historique : procédure sûre (À EXÉCUTER sur l'environnement de déploiement)

La migration schema `presentations.0006_private_presentation_assets` ajoute `private_file` sans effacer les noms de fichiers précédents. Les nouveaux uploads du gestionnaire N1 `ActivityMediaUploadView` écrivent déjà vers ce champ protégé. Les assets historiques `file` restent lisibles comme compatibilité par la route autorisée.

**Commande non destructive d'inventaire :**

```bash
python manage.py harden_presentation_media_assets
```

**Copie + vérification sans purge :**

```bash
python manage.py harden_presentation_media_assets --apply
```

**Suppression contrôlée des anciens octets PUBLICS, uniquement après contrôle des références :**

```bash
python manage.py harden_presentation_media_assets --apply --purge-public
```

La suppression refuse les assets dont une URL brute apparaît encore dans un `editorial_data` historique. Les fichiers manquants sont signalés, pas remplacés artificiellement. La commande ne modifie pas les pages MPS qui référencent directement une ancienne URL `hero_image` ; leur conversion vers des URLs contrôlées demeure une opération de déploiement/migration éditoriale, avant de pouvoir supprimer les originaux correspondants.

**Limite explicite :** même après suppression, un cache de proxy/CDN ou une copie publique externe peut toujours servir des octets antérieurement exposés. En déploiement, bloquer la distribution publique de `/media/presentations/assets/`, auditer les références MPS, migrer ou corriger les pages historiques et purger le CDN selon la politique d'hébergement. **Ces contrôles externes n'ont pas été effectués ici.** Ne pas confondre « commande ajoutée au dépôt » et « fichiers réellement migrés et non publics en production ».

**Protection des nouveaux imports MPS :** depuis ce chantier, `_editorial_from_post` utilise `protected=True` et la route gardée `editorial-media-file`. Les valeurs `hero_image` historiquement enregistrées comme URL brute restent inchangées ; la commande d'audit signale et protège leur suppression. Les anciens liens déployés doivent être inventoriés et convertis par une migration éditoriale contrôlée avant d'exiger une purge complète.

## 5. Tests de régression

Ajoutés ou étendus :
- `presentations/test_media_use.py` : retrait de la visibilité propriétaire, Groupe, Occurrence, livraison ; nombre de requêtes borné malgré le gate additionnel.
- `presentations/test_legacy_media_migration.py` : audit, copie vérifiée, purge conditionnelle et conservation du lien contrôlé `published-media-file`.
- `presentations/test_editorial_media_delivery.py` : nouveau `hero_image` privé, route avec droits de brouillon/publication, révocation.
- `mobile/test/discovery_recognition_offline_test.dart` : origine forgée, politique first-party, remplacement complet, file de retrait et Reader indépendant.
- Tests déjà présents : `discovery/api/test_media_bindings.py`, `presentations/test_media_use.py`, `discovery/api/test_resource_previews.py`.

**Statut d'exécution : non exécutés.** L'utilisateur a demandé de poursuivre les implémentations sans se préoccuper des CI ; cela ne vaut ni attestation de sécurité de déploiement ni résultat de tests.

## 6. Critères de sortie de code

- [x] Sélecteur et transport media-use partagent l'admission propriétaire et le groupe.
- [x] Publication/retrait demeurent contrôlés par `media_services`, sans publication automatique depuis un fichier.
- [x] Aucun média d'Occurrence annulée ne passe le nouveau sélecteur/la livraison.
- [x] Aucune URL brute de stockage publiée dans la projection `media_bindings` ; contenu servi via lien media-use.
- [x] Retenue automatique conditionnée à la véritable origine API de confiance.
- [x] Remplacements locaux non destructeurs en cas d'échec de rename ; retrait sérialisé après écriture en cours.
- [x] Commande d'audit, copie privée et purge conditionnelle des fichiers hérités.
- [x] Nouveaux imports éditoriaux MPS sécurisés avec stockage privé et route de livraison autorisée.
- [x] Tests écrits et documentation d'exploitation ajoutés.
- [ ] Migration réelle, host/CDN, anciennes pages `hero_image`, tests exécutés : **ne pas prétendre réalisés**.

**Décision : CHANTIER 03 — CODE LIVRÉ, MIGRATION/VALIDATION D'EXPLOITATION EN ATTENTE.** Les travaux de gabarit N1 sont réservés au chantier 04. Pas de merge ni déploiement implicite.
