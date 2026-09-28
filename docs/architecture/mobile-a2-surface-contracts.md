# A2 — Surface contracts

> **Statut : contrat produit/technique A2-P0**
>
> Ce document décrit les surfaces par question humaine. La structure Django n'est pas l'architecture de l'écran.

## 1. Invariants transversaux

- Profile = personne globale, jamais rôle global participant/organisateur.
- Assignment = responsabilité ; Permission/Mandate = autorité.
- Membership/Group/Team n'accorde pas automatiquement d'autorité.
- Readiness est dérivée côté owner/serveur.
- Access, AccessCredential et AccessUse restent distincts.
- Capacity répond à combien, Placement à où.
- Dossier et Project ne deviennent pas des task managers.
- Presentation représente les faits ; elle ne les possède pas.
- Toute action sensible est revalidée côté serveur.
- Une action visible mène quelque part d'utile.
- Aucun vocabulaire d'architecture interne n'est visible.

## 2. Maintenant

### Question humaine

> **Qu'est-ce qui compte maintenant ?**

### Source backend

GET /api/v1/me/now/

Projection serveur : personal.now.

Le runtime main sérialise actuellement chaque item avec notamment :

- key ;
- kind ;
- dimension ;
- source ;
- state ;
- title ;
- summary ;
- timing ;
- capabilities ;
- links ;
- occurrence pour certains Journey.

### Projection locale

Racine A1 personal.now dans projection_snapshots.

### Sections / hiérarchie

A2 suit l'ordre serveur et la sémantique présente. Il ne crée pas un ranking local.

Composition visuelle :

1. contexte/header ;
2. action(s) réellement importante(s) ;
3. informations secondaires ;
4. all-clear si items vide connu.

Les dimensions serveur peuvent informer la présentation, mais aucun enum technique n'est imprimé tel quel.

### Actions visibles

Uniquement celles démontrées par capabilities + links ou par un handoff owner sûr.

Si un detail appartient à A3 et n'a pas encore une destination utile, ne pas afficher un bouton mort.

### Empty

Si items=[] dans un snapshot synchronisé :

> **Tout est en ordre. ✓**

Si aucun snapshot :

> état de première disponibilité, jamais all-clear.

### Loading

Skeleton seulement sans snapshot local utile.

### Offline

Afficher le snapshot connu + indicateur discret.

### Stale

Conserver le contenu ; signaler la vérification nécessaire uniquement si l'âge influence une décision.

### Error

Conserver le contenu précédent. Retry discret.

### Back

Retour depuis une profondeur A2/A3-compatible restitue Maintenant et sa position.

### Resume

Rester sur Maintenant ; refresh discret si nécessaire.

### Accessibilité

Le premier élément d'attention doit être annoncé avant les détails secondaires. All-clear doit être lisible comme information, pas comme bouton.

### Deep links

Un deep link vers un item suit le link serveur/route mapper. Il revalide auth et scope.

### Limite A3

Pas de reconstruction complète Journey/Requirement/Access/Jour J.

## 3. En cours

### Question humaine

> **Qu'est-ce que j'ai réellement engagé et où en suis-je ?**

### Source backend

GET /api/v1/me/ongoing/

Projection : personal.ongoing, bornée actuellement à 18 items.

Le serveur compose notamment Journey, Access, Dossier, Project, Waitlist, transfert et certains Payment.

Champs généraux observés :

- kind/source ;
- state ;
- title ;
- ready ;
- actor_interventions ;
- continuation ;
- blocker ;
- next ;
- timing ;
- place ;
- capabilities ;
- links.

### Projection locale

Racine A1 personal.ongoing.

### Sections / hiérarchie

Présenter la continuité humaine :

- action de ma part lorsque le serveur l'indique ;
- attente/continuation ;
- prêt pour la suite ;
- blocage lorsque le serveur le fournit.

Ne pas inventer ces catégories en interprétant des statuts inconnus.

### Actions visibles

Les actor_interventions/capabilities/links autorisent le geste. Le mobile ne dérive jamais une action depuis un enum.

### Empty

Aucun engagement en cours peut être un vrai état vide.

Le message reste sobre, sans pousser artificiellement à découvrir du contenu.

### Loading / Offline / Stale / Error

Même discipline que Maintenant.

### Back

En cours → détail → retour conserve l'item et le scroll.

### Resume

Ne pas remonter en tête ni revenir à Maintenant.

### Accessibilité

Chaque item expose un titre, une situation humaine et une action principale maximum clairement priorisée.

### Deep links

Le link owner est conservé même si la profondeur Flutter arrive en A3.

### Limite A3

Pas de détail Journey complet, formulaires, Requirements profonds, AccessCredential ni Dossier workspace.

## 4. Makolo Mark

### Question humaine

> **Qu'est-ce que vous avez en tête ?**

### Source backend

POST /api/v1/me/mark/

Entrée texte actuelle :

~~~text
input.kind = text
input.value = texte
context = objet borné
~~~

La valeur texte est limitée côté serveur ; le client ne doit pas supposer que d'autres modalités sont déjà supportées.

### Projection locale

Draft local. La réponse serveur peut être conservée pour continuité UX si la politique A2 le justifie, mais n'est jamais transformée en vérité métier locale.

### Sections / hiérarchie

1. Mark/signature ;
2. question ;
3. champ ;
4. feedback d'envoi ;
5. résultat ou question de clarification ;
6. confirmation si nécessaire ;
7. handoff utile.

### États serveur

~~~text
resolved
completed
needs_clarification
needs_confirmation
unknown
unsupported
forbidden
~~~

Ce sont des états métier normaux, potentiellement HTTP 200.

### Actions visibles

- soumettre ;
- répondre à une clarification ;
- confirmer seulement la conséquence explicitement décrite ;
- suivre un link/handoff ;
- revenir/modifier le draft.

### Empty

Champ vide = aucune erreur tant que l'utilisateur n'a pas tenté une soumission invalide.

### Loading

Le champ et le contexte restent visibles. Bloquer une double soumission si elle est dangereuse.

### Offline

Sauver le draft ; aucune fausse interprétation ; aucune exécution automatique sensible au retour réseau.

### Stale

S'applique au résultat/handoff si sa cible exige revalidation, pas au texte du draft.

### Error

Transport error : draft conservé, message court, retry.

### Back

Fermer Mark retourne à la destination précédente. Le draft récupérable n'est pas perdu.

### Resume

Restaurer le draft ; ne pas relancer automatiquement le POST.

### Accessibilité

Label explicite du champ, ordre question → champ → résultat, confirmation compréhensible hors couleur.

### Deep links

Un handoff suit links/handoff serveur. Le client n'invente pas de destination à partir de l'intent.

### Limite A3

Pas de conversation persistante fictive, pas d'historique de chat générique, pas de moteur IA embarqué.

## 5. Découvrir

### Question humaine

> **Qu'est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

### Source backend

GET /api/v1/discovery/items/

Projection : discovery.items.

Éléments actuellement projetés avec :

- identity : family, candidate_key, resource, occurrence/revision ;
- representation : kind, title, summary, image_url, route_label, eyebrow ;
- timing ;
- place ;
- owner ;
- availability ;
- price ;
- personal_relation ;
- saved ;
- watch ;
- capabilities ;
- links ;
- provenance minimale.

L'endpoint supporte la collection mature multi-famille ; A2 ne revient pas au feed Event legacy.

### Projection locale

Pack Discovery borné à installer en P1/P3 par l'orchestrateur, sur les primitives A1.

### Sections / hiérarchie

- recherche ;
- contexte/filtres ;
- possibilités ;
- représentation riche lorsque les données existent ;
- fin de corpus.

### Actions visibles

- ouvrir detail si route utile ;
- save/unsave seulement si capability ;
- watch seulement si owner contract ;
- engagement seulement via owner.

### Empty

Distinguer :

- aucun résultat pour les critères ;
- pack local inexistant ;
- pack local épuisé ;
- recherche offline limitée au corpus acquis.

### Loading

Snapshot local immédiat. Skeleton seulement sans pack.

### Offline

Recherche/filtre local sur le corpus acquis. Ne jamais présenter cela comme exhaustif.

### Stale

Permettre l'exploration, mais revalider les disponibilités avant engagement.

### Error

Garder le pack et la position. Retry réseau n'efface ni query ni filtres.

### Back

Résultat → retour restaure query, filtres, scroll et mode de présentation.

### Resume

Conserver le contexte ; refresh discret.

### Accessibilité

Média décoratif exclu des Semantics ; titre, contexte, date/lieu et action restent lisibles sans image.

### Deep links

Utiliser links fournis. Un item inconnu/local absent peut être résolu via réseau si autorisé ; sinon expliquer l'indisponibilité.

### Limite A3

A2 peut avoir un détail minimal si le contrat owner est petit et stable. Pas de duplication de Activity/Occurrence workspace.

## 6. Moi

### Question humaine

> **Ce qui me concerne dans Makolo.**

### Source backend

GET /api/v1/me/

Projection : personal.me.

Le runtime main compose :

- identity ;
- passport ;
- considerations ;
- collectives ;
- resources ;
- support ;
- links.

Previews bornées actuellement à 6 par famille principale.

### Projection locale

Racine A1 personal.me.

### Sections / hiérarchie

Territoires humains :

1. identité personnelle ;
2. Passeport Makolo ;
3. ce qui compte pour moi : interests/open to/watches/bookmarks/follows selon présence ;
4. mes collectifs ;
5. mes ressources ;
6. Recognition/Loyalty/Partner si disponibles.

Les sections absentes ne laissent pas des containers vides décoratifs.

### Actions visibles

Suivre uniquement les links owner :

- identity_update ;
- considerations ;
- collectives ;
- passport ;
- resources ;
- partners ;
- accesses ;
- history.

A2 n'invente pas une édition inline universelle du Profile.

### Empty

Empty par section. La surface entière n'est pas résumée par Aucune donnée.

### Loading / Offline / Stale / Error

Snapshot privé local prioritaire ; refresh discret ; stale ciblé.

### Back

Retour d'une preview restitue Moi.

### Resume

Rester dans la section visible.

### Accessibilité

Identité annoncée sans surcharger ; sections navigables par headings/semantics.

### Deep links

Les liens owner sont conservés. Les profondeurs non A2 ne créent pas de CTA mort.

### Limite A3

Pas de gestion complète Passport/Resources/Group/Recognition/Loyalty/Partner.

## 7. Avatar

### Question humaine

> **Quel compte et quel contexte acteur suis-je en train d'utiliser ?**

### Source backend

Identité :

GET /api/v1/accounts/auth/me/

Contextes d'Espace réellement autorisés :

GET /api/v1/organizations/workspaces/

Le serveur Z15 construit ces workspaces à partir de l'autorité réelle. Une membership seule ne suffit pas.

### Projection locale

Identité/session déjà connue ; contexte UX local récupérable. Toute autorité doit être revalidée.

### Sections / hiérarchie

Pattern court :

- avatar + nom ;
- contexte courant ;
- contextes autorisés seulement si un handoff réel existe ;
- compte/paramètres ;
- sécurité/appareils si contrat mobile démontré ;
- déconnexion.

### Agir comme

A2 ne crée pas un mode act_as_space.

Le runtime personnel rejette précisément les overrides d'autorité fournis par le client. L'inventaire /organizations/workspaces/ prouve qu'un Espace est accessible ; il ne définit pas à lui seul une mutation de contexte.

Règle :

- si un contrat de handoff/shell Espace mobile est disponible au moment P1, le brancher ;
- sinon ne pas afficher un sélecteur qui promet un changement non supporté.

### Empty

Pas de contextes d'Espace autorisés = identité Profile normale, pas erreur.

### Offline

Compte courant identifiable ; aucune nouvelle autorité ; logout suit la politique A1 de protection des données locales.

### Back

Bottom sheet se ferme avant de quitter l'onglet courant.

### Resume

Ne pas changer d'acteur implicitement.

### Accessibilité

Bottom sheet ordonné, cibles larges, contexte courant annoncé.

### Limite A3+

Gestion détaillée des appareils, sécurité, facturation ou shell Espace selon leurs contrats réels.

## 8. Notifications — surface secondaire conditionnelle

Backend vérifié :

- list ;
- unread filter/count ;
- detail ;
- mark read.

A2 ne la construit que si :

- une destination stable existe ;
- le header la route ;
- la lecture est bornée ;
- le cache local/refresh est défini ;
- le deep-link mapping est testé.

Sinon : pas d'icône.

## 9. Conversations — surface secondaire conditionnelle

Backend vérifié : collection /api/v1/conversations/ et owner scope.

A2 ne construit pas un chat générique par simple conformité au header Mature.

Si le slice entre dans A2 :

- liste courte ;
- état local connu ;
- draft local ;
- envoi distant ;
- navigation structurée ;
- back/resume préservés.

Sinon : pas d'icône morte.

## 10. Règle de texte utilisateur

Interdit :

~~~text
projection locale
owner
schema
outbox
payload
backend
A1
A2
Readiness.WAITING
JourneyStatus.PENDING_APPROVAL
~~~

Préférer le langage de la situation :

- Tout est en ordre. ✓
- Vous avez fait votre part. Ça suit son cours.
- Tout est prêt pour la suite.
- Un point doit être réglé avant de continuer.

Ces phrases ne sont pas des strings globales obligatoires : elles ne sont utilisées que lorsque les faits serveur les justifient.
