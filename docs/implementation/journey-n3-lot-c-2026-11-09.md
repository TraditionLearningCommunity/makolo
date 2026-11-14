# Journey N3 — Lot C : fiabilité, finition et validation

**Dépôt / PR :** `TraditionLearningCommunity/makolo` #522  
**Branche :** `fix/discover-a-continuation-context-20261014`  
**Date :** 9 novembre 2026  
**Portée :** C8, C9, C10 — à la suite des lots A/B, sans recréer les propriétaires.  
**Statut :** modifications poussées sur #522, aucun merge ; exécution complète Flutter/Django et validation sur appareil non revendiquées.

## Règles UX conservées

- Journey est une profondeur propriétaire unique, pas une déclinaison de Notifications, Conversations, En cours ou Moi.
- Le résultat recherché et la situation connue précèdent les moyens techniques.
- Local-first est **la manière de lire la BDD du Profil**, pas un « mode hors ligne ». La mince ligne d'état réseau du shell suffit.
- Aucune explication de serveur, cache, synchronisation ou file d'attente technique dans le contenu Journey.
- Les étapes, exigences, résultats, paiements, accès et capacités ne sont pas fabriqués par la Presentation.
- Aucun changement de route depuis Notifications ou Conversations, aucun modèle parallèle, aucune migration.

## C8 — Fiabilité local-first

### Lecture et autorité

- `JourneyDetailSelector` refuse toute projection dont la source porte une révocation explicite (`permission_denied`, `not_found`), y compris pendant un court décalage entre flux local et état du propriétaire.
- Une erreur de transport non révocatoire ne masque pas la projection déjà acquise.
- Les flux de Journey et Preparation sont isolés par Profil et clé ressource ; le changement de Journey ou de Profil réinitialise la situation visible, ses actualisations et les réponses d'invitation en vol.
- Les callbacks d'actions asynchrones ne peuvent pas reporter le résultat d'un ancien Profil sur le nouvel écran.

### Fichiers Preparation

- Les fichiers privés acquis sont retrouvés par leur FileRecord du Profil après redémarrage, sans nouvelle requête réseau.
- « Ouvrir le document » utilise le fichier privé ; « Enregistrer une copie » est distinct et volontaire (export vers Téléchargements).
- L'identité des bytes inclut la **version** de la ressource. La version 1 préserve l'identifiant historique et les fichiers déjà acquis ; les versions suivantes ne sont pas substituées par des octets périmés.
- Les états d'ouverture et de téléchargement sont isolés du Profil en cas de changement pendant une opération.
- La profondeur Resource/Requirement garde le contenu local lors d'un échec réseau, mais masque une projection explicitement révoquée.

### Paiement et commande

- Le N3 continue à afficher les obligations composées à partir de leur statut propriétaire, **pas du dernier statut d'une tentative de paiement**.
- Le détail Payment et le détail Commerce peuvent lire un résumé non actionnable déjà acquis via la projection Journey du même Profil.
- Une lecture propriétaire confirmée remplace cette observation. Un refus 403/404 retire le résumé.
- Aucun bouton `pay`, montant confirmé, commande acquittée, ou transition métier n'est déduit de ce résumé local. Les mutations sensibles restent celles du propriétaire.

## C9 — Finition Web / Flutter

- Le bloc objectif Flutter est conservé dans la palette Makolo. Les contenus de N3 ont une largeur de lecture bornée sur écrans larges, avec la même profondeur et les mêmes propriétaires.
- Le bloc « Pour avancer » et Jour J/Live ne sont plus des panneaux d'alerte orange par défaut ; les états réellement bloquants gardent leur sens.
- Le résultat d'une Journey terminale s'affiche depuis le statut Journey réel ; une Journey terminale ne présente pas d'action de préparation comme encore active.
- Les cartes « Contexte » évitent de répéter le titre du haut de page et distinguent Activity d'Occurrence.
- La continuité Conversations conserve son accès existant mais prend une place secondaire après le contenu utile de la démarche.
- Le Web reçoit un haut de page « Mon objectif » violet profond/corail de marque ; il conserve sa route et les sections propriétaires. Pas de progression synthétique ni de tableau de bord à trois colonnes.
- Les libellés ne mentionnent pas « BDD locale », « serveur » ou « mode hors ligne » ; les statuts des opérations continuent à dépendre des accusés réels.

## C10 — Couverture de non-régression

### Tests ajoutés / renforcés

- `mobile/test/journey_n3_lot_c_test.dart` : révocation contre projection conservée, panne de transport sans effacement, statut terminal sans action inventée, changement de Profil, présentation compacte et large, état Payment `pending` non écrasé par une tentative `succeeded`.
- `core/test_z5_detail_api.py` : présence du bloc objectif Web et absence de progression factice ; les anciens tests d'API de Forms, Payment, Readiness et Occurrence sont conservés.
- Tests préexistants des lots A/B : lecture locale `ProfileStore`, steps, exigences, ressources, liens propriétaires exacts, plusieurs obligations, date seule.
- Contrôle structurel des fichiers Dart modifiés : parenthèses, accolades et crochets vérifiés sur les fichiers concernés, sans garantir l'analyse Dart ou les tests d'exécution.

### Scénarios à exécuter avant intégration

1. **Visiteur/participant** : permissions, lien direct `/journeys/:id`, même Journey depuis En cours, Mes démarches, Notifications/Conversations sans refonte de ces surfaces.
2. **États** : action disponible, plusieurs actions, attente, blocage, aucune intervention, refus, Journey réalisée/annulée/expirée, étapes réelles et dépendances.
3. **Local-first** : démarrage à froid avec projections et documents acquis, écran et ressources ouverts sans réseau, retour du réseau, reprise des envois du formulaire et présentation correcte des confirmations.
4. **Sécurité** : 403/404, ancien flux local encore en mémoire, changement de Profil, de Journey et de Space, aucun affichage d'un droit perdu.
5. **Propriétaires** : brouillon/Submit, Requirement, ressource version 1 puis 2, paiement, commande, Access, Activity/Occurrence, Jour J et Makolo Live selon capacité.
6. **Présentation** : petit Android, texte agrandi/lecteur d'écran, grand Web/tablette, rotation et retour après profondeur ; absence d'overflow et de doublons.
7. **Web** : Template Journey, permissions authentification, formulations, absence de pourcentage imaginaire, liens directs.
8. **Migrations et données** : aucune migration ajoutée par le lot C ; vérifier que les anciennes projections et FileRecords version 1 restent utilisables.
9. **Suite** : tests ciblés Django, tests Flutter ciblés, suites pertinentes, `flutter analyze` / format, puis vérification CI avant éventuel merge.

### Limites de validation

Le container de travail ne dispose pas de Flutter/Dart ni d'une copie exécutable complète du dépôt, et ne peut pas accéder à GitHub par `git clone`. Les modifications ont été faites via le connecteur GitHub sur la branche de #522 ; **les tests sont écrits mais ne sont pas déclarés exécutés**. Les GitHub Actions automatiques observées étaient en attente/en cours/annulées sur certains commits intermédiaires, et ne prouvent pas une validation verte du HEAD.

## Aucun merge

La PR #522 reste la seule branche du chantier. Ne pas fusionner sans validation réelle des tests et sans CI verte, même si les changements de présentation ont été poussés.
