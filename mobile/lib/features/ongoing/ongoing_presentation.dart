import '../../data/local/profile_store.dart';

class OngoingContinuityPresentation {
  const OngoingContinuityPresentation({
    required this.ownerKind,
    required this.ownerId,
    required this.kind,
    required this.title,
    required this.synthesis,
    required this.settled,
    required this.mySide,
    required this.elsewhere,
    required this.next,
    required this.waiting,
    required this.blocker,
    required this.unknown,
    required this.timing,
    required this.place,
    required this.capabilities,
    required this.links,
    required this.rawState,
  });

  final String? ownerKind;
  final String? ownerId;
  final String kind;
  final String title;
  final String synthesis;
  final List<String> settled;
  final List<String> mySide;
  final List<String> elsewhere;
  final List<String> next;
  final String? waiting;
  final String? blocker;
  final String? unknown;
  final Map<String, dynamic> timing;
  final Map<String, dynamic> place;
  final List<String> capabilities;
  final Map<String, String> links;
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

    final settled = <String>[
      for (final entry in ready)
        if (_text(entry['title']) != null) _text(entry['title'])!,
    ];
    final mySide = <String>[
      for (final entry in interventions)
        if (_text(entry['title']) != null) _text(entry['title'])!,
    ];
    final elsewhere = <String>[
      if (_text(continuation['summary']) != null)
        _text(continuation['summary'])!,
      if (continuation['state'] == 'waiting' &&
          _text(continuation['summary']) == null)
        'Une réponse est attendue.',
    ];
    final nextItems = <String>[
      if (_text(next['title']) != null) _text(next['title'])!,
    ];

    final rawState = _text(item['state']) ?? 'unknown';
    final blockerText = _text(blocker['title']) ?? _text(blocker['summary']);
    final waitingText = continuation['state'] == 'waiting'
        ? (_text(continuation['summary']) ?? 'Une réponse est attendue.')
        : null;

    return OngoingContinuityPresentation(
      ownerKind: _text(source['kind']),
      ownerId: _text(source['id']),
      kind: _text(item['kind']) ?? 'unknown',
      title: _text(item['title']) ?? 'Continuité',
      synthesis: _synthesis(
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
      next: List.unmodifiable(nextItems),
      waiting: waitingText,
      blocker: blockerText,
      unknown: rawState == 'unknown' ? 'L’état actuel est inconnu.' : null,
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

  static String? _text(Object? value) {
    if (value is! String) return null;
    final text = value.trim();
    return text.isEmpty ? null : text;
  }
}
