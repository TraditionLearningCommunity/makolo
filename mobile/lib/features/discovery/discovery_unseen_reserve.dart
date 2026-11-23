/// Device presentation ledger for server-admitted Discovery candidates.
///
/// The backend decides eligibility and order. This ledger only records which
/// already-received candidates have been shown and which are still unseen.
/// It never creates an owner action, Saved relation, or local ranking.
class DiscoveryUnseenReserve {
  DiscoveryUnseenReserve({
    this.rootReceivedAt,
    Iterable<String> shownKeys = const [],
    Iterable<String> evictedKeys = const [],
    Iterable<Map<String, dynamic>> unseen = const [],
  }) : _shown = <String>{...shownKeys},
       _evicted = <String>{...evictedKeys} {
    observe(unseen);
  }

  final DateTime? rootReceivedAt;
  static const int maxUnseen = 50;
  // Transport is at most 48 pages of 100 rows plus the signed root.
  // Older metadata is redundant once those raw pages are pruned.
  static const int maxRememberedKeys = 5200;
  final Set<String> _shown;
  final Set<String> _evicted;
  final Map<String, Map<String, dynamic>> _unseen = {};

  static String? keyOf(Map<String, dynamic> candidate) {
    final identity = candidate['identity'];
    if (identity is! Map) return null;
    final key = identity['candidate_key'];
    return key is String && key.isNotEmpty ? key : null;
  }

  Set<String> get shownKeys => Set.unmodifiable(_shown);
  Set<String> get unseenKeys => Set.unmodifiable(_unseen.keys.toSet());
  int get unseenCount => _unseen.length;

  /// Append in original server order. An overflow evicts the oldest unseen
  /// candidate, never a shown one. Evicted keys cannot reappear merely
  /// because an older transport page remains available offline.
  void observe(Iterable<Map<String, dynamic>> candidates) {
    for (final row in candidates) {
      final key = keyOf(row);
      if (key == null ||
          _shown.contains(key) ||
          _evicted.contains(key) ||
          _unseen.containsKey(key)) {
        continue;
      }
      _unseen[key] = Map<String, dynamic>.from(row);
      while (_unseen.length > maxUnseen) {
        final oldest = _unseen.keys.first;
        _unseen.remove(oldest);
        _evicted.add(oldest);
        _trimHistory(_evicted);
      }
    }
  }

  static void _trimHistory(Set<String> keys) {
    while (keys.length > maxRememberedKeys) {
      keys.remove(keys.first);
    }
  }

  List<String> pendingFrom(Iterable<String> eligibleKeys) {
    final eligible = eligibleKeys.toSet();
    return List.unmodifiable(_unseen.keys.where(eligible.contains));
  }

  /// Reveal only already acquired, currently eligible candidates. The count
  /// is presentation pacing, not relevance selection.
  List<String> reveal(Iterable<String> eligibleKeys, {required int count}) {
    if (count <= 0) return const [];
    final batch = pendingFrom(eligibleKeys).take(count).toList();
    for (final key in batch) {
      _unseen.remove(key);
      _shown.add(key);
      _trimHistory(_shown);
    }
    return List.unmodifiable(batch);
  }

  bool isShown(String key) => _shown.contains(key);

  Map<String, dynamic> toPayload({
    required String profileId,
    required String fieldKey,
    required DateTime rootReceivedAt,
  }) => {
    'profile_id': profileId,
    'field_key': fieldKey,
    'root_received_at': rootReceivedAt.toUtc().toIso8601String(),
    'shown_keys': _shown.toList(growable: false),
    'evicted_keys': _evicted.toList(growable: false),
    'unseen': _unseen.values.toList(growable: false),
  };

  static DiscoveryUnseenReserve? fromPayload(
    Map<String, dynamic> payload, {
    required String profileId,
    required String fieldKey,
    required DateTime rootReceivedAt,
  }) {
    if (payload['profile_id'] != profileId ||
        payload['field_key'] != fieldKey ||
        payload['root_received_at'] !=
            rootReceivedAt.toUtc().toIso8601String()) {
      return null;
    }
    final shown = payload['shown_keys'];
    final evicted = payload['evicted_keys'];
    final unseen = payload['unseen'];
    if (shown is! List || evicted is! List || unseen is! List) return null;
    if (shown.any((key) => key is! String) ||
        evicted.any((key) => key is! String)) {
      return null;
    }
    final rows = <Map<String, dynamic>>[];
    for (final raw in unseen) {
      if (raw is! Map) return null;
      rows.add(Map<String, dynamic>.from(raw));
    }
    return DiscoveryUnseenReserve(
      rootReceivedAt: rootReceivedAt,
      shownKeys: shown.cast<String>(),
      evictedKeys: evicted.cast<String>(),
      unseen: rows,
    );
  }
}
