import '../data/local/profile_store.dart';

class PersonalRepository {
  PersonalRepository(this.store);

  final ProfileStore store;

  Stream<StoredProjection?> watchNow() =>
      store.watchProjection('personal.now');

  Stream<StoredProjection?> watchOngoing() =>
      store.watchProjection('personal.ongoing');

  Stream<StoredProjection?> watchMe() =>
      store.watchProjection('personal.me');
}
