# Recette Mes Démarches — Liste navigable, sans explications techniques

**Cible :** PR #522, branche existante. **Portée :** présentation Flutter de l'organisateur Objectives et de ses collections, sans modifier ses propriétaires métier.

## Correction

- Le bandeau sur les données locales ou les nouveautés à la reconnexion est retiré de l'organisateur quand la liste est déjà visible. Le mécanisme de cache, la synchronisation, les états d'erreur et le geste pour rafraîchir restent inchangés.
- Le compteur de la collection garde le nombre d'éléments effectivement acquis, sans suffixe technique « chargé(s) ». Il ne prétend pas donner le total lorsque des pages supplémentaires restent inconnues.
- En mode Liste, chaque Projet, Dossier ou Démarche est une carte individuelle ouvrable avec titre, type, état, contexte pertinent et chevron.
- En mode Cartes, les enfants ne sont plus de simples lignes de texte : chacun devient un élément ouvrable, avec le même appel `onOpenItem(kind,id)` que dans les autres modes.
- Le mode Explorateur garde sa structure hiérarchique et sa possibilité de déplier/replier ; les titres sont plus lisibles et le chevron distingue l'action d'ouverture.
- Les collections Mes projets et Mes dossiers réutilisent une présentation de carte explicitement cliquable. Les mentions techniques de reconnexion et les messages de fin superflus sont écartés.
- Aucun changement de modèle, migration, API, permission, identité ni routage. Les projets, dossiers et démarches restent la responsabilité de leurs domaines canoniques.

## Validation ciblée

- Tester trois modes de l'organisateur avec une collection de plusieurs items.
- Toucher une sous-entrée de carte et vérifier que **son** identifiant est ouvert, sans ouvrir le parent.
- Vérifier les vues à 320 px et l'absence d'overflow.
- Vérifier que le changement de contexte Moi/Nous n'ouvre pas des items d'un autre Space.
- Vérifier avec cache seulement : aucun bandeau explicatif n'interrompt la liste, mais les contrôles d'erreur et de rafraîchissement restent disponibles.
- Les tests Flutter ne peuvent pas être exécutés localement sans le SDK ; ne pas présumer de CI verte.
