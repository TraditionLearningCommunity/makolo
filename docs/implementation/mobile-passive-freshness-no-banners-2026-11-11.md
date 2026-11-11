# Recette — sobriété des messages techniques dans les surfaces Makolo

**PR #522** — 11 novembre 2026. Portée : expérience de lecture Flutter. Pas de changement d'API, modèle, migration, sécurité ni mécanisme de synchronisation.

## Contrat UX appliqué

Quand une surface possède des données utiles déjà obtenues, **ne pas ajouter de phrase explicative** du type « informations à actualiser », « dernières informations affichées », « données disponibles hors ligne », « conservé sur l'appareil » ou « couverture partielle ». Le signal de connectivité du shell suffit. Une actualisation peut rester discrète.

Les exceptions indispensables restent visibles : droits révoqués, échéance imposant une revalidation de sécurité, erreur en l'absence de contenu, conflit métier, mutation non confirmée et états de chargement/vide réels. Les données privées ne doivent pas être révélées seulement parce qu'un cache existe.

## Sources modifiées

- `MakoloFreshnessNotice` partagé : masque uniquement les indications **passives** d'ancienneté/actualisation, pas les états `revalidationRequired` et `expired` ; la ligne de connectivité existante est conservée.
- `ProjectWorkspaceScreen` et `DossierWorkspaceScreen` : suppression des phrases « local / hors ligne » et du second bouton d'erreur d'actualisation sous un contenu déjà disponible. Bouton d'actualisation de l'AppBar, geste pull-to-refresh, contrôles source invalidée et restrictions de mutation inchangés.
- Profondeurs `SpaceInsightScreen` : disparition de l'explication de dernier état et de l'erreur répétée de recherche si des résultats sont déjà disponibles ; la recherche sans résultats garde un état d'échec compréhensible.
- `HistoryScreen` : disparition des explications sur le stockage et la mise à jour, en conservant dates, faits et action d'ouverture.
- `TransverseRetrievalScreen` : suppression de la note permanente « couverture partielle / hors connexion » et des notifications génériques quand des résultats sont visibles ; erreur de recherche conservée si aucun résultat.
- `PersonalProjectionScreen` : état d'absence neutre sans exposer le stockage local.
- `ProfileConnectionsScreen` : indication technique d'état obsolète retirée de la liste existante ; mutation toujours interdite si le serveur n'est pas fiable.
- Les comportements de Moi, Nous, Now, En cours et des écrans utilisant la primitive commune bénéficient de cette présentation sans recopier la logique.

## Recette et risques

- Basculer entre Moi et Nous, puis visiter Démarches, Projets, Dossiers, Historique, Relations et Recherche avec des données locales présentes et le réseau interrompu : le contenu reste lisible sans bannière explicative.
- Vérifier que toute action exigeant un retour serveur ne montre pas de confirmation avant sa décision.
- Vérifier qu'un changement de Profile/Space ou une permission révoquée invalide la projection comme avant.
- Vérifier les états vides et les erreurs en absence de données ; ne pas les masquer derrière la ligne réseau.
- Exécuter les tests Flutter ciblés et l'analyseur Flutter sur la branche avant intégration ; non exécutés ici faute de SDK Android/Flutter.
