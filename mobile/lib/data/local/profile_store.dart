import 'dart:convert';

import 'package:drift/drift.dart';

import 'makolo_database.dart';

class StoredProjection {
  const StoredProjection({
    required this.kind,
    required this.schemaVersion,
    required this.payload,
    required this.receivedAt,
  });

  final String kind;
  final int schemaVersion;
  final Map<String, dynamic> payload;
  final DateTime receivedAt;
}

class ProfileStore {
  ProfileStore(this.database, this.profileId);

  final MakoloDatabase database;
  final String profileId;

  Stream<StoredProjection?> watchProjection(String kind) {
    final query = database.select(database.projectionSnapshots)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.projectionKind.equals(kind) &
            row.resourceKey.equals(''),
      );
    return query.watchSingleOrNull().map(
          (row) => row == null
              ? null
              : StoredProjection(
                  kind: row.projectionKind,
                  schemaVersion: row.schemaVersion,
                  payload:
                      jsonDecode(row.payloadJson) as Map<String, dynamic>,
                  receivedAt: row.receivedAt,
                ),
        );
  }

  Future<StoredProjection?> readProjection(String kind) async {
    final query = database.select(database.projectionSnapshots)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.projectionKind.equals(kind) &
            row.resourceKey.equals(''),
      );
    final row = await query.getSingleOrNull();
    if (row == null) return null;
    return StoredProjection(
      kind: row.projectionKind,
      schemaVersion: row.schemaVersion,
      payload: jsonDecode(row.payloadJson) as Map<String, dynamic>,
      receivedAt: row.receivedAt,
    );
  }

  Future<void> putProjection({
    required String kind,
    required int schemaVersion,
    required Map<String, dynamic> payload,
    DateTime? sourceGeneratedAt,
  }) async {
    final now = DateTime.now().toUtc();
    await database.into(database.projectionSnapshots).insertOnConflictUpdate(
          ProjectionSnapshotsCompanion.insert(
            profileId: profileId,
            projectionKind: kind,
            schemaVersion: schemaVersion,
            payloadJson: jsonEncode(payload),
            receivedAt: now,
            sourceGeneratedAt: Value(sourceGeneratedAt),
            lastVerifiedOnlineAt: Value(now),
          ),
        );
  }
}
