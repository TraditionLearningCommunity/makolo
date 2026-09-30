import 'dart:convert';

import 'package:drift/drift.dart';

import '../data/local/makolo_database.dart';
import '../sync/outbox/outbox_repository.dart';

class StoredLocalDraft {
  const StoredLocalDraft({
    required this.draftId,
    required this.owner,
    required this.resourceKind,
    required this.payload,
    required this.updatedAt,
    this.resourceId,
  });

  final String draftId;
  final String owner;
  final String resourceKind;
  final String? resourceId;
  final Map<String, dynamic> payload;
  final DateTime updatedAt;
}

class DraftRepository {
  DraftRepository({
    required this.database,
    required this.outbox,
    required this.profileId,
  });

  final MakoloDatabase database;
  final OutboxRepository outbox;
  final String profileId;

  Future<void> saveLocal({
    required String draftId,
    required String owner,
    required String resourceKind,
    String? resourceId,
    required Map<String, dynamic> payload,
  }) {
    return database
        .into(database.localDrafts)
        .insertOnConflictUpdate(
          LocalDraftsCompanion.insert(
            draftId: draftId,
            profileId: profileId,
            owner: owner,
            resourceKind: resourceKind,
            resourceId: Value(resourceId),
            payloadJson: jsonEncode(payload),
            updatedAt: DateTime.now().toUtc(),
          ),
        );
  }

  Future<StoredLocalDraft?> read({
    required String owner,
    required String resourceKind,
    required String resourceId,
  }) async {
    final query = database.select(database.localDrafts)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.owner.equals(owner) &
            row.resourceKind.equals(resourceKind) &
            row.resourceId.equals(resourceId),
      );
    final row = await query.getSingleOrNull();
    return row == null ? null : _stored(row);
  }

  Stream<StoredLocalDraft?> watch({
    required String owner,
    required String resourceKind,
    required String resourceId,
  }) {
    final query = database.select(database.localDrafts)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.owner.equals(owner) &
            row.resourceKind.equals(resourceKind) &
            row.resourceId.equals(resourceId),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null ? null : _stored(row),
    );
  }

  Future<int> delete({
    required String owner,
    required String resourceKind,
    required String resourceId,
  }) {
    return (database.delete(database.localDrafts)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.owner.equals(owner) &
              row.resourceKind.equals(resourceKind) &
              row.resourceId.equals(resourceId),
        ))
        .go();
  }

  Future<void> saveAndQueue({
    required String draftId,
    required String owner,
    required String resourceKind,
    String? resourceId,
    required Map<String, dynamic> payload,
    required String operationId,
    required String deviceInstanceId,
    required String operationKind,
    required String intentId,
    required ReplayPolicy replayPolicy,
    String? ownerIdempotencyKey,
  }) {
    return database.transaction(() async {
      await saveLocal(
        draftId: draftId,
        owner: owner,
        resourceKind: resourceKind,
        resourceId: resourceId,
        payload: payload,
      );
      await outbox.enqueue(
        operationId: operationId,
        deviceInstanceId: deviceInstanceId,
        operationKind: operationKind,
        owner: owner,
        resourceKind: resourceKind,
        resourceId: resourceId,
        payload: payload,
        intentId: intentId,
        replayPolicy: replayPolicy,
        ownerIdempotencyKey: ownerIdempotencyKey,
      );
    });
  }

  StoredLocalDraft _stored(LocalDraft row) {
    return StoredLocalDraft(
      draftId: row.draftId,
      owner: row.owner,
      resourceKind: row.resourceKind,
      resourceId: row.resourceId,
      payload: jsonDecode(row.payloadJson) as Map<String, dynamic>,
      updatedAt: row.updatedAt,
    );
  }
}
