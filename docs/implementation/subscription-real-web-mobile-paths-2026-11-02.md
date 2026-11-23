# Subscription — Validation des parcours réels Web/mobile (2 novembre 2026)

Périmètre volontaire : **parcours utilisateur**, sans modification de workflow CI, sans fusion et sans prétention de validation sur appareil.

## Parcours vérifiés et renforcés dans le code

| Départ | Action serveur | Refus attendu | Continuité |
| --- | --- | --- | --- |
| Moi → Créer Activity | `create_activity(owner_profile=actor)` | `ValidationError(subscription)` si `activities.create` indisponible | Subscription personnelle → retour au formulaire → nouvelle tentative |
| Space A → Créer Activity | `create_activity(space=A)` sous `SPACE_ACTIVITIES_MANAGE` | Entitlement de A, jamais du Profil opérateur | Subscription A (si visible au Mandate) → `/activities/create/?space=A` |
| Profil/Space → Event | `create_event` puis Activity owner | Même gate que l'Activity propriétaire | Subscription du sujet → formulaire Event pré-sélectionnant le Space autorisé |
| Space A → Nous → Équipe → Ajouter | `add_or_update_member` | `team.members` sur profils actifs distincts ; permission équipe séparée | Subscription A (si visible) → retour équipe, sans mutation automatique |
| Space B et Profil | Services propriétaires distincts | Blocage A sans contagion vers B | Pas de fuite inter-sujet |
| Acteur sans droit Subscription | Refus uniquement de capacité | Ne pas afficher des données de gestion ou billing | Indication de contacter la personne autorisée, aucun lien de lecture privé |

## Corrections du passage final

- `mobile/lib/features/space/space_shell_routes.dart` : les réponses d'erreur d'une mutation équipe arrivant après un changement d'acteur ne produisent plus de Snackbar périmée. Les réponses 401/403/404 et les refus Subscription restent distincts ; seul un handoff effectivement exposé par Nous autorise « Comprendre ».
- `subscriptions/test_lot4_continuation.py` : scénarios de reprise **réelle** : refus de capacité, consultation de Subscription, ajout d'une capacité réelle par le service de grants, retour à l'équipe, admission d'un nouveau Profil, répétition idempotente du Profil déjà compté ; blocage d'A sans empêcher l'ajout dans B.
- Les tests précédents couvrent URL externes, slug inconnu, retour Event lié au propriétaire, acteur équipe sans Mandate Subscription et validation du POST après changement d'acteur Flutter.

## Exclusions et état de preuve

Ce chantier ne change pas de modèles, migrations, plan, prix, workflow CI, secrets, ni permissions. Il ne fusionne pas #522. Les changements sont poussés sur sa branche.

Le code a été inspecté à partir du HEAD réel de la branche et des tests ciblés ont été ajoutés. **Un passage réel navigateur et Android, et l'exécution locale des tests Django/Flutter, ne sont pas attestés** dans cette session faute de checkout Flutter/Django exécutable. Les tests sont donc des preuves écrites de contrat, pas une attestation de validation E2E sur appareil.

Les opérations de paiement, d'éligibilité, de Mandate et de confirmation restent arbitres sur leurs services propriétaires. Le retour depuis Subscription n'exécute jamais le geste initial à la place de l'utilisateur.


## Complément de fermeture UX — 3 novembre 2026, branche de #522

**Problème utilisateur observé :** les quatre surfaces Flutter (abonnement, formules, options, facturation) montrent une accumulation de grandes cartes, une faible distinction des niveaux N1/N2/N3, des libellés techniques et un écran financier vide disproportionné. La même grammaire est désormais reprise pour Web et Space.

**Implémentation :**
- N1 Flutter : formule actuelle et statut dans une unité de reconnaissance ; options actives en lignes ; capacités et conditions en profondeur ; navigation condensée, sans icône décorative sur chaque ligne.
- N1 Web : formule et statut groupés, listes d'offres compactes, historique et facturation bornés à deux entrées sur l'accueil de l'abonnement ; les pages dédiées conservent pagination et détails.
- N2 : consultation explicite d'une formule ou d'une option avant mutation ; fonctionnalités conservées sans répéter toutes les métadonnées dans chaque résultat.
- N3 Flutter : confirmation explicite avant le POST idempotent ; montant issu de Billing Terms et paiement exact dirigé vers Payments lorsqu'il existe.
- Facturation : états financiers présentés en langage humain, distinctions entre demande, obligation et règlement conservées ; pas d'invention de facture ni d'échéance.
- Profil/Space : acteurs et permissions conservés, lecture des paiements autorisée séparément, annulation bloquée sur obligation financière non régularisée.
- Catalogue de démonstration opt-in : bénéfices différenciés par scénario sans inventer de nouvelles capacités Profil ; les offres déjà publiées restent immuables.

**Contrat de sortie à vérifier sur la branche courante :** tests ciblés Django (Subscriptions, paiement, permissions, continuation), migrations et API ; formatter Dart canonique, analyse Flutter, tests ciblés des écrans Profil et Space ; contrôle visuel Android 360/430 dp avec textScale 1,0/1,3/1,6 et Web compact/large ; passages BASE, ADDON, paiement en attente, refus, règlement et historiques. Ne jamais confondre code poussé et expérience validée sur appareil.

**Dépendances CI détectées pendant cette fermeture :** le modèle Accounts de visibilité nécessitait une migration additive d'alignement de sa contrainte ; le générateur Dart échouait sur une expression du détail des Connexions. Ces corrections transversales ne modifient ni les domaines Subscription/Payment ni les permissions.

**Invariants :** aucune nouvelle table Subscription ou Payment, aucun changement de prix commercial officiel, aucun contournement de test, aucune confirmation financière hors ligne, aucune fusion avant CI verte. Les données de démonstration déjà présentes en SQLite ne sont pas réécrites automatiquement par l'évolution du générateur.
