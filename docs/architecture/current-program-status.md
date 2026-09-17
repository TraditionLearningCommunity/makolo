# Makolo — Current Program Status

> **Statut : snapshot opérationnel.** Ce document décrit l’état observé du dépôt au **17 septembre 2026**. Il ne remplace pas les blueprints de domaine ni les roadmaps ; il sert à réconcilier leur cible avec le runtime et l’état GitHub courant. En cas de divergence, le code, les migrations, les tests et l’état GitHub courant gagnent.

## Référence auditée

- Dépôt : `TraditionLearningCommunity/makolo`
- Branche principale : `main`
- HEAD observé pendant l’audit : `f7d7378ed1eeea175a4ce79474fca0e8eb4e4d85`
- Dernier merge observé sur `main` : PR #232 — realistic synthetic demo world
- `ci/aggregate` sur ce HEAD : **success**
- PR active structurante : **#234 — M8 — Mobile-first mature personal experience**
- Head PR #234 : `1973b03c38112c02bfa2aad3a46063a50a44fa03`

Ce snapshot doit être réactualisé lorsqu’un changement de programme important est mergé.

---

## 1. Position globale

La trajectoire produit reste cumulative :

```text
Makolo Mature
    ↓
Makolo Mobile
    ↓
Makolo Intelligence Kernel
    ↓
Makolo Agent
    ↓
Compétences / agents spécialisés
```

État observé :

| Couche | État au 17 septembre 2026 |
| --- | --- |
| Makolo Mature | très avancé ; backend/domaines/hardening largement fermés, convergence UX M8 finale encore en PR |
| Makolo Mobile | architecture et Phase 0 préparées ; implémentation Flutter pas encore réellement engagée sur `main` |
| Intelligence Kernel | fondations substantielles existantes ; runtime agentique transverse non encore construit |
| Makolo Agent | non encore livré comme boucle observe → plan → act → verify |
| Spécialisations | non encore livrées comme agents ; leurs domaines métier sont déjà largement présents |

Les pourcentages éventuels utilisés dans des discussions sont des estimations d’ingénierie, pas des métriques canoniques. Ce document préfère donc des états et preuves observables.

---

## 2. Makolo Mature

### Livré / stabilisé

La roadmap Mature marque déjà comme livrés :

```text
M1 ✅ Readiness Engine
M2 ✅ Forms, Questionnaires & Preparation Resources
M3 ✅ Presentation System
M4 ✅ Trust & Quality
M5 ✅ Social Action Network & Useful Engagement
M6 ✅ Spatiotemporal Intelligence, Hazards & Last-Minute
M7 ✅ Interoperability, Connections & Extension Platform
```

Le programme G — Profil, pertinence & réseau d’action — est également documenté comme terminé.

Les trains et domaines intégrés fournissent déjà notamment :

- Personal Assets / Action Memory / Trusted Reuse ;
- Prepared Start / Contextual NextAction / Proactive Preparation ;
- Dossiers / Projets / Collaboration ;
- Occurrence Operations ;
- Domain Events / Automation / Notifications ;
- Connections / Actions / Extension Platform ;
- Intelligence Foundation et Discover Intelligence ;
- réseau d’action, autorisation, Access, Capacity, Commerce, Payment, Trust, Geography et autres domaines canoniques.

### M9

Le hardening M9 a déjà été exécuté et documenté :

- sécurité, autorité, confidentialité et supply chain ;
- concurrence, idempotence et résilience externe ;
- migrations historiques et performance ;
- quality gate cross-domain et handoff vers M10.

L’existence de ce travail signifie que la séquence documentaire historique `M8 → M9 → M10` ne doit plus être lue comme « M9 reste à faire ». M9 a été fermé sur un état antérieur du runtime.

### M8 final actuellement ouvert

La PR #234 rouvre **M8 comme convergence finale de l’expérience personnelle mobile-first**, sans recréer les domaines ni annuler M9.

Elle porte notamment :

```text
Maintenant
Découvrir
Makolo Mark
En cours
Moi
```

avec :

- shell personnel commun mobile/desktop ;
- `/me/` recentré sur « ce qui compte maintenant » ;
- surface En cours ;
- surface Moi ;
- Makolo Mark central borné aux capacités réellement présentes ;
- conservation des routes profondes Journey / Access / History ;
- aucune migration métier ;
- aucune nouvelle vérité persistée ;
- Permission / Mandate / Access / Payment inchangés.

### Séquence réelle de fermeture à partir d’aujourd’hui

La séquence opérationnelle doit donc être lue ainsi :

```text
M1–M7 / G / grands trains        ✅
M8 initial                        ✅
M9 hardening                      ✅ fermé sur sa base auditée
M8 convergence mobile-first       🔄 PR #234
        ↓
réconciliation post-M8
        ↓
M10 / Mature Closure actualisé
        ↓
Mobile A0/A1
```

Après merge de #234, M10 doit vérifier que les garanties M9 restent vraies sur le runtime final au lieu de refaire M9 comme programme complet.

---

## 3. Makolo Mobile

Le programme mobile reste :

```text
A0 — Phase 0 / foundation
A1 — Application native
A2 — Native Capabilities
A3 — Ambient Makolo
A4 — Operations & Offline R&D
```

Décisions déjà établies :

- Flutter ;
- même dépôt GitHub ;
- backend Django reste source de vérité ;
- le mobile ne réimplémente pas Readiness, Permission, Payment, Access ou ranking ;
- le mobile exploite progressivement push, biométrie, caméra/scanner, partage, localisation, geofencing, voice/intents, haptique et capacités offline bornées.

État observé :

- branche `mobile/a0-phase-0-foundation` présente ;
- elle pointe encore sur le même commit que le `main` observé ;
- aucune PR ouverte observée pour cette branche ;
- aucun projet Flutter n’a encore été identifié sur `main` pendant l’audit.

Conclusion : **Mobile est préparé architecturalement, mais l’implémentation native reste à démarrer.**

---

## 4. Intelligence Kernel — ce qui existe déjà

Le Kernel futur ne part pas de zéro.

### Fondations déjà présentes

#### Intelligence Foundation

Le dépôt possède déjà une infrastructure transverse `intelligence` avec des concepts tels que :

- gateway ;
- capabilities provider-neutral ;
- provider registry / routing ;
- health / timeout / fallback ;
- structured output ;
- telemetry privacy-safe ;
- fonctionnement possible sans provider externe.

#### Mémoire utile à l’action

Makolo possède déjà :

- Personal Assets ;
- Action Memory ;
- Trusted Reuse ;
- JourneyArtifact ;
- Proof / Credential Trust dans leurs frontières propres.

#### Système nerveux interne

Makolo possède déjà :

- Domain Events ;
- Automation / Autopilot ;
- Notifications ;
- Proactive Preparation.

#### Contexte déterministe déjà riche

Le futur Context Builder pourra composer des vérités et projections déjà présentes :

- Profile ;
- Interests ;
- Open to ;
- Veilles ;
- Dossier / Journey ;
- Requirements / Readiness ;
- Prepared Start / NextAction ;
- Geography / Hazards ;
- Action Memory ;
- contexte d’autorité ;
- Connections / provider capabilities.

#### Sources externes structurées

Opportunity possède déjà un exemple important de séparation entre source externe, vérification de source et vérité canonique. Cette logique doit inspirer le Kernel sans forcer un modèle universel prématuré.

---

## 5. Intelligence Kernel — ce qui manque encore

Le Kernel n’est pas encore un runtime agentique complet.

Les briques principales restant à concevoir/implémenter sont :

```text
Perception générale
    Web search / fetch / watchers / APIs / documents / change detection

Observation contract transverse
    provenance / freshness / confidence / scope / sensitivity / fingerprint

Context Builder agentique
    contexte borné par actor / goal / time / authority

Working memory agentique
    état d’exécution, sans dupliquer Action Memory ni les domaines

Reasoner / Planner
    modèle + stratégies + budgets + retry policy

Policy / Consent Gate
    confirmation, privacy, authority, connection scopes

Tool Gateway agentique
    tools contrôlés enveloppant les services canoniques

Verifier / Evaluator
    règles déterministes, sources primaires, schemas, outcomes

Agent runtime loop
    observe → understand → plan → act → verify → update / stop
```

Invariant : **le Kernel étend les fondations `intelligence`, `automation`, M7, Action Memory et Domain Events ; il ne crée pas une seconde plateforme parallèle.**

---

## 6. Makolo Agent

Makolo Agent n’est considéré livré que lorsque Makolo peut poursuivre un objectif à travers plusieurs étapes avec une boucle contrôlée :

```text
Goal
  ↓
Observe
  ↓
Understand
  ↓
Plan
  ↓
Act through allowed tools
  ↓
Verify
  ↓
Replan or stop
```

Les mécanismes actuels Prepared Start, NextAction, Proactive Preparation, Veilles, Recommendations, Automation et Makolo Mark constituent des **précurseurs** ; ils ne doivent pas être présentés comme un agent général déjà livré.

---

## 7. Spécialisations

Les spécialisations viennent **après** le Kernel commun.

Exemples :

```text
Scholarship / Opportunity
Employment
Events / Concerts
Travel / Mobility
Operations
Services
```

Une spécialisation doit rester :

```text
Shared Kernel
+ Domain Playbook
+ Specialized Sources
+ Specialized Tools
+ Specialized Policies
+ Specialized Evaluators
```

Elle ne crée pas sa propre identité utilisateur, sa propre permission, sa propre mémoire générale ni sa propre plateforme provider.

---

## 8. Priorité de travail actuelle

Au snapshot du 17 septembre 2026 :

1. fermer proprement la PR #234 ;
2. vérifier les gates post-merge sur `main` ;
3. recalibrer M10 sur le runtime final, en réutilisant les preuves M9 encore valides ;
4. démarrer réellement Mobile A0/A1 avec Flutter dans le même dépôt ;
5. faire évoluer ensuite l’Intelligence Foundation vers le Kernel ;
6. fermer la première boucle Makolo Agent générale et bornée ;
7. seulement ensuite introduire les spécialisations par valeur et vérifiabilité.

Cette séquence n’interdit pas de préparer les contrats du Kernel en parallèle lorsque les surfaces ne collisionnent pas avec M8/Mobile, mais elle interdit de déclarer un agent livré avant que son runtime et ses frontières soient effectivement vérifiés.
