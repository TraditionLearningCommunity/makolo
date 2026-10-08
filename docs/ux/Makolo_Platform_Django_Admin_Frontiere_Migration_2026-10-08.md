# Makolo Platform ↔ Django Admin
## Frontière canonique, matrice de responsabilités et stratégie de migration

**Date :** 2026-10-08  
**Base runtime :** `main@52eced16a35d779f98eb8d43bbea405fd7f7b4b0`  
**Objet :** décider ce qui doit vivre dans Makolo Platform, ce qui doit rester Django Admin et comment migrer sans dupliquer les domaines.

---

# 0. Décision

```text
PLATFORM
→ travail opérateur récurrent
→ workflows humains
→ owner services
→ permissions Makolo
→ audit
→ diagnostic multi-domaines

DJANGO ADMIN
→ maintenance technique profonde
→ inspection model-centric
→ configuration framework
→ fallback exceptionnel
```

Django Admin ne doit pas être supprimé.

Django Admin ne doit pas être maquillé pour devenir Platform.

---

# 1. Critère principal

Une capacité appartient à **Platform** si elle répond majoritairement :

```text
un opérateur doit comprendre un contexte
+
prendre une décision humaine
+
agir via un domaine
+
répéter ce workflow régulièrement
```

Une capacité peut rester **Django Admin** si elle répond majoritairement :

```text
inspection technique rare
+
configuration framework
+
maintenance développeur
+
debug profond
+
action exceptionnelle
```

---

# 2. Règle de sécurité

Plus une mutation touche :

- autorité ;
- argent ;
- Trust ;
- visibility ;
- lifecycle ;
- publication ;
- secrets ;

moins elle doit reposer sur un simple formulaire ModelAdmin générique.

---

# 3. Matrice globale

| Capacité | Platform | Django Admin | Cible |
|---|---:|---:|---|
| Operations Overview | Oui | Non nécessaire | PLATFORM |
| Incidents | Oui | Inspection possible | PLATFORM |
| Organization lifecycle | Oui | Éviter mutation brute | PLATFORM |
| Event moderation | Oui | Éviter mutation brute | PLATFORM |
| Worker health | Oui | Inspection éventuelle | PLATFORM |
| Operations audit | Oui | Inspection possible | BOTH / Platform normal |
| Trust verification | Oui | Inspection possible | PLATFORM |
| Reports / disputes | Oui | Inspection possible | PLATFORM |
| Trust Evidence | Oui, protégée | Inspection exceptionnelle | PLATFORM |
| Opportunity curation | Oui | Inspection possible | PLATFORM |
| Subscription governance | Oui | Inspection technique | PLATFORM |
| Recognition policy | Oui cible | Oui actuellement | MIGRATE |
| Recognition audit | Oui cible | Oui actuellement | DUAL puis Platform |
| Recognition economy | Oui cible | Oui actuellement | MIGRATE |
| Platform interoperability | Oui | Config technique possible | PLATFORM |
| DomainEventOutbox | Peut-être N3 | Oui | ADMIN / SYSTEM DEPTH |
| DomainEventConsumption | Peut-être N3 | Oui | ADMIN / SYSTEM DEPTH |
| SocialApp credentials | Non | Oui | ADMIN |
| secrets / env | Non | Non UI valeur brute | ENV / ADMIN config safe |
| schema/migrations | Non | Non product UI | ENGINEERING |
| raw arbitrary model edit | Non | Oui seulement si justifié | ADMIN |
| emergency forensic inspection | Non | Oui | ADMIN |
| user-facing Profile/Space work | Non | Non | MAKOLO APP |

---

# 4. Operations Overview

**Platform : OUI**

Pourquoi :

- situation transverse ;
- signaux ;
- incidents ;
- workers ;
- paiements ;
- scans ;
- notifications ;
- organizations queue.

Django Admin ne donne pas ce modèle mental.

---

# 5. Organization lifecycle

**Platform : OUI**

Le runtime possède déjà les services :

```text
suspend_space
archive_space
restore_space
```

avec reason et audit.

**Django Admin :**
- lecture possible ;
- édition brute du lifecycle à éviter.

---

# 6. Event moderation

**Platform : OUI**

Actions :

```text
unlist
private
cancel
restore_public
```

avec reason.

**Admin :**
ne doit pas offrir un chemin plus facile qui bypass les services.

---

# 7. Incidents

**Platform : OUI**

Workflow opérateur.

Admin peut rester utile pour inspection DB exceptionnelle.

---

# 8. Worker Health

**Platform : OUI**

L’opérateur doit comprendre :

- état ;
- stale ;
- erreur ;
- dernier cycle.

Admin n’est pas nécessaire comme chemin normal.

---

# 9. Operations Audit

**Platform : OUI en lecture**

Admin peut conserver inspection profonde.

Les entrées restent créées par owner/services.

---

# 10. Trust Review

**Platform : OUI**

Le runtime possède déjà une file staff dédiée.

C’est un workflow humain clair.

Django Admin ne doit pas être le chemin normal de décision Trust.

---

# 11. Trust Evidence

**Platform : OUI mais strict**

- permission ;
- explicit open ;
- private/no-store ;
- audit si nécessaire.

Admin uniquement pour forensic exceptionnel.

---

# 12. Opportunity Curation

**Platform : OUI**

Les staff views actuelles sont déjà proches d’un module Platform.

Migration principale :

```text
shell + design + navigation
```

pas réécriture métier.

---

# 13. Subscriptions

**Platform : OUI**

Permissions dédiées déjà présentes.

Cibles :

- catalogue ;
- subscription ;
- transitions ;
- reviews ;
- entitlement grants.

Admin reste inspection/fallback.

---

# 14. Recognition Policies

**Aujourd’hui : Admin fortement utilisé**

**Cible : Platform**

Raison :

- simulate ;
- publish ;
- schedule ;
- lifecycle ;
- conséquence globale.

Ce sont des workflows, pas de simples edits de row.

---

# 15. Recognition Audit

**Aujourd’hui : Admin read-only**

**Cible : Dual**

Admin est très adapté à l’inspection brute.

Platform doit fournir une lecture humaine lorsque l’opérateur enquête.

Les deux peuvent coexister.

---

# 16. Recognition Achievement Definitions

**Cible : Platform**

Si les opérateurs les gèrent régulièrement.

Admin fallback pendant transition.

---

# 17. Recognition Rewards

**Cible : Platform**

Le workflow doit expliquer :

- cost ;
- beneficiary ;
- fulfillment owner ;
- immutabilité après usage.

---

# 18. Interoperability

**Platform : OUI**

La projection existe déjà.

Admin peut rester nécessaire pour certains credentials/config framework.

Platform n’affiche jamais secrets.

---

# 19. SocialApp OAuth/OIDC

**Django Admin : OUI**

Le runbook utilise déjà `SocialApp`.

C’est une configuration framework/infrastructure rare.

Pas besoin de la reconstruire dans Platform v1.

Platform peut seulement afficher :

```text
Google   Configuré
Facebook Non configuré
...
```

si une projection sûre existe.

---

# 20. Environment variables

**Ni Platform ni Django Admin ne doivent afficher les valeurs sensibles.**

Configuration par environnement.

---

# 21. Domain Events

Le runtime Admin actuel est prudent :

- readonly ;
- no add ;
- no delete ;
- requeue failed ciblé.

C’est un bon candidat pour rester Admin au début.

---

# 22. Domain Event requeue

Peut migrer dans Platform Système si ce workflow devient fréquent.

Mais uniquement avec :

- raison ;
- contexte ;
- attempts ;
- idempotence ;
- owner impact ;
- audit.

---

# 23. Raw model inspection

Admin reste meilleur pour :

- regarder les fields ;
- vérifier relations ;
- debug développeur ;
- incident exceptionnel.

Platform ne doit pas tout reproduire.

---

# 24. Raw model mutation

À réduire.

Particulièrement pour :

- lifecycle ;
- finance ;
- trust ;
- authority ;
- access ;
- publication.

---

# 25. Django Groups / Django permissions

Ne pas utiliser comme produit Makolo à la place de :

```text
Role
Mandate
Permission
```

existants.

---

# 26. `is_staff`

`is_staff` reste un gate technique Django Admin.

Il ne doit pas devenir le critère Platform.

---

# 27. `is_superuser`

Réserver :

- bootstrap ;
- maintenance ;
- récupération ;
- développeur autorisé.

Pas rôle quotidien.

---

# 28. Theming Admin

Customisation acceptable :

- titre clair ;
- avertissement `Administration technique` ;
- lien vers Platform ;
- environnement visible si sûr ;
- couleur distincte de production si connue ;
- hide models inutiles.

Customisation interdite comme stratégie :

```text
faire croire que Django Admin = Platform
```

---

# 29. Navigation Admin

Peut rester model-centric.

C’est précisément sa fonction.

Ne pas investir beaucoup dans un faux shell métier.

---

# 30. Admin read-only

De nombreux modèles sensibles devraient tendre vers :

```text
read-only
```

si leur mutation normale possède désormais un workflow Platform.

---

# 31. Admin actions

Conserver seulement :

- actions techniques réellement justifiées ;
- opérations sûres ;
- récupération.

Les actions métier fréquentes migrent.

---

# 32. Emergency actions

Toute action emergency dans Admin doit être :

- documentée ;
- rare ;
- auditable autant que possible ;
- couverte par runbook.

---

# 33. Break-glass

Un mécanisme break-glass explicite serait préférable à “tout superuser tout le temps” si le besoin devient réel.

Ce contrat ne crée pas encore ce mécanisme.

---

# 34. Stratégie de migration

## Étape A

Créer shell Platform et intégrer links vers workflows existants.

## Étape B

Operations, Trust, Opportunity deviennent visuellement Platform.

## Étape C

Subscriptions reçoit une vraie Presentation Platform.

## Étape D

Recognition Policies/Rewards/Achievements migrent hors Admin comme chemin normal.

## Étape E

System/Domain Events restent hybrid.

## Étape F

Réduire permissions Admin modèle par modèle.

---

# 35. Double-write interdit

Pendant migration :

```text
Platform
→ owner service
Admin
→ même owner service si mutation conservée
```

Pas deux logiques.

---

# 36. Double workflow temporaire

Possible seulement si :

- même service ;
- même validation ;
- même audit ;
- comportement testé.

---

# 37. Admin fallback

Quand Platform couvre correctement une capacité :

Admin devient :

```text
inspection
+
emergency fallback
```

---

# 38. Suppression d’un Admin workflow

Avant suppression :

- Platform équivalent complet ;
- tests ;
- runbook ;
- permissions ;
- audit ;
- rollback.

---

# 39. Matrice sécurité

| Risque | Platform | Admin |
|---|---|---|
| IDOR | tests owner selectors | staff gate + object perms |
| Secret leak | projection safe | fields masqués |
| Unsafe state transition | service owner | empêcher direct edit |
| Bulk destructive | owner bulk only | désactiver action |
| Missing audit | service logs | action custom audit ou désactiver |
| PII exposure | minimal | limiter champs |
| Wrong environment | indicator | indicator/title |
| Superuser overreach | non normal | break-glass only |

---

# 40. Definition of Done — Platform remplace Admin pour un workflow

Un workflow est migré quand :

1. les utilisateurs cibles n’ont plus besoin d’ouvrir Admin ;
2. toutes les actions passent par owner service ;
3. la Permission Makolo est correcte ;
4. les states/erreurs sont explicites ;
5. reason/confirmation existent ;
6. audit est conservé ;
7. concurrence est gérée ;
8. tests IDOR existent ;
9. Admin ne fournit plus un bypass simple ;
10. runbook est à jour.

---

# 41. Ce qui ne doit probablement jamais migrer

- édition de migrations ;
- introspection schéma ;
- secrets env ;
- SocialApp secret setup ;
- rare low-level forensic ;
- certaines tables techniques ;
- debug raw data autorisé ;
- actions de réparation réservées aux ingénieurs.

---

# 42. Ce qui doit presque certainement migrer

- lifecycle moderation ;
- incidents ;
- Trust queue ;
- disputes ;
- Opportunity curation ;
- Subscription reviews ;
- Entitlement grant governance ;
- Recognition policy publication ;
- Recognition economy governance ;
- worker/system health.

---

# 43. Anti-pattern final

Interdit :

```text
Django Admin
+
theme noir/violet
+
logo Makolo Platform
=
“Platform”
```

La frontière n’est pas esthétique.

Elle est :

```text
modèle mental
+
autorité
+
workflow
+
services
+
audit
+
sécurité
```

---

# 44. Formulation finale

> **Makolo Platform doit devenir le chemin normal des workflows opérateur récurrents et à forte conséquence, tandis que Django Admin reste une couche technique profonde pour inspection, configuration framework et maintenance exceptionnelle. La migration doit être progressive : on réutilise les services, permissions, selectors et audits existants, on enveloppe les capacités actuelles dans un shell Platform cohérent, puis on réduit les mutations directes de l’Admin au fur et à mesure que les workflows sûrs existent. Rethemer Django Admin ne suffit pas, car la différence essentielle n’est pas visuelle : Platform organise le travail autour d’une situation et d’une conséquence humaine, là où Django Admin organise l’accès autour des modèles et des rows.**
