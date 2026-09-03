# R2 — Contextual Actions & Priority

> **Statut : contrat backend du checkpoint R2 du train R — Préparation intelligente.** Ce document complète le Domain Blueprint, `readiness.md`, la Strategic Action Roadmap et la Mature Program Roadmap. Les domaines propriétaires restent la source de vérité ; R2 ne persiste aucune tâche ni aucun état global de readiness.

## 1. Question traitée

R2 répond à :

> **Dans ce contexte, quelle est la prochaine action utile et qu'est-ce qui mérite mon attention en priorité ?**

Pipeline :

```text
faits canoniques
        ↓
projections autorisées des domaines propriétaires
        ↓
adaptateurs R2
        ↓
ContextualAction
        ↓
priorité transverse explicite + déduplication exacte
        ↓
primary_attention / primary_action
        ↓
signature pure consommable par R3
```

R2 n'est ni une todo list, ni un bounded context de tâches, ni une seconde Readiness. Il ne crée aucun `Task`, `UserTask`, `ActionQueue`, feed, dashboard ou modèle de cockpit.

## 2. Frontière de propriété

Les faits restent propriétaires de leurs domaines :

- M1 Readiness porte ses `ReadinessCheck`, son `ReadinessResult` et son `NextAction` historique ;
- R1 Prepared Start porte les Requirement exacts d'une `OpportunityRevision`, Trusted Reuse et la distinction `READY / REVIEW_REQUIRED / CONFIRMATION_REQUIRED / UNKNOWN / MISSING` ;
- D porte Dossier et Collective Readiness privacy-safe ;
- Payment porte `PaymentObligation` et son payeur ;
- Access porte le droit ; Capacity porte les allocations ; Occurrence porte son état ;
- M6 porte `TemporalContext`, `Hazard` et `ActionAdvice` ;
- Assignment reste une responsabilité et Mandate reste l'autorité.

R2 **normalise seulement les conséquences actionnables de projections déjà autorisées**. Il ne lit pas directement ces modèles dans son resolver et ne réévalue aucune permission propriétaire.

## 3. Contrat `ContextualAction`

Le contrat est un dataclass Python immuable et non persistant. Une action contextualisée conserve :

- une `ContextualActionIdentity` explicite : `source_domain`, `source_key`, `action_key`, `context_type`, `context_id` ;
- un `kind` stable et technique ;
- un tier de priorité R2 ;
- une actionability explicite ;
- les `reason_codes` propriétaires ;
- un label et un résumé minimaux pour la présentation ;
- une CTA canonique optionnelle ;
- une deadline canonique optionnelle et sa relation déterministe à `observed_at` ;
- `confirmation_required` et `mandatory` lorsqu'ils sont connus ;
- `observed_at`.

`url = None` est valide. R2 ne fabrique pas d'URL pour compléter artificiellement le contrat et ne considère jamais une URL comme une autorisation durable : le service propriétaire doit revalider la permission lors de l'exécution.

## 4. Attention et actionability

Les états R2 sont :

- `TERMINAL` : fait dominant qui invalide l'action suivante dans le contexte, par exemple une Occurrence annulée ;
- `BLOCKING` : obstacle canonique qui doit être signalé avant une action de niveau inférieur ;
- `ACTIONABLE` : action que la projection propriétaire présente comme utile maintenant ;
- `WAITING` : rien d'utile n'est exécutable par l'acteur dans cette projection ;
- `ADVICE` : conseil non propriétaire d'un état métier, notamment M6 ;
- `INFORMATION` : information d'attention sans action exécutable.

Le résultat R2 expose séparément :

- `primary_attention` : le premier élément à comprendre ;
- `primary_action` : la première action réellement actionnable après application des blockers.

Une `TERMINAL` supprime `primary_action` dans le contexte résolu. Un `BLOCKING` P0 empêche qu'une action de niveau inférieur soit promue ; une résolution actionnable P0 peut en revanche devenir `primary_action`. Cela couvre notamment :

```text
Occurrence annulée + paiement requis
→ attention : annulation
→ action primaire : aucune

Access indisponible + access_action + leave_now
→ attention : Access indisponible
→ action primaire : action Access
→ leave_now n'est jamais promu devant le blocker
```

## 5. Tiers de priorité

R2 n'utilise aucun score composite, ML, LLM ou comportement utilisateur.

| Tier | Signification | Exemples |
|---|---|---|
| `P0_CRITICAL` | terminal ou blocker dominant | Occurrence annulée, Access indisponible, Journey expirée, blocker canonique |
| `P1_REQUIRED` | action obligatoire confirmée et actionnable | paiement requis, étape participant obligatoire, réponse d'invitation, formulaire obligatoire, Requirement Prepared Start obligatoire manquant/à confirmer |
| `P2_TIME_CONSTRAINED` | action non-P1 dont la contrainte temporelle canonique domine | `leave_now`, progression dont la deadline exacte est overdue/due today |
| `P3_PROGRESS` | progression utile sans urgence canonique | Journey draft, Requirement optionnel, vérification d'un Prepared Start `UNKNOWN` |
| `P4_INFORMATION` | attente, conseil ou information | attente d'un tiers, review Prepared Start, warning/information M6 |

La priorité est issue des faits et reason codes, pas du nom du domaine. `Payment` ne gagne donc pas toujours sur `Journey`, et M6 ne gagne pas toujours sur Prepared Start.

### `UNKNOWN` Prepared Start

`UNKNOWN` reste `UNKNOWN`. R2 produit au plus une action `verify_requirement` de progression et conserve `prepared_start.acceptance_unknown`. Il ne la transforme jamais en `MISSING`, `not eligible` ou blocker certain. Une confirmation Trusted Reuse connue et obligatoire reste une action P1 plus certaine qu'une vérification `UNKNOWN`.

## 6. Temps et tie-break

R2 ne définit aucun seuil « bientôt ». Une deadline n'est utilisée que si le caller fournit un datetime canonique déjà autorisé, indexé par `ReadinessCheck.key`, ou si la projection propriétaire l'exprime déjà.

Les relations supportées sont :

- `OVERDUE` ;
- `DUE_TODAY` ;
- `FUTURE` ;
- `NONE`.

À tier égal, l'ordre est :

```text
priority tier
→ actionability
→ deadline state
→ distance à la deadline canonique
→ mandatory
→ identité stable (context/source/action)
```

Aucun ordre DB, dictionnaire Python, provider, microseconde de calcul ou aléa n'intervient dans le tie-break.

## 7. Adaptateurs réellement supportés

### M1 Readiness

`actions_from_readiness()` parcourt **tous** les `ReadinessCheck` visibles. Il ne remplace pas `ReadinessResult.next_action`, qui conserve son comportement historique basé sur le premier contributor actionnable.

Les deadlines éventuelles sont fournies séparément par le caller sous forme `ReadinessCheck.key → datetime canonique`. R2 ne rouvre ni Payment, ni JourneyStep, ni FormRequest pour les découvrir.

### R1 Prepared Start

`actions_from_prepared_start()` consomme directement le `PreparedStartResult` R1 :

- `READY` ne produit aucune fausse action ;
- `REVIEW_REQUIRED` reste une attente ;
- `CONFIRMATION_REQUIRED` conserve la confirmation ;
- `MISSING` reste un gap connu ;
- `UNKNOWN` reste explicitement incertain ;
- `Requirement` et `OpportunityRevision` exacts font partie de l'identité R2.

R2 ne relit ni Action Memory, ni Library, ni Proof, ni Trusted Reuse.

### Dossier / Collective Readiness

`actions_from_dossier()` consomme uniquement le `DossierReadinessResult` déjà privacy-safe.

Une influence cachée devient **un seul signal opaque** `dossier.hidden_influence`. R2 ne reçoit ni n'ouvre la Journey cachée.

`DossierNextAction` conserve désormais, de façon rétrocompatible et uniquement pour une action déjà visible au bénéficiaire, les métadonnées techniques `key`, `source`, `source_key`, `reason_code` du check M1 d'origine. Cela permet de démontrer qu'une action visible dans Journey Readiness et la même action projetée dans Dossier ont réellement la même identité, sans dédupliquer par texte ou URL.

Si cette identité technique n'existe pas (ancien objet ou projection synthétique), R2 garde une identité Dossier locale et **refuse implicitement la déduplication par ressemblance**.

### M6 `ActionAdvice`

`actions_from_action_advices()` adapte les kinds M6 déclarativement :

```text
cancelled     → P0 / TERMINAL
access_action → P0 / ACTIONABLE
leave_now     → P2 / ACTIONABLE
warning       → P4 / ADVICE
information   → P4 / INFORMATION
```

Le `source_key`, le `reason_code`, le résumé, l'URL et `observed_at` M6 sont conservés. Le nombre `ActionAdvice.priority` reste une convention locale M6 et n'est pas transformé en score transverse R2.

### Assignment / Mandate

R2 n'a aucun adaptateur `Assignment → Action` brut. Une Assignment seule ne devient jamais une CTA. Si un domaine propriétaire, après ses propres règles de responsabilité **et** d'autorité, expose un `ReadinessCheck.ACTION_REQUIRED`, R2 peut normaliser cette projection autorisée. Membership, Assignment ou Dossier authority ne sont jamais utilisés par R2 pour fabriquer une permission.

## 8. Déduplication

La déduplication est exacte et conservatrice. La clé est `ContextualActionIdentity` :

```text
source_domain
source_key
action_key
context_type
context_id
```

Interdictions :

- label ;
- URL seule ;
- similarité de texte ;
- fuzzy matching ;
- embeddings ;
- LLM.

Deux paiements distincts portant tous deux le label « Payer » restent deux actions. Une Journey Readiness et une Dossier projection portant exactement la même identité technique deviennent une seule action.

## 9. Signature stable pour R3

R2 expose deux fonctions pures versionnées :

- `contextual_action_signature()` ;
- `contextual_action_result_signature()`.

La signature inclut la sémantique matérielle : identité stable, kind, tier, actionability, reason codes, CTA, deadline exacte + état temporel, confirmation et caractère mandatory.

Elle exclut volontairement :

- `observed_at` seul ;
- label ;
- résumé ;
- ponctuation ;
- ordre d'entrée/DB.

R2 ne persiste aucune signature et ne détecte aucun A→B. R3 décidera plus tard ce qui constitue un changement matériel, sa mémoire, ses événements/automations/notifications et l'anti-spam.

## 10. Privacy, performance et effets de bord

Règle centrale :

> **R2 peut composer des projections déjà autorisées ; il ne peut pas élargir leur visibilité.**

Les invariants restent :

```text
actor ≠ beneficiary
controller ≠ subject
initiator ≠ beneficiary
Assignment ≠ authority
Membership ≠ authority
Dossier authority ≠ Journey authority
Sharing ≠ Permission
```

La couche R2 n'exécute aucune requête DB. Elle travaille sur des objets déjà projetés ; la performance des lectures reste donc dans `readiness_queryset()`, `resolve_many()`, Prepared Start R1, les selectors Dossier et M6. La normalisation d'un nombre N de candidats est pure et ne crée aucun N+1.

Résoudre des ContextualActions ne crée ou ne modifie aucun Journey, JourneyStep, Payment, PaymentObligation, Access, CapacityReservation, RequirementAssessment/Evidence, PersonalAssetUse, JourneyArtifact, Proof, Dossier, Assignment, Notification, AutomationRun ou Domain Event.

## 11. Frontières R3 et M8

R2 ne construit :

- aucun Domain Event ou consumer de préparation ;
- aucune AutomationRun ;
- aucun scheduler ;
- aucune notification/email/push ;
- aucun état `last notified` ou curseur A→B ;
- aucune API globale `/api/me/next-actions/` ;
- aucun Accueil Mature, dashboard, feed, Cockpit ou navigation globale ;
- aucune IA décisionnelle.

**R possède les règles/projections de préparation ; M8 possède leur composition web.**

Handoff R3 :

```text
ContextualAction v1
+ tiers P0..P4
+ actionability explicite
+ identité exacte/déduplication conservatrice
+ tie-break déterministe
+ signatures r2-action-v1 / r2-result-v1
        ↓
R3 : ancien état vs nouveau → changement matériel ? → Automation/Notification si utile
```
