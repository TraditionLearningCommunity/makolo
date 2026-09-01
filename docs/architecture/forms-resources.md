# Forms, Questionnaires & Resources de préparation

## Décision de bounded context

M2 utilise `questionnaires` plutôt que `forms` afin d’éviter l’ambiguïté avec `django.forms`. Le moteur reste transversal : il dépend des primitives canoniques Activity/Journey et ne connaît ni `EventDetails` ni `ServiceDetails`.

Les Resources de préparation vivent dans le bounded context `preparation`, au voisinage du cœur Activity. Elles sont explicitement rattachées à `Activity` et éventuellement `Occurrence`.

## Invariants

- Activity reste le noyau.
- Journey reste le parcours individuel canonique.
- Requirement reste une condition métier ; ce n’est pas un formulaire.
- JourneyArtifact reste l’artefact individuel d’un dossier Journey.
- ActivityResource est une information ou un document partagé de préparation.
- Readiness reste dérivé ; aucun `is_ready` M2 n’est stocké.
- Mandate/permissions restent l’autorité serveur.

## Questionnaires

### Form

`Form` est une définition durable rattachée à une Activity canonique. `key` est unique dans l’Activity. Le propriétaire n’est pas recopié : l’autorité découle de l’Activity et de `ACTIVITY_MANAGE`.

### FormVersion

`FormVersion` porte une version numérotée. Une version commence `draft`, devient `published`, et les champs structurels d’une version publiée ne peuvent plus être modifiés silencieusement. Une évolution se fait par une nouvelle version. Les Requests/Responses restent liées à la version réellement utilisée.

### Questions

`FormQuestion` est ordonnée par `position` et supporte :

- `short_text` ;
- `long_text` ;
- `boolean` ;
- `single_choice` ;
- `multiple_choice` ;
- `number` ;
- `date`.

M2 n’ajoute pas de question `file`. Un document individuel fourni dans une Journey continue d’utiliser `JourneyArtifact`.

Les contraintes utiles (`required`, longueurs, bornes numériques, choix autorisés) sont validées dans les services serveur, indépendamment du client.

### FormRequest

`FormRequest` lie explicitement une `FormVersion` publiée à une `Journey`. Il porte `required`, `opens_at`, `due_at`, son statut et `completed_at`. Il n’existe aucun GenericForeignKey métier universel.

Une Request ne peut pas relier une Journey et un Form de deux Activities différentes.

### FormResponse / FormAnswer

Une Request possède au plus une Response. La Response connaît explicitement la version et le répondant. Le répondant doit être le bénéficiaire de la Journey.

Workflow M2 :

- `draft` ;
- `submitted` ;
- `reopened` via une opération explicite et auditée.

Après soumission la mutation participant est refusée. Une réouverture est une action opérateur avec autorité Activity.

### Permissions et privacy

Le participant ne peut lire ou modifier que les Requests de ses Journeys. L’opérateur doit disposer de `ACTIVITY_MANAGE` pour créer/publier/demander des Forms et consulter les réponses dans le périmètre de l’Activity. Une JourneyAssignment seule ne confère pas cette autorité.

Les Domain Events et notifications ne copient aucune réponse sensible.

### Requirements et Services

La soumission d’un formulaire ne satisfait pas automatiquement un Requirement. `FormRequest` et `FormResponse` fournissent les identifiants stables qu’un domaine consommateur peut relier explicitement à son Requirement/Assessment. La décision de satisfaction reste dans le domaine propriétaire (par exemple Services), sans dépendance `questionnaires -> services`.

JourneyArtifact reste la primitive d’evidence documentaire individuelle. M2 ne crée pas `UploadedDocument`.

### Readiness

Le contributeur `questionnaire_contributor` applique :

- Request obligatoire ouverte et non soumise -> `ACTION_REQUIRED`, reason `form_response_required` ;
- Request future -> `WAITING`, reason `form_response_not_open` ;
- deadline dépassée et action désormais fermée -> `BLOCKED`, reason `form_response_deadline_passed` ;
- Response soumise -> `SATISFIED`, reason `form_response_submitted` ;
- Request optionnelle -> ne bloque pas Readiness.

La NextAction pointe vers la Request web canonique. Une validation métier externe reste représentée par le contributeur du domaine qui possède cette validation ; M2 n’invente pas une review Form.

## Resources de préparation

### ActivityResource

`ActivityResource` se rattache à une Activity et, facultativement, à une Occurrence. Elle ne duplique ni titre Activity, ni lieu, ni date, ni organisateur.

Kinds M2 :

- texte/instructions ;
- URL externe ;
- fichier privé.

### Visibilité

- `public` : publication destinée au contexte public ;
- `participant` : seulement un bénéficiaire disposant d’une Journey active dans le scope Activity/Occurrence ;
- `restricted` : seulement une autorité `ACTIVITY_MANAGE`.

Les fichiers sont stockés via un storage privé sans URL publique. Le téléchargement passe par une vue qui revérifie l’autorisation. La validation de fichier réutilise la discipline JourneyArtifact : limite de taille, MIME autorisé, signature réelle et SHA-256.

### Versioning

Une Resource commence en version 1. Le remplacement crée une nouvelle ligne avec `supersedes`, incrémente exactement la version, publie la nouvelle version et marque l’ancienne `superseded`. Les contraintes DB distinguent correctement scope Activity et scope Occurrence, y compris lorsque l’Occurrence est NULL.

### JourneyArtifact

`ActivityResource` et `JourneyArtifact` restent séparés : consulter une Resource ne crée aucun Artifact et rendre un Artifact visible à un opérateur ne le transforme pas en Resource.

### Readiness

Une Resource informative ne bloque jamais Readiness. M2 ne crée pas de preuve de lecture implicite. Un futur acknowledgement devra être explicite, audité et posséder son propre contributeur Readiness.

## Domain Events, Notifications et Automation

Les services propriétaires émettent :

- `form.requested` ;
- `form.submitted` ;
- `form.reopened` ;
- `resource.published` ;
- `resource.replaced`.

Les notifications M2 sont consommées depuis l’outbox existante. Une nouvelle Request ou une réouverture peut notifier le bénéficiaire. Une Resource ne déclenche une notification participant que si la publication est explicitement marquée `significant_update`, afin d’éviter le spam.

M2 ne crée aucun scheduler. `due_at` et les Domain Events sont les primitives qu’Automation/Autopilot existant peut utiliser pour des rappels idempotents avant échéance. Une future règle de rappel doit rester dans l’infrastructure Automation, pas dans `questionnaires`.

## Web et API

Participant :

- Journey detail -> Forms (`À compléter`, `En cours`, `Soumis`) ;
- ouverture, sauvegarde brouillon, soumission, relecture ;
- section `Documents et instructions` filtrée par autorisation.

Opérateur :

- console Form par Activity : création, nouvelle version, ajout de questions, publication, Request Journey, consultation des réponses ;
- console Resource par Activity : création, visibilité, publication, remplacement/versioning.

API participant :

- lister/lire ses FormRequests ;
- sauvegarder une réponse ;
- soumettre ;
- lister les Resources d’une Journey autorisée.

Les endpoints appellent les mêmes services que le web : le backend reste la source de vérité.
