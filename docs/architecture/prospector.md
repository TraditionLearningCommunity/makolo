# Makolo — Acteur 1 : Prospecteur

> **Statut du train : PX1 — Frontier durable.**
>
> Base initiale du train : main@9c60119f4eab8628ff33b230562f85ed8500c632.
> PX1 est empilé sur PX0@b5bc9e9cf2d0ea887857515661db924844e54476.
> Le code, les migrations, les tests et le main courant restent prioritaires.

## 1. Mission

Le **Prospecteur** cherche où existent potentiellement des **fragments utiles au
réseau d'action Makolo**. Il ne cherche pas une page qui contiendrait une
« opportunité complète » et il ne décide pas qu'un fragment est une vérité
métier.

Une condition, une procédure, un centre, une session, un financement, une
deadline, une ressource ou un moyen d'accès peuvent être aussi importants à
prospecter qu'une page d'emploi ou de formation.

~~~text
Prospecteur : où Makolo devrait-il regarder ?
Observateur : que dit réellement cette ressource ?
Interpréteur: quels faits candidats contient l'observation ?
Résolveur   : de quelles réalités ces faits parlent-ils ?
~~~

Le Prospecteur et la surface produit Discover restent distincts :

~~~text
Prospecteur : Makolo prospecte ce qu'il ne connaît pas encore.
Discover    : l'utilisateur découvre ce que Makolo connaît déjà.
~~~

## 2. Frontière de dépendances

Le core importable prospector reste Python pur :

~~~text
prospector core -X-> Django
prospector core -X-> modèles métier Makolo
prospector core -X-> réseau
prospector core -X-> Crawlee
~~~

PX1 ajoute un adaptateur de persistance :

~~~text
prospector contracts / ports
          ▲
          │
DjangoFrontierStore
          │
          ▼
prospector.django_app
          │
          ▼
PostgreSQL
~~~

Django est utilisé ici pour le cycle de migrations et l'ORM déjà présents dans
Makolo. Il n'est pas le moteur du Prospecteur et ne remonte pas dans le core.

## 3. Identité technique

PX1 supporte explicitement kind=web_url.

La canonicalisation v1 :

- accepte uniquement HTTP(S) absolu ;
- met scheme et hostname en minuscules ;
- canonicalise les noms IDNA et les adresses IP ;
- retire le port par défaut ;
- transforme un path vide en / ;
- retire le fragment ;
- **préserve la query telle quelle** ;
- refuse les credentials embarqués dans l'URL.

Aucun paramètre utm_*, pagination ou query « inutile » n'est supprimé par
heuristique. Une telle suppression peut changer l'identité d'une ressource et
appartiendra à une politique explicitement testée.

target_key est versionné et borné :

~~~text
web_url:v1:<sha256(kind + NUL + canonical_locator)>
~~~

C'est l'identité **de cible technique**, jamais celle d'une Activity, d'une
Occurrence, d'une organisation ou d'une autre réalité métier.

## 4. Frontier durable

PX1 persiste deux projections opérationnelles.

### ProspectorFrontierEntry

Une ligne par target_key canonique :

- locator et kind canoniques ;
- état Frontier ;
- priorité opérationnelle ;
- disponibilité ;
- première / dernière découverte ;
- compteur de redécouvertes ;
- contexte de politique courant ;
- hints d'observation courants ;
- lease de claim ;
- date de complétion.

### ProspectorFrontierEvidence

Provenance compacte attachée à une cible :

- méthode de découverte ;
- cible source éventuelle ;
- observation source éventuelle ;
- provider éventuel ;
- attributs ;
- contexte/hints au moment de cette provenance ;
- première / dernière apparition ;
- compteur.

Une redécouverte identique incrémente le compteur au lieu d'ajouter une suite
infinie de lignes. Des provenances réellement distinctes sont conservées.

## 5. Cycle de vie PX1

~~~text
admit
  ↓
READY ──claim──> CLAIMED ──complete──> COMPLETED
  ▲                 │
  └────defer────────┘

COMPLETED ──requeue explicite──> READY
~~~

Une simple redécouverte d'une cible COMPLETED **ne la réactive pas**.

Le statut SUPPRESSED est réservé par le contrat de stockage ; ses politiques
effectives seront définies avec la sécurité/admissibilité en PX4.

## 6. Leases et concurrence

Un claim produit un FrontierClaim contenant :

- la cible ;
- le worker ;
- un token opaque ;
- l'expiration de lease.

Le token doit encore être le token durable courant pour terminer ou différer le
travail. Un ancien worker ne peut donc pas clôturer une cible récupérée par un
autre.

Sur PostgreSQL, les claims utilisent des verrous de ligne et SKIP LOCKED
lorsqu'il est disponible. Une lease expirée redevient réclamable sans opération
de réparation séparée.

SQLite reste compatible pour les tests fonctionnels, mais les garanties de
concurrence sont validées explicitement sur PostgreSQL.

## 7. Idempotence

L'admission est idempotente au niveau de l'identité :

~~~text
100 admissions concurrentes de la même URL canonique
→ 1 FrontierEntry
~~~

Les admissions restent comptées et les provenances distinctes restent
auditables.

Une collision où le même target_key pointerait vers un couple kind/locator
différent est refusée comme conflit, même si SHA-256 rend ce cas extrêmement
improbable.

## 8. Ce que PX1 ne fait pas

PX1 ne :

- contacte aucun site ;
- n'intègre pas Crawlee ;
- n'interroge pas Common Crawl ;
- n'entretient aucune liste manuelle de sites ;
- n'interprète aucun contenu ;
- ne crée aucune vérité métier ;
- ne décide pas qu'un fragment est un Requirement, Proof, Access ou Activity ;
- n'introduit ni Elasticsearch, ni Redis, ni Kafka, ni LLM.

## 9. Train après la correction « réseau de faits »

~~~text
PX0  fondation Python pure
 ↓
PX1  Frontier PostgreSQL durable
 ↓
PX2  sources de prospection autonomes / index externes
 ↓
PX3  contrat Prospecteur ↔ Observateur
 ↓
PX4  sécurité réseau / admissibilité / budgets
 ↓
PX5  expansion autonome : graphe Web, sitemaps, feeds, anti-traps
 ↓
PX6  runtime continu + adapter Crawlee / recovery / backpressure
 ↓
PX7  feedback aval + exploration/exploitation
 ↓
PX8  pilote Internet réel
 ↓
PX9  hardening / échelle
~~~

## 10. Validation PX1

Gates généraux :

~~~text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
~~~

Tests ciblés indépendants de Django :

~~~text
python -m unittest discover prospector/tests -v
~~~

Tests Frontier ORM :

~~~text
python manage.py test prospector.django_app.tests
~~~

Un workflow PostgreSQL dédié exécute migrations et tests de concurrence avec
plusieurs threads afin de vérifier les garanties que SQLite ne peut pas fournir.
