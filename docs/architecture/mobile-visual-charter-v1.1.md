# Makolo Mobile — Charte visuelle V1.1

**Statut : FERMÉ — référence visuelle pour l’application mobile Makolo**  
**Version : 1.1**  
**Date : 27 septembre 2026**  
**Portée : Flutter mobile, expérience personnelle, Android et iOS**

> Cette charte définit le langage visuel de l’application mobile Makolo. Elle complète le contrat comportemental et l’architecture local-first. Elle ne crée aucune vérité métier, aucun état métier parallèle et aucune autorité côté client.

---

## 0. Base de fermeture

Base vérifiée avant consolidation :

- dépôt : `TraditionLearningCommunity/makolo` ;
- `main` vérifié : `ad7f3d23f449487676eeaeda37d432cc24d1171f` ;
- A1 mobile : PR `#306`, ouverte, branche `mobile/a1-installed-makolo-core`, head `fcf77a3a329a89d190c302adf907be1bc89b333f` ;
- fermeture identité native Android : PR `#319`, **fusionnée dans A1** ;
- A2-P0 docs : PR `#321`, ouverte, branche `docs/mobile-a2-p0-specs` ;
- A1 possède déjà le shell, le Mark, des tokens initiaux, les primitives de comportement, les états sync/offline, le stockage local-first et les fondations Flutter.

Cette charte ne redéfinit donc pas A1. Elle ferme la direction visuelle qu’A2 et les trains mobiles suivants doivent consommer.

---

# 1. Intention visuelle

## 1.1. Signature

La direction visuelle de Makolo est :

> **élégance en mouvement**

Makolo doit paraître :

- calme ;
- compétent ;
- chaleureux ;
- contemporain ;
- professionnel ;
- mémorable sans être spectaculaire ;
- léger visuellement et techniquement ;
- orienté vers l’action réelle.

Le produit ne cherche pas à impressionner par la quantité d’effets. Il doit donner l’impression que les choses sont comprises, ordonnées et prêtes à avancer.

## 1.2. Test de reconnaissance

Un écran Makolo doit rester reconnaissable même lorsque :

- le violet primaire est absent ;
- aucune photographie n’est présente ;
- aucune animation n’est en cours ;
- le Mark n’est pas affiché en grand.

La reconnaissance vient de la combinaison :

1. hiérarchie typographique ;
2. surfaces chaleureuses ;
3. densité maîtrisée ;
4. formes cohérentes ;
5. rythme d’espacement ;
6. mouvement court et significatif ;
7. Makolo Mark utilisé aux endroits structurels ;
8. langage produit simple et humain.

---

# 2. Principes immuables

## 2.1. Moins, mais mieux

Un écran ne doit pas être rempli pour sembler utile.

Le vide peut signifier :

> **Tout est en ordre. ✓**

L’espace calme est un matériau visuel Makolo.

## 2.2. Continuité avant spectacle

Une transition, une animation, une image ou une couleur doit améliorer au moins une de ces choses :

- orientation ;
- compréhension ;
- continuité ;
- confirmation ;
- action.

Sinon elle doit être retirée.

## 2.3. L’interface représente, elle ne possède pas

Les couleurs, badges, timelines, cartes, animations et états visuels représentent les vérités des domaines propriétaires.

Ils ne créent jamais une seconde vérité pour Readiness, Access, Capacity, Permission, Mandate, Payment, Journey ou tout autre domaine.

## 2.4. Le produit parle humainement

Aucun jargon d’architecture, de projection, de moteur ou de modèle ne doit devenir un élément visuel utilisateur.

---

# 3. Palette

## 3.1. Couleurs primitives canoniques

| Rôle | Nom | Valeur |
|---|---|---:|
| Marque primaire | Makolo Indigo | `#5232DB` |
| Marque profonde | Makolo Deep | `#2B176E` |
| Accent | Makolo Pulse | `#FF704D` |
| Surface chaude | Makolo Warm | `#FAF7F5` |
| Encre | Makolo Ink | `#0F172A` |
| Succès | Success | `#07806F` |
| Attention | Warning | `#B45309` |
| Danger | Danger | `#C83C3C` |
| Information | Info | `#2563EB` |

## 3.2. Règles d’usage

### Indigo

Pour :

- navigation active ;
- CTA principal ;
- focus ;
- orientation ;
- éléments de marque ;
- sélection structurante.

Ne pas transformer tout l’écran en violet.

### Deep

Pour :

- surfaces de marque fortes ;
- moments immersifs ponctuels ;
- dark surfaces sélectionnées ;
- grands contrastes de marque.

### Pulse

Le corail est un **accent rare**.

Pour :

- ponctuation éditoriale ;
- détail expressif ;
- signal visuel non sémantique ;
- petites signatures Discover.

Interdit comme :

- couleur de succès ;
- couleur d’erreur ;
- deuxième couleur primaire ;
- fond généralisé des CTA.

### Couleurs sémantiques

Success, Warning, Danger et Info sont réservés aux états correspondants.

Une couleur sémantique doit toujours être accompagnée par un texte, une icône ou les deux.

---

# 4. Matériaux visuels

## 4.1. Light mode

- `canvas` : `#FAF7F5` ;
- `surface` : blanc neutre ;
- `surface-raised` : blanc neutre + élévation discrète ;
- `text-primary` : `#0F172A` ;
- `brand-surface` : `#5232DB` ou `#2B176E` selon contexte ;
- bordures : neutres, très faibles, jamais dominantes.

## 4.2. Dark mode

Le dark mode personnel n’est pas le thème Platform.

Base :

- fond principal : Makolo Ink `#0F172A` ;
- surfaces : légèrement plus claires que le fond ;
- texte principal : `#FAF7F5` ;
- Indigo reste la marque ;
- Pulse reste rare ;
- les couleurs sémantiques conservent leur signification.

Le dark mode ne doit pas devenir noir pur partout.

### 4.2.1. Hiérarchie des surfaces sombres

Le dark mode doit conserver une profondeur lisible sans multiplier arbitrairement les couleurs. La relation attendue est :

1. `canvas-dark` — base Ink ;
2. `surface-dark-low` — très légère élévation perceptive ;
3. `surface-dark` — surface de contenu ;
4. `surface-dark-raised` — sheet, menu ou élément réellement superposé.

Les valeurs exactes peuvent être construites à partir d’Ink et de superpositions neutres contrôlées, puis validées par contraste. Une feature ne choisit pas localement ses propres noirs/gris.

## 4.3. Surfaces

Il existe quatre familles :

1. **Canvas** — fond de page ;
2. **Surface** — contenu ordinaire ;
3. **Raised Surface** — sheet, menu, élément réellement superposé ;
4. **Brand Surface** — moment de marque ponctuel.

Les ombres ne servent pas à séparer toutes les cartes.

## 4.4. Edge-to-edge et zones système

Makolo est conçu **edge-to-edge** lorsque la plateforme le permet.

Règles :

- le canvas peut se prolonger sous les zones système ;
- le contenu, les contrôles et les actions respectent les insets et Safe Areas nécessaires ;
- ne pas ajouter un cadre/padding global artificiel autour de toute l’application ;
- éviter tout flash de couleur incohérent entre surface native, Flutter et zones système ;
- les barres système doivent rester lisibles et cohérentes avec la surface affichée.

L’objectif est une surface continue, pas une application visuellement enfermée dans un rectangle.

---

# 5. Typographie

## 5.1. Familles

- **Manrope** : titres, marque, chiffres importants ;
- **Inter** : texte courant, navigation, boutons, formulaires, métadonnées.

Aucune typographie serif n’appartient à la charte mobile Makolo V1.

Les fonts doivent être disponibles localement dans l’application ; l’UI ne dépend pas d’un téléchargement de police au runtime.

## 5.2. Échelle

| Token | Police | Taille | Graisse | Usage |
|---|---|---:|---:|---|
| Display | Manrope | 32 | 800 | moment exceptionnel |
| H1 | Manrope | 28 | 800 | titre principal |
| H2 | Manrope | 24 | 700 | section majeure |
| H3 | Manrope | 20 | 700 | sous-section |
| Title | Manrope | 17 | 700 | carte importante |
| Body L | Inter | 16 | 400/500 | texte principal |
| Body M | Inter | 14 | 400/500 | UI dense |
| Label | Inter | 13 | 600 | boutons, chips |
| Caption | Inter | 12 | 500 | métadonnée |
| Nav | Inter | 11 | 600 | navigation primaire |

L’interlignage doit rester généreux, particulièrement sur les écrans personnels.

## 5.3. Règle de densité

Une carte ne doit pas empiler cinq niveaux typographiques différents.

Préférer :

**titre → information utile → état/action**.

---

# 6. Espacement

Makolo utilise une grille de base de **4 dp**.

Tokens :

- `4` — micro ;
- `8` — petit ;
- `12` — compact ;
- `16` — standard ;
- `20` — respiration interne ;
- `24` — section ;
- `32` — séparation majeure ;
- `40` — respiration forte ;
- `48` — structure ;
- `64` — espace exceptionnel.

Marge horizontale écran recommandée : **20 dp**, réduite à 16 dp seulement lorsque la largeur réellement disponible l’exige.

---

# 7. Formes

## 7.1. Rayons

- contrôle : `12 dp` ;
- carte : `16 dp` ;
- grande carte / hero / section : `24 dp` ;
- bottom sheet : `28 dp` en haut ;
- chip / status pill : rayon complet.

Tout ne doit pas être une pilule.

## 7.2. Élévation

Trois niveaux suffisent :

- `0` : contenu posé sur le canvas ;
- `1` : carte interactive ou barre ;
- `2` : sheet/menu/modal.

Les ombres doivent rester courtes et douces.

---

# 8. Iconographie

## 8.1. Base

La base reste l’iconographie Material cohérente, de préférence dans sa variante outlined pour les états neutres.

Un SVG spécifique est introduit uniquement lorsqu’un concept Makolo important n’est pas représentable proprement par l’iconographie standard.

## 8.2. Makolo Mark

Le Mark officiel est un asset, pas une icône générique.

Règles :

- ne jamais le redessiner ;
- ne jamais le remplacer par un `M` ;
- ne jamais modifier sa géométrie ;
- animation possible du conteneur, de l’opacité ou de l’échelle globale ;
- pas de morphing du tracé canonique.

Le concept visuel généré pendant la recherche est donc **non normatif** pour la géométrie exacte du Mark.

## 8.3. Touch targets

Toute action tactile principale : **48 × 48 dp minimum**.

---

# 9. Image, photographie et média

## 9.1. Principe

No Orphan Media s’applique intégralement au mobile.

Une image doit aider à :

- reconnaître ;
- choisir ;
- comprendre ;
- se situer ;
- se projeter dans une possibilité réelle.

## 9.2. Par surface

### Maintenant

Photographie non nécessaire par défaut.

L’écran doit pouvoir être beau avec uniquement :

- typographie ;
- espaces ;
- petits symboles ;
- états ;
- actions.

### Découvrir

C’est la surface la plus visuelle.

Les médias y sont légitimes lorsqu’ils appartiennent à l’Activity, Occurrence, lieu ou réalité présentée.

### En cours

Vignettes possibles pour reconnaissance rapide, mais secondaires par rapport à l’état et à la prochaine action.

### Moi

Avatar, documents, collectifs et ressources peuvent avoir une représentation visuelle utile. Pas de décoration gratuite.

### Makolo

Surface essentiellement typographique et interactionnelle. Peu ou pas de photographie.

---

# 10. Navigation primaire

La navigation personnelle mobile est fermée comme :

> **Maintenant · Découvrir · Makolo · En cours · Moi**

## 10.1. Barre

- hauteur de contenu : environ `72 dp` avant SafeArea ;
- labels toujours visibles ;
- quatre destinations ordinaires ;
- Makolo Mark central structurel ;
- icônes simples ;
- aucun badge de réengagement artificiel.

## 10.2. Makolo central

Le Mark central n’est pas un cinquième onglet identique aux autres.

Il ouvre l’entrée naturelle :

> **Qu’est-ce que vous avez en tête ?**

Il reste central dans toutes les profondeurs où la navigation primaire est pertinente.

## 10.3. Navigation adaptative

Les cinq destinations restent sémantiquement stables, mais leur conteneur peut s’adapter à l’espace disponible.

- téléphone : navigation basse ;
- grand écran / foldable / tablette : rail ou composition équivalente si cela améliore réellement l’usage ;
- ne jamais étirer artificiellement une barre mobile sur une largeur excessive ;
- le changement de conteneur de navigation ne change ni les destinations ni leur sens.

La décision dépend de l’espace réellement disponible, pas seulement du type d’appareil.

## 10.4. Retour, prédiction et continuité

Le retour système doit préserver la logique visuelle et le contexte.

Pour les parcours du type :

`Liste → Détail → Retour`

ou :

`Carte → Fiche → Retour`

Makolo doit restaurer raisonnablement :

- position de scroll ;
- filtres ;
- tri ;
- sélection ;
- position/zoom de carte lorsque pertinent.

Lorsque la plateforme fournit un retour prédictif, l’interface doit l’intégrer sans casser le router ni inventer une navigation parallèle.

---

# 11. Grammaire des composants

## 11.1. Boutons

### Primary

- Filled Indigo ;
- une seule action dominante par zone lorsque possible ;
- libellé précis.

### Secondary

- tonal / outline ;
- ne concurrence pas le CTA primaire.

### Tertiary

- texte ou icon button ;
- pour actions locales peu risquées.

### Destructive

- Danger ;
- jamais violet ;
- confirmation seulement lorsque le coût d’erreur le justifie.

## 11.2. Cards

Une carte existe lorsqu’un objet doit être perçu comme une unité.

Ne pas transformer toutes les lignes en cards.

Types :

- `ActionCard` ;
- `DiscoveryCard` ;
- `JourneyCard` ;
- `ResourceCard` ;
- `IdentityCard` ;
- `StatusCard`.

Le nom du composant ne crée pas un modèle métier.

## 11.3. List rows

À privilégier pour :

- paramètres ;
- ressources simples ;
- métadonnées ;
- actions secondaires ;
- historique ;
- sous-navigation.

## 11.4. Chips

Réservées à :

- filtre ;
- sélection courte ;
- statut compact ;
- contexte.

Pas de nuages de chips décoratifs.

## 11.5. Bottom sheets

Préférées lorsque l’utilisateur doit :

- choisir ;
- compléter un contexte ;
- agir sans quitter la continuité actuelle.

Éviter les sheets imbriquées.

---

# 12. Les cinq archétypes d’écran

## 12.1. Maintenant — calme opérationnel

Question :

> **Qu’est-ce qui compte maintenant ?**

Règles :

- une action dominante maximum ;
- pas de catalogue ;
- pas de feed ;
- pas d’image hero obligatoire ;
- priorité à l’état et à la prochaine action ;
- si rien n’est requis : espace calme et conclusion claire.

## 12.2. Découvrir — richesse contrôlée

Question :

> **Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

Règles :

- recherche ;
- filtres ;
- liste/carte lorsque pertinent ;
- médias contextualisés ;
- cartes plus expressives ;
- Pulse autorisé avec modération ;
- pas de scroll artificiellement addictif.

## 12.3. Makolo — intention naturelle

Question :

> **Qu’est-ce que vous avez en tête ?**

Règles :

- beaucoup d’espace ;
- Mark visible mais non envahissant ;
- une entrée principale ;
- suggestions contextuelles seulement si utiles ;
- pas de taxonomie interne sous forme de boutons ;
- clarification progressive.

## 12.4. En cours — continuité

Question :

> **Où en sont les choses ?**

Règles :

- distinguer ce qui suit son cours, ce qui attend l’utilisateur et ce qui est bloqué ;
- prochaine action très lisible ;
- statut contextuel ;
- timeline uniquement lorsqu’elle aide réellement ;
- média secondaire.

## 12.5. Moi — stabilité personnelle

Territoires :

- Passeport Makolo ;
- ce qui compte pour moi ;
- mes collectifs ;
- mes ressources ;
- préférences et paramètres en profondeur.

Règles :

- calme ;
- très peu d’accent ;
- structure claire ;
- pas de copie exhaustive des modèles rattachés au Profile.

---

# 13. États système et synchronisation

## 13.1. Normalité silencieuse

`Synced` n’est pas un badge permanent.

Lorsque tout fonctionne : **rien à montrer**.

## 13.2. Hors connexion

Si le contenu local existe :

- conserver le contenu ;
- signaler discrètement l’état réseau uniquement si utile ;
- ne pas transformer l’écran en erreur.

## 13.3. Pending

Une action locale non encore confirmée doit distinguer :

- enregistré sur cet appareil ;
- en attente de synchronisation ;
- en attente de confirmation ;
- confirmé ;
- conflit ;
- échec.

## 13.4. Loading

- < ~150 ms : aucun loader ;
- ~150–800 ms : feedback local ;
- > ~800 ms : skeleton/progression adaptée ;
- refresh : garder le contenu utile visible.

---

# 14. Motion

## 14.1. Principe

La motion Makolo explique le **mouvement**, la **continuité** et la **prise en charge**.

Elle ne divertit pas.

## 14.2. Durées

- instantané : `120 ms` ;
- micro-transition : `160 ms` ;
- transition standard : `240 ms` ;
- transition structurante : `320 ms` maximum dans la majorité des cas.

Au-delà, une justification fonctionnelle est nécessaire.

## 14.3. Mouvements privilégiés

- translation faible ;
- fade ;
- légère élévation ;
- scale très faible ;
- shared-axis ou continuité spatiale quand l’origine et la destination doivent être comprises.

## 14.4. Signature Mark

Activation possible :

1. press feedback ;
2. légère compression du conteneur ;
3. reprise douce ;
4. transition vers la surface Makolo.

Le tracé du Mark reste intact.

## 14.5. Reduce Motion

Lorsque Reduce Motion est actif :

- les translations décoratives disparaissent ;
- les durées deviennent nulles ou minimales ;
- aucune information ne doit être perdue.

## 14.6. Identité en mouvement

Makolo signifie « les pieds » en Lingala. Cette origine peut nourrir une **signature cinétique discrète** autour de l’appui, du pas, de la progression et de l’avancée.

Cette signature :

- peut apparaître dans le Brand Moment ;
- peut inspirer certaines transitions de progression ou de prise en charge ;
- ne transforme pas les pieds ou empreintes en décoration récurrente ;
- ne remplace jamais l’iconographie fonctionnelle ;
- ne modifie jamais le tracé canonique du Makolo Mark ;
- reste courte, abstraite et compatible Reduce Motion.

La reconnaissance dynamique de Makolo vient de la continuité et de l’avancée, pas d’un spectacle permanent.

---

# 15. Haptics

Les haptics sont sémantiques.

- sélection structurante : `selectionClick` ;
- succès réel : impact léger ;
- avertissement important : impact moyen ;
- pas d’haptique à chaque navigation ;
- pas de pattern gamifié ;
- pas de vibration pour compenser un mauvais feedback visuel.

---

# 16. Lancement, Brand Moment, onboarding et authentification

Les trois couches suivantes sont strictement distinctes :

1. **Splash natif** ;
2. **Brand Moment Makolo** ;
3. **Onboarding**.

Elles ne partagent ni la même fréquence ni la même responsabilité.

## 16.1. Splash natif

Le splash natif est technique et identitaire.

Règles :

- fond violet Makolo ;
- Makolo Mark canonique centré ;
- aucune attente artificielle ;
- aucun slogan obligatoire ;
- aucun contenu réseau ;
- aucun tutoriel ;
- pas d’animation longue ;
- disparition dès que Flutter est prêt ;
- cohérence stricte entre surface native et premier frame Flutter afin d’éviter un flash blanc/noir.

## 16.2. Brand Moment Makolo

Le Brand Moment est un court moment identitaire distinct du splash natif. Il peut apparaître pour une personne déjà utilisatrice de Makolo selon une politique locale centralisée.

Direction retenue :

`quelques pas stylisés → convergence/progression → Makolo apparaît → destination`

Règles :

- durée totale cible : environ `0,8–1,5 s` ;
- pas de jambes/pieds réalistes ;
- pas de personnage cartoon ;
- préférer Flutter natif à une librairie lourde ;
- le Makolo Mark officiel n’est jamais redessiné ;
- aucune attente artificielle ;
- variante Reduce Motion très courte ou statique ;
- ne pas rejouer au simple retour d’arrière-plan ;
- ne pas perturber deep link, notification utile, brouillon ou restauration sûre.

La cadence exacte est un **paramètre de politique**, pas une décision dispersée dans l’UI. Les valeurs actuellement envisagées sont :

- premier lancement du jour ;
- ou une fois tous les trois jours.

Le code doit permettre de choisir l’une ou l’autre sans réécrire l’écran.

Pour un utilisateur existant, éviter une copie comme « Votre parcours commence ».

## 16.3. Onboarding

L’onboarding concerne la première utilisation de l’installation/appareil. Ce n’est ni un splash ni un tutoriel.

Objectif :

- expliquer Makolo sur une surface courte ;
- présenter quelques exemples humains comme services, transports et événements ;
- demander uniquement les permissions utiles à cet instant ;
- proposer `Se connecter`, `Créer un compte` et `Continuer sans compte` ;
- permettre `Passer` lorsque pertinent ;
- conduire rapidement vers une surface utilisable.

La formulation candidate « Découvrir. Préparer. Avancer. » peut être utilisée si elle reste cohérente avec le langage produit canonique, mais elle n’impose aucun nouveau modèle métier.

Ne pas demander au démarrage, sans besoin réel :

- caméra ;
- localisation ;
- photos ;
- microphone ;
- Bluetooth ;
- permission générique de stockage.

Ces permissions sont demandées contextuellement lors du premier usage qui les nécessite, avec explication préalable.

## 16.4. Authentification et invité

Makolo reste utilisable sans compte lorsque la surface demandée est compatible invité.

- ne pas forcer Login après onboarding ;
- `Passer` n’est pas un faux bouton ;
- `Continuer sans compte` mène réellement à une expérience guest utile ;
- les capacités personnelles nécessitant une identité serveur restent protégées ;
- aucun faux Profile n’est créé pour un invité.

## 16.5. Persistance locale

Les états d’onboarding et de Brand Moment sont distincts.

Conceptuellement :

- onboarding terminé ;
- dernier Brand Moment affiché.

Ils ne doivent pas être encodés dans un même flag et ne deviennent pas des vérités métier serveur.

---

# 17. Accessibilité

La conformité visuelle exige :

- contrastes WCAG appropriés ;
- 48 dp minimum pour actions tactiles principales ;
- texte redimensionnable sans rupture majeure ;
- focus visible ;
- état jamais communiqué uniquement par couleur ;
- labels accessibles sur icon buttons ;
- ordre de lecture cohérent ;
- Mark décoratif exclu des semantics quand il n’apporte pas d’information ;
- motion réductible ;
- dark mode non dégradé.

La charte doit rester utilisable au minimum avec un fort agrandissement de texte sans chevauchement critique ni action inaccessible.

---

# 18. Poids technique et assets

## 18.1. Principe

L’identité Makolo ne doit pas imposer une application lourde.

## 18.2. Règles

- SVG pour Mark et illustrations vectorielles simples ;
- images raster compressées et dimensionnées au besoin réel ;
- thumbnails distantes plutôt que médias lourds bundlés ;
- aucune librairie d’animation lourde par défaut ;
- pas de Rive/Lottie tant qu’un besoin non réalisable proprement avec Flutter natif n’est pas démontré ;
- aucun pack d’icônes redondant ;
- polices limitées aux familles/graisses réellement utilisées ;
- toute dépendance purement visuelle importante doit justifier son coût dans l’APK/IPA.

---

# 19. Dark mode

Le dark mode doit conserver exactement la même architecture et la même sémantique.

Il ne doit pas :

- créer un produit différent ;
- rendre tout violet ;
- confondre la surface personnelle avec l’identité noire/violette réservée au contexte Platform web lorsque celui-ci est utilisé ;
- réduire le contraste des états métier.

---

# 20. Ce que le rendu conceptuel conserve et ce qu’il corrige

Le rendu visuel généré pendant la phase de recherche est utile comme direction, mais n’est pas un contrat pixel-perfect.

## Conservé

- canvas chaud ;
- hiérarchie très claire ;
- cinq repères visibles ;
- Mark central ;
- Discover plus visuel ;
- En cours plus structuré ;
- Moi plus calme ;
- usage généreux de l’espace.

## Corrigé

- aucun faux Mark ou Mark redessiné ;
- aucune police serif ;
- Maintenant n’a pas besoin d’une grande photographie décorative ;
- moins de violet réparti sur toutes les surfaces ;
- moins de bulles décoratives génériques ;
- statuts et wording doivent toujours venir des contrats produit réels ;
- pas d’apparence exclusivement iOS : la charte est Flutter et multi-plateforme.

---

# 21. Anti-patterns fermés

Interdits sans justification explicite :

- gradients sur toutes les cartes ;
- glassmorphism généralisé ;
- néomorphisme ;
- gros drop shadows partout ;
- couleurs pastel sans rôle ;
- emojis comme iconographie structurelle ;
- confetti ;
- streaks ;
- likes ;
- compteurs de popularité décoratifs ;
- loaders plein écran répétés ;
- feed infini artificiel ;
- cards imbriquées ;
- dix couleurs de statut ;
- motion continue ;
- Mark redessiné ;
- jargon backend visible ;
- badges de sync lorsque tout va bien ;
- image décorative orpheline.

---

# 22. Traduction Flutter

A2 doit consolider le design system autour de :

- `ThemeData` explicite light/dark ;
- `ColorScheme` contrôlé plutôt que dérivé principalement de `fromSeed` ;
- `ThemeExtension` pour les tokens Makolo non standards ;
- `MakoloColors` ;
- `MakoloSpacing` avec l’échelle complète de la charte ;
- `MakoloRadii` avec usages explicites ;
- `MakoloMotion` avec `120/160/240/320 ms` et adaptation Reduce Motion ;
- typographie Manrope/Inter **réellement embarquée** et déclarée dans `pubspec.yaml`, avec uniquement les graisses nécessaires ;
- thèmes partagés pour boutons, champs, cards, navigation, sheets et feedback ;
- variantes light/dark testées ;
- composants partagés ;
- aucune logique métier dans le design system.

Le design system doit être consommé par les features ; une feature ne redéfinit pas localement les couleurs/rayons/motion de Makolo.

---

# 23. Golden screens de référence

La charte est considérée correctement appliquée lorsque cinq écrans de référence existent :

1. Maintenant ;
2. Découvrir ;
3. Makolo ;
4. En cours ;
5. Moi.

Pour chacun :

- light ;
- dark ;
- petit écran ;
- grand téléphone ;
- text scaling élevé ;
- contenu ;
- empty ;
- offline/pending lorsqu’applicable.

Le jeu de régression doit aussi couvrir les états transversaux critiques :

- loading initial ;
- erreur récupérable ;
- action requise ;
- `Tout est en ordre` ;
- permission refusée ;
- saisie avec clavier ouvert ;
- onboarding ;
- état final du Brand Moment ;
- état Reduce Motion lorsqu’il change le rendu.

Ces références testent un **système visuel**, pas seulement cinq belles captures.

Ils deviennent la base de visual regression des surfaces personnelles mobiles.

---

# 24. Critères de sortie de la charte V1

La charte V1 est **fermée** lorsque l’implémentation respecte :

- palette et rôles ;
- typographie ;
- espacement ;
- formes ;
- navigation ;
- iconographie ;