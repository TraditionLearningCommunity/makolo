# C7 — Fermeture de l’interopérabilité dans l’expérience Web et Flutter

**PR de travail :** #522 — `fix/discover-a-continuation-context-20261014`  
**Statut :** correctifs et tests ciblés écrits et poussés ; validation exécutable non attestée dans cette session.  
**Portée :** fermer la cohérence des parcours réellement livrés C1–C6, sans inventer C8, OAuth universel, marketplace, nouveaux providers, second moteur de Sync ou nouvelles tables.

## 1. Constat runtime à la reprise

- M7 contient les contrats génériques Capability / Connection / Action / Extension / Webhook ; il ne fournit **aucun droit** par une simple installation.
- Z16 projette les vraies `ProviderConnection` Intelligence aux scopes Profile / Space / Platform.
- C4 fournit le lifecycle de clés chiffrées via Intelligence, en Web et Flutter personnels/Space et Web Platform.
- C5 permet deux actions explicites de Découvrir : clarification structurée et Web Research, sans fournisseur facturable sur un GET et sans sauvegarder les pistes externes comme faits métier.
- C6 réutilise Notifications/FCM et les modes Payments existants, en séparant `domain_integrations` de `connections`. Aucune liaison bancaire, géocodage réseau ou calendrier externe n'est déduite de leur existence.

## 2. Contrats de fermeture implémentés

### Autorité, session, propriétaire

1. **Backend :** l'autorité est contrôlée lors de chaque GET et mutation propriétaire. Profile : `profile.user` ; Space : Mandate direct `space.manage` (pas TeamMembership ni rôle Platform) ; Platform : `platform.manage`. Une révocation effective retire la lecture et refuse immédiatement PATCH/DELETE. Les tests de C7 révoquent réellement des Mandates après une première lecture valide.
2. **Flutter Profile :** un snapshot Z16 stocké est une observation, jamais un droit actuel. À l'entrée, l'écran sollicite `SyncEngine.pullInteroperability()` même si un snapshot existe ; le dernier état connu reste visible en cas d'échec mais les mutations restent fermées. `_refreshAndConfirm` distingue une modification serveur confirmée d'une projection ensuite inaccessible.
3. **Flutter Space :** lecture online-only, sans copie dans le `ProfileStore`. L'acteur et l'ID Space sont revalidés après chaque réponse. Le changement de Space, runtime ou perspective invalide immédiatement les données ; le contexte est réinspecté avant d'autoriser des contrôles. Les états Sync dégradés ou syncing interdisent les mutations.
4. **Dialogues et catalogues :** `IntelligenceConnectionControls` surveille `runtime + owner path`, invalide les requêtes de catalogue hors génération, et ne soumet pas une clé saisie dans un dialogue ouvert pour un ancien propriétaire. Une opération en vol n'affecte pas les flags de la nouvelle portée.

### Statut, erreur, reprise

5. **Vocabulaire commun :** `interoperability.presentation` (Web) et `interoperability_presentation.dart` (Flutter Profile et Space) ont la même hiérarchie : disabled → unavailable → degraded → unknown → usable/no-capability → connected/available. `health=unknown` ne signifie jamais que le fournisseur a été vérifié.
6. **Confirmer avant d'annoncer :** les mutations owner ne se doublent pas d'une vérité locale optimiste. La confirmation de l'écriture serveur reste distincte d'un éventuel échec du refresh. Les messages cachent les erreurs et clés brutes.
7. **Empty/offline/error :** les états non peuplés, la projection sans snapshot, la panne réseau et le snapshot ancien restent distinguables et reprenables. Une page Connexions ne rend pas inopérants Découvrir, Moi, Nous ou le reste de Makolo.

### Push, continuité de révocation

8. Le retrait d'un PushEndpoint appartient à Notifications, et les notifications déjà en file sont ignorées si l'appareil est inactif.
9. Une installation révoquée ne peut plus être réactivée silencieusement ni par token refresh, ni automatiquement après changement de Profil. Le propriétaire peut demander une réactivation explicite depuis l'appareil, avec la source FCM réelle. Aucun `installation_id`, `token_hash`, `token_hint` ni token chiffré n'est exposé dans les projections.
10. Flutter garde les requêtes d'appareils online-only et ne présente pas le résultat d'un ancien Profil comme succès après changement de runtime.
11. Une inscription automatique du même appareil sous un autre Profil ne peut pas réactiver un endpoint déjà révoqué : une intention explicite est nécessaire. Les projections en conflit ou obsolètes restent informatives et la mutation est désactivée.

## 3. Surfaces consommées, sans nouveau système

| Contexte | Entrée Web | Entrée Flutter | Autorité et owner |
|---|---|---|---|
| Profile | Moi → Connexions | `/connections` | Profil authentifié ; Intelligence + Notifications ; Payments pour modes exposables |
| Space | Nous → Connexions | `/space/<slug>/connections` | `space.manage` direct ; `finance.manage` direct distinct pour modes financiers |
| Platform | Interopérabilité | Pas de shell Platform mobile personnel | `platform.manage` ; Intelligence + faits Payments stricts |
| Découvrir | `POST /discover/clarify/`, `POST /discover/research/` | recherches explicites depuis la recherche native | Profil ; Discovery conserve vérité des critères et des items ; Gateway seulement si volontaire |

Aucun écran ne promet qu'une Action M7 sans endpoint propriétaire puisse être exécutée. Les Extensions vides restent vides. Le health et un badge `usable` ne remplacent jamais une permission.

## 4. Matrice d'épreuves ciblées

| Scénario | Attendu |
|---|---|
| Profil B lit/modifie la clé du Profil A | 404 / refus, aucun secret |
| Space Manager valide, puis Mandate révoqué | GET 404, mutation 404, état propriétaire inchangé |
| Platform admin sans Mandate Space direct | Space 404 ; Platform isolée |
| Mandate Platform révoqué | GET/gestion Platform 403 |
| Cache personnel + offline | lisible en dernier état connu, mutation désactivée |
| Espace A → Espace B pendant GET | réponse tardive A ignorée ; jamais de copie dans ProfileStore |
| Dialogue clé ouvert puis changement runtime/path | aucune clé POST vers le nouveau propriétaire |
| Rotation/désactivation/intention de retrait | serveur confirme ; relecture séparée ; aucune modification optimiste |
| Santé unknown/degraded/disabled | libellés identiques Web/Profile/Space |
| Push révoqué, livraison déjà en file | aucune livraison à un endpoint retiré |
| Push révoqué et autre utilisateur démarre le même appareil | pas de réactivation silencieuse |
| Découvrir sans clé ou fournisseur indisponible | parcours déterministe préservé ; aucune vérité externe inventée |

## 5. Tests et vérifications à exécuter dans un checkout

Tests ajoutés ou étendus C7 :
- `interoperability/test_c7_live_authority.py` : révocations réelles et absence de transferts d'autorité ;
- `mobile/test/c7_intelligence_owner_continuity_test.dart` : réponse de catalogue obsolète et ancien dialogue de clé ;
- `mobile/test/c7_space_owner_continuity_test.dart` : réponse Space A après changement vers B, lecture seule sur Sync dégradée ;
- `mobile/test/space_connections_status_test.dart` : état et langage communs ;
- `notifications/test_push.py` : non-réactivation cross-Profil et non-livraison après révocation.

Régressions propriétaires C4–C6 à conserver :

```bash
python manage.py test interoperability.test_z16_api interoperability.test_c7_live_authority intelligence.test_connection_management_api intelligence.test_connection_management_web notifications.test_push interoperability.test_c6_owner_integrations discovery.api.test_c5_owner_actions core.test_w8_personal_interoperability
python manage.py makemigrations --check --dry-run
cd mobile
flutter test test/interoperability_screen_test.dart test/space_connections_status_test.dart test/c7_intelligence_owner_continuity_test.dart test/c7_space_owner_continuity_test.dart test/intelligence_connection_controls_test.dart test/c6_domain_integrations_projection_test.dart test/c6_push_device_controls_test.dart
flutter analyze lib/features/interoperability lib/repositories/interoperability_repository.dart lib/platform/notifications/push_endpoint_registrar.dart
```

Aucune CI déclenchée dans cette session. **Les tests sont écrits, pas attestés verts.** Le contrat de fermeture définitive suppose l'exécution des suites ciblées, l'inspection des éventuels échecs et un passage réel sur appareils + comptes autorisés (Profile, Space, Platform) ; il ne suppose pas de faux fournisseurs ni de données de démonstration en environnement réel.

## 6. Décisions et hors périmètre

- Pas de migrations ni de nouvelle entité. Les vérités métier restent dans Intelligence, Payments, Notifications, Discovery et Authorization.
- Pas d'OAuth générique ou permission Google Calendar/Drive/Gmail par social login.
- Pas de provider PSP réel, de météo, geocoding ou routing déclaré si absent.
- Pas de webhook tenant sans identité et key resolver prouvés.
- Pas d'usage externe déclenché automatiquement hors contrat utilisateur.
- C8 n'est pas fixé par ce document : vérifier le plan canonique avant d'en faire un nouveau chantier.

**Verdict C7 : code de fermeture poussé ; QA d'exécution non attestée, ne pas dire “fermé et validé” avant les preuves.**
