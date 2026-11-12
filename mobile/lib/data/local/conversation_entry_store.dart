import 'dart:convert';

import 'package:drift/drift.dart';

import 'makolo_database.dart';
import 'profile_store.dart';

/// Indexed owner projections reuse Drift's existing Profile isolation/migrations.
/// The source watermark and a delta page commit in the same local transaction.
class ConversationEntryStore {
  ConversationEntryStore(this.database, this.store, this.profileId) {
    if (store.profileId != profileId || !identical(store.database, database)) {
      throw ArgumentError('Exchange cache requires one Profile scope');
    }
  }

  static const kind = 'conversation.exchange.entry';
  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;

  Future<List<Map<String, dynamic>>> search(
    String pointId,
    String query,
  ) async {
    final rows = await database
        .customSelect(
          "SELECT payload_json FROM projection_snapshots WHERE profile_id=? AND projection_kind=? "
          "AND json_extract(payload_json,'\$.point_id')=? AND json_extract(payload_json,'\$.removed')=0 "
          "AND instr(lower(json_extract(payload_json,'\$.body')),lower(?))>0 "
          "ORDER BY json_extract(payload_json,'\$.sequence') DESC LIMIT 100",
          variables: [
            Variable.withString(profileId),
            Variable.withString(kind),
            Variable.withString(pointId),
            Variable.withString(query),
          ],
          readsFrom: {database.projectionSnapshots},
        )
        .get();
    return _decode(rows);
  }

  Future<List<Map<String, dynamic>>> after(String pointId, int sequence) async {
    final rows = await database
        .customSelect(
          "SELECT payload_json FROM projection_snapshots WHERE profile_id=? AND projection_kind=? "
          "AND json_extract(payload_json,'\$.point_id')=? AND json_extract(payload_json,'\$.sequence')>? "
          "ORDER BY json_extract(payload_json,'\$.sequence') LIMIT 200",
          variables: [
            Variable.withString(profileId),
            Variable.withString(kind),
            Variable.withString(pointId),
            Variable.withInt(sequence),
          ],
          readsFrom: {database.projectionSnapshots},
        )
        .get();
    return [
      for (final row in rows)
        jsonDecode(row.read<String>('payload_json')) as Map<String, dynamic>,
    ];
  }

  Selectable<QueryRow> _query(
    String pointId, {
    int limit = 100,
    int? before,
  }) => database.customSelect(
    'SELECT payload_json FROM projection_snapshots '
    'WHERE profile_id = ? AND projection_kind = ? '
    "AND json_extract(payload_json, '\$.point_id') = ? "
    '${before == null ? '' : "AND json_extract(payload_json, '\$.sequence') < ? "}'
    "ORDER BY json_extract(payload_json, '\$.sequence') DESC LIMIT ?",
    variables: [
      Variable.withString(profileId),
      Variable.withString(kind),
      Variable.withString(pointId),
      if (before != null) Variable.withInt(before),
      Variable.withInt(limit),
    ],
    readsFrom: {database.projectionSnapshots},
  );

  List<Map<String, dynamic>> _decode(List<QueryRow> rows) => rows.reversed
      .map(
        (row) =>
            jsonDecode(row.read<String>('payload_json'))
                as Map<String, dynamic>,
      )
      .toList(growable: false);

  Future<List<Map<String, dynamic>>> read(
    String pointId, {
    int limit = 100,
    int? before,
  }) async =>
      _decode(await _query(pointId, limit: limit, before: before).get());

  Stream<List<Map<String, dynamic>>> watch(String pointId, {int limit = 100}) =>
      _query(pointId, limit: limit).watch().map(_decode);

  Future<int> version(String pointId) async {
    final row =
        await (database.select(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.equals('exchange:$pointId'),
            ))
            .getSingleOrNull();
    return int.tryParse(row?.cursor ?? '') ?? 0;
  }

  Future<String?> scope(String pointId) async =>
      (await store.readProjection(
            'conversation.exchange.scope',
            resourceKey: pointId,
          ))?.payload['scope']
          as String?;

  Future<void> setScope(String pointId, String scope) => store.putProjection(
    kind: 'conversation.exchange.scope',
    resourceKey: pointId,
    schemaVersion: 1,
    payload: {'scope': scope},
  );

  Future<void> apply(
    String pointId,
    List<Map<String, dynamic>> rows, {
    int? nextVersion,
  }) => database.transaction(() async {
    for (final row in rows) {
      final id = row['id'];
      if (id is! String ||
          row['point_id'] != pointId ||
          row['sequence'] is! int ||
          row['last_change_version'] is! int) {
        throw const FormatException('Invalid Exchange owner projection');
      }
      final old = await store.readProjection(kind, resourceKey: '$pointId:$id');
      if (old != null &&
          (old.payload['last_change_version'] as int) >
              (row['last_change_version'] as int))
        continue;
      await store.putProjection(
        kind: kind,
        resourceKey: '$pointId:$id',
        schemaVersion: 1,
        payload: row,
      );
    }
    if (nextVersion != null) {
      final current = await version(pointId);
      if (nextVersion < current)
        throw const FormatException('Exchange watermark regressed');
      await database
          .into(database.syncSources)
          .insertOnConflictUpdate(
            SyncSourcesCompanion.insert(
              profileId: profileId,
              sourceKey: 'exchange:$pointId',
              route: 'api/v1/conversations/points/$pointId/entries/sync/',
              cursor: Value('$nextVersion'),
              lastSuccessAt: Value(DateTime.now().toUtc()),
            ),
          );
    }
  });

  Future<void> revoke(String pointId) => database.transaction(() async {
    await store.deleteProjection(
      'conversation.exchange.scope',
      resourceKey: pointId,
    );
    await (database.delete(database.projectionSnapshots)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.projectionKind.equals(kind) &
              row.resourceKey.like('$pointId:%'),
        ))
        .go();
    await (database.delete(database.syncSources)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.sourceKey.equals('exchange:$pointId'),
        ))
        .go();
  });
}
