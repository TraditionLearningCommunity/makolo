# Makolo Mobile — Phase 0 / handoff Flutter

> Audit réconcilié le 19 septembre 2026 sur `main@3f9afc129a7bc97de2ce95003fe194e65756ed6c`.
> La PR #234 M8 est mergée ; ses cinq repères personnels sont donc désormais un contrat livré à préserver.

## Décision

Le client Flutter vit dans `mobile/` du dépôt unique `TraditionLearningCommunity/makolo`. Il reste un client du backend canonique Makolo.

## Collision audit

Le travail M8 est désormais intégré à `main`. Phase 0 reste bornée à `mobile/`, ce document et la CI mobile : aucune reprise des templates, selectors ou vérités web.

## Backend déjà disponible

Le runtime courant possède Django REST Framework et SimpleJWT.

Authentification :
- JWT Bearer par défaut pour l'API ;
- SessionAuthentication reste disponible pour le web ;
- access token 15 min ;
- refresh token 7 jours ;
- rotation + blacklist après rotation ;
- logout serveur avec blacklist du refresh token.

Endpoints vérifiés :
- `GET /api/v1/health/`
- `GET /api/v1/readiness/`
- `POST /api/v1/accounts/auth/register/`
- `POST /api/v1/accounts/auth/login/`
- `POST /api/v1/accounts/auth/refresh/`
- `POST /api/v1/accounts/auth/logout/`
- `GET /api/v1/accounts/auth/me/`
- `PATCH /api/v1/accounts/auth/profile/update/`
- `GET /api/v1/discovery/items/`
- `GET /api/v1/discovery/map/`
- `GET /api/v1/discovery/for-you/`
- `GET|POST /api/v1/discovery/bookmarks/`
- `GET /api/v1/events/discover/`

Des préfixes API existent aussi pour organizations, events, tickets, payments, notifications, conversations, questionnaires, preparation, trust, scanner, analytics, partners, CRM, automation, promotions, loyalty, operations, discovery, social, goals, growth et spatiotemporal. Ils doivent être audités endpoint par endpoint avant consommation mobile.

## Gaps à ne pas masquer côté Flutter

Le routeur principal ne monte pas encore d'API mobile complète pour plusieurs capacités nécessaires à A1, notamment Journey, Activity générique, Access, Capacity, Commerce générique, Personal Assets/Library, Dossier/Objectives et les projections personnelles Maintenant / En cours.

Flutter ne doit donc pas lire des templates HTML ni réimplémenter ces vérités. Les API manquantes devront être exposées côté Django à partir des domaines/selectors/services propriétaires.

## Sécurité

- réutiliser le contrat JWT existant ;
- refresh token en secure storage natif à A1 ;
- aucun token/secret/QR complet dans les logs ;
- biométrie = protection locale, jamais autorité serveur ;
- aucune autorité déduite de l'UI ;
- CORS n'est pas requis pour les clients natifs ; ne l'ajouter que si un vrai besoin Flutter Web cross-origin apparaît.

## Tests et CI

Phase 0 : format, analyse statique, widget smoke test.

La CI Flutter est indépendante et filtrée par `mobile/**`. Les jobs PostgreSQL backend ne doivent pas être déclenchés par un changement purement mobile. PostgreSQL reste requis lorsque le backend/persistance/concurrence est réellement modifié.

## Rendu

Après génération des hôtes natifs avec les identifiants approuvés :
- Android : émulateur ou téléphone réel + hot reload ;
- iOS : simulateur/appareil sur macOS/Xcode ;
- CI : tests puis artefacts APK/AAB lorsque ces hôtes seront versionnés.

## Gate Phase 0

- dossier `mobile/` présent ;
- navigation canonique Maintenant · Découvrir · Makolo · En cours · Moi ;
- inventaire API/auth/gaps documenté ;
- aucune vérité métier dupliquée ;
- aucune URL/secrets/identifiants store inventés ;
- tests de fondation ;
- CI mobile isolée ;
- pas de migration.
