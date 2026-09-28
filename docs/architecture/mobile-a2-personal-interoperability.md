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

La projection Z16 est une **copie locale**, jamais une vérité métier.

Le cache sert à :

- afficher immédiatement un snapshot déjà acquis ;
- préserver la lecture hors ligne ;
- conserver la dernière projection lors d'un échec de refresh.

La fraîcheur et les échecs restent portés par le noyau sync existant.

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
