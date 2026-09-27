# A2 — Integration & handoff log

> **Statut initial : template A2-P0**
>
> Ce document devient le journal d'intégration A2 puis le handoff A3.
>
> Ne jamais remplir un SHA, un test, un build ou une validation par supposition.

## 1. Snapshot P0

### main audit

~~~text
main de départ P0:
98618746d2d4c0ae1b3e1a4ce3da0c6bdfbca527
W7 — Close orphan web capabilities (#312)
~~~

### A1 audit

~~~text
PR A1 principale:
#306 A1 — Installed Makolo Core
branche: mobile/a1-installed-makolo-core
head observé: 7e233118c207578ac4da65221a30009474ba75c8
état P0: OPEN / non fusionnée

PR fermeture native:
#319 A1 — close Android native identity and APK checkpoint
branche: mobile/a1-native-identity-closure
base: mobile/a1-installed-makolo-core
head observé le plus récent pendant P0:
e001aaeca85cdcc57da6db31b08f25aca97345e2
état P0: OPEN
~~~

Au dernier contrôle P0, les workflows du HEAD #319 sont terminés et verts : **Mobile CI**, **Mobile Android Build** et **Mobile APK**. #319 reste toutefois ouverte et non intégrée dans #306 ; #306 reste elle-même ouverte et non fusionnée sur `main`.

Conclusion P0 :

~~~text
A2_BASE_SHA = NON DÉFINI
A2-P1 = BLOQUÉ
lanes fonctionnelles = NON LANCÉES
~~~

## 2. Documents A2 P0

- [x] mobile-a2-program.md
- [x] mobile-a2-visual-behavior.md
- [x] mobile-a2-local-first-surfaces.md
- [x] mobile-a2-surface-contracts.md
- [x] mobile-a2-lane-action.md
- [x] mobile-a2-lane-explore-self.md
- [x] mobile-a2-acceptance-matrix.md
- [x] mobile-a2-integration-handoff.md

Branche P0 :

~~~text
docs/mobile-a2-p0-specs
~~~

La PR et son merge SHA seront ajoutés ci-dessous une fois réellement disponibles.

## 3. Gate avant P1

À revérifier dans cet ordre :

- [ ] main HEAD courant ;
- [ ] A1 #306 fusionnée ;
- [ ] branche #319 fermée/intégrée ;
- [ ] CI Mobile finale verte ;
- [ ] Android Build final vert ;
- [ ] APK checkpoint final vert si requis par A1 ;
- [ ] mobile/ présent sur main ;
- [ ] mobile-a1-installed-core.md présent sur main ;
- [ ] migrations Drift finales relues ;
- [ ] aucune migration Django A1 inattendue ;
- [ ] docs API/Product Language/brand réconciliées ;
- [ ] PR W/Z/autres trains collisionnées ;
- [ ] contrats Project Behavior + Local-first toujours alignés.

Si une case critique échoue, ne pas créer A2_BASE_SHA.

## 4. A2-P1 — shared checkpoint

À remplir seulement après gate précédente.

~~~text
main post-A1:
<sha>

branche intégration:
mobile/a2-integration

commit docs P0 réconciliées:
<sha>

corrections shared minimales:
<liste ou aucune>

A2_BASE_SHA:
<sha>
~~~

### Changements communs autorisés en P1

Seulement ce qui doit exister avant les lanes, par exemple :

- repository interfaces réellement transversales ;
- support central Discovery pack ;
- migration Drift nécessaire ;
- sync root central ;
- primitive header/Avatar commune si deux lanes en dépendent ;
- test de contrat partagé.

Aucun écran métier complet.

### Tests P1

~~~text
<commandes réelles>
<résultats>
~~~

## 5. Lane Action log

### Branche

~~~text
mobile/a2-action-orchestration
base: <A2_BASE_SHA>
~~~

### PR

~~~text
PR: <numéro/url>
head SHA: <sha>
merge SHA dans mobile/a2-integration: <sha>
~~~

### Surfaces

- Maintenant :
- En cours :
- Mark :

### Fichiers

~~~text
<liste/résumé>
~~~

### APIs

~~~text
<routes réellement consommées>
~~~

### Local-first impact

~~~text
<repositories/store/drafts/sync>
~~~

### Behavior states

~~~text
<états couverts>
~~~

### Tests

~~~text
<commandes réelles et résultats>
~~~

### Screenshots/goldens

~~~text
<chemins ou artefacts>
~~~

### Limitations / dette

~~~text
<uniquement faits observés>
~~~

### Review croisée reçue

~~~text
<commentaires du développeur 2>
~~~

## 6. Lane Explore/Self log

### Branche

~~~text
mobile/a2-explore-self
base: <A2_BASE_SHA>
~~~

### PR

~~~text
PR: <numéro/url>
head SHA: <sha>
merge SHA dans mobile/a2-integration: <sha>
~~~

### Surfaces

- Découvrir :
- Moi :
- Avatar :

### Fichiers

~~~text
<liste/résumé>
~~~

### APIs

~~~text
<routes réellement consommées>
~~~

### Local-first impact

~~~text
<Discovery pack / personal.me / account context>
~~~

### Behavior states

~~~text
<états couverts>
~~~

### Tests

~~~text
<commandes réelles et résultats>
~~~

### Screenshots/goldens

~~~text
<chemins ou artefacts>
~~~

### Limitations / dette

~~~text
<uniquement faits observés>
~~~

### Review croisée reçue

~~~text
<commentaires du développeur 1>
~~~

## 7. P3 — Integration log

### Base avant intégration

~~~text
main vérifié:
<sha>

mobile/a2-integration avant lanes:
<sha>
~~~

### Collision audit

- [ ] app/**
- [ ] navigation/**
- [ ] theme/behavior primitives
- [ ] auth/network/sync
- [ ] Drift tables/schema
- [ ] PersonalRepository historique
- [ ] Product Language
- [ ] brand assets
- [ ] API routes
- [ ] W/desktop changes pertinents.

### Intégration Action

~~~text
source merge SHA:
<sha>

conflits:
<liste>

résolution:
<résumé>
~~~

### Intégration Explore/Self

~~~text
source merge SHA:
<sha>

conflits:
<liste>

résolution:
<résumé>
~~~

### Wiring orchestrateur

À journaliser :

- AppShell ;
- router ;
- bottom navigation ;
- Mark central ;
- headers ;
- Avatar ;
- suppression placeholders ;
- repository cleanup ;
- sync indicators ;
- deep links ;
- back ;
- session recovery.

## 8. P4 — Cross-surface QA

### Produit

- [ ] bonnes questions humaines ;
- [ ] pas de feed générique ;
- [ ] pas de task manager ;
- [ ] pas d'ORM visible ;
- [ ] pas de faux contenu.

### Behavior

- [ ] loading ;
- [ ] empty ;
- [ ] error ;
- [ ] offline ;
- [ ] stale ;
- [ ] pending ;
- [ ] back ;
- [ ] resume ;
- [ ] refresh ;
- [ ] recovery ;
- [ ] accessibility ;
- [ ] Reduce Motion.

### Visuel

- [ ] hiérarchie ;
- [ ] rythme ;
- [ ] spacing ;
- [ ] typo ;
- [ ] contraste ;
- [ ] densité ;
- [ ] identité Makolo ;
- [ ] aucune esthétique Flutter générique.

### Scénarios cross-surface

~~~text
Maintenant → Mark → retour
Maintenant → En cours
Découvrir → résultat → retour
Moi → Avatar → retour
deep link/notification → bonne surface
offline → changer d'onglet
resume → même onglet
logout/relogin → isolation Profile
~~~

Résultats :

~~~text
<à remplir>
~~~

## 9. Build / device

### CI

~~~text
flutter format:
<résultat>

flutter analyze:
<résultat>

flutter test:
<résultat>

generated code:
<résultat>

Android Build:
<résultat>

APK:
<résultat>
~~~

### Smoke appareil réel

~~~text
appareil/type:
<non sensible>

install:
<résultat>

online:
<résultat>

offline:
<résultat>

relaunch offline:
<résultat>

back gesture:
<résultat>

text scaling:
<résultat>

Reduce Motion:
<résultat>

session recovery:
<résultat>
~~~

Ne jamais prétendre iOS validé sans environnement/host réellement disponible.

## 10. PR finale A2

~~~text
branche:
mobile/a2-integration

base:
main

titre:
A2 — Personal Makolo

PR:
<numéro/url>

head SHA:
<sha>

merge SHA:
<sha>

main final:
<sha>
~~~

Le corps de PR doit documenter :

- A1 base ;
- deux lanes ;
- surfaces ;
- architecture local-first ;
- Behavior ;
- visual system ;
- APIs ;
- screenshots ;
- tests ;
- accessibilité ;
- build Android ;
- migrations Drift éventuelles ;
- absence/présence justifiée de migration Django ;
- gaps A3.

## 11. Handoff A3

Uniquement les profondeurs réellement reportées.

Format :

| Gap | Surface A2 | Owner | Contrat disponible | Pourquoi A3 |
|---|---|---|---|---|
| <...> | <...> | <...> | <route/link> | <raison> |

Ne pas utiliser A3 comme poubelle à bug A2. Un bug d'une surface A2 reste A2.

## 12. Rapport final

~~~text
main de départ:
<sha>

A2_BASE_SHA:
<sha>

branche intégration:
mobile/a2-integration

branche développeur 1:
mobile/a2-action-orchestration
PR développeur 1:
<...>
merge SHA:
<...>

branche développeur 2:
mobile/a2-explore-self
PR développeur 2:
<...>
merge SHA:
<...>

PR finale A2:
<...>
merge SHA:
<...>

main final:
<sha>
~~~

### Surfaces

~~~text
Maintenant  ✅/❌
Découvrir   ✅/❌
Mark        ✅/❌
En cours    ✅/❌
Moi         ✅/❌
Avatar      ✅/❌
~~~

### Local-first

~~~text
offline     ✅/❌
stale       ✅/❌
refresh     ✅/❌
resume      ✅/❌
sync        ✅/❌
~~~

### UX

~~~text
Behavior        ✅/❌
visual          ✅/❌
motion          ✅/❌
haptics         ✅/❌
accessibility   ✅/❌
Product Language ✅/❌
~~~

### Verdict

Utiliser uniquement l'un des deux formats :

~~~text
A2 TERMINÉ — A3 READY
~~~

ou :

~~~text
A2 NON TERMINÉ

Blockers :
- ...
~~~
