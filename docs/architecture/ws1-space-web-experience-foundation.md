# WS1 — Space Web Experience Foundation

**Statut :** intégré sur `main` via PR #421.  
**Base auditée :** `main@f640d0ddd6d7839944ef2d90abf48cbc3e381803`.  
**Branche :** `ws1-space-web-experience-foundation`.

## 1. Objet

WS1 établit la fondation Web de l’expérience Space sans déplacer les vérités métier hors de leurs domaines propriétaires.

Chaîne conservée :

```text
vérité owner
→ selector / service / autorisation
→ projection UX serveur ZS
→ présentation Web
```

Le Web ne reconstruit ni Permission, ni Mandate, ni archetype, ni responsabilité valide, ni capability.

## 2. Audit de départ

Le `main` de départ contient ZS1–ZS6. Le bootstrap `build_space_workspace()` et les projections ZS servent de source au shell.

Deux PR ouvertes ont été examinées avant branchement :

- #417 : Mobile uniquement ;
- #410 : Mayele uniquement.

Aucune ne touche les fichiers Web Space modifiés par WS1.

Les PR W1–W8 ont été relues comme historique d’architecture. Le runtime courant reste prioritaire.

## 3. Architecture retenue

La racine Web d’un Space devient l’entrée naturelle de l’expérience Space :

```text
/spaces/<slug>/
```

La Console historique reste disponible sur ses routes existantes, notamment :

```text
/spaces/<slug>/overview/
```

et les profondeurs owner-backed Activities, Requests, Access, Commerce, Payments, CRM, Groups, Funding, Partners, Operations, Analytics, Automation, Team, Settings, Transport, etc.

La Console est donc une profondeur/outillage. Elle n’est plus utilisée comme navigation primaire WS1.

## 4. Navigation Space

La navigation primaire WS1 est :

```text
Maintenant | Découvrir | [Makolo Mark] | Métier | Nous
```

Le quatrième libellé visible provient du `operating_preset.primary_business_label` exposé par ZS. Aucun dictionnaire frontend d’archetypes n’est ajouté.

Le contexte personnel conserve sans changement :

```text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
```

Le Makolo Home respecte l’acteur courant : dans une surface WS1, il revient à la racine du Space.

## 5. Responsabilité de lecture

WS1 consomme `workspace.responsibilities`.

La sélection se fait par query parameter `responsibility`, avec `all` par défaut.

Règles :

- le Space est résolu avant la responsabilité ;
- la clé doit appartenir aux responsabilités courantes renvoyées par le serveur pour ce Space ;
- une clé étrangère ou révoquée produit un 404 ;
- aucune ancienne responsabilité invalide n’est conservée silencieusement ;
- la responsabilité choisie est propagée entre les cinq portes ;
- changer de Space réinitialise naturellement la responsabilité ;
- aucune préférence UX n’est persistée en base.

La responsabilité reste un filtre de lecture et ne devient jamais une autorité.

## 6. Archetype et vocabulaire

WS1 lit le vocabulaire métier dans le read model ZS :

```text
operating_preset.primary_business_label
```

Exemple : un Space `education` peut afficher `Programmes`.

L’archetype n’accorde aucune capability.

## 7. Maintenant et Découvrir

WS1 consomme directement les builders serveur ZS utilisés par les APIs `now` et `discover`.

Lorsque le serveur retourne :

```json
{
  "selection": {
    "state": "unavailable",
    "reason": "no_safe_selection_contract"
  },
  "items": []
}
```

le Web affiche un état sobre et n’invente aucune urgence, priorité, recommandation ou heuristique issue de Payments, Requests, Capacity, Incidents, Automation ou Analytics.

La présentation approfondie reste réservée à WS2.

## 8. Métier, Nous et Makolo Mark

WS1 installe les portes et le contexte.

- Métier expose le vocabulaire serveur et un handoff vers les outils owner-backed.
- Nous conserve l’identité collective au premier plan et ne devient pas Settings.
- Makolo Mark est présent dans la navigation Space, mais WS1 ne crée aucune mutation Mark parallèle ni acting context fourni arbitrairement par le client.

Les profondeurs complètes restent réservées à WS3–WS5.

## 9. Compact / Adaptive / Expanded

WS1 réutilise le shell Mature W existant :

```text
Compact  < 768 px
Adaptive 768–1199 px
Expanded >= 1200 px
```

Aucune seconde architecture responsive ni SPA n’est introduite.

Le shell continue à utiliser :

- Django templates ;
- HTMX / progressive enhancement ;
- URLs normales ;
- refresh ;
- back/forward ;
- nouvel onglet ;
- navigation sans JavaScript sur les liens essentiels.

## 10. Sécurité et confidentialité

La résolution du Space part de `workspace_spaces()`, donc des Mandates Space/Activity actuels.

Ne suffisent jamais seuls :

- TeamMembership ;
- GroupMembership ;
- Assignment opérationnelle ;
- Platform authority.

Les responsabilités sont revalidées à chaque requête.

Le template reçoit le read model borné ZS, pas un dump de Permission/Mandate. Aucune donnée Credential, ProviderCredential, QR complet ou secret n’est ajoutée.

## 11. Performance

Le premier rendu reste server-rendered.

WS1 n’ajoute :

- aucun polling ;
- aucun cache privé persistant ;
- aucun chargement de tous les modules ;
- aucun appel API par item ;
- aucune reconstruction JavaScript des projections.

Les builders serveur existants sont appelés directement afin d’éviter un appel HTTP interne vers les APIs de la même application.

## 12. Persistance et migrations

WS1 ajoute **zéro modèle** et doit produire **zéro migration**.

Le contexte de responsabilité reste éphémère et URL-scoped.

## 13. Tests

La suite ciblée WS1 couvre :

- visiteur et outsider ;
- shell Space ;
- cinq destinations Space ;
- conservation des cinq N1 personnelles ;
- vocabulaire d’archetype serveur ;
- responsabilité valide ;
- responsabilité étrangère ;
- responsabilité révoquée ;
- TeamMembership seul ;
- GroupMembership seul ;
- Assignment opérationnelle seule ;
- Platform authority seule ;
- autorité Activity-scoped ;
- absence de matériau sensible dans le shell.

L’E2E WS1 couvre les largeurs représentatives 400, 800, 1199, 1200 et 1440 px, l’absence d’overflow, les URLs directes, HTMX et back/forward.

## 14. Non-objectifs

WS1 ne ferme pas :

- la présentation complète Maintenant / Découvrir ;
- les profondeurs Métier par archetype ;
- Nous / Relations / Pilotage ;
- Jour J / Live / Scanner ;
- l’orchestration complète Makolo Mark ;
- la migration de toute la Console historique.

## 15. Handoff WS2+

```text
WS2 — Maintenant & Découvrir
WS3 — Métier & Archetypes
WS4 — Nous, Relations & Pilotage
WS5 — Jour J, Live, Scanner & Mark
WS6 — réconciliation et fermeture Web Space
```

## 16. État post-merge

WS1 est intégré sur `main` via la PR #421.

- base auditée initiale : `main@f640d0ddd6d7839944ef2d90abf48cbc3e381803` ;
- HEAD fonctionnel final de la branche : `e504f32f7c4658bdf14f7cfc547792a857ede65c` ;
- commit de merge : `af285c015881c2ff7cbeacc9df80f4d52593c8a6` ;
- aucune migration WS1 ;
- les gates frontend artifact sync, Django checks et missing migrations ont passé avant merge ;
- le correctif final a réparé la spec E2E `permissions.spec.mjs` sans modifier les invariants d’autorité ni affaiblir les tests.

La suite du programme Web Space reste WS2–WS6 selon le handoff ci-dessus.
