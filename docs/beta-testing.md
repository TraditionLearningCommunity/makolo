# Guide de test bêta Makolo

Ce guide décrit uniquement les parcours alimentés par le profil `beta`. Le mot de passe temporaire commun aux comptes est transmis séparément et ne doit pas être ajouté dans Git, une issue ou un rapport.

## Participant — `beta.participant@makolo.test`

1. Se connecter et ouvrir **Découvrir**.
2. Ouvrir un **Événement** puis un **Trajet**.
3. Tester les filtres temporels/localité/gratuit-payant disponibles.
4. Ouvrir `/me/`, **Mes démarches**, **À venir**, **Mes accès** et **Notifications**.
5. Vérifier qu'une inscription Event et une réservation Transport apparaissent avec le vocabulaire produit approprié.
6. Vérifier un billet valide et l'historique déjà utilisé.

## Space admin — `beta.spaceadmin@makolo.test`

1. Choisir **Agir au nom de** l'Espace bêta.
2. Ouvrir la Vue d'ensemble.
3. Parcourir Activités, Équipe, Groupes et Lieux selon les surfaces affichées.
4. Vérifier que l'autorité vient du Mandat actif et non d'un statut superuser.

## Event manager — `beta.eventmanager@makolo.test`

1. Agir au nom de l'Espace Event bêta.
2. Ouvrir **Activités** puis un Événement.
3. Examiner ses Occurrences présentées comme dates/horaires, ses Tarifs et sa disponibilité.
4. Consulter les Demandes, Commandes et Accès autorisés.
5. Vérifier qu'une Activity hors de son scope n'est pas administrable.

## Transport operator — `beta.transport@makolo.test`

1. Ouvrir l'Espace Transport bêta.
2. Consulter les trajets Lubumbashi ↔ Kolwezi et leurs départs.
3. Vérifier origine, destination, heure, tarif et capacité.
4. Examiner un départ disponible, un départ complet et un scénario à payer sur place.
5. Vérifier que la surface Transport ne dépend pas d'un Event artificiel.

## Finance — `beta.finance@makolo.test`

1. Ouvrir Commandes et Paiements dans le contexte autorisé.
2. Vérifier les montants, devise et statuts.
3. Comparer valeur commerciale et paiement réellement encaissé.
4. Vérifier que le scénario `on_site` apparaît comme à payer sur place et non comme paiement encaissé.
5. Vérifier que ce persona n'obtient pas automatiquement CRM, Scanner ou gestion Activity.

## Scanner — `beta.scanner@makolo.test`

Le seed fournit un credential de smoke Event et un credential de smoke Transport. Le token brut ne doit jamais être copié dans un rapport ou une issue.

1. Ouvrir le contexte de contrôle autorisé.
2. Scanner le credential Event dédié : résultat attendu accepté selon le contrat courant.
3. Rejouer le même scan : résultat attendu duplicate/déjà utilisé selon le contrat courant.
4. Utiliser le credential Transport dédié pour vérifier le vocabulaire d'embarquement.
5. Vérifier que le compte Scanner ne peut pas administrer l'Espace ou consulter Finance hors mandat.

Un scan consomme un état de démo. Pour une répétition propre du scénario, reseeder la base candidate plutôt que créer manuellement un Access en live.

## Marketing — `beta.marketing@makolo.test`

1. Ouvrir Contacts, Audiences et Promotions si ces surfaces sont exposées dans le contexte.
2. Vérifier l'audience seedée et les promotions actives/expirées.
3. Ne pas interpréter l'appartenance à une Audience comme consentement marketing.
4. Vérifier que Finance n'est pas accordé automatiquement.

## Makolo staff/admin — `beta.admin@makolo.test`

Ce compte sert aux vérifications plateforme/opérations nécessitant réellement le staff. Il ne doit pas être utilisé pour valider les frontières des personas professionnels : ces contrôles doivent être faits avec leurs comptes dédiés.

## Discovery et carte — public

Sans session puis avec un Participant :

- vérifier Event + Transport dans les résultats publics ;
- vérifier Aujourd'hui/Demain/ce week-end/cette semaine ou les équivalents réellement affichés ;
- vérifier gratuit, payant, disponible et complet ;
- vérifier recherche/locality ;
- vérifier carte MapLibre, tuiles, attribution, pins et sélection ;
- vérifier que la liste reste exploitable si la carte est indisponible ;
- vérifier qu'un objet privé, non répertorié ou annulé ne pollue pas Discovery public.

## À signaler pendant la bêta

Pour chaque retour, noter le persona, l'écran et le scénario. Distinguer bug, UX, fonctionnalité manquante, performance, contenu ou environnement. Ne jamais inclure mot de passe, cookie/session, Authorization, token QR, reset token ou secret webhook.
