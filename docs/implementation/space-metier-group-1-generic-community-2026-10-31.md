# Métier Space — groupe 1 : Activités (generic) et Initiatives (community)

Date : 31 octobre 2026. Dépôt : `TraditionLearningCommunity/makolo`.
Branche unique : `fix/discover-a-continuation-context-20261014` (PR #522).
Base `main` vérifiée : `d0f0ec421c94c255fa4c0acd3509938a70c6322f`.
Ce checkpoint poursuit les lots 0/1 et démarre 2A + le **premier** groupe de 2B ; il ne prétend pas couvrir les six autres archétypes.

## Problème utilisateur

Métier generic doit répondre à « Qu’est-ce que nous faisons réellement, qu’est-ce qui se prépare et qu’est-ce qui continue ? ».

Métier community doit répondre à « Qu’est-ce que nous faisons concrètement avancer ensemble, sur le terrain ou dans la durée ? ».

Jusqu’ici, le serveur fournissait des sections owner-backed mais pas de véritable logique de lecture N1 : continuité, portefeuille durable et domaines spécialisés restaient un empilement de listes identique, avec un ordre plutôt statique.

## Livré dans #522

- Nouveau module de **composition dérivée** `organizations/space_work_composition.py`. Aucun modèle/migration, état persistant, Permission, Workflow ou fact owner dupliqué.
- `build_space_work_projection` expose un `business_world` additionnel uniquement pour `generic` et `community`. Les clients historiques peuvent continuer à utiliser `sections`, `selection`, `links` et `capabilities`.
- `business_world.perspectives` référence les **sections déjà autorisées** (pas des copies d'Activity ou des items artificiels). `reading_groups` compose `continuity`, `portfolio`, `specialized`, `history` et `other` conditionnellement à des faits existants. Aucun groupe vide n'est injecté. Une nouvelle verticale non connue de la grammaire reste accessible dans `other`.
- Le `generic` mène par sa continuité lorsqu'elle existe ; sans continuité visible, son portefeuille d'Activities est la première réalité lisible. Le `community` privilégie ce qui avance et garde les initiatives durables comme portefeuille. Aucun Group/Team/Membership/Partner n'est promu artificiellement en Initiative.
- Les espaces calmes peuvent présenter un message de continuité apaisée, **uniquement pour une projection N1 non filtrée** ; une sélection partielle n'est jamais proclamée calme.
- L'Activity durable publiée peut exposer sa **prochaine Occurrence réellement programmée et autorisée** (date/heure, identité owner). Aucun nouveau statut `ongoing` pour une Activity publiée. La projection réutilise le parcours des Occurrences déjà consultées.
- Le Web consomme directement les groupes et questions serveur dans `organizations/space_work_web.py` / `templates/organizations/space/work.html` sans recalculer des états ou créer une nouvelle logique métier.
- Les six autres archétypes gardent leur contrat actuel, sans `business_world` inventé.

## Frontières et garanties

- `ACTOR_CONTEXT = Space` et `VIEWER = Profile`.
- Visibilité d'Activity/Occurrence/Services/Commerce filtrée par les selectors existants, leurs permissions et la perspective de responsabilité.
- La composition ne révèle pas de membres, groupes, finances ni données privées ; elle référence seulement les sections et les Occurrences déjà permises.
- Ni feed communautaire ni ranking ni KPI ni WorkItem ni second workflow. Pas de création contextuelle sans action owner réellement disponible.
- L'API et les mutations propriétaires restent distinctes. N2/N3 ne sont pas redéveloppés ici ; les handoffs propriétaires existants demeurent.

## Tests ajoutés dans #522

- `organizations.test_zs3_space_work_api` : monde vide réel ; groupe portfolio au calme ; continuité avant portfolio ; composition community avec Activity + Occurrence ; visibilité bornée Activity et absence de fausses perspectives ; sélection qui ne déclare pas un état calme global ; régression des six autres archétypes ; prochaine Occurrence vérifiée.
- `organizations.test_ws3_space_work_web` : groupe generic au calme, groupe community avec action future, absence de faux chapitres en état vide.

Commandes à exécuter localement (pas de CI imposée pour poursuivre ce travail) :

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_zs3_space_work_api organizations.test_ws3_space_work_web
```

**État de validation :** code poussé, tests ajoutés mais non exécutés dans la session distante ; aucun merge ni attestation de réussite. Si les tests locaux révèlent un défaut, corriger la cause sur #522.

## Suite contrôlée : lot 2B par groupes

1. **Groupe 2 : Éducation / Prestations** — vrai langage de Programmes/Services, demandes, cas, requirements et handoffs propriétaires ; ne pas copier l'autorité de bénéficiaire.
2. **Groupe 3 : Commerce / Transport** — Offers, Orders, routes, véhicules, Occurrences/Départs, Capacity et profondeur Jour J ; structure != état live.
3. **Groupe 4 : Créatif / Média** — créations, productions, occurrences et médias owner-backed ; pas de feed/posts artificiels.
4. **Étape commune Web/Flutter** — N1/N2/N3, behavior, owner handoffs, adaptation, local-first et révocation, à partir des projections consolidées. Flutter ne doit pas introduire de source de vérité locale.

Avant tout lot suivant, reprendre le HEAD courant de #522 et procéder à un collision audit. Aucun nouveau PR, pas de merge sur main.
