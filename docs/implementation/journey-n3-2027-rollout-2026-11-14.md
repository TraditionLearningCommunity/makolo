# Démarche N3 2027 — implémentation de la composition universelle/contextuelle

**Date :** 14 novembre 2026  
**PR :** #522 · **branche :** `fix/discover-a-continuation-context-20261014`  
**Point de départ inspecté :** `4639cc5ab6977a57e256d987db99a8b00b717b38`  
**Référence UX :** `docs/ux/journey-n3-specification-implementation-2027-pr522.md`  
**Statut :** modifications poussées dans #522, non fusionnées, tests non exécutés sur SDK/Android dans cette intervention.

## Lecture du chantier réel avant modification

- Une seule route N3 existait déjà ; les situations `action/waiting/blocked/choices/completed/calm`, les owner Forms/Requirements/Payment/Access, les JourneySteps, les ressources Preparation et les transitions Journey étaient présents dans #522. Pas de duplication de ces domaines.
- `personal.journey.detail` est acquis par Sync Kernel et lu dans Drift/ProfileStore ; les permissions et la Readiness restent chez les propriétaires.
- L'owner Jour J `operations.occurrence_experience` admet les bénéficiaires via `participant_occurrence_live_available` ; le simple `occurrence_id` ne suffit pas.
- Le fragment Web Preparation affichait des sections vides et le Web N3 avait deux listes de formulaires.

## Modifications effectivement réalisées

### D1 — Serveur / API / autorisation

- `core/api/detail_views.py` vérifie l'éligibilité au Jour J via le résolveur bénéficiaire du propriétaire Operations avant de passer un drapeau `day_of_available` à la projection N3.
- `core/api/detail_projections.py` annonce `open_day_of` et son lien seulement si cette admission est établie ; l'Occurrence reste consultable selon ses propres règles. Les autres capacités sont inchangées.
- `core/participant_views.py` donne au Web le lien Jour J seulement aujourd'hui, après la même vérification d'éligibilité. Une Journey Service `fulfilled` est libellée « Suivi terminé dans Makolo », sans confondre le résultat de l'organisme.

### D2 — Composition déterministe Flutter

- `journey_composition.dart` identifie les mouvements distincts par leur **lien propriétaire**, non par la clé de check Readiness ; plusieurs contrôles menant au même owner ne créent pas un faux choix.
- Les contrôles techniques dont le texte ne sert pas à la préparation visible restent des vérités Readiness serveur, mais ne gonflent pas le compteur UI « points vérifiés ».
- La situation dominante affiche le CTA propriétaire principal sans répéter son propre libellé comme paragraphe explicatif.
- Les autres actions distinctes restent accessibles ; URL inconnue = information, jamais fausse action.

### D3 — UI Flutter

- Couverture pleine largeur en surfaces Makolo claires/sombres, cible universelle, titre, état, conversation conditionnelle et repères de l'Occurrence regroupés sans second panneau date/adresse.
- Jour ±N regroupé avec calendrier, horaire et localisation, cliquable **uniquement** à J et si la projection donne un handoff propriétaire.
- Preview Preparation en défilement horizontal, 2+ tuiles lisibles sur petits écrans, jusqu'à quatre aperçus ; chaque tuile ouvre la **profondeur Preparation** disponible (pas de lien fichier prétendument direct).
- Préparation : compteurs cohérents avec les éléments réellement affichés. Les groupes techniques seuls ne produisent plus une carte vide.
- Mon parcours : étapes Journey owner, passées courtes visibles, futures repliables et branches réelles ; placé après préparation/ressources/engagements. Pas de timeline inventée.
- Historique : informations et dates compactes dans une ligne ; états et dates proviennent des transitions owner.
- Service terminal : statut « Suivi terminé dans Makolo » une seule fois, distinct de la réponse externe affichée séparément.
- Handoffs : un `next_action` de formulaire (detail/save/submit) ouvre le formulaire propriétaire ; Payment/Commerce ouvrent seulement une obligation/commande déjà liée à cette Journey, par identifiant exact, jamais par URL brute.
- Les Occurrences sans libellé distinct n'ajoutent plus une carte « Occurrence » générique qui répète la couverture.

### D4 — Lecture locale / asynchronisme

- `JourneyRepository` conserve sa projection `personal.journey.detail` et expose un résumé déjà connu depuis `personal.ongoing` **de ce Profile**, sans lui transférer des capacités.
- En absence de détail N3 acquis, le N3 peut montrer un objectif/date/lieu autorisés provenant de cette lecture locale. Aucun formulaire, paiement ou lien Jour J n'est fabriqué depuis ce résumé.
- Le flux Ongoing local est conservé entre reconstructions et rebindé au changement de repository/Profile/Journey. Les échecs réseau de refresh continuent à ne pas effacer la projection acquise.
- Les décisions serveur, règles de révocation, brouillons, fichiers et outbox restent dans les propriétaires et le Sync Kernel existants ; aucune nouvelle outbox « Journey générique » ajoutée.

### D5 — Web

- `participant_journey_detail.html` garde une couverture compacte : conversation dans l'en-tête du bloc, Jour J dans la ligne calendrier, pas de second gros panneau Live ; parcours après les profondeurs de préparation.
- Suppression de la deuxième liste Web de FormRequests ; « Mes documents » ne devient pas un bouton universel hors contexte.
- `preparation/participant_workspace.html` ne rend plus de sections Form/Resource vides. Form Requests = lignes compactes ; Resources owner = tuiles réactives ; instructions textuelles longues repliées dans `details`, sans masquage des ressources restantes.
- Les routes serveur Web continuent à recontrôler les droits, aucune autorité ou mutation ajoutée aux templates.

### D6 — Tests ajoutés/actualisés, non prétendus exécutés

- `core/test_z5_detail_api.py` : vérifie `open_day_of` pour un bénéficiaire éligible puis son retrait lorsque la Journey devient annulée ; pas de double panneau Form et pas de « aucun document » fictif sur Web.
- `mobile/test/journey_universal_composition_test.dart` : contrôles techniques non affichables, plusieurs checks vers un seul owner.
- `mobile/test/journey_n3_lot_c_test.dart` : libellé « Mon parcours » aligné.
- `mobile/test/journey_n3_2027_experience_test.dart` : preview 320 dp et navigation Preparation, actions Form/Payment réelles, contrôle technique, résumé Ongoing connu, isolation d'identité d'une Journey.

## Frontières non falsifiées

- `Capacity`, `Placement`, `Waitlist`, planning Jour J, QR AccessCredential, preuve, attestation et référence de dossier ne sont **pas** synthétisés depuis Journey lorsqu'aucun owner autorisé n'en expose le lien / le fait. Ajouter des tuiles visuelles à vide violerait les contrats.
- Le résumé Ongoing local est **partiel** : il ne transforme pas une action absente ni une donnée encore non acquise en fait confirmé.
- L'API Jour J et les deep links des autres N2/Operations gardent leurs propriétaires ; cette passe n'a pas refondu Découvrir, Conversations, Notifications ni Jour J.
- Le rendu physique Android/Samsung, l'accessibilité complète, Django tests et Flutter analyze/goldens doivent encore être exécutés sur un clone synchronisé. Aucun résultat vert n'est inventé.

## Suite de recette locale PowerShell (à exécuter, pas exécutée ici)

```powershell
cd C:\Users\Public\makolo
git status --short --branch
git fetch origin
git switch fix/discover-a-continuation-context-20261014
git pull --ff-only
python manage.py check
python manage.py test core.test_z5_detail_api services.test_t35_participant_workspace
cd mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter analyze
flutter test test/journey_n3_2027_experience_test.dart test/journey_universal_composition_test.dart test/journey_n3_lot_c_test.dart test/journey_n3_composition_test.dart
```

**Recette physique encore nécessaire :** émulateur/Samsung, 320–430 dp et texte agrandi, Profil A/B, Jour −2/J/J+N, refus/revocation 403, mode avion avec détail acquis et avec seulement Ongoing acquis, deux actions simultanées, paiement pending, Service terminé avec résultat externe négatif, Web responsive et lecture locale Preparation.

**Merge :** ne pas fusionner dans main avant les contrôles pertinents et l'accord du propriétaire.
