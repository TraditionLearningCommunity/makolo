# Makolo — Current Program Status

> **Statut : snapshot opérationnel.** Ce document décrit l'état observé du dépôt au **26 septembre 2026**. Il ne remplace pas les blueprints de domaine ni les roadmaps. En cas de divergence, le code, les migrations, les tests et l'état GitHub courant gagnent.

## Référence auditée

- Dépôt : `TraditionLearningCommunity/makolo`
- Branche principale : `main`
- HEAD Z15 intégré : `main@993e17d64372dea2d4da36c5c3274e5df378cb89`
- PR #288 — Z14 : mergée ; programme Z1–Z14 fermé
- PR #290 — M10.0 Shell & Structured Navigation : mergée ; aucune migration
- PR #303 — A0 architecture mobile local-first : mergée ; le développement Flutter reste un programme séparé
- PR #301 — W6 Desktop Power Layer & Closure : mergée ; Z15 ne modifie aucune surface W
- PR #304 — Z15 : mergée sur `main` après CI verte ; réconciliation backend des capacités orphelines intégrée
- PR #312 — W7 : chantier web de fermeture des capacités orphelines, basé sur le `main` post-Z15

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
- W6 intégré ;
- Z15 est intégré : les capacités backend orphelines sont classifiées et exposées sans rouvrir les surfaces personnelles ;
- W7 consomme ces contrats côté Web Mature/Espace sans construire Platform ;
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
```

L'ancienne PR Z7 #272 a été fermée comme supersédée par la PR réconciliée #274 déjà mergée.

Le closeout détaillé et les gaps classifiés sont dans [`z14-program-closeout.md`](z14-program-closeout.md).

Z15 est un chantier post-closeout borné de réconciliation des capacités backend devenues totalement ou partiellement orphelines. Il ne rouvre pas les surfaces personnelles et ne construit pas W. Son inventaire canonique est [`z15-orphan-capabilities-reconciliation.md`](z15-orphan-capabilities-reconciliation.md).

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

L'ancienne PR #248 a été remplacée par la réconciliation A0 intégrée via PR #303. Le contrat mobile local-first courant doit donc être lu depuis `main`, pas depuis l'ancienne branche divergente.

Le développement Flutter reste distinct de Z15.

## 6. Intelligence

L'intelligence cumulative et l'Univers Makolo ne bloquent pas la fermeture du backend personnel Mature. Aucun moteur IA, score humain universel ou nouvelle intelligence n'est requis par le contrat Z.

Makolo Mark reste un orchestrateur borné et owner-directed. Les futures capacités d'intelligence doivent étendre les fondations existantes sans devenir une seconde source de vérité métier.

## 7. Collision audit courant

PR ouvertes pertinentes après intégration Z15 :

- #252 Space archetypes : ancienne branche profondément divergente, programme Space séparé ;
- #270 ECC : documentation d'orchestration ;
- #283 Actor 6 : documentation ;
- #284 Pré-8 Actors/Universe input : documentation ;
- #223 research lab : isolé hors runtime.

W6 #301, ACT-F #305 et Z15 #304 sont intégrés. W7 #312 est le chantier Web borné qui consomme Z15 ; les autres lignes ouvertes ne doivent pas réécrire simultanément la Console Espace ni les runtimes Actors.

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

Z15 #304 a été fusionné après CI PR verte. W7 doit conserver la même règle : tests ciblés puis CI complète verte avant merge, sans migration ni affaiblissement des invariants d'autorité.

## 9. Prochaine décision

```text
Programme Z historique fermé
→ Z15 ✅ réconciliation backend orpheline intégrée
→ W7 fermeture Web des capacités réconciliées
→ Platform séparé après W
→ suite M10 / production readiness globale
→ A Mobile
```

M10.0 ne vaut pas déclaration de production readiness ; il ferme uniquement la couture de navigation personnelle qui aurait sinon forcé le client natif à parser des URLs HTML ou reconstruire des relations métier.
