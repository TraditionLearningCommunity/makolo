# Passeport Makolo — document PDF de représentation

**Portée :** Profil personnel et Espace. Contrat d'impression du Passeport déjà composé et autorisé par Sharing. Cette note accompagne le chantier de la PR #522 ; elle ne crée aucun nouvel état métier.

## Fonction

Le PDF du Passeport Makolo peut accompagner un CV, un dossier, une candidature ou des attestations. Il représente des informations déclarées, des activités pertinentes et, lorsqu'ils existent, des faits établis ou des titres réellement délivrés. Il est émis par Makolo, **sans être présenté comme une pièce d'identité légale ni comme une certification générale de ses déclarations**.

Le document est la traduction **éditoriale sur papier** du Passeport, non une capture d'écran ni une seconde source de vérité.

## Chaîne propriétaire

1. sharing/passport.py construit une PassportProjection selon le sujet, le contexte d'autorité et la variante (complete, public, thematic, custom).
2. sharing/passport_documents.py sérialise les faits admissibles et émet **un** PassportSnapshot daté, avec une empreinte documentaire.
3. sharing/passport_pdf.py associe à **ce même snapshot** l'identifiant documentaire, la date UTC et le lien de vérification signé ; il prépare uniquement la photo propriétaire admise dans la projection.
4. sharing/passport_pdf_layout.py compose le fichier A4 à partir du contenu émis et de médias déjà autorisés. Ce module ne lit aucune table métier et n'ajoute aucune permission.
5. Le Web et Flutter reçoivent le même PDF serveur ; PDF enregistre, Partager remet le PDF ou le lien public quand autorisé.

Un QR vérifie **l'émission d'un document identifié**, non la véracité de toute affirmation, ni un accès implicite aux coordonnées privées. Une variante personnalisée ne rend pas son contenu public.

## Principes de mise en page

- A4 portrait, surface utile ~180 mm, pagination selon le volume réel.
- En-tête institutionnel avec le Makolo Mark officiel et titre « Passeport Makolo ».
- Bloc d'identité violet avec portrait carré cover, orientation EXIF corrigée et monogramme sobre si aucun portrait autorisé.
- Localisations lisibles (pays en français, y compris les valeurs historiques RDC et le code CD).
- Bio et faits personnels séparés des déclarations, preuves et attestations. Pas de sections factices.
- Centres d'intérêt et ouvertures en pastilles imprimables ; liens cliquables.
- Faits établis, activités et attestations avec métadonnées réellement disponibles, sans sceaux inventés.
- Bloc de vérification sur la dernière page : QR, identifiant du snapshot, date UTC, variante, domaine de vérification.
- Couleurs Makolo #5232DB, #2B176E, #FAF7F5, encre #0F172A. Typographie Unicode embarquée lorsque disponible dans l'environnement, Helvetica de repli.

## Confidentialité

Le Passeport complet peut contenir des coordonnées privées, exclusivement lorsqu'il est généré pour son propriétaire ou une autorité explicitement autorisée. Les autres variantes n'héritent jamais de ces coordonnées ; aucune information n'est reprise implicitement d'un document, d'une preuve ou d'un Espace associé. Les projections de partage public et les autorisations de média restent propriétaires des décisions de divulgation.

## Vérifications ciblées

    python manage.py check
    python manage.py test sharing.test_passport_pdf_layout sharing.test_g6_passport core.test_z4_me_capital_api

Inspecter visuellement tous les feuillets des cas : identité sans photo, portrait EXIF 6, profil succinct, biographie longue, nombreux intérêts, preuves/attestations, Passeport public et Passeport d'Espace. Vérifier l'extraction du texte français, la lisibilité N&B et le QR sur le fichier final. Ne pas fusionner avec CI rouge ; aucune fusion automatique de #522.
