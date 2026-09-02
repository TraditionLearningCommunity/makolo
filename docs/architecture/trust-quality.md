# Makolo — Trust & Quality (M4)

## Vision

M4 fournit la vérité transversale de confiance et de qualité de Makolo. `Event` reste une verticale et `Activity` le noyau. Trust ne duplique pas les états de Journey, Occurrence, Access, Services ou Payment : il lit leurs faits canoniques et produit des décisions ou projections explicables.

Doctrine : **faits observables → faits vérifiés → feedback subjectif**. M4 sépare Verification, Operational Reliability, Feedback, Reports, Disputes, Reputation et Proofs. Aucun `reputation_score`, `trust_score`, classement humain ou signal de popularité n’est créé.

## Verification

`VerificationClaim` représente une affirmation précise portant soit sur un `Profile`, soit sur un `Space`. Les claim types V1 sont contrôlés par code : identité Profile, identité Espace et contact. Aucun `GenericForeignKey` universel n’est utilisé.

Workflow : `REQUESTED → UNDER_REVIEW → VERIFIED | REJECTED`, avec transitions explicites vers `REVOKED`. Une `valid_until` passée rend immédiatement le claim inactif dans les projections publiques ; l’historique reste conservé. `REVOKED` est une décision explicite, différente de l’expiration temporelle.

La primitive historique `Organization.verification_status` et `accounts.VerificationDocument` est conservée. La migration M4 backfill uniquement les anciens Espaces `pending` et `verified`, avec une source `legacy-organization-status`, sans inventer de preuve ni renforcer un statut ambigu. Le champ Organization reste une projection de compatibilité lors des décisions d’identité Espace.

Une demande Espace exige `space.trust.manage`, donc un Mandate qui porte réellement cette autorité. Une membership seule n’accorde rien. La décision Makolo exige `platform.trust.review`. Le demandeur ou le Profile sujet ne peut pas s’auto-vérifier.

### Evidence

`TrustEvidence` est privé et ne possède qu’un parent : `VerificationClaim` ou `Report`. Il réutilise `accounts.validators.validate_verification_document` (taille, extension/MIME, signature PDF, image décodable). Les surfaces M4 ne renvoient jamais `file.url` : les téléchargements passent par une vue autorisée. Les notes de review et evidence ne font jamais partie des projections publiques.

## Feedback

`Feedback` est ancré à une `Journey` et, si pertinent, à son `Occurrence`. `can_submit_feedback()` exige le bénéficiaire Profile et un fait démontrant que l’expérience peut être évaluée : Journey fulfilled, Occurrence achevée/past, AccessUse accepté ou outcome Service successful. Une Journey future ou appartenant à autrui est refusée.

Une contrainte garantit un feedback principal par `(Journey, author)`. Les dimensions V1 contrôlées sont `delivery`, `timeliness`, `access_experience` et `accuracy` avec `yes/no/not_applicable`; la dimension Access est refusée lorsqu’aucun Access n’existe. Le sentiment et le commentaire sont facultatifs. Le retrait retire le feedback des agrégats publics. La modération masque un contenu ; elle ne réécrit jamais le sentiment ou les faits structurés.

M2 Questionnaires reste le moteur de formulaires génériques. M4 n’introduit aucun Form Builder concurrent.

## Reports

`Report` représente une anomalie nécessitant examen et reste distinct du Feedback. Les catégories sont contrôlées par code. Les relations sont explicites vers Journey, Activity, Occurrence, AccessUse et/ou Space ; aucun report universel par GFK.

Lifecycle : `OPEN → TRIAGED/INVESTIGATING → RESOLVED | DISMISSED`. Le participant ne peut créer un report Journey que sur sa propre expérience. Staff Makolo contrôle triage/résolution. Le texte, l’identité du reporter, l’evidence et les notes staff ne sont jamais inclus dans la projection publique Trust.

Un report non résolu n’influence pas la réputation publique.

## Disputes

`Dispute` est un dossier interne Makolo, pas un tribunal ni un arbitrage juridiquement contraignant. Il peut être ouvert depuis un Report suffisamment contextualisé. Les parties référencent les objets canoniques ; leurs noms/emails ne sont pas recopiés.

Workflow : `OPEN → UNDER_REVIEW/AWAITING_INFORMATION → DECIDED → CLOSED`. La décision conserve `decision_code`, un résumé divulguable, le décideur, la date et un `remedy_code`. Le remedy `refund_requested` signifie une demande d’action : M4 ne possède ni wallet, escrow, ledger ni vérité de remboursement et ne modifie jamais directement Payment.

## Operational Reliability & Reputation

`get_operational_reliability_summary()` et `get_public_trust_summary()` sont des projections dérivées. Elles n’écrivent aucune nouvelle vérité. V1 expose seulement les métriques que les données actuelles savent soutenir : Occurrences complétées/annulées et Journeys fulfilled/cancelled. Chaque métrique garde son numérateur, dénominateur, période et source canonique.

Le résumé public combine :

- claims publics encore actifs ;
- fiabilité opérationnelle factuelle ;
- nombre de Feedbacks liés à des expériences vérifiables ;
- ventilation sentiment seulement à partir de 3 Feedbacks sur la période.

Le seuil `PUBLIC_FEEDBACK_BREAKDOWN_MIN_SAMPLE = 3` évite de présenter un tout petit échantillon comme une certitude. Le résumé opérateur ajoute seulement des agrégats de dossiers. Aucune note privée, evidence, report ouvert ou commentaire brut n’est publié. Followers, likes, vues et popularité sont absents du calcul.

## Proofs / Attestations

`Proof` est une vérité structurée liée au bénéficiaire Profile d’une Journey. Son `public_id` est un UUID opaque distinct de la clé primaire. Types V1 : Journey accomplie, participation confirmée, Access utilisé, Service complété.

`issue_proof()` valide le fait canonique avant émission et utilise une unicité `(subject_profile, journey, proof_type)` pour rendre le retraitement idempotent. Une Proof n’est publique que si `is_public=True`; il n’existe aucun listing public des Proofs d’un Profile. Une Proof révoquée reste vérifiable comme révoquée. M4 n’ajoute ni blockchain, NFT, signature crypto artisanale ni moteur PDF.

## Privacy et permissions

Permissions nouvelles :

- `space.trust.view` : projection/dossiers divulguables de cet Espace ;
- `space.trust.manage` : demandes/actions Trust déléguables de cet Espace ;
- `platform.trust.review` : review/décision Makolo.

`space-owner` reçoit view/manage ; `space-admin` seulement view ; `makolo-platform-admin` reçoit review. L’autorité est résolue par Mandate. Les vues, API et téléchargements réutilisent les services/policies serveur ; l’authentification seule ne suffit pas aux opérations sensibles.

Les templates Django échappent les commentaires/descriptions. Les projections publiques sont des dictionnaires dédiés, jamais des sérialisations brutes de modèles Trust.

## Relations aux domaines canoniques

- **Activity / Occurrence** : sources d’opération et contexte ; Trust ne crée pas de statut parallèle.
- **Journey** : ancrage Feedback/Report/Proof et propriétaire du parcours.
- **Access / AccessUse** : source factuelle pour l’éligibilité et certaines Proofs ; Trust ne modifie pas les credentials.
- **Services** : outcome canonique peut prouver une expérience/complétion ; ServiceRequirementAssessment reste dans Services.
- **Finance / Payment** : propriétaire exclusif de l’argent. Un remedy Trust ne copie jamais `payment_was_refunded`.
- **Requirements / M1** : une future exigence peut référencer un claim par bridge explicite ; Trust ne bloque pas READY globalement.
- **Forms / M2** : collecte complémentaire possible, mais FormResponse n’est jamais automatiquement une Verification.
- **Resources / M2** : document public de préparation ≠ TrustEvidence.
- **Presentation / M3** : M4 expose des projections sûres. M3 possède la représentation et n’est pas une dépendance runtime de Trust.

## Web et API

Web V1 : résumé public Espace, console Trust Espace, demande Verification, Feedback participant, Report participant, lecture Report/Dispute autorisée, mes Proofs, vérification publique opaque et queue staff.

API V1 : résumé public Space, submit Feedback/Report, lecture de son Dispute, liste privée de ses Proofs et vérification publique d’une Proof explicitement partagée. Les commentaires/evidence/notes privées ne sont jamais inclus dans l’API publique Trust.

## Décisions reportées

M4 ne choisit pas de provider KYC/Identity, de politique légale définitive de rétention, de chiffrement artisanal, de ranking Discovery, de social feed, de marketplace/assurance/escrow, de modération IA ou de blockchain. Ces décisions pourront composer le contrat Trust sans déplacer la vérité M4.
