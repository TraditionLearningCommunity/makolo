# Makolo — Découvrir : chantier 04, Presentation N1

**Date :** 31 octobre 2026  
**Branche :** `fix/discover-a-continuation-context-20261014` ([PR #522](https://github.com/TraditionLearningCommunity/makolo/pull/522)).  
**Périmètre :** composition **N1 Web et Flutter**, sans nouveau fait métier ni mutation et sans engager le chantier 05 (navigation, recherche, carte).  
**Décision :** **implémentation N1 livrée en code** ; tests ajoutés, exécution des tests et CI différée au chantier 09 sur instruction de l'utilisateur. **Aucun test exécuté n'est affirmé vert.**

## 1. Contrats et réutilisation

Le contrat [`discovery-n1-layout-contract.md`](../architecture/discovery-n1-layout-contract.md) demeure normatif pour huit zones ordonnées. Les projections de la PR #522 restent la source des faits : `discovery/api/composition.py`, `discovery/api/projections.py`, `discovery/api/media_bindings.py`. Aucune migration, endpoint, table, `Possibility`, `Media`, `Resource` ou propriété de fait n'a été créée pour arranger le rendu.

Le chantier réutilise :
- `DiscoveryPossibilityUnit` pour N1 Flutter (également employé à N2 avec `detailMode`) et `DiscoveryExplorationView` pour sa mise en page adaptative ;
- `_web_discovery_card`, `_universal_card.html` et `_resource_item.html` pour N1 Web ;
- `DiscoveryReader` et `DiscoveryShareControl` et les routes propriétaires pour lecture et interaction ;
- les associations `media_bindings`, champs `presentation_facts`, `spatial_facts`, `temporal_facts`, `resources`, `assessment` et `variants` déjà admis.

## 2. Huit zones : état de sortie du chantier

| Zone | Comportement utilisé / livré | Changement dans ce chantier |
| --- | --- | --- |
| **1. Porteur + ajout** | Ligne propriétaire/avatar/lien public lorsque autorisé, date d'ajout à droite distincte des dates métier | Flutter `discoveryAddedAtLabel` : « À l’instant », « il y a 2 min », « il y a 2 h », « Hier », « Avant-hier », jours/semaines puis date. Web `_added_date_label` + `card.added_label` ; `<time datetime>` et tooltip de date exacte conservés. Pas de calcul de date d'événement. |
| **2. Titre** | Titre du modèle, ouverture N2 uniquement si l'utilisateur agit | Structure existante conservée, aucune navigation nouvelle |
| **3. Type / verticale** | Verticale, eyebrow, sous-type, dédoublonnés | Les libellés restent sous le titre ; pas de « Type » dupliqué dans les faits pratiques ; sans invention de classification |
| **4. Description** | Texte N1 sur trois lignes, dépliable par toucher et « Voir plus/Voir moins » ; seul le texte change | Comportement existant conservé ; tests couvrent stabilité des faits, retour et absence de navigation involontaire |
| **5. Informations pratiques** | Prix, dates, place, disponibilité, contexte owner-backed | Flutter : titre de section lorsque faits ou notes établis ; conservation de l'indisponibilité **connue** (plus confondue avec inconnue), rôles spatiaux `Départ/Escale/Arrivée/Embarquement` et localité ; seules les notes `assessment.state=limiting` sont visibles ; variantes annoncées à partir de deux. Web : mêmes rôles et labels temporels `Début/Fin/Ouverture/Clôture/Date limite`, aucun `unknown` placé comme fait, notes limitantes seulement et variantes multiples. |
| **6. Média / galerie** | Images explicitement publiées, galerie et Reader, sans média synthétique | Flutter conserve désormais l'`alt_text` et le MIME `image/jpeg` ou `image/png` de l'association propriétaire pour ouvrir le Reader, même lorsque l'image principale partage la même URL. La représentation sans média ne produit toujours pas de faux visuel. |
| **7. Documents / ressources** | Deux premières ressources à N1 ; commande « Voir les N ressources » pour tout montrer/replier, liens TEXT/FILE/URL envoyés aux lecteurs propriétaires | Code de présentation existant réutilisé sans introduire de nouvelle limite serveur ; `read_url` sert à lire le TEXT intégral depuis Preparation, sans substituer un extrait tronqué. |
| **8. Interactions** | Trois colonnes égales mobiles (Save / action métier ou détail / Share), Web en grille trois colonnes ; capacités du serveur respectées | Aucun CTA ni droit ajouté. Sans action métier native, le centre ouvre N2 ; l'absence de capacité Save ne produit pas de mutation. |

## 3. Corrections précises

### Flutter — `mobile/lib/presentation/possibilities/discovery_possibility_unit.dart`

- Fonction pure `discoveryAddedAtLabel(addedAt, now, french)` : différence temporelle locale **du champ `date.kind=added_at` seulement**, date entière dans Tooltip/Semantics. Aucune conversion du `timing` owner.
- `_reliableFacts` continue de filtrer les inconnues, mais n'élimine plus la valeur `indisponible` lorsqu'elle est confirmée par le wire.
- Rôles spatiaux traduits avec fidélité aux attributs owner et à la localité ; pas de coordonnées déduites.
- `_contextNotes` : notes `limiting` seules, nombre réel de variantes (> 1) et de relations ; aucun verdict local.
- Section « Informations pratiques » présente seulement quand un fait ou contexte reconnu existe.
- Galerie : rapprochement par URL, déduplication sans perdre `mime_type` ni `alt_text` explicites du `PresentationMediaUse` ; Reader reçoit son type MIME réel pour JPEG/PNG.

### Web — `discovery/views.py`, `templates/discovery/_universal_card.html`

- `_added_date_label` construit une étiquette lisible à partir du seul `date.kind=added_at`, séparément de `temporal_facts` et de la valeur exacte HTML `datetime`.
- `_web_discovery_card` localise les repères métier de temps et les rôles spatiaux, respecte l'identité des faits et dédoublonne les valeurs déjà présentées.
- Évite les placeholders `unknown/inconnu/n/a/à confirmer` comme faits pratiques.
- Les seules notes contextualisées à N1 sont celles marquées `limiting` par le serveur ; aucun raisonnement local de qualité ou de priorité.
- `variant_count` s'affiche pour plusieurs variantes effectives, sans dupliquer une seule Occurrence.

## 4. Régressions et exemples enregistrés

**Flutter :** `mobile/test/discovery_mature_screen_test.dart`
- dates d'ajout relatées en français et en anglais, futur non présenté comme passé ;
- disponibilité `Indisponible` connue, Départ/Escale/Arrivée ;
- informations pratiques uniquement lorsque connues ou limitées par le propriétaire ; variante réelle et limitation documentée, inconnue non promue ;
- tests préexistants conservés : ordre, 3 actions, date à droite, classification, description expandable, sept documents dont deux initiaux, large/compact, changement d'échelle de texte, partage.

**Web :** `discovery/test_m8b_mature_discover.py`
- étiquettes temporelles relatives et absence d'inférence de date ;
- déduplication de type, noms de lieu et rôles, disponibilité connue, date limite distincte de la date d'ajout ;
- tests préexistants conservés : séquence, trois positions d'action, partage, CTAs web explicites.

Les tests ne sont **pas exécutés**. Ce sont des contrats de non-régression écrits et stockés sur la branche.

## 5. Frontières de fermeture

**Ce chantier ne corrige pas :**
- la transmission du contexte recherche/filtre au nouvel écran carte, la restauration du scroll/sélection, ni la continuation entre les écrans : **chantier 05** ;
- la comparaison conditionnelle approfondie et les variantes en N2 : **chantier 06** ;
- les mutations Save/Watch/Sharing et la garantie d'autorisation N3 : **chantier 07** ;
- les snapshots, la conservation et révocation de fichiers offline : **chantier 08** ;
- la CI, les tests réellement exécutés, Web E2E, la vérification Android et le merge : **chantier 09**.

Les chantiers 01–03 sont réutilisés sans relancer ni contourner leurs propriétaires. Aucune modification d'API ni de politique de stockage dans ce lot.

## 6. Critères de livraison de code

- [x] Ordre des huit zones N1 conservé sur Web et Flutter, sans hauteur fictive pour les données absentes.
- [x] Date d'ajout à droite et humanisée, source distincte des horaires propriétaires.
- [x] Type/verticale dédupliqués.
- [x] Description expandable sans mutation des faits et autres zones.
- [x] Faits pratiques métiers lisibles, indisponibilité connue affichée, inconnues non devinées.
- [x] Galerie avec type MIME/alt owner, sans média artificiel.
- [x] Deux ressources puis toutes, Reader propriétaire réutilisé.
- [x] Trois interactions sans permission ajoutée, Web et Flutter.
- [x] Tests de régression écrits et traçabilité de livraison.
- [ ] Tests/CI/Android/Web réellement exécutés : **différés, non revendiqués**.

**Décision : chantier 04 — implémentation livrée, certification différée. Prochain chantier autorisé : 05 exclusivement.**
