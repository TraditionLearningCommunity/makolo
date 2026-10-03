# Quickstart validation — Mobile Mature Moi

1. Construire une `StoredProjection(kind: personal.me)` avec la vraie shape backend.
2. Vérifier Identity + Passport + Considerations + Collectives + Resources.
3. Vérifier Support absent lorsque tous ses éléments ont `available=false`, puis présent lorsqu'un élément est disponible.
4. Vérifier sparse: Moi reste visible et chaque territoire porte son empty local.
5. Corrompre une famille imbriquée de Resources et vérifier que seul Resources passe en erreur.
6. Vérifier freshness depuis les métadonnées StoredProjection, sans TTL local.
7. Vérifier `content + offline` via `SyncStatusScope` et `MeScreen`.
8. Vérifier `content + syncing`: contenu conservé + feedback discret.
9. Vérifier `content + source error`: Moi reste visible.
10. Tester 800 dp: vertical.
11. Tester 840 dp: deux territoires possibles.
12. Tester 900 dp: maximum deux territoires.
13. Tester sparse à 900: largeur seule ne force pas deux territoires.
14. Ouvrir une Resource: N2, contexte humain, Back vers Moi.
15. Tester textScale 1.0, 1.3 et 1.6 sur 430×932.
16. Exécuter format, analyze et tests Mobile impactés.
17. Vérifier Android build et CI #451.
18. Réconcilier le `main` courant puis rerun les gates.
19. Marquer T015 seulement après tous les gates verts.
