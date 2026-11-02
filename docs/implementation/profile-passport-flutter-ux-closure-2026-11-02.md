# Passeport Flutter — parcours PDF et partage natif

**PR :** #522 ; **fusion :** aucune. **Validation :** tests rédigés, non exécutés ici.

## Contrat utilisateur

Le bouton PDF n'exécute plus automatiquement un téléchargement. Il présente :
- **Prévisualiser** : lecteur PDF dans l'application (pdfrx déjà présent).
- **Enregistrer dans Téléchargements** : conserve le pont natif Android MediaStore déjà implémenté.
- **Choisir le dossier** : sélecteur natif FilePicker, avec octets PDF transmis à la destination retenue.
- **Partager le PDF** : partage de fichier via share_plus (applications installées, selon Android).

Le menu Partager conserve **partager/coller le lien public**, **émettre puis partager une version**, **historique des versions et partages expirants** ; il ajoute **partager le PDF**. La distinction lien public / lien de version émise / document transmis en tant que fichier reste visible. Un PDF déjà transmis ne peut pas être rappelé via Sharing. Les fichiers de travail temporaires sont effacés après usage.

## Public et variantes

Public ne signifie pas un « profil réduit à la carte d'identité ». C'est la projection **de toutes les familles de faits de Complet qui sont admissibles publiquement** : identité, présentation, liens, intérêts, Open To, activités, preuves et credentials admissibles. Les informations strictement propriétaires (téléphone, adresse, date de naissance, relations internes, etc.) restent hors Public, sauf évolution canonique des règles de divulgation.

Thématique garde l'identité autorisée et filtre les faits thématiques ; Personnalisé compose selon les sélections du titulaire avec les frontières de confidentialité en vigueur. Le filtre d'une variante ne transfère pas de Permission, Mandate ni Access.

## Points de QA restant à réaliser

- Sur Android : vérification prévisualisation, sauvegarde Downloads, choix de dossier, envoi PDF et lien via WhatsApp/SMS/apps installées ; annulation et nettoyage.
- Comparaison Web/API/Flutter/PDF sur identité publique et chaque famille de faits.
- Exécution des tests Flutter et Django ciblés ; revue de l'absence de régression de l'historique et de l'émission.

Le test `sharing.test_passport_stage3_content` est enrichi pour contrôler que Public n'efface pas une famille complète de faits publiables.
