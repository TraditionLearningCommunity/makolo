# Passeport Flutter — parcours documentaire et composition native

**Branche :** PR #522 · **État :** code poussé, non fusionné, sans validation
Android complète à ce stade.

## Composition

Une projection Complet du titulaire est reçue et conservée dans son contexte
local-first. Flutter produit les aperçus Public, Thématique et Personnalisé par
retrait des faits non admissibles ou non pertinents, sans recharger la
projection pour chaque bascule. Les décisions d'admissibilité viennent du
serveur ; aucune règle d'autorité n'est déplacée au client.

Les champs personnels publics sont fournis sous `presentation_details`,
distincts de `owner_details`. Prénom, nom, identifiant, ville et pays ne sont
présentés que selon leurs politiques respectives. Téléphone, adresse, date de
naissance et autres données sensibles ne sont pas recopiés dans les variantes
publiques. La section reste visible s'il reste au moins un fait admissible.

## Barre et actions

La barre contient Confidentialité, Versions, PDF, Partager.

- **PDF :** une émission serveur, téléchargement immédiat dans le dossier
  Téléchargements Android. Pas de prévisualisation ni de choix de dossier.
- **Partager :** exactement quatre actions : Partager le PDF, Partager dans
  Makolo, Partager le lien public, Copier le lien du Passeport.
- **Versions :** historique daté, chaque version proposant directement
  Télécharger, Partager et Révoquer. Aucun doublon dans le menu Partager.

Le lien signé de vérification et le droit Sharing sont distincts. Un
destinataire conserve sa propre session. Les PDF externes déjà transmis ne
peuvent pas être rappelés.

## Édition

`MeProfileScreen` reste l'éditeur Accounts. Groupes : Identité,
Localisation, Contact (e-mail en lecture seule, téléphone), Activité
professionnelle (profession, entreprise, organisation), Liens et réseaux
sociaux (site web, LinkedIn, Facebook, Instagram, TikTok, X, YouTube),
Visibilité.

L'identifiant Makolo est présenté avec une action distincte exploitant
l'endpoint Accounts et ses contraintes d'unicité et de délai. Il n'est pas
ajouté au PATCH général. La modification de l'e-mail n'est pas exposée faute
d'un parcours de vérification dédié. Les brouillons sont préservés en cas
d'erreur et les champs invalides signalés.

## Parité documentaire

Le snapshot émis fige les faits admissibles, y compris les données
personnelles publiables. Le PDF et la lecture d'une version historique ne
reconstruisent pas la biographie ou le rôle depuis le Profil actuel. Les
informations absentes n'impriment aucune rubrique vide. La langue du document
n'est pas un fait personnel.

## Vérifications encore à exécuter

- Tests Django ciblés : projection, frontières d'audience, snapshots, PDF.
- Tests widgets Flutter : quatre variantes, groupes de champs, menu de
  partage et historique.
- Compilation Flutter, formatage, contrôle Android Downloads, partage natif,
  lecture A vers B et changement d'identifiant.
- Pas de fusion tant que les garanties pertinentes n'ont pas été vérifiées.
