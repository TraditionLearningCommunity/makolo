# Financement — verticale Activity

## Intention

La verticale **Financement** représente une possibilité Makolo dans laquelle réunir de l’argent permet de rendre une action réelle possible.

Elle respecte le principe **backend générique, métier contextuel** : `Activity` reste la vérité générique de la possibilité ; `FundingDetails` ajoute uniquement les faits financiers nécessaires à cette expression métier.

## Propriété des vérités

- `Activity` possède le titre, les descriptions, le propriétaire logique, le statut et la visibilité.
- `FundingDetails` possède la devise, l’objectif optionnel, les limites optionnelles de contribution et la fenêtre d’ouverture.
- `FundingContribution` conserve l’intention auditée d’un Profile de contribuer un montant donné.
- `PaymentObligation` et `Payment` restent propriétaires de l’exécution financière, des providers, états, preuves, remboursements, settlements et payouts.
- Discovery et Presentation ne possèdent aucun montant financier : ils projettent les faits des domaines propriétaires.

Une composition ne transfère jamais implicitement Permission, Mandate, Access, Payment ou accès à des données privées.

## Progression dérivée

Le montant `réuni` est la somme des contributions dont l’obligation de paiement est actuellement `SATISFIED`.

Pour un objectif `T` et un montant réuni `R` :

- `reste = max(T - R, 0)` ;
- `dépassement = max(R - T, 0)` ;
- l’objectif est atteint lorsque `R >= T`.

Presentation adapte alors le langage :

- avant l’objectif : **Reste à réunir** ;
- à l’objectif : **Objectif atteint ✓** ;
- au-delà : **Objectif dépassé de … ✓**.

Une situation sans objectif fixe affiche le montant réuni sans inventer de reste ni de pourcentage.

Un remboursement fait sortir l’obligation de l’état `SATISFIED` et la projection est recalculée ; aucun compteur financier parallèle n’est maintenu.

## Contribution

Une contribution :

1. est volontaire et initiée par un Profile authentifié ;
2. respecte la devise et les éventuels minimum/maximum du financement ;
3. crée une `PaymentObligation` canonique vers le propriétaire logique de l’Activity ;
4. poursuit ensuite le flux Payments existant.

La référence client fournit l’idempotence du geste de contribution. Une contribution auditée est immuable.

## Autorité

Pour un financement personnel, le propriétaire du Profile porte l’Activity.

Pour un financement porté par un Espace, la création exige à la fois l’autorité de gestion des Activities et l’autorité Finance de cet Espace. La gestion ultérieure exige également une autorité financière explicite dans le contexte Activity/Espace.

Membership, Group ou Team n’accordent aucune autorité financière implicite.

## Expérience

Le langage utilisateur reste contextuel : **Financement**, **Collecte**, **Soutenir**, **Contribuer** ou **Financer** selon la situation.

La surface de détail explique immédiatement :

- ce qui doit être rendu possible ;
- qui porte l’Activity ;
- l’objectif lorsqu’il existe ;
- le montant réuni ;
- ce qui reste à réunir ou le dépassement ;
- le prochain geste utile : **Contribuer**.

La même Activity peut utiliser Sharing pour être proposée à une personne, Dossier pour devenir un objectif actif, et Action Network lorsque son autorité a explicitement déclaré un besoin.

## Critère de sortie

Le financement doit permettre à Makolo de projeter correctement un fait de préparation comme **Financement réuni ✓** lorsqu’il est réellement satisfait, sans créer un second état générique de Readiness.
