import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../network/api_error.dart';
import '../../sync/freshness.dart';
import '../../sync/projection_contract.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';
import 'access_credential_vault.dart';

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
    this.locallyRetained = false,
    this.checkedAt,
    this.offlineUntil,
  });

  final String accessId;
  final String credentialType;
  final String payload;
  final DateTime? issuedAt;
  final bool locallyRetained;
  final DateTime? checkedAt;
  final DateTime? offlineUntil;
}

class AccessRepository {
  AccessRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
    this.api,
    AccessCredentialVault? credentialVault,
  }) : credentialVault = credentialVault ?? SecureAccessCredentialVault();

  static const collectionProjectionKind = 'personal.accesses';
  static const projectionKind = 'personal.access.detail';
  static const credentialProjectionKind = 'personal.access.credential';
  static const defaultCollectionLimit = 24;

  static const freshnessPolicy = FreshnessPolicy(id: 'access-owner');

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;
  final MakoloApiClient? api;
  final AccessCredentialVault credentialVault;
  final Map<String, int> _credentialGenerations = {};

  String collectionResourceKey({
    required String relationship,
    required int offset,
    int limit = defaultCollectionLimit,
  }) => '$relationship:$offset:$limit';

  String collectionSourceKey({
    required String relationship,
    required int offset,
    int limit = defaultCollectionLimit,
  }) => 'accesses:$relationship:$offset:$limit';

  SyncSourceDefinition collectionSourceFor({
    required String relationship,
    required int offset,
    int limit = defaultCollectionLimit,
  }) {
    final encodedRelationship = Uri.encodeQueryComponent(relationship);
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: collectionSourceKey(
        relationship: relationship,
        offset: offset,
        limit: limit,
      ),
      owner: 'Access',
      path:
          'api/v1/me/accesses/?relationship=$encodedRelationship'
          '&limit=$limit&offset=$offset',
      projectionKind: collectionProjectionKind,
      resourceKey: collectionResourceKey(
        relationship: relationship,
        offset: offset,
        limit: limit,
      ),
      category: SyncSourceCategory.collection,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<List<StoredProjection>> watchCollectionPages() =>
      store.watchProjections(collectionProjectionKind);

  Future<StoredProjection?> readCollectionPage({
    required String relationship,
    required int offset,
    int limit = defaultCollectionLimit,
  }) => store.readProjection(
    collectionProjectionKind,
    resourceKey: collectionResourceKey(
      relationship: relationship,
      offset: offset,
      limit: limit,
    ),
  );

  Stream<AccessSourceState> watchCollectionSource({
    required String relationship,
    int offset = 0,
    int limit = defaultCollectionLimit,
  }) {
    final sourceKey = collectionSourceKey(
      relationship: relationship,
      offset: offset,
      limit: limit,
    );
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
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

  /// Any denied Access collection must withdraw its known beneficiary
  /// context, even if an older list page is still present in SQLite.
  Stream<Set<String>> watchRevokedCollectionRelationships() {
    final query = database.select(database.syncSources)
      ..where((row) =>
          row.profileId.equals(profileId) &
          row.sourceKey.like('accesses:%'));
    return query.watch().map((rows) {
      final revoked = <String>{};
      for (final row in rows) {
        if (!row.invalidated) continue;
        final parts = row.sourceKey.split(':');
        if (parts.length >= 2) revoked.add(parts[1]);
      }
      return revoked;
    });
  }

  Future<bool> _hasRevokedBeneficiaryCollection() async {
    final rows = await (database.select(database.syncSources)
          ..where((row) =>
              row.profileId.equals(profileId) &
              row.sourceKey.like('accesses:beneficiary:%')))
        .get();
    return rows.any((row) => row.invalidated);
  }

  Future<AccessSourceState> readCollectionSource({
    required String relationship,
    int offset = 0,
    int limit = defaultCollectionLimit,
  }) async {
    final key = collectionSourceKey(
      relationship: relationship,
      offset: offset,
      limit: limit,
    );
    final row = await (database.select(database.syncSources)
          ..where((item) =>
              item.profileId.equals(profileId) &
              item.sourceKey.equals(key)))
        .getSingleOrNull();
    return row == null
        ? AccessSourceState.unknown
        : AccessSourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          );
  }

  /// A bounded set of owner-authorized details is warmed after an online
  /// collection refresh. No credential payload or AccessUse is ever cached.
  Future<void> warmKnownDetails(
    Iterable<String> ids, {
    int limit = 6,
  }) async {
    if (sync == null) return;
    final unique = <String>{};
    var attempted = 0;
    for (final id in ids) {
      if (id.isEmpty || !unique.add(id)) continue;
      if (attempted >= limit) break;
      if (await readDetail(id) != null) continue;
      final before = await readSource(id);
      if (before.invalidated) continue;
      attempted++;
      try {
        await refreshDetail(id);
        final after = await readSource(id);
        if (after.reachability == ReachabilityState.unreachable &&
            !after.invalidated) {
          break;
        }
      } on Object {
        break;
      }
    }
  }

  Future<void> refreshCollectionPage({
    required String relationship,
    required int offset,
    int limit = defaultCollectionLimit,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Access owner is not configured.');
    }
    await engine.refreshSource(
      collectionSourceFor(
        relationship: relationship,
        offset: offset,
        limit: limit,
      ),
    );
  }

  SyncSourceDefinition sourceFor(String accessId) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'access:$accessId',
      owner: 'Access',
      path: 'api/v1/me/accesses/$accessId/',
      projectionKind: projectionKind,
      resourceKey: accessId,
      indexedResourceKind: 'Access',
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
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
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
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
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
    if ((await readSource(accessId)).invalidated) {
      await credentialVault.delete(profileId, accessId);
    }
  }

  Future<void> invalidateDetail(String accessId) async {
    final engine = sync;
    if (engine == null) return;
    await engine.invalidate(sourceFor(accessId));
  }

  /// Only a beneficiary capability issued by the owner unlocks the QR
  /// navigation. Merely knowing an Access ID or a link grants no authority.
  static String? credentialPathFromKnownPages(
    Iterable<StoredProjection> pages,
    String accessId,
  ) {
    for (final page in pages) {
      if (page.kind != collectionProjectionKind ||
          page.schemaVersion != 1 ||
          !page.resourceKey.startsWith('beneficiary:')) {
        continue;
      }
      final rows = page.payload['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        final item = _map(raw);
        if (_string(_map(item['identity'])['id']) != accessId ||
            _string(item['relationship']) != 'beneficiary') continue;
        final capabilities = item['capabilities'];
        if (capabilities is! List ||
            !capabilities.contains('present_credential')) continue;
        final link = _string(_map(item['links'])['credential']);
        if (link != null && _isCredentialPath(link, accessId)) return link;
      }
    }
    return null;
  }

  Future<String?> readKnownCredentialPath(String accessId) async {
    if (await _hasRevokedBeneficiaryCollection()) return null;
    return credentialPathFromKnownPages(
      await store.readProjections(collectionProjectionKind),
      accessId,
    );
  }

  static bool _isCredentialPath(String path, String accessId) {
    final parsed = Uri.tryParse(path);
    if (parsed == null || parsed.hasScheme || parsed.hasAuthority ||
        parsed.hasQuery || parsed.hasFragment) return false;
    return parsed.path ==
        '/api/v1/me/accesses/$accessId/credential/';
  }

  /// Credential retention is an independent owner decision from Access
  /// itself. A refusal must not erase a legitimate Access detail.
  Future<bool> _credentialRetentionDenied(String accessId) async {
    final row = await (database.select(database.syncSources)
          ..where((item) =>
              item.profileId.equals(profileId) &
              item.sourceKey.equals('access-credential:$accessId')))
        .getSingleOrNull();
    return row?.invalidated == true;
  }

  Future<void> _markCredentialRetention(
    String accessId, {
    required bool denied,
  }) async {
    await database.into(database.syncSources).insertOnConflictUpdate(
      SyncSourcesCompanion.insert(
        profileId: profileId,
        sourceKey: 'access-credential:$accessId',
        route: 'api/v1/me/accesses/$accessId/credential/',
        invalidated: Value(denied),
        lastErrorCode: Value(denied ? 'retention_denied' : null),
      ),
    );
  }

  Future<AccessCredentialData?> readRetainedCredential(
      String accessId) async {
    final detail = await readSource(accessId);
    if (detail.invalidated ||
        await _hasRevokedBeneficiaryCollection() ||
        await _credentialRetentionDenied(accessId)) {
      try {
        await credentialVault.delete(profileId, accessId);
      } on Object {
        // A durable nonsecret tombstone still blocks local presentation.
      }
      return null;
    }
    final value = await credentialVault.read(profileId, accessId);
    if (value == null || !_isCredentialPath(value.path, accessId)) {
      if (value != null) await credentialVault.delete(profileId, accessId);
      return null;
    }
    return AccessCredentialData(
      accessId: accessId,
      credentialType: 'qr',
      payload: value.payload,
      issuedAt: value.issuedAt,
      locallyRetained: true,
      checkedAt: value.checkedAt,
      offlineUntil: value.expiresAt,
    );
  }

  Future<AccessCredentialData> fetchCredential({
    required String accessId,
    required String path,
  }) async {
    final remote = api;
    if (remote == null) {
      throw StateError('Remote Access owner is not configured.');
    }
    if (!_isCredentialPath(path, accessId)) {
      throw const FormatException('Unexpected Access credential owner path');
    }
    final generation = (_credentialGenerations[accessId] ?? 0) + 1;
    _credentialGenerations[accessId] = generation;
    bool isCurrent() =>
        _credentialGenerations[accessId] == generation &&
        sync?.isActive != false;

    late final Map<String, dynamic> data;
    try {
      final response = await remote.get(path);
      final envelope = ProjectionEnvelope.parse(response.jsonObject());
      if (envelope.projection != credentialProjectionKind) {
        throw FormatException(
          'Expected $credentialProjectionKind, got ${envelope.projection}',
        );
      }
      data = envelope.data;
    } on MakoloApiError catch (error) {
      if (isCurrent() &&
          (error.statusCode == 403 || error.statusCode == 404)) {
        await _markCredentialRetention(accessId, denied: true);
        try {
          await credentialVault.delete(profileId, accessId);
        } on Object {
          // The profile-scoped tombstone still prevents a stale QR reopening.
        }
      }
      rethrow;
    }
    if (!isCurrent()) {
      throw StateError('Superseded AccessCredential response');
    }
    // An explicit Access owner denial may have arrived via another
    // concurrent SyncEngine while this credential GET was in flight.
    if (sync?.isActive == false ||
        (await readSource(accessId)).invalidated ||
        await _hasRevokedBeneficiaryCollection()) {
      await _markCredentialRetention(accessId, denied: true);
      try {
        await credentialVault.delete(profileId, accessId);
      } on Object {
        // Durable tombstone prevents any local presentation.
      }
      throw StateError('Access authority withdrawn before credential receipt');
    }

    final access = _map(data['access']);
    final relationship = _string(data['relationship']);
    final representation = _map(data['representation']);
    final receivedAccessId = _string(access['id']);
    final credentialType = _string(representation['credential_type']);
    final payload = _string(representation['payload']);

    if (receivedAccessId != accessId ||
        relationship != 'beneficiary' ||
        credentialType == null ||
        payload == null) {
      throw const FormatException('Invalid AccessCredential owner payload.');
    }

    final issued = _dateTime(representation['issued_at']);
    final policy = _map(data['offline_presentation']);
    final expiry = _dateTime(policy['expires_at']);
    final checked = _dateTime(policy['observed_at']);
    final canRetain = credentialType == 'qr' &&
        policy['allowed'] == true &&
        policy['scope'] == 'display_only' &&
        expiry != null &&
        checked != null &&
        !expiry.isBefore(checked) &&
        expiry.isAfter(DateTime.now().toUtc());
    var securelyRetained = false;
    if (canRetain && expiry != null && checked != null) {
      try {
        await credentialVault.save(
          profileId,
          RetainedAccessQr(
            accessId: accessId,
            path: path,
            payload: payload,
            issuedAt: issued,
            checkedAt: checked,
            expiresAt: expiry,
          ),
        );
        securelyRetained = true;
      } on Object {
        // Secure-store failure never copies a secret into an unprotected DB.
      }
    } else {
      // The owner has not approved a finite offline presentation. Revoke
      // any older device copy before attempting secure-store deletion.
      if (isCurrent()) {
        await _markCredentialRetention(accessId, denied: true);
        try {
          await credentialVault.delete(profileId, accessId);
        } on Object {
          // The nonsecret tombstone is authoritative for local rendering.
        }
      }
    }
    if (isCurrent() && canRetain) {
      final stillAuthorized = sync?.isActive != false &&
          !(await readSource(accessId)).invalidated &&
          !(await _hasRevokedBeneficiaryCollection());
      if (stillAuthorized && securelyRetained) {
        await _markCredentialRetention(accessId, denied: false);
      } else {
        // Generic Access revocation and secure-vault failure both fail
        // closed, even when the HTTP credential response itself was 200.
        await _markCredentialRetention(accessId, denied: true);
        try {
          await credentialVault.delete(profileId, accessId);
        } on Object {
          // The nonsecret Profile tombstone prevents local disclosure.
        }
      }
    }

    return AccessCredentialData(
      accessId: accessId,
      credentialType: credentialType,
      payload: payload,
      issuedAt: issued,
      checkedAt: checked,
      offlineUntil: canRetain ? expiry : null,
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
