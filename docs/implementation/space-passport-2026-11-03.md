# Makolo — Passeport d'Espace : raccordement Nous / Sharing / Flutter

**Date :** 3 novembre 2026  
**PR de travail :** #522, non fusionnée  
**Sources de vérité :** code et migrations actuels ; blueprint de domaine ; contrats Space, Sharing et Passeport personnel.

## Problème et principe

Le Passeport d'un Espace présente l'identité collective durable, ses Activities
opérées, les faits Trust établis et ses Credentials délivrés. Il ne devient pas
un Profil humain et ne porte pas de mot de passe, de session, ni d'autorité
implicite. « Nous » est le point d'entrée opérateur. Le lecteur public de
l'identifiant du Space reste la route canonique `/<identifier>/`.

Les capacités existantes `PassportProjection`, `PassportSnapshot`,
`PassportShareSubject`, `ShareEnvelope`, `ShareDelivery`, les liens signés,
le moteur PDF et la révocation sont réutilisés. Aucun nouveau modèle ou migration.

## Serveur

Le constructeur `build_space_passport` distingue désormais :

- **Complet :** données Space autorisées à l'opérateur, coordonnées
  institutionnelles privées, Activities publiées ou historiques privées,
  et équipes privées seulement sous `SPACE_TEAM_MANAGE`.
- **Public :** Activity de visibilité réellement publique, Trust public,
  synthèse de Credentials issus d'Activities publiques, identité publique.
- **Thématique :** même socle public, seules les familles thématisables
  sont filtrées par les Topics actifs ; l'identité générale reste présente.
- **Personnalisé :** même socle public par défaut, retraits `exclude`,
  `exclude_activity` et `exclude_credential` validés côté serveur.
  Les anciennes sélections `include` Web restent acceptées dans leur
  périmètre strictement public.

Un champ ou une Activity interne n'est jamais révélée par le seul choix d'une
variante ou d'un thème. Les liens de public Passport utilisent
`PublicIdentifier`, pas un slug deviné ni une URL de compte personnel.

L'API privée `/api/v1/organizations/workspaces/<slug>/passport/` expose
la projection complète et les métadonnées de composition au seul acteur
possédant `SPACE_MANAGE`. Elle possède des profondeurs séparées pour PDF,
émission, histoire paginée, lecture / PDF de version, Sharing explicite,
livraison Makolo→Profil et révocations. Les réponses portent
`Cache-Control: private, no-store`. Les autorisations restent serveur :
`SPACE_VIEW`, appartenance à l'équipe et Mandate Activity limité ne
déclenchent pas l'accès opérateur au Passeport privé.

L'émission PDF crée **une** version datée. Télécharger une version déjà
émise ne crée aucune nouvelle version. Le lien de vérification n'accorde
aucun droit de consultation privé. Un grant Sharing reste distinct.

## Flutter Nous

La route native `/space/:slug/us/passport` est accessible seulement depuis
le handoff `space.us` reçu du serveur pour un acteur possédant la
capacité de gestion. La page revalide l'acteur courant et purge la source
en mémoire lors du changement d'Espace.

La page possède quatre icônes : Confidentialité/édition (handoff vers les
paramètres institutionnels existants), Versions, PDF et Partager. Les quatre
actions Partager sont PDF dans l'OS, dans Makolo, lien public vivant, et lien
d'une version émise ; l'historique regroupe Télécharger, Partager, Révoquer.
Le PDF est enregistré dans les Téléchargements Android via le MediaStore
existant ; pas d'étape d'émission manuelle affichée.

Une unique projection propriétaire nourrit les quatre variantes locales.
Le client n'infère jamais une autorité ni l'admissibilité d'une Activity.
L'éditeur institutionnel réutilise l'API Organizations. Il regroupe
l'identité (nom, identifiant en lecture seule, présentation), la localisation
(ville et pays), le contact (e-mail, téléphone) et les liens (site web).
La normalisation HTTPS et la validation locale précèdent le PATCH, qui ne
transmet que les champs modifiés. Aucune nouvelle vérité métier n'a été créée.

## Frontières et limites assumées

- Le Space ne possède pas l'équivalent du modèle `ProfileVisibilityPolicy`
  par champ. Son écran natif **Confidentialité du Passeport** gère les deux
  réglages réels `Organization.public_profile` (lecteur public) et
  `Organization.searchable` (découverte/recherche), sans créer de
  fausses audiences par champ. Une granularité supplémentaire exigerait
  une décision de domaine et un contrat de données explicites.
- La consultation anonyme d'une ancienne version **publique** est
  revalidée après retrait de la visibilité publique d'une Activity ou d'un
  fait Trust/credential, ou désactivation du Passeport public. Le snapshot
  émis n'est pas réécrit ; son contenu n'est plus divulgué publiquement.
- Il n'existe pas de logo de Passport Space canonique dans `Organization`.
  Un média de Presentation ne peut pas être réutilisé comme portrait
  institutionnel sans lien de propriété, consentement et délivrance admise.
  La carte de l'Espace conserve donc actuellement une identité typographique.
- L'acquisition du Passeport collectif est actuellement online-only et
  fail-closed pour la source privée : aucune autorité révoquée ne doit
  rester visible à partir d'une ancienne projection hors ligne. Un
  cache local autorisé et réconciliable exigera une intégration ciblée au
  noyau Space existant, pas un deuxième moteur de synchronisation.
- Les Conversations ne sont pas déduites d'un envoi direct. Le
  destinataire Profil reçoit un `ShareDelivery` sous son identité.

## Vérifications nécessaires

Tests Django `organizations.test_space_passport_api`,
`sharing.test_g6_passport` et règles de disclosure ; widgets Flutter
`space_us_surface_test.dart`, plus build/analyseur de l'écran natif,
des routes et de l'éditeur. Sur Android : changement d'Espace actif,
Mandate révoqué, téléchargement OS, PDF externe, partage Makolo A→B,
versions anciennes, lecture publique sans compte et liens explicites.

**Statut :** code et tests ciblés poussés dans #522, mais **tests non
exécutés et rendu Android non validé**. Ce document ne déclare pas une
fermeture de production ni une fusion.
