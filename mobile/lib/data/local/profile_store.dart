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
      (row) => row == null ? null : _storedProjection(row),
    );
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
    return row == null ? null : _storedProjection(row);
  }

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

  Future<int> deleteProjection(
    String kind, {
    String resourceKey = '',
  }) {
    return (database.delete(database.projectionSnapshots)
          ..where(
            (row) =>
                row.profileId.equals(profileId) &
                row.projectionKind.equals(kind) &
                row.resourceKey.equals(resourceKey),
          ))
        .go();
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
