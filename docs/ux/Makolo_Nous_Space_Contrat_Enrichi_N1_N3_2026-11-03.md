# Makolo — Nous Space : contrat enrichi et continuité avec Moi

**Date de consolidation :** 3 novembre 2026  
**Nature :** addendum conceptuel et contrat de fermeture UX/Presentation, non migration et non format API imposé  
**Statut :** décisions de conception consolidées ; implémentation et validations à confronter au HEAD de travail courant  
**Périmètre :** Profil personnel / Moi comme référence de grammaire, Space / Nous comme objet de réalisation ; Django, Web, Flutter et local-first  
**Branche de travail décidée :** PR #522 `fix/discover-a-continuation-context-20261014` ; **#528 fermée sans merge**, diagnostic repris dans #522.  
**Repère GitHub consulté pendant cette consolidation :** #522 ouverte, HEAD observé `5df3543152bf62c59f143fb9fe956c29726f6946`. Ce repère n'est pas une base figée : vérifier de nouveau avant chaque écriture.  
**Promesse :** « Makolo marche pour vous. »  
**Principe :** « Pas le plaisir de rester. Le plaisir d'avancer. »

## 0. Fonction du document et méthode de lecture

Ce document **n'annule pas** :

1. `Makolo_Contrat_Moi_et_Nous_Gele_2026-10-06.md` (contrat conceptuel gelé) ;
2. `Makolo_Moi_Nous_Contrats_Donnees_Serveur_Client_Presentation_Consolidation_2026-10-10.md` (contrat données, serveur, client, Presentation) ;
3. `docs/ux/Makolo_UX_Nous_Identite_Organisation_Collective_Contrat_Consolide_2026-10-08.md` et les contrats visuels/Behavior/mobile ;
4. le code, les modèles, les migrations, les tests et les permissions actuellement présents dans `main`, prioritaires sur toute documentation.

Il **complète** ces références par les décisions prises lors de la lecture comparée des captures Android de Moi et Nous et par les précisions explicites suivantes : **un même langage Passeport Makolo pour Profil et Space**, **Ressources de cet Espace comme territoire de Nous**, et **harmonisation Presentation Moi/Nous sans fusion métier**. Ces décisions sont des enrichissements récents ; elles ne doivent pas être faussement attribuées comme déjà écrites dans les deux anciens contrats.

**Distinction de statuts :**
- **HÉRITÉ** : exigence déjà présente dans les documents gelés.
- **CONSOLIDÉ** : précision ou décision formulée au cours de la conversation récente.
- **À VÉRIFIER** : contrat technique, parcours ou politique dont l'existence complète n'a pas été démontrée par le code et les tests actuels.
- **NON RETENU** : proposition écartée explicitement.

Aucune ligne de ce document ne crée automatiquement un modèle persistant, un droit, une API, une route, une donnée publique ou une fonctionnalité déjà livrée.

---

## 1. Doctrine commune : deux identités, un même Makolo

**HÉRITÉ — Navigation et sens :**

```text
CONTEXTE PERSONNEL : Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
CONTEXTE SPACE      : Maintenant | Découvrir | [Makolo Mark] | Métier  | Nous
```

**Moi** répond à : « Qu'est-ce qui est déjà en place autour de moi pour faciliter la suite ? » ; il rend compréhensible le **capital personnel** du Profile.

**Nous** répond à : « Qui sommes-nous et comment fonctionnons-nous ensemble ? » ; il rend compréhensible **l'identité durable, la structure, les relations, les ressources légitimes et la gouvernance du collectif**.

**CONSOLIDÉ — Symétrie d'expérience, non symétrie métier :** Les deux surfaces utilisent un langage Presentation reconnaissable : identité d'abord, territoires/sections ensuite, aperçus utiles, profondeurs explicites, même discipline de médias, de navigation, de fraîcheur et d'accessibilité. Elles ne deviennent jamais `Moi<Space>`, `Nous<Profile>` ou un `ActorCapital` universel.

Le `Profile` est une personne globale ; le `Space` est un acteur collectif durable. Le **viewer de Nous est toujours un Profile humain** ; un Space n'a pas de compte humain, de mot de passe ou d'Avatar-personne. Dans un contexte Space, l'Avatar du shell continue d'identifier le viewer, tandis que la représentation institutionnelle identifie l'acteur collectif.

### 1.1. Nature des personnes et portée de la comparaison

**CONSOLIDÉ — Langage humain :**

- Passeport d'un **Profile** : représentation identitaire d'une personne physique, éventuellement comparable à une carte d'identité enrichie ou à un CV.
- Passeport d'un **Space** : représentation identitaire du collectif, éventuellement comparable à une carte d'identité institutionnelle, à un dossier de présentation ou à un CV collectif.

**Limite impérative :** `Space` ne signifie pas automatiquement « personne morale juridiquement constituée ». Une entreprise, une association constituée ou une institution peut avoir une personnalité juridique ; un collectif informel peut ne pas l'avoir. L'UX doit employer le vocabulaire adapté au fait réel, sans fabriquer un statut légal, une vérification ou une certification.

---

## 2. Passeport Makolo : même langage pour Moi et Nous

**DÉCISION CONSOLIDÉE :** « Passeport Makolo » est le **nom d'expérience commun** au Profil personnel et à l'Espace. Ne pas inventer « Voir notre identité » comme profondeur concurrente, ni reléguer le Passeport Space à une ligne quelconque entre abonnement, connexions et paramètres.

La partie commune est la **représentation/export de faits légitimes** ; la partie spécifique est le sujet, les faits propriétaires, les variantes et les règles d'exposition. Le Passeport ne devient ni le Profile, ni le Space, ni une nouvelle vérité canonique ni un Credential universel.

### 2.1. Sémantique commune

```text
SUJET : Profile OU Space (jamais inféré par le client)

FAITS PRÉSENTABLES
  DECLARED   : déclarations attribuées à leur déclarant
  ESTABLISHED: faits et preuves admis au degré réellement établi
  ISSUED    : titres/credentials délivrés par l'autorité compétente

     → Passport owner (Sharing/Passport + propriétaires concernés)
     → preview N1 limitée et autorisée
     → lecture N2
     → partage / export / variantes owner-backed, si permis
```

**HÉRITÉ :** `DECLARED ≠ ESTABLISHED ≠ ISSUED` ; Passport ≠ Proof ≠ Credential Trust ≠ AccessCredential. Un Passeport peut présenter une chose mais ne lui attribue pas plus de réalité ou de force probante que la source. Le consentement et la divulgation minimale précèdent le partage.

**À VÉRIFIER au runtime :** disponibilité des projections et variantes de Passeport pour le Space, permission de consulter/partager, handoff native Flutter, PDF/lecteur, retraits/révocation, présentation publique, modes offline. Dans le code étudié précédemment, `sharing/passport.py` contient déjà `build_profile_passport` et `build_space_passport` : **réutiliser ce propriétaire**, sans conclure que toutes les routes et expériences mobiles sont complètes.

### 2.2. Composition N1 à retenir

- Identité reconnaissable du Profile/Space au début.
- **Territoire Passeport Makolo visible distinctement**, si une entrée réelle et légitime est disponible ; le traitement visuel peut être fort, comme sur Moi, sans prétendre que le Passeport est un document d'État.
- Un aperçu simple : « Mon passeport » / « Passeport de cet Espace », avec formulation d'action pertinente (« Consulter », « Présenter », « Partager » uniquement si autorisé).
- Les détails, variantes, contenus sensibles et exports restent en profondeur propriétaire.
- Si le Passeport n'est pas disponible ou non autorisé, état local honnête ; aucune carte trompeuse.

**NON RETENU :** « Voir notre identité » comme substitut du Passeport. L'identité compacte reste dans le haut de Nous ; le Passeport porte le parcours de présentation plus riche.

---

## 3. Ressources : une famille pour Moi et un territoire pour Nous, sans fusion des propriétaires

**HÉRITÉ — Moi :** `RESOURCES` distingue `PERSONAL_ASSETS[]`, `PROOFS[]` et `CREDENTIALS_TRUST[]`. `Access` demeure une famille autonome, obtenue par handoff « Mes accès », et non un sous-type Resource ; `PersonalAsset ≠ JourneyArtifact ≠ Proof ≠ Credential Trust ≠ AccessCredential`. Posséder une pièce ≠ la retrouver ≠ satisfaire un Requirement.

**CONSOLIDÉ — Nous :** ajouter explicitement dans la grammaire N1 de Nous le territoire humain **« Nos ressources » / « Ressources de cet Espace »**. Il permet de reconnaître les ressources **réellement attribuées au Space et consultables par le viewer**, sans se transformer en bibliothèque de tous les fichiers associés à ses membres, Activities ou démarches.

### 3.1. Frontières de propriété

Une ressource peut être :

- détenue personnellement par un Profile ;
- réellement possédée, administrée ou partagée institutionnellement par un Space selon un propriétaire canonique ;
- une pièce affectée à une Activity, une Occurrence, une Journey ou un Dossier ;
- une Proof ou Credential Trust portant sur un sujet donné ;
- un document lié à un Requirement, sans que sa simple présence suffise à le satisfaire.

**Ce ne sont pas des relations équivalentes.** Une personne membre d'un Space n'y transfère pas ses PersonalAssets ; le fait qu'une Activity appartienne au Space n'en fait pas tous les artefacts des « ressources institutionnelles » ; une Proof n'est pas nécessairement un document consultable par tous les membres. La visibilité dépend de l'owner, du sujet, du purpose et de l'autorité effective.

### 3.2. Contrat UX du territoire « Nos ressources »

**N1 :** aperçu **borné et justifié** de ressources institutionnelles légitimement visibles ; éviter une liste exhaustive de documents. Libellés simples, type/provenance lorsque cela aide à comprendre, état de disponibilité réel, entrée vers une collection/profondeur propriétaire existante si elle est autorisée.

**N2 :** explorer, rechercher ou filtrer les ressources institutionnelles si le backend actuel le permet ; distinguer document, Proof, Credential et ressource au lieu de leur attribuer une classe universelle. La recherche ne doit pas conclure « aucune ressource » lorsque seule une partie est visible.

**N3 :** consultation, partage, ajout ou gestion chez le propriétaire métier pertinent, avec vérification serveur. Ne pas bâtir un stockage générique `SpaceResource` avant d'avoir audité les domaines et relations déjà existants.

**États :** `visible mais vide`, `non divulguable`, `inconnu`, `erreur partielle`, `offline avec snapshot encore lisible`, `autorité révoquée` doivent être distinguables. Ne jamais exposer dans la racine URLs privées, chemins de stockage, hash, credentials complets, fichiers ou PII non nécessaires.

**À VÉRIFIER :** le contrat complet d'agrégation des ressources de Space, ses droits de lecture, son inventaire canonique et sa route N2. Le simple fait qu'une expérience Resources personnelle existe ne prouve pas que la même projection Space soit déjà livrée. Implémenter par composition de propriétaires si possible, sans nouvelle table, ni transfert automatique de droits.

---

## 4. Nous : le noyau conceptuel enrichi, sans supprimer l'ancien

L'ancien contrat Nous fixe : `ACTOR_CONTEXT`, `VIEWER`, `VIEWER_RELATION`, `COLLECTIVE_IDENTITY`, `TEAM`, `RESPONSIBILITY_STRUCTURE`, `GOVERNANCE`, `RELATIONS`, `TRUST`, `INSTITUTIONAL_HANDOFFS`. **Tous sont conservés.** Le Passeport et les Ressources deviennent deux **territoires UX** supplémentaires, non de nouvelles autorités ni des tables.

### 4.1. Contrat conceptuel enrichi (PAS un wire JSON à imposer)

```text
NOUS — SURFACE DE PRÉSENTATION
│
├─ ACTOR_CONTEXT             1 Space courant
├─ VIEWER                    1 Profile humain
├─ VIEWER_RELATION           1 projection liée au viewer
│  ├─ responsabilités/contextes pertinents 0..n
│  ├─ authority_summary?     0..1, côté serveur
│  └─ handoffs autorisés     0..n
│
├─ COLLECTIVE_IDENTITY       1 portrait institutionnel durable
│  ├─ identité / représentation / archétype / lifecycle
│  ├─ présence publique / mission / localisation générale?
│  └─ faits de contact autorisés?
│
├─ PASSPORT_TERRITORY        0..1 preview UX  [ENRICHISSEMENT]
│  ├─ disponibilité réellement établie
│  ├─ preview autorisée?
│  └─ owner_handoff?
│
├─ TEAM                     0..1 résumé ; 0..n équipes/personnes visibles
├─ RESPONSIBILITY_STRUCTURE 0..1 résumé ; 0..n responsabilités
├─ GOVERNANCE               0..1 résumé ; 0..n Owners/autorités projetées
├─ RELATIONS                0..1 résumé ; 0..n handoffs par owner
│
├─ RESOURCES_TERRITORY       0..1 regroupement UX [ENRICHISSEMENT]
│  ├─ aperçus de ressources owner-backed 0..n
│  ├─ statut de visibilité/fraîcheur par source
│  └─ owner_handoffs 0..n
│
├─ TRUST                    0..1 résumé ; 0..n faits établis
└─ INSTITUTIONAL_HANDOFFS   0..n, secondaires
```

**Important :** `PASSPORT_TERRITORY` et `RESOURCES_TERRITORY` sont des **noms de conception**, pas des clés API obligatoires. La présentation peut les composer à partir de routes/projections propriétaires existantes. Leur cardinalité de preview n'est pas une limitation arbitraire des données de profondeur.

### 4.2. Identité du Space et relation du viewer

Le haut de Nous présente l'identité **du Space**. « Ma place dans cet Espace » exprime la relation **du viewer à ce Space**. Une personne peut être propriétaire, gestionnaire d'activité, collaborateur ou avoir plusieurs perspectives ; cela ne change pas l'identité du collectif.

**HÉRITÉ — invariants de responsabilité et autorité :**

```text
Assignment = responsabilité
Mandate/Permission = autorité
TeamMembership / GroupMembership ≠ autorité
created_by ≠ Owner perpétuel
Archetype ≠ Permission ≠ Entitlement ≠ forme juridique
Lifecycle ≠ Trust ≠ Readiness
```

Une projection de perspective issue de Mandates peut apparaître dans l'expérience pour aider le viewer à se situer, mais elle **ne doit pas être présentée comme un Assignment opérationnel**. Le bloc « Propriétaire d'Espace / Périmètre collectif » observé dans les captures doit être rendu comme **autorité ou place du viewer**, pas comme preuve qu'il assume personnellement toutes les responsabilités du Space.

---

## 5. Contrat de composition N1 : reprendre les bons principes de Moi

**HÉRITÉ — Moi :** surface SECTION-FIRST / TERRITORY-FIRST, identité en ancre, sections durables, aperçus bornés, retour N2/N3, états locaux. **CONSOLIDÉ — Nous :** mêmes conventions perceptives et comportementales, sans recopier mécaniquement les mêmes objets métier.

### 5.1. Déroulé conceptuel de Nous Compact

Ordre candidat, adaptable à la réalité, à la visibilité et au contrat Presentation :

1. **Identité collective** — nom du Space, représentation/logo si disponible, description/mission utile, archétype et localisation générale réellement exposable ; pas de fiche administrative exhaustive.
2. **Passeport Makolo** — « Passeport de cet Espace », repère identitaire fort, profondeur Sharing/Passport réelle ; pas un simple item perdu au milieu de la gestion.
3. **Notre organisation** — structure et équipe visibles, nombre seulement si explicitement divulguable, aperçu compact des collaborateurs ou équipes et entrée vers N2.
4. **Ma place / Nos responsabilités** — relation viewer→Space et responsabilités collectives distinguées ; une autorité de propriétaire n'est pas un Assignment. Les deux sous-lectures peuvent avoir des titres et profondeurs séparés.
5. **Nos relations** — résumé institutionnel et handoffs distincts vers Groups, CRM/Contacts, Audiences, Partners et autres propriétaires ; pas de répétition automatique de la liste Team.
6. **Nos ressources** — aperçu limité des documents, Proofs, Credentials ou autres ressources que l'Espace peut réellement présenter/mobiliser sous les droits du viewer ; pas de collection fictive.
7. **Gouvernance et confiance** — Owners et autorités si visibles, faits Trust précis, sans score ni faux badge universel ; garder leur séparation sémantique même en regroupement de présentation.
8. **Profondeurs institutionnelles secondaires** — abonnements, connexions, configuration, pilotage, autres outils autorisés : accessibles sans devenir la racine ni un mur de CTA.

Ce n'est **pas** une obligation de montrer huit grandes cartes. Une famille vide, restreinte ou absente peut se résumer ou disparaître localement lorsque le contrat le permet. Un Passeport réellement disponible garde néanmoins une visibilité comparable à son équivalent dans Moi.

### 5.2. Références concrètes des captures Android fournies

**Moi — observations :** identité/portrait en haut, Passeport Makolo comme surface fortement reconnaissable, titres de sections avec bandeaux clairs, intérêts sous forme de chips, collectifs en lignes à chevron, territoires Mes accès / Mon historique / Mes ressources / Mes appuis. On ne doit pas copier ses imperfections : titres très longs, « Accès utilisé » répété ou plusieurs « Équipe principale » indistinctes.

**Nous — observations :** header et switcher préservés, carte d'identité Youth Policy Lab, colonnes de sections répétant titre + sous-titre technique + carte + lien violet, liste des membres (Blaise, Fabrice, Gael, Kevin, Yannick dans l'exemple), catégories Équipe/Groupes/Contacts/Publics/Partenaires listées même lorsqu'elles affichent « Aucune relation visible », suivi de Gouvernance/Confiance et d'un long ensemble Abonnement/Connexions/Passeport/Modifier/Piloter. Le filtre de responsabilité du haut est tronqué (« Toutes mes respo... »).

**Corrections N1 à retenir :**

- Harmoniser bandeaux, hiérarchie, espace et navigation avec Moi, sans faire un dashboard ni une grille administrative.
- Retirer le caractère systématique « titre + explication + carte + CTA » pour chaque section ; choisir le traitement selon le sens du fait (passport fort, aperçu d'équipe léger, relation compacte, Trust discret, settings secondaire).
- Ne pas afficher les cinq collaborateurs à la racine si un aperçu plus court suffit, et ne pas les répéter dans « Relations ».
- Ne pas présenter trois catégories vides comme trois contenus riches ; conserver la navigation N2 vers les propriétaires pertinents.
- Humaniser les formulations : « Mandates institutionnels » → « Autorité et gouvernance » selon contexte ; « n'est projeté » → « aucune vérification publique active à afficher » ; « au moins 4 relations dans cet aperçu » → une formulation indiquant honnêtement qu'il s'agit d'une sélection partielle.
- Ne jamais transformer un compte partiel de 4 items en compte total certain.
- Corriger les libellés tronqués des contrôles du shell ; préserver accessibilité avec textScale 1.3/1.6.
- Rassembler les options institutionnelles secondaires dans un territoire discret, en conservant leurs vraies destinations.
- Réutiliser les éléments Presentation et Behavior existants ; ne pas introduire un design system isolé de Nous.

### 5.3. Grammaire d'une unité N1

```text
TERRITOIRE
  Reconnaissance : quoi / qui / quelle relation ?
  Résumé autorisé : fait précis, quantité seulement si honnête et exposable
  Provenance / fraîcheur : si essentielle à la compréhension
  Action : handoff vérifié, secondaire quand nécessaire
  États : visible / vide / masqué / inconnu / erreur / offline
```

**Pas de remplissage artificiel**, de métrique de popularité, de score de confiance, de score de complétion, d'organigramme imposé ni de collection décorative.

---

## 6. N2 / N3 : continuité des territoires, sans débordement métier

**N2 :** approfondir Passeport, Team, Responsabilités, Relations, Ressources, Trust, Gouvernance, avec choix/selection et retour conservés. La présence d'un handoff signifie que la profondeur existe pour ce viewer et ce Space ; le client ne déduit pas la route depuis un libellé `kind`.

**N3 :** modifier identité, gérer Team, affecter une responsabilité, éditer un Passeport, partager un document, transférer Ownership, changer le lifecycle, gérer abonnement/connexions uniquement chez les owners et après revalidation. Un formulaire local, un snapshot ancien ou un bouton affiché ne garantit pas que l'opération reste autorisée.

Le **Métier** répond à « Que faisons-nous / opérons-nous ? » ; les commandes, produits, véhicules, activités, dossiers et programmes restent chez leurs owners. Leur existence peut influencer une synthèse humaine, mais ne devient pas un contenu d'identité collective ni une ressource institutionnelle sans relation légitime.

---

## 7. Propriétaires, API, Web, Flutter : mapping à vérifier plutôt que remplacer

| Dimension Nous | Owner canonique attendu | Observation antérieure sur la branche #522 | Décision |
|---|---|---|---|
| Identité | Organizations / Space | `space_us_projection.py` expose `identity`, `organization` | Conserver ; améliorer présentation sans copier Métier |
| Relation viewer / perspectives | Authorization + Workspace projection | `authority`, `responsibilities`, `handoffs` | Distinguer Mandate et Assignment en microcopy |
| Équipe / collaborateurs | Organizations / Team | `team`, preview conditionné au droit Team | Divulgation minimale, pas de count restreint |
| Ownership / gouvernance | Authorization / Mandates | `ownership` conditionné aux capacités | Aucun owner inféré de `created_by` |
| Relations | Groups, CRM, Audience, Partners + projection de lecture | `relationships.sections` composé sous permissions | Résumé sans copie ni double comptage |
| Trust | Trust | `trust` via faits et claims établis | Pas de score ni de vérification universelle |
| **Passeport de cet Espace** | **Sharing/Passport et owners sources** | `build_space_passport` connu ; handoff aperçu sur Android constaté | Intégrer territoire identitaire N1 et profondeur réelle ; vérifier fonctions natives |
| **Ressources de cet Espace** | **Owners Assets / Proof / Trust / ressources métier selon leur véritable sujet** | Contrat d'agrégation Space non confirmé | Composer par sources autorisées ; ne pas inventer une table générique |
| Paramètres / abonnements / connexions | Domaines institutionnels concernés | Handoffs observés en bas de Nous | Réduire leur poids N1, conserver destination et autorité |

**Compatibilité** : `space.us` et ses clés déjà consommées par Web/Flutter ne doivent pas être remplacées brutalement par cet organigramme conceptuel. Toute évolution de projection doit être additive et testée, ou se faire dans un selector/read model côté présentation si les propriétaires suffisent. Les handoffs Web et Flutter peuvent avoir des routes natives distinctes ; chacun doit viser une vraie profondeur.

**Source de vérité** : le code/HEAD principal courant prévaut ; les inventaires précédents datent de lectures antérieures et ne sont pas une attestation de couverture complète à l'instant du développement.

---

## 8. Sécurité, visibilité, continuité et local-first

1. **Viewer = Profile, actor = Space** ; isolation stricte par Profile + Space + scope pertinent.
2. Le fait d'être TeamMember, GroupMember ou auteur de la création du Space n'accorde pas Mandate/Permission.
3. Viewer Activity-limited : identité minimale ; pas de Team privée, ownership, contacts internes, ressources sensibles ni gestion institutionnelle globale.
4. Données publiques, données d'un collaborateur, données du Space et données d'une Activity : **quatre scopes qui ne se transfèrent pas implicitement**.
5. Un aperçu cache/stale peut servir à comprendre ce qui était connu, pas à garantir un droit courant ni une validité institutionnelle.
6. Après révocation explicite, invalider ou masquer les données privées dérivées et les actions sensibles ; aucune mutation offline présumée confirmée.
7. Une erreur d'agrégation Ressources/Passport/Trust ne doit pas effacer l'identité ou les autres territoires.
8. `Cache-Control: private, no-store` des endpoints privés Web n'est pas une permission de stockage illimité côté application ; utiliser exclusivement le noyau local-first existant et sa politique de rétention.
9. Confidentialité : pas de clés privées, chemins de stockage, QR/AccessCredentials complets, PII privée, Permissions brutes ni contenus documentaires non autorisés dans la racine.
10. Identité Space suspendu/archivé : conserver le portrait et expliquer le lifecycle, sans déduire des règles de mutation que l'owner n'a pas exposées.

---

## 9. Critères de sortie et tests de fermeture

### 9.1. N0 — Réconciliation

- Vérifier `main`, HEAD #522 et la PR empilée #533 au moment de modifier ; comparer les surfaces qui collisionnent.
- Confirmer que #528 est fermée sans merge, son diagnostic déjà repris dans #522, **sans reproduire** le chantier.
- Tracer chaque territoire : owner → selector/read model → API → stockage local → presentation Web/Flutter → action/route N2/N3.
- Séparer clairement **existant**, **partiel**, **manquant**, **non encore testé**.

### 9.2. N1 — Composition et clarté

- Identité collective reconnaissable dès le début ; Avatar viewer reste personnel.
- Passeport Makolo du Space visible comme territoire identitaire légitime, pas ligne de paramétrage.
- « Nos ressources » présente seulement un aperçu owner-backed, ou indique honnêtement l'indisponibilité de l'inventaire jusqu'à son raccordement.
- Team, responsabilités, autorité, relation viewer et ownership ne se confondent pas.
- Relations et équipes ne se dupliquent pas ; pas de catalogue de sections vides.
- Settings/abonnement/connexions/pilotage secondaires sans perte de parcours.
- Libellés humains et non tronqués ; hiérarchie visuelle proche de Moi mais contenu propre à Nous.

### 9.3. Tests serveur / permission

- Visiteur, outsider, TeamMember sans Mandate, authority Space, authority Activity-only, Mandate révoqué, accès inter-Space (IDOR).
- Team et effectifs interdits quand visibilité restreinte ; plusieurs Owners supportés, dernier Owner protégé par owner.
- Passeport Profile vs Passeport Space : sujet correct, variantes et exposition bornée, public/privé distinct, export/partage autorisés et retrait.
- Ressource personnelle non visible comme ressource Space par appartenance Team ; ressource Activity non héritée automatiquement ; Proof ≠ Asset ≠ Credential ≠ Access.
- Aucun secret, storage path, contenu privé ni PII inutile en N1.

### 9.4. Tests Web / Flutter / Golden

- Compact 360×800 et 430×932, Medium 834×1112, Wide 1440×900 selon la charte et les Goldens Nous ; textScale 1.0, 1.3 et 1.6.
- Pas de troncature injustifiée du sélecteur de perspective ; navigation au clavier et lecteur d'écran à vérifier.
- Retours N2/N3 au territoire, position de scroll, sélection, Space actif et viewer d'origine.
- First load, snapshot rafraîchi, hors ligne, erreur partielle et révocation ; pas de rétention de capacités sensibles après perte d'autorité.
- Captures Android de Moi/Nous comparées sur données réelles ou fixtures équivalentes ; vérification de la hiérarchie, de la densité et du même langage.
- Tests ciblés d'abord, puis gates pertinentes ; **jamais de test affaibli pour obtenir du vert**, pas de fusion avec CI rouge.

### 9.5. Critère d'acceptation humain

En moins d'une courte lecture de la racine Nous, le viewer comprend :

> Voilà notre collectif, comment nous pouvons nous présenter, avec qui nous fonctionnons, quelle est ma place ici, quelles ressources institutionnelles nous pouvons réellement mobiliser et où approfondir sans me perdre dans une console.

Ce critère ne demande ni un compteur de clics, ni un score d'engagement ni un temps d'écran prolongé.

---

## 10. Décisions et points non clos

| Sujet | Statut | Décision / ouverture |
|---|---|---|
| Moi et Nous comme cinquièmes portes d'identité | HÉRITÉ | Sens distincts, grammaire commune |
| Passeport Makolo comme langage Profil/Space | CONSOLIDÉ | Une même famille de représentation, sujets et règles distincts |
| Passeport de l'Espace mis en valeur dans N1 | CONSOLIDÉ | Ne pas le reléguer à Settings ; owner Sharing |
| « Voir notre identité » comme destination substitutive | NON RETENU | Identité compacte + Passeport ; pas de doublon |
| Ressources de cet Espace dans Nous | CONSOLIDÉ | Territoire N1, owner-backed, distinction stricte des ressources personnelles |
| Projection technique complète des ressources Space | À VÉRIFIER | Inventaire des owners, permissions, routes et profondeur N2 |
| Parité Flutter/Web Passeport et Ressources | À VÉRIFIER | Vrai comportement natif, handoffs, caching et divulgation |
| Harmonisation visuelle avec Moi | CONSOLIDÉ | Bandeaux/territoires/aperçus/chevrons, sans copier mécaniquement |
| Mandate du viewer vs Assignment | HÉRITÉ, renforcé | Étiquettes distinctes et provenance claire |
| Critères d'acceptation Android | CONSOLIDÉ | Corriger répétition, langue technique, CTA dispersés, troncature |
| Nouveau modèle métier `SpaceResource` ou `ActorPassport` | NON RETENU par défaut | Seulement si démontré irréductible et réconcilié avec owners |
| Intégration de tous ces travaux dans la PR #522 | CADRE DE TRAVAIL | Ne pas merger avant preuve/tests ; ne pas modifier `main` |

### Formulation de référence

**Moi** est la surface personnelle qui rend reconnaissables l'identité du Profile, son Passeport Makolo, ses considérations, ses collectifs, ses ressources et ses appuis, avec des profondeurs propriétaires légitimes.

**Nous** est la surface du Space qui rend reconnaissables l'identité durable du collectif, **son Passeport Makolo**, sa relation avec le viewer, ses équipes, responsabilités, relations, **ressources institutionnelles**, gouvernance et faits de confiance, avec les outils de gestion seulement en profondeur.

**Un seul Makolo, un même langage de Passeport et de Presentation, deux acteurs et deux contrats sémantiques qui ne se confondent pas.**

---

## Annexe A — Sources précises de ce complément

- **Contrat gelé du 6 octobre** : §0, §5–13 pour Moi/Passport/Resources ; §22–47 pour Nous, viewer relation, identité, équipe, responsabilité, gouvernance, relations, Trust et local-first.
- **Contrats serveur/client du 10 octobre** : §0–2 (frontières), §3–8 (Moi), §9–16 (Nous), tableau US-01 à US-10 et BOTH-01 à BOTH-03.
- **Contrat UX Nous du 8 octobre** : N1/N2/N3, vues Compact/Medium/Wide, divulgation minimale et Golden candidates G-NOUS-01 à G-NOUS-11.
- **Captures Android fournies lors de l'échange** : observations de Youth Policy Lab (Nous) et du Profil personnel (Moi), dont le placement du Passeport, les bandeaux de section, l'équipe, les relations et le filtre tronqué.
- **Décisions explicites de l'échange** : Passeport = langage partagé pour personne et Space ; ressources du Space comme territoire à part entière ; ne rien perdre des acquis et ne pas fusionner les contrats métier.

## Annexe B — Note de non-régression documentaire

Les contrats du 6 et du 10 octobre restent intacts. Ce nouveau document est un **addendum traçable**. Lorsqu'une clause ancienne reste valable, elle n'est pas effacée ; lorsqu'une dimension manque au texte Nous initial (Passeport / Ressources institutionnelles), elle est indiquée comme **enrichissement**, sans prétendre qu'elle existait déjà dans la réponse conceptuelle ancienne ou dans la projection actuelle.