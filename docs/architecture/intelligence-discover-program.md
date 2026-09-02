# Makolo — Programme I: Intelligence & Discover 2027

> **Statut : décision d'architecture et séquencement du programme I.**
>
> Ce document complète `makolo-domain-blueprint.md`, `strategic-action-roadmap.md`, `spatiotemporal-intelligence.md` et `analytics-event-intelligence.md`. Le code, les migrations, les tests et le `main` courant restent la vérité sur ce qui est effectivement livré.

## I — Vision

Makolo prépare une couche d'intelligence transverse et une évolution de Discover sans transformer l'application en chatbot ni rendre le produit dépendant d'un fournisseur, d'un modèle ou d'un LLM.

Principes :

1. **les domaines canoniques décident ; l'intelligence interprète, classe, résume ou suggère** ;
2. **aucune capacité critique ne dépend d'un provider** : Discover, Journey, Access, Capacity, Commerce, Payment et permissions restent utilisables sans intelligence externe ;
3. **les contrats métier restent dans leurs domaines propriétaires** : `DiscoveryIntent` appartient à Discovery, une explication de Readiness à Journey/Readiness, etc. ;
4. **`intelligence` est une app d'infrastructure transverse, pas un bounded context métier** ;
5. **provider ≠ protocole ≠ modèle** : le runtime route des capabilities vers des connexions configurées ;
6. **structured output + validation** avant toute utilisation métier ;
7. **permissions et minimisation des données avant appel externe** ;
8. **aucune autorité autonome** pour Payment, Access, Capacity, Permission, Mandate, Journey lifecycle ou décision de validation ;
9. **fallback déterministe obligatoire** pour les surfaces produit qui utilisent une intelligence optionnelle ;
10. **les données brutes sensibles ne sont pas journalisées par défaut**.

Le programme combine deux tracks :

- **Track A — Intelligence Foundation** : infrastructure transverse, providers, routing, policy, health, telemetry et évaluation ;
- **Track B — Discover 2027** : champ d'intention, contraintes visibles, filtres avancés secondaires, browse/recommendations et intégration optionnelle avec Intelligence.

Le point de jonction doit rester petit : Discovery produit et valide un `DiscoveryIntent`; Intelligence peut seulement fournir un candidat structuré quand l'interpréteur déterministe n'est pas suffisant.

---

## I1 — Intelligence Foundation

### Objectif

Créer l'app Django `intelligence` et les contrats stables qui permettent aux domaines de demander une capability sans connaître un fournisseur.

### Livrables

- app `intelligence` enregistrée dans `INSTALLED_APPS` ;
- `IntelligenceCapability` avec primitives initiales :
  - `TEXT_GENERATE` ;
  - `STRUCTURED_GENERATE` ;
  - `EMBED` ;
  - `RERANK` ;
- `IntelligenceRequest` / `IntelligenceResult` provider-neutral ;
- contrat `IntelligenceProvider` ;
- `NoOpIntelligenceProvider` ;
- registry en mémoire testable ;
- `IntelligenceGateway` avec fallback propre et absence de 500 lorsque rien n'est configuré ;
- erreurs typées (`ProviderUnavailable`, `CapabilityUnsupported`, `InvalidProviderResult`) ;
- aucun modèle métier, aucune clé, aucun provider réseau réel ;
- tests unitaires des contrats, routing minimal et fallback.

### Invariants

- aucune dépendance depuis `intelligence` vers les modèles métier canoniques ;
- les domaines peuvent dépendre de `intelligence`, jamais l'inverse pour interpréter leurs objets ;
- aucun appel réseau dans les tests ;
- l'absence totale de provider est un état normal.

### Critère de sortie

Un domaine peut demander une capability au gateway et obtenir soit un résultat valide, soit un résultat d'indisponibilité contrôlé, sans connaître le provider concret.

---

## I2 — Provider Registry, BYOK & Runtime Configuration

### Objectif

Permettre d'ajouter, tester, activer, désactiver et router des connexions provider sans modifier le code lorsque leur protocole est déjà supporté.

### Livrables

- configuration persistante provider-neutral ;
- séparation stricte `protocol` / `connection` / `model` ;
- portées préparées : `PLATFORM`, `SPACE`, `PROFILE` ;
- credential store chiffré avec clé maîtresse hors base ;
- aucune ré-exposition du secret complet après écriture ;
- key hint non sensible ;
- rotation/remplacement de credential ;
- routes par capability avec priorité/fallback ;
- health status et test de connexion explicite ;
- timeouts et bornes configurables ;
- `OPENAI_COMPATIBLE` comme premier protocole dynamique ;
- adaptateurs officiels supplémentaires seulement lorsqu'ils nécessitent réellement un protocole différent ;
- aucune URL arbitraire non bornée accessible aux utilisateurs ordinaires ;
- admin/configuration autorisée côté serveur ;
- migration additive et tests PostgreSQL pertinents.

### Comportement cible

Pour un protocole déjà connu :

`Ajouter connexion → base URL → clé → modèle → tester → assigner capabilities → actif`

ne nécessite ni commit ni redéploiement.

### Critère de sortie

Ajouter une nouvelle clé ou une instance OpenAI-compatible peut activer une route Intelligence sans changement de code, tout en conservant fallback et contrôle d'autorisation.

---

## I3 — Discovery Intent Foundation

### Objectif

Faire de Discover un moteur orienté intention sans remplacer son moteur canonique actuel.

### Livrables

- `DiscoveryIntent` comme value object/DTO non persistant ;
- `AppliedConstraint` pour la présentation des contraintes ;
- normalisation des paramètres GET actuels vers le nouveau contrat ;
- interpréteur déterministe initial ;
- compréhension bornée de : verticales, aujourd'hui/demain/week-end, périodes matin/après-midi/soir, proximité, gratuit et lieux résolus par Geography ;
- le texte non compris reste du texte de recherche ;
- aucune contrainte ambiguë inventée silencieusement ;
- extension du filtre temporel par période de journée sans nouvelle vérité métier ;
- compatibilité des URLs et tests Discovery existants.

### Critère de sortie

`Je veux voyager à Kolwezi demain matin` peut devenir un intent structuré lorsque les éléments sont résolubles, et l'ancien formulaire produit le même contrat sans régression.

---

## I4 — Discover 2027 UX

### Objectif

Remplacer le formulaire comme point d'entrée principal sans retirer les filtres avancés.

### Surface cible

- question principale : **« Que voulez-vous faire ? »** ;
- un champ naturel principal, non présenté comme chatbot ;
- quick actions : autour de moi, ce soir, voyager, événements, opportunités/être accompagné selon disponibilité réelle ;
- contraintes interprétées visibles sous forme de chips éditables/supprimables ;
- bouton `Filtres` donnant accès aux contrôles avancés ;
- résultats, carte et recommandations restent des interfaces visuelles structurées ;
- aucun dialogue bavard obligatoire ;
- Discover fonctionne également sans saisie via browse/recommendations ;
- backend essentiel utilisable sans JavaScript.

### Critère de sortie

L'utilisateur peut écrire, choisir ou simplement explorer, sans perdre la précision des filtres actuels.

---

## I5 — Discover × Intelligence, Telemetry & Hardening

### Objectif

Utiliser Intelligence comme augmentation optionnelle de Discover et mesurer objectivement son bénéfice.

### Pipeline

1. interprétation déterministe ;
2. si confiance suffisante : recherche canonique directe ;
3. sinon, capability Intelligence structurée ;
4. validation stricte du candidat `DiscoveryIntent` ;
5. recherche Makolo canonique ;
6. en cas de timeout, erreur, provider absent ou résultat invalide : fallback classique.

### Livrables

- capability métier exposée par Discovery via les primitives I1/I2 ;
- schema/versioning de structured output ;
- aucune donnée privée non nécessaire envoyée au provider ;
- aucun accès provider aux querysets/ORM ;
- telemetry privacy-safe : succès/échec, latence, capability, provider/model, sans prompt/réponse brute par défaut ;
- instrumentation produit : zero-result, reformulation, correction de contrainte, ouverture résultat, action démarrée/terminée ;
- évaluation comparative baseline déterministe vs intelligence ;
- tests timeout, provider down, invalid output, IDOR et absence de clé ;
- Discover reste pleinement utilisable provider-free.

### Critère de sortie

Une connexion configurée peut améliorer les requêtes naturelles complexes, mais sa suppression complète ne casse aucune fonction essentielle de Discover.

---

## Usages suivants possibles

Après validation de Discover, les mêmes fondations peuvent servir à des cas séparément décidés et évalués :

- Journey/Readiness : expliquer les prochaines actions à partir de faits canoniques ;
- Action Memory / Trusted Reuse : proposer des candidats, jamais déclarer une preuve valide seul ;
- documents : extraction structurée avec confirmation ;
- Analytics : narration de métriques calculées par Analytics ;
- CRM : langage naturel vers règles d'audience structurées, sans choix opaque des destinataires ;
- Notifications : regroupement/résumé de faits déjà autorisés ;
- Operations/Scanner : explication d'anomalies, jamais décision autonome d'accès.

Chaque nouveau consommateur doit garder son contrat métier dans son domaine et définir explicitement : données autorisées, fallback, validation, métrique de succès et actions interdites.

---

## Séquencement

```text
main
  ↓
I1 — Intelligence Foundation
  ↓
I2 — Provider Registry / BYOK / Runtime Configuration
  ↓
I3 — Discovery Intent Foundation
  ↓
I4 — Discover 2027 UX
  ↓
I5 — Discover × Intelligence + Telemetry + Hardening
  ↓
réconciliation avec le main réel du moment
```

Les checkpoints peuvent être empilés pour validation, mais ils ne doivent pas être mergés hors ordre. Avant la réconciliation finale, vérifier les trains concurrents et résoudre explicitement les collisions avec le `main` courant.
