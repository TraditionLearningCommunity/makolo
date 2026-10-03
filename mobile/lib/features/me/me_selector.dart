import '../../data/local/profile_store.dart';
import '../../design/surface_states.dart';
import '../../navigation/destination.dart';
import '../../presentation/contracts/me_presentation.dart';
import '../../sync/freshness.dart';

class MeItemPresentation {
  const MeItemPresentation({
    required this.destination,
    required this.title,
    this.subtitle,
    this.metadata = const [],
  });

  final StructuredDestination destination;
  final String title;
  final String? subtitle;
  final List<String> metadata;
}

class MeTerritorySelection {
  const MeTerritorySelection({
    required this.presentation,
    required this.items,
  });

  final MeTerritoryPresentation presentation;
  final List<MeItemPresentation> items;
}

class MeSelection {
  const MeSelection({
    required this.presentation,
    required this.territories,
    required this.state,
    required this.identityState,
    this.identitySubtitle,
    this.identityDetail,
  });

  final MePresentation presentation;
  final List<MeTerritorySelection> territories;
  final MakoloSurfacePresentation state;
  final MakoloSurfacePresentation identityState;
  final String? identitySubtitle;
  final String? identityDetail;
}

class MeSelector {
  const MeSelector();

  static const FreshnessPolicy _freshnessPolicy = FreshnessPolicy(
    id: 'personal.me',
  );

  MeSelection select({
    required StoredProjection? projection,
    required DateTime now,
    MakoloReachabilityCue reachability = MakoloReachabilityCue.unknown,
    MakoloFailureCue failure = MakoloFailureCue.none,
    bool refreshing = false,
  }) {
    if (projection == null) {
      const state = MakoloSurfacePresentation(
        availability: MakoloAvailabilityCue.initial,
      );
      return const MeSelection(
        presentation: MePresentation(identityLabel: 'Moi', territories: []),
        territories: [],
        state: state,
        identityState: state,
      );
    }

    final freshness = _freshnessCue(
      _freshnessPolicy.evaluate(projection, now: now),
    );
    final commonState = MakoloSurfacePresentation(
      availability: MakoloAvailabilityCue.content,
      freshness: freshness,
      reachability: reachability,
      failure: failure,
      refreshing: refreshing,
    );

    final identityRaw = _map(projection.payload['identity']);
    final identityLabel = _string(identityRaw?['display_name']) ?? 'Moi';
    final identityMalformed =
        projection.payload.containsKey('identity') && identityRaw == null;
    final identityState = MakoloSurfacePresentation(
      availability: identityRaw == null
          ? MakoloAvailabilityCue.empty
          : MakoloAvailabilityCue.content,
      freshness: freshness,
      reachability: reachability,
      failure: identityMalformed
          ? MakoloFailureCue.blocking
          : MakoloFailureCue.none,
    );

    final territories = <MeTerritorySelection>[
      _passport(projection.payload['passport'], freshness, reachability),
      _considerations(
        projection.payload['considerations'],
        freshness,
        reachability,
      ),
      _collectives(projection.payload['collectives'], freshness, reachability),
      _resources(projection.payload['resources'], freshness, reachability),
    ];

    final support = _support(
      projection.payload['support'],
      freshness,
      reachability,
    );
    if (support != null) territories.add(support);

    final presentations = territories
        .map((territory) => territory.presentation)
        .toList(growable: false);

    return MeSelection(
      presentation: MePresentation(
        identityLabel: identityLabel,
        territories: List.unmodifiable(presentations),
      ),
      territories: List.unmodifiable(territories),
      state: commonState,
      identityState: identityState,
      identitySubtitle: _identitySubtitle(identityRaw),
      identityDetail: _string(identityRaw?['bio']),
    );
  }

  MeTerritorySelection _passport(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    final malformed = raw != null && section == null;
    final available = section?['available'] == true;
    return MeTerritorySelection(
      presentation: MeTerritoryPresentation(
        key: 'passport',
        label: 'Passeport Makolo',
        summary: 'Ce qui peut vous représenter selon le contexte.',
        state: _sectionState(
          hasContent: available,
          malformed: malformed,
          freshness: freshness,
          reachability: reachability,
        ),
      ),
      items: const [],
    );
  }

  MeTerritorySelection _considerations(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    final malformed = raw != null && section == null;
    final items = <MeItemPresentation>[];
    if (section != null) {
      _appendBounded(items, section['interests'], _interest);
      _appendBounded(items, section['open_to'], _openTo);
      _appendBounded(items, section['watches'], _watch);
      _appendBounded(items, section['bookmarks'], _bookmark);
      _appendBounded(items, section['followed_spaces'], _followedSpace);
      _appendBounded(items, section['followed_profiles'], _followedProfile);
    }
    return _territory(
      key: 'considerations',
      label: 'Ce qui compte pour moi',
      summary: 'Intérêts, ouvertures et veilles déjà connus.',
      items: items,
      malformed: malformed,
      freshness: freshness,
      reachability: reachability,
    );
  }

  MeTerritorySelection _collectives(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    final malformed = raw != null && section == null;
    final items = <MeItemPresentation>[];
    if (section != null) {
      _appendBounded(items, section['authorized_spaces'], _space);
      _appendBounded(items, section['teams'], _team);
      _appendBounded(items, section['groups'], _group);
    }
    return _territory(
      key: 'collectives',
      label: 'Mes collectifs',
      summary: 'Appartenances et contextes visibles, sans autorité implicite.',
      items: items,
      malformed: malformed,
      freshness: freshness,
      reachability: reachability,
    );
  }

  MeTerritorySelection _resources(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    final malformed = raw != null && section == null;
    final items = <MeItemPresentation>[];
    if (section != null) {
      _appendBounded(items, section['documents'], _document);
      _appendBounded(items, section['proofs'], _proof);
      _appendBounded(items, section['credentials'], _credential);
    }
    return _territory(
      key: 'resources',
      label: 'Mes ressources',
      summary: 'Documents, preuves et credentials restent des réalités distinctes.',
      items: items,
      malformed: malformed,
      freshness: freshness,
      reachability: reachability,
    );
  }

  MeTerritorySelection? _support(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    if (section == null) return null;
    final items = <MeItemPresentation>[];
    for (final entry in section.entries) {
      final value = _map(entry.value);
      if (value?['available'] != true) continue;
      items.add(
        MeItemPresentation(
          destination: StructuredDestination(kind: 'support', id: entry.key),
          title: _supportLabel(entry.key),
          subtitle: value?['needs_response'] == true
              ? 'Une réponse peut être nécessaire.'
              : null,
        ),
      );
    }
    if (items.isEmpty) return null;
    return _territory(
      key: 'support',
      label: 'Mes appuis',
      summary: 'Relations et soutiens déjà disponibles.',
      items: items,
      malformed: false,
      freshness: freshness,
      reachability: reachability,
    );
  }

  MeTerritorySelection _territory({
    required String key,
    required String label,
    required String summary,
    required List<MeItemPresentation> items,
    required bool malformed,
    required MakoloFreshnessCue freshness,
    required MakoloReachabilityCue reachability,
  }) {
    return MeTerritorySelection(
      presentation: MeTerritoryPresentation(
        key: key,
        label: label,
        summary: summary,
        items: List.unmodifiable(items.map((item) => item.destination)),
        state: _sectionState(
          hasContent: items.isNotEmpty,
          malformed: malformed,
          freshness: freshness,
          reachability: reachability,
        ),
      ),
      items: List.unmodifiable(items),
    );
  }

  MakoloSurfacePresentation _sectionState({
    required bool hasContent,
    required bool malformed,
    required MakoloFreshnessCue freshness,
    required MakoloReachabilityCue reachability,
  }) {
    return MakoloSurfacePresentation(
      availability: hasContent
          ? MakoloAvailabilityCue.content
          : MakoloAvailabilityCue.empty,
      freshness: freshness,
      reachability: reachability,
      failure: malformed ? MakoloFailureCue.blocking : MakoloFailureCue.none,
    );
  }

  void _appendBounded(
    List<MeItemPresentation> target,
    Object? raw,
    MeItemPresentation? Function(Map<String, dynamic>) parser,
  ) {
    final collection = _map(raw);
    final rows = collection?['items'];
    if (rows is! List) return;
    for (final row in rows) {
      final map = _map(row);
      if (map == null) continue;
      final parsed = parser(map);
      if (parsed != null) target.add(parsed);
    }
  }

  MeItemPresentation? _interest(Map<String, dynamic> raw) {
    final topic = _map(raw['topic']);
    final id = _string(topic?['id']);
    final label = _string(topic?['label']);
    if (id == null || label == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'topic', id: id),
      title: label,
      subtitle: 'Intérêt',
    );
  }

  MeItemPresentation? _openTo(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final label = _string(raw['label']);
    if (id == null || label == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'open_to', id: id),
      title: label,
      subtitle: 'Ouvert à',
    );
  }

  MeItemPresentation? _watch(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['name']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'watch', id: id),
      title: title,
      subtitle: _string(raw['status_label']) ?? 'Veille',
    );
  }

  MeItemPresentation? _bookmark(Map<String, dynamic> raw) {
    final activity = _map(raw['activity']);
    final id = _string(activity?['id']);
    final title = _string(activity?['title']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'activity', id: id),
      title: title,
      subtitle: 'Enregistré',
    );
  }

  MeItemPresentation? _followedSpace(Map<String, dynamic> raw) {
    final space = _map(raw['space']);
    final id = _string(space?['id']);
    final title = _string(space?['name']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'space', id: id),
      title: title,
      subtitle: 'Espace suivi',
    );
  }

  MeItemPresentation? _followedProfile(Map<String, dynamic> raw) {
    final profile = _map(raw['profile']);
    final id = _string(profile?['id']);
    final title = _string(profile?['display_name']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'profile', id: id),
      title: title,
      subtitle: 'Profil suivi',
    );
  }

  MeItemPresentation? _space(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['name']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'space', id: id),
      title: title,
      subtitle: raw['can_act'] == true
          ? 'Contexte autorisé par le serveur'
          : 'Espace',
    );
  }

  MeItemPresentation? _team(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['name']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'team', id: id),
      title: title,
      subtitle: 'Membre',
    );
  }

  MeItemPresentation? _group(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['name']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'group', id: id),
      title: title,
      subtitle: 'Groupe visible',
    );
  }

  MeItemPresentation? _document(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['title']);
    if (id == null || title == null) return null;
    final kind = _string(raw['asset_kind_label']) ?? 'Document';
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'personal_asset', id: id),
      title: title,
      subtitle: kind,
      metadata: _metadata(_string(raw['sensitivity_label'])),
    );
  }

  MeItemPresentation? _proof(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title =
        _string(raw['proof_type_label']) ?? _string(raw['proof_type']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'proof', id: id),
      title: title,
      subtitle: _string(raw['status_label']) ?? 'Preuve',
    );
  }

  MeItemPresentation? _credential(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['title']);
    if (id == null || title == null) return null;
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'credential', id: id),
      title: title,
      subtitle: _string(raw['credential_type_label']) ?? 'Credential',
      metadata: _metadata(_string(raw['status_label'])),
    );
  }

  String? _identitySubtitle(Map<String, dynamic>? identity) {
    if (identity == null) return null;
    final parts = <String>[];
    final profession = _string(identity['profession']);
    if (profession != null) parts.add(profession);
    final location = _map(identity['location']);
    if (location != null) {
      final place = [
        _string(location['city']),
        _string(location['country']),
      ].whereType<String>().join(', ');
      if (place.isNotEmpty) parts.add(place);
    }
    return parts.isEmpty ? null : parts.join(' · ');
  }

  List<String> _metadata(String? value) =>
      value == null ? const [] : <String>[value];

  String _supportLabel(String key) => switch (key) {
    'recognition' => 'Reconnaissance',
    'loyalty' => 'Fidélité',
    'partners' => 'Partenaires',
    _ => key,
  };

  Map<String, dynamic>? _map(Object? value) {
    if (value is! Map) return null;
    return value.map((key, value) => MapEntry(key.toString(), value));
  }

  String? _string(Object? value) {
    if (value is! String) return null;
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }

  MakoloFreshnessCue _freshnessCue(FreshnessState state) {
    return switch (state) {
      FreshnessState.fresh => MakoloFreshnessCue.current,
      FreshnessState.usableButOld => MakoloFreshnessCue.oldObservation,
      FreshnessState.refreshRecommended =>
        MakoloFreshnessCue.refreshRecommended,
      FreshnessState.revalidationRequired =>
        MakoloFreshnessCue.revalidationRequired,
      FreshnessState.expired => MakoloFreshnessCue.expired,
    };
  }
}
