# Runtime Contract — personal.me → Moi

## Pipeline
`PersonalRepository.watchMe() → StoredProjection personal.me → MeSelector → MePresentation/MeSelection → MeView`

## Sections supportées
- `identity`
- `passport`
- `considerations`
- `collectives`
- `resources`
- `support` lorsque réellement disponible

## Distinctions obligatoires
- Profile ≠ Account/Settings
- Membership ≠ Permission ≠ Mandate
- PersonalAsset ≠ JourneyArtifact ≠ Proof
- Credential Trust ≠ AccessCredential
- posséder une ressource ≠ satisfaire un Requirement

## États
Chaque territoire peut être content, local-empty ou local-error indépendamment. Freshness/reachability sont des axes séparés.

## Navigation
La lane peut ouvrir une profondeur N2 locale. Elle n'invente aucune route owner. Toute future action owner devra venir d'une capability/route existante et autorisée.
