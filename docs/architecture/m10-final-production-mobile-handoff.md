# M10.2 — Fermeture finale Production Gate & Mobile Handoff

> **Statut : contrat de fermeture de M10 côté dépôt.**
>
> Base auditée au démarrage de M10.2 : main@33f189f07b5e46769e39dc77f8cc85257523a17d.
>
> Le code, les migrations, les tests et le main courant restent prioritaires si ce document vieillit.

## 1. Objet

M10.2 ferme le handoff entre Makolo Mature Core/Web/API et le futur client mobile natif sans démarrer le programme A.

La cible de M10 reste :

> **Makolo Mature est un produit complet backend + web + API même si aucune application mobile native n'existait jamais.**

M10.2 ne crée aucun namespace /api/v1/mobile/, aucun modèle métier mobile, aucun état Readiness parallèle, aucune autorité locale/offline, aucune application Flutter et aucun provider de production inventé.

PythonAnywhere reste l'environnement bêta/test temporaire documenté. Aucune cible de production finale n'est déduite de ce chantier.

## 2. Correction runtime finale : authentification Web

L'audit bêta anonyme a mis en évidence une erreur 500 sur /library/.

La cause dans le dépôt était un alias d'authentification global invalide :

~~~
LOGIN_URL = "accounts:login"
LOGOUT_REDIRECT_URL = "accounts:login"
~~~

Le namespace Web Accounts réel ne fournit pas cette route. La connexion canonique Mature est core:login, déjà utilisée par la majorité des surfaces Web.

M10.2 aligne donc :

~~~
LOGIN_URL = "core:login"
LOGOUT_REDIRECT_URL = "core:login"
Operations Staff login_url = "core:login"
~~~

Le changement est couvert par des régressions anonymes sur Bibliothèque et Operations.

Le 500 observé en bêta sur /me/ ne correspond pas au code courant : MatureParticipantHomeView utilise déjà explicitement core:login. Cela constitue une preuve que l'environnement bêta observé doit être redéployé sur le SHA courant avant d'être utilisé comme preuve de release.

## 3. Contrat API canonique du client natif

Les cinq destinations permanentes restent :

| Surface | Contrat |
| --- | --- |
| Maintenant | GET /api/v1/me/now/ |
| Découvrir | GET /api/v1/discovery/items/ |
| Makolo Mark | POST /api/v1/me/mark/ |
| En cours | GET /api/v1/me/ongoing/ |
| Moi | GET /api/v1/me/ |

Le bootstrap d'identité est distinct : GET /api/v1/accounts/auth/me/.

Les profondeurs owner-backed déjà livrées incluent notamment :

| Domaine / profondeur | Contrat principal | Règle |
| --- | --- | --- |
| Journey | GET /api/v1/me/journeys/<id>/ | scope participant serveur |
| Requirement d'une Journey | GET /api/v1/me/journeys/<journey>/requirements/<assessment>/ | owner Requirement |
| Activity | GET /api/v1/activities/<id>/ | projection viewer-aware |
| Occurrence | GET /api/v1/occurrences/<id>/ | projection viewer-aware |
| Dossier | GET /api/v1/objectives/dossiers/<id>/ | scope Objectives |
| Project | GET /api/v1/objectives/projects/<id>/ | scope Objectives |
| Access | GET /api/v1/me/accesses/ et détail | Access décide le droit |
| AccessCredential | GET /api/v1/me/accesses/<id>/credential/ | sensible, scope bénéficiaire |
| Historique | GET /api/v1/me/history/ | projection personnelle |
| Jour J | GET /api/v1/me/occurrences/<id>/day-of/ | relation/Access pertinent |
| Live | GET /api/v1/operations/occurrences/<id>/live/ | scope Operations participant |
| Passport | GET /api/v1/me/passport/ | projection Profile/Sharing/Trust |
| Resources | GET /api/v1/me/resources/ et détail | controller scope |
| Resource download | GET /api/v1/me/resources/versions/<id>/download/ | privé |
| Resource reuse | POST /api/v1/me/resources/versions/<id>/reuse/ | revalide Journey |
| Group | GET /api/v1/me/collectives/groups/<id>/ | relation visible + Authorization |
| Partner | GET /api/v1/me/partners/ et détail | subject scope |
| Recognition | GET /api/v1/recognition/me/ | owner Recognition |
| Loyalty | GET /api/v1/loyalty/me/ | owner Loyalty |
| Notifications | /api/v1/notifications/ | identité/navigation structurée |
| Conversations | /api/v1/conversations/ | scope conversation serveur |

Le contrat schema_version = 1 demeure en vigueur.

## 4. Ce que le mobile doit déléguer au serveur

Le client natif peut gérer rendu, navigation, cache de présentation, saisie locale, états de chargement et capacités du téléphone.

Il ne doit jamais recalculer ou inférer comme vérité :

~~~
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
prix / total final
stock / Capacity
validité d'un credential
~~~

Une projection mobile suit links et capabilities, puis la mutation est toujours revalidée par le domaine propriétaire côté serveur.

## 5. Identité, autorité et contexte d'Espace

Le mobile doit conserver les invariants du backend :

~~~
Profile = personne globale
Assignment = responsabilité
Mandate / Permission = autorité
Membership != authority
~~~

Une action personnelle utilise le Profile courant.

Une action au nom d'un Espace doit être adossée au contexte d'autorité explicite fourni/revalidé par le serveur. Une Membership, une Team ou un Group ne suffit jamais à transférer une Permission ou un Mandate.

Aucune composition Dossier/Project/Journey/Group ne transfère implicitement Access, Payment, données privées ou autorité d'Espace.

## 6. Transport, erreurs, retry et confidentialité

Le contrat mobile courant conserve UUID en chaînes, Decimal/argent en chaînes décimales avec devise explicite, datetime ISO-8601 timezone-aware, pagination serveur, erreurs API normalisées, private/no-store sur les projections privées et ressources sensibles, ainsi que les idempotency keys là où le domaine en possède déjà.

Un retry aveugle n'est jamais autorisé sur une mutation qui ne possède pas de contrat d'idempotence.

## 7. No Orphan / No Orphan Media

Le client natif ne crée pas de feed, story, post ou média générique pour remplir une surface.

Discover reste la surface exploratoire de possibilités. Maintenant reste la surface privée de ce qui compte maintenant. Presentation représente les faits ; elle n'en devient pas propriétaire.

## 8. Classification des gaps A–F

Pour le handoff A, la classification est :

~~~
A = contrat backend requis avant de livrer la fonctionnalité mobile correspondante
B = responsabilité native/mobile, sans nouveau métier backend
C = profondeur mobile ultérieure / R&D
D = décision opérateur, provider ou produit externe
E = déjà résolu par Core/Web/API
F = inutile ou contraire à l'architecture
~~~

| Sujet | Classe | Décision M10 |
| --- | --- | --- |
| Auth + bootstrap identité | E | livré |
| cinq surfaces Maintenant/Découvrir/Mark/En cours/Moi | E | livré |
| owner links/capabilities + détails Journey/Access/etc. | E | livré |
| Group : lecture/detail mobile | E | livré |
| Group : mutations de gestion mobile dédiées | A | requis seulement quand A expose cette gestion |
| PersonalAsset : lecture/detail/download/reuse | E | livré |
| PersonalAsset : upload générique Mature mobile | A | requis avant l'upload natif générique |
| Passport : lecture | E | livré |
| ShareEnvelope : création/révocation dédiée mobile | A | requis avant gestion native du partage Passport |
| Interests/Open to : lecture dans Moi | E | livré |
| Interests/Open to : mutation dédiée si l'écran natif l'exige | A | à ajouter avec owner Topics, pas dans le shell |
| secure storage JWT natif | B | responsabilité A |
| Universal Links / Android App Links | B | après décision réelle bundle/domaines |
| push FCM/APNs, caméra, partage système | B | capacité appareil/provider |
| offline sync / autorité offline | C | ne pas simuler dans A1 |
| realtime générique | C | non requis pour fermer Core/Web |
| provider Payment final | D | aucune cible/provider inventé |
| hébergement Observer Browser/Chromium | D | optionnel, explicite, séparé |
| intelligence cumulative | C | hors chemin critique M10 |
| modalité fichier générique Mark | A | seulement si une expérience native la requiert |
| mode générique « Profile représentant un Space » | C | ne pas introduire pour contourner Mandate/Permission |
| namespace /api/v1/mobile/ | F | explicitement interdit |
| duplication des règles métier dans le client | F | explicitement interdite |

Conclusion : aucun gap A ne bloque la fondation A1 auth/navigation/cinq surfaces. Les gaps A listés bloquent uniquement les fonctionnalités natives correspondantes lorsqu'elles seront effectivement planifiées.

## 9. Disposition de l'ancienne PR A0 #248

La PR #248 est une expérimentation ancienne, très en retard sur main, et ne constitue pas le contrat mobile actuel.

Réutilisable sélectivement au démarrage de A : l'idée du shell à cinq destinations, l'identité visuelle si elle reste alignée, l'idée d'un smoke test mobile minimal et l'idée d'un workflow CI mobile séparé.

À réévaluer : versions Flutter/Dart, structure du package natif, workflow CI exact, gestion état/réseau/secure storage/deep links.

Obsolète : l'ancien audit API de mobile-phase-0-handoff.md, tout constat disant que Journey/Activity/Access/Personal projections manquent, ainsi que toute base SHA historique ou workflow qui diverge du main actuel.

La PR #248 ne doit pas être mergée telle quelle. Le programme A repartira du main fermé et pourra reprendre sélectivement les éléments utiles.

## 10. Providers et runtime

M10 ne choisit aucun provider fictif.

| Capability | État canonique |
| --- | --- |
| E-mail | backend Django, SMTP possible si configuré |
| Payment | sandbox/manual ; provider final non choisi |
| Cartographie | MapLibre + tile URL configurable |
| Observer HTTP/Browser | modes explicites, Browser non auto-activé |
| Intelligence | registry/capability ; non critique pour fermer M10 |
| Autopilot | worker persistant ou fallback scheduled, jamais les deux |

Le serveur Web PythonAnywhere installe requirements.txt uniquement. Les acteurs internes utilisent requirements-agents.txt, qui porte les dépendances Crawlee/Playwright.

## 11. Preuves bêta disponibles et limite

Des vérifications read-only de l'environnement PythonAnywhere ont établi que /api/v1/health/ répond ok, que /api/v1/readiness/ répond ready, que les principales surfaces publiques observées répondent sans erreur 500 et que les APIs privées anonymes observées renvoient 401 proprement.

L'environnement observé a cependant montré des 500 Web anonymes incompatibles avec le code actuel. Ces éléments ne prouvent donc pas que le SHA M10 final est déployé.

La preuve opérateur finale doit être faite après déploiement du SHA M10 final.

## 12. Gate opérateur externe avant déclaration d'une bêta RC déployée

À enregistrer pour l'environnement réellement utilisé :

1. SHA effectivement déployé ;
2. check --deploy ;
3. migrate --check et état migrations ;
4. health + readiness ;
5. mode Autopilot explicite ;
6. mode Observer explicite ;
7. backup récent + preuve de restore ;
8. espace disque/logs ;
9. smoke visiteur ;
10. smoke utilisateur authentifié ;
11. action personnelle ;
12. action au nom d'un Espace avec Mandate/Permission ;
13. Activity/Occurrence ;
14. Journey/Requirements/Readiness ;
15. Access/AccessCredential ;
16. Capacity lorsqu'elle est touchée ;
17. absence d'erreur 500 sur les surfaces critiques.

Aucun mot de passe, token, QR complet, credential ou PII ne doit être copié dans ce document.

## 13. Protection de main

Au démarrage de M10.2, GitHub expose toujours main comme non protégé et aucun ruleset n'est présent.

La connexion d'automatisation disponible dans ce chantier ne fournit pas d'action d'administration pour créer la protection. M10.2 n'invente donc pas un état de protection.

L'administrateur du dépôt doit activer une politique compatible avec les workflows réellement déclenchés. Un check path-filtered ou un check publié uniquement sur push ne doit pas être rendu obligatoire sur PR s'il peut ne jamais être créé.

## 14. Critères de sortie dépôt M10.2

Le dépôt est fermé pour M10.2 lorsque le bug de redirect Web est corrigé, les régressions ciblées sont vertes, aucune migration métier n'est ajoutée, makemigrations --check --dry-run reste propre, les contrats API A1 restent résolus sans namespace mobile parallèle, la matrice de handoff et les gaps A–F sont figés, la PR M10.2 est verte et mergée, puis le nouveau main repasse vert.

Les deux actions suivantes restent externes au code : déployer le SHA final sur l'environnement bêta choisi et exécuter le smoke authentifié ; activer la protection/ruleset de main avec des checks compatibles.

## 15. Handoff vers A Mobile

A peut commencer uniquement depuis le main M10 fermé.

Ordre de départ recommandé :

~~~
architecture native
→ navigation cinq surfaces
→ auth + secure storage
→ client API commun
→ Maintenant / Découvrir / Mark / En cours / Moi
→ owner depths via links/capabilities
→ mutations natives seulement lorsqu'un owner contract existe
~~~

Le mobile n'est pas une seconde implémentation de Makolo.

> **Le backend décide. Le client natif présente, orchestre et utilise les capacités du téléphone.**
