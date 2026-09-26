import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'fakes.dart';

void main() {
  test('sync applies owner projections locally and preserves them offline',
      () async {
    var online = true;
    var revision = 1;
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      if (!online) throw const SocketException('offline');
      final key = switch (request.url.path) {
        '/api/v1/me/now/' => 'personal.now',
        '/api/v1/me/ongoing/' => 'personal.ongoing',
        '/api/v1/me/' => 'personal.me',
        _ => throw StateError('unexpected route ${request.url.path}'),
      };
      return http.Response(
        jsonEncode({
          'meta': {
            'projection': key,
            'schema_version': 1,
            'generated_at': '2026-09-26T10:00:00Z',
            'scope': 'personal',
          },
          'data': {
            'revision': revision,
            'items': key == 'personal.now'
                ? [
                    {'label': 'Action $revision'},
                  ]
                : <Object>[],
          },
        }),
        200,
      );
    });

    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      httpClient: client,
      tokenStore: tokens,
    );
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final sync = SyncEngine(
      api: api,
      store: store,
      database: database,
      profileId: 'profile-a',
    );

    await sync.refreshRoots();
    expect(
      (await store.readProjection('personal.now'))?.payload['revision'],
      1,
    );

    revision = 2;
    await sync.refreshRoots();
    expect(
      (await store.readProjection('personal.now'))?.payload['revision'],
      2,
    );

    online = false;
    await sync.refreshRoots();
    expect(
      (await store.readProjection('personal.now'))?.payload['revision'],
      2,
    );

    final source = await (database.select(database.syncSources)
          ..where((row) => row.sourceKey.equals('personal.now')))
        .getSingle();
    expect(source.invalidated, isTrue);

    online = true;
    revision = 3;
    await sync.refreshRoots();
    expect(
      (await store.readProjection('personal.now'))?.payload['revision'],
      3,
    );
  });
}
