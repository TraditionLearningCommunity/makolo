# Runtime Contract — personal.me → Moi

## Pipeline contenu

```text
PersonalRepository.watchMe()
→ StoredProjection personal.me
→ MeSelector
→ MePresentation / MeSelection
→ MeView
```

## Pipeline état de source

```text
PersonalRepository.watchMeSource()
→ watchOwnerSourceState(...)
→ SyncSources.personal.me

SyncStatusScope
→ offline / syncing lifecycle
```

Le contenu et l'état de transport restent deux axes séparés.

## Sections supportées
- `identity`
- `passport`
- `considerations`
- `collectives`
- `resources`
- `support` uniquement lorsqu'un élément est réellement disponible

## Distinctions obligatoires
- Profile ≠ Account/Settings
- Membership ≠ Permission ≠ Mandate
- PersonalAsset ≠ JourneyArtifact ≠ Proof
- Credential Trust ≠ AccessCredential
- posséder une ressource ≠ satisfaire un Requirement

## États
- root snapshot absent: structure SECTION-FIRST de première disponibilité;
- empty: local au territoire;
- malformed: error local au territoire;
- offline: snapshot conservé + cue;
- syncing: snapshot conservé + feedback discret;
- source error avec snapshot: recoverable, contenu conservé;
- source invalidated: freshness demande revalidation;
- Support vide: section absente.

## Responsive
- < 840: vertical;
- >= 840: maximum 2 territoires, uniquement lorsque le contenu le justifie;
- N2: même vérité, géométrie single-pane ou split selon contraintes partagées.

## Navigation
La lane ouvre une profondeur N2 locale de présentation. Elle n'invente aucune route, mutation, capability ou autorité owner. Une profondeur métier future devra utiliser un contrat propriétaire réel.
