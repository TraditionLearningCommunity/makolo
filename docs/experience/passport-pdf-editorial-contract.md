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
- Bloc d'identité violet en **trois territoires** : portrait carré à gauche, identité naturelle au centre (nom complet sans étiquette Prénom/Nom, profession, lieu et identifiant), **QR de vérification à droite sur fond blanc** et avec zone calme pour la lecture optique. Orientation EXIF corrigée ; monogramme uniquement si aucun portrait autorisé.
- La langue et le genre ne figurent dans cette zone que lorsqu'ils sont renseignés et présents dans la variante complète autorisée. Aucun « Non renseigné », aucune identité reconstruite artificiellement.
- Localisations lisibles (pays en français, y compris les valeurs historiques RDC et le code CD).
- Les informations complémentaires réellement présentes (contact, organisation, date de naissance si autorisée) restent dans une section discrète ; ni tableau redondant Prénom/Nom, ni colonne vide pour un élément unique.
- Bio et faits personnels séparés des déclarations, preuves et attestations. Pas de sections factices.
- Centres d'intérêt et ouvertures en pastilles imprimables ; liens cliquables.
- Faits établis, activités et attestations avec métadonnées réellement disponibles, sans sceaux inventés.
- Bloc de référence **en bas de la dernière page**, distinct du QR de la première page : « Vérifier ce document », identifiant du snapshot, date UTC d'émission, variante et domaine réel d'émission lié au token signé. Le QR n'est **pas répété** au pied du document.
- Le QR renvoie à la vérification de **ce snapshot émis**, pas à un passeport public recomposé. Sur une installation locale, le domaine peut être 127.0.0.1 et ne pas être accessible depuis un autre appareil ; ne jamais inventer un domaine de production.
- Couleurs Makolo #5232DB, #2B176E, #FAF7F5, encre #0F172A. Typographie Unicode embarquée lorsque disponible dans l'environnement, Helvetica de repli.

## Composition du parcours (étape 3)

Le Passeport combine l'identité et un parcours d'action fondé sur les faits existants : activités portées (publication ≠ réalisation), Proofs établis par Makolo, Credential Trust reçus d'un émetteur, vérifications admises, et attestations émises par l'Espace sous forme de résumé sans bénéficiaires.

Le Passeport **complet** d'un Profil ajoute, depuis les domaines propriétaires, ses appartenances actives aux Équipes et ses Mandates Espace actifs, sous des rubriques distinctes : appartenance ≠ autorité. Les variantes public, thématique et personnalisée ne reçoivent pas ces relations internes automatiquement.

Le Passeport complet d'un Espace peut présenter les noms de ses Équipes actives **seulement** si la personne consultante possède la permission de gestion des équipes de cet Espace. Un simple accès à l'Espace ne suffit pas. Les sorties Web, API personnelle/Flutter et PDF rendent uniquement les faits admis par la projection propriétaire ; le PDF n'infère aucune relation.

Aucune nouvelle source de vérité, table, inférence de compétence, score ou CV RH générique n'est introduite.

## Variantes, sélection et divulgation (étape 4)

- **Public** : représentation en lecture directe de l'identifiant public, admise uniquement si la publication de l'entité est autorisée ; le réglage `searchable` ne contrôle pas l'accès par lien. La personne propriétaire peut toujours consulter l'aperçu de sa propre version publique, même si elle ne l'a pas publiée.
- **Complet** : version propriétaire du Profil, ou version réservée à une autorité disposant du droit de consulter le workspace de l'Espace. Les noms des Équipes internes restent soumis à une autorité de gestion d'équipe indépendante du droit de consultation.
- **Thématique** : composition des faits du titulaire liés à un ou plusieurs Topics explicitement demandés ; cette variante reste **privée** tant que le titulaire n'a pas volontairement exporté son document. Elle ne transforme pas une preuve privée en déclaration publiquement accessible.
- **Personnalisé** : l'identité minimale (nom et identifiant) subsiste, mais la photo, la biographie, la profession, la localisation, les liens, les centres d'intérêt, les ouvertures et les faits sélectionnables ne sont transmis que s'ils sont explicitement inclus. Une sélection vide produit un Passeport d'identité minimal. Une sélection de fait étranger est rejetée par le serveur.
- **Adresse canonique `/<identifiant>/`** : un visiteur ne peut obtenir que le public autorisé. Un utilisateur reconnu comme titulaire peut consulter les variantes privées par cette même adresse ; il ne transmet jamais cette autorisation aux autres visiteurs.
- **Web personnalisé** : aperçu limité aux informations choisies ; `Modifier la sélection` ouvre séparément la liste privée des choix admissibles avec cases conservées. Les documents exportés n'intègrent jamais ce catalogue.
- **Flutter** : aucun élément privé n'est présélectionné lors de la création d'une variante personnalisée ; partage et PDF exigent une projection en ligne à nouveau autorisée. Le propriétaire doit être averti lorsqu'il transmet un document susceptible de contenir des informations privées.
- **Document vérifiable** : la page du lien signé confirme l'émission et expose seulement les références de vérification ; elle ne diffuse pas le contenu privé de la projection. La vérification historique et les versions datées sont traitées à l'étape 5.

Les variantes ne dupliquent aucune vérité métier, n'ajoutent aucune permission et ne rendent jamais un contenu public par simple composition.

## Confidentialité

Le Passeport complet peut contenir des coordonnées privées, exclusivement lorsqu'il est généré pour son propriétaire ou une autorité explicitement autorisée. Les autres variantes n'héritent jamais de ces coordonnées ; aucune information n'est reprise implicitement d'un document, d'une preuve ou d'un Espace associé. Les projections de partage public et les autorisations de média restent propriétaires des décisions de divulgation.

## Vérifications ciblées

    python manage.py check
    python manage.py test sharing.test_passport_pdf_layout sharing.test_g6_passport core.test_z4_me_capital_api

Inspecter visuellement tous les feuillets des cas : identité sans photo, portrait EXIF 6, profil succinct, biographie longue, nombreux intérêts, preuves/attestations, Passeport public et Passeport d'Espace. Vérifier l'extraction du texte français, la lisibilité N&B et le QR sur le fichier final. Ne pas fusionner avec CI rouge ; aucune fusion automatique de #522.
