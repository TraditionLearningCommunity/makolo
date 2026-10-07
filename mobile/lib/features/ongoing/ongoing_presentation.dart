import '../../data/local/profile_store.dart';

class OngoingContinuityPresentation {
  const OngoingContinuityPresentation({
    required this.id,
    required this.ownerKind,
    required this.ownerId,
    required this.kind,
    required this.title,
    required this.synthesis,
    required this.settled,
    required this.mySide,
    required this.elsewhere,
    required this.makolo,
    required this.systemOrTime,
    required this.next,
    required this.waiting,
    required this.blockers,
    required this.unknown,
    required this.timing,
    required this.place,
    required this.capabilities,
    required this.links,
    required this.handoffs,
    required this.rawState,
  });

  final String id;
  final String? ownerKind;
  final String? ownerId;
  final String kind;
  final String title;
  final String synthesis;
  final List<String> settled;
  final List<String> mySide;
  final List<String> elsewhere;
  final List<String> makolo;
  final List<String> systemOrTime;
  final List<String> next;
  final String? waiting;
  final List<String> blockers;
  String? get blocker => blockers.isEmpty ? null : blockers.first;
  final String? unknown;
  final Map<String, dynamic> timing;
  final Map<String, dynamic> place;
  final List<String> capabilities;
  final Map<String, String> links;
  final List<OngoingHandoffPresentation> handoffs;
  final String rawState;

  bool get hasParallelMovement {
    var movingDimensions = 0;
    if (mySide.isNotEmpty) movingDimensions++;
    if (elsewhere.isNotEmpty) movingDimensions++;
    if (next.isNotEmpty) movingDimensions++;
    return movingDimensions > 1;
  }

  static List<OngoingContinuityPresentation> fromProjection(
    StoredProjection projection,
  ) {
    final rawItems = projection.payload['items'];
    if (rawItems is! List) return const [];
    return [
      for (final raw in rawItems)
        if (raw is Map) _fromMap(Map<String, dynamic>.from(raw)),
    ];
  }

  static OngoingContinuityPresentation _fromMap(Map<String, dynamic> item) {
    final source = _map(item['source']);
    final ready = _maps(item['ready']);
    final interventions = _maps(item['actor_interventions']);
    final continuation = _map(item['continuation']);
    final blocker = _map(item['blocker']);
    final next = _map(item['next']);
    final links = _map(item['links']);
    final c0Handoffs = _maps(item['handoffs']);
    final continuityIdentity = _map(item['continuity_identity']);

    final continuityId =
        _text(item['id']) ??
        _text(item['continuity_identity']) ??
        _text(continuityIdentity['id']) ??
        [
          _text(source['kind']) ?? _text(item['kind']) ?? 'continuity',
          _text(source['id']) ?? _text(item['title']) ?? 'unknown',
        ].join(':');

    final settled = <String>[
      ..._labels(item['settled']),
      for (final entry in ready)
        if (_text(entry['title']) != null &&
            !_labels(item['settled']).contains(_text(entry['title'])))
          _text(entry['title'])!,
    ];
    final mySide = <String>[
      ..._labels(item['my_side']),
      ..._labels(item['profile_side_remaining']),
      for (final entry in interventions)
        if ((_text(entry['title']) ?? _text(entry['summary'])) case final text?)
          if (!_labels(item['my_side']).contains(text) &&
              !_labels(item['profile_side_remaining']).contains(text))
            text,
    ];
    final elsewhere = <String>[
      ..._labels(item['elsewhere']),
      ..._labels(item['continues_elsewhere']),
      if (_text(continuation['summary']) != null)
        _text(continuation['summary'])!,
      if (continuation['state'] == 'waiting' &&
          _text(continuation['summary']) == null)
        'Une réponse est attendue.',
    ];
    final nextItems = <String>[
      ..._labels(item['next_items']),
      if (_text(next['title']) != null) _text(next['title'])!,
    ];
    final makolo = <String>[
      ..._labels(item['makolo']),
      ?_text(item['makolo_preparation']),
    ];
    final systemOrTime = _labels(item['system_or_time']);

    final explicitState = _text(item['state']);
    final rawState = explicitState ?? 'unspecified';
    final serverSummary = _text(item['summary']);
    final blockers = <String>[
      ..._labels(item['blockers']),
      ?(_text(blocker['title']) ?? _text(blocker['summary'])),
    ];
    final blockerText = blockers.isEmpty ? null : blockers.first;
    final waitingText = continuation['state'] == 'waiting'
        ? (_text(continuation['summary']) ?? 'Une réponse est attendue.')
        : null;

    return OngoingContinuityPresentation(
      id: continuityId,
      ownerKind: _text(source['kind']),
      ownerId: _text(source['id']),
      kind: _text(item['kind']) ?? 'unknown',
      title:
          _text(item['human_context']) ?? _text(item['title']) ?? 'Continuité',
      synthesis:
          _text(item['synthesis']) ??
          _text(item['where_i_am']) ??
          serverSummary ??
          _synthesis(
            rawState: rawState,
            ready: settled,
            mySide: mySide,
            elsewhere: elsewhere,
            blocker: blockerText,
            waiting: waitingText,
          ),
      settled: List.unmodifiable(settled),
      mySide: List.unmodifiable(mySide),
      elsewhere: List.unmodifiable(elsewhere),
      makolo: List.unmodifiable(makolo),
      systemOrTime: List.unmodifiable(systemOrTime),
      next: List.unmodifiable(nextItems),
      waiting: waitingText,
      blockers: List.unmodifiable(blockers),
      unknown: explicitState == 'unknown' ? 'L’état actuel est inconnu.' : null,
      timing: Map.unmodifiable(_map(item['timing'])),
      place: Map.unmodifiable(_map(item['place'])),
      capabilities: [
        for (final value
            in item['capabilities'] is List
                ? item['capabilities'] as List
                : const [])
          if (value is String) value,
      ],
      links: {
        for (final entry in links.entries)
          if (entry.value is String) entry.key: entry.value as String,
      },
      handoffs: List.unmodifiable([
        for (final handoff in c0Handoffs)
          ?OngoingHandoffPresentation.fromMap(handoff),
      ]),
      rawState: rawState,
    );
  }

  static String _synthesis({
    required String rawState,
    required List<String> ready,
    required List<String> mySide,
    required List<String> elsewhere,
    required String? blocker,
    required String? waiting,
  }) {
    if (blocker != null) return blocker;
    if (mySide.isNotEmpty) return mySide.first;
    if (waiting != null) return waiting;
    if (elsewhere.isNotEmpty) return elsewhere.first;
    if (ready.isNotEmpty) return ready.first;
    return switch (rawState) {
      'available' => 'Votre accès est disponible.',
      'pending' => 'Cette réalité continue.',
      'offered' => 'Une décision vous attend.',
      'blocked' => 'Cette réalité est bloquée.',
      _ => 'Cette réalité continue.',
    };
  }

  static Map<String, dynamic> _map(Object? value) =>
      value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

  static List<Map<String, dynamic>> _maps(Object? value) {
    if (value is! List) return const [];
    return [
      for (final item in value)
        if (item is Map) Map<String, dynamic>.from(item),
    ];
  }

  static List<String> _labels(Object? value) {
    if (value is! List) return const [];
    return [
      for (final item in value) ?_label(item),
    ];
  }

  static String? _label(Object? value) {
    if (value is String) return _text(value);
    if (value is! Map) return null;

    final map = Map<String, dynamic>.from(value);
    final title = _text(map['title']);
    if (title != null) return title;

    final summary = _text(map['summary']);
    if (summary != null) return summary;

    final label = _text(map['label']);
    if (label != null) return label;

    final blockedTransition = _map(map['blocked_transition']);
    final blockedTitle = _text(blockedTransition['title']);
    if (blockedTitle != null) return blockedTitle;

    return _text(blockedTransition['summary']);
  }

  static String? _text(Object? value) {
    if (value is! String) return null;
    final text = value.trim();
    return text.isEmpty ? null : text;
  }
}

class OngoingHandoffPresentation {
  const OngoingHandoffPresentation({
    required this.type,
    required this.target,
    required this.id,
  });

  final String type;
  final String target;
  final String id;

  static OngoingHandoffPresentation? fromMap(Map<String, dynamic> value) {
    final type = OngoingContinuityPresentation._text(value['type']);
    final target = OngoingContinuityPresentation._text(value['target']);
    final id = OngoingContinuityPresentation._text(value['id']);
    if (type == null || target == null || id == null) return null;
    return OngoingHandoffPresentation(type: type, target: target, id: id);
  }
}
