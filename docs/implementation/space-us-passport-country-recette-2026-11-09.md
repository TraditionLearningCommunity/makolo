# Recette Nous — Passeport unique et pays dans le formulaire Space

**PR #522 · 2026-11-09**

- **Nous N1 Flutter** : suppression de l'en-tête secondaire « Passeport Makolo » précédant la carte principale, désormais seule carte « Notre Passeport ». Handoff owner et règles d'affichage inchangés.
- **Web Nous** : la même carte d'entrée porte le titre « Notre Passeport » sans eyebrow redondant.
- **Identité de l'Espace** : le pays n'est plus un `TextFormField` libre. Le formulaire réutilise `mobile/lib/features/me/me_country_choices.dart` (source de la liste utilisée par le profil personnel), offre la recherche par nom/code et exige une option reconnue.
- L'écran affiche le **nom français** (par exemple « Congo-Kinshasa ») ; le contrat backend reste le code ISO déjà utilisé (`CD`). La ville reste un champ texte, comme dans Moi.
- Les données existantes ne sont pas migrées ni réécrites. L'Espace est toujours mis à jour uniquement par son API propriétaire, après vérification des permissions.
- Les tests visés vérifient le Passeport unique, la représentation lisible du pays, la réutilisation de la liste et le contrat Web. Les tests exécutables requièrent le runner Flutter/Django ; aucun résultat CI vert n'est présumé.
