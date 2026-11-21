# C5 — Connexions Intelligence consommées dans une action Makolo

**Chantier :** PR #522, après C4. **Statut :** implémenté en code ; tests ciblés écrits, non exécutés dans cette session. Aucune migration, aucun modèle, aucune nouvelle Action M7.

## 1. Besoin et périmètre

C4 permet de relier et de gérer des services Intelligence à clé API. C5 ferme le premier usage utilisateur **de bout en bout** dans un domaine propriétaire existant :

1. **Découvrir / Clarifier ma recherche** utilise `structured_generate` (OpenAI compatible) pour proposer des filtres canoniques déjà définis par Discovery.
2. **Découvrir / Chercher des sources externes** utilise `web_research` (Tavily, Exa ou OpenAI Responses Web) pour afficher des pistes externes liées à la recherche. Une piste externe n'est pas une Activity, Occurrence, Opportunity, Proof ni donnée Mayele admise.

Les usages existants de `IntelligenceGateway` (Discovery, Interpreter, WebResearch) sont réutilisés. L'Interpreter en batch conserve son contexte plateforme ; C5 ne lui transfère pas la clé d'un Profil sans mandat et ne crée pas d'API `M7.execute`.

**Parcours :** le Profil choisit un geste → serveur récupère le Profil courant sans accepter de propriétaire client → registre Intelligence résout les routes actives du propriétaire et les routes plateforme existantes → Gateway exécute l'adapter → Discovery vérifie son contrat → Web/Flutter présentent critères ou sources → utilisateur poursuit son exploration avec le selector canonique.

## 2. Contrats HTTP explicites

| Route | Autorité | Effet |
|---|---|---|
| `POST /api/v1/discovery/clarify/` | Profil authentifié | `{"criteria":{"q":"..."}}` → enveloppe `discovery.clarification` avec `status`, `reason`, `query`, `constraints` |
| `POST /api/v1/discovery/research/` | Profil authentifié | `{"q":"..."}` → enveloppe `discovery.source-leads` avec `status`, `reason`, `sources`, `candidates` |
| `POST /discover/clarify/` | Session Web + CSRF | Redirige vers la recherche déterministe avec les critères vérifiés et le contexte spatial conservé |
| `POST /discover/research/` | Session Web + CSRF | Page éphémère de sources externes avec retour au champ Découvrir |
| `GET /api/v1/discovery/items/`, `GET /discover/` | selon contrats Discovery existants | Restent déterministes : aucun appel fournisseur facturable implicite lors d'une simple exploration |

Aucun champ `profile_id`, `space_id`, `provider_id`, `base_url` ou `api_key` n'est accepté par ces actions. Le propriétaire réel de la Connection est Intelligence ; Discovery possède la décision d'appliquer les critères et de présenter des pistes dans une exploration.

## 3. Preuves métier et limitations

- **Clarification :** n'applique que les valeurs allowlistées `vertical`, `place`, `when`, `period`, `price`, `text` après validation et rapprochement avec les connaissances canoniques de lieux existants. Un filtre explicite n'est pas écrasé par un résultat de fournisseur. Une réponse invalide laisse la recherche déterministe intacte.
- **Web Research :** construit une `ResearchMission` temporaire, bornée à trois candidats et une requête, en réutilisant `IntelligenceWebResearchEngine`. Les références source et candidat sont produites par les contrats existants. Les réponses exposées sont limitées aux sources HTTPS et aux candidats effectivement sourcés, sans transformation en objet métier persistant.
- **Disponibilité :** status `unavailable` si aucune route utilisable, clé refusée, quota atteint, transport indisponible ou erreur. Les motifs publics sont bornés à `invalid_credentials`, `rate_limited`, `network_unavailable` et `provider_unavailable` ; aucune exception brute n'est exposée.
- **Confidentialité :** pas de secret dans la réponse, les liens, la projection, le cache, l'outbox ou l'analytics. Le texte de recherche part au fournisseur **uniquement sur POST explicite**, avec le consentement C4 préalable du titulaire de la clé. Les frais et quotas éventuels appartiennent au fournisseur.
- **Continuité :** en cas d'absence de service, d'erreur ou de résultat inutilisable, l'exploration déterministe est préservée. La carte, les filtres, la pagination et les viewers restent sous Discovery ; aucun résultat externe n'est enregistré comme possibilité.

## 4. Clients

- **Web :** deux formulaires CSRF distincts à côté du champ Découvrir après la recherche initiale. Pour les pistes, une profondeur transitoire affiche des liens externes avec indication explicite de non-vérification et retour à la recherche originale.
- **Flutter :** le `DiscoveryRepository` transporte les deux actions sans écrire dans Drift/ProfileStore. `DiscoverySearchScreen` permet de clarifier les critères, relance le selector existant, et ouvre les sources dans une feuille temporaire. Les URLs externes doivent être HTTPS et sans identifiants incorporés. Aucun usage en arrière-plan ni queue hors ligne.

## 4.1 Bornes de sécurité supplémentaires

- Les deux POST sont limités à **12 invocations par heure et par utilisateur authentifié**, via les throttles DRF existants (réutilisés dans les vues Django Web). Déployer avec un cache partagé si plusieurs workers doivent appliquer un budget global ; le cache non partagé reste une protection locale seulement.
- Les paramètres explicites de date, lieu, verticalité, moment et géographie ne sont jamais écrasés par une interprétation externe. Le rayon seul, sans position, ne déclenche pas une fausse autorité géographique.
- Les URLs de sources doivent être HTTPS, sans identifiants incorporés, et ne doivent pas cibler localhost, les IP privées ou les IP réservées. Seules les sources réellement citées par des pistes affichées figurent dans la réponse.
- Les erreurs de clé, de quota et de disponibilité sont réduites à des catégories publiques stables. Le contrat historique de l'IntelligenceGateway pour les erreurs réseau reste compatible ; aucune réponse brute du fournisseur ne ressort de l'API.
- Les utilisateurs peuvent rejoindre **Moi → Connexions** depuis Découvrir lorsqu'une capacité Intelligence n'est pas disponible ; aucune Permission ou Mandate n'est déduite de la présence d'un bouton.

## 5. Tests ciblés et contrat de sortie

Tests ajoutés : `discovery/api/test_c5_owner_actions.py` et `mobile/test/discovery_c5_connected_actions_test.dart`. Ils couvrent également le budget d'appels, la protection CSRF, les refus cross-Profil, le GET sans fournisseur, les filtres spatiaux, les URLs privées et la présentation Web des sources.

```bash
python manage.py test discovery.api.test_c5_owner_actions discovery.test_intent discovery.api.test_mature_discovery intelligence.test_connection_management_api intelligence.tests web_research.tests.test_provider_pack
python manage.py makemigrations --check --dry-run
cd mobile
flutter test test/discovery_c5_connected_actions_test.dart test/discovery_mature_screen_test.dart test/intelligence_connection_controls_test.dart
flutter analyze lib/features/discovery lib/features/interoperability test/discovery_c5_connected_actions_test.dart
```

**Non attesté dans la session :** tests Django et Flutter réellement exécutés, compatibilité PostgreSQL et essais réseau avec clés réelles. La PR #522 reste ouverte, sans fusion. La fusion reste conditionnée à la vérification des gates requises. Les appels externes réels ne doivent être testés qu'avec un compte et des frais explicitement autorisés.

**Critère de fermeture fonctionnelle de C5 :** un utilisateur possédant une Connection personnelle configurée peut lancer explicitement la clarification ou la recherche de sources, voir un résultat borné et utile, puis poursuivre Découvrir sans fuite, faux faits, privilèges implicites ni perte de contexte.
