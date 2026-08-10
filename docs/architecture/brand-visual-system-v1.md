# Makolo — Brand & Visual System V1

Cette charte formalise l'identité appliquée au produit Makolo. Elle complète le système UX 2026 existant sans modifier la logique métier.

## Territoire

Makolo se positionne sur trois idées : **mouvement, rencontre, confiance**.

Le nom permet d'évoquer le déplacement et le parcours sans utiliser de représentation littérale de pieds. L'identité doit rester crédible pour les zones transactionnelles (paiements, billets, contrôle d'accès, back-office) tout en conservant l'énergie d'un produit événementiel participant-first.

Principes de marque :

- vivant, mais pas festif à outrance ;
- fiable, mais pas froid ou institutionnel ;
- contemporain et accessible ;
- africain par son ancrage, son rythme et son contexte, sans folklore décoratif ;
- suffisamment large pour Discovery, billetterie, CRM, Analytics, Partners, Autopilot et Smart Access.

## Logo temporaire

Le logo final fera l'objet d'un travail séparé. Jusqu'à sa validation, l'interface utilise un **M** simple comme marque temporaire. Aucun pictogramme de ticket, QR, calendrier ou empreinte n'est utilisé comme logo principal.

## Palette

| Rôle | Token | Hex |
| --- | --- | --- |
| Makolo Indigo | `--mk-brand` | `#5232DB` |
| Makolo Deep | `--mk-brand-strong` | `#2B176E` |
| Makolo Pulse | `--mk-pulse` | `#FF704D` |
| Makolo Ink | `--mk-text` | `#0F172A` |
| Makolo Warm | `--mk-surface-warm` | `#FFF8F3` |
| Cloud | `--mk-bg` | `#F6F7FB` |
| Success | `--mk-positive` | `#07806F` |
| Warning | `--mk-warning` | `#B45309` |
| Danger | `--mk-danger` | `#C83C3C` |
| Info | `--mk-info` | `#2563EB` |

### Usage

- Indigo : identité, navigation active, CTA principal, focus et orientation.
- Pulse : énergie éditoriale, tendance, favoris et micro-accents. Jamais pour signaler un succès ou une erreur.
- Success : billet valide, paiement réussi, scan accepté.
- Warning : attente, stock faible, action à surveiller.
- Danger : refus, erreur, annulation ou état destructif.
- Info : information système neutre.

Le corail n'est pas une deuxième couleur primaire. Il doit rester rare afin de conserver son rôle de « pulse » événementiel.

## Typographie

- **Manrope 700–800** : marque, titres de page, titres de cartes importantes, chiffres de synthèse.
- **Inter 400–700** : navigation, boutons, formulaires, tableaux, texte courant et UI dense.

Le produit conserve des fallbacks système pour rester utilisable si les webfonts ne sont pas disponibles.

## Formes et densité

- panneaux : rayon principal ~20 px ;
- contrôles : ~12 px ;
- actions tactiles principales : au moins 44 px ;
- badges : pilules compactes ;
- ombres courtes et discrètes ;
- gradients réservés aux héros, surfaces de marque et absence d'image, jamais à toutes les cartes.

Le back-office reste plus dense et neutre que les surfaces participant. Discovery peut utiliser davantage de chaleur (`Makolo Warm`) et de Pulse.

## Motion

La motion exprime le territoire de mouvement : petite translation, progression, entrée et glissement. Elle ne doit jamais être indispensable à la compréhension. `prefers-reduced-motion` reste prioritaire.

## Accessibilité

- focus visible avec Makolo Indigo ;
- couleurs sémantiques distinctes de la couleur de marque ;
- états importants accompagnés de texte ou d'icônes, jamais communiqués par couleur seule ;
- contraste prioritaire dans billets, paiement, scanner et formulaires ;
- mode sombre conservant la hiérarchie sémantique.

## Implémentation

Le socle historique reste dans `static/css/makolo-ui.css` et `static/css/makolo-compat.css`.

La charte V1 est appliquée par `static/css/makolo-brand.css`, chargé après ces deux fichiers afin de surcharger les tokens et composants sans réécrire les templates métier. Les écrans participant les plus visibles peuvent utiliser des classes dédiées telles que `mk-participant-hero`, `mk-pulse-*`, `mk-event-*` et `mk-ticket-*`.
