# C4 — Interoperability consommable : première intégration complète par owner

**Date :** 2026-11-01  
**Portée :** PR #522, sans fusion, aucun modèle/migration ajouté.  
**Statut :** livré en code pour le cycle de vie **Intelligence BYO API key** et sa consommation Web/Flutter ; validation d'exécution des tests et services externes non attestée. **Pas de catalogue OAuth générique livré.**

## Pourquoi

C1 constate M7 comme kernel et Z16 comme projection GET, tandis que des domaines comme Intelligence, Payments, Notifications et Accounts possèdent déjà leurs adaptations. C2/C3 fixent les parcours et la présentation. C4 ne doit pas créer une fausse marketplace, ni utiliser les intégrations d'authentification sociale pour accéder à des calendriers/fichiers. La première intégration exploitable choisie s'appuie sur l'existant `intelligence.ProviderConnection`, `IntelligenceRoute`, `ProviderCredential`, `build_runtime_registry` et les adapters déjà présents.

## Propriétaire et catalogue de fournisseurs

**Owner :** Intelligence. **Pas d'API M7 de mutation ni de nouvelle table**.

Fournisseurs explicitement exposés, avec endpoint HTTPS fixe côté serveur, sans URL saisie par l'acteur :

| Offer code | Protocole existant | Capacités | Paramètre requis |
|---|---|---|---|
| `tavily` | `tavily_search` | `web_research` | Clé Tavily |
| `exa` | `exa_search` | `web_research` | Clé Exa |
| `openai` | `openai_compatible` | `text_generate`, `structured_generate`, `embed` | Clé + identifiant modèle |
| `openai_web` | `openai_responses_web` | `web_research` | Clé + identifiant modèle |

Les endpoints de ces offres sont vérifiés contre les spécifications publiques et fixés dans `intelligence/connection_management.py`. Le client n'envoie jamais `base_url`, `priority`, `routes`, `timeout_seconds`, `scope`, `profile_id`, `space_id` ou credential chiffré.

**Références fournisseur (techniques, non secrets) :**
- https://help.tavily.com/articles/4840311948-tavily-search-api
- https://github.com/exa-labs/openapi-spec/blob/master/exa-openapi-spec.yaml
- https://developers.openai.com/api/reference/overview

La présence d'un offer signifie **adapter disponible dans Makolo et clé à apporter**, pas « compte fournisseur déjà connecté ». Les frais et les quotas restent ceux du compte fournisseur de l'utilisateur.

## Contrats HTTP propriétaire (distincts de Z16)

| Scope | Catalogue + création | Détail + mise à jour + retrait |
|---|---|---|
| Profile | `GET/POST /api/v1/me/intelligence/connections/` | `GET/PATCH/DELETE /api/v1/me/intelligence/connections/<uuid>/` |
| Space | `GET/POST /api/v1/organizations/workspaces/<slug>/intelligence/connections/` | `GET/PATCH/DELETE /api/v1/organizations/workspaces/<slug>/intelligence/connections/<uuid>/` |
| Platform | `GET/POST /api/v1/platform/intelligence/connections/` | `GET/PATCH/DELETE /api/v1/platform/intelligence/connections/<uuid>/` |

- `GET` collection = `{"offers":[{"code","label","description","capabilities","requires_model","can_connect"}]}`, sans credential ni endpoint.
- `POST` = `{"provider","name","api_key","model","consent":true}` ; `consent=true` est obligatoire. Création atomique d'une Connection Intelligence, de sa credential chiffrée et de ses routes de capacités allowlistées. Rejet des paramètres inconnus, des doublons de même nom/protocole/endpoint par portée, des valeurs invalides et des protocoles non allowlistés.
- `PATCH` = `{"enabled":true|false}` ou `{"api_key":"..."}` ; réactivation impossible sans clé. Une rotation remet la santé à `unknown`.
- `DELETE` = retire Connection et credential locale, y compris les routes associées. **Ne révoque pas la clé chez le fournisseur externe** ; l'interface l'explique.
- Réponses = uniquement `project_provider_connection` sans secret ; `Cache-Control: private, no-store`.
- `INTELLIGENCE_CREDENTIAL_MASTER_KEY` reste un prérequis opérationnel existant ; si absent, catalogue `can_connect=false` et `POST` refuse avec 503, sans enregistrer la clé.
- Pas de vérification réseau facturable déclenchée simplement par l'ouverture d'un écran ou la création d'une connexion.

## Autorité et confidentialité

- **Profile :** `profile.user == request.user` sur lecture et mutations. Autre Profile => 404.
- **Space :** `space.manage` direct sur le Space courant, réévalué dans la vue et dans les services. `TeamMembership` ou autorité Platform isolée ne suffisent pas. Refus hors portée => 404.
- **Platform :** `platform.manage` obligatoire en API et sur la vue Web. Connexions du seul scope Platform.
- Aucun champ fourni par le client ne choisit la portée ou le propriétaire ; routes HTTP et acteur serveur le fixent.
- Une clé n'est jamais sérialisée, loggée par ces nouveaux chemins ni copiée dans ProfileStore. La connexion est déclarée liée à Makolo et non au compte social.
- L'état `manageable` dans Z16 ne confère jamais un endpoint générique M7 ; les mutations sont documentées exclusivement chez Intelligence.
- Les `Actions` M7, `Extensions` et Webhooks ne deviennent pas une marketplace par cette livraison.

## Parcours Web

- Moi → Connexions : options autorisées, formulaire de connexion avec consentement, statuts et gestion de clés avec CSRF, confirmation du retrait.
- Nous → Connexions : même composant formulaire, contrôlé par Mandate direct `space.manage`.
- Platform → Interopérabilité : affichage et gestion techniques sous `platform.manage`.
- Les formulaires serveur ne reflètent jamais les credentials en réponse ni en message d'erreur, et la lecture partage Z16 avec l'API.

## Parcours Flutter

- **Moi → Connexions :** projection locale `personal.interoperability` maintenue par `SyncEngine` ; le composant propriétaire charge seulement les offers depuis Intelligence, puis exécute `POST/PATCH/DELETE` avec revalidation Z16. Les clés en formulaire ne vont jamais dans Drift/ProfileStore. Panne : dernière observation explicite, aucune réussite locale optimiste.
- **Nous → Connexions :** handoff serveur limité à `space.manage` direct, route `/space/<slug>/connections`, GET Z16 autorisé et revalidation du contexte acteur avant toute gestion. **Online-only** pour cette profondeur C4 ; aucune projection Space stockée dans le ProfileStore personnel. Une perte d'autorité ou changement d'acteur efface immédiatement l'état du composant. Une future cache propriétaire Space doit réutiliser SpaceSync et non un second système.
- Platform demeure Web/API ; l'application personnelle Flutter n'ouvre pas de shell Platform.

## Tests C4 ajoutés (écrits, non exécutés ici)

- API : création atomique, lecture Z16, chiffrement/déchiffrement côté serveur, rotation, disable/enable, retrait, absence de secrets, no-store, refus cross-Profile, Membership ≠ Mandate, Platform ≠ Space, validation stricte, indisponibilité de la clé maître.
- Web : formulaires réels Profile/Space, contrôle de propriété, absence de secrets dans l'HTML et confirmation du retrait.
- Flutter : catalogue vérifié côté serveur, consentement avant soumission, clé présente uniquement dans requête POST du propriétaire, non rendue dans l'écran.
- Test plus vaste E2E avec véritables credentials fournisseur et vérification physique d'une action de recherche/génération : **non exécuté**, dépend d'un environnement explicitement configuré et d'une clé consentie.

## Limitations explicites et suite

- Pas de « connecter Google Drive », « lire Google Calendar » ou autre OAuth : Accounts social login n'accorde aucune de ces permissions.
- Le retrait local de la clé n'invalide pas celle du fournisseur ; l'acteur doit également la révoquer dans sa console fournisseur si nécessaire.
- La capacité de recherche/génération est obtenue par les domaines Makolo qui utilisent déjà `build_runtime_registry` et leur propre Action/context ; C4 n'ajoute **aucune action universelle** `execute` ni exécution facturable depuis une carte Connexions.
- Le health check explicite reste administrable techniquement par Intelligence ; la disponibilité d'une clé nouvellement ajoutée n'est pas garantie sans utilisation/contrôle réel.
- La validation CI et les tests locaux n'ont pas été exécutés à la demande ; **aucune fusion** n'est autorisée à être considérée sûre sur cette seule base.

**Critère de fermeture du lot livré :** un acteur peut, dans une portée autorisée, découvrir un provider compatible, accepter l'usage de sa clé, le relier, voir sa Connection projetée, désactiver/réactiver/rotater/retirer, et retrouver l'état cohérent sur Web et Flutter. L'état réel du fournisseur reste une dépendance externe.
