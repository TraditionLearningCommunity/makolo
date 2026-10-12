# Mature Mobile Experience — reprise Codex

## Contrat de reprise

- Objectif : fermer les écarts réels des contrats de préparation, depuis le checkpoint Antigravity, sans reconstruire les surfaces déjà modifiées.
- Owner : Codex, intégrateur unique.
- Base : `0366d81203ee06937427f055d4d31f905172f849`, neuf commits depuis `f2351b8b5db1ce362b7ddc6ca2951d9d79ce2538`.
- Branche : `feature/mature-mobile-composition` ; `origin/main` encore à la base au démarrage ; aucune PR ouverte (API GitHub).
- Surfaces : projections Organizations, Presentation/Flutter Space, routes propriétaires, tests ciblés, documentation de convergence.
- Interdits : modèles/tables/migrations, nouvelle autorité, données inventées, refonte du thème/sync, modification de main, push intermédiaire, merge automatique.
- Acceptation : profondeurs réellement accessibles et revalidées, provenance/limites visibles dans Piloter, relations distinctes, absence/fraîcheur/révocation honnêtes, contrats compatibles.
- Évidence : tests Django d'autorisation/sélection et Flutter de navigation/présentation/acteur ; formateur canonique, analyse, Goldens pertinents et gates finaux.
- Gate : validation locale puis push final unique, PR et CI verte ; aucun merge automatique.

## A — Space Now / Découvrir

`space_attention_projection.py`, `workspace_projection.py`, `space_work_projection.py` et les tests ZS6 distinguent visibilité du portefeuille et sélection attentionnelle. Les permissions autorisent la lecture des objets, mais ne définissent ni pertinence collective, ni pourquoi maintenant, ni prochain mouvement, ni admission de possibilités pour un Space. Le selector personnel Discovery ne porte pas ce contexte collectif.

La composition du portefeuille Métier ne peut donc pas devenir une sélection Now/Discover par renommage. `selection.unavailable / no_safe_selection_contract` reste conservé, avec `items=[]` ; ce n'est pas une preuve de calme ou de champ vide. Le blocage précis est l'absence d'une politique de sélection collective établie, scopée par mandat/perspective, portant les raisons et les destinations autorisées. Aucun modèle ni politique métier n'est inventé pour la contourner.

## B–D — écarts confirmés

- Métier : les huit grammaires existent côté serveur ; les cartes enrichies d'Antigravity sont conservées. Les liens d'approfondissement restent absents de l'interface hors Jour J ; les collections bornées doivent afficher leur couverture.
- Relations : recherche/sélection propriétaire existent ; Flutter aplatit les owners et ne permet pas d'approfondissement. Ne pas fusionner deux relations vers un même Profil.
- Piloter : le serveur livre preuves, raison, incertitude, couverture et date ; Flutter ne montre que titre/résumé et clés techniques des mesures.
- Transversal : `SpaceRetrievalOwnerScreen` existe mais sa destination n'est pas montée dans le router ; fermeture nécessaire à la recherche/historique et aux handoffs Métier/Relations.

La validation visuelle sur appareil n'est pas attestée par le transfert.

## Checkpoints vérifiés

- Projections Métier : sélection par identité avant les limites d'aperçu, avec les mêmes selectors et permissions ; pagination par section (20 éléments), offset borné ; refus des identités étrangères/malformées et des sections non visibles. Une lentille Activity n'expose pas les routes/véhicules collectifs. Les lieux et arrêts viennent des relations Geography/Transport existantes, avec prefetch.
- Profondeurs Flutter : destination propriétaire Space montée pour Métier, Recherche, Historique et Relations ; relecture serveur avec responsabilité courante. Les liens Activity et Jour J restent distincts. Présentation MPS d'une Activity revalidée avant utilisation ; échec explicite, sans ancien artifact affiché après refus.
- Continuation Métier : pages éphémères, sans nouveau store/sync ; retry au même offset, déduplication par identité propriétaire, contenu conservé sur erreur technique et retiré sur refus/changement d'acteur.
- Piloter : signaux avant mesures ; preuve, source, date, couverture bornée, raison et incertitude visibles. Zéro, inconnu et données insuffisantes restent distincts ; montants par devise seulement avec capability financière. Aucun calcul de tendance/causalité inventé.
- Relations : propriétaires conservés séparément, même si un Profil apparaît plusieurs fois ; aperçu et recherche distante distingués, résultats tardifs écartés, sélection revalidée au détail.
- Snapshot : SourceState, fraîcheur et date d'observation utilisés sur les racines et insights ; refus/révocation distincts du vide métier, snapshot expiré non exposé.
- Convergence : destination personnelle des commandes raccordée à l'écran propriétaire déjà présent ; corrections des contrôles null impossibles dans les commits repris, sans supprimer leurs comportements.

Le premier checkpoint de formatage a appelé par erreur le binaire direct Dart 3.11.5 du SDK cassé `C:/src/flutter`, malgré son lanceur redirigé vers 3.13.3. L'appel corrigé passe par le SDK actif `C:/src/flutter_3473` (Flutter 3.47.3 / Dart 3.13.3). Les modifications de formatage étrangères au chantier ont été annulées par le vrai formateur, sans reset et sans modifier les neuf commits repris.

Validation intermédiaire : 113 tests Django (Space ZS3/ZS4/ZS6, History/Search Space, contrats personnels Z1/Z2/Z4/Z5/Z6) et 485 tests Flutter hors Goldens réussis. Vérification de migrations : aucune modification détectée. Contrat OpenAPI : 12 opérations requises conservées ; 8 fixtures C0 valides.
