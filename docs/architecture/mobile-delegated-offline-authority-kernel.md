# Makolo Mobile — Bloc F
## Field Operations & Delegated Offline Authority

**Statut : CONCEPTION FERMÉE — implémentation conditionnée par des contrats owner démontrés**  
**Date : 2026-09-28**  
**Dépôt : TraditionLearningCommunity/makolo**  
**Base de clôture : main @ 32a3bd5c53356853be8c6e4c995042501fe6365a**  
**Branche de consolidation : docs/mobile-bloc-e-final-closure**

---

# 1. Objet

Le Bloc F ferme la conception de la seule catégorie de local-first que les Blocs A–E ne doivent pas improviser :

> **agir sur le terrain alors que l'autorité serveur n'est momentanément pas joignable.**

Il correspond au jalon A5 du programme mobile :

- scanner offline ;
- Access offline ;
- double-use / double-spend ;
- clock skew ;
- Capacity déléguée ;
- Placement / Queue coordonnés localement ;
- délégation offline uniquement si le besoin est démontré ;
- réconciliation terrain.

F n'est pas « rendre Makolo offline ». L'application est déjà local-first depuis A.

F traite exclusivement l'exception où un appareil pourrait recevoir **une autorité bornée et explicitement déléguée** pour produire des faits opérationnels alors que le serveur n'est pas disponible.

---

# 2. Frontière fondamentale

Le principe A–E reste vrai :

    server owner
    = vérité partagée + autorité + concurrence globale

Le Bloc F ajoute seulement, lorsqu'un owner le permet :

    server owner
    → délégation bornée
    → appareil déterminé
    → opérations déterminées
    → durée / scope / budget déterminés
    → journal local durable
    → réconciliation serveur

Cette délégation ne transforme jamais le téléphone en serveur Makolo général.

Elle ne permet pas au client de recalculer librement :

- Permission ;
- Mandate ;
- Access ;
- Readiness ;
- Requirement satisfaction ;
- Payment ;
- Capacity globale ;
- Placement global ;
- Queue globale ;
- Trust ;
- disponibilité globale.

---

# 3. État runtime vérifié à la clôture

Sur `main @ 32a3bd5c53356853be8c6e4c995042501fe6365a` :

- le Scanner est connecté au serveur ;
- `POST /api/v1/scanner/scan/` utilise `client_reference` pour l'idempotence d'une même tentative connectée ;
- Scanner délègue la validation canonique à Access ;
- un scan accepté produit un `AccessUse` canonique et peut produire une observation de checkpoint distincte ;
- les affectations Scanner courantes sont résolues serveur-side ;
- Operations expose un Offline Action Pack viewer-aware ;
- le pack courant contient `fresh_until`, `expires_at`, `stale`, `expired` et `refresh_required` ;
- ce pack est explicitement **non autoritatif** ;
- le noyau local possède déjà Outbox, fichiers, snapshots et reprise après crash ;
- aucune primitive générique `OfflineGrant` autoritative n'est démontrée dans le runtime courant.

Conclusion :

> **F ne peut pas déclarer le scanner offline ou Access offline “implémentés” à partir du runtime actuel.**

Le travail de F consiste à fixer le protocole architectural requis avant qu'un owner puisse légitimement déléguer de l'autorité.

---

# 4. Trois classes à ne pas confondre

## 4.1 Lecture offline

Exemples :

- Offline Action Pack ;
- snapshot Jour J ;
- Access summary ;
- assignment déjà connu ;
- ressource déjà téléchargée.

Aucune autorité nouvelle.

## 4.2 Intention préparée offline

Exemples :

- scan capturé mais non validé ;
- formulaire préparé ;
- opération mise en Outbox.

L'appareil peut conserver l'intention, mais ne doit pas annoncer une conséquence métier définitive.

## 4.3 Autorité offline déléguée

Cas exceptionnel où le serveur a explicitement autorisé un appareil à produire un résultat opérationnel localement dans des limites connues.

Exemple potentiel :

- accepter un contrôle d'accès à une porte pendant une perte réseau, si et seulement si le protocole Access/Scanner le permet réellement.

C'est cette troisième classe que possède F.

---

# 5. Gate obligatoire avant toute délégation

Une capacité n'entre dans F que si les cinq questions suivantes ont une réponse démontrable.

1. **Pourquoi l'attente du réseau est-elle inacceptable ?**
2. **Quel owner possède la décision ?**
3. **Quelle autorité minimale doit être déléguée ?**
4. **Quel dommage peut produire une décision locale erronée ou dupliquée ?**
5. **Comment le serveur réconcilie-t-il ensuite les faits concurrents ?**

Si une réponse manque :

> **la capacité reste lecture offline ou intention pending, pas autorité offline.**

---

# 6. Contrat minimal d'une délégation

F ne fige pas un nouveau modèle Django ni un nom de table.

Toute implémentation future doit néanmoins transporter explicitement au minimum :

- identité de la délégation ;
- owner émetteur ;
- acteur autorisé ;
- appareil/installation autorisé si le risque le nécessite ;
- scope métier précis ;
- opérations permises ;
- début de validité ;
- fin de validité ;
- limites quantitatives éventuelles ;
- version/epoch de politique permettant une invalidation ;
- données de vérification strictement nécessaires ;
- stratégie de conflit ;
- stratégie de réconciliation ;
- preuve d'intégrité vérifiable localement lorsque la décision offline l'exige.

Le format exact peut être un objet signé, un paquet owner-specific ou une autre représentation.

Décision :

> **F n'impose ni JWT, ni format cryptographique, ni provider tant que l'owner et le threat model ne les justifient pas.**

---

# 7. Liaison appareil

Une délégation sensible ne doit pas devenir une autorité portable copiée librement entre téléphones.

Selon le risque de l'owner, elle peut nécessiter une liaison à :

- installation Makolo ;
- compte/Profile ;
- assignment ;
- occurrence ;
- porte/checkpoint ;
- fenêtre temporelle ;
- clé ou matériel local protégé.

Mais :

- biométrie != Permission ;
- possession du téléphone != Mandate ;
- push token != identité d'autorité ;
- device id technique != preuve de légitimité métier.

La liaison device protège une délégation déjà accordée ; elle ne la crée jamais.

---

# 8. Temps et clock skew

Une autorité bornée par le temps ne peut pas dépendre naïvement de l'horloge murale du téléphone.

F impose :

1. une référence temporelle provenant du serveur lors de l'émission/synchronisation ;
2. l'enregistrement local de l'instant de réception ;
3. l'utilisation d'un temps monotone pour mesurer l'écoulement local lorsque la plateforme le permet ;
4. une tolérance explicite définie par l'owner ;
5. un échec sûr lorsque l'appareil ne peut plus démontrer qu'il est dans la fenêtre autorisée.

Le client ne prolonge jamais lui-même une délégation expirée en modifiant l'heure locale.

---

# 9. Scanner offline

## 9.1 Ce que le runtime actuel sait déjà faire

Connecté :

    QR/token
    → Scanner
    → authority assignment
    → Access validation
    → AccessUse
    → ScanLog
    → checkpoint observation éventuelle

Cette chaîne est bonne et doit rester canonique.

## 9.2 Ce qui manque pour l'offline

Le `qr_token` actuel et l'Offline Action Pack ne constituent pas, à eux seuls, un protocole de validation offline.

Avant de permettre `accepted` hors réseau, l'owner doit fournir :

- un matériel de vérification offline borné à l'Occurrence ;
- la liste minimale des scopes/assignments autorisés ;
- les règles de validité applicables ;
- un ledger local durable des décisions ;
- une règle de duplication locale ;
- une politique explicite pour le même credential présenté à plusieurs terminaux isolés ;
- un protocole de réconciliation avec AccessUse et Scanner.

Le client ne télécharge pas arbitrairement toute la base de credentials.

## 9.3 Résultat local

Un scan offline ne doit jamais produire le même vocabulaire que le serveur si la garantie n'est pas équivalente.

Le protocole doit distinguer, selon le niveau réel :

- accepté sous délégation valide ;
- refus déterministe ;
- inconnu / vérification réseau requise ;
- déjà vu sur ce terminal ;
- conflit potentiel inter-terminal.

Aucun « succès » définitif ne doit masquer une incertitude que le protocole ne sait pas résoudre.

---

# 10. Double-use / double-spend

Deux terminaux complètement isolés ne peuvent pas empêcher magiquement l'utilisation simultanée d'un même droit partagé sans protocole supplémentaire.

F interdit donc de promettre une unicité globale offline par simple cache.

Les stratégies admissibles doivent être choisies explicitement par l'owner, par exemple :

- partition d'autorité ;
- terminal unique autorisé pour un scope ;
- budgets/ranges préalloués ;
- coordination locale démontrée ;
- acceptation contrôlée d'un risque provisoire avec réconciliation.

Le choix dépend de la conséquence métier.

> **Aucune stratégie universelle de “last write wins” n'est acceptable pour AccessUse.**

---

# 11. Ledger opérationnel local

Une décision autoritative offline doit être écrite durablement avant d'être présentée comme acquise.

Chaque fait local doit posséder au minimum :

- identifiant stable ;
- délégation utilisée ;
- acteur ;
- appareil ;
- owner/scope ;
- type d'opération ;
- ressource ciblée ;
- référence d'intention ;
- temps local observé + ancre serveur disponible ;
- résultat local ;
- données minimales nécessaires à la réconciliation ;
- état de sync.

Le ledger est append-oriented.

Une correction ne réécrit pas silencieusement l'histoire ; elle produit une conséquence de réconciliation.

---

# 12. Reconnexion et réconciliation

Au retour réseau :

    ledger local
    → owner API de réconciliation
    → revalidation serveur
    → détection duplicates/conflits
    → faits canoniques
    → conséquences owner
    → refresh projections
    → conservation audit local bornée

Le serveur peut décider qu'une opération locale est :

- confirmée ;
- déjà connue ;
- rejetée ;
- conflictuelle ;
- partiellement appliquée selon contrat owner.

Le téléphone ne force jamais sa version en vérité globale.

---

# 13. Access offline

Access reste le droit.

AccessCredential reste sa représentation/secret.

AccessUse reste l'observation de l'usage.

Une délégation F ne doit pas fusionner ces trois concepts.

Pour qu'un Access puisse être contrôlé offline, le protocole doit démontrer :

- quels Access sont dans le scope ;
- quelle représentation est vérifiable localement ;
- quelles invalidations/révocations peuvent survenir pendant la coupure ;
- quel risque résiduel est accepté ;
- comment AccessUse sera créé/réconcilié.

Sans cela :

> **Access offline = non autorisé.**

---

# 14. Capacity déléguée

Capacity répond « combien ? ».

F n'autorise jamais le téléphone à inventer une capacité globale depuis une ancienne valeur `available`.

Si un owner a besoin d'allocation offline, il doit déléguer un **budget borné** ou une partition explicitement réservée au terrain.

Le protocole doit traiter :

- allocation initiale serveur ;
- consommation locale ;
- expiration ;
- restitution ;
- dépassement interdit ;
- deux appareils ;
- réconciliation ;
- annulation.

Sans budget owner-issued, Capacity reste réseau-required pour toute allocation.

---

# 15. Placement et Queue

Placement répond « où ? ».

Live Queue répond à l'ordre opérationnel courant.

Ces réalités sont partagées et concurrentes.

Un mode offline ne peut exister que si le serveur a défini qui coordonne le scope déconnecté.

Possibilités conceptuelles :

- coordinateur unique désigné ;
- partition de files/portes ;
- sous-scope local indépendant ;
- autre protocole owner démontré.

F ne choisit pas un algorithme de consensus générique et ne crée pas un réseau pair-à-pair Makolo par principe.

---

# 16. Checkpoints

JourneyStep != Checkpoint opérationnel.

Un checkpoint offline ne peut être observé autoritativement que si :

- l'acteur est légitimement assigné ;
- le checkpoint appartient au scope délégué ;
- sa fenêtre est encore démontrablement valide ;
- l'observation possède un identifiant stable ;
- la réconciliation peut relier le fait à AccessUse ou aux autres faits owners pertinents.

Sinon, l'appareil peut seulement préparer une observation pending.

---

# 17. Révocation pendant la coupure

Une délégation ne peut pas recevoir instantanément une révocation lorsqu'elle est réellement hors réseau.

Le système doit donc réduire cette fenêtre par :

- durées bornées ;
- scope minimal ;
- refresh avant prise de service ;
- invalidation au retour réseau ;
- rotation de politique lorsque nécessaire.

F interdit de présenter une délégation longue et large comme équivalente à une autorisation serveur temps réel.

---

# 18. Sécurité et confidentialité

Le paquet offline contient le strict minimum.

Il ne doit pas exposer par défaut :

- liste exhaustive de participants ;
- documents privés ;
- QR secrets réutilisables sans nécessité ;
- credentials d'autres contexts ;
- Permission/Mandate bruts sans besoin ;
- données financières ;
- payloads de Trust ;
- secrets serveur.

Les logs/crash reports ne contiennent jamais :

- token complet ;
- credential ;
- QR payload ;
- clé privée ;
- secret de délégation ;
- PII inutile.

---

# 19. Stockage local

F réutilise les primitives existantes avant toute table nouvelle :

- OutboxOperations ;
- ProjectionSnapshots ;
- ResourceIndex ;
- FileRecords si matériel fichier ;
- stockage protégé pour petits secrets ;
- nouveau ledger spécialisé uniquement si les requêtes/règles opérationnelles le justifient réellement.

Aucun modèle Drift générique `OfflineEverything`.

Toute migration locale doit être :

- versionnée ;
- testée upgrade/downgrade logique ;
- compatible avec un ledger pending ;
- résistante au crash.

---

# 20. Offline Action Pack

Le pack O5 reste une projection de lecture.

Les durées actuelles du runtime sont des paramètres serveur et ne deviennent pas une constante mobile.

Décision :

> **Offline Action Pack ≠ délégation F.**

Un futur owner peut référencer certaines données du pack dans une expérience F, mais l'autorité doit venir d'un contrat distinct et explicite.

---

# 21. UX terrain

L'interface doit rendre visible le niveau réel de garantie.

États minimaux :

- connecté et autorité serveur disponible ;
- offline lecture seulement ;
- offline délégation active ;
- délégation proche expiration ;
- délégation expirée ;
- opération pending ;
- conflit de réconciliation ;
- autorité retirée.

La couleur seule ne suffit pas.

L'utilisateur doit savoir si une action :

- est définitivement confirmée ;
- a été acceptée sous délégation ;
- attend encore le serveur.

---

# 22. Background

Workmanager/background execution aide à :

- reconnecter ;
- flush le ledger ;
- renouveler un paquet avant une prise de service si l'OS le permet ;
- effectuer une maintenance bornée.

Mais l'OS peut retarder ou supprimer une tâche.

Le protocole F ne dépend donc jamais d'un background job pour préserver son intégrité.

---

# 23. Gaps serveur réels à la clôture

Sur le runtime audité, ne sont pas démontrés :

1. protocole de délégation offline owner-issued ;
2. matériel de vérification Scanner/Access offline ;
3. réconciliation batch des décisions terrain ;
4. budget Capacity délégué ;
5. coordinateur offline Placement/Queue ;
6. liaison autoritative d'une délégation à une installation mobile ;
7. protocole de révocation/epoch pour ces délégations.

Ces gaps ne justifient pas immédiatement sept nouveaux modèles.

Ils doivent être implémentés uniquement lorsqu'un scénario terrain réel le nécessite.

---

# 24. Ordre d'implémentation recommandé

## F0 — preuve du besoin

Reproduire un scénario réel où la perte réseau bloque une opération légitime.

## F1 — scanner offline borné

Premier candidat naturel parce que :

- le Scanner connecté existe ;
- AccessUse existe ;
- l'idempotence de tentative existe ;
- les assignments/gates/checkpoints existent.

Mais aucune implémentation ne commence avant choix du protocole de vérification.

## F2 — Access reconciliation

Fermer la création/réconciliation des AccessUse terrain.

## F3 — capacité déléguée

Seulement si un vrai cas de réservation/allocation terrain l'exige.

## F4 — Placement/Queue

Seulement si le modèle de coordination locale a un owner clair.

---

# 25. Tests obligatoires

## Autorité

- aucun grant = aucune décision autoritative offline ;
- wrong actor ;
- wrong device lorsque binding requis ;
- wrong occurrence ;
- wrong gate/checkpoint ;
- expired ;
- policy epoch invalide.

## Temps

- horloge locale avancée ;
- horloge locale reculée ;
- reboot ;
- longue suspension ;
- absence d'ancre fiable.

## Scanner

- même QR deux fois même terminal ;
- même `client_reference` ;
- même QR sur deux terminaux isolés ;
- credential révoqué pendant coupure ;
- mauvais événement ;
- mauvais checkpoint.

## Résilience

- kill app après acceptation avant sync ;
- crash pendant écriture ledger ;
- crash pendant réconciliation ;
- réseau revient puis repart ;
- réconciliation partielle.

## Confidentialité

- aucun secret dans logs ;
- aucune donnée d'un autre scope ;
- purge/retention correcte après fin de service.

---

# 26. Anti-features

F interdit :

- serveur Django embarqué dans Flutter ;
- copie locale complète d'Access ;
- copie locale globale de Capacity ;
- validation QR « parce que le token ressemble à un token » ;
- Permission/Mandate déduits d'un assignment ;
- succès offline sans délégation ;
- last-write-wins universel ;
- synchronisation pair-à-pair générique inventée ;
- blockchain/consensus ajouté sans besoin démontré ;
- grant sans expiration ;
- grant global multi-domaines ;
- clé privée serveur embarquée dans l'app ;
- confiance fondée sur l'heure modifiable du téléphone.

---

# 27. Décisions figées

1. Le local-first ordinaire n'accorde aucune autorité.
2. F traite uniquement l'autorité explicitement déléguée.
3. Offline Action Pack reste non autoritatif.
4. Une délégation est owner-specific et scope-specific.
5. Assignment reste responsabilité ; l'autorité vient du contrat owner.
6. Device binding peut protéger une délégation mais ne crée pas d'autorité.
7. Access, AccessCredential et AccessUse restent distincts.
8. Capacity et Placement restent distincts.
9. Waitlist et Live Queue restent distincts.
10. Aucun succès définitif n'est affiché au-delà de la garantie réelle.
11. Clock skew est un problème de protocole, pas un détail UI.
12. Double-use global ne peut pas être « résolu » par simple cache.
13. Toute décision offline autoritative est journalisée durablement.
14. Le serveur réconcilie et garde la vérité globale.
15. Aucun modèle générique OfflineGrant n'est ajouté sans besoin démontré.

---

# 28. Critères de sortie de la conception

Le Bloc F est fermé comme contrat de conception lorsque :

- la différence lecture / pending / autorité est explicite ;
- les gates de délégation sont fixés ;
- le scope minimal d'une délégation est fixé ;
- les contraintes clock skew sont fixées ;
- le problème double-use est traité honnêtement ;
- la réconciliation est owner-first ;
- Scanner/Access ne sont pas déclarés offline avant leur protocole réel ;
- Capacity/Placement/Queue ne sont pas localement globalisés ;
- les exigences sécurité/confidentialité sont explicites ;
- aucun provider, secret, URL ou modèle absent n'est inventé.

---

# 29. Formule finale

> **Makolo Mobile peut continuer à montrer et préparer beaucoup de choses hors réseau. Il ne peut décider hors réseau que ce qu'un owner lui a explicitement délégué, pour un scope, un temps et un risque bornés.**

F transforme donc l'exception terrain en protocole contrôlé, sans transformer le téléphone en seconde source de vérité.

La fermeture de maturité, sécurité, observabilité, distribution et stores est portée par `mobile-mature-release-kernel.md` (Bloc G).
