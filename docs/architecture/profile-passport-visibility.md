# Passeport Makolo - visibilite personnelle (PR #522)

## Objectif
Un seul Profil, plusieurs projections selon le lecteur. La variante Complete est reservee au proprietaire ; la vue partagee est filtree selon la politique de visibilite et les permissions des domaines d'origine.

## Domaines proprietaires
- Accounts porte l'identite et les regles de divulgation (ProfileVisibilityPolicy, ProfileVisibilityAudience).
- Topics porte Interests et Open To, jamais copies dans le Passeport.
- Groups, Organizations et Authorization portent les relations collectives actuelles.
- Trust, Activity, Journey gardent leurs protections propres.
- Le Passeport demeure une projection, pas une source de verite supplementaire.

## Audiences cumulables
- Public : tout visiteur.
- Mes collectifs : membres actuels partageant une appartenance effective a un collectif actif avec le proprietaire, relation recalculee a chaque consultation. Un Mandate ou une Permission d'Espace sans Membership n'etablit jamais cette appartenance.
- Espace, Equipe ou Groupe choisi : relation effective des deux profils au collectif selectionne.
- Personne choisie : profil Makolo designe.
- Une politique sans audience est privee.
- Public est exclusif des audiences restreintes pour eviter toute
  divulgation involontaire. Plusieurs audiences restreintes peuvent se cumuler.
- L'identifiant public du porteur reste accessible.

Aucun collectif aujourd'hui signifie aucun membre autorise. Une adhesion future ouvre automatiquement la visibilite a ses membres. Un depart la ferme. L'appartenance n'accorde aucune autorite metier.

## Compatibilite et protection
- Nouveaux Interests / Open To publics par defaut ; les flags historiques explicitement prives restent prives sans migration de donnees.
- Le consentement a la recherche reste independant de la visibilite du profil.
- Secrets, telephone, email, naissance, adresse precise, coordonnees fines et AccessCredential sont hors des cibles publiables.
- Les documents PDF/HTML publics produits pour un lecteur tiers ne contiennent pas de faits reserves aux collectifs.
- Les anciennes versions exportees sont des documents dates et ne changent pas retroactivement.
- Une verification publique ancienne conserve la preuve d'emission, mais son contenu
  est masque si la divulgation personnelle publique s'est restreinte depuis.
  Un partage explicite d'instantane releve de Sharing (duree et revocation).

## Surfaces
- API privee proprietaire : GET/PUT /api/v1/me/passport/visibility/
- Web : Passeport puis Confidentialite
- Flutter : Passeport puis action Confidentialite
- Consultation Web / API publique : filtre serveur, jamais seulement client

## Validation avant fusion
- python manage.py makemigrations --check --dry-run
- python manage.py migrate --plan
- python manage.py test accounts.test_profile_visibility accounts.test_passport_visibility_integration accounts.test_public_profile_api topics.tests sharing.test_g6_passport sharing.test_passport_public_identity
- dart format, flutter analyze et tests cibles Flutter
- PostgreSQL, tests d'appartenance active/retiree et absence de fuite sur exports
- Ne jamais fusionner avec CI rouge.

## Fermeture P1-P4 sur #522
- Les regles par champ incluent les faits declares entreprise et organisation,
  visibles dans la presentation Web, Flutter et PDF selon leur audience.
- Le Passeport complet proprietaire compose les equipes, groupes et Espaces
  accessibles deja presents dans Moi, sans les exposer par defaut en public.
- Web et API consomment la meme projection de reglage owner-scoped.
- Les IDs malformes de cibles de confidentialite produisent une reponse 400.
- Les variantes restent Public, Complet, Thematique et Personnalisees.
  La lecture avec audience est un mode de consultation, pas une variante.
- Les scenarios de publication, retrait, nouvelles appartenances, depart de
  collectif, IDOR et anciennes versions publiques sont couverts par des tests
  cibles a executer localement dans P5.

## Fermeture de la frontiere appartenance / autorite (etape 4)
- Les TeamMembership actives creent des relations Team et Space, sans accorder d'autorite.
- Les GroupMembership actives et les Groups personnels actifs possedes creent des relations Group, sans autorite implicite.
- Les Mandates d'Espace restent dans Authorization : ils ne sont pas des Membership et n'ouvrent pas « Mes collectifs ».
- Les audiences restreintes sont resolues sur le viewer authentifie et les appartenances courantes a chaque consultation, jamais par simple role global ou cache public.
- L'aperçu du lecteur peut exposer seulement les champs explicitement ouverts a ce lecteur ; la projection publique exportable conserve ses limites de publication.
- Regression cible : `accounts.test_passport_visibility_integration` couvre Mandate seul, adhesion active et depart.

## Fermeture fonctionnelle de l'étape 4 — consentement et lecture (PR #522)

### Consentement initial
- Le programme G conserve la proposition **Public par défaut** pour une nouvelle déclaration explicite Interest / Open To ; aucune déclaration n'est inférée d'une recherche, d'un Favori ou d'une veille.
- Sur Web, choisir une nouvelle déclaration propose automatiquement sa publication, mais décocher **Afficher publiquement** avant le premier enregistrement doit être respecté par le serveur. Sans JavaScript, le formulaire se replie sur le choix effectivement coché (non coché = privé). Les options visibles sont servies par `static/js/topic-declaration-visibility.js`, sans contrôle de permission côté client.
- L'API `/api/v1/me/considerations/settings/` accepte `new_visibility: "public" | "private"` pour les déclarations nouvellement créées. En cas d'omission, le comportement public de compatibilité est conservé ; un changement de sélection ne modifie jamais la visibilité des lignes retenues.
- Flutter propose **Ajouter publiquement / Garder privé** *avant* toute mutation. Le choix `private` ne déclenche ni `searchable` ni conversion d'Interest en Open To.
- L'ancien formulaire Topics et le réglage détaillé du Passeport ont une seule vérité de divulgation : les cases Public affichent la visibilité publique effectivement calculée. Une action explicite retire le cas échéant une ancienne règle PUBLIC persistée, sans effacer un partage ciblé toujours restreint.

### Frontières du lecteur et des documents
- `public_profile` ouvre la consultation d'une projection publique ; `searchable` est une décision indépendante. Ni Membership, ni Mandate, ni Permission ne deviennent automatiquement une audience ; une relation collective active est nécessaire des deux côtés.
- Le mode de consultation par une personne autorisée (`audience=mine`) est **une vue Web dynamique**, pas un droit d'export ni un cinquième type de Passeport. Les téléchargements, PDF et documents publics restent filtrés pour un visiteur public.
- Une ancienne version publique conserve son identité documentaire et son empreinte. Sa lecture publique est refusée si le Profil, un champ déclaré, un Interest/Open To, une Activity, une Proof ou un Credential qu'elle contient n'est plus publiquement admissible selon le domaine propriétaire. Les identifiants stables (Activity.id, Proof.public_id, Credential.public_id) sont comparés aux sources actuellement représentables ; une simple modification de titre ne révoque pas le contenu daté.
- Un lien de vérification constate l'émission, il ne crée jamais un partage privé. Un partage explicite d'un snapshot privé non-complet relève de Sharing, avec expiration et révocation propres. Changer la visibilité du Passeport vivant ne rappelle pas les PDF déjà téléchargés ni ne révoque à lui seul un partage explicite : le titulaire doit pouvoir révoquer ce lien séparément.
- Aucun nouveau domaine de données, variable de production ou audience Activity/Proof/Credential parallèle n'est introduit. Les trois familles gardent les droits de leurs propriétaires canoniques.

### Vérifications ciblées ajoutées, sans bloquer le chantier sur CI
- `topics.test_passport_initial_disclosure` : première sélection privée ou publique, audience antérieure PUBLIC retirée, audience ciblée préservée, mutation native privée et `searchable` indépendant.
- `sharing.test_passport_stage4_withdrawal` : un ancien document public est masqué après retrait de l'Activity, de la Proof ou du Credential ; l'émission datée n'est pas effacée.
- `accounts.test_passport_visibility_integration` : « Mes collectifs » et Space choisi ne s'ouvrent pas avec un Mandate seul.
- Les migrations historiques ne sont pas destructivement réécrites ; les comportements de publication déjà consentis restent valides.

**État :** règles de l'étape 4 implémentées dans #522. Validation automatique et intégration finale sont des opérations séparées.

## Lecture native d’une version émise — Web/API/Flutter

Une vérification d'émission et un partage explicite de version datée restent deux contrats différents.

- Le reader Web et l'API `sharing.passport.document` partagent la décision de publication actuelle et `_snapshot_content_allowed`. Un lien signé de vérification n'ouvre pas de document privé à un tiers, même lorsque le document est intègre.
- Le reader d'un lien Sharing passe toujours par `resolve_passport_share` (expiration, révocation, intégrité, variante non complète). Un lien partagé peut lire exclusivement le `PassportSnapshot.payload` original ; il ne reconstruit pas le Profil vivant.
- L'API fournit `payload=null` lorsque le viewer n'a pas de droit de lecture. Les réponses sensibles sont `private, no-store` et varient sur les éléments d'authentification.
- Flutter ouvre les liens `/passport/verify/<token>/` et `/passport/shared/<token>/` dans un lecteur natif sans stockage persistant automatique. Changer de token ou recevoir un refus retire la projection précédemment vue.
- Ce lecteur ne transfère aucun droit supplémentaire de Profile, Permission, Mandate, Access ou Requirement. La vérification d'émission ne certifie pas toutes les déclarations du titulaire.

Contrat de mise en œuvre et tests ciblés : `docs/implementation/profile-passport-reader-closure-2026-11-02.md`. La séquence 01–06 du Passeport demeure inchangée ; il ne s'agit pas d'une étape canonique 07.
