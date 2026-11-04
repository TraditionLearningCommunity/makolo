import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';
import 'package:makolo_mobile/sync/sync_source.dart';

import 'dio_testing.dart';
import 'fakes.dart';

Map<String, dynamic> envelope(
  String kind,
  String title, {
  String generated = '2026-11-04T08:00:00Z',
  String? actor,
}) => {
  'meta': {
    'projection': kind,
    'schema_version': 1,
    'scope': 'personal',
    'generated_at': generated,
  },
  'data': {
    'title': title,
    if (actor != null) 'actor': {'type': 'profile', 'id': actor},
  },
};

MakoloApiClient clientFor(MockClient mock) => MakoloApiClient(
  baseUri: Uri.parse('https://makolo.invalid/'),
  dio: mock.dio,
  tokenStore: MemoryTokenStore(
    session: const AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: 'profile-a',
    ),
  ),
);

SyncSourceDefinition source(String kind) =>
    SyncSourceDefinition.projectionEnvelope(
      sourceKey: kind,
      owner: 'Profile',
      path: 'api/v1/me/now/',
      projectionKind: kind,
    );

void main() {
  test('two SyncEngines cannot resurrect a newer revoked owner projection',
      () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final firstRequest = Completer<void>();
    final delayedReply = Completer<MockResponse>();
    var calls = 0;
    final api = clientFor(MockClient((_) async {
      calls++;
      if (calls == 1) {
        firstRequest.complete();
        return delayedReply.future;
      }
      return MockResponse(jsonEncode({
        'error': {'code': 'permission_denied', 'message': 'Denied'},
      }), 403);
    }));
    final a = SyncEngine(
      api: api, store: store, database: db, profileId: 'profile-a',
    );
    final b = SyncEngine(
      api: api, store: store, database: db, profileId: 'profile-a',
    );
    final owner = source('personal.now');
    final waiting = a.pullSource(owner);
    await firstRequest.future;
    await expectLater(b.pullSource(owner), throwsA(isA<Exception>()));
    delayedReply.complete(MockResponse(
      jsonEncode(envelope('personal.now', 'old', actor: 'profile-a')),
      200,
    ));
    await waiting;
    expect(await store.readProjection('personal.now'), isNull);
    final sources = await db.select(db.syncSources).get();
    expect(sources.single.invalidated, isTrue);
    expect(sources.single.lastErrorCode, 'permission_denied');
  });

  test('owner generated-at is monotonic and foreign actors are rejected',
      () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    var response = envelope(
      'personal.now', 'newer',
      generated: '2026-11-04T08:00:00Z',
      actor: 'profile-a',
    );
    final api = clientFor(MockClient((_) async =>
      MockResponse(jsonEncode(response), 200)));
    final sync = SyncEngine(
      api: api, store: store, database: db, profileId: 'profile-a',
    );
    final owner = source('personal.now');
    await sync.pullSource(owner);
    response = envelope(
      'personal.now', 'older',
      generated: '2026-11-03T08:00:00Z',
      actor: 'profile-a',
    );
    await sync.pullSource(owner);
    expect((await store.readProjection('personal.now'))?.payload['title'],
        'newer');
    response = envelope(
      'personal.now', 'foreign',
      generated: '2026-11-05T08:00:00Z',
      actor: 'profile-b',
    );
    await expectLater(sync.pullSource(owner), throwsFormatException);
    expect((await store.readProjection('personal.now'))?.payload['title'],
        'newer');

    expect(
      () => SyncEngine(
        api: api, store: store, database: db, profileId: 'profile-b',
      ),
      throwsArgumentError,
    );
  });

  test('logout/deactivation stops in-flight replacement without data loss',
      () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    await store.putProjection(
      kind: 'personal.now', schemaVersion: 1,
      payload: {'title': 'received locally'},
    );
    final started = Completer<void>();
    final waiting = Completer<MockResponse>();
    final api = clientFor(MockClient((_) async {
      started.complete();
      return waiting.future;
    }));
    final sync = SyncEngine(
      api: api, store: store, database: db, profileId: 'profile-a',
    );
    final pull = sync.pullSource(source('personal.now'));
    await started.future;
    sync.deactivate();
    waiting.complete(MockResponse(jsonEncode(
      envelope('personal.now', 'late', actor: 'profile-a'),
    ), 200));
    await pull;
    expect((await store.readProjection('personal.now'))?.payload['title'],
        'received locally');
  });

  test('expired projection cannot be reused offline across Profile reads',
      () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final first = ProfileStore(db, 'profile-a');
    await first.putProjection(
      kind: 'private.capability', schemaVersion: 1,
      payload: {'state': 'allowed'},
      expiresAt: DateTime.now().toUtc().subtract(const Duration(seconds: 1)),
    );
    expect(await first.readProjection('private.capability'), isNull);
    expect(await first.readProjections('private.capability'), isEmpty);
    expect(await first.watchProjection('private.capability').first, isNull);
    expect(await ProfileStore(db, 'profile-b')
        .readProjection('private.capability'), isNull);
  });
}
