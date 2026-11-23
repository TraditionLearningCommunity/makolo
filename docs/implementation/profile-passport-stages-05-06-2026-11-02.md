# Passeport personnel Makolo — étapes 05 et 06

**Date :** 2 novembre 2026  
**Branche d’intégration :** `fix/discover-a-continuation-context-20261014` / PR #522  
**Statut :** implémentation poussée dans la PR ; validation des tests, CI, Android et revue avant fusion encore requise.

## 1. Propriétaires et frontières

- Accounts détient l’identité personnelle et la politique d’audience.
- Topics détient les intérêts et les déclarations « Ouvert à ».
- Sharing détient les versions émises (`PassportSnapshot`) et les liens explicites (`ShareEnvelope` / `PassportShareSubject`).
- Les domaines Activity / Trust restent propriétaires de leurs droits et retraits ; un Passeport émis n’accorde aucun droit supplémentaire.
- Web, API personnelle et Flutter représentent ces vérités. Aucune nouvelle table, migration, Permission, Mandate ou variante de Passeport n’est introduite.

## 2. Étape 05 — Documents, versions et partage

Les quatre variantes préexistantes — Public, Complet, Thématique, Personnalisé — conservent leurs règles de sélection. Les éditions PDF continuent à matérialiser un snapshot immuable, avec identifiant, empreinte et QR/lien de vérification. Un export PDF **ou HTML imprimable** qui échoue au rendu ne peut plus laisser une version « émise » orpheline : émission et rendu sont dans une même transaction.

Le propriétaire peut désormais **révoquer une version datée** depuis l’historique Web ou depuis l’application native. La version et son empreinte restent consultables par son titulaire, mais sa lecture publique et ses liens actifs sont retirés. La révocation utilise le service Sharing canonique pour chaque lien encore actif ; elle est idempotente.

L’API propriétaire `/api/v1/me/passport/history/` fournit maintenant les identifiants et dates d’expiration des seuls liens actifs de chaque version (sans exposer leur jeton). Les POST owner-scoped ajoutés sont :

- `/api/v1/me/passport/history/<snapshot_id>/revoke/` — révoquer l’émission et les liens actifs ;
- `/api/v1/me/passport/shares/<share_id>/revoke/` — révoquer un lien précis, sans révoquer la version.

L’historique Web offre la même commande de révocation d’émission. Les vues owner/Space revalident les droits à la requête. Le lien de vérification **n’est pas** un lien de partage et ne donne pas accès à un contenu privé. Un PDF déjà téléchargé par un tiers ne peut pas être rappelé.

## 3. Étape 06 — Web et Flutter

L’expérience native conserve le Passeport courant, le PDF, l’historique des versions datées et les variantes. Les actions Flutter permettent désormais de :

- choisir une expiration de partage de 1, 7 ou 30 jours ;
- voir les liens actifs associés à une version ;
- révoquer individuellement un lien ou la version entière, après confirmation ;
- recharger l’historique pour retrouver le statut serveur ;
- réessayer une lecture échouée sans écran vide et sans perdre les contrôles de variantes.

Le `FutureBuilder` est attaché à la clé déterministe de sélection ; une réponse de l’ancienne sélection ne doit plus réapparaître dans une autre sélection. L’export natif supprime son PDF de travail du cache privé après sauvegarde **ou annulation**. La destination choisie par la personne reste sous son contrôle.

## 4. Validation ciblée

Tests ajoutés/étendus :

- `sharing.test_passport_issuance_sharing` : révocation d’une version et de tous ses partages, archive immuable, révocation d’un seul lien, exposition owner-scoped de la liste active, refus IDOR et rollback PDF/HTML ;
- `mobile/test/me_passport_history_test.dart` : consultation datée, révocations natives, erreur réseau, reprise et maintien des variantes, absence de contenu privé ancien lors d’un changement de variante.

Commandes à lancer dans l’environnement de développement réel :

```bash
python manage.py test sharing.test_passport_issuance_sharing sharing.test_passport_stage4_withdrawal accounts.test_passport_visibility_integration topics.test_passport_initial_disclosure
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
cd mobile
dart format lib/features/me/me_passport_screen.dart test/me_passport_history_test.dart
flutter analyze
flutter test test/me_passport_history_test.dart
```

La validation Android réelle reste nécessaire : première ouverture, changement de Profil, changement de variante, refus serveur, PDF enregistré/annulé, partage et révocation puis ouverture du lien par un tiers. Les gates globales de la PR restent à examiner avant fusion.

## 5. Principes préservés

- Émission ≠ publication ≠ Sharing.
- Révocation de version ≠ suppression d’historique.
- Révocation d’un lien ≠ révocation des autres liens.
- Un viewer collectif n’obtient ni Mandate ni Permission.
- Une projection hors-ligne ne peut créer ni révoquer localement des droits serveur.
- Toute action sensible est confirmée en ligne par le propriétaire canonique.
