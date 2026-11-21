# Groupe 2 — Migration transversale des pages secondaires Web + Flutter

**Branche de travail :** `fix/discover-a-continuation-context-20261014` — PR #522.  
**Statut :** implémentation de présentation intégrée ; vérification à l'exécution et revue visuelle non revendiquées.  
**Références :** `00-audit.md`, `01-interaction-contract.md`, `02-primitives-catalog.md`, `03-validation-matrix.md`, `04-foundation-implementation.md`, `05-foundation-f2.md` et `06-group1-principal-surfaces.md`.

## 1. Délimitation

Conformément au plan F1, le **Groupe 2** porte sur les surfaces **personnelles secondaires** accessibles depuis les cinq entrées principales : collections, listes et détails, paramètres, recherche, Dossiers/Projets, ressources et conversations. Il comprend également les écrans auxiliaires réellement associés à ces parcours : veilles, enregistrements, notifications, accès, Passeport et préférences.

**Le Groupe 3 reste distinct** : profondeur N1/N2/N3 métier, consoles des Espaces, tableaux opérationnels et Jour J. Modifier ici un lien de navigation vers un niveau profond ne signifie pas que le niveau profond lui-même est migré.

La fondation reste unique : `static/css/makolo-interactions.css` + contrôleurs F1/F2 pour le Web et `mobile/lib/design/action_controls.dart`, `interaction_primitives.dart`, `interaction_f2.dart` pour Flutter. **Aucune page ne doit introduire sa propre variante générique de bouton ou son propre moteur de permissions.**

## 2. Surfaces Web prises en charge

| Ensemble | Chemins utilisés / écrans | Migration |
| --- | --- | --- |
| Démarches, accès, historique et recherche personnelle | `templates/core/participant_journey_{list,detail}.html`, `participant_access_{list,detail}.html`, `participant_history.html`, `personal_transverse_search.html` | Actions globales ; champs de recherche/filtre communs quand l'ancien champ était local ; GET et ordre serveur conservés |
| Choix de Moi et connexions | `templates/core/participant_me_considerations.html`, `personal_connections.html`, `templates/interoperability/connection_experience.html` | Liens/onglets/commandes partagés ; styles Connections limités à la composition, dans `personal-connections-layout.css` |
| Découverte secondaire | `templates/discovery/bookmarks.html`, `watch_{list,create,detail,edit}.html`, `for_you.html`, `my_events.html` | Actions, retours, filtres et pagination réutilisables ; aucun classement client inventé |
| Profil, compte et préférences | `templates/accounts/{profile,settings,account,account_switcher,password_change}.html`, notifications | Boutons normalisés ; paramètres avec formulaires POST et CSRF inchangés ; couleurs d'actions non redéfinies |
| Bibliothèque et documents | `templates/personal_assets/{list,detail,form,reuse,use_in_journey,save_artifact}.html` | Recherche et filtres propriétaires, téléchargements et actions de conservation réutilisent le socle ; aucune nouvelle permission |
| Conversations | `templates/conversations/{list,detail,history,exchange,_composer,_rich_composer}.html` | Actions secondaires, décisions d'invitation, recherche de Points, composants d'envoi et divulgations ; les formulaires owner restent natifs |
| Dossier et Projet | `templates/objectives/organizer.html`, `objectives/templates/objectives/{dossier,project}_{list,form,detail}.html` | Variantes partagées primary/secondary/ghost/link, boutons de dialogue ; CSS de workspace borné à la disposition ou à un fallback non migré |
| Autres entrées secondaires personnelles | Notifications, billets, suivi, partages du Passeport, groupes personnels et connexions interopérables | Application des mêmes variantes communes, avec conservation des actions sensibles proprement autorisées |

Les dossiers `static/css/objective-organizer.css`, `dossier-workspace.css` et `project-workspace.css` référencent désormais les tokens globaux `--mk-*` et réservent les anciennes règles de boutons aux éléments **sans** `mk-action-button`. Les feuilles de composition sont chargées dans `extra_css` du shell, et non injectées dans le contenu de la page.

Le CSS de Connections ne crée aucun style de bouton ; il règle uniquement les lignes, la grille et le contexte. Le même principe vaut pour les sections légitimes de Moi et des Dossiers.

## 3. Surfaces Flutter prises en charge

| Ensemble | Fichiers / exemples | Intégration |
| --- | --- | --- |
| Compte, profil et Passeport | `features/settings/change_password_screen.dart`, `notification_preferences_screen.dart`, `features/me/me_profile_screen.dart`, `me_passport_screen.dart`, `me_passport_visibility_screen.dart` | `MakoloActionButton` primary/secondary/quiet/danger selon intention ; `MakoloIconActionButton` pour actions iconiques accessibles ; confirmations destructives explicitement distinctes |
| Enregistrements, veilles, collectifs et suivis | `features/me/me_saved_screen.dart`, `me_collectives_screen.dart`, `me_follows_screen.dart`, `features/discovery/discovery_watch_{screens,create}.dart` | Créer, enregistrer, retrouver, paginer et réessayer avec les contrôles communs |
| Ressources et historique | `features/resources/{resources_screen,resource_detail_screen}.dart`, `features/continuity/history_screen.dart`, `conversation_history_screen.dart` | Retry, actualiser, télécharger, réutiliser et continuer ; attente et refus conservés |
| Recherche transverse | `features/continuity/transverse_retrieval_screen.dart` | Champs et filtres owner-backed ; sélections temporelles avec contrôles communs ; pas de tri universel F2 appliqué à un corpus serveur incomplet |
| Dossier, Projet, organisateur | `features/continuity/{objective_organizer_screen,objective_collection_screen,objective_create_screen,dossier_workspace_screen,project_workspace_screen}.dart` | Actions conditionnelles `_cap` / `_has` conservées ; seuls leurs rendus sont harmonisés ; aucun nouveau transport métier |
| Conversations et parcours | `features/continuity/{conversation_screens,conversation_context_screen,conversation_form_sheet,conversation_history_screen}.dart`, `features/journey/journey_detail_screen.dart` | Actions des Points, confirmations, invitations, navigation et continuation via les mêmes composants |
| Accès et aperçus secondaires | `features/access/access_collection_screen.dart` et contrôles mobiles associés | Actions d'inspection, retour et retry harmonisées sans création ni validation locale de droit d'accès |

Le composant `MakoloActionButton` **compose le thème Material Makolo**, ne remplace ni le routeur, ni les services métier, ni le mécanisme de synchronisation. Les cas sensibles (révocation de lien, refus d'invitation) conservent leur consentement et leur voie de confirmation. Les contrôles personnalisés déjà sémantiques (orbite de sauvegarde, scan, preview média, pass de transport) restent spécialisés.

## 4. Grammaire transversale : règles non négociables

1. **Identité et permission** : seules les actions autorisées par le propriétaire sont présentées ; chaque POST/API revalide rôle, mandat, source et destination. Le rendu ne devient pas une autorisation.
2. **Recherche et tri** : liste propriétaire ou paginée = GET/API existant, pas un `makoloFilterLocal` appliqué à un corpus partiel. `mk-interaction-field` ne fait que styler le champ.
3. **Lien, déplacement, transition, révocation** : ne jamais déduire de transport générique à partir d'un bouton ; mêmes commandes owner que les formulaires/clients existants, sans faux Undo.
4. **Etats et retour** : pending, échec, conflit et hors ligne restent fidèles à la source ; pas de succès avant confirmation. URL, focus et scroll de reprise conservés quand le propriétaire les fournit.
5. **Accessibilité** : labels des icônes, cible Web 44 px / Flutter 48 dp, commandes clavier, contraste, SafeArea, réductions de mouvement ; les alternatives au glisser-déposer restent obligatoires.
6. **Données sensibles** : aucun élément privé n'est exposé par une liste de destination, un menu ou une prévisualisation hors du scope acteur.
7. **Zéro système parallèle** : pas de deuxième set de tokens, de routeur, de CSS bouton par page, de projet/ticket/access parallèle dans `events`.

## 5. Tests ajoutés

- `e2e/specs/interaction-group2.spec.mjs` : chargement global sur les routes secondaires, recherche GET propriétaire, champs partagés, continuité des formulaires POST/CSRF, Dossier/Projet et cibles Web compactes.
- `mobile/test/secondary_owner_action_controls_test.dart` : action primary/secondary, désactivation par capability, menu filtré par owner, apparence destructive et prévention des doubles validations pendant l'attente.

Les tests de domaine existants demeurent inchangés. Ce chantier ne supprime ni n'affaiblit leurs assertions. **Conformément à la priorité demandée pour ce lot, aucun état de CI n'est revendiqué ici.** L'intégration est sur la branche #522, sans merge dans `main`.

## 6. Critère de sortie et suite

La migration de **présentation commune des surfaces secondaires** est distincte de l'implémentation d'une nouvelle capacité métier. Les commandes métier ne sont branchées que si elles existent déjà et sont autorisées. Les styles de composition par écran restent permis : une architecture sans tout CSS local n'est pas le but ; le but est **zéro duplicat des composants communs**.

Prochaine famille : Groupe 3 (N1/N2/N3, Space métier, Jour J), avec audit de profondeur, densité et rôle pour chaque surface, **sur la même branche de la PR #522** selon la décision du projet. Aucun nouveau chantier de groupe ne doit écraser les modifications existantes.


## 7. Contrôle statique final du périmètre

La lecture des templates du Groupe 2 confirme l'absence de l'ancienne classe `mk-btn` dans les listes personnelles Journey/Access/History/Search, les écrans secondaires de veilles et les principales pages Conversation inspectées. Les boutons d'icône `mk-icon-btn` de retrait des enregistrements sont **conservés** : c'est déjà un contrôle global avec son libellé accessible, pas une duplication propre à Bookmarks. Les écrans Dossier/Projet conservent des boutons de vues (`aria-pressed`) et des formulaires owner : ne pas confondre leur présentation spécialisée avec de nouveaux droits.

La lecture statique vérifie des classes et chemins réellement modifiés, **pas** l'exécution des tests, les captures d'écran, la validation de permissions serveur, ni l'état de production. Les styles de composition locaux sont légitimes tant qu'ils ne redéfinissent pas les primitives partagées.


## 8. Normalisation complémentaire des contrôles secondaires

- Les filtres de l'Historique personnel, de la Bibliothèque et de la liste des Conversations utilisent maintenant la barre d'onglets partagée avec `aria-current="page"`. Ces onglets restent des liens vers les vues serveur : ils ne trient ni ne filtrent artificiellement le corpus.
- Les suppressions de veilles et de compte utilisent la variante destructive commune ; la requête est toujours propriétaire et protégée côté serveur.
- Le sélecteur de comptes a été ajouté au périmètre : composition extraite de `templates/accounts/account_switcher.html` vers `static/css/account-switcher-layout.css`, chargée dans le head. Le retour et l'ajout de compte utilisent la variante partagée `inverse` sur fond violet, avec focus à contraste élevé. Aucun CSS inline de bouton propre à ce template ne subsiste.
- Le test Web transversal de Groupe 2 inclut les filtres GET liés à Historique/Bibliothèque/Conversations et le sélecteur de comptes avec son formulaire POST/CSRF.

La variante Web `data-variant="inverse"` est définie dans `makolo-interactions.css` pour toute surface de marque à fond sombre. Elle n'appartient pas au Sélecteur de comptes. Le responsive et les compositions de cette page restent locaux, sans redéfinition des boutons.

## 9. Derniers reliquats clôturés après revue

La vérification des écrans actuels de #522 a conduit à achever les usages communs sans déplacer dans ce groupe les profondeurs N1/N2/N3 du Groupe 3.

- **Groupes personnels Web :** la page de détail utilise maintenant les actions globales pour navigation, adhésion, demande, éligibilité Activity et archivage. Les conditions de rôle et les formulaires POST/CSRF demeurent propriétaires.
- **Billetterie Web :** la page de commande applique les variantes communes aux actions réservation, paiement, annulation et code promotionnel, en conservant Commerce et Payment comme propriétaires.
- **Passeport émis Web :** les pages HTML autonomes d'historique et de lien émis chargent explicitement les styles communs. Création/copie/révocation adoptent les mêmes contrôles ; les révocations conservent POST et CSRF. Le Passeport de document imprimable conserve volontairement sa présentation de sortie spécifique.
- **Notifications Web :** pagination complétée, onglets natifs et actions de lecture maintenus.
- **Flutter profil et Passeport :** recherche de personnes, confirmation, reprise, barre d'outils et édition utilisent les actions communes, sans toucher à la confidentialité.
- **Flutter historique et recherche :** les commandes retry/search/pagination/inspection adoptent les contrôles globaux ; les recherches restent owner-backed.
- **Flutter conversations et veilles :** les réponses simples, l'édition et les confirmations destructives réutilisent les composants communs sans modifier les callbacks, la sélection ou les services.
- **Flutter Journey et création :** les handoffs propriétaires sont harmonisés ; les contrôles de dates et les actions d'édition ne créent aucune mutation métier générique.

Les interactions spécialisées (orbit de sauvegarde, champs à choix multiples, médias, QR, calendrier et document imprimable) demeurent spécialisées et ne constituent pas une deuxième bibliothèque de boutons. Le Groupe 3 garde les profondeurs métier, consoles Space et Jour J.

Les parcours complémentaires Groups/Tickets et l'historique privé des émissions de Passeport sont ajoutés aux tests E2E du Groupe 2. Ces tests ne sont pas déclarés exécutés.

**Sortie d'implémentation :** la migration commune du Groupe 2 est intégrée et documentée sur la branche de #522, sans merge. La prochaine étape est le Groupe 3.
