# WS5 — Space Jour J, Live, Scanner & Makolo Mark — Web

**Statut :** branche d’implémentation WS5  
**Base initiale auditée :** `main@f3a7cf94514c94d65198b286bcf33e1cbe470697`  
**Branche :** `ws5-space-day-of-live-scanner-mark-web`  
**PR :** #430 — WS5 — Space Jour J, Live, Scanner & Makolo Mark  
**Portée :** Web Space uniquement ; aucune migration, aucun nouveau modèle, aucune nouvelle vérité Operations/Scanner/Access/Mark.

## 1. Objectif

WS5 ferme les profondeurs Web Space liées à l’action réelle :

- Jour J opérateur ;
- Live ;
- Scanner occurrence-scoped ;
- Makolo Mark dans le contexte Space.

Le chantier reste parallèle à WS2, WS3 et WS4. Il ne reprend ni Maintenant, ni Découvrir, ni Métier, ni Nous/Relations/Pilotage, ni le shell final.

Invariant de composition :

```text
owners / projections ZS5
        ↓
composition Web
        ↓
action owner-backed
        ↓
refetch / navigation
```

Le Web ne reconstruit ni Permission, ni Readiness, ni Live, ni Access.

## 2. Collision audit de départ

Au branchement :

- WS1 était intégré sur `main` via #421, avec closeout #424 ;
- WS2 #426 était ouvert et touchait notamment `organizations/space_web_views.py` ;
- WS3 #427 était ouvert et évitait volontairement ce fichier ;
- la branche `ws4-space-us-relations-pilot-web` était identique à `main` ;
- #428 corrigeait des régressions CI Space post-merge dans des tests partagés.

Décision WS5 :

- nouveaux views dans `organizations/space_ws5_web.py` ;
- templates propriétaires WS5 ;
- modification minimale de `organizations/urls.py` ;
- modification scanner JS strictement rétrocompatible : le scanner historique garde son comportement, WS5 seul désactive l’auto-start caméra via `data-auto-start="false"` ;
- aucun changement du shell global WS1.

## 3. Contrats ZS5 consommés

### Jour J

Owner/projection :

```text
build_space_operator_day_of(...)
GET /api/v1/operations/occurrences/<id>/day-of/
```

La projection décide :

- le scope Space ;
- la perspective `space|operator` ;
- la phase admissible ;
- readiness ;
- capacity ;
- queues ;
- placement ;
- checkpoints ;
- capability Scanner.

WS5 ne recalcule pas un Jour J depuis des faits dispersés.

### Live

Owner/projection :

```text
resolve_occurrence_live(...)
GET /api/v1/operations/occurrences/<id>/live/
```

WS5 affiche la phase, le timing, le contexte spatial et les agrégats déjà produits par Operations.

Aucun `Date.now()`, timer ou heuristique frontend ne transforme une heure planifiée en Live. Le runtime ZS5 opérateur ne fournit pas aujourd’hui un enum universel `planned|estimated|observed|live|unknown|unavailable` pour chaque sous-champ ; WS5 ne l’invente donc pas et conserve les états/truth réellement exposés par les owners.

### Scanner

Projection :

```text
build_scanner_context(...)
GET /api/v1/scanner/occurrences/<id>/context/
```

Autorité :

```text
user_can_scan_activity(...)
```

Mutation owner réutilisée côté WS5 :

```text
AccessCredential
→ resolve_access_credential(...)
→ validate_access(...)
→ AccessUse
```

La mutation revalide l’autorité au POST et impose `expected_activity` + `expected_occurrence`.

`ScannerAssignment` reste un contexte de responsabilité et n’accorde aucune Permission.

Lorsqu’un Activity n’a pas d’endpoint owner compatible, l’interface affiche `unavailable` et ne fabrique aucun succès.

### Makolo Mark

Orchestrateur :

```text
orchestrate_space_mark(...)
POST /api/v1/organizations/workspaces/<slug>/mark/
```

Le Web WS5 appelle directement le même orchestrateur serveur ; il ne fait pas un HTTP localhost vers l’API.

Le contexte accepté par la vue Web est construit côté serveur depuis :

- Space résolu par `SpaceWebMixin` ;
- responsabilité déjà revalidée ;
- Occurrence explicitement fournie comme cible ;
- données de clarification strictement nécessaires ;
- confirmation explicite lorsque l’orchestrateur la demande.

Les champs clients `permission`, `mandate`, `acting_user`, `is_admin` ou assimilés ne sont jamais injectés dans le contexte d’autorité.

## 4. Routes Web WS5

```text
/<space>/mark/
/<space>/occurrences/<occurrence-id>/day-of/
/<space>/occurrences/<occurrence-id>/live/
/<space>/occurrences/<occurrence-id>/scanner/
/<space>/occurrences/<occurrence-id>/scanner/scan/
```

Noms Django :

```text
organizations:space-mark
organizations:space-occurrence-day-of
organizations:space-occurrence-live
organizations:space-occurrence-scanner
organizations:space-occurrence-scanner-action
```

Jour J, Live et Scanner restent occurrence-scoped et deep-linkables.

## 5. Jour J Web

Question :

> Qu’est-ce qui compte maintenant pour cette Occurrence réelle et pour l’action que je peux y accomplir ?

La vue refuse :

- Occurrence étrangère au Space courant ;
- absence d’autorité Space/Activity ;
- projection ZS5 non disponible ;
- Occurrence hors phase Jour J.

La page reste focalisée :

- contexte Occurrence ;
- action actuelle owner-projected ;
- préparation opérationnelle ;
- flux utiles ;
- handoffs Live et Scanner si autorisés.

Elle n’est ni un dashboard Space ni une archive.

Une Occurrence terminée ferme naturellement la route Jour J ; aucun `JourJHistory` n’est créé.

## 6. Live Web

Live est une profondeur de l’Occurrence, pas un état global du Space.

WS5 conserve les faits retournés par Operations et ne déduit aucune observation depuis l’horloge du navigateur.

Aucun polling n’est ajouté dans WS5. La surface est server-rendered et reste compatible refresh/back/forward. Une stratégie de rafraîchissement plus riche pourra être ajoutée seulement si le contrat serveur et la charge le justifient.

## 7. Scanner Web

La surface Scanner est focalisée sur :

```text
contexte
→ scan
→ résultat
→ récupération
→ suivant
```

Elle réutilise le moteur QR déjà présent dans le dépôt :

- `qr-scanner` existant ;
- caméra navigateur existante ;
- fallback image ;
- fallback saisie manuelle ;
- anti-double lecture ;
- état pending ;
- verrou après succès ;
- action « Scanner le suivant ».

WS5 change un seul comportement transversal : le script accepte désormais `data-auto-start="false"`. La surface WS5 utilise ce flag pour demander la caméra uniquement après l’action explicite « Démarrer la caméra ». Les anciennes surfaces conservent l’auto-start par défaut.

Le POST Scanner :

- revalide l’autorité canonique ;
- refuse une autorité révoquée même après un GET réussi ;
- ne fait jamais confiance à Assignment ;
- n’enregistre pas le credential dans logs/templates/URL ;
- utilise les services Access propriétaires.

## 8. Makolo Mark Web

Le Mark reste le même Makolo Mark.

Question :

> J’ai quelque chose à donner à Makolo.

Le formulaire WS5 :

- utilise le vrai asset Mark du shell ;
- conserve le Space courant ;
- accepte seulement le texte, conformément à l’orchestrateur actuel ;
- expose l’Occurrence comme contexte optionnel ;
- rend `needs_clarification`, `needs_confirmation`, `resolved`, `completed`, `forbidden`, `unsupported`, `unknown` sans inventer de nouvel état métier ;
- ne transforme jamais une intention reconnue en autorité.

Les handoffs Web actuellement matérialisés sont uniquement ceux réellement supportés :

- Operations/Jour J ;
- Scanner occurrence context ;
- Organizations/Team.

Les autres handoffs restent honnêtement `unsupported` lorsque ZS5 les déclare tels.

## 9. Behavior, erreurs et récupération

WS5 suit le cycle :

```text
Comprendre
→ Agir
→ Feedback
→ Récupérer
→ Terminer
```

Principes appliqués :

- messages owner-backed ;
- états indisponibles explicites ;
- aucun faux succès ;
- résultats Scanner annoncés via `aria-live` ;
- Mark garde la saisie visible après réponse et permet la clarification/confirmation ;
- direct URL et historique navigateur conservés ;
- aucune persistance d’état UX `scanner open`, `live selected`, `came_from_day_of`.

## 10. Responsive et accessibilité

WS5 réutilise le régime et le shell WS1 :

- Compact < 768 px ;
- Adaptive 768–1199 px ;
- Expanded >= 1200 px.

Aucun second système responsive.

Les surfaces utilisent :

- structure linéaire en compact ;
- grilles seulement lorsque l’espace le permet ;
- contrôles clavier natifs ;
- labels explicites ;
- `role=status` / `aria-live` pour les résultats ;
- messages textuels en plus de la couleur ;
- aucun mouvement indispensable.

## 11. Performance et confidentialité

WS5 n’ajoute :

- aucun cache ;
- aucun polling ;
- aucun preload de toutes les Occurrences ;
- aucune nouvelle bibliothèque caméra ;
- aucune requête par item supplémentaire dans le frontend ;
- aucune persistance de QR/credential ;
- aucun analytics de credential.

Les projections restent occurrence-scoped et bornées par les owners existants.

## 12. Tests

Tests WS5 :

```text
organizations.test_ws5_space_day_of_live_scanner_mark_web
```

Couverture :

- auth/outsider/privacy-safe ;
- Activity-scoped authority ;
- Assignment seule ;
- Platform-only ;
- Occurrence étrangère ;
- Occurrence non actuelle ;
- Jour J fermé après fin ;
- Live issu du serveur et non de l’horloge Web ;
- Scanner sans endpoint owner → unavailable ;
- TOCTOU Scanner après révocation ;
- Mark handoff Jour J ;
- injection client de pseudo-autorité ignorée ;
- responsabilité != authority ;
- Mark unsupported honnête ;
- clarification + confirmation owner-backed.

Suites à rejouer avant merge :

```text
operations.test_zs5_space_action_api
operations.test_o4_occurrence_live_api
organizations.test_ws1_space_web_foundation
organizations.test_ws5_space_day_of_live_scanner_mark_web
python manage.py check
python manage.py makemigrations --check --dry-run
npm run check:runtime-deps
npm run build
Playwright ciblé / CI obligatoire
```

## 13. Migrations

WS5 ajoute :

```text
aucun modèle
aucune migration
```

Tout état d’interface est éphémère ou porté par l’URL.

## 14. Fichiers partagés touchés

Partagés :

- `organizations/urls.py` — imports + cinq routes WS5, sans refactor ;
- `frontend/src/scanner.js` — flag rétrocompatible d’auto-start caméra ;
- `static/dist/scanner.js` — build correspondant.

Propriétaires WS5 :

- `organizations/space_ws5_web.py` ;
- `templates/organizations/space/day_of.html` ;
- `templates/organizations/space/live.html` ;
- `templates/organizations/space/scanner.html` ;
- `templates/organizations/space/mark_ws5.html` ;
- `organizations/test_ws5_space_day_of_live_scanner_mark_web.py` ;
- ce document.

## 15. Non-objectifs

WS5 ne possède pas :

- Maintenant / Découvrir ;
- Métier / archétypes ;
- Nous / Relations / Pilotage ;
- navigation primaire finale ;
- redesign du shell ;
- Flutter ;
- Platform ;
- Molongo ;
- nouveau moteur Live ;
- nouveau système Access ;
- nouvelle API Scanner générique ;
- historique Jour J ;
- feed média ;
- offline Web complet.

## 16. WS6 HANDOFF

### Base / branche / PR

```text
base initiale = f3a7cf94514c94d65198b286bcf33e1cbe470697
branche       = ws5-space-day-of-live-scanner-mark-web
PR            = #430
```

### Routes

```text
Mark    → organizations:space-mark
Jour J  → organizations:space-occurrence-day-of
Live    → organizations:space-occurrence-live
Scanner → organizations:space-occurrence-scanner
Scan    → organizations:space-occurrence-scanner-action
```

### Views

```text
SpaceMarkWS5View
SpaceOccurrenceDayOfView
SpaceOccurrenceLiveView
SpaceOccurrenceScannerView
SpaceOccurrenceScannerActionView
```

### Templates

```text
organizations/space/mark_ws5.html
organizations/space/day_of.html
organizations/space/live.html
organizations/space/scanner.html
```

### JS / CSS

```text
frontend/src/scanner.js
static/dist/scanner.js
CSS WS5 dédié : aucun
```

### Projections ZS5

```text
build_space_operator_day_of
resolve_occurrence_live
build_scanner_context
orchestrate_space_mark
```

### Owner endpoints / services

```text
GET  /api/v1/operations/occurrences/<id>/day-of/
GET  /api/v1/operations/occurrences/<id>/live/
GET  /api/v1/scanner/occurrences/<id>/context/
POST /api/v1/organizations/workspaces/<slug>/mark/

Access scan mutation WS5
→ resolve_access_credential
→ validate_access
```

### Handoffs

```text
Jour J → Live
Jour J → Scanner si capability
Jour J → retour Métier / Maintenant
Mark → Jour J
Mark → Scanner
Mark → Team owner
```

### Collisions potentielles

- `organizations/urls.py` peut recevoir en parallèle les routes/imports WS2/WS3/WS4 ; réconcilier par composition.
- `organizations/space_web_views.py` est volontairement laissé aux chantiers parallèles.
- `templates/organizations/space/base.html` n’est pas modifié.
- le flag scanner JS est rétrocompatible ; conserver `autoStart !== false` lors d’une réconciliation.
- WS6 doit conserver les routes WS5 comme profondeurs contextuelles et ne pas les ajouter à la navigation primaire.

### Décisions comportementales

- caméra WS5 opt-in ;
- aucun polling Live ;
- Jour J 404 privacy-safe lorsqu’il n’est pas légitime/courant ;
- Scanner unavailable plutôt que faux endpoint ;
- mutation Scanner revalidée au POST ;
- Mark Web appelle l’orchestrateur directement côté serveur ;
- aucun champ d’autorité construit depuis le client.

### Gaps laissés volontairement

- aucun endpoint owner de scan générique non-Event n’est inventé ;
- aucun polling/stream Live n’est ajouté ;
- aucun handoff Mark non supporté par ZS5 n’est simulé ;
- les entrées finales depuis WS2/WS3 restent à composer dans WS6 ;
- le shell final et l’immersion globale restent responsabilité WS6.

WS6 doit réconcilier ces profondeurs avec le `main` courant sans déplacer leurs vérités vers Presentation.
