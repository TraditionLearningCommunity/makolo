import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';

import 'tables.dart';

part 'makolo_database.g.dart';

@DriftDatabase(
  tables: [
    ProjectionSnapshots,
    ResourceIndex,
    SyncSources,
    OutboxOperations,
    LocalDrafts,
    FileRecords,
  ],
)
class MakoloDatabase extends _$MakoloDatabase {
  MakoloDatabase(super.executor);

  factory MakoloDatabase.memory() => MakoloDatabase(NativeDatabase.memory());

  /// Canonical UUID-like Profile IDs retain their established path. Other
  /// identities use a reversible, collision-free encoding: replacing every
  /// punctuation character with '_' could put two Profiles in one database.
  static String profileDirectoryKey(String profileId) {
    if (profileId.isEmpty) {
      throw ArgumentError.value(profileId, 'profileId', 'must not be empty');
    }
    const prefix = '__encoded__';
    if (RegExp(r'^[A-Za-z0-9_-]+
    await directory.create(recursive: true);
    return MakoloDatabase(
      NativeDatabase.createInBackground(
        File('${directory.path}/makolo.sqlite'),
      ),
    );
  }

  @override
  int get schemaVersion => 2;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (m) => m.createAll(),
    onUpgrade: (m, from, to) async {
      if (from < 2) {
        await m.createTable(resourceIndex);
        await m.addColumn(outboxOperations, outboxOperations.lastErrorCode);
      }
    },
    beforeOpen: (details) async {
      await customStatement('PRAGMA foreign_keys = ON');
      await customStatement(
        'CREATE INDEX IF NOT EXISTS outbox_profile_state '
        'ON outbox_operations(profile_id, state, observed_at)',
      );
    },
  );
}
).hasMatch(profileId) &&
        !profileId.startsWith(prefix)) {
      return profileId;
    }
    return '$prefix${base64Url.encode(utf8.encode(profileId)).replaceAll('=', '')}';
  }

  static Future<MakoloDatabase> openForProfile(String profileId) async {
    final base = await getApplicationSupportDirectory();
    final safeProfile = profileDirectoryKey(profileId);
    final directory = Directory('${base.path}/profiles/$safeProfile');
    await directory.create(recursive: true);
    return MakoloDatabase(
      NativeDatabase.createInBackground(
        File('${directory.path}/makolo.sqlite'),
      ),
    );
  }

  @override
  int get schemaVersion => 2;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (m) => m.createAll(),
    onUpgrade: (m, from, to) async {
      if (from < 2) {
        await m.createTable(resourceIndex);
        await m.addColumn(outboxOperations, outboxOperations.lastErrorCode);
      }
    },
    beforeOpen: (details) async {
      await customStatement('PRAGMA foreign_keys = ON');
      await customStatement(
        'CREATE INDEX IF NOT EXISTS outbox_profile_state '
        'ON outbox_operations(profile_id, state, observed_at)',
      );
    },
  );
}
