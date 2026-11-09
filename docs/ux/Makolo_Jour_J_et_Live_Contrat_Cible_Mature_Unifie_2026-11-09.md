# Makolo — Jour J et Makolo Live : contrat cible Mature unifié

**Statut :** cible produit et UX proposée, à valider avant gel — aucune implémentation revendiquée.  
**Date :** 9 novembre 2026.  
**Portée :** deux pages canoniques, perspectives métier, profondeurs, Web et Flutter, local-first et sécurité.  
**Contexte de rédaction :** PR #522, branche `fix/discover-a-continuation-context-20261014`.  
**Références à conserver :** `docs/ux/Makolo_Contrat_Jour_J_et_Makolo_Live_Gele_2026-10-07.md` et `docs/ux/Makolo_Contrat_Jour_J_et_Makolo_Live_Gele_Implementation_API_v1_2026-10-08.md`.

> **Objet de ce document : la destination idéale, pas les reliquats de code, l'audit des écarts, un backlog ni une déclaration de livraison.** Les documents gelés gardent leur valeur historique et leurs contrats API. Le présent texte clarifie la cible produit unifiée ; en cas de divergence de formulation « personnel / Space », il distingue désormais **acteur** et **perspective**, sans décréter une modification implicite des API existantes.

## 1. Principe central : deux pages, pas six

**Une Occurrence. Un Jour J canonique. Un Makolo Live canonique seulement lorsque celui-ci est pertinent et explicitement activé. Toutes les capacités légitimes coexistent sans sélecteur de casquette obligatoire.**

- **Jour J :** « Où en suis-je et que dois-je faire pour accomplir correctement cette Occurrence ? » C'est la page **d'action et d'orientation**.
- **Makolo Live :** « Qu'est-ce qui est effectivement connu ou observé, qu'est-ce qui évolue et quelle est la qualité de cette connaissance ? » C'est la page **de réalité observée**.
- **Makolo Live est facultatif.** Toute Activity, Journey ou Occurrence ne doit pas automatiquement posséder Live. Une Occurrence peut disposer de Jour J sans Live ; la phase temporelle, une Journey ou un accès valide ne publient jamais Live à eux seuls. Une activation explicite par un responsable autorisé et une fenêtre de pertinence sont nécessaires. Quand Live est disponible, c'est une profondeur contextuelle de Jour J, avec un résumé intégré uniquement si des faits utiles existent. Ce ne sont ni deux portes primaires, ni deux tableaux de bord.

**Unicité d'expérience ne veut pas dire endpoint, classe Flutter ou projection unique.** Plusieurs points d'entrée et projections spécialisées peuvent préserver l'autorité et la compatibilité. Le produit ne présente cependant pas des *pages de catégorie Profil* et des *pages de catégorie Space* comme expériences séparées.

## 2. Trois dimensions à ne jamais confondre

| Dimension | Question | Possibilités |
| --- | --- | --- |
| **Acteur effectif** | Au nom de qui agit-on ? | Profil personnel ; Space via un Profil dûment mandaté |
| **Perspective métier** | À quel titre intervient-on sur cette Occurrence ? | Participant / bénéficiaire ; organisateur / auteur / opérateur ; plateforme Makolo |
| **Autorité effective** | Quels faits et actions sont autorisés ici ? | Relations canoniques, permissions, mandats, périmètre, état et politiques des propriétaires |

Un **Profil** peut être participant et/ou organisateur. Un **Space** peut être participant et/ou organisateur. Un mandat staff ouvre, lorsque réellement attribué, une perspective **plateforme**, et non un accès universel ; un Space ne devient pas « la plateforme » par nature.

Un Profil qui opère pour un Space doit posséder une délégation réelle ; choisir un Space dans l'interface ne transfère pas les permissions. Les capacités d'un organisateur ne sont pas uniformes : un membre chargé du scan ne reçoit pas automatiquement la gestion des capacités ou l'accès aux données privées.

**Cumul et coexistence sur la même Occurrence :** une personne ou un Space peut légitimement être bénéficiaire **et** organisateur, et cumuler les mandats d'organisation (finance, logistique, Scanner, administration, etc.). **Aucun mode ni sélecteur « participant / organisateur / financier / logisticien / scanneur » n'est nécessaire pour révéler ses commandes.** Les faits et actions que l'acteur est autorisé à voir coexistent dans la même page, regroupés selon leur sens et hiérarchisés par l'utilité et l'urgence. Deux actions essentielles, l'une pour l'accomplissement personnel et l'autre pour l'organisation, peuvent être visibles simultanément. Le serveur vérifie chaque capacité, chaque donnée et chaque mutation séparément : la coexistence d'affichage n'est ni une fusion des droits, ni un droit d'accès à des données privées supplémentaires. La supervision plateforme conserve une portée et une finalité distinctes.

## 3. Parcours d'entrée, de sortie et de continuité

Les accès peuvent venir de Maintenant, En cours, Métier, Makolo Mark, d'un lien contextualisé ou d'une notification légitime ; Découvrir ne contourne pas la démarche d'admission. Chaque entrée vise une **Occurrence identifiée** et un **acteur effectif**. Les responsabilités et relations autorisées sont résolues ensemble, sans imposer un choix de mode avant l'entrée.

```text
Contexte d'origine → Occurrence → JOUR J → MAKOLO LIVE
                                  ↑           │
                                  └───────────┘
Après fin / annulation → En cours, Historique ou owner légitime
```

- Back restaure le contexte, le scroll et si possible la focalisation, sans conserver une permission expirée.
- Deep link et paramètre de perspective sont des demandes de navigation, jamais des preuves d'autorité.
- Jour J existe pour une fenêtre et des phases d'accomplissement reconnues par les owners ; la phase ne prouve pas qu'un fait Live est observé.
- Après l'Occurrence, Live cesse d'être présenté comme une situation courante. Jour J oriente vers les conséquences fiables et l'Historique. Une annulation ne produit pas un faux Live.

## 4. JOUR J — contrat de page unique

### 4.1. Invariant commun

Une hiérarchie stable, quel que soit l'acteur : **contexte → situation → actions réellement importantes → orientation et moyens → contraintes → suivi utile → suite**. L'accomplissement garde une priorité lisible, **sans règle arbitraire d'un seul bouton visible** : si une action de participation et une action d'organisation sont toutes deux essentielles et autorisées, elles apparaissent ensemble avec des libellés, contextes et regroupements sans ambiguïté. Les opérations supplémentaires (finance, logistique, Scanner...) sont directement accessibles sans changer de rôle ; les commandes secondaires ne doivent pas écraser les priorités. `CURRENT_MOVE = NONE` demeure un état légitime pour un territoire même si des actions existent dans un autre.

1. **Contexte de l'Occurrence :** nom humain, Activity associée, phase, date et destination utiles, acteur effectif et responsabilités pertinentes sans affichage d'UUID bruts ni menu préalable de casquettes.
2. **État actuel :** ce qui est effectivement établi, pas un récit inventé de progression.
3. **Prochain mouvement :** libellé compréhensible, possibilité réelle, éventuel blocage, action owner-backed et résultat confirmé. Ne pas faire d'une prévision une instruction confirmée.
4. **Orientation :** destination, zone, emplacement, instructions et mobilité selon leur vérité respective. Carte facultative et utile ; position actuelle inconnue si non observée.
5. **Moyens d'accomplissement :** droits Access, justificatifs à présenter via profondeur protégée, file opérationnelle, placement, checkpoint, ressources pertinentes.
6. **Readiness :** obstacle ou attente réellement applicable, raison et action corrective légitime ; pas d'inventaire bureaucratique par défaut.
7. **Live intégré :** fait ou changement pertinent avec sa couverture et sa fraîcheur ; accès à Live focalisé lorsque cela aide. Pas de copie intégrale de Live.
8. **Sortie :** état terminal et handoff clair vers En cours, Historique ou le domaine propriétaire.

Une **waitlist** n'est pas une **Live Queue**. Un nombre d'entrées dans la projection n'est pas une position de file. Une capacité n'est ni nécessairement commerciale ni nécessairement payante. L'absence de paiement n'est pas un défaut d'accomplissement.

### 4.2. Composition simultanée des responsabilités autorisées

La matrice ci-dessous décrit les **sources possibles de contenus et d'actions**, pas trois modes exclusifs. Pour une Occurrence et un acteur effectif donnés, les colonnes applicables peuvent être présentées **ensemble**. Les mandats organisateurs (finance, logistique, Scanner, gouvernance) sont agrégés dans la même zone d'organisation, avec des contrôles visibles seulement si autorisés. Une commande participant importante n'est pas cachée lorsque l'acteur organise aussi. Les commandes organisationnelles peuvent être prioritaires dans un contexte de conduite, **sans effacer une action de bénéficiaire urgente**.

| Territoire | Participant / bénéficiaire | Organisateur / opérateur | Plateforme Makolo |
| --- | --- | --- | --- |
| Situation dominante | « Mon accomplissement » | « Quelle réalisation faut-il opérer ? » | « Quel contrôle / assistance est autorisé ? » |
| Action P3 | Me présenter, rejoindre, poursuivre, fournir ce qui est requis | Ouvrir/traiter un contrôle ou une opération sous mandat | Examiner / intervenir selon mandat staff et finalité |
| Orientation | Ma destination, mon attribution, ma prochaine étape | Zones, flux et lieux utiles à l'opération | Contexte spatial limité au besoin de supervision |
| Access | Mes droits et credential protégés | Contrôle de droits et scan si autorisé | Audit/contrôle autorisé, jamais credential universel |
| Queue / Placement / Checkpoints | Ma situation connue | Gestion ou lecture des éléments dans mon périmètre | Lecture/intervention de supervision si autorisée |
| Capacity / Readiness | Effet sur mon parcours | Disponibilités et préparation réellement établies | Risques et conformité pertinents, si source réelle |
| Exceptions | Blocage me concernant | Incident opérationnel ou difficulté à traiter | Modération ou assistance dans le périmètre staff |

Ces cellules expriment des **intentions de présentation**, non des permissions créées par le contrat. Les données sont toujours fournies par les owners et filtrées avant la présentation.

## 5. MAKOLO LIVE — contrat de page unique

### 5.1. Invariant commun

Hiérarchie **contexte et couverture → faits établis → changements significatifs → temporalité / spatialité / opération → conséquences → provenance**. Live n'est ni un feed social, ni une timeline exhaustive, ni une promesse de streaming temps réel. **Realtime ≠ Live** : un transport rapide ne rend pas un fait vrai.

Chaque fait important conserve, selon disponibilité, son **état de vérité**, sa **source**, son **moment observé** et sa **fraîcheur** :

- `planned` : prévu ;
- `estimated` : estimé ;
- `observed` : observation établie ;
- `live` : observation courante qualifiée ;
- `unknown` : pas de connaissance suffisante ;
- `unavailable` : source/lecture indisponible.

La **couverture globale** de la lecture Live se distingue des états individuels : `ESTABLISHED`, `PARTIAL`, `UNAVAILABLE`, uniquement si ce niveau est déterminable à partir de sources réelles. **HIDDEN ≠ UNAVAILABLE ≠ EMPTY** ; aucune rubrique vide ne sert de preuve qu'il ne se passe rien.

### 5.2. Territoires de faits

1. **Temporalité :** horaires planifiés, départ/début/fin observés, retard confirmé, estimations qualifiées ; une heure programmée n'est pas un fait exécuté.
2. **Spatialité :** destination prévue, zone affectée, position observée, modifications réellement établies ; aucune géolocalisation simulée.
3. **Opérations :** accès contrôlés, appels de file, checkpoints, placements, capacité, préparation, Scanner et incidents **seulement si leurs propriétaires produisent les faits accessibles**.
4. **Delta utile :** ce qui a réellement changé, pourquoi cela compte et quand cela a été observé. Ne jamais reconstruire un historique fiable à partir de snapshots qui ne suffisent pas à le prouver.
5. **Instructions :** seulement les consignes légitimes publiées par le propriétaire ; observation ≠ instruction ≠ mutation autorisée.
6. **Médias :** photos/vidéos/documents Live explicitement rattachés, publiés et autorisés ; respect de No Orphan Media, révocation et conservation ; aucun feed ou média fictif.

### 5.3. Perspective métier de Live

- **Participant :** déroulement utile à son propre accomplissement ; ses faits de file, placement et accès, et les annonces publiables. Les identités, contrôles et données d'autres bénéficiaires ne deviennent pas visibles par défaut.
- **Organisateur :** lecture des flux et états opérationnels du périmètre mandaté, et des changements vérifiés qui appellent une décision ; les actions demeurent chez leurs owners.
- **Plateforme :** faits nécessaires à la supervision, la conformité, l'assistance ou la modération, selon permissions staff et finalité. Aucune omniscience ou accès aux secrets par principe.

**Différence obligatoire avec Jour J :** Live explique le réel et ses évolutions ; Jour J organise les actions importantes réellement possibles, y compris plusieurs actions essentielles de responsabilités différentes. Un même fait peut apparaître sur les deux avec une focalisation différente, sans dupliquer une source d'autorité.

## 6. Profondeurs secondaires — catalogue de capacités, pas obligation de nouvelles pages

Une profondeur n'existe que si l'information ou l'opération exige un focus dédié. Elle peut être un panneau, une sheet, un écran secondaire ou un handoff vers un owner existant.

| Profondeur | Depuis Jour J | Depuis Live | Owner et condition |
| --- | --- | --- | --- |
| Orientation / destination | Chemin et consignes pour agir | Position/changement réellement observé | Geography / Spatiotemporal ; source connue |
| Access / credential | Mes droits et présentation protégée | Fait de contrôle ou changement d'état autorisé | Access ; pas de secret dans une projection générale |
| Queue | Ma place / mon appel connu | Évolution observée de la file | Operations Queue ; séparation de la waitlist |
| Placement | Mon attribution et mon étape | Attribution ou changement établi | Operations Placement |
| Checkpoints | Étape à accomplir | Observation du contrôle | Operations Checkpoints |
| Readiness / Capacity | Blocage et prochaine intervention | Faits établis de préparation et capacité | Readiness / Capacity |
| Scanner | Contrôle à effectuer, si mandat | Faits de scan ou passage à l'outil | Scanner / Access ; validation serveur |
| Incident | Action/correction autorisée | Incident observé et publiable | Owner incident vérifié, jamais module fictif |
| Média | Preuve ou instruction utile à l'action | Observation visuelle publiée | Owner média, visibilité et provenance |
| Historique / conséquences | Suite de l'accomplissement | Sortie du Live terminé | Owner historique / progression |

Les profondeurs héritent de l'acteur effectif et du contexte de l'Occurrence et **revalident leur propre autorité par donnée et par action**. Une personne peut accéder depuis la même page à ses profondeurs de bénéficiaire et à ses profondeurs organisationnelles autorisées, sans changement de mode. Le staff n'accède qu'aux éléments compatibles avec un mandat plateforme réel.

## 7. Layout, interaction et accessibilité

**Deux personnalités distinctes sur une grammaire Makolo commune.**

- **Jour J : action-first.** Sur Compact : situation, mouvement, orientation et justificatif prioritaire. Sur Medium : action et spatialité peuvent cohabiter. Sur Wide : outils d'opération lisibles, sans dashboardification.
- **Live : reality-first.** Sur Compact : couverture et fait dominant puis changements. Sur Medium/Wide : lecture temporelle, spatiale et opérationnelle côte à côte seulement si cela améliore la compréhension.
- Les breakpoints dépendent de l'espace disponible et non d'une opposition Profil / Space. Text scale, lecteur d'écran, clavier, cibles tactiles, contraste et alternatives aux gestes restent obligatoires.
- Actualisation manuelle et à la reprise ; aucune promesse de « direct » si le pipeline owner n'est pas réellement courant. Ne pas déplacer brutalement le scroll ou la sélection à l'arrivée d'un fait.
- Les mutations sensibles demandent confirmation ou retour explicite ; jamais de faux succès ni de permission déduite du bouton affiché.
- Rechercher/filtrer uniquement un corpus effectivement disponible et autorisé ; ne pas inventer un moteur transverse Live.

## 8. Local-first, révocation et sécurité

- Les snapshots utiles peuvent être conservés par acteur/profil, périmètre de données et contexte, selon la politique de chaque propriétaire, avec horodatage et indication de fraîcheur. Offline ne signifie ni actualité garantie ni action serveur confirmée.
- Le changement d'acteur effectif (Profil / Space mandaté) ne doit pas faire fuiter une projection, un média, un credential ou une action d'un autre contexte. Le cumul de relations et de fonctions sur une Occurrence n'autorise pas une fusion des données privées ; les éléments sont vérifiés par portée, relation, propriétaire et autorité.
- La perte de permission, la révocation, la fin de fenêtre Live et les changements d'état déclenchent revalidation et suppression/masquage des données dérivées devenues illégitimes.
- Les protections contre le TOCTOU et les contrôles des mutations sont côté serveur ; une `capability` affichée n'est pas une autorisation.
- Les messages de refus, absence de données, indisponibilité source et contexte terminé restent distincts et compréhensibles.

## 9. Définition de conformité Mature

La cible est atteinte lorsque les scénarios suivants sont démontrés **par tests et expérience utilisateur**, sans supposer la présence de nouvelles données :

1. Un **Profil participant**, un **Profil organisateur**, un **Space bénéficiaire** et un **Space organisateur** consultent **la même expérience Jour J** ; lorsque Live est explicitement activé, ils accèdent à **la même expérience Live** sous leurs autorisations respectives.
2. Une personne ou un Space **participant et organisateur** voit simultanément les deux familles de contenus et les deux actions essentielles lorsqu'elles existent, **sans changer de mode**, sans fuite de données ni élévation d'autorité. Plusieurs mandats d'organisation composent une seule expérience et ne requièrent aucun sélecteur préalable.
3. La perspective **plateforme** est ouverte seulement aux mandats staff vérifiés et respecte ses finalités.
4. Jour J montre **une situation compréhensible et les actions importantes réellement autorisées**, simultanément lorsque nécessaire, avec une hiérarchie claire ; accès, attentes et placements sont correctement nommés, puis la sortie reste naturelle.
5. Live distingue systématiquement **faits, prévisions, estimations, inconnu, indisponible, couverture et fraîcheur** ; il montre les changements significatifs seulement quand ils sont établis.
6. Les deux pages possèdent **des hiérarchies visuelles distinctes** ; les profondeurs et retours restent cohérents.
7. Aucun credential, position, incident, observation ou succès n'est inventé ou divulgué.
8. Les refus, révocations, contextes multi-acteurs, double rôle, hors-ligne, fin/annulation, retour depuis background, Compact/Medium/Wide et accessibilité sont validés sur Web et Flutter.
9. Les owners existants gardent leurs responsabilités : Activity/Occurrence, Journey, Access, Operations, Capacity, Scanner, Readiness, Geography, Notifications, Domain Events et autres domaines canoniques.
10. Aucune seconde source de vérité ni nouveau modèle JourJ/Live générique n'est introduit pour réaliser la présentation.


## Règle d'éligibilité Live : opt-in, jamais automatique

- **Jour J ne dépend jamais de la publication Live.** La démarche et les accès restent accessibles selon leurs owners, même pour une Occurrence sans Live.
- **Live est une publication optionnelle de l'Occurrence**, activable/désactivable uniquement par un responsable autorisé. L'activation ne crée pas de faits, de couverture complète, de mouvement de foule ou de temps réel fictif.
- **La disponibilité doit être résolue côté serveur** : activation explicite, fenêtre admissible, droits du viewer. Les liens Live des interfaces et projections historiques ne doivent pas prétendre à une disponibilité sans cette vérification.
- **L'absence de Live n'est ni un échec ni un blocage.** La destination normale reste Jour J ; les pages Live non publiées répondent indisponible/refus, sans résurrection de cache privé.
- **Profil et Space partagent les mêmes types de pages** : l'acteur effectif contrôle le périmètre institutionnel, jamais un sélecteur finance/scanner/participant pour dévoiler les commandes.

## 11. Décision produit : cumul de capacités sans « mode » préalable

- **Cas fonctions d'organisation :** financier + logisticien + scanneur voient toutes les opérations effectivement autorisées, regroupées par objet et priorité. Les commandes sont découvertes directement dans Jour J ou leurs profondeurs ; aucun choix « je suis financier » n'est nécessaire.
- **Cas bénéficiaire + organisateur :** même acteur, même Occurrence, même Jour J et même Live. Les informations d'accomplissement personnel et d'opération coexistent. Deux CTA importants peuvent être affichés côte à côte ou successivement selon l'écran ; l'un ne supprime pas l'autre. Le contexte visuel (« Mon accès », « Contrôle des entrées ») prévient l'ambiguïté.
- **Hiérarchie :** une responsabilité opérationnelle active peut devenir prioritaire, mais la priorité n'est pas une exclusivité. La présentation arbitre l'espace, la densité et les regroupements, pas les droits.
- **Règle sécurité :** chaque contenu et commande est accordé par ses owners ; aucune autorité n'est ajoutée par le client. L'absence d'un bouton pour un acteur non autorisé découle du serveur, comme l'impossibilité d'envoyer un message quand une permission est désactivée, et non d'un mode UX à activer.
- **Plateforme :** les opérations staff doivent rester identifiables et justifiées par un mandat spécifique ; elles peuvent être accessibles dans la même expérience seulement si les frontières de finalité, journalisation et confidentialité sont garanties, sans masquer les autres capacités légitimes.
- **Anti-feature explicite :** ne jamais demander à l'utilisateur de sélectionner son métier ou sa casquette uniquement pour faire apparaître un bouton déjà autorisé.

Ce contrat est la **cible produit** ; les scénarios, lots et gates d'implémentation sont suivis séparément dans `docs/implementation/jour-j-live-mature-plan-lots-2026-11-09.md`.

## 10. Statut et frontière

Ce texte fixe **ce que l'expérience doit devenir**. Il **n'énumère volontairement pas les manques de #522**, ne promet pas de fonctionnalités non établies et ne modifie pas les quatre frontières API documentées en octobre. Une future implémentation devra auditer les owners, les mandats et la compatibilité avant de traduire le contrat en code.

**Aucun changement de code, d'API, de migration ou de permission n'est inclus dans ce contrat de conception.**
