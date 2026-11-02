# Découvrir — chantier 09 : fermeture d'implémentation et contrats de sortie

**Date :** 2026-11-02 · **Dépôt unique :** `TraditionLearningCommunity/makolo` · **Branche de livraison UNIQUE :** `fix/discover-a-continuation-context-20261014` · **PR :** [#522](https://github.com/TraditionLearningCommunity/makolo/pull/522).

## 0. Décision de travail (instruction explicite)

**TOUTES les modifications et la traçabilité du chantier 09 se font directement dans #522.** Pas de branche de certification, pas de PR de checkpoint, pas de réconciliation d'une autre branche vers #522, pas de fusion dans `main`, pas de CI utilisée pour conditionner l'avancement du travail d'implémentation. Le chantier 09 doit fermer **les fonctionnalités réellement manquantes**, pas déplacer le chantier vers des exercices de certification.

La PR #532, créée au cours d'une tentative antérieure de CI, **n'est pas une source de vérité ni un véhicule de livraison**. Ses échecs ou réussites historiques ne remplacent pas un diagnostic des sources de #522. Les changements du Reader et les tests correspondants sont **déjà présents dans #522** ; ne pas les copier à nouveau.

**Statuts :** `LIVRÉ EN CODE` = code et tests écrits ; `VALIDÉ PAR EXÉCUTION` = tests effectivement exécutés et réussis ; `NON VÉRIFIÉ` = aucune preuve d'exécution. Ne pas appeler `NON VÉRIFIÉ` un échec produit, mais ne jamais l'appeler `VERT` non plus.

## 1. Contrat final de l'expérience

Promesse : « Makolo marche pour vous ». Le champ Découvrir répond à « Qu'est-ce que je pourrais avoir envie de vivre, faire ou obtenir ? » et ouvre une **suite d'actions réelles**. Les couches de présentation ne possèdent aucune vérité métier.

**Chaîne complète à livrer :**

`faits owners → admission/permissions → Discovery projection → filtres/carte N1 → détail N2 → action propriétaire N3 → retour/continuité locale`.

Découvrir n'implémente pas un feed générique ; ne promet aucune place, aucun paiement, aucun billet, aucune inscription et aucune permission à la place des propriétaires. Les domaines `Activity`, `Occurrence`, `Service`, `Funding`, `Opportunity`, `Commerce`, `Journey`, `Access`, `Capacity`, `Sharing`, `Profile`, `Space` restent propriétaires.

## 2. Matrice exhaustive de sortie fonctionnelle

| Bloc | Exigence vérifiable en code et UX | Sources existantes à réutiliser |
| --- | --- | --- |
| Admission | N'exposer que les options admises, publiques ou privées selon la vraie permission, sans fuite entre Profils ou Spaces | `discovery/api/composition.py`, owners |
| Identité | Une seule identité canonique `family/resource/candidate_key`, qui survit liste/carte/détail/retour ; pas de modèle `Possibility` bis | `discovery/api/projections.py`, `discovery_wire.dart` |
| Capacités | Une action visible doit correspondre à `owner/state/capability/resource/destination` vérifiés | propriétaires + selector |
| N1 | Titre, émetteur, sens, image publiée, fait temporel et spatial, prix/disponibilité connus ou explicitement inconnus ; date relative sans confondre date de publication et date d'événement | `_universal_card.html`, `discovery_possibility_unit.dart` |
| Recherche | Texte, type, lieu, temps, prix, géographie et rayon filtrent une seule projection, sans élargissement silencieux | `DiscoveryQuery`, API |
| Pagination | Curseurs opaques ; pas d'inférence de token ; page précédente seulement si token connu ; refus de continuation → premier lot du même contexte | repository, API |
| Carte | Même sélection et mêmes faits que la liste ; pin uniquement si coordonnée owner publiée ; carte compacte visible ; indisponibilité des tuiles ≠ absence de résultat | spatial view, MapLibre |
| Navigation | Recherche/Liste/Carte/N1/N2/retour conservent critères, candidat et scroll, y compris liens directs et parcours invité | GoRouter, ProfileStore |
| N2 | Faits, descriptions, ressources, assessments favorable/limiting/unknown, lieux et dates propres aux Occurrences, relations déclarées | `detail_projection`, N2 Web/Flutter |
| Comparaison | Uniquement options explicitement comparables et dimensions réellement connues pour toutes ; aucun classement universel ni gagnant fabriqué | N2 conditional rows |
| Save | Save/Unsave idempotent, authentification explicite, identité et état confirmés, jamais une réservation | `set_saved_state` propriétaire |
| Watch | Veille sur critères et non Save ; création idempotente, pause, reprise, édition, suppression, résultats N2, visibilité par Profil | `ensure_discovery_watch` |
| Sharing | Lien public owner-confirmé / livraison privée confirmée ; token, ACL, refus, expiration/révocation, reprise authentification | Sharing API |
| N3 | Commerce, Services, Funding, Events, Obtention et Journey : seulement handoff autorisé, confirmation finale par owner | `_primaryNativePath` et routes natives |
| Local-first | Snapshot acquis consultable offline, sans nouveau contenu inventé ni faux succès ; revalidation avant opération owner | `ProfileStore`, `SyncEngine` |
| Révocation | 403/404 retire les projections dérivées et marque la source ; panne réseau ne purge pas les données valides | `SyncSourceDefinition` |
| Confidentialité | Isolation entre Profils, viewer vérifié, private Reader séparé, ancienne copie partagée illisible/nettoyable, URLs signées non retenues | `DiscoveryOfflineStore`, Reader |
| HTTP | Réponses viewer-sensibles et Sharing non stockables par caches partagés, y compris erreurs | API `finalize_response` |
| Accès | Visiteur et Profil ont des parcours adaptés ; aucune autorité héritée d'un Group/Space | views, routes, permissions |
| État UI | Distinguer loading / no match / fin / hors ligne / refus / revalidation / échec temporaire ; action sensible désactivée si autorité non revalidée | selector, screens |
| Retour d'action | Après action propriétaire, réacquérir le fait owner confirmé et ne jamais extrapoler un état `success` à partir du simple clic | repository et callbacks |

## 3. Invariants non négociables

1. Le client **présente** les faits et transactions : il ne crée ni permission, ni mandat, ni droit, ni paiement, ni disponibilité.
2. `UNKNOWN` ≠ `FALSE` ou `UNAVAILABLE` ; `Waitlist` ≠ `Live Queue` ; `Capacity` ≠ `Placement`.
3. Posséder un document ≠ satisfaire un Requirement ; un média publié ne prouve pas qu'il est accessible hors ligne.
4. Une composition de possibilités ne transfère ni Access, ni Permission, ni Mandate, ni données privées.
5. Le cold-start peut **lire** un ancien fait autorisé mais ne peut pas **agir** sur la base d'une autorisation passée.
6. Les résultats d'une Watch ou d'un lien Share ouvrent une possibilité admise, jamais une action N3 automatique.
7. Une requête hors connexion ne devient jamais un résultat « aucun match » si le serveur n'a pas répondu.
8. Une seule identité de Profil globale ; Space contextuel et responsable, pas une seconde personne.

## 4. Contrôles de réalisation et non-régression à prévoir dans #522

### 4.1 Serveur Django

- Admissions publiques/privées sur chaque famille, permission et IDOR, mise à jour/retrait propriétaire, génération de `candidate_key`.
- Projection N1/N2, prix et disponibilité réellement source-backed, ressources et provenance.
- Recherche et pagination : filtres combinés, cursor signé, altération, replay, page précédente, 400 contrôlé.
- Save et Watch idempotents (répétitions/concurrence, différentes personnes, Dossier personnel), refus 401/403/404.
- Sharing lien public et livraison privée : émission, destinataire, expiration, révocation, retrait owner, no-store.
- Actions N3 : pas de chemin inventé, aucune transaction automatique, permissions vérifiées dans la route propriétaire.
- Vérifier migrations existantes, `makemigrations --check`, `migrate --plan`, tests ciblés et PostgreSQL si impacté.

### 4.2 Flutter et UI

- Contrôle de structure `dart format` et `flutter analyze`, sans modifier les tests ou snapshots pour obtenir artificiellement du vert.
- Tests ciblés de N1, N2, carte, sélection, filtres, pagination, Watch, Save, Sharing et routes N3.
- Cas offline/réinstallation/switch Profil/reprise de scroll/403+late-200/read-only N2 ; Reader public vs privé.
- Appareil Android : installation réelle, cold start, perte de réseau, retour online, publication retirée, lien partagé, retour du N3 et permissions.
- Web : home public, page détail, droits, anti-IDOR, URL retour sûre, responsive et accessibilité.

### 4.3 Critères de preuve

**La présence d'un test n'est pas un test réussi.** Pour chaque contrôle exécuté : SHA exact, commande/workflow, résultat, preuve vérifiable, cause et correctif si échec. Une erreur Now ou d'un autre train n'est pas automatiquement imputable à Découvrir ; elle ne doit cependant jamais être masquée si elle bloque la qualité globale.

## 5. Travaux 09 déjà présents dans #522

- Correction du nettoyage des anciennes copies Reader non cloisonnées : `purgeLegacyUnscopedReader` dans `mobile/lib/presentation/possibilities/discovery_offline_store.dart`, invocation depuis le chemin de lecture protégé.
- Test de régression de refus des copies legacy dans `mobile/test/discovery_stage08_media_privacy_test.dart`.
- Les autres capacités 01–08 restent consignées dans leurs relevés spécifiques, sans duplication des vérités métiers.

## 6. État du chantier

**Livrables :** matrice fonctionnelle du présent document, registre R01–R28, sources et tests enregistrés dans #522. Les diagnostics antérieurs de formatage Dart, de bundles Web et de goldens Now constituent des observations d'outillage, **pas** une nouvelle branche de développement ni une condition d'implémentation.

**Non attesté :** suite de tests finale 01–08 sur HEAD #522, build Android installé réellement, parcours Web et Flutter E2E, comparaison des goldens Now, validation de l'ensemble des migrations et résultat de tous les workflows sur un HEAD stable.

**Décision : CHANTIER 09 — PÉRIMÈTRE D'IMPLÉMENTATION FIXÉ DANS #522 ; CERTIFICATION EXÉCUTÉE NON ATTESTÉE.** Aucun merge ni déploiement. Ne pas relancer une procédure de checkpoint/réconciliation à la place des corrections produit. Les vérifications pourront être exécutées séparément lorsque l'utilisateur le demandera explicitement.
