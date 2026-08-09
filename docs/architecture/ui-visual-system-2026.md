# Makolo UI / UX Visual System 2026

Cette évolution est volontairement **présentationnelle** : elle ne modifie ni les modèles métier, ni les permissions, ni les états de commande, ni les moteurs CRM/Payments/Scanner/Automation. Les templates continuent à utiliser les mêmes routes et les mêmes objets de contexte.

## Direction

Makolo adopte une interface professionnelle, sobre et contemporaine : hiérarchie typographique forte, densité contrôlée, surfaces neutres, indigo réservé aux actions et à l’orientation, couleurs sémantiques réservées aux états. Les dégradés restent ponctuels et structurels, jamais décoratifs sur chaque carte.

Le shell utilise une navigation compacte regroupée par intention : Principal, Exploitation, Audience & croissance, Pilotage et Plateforme staff. Sur mobile, la navigation devient un drawer accessible au clavier et fermable par Escape.

## Design tokens

Les tokens CSS sont centralisés dans `static/css/makolo-ui.css` :

- fond et surfaces light/dark ;
- texte principal, secondaire et subtil ;
- couleur de marque et surface de marque ;
- bordures ;
- ombres courtes et flottantes ;
- rayons ;
- dimensions du shell.

`static/css/makolo-compat.css` applique ces tokens aux templates métier historiques afin d’éviter une réécriture risquée de la logique de chaque écran. Les formulaires Django natifs, tableaux, cartes et boutons gagnent ainsi une base visuelle commune.

## Motion

Les animations sont limitées à :

- entrée douce d’une page ;
- micro-élévation des cartes interactives ;
- translation minimale des flèches ;
- transitions du drawer mobile et des menus ;
- apparition des messages système.

Aucune animation n’est essentielle à la compréhension ou à l’exécution d’une action. `prefers-reduced-motion: reduce` désactive pratiquement toutes les animations et transitions.

## Accessibilité

- focus clavier visible sur liens, boutons et champs ;
- boutons icon-only avec `aria-label` ;
- messages système avec rôle de statut ;
- drawer mobile déclaré comme dialogue ;
- contraste basé sur des tokens distincts light/dark ;
- contrôles tactiles d’au moins ~42–44 px sur les actions principales ;
- états non communiqués uniquement par animation.

## Responsive

Desktop : sidebar fixe 264 px et topbar compacte.

Tablet/mobile : sidebar remplacée par un drawer, contenus sans largeur artificielle, actions qui reviennent à la ligne, formulaires et cartes reflow en une colonne lorsque nécessaire.

## Écrans explicitement retravaillés

- shell global, navbar, sidebar mobile/desktop, footer et messages ;
- authentification ;
- vue d’ensemble ;
- Discovery, Pour vous, Favoris et Mes événements ;
- cartes événement ;
- profil public organisateur ;
- liste et détail événement ;
- portefeuille tickets ;
- paiements ;
- organisations ;
- CRM ;
- Growth ;
- Analytics ;
- Promotions ;
- Fidélité ;
- Partenaires ;
- Smart Access.

Les autres templates héritent du shell, des contrôles de formulaire et de la couche de compatibilité.

## Dette assumée pour A1 Go-Live

Le chantier visuel ne remplace pas le futur travail d’industrialisation frontend : Tailwind/HTMX/Alpine/Lucide restent actuellement chargés selon l’architecture existante. Lors de A1 Go-Live, ces dépendances pourront être compilées, versionnées et sécurisées par CSP sans changer le langage visuel défini ici.
