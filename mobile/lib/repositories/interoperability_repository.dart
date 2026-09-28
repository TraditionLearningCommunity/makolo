import '../data/local/profile_store.dart';

class InteroperabilityConnectionProjection {
  const InteroperabilityConnectionProjection({
    required this.id,
    required this.displayName,
    required this.owner,
    required this.scope,
    required this.providerProtocol,
    required this.available,
    required this.connected,
    required this.usable,
    required this.manageable,
    required this.enabled,
    required this.status,
    required this.health,
    required this.capabilities,
  });

  final String id;
  final String displayName;
  final String owner;
  final String scope;
  final String providerProtocol;
  final bool available;
  final bool connected;
  final bool usable;
  final bool manageable;
  final bool enabled;
  final String status;
  final String health;
  final List<String> capabilities;

  factory InteroperabilityConnectionProjection.fromJson(
    Map<String, dynamic> json,
  ) {
    return InteroperabilityConnectionProjection(
      id: json['id'] is String ? json['id'] as String : '',
      displayName: json['display_name'] is String
          ? json['display_name'] as String
          : 'Service',
      owner: json['owner'] is String ? json['owner'] as String : '',
      scope: json['scope'] is String ? json['scope'] as String : '',
      providerProtocol: json['provider_protocol'] is String
          ? json['provider_protocol'] as String
          : '',
      available: json['available'] == true,
      connected: json['connected'] == true,
      usable: json['usable'] == true,
      manageable: json['manageable'] == true,
      enabled: json['enabled'] == true,
      status: json['status'] is String ? json['status'] as String : 'unknown',
      health: json['health'] is String ? json['health'] as String : 'unknown',
      capabilities: _stringList(json['capabilities']),
    );
  }
}

class InteroperabilityProviderProjection {
  const InteroperabilityProviderProjection({
    required this.code,
    required this.available,
    required this.capabilities,
  });

  final String code;
  final bool available;
  final List<String> capabilities;

  factory InteroperabilityProviderProjection.fromJson(
    Map<String, dynamic> json,
  ) {
    return InteroperabilityProviderProjection(
      code: json['code'] is String ? json['code'] as String : '',
      available: json['available'] == true,
      capabilities: _stringList(json['capabilities']),
    );
  }
}

class InteroperabilityActionProjection {
  const InteroperabilityActionProjection({
    required this.code,
    required this.capability,
    required this.owner,
    required this.requiresConnection,
    required this.available,
    required this.authorized,
    required this.idempotencyRequired,
  });

  final String code;
  final String capability;
  final String owner;
  final bool requiresConnection;
  final bool available;
  final bool authorized;
  final bool idempotencyRequired;

  factory InteroperabilityActionProjection.fromJson(Map<String, dynamic> json) {
    return InteroperabilityActionProjection(
      code: json['code'] is String ? json['code'] as String : '',
      capability:
          json['capability'] is String ? json['capability'] as String : '',
      owner: json['owner'] is String ? json['owner'] as String : '',
      requiresConnection: json['requires_connection'] == true,
      available: json['available'] == true,
      authorized: json['authorized'] == true,
      idempotencyRequired: json['idempotency_required'] == true,
    );
  }
}

class InteroperabilityExtensionProjection {
  const InteroperabilityExtensionProjection({
    required this.code,
    required this.actions,
    required this.readProjections,
    required this.uiSlots,
    required this.available,
    required this.enabled,
  });

  final String code;
  final List<String> actions;
  final List<String> readProjections;
  final List<String> uiSlots;
  final bool available;
  final bool enabled;

  factory InteroperabilityExtensionProjection.fromJson(
    Map<String, dynamic> json,
  ) {
    return InteroperabilityExtensionProjection(
      code: json['code'] is String ? json['code'] as String : '',
      actions: _stringList(json['actions']),
      readProjections: _stringList(json['read_projections']),
      uiSlots: _stringList(json['ui_slots']),
      available: json['available'] == true,
      enabled: json['enabled'] == true,
    );
  }
}

class ProfileInteroperabilityProjection {
  const ProfileInteroperabilityProjection({
    required this.schemaVersion,
    required this.providers,
    required this.connections,
    required this.actions,
    required this.extensions,
    required this.receivedAt,
  });

  final String schemaVersion;
  final List<InteroperabilityProviderProjection> providers;
  final List<InteroperabilityConnectionProjection> connections;
  final List<InteroperabilityActionProjection> actions;
  final List<InteroperabilityExtensionProjection> extensions;
  final DateTime receivedAt;

  bool get isEmpty =>
      providers.isEmpty &&
      connections.isEmpty &&
      actions.isEmpty &&
      extensions.isEmpty;

  factory ProfileInteroperabilityProjection.fromStored(
    StoredProjection stored,
  ) {
    final payload = stored.payload;
    if (payload['schema_version'] != 'z16.v1' ||
        payload['context'] != 'profile') {
      throw const FormatException(
        'Unsupported Profile interoperability projection.',
      );
    }

    return ProfileInteroperabilityProjection(
      schemaVersion: payload['schema_version'] as String,
      providers: _maps(payload['providers'])
          .map(InteroperabilityProviderProjection.fromJson)
          .toList(growable: false),
      connections: _maps(payload['connections'])
          .map(InteroperabilityConnectionProjection.fromJson)
          .where((connection) => connection.scope == 'profile')
          .toList(growable: false),
      actions: _maps(payload['actions'])
          .map(InteroperabilityActionProjection.fromJson)
          .where((action) => action.authorized)
          .toList(growable: false),
      extensions: _maps(payload['extensions'])
          .map(InteroperabilityExtensionProjection.fromJson)
          .where((extension) => extension.available && extension.enabled)
          .toList(growable: false),
      receivedAt: stored.receivedAt,
    );
  }
}

class ProfileInteroperabilityRepository {
  const ProfileInteroperabilityRepository(this.store);

  static const projectionKind = 'personal.interoperability';

  final ProfileStore store;

  Stream<ProfileInteroperabilityProjection?> watch() {
    return store.watchProjection(projectionKind).map((stored) {
      if (stored == null) return null;
      return ProfileInteroperabilityProjection.fromStored(stored);
    });
  }

  Future<ProfileInteroperabilityProjection?> read() async {
    final stored = await store.readProjection(projectionKind);
    if (stored == null) return null;
    return ProfileInteroperabilityProjection.fromStored(stored);
  }
}

List<String> _stringList(Object? value) {
  if (value is! List) return const [];
  return value.whereType<String>().toList(growable: false);
}

List<Map<String, dynamic>> _maps(Object? value) {
  if (value is! List) return const [];
  return value
      .whereType<Map>()
      .map((row) => Map<String, dynamic>.from(row))
      .toList(growable: false);
}
