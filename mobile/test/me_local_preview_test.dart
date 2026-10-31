import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';
import 'package:makolo_mobile/features/me/me_local_preview.dart';

StoredProjection _snapshot({
  required String profileId,
  required Map<String, dynamic> data,
  String kind = 'personal.me',
}) => StoredProjection(
  kind: kind,
  schemaVersion: 1,
  receivedAt: DateTime.utc(2026, 10, 29),
  payload: {
    'actor': {'type': 'profile', 'id': profileId},
    ...data,
  },
);

void main() {
  test(
    'Passport snapshots persist per profile and exact presentation variant',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final owner = ProfileStore(database, 'owner-a');
      final another = ProfileStore(database, 'owner-b');
      const publicKey = 'variant=public';
      const privateKey = 'variant=complete';
      await owner.putProjection(
        kind: 'personal.me.passport',
        resourceKey: privateKey,
        schemaVersion: 1,
        payload: {
          'variant': 'complete',
          'identity': {'display_name': 'Profil A'},
          'private_details': {'phone': 'PRIVATE-OWNER-ONLY'},
        },
      );
      await owner.putProjection(
        kind: 'personal.me.passport',
        resourceKey: publicKey,
        schemaVersion: 1,
        payload: {
          'variant': 'public',
          'identity': {'display_name': 'Profil A'},
        },
      );
      final complete = await owner.readProjection(
        'personal.me.passport',
        resourceKey: privateKey,
      );
      final public = await owner.readProjection(
        'personal.me.passport',
        resourceKey: publicKey,
      );
      expect(complete?.payload['private_details'], isNotNull);
      expect(public?.payload.containsKey('private_details'), isFalse);
      expect(
        await another.readProjection(
          'personal.me.passport',
          resourceKey: privateKey,
        ),
        isNull,
      );
    },
  );

  test('an offline Me preview belongs only to its current profile', () {
    final snapshot = _snapshot(
      profileId: 'owner-a',
      data: {
        'identity': {'display_name': 'Profil A'},
        'considerations': {
          'interests': {
            'items': [
              {'id': 'topic-a', 'label': 'Éducation'},
            ],
          },
        },
      },
    );

    expect(MeLocalPreview.forProfile(snapshot, 'owner-b'), isNull);
    expect(
      MeLocalPreview.forProfile(snapshot, 'owner-a')?.identity?['display_name'],
      'Profil A',
    );
    expect(
      MeLocalPreview.forProfile(
        snapshot,
        'owner-a',
      )?.collection('considerations', 'interests')?['items'],
      isNotEmpty,
    );
    expect(
      MeLocalPreview.forProfile(
        _snapshot(profileId: 'owner-a', data: {}, kind: 'personal.now'),
        'owner-a',
      ),
      isNull,
    );
  });

  test('unknown collections never become authoritative empty ones', () {
    final preview = MeLocalPreview.forProfile(
      _snapshot(
        profileId: 'owner-a',
        data: {
          'considerations': {
            'interests': {'count': 4},
            'bookmarks': {'items': 'malformed'},
            'open_to': {'items': <Object>[]},
          },
        },
      ),
      'owner-a',
    )!;

    expect(preview.collection('considerations', 'interests'), isNull);
    expect(preview.collection('considerations', 'bookmarks'), isNull);
    expect(preview.collection('considerations', 'open_to')?['items'], isEmpty);
  });

  test('cached bookmark rows preserve the owner-backed activity identity', () {
    final preview = MeLocalPreview.forProfile(
      _snapshot(
        profileId: 'owner-a',
        data: {
          'considerations': {
            'bookmarks': {
              'items': [
                {
                  'id': 'saved-1',
                  'activity': {'id': 'activity-1', 'title': 'Une possibilité'},
                },
              ],
              'has_more': true,
              'next_offset': 1,
            },
          },
        },
      ),
      'owner-a',
    )!;
    final bookmarks = preview.collection('considerations', 'bookmarks')!;
    expect((bookmarks['items'] as List).length, 1);
    expect(
      ((bookmarks['items'] as List).single as Map)['activity']['id'],
      'activity-1',
    );
    expect(bookmarks['has_more'], isTrue);
  });
  test(
    'confirmed owner changes update only the matching profile snapshot',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final owner = ProfileStore(database, 'owner-a');
      final other = ProfileStore(database, 'owner-b');
      Map<String, dynamic> initial(String id) => {
        'actor': {'type': 'profile', 'id': id},
        'considerations': {
          'interests': {
            'items': [
              {'id': 'old', 'label': 'Ancien'},
            ],
            'count': 1,
          },
          'open_to': {'items': <Object>[], 'count': 0},
          'bookmarks': {
            'items': [
              {
                'id': 'saved-1',
                'activity': {'id': 'activity-1', 'title': 'Activité'},
              },
              {
                'id': 'saved-2',
                'activity': {'id': 'activity-2', 'title': 'Autre'},
              },
            ],
            'count': 2,
          },
        },
      };
      for (final record in [owner, other]) {
        await record.putProjection(
          kind: 'personal.me',
          schemaVersion: 1,
          payload: initial(record.profileId),
        );
      }
      final repository = PersonalRepository(owner);
      await repository.reflectMeConfirmedChoices(
        settings: {
          'interests': ['new'],
          'selected_topics': [
            {'id': 'new', 'label': 'Nouveau'},
          ],
          'open_to': ['collaborate'],
          'open_to_options': [
            {'id': 'collaborate', 'label': 'Collaborer'},
          ],
        },
      );
      await repository.reflectMeBookmarkRemoved(activityId: 'activity-1');
      final local = MeLocalPreview.forProfile(
        await owner.readProjection('personal.me'),
        owner.profileId,
      )!;
      expect(
        (local.collection('considerations', 'interests')!['items'] as List)
            .single['id'],
        'new',
      );
      expect(
        (local.collection('considerations', 'open_to')!['items'] as List)
            .single['id'],
        'collaborate',
      );
      final saved = local.collection('considerations', 'bookmarks')!;
      expect(saved['count'], 1);
      expect(
        ((saved['items'] as List).single['activity'] as Map)['id'],
        'activity-2',
      );

      final untouched = MeLocalPreview.forProfile(
        await other.readProjection('personal.me'),
        other.profileId,
      )!;
      expect(
        (untouched.collection('considerations', 'interests')!['items'] as List)
            .single['id'],
        'old',
      );
      expect(
        (untouched.collection('considerations', 'bookmarks')!['items'] as List)
            .length,
        2,
      );
    },
  );
}
