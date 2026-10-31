# C2 — Interopérabilité : parcours et frontières d'autorité (Profile / Space / Platform)

**Statut : contrat de conception et fermeture des parcours actuellement consommables ; branche PR #522.**  
**Sources :** code actuel de `interoperability/`, `intelligence/interoperability.py`, `interoperability/api_views.py`, `core/interoperability_views.py`, `organizations/space_web_views.py`, `mobile/lib/features/interoperability/`, `mobile/lib/sync/sync_engine.dart`, blueprint, M7 et Z16.  
**Invariants :** backend générique, métier contextuel ; Assignment = responsabilité, Mandate/Permission = autorité ; une Connection donne un canal, jamais le droit implicite de lire/agir ; aucune vérité propriétaire déplacée.

## 1. Ce que signifie « connexion »

Trois réalités non interchangeables :

1. **Configuration technique d'un fournisseur** : p. ex. `intelligence.ProviderConnection` et ses routes/credentials. L'owner Intelligence conserve création, secrets, activation et exécution. Le client peut lire une projection Z16 autorisée, pas la configuration.
2. **Relation consentie d'un acteur avec un service externe** : lorsque l'owner concerné offre réellement établissement, vérification et révocation. Le seul kernel M7 ne prouve pas que ce parcours existe.
3. **Capacité métier utilisant une intégration** : Payments, Notifications, Geography, Spatiotemporal, Accounts, etc. Elle vit dans son parcours propriétaire, et ne devient pas automatiquement une Connection à afficher dans « Connexions ».

`available` ≠ `connected` ≠ `usable` ≠ `manageable`. Le statut sanitaire du provider n'est ni une preuve de droit ni une réussite métier.

## 2. Scénarios Profile

### P1 — Consulter ses connexions personnelles (LIVRÉ)

**Entrée :** Avatar → Connexions, Web `/me/connections/`, Flutter `/connections`.  
**Lecture :** projection serveur `GET /api/v1/me/interoperability/`, `z16.v1`, `context=profile`.  
**Autorité :** authentification + sélection `ProviderConnection.profile__user=actor`. Aucun `profile_id` client.  
**Sortie :** connexions effectivement sélectionnées, état et capacités non sensibles ; sinon état vide vrai.  
**Interdits :** aucune Connection Space/Platform, aucun credential, endpoint, modèle technique ni secret.  
**Web :** partage `build_profile_interoperability_payload` entre API et template, sans requête HTTP vers soi-même.  
**Flutter :** `personal.interoperability` isolé par Profil, SyncEngine, snapshot acquis ; lors d'échec réseau, observation préservée et marquée ancienne, jamais déclarée preuve d'autorité actuelle.

### P2 — Actualiser et reprendre (LIVRÉ)

**Déclencheurs :** ouverture sans snapshot, refresh manuel, événements de synchronisation existants.  
**Réponse valide :** nouvelle projection autorisée remplace l'ancienne atomiquement.  
**Panne transport :** conserver la dernière observation sans fabriquer un succès.  
**403/404 explicitement owner-scoped :** appliquer la purge prévue par le noyau sync ; jamais réafficher une projection révoquée.  
**401 :** utiliser la récupération de session existante.  
**Offline sans snapshot :** expliquer l'indisponibilité, préserver le fonctionnement des autres surfaces.  
**Reprise :** ne pas déclencher un appel de mutation au seul retour en ligne.

### P3 — Comprendre l'état et les capacités (LIVRÉ en lecture)

L'UI expose une description humaine de `enabled/status/health/usable`, les capabilities allowlistées et la source propriétaire. Une Connection reliée sans capacité active n'est pas vendue comme actionnable. Les Actions M7 projetées sont une *capacité potentielle* : sans lien d'exécution propriétaire, aucun CTA « Exécuter ». Les Extensions ne sont présentées que si autorisées, disponibles et activées.

### P4 — Connecter un nouveau service / consentir (NON LIVRÉ)

Un bouton `Connecter` n'est admissible que si l'owner expose une offre réelle et un parcours fiable avec : fournisseur concret, finalité, données/scopes, identification de l'acteur, retour sûr, preuve d'autorisation, stockage secret côté serveur, traitement de refus/expiration, état final relu du propriétaire. **Ne pas créer d'OAuth générique à partir des callbacks Accounts ni de `ProviderConnection` Intelligence.** Un fournisseur présent dans Accounts pour le login n'est pas une permission de lire ses données.

### P5 — Désactiver, reconnecter et révoquer (NON LIVRÉ génériquement)

`manageable=true` est une décision d'autorité, **pas une URL disponible**. Un contrôle mutateur requiert un owner, une route et une méthode réelles, CSRF/session Web ou bearer mobile, validation serveur de portée, protection idempotence/concurrence, confirmation de révocation et invalidation des caches. La révocation d'un token externe et la désactivation d'une connexion sont deux opérations distinctes : ne jamais les confondre. Aucun client ne modifie sa projection locale en guise de confirmation.

### P6 — Utiliser une capacité dans une démarche (CONDITIONNEL)

La démarche (Journey, Resource, Payment, Notification, etc.) choisit l'action et son contrat. L'owner vérifie Permission/Mandate, Connection autorisée, paramètres métier, idempotence et résultat. Connexions sert à comprendre/gérer la relation, **pas** à exécuter toutes les actions disponibles.

## 3. Scénarios Space

### S1 — Consulter les connexions du Space (LIVRÉ Web/API)

**Entrée :** console Nous → Connexions ou `GET /api/v1/organizations/workspaces/<slug>/interoperability/`.  
**Autorité :** Mandate direct `space.manage` sur ce Space ; Membership, Team, Group, Assignment ou Platform ne donnent jamais ce droit automatiquement.  
**Refus :** 404 pour ne pas divulguer l'existence d'un autre Space.  
**Projection :** seules Connections `scope=space` de l'organisation courante.  
**Exécution :** uniquement via un owner explicite, jamais sur un simple état `manageable`.

### S2 — Consultation Flutter Space (OUVERT)

Le contrat API existe mais aucun écran Flutter Space de connexion n'est attesté par ce checkpoint. La future consommation doit se brancher sur le contexte Space déjà existant et isoler la lecture par `actor + space`, sans copier le snapshot personnel. Un changement/retrait de Mandate invalide cette lecture. Ne pas ouvrir la navigation sans autorité.

### S3 — Création/gestion d'une connexion Space (NON LIVRÉ génériquement)

Même contrat owner-led que P4/P5, avec identité du Space et contrôle direct de `space.manage` sur **chaque** opération serveur. Aucune autorisation par simple appartenance ou par autorité Platform implicite.

## 4. Scénarios Platform

### T1 — Inspecter les connexions Platform (LIVRÉ Web/API)

**Entrée :** Platform, `GET /api/v1/platform/interoperability/`.  
**Autorité :** `platform.manage`.  
**Isolation :** seules Connections Platform ; `space_modules_included=false`, `personal_modules_included=false`.  
**Confidentialité :** pas de credentials ni d'internes techniques dans le payload client.

### T2 — Pilotage/configuration fournisseur (INTERNE / propriétaire)

Intelligence Admin a une frontière technique spécifique. Ne pas transformer Platform en navigateur ORM ni exporter secrets/configuration. Ajouter un parcours Platform seulement après contrat owner contrôlé et audit explicite.

## 5. Matrice des réponses d'autorité

| Événement | Projection/UX | Opération possible ? |
|---|---|---|
| Profile connecté et propriétaire | Z16 personnel | Lecture ; mutation seulement si owner l'expose |
| Autre Profile | Données absentes | Non |
| Space avec `space.manage` direct | Z16 Space | Lecture ; mutation propriétaire distincte |
| Space avec Membership seulement | 404 | Non |
| Platform avec `platform.manage` | Z16 Platform uniquement | Lecture ; mutation propriétaire distincte |
| Connection disabled | visible si autorisé, `usable=false` | Pas d'usage |
| Health unavailable/degraded/unknown | état honnête, distinct du droit | Revalidation owner avant action |
| Perte réseau Flutter | snapshot daté, lecture seule | Aucun nouveau droit |
| 403/404 owner-scoped | retrait du snapshot concerné | Non |
| 401 | récupération authentification | Non avant réauthentification |
| Permission/Mandate révoqué | serveur refuse, client invalide | Non |
| Action sans lien propriétaire | métadonnée informative seulement | Non |

## 6. Frontières transverses

- **Accounts/social login** : connexion de compte Makolo ≠ délégation d'accès à un service.
- **Payments** : initiation et confirmations gardées chez Payments, selon ses propres permissions et idempotence.
- **Notifications push** : endpoint d'installation et révocation gardés chez Notifications.
- **Geography/Spatiotemporal** : provider d'information géographique/météo n'est pas une Connection personnelle par défaut.
- **Events/Webhooks** : contrat transport + signature ; pas d'abonnement utilisateur direct sans owner autorisé.
- **Extension** : seulement les Actions, événements, projections et UI slots allowlistés ; aucune exécution arbitraire ou marketplace.
- **Local-first** : cache d'observation seulement, pas de consentement, droit ou succès stocké comme vérité indépendante.

## 7. Critères de sortie et tests ciblés

- Même vérité Z16 pour le Web et Flutter Profile ; états de connexion cohérents.
- Profile A ne voit jamais B ; une fixture Space ne rejoint jamais `personal.interoperability`.
- Space sans Mandate direct reste 404, même si Membership ou privilège Platform existe.
- Platform ne révèle jamais Profile/Space.
- Aucun token, clé, endpoint provider ni credential dans une projection Web/API/cache.
- Disabled ≠ usable ; degraded et unknown ≠ autorisation permanente.
- Sans snapshot Flutter, panne transport ≠ chargement infini ; avec snapshot, panne ≠ suppression.
- 403/404 provoquent les invalidations du noyau sync ; 401 conserve la récupération de session.
- Actions et Extensions sans endpoint owner restent informatives ; absence de CTA fictif.
- Pas de migration ni d'API mutable générique requise pour fermer ces parcours de lecture.

## 8. Transfert vers C3 / lots d'implémentation futurs

1. Faire converger les libellés et états entre Web et Flutter à partir des vérités Z16.
2. Concevoir la profondeur Connexion N2 en lecture (finalité, disponibilité, capacité, propriété) seulement si une connexion réelle existe, sans montrer la configuration technique.
3. Brancher un éventuel écran Flutter Space sur la couche de contexte Space existante **après** audit des projections et gestion révocation.
4. Pour chaque service connectable futur, ouvrir un contrat owner spécifique (établir/consentir/révoquer) et des tests IDOR/révocation/idempotence avant de publier un CTA.
5. Ne pas prétendre que C2 rend les services externes OAuth libre-service disponibles.

**Verdict :** les parcours de consultation et de continuité sont prêts dans leur frontière canonique ; les parcours de connexion, de révocation et d'exécution utilisateur nécessitent des contrats propriétaires absents, et ne sont pas « implémentables » honnêtement par la seule couche Web/Flutter.
