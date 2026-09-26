import 'package:drift/drift.dart';

class ProjectionSnapshots extends Table {
  TextColumn get profileId => text()();
  TextColumn get projectionKind => text()();
  TextColumn get resourceKey => text().withDefault(const Constant(''))();
  IntColumn get schemaVersion => integer()();
  TextColumn get payloadJson => text()();
  DateTimeColumn get receivedAt => dateTime()();
  DateTimeColumn get sourceGeneratedAt => dateTime().nullable()();
  DateTimeColumn get sourceUpdatedAt => dateTime().nullable()();
  DateTimeColumn get lastVerifiedOnlineAt => dateTime().nullable()();
  DateTimeColumn get freshUntil => dateTime().nullable()();
  DateTimeColumn get expiresAt => dateTime().nullable()();
  TextColumn get freshnessPolicyId => text().nullable()();

  @override
  Set<Column<Object>> get primaryKey => {
    profileId,
    projectionKind,
    resourceKey,
  };
}

class ResourceIndex extends Table {
  TextColumn get profileId => text()();
  TextColumn get resourceKind => text()();
  TextColumn get resourceId => text()();
  TextColumn get label => text().nullable()();
  TextColumn get projectionKind => text()();
  TextColumn get navigationJson => text().nullable()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {profileId, resourceKind, resourceId};
}

class SyncSources extends Table {
  TextColumn get profileId => text()();
  TextColumn get sourceKey => text()();
  TextColumn get route => text()();
  IntColumn get schemaVersionSeen => integer().nullable()();
  DateTimeColumn get lastSuccessAt => dateTime().nullable()();
  DateTimeColumn get generatedAtSeen => dateTime().nullable()();
  TextColumn get cursor => text().nullable()();
  BoolColumn get invalidated => boolean().withDefault(const Constant(false))();
  TextColumn get lastErrorCode => text().nullable()();

  @override
  Set<Column<Object>> get primaryKey => {profileId, sourceKey};
}

class OutboxOperations extends Table {
  TextColumn get operationId => text()();
  TextColumn get profileId => text()();
  TextColumn get deviceInstanceId => text()();
  TextColumn get operationKind => text()();
  TextColumn get owner => text()();
  TextColumn get resourceKind => text().nullable()();
  TextColumn get resourceId => text().nullable()();
  TextColumn get payloadJson => text()();
  TextColumn get dependencyIdsJson =>
      text().withDefault(const Constant('[]'))();
  TextColumn get sequenceGroup => text().nullable()();
  DateTimeColumn get observedAt => dateTime()();
  TextColumn get state => text().withDefault(const Constant('queued'))();
  IntColumn get attempts => integer().withDefault(const Constant(0))();
  DateTimeColumn get nextRetryAt => dateTime().nullable()();
  TextColumn get intentId => text()();
  TextColumn get ownerIdempotencyKey => text().nullable()();
  TextColumn get replayPolicy => text()();
  TextColumn get lastErrorCode => text().nullable()();

  @override
  Set<Column<Object>> get primaryKey => {operationId};
}

class LocalDrafts extends Table {
  TextColumn get draftId => text()();
  TextColumn get profileId => text()();
  TextColumn get owner => text()();
  TextColumn get resourceKind => text()();
  TextColumn get resourceId => text().nullable()();
  TextColumn get payloadJson => text()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {draftId};
}

class FileRecords extends Table {
  TextColumn get fileId => text()();
  TextColumn get profileId => text()();
  TextColumn get owner => text()();
  TextColumn get localPath => text()();
  TextColumn get purpose => text()();
  TextColumn get sensitivity => text()();
  BoolColumn get reconstructible =>
      boolean().withDefault(const Constant(false))();
  DateTimeColumn get createdAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {fileId};
}
