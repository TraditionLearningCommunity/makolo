import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
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
  late Directory mediaDirectory;

  setUp(() {
    mediaDirectory = Directory.systemTemp.createTempSync('makolo-c3-media-');
    database = MakoloDatabase.memory();
    outbox = OutboxRepository(database, 'profile-a');
    drafts = DraftRepository(
      database: database,
      outbox: outbox,
      profileId: 'profile-a',
    );
    tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    requests = [];
    reachable = true;
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        requests.add(request);
        if (!reachable) {
          return const MockResponse('{"error":"unavailable"}', 503);
        }
        if (request.url.path.endsWith('/respond/')) {
          return MockResponse(
            jsonEncode({
              'id': 'response-confirmed',
              'point_id': 'point-vote',
              'status': 'active',
              'value': (request.data as Map)['value'],
            }),
            200,
          );
        }
        if (request.url.path.endsWith('/media/')) {
          return MockResponse(
            jsonEncode({
              'point_id': 'point-confirmed',
              'attachment': {'id': 'attachment-confirmed'},
            }),
            200,
          );
        }
        if (request.url.path.endsWith('/compose/') ||
            request.url.path.endsWith('/forms/')) {
          return MockResponse(jsonEncode({'point_id': 'point-confirmed'}), 200);
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
      refreshDetail: (_, _) async {},
      mediaMime: (filename, kind) =>
          kind == 'image' ? 'image/png' : 'application/octet-stream',
      mediaDirectory: () async => mediaDirectory,
    );
  });

  tearDown(() async {
    await database.close();
    if (await mediaDirectory.exists()) {
      await mediaDirectory.delete(recursive: true);
    }
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

  test(
    'offline composition is durably queued without network requests',
    () async {
      reachable = false;
      await delivery.saveDraft(
        conversationId: 'conv-1',
        kind: 'information',
        payload: {'body': 'Bonjour'},
      );
      final reference = await delivery.queue(
        conversationId: 'conv-1',
        mode: 'text',
        body: 'Bonjour',
      );
      expect(requests, isEmpty);
      final draft = await delivery.readDraft(
        conversationId: 'conv-1',
        kind: 'information',
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
    },
  );

  test(
    'a Point response survives offline and replays once with the same reference',
    () async {
      reachable = false;
      final reference = await delivery.queue(
        conversationId: 'conv-1',
        mode: 'response',
        pointId: 'point-vote',
        responseValue: false,
        representedSpaceId: 'space-1',
      );
      expect(requests, isEmpty);
      final pending = await delivery.watchOutgoing('conv-1').first;
      expect(pending.single.kind, 'response');
      expect(pending.single.pointId, 'point-vote');
      expect(pending.single.responseValue, false);
      expect(pending.single.representedSpaceId, 'space-1');
      expect(pending.single.state, OutboxState.queued.wireValue);
      final rows = await database.select(database.outboxOperations).get();
      expect(rows.single.ownerIdempotencyKey, reference);
      expect(rows.single.replayPolicy, ReplayPolicy.idempotent.wireValue);

      reachable = true;
      final worker = processor();
      await worker.run();
      await worker.run();
      expect(requests.length, 1);
      expect(requests.single.url.path,
          '/api/v1/conversations/points/point-vote/respond/');
      final sent = requests.single.data as Map;
      expect(sent['client_reference'], reference);
      expect(sent['represented_space_id'], 'space-1');
      expect(sent['value'], false);
      final confirmed = await database.select(database.outboxOperations).get();
      expect(confirmed.single.state, OutboxState.confirmed.wireValue);
    },
  );

  test(
    'two distinct Points coexist; owner confirms each exactly once',
    () async {
      final first = await delivery.queue(
        conversationId: 'conv-1',
        mode: 'text',
        body: 'Bonjour',
      );
      final second = await delivery.queue(
        conversationId: 'conv-1',
        mode: 'point',
        kind: 'poll',
        title: 'Quel moment ?',
        options: ['Matin', 'Soir'],
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
      expect(
        rows.every((row) => row.state == OutboxState.confirmed.wireValue),
        isTrue,
      );
      final outgoing = await delivery.watchOutgoing('conv-1').first;
      expect(outgoing.every((intent) => intent.isConfirmed), isTrue);
    },
  );

  test('a queued Form is routed through the owner Form endpoint', () async {
    final intent = await delivery.queue(
      conversationId: 'conv-2',
      mode: 'form',
      title: 'Pièces à préparer',
      questions: ['Votre nom ?'],
    );
    await processor().run();
    expect(requests.single.url.path, '/api/v1/conversations/conv-2/forms/');
    expect((requests.single.data as Map)['client_reference'], intent);
    expect((requests.single.data as Map)['questions'], ['Votre nom ?']);
  });

  test(
    'private media is copied before sending and survives original deletion',
    () async {
      final captured = File('${mediaDirectory.path}/captured.png');
      await captured.writeAsBytes([137, 80, 78, 71, 13, 10, 26, 10, 0]);
      final reference = await delivery.queue(
        conversationId: 'conv-1',
        mode: 'media',
        mediaKind: 'image',
        filename: 'captured.png',
        filePath: captured.path,
        body: 'Voici une photo',
      );
      await captured.delete();
      final outgoing = await delivery.watchOutgoing('conv-1').first;
      expect(outgoing.single.reference, reference);
      expect(outgoing.single.mediaKind, 'image');
      expect(outgoing.single.filename, 'captured.png');
      final copy = File(outgoing.single.localFilePath!);
      expect(await copy.exists(), isTrue);
      expect(await copy.readAsBytes(), [137, 80, 78, 71, 13, 10, 26, 10, 0]);
      expect(requests, isEmpty);
    },
  );

  test('a Question with a photo dispatches one typed media mutation', () async {
    final photo = File('${mediaDirectory.path}/question.png');
    await photo.writeAsBytes([137, 80, 78, 71, 13, 10, 26, 10, 0]);
    await delivery.queue(
      conversationId: 'conv-1',
      mode: 'media',
      pointKind: 'question',
      title: 'Vous aimez cette photo ?',
      body: 'Laquelle préférez-vous ?',
      filePath: photo.path,
      filename: photo.uri.pathSegments.last,
      mediaKind: 'image',
    );
    await processor().run();
    expect(requests.single.url.path, '/api/v1/conversations/conv-1/media/');
    final data = requests.single.data as FormData;
    final fields = Map<String, String>.fromEntries(data.fields);
    expect(fields['point_kind'], 'question');
    expect(fields['title'], 'Vous aimez cette photo ?');
    expect(fields['body'], 'Laquelle préférez-vous ?');
    expect(data.files.single.key, 'file');
    final rows = await database.select(database.outboxOperations).get();
    expect(rows.single.state, OutboxState.confirmed.wireValue);
  });

  test(
    'a mismatched Profile cannot dispatch a queued owner mutation',
    () async {
      await delivery.queue(
        conversationId: 'conv-1',
        mode: 'text',
        body: 'Privé',
      );
      tokens.session = const AuthSession(
        accessToken: 'other',
        refreshToken: 'other',
        profileId: 'profile-other',
      );
      await processor().run();
      expect(requests, isEmpty);
      final rows = await database.select(database.outboxOperations).get();
      expect(rows.single.state, OutboxState.awaitingConfirmation.wireValue);
    },
  );
}
