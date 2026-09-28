# Makolo Mobile — Bloc G
## Mobile Mature, Hardening & Release Kernel

**Statut : CONCEPTION FERMÉE — release conditionnée par les identités/configurations réelles**  
**Date : 2026-09-28**  
**Dépôt : TraditionLearningCommunity/makolo**  
**Base de clôture : main @ 32a3bd5c53356853be8c6e4c995042501fe6365a**  
**Branche de consolidation : docs/mobile-bloc-e-final-closure**

---

# 1. Objet

Le Bloc G ferme la conception de la dernière couche du programme Mobile après A–F :

> **rendre le client installé durablement exploitable, observable, sécurisé, performant et publiable sans inventer les identités ni la production qui n'existent pas encore.**

Il correspond au jalon A6 — Mobile Mature & Release.

G ne refait ni :

- le Design System ;
- le noyau local-first ;
- la synchronisation ;
- les fichiers/médias ;
- les capacités natives ;
- les profondeurs métier ;
- l'autorité offline.

Il vérifie que toutes ces couches peuvent être livrées comme un produit mobile réel.

---

# 2. État runtime vérifié à la clôture

Sur `main @ 32a3bd5c53356853be8c6e4c995042501fe6365a` :

- Flutter est piné à 3.47.3 / Dart 3.13.x ;
- l'application Android existe sous `mobile/android/` ;
- l'identité Android actuelle est `com.makolo` ;
- le `minSdk` est au moins 24 ;
- le build Android de développement utilise JDK 21 pour les plugins actuels ;
- le bytecode application reste Java/Kotlin 17 ;
- le build `release` Android n'a **pas** de signing production : la configuration actuelle retombe volontairement sur le debug signing ;
- aucun host iOS n'existe ;
- aucun bundle identifier, signing team, provisioning profile, App Group ou entitlement iOS n'est canonique ;
- Firebase est présent comme dépendance mais aucune identité/configuration provider ne doit être supposée ;
- `SentryCrashReporter` existe derrière une abstraction mais aucun DSN n'est fabriqué ;
- `CrashReporter` et `Diagnostics` disposent d'une implémentation no-op ;
- la CI mobile est impact-based ;
- `Mobile Android Build` ne construit aujourd'hui qu'un APK debug ;
- le workflow APK manuel reste un checkpoint bêta/test, pas une publication store.

Conclusion :

> **G ferme les exigences de maturité et de release ; il ne déclare pas Makolo publié en store ni prêt production tant que les identités, secrets, comptes et gates externes ne sont pas réellement disponibles.**

---

# 3. Principe de fermeture

Une release mobile Makolo est acceptable seulement si les quatre niveaux suivants sont vrais simultanément :

1. **Produit** — les surfaces utiles sont cohérentes et les anti-features restent absentes ;
2. **Données** — migrations, stockage, sync et recovery préservent l'information ;
3. **Sécurité** — secrets, autorité et données privées restent protégés ;
4. **Distribution** — le binaire est signé, identifiable, testable et traçable sur la plateforme réelle.

Un build qui compile ne suffit pas.

---

# 4. Device lifecycle

Le mobile doit distinguer :

- installation technique ;
- session authentifiée ;
- Profile courant ;
- éventuel device enregistré auprès d'un owner ;
- push token ;
- délégation F éventuelle.

Ces objets ne sont pas interchangeables.

Une future registration device serveur n'est ajoutée que lorsqu'un besoin réel l'exige, par exemple :

- révocation d'un appareil ;
- push ciblé ;
- délégation F liée à un device ;
- inventaire de sessions/installations ;
- sécurité renforcée.

G interdit de créer un modèle `Device` uniquement pour satisfaire une architecture théorique.

---

# 5. Déconnexion, retrait d'appareil et suppression de compte

Trois opérations restent distinctes.

## Logout

- retire les credentials actifs ;
- ne supprime pas silencieusement drafts/outbox/fichiers privés utiles ;
- protège l'accès local après perte de session.

## Retrait d'un appareil

Si une capacité serveur de révocation device existe un jour :

- elle invalide les artefacts liés à cet appareil ;
- elle ne supprime pas l'historique métier ;
- elle doit traiter push token, délégations F et autres capacités liées.

## Suppression de compte

Elle suit exclusivement le contrat serveur canonique.

Le client ne tente pas de reproduire l'anonymisation ou les règles de conservation localement.

---

# 6. Multi-Profile

Le noyau local a déjà posé l'isolation par Profile.

G exige avant activation d'une UX multi-Profile complète :

- sélection explicite du Profile ;
- séparation des DB/snapshots/drafts/fichiers selon la stratégie installée ;
- aucune fuite dans les widgets, notifications ou caches ;
- changement atomique de contexte ;
- outbox visible pour le bon Profile ;
- logout/re-auth sans suppression accidentelle du travail d'un autre Profile.

Si le produit ne retient pas encore cette UX, G n'oblige pas à l'exposer.

---

# 7. Secure storage et secrets

Secure storage reste réservé aux petits secrets et credentials techniques.

Ne vont pas dans Drift ordinaire :

- JWT ;
- refresh token ;
- secrets de délégation F ;
- clés privées éventuelles ;
- AccessCredential sensible si la politique owner ne le permet pas.

Ne vont pas dans logs/crash reports :

- Authorization ;
- password ;
- token ;
- secret ;
- credential ;
- QR payload ;
- document privé ;
- chemin local révélateur ;
- PII inutile.

Biométrie peut protéger l'accès local à un secret ; elle ne remplace jamais l'autorisation serveur.

---

# 8. Sauvegarde OS et restauration

La stratégie actuelle Android évite la restauration aveugle des données applicatives sensibles.

G fixe le principe :

> **une restauration OS ne doit jamais ressusciter une session, une délégation, une outbox ou un secret comme s'ils étaient encore valides.**

Toute activation future de backup doit classer explicitement :

- reconstructible ;
- privé durable ;
- secret ;
- pending unique ;
- cache ;
- préférence.

Outbox/drafts irremplaçables ne doivent jamais être traités comme cache.

---

# 9. Migrations locales

Avant release :

- toute migration Drift est testée depuis au moins la dernière version publiée supportée ;
- un upgrade avec outbox non vide est testé ;
- un upgrade avec drafts est testé ;
- un crash au milieu de la migration est traité selon les garanties de la couche locale ;
- aucune migration destructive ne supprime silencieusement du travail non synchronisé.

Si aucune migration n'est nécessaire, ne pas en créer artificiellement.

---

# 10. Faible stockage

Makolo doit rester utilisable lorsque le stockage devient contraint.

Ordre de priorité :

1. secrets et metadata nécessaires à la sécurité ;
2. outbox/drafts non remplaçables ;
3. fichiers privés explicitement gardés offline ;
4. snapshots utiles ;
5. médias/cartes reconstructibles ;
6. caches temporaires.

Le nettoyage automatique cible d'abord le reconstructible.

Il ne purge jamais une outbox ou un draft parce qu'un cache est volumineux.

---

# 11. Performance

G impose des budgets mesurables, mais ne fige pas de nombres arbitraires sans benchmark réel.

À mesurer sur appareils représentatifs :

- cold start ;
- warm start ;
- temps jusqu'au premier contenu utile local ;
- navigation N1/N2 ;
- scroll grands jeux de données ;
- ouverture PDF/image/vidéo ;
- map rendering ;
- capture/caméra ;
- scanner ;
- sync après reconnexion ;
- mémoire ;
- taille DB/cache ;
- consommation batterie des tâches background.

La correction vise la cause, pas la suppression d'une fonctionnalité ou d'un test.

---

# 12. Réseau et batterie

Le mobile ne doit pas maintenir du realtime permanent sans besoin owner démontré.

G exige :

- refresh owner-scoped ;
- coalescing des refreshs lorsque possible ;
- pas de polling agressif en arrière-plan ;
- backoff technique pour lectures/retries sûrs ;
- mutations selon leurs contrats B/E/F ;
- respect des fenêtres OS de background.

Push reste un signal.

---

# 13. Observabilité

L'observabilité doit répondre à :

- l'app démarre-t-elle ?
- les migrations réussissent-elles ?
- les sync échouent-elles ?
- quelle famille d'API échoue ?
- quels crashes sont récurrents ?
- quelles capacités natives échouent par plateforme/version ?

Elle ne doit pas devenir un flux de données privées.

Événements/diagnostics doivent privilégier :

- code d'erreur ;
- type d'opération ;
- source technique ;
- version app ;
- version OS ;
- durée ;
- état de connectivité approximatif ;
- identifiants non sensibles seulement si nécessaires et autorisés.

Pas de payload métier brut par défaut.

---

# 14. Crash reporting

`CrashReporter` reste l'abstraction.

Un provider concret n'est activé que lorsque :

- son environnement est décidé ;
- ses secrets/DSN sont configurés hors code ;
- sa politique de collecte est validée ;
- les filtres PII/secrets sont testés ;
- le consentement applicable est respecté.

Le fait que `sentry_flutter` soit dans `pubspec.yaml` ne signifie pas qu'une production Sentry existe.

---

# 15. Analytics produit

G n'introduit pas de tracking d'engagement générique.

Les métriques centrales restent liées à l'action réelle :

- progression utile ;
- reprise d'une démarche ;
- action préparée/confirmée ;
- temps économisé lorsque démontrable ;
- erreurs bloquantes ;
- succès d'un parcours réel.

Pas de watch time, streak, scroll infini artificiel ou vanity metrics comme objectif produit.

Toute analytics respecte divulgation minimale et confidentialité.

---

# 16. Logs

En release :

- pas de `print` verbeux avec payloads ;
- pas de logs secrets ;
- pas de dump HTTP intégral ;
- pas de chemin privé complet ;
- pas de QR/credential ;
- pas de document.

Les logs techniques doivent être bornés et exploitables.

---

# 17. Sécurité applicative

Checklist minimale :

- tokens uniquement secure storage ;
- refresh single-flight ;
- TLS en production réelle ;
- aucune URL de production inventée ;
- aucun cleartext production ;
- deep links revalidés ;
- fichiers privés hors cache public ;
- screenshots/screen recording sensibles évalués selon feature réelle ;
- clipboard utilisé avec prudence pour secrets ;
- secrets non embarqués dans Dart/assets ;
- aucune clé privée serveur dans l'app ;
- permissions OS minimales et contextuelles ;
- données de démo distinctes des données réelles.

---

# 18. Android release

Le runtime actuel n'a pas de signing production.

G fixe la séquence :

    identité Android canonique
    → keystore release créé hors dépôt
    → credentials CI sécurisés
    → build release signé
    → versionCode/versionName gouvernés
    → tests release
    → artifact vérifié
    → canal bêta
    → store lorsque compte et fiche sont prêts

Le keystore, mots de passe et credentials de store ne sont jamais commités.

Le fallback debug signing actuel est acceptable pour validation locale, jamais comme preuve de release production.

---

# 19. Android app identity

L'identité actuelle `com.makolo` est utilisée par le host Android présent.

Toute décision de changement d'applicationId avant publication doit être explicite : après publication, cette identité devient coûteuse à changer.

G ne renomme pas l'applicationId sans décision officielle.

---

# 20. iOS

Aucun host iOS n'existe sur le runtime audité.

Donc G ne peut pas déclarer :

- build iOS vert ;
- bundle identifier ;
- Team ID ;
- provisioning ;
- App Store Connect app ;
- Associated Domains ;
- Push entitlement ;
- App Group ;
- Live Activity entitlement.

Séquence iOS correcte lorsqu'elle est décidée :

    identité officielle
    → host Flutter iOS
    → signing team
    → capabilities strictement nécessaires
    → build simulator/device
    → tests
    → archive
    → TestFlight
    → App Store

Aucun identifiant ne doit être inventé pour « préparer » le dépôt.

---

# 21. Push production

Firebase packages existent, mais G distingue dépendance et service configuré.

Avant activation réelle :

- provider confirmé ;
- projet/app réellement créé ;
- credentials hors dépôt ;
- configuration Android/iOS réelle ;
- token registration owner API démontrée ;
- rotation/revocation ;
- permissions utilisateur ;
- notification routing ;
- tests foreground/background/terminated.

Si ces éléments ne sont pas disponibles, Push reste une capacité prête à être branchée, pas une promesse production.

---

# 22. Maps production

MapLibre est un renderer.

G n'autorise toujours aucun serveur de tuiles public codé en dur par commodité.

Avant release d'une expérience Maps :

- provider/style réellement choisi ;
- droits d'usage vérifiés ;
- attribution correcte ;
- clé éventuelle protégée selon le modèle du provider ;
- offline policy vérifiée ;
- coûts/quotas compris ;
- fallback sans carte si service indisponible lorsque le parcours le permet.

Geography métier reste serveur.

---

# 23. Universal Links / App Links

Les entrées structurées D existent côté application.

La validation production demande ensuite :

- domaine officiel ;
- fichiers d'association correctement servis ;
- Android intent filters ;
- iOS Associated Domains après création du host ;
- tests de possession du domaine ;
- fallback web ou app cohérent.

Une URL technique de bêta ne devient pas automatiquement domaine canonique.

---

# 24. Permissions OS

Avant release, chaque permission doit avoir :

- une feature propriétaire ;
- un déclencheur contextuel ;
- une explication utilisateur ;
- un comportement refusé ;
- un comportement « ne plus demander » ;
- un test plateforme.

Aucune rafale de permissions au premier lancement.

---

# 25. Accessibilité

G impose au minimum :

- tailles tactiles ;
- semantics/lecteur d'écran ;
- text scaling ;
- contraste ;
- absence de dépendance couleur seule ;
- focus lorsque pertinent ;
- Reduce Motion ;
- back gesture ;
- clavier adapté aux Forms.

Les tests visuels ne remplacent pas l'accessibilité fonctionnelle.

---

# 26. Localisation et langues

Aucune promesse de localisation multilingue n'est déclarée tant que le produit n'a pas choisi son périmètre.

Avant ajout de langues :

- extraire les chaînes de manière cohérente ;
- préserver Product Language ;
- tester longueur/RTL si applicable ;
- ne pas traduire les concepts canoniques en termes métier incorrects.

G ne force pas un chantier i18n spéculatif.

---

# 27. Versioning

La version actuelle du package mobile est pré-release.

Avant canal bêta externe puis store, définir explicitement :

- politique `versionName` ;
- politique `versionCode`/build number ;
- compatibilité API minimale ;
- stratégie de migration locale ;
- support des versions anciennes ;
- mécanisme de blocage uniquement si réellement nécessaire.

Le client ne doit pas casser silencieusement sur un `schema_version` inconnu.

---

# 28. Compatibilité API

Les parsers doivent :

- accepter l'évolution additive prévue ;
- rejeter proprement les contrats incompatibles ;
- ne pas inventer des valeurs métier manquantes ;
- préserver `unknown != false != absent` ;
- guider l'utilisateur vers update seulement si réellement nécessaire.

Pas de couplage mobile à un SHA serveur exact en production.

---

# 29. Feature rollout

Une capacité risquée peut être activée progressivement si le backend possède déjà un mécanisme canonique approprié.

G n'invente pas un système global de feature flags uniquement pour le mobile.

Le rollout ne doit pas contourner Permission/Mandate/Access.

---

# 30. Beta

PythonAnywhere reste un environnement temporaire test/bêta tant que les docs officielles n'en décident pas autrement.

Une bêta mobile couvre au minimum :

- visiteur ;
- création/connexion/session ;
- utilisateur authentifié ;
- Maintenant/Découvrir/En cours/Moi/Mark ;
- action personnelle ;
- action au nom d'un Espace si la surface mobile existe réellement ;
- Permission/Mandate ;
- Activity/Occurrence ;
- Journey ;
- Access ;
- Capacity ;
- domaines touchés ;
- online → offline → online ;
- kill/restart ;
- notification/deep link si configuré ;
- absence de 500.

---

# 31. Données de test

Les données de démonstration restent séparées des données réelles.

Avant distribution à des testeurs externes :

- aucun compte partagé avec mot de passe réel dans docs/code ;
- aucun token préchargé ;
- aucun document privé réel dans fixtures ;
- procédure de reset claire ;
- environnement identifiable comme test/bêta.

---

# 32. CI

Le principe impact-based actuel est conservé.

Gates :

## Docs-only mobile

- validation documentaire/CI pertinente.

## Dart/application

- `dart format` ;
- `flutter analyze` ;
- codegen policy ;
- tests ciblés avec fallback complet.

## Drift/local core

- tests DB/migrations ;
- sync/outbox concernés.

## Native/dependencies

- Android debug build au minimum ;
- tests platform concernés.

## Release

Lorsqu'un signing réel existe :

- build release signé ;
- artifact inspection ;
- smoke test release.

## iOS

Seulement lorsqu'un host et une identité iOS canoniques existent, sur runner approprié.

---

# 33. Tests de release

Avant chaque canal de distribution :

- fresh install ;
- upgrade depuis version précédente supportée ;
- login/logout ;
- session expirée ;
- first launch offline ;
- normal launch offline ;
- outbox pending ;
- crash recovery ;
- low storage ;
- permission denied ;
- background/resume ;
- deep link ;
- partage entrant ;
- fichiers ;
- carte si activée ;
- scanner connecté ;
- F offline si réellement implémenté ;
- suppression de compte ;
- changement de Profile si exposé.

---

# 34. Dependency policy

Aucune dépendance n'est ajoutée parce qu'elle est populaire.

Avant ajout :

- feature owner ;
- bénéfice concret ;
- maintenance ;
- licence ;
- taille binaire ;
- impact natif ;
- sécurité ;
- alternatives SDK ;
- support des plateformes retenues.

Les packages installés mais non configurés restent derrière leurs abstractions et ne doivent pas forcer une configuration fictive.

---

# 35. Supply chain

G exige :

- lockfile commité ;
- versions revues ;
- Actions pinées comme le dépôt le fait déjà ;
- secrets GitHub Actions hors YAML ;
- pas de téléchargement/exécution arbitraire non vérifié ;
- revue des permissions de workflows ;
- dépendances natives testées après upgrade.

Les upgrades majeurs ne sont pas mélangés à une release critique sans raison.

---

# 36. Builds reproductibles

Un artifact release doit être traçable vers :

- commit ;
- version ;
- configuration d'environnement non secrète ;
- toolchain ;
- résultat CI.

Les secrets ne font pas partie du manifest public.

G ne promet pas un bit-for-bit reproducible build tant que le toolchain complet ne le garantit pas ; il exige la traçabilité.

---

# 37. Rollback

Le mobile ne peut pas être rollbacké instantanément comme un serveur déjà installé.

Donc :

- migrations locales doivent être prudentes ;
- API doit tolérer des clients plus anciens pendant la fenêtre de support ;
- backend ne retire pas brutalement un champ consommé ;
- feature critique doit pouvoir être neutralisée côté owner lorsqu'un mécanisme canonique existe ;
- une release cassée déclenche une version corrective, pas une mutation destructive des données locales.

---

# 38. Incident mobile

Un incident doit permettre de répondre :

- quelle version ;
- quelle plateforme/OS ;
- quel parcours ;
- quel owner ;
- online/offline ;
- mutation pending ou confirmée ;
- impact données ;
- possibilité de reproduction.

Ne jamais demander à un utilisateur d'envoyer un token, QR secret ou document privé pour diagnostiquer.

---

# 39. Privacy review

Avant release, revoir :

- données Drift ;
- fichiers privés ;
- caches ;
- logs ;
- analytics ;
- crash reports ;
- push payloads ;
- widgets ;
- share sheet ;
- clipboard ;
- screenshots éventuels ;
- sauvegarde OS ;
- suppression de compte.

La divulgation minimale s'applique aussi aux surfaces système.

---

# 40. Store metadata

G ne rédige pas comme vérité des éléments store qui dépendent de décisions non prises.

À préparer uniquement lorsque les comptes existent :

- nom officiel ;
- description ;
- screenshots ;
- privacy disclosures ;
- catégorie ;
- âge ;
- contact/support ;
- URL de politique ;
- Data Safety / App Privacy ;
- notes de review.

Les déclarations doivent correspondre au binaire réel.

---

# 41. Critères de go/no-go release

Une release externe est **NO-GO** si l'un de ces éléments est faux :

- CI requise verte ;
- migrations sûres ;
- secrets absents du dépôt ;
- configuration d'environnement réelle ;
- erreurs critiques connues non résolues ;
- auth/recovery testés ;
- owner actions sensibles revalidées ;
- confidentialité revue ;
- signing réel pour le canal visé ;
- identité plateforme réelle ;
- procédure de rollback/correctif comprise.

G ne transforme pas « presque prêt » en « production ».

---

# 42. Anti-features

G interdit :

- signing debug présenté comme production ;
- faux bundle id iOS ;
- faux DSN ;
- faux Firebase project ;
- clé Maps inventée ;
- secrets dans `--dart-define` commité ou logs ;
- analytics d'engagement générique ;
- permissions au lancement sans besoin ;
- purge de drafts/outbox pour gagner de l'espace ;
- retry aveugle de mutation ;
- forcer une update pour masquer une incompatibilité évitable ;
- Store release avec CI rouge ;
- affaiblir un test pour livrer.

---

# 43. Décisions figées

1. G ferme la maturité/release, pas les domaines métier.
2. Un build debug vert n'est pas une release.
3. Android production signing reste à configurer réellement.
4. Aucun host/identity iOS n'est inventé.
5. Firebase/Sentry installés ne signifient pas providers configurés.
6. Observabilité reste privacy-safe.
7. Outbox/drafts ont priorité sur les caches en faible stockage.
8. Le device n'est pas une autorité métier.
9. Biométrie protège localement ; elle n'accorde rien.
10. Multi-Profile n'est exposé que si l'isolation complète est démontrée.
11. CI reste impact-based avec fallback sûr.
12. API et migrations doivent tolérer la réalité des upgrades mobiles.
13. Les stores exigent des identités et comptes réels.
14. PythonAnywhere n'est pas présenté comme production finale.
15. Aucun secret, provider ou cible production n'est inventé.

---

# 44. Critères de sortie de la conception

Le Bloc G est fermé comme contrat de conception lorsque :

- device lifecycle est distingué de la session/Profile ;
- sécurité locale et backup sont fixés ;
- migrations/low storage sont traités ;
- performance/batterie sont mesurables ;
- observabilité et privacy sont bornées ;
- Android release path est explicite sans faux signing ;
- iOS reste honnêtement non configuré ;
- push/maps/deep links exigent leurs vraies configurations ;
- beta/release gates sont définis ;
- rollback mobile est prévu ;
- aucune identité ou production fictive n'est introduite.

---

# 45. Formule finale

> **Makolo Mobile est mature quand il peut avancer avec la personne sans perdre son travail, sans déplacer l'autorité, sans exposer ses données et sans mentir sur le niveau de production du binaire.**

G ferme le chemin de conception jusqu'à la distribution réelle. La publication elle-même reste une opération contrôlée, dépendante des comptes, identités, secrets et environnements effectivement décidés.
