import 'dart:convert';

import 'package:drift/drift.dart';

import '../data/local/makolo_database.dart';
import '../sync/outbox/outbox_repository.dart';

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
    return database.into(database.localDrafts).insertOnConflictUpdate(
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
}
