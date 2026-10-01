import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/sync_engine.dart';
import 'access_repository.dart';

AccessRepository buildAccessRepository({
  required MakoloDatabase database,
  required ProfileStore store,
  required String profileId,
  required MakoloApiClient? api,
  required SyncEngine? sync,
}) => AccessRepository(
  database: database,
  store: store,
  profileId: profileId,
  api: api,
  sync: sync,
);
