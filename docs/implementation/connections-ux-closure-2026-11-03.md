# Connexions — expérience N2/N3 Web et Flutter (3 novembre 2026)

## Périmètre

Branche de travail : PR #522, sans nouveau domaine persistant ni modification directe de `main`.

Objectif : remplacer les cartes techniques et le dialogue de connexion surchargé par une expérience propriétaire, concise et navigable : **Découvrir → fiche N3 → connecter**, ou **Mes connexions → fiche N3 → gérer**.

Les captures Android transmises montrent des libellés très longs, des CTA compressés, un dialogue vertical trop dense et l'exposition de modes internes (Push/Payments) parmi les services externes. Cette passe traite la composition, sans attribuer de capacités fictives aux fournisseurs.

## Contrats propriétaires conservés

- `GET /api/v1/me/interoperability/` reste la projection Z16 personnelle et sa lecture local-first.
- Catalogue des fournisseurs connectables : `GET /api/v1/me/intelligence/connections/` et variante Space, géré par Intelligence.
- Écriture : `POST/PATCH/DELETE` Intelligence, sous portée Profile ou Space, avec consentement et revalidation serveur.
- La liste des connexions établies provient des `ProviderConnection` filtrées par propriétaire et de leur projection Z16.
- Les providers connectables ne sont **pas** des comptes externes déjà reliés. Le catalogue actuel reflète les adaptateurs Intelligence effectivement prévus côté serveur ; il ne constitue pas une marketplace ou une table générique de connecteurs en base.
- Les capacités `domain_integrations` restent du ressort de Notifications ou Payments et ne s'affichent pas comme des connexions externes.
- Aucune clé, URL d'endpoint interne ou identité de token n'est exposée dans les lectures ou dans les états persistés Flutter.

## UX livrée en source

### N2 — Découvrir et Mes connexions

- Listes de lignes compactes, marges stables, informations secondaires limitées à deux lignes, ligne entière navigable.
- Recherche et filtre par capacités dérivées du catalogue owner (pas de noms de fournisseurs codés en dur dans les vues clientes).
- Navigation adaptée aux petits écrans et au grossissement du texte, sans `SegmentedButton` rigide.
- Liste des connexions authentiquement observées, statut humain et accès au détail.
- Dernier état local lisible sans réseau ; mutation suspendue tant que le serveur/owner n'est pas confirmé.
- Rafraîchissement explicite du catalogue et du Z16 sans les confondre.

### N3 — Comprendre, connecter, gérer

- Écran Flutter défilable, espace pour les champs, action principale ancrée ; pas de dialogue de saisie complexe.
- Fiche alimentée par les champs réels du catalogue (`label`, `description`, `capabilities`, `requires_model`, `can_connect`).
- Consentement explicite et secret uniquement dans les contrôleurs temporaires du formulaire et la requête propriétaire.
- Connexion établie : statut Z16, capacités, désactivation/réactivation, rotation de clé, retrait après confirmation.
- La navigation vers Découvrir est exposée uniquement pour une connexion Intelligence utilisable avec une capacité pertinente ; aucun appel fournisseur automatique.
- Les résultats d'une écriture confirmée et d'une relecture Z16 ratée restent distincts.

### Web et Space

- Présentation Web responsive factorisée entre Moi et Nous dans `templates/interoperability/connection_experience.html`.
- Sélection de fiche N3 et filtres traités côté serveur par `interoperability/catalog_presentation.py`.
- Les connections Space restent filtrées et gouvernées par `space.manage` direct ; l'identité du Space et, lorsqu'il existe, le contexte de responsabilité restent dans la navigation.
- Les formulaires Web conservent CSRF, opérations owner et aucun reflet de secret. Retour vers Mes connexions après mutation.
- Pas de nouvelles routes de mutation universelles et aucun transfert implicite d'autorité.

## Vérifications

Tests sources ajustés/ajoutés : `mobile/test/intelligence_connection_controls_test.dart`, `mobile/test/c8_interop_mutation_refresh_test.dart`, `mobile/test/c7_intelligence_owner_continuity_test.dart`, `mobile/test/c7_space_owner_continuity_test.dart`, `mobile/test/interoperability_screen_test.dart`, `mobile/test/connections_n2_n3_layout_test.dart`, `core/test_w8_personal_interoperability.py`, `intelligence/test_connection_management_web.py` et `organizations/test_ws4_space_web.py`.

**Non attesté à cette étape :** exécution Flutter/Django, compilation Android, inspection réelle des mises en page sur téléphones et CI. L'utilisateur a demandé de ne pas s'occuper de la CI pour ce chantier. Les vérifications d'exécution et la réconciliation finale de la PR restent à effectuer avant tout merge ; aucune validation verte n'est prétendue.

## Invariants inchangés

- Profile personne globale ; Space exige son Mandate/Permission direct.
- Connection donne un canal ; Permission/Mandate donne l'autorité ; Action exécute un contrat ; owner garde la vérité.
- Une capacité disponible ne signifie pas connexion établie.
- Snapshot local = observation, jamais consentement, droit ou succès confirmé.
- Aucune migration, nouveau modèle générique Plugin, fausse intégration OAuth ni galerie de médias orphelins.
