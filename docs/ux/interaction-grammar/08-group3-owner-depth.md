# Groupe 3 — Profondeurs propriétaires N1/N2/N3 et Space

**Branche :** `fix/discover-a-continuation-context-20261014`, PR #522.  
**Statut :** migration transversale engagée, partiellement implémentée ; consoles métiers spécialisées et certaines commandes contextuelles encore à compléter.  
**Dépendance :** contrats A–D, F1, F2 et Groupes 1–2.

## Règle d'architecture

Les actions communes (primary, secondary, quiet/ghost, link, danger), les disclosures natifs et le feedback conservent une implémentation commune. Les écrans propriétaires gardent leur sélection d'actions, leur ordre métier, leurs habilitations, leur route de navigation, leurs formulaires POST/CSRF et leur vérité autoritative. L'UI ne fabrique aucun Access, ticket, ordre, paiement, état Journey ni relation de type Activity.

Groupe 3 comprend les profondeurs personnelles, Space Work, Space US, les consoles métiers et les opérations Jour J / Live / Scanner ; l'existence d'un menu ne prouve ni une autorisation ni un transport de mutation.

## Migration Web réalisée à ce stade

- `templates/core/_now_n2_focus.html`, `templates/discovery/{possibility_detail,activity_detail}.html` : accès N2 et CTA owner communs.
- `templates/organizations/space/{work,work_depth,work_g2_depth,work_g3_depth,work_g4_depth,work_g2_create,work_g3_departure_operations,work_g3_offer_form,now,day_of,live,scanner,base}.html` : variantes globales ; navigation, pagination et actions owner conservées.
- `templates/organizations/console/{base,services,scanner,access}.html` et `templates/scanner/{home,console,log_list}.html` : actions communes, including scanner controls by their unchanged IDs.
- `static/css/makolo-interactions.css` : un contrôle `hidden` reste réellement masqué ; `mk-action-hint` est un indicateur non interactif à utiliser dans une carte déjà cliquable, sans inventer un second bouton.

Les libellés « Ouvrir » dans les cartes Space qui possèdent déjà un lien ont été transformés en indicateurs passifs. Les composants de choix de date, de carte, de QR, de formulaire spécialisé ou d'outil de scan restent du ressort du propriétaire.

## Migration Flutter réalisée à ce stade

Les fichiers suivants adoptent `mobile/lib/design/action_controls.dart`, sans modifier leurs callbacks ou leurs transports :

- `features/space/space_work_{surface,g2_depth,g3_depth,g4_depth,offer_editor_screen,create_activity_screen}.dart` : création / édition G1–G4, pagination, handoff propriétaire et recherche.
- `features/space/space_transport_{create_screen,departure_operations_screen}.dart` : création, confirmations réelles, recherche de destinations, pagination, reprogrammation, annulation destructive.
- `features/space/space_{occurrence_screen,request_screen,service_case_screen,documents_screen,document_detail_screen}.dart` : inspection, approbation/refus, service case, versions, partage et révocation.
- `features/space/space_{us_resources_screen,us_settings_screen,passport_screen,passport_visibility_screen,insight_screen}.dart` : ressources, autorisations, profil d'Espace, export et partage.
- `features/continuity/{dossier_workspace_screen,project_workspace_screen}.dart` : confirmation générique partagée, sans nouveau service Dossier/Projet.

La voie d'annulation est représentée comme `danger` lorsque cela correspond à une révocation/annulation destructive confirmée ; aucune compensation automatique n'est présumée.

## Non-régressions contractuelles

1. Les actions de Space restent invisibles si les capacités `can_manage_offer`, `can_manage_operations`, `canDecide`, etc. ne sont pas rendues par le propriétaire.
2. Les collections paginées demeurent server-backed. Pas de tri local du corpus partiel.
3. Scanner : `#start-camera`, `#stop-camera`, `#toggle-flash`, `#scan-next` restent disponibles aux scripts propriétaires. `#scan-next.hidden` ne peut pas être forcé visible par un CSS de bouton global.
4. Les formulaires POST/CSRF, les confirmations et leur sens restent inchangés.
5. Flutter : les `MakoloActionButton` ne confirment pas une mutation ; leurs callbacks restent owner-bound. Les icônes seules imposent un tooltip et une cible d'au moins 48 dp.
6. Les consoles Space qui ne représentent que des faits ou des liens n'ont pas besoin de composants de mutation génériques.

## Contrôles ajoutés

`e2e/specs/interaction-group3.spec.mjs` couvre le chargement du socle, le Web compact, la présence des actions Space et l'absence d'exposition prématurée des commandes du scanner. Les tests Flutter existants `mobile/test/space_work_g2_depth_test.dart`, `space_work_g3_depth_test.dart`, `space_work_g4_depth_test.dart`, `space_work_surface_test.dart` vérifient l'affichage owner-capability et le routage des callbacks.

**Ces tests ne sont pas présentés comme exécutés.** La migration des consoles et des profondeurs les plus spécialisées reste à poursuivre avant de conclure que le Groupe 3 est entièrement implémenté.

## Reliquat identifié

Poursuivre l'inventaire des vues `templates/organizations/console/*`, `templates/organizations/space/*` non encore harmonisées, des écrans Flutter Dossier/Projet et des commandes métier à forte densité. Ne pas remplacer leurs composants spécialisés ou leur autorité par un bouton ou un moteur générique pour maximiser un taux de migration.

## Complément : consoles Space et Passeport

La seconde passe du Groupe 3 a harmonisé les contrôles owner des consoles `organizations/console/{team,payments,operations,activities,settings,orders,requests}.html` : création, navigation de niveau, recherches, filtrage et retraits. L'appartenance à une équipe ne donne toujours aucun droit de Mandat par elle-même ; les formulaires de retrait sont inchangés. Les filtres restent GET et les actions autoritatives restent des POST propriétaires.

L'écran Flutter `features/space/space_passport_screen.dart` réutilise maintenant les mêmes actions du thème pour publication/partage, export, confidentialité, recherche et révocation, en respectant le périmètre Espace, les capacités projetées et les confirmations existantes. Aucun jeton ni détail privé n'est ajouté dans une URL publique.

Un seul socle de contrôle ne signifie pas une surface unique : les panneaux Space, les documents et le scanner gardent leur composition et leurs éléments dédiés.

## Complément — retrieval Space et contrat Flutter

- `templates/organizations/space/{discover,retrieval,retrieval_owner_detail}.html` réutilise les contrôles de navigation, recherche, retour et pagination. Le formulaire de recherche transverse reste responsable de son classement et de son périmètre d'accès ; aucun tri local F2 n'est forcé sur ces résultats.
- `templates/organizations/console/team.html` possède désormais des variantes de contrôle communes pour gérer les équipes, inviter, rechercher, naviguer et retirer. La variante danger marque un retrait sans bypass des formulaires POST ni des validations du propriétaire.
- `mobile/test/interaction_group3_depth_test.dart` confirme à l'échelle widget que l'action owner d'une offre n'apparaît qu'avec la capacité correspondante et que la pagination G3 utilise la commande partagée tout en transmettant le bon offset au propriétaire.

Ces éléments complètent l'intégration sans signifier que toutes les consoles et les profondeurs spécialisées sont déjà migrées.
