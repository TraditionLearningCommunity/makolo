# Capital d’action personnel — Q1 Personal Library Foundation

`Q_BASE_SHA = 0b368d0f91edce352265fdaefd2ae2978da0e76b`

Q1 introduit **Ma Bibliothèque** comme bounded context personnel durable, sans Journey artificielle et sans reconstruire Trust, Requirements, Readiness ou Sharing.

## Frontières

- `PersonalAsset` est l’identité durable d’un élément personnel.
- `PersonalAssetVersion` conserve chaque fichier/version de façon immuable et auditée.
- `JourneyArtifact` reste contextualisé dans une Journey ; son FK `journey` reste obligatoire.
- Un PersonalAsset n’est ni une Proof, ni un Requirement, ni un état de Readiness.
- Q1 ne dépend d’aucune branche Sharing non mergée.

## Controller et sujet

`controller` est l’unique racine d’autorisation Q1. Le sujet est exactement un `Profile` ou un `ExternalBeneficiary`, par contrainte XOR. Être sujet n’accorde aucun accès. Pour un bénéficiaire externe, Q1 respecte au minimum la provenance actuelle : seul son `created_by` peut l’utiliser comme sujet lors de la création.

## Versioning et stockage

Les fichiers vivent uniquement sur `PersonalAssetVersion`. La première version vaut 1 ; chaque suivante référence explicitement `supersedes`, conserve l’ancienne version, son hash SHA-256 et ses métadonnées. Une version persistée ne peut pas être modifiée ou supprimée silencieusement.

Le stockage réutilise `journeys.storage.private_artifact_storage`, sans URL publique. L’upload réutilise `validate_artifact_upload`, donc la limite configurée, la vérification taille réelle/MIME/signature et le calcul SHA-256 existants. Le chemin Q1 est opaque et n’utilise jamais le nom utilisateur.

## Sécurité

Selectors et services filtrent en base par `controller`. Membership, Assignment, rôle Journey, sujet distinct ou utilisateur authentifié quelconque ne donnent aucun accès implicite. L’archivage est logique via `archived_at`; les versions sont conservées.

## Suite du train Q

Q2 ajoutera l’UX Ma Bibliothèque et la réutilisation explicite d’une `PersonalAssetVersion` vers un nouveau `JourneyArtifact`, afin qu’un remplacement futur en Bibliothèque ne réécrive jamais l’historique Journey. Q3/Q4 pourront ensuite ajouter les relations de provenance, Action Memory/Trusted Reuse et politiques finales de rétention selon leurs checkpoints propres.
