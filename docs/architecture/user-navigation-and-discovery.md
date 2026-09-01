# Navigation utilisateur et découverte

Makolo conserve un backend organisé par domaines canoniques, tandis que l’interface utilisateur est organisée par intentions. Une simplification de navigation ne fusionne donc pas les responsabilités métier.

## Navigation personnelle

La sidebar personnelle expose uniquement :

- **Accueil** : synthèse personnelle ;
- **Mes démarches** : Journey actives ou en attente d’action, toutes verticales confondues ;
- **Mes accès** : droits et credentials obtenus et utilisables ;
- **Historique** : éléments terminés, utilisés, expirés, annulés ou clôturés selon leur contrat ;
- **Découvrir** : porte d’entrée pour ce que la personne peut encore faire.

`Services`, `Opportunités` et l’abonnement personnel ne sont pas des destinations principales de cette sidebar.

## Découvrir

Discover est une projection de lecture orientée utilisateur. Elle agrège les contenus publics utiles sans créer de super-modèle métier. Les catégories visibles reflètent des intentions : **Tout**, **Événements**, **Voyager**, **Être accompagné** et **Autres**.

Les Events et le Transport restent des verticales Activity. Les Services restent des Activity d’accompagnement/processus. Un Service public peut être projeté dans Discover même s’il n’a pas d’Occurrence planifiée.

`Opportunity` reste une possibilité ou un contexte externe, pas un produit autonome de navigation. Lorsqu’une recherche correspond à une Opportunity publiée, Discover peut l’utiliser pour contextualiser un accompagnement compatible et transmettre cette Opportunity au flux Service existant.

## Abonnements et autorité active

En contexte personnel, l’abonnement est accessible dans le menu compte sous **Mon abonnement et facturation**.

En contexte Space, la navigation administrative utilise **Abonnement de l’espace** et **Paramètres de l’espace**. Les liens restent conditionnés par les permissions serveur existantes.

L’autorité active est toujours explicite : une personne agit soit en son nom, soit au nom d’un Space. Les changements de navigation ne modifient ni les permissions, ni les règles anti-IDOR, ni les modèles de Subscription.
