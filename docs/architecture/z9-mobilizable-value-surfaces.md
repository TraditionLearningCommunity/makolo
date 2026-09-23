# Z9 — Recognition, Loyalty et Partner : valeur mobilisable personnelle

## Objet

Z9 ferme les profondeurs personnelles secondaires de trois domaines qui peuvent produire une conséquence utile sans les fusionner :

```text
Recognition = valeur reconnue par le réseau Makolo
Loyalty     = relation d'avantages avec une organisation/programme
Partner     = relation économique ou d'affiliation avec une organisation
```

La proximité UX n'introduit aucune vérité métier commune. Z9 n'ajoute aucun modèle, aucune migration, aucun wallet, aucun total transversal et aucun score humain.

## Frontières

```text
Recognition != Loyalty != Partner
Recognition credit != monnaie
Loyalty points != Recognition credits
Loyalty membership != TeamMembership
Loyalty membership != Space authority
Partner relationship != Space authority
Partner != CRM contact
Reward/Achievement != Credential Trust
Partner economic right != Payment movement
pending != earned != paid
```

Les projections personnelles utilisent toujours `request.user`. Aucun `profile_id` ne permet de changer de sujet.

## Recognition

La profondeur canonique reste l'API owner-domain existante :

```text
GET  /api/v1/recognition/me/
POST /api/v1/recognition/rewards/<reward-id>/redeem/
POST /api/v1/recognition/redemptions/<redemption-id>/<accept|decline>/
```

Z9 conserve les contrats Z4 et ajoute un résumé explicitement non monétaire, un historique récent humain et borné, ainsi que les links/capabilities utiles. Le ledger brut n'est pas exposé : pas d'idempotency key, metadata technique, source interne ou fulfillment snapshot.

La lecture ne crée aucun compte Recognition. Les redemptions continuent de passer par `recognition.economy`; l'idempotence et les décisions bénéficiaire restent propriétaires du domaine.

## Loyalty

La profondeur canonique reste :

```text
GET /api/v1/loyalty/me/
```

Les comptes restent séparés par programme et organisation. Z9 ne calcule jamais une somme de points entre programmes. Chaque compte expose son unité locale `points_name`, son tier local lorsqu'il existe et un historique récent borné sans metadata technique.

Les rewards exposées comme mobilisables proviennent d'un selector qui reproduit seulement les préconditions non mutantes du service propriétaire : programme/reward actifs, fenêtre de validité, compte personnel, plafond d'usage et solde suffisant. Le service `loyalty.services.redeem_reward()` revalide transactionnellement au moment de la mutation.

Z11 durcit la profondeur de mutation `POST /api/v1/loyalty/rewards/<reward-id>/redeem/` : le reward doit appartenir à un programme pour lequel le Profile possède déjà un compte, une `idempotency_key` est obligatoire, et un replay de la même requête restitue la même redemption sans second débit. Aucun modèle ni champ d'idempotence supplémentaire n'est créé : l'unicité existante du `LoyaltyLedgerEntry.idempotency_key` reste le verrou canonique.

Les réponses personnelles Loyalty sont `private, no-store`. Aucun GET ne crée compte ou membership.

## Partner

`GET /api/v1/me/partners/` reste l'index compact Z4. Z9 ajoute :

```text
GET /api/v1/me/partners/<partner-id>/
```

Le détail est strictement `Partner.user == request.user`. Il expose relation, organisation, codes personnels, métriques agrégées autorisées, commissions et payouts bornés, sans buyer PII, CRM notes, coordonnées Partner internes ni données bancaires.

Les montants restent `Decimal + currency`. Les devises ne sont jamais additionnées. `unallocated_earned` conserve une ligne par devise et `aggregate_across_currencies` reste explicitement nul.

Z9 n'expose aucune capability de payout self-service : le runtime actuel réserve la création/confirmation de payout au service Finance propriétaire. Une relation Partner ne produit jamais Permission ou Mandate d'Espace.

## Anti-features

Z9 interdit explicitement :

```text
wallet universel
Makolo Points
total de valeur Recognition + Loyalty + Partner
score social / réputation globale
ranking humain
gamification générique
conversion automatique entre credits, points et monnaies
Space authority implicite
dashboard Analytics complet dans Partner
```

## Performance et confidentialité

- Recognition : ledger récent borné à 20 entrées humaines.
- Loyalty : comptes personnels seulement, historique récent borné à 20 entrées par compte, rewards calculées en lecture sans mutation.
- Partner : codes/commissions/payouts bornés à 50, métriques agrégées sans buyer PII.
- Aucune projection Z9 ne sérialise les metadata de ledger, notes CRM/Partner, e-mails/téléphones tiers, références de commande acheteur ou détails bancaires.
- Aucun cache persistant ni snapshot API n'est créé.

## Continuité Z4 / Z7 / Z10

`Moi` reste compact et pointe vers les owner APIs Recognition/Loyalty et l'index Partner. Makolo Mark orchestre vers ces mêmes vérités sans les posséder. Z9 fournit des identités stables, links, states et capabilities utilisables ensuite par Z10 sans dépendance à l'ORM.
