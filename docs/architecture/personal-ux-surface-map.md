# Makolo Personnel — cartographie finale des surfaces UX

## Statut

Cette cartographie décrit le mode **Profil / Me**, c’est-à-dire une personne qui agit en son nom propre.

Elle ne définit ni la console **Space** ni l’autorité **Platform**.

La règle de fermeture est :

> Les cinq repères sont le système de navigation. Les autres surfaces sont des profondeurs explicites de ce système, pas un second produit caché.

La source exécutable de propriété UX est `core/personal_navigation.py`.

## Niveaux

### N1 — cinq repères principaux

Il existe exactement **5** surfaces N1 :

1. **Maintenant** — ce qui demande de faire, décider, s’adapter ou débloquer maintenant.
2. **Découvrir** — explorer des possibilités non encore engagées.
3. **Makolo** — donner une intention, une information ou un objet à Makolo ; le Mark route ensuite vers le domaine propriétaire.
4. **En cours** — retrouver ce qui est engagé et continue.
5. **Moi** — capital durable personnel.

Le **Header / Avatar** est transverse. Il n’est pas un sixième repère.

## Comptage exécutable

Au 26 septembre 2026, la fermeture explicite couvre :

| Niveau | Nombre de destinations routées | Sens |
| --- | ---: | --- |
| N1 | **5** | repères principaux |
| N2 | **30** | familles/destinations personnelles directement retrouvables |
| N3 | **33** | détails et profondeurs contextuelles |
| N4 | **61** | opérations ponctuelles dans une réalité existante |
| Legacy | **1** | `PersonalGoal`, conservé pour compatibilité mais non promu |

Ces nombres comptent des **destinations UX routées**, pas des concepts que l’utilisateur doit mémoriser.

## N2 — destinations secondaires

### Propriétaire Maintenant

- Ce qui attend ma réponse / sollicitations.
- Mes besoins / réseau d’action orienté action.

Le vieux flux générique `social:network` est retiré de l’expérience personnelle et redirige vers **Maintenant**. Makolo ne maintient pas un feed d’engagement comme destination parallèle.

### Propriétaire Découvrir

- Pour vous.
- Découvrir des collectifs.
- Opportunités.
- Services.
- Transport.
- Événements.

Les détails de possibilité restent N3. Les actions de démarrage/réservation/contribution sont N4.

### Propriétaire En cours

- Démarches.
- Accès.
- Dossiers personnels.
- Projets personnels.
- Billets.
- Liste d’attente.
- Transferts.

Les paiements ne deviennent pas un repère autonome. Ils restent une profondeur de la réalité engagée.

### Propriétaire Moi

- Historique.
- Éléments gardés.
- Veilles.
- Mes collectifs.
- Mes ressources.
- Passeport Makolo.
- Recognition.
- Loyalty.
- Relation Partner personnelle.

**Éléments gardés** et **Veilles** sont du capital personnel récupérable depuis Moi. Leur domaine backend reste Discovery, mais leur propriétaire de navigation personnelle est Moi.

### Propriétaire Header

- Conversations.
- Notifications.
- Compte et paramètres.
- Changer de compte.
- Abonnement personnel.
- Agir comme.

`Agir comme` change le contexte d’acteur. Une Membership ou l’apparition d’un Space dans ce sélecteur ne crée aucune Permission ni Mandate.

## N3 — profondeurs contextuelles

Le N3 contient notamment :

- détail d’une Démarche ;
- Jour J / Occurrence Live ;
- détail d’un Access ;
- détail d’un Dossier ;
- détail d’un Projet ;
- détail billet/commande ;
- paiement ;
- workspace participant d’une démarche Service ;
- réutilisation de ressource dans une Requirement ;
- détail d’une Veille ;
- détail/vie d’un Groupe ;
- détail d’une ressource ;
- import/partage reçu ;
- relation Loyalty avec une organisation ;
- preuves personnelles ;
- conversation ;
- préférences de notification ;
- Interests / Open to.

Une surface N3 conserve le repère N1 de son propriétaire actif et possède un retour cohérent vers lui.

## N4 — opérations

Le N4 regroupe les opérations qui ne doivent jamais devenir de la navigation :

- accepter/refuser ;
- rejoindre/quitter ;
- créer/modifier une Veille ;
- payer/annuler/compléter ;
- présenter/télécharger ;
- ajouter ou versionner un document ;
- relier/délier une Démarche ;
- gérer une dépendance ;
- accepter/refuser un transfert ;
- répondre/accuser réception dans une conversation ;
- gérer ponctuellement un Groupe ;
- changer un abonnement ;
- répondre à une invitation.

Le nombre de N4 peut augmenter avec les capacités métier sans faire croître N1.

## Frontières d’acteur

### Personnel

Les listes `Dossier` / `Project` ouvertes depuis **En cours** ne projettent que les réalités personnelles :

- `owner_profile = request.user`
- `owning_space = null`

Le formulaire historique de création conserve toutefois son contrat brownfield : un Profile disposant de l’autorité requise peut choisir explicitement un `Espace porteur`. Cette capacité ne transforme pas pour autant la liste **En cours** en projection Space.

### Space

Les capacités Space restent dans leur console/contextes dédiés. La création explicite d’un Dossier/Projet avec `Espace porteur` respecte les permissions existantes, mais cette réalité n’est pas absorbée dans les listes personnelles. Une route opérateur ou staff partageant un namespace Django avec une capacité personnelle n’est **pas** automatiquement absorbée par le shell personnel.

### Platform

Platform est hors périmètre de cette fermeture.

## Routes volontairement non possédées par le shell personnel

Le résolveur ne classe plus des namespaces entiers. Une route staff, opérateur, console Space, publique ou technique reste sans propriétaire personnel tant qu’un contrat explicite ne la rattache pas.

Exemples :

- `services:operator-dashboard`
- `opportunities:staff-dashboard`
- `funding:manage`

Cela évite qu’une page d’autorité soit affichée avec **Découvrir**, **Moi** ou **En cours** actif simplement parce qu’elle vit dans le même module Django.

## Legacy

`PersonalGoal` reste conservé pour compatibilité historique, mais n’est pas une destination Mature active.

Il ne doit pas redevenir une métrique centrale ni une entrée privilégiée dans Moi ou Historique.

## Invariant final

Pour le Profile agissant en son nom propre :

> une capacité utile doit être retrouvable depuis Maintenant, Découvrir, Makolo, En cours, Moi ou le Header ; une capacité d’autorité Space/Platform ne doit jamais être absorbée par ce shell par simple proximité technique.
