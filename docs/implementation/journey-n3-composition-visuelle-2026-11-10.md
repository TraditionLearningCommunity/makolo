# Makolo N3 Démarche — composition visuelle des faits

**Référence active :** `TraditionLearningCommunity/makolo`, PR #522, branche `fix/discover-a-continuation-context-20261014`.  
**Date :** 10 novembre 2026.  
**Chantier :** correction UX après retours Android des lots A/B/C, **sur la même page Journey**.

## Intention

La Démarche doit être compréhensible au premier coup d'œil par une personne sans vocabulaire technique. Une information s'exprime par la représentation la plus simple : objectif, icône, date, heure, lieu, état, action, document, accès ou échéance. **Pas une grande carte par champ.**

Les règles héritées des contrats `Makolo_UX_Demarche_Journey_Contrat_Consolide_2026-10-09.md`, Requirements/Readiness, Preparation, Forms, Jour J et En cours demeurent : Journey orchestre ; les propriétaires conservent leurs faits, permissions et confirmations.

## Ce qui a été modifié

### Identité et calendrier

- Le même en-tête propriétaire rassemble objectif réel, état Journey, éventuelle catégorie métier, date, heure, lieu et repère relatif.
- Les informations simples ne sont pas répétées en bas dans une carte « À retenir ».
- Les informations secondaires « Sur place » ne sont affichées que pour une adresse **supplémentaire**, une vraie fin prévue ou une consigne non déjà affichée.
- `Africa/Lubumbashi` n'est plus un libellé pour l'utilisateur ; il reste une donnée IANA de calendrier.
- Les intitulés Web/Flutter sont adaptatifs, et les valeurs manquantes n'engendrent pas de contenu inventé.

### Jour −N / Jour J / Jour J +N

Le compteur représente la distance entre **la date de l'Occurrence** et la date du jour dans son fuseau horaire connu :

- 245 jours avant : **Jour −245**
- 16 jours avant : **Jour −16**
- 2 jours avant : **Jour −2**
- sur la date : **Jour J**
- 2 jours après : **Jour J +2**
- 176 jours après : **Jour J +176**

Il n'y a aucune limite artificielle à N. Le calcul utilise les jours civils et non des intervalles de 24 heures. Le client Flutter utilise la base de données de fuseaux IANA embarquée (sans réseau) et actualise le repère au minuit de **l'Occurrence**, même si l'app reste ouverte. Django utilise `zoneinfo`. Une date ou un fuseau invalide ne crée pas de faux compteur.

**Le repère temporel n'est pas une capacité Jour J, un état Journey ou un état Makolo Live.** Les profondeurs Jour J/Live conservent leurs admissions et leurs faits réels ; une date passée ne termine pas une Journey.

### Composition des autres données

- **Actions et attente** : prochaine action autorisée au premier plan ; attente, blocage et choix réels distincts ; aucune action fictive. Une intervention dont le seul texte est identique à l'objectif est écartée de la présentation lorsqu'elle n'a pas de lien d'action, sans modifier Readiness.
- **JourneySteps** : chemin compact dans une seule surface, statuts et dépendances du propriétaire, éléments passés repliés ; ni pourcentage calculé ni étapes synthétiques.
- **Readiness** : bloque, de votre côté, en attente, en ordre dans une composition compacte. Les éléments acquis sont consultables et ne dominent pas.
- **Documents / Preparation** : type de ressource reconnu par son MIME et son kind (PDF, image, vidéo, lien, instruction, fichier). Les lignes d'aperçu ne simulent plus des ouvertures individuelles ; le bouton explicite mène à la profondeur Preparation existante. Données lues dans la projection locale du Profil.
- **Formulaires** : titre réel de FormVersion, icône, état, caractère obligatoire, échéance et lien propriétaire.
- **Requirements** : état et obligation affichés avec icône, clic seulement lorsqu'un handoff autorisé existe.
- **Payment / Commerce** : montant/devise/état propriétaire, présentation groupée si plusieurs obligations ; aucune tentative de transaction n'est transformée en paiement confirmé.
- **Access** : entrée reconnaissable ; le QR et les credentials restent dans leur profondeur propriétaire.
- **Activity / Occurrence** : liens nommés « À propos de l'activité » et « Date ou séance », affichés seulement s'ils ouvrent une profondeur réelle et sans répéter le titre déjà en haut.
- **Conversation** : handoff contextuel existant conservé, sans nouveau chat.

### Local-first, sécurité et variantes

- Les widgets Flutter sont composés par les projections **ProfileStore** du Profil courant, sans attente réseau au rendu.
- L'indicateur réseau global du shell suffit ; pas de mode « hors ligne », de jargon local/serveur ou d'explication technique ajoutée à N3.
- La révocation explicite d'un propriétaire continue à primer sur les anciens instantanés locaux.
- Aucun modèle ou migration ajouté à Journey, Activity, Occurrence, Access, Payment, Preparation ou Requirements.
- La page sait fonctionner sans Occurrence, sans date, sans étape, sans ressource, sans paiement, en attente ou terminée, sans créer de cartes artificielles.

## Tests du changement

- `mobile/test/journey_time_presentation_test.dart` : J−245, J−16, J−2, Jour J, J+2, J+176 ; changement de fuseau ; date erronée ; lieu non répété.
- `mobile/test/journey_n3_composition_test.dart` : page N3 composée depuis le ProfileStore sans client réseau, date/heure/ville/compteur, ressources typées, absence de doubles informations à largeur Android.
- `core/test_journey_time_presentation.py` : mêmes bornes temporelles, fuseaux horaires, lieu dédoublonné.
- Les tests préexistants des lots A/B/C gardent leurs exigences sur permissions, actions propriétaires, documents, paiements et états terminaux.

**Attention :** commit et présence sur #522 ne sont pas une preuve d'exécution. Avant toute fusion : `flutter analyze`, tests Flutter ciblés, tests Django ciblés, vérification Android réelle, accessibilité et CI. Ne pas affaiblir les tests pour obtenir du vert.

## Hors de la refonte

Pas de refonte de Découvrir, Notifications, Conversations, En cours, Moi/Mes démarches ; aucun nouveau N3. Les sources de vérité canoniques restent inchangées. Une capacité non projetée par le propriétaire (par exemple une position en liste d'attente inconnue) **n'est pas simulée** pour enrichir artificiellement l'interface.
