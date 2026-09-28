# Makolo Mobile — Files, Media & Transfer Kernel

> **Statut : Bloc C fermé — contrat canonique de conception**
>
> **Objet :** fixer comment l’application mobile acquiert, conserve temporairement, affiche, transfère, télécharge, exporte et purge les fichiers et médias sans devenir propriétaire de leur signification métier.
>
> **Base runtime vérifiée lors de cette consolidation :** `main@bf4ee1af02503ff7ff935939ad2ec508bf69f8cd` — “A2 — reconciled mobile integration checkpoint (#333)”.
>
> Le runtime courant gagne toujours sur ce document. Avant implémentation, revalider `main`, les APIs owners, le schéma Drift, les migrations, les permissions OS, les limites de taille et les PR concurrentes.

---

## 1. Principe directeur

Le Bloc C répond à une seule question :

> **Comment Makolo Mobile manipule-t-il des octets réels — document, photo, vidéo, PDF, pièce jointe, capture caméra, téléchargement, média de présentation — sans décider à la place des domaines de ce que ces octets signifient ?**

Invariant :

> **Capturer ou importer des octets ne détermine jamais leur propriétaire métier.**

Un PDF n’est pas automatiquement une Resource.

Une photo n’est pas automatiquement un média d’Activity.

Une image de certificat n’est pas automatiquement une Credential.

Un fichier donné au Makolo Mark n’est pas automatiquement conservé.

Une vidéo jointe à une Conversation n’est pas un média Discovery.

Le sens, le contexte et la finalité choisissent l’owner.

---

## 2. Architecture générale

Pipeline d’acquisition et d’upload :

```text
OS / Camera / Gallery / File picker
                ↓
           Acquisition
                ↓
      PRIVATE DEVICE STAGING
                ↓
           FileRecord
                ↓
      owner / intent binding
                ↓
      Transfer Coordinator
                ↓
      owner-specific API
                ↓
             SERVER
      validate + decide + store
                ↓
     canonical owner result
          ↙             ↘
 staging purgé      copie locale conservée
                    si elle a encore un sens
```

Pipeline de lecture distante :

```text
owner API / download
        ↓
temporary .part
        ↓
transport validation
        ↓
atomic rename
        ↓
private durable OR reconstructible cache
        ↓
viewer / export explicite
```

Le pipeline binaire est commun.

Les owners métier conservent des adapters spécifiques.

Ne pas créer :

- MarkUploader ;
- JourneyUploader ;
- ConversationUploader ;
- ResourceUploader ;
- ActivityUploader ;

chacun avec sa propre gestion des fichiers, retries et purge.

---

# 3. C-A — cycle de vie exact d’un fichier local

## 3.1 Deux axes distincts

L’état technique du stockage et l’état d’une opération distante ne doivent pas être fusionnés.

### Axe stockage

```text
ACQUIRED
   ↓
STAGED
   ↓
PRIVATE
   ↓
CACHE
   ↓
REMOVED
```

Ces noms sont conceptuels ; le schéma physique peut être plus simple.

### Axe opération

L’état d’upload n’appartient pas au fichier comme vérité finale.

Il appartient normalement à Bloc B / Outbox :

```text
NONE
QUEUED
IN_FLIGHT
AWAITING_CONFIRMATION
CONFIRMED
CONFLICT
FAILED
CANCELLED
```

Ainsi :

> **FileRecord décrit où sont les octets. OutboxOperation décrit l’intention et son exécution distante.**

Ne pas créer une seconde state machine upload indépendante dans FileRecord.

---

## 3.2 Acquisition

Sources possibles :

- file picker ;
- gallery ;
- camera ;
- download ;
- generated representation ;
- import système.

Dès acquisition :

```text
OS/plugin result
    ↓
copy into Profile-scoped Makolo sandbox
    ↓
FileRecord
    ↓
draft / intent / owner adapter
```

Ne pas construire l’architecture autour du chemin externe retourné par le plugin.

Un content URI, un cache plugin ou un fichier temporaire OS peut devenir inaccessible après restart.

---

## 3.3 Staging privé

Le staging est :

- Profile-scoped ;
- privé ;
- non public ;
- suffisamment durable pour survivre à un restart ;
- non considéré comme vérité métier ;
- conservé tant qu’une intention, un draft ou une opération l’utilise.

Exemple :

```text
photo prise
→ app tuée
→ relaunch
→ FileRecord + Draft/Outbox toujours présents
→ reprise possible
```

La personne ne doit pas refaire une capture simplement parce que l’OS a interrompu l’application.

---

## 3.4 Private durable

Une copie privée durable existe seulement lorsqu’une raison réelle le justifie :

- disponibilité hors ligne explicitement voulue ;
- ressource que l’application doit conserver ;
- fichier indispensable à une continuité locale.

Contrairement au cache :

> **elle ne peut pas être supprimée silencieusement pour récupérer de l’espace si une intention ou un usage local en dépend.**

---

## 3.5 Cache reconstructible

Exemples :

- thumbnails ;
- image Discovery ;
- preview ;
- PDF retéléchargeable ;
- média distant ;
- tuiles cartographiques.

Règle :

> **la suppression du cache ne détruit ni vérité, ni intention, ni travail utilisateur.**

Le cache peut être purgé.

---

## 3.6 Sensitive / ephemeral

Certains secrets ne doivent pas devenir des FileRecord ordinaires :

- AccessCredential ;
- QR secret ;
- token ;
- représentation sensible de droit ;
- secret de partage.

Selon le contrat owner :

- memory only ;
- protected ephemeral storage ;
- secure storage spécialisé.

Jamais de persistance générale par facilité.

---

## 3.7 Export

Exporter signifie créer explicitement une copie hors du sandbox Makolo.

```text
Makolo sandbox
   ↓ user intent
Files / Gallery / share sheet
```

Après export, Makolo ne contrôle plus nécessairement cette copie.

Mais :

> export ≠ publication  
> export ≠ changement d’owner  
> export ≠ synchronisation

---

## 3.8 Purge

### Peut être supprimé immédiatement

- cache reconstructible ;
- preview ;
- thumbnail ;
- `.part` abandonné.

### Suppression conditionnelle

Un fichier staging/private ne peut être purgé que si :

- aucune OutboxOperation ne le référence ;
- aucun draft ne le référence ;
- aucune copie offline explicite n’en dépend ;
- aucune autre intention active ne l’utilise.

Préférer dériver les références depuis les stores existants plutôt qu’introduire un refcount fragile si ce n’est pas nécessaire.

### Retrait du compte de l’appareil

Doit conduire à la purge du scope local concerné :

- tokens/secrets ;
- DB locale ;
- staging ;
- private files ;
- cache ;
- fichiers temporaires.

Les conséquences serveur ne sont pas supprimées par simple purge device.

---

## 3.9 FileRecord

FileRecord reste technique.

Conceptuellement :

```text
FileRecord
├── file_id
├── profile_id
├── local_path
├── storage_class
├── source_kind
├── owner?
├── purpose?
├── original_name?
├── mime_type?
├── byte_length?
├── content_hash?
├── sensitivity
├── reconstructible
├── created_at
└── last_accessed_at?
```

Ne pas y mettre :

- Requirement status ;
- Credential status ;
- Proof trust ;
- Access validity ;
- Readiness ;
- business lifecycle.

Le hash peut servir à l’intégrité ou à une optimisation technique.

> **same hash ≠ same business object**

---

# 4. C-B — contrats owner par owner

## 4.1 Makolo Mark / InboundCapture

Le serveur possède déjà un concept `InboundCapture` pour des entrées provisoires, notamment FILE/TEXT/URL, avec lifecycle de staging serveur.

C’est cohérent avec le contrat du Mark :

```text
receive provisionally
→ understand
→ absorb into canonical owner OR discard/expire
```

Décision :

> **Ne pas créer MarkFile, MobileCapture ou un stockage universel spécifique au mobile. Réutiliser InboundCapture comme staging owner côté serveur.**

Pipeline cible :

```text
local staging
→ InboundCapture API
→ capture reference
→ Makolo Mark orchestration
→ canonical owner
→ provisional server payload removed when appropriate
```

Le Mark API actuel doit évoluer pour accepter une référence de capture correctement autorisée, pas nécessairement un multipart monolithique à chaque clarification.

---

## 4.2 PersonalAsset

Le serveur sait déjà :

- représenter des ressources personnelles ;
- versionner ;
- télécharger ;
- réutiliser dans Journey ;
- conserver provenance et métadonnées.

Le gap mobile est une vraie API owner de création / nouvelle version.

Contrat fonctionnel attendu :

### création

- file ;
- title ;
- asset kind ;
- sensitivity ;
- issued_at si pertinent ;
- expires_at si pertinent ;
- subject lorsque le domaine l’autorise.

### nouvelle version

- file ;
- métadonnées temporelles pertinentes.

Le serveur décide du lifecycle.

Le mobile ne fabrique ni trust, ni Proof, ni satisfaction Requirement.

---

## 4.3 JourneyArtifact

Les services et surfaces Web existent déjà pour créer/versionner des artifacts.

Flutter ne doit jamais poster un formulaire HTML.

Gap :

> **API owner JourneyArtifact mobile consommable qui réutilise les services métier actuels.**

Pipeline :

```text
capture/import
→ local staging
→ owner upload
→ server artifact/version
→ refresh Journey / Requirement projections
```

Posséder ou uploader un artifact ne satisfait jamais automatiquement un Requirement.

---

## 4.4 ConversationAttachment

Le domaine Conversation prévoit des familles :

- file ;
- image ;
- audio ;
- voice ;
- video.

Mais les validations upload actuellement observées ne sont pas encore alignées avec toute cette largeur fonctionnelle.

Avant exposition mobile audio/voice/video :

1. aligner les MIME réellement autorisés ;
2. fixer tailles/durées ;
3. fixer permissions OS ;
4. exposer une API attachment owner ;
5. tester reprise, confidentialité et purge.

Le mobile ne contourne jamais une validation serveur simplement parce que le plugin sait produire un fichier.

---

## 4.5 Avatar

L’API Account/Profile supporte déjà l’upload d’image.

Pipeline :

```text
camera/gallery
→ staging
→ preview/crop éventuel
→ Profile API
→ server validates
→ refresh profile/account
→ staging purge
```

Une transformation est légitime ici parce que la destination est explicitement une représentation visuelle.

---

## 4.6 Activity/Event media

Certaines verticales possèdent déjà des médias spécifiques, par exemple une cover Event.

Ne pas généraliser cela en `UniversalMedia`.

Toute capacité média durable doit répondre :

- attachée à quoi ?
- pour quelle finalité ?
- qui peut la voir ?
- quelles transformations sont autorisées ?
- qui en est owner ?

> **No Orphan Media.**

Presentation représente les faits ; elle ne devient pas propriétaire du domaine représenté.

---

## 4.7 Trust / Proof / Credential

Un document importé peut soutenir une analyse ou un workflow de confiance.

Mais :

> fichier ≠ Proof  
> fichier ≠ Credential  
> fichier ≠ AccessCredential  
> fichier ≠ vérification

Les owners Trust/Proof/Credential déterminent la conséquence.

---

# 5. C-C — download, preview, cache et export

## 5.1 Download atomique

Pipeline obligatoire :

```text
download
→ destination.part
→ complete + transport checks
→ atomic rename
→ usable local file
```

Un fichier partiel ne doit jamais être présenté comme valide.

---

## 5.2 Preview ≠ original

Un original peut produire :

- thumbnail ;
- raster preview ;
- first-page preview ;
- transcoded preview ;
- poster frame.

Toutes ces variantes sont reconstructibles.

> **preview ≠ source**

Une purge preview ne détruit jamais l’original owner.

---

## 5.3 PDF

Le mobile peut :

- télécharger ;
- afficher dans sandbox privé ;
- conserver offline si autorisé ;
- exporter si owner autorise.

Un PDF présent localement ne signifie jamais que le Requirement correspondant est satisfait.

Un viewer embarqué spécialisé, tel que `pdfrx`, peut être retenu après revalidation au moment de l’implémentation.

---

## 5.4 Images

Séparer conceptuellement :

```text
original
preview
thumbnail
```

Ne pas écraser l’original parce qu’une vue n’a besoin que d’une miniature.

---

## 5.5 Vidéo

Même règle :

```text
original
poster/preview
local cache
```

`video_player` peut couvrir la lecture standard si les besoins restent simples.

Le lecteur ne devient pas un système média métier.

---

## 5.6 Share

La présence d’un fichier local ne suffit pas à afficher Share.

Avant `share_plus` :

> **l’owner doit autoriser l’export ou le partage de cette représentation.**

Platform capability ≠ business permission.

---

## 5.7 External handoff

`url_launcher` ou une capacité OS peut ouvrir navigateur, mail, téléphone ou application externe.

Ce handoff reste technique.

Il ne remplace pas une intégration métier et ne transfère aucune autorité.

---

# 6. C-D — gros médias, vidéo, background et reprise

## 6.1 Petits et moyens fichiers

Pour documents, images et fichiers de taille raisonnable :

> multipart classique reste le choix par défaut tant qu’il répond réellement au besoin.

Ne pas complexifier par principe.

---

## 6.2 Gros médias

Vidéo et gros fichiers changent le problème :

- durée de transfert ;
- réseau instable ;
- batterie ;
- stockage temporaire ;
- reprise ;
- OS background ;
- coût serveur.

Donc :

> **ne pas considérer un multipart géant comme architecture universelle définitive.**

---

## 6.3 Upload résumable

Décision :

> **Bloc C ne crée pas de protocole chunk maison.**

Lorsqu’un vrai scénario gros média l’exigera, le choix dépendra de l’infrastructure réelle :

- resumable session ;
- presigned object upload ;
- storage provider ;
- autre protocole spécialisé.

Ne jamais inventer aujourd’hui une cible de stockage ou un provider de production.

---

## 6.4 Background

Le background réutilise Bloc B :

```text
OutboxOperation
    +
FileRecord
    ↓
FileTransferCoordinator / owner handler
    ↑
foreground
resume
reconnect
OS background scheduler
```

Workmanager ou l’équivalent OS n’a pas sa propre implémentation métier du transfert.

---

## 6.5 Progression

La progression est une observation d’exécution :

```text
transferred / total
```

Elle peut produire une UX :

> Envoi 43 %

Mais :

> **100 % transport ≠ owner confirmed**

Chaîne réelle :

```text
uploading
→ transport complete
→ owner accepted/validated
→ canonical consequence
```

La dernière vérité appartient au serveur.

---

## 6.6 Offline par owner

Un fichier peut être :

### offline autorisé

→ private durable.

### reconstructible

→ cache.

### non autorisé à persister

→ protected ephemeral ou memory only.

La sensibilité et l’owner décident.

---

# 7. Acquisition : outils retenus

## file_picker

Pour fichiers/documents venant du système de fichiers.

## image_picker

Pour :

- sélection image/vidéo ;
- capture système simple ;
- cas où Makolo n’a pas besoin de contrôler l’expérience caméra.

## camera

Pour les expériences où la caméra fait partie du produit :

- Mark intégré ;
- scan guidé ;
- capture document ;
- scanner ;
- overlay ;
- preview contrôlée ;
- capture vidéo intégrée.

Formule :

> **image_picker pour “j’ai besoin d’un média”.**
>
> **camera pour “la caméra fait partie de l’expérience”.**

---

# 8. Conservation de l’original

Pour :

- documents ;
- preuves ;
- JourneyArtifacts ;
- Trust material ;
- PersonalAssets ;

préserver par défaut les octets originaux reçus.

Ne pas appliquer automatiquement :

- recompression JPEG ;
- conversion PDF ;
- OCR destructif ;
- suppression de métadonnées ;
- re-encoding vidéo ;

avant décision owner.

Les previews peuvent être générées séparément.

Pour Avatar/cover/media de présentation, crop/resize/recompression peuvent être légitimes parce que l’owner demande explicitement une représentation transformée.

---

# 9. Validation

Validation client :

- taille prévisible ;
- extension ;
- MIME apparent ;
- dimensions/durée lorsque disponibles.

But : UX et prévention des erreurs évidentes.

Validation serveur :

- MIME réel ;
- signature ;
- taille ;
- hash ;
- règles owner ;
- permission ;
- lifecycle.

> **client validation = préflight**
>
> **server validation = authority**

---

# 10. No Orphan Media comme règle de rétention

Chaque fichier durable doit pouvoir répondre :

> **Pourquoi existe-t-il encore ?**

Au moins une raison doit exister :

- owner canonique ;
- OutboxOperation ;
- draft ;
- copie offline explicite ;
- source reconstructible de cache.

Sinon il devient candidat à purge.

Cela traduit techniquement :

> **No Orphan Content / No Orphan Media.**

---

# 11. Matrice serveur / mobile / gaps

| Capacité | Serveur actuel | Mobile actuel/fondation | Décision |
| --- | --- | --- | --- |
| File picker | n/a | présent en A2 | staging Profile-scoped |
| Gallery/image/video picker | n/a | présent en A2 | utiliser pour cas système simples |
| Camera intégrée | n/a | présent en A2 | utiliser pour expériences guidées |
| File staging | n/a | `ProfileFileStore` présent en A2 | consolider avec FileRecord/Outbox |
| File transfer coordinator | n/a | présent en A2 | brancher aux owner handlers Bloc B |
| Media cache | n/a | présent en A2 | reconstructible uniquement |
| Private media viewers | n/a | présents en A2 | conserver privé |
| Avatar upload | API existante | pipeline possible | intégrer |
| PersonalAsset lecture | oui | à consommer | intégrer |
| PersonalAsset download | oui | pipeline C-C | intégrer |
| PersonalAsset reuse | oui | owner action | intégrer |
| PersonalAsset create/version | services existent, API mobile non démontrée | staging prêt | **API owner à ajouter** |
| JourneyArtifact create/version | services/Web existent | staging prêt | **API owner à ajouter** |
| Mark texte | oui | à intégrer | conserver |
| InboundCapture serveur | concept/services existants | staging local | **API owner à exposer** |
| Mark file | pas de contrat mobile complet | architecture prête | InboundCapture reference → Mark |
| Conversation text | API oui | à consommer | intégrer |
| Conversation attachments | domaine présent | pipeline local possible | **API owner à exposer** |
| Conversation audio/voice/video | modèle plus large que validation observée | ne pas publier encore | **réconcilier contrat serveur** |
| Event cover | API spécialisée présente | capture/upload possible | intégrer sans généraliser |
| Activity media générique | non démontré | architecture prête | owner Presentation/Activity au besoin |
| PDF viewer | owner downloads | private viewer à finaliser | intégrer |
| Video viewer | owner-specific | base A2 | intégrer quand owner le permet |
| Share/export | dépend owner | capability OS | owner permission d’abord |
| Gros upload résumable | non démontré | non | ne pas inventer |

---

# 12. Sécurité et confidentialité

Règles :

- sandbox par Profile ;
- aucun secret dans filename ;
- pas de payload sensible dans les logs ;
- original_name traité comme donnée non fiable ;
- local_path jamais utilisé comme identité métier ;
- MIME client non autoritaire ;
- serveur revalide ;
- aucune sauvegarde Gallery automatique ;
- export explicite ;
- credentials sensibles séparés ;
- cache privé non partagé entre Profiles ;
- purge locale lors du retrait du compte de l’appareil.

---

# 13. Ce que le Bloc C interdit

Ne pas créer :

- UniversalMedia sans owner ;
- MobileDocument générique ;
- MarkFile domain ;
- deuxième Outbox dédiée aux uploads ;
- upload_state métier dans FileRecord ;
- stockage Gallery implicite ;
- transformation destructive par défaut ;
- pipeline d’upload par feature ;
- protocole chunk maison sans besoin ;
- fichier = Proof/Credential/Access ;
- média durable sans finalité.

---

# 14. Décisions gelées du Bloc C

| Sujet | Décision |
| --- | --- |
| Pipeline fichiers | commun, adapters owner-specific |
| Acquisition | copie immédiate vers sandbox Makolo |
| FileRecord | technique uniquement |
| Staging | privé et restart-safe |
| Private durable | seulement avec justification |
| Cache | reconstructible |
| Sensitive media | stockage spécialisé ou éphémère |
| Upload state | Outbox Bloc B |
| File picker | documents/fichiers |
| image_picker | média système simple |
| camera | expérience caméra intégrée |
| Original document | préservé par défaut |
| Preview | distincte et reconstructible |
| Validation | serveur autoritaire |
| Download | `.part` puis rename atomique |
| Export | explicite |
| Share | autorisé par owner avant share sheet |
| Mark file | InboundCapture, pas nouveau domaine |
| PersonalAsset mobile create | API owner à ajouter |
| JourneyArtifact mobile create | API owner à ajouter |
| Conversation media | API/validation à réconcilier |
| Gros médias | pas de protocole maison |
| Background | même Outbox/Transfer pipeline |
| Progression | transport seulement |
| No Orphan Media | règle de rétention |

---

# 15. Critères de sortie avant implémentation

Avant de coder ce Bloc C :

1. revalider les APIs owners ;
2. confirmer le schéma FileRecord réellement présent ;
3. décider les migrations Drift ;
4. fixer la relation FileRecord ↔ Draft/Outbox ;
5. définir la purge Profile-scoped ;
6. écrire tests restart avec upload pending ;
7. écrire tests cancellation avec références multiples ;
8. écrire tests download partiel et rename atomique ;
9. écrire tests cache purge sans perte de vérité ;
10. écrire tests owner validation ;
11. écrire tests remove-account purge ;
12. vérifier permissions Android/iOS ;
13. vérifier limites réelles PersonalAsset/JourneyArtifact/Conversation ;
14. exposer les APIs serveur manquantes avant de prétendre supporter les flows ;
15. vérifier que chaque média durable possède un owner ou une raison reconstructible.

---

# 16. Etat runtime lors de la fermeture

Au moment de cette consolidation :

- `main = bf4ee1af02503ff7ff935939ad2ec508bf69f8cd` ;
- A2 (#333) est fusionné ;
- `mobile/lib/data/files/` contient déjà notamment `ProfileFileStore`, `FileTransferCoordinator`, `ProfileMediaCache` et cache manager ;
- `mobile/lib/platform/files/` possède le system file picker ;
- `mobile/lib/platform/camera/` possède media picker et integrated camera ;
- `mobile/lib/platform/media/` possède les private media views ;
- ces fondations sont réutilisables mais ne remplacent pas les contrats owner de ce document.

Les PR documentaires précédentes des Blocs A/B étaient fermées non fusionnées lors de cette vérification ; leurs décisions doivent donc être réconciliées explicitement avec `main` avant toute implémentation qui en dépend.

---

# 17. Formule finale

Le Files, Media & Transfer Kernel ne décide jamais ce qu’un fichier **est** dans Makolo.

Il garantit seulement que les octets nécessaires sont :

- acquis proprement ;
- conservés aussi longtemps que nécessaire ;
- protégés selon leur sensibilité ;
- transmis au bon owner ;
- réconciliés avec le serveur ;
- affichés ou exportés légitimement ;
- puis supprimés lorsqu’ils n’ont plus de raison d’exister.

> **Le support suit le sens ; il ne crée pas son propre univers.**

C’est la traduction infrastructurelle de :

> **« No Orphan Media »**

et de la promesse générale :

> **« Makolo marche pour vous. »**
