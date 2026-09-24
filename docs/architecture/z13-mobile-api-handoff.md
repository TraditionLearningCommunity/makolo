# Z13 — Contrat final Web ↔ API ↔ Flutter et handoff mobile

> Statut : contrat de fermeture du programme Z pour le handoff mobile.
> Base de départ auditée : `main@e0bfdc0427bf20f1795ebbeac0070a35f720bf1d`, après intégration de Z12+.
> Le runtime courant reste toujours la source de vérité si ce snapshot vieillit.

## 1. Problème utilisateur et objectif

Makolo doit pouvoir devenir une application mobile sans demander à Flutter de reconstruire la signification métier depuis les modèles Django, les pages HTML ou des conventions implicites.

Z13 ferme donc le contrat de consommation :

```text
domaines canoniques
  → selectors / services / Readiness / autorisation propriétaires
  → projections et owner APIs
  → links + capabilities
  → Flutter
```

Règle :

> **Le serveur décide ce que la réalité signifie et ce qui est permis. Flutter présente, navigue et conserve seulement l’état visuel/local nécessaire.**

Z13 ne crée pas un nouveau domaine, un modèle mobile, une Readiness mobile, une copie d’Access, un wallet universel, un `/api/v1/mobile/`, un moteur de ranking, un provider de paiement ou une nouvelle vérité persistante.

## 2. Contrat de travail

- Owner : intégration Backend/API ↔ mobile.
- Base : `main@e0bfdc0427bf20f1795ebbeac0070a35f720bf1d`.
- Branche : `task-z13-mobile-api-handoff`.
- Écriture prévue : documentation du contrat et tests de transport/route bornés.
- Interdit : modèles métier, migrations métier, duplication des selectors, contournement Permission/Mandate/Access, invention d’URL de production ou d’identifiants natifs.
- Gate : tests ciblés, migration check via CI, CI complète verte, réconciliation avec le `main` courant puis merge vert.

## 3. Audit d’entrée

Z6 à Z12 sont présents dans le runtime de départ. Z12+ est intégré par la PR #285.

Le contrat Z courant expose notamment :

- `/api/v1/me/` — Moi Mature ;
- `/api/v1/me/now/` — Maintenant ;
- `/api/v1/me/ongoing/` — En cours ;
- `/api/v1/me/mark/` — Makolo Mark ;
- `/api/v1/discovery/items/` — Discover Mature multi-famille ;
- les profondeurs Journey, Requirement, Access, History, Jour J, Passport, Resources, Groups et Partner ;
- les owner APIs Activity, Occurrence, Objectives, Operations Live, Questionnaires, Recognition, Loyalty, Payments, Ticketing, etc.

Le bootstrap d’authentification reste `GET /api/v1/accounts/auth/me/`. Il ne doit jamais être confondu avec `GET /api/v1/me/`, qui est la surface Mature Moi.

Le Web Mature garde sa propre composition. En particulier :

```text
Web /me/          = Maintenant
API /api/v1/me/   = Moi
API /api/v1/me/now/ = Maintenant
```

Ce décalage de chemin est volontaire et doit être traité par le routeur Flutter, pas “corrigé” par heuristique.

## 4. Collision audit

Branches/PR ouvertes au réaudit :

- #284 Pré-8 : documentaire, sans collision d’écriture avec Z13 ;
- #283 Actor 6 closure : documentaire ;
- #270 ECC : documentation d’orchestration ;
- #252 Space archetypes : profondément divergente et hors surfaces Z13 ;
- #248 A0 Flutter : profondément divergente, `10` commits devant et `478` derrière le `main` de départ ;
- #272 ancien Z7 : historique/divergent ;
- #223 recherche : hors runtime Z13.

La branche A0 ne doit donc pas être fusionnée telle quelle. Sa petite fondation visuelle peut être réinterprétée ou transplantée lors d’A1, mais son inventaire API historique est obsolète.

## 5. Répartition serveur / Flutter

Le serveur reste propriétaire de :

- visibilité et divulgation minimale ;
- Permission, Mandate et contexte d’action ;
- validité Access et disponibilité de l’AccessCredential ;
- Readiness, Requirement satisfaction et blockers ;
- Capacity, Placement, Live Queue et Checkpoints ;
- état Payment / Commerce ;
- inclusion dans Maintenant, continuité En cours et Historique ;
- capabilities et owner handoffs ;
- états `unknown`, `waiting`, `blocked`, `planned`, `estimated`, `observed`.

Flutter possède :

- layout, animation, iconographie et accessibilité ;
- navigation locale entre écrans ;
- état de chargement, sélection, scroll et saisie non soumise ;
- secure storage natif pour les tokens ;
- cache éphémère de présentation lorsque le contrat de confidentialité le permet ;
- stratégie de rafraîchissement réseau sans inventer de vérité métier.

Flutter ne doit jamais déduire une action depuis un texte, un Membership, un Assignment, un statut visuel ou un identifiant obtenu ailleurs.

## 6. Identité, enveloppe et version

Les projections Z gardent :

```json
{
  "meta": {
    "projection": "personal.now",
    "schema_version": 1,
    "generated_at": "2026-09-24T10:00:00+02:00",
    "scope": "personal"
  },
  "data": {}
}
```

Contrats de transport :

- UUID métier → chaîne ;
- Decimal / argent → chaîne décimale, jamais float ;
- datetime → ISO-8601 timezone-aware ;
- date seule → `YYYY-MM-DD`, jamais minuit inventé ;
- enum → code machine stable, label éventuel séparé ;
- collection connue vide → `[]` ;
- absence connue → `null` ;
- fait légitimement inconnu → état `unknown` explicite ;
- secret caché → omission ou 404 selon le owner, pas faux `unknown`.

Une identité canonique utilise `kind + id`. Une `key` de projection est opaque ; Flutter ne la parse pas pour retrouver une table, une route ou une permission.

A1 doit accepter les champs additifs inconnus de schema v1. Une future rupture de sens/forme exige une version explicite ; le client ne doit pas “deviner” comment interpréter une version qu’il ne supporte pas.

## 7. Links, capabilities et TOCTOU

`links` indique où poursuivre. `capabilities` indique ce qui est permis au moment de la projection.

Flutter :

- suit un lien API fourni au lieu de reconstruire une URL depuis un UUID ;
- n’affiche comme action métier active qu’une capability correspondante ;
- ne considère jamais une capability comme une autorisation durable.

Chaque mutation revalide serveur-side l’autorité et l’état courant. Une capability peut donc devenir invalide entre lecture et action.

Une capability sans API mobile consommable n’autorise pas Flutter à POSTer un formulaire HTML. Le cas Groupes est explicitement documenté comme gap ci-dessous.

## 8. Matrice de handoff principale

| Expérience | Web Mature | API canonique | Owner principal | Règle Flutter |
| --- | --- | --- | --- | --- |
| Maintenant | `/me/` | `GET /api/v1/me/now/` | composition personnelle + owners | rendre `items`; `[]` peut afficher « Tout est en ordre. ✓ » |
| Découvrir | `/discover/` | `GET /api/v1/discovery/items/` | Discovery + familles propriétaires | recherche/exploration ; pas de ranking local |
| Makolo Mark | `/mark/` | `POST /api/v1/me/mark/` | orchestration + owner handoff | envoyer intention textuelle ; suivre le handoff |
| En cours | `/me/ongoing/` | `GET /api/v1/me/ongoing/` | composition personnelle + owners | conserver le fil ; attendre ≠ bloqué |
| Moi | `/me/moi/` | `GET /api/v1/me/` | Profile + owners personnels | hub personnel, pas dump du compte |
| Journey | `/me/journeys/<id>/` | `GET /api/v1/me/journeys/<id>/` | Journey / Readiness | utiliser forms, requirements, links et capabilities serveur |
| Access | `/me/accesses/<id>/` | `GET /api/v1/me/accesses/<id>/` | Access | droit ≠ credential |
| Jour J | contexte Occurrence | `GET /api/v1/me/occurrences/<id>/day-of/` | Occurrence + Access + Operations | grande surface contextuelle, pas sixième onglet |
| Live | contexte Jour J | `GET /api/v1/operations/occurrences/<id>/live/` | Operations | uniquement si owner/capability l’autorise |
| Historique | `/me/history/` | `GET /api/v1/me/history/` | projection Access/Journey | ouvrir les détails canoniques |
| Passport | Sharing Web | `GET /api/v1/me/passport/` | Profile/Sharing/Trust | projection ≠ Profile brut |
| Resources | Library Web | `GET /api/v1/me/resources/` | Personal Assets | document ≠ Requirement satisfait |
| Groupes | Group Web | `GET /api/v1/me/collectives/groups/<id>/` | Groups + Authorization | Membership ≠ authority |
| Recognition | dashboard owner | `GET /api/v1/recognition/me/` | Recognition | économie distincte |
| Loyalty | dashboard owner | `GET /api/v1/loyalty/me/` | Loyalty | économie distincte |
| Partner | dashboard owner | `GET /api/v1/me/partners/<id>/` | Partner | relation ≠ autorité Space |
| Dossier / Project | owner Web | `GET /api/v1/objectives/dossiers|projects/<id>/` | Objectives | aucun task manager générique |

Aucun namespace `/api/v1/mobile/` n’est créé.

## 9. Parcours consommateurs minimaux

### Maintenant → détail → action → refetch

Flutter charge Maintenant, prend la ressource canonique et les `links`, ouvre la profondeur propriétaire, exécute uniquement la mutation exposée, puis recharge la projection concernée.

Le résultat d’une mutation ne doit pas être utilisé pour simuler localement une nouvelle Readiness.

### Découvrir → conserver / engager

`PUT|DELETE .../saved/` représente explicitement la conservation. Une Veille est distincte. Un engagement suit le owner handoff exposé par la possibilité ; Flutter ne crée pas arbitrairement une Journey.

### Journey → Form → Readiness

Le Journey detail fournit les demandes de formulaire réellement actionnables. Après save/submit, Flutter recharge le Journey ou Maintenant/En cours. Il ne marque jamais un Requirement comme satisfait à partir de la seule présence d’une réponse ou d’un document.

### Access → Jour J → Credential / Live

Access ouvre Jour J lorsque l’Occurrence pertinente existe. Jour J distingue planned/estimated/observed/unknown. Le credential n’est chargé que par sa profondeur protégée. Live reste Operations.

### Historique → détail

Historique donne des références Journey/Access et leurs vrais liens. Il n’est pas un journal générique de notifications ou d’audit.

## 10. Mutations, retries et idempotence

| Mutation | Contrat de retry |
| --- | --- |
| Save/unsave Discover `PUT/DELETE` | état explicite ; rejouable comme opération d’état |
| Création de Veille `POST` | pas de clé d’idempotence générique ; **pas de retry aveugle** ; relire/reconcilier après résultat réseau ambigu |
| Form save | mise à jour owner-backed ; relire avant répétition si résultat ambigu |
| Form submit | terminal et sans clé d’idempotence client ; **pas de retry aveugle** |
| ActionProposal respond | décision terminale ; **pas de retry aveugle** ; refetch Now/détail |
| Recognition reward redeem | `idempotency_key` obligatoire ; réutiliser la même clé pour la même intention |
| Recognition accept/decline | décision terminale ; refetch après résultat ambigu |
| Loyalty reward redeem | `idempotency_key` obligatoire ; réutiliser la même clé |
| Resource reuse | replay même version/Journey converge vers le même artifact owner-backed |
| Ticket order historique | conserver la même `idempotency_key` pour la même intention |
| Payment create | utiliser l’idempotence owner existante |
| Scanner | conserver `client_reference` pour le retry de la même tentative |

La rotation JWT impose aussi de sérialiser le refresh côté client : un même refresh ne doit pas être utilisé en parallèle comme s’il était immuable.

## 11. Pagination et bornage

Il n’existe pas une forme de pagination universelle à réinventer dans Flutter.

Contrats importants actuels :

- Discover Mature : `page/page_size`, maximum 50 ;
- Mes accès : `offset/limit`, défaut 24, maximum 50 ;
- Historique : `offset/limit`, défaut 24, maximum 50 ;
- Resources : `offset/limit`, défaut 24, maximum 50 ;
- En cours : projection supérieure bornée à 18 ;
- Moi : previews bornées ; profondeurs séparées ;
- Activity detail : Occurrences bornées à 50 avec signal de suite.

Le client lit la pagination fournie par chaque owner ; il ne suppose ni liste infinie ni chargement complet.

## 12. Erreurs

Les projections et erreurs transversales Z utilisent prioritairement :

```json
{
  "error": {
    "code": "validation_error",
    "message": "Les données fournies sont invalides.",
    "fields": {}
  }
}
```

Flutter utilise `code` pour la logique et traite `message/fields` comme présentation.

Certaines owner APIs historiques conservent encore leurs formes propres, notamment `detail` ou `errors`. Le client A1 doit isoler cette compatibilité dans la couche HTTP ; il ne doit pas faire remonter plusieurs conventions jusqu’aux écrans.

Un état métier valide `waiting`, `blocked`, `unknown`, `needs_confirmation` ou `forbidden` peut être une réponse HTTP 200 lorsque le contrat owner le définit ainsi.

## 13. Auth, confidentialité et cache

- Bearer JWT pour le client natif ;
- access token courant : 15 min ;
- refresh courant : 7 jours, rotation + blacklist ;
- tokens uniquement dans un secure storage natif ;
- aucune PII, token, QR complet, credential, réponse privée ou payload Payment dans logs/crash breadcrumbs ;
- les réponses personnelles `private, no-store` ne deviennent pas un cache durable hors-ligne par commodité ;
- logout : oublier tokens et état personnel sensible local ;
- un autre Profile ne peut jamais être choisi par `profile_id`, `user_id` ou autre override sur les surfaces personnelles ;
- un objet privé hors scope peut répondre 404 afin de ne pas confirmer son existence.

## 14. Jour J, Live et faible connectivité

Jour J est contextuel à une Occurrence actuelle ; ce n’est pas un sixième élément permanent de navigation.

Operations expose aussi :

`GET /api/v1/operations/occurrences/<id>/offline-action-pack/`

Ce pack est un snapshot de lecture viewer-aware :

- schema `operations.offline_action_pack` v1 ;
- fraîcheur courte et expiration bornée ;
- credentials, contacts, paiement, QR brut, secrets, action URLs et historique de localisation sont retirés ;
- il n’accorde jamais d’autorité ;
- toutes les mutations doivent être revalidées par le serveur.

Ce contrat peut être consommé plus tard pour A4/faible connectivité. Il ne justifie pas un moteur de mutations offline ni un `last write wins` pour Access ou Payment.

Aucun WebSocket/SSE générique n’est canonique aujourd’hui. Flutter peut rafraîchir les GET selon son contexte UX, mais ne doit pas inventer une fréquence comme vérité métier.

## 15. Notifications et deep links

Le serializer Notification courant fournit `action_url`, `metadata` et une `navigation` structurée limitée aux identifiants historiques Event/Order/Payment/Ticket.

Il n’existe pas encore de contrat de navigation structuré couvrant toutes les ressources Mature, ni de configuration native versionnée pour :

- Android App Links / `assetlinks.json` ;
- iOS Universal Links / `apple-app-site-association` ;
- schème natif Makolo ou identifiants d’application.

A1 doit donc :

1. préférer les `links` API et `kind/id` fournis par les projections lorsqu’il navigue depuis Makolo ;
2. ne pas parser une URL HTML pour dériver une permission ou un état ;
3. ajouter les universal/app links uniquement après décision réelle sur domaine et identifiants natifs.

Z13 n’invente aucune de ces valeurs.

## 16. Moi : profondeurs et frontières

### Passport

Variants actuels : public, complete, thematic, custom. Le client peut sélectionner une projection ; il ne sérialise pas le Profile brut.

La capability `present` existe, mais aucune API dédiée de création de ShareEnvelope mobile n’a été démontrée dans le runtime Z13. Flutter ne doit pas fabriquer un secret/lien de partage.

### Resources

Lecture, détail, download et reuse sont disponibles. Reuse crée un JourneyArtifact snapshot et ne satisfait jamais un Requirement par lui-même.

Aucune API Mature générique d’upload mobile Personal Asset n’est présente. La caméra/document natif reste donc hors contrat A1 tant qu’un owner endpoint n’est pas livré.

### Groups

Le détail personnel expose Membership, authority et capabilities owner-backed. Plusieurs actions de gestion pointent encore vers des routes Web. Flutter peut afficher la relation et les droits, mais ne POSTe pas ces formulaires HTML. Les mutations Group mobile attendent une vraie owner API.

### Recognition / Loyalty / Partner

Ces domaines restent séparés. Il n’existe ni solde universel ni total financier inter-devises. Une relation Partner ou Loyalty n’accorde aucune autorité Space.

## 17. Paiement

Le mobile consomme seulement ce que Payments expose réellement.

Le runtime auditée connaît les providers `sandbox` et `manual`; `manual` est une capacité contrôlée. Aucun provider de production réel n’est déduit ou documenté par Z13.

Journey detail n’invente pas une capability `pay` si aucune mutation consommable n’est réellement disponible pour ce contexte.

## 18. Évaluation A0

La branche historique #248 apporte une preuve utile de direction :

- structure Flutter minimale ;
- Material 3 ;
- palette Makolo correcte ;
- navigation Maintenant · Découvrir · Makolo · En cours · Moi ;
- aucun modèle métier mobile parallèle.

Elle n’est toutefois pas une base intégrable : au réaudit Z13 elle est `10` commits devant mais `478` derrière `main`, et son document API précède Z1–Z12.

Décision Z13 : **A1 repart du `main` courant après fermeture Z13.** La petite fondation A0 peut être transplantée sélectivement si elle reste utile ; son historique ne doit jamais écraser le contrat Mature.

## 19. Gaps explicitement laissés au bon propriétaire

Ces gaps ne sont pas masqués par Flutter :

- pas d’upload Personal Asset Mature générique ;
- mutations de gestion Group non exposées comme owner API mobile ;
- pas d’API ShareEnvelope Passport mobile démontrée ;
- navigation Notification Mature incomplète ;
- pas de universal/app links versionnés ;
- pas de transport realtime générique ;
- création de Veille et plusieurs décisions terminales non blind-retry ;
- pas de provider Payment production à inventer ;
- Mark n’accepte pas un fichier générique comme modalité ;
- aucune autorité offline dérivée d’un snapshot.

Ils ne justifient ni nouveau domaine ni copie de vérité. Ils seront ouverts uniquement quand un scénario A1/A2/A4 réel en a besoin.

## 20. Gate A1

A1 peut commencer lorsque Z13 est merged sur un `main` vert et peut s’appuyer sur ce contrat sans interpréter le schéma Django.

Le premier client doit au minimum pouvoir implémenter :

```text
login/refresh/logout
→ Maintenant
→ Découvrir
→ Mark
→ En cours
→ Moi
→ profondeur Journey/Access/Jour J
→ owner mutation quand capability + link existent
→ refetch
```

A1 ne doit pas commencer depuis la branche A0 historique, ni créer un namespace backend mobile parallèle.

## 21. Evidence et migrations

Les régressions Z1, Z10, Z11 et Z12 couvrent déjà l’enveloppe, la continuité inter-surfaces, les IDOR/no-store, l’idempotence owner-backed et le coût des projections.

Z13 ajoute un test de transport léger qui fige :

- auth `me` distinct de Mature Moi ;
- les cinq surfaces principales ;
- Journey → Jour J → Operations Live ;
- l’absence de `/api/v1/mobile/` ;
- `schema_version = 1`.

Aucune migration n’est requise par Z13.
