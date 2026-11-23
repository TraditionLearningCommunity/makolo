import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/features/mark/mark_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

import 'fakes.dart';

class _IntakeApi extends MakoloApiClient {
  _IntakeApi()
    : super(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(),
      );

  String? lastPath;
  Map<String, Object?>? lastFields;
  List<MakoloUploadFile> lastFiles = const [];
  bool timeout = false;

  @override
  Future<ApiResponse> upload(
    String path, {
    String method = 'POST',
    Map<String, Object?> fields = const {},
    List<MakoloUploadFile> files = const [],
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
    TransferProgress? onProgress,
  }) async {
    lastPath = path;
    lastFields = fields;
    lastFiles = files;
    if (timeout) throw TimeoutException('connection was interrupted');
    return ApiResponse(
      201,
      '{"data":{"state":"received","receipt_id":"test-receipt-1",'
      '"action_confirmed":false,"message":"Demande reçue."}}',
      const {},
    );
  }
}

void main() {
  late MakoloDatabase database;
  late _IntakeApi api;
  late DraftRepository drafts;
  late MarkRepository repository;

  setUp(() {
    database = MakoloDatabase.memory();
    api = _IntakeApi();
    drafts = DraftRepository(
      database: database,
      outbox: OutboxRepository(database, 'profile-intake'),
      profileId: 'profile-intake',
    );
    repository = MarkRepository(AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
      api: api,
      drafts: drafts,
    ));
  });

  tearDown(() async {
    await database.close();
    api.close(force: true);
  });

  test('audio-only receives server receipt and never claims a business action',
      () async {
    final result = await repository.submitIntake(
      actor: const PersonalActorContext(),
      input: '',
      attachments: const [
        {'file_id': 'voice', 'kind': 'audio', 'purpose': 'mark_intake'},
      ],
      links: const [],
      uploads: const [
        MakoloUploadFile(
          fieldName: 'files',
          path: '/private/voice.m4a',
          filename: 'voice.m4a',
          contentType: 'audio/mp4',
        ),
      ],
      requestKey: '0123456789abcdef0123456789abcdef',
      submissionFingerprint: 'media-payload-v1',
    );
    expect(result.state, 'received');
    expect(result.raw['action_confirmed'], isFalse);
    expect(api.lastPath, 'api/v1/me/mark/intake/');
    expect(api.lastFields?['text'], '');
    expect(api.lastFiles.single.contentType, 'audio/mp4');
    expect(
      await repository.readDraft(const PersonalActorContext()),
      isNull,
    );
  });

  test('timeout retains durable same-key draft for explicit retry', () async {
    api.timeout = true;
    final result = await repository.submitIntake(
      actor: const PersonalActorContext(),
      input: 'Texte initial',
      attachments: const [],
      links: const ['https://example.org/a'],
      uploads: const [],
      requestKey: 'abcdefabcdefabcdefabcdefabcdefab',
      submissionFingerprint: 'payload-v1',
    );
    expect(result.state, 'receipt_unknown');
    final stored = await repository.readDraft(const PersonalActorContext());
    expect(stored?['submission_key'], 'abcdefabcdefabcdefabcdefabcdefab');
    expect(stored?['submission_fingerprint'], 'payload-v1');
    expect(stored?['links'], ['https://example.org/a']);
  });

  test('space intake is routed to its own owner without personal authority',
      () async {
    final space = SpaceActorContext(
      space: SpaceActorIdentity(id: 'space-id', slug: 'atelier'),
      perspective: ActorPerspective.opaque('mandate:1'),
    );
    final result = await repository.submitIntake(
      actor: space,
      input: '',
      attachments: const [],
      links: const ['https://example.org/a'],
      uploads: const [],
      requestKey: 'fedcfedcfedcfedcfedcfedcfedcfedc',
      submissionFingerprint: 'link-space-v1',
    );
    expect(result.state, 'received');
    expect(
      api.lastPath,
      'api/v1/organizations/workspaces/atelier/mark/intake/',
    );
    expect(api.lastFields?['context'], contains('mandate:1'));
  });
}
