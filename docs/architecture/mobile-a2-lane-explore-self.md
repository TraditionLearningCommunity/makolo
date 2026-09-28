# A2 — Lane Explore & Self

> **Développeur/agent 2**
>
> **Statut : work package préparé — NE PAS DÉMARRER avant A2_BASE_SHA**
>
> **Branche prévue : mobile/a2-explore-self**
>
> **Cible PR : mobile/a2-integration**

## 1. Mission

Construire :

~~~text
Découvrir
Moi
Avatar
~~~

Ces surfaces couvrent :

~~~text
ce qui pourrait m'intéresser / être utile
+
ce qui me représente et m'appartient
+
mon compte et mon contexte acteur
~~~

Le développeur 2 ne travaille pas Maintenant, En cours ou Makolo Mark, sauf demande explicite de l'orchestrateur.

## 2. Préconditions

Ne commencer qu'après réception de :

- A2_BASE_SHA ;
- contrats A2 communs ;
- confirmation A1 fusionné/vert ;
- décision orchestrateur sur le pack Discovery local ;
- décision orchestrateur sur ce qui est réellement supporté dans Avatar.

La branche part exactement de A2_BASE_SHA.

## 3. Fichiers autorisés

Créer/modifier autant que possible sous :

~~~text
mobile/lib/features/discovery/**
mobile/lib/features/me/**
mobile/lib/features/avatar/**

mobile/test/**discovery**
mobile/test/**me**
mobile/test/**avatar**
~~~

Repositories/adapters spécialisés nouveaux autorisés, par exemple :

~~~text
discovery_repository.dart
me_repository.dart
account_context_repository.dart
~~~

Suivre la convention A1 finale plutôt que créer un nouveau pattern.

## 4. Shared/frozen

Ne pas modifier indépendamment :

~~~text
mobile/lib/app/**
mobile/lib/navigation/**
mobile/lib/design/makolo_theme.dart
mobile/lib/design/behavior_primitives.dart
mobile/lib/design/behavior_states.dart
mobile/lib/auth/**
mobile/lib/network/**
mobile/lib/sync/**
mobile/lib/data/local/**
mobile/pubspec.yaml
mobile/pubspec.lock
~~~

Le nouveau pack Discovery local est un changement partagé. La lane spécifie le besoin ; l'orchestrateur modifie Drift/sync sur mobile/a2-integration.

Ne pas modifier :

~~~text
mobile/lib/features/now/**
mobile/lib/features/ongoing/**
mobile/lib/features/mark/**
~~~

## 5. Découvrir

### Contrat

Question :

> **Qu'est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

Source :

~~~text
GET /api/v1/discovery/items/
~~~

Utiliser la projection mature multi-famille, pas le feed Event historique.

### Rendu

Découvrir est la surface A2 la plus exploratoire.

Quand présent dans le payload, utiliser :

- image ;
- title/summary ;
- date/temps ;
- lieu ;
- owner ;
- availability ;
- price ;
- relation personnelle ;
- saved/watch ;
- raison/contexte lorsqu'un owner l'expose ;
- capabilities ;
- links.

Ne pas fabriquer de média, score ou popularité.

### Recherche

Online :

- requête vers l'API Discovery propriétaire ;
- résultats appliqués au store/pack selon contrat orchestrateur.

Offline :

- recherche uniquement dans le corpus local ;
- ne pas prétendre à l'exhaustivité.

### Filtres

Pattern mobile préféré : bottom sheet.

Préserver :

- query ;
- filtres ;
- position de scroll ;
- élément sélectionné ;
- mode liste/carte seulement si un mode carte est réellement implémenté.

### Bounded exploration

Quand le corpus se termine :

- montrer une vraie fin ;
- proposer explicitement d'élargir si cela a du sens ;
- ne pas relâcher silencieusement les critères.

### Média

- no orphan media ;
- pas d'autoplay ;
- dimensions stabilisées ;
- absence d'image = layout élégant, pas placeholder technique ;
- cache média via infrastructure A1, jamais nouveau cache parallèle.

## 6. Moi

### Contrat

Question :

> **Ce qui me concerne dans Makolo.**

Source :

~~~text
GET /api/v1/me/
projection locale A1 : personal.me
~~~

Le runtime compose déjà :

- identity ;
- passport ;
- considerations ;
- collectives ;
- resources ;
- support ;
- links.

### Structure

Présenter seulement les sections pertinentes et présentes.

Ordre de départ recommandé, à ajuster sur données réelles :

1. identité ;
2. Passeport Makolo ;
3. Ce qui compte pour moi ;
4. Mes collectifs ;
5. Mes ressources ;
6. Recognition/Loyalty/Partner lorsque disponibles.

Ne pas transformer Moi en édition brute de User/Profile.

### Collectifs

Le serveur distingue :

- authorized_spaces ;
- teams ;
- groups.

Ne jamais déduire l'autorité d'une Team ou Group membership.

Si une section montre une appartenance, son wording ne doit pas suggérer que la personne peut administrer l'Espace.

### Ressources

Les previews peuvent inclure documents, Proof et Credentials.

A2 ne confond pas :

~~~text
ressource
fichier
Proof
Credential
AccessCredential
~~~

Ne jamais afficher un secret de credential dans la racine Moi.

## 7. Avatar

### Contrat

Avatar ≠ Moi.

Avatar porte :

- compte authentifié ;
- contexte acteur ;
- paramètres/compte réellement supportés ;
- sécurité/appareils si contrat disponible ;
- déconnexion.

Moi porte la projection personnelle.

### Identité

Source auth :

~~~text
GET /api/v1/accounts/auth/me/
~~~

Ne pas remplacer Moi par ce bootstrap.

### Contextes autorisés

Runtime disponible :

~~~text
GET /api/v1/organizations/workspaces/
~~~

Cette collection est permissionnée.

Mais :

> workspace autorisé ≠ mécanisme mobile déjà défini pour agir comme cet Espace.

Ne pas créer une liste "Agir comme" cliquable tant que l'orchestrateur n'a pas démontré le handoff de contexte.

Aucun state local ne crée Permission/Mandate/Access.

### Pattern

Avatar est une surface courte :

- bottom sheet de préférence ;
- plein écran uniquement si le contenu réel le justifie.

Il n'est jamais un sixième item de bottom navigation.

## 8. Notifications / Conversations

Cette lane ne les implémente pas implicitement.

Si l'orchestrateur décide de les inclure comme support du header :

- il définit d'abord le repository/store partagé ;
- il assigne explicitement la surface ;
- aucune icône n'est créée avant la destination.

Le simple fait que le Web possède l'icône ne suffit pas.

## 9. Local-first — Discovery

A1 n'a pas encore de source Discovery installée.

La lane doit produire la forme de lecture et les adapters, mais la migration/store/sync partagés appartiennent à l'orchestrateur.

Le pack est borné, owner-aware et non exhaustif.

Aucune logique de ranking locale.

Le payload local doit préserver les informations nécessaires au rendu sans retransformer Activity/Occurrence en nouvelles entités métier.

## 10. Local-first — Moi

Utiliser personal.me via le store A1.

Ne pas refaire :

~~~text
screen
→ GET /me/
→ spinner
~~~

à chaque visite.

Les sous-sections éventuellement chargées en profondeur appartiennent à leurs owners et peuvent rester network-required si A3 n'a pas encore installé leur cache.

## 11. Local-first — Avatar

Le compte courant peut être disponible offline via session locale sécurisée.

Cependant :

- aucune autorité nouvelle offline ;
- aucun nouvel Espace sélectionnable sans contrat ;
- les workspaces autorisés peuvent être stale et exigent revalidation avant action au nom d'un Espace ;
- logout/remove-account traite explicitement les pending operations.

## 12. Composants de feature

Exemples locaux :

- DiscoverySearchHeader ;
- DiscoveryResultCard ;
- DiscoveryEmpty ;
- DiscoveryFilterSheet ;
- MeIdentityHeader ;
- MeSection ;
- MePreviewRow ;
- AvatarSheet.

Ne pas créer AppHeader global, MakoloCard global, SyncBanner global ou nouveau design system.

## 13. Product Language

Ne pas afficher les noms internes :

- ProfileInterest ;
- ProfileOpenTo ;
- DiscoveryWatchStatus ;
- TeamMembership ;
- Permission ;
- Mandate ;
- credential_type raw ;
- projection ;
- owner.

Utiliser les labels serveur et le vocabulaire produit.

Moi doit paraître personnel, pas administratif.

## 14. Tests minimum

### Découvrir

- initial sans pack ;
- results ;
- empty query ;
- search ;
- filters ;
- pagination/boundary ;
- offline cached ;
- stale ;
- back restores search/scroll ;
- media absent ;
- media available ;
- save capability présente/absente ;
- no CTA sans link.

### Moi

- projection complète ;
- sections absentes ;
- previews vides ;
- support disponible/absent ;
- authorized_spaces distinct de team membership ;
- offline ;
- stale ;
- links A3 conservés.

### Avatar

- identity ;
- no authorized context ;
- authorized workspaces affichés seulement selon décision orchestrateur ;
- aucun membership-only faux contexte ;
- logout ;
- pending local work warning selon A1 ;
- large text ;
- bottom sheet/back ;
- session expiration.

### Repository

- cache local immédiat ;
- refresh non destructif ;
- profile isolation ;
- Discovery pack borné ;
- recherche offline limitée au local.

### Accessibility

- search label ;
- filtre ;
- cards lisibles sans image ;
- sections Moi avec headings ;
- Avatar sheet order ;
- text scaling.

### Goldens

Candidats :

- Discover result card ;
- Discover no-image ;
- Discover empty ;
- Moi identity + sections ;
- Avatar sheet.

## 15. Screenshots

Obligatoires pour :

- petit/moyen/grand téléphone ;
- Discover riche ;
- Discover sans média ;
- Discover empty ;
- Discover offline ;
- Moi complet ;
- Moi sparse ;
- Avatar ;
- grands textes.

Aucune donnée réelle sensible.

## 16. Visual goals

### Découvrir

Doit donner envie de considérer une possibilité réelle, pas de scroller pour scroller.

### Moi

Doit sembler personnel, calme, utile, sans devenir un réseau social.

### Avatar

Doit sembler utilitaire et sûr, pas une destination de contenu.

## 17. Review croisée

Avant merge, relire mobile-a2-lane-action.md et signaler à l'orchestrateur :

- faiblesse visuelle ;
- violation conventions mobile ;
- Product Language technique ;
- action morte ;
- composant partagé inutile.

Ne pas modifier la branche Action.

## 18. Contenu de PR

La PR vers mobile/a2-integration contient :

- surfaces ;
- fichiers ;
- API ;
- dépendance au pack Discovery partagé ;
- impact store local ;
- états Behavior ;
- screenshots ;
- tests ;
- limitations ;
- besoins A3 ;
- aucune migration Django.

## 19. Gate de sortie

La lane est mergeable si :

- Découvrir est réellement exploratoire sans feed de rétention ;
- Moi consomme personal.me localement ;
- Avatar reste séparé de Moi ;
- aucune autorité n'est inventée ;
- pas de faux contenu ;
- back/query/scroll sont préservés ;
- offline est honnête ;
- tests verts ;
- accessibilité ciblée ;
- visual QA validée ;
- shared/frozen respecté.
