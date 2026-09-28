# A2 — Launch & onboarding

> **Statut : branche empilée de travail**
>
> **Branche :** `mobile/a2-launch-onboarding`
>
> **Base A1 observée :** `mobile/a1-installed-makolo-core@2cc0d88aa917f91add69da03785a73fc2dab5aed`
>
> **Intégration :** STACKED ON A1 — DO NOT MERGE — RECONCILIATION REQUIRED AFTER A1 MERGES TO MAIN.

## 1. Frontières

Le runtime réconcilié conserve deux responsabilités distinctes :

1. **lancement visuellement continu** : splash natif puis premier frame Flutter avec le même fond/Mark, sans seconde phase de marque concurrente ;
2. **onboarding** : première utilisation de cette installation.

Aucune de ces couches ne possède une vérité métier.

## 2. Splash natif

Le host Android A1 est conservé.

Le lancement utilise :

- fond Makolo Indigo `#5232DB` ;
- Makolo Mark canonique blanc centré ;
- aucun texte ;
- aucun spinner ;
- aucune attente artificielle ;
- aucun média réseau.

Le splash Flutter technique reprend le même fond et le même Mark afin de réduire le risque de flash entre la fenêtre native et le premier frame Flutter.

## 3. Animation de lancement

Le retour appareil réel a montré qu'un `SplashScreen` suivi d'un `BrandMoment` distinct produit l'impression de deux splash screens.

Le runtime final n'enchaîne donc plus une seconde page de marque. Le premier frame Flutter prolonge directement le splash natif :

~~~text
Mark blanc sur Indigo
→ léger mouvement du Mark évoquant la marche
→ première surface prête
~~~

Le launch gate impose un minimum visuel d'une seconde depuis le début du lancement et attend plus longtemps lorsque l'initialisation réelle n'est pas terminée. Il ne rajoute pas un délai après une initialisation déjà plus longue.

Reduce Motion conserve un Mark blanc statique.

`BrandMoment` peut subsister comme ancien composant source tant qu'aucun nettoyage séparé ne le justifie, mais il n'est plus une étape du lancement.

## 4. Onboarding

Le premier écran reste unique et présente :

> **Découvrir. Préparer. Avancer.**

Les mots **Services**, **Transports** et **Événements** sont uniquement des exemples UX.

Il n'existe aucun carrousel marketing ni tutoriel fonctionnel.

Après cette présentation, aucune permission système n'est demandée sur le runtime A1 actuel : Android ne déclare que `INTERNET` et A1 ne possède pas de capacité push/caméra/localisation qui justifierait une demande initiale.

Caméra, localisation, fichiers/médias et notifications restent donc contextuels à une future capacité réelle.

## 5. Guest et authentification

L'onboarding propose :

- Se connecter ;
- Créer un compte ;
- Continuer sans compte.

Le backend possède déjà `POST /api/v1/accounts/auth/register/`. Le client mobile l'utilise sans inventer de nouvel endpoint.

Un utilisateur non authentifié n'est plus forcé vers Login. Il arrive sur une surface Découvrir bornée et peut naviguer dans le shell ; les surfaces personnelles expliquent leur frontière sans créer de faux Profile ni d'autorité locale.

Les destinations personnelles profondes restent préservées et demandent une authentification sans transformer la route en fausse capacité guest.

## 6. Préférences locales

Le runtime utilise `hasCompletedOnboarding` pour l'onboarding. Le champ historique `lastBrandMomentAt` peut encore exister dans le stockage de préférences pour compatibilité des installations déjà écrites, mais il ne commande plus une seconde phase visuelle de lancement.

Ces préférences sont stockées dans un petit fichier JSON de support applicatif via `path_provider`, déjà présent en A1.

Ils ne sont pas stockés dans Drift, ne deviennent pas une vérité backend et ne nécessitent aucune migration Django ou locale.

## 7. Lifecycle et navigation

Le launch gate se superpose au routeur sans réécrire la destination demandée.

Priorités conservées :

- destination déjà demandée ;
- récupération de session ;
- route personnelle protégée ;
- navigation normale.

Le retour depuis background est géré par le lifecycle A1 et ne recrée pas le launch gate.

Une session expirée continue à préserver la dernière route utile via `SessionRecoveryController`.

## 8. Accessibilité

Le chantier couvre :

- Semantics ;
- ordre de lecture naturel ;
- grands textes via surfaces scrollables ;
- touch targets Material ;
- contraste Indigo/Warm ;
- Reduce Motion ;
- animation non nécessaire à la compréhension.

## 9. Réconciliation future

Fichiers partagés modifiés :

- `mobile/lib/app/makolo_app.dart` ;
- `mobile/lib/app/providers.dart` ;
- `mobile/lib/app/router.dart` ;
- `mobile/lib/features/auth/login_screen.dart` ;
- `mobile/lib/features/splash/splash_screen.dart` ;
- `mobile/lib/network/makolo_api_client.dart` ;
- ressources `mobile/android/app/src/main/res/**`.

La réconciliation post-A1 doit relire ces fichiers contre le `main` réellement fusionné et contre les contrats A2-P0 avant toute intégration finale.

Aucune migration Django. Aucune migration Drift. Aucune nouvelle dépendance.
