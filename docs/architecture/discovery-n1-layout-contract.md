# Découvrir N1 — composition de la possibilité

Statut : contrat d’assemblage Web / Flutter, implémenté sur la branche de PR #522.
Sources propriétaires : le backend et les domaines canoniques. Ce document décrit un **rendu** et n’introduit aucune vérité persistante.

## Ordre des zones, sans emplacement vide

1. **Porteur + ajout** : avatar et nom du Profil/Espace navigables selon les droits, date **d’ajout** à droite et distincte de toute date d’Occurrence.
2. **Titre** : désigne la possibilité.
3. **Verticale / type** : libellé métier principal et sous-type pertinent, dédupliqués. L’état de participation personnel n’est pas un type.
4. **Description** : aperçu court à N1 ; toucher le texte ou « Voir plus » développe, un second toucher ou « Voir moins » replie. Seul le texte est affecté.
5. **Informations pratiques** : prix canonique, lieu, quand, disponibilité, dates/repères particuliers, variantes et contexte autorisé. Les libellés et valeurs restent visibles et stables pendant le dépliage du texte ; aucune extraction de prix depuis une description libre.
6. **Média principal / galerie** : uniquement les usages de présentation publics, disponibles et autorisés. Aucun visuel artificiel lorsque les médias n’existent pas ; l’image et les ressources documentaires restent distinctes.
7. **Documents et ressources** : les deux premières ressources publiques dans l’ordre canonique. Pour plus de deux, un contrôle distinct révèle la collection entière, puis permet le repli. PDF, liens, textes et fichiers sont consultables conformément à leurs capacités.
8. **Interactions** : trois colonnes égales sur mobile, Enregistrer / Action métier autorisée ou consultation / Partager, sans changement implicite des capacités.

## Invariants de la projection

- Aucune limite arbitraire de six ressources annexes : `discovery/api/composition.py` transmet toutes les ressources **publiées et publiques**, sans transférer les ressources privées.
- Les deux premiers éléments sont une **limite d'affichage replié**, et non une limitation du nombre de ressources serveur.
- Un état de disponibilité inconnu ne justifie pas un calcul client ; un prix mentionné seulement dans le texte reste éditorial.
- Les faits temporels et spatiaux conservent leur sens métier (départ, arrivée, échéance, etc.).
- Les zones conditionnelles sont omises en leur absence, sans placeholder ni hauteur réservée.
- Web et Flutter consomment la même identité et les mêmes faits, avec présentation adaptative.
- Aucun nouveau modèle `Possibility`, `Media` ou `Resource` n'est introduit pour cette composition.

## Régressions à protéger

- Seven-or-more resource presentation, with only two initially visible.
- Ressource privée jamais exposée par Discovery.
- Classification sans duplication de « Type ».
- Les faits restent visibles lors de « Voir plus / Voir moins ».
- Ordre des zones, navigation du porteur, actions et contraste clair/sombre.
- Galerie, ressources et lecteurs propriétaires non perturbés par le changement de composition.

Ce contrat complète, sans remplacer, `docs/architecture/makolo-domain-blueprint.md` et les contrats UX Découvrir. Les domaines propriétaires et leurs permissions restent prioritaires.
