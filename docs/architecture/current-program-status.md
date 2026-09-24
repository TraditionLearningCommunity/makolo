# Makolo — Current Program Status

> **Statut : snapshot opérationnel.** Ce document décrit l'état observé du dépôt au **24 septembre 2026**. Il ne remplace pas les blueprints de domaine ni les roadmaps. En cas de divergence, le code, les migrations, les tests et l'état GitHub courant gagnent.

## Référence auditée

- Dépôt : `TraditionLearningCommunity/makolo`
- Branche principale : `main`
- HEAD Z14 vérifié sur `main` : `bee273500a383941ac89796156e1e429ed9de345`
- PR #288 — Z14 : mergée ; CI post-merge verte
- Z1–Z14 : intégrés ; le programme Z est fermé
- M10.0 : gate final Shell & Structured Navigation ; lorsqu'il est présent sur `main` après CI verte, M10.0 est fermé ; aucune migration

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
- Z1–Z14 intégrés ; programme Z fermé ;
- M10.0 ferme la couture shell/navigation avant la suite du gate M10 ;
- M10 reste un gate global distinct. La fermeture de Z ne signifie pas « production-ready ».

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
```

L'ancienne PR Z7 #272 a été fermée comme supersédée par la PR réconciliée #274 déjà mergée.

Le closeout détaillé et les gaps classifiés sont dans [`z14-program-closeout.md`](z14-program-closeout.md).

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

L'ancienne PR #248 (`mobile/a0-phase-0-foundation`) a été réauditée : elle contient une petite fondation Flutter utile, mais sa base est profondément divergente du `main` courant et son ancien inventaire API précède Z1–Z13.

Classification : **needs adaptation**.

Règle de reprise :

```text
main fermé
→ contrat Z13
→ transplantation sélective de ce qui reste utile dans A0
→ A Mobile
```

Ne pas merger #248 telle quelle pour « fermer » Z.

## 6. Intelligence

L'intelligence cumulative et l'Univers Makolo ne bloquent pas la fermeture du backend personnel Mature. Aucun moteur IA, score humain universel ou nouvelle intelligence n'est requis par le contrat Z.

Makolo Mark reste un orchestrateur borné et owner-directed. Les futures capacités d'intelligence doivent étendre les fondations existantes sans devenir une seconde source de vérité métier.

## 7. Collision audit courant

PR ouvertes pertinentes au démarrage Z14 :

- #248 A0 Flutter : à adapter, pas à merger telle quelle ;
- #252 Space archetypes : programme Space séparé ;
- #270 ECC : docs d'orchestration ;
- #283 Actor 6 : docs ;
- #284 Pré-8 Actors/Universe input : docs ;
- #223 research lab : isolé hors runtime.

Aucune de ces PR n'est utilisée comme justification pour réécrire les surfaces personnelles Z14.

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

Le `main` Z12+ précédent avait également une CI verte avec 2519 tests Django. Z14 doit à son tour finir avec le dernier head vert, puis vérifier le `main` post-merge.

## 9. Prochaine décision

```text
Programme Z fermé
→ M10.0 Shell & Structured Navigation
→ suite M10 / production readiness globale
→ A Mobile
```

M10.0 ne vaut pas déclaration de production readiness ; il ferme uniquement la couture de navigation personnelle qui aurait sinon forcé le client natif à parser des URLs HTML ou reconstruire des relations métier.
