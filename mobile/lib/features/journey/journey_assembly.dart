import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/sync_engine.dart';
import 'journey_repository.dart';

JourneyRepository buildJourneyRepository({
  required MakoloDatabase database,
  required ProfileStore store,
  required String profileId,
  required SyncEngine? sync,
}) => JourneyRepository(
  database: database,
  store: store,
  profileId: profileId,
  sync: sync,
);
