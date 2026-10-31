# Makolo — Découvrir : chantier 06, profondeur N2, variantes et comparaison conditionnelle

**Date :** 31 octobre 2026  
**Branche :** `fix/discover-a-continuation-context-20261014` ([PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522)).  
**Périmètre strict :** profondeur lisible **N2 Web/Flutter** des possibilités déjà admises par Discovery ; mise en forme des faits propriétaires, des évaluations, des variantes d'Occurrence, des relations déclarées et des seules dimensions comparables.  
**Décision :** **implémentation N2 livrée en code**, validation exécutée **différée au chantier 09**. Pas de tests/CI lancés et aucun résultat vert revendiqué. Chantier 07 non ouvert.

## 1. Source normative et invariants

La section **Découvrir** du [contrat maître](../ux/Makolo_Contrat_Maitre_Now_Ongoing_Decouvrir_Me_2026-10-05.md) (§§ 31–38, 44–47, 77 et 82) prescrit :

- N2 expose l'identité/la représentation, le sens, les faits et les évaluations **favorables/limitantes/inconnues**, variantes et relations **si elles existent**, médias, temps/lieu/coût, fraîcheur **si disponible**, capacités et profondeur propriétaire.
- `UNKNOWN` n'est **ni** un refus **ni** une valeur par défaut ; le client n'infère pas de date, place, prix, accessibilité, éligibilité ou droit de participation.
- Les variantes ne sont produites que par le domaine ou l'amont ; similarité des titres ≠ variante. Une variante peut être une réalisation d'une même option ; une alternative est une option indépendante, et **complément ≠ alternative**.
- La comparaison est une projection **temporaire**, jamais un modèle propriétaire ou un score de pertinence, et elle n'est visible que si les dimensions des options sont réellement comparables. Il n'y a ni vainqueur UX universel ni classement implicite.
- La profondeur métier appartient aux owners : Activity, Occurrence, Opportunity, Funding, Service, Obtention. Découvrir ne copie pas leurs transactions ni leurs règles.

Les choix existants sont réutilisés : `detail_projection()` de `discovery/api/composition.py`, `DiscoveryWire`, `DiscoverySelector`, `DiscoveryPossibilityUnit`, `DiscoveryReader`, liens natifs owners et leur validation serveur. **Aucune nouvelle table, API de faits, migration ou action propriétaire.**

## 2. Écart d'entrée documenté

Le N2 mobile existant affichait la même unité N1, en retirant le chrome compact, et ajoutait seulement une liste de dates de variantes. Il ne distinguait pas de manière lisible les trois états d'assessment, ne présentait pas les réalisations par leur identifiant d'Occurrence ni les lieux rattachés à cet identifiant, ne proposait aucune comparaison conditionnelle et ne rendait pas les relations déclarées.

Le Web exposait la page Découvrir et certaines profondeurs spécialisées, mais **pas de N2 universel de lecture** fondé sur `detail_projection(family, id)` pour les quatre familles admises : `activity`, `service_activity`, `funding_activity`, `opportunity`.

## 3. Mobile : N2 universel, sans copie de domaine

**Nouveaux fichiers :**
- `mobile/lib/presentation/possibilities/discovery_n2_model.dart` — vue **pure en mémoire** des informations N2 : états d'assessment, variantes d'Occurrence, lieux indexés par Occurrence, relations libellées, fraîcheur explicitement transmise. `comparisonRows` existe uniquement si deux variantes distinctes d'une **même Activity** présentent chacune une valeur connue et distincte sur la **même dimension** (`Début`, `Fin`, `Lieu`). Pas de comparaison si la dimension manque à l'une, pas de prix parent copié dans la variante, pas d'analyse d'éligibilité locale.
- `mobile/lib/presentation/possibilities/discovery_n2_depth.dart` — présentation lisible des blocs favorables, limitants et inconnus, cartes de variantes avec début/fin/lieux, comparaison horizontalement défilante uniquement si `comparisonRows` non vide, relations libellées sans les rebaptiser « alternatives », fraîcheur uniquement si l'owner l'a fournie.

**Intégration :** `discovery_possibility_unit.dart` utilise `DiscoveryN2DepthSection` uniquement si `detailMode`, supprime l'ancien rendu dates-seules et évite les doublons des notes N1. Le détail intégral de description, tous les documents/resources et la galerie/Reader préexistants restent disponibles. Une variante n'expose « Consulter cette réalisation » **que si le client a déjà un handler de lecture owner** ; l'URL navigue vers `/occurrences/:id`, où le serveur revérifie la visibilité. L'invité sans handler n'obtient aucun CTA de lecture propriétaire artificiel.

Les familles non `activity` continuent d'afficher N2 (description, faits, assessment, ressources, médias, liens owner disponibles). En l'absence de variantes Occurrence prouvées, aucune comparaison ni panneau de comparaison vide n'est créé.

## 4. Web : détail N2 pour chaque famille admise

**Nouveaux :**
- `discovery/n2_presentation.py` — projection pure, avec les mêmes garde-fous : états séparés, dates et lieux par Occurrence, déduplication par identité, comparaison uniquement sur les dimensions entièrement documentées de variantes Activity, relations explicites sans fabriquer d'alternatives.
- `discovery/possibility_detail.html` — profondeur lisible (description, faits, assessments, variantes, comparaison conditionnelle, relations, médias, documents et fraîcheur explicitement connue).
- `discovery:possibility-detail` — route de lecture `/discover/possibilities/<family>/<id>/`.

**Branchements :**
- `DiscoveryPossibilityDetailView` prend **exclusivement** `detail_projection` depuis le pipeline owner-admis. Famille non supportée ou ressource non autorisée/inexistante → HTTP 404, sans recherche de secours. L'URL de retour est limitée aux chemins internes `/discover/` validés pour empêcher le retour ouvert vers un domaine tiers.
- `_web_discovery_card` ajoute `card.n2_url`. La carte N1 expose le lien **« Approfondir cette possibilité »** sans remplacer l'action propriétaire N1/les trois interactions existantes. Le lien transporte le chemin courant Découvrir pour revenir aux critères.
- Le contenu Web N2 affiche **toutes** les ressources déjà admises, sans créer de copies de documents ni de nouvelles permissions.

**Aucune comparaison entre deux possibilités distinctes** n'est simulée : le payload canonique courant expose `relations: []` par défaut ; un libellé de relation ne suffit pas à prouver une relation de substituabilité, et il manque actuellement un contrat propriétaire autorisant une table de comparaison inter-possibilités. La comparaison existante de ce chantier concerne donc uniquement les variantes Occurrence de la même Activity, lorsque les faits communs sont réellement publiés.

## 5. Scénarios de non-régression écrits

`mobile/test/discovery_n2_depth_test.dart` :
- distinctions `favorable/limiting/unknown` sans inférence ni doublons ;
- deux variantes Occurrence, lieux attachés aux bons IDs, différence d'horaire et de lieu, pas de prix inventé ;
- aucune comparaison pour dimension incomplète, une seule variante ou famille `funding_activity` non comparable ;
- relation `complement` conservée comme telle, jamais renommée `alternative` ;
- affichage mobile et ouverture de l'Occurrence seulement via handler de lecture disponible.

`discovery/test_n2_presentation.py` :
- classes de connaissance distinctes et inconnues non transformées en négation ;
- comparabilité stricte des dates/lieux connus ; pas de calcul de prix minimum ;
- non-comparabilité de Funding, Service et Opportunity avec une suite de variantes non contractuelle ;
- complément ≠ alternative ; route N2 existante et stable.

`discovery/test_m8b_mature_discover.py` :
- intégration N1 → N2 d'une Opportunity réellement publiée, avec réponse Web 200 et aucun tableau fictif ;
- refus 404 d'une famille non admise ; retour Web refusant une URL externe.

**Ces tests sont enregistrés, mais non exécutés.** L'intégration Web, les appareils Android, l'accessibilité réelle des tableaux horizontaux et les transitions owner restent à éprouver à la certification 09.

## 6. Matrice de familles

| Famille Discovery | N2 lecture | Variantes | Comparaison | Prochain accès |
| --- | --- | --- | --- | --- |
| `activity` | Oui, si l'owner l'admet | Occurrences réellement projetées, jusqu'au plafond server existant | Uniquement dimensions `Début`/`Fin`/`Lieu` complètes et divergentes ; aucun classement | Occurrence/Activity uniquement via chemins déjà existants, droits relus |
| `service_activity` | Oui | Aucune variante fictive | Aucune table fictive | Détail Service ou commande native si le serveur la propose |
| `funding_activity` | Oui | Aucune variante fictive | Pas de comparaison avec une formation à financer | Funding/Activity via handoff propriétaire existant |
| `opportunity` | Oui | Aucune variante fictive | Aucune comparaison inter-possibilité inventée | Owner Opportunity seulement s'il fournit un lien |

## 7. Limites et sortie

- La présence de plusieurs variantes dépend de `matching_count` et du plafond **12** déjà imposé dans `discovery/api/composition.py` ; ce chantier ne prétend pas afficher une population de variantes non admises ou plus complète que ce qui est livré par le serveur.
- Les relations ne sont montrées que lorsque le serveur fournit un **libellé explicite**. Les relations `relations: []` ne donnent lieu ni à inférence, ni à comparaison vide.
- Les dimensions inconnues restent absentes de la **table** pour ne pas simuler un fait comparable ; leurs explications `assessment.state=unknown` restent visibles en profondeur.
- Aucune donnée Web privée non admise n'est ajoutée. Les URLs owner affichées sont des handoffs existants qui réévaluent les autorisations.
- Aucun effet Save, Watch, Share ni engagement N3 nouveau n'a été introduit ; **chantier 07** séparé.
- Pas de CI, de test exécuté, de build Flutter, de migration ou de déploiement revendiqués.

### Critères de livraison en code

- [x] N2 universel Web/Flutter, description et toutes les ressources réelles.
- [x] Les trois types d'assessment sont présentés sans perdre leur sens.
- [x] Variantes d'Occurrence dédupliquées et ancrées à leur identité.
- [x] Variantes et relations distinctes des alternatives.
- [x] Comparaison uniquement quand plusieurs variantes Activity ont un même fait connu et divergent.
- [x] Aucun score de victoire, aucun prix/capacité/éligibilité calculé.
- [x] Autorisation propriétaire réévaluée sur les profondeurs et N2 Web.
- [x] Tests ciblés écrits et sortie documentée.
- [ ] Tests/CI/Android/Web exécutés — **différés au chantier 09**.

**Décision : chantier 06 — code livré, certification différée. Prochain chantier 07 exclusivement.**
