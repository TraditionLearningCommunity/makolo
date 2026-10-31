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
  activé uniquement si le runtime possède une configuration explicite.
- Réponses malformées / requêtes réseau refusées / annulations ont des contrats distincts.
- Une saisie non vide peut déclencher une suggestion ; le composant partagé
  utilise un debounce de 350 ms, limite à cinq résultats, annule les appels
  obsolètes et ignore les réponses tardives.

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

1. Vérifier la licence et le quota effectifs avant une utilisation commerciale.
2. Utiliser les valeurs explicites `MAKOLO_GEOCODING_ENABLED` et
   `MAKOLO_GEOCODING_API_KEY`, indépendantes de `MAKOLO_MAP_STYLE`.
3. Injecter `GeoSearchGateway` dans le composant `GeoAutocompleteField`,
   sans lier le provider aux vues métier.
4. Le widget gère 350 ms de debounce, suppression des résultats obsolètes,
   annulation par `CancelToken`, résultats bornés, erreurs et saisie libre.
5. Ne solliciter le GPS que pour une action utilisateur distincte.
6. Limiter les caches aux données temporaires autorisées par la licence.
7. Tester avant l'activation la recherche au Congo/RDC et ailleurs,
   les lieux homonymes, les accents, la connectivité lente et les quotas.

Le lot 1 ne modifie ni backend, ni migrations, ni écran Discover,
ni tarifs, ni contrat métier Geography.

## Configuration locale (les clés ne sont pas dans le code)

Pour le développement, copier `mobile/config/dev.json` vers
`mobile/config/dev.local.json` (ignoré par Git) puis y ajouter :

```json
"MAKOLO_GEOCODING_ENABLED": "true",
"MAKOLO_GEOCODING_API_KEY": "VOTRE_CLE_CLIENTE_GEOCODING"
```

Conserver les autres paramètres du JSON. Démarrer depuis `mobile/` :

```bash
flutter run --flavor dev --dart-define-from-file=config/dev.local.json
```

Ces clés restent remplaçables par environnement. Le plan MapTiler Free
ou payant ne change pas le code Flutter. Une clé incluse dans l'APK est
visible par le client : la restreindre et maîtriser les quotas ; ne jamais
utiliser une clé privée serveur. Les clés diffusées dans un chat ou des logs
sont à régénérer avant une diffusion au public.

La suggestion externe ne modifie jamais `Geography.Place`. Dans le filtre
Discovery actuel, la ville sélectionnée fournit une valeur textuelle compatible
avec le paramètre `place` côté serveur ; les coordonnées externes restent
attachées à la suggestion UX, sans forcer une recherche nearby. Le filtre
`date` exact existant est alimenté par le sélecteur calendrier Flutter.
