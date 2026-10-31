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
- Mes collectifs : membres actuels partageant un collectif actif avec le proprietaire, relation recalculee a chaque consultation.
- Espace, Equipe ou Groupe choisi : relation effective des deux profils au collectif selectionne.
- Personne choisie : profil Makolo designe.
- Une politique sans audience est privee.
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
