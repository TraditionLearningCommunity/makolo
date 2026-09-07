# Recognition — Network Utility kernel v1

> **Statut : noyau technique v1, coefficients de production non décidés.**
>
> Ce document décrit la première persistance nécessaire pour rendre le moteur de Recognition simulable, idempotent et auditable. Il ne transforme pas les interactions Makolo en barème fixe et ne remplace aucune vérité métier des domaines sources.

## 1. But

Makolo doit pouvoir reconnaître une contribution utile à son réseau d'action sans confondre :

- fait métier et Points ;
- action réelle et événements techniques qui la prouvent ;
- valeur instantanée et utilité qui continue dans le temps ;
- acteur humain d'une opération et sujet auquel l'impact appartient ;
- valeur réseau et valeur économique ;
- Recognition plateforme et Loyalty d'un Espace.

Le pipeline cible reste :

```text
Domain facts / Domain Events / Analytics
        ↓ adapters
Utility observations
        ↓
Impact episodes / Action outcomes
        ↓
Temporal impact slices
        ↓
finite point pool
        ↓ Attribution
Profile XOR Space + UNATTRIBUTED
        ↓
immutable Points ledger
```

Le kernel v1 persiste seulement ce qui est nécessaire à l'idempotence, à l'accumulation et au ledger. Les observations, épisodes, outcomes, scores de rareté et claims d'attribution restent des contrats/projections jusqu'à ce que des besoins de persistance démontrés apparaissent.

## 2. Frontière avec Loyalty

`loyalty` reste le domaine de fidélité **propre à un Espace/Organization**, avec ses programmes, tiers, memberships et règles historiques order/ticket/check-in.

Recognition est une capacité plateforme distincte :

- sujet = exactement un Profile ou un Space ;
- impact dérivé de l'utilité observée ;
- aucune règle `points_per_ticket`, `points_per_order` ou `points_per_checkin` n'est réutilisée comme vérité Recognition ;
- aucun backfill ou transfert automatique des soldes Loyalty n'est effectué ;
- une convergence future peut extraire des primitives techniques communes de ledger, sans fusionner les sémantiques.

Points Recognition et Points Loyalty peuvent donc coexister tant que leurs surfaces et responsabilités restent explicitement séparées.

## 3. Contrats non persistés

### `RecognitionSliceCandidate`

Un adapter produit une tranche déjà évaluée en impact, avec :

- `slice_key` : identité globale stable anti-double-compte ;
- `accrual_key` : identité du cumul auquel appartient la tranche ;
- `channel` : Capacity, Coverage, Actionability, Real Action, Economic, Reliability, Durability ou Promotional ;
- `temporal_profile` : PULSE, WINDOW, STOCK ou FLOW ;
- `occurred_at` : moment où la réalité s'est produite ;
- `available_at` : moment où cette réalité est devenue consommable par Recognition ;
- `impact_delta` : nouvel impact, jamais l'impact déjà reconnu ;
- `attribution_shares` : parts Profile/Space dont la somme est inférieure ou égale à 1 ;
- métadonnées minimales d'audit, sans dupliquer des données privées sources.

`available_at` est volontairement distinct de `occurred_at`. Une preuve arrivée en retard peut donc entrer dans une fenêtre ultérieure sans réouvrir et recompter les anciennes fenêtres.

## 4. Fenêtres d'évaluation

La cadence par défaut v1 est **24 heures**.

Cette cadence répond à : « quand Makolo constate-t-il les nouveaux effets ? » et non à : « combien valent-ils ? ».

Un `RecognitionCursor` conserve :

- la Policy utilisée ;
- la taille de fenêtre ;
- la fin de la dernière fenêtre terminée.

Une `RecognitionEvaluationWindow` représente une fenêtre demi-ouverte :

```text
[starts_at, ends_at)
```

Les adapters doivent sélectionner les faits d'après leur disponibilité dans cette fenêtre, tout en conservant leur `occurred_at` réel.

Invariant :

> Relancer un worker, changer la fréquence du cron ou retraiter une fenêtre ne doit jamais créer de Points supplémentaires pour les mêmes slices.

Le cursor n'avance qu'après clôture valide de la fenêtre.

## 5. Anti-double-compte

`RecognitionSliceReceipt.slice_key` est globalement unique.

Une slice déjà reçue devient un no-op strict lors d'un retry. Le receipt historique n'est ni modifié ni supprimé.

Cette identité est distincte de la corrélation métier d'un `ActionOutcome`. Les futurs adapters ont la responsabilité de produire un même `slice_key` pour la même tranche réelle et de ne pas traduire Journey + Payment + Access + fulfilment comme plusieurs résultats lorsque ces faits prouvent le même outcome.

## 6. Accumulation des petits impacts

Un arrondi par fenêtre ferait perdre les micro-contributions persistantes. Le kernel utilise donc `RecognitionAccrual`.

Pour un même `accrual_key + policy_version` :

```text
cumulative_impact(t)
    ↓ policy
cumulative_point_target(t)
```

La nouvelle tranche ne mature que :

```text
point_pool_delta = target_after - target_before
```

Conséquences :

- une bourse peut produire plusieurs jours de petits FLOW avant de maturer `+1` Point ;
- découper artificiellement le même impact en davantage de slices ne crée pas davantage de pool ;
- le même impact déjà cumulé n'entre jamais une deuxième fois ;
- une nouvelle Policy démarre une nouvelle lignée d'accrual sans repricer le ledger historique.

## 7. Courbe Points

Le kernel définit une interface `PointsTargetPolicy` et seulement une `SimulationPolicyV0` pour les tests/simulations.

Ses coefficients ne constituent **pas** le barème de production.

La courbe est appliquée au cumul d'impact **avant** attribution pour créer un pool fini. Cette position est une précision v1 importante : appliquer une courbe concave séparément à chaque contributeur permettrait de créer artificiellement plus de Points en multipliant les contributeurs.

Avec un pool fini :

```text
Σ grants + UNATTRIBUTED = pool
```

La conservation est vérifiée au niveau de chaque slice et de chaque fenêtre.

## 8. Attribution v1 du pool

Le kernel reçoit des parts déjà produites par l'Attribution Engine/adapters.

Chaque part cible exactement :

- un Profile ; ou
- un Space.

La somme des parts explicites doit être `<= 1`. Le reste est `UNATTRIBUTED`.

La conversion d'un pool entier vers des entiers utilise une méthode déterministe de plus grands restes afin que l'arrondi conserve exactement le total.

Le kernel ne persiste pas encore les `AttributionClaim` détaillés. Le futur Attribution Engine pourra les dériver notamment à partir de OPERATE, ORCHESTRATE, DELIVER, ENABLE, AMPLIFY et MAINTAIN, avec causalité et décroissance downstream.

## 9. Compte global de Points

`RecognitionAccount` appartient exactement à :

```text
Profile XOR Space
```

Il conserve trois agrégats opérationnels :

- `points_balance` : disponible maintenant ;
- `lifetime_earned` : total historiquement gagné ;
- `lifetime_spent` : total historiquement utilisé.

Une dépense :

```text
balance -= points
lifetime_spent += points
lifetime_earned inchangé
```

Dépenser ses Points ne fait donc jamais perdre l'historique de contribution ni un Achievement fondé sur cet historique.

## 10. Ledger

`RecognitionLedgerEntry` est la source de vérité historique des mouvements de Points.

Le ledger est signé :

- `GRANT` : crédit ;
- `SPEND` : débit ;
- `REVERSAL` : écriture compensatrice future ;
- `ADJUSTMENT` : correction explicitement auditée future.

Les lignes sont immuables. Toute correction est une nouvelle écriture.

Chaque opération porte une `idempotency_key` globale unique. Les grants dérivent leur clé de `slice_key + subject`.

`points_balance` est une projection transactionnelle et doit rester reconstructible par la somme du ledger.

## 11. Concurrence

Les opérations qui modifient un solde utilisent une transaction et un verrou `select_for_update` sur le compte.

Une utilisation de Points vérifie le solde **après** acquisition du verrou. Deux dépenses concurrentes ne peuvent donc pas consommer les mêmes Points sur PostgreSQL.

Le traitement d'une slice verrouille aussi sa fenêtre puis son accrual avant maturation et attribution.

Les tests PostgreSQL sont obligatoires avant intégration finale de ce kernel.

## 12. Reversal et solde négatif

Le schéma prévoit un type `REVERSAL`, mais le service v1 ne l'implémente pas encore.

Le choix retenu pour le prochain checkpoint est de ne pas exposer silencieusement un solde négatif. Le service de reversal devra distinguer :

- Points encore disponibles : débit compensateur normal ;
- Points déjà dépensés : dette/hold Recognition explicite ou autre règle canonique à décider avant activation.

Aucune reprise n'est déclenchée par un simple changement de Policy.

## 13. Scheduler / Autopilot

`recognition.automation.run_recognition_cycle()` existe comme orchestrateur injecté :

- provider d'observations/slices ;
- Policy ;
- cursor ;
- fenêtre.

Il n'est **pas encore branché** à `automation.scheduler.run_autopilot_cycle()`.

Cette absence est volontaire : brancher un provider vide en production puis avancer le watermark ferait perdre la possibilité de traiter ensuite des faits historiques devenus disponibles. Le branchement Autopilot arrivera avec le premier ensemble d'adapters réels.

## 14. Sources futures privilégiées

Le kernel ne doit pas importer directement tous les modèles métier. Les premières sources doivent être choisies parmi :

- Domain Events canoniques ;
- `AnalyticsFact` lorsque sa projection est suffisante ;
- selectors/read models canoniques quand un delta nécessite un état avant/après ;
- adapters métier très fins lorsque le Domain Event ne contient pas assez de contexte.

Le code source reste la vérité ; Analytics ne devient jamais propriétaire de Payment, Journey, Access, Capacity ou Activity.

## 15. Scope du premier checkpoint

Le checkpoint kernel livre :

- contrats génériques ;
- fenêtre/cursor 24 h configurable ;
- `available_at` pour données tardives ;
- accrual des micro-impacts ;
- pool fini et conservation ;
- compte Profile XOR Space ;
- ledger immuable ;
- dépense idempotente et transactionnelle ;
- simulation Policy non-production ;
- tests d'idempotence, cumul, dépense et fenêtres.

Il ne livre pas encore :

- barème de production ;
- adapters Domain Events/Analytics ;
- scoring Scarcity/Marginality réel ;
- Attribution Engine complet ;
- Rewards/Entitlements/Payment bridge ;
- UI ;
- API ;
- activation Autopilot ;
- backfill.

## 16. Critères de sortie avant activation réelle

Avant de distribuer des Points à des utilisateurs réels :

1. calibrer au moins une Policy avec les scénarios de simulation ;
2. livrer des adapters réels avec `slice_key` stable et `available_at` documenté ;
3. tester les collisions et dépenses sous PostgreSQL ;
4. vérifier les migrations et la reconstruction des balances ;
5. ajouter observabilité des pools, `UNATTRIBUTED`, grants, spends et erreurs ;
6. tester cancellations/refunds/reversals avant d'activer les canaux économiques ;
7. brancher ensuite Recognition au scheduler Autopilot canonique ;
8. garder Loyalty et Recognition séparés dans l'UX et les APIs tant qu'une convergence explicite n'est pas décidée.
