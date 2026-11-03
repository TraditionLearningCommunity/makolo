# A2 — Interopérabilité personnelle et fermeture mobile ciblée

> **Statut : chantier A2 mobile.** Le runtime courant, les tests et `main` gagnent sur ce document.

## 1. Objet

Ce checkpoint A2 consomme le contrat serveur Z16 pour le **Profil uniquement** et ferme trois défauts mobiles observés sans rouvrir l'architecture A2 :

```text
M7 kernel
→ Z16 contrat serveur
→ A2 Profil mobile
   → Avatar
   → Connexions
```

Le même chantier ferme également :

- le lancement visuellement dupliqué ;
- la vérification anticipée de l'Identifiant Makolo ;
- la proportion du Makolo Mark central.

Aucun contexte Space ou Platform n'est construit ici.

## 2. Contrat Z16 consommé

Source canonique :

```text
GET /api/v1/me/interoperability/
```

Schéma attendu :

```text
z16.v1
context = profile
providers
connections
actions
extensions
webhooks
links
```

Le mobile ne lit ni ORM, ni registries Python, ni Django Admin.

La projection locale est stockée dans le `ProfileStore` existant sous :

```text
personal.interoperability
```

Aucune nouvelle table Drift n'est créée.

Le nouveau sync source réutilise `SyncEngine` et `syncSources`. Launch/resume/reconnect/refresh restent les mécanismes communs de continuité.

## 3. Confidentialité et scopes

Le client n'accepte comme Connections personnelles que les entrées projetées avec :

```text
scope = profile
```

Une entrée Space injectée dans une fixture ou un cache ne devient jamais une Connection personnelle présentée par la feature.

Le mobile ne stocke ni n'affiche :

- credential ;
- secret ;
- clé API ;
- token provider ;
- endpoint interne ;
- configuration provider privée.

Z16 reste propriétaire de la divulgation et de l'autorisation.

## 4. Avatar → Connexions

L'Avatar expose désormais une destination secondaire :

```text
Connexions
```

Ce n'est pas une nouvelle destination principale.

La surface affiche uniquement les faits réellement présents dans Z16 :

- Connections personnelles ;
- providers réellement installés lorsque le runtime en expose ;
- Actions autorisées ;
- Extensions disponibles.

Le runtime Z16 peut légitimement retourner des listes vides. Dans ce cas, l'écran affiche un empty state calme au lieu d'inventer Gmail, Calendar, OpenAI ou une marketplace.

Aucune action de configuration n'est inventée : Z16 expose actuellement l'état des Connections mais ne fournit pas de mutation générique de gestion.

## 5. Local-first

La projection Z16 acquise est une **observation locale persistée** du contrat serveur, jamais une nouvelle vérité métier.

La représentation locale sert à :

- afficher immédiatement un snapshot déjà acquis ;
- préserver la lecture locale lorsque la source distante n'est pas joignable ;
- conserver la dernière observation lors d'un échec de refresh.

L'UI consomme cette représentation locale. Le réseau sert à acquérir une version absente, rafraîchir une observation devenue ancienne et revalider lorsque le contrat l'exige. Availability, freshness, reachability et authority restent distinctes. La fraîcheur et les échecs restent portés par le noyau sync existant.

Aucun deuxième moteur de sync ni second client HTTP n'est introduit.

## 6. Lancement unique

Avant ce checkpoint, le lancement Flutter pouvait enchaîner :

```text
SplashScreen
→ BrandMoment
→ contenu
```

alors que le host Android possède déjà son splash natif.

Le contrat final devient :

```text
Android native splash violet + Mark blanc
→ Flutter SplashScreen visuellement continu
→ minimum 1 seconde depuis le début du lancement
→ attente réelle de l'initialisation si elle dure davantage
→ onboarding ou première surface prête
```

`BrandMoment` n'est plus une seconde étape de lancement.

Le Flutter splash garde le Makolo Mark blanc et applique un très léger mouvement alterné/vertical donnant une impression de marche. Avec Reduce Motion, le Mark reste statique.

La suppression porte sur la duplication de phase, pas sur l'ajout d'un délai masquant le problème.

## 7. Identifiant Makolo pendant la saisie

Le client applique d'abord la validation locale canonique :

- normalisation lowercase et retrait d'un `@` initial ;
- 3 à 30 caractères ;
- lettres minuscules, chiffres, point, tiret, underscore ;
- valeurs réservées refusées.

Une valeur localement valide déclenche après **400 ms** de debounce :

```text
GET /api/v1/accounts/auth/identifier/availability/?value=<identifiant>
```

États UI :

```text
idle
checking
available
unavailable
unable_to_check
```

Un compteur de génération et une vérification de la valeur courante empêchent une réponse réseau ancienne d'écraser la réponse de la nouvelle saisie.

Une panne réseau n'est jamais interprétée comme disponibilité.

La vérification anticipée ne remplace pas la validation serveur finale lors de la création du compte.

## 8. E-mail

Aucun pré-check e-mail n'est ajouté.

Le contrat Accounts audité fournit une disponibilité publique pour **l'Identifiant Makolo**, mais pas un endpoint public de disponibilité e-mail. Le mobile ne crée donc aucun mécanisme parallèle pouvant devenir un oracle d'énumération de comptes.

L'e-mail conserve :

- validation locale ;
- validation finale serveur ;
- message d'erreur actionnable après soumission.

## 9. Makolo Mark central

Le cercle central reste à **56 × 56** et la hauteur de navigation reste inchangée.

La taille du Mark passe :

```text
32 → 38
```

soit **+18,75 %**, dans la fourchette demandée, sans agrandir la barre ni le cercle.

## 10. Tests ciblés

Le checkpoint couvre notamment :

- cache/sync de `personal.interoperability` ;
- empty state Connexions ;
- filtrage Profile contre une Connection Space injectée ;
- absence de rendu d'un secret injecté ;
- Actions autorisées et Extensions ;
- entrée Avatar Connexions ;
- taille 38 du Mark central ;
- splash minimum 1 seconde ;
- absence de seconde phase `BrandMoment` ;
- debounce Identifiant Makolo ;
- réponse réseau obsolète ignorée ;
- erreur réseau distincte de disponibilité ;
- identifiant localement invalide sans requête ;
- e-mail sans requête de disponibilité.

## 11. Non-objectifs

Ce chantier ne construit pas :

- l'interopérabilité Space ;
- l'interopérabilité Platform ;
- une marketplace ;
- de faux providers ;
- un OAuth générique ;
- une mutation de Connection absente de Z16 ;
- une vérification publique de disponibilité e-mail ;
- un nouveau moteur local-first ;
- un redesign du shell ou de l'inscription.

## 12. Gate de fermeture

Avant merge :

1. formatter/analyze Flutter ;
2. tests ciblés ;
3. Mobile CI ;
4. Android build/APK si déclenché par les workflows courants ;
5. dépendance Accounts/Identifiant Makolo intégrée sur `main` ;
6. réconciliation de la branche sur ce `main` ;
7. CI verte.

Après merge :

- vérifier le HEAD final `main` ;
- générer l'APK depuis ce HEAD final ;
- vérifier sur appareil réel : cold start, splash unique, signup/availability, réseau lent/absent, navigation authentifiée, Mark central, Avatar → Connexions.

La fermeture a ensuite été réconciliée avec `main@f3879e04` après l’intégration de Web Search #360 ; ce changement n’ajoute aucune responsabilité mobile et sert uniquement à garantir les gates sur le `main` réellement courant.


## 13. Réconciliation #522 — 31 octobre 2026

**Constat vérifié dans le runtime de #522 :** la vue Flutter consomme `GET /api/v1/me/interoperability/` et retient une projection `personal.interoperability` par Profil. Le serveur sélectionne les `ProviderConnection` Intelligence personnelles via `profile__user`, sans divulguer les credentials, les routes internes ni les configurations techniques. `z16.v1` expose des faits en lecture seule, pas une opération générale de création ou d'autorisation d'un service externe.

La distinction reste importante :

- **M7** : primitives de Connections, Actions, Providers et Extensions ;
- **Z16** : projection de ce que le runtime a effectivement configuré pour ce Profil ;
- **Flutter** : présentation et synchronisation de ces faits, sans devenir propriétaire des autorisations ;
- **services réellement connectables** : nécessitent un parcours métier propriétaire, un provider concret configuré et une mutation autorisée explicitement côté serveur.

Une liste vide de Z16 ne prouve pas une panne Flutter ; elle peut être la représentation exacte d'un Profil sans Connection personnelle et sans catalogue M7 runtime installé.

### Fermeture mobile ciblée portée par #522

L'écran Connexions dispose d'une actualisation volontaire (bouton et geste de rafraîchissement), via le `SyncEngine` existant. En cas d'échec, le snapshot local reste visible avec un message de fraîcheur ; lorsque aucun snapshot n'existe et que l'acquisition échoue, un état d'erreur explicite remplace le chargement illimité. Le rendu des capacités distingue la disponibilité déclarée de toute possibilité d'exécution directe : il n'existe toujours pas de CTA fictif.

### Ce qui reste nécessaire pour une connexion personnelle utilisable de bout en bout

Avant d'ajouter dans Flutter « Connecter », « Autoriser », « Désactiver » ou « Exécuter », le domaine propriétaire du service doit livrer un contrat consommable réel, incluant :

1. un service concret, son identité publique et sa finalité pour l'utilisateur ;
2. un flux d'autorisation ou de configuration valide pour le Profil (consentement, scopes, révocation) ;
3. une opération serveur autorisée, idempotente selon le besoin, et sa représentation de résultat ;
4. des liens/actions allowlistés dans un contrat public dont Flutter peut suivre la destination, sans déduire d'URL ou de permission ;
5. les tests d'isolation entre Profils, de révocation, d'échec/récupération, de confidentialité et de compatibilité local-first.

Les credentials restent exclusivement dans leur coffre propriétaire ; aucun secret ne rejoint le `ProfileStore` ni la projection. Les Connections Space et Platform conservent leur autorité spécifique. **Ne pas qualifier la connexion libre-service de livrée tant que ce contrat serveur n'existe pas réellement.**

La validation Android et les gates Flutter/CI de #522 restent obligatoires avant toute fusion.
