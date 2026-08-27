# Module Scanner

## Responsabilité

`scanner` est la couche Makolo de contrôle d’accès des `Activity` / `Occurrence`.

La vérité métier contrôlée est canonique :

- `Access` représente le droit ;
- `AccessCredential` représente le QR / pass / credential présenté ;
- `AccessUse` représente le contrôle ou l’utilisation du droit.

La verticale `events` peut conserver ses surfaces et projections historiques (`Ticket`, `ScanLog`), mais elle compose le contrôle canonique au lieu de recréer une décision métier parallèle.

Le module ne fait jamais confiance au contenu du QR ni aux identifiants Activity/Occurrence transmis par le navigateur. La décision finale et le scope sont revalidés côté serveur.

## Modèles

### ScannerAssignment

Une affectation relie un agent à une portée de contrôle. Le modèle supporte la portée canonique Activity/Occurrence et conserve la compatibilité Event nécessaire aux surfaces historiques.

Une affectation n’est pas une permission en elle-même : l’autorité serveur reste résolue par les permissions / rôles / Mandates applicables. Une TeamMembership ou GroupMembership seule ne donne pas le droit de scanner.

### AccessUse

`AccessUse` est le journal canonique lorsqu’un `Access` identifiable a pu être résolu.

Il conserve notamment :

- l’Access ;
- le credential identifié lorsque pertinent ;
- l’acteur de contrôle lorsque pertinent ;
- l’Occurrence de contrôle ;
- le résultat ;
- la source ;
- l’heure métier du contrôle ;
- une `client_reference` facultative pour l’idempotence du cycle scanner.

Le QR brut, le token signé et les hashes ne sont pas stockés dans `AccessUse`.

### ScanLog

`ScanLog` reste la projection opérationnelle et la couche de compatibilité du Scanner historique Event, notamment pour les tentatives qui ne peuvent pas résoudre un `Access`.

Il conserve :

- l’événement historique contrôlé ;
- le billet lorsqu’il a pu être identifié ;
- l’agent ;
- l’affectation ;
- le résultat opérationnel ;
- l’heure ;
- la porte ;
- une référence client idempotente ;
- une empreinte SHA-256 du QR.

Lorsque la décision vient d’Access, `ScanLog.metadata` peut porter le résultat canonique et l’identifiant `AccessUse`, jamais le QR brut.

## Résultats canoniques AccessUse

```text
accepted          accès autorisé
already_used      accès single-use déjà consommé
expired           accès expiré
not_yet_valid     accès authentique mais contrôle trop tôt
revoked           accès révoqué
cancelled         accès annulé
wrong_activity    accès prévu pour une autre Activity
wrong_occurrence  accès prévu pour une autre Occurrence
invalid_credential credential invalide ou non reconnu
```

Les surfaces Event peuvent projeter ces décisions vers leurs anciens `ScanResult`, mais l’interface doit conserver le résultat canonique afin de présenter le bon vocabulaire produit.

## Autorisation

Le Scanner générique doit vérifier `ACTIVITY_ACCESS_SCAN` dans la bonne portée ou une affectation canonique valide selon les règles du domaine Scanner.

La verticale Event conserve ses contrôles de compatibilité, mais une Membership d’Espace ou de Groupe n’accorde jamais implicitement l’autorité de scanner. Les rôles, permissions et Mandates restent la source de vérité serveur.

## Anti-double-scan et concurrence

La validation canonique `validate_access()` s’exécute dans une transaction et verrouille l’`Access` avec `select_for_update()`.

Pour un `Access` single-use :

```text
Access.valid
  -> lock DB
  -> scope / credential / fenêtre de validité
  -> AccessUse.accepted
  -> Access.used
  -> Domain Event Access.used
  -> commit
```

Une véritable présentation ultérieure produit :

```text
Access.used
  -> AccessUse.already_used
```

La capacité n’est pas consommée une seconde fois et aucun nouveau droit n’est créé.

PostgreSQL fournit la sémantique de verrouillage ligne par ligne attendue sous concurrence. SQLite reste utile au développement et aux tests mais ne reproduit pas exactement ce verrouillage.

## Idempotence d’un cycle scanner

Les scanners peuvent transmettre `client_reference`.

Pour un même contrôleur authentifié, la combinaison `(actor, client_reference)` est unique lorsqu’une référence est fournie. Une répétition technique avec la même référence retourne le même `AccessUse` et le même résultat au lieu de créer une seconde utilisation.

Cette règle distingue :

- la répétition réseau / caméra du même cycle ;
- une nouvelle présentation volontaire, qui utilise une nouvelle référence et peut donc produire `already_used`.

Le Scanner Event conserve également son idempotence `ScanLog` pour sa couche opérationnelle historique.

## Interface web

Après `accepted`, la console web fige le résultat et ignore les nouvelles lectures caméra jusqu’à une action explicite **Scanner le suivant**. Le succès ne peut donc plus être remplacé visuellement par la relecture immédiate du même QR.

Les titres de décision distinguent notamment :

- `Accès autorisé` ;
- `Contrôle pas encore ouvert` ;
- `Billet déjà utilisé` ;
- `Billet expiré` ;
- `Billet révoqué` ;
- `Billet annulé` ;
- `Autre activité / occurrence` ;
- `QR invalide ou non reconnu`.

Les surfaces génériques utilisent `Activity` / `Occurrence` / `Contrôle affecté`. Une verticale peut contextualiser le vocabulaire (`Départ` pour Transport, date/séance pour Event, etc.).

Aucune validation de sécurité n’est effectuée dans JavaScript : le navigateur capture le credential et l’envoie au serveur.

### T28 — contrat terrain/mobile

La surface caméra est une amélioration progressive du même Scanner canonique :

- `QrScanner` demande en priorité la caméra `environment` ; le fallback `BarcodeDetector/getUserMedia` utilise également `facingMode: {ideal: "environment"}` ;
- le sélecteur de caméra existant reste la seule UI de changement de device ;
- l’action Lampe n’est rendue visible que lorsque la caméra expose réellement cette capacité ;
- refus de permission, absence de caméra ou API indisponible produisent un message actionnable et laissent disponibles l’image QR et la saisie manuelle ;
- le résultat est annoncé textuellement via une région `aria-live` ; couleur, son ou vibration ne sont jamais la seule information ;
- lorsque `navigator.vibrate` existe, un feedback tactile bref peut distinguer succès et refus ; son absence ou son échec ne change jamais le résultat ;
- **Scanner le suivant** reste l’action dominante après succès ;
- `pagehide` arrête la caméra et détruit le moteur QR pour ne pas laisser de track actif en arrière-plan.

Le feedback sonore reste facultatif et n’est pas requis par T28 : le visuel et le texte suffisent dans tous les cas.

## Audit participant et Operations

- le participant voit l’historique de son propre `Access` à partir d’`AccessUse` ;
- il voit date/heure, résultat compréhensible et occurrence utile, sans identité interne du contrôleur, hashes, metadata ni credential ;
- Operations réutilise les scopes Space/Activity et les Mandates existants ;
- `ScanLog` ne remplace jamais `AccessUse` pour un Access identifiable ;
- aucune nouvelle table de tentative parallèle n’est nécessaire pour ce cycle.

## Confidentialité

- le QR brut n’est jamais persisté dans les logs applicatifs ;
- le Scanner historique peut conserver uniquement un fingerprint SHA-256 ;
- les credentials signés ne sont pas exposés dans Operations ;
- aucune donnée client n’est utilisée comme preuve d’autorisation ;
- Activity et Occurrence sont toujours revalidées côté serveur.

## Compatibilité historique Event

Les routes historiques Event restent disponibles tant que les surfaces correspondantes existent :

```text
/scanner/
/scanner/event/<slug>/
/scanner/event/<slug>/scan/
/scanner/logs/
/scanner/assignments/
```

Elles doivent déléguer la décision d’un credential canonique à Access. Les futurs parcours non-Event ne doivent pas dépendre de ces routes ni de `Ticket` / `ScanLog` pour leur vérité métier.

## Extensions prévues

- mode PWA/offline contrôlé avec synchronisation et politique explicite de conflit ;
- statistiques temps réel dans `analytics_app` ;
- notifications d’incidents ;
- zones multiples / capacités par point de contrôle ;
- intégration de matériels scanners dédiés via l’API.