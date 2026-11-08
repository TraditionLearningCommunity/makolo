# B — Makolo Interaction Grammar V1

**Statut : contrat de conception proposé pour revue (non implémenté).**  
**Portée :** Web compact/adaptatif/expanded, tablette tactile, Flutter Android/iOS, souris, clavier, tactile, lecteur d'écran.  
**Références :** 00-audit.md, contrat transversal Mature, charte mobile V1.1, Product Language, constitution Makolo, contrat Desktop W, source runtime main indiquée dans l'audit.

## 1. Doctrine

**Une intention = une sémantique = des garanties identiques, quel que soit l'appareil.** Un geste est une manière d'invoquer une intention, jamais une nouvelle opération métier. Makolo reste professionnel, calme, direct, non infantilisant et compréhensible sans tutoriel.

L'application est unique sur le plan produit : **deux interfaces appropriées** sont autorisées, pas deux ensembles de fonctionnalités métier divergents. Parité = accès aux mêmes intentions autorisées et résultats, pas identité pixel/gestuelle. Si une capacité n'est pas encore disponible sur l'un des clients, afficher un chemin réellement pris en charge ou ne pas promettre l'action.

Hiérarchie : contexte → information prioritaire → action utile → détails progressifs. Aucun bouton « découvrir les fonctionnalités de Makolo » ne doit être requis pour comprendre les commandes courantes.

## 2. Registre des intentions

| Clé de conception | Intention | Signification stable | Précondition |
| --- | --- | --- | --- |
| OPEN | Ouvrir | Naviguer vers l'objet ou sa profondeur | Lien autorisé et valide |
| INSPECT | Aperçu | Voir les faits utiles sans quitter sa position | Projection visible disponible |
| MORE | Actions | Montrer les actions secondaires applicables | Au moins une action pertinente |
| SELECT | Sélectionner | Marquer des éléments pour une action | Collection compatible |
| SORT | Trier | Changer la lecture selon un critère explicite | Ordre de lecture réellement disponible |
| FILTER | Filtrer | Restreindre la collection dans un corpus explicite | Portée honnête locale / serveur |
| REORDER | Réorganiser | Changer un **ordre manuel** appartenant à un owner | Opération de rang autorisée et persistable |
| MOVE | Déplacer | Changer le conteneur ou rattachement canonique | Commande owner, source/destination valides |
| LINK | Associer | Établir une relation sans déplacer l'objet | Commande de relation autorisée |
| UNLINK | Détacher | Retirer une relation sans détruire l'objet | Commande owner disponible |
| TRANSITION | Changer d'état | Demander une transition métier | Transition validée côté owner |
| EDIT | Modifier | Éditer un champ propriétaire explicitement modifiable | Validation, gestion conflit et sauvegarde |
| BULK | Action groupée | Exécuter une opération définie pour une sélection | Capacité batch réelle ou orchestration sûre |
| UNDO | Annuler une action | Appliquer une inversion **réelle** et autorisée | Commande inverse sûre, validable |
| SEARCH | Rechercher | Retrouver une réalité visible dans le contexte | Respect du contrat Recherche transverse |

**N'interchanger jamais :** SORT ≠ REORDER ; MOVE ≠ LINK ; SELECT ≠ OPEN ; TRANSITION ≠ changement de colonne cosmétique ; « retour navigateur » ≠ UNDO métier ; « stocké localement » ≠ « confirmé ».

Un élément de collection peut être navigable sans être réorganisable ni déplaçable. Une Démarche liée à un Dossier n'est pas nécessairement un enfant transférable comme un fichier.

## 3. Grammaire gestuelle décidée

| Intention | Souris / trackpad Web | Clavier Web | Mobile / Web tactile | Alternative accessible visible |
| --- | --- | --- | --- | --- |
| Ouvrir | Clic sur titre/surface explicitement navigable | Tab, Enter | Appui simple | Lien ou action Ouvrir |
| Aperçu | Bouton d'aperçu / action locale | Bouton + Enter/Espace, Escape ferme | Bouton ouvrant sheet/détail | Ouvrir le détail complet |
| Actions contextuelles | ⋯, clic droit seulement en raccourci sur objet compatible | ⋯ au Tab, menu par Enter/Espace, flèches et Escape | ⋯, appui long optionnel | ⋯ permanent ou accessible au focus |
| Sélection multiple | Case, Maj/Ctrl selon règles documentées | Cases, Espace, contrôles de lot | Mode Sélection explicite | Cases / bouton Sélectionner |
| Tri | Contrôle de tri | Choix via clavier | Contrôle de tri / sheet | Choix de critère accessible |
| Réorganisation manuelle | Poignée + glisser si activée | Déplacer avant/après ou commandes Monter/Descendre | Poignée tactile + déplacement, pas appui long sur toute la ligne | Commandes Monter/Descendre/position |
| Déplacement conteneur | Drag de l'objet vers zone compatible, en raccourci | Déplacer → choisir destination | Déplacer → choisir destination ; drag éventuel avec affordance explicite | Déplacer → destination → validation |
| Relation | Action Associer, éventuellement geste explicite distinct | Associer → sélectionner | Associer → sélectionner | Action Associer |
| Édition | Champ inline uniquement sur champ modifiable | Enter/modifier, Escape annuler, Ctrl/Cmd+Enter si applicable | Champ explicite, clavier adapté | Éditer dans la profondeur de détail |
| Annuler | Action Annuler seulement si inverse fiable | Activation du contrôle Annuler | Action Annuler seulement si inverse fiable | Retour d'information + lien inverse |

**Conflit de gestes résolu :** appui long sur l'objet = raccourci vers actions contextuelles ; drag pour REORDER = poignée visible. Le MOVE « déposer sur Projet » n'utilise ce geste que si le type et la destination sont annoncés visuellement et qu'un choix de destination alternatif existe. Ne pas rendre toute liste draggable par défaut.

Un clic droit n'intercepte pas systématiquement le menu navigateur : seulement sur les objets concernés, sans empêcher les fonctions natives attendues des champs texte/liens.

## 4. Politique d'affordance

- Le chevron signifie expansion ou navigation selon **son contexte visuel explicite**, jamais les deux à la fois sur une même zone.
- La poignée de drag n'apparaît que pour REORDER autorisé. Elle n'indique pas MOVE.
- La zone de dépôt affiche visiblement sa nature et le résultat attendu. Survol sur une zone invalide ne signifie pas validation ; ne pas autoriser un drop silencieux.
- L'action principale reste immédiatement repérable ; les actions secondaires sont regroupées derrière ⋯. Ne pas cacher une action indispensable derrière un geste secret.
- Le mode sélection modifie clairement la barre d'actions et offre « Terminer/Annuler la sélection ». Un appui sur une ligne en mode sélection sélectionne, sans navigation accidentelle.
- Un ensemble trié automatiquement ne présente pas de poignée d'ordre manuel. Il peut être filtrable mais pas nécessairement reclassable.

## 5. Registre d'icônes sémantiques

Le registre définit un **sens stable**, non une importation d'icônes depuis une nouvelle bibliothèque. Valeurs candidates à matérialiser par un mapping central lors de l'implémentation :

| Intention | Signature graphique | Web Lucide candidat | Flutter Material candidat | Contraintes |
| --- | --- | --- | --- | --- |
| MORE | trois points horizontaux | ellipsis | more_horiz | Toujours même entrée d'actions |
| REORDER | points verticaux en poignée | grip-vertical | drag_indicator | Uniquement ordre manuel |
| SORT | deux flèches opposées | arrow-down-up | sort | Jamais pour drag |
| MOVE | dossier avec mouvement entrant | folder-input | drive_file_move_outline | Destination explicitée |
| LINK | maillons reliés | link-2 | link | Relation sans transfert |
| UNLINK | lien rompu | unlink | link_off | Ne supprime pas l'objet |
| INSPECT | panneau de détail | panel-right-open | view_sidebar_outlined | Lecture, pas édition |
| SELECT | case à cocher | square-check | check_box_outlined | Sélection multiple |
| UNDO | flèche retour courbe | undo-2 | undo | Uniquement inversion exécutable |
| SEARCH | loupe | search | search | Portée de recherche annoncée |
| FILTER | entonnoir | filter | filter_alt_outlined | Distinct du tri |
| EXPAND | chevron directionnel | chevron-down | expand_more | Orientation ajustée à l'état |
| CLOSE | croix | x | close | Fermer un panneau, pas annuler une mutation |

**Règle de mise en production :** vérifier noms réels disponibles, direction, stroke, taille, accessibilité et similitude des glyphes dans les bundles existants. Un glyph Flutter plus cohérent peut remplacer le candidat sans changer la clé sémantique. Jamais de nouveau jeu d'icônes par écran. Le label vocal décrit l'action + l'objet, pas la forme de l'icône.

Le Mark officiel reste un symbole de marque et d'entrée produit, jamais un glyph générique. Le corail ne signifie ni succès ni erreur.

## 6. Contrat de commande et autorité

La description suivante est **conceptuelle, pas un nouveau schéma API**. Chaque intention visible doit pouvoir être résolue en :

- **source** : type/identité stable, contexte acteur et scope ;
- **capacité effective** : action possible ici, avec contraintes/destinations ;
- **éligibilité** : validation serveur actuelle sur objet(s) et cible ;
- **risque** : sans conséquence, réversible, irréversible ou sensible ;
- **transport pris en charge** : formulaire Web, API owner, autre mécanisme explicite et sécurisé ;
- **résultat** : confirmation canonique, refus, conflit ou échec ;
- **réconciliation** : refresh ciblé des projections et conservation du contexte ;
- **compensation** : uniquement si l'owner sait inverser la commande.

Le contrôleur UI peut normaliser les états de présentation ; il ne devient pas un service métier universel et ne génère pas d'endpoint générique /move, /reorder ou /bulk. Le serveur doit réévaluer Permissions/Mandates et les invariants même après affichage d'une capacité. Ne pas révéler dans les cibles de déplacement un objet que la personne n'a pas le droit de voir.

## 7. Contrat d'états et de feedback

Deux axes existants à respecter : **Content State** (initial/loading/content/empty/error…) et **Sync State** (synced/syncing/pending/offline/conflict/failed…). Pour les commandes, décliner les états sans faux succès :

- **Prêt** : objet disponible, capacités actuelles affichables.
- **Sélectionné** : changement de présentation local sans mutation.
- **Déplacement en cours** : projection flottante discrète + cible potentielle ; aucun changement métier encore réalisé.
- **À confirmer** : contexte et effet exact exposés si le risque le justifie.
- **En cours / En attente d'envoi** : attente et prévention double-submit ; contexte conservé.
- **Confirmé** : retour discret seulement après résultat autoritatif.
- **Refusé** : revalidation serveur, message humain, réconciliation.
- **Conflit** : signal explicite, rafraîchir/revoir ; jamais assimiler à panne réseau.
- **Hors ligne** : préserver les données acquises ; file d'attente seulement pour commandes supportées par l'owner et l'outbox.
- **Annulable** : action Annuler proposée uniquement tant que l'inverse existe et reste autorisée.

Le client ne confirme jamais Payment, Access, Capacity, Mandate, scanner, Readiness ou transition de cycle de vie sur la seule base d'une animation optimistic. Les erreurs apparaissent au plus près de l'action ; la notification globale est réservée aux problèmes transversaux.

La formulation visible reste courte : « Déplacer », « Vers… », « En cours », « Confirmé », « Impossible de déplacer », « Réessayer ». Ne jamais exposer owner, outbox, payload, projection, HTTP 409 ou jargon d'infrastructure.

## 8. Navigation et composition

- Web : première réponse HTML Django, HTMX/progressive enhancement ; URL directe, retour navigateur, scroll et focus préservés. Déjà défini : compact < 768 CSS px, adaptatif 768–1199, expanded >= 1200 ; ne pas forcer un double panneau à largeur insuffisante.
- Flutter : conserver les seuils de Presentation établis par MakoloLayout et les conventions du shell. Les gestes sont natifs ; les surfaces compactes peuvent utiliser des sheets avec SafeArea.
- Même information : Web expanded peut montrer un Inspect rail, mobile un bottom sheet ou une profondeur dédiée.
- Un retour ferme d'abord l'overlay, puis la profondeur ; ne réinitialise pas arbitrairement l'écran source.
- Recherche locale = corpus déjà acquis ; Recherche transverse = contrat owner-backed. Ctrl/Cmd+K existant reste un accélérateur de navigation Web, pas un substitut à la recherche globale et pas un clone du Makolo Mark.

## 9. Accessibilité, motion et confidentialité — obligatoires

1. Actions fondamentales au clavier, au toucher simple et au lecteur d'écran ; gestes de drag optionnels avec commande alternative.
2. Focus visible et restauré ; état selected/expanded/disabled annoncé. Pas de contrôle essentiel uniquement au hover.
3. Touch targets principales **48×48 dp sur Flutter** selon charte ; sur le Web conserver au minimum les **44 CSS px testés par l'E2E Objectives**, puis viser la même aisance tactile.
4. Contraste, taille de texte agrandie et ordre de lecture vérifiés en clair/sombre.
5. Mouvement fonctionnel, court, supprimé ou réduit avec Reduce Motion. Pas de confettis, inertie spectaculaire ni animation bloquante.
6. Haptique ponctuelle et significative, jamais de succès haptique définitif avant confirmation du serveur.
7. Preview, menu, drag ghost et annonces vocales : divulgation minimale, surtout en contexte Space partagé.
8. Aucune conservation croisée de sélection, destination, tri privé ou draft lorsque l'acteur change sans vérification de scope.

## 10. Critères de clôture du contrat

Une nouvelle interaction ne peut être validée pour implémentation que si : intention stable, différence avec les intentions voisines, capacité owner démontrée, alternative accessible, comportement hors ligne/refus documenté, parité des issues Web/mobile, méthode de restauration de contexte, registre d'icônes et tests prévus.

Les visualisations (chronologie, graphe causal, calendrier, tableaux d'états) ne sont **pas des primitives de mutation** : elles consomment les mêmes commandes et ne créent jamais de causalité/statut par déplacement visuel implicite.

**Ce contrat tranche la politique UX ; il ne prouve pas que les gestes avancés sont déjà livrés.**
