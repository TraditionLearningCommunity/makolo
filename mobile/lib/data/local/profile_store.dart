import 'dart:convert';

import 'package:drift/drift.dart';

import 'makolo_database.dart';

class StoredProjection {
  const StoredProjection({
    required this.kind,
    required this.schemaVersion,
    required this.payload,
    required this.receivedAt,
    this.resourceKey = '',
    this.sourceGeneratedAt,
    this.sourceUpdatedAt,
    this.lastVerifiedOnlineAt,
    this.freshUntil,
    this.expiresAt,
    this.freshnessPolicyId,
  });

  final String kind;
  final String resourceKey;
  final int schemaVersion;
  final Map<String, dynamic> payload;
  final DateTime receivedAt;
  final DateTime? sourceGeneratedAt;
  final DateTime? sourceUpdatedAt;
  final DateTime? lastVerifiedOnlineAt;
  final DateTime? freshUntil;
  final DateTime? expiresAt;
  final String? freshnessPolicyId;
}

/// A searchable pointer to an already acquired owner-backed detail.
/// This index never grants authority or outlives its underlying projection.
class IndexedResource {
  const IndexedResource({
    required this.kind,
    required this.id,
    required this.projectionKind,
    this.label,
  });

  final String kind;
  final String id;
  final String projectionKind;
  final String? label;
}

class ProfileStore {
  ProfileStore(this.database, this.profileId);

  final MakoloDatabase database;
  final String profileId;

  Stream<StoredProjection?> watchProjection(
    String kind, {
    String resourceKey = '',
  }) {
    final query = database.select(database.projectionSnapshots)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.projectionKind.equals(kind) &
            row.resourceKey.equals(resourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null ? null : _usableProjection(row),
    );
  }

  Stream<List<StoredProjection>> watchProjections(String kind) {
    final query = database.select(database.projectionSnapshots)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.projectionKind.equals(kind),
      );
    return query.watch().map(
      (rows) => rows
          .map(_usableProjection)
          .whereType<StoredProjection>()
          .toList(growable: false),
    );
  }

  Future<List<StoredProjection>> readProjections(String kind) async {
    final query = database.select(database.projectionSnapshots)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.projectionKind.equals(kind),
      );
    final rows = await query.get();
    return rows
        .map(_usableProjection)
        .whereType<StoredProjection>()
        .toList(growable: false);
  }

  Future<StoredProjection?> readProjection(
    String kind, {
    String resourceKey = '',
  }) async {
    final query = database.select(database.projectionSnapshots)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.projectionKind.equals(kind) &
            row.resourceKey.equals(resourceKey),
      );
    final row = await query.getSingleOrNull();
    return row == null ? null : _usableProjection(row);
  }

  /// References are not independent facts: only a retained, unexpired
  /// keyed owner projection may make a resource searchable.
  Future<void> putResourceReference({
    required String resourceKind,
    required String resourceId,
    required String projectionKind,
    String? label,
  }) async {
    if (resourceKind.trim().isEmpty ||
        resourceId.trim().isEmpty ||
        projectionKind.trim().isEmpty) {
      throw ArgumentError('Indexed resource identity must not be empty');
    }
    await database
        .into(database.resourceIndex)
        .insertOnConflictUpdate(
          ResourceIndexCompanion.insert(
            profileId: profileId,
            resourceKind: resourceKind,
            resourceId: resourceId,
            projectionKind: projectionKind,
            label: Value(label),
            updatedAt: DateTime.now().toUtc(),
          ),
        );
  }

  /// The join prevents an index pointer from presenting a revoked, removed
  /// or expired owner snapshot as locally available. No new business truth.
  Selectable<QueryRow> _knownResourceQuery({
    String search = '',
    int limit = 100,
  }) {
    if (limit < 1 || limit > 500) {
      throw ArgumentError.value(limit, 'limit', 'must be between 1 and 500');
    }
    final needle = search.trim();
    return database.customSelect(
      '''
      SELECT r.resource_kind, r.resource_id, r.projection_kind, r.label
      FROM resource_index AS r
      INNER JOIN projection_snapshots AS p
        ON p.profile_id = r.profile_id
        AND p.projection_kind = r.projection_kind
        AND p.resource_key = r.resource_id
      WHERE r.profile_id = ?
        AND (p.expires_at IS NULL OR p.expires_at > ?)
        AND (? = '' OR instr(lower(coalesce(r.label, '')), lower(?)) > 0)
      ORDER BY r.updated_at DESC, r.resource_kind, r.resource_id
      LIMIT ?
      ''',
      variables: [
        Variable.withString(profileId),
        Variable.withInt(DateTime.now().toUtc().millisecondsSinceEpoch ~/ 1000),
        Variable.withString(needle),
        Variable.withString(needle),
        Variable.withInt(limit),
      ],
      readsFrom: {database.resourceIndex, database.projectionSnapshots},
    );
  }

  List<IndexedResource> _readResourceRows(List<QueryRow> rows) => rows
      .map(
        (row) => IndexedResource(
          kind: row.read<String>('resource_kind'),
          id: row.read<String>('resource_id'),
          projectionKind: row.read<String>('projection_kind'),
          label: row.readNullable<String>('label'),
        ),
      )
      .toList(growable: false);

  Future<List<IndexedResource>> readKnownResources({
    String search = '',
    int limit = 100,
  }) async => _readResourceRows(
    await _knownResourceQuery(search: search, limit: limit).get(),
  );

  /// Updates when either an indexed pointer or its owner projection changes.
  /// Time-only expiry is evaluated again when the query is resubscribed
  /// (for example after resuming the application).
  Stream<List<IndexedResource>> watchKnownResources({
    String search = '',
    int limit = 100,
  }) => _knownResourceQuery(
    search: search,
    limit: limit,
  ).watch().map(_readResourceRows);

  // Raw server pages and owner projections are kept intact. A bounded
  // reserve of not-yet-presented Discovery items must be maintained at item
  // level, not by evicting raw cursor pages or their dependencies.
  Future<void> putProjection({
    required String kind,
    String resourceKey = '',
    required int schemaVersion,
    required Map<String, dynamic> payload,
    DateTime? receivedAt,
    DateTime? sourceGeneratedAt,
    DateTime? sourceUpdatedAt,
    DateTime? lastVerifiedOnlineAt,
    DateTime? freshUntil,
    DateTime? expiresAt,
    String? freshnessPolicyId,
  }) async {
    if (kind == 'personal.access.credential') {
      throw const FormatException(
        'AccessCredential secrets belong only in the protected credential vault',
      );
    }
    final observedAt = (receivedAt ?? DateTime.now()).toUtc();
    await database
        .into(database.projectionSnapshots)
        .insertOnConflictUpdate(
          ProjectionSnapshotsCompanion.insert(
            profileId: profileId,
            projectionKind: kind,
            resourceKey: Value(resourceKey),
            schemaVersion: schemaVersion,
            payloadJson: jsonEncode(payload),
            receivedAt: observedAt,
            sourceGeneratedAt: Value(sourceGeneratedAt?.toUtc()),
            sourceUpdatedAt: Value(sourceUpdatedAt?.toUtc()),
            lastVerifiedOnlineAt: Value(
              (lastVerifiedOnlineAt ?? observedAt).toUtc(),
            ),
            freshUntil: Value(freshUntil?.toUtc()),
            expiresAt: Value(expiresAt?.toUtc()),
            freshnessPolicyId: Value(freshnessPolicyId),
          ),
        );
  }

  Future<int> deleteProjection(String kind, {String resourceKey = ''}) {
    return (database.delete(database.projectionSnapshots)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.projectionKind.equals(kind) &
              row.resourceKey.equals(resourceKey),
        ))
        .go();
  }

  /// Remove all snapshots of one derived kind in this Profile only. A server
  /// refusal of a Discovery owner invalidates its formerly composed windows;
  /// it must not erase the other Profile's local data.
  Future<int> deleteProjectionsOfKind(String kind) {
    return (database.delete(database.projectionSnapshots)..where(
          (row) =>
              row.profileId.equals(profileId) & row.projectionKind.equals(kind),
        ))
        .go();
  }

  /// Expired owner snapshots cannot be revived merely by a transport failure.
  /// Cleanup is scoped to this Profile and never touches user-owned drafts.
  Future<int> purgeExpiredProjections() async {
    final cutoff = DateTime.now().toUtc();
    return database.transaction(() async {
      final removed =
          await (database.delete(database.projectionSnapshots)..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.expiresAt.isSmallerOrEqualValue(cutoff),
              ))
              .go();
      // ResourceIndex is a rebuildable pointer, never independent owner
      // knowledge. Compact only references whose exact owner snapshot has
      // disappeared. Drafts, FileRecords and all other Profiles are untouched.
      await database.customUpdate(
        '''
        DELETE FROM resource_index
        WHERE profile_id = ?
          AND NOT EXISTS (
            SELECT 1 FROM projection_snapshots AS p
            WHERE p.profile_id = resource_index.profile_id
              AND p.projection_kind = resource_index.projection_kind
              AND p.resource_key = resource_index.resource_id
          )
        ''',
        variables: [Variable.withString(profileId)],
        updates: {database.resourceIndex},
      );
      return removed;
    });
  }

  /// Keep bounded reconstructible projections without touching the raw owner
  /// records of other kinds or Profiles. The active page and its first lot
  /// can be protected by the caller during the rotation.
  Future<void> pruneProjectionsOfKind(
    String kind, {
    required int retain,
    Set<String> protectResourceKeys = const {},
  }) async {
    if (retain < 0) throw ArgumentError.value(retain, 'retain');
    final rows = await readProjections(kind);
    rows.sort((a, b) {
      final newerFirst = b.receivedAt.compareTo(a.receivedAt);
      return newerFirst != 0
          ? newerFirst
          : a.resourceKey.compareTo(b.resourceKey);
    });
    var kept = 0;
    for (final projection in rows) {
      if (protectResourceKeys.contains(projection.resourceKey)) continue;
      if (kept++ >= retain) {
        await deleteProjection(kind, resourceKey: projection.resourceKey);
      }
    }
  }

  /// Hard expiry is different from refresh freshness. Offline readers may
  /// show an older observation after a timeout, but never a time-expired
  /// permission or capability-bearing projection.
  StoredProjection? _usableProjection(ProjectionSnapshot row) {
    final expires = row.expiresAt;
    if (expires != null && !DateTime.now().toUtc().isBefore(expires.toUtc())) {
      return null;
    }
    return _storedProjection(row);
  }

  StoredProjection _storedProjection(ProjectionSnapshot row) {
    return StoredProjection(
      kind: row.projectionKind,
      resourceKey: row.resourceKey,
      schemaVersion: row.schemaVersion,
      payload: jsonDecode(row.payloadJson) as Map<String, dynamic>,
      receivedAt: row.receivedAt,
      sourceGeneratedAt: row.sourceGeneratedAt,
      sourceUpdatedAt: row.sourceUpdatedAt,
      lastVerifiedOnlineAt: row.lastVerifiedOnlineAt,
      freshUntil: row.freshUntil,
      expiresAt: row.expiresAt,
      freshnessPolicyId: row.freshnessPolicyId,
    );
  }
}
