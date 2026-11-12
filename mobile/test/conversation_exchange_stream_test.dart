import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/conversation_entry_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/conversation_exchange_sheet.dart';
import 'package:makolo_mobile/features/continuity/conversation_repository.dart';
import 'package:makolo_mobile/network/api_error.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

Map<String, dynamic> message(
  String id,
  int sequence,
  int version, {
  String body = 'Message reçu',
  bool removed = false,
}) => {
  'id': id,
  'entry_id': id,
  'point_id': 'point-a',
  'sequence': sequence,
  'last_change_version': version,
  'body': body,
  'removed': removed,
  'own': false,
  'edit_version': 1,
  'author': {'id': 'person-b', 'label': 'Personne B'},
  'created_at': '2026-11-12T10:00:00Z',
  'attachments': [],
  'mentions': [],
  'references': [],
  'reactions': [],
  'capabilities': {},
};

void main() {
  late MakoloDatabase database;
  late ProfileStore store;
  late ConversationEntryStore entries;
  setUp(() {
    database = MakoloDatabase.memory();
    store = ProfileStore(database, 'profile-a');
    entries = ConversationEntryStore(database, store, 'profile-a');
  });
  tearDown(() async {
    await database.close();
  });

  ConversationRepository repository(
    Future<MockResponse> Function(MockRequest) handler,
  ) {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient(handler).dio,
    );
    final sync = SyncEngine(
      api: api,
      store: store,
      database: database,
      profileId: 'profile-a',
    );
    return ConversationRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );
  }

  test(
    'local projection and watermark survive repository reconstruction',
    () async {
      await entries.apply('point-a', [message('one', 1, 1)], nextVersion: 1);
      final reconstructed = ConversationEntryStore(
        database,
        ProfileStore(database, 'profile-a'),
        'profile-a',
      );
      expect((await reconstructed.read('point-a')).single['id'], 'one');
      expect(await reconstructed.version('point-a'), 1);
    },
  );

  test('delta page and watermark commit atomically; malformed later row rolls back', () async {
    await expectLater(
      entries.apply('point-a', [
        message('one', 1, 1),
        {'id': 'malformed'},
      ], nextVersion: 2),
      throwsFormatException,
    );
    expect(await entries.read('point-a'), isEmpty);
    expect(await entries.version('point-a'), 0);
  });

  test(
    'historical acquisition cannot overwrite a newer edit or tombstone',
    () async {
      await entries.apply('point-a', [
        message('one', 1, 8, body: '', removed: true),
      ], nextVersion: 8);
      await entries.apply('point-a', [
        message('one', 1, 1, body: 'Ancien texte privé'),
      ]);
      final row = (await entries.read('point-a')).single;
      expect(row['removed'], true);
      expect(row['body'], '');
    },
  );

  test('same server identity reconciles without duplicated bubbles', () async {
    final row = message('one', 1, 1)..['client_reference'] = 'stable-intent';
    await entries.apply('point-a', [row], nextVersion: 1);
    await entries.apply('point-a', [row], nextVersion: 1);
    expect(await entries.read('point-a'), hasLength(1));
  });

  test('Profile caches and revocation never touch another Profile', () async {
    final other = ConversationEntryStore(
      database,
      ProfileStore(database, 'profile-b'),
      'profile-b',
    );
    await entries.apply('point-a', [message('one', 1, 1)], nextVersion: 1);
    expect(await other.read('point-a'), isEmpty);
    await other.apply('point-a', [message('two', 2, 2)], nextVersion: 2);
    await entries.revoke('point-a');
    expect(await entries.read('point-a'), isEmpty);
    expect((await other.read('point-a')).single['id'], 'two');
  });

  test(
    'reconnection drains all delta pages before advancing to stream head',
    () async {
      final requested = <int>[];
      final repo = repository((request) async {
        if (request.url.path.endsWith('/receipts/'))
          return const MockResponse('{"entries":[]}', 200);
        final after = int.parse(request.url.queryParameters['after_version']!);
        requested.add(after);
        return MockResponse(
          jsonEncode({
            'viewer_profile_id': 'profile-a',
            'point_id': 'point-a',
            'scope': 'scope-a',
            'stream_version': 2,
            'results': [
              message(after == 0 ? 'one' : 'two', after + 1, after + 1),
            ],
            'next_version': after + 1,
            'has_more': after == 0,
          }),
          200,
        );
      });
      await repo.refreshExchange('point-a');
      expect(requested, [0, 1]);
      expect(await entries.version('point-a'), 2);
      expect(await entries.read('point-a'), hasLength(2));
    },
  );

  test('revocation purges local messages instead of rendering stale private history', () async {
    await entries.apply('point-a', [message('one', 1, 1)], nextVersion: 1);
    final repo = repository(
      (_) async => const MockResponse('{"detail":"inaccessible"}', 403),
    );
    await expectLater(
      repo.refreshExchange('point-a'),
      throwsA(isA<MakoloApiError>()),
    );
    expect(await entries.read('point-a'), isEmpty);
  });

  test(
    'new Profile response cannot be persisted in the old Profile store',
    () async {
      final repo = repository(
        (_) async => MockResponse(
          jsonEncode({
            'viewer_profile_id': 'profile-b',
            'point_id': 'point-a',
            'scope': 'scope-b',
            'results': [message('private-b', 1, 1)],
            'next_version': 1,
            'has_more': false,
          }),
          200,
        ),
      );
      await expectLater(repo.refreshExchange('point-a'), throwsFormatException);
      expect(await entries.read('point-a'), isEmpty);
    },
  );

  testWidgets(
    'offline screen renders useful Drift messages with no refresh skeleton',
    (tester) async {
      await entries.apply('point-a', [message('one', 1, 1)], nextVersion: 1);
      final repo = ConversationRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
      );
      await tester.pumpWidget(
        MaterialApp(
          home: ConversationExchangeSheet(
            repository: repo,
            conversationId: 'conversation-a',
            pointId: 'point-a',
            title: 'Discussion',
            canRespond: false,
            capabilities: const {},
            onPublished: (_) {},
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Message reçu'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );
}
