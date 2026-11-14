import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

Map<String, dynamic> root(String token) => {
  'surface': 'ongoing_me',
  'actor': {'type': 'profile', 'id': 'profile-a'},
  'items': [
    {'id': 'journey-a', 'kind': 'journey', 'title': 'Démarche A'},
  ],
  'continuation': {'state': 'more', 'token': token},
};

void main() {
  test(
    'Ongoing keeps received continuation after equivalent root refresh',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      await store.putProjection(
        kind: 'personal.ongoing',
        schemaVersion: 1,
        payload: root('opaque-cursor'),
        receivedAt: DateTime.utc(2026, 11, 3),
      );
      await store.putProjection(
        kind: PersonalRepository.ongoingContinuationKind,
        schemaVersion: 1,
        payload: {
          'actor_id': 'profile-a',
          'root_token': 'opaque-cursor',
          'first_keys': ['journey-a'],
          'rows': [
            {'id': 'journey-a', 'kind': 'journey'},
            {'id': 'journey-b', 'kind': 'journey', 'title': 'Démarche B'},
          ],
          'continuation': {'state': 'end'},
        },
      );
      final personal = PersonalRepository(store);
      var known = await personal.watchOngoing().first;
      expect(known?.payload['items'], hasLength(2));

      await store.putProjection(
        kind: 'personal.ongoing',
        schemaVersion: 1,
        payload: root('opaque-cursor'),
        receivedAt: DateTime.utc(2026, 11, 4),
      );
      known = await personal.watchOngoing().first;
      expect(known?.payload['items'], hasLength(2));
      expect((known?.payload['continuation'] as Map)['state'], 'end');

      await store.putProjection(
        kind: 'personal.ongoing',
        schemaVersion: 1,
        payload: root('different-owner-cursor'),
        receivedAt: DateTime.utc(2026, 11, 4, 12),
      );
      known = await personal.watchOngoing().first;
      expect(known?.payload['items'], hasLength(1));
      final other = PersonalRepository(ProfileStore(db, 'profile-b'));
      expect(await other.watchOngoing().first, isNull);
    },
  );
}
