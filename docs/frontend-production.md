# Frontend de production Makolo

Ce document décrit le pipeline frontend de Makolo après la passe **Frontend Production Hardening**. L'objectif est qu'une release déjà construite puisse être déployée sur PythonAnywhere sans Node/npm et sans exception spéciale à `collectstatic`.

## 1. Architecture

Les sources de build ne sont jamais placées dans `static/` :

```text
frontend/
├── src/
│   ├── styles.css       # entrée Tailwind
│   ├── app.js           # shell global HTMX + Alpine CSP + Lucide + thème
│   ├── theme-init.js    # initialisation précoce du thème
│   ├── scanner.js       # comportement UI du scanner web
│   └── live-access.js   # rafraîchissement Smart Access
├── tailwind.config.js
└── build.mjs

static/
├── css/
│   ├── makolo-ui.css
│   ├── makolo-compat.css
│   └── makolo-brand.css
└── dist/
    ├── makolo.css
    ├── makolo.js
    ├── theme-init.js
    ├── scanner.js
    ├── live-access.js
    ├── qr-scanner.umd.min.js
    └── qr-scanner-worker.min.js
```

`static/dist/` est **commité**. C'est volontaire : PythonAnywhere reçoit les artefacts de release via `git pull` et n'a pas besoin de Node.

`frontend/.generated/` est temporaire et ignoré. Le build y génère le registre minimal d'icônes Lucide réellement utilisées dans les templates.

## 2. Dépendances verrouillées

Les versions directes sont exactes dans `package.json` et résolues par `package-lock.json` :

Runtime navigateur :

- `@alpinejs/csp` `3.15.12`
- `htmx.org` `1.9.12`
- `lucide` `1.27.0`
- `qr-scanner` `1.4.2`

Build uniquement :

- `tailwindcss` `3.4.19`
- `esbuild` `0.28.1`

Ne pas utiliser `latest`, `^`, `~` ou des plages `x.x` pour les dépendances directes.

## 3. Build local

Prérequis développeur : Node correspondant à la version CI et npm.

```bash
npm ci
npm run build
```

Le build :

1. compile et minifie Tailwind vers `static/dist/makolo.css` ;
2. détecte les icônes `data-lucide` des templates ;
3. génère un registre Lucide tree-shaké ;
4. bundle/minifie le shell vers `static/dist/makolo.js` ;
5. minifie les scripts scanner et Smart Access ;
6. copie le runtime et le worker `qr-scanner` à côté l'un de l'autre ;
7. ne produit pas de sourcemaps de production.

Après modification de `frontend/`, des templates qui utilisent de nouvelles classes Tailwind ou de nouvelles icônes, ou d'une dépendance frontend, exécuter `npm run build` et commiter le diff de `static/dist/`.

## 4. Tailwind

Makolo n'utilise plus `cdn.tailwindcss.com`.

La source Tailwind est `frontend/src/styles.css`, hors de `STATICFILES_DIRS`. Cela supprime l'ancien cas où `static/css/input.css` contenant une directive de build était traité par `ManifestStaticFilesStorage` pendant `collectstatic`.

`frontend/tailwind.config.js` :

- utilise `darkMode: 'class'` ;
- conserve les couleurs et familles de fontes Makolo ;
- scanne les templates Django et les sources JS ;
- n'utilise pas de safelist globale artificielle.

Si une classe devient réellement dynamique et non détectable, préférer d'abord une classe explicite dans le template/source. Ajouter une safelist ciblée uniquement si la dynamique est incontournable.

## 5. CSS Makolo historique

`makolo-ui.css`, `makolo-compat.css` et `makolo-brand.css` restent des fichiers locaux distincts. Cette stratégie limite le risque de régression visuelle pendant le durcissement de production. Ils sont tous validés dans le manifest WhiteNoise.

Les imports Google Fonts ont été retirés. Les familles `Inter` et `Manrope` restent des préférences de CSS si elles existent localement sur le système, puis tombent immédiatement sur une stack système robuste. Aucune police distante n'est nécessaire au rendu fonctionnel.

## 6. JavaScript global

`static/dist/makolo.js` contient uniquement le shell partagé :

- HTMX ;
- Alpine **CSP build** ;
- le sous-ensemble Lucide effectivement utilisé ;
- la gestion du thème ;
- le rafraîchissement des icônes après les swaps HTMX.

Le script de thème précoce est séparé dans `theme-init.js` afin d'appliquer le thème avant le rendu sans JavaScript inline.

Le code scanner et le rafraîchissement Smart Access ne sont pas chargés sur les pages ordinaires.

## 7. Scanner

La logique serveur du scanner n'est pas modifiée.

La console scanner charge seulement sur sa page :

- `qr-scanner.umd.min.js` ;
- `scanner.js` ;
- `qr-scanner-worker.min.js` à la demande du moteur QR.

Smart Access charge séparément `live-access.js` pour son rafraîchissement périodique, sans script inline.

Le parcours conserve : caméra, sélection de caméra, lampe si disponible, moteur QR logiciel, fallback `BarcodeDetector`, lecture d'image, saisie manuelle et validation côté serveur Makolo.

Le worker reste dans le même dossier que le runtime QR pour conserver la résolution relative prévue par la bibliothèque.

## 8. CSP et headers navigateur

Makolo applique une CSP first-party :

```text
default-src 'self';
base-uri 'self';
connect-src 'self';
font-src 'self';
form-action 'self';
frame-ancestors 'none';
frame-src 'none';
img-src 'self' data: blob:;
media-src 'self' blob:;
object-src 'none';
script-src 'self';
style-src 'self' 'unsafe-inline';
worker-src 'self' blob:
```

`script-src` ne contient ni `unsafe-inline` ni `unsafe-eval`.

`style-src 'unsafe-inline'` est conservé temporairement parce que les templates Makolo existants contiennent encore de nombreux attributs `style=` first-party. Les supprimer relève d'une passe visuelle/accessibilité plus large ; cela ne justifie aucun relâchement de la politique script.

Headers complémentaires :

- `X-Content-Type-Options: nosniff` ;
- `Referrer-Policy: same-origin` ;
- `X-Frame-Options: DENY` en complément de `frame-ancestors 'none'` ;
- `Permissions-Policy: camera=(self), microphone=(), geolocation=()` ;
- cookies secure, redirection HTTPS et HSTS restent pilotés par l'environnement production existant.

La caméra est donc autorisée uniquement à l'origine Makolo.

## 9. WhiteNoise et collectstatic

La production utilise toujours :

```text
whitenoise.storage.CompressedManifestStaticFilesStorage
```

La commande standard est la seule commande supportée :

```bash
python manage.py collectstatic --noinput
```

Aucun `--ignore input.css` n'est requis.

`scripts/validate_static_manifest.py` vérifie explicitement les entrées critiques du manifest et l'existence de leurs cibles hashées, notamment les trois CSS historiques, le CSS/JS principal et les assets scanner/Smart Access.

## 10. Contrôles CI

La CI utilise une version Node explicite et :

```bash
npm ci
npm run build
git diff --exit-code -- package-lock.json static/dist
npm run check:runtime-deps
python manage.py collectstatic --noinput
python scripts/validate_static_manifest.py
python manage.py test
```

Le contrôle runtime refuse la réintroduction dans les templates de :

- `cdn.tailwindcss.com`
- `unpkg.com`
- `cdn.jsdelivr.net`
- `fonts.googleapis.com`
- `fonts.gstatic.com`
- JavaScript inline exécutable

Il ne bloque pas les liens HTTPS utilisateurs ou métier.

Des smoke tests rendent les pages publiques et authentifiées avec `CompressedManifestStaticFilesStorage` afin qu'une entrée de manifest manquante échoue en CI plutôt qu'après déploiement.

## 11. Workflow développeur

Pour un changement Python/template sans impact frontend : workflow Django habituel.

Pour un changement frontend ou une nouvelle classe/icône :

```bash
npm ci
npm run build
python scripts/check_frontend_runtime_deps.py
python manage.py collectstatic --noinput
python scripts/validate_static_manifest.py
python manage.py test
```

Commiter les sources et les artefacts `static/dist` synchronisés.

## 12. Déploiement PythonAnywhere

Aucun Node/npm n'est requis pour une release mergée :

```bash
cd ~/makolo
source ~/.virtualenvs/makolo/bin/activate
git checkout main
git pull origin main
python manage.py check
python manage.py collectstatic --noinput
```

Puis **PythonAnywhere > Web > Reload**.

Il n'y a ni commande npm, ni `--ignore input.css`, ni seed, ni service worker, ni nouveau worker applicatif à démarrer. Le fichier worker QR est un asset navigateur statique, pas un processus serveur.

## 13. Ajouter une dépendance JS

1. Vérifier qu'elle est réellement nécessaire et compatible CSP.
2. Choisir une version exacte.
3. Modifier `package.json` sans plage de version.
4. Régénérer le lockfile avec npm.
5. Intégrer la dépendance dans `frontend/src` plutôt que par CDN.
6. Exécuter `npm ci && npm run build`.
7. Vérifier le poids produit et l'absence de code chargé globalement sans nécessité.
8. Mettre à jour ce document si l'architecture, la CSP ou le déploiement change.
9. Commiter `package-lock.json` et `static/dist` si leur contenu change.
