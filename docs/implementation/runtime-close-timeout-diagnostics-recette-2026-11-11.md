# Recette — timeouts réseau et cycle de vie du runtime (PR #522)

**11 novembre 2026 ·** Correction interne sans modification des modèles métier, routes API, UI, mécanismes de synchronisation, outbox ou migrations.

## Diagnostic confirmé

- L'émulateur et Django étaient joignables pendant le diagnostic Copilot. Les timeouts Dio ne sont pas attribués à un endpoint unique; ne pas augmenter arbitrairement la limite de 15 secondes.
- Drift crée naturellement une base publique et une base par Profile avec exécuteurs distincts. L'avertissement « plusieurs MakoloDatabase » n'est pas, à lui seul, une preuve de partage de l'exécuteur ou de corruption.
- Le provider fermait le runtime précédent sans attendre avant de reconstruire le public store. Une invalidation d'authentification pendant une initialisation pouvait aussi laisser une instance ouvrir après dispose.

## Corrections

1. **Barrière de fermeture** `RuntimeCloseBarrier` : chaque nouveau runtime attend la fermeture **complète** du précédent avant d'ouvrir les fichiers. Le callback `ref.onDispose` est enregistré avant la fin d'initialisation. Une initialisation échouée ne laisse aucun runtime construit à fermer; un échec réel de fermeture ne permet pas de rouvrir silencieusement les mêmes fichiers. Tous les flux sont asynchrones et la couche UI continue de montrer son état de chargement existant.
2. **Transport HTTP** : les appels JSON, téléchargements et images mesurent leur durée via `Stopwatch`. Sur timeout de connexion, d'envoi ou de réception, un **événement dans le journal de debug uniquement** indique la phase, la méthode, la famille de route et la durée. Le journal ne contient ni URL complète, ni query string, ni identifiant d'Espace/Profile, ni header, ni body, ni token. Les exceptions `TimeoutException`, `MakoloTransportError`, la logique de refresh 401 et l'idempotence restent inchangées.
3. **Tests** : transitions normales et rapides, erreur de construction, échec de fermeture dans `runtime_close_barrier_test.dart`; conversion des trois phases Dio vers `TimeoutException` dans `api_client_test.dart`.

## Recette

- Démarrer sur l'émulateur sans `All Exceptions` ; `Uncaught Exceptions` peut rester activé.
- Naviguer vers Notre équipe et répéter le scénario : vérifier dans la console de debug si un événement `makolo.network` décrit la famille et phase d'une requête de plus de 15 s. Aucun message technique ajouté dans l'interface.
- Basculer Profile → Space → Profile (sans changer de compte), puis se déconnecter et se reconnecter, et vérifier la conservation des données privées et des brouillons.
- Changer de compte/Profile si disponible, vérifier que les données de l'ancien Profile ne se présentent pas dans le nouveau et qu'aucun chevauchement d'ouverture du fichier public n'apparaît.
- Si un ANR survient sans arrêt du débogueur, collecter la trace du thread UI : les timeouts ne prouvent pas la cause des ANR.
- Ne pas désactiver l'avertissement Drift : il peut se produire du seul fait de bases distinctes.

**État de validation** : revue statique et tests de régression ajoutés. Le SDK Flutter n'est pas accessible dans l'environnement GitHub de cette intervention, donc les tests Flutter, l'analyseur et les tests Android ne sont pas déclarés exécutés.
