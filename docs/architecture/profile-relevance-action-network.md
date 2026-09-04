# Makolo — Programme G : Profil, pertinence & réseau d’action

> **Statut : canonique pour le programme G de Makolo Mature.** Ce document complète [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md), [`mature-program-roadmap.md`](mature-program-roadmap.md), [`strategic-action-roadmap.md`](strategic-action-roadmap.md), [`social-action-network.md`](social-action-network.md) et [`mature-experience-principles.md`](mature-experience-principles.md). Le code, les migrations, les tests et l’état GitHub du `main` courant restent la vérité sur ce qui est effectivement livré.

## 1. Pourquoi G existe

Makolo ne doit pas comprendre un Profil uniquement comme un compte qui s’authentifie, ni comme une page sociale statique. Le Profil devient progressivement un **profil d’action** : une base privée et contrôlée qui permet à Makolo de comprendre ce qui compte pour une personne, ce qu’elle accepte de rendre visible, ce qu’elle demande à Makolo de rechercher et ce que son parcours permet réellement d’établir.

G répond à quatre questions complémentaires :

1. **Qui suis-je et qu’est-ce que je choisis de montrer ?**
2. **Qu’est-ce qui m’intéresse et qu’est-ce que Makolo doit chercher pour moi ?**
3. **Pour quoi puis-je volontairement être sollicité ?**
4. **Qu’est-ce que Makolo peut présenter ou établir à partir de faits réels sans transformer ma vie privée en matière première sociale ?**

Principe produit :

> **Le Profil Makolo ne sert pas seulement à dire qui vous êtes. Il permet à Makolo de comprendre ce qui compte pour vous, ce que vous avez déjà, et ce que vous pouvez faire ensuite.**

G n’est pas un nouveau réseau social, un moteur RH généraliste, un CV builder, un bloc-notes de souhaits ni un nouveau bounded context transversal. Il compose les domaines canoniques déjà présents.

## 2. G n’est pas un bounded context unique

Le préfixe G désigne un **programme de maturation produit**, comme les autres séries de travail Makolo. Il ne signifie pas qu’une app Django `g` ou un agrégat global doit exister.

Les responsabilités restent dans leurs propriétaires naturels :

- `accounts` : identité personnelle, données du Profil, préférences et confidentialité ;
- `topics` : vocabulaire canonique de Topics et déclarations d’Interests ;
- `activities` : classification Activity par Topics et faits d’organisation ;
- `discovery` : exploration, requêtes exécutables, Favoris et Veilles ;
- `objectives` : Dossiers et Projets ;
- `trust` : Proofs et Credentials délivrés ;
- `personal_assets` / Requirements / Readiness : capital d’action, réutilisation et préparation ;
- `organizations` : Espaces et contrats de suivi/identité collective ;
- Notifications / Automation : diffusion et orchestration des changements utiles ;
- Presentation/Sharing : représentations et circulation contrôlée lorsque pertinent.

G ajoute des relations, projections et usages. Il ne doit pas recopier les vérités de ces domaines.

## 3. Les distinctions que G rend canoniques

| Concept | Question | Règle |
|---|---|---|
| **Profile** | Qui suis-je dans Makolo ? | Une personne physique, avec données privées et projection publique contrôlée. |
| **Interest** | Qu’est-ce qui m’intéresse ? | Déclaration explicite vers un `Topic`. Ne pas la déduire silencieusement du comportement. |
| **Follow** | Qui / quelle source veux-je suivre ? | Relation de suivi ; distincte d’un intérêt thématique. |
| **Favorite / Bookmark** | Quel objet précis veux-je garder ? | Sauvegarde d’un objet concret ; ne crée ni Dossier, Journey ni Veille. |
| **Open to / Ouvert à** | Pour quoi puis-je être sollicité ? | Signal volontaire de disponibilité, distinct d’un Interest. |
| **Veille** | Que doit continuer à rechercher Makolo ? | Requête Discovery persistante, structurée et exécutable, privée par défaut. |
| **Dossier** | Quel résultat ai-je décidé de poursuivre ? | Objectif actif ; peut exister avant toute Journey. |
| **Journey / Démarche** | Quelle démarche concrète ai-je commencée ? | Processus d’exécution. |
| **Proof** | Quel fait Makolo peut-il établir ? | Fait atomique de Trust, pas score humain universel. |
| **Credential Trust** | Qu’a délivré explicitement un émetteur ? | Attestation/certification immuable et vérifiable ; distincte de `AccessCredential`. |
| **Passeport Makolo** | Quelle représentation portable puis-je produire à partir de faits contrôlés ? | Projection/export ; jamais nouvelle source de vérité. |

Une même personne peut donc : aimer la technologie, suivre un Space, enregistrer une Activity, être ouverte à intervenir comme mentor, maintenir une Veille de bourses, poursuivre un Dossier d’études et disposer de Credentials vérifiables. Ces faits ne doivent jamais être fusionnés en un seul « profilage » opaque.

## 4. Profil privé et Profil public

Makolo conserve **un seul Profil**. Il n’existe pas de `PrivateProfile` et `PublicProfile` concurrents.

Le Profil public est une **projection** contrôlée du Profil et des faits publics autorisés.

Il peut présenter selon les contrats réellement disponibles :

- nom d’affichage et avatar ;
- bio courte ;
- localisation générale lorsque choisie ;
- liens externes déclarés ;
- Interests explicitement rendus publics ;
- `Open to` explicitement exposés ;
- Activities personnelles publiques ;
- associations publiques légitimes à des Espaces ;
- plus tard, éléments sélectionnés pour le Passeport Makolo.

Il ne doit pas exposer automatiquement :

- email ou téléphone ;
- date de naissance complète ;
- adresse précise ou coordonnées fines ;
- Library / Personal Assets ;
- Dossiers ou Journeys privées ;
- Veilles ;
- Favorites ;
- paiements, commandes ou Access personnels ;
- historique privé ;
- liste privée des Follow ;
- critères sensibles utilisés uniquement pour une action ou une personnalisation privée.

`public_profile` et `searchable` sont deux décisions différentes :

```text
public_profile
= la projection publique existe et peut être consultée selon son contrat

searchable
= le Profile accepte d’être candidat à une découverte/recherche autorisée
```

Être public ne rend pas automatiquement searchable ; être searchable ne doit jamais exposer des champs qui ne sont pas publics ou autorisés pour le cas d’usage.

## 5. Collecte progressive des données

Makolo ne doit pas exiger un Profil exhaustif à la création du compte.

Principe :

> **Demander une information lorsqu’elle devient utile à une action compréhensible, pas simplement parce qu’un champ existe.**

Exemples :

- proposer les Interests pendant Discover lorsque cela améliore réellement les résultats ;
- demander une zone lorsque l’utilisateur souhaite une expérience locale ;
- demander une donnée d’éligibilité lorsqu’un Requirement précis en a besoin ;
- proposer d’enrichir le Passeport lorsque l’utilisateur veut le partager ou l’exporter.

Une donnée optionnelle ne doit pas devenir obligatoire uniquement pour faire progresser un compteur de Profil.

## 6. Interests et Topics

`Topic` est le vocabulaire canonique partagé pour les thèmes réellement transversaux.

`ProfileInterest` représente une déclaration explicite d’un Profile vers un Topic. `ActivityTopic` permet de classer une Activity avec le même vocabulaire.

Principes :

- nouveaux Interests privés par défaut ;
- la personnalisation privée et l’exposition publique sont séparées ;
- un comportement observé peut devenir un signal de recommandation mais ne réécrit pas silencieusement « Mes centres d’intérêt » ;
- Follow, Favorite, recherche et historique ne sont jamais automatiquement convertis en Interests ;
- les verticales ne recréent pas des taxonomies incompatibles si `Topic` couvre déjà le besoin transversal.

## 7. Ouvert à — rendre le réseau réellement bilatéral

`Open to` répond à :

> **Pour quels types de sollicitations cette personne accepte-t-elle d’être potentiellement découverte ou contactée ?**

Exemples : participer, collaborer, bénévolat, mentorat, intervenir, organiser, recevoir certaines opportunités.

`Open to` n’est pas une preuve de compétence et n’est pas un Interest.

```text
Interest : Technologie
Open to  : Intervenir comme mentor
Proof    : A effectivement animé telle activité
```

Cette séparation est essentielle pour le futur moteur bilatéral : une personne ne doit pas devenir « recrutable » simplement parce qu’un comportement privé ou un intérêt thématique a été observé.

## 8. Veille Makolo

Une Veille signifie :

> **« Makolo, continue à rechercher ceci pour moi avec ces critères. »**

Une Veille est une requête Discovery persistante, pas une intention vague.

Elle doit rester :

- privée par propriétaire ;
- structurée et validée ;
- rejouable par le moteur Discovery ;
- active ou en pause ;
- modifiable/supprimable selon son contrat ;
- éventuellement rattachée à un Dossier du même propriétaire ;
- indépendante d’une Journey et sans création automatique de Dossier.

Une Veille vide ne doit pas devenir un bloc-notes :

```text
« penser à apprendre Python » + aucun critère exécutable
≠ Veille Makolo
```

La Veille peut devenir une source explicable de notification future :

> « Cette possibilité correspond à votre Veille “Master informatique 2027”. »

Les critères de Veille peuvent révéler des intentions très sensibles. Ils ne sont jamais projetés sur le Profil public, le Passeport ou le moteur de découverte des personnes sans un futur contrat explicite distinct.

## 9. Trust : Proof, Credential et AccessCredential

G5 stabilise une frontière importante :

- `Proof` : fait atomique établi par Makolo ;
- `Credential` Trust : attestation/certification délivrée par un émetteur métier identifié ;
- `JourneyArtifact` : document individuel/versionné d’une Journey ;
- `AccessCredential` : représentation ou secret d’un droit d’accès.

Un Credential Trust ne devient pas un `Proof` géant et un `AccessCredential` ne devient pas un certificat de parcours.

Le Credential doit conserver son émetteur, son bénéficiaire, sa source canonique, son état et sa révocation. Il ne doit pas copier comme vérités indépendantes nom, email ou téléphone du bénéficiaire lorsque les relations canoniques existent.

## 10. Passeport Makolo

Le **Passeport Makolo** est la représentation portable d’un Profile ou d’un Space construite à partir de faits canoniques et de sélections contrôlées.

Il n’est :

- ni une carte d’identité étatique ;
- ni un CV Word fabriqué librement ;
- ni une Proof unique ;
- ni un Credential délivré après une Activity ;
- ni une nouvelle base de réputation.

La valeur du Passeport vient de la capacité à distinguer ce qui est :

1. **déclaré** par le sujet ;
2. **établi** par Makolo à partir de faits ;
3. **délivré** par un émetteur via Credential.

Versions prévues :

- publique ;
- complète/privée ;
- thématique ;
- personnalisée.

Un export doit être daté et, lorsqu’une vérification est offerte, permettre de constater l’état actuel des éléments vérifiables, notamment une éventuelle révocation.

Le Passeport ne doit pas conclure automatiquement « cette personne est bonne à embaucher ». Il présente les faits, expériences et disponibilités légitimes ; une future pertinence doit rester explicable et distincte de la décision humaine.

## 11. Le réseau Makolo est à deux côtés

Makolo ne doit pas être seulement :

```text
personne → cherche Activity / Opportunity
```

Il doit aussi permettre, avec consentement et disclosure contrôlée :

```text
Space / organisateur → exprime un besoin → trouve des Profiles pertinents → sollicite → action
```

Les cas dépassent le recrutement : participants, collaborateurs, bénévoles, mentors, intervenants, staff, prestataires ou autres contributeurs selon le contexte.

La découverte d’une personne doit s’appuyer d’abord sur des signaux qu’elle a volontairement rendus utilisables :

- `searchable` ;
- `Open to` ;
- informations publiques ;
- Topics/Interests publics lorsque pertinents ;
- Activities publiques ;
- Proofs/Credentials sélectionnés lorsqu’un contrat de projection l’autorise ;
- géographie approximative consentie.

Invariant :

> **Donnée disponible ≠ critère de recherche autorisé.**

Une recherche de personnes ne doit jamais transformer des Veilles, Dossiers, données sensibles ou comportements privés en filtres exposés à un tiers.

## 12. Activation du Profil sans collecte opportuniste

La progression du Profil peut aider l’utilisateur à comprendre ce qui rend Makolo plus utile, mais elle ne doit pas devenir un score de quantité de données personnelles.

La cible G8 est une projection dérivée et contextuelle :

- identité/presentation utile ;
- Interests utiles à Discover ;
- `Open to` utile au réseau bilatéral ;
- éléments utiles au Passeport ;
- étapes proposées seulement lorsqu’un bénéfice est compréhensible.

Une présentation possible est un anneau ou pourcentage autour de l’avatar, mais le contrat produit reste plus important que l’habillage.

Makolo préfère :

> « Ajoutez quelques centres d’intérêt pour améliorer Discover. »

à :

> « Votre profil est incomplet : remplissez encore 8 champs. »

## 13. Personnalisation et notifications utiles

G9 compose des signaux explicites et des états métier existants :

```text
Profile
+ Interests
+ Follow
+ Geography
+ Veilles
+ Dossiers / Journeys
+ Library / Action Memory
+ History
+ Open to
→ Discover / Prepared Start / NextAction / Notifications
```

La personnalisation doit rester explicable.

Exemples :

- « Parce que Technologie fait partie de vos centres d’intérêt. »
- « Parce que vous suivez cet Espace. »
- « Parce que cette possibilité correspond à votre Veille. »
- « Parce que vous avez déjà une partie des éléments nécessaires. »

Le principe d’engagement n’est pas de provoquer un retour artificiel comme un feed social. La donnée de Profil devient utile lorsqu’elle déclenche une action pertinente au bon moment.

Cible forte :

> **Une chose pertinente vient d’apparaître et Makolo peut déjà montrer ce qui est prêt, ce qui manque ou ce qui peut être fait ensuite.**

## 14. Séquence G1 → G9

### G1 — Profile Foundations ✅ intégré

- Profile en sections ;
- collecte progressive ;
- liens sociaux/site web optionnels ;
- confidentialité conservatrice ;
- séparation préparée entre public et searchable ;
- compatibilité des anciens champs sans création automatique de Space.

### G2 — Topics & Interests ✅ intégré

- `Topic` canonique ;
- `ProfileInterest` explicite et privé par défaut ;
- `ActivityTopic` ;
- première raison Discovery explicable ;
- aucun Interest inféré depuis Follow/Favorite/historique.

### G3 — Profil public + Ouvert à ✅ intégré

- projection publique privacy-safe ;
- Interests explicitement publics ;
- `ProfileOpenTo` distinct ;
- `public_profile` distinct de `searchable` ;
- aucune donnée sensible projetée automatiquement.

### G4 — Veille Makolo ✅ intégré

- Veilles privées ;
- critères Discovery structurés/validés ;
- création depuis Discover ;
- replay sans stockage parallèle des résultats ;
- pause/réactivation ;
- lien Dossier optionnel ;
- aucun `Intention`.

### G5 — Credentials / attestations délivrées ✅ intégré

- Credential Trust séparé de Proof et JourneyArtifact ;
- émetteur canonique Profile ou Space selon l’Activity ;
- bénéficiaire et sources relationnels ;
- délivrance/révocation contrôlées ;
- vérification publique réutilisant Trust ;
- préparation de la lecture G6.

### G6 — Passeport Makolo

Construire une projection/export Profile et Space à partir des données autorisées, Activities, Proofs et Credentials, avec variantes publique, complète, thématique et personnalisée. Le Passeport ne devient pas une source de vérité ni un score humain.

### G7 — Réseau bilatéral

Permettre l’expression d’un besoin et la découverte privacy-safe de Profiles pertinents à partir de `searchable`, `Open to` et faits publics autorisés, puis une sollicitation explicite acceptée/refusée avant l’action.

### G8 — Activation progressive du Profil

Construire une complétion dérivée et des prompts contextuels utiles sans rendre des champs optionnels obligatoires ni collecter des données sensibles pour faire progresser un score.

### G9 — Personnalisation croisée & notifications

Composer Interests, Follow, Geography, Veilles, état d’action, capital personnel et signaux publics/privés autorisés pour améliorer Discover, Prepared Start, NextAction et Notifications avec des raisons explicables.

## 15. Dépendances et parallélisme

La séquence de référence est :

```text
G1 ─┐
G2 ─┼──► G3 ─────┐
G5 ─┘            │
                 ├──► G6
G2 ─────► G4     ├──► G7
                 └──► G8

G6 / G7 / G8 consolidés
          ↓
         G9
```

G1/G2/G5 ont pu être menés en parallèle puis consolidés. G3/G4 ont ensuite avancé en parallèle. La prochaine vague peut paralléliser G6/G7/G8 depuis un `main` vert commun ; G9 vient après leur consolidation.

Les branches de travail doivent rester courtes, ciblées et réconciliées avec le `main` réel avant merge. Les audits généraux ne sont pas requis lorsque les contrats concernés sont déjà identifiés.

## 16. Invariants G

1. **Un seul Profile, plusieurs projections ; pas de PrivateProfile/PublicProfile concurrents.**
2. **La collecte de données est progressive et justifiée par un bénéfice compréhensible.**
3. **Interest, Follow, Favorite, Open to, Veille, Dossier et Journey sont des concepts distincts.**
4. **Un signal comportemental n’écrit pas silencieusement un Interest explicite.**
5. **Un Interest utilisé pour personnaliser n’est pas automatiquement public.**
6. **Une Veille est privée et exécutable ; ce n’est ni une note ni une Intention vague.**
7. **Un Dossier peut exister sans Journey ; Veille et Dossier restent indépendants.**
8. **Public Profile et searchable sont deux consentements différents.**
9. **Donnée disponible ne signifie jamais critère de recherche autorisé.**
10. **Proof, Credential Trust, JourneyArtifact et AccessCredential restent séparés.**
11. **Le Passeport Makolo est une projection/export, pas une nouvelle vérité métier.**
12. **Le Passeport distingue déclaration, fait établi et attestation délivrée.**
13. **Makolo ne produit pas un score universel de valeur, employabilité ou compétence humaine.**
14. **Le réseau bilatéral part de signaux volontaires et de faits publics autorisés, jamais de la vie privée implicite.**
15. **La personnalisation doit pouvoir expliquer les raisons principales d’une proposition ou notification.**
16. **L’objectif d’engagement est l’action utile accomplie, pas le temps passé dans un feed.**

## 17. Relation avec M5, M8 et le mobile

G prolonge M5 sans le remplacer : M5 a posé le réseau social d’action, les Contributions et l’engagement utile ; G renforce l’identité d’action, la pertinence, la découvrabilité consentie et la portabilité des faits.

M8 possède l’assemblage web Mature : il doit composer Profile, Interests, Open to, Veilles, Passeport et sollicitations sans créer un second modèle social.

Le programme mobile A consommera ensuite les mêmes contrats backend/API. Aucun comportement critique de G ne doit dépendre uniquement d’un template ou de JavaScript web.
