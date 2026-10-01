import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/sync_engine.dart';
import 'day_of_repository.dart';

DayOfRepository buildDayOfRepository({
  required MakoloDatabase database,
  required ProfileStore store,
  required String profileId,
  required SyncEngine? sync,
}) => DayOfRepository(
  database: database,
  store: store,
  profileId: profileId,
  sync: sync,
);
