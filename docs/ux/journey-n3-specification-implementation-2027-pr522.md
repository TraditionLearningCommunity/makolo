# Makolo — Démarche N3 : spécification d'implémentation 2027

**Date :** 14 novembre 2026  
**Dépôt :** TraditionLearningCommunity/makolo  
**PR et branche de réalisation :** #522 / fix/discover-a-continuation-context-20261014  
**Base inspectée pour cette spécification :** HEAD 898088144b94ee3dcfb50c565bfa3bd75e270d98  
**Statut :** directive de mise à jour UX, API, Flutter, Web, local-first et recette ; **pas** une certification d'implémentation.  
**Périmètre :** le N3 propriétaire Journey accessible depuis En cours, Moi/Mes démarches, Now, notifications et conversations. Ne pas refaire ces points d'entrée ni le N3 Découvrir.

## 0. Contrat de lecture, précédence et sources

- Les six visuels fournis le 14 novembre (capture actuelle + universelle + action/préparation + attente + terminée + Jour J) définissent **l'intention visuelle**, pas une fixture de vérité. Ne jamais reprendre leurs fausses dates, statuts, étapes, documents, QR, références, délais, codes et succès comme données produit.
- Contrat principal : Makolo_UX_Demarche_Journey_Contrat_Consolide_2026-10-09.md.
- Contrats associés : Requirements/Readiness, Preparation/Ressources, Forms/Questionnaires, Jour J/Live, Conversations, Mes accès, Historique, En cours, Moi/Nous et contrats serveur/client/Presentation des 9-10 octobre.
- Vérifications de réalité : AGENTS.md, README.md, mobile/README.md, docs/architecture/, docs/ux/, routes, projection API, selectors, stores et tests sur #522, puis comparaison avec le HEAD actuel de main avant toute modification.
- Priorité : **invariants métier > vérité effective du code et des propriétaires > contrats de présentation > maquettes**. Toute divergence importante doit être diagnostiquée ; ne pas la masquer par des libellés.
- Cette spécification peut être amendée après recette, sans faire de la Presentation une nouvelle autorité métier.

## 1. Décision produit absolue

**Une seule racine Démarche N3, avec une composition universelle et plusieurs situations contextuelles.** Pas cinq pages et pas cinq copies de JourneyDetailScreen.

La personne doit comprendre sans effort : quel objectif, quelle situation, quel mouvement possible, ce qui dépend d'un tiers, ce qui est confirmé, ce qui aide, quelle profondeur ouvrir, et ce qu'elle a obtenu.

**À faire :** information densifiée, visuelle, calme, utile, orientée action ; icône et quelques mots ; présent avant passé ; ressources selon leur nature ; contenu local disponible immédiatement.

**À bannir :** page comme livre, cartes empilées pour chaque champ, titres dupliqués, compteurs décoratifs, timeline inventée, jargon technique, message de connectivité répétitif, faux succès, faux blocage, instruction non cliquable ressemblant à un bouton, répétition de date/lieu/heure, interface calquée sur des modèles Django, tutoriels intégrés.

La forme peut se rapprocher en finition des applications grand public, **sans** transformer Makolo en réseau social ni chercher à retenir l'utilisateur artificiellement.

## 2. Socle universel — défini par la sémantique, pas par des blocs toujours visibles

Pour toute Journey autorisée et connue :

1. **Identité :** objectif canonique, titre humain (fallback localisé), nature du parcours seulement si elle clarifie.
2. **Situation :** état owner Journey humanisé ; ne pas inférer « réussi », « en attente », « bloqué » uniquement du temps ou d'une couleur.
3. **Mouvement :** action principale confirmée, plusieurs choix, attente explicite, obstacle confirmé, résultat réel, ou absence de mouvement ; une seule logique de priorité.
4. **Accès aux profondeurs :** seulement les handoffs vérifiés et réellement utiles.
5. **Continuité :** lecture et navigation en respectant le Profil actif, les informations privées locales, les refus et le retour.

**Conditionnels même dans la couverture :** date, heure, ville, Jour ±N, conversation, image, organisateur, référence. Une Journey sans Occurrence n'a pas un faux Jour J ; une Journey sans Conversation n'a pas une icône factice. Un écran avec peu de données doit rester élégant **sans contenants vides**.

## 3. N3 — hiérarchie visuelle et ordre adaptatif

Structure composable, pas liste rigide :

1. **Couverture pleine largeur** : objectif, état, repère temporel et contexte court, conversation contextuelle si réellement accessible.
2. **Situation dominante** : prochaine action, choix, attente, blocage ou résultat ; si rien à dire/faire, cette surface disparaît.
3. **Préparation utile** : Requirements, Forms, vrais points Readiness, ou étapes du parcours selon importance. Ne pas répéter la prochaine action.
4. **Ressources** : mini-aperçu typé et profondeur complète, si liste connue non vide ou collection explicitement accessible.
5. **Repères complémentaires** : consigne d'entrée, salle, rendez-vous, contact, échéance ou notice réellement distincte de la couverture.
6. **Mes engagements** : Access, Payment, Commerce, Capacity/Waitlist, réservation, documents/pièces propres au parcours, lorsque projetés.
7. **Mon parcours** : JourneySteps réels, si utiles, en timeline compacte ou structure de branches selon le graphe réel ; jamais étape synthétique.
8. **Historique significatif** : aperçu de transitions owners et lien « Voir tout » si une profondeur réelle existe.
9. **Contexte secondaire** : Activity/Occurrence/Dossier/Projet seulement s'ils apportent une profondeur utile, sans doubler le titre ou le calendrier.

Cette composition **remonte** l'obstacle/action urgent devant les documents, **remonte** le résultat durable après accomplissement, **remonte** Jour J quand l'Occurrence est actuelle et admissible. Les autres éléments se replient ou s'effacent. Le parcours n'est pas une checklist universelle.

## 4. Couverture — spécification pixel-comportement

**À faire**

- AppBar simple : retour, « Démarche » ou vocabulaire propriétaire clair, actualisation éventuellement en action secondaire, aucun bouton Conversation dans l'AppBar.
- Couverture Makolo **pleine largeur disponible** sous l'AppBar ; pas de seconde marge horizontale autour de la couverture. La couverture est un ensemble, pas une carte blanche à l'intérieur d'une carte blanche. Rayon inférieur cohérent avec le design system.
- Icône d'**objectif/cible** ; jamais passeport, badge d'accès ni check de réussite pour symboliser l'objectif universel.
- Titre véritable, lisible, deux à quatre lignes selon longueur ; le texte ne coupe pas arbitrairement l'objectif.
- Statut compact en mots simples ; icône conversation tactile à l'intérieur de la couverture si ConversationContextAction autorisée, avec tooltip/semantic label « Conversation de cette démarche ».
- Répéter ni la catégorie « Échange » ni la description « [titre] — engagé ». Une description ne s'affiche que si elle **ajoute** des informations utiles ; ne pas tronquer la phrase importante.
- **Date + plage horaire + lieu** présentés en une ligne si les dimensions le permettent, avec icônes calendrier/horloge/localisation ; sinon deux lignes propres selon largeur et grossissement. Priorité à la lisibilité, jamais compression illisible pour tenir artificiellement une ligne.
- Si début/fin même journée et connus : « 11h–14h » **une seule fois**. Si multi-jours : date/plage appropriées et fin distincte mais toujours dans le bloc temporel de la couverture. Si date seule : pas d'heure inventée.
- Ville et nom de lieu non répétés ; adresse détaillée sous forme d'info secondaire **dans la couverture** seulement si elle ajoute réellement quelque chose (ex. « Centre-ville » pour « Kampala »). Aucun double panneau « Adresse » ou « Fin prévue » plus bas.
- Repère temporel compact « Jour −24 », « Jour J » ou « Jour J +176 », situé près du temps. Avant/après le jour, **indicateur passif** qui ne ressemble pas à une action engagée ; « Jour J » devient action ouvrable seulement si l'owner confirme la permission/admission et la règle calendaire attendue.
- Pas de CTA secondaire « Ouvrir Jour J » répété plus bas. Makolo Live doit rester une profondeur d'Operations légitime, non un gadget permanent en tête.
- Couverture compatible fond clair et sombre, logos/images propriétaires autorisés seulement s'ils ajoutent quelque chose et ne remplacent pas la vérité.

**À ne pas faire**

- Ne pas ajouter une icône de document/passeport comme emblème de « Mon objectif ».
- Ne pas mettre le lieu à trois endroits ou afficher l'identifiant IANA « Africa/Lubumbashi ».
- Ne pas coder le statut « Aujourd'hui » selon la seule date d'un événement ; c'est une indication temporelle, pas un statut Journey.
- Ne pas dupliquer une couverture de visuel de maquette dans la Page de Découvrir : N3 Découvrir reste un chantier différent.

### Règles de compactage recommandées

- Couverture : 0 dp de marge latérale externe sur mobile ; padding interne recommandé 12–16 dp ; hauteur **intrinsèque**, jamais fixée.
- Contenus : marges latérales de référence 12–16 dp selon les composants existants ; espacement entre territoires typiquement 12–16 dp ; rows autour de 44–56 dp si tappables.
- Nom long : multi-lignes autorisées avec reflow ; pas de ligne forcée à 10 pt.
- Sur largeur ~320 dp : 2 lignes pour faits calendaires si nécessaire ; sur 360–430 dp : une ligne quand possible ; à texte agrandi : réorganisation accessible sans overflow.
- Ne pas introduire de deuxième barre réseau. La fine ligne système existante suffit.

## 5. Temps / Jour −N / Jour J / Jour J +N

- Source : **date civile de référence de l'Occurrence**, avec son fuseau IANA réel ; si la Journey a une échéance mais pas d'Occurrence, utiliser le vocabulaire « Échéance » et non « Jour J ».
- Calcul déterministe en jours civils dans le calendrier de l'Occurrence, non en tranches de 24 h UTC.
- Avant : Jour −245, Jour −16, Jour −2, Jour −1 ; jour même : Jour J ; après : Jour J +2, Jour J +176 ; aucune limite artificielle.
- Au changement de minuit de l'Occurrence, au retour de background et quand la projection locale change : recomposer ce seul repère sans fetch forcé ni boucle de rebuild.
- Fuseau absent/invalide ou date manquante : **ne pas inventer Jour J** ; montrer la date simple si valide, ou aucun repère.
- Un repère J+N ne marque ni Journey completed, ni Access used, ni Occurrence closed.
- La présence d'un lien « day_of » dans une projection ne suffit pas, à elle seule, à prouver une admission complète. Vérifier le contrat de l'owner Jour J/Operations et la capacité effective côté serveur avant de rendre le repère cliquable.
- **Politique UX demandée :** indicateur Jour ±N passif sauf sur Jour J avec droit et admission établis. Les autres points d'entrée légitimes de Jour J prévus par le contrat gelé continuent d'exister indépendamment.
- Jamais de QR, badge ou accès généré simplement parce que le compteur vaut zéro.

## 6. Situation actuelle — cinq familles, un seul emplacement dominant

**A. Action du Profile (maquette préparation/badge)**

- Afficher un message humain concret et **le bouton correspondant** à la capacité propriétaire : « Compléter mes informations », « Envoyer ma photo », « Répondre à l'invitation », « Régler le montant », « Choisir une date ».
- Ne pas afficher « Confirmer : [titre entier] » sans action reconnue.
- Action principale choisie selon priorité propriétaire, conséquence et échéance ; pas de décision fondée sur la longueur du libellé ou sur l'ordre arbitraire du JSON.
- Si plusieurs actions légitimes : montrer le choix, l'une peut dominer **si justifié**, toutes restent atteignables et distinctes.
- Si un lien propriétaire n'est pas reconnu par le routeur client : ne pas fabriquer un CTA qui ne fonctionne pas ; diagnostiquer le mapping et corriger la couverture route/owner.

**B. Attente (maquette candidature)**

- État « En attente » avec ce qui/qui est attendu si connu, éventuelle échéance **explicitement projetée** ; « rien à faire » uniquement si le propriétaire l'établit.
- Dossier/pièces et Conversation accessibles en entrées secondaires autorisées, sans second gros bouton Conversation lorsque l'icône existe déjà dans la couverture.
- Une attente n'est pas un blocage, n'augmente pas artificiellement la progression et n'autorise pas l'app à inventer « sous 7 jours ».

**C. Blocage / refus / incertitude**

- Blocage : conséquence concrète, qui peut agir, moyen autorisé, CTA owner ; couleur d'alerte seulement si le blocage est réel.
- Refus final : résultat refusé et motif uniquement si divulgable, sans CTA de reprise fictive.
- Inconnu : aucune fausse carte « en ordre », aucun refus inventé, aucune assimilation à blocage.
- Distinction explicite entre décision refusée, permission révoquée, action impossible et simple attente réseau.

**D. Jour J (maquette aujourd'hui)**

- Couverture compacte avec **Jour J** ; entrée vers profondeur Jour J uniquement si état temporel et admission métier vérifiés.
- Ne pas répéter un gros pavé « Jour J / Ouvrir Jour J » après l'en-tête ; l'information actuelle utile peut remonter comme micro-ligne « Entrée Hall B » ou « Salle Agora 2 » si réellement projetée.
- Si accès scannable existe : profondeur AccessCredential / Jour J sécurisée ; aucun QR sensible dans des tuiles de Resource ou dans la capture d'écran publique.
- Live : statut « prévu », « estimé », « observé », « inconnu » selon Operations ; ne pas annoncer « en direct » sur le seul horaire prévu.

**E. Terminal (maquette attestation)**

- Remplacer le panneau « Pour avancer » par **résultat owner réel**, action d'ouverture/export si réellement disponibles, ou conclusion sans artefact si la Journey se termine sans résultat documentaire.
- Distinguer Journey completed et décision Service de l'organisme ; Payment settled et Access issued ne concluent pas automatiquement Journey.
- Pas de redondance « Réalisée » dans couverture, sous-titre, carte résultat, préparation et timeline.
- Les capitalisations durables (Access, Proof, Credential, PersonalAsset) restent consultables dans leurs owners et dans Moi selon leurs droits.
- Aucun résultat « attestation disponible » si un artefact propriétaire n'est pas identifié.

## 7. Ma préparation — Readiness, Requirements et Forms

- Présenter de **vrais groupes** : de mon côté, bloque la suite, en attente, en ordre. L'état Readiness vient du serveur et demeure dérivé ; ne pas ajouter un booléen persisté « prepared » dans Journey.
- Indicateur compact seulement si le nombre est fiable : « 2 points à faire · 3 points vérifiés » ; ne pas afficher « 3 vérifiés » et montrer une seule ligne sans expliquer qu'il s'agit d'un aperçu filtré.
- Lorsqu'un groupe est déplié : afficher soit **tous** les éléments comptés avec possibilité de révéler la suite, soit distinguer « 1 affiché sur 3 » et permettre « Voir les 3 ».
- Ne pas compter les checks techniques peu utiles comme trois victoires utilisateur (« occurrence exploitable », « aucun obstacle actif », etc.). Si les données viennent du owner, les conserver pour la décision, mais les filtrer selon une **règle stable explicite de présentation** sans falsifier le total visible.
- Les Requirements affichent intitulé, obligation, conséquence et moyen(s) propriétaires de satisfaire. Posséder un fichier ≠ avoir satisfait une condition.
- Les Forms : état réel, titre, requis/facultatif, ouverture, échéance, brouillon local, soumission et confirmation séparées ; ouvrir leur profondeur propriétaire, ne pas incorporer un questionnaire géant dans Journey.
- Les actions alternatives légitimes pour une Requirement restent accessibles ; aucune source de vérité locale parallèle pour le « prêt ».
- En terminal : ne pas laisser « Ma préparation » vide ; garder les vrais formulaires/pièces consultables si cela sert le résultat durable, sans transformer leur ancien état en action active.

## 8. Documents, instructions et ressources

- Deux composants différents : aperçu N3 et profondeur Preparation. **Le N3 ne devient pas un lecteur de documents complet**.
- Typage exact : instruction (texte), URL externe, PDF, image, vidéo, fichier, contact, carte/planning. L'icône dépend du MIME/kind owner, pas d'une estimation du titre.
- Sur écran de 320–390 dp : **ne pas faire tenir quatre petites tuiles sur une ligne** comme sur une maquette grand format. Préférer une rangée horizontale scrollable montrant environ 2 à 2,4 éléments ou une grille de deux selon le contenu, avec large zone tactile et ordre accessible.
- Aperçu de 2–4 vrais éléments selon largeur ; « Voir les N ressources » seulement si N est connu sur une collection exhaustive ; sinon « Voir les ressources ». Pas de « 0 » si la BDD locale n'est pas encore exhaustive.
- Deux ressources homonymes restent deux objets ; nom, type, aperçu et source permettent de les distinguer ; ne pas dédupliquer par titre.
- Les aperçus ouvrables doivent être réellement interactifs ; si seule la profondeur globale est supportée, ne pas simuler des chevrons d'ouverture sur les items.
- Dans la profondeur : « Ouvrir » ≠ « Enregistrer une copie ». Afficher un aperçu PDF/image/texte si acquis et autorisé ; pas de téléchargement automatique forcé d'un fichier déjà présent et valide.
- Resource versionnée : bytes privés et métadonnées cohérents ; pas d'ancienne version affichée comme nouvelle. Les liens externes ne sont jamais marqués « accomplis » parce qu'on a cliqué.
- Contenu long : mise en page de lecture sobre, titres/paragraphes clairs, contenu développé sur demande, pas de cartes énormes pour chaque paragraphe.
- Privacy : ressource, PersonalAsset, JourneyArtifact, Proof et Credential restent distincts ; aucune exportation implicite vers Moi.

## 9. Repères complémentaires — une seule présence de chaque fait

Les faits date/début/fin/ville/lieu sont déjà dans la couverture. **Ne pas créer** « À savoir », « Adresse » et « Fin prévue » pour les répéter.

Afficher un micro-territoire contextuel (« Sur place », « Repères utiles ») **seulement** s'il existe un renseignement distinct et utile : entrée, salle, point de rendez-vous, contact, consigne d'accessibilité, format de photo, référence de dossier, heure de passage particulière, échéance attestée, itinéraire connu ou planning propriétaire.

- Toute ligne peut devenir action « Appeler », « S'y rendre », « Ouvrir le planning » uniquement avec destination autorisée et opérationnelle.
- Un numéro ou un code sensible ne doit pas être ajouté depuis la maquette ; le gérer selon permissions, visibilité et masquage appropriés.
- Pas de chevron à droite si aucune profondeur ne s'ouvre.
- N'ajouter aucune sous-section lorsque les seuls faits connus sont déjà dans la couverture.

## 10. Mes engagements — pas de générique qui avale les owners

Composer seulement les propriétaires réellement liés à la Journey :

- **Access** : état du droit, validité et destination ; AccessCredential (QR) exclusivement dans le détail sécurisé, AccessUse distinct. N'afficher « Mon accès » que si la relation est confirmée et autorisée.
- **Payment** : obligations multiples, montant, devise, échéance et statut de l'obligation ; la tentative « succeeded » ne solde pas elle-même une obligation « pending ».
- **Commerce** : commande, total/devise, état/expiration confirmés ; action vers Commerce owner.
- **Reservation / Capacity / Waitlist / Placement** : projeter seulement si leurs owners et liens existent. Capacité ≠ placement ; liste d'attente ≠ queue Live ; aucune position ou disponibilité inventée.
- **Form / Requirement / Pièces / Dossier** : ne pas exposer une entrée sans owner réel, et ne pas dupliquer la même action de la zone dominante.
- Plusieurs obligations/engagements : liste compacte regroupée, états individuellement lisibles, pas un seul bouton « Payer » couvrant plusieurs dettes sans distinction.

Aucun lien visuel ne délègue implicitement Permission, Payment, Access ou des informations privées d'un autre Profile.

## 11. Mon parcours — JourneySteps réels, pas parcours inventé

- Montrer « Mon parcours » seulement si les vrais JourneySteps aident à comprendre la progression.
- Séquence : étapes terminées compactées, présente visible, 0 à 2 futures pertinentes, « Voir la suite » quand elles existent et sont réellement connues.
- Branches : représenter choix/dépendances si owner-backed, ne pas forcer une timeline linéaire.
- Chaque statut d'étape vient de Journey owner. Ne jamais créer les cinq étapes de la maquette « Demande > Validation > Préparation > Jour J > Résultat » si elles n'existent pas.
- JourneyStep n'est pas un checkpoint Jour J. Une « étape réalisée » ne remplace pas un résultat AccessUse ni une décision Payment.
- Le clic sur une étape ouvre une vraie profondeur si disponible ; sinon la ligne est informative, sans faux chevron.
- Ne pas afficher à la fois la même étape dans « Préparation », « Mon parcours » et « Historique » sans rôle distinct.

## 12. Historique — petit aperçu, vérité datée

- Entrées significatives du propriétaire : demande transmise/confirmée, décision, accès accordé, document émis, état changé, etc. uniquement si le owner en donne la provenance.
- Début : 2–3 derniers éléments, dans l'ordre réel, date/heure pertinentes ; la profondeur Historique existe seulement si réellement routée.
- Temps d'événement ≠ temps de synchronisation ; « updated_at » ne devient pas date d'accomplissement.
- « Voir tout » ne doit pas être un bouton mort ; pas de liste complète infinie dans la racine N3.
- Ne pas copier des logs techniques ni dupliquer à l'identique une notification déjà présentée dans Now.
- Pour une Journey terminale, conserver ce qui aide à retrouver le résultat, sans retenir indéfiniment l'engagement dans En cours.

## 13. Tableau universel des faits et propriétaires

| Fait | Owner / source existante ou à confirmer | N3 | Action permise |
|---|---|---|---|
| Objectif, workflow, statut | Journey / Activity, identity/representation/state | Couverture | Aucun changement de statut client |
| Résumé utile | Activity/Journey representation.summary | Texte court conditionnel | Lire |
| Date, horaire, lieu, fuseau | Occurrence timing/place | Ligne couverture | Owner Occurrence |
| Jour ±N | Calcul local sur Occurrence date + IANA | Petit repère | Jour J seulement si admission owner |
| Conversation contextuelle | Conversations + autorisation | Icône couverture | Ouvrir/assurer contexte selon contrat |
| Prochaine action et choix | Readiness next/checks + lien owner | Situation dominante | Handoff typé |
| Blocage, attente et vérifiés | Readiness dérivée | Résumé / détail compact | Handoff vers résolution |
| Form Requests | Questionnaires | Ma préparation/engagements | Consulter, sauver brouillon, soumettre selon capacité |
| Requirement assessment | Requirements | Ma préparation | Voir moyens, satisfaire via owner |
| Documents fournis | Preparation Resource | Mini-aperçus | Lire, ouvrir, exporter selon droits |
| JourneyArtifact | Journey | Pièces liées au parcours | Consulter/fournir si owner le permet |
| Proof / Trust | Trust, propriétaire de la preuve | Détail conditionnel | Réutiliser/valider selon policy |
| Obligation de paiement | Payment | Engagement | Détail Payment, décision serveur |
| Commande | Commerce | Engagement | Détail Commerce |
| Accès et credential | Access | Engagement | Détail sécurisé |
| Capacity / Waitlist / Placement | Owners propres (projection à confirmer) | Contexte utile | Propriétaire uniquement |
| Jour J/Live | Operations / Occurrence | Repère/handoff | Admission owner, profondeur Jour J |
| Parcours | JourneyStep | Mon parcours si utile | Lire/ouvrir la profondeur réelle |
| Historique | Owner transitions/history projection | Aperçu | Historique propriétaire si disponible |
| Résultat final et actif durable | Owner de résultat / Journey, personal owners | Bloc résultat conditionnel | Ouvrir l'actif existant |
| Activity / Occurrence / Dossier | Owners correspondants | Lien secondaire si différent | Naviguer, pas dupliquer |

**Écart à combler explicitement :** la projection API Journey inspectée expose aujourd'hui identité, représentation, état, Readiness, steps, history, service, requests, requirements, forms, occurrence, payment, access et resources ; des données illustrées dans les maquettes (réservation détaillée, waitlist, résultat document, référence dossier, contact, salle, Wi-Fi, planning) ne sont pas automatiquement présentes. Pour chaque écart : vérifier l'owner et son endpoint existants avant de proposer une extension de projection **strictement additive, autorisée, non duplicative**. Si aucune source propriétaire n'existe, ne rien fabriquer pour remplir la maquette.

## 14. Contrat Serveur Django / API

**Serveur = vérité des faits et décisions :** statut Journey, Readiness dérivée, transitions, actions admissibles, permissions/mandats, Forms, Requirements, Payment, Access, Capacity, Waitlist, Occurrence, Operations, History owner.

Travail demandé :

1. Auditer les projections effectives de core/api/detail_projections.py et les selectors de chaque owner : liste des champs/links/capabilities déjà disponibles vs besoins UX. Ne pas créer un /mobile/ ou /sync/ générique.
2. Maintenir l'API Journey comme **composition autorisée**. Elle ne possède pas les réponses de formulaire, paiements, QR ou données documentaires privées des autres owners.
3. Fournir un contrat de handoff cohérent : type de destination, identifiant owner, lien canonique, capability actuelle, rôle/acteur et conséquence. Réutiliser le schéma existant lorsque suffisant ; ne proposer un nouveau descripteur typé que si les liens actuels ne permettent pas une action légitime.
4. **Ne pas offrir une capability simplement parce qu'un lien peut être construit.** Vérifier explicitement l'admission Jour J, les restrictions temporelles et l'autorité du bénéficiaire.
5. Prévoir projections autorisées de résultats durables et de contextes supplémentaires uniquement si les owners les exposent ; ID/URL privé jamais ouvert à un autre Profile.
6. Les actions sensibles et concurrentes réévaluent les permissions et les états côté owner ; idempotence, statut de réception et réconciliation explicites.
7. Chaque mutation confirme ou refuse, invalide les sources liées et permet au client de réacquérir les projections ; ne pas écrire de statut Journey optimiste définitif.
8. Contrôler IDOR, permissions, date-only/IANA, distincts form/requirement/resource/artifact/proof/credential, états inconnus, plusieurs paiements, invitation accept/decline et changement d'autorité.
9. API et Web lisent les mêmes owners, ne divergent pas en calculs métiers ; les humanisations de libellé sont des projections de présentation.

**Constat de code à auditer :** build_journey_detail ajoute actuellement une capability open_day_of dès qu'une occurrence_id existe ; vérifier si la profondeur cible effectue elle-même l'admission et ajuster **la sémantique de cette capability** sans élargir les droits. Une occurrence liée n'est pas une admission Jour J.

## 15. Client Flutter — acquisition, sélecteurs, navigation

**À conserver :** JourneyDetailScreen unique, JourneyRepository/projectionKind personal.journey.detail, JourneyDetailSelector, JourneyComposition, ProfileStore/Drift, PreparationResourcesRepository, router existant, ConversationContextAction, Action controls et design system.

**À mettre à jour :**

- Un modèle de composition **pur et déterministe** depuis les faits owner locaux : identité, situation dominante, sous-sections conditionnelles, hiérarchie, liens et badges. Pas de vérité, permission, statut, paiement ou conformité calculés en widgets.
- Composer les champs par priorité et déduplication **sémantique**, pas par suppression aveugle d'une chaîne égale au titre si un autre contexte en exige la lecture.
- Une action → un handoff réel. Couvrir les routes propriétaires existantes ; les destinations externes passent par une policy sûre ; une destination inconnue reste un fait informatif, et devient un élément d'audit plutôt qu'un CTA faux.
- Navigation depuis En cours, Moi/Mes démarches, Now, Notifications, Conversations et recherche vers **la même** racine N3. Aucun changement des écrans d'origine dans ce lot, sauf correctif ponctuel de handoff indispensable.
- Les profondeurs ouvertes puis refermées conservent scroll, onglet/expansion pertinente, dernier champ brouillon, contenu acquis.
- Une information observable importante (confirmation d'envoi, refus de permission, résultat Payment) se réconcilie sans bruit ni régression du contenu local.
- Isoler routes, stores, fichiers et callback asynchrones par Profile/actorContext et ressource ; une ancienne réponse réseau ne change jamais la nouvelle Journey affichée.

**Exemples de points d'entrée et leurs owners :**
- /journeys/:id → Journey N3.
- /journeys/:id/forms/:formId → Questionnaires.
- /journeys/:id/requirements/:assessmentId → Requirements.
- /journeys/:id/resources → Preparation.
- /payments/obligations/:id → Payment.
- /commerce/orders/:id → Commerce.
- /accesses/:id → Access.
- /occurrences/:id/day-of → Operations/Jour J.
- /conversations/:id → Conversations.
- JourneyArtifact / History / Dossier : n'exposer que les profondeurs réelles et autorisées, confirmer les routes existantes.

## 16. Local-first silencieux — obligatoire dès le premier rendu

**Lecture :** serveur propriétaire → projection API autorisée → Sync Kernel → BDD locale isolée du Profile → sélecteur → Flutter.

**Action :** intention/brouillon privé autorisé → API owner (direct ou outbox lorsque la mutation le permet) → décision serveur → source invalidée/réconciliée → nouvelle projection locale → UI.

- La BDD locale **n'est pas un cache optionnel** ni un « mode hors ligne ». Le N3 se compose depuis les informations déjà acquises, immédiatement.
- Pas de page bloquée, pas de bannière « actualisation impossible » ou « informations connues restent visibles », pas de cours sur serveur/cache/outbox.
- Si le réseau échoue et que la page reste utilisable : **silence** en plus de la ligne réseau globale existante.
- Si une action a été préparée mais pas transmise : icône discrète près de l'action avec sémantique « à envoyer » ; envoyée ≠ réception confirmée ≠ décision finale. Pas de succès de soumission sans accusé owner.
- Brouillons/formulaires, fichiers privés autorisés, versions de ressources et outbox survivent aux reconstructions, changements d'écran, app en veille et coupures.
- Les flux resources/forms/requirements peuvent échouer séparément. Un échec Preparation n'efface pas Journey ; une collection locale non exhaustive ne devient pas « Aucune ressource ».
- Les refus explicites du propriétaire (403/révocation) masquent les données concernées, même si une ancienne projection existe ; ne pas effacer les autres données privées ni les brouillons sans contrat.
- Retour réseau : Sync Kernel orchestre sans devenir owner, réconciliation silencieuse, backoff sans cascade de requêtes, revalidation sensible seulement au besoin.
- Changement de Profile/Space et refresh en vol : annulation logique/génération d'identité, jamais de bleed entre comptes.
- Push = signal d'invalidation, pas vérité. Horloge de Jour J = présentation locale, pas polling API.

## 17. Asynchronisme et opérations — états visibles utiles

| Situation réelle | Présentation minimale | Vérité requise |
|---|---|---|
| Brouillon modifié | Crayon/enregistrement discret | Draft local écrit |
| Intention non envoyée | Horloge/point discret près de l'action | Outbox propriétaire autorisée |
| Soumission en transit | Feedback local sans succès | Requête active et idempotence |
| Transmission confirmée | Confirmation envoyée | Accusé technique explicite |
| Réponse owner acceptée | Résultat confirmé | Projection réconciliée |
| Réponse owner refusée | Motif/action corrective | Décision serveur |
| Réseau absent, contenu connu | Pas d'alerte répétée | BDD locale |
| Donnée partielle | Pas de faux « aucun » | Couverture locale incomplète |
| Permission retirée | Ne plus révéler le contenu | 403/révocation owner |
| Conflit / version changée | Message dans la profondeur concernée | Version/owner |
| Fichier pas acquis | Lien/action légitime, sans fausse vignette | Métadonnées Resource |
| Action non permise sans réseau | Contrôle neutralisé/contextuel avec conséquence | Owner ou besoin d'autorité fraîche |

Aucun état UI ne se déclare « livré » ou « lu » sans événements porteurs de ces sémantiques. Ne pas imiter mécaniquement les coches WhatsApp avec des significations non implémentées.

## 18. Web — parité de sens et de comportement

- **Même route et mêmes propriétaires**, pas clone HTML de la structure Flutter.
- Couverture dense responsive, champs temporels non redondants, badge Jour J avec admission réelle, accès Conversation si droit, prochaine action et résultat selon vérités API.
- Sections contextuelles regroupées ; ne plus multiplier les gros panneaux, les encadrés « Pour avancer » et les liens d'aside qui répètent les faits.
- Template participant_journey_detail.html et contrôleur participant_views.py doivent projeter le même inventaire d'informations utiles que Flutter, dans les limites du navigateur.
- Wide : zone résumé + profondeur sélectionnée possible, **pas** un dashboard à trois colonnes. Navigation, focus, aria, contraste, responsive.
- En cas d'action Web, CSRF, permissions Django, POST métier avec confirmation serveur ; pas d'optimisme de résultat.
- Web ne doit pas inventer une ressource ou un compteur pour compenser une source API manquante ; vérifier le propriétaire et la projection d'abord.

## 19. Design system UI — critères de qualité 2027

- Reprendre les primitives Makolo existantes, palette officielle #5232DB, #2B176E, #FF704D, #FAF7F5, #0F172A ; Makolo Mark officiel, jamais redessiné.
- Le violet sert au sens/à la marque, pas à chaque icône. Les alertes, réussites et attentes utilisent leur état sémantique avec contraste adapté en thèmes clair/sombre.
- Une **seule** surface dominante, les autres objets sont des lignes/tuiles compacte(s), pas un livre de cartes.
- Supprimer le décor redondant : lignes de séparation superflues, doubles arrondis, faux chevrons, CTA répétitifs, grands vides.
- Resource preview : 2 éléments visibles sur 320–390 dp ou carrousel horizontal propre ; 4 colonnes seulement si la largeur réelle permet des titres lisibles.
- Statuts en mots courts, pas seulement couleur. Icônes familières soutiennent l'action ; seules ne suffisent pas pour un échec sensible.
- Cibles tactiles 44–48 dp minimum selon règles plateforme, semantics/tooltip, gestion d'ordre focus, lecteur d'écran, text scale 200 %, contraste requis et pas de troncature silencieuse d'une action importante.
- Animation discrète seulement pour transition utile ; aucune progression ou compteur « succès » fictif.
- Pas de carte vide pendant chargement si une projection locale existe. Skeleton uniquement quand aucune donnée locale n'est disponible.
- Le visuel reste cohérent sur Android 320/360/390/430 dp, tablette, Web et grands caractères, sans overflow ni texte microscopique.

## 20. Les cinq compositions de référence

**Universelle (Démarche simple, même moteur)**  
Couverture, état, ressources si présentes, préparation compacte si présente, engagements si présents, parcours réel et historique si utile. Les petites démarches ne sont pas forcées à remplir l'écran.

**Action à accomplir (badge/conférence)**  
Couverture + repère Jour −N, action owner principale, Requirements/Forms, ressources, éventuellement paiement et accès, étapes réelles. Ne pas supposer une pièce d'identité ni une confirmation si aucun owner ne l'exige.

**Attente (candidature)**  
Couverture + attente connue, pièces consultables, décision/échéance réelle si disponible, conversation autorisée, étapes réelles. Aucun « sous 7 jours » inventé, aucune soumission répétée.

**Jour J (jour actuel)**  
Couverture + Jour J admissible, accès aux opérations réelles, entrée/salle/planning uniquement s'ils sont connus, Access si existant, étapes non confondues avec checkpoints. Aucun deuxième bouton Jour J massif.

**Terminal (attestation ou autre résultat)**  
Couverture + état terminal, résultat concret si identifié, actions de récupération autorisées, documents/historique durables, engagements terminaux consultables. Pas de fausse attestation ou de « tous les points vérifiés » inventés.

**Autres cas obligatoires non illustrés par une image :** blocage, refus, révocation, échec de paiement, plusieurs branches/actions, invitation, dossier Service, liste d'attente, Journey sans Occurrence, date seule, ressources incomplètes et changements de Profile.

## 21. Plan de réalisation découpé dans #522

**Lot D0 — Inventaire/collision**  
Vérifier main/HEAD #522/commits/CI/travaux parallèles, propriétaires, migrations et tests. Construire matrice champ source → projection → selector → représentation → handoff. Ne pas faire de refonte de Découvrir/Notifications/Conversations.

**Lot D1 — Contrat des faits et des actions**  
Corriger les insuffisances prouvées des owner projections ; clarifier admission Jour J, actions multiples, destinations non reconnues, résultat owner. Tests serveur sur permissions, statuses, non-divulgation, idempotence. Aucun nouveau modèle par réflexe.

**Lot D2 — Sélecteur de composition Flutter**  
Formaliser les territoires universels/contextuels, ordre et déduplication, états waiting/blocked/action/choice/terminal. Tests unitaires déterministes depuis des projections locales réelles.

**Lot D3 — Composants visuels et actions N3**  
Couverture, repères temporels, situation dominante, préparation, resources, engagements, étape réelle, historique. Garder les routes profondes, la conversation dans la couverture, une seule action principale ; pas de faux chevrons. Goldens 320/390/430 + dark + text scale.

**Lot D4 — Propriétaires locaux/asynchrones**  
Vérifier toutes les profondeurs liées : Forms/Requirements/Resources/Artifacts/Payment/Commerce/Access/Jour J ; brouillons, fichiers, outbox, permissions et reprises. Aucune cascade réseau.

**Lot D5 — Web**  
Même hiérarchie et vocabulaire, permissions serveur, responsivité, actions, absence de doublons, situation active et terminale ; tests Django/templates.

**Lot D6 — Recette produit complète**  
Parcours depuis En cours/Moi/Now/Notification/Conversation, scénarios universels et contextuels, android emulator + Samsung, Web, coupure réseau, fermeture/reprise, changement de compte, refus, erreurs, accessibilité, captures réelles. Corriger causes, pas affaiblir tests.

Chaque lot : diagnostic court, fichiers réellement modifiés, propriétaire, risques, tests ciblés exécutés (ou explicitement non exécutés), commit(s) et état de #522. Ne pas merger main.

## 22. Matrice d'acceptation fonctionnelle

| ID | Scénario | Attendu |
|---|---|---|
| JN3-01 | Journey simple sans Occurrence | Objectif+état, aucune fausse date/Jour J |
| JN3-02 | Occurrence date seule | Date lisible, aucune heure fictive |
| JN3-03 | Même date 11h–14h + ville | Une plage et un lieu, aucune carte de fin/adresse répétée |
| JN3-04 | Jour −245, −16, −2, J, J+2, J+176 | Calcul civil exact dans fuseau owner |
| JN3-05 | Jour J non admis | Badge non ouvrable, aucune extension de droit |
| JN3-06 | Jour J admis | Badge ouvre vraie profondeur, pas deuxième CTA |
| JN3-07 | Deux prochaines actions | Les deux sont atteignables, priorité justifiée |
| JN3-08 | Action externe | Lien sûr + retour, clic ≠ accomplissement |
| JN3-09 | En attente | Attente non bloquante, aucune action fictive |
| JN3-10 | Blocker | Cause, conséquence, voie de résolution owner |
| JN3-11 | Requirements et Forms | Distincts, pas de document possédé réputé satisfait |
| JN3-12 | Resource locale versionnée | Ouverture de bonne version, pas de requête de remplacement inutile |
| JN3-13 | Ressource absente localement | Pas de faux zéro, page Journey toujours lisible |
| JN3-14 | Paiement tentative réussie / obligation pending | Affichage « pending », pas faux paiement acquitté |
| JN3-15 | Accès émis / Journey en cours | Journey reste en cours selon owner |
| JN3-16 | Waitlist vs Live Queue | Présentations distinctes, aucun rang inventé |
| JN3-17 | Journey completed sans résultat documentaire | Conclusion honnête, aucune attestation fictive |
| JN3-18 | Journey completed avec artefact owner | Ouvrir/exporter via owner autorisé |
| JN3-19 | Historique | Entrées significatives réelles, dates d'événements |
| JN3-20 | Conversation autorisée/non autorisée | Icône sous couverture seulement quand légitime |
| JN3-21 | Offline avec projection/bytes | N3 et documents utilisables, sans jargon ni alertes |
| JN3-22 | Soumission en attente puis confirmée | États distincts, succès seulement après owner |
| JN3-23 | Permission 403/revoked | Contenu ancien masqué et Profile isolé |
| JN3-24 | Changement Profile pendant refresh | Aucun bleed, anciens callbacks ignorés |
| JN3-25 | Dark/light + accessibilité | Contrastes, focus, texte augmenté sans overflow |
| JN3-26 | 320/360/390/430 dp | Ressources non microscopiques, couverture reflow |
| JN3-27 | Web | Identité, action, résultat et permission cohérents avec Flutter |
| JN3-28 | Multiples entrées N2 | Même Journey N3 avec contexte de retour correct |
| JN3-29 | Environnement demo incohérent | Diagnostiquer la source, ne pas « réparer » par un texte UI |
| JN3-30 | Refresh/rebuild répétés | Pas de cascade ni de perte de position/brouillon |

Les scénarios sont testés avec des fixtures d'owner explicitement déclarées démo. Les snapshots goldens n'ont **jamais** valeur de preuve de paiement, d'accès ou de readiness.

## 23. Vérifications d'implémentation et merge gate

- Django : tests API/projections, permissions, IDOR, owner admission, migrations/check, concurrence/idempotence lorsque mutations touchées, PostgreSQL si impact.
- Flutter : génération si nécessaire, **mobile/tool/dart_format.sh write + check**, flutter analyze, tests impactés puis suite pertinente, goldens, build Android selon impact.
- Sans SDK Flutter : workflow canonique **Mobile Format** sur la feature branch, puis relire HEAD ; aucune imitation manuelle du formateur.
- Android : Makolo_API_35 et Samsung selon impact, utiliser le profil de lancement existant, ne pas relancer Android à chaque F5 ; mode avion avec DB locale préacquise et DB partielle.
- Web : Django template, auth, navigation, responsive, gestion d'erreurs et permissions, pas de source API autoritaire parallèle.
- Ne jamais déclarer une CI verte avant résultat réel. Corriger les causes, respecter les travaux parallèles, ne pas fusionner si rouge.
- Commit/push résumés avec fichiers/risques/tests réellement exécutés, #522 conservée, pas de merge sans accord.

## 24. Définition de « terminé »

La mise à jour N3 est terminée **uniquement si** :

1. Les 8 questions du contrat Journey reçoivent des réponses pertinentes sans longueur ni répétition inutiles.
2. Chaque fait rendu a une source/permission identifiée et chaque action ouvrable mène à un owner effectif.
3. Les cinq compositions de référence existent **dans la même page** et les cas non illustrés sont corrects.
4. Les règles date/heure/Jour J et sans-Occurrence sont fiables, multi-fuseaux, sans faux accès.
5. Les Collections locales partielles, le mode avion, l'outbox, la révocation et les multi-Profils restent vrais et silencieux.
6. Flutter et Web conservent une parité sémantique réelle.
7. Un utilisateur peu habitué aux applications peut localiser son objectif, l'unique prochaine action ou l'attente, les ressources et les résultats sans lire une notice.
8. La recette réelle montre une UI nette, dense, attractive, accessible, sans superposition, sans 4 tuiles illisibles, sans jargon.
9. Les tests et CI pertinents sont effectivement verts ; les limites restantes sont explicites.
10. Aucun nouveau modèle générique, faux statut, autorité parallèle, doublon métier ou régression N2 n'a été introduit.

**Promesse vérifiable : Makolo marche pour vous. Le plaisir d'avancer, pas le plaisir de rester.**
