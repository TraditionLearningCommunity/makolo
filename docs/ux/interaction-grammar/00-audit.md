# A — Audit de l'expérience d'interaction transversale Makolo

**Statut : audit de conception, sans implémentation.**  
**Date : 8 novembre 2026.**  
**Source runtime auditée : TraditionLearningCommunity/makolo, main @ d0f0ec421c94c255fa4c0acd3509938a70c6322f.**  
**Branche documentaire : docs/interaction-grammar-cross-platform-20261108.**

## 1. Décision de cadrage

Makolo vise **un seul produit, deux interfaces complémentaires** : Web Django/HTMX et client Flutter natif, partageant les mêmes concepts, capacités serveur, intentions, politiques d'état et vocabulaire. Ce chantier ne construit pas d'écran et n'ajoute aucun système métier, modèle, endpoint, couche de synchronisation ni framework frontend.

Principe d'expérience : **« Pas le plaisir de rester. Le plaisir d'avancer. »** Une interaction doit améliorer orientation, compréhension, action, continuité ou confirmation. La qualité ne se mesure pas au nombre d'animations ou de gestes disponibles.

La couche étudiée est distincte du **Makolo Presentation System (MPS)** qui rend des artefacts présentables (invitations, programmes, billets, etc.). Ne pas rebaptiser MPS en design system de l'application.

## 2. Sources lues et priorité

1. Code, tests et contrats présents sur le main identifié en en-tête.
2. docs/architecture/makolo-domain-blueprint.md et .specify/memory/constitution.md.
3. docs/ux/Makolo_Contrat_Transversal_Mature_Experience_2026-10-06.md.
4. docs/architecture/mobile-a2-visual-behavior.md ; docs/architecture/mobile-visual-charter-v1.1.md.
5. docs/architecture/mobile-presentation-foundation-closure.md ; docs/architecture/w-desktop-experience-closure.md.
6. docs/product/product-language.md ; docs/ux/Makolo_UX_Recherche_Transverse_Contrat_Consolide_2026-10-08.md.
7. docs/architecture/mature-experience-principles.md ; docs/architecture/presentation-system.md.
8. Écrans, services et E2E Objectives ; composants de design, tests et continuité Flutter.

**Limite documentaire explicite :** Makolo_Application_Behavior_Interaction_System_v1.1.md est cité par les contrats historiques, mais aucun fichier autonome de ce nom n'a été trouvé dans la recherche de fichiers du dépôt. Ne pas prétendre avoir lu cette source indépendante ; les contrats versionnés disponibles servent ici de base. Comparer avec l'original lorsqu'il sera retrouvé.

**État GitHub vérifié :** au moment de l'audit, la seule PR ouverte retournée était #522, portant un chantier de consolidation distinct. Ce dossier documentaire ne doit pas être ajouté à cette PR ni fusionné avant revue. Les anciennes références à d'autres forks ne remplacent pas l'état du dépôt réellement accessible.

## 3. Inventaire vérifié — ce qui existe déjà

| Couche | Preuves dans le dépôt | État observé | Décision |
| --- | --- | --- | --- |
| Socle mobile | mobile/lib/design/makolo_theme.dart, makolo_components.dart, makolo_patterns.dart | Tokens, card, section, status, metadata, transitions, timeline | Réutiliser ; pas de deuxième MakoloTheme ou UniversalCard |
| Comportements mobiles | mobile/lib/design/behavior_primitives.dart, behavior_states.dart, surface_states.dart | Bottom sheet, confirmations, notifications, feedback local/pending/confirmed, Undo callback, haptique, états de sync | Étendre seulement lorsque le contrat prouve un manque |
| Continuité mobile | mobile/lib/app/resumable_interaction_store.dart ; tests de session/sync/présentation | Stockage de contexte reprenable et mécanismes de récupération déjà présents | Ne pas créer de deuxième store global |
| Web | frontend/src/app.js, static/js/workspace-runtime.js, templates/base/app.html | HTML serveur, HTMX, runtime de projection avec invalidation et scope | Garder amélioration progressive, URLs directes et historique |
| Accélérateurs Web | static/js/desktop-power.js et static/css/mature-experience.css | Palette Ctrl/Cmd+K, sélection au clavier, Escape, adaptation à la largeur | Ne pas redévelopper une seconde palette |
| CSS Web | static/css/makolo-ui.css, makolo-brand.css, mature-experience.css, makolo-a11y.css | Classes .mk-* et tokens déjà étendus | Consolider sans migration globale aveugle |
| Tests Web | e2e/specs/interactions.spec.mjs et objectives-product.spec.mjs | Clavier, menu utilisateur, focus, mobile Web, a11y, composition Dossier/Projet | Compléter les tests plutôt que réécrire les couvertures |
| Tests Flutter | mobile/test/behavior_primitives_test.dart, presentation_state_contract_test.dart, visual_regression_test.dart, tests de continuité | Feedback, Semantics, Reduce Motion, feuilles, scénarios et visuels | Conserver harness et goldens existants |
| Domaines Objectives | objectives/services.py, views.py, urls.py et tests D3-D6 | Rattacher/détacher/déplacer Dossier vers Projet, liaison de Journey, dépendance, cycle de vie, autorité | Utiliser comme pilote métier d'interaction |
| API Objectives | objectives/api_urls.py et api_views.py | Endpoints de lecture Dossier/Projet observés | Ne pas présumer d'un endpoint de mutation mobile équivalent |

Le comportement exact d'un composant non listé n'est **pas** réputé absent : cet inventaire est borné aux fichiers inspectés et recherches effectuées.

## 4. Écarts étayés

### A1 — Grammaire gestuelle transversale incomplète (priorité haute)

Le contrat Mature prévoit des règles d'état, tri, accessibilité, retour, mutation, Undo et sélection comme contexte. Le contrat Desktop W6 stipule que drag & drop, menu contextuel et sélection multiple étaient **exclus du périmètre initial**, dans l'attente d'un besoin owner-domain prouvé. Les surfaces Objectives vérifiées utilisent encore des formulaires POST pour rattacher, déplacer, détacher et lier. Aucun composant drag & drop global ne peut être affirmé installé sur la base de cette lecture.

**Décision :** fixer l'intention de chaque manipulation avant de choisir la gestuelle ; l'amélioration directe sur Dossier/Projet sera future et conditionnée à un contrat serveur réel.

### A2 — Sémantique des listes à expliciter (priorité haute)

Une collection peut être ordonnée par le serveur, triée pour lecture, réorganisée manuellement, regroupée par état ou parcourue en continuum. Ces opérations n'ont pas la même autorité.

**Décision :** « voir une liste » n'implique pas « pouvoir la réordonner ». Une poignée visible signifie **ordre manuel modifiable** ; les colonnes d'état ne transforment pas le statut métier par glissement sans commande autorisée.

### A3 — Registre d'icônes non encore démontré comme commun Web / Flutter (priorité haute)

Le Web importe Lucide via frontend/src/app.js ; le client natif s'appuie notamment sur les icônes Material. La même action doit garder la même signification et une silhouette compatible, indépendamment des packages. Les icônes ne remplacent pas les libellés d'accessibilité.

**Décision :** registre sémantique canonique, mapping de glyphes contrôlé et tests visuels croisés ; pas de sélection libre par écran.

### A4 — Écarts de tokens / CSS historiques (priorité moyenne)

- Charte mobile et MakoloColors.warm : #FAF7F5.
- frontend/tailwind.config.js : warm #FFF8F3.
- static/css/makolo-brand.css : --mk-surface-warm #fff8f3.
- static/css/makolo-ui.css contient des valeurs anciennes de marque (par exemple --mk-brand #4f46e5 et .mk-btn-primary).
- D'autres feuilles et overrides corrigent certains contrastes ; l'ordre effectif de cascade doit être vérifié avant toute unification.

**Décision :** définir les rôles de tokens et réaliser un audit de cascade calculée avant corrections futures. Ne pas remplacer mécaniquement toute occurrence par la valeur de marque : couleurs primitives, couleurs de contraste et surfaces sont des rôles distincts.

### A5 — Autorité et canaux de mutation à ne pas inventer (priorité bloquante pour l'exécution)

objectives/services.py possède les règles et vérifications. Les templates Objectives appellent des vues POST à formulaires. objectives/api_urls.py ne montre que des routes de détail en lecture pour Dossier/Projet. Une future interaction mobile ne doit ni simuler le déplacement ni réutiliser un POST HTML comme API native sans décision explicite de contrat.

**Décision :** toute opération direct-manipulation est bloquée tant que l'owner n'expose pas un chemin de mutation adapté et testé pour le client concerné. Aucune interface n'est autorisée à déduire l'autorité du simple rendu d'un bouton.

### A6 — Préférences et réversibilité à borner (priorité moyenne)

Le contrat Mature préserve le contexte (scroll, filtres, tri, sélection, profondeur, draft). showMakoloUndoToast existe côté Flutter mais sa présence n'établit pas que les opérations métier sont annulables.

**Décision :** préférences locales/persistées seulement dans le scope acteur/profil autorisé, séparées de l'état métier ; Undo réel seulement avec commande inverse sûre et revalidation, sinon confirmation préalable si nécessaire.

## 5. Risques de régression

- Faux succès, double envoi, conflit caché, capacité devenue périmée.
- Fuite d'existence d'objets privés dans menus, recherche de destination, drag preview ou erreurs.
- Deux sémantiques d'appui long en concurrence (menu contextuel vs drag).
- Perte du focus/scroll/back en fermant un panneau ou après actualisation.
- Touch target trop petite, affordance uniquement au hover ou geste sans alternative.
- Densité « dashboard », onboarding/tutoriels bavards, animations ornementales.
- CSS/JS globaux ajoutés à chaque page ; coût de rendu/prefetch sur les surfaces non concernées.
- Confusion entre MPS, design system applicatif, Product Language et service métier.

## 6. Frontières fermes

**Dans le chantier de conception :** audit, contrat d'intentions, iconographie sémantique, inventaire de primitives, cartographie des dépendances, matrice de tests et plan d'adoption.

**Hors chantier :** changement de code Web/Flutter/Django, refonte d'écran, ajout d'endpoint, drag & drop fonctionnel, migration de base, réorganisation des états métier, nouvelle palette de commandes, nouveau routeur et nouvelle infrastructure de sync.

## 7. Décisions et suites

1. Contrat : 01-interaction-contract.md.
2. Catalogue réutilisable : 02-primitives-catalog.md.
3. Scénarios et critères de validation : 03-validation-matrix.md.

Le présent audit est une **preuve de lecture statique**, pas un audit visuel sur appareils, ni une exécution des tests. Aucune CI, capture d'écran ou mesure de performance n'est déclarée obtenue par ce dossier.
