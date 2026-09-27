# A2 — Acceptance matrix

> **Statut : gate A2-P0 pour développement, intégration et QA**
>
> Une case n'est validée que par un comportement observé/testé, pas par présence de code.

## 1. Matrice surface × état

Légende :

- **REQ** : obligatoire pour fermer A2 ;
- **N/A** : non applicable seulement avec justification écrite ;
- **A3** : profondeur explicitement reportée, mais aucun CTA mort n'est permis.

| État / scénario | Maintenant | Découvrir | Mark | En cours | Moi | Avatar |
|---|---:|---:|---:|---:|---:|---:|
| initial | REQ | REQ | REQ | REQ | REQ | REQ |
| first load sans local | REQ | REQ | REQ | REQ | REQ | REQ |
| local snapshot immédiat | REQ | REQ après pack A2 | draft REQ | REQ | REQ | identité REQ |
| content | REQ | REQ | REQ | REQ | REQ | REQ |
| empty | REQ | REQ | REQ | REQ | par section REQ | REQ |
| success | selon action | save/handoff selon owner | REQ | selon action | selon owner | logout/settings selon owner |
| refresh | REQ | REQ | N/A pour draft ; re-submit explicite | REQ | REQ | identité/context refresh REQ |
| offline avec contenu | REQ | REQ | draft REQ | REQ | REQ | identité locale REQ |
| offline sans contenu | REQ | REQ | REQ | REQ | REQ | REQ |
| stale | REQ | REQ | résultat si pertinent | REQ | REQ | autorité/contextes REQ |
| syncing | REQ | REQ | submit feedback | REQ | REQ | si refresh |
| pending | owner action | save/watch selon owner | confirmation/owner | owner action | owner action | logout work warning |
| sync failure | REQ | REQ | transport error | REQ | REQ | refresh error |
| retry | REQ | REQ | REQ | REQ | REQ | selon opération |
| conflict | si owner | saved/watch si owner | draft multi-device si installé | si owner | si owner | session/context si owner |
| back | REQ | REQ | REQ | REQ | REQ | REQ |
| resume | REQ | REQ | REQ | REQ | REQ | REQ |
| scroll/context restore | REQ si détail | REQ | draft | REQ | REQ | N/A/scroll sheet |
| deep link | REQ pour links supportés | REQ | handoff REQ | REQ | REQ | support account routes |
| text scaling | REQ | REQ | REQ | REQ | REQ | REQ |
| Semantics | REQ | REQ | REQ | REQ | REQ | REQ |
| Reduce Motion | REQ | REQ | REQ | REQ | REQ | REQ |
| session expiration | REQ | REQ | draft conservé | REQ | REQ | REQ |
| logout/relogin autre Profile | REQ | REQ | draft isolé | REQ | REQ | REQ |
| no fake content | REQ | REQ | REQ | REQ | REQ | REQ |
| no technical language | REQ | REQ | REQ | REQ | REQ | REQ |

## 2. Gate Maintenant

### Données

- [ ] GET /api/v1/me/now/ consommé via repository/store.
- [ ] Aucun tri métier local parallèle.
- [ ] links/capabilities conservés.
- [ ] snapshot Profile-isolated.

### États

- [ ] pas de snapshot + online ;
- [ ] pas de snapshot + offline ;
- [ ] items ;
- [ ] items + offline ;
- [ ] items + stale ;
- [ ] refresh avec contenu conservé ;
- [ ] erreur refresh avec contenu conservé ;
- [ ] items=[] synchronisé → vrai all-clear.

### UX

- [ ] **Tout est en ordre. ✓** seulement pour all-clear réel ;
- [ ] une action importante ressort ;
- [ ] pas de dashboard de cards ;
- [ ] pas de feed ;
- [ ] pas de message d'architecture.

### Navigation

- [ ] detail → back restaure Maintenant ;
- [ ] resume conserve l'onglet ;
- [ ] deep link owner-safe.

## 3. Gate En cours

### Données

- [ ] personal.ongoing local-first ;
- [ ] readiness/waiting/blocker/next non recalculés ;
- [ ] familles server-projected acceptées sans switch métier fragile ;
- [ ] links/capabilities honorés.

### Scénarios

- [ ] plusieurs Journey ;
- [ ] Access disponible ;
- [ ] waiting ;
- [ ] action needed ;
- [ ] blocker ;
- [ ] Dossier/Project si présents ;
- [ ] Waitlist offered vs waiting ;
- [ ] transfert incoming/outgoing si présents ;
- [ ] Payment pending si présent ;
- [ ] empty.

### UX

- [ ] différencie action de ma part / attente / prêt lorsque le serveur le permet ;
- [ ] pas de task manager ;
- [ ] pas de Kanban ;
- [ ] profondeur A3 non inventée.

## 4. Gate Mark

### Input

- [ ] champ texte réel ;
- [ ] validation vide ;
- [ ] limite de longueur alignée sur contrat ;
- [ ] draft local ;
- [ ] autosave raisonnable ;
- [ ] restore après interruption.

### États serveur

- [ ] resolved ;
- [ ] completed ;
- [ ] needs_clarification ;
- [ ] needs_confirmation ;
- [ ] unknown ;
- [ ] unsupported ;
- [ ] forbidden.

### Transport / offline

- [ ] transport error conserve le draft ;
- [ ] offline conserve le draft ;
- [ ] aucun completed local ;
- [ ] pas de blind replay sensible ;
- [ ] double submit maîtrisé.

### Confirmation

- [ ] conséquence humaine lisible ;
- [ ] server revalidation ;
- [ ] idempotency key lorsque requise ;
- [ ] succès uniquement après autorité distante.

### UX

- [ ] pas de menu de capacités ;
- [ ] pas de chat persistant fictif ;
- [ ] back restaure la surface précédente ;
- [ ] Reduce Motion fonctionne avec éventuel morphing.

## 5. Gate Découvrir

### Données

- [ ] utilise /api/v1/discovery/items/ mature ;
- [ ] pas le feed Event legacy comme source primaire ;
- [ ] pack local borné installé ;
- [ ] payload utile conservé sans duplication métier ;
- [ ] média cache réutilise A1.

### Recherche / filtres

- [ ] query online ;
- [ ] recherche offline dans corpus acquis ;
- [ ] filtres bottom sheet ;
- [ ] query/filtres restaurés après back ;
- [ ] scroll restauré ;
- [ ] pagination/boundary claire.

### États

- [ ] résultats ;
- [ ] aucun résultat ;
- [ ] pas de pack ;
- [ ] pack offline ;
- [ ] stale ;
- [ ] media absent ;
- [ ] media présent ;
- [ ] fin du corpus.

### UX

- [ ] visuel sans autoplay ;
- [ ] No Orphan Media ;
- [ ] pas de popularité générique ;
- [ ] pas d'infinite scroll artificiel ;
- [ ] disponibilité ancienne non présentée comme garantie.

## 6. Gate Moi

### Données

- [ ] personal.me local-first ;
- [ ] identity ;
- [ ] passport ;
- [ ] considerations ;
- [ ] collectives ;
- [ ] resources ;
- [ ] support ;
- [ ] links.

### Sections

- [ ] section absente → pas de card vide ;
- [ ] previews vides traitées intentionnellement ;
- [ ] authorized_spaces distinct de teams/groups ;
- [ ] resources sans secret ;
- [ ] support seulement si available.

### UX

- [ ] pas de Profile dump ;
- [ ] pas de profil social ;
- [ ] pas de grille de 20 raccourcis ;
- [ ] Avatar séparé.

## 7. Gate Avatar

### Identité

- [ ] auth/me distinct de personal.me ;
- [ ] compte courant compréhensible ;
- [ ] logout réel ;
- [ ] pending work traité avant suppression locale si nécessaire.

### Autorité

- [ ] contexts viennent uniquement du serveur ;
- [ ] membership seule ne crée aucun contexte ;
- [ ] aucun local state ne crée Permission/Mandate ;
- [ ] aucun faux act_as_space ;
- [ ] sélection d'un contexte visible seulement si handoff réellement supporté.

### UX

- [ ] bottom sheet/back naturel ;
- [ ] large text ;
- [ ] touch targets ;
- [ ] contexte courant annoncé ;
- [ ] pas sixième tab.

## 8. Gate cross-surface

Tester :

~~~text
Maintenant → Mark → retour
Maintenant → En cours
Découvrir → résultat → retour
Moi → Avatar → retour
deep link/notification → destination correcte
offline → changer d'onglet
resume → même onglet
session expire → reconnect → contexte restauré
logout Profile A → login Profile B → aucune fuite locale
~~~

Critères :

- [ ] bottom bar stable ;
- [ ] Mark reste action centrale ;
- [ ] headers contextuels cohérents ;
- [ ] indicateurs sync cohérents ;
- [ ] transitions courtes ;
- [ ] aucune route placeholder visible sur les six surfaces A2.

## 9. Gate visuel

Revue côte à côte :

~~~text
Maintenant → calme / priorité
Découvrir  → envie / exploration
Mark       → simplicité / intention
En cours   → continuité / progression
Moi        → identité / capital personnel
Avatar     → compte / contexte
~~~

Vérifier :

- [ ] hiérarchie ;
- [ ] rythme ;
- [ ] spacing ;
- [ ] typo ;
- [ ] contraste ;
- [ ] densité ;
- [ ] usage rare du Pulse ;
- [ ] Mark officiel ;
- [ ] aucune couleur Material par défaut ;
- [ ] aucune répétition de Card générique.

## 10. Gate performance perçue

- [ ] ouverture locale sans spinner quand snapshot présent ;
- [ ] pas de flash blanc ;
- [ ] skeleton seulement sans local ;
- [ ] image progressive ;
- [ ] pas de layout shift évitable ;
- [ ] listes fluides ;
- [ ] refresh non destructif.

## 11. Gate sécurité/confidentialité

- [ ] DB locale isolée par Profile ;
- [ ] no-store serveur n'est pas contourné par un cache web ; le store installé suit son contrat de sécurité A1 ;
- [ ] aucune Permission/Mandate dérivée client ;
- [ ] aucun AccessCredential/secret dans projection générique ;
- [ ] aucune PII inutile dans screenshot/golden/log ;
- [ ] autorité revalidée côté serveur ;
- [ ] session expirée ne valide aucune action sensible offline.

## 12. Gate tests / CI

Chaque lane :

- [ ] format ;
- [ ] analyze ;
- [ ] unit tests ;
- [ ] repository tests ;
- [ ] widget tests ;
- [ ] behavior state tests ;
- [ ] accessibility ciblée ;
- [ ] golden ciblés ;
- [ ] integration slice si faisable.

Intégration :

- [ ] generated-code check ;
- [ ] Mobile CI verte ;
- [ ] Android Build vert ;
- [ ] APK checkpoint quand le diff le justifie ;
- [ ] aucun test affaibli/supprimé pour obtenir du vert.

## 13. Gate appareil réel

Après P3 :

- [ ] install Android réel ;
- [ ] online ;
- [ ] couper réseau ;
- [ ] navigation offline ;
- [ ] relaunch offline ;
- [ ] retour réseau ;
- [ ] back gesture ;
- [ ] text scaling ;
- [ ] Reduce Motion si disponible sur l'appareil/test ;
- [ ] session recovery ;
- [ ] Mark draft recovery.

iOS ne peut être déclaré validé sans host/identity canonique réel.

## 14. Verdict

A2 ne passe que si toutes les exigences REQ applicables sont fermées.

Verdict final autorisé :

~~~text
A2 TERMINÉ — A3 READY
~~~

Sinon :

~~~text
A2 NON TERMINÉ

Blockers :
- ...
~~~
