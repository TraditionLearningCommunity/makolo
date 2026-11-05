import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/features/continuity/conversation_local_delivery.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_processor.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  late MakoloDatabase database;
  late OutboxRepository outbox;
  late DraftRepository drafts;
  late MemoryTokenStore tokens;
  late ConversationLocalDelivery delivery;
  late List<MockRequest> requests;
  late bool reachable;

  setUp(() {
    database = MakoloDatabase.memory();
    outbox = OutboxRepository(database, 'profile-a');
    drafts = DraftRepository(
      database: database, outbox: outbox, profileId: 'profile-a',
    );
    tokens = MemoryTokenStore(session: const AuthSession(
      accessToken: 'access', refreshToken: 'refresh',
      profileId: 'profile-a',
    ));
    requests = [];
    reachable = true;
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        requests.add(request);
        if (!reachable) return const MockResponse('{"error":"unavailable"}', 503);
        if (request.url.path.endsWith('/compose/') ||
            request.url.path.endsWith('/forms/')) {
          return MockResponse(
            jsonEncode({'point_id': 'point-confirmed'}),
            200,
          );
        }
        throw StateError('Unexpected request ${request.url.path}');
      }).dio,
    );
    delivery = ConversationLocalDelivery(
      database: database,
      drafts: drafts,
      outbox: outbox,
      tokens: tokens,
      api: api,
      profileId: 'profile-a',
      refreshDetail: (_, __) async {},
    );
  });

  tearDown(() async {
    await database.close();
  });

  OutboxProcessor processor() => OutboxProcessor(
    repository: outbox,
    handlers: {ConversationLocalDelivery.operationKind: delivery.handle},
    expectedOwners: {
      ConversationLocalDelivery.operationKind: ConversationLocalDelivery.owner,
    },
    expectedReplayPolicies: {
      ConversationLocalDelivery.operationKind: ReplayPolicy.idempotent,
    },
    canDispatch: (operation) async =>
        (await tokens.readSession())?.profileId == operation.profileId,
  );

  test('offline composition is durably queued without network requests', () async {
    reachable = false;
    await delivery.saveDraft(
      conversationId: 'conv-1', kind: 'information',
      payload: {'body': 'Bonjour'},
    );
    final reference = await delivery.queue(
      conversationId: 'conv-1', mode: 'text', body: 'Bonjour',
    );
    expect(requests, isEmpty);
    final draft = await delivery.readDraft(
      conversationId: 'conv-1', kind: 'information',
    );
    expect(draft?['body'], 'Bonjour');
    final pending = await delivery.watchOutgoing('conv-1').first;
    expect(pending.single.reference, reference);
    expect(pending.single.body, 'Bonjour');
    expect(pending.single.state, OutboxState.queued.wireValue);
    final rows = await database.select(database.outboxOperations).get();
    expect(rows.single.ownerIdempotencyKey, reference);
    expect(rows.single.replayPolicy, ReplayPolicy.idempotent.wireValue);
    expect(rows.single.resourceId, 'conv-1');
  });

  test('two distinct Points coexist; owner confirms each exactly once', () async {
    final first = await delivery.queue(
      conversationId: 'conv-1', mode: 'text', body: 'Bonjour',
    );
    final second = await delivery.queue(
      conversationId: 'conv-1', mode: 'point', kind: 'poll',
      title: 'Quel moment ?', options: ['Matin', 'Soir'],
    );
    expect(first, isNot(second));
    final worker = processor();
    await worker.run();
    await worker.run();
    expect(requests.length, 2);
    final references = requests
        .map((request) => (request.data as Map)['client_reference'])
        .toSet();
    expect(references, {first, second});
    final rows = await database.select(database.outboxOperations).get();
    expect(rows.length, 2);
    expect(rows.every((row) =>
        row.state == OutboxState.confirmed.wireValue), isTrue);
    final outgoing = await delivery.watchOutgoing('conv-1').first;
    expect(outgoing.every((intent) => intent.isConfirmed), isTrue);
  });

  test('a queued Form is routed through the owner Form endpoint', () async {
    final intent = await delivery.queue(
      conversationId: 'conv-2', mode: 'form',
      title: 'Pièces à préparer', questions: ['Votre nom ?'],
    );
    await processor().run();
    expect(requests.single.url.path,
        '/api/v1/conversations/conv-2/forms/');
    expect((requests.single.data as Map)['client_reference'], intent);
    expect((requests.single.data as Map)['questions'], ['Votre nom ?']);
  });

  test('a mismatched Profile cannot dispatch a queued owner mutation', () async {
    await delivery.queue(
      conversationId: 'conv-1', mode: 'text', body: 'Privé',
    );
    tokens.session = const AuthSession(
      accessToken: 'other', refreshToken: 'other',
      profileId: 'profile-other',
    );
    await processor().run();
    expect(requests, isEmpty);
    final rows = await database.select(database.outboxOperations).get();
    expect(rows.single.state, OutboxState.awaitingConfirmation.wireValue);
  });
}
