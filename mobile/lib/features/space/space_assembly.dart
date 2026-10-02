import '../../app/runtime/actor_context_controller.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/sync_engine.dart';
import 'space_repository.dart';

WorkspaceContextRepository buildWorkspaceContextRepository({
  required MakoloDatabase database,
  required ProfileStore store,
  required String profileId,
  required ActorContextController actorContext,
  required SyncEngine? sync,
}) {
  return WorkspaceContextRepository(
    database: database,
    store: store,
    profileId: profileId,
    actorContext: actorContext,
    sync: sync,
  );
}
