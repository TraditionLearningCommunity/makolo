# Recognition v1 — plateforme de crédits Makolo

## Promesse

Recognition sert la promesse **« Makolo marche pour vous »** : la valeur qu'un Profile ou un Space rend possible dans le réseau Makolo est reconnue, puis peut faciliter une action suivante.

Recognition ne mesure pas la réussite physique d'un événement et ne corrige pas rétroactivement ses crédits à partir d'une interprétation externe. Un paiement Makolo peut produire de la valeur, puis un remboursement Makolo produire une nouvelle valeur distincte.

## Pipeline

```text
Domain Events / faits canoniques
  -> RecognitionSignal
  -> Policy/Rule déclarative
  -> Utility delta
  -> accrual cumulatif
  -> pool fini de crédits
  -> attribution Profile XOR Space + UNATTRIBUTED
  -> ledger immuable + balance privée
  -> Achievement / Reward / utilisation pour soi ou un bénéficiaire
```

Le calcul du pool et sa répartition sont deux opérations distinctes. L'attribution conserve le pool : ajouter des contributeurs ne crée jamais plus de crédits.

## Moteur et runtime

`recognition.engine` est déterministe et ne fait ni ORM, ni I/O, ni lecture d'horloge. Le runtime Django traduit les modèles configurés en contrats purs, résout les sujets et persiste ensuite les résultats.

Les profils temporels v1 sont `PULSE`, `WINDOW`, `STOCK`, `FLOW`, `TRANSITION`. Les fenêtres pilotent **quand** la valeur est observée, jamais sa quantité. `occurred_at` et `available_at` restent distincts pour les faits tardifs.

## Policy administrable

Une Policy contient des Rules versionnées. Le staff autorisé configure : Signal, scope, conditions, mesure, normalisation, temporalité, agrégation, courbe, modulateurs, identité d'outcome et attribution. Le DSL est fermé : aucun Python, SQL ni parcours libre des modèles métier.

La Policy par défaut est volontairement conservatrice et permet au runtime de fonctionner avant configuration. Un remboursement reçoit par défaut la moitié du poids d'un paiement (`1` contre `2`) sans prétendre établir une conversion monétaire. Les montants peuvent être exploités plus tard par une Rule lorsque le Signal les expose explicitement.

Avant publication, une Policy importante est simulée sur des Signals historiques. La simulation ne crée ni receipt, ni ledger, ni consommation de Signal. Une version publiée est remplacée par une nouvelle version plutôt que réécrite.

## Persistance

- `RecognitionAccount` : exactement Profile ou Space, jamais un champ sur User ;
- `RecognitionSignal` : fait sémantique borné venant des adapters ;
- `RecognitionEvaluationWindow` / `RecognitionCursor` : cadence et watermark ;
- `RecognitionAccrual` : cumul haute précision empêchant l'inflation par découpage ;
- `RecognitionSliceReceipt` : preuve idempotente d'une tranche consommée ;
- `RecognitionObjectEvaluation` / `RecognitionAllocation` : historique compréhensible objet -> pool -> sujets ;
- `RecognitionLedgerEntry` : vérité historique des mouvements ;
- balance, lifetime earned/spent, pending et correction deficit : projections opérationnelles ;
- `AchievementDefinition` / `AchievementGrant` : accomplissements séparés des crédits ;
- `RewardDefinition` / `RecognitionRedemption` : économie administrable et utilisation.

## Confidentialité et autorité

Les crédits d'un Profile sont privés. Un Space exige `space.recognition.view`; l'utilisation de ses crédits exige `space.recognition.spend`. Membership ne suffit jamais. Les opérations de Policy, économie, Achievements et audit utilisent des Permissions plateforme dédiées.

Il n'existe pas de leaderboard global Recognition.

## Utilisation

Les crédits peuvent être utilisés pour le sujet propriétaire ou au bénéfice d'un autre Profile/Space lorsque la Reward l'autorise. Le bénéficiaire reçoit le bénéfice, pas un transfert de wallet. Le transfert libre de crédits n'est pas une capacité v1.

Une Reward décrit le coût et la délégation de fulfillment ; Recognition ne devient jamais propriétaire d'Entitlement, Payment/Payout, Promotion, Access ou Action Network.

## Invariants

1. même fait + même Policy + même état antérieur -> même résultat ;
2. un outcome est consommé au plus une fois ;
3. somme allocations + UNATTRIBUTED = pool ;
4. le nombre de contributeurs n'augmente pas le pool ;
5. aucun succès/échec externe ne reprixe le passé ;
6. les micro-valeurs s'accumulent avant arrondi ;
7. une nouvelle Policy ne reprixe pas le ledger historique ;
8. simulation et émission réelle sont séparées ;
9. Profile/Space seuls détiennent un solde ;
10. les crédits restent privés par défaut ;
11. une utilisation pour autrui ne transfère pas le wallet ;
12. les règles économiques et les coûts de Rewards restent des données administrables, pas des constantes codées.
