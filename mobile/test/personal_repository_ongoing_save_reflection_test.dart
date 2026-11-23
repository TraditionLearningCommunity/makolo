import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

void main() {
  test(
    'confirmed Discovery save only updates matching Ongoing N1 presentation',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-1');
      final repository = PersonalRepository(store);
      final generatedAt = DateTime.utc(2026, 10, 26);
      await store.putProjection(
        kind: 'personal.ongoing',
        schemaVersion: 1,
        sourceGeneratedAt: generatedAt,
        payload: {
          'continuation': {'token': 'opaque'},
          'items': [
            {
              'id': 'continuity-1',
              'source': {'kind': 'journey', 'id': 'j1'},
              'n1': {
                'possibility': {
                  'family': 'service_activity',
                  'id': 'activity-1',
                  'saved_state': 'not_saved',
                  'capabilities': ['save'],
                },
              },
            },
            {
              'id': 'continuity-2',
              'n1': {
                'possibility': {
                  'family': 'opportunity',
                  'id': 'activity-1',
                  'saved_state': 'not_saved',
                },
              },
            },
            {
              'id': 'continuity-3',
              'n1': {
                'possibility': {
                  'family': 'activity',
                  'id': 'activity-2',
                  'saved_state': 'not_saved',
                },
              },
            },
          ],
        },
      );

      await repository.reflectOngoingDiscoverySave(
        activityId: 'activity-1',
        saved: true,
      );
      final snapshot = (await store.readProjection('personal.ongoing'))!;
      final rows = snapshot.payload['items'] as List;
      final first = ((rows[0] as Map)['n1'] as Map)['possibility'] as Map;
      final second = ((rows[1] as Map)['n1'] as Map)['possibility'] as Map;
      final third = ((rows[2] as Map)['n1'] as Map)['possibility'] as Map;
      expect(first['saved_state'], 'saved');
      expect(second['saved_state'], 'not_saved');
      expect(third['saved_state'], 'not_saved');
      expect(first['capabilities'], ['save']);
      expect(snapshot.payload['continuation'], {'token': 'opaque'});
      // Drift/SQLite may restore the same instant in the local timezone.
      expect(snapshot.sourceGeneratedAt, isNotNull);
      expect(snapshot.sourceGeneratedAt!.isAtSameMomentAs(generatedAt), isTrue);

      await repository.reflectOngoingDiscoverySave(
        activityId: 'activity-1',
        saved: false,
      );
      final reverted = (await store.readProjection('personal.ongoing'))!;
      expect(
        ((((reverted.payload['items'] as List)[0] as Map)['n1']
                as Map)['possibility']
            as Map)['saved_state'],
        'not_saved',
      );
    },
  );

  test(
    'no cached Ongoing projection means there is nothing to reflect',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final repository = PersonalRepository(
        ProfileStore(database, 'profile-1'),
      );
      await repository.reflectOngoingDiscoverySave(
        activityId: 'activity-1',
        saved: true,
      );
    },
  );
}
