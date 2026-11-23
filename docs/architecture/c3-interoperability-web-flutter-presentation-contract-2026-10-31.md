# C3 — Contrat commun de présentation Interoperability Web et Flutter

**Statut : C3 implémenté pour les parcours de lecture Z16 ; mutations non couvertes faute de contrats owner.**  
**Branche de travail :** PR #522 ; document vivant, le code courant gagne.

## 1. Problème résolu

Une projection Z16 peut exposer `connected=true` sans prouver qu'une action soit exécutable. Connexions doit distinguer une relation existante, l'autorité effective, l'état du service et une capacité active, sans interpréter localement une permission. Le Web et Flutter partagent le contrat serveur, mais pas leur runtime de navigation et synchronisation.

## 2. Inputs autorisés

| Surface | Source | Filtre de portée | Propriétaire |
|---|---|---|---|
| Web Moi → Connexions | `build_profile_interoperability_payload(actor)` | Profile de l'acteur | Interoperability projection, Intelligence pour les faits |
| Flutter Moi → Connexions | `GET /api/v1/me/interoperability/` → `personal.interoperability` | `context=profile`, `scope=profile`, store isolé | Z16 + SyncEngine |
| Web Nous → Connexions | `build_interoperability_payload(context=space)` | `space.manage` direct sur Espace | Space/Intelligence |
| API Platform | `GET /api/v1/platform/interoperability/` | `platform.manage` | Platform/Intelligence |

Z16 `schema_version=z16.v1` constitue la seule source des propriétés `available`, `connected`, `usable`, `manageable`, `enabled`, `health` et `capabilities`. Le client ne recalcule pas `usable` à partir d'autres attributs.

## 3. Vocabulaire commun et règles de présentation

- Disabled : **Désactivé** — « Cette connexion est désactivée. »
- Health unavailable : **Momentanément indisponible** — « Le service ne répond pas actuellement. »
- Health degraded : **Connecté · disponibilité réduite** (si connecté) — « Le service peut être temporairement limité. »
- Health unknown : **Connecté · état à vérifier** (si connecté) — « La disponibilité doit être vérifiée. »
- Connecté avec `capabilities=[]` : **Relié · aucune capacité active** — « Aucune capacité active n'est exposée. »
- Usable : **Connecté et disponible** — « Cette connexion possède une capacité active. »
- Autres cas : **Disponible/État à vérifier** — « Aucune action n'est disponible depuis cette connexion. »

Ces messages décrivent une observation, jamais une promesse d'exécution ou la validité d'un consentement externe. Web utilise `interoperability.presentation` ; Flutter applique la même grille à la projection locale.

## 4. Niveaux de profondeur

- **N1 :** Moi (ou Nous pour l'Espace). Aucun nouvel onglet principal.
- **N2 :** Connexions, lecture globale et empty state véridique.
- **N3 :** détail de connexion uniquement lorsque sa finalité/permissions publiques sont réellement exposées par l'owner ; ne pas inventer N3 pour un `ProviderConnection` technique.
- **Contextuel :** action propriétaire dans Journey, Resource, Payment, Notification ou autre parcours, et non une interface d'exécution générique.

## 5. États d'expérience

| Condition | Web | Flutter |
|---|---|---|
| Projection valide non vide | rendu serveur des seules données autorisées | rendu du dernier snapshot validé |
| Liste vide valide | message sobre, sans service factice | même vérité et possibilité d'actualiser |
| Chargement initial | cycle HTTP de la page | attente acquisition puis état explicite |
| Réseau absent avec snapshot | requête Web échoue | snapshot lisible, état ancien |
| Réseau absent sans snapshot | erreur Web | indisponibilité locale, pas de spinner infini |
| Erreur d'acquisition | gestion Web standard | message et retry, snapshot préservé |
| Refus owner 403/404 | aucun accès | purge du snapshot concerné via SyncEngine |
| 401 | session Web/Login | récupération session canonique |
| Découverte d'une Action sans lien | libellé informatif | libellé informatif |
| Refresh | nouvelle lecture | SyncEngine, revalidation du propriétaire |
| Changement Profil | nouvelle session/projection | isolation des stores, aucun partage |
| Changement Space/Mandate | lecture serveur filtrée | pas de réutilisation de snapshot Profile |

## 6. Interdictions

Aucun CTA `Connecter`, `Exécuter`, `Déconnecter` ou `Révoquer` sans lien/contrat propriétaire explicite. Aucun endpoint ni callback OAuth construit à partir d'un code provider. Aucun credential, secret, token, URL interne, modèle technique ou diagnostic de latence dans la projection. Aucun changement local optimiste de droit. Aucun nouveau `Connection` persistant parallèle à Intelligence/owner. Aucun transfert automatique de Permission/Mandate entre Profile, Space et Platform.

## 7. Adaptateurs et implémentation

- `interoperability/presentation.py` : messages humains déterministes et sans effet métier.
- `templates/core/personal_connections.html` : statut + explication pour chaque connexion réellement sélectionnée.
- `mobile/lib/features/interoperability/connections_screen.dart` : même explication à partir de la projection stockée ; refresh via SyncEngine ; dernier état connu préservé.
- `mobile/lib/repositories/interoperability_repository.dart` : rejet `schema_version/context` inattendu et filtrage `scope=profile`.
- Aucun nouveau modèle, migration, API de mutation, client HTTP ou moteur de synchronisation.

## 8. Tests ciblés et critères de sortie

1. Mes connexions Web et Flutter affichent des formulations cohérentes pour désactivation, indisponibilité, dégradation, unknown, sans capacité et utilisabilité.
2. Les résultats ne divulguent jamais données d'un autre Profile/Space/Platform, secrets, configuration ou protocole interne.
3. Les Actions ne promettent jamais une exécution sans contrat owner.
4. Empty, erreur, panne réseau et refus explicite demeurent des états différents.
5. L'interface reste utilisable sans catalogue M7 installé ; une liste vide n'est pas une panne.
6. Aucun statut affiché n'est utilisé par le client comme permission de mutation.

## 9. Limitations résiduelles (ne pas déclarer livrées)

- Connexion OAuth/consentement utilisateur et révocation de service : pas de contrat owner générique livré.
- Connexions Space Flutter : à intégrer avec contexte Space local-first et révocation Mandate, sans contamination des projections Profile.
- UI N3 et exécution d'Action : attendre les liens d'owner effectivement publiés.
- Santé de provider ne signifie pas capacité métier vérifiée : conserver la nuance jusqu'à l'action réelle.

**Verdict :** C3 est fermé pour la présentation et la continuité des projections Z16 personnelles existantes. L'interopérabilité de bout en bout pour des services connectables est conditionnelle à des contrats propriétaire supplémentaires ; ne pas assimiler cette dépendance à un simple retard Flutter.
