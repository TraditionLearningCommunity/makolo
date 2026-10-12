# Mature Mobile Experience — reprise Codex

## Contrat de reprise

- Objectif : fermer les écarts réels des contrats de préparation, depuis le checkpoint Antigravity, sans reconstruire les surfaces déjà modifiées.
- Owner : Codex, intégrateur unique.
- Base : `0366d81203ee06937427f055d4d31f905172f849`, neuf commits depuis `f2351b8b5db1ce362b7ddc6ca2951d9d79ce2538`.
- Branche : `feature/mature-mobile-composition` ; `origin/main` encore à la base au démarrage ; aucune PR ouverte (API GitHub).
- Surfaces : projections Organizations, Presentation/Flutter Space, routes propriétaires, tests ciblés, références Now et leur gate CI existant, documentation de convergence.
- Interdits : modèles/tables/migrations, nouvelle autorité, données inventées, refonte du thème/sync, modification de main, push intermédiaire, merge automatique.
- Acceptation : profondeurs réellement accessibles et revalidées, provenance/limites visibles dans Piloter, relations distinctes, absence/fraîcheur/révocation honnêtes, contrats compatibles.
- Évidence : tests Django d'autorisation/sélection et Flutter de navigation/présentation/acteur ; formateur canonique, analyse, Goldens pertinents et gates finaux.
- Gate : validation locale puis push final unique, PR et CI verte ; aucun merge automatique.

## A — Space Now / Découvrir

`space_attention_projection.py`, `workspace_projection.py`, `space_work_projection.py` et les tests ZS6 distinguent visibilité du portefeuille et sélection attentionnelle. Les permissions autorisent la lecture des objets, mais ne définissent ni pertinence collective, ni pourquoi maintenant, ni prochain mouvement, ni admission de possibilités pour un Space. Le selector personnel Discovery ne porte pas ce contexte collectif.

La composition du portefeuille Métier ne peut donc pas devenir une sélection Now/Discover par renommage. `selection.unavailable / no_safe_selection_contract` reste conservé, avec `items=[]` ; ce n'est pas une preuve de calme ou de champ vide. Le blocage précis est l'absence d'une politique de sélection collective établie, scopée par mandat/perspective, portant les raisons et les destinations autorisées. Aucun modèle ni politique métier n'est inventé pour la contourner.

## B–D — écarts confirmés

- Métier : les huit grammaires existent côté serveur ; les cartes enrichies d'Antigravity sont conservées. Les liens d'approfondissement restent absents de l'interface hors Jour J ; les collections bornées doivent afficher leur couverture.
- Relations : recherche/sélection propriétaire existent ; Flutter aplatit les owners et ne permet pas d'approfondissement. Ne pas fusionner deux relations vers un même Profil.
- Piloter : le serveur livre preuves, raison, incertitude, couverture et date ; Flutter ne montre que titre/résumé et clés techniques des mesures.
- Transversal : `SpaceRetrievalOwnerScreen` existe mais sa destination n'est pas montée dans le router ; fermeture nécessaire à la recherche/historique et aux handoffs Métier/Relations.

La validation visuelle sur appareil n'est pas attestée par le transfert.

## Checkpoints vérifiés

- Projections Métier : sélection par identité avant les limites d'aperçu, avec les mêmes selectors et permissions ; pagination par section (20 éléments), offset borné ; refus des identités étrangères/malformées et des sections non visibles. Une lentille Activity n'expose pas les routes/véhicules collectifs. Les lieux et arrêts viennent des relations Geography/Transport existantes, avec prefetch.
- Profondeurs Flutter : destination propriétaire Space montée pour Métier, Recherche, Historique et Relations ; relecture serveur avec responsabilité courante. Les liens Activity et Jour J restent distincts. Présentation MPS d'une Activity revalidée avant utilisation ; échec explicite, sans ancien artifact affiché après refus.
- Images MPS : le renderer consomme désormais le binding réel, au lieu d'une icône systématique. Représentations HTTP(S) de même origine uniquement, sans en-tête bearer ni cache disque supplémentaire ; alternative textuelle, chargement, erreur et retry ; image décodée évincée au démontage/changement de portée. Les médias absents ne créent pas de cadre orphelin. Tests de résolution/origine et d'erreur récupérable ajoutés.
- Continuation Métier : pages éphémères, sans nouveau store/sync ; retry au même offset, déduplication par identité propriétaire, contenu conservé sur erreur technique et retiré sur refus/changement d'acteur.
- Piloter : signaux avant mesures ; preuve, source, date, couverture bornée, raison et incertitude visibles. Zéro, inconnu et données insuffisantes restent distincts ; montants par devise seulement avec capability financière. Aucun calcul de tendance/causalité inventé.
- Relations : propriétaires conservés séparément, même si un Profil apparaît plusieurs fois ; aperçu et recherche distante distingués, résultats tardifs écartés, sélection revalidée au détail.
- Snapshot : SourceState, fraîcheur et date d'observation utilisés sur les racines et insights ; refus/révocation distincts du vide métier, snapshot expiré non exposé.
- Convergence : destination personnelle des commandes raccordée à l'écran propriétaire déjà présent ; corrections des contrôles null impossibles dans les commits repris, sans supprimer leurs comportements.

Le premier checkpoint de formatage a appelé par erreur le binaire direct Dart 3.11.5 du SDK cassé `C:/src/flutter`, malgré son lanceur redirigé vers 3.13.3. L'appel corrigé passe par le SDK actif `C:/src/flutter_3473` (Flutter 3.47.3 / Dart 3.13.3). Les modifications de formatage étrangères au chantier ont été annulées par le vrai formateur, sans reset et sans modifier les neuf commits repris.

Validation intermédiaire : 113 tests Django (Space ZS3/ZS4/ZS6, History/Search Space, contrats personnels Z1/Z2/Z4/Z5/Z6) et 485 tests Flutter hors Goldens réussis. Vérification de migrations : aucune modification détectée. Contrat OpenAPI : 12 opérations requises conservées ; 8 fixtures C0 valides.

## Matrice de convergence des contrats

Les contrats de données personnels et leurs consolidations restent rattachés aux mêmes surfaces ci-dessous. Ce registre reprend le transfert et ferme les écarts confirmés ; il ne transforme pas une cible documentaire en fonctionnalité existante.

| Contrat / famille | Propriétaires et profondeur | Résultat de reprise |
|---|---|---|
| Now, S1–S5, données Now | `now_presentation.dart`, `now_screen.dart`, projections Core | Neuf commits conservés ; conséquence et dominance Presentation présentes ; contrôles d'analyse corrigés ; références S1–S5 actualisées pour le rendu réel. |
| Découvrir, données Découvrir/Me | Discovery selector/repository, `discovery_mature_view.dart` | Métadonnées et focus conservés ; bookmark affiché pour une capacité ou un état enregistré, pas pour `unknown` ; suites ciblées vertes. |
| En cours, données Ongoing/Me | Personal projections, `ongoing_screen.dart` | Dimensions et profondeurs existantes conservées ; tests de continuité et suite Flutter complète. |
| Moi/Nous, leurs cadres et données | Me projection, `me_screen.dart`, Space Us et Nous depths | Passeport interactif conservé ; callbacks typés corrigés ; Team/Group/Mandate restent séparés. |
| Space Now/Découvrir, cadre et données | `space_attention_projection.py`, Space repository/root | `unavailable` conservé pour le blocage A précis ; aucun faux calme, y compris source inconnue/partielle. |
| Métier Activités / Generic | Work + Activity/Occurrence | Sélection, continuation, identité, horaires/lieu, Activity liée et Jour J propriétaire ; aucune activité synthétique. |
| Métier Commerce | Work + Offer / CommerceOrder | Offre et commande restent séparées ; prix unitaire et devise de l'Offer lisibles, sans exposer un état Payment ; détail commande relu par Commerce. |
| Métier Créations / Creative | Work + Activity + MPS | Grammaire Créations conservée ; présentation matérielle autorisée accessible à la profondeur Activity, sans CreationModel ni image fictive. |
| Métier Initiatives / Community | Work + Activity / groupes propriétaires | Grammaire Initiatives conservée ; contexte et relations réellement visibles, sans métrique d'impact/autorité inventée. |
| Métier Prestations | Work + Offer / service Journeys | Offre distincte du dossier ; facet progressive et blocages uniquement sur Journey ; détails revalidés par les selectors Services existants. |
| Métier Productions / Media | Work + Activity + MPS | Production reste l'Activity ; média lié au contexte MPS, sans feed ni fichier transformé en production. |
| Métier Programmes / Education | Work + Activity / Occurrence / registration Journey | Programme, session et parcours gardent leurs identités et relations ; pas de Programme ORM ni écran spécialisé artificiel. |
| Métier Transport | Work + Route / Vehicle / Occurrence + Geography | Structure distincte des départs ; arrêts/lieu et places véhicule explicites ; Activity/Jour J séparés ; lentille Activity sans structure globale. |
| Piloter | Analytics projection, `SpacePilotSurface` | Preuves, portée, fraîcheur, lacunes et incertitudes rendues ; aucune tendance/causalité ni capacité financière déduite. |
| Personnes et relations | Team / Groups / CRM / Audiences / Partners | Sections distinctes, recherche distante bornée et profondeur owner-scoped ; aucun UniversalPerson ni fusion par nom. |
| Historique / Recherche transverse | History/Search projections + owner screens | Reconnaissance conservée ; destinations Space montées, commande personnelle montée ; caches personnels/collectifs distincts. |
| Mes Accès | Access collection/detail/credential | Badges et bénéficiaire conservés ; profondeur réelle existante ; aucun credential ajouté aux collections ; tests Z6 et Flutter. |
| Démarche/Journey | Journey detail et owner repositories | Owners, Readiness, paiements, ressources et questionnaires conservés ; tests Z5 et suite Flutter. |
| Requirements/Readiness | Requirement detail et selectors Readiness | Pas de nouveau statut/persistance ; contrats propriétaires conservés, tests Z5 et Flutter. |
| Préparation / ressources contextuelles | Preparation et Resource details | Aucun document assimilé à une exigence satisfaite ; propriétaires et transferts conservés, suite Flutter complète. |
| Forms / Questionnaires | Questionnaire reference depth / submit coordinator | Profondeurs et récupération existantes conservées, suite Flutter complète ; aucune mutation nouvelle. |
| Jour J / Makolo Live | Occurrence owner projections et routes opérateur | Handoff `open_day_of` serveur conservé ; aucun checkpoint assimilé à JourneyStep ; suite Flutter complète. |
| Makolo Mark | Mark owner/repository/routes | Routage acteur conservé ; aucune ingestion ou autorité nouvelle, suite Flutter complète. |
| Notifications | Push/router et récupération de session | Destinations propriétaires conservées ; suite Flutter complète, aucun payload privé ajouté. |
| Maître surfaces personnelles / expérience transversale / Behavior | Owners, selectors, adapter et design system existants | Pas de thème ou sync parallèle ; absence, erreur, snapshot, révocation, acteur, navigation et grandes polices vérifiés sur les changements. |

Limites assumées : aucune mutation opérateur nouvelle ni formulaire Flutter inventé pour une capability dont le propriétaire n'a pas de flow mobile existant. Une capability ne devient jamais un bouton décoratif. Aucun émulateur/appareil n'a été utilisé ; la validation sur appareil n'est pas effectuée.

Contrat API additionnel compatible : `work/?kind=<source.kind>&id=<source.id>` retourne `selection` (0..1, mêmes selectors que la collection, filtrage avant limite). `work/?section=<clé visible>&offset=<0..10000>` retourne une seule section, `page.offset`, `page.limit=20` et `has_more` ; section non visible = 404, offset invalide = 400. Sans ces paramètres, les sections racine restent inchangées ; les nouvelles clés sont additives. Le prix d'une Offer est une chaîne décimale et une devise séparées, sous la permission Commerce déjà exigée ; aucun état Payment n'est ajouté.

Goldens : les références Now ont été rendues et examinées sur Windows avec Flutter 3.47.3. S5 inclut désormais la conséquence déjà implémentée dans le checkpoint Antigravity. Les contrôles visuels généraux présentent un écart de rasterisation avec les hashes Ubuntu approuvés ; leur manifeste n'a pas été modifié. Le workflow Now existant devient un gate PR en lecture seule, avec artifacts de comparaison ; il ne commit/push plus automatiquement sur une ancienne branche. La vérification Ubuntu de la PR reste le gate canonique.

Self-review (`ai-development-guardrails.md`) : propriétaires et permissions réutilisés ; lecture seule pour les nouveaux parcours ; retry explicite ; aucune outbox/pending inventée ; identités/acteurs contrôlés et réponses tardives écartées ; aucun modèle/migration/dependency nouveau ; tests non affaiblis ; absence de secrets dans le diff vérifiée avant publication. La qualité sur appareil et le selector collectif Space attentionnel restent des limites explicites, pas des validations prétendues.

## Validation finale locale et CI

- Suite finale Flutter après rendu média : 487 tests hors Goldens, tous verts ; analyse sans avertissement et formateur Dart 3.13.3 au vert.
- Django : 113 tests de convergence puis 20 tests Métier après ajout du prix de l’Offer, tous verts ; aucune migration détectée ; contrats OpenAPI/C0 préservés.
- PR unique : #518, sans merge automatique. Mobile CI, CI générale, API Contract, sécurité, contrôles visuels généraux, Android Build et suites PostgreSQL sont verts sur le premier HEAD publié.
- Le premier gate Now a révélé une préparation CI manquante (sources générées absentes). La génération build_runner et la vérification de sa politique sont ajoutées comme dans Mobile CI ; les assertions Golden restent strictes.

- Correction Golden canonique : les 20 scénarios ont été rendus avec succès sur Ubuntu/Flutter 3.47.3 dans le run `38243330011`, HEAD `5b536c258174bf1c101d9de9bd19ead1d3a9d8b9`. Les 20 PNG de l’artifact `11743962104` remplacent les références Windows après inspection. Seule la rasterisation diffère entre ces environnements ; la conséquence S5 et les assertions restent conservées. Les références versionnées sont désormais celles du runner canonique, pas celles du poste Windows.
