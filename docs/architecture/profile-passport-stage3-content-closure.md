# Passeport Makolo personnel — fermeture de contenu (étape 3)

**Portée :** Projection du Profil personnel, Web / API / Flutter / PDF.
**Statut :** contrat de réalisation proposé sur une branche empilée sur la PR #522 ; **non fusionné dans main**.
**Référence :** `docs/ux/Makolo_UX_Moi_Identite_Capital_Personnel_Contrat_Consolide_2026-10-08.md`, `docs/architecture/makolo-domain-blueprint.md`, `docs/architecture/profile-relevance-action-network.md`, `docs/architecture/profile-passport-visibility.md`, `docs/experience/passport-pdf-editorial-contract.md`.

## 1. Fonction et frontière

Le Passeport représente les faits existants qui facilitent une action réelle. Ce n'est **ni** une identité civile certifiée, **ni** un CV universel, **ni** un réseau social, **ni** un lieu où saisir ou stocker une deuxième vérité métier.

```text
Faits des propriétaires canoniques
  + admission métier
  + visibilité effectivement autorisée
  + sélection éventuelle
  = projection Passeport du lecteur
```

Aucune sélection ne transforme un droit de consultation en Mandate, Permission, Access ou Payment. Une information absente ne doit jamais être inventée pour remplir la mise en page.

## 2. Contenu du Passeport personnel

| Rubrique UX | Propriétaire | Critère d'admission |
|---|---|---|
| Identité | Accounts / PublicIdentifier | identifiant stable ; nom et portrait seulement si divulgués |
| Présentation | Accounts / UserProfile | bio, profession, entreprise et organisation *renseignées* ; pas d'affiliation attestée par défaut |
| Localisation générale | UserProfile | ville / pays séparément autorisés ; pas d'adresse ni de coordonnées fines |
| Liens | Accounts | liens renseignés et divulgués |
| Intérêts | Topics / ProfileInterest | déclaration explicite, Topic actif, visibilité de l'élément |
| Ouvert à | Topics / ProfileOpenTo | déclaration explicite **active**, Topic lié s'il existe ; indépendant des Interests |
| Activités portées | Activity | propriétaire Profile ; états `PUBLISHED`, `COMPLETED`, `ARCHIVED` ; jamais brouillon |
| Faits établis | Trust / Proof | preuve `ACTIVE`, appartenance au Profil, protection de l'Activity source |
| Attestations reçues | Trust / Credential | détenteur Profil, statut réel, contexte source autorisé ; une révocation n'est jamais présentée comme valide |
| Équipes, Groupes | Membership et propriétaires correspondants | relation actuelle et Groupe actif (`status=ACTIVE`), seulement vue `complete` du titulaire ; Groupe archivé = historique chez son propriétaire |
| Espaces accessibles | Organizations / permissions existantes | accès effectif ; ne signifie pas Membership |
| Mandats actifs | Authorization / Mandate | autorité actuelle dans une portée explicite ; ne signifie pas TeamMembership |
| Coordonnées personnelles | Accounts | seulement `complete` propriétaire, jamais autres variantes par héritage |

Le Passeport Complet est exhaustif **dans ce périmètre**, pas un export de tout le compte. Veilles, favoris, Journeys en cours, documents privés, secrets, AccessCredentials, détails de paiement et autres données opérationnelles ne sont pas importés implicitement.

## 3. Quatre variantes, une seule projection source

- **Complet :** titulaire authentifié, identité et capital représentable, plus relations/coordonnées owner-only. Les informations privées restent régies par leur domaine.
- **Public :** uniquement les faits divulguables selon les règles d'admission et de publication ; `public_profile` n'implique pas `searchable` et inversement.
- **Thématique :** sélection explicite de Topics pertinents parmi les Interests, Open to actifs, Activities, Proofs actives et Credentials réellement représentables. La projection thématique reste privée tant qu'un partage autorisé distinct n'a pas été établi. Elle ne fabrique aucune nouvelle compétence.
- **Personnalisé :** sélection bornée de sections et d'éléments appartenant au titulaire ; refus des IDs étrangers, aucun fait personnel privé présélectionné. L'identifiant minimal subsiste.

Le choix d'un Topic ne signifie pas « je possède une compétence ». Un `Open to` n'est pas un `Interest`, et doit néanmoins proposer son thème dans le sélecteur, même lorsqu'il est le seul fait disponible sur ce thème. **Web et Flutter affichent le libellé de l'ouverture ET son Topic facultatif**, pour distinguer « Mentorat · Géométrie » de « Mentorat · Recherche ».

## 4. Langage et provenance

- Faits déclarés : libellés naturels « À propos », « Profession », « Intérêts », « Ouvert à » ; pas de badge « Déclaré » répété.
- Activity publiée : « activité publiée », pas « participation réussie ».
- Proof active : « fait établi », avec contexte et date lorsqu'ils existent.
- Credential délivré : « attestation », avec émetteur et statut.
- Team / Group : appartenance, jamais autorité implicite. Mandate : autorité située, jamais qualification globale.
- QR documentaire : atteste l'émission d'une version, pas la vérité de toutes les déclarations.

## 5. Comportement Web / Flutter / PDF

L'API `personal.me.passport`, les vues Web et le PDF utilisent les mêmes faits canoniques. Flutter ne doit jamais inventer des champs absents du serveur. Les variantes `thematic` et `custom` doivent préserver la sélection lors du retour et ne pas afficher un contenu d'une autre variante depuis un cache. Les changements d'audience demandent une réévaluation côté serveur. Une édition de Profil modifie son propriétaire réel, pas une copie stockée dans Sharing.

Une section sans valeur est omise ou remplacée par une aide d'édition contextualisée réservée au titulaire. Ne pas remplir artificiellement les espaces ni transformer Moi en tableau de bord.

## 6. Critères de validation

- [x] Pas de nouveau modèle, migration ni source de vérité : composition par `sharing/passport.py`.
- [x] Sélection des thèmes `Open to` actifs même sans Interest ou Activity associés.
- [x] Une Proof révoquée seule ne rend pas artificiellement son Topic disponible.
- [x] Groupes archivés omis de la projection des affiliations actuelles, sans toucher à leur historique canonique.
- [x] Quatre tests ciblés ajoutés dans `sharing/test_passport_stage3_content.py`.
- [x] Le client Flutter conserve le contexte Topic d'Open To et dispose d'un test widget dédié dans `mobile/test/me_passport_stage3_content_test.dart`.
- [ ] Exécuter `python manage.py test sharing.test_passport_stage3_content sharing.test_g6_passport`.
- [ ] Exécuter `python manage.py check` et `python manage.py makemigrations --check --dry-run`.
- [ ] Exécuter `flutter test test/me_passport_stage3_content_test.dart` et `flutter analyze` depuis `mobile/`.
- [ ] Vérifier les autres tests de projection propriétaire, le rendu Web/Flutter/PDF et les CI sur le HEAD à intégrer.
- [ ] Réconcilier avec la PR #522 puis vérifier `main` après fusion ; **aucune fusion avec CI rouge**.

## 7. Hors de l'étape 3 : transmettre à l'étape 4

Les audiences fines, le défaut de consentement des nouveaux Interests / Open to, la sémantique exacte de « Mes collectifs », les vues « Voir comme » et la révocation des partages/historiques restent régis par leurs propriétaires et par le chantier de confidentialité. **Sur #522, les nouveaux Interests/Open to passent de privé par défaut (`main`) à public par défaut : ne pas traiter ce changement comme implicitement validé.** Toute correction doit être évaluée avec les tests et migrations concernés.

**Promesse :** « Makolo marche pour vous. » Le Passeport présente ce qui est déjà utile pour avancer.


## Addendum de mise en œuvre — 3 novembre 2026 / Flutter, PR #522

Cet addendum remplace **pour le client personnel Flutter** les anciennes décisions
d'aperçu personnalisé minimal et de recalcul serveur de chaque variante.

- La lecture privée du titulaire `/api/v1/me/passport/?variant=complete`
  renvoie une projection source avec une enveloppe `composition.schema_version=1`,
  une identité publique admise et les identifiants publics admis pour chaque
  famille de faits. Le cache reste personnel, remplaçable et purgé sur refus.
- Flutter compose Complet, Public, Thématique et Personnalisé depuis ce seul
  chargement. Les thèmes des déclarations et les classifications Activity sont
  transmis dans la projection personnelle ; aucun client ne réinterprète les
  droits des domaines.
- Public = faits admis publiquement ; Thématique = même socle général autorisé,
  filtrage des faits thématisables ; Personnalisé = socle public dont la
  personne retire explicitement des éléments. Le protocole natif envoie
  `exclude`, `exclude_activity`, `exclude_proof`, `exclude_credential`
  à l'émission. L'API conserve la compatibilité des sélections `include`
  historiques sur Web.
- L'émission, l'intégrité du snapshot, l'empreinte et les droits sont de la
  responsabilité du serveur. Un lecteur tiers ne reçoit jamais la projection
  complète du titulaire.
- Les implications confirmées `ActivityInvolvement` sont représentées comme
  expériences avec titre, fonctions et date d'Occurrence si connue.
  Ni un Journey ni une réservation n'infère une participation.
- Les données personnelles manquantes peuvent être indiquées sobrement à
  leur titulaire dans Flutter ; aucune section vide n'est imprimée.
- Les relations internes Membership/Mandate/Access restent owner-only sans
  autorisation explicite de divulgation propre à leur domaine. Une projection
  ne fait pas naître un droit collectif.
- L'édition du Profil relevait d'un chantier distinct lors de cet addendum.
  Elle a ensuite été intégrée à #522 via le même propriétaire Accounts,
  sans modèle `PassportEditor` parallèle.

**Qualité non attestée :** les modifications ont été poussées sur #522, mais
la suite Django, le formatage et les tests Flutter/Android sont à exécuter avant
une éventuelle fusion. La PR reste non fusionnée.


## Rectification de composition et de l'éditeur — 3 novembre 2026

- La propriété privée `private_details` est réservée au propriétaire de
  Complet. Les autres variantes transportent `presentation_details`,
  liste bornée par la visibilité de chaque fait ; Flutter expose cette
  présentation comme `personal_details`, sans réutiliser le conteneur privé.
- L'audience de `name` contrôle le prénom et le nom, sans cacher
  l'identifiant public. `city` et `country` sont indépendants.
  Les coordonnées sensibles (téléphone, adresse, naissance) ne sont pas
  rendues publiques implicitement.
- Une émission conserve dans le snapshot la même sélection autorisée ;
  la consultation publique historique réévalue les retraits d'audience.
- Les variantes restent des suppressions sur un seul socle local.
  Aucun chargement serveur supplémentaire n'est introduit par le changement
  d'onglet en lui-même.
- L'édition du Profil est réorganisée en groupes naturels, affiche
  l'e-mail sans le modifier, et utilise `auth/identifier/` pour un
  éventuel changement d'identifiant, soumis aux règles Accounts.
- Le menu de partage courant contient quatre options. L'ancien document
  relève exclusivement de la page Versions.

Les tests ajoutés décrivent ces contrats. Leur exécution et la vérification
sur appareil restent nécessaires avant une éventuelle fusion.
