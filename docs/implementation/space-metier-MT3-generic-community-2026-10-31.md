# MT3 — Fermeture des profondeurs Métier G1 : Activités et Initiatives

**Date :** 31 octobre 2026. **Dépôt :** TraditionLearningCommunity/makolo. **PR de travail :** #522, branche `fix/discover-a-continuation-context-20261014`.
**Checkpoint :** code serveur + Web et tests ciblés poussés. **Pas de migration, pas de nouveau modèle, pas de nouvelle autorité.** Pas de prétention de tests exécutés : accès GitHub aux sources, pas de checkout Django/Flutter exécutable dans cette session. L'intégration native Flutter spécialisée reste dans le périmètre **MT7** explicitement prévu ; son N1 et sa profondeur owner générique existants ne sont pas régressés par ce lot.

## 1. Pourquoi ce travail

G1 avait déjà composé les N1 `generic` (Activités) et `community` (Initiatives) dans `space_work_composition.py` et `space_work_presentation.py`. Les liens Web allaient souvent directement vers la Console et manquaient une profondeur humaine : Activity/Initiative durable, Occurrences réelles associées, dates, contexte, retour, ressources et opérations strictement sous droit.

**MT3 ne duplique pas les modèles** : Activity reste l'identité d'une initiative ; Occurrence, Journey et Funding restent propriétaires de leurs vérités. Group ou Team ne devient jamais une initiative ni une permission.

## 2. N1 → N2 → N3 livré

| Origine N1 | N2 Web ajouté | N3 réel sous condition et autorité |
| --- | --- | --- |
| Activité durable | `/spaces/<slug>/work/activity/<uuid>/` *préfixe effectif déterminé par organizations.urls* | Console Activity et gestion des Resources seulement avec `ACTIVITY_MANAGE` réelle |
| Initiative durable | même N2 Activity avec grammaire Initiative | mêmes outils ; Funding Manage supplémentaire uniquement si `FundingDetails(activity)` existe **et** `can_manage_funding` |
| Occurrence / action terrain | `.../work/occurrence/<uuid>/` | Jour J uniquement si `open_day_of` réel, revalidé par Operations |
| Demande ou démarche visible | `.../work/journey/<uuid>/` | profondeur Service opérateur si `open_service_case` et lien owner réels ; les décisions JourneyRequest restent dans leur propriétaire, aucun POST ici |

Les URLs N2 utilisent le routeur canonique `organizations:space-work-depth`, pas une chaîne préfixée construite manuellement. `kind` n'admet que `activity`, `occurrence`, `journey`, et ce N2 est fermé aux 6 autres archétypes (MT4–MT6 choisiront leurs propres compositions).

### Parcours de lecture

- **Activity / Initiative N2 :** identité, description courte, état réel, liste paginée (12/page) des Occurrences réelles, dates et statuts propriétaires, lien vers chaque profondeur Occurrence. Une Activity sans Occurrence reste légitime et affiche un état calme (pas une erreur).
- **Occurrence N2 :** identité, statut, date/heure/timezone et lieu si connu, lien vers l'Activity parent **si parent toujours autorisé**, et action Jour J seulement dans sa fenêtre opérationnelle.
- **Journey N2 :** démarche, statut humain du propriétaire, contexte Activity autorisé, lien vers parent si disponible, pas de bénéficiaire, pièce, secret ou fausse action. Cas Service mixte : lien vers profondeur opérateur existante lorsque ses propres permissions et son contexte le rendent possible.
- **Funding N3 :** jamais suggéré à partir du seul archétype Community ; utilise une relation O2O réelle et les permissions de Funding. Aucun total ni pourcentage reconstitué par l'UX.

### Back et navigation

Le lien depuis la racine N1 conserve `responsibility` et la section `from`. Depuis la liste d'Occurrences d'une Activity, le retour revient au N2 parent et à sa page d'origine (pas systématiquement N1). La lecture du N2 repasse à chaque GET par `build_space_work_projection(source_kind, source_id, responsibility_key)` et refuse tout objet absent de `selection`; les liens vers N3 revalident à nouveau chez le propriétaire. L'ID de la réalité n'est jamais dérivé du texte ou de l'ordre d'un item.

N2 ne peut pas révéler des données d'un Space étranger ou d'une Activity hors mandat. Une révocation fait échouer la relecture. Limites et onglets N1 ne deviennent pas des droits.

## 3. Chantiers effectivement modifiés

- `organizations/space_work_g1_web.py` **ajout** : composition N2 G1, liens N3 owner-backed, permission et parent, état calme, pagination et retour.
- `templates/organizations/space/work_depth.html` **ajout** : une surface Makolo partageant shell et tokens, mais vocabulaire et compositions contextuelles, pas de `titre + status + bouton` universel.
- `organizations/urls.py` : nouveau chemin `space-work-depth`.
- `organizations/space_work_web.py` : N1 Generic/Community ouvre maintenant N2 contextuel ; autres six archétypes inchangés.
- `organizations/test_space_work_mt3.py` **ajout** : 11 scénarios ciblés, sans suppression ni affaiblissement d'un test existant.

## 4. Résultats attendus et exclusions

Les tests statiquement ajoutés vérifient : N1→N2→Occurrence ; langue Generic vs Community ; initiative durable sans date ; Funding owner réel et autorisé ; Jour J phase réelle ; 15 Occurrences paginées ; impossibilité de suivre un lien après changement d'acteur ; mandat Activity-limited, accès étranger et révocation ; GroupMembership sans autorité ; interdiction G1 aux six autres archétypes ; Journey sans fuite de bénéficiaire ; Service mixte qui n'annonce pas une profondeur inexistante.

Aucun WorkItem, Initiative persistée, équipe fictive, nouvelle API de création, paiement, queue, « Live », degré de readiness, feed ou média orphelin n'a été créé.

**Choix délibéré :** le formulaire canonique `activities:create` possède un choix explicite de l'organisateur, mais pas un pré-remplissage contextualisé garanti par cet N1. MT3 n'ajoute pas de bouton « Nouvelle initiative » qui risquerait de créer par défaut au nom du Profil au lieu de l'Espace. Une future liaison de création devra verrouiller le bon acteur et les vrais mandats. Les demandes JourneyRequest et les actes Services sont réutilisés, pas réimplémentés dans ce N2.

## 5. Gates et transfert sans perte

**MT3 livré en code Web/serveur**, revue du source effectuée, tests ciblés **ajoutés mais non exécutés** faute d'environnement Django dans cette session. Il ne serait pas exact de déclarer la QA visuelle ou l'E2E validée.

Pour test local ciblé si disponible, sans bloquer le travail sur les CI :

```bash
python manage.py test organizations.test_space_work_mt3 organizations.test_ws3_space_work_web organizations.test_zs3_space_work_api
```

**MT4–MT6 :** construire les profondeurs propres à leurs familles **sans reprendre** le code G1 ou transformer le G1 en template métier universel.

**MT7 :** intégrer une profondeur native Flutter de qualité équivalente, consommer les handoffs et relations owner-backed sans WebView improvisée, préserver sélection/scroll/back, travailler local-first/stale/revocation et fluidité/adaptive. Aucun double backend mobile.

**MT8 :** examiner scénarios visiteur, acteur Space, mandat limité, permissions perdues, Activity publiée sans Occurrence, initiative avec plusieurs Occurrences, Funding présent/absent, Service mixte, qualité responsive et accessibilité.

**Formule :** une application Makolo, N2 humains et contextuels, N3 multiples seulement lorsqu'un vrai propriétaire les rend accessibles ; ne pas forcer les huit grammaires à la même géométrie d'écran.
