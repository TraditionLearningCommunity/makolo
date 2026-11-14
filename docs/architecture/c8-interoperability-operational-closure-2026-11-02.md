# C8 — Fermeture opérationnelle de l'interopérabilité C1–C7

**Périmètre retenu le 2 novembre 2026** : dernier chantier transversal de consolidation des parcours existants, proposé après C7. Ce numéro ne correspond pas à un C8 historique retrouvé.  
**Branche de travail** : PR #522, `fix/discover-a-continuation-context-20261014`.  
**Verdict** : correctifs et régressions **poussés en code** ; tests, PostgreSQL, Flutter, fournisseur réel et FCM appareil **non exécutés/attestés dans cette session**. Les gates doivent rester explicites avant fusion.

## 1. Problème et règle de composition

C1–C3 ont établi le catalogue, les autorités et le contrat de présentation. C4 fournit les connexions Intelligence à clé propre, C5 leur consommation explicite dans Découvrir, C6 les intégrations réellement propriétaires (Notifications/FCM et modes Payments), C7 l'isolation des contextes et la continuité Web/Flutter.

C8 ne doit ni créer des fournisseurs inexistants, ni un « M7.execute » universel, ni déplacer les secrets, les Mandates, Payments, l'observation FCM ou les faits Discovery dans un domaine Interoperability. M7/Z16 restent les contrats de composition, Intelligence / Discovery / Notifications / Payments / Authorization les sources de vérité.

## 2. Correctifs C8 implémentés

### C8.1 — Intégrité serveur, sécurité, révocation

- **Intelligence / health** : un probe potentiellement facturable lancé avant une rotation, une désactivation ou un retrait ne peut plus réécrire `health_status=healthy` après la mutation. La mise à jour utilise une comparaison atomique avec le `updated_at` et l'activation observés au démarrage ; une réponse devenue obsolète retourne `unknown`, sans réintroduire de preuve périmée.
- **Intelligence / health** : la réponse `IntelligenceResult.available=False` est désormais interprétée comme un échec de santé, même sans exception. `invalid_credentials` a un état propriétaire distinct. Un résultat mal formé ne certifie pas la disponibilité.
- **Intelligence / admin** : une rotation de credential via la console technique invalide désormais la santé et les mesures antérieures, comme dans le service API C4 ; pas de réutilisation d'une preuve attachée à l'ancienne clé.
- **Intelligence / concurrence Platform** : la création de connexions sous une portée Platform unique est désormais sérialisée entre opérateurs distincts avec un verrou transactionnel PostgreSQL à identifiant stable. Le verrou individuel d'opérateur ne suffisait pas. Aucun nouvel état persistant ; le fallback SQLite de développement n'offre pas cette garantie concurrente et le test dédié est réservé à PostgreSQL.
- **Interoperability et Intelligence APIs** : `Cache-Control: private, no-store` est imposé à tous les résultats, y compris les erreurs d'autorité, d'authentification et de validation, via le mixin de confidentialité existant.
- Les Mandates Profile/Space/Platform continuent à être contrôlés dans les propriétaires lors de chaque mutation. Aucun booléen Z16 `manageable` n'est un droit générique.

### C8.2 — Usage métier complet et vérité

- Test HTTP propriétaire **create → Z16 → Découvrir Web Research → disable → unavailable/no network → enable → rotate → utiliser nouvelle clé → DELETE → credential supprimé/Z16 vide → unavailable/no network**. La requête au fournisseur est simulée et l'en-tête Bearer courant est contrôlé ; aucun appel réel payant ni clé utilisateur.
- Les sources externes restent des pistes sourcées, non admises comme Activities/Occurrences/Opportunities. Aucun accès aux données privées d'un autre Profil n'est accordé au fournisseur.
- Notifications garde son cycle d'inscription/révocation/réactivation FCM et Payments ses seuls modes réellement présents (sandbox ou traitement manuel autorisé). Les tests C6–C7 couvrent ce cycle sans inventer de PSP connecté.

### C8.3 — Continuité Web/Flutter

- Flutter Moi : après une mutation confirmée par le serveur, une simple `Future` SyncEngine terminée ne prouve plus que l'observation a été appliquée. `ProfileConnectionsScreen._refreshAndConfirm` compare l'horodatage du snapshot Z16 précédent à celui de la nouvelle observation. En cas de réponse abandonnée, erreur ou autorité modifiée, le client annonce l'indisponibilité de la relecture, **pas** une confirmation fictive.
- C7 conserve la purge/suspension lors du changement de Profil/Space, la lecture Space online-only et l'absence de clés dans Drift/ProfileStore. Les boutons mutations dégradées restent inactifs ; la dernière observation est étiquetée comme telle.

### C8.4 — Robustesse et exploitation

- Discovery journalise un événement `discovery.external_action` avec seulement l'action (`clarify`/`research`), le statut public, la catégorie d'échec publique et un nombre de pistes borné à trois. Il n'écrit **ni requête, ni utilisateur, ni URL, ni clé, ni prompt, ni réponse de fournisseur** dans ces nouveaux événements.
- Le `IntelligenceGateway` conserve sa télémétrie provider-neutral existante (capability, issue, latence, code et feature, sans payload) ; les categories d'erreur historiques non normalisées ne sont pas modifiées artificiellement pour passer un test.
- Discovery reste une action **POST explicite**, limitée par utilisateur, avec repli déterministe et `private, no-store`. Rien ne facture un fournisseur par un simple GET Découvrir.

### C8.5 — Réconciliation, preuve et handoff

Les contrats C1–C7 et leurs frontières restent inchangés. Aucun modèle ni migration nouvelle C8, aucun backfill, aucune installation OAuth/Calendar/Drive/PSP/Geography/Spatiotemporal non prouvée.

## 3. Fichiers concernés

**Correctifs** : `intelligence/health.py`, `intelligence/admin.py`, `intelligence/connection_api.py`, `interoperability/api_views.py`, `discovery/assistance.py`, `mobile/lib/features/interoperability/connections_screen.dart`.

**Tests C8** :
- `intelligence/test_c8_health_consistency.py` — succès sain, `available=False`, diagnostic retardé après rotation, disable et DELETE, rotation admin.
- `intelligence/test_c8_platform_creation_concurrency.py` — deux administrateurs Platform créant simultanément le même fournisseur sous PostgreSQL, un seul succès attendu.
- `interoperability/test_c8_owner_response_privacy.py` — 404 Space, 403 Platform, 400 payload, profil et `no-store`.
- `discovery/api/test_c8_interop_journey.py` — parcours de connexion et usage propriétaire jusqu'au retrait, sans transport externe réel.
- `discovery/api/test_c8_operational_events.py` — logs utilisables et minimaux, sans requête privée ou clé.
- `mobile/test/c8_interop_mutation_refresh_test.dart` — écriture Intelligence acceptée, rafraîchissement Z16 interrompu, conservation du snapshot et absence de secrets dans le store.
- Les tests C4–C7 existants restent obligatoires (permissions, CSRF, frontières d'autorité, FCM, Flutter Sync/Space et sorties Discovery).

## 4. Matrice d'acceptation et commandes reproductibles

| Gate | Preuve requise | Statut |
|---|---|---|
| Autorité | Cas Profile/Space/Platform, IDOR, Mandate retiré, no-store sur erreur | Tests écrits ; non exécutés |
| Concurrent health | Rotation/désactivation/DELETE pendant un probe ; résultat indisponible jamais sain | Tests écrits ; non exécutés |
| Gateway réel | Connexion personnelle avec clé consentie, opération avec quota connu, état provider observé | Externe, non attesté |
| Découvrir | Résultats structurés, provenance et limite, erreur/réparation, coût explicite | Mock tests écrits ; externe non attesté |
| FCM | Inscription Android/iOS, notification, révocation, réactivation après redémarrage/changement de Profil | Tests code ; appareil non attesté |
| Payments | Sandbox flag et finance direct, aucune fausse connexion PSP | Tests C6 ; non exécutés |
| Flutter | Cold-start, absence réseau, cache conservé, Z16 réellement appliqué, changement de Profil et Space, retrait | Tests code ; appareil non attesté |
| Données | Aucune migration C8 ; schémas déjà livrés et migrations des autres chantiers vérifiés | Contrôle de migrations non exécuté |
| Intégration PR | Branches concurrentes examinées, intégration sans écraser leurs travaux ; CI obligatoire avant merge | PR ouverte ; CI non déclenchée |

```bash
python manage.py test intelligence.test_c8_health_consistency intelligence.test_c8_platform_creation_concurrency interoperability.test_c8_owner_response_privacy discovery.api.test_c8_interop_journey discovery.api.test_c8_operational_events
python manage.py test intelligence.test_connection_management_api intelligence.test_connection_management_web intelligence.test_web_research_routing interoperability.test_z16_api interoperability.test_c6_owner_integrations interoperability.test_c7_live_authority discovery.api.test_c5_owner_actions notifications.test_push
python manage.py makemigrations --check --dry-run
cd mobile
flutter test test/c8_interop_mutation_refresh_test.dart test/interoperability_screen_test.dart test/c7_intelligence_owner_continuity_test.dart test/c7_space_owner_continuity_test.dart test/c6_domain_integrations_projection_test.dart test/c6_push_device_controls_test.dart test/discovery_c5_connected_actions_test.dart
flutter analyze lib/features/interoperability lib/repositories/interoperability_repository.dart
```

Le test réel d'un fournisseur, la configuration opérationnelle et les coûts restent soumis à autorisation explicite. `INTELLIGENCE_CREDENTIAL_MASTER_KEY` est requis pour les credentials BYO, `MAKOLO_FIREBASE_PUSH_ENABLED` gouverne FCM et `PAYMENTS_SANDBOX_ENABLED` le mode de démonstration : ne pas déduire leur valeur effective d'un document. Une configuration de cache partagée est nécessaire pour que les throttles interworkers aient une portée globale.

## 5. Critères de sortie et dette résiduelle déclarée

**C8 terminé en implémentation** signifie : aucun scénario nouveau inventé, corrections et tests de bord présents dans #522, vérité propriétaire et interfaces réconciliées.

**C8 validé en exploitation** exige **réellement** : tests verts, migrations contrôlées, postures PostgreSQL, essais mobiles avec authentification et changements d'acteurs, au moins un fournisseur autorisé testé sous budget connu, aucune régression critique de sécurité/continuité. Ces preuves ne sont pas disponibles dans cette session et ne doivent pas être remplacées par une mention « DONE ».

À surveiller dans la fermeture et les gates M9/M10, sans les traiter comme fonctionnalités C8 fictives : concurrence inter-opérateurs de création de connexions Platform corrigée pour le chemin propriétaire PostgreSQL (sans contrainte d'unicité DB générale, contrôler les voies d'administration directe), santé réelle indépendante de la capacité métier, échec de transport après commit pouvant nécessiter une relecture, coût/quotas réels externes, environnement de push iOS/Android et capacités non installées.

**Décision :** arrêter l'expansion du chantier C1–C8 une fois les défauts réels corrigés ; transférer les gates d'exécution au processus de qualité existant, sans masquer les limites ni créer de nouvelle architecture locale.

## 6. Solde des reliquats de code C1–C8 (2 novembre 2026)

Ces corrections sont intervenues **après** l'implémentation initiale de C8, dans la même PR #522. Elles ne constituent pas un nouveau train C9.

1. **Notifications — changement de Profil** : `register_push_endpoint` refuse désormais tout transfert implicite d'une installation FCM appartenant à un autre Profil, même si un token se renouvelle. Une réactivation explicite sur l'appareil exige **simultanément** le token FCM courant et le même identifiant d'installation que l'endpoint existant. Un seul identifiant ne permet pas de reprendre un endpoint tiers. Les correspondances en conflit entre propriétaires ne sont pas supprimées en cascade. `PushEndpointRegistrar.start` gère les refus de synchronisation automatique en best effort et maintient l'écoute des futurs tokens ; seule `reactivateCurrent()` expose une erreur à la demande de l'utilisateur. Ce transfert ne représente ni mandat, ni permission, ni preuve métier générale. Si le fournisseur a renouvelé le token depuis le dernier enregistrement de l'autre Profil, une migration inter-Profil peut nécessiter un retrait par l'ancien propriétaire plutôt qu'un transfert automatique non vérifiable ; pas de preuve cryptographique artificielle introduite.
2. **Flutter — vérité post-réactivation** : trois états distincts, conservés à l'écran : écriture acceptée par Notifications, liste des appareils rafraîchie, projection Z16 des connexions effectivement confirmée. Une deuxième relecture échouée n'annonce plus un succès global ; le service peut être enregistré sans que l'interface ait la dernière projection.
3. **Payments — contexte financier** : `payments.manual` n'est plus projeté globalement dans Moi à partir d'un rôle Finance valable quelque part. Son état reste propriétaire dans l'Espace qui possède `finance.manage` direct ou dans Platform sous permission pertinente. Une démonstration sandbox reste clairement séparée d'un prestataire bancaire réellement connecté.
4. **Continuité réelle des capacités** : une connexion Intelligence personnelle ayant `web_research` ou `structured_generate` reçoit un accès vers la page **Découvrir** existante sur Web et Flutter. Ce lien n'exécute pas automatiquement un appel payant et ne crée pas une nouvelle Action. Les cartes informatives M7 Action/Extension sans destination propriétaire implémentée sont clairement décrites comme **contrats déclarés**, non comme boutons exécutables.
5. **Intelligence / Découvrir — reprise après échec** : distinction publique et stable entre `connection_unavailable` (aucune route utilisable), `invalid_credentials` (clé refusée), `rate_limited` (attendre le quota) et `network_unavailable` (fournisseur temporairement inaccessible). Les liens vers Moi → Connexions ne sont proposés que si configurer ou réparer une clé constitue une suite pertinente ; les erreurs réseau et quotas gardent la recherche déterministe. Aucun détail technique, credential ou texte utilisateur n'est ajouté au journal.

Tests ciblés ajoutés ou renforcés : `notifications/test_push.py`, `mobile/test/c6_push_device_controls_test.dart`, `interoperability/test_c6_owner_integrations.py`, `mobile/test/interoperability_screen_test.dart`, `discovery/api/test_c8_recovery_remainders.py`, `discovery/api/test_c5_owner_actions.py`, `discovery/api/test_c8_operational_events.py` et `intelligence/tests.py`.

**Statut des preuves** : changements poussés à la branche de PR, tests ciblés rédigés mais non exécutés dans cette session, CI non sollicitée selon l'instruction. Ne pas déclarer la fermeture opérationnelle validée à partir du seul push GitHub. Aucune migration, aucune extension de catalogue ni modification directe de `main`.
