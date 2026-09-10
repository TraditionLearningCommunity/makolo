# Résultats — Frontière d’opportunité appliquée à un Profile Makolo

Exécution de référence : Python standard, simulation V2, base conceptuelle auditée sur `main@a840455af8cd3cfc185404b4dc8c28a53bbb9eb6`.

Le script a été compilé puis exécuté avec succès avant versionnement. Toutes les assertions intégrées passent.

## 1. Résultat principal

La simulation montre qu’on peut insérer la Frontière d’opportunité **sans remplacer les lois Makolo existantes** :

```text
contexte acteur personnel
-> faits/projections métier
-> R2 : priorité / actionability / deadline / blocker
-> plans admissibles
-> Pareto local
-> safe screening
-> Pareto global étiqueté
```

La Frontière intervient donc à l’intérieur d’un régime déjà autorisé par Makolo, jamais pour compenser une obligation, une révocation d’Access ou une annulation.

## 2. Trajectoire temporelle exécutée

| Snapshot | État dominant | Frontière calculée |
|---|---|---|
| `t0_initial_personal_state` | P1 / due today | paiement universitaire + formulaire visa |
| `t1_after_payment` | P1 / due today | formulaire visa |
| `t2_after_required_form` | P1 / future | proposition mentor |
| `t3_capacity_hold_expired` | P0 blocker Capacity | aucune action de Frontière |
| `t4_capacity_committed` | P1 / future | proposition mentor |
| `t5_mentor_proposal_answered` | P1 / no deadline | confirmation Trusted Reuse |
| `t6_identity_reuse_confirmed` | P1 / no deadline | décision Recognition |
| `t7_recognition_decided` | P1 / no deadline | proposition reçue pour mon besoin |
| `t8_personal_need_proposal_decided` | P1 / no deadline | attestation bancaire manquante |
| `t9_bank_letter_prepared` | P3 / future | revisit Conversation |
| `t10_hidden_dossier_influence` | P0 blocker Dossier opaque | aucune action de Frontière |
| `t11_leave_now` | P2 / due today | partir maintenant |
| `t12_access_revoked` | P0 Access blocker | réparer/vérifier l’Access |
| `t13_access_restored_by_action` | P2 / due today | partir maintenant |
| `t14_departed_for_concert` | P3 / future | revisit Conversation |
| `t15_personal_actions_cleared` | P4 / Discover | exposition + atelier IA |
| `t16_discovery_frontier` | P4 / Discover | exposition + atelier IA |

Le scénario ne rejoue jamais l’état initial : chaque transition repart du `State` courant.

## 3. Premier front multi-cibles

À 16:00, deux obligations `P1_REQUIRED / DUE_TODAY` survivent à la comparaison.

### Paiement — virement

```text
deadline_minutes = 420
user_effort_min  = 10
cash_cdf         = 0
travel_min       = 0
elapsed_min      = 18
interactions     = 2
p1_after         = 6
```

### Paiement — carte

```text
deadline_minutes = 420
user_effort_min  = 4
cash_cdf         = 25000
travel_min       = 0
elapsed_min      = 4
interactions     = 1
p1_after         = 6
```

### Formulaire visa — préremplissage/réutilisation

```text
deadline_minutes = 450
user_effort_min  = 8
cash_cdf         = 0
travel_min       = 0
elapsed_min      = 12
interactions     = 2
p1_after         = 6
```

Aucun score `a*time + b*money + ...` n’est utilisé. Le paiement et le formulaire restent donc simultanément des possibilités efficaces : le paiement est plus urgent ; certaines voies du formulaire sont sans coût financier ; la carte est plus rapide mais payante ; le virement évite le coût mais demande plus d’effort/temps.

Le plan manuel du formulaire est éliminé localement avant la comparaison inter-cibles.

## 4. R2 reste un gate, pas un score de préférence

À `t5`, le tri déterministe R2 peut encore désigner une identité technique particulière comme `primary_attention` dans un ensemble P1 sans deadline. La Frontière n’utilise pas ce dernier tie-break technique comme vérité de préférence : à l’intérieur du même régime sémantique, elle compare les conséquences réelles des plans.

La confirmation Trusted Reuse survit alors seule :

```text
user_effort_min = 5
elapsed_min     = 6
interactions    = 1
p1_after        = 3
```

et le safe screening prouve temporairement hors Frontière :

```text
action-network:personal-owner
prepared-start:bank-letter
recognition:benefit
```

Elles ne sont pas supprimées de l’univers. Après la confirmation, elles sont réévaluées et reviennent successivement lorsque leurs concurrents disparaissent.

C’est exactement le principe :

> ne pas recalculer ce qui reste prouvé ; ne jamais oublier ce qui peut redevenir possible.

## 5. Capacity change la Frontière sans action du Profile

Le concert possède un hold Capacity qui expire à 17:20.

À 17:25 :

```text
HELD expiré -> capacity_not_secured -> P0 BLOCKING
```

La Frontière d’action est vide parce qu’aucune résolution personnelle canonique n’est fournie par ce blocker.

Quand un événement canonique sécurise ensuite la capacité comme `COMMITTED`, le blocker disparaît et la précédente action P1 redevient pertinente.

Cela valide que la Frontière dépend de `S(t)`, pas seulement de l’historique des choix utilisateur.

## 6. Dossier : divulgation minimale

Une influence cachée est introduite dans le Dossier personnel. Le seul texte projeté est le signal opaque :

> Un élément non visible affecte actuellement l’avancement de ce dossier.

Aucune identité, titre ou détail de la Journey cachée n’entre dans les données de Frontière.

Le signal est P0 blocking et suspend donc les comparaisons de niveau inférieur jusqu’à disparition du blocker.

## 7. M6 : le temps fait apparaître une action

Le scénario utilise :

```text
target_arrival = 20:00
route_duration = 35 min
safety_buffer  = 10 min
recommended_departure = 19:15
```

À 19:20, sans réinitialisation :

```text
now >= recommended_departure
-> leave_now
-> P2_TIME_CONSTRAINED
```

La Frontière contient alors `m6:concert:leave-now`.

Performance du plan :

```text
deadline_minutes = 40
user_effort_min  = 2
travel_min       = 35
elapsed_min      = 35
interactions     = 1
p2_after         = 0
```

## 8. Access révoqué : blocker + résolution

Après apparition de `leave_now`, l’Access personnel passe à `revoked`.

La projection contient simultanément :

```text
Readiness: P0 BLOCKING / access_unavailable
M6:        P0 ACTIONABLE / access_action
```

Le blocker reste l’attention primaire, mais le resolver autorise la réparation P0 comme action primaire. La Frontière contient donc uniquement le chemin de réparation :

```text
user_effort_min = 6
elapsed_min     = 8
interactions    = 2
p0_after        = 0
p2_after        = 1
```

Après restauration de l’Access, `leave_now` revient naturellement.

## 9. Discover : accessibilité puis Pareto

Quand les obligations/progressions personnelles sont dégagées, le scénario entre en régime P4 Discover.

Résultats :

```text
cancelled  -> exclue avant Pareto
soldout    -> inaccessible (capacity = 0)
seminar    -> accessible mais safe-screened / dominé
gallery    -> Frontière
workshop   -> Frontière
```

### Exposition

```text
deadline_minutes = 1080
user_effort_min  = 1
cash_cdf         = 5000
travel_min       = 12
elapsed_min      = 25
interactions     = 1
```

### Atelier IA — taxi

```text
deadline_minutes = 720
user_effort_min  = 8
cash_cdf         = 8000
travel_min       = 35
elapsed_min      = 45
interactions     = 2
```

### Atelier IA — transport moins cher

```text
deadline_minutes = 720
user_effort_min  = 10
cash_cdf         = 2000
travel_min       = 55
elapsed_min      = 75
interactions     = 2
```

L’exposition et l’atelier coexistent parce qu’aucun ne domine tous les compromis de l’autre. Aucun cap de diversité n’est nécessaire pour provoquer cette pluralité.

## 10. Frontière Personne / Space

Trois candidats volontairement extrêmement avantageux sont présents à chaque état :

```text
dossier:space:hidden
action-network:proposal:space
conversation:space-resolve
```

Ils sont P0/P1, coûtent presque rien, et gagneraient facilement si le calcul mélangeait les contextes.

Ils sont pourtant exclus **avant** le gate R2 et avant Pareto parce que :

```text
represented_space = None
```

L’exécution vérifie leur exclusion par assertion.

C’est un résultat central pour le futur grand bouton : une Permission d’Espace détenue par la personne ne doit pas contaminer la projection personnelle.

## 11. Déduplication Journey / Dossier

Le formulaire visa est projeté deux fois dans les données brutes :

- depuis Journey/Questionnaire ;
- depuis le Dossier personnel.

Les deux projections portent exactement la même `Identity`. Le moteur les fusionne avant calcul et l’exécution vérifie `deduplicated_identity_count >= 1`.

Aucune déduplication par libellé ou similarité n’est utilisée.

## 12. Edge case terminal

Une variante du monde marque l’Occurrence du concert `cancelled`.

Résultat :

```text
primary_attention = readiness:concert-cancelled
actionability     = TERMINAL
primary_action    = null
frontier           = []
```

Donc aucune possibilité moins urgente ne traverse artificiellement une annulation terminale.

## 13. Ce que l’expérience confirme / ne confirme pas

### Confirmé par cette simulation

- la théorie peut être composée avec les contrats Makolo sans nouveau modèle persistant ;
- Pareto doit venir **après** les invariants/gates métier ;
- l’état futur après action est une dimension utile pour éviter un simple biais « action la moins chère » ;
- Personne et Space doivent être séparés avant toute comparaison ;
- une cible screenée peut revenir plus tard ;
- les changements du monde (temps, Capacity, Access) déplacent réellement la Frontière ;
- Discover peut produire plusieurs possibilités efficaces sans diversité artificielle.

### Pas encore démontré

- que ce vecteur de performance est le vecteur final du produit ;
- que les coûts `user_effort_min`, `elapsed_min` ou `interactions` peuvent tous être obtenus de manière canonique dans le runtime actuel ;
- que la Frontière doit remplacer le `primary_action` de l’Accueil ;
- que les bornes de safe screening pourront être obtenues efficacement sur toutes les familles Makolo réelles ;
- que le cas `acting_as_space` suit les mêmes règles de projection.

La prochaine étape doit donc rester expérimentale : brancher progressivement **des projections réelles en lecture seule** dans ce laboratoire, ou rejouer des fixtures Makolo, avant toute modification de la surface produit.