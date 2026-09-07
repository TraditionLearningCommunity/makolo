# Recognition v1 — plateforme de crédits Makolo

## Promesse

Recognition sert la promesse **« Makolo marche pour vous »** : la valeur qu'un Profile ou un Space rend possible dans le réseau Makolo est reconnue, puis peut faciliter une action suivante.

Recognition ne mesure pas la réussite physique d'un événement et ne corrige pas rétroactivement ses crédits à partir d'une interprétation externe. Un paiement Makolo peut produire de la valeur, puis un remboursement Makolo produire une nouvelle valeur distincte.

> Recognition transforme les actions déjà rendues possibles dans Makolo en capacité supplémentaire d'avancer.

## Pipeline

```text
Domain Events / faits canoniques
  -> adapter sémantique borné
  -> RecognitionSignal minimal
  -> Policy/Rule déclarative
  -> mesure par Signal
  -> agrégation objet/fenêtre
  -> normalisation + courbe + modulateurs
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

Les profils temporels v1 sont `PULSE`, `WINDOW`, `STOCK`, `FLOW`, `TRANSITION`. Les fenêtres pilotent **quand** la valeur est observée, jamais sa quantité. `occurred_at` reste le temps du fait métier ; `available_at` est le moment où Recognition a effectivement reçu le fait. Un Domain Event livré tardivement peut ainsi être traité dans une fenêtre encore ouverte sans réécrire son temps métier ni rouvrir une fenêtre clôturée.

Les Rules sont évaluées par objet et fenêtre. L'agrégation (`SUM`, `COUNT`, `COUNT_DISTINCT`, `AVG`, `MIN`, `MAX`, `DELTA`, `SUM_DISTINCT_OUTCOME`, `LATEST_STATE`) précède la normalisation et la courbe. Les modes de combinaison `additive`, `exclusive` et `max` sont des comportements exécutés, pas seulement des métadonnées d'administration.

## Contrats de Signals et confidentialité

Recognition ne copie pas librement les payloads des Domain Events. Chaque type de Signal accepté possède un contrat explicite de champs et de types. `record_signal` applique le même contrat à tous les adapters : un adapter ne peut donc pas contourner la minimisation en appelant directement la couche d'ingestion.

Le DSL ne peut référencer que les champs exposés par le contrat du Signal. Les champs non numériques ne peuvent pas entrer dans une formule numérique. Une Rule utilisant un montant monétaire doit fixer explicitement la devise dans son scope ou ses conditions ; Recognition ne réalise aucun FX implicite.

Les contributeurs sont eux aussi bornés à des sujets `Profile` ou `Space` explicites avec un poids causal positif. Un Space peut être attribué lorsque le Domain Event porte son contexte. Une attribution personnelle n'est ajoutée que lorsqu'une causalité existe dans les faits/modèles canoniques (par exemple auteur d'une révision publiée, créateur d'un partage ayant effectivement déclenché une Démarche). Un Membership, un titre ou une Assignment seuls ne créent aucun crédit.

## Policy administrable

Une Policy contient des Rules versionnées. Le staff autorisé configure : Signal, scope, conditions, mesure, normalisation, temporalité, agrégation, courbe, modulateurs, identité d'outcome, combinaison et attribution. Le DSL est fermé : aucun Python, SQL ni parcours libre des modèles métier.

La Policy par défaut est volontairement conservatrice et permet au runtime de fonctionner avant configuration. Un remboursement reçoit par défaut la moitié du poids d'un paiement (`1` contre `2`) sans prétendre établir une conversion monétaire.

Avant publication, une Policy importante est simulée sur les Signals historiques. La simulation applique les mêmes règles d'agrégation et de combinaison que le runtime, mais ne crée ni receipt, ni ledger, ni consommation de Signal. Une version publiée est remplacée par une nouvelle version plutôt que réécrite. Le jeu de Rules d'une Policy publiée est fermé : aucune Rule ne peut être ajoutée ou modifiée après publication.

## Persistance

- `RecognitionAccount` : exactement Profile ou Space, jamais un champ sur User ;
- `RecognitionSignal` : projection sémantique minimale et bornée ;
- `RecognitionEvaluationWindow` / `RecognitionCursor` : cadence et watermark ;
- `RecognitionAccrual` : cumul haute précision empêchant l'inflation par découpage ;
- `RecognitionSliceReceipt` : preuve idempotente d'une tranche consommée ;
- `RecognitionObjectEvaluation` / `RecognitionAllocation` : historique objet -> pool -> sujets et évidence causale ;
- `RecognitionLedgerEntry` : vérité historique append-only des mouvements ;
- balance, lifetime earned/spent, pending et correction deficit : projections opérationnelles ;
- `AchievementDefinition` / `AchievementGrant` : accomplissements séparés des crédits ;
- `RewardDefinition` / `RecognitionRedemption` : économie administrable et utilisation.

Une correction n'est admise que pour une erreur interne Recognition. Elle produit une écriture compensatrice. Si les crédits erronés ont déjà été utilisés, le solde visible reste à zéro et le reliquat devient `correction_deficit`; les gains futurs l'absorbent avant de devenir disponibles. Il n'existe donc pas de dette Recognition visible pour l'utilisateur.

## Achievements et badges

Un Achievement ne constitue ni un solde ni un tier global. Ses critères peuvent reconnaître une trajectoire : nombre d'allocations, objets distincts, canaux distincts, modes causaux distincts, Rules distinctes ou crédits effectivement attribués, en plus des agrégats de compte. `Badge` reste une présentation de l'Achievement.

Une fois accordée, la définition utilisée ne peut plus être réinterprétée ou supprimée. Une évolution de sens passe par une nouvelle définition. Les grants et leur évidence restent historiques.

## Confidentialité et autorité

Les crédits d'un Profile sont privés. Un Space exige `space.recognition.view`; l'utilisation de ses crédits exige `space.recognition.spend`. Membership ne suffit jamais. Les opérations de Policy, économie, Achievements et audit utilisent des Permissions plateforme dédiées.

Il n'existe pas de leaderboard global Recognition. La suppression d'un sujet ne doit jamais entraîner une suppression implicite de l'historique Recognition ; les références protégées et le ledger préservent l'intégrité historique, avec divulgation minimale dans les projections.

## Utilisation, bénéficiaire et Rewards

Les crédits peuvent être utilisés pour le sujet propriétaire ou au bénéfice d'un autre Profile/Space lorsque la Reward l'autorise. Le bénéficiaire reçoit le bénéfice, pas un transfert de wallet. Le transfert libre de crédits n'est pas une capacité v1.

Une Reward porte une version, un coût, des dates, du stock et des règles d'éligibilité possibles (type de bénéficiaire, seuil propriétaire, quota par propriétaire ou bénéficiaire). Le catalogue privé ne présente qu'une version active par code, la plus récente, et filtre les Rewards non utilisables par le compte courant.

Lorsque `acceptance_required` est actif pour un autre Profile, la dépense est enregistrée mais le fulfillment reste en attente du consentement. Un refus annule l'utilisation et restitue les crédits au propriétaire sans créer de nouveaux crédits gagnés. Une acceptation permet au domaine propriétaire de réaliser le bénéfice.

`ENTITLEMENT` possède un bridge v1 réel vers le service canonique `subscriptions.runtime_services.create_entitlement_grant`; Recognition ne modifie pas les modèles Subscription et ne devient pas propriétaire de l'Entitlement. Les autres kinds (`Promotion`, `Access`, `Introduction`, `Payout`, etc.) restent des demandes à déléguer à leurs domaines propriétaires tant qu'un bridge canonique explicite n'est pas fourni.

Une Reward déjà utilisée devient historique : son coût, son fulfillment et ses règles ne sont plus modifiables. Le staff crée une nouvelle version pour faire évoluer l'offre.

## Présentation des crédits

Le stockage reste un entier de crédits. L'interface compacte uniquement la présentation avec les préfixes usuels : `2k crédits`, `63,3G crédits`, puis `T`, `P`, `E`, `Z`, `Y` si nécessaire. Aucun nouveau symbole ou nouvelle unité métier n'est introduit.

## Invariants de fermeture K

1. même fait + même Policy + même état antérieur -> même résultat ;
2. un outcome est consommé au plus une fois ;
3. somme allocations + UNATTRIBUTED = pool ;
4. le nombre de contributeurs n'augmente pas le pool ;
5. aucun succès/échec externe ne reprixe le passé ;
6. un remboursement Makolo est un nouvel épisode positif, pas une annulation des crédits du paiement ;
7. les micro-valeurs s'accumulent avant arrondi ;
8. une nouvelle Policy ne reprixe pas le ledger historique ;
9. simulation et émission réelle sont séparées ;
10. Profile/Space seuls détiennent un solde ;
11. les crédits restent privés par défaut ;
12. une utilisation pour autrui ne transfère pas le wallet ;
13. un bénéfice nécessitant consentement n'est pas imposé au bénéficiaire ;
14. une correction interne ne produit jamais de solde utilisateur négatif ;
15. les payloads métier privés ou non contractuels n'entrent pas dans Recognition ;
16. une formule monétaire n'effectue aucun FX implicite ;
17. une Policy publiée, une Reward utilisée et un Achievement accordé ne sont pas réinterprétés silencieusement ;
18. les règles économiques et les coûts de Rewards restent des données administrables, pas des constantes codées ;
19. Recognition délègue toujours Entitlement, Payment/Payout, Promotion, Access et Action Network à leurs domaines propriétaires ;
20. la finalité de Recognition reste d'accélérer la prochaine action, pas de créer une destination de score.
