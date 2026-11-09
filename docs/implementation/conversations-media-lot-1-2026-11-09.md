# Conversations — Lot 1 : médias intégrés et visionneuses

Date : 9 novembre 2026  
Dépôt : \`TraditionLearningCommunity/makolo\`  
Branche : \`fix/discover-a-continuation-context-20261014\` (PR #522)

## Objectif

Permettre de **consulter** les pièces jointes privées directement dans une
Conversation : photos, notes vocales, audio, vidéos, PDF et texte brut, plutôt
que de ne montrer que leur nom. Grouper les médias appartenant à un même Point
et proposer une consultation détaillée modale, avec téléchargement et partage
explicites.

Aucun nouveau domaine, modèle ou chemin de stockage public.

## Flutter

- Réutilisation de \`ConversationAttachmentViewer\`, de
  \`PrivatePdfView\` / \`PrivateVideoControllerFactory\`, de
  \`AndroidDeviceDownloads\` et de \`SystemShareGateway\`.
- \`ConversationMediaGroup\` rassemble les pièces d'un Point ; les photos sont
  présentées en mosaïque bornée à quatre cases, avec compteur de surplus.
  Les messages audio, PDF et texte conservent des contrôles inline sur demande.
- Vidéo seule : lecture inline à la demande ; ensembles photo/vidéo :
  ouverture détaillée avec navigation précédent/suivant.
- Lecteur audio avec lecture/pause, position, durée et recherche temporelle ;
  lecteur vidéo avec lecture/pause et barre de progression.
- Visionneuse avec navigation, téléchargement et partage explicites ;
  messages d'erreur/reprise en cas d'échec d'accès.
- La liste Médias des détails garde des vignettes compactes et ouvre la
  visionneuse à l'élément choisi.
- Copies temporaires distinctes par ouverture, sous un emplacement privé
  propre au profil, pour empêcher un lecteur inline de supprimer le fichier
  d'une visionneuse détaillée. Nettoyage à la fermeture, hors export explicite.

Les documents non rendables nativement (notamment DOC/DOCX) conservent une
action explicite d'ouverture dans une application compatible : aucun lecteur
intégré fictif, ni conversion implicite côté serveur.

## Web

- Nouveau fragment \`_attachment_gallery.html\` commun aux Points et aux
  entrées d'Échange ; lecture directe image/audio/vidéo, PDF et texte brut.
- Grille multimédia et visionneuse modale pilotée par
  \`conversations-media-gallery.js\` : navigation, téléchargement, partage
  explicite si Web Share Files est disponible, compactage des grands
  ensembles visuels sans masquer les autres documents.
- Tous les liens pointent vers les routes d'attachment déjà contrôlées.
  Aucun média privé n'est chargé depuis une URL publique non autorisée.
- Autorisation d'aperçu inline uniquement pour types MIME strictement listés,
  avec \`nosniff\`, \`private, no-store\` et ACL existante.
- PDF/texte dans un iframe same-origin : adaptation de \`frame-src\` à
  \`'self'\` limitée aux vues HTML privées de Conversation, d'Historique
  et d'Échange. Le CSP global demeure inchangé et \`frame-ancestors 'none'\`
  reste en vigueur. La route de média conserve
  \`X-Frame-Options: SAMEORIGIN\`.

## Hors périmètre de ce lot

- Hiérarchie média du Point versus médias propres à une assertion de sondage
  ou à une question d'un formulaire : relève du lot 2 et de leurs projections
  serveur correspondantes.
- Ajouter/inviter des participants : lot 5. La recherche se fonde sur un
  **identifiant canonique**, pas sur une identité de nom ni une relation de
  « contact » obligatoire. Les politiques de découvrabilité, profil public,
  « ouvert à » et invitations restent à respecter.
- Politique de rétention longue durée, téléchargement vidéo exhaustif,
  génération serveur de miniatures vidéo et conversion serveur de DOC/DOCX :
  non introduits par ce lot.
- Aucune affirmation de compatibilité de lecture pour tous les codecs ou
  tous les navigateurs sans vérification sur appareil.

## Validation

Conformément à la demande du chantier, **aucune CI ni campagne de tests n'a
été lancée** dans cette intervention. Les commits ne constituent pas une
attestation d'exécution Android/Web. La vérification runtime devra établir
le fonctionnement effectif, notamment selon les codecs, le navigateur et
les permissions de stockage/partage de l'appareil.

La PR #522 n'est pas fusionnée.
