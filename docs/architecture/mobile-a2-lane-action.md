# A2 — Lane Action & Orchestration

> **Développeur/agent 1**
>
> **Statut : work package préparé — NE PAS DÉMARRER avant A2_BASE_SHA**
>
> **Branche prévue : mobile/a2-action-orchestration**
>
> **Cible PR : mobile/a2-integration**

## 1. Mission

Construire les surfaces personnelles :

~~~text
Maintenant
En cours
Makolo Mark
~~~

Elles forment une même chaîne mentale :

~~~text
ce qui compte maintenant
→ ce qui est réellement engagé
→ ce que je demande à Makolo de comprendre/préparer/faire avancer
~~~

Le développeur 1 ne travaille pas Découvrir, Moi ou Avatar, sauf demande explicite de l'orchestrateur pour un composant réellement commun.

## 2. Préconditions

Ne commencer que lorsque l'orchestrateur fournit :

- A2_BASE_SHA ;
- mobile-a2-program.md réconcilié avec le main post-A1 ;
- mobile-a2-visual-behavior.md ;
- mobile-a2-local-first-surfaces.md ;
- mobile-a2-surface-contracts.md ;
- mobile-a2-acceptance-matrix.md ;
- confirmation que A1 est fusionné et vert.

La branche part exactement de A2_BASE_SHA.

## 3. Fichiers autorisés

Créer/modifier autant que possible sous :

~~~text
mobile/lib/features/now/**
mobile/lib/features/ongoing/**
mobile/lib/features/mark/**

mobile/test/**now**
mobile/test/**ongoing**
mobile/test/**mark**
~~~

Repositories/adapters spécialisés nouveaux autorisés, par exemple :

~~~text
mobile/lib/repositories/now_repository.dart
mobile/lib/repositories/ongoing_repository.dart
mobile/lib/repositories/mark_repository.dart
~~~

ou, si la convention finale A1 place les repositories dans chaque feature, suivre cette convention après vérification.

## 4. Fichiers interdits sans checkpoint orchestrateur

Ne pas modifier indépendamment :

~~~text
mobile/lib/app/**
mobile/lib/navigation/**
mobile/lib/design/makolo_theme.dart
mobile/lib/design/behavior_primitives.dart
mobile/lib/design/behavior_states.dart
mobile/lib/auth/**
mobile/lib/network/**
mobile/lib/sync/**
mobile/lib/data/local/**
mobile/pubspec.yaml
mobile/pubspec.lock
~~~

Ne pas modifier non plus les features de l'autre lane :

~~~text
mobile/lib/features/discovery/**
mobile/lib/features/me/**
mobile/lib/features/avatar/**
~~~

Si un besoin partagé apparaît, le documenter dans la PR et demander un petit changement orchestrateur sur mobile/a2-integration.

## 5. Maintenant

### Contrat

Question :

> **Qu'est-ce qui compte maintenant ?**

Source :

~~~text
GET /api/v1/me/now/
projection localisée A1 : personal.now
~~~

Le serveur décide l'appartenance, la priorité et les actions. Le client ne reclasse pas.

### Rendu

La première impression doit permettre de savoir en quelques secondes :

- s'il y a quelque chose à faire ;
- si rien n'exige d'action ;
- quelle est l'action prioritaire visible ;
- si les données sont anciennes ou offline seulement lorsque cela importe.

Ne pas créer un dashboard uniforme.

### États obligatoires

- snapshot local immédiat ;
- first load sans snapshot ;
- items ;
- vrai all-clear ;
- offline avec contenu ;
- offline sans contenu ;
- stale ;
- refresh avec contenu préservé ;
- erreur sync avec contenu préservé ;
- session expirée ;
- resume.

### All-clear

Seulement pour items=[] dans une projection connue :

> **Tout est en ordre. ✓**

Jamais pour une DB vide ou une première ouverture non synchronisée.

### Actions

Suivre capabilities + links.

Si un link mène à une profondeur A3 non encore construite :

- ne pas inventer la profondeur ;
- ne pas afficher un CTA mort ;
- conserver le contrat pour l'intégration A3.

## 6. En cours

### Contrat

Question :

> **Qu'est-ce que j'ai réellement engagé et où en suis-je ?**

Source :

~~~text
GET /api/v1/me/ongoing/
projection localisée A1 : personal.ongoing
~~~

Le runtime compose déjà plusieurs familles d'objets.

Ne pas traiter En cours comme :

- todo list ;
- Kanban ;
- liste brute de Journey ;
- agrégateur d'ORM.

### Présentation

L'UI doit rendre perceptibles les différences quand elles existent réellement dans le payload :

- action de ma part ;
- attente normale ;
- prêt ;
- blocage ;
- prochaine étape ;
- timing/lieu utiles.

Ne jamais dériver localement ces catégories à partir de statuts inconnus.

### Profondeur

A2 n'implémente pas Journey/Requirement/Dossier/Project complet.

Le détail n'est visible que s'il existe une destination mobile utile ou un petit read-only detail explicitement approuvé par l'orchestrateur.

## 7. Makolo Mark

### Contrat

Question :

> **Qu'est-ce que vous avez en tête ?**

Source :

~~~text
POST /api/v1/me/mark/
~~~

États normaux :

~~~text
resolved
completed
needs_clarification
needs_confirmation
unknown
unsupported
forbidden
~~~

### UX

Le Mark n'est pas un menu de fonctions.

Ne pas afficher des boutons de type :

~~~text
Comprendre
Retrouver
Réutiliser
Conserver
Faire avancer
~~~

La surface reste compacte :

~~~text
Mark
question
input
feedback
résultat/clarification/confirmation
~~~

### Offline

Le draft est local.

Ne pas :

- afficher completed localement ;
- interpréter localement ;
- blind-queue une action sensible ;
- envoyer automatiquement au retour réseau sans décision conforme au contrat.

### Confirmation

Afficher la conséquence humaine.

Le serveur/owner revalide l'autorité et l'état après confirmation. Respecter les idempotency keys lorsque l'owner l'exige.

## 8. Architecture locale de la lane

### Maintenant / En cours

Lecture principale :

~~~text
watch repository
→ store local
→ UI
~~~

Refresh :

~~~text
UI conserve le contenu
→ repository demande sync
→ sync écrit le store
→ UI observe le store
~~~

Le repository de feature peut adapter le payload pour la présentation, mais ne crée aucune nouvelle vérité métier.

### Mark

~~~text
draft repository local
+
Mark API distante
+
mapping des états serveur vers UX
~~~

La réponse Mark ne doit pas être persistée comme vérité métier dans une table ad hoc.

## 9. Composants de feature

Garder locaux tant qu'ils ne servent qu'à une surface.

Exemples possibles :

- NowPrioritySection ;
- NowAllClear ;
- OngoingItemRow ;
- OngoingContinuation ;
- MarkIntake ;
- MarkResult ;
- MarkClarification ;
- MarkConfirmation.

Ne pas créer MakoloCard global, AppHeader global ou SyncBanner global dans la lane.

## 10. Behavior obligatoire

Pour chaque surface :

- initial ;
- loading ;
- content ;
- empty ;
- success ;
- error ;
- offline ;
- stale ;
- syncing/pending si pertinent ;
- retry ;
- back ;
- resume ;
- session recovery ;
- Reduce Motion ;
- Semantics ;
- text scaling.

Aucun refresh ne remplace un contenu existant par un écran vide.

## 11. Product Language

Ne pas afficher les codes bruts :

~~~text
pending_approval
waiting
blocked
action_required
owner
projection
schema
outbox
~~~

Utiliser le label/summary serveur quand humain, ou un mapping produit limité et explicitement couvert par tests.

Ne pas créer une taxonomie parallèle complète dans Flutter.

## 12. Accessibilité

Tester au minimum :

- semantics de l'action principale ;
- ordre de lecture Maintenant ;
- all-clear ;
- Ongoing avec texte large ;
- clarification Mark ;
- confirmation Mark ;
- bouton retour ;
- erreurs non dépendantes de la couleur.

## 13. Motion / haptics

Motion :

- transitions courtes ;
- morphing Mark seulement si la causalité est améliorée ;
- aucune animation ne bloque l'action ;
- Reduce Motion respecté.

Haptics :

- éventuellement validation importante ;
- accomplissement réel ;
- erreur locale claire ;
- jamais chaque tap.

Un haptic de succès final n'est pas joué avant confirmation serveur de l'état requis.

## 14. Tests minimum

### Unit

- mapping payload → presentation model ;
- gestion des états Mark ;
- logique locale de draft ;
- freshness/presentation sans décision métier.

### Repository

- lecture locale immédiate ;
- refresh conserve snapshot ;
- erreur réseau ne supprime pas snapshot ;
- session/repository isolation Profile si applicable.

### Widget

Maintenant :

- local snapshot ;
- all-clear ;
- offline content ;
- no snapshot offline ;
- stale ;
- refresh.

En cours :

- plusieurs items ;
- empty ;
- waiting ;
- action needed ;
- blocker ;
- offline ;
- back context.

Mark :

- input ;
- resolved ;
- completed ;
- clarification ;
- confirmation ;
- unknown ;
- unsupported ;
- forbidden ;
- transport error ;
- offline draft ;
- resume draft.

### Accessibility

Semantics + text scaling ciblés.

### Goldens

Candidats :

- Maintenant all-clear ;
- Maintenant action principale ;
- En cours mixte ;
- Mark intake ;
- Mark clarification/confirmation.

## 15. Screenshots obligatoires

Pour les trois surfaces :

- petit téléphone ;
- moyen ;
- grand ;
- empty ;
- content ;
- offline ;
- error ;
- loading ;
- grand texte.

Ne jamais committer de PII réelle ou secret dans les captures.

## 16. Integration slice recommandé

Démontrer au moins une séquence :

~~~text
launch
→ Maintenant lit local
→ refresh discret
→ ouvrir En cours
→ revenir
→ ouvrir Mark
→ saisir draft
→ background/resume
→ draft toujours présent
~~~

Puis un scénario offline :

~~~text
contenu local
→ couper réseau
→ changer Maintenant/En cours
→ Mark draft
→ retour réseau
→ sync discrète
~~~

## 17. Review croisée

Avant merge, relire mobile-a2-lane-explore-self.md et signaler à l'orchestrateur :

- violations local-first ;
- duplication métier ;
- incohérence Behavior ;
- besoin injustifié de primitive partagée.

Ne pas modifier la branche de l'autre lane.

## 18. Contenu de PR

La PR vers mobile/a2-integration décrit :

- scope ;
- fichiers ;
- APIs consommées ;
- local storage impact ;
- behavior states ;
- captures ;
- tests exécutés ;
- limites A3 ;
- demandes de shared changes ;
- aucune migration Django.

## 19. Gate de sortie

La lane est mergeable seulement si :

- les trois surfaces sont utilisables ;
- aucun placeholder A1 ne reste sur leur contenu ;
- les shared/frozen files n'ont pas été modifiés hors checkpoint ;
- local-first est démontré ;
- aucune vérité métier n'est dupliquée ;
- aucune action morte ;
- tests verts ;
- visual QA revue ;
- accessibilité ciblée ;
- Product Language conforme.
