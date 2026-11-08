import 'package:drift/drift.dart';

import '../data/local/makolo_database.dart';
import 'freshness.dart';

class OwnerSourceState {
  const OwnerSourceState({
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

  static const unknown = OwnerSourceState();
}

Stream<OwnerSourceState> watchOwnerSourceState({
  required MakoloDatabase database,
  required String profileId,
  required String sourceKey,
}) {
  final query = database.select(database.syncSources)
    ..where(
      (row) =>
          row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
    );
  return query.watchSingleOrNull().map(
    (row) => row == null
        ? OwnerSourceState.unknown
        : OwnerSourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          ),
  );
}

Future<OwnerSourceState> readOwnerSourceState({
  required MakoloDatabase database,
  required String profileId,
  required String sourceKey,
}) async {
  final query = database.select(database.syncSources)
    ..where(
      (row) =>
          row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
    );
  final row = await query.getSingleOrNull();
  return row == null
      ? OwnerSourceState.unknown
      : OwnerSourceState(
          lastSuccessAt: row.lastSuccessAt,
          invalidated: row.invalidated,
          lastErrorCode: row.lastErrorCode,
        );
}
