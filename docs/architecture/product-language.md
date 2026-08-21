# Product Language — boundary note

**Task 14 — Product Language : la présentation utilisateur est contextualisée par verticale et workflow, sans modifier les bounded contexts canoniques.**

La référence détaillée de vocabulaire est [`docs/product/product-language.md`](../product/product-language.md). Le code de résolution partagé est `core/product_language.py`.

`Activity`, `Occurrence`, `Journey`, `Offer`, `CommerceOrder`, `Payment` et `Access` restent les propriétaires métier canoniques. Events et Transport restent des verticales composées ; Product Language ne décide ni de l’éligibilité, ni de la capacité, ni du paiement, ni de l’autorisation, ni de l’émission d’un droit.
