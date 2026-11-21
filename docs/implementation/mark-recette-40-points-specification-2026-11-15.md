# Makolo Mark — Spécification d’implémentation de la recette UX/UI (40 points)

**Date de cadrage :** 15 novembre 2026  
**Statut :** spécification pour exécution et vérification, **pas** certification du runtime  
**Dépôt canonique :** `TraditionLearningCommunity/makolo`  
**Branche de travail :** `fix/discover-a-continuation-context-20261014` — **PR #522** ; ne pas merger, ne pas désactiver les workflows CI  
**Références :** `AGENTS.md`, `README.md`, `mobile/README.md`, `docs/ux/`, `Makolo_UX_Makolo_Mark_Contrat_Consolide_2026-10-08.md` et `Makolo_UX_Decouvrir_Contrat_Consolide.md` ; les contrats et la réalité des propriétaires priment sur cette proposition.  
**Source de recette :** captures Samsung/émulateur et décisions de la revue Mark (texte, clavier, médias, caméra, dictée, audio, brouillon, envoi) transmises dans la conversation.  
**But :** terminer l’expérience **« J’ai quelque chose à donner à Makolo »**, sans transformer Mark en réseau social, messagerie infinie, tuto technique ou propriétaire métier parallèle.

## 0. Correction explicite de la maquette : icône « Enregistrer »

**OBLIGATOIRE — ne pas utiliser l’icône signet / bookmark générique.** L’icône à réutiliser est **`DiscoveryOrbitIcon`**, définie dans :

- `mobile/lib/presentation/possibilities/discovery_save_icon.dart` ;
- exportée via `mobile/lib/presentation/possibilities/discovery_possibility_unit.dart` ;
- déjà utilisée dans `mobile/lib/features/discovery/discovery_mature_view.dart`, notamment sur l’action « Enregistrer ».

Elle possède deux états réels : `saved: false` (« Enregistrer ») et `saved: true` (« Enregistré »), avec couleur et taille paramétrables. **Réutiliser le composant exact et ses assets existants**, sans le redessiner et sans le remplacer par `Icons.bookmark`, `Icons.save_outlined` ou une nouvelle icône inventée.

**Important — réutilisation visuelle, pas transfert de propriété :** l’action de Découvrir enregistre une possibilité via son propriétaire. Dans Mark, la même grammaire visuelle déclenche **la sauvegarde du brouillon Mark dans son store/owner existant**, jamais un `OpportunitySave` ou un engagement Découvrir. La réussite visuelle « Enregistré » ne s’affiche que si le brouillon est effectivement conservé. Le cas sans capacité de sauvegarde reste indisponible/explicable, jamais marqué réussi. Web doit employer l’asset/trait original équivalent, avec les mêmes états et sémantique ; vérifier son chemin exact avant modification.

**Libellés accessibles :** « Enregistrer le brouillon », puis « Brouillon enregistré ». Visuellement, l’icône peut rester seule dans l’interface compacte. Le bouton de l’autre action est **« Envoyer »** (icône/action dédiée, distincte, mais pas obligatoirement une flèche à droite).

## 1. Résultat produit attendu

Une seule expérience **Makolo Mark**, en contexte `Profile` ou `Space`, responsive sur Flutter mobile, tablette et Web/ordinateur. La personne peut **écrire, dicter, enregistrer, photographier, sélectionner plusieurs images et documents, coller un lien, revoir/retirer, enregistrer un brouillon et envoyer une demande** selon les capacités réelles. L’intelligence et l’orchestration restent progressives, owner-backed et déterministes quand un modèle n’est pas configuré.

Le design doit être **original Makolo** : Makolo Mark officiel (sans le redessiner), palette `#5232DB`, `#2B176E`, `#FF704D`, `#FAF7F5`, `#0F172A`, typographie calme, actions lisibles. Ne pas copier la barre « + / micro / flèche » de ChatGPT, ni les couleurs/formes/animations spécifiques de Gemini. Réutiliser les gestes natifs connus mais composer une **surface d’intention et d’action**, non une conversation à scroll infini.

### Contrat minimum de la surface

- Écran au repos : symbole officiel, invitation humaine courte, saisie compacte ; pas de tutoriel ni compteurs inutiles.
- En saisie : focus conservé ; composeur accessible **près du clavier** ; la grande introduction s’efface sans reconstruire le champ ni faire apparaître un vide anormal.
- En préparation enrichie : miniatures image/photo, vignettes PDF/doc, puce audio, liens détectés ; hauteur plafonnée, défilement local approprié, action toujours accessible.
- Ajout : **un seul geste d’ajout** ouvrant « Appareil photo », « Photos », « Fichiers » ; le micro reste un geste distinct.
- Sauvegarde : **`DiscoveryOrbitIcon`** pour « Enregistrer le brouillon » ; aucun snackbar ou panneau technique lorsque la sauvegarde normale est silencieuse.
- Soumission : « Envoyer » signifie transmettre la **demande réellement acceptée par le propriétaire** ; distinguer sa réception de l’exécution/confirmation métier.
- Vocabulaire : « Ajouter », « Photo », « Photos », « Fichiers », « Audio », « Transcrire », « Pause », « Reprendre », « Terminer », « Enregistrer », « Envoyer », « Réessayer » selon contexte. Éviter « revalidation distante », « cache », « outbox », « moteur IA », « brouillon local », « transcription système ».

## 2. Registre des 40 anomalies — exigences et critères de réception

La numérotation ci-dessous est stable pour la PR, les tests et les captures. **P0** = action trompeuse/perdue/bloquée ; **P1** = parcours ou ergonomie majeure ; **P2** = finition.

### A — identité, saisie, clavier (01–12)

| ID | P | Défaut de recette | Exigence / preuve attendue |
|---|---|---|---|
| M01 | P1 | Composeur trop semblable à un chat | Composition Makolo spécifique, surfaces d’intention et marque officielle ; revue visuelle comparative mobile/Web, sans copier de marque tierce |
| M02 | P1 | Grand « Continuer » ancien | « Envoyer » compact et naturel, intégré à la surface, sans grand pied de formulaire |
| M03 | P1 | Flèche à droite trop conventionnelle | Identité propre, différenciation claire « Enregistrer » / « Envoyer » ; validation de compréhension sans tutoriel |
| M04 | P1 | Cinq boutons permanents | Menu contextuel unique Appareil photo / Photos / Fichiers, micro distinct ; pas de bouton Lien |
| M05 | P1 | Trop d’explications affichées | Retirer paragraphes techniques et titres répétitifs ; conserver seulement les conséquences nécessaires |
| M06 | P1 | Champ trop haut vide | Hauteur 1–2 lignes au repos, croissance jusqu’à un plafond puis scroll intérieur ; longue demande lisible |
| M07 | P2 | Double rectangle autour du champ | Un seul composeur visuel, contraste et focus accessibles |
| M08 | P2 | Compteur `0/600` permanent | Indice de limite seulement utile, sans supprimer la validation serveur |
| M09 | P1 | Saisie éloignée du clavier | Composeur accessible près du clavier et des insets natifs ; test Samsung et émulateur |
| M10 | P1 | Grand espace vide pendant l’édition | États accueil, édition, préparation enrichie continus et visuellement équilibrés |
| M11 | P2 | Disparition brutale de l’intro | Transition calme, sans unmount/rebuild de l’éditeur ni perte de sélection |
| M12 | P2 | Outils encombrants | Touch targets accessibles, icônes cohérentes, actions secondaires contextuelles |

### B — images, fichiers, liens (13–22)

| ID | P | Défaut de recette | Exigence / preuve attendue |
|---|---|---|---|
| M13 | P1 | Une image par sélection | Sélection multiple de photos **et** fichiers quand le picker natif le permet ; plafond initial UX **10 pièces cumulées par demande** (photos + docs + audios), à valider contre les limites owners et taille ; aucune sélection perdue |
| M14 | P1 | Photos peu lisibles | Miniature réelle de chaque photo/image, identifiée par sa source locale, appui pour aperçu |
| M15 | P1 | Documents affichés en texte brut | Vignette format + nom tronqué, aperçu PDF si viewer propriétaire disponible, pas de faux aperçu |
| M16 | P1 | Croix géante masquant les photos | Retrait discret, contrasté, zone tactile 44–48 dp, sans couvrir le sujet |
| M17 | P2 | Tailles/ratios discordants | Grille cohérente, conservation des proportions pertinentes, accès à la vue entière |
| M18 | P1 | Composeur immense à 5+ pièces | Galerie interne bornée/défilante, zone texte et actions toujours accessibles |
| M19 | P1 | Capture caméra renversée | Diagnostiquer capteur/EXIF/orientation/affichage ; ne pas faire de rotation arbitraire ; tests portrait, paysage, caméra avant/arrière |
| M20 | P1 | Double validation caméra puis Mark | Si le sélecteur natif demande déjà « OK », ne pas imposer un deuxième « Garder » par défaut ; aperçu facultatif par toucher |
| M21 | P1 | Bouton Lien imposé | Détection `https?` depuis le texte collé/tapé ; puce non intrusive ; pas de fetch automatique, ni d’autorité déduite |
| M22 | **P0** | Médias montrés comme joints mais non transmis | Raccorder les pièces à des owners capables de les recevoir, ou distinguer explicitement pièce préparée de pièce réellement soumise ; aucun « Envoyé » fictif |

### C — voix et dictée (23–31)

| ID | P | Défaut de recette | Exigence / preuve attendue |
|---|---|---|---|
| M23 | P1 | Deux entrées dictée / audio compliquées | **Une seule entrée vocale**, session d’enregistrement locale, puis usage « Audio » ou « Transcrire » lorsque possible |
| M24 | **P0** | Silence = arrêt de dictée | Le silence ne termine **jamais la capture audio principale** ; pause naturelle ≠ Stop |
| M25 | P1 | Une validation par phrase | Session longue, plusieurs phrases, reprise sans valider chaque silence ; limites durée/stockage explicites uniquement si impact |
| M26 | P1 | Pause traitée comme fin | Pause/Reprendre/Terminer distincts, timers et fichier cohérents |
| M27 | P1 | Transcription dans second formulaire | Résultat éditable dans **le champ Mark existant**, insertion sans écrasement de la demande et avec annulation sûre |
| M28 | P1 | Barre vocale lourde | Bande audio compacte avec durée/état et icônes pause, reprise, fin, écouter, supprimer |
| M29 | P1 | « Garder » ambigu | En fin d’enregistrement : choix « Audio » / « Transcrire », puis action « Envoyer » de la demande ; pas de faux envoi direct |
| M30 | P1 | Capacités variables des appareils | Enregistrer d’abord ; transcription live si elle peut durer sans interrompre la capture ; sinon différée **si moteur audio-fichier disponible**, sinon audio seul, avec conséquence simple |
| M31 | P2 | Mode oral immersif assimilé à Mark | **Reporté** ; ne pas afficher une expérience de conversation vocale continue comme opérationnelle |

**Machine d’états vocale de référence :**

`idle → recording ↔ paused → stopped → (audio_selected | transcription_pending | transcript_ready | unavailable) → prepared → submission_pending → owner_outcome`.

- Le recorder local constitue la source stable ; le moteur STT ne décide pas du cycle de vie du recorder.
- Si la reconnaissance live se ferme après silence, elle peut être reprise lorsque autorisée, **sans arrêter l’enregistrement** et sans demander confirmation à chaque segment. Ne pas promettre un STT continu que le téléphone ne fournit pas.
- Toute transcription est candidate éditable ; ne jamais prétendre qu’une transcription d’un fichier audio existe si aucune capacité ne le permet.
- Ne pas conserver durablement le brut audio par défaut quand l’utilisateur choisit uniquement le texte, sauf besoin légitime explicite et politique de conservation.
- Micro : permission demandée au geste, arrêt à l’annulation, au changement d’Actor, à la disparition de l’écran et selon lifecycle ; jamais lancer le micro après disposal.
- Un fichier audio « prêt » n’est pas une demande envoyée. Pour envoyer le son, exiger un endpoint/owner acceptant réellement ce média et sa confirmation.

### D — brouillon, soumission, retours (32–40)

| ID | P | Défaut de recette | Exigence / preuve attendue |
|---|---|---|---|
| M32 | P1 | Carte « Brouillon local » | Remplacer par l’icône **Découvrir / `DiscoveryOrbitIcon`** et un état léger ; aucune carte permanente |
| M33 | P1 | « revalidation distante », détails techniques | Messages en langage humain : seulement conséquence + geste utile |
| M34 | **P0** | Dialogue « Continuer avec le texte seulement ? » | Supprimer le dialogue systématique. Si pièces non prises en charge, leur non-envoi doit être explicite **avant** l’action, de façon sobre ; pas de tromperie |
| M35 | P1 | « Garder », « Continuer » confus | Actions distinctes : **Enregistrer** brouillon et **Envoyer** la demande ; icônes sémantiques testées |
| M36 | P1 | Échecs réseau bavards | Un indice discret « Non envoyé » et « Réessayer » utile quand l’action en dépend ; pas d’alertes automatiques répétées |
| M37 | **P0** | « Envoyé » interprété comme « accompli » | `draft_saved ≠ queued ≠ received ≠ owner_decided ≠ fulfilled`; rendre les transitions vraies |
| M38 | P1 | Rebuild/retry réseau bruyant | Lecture du contenu local, refresh discret, absence de cascade de banners/snackbars |
| M39 | **P0** | Risque de mélange / perte des brouillons | Scope strict Profile/Space, isolation des fichiers privés, changement d’acteur et restauration sûre, pas d’écrasement d’une intention en attente |
| M40 | P1 | Trop de cartes et confirmations | Une clarification bloquante à la fois ; confirmation explicite uniquement lorsque conséquence métier réelle |

## 3. Contrats de fonctionnement — ne pas déplacer les vérités

- Mark est **un orchestrateur de préparation/intention**, pas un nouveau propriétaire de `Activity`, `Journey`, `Requirements`, `Resource`, `Proof`, `Access`, `Capacity`, `Payment`, `Permission`, `Mandate`.
- `Profile` = personne, `Space` = identité collective ; une membership/team n’accorde jamais une autorité implicite.
- `Django` possède les décisions et invariants ; API projette ; Flutter sauvegarde le brouillon et les médias privés localement, compose et réconcilie, sans inventer succès ou autorité.
- Un document détenu n’est pas une exigence satisfaite ; une photo affichée n’est pas une preuve reconnue ; un audio enregistré n’est pas un envoi.
- Le geste **Enregistrer** dans Mark conserve le brouillon dans le magasin Mark déjà présent. **Ne pas appeler le propriétaire Découvrir** pour sauvegarder ce brouillon sous prétexte que l’icône visuelle est réutilisée.
- « Envoyer » doit viser la requête owner réellement capable. Si l’API Mark reste text-only et que les médias doivent participer à l’intention, **ne pas masquer leur absence** ; prévoir le handoff propriétaire, une préparation avec capacité ou une affordance désactivée justifiée. Il est interdit de transformer silencieusement « texte + 5 photos » en « texte seulement » tout en affichant « Envoyé ».
- Pour lien détecté : `http(s)` syntaxiquement correct, pas de scraping ni accès privé implicite ; ne pas faire croire que la page a été comprise.
- Limites : `600` caractères actuellement côté Mark, validation serveur finale ; 10 pièces est **cible UX conditionnelle**, jamais promesse de taille/format universels avant validation des owners.
- Concurrence, idempotence, réconciliation, outbox autorisée, droits et données privées : préserver les mécanismes existants. Une outbox est une intention, pas une confirmation.
- Une réponse distante ambiguë ne doit pas déclencher un nouvel envoi concurrent sans clé idempotente ni décision propriétaire.

## 4. Spécification des interactions et textes définitifs

| Situation | Formulation visible / accessibilité | Condition de vérité |
|---|---|---|
| Brouillon non encore sauvegardé | Icône orbite de Découvrir, tooltip « Enregistrer le brouillon » | Action locale possible pour l’Actor |
| Brouillon réellement sauvegardé | Même orbite, état `saved:true`, « Brouillon enregistré » au focus | Écriture effective confirmée par store local |
| Échec de sauvegarde | Icône d’erreur locale, « Impossible d’enregistrer. Réessayer » | Erreur effective et action de retry utile |
| Enregistrement vocal | « En cours · 00:42 », Pause, Terminer | Recorder réel actif |
| Audio en pause | « En pause · 00:42 », Reprendre, Terminer | Recorder réellement suspendu |
| Audio terminé | Icônes « Audio » / « Transcrire » et Écouter / Supprimer | Fichier audio staged existant |
| Transcription indisponible | « Transcription indisponible. Vous pouvez envoyer l’audio. » | Pas de capacité STT fichier/live autorisée |
| Soumission en préparation | « Envoi… » uniquement si requête réellement en cours | Pas de succès anticipé |
| Demande non reçue | « Non envoyé », « Réessayer » | Échec réel ou absence de décision, sans effacer la demande |
| Demande reçue | « Reçu » ou suite propriétaire | Accusé propriétaire autoritatif |
| Action métier terminée | Résultat/contextualisation du vrai owner | Décision confirmée, jamais présumée |

**Interdictions visibles par défaut :** « Brouillon local », « Makolo n’a pas pu revalider le contexte à distance », « Les informations connues restent visibles », « API/cache/outbox », « Aucun moteur IA nécessaire », « Consultation uniquement pour le moment », bannières persistantes à chaque échec de refresh, longues pages d’aide sur le STT. Une explication de confidentialité n’apparaît qu’au moment où elle change réellement le choix ou la conséquence.

## 5. Parcours d’implémentation ciblés

1. **Audit avant écriture :** vérifier `main`, PR #522, changements récents, collisions, `AGENTS.md`, architecture et propriétaire existants ; ne pas refaire l’acquis.
2. **Design système :** intégrer `DiscoveryOrbitIcon` au composeur Mark mobile en respectant les états réellement sauvegardés ; retrouver la représentation web correspondante ; ne toucher ni son SVG ni au save métier Découvrir.
3. **Composeur Flutter :** identité visuelle originale, saisie + galerie médias bornée + icône Enregistrer + action Envoyer, focus natif, clavier, tailles, accessibilité ; conserver `MarkScreen` et les stores, limiter les nouvelles abstractions.
4. **Images/caméra :** multi-picker natif sans perte, max 10 pièces combinées sous politique claire, EXIF/orientation, aperçu unique, récupération/annulation, suppression/ownership des fichiers.
5. **Voix :** unifier le point d’entrée tout en réutilisant le recorder et les passerelles STT ; faire durer la capture malgré les silences ; pause/reprise/fin ; choisir audio ou transcription ; fallback exact ; aucune conservation/transmission implicite.
6. **Brouillon/envoi :** clarifier `save draft` vs `submit request`, rendre les status silencieux et vrais ; corriger `local_attachments_only` / `local_references_only` sans masquer l’impact ; owner route/hand-off si disponible.
7. **Web Profile/Space :** mêmes gestes et termes, formats, multi-fichier, média local preview, sauvegarde et limite owner, fenêtre desktop réductible ; éviter divergence de contrats Web/Flutter.
8. **Contrôle des sources de vérité :** aucun nouveau modèle, aucun endpoint générique ou transfert de pouvoirs non justifié ; préserver API canonique et migrations.
9. **Documentation et tests :** scénarios ci-dessous ; consigner capacités effectivement livrées vs dépendances bloquantes avant d’annoncer « fini ».

**Points de départ source (à relire au HEAD du moment) :**

- `mobile/lib/features/mark/mark_screen.dart`, `mark_repository.dart`, `mark_voice_capture.dart`, `mark_dictation_capture.dart`, `mark_navigation.dart` ;
- `mobile/lib/presentation/possibilities/discovery_save_icon.dart` et usages de `DiscoveryOrbitIcon` ;
- `mobile/lib/platform/` (caméra, multi-picker, STT, AudioRecorder, fichier privé), Drift/drafts/outbox ;
- `templates/core/makolo_mark.html`, `templates/organizations/space/mark_ws5.html`, `templates/partials/mark_input_tools.html`, `static/js/mark-intake.js`, `static/css/mark-intake.css` ;
- `core/mark_orchestration.py`, `core/mature_experience_views.py`, `organizations/api/space_mark_projection.py` et propriétaires `personal_assets` / autres domaines autorisés.

## 6. Tests de réception obligatoires

**Flutter / Samsung / émulateur**
- [ ] 01–12 : accueil, saisie longue/courte, clavier ouvert/fermé, retour arrière, rotation, orientation, aucun saut de focus, accessibilité, tablette.
- [ ] L’orbite `DiscoveryOrbitIcon` est **visuellement identique** à Découvrir ; l’état enregistré apparaît seulement après sauvegarde effective du brouillon, sans créer `OpportunitySave`.
- [ ] 13–18 : choisir 1, 5, 10 pièces en plusieurs opérations ; caméra, galerie multiple, fichiers multiples, combinaison de types ; tenter la 11e, retrait, réouverture, brouillon restauré, aucun mélange Profile/Space.
- [ ] 19–20 : photo portrait/paysage, caméra frontale/arrière, EXIF, « OK » natif, pas de deuxième validation imposée.
- [ ] 21–22 : URL collée, URL non http(s), pièces réellement soumises vs préparées ; pas de faux traitement audio/image.
- [ ] 23–31 : parole, silence 5 s / 30 s / 2 min, reprise, pause/reprise manuelle, longues interventions, app en arrière-plan, permissions refusées ; audio utilisable, transcription fichier seulement si moteur vérifié, annulation restaure texte.
- [ ] 32–40 : mode avion avec local présent/vide, indisponibilité serveur répétée, deux envois rapides, idempotence, soumission ambiguë, changements d’Actor, redémarrage, perte de réseau pendant upload et reprise.
- [ ] Navigation jour J, accès, reconnaissance, Space : aucune autorité inventée et aucune « réussite » avant décision propriétaire.

**Web**
- [ ] Smartphone, tablette, desktop : présence et accessibilité de l’orbite, soumission distincte, miniatures, choix de pièces, clavier, fenêtre flottante/réduite et restauration.
- [ ] Vérifier reconnaissance vocale du navigateur selon permission, interruption d’onglet, disponibilité de moteur ; pas de promesse de transcription différée sans moteur.
- [ ] Sélection et transmission par owner validé uniquement, CSRF, privacy, restrictions de taille/format, aucune fuite de document privé dans l’HTML ou l’état d’un autre Actor.

**Tests ciblés et outils**
- Django : tests propriétaires ciblés, `manage.py check`, migrations, permissions/IDOR, idempotence/concurrence, PostgreSQL si impact.
- Flutter : `dart run build_runner build --delete-conflicting-outputs`, **`bash tool/dart_format.sh write` puis `check`**, `flutter analyze`, tests ciblés, goldens et build Android selon impact.
- Si SDK Dart indisponible, utiliser **le workflow existant `Mobile Format` sur la feature branch** seulement avec accord ; ne pas inventer un formatter ni manipuler des workflows CI.
- Ne jamais affaiblir les tests existants. Une CI rouge ne devient pas une livraison certifiée.

## 7. Critères de sortie et compte rendu

**La PR #522 ne pourra être déclarée « corrigée » que lorsque :** (a) les 40 exigences sont tracées en tests/captures et leurs limites réelles explicites ; (b) l’orbite Découvrir est réutilisée sans duplication ni mutation Découvrir ; (c) le clavier/focus, multi-pièces/orientation et voix longue sont recettés ; (d) aucune image/audio/document n’est réputé analysé ou envoyé sans propriétaire ; (e) tous les états brouillon/envoi/décision sont exacts ; (f) code formaté, tests ciblés, analyse/build et recette pertinents exécutés avec preuves.

**À chaque intervention :** lister fichiers touchés, branche, commits, tests réellement effectués, anomalies résiduelles, obstacles et prochaine action. Conserver la PR ouverte ; ne pas merger, annuler ou désactiver des workflows existants ; ne pas modifier `main` sans accord.

## 8. Décision de priorisation

1. **P0 :** M22, M24, M34, M37, M39 — aucun trompe-l’œil d’envoi, aucune coupure de capture sur silence, aucun mélange ou perte de données.
2. **P1 :** tous les autres parcours touchant saisie, caméra, STT, médias, sauvegarde réelle et owner.
3. **P2 :** proportion des icônes, animations, vignettes et homogénéité, seulement après contrats vérifiés.

**Ce document est un mandat de correction et de vérification, pas l’assertion que les 40 points ont déjà été exécutés.**
