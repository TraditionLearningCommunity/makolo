# Audit Makolo — base pour la simulation Frontière d’opportunité

Référence auditée : `main` au commit `c829a30fc7198aa969595e050defbc41779e8df8`.

## 1. Règle d’acteur de ce laboratoire

Le laboratoire traite uniquement le cas :

```text
actor = Profile
represented_space = None
beneficiary = ce même Profile lorsque la capacité concerne sa propre action
```

Une Permission ou un Mandate détenu par ce Profile pour un Space ne transforme jamais une action du Space en action personnelle.

Cette contrainte est nécessaire parce que plusieurs selectors actuels de Makolo répondent à « que peut faire cet acteur ? » au sens large, et incluent donc des actions rendues possibles par une autorité déléguée.

## 2. Briques réutilisables telles quelles conceptuellement

### Journey / Readiness

`readiness.selectors.participant_readiness_queryset(profile, ...)` filtre explicitement les Journeys sur `beneficiary=profile` puis charge les faits canoniques nécessaires à Readiness. C’est une très bonne source pour l’état personnel.

### Access

`core.participant_selectors.participant_accesses(profile)` filtre `Access` sur `beneficiary=profile`. La représentation personnelle d’un droit peut donc être distinguée du simple fait que le Profile contrôle un Space.

### Saved Opportunity / Prepared Start

`opportunities.selectors.saved_opportunities(profile)` part des `OpportunitySave` appartenant au Profile. `core.home_presentation._prepared_start_actions()` compose ensuite `prepared_start_for_revision()` et `actions_from_prepared_start()` sans créer une seconde vérité métier.

### R2 Contextual Actions

`docs/architecture/contextual-actions.md` et `preparation.contextual_actions` établissent un contrat important : les faits restent dans leurs domaines propriétaires, les adaptateurs normalisent seulement des conséquences actionnables, puis le resolver applique une priorité transverse explicite, sans score ML/LLM.

La simulation conserve donc cette structure :

```text
faits/projections -> contraintes fortes -> plans admissibles -> Pareto
```

Elle ne remplace pas les contraintes fortes par Pareto.

### Proactive Preparation

R3 classe les changements entre deux états calculés (baseline, unchanged, non-material, material) à partir de signatures pures. Cette logique confirme qu’un futur moteur peut raisonner sur `S(t) -> S(t+Δ)` sans rejouer tout le passé.

## 3. Surfaces qui exigent un filtre personnel

### Dossier

`objectives.selectors.dossiers_for_profile(profile)` retourne :

- les Dossiers dont `owner_profile=profile` ;
- mais aussi des Dossiers visibles ou gérables par Permissions/Mandates sur des Spaces ou sur le Dossier.

Pour le grand bouton personnel, le sous-ensemble strict est donc conceptuellement :

```text
Dossier.owner_profile == profile
Dossier.owning_space is None
```

Le modèle Dossier impose déjà exactement un contexte propriétaire Profile ou Space ; aucun nouveau modèle n’est nécessaire.

### Action Network

`social.profile_search.action_proposals_requiring_actor_response(actor)` est volontairement une inbox canonique plus large. Elle inclut :

- `OWNER_TO_CANDIDATE` vers `candidate_profile=actor` ;
- `CANDIDATE_TO_OWNER` lorsque `need.owner_profile=actor` ;
- mais aussi des propositions pour un `candidate_space` ou un `need.space` que l’acteur a l’autorité de gérer.

Dans le contexte personnel, seules les deux premières formes sont retenues.

### Conversations

`conversations.attention.attention_points_for_profile()` est viewer-aware, mais la raison `resolve` peut dépendre de `can_manage_conversation()`. Or ce dernier accepte aussi des permissions Space/Activity/Dossier.

Pour le contexte personnel :

- `respond`, `acknowledge`, `form`, `revisit` restent des demandes adressées au Profile lorsqu’il est dans l’audience requise ;
- `resolve` ne doit être retenu que si l’autorité vient d’un contexte personnel possédé par le Profile (par exemple Activity personnelle, Dossier personnel, besoin personnel), d’une Journey dont il est bénéficiaire/initiator, d’une proposition personnelle, ou d’une conversation directe ;
- un simple pouvoir de gestion d’un Space ne suffit pas.

## 4. Accueil Mature actuel

`core.home_presentation.build_mature_home()` compose actuellement :

```text
Journey/Readiness
Dossier
Prepared Start
Conversation attention
Action Network proposals
Recognition
```

puis appelle `resolve_contextual_actions()` et produit :

```text
primary_attention
primary_action
action_items
knowledge_items
upcoming
all_clear
```

C’est un excellent banc d’essai pour le futur grand bouton, mais ce laboratoire ne modifie pas cette fonction.

## 5. Discover

Discover possède déjà `DiscoveryIntent`, un interpréteur déterministe et une augmentation IA provider-neutral facultative. Le programme Intelligence & Discover exige que les domaines restent propriétaires de leurs contrats et qu’aucune capacité critique ne dépende d’un provider.

Pour la première simulation du grand bouton, les nouvelles possibilités Discover sont gardées comme un **deuxième régime** : elles ne passent dans le pool principal que lorsqu’aucune contrainte P0/P1 personnelle ne réclame d’abord l’attention.

## 6. Traduction de Frontière d’opportunité vers Makolo

La simulation n’assimile pas les concepts métier à des masses ou forces physiques. Elle traduit seulement la structure mathématique :

```text
S(t)          = projection de l’état personnel courant
T_i           = cible/action Makolo concrète
Pi_i          = plans admissibles pour atteindre cette cible
C_i           = vecteurs de performances de ces plans
L_i           = Pareto local de la cible
P             = Pareto global de l’union des L_i
F             = labels des cibles qui contribuent à P
```

Les dimensions choisies pour le laboratoire sont des coûts concrets et homogènes dans leur sens (tous à minimiser) :

```text
user_minutes
cash_cents
travel_minutes
steps_remaining
```

Aucune somme pondérée n’est faite entre elles.

Les priorités Makolo `P0..P4` ne deviennent pas une cinquième dimension : elles restent un **gate déterministe en amont**. Exemple : une annulation ou un blocker P0 ne doit pas être « compensé » par un autre candidat moins cher.

## 7. Collision audit

Au moment de l’audit :

- PR #221 modifie le shell/navigation M8 UX ;
- PR #222 modifie Discovery Presentation ;
- le laboratoire ne touche aucun de leurs fichiers.

Le dossier racine `frontiere_opportunite_lab/` est donc volontairement isolé pour éviter une collision avec M8 et pour permettre d’évaluer la théorie avant intégration.

## 8. Critères de sortie de la simulation

La simulation est considérée utile si elle démontre au minimum :

- exclusion stricte des actions Space-only du contexte personnel ;
- conservation des actions personnelles issues de plusieurs domaines ;
- Pareto local puis global ;
- cible accessible mais globalement dominée ;
- pluralité de cibles de frontière ;
- changement de frontière après une action réelle ;
- screening sans faux rejet dans les scénarios construits ;
- absence de modèle persistant ou d’appel IA.
