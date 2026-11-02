# C6 — Extensions des intégrations métier réelles

**Programme :** continuité C1–C5 ; PR #522.  
**Statut :** implémenté dans la branche de PR ; tests ciblés écrits, non exécutés dans cette session. **Aucune migration ni nouveau modèle.**

## Problème utilisateur

C4 relie un fournisseur Intelligence et C5 permet à Découvrir de l'utiliser. Les autres capacités spécialisées de Makolo ne doivent pas être présentées comme des comptes externes connectables : certaines sont déjà utilisables à travers leur domaine propriétaire ; d'autres n'ont encore aucun fournisseur installé.

C6 ferme les parcours de **gestion des appareils push** et de **visibilité contextuelle des modes de paiement effectivement disponibles**. Il n'ajoute ni marketplace, ni OAuth universel, ni Action exécutable sans owner, ni faux providers.

## Audit des propriétaires

| Domaine | Faits runtime constatés | C6 |
|---|---|---|
| Intelligence | ProviderConnection / Credential / Route, Web+Flutter et Découvrir C4–C5 | Réutilisé, aucun double |
| Notifications | FCM : PushEndpoint chiffré, livraison owner, inscription et révocation | Inventaire privé d'appareils, retrait et réactivation explicite |
| Payments | `PaymentProvider.SANDBOX` sous flag et `PaymentProvider.MANUAL` pour autorité finance | Disponibilité par owner, modes distincts des connexions, aucune initiation générique |
| Accounts | Social login Google, Microsoft, Facebook, LinkedIn sous allauth | **Non** assimilé à une permission d'accès aux fichiers, calendriers ou messages |
| Geography | Contrat `Geocoder`, aucune implémentation réseau canonique | Aucune fausse connexion créée |
| Spatiotemporal | Interfaces routing/traffic/weather + défaut NoOp | Aucune disponibilité fournisseur affirmée |
| Domain Events/Webhooks | Contrats de signature, delivery injecté, pas de key resolver universel attesté | Pas de webhook « activable » inventé |
| M7 Extensions | Registre allowlisté, pas de catalogue produit générique installé | Aucun plugin arbitraire, aucune exécution directe |

## Contrats livrés

### 1. Notifications : appareils privés et révocation durable

- `GET /api/v1/notifications/push/endpoints/` renvoie uniquement les appareils **actifs de l'acteur** (maximum 30), avec `id`, provider, platform, version, statut et dernière observation. Réponse `private, no-store`.
- `DELETE /api/v1/notifications/push/endpoints/<uuid:pk>/` : seul propriétaire, 404 anti-IDOR, révocation idempotente (204), délégation à `notifications.push.revoke_push_endpoint_by_id`.
- L'API d'enregistrement existante `POST /api/v1/notifications/push/endpoints/` reste propriétaire et compatible ; son serializer public ne renvoie désormais plus l'`installation_id` ni `token_hint`. Les tokens restent chiffrés côté serveur.
- Le nouvel argument `reactivate` est `false` par défaut : une inscription automatique ou un changement de token **ne peut plus annuler la révocation décidée par ce Profil sur cette installation**. La réactivation demande `reactivate=true` de l'acteur authentifié via le token local de son appareil.
- Web Moi → Connexions : appareils visibles sans secrets, retrait protégé CSRF sur le service owner Notifications.
- Flutter Moi → Connexions : lecture online-only du propriétaire, retrait sous contrôle d'une projection fraîche, activation explicite « Activer sur cet appareil » lorsque Firebase est effectivement disponible dans le runtime mobile. La source FCM n'est jamais stockée dans Drift/ProfileStore.
- Limite : révoquer l'inscription Makolo ne supprime pas nécessairement le token chez Firebase ; cela supprime son usage de livraison par Makolo.

### 2. Payments : capacités réelles, sans faux comptes externes

- Nouveau selector propriétaire `payments.integration_availability.payment_configuration_for(actor)`, utilisé **à la fois** par l'API existante `GET /api/v1/payments/configuration/` et par les projections d'interopérabilité.
- La configuration ne montre `sandbox` que sous `PAYMENTS_SANDBOX_ENABLED` et `manual` que pour une autorité Finance pertinente.
- **Aucun des deux n'est une Connection externe** et `connected=false` est explicite. Une possibilité de paiement ne déclenche jamais `initiate_payment` hors de l'obligation et de l'autorité métier.
- Dans Nous, le mode manuel n'est projeté que pour `finance.manage` **direct** sur l'Espace considéré ; simple Membership, rôle Platform ou `space.manage` ne crée pas cette autorité financière.
- Dans Platform, seuls les modes owner disponibles sont exposés aux opérateurs `platform.manage`, sans détails Profil/Space.

### 3. Lecture Z16 additive, sans second système

`interoperability.projections.build_interoperability_payload` ajoute un champ optionnel `domain_integrations`. **Ce ne sont ni des `connections`, ni des M7 `actions`, ni des `extensions`.** Le schéma `z16.v1` conserve les champs existants : les anciens snapshots Flutter sans ce champ restent acceptés.

Chaque ligne retenue possède un code, un owner, une catégorie, une disponibilité technique, un statut et un descriptif. Les intégrations push incluent un compte d'appareils (pas les credentials). Les modes Payments ne déclarent jamais de compte financier relié. Les liens techniques pointent uniquement vers les routes owner déjà vérifiées.

L'état `available` n'accorde ni Permission, ni Mandate, ni droit d'exécution. Chaque mutation repart du contrôleur propriétaire et recontrôle la session et le propriétaire.

### 4. Interfaces Web et Flutter

- Moi : affichage distinct « Services utilisés dans Makolo » ; liste/retirer les appareils push ; présentation honnête de `sandbox_only` et `manual_available`.
- Nous : modes Payments seulement si `finance.manage` direct ; handoff Web et Flutter sous la lecture Z16 Space déjà autorisée.
- Platform : disponibilité de traitement owner affichée dans la page technique et l'API, pas de shell Platform personnel Flutter.
- Offline : une ancienne projection est une observation, **jamais une autorisation de modifier un appareil**. Le contrôle Flutter n'envoie pas de mutation lorsque l'état Sync est dégradé.

## Contrôle qualité

Tests ajoutés ou étendus :
- `notifications/test_push.py` : inventaire secret-free, révocation cross-Profile refusée, répétition idempotente, interdiction de réactivation silencieuse après token refresh, réactivation explicite.
- `interoperability/test_c6_owner_integrations.py` : exposition Profile/Space/Platform, finance direct, aucun PSP imaginaire, CSRF, absence d'identifiants sensibles, suppression Web owner.
- `mobile/test/c6_domain_integrations_projection_test.dart` : décodage additif, séparation des Connections, ancien Z16.
- `mobile/test/c6_push_device_controls_test.dart` : contrôle de révocation, pas de token affiché, mode lecture seule quand la fraîcheur ne permet pas les mutations.

Commandes de validation ciblée dans le checkout de #522 :

```bash
python manage.py test notifications.test_push interoperability.test_c6_owner_integrations interoperability.test_z16_api core.test_w8_personal_interoperability
python manage.py test payments
python manage.py makemigrations --check --dry-run
cd mobile
flutter test test/c6_domain_integrations_projection_test.dart test/c6_push_device_controls_test.dart test/intelligence_connection_controls_test.dart
flutter analyze lib/features/interoperability lib/repositories/interoperability_repository.dart lib/platform/notifications/push_endpoint_registrar.dart
```

**Non attesté ici :** exécution Django/Flutter, PostgreSQL, test de livraison FCM réel, tests de configuration Payments sur environnement de bêta. Les CI n'ont pas été déclenchées à la demande. Ne pas assimiler code poussé à validation d'exécution.

## Critères de sortie

1. Les seules intégrations montrées proviennent de faits propriétaires réels.
2. Un utilisateur peut inspecter et retirer ses appareils, sans lire ceux des autres, ni exposer de tokens/installation IDs.
3. Un appareil révoqué ne se réactive pas sans intention explicite sur l'appareil.
4. Payments garde la vérité des obligations et de l'argent, aucun PSP externe/connexion bancaire n'est fabriqué.
5. Space/Platform respectent les frontières d'autorité, y compris finance séparé de space.manage.
6. Web et Flutter consomment le même Z16 additif, sans état métier dupliqué, succès optimiste ni migration.
