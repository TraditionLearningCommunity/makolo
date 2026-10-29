import '../../data/local/profile_store.dart';

/// Read-only presentation of facts already received for the active profile.
///
/// No extra persisted owner, no invented permissions, and no fallback to a
/// snapshot belonging to another profile. Missing/malformed collections stay
/// unknown rather than becoming an authoritative empty list.
class MeLocalPreview {
  const MeLocalPreview._(this._payload);

  final Map<String, dynamic> _payload;

  static MeLocalPreview? forProfile(
    StoredProjection? snapshot,
    String profileId,
  ) {
    if (snapshot == null || snapshot.kind != 'personal.me') return null;
    final actor = snapshot.payload['actor'];
    if (actor is! Map ||
        actor['type'] != 'profile' ||
        actor['id']?.toString() != profileId) {
      return null;
    }
    return MeLocalPreview._(snapshot.payload);
  }

  Map<String, dynamic>? get identity {
    final raw = _payload['identity'];
    return raw is Map ? Map<String, dynamic>.from(raw) : null;
  }

  Map<String, dynamic>? collection(String territory, String family) {
    final section = _payload[territory];
    if (section is! Map) return null;
    final raw = section[family];
    if (raw is! Map || raw['items'] is! List) return null;
    final items = raw['items'] as List;
    if (items.any((item) => item is! Map)) return null;
    return <String, dynamic>{
      ...raw.map((key, value) => MapEntry(key.toString(), value)),
      'items': [
        for (final item in items)
          Map<String, dynamic>.from(item as Map),
      ],
    };
  }
}
