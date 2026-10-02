# Makolo — Adoption brownfield de Spec Kit

**Statut :** contrat d'outillage et de processus  
**Dépôt :** `TraditionLearningCommunity/makolo`  
**Intégration initiale :** Codex skills  
**Version Spec Kit épinglée :** `v1.0.13`  
**Script local privilégié :** PowerShell (`ps`)  
**Date d'adoption :** 2026-10-02

## 1. Objet

Spec Kit est introduit dans Makolo pour rendre les changements bornés plus traçables entre :

```text
problème utilisateur
→ spécification
→ plan contre le dépôt courant
→ tâches
→ implémentation
→ convergence
→ PR / CI / main
```

Il s'agit d'une couche de processus. Spec Kit n'est ni un bounded context Makolo, ni une source
de vérité métier, ni un remplaçant de `AGENTS.md`, du Domain Blueprint, des contrats canoniques,
des migrations, des tests ou de l'orchestration Git existante.

## 2. Pourquoi une adoption brownfield

Makolo est déjà un produit avancé. L'adoption ne doit donc pas reconstruire rétroactivement le
système sous `specs/`.

Le premier principe est :

> spécifier le prochain changement borné, pas réécrire l'histoire du produit.

Une feature Spec Kit décrit l'intention d'un changement précis. Le code et les documents canoniques
existants restent le contexte d'implémentation et les sources de vérité selon la priorité Makolo.

## 3. Source de vérité

Les artefacts Spec Kit sont subordonnés à la hiérarchie fixée dans la constitution Makolo :

1. code, migrations et tests actuels ;
2. `docs/architecture/makolo-domain-blueprint.md` ;
3. docs canoniques pertinentes ;
4. `docs/operations-runbook.md` ;
5. état GitHub courant ;
6. historique et handoffs.

Si `spec.md`, `plan.md` ou `tasks.md` deviennent faux après une évolution de `main`, ils
doivent être réconciliés. On ne force jamais le runtime à correspondre à une spec devenue obsolète.

## 4. Ce qui est installé

Le dépôt versionne le scaffold partagé de Spec Kit `v1.0.13` :

- `.specify/templates/` — templates upstream ;
- `.specify/scripts/powershell/` — scripts upstream ;
- `.specify/memory/constitution.md` — constitution Makolo ;
- `.specify/workflows/speckit/` — workflow upstream ;
- `.agents/skills/speckit-*/SKILL.md` — intégration Codex ;
- manifests d'intégrité et état d'intégration sous `.specify/integrations/`.

Les templates upstream ne sont pas personnalisés dans cette première adoption. Les contraintes
Makolo vivent dans la constitution et dans les documents canoniques existants, ce qui réduit le
coût des futures mises à jour de Spec Kit.

## 5. Ce qui n'est pas installé

La première adoption n'active pas :

- l'extension Git de Spec Kit ;
- l'extension bug ;
- l'extension assess ;
- des presets communautaires ;
- un workflow GitHub Actions supplémentaire ;
- une création automatique d'issues ;
- une migration du code produit.

Makolo possède déjà son propre contrat de branches, ownership, collision audit, PR, CI et merge.
Ajouter l'extension Git maintenant dupliquerait cette responsabilité.

## 6. Installation locale

Sur un poste de développement qui doit exécuter la CLI :

```powershell
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.0.13
specify --version
specify integration status --json
```

Le scaffold étant versionné dans le dépôt, un checkout normal n'a pas besoin de relancer
`specify init`.

Pour régénérer volontairement le scaffold géré, le faire uniquement sur une branche dédiée puis
examiner le diff :

```powershell
specify init --here --force --non-interactive --integration codex --script ps
```

Ne jamais accepter aveuglément un diff d'upgrade ou de régénération.

## 7. Invocation avec Codex

L'intégration Codex est basée sur les skills. La forme d'invocation est :

```text
$speckit-constitution
$speckit-specify
$speckit-clarify
$speckit-plan
$speckit-checklist
$speckit-tasks
$speckit-analyze
$speckit-implement
$speckit-converge
```

`$speckit-taskstoissues` reste disponible mais optionnel.

La constitution n'est pas rejouée pour chaque feature. Elle change uniquement lorsqu'une règle de
gouvernance Makolo change réellement.

## 8. Workflow Makolo recommandé

Avant `$speckit-specify`, le chantier possède déjà une branche Makolo dédiée créée depuis le
`main` vérifié.

### Specify

Décrire le problème utilisateur, le résultat attendu et les frontières de compatibilité. Éviter les
choix techniques prématurés.

### Clarify

Utiliser `$speckit-clarify` lorsque plusieurs interprétations changeraient réellement le scope,
l'autorité, la confidentialité ou l'expérience.

### Plan

Le plan Makolo MUST commencer par les preuves brownfield :

- HEAD `main` courant ;
- commits/PR/branches pertinents ;
- collision audit ;
- implémentation actuelle ;
- migrations et tests du domaine ;
- propriétaires canoniques ;
- conséquences opérationnelles.

Un plan qui repart d'une architecture imaginaire doit être rejeté.

### Tasks

Les tâches doivent être petites, traçables et porter des chemins concrets. Une tâche marquée
parallèle n'est réellement parallèle que si elle ne partage pas les mêmes surfaces d'écriture.

Pour deux agents :

```text
lane A : surface indépendante
lane B : surface indépendante
          ↓
     intégrateur unique
          ↓
        converge
```

Les changements sur les mêmes modèles, migrations, sélecteurs, navigation globale, fixtures ou
permissions doivent être séquencés ou confiés à un intégrateur unique.

### Analyze

Pour un changement non trivial, `$speckit-analyze` vérifie la cohérence entre constitution,
spec, plan et tâches avant l'implémentation.

### Implement / Converge

Après `$speckit-implement`, lancer `$speckit-converge`.

Si Converge trouve un écart réel, il doit enrichir les tâches ou signaler l'incohérence ; on
répète ensuite :

```text
implement
→ converge
→ gaps ?
   ├─ oui → implement
   └─ non → review / tests / CI
```

`Converged` ne signifie pas automatiquement « mergeable ». Les tests, la sécurité, la revue de
diff, la réconciliation avec `main` et la CI restent obligatoires.

## 9. Cycle de vie des specs

Pendant le chantier, les artefacts peuvent évoluer avec la découverte du code réel.

Après merge, le répertoire `specs/<feature>/` est conservé comme **trace historique de
livraison**, pas comme une nouvelle documentation canonique permanente.

Un changement futur important crée normalement une nouvelle feature/spec qui référence ce qui
existe déjà. On évite ainsi qu'une ancienne spec concurrence le runtime ou le Domain Blueprint.

## 10. Critère pour le premier pilote

Le premier pilote doit être :

- réel mais borné ;
- assez petit pour parcourir tout le cycle ;
- sans refonte transverse ;
- avec critères d'acceptation observables ;
- avec propriétaires canoniques identifiables ;
- avec un risque de collision faible.

Le but du pilote est d'évaluer si Spec Kit améliore effectivement la traçabilité et la fermeture
du travail Makolo avant d'étendre son usage à des chantiers plus larges.
