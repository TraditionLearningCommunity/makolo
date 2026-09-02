# M5 — Social Action Network & Useful Engagement

## Vision

Makolo est un **réseau social d'action** : le graphe social sert à découvrir, préparer et accomplir des actions réelles. Il n'est pas optimisé pour le temps de scroll, la popularité ou la viralité. **Activity reste le noyau** ; Event, Service et Transport sont des verticales. Journey reste le parcours individuel.

## Frontières canoniques

M5 compose `Profile`, `Organization/Space`, `Groups`, `Activity/Occurrence`, `Journey`, `Access`, `Discovery`, `Notifications`, `Loyalty` et Trust M4. Il ne recrée ni Readiness M1, Forms/Resources M2, Presentation M3, Trust/Feedback/Reports/Proofs M4, ni le Sharing externe P1.

`OrganizationFollow` reste le Follow canonique d'un Space. Follow ne crée aucun `Mandate`, aucune `Permission`, aucun accès participant et aucun consentement CRM. `GroupMembership` reste une appartenance de Groupe et ne devient jamais une autorité Space. `ActivityBookmark` reste le signal explicite d'enregistrement ; M5 n'ajoute aucun Like/Favorite parallèle.

## Contributions — No Orphan Content

`social.Contribution` est un UGC contextualisé, pas un post généraliste. Une racine doit référencer au moins un contexte canonique `Space`, `Group`, `Activity` ou `Occurrence`. La DB impose cet invariant et le service vérifie en plus la cohérence Occurrence→Activity et les relations Space/Group/Activity.

Kinds contrôlés : `UPDATE`, `TIP`, `FIELD_NOTE`, `DISCUSSION`, `SHARE`. Une `UPDATE` officielle exige une autorité `SPACE_MANAGE` ou `ACTIVITY_MANAGE`. Une contribution de Groupe exige une membership active ou la permission Groupe réelle. Une note terrain hors Groupe exige une relation Journey/Access admissible. Un partage interne stocke uniquement `Group + Activity`, sans copier l'Activity et sans octroyer Journey, Access, Capacity, billet ou Resource privée.

Les réponses héritent exactement du contexte racine et la profondeur est bornée. Le texte est du texte brut échappé ; aucun HTML arbitraire n'est rendu. Aucun média social n'est ajouté en M5 faute de besoin démontré : cela évite aussi une URL storage contournant la privacy Groupe.

## Visibility et modération

Les contenus de Groupe restent `CONTEXT` et sont lisibles uniquement par les personnes autorisées. Une publication `PUBLIC` est réservée à une update officielle sur un contexte lui-même public. Les états `PUBLISHED`, `HIDDEN`, `REMOVED` permettent un retrait non destructif. Auteur, modérateur Groupe, autorité Activity/Space et staff n'ont que les capacités correspondant à leur périmètre.

M4 reste propriétaire des Reports. Le modèle M4 actuel ne possède pas de FK Contribution et son service impose un contexte Trust vérifiable ; M5 ne crée donc pas `SocialReport`. Une extension future doit être un bridge explicite vers `trust.Report`, jamais une deuxième infrastructure de signalement.

## Action Stream

`social.action_stream.ActionStreamItem` et `ActionStreamPage` sont des projections Python non persistantes. Il n'existe pas de `FeedItem` ou `Timeline` matérialisé. Les sources sont bornées : Activities publiques récentes des Spaces suivis, Contributions/SHARE des Groupes actifs et recommandations Discovery. Le flux déduplique par Activity, agrège les reasons, utilise une fenêtre temporelle, applique un limit/offset et propose « voir plus » plutôt qu'un infinite scroll obligatoire.

Aucune Journey privée d'un tiers, FormResponse, Payment, AccessCredential, QR, Report, Dispute, evidence Trust, Goal ou CRM note n'entre dans ce flux.

## Recommendations explicables

`discovery.recommendations` étend Discovery plutôt que créer un second moteur. Les adapters calculent des candidates bornées à partir de : `following_space`, `group_relevance`, `bookmarked_similar_activity`, `past_activity_interest`. Le ranking est déterministe, documenté par des poids explicites et la fraîcheur ; il n'utilise ni followers, likes, vues, influence score ni ML opaque. Les candidates non publiées/inaccessibles sont filtrées avant exposition et un cap par Space préserve une diversité simple.

Le moteur est Activity-first et couvre Event, Service, Transport et Activity générique. Les reasons basées sur l'historique restent génériques et ne révèlent jamais le détail d'une Journey privée. Les CTAs proviennent uniquement de routes Makolo contrôlées.

## History, Personal Stats et Goals

`/me/history/` reste la projection existante ; M5 l'enrichit avec une projection privée de stats, Goals, Contributions personnelles, Proofs M4 et Loyalty. Aucune table Timeline n'est créée et aucune donnée n'est publiée automatiquement.

`goals.PersonalGoal` appartient au domaine personnel. Types M5 : Journeys accomplies et Activities accomplies. `target_value > 0`, période bornée et workflow `ACTIVE/COMPLETED/PAUSED/CANCELLED`. Le progrès est dérivé en lot des Journeys `FULFILLED`; aucune valeur de progrès n'est modifiable. La completion est idempotente et produit seulement une notification in-product dédupliquée. Un Goal ne bloque jamais Readiness et ne donne jamais automatiquement des points Loyalty.

## Loyalty et achievements

M5 lit les `LoyaltyAccount`, Memberships et Rewards canoniques ; il ne modifie ni ledger, ni règles de points, ni équivalence monétaire. Les Proofs M4 sont visibles au propriétaire dans son History selon le contrat M4. Private by default : aucune Journey, Goal, Proof privé, Follow list ou membership privée n'est transformée automatiquement en publication.

Le Sharing externe reste P1. Si P1 est absent de `main`, M5 n'invente aucun token ou ShareLink. S'il est présent au final sync, seules ses APIs stables doivent être consommées.

## API, sécurité et mobile futur

Les services `create_contribution`, `share_activity_to_group`, `moderate_contribution`, selectors de stream/recommendations et services Goals portent la logique serveur ; les Views/API ne la réimplémentent pas. Les vérifications serveur empêchent IDOR entre Groupes, publication officielle sans autorité, lecture de Groupe privé et modification d'un Goal tiers. Les templates échappent l'UGC et aucune URL utilisateur libre ne devient un CTA.

Les APIs web sont réutilisables plus tard par le mobile. M5 ne construit ni app mobile, push natif, géofence, routing, météo, last-minute engine, DM, chat temps réel, autoplay, stories, vidéo, marketplace ou système de plugins.

## Analytics et engagement utile

Le succès M5 doit être relié aux actions réelles : Follow→Activity view/Journey, Group SHARE→Activity/Journey, Recommendation→Activity/Journey, Bookmark→Journey, Goal created→completed, Contribution→action utile. Le temps de scroll, les likes et les vues ne sont pas des KPI métier M5.

## Décisions reportées

- média Contribution : reporté jusqu'à un besoin réel avec storage privé autorisé ;
- bridge exact Contribution→M4 Report : à ajouter lorsque le contrat Report accepte explicitement ce contexte ;
- partage externe d'achievement : P1 uniquement ;
- signaux M6 `nearby_now`, `capacity_released`, `leave_soon` : réservés à M6 ;
- adapters d'extensions : M7 pourra se brancher sur les contracts candidates/reasons sans plugin system M5 ;
- Cockpit global : M8 composera les projections M5.
