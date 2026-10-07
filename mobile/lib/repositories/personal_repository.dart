import '../data/local/profile_store.dart';
import '../sync/owner_source_state.dart';

class PersonalRepository {
  PersonalRepository(this.store);

  final ProfileStore store;

  Stream<StoredProjection?> watchNow() => store.watchProjection('personal.now');

  Stream<OwnerSourceState> watchNowSource() => watchOwnerSourceState(
    database: store.database,
    profileId: store.profileId,
    sourceKey: 'personal.now',
  );

  Stream<StoredProjection?> watchOngoing() =>
      store.watchProjection('personal.ongoing');

  Stream<OwnerSourceState> watchOngoingSource() => watchOwnerSourceState(
    database: store.database,
    profileId: store.profileId,
    sourceKey: 'personal.ongoing',
  );

  Stream<StoredProjection?> watchMe() => store.watchProjection('personal.me');

  Stream<OwnerSourceState> watchMeSource() => watchOwnerSourceState(
    database: store.database,
    profileId: store.profileId,
    sourceKey: 'personal.me',
  );
}
