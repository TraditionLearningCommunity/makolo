# Métier Space — contrat figé d'une seule application, huit grammaires, profondeurs non uniformes

**Décision de conception du 31 octobre 2026.** Suivi dans la PR #522. **Pas de changement runtime dans ce checkpoint.** Complète sans remplacer `Makolo_Contrat_Metier_Space_Gele_2026-10-06.md` et les huit contrats UX Métier du 8 octobre. Les faits du code et les autorisations propriétaires prévalent.

## Décision centrale

**Une application Makolo, un ADN visuel/interactionnel commun, huit grammaires contextuelles possibles.** Jamais huit applications ou huit thèmes séparés. Mais **aucun layout N1 universel, aucune fiche N2 universelle, aucun N3 unique**. Les niveaux désignent des *profondeurs cognitives*, non un nombre de routes ou une succession obligatoire de pages.

- **N1** : entrée métier contextualisée : comprendre l'activité réelle, les structures et la continuité pertinente au Space. L'ordre, la densité et les composants suivent les faits et l'archétype ; pas de gros bouton identique placé au même endroit sur tous les N1, ni de trois cartes artificiellement imposées.
- **N2** : approfondir une réalité concrète, une collection ou une relation : Activity, programme, session, dossier, commande, route, départ, œuvre, production, édition, etc. Le contrat de vérité est commun, **pas le squelette de l'écran**.
- **N3** : profondeur d'action ou d'information appartenant à son véritable owner. Un N2 peut ouvrir **0..n N3** distincts (ex. Programme → inscriptions, sessions, ressources, exigences ; Départ → capacité, opérations, Jour J ; Œuvre → ressources, présentations, offres réelles). Un N1 peut aller directement à une profondeur propriétaire lorsque N2 n'ajoute rien. N3 peut renvoyer au même N2 et préserver l'origine.
- Aucun métier n'est forcé à « commencer », « payer », « approuver », « terminer », « publier » ou « devenir Live ». Les actions naissent de faits, d'une intention, d'un contexte, d'une autorité et d'un owner réellement capables de les traiter.

## Cohérence de produit : identité sans uniformisation

Une seule géométrie et un seul système : shell Space, Makolo Mark, palette `#5232DB #2B176E #FF704D #FAF7F5 #0F172A`, typographie, espacements, densité, navigation, hiérarchie visuelle, feedbacks, states, accessibilité, motion, adaptive Web/Flutter et comportements de retour. Réutiliser des **primitives de sens** : identity/subject, timeline, continuity, structure/relations, conditions/readiness, offer, request/case, media contextualisé, actions/handoffs.

**Composer ces primitives selon les faits**, non selon une page standard par archétype. Une œuvre peut privilégier l'image si un média autorisé existe ; Transport peut privilégier départ et horaire ; Services un dossier et ses conditions ; Commerce l'offre et la commande. Le visuel n'est pas un décor et une image absente ne casse jamais le parcours. Web et Flutter ont la même grammaire métier et les mêmes droits, mais pas nécessairement les mêmes pixels ni gestes.

Deux tests de qualité opposés : si le langage visuel, la navigation et les retours donnent l'impression de changer d'application, **échec** ; si huit métiers se réduisent au même template `titre + statut + bouton`, **échec**.

## Grammaires de référence (non exclusives, jamais des écrans imposés)

| Archétype | Centre de gravité N1 | Profondeurs possibles selon owner et autorité |
| --- | --- | --- |
| Generic / Activités | activités et réalisations, structures et continuité | Activity, Occurrence, demandes, préparation, ressources, Jour J |
| Community / Initiatives | initiatives et actions collectives | initiative réelle, Occurrence, demande, coordination autorisée |
| Education / Programmes | programmes, sessions, inscriptions | programme, session, JourneyRequest, Form, Requirement, Resource |
| Service provider / Prestations | prestations, demandes, dossiers | cas Services, Journey, assessment, réalisation, owner de preuve |
| Commerce | offres, commandes, réalisations | Offer, Order, Capacity, Payment/Access si véritablement présents et autorisés |
| Transport | exploitation, départs, routes, véhicules | départ, route, véhicule, Capacity, opérations, Access, Jour J |
| Creative / Créations | œuvre/création, progression fondée, présentations | Activity, Occurrence, Resource, Presentation, Offer réelle |
| Media / Productions | production, édition et réalisation | Activity, Occurrence, ressources, médias publiés, diffusion si owner réel |

L'archétype oriente la langue et la lecture **sans masquer une verticale supplémentaire réelle** ni conférer une permission. Un Space mixte peut présenter plusieurs perspectives seulement lorsqu'elles sont utiles, distinctes, réellement alimentées et autorisées. `ResponsibilityPerspective` (sous quel mandat ?) et `BusinessPerspective` (quelle réalité ?) restent indépendantes.

## Architecture technique conceptuelle

Réutiliser `BUSINESS_WORLD / BUSINESS_PERSPECTIVE / BUSINESS_SECTION / BUSINESS_ENTRY / CONTINUITY_FACET / OWNER_HANDOFF / MEDIA_BINDINGS / KNOWLEDGE_CONTEXT` du contrat gelé. `BusinessEntry` est une projection UX d'un fait owner-backed, **pas** un modèle `WorkItem`, ni une carte universelle. La Presentation n'acquiert aucune propriété métier.

Une transition vers profondeur porte : Space Actor, viewer, responsabilité, perspective, entry identity, owner reference, intention, handoff réel, scope/capability serveur, contexte de retour. Un N2 propose ses N3 disponibles selon les actions des propriétaires ; n'invente aucun endpoint ni destination. Les pouvoirs sont revérifiés à l'ouverture et à l'exécution. Le lien n'est pas une permission.

**Règle de navigation :** `N1 → N2 A → N3-A → N2 A` ou `N1 → N2 A → N3-B → N2 A`, avec sélection, section, recherche, filtres, profondeur, défilement et acteur retrouvés ; entrée directe N1→owner permise ; N2↔N2 permis. Pas d'escalier linéaire ni écran intermédiaire obligatoire.

## États, confidentialité et local-first

Distinguer : contenu, calme, vide établi, aucun résultat filtré, chargement, rafraîchissement, partiel, indisponible, offline, stale, erreur locale, perte d'autorité. `empty` n'est certain que si `coverage=established`; `hidden` par permission implique omission sans divulgation. Une permission révoquée invalide actions, routes et cache. Flutter conserve seulement des snapshots correctement isolés (viewer/Space/responsabilité/perspective/source) avec fraîcheur explicite, jamais une autorité locale ni un Live inventé. Les fichiers/images privés ne sont pas promus en N1 pour l'esthétique.

Interdits : task manager ou ERP générique, feed, CMS parallèle, duplication de Journey/Payment/Access/Requirement/Readiness, métriques de watch-time/popularité, transfert implicite de Mandate par Group/Membership, action universelle « Créer » non contextuelle.

## Ce qui est livré et ce qui reste

Les groupes 1–4 de #522 ont réalisé les huit grammaires **N1 serveur/Web**. Les `reading_groups`, `perspectives=[primary]` et handoffs existants ne représentent **pas encore** le contrat final multi-perspectives, N2→N3 multiples, coverage source par source ou Flutter complet. Ils sont à améliorer **par composition**, sans restructuration gratuite.

Ne pas écrire huit pages N2 parallèles. **D'abord inventorier** les vrais owners et destinations, les cas sans N3, les cas multi-N3, les permissions, les profondeurs Web/Flutter déjà existantes ; puis combler les manques justifiés.

## Critères de fermeture (gates)

1. **Unité perceptive** : même Makolo (navigation, tokens, Behavior, retour) dans les huit grammaires, sans template métier uniforme.
2. **Vérité** : section et action issues d'un owner ; domaines mixtes visibles sous droit ; aucun statut inventé.
3. **Topologie** : N2 flexible, 0..n N3, handoffs exacts, back à l'origine ; pas d'étape vide imposée.
4. **Sécurité** : droits/IDOR revérifiés par owner, aucune autorité Membership, révocation et changement de Space sûrs.
5. **États** : empty, calm, partial, unavailable, no-match, offline/stale/refreshing correctement distingués.
6. **Deux clients** : mêmes identités et contrats, rendus natifs adaptés, aucun second backend Flutter.
7. **Preuves** : tests ciblés puis suite pertinente, migrations, PostgreSQL si nécessaire, QA visuelle Web/Flutter, zéro suppression/affaiblissement de test.

## Séquence après cette décision

**A.** Inventaire/collision audit au HEAD courant ; cartographie réelle `N1 → N2 → N3 0..n` par owner ; réemploi d'existant.  
**B.** Contrat serveur de sélection/handoffs/coverage/intention/navigation, sans nouvelle persistance par défaut.  
**C.** Web : expérience cohérente et parcours propriétaires complets, visuellement contextualisés.  
**D.** Flutter : mêmes contrats, Behavior natif et local-first sûr.  
**E.** Tests end-to-end, privacy, permissions et validation avant fermeture.

**Formule figée :** *Une seule application Makolo ; huit grammaires sans huit produits ; aucune géométrie N1/N2/N3 imposée ; un N2 peut conduire à plusieurs N3 propriétaires ; les faits choisissent les compositions, l'autorité choisit les actions, le design system assure l'unité.*
