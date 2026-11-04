# Discovery — Étape 6 : mesures et clôture du volet serveur (2026-11-04)

## Portée

Branche existante de PR #522 : `fix/discover-a-continuation-context-20261014`.
Le but est une acquisition utile et plusieurs représentations (N1, Carte, N2/N3) sans dupliquer l'autorité métier, ni supprimer de faits, de permissions ou de Resources.

**Statut :** optimisation N+1 serveur mesurée et validée localement ; étape 6 globale en attente de validation Flutter/Android, d'un contrôle d'équivalence figé et du statut CI. Les résultats ci-dessous viennent des commandes exécutées par l'opérateur sur son serveur local : ils ne sont pas une exécution CI et ne représentent pas une production.

## Référence et résultat

| Indicateur | Avant | Après |
| --- | ---: | ---: |
| HTTP N1 seul, médiane 5 essais | 2693,5 ms | 1011,6 ms |
| HTTP N1 + spatial_index enrichi, médiane | 5082,0 ms | 2725,2 ms |
| HTTP page 2, médiane | 3135,8 ms | 1004,0 ms |
| SQL, mesure après identification des N+1 | 966 | 102 |
| Taille réponse N1 seul | 234,1 KiB | 152,5 KiB |
| Taille réponse N1 + Carte | 2695,6 KiB | 2778,6 KiB |
| Projection interne N1 + Carte, médiane | 4301,7 ms | 2694,6 ms |
| Sérialisation JSON interne, médiane | 45,6 ms | 49,4 ms |

Les mesures initiales comptaient 794 candidats dont 491 cartographiables. Les dernières mesures en comptent **793 dont 485**. Les données de démonstration et l'éligibilité temporelle ont évolué pendant le chantier : **ne pas interpréter les comptes comme une preuve d'équivalence identité-à-identité**. Un test figé doit vérifier cette propriété avant toute fermeture définitive.

## Origines corrigées

1. `preparation/services.py` et `discovery/api/composition.py` : l'éligibilité Group est résolue une fois pour la collection, et transmise au service propriétaire de la vérification des Resources (qui conserve ses autres contrôles d'autorité). ~485 requêtes répétitives ont disparu lors du profilage.
2. `discovery/unified.py` : les relations verticales liées aux Services sont chargées par lot avant leur représentation, évitant ~380 accès répétés.
3. `discovery/search.py` : préchargement des relations `funding_details` et `obtention_details` pour les Occurrences.

Tests ciblés exécutés localement (5/5 OK) :

```powershell
python manage.py test discovery.test_stage6_prefetch discovery.test_stage6_service_prefetch preparation.test_stage6_bulk_resource_gate --keepdb
```

Mesures reproductibles :

```powershell
.\scripts\makolo_etape6_diagnostic_serveur.ps1
python manage.py shell -c "exec(open('scripts/discovery_stage6_profile.py', encoding='utf-8').read())"
python manage.py shell -c "exec(open('scripts/discovery_stage6_sql_origins.py', encoding='utf-8').read())"
```

## Ce qui reste à faire sans nouveau grand audit

1. **Validation fonctionnelle à données figées** : comparer les identités, la représentation, les permissions, les Resources et les champs spatiaux avant/après avec le même jeu de données et le même viewer, pour visiteur et Profil. Les comptes mouvants n'attestent pas cette équivalence.
2. **Flutter sur appareil** : mesurer un parcours N1 → Carte → N2 → retour Carte/N1 → N3, distinguer cold/warm, vérifier le nombre d'appels HTTP, le stockage local par Profil, le décodage et la réutilisation du `spatial_index`, sans cache Carte séparé ni téléchargement systématique.
3. **Fluidité Carte** : 485 points sur le jeu local courant ; vérifier latence de rendu, pan/zoom, mémoire et absence de jank sur appareil, sans rétrécir artificiellement le périmètre des possibilités.
4. **Conservation des acquis** : tests Flutter ciblés et analyse sur les fichiers touchés, puis statut CI vérifié pour le HEAD courant de #522. Ne pas merger avec CI rouge.

## Non-objectifs et invariants

- Ne pas réduire les détails N2/N3, masquer des Resources ou retirer des lieux pour faire baisser le poids JSON.
- Ne pas déplacer la responsabilité des Permissions, Mandates, Access et faits propriétaires dans Flutter.
- Ne pas créer de nouveau cache métier indépendant pour la carte.
- Ne pas modifier les migrations de démonstration, les fichiers privés locaux ni les autres chantiers concurrents de la PR.
- La compression HTTP n'a pas été observée sur le serveur local (absence de `Content-Encoding`) ; cela reste une optimisation de transport distincte, non une preuve de compression désactivée dans tous les environnements.
