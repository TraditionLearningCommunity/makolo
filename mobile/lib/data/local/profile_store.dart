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
      (rows) => rows.map(_usableProjection).whereType<StoredProjection>().toList(growable: false),
    );
  }

  Future<List<StoredProjection>> readProjections(String kind) async {
    final query = database.select(database.projectionSnapshots)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.projectionKind.equals(kind),
      );
    final rows = await query.get();
    return rows.map(_usableProjection).whereType<StoredProjection>().toList(growable: false);
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
    if (expires != null &&
        !DateTime.now().toUtc().isBefore(expires.toUtc())) return null;
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
