# Abonnement & facturation — corrections et limites de fermeture (02/11/2026)

Statut : **implémentation sur la PR #522, non fusionnée**. Ce document trace les 31 constats du retour mobile (SUB-01 à SUB-31) en distinguant correctifs livrés, tests ciblés ajoutés et contrats encore ouverts. Le statut de CI et la validation Android restent à constater sur le HEAD de la PR au moment du merge.

## Parcours cible

Pour une PlanVersion publique en libre-service et éligible : consultation → aperçu des capacités, limites, conditions et BillingTerms **pinnés** → confirmation d'une intention idempotente → ouverture directe d'une PaymentObligation liée si paiement requis. Si aucune obligation et aucune condition bloquante ne subsiste, la Transition libre-service se complète depuis le service propriétaire. Si l'obligation est à régler, la formule précédente reste active ; le client peut reprendre son paiement depuis l'Abonnement. Après confirmation de l'obligation par Payments et Readiness « ready », le service Subscription complète la Transition et publie le nouvel Item ; le client réinterroge la projection. Un retour client ou une capture de succès ne prouve jamais le paiement.

Ni un plan sans BillingTerms ni un libellé « Tarif non communiqué » ne doivent être présentés comme un prix de zéro. La base technique existante peut ne pas porter d'obligation : **aucun tarif ou prorata ne doit être inventé**.

## Registre de suivi (constats issus des captures)

| Références | État de cette PR | Détail |
|---|---|---|
| SUB-01, 10, 15, 21 | **Politique ouverte** | La présence des anciennes obligations est historique ; période de couverture réelle, prorata, crédits, renouvellement et downgrade ne sont pas encore contractualisés dans les propriétaires financiers. Pas de conversion arbitraire 7 → 18 USD. |
| SUB-02 | **À valider en environnement** | Le statut « Réglée » doit provenir de Payments ; les offres et règlements DEMO/sandbox ne certifient pas un paiement réel. |
| SUB-03, 23, 24, 26 | **Corrigé au niveau orchestration** | Auto-finalisation de la Transition libre-service prête et après règlement confirmé ; suppression de l'approbation manuelle artificielle. Les véritables Requirements d'approbation restent bloquants. |
| SUB-04 | **Couvert par existant et tests ajoutés** | Clés d'idempotence et verrouillages du service Subscription conservés ; Payment conserve sa clé en cas d'issue réseau incertaine, nouvelle clé après échec attesté. |
| SUB-05, 13 | **Couvert par les domaines existants, à retester** | Entitlements selon sujet Profil/Espace ; Membership ≠ Mandate ; filtre Finance sur les détails et liens de paiement de l'Espace. Aucune élévation d'autorité. |
| SUB-06, 18 | **Corrigé en projection** | Nouveaux libellés de facture commerciaux ; historique des anciennes obligations réaffiché selon PlanVersion pinnée si le lien existe. Terminologie UX de Transition améliorée. |
| SUB-07, 31 | **Amélioré, pas clos** | Aperçu des gains/pertes et quotas existants, explication explicite si aucune différence technique n'est déclarée. Des DEMO Plus/Max identiques en capacités requièrent de vrais produits différenciés, pas des bénéfices inventés. |
| SUB-08, 25 | **Corrigé pour les obligations visibles** | `next_action` et `payment_obligation_id` de projection privée ; accès direct et reprise côté Flutter, redirection vers paiement côté Web. |
| SUB-09 | **Amélioré** | History expose l'ancienne et la nouvelle formule lorsque source disponible ; date de conclusion si disponible. |
| SUB-11 | **Sécurisé, cycle complet ouvert** | Annulation refusée si obligation financière active, pour éviter un payable orphelin ; résolution financière/avoir/remboursement à définir chez Payments avant autoriser une annulation de bout en bout. |
| SUB-12 | **Raccordé au parcours** | Ajout/retrait d'option emprunte les mêmes services de Transition, requiert les droits du sujet, sans inventer une nouvelle API. |
| SUB-14 | **À vérifier sur Android** | Relecture après retour du paiement, acteurs séparés, messages réseau prudents ; cold start et restauration à tester. |
| SUB-16, 17, 27, 28 | **Corrigé pour les écrans centraux** | TopBar conserve titre et retour ; suppression des en-têtes secondaires redondants, suppression du doublon « déjà inclus ». Le lien intentionnel de retour vers l'équipe constitue une continuation distincte. |
| SUB-19, 20, 29, 30 | **Amélioré** | Montant financier prioritaire, statuts et échéances en dessous, liste d'actions groupée, espacement vertical réduit, CTA paiement contextualisé. Contrôle de rendu sur petits écrans encore nécessaire. |
| SUB-22 | **Non certifié** | Contrôle accessibilité tactile, contrastes, TalkBack et texte agrandi à exécuter sur appareil. |

## Frontières

- Subscription décide uniquement de Transition, éligibilité, Readiness et Items ; Payments décide de Payment, PaymentObligation, montants et confirmation fiable ; les permissions/Mandates restent dans Authorization.
- Les deux obligations de 7 et 18 USD vues en démo ne démontrent ni surfacturation ni prorata. Sans période de couverture ni politique commerciale définie, les garder comme faits financiers historiques ; **ne pas supprimer ni backfiller**.
- Le paiement mobile existant expose seulement le provider sandbox disponible dans sa configuration, pas une nouvelle intégration bancaire réelle. Aucun écran Flutter ne peut valider une transaction.
- Un écran Space sans FINANCE_VIEW n'obtient ni l'ID de l'obligation privée ni une permission de payer via sa seule autorité Subscription.

## Vérifications avant merge

Django :
```bash
python manage.py test subscriptions.test_native_payment_continuation subscriptions.test_web_checkout_continuation subscriptions.test_f2_billing subscriptions.test_s4_payment_bridge subscriptions.test_s4_transitions subscriptions.test_space_native_api subscriptions.test_s6_product_ux subscriptions.test_lot3_enforcement
python manage.py makemigrations --check --dry-run
```
Flutter :
```bash
cd mobile
dart format --output=none --set-exit-if-changed lib/features/settings/billing_screen.dart lib/features/settings/subscription_actions_panel.dart lib/features/payments/payment_obligation_screen.dart test/billing_screen_test.dart test/subscription_personal_flow_test.dart test/subscription_actions_panel_test.dart test/space_subscription_test.dart test/payment_obligation_retry_test.dart
flutter analyze
flutter test test/subscription_actions_panel_test.dart test/subscription_personal_flow_test.dart test/billing_screen_test.dart test/space_subscription_test.dart test/payment_obligation_retry_test.dart
```

**Non exécutés dans cette session** : le travail a été poussé via le connecteur GitHub ; aucune validation locale Django/PostgreSQL/Flutter ou Android n'est attestée. Ne pas fusionner avant vérification des gates concernées.
