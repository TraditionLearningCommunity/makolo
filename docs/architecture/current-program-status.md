# Makolo — Current Program Status

> **Statut : snapshot opérationnel.** Ce document décrit l'état observé du dépôt au **2 octobre 2026**. Il ne remplace pas les blueprints de domaine ni les roadmaps. En cas de divergence, le code, les migrations, les tests et l'état GitHub courant gagnent.

## Référence auditée

- Dépôt : `TraditionLearningCommunity/makolo`
- Branche principale : `main`
- HEAD audité avant Z16 : `main@ce1525075b61a7255e2a33ee8779af8a08c40008`
- HEAD Z15 intégré historique : `main@98618746d2d4c0ae1b3e1a4ce3da0c6bdfbca527`
- PR #288 — Z14 : mergée ; programme Z1–Z14 fermé
- PR #290 — M10.0 Shell & Structured Navigation : mergée ; aucune migration
- PR #303 — A0 architecture mobile local-first : mergée ; le développement Flutter reste un programme séparé
- PR #301 — W6 Desktop Power Layer & Closure : mergée ; Z15 ne modifie aucune surface W
- PR #304 — Z15 : mergée sur `main` après CI verte ; réconciliation backend des capacités orphelines intégrée
- PR #312 — W7 : mergée sur `main` après CI verte ; fermeture Web des capacités orphelines intégrée
- PR #333 — checkpoint d’intégration du programme A2.x : mergé après gates Mobile/Android/visual/smoke ; ce merge ne ferme pas le groupe A2
- PR #350 — docs post-A2 : mergée ; documentation mobile réconciliée
- PR #352 — Bloc D mobile natif : mergée ; conception Permissions/Push/Ingress/Ambient figée avant implémentation
- PR #355 — Z16 : exposition consommable M7 Profile/Space/Platform ; intégrée après CI verte
- PR #361 — W8 : consommation Web Profil de Z16 via Avatar → Connexions ; intégrée par ce changement après CI verte
- PR #419 — ZS6 : réconciliation finale du programme Space UX Projection ; mergée après CI complète verte sur `main@be289f4c0e1c044d297228505b73d0bab789e99c`
- PR #421 — WS1 : Space Web Experience Foundation ; mergée sur `main@af285c015881c2ff7cbeacc9df80f4d52593c8a6`, sans migration

Le snapshot doit être réactualisé lorsqu'un changement de programme important est mergé.

## 1. Position globale

La trajectoire reste cumulative :

```text
Makolo Mature
    ↓
Backend UX Projection / programme Z
    ↓
M10 / production readiness globale
    ↓
Makolo Mobile
    ↓
Intelligence cumulative / Agent selon les programmes futurs
```

Le programme Z n'est pas un nouveau domaine. Il a recomposé le backend existant pour que Web et futurs clients consomment des vérités métier propriétaires au lieu de reconstruire le métier depuis l'ORM.

## 2. Makolo Mature

État vérifié :

- M1–M7 livrés selon les docs canoniques et le runtime ;
- M8 Mature Web Experience intégré, y compris la convergence mobile-first #234 ;
- M9 hardening fermé sur sa base auditée, puis ses garanties pertinentes réutilisées par Z11/Z12 ;
- Z1–Z14 intégrés ; programme Z historique fermé ;
- M10.0 intégré ;
- A0 architecture mobile réconciliée ;
- programme A2.x en cours par sous-tâches ; #333 est un checkpoint d’intégration, pas une déclaration de fermeture du groupe ;
- W6 intégré ;
- Z15 est intégré : les capacités backend orphelines sont classifiées et exposées sans rouvrir les surfaces personnelles ;
- W7 est intégré : le Web Mature/Espace consomme ces contrats sans construire Platform ;
- W8 est intégré via PR #361 : le Profil Web consomme Z16 via Avatar → Connexions sans ajouter de N1 ;
- Z16 est intégré via PR #355 : le kernel M7 dispose d’un contrat API consommable Profile/Space/Platform sans inventer de catalogue runtime ;
- M10 reste un gate global distinct. Z15 ne signifie pas « production-ready ».

La navigation personnelle canonique reste :

```text
Maintenant | Découvrir | Makolo Mark | En cours | Moi
```

`Jour J` reste contextuel à une Occurrence actuelle. `Makolo Live` reste sous Jour J et appartient à Operations.

## 3. Programme Z — Backend UX Projection & API Composition

État réel :

```text
Z0    audit initial / baseline                 vérifié historiquement
Z1    contrat de projection                    ✅ intégré
Z2    Maintenant + En cours                    ✅ intégré
Z3    Découvrir                                ✅ intégré
Z4    Moi                                      ✅ intégré
Z5    détails engagés                          ✅ intégré
Z6    surfaces secondaires + Jour J/Live       ✅ intégré
Z7    Makolo Mark                              ✅ intégré
Z8    Passeport/Ressources/Groupes              ✅ intégré
Z9    Recognition/Loyalty/Partner               ✅ intégré
Z10   continuité inter-surfaces                 ✅ intégré
Z11   sécurité/autorité/confidentialité          ✅ intégré
Z12+  performance/stabilité/coût                ✅ intégré
Z13   contrat final Web/API/Flutter              ✅ intégré
Z14   fermeture/readiness mobile                 ✅ intégré
Z15   réconciliation capacités orphelines         ✅ intégré via PR #304
Z16   exposition consommable interopérabilité       ✅ intégré via PR #355
```

L'ancienne PR Z7 #272 a été fermée comme supersédée par la PR réconciliée #274 déjà mergée.

Le closeout détaillé et les gaps classifiés sont dans [`z14-program-closeout.md`](z14-program-closeout.md).

Z15 est un chantier post-closeout borné de réconciliation des capacités backend devenues totalement ou partiellement orphelines. Il ne rouvre pas les surfaces personnelles et ne construit pas W. Son inventaire canonique est [`z15-orphan-capabilities-reconciliation.md`](z15-orphan-capabilities-reconciliation.md).

Z16 ferme l’écart entre le kernel M7 et sa consommation client. Il expose un read contract scoped Profile/Space/Platform, projette les `intelligence.ProviderConnection` sans secrets et conserve des listes vides lorsque les registries M7 n’ont aucune installation runtime. Son contrat canonique est [`z16-interoperability-consumable-contracts.md`](z16-interoperability-consumable-contracts.md).

## 3 bis. Programme ZS — Space UX Projection

État réel après PR #419 :

```text
ZS1   socle Space UX Projection                         ✅ intégré
ZS2   Maintenant + Découvrir Space                     ✅ contrat minimal intégré dans ZS6
ZS3   Métier & Archetype Projections                   ✅ intégré
ZS4   Nous, Relations & Pilotage                       ✅ intégré
ZS5   Jour J, Live, Scanner & Makolo Mark              ✅ intégré
ZS6   réconciliation / sécurité / performance / handoff ✅ intégré via PR #419
```

ZS2 n'a jamais existé comme branche/PR indépendante. Le runtime final expose désormais `GET /api/v1/organizations/workspaces/<slug>/now/` et `GET /api/v1/organizations/workspaces/<slug>/discover/` avec une collection vide et `selection.state=unavailable` lorsqu'aucun sélecteur sûr n'existe. Aucun ranking, score ou heuristique Molongo n'est introduit.

Le contrat final et les matrices de convergence/autorité/handoff sont dans [`zs6-space-projection-final-handoff.md`](zs6-space-projection-final-handoff.md).

## 3 ter. Programme WS — Space Web Experience

État réel après PR #421 :

```text
WS1   Space Web Experience Foundation                  ✅ intégré
WS2   Maintenant & Découvrir                           ⏳ à venir
WS3   Métier & Archetypes                              ⏳ à venir
WS4   Nous, Relations & Pilotage                       ⏳ à venir
WS5   Jour J, Live, Scanner & Makolo Mark              ⏳ à venir
WS6   réconciliation / fermeture Web Space             ⏳ à venir
```

WS1 installe le shell Web Space au-dessus des projections ZS, la navigation primaire `Maintenant | Découvrir | Makolo Mark | Métier contextualisé | Nous`, la responsabilité de lecture revalidée serveur et le handoff explicite vers la Console historique. Il ne duplique ni Permission, ni Mandate, ni archetype, ni logique de ranking.

Le closeout détaillé est dans [`ws1-space-web-experience-foundation.md`](ws1-space-web-experience-foundation.md).

## 4. Contrat personnel prêt pour client natif

Les cinq surfaces principales ont des APIs canoniques :

```text
Maintenant   GET  /api/v1/me/now/
Découvrir    GET  /api/v1/discovery/items/
Makolo Mark  POST /api/v1/me/mark/
En cours     GET  /api/v1/me/ongoing/
Moi          GET  /api/v1/me/
```

Le client suit ensuite les owner handoffs Journey, Access, History, Jour J, Operations Live, Passport, Resources, Groups, Recognition, Loyalty, Partner, Dossier et Project.

Le backend décide Permission, Mandate, Readiness, Requirement satisfaction, Access validity, Now/Ongoing/History membership, Live eligibility et Space authority. Flutter ne les infère pas.

## 5. Makolo Mobile

Le programme mobile reste distinct du programme Z.

L'ancienne PR #248 a été remplacée par la réconciliation A0 intégrée via PR #303. Le programme A2 est un groupe de plusieurs sous-tâches A2.x : la PR #333 est un checkpoint d’intégration mergé, mais ne signifie pas que le groupe A2 est terminé. Sa documentation a été réconciliée via #350 et les sous-tâches suivantes doivent toujours être relues depuis l’état GitHub courant.

Z16 ne modifie pas Flutter. Il ajoute le contrat serveur que les sous-tâches pertinentes du programme A2.x peuvent consommer pour une surface Connexions sans connaître les registries Python ni l’ORM.

## 6. Intelligence

L'intelligence cumulative et l'Univers Makolo ne bloquent pas la fermeture du backend personnel Mature. Aucun moteur IA, score humain universel ou nouvelle intelligence n'est requis par le contrat Z.

Makolo Mark reste un orchestrateur borné et owner-directed. Les futures capacités d'intelligence doivent étendre les fondations existantes sans devenir une seconde source de vérité métier.

## 7. Collision audit courant

PR ouvertes pertinentes lors de l’audit Z16 :

- #353 Accounts/social auth : touche notamment `config/urls.py`, évité par Z16 ;
- #351 feedback mobile/device : Mobile + Accounts, sans reprise du contrat Z16 ;
- #308 hiérarchie UX personnelle : touche la navigation personnelle, volontairement hors Z16 ;
- #252 Space archetypes : ancienne branche profondément divergente, programme Space séparé ;
- #284/#283/#270 : documentation/Actors/orchestration ;
- #223 research lab : isolé hors runtime.

Z16 reste donc dans `interoperability/`, `intelligence/interoperability.py` et les URL modules déjà inclus, sans modifier `config/urls.py`, la navigation globale, l’Avatar, la Console Espace web ou Flutter.

## 8. Qualité et CI

Le head Z13 #287 a été mergé seulement après succès de :

- CI Django complète ;
- shards PostgreSQL ;
- E2E ;
- Security supply chain ;
- Beta seed validation ;
- Funding PostgreSQL ;
- Conversation PostgreSQL ;
- Subscriptions.

Z15 #304 et W7 #312 ont été fusionnés après CI PR verte. W7 n'a ajouté aucune migration et conserve les invariants d'autorité. Z16 #355 n’ajoute aucune migration et n’est intégrable qu’après CI PR verte.

## 9. Prochaine décision

```text
Programme Z historique fermé
→ Z15 ✅ réconciliation backend orpheline intégrée
→ W7 ✅ fermeture Web des capacités réconciliées
→ Z16 ✅ exposition consommable du kernel M7
→ W8 ✅ surface Profil Web Connexions via PR #361, après CI verte
→ programme A2.x en cours ; consommation mobile Z16 portée par les sous-tâches pertinentes
→ suite M10 / production readiness globale selon le `main` courant
```

M10.0 ne vaut pas déclaration de production readiness ; il ferme uniquement la couture de navigation personnelle qui aurait sinon forcé le client natif à parser des URLs HTML ou reconstruire des relations métier.
