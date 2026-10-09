import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/sync_engine.dart';
import 'preparation_repository.dart';

class PreparationAssembly {
  const PreparationAssembly({
    required this.requirements,
    required this.resources,
  });

  final RequirementRepository requirements;
  final PreparationResourcesRepository resources;
}

PreparationAssembly buildPreparationAssembly({
  required MakoloDatabase database,
  required ProfileStore store,
  required String profileId,
  required MakoloApiClient? api,
  required SyncEngine? sync,
}) => PreparationAssembly(
  requirements: RequirementRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  ),
  resources: PreparationResourcesRepository(
    database: database,
    store: store,
    profileId: profileId,
    api: api,
    sync: sync,
  ),
);
