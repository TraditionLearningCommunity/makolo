# Makolo Mobile — recherche géographique (fondation)

## Problème utilisateur

Une personne doit pouvoir retrouver rapidement une ville, une adresse ou un lieu réel,
y compris lorsque Makolo n'a encore aucune Activity, Occurrence ou Space dans ce lieu.

La suggestion UX issue d'un fournisseur n'est **pas** un `Place` ou une `Zone`
canonique. La sélection ne crée aucune ligne métier. La carte (MapLibre)
n'est pas un fournisseur de géocodage.

## État livré : fondation seulement

- `GeoSearchGateway` fournit `suggest(query, language, limit, cancelToken)`.
- `GeoSuggestion` conserve l'identifiant externe, le libellé, les coordonnées,
  le type et la provenance. Aucune donnée de Profile ni position GPS implicite.
- `MapTilerGeoSearchGateway` est un adaptateur candidat, injectable,
  **non activé** dans le runtime ou dans une feature.
- Réponses malformées / requêtes réseau refusées / annulations ont des contrats distincts.
- Minimum deux caractères, maximum dix résultats ; le futur widget impose
  aussi un debounce et invalide ses réponses obsolètes.

Aucun compte, clé, quota, prix spécifique au compte ni droit commercial
de géocodage Makolo n'a été vérifié. L'existence d'un style MapTiler
DEV ne prouve pas que la clé autorise l'API Geocoding.
Ne pas extraire automatiquement de clé du style cartographique.
L'activation future exige une configuration client approuvée,
avec clés restreintes et plafond de consommation connu.

## Choix du fournisseur à valider

**Candidat : MapTiler Cloud Geocoding.** Il est compatible avec la
cartographie existante, expose les requêtes autocomplete, limites, types,
langues et recherche mondiale. MapTiler Cloud facture suivant le plan,
les requêtes/sessions et leurs quotas ; le plan Free est réservé aux
usages non commerciaux et au développement autorisé.
Vérifier directement le compte, le plan, les plafonds et les domaines ou
packages mobiles autorisés avant activation. Le modèle de facturation par
session décrit pour les SDK ne doit pas être supposé disponible pour
le simple adaptateur HTTP Flutter.

**Écarté : Nominatim public d'OpenStreetMap** pour le typeahead :
sa politique interdit expressément l'autocomplétion client.
Un service OSM tiers autorisé serait un fournisseur distinct à évaluer.

**Alternative : GeoNames**, avec attribution CC-BY, limites publiées,
qualité et couverture des adresses à éprouver ; pas retenu comme provider
principal sans tests qualitatifs sur les régions desservies.

Références :
- https://docs.maptiler.com/cloud/api/geocoding/
- https://www.maptiler.com/terms/cloud/
- https://docs.maptiler.com/guides/account/sessions-vs-requests/
- https://operations.osmfoundation.org/policies/nominatim/
- https://www.geonames.org/export/

## Conditions d'activation et d'intégration

1. Faire approuver le produit de géocodage et le quota effectif par le propriétaire.
2. Étendre la configuration runtime de manière explicite, sans utiliser le
   token de style et sans intégrer de secret serveur dans l'APK.
3. Fournir `GeoSearchGateway` par injection dans le composant partagé du
   **lot 2** ; ne pas le coupler à `DiscoveryQuery`.
4. Le widget du lot 2 gère 250–400 ms de debounce, suppression des résultats
   obsolètes, annulation par `CancelToken`, limites de requêtes, états de réseau,
   sélection accessible et retour à la saisie si le provider est indisponible.
5. Ne solliciter le GPS que pour une action utilisateur distincte.
6. Limiter les caches aux données temporaires autorisées par la licence.
7. Tester avant l'activation la recherche au Congo/RDC et ailleurs,
   les lieux homonymes, les accents, la connectivité lente et les quotas.

Le lot 1 ne modifie ni backend, ni migrations, ni écran Discover,
ni tarifs, ni contrat métier Geography.
