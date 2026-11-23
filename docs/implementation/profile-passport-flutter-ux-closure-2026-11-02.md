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

## Éditeur intelligent — 3 novembre 2026

L'éditeur Accounts conserve un bouton global **Enregistrer**, mais **aucun
bouton de vérification par champ**. Flutter valide silencieusement au fil de
la saisie lorsqu'un champ a déjà été vérifié, et à la perte du focus pour un
nouveau champ. Il corrige automatiquement les espaces périphériques et
normalise les liens vers HTTPS sans ajouter un second protocole, de manière
idempotente. Les URL sont validées par structure, longueur et domaine du
réseau social déclaré ; l'application ne prétend pas tester leur disponibilité.

Les règles locales sont isolées dans
`mobile/lib/features/me/passport_editor_field_rules.dart` :
- Prénom/Nom : 150 caractères ; Profession, Entreprise, Organisation :
  255 ; Ville : 100 ; Téléphone : 30 caractères de saisie, dont 7 à 15
  chiffres ; URL : 200. À propos et Adresse n'ont pas de limite
  arbitraire additionnelle.
- Téléphone : clavier et ponctuation adaptés, indicatif non inventé.
  Date de naissance : sélection locale, sans date future. Pays :
  sélection ISO existante, avec reconnaissance des noms/codes exacts.
- Identifiant Makolo : casse et préfixe `@` normalisés localement,
  3 à 30 caractères et noms réservés contrôlés avant l'appel à
  `auth/identifier/`. L'unicité et les délais demeurent sous Accounts.
- Photo : extension et signature JPEG/PNG/WebP et taille maximale
  de 5 Mo contrôlées avant l'envoi ; Accounts valide intégralement
  l'image et son autorisation.

Les erreurs détectables localement ne provoquent aucun PATCH. Le feedback
est limité à une icône et à un message court sous le champ concerné.
L'éditeur n'ajoute ni tutoriel ni appel réseau par frappe. Lors de
l'enregistrement, seuls les champs effectivement modifiés sont transmis ;
une ancienne valeur non modifiée et invalide n'empêche pas de sauvegarder
un autre champ. Les brouillons et erreurs restent récupérables.

**État :** modifications et tests de régression poussés sur #522.
Les tests Flutter n'ont pas été exécutés dans cette session (SDK non présent
dans l'environnement disponible). Le serveur reste l'autorité finale.
