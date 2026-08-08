# Partners / Ambassadeurs / Affiliation

## Responsabilité

`partners` gère l'acquisition attribuable à des partenaires d'une organisation sans transformer les partenaires en administrateurs Makolo et sans exposer les données personnelles des participants.

Le domaine couvre : profils partenaires, campagnes par événement, codes/liens de recommandation, visites anonymisées, attribution d'une commande, commissions, soldes, paiements de commissions, portail ambassadeur et intégration Event Intelligence.

## Modèles

### Partner

Profil organisationnel d'un ambassadeur, influenceur, agence, média, communauté ou partenaire commercial. Il peut être lié à un compte Makolo afin d'offrir un portail partenaire sur ses propres performances et règlements.

### AffiliateCampaign

Campagne rattachée à exactement une organisation et un événement. Elle définit le statut, la fenêtre d'attribution (1 à 90 jours) et la règle de commission par défaut : pourcentage ou montant fixe.

### ReferralCode

Code unique par couple campagne/partenaire. Un override de commission est possible pour négocier un taux spécifique. Le lien public est `/partners/r/<code>/`. Un code peut être désactivé/réactivé sans supprimer son historique.

### ReferralVisit

Journal minimal d'une visite : code, UUID visiteur opaque, chemin de destination, domaine référent et horodatage. Makolo ne persiste ni adresse IP ni URL référente complète dans ce domaine.

### ReferralAttribution

Relation OneToOne entre une commande et le code qui l'a apportée. Une commande ne peut donc produire qu'une attribution. États : `pending`, `confirmed`, `reversed`.

### PartnerCommission

Snapshot financier de la règle appliquée au moment de la conversion : type, valeur, montant, devise et état `earned`, `paid` ou `reversed`. Le snapshot empêche une modification future de campagne de réécrire l'histoire financière.

### PartnerPayout

Regroupe des commissions acquises d'un seul partenaire et d'une seule devise. Il sert d'audit de règlement hors Makolo jusqu'à l'introduction éventuelle d'un provider de payout réel.

## Attribution

Makolo utilise actuellement un modèle **last valid referral** : le dernier code valide visité remplace le précédent dans la session. Le code doit être actif, le partenaire actif, la campagne active dans sa fenêtre temporelle et la commande doit concerner l'événement de la campagne.

Le navigateur reçoit un UUID visiteur dans la session. La visite est dédupliquée par `(referral_code, visitor_id)`. L'API mobile peut fournir explicitement `referral_code` lors de `POST /api/v1/tickets/orders/`.

Une simple visite ou réservation ne génère aucune commission.

### Auto-attribution / self-referral

Si le compte Makolo lié au partenaire achète lui-même via son propre code, Makolo conserve une attribution `reversed` pour audit mais la rend immédiatement non commissionnable. Le checkout et le paiement client continuent normalement : la règle anti-abus ne doit jamais casser la vente.

Cette protection est volontairement basique. Un scoring anti-fraude avancé pourra plus tard analyser appareils, volumes, comportements et réseaux sans introduire aujourd'hui une collecte intrusive.

## Cycle financier

```text
Referral visit
    ↓
TicketOrder pending
    ↓
ReferralAttribution pending
    ↓
paiement réussi / commande confirmée
    ↓
ReferralAttribution confirmed
    ↓
PartnerCommission earned
    ↓
PartnerPayout draft
    ↓
PartnerCommission paid
```

Une annulation/remboursement inverse l'attribution et la commission tant que celle-ci n'a pas déjà été payée.

Une commission `paid` interdit une inversion silencieuse. Le remboursement est refusé par le service transactionnel tant qu'un ajustement comptable n'a pas été traité. Cette règle évite de créer automatiquement une dette négative invisible envers un partenaire.

Les commissions déjà affectées à un `PartnerPayout` brouillon ne restent pas dans le solde disponible et ne peuvent donc pas être incluses dans deux règlements simultanés. Annuler un payout brouillon libère ses commissions ; marquer le payout payé les rend `paid` de façon transactionnelle.

## Calcul des commissions

Pourcentage :

```text
commission = total commande × taux / 100
```

Le résultat est arrondi à deux décimales et utilise la devise de la commande.

Montant fixe : la devise de campagne doit correspondre à la devise de la commande. Aucune conversion FX implicite n'est réalisée par Makolo. Une conversion dans une autre devise reste attribuée mais ne crée pas de dette de commission ambiguë.

Les commandes gratuites et commissions calculées à zéro restent mesurables comme conversions, mais ne créent ni `PartnerCommission` à payer ni `PartnerPayout` nul.

Les paiements partenaires sont séparés par devise. Aucun total multi-devise n'est additionné.

## Permissions

- Owner / Admin : gestion partenaires + finance partenaire ;
- Marketing : création/modification partenaires, campagnes et codes, statistiques agrégées sans montants de commissions ;
- Finance : commissions, soldes et paiements, sans obtenir automatiquement le droit de créer/modifier une campagne ;
- partenaire lié à un compte : son propre profil, ses liens, conversions agrégées et montants de ses propres commissions ;
- autres participants : aucun accès ;
- staff Makolo : supervision plateforme.

Les sélecteurs appliquent ces frontières côté web et API. Les réponses partenaires ne contiennent jamais le nom, l'e-mail, le téléphone ou le QR d'un acheteur.

## Intégration Tickets / Payments

Le web attribue une commande à partir du referral conservé dans la session. L'API accepte `referral_code` en entrée.

Le domaine s'abonne au changement d'état de `TicketOrder`. Quand une commande devient `confirmed`, la commission est créée si une attribution commissionnable existe. Quand elle devient `cancelled` ou `expired`, l'attribution est inversée.

Cette synchronisation fonctionne donc aussi pour les paiements sandbox/manuels et futurs PSP, puisqu'elle dépend de la vérité métier `TicketOrder` plutôt que d'un provider de paiement précis.

## Notifications

Quand le partenaire est lié à un compte Makolo :

- création d'un code -> notification « lien ambassadeur prêt » ;
- commission acquise -> notification transactionnelle avec montant/devise ;
- payout marqué payé -> notification de règlement et référence.

Les notifications sont créées après commit et passent dans l'outbox Notifications existante pour l'e-mail, les retries et les préférences utilisateur.

## Event Intelligence

`analytics_app` enrichit le détail événement avec : visites partenaires, commandes attribuées, conversions confirmées, taux de conversion, leaderboard agrégé et insights de canal. Les coûts de commissions par devise ne sont présents que pour les rôles financiers.

Aucun acheteur individuel n'est exposé dans ce read-model.

## Interfaces

```text
/partners/
/partners/org/<organization-slug>/
/partners/org/<organization-slug>/partners/new/
/partners/org/<organization-slug>/campaigns/new/
/partners/campaigns/<uuid>/
/partners/campaigns/<uuid>/edit/
/partners/partners/<uuid>/
/partners/partners/<uuid>/edit/
/partners/r/<code>/
```

API :

```text
GET/POST /api/v1/partners/partners/
GET/POST /api/v1/partners/campaigns/
GET/POST /api/v1/partners/codes/
GET      /api/v1/partners/commissions/
GET/POST /api/v1/partners/payouts/
POST     /api/v1/partners/payouts/<uuid>/paid/
POST     /api/v1/partners/payouts/<uuid>/cancel/
GET      /api/v1/partners/partners/<uuid>/metrics/
```

## Évolutions prévues

- scoring anti-fraude avancé au-delà du blocage de self-referral ;
- coupons/promo combinés avec affiliation ;
- attribution multi-touch ;
- payouts automatisés lorsque des fournisseurs fiables sont choisis ;
- commissions par produit/type de billet ;
- objectifs et bonus par palier ;
- campagnes multi-événements ;
- intégration Event CRM et audiences d'ambassadeurs.
