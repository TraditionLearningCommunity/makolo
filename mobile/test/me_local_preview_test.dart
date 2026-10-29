import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
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
      MeLocalPreview.forProfile(snapshot, 'owner-a')
          ?.collection('considerations', 'interests')?['items'],
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
      _snapshot(profileId: 'owner-a', data: {
        'considerations': {
          'interests': {'count': 4},
          'bookmarks': {'items': 'malformed'},
          'open_to': {'items': <Object>[]},
        },
      }),
      'owner-a',
    )!;

    expect(preview.collection('considerations', 'interests'), isNull);
    expect(preview.collection('considerations', 'bookmarks'), isNull);
    expect(preview.collection('considerations', 'open_to')?['items'], isEmpty);
  });

  test('cached bookmark rows preserve the owner-backed activity identity', () {
    final preview = MeLocalPreview.forProfile(
      _snapshot(profileId: 'owner-a', data: {
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
      }),
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
}
