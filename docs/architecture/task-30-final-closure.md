# Tâche 30 — clôture finale T23–T29

## État du cycle

T30 conserve le principe **« Event est une verticale. Activity est le noyau. »** et clôt le cycle sans nouveau domaine parallèle.

Les invariants livrés par T23–T29 restent les contrats actifs : Journey/Access/Scanner canoniques, ownership Profile ou Space explicite, Commerce séparant buyer/payer/beneficiary/payee/operator, Discovery Activity-first, Group distinct de Team et Audience, Mandate comme autorité, et `/me/` comme projection personnelle sans modèle de timeline.

T30 rationalise uniquement les reliquats constatés sur `main` :

- `/me/history/` est la surface canonique du passé ; `Mes démarches` reste centrée sur les processus actifs et `Mes accès` sur les droits actifs / achats pour autrui ;
- Follow reste une relation privée orientée action ; aucun compteur public ni score de popularité n'est utilisé dans Discovery ;
- `OrganizationFollow` reste la relation explicite pour un Space et `ProfileFollow` couvre explicitement un organisateur personnel, sans `GenericForeignKey` ni `SocialActor` ;
- `ProfileFollow` n'accorde aucune Permission et ne crée pas automatiquement de Contact CRM, Audience ou consentement marketing.

## Capacités reportées

| Capacité | Disposition | Décision |
| --- | --- | --- |
| Changement de compte sans mot de passe | `FUTURE_PRODUCT_DECISION` | Le device cookie mémorise seulement un identifiant opaque et ne constitue aucun grant d'authentification. En l'absence de primitive serveur de délégation/réauthentification sûre, le changement de compte continue de demander une authentification. Aucun mot de passe, session key ou bearer token réutilisable n'est stocké côté client. |
| Paiement de production | `PRODUCTION_DEPENDENCY` | Le noyau possède `sandbox` et `manual`, mais aucun PSP réel n'est configuré. La production devra fournir un adaptateur conforme au contrat `payments` (création/confirmation, idempotence, signature de webhook, retry, remboursement et devises) sans fournisseur, compte ou secret inventé ici. |
| Split payouts / escrow / wallet / FX / taxes internationales / settlement complexe | `NOT_NEEDED` | Aucun contrat métier actuel ne justifie de transformer Makolo en infrastructure fintech anticipée. |
| Claim automatique d'un bénéficiaire externe par e-mail | `ACCEPTED_LIMITATION` | Un e-mail identique n'est pas une preuve d'identité. Aucun auto-claim n'est réalisé sans vérification forte. |
| Transfert complet d'Access vers une autre identité | `FUTURE_PRODUCT_DECISION` | Le bridge actuel peut synchroniser certains transferts historiques et réémettre un credential pour un Access actif ; il ne définit pas encore un workflow complet de cession d'identité, consentement, audit et révocation concurrente. |
| Transport multi-voyageurs dans une seule réservation | `ACCEPTED_LIMITATION` | Une réservation Transport correspond à un voyageur/une place ; plusieurs billets restent plusieurs intentions explicites et idempotentes. |
| Promotions sur Activities personnelles | `FUTURE_PRODUCT_DECISION` | Commerce sait porter `payee_profile`, mais Promotions reste aujourd'hui Space/Event-scoped. Aucun faux Space n'est créé pour contourner cette limite ; un futur changement devra aligner ownership Promotion, Offers éligibles et payee personnel. |
| « Pour vous » universel | `ACCEPTED_LIMITATION` | La surface indique explicitement qu'elle reste une compatibilité Event. Discovery universelle demeure Activity/Occurrence-first ; T30 retire les signaux agrégés de followers des scores publics. |
| GroupEligibility au niveau Occurrence/Offer | `NOT_NEEDED` | Aucun scénario démontré ne justifie trois moteurs d'éligibilité. `ActivityGroupEligibility` reste le contrat unique. |
| Matérialisation massive Group → Journeys | `NOT_NEEDED` | L'éligibilité, l'invitation et la résolution au moment de l'action sont préférées ; cibler un Groupe ne crée pas des milliers de Journeys. |
| Scanner offline / PWA | `FUTURE_PRODUCT_DECISION` | Aucun protocole offline ne garantit encore correctement révocation, usage unique et concurrence. Le scanner online canonique reste la vérité. |

## Compatibilités legacy conservées

- `OrganizationMembership` reste une projection de compatibilité tant que des fixtures/API historiques écrivent encore ce modèle ; l'autorité runtime reste `Mandate` et la collaboration `TeamMembership`.
- `EventBookmark`/routes Event-shaped restent des façades de compatibilité autour de `ActivityBookmark` lorsque des clients historiques les consomment.
- Les anciennes Activities sans `owner_profile` ni `space` sont tolérées uniquement pour données pré-T24 non inférables ; toute nouvelle Activity exige exactement un owner logique.
- Les routes/modèles `Ticket` et certaines routes Event/Scanner restent des projections de la verticale Event tant que leurs consommateurs réels existent ; `Journey`, `CommerceOrder`, `Access`, `AccessCredential` et `AccessUse` restent canoniques.
- Les compatibilités historiques de Group découvrabilité restent conservées lorsqu'elles protègent des données anciennes ; elles ne créent aucune autorité parallèle.

Aucune suppression destructive de données ou de migration n'est réalisée par T30.

## Réseau d'action

Le contrat final est :

- Favorite = retrouver une Activity ;
- Follow = rester informé des actions utiles d'un organisateur, de manière privée ;
- Group = communauté / appartenance / éligibilité ;
- Team = collaboration opérationnelle ;
- Audience = ciblage CRM soumis à ses propres règles et consentements ;
- Journey = démarche concrète ;
- Access = droit acquis ;
- Mandate = autorité.

Follow ne constitue ni un like, ni une preuve de qualité, ni un classement, ni un compteur public, ni une valeur commerciale de l'organisateur. Un Follow n'est jamais un consentement marketing implicite et `ProfileFollow` n'alimente pas automatiquement le CRM.

## Dépendance de production explicite

PythonAnywhere reste un environnement temporaire de test. T30 ne choisit ni n'invente l'hébergement final ni un fournisseur de paiement de production.

## Après T30

T30 ne crée pas automatiquement de T31. Un nouveau chantier devra provenir d'un retour bêta reproduit, d'une décision produit explicite, d'une préparation réelle de production ou d'un besoin métier démontré.
