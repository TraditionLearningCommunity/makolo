# Subscription — Lot 4 : comprendre le blocage, puis reprendre l'action

**Périmètre :** Web et Flutter sur la PR #522, sans nouveau modèle, Feature, entitlement, prix, Mandate ni migration. La Subscription reste une vérité serveur et non une mécanique de rétention.

## Problème utilisateur

Une action réelle peut être refusée par `activities.create` ou par un quota `team.members`. Montrer seulement une erreur laisse le Profil sans chemin de continuation. Le besoin n'est pas de multiplier les pages Subscription, mais de relier l'action au bon propriétaire métier :

1. Refus métier effectif par le service owner.
2. Explication de la condition Subscription, distincte de Permission/Mandate et du réseau.
3. Navigation vers la Subscription du propriétaire logique (Profil ou Espace), uniquement si le lecteur y est autorisé.
4. Consultation de l'état, des capacités, des limites et des conditions réellement exposées par le serveur ; option de transition uniquement si `can_manage`.
5. Retour volontaire à l'action initiale pour une **nouvelle tentative** ; jamais de replay implicite, de réussite supposée ou de transfert d'autorité.

## Web

- `subscriptions/ux_continuation.py` : le handoff n'est produit que pour `ValidationError` structurée par `subscription`. Pour un Espace, la présence d'une Subscription visible à l'acteur est vérifiée par `subscriptions_visible_to_actor`. Sans droit de lecture, le formulaire conseille de consulter la personne autorisée mais n'affiche aucun lien privé.
- Création d'Activity (personnelle ou Espace), d'Event et ajout de collaborateur Espace : erreurs conservées dans le formulaire de l'action, avec une carte `Comprendre dans l'abonnement` uniquement en cas de refus d'Entitlement. Les erreurs de permission, de formulaire et les autres échecs ne génèrent pas de handoff.
- Les pages personnelles `/subscription/` et Space `/spaces/<slug>/subscription/` affichent un lien `Revenir à l'action` après validation serveur d'un chemin local autorisé.
- Le paramètre éphémère `next` circule dans les liens de preview, les formulaires POST de transition/cancel/complete et le retour à la page Subscription. L'allowlist côté serveur rejette les URL externes, les chemins non-action, les autres Espaces, les chemins malformés et les profondeurs privilégiées.
- Reprendre rouvre la destination ; le brouillon Web ou les pièces jointes ne sont pas réputés sauvegardés ni automatiquement réémis. Les droits et Entitlements sont revérifiés à la nouvelle mutation.

## Flutter

- Le chemin natif concret actuellement présent est `Nous > Équipe > Ajouter un collaborateur`, via `SpaceNousDepthScreen`.
- L'API Organizations possède déjà des erreurs Django `{"subscription": [...]}` sérialisées comme 400 DRF. Le composant ne crée un CTA **Comprendre** que pour ce champ précis, un handoff `subscription` déjà exposé par le serveur dans la projection `Nous`, et l'acteur Space exact encore actif.
- Aucun CTA pour les 401/403/404 de mandat, les erreurs réseau, les champs de formulaire ou les Espaces différents. Le GET Subscription revalide la lecture serveur même si une projection périmée conservait le handoff.
- `/space/:slug/subscription?from=team` utilise `BillingScreen` réutilisé pour le lot 2. Un panneau contextuel explique qu'aucune admission n'est automatique et propose `Revenir à l'équipe`. Le retour est indisponible si l'acteur actif ne correspond plus à l'Espace attendu.
- Les clients n'inventent ni quota, ni paiement, ni achat immédiat, ni permission, ni état Subscription.
- `custom_roles` n'a pas de CRUD public ; aucun parcours artificiel de rôle/abonnement n'a été créé.

## Tests ajoutés et renforcés

- `subscriptions/test_lot4_continuation.py` : blocage Activity personnel ; quota d'équipe et reprise dans le bon Space ; Mandate de gestion d'équipe sans droit de consulter Subscription ; refus de `next` externe ou cross-Space ; continuité preview/POST ; erreur non Subscription sans lien.
- `mobile/test/space_subscription_screen_test.dart` : distinction d'une erreur structurée `subscription` et d'un refus de permission/champ ; affichage puis révocation du retour à l'équipe lorsque le contexte acteur change.

## Critères de sortie et vérifications

**Faits attestés :** changements et fichiers de tests poussés dans la PR #522, sources propriétaires et frontaux raccordés. Aucun modèle ni migration ajouté.

**Non attestés ici :** exécution Python/Django/Flutter, test Web réel navigateur, test cold-start mobile, et CI. L'environnement de cette session n'a pas de checkout Django/Flutter ni de binaire Flutter. Les tests ciblés doivent être exécutés sur le dépôt courant avant merge ; la PR demeure ouverte.

La fermeture du lot 4 ne signifie pas que toutes les transactions sont instantanées : Payment, Requirements et transitions restent owner-backed, et leur achèvement détermine l'Entitlement effectif.
