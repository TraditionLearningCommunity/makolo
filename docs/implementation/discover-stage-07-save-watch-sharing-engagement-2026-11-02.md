# Makolo — Découvrir : chantier 07, Save, Watch, Sharing et engagement N3

**Date :** 2 novembre 2026  
**Branche :** `fix/discover-a-continuation-context-20261014` · [PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522).  
**Périmètre :** R22–R24 ; actions explicites déjà autorisées par les domaines propriétaires, distinctions Save/Watch/Share/Engage, confirmations et refus, reprise des liens partagés et profondeur N3.  
**Décision :** **implémentation livrée en code** ; tests créés **sans exécution**, CI non lancée conformément à l'instruction de l'utilisateur. Chantier 08 non commencé.

## 1. Séparation des autorités — invariant de sortie

| Intention | Propriétaire canonique | Effet réel autorisé | Confirmation |
| --- | --- | --- | --- |
| **Save/Unsave** | ActivityBookmark ou OpportunitySave via Discovery API | Conserver/déconserver une possibilité de lecture ; aucune participation | Réponse `discovery.saved` avec `identity.family`, `identity.resource.id` et `saved.state` identiques à l'intention |
| **Watch** | DiscoveryWatch et `ensure_discovery_watch` | Mémoriser **les critères de recherche**, pas un candidat et pas une Journey | Identifiant de Watch confirmé par `discovery.watch`; création réessayée idempotente pour une Veille active équivalente |
| **Sharing externe** | Sharing ShareEnvelope / ShareLink | Émettre un lien révocable, aucun état de Save | `state=link`, URL absolue contrôlée ; lien soumis à résolution owner au moment d'être ouvert |
| **Sharing interne** | Sharing ShareDelivery | Envoyer à un Profil destinataire éligible, sans accord/participation du destinataire supposé | `state=delivered` **et** `delivery_id` non vide ; le destinataire seul résout sa livraison |
| **Engagement N3** | Events, Commerce, Services, Funding, Obtention, Journeys | Ouvrir exclusivement le parcours natif que l'owner annonce et autorise | Confirmation métier **dans** la profondeur owner ; Découvrir ne signe pas le succès |

Aucun modèle de Bookmark, Veille, Share, Delivery, Journey, Order ni Payment bis n'a été introduit ; aucune migration.

## 2. Save : confirmation d'un état et non simple clic

L'API `DiscoveryItemSavedAPIView` utilise déjà le selector propriétaire `detail_candidate` et `set_saved_state` : 404 pour une possibilité indisponible, authentification requise et identité owner-admise. L'enregistrement est naturellement idempotent (ActivityBookmark `get_or_create`, OpportunitySave owner) et la suppression est répétable.

**Renforcement Flutter** : `DiscoveryRepository.setSaved` valide maintenant le wire d'item, l'égalité `family/id` du candidat demandé et la valeur exacte `saved` ou `not_saved` en sortie. Il ne persiste pas un état d'un autre candidat et ne retourne pas succès pour une réponse incohérente. Les boutons N1/N2 gardent leur blocage pendant mutation, et ne confirment un Save qu'après ce contrôle ; un refresh du champ reste une étape distincte, non propriétaire de la mutation. **Une réponse tardive obtenue après changement de candidat ne peut pas marquer le nouvel item comme enregistré.**

## 3. Watch : service owner complet et Web/Flutter cohérents

### API / serveur

- `DiscoveryWatchListCreateAPIView.post` réutilise **`ensure_discovery_watch`**, déjà atomique et sérialisé par verrouillage de l'owner. Un retry d'une veille **active** de mêmes critères et même Dossier personnel retourne **200 + `created=false` et le même id**, au lieu de créer deux Veilles ; la première création retourne 201 + `created=true`. Une veille en pause reste indépendante d'une nouvelle création active.
- `normalize_watch_criteria` et les validations du modèle sont conservés. Les `ValidationError` du domaine deviennent des erreurs HTTP 400 explicites pour critères, Dossier/UUID, statut et nom (1–140 caractères). Les lectures, mutations, pause, reprise et suppression demeurent liées à `request.user` ; un autre Profil reçoit 404.
- **Web** : `DiscoveryWatchCreateForm.save` utilise le **même** service `ensure_discovery_watch` ; un double envoi du formulaire Web ne crée plus de doublon.
- Aucun filtre incompatible n'est supprimé en silence. Les Watches continuent à couvrir les familles réellement supportées par `execute_watch` (notamment Activities et Services), sans promettre la surveillance de toutes les familles.

### Flutter

- `DiscoveryQuery.watchCriteria` transporte exclusivement les filtres exécutables `q/place/when/period/vertical/price/dates/position/rayon/timezone`, jamais `page`, `page_size`, `continuation`, sélection N1, profil ou état de cache. Rayon entier normalisé au format attendu par le propriétaire.
- `DiscoveryRepository` expose `createWatch`, `updateWatchStatus`, `editWatch` et `deleteWatch`, avec validation des enveloppes de réponse et de l'identité, attente de confirmation et synchronisation opportuniste de la liste. Un échec de rafraîchissement après succès owner ne déclenche pas un faux échec ni un replay automatique.
- Nouveau `discovery_watch_create.dart` : dialogue avec nom (1–140 caractères) et filtres courants, annulation sans mutation, état de chargement et refus visible. Le navigateur n'ouvre `/discover/watches/:id` **qu'après réception d'un vrai identifiant serveur**.
- Les écrans N1 de racine et Recherche exposent l'action Veille distincte de Save et Share, seulement lorsque des critères existent. La liste Veilles permet créer, mettre en pause, reprendre, renommer, remplacer explicitement les critères après accord, et supprimer après confirmation.
- Les résultats de Veille utilisent désormais `onOpenItem(family,id)` pour ouvrir le **N2 Discovery canonique** plutôt que de remplacer la projection par une simple profondeur Activity. Aucune Journey n'est créée par la lecture d'un résultat.

## 4. Sharing : liens, destinataires, rejet et reprise

- `SharePossibilityAPIView` continue à demander `detail_projection` **owner-admis** avant toute émission, à filtrer les Profiles destinataires et à utiliser les services Sharing existants. Un `recipient_id` explicitement fourni mais vide/invalide est refusé avec HTTP 400 : la requête n'est **jamais** reconvertie silencieusement en lien public.
- Dans `DiscoveryShareControl`, un utilisateur authentifié passe **toujours** par le propriétaire Sharing pour créer un lien ; l'absence d'un indicateur Web ne déclenche plus un fallback de lien non confirmé. Un invité peut partager seulement l'URL publique explicitement projetée. Le token mémorisé est invalidé localement si l'identité du candidat ou l'état d'authentification change. **Les réponses réseau encore en vol sont liées à la génération de l'item et rejetées si l'utilisateur a changé de possibilité** ; un ancien token n'est jamais appliqué à la nouvelle carte.
- Le partage interne exige **`state=delivered` et `delivery_id` non vide**, sans affiche de succès sur simple réponse partielle. Le moteur `create_direct_*` du domaine évite déjà les livraisons dupliquées récentes et conserve les limites de débit.
- `DiscoverySharedLinkScreen` accepte un jeton public ou une livraison privée : pour une livraison authentifiée demandée hors session, l'utilisateur est redirigé vers Login avec le **même** `/shares/:id` en reprise. À la résolution, seul le `route` strictement cohérent avec `family/id` autorisés est ouvert ; une réponse ancienne d'un lien précédent ne peut pas écraser la nouvelle résolution.
- Les resolveurs Sharing publics et privés conservent leur refus si le sujet est retiré, le partage est révoqué/expiré, ou le destinataire n'est pas propriétaire de la livraison. Les URLs de sortie sont vérifiées au moment d'ouverture : aucune autorisation locale définitive.

## 5. Engagement N3 : ne jamais fabriquer une action

`DiscoveryPossibilityUnit._primaryNativePath` existait et est **réutilisé**, sans inventer de `start` universel. Les chemins autorisés sont vérifiés par **propriétaire + `owner_api` + capacité + ressource canonique + correspondance exacte de l'URL**, selon la verticale :
- Commerce : offres d'Activity, checkout Journey existant, reprise d'Order ;
- Services : entrée native Service autorisée, et exigence d'authentification lorsque prévue ;
- Events : choix de billets déclaré par l'owner ;
- Funding : contribution liée à la ressource Funding ;
- Obtention : choix natif d'Obtention ;
- Journeys : continuation du vrai parcours.

Le N1 peut proposer l'entrée native si elle est véritable ; N2 expose une entrée métier seulement si elle est résolue ; sinon le détail reste en lecture, sans acquiescement implicite. **Les résultats des Watches et les liens Sharing conduisent d'abord à la possibilité canonique**, pas à une transaction automatique. Le refus d'une destination native inconnue n'est pas converti en Web fallback.

## 6. Tests de non-régression ajoutés (non exécutés)

**Django**
- `discovery/api/test_stage07_watch_save.py` : authentification, création Watch et replay idempotent, indépendance Bookmark, pause/reprise/suppression par owner, refus tenant étranger, critères/statut/Dossier invalides, renommage/remplacement de critères, double soumission Web, Save/Unsave répétables sur Opportunity sans Watch créée.
- `discovery/api/test_stage07_sharing.py` : publication, génération owner d'un lien puis résolution publique, révocation, retrait du sujet, authentification, destinataire vide/invalide et absence de livraison, impossibilité de résoudre la livraison d'autrui.

**Flutter**
- `mobile/test/discovery_stage07_actions_test.dart` : critères Watch sans curseur ni viewer, chemins API distincts, contrôles de confirmation Save/Sharing/reprise, N3 exact Commerce/Funding/Events/Obtention et refus de checkout appartenant à une autre ressource ; réponse Save tardive sans contamination d'une seconde carte, et génération Share obsolète.
- Les tests préexistants de Service start, login Save invité, engagements N1 et partage externe restent conservés.

## 7. Frontières et statut

- Pas de nouveau moteur de notification, de polling, de Watch sur families non couvertes ou de `Watch` reconstruit depuis un Save.
- Pas de simulation d'un checkout, paiement, billet, participation, accès ou commande propriétaire.
- Les garanties de snapshots, révocations locales, cache et profil isolé de données archivées relèvent du **chantier 08**, pas de cette livraison.
- Aucun test/CI/Web E2E/build Android ni migration n'a été exécuté. Les tests écrits ne valent **pas** preuve de réussite.

### Critères de livraison de code

- [x] Save/Unsave owner-confirmés et indépendants de Watch/Sharing/N3.
- [x] Watch Web et Flutter idempotente, CRUD et statut privés ; reprise de critères et confirmation.
- [x] Sharing interne/externe avec source owner, contrôle de destinataire et delivery ID, refus révocation/retrait, reprise Login.
- [x] Les routes N3 restent strictement owner-verified et sans transaction fictive ; couverture des principales verticales par tests écrits.
- [x] Rapport de livraison, scénarios et fichiers enregistrés dans #522.
- [ ] Exécution réelle des tests/CI/Appareil/Web — **différée à 09**.

**Décision : chantier 07 — livraison de code terminée, certification non exécutée. Prochain chantier autorisé : 08 exclusivement.**
