# Z14 — Fermeture du programme Z et readiness mobile

> **Statut : gate final de fermeture.**
> Base de départ : `main@2752357ed790b60f925da71042fcf9e7cbcbea3c`, merge de Z13 (#287).
> Date d'audit : 24 septembre 2026.
> Le runtime courant, les migrations, les tests et l'état GitHub gagnent toujours sur ce document.
>
> Le merge de la PR Z14 constitue la fermeture documentaire du programme uniquement si son dernier head est vert et si le `main` post-merge est revérifié.

## 1. Verdict de readiness

Le backend personnel Mature possède désormais un contrat suffisamment explicite pour être consommé par un client mobile sans reconstruire la logique métier.

```text
domain truths
→ owner selectors/services
→ UX projections/orchestration
→ API
→ clients
```

Z14 n'ajoute ni surface, ni domaine, ni modèle, ni intelligence, ni namespace mobile parallèle.

Décision de gate sur la base auditée :

```text
backend personal contract ready
→ mobile may start après les gates globaux applicables
```

Cette conclusion signifie **mobile-contract ready**, pas **production-ready**. M10 et les gates de production restent distincts du programme Z.

## 2. État vérifié Z0 → Z14

| Train | État vérifié | Preuve principale |
| --- | --- | --- |
| Z0 | audit initial absorbé dans le programme ; pas de PR autonome identifiée | contrat Z et audits Z3/Z6 |
| Z1 | intégré | PR #257 |
| Z2 | intégré | PR #260 |
| Z3 | intégré | PR #259 |
| Z4 | intégré | PR #261 |
| Z5 | intégré | PR #264 |
| Z6 | intégré, continuation incluse | PR #267 puis #271 |
| Z7 | intégré par la branche réconciliée | PR #274 ; ancienne PR #272 fermée comme supersédée |
| Z8 | intégré | PR #273 |
| Z9 | intégré | PR #276 |
| Z10 | intégré | PR #279 |
| Z11 | intégré | PR #277 |
| Z12+ | intégré | PR #285 |
| Z13 | intégré | PR #287 |
| Z14 | gate final | cette PR ; fermeture après CI + merge + vérification post-merge |

Aucune migration métier n'a été introduite par Z1–Z13. Z14 n'en introduit pas non plus.

## 3. Collision audit final

| PR ouverte | Classification Z14 |
| --- | --- |
| #248 — A0 Flutter | **needs adaptation** : base profondément divergente ; ne pas merger telle quelle. Réutilisation sélective seulement depuis le `main` fermé. |
| #252 — Space archetypes | chantier Space séparé ; ne bloque pas le contrat personnel Z. |
| #270 — ECC docs | documentation d'orchestration ; pas de collision métier Z14. |
| #283 — Actor 6 closure | documentaire ; pas de collision avec les surfaces personnelles. |
| #284 — Pré-8 actors/universe input | documentaire ; pas de collision Z14. |
| #223 — research lab | recherche isolée hors runtime personnel. |

L'ancienne PR Z7 #272 a été explicitement fermée comme supersédée par #274 déjà intégrée.

## 4. Surfaces personnelles finales

Navigation permanente :

```text
Maintenant | Découvrir | Makolo Mark | En cours | Moi
```

Surfaces contextuelles/profondes : Journey, Requirement/Readiness, Activity/Occurrence, Dossier/Project, Mes accès, Historique, Jour J, Makolo Live, Passeport, Ressources personnelles, Groupes, Recognition, Loyalty et Partner.

- Maintenant répond à « Qu'est-ce qui compte maintenant ? » et peut conclure « Tout est en ordre. ✓ ».
- En cours conserve le fil de ce qui est engagé ; Maintenant reprend la main lorsque l'intervention redevient utile.
- Découvrir reste un champ de possibilités, pas un feed de rétention ni un ranking universel.
- Makolo Mark orchestre et remet aux owners ; il ne devient ni owner, ni mémoire métier générale, ni chatbot universel.
- Moi reste un hub de capital personnel et relationnel utile, pas un dump de données.
- Jour J reste contextuel à une Occurrence actuelle et n'est pas une sixième destination permanente.
- Makolo Live reste sous `Occurrence → Jour J → Operations Live`.

## 5. Inventaire API personnel mobile-ready

Les capabilities sont calculées côté serveur ; les links servent de handoff vers la profondeur propriétaire.

| Méthode | Path | Auth / scope | Owner / projection | Bornage |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/me/now/` | auth, Profile courant | Maintenant + owners | sources/sections bornées |
| GET | `/api/v1/discovery/items/` | public/contextuel | Discovery + familles propriétaires | page/page_size, max 50 |
| POST | `/api/v1/me/mark/` | auth, Profile courant | Mark orchestration | input borné |
| GET | `/api/v1/me/ongoing/` | auth, Profile courant | En cours | max 18 |
| GET | `/api/v1/me/` | auth, Profile courant | Moi | previews bornées |
| GET | `/api/v1/me/journeys/<id>/` | auth, participant autorisé | Journey/Readiness | détail |
| GET | `/api/v1/me/journeys/<journey>/requirements/<assessment>/` | auth, Journey visible | Requirement owner | détail |
| GET | `/api/v1/activities/<id>/` | viewer-aware | Activity | Occurrences max 50 |
| GET | `/api/v1/occurrences/<id>/` | viewer-aware | Occurrence | détail |
| GET | `/api/v1/objectives/dossiers/<id>/` | auth/owner scope | Objectives | détail |
| GET | `/api/v1/objectives/projects/<id>/` | auth/owner scope | Objectives | détail |
| GET | `/api/v1/me/accesses/` | auth, relation explicite | Access | offset/limit 24, max 50 |
| GET | `/api/v1/me/accesses/<id>/` | auth, scope Access | Access | détail |
| GET | `/api/v1/me/accesses/<id>/credential/` | auth, bénéficiaire légitime | AccessCredential | sensible, no-store |
| GET | `/api/v1/me/history/` | auth, Profile courant | Journey/Access terminal | offset/limit 24, max 50 |
| GET | `/api/v1/me/occurrences/<id>/day-of/` | auth, relation/Access pertinent | Jour J | une Occurrence |
| GET | `/api/v1/operations/occurrences/<id>/live/` | auth + scope participant | Operations Live | une Occurrence |
| GET | `/api/v1/me/passport/` | auth | Profile/Sharing/Trust projection | projection |
| GET | `/api/v1/me/resources/` | auth, controller scope | Personal Assets/Trust | 24, max 50 |
| GET | `/api/v1/me/resources/<id>/` | auth, controller scope | Personal Assets | versions bornées |
| GET | `/api/v1/me/resources/versions/<id>/download/` | auth, controller scope | Personal Assets | un objet |
| POST | `/api/v1/me/resources/versions/<id>/reuse/` | auth, controller + Journey scope | Personal Assets → JourneyArtifact | owner-idempotent |
| GET | `/api/v1/me/collectives/groups/<id>/` | auth, relation visible | Groups + Authorization | détail |
| GET | `/api/v1/recognition/me/` | auth | Recognition | collections bornées |
| GET | `/api/v1/loyalty/me/` | auth | Loyalty | collections bornées |
| GET | `/api/v1/me/partners/` | auth | Partner | collection bornée |
| GET | `/api/v1/me/partners/<id>/` | auth, subject scope | Partner | détail |

Le bootstrap identité reste `GET /api/v1/accounts/auth/me/`, distinct de la surface Mature `GET /api/v1/me/`. Il n'existe pas de namespace parallèle `/api/v1/mobile/`.

Les APIs Event/Ticket/Scanner et certaines routes Event-shaped de bookmarks restent des compatibilités historiques. Z14 ne les supprime pas sans preuve de disparition de leurs consommateurs.

## 6. Invariants non négociables revalidés

```text
Profile = personne globale
Assignment = responsabilité
Permission / Mandate = autorité
Membership != authority
Readiness = projection dérivée

Requirement != Form != Resource != JourneyArtifact != Proof
Requirement != Credential Trust != AccessCredential
Access = droit
AccessCredential = représentation / secret
AccessUse = observation
Capacity = combien ?
Placement = où ?
Waitlist = attendre une place
Live Queue = attendre son tour
JourneyStep != Checkpoint
Dossier = objectif actif composé
Project = horizon durable
buyer != beneficiary
Partner relation != Space authority
Loyalty membership != Space authority
```

Posséder, retrouver, réutiliser ou transmettre un document ne signifie jamais satisfaire un Requirement. Une composition ne transfère jamais implicitement Permission, Mandate, Access, Payment ou accès à des données privées.

Presentation représente les faits ; elle ne les possède pas.

## 7. Sécurité, confidentialité et IDOR

Les preuves Z11 et les régressions Z2/Z5–Z10 confirment :

- sujet personnel = `request.user` ; les overrides d'acteur client sont refusés ;
- ressources privées étrangères opaques, généralement 404 selon le owner ;
- buyer distinct du beneficiary et sans accès au credential du bénéficiaire ;
- Membership/Assignment sans autorité implicite ;
- AccessCredential/QR/token absents des projections générales ;
- projections personnelles `private, no-store` selon contrat ;
- Resource reuse revérifie la Journey et ne satisfait pas un Requirement ;
- Recognition, Loyalty et Partner restent isolés ;
- aucune somme monétaire inter-devise ;
- mutations sensibles revérifiées côté serveur avec idempotence propriétaire lorsqu'elle existe.

La recherche de motifs de secrets accidentels n'a identifié ni clé AWS, ni clé privée, ni token GitHub committé. Les exemples de CI et `.env.example` sont synthétiques. Les seeds n'impriment pas la valeur du mot de passe.

## 8. Contrat de transport

`schema_version = 1` reste la version courante. UUID → string ; Decimal/argent → string décimale ; devise explicite ; datetime → ISO-8601 timezone-aware ; date-only → `YYYY-MM-DD` sans faux minuit ; `[]` = collection connue vide ; `null` = absence connue ; `unknown` reste explicitement inconnu.

Une addition rétrocompatible peut rester v1 ; une rupture de sens ou de forme exige une version explicite.

## 9. Continuités prouvées

Les tests Z10/Z11 couvrent notamment :

```text
Journey engagée → En cours → action utile → Maintenant + En cours
→ action exécutée → Maintenant disparaît → En cours continue

En cours → terminal → Historique
Discover → detail → owner engagement → En cours
Occurrence actuelle → Jour J → Operations Live / Access / Queue / Placement
Moi → Resource → reuse → JourneyArtifact
Mark → owner surface
```

Le dernier flux ne confère aucune identité parallèle ; Resource reuse ne satisfait jamais automatiquement Requirement.

## 10. Performance et stabilité

Z12+ reste la preuve propriétaire. Z14 ne refait pas un benchmark exhaustif. Bornes actuelles : Maintenant borné par source et section ; En cours 18 ; Discover max 50 ; Moi preview 6/sections 50 ; Mes accès 24/max 50 ; Historique 24/max 50 ; Resources 24/max 50, versions 20/max 50 ; Activity detail Occurrences max 50.

Z12 a corrigé les N+1 observés sans cache ni index spéculatif. Les GET principaux ne créent pas de vérité métier pour matérialiser une projection UX.

## 11. Migrations, CI et warnings

Inventaire Z1–Z13 : **aucune migration métier Z**. Z14 : aucune migration.

Gates verts sur le head Z13 avant merge : `check`, `makemigrations --check --dry-run`, migrations, full Django, PostgreSQL shards, E2E, Security supply chain, Beta seed validation, Funding PostgreSQL, Conversation PostgreSQL et Subscriptions.

Le `main` Z12+ précédent avait aussi une CI verte avec **2519 tests Django**.

Warnings lus et classés non bloquants : dépréciations Node `punycode`/`url.parse()` issues de toolchain ; warning GitHub Actions relatif à Node 20 forcé sur Node 24 ; warnings HTTP attendus des tests négatifs. Z14 ne lance pas une grosse mise à jour de dépendances pour les faire disparaître.

## 12. Flutter may / Flutter must not

### Flutter may

- afficher les cinq destinations permanentes ;
- charger les projections et profondeurs owner-backed ;
- suivre les `links` et afficher les actions correspondant aux `capabilities` ;
- gérer layout, loading, sélection, scroll, saisie locale et navigation ;
- conserver les tokens dans un secure storage natif ;
- refetch après mutation ;
- accepter les champs additifs inconnus compatibles schema v1.

### Flutter must not

Flutter ne doit jamais inférer :

```text
Permission
Mandate
Readiness
Requirement satisfaction
Access validity
Now membership
Ongoing membership
History inclusion
Live eligibility
Space authority
```

Il ne doit pas inventer une Journey depuis Discover, considérer un document comme Requirement satisfait, considérer un snapshot offline comme autorité, agréger Recognition/Loyalty/Partner, sommer des devises, parser une URL HTML pour dériver une permission ou porter de logique métier critique.

## 13. No Orphan et anti-rétention

L'audit n'a pas trouvé de nouveau FeedItem métier générique, wallet universel, score humain transversal, infinite scroll obligatoire, likes/streaks ou optimisation watch-time introduit par Z. Les contenus restent contextualisés ; le média reste attaché à un contexte autorisé ; Discover reste borné.

## 14. Gaps finaux

### BLOCKING

`0` sur la base auditée avant la CI propre de Z14. Tout échec CI du dernier head Z14 redevient BLOCKING.

### NON-BLOCKING

- quelques owner APIs historiques gardent une forme d'erreur différente du contrat Z transversal ;
- maintenance future des warnings Node/GitHub Actions ;
- routes legacy conservées tant que leurs consommateurs ne sont pas prouvés supprimables.

### FUTURE PROGRAM / owner futur

- mutations Group mobile dédiées ;
- upload Personal Asset Mature générique depuis mobile ;
- création ShareEnvelope Passport dédiée mobile ;
- Universal Links / Android App Links après décision réelle d'identifiants/domaines ;
- realtime natif/générique ;
- offline sync et autorité offline ;
- provider Payment de production ;
- modalité fichier générique Mark ;
- mode Profile représentant un Space ;
- intelligence cumulative / Univers Makolo.

Aucun de ces éléments ne doit prolonger artificiellement Z14.

> **Post-Z14 / M10.0 :** la navigation structurée Notification vers les identités Mature démontrées a été fermée dans le chantier M10.0 sans rouvrir Z.

## 15. Handoff vers A

La séquence canonique reste `M7 → M8 → M9 → M10 → A Mobile`. Le runtime a intégré M8, le hardening M9 puis le programme Z. Z14 ferme Z ; il ne déclare pas M10 ni Makolo production-ready.

Prochaine action mobile : partir du `main` fermé, pas de l'ancienne branche A0 ; reprendre sélectivement la fondation Flutter utile ; implémenter auth + les cinq surfaces via Z13 ; suivre links/capabilities ; garder toute décision métier critique côté serveur.

> **Le backend a fini d'expliquer Makolo aux clients. Le mobile peut maintenant commencer à l'incarner, sous réserve des gates globaux applicables.**
