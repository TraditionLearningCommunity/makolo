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
    this.canOpen = false,
    this.mediaPath,
    this.mediaAlt,
  });

  final StructuredDestination destination;
  final String title;
  final String? subtitle;
  final List<String> metadata;
  final bool canOpen;
  final String? mediaPath;
  final String? mediaAlt;
}

class MeTerritorySelection {
  const MeTerritorySelection({
    required this.presentation,
    required this.items,
    this.totalCount = 0,
    this.hasMore = false,
    this.savedCount = 0,
  });

  final MeTerritoryPresentation presentation;
  final List<MeItemPresentation> items;
  final int totalCount;
  final bool hasMore;
  final int savedCount;

  bool get hasContent =>
      presentation.state.availability == MakoloAvailabilityCue.content;
}

class MeSelection {
  const MeSelection({
    required this.presentation,
    required this.territories,
    required this.state,
    required this.identityState,
    this.identitySubtitle,
    this.identityDetail,
    this.identityAvatarUrl,
    this.canOpenHistory = false,
  });

  final MePresentation presentation;
  final List<MeTerritorySelection> territories;
  final MakoloSurfacePresentation state;
  final MakoloSurfacePresentation identityState;
  final String? identitySubtitle;
  final String? identityDetail;
  final String? identityAvatarUrl;
  final bool canOpenHistory;

  int get contentfulTerritoryCount => territories
      .where(
        (territory) =>
            territory.hasContent && territory.presentation.key != 'accesses',
      )
      .length;
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
    bool sourceInvalidated = false,
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
      _freshnessPolicy.evaluate(
        projection,
        now: now,
        invalidated: sourceInvalidated,
      ),
    );
    final state = MakoloSurfacePresentation(
      availability: MakoloAvailabilityCue.content,
      failure: failure,
      refreshing: refreshing,
    );

    final identityRaw = _map(projection.payload['identity']);
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

    final links = _map(projection.payload['links']);
    final territories = <MeTerritorySelection>[
      _passport(projection.payload['passport'], freshness, reachability),
      _considerations(
        projection.payload['considerations'],
        freshness,
        reachability,
      ),
      _collectives(projection.payload['collectives'], freshness, reachability),
      if (_string(links?['accesses']) != null)
        _accesses(freshness, reachability),
      _resources(
        projection.payload['resources'],
        freshness,
        reachability,
        ownerAvailable: _string(links?['resources']) != null,
      ),
    ];

    final support = _support(
      projection.payload['support'],
      freshness,
      reachability,
    );
    if (support != null) {
      territories.add(support);
    }

    return MeSelection(
      presentation: MePresentation(
        identityLabel: _string(identityRaw?['display_name']) ?? 'Moi',
        territories: List.unmodifiable(
          territories.map((territory) => territory.presentation),
        ),
      ),
      territories: List.unmodifiable(territories),
      state: state,
      identityState: identityState,
      identitySubtitle: _identitySubtitle(identityRaw),
      identityDetail: _string(identityRaw?['bio']),
      identityAvatarUrl: _string(identityRaw?['avatar_url']),
      canOpenHistory: _string(links?['history']) != null,
    );
  }

  MeTerritorySelection _passport(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    final malformed =
        raw != null &&
        (section == null ||
            (section.containsKey('available') &&
                section['available'] is! bool));
    final available = section?['available'] == true;

    return MeTerritorySelection(
      presentation: MeTerritoryPresentation(
        key: 'passport',
        label: 'Passeport Makolo',
        summary: 'Votre identité à partager, selon votre choix.',
        state: _sectionState(
          hasContent: available,
          malformed: malformed,
          freshness: freshness,
          reachability: reachability,
        ),
      ),
      items: available
          ? const [
              MeItemPresentation(
                destination: StructuredDestination(kind: 'passport', id: 'me'),
                title: 'Mon passeport',
                canOpen: true,
              ),
            ]
          : const [],
    );
  }

  MeTerritorySelection _considerations(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    var malformed = raw != null && section == null;
    final items = <MeItemPresentation>[];

    if (section != null) {
      malformed =
          _appendBounded(items, section, 'interests', _interest) || malformed;
      malformed =
          _appendBounded(items, section, 'open_to', _openTo) || malformed;
      malformed =
          _appendBounded(items, section, 'watches', _watch) || malformed;
      malformed =
          _appendBounded(items, section, 'bookmarks', _bookmark) || malformed;
      malformed =
          _appendBounded(items, section, 'followed_spaces', _followedSpace) ||
          malformed;
      malformed =
          _appendBounded(
            items,
            section,
            'followed_profiles',
            _followedProfile,
          ) ||
          malformed;
    }

    return _territory(
      key: 'considerations',
      label: 'Ce qui compte pour moi',
      summary: 'Intérêts, veilles et envies.',
      items: items,
      malformed: malformed,
      freshness: freshness,
      reachability: reachability,
      savedCount: _collectionCount(section, ['bookmarks']),
      // Saved possibilities have their own visible counter below this heading.
      // This count reflects personal considerations rather than double-counting
      // the separately presented collection of saved opportunities.
      totalCount: _collectionCount(section, [
        'interests',
        'open_to',
        'watches',
        'followed_spaces',
        'followed_profiles',
      ]),
      hasMore: _collectionHasMore(section, [
        'interests',
        'open_to',
        'watches',
        'bookmarks',
        'followed_spaces',
        'followed_profiles',
      ]),
    );
  }

  MeTerritorySelection _collectives(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    var malformed = raw != null && section == null;
    final items = <MeItemPresentation>[];

    if (section != null) {
      malformed =
          _appendBounded(items, section, 'authorized_spaces', _space) ||
          malformed;
      malformed = _appendBounded(items, section, 'teams', _team) || malformed;
      malformed = _appendBounded(items, section, 'groups', _group) || malformed;
    }

    return _territory(
      key: 'collectives',
      label: 'Mes collectifs',
      summary: 'Espaces, équipes et groupes.',
      items: items,
      malformed: malformed,
      freshness: freshness,
      reachability: reachability,
      totalCount: _collectionCount(section, [
        'authorized_spaces',
        'teams',
        'groups',
      ]),
      hasMore: _collectionHasMore(section, [
        'authorized_spaces',
        'teams',
        'groups',
      ]),
    );
  }

  MeTerritorySelection _accesses(
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    return _territory(
      key: 'accesses',
      label: 'Mes accès',
      summary: 'Vos droits et invitations.',
      items: const [
        MeItemPresentation(
          destination: StructuredDestination(
            kind: 'access_collection',
            id: 'mine',
          ),
          title: 'Voir mes droits disponibles',
          canOpen: true,
          subtitle: 'Billets, invitations et droits',
        ),
      ],
      malformed: false,
      freshness: freshness,
      reachability: reachability,
    );
  }

  MeTerritorySelection _resources(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability, {
    required bool ownerAvailable,
  }) {
    final section = _map(raw);
    var malformed = raw != null && section == null;
    final items = <MeItemPresentation>[];

    if (section != null) {
      malformed =
          _appendBounded(items, section, 'documents', _document) || malformed;
      malformed = _appendBounded(items, section, 'proofs', _proof) || malformed;
      malformed =
          _appendBounded(items, section, 'credentials', _credential) ||
          malformed;
    }

    // A collection link is not evidence that any resource exists.
    if (ownerAvailable && items.isNotEmpty) {
      items.insert(
        0,
        const MeItemPresentation(
          destination: StructuredDestination(
            kind: 'resource_collection',
            id: 'mine',
          ),
          title: 'Toutes mes ressources',
          subtitle: 'Documents et attestations',
          canOpen: true,
        ),
      );
    }

    return _territory(
      key: 'resources',
      label: 'Mes ressources',
      summary: 'Documents, preuves et attestations.',
      items: items,
      malformed: malformed,
      freshness: freshness,
      reachability: reachability,
      totalCount: _collectionCount(section, [
        'documents',
        'proofs',
        'credentials',
      ]),
      hasMore: _collectionHasMore(section, [
        'documents',
        'proofs',
        'credentials',
      ]),
    );
  }

  MeTerritorySelection? _support(
    Object? raw,
    MakoloFreshnessCue freshness,
    MakoloReachabilityCue reachability,
  ) {
    final section = _map(raw);
    if (section == null) {
      return null;
    }

    final items = <MeItemPresentation>[];
    for (final entry in section.entries) {
      final value = _map(entry.value);
      if (value?['available'] != true) {
        continue;
      }
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

    if (items.isEmpty) {
      return null;
    }

    return _territory(
      key: 'support',
      label: 'Mes appuis',
      summary: 'Reconnaissances et relations.',
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
    int totalCount = 0,
    bool hasMore = false,
    int savedCount = 0,
  }) {
    return MeTerritorySelection(
      totalCount: totalCount,
      hasMore: hasMore,
      savedCount: savedCount,
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

  int _collectionCount(Map<String, dynamic>? section, List<String> keys) {
    if (section == null) return 0;
    var total = 0;
    for (final key in keys) {
      final collection = _map(section[key]);
      final count = collection?['count'];
      if (count is int && count >= 0) {
        total += count;
      } else if (collection?['items'] is List) {
        total += (collection!['items'] as List).length;
      }
    }
    return total;
  }

  bool _collectionHasMore(Map<String, dynamic>? section, List<String> keys) {
    if (section == null) return false;
    return keys.any((key) => _map(section[key])?['has_more'] == true);
  }

  bool _appendBounded(
    List<MeItemPresentation> target,
    Map<String, dynamic> section,
    String key,
    MeItemPresentation? Function(Map<String, dynamic>) parser,
  ) {
    if (!section.containsKey(key)) {
      return false;
    }

    final collection = _map(section[key]);
    if (collection == null) {
      return true;
    }

    final rows = collection['items'];
    if (rows is! List) {
      return true;
    }

    for (final raw in rows) {
      final map = _map(raw);
      if (map == null) {
        continue;
      }
      final item = parser(map);
      if (item != null) {
        target.add(item);
      }
    }

    return false;
  }

  MeItemPresentation? _interest(Map<String, dynamic> raw) {
    final topic = _map(raw['topic']);
    final id = _string(topic?['id']);
    final label = _string(topic?['label']);
    if (id == null || label == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'topic', id: id),
      title: label,
    );
  }

  MeItemPresentation? _openTo(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final label = _string(raw['label']);
    if (id == null || label == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'open_to', id: id),
      title: label,
    );
  }

  MeItemPresentation? _watch(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['name']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'watch', id: id),
      canOpen: true,
      title: title,
      subtitle: _string(raw['status_label']) ?? 'Veille',
    );
  }

  MeItemPresentation? _bookmark(Map<String, dynamic> raw) {
    final activity = _map(raw['activity']);
    final id = _string(activity?['id']);
    final title = _string(activity?['title']);
    if (id == null || title == null) return null;
    String? mediaPath;
    String? mediaAlt;
    final bindings = raw['media_bindings'];
    if (bindings is List) {
      for (final candidate in bindings) {
        final binding = _map(candidate);
        final target = _map(binding?['target']);
        final resource = _map(binding?['resource']);
        final path = _string(resource?['url']);
        if (binding?['purpose'] != 'RECOGNIZE' ||
            target?['kind'] != 'activity' ||
            target?['id'] != id ||
            resource?['kind'] != 'presentation_media_use' ||
            !{'image/jpeg', 'image/png'}.contains(resource?['mime_type']) ||
            path == null ||
            !path.startsWith('/') ||
            path.startsWith('//') ||
            Uri.tryParse(path)?.hasQuery == true) {
          continue;
        }
        mediaPath = path;
        mediaAlt = _string(resource?['alt_text']);
        break;
      }
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'activity', id: id),
      canOpen: true,
      title: title,
      mediaPath: mediaPath,
      mediaAlt: mediaAlt,
    );
  }

  MeItemPresentation? _followedSpace(Map<String, dynamic> raw) {
    final space = _map(raw['space']);
    final id = _string(space?['id']);
    final title = _string(space?['name']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(
        kind: 'space',
        id: id,
        link: _string(space?['slug']),
      ),
      canOpen: _string(space?['slug']) != null,
      title: title,
    );
  }

  MeItemPresentation? _followedProfile(Map<String, dynamic> raw) {
    final profile = _map(raw['profile']);
    final id = _string(profile?['id']);
    final title = _string(profile?['display_name']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'profile', id: id),
      canOpen: true,
      title: title,
    );
  }

  MeItemPresentation? _space(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['name']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(
        kind: 'space',
        id: id,
        link: _string(raw['slug']),
      ),
      canOpen: _string(raw['slug']) != null,
      title: title,
      subtitle: raw['can_act'] == true ? 'Contexte autorisé' : 'Espace',
    );
  }

  MeItemPresentation? _team(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['name']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'team', id: id),
      title: title,
      subtitle: 'Équipe',
    );
  }

  MeItemPresentation? _group(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['name']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'group', id: id),
      canOpen: true,
      title: title,
      subtitle: 'Groupe',
    );
  }

  MeItemPresentation? _document(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['title']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'personal_asset', id: id),
      canOpen: true,
      title: title,
      subtitle: _string(raw['asset_kind_label']) ?? 'Ressource',
      metadata: _metadata(_string(raw['sensitivity_label'])),
    );
  }

  MeItemPresentation? _proof(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title =
        _string(raw['proof_type_label']) ?? _string(raw['proof_type']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'proof', id: id),
      title: title,
      subtitle: _string(raw['status_label']) ?? 'Preuve',
    );
  }

  MeItemPresentation? _credential(Map<String, dynamic> raw) {
    final id = _string(raw['id']);
    final title = _string(raw['title']);
    if (id == null || title == null) {
      return null;
    }
    return MeItemPresentation(
      destination: StructuredDestination(kind: 'credential', id: id),
      title: title,
      subtitle: _string(raw['credential_type_label']) ?? 'Titre',
      metadata: _metadata(_string(raw['status_label'])),
    );
  }

  String? _identitySubtitle(Map<String, dynamic>? identity) {
    if (identity == null) {
      return null;
    }

    final parts = <String>[];
    final profession = _string(identity['profession']);
    if (profession != null) {
      parts.add(profession);
    }

    final location = _map(identity['location']);
    if (location != null) {
      final place = [
        _string(location['city']),
        _string(location['country']),
      ].whereType<String>().join(', ');
      if (place.isNotEmpty) {
        parts.add(place);
      }
    }

    return parts.isEmpty ? null : parts.join(' · ');
  }

  List<String> _metadata(String? value) {
    return value == null ? const [] : <String>[value];
  }

  String _supportLabel(String key) {
    return switch (key) {
      'recognition' => 'Reconnaissance',
      'loyalty' => 'Fidélité',
      'partners' => 'Partenaires',
      _ => key,
    };
  }

  Map<String, dynamic>? _map(Object? value) {
    if (value is! Map) {
      return null;
    }
    return value.map((key, item) => MapEntry(key.toString(), item));
  }

  String? _string(Object? value) {
    if (value is! String) {
      return null;
    }
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
