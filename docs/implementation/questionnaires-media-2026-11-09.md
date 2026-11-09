# Questionnaires — médias canoniques par version, question et choix

**Date :** 9 novembre 2026  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Branche :** `fix/discover-a-continuation-context-20261014` (PR #522)

## Décision

Questionnaires est le domaine propriétaire des formulaires, questions et
réponses. Conversations peut publier un `Form Request` mais ne copie ni le
modèle `FormQuestion`, ni les médias, ni les assertions.

Une question peut présenter une consigne, un média et plusieurs assertions,
chacune possédant son propre groupe ordonné de médias/légendes.

## Relations persistées

Nouveau `QuestionnaireMedia` :

- `form_version` (FK obligatoire `FormVersion`) : provenance et version ;
- `question` (FK optionnelle `FormQuestion`) : média du libellé et des
  précisions de la question ;
- `choice_index` (entier optionnel) : position du choix existant dans
  `FormQuestion.choices` JSON (ce tableau reste propriétaire du contenu) ;
- `position` : ordre de présentation dans son niveau d'attachement ;
- `caption` : légende propre à chaque fichier ;
- `kind`, `mime_type`, `original_name`, `size`, `content_hash`,
  `uploaded_by`, `file` privé, `created_at`.

Les fichiers sans question appartiennent à l'introduction du formulaire.
Un index de choix exige une question à choix unique/multiple et doit être
compris dans son tableau. Les fichiers d'une question doivent appartenir à
la même version. La modification des assertions ayant des médias associés
est interdite tant que les médias n'ont pas été détachés.

Aucun champ existant n'est supprimé. Migration additive :
`questionnaires/migrations/0003_questionnaire_media.py`, dépendante de
`0002_profile_targeted_requests`. Les questionnaires et réponses historiques
n'ont aucun média ; leurs réponses restent inchangées.

## Versionnement et autorisations

L'ajout/retrait est réservé aux gestionnaires autorisés de l'Activity lorsque
la version est `draft`. Les versions `published` / `retired` ne sont pas
modifiées ; pour les enrichir, il faut créer une nouvelle version.

Le téléchargement requiert soit la permission de gestion de l'Activity,
soit une `FormRequest` non annulée visant le Profile ou le bénéficiaire
de la Journey. Aucun lien public de stockage n'est exposé.

Utilisation du stockage privé déjà présent dans le dépôt
(`private_artifact_storage`). Validation des fichiers par signature réelle :
images/documents via la validation sûre existante, médias audio/vidéo via
`core.private_media_validation`, commun à Conversations et Questionnaires.

## API

- `POST /api/v1/questionnaires/versions/<uuid>/media/` (multipart)
  reçoit `file`, `kind`, `caption`, `position`, `question_id` et
  `choice_index` facultatifs.
- `DELETE /api/v1/questionnaires/media/<uuid>/` : retrait autorisé
  uniquement du brouillon.
- `GET /api/v1/questionnaires/media/<uuid>/download/` : vérification
  des droits à chaque téléchargement, `private/no-store`, `nosniff`.
- Les projections `FormRequest` existantes gagnent :
  `form_version.media[]`, `questions[].media[]`,
  `questions[].choice_media[]`. Les clés de réponse restent identiques.

## Présentation

Le Web montre les médias à leur emplacement : introduction du formulaire,
texte de la question, puis ses médias, puis texte de chaque choix suivi
immédiatement des médias de ce choix. Lecture directe des images, audios,
vidéos, PDF et textes ; documents Office ouverts via action explicite.

Le gestionnaire Web permet l'ajout au formulaire, à une question ou à un
choix clairement identifié, et le retrait tant que la version est brouillon.

Flutter interprète les mêmes champs de projection et réutilise le lecteur
privé existant via un téléchargeur protégé propre à Questionnaires :
galeries, zoom images, contrôles audio/vidéo, PDF, fichiers et actions
de lecture/partage. Les médias sont en position avant la saisie des
assertions ou immédiatement après l'assertion concernée.

## Portée et contrôle qualité

Changements poussés directement sur la branche active de la PR #522 ;
aucune fusion de `main`, aucun déploiement.

À la demande du chantier, pas de CI, ni campagne de tests, ni exécution
Android/Web dans cette session. La revue effectuée est statique. Une
migration et une validation effective sur l'environnement de développement
seront nécessaires avant tout déploiement de test. Le stockage privé du
formulaire n'est pas une `Resource`, un `Proof` ou une copie de média
`ConversationPointAttachment`.

Les réponses des participants restent textuelles/structurées comme avant :
les pièces jointes ici enrichissent **les consignes du questionnaire**,
elles ne constituent pas encore des réponses de type fichier.
