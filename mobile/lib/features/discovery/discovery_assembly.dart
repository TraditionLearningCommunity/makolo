import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/sync_engine.dart';
import 'discovery_repository.dart';

DiscoveryRepository? buildDiscoveryRepository({
  required MakoloDatabase database,
  required ProfileStore store,
  required String profileId,
  required MakoloApiClient? api,
  required SyncEngine? sync,
}) {
  if (api == null) return null;
  return DiscoveryRepository(
    database: database,
    store: store,
    profileId: profileId,
    api: api,
    sync: sync,
  );
}
