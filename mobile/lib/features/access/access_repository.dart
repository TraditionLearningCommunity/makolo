import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/projection_contract.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class AccessSourceState {
  const AccessSourceState({
    this.lastSuccessAt,
    this.invalidated = false,
    this.lastErrorCode,
  });

  final DateTime? lastSuccessAt;
  final bool invalidated;
  final String? lastErrorCode;

  ReachabilityState get reachability => reachabilityFromSource(
    lastSuccessAt: lastSuccessAt,
    lastErrorCode: lastErrorCode,
  );

  static const unknown = AccessSourceState();
}

class AccessCredentialData {
  const AccessCredentialData({
    required this.accessId,
    required this.credentialType,
    required this.payload,
    this.issuedAt,
  });

  final String accessId;
  final String credentialType;
  final String payload;
  final DateTime? issuedAt;
}

class AccessRepository {
  AccessRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
    this.api,
  });

  static const projectionKind = 'personal.access.detail';
  static const credentialProjectionKind = 'personal.access.credential';

  static const freshnessPolicy = FreshnessPolicy(id: 'access-owner');

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;
  final MakoloApiClient? api;

  SyncSourceDefinition sourceFor(String accessId) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'access:$accessId',
      owner: 'Access',
      path: 'api/v1/me/accesses/$accessId/',
      projectionKind: projectionKind,
      resourceKey: accessId,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<StoredProjection?> watchDetail(String accessId) {
    return store.watchProjection(projectionKind, resourceKey: accessId);
  }

  Future<StoredProjection?> readDetail(String accessId) {
    return store.readProjection(projectionKind, resourceKey: accessId);
  }

  Stream<AccessSourceState> watchSource(String accessId) {
    final sourceKey = sourceFor(accessId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.sourceKey.equals(sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? AccessSourceState.unknown
          : AccessSourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }

  Future<AccessSourceState> readSource(String accessId) async {
    final sourceKey = sourceFor(accessId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.sourceKey.equals(sourceKey),
      );
    final row = await query.getSingleOrNull();
    return row == null
        ? AccessSourceState.unknown
        : AccessSourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          );
  }

  Future<void> refreshDetail(String accessId) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Access owner is not configured.');
    }
    await engine.refreshSource(sourceFor(accessId));
  }

  Future<void> invalidateDetail(String accessId) async {
    final engine = sync;
    if (engine == null) return;
    await engine.invalidate(sourceFor(accessId));
  }

  Future<AccessCredentialData> fetchCredential({
    required String accessId,
    required String path,
  }) async {
    final remote = api;
    if (remote == null) {
      throw StateError('Remote Access owner is not configured.');
    }

    final response = await remote.get(path);
    final envelope = ProjectionEnvelope.parse(response.jsonObject());
    if (envelope.projection != credentialProjectionKind) {
      throw FormatException(
        'Expected $credentialProjectionKind, got ${envelope.projection}',
      );
    }

    final access = _map(envelope.data['access']);
    final relationship = _string(envelope.data['relationship']);
    final representation = _map(envelope.data['representation']);
    final receivedAccessId = _string(access['id']);
    final credentialType = _string(representation['credential_type']);
    final payload = _string(representation['payload']);

    if (receivedAccessId != accessId ||
        relationship != 'beneficiary' ||
        credentialType == null ||
        payload == null) {
      throw const FormatException('Invalid AccessCredential owner payload.');
    }

    return AccessCredentialData(
      accessId: accessId,
      credentialType: credentialType,
      payload: payload,
      issuedAt: _dateTime(representation['issued_at']),
    );
  }

  static Map<String, dynamic> _map(Object? value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), item));
    }
    return const {};
  }

  static String? _string(Object? value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? null : text;
  }

  static DateTime? _dateTime(Object? value) {
    final text = _string(value);
    return text == null ? null : DateTime.tryParse(text);
  }
}
