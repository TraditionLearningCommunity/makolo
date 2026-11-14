# Passeport personnel — consultation des documents émis, Web/API/Flutter

**Date :** 2 novembre 2026  
**Intégration :** PR #522, branche `fix/discover-a-continuation-context-20261014`.  
**Statut :** code et tests ciblés poussés. Ni CI, ni merge, ni validation Android annoncés.

## 1. Pourquoi ce prolongement

La séquence locale du Passeport personnel se termine aux étapes 05 (documents/versions/partages) et 06 (Web/Flutter) ; **aucune étape canonique 07 n'existe**. Le présent chantier ferme un écart d'usage restant : une personne ayant reçu un lien de vérification ou de partage pouvait consulter son document sur le Web, mais n'avait pas de lecture native Flutter de la version effectivement émise.

La lecture est une projection, pas un nouveau document métier, un cinquième type de Passeport, un nouvel Access ou un nouveau Sharing.

## 2. Propriétaires

- `PassportSnapshot` demeure la vérité de l'émission immuable.
- `PassportVerificationView` et le nouveau reader API réutilisent `_snapshot_content_allowed` et les mêmes limites des faits propriétaires.
- `resolve_passport_share` reste l'unique accès par le lien Sharing explicite : durée, état, révocation, interdiction de la variante complète et intégrité.
- L'API reader ne réémet jamais de document, ne constitue jamais un droit nouveau et ne transmet jamais le secret du lien autrement que dans le contexte de la requête.
- Flutter représente uniquement le `payload` daté déjà autorisé ; aucune restauration hors ligne, copie de document, cache persistant ou autorisation locale n'est ajoutée.

## 3. Contrats de lecture

| Mode | Route Web | Route API | Droit |
|---|---|---|---|
| Vérification | `/passport/verify/<token>/` | `/api/v1/sharing/passport/verify/<token>/` | prouve l'émission ; contenu selon le droit actuel du lecteur |
| Partage explicite | `/passport/shared/<token>/` | `/api/v1/sharing/passport/shared/<token>/` | contenu figé si et seulement si le grant Sharing est actif et intègre |

Les réponses API utilisent la projection `sharing.passport.document`, scope `reader`, avec `document_id`, `public_identifier`, `subject_kind`, `variant`, `issued_at`, `revoked`, `integrity_ok`, `can_view_content`, `explicit_share`, `expires_at` et **`payload=null` lorsque le lecteur n'est pas autorisé**.

Le lien de vérification retourne alors uniquement les métadonnées de l'émission ; un lien de partage inexistant, expiré ou révoqué renvoie 404. Les réponses sont marquées `private, no-store` et varient selon l'authentification.

## 4. Expérience Flutter

Routes natives publiques `/passport/verify/:token` et `/passport/shared/:token`, compatibles avec les App Links sur l'hôte déjà configuré. Un lecteur authentifié peut consulter sa propre vérification par l'API authentifiée. Un porteur de lien Sharing utilise le droit bearer sans exiger de compte.

Le lecteur montre identité datée, déclarations, activités, faits et attestations réellement contenus dans la version. Il distingue émission vérifiée, document révoqué, intégrité invalide et contenu non autorisé ; il rappelle que la preuve d'émission n'est pas une certification globale. Changement de token, échec réseau ou refus serveur effacent le contenu du précédent lecteur avant de présenter le nouvel état. Aucun partage implicite ni action métier n'est offert.

## 5. Tests ajoutés

- `sharing.test_passport_reader_api` : absence de lecture privée par token signé, publication indépendante de `searchable`, contrôle de lecture publique après retrait, contenu identique Web/API pour un même grant, expiration/révocation et refus de tokens invalides.
- `mobile/test/passport_document_reader_test.dart` : lecteur privé non divulgué, partage actif, nouvelles routes, invalidation d'un ancien token lorsqu'un autre prend sa place.

Les tests ciblés et le build Flutter restent à exécuter dans le dépôt local. Aucun nouveau modèle/migration ni modification de `main`.
