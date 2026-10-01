import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/sync_engine.dart';
import 'conversation_repository.dart';
import 'history_repository.dart';
import 'objective_repository.dart';

class ContinuityAssembly {
  const ContinuityAssembly({
    required this.objectives,
    required this.history,
    required this.conversations,
  });

  final ObjectiveRepository objectives;
  final HistoryRepository history;
  final ConversationRepository conversations;
}

ContinuityAssembly buildContinuityAssembly({
  required MakoloDatabase database,
  required ProfileStore store,
  required String profileId,
  required SyncEngine? sync,
}) => ContinuityAssembly(
  objectives: ObjectiveRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  ),
  history: HistoryRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  ),
  conversations: ConversationRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  ),
);
