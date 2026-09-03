# Makolo — Mature Experience Principles

> **Statut : canonique pour les principes d'expérience à assembler dans M8.** Ce document complète [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md), [`strategic-action-roadmap.md`](strategic-action-roadmap.md) et [`mature-program-roadmap.md`](mature-program-roadmap.md). Il ne crée aucun bounded context et ne décide pas à l'avance qu'un modèle média transversal doit exister. Le code, les migrations et les tests du `main` courant restent la vérité sur le runtime effectivement livré.

## 1. Problème produit

Makolo sait progressivement découvrir, préparer, orchestrer, payer, donner accès, guider dans le temps et l'espace, coordonner plusieurs acteurs, accompagner l'Occurrence réelle et conserver ce qui pourra être réutilisé.

Mais une expérience principalement composée de textes, formulaires, statuts, listes et commandes peut donner l'impression d'un SaaS, d'un ERP, d'un gestionnaire de démarches ou d'une todo list sophistiquée.

Le problème n'est pas l'utilité de Makolo.

> **L'utilité n'engendre pas automatiquement le désir.**

Makolo doit pouvoir parler à l'utilisateur par l'image, le mouvement, le son, la carte, les personnes, l'ambiance, l'immédiateté et la curiosité, sans construire une économie autonome du contenu ni optimiser la captation de l'attention.

Principe produit :

> **Makolo ne cherche pas principalement à rendre désirable le prochain contenu. Makolo cherche à rendre désirable la prochaine possibilité réelle.**

Le média est un moyen. Les objets restent notamment `Activity`, `Occurrence`, `Opportunity`, `Space`, `Group`, `Journey`, Dossier et les actions réelles qu'ils permettent.

## 2. Action Delight

Principe transversal :

> **Pas le plaisir de rester. Le plaisir d'avancer.**

Makolo peut chercher à produire :

- curiosité ;
- anticipation ;
- soulagement ;
- confiance ;
- fierté ;
- plaisir collectif ;
- sentiment de mouvement.

Ces émotions doivent découler de possibilités et accomplissements réels, pas d'une mécanique de dépendance.

Les métriques centrales restent liées à l'action : Activity ouverte, enregistrée ou partagée ; Journey démarrée ; demande/réservation/commande ; participation réelle ; action utile accomplie. Le watch time, la profondeur de scroll et le nombre maximal d'items servis ne sont pas des objectifs métier centraux.

## 3. Séparation fondamentale : Accueil et Discover

### Accueil

Question :

> **Qu'est-ce qui compte maintenant ?**

L'Accueil est privé, contextuel et orienté accomplissement. Il compose notamment `NextAction`, Readiness, Journey, Dossier, Assignment, Access, Payment, Hazard, départ recommandé, Occurrence imminente et responsabilités autorisées.

L'Accueil doit pouvoir avoir une vraie conclusion :

> **Tout est en ordre. ✓**

Il ne devient pas le grand feed Makolo et ne crée pas de `HomeFeedItem` ou de timeline persistante générique.

### Discover

Question :

> **Qu'est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

Discover est volontairement exploratoire. Il peut être visuel, multimédia, scrollable, cartographique, sensoriel et social. L'utilisateur choisit d'entrer dans cet espace.

L'exploration ne doit pas être confondue avec l'accomplissement. M8 doit rendre cette différence perceptible dans l'expérience et pas seulement dans l'architecture.

## 4. Sensory Discovery — Découverte sensorielle

### Nature

Capacité d'expérience et de projection. Elle ne justifie pas, à elle seule, un nouveau bounded context.

Candidat naturel à M8 par composition de Discovery, Presentation M3, Activity/Occurrence, Geography/M6, Space et M5 lorsque le contexte social enrichit réellement la découverte.

### Problème

Une Activity réelle peut être enthousiasmante, belle, humaine, sociale, spectaculaire ou apaisante tout en paraissant peu intéressante lorsqu'elle est représentée seulement par :

`titre + description + date + bouton`.

Une découverte trop textuelle impose un effort cognitif avant même que l'utilisateur sache si la possibilité lui donne envie.

### Promesse

> **Voyez, écoutez et ressentez suffisamment une possibilité pour savoir rapidement si vous avez envie de la vivre.**

Version courte :

> **Voyez ce qui vous donne envie.**

### Représentation adaptée à l'Activity

Il n'existe pas de doctrine « tout doit être vidéo ».

Exemples de composition possibles :

- concert : courte vidéo dominante ;
- voyage : carte + paysages + courte vidéo ;
- restauration : photos + carrousel ;
- formation : personne + vidéo/audio + informations essentielles ;
- transport : carte + véhicule/lieu + horaires ;
- service : démonstration ou explication courte.

Les facts tels que date, capacité, prix, Access, disponibilité ou CTA restent produits par leurs domaines canoniques. Le média les représente ; il ne les possède pas.

## 5. Contextual Action Media — No Orphan Media

### Nature

Mécanisme transversal à auditer avant toute généralisation du multimédia. Il peut révéler un gap technique persistant, mais aucun modèle `Media`, `MediaAsset` ou équivalent ne doit être créé avant audit des contrats Presentation, storage, uploads et visibility existants.

### Problème

Ajouter indépendamment `video_url` à Event, `audio_url` à Service, `gallery` à Journey ou `image_2` à Transport recréerait les duplications que l'architecture Makolo cherche à supprimer.

### Promesse

> **Une possibilité Makolo peut être montrée de la manière la plus naturelle sans recopier sa vérité métier.**

### Principe

> **No Orphan Media : un média Makolo possède toujours un contexte et une finalité.**

Un média peut représenter ou accompagner, lorsque le contrat le permet :

- Activity ;
- Occurrence ;
- Space ;
- Group ;
- Contribution M5 ;
- Resource ;
- éventuellement Journey lorsque confidentialité et finalité le justifient.

Il n'existe pas simplement pour « alimenter Makolo ».

### Responsabilités candidates à auditer

Selon le gap réel, le mécanisme pourrait devoir porter : type image/vidéo/audio, provenance, contrôleur logique, contexte, ordre, visibility, durée, miniature, texte alternatif, captions/transcription, sensibilité et état de modération.

Cette liste est une cible d'audit, pas une décision de schéma.

### Ce que le média ne possède jamais

Il ne possède pas :

- Activity ;
- Permission/Mandate ;
- Journey ;
- Access ;
- Payment ;
- Capacity ;
- date d'Occurrence ;
- prix ;
- état métier de disponibilité ;
- popularité comme vérité métier.

### Intégration M5

`social.Contribution` reste un contenu contextualisé. M5 a délibérément livré du texte sans média social et a reporté le média jusqu'à un besoin démontré avec storage/visibility sûrs.

L'extension correcte est conceptuellement :

```text
Contribution contextualisée
+ média autorisé
+ même contexte
+ même visibility
+ mêmes contrôles d'autorisation
= Contribution multimédia
```

et non une nouvelle infrastructure de posts vidéo.

### Sécurité

Avant implémentation, l'audit doit traiter notamment :

- storage public/privé ;
- URL signée lorsque nécessaire ;
- contrôle d'accès serveur ;
- cache privacy ;
- MIME ;
- taille et durée ;
- traitement de fichiers ;
- suppression ;
- modération ;
- métadonnées sensibles ;
- accessibilité ;
- exposition Groupe/public.

Un média ne doit jamais permettre de contourner la confidentialité d'un Group, d'une Contribution, d'une Resource ou d'une Journey.

## 6. État d'implémentation à ne pas canoniser comme architecture finale

Au moment de l'audit ayant conduit à ce document, la verticale Event possède encore `Event.cover_image` et la présentation Discovery récupère son image depuis cette verticale.

Cela prouve qu'une représentation image existe déjà ; cela ne fait pas d'Event le propriétaire générique du média Makolo.

La direction est :

> **généraliser la représentation de manière Activity-first sans remettre Event au centre.**

La migration exacte doit être décidée seulement après audit de M3 Presentation, Discovery, storage et uploads. Une compatibilité Event peut rester nécessaire pendant la transition.

## 7. Bounded Exploration — Exploration sans piège

### Nature

Contrat produit, ranking et UX. Pas un nouveau domaine.

### Problème

Deux mauvaises solutions existent :

1. pagination traditionnelle visible qui casse inutilement l'exploration mobile ;
2. infini artificiel où les critères sont progressivement dégradés uniquement pour continuer à servir quelque chose.

### Promesse

> **Explorez aussi loin que vous le souhaitez sans perdre de vue pourquoi Makolo vous montre quelque chose.**

Et surtout :

> **Makolo peut arriver au bout de ce qui est réellement pertinent.**

### Scroll continu ≠ corpus infini

Makolo peut utiliser une pagination/cursor technique invisible dans l'interface et permettre un scroll naturel.

Lorsque le corpus pertinent est épuisé, il peut afficher une frontière réelle puis proposer un élargissement explicite : zone plus large, période suivante ou autre contexte.

Exemple :

```text
Pour vous maintenant
        ↓
✓ Vous avez vu les recommandations les plus pertinentes.
        ↓
Autour de vous
        ↓
Ce week-end
        ↓
Plus loin
```

Les cercles peuvent être géographiques, temporels, sociaux ou contextuels.

### Explicabilité

Une recommandation conserve une raison compréhensible lorsque possible : près de vous, ce week-end, Space suivi, partagé dans votre Groupe, Activity similaire enregistrée, nouvelle disponibilité ou autre raison issue d'un fait structuré légitime.

Ne pas introduire « populaire » comme raccourci opaque. Tout signal futur de demande/fréquentation doit être défini à partir de faits d'action réels, agrégés de manière privacy-safe et sans devenir un score de popularité universel.

### Métriques

À observer :

- Activity ouverte ;
- diversité des Activities réellement explorées ;
- bookmark ;
- partage ;
- conversion vers Journey/demande/réservation/commande ;
- participation réelle ;
- taux d'épuisement naturel du corpus ;
- cohérence entre raison affichée et action produite.

Ne pas optimiser principalement : scroll depth, session time ou nombre maximal d'items servis.

## 8. Action Rituals — situations humaines répétées

### Nature

Cadre d'expérience transversal. Pas de modèle `Ritual` et pas de bounded context.

M8 puis le mobile doivent orchestrer les domaines existants autour de moments humains répétés.

### Aujourd'hui

Question : **Qu'est-ce qui m'attend aujourd'hui ?**

Surface principale : Accueil.

Composition : NextAction, Readiness, Journey, Dossier, Assignment, Occurrence, Notifications.

Promesse ressentie : **Je sais ce qui compte sans chercher partout.**

### On fait quoi ?

Déclencheurs : soirée, week-end, vacances, moment libre, amis/famille.

Surface : Discover.

Promesse : **Trouvons quelque chose qui nous donne envie.**

Ambition culturelle : « Regarde sur Makolo » peut devenir une réponse naturelle à « On fait quoi ce week-end ? ».

### Est-ce que tout est prêt ?

Déclencheur : avant un voyage, événement, rendez-vous, cérémonie ou inscription.

Surface : Accueil / Journey Command Center.

Composition : Readiness, Requirements, Payment, Access, Resources, Q/R et M6 selon contexte.

Promesse : **Ouvrez Makolo et partez tranquille.**

Émotion recherchée : soulagement.

### Il est temps d'y aller

Déclencheur : Occurrence imminente.

Makolo passe progressivement de la préparation à l'action.

Composition : Occurrence, M6, Access, O — Occurrence Operations, Placement, Flow/Queue et Geography.

Promesse : **Quand l'action commence, Makolo me montre ce qui compte maintenant.**

### Autour de moi maintenant

Déclencheur : recherche spontanée de ce qui existe autour de l'utilisateur.

Surface : Discover + carte.

Composition : Discovery, Geography/M6, Activity, Occurrence et Capacity lorsqu'elle est exposable.

Promesse : **Voyez ce qui est possible autour de vous maintenant.**

### On fait ça ?

Déclencheur : une personne trouve une Activity utile ou attirante pour son Groupe.

Composition : Discover, Sharing P, M5, Group, Activity.

Promesse : **Je ne t'envoie pas seulement quelque chose à regarder : je te propose quelque chose qu'on peut faire.**

Le média donne envie. Sharing transporte l'action.

### Une possibilité vient d'apparaître

Déclencheur : fait métier réel — place libérée, nouvelle Occurrence/départ, Requirement modifié, Opportunity pertinente, deadline ou Hazard.

Composition : Domain Events, Automation/Autopilot, Notifications, Discovery, R et M6 selon contexte.

Promesse : **Makolo revient vers moi lorsqu'un changement modifie réellement ce que je peux faire.**

Interdit : relances de rétention du type « vous ne nous avez pas ouvert depuis trois jours » sans changement métier utile.

### J'ai accompli quelque chose

Déclencheur : Journey/Activity accomplie.

Composition : History, Proof, Goals, Q — Bibliothèque/Action Memory.

Promesse : **Ce que vous avez accompli ne disparaît pas et peut faciliter la suite.**

Le partage reste volontaire et la vie personnelle privée par défaut.

## 9. Préparation M8 — M8-PRE

M8-PRE est une piste de préparation et non un train métier ou un nouveau bounded context. Elle peut être auditée en parallèle des trains métier.

### M8-P0 — Experience contracts & audit

Auditer :

- M3 Presentation ;
- Discovery ;
- Event `cover_image` et autres images existantes ;
- Activity/Occurrence ;
- ActivityResource ;
- storage public/privé ;
- validators/uploads ;
- M5 Contribution/visibility/modération ;
- Sharing ;
- M6 Geography/spatiotemporal ;
- frontend actuel.

Décider ensuite si un vrai gap média transversal persiste.

### M8-P1 — Activity-first representation / media foundation si gap confirmé

Si l'audit le justifie, fournir le minimum technique permettant à Activity/Occurrence et aux contextes autorisés d'être représentés sans dépendre d'une verticale Event.

Ne pas ouvrir un grand chantier `Media` autonome.

### M8-P2 — Bounded Discovery contracts

Stabiliser les contrats de candidates, reasons, cursors/boundaries, redaction et extension explicite de zone/temps nécessaires à l'exploration bornée.

### M8-P3 — Ritual contracts & acceptance scenarios

Transformer les rituels de ce document en scénarios d'acceptation transversaux afin que M8 puisse tester une expérience cohérente au-dessus des domaines stabilisés.

Les gros changements Home/Discover restent dans M8 pour éviter plusieurs trains qui refont simultanément le frontend global.

## 10. Gate produit M8

Le web Mature ne doit pas être considéré comme réellement Mature si :

- Discover reste essentiellement textuel ;
- Activity est riche architecturalement mais pauvre visuellement ;
- l'Accueil ressemble à un dashboard SaaS sans hiérarchie d'action ;
- l'utilisateur doit connaître la terminologie interne pour agir ;
- la représentation générique reste enfermée dans Event ;
- exploration et accomplissement sont confondus ;
- l'Occurrence imminente ressemble encore à une fiche statique ;
- les médias deviennent du contenu sans contexte ;
- l'exploration doit inventer artificiellement des items pour ne jamais se terminer.

Gate recherché :

> **Makolo Mature doit pouvoir être utile sans ressembler à un outil qu'il faut se forcer à utiliser.**

M8 doit assembler Makolo de façon à ce qu'il soit aussi naturel d'explorer une possibilité que rassurant de préparer une action et évident d'agir quand le moment arrive.

## 11. Mobile

Le programme mobile A amplifie ensuite cette direction grâce aux capacités du téléphone : caméra, localisation ponctuelle, audio, push, share sheet, haptique, widgets, Live Activities/équivalents, géofencing lorsqu'il est justifié et offline spécialisé.

Exemples :

- Aujourd'hui → widget ;
- Il est temps d'y aller → push / Live Activity ;
- Autour de moi → localisation ponctuelle ;
- On fait ça ? → share sheet ;
- document → caméra ;
- Occurrence Live → haptique/offline/push.

Le mobile ne devient pas propriétaire du ranking, de Readiness, de l'autorisation, de Payment ou de la validité Access.

## 12. Boucle produit cible

```text
DISCOVER
   ↓
Voir / ressentir
   ↓
ENVIE
   ↓
Activity → Journey / Dossier
   ↓
PRÉPARER
   ↓
Occurrence / Access
   ↓
AGIR / VIVRE
   ↓
History / Proof / Memory
   ↓
ACCOMPLI
   └──────────────► nouvelle découverte
```

Cette boucle complète **« Makolo marche pour vous »** par une seconde qualité essentielle :

> **Makolo vous donne envie d'avancer.**

## 13. Anti-features

Ce document ne justifie pas automatiquement :

- `Media` bounded context ;
- `VideoFeed` ;
- `Story` ;
- `Reel` ;
- `Creator` / économie d'influence ;
- Like ;
- ViewCount comme vérité centrale ;
- WatchTimeScore ;
- `Ritual` model ;
- `DiscoverFeedItem` métier persistant ;
- `HomeFeedItem` métier persistant ;
- autoplay généralisé ;
- ranking opaque visant principalement la rétention.

Les besoins doivent d'abord être résolus par Presentation, Discovery, Activity/Occurrence, Contribution M5, projections/read models et, seulement si l'audit démontre un gap réel, un mécanisme media contextualisé.