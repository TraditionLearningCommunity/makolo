# End-to-End Product Validation & UX Hardening

Cette passe complète les tests Django de Makolo par une validation navigateur réelle. Son objectif est de vérifier qu'un utilisateur peut suivre les parcours critiques sans connaître l'architecture interne, tout en détectant les régressions JavaScript, HTTP, CSP, responsive, clavier, accessibilité et visuelles.

## Architecture

La suite Playwright est volontairement légère :

- `playwright.config.mjs` : projets, viewports, traces, screenshots et vidéos sur échec ;
- `e2e/fixtures/` : fixture Makolo et surveillance des erreurs silencieuses ;
- `e2e/helpers/` : authentification, e-mail et assertions axe ;
- `e2e/specs/` : parcours produit lisibles par domaine ;
- `e2e/specs/visual.spec.mjs-snapshots/` : baselines visuelles Linux ;
- `scripts/e2e-env.sh` : variables du mode E2E ;
- `scripts/prepare-e2e.sh` : DB, migrations, fixtures, collectstatic et validation du manifest ;
- `scripts/run-e2e.sh` : serveur Django local, health check, Playwright et nettoyage ;
- `core/management/commands/prepare_e2e.py` : données navigateur déterministes.

Le mode `DJANGO_ENV=e2e` reste une variante localhost-safe de la configuration de production : `DEBUG=False`, WhiteNoise avec manifest strict, CSP réelle, assets buildés, e-mails fichier et paiement sandbox. Il ne modifie pas les protections de production et ne doit jamais viser la base PythonAnywhere.

## Pré-requis et commandes locales

Makolo utilise Python 3.10 et Node 24.18.0 dans la CI. Les dépendances Playwright sont strictement épinglées dans `package.json` et `package-lock.json`.

Première installation locale :

```bash
python -m pip install -r requirements.txt
npm ci
npm run build
npx playwright install --with-deps chromium firefox
```

Lancer la suite complète :

```bash
npm run test:e2e
```

Le runner prépare automatiquement une SQLite temporaire, les e-mails E2E, les fixtures, `collectstatic`, le manifest WhiteNoise, démarre Django sur localhost, attend le health check, lance Playwright et arrête le serveur à la fin.

Mettre à jour les baselines visuelles uniquement après avoir compris et validé le changement :

```bash
npm run test:e2e:update-snapshots
```

Ne jamais mettre à jour les snapshots uniquement pour faire passer une CI rouge. Il faut d'abord identifier la cause, vérifier visuellement le changement et ne conserver une nouvelle baseline que si le changement est volontaire.

## Données E2E

`python manage.py prepare_e2e` est refusé hors de `DJANGO_ENV=e2e`. La commande réinitialise uniquement la base E2E et crée des données fictives déterministes. Le mot de passe partagé est volontairement fictif et réservé aux tests :

```text
Makolo-E2E-2026!
```

Principaux comptes :

| Rôle / cas | Compte |
|---|---|
| Participant | `participant@e2e.makolo.test` |
| Participant vide | `empty.participant@e2e.makolo.test` |
| Profil | `profile.user@e2e.makolo.test` |
| Reset password | `reset.user@e2e.makolo.test` |
| Suppression autorisée | `delete.me@e2e.makolo.test` |
| Dernier propriétaire | `sole.owner@e2e.makolo.test` |
| Owner | `owner@e2e.makolo.test` |
| Event Manager | `event.manager@e2e.makolo.test` |
| Finance | `finance@e2e.makolo.test` |
| Marketing | `marketing@e2e.makolo.test` |
| Agent scanner | `scanner@e2e.makolo.test` |
| Multi-rôle | `multi.role@e2e.makolo.test` |
| Organisateur neuf | `new.organizer@e2e.makolo.test` |
| Staff Makolo | `staff@e2e.makolo.test` |

Les fixtures comprennent une organisation active, une organisation sans événement, plusieurs événements publics/futurs, une billetterie achetable, un événement avec gate et affectation scanner, ainsi que des données Operations demo et live distinctes. Elles réutilisent les services métier lorsque c'est pertinent et ne copient pas le gros seed demo.

## Matrice des parcours couverts

| Profil | Entrée et parcours principaux | Contrôles d'accès |
|---|---|---|
| Visiteur | `/`, Découvrir, recherche, événement public, organisateur public, login, inscription, 404 | surfaces privées redirigent vers login avec `next` |
| Participant | dashboard, Pour vous, Favoris, achat, commande, paiement sandbox, billet, QR, Mes événements | outils organisation interdits par navigation et accès direct |
| Owner | dashboard organisation, création événement, publication, billetterie, catalogue | accès aux outils autorisés par les permissions existantes |
| Event Manager | événements, accès, CRM/Growth selon capacités, billetterie | pas de Finance ; accès direct vérifié |
| Finance | paiements/finance/analytics selon capacités | pas de création événement |
| Marketing | CRM/Growth/Promotions selon capacités | pas de création événement |
| Agent scanner | événement affecté, scanner, historique | aucun privilège organisateur indu |
| Multi-rôle | dashboard organisateur déterministe et union des capacités | absence de conflit de navigation |
| Staff Makolo | Operations Center | non-staff refusé directement |

Les états vides d'un participant neuf et d'un organisateur neuf vérifient également qu'une prochaine action utile reste visible.

## Parcours compte

La suite navigateur couvre :

- inscription invalide puis valide ;
- login invalide puis valide avec conservation de `next` ;
- mot de passe oublié depuis le vrai formulaire web ;
- lecture du vrai e-mail écrit par Django ;
- extraction et ouverture du lien de reset ;
- définition d'un nouveau mot de passe ;
- connexion avec le nouveau mot de passe ;
- refus de réutilisation du token ;
- modification et persistance du profil ;
- conservation des préférences SMS et Push existantes ;
- changement de mot de passe ;
- suppression et anonymisation d'un participant ;
- blocage de la suppression du dernier propriétaire d'une organisation.

## Paiement sandbox et billet

Aucune passerelle externe n'est appelée. Le scénario utilise exclusivement le provider sandbox existant de Makolo :

```text
événement → choix du billet → commande → sandbox → succès → commande confirmée → billet émis
```

Un second scénario annule une tentative sandbox puis vérifie qu'un retry reste possible sans perdre la commande.

## QR → scanner

Le parcours critique relie réellement les deux côtés du produit :

1. le participant achète le billet depuis l'UI ;
2. Playwright ouvre le billet et capture l'image QR réellement servie ;
3. l'agent scanner ouvre l'événement auquel il est affecté ;
4. la même image est fournie au fallback fichier ;
5. `qr-scanner` côté navigateur décode l'image ;
6. le serveur applique la validation scanner existante ;
7. le premier scan affiche `Accès autorisé` ;
8. la même image est soumise une seconde fois ;
9. le second scan est refusé comme billet déjà utilisé ;
10. l'historique contient les deux résultats et le billet du participant est marqué utilisé.

Le test n'appelle pas directement l'API scan avec le token.

La surface caméra vérifie également : permission refusée compréhensible, fallback image, fallback manuel et fonctionnement sans `BarcodeDetector`. Une fake caméra vidéo n'est pas un gate CI : le parcours QR par image, lui, est bloquant.

## Surveillance des erreurs silencieuses

La fixture Playwright fait échouer les pages critiques en présence de :

- `pageerror` JavaScript ;
- `console.error` inattendu ;
- asset critique en 404 ;
- réponse HTTP 500 inattendue ;
- violation CSP significative ;
- erreur frontend Alpine/HTMX ;
- ressource frontend manquante.

Les réponses contrôlées attendues par les tests 403/404/500 sont ciblées explicitement ; il n'existe pas de grosse allowlist générale.

Le garde-fou `npm run check:runtime-deps` interdit aussi les dépendances runtime CDN critiques, les scripts inline et les handlers HTML inline tels que `onclick` ou `onsubmit`.

## Accessibilité et clavier

`@axe-core/playwright` audite les surfaces représentatives avec un gate bloquant sur les violations `critical` et `serious`. La baseline actuelle ne contient aucune exception axe de ces niveaux.

Les tests couvrent notamment : home, login, inscription, dashboard participant, discovery, event detail, profil, billet, scanner, dashboard organisation, Operations et pages d'erreur représentatives.

Une passe clavier vérifie `Tab`, `Shift+Tab`, `Enter`, `Space` et `Escape`, y compris navigation, menu utilisateur et menu mobile. Le shell possède un lien d'évitement vers le contenu principal.

## Mobile, thèmes et régression visuelle

Projets Playwright :

- Chromium desktop : `1440 × 900`, suite complète ;
- Chromium mobile : `390 × 844`, scénarios mobiles critiques ;
- Firefox desktop : smoke ciblé sur les parcours publics/discovery.

La couverture visuelle contient 14 snapshots Linux représentatifs :

- light desktop : home, discovery, dashboard participant, dashboard organisateur, ticket, scanner, Operations ;
- dark desktop : dashboard participant, discovery, scanner ;
- mobile : home, discovery, dashboard participant, scanner.

Les animations sont désactivées pendant la comparaison, le curseur est masqué et seules les zones réellement dynamiques sont masquées (notamment le QR secret et un timestamp Operations). Les tests vérifient aussi l'absence d'overflow horizontal majeur. Le scanner desktop dispose d'un garde-fou supplémentaire vérifiant sidebar desktop, trigger mobile caché et zéro overflow avant la capture.

Le choix light/dark est testé via le vrai `localStorage` et doit persister après reload.

## Liens internes

Un crawl limité collecte les liens GET internes non destructifs sur les surfaces importantes (navigation, dashboard, profil, organisation). Il exclut logout, POST/destruction, API, fichiers et liens externes, puis bloque les 404, 500 et boucles de redirection.

## Erreurs produit

Les 403, 404 et 500 sont testées dans le navigateur. La 500 est déclenchée par une route synthétique disponible uniquement en `DJANGO_ENV=e2e`, ce qui permet de vérifier :

- page Makolo sans traceback ;
- action de sortie ;
- identifiant `MKL-*` ;
- présence du même identifiant dans le log serveur.

Cette route n'existe pas en production.

## CI GitHub Actions

Le workflow `CI` conserve le job Django existant et ajoute un job `e2e` séparé, en lecture seule. Le job E2E :

1. checkout ;
2. Python 3.10 ;
3. Node 24.18.0 ;
4. dépendances Python ;
5. `npm ci` ;
6. build frontend ;
7. vérification que `static/dist` est synchronisé ;
8. garde-fou runtime CSP/CDN/inline ;
9. `makemigrations --check --dry-run` ;
10. installation Chromium + Firefox ;
11. préparation DB/fixtures/collectstatic/manifest ;
12. Playwright ;
13. upload du rapport HTML, traces, screenshots, vidéos et log serveur uniquement en cas d'échec.

Le job Django reste la référence pour la suite unitaire/intégration Python. Playwright la complète et ne remplace aucun test Django.

## Débogage d'une CI rouge

Classer d'abord l'échec : produit, test, fixture ou race condition. Utiliser ensuite le rapport HTML, la trace, le screenshot, la vidéo et `/tmp/makolo-e2e-server.log`. Ne pas ajouter de `waitForTimeout(...)` arbitraire pour masquer un problème de synchronisation.

Pour une régression métier identifiée dans une vue, un formulaire, un service, un selector ou une permission, ajouter également un test Django ciblé lorsque cela apporte une protection plus proche de la cause.

## Production / PythonAnywhere

Playwright n'est pas un composant runtime Makolo. Il ne faut installer ni Playwright ni Chromium sur PythonAnywhere. La base E2E, les comptes E2E et le backend e-mail fichier ne sont utilisés qu'avec `DJANGO_ENV=e2e`.

Cette passe n'ajoute aucune migration métier, aucun service worker, aucune PWA, aucun nouveau worker serveur et aucune intégration externe de paiement/SMS/Push.

Après merge, un déploiement PythonAnywhere reste :

```bash
cd ~/makolo
source ~/.virtualenvs/makolo/bin/activate
git checkout main
git pull origin main
python manage.py check
python manage.py collectstatic --noinput
```

Puis `PythonAnywhere > Web > Reload`. Il n'est pas nécessaire de relancer le seed demo ni d'exécuter npm sur PythonAnywhere puisque `static/dist` reste commité et validé en CI.
